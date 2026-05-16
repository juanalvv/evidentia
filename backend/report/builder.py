"""Assemble Evidentia analysis JSON into a markdown report."""

from __future__ import annotations

from typing import Any


def _pct(score: float | None) -> str:
    if score is None:
        return "—"
    return f"{round(float(score) * 100)}%"


def _flag_label(flag: str | None) -> str:
    return {"stale": "⚠ Outdated / superseded risk", "ok": "✓ Acceptable recency", "recent": "◎ Recent"}.get(
        flag or "", flag or "—"
    )


def _score_bar(score: float | None, width: int = 12) -> str:
    if score is None:
        return ""
    filled = max(0, min(width, int(round(float(score) * width))))
    return "█" * filled + "░" * (width - filled)


def build_report(data: dict[str, Any]) -> dict[str, str]:
    """Return `{ \"markdown\": ... }` from an AnalysisResult dict."""
    lines: list[str] = []
    paper = data.get("paper") or {}
    title = paper.get("title") or "Untitled draft"
    lines.append(f"# Evidentia Report: {title}")
    if paper.get("authors"):
        lines.append(f"*Authors (detected):* {paper['authors']}")
    lines.append("")

    summary = data.get("executive_summary")
    if summary:
        lines.append("## Key Findings")
        lines.append(summary.strip())
        lines.append("")

    scores = data.get("overall_scores") or {}
    lines.append("## Overall grades")
    lines.append("| Dimension | Score |")
    lines.append("|-----------|-------|")
    for key, label in [
        ("source_quality", "Source quality"),
        ("coverage", "Argument coverage"),
        ("data_quality", "Data / methods quality"),
    ]:
        s = scores.get(key)
        bar = _score_bar(s)
        lines.append(f"| {label} | {_pct(s)} `{bar}` |")
    lines.append("")

    citations = data.get("citations") or []
    if citations:
        lines.append("## Source quality by citation")
        for c in citations:
            sid = c.get("id", "?")
            yr = c.get("year", "?")
            sq = c.get("source_quality_score")
            lines.append(f"### [{sid}] {c.get('title', 'Unknown')} ({yr})")
            lines.append(f"- **Quality:** {_pct(sq)} `{_score_bar(sq)}`")
            lines.append(f"- **Recency:** {_flag_label(c.get('recency_flag'))}")
            if c.get("doi"):
                lines.append(f"- **DOI:** [{c['doi']}](https://doi.org/{c['doi'].replace('https://doi.org/', '')})")
            if c.get("superseded_notes"):
                lines.append(f"- **Supersession note:** {c['superseded_notes']}")
            for sup in c.get("superseded_by") or []:
                lines.append(f"  - Newer related work: *{sup.get('title')}* ({sup.get('year')})")
            lines.append("")

    claims = data.get("claims") or []
    if claims:
        lines.append("## Claims, coverage & counterarguments")
        for claim in claims:
            lines.append(f"### {claim.get('id', 'claim')}: {claim.get('section', 'Section')}")
            lines.append(f"> {claim.get('text', '').strip()}")
            cov = claim.get("coverage_score")
            lines.append(f"- **Coverage:** {_pct(cov)} `{_score_bar(cov)}`")
            cited = claim.get("cited_source_ids") or []
            if cited:
                lines.append(f"- **Cited sources:** {', '.join(cited)}")
            for i, ca in enumerate(claim.get("counterarguments") or [], 1):
                lines.append(f"- **Counterargument {i}:** {ca.get('summary', '')}")
                for p in ca.get("papers") or []:
                    doi = p.get("doi")
                    link = p.get("url") or (f"https://doi.org/{doi}" if doi else "")
                    link_part = f" — [{link}]({link})" if link else ""
                    lines.append(
                        f"  - {p.get('authors', 'Unknown')} ({p.get('year', '?')}): "
                        f"*{p.get('title', 'Untitled')}*{link_part}"
                    )
                    if p.get("relevance"):
                        lines.append(f"    - *Relevance:* {p['relevance']}")
            supporting = claim.get("supporting_sources") or []
            if supporting:
                lines.append("- **Additional supporting literature:**")
                for s in supporting:
                    note = f" — {s['note']}" if s.get("note") else ""
                    lines.append(f"  - *{s.get('title')}* ({s.get('year', '?')}){note}")
            lines.append("")

    dq = data.get("data_quality") or {}
    if dq:
        lines.append("## Data & methods comparison")
        lines.append(f"**Overall data quality score:** {_pct(dq.get('score'))} `{_score_bar(dq.get('score'))}`")
        if dq.get("summary"):
            lines.append("")
            lines.append(dq["summary"].strip())
        comparisons = dq.get("comparisons") or []
        if comparisons:
            lines.append("")
            lines.append("| Aspect | In draft | Field norm | Verdict |")
            lines.append("|--------|----------|------------|---------|")
            for row in comparisons:
                lines.append(
                    f"| {row.get('aspect', '')} | {row.get('paper_value', '')} | "
                    f"{row.get('field_norm', '')} | `{row.get('verdict', '')}` |"
                )
        lines.append("")

    errors = data.get("errors") or []
    if errors:
        lines.append("## Warnings")
        for err in errors:
            lines.append(f"- {err}")
        lines.append("")

    lines.append("---")
    lines.append("*Generated by Evidentia — Hack-a-Claw Cloud Track*")
    return {"markdown": "\n".join(lines)}


if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    fixture = Path(__file__).parent / "fixtures" / "mock_analysis.json"
    payload = json.loads(fixture.read_text(encoding="utf-8"))
    md = build_report(payload)["markdown"]
    out = Path(__file__).parent / "fixtures" / "mock_report.md"
    out.write_text(md, encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(md)
