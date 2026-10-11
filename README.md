# FoxWorx DreadFoxHacker — Kali Workbench v3.0

> **PROPRIETARY SOFTWARE — Copyright © 2026 FoxWorx LLC. All rights reserved.**  
> Public visibility is for inspection and demonstration. Use, installation, modification, redistribution, and commercial exploitation require FoxWorx LLC authorization under the [LICENSE](LICENSE). Third-party components retain their own notices.

DreadFoxHacker is a browser-based, AI-assisted Kali Linux workstation developed for **authorized security testing** by FoxWorx LLC.

## Platform capabilities

- Real interactive Kali terminal with reconnectable sessions.
- Searchable discovery of executables installed on the host and a manual toolbox.
- OpenAI, Anthropic, Google Gemini, xAI, DeepSeek, Mistral, Ollama, LM Studio, vLLM, and compatible inference endpoints.
- Tutor and approval-based Copilot modes.
- Rabbit Hole investigation mode using administrator-approved, bounded CLI adapters.
- Tool Intelligence with local documentation and version-specific saved knowledge.
- Investigation Graph with execution relationships, selectable evidence-backed nodes, annotations, and JSON/SVG/PNG exports.
- Engagements, evidence capture, job histories, and the optional DreadFox digital companion.
- Designed for Kali Linux on Raspberry Pi ARM64 and x86-64 workstations, with Cloudflare Access and Tunnel support.

## Release and installation

**Publication status:** The proprietary license and project overview are published. The full v3.0 source distribution, installation guide, user guide, scripts, and tests are being transferred separately; they are **not yet hosted in this repository**.

The prepared distribution includes `docs/INSTALL.md`, `docs/OPERATOR-GUIDE.md`, `docs/SECURITY.md`, `docs/INVESTIGATION-GRAPH.md`, platform guides, policy examples, installer scripts, regression tests, and bundled third-party notices.

For an authorized operator, the packaged install procedure begins with:

```bash
bash scripts/install.sh --preflight
bash scripts/install.sh
bash scripts/doctor.sh
```

Run under a dedicated non-root account. Do **not** expose local authentication mode through a public tunnel. Administrator policies are required for Rabbit Hole autonomy and do not constitute a network sandbox.

## Ownership and security

Original FOXWORX materials owned or licensable by FoxWorx LLC are covered by the proprietary [LICENSE](LICENSE). Vendored components and dependencies retain their separate licenses. Testing is permitted only against explicitly authorized systems and within applicable program rules.

This is a development release requiring acceptance testing on the target Kali host, AI provider, and Cloudflare deployment. No warranty is provided.
