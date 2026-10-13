# DreadFox Sanctuary — optional digital companion

DreadFox has two clearly separated functions: a **deterministic local digital pet** and an **optional user-initiated conversation interface**. The activity observer only sees generic event names and never talks to a model. An operator can choose to talk to DreadFox through their selected cloud/local model, but only after explicitly enabling AI conversations. It cannot run commands, manage tools, read targets or tool output, or affect approvals. The observer is an asynchronous task within the same workbench process, not an OS daemon.

## Getting started

1. Sign into your FOXWORX workbench on Kali ARM64 or x86-64.
2. Choose **✦ DreadFox** in the workspace tabs or the small fox in the header.
3. Read the privacy note and click **Hatch DreadFox** to opt in. Nothing is recorded before hatching.
4. Visit the sanctuary to check mood, XP, tails, a private journal, the activity affinities, and keepsakes.
5. **Play**, **Snack** or **Rest** for a small change in energy, bond or curiosity. These have cooldowns and do not earn XP.
6. Expand **Companion settings & privacy** to rename the fox, pause/resume tracking, start over, or erase all pet data.

The local pet game and offline conversations require **no API key, network access, GPU or model server**. AI conversation is separately opt-in and uses whatever provider/model you selected in **Model & keys**. Cloud models may charge for each DreadFox chat request.

## What counts as activity

The observer listens to a strict allowlist of existing *audit action names* only, **after the actual workbench event has been committed**. It does not copy the corresponding audit `details` field. Its recognized categories are:

| Category | Coarse activity (examples) | XP per credited event |
|---|---|---|
| Exploration | Terminal created; engagement created | 3; 8 |
| Craft | Completed managed job; workspace file uploaded | 12; 5 |
| Wisdom | AI-assisted learning request | 5 |
| Careful practice | Explicitly approved job; scope updated; evidence exported | 3; 3; 10 |

XP is limited to **120 points per UTC day**, and individual event kinds have cooldowns of **1–5 minutes**. Every accepted event is credited at most once by the observer. High-frequency job spam is not an efficient way to level; the pet isn't a scoring system for scan volume or vulnerability severity. Neither failures nor target counts give rewards.

**Full terminal commands are not counted individually.** Opening a terminal is a recognized coarse event; the pet never captures individual commands, keystrokes or PTY data. This protects engagement and personal data by design.

## How growth works

- **Experience (XP)** is permanent until you reset/erase the pet. Level is based on lifetime XP.
- **Tails and stage** require *both* enough XP and a minimum number of real calendar days since hatching. This prevents speed-running nine tails immediately.
- **Energy** replenishes while offline; prolonged absence does not kill, starve, or reset your fox. It simply becomes **Dreaming** until you return. Mood also reflects bond, curiosity and rest.
- **Activity affinities** track counts across Exploration, Craft, Wisdom and Careful Practice, without storing destinations or outputs.
- **Keepsakes** are earned through milestone counters, such as first XP, learning sessions or days active.
- The journal keeps a bounded set of the **80 most recent** generic notes in SQLite; the UI shows the latest 30. Lifetime XP, counters, stage and name are retained unless you erase them.

| Tail | Stage | Earliest age | Lifetime XP |
|---|---|---:|---:|
| 1 | Fox Kit | Immediately | 0 |
| 2 | Curious Scout | 1 day | 50 |
| 3 | Clever Trickster | 3 days | 120 |
| 4 | Forest Guardian | 7 days | 250 |
| 5 | Arcane Sage | 14 days | 450 |
| 6 | Moonlit Mystic | 30 days | 800 |
| 7 | Silver Elder | 90 days | 1,400 |
| 8 | Starbound Spirit | 180 days | 2,200 |
| 9 | Nine-Tailed Guardian | 365 days | 3,500 |

These are *minimums*, not guaranteed dates. A fox with insufficient XP will remain at its current stage. The sanctuary does not award retroactive XP during outages.

## Privacy, isolation and reliability

- Each authenticated FOXWORX operator receives a logically independent pet in the existing per-node SQLite file, `workbench-v2.sqlite3`. The existing database is preserved across upgrading from v2.2.
- The activity observer saves only predefined action types, generic narration, UTC times, aggregate counters, XP and the operator's chosen pet name to the milestone journal. **No command text, arguments, engagement domains, vulnerabilities, IP addresses, targets, evidence filenames, regular copilot chats or secrets are copied automatically.** Explicit DreadFox chat prompts and model responses are stored in a **separate** table and can be cleared independently. The existing operational audit remains separate.
- Opt-in is required; **Pause tracking** prevents new credits. **Erase companion data** deletes that operator's profile and journal. **Start over** deletes and hatches a new pet (new progress clock).
- Background action notifications enter a bounded in-memory queue (max 1,024). Under overload an optional notification is **dropped** rather than delaying or blocking terminal, jobs or AI requests. If optional pet storage cannot initialize, FOXWORX continues running and the companion returns a visible error rather than blocking other services. During shutdown the app attempts a bounded drain; a crash can lose queued pet credits without harming workbench records. `GET /api/pet` is a fast local snapshot, and care actions are protected by existing CSRF and login safeguards.
- The pet observer is not a tool sandbox or a security control. FOXWORX terminal operators still share a Linux service account; anyone with access to that account can read the SQLite file even if browser profiles are separated. Use a dedicated non-root account and trusted operators only.
- Pet records do not sync between independent Pi and Z790 nodes. A single person's fox on two nodes is **two different pets**, not a shared character. True multi-node continuity would need a future opt-in synchronization design.

## Backups and upgrades

Stop the service after finishing jobs and terminal work:

```bash
systemctl --user stop foxworx-workbench
```

Back up `~/.local/share/foxworx-workbench-v2/` (including the SQLite WAL if present) together with private configuration `~/.config/foxworx-workbench/`. Installing v2.5 creates new pet and separate chat tables without overwriting existing engagement, chat or tool data. The app still uses the same `foxworx-workbench.service` user service. Upgrading the source folder does not automatically migrate or copy data to another machine.

See [INSTALL.md](INSTALL.md) and [SECURITY.md](SECURITY.md) for general deployment and Cloudflare prerequisites.

## Whispers with your fox — v2.4

1. Hatch DreadFox, then scroll down to **Whispers with your fox**. The default is **Offline · no AI calls**. Ask how it feels, how many tails it has, or what it remembers. Its replies use predefined safe pet data; offline dialogue is deliberately limited compared with a language model.
2. Choose a favorite memory theme: **Evolve from activity**, Exploration, Craft, Wisdom, or Stewardship. This setting influences the companion persona only; it grants no XP and cannot modify tool behavior. Auto mode follows the highest earned activity category.
3. If desired, configure a model in the main workbench **Model & keys** interface. Turn on **Use my selected AI model** in the sanctuary and confirm the privacy/cost notice. From that point, **only user-submitted DreadFox messages** invoke model inference; the activity observer never invokes models.
4. Chat replies are saved in a dedicated `pet_conversations` SQLite table, not the regular copilot history or milestone journal. You can clear conversations at any time without losing your pet; starting over or erasing the pet removes those messages.

### Memory and privacy boundaries

Without optional Workbench Pulse, the AI sees only these pet fields: chosen name, stage, tail count, age in days, level, XP, mood, energy, bond, curiosity, four aggregate activity affinity counts, derived personality, earned keepsake titles, and up to five built-in generic milestone notes. **No audit details, engagement notes, targets, command text, individual job records, tool output, files, credentials, or main AI chat history** enter the companion's model context automatically. With separate Workbench Pulse consent, coarse seven-day activity bands can also be included; see below.

For conversational continuity, at most **12 messages** from previous *AI pet dialogue* are sent, and only when the same operator selects the same provider, model ID, approved inference endpoint and provider credential. Offline pet dialogue is not forwarded to a model. Switching providers or local servers does not share earlier conversations across routes. Current messages are sent because the user explicitly submitted them. **Do not paste secrets or confidential evidence into DreadFox chat**; arbitrary submitted content cannot be validated as non-sensitive. Provider requests may be billed and may leave the node.

Conversation records are bounded to **60 messages per operator**, retained indefinitely until rotated out, explicitly cleared or the pet is deleted. Records are plain SQLite text, accessible to anyone who can read the shared service-account database. DreadFox still has no independent OS isolation. Pet name, short theme preference, memory journal and affinity counters are durable across restarts and continue to evolve for years.

The model is never given function definitions, terminal access, a tool registry, approval permissions or commands. If a provider unexpectedly returns function calls, the conversation is rejected and no response is saved. Model answers should be treated as playful generated text, not verified information. Turning AI conversations off does not stop passive activity tracking; that is controlled by a separate checkbox. Turning tracking off does not delete conversations.

### Operational limitations

- No fully autonomous character, scheduled unsolicited messages, cross-node pet synchronization, voice/video, or remote desktop for the fox.
- No semantic embedding/vector database or long-context reconstruction of years of chat; long-term growth is in durable safe pet traits and milestones. Model context is intentionally short and provider-specific.
- Dialogue from a new provider does not automatically import messages from an older model. Model compatibility and response quality vary.
- Offline chat understands a small group of phrases. For free-form conversation enable AI, or add more offline rules in `foxworx/pet_chat.py`.

## Workbench Pulse — v2.5 contextual conversation

DreadFox can now notice **some** of the work you are doing without accessing its contents. **Workbench Pulse is a separate permission from hatching and from enabling AI conversations.** Existing pets are opted out. Enable it in the Whispers section to begin collecting new broad events; it never scans earlier audits, jobs or chat logs. You can inspect exactly what the fox sees in a seven-day frequency preview.

| Pulse category | Fixed event types it groups | Never supplied |
|---|---|---|
| Terminal sessions | New PTY sessions | Input, shell output, command strings |
| Reviewed operations | Managed-job approvals | Approved command, proposal details, target |
| Completed jobs | Managed jobs that succeeded | Actual executable, exit code, results |
| Unfinished jobs | Managed jobs that failed, stopped, timed out, exceeded output limit or were interrupted | Error text, target, severity |
| Learning sessions | Main copilot requests | Question, provider, model, generated response |
| Workspace planning | Engagement/workspace created or updated | Workspace names, notes, scope, URLs |
| Evidence organization | Workspace uploads and evidence exports | Paths, names, file contents, exported ZIP |

Each stored database row has only: `owner`, current pet-generation identifier, **UTC calendar day**, **fixed category**, and **count capped at 20**. The user-facing and model-facing values are **Some**, **A few**, **Several**, or **Frequent** over the latest seven UTC days. No precise times, entity names, filenames, command arguments, outputs, URLs, IP addresses, findings or secrets are ingested. The source is a hardcoded event-name map. The companion never queries the audit `details` column.

### Privacy and retention

- Off by default; never backfills historical actions. Turning off erases the companion's entire saved seven-day pulse at once. Deleting or resetting the pet also erases it.
- Turning off regular pet activity tracking suppresses the pulse without deleting its still-in-window summary. Readback is disabled while tracking is paused.
- Each read or activity update prunes out-of-window rows. Long periods of inactivity do not trigger AI requests. Existing XP/milestones remain independent.
- **Offline chat** can summarize the pulse without contacting an AI model. **AI chat** includes the pulse only when both Pulse and AI conversations were deliberately enabled, and the user sends a DreadFox message. This may send coarse behavioral metadata to a cloud provider; hosted model privacy terms still apply.
- Switching Pulse on/off rotates the contextual AI-history partition, preventing prior contextual conversations from being automatically forwarded on subsequent requests. **Old pet chat messages remain visible in local history** and may contain earlier AI references to your activity; use *Clear conversation* to erase them. Previously sent provider requests cannot be recalled.
- Pet profiles, pulse rows, and chat records share the existing protected service-account SQLite database; the app does not isolate untrusted UNIX users. Cloudflare Access by itself does not provide host-level separation.
- Workbench Pulse does **not** inspect processes, instrument terminal commands, grade vulnerabilities or evaluate user competence. It is a playful abstract activity summary only.

Endpoints: `GET /api/pet/context`, `PUT /api/pet/context` with `{ "enabled": true/false }`, and `DELETE /api/pet/context`. Mutations require the normal authenticated CSRF context. The ordinary FOXWORX audit subsystem is not modified.
