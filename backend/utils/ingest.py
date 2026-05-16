"""Build orchestrator input payloads from ingested documents (SCHEMAS.md)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

SourceKind = Literal["pdf", "text"]


def _guess_paper_metadata(full_text: str) -> Dict[str, Optional[Any]]:
    """Cheap heuristic for paper title/authors from the start of the document."""
    lines = [line.strip() for line in full_text.splitlines() if line.strip()]
    if not lines:
        return {"title": None, "authors": None}

    title = lines[0]
    authors: Optional[List[str]] = None
    if len(lines) > 1:
        candidate = lines[1]
        lowered = candidate.lower()
        if (
            len(candidate) <= 200
            and not lowered.startswith(("abstract", "introduction", "keywords", "acknowledg"))
        ):
            authors = [candidate]

    return {"title": title, "authors": authors}


def _citation_from_prepared(citation_id: str, prepared: Dict[str, Any]) -> Dict[str, Any]:
    """Map prepare_reference_for_model output to SCHEMAS.md citation shape."""
    return {
        "citation_id": citation_id,
        "raw_text": prepared.get("raw_text") or "",
        "title": prepared.get("title"),
        "authors": prepared.get("authors"),
        "year": prepared.get("year"),
        "doi": prepared.get("doi"),
        "journal": prepared.get("journal"),
    }


def build_submission_payload(
    job_id: str,
    full_text: str,
    prepared_references: List[Dict[str, Any]],
    source: SourceKind,
) -> Dict[str, Any]:
    """Build Person A's input payload per SCHEMAS.md (claims filled later by agents)."""
    guessed = _guess_paper_metadata(full_text)
    citations = [
        _citation_from_prepared(f"cite-{index}", prepared)
        for index, prepared in enumerate(prepared_references, start=1)
    ]

    return {
        "submission_id": job_id,
        "claims": [],
        "citations": citations,
        "full_text": full_text,
        "metadata": {
            "source": source,
            "title": guessed["title"],
            "authors": guessed["authors"],
        },
    }
