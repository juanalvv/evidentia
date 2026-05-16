import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx

from backend.tools.http_client import http_client

ARXIV_BASE_URL = "https://export.arxiv.org/api/query"
XML_NAMESPACES = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
}


def _get_text(element: Optional[ET.Element], default: Optional[str] = None) -> Optional[str]:
    if element is None or element.text is None:
        return default
    return element.text.strip() or default


def _normalize_arxiv_entry(entry: ET.Element) -> Dict[str, Any]:
    arxiv_id = _get_text(entry.find("atom:id", XML_NAMESPACES))
    title = _get_text(entry.find("atom:title", XML_NAMESPACES))
    summary = _get_text(entry.find("atom:summary", XML_NAMESPACES))
    published = _get_text(entry.find("atom:published", XML_NAMESPACES))
    updated = _get_text(entry.find("atom:updated", XML_NAMESPACES))

    authors = []
    for author in entry.findall("atom:author", XML_NAMESPACES):
        name = _get_text(author.find("atom:name", XML_NAMESPACES), "")
        if name:
            authors.append(name)

    categories = []
    for category in entry.findall("atom:category", XML_NAMESPACES):
        term = category.attrib.get("term")
        if isinstance(term, str) and term.strip():
            categories.append(term.strip())

    primary_category = None
    primary_category_el = entry.find("arxiv:primary_category", XML_NAMESPACES)
    if primary_category_el is not None:
        primary_category = primary_category_el.attrib.get("term")

    doi = _get_text(entry.find("arxiv:doi", XML_NAMESPACES))

    links = {link.attrib.get("title") or link.attrib.get("type"): link.attrib.get("href") for link in entry.findall("atom:link", XML_NAMESPACES) if link.attrib.get("href")}
    pdf_url = links.get("pdf") or links.get("application/pdf") or links.get(None)

    return {
        "id": arxiv_id,
        "doi": doi,
        "title": title,
        "abstract": summary,
        "authors": authors or None,
        "published": published,
        "updated": updated,
        "categories": categories or None,
        "primary_category": primary_category,
        "url": pdf_url or arxiv_id,
        "source": "arxiv",
    }


def _build_search_query(
    query: Optional[str] = None,
    author: Optional[str] = None,
    title: Optional[str] = None,
) -> Optional[str]:
    parts: List[str] = []
    if query:
        parts.append(f"all:{query}")
    if author:
        parts.append(f"au:{author}")
    if title:
        parts.append(f"ti:{title}")
    if not parts:
        return None
    return "+AND+".join(urllib.parse.quote_plus(part) for part in parts)


async def search_arxiv(
    query: Optional[str] = None,
    author: Optional[str] = None,
    title: Optional[str] = None,
    max_results: int = 10,
    client: Optional[httpx.AsyncClient] = None,
) -> Dict[str, Any]:
    """Search arXiv by query, author, or title and return normalized metadata."""
    search_query = _build_search_query(query, author, title)
    if search_query is None:
        return {"success": False, "error": "invalid_request", "details": "At least one of query, author, or title must be provided."}

    url = f"{ARXIV_BASE_URL}?search_query={search_query}&max_results={max_results}"
    headers = {"User-Agent": "Evidentia/1.0"}

    if client is None:
        response = await http_client.get_with_retries(url, headers=headers)
    else:
        response = await client.get(url, headers=headers)

    if response.status_code == 429:
        return {"success": False, "error": "rate_limit", "details": "arXiv rate limited after retries"}

    try:
        response.raise_for_status()
        root = ET.fromstring(response.text)
    except httpx.HTTPStatusError as exc:
        return {"success": False, "error": "http_error", "details": str(exc)}
    except ET.ParseError as exc:
        return {"success": False, "error": "parse_error", "details": str(exc)}

    entries = root.findall("atom:entry", XML_NAMESPACES)
    papers = [_normalize_arxiv_entry(entry) for entry in entries if isinstance(entry, ET.Element)]

    total_results = None
    total_el = root.find("opensearch:totalResults", XML_NAMESPACES)
    if total_el is not None and total_el.text:
        try:
            total_results = int(total_el.text.strip())
        except ValueError:
            total_results = None

    return {
        "success": True,
        "query": {
            "query": query,
            "author": author,
            "title": title,
        },
        "data": papers,
        "total": total_results,
    }


if __name__ == "__main__":
    import argparse
    import asyncio
    import json

    parser = argparse.ArgumentParser(description="arXiv API wrapper.")
    parser.add_argument("--query", help="General search query")
    parser.add_argument("--author", help="Search by author")
    parser.add_argument("--title", help="Search by title")
    parser.add_argument("--max-results", type=int, default=5, help="Maximum results")
    args = parser.parse_args()

    async def main() -> None:
        result = await search_arxiv(args.query, args.author, args.title, args.max_results)
        print(json.dumps(result, indent=2, ensure_ascii=False))

    asyncio.run(main())