from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class Citation(BaseModel):
    citation_id: str
    raw_text: str
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    doi: Optional[str] = None
    journal: Optional[str] = None


class Claim(BaseModel):
    claim_id: str
    text: str


class InputPayload(BaseModel):
    submission_id: str
    claims: List[Claim]
    citations: List[Citation]
    full_text: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class AgentError(BaseModel):
    agent: str
    message: str
    details: Optional[Dict[str, Any]] = None


class SourceCheck(BaseModel):
    citation_id: str
    normalized_title: Optional[str] = None
    normalized_doi: Optional[str] = None
    publication_year: Optional[int] = None
    is_outdated: bool = False
    contradiction_signals: List[str] = Field(default_factory=list)
    evidence: List[str] = Field(default_factory=list)


class CounterPaper(BaseModel):
    paper_id: str
    title: str
    year: Optional[int] = None
    venue: Optional[str] = None
    url: Optional[str] = None
    abstract_snippet: Optional[str] = None
    relevance_score: Optional[float] = None


class CounterArgument(BaseModel):
    claim_id: str
    summary: str
    papers: List[CounterPaper] = Field(default_factory=list)


class SourceQualityScore(BaseModel):
    citation_id: str
    score: float
    rubric: Dict[str, Any] = Field(default_factory=dict)


class CoverageScore(BaseModel):
    score: float
    explanation: str
    claims_backed: List[str] = Field(default_factory=list)
    claims_unbacked: List[str] = Field(default_factory=list)


class GraderOutput(BaseModel):
    source_quality: List[SourceQualityScore] = Field(default_factory=list)
    coverage: Optional[CoverageScore] = None


class AuditEvent(BaseModel):
    event_type: str
    status: str
    detail: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class OrchestratorOutput(BaseModel):
    submission_id: str
    source_checks: List[SourceCheck] = Field(default_factory=list)
    counterarguments: List[CounterArgument] = Field(default_factory=list)
    grader: Optional[GraderOutput] = None
    audit_events: List[AuditEvent] = Field(default_factory=list)
    errors: List[AgentError] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)
