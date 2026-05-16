# Roadmap for Evidentia implementation
Here's the full roadmap for ScholarCounter, a 24-hour build for the Hack-a-Claw Cloud Track.

Project: ScholarCounter
Stack overview
Based on the hackathon specs, your Cloud Track stack is:
Teams on the Cloud Track build on fully sponsored cloud compute instances via Brev.dev. The core runtime is NemoClaw — NVIDIA's open-source stack enabling secure, on-premises (or cloud) deployment of autonomous AI assistants using Nemotron models, orchestrated via OpenShell for sandboxed execution and tool integration. UcscNVIDIA
For the model brain: Nemotron 3 Super is a 120B total / 12B active-parameter hybrid Mamba-Transformer MoE model built for agentic reasoning, with a 1M-token native context window and multi-token prediction that delivers 2–3x wall-clock speedup on structured generation like tool calls. You'll pair it with Nemotron Nano for cheaper fast tasks. The NemoClaw model router can select between Nano and Super based on a tolerance threshold — 0.0 always picks the most accurate model, 1.0 always picks the cheapest, and 0.20 (default) allows up to 20 percentage points below the best for a cheaper model. NVIDIAGitHub

File structure
scholarcounter/
├── README.md
├── .env                          # NVIDIA_INTEGRATE_API_KEY, etc.
├── nemoclaw/
│   ├── policy.yaml               # OpenShell network egress policy
│   └── sandbox-config.json       # NemoClaw sandbox definition
├── backend/
│   ├── main.py                   # FastAPI app entry point
│   ├── agents/
│   │   ├── orchestrator.py       # Routes tasks to sub-agents
│   │   ├── source_checker.py     # Validates/dates citations
│   │   ├── counter_researcher.py # Finds opposing papers
│   │   └── grader.py             # Scores sourcing + data quality
│   ├── tools/
│   │   ├── semantic_scholar.py   # Semantic Scholar API wrapper
│   │   ├── crossref.py           # Crossref DOI + metadata
│   │   ├── openalex.py           # OpenAlex free academic graph
│   │   └── arxiv.py              # arXiv search wrapper
│   ├── memory/
│   │   └── context_store.py      # In-session agent memory (SOUL.md pattern)
│   ├── report/
│   │   └── builder.py            # Assembles final report markdown
│   └── utils/
│       ├── pdf_parser.py         # Extract text + references from PDF
│       └── citation_extractor.py # Parse reference list into structured data
├── frontend/
│   ├── index.html
│   ├── app.js                    # Upload + streaming report display
│   └── styles.css
└── deploy.sh                     # One-command Brev deploy script

Phases of development
Phase 0 — Setup (Hour 0–1, all 3 people together)
Before splitting, spend 1 hour as a group:

Spin up the Brev instance. Use openshell sandbox create --name openclaw-nvidia --from sandboxes/openclaw-nvidia --forward 18789 with your NVIDIA_INTEGRATE_API_KEY. Ajeet Singh Raina
Confirm the NemoClaw gateway, policy proxy, and Nemotron inference endpoint are reachable.
Create the repo, share credentials in .env, agree on the API contracts between agents (input/output JSON schemas).
Write the policy.yaml to whitelist the external academic APIs you'll call (Semantic Scholar, Crossref, OpenAlex, arXiv).


Parallel workstreams (Hours 1–18)
Person A — Agent core & orchestrator
Responsibility: The NemoClaw agentic brain. Owns agents/, tools/, memory/.
Steps:

Hour 1–3: Build orchestrator.py. This is the main OpenClaw loop — it receives a structured representation of the paper (claims + references list), then fans out tasks to the three sub-agents. Use Nemotron Super for orchestration reasoning (needs to understand argument structure), Nemotron Nano for simple dispatch decisions.
Hour 3–6: Build source_checker.py. Given a citation, it calls Crossref (for DOI metadata + publication date), then Semantic Scholar (to check if that paper has been superseded — look at its "cited by" graph for papers that contradict it). Flag sources older than 5 years in a rapidly-changing field.
Hour 6–10: Build counter_researcher.py. Takes the paper's key claims as input, formulates search queries, and calls Semantic Scholar + OpenAlex to find papers with opposing conclusions. This agent needs Nemotron Super — it must reason about semantic similarity between claims and paper abstracts.
Hour 10–14: Build grader.py. Two scoring functions: (a) source quality score — journal impact, recency, citation count; (b) coverage score — what fraction of the paper's claims are actually backed by a cited source. Use Nemotron Nano for the scoring math, Super only for the coverage reasoning.
Hour 14–18: Integration testing. Make sure agents share memory properly (the orchestrator needs to pass context between agents so the grader knows what the source checker found). Wire up the context_store.py using OpenClaw's persistent workspace files.

Key tools: NemoClaw OpenShell SDK, Nemotron API (integrate.api.nvidia.com), Semantic Scholar API (free), Crossref REST API (free), OpenAlex API (free, no key needed).

Person B — Data ingestion & academic API layer
Responsibility: Everything below the agents. Owns tools/, utils/, backend/main.py.
Steps:

Hour 1–3: Build pdf_parser.py. Use PyMuPDF (fitz) to extract full text and the reference section. Build citation_extractor.py to parse references into structured dicts: {authors, title, year, doi, journal}. Use a regex + heuristic approach first; if time allows, run a Nemotron Nano call to clean up malformed references.
Hour 3–6: Build semantic_scholar.py and crossref.py. Semantic Scholar's Graph API lets you search by title/DOI and get full citation graphs — this is your primary source for "is this paper outdated?" and "what papers oppose this?". Crossref gives you clean metadata by DOI. Both are free with no auth.
Hour 6–9: Build openalex.py and arxiv.py. OpenAlex is a fully open academic graph — great for field-level coverage. arXiv for preprints (important for fast-moving ML/CS fields). Add basic caching so repeated queries for the same DOI don't re-hit the API.
Hour 9–13: Build main.py (FastAPI). Expose three endpoints: POST /analyze (accepts PDF or text, kicks off orchestrator), GET /status/{job_id} (polling), GET /report/{job_id} (returns finished report). Use background tasks so the frontend can poll while agents run.
Hour 13–18: Add error handling, rate limit retries, and make sure the tool wrappers properly surface errors back to the orchestrator (agents need to know when an API call failed vs. returned no results — different recovery strategies).

Key tools: PyMuPDF, FastAPI, httpx (async HTTP), Semantic Scholar API, Crossref, OpenAlex, arXiv API.

Person C — Report builder & frontend
Responsibility: The output layer and UI. Owns report/, frontend/.
Steps:

Hour 1–3: Design the report schema. Define exactly what builder.py will receive from the orchestrator (JSON with: claims list, per-claim counterarguments, source grades, data quality scores, supporting sources). Mock this with fake data so you can build the frontend without waiting for the agents.
Hour 3–7: Build builder.py. Takes the agent outputs and renders a structured markdown report with sections: (1) Executive summary, (2) Source quality grades per citation, (3) Counterargument section per claim, (4) Data quality comparison, (5) Supporting sources. Use Nemotron Nano to write clean prose transitions between sections.
Hour 7–12: Build the frontend (index.html, app.js). Key interactions: file upload (PDF or paste text), a progress indicator that shows which agent is running, and a rendered report view. Use Server-Sent Events or polling against /status/{job_id}. Keep it functional — this is a hackathon, not a design sprint. A clean split-pane (input left, report right) is enough.
Hour 12–16: Add the grading visualization. Two simple bar/gauge components: one for source quality (per citation, color-coded red/yellow/green), one for overall coverage score. These are the most demo-able outputs — judges will look at them immediately.
Hour 16–18: Polish and integration. Connect real agent output to the report builder. Make sure the report renders end-to-end with a real paper.

Key tools: Jinja2 or plain f-strings for report templating, Marked.js (frontend markdown rendering), vanilla JS for polling, CSS for the split-pane layout.

Final sprint (Hours 18–23)
All three together:

Hour 18–20: End-to-end test with a real paper (grab a short arXiv paper). Fix whatever breaks.
Hour 20–22: Record a 2-minute demo video. Show: upload paper → agents running → report with grades and counterarguments.
Hour 22–23: Write the submission README. Make sure your deploy.sh works on a fresh Brev instance.


Resources & tools summary
LayerToolWhyCloud computeBrev.devSponsored GPU instance, one-command NemoClaw deployAgent runtimeNemoClaw + OpenShellSandboxed execution, policy-based egress, audit trailPrimary modelNemotron 3 Super 120BDeep claim reasoning, semantic search, argument analysisFast/cheap modelNemotron 3 Nano 30BScoring, formatting, simple dispatchPDF parsingPyMuPDF (fitz)Fast, accurate text + reference extractionAcademic API 1Semantic Scholar Graph APICitation graphs, recency, opposing papersAcademic API 2Crossref REST APIDOI metadata, publication datesAcademic API 3OpenAlexOpen academic graph, field coverageAcademic API 4arXiv APIPreprint search (CS/ML fields)BackendFastAPIAsync API, background jobsFrontendVanilla HTML/JSFast to build, no framework overhead
