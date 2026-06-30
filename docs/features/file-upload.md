<!-- last_verified: 2026-06-30 -->
# Feature: Ingest (Raw Video Upload)

## Purpose
Upload raw long-form video from the browser to Backblaze B2 under `raw/`, forming the ingest pool every Dataset Build draws from.

## Used By
- UI: `/upload` page, upload form component
- API: `POST /upload`

## Core Functions
- `apps/web/src/components/upload/upload-form.tsx` — orchestrates dropzone + progress + upload state
- `apps/web/src/components/upload/dropzone.tsx` — drag-and-drop via `react-dropzone`
- `apps/web/src/components/upload/upload-progress.tsx` — per-file progress, errors, retry controls
- `apps/web/src/lib/api-client.ts` — `uploadFile()` using XHR for progress events
- `services/api/app/runtime/upload.py` — HTTP handler, reads file chunks
- `services/api/app/service/upload.py` — validates, sanitizes, stores under `raw/`, computes basic metadata
- `services/api/app/repo/b2_client.py` — `upload_file()` via boto3 `put_object`

## Canonical Files
- Upload handler pattern: `services/api/app/runtime/upload.py`
- Service orchestration pattern: `services/api/app/service/upload.py`
- Frontend upload flow: `apps/web/src/components/upload/upload-form.tsx`

## Inputs
- file: `File` (from browser, multipart form data) — a video (e.g. broadcast, fitness, security footage)
- content_type: string (from file MIME type)

## Outputs
- `FileUploadResponse`: key, filename, size, content_type, uploaded_at, url, metadata (content hashes + size only)
- Side effect: video stored in B2 under `raw/{sanitized_filename}` — selectable as a build source

## Flow
- User drops or selects a video in the dropzone
- Client validates file size (max 500MB) and type — rejected files remain in the queue with a clear reason
- XHR sends multipart POST to `/upload` with progress events
- API checks `Content-Length` early to reject oversized requests before reading the body
- API sanitizes the filename (strips path components, null bytes, unsafe chars, length cap)
- API reads the file with streaming size enforcement and rejects empty files
- API uses key `raw/{sanitized_filename}` and calls `put_object` to B2
- API computes basic metadata (content hash + size; no EXIF/PDF extraction)
- API returns `FileUploadResponse`; client shows a toast and refreshes shared data

## Edge Cases
- File exceeds 500MB → client-side rejected row + toast; API returns 413 if bypassed
- File type not in allowlist → API returns 415
- No filename provided → API returns 400
- Empty file → API returns 400
- Duplicate filename → B2 creates a new version (buckets are versioned)
- B2 unreachable → API returns 500; UI keeps failed rows retryable

## UX States
- Empty: dropzone with instructions
- Loading: per-file progress bars
- Error: red status icon, error message per file, retry when applicable
- Complete: green checkmark, "Clear finished" button

## Verification
- Test files: `services/api/tests/test_upload_conflict.py`, `services/api/tests/test_error_handling.py`
- Required cases: successful upload, oversized rejection, disallowed type, missing filename, empty file, duplicate allowed
- Quick verify command: `pnpm test:api`
- Full verify command: `pnpm lint && pnpm lint:api && pnpm test:api && pnpm check:structure`
- Pass criteria: all pytest tests green, no ruff violations

## Related Docs
- [ARCHITECTURE.md](../../ARCHITECTURE.md)
- [Builds](builds.md)
- [App Workflows](../app-workflows.md)
