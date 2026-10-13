# FOXWORX DreadFoxHacker v3.3.3 — Release verification

**Date:** 2026-10-11. **Scope:** token-free browser access and no application Cloudflare hostname registration, with preservation of the Kali workbench, terminal, AI, Discord, hardware and graph. Tests executed on a Linux x86-64 build system, **not** on the user's Kali Pi or against live Cloudflare services.

- **242 Python regression tests passed**. New tests exercise default no-token settings, no-login sessions on localhost and multiple HTTPS domains, tunnel Host rewriting, preservation of credentials/state during migration, and mutation request checks.
- **Offline Chromium browser smoke passed** at desktop and mobile sizes. Token-free boot hides both the login card and Sign out control, while Codex, Discord Team, Graph, Hardware, Tool Intelligence, and DreadFox fixture checks remain functional.
- **Actual non-root service smoke passed** under an unprivileged Linux user: HTTP without login cookies, session and Origin/CSRF, real PTY over ticketed WebSocket, bounded managed job with saved output and investigation graph annotation, hardware inventory, cached CLI knowledge, provider selection, and DreadFox companion activity.
- Python compile, JavaScript syntax and shell syntax checks passed.
- No Cloudflare Tunnel integration, Cloudflare Access credentials or public hostname registration is required by the default service. Listening address stays `127.0.0.1:8765`.
- The installer backs up and migrates only authentication mode/port/origin; existing state, model credentials, Discord and Codex configuration are preserved (and still usable if otherwise valid).

## Important security and compatibility tradeoffs

`FOXWORX_AUTH_MODE=open` is **not authenticated**. Everyone who can reach a machine's published endpoint can operate the server-side terminal with its unprivileged Linux account. No application-level user separation, session login, JWT or email allowlist applies. Browser Origin/CSRF checks and short-lived terminal tickets are not substitutes for network or identity access controls. The operator is responsible for any tunnel exposure and may independently enable Cloudflare Access if desired.

Live Pi ARM64 installation, systemd startup after reboot, cloudflared route/websocket transport, direct Codex/ChatGPT login, real Discord API communication, and inference providers still require testing on the target systems. No real network assessments or external inference were conducted during verification.
