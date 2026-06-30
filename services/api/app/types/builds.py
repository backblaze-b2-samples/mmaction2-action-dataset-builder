"""Pydantic models for the MMAction2 action-dataset builder.

Pure data — no logic, no imports from other app layers (types is the bottom
layer). These are the contract shared with the frontend via
packages/shared/src/types.ts.
"""

from typing import Literal

from pydantic import BaseModel

# Build-job lifecycle, surfaced live in the UI via service/pipeline.py.
JobStatus = Literal[
    "queued",
    "segmenting",
    "clipping",
    "labeling",
    "packaging",
    "complete",
    "failed",
]

BuildStatus = Literal["draft", "running", "complete", "failed"]
SegmentStrategy = Literal["fixed-stride", "scene-detect"]
SplitPreset = Literal["70/15/15", "80/10/10", "60/20/20"]
Split = Literal["train", "val", "test"]


class BuildConfig(BaseModel):
    """The build configuration for one dataset build (editable while draft)."""

    # The raw source video this build is built from (a raw/ object key).
    source_key: str
    # Candidate-interval strategy.
    strategy: SegmentStrategy = "fixed-stride"
    window_seconds: float = 5.0
    stride_seconds: float = 5.0
    # MMAction2 recognizer id (see repo/mmaction_engine._MODELS).
    recognizer_model: str = "tsn-r50-kinetics400"
    # Clips below this top-1 confidence are dropped (not labeled into the set).
    confidence_threshold: float = 0.30
    split_preset: SplitPreset = "70/15/15"
    version_tag: str = "v1"
    # Caps a CPU demo at a manageable number of candidate clips.
    max_clips: int = 60


class Segment(BaseModel):
    """One candidate action interval (seconds) before labeling."""

    index: int
    start: float
    end: float


class LabeledClip(BaseModel):
    """One trimmed clip with its MMAction2 action label + confidence."""

    clip_id: str
    action: str
    confidence: float
    split: Split
    start: float
    end: float
    duration: float
    # B2 key under builds/<id>/dataset/clips/<class>/<clip_id>.mp4
    clip_key: str


class BuildStats(BaseModel):
    """Roll-up stats for a completed build (stored in build.json)."""

    segments_total: int = 0
    clips_total: int = 0
    clips_dropped: int = 0
    classes_seen: list[str] = []
    # label -> count, for the per-class distribution panel.
    class_distribution: dict[str, int] = {}
    # train/val/test -> count.
    split_distribution: dict[str, int] = {}
    avg_confidence: float = 0.0


class Release(BaseModel):
    """A versioned dataset release written under the build's release prefix."""

    version: str
    manifest_key: str
    metadata_key: str
    annotation_keys: list[str] = []
    clip_count: int = 0
    created_at: str


class Build(BaseModel):
    """Primary entity. The manifest persisted at builds/<id>/build.json."""

    id: str
    name: str
    description: str = ""
    status: BuildStatus = "draft"
    config: BuildConfig
    stats: BuildStats = BuildStats()
    clips: list[LabeledClip] = []
    releases: list[Release] = []
    error: str | None = None
    created_at: str
    updated_at: str


class BuildSummary(BaseModel):
    """Lightweight build row for the list view (no per-clip detail)."""

    id: str
    name: str
    description: str = ""
    status: BuildStatus
    source_key: str
    recognizer_model: str
    clips_total: int = 0
    classes_total: int = 0
    release_count: int = 0
    created_at: str
    updated_at: str


class BuildJob(BaseModel):
    """Live, process-local build progress. Ephemeral — see service/pipeline.py."""

    id: str
    build_id: str
    status: JobStatus
    progress: float = 0.0
    message: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class BuilderStatsSummary(BaseModel):
    """Dashboard metrics derived from B2 listings + manifests."""

    footage_ingested: int
    builds_total: int
    builds_complete: int
    total_clips: int
    total_classes: int
    storage_used_human: str


class SourceVideo(BaseModel):
    """An uploaded raw video selectable in the build form."""

    key: str
    filename: str
    size_bytes: int
    size_human: str
    uploaded_at: str


class ClassGroup(BaseModel):
    """A Kinetics-400 action class and its clips, for the /dataset explorer."""

    action: str
    count: int
    clips: list[LabeledClip] = []
