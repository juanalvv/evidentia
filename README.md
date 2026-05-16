# Evidentia / ScholarCounter

Hack-a-Claw Cloud Track — academic paper counter-analysis agent.

## Team lanes

- **Person A:** `backend/agents/`, tools orchestration (NemoClaw)
- **Person B:** `backend/main.py`, `backend/tools/`, `backend/utils/`
- **Person C:** `backend/report/`, `frontend/` — see [frontend/README.md](frontend/README.md)

## Quick demo (Person C)

```powershell
cd evidentia
python backend/report/builder.py
python -m http.server 8080
```

→ http://localhost:8080/frontend/?demo=1
