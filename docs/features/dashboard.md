<!-- last_verified: 2026-06-30 -->
# Feature: Dashboard

## Purpose
Give an at-a-glance overview of dataset-building activity across all builds.

## Used By
- UI: `/` page (dashboard home)
- API: `GET /builds/stats`, `GET /builds`

## Core Functions
- `apps/web/src/components/dashboard/builder-stats-cards.tsx` — stat cards
- `apps/web/src/components/dashboard/recent-builds-table.tsx` — latest builds
- `apps/web/src/lib/queries.ts` — `useBuilderStats()`, `useBuilds()`
- `apps/web/src/lib/api-client.ts` — `getBuilderStats()`, `getBuilds()`
- `services/api/app/runtime/builds.py` — `GET /builds/stats`, `GET /builds`
- `services/api/app/service/builds.py` — `get_dashboard_stats()`, `list_builds()`
- `services/api/app/repo/b2_client.py` — B2 listings/aggregation

## Canonical Files
- Stat cards: `apps/web/src/components/dashboard/builder-stats-cards.tsx`
- Stats service logic: `services/api/app/service/builds.py`

## Inputs
- None (dashboard loads data automatically)

## Outputs
- `GET /builds/stats` → `BuilderStatsSummary` (footage_ingested, builds_total, builds_complete, total_clips, total_classes, storage_used_human)
- `GET /builds` → `BuildSummary[]` for the recent builds table (newest first)

## Flow
- Page loads → two parallel API calls (builder stats, builds list)
- Stat cards display footage ingested, builds total / complete, total labeled clips, total classes, storage used
- Recent builds table shows the latest builds with name, source, status badge, clip count, classes, created date

## Edge Cases
- API unavailable → inline error state with retry
- No builds yet → empty stat values + "No builds yet" table prompt to create the first build
- Large bucket → stats endpoint paginates B2 listings via `ContinuationToken`

## UX States
- Loading: skeleton placeholders for cards and table
- Empty: "No builds yet"
- Loaded: populated cards + recent builds table

## Verification
- Test files: `services/api/tests/` (builds + stats coverage)
- Required cases: stats with builds, stats with empty bucket, API error fallback
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Builds](builds.md)
- [App Workflows](../app-workflows.md)
