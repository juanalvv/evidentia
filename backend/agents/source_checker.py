from __future__ import annotations

from typing import Any, Dict, List

from .model_router import ModelRoute
from .schemas import Citation, SourceCheck
from ..memory.context_store import ContextStore


def run_source_check(
    citations: List[Citation],
    tools: Dict[str, Any],
    model_route: ModelRoute,
    context: ContextStore,
) -> List[SourceCheck]:
    """Validate citations and detect outdated or contradicted sources."""

    crossref = tools.get("crossref")
    semscholar = tools.get("semantic_scholar")

    results: List[SourceCheck] = []
    for citation in citations:
        check = SourceCheck(citation_id=citation.citation_id)

        if crossref and citation.doi:
            meta = crossref.lookup_doi(citation.doi)
            check.normalized_title = meta.get("title")
            check.publication_year = meta.get("year")
            check.normalized_doi = meta.get("doi")

        if semscholar:
            signals = semscholar.find_contradiction_signals(
                title=check.normalized_title or citation.title,
                doi=check.normalized_doi or citation.doi,
            )
            check.contradiction_signals = signals
            if signals:
                check.evidence.append("Contradiction signals found in citation graph")

        if check.publication_year:
            check.is_outdated = _is_outdated(check.publication_year)

        results.append(check)

    context.set("source_checks", [item.model_dump() for item in results])
    return results


def _is_outdated(publication_year: int, cutoff_years: int = 5) -> bool:
    current_year = 2026
    return current_year - publication_year >= cutoff_years
