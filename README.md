# FOXWORX Kali Workbench · v3.3.3

FOXWORX DreadFoxHacker is a browser-based workbench for **authorized FoxWorx operators**. It brings a Linux terminal, local tool discovery, managed jobs, evidence, and optional AI assistance into one workspace for authorized security assessments and lab work.

Run the service on a compatible Linux machine and open it locally or through an independently configured remote connection. Raspberry Pi and Z790 systems are examples, not required hardware.

**License:** © 2026 FoxWorx LLC. This is proprietary software. Employees and contractors may use it within their express FoxWorx LLC authorization; other use requires permission under the [LICENSE](LICENSE). A public GitHub repository does not grant a public license. Third-party components retain their own licenses.

> **Access model:** The default installation listens on `http://127.0.0.1:8765` with no application login. Anyone who can reach the service can use its terminal and access its data as the service's Linux account. Use a trusted local environment and control access to any remote route. See [local service and remote access](docs/LOCAL-SERVICE.md).

## Supported platforms

The application checks the operating system and CPU architecture, not a particular motherboard or computer model.

| Requirement | Supported configuration |
|---|---|
| Intended operating system | Kali Linux, 64-bit |
| Intel / AMD hosts | `x86_64` / `amd64`: desktops, laptops, mini PCs, workstations, servers, or Linux virtual machines |
| ARM hosts | `aarch64` / `arm64`: Raspberry Pi and other 64-bit ARM Linux systems with compatible dependencies |
| Python | 3.11 or newer, with virtual-environment support |
| Service account | Dedicated non-root Linux account with a writable home directory and an active systemd user session |
| GPU | Optional; the terminal, toolbox, jobs, and evidence features do not require one |
| Browser access | A modern browser on the host or another device, including a phone or tablet |

Other Linux distributions pass the platform check on these architectures, but package names, dependencies, and assessment tools need separate verification. Acceptance by the platform check does not mean every device or distribution has been tested. Native Windows, macOS, 32-bit ARM, and 32-bit x86 service hosts are unsupported; Windows and macOS devices can still access a Linux-hosted instance through a browser.

Available tools depend on the host's installed packages, permissions, drivers, and connected hardware. FOXWORX does not require a Z790 motherboard, NVIDIA GPU, Cloudflare account, or cloud AI subscription. See the [platform and optional GPU guide](docs/PLATFORMS.md).

## What operators can do

| Workspace | Capabilities |
|---|---|
| Terminal | Use a native Linux shell with reconnect, resize, bounded output replay, and multiple sessions. Sessions remain active when the browser disconnects while the service is running. |
| Toolbox | Discover installed executables, search tool descriptions, inspect prerequisites, and distinguish command-line, interactive, and desktop tools. |
| Managed jobs | Review command proposals, approve execution, follow live output, inspect exit status, and stop jobs. Jobs have output, timeout, and concurrency limits. |
| Engagements and evidence | Organize assessment scope, authorization notes, jobs, and uploaded files; export evidence with a checksum manifest. |
| AI assistance | Choose Tutor, Copilot, or Rabbit Hole, with a separately selected provider and model. Terminal and toolbox operation do not depend on AI. |
| Investigation Graph | Explore recorded tool execution, retries, evidence, and output observations; annotate and export the graph. Parsed observations are not independently verified findings. |
| Tool Intelligence | Read local tool references, cache version-specific documentation, and save operator notes. Online retrieval requires administrator enablement. |
| Hardware Intelligence | Inspect Linux-visible CPU, RAM, network, PCI/USB, graphics, and accelerator information; review network-interface roles. Detection does not guarantee a device's assessment capabilities. |
| Discord Team Intelligence | Optionally share approved findings and receive engagement-tagged team context through one configured Discord channel. Messages do not authorize command execution. |
| DreadFox companion | Use an optional evolving digital companion with offline dialogue, opt-in AI conversation, and opt-in summaries of limited activity categories. The companion has no tool-execution privileges. |

Tool discovery does not install tools, and desktop-only tools are not rendered as a remote desktop. Hardware detection and documentation do not grant additional Linux permissions.

## Install on a Linux host

Use these steps as an authorized operator signed in to a dedicated **non-root** account. Keep an administrator or console recovery path available. The installer requires Internet access to download Python dependencies.

### 1. Obtain the application

Clone the repository into the operator's home directory:

```bash
cd ~
git clone https://github.com/Dread-Fox/FoxWorx-DreadFoxHacker.git
cd FoxWorx-DreadFoxHacker
```

Alternatively, extract an authorized release archive and open its application directory. Use a directory path without spaces, quotes, percent signs, or backslashes. The installed service uses this path; rerun installation if it changes.

### 2. Check compatibility and install

```bash
bash scripts/install.sh --preflight
bash scripts/install.sh
bash scripts/doctor.sh
```

The preflight reports host compatibility without changing files, packages, or services. The installer creates a Python virtual environment, installs application dependencies, and registers the `foxworx-workbench` systemd user service. It requests sudo only when the minimal OS dependencies need installation. It does not install the Kali tool collection, NVIDIA drivers, a model server, or Cloudflare.

Useful installation options:

| Option | Purpose |
|---|---|
| `--without-ai` | Skip the optional LiteLLM dependencies for cloud and local model providers. |
| `--skip-apt` | Skip OS package installation when the required dependencies are already available. |
| `--no-start` | Prepare the installation without starting the service. |

**Upgrades:** Save needed evidence and finish active work before stopping an existing service with `systemctl --user stop foxworx-workbench`. Stopping interrupts live terminals and jobs. The installer refuses to replace a running workbench and preserves existing state and credentials, but this release backs up and migrates authentication mode, port, and origin to the default token-free local configuration. Review the [installation and upgrade guide](docs/INSTALL.md) before updating an existing deployment, especially one using authenticated access.

### 3. Open the workbench

Open **http://127.0.0.1:8765** in a browser on the host. The default installation has no setup token or application sign-in screen. Signing in to an optional AI provider is a separate operation.

Check service status or logs when needed:

```bash
systemctl --user status foxworx-workbench --no-pager
journalctl --user -u foxworx-workbench -n 80 --no-pager
```

See [installation](docs/INSTALL.md) for startup after logout or reboot, backups, and rollback.

## First operator workflow

1. Open the default **Local lab** engagement, or create an engagement with the assessment's exact scope and authorization notes.
2. Open a terminal and confirm basic operation with commands such as `pwd` and `uname -m`.
3. Refresh the toolbox and inspect the tools actually installed on this host. Run a harmless check such as `curl --version` if Curl is available.
4. For a managed job, review its proposed command and target, confirm authorization, and approve it. Check the recorded output and exit status in Jobs.
5. Organize evidence in the engagement and export it when needed.
6. If using AI, open **AI copilot → Provider & model**, configure the chosen provider, and try **Tutor** before enabling assessment workflows.

On a phone or tablet, swipe inside the terminal or use **Output history** to read earlier output. Tap **Latest output ↓** to return to the newest lines. Fullscreen terminal programs may not provide scrollback.

Read the [operator guide](docs/OPERATOR-GUIDE.md) for the full workflow.

## AI modes and optional integrations

**Tutor** provides explanations and read-oriented assistance. **Copilot** can prepare managed command proposals; execution requires an operator's explicit approval. **Rabbit Hole** discovers tools, checks results and tries alternatives automatically after one initial task authorization. Choose selected administrator workflows or, with an enabled schema-3 policy, installed CLI tools with model-constructed arguments. Installed CLI mode uses the Linux service account's file and network access; its stated target is not an enforced sandbox. Follow-up prompts steer the active task while its targets and finite budget stay fixed. Rabbit Hole requires a separately installed administrator policy.

**Large tool inventories:** The backend ranks installed tools using names, descriptions and local package/manual metadata. Agents receive at most 10 relevant candidates, then can refine filters or page through more matches. There is no fixed inventory-count ceiling; synthetic tests cover up to 50,000 entries. Inventory refresh runs in the background when stale, and manual Refresh remains available. See [tool discovery](docs/TOOL-DISCOVERY.md).

The provider selector supports cloud providers, Codex, and administrator-approved local inference servers. Model availability, credentials, costs, and tool-calling support depend on the selected provider. A successful connection check does not establish that every AI workflow is supported. Codex offers its own account sign-in flow; operators should not put account passwords, cookies, or access tokens into workbench chat.

Local inference is a separate service, such as Ollama, LM Studio, or vLLM. FOXWORX does not install or manage its drivers, models, or GPU allocation. Provider credentials and approved local endpoints are configured through the browser settings and private host configuration. For host configuration changes:

```bash
bash scripts/configure.sh
systemctl --user restart foxworx-workbench
```

Use the dedicated setup guides:

- [AI providers, credentials, and local inference](docs/AI-PROVIDERS.md)
- [Codex provider setup and limits](docs/CODEX-AGENT.md)
- [Rabbit Hole authorization and limits](docs/RABBIT-HOLE.md)
- [Administrator tool policy](docs/ADAPTER-POLICY.md) and [CLI adapters](docs/CLI-ADAPTERS.md)
- [Discord team setup and sharing](docs/DISCORD-TEAM.md)
- [DreadFox companion and privacy controls](docs/DREADFOX.md)

## Remote access and team deployments

For access from another computer, an operator can use an SSH forward to the Linux host:

```bash
ssh -N -L 127.0.0.1:8765:127.0.0.1:8765 operator@HOST_ADDRESS
```

Replace `operator` and `HOST_ADDRESS` with the host's SSH account and address, keep the connection open, and browse to `http://127.0.0.1:8765` on the client. The client port must be available.

A separately managed HTTPS reverse proxy or tunnel can also forward to `http://127.0.0.1:8765` with WebSocket support. Cloudflare is optional. The application does not create a tunnel, register a domain, or enforce visitor identity in default open mode. HTTPS alone does not restrict who can operate the workbench; configure access controls on the remote route before making it reachable outside the trusted operator environment.

**Operators sharing an instance share authority.** In default open mode, visitors use one shared local operator identity and the same Linux service account. They can access that account's files, configuration, evidence, and connected integrations. Credential encryption does not isolate operators who share its shell access. Use separate service accounts or hosts where separate trust boundaries are required.

Install each host independently, with its own service, configuration, and data. Discord can provide optional team context, but FOXWORX does not provide centralized fleet management or automatic evidence synchronization. See [local and remote access](docs/LOCAL-SERVICE.md) and [security boundaries](docs/SECURITY.md).

## Operational limits and verification

This is a tested development distribution for trusted operators. It has not undergone an independent security audit, and the checks do not establish compatibility with every supported architecture, physical device, inference provider, or external integration.

Guided scope checks validate inputs; they do not enforce actual network destinations. Terminal commands and some tools can reach beyond the stated scope. Assessments require operator authorization and appropriate host/network isolation. The service does not install passwordless sudo or grant extra privileges to make tools work.

For verification details, consult the dated [release report](verification/TEST-REPORT.md) and the feature reports in [verification/](verification/). Hardware installation, reboot behavior, remote transport, and live provider or Discord connections need validation in each deployment.

## Documentation

- [Installation, upgrades, and rollback](docs/INSTALL.md)
- [Operator guide](docs/OPERATOR-GUIDE.md)
- [Configuration reference](docs/CONFIGURATION.md)
- [Platform and optional GPU setup](docs/PLATFORMS.md)
- [Security boundaries](docs/SECURITY.md)
- [Tool coverage and prerequisites](docs/TOOL-COVERAGE.md)
- [Tool Intelligence](docs/TOOL-INTELLIGENCE.md)
- [Ranked tool discovery](docs/TOOL-DISCOVERY.md)
- [Hardware Intelligence](docs/HARDWARE-INTELLIGENCE.md)
- [Investigation Graph](docs/INVESTIGATION-GRAPH.md)
- [Developer guide](docs/DEVELOPER.md)
- [Dependency provenance and third-party licenses](docs/DEPENDENCIES.md)
- [Release history](CHANGELOG.md)

Application source, tests, policies, installation scripts, and bundled frontend assets are included in this repository. Kali tools, provider credentials, model weights, and tunnel credentials are not bundled.
