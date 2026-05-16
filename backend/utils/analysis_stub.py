from __future__ import annotations

from typing import Any, Dict, List

from backend.agents.model_router import ModelRouter
from backend.agents.orchestrator import Orchestrator, blocked_action_stub
from backend.agents.schemas import Claim, Citation, InputPayload
from backend.memory.context_store import ContextStore
from backend.report.builder import build_report
from backend.tools.agent_tools import build_agent_tools


async def build_ingestion_analysis_result(
    job_id: str,
    ingest: Dict[str, Any],
    analysis: Dict[str, Any],
    created_at_iso: str,
) -> Dict[str, Any]:
    """Run the Orchestrator pipeline and return a Final AnalysisResult dict."""
    claims_input = ingest.get("claims") or []
    citations_input = ingest.get("citations") or []

    if not claims_input:
        claims_input = [{"claim_id": "c1", "text": "Demo claim: results section asserts strong improvements."}]

    claims = [
        Claim(claim_id=c.get("claim_id") or c.get("id") or f"c{idx+1}", text=c.get("text", ""))
        for idx, c in enumerate(claims_input)
    ]
    citations = [
        Citation(
            citation_id=c.get("citation_id") or c.get("id") or f"cite-{idx+1}",
            raw_text=c.get("raw_text") or c.get("raw") or "",
            title=c.get("title"),
            authors=c.get("authors"),
            year=c.get("year"),
            doi=c.get("doi"),
            journal=c.get("journal"),
        )
        for idx, c in enumerate(citations_input)
    ]

    payload = InputPayload(
        submission_id=job_id,
        claims=claims,
        citations=citations,
        full_text=ingest.get("full_text"),
        metadata=ingest.get("metadata") or {},
    )

    router = ModelRouter(super_model="nemotron-super", nano_model="nemotron-nano")
    context = ContextStore()
    orchestrator = Orchestrator(
        router,
        build_agent_tools(),
        context,
        blocked_action_cb=blocked_action_stub,
    )

    output = await orchestrator.run(payload)

    paper = {
        "title": (payload.metadata or {}).get("title") or (payload.full_text or "")[:120],
        "authors": (payload.metadata or {}).get("authors") or None,
        "uploaded_at": created_at_iso,
    }

    grader = output.grader
    source_quality_scores = []
    if grader and grader.source_quality:
        for s in grader.source_quality:
            source_quality_scores.append(float(s.score))

    overall_source_quality = None
    if source_quality_scores:
        overall_source_quality = sum(source_quality_scores) / len(source_quality_scores)

    coverage_score = grader.coverage.score if (grader and grader.coverage) else None

    citations_out = []
    sc_by_id = {sc.citation_id: sc for sc in output.source_checks}
    score_by_id = {sq.citation_id: float(sq.score) for sq in (grader.source_quality or [])} if grader else {}

    for c in payload.citations:
        sc = sc_by_id.get(c.citation_id)
        year = c.year or (sc.publication_year if sc else None)
        recency = "stale" if (sc and sc.is_outdated) else ("recent" if isinstance(year, int) and (2026 - year) <= 2 else "ok")
        citations_out.append(
            {
                "id": c.citation_id,
                "authors": ", ".join(c.authors) if c.authors else None,
                "title": c.title or (sc.normalized_title if sc else None),
                "year": year,
                "doi": c.doi,
                "journal": c.journal,
                "source_quality_score": score_by_id.get(c.citation_id),
                "recency_flag": recency,
                "superseded_notes": None,
                "superseded_by": [],
            }
        )

    counter_map: Dict[str, List[Dict[str, Any]]] = {}
    for ca in output.counterarguments:
        claim_id = ca.claim_id
        papers = []
        for p in ca.papers:
            papers.append(
                {
                    "title": p.title,
                    "authors": getattr(p, "authors", None),
                    "year": p.year,
                    "doi": None,
                    "url": getattr(p, "url", None),
                    "relevance": getattr(p, "relevance_score", None),
                }
            )
        counter_map.setdefault(claim_id, []).append({"summary": ca.summary, "papers": papers})

    claims_out = []
    for cl in payload.claims:
        claims_out.append(
            {
                "id": cl.claim_id,
                "text": cl.text,
                "section": getattr(cl, "section", ""),
                "cited_source_ids": getattr(cl, "cited_source_ids", []) or [],
                "coverage_score": coverage_score,
                "counterarguments": counter_map.get(cl.claim_id, []),
                "supporting_sources": [],
            }
        )

    data_quality = analysis.get("data_quality") if isinstance(analysis, dict) else None

    agent_errors: List[str] = []
    for err in output.errors:
        if err.message:
            agent_errors.append(f"{err.agent}: {err.message}")

    final = {
        "job_id": job_id,
        "status": "completed",
        "paper": paper,
        "progress": {"phase": "done", "percent": 100, "message": "Analysis complete", "agent": "orchestrator"},
        "executive_summary": analysis.get("executive_summary") or "Automated analysis complete.",
        "overall_scores": {
            "source_quality": overall_source_quality,
            "coverage": coverage_score,
            "data_quality": data_quality.get("score") if isinstance(data_quality, dict) else None,
        },
        "citations": citations_out,
        "claims": claims_out,
        "data_quality": data_quality or {"score": None, "summary": None, "comparisons": []},
        "final_verdict": analysis.get("final_verdict") if isinstance(analysis, dict) else None,
        "errors": agent_errors,
    }

    try:
        final["markdown"] = build_report(final)["markdown"]
    except Exception:
        final["markdown"] = None

    return final


def build_failed_analysis_result(job_id: str, error: str, created_at_iso: str) -> Dict[str, Any]:
    return {
        "job_id": job_id,
        "status": "failed",
        "paper": {"title": None, "authors": None, "uploaded_at": created_at_iso},
        "progress": {"phase": "done", "percent": 100, "message": error, "agent": "orchestrator"},
        "executive_summary": f"Analysis failed: {error}",
        "overall_scores": {"source_quality": None, "coverage": None, "data_quality": None},
        "citations": [],
        "claims": [],
        "data_quality": {"score": None, "summary": None, "comparisons": []},
        "final_verdict": None,
        "markdown": None,
        "errors": [error] if error else ["unknown_error"],
    }
