from __future__ import annotations

from typing import Any, Dict, List

from .model_router import ModelRoute
from .schemas import Citation, Claim, CoverageScore, GraderOutput, SourceCheck, SourceQualityScore
from ..memory.context_store import ContextStore


async def run_grader(
    claims: List[Claim],
    citations: List[Citation],
    source_checks: List[SourceCheck],
    tools: Dict[str, Any],
    model_route_reasoning: ModelRoute,
    model_route_scoring: ModelRoute,
    context: ContextStore,
) -> GraderOutput:
    llm = tools.get("llm")
    scores: List[SourceQualityScore] = []

    for citation in citations:
        score, rubric = await _score_citation(citation, source_checks, llm, model_route_scoring)
        scores.append(SourceQualityScore(citation_id=citation.citation_id, score=score, rubric=rubric))

    coverage = await _coverage_score(claims, citations, llm, model_route_reasoning)
    output = GraderOutput(source_quality=scores, coverage=coverage)
    context.set("grader", output.model_dump())
    return output


async def _score_citation(
    citation: Citation,
    source_checks: List[SourceCheck],
    llm: Any,
    model_route: ModelRoute,
) -> tuple[float, Dict[str, Any]]:
    rubric = {"recency": 0.0, "citations": 0.0, "venue": 0.0}
    score = 0.5

    check = next((item for item in source_checks if item.citation_id == citation.citation_id), None)
    if check and check.publication_year:
        age_penalty = 0.1 if check.is_outdated else 0.0
        rubric["recency"] = 1.0 - age_penalty

    if llm:
        prompt = (
            "Score citation quality on a 0-1 scale using year, venue, and citation count.\n"
            f"Citation: {citation.raw_text}\n"
            "Return JSON: {\"score\": 0.0, \"recency\": 0.0, \"citations\": 0.0, \"venue\": 0.0}."
        )
        response = await llm.complete(prompt=prompt, model=model_route.name, max_tokens=128)
        parsed = _safe_parse_json(response)
        if parsed:
            score = float(parsed.get("score", score))
            rubric.update({
                "recency": parsed.get("recency", rubric["recency"]),
                "citations": parsed.get("citations", rubric["citations"]),
                "venue": parsed.get("venue", rubric["venue"]),
            })

    return score, rubric


async def _coverage_score(
    claims: List[Claim],
    citations: List[Citation],
    llm: Any,
    model_route: ModelRoute,
) -> CoverageScore:
    if not claims:
        return CoverageScore(score=0.0, explanation="No claims provided.")

    if not llm:
        return CoverageScore(score=0.5, explanation="Coverage estimated without LLM.")

    prompt = (
        "Determine which claims are supported by the citations.\n"
        f"Claims: {[claim.text for claim in claims]}\n"
        f"Citations: {[citation.raw_text for citation in citations]}\n"
        "Return JSON with supported_claim_ids, unsupported_claim_ids, and score 0-1."
    )
    response = await llm.complete(prompt=prompt, model=model_route.name, max_tokens=256)
    parsed = _safe_parse_json(response)
    if not parsed:
        return CoverageScore(score=0.5, explanation="Coverage could not be parsed.")

    claims_backed = [str(i) for i in parsed.get("supported_claim_ids", [])]
    claims_unbacked = [str(i) for i in parsed.get("unsupported_claim_ids", [])]
    score = float(parsed.get("score", 0.5))
    explanation = parsed.get("explanation", "Coverage estimated from LLM reasoning.")
    return CoverageScore(
        score=score,
        explanation=explanation,
        claims_backed=claims_backed,
        claims_unbacked=claims_unbacked,
    )


import re
import json

def _safe_parse_json(response: str) -> Dict[str, Any]:
    try:
        # 1. Try direct parse
        return json.loads(response.strip())
    except Exception:
        pass

    try:
        # 2. Try extracting from markdown code blocks
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if match:
            return json.loads(match.group(1).strip())
    except Exception:
        pass

    try:
        # 3. Try finding the first '{' and last '}'
        start = response.find("{")
        end = response.rfind("}")
        if start != -1 and end != -1:
            return json.loads(response[start : end + 1].strip())
    except Exception:
        pass

    return {}
