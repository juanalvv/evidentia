# ScholarCounter - Person A Plan

Deliver the NemoClaw agentic core: schemas, orchestrator, sub-agents, memory handoff, manual model routing (Super vs Nano), and audit/blocked-action evidence. Use the fastest NemoClaw integration path validated by a quick spike, then build the pipeline that consumes Person B's tool wrappers and outputs Person C's report schema.

## Steps

### Phase A0 - Fastest NemoClaw integration spike
1. Validate quickest runtime entrypoint (gateway HTTP API vs Python SDK).
2. Run a minimal agent that calls a stub tool and confirms policy/audit logs.
3. Confirm Nemotron endpoints are reachable inside the sandbox and allowed by policy.

Status: not started (needs NemoClaw runtime validation).

### Phase A1 - Schema contract (Person A owned)
1. Define JSON schemas for input, per-agent outputs, and orchestrator output.
2. Align with Person B tool wrapper formats and Person C report inputs.

Status: implemented and verified via `test.py` output; schemas compile and serialize.

### Phase A2 - Orchestrator core
1. Implement manual model routing (Super for reasoning, Nano for cheap scoring/formatting).
2. Build orchestration flow: parse inputs, call sub-agents, aggregate outputs.
3. Add resilience: per-agent timeouts, fallback on tool errors, partial-result output.

Status: implemented and verified with stub tools (no errors, audit event appended).

### Phase A3 - Source checker agent
1. Normalize citations and determine recency via Crossref metadata.
2. Use Semantic Scholar citation graph to flag outdated/contradicted sources.
3. Emit structured flags and evidence snippets for grading/reporting.

Status: stub logic implemented; real tool wrappers not wired yet.

### Phase A4 - Counter researcher agent
1. Generate claim-specific queries with Nemotron Super.
2. Query Semantic Scholar + OpenAlex; rank opposing papers.
3. Produce concise counterargument summaries per claim.

Status: stub logic implemented; real tool wrappers not wired yet.

### Phase A5 - Grader agent
1. Define scoring rubric (recency, citation count, venue proxy).
2. Compute coverage score (claims backed by citations) with confidence notes.
3. Use Nano for scoring math and Super for coverage reasoning text.

Status: baseline rubric + fallback scoring implemented; LLM scoring expects tool wiring.

### Phase A6 - Memory and context store
1. Implement persistent context store backed by OpenClaw workspace files.
2. Enforce a shared schema for agent read/write.

Status: context store implemented and exercised in `test.py`.

### Phase A7 - Audit logs + blocked-action demo
1. Add a controlled forbidden action inside the agent flow.
2. Capture and summarize policy denial in orchestrator output.

Status: blocked-action stub implemented and verified in `test.py` output.

### Phase A8 - Integration testing
1. End-to-end run with Person B tools and Person C report schema.
2. Validate error paths: missing citations, empty results, rate limits.

Status: pending (needs tool wrappers and report schema wiring).

## Verification
1. Minimal orchestrator run verified with stub tools and blocked-action event.
2. Sample claim produces source checks, counter research summary, and grading output.
3. Model routing in place (Super for reasoning, Nano for scoring).
4. Tool failure handling not verified yet (requires tool wrappers).

## Decisions
- Manual model selection in the orchestrator (no NemoClaw model router).
- Person A defines JSON schemas across agents and report builder.
- Blocked-action demo is part of the agent flow.

## Further Considerations
1. Lock the fastest NemoClaw integration (gateway REST vs Python SDK) after a quick spike.
2. Decide how to infer "superseded" if Semantic Scholar lacks explicit contradiction signals.
3. Ensure policy whitelist includes all academic APIs and Nemotron endpoints.
