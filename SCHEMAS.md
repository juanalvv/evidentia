# ScholarCounter Schemas

This document defines the JSON contracts between Person A (agents), Person B (tools/backend), and Person C (report builder).

## Input Payload

```json
{
  "submission_id": "string",
  "claims": [
    {
      "claim_id": "string",
      "text": "string"
    }
  ],
  "citations": [
    {
      "citation_id": "string",
      "raw_text": "string",
      "title": "string",
      "authors": ["string"],
      "year": 2021,
      "doi": "string",
      "journal": "string"
    }
  ],
  "full_text": "string",
  "metadata": {
    "source": "pdf|text",
    "title": "string",
    "authors": ["string"]
  }
}
```

## SourceCheck Output

```json
{
  "citation_id": "string",
  "normalized_title": "string",
  "normalized_doi": "string",
  "publication_year": 2021,
  "is_outdated": false,
  "contradiction_signals": ["string"],
  "evidence": ["string"]
}
```

## CounterArgument Output

```json
{
  "claim_id": "string",
  "summary": "string",
  "papers": [
    {
      "paper_id": "string",
      "title": "string",
      "year": 2021,
      "venue": "string",
      "url": "string",
      "abstract_snippet": "string",
      "relevance_score": 0.0
    }
  ]
}
```

## Grader Output

```json
{
  "source_quality": [
    {
      "citation_id": "string",
      "score": 0.0,
      "rubric": {
        "recency": 0.0,
        "citations": 0.0,
        "venue": 0.0
      }
    }
  ],
  "coverage": {
    "score": 0.0,
    "explanation": "string",
    "claims_backed": ["claim_id"],
    "claims_unbacked": ["claim_id"]
  }
}
```

## Audit Event

```json
{
  "event_type": "policy_block|policy_allow|tool_call",
  "status": "denied|allowed|error",
  "detail": "string",
  "metadata": {}
}
```

## Orchestrator Output

```json
{
  "submission_id": "string",
  "source_checks": [],
  "counterarguments": [],
  "grader": {},
  "audit_events": [],
  "errors": [
    {
      "agent": "string",
      "message": "string",
      "details": {}
    }
  ],
  "raw": {
    "duration_seconds": 0.0
  }
}
```
