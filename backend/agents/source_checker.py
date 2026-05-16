from __future__ import annotations

from typing import Any, Dict, List, Optional

from .model_router import ModelRoute
from .schemas import AgentError, Citation, SourceCheck
from ..memory.context_store import ContextStore


async def run_source_check(
    citations: List[Citation],
    tools: Dict[str, Any],
    model_route: ModelRoute,
    context: ContextStore,
    error_sink: Optional[List[AgentError]] = None,
) -> List[SourceCheck]:
    """Validate citations and detect outdated or contradicted sources."""

    crossref = tools.get("crossref")
    semscholar = tools.get("semantic_scholar")

    results: List[SourceCheck] = []
    for citation in citations:
        check = SourceCheck(citation_id=citation.citation_id)

        if crossref and citation.doi:
            meta = await crossref.lookup_doi(citation.doi)
            meta = _unwrap_tool_metadata(meta, "crossref", error_sink)
            check.normalized_title = meta.get("title") or citation.title
            check.publication_year = meta.get("year") or citation.year
            check.normalized_doi = meta.get("doi") or citation.doi
        else:
            check.normalized_title = citation.title
            check.publication_year = citation.year
            check.normalized_doi = citation.doi

        if semscholar:
            signals = await semscholar.find_contradiction_signals(
                title=check.normalized_title or citation.title,
                doi=check.normalized_doi or citation.doi,
            )
            signals = _unwrap_tool_list(signals, "semantic_scholar", error_sink)
            check.contradiction_signals = signals
            if signals:
                check.evidence.append("Contradiction signals found in citation graph")

        if check.publication_year:
            check.is_outdated = _is_outdated(check.publication_year)

        results.append(check)

    context.set("source_checks", [item.model_dump() for item in results])
    return results


def _record_error(
    error_sink: Optional[List[AgentError]],
    tool_name: str,
    error_code: Optional[str],
    details: Any,
) -> None:
    if error_sink is None or not error_code:
        return
    if error_code == "not_found":
        return
    error_sink.append(
        AgentError(
            agent="source_checker",
            message=f"{tool_name} error: {error_code}",
            details={"error": error_code, "details": details},
        )
    )


def _unwrap_tool_metadata(
    result: Any,
    tool_name: str,
    error_sink: Optional[List[AgentError]],
) -> Dict[str, Any]:
    if isinstance(result, dict) and "success" in result:
        if result.get("success") is True:
            return result.get("data") or {}
        _record_error(error_sink, tool_name, result.get("error"), result.get("details"))
        return {}
    return result if isinstance(result, dict) else {}


def _unwrap_tool_list(
    result: Any,
    tool_name: str,
    error_sink: Optional[List[AgentError]],
) -> List[str]:
    if isinstance(result, dict) and "success" in result:
        if result.get("success") is True:
            data = result.get("data")
            return list(data) if isinstance(data, list) else []
        _record_error(error_sink, tool_name, result.get("error"), result.get("details"))
        return []
    return list(result) if isinstance(result, list) else []


def _is_outdated(publication_year: int, cutoff_years: int = 5) -> bool:
    current_year = 2026
    return current_year - publication_year >= cutoff_years
