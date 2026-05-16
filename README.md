# Evidentia / ScholarCounter
Hackathon information: https://www.shortesthack.com/

Hack-a-Claw Cloud Track — academic paper counter-analysis agent.

Brief abstract:
An academic paper "counterer". That is, a tool to which academic researchers can input drafts of their papers, with the purpose of having the agent check its sources, research the subject, and:
-check whether the sources on which the researcher bases its arguments are outdated/have been rendered obsolete by new research
-research papers in the field holding the oppposite opinions to those of the researcher
-craft reports with counterarguments to the statements in the paper, with references to the sources on which it bases these counterarguments
-Grading the sourcing quality of the paper, both on the quality of the sources themselves and the extent of the coverage of the paper's arguments by the sources.
-Grading the quality of the data gathered by the researcher themselves, comparing it to similar data gatherings/experiments on other papers
-Offer further sources supporting the researcher's positions.

## Team lanes

- **Person A:** `backend/agents/`, tools orchestration (NemoClaw)
- **Person B:** `backend/main.py`, `backend/tools/`, `backend/utils/` — tool contracts: [backend/tools/TOOLS.md](backend/tools/TOOLS.md)
- **Person C:** `backend/report/`, `frontend/` — see [frontend/README.md](frontend/README.md)

## Backend API (Person B)

On Linux or Brev, from the repo root: `chmod +x deploy.sh && ./deploy.sh`. That installs dependencies from `requirements.txt` and runs `uvicorn` on **0.0.0.0:8000**. Copy [`.env.example`](.env.example) to `.env` and set values such as `UNPAYWALL_EMAIL` before calling Unpaywall-backed paths. For the static UI to call this API, Person C sets `window.SCHOLAR_COUNTER_API` in [`frontend/config.js`](frontend/config.js) to the reachable base URL (for example `http://localhost:8000` locally or `http://YOUR-BREV-HOST:8000` on the instance), then serves the repo with `python -m http.server 8080` and opens `/frontend/` as in [frontend/README.md](frontend/README.md).

## Quick demo (Person C)

```powershell
cd evidentia
python backend/report/builder.py
python -m http.server 8080
```

→ http://localhost:8080/frontend/?demo=1
