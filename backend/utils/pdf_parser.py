import re
from typing import Dict, List, Optional

try:
    import fitz  # PyMuPDF
except ImportError as exc:
    raise ImportError(
        "PyMuPDF is required for backend.utils.pdf_parser. Install it with `pip install pymupdf`."
    ) from exc

REFERENCE_START_RE = re.compile(
    r"(?im)^(references|bibliography|works cited|literature cited)\s*$"
)
REFERENCE_END_RE = re.compile(r"(?im)^(appendix|supplementary|acknowledgements|acknowledgments)\s*$")


def extract_text(pdf_path: str) -> str:
    """Extract plain text from every page of a PDF."""
    doc = fitz.open(pdf_path)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return "\n".join(pages).strip()


def find_reference_section(full_text: str) -> Optional[Dict[str, int]]:
    """Locate the reference section start and end in extracted PDF text."""
    matches = list(REFERENCE_START_RE.finditer(full_text))
    if not matches:
        return None

    start_match = matches[-1]
    start = start_match.end()
    following_text = full_text[start:]
    end_match = REFERENCE_END_RE.search(following_text)
    end = start + end_match.start() if end_match else len(full_text)
    return {"start": start, "end": end}


def extract_references_text(full_text: str) -> str:
    """Extract the reference section text block from the document text."""
    bounds = find_reference_section(full_text)
    if not bounds:
        return ""
    return full_text[bounds["start"]:bounds["end"]].strip()


def _split_inline_numbered_entries(reference_text: str) -> List[str]:
    """Split a text block on inline numbered reference markers if needed."""
    numbered_boundary = re.compile(
        r"(?<=\S)\s+(?=(?:\[?\d{1,3}\]?\.?|\d{1,3}\))\s+)"
    )
    parts = numbered_boundary.split(reference_text)
    return [part.strip() for part in parts if part.strip()]


def _split_reference_paragraph(paragraph: str) -> List[str]:
    lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
    if not lines:
        return []

    entries: List[str] = []
    current: List[str] = []
    entry_start_re = re.compile(r"^(?:\[?\d{1,3}\]?\.?|\d{1,3}\)|•)\s+")

    for line in lines:
        if entry_start_re.match(line) and current:
            entries.append(" ".join(current).strip())
            current = [line]
        else:
            current.append(line)
    if current:
        entries.append(" ".join(current).strip())

    if len(entries) == 1:
        return _split_inline_numbered_entries(entries[0])
    return entries


def split_reference_entries(references_text: str) -> List[str]:
    """Split the reference text into individual reference strings."""
    if not references_text.strip():
        return []

    normalized = references_text.replace("\r\n", "\n").strip()
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", normalized) if p.strip()]

    entries: List[str] = []
    for paragraph in paragraphs:
        entries.extend(_split_reference_paragraph(paragraph))
    return entries


def parse_pdf(pdf_path: str) -> Dict[str, object]:
    """Parse a PDF and return its full text plus extracted reference entries."""
    full_text = extract_text(pdf_path)
    references_text = extract_references_text(full_text)
    reference_entries = split_reference_entries(references_text)
    return {
        "full_text": full_text,
        "references_text": references_text,
        "reference_entries": reference_entries,
    }


if __name__ == "__main__":
    import argparse
    import json

    parser = argparse.ArgumentParser(description="Extract PDF text and citations.")
    parser.add_argument("pdf_path", help="Path to a PDF file.")
    args = parser.parse_args()

    result = parse_pdf(args.pdf_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
