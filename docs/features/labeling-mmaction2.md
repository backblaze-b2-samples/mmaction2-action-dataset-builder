<!-- last_verified: 2026-06-30 -->
# Feature: Labeling (MMAction2)

## Purpose
Assign a Kinetics-400 action label + confidence to every trimmed clip using **real MMAction2 recognizer inference**, run locally. This is the marquee feature — the OSS engine the sample is built around.

## Used By
- API: runs inside `POST /builds/{id}/run`
- Job: background pipeline (`services/api/app/service/pipeline.py::_clip_and_label`)

## Core Functions
- `services/api/app/repo/mmaction_engine.py` — `label_clip(clip_path, recognizer_model)` and device autodetect, using `mmaction.apis.init_recognizer` + `inference_recognizer`
- `services/api/app/repo/kinetics_400_labels.txt` — the 400-class label space
- `services/api/app/service/pipeline.py` — routes kept clips to `dataset/clips/<class>/` and writes annotation CSVs

## Canonical Files
- Engine (real MMAction2 calls, lazy heavy imports): `services/api/app/repo/mmaction_engine.py`

## Inputs
- Path to a trimmed clip (MP4)
- `recognizer_model`: `tsn-r50-kinetics400` (default, fast/CPU-friendly) or `tsm-r50-kinetics400`
- `confidence_threshold` (default 0.30) from the build config

## Outputs
- `(action: str, confidence: float)` per clip
- Side effects: kept clips uploaded under `dataset/clips/<class>/`; rows written to `dataset/annotations/<split>.csv` (`clip_key,action,confidence,start,end`)

## Flow
- The recognizer is initialized for the selected model (checkpoint fetched/cached on first use)
- `inference_recognizer` runs on the clip; the top-1 Kinetics-400 label + score is returned
- Clips scoring below `confidence_threshold` are **dropped** (not added to the dataset)
- Kept clips are assigned a train/val/test split (see [Packaging](packaging.md)) and uploaded by class

## Device selection
- **CPU by default**, auto-detecting the first available of **CUDA → Apple MPS → CPU** at runtime
- `mmcv`'s MPS op coverage is partial, so on Apple Silicon labeling effectively runs on CPU — keep `max_clips` modest for a responsive demo
- Never hard-requires a GPU

## Edge Cases
- ML stack not installed → import error surfaces with guidance to `pip install -r requirements-ml.txt` (the base API still boots because heavy imports are lazy)
- Clip too short to decode the model's required frames → handled/skipped by the engine
- All clips below threshold → build completes with zero kept clips (empty dataset)

## Verification
- Structural test: `services/api/tests/test_structure.py::test_ml_sdks_only_in_repo` (mmaction/torch confined to `repo/`)
- Signature guard: the engine's public surface is importable without the heavy stack
- End-to-end model inference is exercised by the pipeline verify step (a real model run on a real clip)
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: structural + signature tests green; a real build labels clips with non-trivial confidences

## Related Docs
- [Clipping](clipping.md) · [Packaging](packaging.md)
- [MMAction2](https://github.com/open-mmlab/mmaction2)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
