#!/usr/bin/env bash
# Install into this directory. Never deletes v1 or existing v2 config/state.
set -euo pipefail
umask 077
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SKIP_APT=0; NO_START=0; WITHOUT_AI=0; PREFLIGHT=0
for arg in "$@"; do
  case "$arg" in
    --skip-apt) SKIP_APT=1;;
    --no-start) NO_START=1;;
    --without-ai) WITHOUT_AI=1;;
    --preflight) PREFLIGHT=1;;
    --help) echo 'Usage: bash scripts/install.sh [--skip-apt] [--no-start] [--without-ai] [--preflight]'; exit 0;;
    *) echo "Unknown option: $arg" >&2; exit 2;;
  esac
done
if [[ "$PREFLIGHT" -eq 1 ]]; then
  python3 -m foxworx.platforms --require
  python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ is required"'
  echo 'Preflight completed. No files, packages, drivers or services were modified.'
  exit 0
fi
[[ "$EUID" -ne 0 ]] || { echo 'Run as a dedicated non-root operator, not sudo/root. The installer asks for sudo only for optional apt dependencies.' >&2; exit 1; }
# Conservative path restriction avoids systemd expansion/quoting ambiguities.
[[ "$ROOT" != *[[:space:]%\"\\]* ]] || { echo 'Extract to a path without spaces, quotes, percent signs or backslashes.' >&2; exit 1; }
[[ "$HOME" != *[[:space:]%\"\\]* ]] || { echo 'Home path contains characters unsupported by this installer.' >&2; exit 1; }
cd "$ROOT"
# Fail before sudo, apt or any local writes on unsupported kernels/architectures.
python3 -m foxworx.platforms --require
PROFILE="$(python3 -m foxworx.platforms --profile)"
echo "Detected supported Kali/Linux host profile: $PROFILE (x86-64 or ARM64)"
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ is required"'
if [[ "$SKIP_APT" -eq 0 ]]; then
  command -v apt-get >/dev/null || { echo 'No apt-get: install Python 3.11+, python3-venv, ca-certificates manually; rerun --skip-apt.' >&2; exit 1; }
  echo 'Checking existing OS packages; no tunnel packages are required.'
  INSTALLED_COUNT="$(dpkg-query -W -f='${Status}\n' python3 python3-venv ca-certificates 2>/dev/null | grep -c '^install ok installed$' || true)"
  if [[ "$INSTALLED_COUNT" -ne 3 ]]; then
    sudo apt-get update
    sudo apt-get install -y python3 python3-venv ca-certificates
  else
    echo 'Required OS packages already installed; skipping sudo/apt.'
  fi
fi
python3 -c 'import sys; assert sys.version_info >= (3,11), "Python 3.11+ is required"'
echo 'No NVIDIA driver, CUDA package, Ollama daemon or Kali tool bundle will be installed automatically.'
if ! systemctl --user show-environment >/dev/null 2>&1; then
  echo 'No usable systemd user session. Log in normally as the operator (not sudo su), then rerun.' >&2
  exit 1
fi
if systemctl --user is-active --quiet foxworx-workbench; then
  echo 'Stop the existing v2 service before updating: systemctl --user stop foxworx-workbench' >&2
  echo 'Stopping terminates live terminal sessions and managed jobs. Archive needed evidence first.' >&2
  exit 1
fi
python3 -m venv .venv
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
if [[ "$WITHOUT_AI" -eq 0 ]]; then
  echo "Installing optional LiteLLM provider SDK (can take longer on ARM64)..."
  .venv/bin/python -m pip install --disable-pip-version-check -r requirements-ai.txt
fi
.venv/bin/python -m pip check
.venv/bin/python -m foxworx.cli configure --local-service --profile "$PROFILE"
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/foxworx-workbench.service" <<EOF
[Unit]
Description=FOXWORX Kali Workbench v3.3.3 (local + optional tunnel)
After=network.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$ROOT/.venv/bin/python -m foxworx.cli serve --config $HOME/.config/foxworx-workbench/settings.env
Environment=PYTHONUNBUFFERED=1
UMask=0077
NoNewPrivileges=true
KillMode=control-group
TimeoutStopSec=20
Restart=on-failure
RestartSec=5
TasksMax=512
LimitNOFILE=4096

[Install]
WantedBy=default.target
EOF
systemctl --user daemon-reload
systemctl --user enable foxworx-workbench.service
if [[ "$NO_START" -eq 0 ]]; then
  # A previously running v2 can restart; an unrelated listener must not be killed.
  if ! systemctl --user is-active --quiet foxworx-workbench; then
    .venv/bin/python - <<'PY'
import socket
from foxworx.config import Settings
cfg=Settings.load()
s=socket.socket(); s.settimeout(1)
if s.connect_ex(('127.0.0.1',cfg.port))==0:
    raise SystemExit(f'Port {cfg.port} is in use. Stop the old service explicitly (v1: systemctl --user stop foxworx), or configure a different port. Then start foxworx-workbench.')
s.close()
PY
  fi
  systemctl --user restart foxworx-workbench
  sleep 2
  systemctl --user is-active --quiet foxworx-workbench || { journalctl --user -u foxworx-workbench -n 40 --no-pager; exit 1; }
fi
echo
printf 'Installed v3.3.3 in %s\n' "$ROOT"
echo 'Local browser:           http://127.0.0.1:8765'
echo 'Optional provider / proxy settings: bash scripts/configure.sh'
echo 'Access mode:             token-free; no setup login required'
echo 'Diagnostics:             bash scripts/doctor.sh'
echo 'Logs:                    journalctl --user -u foxworx-workbench -n 80 --no-pager'
echo 'For service after logout/reboot, an administrator may approve: sudo loginctl enable-linger "$USER"'
echo 'Rabbit Hole retains the v2.8 root-owned adapter policy: docs/CLI-ADAPTERS.md'
echo 'Optional Codex Agent + ChatGPT sign-in: docs/CODEX-AGENT.md'
echo 'Cloudflare is NOT required. Add your own tunnel to http://127.0.0.1:8765 at any time.'
echo 'See docs/LOCAL-SERVICE.md for local and tunnel access, security and troubleshooting.'
