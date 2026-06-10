import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class JobState:
    job_id: str
    status: str = "pending"       # pending | downloading | done | error
    progress: float = 0.0
    filename: Optional[str] = None
    filepath: Optional[str] = None
    error: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobState] = {}
        self._lock = threading.Lock()

    def create(self) -> str:
        job_id = uuid.uuid4().hex
        with self._lock:
            self._jobs[job_id] = JobState(job_id=job_id)
        return job_id

    def get(self, job_id: str) -> Optional[JobState]:
        with self._lock:
            return self._jobs.get(job_id)

    def update_progress(self, job_id: str, progress: float) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "downloading"
                job.progress = progress

    def set_done(self, job_id: str, filepath: str, filename: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "done"
                job.progress = 100.0
                job.filepath = filepath
                job.filename = filename

    def set_error(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job:
                job.status = "error"
                job.error = message

    def all_jobs(self) -> list[JobState]:
        with self._lock:
            return list(self._jobs.values())

    def remove(self, job_id: str) -> None:
        with self._lock:
            self._jobs.pop(job_id, None)
