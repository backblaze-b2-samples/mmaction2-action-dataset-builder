"""Build CRUD + pipeline tests. The MMAction2 engine, ffmpeg, and B2 are all
monkeypatched, so this runs with no GPU, no ML stack, and no live bucket."""

import pytest

from app.service import builds as builds_service
from app.service import pipeline as pipeline_service
from app.types import Build, BuildConfig


@pytest.fixture
def fake_b2(monkeypatch):
    store: dict[str, dict] = {}
    blobs: dict[str, bytes] = {}

    def put_json(key, obj):
        store[key] = obj

    def get_json(key):
        return store.get(key)

    def put_bytes(key, data, ctype):
        blobs[key] = data

    def list_keys(prefix="", max_keys=1000):
        return [k for k in store if k.startswith(prefix)]

    # Patch the names imported into each service module.
    for mod in (builds_service, pipeline_service):
        monkeypatch.setattr(mod, "put_json", put_json, raising=False)
        monkeypatch.setattr(mod, "get_json", get_json, raising=False)
    monkeypatch.setattr(builds_service, "list_keys", list_keys)
    monkeypatch.setattr(pipeline_service, "put_bytes", put_bytes)
    # validate_key is a real, pure function — keep it.
    return store, blobs


def _cfg(source="raw/match.mp4"):
    return BuildConfig(source_key=source, max_clips=3, confidence_threshold=0.1)


def test_create_and_get_build(fake_b2):
    b = builds_service.create_build("Broadcast v1", "desc", _cfg())
    assert b.status == "draft"
    fetched = builds_service.get_build(b.id)
    assert fetched.name == "Broadcast v1"
    assert fetched.config.source_key == "raw/match.mp4"


def test_update_locked_after_run(fake_b2):
    b = builds_service.create_build("b", "", _cfg())
    # Simulate a completed run by flipping status in the manifest.
    store, _ = fake_b2
    store[builds_service.manifest_key(b.id)]["status"] = "complete"
    with pytest.raises(builds_service.BuildLocked):
        builds_service.update_build(b.id, config=_cfg("raw/other.mp4"))
    # Rename is still allowed after a run.
    renamed = builds_service.update_build(b.id, name="renamed")
    assert renamed.name == "renamed"


def test_pipeline_labels_and_packages(fake_b2, monkeypatch):
    """End-to-end pipeline with mocked engine: 3 segments -> labeled clips."""
    store, blobs = fake_b2
    b = builds_service.create_build("run me", "", _cfg())

    # Mock the repo engine: segmentation yields 3 intervals; trim returns bytes;
    # MMAction2 labels alternate between two Kinetics classes with high conf.
    monkeypatch.setattr(pipeline_service, "get_object_bytes", lambda key: b"video-bytes")

    class FakeVideoTools:
        @staticmethod
        def segment_video(path, **kw):
            return [(0.0, 5.0), (5.0, 10.0), (10.0, 15.0)]

        @staticmethod
        def trim_clip(path, start, end):
            return b"clip-bytes"

    class FakeEngine:
        @staticmethod
        def label_clip(path, model):
            return ("yoga", 0.91)

    monkeypatch.setattr(pipeline_service, "video_tools", FakeVideoTools)
    monkeypatch.setattr(pipeline_service, "mmaction_engine", FakeEngine)

    updated = pipeline_service.run_build(builds_service.get_build(b.id))

    assert updated.status == "complete"
    assert updated.stats.clips_total == 3
    assert updated.stats.class_distribution == {"yoga": 3}
    assert len(updated.releases) == 1
    # Clips were written under the build's class-scoped prefix.
    assert any("/dataset/clips/yoga/" in k for k in blobs)
    # Split CSVs + release artifacts were written.
    assert any("/dataset/annotations/train.csv" in k for k in blobs)
    assert any("/dataset/releases/v1/metadata.json" in k for k in store)


def test_pipeline_drops_low_confidence(fake_b2, monkeypatch):
    b = builds_service.create_build("low", "", _cfg())
    monkeypatch.setattr(pipeline_service, "get_object_bytes", lambda key: b"v")

    class FakeVideoTools:
        @staticmethod
        def segment_video(path, **kw):
            return [(0.0, 5.0)]

        @staticmethod
        def trim_clip(path, start, end):
            return b"clip"

    class FakeEngine:
        @staticmethod
        def label_clip(path, model):
            return ("yoga", 0.05)  # below the 0.1 threshold

    monkeypatch.setattr(pipeline_service, "video_tools", FakeVideoTools)
    monkeypatch.setattr(pipeline_service, "mmaction_engine", FakeEngine)

    updated = pipeline_service.run_build(builds_service.get_build(b.id))
    assert updated.stats.clips_total == 0
    assert updated.stats.clips_dropped == 1


def test_class_groups(fake_b2, monkeypatch):
    b = builds_service.create_build("g", "", _cfg())
    store, _ = fake_b2
    # Inject clips directly into the manifest.
    manifest = store[builds_service.manifest_key(b.id)]
    manifest["clips"] = [
        {
            "clip_id": "a",
            "action": "yoga",
            "confidence": 0.9,
            "split": "train",
            "start": 0,
            "end": 5,
            "duration": 5,
            "clip_key": "builds/x/dataset/clips/yoga/a.mp4",
        },
        {
            "clip_id": "b",
            "action": "running on treadmill",
            "confidence": 0.8,
            "split": "val",
            "start": 5,
            "end": 10,
            "duration": 5,
            "clip_key": "builds/x/dataset/clips/running_on_treadmill/b.mp4",
        },
    ]
    groups = builds_service.class_groups(b.id)
    assert {g.action for g in groups} == {"yoga", "running on treadmill"}


def test_build_round_trips_through_model():
    """The Build model survives a JSON round-trip (manifest fidelity)."""
    b = Build(
        id="x",
        name="n",
        config=_cfg(),
        created_at="2026-06-30T00:00:00Z",
        updated_at="2026-06-30T00:00:00Z",
    )
    again = Build(**b.model_dump())
    assert again.config.split_preset == "70/15/15"
