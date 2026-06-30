<!-- last_verified: 2026-06-30 -->
# App Workflows

User journeys inside the application.

## Ingest Raw Video

- User navigates to `/upload`
- Drops or selects a video file in the dropzone
- Client validates file size (max 500MB) and type
- Progress bar shows per-file upload status
- On success the video lands in B2 under `raw/` and becomes selectable as a build source
- See: [Ingest](features/file-upload.md)

## Create a Dataset Build

- User navigates to `/builds` and clicks **New build**
- Fills the create form (`/builds/new`): name, source video (selected from ingested `raw/` videos), segmentation strategy (`fixed-stride` or `scene-detect`), window/stride seconds, recognizer model, confidence threshold, split preset, version tag
- Finite-value fields use selectors; safe defaults are surfaced as field hints
- On submit, a `draft` build is created (`POST /builds`) and persisted to `builds/<id>/build.json`
- See: [Builds](features/builds.md)

## Run a Build (segment → clip → label → package)

- From a build's detail page (`/builds/[id]`), user clicks **Run build**
- A background job starts (`POST /builds/{id}/run`); the page polls live progress
- Status advances `queued → segmenting → clipping → labeling → packaging → complete`
- The pipeline downloads the raw video, proposes candidate intervals, trims each to a short clip, runs **MMAction2** to label it (clips below the confidence threshold are dropped), routes kept clips to `dataset/clips/<class>/`, writes per-split annotation CSVs, and packages a versioned release
- On completion the detail page shows clip count, per-class distribution, splits, and release artifacts
- On failure the build status becomes `failed` with the error surfaced in the UI
- See: [Labeling](features/labeling-mmaction2.md), [Packaging](features/packaging.md)

## Inspect the Dataset

- User navigates to `/dataset` (or opens a build) to browse labeled clips grouped by Kinetics-400 action class
- Each clip plays inline (presigned URL); annotation CSVs and the release manifest are viewable
- See: [Dataset Explorer](features/dataset-explorer.md)

## Edit or Delete a Build

- **Edit** (`/builds/[id]/edit`): change a build's config while it is still `draft`. Config is locked after the first run (API returns 409) — create a new build to change it; rename/description stays editable
- **Delete**: removes everything under `builds/<id>/` (prefix-scoped), returns the deleted object count, toast confirms
- See: [Builds](features/builds.md)

## Browse the Bucket

- User navigates to `/files` for a full-bucket tree view (raw footage + all build artifacts)
- Hover a row for preview / download / delete; empty bucket shows an upload prompt
- See: [File Browser](features/file-browser.md)

## View Dashboard

- User navigates to `/` (home)
- Stat cards show footage ingested, builds total / complete, total labeled clips, total classes, storage used
- A recent builds table lists the latest builds with status, source, clip count, and classes
- Empty state: "No builds yet" prompt to create the first build
- See: [Dashboard](features/dashboard.md)
