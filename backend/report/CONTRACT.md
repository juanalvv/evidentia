# ScholarCounter — Report API contract (Person C ↔ A/B)

Person B exposes these endpoints. Person A's orchestrator writes the JSON shape below into job storage; Person C consumes it via `GET /report/{job_id}`.

## Endpoints (Person B)

| Method | Path | Body / response |
|--------|------|-----------------|
| `POST` | `/analyze` | `multipart`: `file` (PDF) **or** `text` (plain). Returns `{ "job_id": "uuid" }` |
| `GET` | `/status/{job_id}` | `{ "status", "progress" }` — see schema |
| `GET` | `/report/{job_id}` | Full `AnalysisResult` when `status === "completed"`; `404` while running |

### `progress` (for UI polling)

```json
{
  "phase": "ingest | source_check | counter_research | grading | report | done",
  "percent": 0,
  "message": "Human-readable step label",
  "agent": "orchestrator | source_checker | counter_researcher | grader"
}
```

## `AnalysisResult` (orchestrator → report builder)

See `fixtures/mock_analysis.json`. Required top-level keys:

- `job_id`, `status`, `paper`, `progress` (final), `executive_summary`
- `overall_scores`: `{ source_quality, coverage, data_quality }` — floats `0..1`
- `citations[]`, `claims[]`, `data_quality`
- Optional: `errors[]` for partial failures

Person C's `builder.py` accepts this dict and returns `{ "markdown": "...", "html": null }` (HTML optional later).
