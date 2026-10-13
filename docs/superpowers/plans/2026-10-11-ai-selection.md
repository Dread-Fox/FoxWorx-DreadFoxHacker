# Unified AI Selection Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Separate mode from provider/model and make Codex available to every existing AI mode.

**Architecture:** Preserve the existing mode handlers and add a structured native Codex completion transport to ModelGateway. Move Codex sign-in into provider settings and remove its separate chat flow from the browser.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, vanilla JavaScript, Codex app-server, pytest and offline Playwright/Chromium.

**Spec:** `docs/superpowers/specs/2026-10-11-ai-selection-design.md`

## Global Constraints

- Retain first-party ChatGPT device sign-in and actor-specific CODEX_HOME.
- Preserve existing execution approvals, target grants, policy limits and history isolation.
- No real login, paid inference, new runtime dependency or service installation during testing.
- Work in the existing extracted release; no Git repository is available.

## Review Focus

- Missing CLI, expired sign-in and no LiteLLM must have accurate readiness.
- Mode changes must preserve selection; provider changes must preserve unsaved drafts during sign-in.
- Malformed or unknown tool requests must never bypass existing mode authority.
- Timeout/cancellation must interrupt the child before another request is accepted.
- History must never cross actor/provider/model boundaries.

## Task 1: Native provider transport

**Files:** `foxworx/providers.py`, `foxworx/models.py`, `foxworx/codex_agent.py`, `foxworx/model_gateway.py`, `foxworx/app.py`, `tests/test_codex_provider.py`.

**Interfaces:** Add `CodexAgent.complete(owner, model, messages, tools) -> dict` returning normalized content/calls/original, and `CodexAgent.models(owner) -> list[str]`. Add optional `codex` to ProviderManager and ModelGateway constructors; resolved Codex routes carry `owner`.

- [x] Write tests for selectable Codex, key/endpoint rejection, accurate readiness, structured completion and invalid output.
- [x] Run new tests and confirm feature failures.
- [x] Implement provider routing, ephemeral structured completions and model discovery.
- [x] Verify Tutor explanation-only, pending Copilot proposals, bounded Rabbit Hole decisions, isolated history and cancellation.

## Task 2: Independent browser selectors

**Files:** `static/index.html`, `static/app.js`, `static/app.css`, `tests/browser_smoke.py`.

- [x] Update offline browser coverage to select Codex through provider settings and exercise all three modes.
- [x] Confirm the new browser flow fails before changing the UI.
- [x] Move sign-in into provider settings, remove Codex mode/chat branching, retain shared history/context, refresh readiness and model catalog.
- [x] Verify desktop/mobile layout, preserved mode/selection, key/sign-in controls and shared chat clearing.

## Task 3: Documentation and verification

**Files:** `README.md`, `docs/CODEX-AGENT.md`, `docs/AI-PROVIDERS.md`, `verification/AI-SELECTION-REPORT.md`.

- [x] Update usage and deployment limits for the final integration.
- [x] Run full pytest suite, compile/shell/JavaScript checks and offline browser smoke.
- [x] Review the changed files and fix material regressions.
- [x] Report verified behavior and the absence of live-account inference testing.

## Execution record

Implemented in place as authorized. New provider tests failed before implementation; the new browser flow failed before the UI change. Review identified missing turn IDs, repeated-cancellation cleanup and a legacy writable turn route; regression tests reproduced these, and fixes passed. The obsolete legacy inference method was removed while archived history reads remain available. Final verification: 260 tests passed, one environment-dependent test skipped; shell/Python/JavaScript checks and offline Chromium desktop/mobile smoke passed. Native CLI 0.162.1 handshake, model catalog and ephemeral thread configuration were checked with temporary credentials/state and no inference.
