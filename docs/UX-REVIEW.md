# Usability review · v2.0.0

This review is based on source inspection, automated backend tests and **offline Chromium UI fixtures**, including visual review at 1600×1000 and 390×844. It is not a study with your teammates, an accessibility certification, or live browser-to-Pi validation. Screenshots in verification are clearly marked fixtures.

## Addressed in this release

| Friction / risk | Change | Verification or remaining caveat |
|---|---|---|
| A disconnected browser destroys work | In-service persistent PTY and explicit reconnect, bounded output replay; no replayed input. | Real PTY/WebSocket backend tests; service restart still ends terminals. |
| A generic tool button suggests everything works | Installed/missing, interactive/GUI/unknown states, package/path/prerequisite notes. | Catalog/source review and offline GUI-tool UI test. Presence is not runtime readiness. |
| Rusty operators must remember flags | Four guided recipes before advanced arguments; Tutor mode and explanatory tool notes. | Scope/recipe tests. Not hundreds of generated forms with unverifiable semantics. |
| A chatbot suggestion unexpectedly runs | Immutable preview and disabled Approve until authorization checkbox; model has no approve/terminal function. | Real proposal tests and offline approval-flow test. |
| Tutor mode depends on model cooperation | Server refuses unexpected model function calls in Tutor mode. | Failing regression reproduced, then passing test after correction. |
| Double clicks/network retries duplicate execution | One-use approval and explicit conflict/expiry errors; mutations are not automatically retried. | Replay, expiry and digest tests. Refresh Jobs before retrying an uncertain request. |
| Scope notes change after preview | Relevant scope/notes fingerprint checked again at approval. | Regression verifies edited authorization notes invalidate proposal. |
| “Finished” incorrectly implies success | Separate exit-based success/failure, timeout, stop, output limit and interruption states. | Real subprocess tests. Submission is not success. |
| Output is unreadable or floods the browser | Bounded log capture, text rendering, follow toggle/copy, UTF-8-safe paging, export of complete captured logs. | Output cap and UTF-8-boundary tests; arbitrary binary output still belongs in an artifact. |
| Another campaign's recent activity hides older results | History is filtered by engagement before recent-item limits. | Regression with more than 200 newer jobs in another engagement. |
| Sensitive evidence is automatically sent to AI | Job selection and output sharing are separate; sharing off by default; selection→draft remains unsent. | Mock-provider payload checks and offline UI test. Redaction is not complete DLP. |
| Missing credentials make the entire app seem broken | AI status/disabled button and clear configuration instructions; terminal/toolbox work separately. | Unconfigured API test and UI state review. |
| First install leaves users guessing about secrets/services | Generated setup token, configuration wizard, doctor, distinct v2 service, preservation of v1 and config. | CLI and script checks; target systemd installation still needs Pi validation. |
| Warnings use tiny or ambiguous visual states | Persistent scope warning, descriptive failure messages, textual job states, dark/light themes and font controls. | Visual review; some secondary metadata is intentionally small. |
| Small screen loses the toolbox | Mobile drawer, stacked chat and workspace, responsive dialogs, no page horizontal overflow at tested widths. | Offline Chromium smoke. A physical phone/keyboard test is still needed. |
| Clipboard or multiline paste behaves unexpectedly | Clipboard fallback message; dedicated copy button/shortcut; multiline-paste confirmation. | Source review; live OS clipboard behavior unverified. |

## Remaining user-comfort gaps

**Team isolation and roles.** Web identities are not isolated Linux tenants. There is no granular trainee/admin role model. A returning operator should not be given a supposedly restricted shell on an account holding secrets they must not see.

**GUI tools.** Burp, Wireshark's GUI and other desktop applications require a separate desktop solution. The app does not present a blank “launch” screen and call that integration. Interactive CLI modes may still be usable in Terminal when properly installed.

**Not a generic options parser.** Parsing every tool's `--help` cannot reliably produce a safe GUI or scope policy. Four hand-built recipes are available; advanced commands require operator review. Tools with subcommand prompts should use Terminal.

**Separate shell state.** Terminal, AI and toolbox share files but not shell variables, CWD changes, functions or activated environments. Explain this during onboarding; it is displayed under the terminal. Native terminal AI agents have independent approval behavior.

**History and retention.** Recent views are bounded; there is no advanced history search, automatic archival, full disk quota, durable terminal transcript, signed audit or collaborative report editor. Export limits are explicit. Operators must manage retention and workspace growth.

**Remote resilience.** No service-restart terminal restoration, external job watchdog, guaranteed immediate Access revocation or universal “stop all host processes.” The UI labels these boundaries. Cellular/offline recovery, long-duration Cloudflare sessions and Pi reboot behavior remain target-side tests.

**Accessibility.** Controls are labeled, dialogs use native semantics, focus styles and keyboard tab switching are present. Full screen-reader behavior, WCAG audit, high zoom, touch targets and color perception need human verification. Light mode retains a dark terminal for ANSI output contrast.

## Team acceptance exercise

Give a teammate the install guide without additional coaching. Ask them to log in, identify scope, find an installed and missing tool, explain an unfamiliar flag in Tutor mode, prepare and approve one benign local job, interpret a nonzero exit, disconnect/reconnect a terminal, export reviewed evidence and find the GUI limitation. Observe where they hesitate. Record elapsed tasks and mistaken expectations; do not treat this document as that user study.

## v2.1 model-switching usability review

- **Provider names and credentials**: The selector shows cloud/local types and curated examples, but accepts exact model IDs because entitlements and model offerings change. Credentials are saved in a separate action, and the input is cleared on save, dialog close, or reopen. Secrets are never echoed by the settings endpoint. A credential save preserves the in-progress model selection rather than resetting the form.
- **Model discovery and capability claims**: A local **Discover models** button lists installed server models when supported. Cloud identifiers are entered manually, and the interface explicitly warns that text connection success does not prove tool calling. Missing LiteLLM installation is differentiated from missing provider configuration.
- **Provider changes and privacy**: The selected provider/model is always visible in the chat pane; only same-provider-and-model conversation records are sent as history. Past UI messages are still visible in the engagement; switching to cloud changes where the next prompt is sent, so the operator must review scope/notes and output-sharing choice.
- **Clear feedback**: Test connection explicitly says it may be billable and only tests the *saved* selection. Incomplete settings or rejected API requests surface errors inside the dialog; credentials remain separate from the model choice.
- **Mobile**: Offline Chromium at 390px exercises the dialog in addition to the main workbench. Actual device, keyboard, screen reader and 200% zoom tests remain necessary.

**Remaining friction**: There is no integrated credential billing portal, context-window/cost estimator, first-party dynamic cloud model catalog, automatic model/tool-calling certification, or per-user OS sandbox. Operator-level UI isolation does not prevent same-UID shell users from reading stored key material or private configuration.

## v2.5 Workbench Pulse privacy/usability assessment

- **Consent:** separate from hatching and AI conversations, off by default, with a detailed confirmation notice before collecting new events. No retroactive reading of workbench audits.
- **Visibility:** the Sanctuary displays only the same named activity categories and approximate seven-day bands the companion can reference. A paused activity tracker visibly suppresses Pulse exposure.
- **Control:** a clear erase-and-disable action; disabling via checkbox also erases the Pulse database rows immediately. AI conversation history must be cleared separately if the operator wants to remove previous discussion of the Pulse.
- **Model selection:** the operator is told that opting into model-powered companion dialogue may send the coarse Pulse to a cloud provider. Route-specific AI conversational context resets whenever the Pulse setting changes.
- **Desktop/mobile:** the Pulse controls were checked with Chromium fixture data at 1600px and 390px widths. A real target-host or phone accessibility study remains outstanding.
