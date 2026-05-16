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
  setGauges(payload.overall_scores);
  renderCitationGrades(payload.citations);

  let markdown = payload.markdown;
  if (!markdown) {
    markdown = await fetchMarkdownFromPayload(payload);
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
