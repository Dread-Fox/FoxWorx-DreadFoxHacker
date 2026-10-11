# Installation, remote access and recovery

## 1. Choose the host account

Targets: Raspberry Pi 4B running Kali **ARM64**, or a conventional Kali **x86-64** PC (including NVIDIA GPU workstations), Python **3.11+**, a writable home directory and systemd user services. The app also runs on Linux development hosts; native Kali compatibility is a separate test. Kali's official Pi documentation is linked in DEPENDENCIES.md.

Use a dedicated non-root account. Do not put it in privileged groups or give it passwordless sudo merely to make a tool work. Install OS packages through your separate administrator access. The service's `NoNewPrivileges=true` intentionally blocks privilege escalation; raw sockets, capture devices and GUI programs are not guaranteed to behave as in an unrestricted administrator SSH session.

Keep the host powered, cooled and backed by reliable storage. Job logs and artifacts can fill a microSD card. The job log cap does not impose a filesystem quota on arbitrary tool-created files. Check Node health regularly.

## 2. Extract and install

Extract the release ZIP under your home directory. The top-level directory is `foxworx-kali-workbench-v3.0`. Use a path without whitespace, quotes, percent signs or backslashes; the installer validates this to avoid systemd quoting problems. Do not move it after installation without rerunning the installer.

```bash
cd ~/foxworx-kali-workbench-v3.0
bash scripts/install.sh --preflight # no modifications
bash scripts/install.sh
```

The installer creates `.venv`, installs pinned direct dependencies plus the LiteLLM AI extra by default, preserves/creates private configuration, and registers **foxworx-workbench.service** as your user. It requests sudo only for `python3`, `python3-venv`, and `ca-certificates`. It does not run an unattended full OS upgrade. `unzip` is needed separately to extract a ZIP.

**Architecture-specific first-run defaults:** ARM64 nodes start with 2 managed jobs, 4 terminal sessions and a 256 MiB free-disk reserve. x86-64 nodes start with 4 jobs, 8 terminals and a 1024 MiB free-disk reserve. These are application resource limits, not guaranteed performance or CUDA settings. **Existing v2/v2.1 configuration is never overwritten with these defaults.**

See [Pi and Z790 platform guide](PLATFORMS.md), including optional GPU inference and SSH forwarding to a workstation-hosted model.

Options:

```bash
bash scripts/install.sh --preflight      # hardware/platform report only, no writes
bash scripts/install.sh --skip-apt       # OS dependencies already present
bash scripts/install.sh --no-start       # prepare without starting the service
bash scripts/install.sh --without-ai     # skip LiteLLM; terminal/toolbox only
```

The v2 service is distinct from v1's **foxworx.service**. If v1 is using port 8000, stop it deliberately before starting v2:

```bash
systemctl --user stop foxworx
```

Stopping a service can interrupt work. The installer does not delete or silently stop v1 or v2. It refuses to replace a running workbench service; stop it yourself after preserving needed evidence, then rerun the installer. V2.4 reuses the v2 settings and SQLite state; it does not delete the old source folder.

## 3. Local setup and login

```bash
bash scripts/configure.sh --show-token
systemctl --user status foxworx-workbench --no-pager
```

Open `http://127.0.0.1:8000` on the host and paste the local setup token. For a workstation browser, first establish `ssh -L 8000:127.0.0.1:8000 operator@YOUR_PI_ADDRESS`. Keep the forwarded port identical to the configured port so Origin and Host checks match. A different browser origin will be rejected.

Local mode is not anonymous: API requests require the setup login. It also rejects non-loopback peers, unexpected Host headers and Cloudflare forwarding headers. Do not treat these checks as permission to expose local mode publicly.

```bash
bash scripts/configure.sh --rotate-token
systemctl --user restart foxworx-workbench
```

Rotation changes both the local token and signing secret. Restart applies it and invalidates old local cookies. Sign-out clears the browser cookie but does not cryptographically revoke a stolen cookie before its expiration; rotation is the response to suspected local-token compromise.

## 4. Configure AI provider and model

In your authenticated browser, click **AI copilot → Model & keys**, choose one of the ten providers, save a provider key for cloud access if needed, select an exact model ID and click **Use this model**. The **Test selected connection** button makes a short real inference request. For local models on the current node or a private GPU desktop, enter administrator-approved endpoints in the private config first; see **[Universal AI providers](AI-PROVIDERS.md)**. There is no fixed model entitlement, and a provider website subscription is not necessarily API access.

To edit shared host credentials, Cloudflare configuration, or approved local endpoints:

```bash
bash scripts/configure.sh
```

The configuration is stored at `~/.config/foxworx-workbench/settings.env` with mode 600, outside the release directory. Do not paste keys into chat, a support request, an engagement, a screenshot or source control. An AI error does not disable terminal/toolbox operation. API use can incur provider charges; set provider project spending limits independently.

## 5. Publish through Cloudflare Tunnel + Access

These steps configure your own Cloudflare account; the installer does not perform them.

1. Create a **self-hosted Access application** for a dedicated hostname such as `kali01.example.com`. Use restrictive Allow policies for named identities and enforce MFA through your identity/Access policy. Do not use a public Bypass policy for the app or its WebSocket path. Record the application **AUD** and team domain `https://YOURTEAM.cloudflareaccess.com`.
2. Install **cloudflared's official architecture-matched Linux package** on the host and create an outbound named tunnel using Cloudflare's current dashboard instructions. Keep the tunnel token secret. Do not use a public quick tunnel for a full shell.
3. Use `bash scripts/configure.sh` to set `FOXWORX_AUTH_MODE=cloudflare`, `FOXWORX_ORIGIN=https://kali01.example.com`, your team domain, AUD, and comma-separated permitted operator emails. The application's email allowlist is an additional check, not a replacement for Access policy. Restart the workbench.
4. Publish the hostname to **http://127.0.0.1:8000** (or your configured local port). Keep the browser's public Host header intact; an origin Host rewrite to localhost will fail the app's exact-host check. Use an HTTP application route: the web terminal travels over the application's own WebSocket, not Cloudflare's separate SSH rendering feature.
5. Require Access at the edge and, where configured, tunnel origin protection as an additional layer. The workbench itself verifies the JWT signature, issuer, audience, expiry and allowed email. It does not trust a bare email header. Do not publish an unprotected alternate hostname to the same origin.
6. Test a permitted user and an explicitly nonpermitted user. Check Terminal open/resize/reconnect, a harmless local job and evidence download through the public hostname. Confirm your allowed identities and actual MFA behavior in your tenant.

Before public use, test that the origin rejects unauthenticated API access. Since cloudflare mode also checks Host, use the configured public Host while connecting locally:

```bash
curl -i http://127.0.0.1:8000/api/session -H 'Host: kali01.example.com'
```

Expected: **401**, not user data. Without the matching Host, **403** is expected. Do not weaken host checking to make this command succeed. There is no unauthenticated diagnostics endpoint in cloudflare mode.

Cloudflare edge restarts, connectivity or Access expiry may close a WebSocket. The client obtains a fresh one-use ticket and reconnects; it never repeats typed input automatically. The backend also limits a socket's identity lifetime to at most 15 minutes or the Access token expiry, whichever is sooner. Removing a user from Access may not instantly invalidate an already issued token; verify revocation/session-duration behavior in your tenant.

**Cloudflare Tunnel is ingress only.** Nmap, curl and other Kali tools normally send traffic from the Pi's own network path. This distribution does not provide Cloudflare egress, a scan proxy or hidden source IPs.

## 6. Keep the service available after logout

```bash
systemctl --user enable foxworx-workbench
```

For startup without an interactive login, an administrator can review and enable lingering:

```bash
sudo loginctl enable-linger "$USER"
```

This is not done automatically. Test an actual reboot, then verify both cloudflared and the workbench. Do not assume a successful local `systemctl` call proves remote reachability.

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