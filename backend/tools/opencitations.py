import asyncio
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from backend.tools.cache import cache, make_cache_key
from backend.tools.http_client import request_get

OPENCITATIONS_BASE_URL = "https://api.opencitations.net/index/v1"


def _normalize_record(record: Dict[str, Any], relation: str) -> Dict[str, Any]:
    return {
        "id": record.get("oci") or record.get("id"),
        "relation": relation,
        "citing": record.get("citing"),
        "cited": record.get("cited"),
        "creation": record.get("creation"),
        "timespan": record.get("timespan"),
        "publication_year": record.get("publication_year"),
        "metadata": record.get("metadata"),
        "source": "opencitations",
    }


def _build_url(doi: str, relation: str) -> str:
    encoded_doi = urllib.parse.quote(doi.strip(), safe="/")
    if relation == "references":
        return f"{OPENCITATIONS_BASE_URL}/references/{encoded_doi}"
    if relation == "citations":
        return f"{OPENCITATIONS_BASE_URL}/citations/{encoded_doi}"
    raise ValueError(f"Unsupported relation: {relation}")


async def _fetch_relation(
    doi: str,
    relation: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    cache_key = make_cache_key("opencitations", relation, doi.lower())

    async def fetch() -> Dict[str, Any]:
        url = _build_url(doi, relation)

        response = await request_get(url, client=client)

        if response.status_code == 404:
            return {"success": False, "error": "not_found", "doi": doi, "relation": relation, "details": response.text}
        if response.status_code == 429:
            return {"success": False, "error": "rate_limited", "doi": doi, "relation": relation, "details": response.text}

        try:
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            return {"success": False, "error": "http_error", "doi": doi, "relation": relation, "details": str(exc)}
        except ValueError as exc:
            return {"success": False, "error": "parse_error", "doi": doi, "relation": relation, "details": str(exc)}

        if not isinstance(payload, list):
            return {"success": False, "error": "parse_error", "doi": doi, "relation": relation, "details": "Unexpected response format"}

        normalized = [_normalize_record(item, relation) for item in payload if isinstance(item, dict)]
        return {
            "success": True,
            "doi": doi,
            "relation": relation,
            "count": len(normalized),
            "data": normalized,
        }

    return await cache.memoize(cache_key, fetch, ttl=3600)


async def fetch_opencitations_references(
    doi: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Fetch outgoing references for a paper from OpenCitations."""
    return await _fetch_relation(doi, "references", client=client)


async def fetch_opencitations_citations(
    doi: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Fetch incoming citations for a paper from OpenCitations."""
    return await _fetch_relation(doi, "citations", client=client)


async def fetch_opencitations_by_doi(
    doi: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Fetch both references and citations for a DOI from OpenCitations."""
    references, citations = await asyncio.gather(
        fetch_opencitations_references(doi, client=client),
        fetch_opencitations_citations(doi, client=client),
    )

    return {
        "success": references.get("success") is True and citations.get("success") is True,
        "doi": doi,
        "references": references,
        "citations": citations,
    }


if __name__ == "__main__":
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="OpenCitations API wrapper.")
    parser.add_argument("action", choices=["references", "citations", "both"], help="Action to perform")
    parser.add_argument("doi", help="DOI to query")
    args = parser.parse_args()

    async def main() -> None:
        if args.action == "references":
            result = await fetch_opencitations_references(args.doi)
        elif args.action == "citations":
            result = await fetch_opencitations_citations(args.doi)
        else:
            result = await fetch_opencitations_by_doi(args.doi)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    asyncio.run(main())