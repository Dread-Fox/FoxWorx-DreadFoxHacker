# FOXWORX v3.0 — Investigation Graph

FOXWORX now includes a persistent, evidence-linked visualization of **managed jobs** and **Rabbit Hole runs**. The feature works offline with the existing browser and Python stack and introduces no new remote service, AI charges, CLI permissions or Cloudflare configuration.

## What is captured

- Engagement → Rabbit Hole investigation → ordered agent decisions and actual managed jobs
- Failure/retry branches and current job/run statuses (queued, running, succeeded, failed, blocked, stopped)
- Manual, reviewed toolbox jobs saved under an engagement
- When available, **approved target** → guided job relationships using the actual approved proposal's `target` (no target guessing from command strings)
- Carefully parsed output observations for **Nmap/RustScan open ports; Curl/HTTPx HTTP status lines; OpenSSL TLS protocol lines; and Dig/DNSRecon DNS records**. These are *unverified reports of text in tool output*, not validated vulnerabilities.
- Operator-written annotations, saved separately from canonical jobs and visible only to that operator's application identity

Raw command output and full commands are **not embedded in the graph response**. Open the Jobs panel from a graph node to inspect the recorded execution and evidence. AI summaries from a run remain explicitly unverified and are not promoted to findings. Unrecognized tool output is available from Jobs but does not produce automatic observation nodes. No terminal keystroke recording or shell history interception is added.

The graph is **derived from durable SQLite job/run records on each request** and is therefore retained after service restart without duplicating operational history. Notes use the existing per-owner SQLite records, and there is no destructive schema migration. For responsiveness, projection reads a bounded recent history (160 managed jobs, 70 Rabbit Hole runs, max five observations from each successfully finished job). Raw log inspection is capped at 128 KiB per job and first 3,000 lines. Earlier history remains in the canonical store; graph history beyond those limits is not shown. The graph indicates truncation when it reaches its cap.

## Using the interface

1. Sign in and select an engagement.
2. Open **Graph** in the middle workspace.
3. Choose **Execution map** (focus on decisions, retries, and managed jobs) or **Investigation + observations** (adds approved targets and recognized output signals).
4. Filter by text, job status or time window. Pan by dragging the canvas background; zoom using mouse wheel or **+ / −**; **Reset view** restores the default viewport.
5. Click a node or use the keyboard-accessible **Operation index** to see its evidence references, status, provenance and any notes.
6. Use **Open recorded job & output** to inspect its actual command, stdout/stderr and status in Jobs. Annotate the node with your independent assessment, if useful. Empty annotation removes the saved note.
7. Download **JSON** (full bounded graph projection), **SVG** or **PNG** (visible canvas viewport) for internal reporting. Review for target names and confidential annotations before sharing.

The Graph refreshes approximately every three seconds while its tab is visible. It does not request a fresh scan, execute anything, or perform model inference. Graph export does not authorize remote uploads or add findings to HackerOne. All API calls follow the same authentication and CSRF requirements as the existing workbench.

## Reliability and privacy

- A node's `origin` distinguishes manual operator jobs from Rabbit Hole jobs. An orange **retry** edge means a new decision followed a failed/blocked execution in the same run, not that either operation was successful.
- Failed/incomplete processes cannot create automatically parsed observation nodes; they still appear as failed/blocked job nodes with their logs linked.
- App ownership restricts graph records by authenticated operator and engagement; operators on the same Unix service account are still **not OS-isolated**.
- Parsed output is **untrusted data** and is rendered using text nodes, never as executable HTML. Parsing never launches executables. Notes are not authoritative findings and cannot change job records or tool permissions.
- Independent containment for penetration-testing targets still requires host/network-level controls. Rabbit Hole remains governed by the previously installed administrator-owned policy.
- This release does **not** imply verified host reachability, arbitrary tool output parsing, universal network topology discovery, individual terminal command tracking, or machine-learning vulnerability attribution.

## Troubleshooting

`/api/engagements/{engagement_id}/graph` returns the actor-scoped projection. A `404` means the engagement was not accessible under the authenticated identity. Confirm the engagement selector and Jobs record first if the graph is empty. A tool job must be recorded as managed execution; launching a program inside an unrestricted terminal will not create an individual graph job.

To inspect service errors:

```bash
systemctl --user status foxworx-workbench
journalctl --user -u foxworx-workbench -n 100 --no-pager
```

Graph annotations are included when you back up the existing `~/.local/share/foxworx-workbench-v2` directory. Stopping the service for a consistent backup is still recommended. See `INSTALL.md` for the complete upgrade and rollback procedure.
