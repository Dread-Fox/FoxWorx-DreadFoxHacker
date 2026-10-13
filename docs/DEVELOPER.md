# Architecture and extension points

The app is a single-process FastAPI application serving local HTML/CSS/ES modules. There is no React build, Node service, container daemon or mandatory tmux. One worker owns active PTYs, WebSocket tickets and managed jobs; do not start multiple uvicorn workers behind a load balancer.

| Module | Responsibility |
|---|---|
| platforms.py | CPU/OS compatibility, optional bounded NVIDIA discovery and first-install host presets. |
| config.py / cli.py | Validated settings, private local wizard, version/doctor/server entry point. |
| auth.py | Cloudflare RS256 identity, local session cookies, Host/Origin/CSRF, one-use tickets. |
| store.py | SQLite WAL records and audit; actor ownership and engagement-filtered history. |
| scope.py / models.py | Strict user inputs and guided target-rule checking. |
| registry.py / catalog.json | Native package/PATH/desktop metadata discovery and 72 descriptive tool entries. |
| jobs.py | Four guided recipes, immutable proposals, human approval, subprocess execution/logs/limits. |
| terminal.py / pty_child.py | Controlling PTYs, resize/input/output, detach/replay/reap/close. |
| providers.py / model_gateway.py / ai.py | Per-actor encrypted credentials, provider/model selection, approved inference routes, LiteLLM adapter, read-only tool lookup, proposal function, opt-in evidence and strict human approval boundary. |
| evidence.py | Regular-file handling, listing and bounded ZIP export with checksums. |
| app.py | HTTP/WebSocket routes, middleware, request-size limits and service lifecycle. |
| static/ | Browser UI and vendored terminal assets. |

## Test locally

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
PYTHON="$PWD/.venv/bin/python" bash scripts/test.sh
```

`tests/browser_smoke.py` is an optional **offline fixture** test requiring Playwright and a system Chromium at `/usr/bin/chromium`. It runs the actual HTML/CSS/JS and terminal renderer with simulated responses, not a live socket, API provider or Cloudflare service. Never copy those fixtures into production routes.

The server factory has an explicit `_allow_root_for_tests` argument so a root-based build container can execute tests. The CLI never exposes that flag and rejects root. Tests stub the completion adapter for provider routing and use locally generated RSA keys for Cloudflare JWT verification. No tests perform public target scanning or consume paid AI credits.

## Add a tool or recipe

Most newly installed executable names already appear after Refresh. Add administrator-approved directories through FOXWORX_EXTRA_TOOL_PATHS. Add descriptions to catalog.json only for stable names you understand; classification is advisory, not proof of compatibility. Do not execute every discovered binary to probe its version or parse untrusted `--help` into arbitrary form logic.

For a new guided recipe, first write target-validation and argv-construction tests. Add an explicit profile to models.py, PROFILES/recipe in jobs.py, and the matching AI schema enumeration in ai.py. The UI discovers profile metadata from the API. Decide whether the tool follows redirects, reads config/target files, loads plugins/templates, invokes other executables or opens out-of-scope network destinations. Input validation alone is insufficient for containment. Never give the model a direct approve endpoint or unrestricted shell tool as part of a “guided” claim.

Native job arguments use subprocess exec with stdin closed. Shell syntax, expansions, interactive prompts and GUI programs belong elsewhere. A wrapper is new code that needs review, not an automatic extension of the four guided policies.

## APIs

All protected requests require the current identity. Mutations require Origin plus X-Foxworx-CSRF from `/api/session`; Content-Length is required and bounded. Cookies/Access assertions are not replaced by the CSRF header. Do not put keys into URLs.

Read-oriented AI routes: `/api/ai/settings` (provider metadata without decrypted keys), `/api/ai/models?provider=...&endpoint_id=...` (admin-approved local endpoints only). AI writes: `PUT /api/ai/settings`, `PUT/DELETE /api/ai/keys/{provider}`, `POST /api/ai/test` (short real inference request). These use the same identity, CSRF, Host and Origin protections as other APIs.

Read-oriented routes: `/api/session`, `/api/tools`, `/api/diagnostics`, `/api/engagements`, `/api/jobs?engagement_id=...`, `/api/jobs/{id}/output?offset=...`, `/api/proposals`, `/api/terminals`, `/api/chat?engagement_id=...`, engagement `/files`, `/export`, `/api/audit`.

Writes: create/update engagement; refresh inventory; parse argument text; create/dismiss proposal; approve once using its digest and explicit `authorized`; stop jobs; create/close terminal and obtain its one-use ticket; chat/clear chat; upload a file. `/ws/terminals/{id}?ticket=...` still checks the authenticated identity and Origin. No API for root, sudo, package install, Cloudflare administration or automatic vulnerability-report submission exists.

In-memory job/session state is not shared across workers. SQLite stores small metadata records, not terminal streams. The server recovers prior active job records as interrupted instead of retrying them after restart.

## Review limits

The implementation was self-reviewed and tested in the documented build environment. No separate reviewer or external security audit was performed. Before exposing a higher-assurance service, prioritize OS/egress isolation, secrets separation, audit retention, disk quotas, long-lived-session behavior, independent review and actual Kali ARM64/x86-64 native-tool and GPU acceptance.

## Adding inference providers

Add the provider to `providers.PROVIDERS` with a fixed LiteLLM prefix, explicit key/endpoint policy, model validation and capability notes. Never construct the route by concatenating arbitrary browser URLs. Add an API schema test, a gateway contract test, and an operator UI case. The function schema in `ai.TOOLS` is mapped through `model_gateway.make_tools()` to common chat-completion tool calls. Unsupported models must remain usable in Tutor mode where possible, never silently execute a model-generated command. No connector/model gains the human approval endpoint.

`tests/live_local_smoke.py` tests actual HTTP, PTY WebSocket and a harmless managed subprocess under a real non-root Linux user (not the mock provider and not a Kali Pi). `tests/browser_smoke.py` remains an offline Chromium fixture; check the verification report before claiming real cloud/provider interoperability.
