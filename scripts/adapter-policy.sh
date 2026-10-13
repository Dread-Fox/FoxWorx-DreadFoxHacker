#!/usr/bin/env bash
# No sudo inside this script. Verify JSON locally; only OS `install` should run elevated.
set -euo pipefail
cd "$(dirname "$0")/.."
PYTHON="${PWD}/.venv/bin/python"
[[ -x "$PYTHON" ]] || PYTHON=python3
case "${1:-help}" in
  validate) exec "$PYTHON" -m foxworx.adapters validate "${2:-policy/adapter-policy.example.json}";;
  check) exec "$PYTHON" -m foxworx.adapters check;;
  list) exec "$PYTHON" -m foxworx.adapters list;;
  help)
    echo 'Usage: bash scripts/adapter-policy.sh {validate [source.json]|check|list}'
    echo 'Install a validated policy using trusted OS commands (administrator action):'
    echo '  sudo install -d -o root -g root -m 0755 /etc/foxworx'
    echo '  sudo install -o root -g root -m 0644 policy/adapter-policy.example.json /etc/foxworx/adapter-policy.json'
    echo 'Do not sudo-execute scripts from the operator-writable FOXWORX checkout.';;
  *) echo 'Unsupported action' >&2;exit 2;;
esac
