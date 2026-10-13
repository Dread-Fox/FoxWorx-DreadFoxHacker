# Security model · v2.9.0

## Intended trust boundary

This is a **trusted-operator Linux workstation**, not a hosted service for mutually distrustful tenants. Full shell access gives a web operator the authority of the process's Linux account. Web actor checks organize access but do not stop that shell user from reading/modifying the same UID's evidence, database, source, configuration, API keys or processes. The API-key environment allowlist reduces accidental inheritance, not same-account secret access.

Prefer one operator/account/node, or only operators trusted equally with that node's entire account. Separate accounts/processes on the same host still need a deliberate isolation design. Real tenant isolation, network namespaces, destination allowlisted egress, secrets broker separation, signed audit storage and an external watchdog are **not implemented**.

## Implemented defenses

- The runtime and installer refuse root. The generated unit uses NoNewPrivileges, UMask 0077 and control-group cleanup. No sudo rule or privilege grant is installed.
- The listener binds only 127.0.0.1, with one worker and forwarded proxy interpretation disabled. Local setup uses a random token and signed, HttpOnly, SameSite cookie, exact Host checks and loopback constraints; forwarded Cloudflare headers are rejected in local mode.
- Cloudflare mode validates Access JWT RS256 signature through the team JWKS, issuer, audience, expiration and required claims; it requires an explicit allowed email. Missing/forged credentials fail closed. A claimed email header is insufficient. JWKS retrieval is HTTPS with certificate validation and bounded timeout/cache.
- Mutations require exact Origin and actor-bound CSRF verification. WebSockets also require authentication, exact Origin and a 30-second, one-use, owner/session-bound ticket. Long connections are bounded by token expiry and periodic reauthentication. Access policy/MFA itself must be configured in the tenant.
- Mutations have bounded request bodies. Uploads and regular-file downloads use path checks and no-follow protections; uploads do not overwrite existing files. These cannot defeat a hostile same-UID shell user who controls the whole account.
- Managed jobs use subprocess argument arrays without shell interpolation. Advanced arguments can still invoke interpreters or dangerous tool options. This is not a command sandbox or security allowlist.
- Proposals bind user, executable fingerprint, command, relevant engagement scope/notes, expiry and digest. Human approval is explicit and single-use; stale/replayed proposals are rejected. Executable fingerprint checking is a change detector, not race-free attestation against a malicious same-UID writer.
- Any supported provider may look up tools and propose jobs via its function-calling model, but the model can never approve a proposal or write to the terminal. Tutor mode independently rejects unexpected model tool calls. Provider/target text is treated as untrusted. Operator review remains necessary because a model can still recommend a bad command.
- Output is rendered as text, not inserted as HTML. Terminal clipboard-control sequences are not granted clipboard access. The page has a restrictive same-origin CSP and locally bundled assets; no runtime CDN, third-party analytics, web fonts or remote script loads.
- Default managed-job concurrency/time/output/disk-start limits and bounded PTY replay reduce accidental resource use. They do not constrain arbitrary terminal processes, descendants that escape supervision, or tool-created file sizes.

## Explicitly not guaranteed

No hostile multi-tenancy; no enforced HackerOne scope for terminal/advanced commands; no DNS-rebinding-resistant or redirect-aware egress sandbox; no automatic API scope sync; no live authorization verification; no guaranteed scanner request rate across arbitrary modules; no complete/signed/tamper-proof terminal audit; no disk quota; no root tool parity; no built-in GUI desktop; no independently audited production-hardening claim.

The Nmap recipe's scan-rate flag is not a universal application-request governor. WHOIS referrals and DNS resolvers contact infrastructure beyond the literal supplied hostname. HTTP guided headers do not follow redirects, but advanced/native tools can. CNAMEs, shared hosting, wildcard ownership and program-specific prohibitions require manual review.

## Sensitive data and persistence

Config (600) and state directory (700) are outside the source tree. V2.1 encrypts **API credentials only**, per operator, in SQLite using a separately configured Fernet key; the same Linux account can read both encrypted data and the key. This is not hostile-user isolation. Job command lines, artifacts, chat and audit metadata are stored locally; this is not encrypted-at-rest storage by the app. Use host storage encryption and an appropriate backup/retention policy. Terminal output has only a bounded in-memory replay buffer; input is not recorded. Requests go through the selected cloud/local provider and the LiteLLM adapter; retention and provider logging policies differ. Only same-provider-and-model chat history is replayed by the agent, and selected job output remains opt-in. Redaction is best-effort; no zero-retention guarantee is made.

Local sign-out does not stop active testing and does not immediately revoke stolen cookies. Rotate the signing secret/token and restart for suspected local compromise. Cloudflare logout/revocation behavior and token lifetimes depend on your tenant policy. Close active sessions when removing an operator, and rotate any keys that account could read.

## Deployment review

Verify current OS/tool updates, trusted source and artifact checksums, dependency vulnerability advisories, dedicated UID/no broad privileged groups, unexposed loopback listener, restrictive Access policy with tested MFA, matching app email allowlist, valid TLS origin, correct time synchronization, tested unauthorized rejection, backup/recovery and service-after-reboot behavior. Establish explicit customer/program authorization before traffic.

Before commercial client engagements, obtain an independent review and validate required isolation, logging, retention, contractual permissions and disclosure process. The provided automated tests and self-review are not an independent penetration test of the platform.

## Incident response

Use a trusted administrator channel to disconnect the tunnel or revoke access, stop the workbench service, preserve required evidence, rotate credentials reachable by the service UID, inspect that account and restore from a trusted image/backup as appropriate. The UI's Stop managed jobs button is not a universal host kill switch.

## Provider-specific security (v2.1)

Inference URLs cannot be submitted by web users. Administrator-approved URLs (plus fixed loopback defaults) are configured in the private Pi settings, using only HTTP(S) origins or `/v1` paths; model-discovery requests do not follow redirects. Review every remote address for SSRF, DNS rebinding, TLS, secrets and internal network exposure; **administrator approval is a trust decision, not a hardened outbound network sandbox**. Local OpenAI-compatible calls that lack a saved provider key use a dummy key rather than inheriting an ambient OpenAI cloud credential.

Changing the session secret/local login token does **not** rotate the separate `FOXWORX_AI_ENCRYPTION_KEY`. Back up that encryption key with the SQLite DB. Operators who share a Unix service account can read the config and database from the unrestricted native terminal; use separate operating-system isolation and a credential broker if team members are not mutually trusted. Cloud model providers may retain submitted assessment data according to their API terms.

## Cross-platform/GPU boundary (v2.2)

The workbench itself does not install or load NVIDIA drivers, grant PCI/GPU privileges, or expose an inference API. Its bounded `nvidia-smi` query provides **advisory inventory only** and does not certify driver integrity, CUDA availability or model compatibility. GPU UUIDs are not returned to browser clients. For private remote GPU inference, use an SSH tunnel or similarly authenticated private path; do not publish Ollama's unauthenticated HTTP API through Cloudflare without independent authentication and appropriate controls. The Linux user running FOXWORX does **not** automatically inherit an Ollama system service's access/privileges.

Installing a separate FOXWORX instance on the Z790 does not federate evidence or identities from a Pi. Each host needs its own Cloudflare Access application, secrets, backup, authorization review and operational controls.

## DreadFox (v2.3) game-state boundary

DreadFox is a deterministic, optional game feature—not a model, autonomous agent, scanner, or authorization layer. Hatching is the user's opt-in to pet activity tracking. It receives only a hardcoded allowlist of existing audit **action names** through a bounded background queue and ignores full audit details. Its SQLite rows contain coarse event types, generic notes, timestamps, counters, level/XP, and a user-chosen pet name. The deterministic activity observer never calls AI or copies model messages. The separate opt-in pet conversation endpoint sends user-entered pet chat messages, a fixed allowlist of pet metrics, and (only if separately enabled) seven-day Workbench Pulse categorical frequency bands to the selected model, with no tool/function access. Incoming messages and generated replies persist as bounded plaintext SQLite conversation history and must not be used for sensitive assessment data. Users may pause, reset or erase their pet data. It doesn't share pet state between separate Kali nodes. Like all stored app data, its SQLite file is readable by someone who can access the same operating-system service account. See [DREADFOX.md](DREADFOX.md).

## Companion AI privacy boundary (v2.4)

The optional `pet_chat.DreadFoxConversation` is deliberately separate from the Kali execution manager and main copilot. It only holds references to the pet store, a provider selector and the common inference gateway; it does not receive the registry, engagement manager, terminal manager, execution manager, tool schemas or evidence paths. Model requests include a fixed safe pet-state allowlist, the user's typed message and bounded same-provider/model/endpoint pet chat. Any nonempty tool-call response is rejected. No automatic pet observer event makes a model request. Selecting a model endpoint still uses the administrator-approved provider route rules.

This is a data-minimization boundary, **not guaranteed resistance to prompt injection or a separate OS security domain**. Operators control the content they type into chat; it may contain secrets if they paste them. Full terminal access under the same Unix account still allows reading local pet chat and model key material. Pet conversations are plaintext in the SQLite database. Use the clear and erase controls, secure the state directory, and do not publish this workbench to untrusted operators.

## Workbench Pulse least-privilege context (v2.5)

Workbench Pulse is **disabled for all existing and newly hatched pets** until the operator consents separately in the Sanctuary. It consumes only hardcoded, constant action names delivered through the existing nonblocking observer, not arbitrary audit strings or the `details` column. It stores only a calendar-day bucket, one of seven enumerated activity classes, and a saturating per-day count; the conversation context holds only a seven-day approximate band. No job record, command text, target, file path, scan output, evidence body or secret is queried. It includes an abstract category for success/unsuccessful managed jobs, **not the reason or result**. The displayed preview shows the same sanitized data the model sees.

Disabling Workbench Pulse deletes the entire owner-scoped set of rows, without affecting the operational audit or pet XP. Disabling ordinary pet tracking stops new Pulse observations and hides existing in-window counts. Deleting the pet clears both. AI history is segregated by a fresh privacy epoch on consent changes, so previously contextualized conversations are not silently forwarded after revocation; prior conversation text remains locally visible until explicitly cleared. Requests already delivered to a model cannot be recalled. The externally hosted model may retain information under its own policies. No periodic AI calls are made.

Pulse records are owner-bound **within the application's SQLite database**, not isolated at the OS level from other trusted users of the same Unix account. The server is still a trusted-operator development release. The full terminal is not restricted by these application-layer boundaries.

## Rabbit Hole preauthorization boundary (v2.6)

Rabbit Hole uses an explicit finite operator run grant. Workflow mode permits selected guided recipes and autonomous typed adapters. Installed CLI mode additionally permits model-constructed literal arguments for discovered noninteractive executables when a trusted schema-3 policy enables it. These commands use the existing managed-job runner and the service account’s file/network authority. Delegated proposals and jobs record the run ID; run state, instruction revision, policy, scope and executable fingerprint are rechecked at approval and actual launch. Operator follow-ups steer the task without changing targets or budgets; tool output and documentation cannot become operator follow-ups.

Schema-1/2 policy ceilings remain 16 decisions and 30 minutes. Schema-3 permits administrator-configured ceilings up to 10,000 decisions and 1,440 minutes, with finite operator-selected limits below those ceilings. Installed CLI mode defaults to 64 decisions and 60 minutes; workflow mode defaults to 8 and 15. This is not destination-level containment: arbitrary arguments, plugins and child processes may reach outside the stated target. The app provides no OS sandbox or universal traffic limiter. Review the provider confidentiality impact and actual output rather than treating model-reported completion as independent verification.

A successful subprocess exit does not prove that a pentesting goal was solved. `solved` means **model-reported solution with at least one successfully exited guided job**; verify output manually. Run state and individual job evidence are stored locally and may be viewed by anyone with access to the service account's files. No automatic resume after restart; active runs are marked interrupted. Cloudflare Tunnel and the app's authentication do not enforce outbound test traffic.

## v2.7 root-owned adapter policy boundary

Rabbit Hole autonomous tool permissions are now read from a trusted filesystem policy, not from application-writable records or AI prompts. Absent, invalid, or untrusted policies deny autonomous execution. The worker checks policy revisions at every iteration and during active jobs. This is application-level permission, **not** destination-based egress enforcement; see [ADAPTER-POLICY.md](ADAPTER-POLICY.md).

## v2.8 registered tool templates

Schema-2 root policy authorizes typed noninteractive command templates; review-only templates still require approval when used as adapters. Schema-3 can explicitly enable broader installed CLI autonomy. In that mode an agent can invoke the underlying executable directly, including one with a review-only adapter, under the separate installed-tool grant. Existing policies do not acquire this authority. The app cannot guarantee tool semantics, child processes, destinations or result accuracy. See [Rabbit Hole](RABBIT-HOLE.md).


## v2.9 Tool Intelligence isolation

The new cached documentation and optional internet search are **read-only reference functions**, not execution permissions. They do not create, edit, or enable a registered adapter, nor approve a command. Online research is disabled by default and only accepts an installed executable name, not an arbitrary URL or private host. Direct fetch is fixed to the official Kali documentation origin; search results are filtered to a small host allowlist. User notes are visible only to the same authenticated application actor (although trusted users with shared Unix shell authority are not OS-isolated). See [TOOL-INTELLIGENCE.md](TOOL-INTELLIGENCE.md).

## Discord operational intelligence boundary (v3.3)

Discord is an external untrusted channel. A node administrator configures a single bot/channel and optionally a guild. An engagement-specific team key separates context across jobs. Reading Discord must never approve CLI execution, extend authorized scope or trigger model work by itself. Outbound posting requires operator review, deliberately avoids raw evidence and suppresses mentions. Sanitization is best-effort, so operators must ensure customer/program sharing permissions. See [DISCORD-TEAM.md](DISCORD-TEAM.md).

## v3.3.3 optional dual-origin browser access

In v3.3.3 the default `FOXWORX_AUTH_MODE=open` is intentionally **unauthenticated**, at the operator's request. The service binds exclusively to `127.0.0.1:8765` but any operator-configured tunnel may forward to it. It accepts any tunnel hostname without public-origin registration or Cloudflare JWT verification. Whoever reaches the page can use the Kali terminal and inspect account-visible data. Browser Origin/CSRF checks and WebSocket tickets mitigate some cross-site misuse but **do not authenticate users or protect an Internet-exposed endpoint**. Operators can choose Cloudflare Access/MFA independently, but no such service is required or enforced by FOXWORX. All users share the `local-operator` data namespace; legacy identity-scoped records are not automatically merged. Earlier local/proxy/cloudflare authenticated modes remain available only by deliberate manual configuration.
