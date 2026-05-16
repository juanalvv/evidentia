from __future__ import annotations

from typing import Any, Dict, List

from .model_router import ModelRoute
from .schemas import Claim, CounterArgument, CounterPaper
from ..memory.context_store import ContextStore


def run_counter_research(
    claims: List[Claim],
    tools: Dict[str, Any],
    model_route: ModelRoute,
    context: ContextStore,
) -> List[CounterArgument]:
    semscholar = tools.get("semantic_scholar")
    openalex = tools.get("openalex")
    llm = tools.get("llm")

    results: List[CounterArgument] = []
    for claim in claims:
        query = _build_query(claim.text, llm, model_route)
        papers: List[CounterPaper] = []

        if semscholar:
            papers.extend(semscholar.search_opposing(query))
        if openalex:
            papers.extend(openalex.search_opposing(query))

        summary = _summarize_counterarguments(claim.text, papers, llm, model_route)
        results.append(CounterArgument(claim_id=claim.claim_id, summary=summary, papers=papers))

    context.set("counterarguments", [item.model_dump() for item in results])
    return results


def _build_query(claim_text: str, llm: Any, model_route: ModelRoute) -> str:
    if not llm:
        return claim_text
    prompt = (
        "Generate a concise academic search query for opposing evidence.\n"
        f"Claim: {claim_text}\n"
        "Return query only."
    )
    return llm.complete(prompt=prompt, model=model_route.name, max_tokens=64)


def _summarize_counterarguments(
    claim_text: str,
    papers: List[CounterPaper],
    llm: Any,
    model_route: ModelRoute,
) -> str:
    if not llm or not papers:
        return "No strong counterarguments found in current search results."

    titles = "\n".join(f"- {paper.title}" for paper in papers[:5])
    prompt = (
        "Summarize the key counterargument to the claim using these papers.\n"
        f"Claim: {claim_text}\n"
        f"Papers:\n{titles}\n"
        "Return 3-4 sentences."
    )
    return llm.complete(prompt=prompt, model=model_route.name, max_tokens=256)
