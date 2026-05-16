import re
from typing import Dict, Optional

DOI_RE = re.compile(r"\b10\.\d{4,9}/[-._;()/:A-Za-z0-9]+\b")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")


def extract_doi(reference: str) -> Optional[str]:
    match = DOI_RE.search(reference)
    return match.group(0).rstrip(".") if match else None


def extract_year(reference: str) -> Optional[int]:
    match = YEAR_RE.search(reference)
    if match:
        return int(match.group(0))
    return None


def prepare_reference_for_model(reference: str) -> Dict[str, Optional[object]]:
    """Return a raw citation payload for model-driven interpretation.

    We intentionally avoid full structured parsing here. The model receives the
    original citation text and can derive authors, title, journal, and other
    metadata itself.
    """
    normalized = reference.strip()
    return {
        "raw_text": normalized,
        "doi": extract_doi(normalized),
        "year": extract_year(normalized),
        "authors": None,
        "title": None,
        "journal": None,
    }


def parse_reference(reference: str) -> Dict[str, Optional[object]]:
    """Legacy alias for prepare_reference_for_model.

    Keeping the same return shape so downstream components can still use this
    helper while the pipeline transitions to raw citation model input.
    """
    return prepare_reference_for_model(reference)


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Prepare a citation string for model input.")
    parser.add_argument("reference", help="A single reference text block.")
    args = parser.parse_args()

    output = prepare_reference_for_model(args.reference)
    print(json.dumps(output, indent=2, ensure_ascii=False))
