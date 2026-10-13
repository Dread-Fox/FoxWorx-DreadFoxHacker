# FOXWORX v2.8 — CLI Tool Adapter Library

## The new feature

FOXWORX v2.8 retains **17 reviewed built-in Rabbit Hole workflows** and adds **19 sample command templates** plus a general root-policy template registry. Any discovered *noninteractive* Kali executable can be registered for **human-reviewed proposals** after administrator review. Autonomous templates are restricted to a smaller, code-approved executable allowlist. This is not permission for the model to execute arbitrary shell strings.

### Two permission tiers

- **Autonomous:** a root-approved command template can be selected by Rabbit Hole when the operator grants that exact workflow and target. The model can supply only bounded **integer** or administrator-enumerated parameter values. It cannot change executable, append flags, use shell syntax or supply new targets. Each run remains capped at 1–16 model decisions and 1–30 minutes; managed job timeouts also apply.
- **Review:** the model can **prepare** the command via Copilot, or an operator can select **Preview command** in the Rabbit Hole adapter panel. The existing immutable proposal dialog requires a fresh human approval **for every execution**. Review-only templates cannot be selected for an unattended Rabbit Hole run.

Unknown CLI tools are discoverable in the ordinary toolbox, but are **not** given autonomous privileges by discovery alone. Terminal-only tools, shells, interpreters, graphical applications and privileged interfaces are not magically made unattended-safe.

## Inventory of shipped templates

| Adapter ID | CLI | Intended function | Default mode |
|---|---|---|---|
| curl-metadata-tunable | curl | HTTP response metadata with model-chosen timeout and protocol | autonomous |
| nuclei-review | nuclei | Limited-template vulnerability checking | review |
| nikto-review | nikto | Web vulnerability audit | review |
| ffuf-small | ffuf | One URL containing `FUZZ`, low-rate discovery with installed wordlist | autonomous* |
| gobuster-small | gobuster | Low-thread directory discovery | autonomous* |
| feroxbuster-small | feroxbuster | Bounded web discovery | review |
| sqlmap-review | sqlmap | SQL injection checks | review |
| wapiti-review | wapiti | Web vulnerability audit | review |
| testssl-review | testssl | TLS audit | review |
| sslyze-cert | sslyze | TLS certificate information | autonomous |
| masscan-review | masscan | Restricted two-port inventory | review |
| rustscan-review | rustscan | TCP port inspection | review |
| theharvester-review | theHarvester | OSINT sources (third-party queries) | review |
| amass-passive | amass | Passive subdomain research | review |
| subfinder-passive | subfinder | Passive name discovery only | autonomous* |
| enum4linux-review | enum4linux-ng | SMB enumeration | review |
| smbclient-list-review | smbclient | Anonymous SMB share inventory | review |
| httpx-info | httpx-toolkit | Single HTTP endpoint information | autonomous |
| dnsrecon-review | dnsrecon | Basic DNS analysis | review |

`*` These may generate large request volumes, access third-party services, or discover additional names. Their **availability in the sample library is not approval to use them on real programs**. Keep them disabled unless an administrator verifies the current engagement rules and controls egress. Some options are version-sensitive and require validation on the target Kali installation before use.

**Not in the unattended adapter library:** Metasploit (`msfconsole`), other interactive consoles, GUI-only tools, general script interpreters, unrestricted credential attacks, and arbitrary exploit execution. These remain available only through the existing trusted-operator terminal or manual tools where the operator has appropriate OS and engagement permissions. Presence in Kali is not proof of legal authorization or safety.

## Create a schema-2 policy

Two working examples ship with the installer:

- `policy/adapter-policy.v2.example.json`: all 19 templates are registered; **only the original 17** built-in profiles are enabled. Administrators must explicitly opt in to every additional tool.
- `policy/adapter-policy.v2.recon-only.json`: minimal selection of built-in and low-intensity templates, with other registered examples disabled.

The original `policy/adapter-policy.example.json` remains a valid **schema-1** policy; upgrades do not silently expand what it authorizes.

```bash
cd ~/foxworx-kali-workbench-v2.8
bash scripts/adapter-policy.sh list
bash scripts/adapter-policy.sh validate policy/adapter-policy.v2.example.json
```

Edit a copy of the example to remove unneeded registered templates and select permitted IDs in `enabled_profiles`. The **same ID must be registered and enabled** before it can run. Then install the reviewed policy through root-owned system commands:

```bash
sudo install -d -o root -g root -m 0755 /etc/foxworx
sudo install -o root -g root -m 0644 your-reviewed-policy.json /etc/foxworx/adapter-policy.json
bash scripts/adapter-policy.sh check
```

**Do not `sudo bash` a script from the writable application directory.** The service uses the same strict root ownership and parent-directory checks as v2.7. Any policy revision while an autonomous run is in progress revokes that run and stops active managed work.

## Add a new executable

Create one object in `registered_adapters`. This example authorizes only an HTTP metadata read and gives the AI two tightly constrained parameter choices:

```json
{
  "id": "my-curl-headers",
  "tool": "curl",
  "label": "Bounded HTTP metadata check",
  "hint": "One approved URL; no redirects or response body",
  "target_kind": "url",
  "risk": "recon",
  "mode": "autonomous",
  "argv": ["--silent", "--head", "--max-time", "{param:timeout}", "{param:protocol}", "{target}"],
  "parameters": {
    "timeout": {"type":"integer", "min":5, "max":20, "default":10},
    "protocol": {"type":"enum", "choices":["--http1.1", "--http2"], "default":"--http1.1"}
  }
}
```

For autonomy, the reviewed executable must also be in the code-maintained autonomous allowlist (Curl, Nmap, Dig, WHOIS, OpenSSL, WhatWeb, SSLyze, FFUF, Gobuster, Subfinder, or ProjectDiscovery HTTPx). All other CLIs are **review-only**, even if an administrator edits the policy. Extending the autonomous allowlist requires a code-reviewed release.

The root policy permits up to 64 administrator-registered templates and no more than 8 parameters per template. `tool` must be a discovered noninteractive executable, not a command string, shell path, or root-only program. Values may be **bounded integers** or **enumerations**; there is deliberately no model-controlled freeform string, file path, unreviewed flag, or arbitrary command array. Every argv template must include the single `{target}` placeholder. The backend uses `create_subprocess_exec` without a shell.

**The example is a pattern, not a security certification for other utilities.** A CLI can redirect traffic, load plugins/configuration, invoke subprocesses, perform destructive actions or follow newly discovered targets internally. These behaviors need binary-specific review and independent egress isolation. The platform does not inspect kernel network traffic, guarantee DNS pinning, or prevent an authorized process from contacting unapproved destinations.

## Workflow

1. Install or confirm the executable on the **specific** Pi/workstation; refresh the Kali toolbox.
2. As node administrator, review flags, tool/version behavior, credentials, prerequisites, permissions, redirection, third-party contacts, output files, request volume, and scope effects.
3. Register the argv template in schema 2; choose `mode` and a `risk` label (`recon`, `active`, `intrusive`). `intrusive` must always be `review`.
4. Add its ID to `enabled_profiles` **only after approval** and install the policy with root permissions.
5. Operators see it in **Rabbit Hole → Administrator-enabled Kali adapters**. Autonomous ones can be checked for one-time operator authorization; review-only ones have a **Preview command** button.
6. Copilot sees only enabled template metadata. It may generate a reviewed proposal, never approve it. Rabbit Hole sees only operator-approved, administrator-autonomous profiles and bounded parameters.
7. Read actual saved output and exit codes; a model-generated summary or exit code zero does not verify that a finding exists.

## Current limits

This is an *extensible* registry, not adapters for every command in Kali already fully configured or verified. The curated library provides representative recipes for popular CLIs; most system commands and hundreds of specialized Kali programs require administrator-specific schemas. GUI programs, interactive REPLs, tools requiring privileged packet capture, nested shells, secrets, and programs with unavoidable secondary target expansion are still outside unattended mode. Managed jobs and ordinary terminal share the Linux service identity: isolate untrusted operators with OS identities/VMs first. Network-level egress controls are required for real unattended bug-bounty use.
