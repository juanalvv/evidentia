from backend.agents.orchestrator import Orchestrator, blocked_action_stub
from backend.agents.model_router import ModelRouter
from backend.agents.schemas import InputPayload, Claim, Citation
from backend.memory.context_store import ContextStore
from backend.tools.stubs import CrossrefStub, SemanticScholarStub, OpenAlexStub, LLMStub

router = ModelRouter(super_model="nemotron-super", nano_model="nemotron-nano")
context = ContextStore(workspace_root="/tmp/openclaw")
tools = {
    "crossref": CrossrefStub(title="Stubbed Title", year=2019),
    "semantic_scholar": SemanticScholarStub(contradiction_signals=["contradiction_flag"]),
    "openalex": OpenAlexStub(opposing_papers=[]),
    "llm": LLMStub(),
}

payload = InputPayload(
    submission_id="demo-1",
    claims=[Claim(claim_id="c1", text="Claim text here")],
    citations=[Citation(citation_id="s1", raw_text="Doe 2020", title="Sample Paper", year=2020)],
)

orch = Orchestrator(router, tools, context, blocked_action_cb=blocked_action_stub)
result = orch.run(payload)
print(result.model_dump())