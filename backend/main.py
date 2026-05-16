import sys
import os
import asyncio
from typing import Dict, Any, List

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.agents.orchestrator import Orchestrator, blocked_action_stub
from backend.agents.model_router import ModelRouter
from backend.agents.schemas import InputPayload, Claim, Citation, CounterPaper
from backend.memory.context_store import ContextStore
from backend.tools.crossref import fetch_crossref_metadata
from backend.tools.openalex import search_openalex
from backend.tools.llm import LLMClient
from backend.tools.stubs import SemanticScholarStub

class CrossrefAdapter:
    async def lookup_doi(self, doi: str) -> Dict[str, Any]:
        print(f"  [Tools] Querying Crossref for DOI: {doi}")
        try:
            result = await fetch_crossref_metadata(doi)
            if result.get("success"):
                return result["data"]
        except Exception as e:
            print(f"  [Tools] Crossref error: {e}")
        return {}

class OpenAlexAdapter:
    async def search_opposing(self, query: str) -> List[CounterPaper]:
        print(f"  [Tools] Querying OpenAlex for: {query}")
        try:
            result = await search_openalex(query)
            if result.get("success"):
                papers = []
                for p in result["data"]:
                    papers.append(CounterPaper(
                        paper_id=p["id"],
                        title=p["title"],
                        year=p["year"],
                        venue=p["venue"],
                        url=p["url"]
                    ))
                return papers
        except Exception as e:
            print(f"  [Tools] OpenAlex error: {e}")
        return []

async def main():
    print("=== Evidentia NemoClaw Brain ===")
    
    # 1. Initialize router
    model_name = "nvidia/nemotron-3-super-120b-a12b"
    router = ModelRouter(
        super_model=model_name,
        nano_model=model_name 
    )
    
    # 2. Initialize context store
    workspace = os.getenv("OPENCLAW_WORKSPACE", "/tmp/openclaw")
    os.makedirs(workspace, exist_ok=True)
    context = ContextStore(workspace_root=workspace)
    
    # 3. Initialize tools with adapters
    tools = {
        "crossref": CrossrefAdapter(),
        "openalex": OpenAlexAdapter(),
        "llm": LLMClient(),
        "semantic_scholar": SemanticScholarStub(
            contradiction_signals=["[Stub] citation graph looks consistent"],
            opposing_papers=[]
        )
    }
    
    # 4. Create sample input
    payload = InputPayload(
        submission_id="test-run-1",
        claims=[
            Claim(claim_id="c1", text="Large language models exhibit emergent abilities that are not present in smaller models."),
            Claim(claim_id="c2", text="The transformer architecture is the most efficient for all sequence modeling tasks.")
        ],
        citations=[
            Citation(
                citation_id="s1",
                raw_text="Vaswani et al. (2017). Attention Is All You Need. Advances in Neural Information Processing Systems.",
                doi="10.48550/arXiv.1706.03762",
                year=2017
            ),
            Citation(
                citation_id="s2",
                raw_text="Wei et al. (2022). Emergent Abilities of Large Language Models. Transactions on Machine Learning Research.",
                doi="10.48550/arXiv.2206.07682",
                year=2022
            )
        ]
    )
    
    # 5. Run orchestrator
    print(f"Running pipeline for submission: {payload.submission_id}...")
    orch = Orchestrator(router, tools, context, blocked_action_cb=blocked_action_stub)
    
    try:
        output = await orch.run(payload)
        
        print("\n=== Pipeline Results ===")
        print(f"Duration: {output.raw.get('duration_seconds')}s")
        
        print("\n[Source Checks]")
        for check in output.source_checks:
            print(f"- {check.citation_id}: {check.normalized_title} ({check.publication_year})")
            print(f"  Outdated: {check.is_outdated}")
            print(f"  Contradictions: {check.contradiction_signals}")

        print("\n[Counter Research]")
        for ca in output.counterarguments:
            print(f"- Claim {ca.claim_id}: {ca.summary[:150]}...")
            print(f"  Opposing papers found: {len(ca.papers)}")

        if output.grader:
            print("\n[Grader Output]")
            if output.grader.coverage:
                print(f"Coverage Score: {output.grader.coverage.score}")
                print(f"Explanation: {output.grader.coverage.explanation}")
            
            print(f"Source Quality Scores: {[f'{s.citation_id}: {s.score}' for s in output.grader.source_quality]}")

        if output.errors:
            print("\n[Errors]")
            for err in output.errors:
                print(f"- {err.agent}: {err.message}")

    except Exception as e:
        print(f"Pipeline crashed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
