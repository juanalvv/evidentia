import asyncio
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

import httpx

from backend.tools.crossref import fetch_crossref_metadata
from backend.tools.errors import METADATA_NOT_FOUND, summarize_partial_errors
from backend.tools.openalex import fetch_openalex_by_doi
from backend.tools.opencitations import fetch_opencitations_by_doi
from backend.tools.unpaywall import fetch_unpaywall_by_doi


async def fetch_doi_metadata(
    doi: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Lookup DOI metadata using Crossref first, then fallback to OpenAlex."""
    crossref_result = await fetch_crossref_metadata(doi, client=client)
    if crossref_result.get("success"):
        return {"success": True, "source": "crossref", "data": crossref_result["data"]}

    openalex_result = await fetch_openalex_by_doi(doi, client=client)
    if openalex_result.get("success"):
        return {"success": True, "source": "openalex", "data": openalex_result["data"]}

    return {
        "success": False,
        "error": METADATA_NOT_FOUND,
        "doi": doi,
        "sources": {
            "crossref": crossref_result,
            "openalex": openalex_result,
        },
    }


T = TypeVar("T")


async def _safe_enrichment_call(
    fetcher: Callable[[], Awaitable[T]],
    label: str,
) -> Any:
    """Run an enrichment fetcher; return a structured error dict instead of raising on HTTP failures."""
    try:
        return await fetcher()
    except httpx.TimeoutException as exc:
        return {
            "success": False,
            "error": "timeout",
            "source": label,
            "details": str(exc) or "request timed out",
        }
    except httpx.HTTPError as exc:
        return {
            "success": False,
            "error": "http_error",
            "source": label,
            "details": str(exc) or type(exc).__name__,
        }


async def enrich_doi(
    doi: str,
    email: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Combine metadata, citation graph, and OA lookup for a DOI."""
    metadata, citations, oa = await asyncio.gather(
        _safe_enrichment_call(lambda: fetch_doi_metadata(doi, client=client), "metadata"),
        _safe_enrichment_call(lambda: fetch_opencitations_by_doi(doi, client=client), "opencitations"),
        _safe_enrichment_call(lambda: fetch_unpaywall_by_doi(doi, email=email, client=client), "unpaywall"),
    )

    partial = {"metadata": metadata, "citations": citations, "oa": oa}

    return {
        "success": any(part.get("success") for part in partial.values()),
        "doi": doi,
        "metadata": metadata,
        "citations": citations,
        "oa": oa,
        "partial_errors": summarize_partial_errors(partial),
    }
