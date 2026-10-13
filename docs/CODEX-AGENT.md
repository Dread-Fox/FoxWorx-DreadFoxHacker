# Codex provider in FOXWORX

**Copyright © 2026 FoxWorx LLC. All rights reserved.** This guide documents an optional integration with the **first-party OpenAI Codex CLI**; it does not relicense FOXWORX as open source or confer authorization to use its proprietary application. The Codex binary remains under its own published license.

## What has been integrated

- The official Codex CLI's `codex app-server --listen stdio://` protocol, not model-name impersonation or direct use of undocumented ChatGPT endpoints.
- First-party app-server `account/login/start` with `type: chatgptDeviceCode`. The browser receives only OpenAI's HTTPS verification URL and the one-time user code. Authentication tokens are managed by Codex itself.
- Authenticated operator status through `account/read`, sign-out through `account/logout`, model discovery through `model/list`, and ephemeral `thread/start` / `turn/start` / `turn/completed` inference. Codex refreshes its managed credentials under the operator-specific `CODEX_HOME`.
- One authenticated Codex identity per FOXWORX actor and one active Codex turn per actor. New conversations use the shared chat records. Native threads are ephemeral and receive only the context FOXWORX supplies. Legacy history remains stored and readable through `/api/codex/history`; the separate `/api/codex/turn` POST returns HTTP 410. Other OpenAI API-key provider configurations are not used or modified.

## Install Codex on Kali ARM64 or x86-64

Install the official Codex CLI from OpenAI in your trusted non-root Kali user environment. Follow the currently supported installation instructions at <https://developers.openai.com/codex/cli/> and check version/platform support for your ARM64 Raspberry Pi or x86-64 workstation. For example, where an official supported Node.js/npm version is installed:

```bash
npm install -g @openai/codex
command -v codex
codex --version
```

Do not use `sudo npm install -g` just to satisfy FOXWORX; configure a non-root user-owned npm prefix instead. FOXWORX checks its configured executable search path and the standard `~/.local/bin/codex` location. If necessary, set the private `FOXWORX_EXTRA_TOOL_PATHS` value to the absolute npm bin directory and restart the user service. For a self-managed ARM64 device, verify the official CLI supports that platform/version before relying on it.

Run the FOXWORX installer normally if upgrading and keep your state, configuration and Codex authentication paths **out of version control**. Never put OAuth credentials, API keys, private GitHub tokens, or `.env` files in the public repository.

## Sign in with your ChatGPT account

1. Open **Provider & model** and select **Codex · ChatGPT** in the provider list. It works without an OpenAI API key or LiteLLM.
2. Choose **Sign in with ChatGPT**. FOXWORX requests a device code through the official Codex app-server.
3. In your personal browser, open the official HTTPS verification page displayed by Codex. Enter the one-time code and follow OpenAI's authorization prompts. FOXWORX **never** requests your ChatGPT password or cookies.
4. Enter `default`, use **Discover models**, or enter an exact supported model ID. Click **Use this model**, close settings, choose Tutor, Copilot, or Rabbit Hole, and use the normal composer. Changing mode preserves the saved provider/model.
5. Review the result in the shared chat or Rabbit Hole progress panel. Use **Stop Rabbit Hole** to stop an entire authorized run. Provider settings also offer **Stop request** for an active Codex inference and **Disconnect** after it finishes to sign out.

The status panel identifies a local account session. It is **not** proof that a specific model or plan request will succeed; actual inference success depends on the account's entitlements and limits. Running Codex uses your own plan when supported and authenticated; it does **not** supply a general-purpose API key.

## Security, isolation and permissions

- A private `CODEX_HOME` subdirectory is created per FOXWORX actor under the existing state directory, with owner-only mode bits. The parent directory must have a non-root trusted owner and never be served as a web static directory. These permissions do **not** protect operator A from operator B if both can obtain a shell under the same OS UID.
- The Codex process inherits a scrubbed execution environment without `OPENAI_API_KEY` or other FOXWORX provider tokens. The backend never returns a managed credential, token file or bearer token to the browser. Avoid pasting sensitive material in prompts.
- FOXWORX asks Codex for a **read-only** sandbox with `approvalPolicy: never` in an empty provider workspace, and denies unexpected app-server approval requests. Codex can still have read access to files that the service Linux account can read. **A read-only sandbox is not a confidential-data sandbox or complete network egress policy.** Use separate Linux accounts/containers/nodes and OS-enforced restrictions if operators do not trust each other.
- Codex returns structured inference to the shared mode handlers. Native shell, web search and multi-agent features are explicitly disabled for provider threads. Tutor can explain and request existing read-only references. Copilot can prepare proposals but cannot approve them. Rabbit Hole can use only the target, methods and budgets in its existing operator grant and administrator policy. Sign-in adds no execution authority.
- Conversations sent to Codex use the same provider/model history partition and optional job-output sharing as other providers. Legacy native conversations are not silently replayed. The shared **Clear** button clears new shared chat records without deleting archived legacy Codex history.
- Tokens must stay on an operator-controlled runtime, never in a central hosted pool. Never reuse one person's subscription for another person's tasks. Do not add Codex sign-in to a paid service that charges users for accessing their ChatGPT plan.

## Open-source OAuth vs first-party Codex login

OpenAI separately offers **Sign in with ChatGPT plan usage for eligible open-source and selected private clients**. FOXWORX's public GitHub repository and its use of open-source libraries do not make it open-source software: the FoxWorx LLC company-only proprietary license restricts redistribution and other users' use. This release **does not claim enrollment in the open-source direct OAuth client program** or use a third party's OAuth client ID. The supported connection is handled by the unmodified, official Codex CLI/app-server's own ChatGPT authentication. If FoxWorx LLC later elects to offer an actual open-source version or receives approval for a private-client integration, implement the separate documented dynamic-registration flow only under its applicable terms.

Official references (review for changes):

- <https://developers.openai.com/codex/app-server/>
- <https://developers.openai.com/siwc/quickstart>
- <https://developers.openai.com/siwc/token-sharing-open-source>
- <https://openai.com/policies/sign-in-with-chatgpt-terms/>

## Limitations and acceptance testing

This build did not perform a real ChatGPT OAuth login or call an account-billed model in the test container. Run the documented first-sign-in, read-only turn, sign-out, service restart/re-authentication, account switch and Cloudflare browser-flow tests on each supported Kali device. Check that the `codex` binary version matches the currently published app-server schema. Authentication can fail if the Codex device-code mode is disabled, unavailable for your account, or blocked by network policy.
