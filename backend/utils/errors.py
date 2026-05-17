"""Shared helpers for surfacing exceptions in API responses."""

from __future__ import annotations


def format_exception(exc: BaseException) -> str:
    """Return a non-empty human-readable message for job/analysis error fields."""
    message = str(exc).strip()
    if message:
        return message
    if exc.args:
        first = exc.args[0]
        if first is not None and str(first).strip():
            return str(first).strip()
    return type(exc).__name__
