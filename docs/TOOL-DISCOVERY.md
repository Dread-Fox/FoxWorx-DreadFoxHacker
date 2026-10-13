# Ranked local tool discovery

FOXWORX gives Tutor, Copilot and Rabbit Hole a small list of relevant installed tools before each request or decision. The agent can then search more specifically, filter results, read documentation, or request another page. The full inventory is not placed in every model prompt.

## Inventory and ranking

There is no fixed ceiling on the number of discovered executables. The registry scans configured executable directories; usable size depends on host memory and storage. Synthetic checks cover 4,000, 20,000 and 50,000 entries, not a maximum supported count.

Search uses installed executable names, catalog descriptions, categories, package metadata and available local manual summaries. Exact names receive priority, followed by weighted keyword matches. Results include match terms and metadata sources. This is local retrieval, with no additional model request, embedding service or online lookup.

Public summaries are cached in `tool-discovery.sqlite3` in the private state directory. Executable identity and package database changes invalidate cached summaries. Enrichment uses fixed system metadata utilities and local package records; it never executes discovered binaries to probe `--help` or `--version`. It does not index private operator notes or assessment evidence. Missing descriptions leave a tool searchable by name; a listed tool is not proof its drivers, permissions or dependencies are ready.

## Bounded model context

Automatic discovery supplies at most 10 candidates, installed-tool count, category counts and freshness information. Tutor and Copilot search using the current message. Rabbit Hole searches using its objective and recent operator follow-ups. Every provider receives these results through ordinary message context. Models with compatible function calling can also refine the search; discovery does not add function-calling support to incompatible models.

`lookup_tools` accepts:

| Input | Meaning |
|---|---|
| `query` | Required task description or executable name; empty string browses installed tools. Maximum 4,000 characters. |
| `category` | Optional exact category; empty means all categories. |
| `mode` | Optional `cli`, `interactive`, `gui` or `unknown`; empty means all. |
| `limit` | Page size, default 20, range 1–40. |
| `cursor` | Previous result's `next_cursor`, or empty to start. |

The response contains `results`, `total_matches`, `returned`, `next_cursor`, `inventory_revision`, `installed_count`, category counts, scan timestamp and refresh status. Result text is bounded; the serialized response stays below 32 KiB. `total_matches` describes the search, not just the returned page. If a refresh or query change invalidates a cursor, `restart_required` is true and the agent must restart without that cursor.

The existing `/api/tools` toolbox response is unchanged. `lookup_tools` is an AI function, not a new publicly exposed search endpoint.

## Freshness

Startup creates the basic search index and starts local metadata enrichment in the background. When discovery uses an inventory older than 60 seconds, it schedules a refresh, with at most one automatic attempt per minute. The current successful snapshot remains available while refreshing. Manual toolbox Refresh is still available. Scans are serialized and search results identify stale or refreshing inventory; a failed refresh does not delete the last usable snapshot.

New installations or removals can therefore take a refresh cycle to appear. Execution rechecks the actual executable independently of the index.

## Modes and authority

- **Tutor:** receives the shortlist and read-only lookup/documentation functions; cannot execute jobs.
- **Copilot:** receives discovery and can propose commands for explicit operator approval.
- **Rabbit Hole workflows:** can discover alternatives, but executes only the selected authorized workflows.
- **Rabbit Hole installed CLI tools:** can automatically execute relevant installed noninteractive tools under an explicit task/run grant and administrator policy.
- **DreadFox companion:** receives no assessment-tool discovery or execution functions.

See [Rabbit Hole](RABBIT-HOLE.md) for autonomous execution, limits and follow-ups. Discovery and documentation never expand a run grant or change its target.

## Reproduce the benchmark

After installing development dependencies:

```bash
.venv/bin/python tests/benchmark_tool_discovery.py
```

This benchmark reports index construction, warm query latency, response sizes and host information for synthetic inventories. It does not time filesystem discovery, local metadata enrichment, model inference or real assessment tools. Target-side ARM64 performance requires separate measurement.
