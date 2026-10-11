# FOXWORX v3.0.0 verification report

**Release type:** source distribution for Kali Linux ARM64 / x86-64, trusted-operator testing. **Not** independently audited or run on the user's actual Pi/Z790/Cloudflare deployment.

## Verified in the build environment

- **Python regression tests:** `python -m pytest -q` — **200 passed**. New graph tests cover persistent Rabbit Hole/manual job projection, failed-action retry links, approved-target grouping, unverified output parsing, ownership boundaries, annotations and refreshed job statuses. Existing functional tests for CLI, terminals, jobs, policies, AI providers, tool intelligence, DreadFox and evidence remain in the suite.
- **Live non-root localhost test:** `runuser -u oai -- python tests/live_local_smoke.py` (with a writable report location) — **PASS**, using actual authentication and CSRF enforcement, Linux PTY, real WebSocket, an approved local command and captured output, plus authenticated graph retrieval and stored note. No cloud API request, real pentest target, or Cloudflare connection was made. See `live-local-smoke.json`.
- **Offline Chromium UI fixture test:** `python tests/browser_smoke.py` — **PASS**, Chromium 144, zero page JS exceptions; desktop (1600px) and mobile (390px), new Graph tab, retry link, node inspector, save notes, responsive navigation, filter, zoom, and actual downloadable JSON/SVG/PNG files. The graph/sample scan data is **simulated**; the fixture test is not a browser-to-live-server E2E test. See `browser-smoke.json` and `ui-investigation-graph-*.png`.
- **Syntax:** `node --check static/{app,graph}.js`, `bash -n scripts/*.sh`, `python -m compileall -q foxworx` — PASS.
- **Clean-extraction test:** full Python suite retested against the release ZIP; results below are recorded after packaging.
- **Packaging:** ZIP and tar.gz integrity tested and SHA-256 hashes generated. Each distribution includes installer, the v3 installation instructions, security documentation, CLI and adapter policies, offline browser assets, tests, and all Python sources.

## Important functional boundaries

1. **Graph contains managed jobs and Rabbit Hole runs only.** Ordinary terminal keystrokes, interactive commands and arbitrary manual filesystem exploration are not tracked individually.
2. **Recognized output is not validated vulnerability evidence.** Only successful completed jobs using supported text formats yield small parsed observation nodes. Graph edges document actual workflow/proposal relationships, not inferred exploit chains.
3. **Pagination and cost limits:** most recent 160 jobs and 70 Rabbit Hole runs per engagement; five parsed observations per successful job; cached output parsing; 65 visible graph nodes at a time. Full evidence files remain separate.
4. **Privacy:** annotations and graph records use existing per-operator app ownership. The application's shared Linux process/account is not a secure OS-level tenant boundary. Graph JSON/SVG/PNG exports may contain target names or annotations; review before sharing.
5. **No new execution authority:** graphical projection only, no autonomous CLI additions, no changed policy, no new AI inference calls or documentation downloads.
6. **Unverified on target hardware:** fresh pip install and ARM64 dependencies, systemd logout/reboot behavior, Cloudflare Access/Tunnel, NVIDIA GPU inventory, real model responses, and supported Kali utility output variants. Confirm these before inviting remote team members.