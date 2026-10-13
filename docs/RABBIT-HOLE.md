> **v2.8 extension:** Rabbit Hole can now use schema-2 administrator-registered, typed command templates with explicit operator grant, in addition to the 17 built-in recipes. Review-only templates can be proposed by Copilot but never executed unattended. See [CLI-ADAPTERS.md](CLI-ADAPTERS.md).

# Rabbit Hole — bounded autonomous guided investigation (v2.7)

Rabbit Hole is an **operator-initiated, scope-bound, iterative job planner** for an explicitly authorized lab or engagement. Unlike normal Copilot, it may launch more than one **guided** Kali workflow without stopping for per-command approval. It is **not** an unrestricted autonomous shell agent, and is **not** a network sandbox.

## Operator workflow

1. In FOXWORX, create/select the correct **engagement**, enter the exact permitted target(s), exclusions, authorization notes, and permitted automation/rate limits. Verify the external program's up-to-date rules yourself; FOXWORX does not fetch/verify HackerOne permissions.
2. Select and test a cloud or self-hosted AI model under **Model & keys**. Your inference server must support function calls or a simple structured JSON reply. The operator should first test routine Copilot/Tutor use.
3. In **AI copilot**, select **Rabbit Hole · bounded automatic retries**.
4. Enter one **exact target** and select the **administrator-enabled, installed adapters** Rabbit Hole may use. Specify a maximum number of agent decisions (1–16) and run duration (1–30 minutes). One decision can launch at most one managed job.
5. Write a focused goal in the prompt, for example: *“Determine whether the authorized local lab host exposes HTTP or HTTPS service ports and explain what can be concluded from the checks.”* Review the profile selection and one-time authorization box. Press **Authorize & run**.
6. Observe the run's live status and individual job links. The fox companion remains independent; Rabbit Hole is part of the main agent, not DreadFox.
7. Click **Stop Rabbit Hole** whenever needed. Completed outputs remain in Jobs and exported engagement evidence. Failed/blocked runs provide a summary and possible next steps.

**There is no automatic continuation after a crash or service restart.** All queued/running records are marked interrupted on recovery. A new run requires a new explicit authorization. Starting one run does not grant a permanent AI capability.

## Current preapproved workflows (v2.6 baseline)

| Workflow | Executable | Allowed operation | Limits |
|---|---|---|---|
| `tcp-connect` | nmap | TCP service/version inventory | one host, 100 common ports, 10 probes/sec max configured, 60s host timeout |
| `tcp-web` | nmap | TCP service/version inventory on 80,443,8080,8443 | one host, 10 probes/sec max configured, 60s host timeout |
| `http-headers` | curl | HTTP(S) HEAD response headers | one exact URL, no redirects, 20s request limit |
| `http-options` | curl | HTTP(S) OPTIONS response metadata | one exact URL, no redirects, 20s request limit |
| `dns-a` | dig | DNS A lookup | one domain, one resolver call with limited retry |
| `dns-aaaa` | dig | DNS AAAA lookup | one domain, limited retry |
| `dns-mx` | dig | DNS MX lookup | one domain, limited retry |
| `dns-txt` | dig | DNS TXT lookup | one domain, limited retry |
| `whois` | whois | registration lookup | one domain, one invocation |

v2.7 expands this with eight more fixed-purpose adapters, all subject to the root-owned policy described in [ADAPTER-POLICY.md](ADAPTER-POLICY.md). **On upgrade, no autonomous adapter can run until the administrator installs that policy.** Only **installed** tools can run. If a dependency is absent, the agent receives the error and may select another approved method. Tools with interactive prompts, GUI requirements, arbitrary shell pipelines, file writes, plugins, credential attempts, or exploitation workflows are **not delegated** to Rabbit Hole in this release. Those remain available under the manual terminal/toolbox interfaces and existing human approvals where appropriate.

A hostname/IP target can be used by the HTTP profiles as `http://host/` if that derived URL is inside the engagement's saved scope. Supply `https://host/path` explicitly when required. HTTP URL-only authorization **never** implicitly grants whole-host port scans. Scope is checked on every derived profile target. The profile selection is fixed at run start; the model cannot add another target or workflow mid-run. Model-generated text never becomes a shell command.

## Retry behavior and termination

Every iteration: FOXWORX asks the selected model for exactly one `choose_workflow` or `finish_run` action, validates it against the operator's saved grant, prepares a **guided** JobManager proposal, and executes it using the same fingerprint, scope-stamp, timeout, output and concurrency gates as manual jobs. The service records an audit `rabbit-auto-job` event. It supplies the next model step with the previous workflow's status, exit code and **redacted, bounded output tail** so it can adapt after failed diagnostics. The normal Copilot proposal approval path is unchanged.

A run ends with: (1) model-reported success supported by at least one exited-successfully job, (2) a reported hard block and next steps, (3) the iteration/time budget, (4) repeated invalid/failed actions, (5) changed engagement authorization, (6) insufficient resources or missing permitted tools, (7) model/provider failure, or (8) operator stop. Failed steps are not silently counted as success. A model-reported result is **not independent proof that the user's objective is satisfied**; inspect the actual evidence.

**Default: eight decisions and 15 minutes.** **Hard caps: 16 decisions and 30 minutes** per run. At most two active Rabbit Hole runs per node, and only one per operator. Existing managed-job node concurrency, output, disk reserve, per-job timeout, and non-root service limitations still apply. This prevents unbounded expense/resource use. To continue beyond limits, review outputs and authorize a separate new bounded run.

## Privacy and limitations

- The selected AI provider gets the operator's objective, exact target, permitted workflow list, previous workflow status, and a bounded excerpt of generated output. Logs and prompts may contain confidential details. Redaction is best-effort, not a privacy guarantee; select a trusted local inference model for private engagements and avoid targets with secrets in URLs.
- Run records and managed job logs reside in the same local SQLite/state tree as v2.5. They are **not app-encrypted at rest**. Users of the same Linux account with unrestricted terminal access can inspect them.
- App-layer target checks are **not destination-level egress controls**. DNS rebinding, subprocess network access and program-specific scanner behavior may bypass these checks; do not rely on FOXWORX alone to enforce client scope. A restricted VM/container/namespace with enforced egress policies is required before treating unattended assessment as contained.
- Network requests from `dig`/`whois` may contact resolvers/referrals not named by the apparent target. The `nmap --max-rate` flag is not a universal network traffic limiter. External program terms might disallow all automatic testing.
- This version **does not** let the model execute every installed Kali command, arbitrary arguments, shell pipelines, exploit modules, brute-force tools, or a GUI workflow. Adding further safe typed adapters is an extension project with additional policy and integration testing.
- A result may be blocked because the chosen model can't produce structured actions, tools are missing, policy changed, available profiles aren't sufficient, or the platform's resources/time budgets are exhausted.
- The UI can run with Cloudflare Tunnel, but Cloudflare Access authentication/OS permissions and deployment need independent testing on your Pi/Z790.

## Backend API (authenticated)

`POST /api/rabbit-runs` requires CSRF and JSON:

```json
{
  "engagement_id": "<existing 24-char id>",
  "objective": "Review authorized local lab TCP and DNS basics",
  "target": "127.0.0.1",
  "profiles": ["tcp-connect", "dns-a"],
  "max_steps": 8,
  "max_minutes": 15,
  "authorized": true
}
```

`GET /api/rabbit-runs?engagement_id=...` lists operator-owned runs; `GET /api/rabbit-runs/{id}` returns current progress and job references; `POST /api/rabbit-runs/{id}/stop` requests cancellation. Authentication, CSRF, Origin and owner checks are inherited from FOXWORX. **Do not pass a generic bearer token for a system account to untrusted users.**

## Troubleshooting

- **Missing tools:** `command -v nmap curl dig whois`, then refresh the toolbox after installing OS packages permitted by your administrator. FOXWORX does not install scanning tools automatically.
- **Model stops early:** check that the selected provider supports function calling or strict single-action JSON. Check provider credentials, quotas, and server logs.
- **Scope rejection:** compare the exact target and *derived profile target* with the engagement inclusion/exclusion entries. Save changes, then authorize a **new** run.
- **No progress:** check whether a managed job remains active in Jobs; use Stop Rabbit Hole and review system logs before retrying.
- **Resource limit:** lower budgets and concurrent job counts, free space, or start later; do not turn off safeguards to make automation proceed.

For complete setup, see [INSTALL.md](INSTALL.md), [SECURITY.md](SECURITY.md), and [OPERATOR-GUIDE.md](OPERATOR-GUIDE.md).
