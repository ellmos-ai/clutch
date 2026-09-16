# Third-Party Licenses & Software Inventory

**Project:** `clutch` (`clutch-router`)  
**License:** [MIT License](LICENSE)  
**Audit Date:** 2026-09-16  
**Repository:** [ellmos-ai/clutch](https://github.com/ellmos-ai/clutch)  
**Umbrella Collective:** [open-bricks](https://github.com/open-bricks)  

---

## Runtime Architecture & Dependencies

`clutch` is engineered as a **provider-neutral, local-first, zero-egress** model routing and LLM orchestration engine. It analyzes task complexity, selects optimal model gears (G1–G5), manages financial/token budgets, enforces circuit breakers, and learns through experience.

### Mandatory Runtime Dependencies

`clutch` maintains a lean runtime footprint. All mandatory external dependencies are governed by permissive, business-friendly open-source licenses:

| Package | Version Spec | License | Type | Purpose |
|---|---|---|---|---|
| [anthropic](https://github.com/anthropics/anthropic-sdk-python) | `>=0.40.0` | MIT | External | Official Anthropic API client for Claude models |
| [google-genai](https://github.com/googleapis/python-genai) | `>=1.0.0` | Apache-2.0 | External | Official Google GenAI SDK for Gemini models |
| [requests](https://github.com/psf/requests) | `>=2.31.0` | Apache-2.0 | External | HTTP client for Ollama, Moonshot/Kimi, and OpenAI-compatible endpoints |
| *Python Standard Library* | `>=3.10` | PSF License | Built-in | Core runtime: `argparse`, `asyncio`, `dataclasses`, `datetime`, `hashlib`, `json`, `os`, `pathlib`, `re`, `shutil`, `sqlite3`, `subprocess`, `sys`, `time`, `typing` |

All network calls are strictly restricted to user-configured LLM provider endpoints (Anthropic, Google, Ollama, Kimi, or local/remote OpenAI-compatible APIs). Zero third-party telemetry, tracking, or unexpected egress exists.

### Optional Web UI Dependencies (`[web]`)

For users opting into the graphical web interface (`clutch serve --web`), the following optional dependencies are used:

| Package | Version Spec | License | Scope | Purpose |
|---|---|---|---|---|
| [fastapi](https://github.com/fastapi/fastapi) | `>=0.110` | MIT | `[web]` | Modern, fast web framework for the optional local chat interface |
| [uvicorn](https://github.com/encode/uvicorn) | `>=0.27` | BSD-3-Clause | `[web]` | Lightning-fast ASGI web server for loopback serving |
| [python-multipart](https://github.com/Kludex/python-multipart) | `>=0.0.9` | Apache-2.0 | `[web]` | Multipart form data parser for file/image uploads |

### Development & Test Tooling

The following tools are utilized exclusively during development, code quality audits, and automated test execution:

| Package / Tool | Version Spec | License | Scope | Purpose |
|---|---|---|---|---|
| [pytest](https://pytest.org/) | `>=7.0` | MIT | `[dev]` | Automated unit, contract, and regression test runner |
| [ruff](https://github.com/astral-sh/ruff) | `>=0.6` | MIT OR Apache-2.0 | `[dev]` | High-performance Python linter and code style enforcement |
| [setuptools](https://github.com/pypa/setuptools) | `>=68.0` | MIT | `[build-system]` | Standard packaging and build backend |
| [wheel](https://github.com/pypa/wheel) | `>=0.40` | MIT | `[build-system]` | Built-package distribution format standard |

---

## Zero-Copyleft Guarantee & Unprivileged Execution

- **Zero-Copyleft Guarantee:** All runtime libraries, optional extensions, and development tools are governed exclusively by permissive open-source licenses (MIT, Apache-2.0, BSD-3-Clause, PSF). The codebase contains **zero** GPL, AGPL, or viral copyleft dependencies.
- **Unprivileged User-Mode Operation (`RunAsInvoker`):** All components—including the CLI commands, background tasks, SQLite databases, and optional FastAPI web server—execute strictly within unprivileged user space. No administrative rights, root elevation, or UAC prompts are ever required.

---

## Governance & Runtime Invariants

`clutch` adheres to ten foundational governance and runtime invariants:

| Invariant | Category | Description |
|---|---|---|
| `INV-LOCAL-01` | Provider Agnosticism & Zero Lock-in | Seamless hot-swapping across Anthropic, Google Gemini, OpenAI, Ollama, and Kimi without vendor lock-in. |
| `INV-LOCAL-02` | 100% Local-First & Zero Egress | All routing decisions, session history, and metrics remain on local disk; zero tracking or telemetry egress. |
| `INV-UNPRIV-03` | Non-Elevation User Mode (`RunAsInvoker`) | All CLI commands, web apps, and background routines operate strictly in unprivileged user space. |
| `INV-CIRCUIT-04` | Fail-Closed Circuit Breakers | Persistent circuit breakers survive one-shot CLI processes and avoid hammering rate-limited providers. |
| `INV-OVERLAY-05` | Update-Safe User Overlays | User preferences, model exclusions, and aliases live in `~/.clutch/user_overrides.json` across package updates. |
| `INV-FALLBACK-06` | Dual-Alternative Ranked Fallbacks | Every routing decision provides a primary model plus two ranked alternatives for instantaneous failover. |
| `INV-BUDGET-07` | Two-Dimensional Telemetry & Budget | Combines financial USD consumption zones (`Tankuhr`) with real-time token throughput tracking. |
| `INV-PURPOSE-08` | Purpose & Vision Alignment | Vision and multimodal tasks are strictly routed to vision-capable models; code tasks match coding gears. |
| `INV-LEDGER-09` | Transactional SQLite Audit Ledger | All trips, execution records, chat sessions, and prompt library entries are safely stored in local ACID SQLite databases. |
| `INV-SLA-10` | Cross-Platform Multi-OS Parity & SLA | Identical behavior across Linux, Windows, and macOS with committed 48h security response SLA. |

---

## License Texts & Attribution

### MIT License (`clutch`, `anthropic`, `fastapi`, `pytest`, `setuptools`, `wheel`, `ruff`)

```
MIT License

Copyright (c) 2026 Lukas Geiger / ellmos-ai

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

### Apache License 2.0 (`google-genai`, `requests`, `python-multipart`, `ruff`)

```
Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

### BSD 3-Clause License (`uvicorn`)

```
Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

3. Neither the name of the copyright holder nor the names of its
   contributors may be used to endorse or promote products derived from
   this software without specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

### Python Software Foundation License (PSF) (Python Standard Library)

```
1. This LICENSE AGREEMENT is between the Python Software Foundation ("PSF"), and
   the Individual or Organization ("Licensee") accessing and otherwise using Python
   software in source or binary form and its associated documentation.

2. Subject to the terms and conditions of this License Agreement, PSF hereby
   grants Licensee a nonexclusive, royalty-free, world-wide license to reproduce,
   analyze, test, perform and/or display publicly, prepare derivative works, distribute,
   and otherwise use Python alone or in any derivative version, provided, however, that
   PSF's License Agreement and PSF's notice of copyright, i.e., "Copyright (c) 2001-2026
   Python Software Foundation; All Rights Reserved" are retained in Python alone or
   in any derivative version prepared by Licensee.
```
