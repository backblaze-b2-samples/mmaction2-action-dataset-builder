"""Action-dataset build pipeline: raw video -> labeled action-recognition set.

Flow (the B2 write-amplification story — 1 source video -> N labeled clips):

    raw/<video>  --download-->  segment into candidate intervals -->
        trim each interval to a short H.264 clip (imageio-ffmpeg) -->
        REAL MMAction2 recognizer inference -> Kinetics-400 label + confidence -->
    write  builds/<id>/segments.json
           builds/<id>/dataset/clips/<class>/<clip_id>.mp4
           builds/<id>/dataset/annotations/<split>.csv
           builds/<id>/dataset/releases/<version>/{manifest.json,metadata.json,*.csv}
           builds/<id>/build.json  (manifest + stats)

This module owns NO boto3 — it calls the repo for all B2 I/O and the engine
(repo/mmaction_engine, repo/video_tools) for all local compute, whose heavy
imports stay lazy so importing this module is cheap. Builds run in a background
thread; progress is reported via the ephemeral jobs registry.
"""

import csv
import io
import logging
import os
import tempfile
import uuid
from datetime import UTC, datetime

from app.repo import get_object_bytes, mmaction_engine, put_bytes, put_json, video_tools
from app.service import jobs
from app.service.builds import build_prefix, manifest_key
from app.types import Build, BuildStats, LabeledClip, Release, Segment

logger = logging.getLogger(__name__)

# Split-preset label -> (train, val, test) fractions.
_SPLITS: dict[str, tuple[float, float, float]] = {
    "70/15/15": (0.70, 0.15, 0.15),
    "80/10/10": (0.80, 0.10, 0.10),
    "60/20/20": (0.60, 0.20, 0.20),
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_class(action: str) -> str:
    """Filesystem/key-safe class folder name for a Kinetics-400 label."""
    return "".join(c if c.isalnum() else "_" for c in action.lower()).strip("_") or "unknown"


def _assign_split(index: int, total: int, preset: str) -> str:
    """Deterministic train/val/test assignment by position (stable, no DB)."""
    train_f, val_f, _ = _SPLITS.get(preset, _SPLITS["70/15/15"])
    pos = (index + 0.5) / max(1, total)
    if pos < train_f:
        return "train"
    if pos < train_f + val_f:
        return "val"
    return "test"


def _clip_key(build_id: str, action: str, clip_id: str) -> str:
    return f"{build_prefix(build_id)}dataset/clips/{_safe_class(action)}/{clip_id}.mp4"


def _segment(build: Build, src_path: str, progress) -> list[Segment]:
    cfg = build.config
    progress("segmenting", 0.10, f"Segmenting via {cfg.strategy}")
    intervals = video_tools.segment_video(
        src_path,
        strategy=cfg.strategy,
        window_seconds=cfg.window_seconds,
        stride_seconds=cfg.stride_seconds,
        max_clips=cfg.max_clips,
    )
    segments = [
        Segment(index=i, start=s, end=e) for i, (s, e) in enumerate(intervals)
    ]
    put_json(
        f"{build_prefix(build.id)}segments.json",
        {"count": len(segments), "segments": [s.model_dump() for s in segments]},
    )
    return segments


def _clip_and_label(
    build: Build, src_path: str, segments: list[Segment], progress
) -> list[LabeledClip]:
    """Trim each segment, run MMAction2, route the kept clips to B2 by class."""
    cfg = build.config
    kept: list[LabeledClip] = []
    total = max(1, len(segments))
    for i, seg in enumerate(segments):
        frac = i / total
        progress("clipping", 0.20 + 0.25 * frac, f"Clipping {i + 1}/{total}")
        clip_bytes = video_tools.trim_clip(src_path, seg.start, seg.end)
        if not clip_bytes:
            continue

        # The clip must exist on disk for MMAction2's video decoder.
        fd, clip_path = tempfile.mkstemp(suffix=".mp4")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(clip_bytes)
            progress(
                "labeling",
                0.45 + 0.40 * frac,
                f"Labeling {i + 1}/{total} (MMAction2)",
            )
            action, confidence = mmaction_engine.label_clip(
                clip_path, cfg.recognizer_model
            )
        finally:
            if os.path.exists(clip_path):
                os.unlink(clip_path)

        if confidence < cfg.confidence_threshold:
            continue

        clip_id = uuid.uuid4().hex[:10]
        split = _assign_split(len(kept), total, cfg.split_preset)
        key = _clip_key(build.id, action, clip_id)
        put_bytes(key, clip_bytes, "video/mp4")
        kept.append(
            LabeledClip(
                clip_id=clip_id,
                action=action,
                confidence=round(confidence, 4),
                split=split,
                start=seg.start,
                end=seg.end,
                duration=round(seg.end - seg.start, 3),
                clip_key=key,
            )
        )
    return kept


def _csv_for(clips: list[LabeledClip]) -> bytes:
    """LJSpeech-style annotation rows: clip_key,action,confidence,start,end."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["clip_key", "action", "confidence", "start", "end"])
    for c in clips:
        writer.writerow([c.clip_key, c.action, c.confidence, c.start, c.end])
    return buf.getvalue().encode("utf-8")


def _write_split_annotations(build_id: str, clips: list[LabeledClip]) -> dict[str, str]:
    """Write per-split annotation CSVs under dataset/annotations/. Returns keys."""
    keys: dict[str, str] = {}
    for split in ("train", "val", "test"):
        rows = [c for c in clips if c.split == split]
        key = f"{build_prefix(build_id)}dataset/annotations/{split}.csv"
        put_bytes(key, _csv_for(rows), "text/csv")
        keys[split] = key
    return keys


def _package(build: Build, clips: list[LabeledClip], stats: BuildStats, progress) -> Release:
    """Write a versioned release: per-split CSVs + manifest + metadata JSON."""
    progress("packaging", 0.90, "Packaging release")
    version = build.config.version_tag or f"v{len(build.releases) + 1}"
    rel_prefix = f"{build_prefix(build.id)}dataset/releases/{version}/"

    annotation_keys: list[str] = []
    for split in ("train", "val", "test"):
        rows = [c for c in clips if c.split == split]
        key = f"{rel_prefix}{split}.csv"
        put_bytes(key, _csv_for(rows), "text/csv")
        annotation_keys.append(key)

    metadata = {
        "version": version,
        "source_key": build.config.source_key,
        "recognizer_model": build.config.recognizer_model,
        "label_space": "kinetics-400",
        "confidence_threshold": build.config.confidence_threshold,
        "split_preset": build.config.split_preset,
        "clip_count": len(clips),
        "class_distribution": stats.class_distribution,
        "split_distribution": stats.split_distribution,
        "created_at": _now(),
    }
    metadata_key = f"{rel_prefix}metadata.json"
    put_json(metadata_key, metadata)

    manifest = {
        "version": version,
        "clips": [c.model_dump() for c in clips],
        "annotations": annotation_keys,
        "metadata_key": metadata_key,
    }
    manifest_k = f"{rel_prefix}manifest.json"
    put_json(manifest_k, manifest)

    return Release(
        version=version,
        manifest_key=manifest_k,
        metadata_key=metadata_key,
        annotation_keys=annotation_keys,
        clip_count=len(clips),
        created_at=metadata["created_at"],
    )


def _stats(segments: list[Segment], clips: list[LabeledClip]) -> BuildStats:
    class_dist: dict[str, int] = {}
    split_dist: dict[str, int] = {}
    for c in clips:
        class_dist[c.action] = class_dist.get(c.action, 0) + 1
        split_dist[c.split] = split_dist.get(c.split, 0) + 1
    avg_conf = round(sum(c.confidence for c in clips) / len(clips), 4) if clips else 0.0
    return BuildStats(
        segments_total=len(segments),
        clips_total=len(clips),
        clips_dropped=len(segments) - len(clips),
        classes_seen=sorted(class_dist),
        class_distribution=class_dist,
        split_distribution=split_dist,
        avg_confidence=avg_conf,
    )


def run_build(build: Build, job_id: str | None = None) -> Build:
    """Run the full segment -> clip -> label -> package pipeline for one build."""

    def progress(status, pct, message=None):
        if job_id:
            jobs.update_job(job_id, status=status, progress=pct, message=message)

    cfg = build.config
    progress("segmenting", 0.05, "Downloading raw video from B2")
    media_bytes = get_object_bytes(cfg.source_key)
    suffix = os.path.splitext(cfg.source_key)[1] or ".mp4"
    fd, src_path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(media_bytes)
        segments = _segment(build, src_path, progress)
        clips = _clip_and_label(build, src_path, segments, progress)
    finally:
        if os.path.exists(src_path):
            os.unlink(src_path)

    stats = _stats(segments, clips)
    _write_split_annotations(build.id, clips)
    release = _package(build, clips, stats, progress)

    updated = build.model_copy(
        update={
            "status": "complete",
            "stats": stats,
            "clips": clips,
            "releases": [*build.releases, release],
            "error": None,
            "updated_at": _now(),
        }
    )
    put_json(manifest_key(build.id), updated.model_dump())
    progress("complete", 1.0, f"Labeled {len(clips)} clips across {len(stats.classes_seen)} classes")
    logger.info(
        "Built dataset id=%s clips=%d classes=%d segments=%d",
        build.id,
        len(clips),
        len(stats.classes_seen),
        len(segments),
    )
    return updated


def run_job(job_id: str, build: Build) -> None:
    """Background entrypoint: run the build, recording errors on job + manifest."""
    try:
        run_build(build, job_id=job_id)
    except Exception as e:
        logger.exception("Build job failed: build=%s", build.id)
        jobs.update_job(job_id, status="failed", error=str(e))
        failed = build.model_copy(
            update={"status": "failed", "error": str(e), "updated_at": _now()}
        )
        try:
            put_json(manifest_key(build.id), failed.model_dump())
        except Exception:
            logger.exception("Failed to persist error manifest: %s", build.id)
