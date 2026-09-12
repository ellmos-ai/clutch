"""Automated Metadata & Manifest Parity Test Suite for ellmos-ai/clutch."""
from pathlib import Path
import re

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_core_documentation_files_exist():
    """Verify that all core documentation, license, security, and discoverability files exist."""
    required_files = [
        "README.md",
        "README_de.md",
        "SECURITY.md",
        "LICENSE",
        "CHANGELOG.md",
        "llms.txt",
        "pyproject.toml",
    ]
    for filename in required_files:
        filepath = REPO_ROOT / filename
        assert filepath.is_file(), f"Missing required file: {filename}"
        assert filepath.stat().st_size > 0, f"File is empty: {filename}"


def test_version_consistency():
    """Verify that version numbers across pyproject.toml, clutch/__init__.py, and llms.txt match."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    init_text = (REPO_ROOT / "clutch" / "__init__.py").read_text(encoding="utf-8")
    llms_text = (REPO_ROOT / "llms.txt").read_text(encoding="utf-8")

    m_pyproject = re.search(r'version\s*=\s*"([^"]+)"', pyproject_text)
    assert m_pyproject, "Version missing in pyproject.toml"
    version_pyproject = m_pyproject.group(1)

    m_init = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert m_init, "Version missing in clutch/__init__.py"
    version_init = m_init.group(1)

    assert version_pyproject == version_init, f"Version mismatch: pyproject={version_pyproject} vs init={version_init}"
    assert f"v{version_pyproject}" in llms_text or version_pyproject in llms_text, "Version mismatch in llms.txt"


def test_llms_txt_structure_and_timestamp():
    """Verify that llms.txt contains the canonical structure and a recent timestamp."""
    llms_text = (REPO_ROOT / "llms.txt").read_text(encoding="utf-8")

    assert "Last-checked: 2026-09-12" in llms_text, "llms.txt Last-checked timestamp should be 2026-09-12"
    assert "404" in llms_text, "llms.txt should report 404 passing unit tests"
    assert "## Audience" in llms_text, "llms.txt missing Audience section"
    assert "## Search Phrases" in llms_text, "llms.txt missing Search Phrases section"
    assert "## Docs" in llms_text, "llms.txt missing Docs section"
    assert "Core Governance & Runtime Invariants" in llms_text, "llms.txt missing Governance Invariants section"


def test_security_and_ecosystem_sections():
    """Verify that SECURITY.md is bilingual and READMEs contain ecosystem matrix."""
    sec_text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Deutsch" in sec_text and "## English" in sec_text, "SECURITY.md must be bilingual"
    assert "Ecosystem & Sibling Tools" in readme_en, "README.md missing Ecosystem matrix"
    assert "Verwandte Tools & Ökosystem" in readme_de, "README_de.md missing Ecosystem matrix"
    assert "open-bricks" in readme_en and "open-bricks" in readme_de, "Ecosystem umbrella missing"
    assert "agent-ops-stack" in readme_en and "convergence-reconciler" in readme_en, "Missing partner tools"


def test_github_actions_workflow_ci_matrix_and_lint():
    """Verify that GitHub Actions CI workflow tests across Python 3.10-3.13 and includes ruff linting."""
    ci_file = REPO_ROOT / ".github" / "workflows" / "ci.yml"
    assert ci_file.is_file(), "CI workflow .github/workflows/ci.yml missing"
    ci_text = ci_file.read_text(encoding="utf-8")

    assert 'os: [ubuntu-latest, windows-latest, macos-latest]' in ci_text, "CI matrix must cover multi-OS"
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13"]' in ci_text, "CI matrix must cover Python 3.10 through 3.13"
    assert "ruff check ." in ci_text, "CI workflow must include automated ruff check linting step"
    assert "cancel-in-progress: true" in ci_text, "CI workflow must include concurrency cancel-in-progress"


def test_pyproject_configuration_and_classifiers():
    """Verify pyproject.toml PEP 621 metadata, Python 3.13 classifier, and ruff lint configuration."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "Programming Language :: Python :: 3.13" in pyproject_text, "pyproject.toml must include Python 3.13 classifier"
    assert "[tool.ruff]" in pyproject_text, "pyproject.toml must include [tool.ruff] section"
    assert "[tool.ruff.lint]" in pyproject_text, "pyproject.toml must include [tool.ruff.lint] section"
    assert "Parent Organization" in pyproject_text, "pyproject.toml missing Parent Organization url"
    assert "Umbrella Ecosystem" in pyproject_text, "pyproject.toml missing Umbrella Ecosystem url"


def test_readme_google_model_table_matches_catalog():
    """Verify that maintained READMEs document the current preferred Google Flash gear."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "Gemini 3.7 Flash (preferred)" in readme_en, "README.md must list Gemini 3.7 Flash as preferred"
    assert "Gemini 3.5 Flash fallback" in readme_en, "README.md must keep Gemini 3.5 Flash as fallback"
    assert "Gemini 3.7 Flash (bevorzugt)" in readme_de, "README_de.md must list Gemini 3.7 Flash as preferred"
    assert "Gemini 3.5 Flash als Fallback" in readme_de, "README_de.md must keep Gemini 3.5 Flash as fallback"
    assert "Execution selectors and provider evidence" in readme_en
    assert "Ausführungsselektoren und Provider-Evidenz" in readme_de


def test_security_contact_email():
    """Verify that SECURITY.md contains dedicated security contact email addresses and SLA."""
    sec_text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "security@ellmos.ai" in sec_text, "SECURITY.md must provide security@ellmos.ai"
    assert "support@lukasgeiger.com" in sec_text, "SECURITY.md must provide support@lukasgeiger.com"
    assert "lukas@open-bricks.org" in sec_text, "SECURITY.md must provide lukas@open-bricks.org"
    assert "48 hours" in sec_text or "48 Stunden" in sec_text, "SECURITY.md must provide 48h response SLA"


def test_quick_navigation_anchors_parity():
    """Verify that both READMEs contain the 14-point Quick Navigation anchor list."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Quick Navigation" in readme_en, "README.md missing Quick Navigation"
    assert "## Schnellnavigation" in readme_de, "README_de.md missing Schnellnavigation"
    assert "14. [Security Policy & Liability]" in readme_en or "14. [Security" in readme_en
    assert "14. [Sicherheitsrichtlinie & Haftung]" in readme_de or "14. [Sicherheitsrichtlinie" in readme_de


def test_dual_mermaid_diagrams_parity():
    """Verify that both READMEs contain dual Mermaid diagrams: flowchart TD and sequenceDiagram."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "flowchart TD" in readme_en, "README.md missing architecture flowchart TD diagram"
    assert "sequenceDiagram" in readme_en, "README.md missing lifecycle sequenceDiagram"
    assert "flowchart TD" in readme_de, "README_de.md missing architecture flowchart TD diagram"
    assert "sequenceDiagram" in readme_de, "README_de.md missing lifecycle sequenceDiagram"


def test_governance_invariants_table_parity():
    """Verify that both READMEs document the 10 Governance & Runtime Invariants."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Governance & Runtime Invariants" in readme_en, "README.md missing Governance & Runtime Invariants"
    assert "## Governance- & Laufzeit-Invarianten" in readme_de, "README_de.md missing Governance- & Laufzeit-Invarianten"
    assert "Provider Agnosticism & Zero Lock-in" in readme_en, "README.md missing Invariant 1"
    assert "Provider-Agnostizismus & Zero Lock-in" in readme_de, "README_de.md missing Invariante 1"


def test_gitignore_hygiene_patterns():
    """Verify that .gitignore contains standard sync conflict, lock, and cache exclusions."""
    gi_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    required_patterns = [
        "*-conflict-*",
        "*.sync-conflict-*",
        "*.conflict",
        "*-CONFLIT-*",
        "*.sync-temp-*",
        "LOCK",
        "LOCK.*",
        "*.lock",
        "LOCK*.txt",
        "LOCK.permissions.json",
        ".pytest_cache/",
        ".ruff_cache/",
        ".coverage",
        "coverage/",
        "htmlcov/",
        "wheelhouse/",
        ".wheel-smoke/",
        "*.tmp",
        "*.bak",
        "*.log",
    ]
    for pattern in required_patterns:
        assert pattern in gi_text, f".gitignore missing pattern: {pattern}"


def test_pytest_configuration_and_flags():
    """Verify that pyproject.toml configures pytest with standardized flags."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.pytest.ini_options]" in pyproject_text, "Missing [tool.pytest.ini_options] in pyproject.toml"
    assert 'addopts = "-ra -v"' in pyproject_text, "pytest addopts should be configured with -ra -v"
    assert 'testpaths = ["tests"]' in pyproject_text, "pytest testpaths should specify tests"


def test_security_policy_slas_and_contacts():
    """Verify that SECURITY.md enforces SLA response times and umbrella contacts."""
    sec_text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "security@open-bricks.org" in sec_text, "SECURITY.md missing security@open-bricks.org"
    assert "48 hours" in sec_text and "48 Stunden" in sec_text, "SECURITY.md missing 48h SLA in both languages"
    assert "5 business days" in sec_text and "5 Werktagen" in sec_text, "SECURITY.md missing 5-day triage SLA in both languages"


def test_ci_workflow_hardening():
    """Verify that CI workflow enforces bytecode compilation, concurrency, and multi-OS matrix."""
    ci_text = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "cancel-in-progress: true" in ci_text, "CI missing concurrency cancel-in-progress"
    assert "python -m compileall -q clutch tests" in ci_text, "CI missing python bytecode compilation gate"
    assert "python -m pytest -ra -v" in ci_text, "CI missing pytest -ra -v execution"
    assert "os: [ubuntu-latest, windows-latest, macos-latest]" in ci_text, "CI missing multi-OS runner matrix"


def test_changelog_release_entry():
    """Verify that CHANGELOG.md documents the latest 0.6.2 release entry."""
    changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.6.2] - 2026-09-09" in changelog_text, "CHANGELOG.md missing [0.6.2] release header"


def test_readme_badges_parity():
    """Verify that README.md and README_de.md maintain synchronized badges."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "badge/Version-0.6.2-" in readme_en, "README.md missing Version 0.6.2 badge"
    assert "badge/Version-0.6.2-" in readme_de, "README_de.md missing Version 0.6.2 badge"
    assert "Security%20SLA-48h" in readme_en, "README.md missing Security SLA badge"
    assert "Sicherheits--SLA-48h" in readme_de, "README_de.md missing Sicherheits-SLA badge"
    assert "code%20style-ruff" in readme_en, "README.md missing ruff code style badge"
    assert "code%20style-ruff" in readme_de, "README_de.md missing ruff code style badge"
