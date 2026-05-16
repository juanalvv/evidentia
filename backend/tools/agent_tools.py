"""Wire academic API modules into the agent-facing tool dict (lookup_doi, search_opposing, llm)."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from backend.tools import crossref as crossref_mod
from backend.tools import openalex as openalex_mod
from backend.tools.llm import LLMClient
from backend.tools.stubs import CrossrefStub, LLMStub, OpenAlexStub, SemanticScholarStub


def should_use_stubs() -> bool:
    """Use stub tools unless OPENCLAW_USE_STUBS is explicitly false or NVIDIA_API_KEY is present."""
    explicit = os.getenv("OPENCLAW_USE_STUBS")
    if explicit is not None:
        return explicit.lower() in ("1", "true", "yes")
    if os.getenv("NVIDIA_API_KEY"):
        return False
    from dotenv import load_dotenv

    load_dotenv("nvidia_api.env")
    return not os.getenv("NVIDIA_API_KEY")


class CrossrefAdapter:
    async def lookup_doi(self, doi: str) -> Dict[str, Any]:
        return await crossref_mod.fetch_crossref_metadata(doi)


class OpenAlexAdapter:
    async def search_opposing(self, query: str) -> List[Dict[str, Any]]:
        res = await openalex_mod.search_openalex(query)
        if isinstance(res, dict) and res.get("success"):
            return res.get("data") or []
        return []


def build_agent_tools(use_stubs_override: Optional[bool] = None) -> Dict[str, Any]:
    """Return the tools dict expected by SourceChecker, CounterResearcher, and Grader."""
    stubs = should_use_stubs() if use_stubs_override is None else use_stubs_override

    if stubs:
        return {
            "crossref": CrossrefStub(),
            "semantic_scholar": SemanticScholarStub(),
            "openalex": OpenAlexStub(),
            "llm": LLMStub(),
        }

    return {
        "crossref": CrossrefAdapter(),
        "semantic_scholar": None,
        "openalex": OpenAlexAdapter(),
        "llm": LLMClient(),
    }
