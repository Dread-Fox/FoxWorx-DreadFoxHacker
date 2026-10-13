> **v3.3.3 local + tunnel:** Open http://127.0.0.1:8765 locally, or allow one protected HTTPS tunnel hostname without disabling localhost. See [LOCAL-SERVICE.md](LOCAL-SERVICE.md).

# Operator guide

## A deliberate workflow

Create one engagement per authorized program or customer assessment. Record the policy URL, permitted assets, exclusions, prohibited methods, relevant traffic limits, and the date you reviewed permission. The URL is a reference, not a synchronized or verified authorization source. An asset discovered by a tool does not automatically become in scope.

Start in **Tutor** mode to refresh unfamiliar syntax. Tutor sends your question and engagement context for explanation but cannot prepare executable proposals. **Copilot** may discover installed tools and prepare one or more proposals; every proposal still needs explicit human review. Neither mode submits HackerOne reports or validates a finding as exploitable merely because a tool printed it.

For guided tool use: select a tool, choose its recipe, enter one authorized target, preview the exact command, then approve. Exclusions take precedence. `*.example.com` does not include `example.com`, and a URL path scope does not authorize a host-wide Nmap scan. Editing assets or authorization notes invalidates older proposals. A proposal expires after ten minutes and cannot run twice.

## Hardware Intelligence and device roles

The **Hardware** tab lists interfaces, PCI/USB devices, graphics nodes, kernel-exposed accelerators and selected other Linux hardware. Refresh to obtain a current inventory. Loopback/default-route interfaces are protected management devices; assigning an Assessment role to another interface changes FOXWORX's per-operator metadata, **not** Linux networking or radio state. Certain guided Curl HTTP jobs can explicitly request an assessment interface; exact device binding is part of the human-reviewed command. See [Hardware Intelligence](HARDWARE-INTELLIGENCE.md) for details and limitations.

## Terminal versus managed job

The terminal is a real interactive shell with ordinary shell syntax, pipelines, scripts and installed terminal agents. It starts inside the engagement workspace. Jobs execute a literal argument array in that same workspace, with stdin closed. They do not inherit a terminal's current directory, shell variables, aliases, activated virtualenv or shell history. Use explicit executable paths/environment setup in the terminal for such workflows; keep secrets out of job argument previews and logs.

A tool that asks questions or opens a full-screen console belongs in Terminal. The toolbox's **Insert name in terminal** inserts the discovered executable name **without pressing Enter**. Review/add arguments before running. A GUI-only application needs a separate approved desktop; no remote desktop is bundled.

The service deliberately prevents privilege escalation. A command requiring root, file capabilities, a privileged group, a display, a database, a wordlist, a license or hardware may fail even when its executable was found. Fix administration issues outside the web session using an appropriate account; do not solve them by running the workbench as root.

## Sessions and reconnect

Browser disconnect detaches from the in-memory PTY; the shell can keep working. Reconnect obtains a new ticket and replays the latest bounded output. Typed input is not stored for retry, so a dropped connection will not silently repeat a command. Up to four sessions are allowed by default. A detached session expires after one hour. Close unwanted sessions to release resources; exited shells continue to appear until closed/expired.

Closing a terminal terminates its shell-session processes. Restarting/stopping the service ends all terminals and interrupts active managed jobs. Terminal persistence is **not** persistence across service restarts or power loss. The client remembers the selected session ID, not a durable terminal recording. Multiple tabs under the same identity can attach to the same terminal; coordinate before typing.

Ctrl+C interrupts the foreground terminal program. Ctrl+Shift+C copies a selection; clipboard permission may require a secure browser context and user gesture. Multiline paste requires confirmation because it may execute commands. Font-size controls help on small screens.

On a phone, swipe vertically inside the terminal to browse output without scrolling the surrounding page, or drag the large **Output history** bar below the terminal. Move left for older lines and right for newer ones. **Latest output ↓** returns to the bottom and resumes following output. New output leaves your reading position alone while you are above the bottom. The history bar also supports arrow keys, Home and End. Scrolling controls do not focus the shell or open the phone keyboard. History is bounded to 3,000 scrollback lines in the browser and is disabled for fullscreen programs using the alternate buffer; those programs manage their own navigation. Complex interactive work still benefits from a physical keyboard.

## Jobs, output and stop semantics

The Jobs view shows the most recent 200 jobs **within the chosen engagement**. States distinguish queued/running/stopping, succeeded (exit 0), failed (nonzero or launch error), stopped, timed out, output limit and interrupted. Submission is not success. Logs capture stdout and stderr separately and as a combined stream; the combined stream is an observed interleaving, not exact causal ordering.

Default managed-job limits: two concurrent jobs, 15-minute timeout, 5 MiB combined captured output. Logging a copy into stdout/stderr files means approximately twice the captured bytes on disk. The output cap can terminate a noisy job; it is not merely a display limit. The browser displays a bounded 300,000-character window. Full captured logs are in Evidence. UTF-8 output paging preserves complete characters across chunk boundaries.

**Stop managed jobs** stops your managed jobs on the node, across engagements. It deliberately does not pretend to stop every shell, daemon or unrelated system process. Stop terminal work with Ctrl+C/Close as appropriate. A subprocess that deliberately escapes its supervised session is outside this application's containment guarantees; systemd also uses control-group cleanup on service stop.

Select a finished job and click **Delete job** to permanently remove its job record and captured stdout/stderr logs. Confirm the dialog; export evidence first if you need those logs. Failed, stopped, timed-out, output-limited and interrupted jobs can also be deleted. Active jobs must finish cleanup first; jobs used by an active Rabbit Hole run cannot be deleted until the run stops or finishes. Workspace files, existing exports, consumed approvals and audit history remain. Deleted jobs disappear from future evidence exports and job nodes in the graph. Finished Rabbit Hole steps retain their status and show that their job logs were deleted.

## Files and reporting

Files created in the engagement directory appear in Evidence. Uploads are limited to 10 MiB and never overwrite an existing filename. Downloads serve regular files as attachments and refuse symlinks/path traversal. The list is capped at 1,000 files with a visible warning. Larger workflows need local artifact management.

An evidence export includes engagement notes, job metadata, raw captured logs, a report draft and a SHA-256 manifest. Workspace files are opt-in. Export is limited to 64 MiB uncompressed input and 10,000 jobs; oversized exports fail instead of silently omitting records. Stop active jobs before export, and finish/close terminal writers before requesting workspace files. Otherwise arbitrary shell writers can still change files during export. A checksum is not a signature or immutable audit trail.

No terminal keystroke recording or complete terminal transcript is included. Use a reviewed local recording approach separately when engagement rules require it. Review the export for secrets, unrelated data and personal information before sharing. Tool output is an observation, not a finished vulnerability report.

## AI privacy

Every chat request sends your message, engagement name/scope/notes and a small recent-chat window to the configured provider. The complete terminal stream and workspace are not sent. A selected job's command and last 12 KB of output are sent **only when the sharing checkbox is enabled**. Selecting a job alone is not consent. Selection → draft copies terminal text into the unsent chat draft; inspect it before Send.

Best-effort redaction removes some recognizable credentials; it is not complete DLP. A `store:false` API request does not establish zero provider retention. Do not include information your program/client does not permit sharing. Native terminal agents are independent programs with their own keys, policies and execution permissions; installing one does not integrate its approvals into the workbench.

## Troubleshooting

| Symptom | Check/action |
|---|---|
| Installer cannot access systemd user session | Log in normally as the dedicated user rather than `sudo su`; verify `systemctl --user show-environment`. |
| Port 8765 is occupied | Check whether v1 is running. Stop it deliberately or choose another port in configuration. Do not kill an unknown listener. |
| 403 unexpected hostname/origin | Match FOXWORX_ORIGIN and the published Host exactly; avoid Cloudflare Host rewrites or mismatched forwarded ports. |
| Cloudflare identity could not be verified | Check HTTPS team domain, application AUD, email allowlist, Pi clock, CA certificates and outbound JWKS access; sign in again. |
| Terminal fails but page loads | Check Access coverage of WebSocket path, exact Origin, browser/network restrictions and session lifetime. New tickets are short-lived and one-use. |
| Terminal shows old/missing session after restart | Service restart ends terminals; create a new one. Managed jobs are marked interrupted and not repeated. |
| Tool installed but missing from toolbox | Refresh inventory. Configure an additional **absolute directory** in FOXWORX_EXTRA_TOOL_PATHS, then restart. Shell functions/aliases and nonexecutable scripts are not standalone entries. |
| Tool exits immediately | Examine exit code and stderr. Prompts need Terminal; GUI needs a desktop; dependencies/hardware/tokens may be absent. |
| `sudo`/file-capability behavior differs from SSH | Intentional NoNewPrivileges service restriction. Use separate administrator procedures, not root web service. |
| AI unavailable | Set both key and model locally; verify provider project access, billing, limits and network. No provider key is sent to the browser. |
| AI request times out | Draft remains. Check pending proposals/jobs before repeating; a failed browser response is not proof the server received nothing. |
| Node slow or low disk | Stop selected work; close terminals; inspect logs/artifacts and memory. The app does not quota arbitrary shell processes/files. |
| Browser clipboard blocked | Select text and copy manually; use the proper secure origin and user gesture. |
| Foreground job cannot read piped input | Job stdin is closed. Use the real terminal or an explicit input file. |

```bash
bash scripts/doctor.sh
systemctl --user status foxworx-workbench --no-pager
journalctl --user -u foxworx-workbench -n 100 --no-pager
uname -m
```

Review diagnostic/log output before sharing it; paths, commands and artifacts can themselves be sensitive. Never attach the settings file or tunnel token to an issue.

## Your companion — DreadFox

The DreadFox tab is an optional, private digital pet. Hatch once to begin recording generic categories of FOXWORX activity. Its portrait, mood, tails, XP and memories change as you perform reviewed workbench tasks. It is not an AI model and cannot use tools. Use **Play / Snack / Rest** for companionship (cooldowns apply). Open the bottom settings section to rename it, pause tracking, or erase everything. For long-term growth thresholds and privacy restrictions, see [DREADFOX.md](DREADFOX.md).


## Codex Agent / ChatGPT sign-in (v3.1)

Select **Codex Agent · ChatGPT sign-in** in the AI mode selector. Install the official Codex CLI if the panel reports `Not installed`. Use **Sign in with ChatGPT**, open the official verification URL and enter the one-time code there. Once connected, submit a prompt in the ordinary composer. Codex agent messages stream into its status area while a completed turn is saved separately by engagement. Codex uses a read-only execution policy, not Rabbit Hole's adapter permissions. It may still read files visible to the service Linux user. See [CODEX-AGENT.md](CODEX-AGENT.md) for the complete security, login and usage model.

## Discord team collaboration (v3.3)

In **Scope & notes**, set the same team key as your colleagues. In **Team / Discord**, read channel messages tagged to that key, create drafts and publish reviewed summaries. Copilot/Rabbit Hole/Codex can use those snippets as untrusted operational context; they do not become executable instructions. The operator must approve every outbound draft, including a completed Rabbit Hole summary. For configuration, permissions, limits and privacy considerations see [DISCORD-TEAM.md](DISCORD-TEAM.md).
