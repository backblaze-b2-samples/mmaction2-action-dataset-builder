<!-- last_verified: 2026-06-30 -->
# Tech Debt Tracker

Known tech debt items. Agents update this when they discover or create tech debt.

| Description | Impact | Proposed Resolution | Priority | Status |
|---|---|---|---|---|
| In-process background build runner | Build progress is lost on API restart; no horizontal scaling | Move to a durable job queue (e.g. Redis/RQ, Celery, or a managed queue) | High | Open |
| Raw video uploaded through the API is buffered in memory | Large ingests pressure API memory (500MB cap) | Use presigned multipart upload direct to B2 for raw footage | High | Open |
| MMAction2 / `mmcv` install complexity | Fresh-clone labeling can fail if the `mmcv` wheel won't build | Document `mim install mmcv` fallback (done); consider a prebuilt image / extras matrix | Medium | Open |
| Recognizer checkpoints downloaded on first use | First labeled build is slow / needs network | Pre-warm or bake checkpoints into the deployment image | Medium | Open |
| Deterministic positional train/val/test split | Not class-stratified; small datasets may skew per-class balance | Optional stratified split keyed on action class | Low | Open |
| `humanizeBytes` / `formatDate` duplicated in TypeScript | DRY violation | Extract to `lib/utils.ts` | Low | Open |
