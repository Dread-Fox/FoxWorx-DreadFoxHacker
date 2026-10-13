#!/usr/bin/env bash
# A small, explicit package suggestion. Default is apt simulation, not installation.
set -euo pipefail
MODE="${1:---preview}"
case "$MODE" in --preview|--install) ;; *) echo 'Usage: bash scripts/tools.sh [--preview|--install]'; exit 2;; esac
PACKAGES=(nmap curl dnsutils whois jq tmux)
echo "Selected baseline: ${PACKAGES[*]}"
echo 'Tool availability depends on ARM64/x86-64 packages, licenses, privileges, hardware and program permission. This does not install all Kali tools.'
if [[ "$MODE" == '--preview' ]]; then
  apt-get -s install "${PACKAGES[@]}"
else
  [[ "$EUID" -ne 0 ]] || { echo 'Run as the operator; sudo is requested only for apt.'; exit 1; }
  read -r -p 'Install these OS packages? Type INSTALL: ' reply
  [[ "$reply" == 'INSTALL' ]] || { echo 'No changes made.'; exit 0; }
  sudo apt-get install "${PACKAGES[@]}"
  echo 'Use Refresh tools in the web interface after installation.'
fi
