const API = window.EVIDENTIA_API || "";
const MOCK_FIXTURE = "../backend/report/fixtures/synthetic_analysis.json";
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
let activeAnalysisPayload = null;

function showWorkspace({ fromLibrary = false, state = "loading" } = {}) {
  $("#composer-screen")?.classList.add("compact", "collapsed");
  $("#papers-library")?.classList.add("hidden");
  const workspace = $("#analysis-workspace");
  workspace?.classList.remove("hidden", "loading", "report-ready", "citation-ready");
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

function showReportView() {
  $("#analysis-workspace")?.classList.remove("citation-ready", "claim-ready");
  $("#analysis-workspace")?.classList.add("report-ready");
  $("#citation-detail")?.classList.add("hidden");
  $("#claim-detail")?.classList.add("hidden");
  $(".panel-output")?.classList.remove("hidden");
  window.scrollTo({ top: 0, behavior: "instant" });
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

function unwrapReportPayload(payload) {
  if (!payload || typeof payload !== "object") return payload;
  if (payload.analysis_result) return payload.analysis_result;
  if (payload.result?.analysis_result) return payload.result.analysis_result;
  return payload;
}

function coerceScore(value) {
  if (value == null || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

function normalizeCounterEntry(counter) {
  return {
    summary: counter.summary || "",
    papers: (counter.papers || []).map((paper) => ({
      title: paper.title || "Untitled",
      authors: normalizeAuthors(paper.authors) || "",
      year: paper.year ?? null,
      doi: paper.doi ?? null,
      url: paper.url ?? null,
      relevance:
        paper.relevance != null
          ? String(paper.relevance)
          : paper.relevance_score != null
            ? String(paper.relevance_score)
            : "",
    })),
  };
}

function normalizeAnalysisResult(payload) {
  const paper = payload.paper || {};
  const authors = paper.authors;
  const normalizedPaper = {
    ...paper,
    title: paper.title || "Untitled draft",
    authors: Array.isArray(authors) ? authors.filter(Boolean) : authors ? [String(authors)] : [],
  };

  const citations = (payload.citations || []).map((citation) => ({
    ...citation,
    id: citation.id || citation.citation_id,
    authors: normalizeAuthors(citation.authors) || citation.authors || "",
    source_quality_score: coerceScore(citation.source_quality_score),
    recency_flag: citation.recency_flag || "ok",
    superseded_by: citation.superseded_by || [],
  }));

  const claims = (payload.claims || []).map((claim) => ({
    ...claim,
    id: claim.id || claim.claim_id,
    counterarguments: (claim.counterarguments || []).map(normalizeCounterEntry),
    cited_source_ids: claim.cited_source_ids || [],
  }));

  const overall = payload.overall_scores || {};
  const overall_scores = {
    source_quality: coerceScore(overall.source_quality) ?? average(citations.map((c) => c.source_quality_score)),
    coverage: coerceScore(overall.coverage),
    data_quality: coerceScore(overall.data_quality ?? payload.data_quality?.score),
  };

  return {
    ...payload,
    job_id: payload.job_id || payload.submission_id || "job-unknown",
    status: payload.status || "completed",
    paper: normalizedPaper,
    overall_scores,
    citations,
    claims,
    data_quality: payload.data_quality || { score: null, summary: null, comparisons: [] },
    executive_summary: payload.executive_summary || buildExecutiveSummary(overall_scores),
    progress: payload.progress || { phase: "done", percent: 100, message: "Complete", agent: "orchestrator" },
    errors: payload.errors || [],
  };
}

function normalizePayload(payload) {
  const root = unwrapReportPayload(payload);
  if (!root || typeof root !== "object") return root;
  if (root.source_checks || root.counterarguments || root.grader) {
    return buildFromOrchestrator(root);
  }
  return normalizeAnalysisResult(root);
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
  root.innerHTML = `
    <h3>Per-citation grades</h3>
    <p class="section-description">We reviewed each cited source for recency, reliability, and supersession risk. Use these scores to spot which references are strong enough to keep and which ones may need replacement or newer supporting literature.</p>
  `;
  const list = document.createElement("div");
  list.className = "citation-list";
  for (const c of citations) {
    const item = document.createElement("button");
    item.type = "button";
    const sq = c.source_quality_score;
    const pct = sq != null ? Math.round(sq * 100) : "—";
    const color = scoreColor(sq);
    item.className = `citation-item ${color}`;
    item.dataset.citationId = c.id || "";
    item.innerHTML = `
      <span class="citation-title">${escapeHtml(c.title || "Untitled")} (${c.year ?? "?"})</span>
      <span class="citation-bar-wrap"><span class="citation-bar ${color}" style="width:${sq != null ? sq * 100 : 0}%"></span></span>
      <span class="citation-pct">${pct}%</span>
      <span class="citation-flag">${escapeHtml(c.recency_flag || "")}</span>
      <span class="citation-open">Open citation details</span>
      <span class="citation-arrow" aria-hidden="true">→</span>
    `;
    item.addEventListener("click", () => showCitationDetail(c.id));
    list.appendChild(item);
  }
  root.appendChild(list);
}

function renderClaimsSection(claims) {
  const root = $("#claims-section");
  if (!root) return;
  if (!claims?.length) {
    root.classList.add("hidden");
    root.innerHTML = "";
    return;
  }
  root.classList.remove("hidden");
  root.innerHTML = `
    <h3>Claims, coverage & counterarguments</h3>
    <p class="section-description">Each claim is scored by how well it is supported by the paper’s citations. Lower coverage means the claim may need stronger evidence, clearer sourcing, or a narrower wording.</p>
  `;
  const list = document.createElement("div");
  list.className = "claim-list";
  for (const claim of claims) {
    const score = claim.coverage_score;
    const pct = score != null ? Math.round(score * 100) : "—";
    const color = scoreColor(score);
    const item = document.createElement("button");
    item.type = "button";
    item.className = `claim-item ${color}`;
    item.dataset.claimId = claim.id || "";
    item.innerHTML = `
      <span class="claim-title">${escapeHtml(claim.text || "Untitled claim")}</span>
      <span class="claim-bar-wrap"><span class="claim-bar ${color}" style="width:${score != null ? score * 100 : 0}%"></span></span>
      <span class="claim-pct">${pct}%</span>
      <span class="claim-section">${escapeHtml(claim.section || "Section")}</span>
      <span class="claim-open">Open claim details</span>
      <span class="claim-arrow" aria-hidden="true">→</span>
    `;
    item.addEventListener("click", () => showClaimDetail(claim.id));
    list.appendChild(item);
  }
  root.appendChild(list);
}

function citationTitleById(id) {
  const citation = activeAnalysisPayload?.citations?.find((c) => c.id === id);
  return citation?.title || id;
}

function citationById(id) {
  return activeAnalysisPayload?.citations?.find((c) => c.id === id);
}

function externalPaperLink(paper) {
  return paper.url || doiUrl(paper.doi);
}

function showClaimDetail(claimId) {
  const claim = activeAnalysisPayload?.claims?.find((c) => c.id === claimId);
  const detail = $("#claim-detail");
  if (!claim || !detail) return;

  const score = claim.coverage_score;
  const pct = score != null ? Math.round(score * 100) : "—";
  const color = scoreColor(score);
  const cited = claim.cited_source_ids || [];
  const counterarguments = claim.counterarguments || [];

  detail.innerHTML = `
    <button type="button" id="btn-back-report-claim" class="back-library-btn citation-back">← Back to report</button>
    <div class="citation-detail-hero">
      <div>
        <span class="citation-detail-kicker">${escapeHtml(claim.section || "claim")}</span>
        <h2>${escapeHtml(claim.text || "Untitled claim")}</h2>
        <p>${cited.length} cited ${cited.length === 1 ? "source" : "sources"} · ${counterarguments.length} ${counterarguments.length === 1 ? "counterargument" : "counterarguments"}</p>
      </div>
      <div class="citation-detail-score ${color}">
        <strong>${pct}%</strong>
        <span>coverage</span>
      </div>
    </div>

    <section class="citation-analysis-card">
      <h3>Counterarguments</h3>
      ${
        counterarguments.length
          ? `<div class="claim-detail-stack">${counterarguments
              .map(
                (counter, index) => `
                  <article class="claim-detail-card">
                    <span>Counterargument ${index + 1}</span>
                    <p>${escapeHtml(counter.summary || "No summary available.")}</p>
                    ${
                      counter.papers?.length
                        ? `<ul class="superseded-list">${counter.papers
                            .map((paper) => {
                              const link = externalPaperLink(paper);
                              const content = `
                                <strong>${escapeHtml(paper.title || "Untitled paper")}</strong>
                                <span>${escapeHtml(paper.authors || "Unknown authors")} · ${paper.year ?? "?"}</span>
                                ${paper.relevance ? `<span>${escapeHtml(paper.relevance)}</span>` : ""}
                              `;
                              return `<li>${
                                link
                                  ? `<a href="${escapeHtml(link)}" target="_blank" rel="noreferrer">${content}<span class="superseded-open">Open paper ↗</span></a>`
                                  : content
                              }</li>`;
                            })
                            .join("")}</ul>`
                        : ""
                    }
                  </article>
                `
              )
              .join("")}</div>`
          : "<p>No counterarguments were detected for this claim.</p>"
      }
    </section>

    <section class="citation-analysis-card">
      <h3>Cited sources</h3>
      ${
        cited.length
          ? `<ul class="superseded-list">${cited
              .map((id) => {
                const citation = citationById(id);
                const link = doiUrl(citation?.doi);
                const content = `
                  <strong>${escapeHtml(citationTitleById(id))}</strong>
                  <span>${escapeHtml(citation?.authors || "Unknown authors")}${citation?.year ? ` · ${citation.year}` : ""}${citation?.doi ? ` · ${escapeHtml(citation.doi)}` : ""}</span>
                `;
                return `<li>${
                  link
                    ? `<a href="${escapeHtml(link)}" target="_blank" rel="noreferrer">${content}<span class="superseded-open">Open paper ↗</span></a>`
                    : content
                }</li>`;
              })
              .join("")}</ul>`
          : "<p>No cited sources were detected for this claim.</p>"
      }
    </section>

  `;

  $("#analysis-workspace")?.classList.add("claim-ready");
  detail.classList.remove("hidden");
  $("#btn-back-report-claim").addEventListener("click", showReportView);
  window.scrollTo({ top: 0, behavior: "instant" });
}

function citationAttentionText(citation) {
  const score = citation.source_quality_score;
  if (citation.superseded_notes) return citation.superseded_notes;
  if (citation.recency_flag === "stale") return "This source may be outdated for a fast-moving research area.";
  if (score != null && score < 0.45) return "This source has a low quality score and should not be used as primary evidence.";
  if (score != null && score < 0.7) return "This source is usable, but the claim may need stronger or more recent support.";
  return "This citation looks strong, but it should still be checked against newer related work.";
}

function doiUrl(doi) {
  if (!doi) return "";
  return doi.startsWith("http") ? doi : `https://doi.org/${doi}`;
}

function showCitationDetail(citationId) {
  const citation = activeAnalysisPayload?.citations?.find((c) => c.id === citationId);
  const detail = $("#citation-detail");
  if (!citation || !detail) return;

  const score = citation.source_quality_score;
  const pct = score != null ? Math.round(score * 100) : "—";
  const color = scoreColor(score);
  const doi = doiUrl(citation.doi);
  const superseded = citation.superseded_by || [];

  detail.innerHTML = `
    <button type="button" id="btn-back-report" class="back-library-btn citation-back">← Back to report</button>
    <div class="citation-detail-hero">
      <div>
        <span class="citation-detail-kicker">${escapeHtml(citation.recency_flag || "citation")}</span>
        <h2>${escapeHtml(citation.title || "Untitled citation")}</h2>
        <p>${escapeHtml(citation.authors || "Unknown authors")} · ${escapeHtml(citation.journal || "Unknown venue")} · ${citation.year ?? "?"}</p>
      </div>
      <div class="citation-detail-score ${color}">
        <strong>${pct}%</strong>
        <span>source quality</span>
      </div>
    </div>

    <div class="citation-detail-grid">
      <article class="citation-info-card">
        <span>Authors</span>
        <strong>${escapeHtml(citation.authors || "Unknown")}</strong>
      </article>
      <article class="citation-info-card">
        <span>Published</span>
        <strong>${citation.year ?? "Unknown"}</strong>
      </article>
      <article class="citation-info-card">
        <span>Venue</span>
        <strong>${escapeHtml(citation.journal || "Unknown")}</strong>
      </article>
      <article class="citation-info-card">
        <span>DOI</span>
        ${
          doi
            ? `<a href="${escapeHtml(doi)}" target="_blank" rel="noreferrer">${escapeHtml(citation.doi)}</a>`
            : "<strong>Not detected</strong>"
        }
      </article>
    </div>

    <section class="citation-analysis-card">
      <h3>Why this citation needs review</h3>
      <p>${escapeHtml(citationAttentionText(citation))}</p>
    </section>

    <section class="citation-analysis-card">
      <h3>Superseded or newer related work</h3>
      ${
        superseded.length
          ? `<ul class="superseded-list">${superseded
              .map(
                (paper) => {
                  const link = doiUrl(paper.doi);
                  const content = `
                    <strong>${escapeHtml(paper.title || "Untitled paper")}</strong>
                    <span>${paper.year ?? "?"}${paper.doi ? ` · ${escapeHtml(paper.doi)}` : ""}</span>
                  `;
                  return `<li>${
                    link
                      ? `<a href="${escapeHtml(link)}" target="_blank" rel="noreferrer">${content}<span class="superseded-open">Open paper ↗</span></a>`
                      : content
                  }</li>`;
                }
              )
              .join("")}</ul>`
          : "<p>No specific superseding papers were detected for this citation.</p>"
      }
    </section>
  `;

  $("#analysis-workspace")?.classList.add("citation-ready");
  detail.classList.remove("hidden");
  $("#btn-back-report").addEventListener("click", showReportView);
  window.scrollTo({ top: 0, behavior: "instant" });
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

function stripExecutiveSummary(markdown) {
  if (!markdown) return markdown;
  return markdown
    .replace(/^\s*# .+?(?:\n|$)/m, "")
    .replace(/^\s*\*Authors \(detected\):\* .+?(?:\n|$)/m, "")
    .replace(/## Executive summary\s+[\s\S]*?(?=\n## |\n---|$)/i, "")
    .replace(/## Key Findings\s+[\s\S]*?(?=\n## |\n---|$)/i, "")
    .replace(/## Overall grades\s+[\s\S]*?(?=\n## |\n---|$)/i, "")
    .replace(/## Source quality by citation\s+[\s\S]*?(?=\n## |\n---|$)/i, "")
    .replace(/## Claims, coverage & counterarguments\s+[\s\S]*?(?=\n## |\n---|$)/i, "")
    .replace(/## Data & methods comparison\s+[\s\S]*?(?=\n## |\n---|$)/i, "")
    .replace(/## Final Verdict\s+[\s\S]*?(?=\n## |\n---|$)/i, "")
    .replace(/---\s*\n\*Generated by Evidentia[\s\S]*$/i, "")
    .trim();
}

function renderReportTitle(paper) {
  const root = $("#report-title-card");
  if (!root) return;
  const title = paper?.title || "Untitled draft";
  const authors = Array.isArray(paper?.authors) ? paper.authors.join(", ") : paper?.authors;
  root.classList.remove("hidden");
  root.innerHTML = `
    <span class="report-title-kicker">Evidentia Report</span>
    <h1>Evidentia Report: ${escapeHtml(title)}</h1>
    ${authors ? `<p>${escapeHtml(authors)}</p>` : ""}
  `;
}

function renderKeyFindings(summary) {
  const root = $("#key-findings");
  if (!root) return;
  if (!summary) {
    root.classList.add("hidden");
    root.innerHTML = "";
    return;
  }
  root.classList.remove("hidden");
  root.innerHTML = `
    <div class="key-findings-copy">
      <span class="key-findings-kicker">Key Findings</span>
      <h3>What Evidentia found</h3>
      <p>${escapeHtml(summary)}</p>
    </div>
  `;
}

function verdictLabel(verdict) {
  return {
    below_norm: "Below norm",
    ok: "Acceptable",
    strong: "Strong",
  }[verdict] || verdict || "Unknown";
}

function renderDataMethodsSection(dataQuality) {
  const root = $("#data-methods-section");
  if (!root) return;
  if (!dataQuality) {
    root.classList.add("hidden");
    root.innerHTML = "";
    return;
  }
  const score = dataQuality.score;
  const pct = score != null ? Math.round(score * 100) : "—";
  const color = scoreColor(score);
  const comparisons = dataQuality.comparisons || [];
  root.classList.remove("hidden");
  root.innerHTML = `
    <div class="data-methods-header">
      <div>
        <h3>Data & methods comparison</h3>
        <p>${escapeHtml(dataQuality.summary || "Evidentia compared the paper's data and methods against expected field norms.")}</p>
      </div>
      <div class="data-methods-score">
        <div class="score-ring ${color}" style="--score:${score != null ? Math.round(score * 100) : 0}">
          <strong>${pct}%</strong>
        </div>
        <span>data quality</span>
      </div>
    </div>
    <div class="methods-comparison-list">
      ${comparisons
        .map(
          (row) => `
            <article class="method-comparison-card ${scoreColor(row.verdict === "below_norm" ? 0.2 : 0.75)}">
              <div class="method-comparison-top">
                <h4>${escapeHtml(row.aspect || "Method aspect")}</h4>
                <span>${escapeHtml(verdictLabel(row.verdict))}</span>
              </div>
              <div class="method-comparison-grid">
                <div>
                  <span>In draft</span>
                  <strong>${escapeHtml(row.paper_value || "Not detected")}</strong>
                </div>
                <div>
                  <span>Field norm</span>
                  <strong>${escapeHtml(row.field_norm || "Unknown")}</strong>
                </div>
              </div>
            </article>
          `
        )
        .join("")}
    </div>
  `;
}

function normalizeFinalVerdict(payload) {
  const explicit = payload?.final_verdict;
  if (typeof explicit === "string") return { status: explicit };
  if (explicit?.status) return explicit;

  const scores = payload?.overall_scores || {};
  const sourceQuality = scores.source_quality;
  const coverage = scores.coverage;
  const dataQuality = scores.data_quality ?? payload?.data_quality?.score;
  const weakCitation = payload?.citations?.some((citation) => (citation.source_quality_score ?? 1) < 0.45);
  const staleCitation = payload?.citations?.some((citation) => citation.recency_flag === "stale");

  if ((coverage ?? 1) < 0.45) {
    return {
      status: "Needs major evidence work",
      summary: "Core claims need stronger evidence before this paper is ready for submission.",
    };
  }
  if ((dataQuality ?? 1) < 0.65) {
    return {
      status: "Needs to improve methods & data processes",
      summary: "The argument is visible, but methods and data reporting need more rigor.",
    };
  }
  if ((sourceQuality ?? 1) < 0.7 || weakCitation || staleCitation) {
    return {
      status: "Needs citation revision",
      summary: "The paper is close, but some references should be replaced or updated.",
    };
  }
  return {
    status: "Ready to submit",
    summary: "The evidence base, claim coverage, and methods signals are strong enough for review.",
  };
}

function verdictTone(status) {
  return {
    "Ready to submit": "good",
    "Needs citation revision": "warn",
    "Needs major evidence work": "bad",
    "Needs to improve methods & data processes": "warn",
  }[status] || "neutral";
}

function renderFinalVerdict(payload) {
  const root = $("#final-verdict");
  if (!root) return;

  const verdict = normalizeFinalVerdict(payload);
  const status = verdict.status || "Needs major evidence work";
  const tone = verdictTone(status);
  const scores = payload?.overall_scores || {};
  const rationale =
    verdict.rationale?.length
      ? verdict.rationale
      : [
          `Source quality is ${fmtPct(scores.source_quality)}.`,
          `Claim coverage is ${fmtPct(scores.coverage)}.`,
          `Data quality is ${fmtPct(scores.data_quality ?? payload?.data_quality?.score)}.`,
        ];
  const nextSteps =
    verdict.next_steps?.length
      ? verdict.next_steps
      : [
          "Update weak or stale citations with stronger recent literature.",
          "Tighten broad claims so each one maps to direct evidence.",
          "Add clearer methods details before submission.",
        ];

  root.classList.remove("hidden");
  root.className = `final-verdict ${tone}`;
  root.innerHTML = `
    <div class="final-verdict-main">
      <span class="final-verdict-kicker">Final Verdict</span>
      <h3>${escapeHtml(status)}</h3>
      <p>${escapeHtml(verdict.summary || "Evidentia combined source quality, claim coverage, and data quality to produce this recommendation.")}</p>
    </div>
    <div class="final-verdict-panel">
      <span>Why this verdict</span>
      <ul>
        ${rationale.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </div>
    <div class="final-verdict-panel">
      <span>Next best action</span>
      <ul>
        ${nextSteps.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}
      </ul>
    </div>
  `;
}

function resetReportView() {
  $("#scores-panel")?.classList.add("hidden");
  $("#citation-grades")?.classList.add("hidden");
  $("#claims-section")?.classList.add("hidden");
  $("#data-methods-section")?.classList.add("hidden");
  $("#final-verdict")?.classList.add("hidden");
  $("#report-footer-note")?.classList.add("hidden");
  $("#btn-export-pdf")?.classList.add("hidden");
  $("#key-findings")?.classList.add("hidden");
  $("#report-title-card")?.classList.add("hidden");
  $("#citation-grades").innerHTML = "";
  $("#claims-section").innerHTML = "";
  $("#data-methods-section").innerHTML = "";
  $("#final-verdict").innerHTML = "";
  $("#key-findings").innerHTML = "";
  $("#report-title-card").innerHTML = "";
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

function safeFilename(value) {
  return String(value || "evidentia-report")
    .replace(/[<>:"/\\|?*\x00-\x1F]/g, "")
    .replace(/\s+/g, "-")
    .slice(0, 80)
    .replace(/^-+|-+$/g, "")
    .toLowerCase() || "evidentia-report";
}

function pdfToneColor(el) {
  if (el.classList.contains("good")) return "#059669";
  if (el.classList.contains("warn")) return "#d97706";
  if (el.classList.contains("bad")) return "#dc2626";
  return "#64748b";
}

function preparePdfVisuals(root) {
  root.querySelectorAll(".score-ring").forEach((ring) => {
    const score = Number.parseFloat(ring.style.getPropertyValue("--score") || "0");
    const pct = Math.max(0, Math.min(100, Number.isNaN(score) ? 0 : score));
    const color = pdfToneColor(ring);
    const label = ring.querySelector(".gauge-value, strong")?.textContent?.trim() || `${Math.round(pct)}%`;
    const radius = 44;
    const circumference = 2 * Math.PI * radius;
    const offset = circumference * (1 - pct / 100);
    const svg = document.createElement("div");
    svg.innerHTML = `
      <svg width="112" height="112" viewBox="0 0 112 112" xmlns="http://www.w3.org/2000/svg" style="display:block">
        <circle cx="56" cy="56" r="${radius}" fill="#fff" stroke="#e2e8f0" stroke-width="12"></circle>
        <circle cx="56" cy="56" r="${radius}" fill="none" stroke="${color}" stroke-width="12" stroke-linecap="round"
          stroke-dasharray="${circumference}" stroke-dashoffset="${offset}" transform="rotate(-90 56 56)"></circle>
        <text x="56" y="61" text-anchor="middle" font-family="Inter, Arial, sans-serif" font-size="18" font-weight="800" fill="#0f172a">${label}</text>
      </svg>
    `;
    ring.replaceWith(svg.firstElementChild);
  });

  root.querySelectorAll(".citation-bar, .claim-bar").forEach((bar) => {
    bar.style.background = pdfToneColor(bar);
    bar.style.height = "100%";
    bar.style.display = "block";
    bar.style.borderRadius = "999px";
  });

  root.querySelectorAll(".citation-bar-wrap, .claim-bar-wrap").forEach((wrap) => {
    wrap.style.background = "#e2e8f0";
    wrap.style.minHeight = "10px";
    wrap.style.borderRadius = "999px";
    wrap.style.overflow = "hidden";
  });
}

async function exportReportPdf() {
  const button = $("#btn-export-pdf");
  const report = $(".panel-output");
  if (!report || !activeAnalysisPayload) return;

  if (typeof window.html2pdf === "undefined") {
    window.print();
    return;
  }

  if (button) {
    button.disabled = true;
    button.classList.add("exporting");
  }

  const exportNode = report.cloneNode(true);
  exportNode.querySelector(".report-heading")?.remove();
  exportNode.classList.add("pdf-export-content");

  const shell = document.createElement("div");
  shell.className = "pdf-export-shell";
  shell.appendChild(exportNode);
  document.body.appendChild(shell);
  preparePdfVisuals(exportNode);
  const exportWidth = Math.ceil(exportNode.scrollWidth);

  const title = paperTitleFromPayload(activeAnalysisPayload, activeInputMeta);
  const filename = `${safeFilename(title)}-evidentia-report.pdf`;

  try {
    await window.html2pdf()
      .set({
        margin: [0.35, 0.35, 0.45, 0.35],
        filename,
        image: { type: "jpeg", quality: 0.98 },
        html2canvas: { scale: 2, useCORS: true, backgroundColor: "#ffffff", width: exportWidth, scrollX: 0, scrollY: 0 },
        jsPDF: { unit: "in", format: "letter", orientation: "portrait" },
        pagebreak: { mode: ["avoid-all", "css", "legacy"] },
      })
      .from(exportNode)
      .save();
  } finally {
    shell.remove();
    if (button) {
      button.disabled = false;
      button.classList.remove("exporting");
    }
  }
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
  const viewAll = $("#papers-view-all");
  if (!list || !empty || !count) return;

  count.textContent = `${papers.length} ${papers.length === 1 ? "report" : "reports"}`;
  empty.classList.toggle("hidden", papers.length > 0);
  viewAll?.classList.toggle("hidden", papers.length <= 9);
  list.innerHTML = "";

  for (const paper of papers.slice(0, 9)) {
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
  const normalized = normalizePayload(payload);
  activeAnalysisPayload = normalized;

  setGauges(normalized.overall_scores);
  renderReportTitle(normalized.paper);
  renderKeyFindings(normalized.executive_summary);
  renderCitationGrades(normalized.citations);
  renderClaimsSection(normalized.claims);
  renderDataMethodsSection(normalized.data_quality);
  renderFinalVerdict(normalized);

  let markdown = normalized.markdown;
  if (!markdown) {
    markdown = await fetchMarkdownFromPayload(normalized);
  }
  markdown = stripExecutiveSummary(markdown || "");
  renderMarkdownReport(markdown);

  $("#analysis-workspace")?.classList.remove("loading");
  $("#analysis-workspace")?.classList.add("report-ready");
  $("#report-footer-note")?.classList.remove("hidden");
  $("#btn-export-pdf")?.classList.remove("hidden");

  if (options.save) savePaperAnalysis(normalized, options.meta);
}

const MOCK_MARKDOWN = "../backend/report/fixtures/synthetic_report.md";

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
  if (reportRes.status === 202) {
    const pending = await reportRes.json();
    throw new Error(pending.error || "Report not ready");
  }
  if (!reportRes.ok) throw new Error(`Report failed: ${reportRes.status}`);
  return unwrapReportPayload(await reportRes.json());
}

async function startAnalyze(formData) {
  activeInputMeta = getCurrentInputMeta();
  showWorkspace();
  resetReportView();
  window.scrollTo({ top: 0, behavior: "instant" });
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
  $("#btn-back-library-report").addEventListener("click", showLibrary);
  $("#btn-export-pdf").addEventListener("click", exportReportPdf);

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

  const paperId = new URLSearchParams(window.location.search).get("paper");
  if (paperId) {
    openSavedPaper(paperId);
  }
}

initAnalyzer();
