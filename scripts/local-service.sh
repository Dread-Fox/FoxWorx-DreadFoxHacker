#!/usr/bin/env bash
# Force the existing deployment to the local-only 127.0.0.1:8765 profile.
# Does not restart an active service automatically.
set -euo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
[[ -x "$ROOT/.venv/bin/python" ]] || { echo 'Install this release before switching to local-only mode.' >&2; exit 1; }
"$ROOT/.venv/bin/python" -m foxworx.cli configure --local-service
printf 'To apply the change: systemctl --user restart foxworx-workbench\n'
