# Unified AI selection

The operator independently chooses Tutor, Copilot, or Rabbit Hole and a provider/model. Codex belongs in the provider list and retains Codex-managed ChatGPT device sign-in. Changing mode preserves the saved provider/model. This design was approved in conversation on 2026-10-11 with an explicit request to implement it.

## Behavior

- The mode selector contains Tutor, Copilot, and Rabbit Hole only.
- Provider & model opens the existing settings dialog, with Codex alongside other providers. Codex uses sign-in instead of an API key or inference endpoint. Its model catalog comes from the local app-server; exact model IDs remain editable.
- Every provider uses the normal chat history and optional job context. History forwarded to inference remains partitioned by provider/model. Existing legacy Codex history remains stored and accessible through its existing API; it is not silently forwarded.
- Tutor explains and can request existing read-only references. Copilot can prepare existing human-reviewed proposals. Rabbit Hole uses the existing exact-target grant, adapter policy and finite budgets.

## Implementation

ProviderManager resolves Codex selections to an actor-bound route. ModelGateway dispatches that route to CodexAgent.complete rather than LiteLLM. The app-server uses ephemeral threads, explicit model choice, disabled shell/web/multi-agent features, read-only sandbox, never approvals, and a structured output schema. Structured requests are validated and returned to the existing mode handlers; Codex does not run those tools itself. Each completion gets only the history/context supplied by FOXWORX. Timeout, cancellation, disconnect and malformed responses must fail without leaving a running Codex turn.

Authentication/status endpoints remain first-party managed; no OAuth token is returned to the browser. Missing CLI/sign-in prevents readiness with actionable status. Codex readiness does not depend on LiteLLM. Other providers retain existing credential and endpoint requirements. Built-in/local authenticated Codex access is not represented as verified OS isolation.

## Validation

Use fake app-server responses for deterministic provider, Tutor, Copilot, Rabbit Hole, history-isolation, malformed-output and cancellation tests. Exercise the actual frontend in offline Chromium at desktop/mobile widths. Run the existing Python suite and JavaScript syntax check. Do not start paid inference or log in to a real account during verification.
