const API = window.SCHOLAR_COUNTER_API || "";
const MOCK_FIXTURE = "../backend/report/fixtures/mock_analysis.json";

const AGENT_STEPS = [
  { phase: "ingest", label: "Ingesting document", agent: "orchestrator" },
  { phase: "source_check", label: "Checking citations & recency", agent: "source_checker" },
  { phase: "counter_research", label: "Finding opposing literature", agent: "counter_researcher" },
  { phase: "grading", label: "Grading sources & data", agent: "grader" },
  { phase: "report", label: "Building report", agent: "orchestrator" },
  { phase: "done", label: "Complete", agent: "orchestrator" },
];

const $ = (sel) => document.querySelector(sel);

function normalizePayload(payload) {
  if (!payload || typeof payload !== "object") return payload;
  if (payload.source_checks || payload.counterarguments || payload.grader) {
    return buildFromOrchestrator(payload);
  }
  return payload;
}

function buildFromOrchestrator(payload) {
  const nowIso = new Date().toISOString();
  const metadata = payload.metadata || {};
  const authors = metadata.authors;
  const normalizedAuthors = Array.isArray(authors) ? authors : authors ? [authors] : [];
  const paper = payload.paper || {
    title: metadata.title || "Untitled",
    authors: normalizedAuthors,
    uploaded_at: nowIso,
  };

  const sourceChecks = Array.isArray(payload.source_checks) ? payload.source_checks : [];
  const citationsInput = Array.isArray(payload.citations) ? payload.citations : [];
  const claimsInput = Array.isArray(payload.claims) ? payload.claims : [];

  const scoreList = payload.grader?.source_quality || [];
  const coverage = payload.grader?.coverage || null;
  const coverageScore = coverage?.score ?? null;

  const scoresByCitation = new Map(scoreList.map((s) => [s.citation_id, s.score]));
  const checksByCitation = new Map(sourceChecks.map((c) => [c.citation_id, c]));

  const citations = buildCitations(citationsInput, sourceChecks, scoresByCitation, checksByCitation);
  const counterMap = buildCounterMap(payload.counterarguments || []);
  const claims = buildClaims(claimsInput, counterMap, coverage, coverageScore);

  const sourceQuality = average(scoreList.map((s) => s.score));
  const dataQualityScore = payload.data_quality?.score ?? null;
  const overallScores = {
    source_quality: sourceQuality,
    coverage: coverageScore,
    data_quality: dataQualityScore,
  };

  const summary = payload.executive_summary || buildExecutiveSummary(overallScores);

  return {
    job_id: payload.job_id || payload.submission_id || "job-unknown",
    status: payload.status || "completed",
    paper,
    progress: payload.progress || { phase: "done", percent: 100, message: "Complete", agent: "orchestrator" },
    executive_summary: summary,
    overall_scores: overallScores,
    citations,
    claims,
    data_quality: payload.data_quality || {
      score: dataQualityScore,
      summary: "Data quality scoring not available yet.",
      comparisons: [],
    },
    final_verdict: payload.final_verdict || null,
    markdown: payload.markdown || null,
    errors: payload.errors || [],
  };
}

function buildCitations(citationsInput, sourceChecks, scoresByCitation, checksByCitation) {
  const rows = [];

  if (!citationsInput.length && sourceChecks.length) {
    for (const check of sourceChecks) {
      const year = check.publication_year ?? null;
      rows.push({
        id: check.citation_id,
        authors: "",
        title: check.normalized_title || "Untitled",
        year,
        doi: check.normalized_doi || null,
        journal: null,
        source_quality_score: scoresByCitation.get(check.citation_id) ?? null,
        recency_flag: deriveRecencyFlag(check.is_outdated, year),
        superseded_notes: null,
        superseded_by: [],
      });
    }
    return rows;
  }

  for (const citation of citationsInput) {
    const check = checksByCitation.get(citation.citation_id);
    const year = citation.year ?? check?.publication_year ?? null;
    rows.push({
      id: citation.citation_id,
      authors: normalizeAuthors(citation.authors),
      title: citation.title || check?.normalized_title || "Untitled",
      year,
      doi: citation.doi || check?.normalized_doi || null,
      journal: citation.journal || null,
      source_quality_score: scoresByCitation.get(citation.citation_id) ?? null,
      recency_flag: deriveRecencyFlag(check?.is_outdated, year),
      superseded_notes: null,
      superseded_by: [],
    });
  }
  return rows;
}

function buildCounterMap(counterarguments) {
  const map = new Map();
  for (const entry of counterarguments) {
    const claimId = entry.claim_id || "unknown";
    const papers = (entry.papers || []).map((paper) => ({
      title: paper.title || "Untitled",
      authors: normalizeAuthors(paper.authors) || "",
      year: paper.year ?? null,
      doi: paper.doi ?? null,
      url: paper.url ?? null,
      relevance: paper.relevance || (paper.relevance_score != null ? String(paper.relevance_score) : ""),
    }));
    const normalized = { summary: entry.summary || "", papers };
    if (!map.has(claimId)) map.set(claimId, []);
    map.get(claimId).push(normalized);
  }
  return map;
}

function buildClaims(claimsInput, counterMap, coverage, coverageScore) {
  const claimsBacked = new Set(coverage?.claims_backed || []);
  const claimsUnbacked = new Set(coverage?.claims_unbacked || []);
  const rows = [];

  const claimIds = claimsInput.length
    ? claimsInput.map((claim) => claim.claim_id)
    : Array.from(counterMap.keys());

  for (const claimId of claimIds) {
    const claim = claimsInput.find((item) => item.claim_id === claimId) || {};
    rows.push({
      id: claimId,
      text: claim.text || "",
      section: claim.section || "Claim",
      cited_source_ids: claim.cited_source_ids || [],
      coverage_score: deriveClaimCoverage(claimId, claimsBacked, claimsUnbacked, coverageScore),
      counterarguments: counterMap.get(claimId) || [],
      supporting_sources: claim.supporting_sources || [],
    });
  }
  return rows;
}

function deriveClaimCoverage(claimId, claimsBacked, claimsUnbacked, fallback) {
  if (claimsBacked.has(claimId)) return 1.0;
  if (claimsUnbacked.has(claimId)) return 0.0;
  return fallback ?? null;
}

function buildExecutiveSummary(overall) {
  if (!overall) return "";
  const parts = [];
  if (overall.source_quality != null) {
    parts.push(`Average source quality: ${Math.round(overall.source_quality * 100)}%.`);
  }
  if (overall.coverage != null) {
    parts.push(`Coverage score: ${Math.round(overall.coverage * 100)}%.`);
  }
  if (overall.data_quality != null) {
    parts.push(`Data quality score: ${Math.round(overall.data_quality * 100)}%.`);
  }
  if (!parts.length) return "";
  parts.push("Data quality details are pending.");
  return parts.join(" ");
}

function normalizeAuthors(authors) {
  if (!authors) return "";
  if (Array.isArray(authors)) return authors.filter(Boolean).join(", ");
  return String(authors);
}

function deriveRecencyFlag(isOutdated, year) {
  if (isOutdated) return "stale";
  const currentYear = new Date().getFullYear();
  if (typeof year === "number" && currentYear - year <= 2) return "recent";
  return "ok";
}

function average(values) {
  const filtered = values.filter((v) => typeof v === "number" && !Number.isNaN(v));
  if (!filtered.length) return null;
  const total = filtered.reduce((sum, v) => sum + v, 0);
  return total / filtered.length;
}

function scoreColor(score) {
  if (score == null || Number.isNaN(score)) return "neutral";
  if (score >= 0.7) return "good";
  if (score >= 0.45) return "warn";
  return "bad";
}

function setGauges(overall) {
  const panel = $("#scores-panel");
  if (!overall) {
    panel.classList.add("hidden");
    return;
  }
  panel.classList.remove("hidden");
  for (const el of panel.querySelectorAll(".gauge")) {
    const key = el.dataset.metric;
    const val = overall[key];
    const pct = val != null ? Math.round(val * 100) : null;
    const fill = el.querySelector(".gauge-fill");
    const label = el.querySelector(".gauge-value");
    fill.style.width = pct != null ? `${pct}%` : "0%";
    fill.className = `gauge-fill ${scoreColor(val)}`;
    label.textContent = pct != null ? `${pct}%` : "—";
  }
}

function renderCitationGrades(citations) {
  const root = $("#citation-grades");
  if (!citations?.length) {
    root.classList.add("hidden");
    root.innerHTML = "";
    return;
  }
  root.classList.remove("hidden");
  root.innerHTML = "<h3>Per-citation grades</h3>";
  const list = document.createElement("ul");
  list.className = "citation-list";
  for (const c of citations) {
    const li = document.createElement("li");
    const sq = c.source_quality_score;
    const pct = sq != null ? Math.round(sq * 100) : "—";
    li.className = `citation-item ${scoreColor(sq)}`;
    li.innerHTML = `
      <span class="citation-title">${escapeHtml(c.title || "Untitled")} (${c.year ?? "?"})</span>
      <span class="citation-bar-wrap"><span class="citation-bar ${scoreColor(sq)}" style="width:${sq != null ? sq * 100 : 0}%"></span></span>
      <span class="citation-pct">${pct}%</span>
      <span class="citation-flag">${escapeHtml(c.recency_flag || "")}</span>
    `;
    list.appendChild(li);
  }
  root.appendChild(list);
}

function escapeHtml(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderMarkdownReport(markdown) {
  const article = $("#report-content");
  article.innerHTML = typeof marked !== "undefined" ? marked.parse(markdown) : `<pre>${escapeHtml(markdown)}</pre>`;
}

async function fetchMarkdownFromPayload(payload) {
  if (payload.markdown) return payload.markdown;
  const res = await fetch(`${API}/report/build`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  }).catch(() => null);
  if (res?.ok) {
    const data = await res.json();
    return data.markdown;
  }
  return buildMarkdownClientSide(payload);
}

function buildMarkdownClientSide(payload) {
  const lines = [];
  lines.push(`# ${payload.paper?.title || "Report"}`);
  if (payload.executive_summary) {
    lines.push("\n## Executive summary\n" + payload.executive_summary);
  }
  const s = payload.overall_scores || {};
  lines.push("\n## Overall grades");
  lines.push(`- Source quality: ${fmtPct(s.source_quality)}`);
  lines.push(`- Coverage: ${fmtPct(s.coverage)}`);
  lines.push(`- Data quality: ${fmtPct(s.data_quality)}`);
  return lines.join("\n");
}

function fmtPct(v) {
  return v != null ? `${Math.round(v * 100)}%` : "—";
}

function updateProgress(progress) {
  const panel = $("#progress-panel");
  panel.classList.remove("hidden");
  const pct = progress?.percent ?? 0;
  $("#progress-bar").style.width = `${pct}%`;
  $("#progress-message").textContent = progress?.message || "Working…";

  const ul = $("#agent-steps");
  ul.innerHTML = "";
  const currentPhase = progress?.phase || "ingest";
  const currentIdx = AGENT_STEPS.findIndex((s) => s.phase === currentPhase);

  AGENT_STEPS.forEach((step, i) => {
    const li = document.createElement("li");
    let state = "pending";
    if (i < currentIdx || currentPhase === "done") state = "done";
    else if (i === currentIdx) state = "active";
    li.className = state;
    li.textContent = step.label;
    ul.appendChild(li);
  });
}

async function displayAnalysisResult(payload) {
  const normalized = normalizePayload(payload);
  setGauges(normalized.overall_scores);
  renderCitationGrades(normalized.citations);

  let markdown = normalized.markdown;
  if (!markdown) {
    try {
      const mod = await import("../backend/report/builder.py");
      void mod;
    } catch {
      /* frontend-only fallback */
    }
    markdown = buildMarkdownClientSide(normalized);
    if (normalized.claims?.length) {
      markdown += "\n\n*Full report will render when Person B wires `GET /report/{id}` with `markdown` from `builder.py`.*";
    }
  }
  renderMarkdownReport(markdown);
}

const MOCK_MARKDOWN = "../backend/report/fixtures/mock_report.md";

async function loadMock() {
  const res = await fetch(MOCK_FIXTURE);
  const payload = await res.json();
  try {
    const mdRes = await fetch(MOCK_MARKDOWN);
    if (mdRes.ok) payload.markdown = await mdRes.text();
  } catch {
    /* optional */
  }
  updateProgress({ phase: "done", percent: 100, message: "Demo data loaded", agent: "orchestrator" });
  await displayAnalysisResult(payload);
}

async function pollUntilDone(jobId) {
  const intervalMs = 1500;
  for (;;) {
    const res = await fetch(`${API}/status/${jobId}`);
    if (!res.ok) throw new Error(`Status failed: ${res.status}`);
    const status = await res.json();
    updateProgress(status.progress || { percent: 0, message: "Running…" });
    if (status.status === "completed") break;
    if (status.status === "failed") throw new Error(status.error || "Analysis failed");
    await new Promise((r) => setTimeout(r, intervalMs));
  }
  const reportRes = await fetch(`${API}/report/${jobId}`);
  if (!reportRes.ok) throw new Error(`Report failed: ${reportRes.status}`);
  return reportRes.json();
}

async function startAnalyze(formData) {
  $("#btn-analyze").disabled = true;
  updateProgress({ phase: "ingest", percent: 5, message: "Uploading…", agent: "orchestrator" });
  try {
    const res = await fetch(`${API}/analyze`, { method: "POST", body: formData });
    if (!res.ok) throw new Error(`Analyze failed: ${res.status}`);
    const { job_id: jobId } = await res.json();
    const payload = await pollUntilDone(jobId);
    await displayAnalysisResult(payload);
  } finally {
    $("#btn-analyze").disabled = false;
  }
}

$("#analyze-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const file = $("#pdf-file").files[0];
  const text = $("#paper-text").value.trim();
  if (!file && !text) {
    alert("Upload a PDF or paste text.");
    return;
  }
  const fd = new FormData();
  if (file) fd.append("file", file);
  if (text) fd.append("text", text);

  if (!API && !window.SCHOLAR_COUNTER_USE_MOCK) {
    alert("Backend not configured yet. Use “Load demo report” or set SCHOLAR_COUNTER_API in config.js.");
    return;
  }
  await startAnalyze(fd);
});

$("#btn-mock").addEventListener("click", () => loadMock());

// Auto-load mock when opened via file:// or for quick judge preview
if (window.location.search.includes("demo=1")) {
  loadMock();
}
