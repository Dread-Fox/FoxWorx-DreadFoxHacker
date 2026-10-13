# FOXWORX v3.2 — Hardware Intelligence and Device Roles

**Scope:** read-only inventory of hardware that the Linux kernel exposes to the dedicated non-root FOXWORX service. This is not a claim to see every physically connected peripheral, a driver installer, an NPU model runtime, a wireless attack adapter or a network containment system.

## Open the Hardware workspace

Select **Hardware** from the top workspace tabs. Select **Rescan** to retrieve the current detected hardware. The scanner uses sysfs and procfs; where available it also runs one bounded, read-only `iw phy <phy> info` query per discovered wireless PHY. It never invokes interface mode switches, network scanning, packet injection, driver installation or GPU workloads.

The inventory covers:

- **CPU** model, logical threads, system RAM (from the Linux kernel; no `/proc/cpuinfo` serials are published).
- **Networking:** visible Linux interfaces, type, link state, MTU, driver when exposed, wireless PHY, and default-route detection. Hardware MAC addresses and IP addresses are not returned by the API.
- **Wi-Fi:** whether `iw` explicitly advertises `monitor` interface mode. It does **not** test packet injection. Both channel switching and monitor activation are operator-managed operations outside this subsystem.
- **PCI:** device class, slot, vendor and device numeric IDs, driver and NUMA node. PCI processing accelerators are tagged **candidates**, not confirmed NPUs.
- **USB:** vendor and product numeric IDs, generic manufacturer/product labels, USB bus position and reported speed. USB serial numbers are deliberately omitted.
- **Graphics:** DRM card/render node inventory; the separate NVIDIA management query also reports GPU name, free/total VRAM and driver when `nvidia-smi` succeeds. No CUDA/ROCm/oneAPI inference test is run.
- **Accelerators/NPU candidates:** entries in `/sys/class/accel` and PCI processing accelerators. Driver visibility does not prove an NPU is usable by a model runtime. Some NPUs won't be detected when the kernel has no supported driver or sysfs interface.
- **Other Linux classes:** sample/count of block devices, V4L cameras, sound, Bluetooth, TTY, and hardware monitor entries.

Individual classes are capped (32–256 entries) to prevent large or malicious device trees from exhausting a Raspberry Pi. Hardware is refreshed on demand; an internal 15-second cache prevents unnecessary driver queries. Never interpret `0 visible` as proof no hardware is physically connected.

## Management versus assessment interfaces

The Hardware workspace assigns optional **Management**, **Assessment** or **Reserved** labels to network interfaces for the current authenticated FOXWORX operator. Saved roles survive process restarts in the existing owner-scoped SQLite store. Another operator does not inherit these labels.

- Loopback and interfaces carrying a Linux kernel default route are automatically **protected Management**; their labels cannot be changed to Assessment or Reserved through FOXWORX.
- A newly discovered nonmanagement interface starts as **Unassigned**. A trusted operator can choose Assessment or another role; no OS routes are changed and no commands are executed.
- If an Assessment interface becomes a default route after its role was saved, FOXWORX automatically considers it protected, overriding the saved role. If a device changes identity, its old assignment is ignored.
- Default-route protection is a heuristic, not definitive recognition of every interface used by SSH or Cloudflare. Policy routing, site-to-site tunnels, container bridges and custom network namespaces may require a separate **system administrator** to verify management pathways. Operators should keep a distinct, physically reliable management interface.
- Neither labels nor guided binding implement egress filtering, network namespaces, VLAN separation, firewall rules or traffic containment. Terminal and advanced managed jobs retain the underlying Linux account's ordinary privileges.

## Opt-in per-job interface selection (guided Curl only)

For the **Curl → guided HTTP headers, OPTIONS, status, or limited GET** profiles, FOXWORX now offers an **Optional outgoing interface** selection. It lists only interfaces the current operator assigned to Assessment and that are not protected.

If selected, FOXWORX adds `--interface if!<interface>` to the literal argument preview. The operator must still review and approve that exact command. The application rechecks interface identity, assessment role and protected status just before it starts the managed job. The request is rejected if the interface vanished, is down, was reassigned, or became a default route.

**Limitations:** `curl --interface if!name` requires a compatible libcurl version and Linux socket binding permissions. Some hosts need additional capabilities or routes; FOXWORX does not grant them. Resolver queries, proxies, routing policies and separate subprocesses may use other paths. Interface binding alone never guarantees assessment traffic cannot leave a different interface. Review the actual traffic and test on a network you own or have express permission to assess.

Nmap, wireless utilities, registered adapters, autonomous Rabbit Hole jobs and raw terminal commands **do not** silently inherit the role or get auto-bound to interfaces. They require independent device-specific setup and approvals. There are no automatic WLAN mode switches or injection tests.

## AI and investigation history

Copilot offers a read-only `inspect_hardware` tool and can tell the operator which drivers and interfaces Linux reports. Rabbit Hole receives a small hardware summary during planning, but its root-owned adapter policy remains the only source of autonomous command permissions. Codex Agent may access Linux devices visible to its normal OS account through its own runtime; hardware labels do not constrain Codex, and they are not a sandbox.

Guided Curl jobs that explicitly use an assessment interface save the interface name alongside their command and approval metadata; execution history therefore shows which interface was requested. This is a **requested binding**, not proof of packet-level egress. The Investigation Graph continues to show those jobs; full GPU/USB device-to-operation topology edges are not yet built.

## Hardware checks on the actual Kali host

After installing v3.2, compare Hardware with these **read-only** native system tools:

```bash
ip -br link
ip route show default
ip -6 route show default
iw dev
lsusb
lspci -nnk
ls -l /sys/class/accel /sys/class/drm 2>/dev/null
nvidia-smi
```

If `iw` is missing, install/configure the appropriate Linux package from a separate administrator account. A Wi-Fi adapter can appear in USB inventory without creating a WLAN interface when its driver or firmware is missing. An adapter supporting monitor mode may still not support injection. NPU vendor SDKs and separate compute tests may be needed to verify inference capabilities.

## Security boundaries

The hardware API is authenticated; role changes are CSRF-protected and audited. Other than the operator's per-interface labels, the inventory performs no device writes. Fields are text-escaped in the browser and source text from devices should be treated as untrusted metadata. No MAC addresses, interface IP addresses, USB serials or NVIDIA UUIDs are returned. The app service is non-root. FOXWORX v3.2 is not a PCI/USB device security auditor and should not replace Linux access control or network segmentation.
