> **Installed CLI autonomy:** These template restrictions describe workflow mode. A schema-3 policy may separately enable broader installed-tool execution and higher finite budgets. Legacy policies keep their permissions. See [Rabbit Hole](RABBIT-HOLE.md) and the [schema-3 example](../policy/adapter-policy.v3.installed-cli.example.json).

> **v2.8 extension:** This document describes the original schema-1 fixed-purpose policies. Schema 1 remains supported. For schema-2 administrator-registered CLI templates, typed model parameters, and human-review tiers, see [CLI-ADAPTERS.md](CLI-ADAPTERS.md). Installing v2.8 does not implicitly enable new tools.

# FOXWORX v2.7 — Administrator-Controlled Tool Adapters

## What changed

Rabbit Hole now draws its permission from **three independent choices**:

1. **Node administrator:** installs a root-owned JSON policy, listing which *reviewed, fixed-purpose* tool adapters may run autonomously and the maximum run budget.
2. **Engagement owner:** records authorized assets, exclusions, and authorization notes.
3. **Operator:** grants **one specific Rabbit Hole objective**, an exact target, a subset of administrator-enabled workflows, and a finite duration and iteration budget.

The intersection, not the AI's wishes, determines executable commands. A trusted administrator policy cannot define arbitrary commands, flags, plugins, URLs, files, or new executable paths. Each built-in adapter produces a predetermined argv from a validated, exact target.

**Security tradeoff on upgrade:** v2.7 **disables all Rabbit Hole autonomous launches until a root-owned policy is installed**. Normal manual jobs, Tutor, Copilot, and trusted-operator terminal sessions continue working. The policy is deliberately not writable through the browser, API, model, or non-root FOXWORX service account.

## Administrative installation (Kali ARM64 or x86-64)

Run the workbench's installer **as your non-root operator**. Afterward, in the extracted v2.7 directory:

```bash
bash scripts/adapter-policy.sh list
bash scripts/adapter-policy.sh validate policy/adapter-policy.example.json
```

Edit a **copy** of `policy/adapter-policy.example.json` and remove any adapters that should not be authorized. The example enables all 17 *built-in profiles* (not every Kali executable). It is a demonstration, not an endorsement of running all of them in an external bug-bounty program.

To grant that specific policy, use only the trusted OS `install` commands as an administrator:

```bash
sudo install -d -o root -g root -m 0755 /etc/foxworx
sudo install -o root -g root -m 0644 policy/adapter-policy.example.json /etc/foxworx/adapter-policy.json
bash scripts/adapter-policy.sh check
```

If you created your own reviewed policy file, replace the example filename in the second command with its path. **Do not run `sudo bash` against an installer or script from an operator-writable checkout.** The OS installation commands, not the application, manage elevated writes.

To revoke every unattended adapter, an administrator can remove or quarantine `/etc/foxworx/adapter-policy.json`. To revoke only selected permissions, install a newly reviewed JSON file with a reduced `enabled_profiles` list. The running service rereads policy and detects a revision change, aborting new actions and requesting termination of the current managed job. No service restart is necessary for policy changes. Already completed jobs and their evidence remain recorded.

### Policy schema

```json
{
  "schema": 1,
  "enabled_profiles": ["tcp-connect", "http-headers", "dns-a", "tls-certificate"],
  "max_steps": 8,
  "max_minutes": 15
}
```

The policy requires **exactly** these four fields. Unknown adapter names, duplicate entries, unknown JSON keys, invalid limits, unsigned/symlinked/untrusted parent directories, and group/world-writable or non-root-owned files fail closed. Allowed administrator caps: 1–16 decisions and 1–30 minutes. The operator can select lower limits but not higher ones.

`FOXWORX_ADAPTER_POLICY` may point to a different absolute root-owned policy location, provided its entire parent-directory chain is trusted. The recommended/default location is `/etc/foxworx/adapter-policy.json`.

### How to verify

```bash
bash scripts/adapter-policy.sh check
systemctl --user status foxworx-workbench
```

In the browser, open **AI copilot → Rabbit Hole**, then **Refresh adapter permissions**. The panel shows each built-in adapter as enabled/disabled and installed/missing. Only those both enabled and installed can be selected. An administrator's decision and a user-selected grant are stamped into each run. Any policy change invalidates that run, even if the changed policy is more permissive.

## Adapter inventory (17 total)

| Adapter | Tool | Behavior | Target form |
|---|---|---|---|
| tcp-connect | nmap | TCP connect and version-light discovery, 100 ports, low rate | Exact host or IP |
| tcp-web | nmap | TCP connect on ports 80, 443, 8080, 8443 | Exact host or IP |
| http-headers | curl | HEAD response headers, no redirects | Exact HTTP(S) URL |
| http-options | curl | OPTIONS response metadata, no redirects | Exact HTTP(S) URL |
| http-status | curl | HTTP GET with output discarded; status and timing metadata | Exact HTTP(S) URL |
| http-get-limited | curl | HTTP GET, bounded response, 20s deadline, no redirects | Exact HTTP(S) URL |
| dns-a / dns-aaaa | dig | IPv4/IPv6 address lookups | Exact hostname or IP |
| dns-mx / dns-txt | dig | MX and TXT lookups | Exact hostname or IP |
| dns-caa / dns-ns | dig | Certificate authority policy and nameserver lookups | Exact hostname or IP |
| dns-soa / dns-cname | dig | Zone authority and CNAME lookups | Exact hostname or IP |
| whois | whois | Registration metadata | Exact hostname or IP |
| tls-certificate | openssl | Read-only TLS handshake and certificate details on port 443 | Exact host or IP |
| web-fingerprint | whatweb | Low-intensity (`--aggression=1`) application fingerprint | Exact HTTP(S) URL |

`openssl`, `dig`, `nmap`, `whatweb`, and `whois` may not all be installed. Install missing Kali tools separately, review their behavior, and refresh inventory. A matching executable name is **not proof** that its package is configured correctly. Do not treat a CLI exit code of 0 or a model-generated summary as proof that a security finding is valid.

## What this protects — and what it does not

**Enforced in the application:** no arbitrary AI-supplied argv, no shell or privilege escalation, no arbitrary tool addition, no target expansion, no automatically granted additional methods, one grant per run, validated input scope, immutable proposed command checks, executable fingerprints, revocation checks before commands and while waiting, bounded time/steps/output, cancellation, audit records.

**Not yet enforced by this feature:** kernel/network-level destination restrictions, DNS-resolution pinning, proxy policy, redirection behavior of every third-party tool, Linux per-operator isolation, total packet/request rate across jobs, or sandboxing the normal manually operated shell. `dig`/`whois` can contact their normal resolver and referral infrastructure. **Administrator adapter policies are not firewall rules.** For truly constrained bug-bounty automation, run the worker inside a dedicated network namespace, VM, or container with independent egress policy, and verify the program permits the selected methods.

The model receives bounded, redacted result excerpts. Redaction is not guaranteed to remove all confidential details. Use a local trusted model when engagement confidentiality requires it. Rabbit Hole does not run indefinitely; after exhausting the finite budget, it reports what failed and what an operator can do next.

## Troubleshooting

- **Policy missing / untrusted:** check `ls -ld / /etc /etc/foxworx` and `ls -l /etc/foxworx/adapter-policy.json`; ensure root ownership, no group/world write, no symlinks. Run `bash scripts/adapter-policy.sh check`.
- **Newly installed tool remains disabled:** refresh the Toolbox inventory, then the adapter panel. Confirm binary is on the configured discovery path.
- **Start rejected:** the operator selected a disabled adapter, a target outside the saved scope, or a budget exceeding the administrator cap. A URL-only grant never authorizes an implicit whole-host port scan.
- **Run stopped mid-job:** check for administrator policy revision or engagement authorization change, resource limits, or operator cancellation. An interrupted Rabbit Hole run is never resumed automatically.
- **Unsupported scanner features:** third-party tools are version-sensitive. Try manually in your own lab first; do not weaken policy or authorize arbitrary arguments as a workaround.
