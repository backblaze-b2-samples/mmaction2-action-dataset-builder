<!-- last_verified: 2026-06-30 -->
# Feature: Packaging

## Purpose
Assemble the labeled clips into a versioned, training-ready dataset release: per-split annotation CSVs, a manifest, and a dataset metadata JSON.

## Used By
- API: runs inside `POST /builds/{id}/run`
- Job: background pipeline (`services/api/app/service/pipeline.py::_package`)

## Core Functions
- `services/api/app/service/pipeline.py` — `_assign_split()`, `_write_split_annotations()`, `_package()`, `_stats()`
- `services/api/app/repo/b2_client.py` — `put_json` / `put_bytes`

## Canonical Files
- Orchestration: `services/api/app/service/pipeline.py`

## Inputs
- The kept `LabeledClip[]` and roll-up `BuildStats` from the labeling stage
- `split_preset` (`70/15/15` default, `80/10/10`, `60/20/20`) and `version_tag` from the build config

## Outputs
- Per-split annotation CSVs: `builds/<id>/dataset/annotations/{train,val,test}.csv`
- A versioned release under `builds/<id>/dataset/releases/<version>/`:
  - `train.csv`, `val.csv`, `test.csv`
  - `metadata.json` (version, source_key, recognizer_model, label_space `kinetics-400`, confidence_threshold, split_preset, clip_count, class + split distribution, created_at)
  - `manifest.json` (version, clips[], annotation keys, metadata key)
- `Release` recorded on the build manifest (`build.json`)

## Flow
- Clips are assigned to train/val/test deterministically by position (`_assign_split`), so the split is stable and reproducible without a database
- Per-split CSVs are written under `dataset/annotations/`
- A release directory is written with the same CSVs plus manifest + metadata JSON
- Build stats (segments, clips, dropped, class/split distribution, avg confidence) are computed and stored on `build.json`

## Edge Cases
- Zero kept clips → empty CSVs + release with `clip_count: 0`
- Re-running / multiple releases → a new `version_tag` (or auto `v{n}`) keeps prior releases intact
- A class with a single clip → still placed deterministically into one split

## UX States
- Surfaced via the build job status `packaging` and the releases list on the build detail page

## Verification
- Test files: `services/api/tests/` (pipeline/packaging coverage)
- Required cases: split ratios honored, manifest/metadata keys present, empty-dataset release
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green

## Related Docs
- [Labeling](labeling-mmaction2.md) · [Dataset Explorer](dataset-explorer.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
