import httpx
from typing import Any, Dict, Optional

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


async def enrich_doi(
    doi: str,
    email: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Combine metadata, citation graph, and OA lookup for a DOI."""
    metadata = await fetch_doi_metadata(doi, client=client)
    citations = await fetch_opencitations_by_doi(doi, client=client)
    oa = await fetch_unpaywall_by_doi(doi, email=email, client=client)

    partial = {"metadata": metadata, "citations": citations, "oa": oa}

    return {
        "success": any(part.get("success") for part in partial.values()),
        "doi": doi,
        "metadata": metadata,
        "citations": citations,
        "oa": oa,
        "partial_errors": summarize_partial_errors(partial),
    }
