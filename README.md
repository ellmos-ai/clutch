> This short entry point follows the repository’s documentation-archiving rule. Direct predecessor: the detailed `README.md` at base commit `67c5b72fd2ea6d1e91e47f363d8ab9f951b9fd44`, preserved with corrected current claims in [docs/archive/README-2026-10-12.md](docs/archive/README-2026-10-12.md).

<p align="center">
  <img src="docs/assets/banner.svg" alt="clutch banner" width="100%">
</p>

[English](README.md) · [Deutsch](README_de.md) · [Español](README_es.md) · [简体中文](README_zh-Hans.md) · [日本語](README_ja.md) · [Русский](README_ru.md)

# clutch

![Version 0.6.3](https://img.shields.io/badge/version-0.6.3-blue)
[![CI](https://github.com/ellmos-ai/clutch/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/ellmos-ai/clutch/actions/workflows/ci.yml)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
[![MIT License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

**clutch** is a Python library and CLI for routing tasks across configured model providers. It also offers an optional FastAPI web interface intended for local use. The version remains 0.6.3.

## Install and start

```bash
git clone https://github.com/ellmos-ai/clutch.git
cd clutch
python -m pip install -e .
clutch --help
```

For the optional web dependencies, install `python -m pip install -e ".[web]"`. Development and test setup is in [CONTRIBUTING.md](CONTRIBUTING.md).

## Runtime and data boundaries

Configuration, credentials, and history are stored locally by default, though individual commands may accept other paths. Requests and context sent to a remote provider leave the local machine and are subject to that provider’s terms and account settings. Saved API keys are unencrypted text; POSIX mode 0600 is best effort where supported. Child CLI processes inherit the invoking account’s permissions and environment. Local budget zones are thresholds or estimates, not provider billing caps. The optional web interface is intended for local use; clutch does not provide general egress blocking, process sandboxing, or public-hosting certification. The current HTTP app serves the root HTML page but has no routes for the local static assets it references, so complete browser UI behavior is not verified.

See [SECURITY.md](SECURITY.md), [THIRD_PARTY_LICENSES.md](THIRD_PARTY_LICENSES.md), [LICENSE](LICENSE), and machine-readable [llms.txt](llms.txt). Related tools are separate repositories; links in the detailed archive describe their observed relationship and do not imply integration.

## Detailed guide and preserved navigation

The prior 18-section guide remains available in [the dated archive](docs/archive/README-2026-10-12.md). Its original section links are kept here:

1. <a id="1-features"></a><a id="features"></a>[Features & Highlights](docs/archive/README-2026-10-12.md#1-features)
2. <a id="2-architecture"></a><a id="architecture"></a>[Architecture & Metaphor Mapping](docs/archive/README-2026-10-12.md#2-architecture)
3. <a id="3-target-personas--discoverability"></a><a id="target-personas--discoverability"></a>[Typical Use Contexts](docs/archive/README-2026-10-12.md#3-target-personas--discoverability)
4. <a id="4-comparative-matrix-vs-alternatives"></a><a id="comparative-matrix-vs-alternatives"></a>[Usage Modes & Boundaries](docs/archive/README-2026-10-12.md#4-comparative-matrix-vs-alternatives)
5. <a id="5-dual-mermaid-diagrams"></a><a id="dual-mermaid-diagrams"></a>[Dual Mermaid Diagrams](docs/archive/README-2026-10-12.md#5-dual-mermaid-diagrams)
6. <a id="6-governance--runtime-invariants"></a><a id="governance--runtime-invariants"></a>[Runtime Scope & Data Boundaries](docs/archive/README-2026-10-12.md#6-governance--runtime-invariants)
7. <a id="7-road-types"></a><a id="road-types"></a>[Road Types & Task Classification](docs/archive/README-2026-10-12.md#7-road-types)
8. <a id="8-installation"></a><a id="installation"></a>[Installation & Requirements](docs/archive/README-2026-10-12.md#8-installation)
9. <a id="9-quick-start"></a><a id="quick-start"></a>[Quick Start](docs/archive/README-2026-10-12.md#9-quick-start)
10. <a id="10-command-line-interface"></a><a id="command-line-interface"></a>[Command-Line Interface](docs/archive/README-2026-10-12.md#10-command-line-interface)
11. <a id="11-api-keys--credentials"></a><a id="api-keys--credentials"></a>[API Keys & Credentials](docs/archive/README-2026-10-12.md#11-api-keys--credentials)
12. <a id="12-configuration"></a><a id="configuration"></a>[Configuration & User Overlays](docs/archive/README-2026-10-12.md#12-configuration)
13. <a id="13-supported-providers"></a><a id="supported-providers"></a>[Supported Providers & Model Tiers](docs/archive/README-2026-10-12.md#13-supported-providers)
14. <a id="14-execution-patterns"></a><a id="execution-patterns"></a>[Execution Patterns](docs/archive/README-2026-10-12.md#14-execution-patterns)
15. <a id="15-ecosystem--sibling-tools"></a><a id="ecosystem--sibling-tools"></a>[Ecosystem & Sibling Tools](docs/archive/README-2026-10-12.md#15-ecosystem--sibling-tools)
16. <a id="16-third-party-licenses--transparency"></a><a id="third-party-licenses--transparency"></a>[Declared Dependencies & License Scope](docs/archive/README-2026-10-12.md#16-third-party-licenses--transparency)
17. <a id="17-security-policy--liability"></a><a id="security-policy--liability"></a>[Security Policy & Legal Scope](docs/archive/README-2026-10-12.md#17-security-policy--liability)
18. <a id="18-verification--test-suite"></a><a id="verification--test-suite"></a>[Checks & Test Commands](docs/archive/README-2026-10-12.md#18-verification--test-suite)
