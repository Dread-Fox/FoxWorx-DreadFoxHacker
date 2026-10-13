# Tool discovery and autonomous Rabbit Hole verification

Date: 2026-10-12 (America/Denver). Environment: Linux x86-64, Python 3.13.9, configured project virtual environment. This report covers implementation in the shared source workspace, not a deployed service upgrade or live external assessment.

## Results

- `bash scripts/test.sh`: **306 passed, 1 skipped**, plus Python compilation, JavaScript syntax and shell syntax checks. The existing Starlette/AnyIO deprecation warning remains.
- Offline Chromium browser smoke: **PASS** at desktop and 390-pixel mobile widths, including installed-CLI selection, 64-decision/60-minute defaults, sending a supplemental instruction during a run, pending instruction display, cancellation and no horizontal overflow. All rendered target, provider and terminal values are fixtures.
- Synthetic discovery tests cover **4,000, 20,000 and 50,000 tools**. Relevant tools late in the inventory are retrieved, exact names rank first, pagination exposes total counts and stale cursors, and returned context remains bounded.
- Real harmless local fixture programs exercise failed command → successful alternative without a human approval round trip. Records retain run/job linkage and output.
- Tests reject queued launch after stop, policy revocation, changed executable, changed engagement scope or changed instruction revision. Policy revocation during a running job stops its process.
- Supplemental prompts submitted during inference discard the outdated action. Ten queued instructions all reach later decisions; no accepted instruction is silently omitted. Follow-ups do not extend target or elapsed budgets.
- Late final inference cannot report successful completion after budget expiry. Identical executable/argument failures are not repeated indefinitely.
- Schema-1/2 policies keep their permissions and ceilings. Workflow-only grants cannot execute direct CLI actions. API tests cover loopback local access, Origin/CSRF, actor ownership, invalid messages and ended runs.
- Local metadata cache tests cover executable identity changes and removal without executing the discovered program. Background refresh is search-triggered after 60 seconds, single-flight, and preserves the last successful inventory on failure.
- An independent read-only code review identified instruction truncation, reproduced by a failing regression and fixed. Follow-up review found no remaining Important findings.

## Synthetic benchmark

See [benchmark data](tool-discovery-benchmark.json) and `tests/benchmark_tool_discovery.py`. On this host the 50,000-entry in-memory index built in approximately **339 ms**. A targeted warm query had approximately **0.017 ms p95** latency. The targeted shortlist was about **580 bytes**; a broad 40-result page was about **10 KiB**. These are fixture measurements, not guarantees for arbitrary queries or hardware. Filesystem scanning, package/manual enrichment and inference are not included in those timings.

## Artifacts

- [Offline browser results](autonomy-browser-smoke.json)
- [Desktop autonomous run fixture](ui-autonomous-cli-desktop.png)
- [Mobile autonomous run fixture](ui-autonomous-cli-mobile.png)
- [Operator setup and execution boundaries](../docs/RABBIT-HOLE.md)
- [Discovery behavior](../docs/TOOL-DISCOVERY.md)

No live provider calls, external target assessments, live Discord integration, root policy installation or service deployment was performed for this feature. Installed CLI mode intentionally uses the existing Linux service account and is not an OS or network sandbox. Target-side ARM64 installation and performance require separate verification. Enabling this mode requires deliberate installation of an administrator policy permitting it; this change does not silently grant that capability to older policies.
