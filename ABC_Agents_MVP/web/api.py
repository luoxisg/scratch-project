import asyncio
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.requests import ClientDisconnect, Request

from .documents import MAX_UPLOAD, extract
from .runtime import MockRuntime, OpenAIRuntime
from .schemas import (
    AssessmentDetail, AssessmentInput, AssessmentSummary, DecisionReport, Health,
    ParsedDocument, RunStatus, SavedAssessment,
)
from .storage import Store, now
from .workflow import Workflow

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ORIGINS = (
    "http://127.0.0.1:8000", "http://localhost:8000",
    "http://127.0.0.1:5173", "http://localhost:5173",
)
ACTIVE = {"queued", "running"}


def create_app(db_path=None, runtime=None, mode=None, timeout=None):
    mode = mode or os.getenv("ABC_MODE", "mock")
    if mode not in {"mock", "openai"}:
        raise ValueError("ABC_MODE must be mock or openai")
    if mode == "openai" and runtime is None and not os.getenv("OPENAI_API_KEY"):
        raise ValueError("OPENAI_API_KEY is required in openai mode")
    if runtime is None:
        runtime = (MockRuntime() if mode == "mock" else
                   OpenAIRuntime(os.getenv("ABC_AGENTS_MODEL", "gpt-4.1-mini")))
    timeout = timeout if timeout is not None else float(os.getenv("ABC_AGENT_TIMEOUT", "60"))
    if timeout <= 0:
        raise ValueError("ABC_AGENT_TIMEOUT must be positive")
    store = Store(Path(db_path or os.getenv("ABC_DB", ROOT / "data" / "reviews.sqlite3")))
    workflow = Workflow(store, runtime, timeout)
    jobs = {}
    origins = tuple(os.getenv("ABC_ORIGINS", ",".join(DEFAULT_ORIGINS)).split(","))

    @asynccontextmanager
    async def lifespan(_):
        store.prepare()
        yield
        pending = list(jobs.values())
        for task, _ in pending:
            task.cancel()
        await asyncio.gather(*(task for task, _ in pending), return_exceptions=True)

    app = FastAPI(title="ABC Decision Review", version="1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=list(origins),
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=["localhost", "127.0.0.1", "[::1]"])

    @app.middleware("http")
    async def local_boundary(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin and origin not in origins:
            return JSONResponse({"detail": "origin_denied"}, status_code=403)
        if request.method == "POST":
            cap = MAX_UPLOAD + 65_536 if request.url.path == "/api/evidence/parse" else 1_000_000
            body = bytearray()
            try:
                async for chunk in request.stream():
                    if len(body) + len(chunk) > cap:
                        return JSONResponse({"detail": "request_too_large"}, status_code=413)
                    body.extend(chunk)
            except ClientDisconnect:
                return JSONResponse({"detail": "client_disconnected"}, status_code=400)
            # Starlette replays a cached body to the downstream form/JSON parser.
            request._body = bytes(body)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
        )
        return response

    @app.exception_handler(RequestValidationError)
    async def bad_request(_, error):
        return JSONResponse({
            "detail": "invalid_input",
            "fields": [{"location": issue["loc"], "type": issue["type"]} for issue in error.errors()]
        }, status_code=422)

    def get_assessment(assessment_id):
        row = store.detail(str(assessment_id))
        if row is None:
            raise HTTPException(404, "assessment_not_found")
        return row

    def get_run(assessment_id, run_id=None):
        get_assessment(assessment_id)
        runs = store.runs(str(assessment_id))
        if run_id:
            return next((run for run in runs if run["id"] == str(run_id)), None)
        return runs[0] if runs else None

    def status_view(run, include_history=True):
        if run is None:
            return {"status": "draft", "agents": {}, "audit": []}
        exclude = {"report"} if include_history else {"report", "audit", "initial_comparison", "comparison"}
        return {key: value for key, value in run.items() if key not in exclude}

    @app.get("/api/health", response_model=Health)
    async def health():
        return {"status": "ok", "mode": mode, "model": runtime.model}

    @app.get("/api/demo", response_model=AssessmentInput)
    async def demo():
        return AssessmentInput.model_validate_json((Path(__file__).parent / "demo.json").read_text())

    @app.post("/api/evidence/parse", response_model=ParsedDocument)
    async def parse_document(file: Annotated[UploadFile, File()]):
        try:
            contents = await file.read(MAX_UPLOAD + 1)
            if len(contents) > MAX_UPLOAD:
                raise HTTPException(413, "request_too_large")
            return await asyncio.to_thread(extract, file.filename or "", contents)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "unsupported_or_unreadable_document") from None
        finally:
            await file.close()

    @app.post("/api/assessments", status_code=201, response_model=SavedAssessment)
    async def create(task: AssessmentInput):
        payload = task.model_dump(mode="json")
        payload["evidence"] = [{"id": f"E{i}", **item} for i, item in enumerate(payload["evidence"], 1)]
        return store.create(payload)

    @app.get("/api/assessments", response_model=list[AssessmentSummary])
    async def list_assessments():
        return store.list()

    @app.get("/api/assessments/{assessment_id}", response_model=AssessmentDetail)
    async def detail(assessment_id: UUID):
        row = get_assessment(assessment_id)
        return {**row, "runs": [status_view(run, False) for run in store.runs(str(assessment_id))]}

    @app.post("/api/assessments/{assessment_id}/run", status_code=202, response_model=RunStatus,
              response_model_exclude_unset=True)
    async def start_run(assessment_id: UUID):
        row = get_assessment(assessment_id)
        if len(jobs) >= 4:
            raise HTTPException(429, "too_many_active_runs")
        run = store.start(str(assessment_id), mode)
        if run is None:
            raise HTTPException(409, "already_running")
        job = asyncio.create_task(workflow.execute(run, row["assessment"]))
        jobs[run["id"]] = (job, run)

        def finish(task):
            jobs.pop(run["id"], None)
            if task.cancelled() and run["status"] == "queued":
                run.update(status="cancelled", finished_at=now())
                store.save(run)

        job.add_done_callback(finish)
        return status_view(run)

    @app.post("/api/assessments/{assessment_id}/cancel", status_code=202)
    async def cancel_run(assessment_id: UUID):
        run = get_run(assessment_id)
        if not run or run["id"] not in jobs or run["status"] not in ACTIVE:
            raise HTTPException(409, "no_active_run")
        jobs[run["id"]][0].cancel()
        return {"status": "cancelling"}

    @app.get("/api/assessments/{assessment_id}/status", response_model=RunStatus,
             response_model_exclude_unset=True)
    async def status(assessment_id: UUID, run_id: UUID | None = None):
        run = get_run(assessment_id, run_id)
        if run_id and not run:
            raise HTTPException(404, "run_not_found")
        return status_view(run)

    @app.get("/api/assessments/{assessment_id}/report", response_model=DecisionReport)
    async def report(assessment_id: UUID, run_id: UUID | None = None):
        run = get_run(assessment_id, run_id)
        if not run or run["status"] != "complete":
            if run_id and not run:
                raise HTTPException(404, "run_not_found")
            raise HTTPException(409, "report_not_ready")
        return run["report"]

    @app.get("/api/{rest:path}", include_in_schema=False)
    async def api_not_found(rest: str):
        raise HTTPException(404, "route_not_found")

    static = ROOT / "frontend" / "dist"
    if static.is_dir():
        app.mount("/", StaticFiles(directory=static, html=True), name="frontend")
    return app
