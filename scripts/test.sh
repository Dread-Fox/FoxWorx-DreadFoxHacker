#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
[[ -x "$PYTHON" ]] || { echo 'Install requirements-dev.txt into a virtual environment first.' >&2; exit 1; }
"$PYTHON" -m pytest -q
"$PYTHON" -m compileall -q foxworx
for script in scripts/*.sh; do bash -n "$script"; done
if command -v node >/dev/null; then node --check static/app.js; fi
