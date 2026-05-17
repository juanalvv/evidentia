"""In-memory job document for the FastAPI worker (Person B).

Shape stored in ``main.jobs[job_id]``:

- **status** — ``pending`` | ``running`` | ``completed`` | ``failed``
- **progress** — ``{ phase, percent, message, agent }`` (see CONTRACT.md)
- **ingest** — SCHEMAS.md input payload after parsing, or ``None``
- **analysis_result** — orchestrator output (AnalysisResult); ``None`` until Tier 14+
- **result** — raw pipeline payload (``input``, ``analysis``, ``ingest`` mirror); kept for debugging
- **error** — top-level failure string when ``status == failed``
- **created_at** — ISO-8601 UTC timestamp

Agents / UI should treat ``completed`` as the terminal success state (replaces legacy ``finished``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, TypedDict

JobStatus = Literal["pending", "running", "completed", "failed"]


class ProgressPayload(TypedDict):
    phase: str
    percent: int
    message: str
    agent: str


def _utc_now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def default_progress(
    phase: str = "ingest",
    percent: int = 0,
    message: str = "Queued",
    agent: str = "orchestrator",
) -> ProgressPayload:
    return {
        "phase": phase,
        "percent": percent,
        "message": message,
        "agent": agent,
    }


def new_job_document() -> Dict[str, Any]:
    """Return a fresh job row aligned with TASKGUIDE Tier 2 / CONTRACT progress."""
    return {
        "status": "pending",
        "progress": default_progress(),
        "ingest": None,
        "analysis_result": None,
        "result": None,
        "error": None,
        "created_at": _utc_now_iso(),
    }


def progress_update(
    phase: str,
    percent: int,
    message: str,
    agent: str = "orchestrator",
) -> ProgressPayload:
    """Bundle for ``_save_job(..., {"progress": progress_update(...)})``."""
    return {
        "phase": phase,
        "percent": percent,
        "message": message,
        "agent": agent,
    }


def coerce_progress(job: Dict[str, Any]) -> ProgressPayload:
    """Return a CONTRACT-safe progress object (GET /status, GET /report 202)."""
    base = default_progress()
    raw = job.get("progress")
    if not isinstance(raw, dict):
        return base
    try:
        pct = int(raw.get("percent", base["percent"]))
    except (TypeError, ValueError):
        pct = base["percent"]
    return {
        "phase": str(raw.get("phase") or base["phase"]),
        "percent": max(0, min(100, pct)),
        "message": str(raw.get("message") or base["message"]),
        "agent": str(raw.get("agent") or base["agent"]),
    }
