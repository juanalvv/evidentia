# Evidentia

![EvidentIA UI](docs/screenshot.png)

> Built at the **NVIDIA × ASUS Hack-a-Claw Hackathon** hosted at UCSC.

Evidentia is an agentic AI tool that helps academic researchers stress-test their work before publication. Researchers submit a draft paper and Evidentia autonomously analyses it, returning a structured critical report.

## What it does

- **Counter-argument discovery** — finds papers in the field that argue against the researcher's conclusions, with direct citations.
- **Source validation** — checks whether the sources cited in the paper are still current or have been superseded by newer research.
- **Source quality grading** — scores both the individual quality of each cited source and how well the paper's arguments are actually backed by them.
- **Data benchmarking** — compares the researcher's own data against similar experiments and datasets in the literature.
- **Supporting literature** — surfaces additional sources that reinforce the researcher's positions, complementing the critical analysis.

## Tech stack

- **Agent orchestration:** NemoClaw + Nemotron (NVIDIA)
- **Backend:** Python · FastAPI · Uvicorn
- **Frontend:** Vanilla JS / HTML / CSS

## Getting started

### 1. Clone and install

```bash
git clone https://github.com/juanalvv/evidentia.git
cd evidentia
chmod +x deploy.sh && ./deploy.sh
```

This installs all dependencies from `requirements.txt` and starts the API on `0.0.0.0:8000`.

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and set UNPAYWALL_EMAIL and any other required values
```

### 3. Run the frontend

```bash
# In frontend/config.js, set:
# window.SCHOLAR_COUNTER_API = "http://localhost:8000"

python -m http.server 8080
```

Then open [http://localhost:8080/frontend/](http://localhost:8080/frontend/).
