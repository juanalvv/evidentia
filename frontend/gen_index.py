from pathlib import Path

D = "d" + "iv"


def tag(name: str, inner: str = "", cls: str = "", **attrs: str) -> str:
    attr = f' class="{cls}"' if cls else ""
    for k, v in attrs.items():
        attr += f' {k}="{v}"'
    if inner:
        return f"<{name}{attr}>{inner}</{name}>"
    return f"<{name}{attr}></{name}>"


def gauge(metric: str, label: str) -> str:
    return tag(
        D,
        f'<span class="gauge-label">{label}</span>'
        + tag(D, tag(D, "", cls="gauge-fill"), cls="gauge-track")
        + '<span class="gauge-value">—</span>',
        cls="gauge",
        **{"data-metric": metric},
    )


html = "\n".join(
    [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '  <meta charset="UTF-8" />',
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />',
        "  <title>ScholarCounter — Evidentia</title>",
        '  <link rel="stylesheet" href="styles.css" />',
        '  <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>',
        "</head>",
        "<body>",
        tag(
            "header",
            tag(D, tag("h1", "ScholarCounter") + tag("p", "Academic draft counter-analysis · Cloud demo", cls="tagline")),
            cls="app-header",
        ),
        tag(
            "main",
            tag(
                "section",
                "\n".join(
                    [
                        "<h2>Upload draft</h2>",
                        '<form id="analyze-form">',
                        '<label class="file-label"><span>PDF file</span>'
                        '<input type="file" id="pdf-file" accept=".pdf,application/pdf" /></label>',
                        '<p class="or">or</p>',
                        "<label><span>Paste text</span>"
                        '<textarea id="paper-text" rows="10" placeholder="Paste abstract or section…"></textarea></label>',
                        tag(
                            D,
                            '<button type="submit" id="btn-analyze">Analyze</button>'
                            '<button type="button" id="btn-mock" class="secondary">Load demo report</button>',
                            cls="actions",
                        ),
                        "</form>",
                        tag(
                            D,
                            "<h3>Agent progress</h3>"
                            + tag(
                                D,
                                tag(D, "", id="progress-bar", cls="progress-bar", style="width: 0%"),
                                cls="progress-bar-wrap",
                            )
                            + '<p id="progress-message" class="progress-message">Starting…</p>'
                            + '<ul id="agent-steps" class="agent-steps"></ul>',
                            id="progress-panel",
                            cls="progress-panel hidden",
                        ),
                    ]
                ),
                cls="panel panel-input",
                **{"aria-label": "Input"},
            )
            + tag(
                "section",
                "<h2>Report</h2>"
                + tag(D, gauge("source_quality", "Source quality") + gauge("coverage", "Coverage") + gauge("data_quality", "Data quality"), id="scores-panel", cls="scores-panel hidden")
                + tag(D, "", id="citation-grades", cls="citation-grades hidden")
                + tag(
                    "article",
                    '<p class="placeholder">Upload a paper or load the demo to see the counter-analysis report.</p>',
                    id="report-content",
                    cls="report-content",
                ),
                cls="panel panel-output",
                **{"aria-label": "Report"},
            ),
            cls="layout",
        ),
        '  <script src="config.js"></script>',
        '  <script src="app.js"></script>',
        "</body>",
        "</html>",
    ]
)

Path(__file__).parent.joinpath("index.html").write_text(html, encoding="utf-8")
print("ok")
