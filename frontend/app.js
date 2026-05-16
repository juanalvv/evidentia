const API = window.EVIDENTIA_API || "";
const MOCK_FIXTURE = "../backend/report/fixtures/mock_analysis.json";
const SAVED_PAPERS_KEY = "evidentia.savedPapers.v1";

const AGENT_STEPS = [
  { phase: "ingest", label: "Ingesting document", agent: "orchestrator" },
  { phase: "source_check", label: "Checking citations & recency", agent: "source_checker" },
  { phase: "counter_research", label: "Finding opposing literature", agent: "counter_researcher" },
  { phase: "grading", label: "Grading sources & data", agent: "grader" },
  { phase: "report", label: "Building report", agent: "orchestrator" },
  { phase: "done", label: "Complete", agent: "orchestrator" },
];

const $ = (sel) => document.querySelector(sel);
let activeInputMeta = null;

function showWorkspace({ fromLibrary = false, state = "loading" } = {}) {
  $("#composer-screen")?.classList.add("compact", "collapsed");
  $("#papers-library")?.classList.add("hidden");
  const workspace = $("#analysis-workspace");
  workspace?.classList.remove("hidden", "loading", "report-ready");
  workspace?.classList.add(state);
  $("#btn-back-library-top")?.classList.toggle("hidden", !fromLibrary);
  updateComposerSummary();
  resizeComposerInput();
}

function showLibrary() {
  $("#analysis-workspace")?.classList.add("hidden");
  $("#papers-library")?.classList.remove("hidden");
  $("#composer-screen")?.classList.remove("compact", "collapsed");
  $("#btn-back-library-top")?.classList.add("hidden");
  renderPapersLibrary();
}

function expandComposer() {
  $("#composer-screen")?.classList.remove("collapsed");
  resizeComposerInput();
  $("#paper-text")?.focus();
}

function collapseComposer() {
  const screen = $("#composer-screen");
  if (!screen?.classList.contains("compact")) return;
  updateComposerSummary();
  screen.classList.add("collapsed");
}

function updateComposerSummary(label) {
  const summary = $("#summary-text");
  if (!summary) return;
  const file = $("#pdf-file")?.files[0];
  const text = $("#paper-text")?.value.trim();
  const shortText = text ? text.replace(/\s+/g, " ").slice(0, 110) : "";
  const kind = label ? "Demo" : file ? "PDF" : text ? "Text" : "Input";
  const kindEl = document.querySelector(".summary-kind");
  if (kindEl) kindEl.textContent = kind;
  summary.textContent = label || shortText || file?.name || "Demo report loaded";
}

function getCurrentInputMeta(kindOverride) {
  const file = $("#pdf-file")?.files[0];
  const text = $("#paper-text")?.value.trim();
  const kind = kindOverride || (file ? "PDF" : text ? "Text" : "Demo");
  const title = file?.name || text?.replace(/\s+/g, " ").slice(0, 80) || "Demo report";
  return { kind, title };
}

function resizeComposerInput() {
  const input = $("#paper-text");
  if (!input) return;
  const isCompact = $("#composer-screen")?.classList.contains("compact");
  const maxHeight = isCompact ? 150 : 260;
  input.style.height = "auto";
  input.style.height = `${Math.min(input.scrollHeight, maxHeight)}px`;
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
    const ring = el.querySelector(".score-ring");
    const label = el.querySelector(".gauge-value");
    ring.style.setProperty("--score", pct != null ? pct : 0);
    ring.className = `score-ring ${scoreColor(val)}`;
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
  const list = document.createElement("div");
  list.className = "citation-list";
  for (const c of citations) {
    const item = document.createElement("article");
    const sq = c.source_quality_score;
    const pct = sq != null ? Math.round(sq * 100) : "—";
    const color = scoreColor(sq);
    item.className = `citation-item ${color}`;
    item.innerHTML = `
      <div class="citation-main">
        <div>
          <h4 class="citation-title">${escapeHtml(c.title || "Untitled")}</h4>
          <p class="citation-meta">${escapeHtml(c.authors || "Unknown authors")} · ${escapeHtml(c.journal || "Unknown venue")} · ${c.year ?? "?"}</p>
        </div>
        <div class="citation-score ${color}">
          <strong>${pct}%</strong>
          <span>${escapeHtml(c.recency_flag || "unknown")}</span>
        </div>
      </div>
      <div class="citation-gauge" aria-label="Source quality ${pct}%">
        <span class="citation-threshold" style="left:70%"></span>
        <span class="citation-bar ${color}" style="width:${sq != null ? sq * 100 : 0}%"></span>
      </div>
      <div class="citation-footer">
        <span>Source quality</span>
        <span>Review threshold</span>
      </div>
    `;
    list.appendChild(item);
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

function resetReportView() {
  $("#scores-panel")?.classList.add("hidden");
  $("#citation-grades")?.classList.add("hidden");
  $("#citation-grades").innerHTML = "";
  $("#report-content").innerHTML = '<p class="placeholder">Agents are building the counter-analysis report...</p>';
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

function getSavedPapers() {
  try {
    return JSON.parse(localStorage.getItem(SAVED_PAPERS_KEY) || "[]");
  } catch {
    return [];
  }
}

function setSavedPapers(papers) {
  localStorage.setItem(SAVED_PAPERS_KEY, JSON.stringify(papers));
}

function paperTitleFromPayload(payload, meta) {
  return payload.paper?.title || meta?.title || "Untitled analysis";
}

function savePaperAnalysis(payload, meta = activeInputMeta) {
  if (!payload) return;
  const papers = getSavedPapers();
  const now = new Date();
  const paper = {
    id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
    title: paperTitleFromPayload(payload, meta),
    kind: meta?.kind || "Analysis",
    createdAt: now.toISOString(),
    scores: payload.overall_scores || null,
    payload,
  };
  setSavedPapers([paper, ...papers].slice(0, 30));
  renderPapersLibrary();
}

function formatPaperDate(iso) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }).format(
    new Date(iso)
  );
}

function renderPapersLibrary() {
  const papers = getSavedPapers();
  const list = $("#papers-list");
  const empty = $("#papers-empty");
  const count = $("#papers-count");
  if (!list || !empty || !count) return;

  count.textContent = `${papers.length} ${papers.length === 1 ? "paper" : "papers"}`;
  empty.classList.toggle("hidden", papers.length > 0);
  list.innerHTML = "";

  for (const paper of papers) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "paper-card";
    card.dataset.paperId = paper.id;
    const scores = paper.scores || {};
    card.innerHTML = `
      <div class="paper-card-top">
        <span class="paper-kind">${escapeHtml(paper.kind || "Paper")}</span>
        <span class="paper-date">${escapeHtml(formatPaperDate(paper.createdAt))}</span>
      </div>
      <h3 class="paper-title">${escapeHtml(paper.title || "Untitled analysis")}</h3>
      <div class="paper-scores">
        <span class="paper-score">Sources ${fmtPct(scores.source_quality)}</span>
        <span class="paper-score">Coverage ${fmtPct(scores.coverage)}</span>
        <span class="paper-score">Data ${fmtPct(scores.data_quality)}</span>
      </div>
    `;
    card.addEventListener("click", () => openSavedPaper(paper.id));
    list.appendChild(card);
  }
}

async function openSavedPaper(id) {
  const paper = getSavedPapers().find((p) => p.id === id);
  if (!paper) return;
  activeInputMeta = { kind: paper.kind, title: paper.title };
  showWorkspace({ fromLibrary: true, state: "report-ready" });
  window.scrollTo({ top: 0, behavior: "instant" });
  updateProgress({ phase: "done", percent: 100, message: "Saved analysis loaded", agent: "orchestrator" });
  await displayAnalysisResult(paper.payload, { save: false });
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

async function displayAnalysisResult(payload, options = {}) {
  setGauges(payload.overall_scores);
  renderCitationGrades(payload.citations);

  let markdown = payload.markdown;
  if (!markdown) {
    markdown = buildMarkdownClientSide(payload);
    if (payload.claims?.length) {
      markdown += "\n\n*Full report will render when Person B wires `GET /report/{id}` with `markdown` from `builder.py`.*";
    }
  }
  payload.markdown = markdown;
  renderMarkdownReport(markdown);
  $("#analysis-workspace")?.classList.remove("loading");
  $("#analysis-workspace")?.classList.add("report-ready");
  if (options.save) savePaperAnalysis(payload, options.meta);
}

const MOCK_MARKDOWN = "../backend/report/fixtures/mock_report.md";

function wait(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchMockPayload() {
  const res = await fetch(MOCK_FIXTURE);
  const payload = await res.json();
  try {
    const mdRes = await fetch(MOCK_MARKDOWN);
    if (mdRes.ok) payload.markdown = await mdRes.text();
  } catch {
    /* optional */
  }
  return payload;
}

async function runMockAgentFlow(meta) {
  activeInputMeta = meta;
  showWorkspace();
  resetReportView();
  window.scrollTo({ top: 0, behavior: "instant" });
  $("#btn-analyze").disabled = true;
  $("#btn-mock").disabled = true;

  const stepMs = 5000 / AGENT_STEPS.length;
  try {
    for (let i = 0; i < AGENT_STEPS.length; i += 1) {
      const step = AGENT_STEPS[i];
      updateProgress({
        phase: step.phase,
        percent: Math.round(((i + 1) / AGENT_STEPS.length) * 100),
        message: step.label,
        agent: step.agent,
      });
      await wait(stepMs);
    }
    const payload = await fetchMockPayload();
    updateProgress({ phase: "done", percent: 100, message: "Complete", agent: "orchestrator" });
    await displayAnalysisResult(payload, { save: true, meta });
  } finally {
    $("#btn-analyze").disabled = false;
    $("#btn-mock").disabled = false;
  }
}

async function loadMock() {
  updateComposerSummary("Demo report loaded");
  await runMockAgentFlow(getCurrentInputMeta("Demo"));
}

async function startMockAnalyze() {
  await runMockAgentFlow(getCurrentInputMeta());
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
  activeInputMeta = getCurrentInputMeta();
  showWorkspace();
  $("#btn-analyze").disabled = true;
  updateProgress({ phase: "ingest", percent: 5, message: "Uploading…", agent: "orchestrator" });
  try {
    const res = await fetch(`${API}/analyze`, { method: "POST", body: formData });
    if (!res.ok) throw new Error(`Analyze failed: ${res.status}`);
    const { job_id: jobId } = await res.json();
    const payload = await pollUntilDone(jobId);
    await displayAnalysisResult(payload, { save: true, meta: activeInputMeta });
  } finally {
    $("#btn-analyze").disabled = false;
  }
}

function initAnalyzer() {
  const form = $("#analyze-form");
  if (!form) return;

  form.addEventListener("submit", async (e) => {
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

    if (!API && !window.EVIDENTIA_USE_MOCK) {
      await startMockAnalyze();
      return;
    }
    await startAnalyze(fd);
  });

  $("#btn-mock").addEventListener("click", () => loadMock());

  $("#composer-summary").addEventListener("click", expandComposer);
  $("#btn-back-library-top").addEventListener("click", showLibrary);

  $("#pdf-file").addEventListener("change", (e) => {
    const file = e.target.files[0];
    $("#file-name").textContent = file ? file.name : "No PDF attached";
    $("#btn-clear-file").classList.toggle("hidden", !file);
    updateComposerSummary();
  });

  $("#btn-clear-file").addEventListener("click", () => {
    $("#pdf-file").value = "";
    $("#file-name").textContent = "No PDF attached";
    $("#btn-clear-file").classList.add("hidden");
    updateComposerSummary();
  });

  $("#paper-text").addEventListener("input", () => {
    updateComposerSummary();
    resizeComposerInput();
  });

  document.addEventListener("click", (e) => {
    const screen = $("#composer-screen");
    if (!screen?.classList.contains("compact") || screen.classList.contains("collapsed")) return;
    if (screen.contains(e.target)) return;
    collapseComposer();
  });

  if (window.location.search.includes("demo=1")) {
    loadMock();
  }

  renderPapersLibrary();
}

initAnalyzer();
