#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
[[ -x .venv/bin/python ]] || { echo 'Run bash scripts/install.sh first.' >&2; exit 1; }
exec .venv/bin/python -m foxworx.cli doctor "$@"
