from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from .model_router import ModelRouter
from .schemas import AgentError, AuditEvent, CounterArgument, GraderOutput, InputPayload, OrchestratorOutput, SourceCheck
from .source_checker import run_source_check
from .counter_researcher import run_counter_research
from .grader import run_grader
from ..memory.context_store import ContextStore


class Orchestrator:
    """Runs the NemoClaw agent pipeline and aggregates outputs."""

    def __init__(
        self,
        model_router: ModelRouter,
        tools: Dict[str, Any],
        context_store: ContextStore,
        blocked_action_cb: Optional[Any] = None,
    ) -> None:
        self._router = model_router
        self._tools = tools
        self._context = context_store
        self._blocked_action_cb = blocked_action_cb

    async def run(self, payload: InputPayload) -> OrchestratorOutput:
        started = time.time()
        output = OrchestratorOutput(submission_id=payload.submission_id)
        errors: List[AgentError] = []

        self._context.set("submission_id", payload.submission_id)
        self._context.set("claims", [claim.model_dump() for claim in payload.claims])
        self._context.set("citations", [citation.model_dump() for citation in payload.citations])

        try:
            source_checks = await run_source_check(
                payload.citations,
                tools=self._tools,
                model_route=self._router.for_reasoning(),
                context=self._context,
                error_sink=errors,
            )
            output.source_checks = source_checks
        except Exception as exc:  # pragma: no cover - runtime safety net
            errors.append(AgentError(agent="source_checker", message=str(exc)))

        try:
            counterarguments = await run_counter_research(
                payload.claims,
                tools=self._tools,
                model_route=self._router.for_reasoning(),
                context=self._context,
                error_sink=errors,
            )
            output.counterarguments = counterarguments
        except Exception as exc:  # pragma: no cover - runtime safety net
            errors.append(AgentError(agent="counter_researcher", message=str(exc)))

        try:
            grader = await run_grader(
                payload.claims,
                payload.citations,
                output.source_checks,
                tools=self._tools,
                model_route_reasoning=self._router.for_reasoning(),
                model_route_scoring=self._router.for_scoring(),
                context=self._context,
                error_sink=errors,
            )
            output.grader = grader
        except Exception as exc:  # pragma: no cover - runtime safety net
            errors.append(AgentError(agent="grader", message=str(exc)))

        if self._blocked_action_cb:
            audit_event = self._blocked_action_cb()
            if audit_event:
                output.audit_events.append(audit_event)

        output.errors = errors
        output.raw["duration_seconds"] = round(time.time() - started, 2)
        return output


def blocked_action_stub() -> AuditEvent:
    """Fallback blocked-action event for demos when NemoClaw audit logs are not wired yet."""

    return AuditEvent(
        event_type="policy_block",
        status="denied",
        detail="Attempted to access forbidden domain example.invalid",
        metadata={"domain": "example.invalid"},
    )
