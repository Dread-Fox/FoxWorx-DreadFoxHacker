# AI modes, providers and models

The same provider gateway is supported on **Kali ARM64 and x86-64**. On the Z790, install Ollama or another inference server separately and select its loopback endpoint. On a Pi, use an admin-approved private/SSH-forwarded endpoint to the workstation for larger models. GPU detection in the Node tab is informational only; there is no embedded NVIDIA driver installer or automatic model distribution. See [PLATFORMS.md](PLATFORMS.md).

FOXWORX no longer requires OpenAI. Select an **operator-specific** cloud or self-hosted model in **AI copilot → Provider & model**. The model provides explanations, lookup and reviewable proposals, **not execution authority**. Copilot proposals require review and approval of an exact immutable command. Rabbit Hole instead uses an explicit target/method/budget grant and the existing administrator adapter policy. The full native shell remains outside those checks.

## Included integrations

| Browser provider | Inference route | How to connect |
|---|---|---|
| OpenAI | `openai/MODEL` | Operator API key; legacy `OPENAI_API_KEY`/`OPENAI_MODEL` still work |
| Codex · ChatGPT | Native Codex app-server | ChatGPT device sign-in; exact model ID or `default`; no API key |
| Anthropic Claude | `anthropic/MODEL` | Operator API key or shared Pi `ANTHROPIC_API_KEY` |
| Google Gemini | `gemini/MODEL` | Operator key or Pi `GEMINI_API_KEY` |
| xAI Grok | `xai/MODEL` | Operator key or Pi `XAI_API_KEY` |
| DeepSeek | `deepseek/MODEL` | Operator key or Pi `DEEPSEEK_API_KEY` |
| Mistral AI | `mistral/MODEL` | Operator key or Pi `MISTRAL_API_KEY` |
| Ollama | `ollama_chat/MODEL` | Approved Ollama URL, no key by default |
| LM Studio | `openai/MODEL` | Approved LM Studio OpenAI-compatible URL; key optional |
| vLLM | `openai/MODEL` | Approved vLLM OpenAI-compatible URL; key optional |
| Custom compatible server | `openai/MODEL` | Administrator-approved `/v1` URL; key optional |

The UI accepts exact model identifiers rather than hardcoding an obsolete roster. Its examples are **hints, not a list of guaranteed current models**. Provider entitlements, endpoint compatibility, available context and tool support vary by model and account. **The "test connection" button sends a real request, which can be billable; it does not prove tool-calling support.** Tutor mode can still work when the selected model cannot call tools.

API-key and local-server provider adapters use the *LiteLLM Python SDK* installed from `requirements-ai.txt` by default. Codex uses its installed native CLI and works without LiteLLM. The base terminal/toolbox can be installed without it (`bash scripts/install.sh --without-ai`); LiteLLM-backed providers then report that the optional engine is unavailable.

## Independent mode and model selection

Choose Tutor, Copilot, or Rabbit Hole in the workbench. Use Provider & model separately to save your provider, model and connection. Switching modes preserves the selection. All providers use the shared chat interface and the existing mode controls.

For Codex, select **Codex · ChatGPT**, sign in through **Sign in with ChatGPT**, and select a discovered model ID or enter `default`. Click **Use this model**. No API key or local inference endpoint is required. See [Codex setup and limits](CODEX-AGENT.md).

## Cloud API-key model setup

1. Obtain an API key from the **actual provider**. A ChatGPT/Claude web subscription is not automatically an API key or API billing account.
2. Open **AI copilot → Provider & model**, choose a cloud provider, paste the key into **API key** and click **Save key**. The input clears on success and is never returned by the settings API.
3. Enter a currently available model ID without a provider prefix (e.g. if the provider is Anthropic, do **not** enter `anthropic/` again). Click **Use this model**.
4. Click **Test selected connection**. A successful text reply verifies basic inference but **not** function calling. Start in **Tutor** mode, then try **Copilot** with a harmless local proposal for an authorized engagement.

Shared Pi-level provider keys are also supported in `settings.env`, but **any trusted operator using this Linux account can reach those files through the native shell**. Browser API keys are Fernet-encrypted in SQLite using a separate `FOXWORX_AI_ENCRYPTION_KEY` in the private host configuration. This protects against accidental plaintext exposure in routine DB backups, **not** against a same-UID shell user, a compromised Pi or an administrator. Team members who do not fully trust one another need separate accounts/containers and a separate privilege-separated credential broker **before** using this as a multi-tenant platform.

Only messages tagged with the **same provider and model** are replayed as chat history. Switching providers does **not** silently forward previous providers' chat history. Current engagement scope and notes, and a selected job excerpt **only if the operator opts in**, are sent with each request. Cloud providers may process/retain submitted data under their own terms; this release does not promise zero provider retention.

## Local Ollama on the Pi

When Ollama is running on the same Pi at `http://127.0.0.1:11434`, select **Ollama** and endpoint **ollama-local**, then **Discover models**. You must install and start Ollama separately and download a compatible model. The workbench never downloads weights automatically. Raspberry Pi 4B RAM/CPU may make even a small quantized model slow. Model tool calling is model-dependent.

## Ollama on a desktop/GPU workstation (recommended for stronger local inference)

The **Kali Pi executes pentesting tools** and the desktop **serves inference**. The Pi must be able to reach the inference server's configured network address independently of Cloudflare Tunnel. Cloudflare Tunnel here publishes the *browser workbench*, not outbound model traffic. Don't expose an unauthenticated Ollama port on the public Internet. Use a private trusted LAN, network firewall and/or a reviewed private network/tunnel.

On the **Pi**, edit `~/.config/foxworx-workbench/settings.env` and set one escaped dotenv string:

```ini
FOXWORX_AI_ENDPOINTS='{"gpu-ollama":{"provider":"ollama","url":"http://192.168.1.50:11434"}}'
```

Change the address to your desktop's actual private IP. Keep the quote marks as shown. You can configure more than one named endpoint; supported endpoint `provider` values are `ollama`, `lmstudio`, `vllm`, `custom`. Server routes **must be admin-approved in this private file**; web operators cannot supply arbitrary URLs, IP addresses or redirects.

For LM Studio, add a route such as:

```json
{"desktop-studio":{"provider":"lmstudio","url":"http://192.168.1.50:1234/v1"}}
```

For vLLM, a route such as:

```json
{"gpu-vllm":{"provider":"vllm","url":"http://192.168.1.50:8000/v1"}}
```

These JSON objects are alternatives or entries to merge into the single `FOXWORX_AI_ENDPOINTS` map. Configure the actual inference server with listening, TLS/firewall and model permissions separately. Restrict unencrypted HTTP to a genuinely trusted/private path. For a custom server, use HTTPS for an Internet-reachable endpoint. Configured endpoints can contact networks from the Pi, so review every entry as a privileged administrative decision.

Apply Pi configuration changes:

```bash
systemctl --user restart foxworx-workbench
bash scripts/doctor.sh
```

Afterwards select the named endpoint in **Provider & model**. **Discover models** probes an approved Ollama `/api/tags` or OpenAI-compatible `/v1/models` route without following redirects. Some servers do not support listing; enter the exact ID manually. If your local compatible server requires an API key, save it in the same UI for that provider; no cloud API key will be automatically forwarded to a keyless local compatible server.

## Migration from v2.0

Stop the old v2 service *deliberately*, back up engagement evidence and `~/.local/share/foxworx-workbench-v2`, and install v2.4 in its own directory. **The new installer preserves your existing database and configuration** and adds `FOXWORX_AI_ENCRYPTION_KEY` if missing. It does not modify the Kali image or uninstall the old directory. After reinstalling, your existing `OPENAI_API_KEY` plus `OPENAI_MODEL` remain the default unless you select something else. The other providers are configured per operator.

**Important:** preserve `FOXWORX_AI_ENCRYPTION_KEY` in any full restore of per-operator encrypted keys. Rotating the *login* token/session secret is independent from the encryption key after migration. Changing the encryption key without a migration will make stored provider keys unreadable; re-enter them through the UI. Provider keys live in the existing SQLite database and are **not automatically included in engagement evidence ZIP exports**.

## Troubleshooting / limitations

- **AI badge says "Install engine"**: LiteLLM SDK is missing. In the workbench directory, run `.venv/bin/python -m pip install -r requirements-ai.txt` then restart. If this fails, capture the pip error and resolve platform/dependency compatibility; the terminal/toolbox remain functional.
- **No model found**: inference server not reachable from Kali, local service has no model weights loaded, model ID differs from advertised ID, or `/models` is unsupported. Try the provider's own status endpoint from a trusted local terminal and ensure you are only contacting your configured inference server.
- **Unauthorized / quota**: provider key, permission or billing limits. Provider error bodies are not sent to the browser because they can contain secrets. Inspect relevant provider logs in your own accounts.
- **Tool calling rejected**: use Tutor mode or choose a model that explicitly supports function calling. API text completion is **not** proof a model can prepare jobs. JSON/tool-call formats and API policies differ by provider.
- **Previous chat disappeared from model context**: this is intentional after switching provider **or model**. The UI can still display prior messages, but they are not automatically sent to the newly chosen model.
- **Secrets and trust**: an unrestricted browser terminal has the permissions of the service Unix user. Encrypted per-operator keys are **not an isolation mechanism** between untrusted users on that host.
- **Costs/usage**: this release does not calculate a reliable cross-provider price. Set quota/spend limits at each provider and monitor the provider's own billing dashboard.

Relevant upstream docs: https://docs.litellm.ai/docs/providers , https://docs.litellm.ai/docs/ . Check current provider/model names at deployment time.
