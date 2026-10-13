## v3.3.3 — Token-free workbench and tunnel-independent operation

- Removed mandatory FOXWORX setup-token login from the default installation. Fresh installs open directly on `http://127.0.0.1:8765`; the UI suppresses the login/logout workflow.
- A self-managed Cloudflare Tunnel can route any configured public hostname to the service without a FOXWORX public-hostname allowlist, Cloudflare JWT/AUD setup, login cookie, or other application-level proxy registration.
- Installer migrates previous local, proxy or Cloudflare-only settings to `FOXWORX_AUTH_MODE=open` while backing up the original config and preserving secrets, model settings, Discord and persistent data. Old setup tokens are unused and never regenerated.
- Kept user-service binding to localhost, same-origin browser request checks, CSRF header, short-lived WebSocket tickets, administrator execution policies and bounded jobs. Those checks are **not** login restrictions or protection against a visitor already able to access the app.
- **Security tradeoff:** Anyone who can reach the app (including through a tunnel the operator exposes) can interact with the shell as the FOXWORX Linux account. No multi-user identity separation in open mode. Operator-managed Cloudflare Access can be added independently if desired.
- Added regression tests for anonymous local/remote sessions, tunnel Host rewriting, migration, and no-token startup. Updated install and user documentation.

## v3.3.2 — Previous dual-host login release

- Support a second, strictly allowlisted HTTPS hostname while keeping local http://127.0.0.1:8765 working without changing authentication modes.
- New `bash scripts/configure.sh --public-origin https://host.example` command and `--clear-public-origin` revert; no Cloudflare SDK/JWT/AUD configuration required.
- Reject unlisted Host, cross-origin mutations, non-loopback peers and forwarded-to-localhost requests; bind secure cookies to HTTPS ingress.
- First login still requires the local token to protect the real Kali shell; optional trusted-device login remains signed for 30 days and survives restarts.
- Added regression tests for dual ingress, cookie security, same-origin protection, public hostname validation, and admin CLI configuration.

## v3.3.1 — Local-first systemd service (port 8765)

- New default: non-root user service on `127.0.0.1:8765`, authenticated with a local setup token. No Cloudflare account, tunnel, domain, Access AUD or permitted-email allowlist required for installation or operation.
- Installer migrates earlier auth/port settings to local-only mode after backing up private config; preserves all other configuration, secrets and persistent state.
- Optional `proxy` auth mode uses exact HTTPS Origin/Host checks, Secure session cookies and loopback-only proxy access, without an application-level Cloudflare dependency. Legacy Cloudflare JWT mode remains only for compatibility.
- `scripts/local-service.sh` and `foxworx.cli configure --local-service` allow returning to local operation. OS packages already installed on Kali are reused without apt/sudo.
- Updated UI sign-in and operator docs; retained all v3.3 Codex, Discord, Hardware Intelligence, Graph, Rabbit Hole and evidence workflows.

## v3.3.0 — Discord Team Intelligence

- Added optional official Discord Bot API channel polling and human-reviewed summaries; per-engagement team keys isolate shared operational context across independent FOXWORX installations.
- Added authenticated Team / Discord workspace with channel history, operator and AI drafts, publish/reject controls, sync button and source links.
- Added read-only, explicitly untrusted Discord intelligence in Copilot, Rabbit Hole and Codex; no Discord-to-command execution path.
- Bot token and channel configuration stay on host only; all posting uses disabled mentions and bounded, redacted summaries.
- Added dedicated Discord setup, operator, and security documentation.

## v3.2.0 — Hardware Intelligence / Device Role Assignment (2026-10-11)

- Added bounded read-only sysfs/procfs inventory for CPU/RAM, network/Wi-Fi interfaces, PCI, USB, DRM GPU render nodes, kernel accelerator devices and other visible Linux hardware classes. Kept existing NVIDIA GPU metrics.
- Added explicit **unverified** capability labels for NPU/PCI candidates and wireless packet injection. Optional `iw phy info` query reports advertised monitor mode without changing device state.
- Added authenticated Hardware API, new responsive Hardware tab and role labeling (Management, Assessment, Reserved). Default-route and loopback interfaces remain protected; role assignments are per-operator and invalidate when hardware identity changes.
- Guided Curl HTTP proposals can optionally bind to a nominated Assessment interface; the exact argv requires human approval and the link/role/default-route status is revalidated before launch. There is no automated WLAN mode switch or arbitrary CLI device binding.
- Added read-only Copilot hardware lookup and Rabbit Hole planning context. Existing adapter policy, Codex constraints, engagement input validation, DreadFox and OS permissions remain unchanged.
- Added Hardware Intelligence operator guide and Linux verification steps; added hardware backend tests and desktop/mobile UI fixture coverage.
- Known limits: hardware not exposed by Linux is not discoverable, no proof of NPU readiness, no packet injection testing, no driver installation, no network namespace or firewall isolation.

# FOXWORX v3.1.0 — Native Codex Agent

- Added Codex app-server JSON-RPC client, per-operator isolated `CODEX_HOME`, Codex-managed ChatGPT device-code sign-in/sign-out, owner-scoped status, events, user-requested turn interruption, and saved per-engagement threads.
- Codex runs as the unprivileged FOXWORX service account, using a read-only sandbox configuration, denied app-server approval requests, and a dedicated workspace; no FOXWORX user password, cookies, raw tokens, or API keys are forwarded to the browser.
- Added Codex Agent mode and device code, connection status, optional model ID, activity stream and separate history to the browser AI sidebar.
- Preserves v3.0 investigation graph, v2.9 tool intelligence, all existing provider modes, Cloudflare Access and Rabbit Hole policy.
- Does not enable the separate SIWC open-source OAuth token sharing integration; FOXWORX remains proprietary to FoxWorx LLC. The official Codex-managed login is used instead. ChatGPT eligibility and usage limits are controlled by OpenAI.

---

# FOXWORX v3.0.0 — Investigation Graph Engine

- New center-workspace Graph tab: pan/zoom SVG execution map and investigation-with-observations mode; filter by time/status/text; responsive operation index and node details.
- Persistent, actor/engagement-scoped projection of existing managed jobs and Rabbit Hole execution history; running job updates appear without running additional scans.
- Distinct source labels for operator-managed jobs, Rabbit Hole automated operations, and parser-derived unverified output observations; connect retries and reference saved evidence.
- Guided jobs can be grouped by their *approved target* from the preserved proposal. No inferred attack paths or vulnerability claims.
- Version-independent private annotations stored in existing SQLite, bounded output parsers, direct links to actual job output, and JSON/SVG/PNG export.
- No new Python runtime dependency, external browser CDN, migration, change to the DreadFox pet, tool inventory, user shell, universal AI providers, or administrator Rabbit Hole policy.
- Safety: view-only graph, no script execution based on log content, no model-generated verified findings. Full terminal command streams still not captured. Read `docs/INVESTIGATION-GRAPH.md`.

---

# v2.9.0 — Host-aware Tool Intelligence and persistent CLI knowledge (2026-10-11)

- Added separate Python-managed SQLite knowledge database keyed to executable identity and package version; no change to prior app state tables or default state directory.
- Tool Intelligence workspace supports actual installed-executable search, cached man/package docs, long-flag hints, manual refresh, and authenticated operator-isolated usage notes.
- Added optional administrator-controlled official Kali documentation lookup and Brave Search API source links, HTTPS/domain restricted and disabled by default.
- Copilot/Tutor get read-only documentation functions; Rabbit Hole can inspect documentation as bounded steps but cannot turn learned usage into an unapproved command.
- Fixed permission and note boundary tests; preserved schema-2 root-owned adapter policies, the manual toolbox, terminals, DreadFox, Cloudflare identity, engagements and AI provider selection.
- Included offline desktop/mobile browser fixtures, real authenticated API tests, cache invalidation tests, and archive-level distribution checks. ARM64, provider and Cloudflare live acceptance tests remain target-side.

# v2.8.0 — Extensible command templates and model-selected bounded parameters (2026-10-11)

- Added administrator-registered, noninteractive CLI adapters under a strict, root-owned **schema-2** policy. The original schema-1 policy remains valid, without a permission change.
- Included **19 curated example templates** for commonly requested web discovery, TLS, OSINT, network and vulnerability-assessment utilities (not automatically enabled).
- Added structured model-controlled **enum and integer parameters**, rejecting free-form argv, shell syntax, new targets, and unnamed tools in Rabbit Hole.
- Added review-only template proposals to the normal immutable approval flow. Risk-labeled intrusive adapters cannot be delegated to Rabbit Hole.
- Autonomous **registered** templates require a code-reviewed executable allowlist; other noninteractive CLIs remain review-only even if administrators mislabel them.
- Added a real localhost execution test for registered Curl argv after explicit approval; no tool runs when a proposal is merely prepared.
- Added enabled/installed/review-only status, a searchable adapter inventory and one-click command previews.
- Preserved Rabbit Hole budgets, operator-specific authorization, root policy revocation and managed job timeouts.
- Manual terminal, Toolbox, Tutor, Copilot, models, evidence, Cloudflare integration and DreadFox remain on their original paths.
- Added policy examples, administrator setup instructions, and dedicated security regression tests.
- This release does **not** provide kernel egress confinement, target-side Kali validation, or automatic execution of every discovered CLI.

# FOXWORX v2.7.0 — Administrator Tool Adapters

- Added eight new fixed-purpose recipes (DNS CAA/NS/SOA/CNAME, TLS certificate, HTTP status, limited HTTP GET, conservative WhatWeb), 17 total.
- Added read-only administrator policy loader with root ownership and trusted parent-directory verification, exact schema and fail-closed behavior.
- Rabbit Hole start, decision, managed job and active-job checks now bind to policy revision, so revoked permissions stop further unattended activity.
- The web UI discovers administrator-enabled and installed adapters dynamically; disabled/missing profiles cannot be selected.
- Added local, no-elevation policy validation/check/list helper and install instructions that use only trusted OS privileged commands.
- Preserved v2.6 iterative loop, manual terminal/toolbox workflows, cloud/local AI, companion, Cloudflare support and existing state.
- Known limit: no OS-level process isolation or destination-level network firewall; live Kali deployment remains to be verified.

---

# FOXWORX v2.6.0 — Rabbit Hole

- Optional operator-approved **Rabbit Hole** multi-iteration AI tool mode. One scoped target + selected typed guided profiles + 1–16 action decisions + 1–30 minute budget; no human confirmation required per permitted job.
- Nine bounded workflows: nmap TCP inventory and web ports; curl HEAD and OPTIONS; dig A, AAAA, MX and TXT; whois. The model cannot send arbitrary argv, run a shell, install tools or change targets.
- Saved owner-specific run state, managed-job references, failure/exit-status feedback, bounded/redacted output-tail context, cancellation, stale-authorization checks, restart recovery, and explicit `rabbit-auto-job` audit events.
- Model function-call support and strict JSON fallback for supported non-tool-calling models. Up to two node-wide active runs; one per operator.
- Copilot sidebar mode chooser, scope/authorization panel, progress and stop controls, responsive layouts and task summary.
- Retains all v2.5 features, model providers, terminal/toolbox workflows, evidence store, Cloudflare access, and DreadFox. **Not** an unrestricted execution shell or enforced egress sandbox.

# Changelog

## 2.5.0 — DreadFox Workbench Pulse

- Added separately consented, seven-day operations summaries for companion conversations: terminal sessions, reviewed/completed/unfinished managed jobs, copilot learning, workspace planning and evidence organization. It never reads audit details, tools, targets, command text, file paths, or tool results.
- Retains only fixed category/day/saturated counts; only approximate frequency bands are visible in UI, offline reply or AI prompt. No backfill, and expired rows are pruned.
- Added GET/PUT/DELETE owner-bound, CSRF-protected companion context APIs and a responsive preview, enable/erase controls, and clear AI-provider transmission disclosure. Off by default.
- Separate AI chat-history epochs across context-setting changes to avoid silently re-forwarding old contextual conversations; full chat erasure remains independent.
- Preserved the existing pet, SVG nine-tail artwork, universal AI providers, terminal/toolbox and strict tool-approval isolation.
- Added context privacy, bounded-retention, cross-operator, offline and AI isolation, API and real audit-event observer tests; offline Chromium desktop/mobile checks.


## 2.4.0 — DreadFox Whispers / optional model-powered conversations

- Added a distinct conversation module, offline deterministic fox responses, and explicit opt-in for the user's currently selected OpenAI, Anthropic, Gemini, xAI, DeepSeek, Mistral, Ollama, LM Studio, vLLM, or approved compatible provider.
- Added evolving personality labels derived only from safe pet affinities, age and progress, plus an optional user-chosen favorite affinity. A fox develops temperament without reading targets, terminal data, evidence or main copilot chat.
- Added separated, bounded local chat persistence with per-operator ownership and pet-generation deletion. Only the 12 most recent pet messages from the same provider, model and approved inference-server URL are forwarded for AI chats.
- Preserved strict isolation: no tool definitions are supplied, attempted model tool calls are rejected, and no chat request earns XP or affects approvals.
- Added browser-based memory theme, conversation transcript, offline/AI mode selector, explicit transmission disclosure, loading/failure states and independent conversation erasure.
- Added backend privacy/isolation tests, mobile/desktop browser fixture checks and non-root local-service acceptance. No new mandatory dependencies: AI remains optional.

## 2.3.0 — DreadFox Sanctuary / deterministic digital pet

- Added an opt-in, per-operator DreadFox pet with original locally rendered fox portrait, 1–9 tails, growth stages, level/XP, offline recovery, moods, affinity scores, keepsakes, and a private bounded journal.
- Uses only a hardcoded allowlist of **generic workbench audit action names**. Never copies audit details, command text, target identifiers, tool output, or AI messages into pet state.
- Asynchronous, bounded (1,024) observer queue: optional pet telemetry never gates managed jobs, terminal sessions, model inference, or authorizations. No models are used by the pet.
- Includes hatching/opt-in, play/snack/rest, name change, pause/resume tracking, restart-safe persistence, per-user isolation, and full data erasure/reset.
- Dedicated responsive sanctuary tab plus a header companion, in-app information, lifecycle tests, and offline Chromium UI verification.
- Pet storage errors during initialization degrade only the optional companion, not the terminal/toolbox/AI service.
- Upgrade maintains the existing v2 SQLite database and systemd service; new pet tables are created automatically. No new Python packages or GPU requirement.

## 2.2.0 — Universal ARM64/x86-64 Kali nodes

Added normalized Linux ARM64/x86-64 host support, read-only preflight, per-host first-run presets (Pi and workstation), bounded optional NVIDIA inventory, Ollama executable discovery, multi-GPU Node UI, revised packaging/docs, and regression/browser/live-service tests. Existing v2/v2.1 config and evidence are preserved; GPU drivers, CUDA, model servers, remote multi-node orchestration and GUI desktop are not bundled. Actual Kali ARM64/x86-64 systemd installation and RTX 3060 Ti inference require testing on the user's machines.

## 2.1.0 — Universal AI Engine

Added model-agnostic LiteLLM adapter for OpenAI, Anthropic, Gemini, xAI, DeepSeek, Mistral, Ollama, LM Studio, vLLM and admin-approved OpenAI-compatible endpoints. Added operator-specific model selection, encrypted per-provider keys (independent key for login-token rotation), server-approved local inference targets, bounded local model discovery, explicit test requests, privacy-conscious model-history separation and model-compatibility messaging. AI tool calls remain proposals only: existing reviewed, immutable human approval and Tutor-mode enforcement are unchanged.

Installer optionally installs LiteLLM by default; `--without-ai` retains terminal/toolbox function. Preserved the v2 SQLite database and existing config. Added new AI API and offline UI regression checks. Actual cloud billing accounts, GPU endpoints, Kali ARM64 wheel installation and Cloudflare configuration require validation on the operator's target environment.


## 2.0.0 — development distribution

Rebuilt the supplied v0.1 into modular configuration/auth/scope/state/inventory/jobs/terminal/AI/evidence services and a new responsive local-asset web interface. Added persistent browser-detachable PTYs, dynamic inventory beyond 72 curated entries, four guided recipes, explicit immutable single-use approvals, live job logs and truthful statuses, API-driven AI proposals without approval privileges, privacy opt-in, engagement workspaces, evidence exports, local wizard/doctor, install/uninstall/service scripts and regression tests.

Review corrections include server-side Tutor-mode non-dispatch, scope/authorization-note staleness checks, UTF-8 output paging and history filtering before recent-item limits. V1 is not overwritten or automatically migrated.

Not included: GUI desktop, OS/user/egress sandbox, autonomous scope sync, automatic HackerOne reporting, signed audit, terminal recording, arbitrary-tool typed forms, paid live AI verification or deployment onto the user's Pi. See the verification report for actual tests, including offline UI fixture limitations.
