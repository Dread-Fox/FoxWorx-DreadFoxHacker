# FOXWORX v3.3.1 — local-service release verification

**Scope:** Local app defaults, config migration, token login, optional HTTPS proxy, installer static syntax, browser UI, and actual non-root local service operation. Build environment: Linux x86-64 container, not user's Kali ARM64 Raspberry Pi.

- **233 Python tests passed**, including new local-service tests (default port, missing and stale local auth tokens, no Cloudflare dependency, existing-config migration preserving other secrets, proxy Secure cookie and Origin/Host checks).
- **Offline Chromium desktop/mobile smoke passed**, no JavaScript runtime errors. Fixture data is simulated, not a live Discord/Codex provider session.
- **Live non-root service smoke passed** with real localhost HTTP, authenticated sessions, terminal PTY/WebSocket, managed job, Graph evidence, device inventory and companion data. No external service or offensive target was contacted.
- **Non-root installer preflight passed** on build-host Linux x86-64. Shell, Python and browser JavaScript syntax checks passed.
- The default service requires **no Cloudflare binary, account, Access team, AUD, or external hostname**.
- The default listener is intentionally **127.0.0.1:8765**, not a LAN/public listener. Optional HTTPS proxy mode must be configured later and protected at the edge.

**Not verified on the Raspberry Pi:** platform-specific dependency installation, actual ARM64 performance, user-systemd boot persistence, optional external tunnel, live Discord, live Codex or model-provider authentication.
