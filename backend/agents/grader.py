from __future__ import annotations

from typing import Any, Dict, List, Optional

from .model_router import ModelRoute
from .schemas import AgentError, Citation, Claim, CoverageScore, GraderOutput, SourceCheck, SourceQualityScore
from .prompts.loader import prompt_loader
from ..memory.context_store import ContextStore
import re
import json
import logging

logger = logging.getLogger(__name__)

def _extract_scores_from_reasoning(response: str) -> Dict[str, Any]:
    """Fallback: extract citation scores from Nemotron's chain-of-thought reasoning."""
    result: Dict[str, Any] = {}

    # Look for patterns like "recency: ... => 0.4" or "recency = 0.4" or "recency: 0.4"
    for dim in ("recency", "citations", "venue"):
        match = re.search(
            rf"{dim}[^0-9]*?(\d+\.\d+)",
            response, re.IGNORECASE
        )
        if match:
            result[dim] = float(match.group(1))

    # Look for computed aggregate like "score: 0.46" or "= 0.46"
    score_match = re.search(r"(?:score|aggregate)[^0-9]*?(\d+\.\d+)", response, re.IGNORECASE)
    if score_match:
        result["score"] = float(score_match.group(1))
    elif result:
        # Compute from components if we got them
        r = result.get("recency", 0.0)
        c = result.get("citations", 0.0)
        v = result.get("venue", 0.0)
        result["score"] = round(0.4 * r + 0.3 * c + 0.3 * v, 2)

    return result


def _safe_parse_json(response: str) -> Dict[str, Any]:
    try:
        return json.loads(response.strip())
    except Exception:
        pass
    try:
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if match:
            return json.loads(match.group(1).strip())
    except Exception:
        pass
    try:
        start = response.find("{")
        end = response.rfind("}")
        if start != -1 and end != -1:
            return json.loads(response[start:end + 1].strip())
    except Exception:
        pass
    return {}

async def run_grader(
    claims: List[Claim],
    citations: List[Citation],
    source_checks: List[SourceCheck],
    tools: Dict[str, Any],
    model_route_reasoning: ModelRoute,
    model_route_scoring: ModelRoute,
    context: ContextStore,
    error_sink: Optional[List[AgentError]] = None,
) -> GraderOutput:
    llm = tools.get("llm")
    scores: List[SourceQualityScore] = []

    for citation in citations:
        logger.info("Grader: scoring citation %s", citation.citation_id)
        score, rubric = await _score_citation(
            citation,
            source_checks,
            llm,
            model_route_scoring,
            error_sink,
        )
        scores.append(SourceQualityScore(citation_id=citation.citation_id, score=score, rubric=rubric))

    coverage = await _coverage_score(claims, citations, llm, model_route_reasoning, error_sink)
    output = GraderOutput(source_quality=scores, coverage=coverage)
    context.set("grader", output.model_dump())
    return output

async def _score_citation(
    citation: Citation,
    source_checks: List[SourceCheck],
    llm: Any,
    model_route: ModelRoute,
    error_sink: Optional[List[AgentError]],
) -> tuple[float, Dict[str, Any]]:
    rubric = {"recency": 0.0, "citations": 0.0, "venue": 0.0}
    score = 0.5

    check = next((item for item in source_checks if item.citation_id == citation.citation_id), None)
    if check and check.publication_year:
        age_penalty = 0.1 if check.is_outdated else 0.0
        rubric["recency"] = 1.0 - age_penalty

    if llm:
        prompt = prompt_loader.load("citation_score", citation_text=citation.raw_text)
        response = await llm.complete(prompt=prompt, model=model_route.name, max_tokens=600)
        print(f"  [DEBUG Grader] Citation {citation.citation_id} raw response:\n{response}")
        if _is_llm_error(response):
            _record_error(error_sink, "llm", "llm_error", {"stage": "citation_score", "details": response})
            return score, rubric
        parsed = _safe_parse_json(response)
        if not parsed:
            parsed = _extract_scores_from_reasoning(response)
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
    error_sink: Optional[List[AgentError]],
) -> CoverageScore:
    if not claims:
        return CoverageScore(score=0.0, explanation="No claims provided.")

    if not llm:
        return CoverageScore(score=0.5, explanation="Coverage estimated without LLM.")

    logger.info("Grader: calling llm.complete for coverage scoring")
    prompt = prompt_loader.load(
        "coverage_score",
        claims_list=[claim.text for claim in claims],
        citations_list=[citation.raw_text for citation in citations],
    )
    response = await llm.complete(prompt=prompt, model=model_route.name, max_tokens=1024)
    print(f"  [DEBUG Grader] Coverage raw response:\n{response}")
    if _is_llm_error(response):
        _record_error(error_sink, "llm", "llm_error", {"stage": "coverage_score", "details": response})
        return CoverageScore(score=0.5, explanation="Coverage unavailable due to LLM error.")
    parsed = _safe_parse_json(response)
    if not parsed:
        return CoverageScore(score=0.5, explanation="Coverage could not be parsed.")

    claims_backed = [str(i) for i in parsed.get("supported_claim_ids", [])]
    claims_partial = [str(i) for i in parsed.get("partial_claim_ids", [])]
    claims_unbacked = [str(i) for i in parsed.get("unsupported_claim_ids", [])]
    claims_backed.extend(claims_partial)

    score = float(parsed.get("score", 0.5))
    explanation = parsed.get("explanation", "Coverage estimated from LLM reasoning.")
    return CoverageScore(score=score, explanation=explanation, claims_backed=claims_backed, claims_unbacked=claims_unbacked)


def _record_error(
    error_sink: Optional[List[AgentError]],
    tool_name: str,
    error_code: Optional[str],
    details: Any,
) -> None:
    if error_sink is None or not error_code:
        return
    if error_code == "not_found":
        return
    error_sink.append(
        AgentError(
            agent="grader",
            message=f"{tool_name} error: {error_code}",
            details={"error": error_code, "details": details},
        )
    )


def _is_llm_error(response: Any) -> bool:
    if not isinstance(response, str):
        return False
    return response.strip().lower().startswith("llm error:")