<!-- last_verified: 2026-06-30 -->
# Feature: Dataset Explorer

## Purpose
Browse a build's labeled clips grouped by Kinetics-400 action class, with in-browser video preview — a sample-specific view scoped to the app's own dataset output (distinct from the full-bucket [File Browser](file-browser.md)).

## Used By
- UI: `/dataset` page; the dataset panel on `/builds/[id]`
- API: `GET /builds/{id}/dataset`, `GET /builds/{id}/clips/{clip_id}/preview`

## Core Functions
- `apps/web/src/components/dataset/dataset-explorer.tsx` — class-grouped clip browser + player
- `apps/web/src/components/builds/clip-row.tsx` — a single clip row
- `apps/web/src/lib/queries.ts` — `useBuildDataset()`, `useClipPreviewUrl()`
- `services/api/app/service/builds.py` — `class_groups()`
- `services/api/app/service/files.py` — `get_preview_url()` (presigned playback)

## Canonical Files
- Explorer: `apps/web/src/components/dataset/dataset-explorer.tsx`

## Inputs
- A build id (and the build's labeled clips)

## Outputs
- `GET /builds/{id}/dataset` → `ClassGroup[]` (action, count, clips[])
- `GET /builds/{id}/clips/{clip_id}/preview` → `{ url }` presigned MP4 for inline playback

## Flow
- Page loads the build's clips grouped by action class
- Each group shows its class, clip count, and rows; selecting a clip fetches a short-lived presigned URL and plays it inline
- Scoped strictly to `builds/<id>/dataset/clips/` — it never browses the rest of the bucket

## Edge Cases
- Build not found → 404
- A build with no kept clips → empty explorer with guidance to run a build
- Presigned URL expiry → re-fetched on demand (cheap to regenerate)

## UX States
- Loading: skeletons for groups
- Empty: "No clips yet — run a build"
- Loaded: class groups with playable clip rows
- Error: inline error + retry

## Verification
- Test files: `services/api/tests/` (dataset/clips endpoints)
- Required cases: class grouping, preview URL for an existing clip, 404 for missing clip
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: clips render and play in both the list group and the player

## Related Docs
- [Packaging](packaging.md) · [File Browser](file-browser.md)
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
