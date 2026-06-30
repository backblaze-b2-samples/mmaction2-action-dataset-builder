# Build plan — `mmaction2-action-dataset-builder`

Source of truth for the starter tree: `.claude/scratch/vcsk-013c27b8-e086-44f7-ab8a-5ca7f7d99f00/`
(fresh clone). Delta below is computed against that tree only.

---

## 1. Purpose

`mmaction2-action-dataset-builder` is a self-hosted pipeline for turning raw
long-form video into a **labeled action-recognition dataset** stored entirely on
Backblaze B2. A data/ML team ingests broadcasts, fitness videos, or security
footage to `raw/`, then runs a **build**: the app segments each source video into
candidate action intervals, trims each interval to a short MP4 clip, runs
**MMAction2's recognizer inference** to assign a Kinetics-400 action label +
confidence to every clip, and packages train/val/test split manifests plus a
dataset metadata JSON into a versioned release. B2 is the single storage layer for
raw video, trimmed clips, annotation CSVs, and versioned dataset packages —
accessed via the S3-compatible API with a custom user-agent and standard `B2_*`
env vars. It runs on **local OSS only (MMAction2)** — no second API key, B2
credentials only. It's for ML research teams and sports/security analytics teams
who need training data without standing up a labeling service.

## 2. Architecture delta from vibe-coding-starter-kit

The starter kit is the ceiling. Keep the full-stack scaffolding, strip the
demo-specific surfaces, add the dataset-builder domain.

### KEEP (as-is — starter contract, do not strip/rename/replace)
- UI kit / design system: `apps/web/src/components/ui/**`, design tokens in
  `globals.css`, `/design` page. Build new screens from these primitives only.
- **Bucket explorer (full-bucket browse) — `/files`, `apps/web/src/app/files/`,
  `apps/web/src/components/files/**`, and its sidebar entry. NEVER removable.**
- FastAPI layered architecture: `types → config → repo → service → runtime`,
  structural tests, JSON logging, `/health`, `/metrics`, TanStack Query data
  layer, single-`.env` config, error/empty-state patterns, doctor preflight.
- Sidebar shell, header, command palette, theme provider, query client.
- `packages/shared` typed-contract pattern (mirror new Pydantic models into it).

### KEEP-with-minor-adaptation
- **Upload page (`/upload`)** stays as the starter contract requires (page +
  sidebar entry kept). Adapt only its copy + default target prefix so it **ingests
  raw video under `raw/`** and accepts large video (raise `max_file_size`, document
  the in-memory-buffer limit + production multipart note). It is the Ingest step.

### TRIM (remove from starter — not needed here)
- **Metadata extraction feature** (`service/metadata.py`, `types/*` for image/PDF
  metadata, `docs/features/metadata-extraction.md`, Pillow/PyPDF2 deps). The
  dataset builder doesn't extract EXIF/PDF info. Remove the feature, its doc, its
  deps, and its tests; drop the structural reference if any.
- Starter "recent uploads" dashboard widgets that don't map to builds (replaced,
  see Dashboard adaptation).
- Starter `docs/exec-plans/completed/*` (starter history, not this app's) and
  reset `tech-debt-tracker.md` to this app's known debt. The scaffold plan is moved
  into `completed/` at the end of this build.

### ADD (new for this sample)
- **Primary entity: `Dataset Build`** (a build job) with full CRUD+run UI
  (§4). Persisted as JSON in B2 (no database — B2 stays the sole store).
- **`/builds`** — list + create + detail (read) + edit + delete + run.
- **Sample-specific asset explorer — `/dataset`** ("Dataset" view): browse the
  produced clips **scoped to the sample's own output prefix** (`builds/<id>/dataset/`),
  grouped by action class, with in-browser **video preview that must actually
  paint**, plus panels to view annotation CSVs and the release manifest/metadata.
  This satisfies the mandatory "add a sample-specific explorer scoped to the
  sample's own folder" requirement; the generic `/files` bucket explorer is the
  separate, kept full-bucket browser.
- **Adapted Dashboard** (see below).
- Backend domain: `repo/mmaction_engine.py` (MMAction2 recognizer adapter),
  `repo/video_tools.py` (ffmpeg trim + scene-detect via PySceneDetect),
  `repo/builds_store.py` (build JSON CRUD on B2), `service/builds.py`,
  `service/pipeline.py` (segment→clip→label→package orchestration + background
  runner + status), `types/builds.py`, `runtime/builds.py`. New endpoints wire the
  three files (`runtime`, `api-client.ts`, `queries.ts`) and mirror types into
  `packages/shared`.

> **Bucket-explorer tension note:** none — `/files` is fully retained and useful
> here (operators browse raw video and dataset artifacts bucket-wide). No removal
> pressure exists.

### Storage layout (B2 — exact described paths, rooted per build for isolation)
- `raw/<video>` — shared ingest pool (input to builds).
- `builds/<build_id>/build.json` — build config + status + results summary.
- `builds/<build_id>/segments.json` — segment manifest.
- `builds/<build_id>/dataset/clips/<class>/<clip_id>.mp4` — trimmed labeled clips.
- `builds/<build_id>/dataset/annotations/<split>.csv` — per-split annotation CSVs.
- `builds/<build_id>/dataset/releases/<version>/{manifest.json,metadata.json,*.csv}`.

Rooting the described `dataset/clips|annotations|releases` layout under
`builds/<build_id>/` preserves the exact structure the use case calls for while
keeping builds isolated and making **delete trivially prefix-scoped** (delete =
remove everything under `builds/<build_id>/`, never touching `raw/` or other
builds). This is a deliberate, documented decision — reviewer please accept.

## 3. B2 surface (S3-compatible only — no b2-native)

All operations via the existing `repo/b2_client.py` boto3 S3 client (custom
user-agent retained). Operations exercised:
- `put_object` — raw video ingest, clips, annotation CSVs, release
  manifest/metadata JSON, `build.json`, `segments.json`.
- `list_objects_v2` (paginated) — list raw videos, list builds, list clips by
  class for the dataset explorer, dashboard aggregates.
- `head_object` — artifact metadata.
- `get_object` — read raw video bytes for processing; read build JSON.
- `generate_presigned_url` (get_object) — clip/video preview + download.
- `delete_object` / `delete_objects` (batched) — delete a build's prefix.

**No b2-native API used.** No deviation to justify.

## 4. Key features (seed README + `docs/features/*`)

Primary entity = **Dataset Build**. DEFAULT = all lifecycle verbs in the UI;
none omitted (so Phase-5 `omitted_ui_verbs` is expected empty).

| Verb | UI surface | Notes |
|------|-----------|-------|
| create | `/builds` → "New build" form | full create form (selectors + default hints, §Form UX) |
| read | `/builds` list + `/builds/[id]` detail | status, segment count, clip count, per-class label distribution, release artifacts w/ preview |
| edit | `/builds/[id]` edit (enabled only while status = `draft`; rename allowed anytime) | pre-filled form; once a build has run, config is read-only with an inline rationale — verb still present, not omitted |
| delete | `/builds` + detail | deletes the build's `builds/<id>/` prefix (scoped); confirm dialog |
| run | `/builds/[id]` "Run build" | kicks off background pipeline; UI polls status |

**Feature bullets / `docs/features/*` stubs:**
1. **Ingest** (`docs/features/ingest.md`) — upload raw video to `raw/` (adapted Upload page). `deployment: n/a` (pure B2).
2. **Segment** (`docs/features/segmentation.md`) — candidate action intervals via **fixed-stride windowing (default)** or **scene-detect (PySceneDetect, content-aware)**; writes `segments.json`. `deployment: local` (CPU; CUDA→MPS→CPU autodetect inherited, though both strategies are CPU-only compute).
3. **Clip** (`docs/features/clipping.md`) — trim+encode each interval to a short MP4 via **imageio-ffmpeg's bundled ffmpeg binary** (no system-ffmpeg dependency; no subtitles/drawtext needed so the slim-build gotcha doesn't apply). `deployment: local` (CPU).
4. **Label** (`docs/features/labeling-mmaction2.md`) — **MMAction2 recognizer inference** (`mmaction.apis.init_recognizer` + `inference_recognizer`) assigns a Kinetics-400 action label + confidence to each clip; clips routed to `dataset/clips/<class>/`; rows written to `dataset/annotations/<split>.csv`. **Vendor fidelity: real MMAction2 engine, no substitute.** `deployment: local`, **CPU default, autodetect CUDA→MPS→CPU** (mmcv MPS support is weak → on Apple Silicon effectively CUDA→CPU; note this in the doc).
5. **Package** (`docs/features/packaging.md`) — assign clips to train/val/test by ratio, write split manifests + dataset `metadata.json` to `dataset/releases/<version>/`. `deployment: n/a`.
6. **Dataset explorer** (`docs/features/dataset-explorer.md`) — class-grouped clip browser scoped to the sample's output, with painting video preview. `deployment: n/a`.
7. **Builds** (`docs/features/builds.md`) — the build lifecycle itself (CRUD+run, background status). `deployment: n/a`.

### External API provider
**None.** MMAction2 is the sample's whole point and is an on-device/local OSS
framework → per `api-provider-selection.md` rule 1 (local capability), `deployment:
local`, **CPU default with CUDA→MPS→CPU autodetect**, no remote path needed, **no
key beyond `B2_*`**. No Genblaze (the description's "Trending OSS" is MMAction2, with
no Genblaze/`genblaze-*`/`genblaze-s3` mention) — do **not** route through the
Genblaze SDK. Per-feature `deployment` fields are recorded above as explicit fields.

### Background execution
`run` launches the segment→clip→label→package pipeline on an in-process background
worker; status (`queued|segmenting|clipping|labeling|packaging|complete|failed`,
progress, error) is persisted into `build.json` on B2 and polled by the UI via a
TanStack Query hook. Stays within layering (`runtime → service.pipeline → repo`).
Guard against concurrent runs of the same build. Document that production needs a
real job queue.

### ML dependency containment + clean-install safety (CRITICAL)
- All MMAction2 / torch / ffmpeg / scenedetect imports live in `repo/` only
  (`mmaction_engine.py`, `video_tools.py`), mirroring the boto3-in-repo invariant.
  **Add structural-test rows** asserting `mmaction`/`torch`/`scenedetect` are
  imported only under `repo/` (extend `test_structure.py`).
- Heavy ML deps go in a separate **pinned** `services/api/requirements-ml.txt`
  (base `requirements.txt` stays light so the API boots + tests pass without the ML
  install). **Pin every ML dep to a working window** — an unpinned ML requirements
  file is a known false-green (boots + tests pass, marquee feature dies on a fresh
  clone). Recommended window (builder to confirm against MMAction2's install
  matrix): `torch==2.1.2`/`torchvision==0.16.2` (CPU wheels), `mmengine>=0.10,<0.11`,
  `mmcv>=2.1,<2.2`, `mmaction2>=1.2,<1.3`, `scenedetect>=0.6.4,<0.7`,
  `imageio-ffmpeg>=0.5,<0.7`, `decord>=0.6,<0.7` (or opencv-python), `pandas`,
  `numpy`. Document the `mim`/`mmcv` install caveat in the README + dev-workflows
  (mmcv may need a prebuilt wheel via `mim install mmcv`). Flag MMAction2 install
  complexity as the top **verify-step risk**.
- `mmaction_engine.py` **lazy-imports** mmaction/torch inside functions so the base
  API boots without the ML install; add a **no-network signature-guard test** that
  asserts the engine module exposes its public functions (and `device` autodetect)
  without importing torch/mmaction (skip-if-not-installed), mirroring the genblaze
  signature-guard pattern.

### Form UX conventions
- **Create form (`/builds` new):** selectors for every finite-value field, safe
  defaults surfaced as placeholder / `FormDescription` (guidance only, no autofill
  button). Use `apps/web/src/components/settings/settings-form.tsx` as the in-repo
  exemplar (react-hook-form + zod + shadcn Form/Select/RadioGroup).
  - Build name — `Input` (free text).
  - Source video — `Select` (populated from `raw/` listing). Default hint: "pick an ingested video".
  - Segmentation strategy — `RadioGroup`: `fixed-stride` (default) | `scene-detect`.
  - Window length (s) — `Input type=number`, default hint 5.
  - Stride (s) — `Input type=number`, default hint 5 (fixed-stride only; hide/disable for scene-detect).
  - Recognizer model — `Select` (finite): `tsn-r50-kinetics400` (default, "TSN R50 · Kinetics-400 · fast/CPU-friendly"), `tsm-r50-kinetics400`.
  - Confidence threshold — `Input type=number` (0–1), default hint 0.30.
  - Split preset — `Select` (finite): `70/15/15` (default), `80/10/10`, `60/20/20`.
  - Version tag — `Input` (free text), default hint `v1`.
- **Edit form:** same selectors, opens **pre-filled** with the build's real config
  (no default hints — it's editing a real resource). Disabled when status≠`draft`.

## 5. Doc transforms
- **README.md** — full rewrite to the dataset-builder narrative; rebrand; fix the
  B2 setup section to Standard-#3 env vars (`B2_APPLICATION_KEY_ID`, `B2_REGION`,
  `B2_PUBLIC_URL_BASE`); update feature list, tech stack (+PyTorch/MMAction2/
  ffmpeg/PySceneDetect), commands (ML install step), Quick Start; rename "What it
  looks like" image refs to `docs/images/mmaction2-action-dataset-builder-*.png`
  (screenshot step populates later — build step creates no binaries).
- **ARCHITECTURE.md** — new components (ML engine repo modules, builds store,
  pipeline service, background runner), data flows (ingest→segment→clip→label→
  package), external-engine containment, local-CPU/GPU-autodetect note, updated
  env/data-store sections, build-JSON-as-state.
- **AGENTS.md** — updated repo map; **keep** §2 starter contract; add
  mechanical-enforcement rows for mmaction/torch/scenedetect containment; updated
  commands (`pip install -r requirements-ml.txt`).
- **docs/features/** — DELETE `metadata-extraction.md`; REWRITE `dashboard.md`
  (dataset metrics), `file-upload.md`→ingest framing (or new `ingest.md`),
  `file-browser.md` (bucket explorer, keep). ADD `builds.md`, `segmentation.md`,
  `clipping.md`, `labeling-mmaction2.md`, `packaging.md`, `dataset-explorer.md`
  from `_template.md`.
- **docs/app-workflows.md** / **dev-workflows.md** — new user journeys (ingest→
  build→inspect→export) + engineering flows incl. ML deps install, CPU/GPU,
  mmcv/mim caveat, background-job testing.
- **docs/SECURITY.md** / **RELIABILITY.md** — large-file ingest handling,
  background-job failure surfacing, presigned-URL preview, prefix-scoped delete.
- **exec-plans** — clear starter `completed/*`; reset `tech-debt-tracker.md`.

## 6. Rename table

| Kind | From | To |
|------|------|----|
| repo dir | `vibe-coding-starter-kit` | `mmaction2-action-dataset-builder` |
| root pkg name (`package.json`) | `vibe-coding-starter-kit` | `mmaction2-action-dataset-builder` |
| web pkg scope | `@vibe-coding-starter-kit/web` | `@mmaction2-action-dataset-builder/web` |
| shared pkg scope | `@vibe-coding-starter-kit/shared` | `@mmaction2-action-dataset-builder/shared` |
| all scope importers | `@vibe-coding-starter-kit/*` (queries.ts, file-*.tsx, upload-progress.tsx, command-palette.tsx, next.config.ts, …) | `@mmaction2-action-dataset-builder/*` |
| pnpm filter (README/cmds) | `--filter @vibe-coding-starter-kit/web` | `--filter @mmaction2-action-dataset-builder/web` |
| Title Case | `Vibe Coding Starter Kit` / `OSS Starter Kit` | `MMAction2 Action Dataset Builder` |
| `APP_NAME` (app-config.ts) | `OSS Starter Kit` | `MMAction2 Action Dataset Builder` |
| `APP_DESCRIPTION` | `File management dashboard powered by Backblaze B2` | `Build labeled action-recognition datasets from raw video, stored on Backblaze B2.` |
| header branding leak (header.tsx) | hardcoded `oss-starter-kit` + `"Page"` fallback | derive title from `APP_NAME` + route; add titles for `/builds`, `/dataset` (fix the known leak) |
| user-agent | `user_agent_extra="b2ai-oss-start"` | `b2ai-mmaction2-action-dataset-builder` |
| UTM content tag | `utm_content=b2ai-oss-start` | `utm_content=b2ai-mmaction2-action-dataset-builder` |
| env: key id | `B2_KEY_ID` / `b2_key_id` | `B2_APPLICATION_KEY_ID` / `b2_application_key_id` |
| env: endpoint→region | `B2_ENDPOINT` / `b2_endpoint` | `B2_REGION` / `b2_region` (build endpoint `https://s3.{region}.backblazeb2.com`) |
| env: public url | `B2_PUBLIC_URL` / `b2_public_url` | `B2_PUBLIC_URL_BASE` / `b2_public_url_base` |
| env unchanged | `B2_APPLICATION_KEY`, `B2_BUCKET_NAME` | (keep) |
| env readers | settings.py fields + b2_client.py + .env.example + README + infra/railway/README.md + scripts/doctor.mjs | rename consistently |

**Env-var note (Standard #3):** the starter ships non-standard names; the b2-doctor
skill is stale on this. Rename to exactly `B2_APPLICATION_KEY_ID`,
`B2_APPLICATION_KEY`, `B2_BUCKET_NAME`, `B2_REGION`, `B2_PUBLIC_URL_BASE` and update
`settings.py`, every reader, `.env.example`, README, `infra/railway/README.md`,
`scripts/doctor.mjs`. Endpoint is derived from `B2_REGION`.

---

### Acceptance gates (what the reviewer will check)
- S3-only (no b2-native); custom user-agent on the S3 client; Standard-#3 `B2_*`
  names everywhere incl. infra/railway + doctor.
- Bucket explorer `/files` retained; sample-specific `/dataset` explorer added with
  **video preview that actually paints**.
- Primary entity `Dataset Build` exposes create/read/edit/delete/run in the UI.
- Create form: selectors for finite fields, default hints (no autofill); edit form
  pre-filled.
- MMAction2 is the **real** labeling engine (no simulation); imports contained in
  `repo/` and verified by structural test; ML deps **pinned** in `requirements-ml.txt`.
- Layering intact (`types→config→repo→service→runtime`), files <300 lines, JSON
  logging, TanStack Query for all fetches, docs updated, lint/build/test:api/
  check:structure green.
