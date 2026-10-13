# Unified AI selection verification — 2026-10-11

Implemented separate Tutor / Copilot / Rabbit Hole mode and provider/model controls. Codex is a native provider with ChatGPT device sign-in, model discovery, shared chat/context, and structured requests handled by existing mode authority. Its readiness does not require LiteLLM. Old Codex history is preserved; the separate turn endpoint returns HTTP 410.

## Checks

- `PYTHON=/home/kaito/FoxWorx-DreadFoxHacker-v3.3.3/.venv/bin/python bash scripts/test.sh`: **260 passed, 1 skipped**; Python compilation, shell syntax and JavaScript syntax checks passed. One upstream Starlette/AnyIO deprecation warning remains.
- Offline `tests/browser_smoke.py` with Chromium 142.0.7444.175: **PASS**, no page errors, desktop (1600px) and mobile (390px) layouts. Covers independent selections, Codex sign-in/discovery, shared Tutor/Copilot chat and clearing, Rabbit Hole selection, sign-out readiness, and operation without LiteLLM. Fixture screenshots/results are in `/tmp/foxworx-browser-check/`.
- Native Codex CLI **0.162.1**: actual stdio handshake, unsigned-in account status, eight model IDs and acceptance of ephemeral/read-only provider thread settings. Temporary CODEX_HOME/state only; no real login or inference turn.
- Added regression coverage for missing CLI, API key/endpoint rejection, malformed/unoffered requests, isolated supplied context, pending Copilot proposals, existing Rabbit Hole grants, concurrent status startup, optional-provider failure, current interrupt IDs, repeated cancellation and legacy endpoint retirement.
- Code review findings concerning interrupt IDs, repeated-cancellation cleanup and the legacy writable turn route were fixed and reviewed again with no remaining material findings.

## Limits

Live account-billed Codex inference and real ChatGPT sign-in were not performed. Native structured output and account/model access must still be exercised with the operator's own account. Rabbit Hole retains its existing administrator policy and scope/budget requirements. The unchanged Linux account trust boundary remains described in the deployment documentation.
