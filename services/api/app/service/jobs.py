"""Process-local build-job registry.

EPHEMERAL by design: this tracks *live* progress (queued -> segmenting ->
clipping -> labeling -> packaging -> complete/failed) for the UI. It resets on
restart and is not shared across workers. The authoritative answer to "is this
build complete?" is the build.json manifest's status in B2 (see
service/builds.py), never this registry. Production needs a real job queue.

Thread-safe so a FastAPI BackgroundTask thread can update progress while the
request thread reads it. A non-terminal job for a build id blocks a second
concurrent run of the same build (see active_job_for).
"""

import uuid
from datetime import UTC, datetime
from threading import Lock

from app.types import BuildJob
from app.types.builds import JobStatus

_jobs: dict[str, BuildJob] = {}
_lock = Lock()

_TERMINAL: set[str] = {"complete", "failed"}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def create_job(build_id: str) -> BuildJob:
    """Register a new queued build job for a build and return it."""
    job_id = uuid.uuid4().hex
    now = _now()
    job = BuildJob(
        id=job_id,
        build_id=build_id,
        status="queued",
        progress=0.0,
        created_at=now,
        updated_at=now,
    )
    with _lock:
        _jobs[job_id] = job
    return job


def update_job(
    job_id: str,
    *,
    status: JobStatus | None = None,
    progress: float | None = None,
    message: str | None = None,
    error: str | None = None,
) -> None:
    """Patch a job's live fields. No-op if the job id is unknown."""
    with _lock:
        job = _jobs.get(job_id)
        if job is None:
            return
        data = job.model_dump()
        if status is not None:
            data["status"] = status
        if progress is not None:
            data["progress"] = progress
        if message is not None:
            data["message"] = message
        if error is not None:
            data["error"] = error
        data["updated_at"] = _now()
        _jobs[job_id] = BuildJob(**data)


def get_job(job_id: str) -> BuildJob | None:
    with _lock:
        return _jobs.get(job_id)


def list_jobs() -> list[BuildJob]:
    with _lock:
        return sorted(_jobs.values(), key=lambda j: j.created_at, reverse=True)


def active_job_for(build_id: str) -> BuildJob | None:
    """Return a non-terminal job for this build, if any (avoid double-run)."""
    with _lock:
        for job in _jobs.values():
            if job.build_id == build_id and job.status not in _TERMINAL:
                return job
    return None
