<!-- last_verified: 2026-06-30 -->
# Feature: Segmentation

## Purpose
Propose candidate action intervals in a raw video before clipping — the first stage of a build.

## Used By
- UI: build config (strategy + window/stride) on `/builds/new` and `/builds/[id]/edit`; surfaced as segment count on the build detail page
- API: runs inside `POST /builds/{id}/run`
- Job: background pipeline (`services/api/app/service/pipeline.py::_segment`)

## Core Functions
- `services/api/app/repo/video_tools.py` — `segment_video(path, strategy, window_seconds, stride_seconds, max_clips)`
- `services/api/app/service/pipeline.py` — `_segment()` orchestration + writes the manifest

## Canonical Files
- Engine: `services/api/app/repo/video_tools.py`
- Orchestration: `services/api/app/service/pipeline.py`

## Inputs
- Local path to the downloaded raw video
- `strategy`: `fixed-stride` (default) or `scene-detect`
- `window_seconds` (default 5), `stride_seconds` (default 5), `max_clips` (default 60, caps a CPU demo)

## Outputs
- A list of `Segment` (`index`, `start`, `end` in seconds)
- Side effect: `builds/<id>/segments.json` written to B2 (`{count, segments[]}`)

## Flow
- **fixed-stride**: slide a `window_seconds` window across the video every `stride_seconds`, producing evenly spaced candidate intervals (deterministic, no model)
- **scene-detect**: PySceneDetect content-aware detection proposes intervals at scene boundaries
- Either way the interval count is capped at `max_clips` to keep a CPU demo manageable

## Edge Cases
- Video shorter than one window → a single clamped interval
- scene-detect finds no cuts → falls back to a coarse interval / fixed-stride behavior
- More candidates than `max_clips` → truncated to the cap

## UX States
- Surfaced via the build job status `segmenting` and the segment count on the detail page

## Verification
- Test files: `services/api/tests/` (pipeline/segment coverage)
- Required cases: fixed-stride spacing, max_clips cap, short video
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green

## Related Docs
- [Clipping](clipping.md) · [Labeling](labeling-mmaction2.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
