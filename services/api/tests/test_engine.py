"""Engine signature-guard tests that run WITHOUT the heavy ML stack installed.

These guard the lazy-import contract: importing the engine modules and the
pipeline service must not pull in mmaction/torch/scenedetect/cv2 as a side
effect, and the device autodetect must default to CPU (never hard-require a
GPU). They run with no model download and no live bucket.
"""

import sys


def test_engine_imports_without_ml_stack():
    """Importing the engine + pipeline must not import heavy ML modules."""
    import app.repo.mmaction_engine
    import app.repo.video_tools  # noqa: F401
    from app.service import pipeline  # noqa: F401

    for heavy in ("torch", "mmaction", "mmcv", "scenedetect", "cv2", "decord"):
        assert heavy not in sys.modules, f"{heavy} was eagerly imported"


def test_engine_exposes_public_functions():
    """The engine module exposes its public surface without the ML stack."""
    from app.repo import mmaction_engine, video_tools

    assert callable(mmaction_engine.label_clip)
    assert callable(mmaction_engine.select_device)
    assert callable(mmaction_engine.available_models)
    assert callable(video_tools.segment_video)
    assert callable(video_tools.trim_clip)


def test_available_models_are_known():
    from app.repo import mmaction_engine

    models = mmaction_engine.available_models()
    assert "tsn-r50-kinetics400" in models
    assert "tsm-r50-kinetics400" in models


def test_device_defaults_to_cpu_without_torch():
    """With torch absent, the device helper reports CPU (never requires a GPU)."""
    from app.repo.mmaction_engine import select_device

    assert select_device("auto") == "cpu"


def test_device_honors_explicit_override_and_maps_mps_to_cpu():
    """A forced device is honored; mps collapses to cpu for mmcv compatibility."""
    from app.repo.mmaction_engine import select_device

    assert select_device("cuda") == "cuda"
    assert select_device("cpu") == "cpu"
    # mmcv lacks MPS kernels, so an mps request maps to cpu.
    assert select_device("mps") == "cpu"


def test_fallback_labels_are_kinetics_400():
    """The bundled label fallback has exactly 400 Kinetics classes."""
    from app.repo import mmaction_engine

    labels = mmaction_engine._fallback_labels()
    assert len(labels) == 400
    assert "yoga" in labels


def test_confidence_preserves_prob_distribution():
    """Regression: pred_score is already softmaxed (average_clips='prob').

    The engine must NOT re-softmax it. A second softmax flattens a peaked
    distribution toward uniform (~1/num_classes), which is what made every
    real confidence collapse to ~0.004 and forced the gate to be disabled.
    """
    from app.repo.mmaction_engine import _confidence_from_scores

    probs = [0.02, 0.90, 0.03, 0.05]  # already a valid distribution (sums to 1)
    top, conf = _confidence_from_scores(probs)
    assert top == 1
    assert conf == 0.90  # preserved, NOT collapsed toward 0.25


def test_confidence_softmaxes_raw_logits():
    """Non-normalized scores (raw logits) are softmaxed into a distribution."""
    from app.repo.mmaction_engine import _confidence_from_scores

    top, conf = _confidence_from_scores([1.0, 5.0, 1.0, 1.0])
    assert top == 1
    assert 0.8 < conf < 1.0  # the peak dominates after softmax


def test_as_score_list_flattens_tensor_shapes():
    """A [1, N] batch shape is flattened to a 1-D float list."""
    from app.repo.mmaction_engine import _as_score_list

    assert _as_score_list([0.1, 0.9]) == [0.1, 0.9]
    assert _as_score_list([[0.1, 0.9]]) == [0.1, 0.9]  # [1, N] -> [N]


def test_stride_windows_are_capped_and_clamped():
    """Pure segmentation math runs without ffmpeg (no media decode here)."""
    from app.repo.video_tools import _stride_windows

    windows = _stride_windows(duration=30.0, window=5.0, stride=5.0, max_clips=4)
    assert len(windows) == 4  # capped at max_clips
    assert windows[0] == (0.0, 5.0)
    assert all(end <= 30.0 for _, end in windows)
