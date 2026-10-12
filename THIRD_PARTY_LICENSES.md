# Direct Dependencies and License References

Project source metadata identifies clutch-router version 0.6.3 and the project license in [LICENSE](LICENSE). The tables below mirror direct package declarations in pyproject.toml; they do not enumerate transitive packages, inspect built artifacts, or provide a legal compatibility assessment.

## Runtime dependencies

| Package | Declared requirement | Upstream license file |
|---|---|---|
| anthropic | >=0.40.0 | [anthropic-sdk-python/LICENSE](https://github.com/anthropics/anthropic-sdk-python/blob/main/LICENSE) |
| google-genai | >=1.0.0 | [python-genai/LICENSE](https://github.com/googleapis/python-genai/blob/main/LICENSE) |
| requests | >=2.31.0 | [requests/LICENSE](https://github.com/psf/requests/blob/main/LICENSE) |

## Optional web dependencies

These packages are installed with the web extra.

| Package | Declared requirement | Upstream license file |
|---|---|---|
| fastapi | >=0.110 | [fastapi/LICENSE](https://github.com/fastapi/fastapi/blob/master/LICENSE) |
| uvicorn | >=0.27 | [uvicorn/LICENSE.md](https://github.com/Kludex/uvicorn/blob/main/LICENSE.md) |
| python-multipart | >=0.0.9 | [python-multipart/LICENSE.txt](https://github.com/Kludex/python-multipart/blob/main/LICENSE.txt) |

## Test and build tools

The test extra, build-system declaration, and local build instructions add development/build tools. These are not runtime requirements of the installed application.

| Package | Declared scope | Upstream license file |
|---|---|---|
| pytest | test extra | [pytest/LICENSE](https://github.com/pytest-dev/pytest/blob/main/LICENSE) |
| ruff | test extra | [ruff/LICENSE](https://github.com/astral-sh/ruff/blob/main/LICENSE) |
| tomli | test extra on Python <3.11 | [tomli/LICENSE](https://github.com/hukkin/tomli/blob/master/LICENSE) |
| build | documented source-build tool | [build/LICENSE](https://github.com/pypa/build/blob/main/LICENSE) |
| setuptools | PEP 517 build backend | [setuptools/LICENSE](https://github.com/pypa/setuptools/blob/main/LICENSE) |
| wheel | PEP 517 build tool | [wheel/LICENSE.txt](https://github.com/pypa/wheel/blob/main/LICENSE.txt) |

For an assessment of a particular installation or distribution, resolve and review its exact dependency artifacts and their notices. This document is a source-level direct-dependency reference, not a complete software bill of materials or license audit.
