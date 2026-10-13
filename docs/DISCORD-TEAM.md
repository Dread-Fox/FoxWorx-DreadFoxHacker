# FOXWORX v3.3 — Discord Team Intelligence

**Summary:** Operators working independently on Kali nodes can exchange short, reviewed findings through one named Discord text channel. FOXWORX polls a bot-authorized channel, stores tagged messages locally, displays them in **Team / Discord**, and offers engagement-matched snippets to Copilot, Rabbit Hole, and Codex as **untrusted reference data**, not instructions. FOXWORX never executes Discord commands or imports remote scopes/approvals.

## 1. Make a dedicated team channel

Create a Discord server (or choose an existing trusted server) and a restricted text channel such as `#foxworx-findings`. Control access with Discord roles; **everyone who can read that channel can see its findings**, even if the company-only FOXWORX license forbids them from running the application.

In the [Discord Developer Portal](https://discord.com/developers/applications):

1. Create an **application → Bot**. Copy the *bot token* directly into the private FOXWORX host configuration **without adding it to GitHub, a screenshot, or a chat message**. Treat the token as a password. Bot tokens are not webhooks or personal user tokens.
2. Under the Bot settings, enable **Message Content Intent** if you want FOXWORX to read ordinary teammate messages. Discord restricts message content (including HTTP API responses) without this access. Larger apps may need approval. FOXWORX's outbound messages and posts mentioning the bot can still have content without it, but normal channel collaboration will be incomplete.
3. Use the OAuth2 installation link with only the **bot** scope, and grant minimal channel permissions: **View Channel**, **Read Message History**, **Send Messages**. Do not grant Administrator, Manage Roles, Manage Webhooks, or broad server rights. Remove the bot from channels it should not see.
4. In Discord, enable **Developer Mode**, then right-click the text channel and select **Copy Channel ID**. Optionally copy the server/guild ID.

The integration uses official **Discord HTTPS Bot API v10**; it does **not** need Gateway sockets, user tokens, webhook secrets, or a publicly reachable callback URL. Cloudflare Tunnel is used for inbound FOXWORX UI access only; Discord polling uses the Kali host's own outgoing HTTPS connection.

## 2. Configure each Kali node

Each installation needs bot authorization for the intended Discord channel. You can use one bot token on multiple authorized nodes for REST-only access, although **separate application/bot credentials per node** make revocation and attribution easier. If you use distinct bots, invite each to the same channel.

Edit `~/.config/foxworx-workbench/settings.env` with permissions `0600`, outside the source tree. On each node, set:

```ini
FOXWORX_DISCORD_BOT_TOKEN=YOUR_PRIVATE_DISCORD_BOT_TOKEN
FOXWORX_DISCORD_CHANNEL_ID=123456789012345678
FOXWORX_DISCORD_GUILD_ID=123456789012345678
FOXWORX_DISCORD_POLL_SECONDS=30
FOXWORX_DISCORD_NODE_LABEL=Kali-Pi-1
```

The Guild ID and Node Label are optional; the label identifies which workstation posted a reviewed finding without exposing its real hostname. Channel and token must be supplied together; a malformed snowflake is rejected on startup. Poll interval must be 15–300 seconds. The service runs under a dedicated non-root user, and the bot token is not served to the browser or inherited by the terminal/job child environment.

Apply the configuration:

```bash
chmod 600 ~/.config/foxworx-workbench/settings.env
systemctl --user restart foxworx-workbench
bash scripts/doctor.sh
```

**Never** put a Discord bot token into a shell command captured by a managed job, an evidence export, an agent prompt, a repository, or the Team message composer.

## 3. Match an engagement across teammates

1. On each FOXWORX instance, open **Scope & notes** for the relevant engagement.
2. Enter the same **Shared Discord team key**, e.g. `lab-training-2026`. Allowed characters: 3–48 lowercase letters, digits, `-`, `_`. Use different keys for different programs/clients.
3. Match authorized target scope **independently on each node**. The team key is a routing label, **not an authorization grant**.
4. Open the **Team / Discord** tab to read tagged posts or create a draft.

An operator can post a plain Discord message for agents and other workbenches to read by putting this standalone line into its text:

```
[fx:lab-training-2026]
Observed a TCP service on our authorized training machine. Evidence needs manual validation.
```

FOXWORX's own published messages are readable Markdown with a team key and a `FOXWORX-FINDING` version marker automatically. Untagged Discord messages are not loaded into an engagement's AI context; other team keys are filtered out. Discord authors can forge tags: the bridge considers **all messages untrusted**, regardless of their formatting.

## 4. Share findings, including agent findings

- To share manually, use **Team / Discord → Share a finding** and enter a **title** and **short evidence-backed summary** (max. 1,400 characters).
- Copilot can call `draft_discord_finding` to prepare a draft from its investigation. It can never approve the draft or call Discord's send endpoint itself.
- A finished Rabbit Hole run can be selected in **Team / Discord** to create an agent-authored draft using the run's saved summary. Its full command output is **not** sent.
- Click **Approve & publish** to authorize the exact draft. Discord will confirm the posted message ID; the audit trail saves draft creation and publication state. Reject drafts that include sensitive data or speculative claims.
- On ambiguous HTTP errors, a draft becomes `delivery-unknown` instead of retrying automatically; check the channel before deciding how to proceed.

No attachments, whole tool logs, secrets, environment variables, engagement scope files, Codex credential files, or binary evidence files are sent automatically. Deliberately publishing a target address in a finding exposes it to the whole channel; review your disclosure policy first. Sanitization is best-effort and does **not** replace human review.

## 5. What agents do with team findings

- **Copilot / Tutor:** engagement-matched recent findings can be included as clearly labeled untrusted context when a team key is set. Copilot has a read-only `read_discord_team_intelligence` tool; Copilot may prepare a posting draft, but only an operator can publish it.
- **Rabbit Hole:** receives a small read-only set of engagement-matched team notes on each bounded model iteration. Existing scope restrictions, adapter policies, target authorization, budgets, and execution approval rules are unchanged.
- **Codex Agent:** its next explicit operator prompt may include a small engagement-matched context excerpt. This does not give Discord messages control of Codex tools or access to credentials.

**No remote message is an instruction**, even one written by a known teammate or another FOXWORX agent. Remote claims do not extend the engagement's allowlist, revoke safeguards, approve operations, or confirm a vulnerability. All findings should be verified locally before acting on them. Discord is a collaboration layer, **not a remote task queue**.

## 6. Security, limits and troubleshooting

- **Secret security:** token in per-node local config only. Restart the service after rotating a token. Configure Discord-side permissions so a compromised node has access only to the one intended channel. Separate bots for separate teams/clients when possible.
- **Rate limiting:** server respects 429 `retry_after` and uses conservative periodic polling (default 30 seconds). On large channels it ingests at most 100 messages per poll. Bursts exceeding 100 messages between polls may produce gaps; no guarantee of complete history.
- **Content access:** when Message Content Intent is missing, many non-bot, non-mention messages arrive with empty `content` and cannot be used as team intelligence. Enable the intent in the Developer Portal where eligible.
- **Local persistence:** only team-key-tagged messages and drafts live in the FOXWORX state database; ordinary untagged channel chat is not persisted. The bridge retains up to 1,000 recent tagged messages per configured channel. They are visible to authorized local operators with access to the matching engagement and subject to your team's data-retention policies. Deleting messages from Discord does **not** retroactively remove already cached findings. Review local data retention before using client-sensitive channels.
- **Not end-to-end encrypted:** treat Discord as a third-party cloud service. Do not transmit program-confidential vulnerabilities or sensitive customer data if client disclosure rules prohibit it.
- **Connectivity:** no firewall ingress is necessary for Discord. A 401/403/404 or network error shows a generic status, not a token. Check channel ID, permissions, token and outbound HTTPS.
- **Permissions:** no Discord message can run Kali commands, bypass review, change managed jobs, or modify engagement scope through this integration.
- **Multi-node:** each node has its own local message cursor and cached history; all use the same team tag for the same authorized engagement. Initial sync reads only the latest 100; an existing large history is not exhaustively backfilled.
- **Licensing:** the project's FoxWorx LLC proprietary `LICENSE` governs original FOXWORX source; Discord is a separately operated service and retains its own platform terms.

For urgent compromise response, revoke the bot in Discord, rotate the token, remove the values from every node's private configuration, and restart FOXWORX. Preserve audit information as appropriate.
