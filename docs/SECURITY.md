<!-- last_verified: 2026-04-22 -->
# Security

Security principles and implementation for the MMAction2 Action Dataset Builder.

## Trust Boundaries

- **Frontend -> API**: CORS-restricted to configured origins, scoped to `GET/POST/PATCH/DELETE/OPTIONS`
- **API -> B2**: Authenticated via `B2_APPLICATION_KEY_ID` + `B2_APPLICATION_KEY`, signature v4
- **Client -> B2**: Presigned URLs for clip/video preview + download (short expiry; downloads force `Content-Disposition: attachment`)

## Ingest Validation

- Filename sanitization: path traversal, null bytes, unsafe chars stripped
- MIME/extension consistency check against an allowlist (video formats)
- Streaming size enforcement (500MB default for raw video; `Content-Length` checked early)
- Empty file rejection
- Raw footage is stored under the `raw/` prefix only

## File Key Validation

- Empty keys rejected; path-traversal patterns rejected (`../`, `%2e%2e`, backslashes, null bytes)
- Object keys are passed as query parameters (not path segments) so slashes and reserved route names cannot be decoded into traversal
- **Prefix-scoped deletes**: deleting a build removes only objects under `builds/<id>/`; raw footage and other builds are never touched

## Background Jobs

- Build runs execute in-process; a failure is captured and persisted as `status: "failed"` with the error on both the job and `build.json` (no silent partial state)
- No untrusted code is executed — the recognizer runs fixed, configured model checkpoints only

## Download Safety

- Presigned URLs force `Content-Disposition: attachment`
- Prevents inline rendering of user-uploaded content (XSS mitigation)

## Secrets Management

- All secrets loaded via environment variables (pydantic-settings)
- Never committed to source control
- `.env.example` documents required variables without values

## Agent Security Rules

- Never commit `.env`, credentials, or API keys
- Never weaken validation without explicit instruction
- Never bypass CORS, auth, or input sanitization
- Always validate at system boundaries
