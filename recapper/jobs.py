"""Simple in-memory background job tracking for render/export tasks."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Callable
import threading
import traceback
import uuid


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Job:
    id: str
    kind: str
    status: str = "queued"  # queued, running, completed, failed, cancelled
    progress: float = 0.0
    stage: str = ""
    message: str = ""
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)
    result: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    logs: list[str] = field(default_factory=list)

    def to_dict(self, include_logs: bool = True) -> dict[str, Any]:
        data = asdict(self)
        if not include_logs:
            data.pop("logs", None)
        return data

    def log(self, msg: str) -> None:
        ts = _now_iso()
        self.logs.append(f"[{ts}] {msg}")
        self.updated_at = ts

    def update(self, **kwargs: Any) -> None:
        for k, v in kwargs.items():
            setattr(self, k, v)
        self.updated_at = _now_iso()


class JobManager:
    def __init__(self) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()

    def create(self, kind: str, message: str = "") -> Job:
        job = Job(id=f"job_{uuid.uuid4().hex[:12]}", kind=kind, message=message)
        with self._lock:
            self._jobs[job.id] = job
        return job

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def list(self) -> list[Job]:
        with self._lock:
            return list(self._jobs.values())

    def start(self, job: Job, fn: Callable[[Job], dict[str, Any]]) -> Job:
        def runner() -> None:
            job.update(status="running", stage="starting", message="Running")
            job.log("Job started")
            try:
                result = fn(job)
                if job.status != "cancelled":
                    job.update(status="completed", progress=100.0, stage="done", message="Completed", result=result or {})
                    job.log("Job completed")
            except Exception as e:
                job.update(status="failed", stage="error", message=str(e), error=str(e))
                job.log("Job failed: " + str(e))
                job.log(traceback.format_exc())

        t = threading.Thread(target=runner, daemon=True, name=f"job-{job.id}")
        t.start()
        return job


jobs = JobManager()
