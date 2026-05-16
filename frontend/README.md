# Person C — Frontend & report

## Start now (no backend)

From repo root `evidentia/`:

```powershell
python -m http.server 8080
```

Open: http://localhost:8080/frontend/?demo=1  
Or click **Load demo report** (needs the server so `fetch` can load fixtures).

Regenerate demo markdown after editing the JSON contract:

```powershell
python backend/report/builder.py
```

## Your deliverables

| File | Purpose |
|------|---------|
| `backend/report/CONTRACT.md` | JSON schema for Person A/B — **share this in Slack now** |
| `backend/report/fixtures/mock_analysis.json` | Mock orchestrator output |
| `backend/report/builder.py` | Markdown report from JSON |
| `frontend/*` | UI, gauges, polling |

## When Person B has FastAPI

Set in `frontend/config.js`:

```js
window.EVIDENTIA_API = "http://YOUR-BREV-HOST:8000";
```

Endpoints: `POST /analyze`, `GET /status/{id}`, `GET /report/{id}` — see CONTRACT.md.

Person B should call `build_report()` and include `markdown` in the report response (or expose `POST /report/build`).

## Demo URL for judges

Serve `frontend/` + API on Brev; use `?demo=1` as fallback if live analyze fails.
