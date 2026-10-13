#!/usr/bin/env bash
set -euo pipefail
[[ "$EUID" -ne 0 ]] || { echo 'Run as the operator who installed the service.'; exit 1; }
echo 'This stops running terminals/jobs and removes ONLY the v2 user service registration.'
echo 'Source code, configuration, evidence, v1, and Cloudflare configuration are preserved.'
read -r -p 'Type REMOVE to continue: ' reply
[[ "$reply" == REMOVE ]] || { echo 'No changes made.'; exit 0; }
systemctl --user disable --now foxworx-workbench.service
rm -f "$HOME/.config/systemd/user/foxworx-workbench.service"
systemctl --user daemon-reload
echo 'V2 service removed. Review Cloudflare route/Access cleanup separately. Evidence and secrets remain on disk.'
