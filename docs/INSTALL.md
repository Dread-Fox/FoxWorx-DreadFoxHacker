# Installation — local port 8765; no Cloudflare required

**Current release: FoxWorx-DreadFoxHacker-v3.3.3.** Default installation works locally without Cloudflare, and optionally accepts one configured public HTTPS hostname without disabling localhost. See [LOCAL-SERVICE.md](LOCAL-SERVICE.md) for the exact Kali Pi procedure, preserving existing state, and optional future HTTPS proxy mode.


## 1. Choose the host account

Targets: Raspberry Pi 4B running Kali **ARM64**, or a conventional Kali **x86-64** PC (including NVIDIA GPU workstations), Python **3.11+**, a writable home directory and systemd user services. The app also runs on Linux development hosts; native Kali compatibility is a separate test. Kali's official Pi documentation is linked in DEPENDENCIES.md.

Use a dedicated non-root account. Do not put it in privileged groups or give it passwordless sudo merely to make a tool work. Install OS packages through your separate administrator access. The service's `NoNewPrivileges=true` intentionally blocks privilege escalation; raw sockets, capture devices and GUI programs are not guaranteed to behave as in an unrestricted administrator SSH session.

Keep the host powered, cooled and backed by reliable storage. Job logs and artifacts can fill a microSD card. The job log cap does not impose a filesystem quota on arbitrary tool-created files. Check Node health regularly.

## 2. Extract and install

Extract the release ZIP under your home directory. The top-level directory is `FoxWorx-DreadFoxHacker-v3.3.3`. Use a path without whitespace, quotes, percent signs or backslashes; the installer validates this to avoid systemd quoting problems. Do not move it after installation without rerunning the installer.

```bash
cd ~/FoxWorx-DreadFoxHacker-v3.3.3
bash scripts/install.sh --preflight # no modifications
bash scripts/install.sh
```

The installer creates `.venv`, installs pinned direct dependencies plus the LiteLLM AI extra by default, preserves existing credentials and persistent state, backs up and migrates the mode/port/origin to token-free localhost:8765, and registers **foxworx-workbench.service** as your user. It requests sudo only if `python3`, `python3-venv`, or `ca-certificates` is missing. It does not run an unattended full OS upgrade. `unzip` is needed separately to extract a ZIP.

**Architecture-specific first-run defaults:** ARM64 nodes start with 2 managed jobs, 4 terminal sessions and a 256 MiB free-disk reserve. x86-64 nodes start with 4 jobs, 8 terminals and a 1024 MiB free-disk reserve. These are application resource limits, not guaranteed performance or CUDA settings. **Existing resource limits, secrets, and state are preserved; only mode/port/origin are migrated to local-only when needed.**

See [Pi and Z790 platform guide](PLATFORMS.md), including optional GPU inference and SSH forwarding to a workstation-hosted model.

Options:

```bash
bash scripts/install.sh --preflight      # hardware/platform report only, no writes
bash scripts/install.sh --skip-apt       # OS dependencies already present
bash scripts/install.sh --no-start       # prepare without starting the service
bash scripts/install.sh --without-ai     # skip LiteLLM; terminal/toolbox only
```

The v2 service is distinct from v1's **foxworx.service**. If another service is already using port 8765, identify and resolve the port conflict before starting FOXWORX. Do not stop an unrelated process without reviewing it.

Stopping a service can interrupt work. The installer does not delete or silently stop v1 or v2. It refuses to replace a running workbench service; stop it yourself after preserving needed evidence, then rerun the installer. V2.4 reuses the v2 settings and SQLite state; it does not delete the old source folder.

## 3. Token-free local access

Start the systemd user service and open the browser. There is no login token or sign-in screen:

```bash
systemctl --user status foxworx-workbench --no-pager
```

**http://127.0.0.1:8765**

The backend still validates the browser's Origin and CSRF header for mutations, and uses short-lived WebSocket tickets. These are application request-integrity checks, **not an authentication barrier**. With the default `open` mode, any visitor who can reach the endpoint shares the Linux service account's ability to run commands and access saved data. Cloudflare is optional and managed separately by you.

## 4. Configure AI provider and model

In your browser, click **AI copilot → Model & keys**, choose one of the ten providers, save a provider key for cloud access if needed, select an exact model ID and click **Use this model**. The **Test selected connection** button makes a short real inference request. For local models on the current node or a private GPU desktop, enter administrator-approved endpoints in the private config first; see **[Universal AI providers](AI-PROVIDERS.md)**. There is no fixed model entitlement, and a provider website subscription is not necessarily API access.

To edit optional AI credentials, local endpoints or proxy configuration:

```bash
bash scripts/configure.sh
```

The configuration is stored at `~/.config/foxworx-workbench/settings.env` with mode 600, outside the release directory. Do not paste keys into chat, a support request, an engagement, a screenshot or source control. An AI error does not disable terminal/toolbox operation. API use can incur provider charges; set provider project spending limits independently.

## 5. Optional remote tunnel (not part of installation)

No tunnel, domain or Cloudflare credentials are required. FOXWORX binds only to `127.0.0.1:8765` and works in the Pi's own desktop browser immediately after install. If you want a tunnel later, publish your selected hostname to `http://127.0.0.1:8765` in your existing Cloudflare setup. The FOXWORX app requires **no** tunnel setting, public-origin allowlist, setup token, or Cloudflare configuration. Preserve WebSocket support. Everyone who can reach the hostname can operate the Kali workbench, so configure external access restrictions independently if you want them.

## 6. Keep the service available after logout

```bash
systemctl --user enable foxworx-workbench
```

For startup without an interactive login, an administrator can review and enable lingering:

```bash
sudo loginctl enable-linger "$USER"
```

This is not done automatically. Test an actual reboot, then verify the workbench. Do not assume a successful local `systemctl` call proves remote reachability.

## 7. Upgrade and rollback

Keep each source release in a separate directory. Preserve `~/.config/foxworx-workbench` and `~/.local/share/foxworx-workbench-v2`. Export evidence, end terminal work, stop the service, back up state, extract the new source, and run its installer. It replaces the user unit's source path but preserves v2 configuration/state. A running v2 is not updated in place.

There is no automatic migration from v1's schema, jobs or local .env file. This avoids pretending old approvals/identities are compatible. Keep v1 as a read-only reference. Re-enter only required configuration values through the wizard. Do not blindly copy v1 .env into v2.

To roll back to v1, stop v2 and start the retained v1 service only after restoring its valid authentication configuration. Never run both on the same port. For a later v2 downgrade, restore a matching backed-up state/schema along with that release; arbitrary schema downgrade is not supported.

## 8. Backup, removal and disk hygiene

Stop the service before copying the whole state directory so SQLite, logs and workspace files are quiescent:

```bash
systemctl --user stop foxworx-workbench
umask 077
mkdir -p "$HOME/foxworx-backups"
tar -C "$HOME/.local/share" -czf "$HOME/foxworx-backups/workbench-state-$(date +%Y%m%d-%H%M%S).tar.gz" foxworx-workbench-v2
systemctl --user start foxworx-workbench
```

This example assumes the default state path. Configuration/API keys are **not included**; back them up separately using your approved encrypted secret-storage process. Archives can contain sensitive testing data. Restore into a temporary directory, inspect paths/symlinks and ownership, then replace stopped-service state only with a trusted backup. Do not extract an untrusted archive over a live home directory.

`bash scripts/uninstall.sh` asks for confirmation, stops/disables the v2 user service, and removes its unit. It intentionally preserves source, secrets, evidence, v1, and Cloudflare settings. Review each before manual deletion and remove obsolete tunnel routes/Access apps separately. Lingering is not silently disabled because other user services may depend on it.

## Acceptance gate before remote team use

Verify ARM64 and Python; non-root/no broad sudo; service start and reboot; permitted and forbidden Access identities; missing/forged token denial; browser terminal control/reconnect; no jobs until approval; actual local tool exit status; stop and resource limits; evidence handling; optional live AI request; program-specific authorization. Record results in your deployment log. The release's build-container tests do not replace these checks.

## DreadFox companion and conversations (v2.5)

After login select **✦ DreadFox** and hatch the optional companion. The feature does not require LiteLLM or a cloud API key. Its per-operator profile and bounded journal are created in the existing SQLite state file only after opt-in. The upgrade does not collect historical commands or retroactively credit old sessions. See [DREADFOX.md](DREADFOX.md).


**Upgrade note for v2.5:** the installer continues to use the same `foxworx-workbench` systemd user service, settings file, and `~/.local/share/foxworx-workbench-v2` SQLite state directory. The pet conversation table is created on startup. Existing DreadFox profiles default to **offline dialogue** until explicitly changed; no historic Kali or copilot messages are imported. Back up the state directory with the service stopped before upgrading. If your installation already uses Cloudflare, preserve its configuration and confirm the `cloudflare` mode/JWT authentication is still active before allowing team access.

## Rabbit Hole setup (v2.6)

No additional OS service, CUDA driver, or separate scheduler is needed. The mode is integrated into `foxworx-workbench.service`; it uses the existing model settings, owner-bound SQLite store and bounded managed-job executor. The operator must configure an AI provider with functioning structured action support, and install the subset of `nmap`, `curl`, `dig`, and `whois` allowed by their testing policy.

Choose **AI copilot → Rabbit Hole**, define an objective and exact target, select permitted guided workflows, review the finite time/decision budgets, and explicitly confirm automation authorization. The service launches jobs within that grant and displays their progress with a Stop button. Use `docs/RABBIT-HOLE.md` for the workflow and limitations. Upgrading v2.5 retains the existing state directory; the new `rabbit` records are additive. **Always stop the running service and back up your SQLite state before installing the new source version.**

## v2.7 administrator tool policy requirement

After the non-root installer, Rabbit Hole cannot launch autonomous jobs until the administrator deploys a root-owned adapter policy. Read [ADAPTER-POLICY.md](ADAPTER-POLICY.md) and explicitly install a reviewed allowlist. For example:

```bash
bash scripts/adapter-policy.sh validate policy/adapter-policy.example.json
sudo install -d -o root -g root -m 0755 /etc/foxworx
sudo install -o root -g root -m 0644 policy/adapter-policy.example.json /etc/foxworx/adapter-policy.json
bash scripts/adapter-policy.sh check
```

Remove any unwanted adapters from your own reviewed policy before installing it. The provided sample enables all 17 profiles. No service restart is required to reload the installed policy. This policy does not enforce network egress isolation.


## v2.8 registered CLI adapters

The original schema-1 policy remains valid and **does not enable any newly registered executables**. A root administrator can register typed recipes for installed, noninteractive Kali programs with a schema-2 policy. Start by reviewing `docs/CLI-ADAPTERS.md` and the disabled-by-default library in `policy/adapter-policy.v2.example.json`.

```bash
bash scripts/adapter-policy.sh list
bash scripts/adapter-policy.sh validate policy/adapter-policy.v2.example.json
```

Copy the example, remove unwanted templates, and explicitly choose allowed IDs under `enabled_profiles`. Risky or intrusive review-only templates are never valid Rabbit Hole unattended grants. Install only the reviewed policy using the trusted `sudo install` sequence described in CLI-ADAPTERS.md. **Do not simply copy the whole example and enable every tool.** The workbench intentionally does not install individual Kali programs, wordlists, credentials, or packet-capture permissions for you.


## v2.9 Tool Intelligence configuration

The new knowledge database is automatically created beside existing v2 application state. You do not need to modify the administrator's Rabbit Hole adapter policy. Tool discovery, local documentation reading and cached retrieval work offline and do not require an AI API key.

Optional external documentation: edit `~/.config/foxworx-workbench/settings.env` and set `FOXWORX_DOCS_ONLINE=true`, then restart the user service. To enable external search in addition to direct Kali pages, configure a **private server-side** `FOXWORX_DOCS_SEARCH_KEY` issued for the Brave Search API. Never put it in the browser. See [TOOL-INTELLIGENCE.md](TOOL-INTELLIGENCE.md) for sources, privacy and the separate cache deletion procedure.


## v3.0 Investigation Graph upgrade

The **Graph** tab is installed with the existing FastAPI web service and requires no additional Python or JavaScript dependencies. It uses existing `workbench-v2.sqlite3` records and the saved `jobs/` evidence directory. No administrator adapter-policy change is needed.

For a safe upgrade from v2.9 on **either Kali ARM64 (Pi 4B) or Kali x86-64 (Z790)**:

```bash
# Stop current operations and export important evidence first.
systemctl --user stop foxworx-workbench
# Make a private, consistent backup of the DEFAULT state path:
umask 077
mkdir -p "$HOME/foxworx-backups"
tar -C "$HOME/.local/share" -czf "$HOME/foxworx-backups/foxworx-pre-v3-$(date +%Y%m%d-%H%M%S).tar.gz" foxworx-workbench-v2
# After extracting the v3.0 archive into a fresh directory:
cd "$HOME/foxworx-kali-workbench-v3.0"
bash scripts/install.sh --preflight
bash scripts/install.sh
bash scripts/doctor.sh
```

If you customized `FOXWORX_STATE`, back up that exact location instead. The installer reuses existing private settings and data. Open the web interface and select an engagement, then select **Graph**. Run one harmless authorized managed job and confirm a node appears and links to the saved evidence. For live Rabbit Hole branching, configure and authorize the existing administrator policy as described earlier in this guide.

If anything fails, stop the service and inspect `journalctl --user -u foxworx-workbench`. Roll back by reinstalling v2.9 into its **separate source directory** with your backed-up compatible state, while the service is stopped. Downgrades without a known compatible backup are not guaranteed. See [Investigation Graph](INVESTIGATION-GRAPH.md) for behavior and privacy limits.


## v3.1 Codex Agent upgrade (optional)

The FOXWORX installer does **not** install Codex automatically, and an OpenAI API key is **not** required for Codex's first-party ChatGPT account login. See [CODEX-AGENT.md](CODEX-AGENT.md) for current official installation commands, verification, eligibility, per-operator isolation limits and troubleshooting.

After installing Codex CLI as the same non-root service account, verify the absolute executable path via `command -v codex`. If installed in a nonstandard directory, add that absolute bin directory to `FOXWORX_EXTRA_TOOL_PATHS` in the private FOXWORX settings file, then restart the service. Example: `FOXWORX_EXTRA_TOOL_PATHS=/home/kali/.local/share/npm/bin`. Never add a directory writable by a less-trusted user to the executable search path.

**For Cloudflare installations:** Codex authentication goes through OpenAI's verification page, accessed from your personal browser. The Codex process and its private credentials stay on the Kali node. Do not open an alternate unauthenticated port or ask FOXWORX for an OpenAI password. The same Kali Linux service account can access files from every FOXWORX actor despite the API ownership controls; use separate Unix users or separate nodes for operators who are not mutually trusted.

On a service restart, active Codex turns end, while saved Codex sessions and managed sign-in can persist on the Kali node. Your existing AI API providers and Rabbit Hole policy are unchanged.

## v3.2 Hardware Intelligence acceptance check

The Hardware workspace runs without `lspci`, `lsusb`, or `iw` installed because it primarily reads Linux sysfs. `iw` is optional; without it wireless monitor-mode capability is reported as unknown. The existing `nvidia-smi` integration remains optional.

After upgrading and restarting the workbench, select **Hardware → Rescan**. Confirm visible network interfaces against `ip -br link`, and validate that the management connection's default-route interface is marked **Protected**. If using a separate Alfa adapter, verify it produces a Linux WLAN interface; a USB record alone does not prove that its driver is ready. Designate a separate nonmanagement adapter as Assessment only after confirming your own network topology.

To test binding, use **Toolbox → curl → HTTP headers**, enter an authorized test URL, and select the named Assessment interface. Review the preview; a supported libcurl adds `--interface if!<name>`. The kernel may reject device binding if permissions or routes are missing. Do not use this mechanism as network isolation.

Read [Hardware Intelligence](HARDWARE-INTELLIGENCE.md) for supported classes, administrator considerations and verification commands. All previous configuration/state, including Codex sign-in, DreadFox and engagement history, is preserved.

## v3.3 Discord team integration (optional)

The Discord bridge is disabled until a bot token and channel ID are set on the host. See [Discord Team Intelligence](DISCORD-TEAM.md) for the least-privilege bot setup, Message Content requirements, team-key mapping, draft approvals, rate-limit handling, privacy and troubleshooting. **Never place the bot token in source control.** Existing v3.2 databases and configuration are preserved.
