"""Academic tool wrappers for Evidentia.

This package hosts the backend wrappers for external academic APIs used by
teammate B's data ingestion and research layer.
"""

from backend.tools.crossref import fetch_crossref_metadata
from backend.tools.openalex import fetch_openalex_by_doi, search_openalex
from backend.tools.arxiv import search_arxiv
from backend.tools.http_client import http_client

__all__ = [
    "fetch_crossref_metadata",
    "fetch_openalex_by_doi",
    "search_openalex",
    "search_arxiv",
    "http_client",
]
