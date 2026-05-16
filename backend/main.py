import asyncio
import os
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.tools.enrichment import enrich_doi
from backend.utils.citation_extractor import prepare_reference_for_model
from backend.utils.ingest import SourceKind, build_submission_payload
from backend.utils.pdf_parser import parse_pdf, parse_text

_DEFAULT_CORS_ORIGINS = (
    "http://localhost:8080",
    "http://127.0.0.1:8080",
)


def _cors_origins() -> List[str]:
    origins = list(_DEFAULT_CORS_ORIGINS)
    extra = os.getenv("CORS_ORIGINS", "")
    if extra:
        origins.extend(part.strip() for part in extra.split(",") if part.strip())
    return origins


app = FastAPI(title="Evidentia Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: Dict[str, Dict[str, Any]] = {}


def _create_job() -> Dict[str, Any]:
    return {
        "status": "pending",
        "progress": 0,
        "created_at": datetime.utcnow().isoformat() + "Z",
        "ingest": None,
        "result": None,
        "error": None,
    }


def _persist_ingest(
    job_id: str,
    full_text: str,
    prepared_references: List[Dict[str, Any]],
    source: SourceKind,
    result: Dict[str, Any],
) -> Dict[str, Any]:
    ingest = build_submission_payload(job_id, full_text, prepared_references, source)
    _save_job(job_id, {"ingest": ingest})
    result["ingest"] = ingest
    return ingest


def _save_job(job_id: str, updates: Dict[str, Any]) -> None:
    job = jobs.get(job_id)
    if not job:
        return
    job.update(updates)


def _prepare_all_references(reference_entries: List[str]) -> List[Dict[str, Any]]:
    """Prepare every bibliography entry for agents (raw text + optional DOI/year)."""
    return [prepare_reference_for_model(entry) for entry in reference_entries]


def _write_temp_pdf(file_bytes: bytes) -> str:
    fd, path = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    with open(path, "wb") as output_file:
        output_file.write(file_bytes)
    return path


async def _ingest_references(
    job_id: str,
    raw_reference_entries: List[str],
    analysis: Dict[str, Any],
    email: Optional[str] = None,
) -> None:
    """Prepare all citations and enrich DOI-bearing references into analysis."""
    reference_models = _prepare_all_references(raw_reference_entries)
    analysis["reference_entries"] = reference_models

    doi_enrichment_results = []
    total_refs = len(reference_models)
    for index, reference in enumerate(reference_models, start=1):
        if reference.get("doi"):
            enrichment = await enrich_doi(reference["doi"], email=email)
            doi_enrichment_results.append({"reference": reference, "enrichment": enrichment})
        _save_job(job_id, {"progress": min(80, 10 + int(60 * index / max(1, total_refs)))})

    analysis["doi_enrichments"] = doi_enrichment_results


async def _process_analysis_job(
    job_id: str,
    doi: Optional[str] = None,
    text: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    email: Optional[str] = None,
) -> None:
    try:
        _save_job(job_id, {"status": "running", "progress": 5})

        result: Dict[str, Any] = {
            "input": {"doi": doi, "text_provided": bool(text), "file_provided": bool(file_bytes), "email": email},
            "analysis": {},
        }

        if file_bytes is not None:
            pdf_path = _write_temp_pdf(file_bytes)
            try:
                parsed = parse_pdf(pdf_path)
            finally:
                os.unlink(pdf_path)

            result["analysis"]["pdf"] = parsed
            await _ingest_references(
                job_id,
                parsed.get("reference_entries", []),
                result["analysis"],
                email=email,
            )
            _persist_ingest(
                job_id,
                str(parsed.get("full_text", "")),
                result["analysis"]["reference_entries"],
                "pdf",
                result,
            )

        elif text is not None:
            parsed = parse_text(text)
            result["analysis"]["text"] = parsed
            await _ingest_references(
                job_id,
                parsed.get("reference_entries", []),
                result["analysis"],
                email=email,
            )
            _persist_ingest(
                job_id,
                str(parsed.get("full_text", "")),
                result["analysis"]["reference_entries"],
                "text",
                result,
            )

        elif doi is not None:
            prepared = [prepare_reference_for_model(doi)]
            result["analysis"]["reference_entries"] = prepared
            result["analysis"]["doi_enrichment"] = await enrich_doi(doi, email=email)
            _persist_ingest(job_id, "", prepared, "text", result)

        else:
            raise ValueError("No input provided for analysis.")

        _save_job(job_id, {"status": "finished", "progress": 100, "result": result})
    except Exception as exc:
        _save_job(job_id, {"status": "failed", "progress": 100, "error": str(exc)})


@app.post("/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    doi: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    if not any([doi, text, file]):
        raise HTTPException(status_code=400, detail="Provide a DOI, text, or PDF file to analyze.")

    file_bytes = None
    if file is not None:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file was empty.")

    job_id = str(uuid4())
    jobs[job_id] = _create_job()
    background_tasks.add_task(_process_analysis_job, job_id, doi, text, file_bytes, email)

    return {"job_id": job_id, "status": jobs[job_id]["status"]}


@app.get("/status/{job_id}")
async def job_status(job_id: str) -> Dict[str, Any]:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": job["progress"],
        "error": job["error"],
    }


@app.get("/report/{job_id}")
async def job_report(job_id: str) -> Dict[str, Any]:
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    if job["status"] != "finished":
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "status": job["status"],
                "progress": job["progress"],
                "error": job["error"],
                "result": job["result"],
            },
        )
    return {"job_id": job_id, "status": job["status"], "progress": job["progress"], "result": job["result"]}
