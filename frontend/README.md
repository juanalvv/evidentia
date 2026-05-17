# Person C — Frontend & report

## Pages

| Page | File | Purpose |
|------|------|---------|
| Landing | `index.html` | Marketing hero + features |
| Log in | `login.html` | Auth UI (no backend yet) |
| Register | `register.html` | Auth UI (no backend yet) |
| Analyzer | `app.html` | Split-pane upload + report + polling |

Shared: floating nav (`css/site.css`), active link via `js/nav.js`.

## Run locally

From repo root `evidentia/`:

```powershell
python -m http.server 8080
```

- Landing: http://localhost:8080/frontend/
- Demo analyzer: http://localhost:8080/frontend/app.html?demo=1

## API (Person B)

Set in `config.js`:

```js
window.EVIDENTIA_API = "http://YOUR-BREV-HOST:8000";
```

`POST /analyze`, `GET /status/{id}`, `GET /report/{id}` — see `backend/report/CONTRACT.md`.

## Styles

- `css/site.css` — landing, auth, floating nav
- `css/app.css` — analyzer split-pane
