"""MMAction2 recognizer adapter (repo layer).

This is the ONLY module that imports `mmaction` / `torch`, mirroring the
"external SDK lives only in repo/" invariant that also confines `boto3`. The
recognizer is lazy-loaded on first use so server start stays fast, `/health`
never pulls weights, and the API + tests boot WITHOUT requirements-ml.txt.

The labeling step runs the REAL MMAction2 engine — `init_recognizer` +
`inference_recognizer` from `mmaction.apis` — against the Kinetics-400
checkpoints. No simulation, no synthetic labels. Weights download from the
public OpenMMLab model zoo on first use; no API key beyond B2 credentials.

Outputs are plain Python (label string + float score) so every higher layer
(service, runtime) stays free of torch/mmaction.

Device selection auto-detects CUDA -> Apple MPS -> CPU and DEFAULTS TO CPU
(`deployment: local`). mmcv's MPS support is weak, so on Apple Silicon this
deliberately collapses to CUDA -> CPU (MPS is mapped to CPU below); a CPU run
is always a valid fallback and a GPU is never hard-required.
"""

import logging
import math
import os
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

# Bundled fallback Kinetics-400 label list (used only if a loaded model does
# not carry its own classes in dataset_meta). One label per line, index-aligned.
_LABELS_FILE = Path(__file__).resolve().parent / "kinetics_400_labels.txt"

# Registry of supported recognizers -> the bundled MMAction2 config (resolved
# from the installed package's .mim/configs tree) + the public Kinetics-400
# checkpoint URL. Both are TSN/TSM R50 trained on Kinetics-400, CPU-friendly.
_MODELS: dict[str, dict[str, str]] = {
    "tsn-r50-kinetics400": {
        "config": "configs/recognition/tsn/"
        "tsn_imagenet-pretrained-r50_8xb32-1x1x3-100e_kinetics400-rgb.py",
        "checkpoint": (
            "https://download.openmmlab.com/mmaction/v1.0/recognition/tsn/"
            "tsn_imagenet-pretrained-r50_8xb32-1x1x3-100e_kinetics400-rgb/"
            "tsn_imagenet-pretrained-r50_8xb32-1x1x3-100e_kinetics400-rgb_20220906-cd10898e.pth"
        ),
    },
    "tsm-r50-kinetics400": {
        "config": "configs/recognition/tsm/"
        "tsm_imagenet-pretrained-r50_8xb16-1x1x8-50e_kinetics400-rgb.py",
        "checkpoint": (
            "https://download.openmmlab.com/mmaction/v1.0/recognition/tsm/"
            "tsm_imagenet-pretrained-r50_8xb16-1x1x8-50e_kinetics400-rgb/"
            "tsm_imagenet-pretrained-r50_8xb16-1x1x8-50e_kinetics400-rgb_20220831-64d69186.pth"
        ),
    },
}

DEFAULT_MODEL = "tsn-r50-kinetics400"


class MissingMLDependencies(RuntimeError):
    """Raised when the MMAction2 stack (requirements-ml.txt) is absent."""


def available_models() -> list[str]:
    """The recognizer ids the engine can load (selector source for the UI)."""
    return list(_MODELS)


def select_device(override: str = "auto") -> str:
    """Auto-detect the inference device. Honors a non-auto override.

    Defaults to CPU and never hard-requires a GPU. Order: CUDA -> MPS -> CPU.
    mmcv MPS support is weak, so a detected/forced "mps" is mapped to "cpu"
    here (the recognizer pipelines use mmcv ops that lack MPS kernels). With
    torch absent, reports "cpu".
    """
    if override and override != "auto":
        return "cpu" if override == "mps" else override
    try:
        import torch  # type: ignore
    except ImportError:
        return "cpu"
    if torch.cuda.is_available():
        return "cuda"
    # MPS is detected but intentionally mapped to CPU for mmcv compatibility.
    mps = getattr(torch.backends, "mps", None)
    if mps is not None and mps.is_available():
        logger.info("Apple MPS detected but mmcv lacks MPS kernels; using CPU")
        return "cpu"
    return "cpu"


def _resolve_config(rel_config: str) -> str:
    """Resolve a bundled MMAction2 config path inside the installed package.

    MMAction2 ships its `configs/` tree under `mmaction/.mim/` for pip
    installs. We locate the installed package and join the relative path.
    """
    try:
        import mmaction  # type: ignore
    except ImportError as e:  # pragma: no cover - only without ML deps
        raise MissingMLDependencies(
            "mmaction2 is not installed. Install the ML stack: "
            "`pip install -r requirements-ml.txt` (see README for the mim/mmcv caveat)."
        ) from e
    pkg_dir = Path(mmaction.__file__).resolve().parent
    candidates = [
        pkg_dir / ".mim" / rel_config,
        pkg_dir.parent / rel_config,
        pkg_dir / rel_config,
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    # Last resort: hand the relative path to init_recognizer, which searches
    # mmengine's registered config scopes.
    return rel_config


@lru_cache(maxsize=2)
def _load_recognizer(model_id: str):
    """Build (and cache) an MMAction2 recognizer. Heavy: loads weights."""
    try:
        from mmaction.apis import init_recognizer
    except ImportError as e:  # pragma: no cover - only without ML deps
        raise MissingMLDependencies(
            "mmaction2 is not installed. Install the ML stack: "
            "`pip install -r requirements-ml.txt` (see README for the mim/mmcv caveat)."
        ) from e

    spec = _MODELS.get(model_id) or _MODELS[DEFAULT_MODEL]
    device = select_device()
    config = _resolve_config(spec["config"])
    logger.info("Loading MMAction2 recognizer %s on %s", model_id, device)
    return init_recognizer(config, spec["checkpoint"], device=device)


@lru_cache(maxsize=1)
def _fallback_labels() -> list[str]:
    if _LABELS_FILE.exists():
        return [
            line.strip()
            for line in _LABELS_FILE.read_text().splitlines()
            if line.strip()
        ]
    return []


def _classes_for(model) -> list[str]:
    """Kinetics-400 class names — from the model's dataset_meta, else bundled."""
    meta = getattr(model, "dataset_meta", None) or {}
    classes = meta.get("classes")
    if classes:
        return list(classes)
    return _fallback_labels()


def _as_score_list(scores) -> list[float]:
    """Flatten a torch/numpy score tensor (or sequence) to a 1-D float list."""
    if hasattr(scores, "tolist"):
        scores = scores.tolist()
    # pred_score is 1-D in mmaction 1.x; defensively flatten a [1, N] shape.
    if scores and isinstance(scores[0], (list, tuple)):
        scores = scores[0]
    return [float(s) for s in scores]


def _confidence_from_scores(scores: list[float]) -> tuple[int, float]:
    """Top class index + its probability from a per-class score vector.

    Our TSN/TSM heads are configured with `average_clips='prob'`, so
    `inference_recognizer` already returns a softmax distribution in
    `pred_score`. Re-softmaxing it (the historical bug) flattened every
    distribution toward uniform (~1/num_classes ~= 0.0025 for Kinetics-400),
    making `confidence` meaningless and forcing operators to disable the
    confidence gate. So we softmax ONLY when the vector is not already a
    normalized, non-negative distribution (e.g. a model emitting raw logits).
    """
    if not scores:
        return 0, 0.0
    already_distribution = all(s >= 0 for s in scores) and math.isclose(
        sum(scores), 1.0, abs_tol=1e-3
    )
    if not already_distribution:
        peak = max(scores)
        exps = [math.exp(s - peak) for s in scores]
        denom = sum(exps)
        scores = [e / denom for e in exps]
    top = max(range(len(scores)), key=scores.__getitem__)
    return top, float(scores[top])


def label_clip(clip_path: str, model_id: str = DEFAULT_MODEL) -> tuple[str, float]:
    """Run REAL MMAction2 inference on one clip -> (action_label, confidence).

    Loads the recognizer (cached) and runs `inference_recognizer`. The returned
    ActionDataSample carries per-class scores in `pred_score`, which is already
    a softmax distribution (`average_clips='prob'`); we take the top class and
    its probability via `_confidence_from_scores` (no re-softmax). Raises
    MissingMLDependencies if the stack is absent.
    """
    try:
        from mmaction.apis import inference_recognizer
    except ImportError as e:  # pragma: no cover - only without ML deps
        raise MissingMLDependencies(
            "mmaction2 is not installed. Install the ML stack: "
            "`pip install -r requirements-ml.txt`."
        ) from e

    if not os.path.exists(clip_path):
        raise RuntimeError(f"Clip not found for inference: {clip_path}")

    model = _load_recognizer(model_id)
    result = inference_recognizer(model, clip_path)

    # MMAction2 1.x: result.pred_score is a Tensor of per-class probabilities
    # (the head averages clips as 'prob', i.e. it is already softmaxed).
    scores = getattr(result, "pred_score", None)
    if scores is None:
        # Older API surface fallback.
        scores = result.pred_scores.item  # type: ignore[attr-defined]

    top, confidence = _confidence_from_scores(_as_score_list(scores))
    classes = _classes_for(model)
    label = classes[top] if top < len(classes) else f"class_{top}"
    return label, confidence
