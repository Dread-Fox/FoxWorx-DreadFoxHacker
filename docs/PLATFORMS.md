# Supported Kali platforms — Raspberry Pi ARM64 and x86-64 workstations

FOXWORX 2.3 runs one application source tree on both supported CPU architectures. Install **separately on each machine**, with its own non-root Linux account, service, config, engagement data, Cloudflare Access application, and tunnel. The two instances are independent nodes: there is **no centralized multi-node orchestrator or automatic evidence synchronization**.

## Supported configurations

| Feature | Kali ARM64 / Raspberry Pi 4B | Kali x86-64 / Z790 workstation |
|---|---|---|
| Architecture (`uname -m`) | `aarch64` (the 64-bit image; 32-bit ARM is unsupported) | `x86_64` |
| Python | 3.11+ with `python3-venv` | 3.11+ with `python3-venv` |
| Browser + Cloudflare | Same UI and Access security requirements | Same UI and Access security requirements |
| Full PTY and curated tool inventory | Yes, tools actually available on ARM64 | Yes, tools actually available on x86-64 |
| Default **new-install** resource limits | 2 jobs, 4 terminals, 256 MiB free-disk reserve | 4 jobs, 8 terminals, 1024 MiB free-disk reserve |
| GPU local inference | Usually a separate inference host | Optional NVIDIA inference via a separately managed Ollama/LM Studio/vLLM service |
| GUI-only Kali tools | **Not** rendered by FOXWORX | **Not** rendered by FOXWORX, even with a physical GPU/desktop |
| NVIDIA drivers and CUDA | Not required by FOXWORX | Not required by FOXWORX; required separately for NVIDIA acceleration where applicable |

**Important:** A clean upgrade from v2/v2.1 preserves existing limits, credentials, identity and SQLite evidence. Host presets are only applied on the first creation of `settings.env`. For upgraded installations, adjust resource limits manually after reviewing available RAM/disk, then restart. Neither profile installs additional Kali tools or bypasses Linux privileges.

## First run on either host

```bash
uname -m                  # aarch64 or x86_64
python3 --version         # 3.11 or newer
cd ~/foxworx-kali-workbench-v2.4
bash scripts/install.sh --preflight   # read-only; also works before sudo setup
bash scripts/install.sh               # installs only Python runtime prerequisites and venv deps
bash scripts/doctor.sh
```

`--preflight` never installs drivers or packages, writes config, or starts systemd. It returns nonzero on unsupported Linux architectures, macOS/Windows kernels, or Python older than 3.11. If system packages are already installed, use `bash scripts/install.sh --skip-apt`.

The ordinary installer requires a **non-root** account with an active systemd user session. By design, it does not install drivers, permit privileged networking, install a particular model, or provide a browser desktop environment. `systemctl --user status foxworx-workbench` checks the service.

## Hardware detection and the Node tab

The web UI's **Node** tab reports the normalized CPU architecture, Linux distribution, approximate logical-CPU count, installed Kali executable count, optional Ollama executable, and GPU detection status. If `nvidia-smi` is installed, the backend executes a bounded query (3-second timeout, cached for up to 30 seconds) showing GPU count, model names, VRAM totals/free estimates and driver version. Missing, broken or slow driver queries **do not prevent FOXWORX from starting**. PCI identifiers and GPU UUIDs are never sent to the browser.

A GPU showing up in Node does **not** prove CUDA is operational, that Ollama can access it, or that an inference model will fit. An executable showing up in Toolbox does **not** prove architecture-compatible runtime libraries, granted network/raw-socket capabilities, hardware interfaces, model weights, licenses or dependencies.

## Z790 with three RTX 3060 Ti devices

1. First verify Linux can see the GPUs: `lspci | grep -i nvidia`. Then check `nvidia-smi -L` and `nvidia-smi` from a **local administrator terminal**, without altering FOXWORX permissions.
2. If drivers are missing, follow **Kali's official NVIDIA driver installation guide** after a separate OS backup. Kernel headers, DKMS, non-free repositories and reboot requirements depend on your current Kali kernel; FOXWORX will not run an unattended driver installer. Reference: https://www.kali.org/docs/general-use/install-nvidia-drivers-on-kali-linux/
3. Install and run your chosen inference backend **as a separate service**, not inside the FOXWORX worker. For Ollama, follow https://docs.ollama.com/linux and https://docs.ollama.com/gpu ; verify a model responds from the workstation's own terminal first.
4. With Ollama bound to `127.0.0.1:11434` on the **same** workstation, FOXWORX already includes the **`ollama-local`** endpoint. In **AI copilot → Model & keys**, choose Ollama, select or type a model, then click **Test selected connection**.
5. To choose specific GPU devices for the Ollama service, use `CUDA_VISIBLE_DEVICES` in **Ollama's** service environment, not in FOXWORX's `.env`. Get stable GPU UUIDs with `nvidia-smi -L` locally. Check the Ollama server logs for actual device offload.

**VRAM is not automatically pooled as one contiguous 24-GiB GPU.** Your three 8-GiB cards may enable model distribution depending on backend/model, but memory placement, context length, parallelism and available VRAM determine whether a model fits. Three devices do not guarantee that any particular 24-GiB model can load or run well.

## Use workstation-hosted Ollama from the Pi

Cloudflare Tunnel only provides **operator browser ingress**. It does **not** automatically expose your workstation's inference server to a Pi, and exposing Ollama's unauthenticated API on the public Internet is unsafe. Keep Ollama bound to loopback, and use a trusted SSH tunnel or secured private network.

Example: from the **Pi** open an SSH port forward to the workstation (replace names with your own):

```bash
ssh -N -L 127.0.0.1:11435:127.0.0.1:11434 foxoperator@Z790_LAN_ADDRESS
```

This makes the workstation's loopback Ollama API reachable on **the Pi's** `127.0.0.1:11435` while the SSH connection remains active. In the Pi's `~/.config/foxworx-workbench/settings.env`, configure an explicitly admin-approved local route:

```dotenv
FOXWORX_AI_ENDPOINTS='{"z790-ollama":{"provider":"ollama","url":"http://127.0.0.1:11435"}}'
```

Then restart the **Pi** workbench (`systemctl --user restart foxworx-workbench`), select `z790-ollama` in Model & keys, discover an installed model, and test it. The route does not start, secure or keep SSH alive; use a supervised SSH service/tunnel manager if you later need persistence. Do **not** use public Cloudflare hostname to reach an unauthenticated model server.

For optional externally accessible browser workbenches, secure each HTTPS hostname with an upstream access policy and set `FOXWORX_AUTH_MODE=proxy` and its matching exact `FOXWORX_ORIGIN`. Example hostnames: `pi-kali.example.com` and `z790-kali.example.com`, each mapped to its local `http://127.0.0.1:8765` service. Configure and enforce authorization separately on each host; the web UI currently manages **one host per URL**, not both nodes in one tab.

## Tool and security limitations that do not change by CPU

- The registry scans executables present on **that** machine. Some Kali tools are not distributed for ARM64, may have x86-only package builds, need external wordlists/templates, or require elevated privileges or radio hardware. Refresh inventory after installing software. It does not remotely install tools.
- Terminal commands run under the dedicated FOXWORX Linux account. On either platform, additional permissions are not granted to make an unavailable Kali tool work. The `NoNewPrivileges` systemd setting is intentional.
- Browser users on the same node share that Unix account. Cloudflare identity is **not** OS isolation. Use trusted operators or separate Unix users/hosts.
- Tool input checks are not a network sandbox or HackerOne scope authorization. Manual approval remains mandatory; only perform program-authorized work.
- GPU model serving consumes GPU/CPU/RAM independently from the workbench. Monitor contention on the workstation; AI SDK support and driver compatibility need separate live testing on each Kali installation.

## v3.2 hardware visibility

On ARM64 and x86-64, FOXWORX reads kernel sysfs/procfs to inventory visible PCI/USB/network/DRM/accelerator devices. A Raspberry Pi without an Nvidia GPU can still enumerate its USB wireless dongles and network interfaces. A workstation with three NVIDIA cards continues to use `nvidia-smi` for GPU memory, with DRM/PCI data as separate evidence of device nodes. NPUs require kernel drivers exposing devices; PCI processing accelerators are only candidates. See [Hardware Intelligence](HARDWARE-INTELLIGENCE.md).
