# Evidentia Schemas

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

## Final AnalysisResult / Report Payload

This is the normalized payload that `backend/report/builder.py` and `frontend/app.js` expect. Person A/B can produce richer internal objects, but the backend should adapt them to this shape before returning `/report/{job_id}` or calling the report builder.

```json
{
  "job_id": "string",
  "status": "completed|failed|running",
  "paper": {
    "title": "string",
    "authors": ["string"],
    "uploaded_at": "ISO-8601 timestamp"
  },
  "progress": {
    "phase": "ingest|source_check|counter_research|grading|report|done",
    "percent": 100,
    "message": "string",
    "agent": "orchestrator|source_checker|counter_researcher|grader"
  },
  "executive_summary": "string",
  "overall_scores": {
    "source_quality": 0.0,
    "coverage": 0.0,
    "data_quality": 0.0
  },
  "citations": [
    {
      "id": "cite-1",
      "authors": "string",
      "title": "string",
      "year": 2021,
      "doi": "string|null",
      "journal": "string",
      "source_quality_score": 0.0,
      "recency_flag": "stale|ok|recent",
      "superseded_notes": "string|null",
      "superseded_by": [
        {
          "title": "string",
          "year": 2021,
          "doi": "string|null"
        }
      ]
    }
  ],
  "claims": [
    {
      "id": "claim-1",
      "text": "string",
      "section": "string",
      "cited_source_ids": ["cite-1"],
      "coverage_score": 0.0,
      "counterarguments": [
        {
          "summary": "string",
          "papers": [
            {
              "title": "string",
              "authors": "string",
              "year": 2021,
              "doi": "string|null",
              "url": "string|null",
              "relevance": "string"
            }
          ]
        }
      ],
      "supporting_sources": [
        {
          "title": "string",
          "authors": "string",
          "year": 2021,
          "doi": "string|null",
          "note": "string"
        }
      ]
    }
  ],
  "data_quality": {
    "score": 0.0,
    "summary": "string",
    "comparisons": [
      {
        "aspect": "string",
        "paper_value": "string",
        "field_norm": "string",
        "verdict": "below_norm|ok|strong"
      }
    ]
  },
  "final_verdict": {
    "status": "Ready to submit|Needs citation revision|Needs major evidence work|Needs to improve methods & data processes",
    "summary": "string",
    "rationale": ["string"],
    "next_steps": ["string"]
  },
  "markdown": "string|null",
  "errors": []
}
```

### Required Fields For Person C

At minimum, the frontend/report can render a useful result with:

- `paper.title`
- `executive_summary`
- `overall_scores.source_quality`
- `overall_scores.coverage`
- `overall_scores.data_quality`
- `citations[]`
- `claims[]`
- `data_quality`
- `final_verdict`

If `markdown` is missing, `frontend/app.js` can build a small fallback summary client-side. If `final_verdict` is missing, the frontend computes a fallback verdict from `overall_scores`, weak citations, stale citations, and data quality.

### Mapping Notes

- `metadata.title` from the input payload maps to `paper.title`.
- `metadata.authors` maps to `paper.authors`.
- `citation_id` maps to `citations[].id`.
- `grader.source_quality[].score` maps to `citations[].source_quality_score`.
- `grader.coverage.score` maps to `overall_scores.coverage`.
- `SourceCheck.is_outdated` maps to `citations[].recency_flag` (`stale` when true, otherwise `ok` or `recent`).
- `CounterArgument` objects should be grouped under the matching `claims[].counterarguments[]`.
