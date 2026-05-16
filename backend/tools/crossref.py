import urllib.parse
from typing import Any, Dict, Optional

import httpx

from backend.tools.cache import cache, make_cache_key
from backend.tools.http_client import http_client

CROSSREF_BASE_URL = "https://api.crossref.org/works"
USER_AGENT = "Evidentia/1.0 (mailto:team@evidentia.example)"


def _extract_year(date_payload: Any) -> Optional[int]:
    if not isinstance(date_payload, dict):
        return None
    date_parts = date_payload.get("date-parts")
    if not isinstance(date_parts, list) or not date_parts:
        return None
    first = date_parts[0]
    if not isinstance(first, list) or not first:
        return None
    year = first[0]
    return int(year) if isinstance(year, int) else None


def _normalize_authors(author_list: Any) -> Optional[list]:
    if not isinstance(author_list, list):
        return None
    authors = []
    for author in author_list:
        if not isinstance(author, dict):
            continue
        given = author.get("given") or ""
        family = author.get("family") or ""
        name = author.get("name")
        if name and isinstance(name, str):
            authors.append(name.strip())
            continue
        full = " ".join(part for part in (given, family) if part).strip()
        if full:
            authors.append(full)
    return authors if authors else None


def _normalize_crossref_message(message: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "doi": message.get("DOI"),
        "title": message.get("title", [None])[0] if isinstance(message.get("title"), list) else message.get("title"),
        "authors": _normalize_authors(message.get("author")),
        "year": _extract_year(message.get("issued") or message.get("published-print") or message.get("published-online") or message.get("created")),
        "journal": message.get("container-title", [None])[0] if isinstance(message.get("container-title"), list) else message.get("container-title"),
        "publisher": message.get("publisher"),
        "type": message.get("type"),
        "url": message.get("URL"),
        "abstract": message.get("abstract"),
    }


async def fetch_crossref_metadata(doi: str, client: Optional[httpx.AsyncClient] = None) -> Dict[str, Any]:
    """Fetch Crossref metadata for a DOI and normalize the response."""
    cache_key = make_cache_key("crossref", "doi", doi.lower())

    async def fetch() -> Dict[str, Any]:
        encoded_doi = urllib.parse.quote(doi.strip())
        url = f"{CROSSREF_BASE_URL}/{encoded_doi}"
        headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}

        if client is None:
            response = await http_client.get_with_retries(url, headers=headers)
        else:
            response = await client.get(url, headers=headers)

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

        if not isinstance(payload, dict) or "message" not in payload:
            return {"success": False, "error": "parse_error", "doi": doi, "details": "Unexpected response format"}

        normalized = _normalize_crossref_message(payload["message"])
        normalized["source"] = "crossref"
        normalized["doi"] = normalized.get("doi") or doi
        return {"success": True, "data": normalized}

    return await cache.memoize(cache_key, fetch, ttl=3600)


if __name__ == "__main__":
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="Fetch metadata from Crossref by DOI.")
    parser.add_argument("doi", help="DOI to query")
    args = parser.parse_args()

    async def main() -> None:
        result = await fetch_crossref_metadata(args.doi)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    asyncio.run(main())
