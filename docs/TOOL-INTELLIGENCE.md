# FOXWORX v2.9 — Kali Tool Intelligence Engine

## Purpose

FOXWORX v2.9 discovers installed executables from the node's configured search directories, keeps local/version-bound CLI reference material in a persistent SQLite cache, and makes it available to **operators, Tutor, Copilot and Rabbit Hole**. This is a **documentation and knowledge feature**, not an increase in execution permissions. The separate root-owned adapter policy is still the authority for Rabbit Hole autonomy.

## Discovery and memory

- The existing Python `Registry` performs real PATH-directory executable discovery on startup, and when the operator selects **Refresh** in the toolbox. Catalog entries not found on the host are still identified as missing.
- Choose **Tool Intelligence** in the workspace or **Tool knowledge** in the manual toolbox's selected-tool dialog. Search by executable name, description or category.
- Clicking a discovered tool reads its locally installed `man` page using the **man renderer**, if available, then falls back to a bounded set of common `/usr/share/doc/<package>/README*` files. The discovered target executable is **never automatically run** to generate documentation. For tools where running `--help` is safe, operators can run it through their normal approved terminal/toolbox workflow; FOXWORX does not presume that `--help` is harmless for unknown executables.
- It extracts likely `--long-flags` as **unverified reference hints**, not permission to use those flags. Source excerpts are retained, so the model can reference real documentation rather than invented syntax.
- The cache is `~/.local/share/foxworx-workbench-v2/tool-intelligence.sqlite3` by default (under the configured `FOXWORX_STATE`). It is mode `0600`; the containing state directory is `0700`. It lives alongside, not inside, the existing engagement and pet SQLite tables.
- Cache identity includes the executable path, resolved path, inode, size, modification timestamp and the discovered package version. **If the binary changes, old cached documentation and operator notes are not returned as current knowledge.** Up to three local binary revisions are retained for bounded housekeeping.
- Manual **Re-read local docs** refreshes the cache. Installing a manual page without changing the executable requires this explicit refresh.
- **Saved knowledge notes** are operator-authored, capped at 600 characters / 30 notes per executable revision and isolated by authenticated app operator. They can include verified installation quirks and flags, but should never include credentials, hostnames, customer details, or findings. Notes are deliberately **not authored automatically by the AI**; a model can explain them, but cannot store its own unverified guesses as trusted knowledge.

## AI and Rabbit Hole

Copilot function calls include `lookup_tools`, `get_tool_documentation`, `research_official_documentation`, and `search_official_tool_sources`. Tutor gets only these read-only tools and cannot prepare command proposals. Read-only outputs are context-limited before sending to the operator's chosen model.

Rabbit Hole can choose `inspect_tool`, `research_tool` or `search_tool_sources`, and can reuse cached documentation on later runs. Documentation calls count toward the operator's preauthorized **step and time budgets**, and changes to the administrator policy or engagement scope still halt the run. Knowledge never creates or extends an adapter, changes the fixed target, or approves a proposal.

No DreadFox pet data, target addresses, tool output, engagement notes, or prior operator chat history is included in standalone external documentation search queries. **Some retrieved reference text will be transmitted to the selected cloud or local model as part of an explicit AI conversation**, subject to that provider's privacy practices.

## Optional online research — disabled by default

The node administrator can edit the non-root service's config file (`~/.config/foxworx-workbench/settings.env`) to add:

```ini
FOXWORX_DOCS_ONLINE=true
# Optional, only to enable external search results beyond direct Kali docs:
FOXWORX_DOCS_SEARCH_KEY=BRAVE_SEARCH_API_TOKEN
```

Restart with `systemctl --user restart foxworx-workbench`. Keep the file `0600`. Never paste the token into the AI chat, tool notes or screenshots. A documented tool can then be looked up explicitly on its **fixed HTTPS Kali documentation URL** (`https://www.kali.org/tools/<installed-executable>/`). FOXWORX does not follow HTTP redirects, honor ambient HTTP proxy settings, accept user-specified URLs, or fetch non-text content. Retrieval has strict size and time bounds.

When the additional Brave Search API token is configured, **Search approved sources** searches for *the installed tool name* and shows up to eight filtered references from `www.kali.org`, `manpages.debian.org`, `www.gnu.org` and `github.com`. Search results are displayed as reference links and descriptions; FOXWORX does **not** download and execute code from them. The search key stays on the server. Direct Kali documentation and source search are cached for seven days per executable revision. This optional search may involve provider charges and availability limits.

You can disable online lookups immediately by setting `FOXWORX_DOCS_ONLINE=false` and restarting the service. Existing cached online references remain displayed as untrusted references; no new network calls are made. To erase the tool cache entirely, stop the service, back up and then remove the **separate** `tool-intelligence.sqlite3` database and its `-wal`/`-shm` files. This has no effect on engagement, jobs, AI credentials, or DreadFox data.

## Security boundary

Documentation, webpages, search snippets, and saved operator notes are **untrusted data**. They may contain misleading instructions or prompt-injection text. The model is instructed not to follow such text as agent instructions, but model behavior is not a security boundary. The execution engine still enforces its independent administrator policy, target input check, command template verification, human-approval requirements and finite budgets.

An executable appearing in the registry does **not** mean it has required dependencies, permissions, adapters, GUI support, or permission to run against any target. Neither metadata nor version checks provide OS-level sandboxing, network egress containment, or guaranteed safe execution.

### Known limitations / acceptance testing

- No general-purpose full-text index for arbitrary PDFs, HTML folders or custom source repositories; local support is `man` + limited package documents, with optional trusted online research.
- No automatic arbitrary `--help` or other probes against unfamiliar installed binaries; this avoids granting unknown executables background execution authority.
- Upstream search snippets are not fact-checked, and model explanations may still be wrong. Operators should verify unfamiliar flags against the original manual.
- Version metadata depends on the package catalog; uncatalogued executables still get a binary identity cache key.
- Run final integration checks on both Kali ARM64 and x86-64. Verify `man` is available, offline cache survives a restart, and the configured model supports read-only tool calls. Live Brave/Kali requests were not required by the offline build tests.

## Troubleshooting

```bash
bash scripts/doctor.sh
systemctl --user status foxworx-workbench
journalctl --user -u foxworx-workbench -n 80 --no-pager
# Exact node inventory is available at the authenticated /api/tools endpoint
```

If online docs are unavailable, keep online mode disabled and use cached local pages. If the model lacks function-calling support, manual Tool Intelligence browsing still works independently of the AI SDK.

## Ranked discovery

Agents also receive automatic shortlists and can refine paginated searches across the full installed inventory. This uses public local metadata, independently of private operator notes. See [Tool discovery](TOOL-DISCOVERY.md).
