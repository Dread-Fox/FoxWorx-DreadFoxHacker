> **v3.3.3:** FOXWORX supports a token-free local service and self-managed HTTPS tunnel hostnames simultaneously. See [LOCAL-SERVICE.md](LOCAL-SERVICE.md).

# Configuration reference

Default file: `~/.config/foxworx-workbench/settings.env`. Use `bash scripts/configure.sh`, which creates secure permissions and preserves existing values. Environment variables override file values; dotenv interpolation is disabled. Restart the service after changes. `--init` creates only a missing config, `--show-token` and `--rotate-token` apply only if you deliberately switch to the legacy token login mode; they are not used in the default token-free service.

| Key | Default / meaning |
|---|---|
| FOXWORX_AUTH_MODE | `open` (default, no browser login), or legacy `local`, `proxy`, `cloudflare` modes. No Cloudflare setup is required. |
| FOXWORX_PORT | `8765`; supported 1024–65535; listener remains 127.0.0.1. |
| FOXWORX_ORIGIN | `http://127.0.0.1:8765` locally; exact HTTPS origin in optional `proxy` mode, no path. |
| FOXWORX_SESSION_SECRET | Generated random secret; at least 32 characters. Keep private. |
| FOXWORX_LOCAL_TOKEN | Empty on a new open-mode installation. An old token remains stored but unused after migration; only legacy local/proxy login uses it. |
| FOXWORX_STATE | `~/.local/share/foxworx-workbench-v2` (expanded absolute default). |
| CF_TEAM_DOMAIN | `https://YOURTEAM.cloudflareaccess.com`; not the workbench hostname. |
| CF_ACCESS_AUD | Access application's audience identifier. |
| FOXWORX_ALLOWED_EMAILS | Comma-separated explicit emails; mandatory in Cloudflare mode. |
| OPENAI_API_KEY | Optional shared Pi-level credential or legacy v2 key; operators can instead save encrypted keys in the browser. |
| OPENAI_MODEL | Optional legacy OpenAI model ID for a v2 configuration. Per-operator selections override it. |
| FOXWORX_AI_ENCRYPTION_KEY | Separate secret, generated on new installs and automatically added to existing v2 configs by `configure --init`. Must be backed up with per-operator saved keys. Independent from session-token rotation. |
| FOXWORX_AI_ENDPOINTS | JSON map of named `ollama`, `lmstudio`, `vllm` and `custom` server addresses approved by the local administrator. Defaults to `{}`; loopback Ollama/LM Studio are built in. See AI-PROVIDERS.md. |
| ANTHROPIC_API_KEY, GEMINI_API_KEY, XAI_API_KEY, DEEPSEEK_API_KEY, MISTRAL_API_KEY | Optional shared Pi-level credentials. Operator-specific keys override these. |
| FOXWORX_MAX_JOBS | New ARM64 default `2`; new x86-64 default `4`; supported 1–8 active managed jobs. No background task queue beyond those slots. |
| FOXWORX_JOB_TIMEOUT | `900` seconds; supported 5–86400. |
| FOXWORX_LOG_MIB | `5`; supported 1–100 MiB captured bytes per job. Reaching the limit can stop the job. |
| FOXWORX_MAX_TERMINALS | New ARM64 default `4`; new x86-64 default `8`; supported 1–12 node-wide sessions. |
| FOXWORX_RESERVE_MIB | New ARM64 default `256`; new x86-64 default `1024`; minimum free space before a managed job starts. Not a live disk quota. |
| FOXWORX_EXTRA_TOOL_PATHS | Colon-separated additional absolute executable directories, e.g. `/home/foxoperator/go/bin`. Restart then Refresh. |
| FOXWORX_SHELL | `/bin/bash`; an installed executable interactive shell. Its startup files may affect behavior. |

Session limits: no browser login/cookie in open mode; legacy local cookie 8 hours (optional 30-day remembered device); pending proposal 10 minutes; ticket 30 seconds/one use; socket reauthentication at most 15 minutes; detached terminal expiry 1 hour; PTY replay 256 KiB; up to 128 output messages per connected browser; paste/input at most 16 KiB per frame; upload 10 MiB; export 64 MiB uncompressed; 1,000 listed workspace files; 10,000 exported jobs; 200 recent jobs/proposals per view; 60 displayed chat messages; 12 prior messages used for AI history. AI context may include the explicitly opted-in last 12 KB of a selected job.

The installer creates a **user** systemd unit at `~/.config/systemd/user/foxworx-workbench.service`. No application-level password reset email, shared admin role, secret-vault integration, service-token login or unattended API approval is provided.

AI requests currently have a fixed 2,400-output-token budget per provider response, up to three internal response rounds, and a 80-second total backstop with provider calls capped at 48 seconds, and a 95-second browser timeout. Reasoning-heavy requests may need a different reviewed budget/model; incomplete responses are errors, not executed work. No live model tuning or token-cost meter is provided in v2.

For operator-specific AI model selection/keys, use the browser **Model & keys** dialog; never place secrets in engagement notes or chat. Saved keys are encrypted at rest, but trusted same-UID shell users can read the encryption key. The vendor SDK is an optional dependency (`requirements-ai.txt`, installed by default). See [AI-PROVIDERS.md](AI-PROVIDERS.md).

**Cross-platform config:** architecture defaults apply only when config is first created. Existing settings/data remain intact on upgrade. The GPU runtime is not configured through FOXWORX: manage Ollama, NVIDIA drivers and `CUDA_VISIBLE_DEVICES` in their own host services. See [PLATFORMS.md](PLATFORMS.md).

## v3.3.3: Token-free local service and independent Cloudflare routing

`FOXWORX_AUTH_MODE=open` is the default and is enforced on install/upgrades using `scripts/install.sh`. Local HTTP `http://127.0.0.1:8765` and external HTTPS hostnames forwarded to that address work without a registration step. **No setup-token login, session cookie, Cloudflare JWT, or public-origin allowlist is used in open mode.** `FOXWORX_PUBLIC_ORIGIN` has no access-gating effect in open mode. Browser Origin and CSRF checks remain for request integrity only. Access to the network endpoint is therefore sufficient for workbench control; secure your chosen public tunnel independently if needed.

To migrate an existing installation: `bash scripts/local-service.sh` then `systemctl --user restart foxworx-workbench`. Other provider, Discord and Codex configuration is preserved.
