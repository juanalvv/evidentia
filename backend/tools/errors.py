"""Shared error codes and helpers for academic API tool wrappers."""

from __future__ import annotations

from typing import Any, Dict, Optional

# Standard failure codes returned in {"success": False, "error": "<code>", ...}
NOT_FOUND = "not_found"
RATE_LIMITED = "rate_limited"
HTTP_ERROR = "http_error"
PARSE_ERROR = "parse_error"
METADATA_NOT_FOUND = "metadata_not_found"
INVALID_REQUEST = "invalid_request"

TOOL_ERROR_CODES = frozenset(
    {
        NOT_FOUND,
        RATE_LIMITED,
        HTTP_ERROR,
        PARSE_ERROR,
        METADATA_NOT_FOUND,
        INVALID_REQUEST,
    }
)


def tool_error(result: Dict[str, Any]) -> Optional[str]:
    """Return the error code from a tool result, or None if successful."""
    if result.get("success"):
        return None
    error = result.get("error")
    if isinstance(error, str):
        return error
    # OpenCitations aggregate bundles nest references/citations without a top-level error.
    for key in ("references", "citations"):
        nested = result.get(key)
        if isinstance(nested, dict):
            nested_error = tool_error(nested)
            if nested_error:
                return nested_error
    return None


def is_tool_success(result: Dict[str, Any]) -> bool:
    return result.get("success") is True


def summarize_partial_errors(parts: Dict[str, Dict[str, Any]]) -> Dict[str, Optional[str]]:
    """Map sub-call names to their error codes (None when that sub-call succeeded)."""
    return {name: tool_error(result) for name, result in parts.items()}
