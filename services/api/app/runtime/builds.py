"""Builds router: CRUD, run-with-live-progress, stats, sources, dataset explorer.

Thin HTTP layer — validation + status mapping only. All work flows through the
service layer (builds / pipeline / jobs); no boto3, no ML imports here.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.service import jobs
from app.service.builds import (
    BuildLocked,
    BuildNotFound,
    class_groups,
    create_build,
    delete_build,
    get_build,
    get_dashboard_stats,
    list_builds,
    list_sources,
    mark_running,
    update_build,
)
from app.service.files import FileKeyError, get_preview_url
from app.service.pipeline import run_job
from app.types import (
    Build,
    BuildConfig,
    BuilderStatsSummary,
    BuildJob,
    BuildSummary,
    ClassGroup,
    SourceVideo,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/builds/sources", response_model=list[SourceVideo])
async def list_sources_endpoint():
    return list_sources()


@router.get("/builds/stats", response_model=BuilderStatsSummary)
async def builds_stats_endpoint():
    return get_dashboard_stats()


@router.get("/builds/jobs/list", response_model=list[BuildJob])
async def list_jobs_endpoint():
    return jobs.list_jobs()


@router.get("/builds", response_model=list[BuildSummary])
async def list_builds_endpoint():
    return list_builds()


@router.post("/builds", response_model=Build)
async def create_build_endpoint(payload: dict):
    name = (payload or {}).get("name", "")
    description = (payload or {}).get("description", "")
    config_data = (payload or {}).get("config") or {}
    try:
        config = BuildConfig(**config_data)
        return create_build(name, description, config)
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from None


@router.get("/builds/{build_id}", response_model=Build)
async def get_build_endpoint(build_id: str):
    try:
        return get_build(build_id)
    except BuildNotFound:
        raise HTTPException(status_code=404, detail="Build not found") from None


@router.get("/builds/{build_id}/dataset", response_model=list[ClassGroup])
async def build_dataset_endpoint(build_id: str):
    """Class-grouped clips for the scoped /dataset explorer."""
    try:
        return class_groups(build_id)
    except BuildNotFound:
        raise HTTPException(status_code=404, detail="Build not found") from None


@router.patch("/builds/{build_id}", response_model=Build)
async def update_build_endpoint(build_id: str, payload: dict):
    payload = payload or {}
    config = None
    if payload.get("config") is not None:
        try:
            config = BuildConfig(**payload["config"])
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from None
    try:
        return update_build(
            build_id,
            name=payload.get("name"),
            description=payload.get("description"),
            config=config,
        )
    except BuildNotFound:
        raise HTTPException(status_code=404, detail="Build not found") from None
    except BuildLocked:
        raise HTTPException(
            status_code=409,
            detail="Build config is locked after a run — create a new build to change it",
        ) from None
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None


@router.delete("/builds/{build_id}")
async def delete_build_endpoint(build_id: str):
    try:
        deleted = delete_build(build_id)
    except BuildNotFound:
        raise HTTPException(status_code=404, detail="Build not found") from None
    except RuntimeError:
        raise HTTPException(status_code=500, detail="Failed to delete build") from None
    return {"deleted": True, "id": build_id, "objects": deleted}


@router.post("/builds/{build_id}/run", response_model=BuildJob)
async def run_build_endpoint(build_id: str, background_tasks: BackgroundTasks):
    try:
        b = get_build(build_id)
    except BuildNotFound:
        raise HTTPException(status_code=404, detail="Build not found") from None

    existing = jobs.active_job_for(build_id)
    if existing is not None:
        return existing

    b = mark_running(build_id)
    job = jobs.create_job(build_id)
    background_tasks.add_task(run_job, job.id, b)
    logger.info("Enqueued build job=%s build=%s", job.id, build_id)
    return job


@router.get("/builds/{build_id}/clips/{clip_id}/preview")
async def clip_preview_endpoint(build_id: str, clip_id: str):
    """Presigned URL for in-browser playback of a labeled clip."""
    try:
        b = get_build(build_id)
    except BuildNotFound:
        raise HTTPException(status_code=404, detail="Build not found") from None
    clip = next((c for c in b.clips if c.clip_id == clip_id), None)
    if clip is None:
        raise HTTPException(status_code=404, detail="Clip not found")
    try:
        return {"url": get_preview_url(clip.clip_key)}
    except FileKeyError as e:
        raise HTTPException(status_code=400, detail=e.detail) from None
