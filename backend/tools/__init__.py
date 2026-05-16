"""Academic tool wrappers for Evidentia.

This package hosts the backend wrappers for external academic APIs used by
teammate B's data ingestion and research layer.
"""

from backend.tools.arxiv import search_arxiv
from backend.tools.crossref import fetch_crossref_metadata
from backend.tools.enrichment import enrich_doi, fetch_doi_metadata
from backend.tools.http_client import http_client
from backend.tools.openalex import fetch_openalex_by_doi, search_openalex
from backend.tools.opencitations import (
    fetch_opencitations_by_doi,
    fetch_opencitations_citations,
    fetch_opencitations_references,
)
from backend.tools.unpaywall import fetch_unpaywall_by_doi

__all__ = [
    "fetch_crossref_metadata",
    "fetch_openalex_by_doi",
    "search_openalex",
    "search_arxiv",
    "fetch_opencitations_by_doi",
    "fetch_opencitations_citations",
    "fetch_opencitations_references",
    "fetch_unpaywall_by_doi",
    "enrich_doi",
    "fetch_doi_metadata",
    "http_client",
]
