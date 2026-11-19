"""Single-process SQLite store. Each update commits a complete run snapshot."""
import json
import sqlite3
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Store:
    def __init__(self, path: Path):
        self.path = path

    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def prepare(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db, db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS assessments (
                    id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS review_runs (
                    id TEXT PRIMARY KEY, assessment_id TEXT NOT NULL,
                    created_at TEXT NOT NULL, status TEXT NOT NULL, snapshot TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS run_history
                  ON review_runs (assessment_id, created_at);
            """)
            for row in db.execute("SELECT snapshot FROM review_runs WHERE status IN ('queued','running')"):
                run = json.loads(row["snapshot"])
                run.update(status="failed", error="interrupted", finished_at=now())
                for entry in run["audit"]:
                    if entry["status"] == "running":
                        entry["status"] = "interrupted"
                self._update(db, run)

    def create(self, payload):
        assessment = {"id": str(uuid4()), "created_at": now(), "assessment": payload}
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO assessments VALUES (?, ?, ?)",
                       (assessment["id"], assessment["created_at"], json.dumps(payload)))
        return assessment

    def detail(self, assessment_id):
        with closing(self.connect()) as db:
            row = db.execute("SELECT * FROM assessments WHERE id=?", (assessment_id,)).fetchone()
        if row is None:
            return None
        return {"id": row["id"], "created_at": row["created_at"],
                "assessment": json.loads(row["payload"])}

    def list(self):
        with closing(self.connect()) as db:
            rows = db.execute("""
                SELECT a.*, r.snapshot FROM assessments AS a
                LEFT JOIN review_runs AS r ON r.id = (
                    SELECT id FROM review_runs WHERE assessment_id=a.id ORDER BY created_at DESC LIMIT 1
                )
                ORDER BY a.created_at DESC
            """).fetchall()
        items = []
        for row in rows:
            task = json.loads(row["payload"])
            run = json.loads(row["snapshot"]) if row["snapshot"] else {}
            items.append({"id": row["id"], "created_at": row["created_at"],
                          "project_name": task["project_name"], "category": task["category"],
                          "status": run.get("status", "draft"), "decision": run.get("decision"),
                          "mode": run.get("mode"), "agents": run.get("agents", {})})
        return items

    def runs(self, assessment_id):
        with closing(self.connect()) as db:
            rows = db.execute("""
                SELECT snapshot FROM review_runs WHERE assessment_id=? ORDER BY created_at DESC
            """, (assessment_id,)).fetchall()
        return [json.loads(row["snapshot"]) for row in rows]

    def start(self, assessment_id, mode):
        run = {"id": str(uuid4()), "assessment_id": assessment_id, "created_at": now(),
               "mode": mode, "status": "queued", "stage": "define", "error": None,
               "finished_at": None, "audit": [], "agents": {k: "waiting" for k in "ABC"}}
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("""
                SELECT id FROM review_runs WHERE assessment_id=? AND status IN ('queued','running')
            """, (assessment_id,)).fetchone():
                return None
            db.execute("INSERT INTO review_runs VALUES (?, ?, ?, ?, ?)",
                       (run["id"], assessment_id, run["created_at"], run["status"], json.dumps(run)))
        return run

    @staticmethod
    def _update(db, run):
        db.execute("UPDATE review_runs SET status=?, snapshot=? WHERE id=?",
                   (run["status"], json.dumps(run), run["id"]))

    def save(self, run):
        with closing(self.connect()) as db, db:
            self._update(db, run)
