import asyncio
import json
import time
from functools import partial
from io import BytesIO
from zipfile import ZipFile

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from web.api import create_app
from web.runtime import MockRuntime


local_client = partial(TestClient, base_url="http://127.0.0.1")


def wait_for_status(client, aid, expected):
    deadline = time.monotonic() + 4
    while time.monotonic() < deadline:
        response = client.get(f"/api/assessments/{aid}/status")
        assert response.status_code == 200
        result = response.json()
        if result["status"] == expected:
            return result
        if result["status"] in {"failed", "cancelled", "complete"}:
            pytest.fail(f"Expected {expected}, saw {result['status']}: {result.get('error')}")
        time.sleep(0.015)
    pytest.fail(f"Timed out waiting for {expected}")


def create(client, cross=True, evidence=True):
    task = client.get("/api/demo").json()
    task["cross_examine"] = cross
    if not evidence:
        task["evidence"] = []
    response = client.post("/api/assessments", json=task)
    assert response.status_code == 201
    return response.json()["id"]


class BarrierRuntime(MockRuntime):
    def __init__(self):
        self.arrived = set()
        self.released = asyncio.Event()

    async def call(self, step, payload):
        if step in ("B", "C") and payload["round"] == 1:
            self.arrived.add(step)
            if len(self.arrived) == 2:
                self.released.set()
            await self.released.wait()
        return await super().call(step, payload)


@pytest.mark.parametrize("cross", [True, False])
def test_end_to_end_review_and_original_rounds(tmp_path, cross):
    runtime = BarrierRuntime()
    with local_client(create_app(tmp_path / "test.db", runtime=runtime, timeout=0.5)) as client:
        assert client.get("/api/health").json()["mode"] == "mock"
        aid = create(client, cross)
        assert client.get(f"/api/assessments/{aid}/report").status_code == 409
        assert client.post(f"/api/assessments/{aid}/run").status_code == 202
        run = wait_for_status(client, aid, "complete")
        result = client.get(f"/api/assessments/{aid}/report").json()
        assert result["decision"]["state"] == "evidence_required"
        assert result["necessity"]["willingness_to_pay"] == "unknown"
        assert "VMS" in result["sufficiency"]["rationale"]
        assert runtime.arrived == {"B", "C"}  # A serial scheduler cannot clear the barrier.
        assert [(step["agent"], step["round"]) for step in run["audit"]] == [
            ("A", None), ("B", 1), ("C", 1), *([("B", 2), ("C", 2)] if cross else []), ("A", None)
        ]
        first = {step["agent"]: step for step in run["audit"] if step["round"] == 1}
        assert first["B"]["input"] == first["C"]["input"]
        assert not any(k.endswith("round_one") for k in first["B"]["input"])
        assert first["B"]["output"]["challenge"] == first["C"]["output"]["challenge"] == ""
        assert first["B"]["output"]["findings"][0]["evidence_ids"] == ["E1"]
        assert all(entry["duration_ms"] >= 0 and entry["usage"] is None for entry in run["audit"])
        if cross:
            second = {step["agent"]: step for step in run["audit"] if step["round"] == 2}
            assert second["B"]["input"]["peer_round_one"] == first["C"]["output"]
            assert second["C"]["input"]["peer_round_one"] == first["B"]["output"]
            assert second["B"]["output"]["challenge"] and second["C"]["output"]["challenge"]
        assert client.get("/api/assessments").json()[0]["status"] == "complete"
        assert client.get(f"/api/assessments/{aid}").json()["runs"][0]["id"] == run["id"]
        assert client.post(f"/api/assessments/{aid}/run").status_code == 202
        wait_for_status(client, aid, "complete")
        assert client.get(f"/api/assessments/{aid}/report", params={"run_id": run["id"]}).json() == result


def test_missing_evidence(tmp_path):
    with local_client(create_app(tmp_path / "test.db", mode="mock")) as client:
        aid = create(client, evidence=False)
        client.post(f"/api/assessments/{aid}/run")
        wait_for_status(client, aid, "complete")
        report = client.get(f"/api/assessments/{aid}/report").json()
        assert report["decision"]["action"] == "gather_evidence"
        assert not any(f["evidence_ids"] for f in report["sufficiency"]["findings"])


class FailedReviewer(MockRuntime):
    def __init__(self, fail):
        self.fail = fail

    async def call(self, step, payload):
        if step == "B":
            if self.fail:
                raise RuntimeError("PRIVATE_PROVIDER_MESSAGE")
            await asyncio.sleep(60)
        return await super().call(step, payload)


@pytest.mark.parametrize(("fail", "code", "step_status"), [
    (False, "agent_timeout", "timed_out"), (True, "agent_failed", "failed"),
])
def test_timeout_failure_and_preserving_peer(tmp_path, fail, code, step_status):
    with local_client(create_app(tmp_path / "test.db", runtime=FailedReviewer(fail), timeout=0.08)) as client:
        aid = create(client)
        client.post(f"/api/assessments/{aid}/run")
        run = wait_for_status(client, aid, "failed")
        assert run["error"] == code
        assert run["agents"]["B"] == step_status
        assert run["agents"]["C"] == "complete"
        assert run["audit"][-1]["output"] is not None
        assert "PRIVATE_PROVIDER_MESSAGE" not in json.dumps(run)
        assert client.get(f"/api/assessments/{aid}/report").status_code == 409


def test_cancel_and_duplicate_run(tmp_path):
    with local_client(create_app(tmp_path / "test.db", runtime=FailedReviewer(False), timeout=30)) as client:
        aid = create(client)
        assert client.post(f"/api/assessments/{aid}/run").status_code == 202
        wait_for_status(client, aid, "running")
        assert client.post(f"/api/assessments/{aid}/run").status_code == 409
        assert client.post(f"/api/assessments/{aid}/cancel").status_code == 202
        run = wait_for_status(client, aid, "cancelled")
        assert not any(entry["status"] == "running" for entry in run["audit"])
        assert client.get(f"/api/assessments/{aid}/report").status_code == 409


def pdf_text():
    writer = PdfWriter()
    page = writer.add_blank_page(200, 200)
    font = DictionaryObject({
        NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
        NameObject("/BaseFont"): NameObject("/Helvetica"),
    })
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
    })
    content = DecodedStreamObject()
    content.set_data(b"BT /F1 12 Tf 20 40 Td (sample evidence) Tj ET")
    page[NameObject("/Contents")] = content
    target = BytesIO()
    writer.write(target)
    return target.getvalue()


@pytest.mark.parametrize(("filename", "contents"), [
    ("report.txt", b"sample evidence"), ("report.md", b"# sample evidence"),
    ("report.pdf", pdf_text()), ("report.docx", None),
])
def test_extract_document(tmp_path, filename, contents):
    if contents is None:
        target = BytesIO()
        with ZipFile(target, "w") as archive:
            archive.writestr("word/document.xml", """
                <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
                    <w:p><w:r><w:t>sample evidence</w:t></w:r></w:p>
                </w:document>
            """)
        contents = target.getvalue()
    with local_client(create_app(tmp_path / "test.db", mode="mock")) as client:
        response = client.post("/api/evidence/parse", files={"file": (filename, contents)})
        assert response.status_code == 200, response.text
        assert "sample evidence" in response.json()["document_text"]
        assert response.json()["document_name"] == filename


def test_boundary_and_error_redaction(tmp_path, caplog):
    with local_client(create_app(tmp_path / "test.db", mode="mock")) as client:
        response = client.get("/api/health")
        assert response.headers["X-Content-Type-Options"] == "nosniff"
        assert "frame-ancestors 'none'" in response.headers["Content-Security-Policy"]
        assert client.get("/api/health", headers={"Host": "remote.example"}).status_code == 400
        assert client.get("/api/health", headers={"Origin": "https://remote.example"}).status_code == 403
        assert client.get("/api/health", headers={"Origin": "http://localhost:5173"}).headers[
            "Access-Control-Allow-Origin"] == "http://localhost:5173"
        invalid = client.post("/api/assessments", json={"project_name": "PRIVATE_INPUT"})
        assert invalid.status_code == 422
        assert "PRIVATE_INPUT" not in invalid.text and "PRIVATE_INPUT" not in caplog.text
        assert client.post("/api/evidence/parse", files={"file": ("fake.pdf", b"text")}).status_code == 422
        assert client.post("/api/evidence/parse", files={"file": ("app.exe", b"text")}).status_code == 422
        assert client.post("/api/evidence/parse", files={"file": ("big.txt", b"x" * (4 * 1024 * 1024 + 1))}).status_code == 413
