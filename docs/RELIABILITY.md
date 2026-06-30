<!-- last_verified: 2026-06-25 -->
# Reliability

Reliability expectations and practices for this project.

## Health Checks

- `GET /health` verifies B2 connectivity and returns `healthy` or `degraded`
- Health endpoint is always available, even when B2 is down

## Error Handling

- HTTP handlers return structured error responses with appropriate status codes
- External service failures (B2) are caught and surfaced as 500/503 responses
- No unhandled exceptions leak stack traces to clients
- Uncaught exceptions are converted to a typed JSON 500 (`{"detail": "Internal server error"}`, modeled by `app.types.ErrorResponse`) by the catch-all in `timing_middleware`
- **Error responses carry CORS headers.** `CORSMiddleware` is registered LAST in `main.py` so it is the outermost middleware and wraps every response — including uncaught-exception 500s produced by the inner catch-all. This is intentional and load-bearing: if a 500 shipped without `Access-Control-Allow-Origin`, the browser would block it and the frontend would surface only an opaque "network error", hiding the real server bug. Regression-guarded by `tests/test_error_handling.py::test_unhandled_exception_500_carries_cors_headers`.

## Logging

- Structured JSON logging via Python stdlib
- Every request gets a `request_id` for tracing
- Log levels: ERROR for failures, WARNING for degraded state, INFO for requests

## Observability

- Request timing middleware logs duration for every request
- `/metrics` endpoint exposes basic Prometheus-format counters
- Upload success/failure counts tracked

## Background Builds

- A build runs on an in-process background thread; live status
  (`queued|segmenting|clipping|labeling|packaging|complete|failed`) is held in an
  ephemeral jobs registry and polled by the UI
- The durable record is `builds/<id>/build.json` on B2 — a process restart loses
  live job progress but not committed build state
- A failed run is captured: `status: "failed"` plus the error is persisted to both
  the job and the build manifest (no silent partial state)
- Re-running an already-running build returns the existing active job (no duplicate)
- **Known limits** (see `docs/exec-plans/tech-debt-tracker.md`): the in-process
  runner is not durable across restarts and large raw uploads are buffered in
  memory — production should use a real job queue and presigned multipart upload

## Graceful Degradation

- Build and file listings return empty lists (not errors) when B2 has no objects
- Clips below the confidence threshold are dropped; a build with zero kept clips
  still completes with an empty dataset rather than failing
- Frontend shows skeleton states while loading, error states with retry on failure

## Deployment

- Railway health checks on `/health`
- Zero-downtime deploys via rolling updates
- Environment-specific configuration via env vars (no config files in prod)
