import os
import tempfile
from typing import Any, Dict, List, Optional
from uuid import uuid4
import logging

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.job_models import coerce_progress, new_job_document, progress_update
from backend.report.builder import build_report
from backend.tools.enrichment import enrich_doi
from backend.utils.analysis_stub import build_failed_analysis_result, build_ingestion_analysis_result
from backend.utils.errors import format_exception
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

# Basic logging configuration for agent activity
logging.basicConfig(level=logging.INFO)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: Dict[str, Dict[str, Any]] = {}


def _set_progress(
    job_id: str,
    phase: str,
    percent: int,
    message: str,
    agent: str = "orchestrator",
) -> None:
    """Update job progress (CONTRACT.md: phase, percent, message, agent)."""
    _save_job(job_id, {"progress": progress_update(phase, percent, message, agent)})


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
            try:
                enrichment = await enrich_doi(reference["doi"], email=email)
            except Exception as exc:
                enrichment = {
                    "success": False,
                    "doi": reference["doi"],
                    "error": "enrichment_failed",
                    "details": format_exception(exc),
                }
            doi_enrichment_results.append({"reference": reference, "enrichment": enrichment})
        pct = min(80, 10 + int(60 * index / max(1, total_refs)))
        _set_progress(job_id, "ingest", pct, "Processing references…", "orchestrator")

    analysis["doi_enrichments"] = doi_enrichment_results


async def _process_analysis_job(
    job_id: str,
    doi: Optional[str] = None,
    text: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    email: Optional[str] = None,
) -> None:
    try:
        _save_job(
            job_id,
            {
                "status": "running",
                "progress": progress_update("ingest", 5, "Starting ingestion…", "orchestrator"),
            },
        )

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
            _set_progress(job_id, "ingest", 15, "Enriching DOI…", "orchestrator")
            prepared = [prepare_reference_for_model(doi)]
            result["analysis"]["reference_entries"] = prepared
            result["analysis"]["doi_enrichment"] = await enrich_doi(doi, email=email)
            _persist_ingest(job_id, "", prepared, "text", result)

        else:
            raise ValueError("No input provided for analysis.")

        _set_progress(job_id, "analyze", 85, "Running agent pipeline…", "orchestrator")
        ingest = jobs[job_id].get("ingest")
        if not ingest:
            raise RuntimeError("Internal error: ingest payload missing after successful run.")
        analysis_result = await build_ingestion_analysis_result(
            job_id,
            ingest,
            result["analysis"],
            created_at_iso=str(jobs[job_id]["created_at"]),
        )
        analysis_result["markdown"] = build_report(analysis_result)["markdown"]
        _save_job(job_id, {"status": "completed", "result": result, "analysis_result": analysis_result})
    except Exception as exc:
        error_msg = format_exception(exc)
        _set_progress(job_id, "done", 100, error_msg, "orchestrator")
        failed = build_failed_analysis_result(
            job_id,
            error_msg,
            created_at_iso=str(jobs[job_id]["created_at"]),
        )
        failed["markdown"] = build_report(failed)["markdown"]
        _save_job(job_id, {"status": "failed", "error": error_msg, "analysis_result": failed})


@app.post("/analyze")
async def analyze(
    background_tasks: BackgroundTasks,
    doi: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    text: Optional[str] = Form(None),
    file: Optional[UploadFile] = File(None),
) -> Dict[str, Any]:
    """Queue ingestion / analysis. Returns job id and initial ``pending`` status (CONTRACT.md)."""
    if not any([doi, text, file]):
        raise HTTPException(status_code=400, detail="Provide a DOI, text, or PDF file to analyze.")

    file_bytes = None
    if file is not None:
        file_bytes = await file.read()
        if not file_bytes:
            raise HTTPException(status_code=400, detail="Uploaded file was empty.")

    job_id = str(uuid4())
    jobs[job_id] = new_job_document()
    background_tasks.add_task(_process_analysis_job, job_id, doi, text, file_bytes, email)

    return {"job_id": job_id, "status": "pending"}


@app.get("/status/{job_id}")
async def job_status(job_id: str) -> Dict[str, Any]:
    """Poll job state for the frontend (CONTRACT.md + SCHEMAS.md progress block)."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    return {
        "job_id": job_id,
        "status": job["status"],
        "progress": coerce_progress(job),
        "error": job["error"],
    }


@app.get("/report/{job_id}")
async def job_report(job_id: str) -> Dict[str, Any]:
    """Return SCHEMAS.md Final AnalysisResult when the job has finished (success or failure)."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    status = job["status"]
    if status in ("pending", "running"):
        return JSONResponse(
            status_code=202,
            content={
                "job_id": job_id,
                "status": status,
                "progress": coerce_progress(job),
                "error": job["error"],
                "result": job["result"],
            },
        )
    analysis_result = job.get("analysis_result")
    if status == "failed":
        if not analysis_result:
            analysis_result = build_failed_analysis_result(
                job_id,
                job.get("error") or "Unknown error",
                created_at_iso=str(job["created_at"]),
            )
            analysis_result["markdown"] = build_report(analysis_result)["markdown"]
        return analysis_result
    if not analysis_result:
        raise HTTPException(
            status_code=500,
            detail="Completed job is missing analysis_result; this is a server bug.",
        )
    return analysis_result


@app.post("/report/build")
async def report_build(payload: Dict[str, Any]) -> Dict[str, str]:
    """Render markdown from a Final AnalysisResult JSON body (SCHEMAS.md)."""
    return build_report(payload)
