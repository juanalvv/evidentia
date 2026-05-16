#!/usr/bin/env bash
# Evidentia / ScholarCounter — start FastAPI on 0.0.0.0:8000 (Brev/Linux).
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
python3 -m pip install -r requirements.txt
exec python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000
