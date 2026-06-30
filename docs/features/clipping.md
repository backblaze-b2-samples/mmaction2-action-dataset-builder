<!-- last_verified: 2026-06-30 -->
# Feature: Clipping

## Purpose
Trim each candidate interval into a short, self-contained MP4 clip ready for labeling and dataset packaging.

## Used By
- API: runs inside `POST /builds/{id}/run`
- Job: background pipeline (`services/api/app/service/pipeline.py::_clip_and_label`)

## Core Functions
- `services/api/app/repo/video_tools.py` — `trim_clip(path, start, end)` via the bundled ffmpeg
- `services/api/app/service/pipeline.py` — `_clip_and_label()` orchestration

## Canonical Files
- Engine: `services/api/app/repo/video_tools.py`

## Inputs
- Local path to the downloaded raw video
- `start` / `end` seconds for each `Segment`

## Outputs
- Clip bytes (H.264 MP4). Kept clips (after labeling) are written to `builds/<id>/dataset/clips/<class>/<clip_id>.mp4`
- Side effect: B2 `put_object` per kept clip (`video/mp4`)

## Flow
- For each segment, `trim_clip` invokes ffmpeg from **`imageio-ffmpeg`'s bundled binary** (no dependency on a system ffmpeg; no subtitle/text filters are needed, so the slim-build limitation does not apply)
- The clip is written to a temp file for MMAction2's video decoder, labeled, then (if kept) uploaded to B2 under its class folder

## Edge Cases
- ffmpeg produces empty output for a degenerate interval → the clip is skipped
- Temp files are always cleaned up in a `finally` block
- Clip dropped if its label confidence is below the threshold (see [Labeling](labeling-mmaction2.md))

## UX States
- Surfaced via the build job status `clipping` and per-clip progress

## Verification
- Test files: `services/api/tests/` (pipeline coverage)
- Required cases: trim produces a playable clip, empty-output skip
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green

## Related Docs
- [Segmentation](segmentation.md) · [Labeling](labeling-mmaction2.md) · [Packaging](packaging.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
