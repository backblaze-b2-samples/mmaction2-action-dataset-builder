<!-- last_verified: 2026-06-30 -->
# Architecture

## Components

- **apps/web/** — Next.js 16 frontend (App Router, Tailwind v4, shadcn/ui)
  - Dashboard with dataset-build metrics (footage ingested, builds, labeled clips, classes)
  - Builds: list / create / detail / edit / run, with live job progress
  - Dataset explorer: labeled clips grouped by action class, with in-browser video preview (scoped to a build)
  - Raw-video ingest (Upload page) and full-bucket File Browser
  - Dark mode via `next-themes`
- **services/api/** — FastAPI backend (layered architecture)
  - REST API for raw-video ingest, build CRUD + run, dataset listing, file browse
  - B2 S3 integration via boto3 (repo layer)
  - **MMAction2 recognizer inference** + video segmentation/trimming, contained in the repo layer
  - Background build pipeline (segment → clip → label → package) with live progress
  - Health check endpoint with B2 connectivity verification
  - Structured JSON logging with request tracing; Prometheus-format metrics endpoint
- **packages/shared/** — TypeScript type definitions
  - Mirrors Pydantic models from the API (Build, BuildConfig, LabeledClip, …)
  - Consumed by `apps/web/` as workspace dependency

## Backend Layering

The API follows a strict layered architecture:

```
types/     Pydantic models — no logic, no imports from other layers
  |
config/    Settings (pydantic-settings) — depends only on types
  |
repo/      Data access + external engines (boto3 B2, MMAction2, ffmpeg, scenedetect) — no business logic
  |
service/   Business logic — orchestrates repo, returns types
  |
runtime/   FastAPI routes — calls service, never repo directly
```

### Layering Rules

1. Dependencies flow downward only: `types` -> `config` -> `repo` -> `service` -> `runtime`
2. No backward imports (e.g., service must not import from runtime)
3. `boto3` **and the heavy ML/media SDKs** (`mmaction`, `torch`, `torchvision`, `scenedetect`) are only allowed in the `repo/` layer
4. All boundary data uses Pydantic models (no raw dicts across layers)
5. Each file stays under 300 lines

### Directory Structure

```
services/api/
  main.py                  App entrypoint, middleware, router registration
  app/
    types/                 Pydantic models (Build, BuildConfig, LabeledClip, files, stats, …)
    config/                Settings loaded from environment
    repo/                  B2 S3 client + ML/media engines (data + compute access layer)
      b2_client.py         boto3 S3 access (put/list/head/get/presign/delete)
      builds_store.py      build-JSON CRUD + prefix-scoped delete on B2
      mmaction_engine.py   REAL MMAction2 recognizer inference + device autodetect (lazy heavy imports)
      video_tools.py       segment_video + trim_clip (imageio-ffmpeg, PySceneDetect)
    service/               Business logic (builds, pipeline, jobs, upload, files)
    runtime/               FastAPI route handlers (builds, upload, files, health, metrics)
  tests/                   pytest tests (structural + integration)
  requirements.txt         base API deps (light — API boots + tests pass without ML)
  requirements-ml.txt      pinned MMAction2/PyTorch/PySceneDetect/imageio-ffmpeg stack
```

## Boundary Invariants

- **No external SDK leakage**: `boto3` and the ML/media SDKs (`mmaction`, `torch`, `torchvision`, `scenedetect`) are only imported in `app/repo/`. All other layers go through the repo interface. Enforced by `tests/test_structure.py::test_boto3_only_in_repo` and `::test_ml_sdks_only_in_repo`.
- **Lazy heavy imports**: `repo/mmaction_engine.py` imports torch/mmaction *inside* functions, so importing the module (and booting the API / running tests) does not require the ML install.
- **No raw dicts at boundaries**: All data crossing layer boundaries uses typed Pydantic models.
- **No mutable globals**: Configuration is read-only after init.
- **Validated inputs**: All HTTP inputs validated by FastAPI/Pydantic. File keys validated against a prefix allowlist before any B2 access.

## Deployment

- **Local dev** — `pnpm dev` runs both services via `concurrently` (Web `localhost:3000`, API `localhost:8000`)
- **Railway** — two services from the same repo; see `infra/railway/README.md`
- **Compute** — the MMAction2 labeler runs locally, **CPU by default**, auto-detecting CUDA → Apple MPS → CPU at runtime (mmcv MPS coverage is partial, so Apple Silicon effectively uses CPU)

## Data Stores

- **Backblaze B2** — object storage (S3-compatible API), the **sole data store** (no application database)
  - Each **Dataset Build** is persisted as JSON at `builds/<id>/build.json` (config + status + stats + clips + releases)
  - Build artifacts live under the build's own prefix (clips, annotations, releases, segment manifest)
  - Raw source footage lives under `raw/`
  - Listing/metadata via S3 `list_objects_v2` / `head_object`; reads via `get_object`; downloads/previews via presigned URLs
- **In-process job registry** — live build progress (`queued|segmenting|clipping|labeling|packaging|complete|failed`) is ephemeral and process-local; the durable record is `build.json` on B2

### B2 key layout

```
raw/<video>
builds/<id>/build.json
builds/<id>/segments.json
builds/<id>/dataset/clips/<class>/<clip_id>.mp4
builds/<id>/dataset/annotations/<split>.csv
builds/<id>/dataset/releases/<version>/{manifest.json,metadata.json,train.csv,val.csv,test.csv}
```

## External Services

- **Backblaze B2 S3 API** — storage, retrieval, deletion, presigned URLs. No b2-native API is used.
- **MMAction2** — local OSS, no network service or API key. No other external API.

## Trust Boundaries

See [docs/SECURITY.md](docs/SECURITY.md) for full security documentation.

- **Frontend -> API** — CORS-restricted to configured origins. `CORSMiddleware` is registered LAST in `main.py` (outermost) so it wraps **every** response, including uncaught-exception 500s. See [docs/RELIABILITY.md](docs/RELIABILITY.md#error-handling).
- **API -> B2** — authenticated via application keys, signature v4
- **Client -> B2** — presigned URLs for clip/video preview + download (short expiry, forced attachment for downloads)

## Data Flows

- **Ingest**: Browser -> `POST /upload` (multipart) -> service validates + sanitizes -> repo writes to `raw/` -> response
- **Create build**: Browser -> `POST /builds` -> service validates config + source key -> repo writes `build.json` (status `draft`)
- **Run build**: Browser -> `POST /builds/{id}/run` -> mark running + enqueue background job -> pipeline downloads raw video, segments, trims clips, **runs MMAction2 labeling**, writes clips/annotations/release, updates `build.json` -> UI polls `GET /builds/jobs/list` for live progress
- **Inspect**: `GET /builds/{id}` (manifest), `GET /builds/{id}/dataset` (class-grouped clips), `GET /builds/{id}/clips/{clip_id}/preview` (presigned playback)
- **Dashboard**: `GET /builds/stats` -> service aggregates B2 listings + manifests
- **Delete**: `DELETE /builds/{id}` -> service deletes everything under `builds/<id>/` (prefix-scoped), returns object count

## Observability

- Structured JSON logging on all requests with `request_id`
- Request timing middleware (also the catch-all that converts uncaught exceptions to a typed JSON 500)
- `/metrics` endpoint (Prometheus format)
- `/health` endpoint (B2 connectivity check)

## Canonical Files

- Layered API handler: `services/api/app/runtime/builds.py`
- Service orchestration: `services/api/app/service/builds.py`, `services/api/app/service/pipeline.py`
- B2 data access (repo layer): `services/api/app/repo/b2_client.py`, `services/api/app/repo/builds_store.py`
- ML / media engines (repo layer): `services/api/app/repo/mmaction_engine.py`, `services/api/app/repo/video_tools.py`
- Pydantic models: `services/api/app/types/builds.py`
- Config (pydantic-settings): `services/api/app/config/settings.py`
- Structural tests: `services/api/tests/test_structure.py`
- Frontend API client: `apps/web/src/lib/api-client.ts`
- Frontend data hooks: `apps/web/src/lib/queries.ts`
- Shared TypeScript types: `packages/shared/src/types.ts`

## Core Features

- [Builds](docs/features/builds.md)
- [Ingest](docs/features/file-upload.md)
- [Segmentation](docs/features/segmentation.md)
- [Clipping](docs/features/clipping.md)
- [Labeling (MMAction2)](docs/features/labeling-mmaction2.md)
- [Packaging](docs/features/packaging.md)
- [Dataset Explorer](docs/features/dataset-explorer.md)
- [File Browser](docs/features/file-browser.md)
- [Dashboard](docs/features/dashboard.md)

## References

- [docs/SECURITY.md](docs/SECURITY.md) — security principles and implementation
- [docs/RELIABILITY.md](docs/RELIABILITY.md) — reliability expectations
- [AGENTS.md](AGENTS.md) — architectural invariants and agent instructions
