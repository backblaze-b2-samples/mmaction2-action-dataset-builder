"""Action-dataset build CRUD + dashboard aggregations + the /dataset explorer.

The build registry is the builds/ prefix on B2: each build is a
builds/<id>/build.json manifest. There is no application DB — the manifest is
authoritative. Dashboard stats roll up the same manifests + bucket listings.

No boto3 — everything goes through the repo. ML compute lives in the engine
(repo/) + pipeline module, not here.
"""

import logging
import uuid
from datetime import UTC, datetime

from app.config import settings
from app.repo import (
    delete_prefix,
    get_json,
    get_object_stats,
    list_files,
    list_keys,
    put_json,
)
from app.service.files import validate_key
from app.types import (
    Build,
    BuildConfig,
    BuilderStatsSummary,
    BuildSummary,
    ClassGroup,
    SourceVideo,
)
from app.types.formatting import humanize_bytes

logger = logging.getLogger(__name__)


class BuildNotFound(Exception):
    """Raised when a build id has no manifest."""


class BuildLocked(Exception):
    """Raised when editing build config on a non-draft build."""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def build_prefix(build_id: str) -> str:
    return f"{settings.builds_prefix}{build_id}/"


def manifest_key(build_id: str) -> str:
    return f"{build_prefix(build_id)}build.json"


def list_sources() -> list[SourceVideo]:
    """List uploaded raw videos selectable in the build form."""
    out: list[SourceVideo] = []
    for f in list_files(prefix=settings.raw_prefix, max_keys=1000):
        if f.key.endswith("/"):
            continue
        out.append(
            SourceVideo(
                key=f.key,
                filename=f.filename,
                size_bytes=f.size_bytes,
                size_human=f.size_human,
                uploaded_at=f.uploaded_at.isoformat(),
            )
        )
    return out


def _manifest_ids() -> list[str]:
    """Return every build id that has a manifest in B2."""
    keys = list_keys(prefix=settings.builds_prefix, max_keys=1000)
    ids: list[str] = []
    for k in keys:
        if k.endswith("/build.json"):
            ids.append(k[len(settings.builds_prefix):].split("/", 1)[0])
    return ids


def list_builds() -> list[BuildSummary]:
    """List all builds as lightweight summaries (newest first)."""
    summaries: list[BuildSummary] = []
    for build_id in _manifest_ids():
        obj = get_json(manifest_key(build_id))
        if not obj:
            continue
        b = Build(**obj)
        summaries.append(
            BuildSummary(
                id=b.id,
                name=b.name,
                description=b.description,
                status=b.status,
                source_key=b.config.source_key,
                recognizer_model=b.config.recognizer_model,
                clips_total=b.stats.clips_total,
                classes_total=len(b.stats.classes_seen),
                release_count=len(b.releases),
                created_at=b.created_at,
                updated_at=b.updated_at,
            )
        )
    summaries.sort(key=lambda s: s.created_at, reverse=True)
    return summaries


def get_build(build_id: str) -> Build:
    """Fetch a build manifest. Raises BuildNotFound if absent."""
    obj = get_json(manifest_key(build_id))
    if obj is None:
        raise BuildNotFound(build_id)
    return Build(**obj)


def create_build(name: str, description: str, config: BuildConfig) -> Build:
    """Create a new draft build manifest in B2."""
    validate_key(config.source_key)
    now = _now()
    b = Build(
        id=uuid.uuid4().hex[:12],
        name=name.strip() or "Untitled build",
        description=description.strip(),
        status="draft",
        config=config,
        created_at=now,
        updated_at=now,
    )
    put_json(manifest_key(b.id), b.model_dump())
    logger.info("Created build id=%s source=%s", b.id, config.source_key)
    return b


def update_build(
    build_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    config: BuildConfig | None = None,
) -> Build:
    """Rename / redescribe a build; edit build config only while draft."""
    b = get_build(build_id)
    updates: dict = {"updated_at": _now()}
    if name is not None:
        updates["name"] = name.strip() or b.name
    if description is not None:
        updates["description"] = description.strip()
    if config is not None:
        if b.status != "draft":
            raise BuildLocked(build_id)
        validate_key(config.source_key)
        updates["config"] = config
    updated = b.model_copy(update=updates)
    put_json(manifest_key(build_id), updated.model_dump())
    return updated


def delete_build(build_id: str) -> int:
    """Delete a build's manifest + all artifacts, SCOPED to its own prefix."""
    get_build(build_id)  # raises BuildNotFound -> clean 404
    deleted = delete_prefix(build_prefix(build_id))
    logger.info("Deleted build id=%s objects=%d", build_id, deleted)
    return deleted


def mark_running(build_id: str) -> Build:
    """Flip a build to 'running' before a run (so the UI reflects it)."""
    b = get_build(build_id)
    updated = b.model_copy(update={"status": "running", "updated_at": _now()})
    put_json(manifest_key(build_id), updated.model_dump())
    return updated


def class_groups(build_id: str) -> list[ClassGroup]:
    """Group a build's labeled clips by action class for the /dataset explorer."""
    b = get_build(build_id)
    groups: dict[str, list] = {}
    for clip in b.clips:
        groups.setdefault(clip.action, []).append(clip)
    out = [
        ClassGroup(action=action, count=len(clips), clips=clips)
        for action, clips in groups.items()
    ]
    out.sort(key=lambda g: g.count, reverse=True)
    return out


def get_dashboard_stats() -> BuilderStatsSummary:
    """Roll up builder metrics for the dashboard."""
    footage = [
        f
        for f in list_files(prefix=settings.raw_prefix, max_keys=1000)
        if not f.key.endswith("/")
    ]
    builds = list_builds()
    complete = [b for b in builds if b.status == "complete"]
    total_clips = sum(b.clips_total for b in complete)
    classes: set[str] = set()
    for build_id in (b.id for b in complete):
        obj = get_json(manifest_key(build_id))
        if obj:
            classes.update(Build(**obj).stats.classes_seen)
    used = get_object_stats(prefix=settings.builds_prefix)
    return BuilderStatsSummary(
        footage_ingested=len(footage),
        builds_total=len(builds),
        builds_complete=len(complete),
        total_clips=total_clips,
        total_classes=len(classes),
        storage_used_human=humanize_bytes(used["total_size_bytes"]),
    )
