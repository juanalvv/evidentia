const SAVED_PAPERS_KEY = "evidentia.savedPapers.v1";
const REPORTS_PER_PAGE = 9;

const $ = (sel) => document.querySelector(sel);
let currentReportsPage = 1;

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
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

function formatPaperDate(iso) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", minute: "2-digit", hour: "numeric" }).format(
    new Date(iso)
  );
}

function openPaper(id) {
  window.location.href = `app.html?paper=${encodeURIComponent(id)}`;
}

function renderPapersPage() {
  const papers = getSavedPapers();
  const list = $("#papers-list");
  const empty = $("#papers-empty");
  const count = $("#papers-count");
  const pagination = $("#reports-pagination");
  const prev = $("#reports-prev");
  const next = $("#reports-next");
  const pageLabel = $("#reports-page-label");
  if (!list || !empty || !count) return;

  const hasPagination = Boolean(pagination && prev && next && pageLabel);
  const totalPages = Math.max(1, Math.ceil(papers.length / REPORTS_PER_PAGE));
  currentReportsPage = Math.min(Math.max(currentReportsPage, 1), totalPages);
  const visiblePapers = hasPagination
    ? papers.slice((currentReportsPage - 1) * REPORTS_PER_PAGE, currentReportsPage * REPORTS_PER_PAGE)
    : papers;

  count.textContent = `${papers.length} ${papers.length === 1 ? "report" : "reports"}`;
  empty.classList.toggle("hidden", papers.length > 0);
  pagination?.classList.toggle("hidden", papers.length <= REPORTS_PER_PAGE);
  if (hasPagination) {
    pageLabel.textContent = `Page ${currentReportsPage} of ${totalPages}`;
    prev.disabled = currentReportsPage === 1;
    next.disabled = currentReportsPage === totalPages;
  }
  list.innerHTML = "";

  for (const paper of visiblePapers) {
    const card = document.createElement("button");
    card.type = "button";
    card.className = "paper-card paper-card-large";
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
      <span class="paper-open">Open report →</span>
    `;
    card.addEventListener("click", () => openPaper(paper.id));
    list.appendChild(card);
  }
}

$("#reports-prev")?.addEventListener("click", () => {
  currentReportsPage -= 1;
  renderPapersPage();
});

$("#reports-next")?.addEventListener("click", () => {
  currentReportsPage += 1;
  renderPapersPage();
});

renderPapersPage();
