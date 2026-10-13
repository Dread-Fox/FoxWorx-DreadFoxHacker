# FOXWORX v3.3.3 — Local service on port 8765

**This release installs and runs as a systemd user service on `http://127.0.0.1:8765` without configuring Cloudflare.** Optional HTTPS tunnel hostnames can be added without changing local mode or requiring Cloudflare credentials inside FOXWORX. An existing v3.3 configuration is backed up and migrated to local-only mode while preserving secrets, Codex, Discord settings and engagement data.

**Token-free local and tunnel access:** The service runs on `127.0.0.1:8765` and opens the full workspace directly, with no setup token or Cloudflare-specific login. Any tunnel hostname you configure independently can forward to it without an application hostname allowlist. **Anyone who can reach the service can access its Kali shell as the service account.** [Setup and exposure details](docs/LOCAL-SERVICE.md).

**Pi quick start (download the release directly to the Pi):**

```bash
cd ~
tar -xzf ~/Downloads/FoxWorx-DreadFoxHacker-v3.3.3.tar.gz
cd FoxWorx-DreadFoxHacker-v3.3.3
bash scripts/install.sh --preflight
bash scripts/install.sh
```

Open **http://127.0.0.1:8765** in the Pi's browser. An old running FOXWORX user service must be stopped deliberately before installation. **No tunnel or Cloudflare account is required.** [Local installation and optional reverse proxy guide](docs/LOCAL-SERVICE.md) · [Full installation guide](docs/INSTALL.md).

---

> **New in v3.2 — Hardware Intelligence:** A dedicated Hardware workspace inventories the Linux-visible CPU, RAM, network adapters, PCI/USB devices, graphics render nodes, optional NVIDIA GPU metrics, kernel accelerators and probable NPU candidates. Wireless PHYs report advertised monitor-mode support where available; packet-injection readiness remains unverified. Trusted operators can label interfaces Management/Assessment/Reserved, with default-route protection. An explicit, reviewed assessment interface may be selected for certain guided Curl jobs. Copilot and Rabbit Hole receive **read-only hardware awareness**, never new device permissions. See [Hardware Intelligence and device roles](docs/HARDWARE-INTELLIGENCE.md).

> **New in v3.1 — Codex provider + ChatGPT sign-in:** FOXWORX now embeds the official Codex app-server as a selectable provider for Tutor, Copilot and Rabbit Hole. Operators can sign in to Codex using its supported device-code workflow and eligible ChatGPT accounts, without handing passwords, cookies or tokens to the FOXWORX browser. Codex credentials are stored by the first-party CLI in a per-operator CODEX_HOME. Codex turns run in read-only mode with application approval requests denied; this is not equivalent to an OS security sandbox for data isolation. Read [Codex setup and limits](docs/CODEX-AGENT.md). **GitHub visibility and open-source dependencies do not turn the FoxWorx LLC company-only license into an open-source license.**

> **PROPRIETARY SOFTWARE — © 2026 FoxWorx LLC. All rights reserved.**  
> Public viewing does **not** grant permission to install, run, copy, modify, distribute, or commercialize this software outside FoxWorx LLC authorization. See [LICENSE](LICENSE). Third-party components retain their own licenses.

> **New in v3.0 — Investigation Graph:** Live execution and observation graph backed by persistent managed-job and Rabbit Hole records. Visualize tool use, retries, saved job evidence, parsed-but-unverified output observations, and approved target associations. Includes an offline zoomable SVG canvas, filters, annotations, and JSON/SVG/PNG exports. Read [Investigation Graph](docs/INVESTIGATION-GRAPH.md). **No new automated tool permissions or background AI calls.**

> **New in v2.9 — Tool Intelligence:** Python-managed, host-specific CLI discovery and version-bound documentation cache. Operators can inspect local man/package references, discover likely flags, save private verified notes, and optionally retrieve official Kali docs or filtered external search references. Tutor, Copilot and Rabbit Hole can read the same cache, but **documentation NEVER expands execution authority**. Online retrieval is OFF until administrators explicitly enable it. See [Tool Intelligence guide](docs/TOOL-INTELLIGENCE.md).

> **v2.8 CLI adapter expansion:** 17 built-in Rabbit Hole workflows, 19 sample administrator-registered CLI templates (some autonomous, others review-only), model-selectable *typed* parameters, separate review-only tools, and a searchable adapter panel. Existing root-owned schema-1 policies remain valid without expanding privileges. See [docs/CLI-ADAPTERS.md](docs/CLI-ADAPTERS.md) and `policy/adapter-policy.v2.example.json`. The system does not run unrestricted model-generated shell commands.

# FOXWORX Kali Workbench · v3.3.3

> **New in v3.3 — Discord Team Intelligence:** Optional bot integration for one Discord team channel, engagement-tagged inbound findings, read-only AI team context across independently operated machines, human-approved manual/Copilot/Rabbit Hole findings, and persistent local message/draft history. No channel message authorizes tool execution. See [setup and user guide](docs/DISCORD-TEAM.md).

A browser workspace for Kali Linux **ARM64 Raspberry Pi 4B or x86-64 workstations**: **real persistent terminal + discovered tool inventory + live job output + evidence + a normally approval-driven AI copilot and separately preauthorized Rabbit Hole mode**. Local browser access is the default. The operator can independently provide optional external access later.

**Release classification: tested development distribution for trusted operators, not an independently audited unattended pentest system.** This is an actual application, not a mockup or renamed v0.1. It has not been deployed on your Pi or Z790, verified against your Cloudflare account, or independently security-audited. Read the acceptance checklist before publishing it.

## Previously in v2.7 — Administrator-Controlled Tool Adapters

The v2.7 Rabbit Hole extension expands fixed-purpose Kali workflows from **9 to 17** using Nmap, Curl, Dig, WHOIS, OpenSSL and WhatWeb. A **root-owned administrator policy** in `/etc/foxworx/adapter-policy.json` determines which adapters and budgets are permitted; the operator independently chooses a narrower grant for each run. The policy cannot add arbitrary commands or arguments, and revocation stops in-flight autonomous runs. The browser shows enabled, disabled, and uninstalled adapters. **Rabbit Hole is disabled until this policy is explicitly installed**; manual sessions continue to work.

[Administrator tool policy and installation guide](docs/ADAPTER-POLICY.md) · [Policy example](policy/adapter-policy.example.json)

## Previously introduced in v2.6 — Rabbit Hole: bounded autonomous guided investigation

**Select `Rabbit Hole` in the AI copilot** to authorize a single objective, exact scoped target, chosen guided workflows and finite run budget **once**, then let the selected cloud/local model iterate and retry the allowed Kali checks without approving every command. Failed tool output and exit status feed the next step. Progress, job links, stop, audit, a final summary and suggested next steps are included. The regular Copilot/Tutor approval behavior and DreadFox privacy boundary remain unchanged.

The v2.6 release introduced **nine typed, low-impact guided recipes** across Nmap/Curl/Dig/WHOIS—not arbitrary terminal commands or exploit tools. Limits: **1–16 agent decisions**, **1–30 minutes**, only one run per operator and two per node. The model cannot change target, allowed workflows, arguments or authorization. All jobs pass through the existing managed execution checks. **This is not an egress firewall or verified task solver; Rabbit Hole requires a suitably isolated and explicitly authorized assessment environment.**

Read [Rabbit Hole operator guide and safety limitations](docs/RABBIT-HOLE.md) before enabling it.

## New in v2.5 — Workbench Pulse: safe operations context for DreadFox

Operators can now **separately opt in** to DreadFox's seven-day **Workbench Pulse**. The fox can recognize approximate activity in **terminal sessions, reviewed managed jobs, successful or unfinished managed jobs, copilot learning, workspace planning and evidence organization**. It does not know the target, executable, command, path, result, findings or credentials behind those events. Stored records are limited to UTC day, fixed category and saturated count; conversations receive only an approximate frequency band. Raw `audit.details` is never read by the companion.

- **Off by default; no backfill.** Opt-in is in the DreadFox sanctuary. Disabling immediately deletes all stored pulse rows. The regular pet growth journal and XP are separate. Pausing pet tracking also suppresses the pulse.
- **AI privacy:** DreadFox receives the pulse only when enabled; it is passed to the chosen external/cloud/local model **only after the operator also opts into AI dialogue and sends a chat message**. An explicit disclosure is shown. It never triggers background model calls.
- **Conversation privacy:** Changing the Pulse setting rotates its conversation-context partition, so prior pet chats are not forwarded to the model automatically after revoking Pulse access. Existing chat messages remain stored until separately cleared.
- **Retention:** Rows older than seven UTC calendar days are pruned when processed/read; no details are stored at any stage. No existing operations are imported on opt-in.

See [DreadFox companion and Pulse privacy guide](docs/DREADFOX.md). All v2.4 features and the same shared v2 state directory are retained.

## Previously in v2.4 — DreadFox conversations and evolving character

DreadFox now includes **Whispers with your fox**, a separate companion conversation panel below the existing animated SVG fox. Its personality is shaped by safe activity affinity totals (Exploration, Craft, Wisdom, Stewardship), age, energy, bond, curiosity and earned growth. A user can also explicitly set a favorite memory theme. The deterministic field journal and 1–9 tails remain intact.

- **Offline conversation is the default:** the fox responds from its own pet state with no GPU, API key, network request or charge.
- **AI-powered conversation is opt-in:** use the operator's currently selected cloud/local model by enabling the checkbox in the sanctuary. Only the explicitly typed pet message, a safe bounded pet-state summary and at most 12 previous messages from that **same provider + model + approved inference server + credential** are sent. There is no automatic background inference.
- **No Kali privileges:** no tools or function schemas are offered to DreadFox; it cannot execute commands, read targets or output, approve jobs, or access main copilot messages. A model returning a tool request is rejected.
- **Memory control:** short-term conversation records are stored separately in SQLite (maximum 60 rows per operator). Clear pet chat without losing XP; a full pet delete/reset removes conversations and memories. Pet chat itself earns no XP. Model chat text is **not encrypted** in the SQLite database. Never paste confidential data into it.

Model connections are best-effort: provider availability, compatibility, charges and local-server setup must be tested on your hardware. [See the DreadFox guide](docs/DREADFOX.md).

## From v2.3 — DreadFox digital companion

The optional sanctuary retains its original procedural SVG illustration, breathing/tail animation, nine age- and XP-gated growth stages, 120 XP/day limit, activity affinities, moods, interactive care, keepsakes and private milestone journal. The passive activity observer uses **only predefined audit event categories**—never command text, targets, results, secrets or regular AI conversations. Operators may pause activity tracking independently of conversation mode.

## Previously in v2.2 — one service for Pi and Z790

- **Native ARM64 and x86-64 Kali support:** a read-only host preflight and architecture-aware installation (no ARM64-only assumption on a conventional PC).
- **Node diagnostics:** safe reporting of host architecture, logical CPUs, distro, 0–16 NVIDIA devices, available VRAM, driver discovery status and presence of Ollama. Missing GPU utilities are nonfatal.
- **New-install profiles:** Pi defaults to 2 jobs/4 terminals; workstation to 4 jobs/8 terminals. Upgrades **retain existing limits**. Both profiles preserve all authorizations and backend functionality.
- **Optional local GPU inference:** run Ollama/LM Studio/vLLM separately on your Z790; use `ollama-local` on the same host, or a private SSH forward to connect the Pi. FOXWORX never installs NVIDIA drivers or publishes the inference API.
- **Optional per-node Cloudflare access:** same codebase, separate Access-protected hostnames and services; there is no cross-node management plane yet.

Start with [**Platform and multi-GPU setup**](docs/PLATFORMS.md) for both hosts.

## From v2.1 — user-selectable cloud and local AI

**Provider selection is now part of the browser workbench**: OpenAI, Anthropic Claude, Google Gemini, xAI Grok, DeepSeek, Mistral, Ollama, LM Studio, vLLM and administrator-approved OpenAI-compatible servers. Each operator saves a model selection and optional encrypted credential; no API key appears in browser settings responses. Local-model endpoints are approved in the private Pi config and never entered as arbitrary browser URLs. Function-calling ability varies by model; Tutor mode is available for models without tool calls. **Nothing has autonomous approval privileges.**

Install the LiteLLM runtime (default `bash scripts/install.sh`), then click **AI copilot → Provider & model**. See [AI providers, local GPU inference, credentials and migration](docs/AI-PROVIDERS.md).

## What changed from v0.1

| Area | v2 implementation |
|---|---|
| Terminal | Native controlling PTY; browser disconnect detaches rather than killing the shell; bounded replay; reconnect; resize; session selection; close controls. No mandatory tmux dependency. |
| Toolbox | 72 described tool entries **plus dynamic executable discovery**; search/categories; installed/missing states; CLI/interactive/desktop distinctions; package and prerequisite notes. |
| Execution | Four guided recipes and a generic literal-argument launcher; immutable expiring proposals; explicit one-use human approval; saved stdout/stderr; actual exit status; stop/timeout/output/concurrency limits. |
| Copilot | A provider-neutral LiteLLM adapter can discover installed tools and prepare proposals through supported model function calls. The model cannot approve or execute them. Tutor mode blocks proposal dispatch. |
| Engagements | Separate workspaces; exact asset inputs, exclusions, authorization notes; guided input checking; stale proposals rejected after relevant scope/notes changes. |
| Evidence | Persistent job/chat metadata, file upload/download, bounded ZIP export and SHA-256 manifest. Terminal input is not recorded. |
| Usability | Dark/light modes, narrow-screen layout, clear connection/configuration status, visible errors, output follow/copy, optional AI context sharing, local setup wizard and diagnostics. |
| Security | Non-root service; token-free default (no operator identity); browser Origin/CSRF checks; terminal connection tickets; no runtime CDN; no inherited provider secrets in command environments. Legacy authenticated modes remain optional but are not the installation default. |

**72 descriptions does not mean 72 installed tools or 72 graphical adapters.** There are four guided forms. Other noninteractive tools use advanced arguments; interactive tools use the terminal. A remote desktop is not included.

## Install on the Pi or Z790 (Kali Linux)

Use **Kali ARM64 or x86-64 with Python 3.11+**, a dedicated non-root operator account, and a normal systemd user login. Do not install/run this as root. Keep an SSH or local-console recovery path.

Extract `FoxWorx-DreadFoxHacker-v3.3.0.zip` into your home directory, then:

```bash
cd ~/FoxWorx-DreadFoxHacker-v3.3
bash scripts/install.sh --preflight  # read-only compatibility check
# Only when the old v0.1 service is running on the same port:
systemctl --user stop foxworx

bash scripts/install.sh
```

The installer requests sudo only to install minimal OS dependencies; it chooses Pi/workstation resource presets **only for new configurations**. By default it installs optional LiteLLM; use `--without-ai` for a terminal/toolbox-only setup. It does not install Kali's full tool collection, change sudo policy, or install Cloudflare. This token-free release backs up and changes only existing auth mode / port / origin settings; it preserves previous credentials and evidence without using any old login token. Python dependencies require Internet access on the Pi.

Visit **http://127.0.0.1:8765** in a browser on the host; there is no FOXWORX token or login screen. From your workstation, keep an SSH forward open:

```bash
ssh -L 8765:127.0.0.1:8765 operator@YOUR_PI_ADDRESS
```

Then open that loopback URL on your workstation. Tunnel setup is optional and independent of application installation.

Configure optional shared API credentials, inference endpoints, or reverse proxy settings locally:

```bash
bash scripts/configure.sh
systemctl --user restart foxworx-workbench
bash scripts/doctor.sh
```

**External access is your responsibility:** If you add a Cloudflare Tunnel, point it to `http://127.0.0.1:8765`; FOXWORX needs no further changes. This token-free service grants any reachable visitor the Linux service user’s shell access, so you can independently configure Cloudflare Access if desired. See [LOCAL-SERVICE.md](docs/LOCAL-SERVICE.md).

## First workflow

Choose **Tutor**, **Copilot**, or **Rabbit Hole** using the **Mode** selector. Select the provider and model separately using **Provider & model**. Codex appears alongside the other providers and uses **Sign in with ChatGPT** instead of an API key. Changing mode keeps your saved provider and model.

Open a terminal in the default **Local lab** engagement. Confirm native commands such as `pwd` and `uname -m`. Select an installed tool to inspect prerequisites, prepare a harmless local command such as `curl --version`, inspect the immutable preview, check authorization and approve it. Verify its recorded exit code/output in Jobs. Export evidence.

**Terminal on a phone:** Swipe up or down inside the terminal, or drag the large **Output history** bar below it. Tap **Latest output ↓** to return to the newest lines. Reading older output keeps your place as new output arrives. Terminal buttons have larger touch targets on narrow screens; history controls are disabled when a fullscreen program has no scrollback.

For AI, open **Provider & model** in the browser, select any supported cloud/local provider, enter an actual available model ID, and save a provider credential when required. For Ollama, local model discovery is available. Try Tutor mode first; a successful connection check does not guarantee tool calling. The terminal and toolbox work without AI.

## Read before team use

A full shell is powerful: operators on one node share the service Linux account's authority. They can read that account's configuration, encrypted key material, encryption key and files. Encryption at rest **does not isolate hostile shell users**. Web ownership checks do **not** isolate hostile users. Prefer one operator/account/node trust boundary. No passwordless sudo is installed; the service explicitly blocks privilege escalation.

Guided scope checks validate inputs, **not actual network destinations**. Advanced arguments, native terminal commands, tool redirects/referrals and user code are not contained by an engagement firewall. Any Cloudflare ingress protection you choose does not control outbound testing traffic. Program rules and authorization remain the operator's responsibility.

## Documentation

- [Installation, local port 8765, upgrade and optional proxy setup](docs/INSTALL.md)
- [Universal AI providers and local inference](docs/AI-PROVIDERS.md)
- [Codex provider, device sign-in, and deployment limits](docs/CODEX-AGENT.md)
- [Operator guide and troubleshooting](docs/OPERATOR-GUIDE.md)
- [Tool coverage and the complete 72-entry matrix](docs/TOOL-COVERAGE.md)
- [Usability review: fixes, tradeoffs and remaining gaps](docs/UX-REVIEW.md)
- [Security model and deployment checklist](docs/SECURITY.md)
- [Configuration reference](docs/CONFIGURATION.md)
- [Architecture and extension points](docs/DEVELOPER.md)
- [Dependency provenance and licenses](docs/DEPENDENCIES.md)
- [Actual verification results and limits](verification/TEST-REPORT.md)

Original FOXWORX code is proprietary to FoxWorx LLC under the [company-only LICENSE](LICENSE); bundled third-party assets retain their own licenses and notices. This distribution does not bundle Kali tools, API credentials or Cloudflare tunnel tokens.
