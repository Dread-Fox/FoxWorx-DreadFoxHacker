# Kali tool coverage and gap matrix

## What “all tools” means in v2

The terminal can launch installed executables available to the service account under its actual permissions. Inventory discovers executables in fixed system directories plus explicitly configured extra directories, and supplements them with installed package and system desktop metadata. It does not execute arbitrary discovered programs to obtain versions. Missing package metadata is shown as unknown rather than inferred.

There are **72 curated descriptions, four guided forms, and an open-ended discovered executable list**. These are different counts. The distribution contains no Kali binaries. “Installed” means an executable was discovered, not that its dependencies, permissions, architecture, services, license, GPU or radio are working.

## Four guided forms

| Profile | Tool | Managed input behavior | Important gap |
|---|---|---|---|
| TCP service inventory | nmap | One host/IP; unprivileged connect; 100 common ports; version-light; scan rate/retry/host timeout flags. | Service probes are active traffic. Rate flags are not a global application-request governor. No raw SYN/OS detection. |
| HTTP response headers | curl | One HTTP(S) URL; HEAD; no redirect following; user curl config disabled; timeouts. | HEAD may behave differently from GET. Advanced/native curl is not scope-contained. |
| DNS A record | dig | One hostname; A query; bounded retry/time; user dig config disabled. | Configured DNS resolvers are contacted; scope validation is not a DNS egress policy. |
| Registration lookup | whois | One validated host/IP input. | Registry referrals may contact external infrastructure; current program rules still apply. |

## Gaps that cannot be solved by a browser launcher alone

**GUI:** Burp, Wireshark's GUI, desktop ZAP and similar programs need a display or separate remote desktop. V2 labels desktop requirements and does not claim to render their windows. A CLI alternative is a separate workflow, not feature-equivalent GUI support.

**Interactive state:** Framework consoles, REPLs, pagers and tools that prompt require the real terminal. Foreground jobs have closed stdin and cannot be “driven” interactively through the chat. Scripts outside discovered directories, aliases, shell functions, virtualenv commands and Go/Cargo/pipx bins need explicit terminal invocation or configured PATH directories.

**Privileges/hardware:** Raw sockets, packet capture, Wi-Fi monitor/injection, Bluetooth and USB tooling depend on the actual kernel, interfaces, adapters and permissions. No hardware is virtualized by Cloudflare. NoNewPrivileges deliberately blocks setuid/file-capability escalation; availability will differ from root SSH. The application does not give every tool root.

**ARM/compute:** A Pi-compatible OS does not make every x86-only binary, GPU backend, Java GUI or commercial scanner Pi-ready. Test each executable's architecture/runtime and realistic resource use on your node. No benchmark or blanket tool-compatibility claim is made.

**Content/services:** Templates, wordlists, API tokens, browser runtimes, Java/Ruby/Python packages, databases, commercial licenses and auxiliary services can be missing even when the front-end binary exists. Check the vendor and Kali package documentation; the workbench does not silently install them.

**Naming:** Kali's ProjectDiscovery package/executable can use `httpx-toolkit`; a command named `httpx` may refer to a different program. V2 includes both names with an ambiguity warning rather than assuming they are interchangeable. Verify the actual executable/version before approving arguments.

**AI:** The built-in copilot can propose discovered foreground executables through literal arguments, but only four have guided validation. A native terminal AI agent is a separate executable with its own authentication, billing, tools and approval settings. The workbench does not automatically unify those controls.

**Scope:** No automatic HackerOne API synchronization, policy interpretation or actual network-destination enforcement is included. Advanced and terminal use remain operator-controlled. Notes are not a firewall.

## Complete curated catalog

The following entries are descriptive metadata, not a statement that these packages are installed or validated on your Pi. Additional discovered programs appear as unclassified executables and remain available through the terminal.

| Executable | Category | Mode | Package hint | Prerequisite / caution |
|---|---|---|---|---|
| nmap | Discovery | cli | nmap | TCP connect works unprivileged; raw SYN/OS detection need additional privileges. |
| curl | Web | cli | curl | Guided headers disable redirects and user curl configuration. |
| dig | DNS | cli | bind9-dnsutils | DNS queries use configured resolvers. |
| whois | DNS | cli | whois | May contact registry referral servers. |
| openssl | TLS | cli | openssl | Some subcommands are interactive; use the terminal. |
| httpx-toolkit | Web | cli | httpx-toolkit | Preferred Kali executable name; confirm installed version and program rate rules. |
| httpx | Web | cli | Official distribution | May be Python HTTPX, not ProjectDiscovery. Verify identity; prefer httpx-toolkit on Kali. |
| nuclei | Web | cli | nuclei | Templates, version, scope, rate and program policy need review; no blanket safe template set. |
| nikto | Web | cli | nikto | Active checks may be prohibited by individual programs. |
| ffuf | Web | cli | ffuf | Needs a wordlist, a small traffic budget and explicit program permission. |
| gobuster | Web | cli | gobuster | Wordlists and request rate must be selected deliberately. |
| feroxbuster | Web | cli | feroxbuster | Recursive requests can expand traffic; review scope and limits. |
| dirsearch | Web | cli | dirsearch | Review paths, wordlists and request limits. |
| whatweb | Web | cli | whatweb | Check probe aggression and program rules. |
| wafw00f | Web | cli | wafw00f | Makes network requests. |
| sqlmap | Web | cli | sqlmap | Potentially intrusive; manual scope and method review required. |
| wpscan | Web | cli | wpscan | Some data/features require a separate API token. |
| arjun | Web | cli | arjun | Rate and request volume require review. |
| katana | Web | cli | katana | Headless mode needs a compatible browser; crawling can leave intended scope. |
| subfinder | DNS | cli | subfinder | Some providers need separate API keys; discovered assets are not automatically in scope. |
| amass | DNS | cli | amass | Uses data sources and can be resource-intensive; review mode and permissions. |
| dnsrecon | DNS | cli | dnsrecon | Some modes are active enumeration. |
| dnsenum | DNS | cli | dnsenum | Review query volume and third-party queries. |
| dnsx | DNS | cli | dnsx | Verify ARM64 package availability and query rate. |
| fierce | DNS | cli | fierce | Do not treat newly found infrastructure as authorized. |
| theHarvester | OSINT | cli | theharvester | Provider keys and provider restrictions may apply. |
| recon-ng | OSINT | interactive | recon-ng | Interactive workspace; modules/API keys configured separately. |
| sherlock | OSINT | cli | sherlock | Use only in permitted investigations. |
| tshark | Traffic | cli | tshark | Offline PCAP analysis works unprivileged; live capture needs reviewed capture privileges. |
| tcpdump | Traffic | cli | tcpdump | Live capture needs permissions and an appropriate interface. |
| wireshark | Traffic | gui | wireshark | Requires a desktop; use tshark for terminal-only work. |
| burpsuite | Web | gui | burpsuite | Needs a desktop/browser and possibly a license; Java/browser performance on Pi varies. |
| zaproxy | Web | gui | zaproxy | GUI needs desktop; daemon modes can be invoked manually from the terminal. |
| firefox-esr | Web | gui | firefox-esr | Not displayed inside this terminal app; use local desktop or separately secured remote desktop. |
| chromium | Web | gui | chromium | ARM package support and sandbox requirements must be checked on the Pi. |
| msfconsole | Frameworks | interactive | metasploit-framework | Interactive framework; database services and module dependencies are separate. |
| msfdb | Frameworks | interactive | metasploit-framework | Database setup is administrative, not automatic. |
| gdb | Reversing | interactive | gdb | Debugging/ptrace privileges depend on OS policy. |
| radare2 | Reversing | interactive | radare2 | Architecture and target format matter. |
| rizin | Reversing | interactive | rizin | Use a terminal session for interactive work. |
| ghidra | Reversing | gui | ghidra | Requires desktop and a compatible Java runtime; substantial RAM. |
| binwalk | Forensics | cli | binwalk | External extraction helpers may need separate packages. |
| exiftool | Forensics | cli | libimage-exiftool-perl | Works on local workspace files. |
| file | Forensics | cli | file | Works on local workspace files. |
| strings | Forensics | cli | binutils | Works on local workspace files. |
| foremost | Forensics | cli | foremost | Evidence images and recovered files can use substantial disk space. |
| vol | Forensics | cli | volatility3 | Symbols, images and package version are separate requirements. |
| john | Passwords | cli | john | Compute-heavy; use only approved offline artifacts. |
| hashcat | Passwords | cli | hashcat | Pi has no general desktop GPU cracking capability; backend support must be checked. |
| hydra | Passwords | cli | hydra | Online guessing is often prohibited; obtain explicit permission and lockout limits. |
| aircrack-ng | Wireless | cli | aircrack-ng | Requires authorized local radio targets and suitable capture files/hardware. |
| airmon-ng | Wireless | cli | aircrack-ng | Needs compatible adapter/drivers and privileges; may disrupt networking. |
| airodump-ng | Wireless | interactive | aircrack-ng | Local radio hardware and monitor-mode privileges required. |
| bettercap | Traffic | interactive | bettercap | Privileges and network position required; not a HackerOne-wide permission. |
| responder | Network | interactive | responder | Needs a suitable authorized network and privileges; not internet bug-bounty default. |
| netexec | Network | cli | netexec | Protocol dependencies, credentials and explicit scope required. |
| smbclient | Network | interactive | smbclient | Some modes are interactive; use a terminal. |
| smbmap | Network | cli | smbmap | Authorized credentials/scope required. |
| enum4linux-ng | Network | cli | enum4linux-ng | Can generate many network requests. |
| ldapsearch | Network | cli | ldap-utils | Credentials, TLS trust and directory scope require configuration. |
| ssh | Utilities | interactive | openssh-client | Outbound SSH is not the Cloudflare web tunnel; review destination separately. |
| tmux | Utilities | interactive | tmux | Required for workbench reconnectable terminal sessions. |
| python3 | Utilities | cli | python3 | Advanced jobs execute with the service user privileges; not sandboxed. |
| bash | Utilities | interactive | bash | Full native shell access; guided checks do not constrain it. |
| zsh | Utilities | interactive | zsh | Full native shell access; guided checks do not constrain it. |
| jq | Utilities | cli | jq | Useful for structured tool output. |
| git | Utilities | cli | git | Clone only code you trust; repositories can contain executable hooks/scripts. |
| htop | Utilities | interactive | htop | Runs in a real terminal, not a non-interactive job. |
| btop | Utilities | interactive | btop | Runs in a real terminal. |
| codex | AI agents | interactive | Official distribution | Install/authenticate separately; external agent has its own permissions and billing. |
| claude | AI agents | interactive | Official distribution | Install/authenticate separately; not integrated into workbench approval controls. |
| aider | AI agents | interactive | Official distribution | Separate setup, model credentials and behavior apply. |

## Extending coverage

Run `bash scripts/tools.sh --preview` to inspect the small baseline package suggestion. `--install` asks for confirmation before apt installation; it does not install a Kali-everything metapackage. Install other tools separately through your administrator process, configure extra absolute executable directories when needed, restart and refresh inventory. Add a guided adapter only after writing input, command and network-behavior tests.
