import os
import urllib.parse
from typing import Any, Dict, List, Optional

import httpx

from backend.tools.cache import cache, make_cache_key
from backend.tools.http_client import http_client

UNPAYWALL_BASE_URL = "https://api.unpaywall.org/v2"
UNPAYWALL_DEFAULT_EMAIL = os.getenv("UNPAYWALL_EMAIL", "team@evidentia.example")


def _normalize_unpaywall_authors(authors_payload: Any) -> Optional[List[str]]:
    if not isinstance(authors_payload, list):
        return None
    authors: List[str] = []
    for author in authors_payload:
        if not isinstance(author, dict):
            continue
        name = author.get("name")
        if isinstance(name, str) and name.strip():
            authors.append(name.strip())
    return authors if authors else None


def _normalize_oa_location(location: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(location, dict):
        return None
    return {
        "url": location.get("url"),
        "url_for_landing_page": location.get("url_for_landing_page"),
        "url_for_pdf": location.get("url_for_pdf"),
        "host_type": location.get("host_type"),
        "license": location.get("license"),
        "repository_institution": location.get("repository_institution"),
        "version": location.get("version"),
        "content_type": location.get("content_type"),
    }


def _normalize_unpaywall_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    best_location = payload.get("best_oa_location")
    oa_locations = payload.get("oa_locations")
    normalized_locations = [
        loc for loc in (_normalize_oa_location(item) for item in oa_locations or []) if loc
    ]
    return {
        "doi": payload.get("doi"),
        "title": payload.get("title"),
        "year": payload.get("year"),
        "authors": _normalize_unpaywall_authors(payload.get("authors")),
        "journal": payload.get("journal_name"),
        "publisher": payload.get("publisher"),
        "is_oa": payload.get("is_oa"),
        "oa_status": payload.get("oa_status"),
        "best_oa_location": _normalize_oa_location(best_location),
        "oa_locations": normalized_locations,
        "doi_url": payload.get("doi_url"),
        "journal_is_oa": payload.get("journal_is_oa"),
        "source": "unpaywall",
    }


async def fetch_unpaywall_by_doi(
    doi: str,
    email: Optional[str] = None,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Fetch Unpaywall OA metadata for a DOI and normalize the response."""
    cache_key = make_cache_key("unpaywall", "doi", doi.lower())

    async def fetch() -> Dict[str, Any]:
        encoded_doi = urllib.parse.quote(doi.strip(), safe="/")
        email_value = urllib.parse.quote((email or UNPAYWALL_DEFAULT_EMAIL).strip())
        url = f"{UNPAYWALL_BASE_URL}/{encoded_doi}?email={email_value}"

        if client is None:
            response = await http_client.get_with_retries(url)
        else:
            response = await client.get(url)

        if response.status_code == 404:
            return {"success": False, "error": "not_found", "doi": doi, "details": response.text}
        if response.status_code == 429:
            return {"success": False, "error": "rate_limited", "doi": doi, "details": response.text}

        try:
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as exc:
            return {"success": False, "error": "http_error", "doi": doi, "details": str(exc)}
        except ValueError as exc:
            return {"success": False, "error": "parse_error", "doi": doi, "details": str(exc)}

        if not isinstance(payload, dict):
            return {"success": False, "error": "parse_error", "doi": doi, "details": "Unexpected response format"}

        normalized = _normalize_unpaywall_payload(payload)
        normalized["doi"] = normalized.get("doi") or doi
        return {"success": True, "doi": doi, "data": normalized}

    return await cache.memoize(cache_key, fetch, ttl=3600)


if __name__ == "__main__":
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="Unpaywall API wrapper.")
    parser.add_argument("doi", help="DOI to query")
    parser.add_argument("--email", help="Contact email to pass to Unpaywall", default=UNPAYWALL_DEFAULT_EMAIL)
    args = parser.parse_args()

    async def main() -> None:
        result = await fetch_unpaywall_by_doi(args.doi, email=args.email)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    asyncio.run(main())
