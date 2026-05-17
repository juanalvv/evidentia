# Evidentia — Report API contract (Person C ↔ A/B)

Person B exposes these endpoints. Person A's orchestrator writes analysis data into job storage; Person C consumes the normalized payload via `GET /report/{job_id}`.

**Canonical JSON shape:** **`SCHEMAS.md` § Final AnalysisResult / Report Payload** (includes `final_verdict`, `data_quality`, and other Person C minimums). `fixtures/mock_analysis.json` is a concrete example. `CONTRACT.md` summarizes HTTP behavior; SCHEMAS is authoritative for fields.

## Endpoints (Person B)

| Method | Path | Body / response |
|--------|------|-----------------|
| `POST` | `/analyze` | `multipart/form-data`: see [POST /analyze](#post-analyze-multipart) below. **Response:** `{ "job_id": "<uuid>", "status": "pending" }` (HTTP 200). Poll `GET /status/{job_id}` until `completed` or `failed`. |
| `GET` | `/status/{job_id}` | `{ "job_id", "status", "progress", "error" }` — see progress schema |
| `GET` | `/report/{job_id}` | **HTTP 202** while `pending`/`running` (not ready). **HTTP 200** body = **SCHEMAS.md Final AnalysisResult** when `completed` or `failed` (same top-level keys; `status` field inside JSON matches the job). |
| `POST` | `/report/build` | JSON body = **SCHEMAS.md Final AnalysisResult** (e.g. `fixtures/mock_analysis.json`). Returns `{ "markdown": "..." }` from `build_report()`. |

### POST /analyze (multipart)

Use `multipart/form-data`. At least one of **`file`**, **`text`**, or **`doi`** must be present (otherwise **400**).

| Field | Type | Notes |
|--------|------|--------|
| `file` | upload | PDF bytes; parsed for full text + references. |
| `text` | string | Plain draft; references section extracted like PDF text. |
| `doi` | string | **DOI-only path:** skips file/text; runs enrichment for this DOI (Unpaywall email optional). |
| `email` | string | Optional; forwarded to Unpaywall as contact email (see `.env.example` / `UNPAYWALL_EMAIL`). |

**Response body:** `{ "job_id": "<uuid>", "status": "pending" }`. The worker runs in a background task; `status` stays `pending` until the task flips the job to `running` then `completed` or `failed`.

### `progress` (for UI polling)

Aligned with **SCHEMAS.md** Final `progress` object:

```json
{
  "phase": "ingest | source_check | counter_research | grading | report | done",
  "percent": 0,
  "message": "Human-readable step label",
  "agent": "orchestrator | source_checker | counter_researcher | grader"
}
```

## `AnalysisResult` (→ report builder + frontend)

See **`SCHEMAS.md` § Final AnalysisResult** and `fixtures/mock_analysis.json`. Required top-level keys include:

- `job_id`, `status`, `paper`, `progress` (final), `executive_summary`
- `overall_scores`: `{ source_quality, coverage, data_quality }` — floats `0..1`
- `citations[]`, `claims[]`, `data_quality`, **`final_verdict`**
- Optional: `markdown`, `errors[]`

Person C's `builder.py` accepts this dict and returns `{ "markdown": "...", "html": null }` (HTML optional later).

### `/report` while job is running

Implementation uses **HTTP 202** with `{ job_id, status, progress, error, result }` for `pending` / `running` so clients can poll without treating not-ready as an error. (Some docs mention 404; **202 is the chosen behavior** — keep frontend polling until `GET /status` reports `completed` or `failed`.)
