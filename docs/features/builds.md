<!-- last_verified: 2026-06-30 -->
# Feature: Builds (Dataset Build lifecycle)

## Purpose
Create, configure, run, inspect, edit, and delete a **Dataset Build** — the primary entity that turns one raw video into a labeled action-recognition dataset.

## Used By
- UI: `/builds` (list), `/builds/new` (create), `/builds/[id]` (detail + run), `/builds/[id]/edit` (edit), `/dataset` (inspect)
- API: `GET/POST /builds`, `GET/PATCH/DELETE /builds/{id}`, `POST /builds/{id}/run`, `GET /builds/sources`, `GET /builds/stats`, `GET /builds/jobs/list`, `GET /builds/{id}/dataset`, `GET /builds/{id}/clips/{clip_id}/preview`
- Job: in-process background pipeline (see [Labeling](labeling-mmaction2.md))

## Core Functions
- `apps/web/src/components/builds/builds-list.tsx`, `build-form.tsx`, `build-detail.tsx`, `build-edit.tsx`, `clip-row.tsx`
- `apps/web/src/lib/queries.ts` — `useBuilds`, `useBuild`, `useCreateBuild`, `useUpdateBuild`, `useDeleteBuild`, `useRunBuild`, `useBuildJobs`, `useSources`
- `services/api/app/runtime/builds.py` — HTTP layer
- `services/api/app/service/builds.py` — build CRUD + dashboard stats + sources
- `services/api/app/repo/builds_store.py` — build-JSON persistence + prefix-scoped delete

## Canonical Files
- Service orchestration: `services/api/app/service/builds.py`
- Build persistence: `services/api/app/repo/builds_store.py`
- Create/edit form exemplar: `apps/web/src/components/builds/build-form.tsx`

## Inputs
- Build name + description (text)
- `BuildConfig`: `source_key` (a `raw/` object key), `strategy` (`fixed-stride`|`scene-detect`), `window_seconds` (default 5), `stride_seconds` (default 5), `recognizer_model` (`tsn-r50-kinetics400` default, `tsm-r50-kinetics400`), `confidence_threshold` (default 0.30), `split_preset` (`70/15/15`|`80/10/10`|`60/20/20`), `version_tag` (default `v1`), `max_clips` (default 60)

## Outputs
- `Build` manifest persisted at `builds/<id>/build.json` (config + status + stats + clips + releases)
- Side effects on run: segment manifest, clips, annotation CSVs, release artifacts (see [Packaging](packaging.md))

## Flow
- **Create** → `POST /builds` validates the config + source key, writes a `draft` build
- **Read** → list (`BuildSummary[]`) and detail (`Build` with clips, class distribution, releases)
- **Edit** → `PATCH /builds/{id}` updates config while `draft`; name/description always editable
- **Delete** → `DELETE /builds/{id}` removes everything under `builds/<id>/`, returns object count
- **Run** → `POST /builds/{id}/run` marks the build running and enqueues a background job; the UI polls `GET /builds/jobs/list`

## Edge Cases
- Editing config after a run → API returns 409 (config locked); create a new build instead
- Running an already-running build → returns the existing active job (no duplicate run)
- Build not found → 404
- Invalid config / missing source video → 400
- Delete failure → 500

## UX States
- Empty: "No builds yet" prompt
- Loading: skeletons on list/detail
- Running: live status + progress bar (queued → … → complete)
- Error: failed badge + error message; inline retry on fetches

## Verification
- Test files: `services/api/tests/` (builds CRUD, structure)
- Required cases: create, list, get, patch-locked-after-run, delete-scoped, run-enqueues-job
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Segmentation](segmentation.md) · [Clipping](clipping.md) · [Labeling](labeling-mmaction2.md) · [Packaging](packaging.md)
- [App Workflows](../app-workflows.md)
