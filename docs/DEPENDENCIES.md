# Dependencies, provenance and references

## Python

requirements.txt pins architecture-neutral Python direct dependencies to the installed versions used by the release tests. requirements-ai.txt pins LiteLLM 1.104.0 for cloud/self-hosted provider normalization; it is installed by default, or can be skipped with --without-ai. requirements-dev.txt adds test dependencies. Python 3.11+ is the intended target; the actual build test interpreter is recorded in verification/TEST-REPORT.md. The installer creates a venv rather than altering Kali's system Python packages.

A new Internet-backed installation, LiteLLM dependency resolution and ARM64 and x86-64 target-side wheel verification were not possible in the build container (the package index could not be reached). The included observed-version manifest records what was tested, not proof that every dependency has been freshly checked against current vulnerability advisories. Validate dependency resolution and perform your normal vulnerability review on **each** target host. No claim of a completed dependency CVE audit is made.

No Kali executables, driver blobs, wordlists, licensed scanners, operating-system image or model weights are bundled. Install those from their appropriate official distributions, subject to licenses and authorization.

## Browser assets

The app uses local xterm/FitAddon JavaScript and CSS, with no production CDN. Outbound asset download was unavailable while building. The unmodified standalone ESM bundle was taken from the already installed Playwright trace viewer distribution. Its package.json identified `1.57.0-beta-1764944708000`; Python distribution metadata reported Playwright 1.57.0. These are reported as observed rather than pretending a new upstream xterm release was fetched.

The original browser bundle name is `xtermModule-CsJ4vdCR.js`; the stylesheet is `xtermModule.DYP7pi_n.css`. Provenance and SHA-256 values are in static/vendor/manifest.json. Original Playwright LICENSE and ThirdPartyNotices are retained there; xterm's MIT notice is retained in the CSS and notices. Original FoxWorx-owned code is governed by the top-level proprietary LICENSE; bundled third-party components retain their own licenses. The vendored bundle is not claimed to be the latest xterm version. Review/refresh it through a tested build process before higher-assurance deployment.

`bash scripts/doctor.sh` verifies hashes of all four bundled vendor files against the manifest. This detects accidental changes against the included manifest, not a signed supply-chain attestation.

## Host-specific native libraries and drivers

The Python/FastAPI app has no direct CUDA/NVIDIA requirement and uses the same vendored browser assets on ARM64 and x86-64. Python dependencies are installed separately into each host's virtual environment. Native Kali tools are discovered at runtime and may differ by CPU architecture, installed packages, kernel, permissions and hardware.

For GPU workstations, `nvidia-smi` is an optional system diagnostic, not bundled or installed by FOXWORX. Ollama/vLLM GPU inference is an **independently managed service**, with distinct driver/runtime dependencies and version compatibility. See [PLATFORMS.md](PLATFORMS.md) for practical safety boundaries and source documentation.

## Primary references checked for this design

- Cloudflare Access JWT validation: https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/
- Cloudflare WebSocket behavior: https://developers.cloudflare.com/network/websockets/
- Cloudflare Tunnel documentation: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/
- OpenAI reasoning model context/budget guidance: https://developers.openai.com/api/docs/guides/reasoning
- OpenAI Responses function calling: https://developers.openai.com/api/docs/guides/function-calling
- Kali Raspberry Pi 4 documentation: https://www.kali.org/docs/arm/raspberry-pi-4/
- Kali metapackages: https://www.kali.org/docs/general-use/metapackages/
- xterm security guidance: https://xtermjs.org/docs/guides/security/

These sources describe components and security considerations; they do not certify this application, authorize any engagement, or establish tool compatibility on your particular Pi. Use the vendors' current installation/policy pages when configuring your own accounts.

- LiteLLM providers and SDK: https://docs.litellm.ai/docs/providers / https://docs.litellm.ai/docs/ . This project pins 1.104.0, but actual dependency resolution and provider requests **must** be verified from the Kali target before production use.
