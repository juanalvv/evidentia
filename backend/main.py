import sys
import os
import asyncio
import json
from datetime import datetime, timezone
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
                title="Attention Is All You Need",
                doi="10.48550/arXiv.1706.03762",
                year=2017
            ),
            Citation(
                citation_id="s2",
                raw_text="Wei et al. (2022). Emergent Abilities of Large Language Models. Transactions on Machine Learning Research.",
                title="Emergent Abilities of Large Language Models",
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
            print(f"- Claim {ca.claim_id}: {ca.summary}")
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

        report_payload = _build_frontend_payload(payload, output)
        print("\n[Frontend Payload Debug]")
        print(json.dumps(report_payload, indent=2))

    except Exception as e:
        print(f"Pipeline crashed: {e}")
        import traceback
        traceback.print_exc()

def _build_frontend_payload(payload: InputPayload, output: Any) -> Dict[str, Any]:
    now_iso = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    metadata = payload.metadata or {}
    paper = {
        "title": metadata.get("title") or "Untitled",
        "authors": metadata.get("authors") or [],
        "uploaded_at": now_iso,
    }

    source_checks = output.source_checks or []
    scores = output.grader.source_quality if output.grader else []
    scores_by_id = {score.citation_id: score.score for score in scores}
    checks_by_id = {check.citation_id: check for check in source_checks}

    citations = []
    for citation in payload.citations:
        check = checks_by_id.get(citation.citation_id)
        year = citation.year or (check.publication_year if check else None)
        citations.append(
            {
                "id": citation.citation_id,
                "authors": _format_authors(citation.authors),
                "title": citation.title or (check.normalized_title if check else None) or "Untitled",
                "year": year,
                "doi": citation.doi or (check.normalized_doi if check else None),
                "journal": citation.journal,
                "source_quality_score": scores_by_id.get(citation.citation_id),
                "recency_flag": _recency_flag(check.is_outdated if check else None, year),
                "superseded_notes": None,
                "superseded_by": [],
            }
        )

    coverage = output.grader.coverage if output.grader else None
    coverage_score = coverage.score if coverage else None
    claims_backed = set(coverage.claims_backed if coverage else [])
    claims_unbacked = set(coverage.claims_unbacked if coverage else [])

    counter_by_claim = {}
    for item in output.counterarguments or []:
        papers = []
        for counter_paper in item.papers or []:
            papers.append(
                {
                    "title": counter_paper.title,
                    "authors": _format_authors(getattr(counter_paper, "authors", None)),
                    "year": counter_paper.year,
                    "doi": getattr(counter_paper, "doi", None),
                    "url": counter_paper.url,
                    "relevance": _format_relevance(counter_paper.relevance_score),
                }
            )
        counter_by_claim[item.claim_id] = [
            {
                "summary": item.summary,
                "papers": papers,
            }
        ]

    claims = []
    for claim in payload.claims:
        claims.append(
            {
                "id": claim.claim_id,
                "text": claim.text,
                "section": "Claim",
                "cited_source_ids": [],
                "coverage_score": _claim_coverage(claim.claim_id, claims_backed, claims_unbacked, coverage_score),
                "counterarguments": counter_by_claim.get(claim.claim_id, []),
                "supporting_sources": [],
            }
        )

    source_quality = _average_score([score.score for score in scores])
    data_quality_score = None
    overall_scores = {
        "source_quality": source_quality,
        "coverage": coverage_score,
        "data_quality": data_quality_score,
    }

    return {
        "job_id": payload.submission_id,
        "status": "completed",
        "paper": paper,
        "progress": {
            "phase": "done",
            "percent": 100,
            "message": "Analysis complete",
            "agent": "orchestrator",
        },
        "executive_summary": _build_summary(overall_scores),
        "overall_scores": overall_scores,
        "citations": citations,
        "claims": claims,
        "data_quality": {
            "score": data_quality_score,
            "summary": "Data quality scoring not available yet.",
            "comparisons": [],
        },
        "final_verdict": _build_verdict(overall_scores),
        "errors": [err.model_dump() for err in output.errors] if output.errors else [],
    }


def _average_score(values: List[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _format_authors(authors: Any) -> str:
    if not authors:
        return ""
    if isinstance(authors, list):
        return ", ".join(str(item) for item in authors if item)
    return str(authors)


def _recency_flag(is_outdated: bool | None, year: int | None) -> str:
    if is_outdated is True:
        return "stale"
    if year and (datetime.now(timezone.utc).year - year) <= 2:
        return "recent"
    return "ok"


def _claim_coverage(
    claim_id: str,
    backed: set[str],
    unbacked: set[str],
    fallback: float | None,
) -> float | None:
    if claim_id in backed:
        return 1.0
    if claim_id in unbacked:
        return 0.0
    return fallback


def _format_relevance(score: float | None) -> str:
    if score is None:
        return ""
    return f"score: {score:.2f}"


def _build_summary(scores: Dict[str, Any]) -> str:
    parts = []
    if scores.get("source_quality") is not None:
        parts.append(f"Source quality: {round(scores['source_quality'] * 100)}%.")
    if scores.get("coverage") is not None:
        parts.append(f"Coverage: {round(scores['coverage'] * 100)}%.")
    if scores.get("data_quality") is not None:
        parts.append(f"Data quality: {round(scores['data_quality'] * 100)}%.")
    return " ".join(parts) or "Executive summary not available yet."


def _build_verdict(scores: Dict[str, Any]) -> Dict[str, Any]:
    source_quality = scores.get("source_quality")
    coverage = scores.get("coverage")
    data_quality = scores.get("data_quality")

    if source_quality is not None and source_quality < 0.4:
        status = "Needs major evidence work"
    elif coverage is not None and coverage < 0.4:
        status = "Needs major evidence work"
    elif source_quality is not None and source_quality < 0.6:
        status = "Needs citation revision"
    elif coverage is not None and coverage < 0.6:
        status = "Needs citation revision"
    else:
        status = "Ready to submit"

    rationale = []
    if source_quality is not None:
        rationale.append(f"Source quality score is {round(source_quality * 100)}%.")
    if coverage is not None:
        rationale.append(f"Coverage score is {round(coverage * 100)}%.")
    if data_quality is not None:
        rationale.append(f"Data quality score is {round(data_quality * 100)}%.")

    next_steps = [
        "Review unsupported claims and add stronger citations.",
        "Refresh outdated sources with recent peer-reviewed work.",
        "Expand evidence for key claims before submission.",
    ]

    return {
        "status": status,
        "summary": "Auto-generated verdict based on current scores.",
        "rationale": rationale,
        "next_steps": next_steps,
    }


if __name__ == "__main__":
    asyncio.run(main())
