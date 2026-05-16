# Academic API tools (Person B → Person A)

All wrappers return a dict with **`success`: `true`/`false`**. On failure, **`error`** is one of the codes in `backend/tools/errors.py`.

## Error codes

| Code | Meaning | Agent recovery |
|------|---------|----------------|
| `not_found` | Resource absent (unknown DOI, no graph data) | Try OpenAlex search on `raw_text`; skip or flag citation |
| `rate_limited` | HTTP 429 after retries | Back off, retry later, or continue with partial data |
| `http_error` | Other HTTP failure | Retry once; log in `errors[]` |
| `parse_error` | Response not usable | Log; do not treat as “no results” |
| `metadata_not_found` | Crossref + OpenAlex both missed for DOI | Resolve via `search_openalex` / `search_arxiv` |
| `invalid_request` | Missing required arguments (e.g. empty arXiv search) | Fix query before retry |

**Important:** `not_found` ≠ generic failure — no results is a valid outcome; `http_error` / `rate_limited` need different handling.

## Branching examples

```python
meta = enrichment["metadata"]
if meta.get("error") == "metadata_not_found":
    ...
elif meta.get("error") == "rate_limited":
    ...

refs = enrichment["citations"].get("references", {})
if refs.get("error") == "not_found":
    ...
```

## `enrich_doi(doi)` shape

Top-level `success` is true if **any** of metadata, citation graph, or OA succeeded. Always inspect sub-objects:

- `metadata` — `fetch_doi_metadata` (Crossref → OpenAlex)
- `citations` — OpenCitations `references` + `citations` nested results
- `oa` — Unpaywall
- `partial_errors` — `{metadata, citations, oa}` → error code or `null`

## HTTP and caching

- All wrappers use `http_client.request_get()` (retries on 429 via the shared client).
- **`cache.memoize` stores only `success: true` results** — `not_found` and other errors are not cached, so repeated lookups re-hit the API.

## Granular tools

Prefer individual modules when the agent needs one capability: `crossref`, `openalex`, `arxiv`, `opencitations`, `unpaywall`.
