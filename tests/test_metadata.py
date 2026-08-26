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

    assert "Last-checked: 2026-08-26" in llms_text, "llms.txt Last-checked timestamp should be 2026-08-26"
    assert "355" in llms_text, "llms.txt should report 355 passing unit tests"
    assert "## Audience" in llms_text, "llms.txt missing Audience section"
    assert "## Search Phrases" in llms_text, "llms.txt missing Search Phrases section"
    assert "## Docs" in llms_text, "llms.txt missing Docs section"


def test_security_and_ecosystem_sections():
    """Verify that SECURITY.md is bilingual and READMEs contain ecosystem matrix."""
    sec_text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Deutsch" in sec_text and "## English" in sec_text, "SECURITY.md must be bilingual"
    assert "Ecosystem & Sibling Tools" in readme_en, "README.md missing Ecosystem matrix"
    assert "Verwandte Tools & Ökosystem" in readme_de, "README_de.md missing Ecosystem matrix"
    assert "open-bricks" in readme_en and "open-bricks" in readme_de, "Ecosystem umbrella missing"


def test_github_actions_workflow_ci_matrix_and_lint():
    """Verify that GitHub Actions CI workflow tests across Python 3.10-3.13 and includes ruff linting."""
    ci_file = REPO_ROOT / ".github" / "workflows" / "tests.yml"
    assert ci_file.is_file(), "CI workflow .github/workflows/tests.yml missing"
    ci_text = ci_file.read_text(encoding="utf-8")

    assert 'python-version: ["3.10", "3.11", "3.12", "3.13"]' in ci_text, "CI matrix must cover Python 3.10 through 3.13"
    assert "ruff check ." in ci_text, "CI workflow must include automated ruff check linting step"


def test_pyproject_configuration_and_classifiers():
    """Verify pyproject.toml PEP 621 metadata, Python 3.13 classifier, and ruff lint configuration."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "Programming Language :: Python :: 3.13" in pyproject_text, "pyproject.toml must include Python 3.13 classifier"
    assert "[tool.ruff]" in pyproject_text, "pyproject.toml must include [tool.ruff] section"
    assert "[tool.ruff.lint]" in pyproject_text, "pyproject.toml must include [tool.ruff.lint] section"


def test_readme_google_model_table_matches_catalog():
    """Verify that maintained READMEs document the current preferred Google Flash gear."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "Gemini 3.7 Flash (preferred)" in readme_en, "README.md must list Gemini 3.7 Flash as preferred"
    assert "Gemini 3.5 Flash fallback" in readme_en, "README.md must keep Gemini 3.5 Flash as fallback"
    assert "Gemini 3.7 Flash (bevorzugt)" in readme_de, "README_de.md must list Gemini 3.7 Flash as preferred"
    assert "Gemini 3.5 Flash als Fallback" in readme_de, "README_de.md must keep Gemini 3.5 Flash as fallback"


def test_security_contact_email():
    """Verify that SECURITY.md contains dedicated security contact email addresses."""
    sec_text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "security@ellmos.ai" in sec_text, "SECURITY.md must provide security@ellmos.ai"
    assert "support@lukasgeiger.com" in sec_text, "SECURITY.md must provide support@lukasgeiger.com"
