"""Academic tool wrappers for Evidentia.

This package hosts the backend wrappers for external academic APIs used by
teammate B's data ingestion and research layer.
"""

from backend.tools.crossref import fetch_crossref_metadata
from backend.tools.openalex import fetch_openalex_by_doi, search_openalex
from backend.tools.arxiv import search_arxiv
from backend.tools.core_api import fetch_core_by_doi, search_core
from backend.tools.opencitations import (
    fetch_opencitations_by_doi,
    fetch_opencitations_citations,
    fetch_opencitations_references,
)
from backend.tools.unpaywall import fetch_unpaywall_by_doi
from backend.tools.http_client import http_client

__all__ = [
    "fetch_crossref_metadata",
    "fetch_openalex_by_doi",
    "search_openalex",
    "search_arxiv",
    "fetch_core_by_doi",
    "search_core",
    "fetch_opencitations_by_doi",
    "fetch_opencitations_citations",
    "fetch_opencitations_references",
    "fetch_unpaywall_by_doi",
    "http_client",
]
