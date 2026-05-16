import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from backend.tools.http_client import http_client

OPENALEX_BASE_URL = "https://api.openalex.org"
OPENALEX_WORKS_ENDPOINT = f"{OPENALEX_BASE_URL}/works"


def _normalize_authors(authorships: Any) -> Optional[List[str]]:
    if not isinstance(authorships, list):
        return None
    authors: List[str] = []
    for authorship in authorships:
        if not isinstance(authorship, dict):
            continue
        author = authorship.get("author")
        if not isinstance(author, dict):
            continue
        display_name = author.get("display_name")
        if isinstance(display_name, str) and display_name.strip():
            authors.append(display_name.strip())
    return authors if authors else None


def _normalize_openalex_work(work: Dict[str, Any]) -> Dict[str, Any]:
    doi = work.get("doi")
    if isinstance(doi, str):
        doi = doi.strip().lower()
        if doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
    primary_location = work.get("primary_location")
    location_url = None
    if isinstance(primary_location, dict):
        source = primary_location.get("source")
        if isinstance(source, dict):
            location_url = source.get("url")

    venue = None
    publisher = None
    host_venue = work.get("host_venue")
    if isinstance(host_venue, dict):
        venue = host_venue.get("display_name")
        publisher = host_venue.get("publisher")

    return {
        "id": work.get("id"),
        "doi": doi,
        "title": work.get("display_name"),
        "authors": _normalize_authors(work.get("authorships")),
        "year": work.get("publication_year"),
        "venue": venue,
        "publisher": publisher,
        "citationCount": work.get("cited_by_count"),
        "url": location_url or work.get("id"),
        "abstract": None,
        "source": "openalex",
    }


async def search_openalex(
    query: str,
    limit: int = 15,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Search OpenAlex works by query and return normalized results."""
    encoded_query = urllib.parse.quote_plus(query.strip())
    url = f"{OPENALEX_WORKS_ENDPOINT}?search={encoded_query}&per_page={limit}"

    if client is None:
        response = await http_client.get_with_retries(url)
    else:
        response = await client.get(url)

    if response.status_code == 429:
        return {
            "success": False,
            "error": "rate_limited",
            "query": query,
            "details": "OpenAlex rate-limited after retries",
        }

    try:
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        return {"success": False, "error": "http_error", "query": query, "details": str(exc)}
    except ValueError as exc:
        return {"success": False, "error": "parse_error", "query": query, "details": str(exc)}

    if not isinstance(payload, dict) or "results" not in payload:
        return {"success": False, "error": "parse_error", "query": query, "details": "Unexpected response format"}

    papers = [
        _normalize_openalex_work(item)
        for item in payload.get("results", [])
        if isinstance(item, dict)
    ]
    return {
        "success": True,
        "query": query,
        "data": papers,
        "meta": payload.get("meta"),
    }


async def fetch_openalex_by_doi(
    doi: str,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Lookup an OpenAlex work by DOI."""
    encoded_doi = urllib.parse.quote_plus(doi.strip())
    url = f"{OPENALEX_WORKS_ENDPOINT}?filter=doi:{encoded_doi}&per_page=1"

    if client is None:
        response = await http_client.get_with_retries(url)
    else:
        response = await client.get(url)

    if response.status_code == 429:
        return {
            "success": False,
            "error": "rate_limited",
            "doi": doi,
            "details": "OpenAlex rate-limited after retries",
        }

    try:
        response.raise_for_status()
        payload = response.json()
    except httpx.HTTPStatusError as exc:
        return {"success": False, "error": "http_error", "doi": doi, "details": str(exc)}
    except ValueError as exc:
        return {"success": False, "error": "parse_error", "doi": doi, "details": str(exc)}

    if not isinstance(payload, dict) or "results" not in payload:
        return {"success": False, "error": "parse_error", "doi": doi, "details": "Unexpected response format"}

    results = payload.get("results", [])
    if not isinstance(results, list) or not results:
        return {"success": False, "error": "not_found", "doi": doi, "details": "No OpenAlex work found for DOI"}

    work = results[0]
    if not isinstance(work, dict):
        return {"success": False, "error": "parse_error", "doi": doi, "details": "Invalid work record"}

    normalized = _normalize_openalex_work(work)
    normalized["doi"] = normalized.get("doi") or doi
    return {"success": True, "doi": doi, "data": normalized}


if __name__ == "__main__":
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="OpenAlex API wrapper.")
    parser.add_argument("action", choices=["search", "doi"], help="Action to perform")
    parser.add_argument("value", help="Search query or DOI")
    args = parser.parse_args()

    async def main() -> None:
        if args.action == "search":
            result = await search_openalex(args.value)
        else:
            result = await fetch_openalex_by_doi(args.value)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    asyncio.run(main())