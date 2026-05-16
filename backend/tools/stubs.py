from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class CrossrefStub:
    """Stub Crossref client that returns fixed metadata for a DOI."""

    title: str = "Stubbed Crossref Title"
    year: int = 2021
    doi: str = "10.0000/stubbed"

    def lookup_doi(self, doi: str) -> Dict[str, Any]:
        return {"title": self.title, "year": self.year, "doi": doi or self.doi}


@dataclass
class SemanticScholarStub:
    """Stub Semantic Scholar client for contradiction signals and opposing papers."""

    contradiction_signals: Optional[List[str]] = None
    opposing_papers: Optional[List[Dict[str, Any]]] = None

    def find_contradiction_signals(self, title: Optional[str] = None, doi: Optional[str] = None) -> List[str]:
        return list(self.contradiction_signals or [])

    def search_opposing(self, query: str) -> List[Dict[str, Any]]:
        return list(self.opposing_papers or [])


@dataclass
class OpenAlexStub:
    """Stub OpenAlex client that returns opposing papers."""

    opposing_papers: Optional[List[Dict[str, Any]]] = None

    def search_opposing(self, query: str) -> List[Dict[str, Any]]:
        return list(self.opposing_papers or [])


@dataclass
class LLMStub:
    """Stub LLM client that returns fixed responses for scoring and summaries."""

    score_payload: str = '{"score": 0.7, "recency": 0.8, "citations": 0.6, "venue": 0.7}'
    coverage_payload: str = '{"supported_claim_ids": ["c1"], "unsupported_claim_ids": [], "score": 0.8, "explanation": "Stubbed coverage."}'
    summary_text: str = "Stubbed counterargument summary."
    query_text: str = "stubbed query"

    def complete(self, prompt: str, model: str, max_tokens: int = 128) -> str:
        if "Return JSON" in prompt and "citation quality" in prompt:
            return self.score_payload
        if "supported_claim_ids" in prompt or "unsupported_claim_ids" in prompt:
            return self.coverage_payload
        if "Return query only" in prompt:
            return self.query_text
        return self.summary_text
