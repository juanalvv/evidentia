from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from .model_router import ModelRoute
from .schemas import AgentError, Claim, CounterArgument, CounterPaper
from .prompts.loader import prompt_loader
from ..memory.context_store import ContextStore

async def run_counter_research(
    claims: List[Claim],
    tools: Dict[str, Any],
    model_route: ModelRoute,
    context: ContextStore,
    error_sink: Optional[List[AgentError]] = None,
) -> List[CounterArgument]:
    semscholar = tools.get("semantic_scholar")
    openalex = tools.get("openalex")
    llm = tools.get("llm")

    results: List[CounterArgument] = []
    for claim in claims:
        query = await _build_query(claim.text, llm, model_route, error_sink)
        papers: List[CounterPaper] = []

        if semscholar:
            sem_result = await semscholar.search_opposing(query)
            papers.extend(_unwrap_tool_papers(sem_result, "semantic_scholar", error_sink))
        if openalex:
            oa_result = await openalex.search_opposing(query)
            papers.extend(_unwrap_tool_papers(oa_result, "openalex", error_sink))

        summary = await _summarize_counterarguments(claim.text, papers, llm, model_route, error_sink)
        results.append(CounterArgument(claim_id=claim.claim_id, summary=summary, papers=papers))

    context.set("counterarguments", [item.model_dump() for item in results])
    return results


async def _build_query(
    claim_text: str,
    llm: Any,
    model_route: ModelRoute,
    error_sink: Optional[List[AgentError]],
) -> str:
    if not llm:
        return claim_text
    prompt = prompt_loader.load("research_query", claim_text=claim_text)
    raw_query = await llm.complete(prompt=prompt, model=model_route.name, max_tokens=64)
    if _is_llm_error(raw_query):
        _record_error(error_sink, "llm", "llm_error", {"stage": "query", "details": raw_query})
        return claim_text
    cleaned = _clean_query(raw_query)
    return cleaned if cleaned else claim_text


def _clean_query(query: str) -> str:
    # 1. Try to extract content between <query> tags (best for wordy models)
    tag_match = re.search(r"<query>(.*?)</query>", query, re.DOTALL | re.IGNORECASE)
    if tag_match:
        return tag_match.group(1).strip().strip('"').strip("'")

    # 2. Strip leaked prompt instructions that restate the task
    # e.g. "We need to output a concise search query under 10 words that finds literature challenging... the claim: "X""
    leaked = re.match(
        r"(?:We need to|I need to|Let me|I will|To find).*?(?:claim|statement)[:\s]*[\"\"\"\'](.*?)[\"\"\"\']",
        query.strip(),
        re.DOTALL | re.IGNORECASE,
    )
    if leaked:
        # The model echoed the prompt but didn't produce an actual query — use the claim text as search basis
        return ""

    # 3. Fallback: Look for common labels
    labels = ["Query:", "Search query:", "Output:"]
    cleaned = query.strip().strip('"').strip("'")

    for label in labels:
        if cleaned.lower().startswith(label.lower()):
            cleaned = cleaned[len(label) :].strip().strip(":").strip()

    # 4. Strip common conversational prefixes
    prefixes = [
        "Here is the query:",
        "We need to find",
        "We need to output",
        "We need to produce",
        "Opposing evidence for",
        "Generate a concise academic search query",
        "A concise academic search query",
        "text:",
    ]
    for prefix in prefixes:
        if cleaned.lower().startswith(prefix.lower()):
            cleaned = cleaned[len(prefix) :].strip().strip(":").strip()

    # Final cleanup (take only the first line if it's still messy)
    cleaned = cleaned.split("\n")[0].strip().strip('"').strip("'")
    return cleaned


async def _summarize_counterarguments(
    claim_text: str,
    papers: List[CounterPaper],
    llm: Any,
    model_route: ModelRoute,
    error_sink: Optional[List[AgentError]],
) -> str:
    if not llm or not papers:
        return "No strong counterarguments found in current search results."

    titles = "\n".join(f"- {paper.title}" for paper in papers[:5])
    prompt = prompt_loader.load("counter_summary", claim_text=claim_text, titles=titles)
    response = await llm.complete(prompt=prompt, model=model_route.name, max_tokens=1024)
    if _is_llm_error(response):
        _record_error(error_sink, "llm", "llm_error", {"stage": "summary", "details": response})
        return "Counterargument summary unavailable due to LLM error."
    
    parsed = _safe_parse_json(response)
    if parsed and "summary" in parsed:
        return parsed["summary"]

    # Try to extract summary value even from truncated JSON
    summary_match = re.search(r'"summary"\s*:\s*"((?:[^"\\]|\\.)*)"?', response, re.DOTALL)
    if summary_match:
        return summary_match.group(1).rstrip('"')

    # Strip leading JSON wrapper if the model just wrapped plain text in braces
    stripped = response.strip()
    if stripped.startswith("{"):
        # Remove JSON boilerplate, return as plain text
        stripped = re.sub(r'^\{\s*"summary"\s*:\s*"?', '', stripped)
        stripped = re.sub(r'"?\s*\}?\s*$', '', stripped)
        if stripped:
            return stripped

    return response


def _safe_parse_json(response: str) -> Dict[str, Any]:
    try:
        import json
        # 1. Try direct parse
        return json.loads(response.strip())
    except Exception:
        pass

    try:
        import re
        # 2. Try extracting from markdown code blocks
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", response, re.DOTALL)
        if match:
            import json
            return json.loads(match.group(1).strip())
    except Exception:
        pass

    try:
        # 3. Try finding the first '{' and last '}'
        start = response.find("{")
        end = response.rfind("}")
        if start != -1 and end != -1:
            import json
            return json.loads(response[start : end + 1].strip())
    except Exception:
        pass

    return {}


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
            agent="counter_researcher",
            message=f"{tool_name} error: {error_code}",
            details={"error": error_code, "details": details},
        )
    )


def _is_llm_error(response: Any) -> bool:
    if not isinstance(response, str):
        return False
    return response.strip().lower().startswith("llm error:")


def _unwrap_tool_papers(
    result: Any,
    tool_name: str,
    error_sink: Optional[List[AgentError]],
) -> List[CounterPaper]:
    if isinstance(result, dict) and "success" in result:
        if result.get("success") is True:
            data = result.get("data")
            return _coerce_papers(data)
        _record_error(error_sink, tool_name, result.get("error"), result.get("details"))
        return []
    return _coerce_papers(result)


def _coerce_papers(items: Any) -> List[CounterPaper]:
    if not isinstance(items, list):
        return []
    papers: List[CounterPaper] = []
    for item in items:
        paper = _coerce_paper(item)
        if paper:
            papers.append(paper)
    return papers


def _coerce_paper(item: Any) -> Optional[CounterPaper]:
    if isinstance(item, CounterPaper):
        return item
    if not isinstance(item, dict):
        return None
    title = item.get("title") or item.get("display_name")
    if not isinstance(title, str) or not title:
        return None
    paper_id = item.get("paper_id") or item.get("id") or item.get("paperId") or title[:48]
    relevance_score = item.get("relevance_score")
    if relevance_score is None and isinstance(item.get("relevance"), (int, float)):
        relevance_score = float(item.get("relevance"))
    return CounterPaper(
        paper_id=paper_id,
        title=title,
        year=item.get("year"),
        venue=item.get("venue") or item.get("journal"),
        url=item.get("url"),
        abstract_snippet=item.get("abstract_snippet") or item.get("abstract"),
        relevance_score=relevance_score,
    )
