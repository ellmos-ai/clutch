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
        "NOTICE",
        "CHANGELOG.md",
        "llms.txt",
        "pyproject.toml",
        "THIRD_PARTY_LICENSES.md",
        "THIRD_PARTY_LICENSES.txt",
        "MARKETING-LOG.txt",
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

    assert "Last-checked: 2026-09-28" in llms_text, "llms.txt Last-checked timestamp should be 2026-09-28"
    assert "416" in llms_text, "llms.txt should report 416+ passing unit tests"
    assert "## Audience" in llms_text, "llms.txt missing Audience section"
    assert "## Search Phrases" in llms_text, "llms.txt missing Search Phrases section"
    assert "## Docs" in llms_text, "llms.txt missing Docs section"
    assert "NOTICE" in llms_text, "llms.txt missing NOTICE link"
    assert "THIRD_PARTY_LICENSES.md" in llms_text, "llms.txt missing THIRD_PARTY_LICENSES.md link"
    assert "THIRD_PARTY_LICENSES.txt" in llms_text, "llms.txt missing THIRD_PARTY_LICENSES.txt link"
    assert "MARKETING-LOG.txt" in llms_text, "llms.txt missing MARKETING-LOG.txt link"
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
    """Verify that both READMEs contain the 18-point Quick Navigation anchor list."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "## Quick Navigation" in readme_en, "README.md missing Quick Navigation"
    assert "## Schnellnavigation" in readme_de, "README_de.md missing Schnellnavigation"
    assert "18. [Verification & Test Suite](#sec-18)" in readme_en
    assert "18. [Verifikation & Testsuite](#sec-18)" in readme_de
    for i in range(1, 19):
        assert f"\n{i}. [" in readme_en, f"README.md missing navigation item {i}"
        assert f"\n{i}. [" in readme_de, f"README_de.md missing navigation item {i}"
        sec_id = f"sec-{i:02d}"
        assert f"(#{sec_id})" in readme_en, f"README.md missing navigation anchor #{sec_id}"
        assert f"(#{sec_id})" in readme_de, f"README_de.md missing navigation anchor #{sec_id}"



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

    assert "Governance & Runtime Invariants" in readme_en, "README.md missing Governance & Runtime Invariants"
    assert "Governance- & Laufzeit-Invarianten" in readme_de, "README_de.md missing Governance- & Laufzeit-Invarianten"
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
    assert "-ra -v" in pyproject_text, "pytest addopts should include -ra -v"
    assert "--basetemp=.pytest_temp" in pyproject_text, "pytest addopts should include --basetemp=.pytest_temp"
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
    """Verify that CHANGELOG.md documents the latest 0.6.3 release entry."""
    changelog_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "## [0.6.3] - 2026-09-13" in changelog_text, "CHANGELOG.md missing [0.6.3] release header"


def test_readme_badges_parity():
    """Verify that README.md and README_de.md maintain synchronized badges."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "badge/Version-0.6.3-" in readme_en, "README.md missing Version 0.6.3 badge"
    assert "badge/Version-0.6.3-" in readme_de, "README_de.md missing Version 0.6.3 badge"
    assert "Pytest-416%20passed" in readme_en, "README.md missing current pytest badge"
    assert "Pytest-416%20bestanden" in readme_de, "README_de.md missing current pytest badge"
    assert "Attribution-NOTICE" in readme_en, "README.md missing NOTICE badge"
    assert "Attribution-NOTICE" in readme_de, "README_de.md missing NOTICE badge"
    assert "Level%201%20SBOM-Plain--Text" in readme_en, "README.md missing Level 1 SBOM badge"
    assert "Level%201%20SBOM-Plain--Text" in readme_de, "README_de.md missing Level 1 SBOM badge"
    assert "Verified-2026--09--28" in readme_en, "README.md missing Verified date badge"
    assert "Gepr%C3%BCft-2026--09--28" in readme_de, "README_de.md missing Geprüft date badge"
    assert "Security%20SLA-48h" in readme_en, "README.md missing Security SLA badge"
    assert "Sicherheits--SLA-48h" in readme_de, "README_de.md missing Sicherheits-SLA badge"
    assert "code%20style-ruff" in readme_en, "README.md missing ruff code style badge"
    assert "code%20style-ruff" in readme_de, "README_de.md missing ruff code style badge"
    assert "Third--Party%20Licenses-Audited" in readme_en, "README.md missing Third-Party Licenses badge"
    assert "Drittanbieter--Lizenzen-Gepr%C3%BCft" in readme_de, "README_de.md missing Drittanbieter-Lizenzen badge"
    assert "Marketing--Log-Active" in readme_en, "README.md missing Marketing Log badge"
    assert "Marketing--Log-Aktiv" in readme_de, "README_de.md missing Marketing Log badge"


def test_ci_workflow_job_timeouts():
    """Verify that CI workflows specify timeout-minutes on all jobs to prevent runaway runners."""
    workflows_dir = REPO_ROOT / ".github" / "workflows"
    for wf in ["ci.yml", "tests.yml", "publish.yml", "stale.yml", "welcome.yml"]:
        content = (workflows_dir / wf).read_text(encoding="utf-8")
        assert "timeout-minutes:" in content, f"Workflow {wf} missing timeout-minutes on jobs"


def test_onedrive_multihost_gitignore_patterns():
    """Verify that .gitignore blocks OneDrive sync conflict patterns and build caches."""
    gi_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    patterns = [
        "* (kopie)*",
        "* (copy)*",
        "*-ASUS.*",
        "*-LAPTOP.*",
        "*-WORKSTATION-LG.*",
        "*.orig",
        "*.rej",
        ".tox/",
        ".turbo/",
        ".mypy_cache/",
    ]
    for pattern in patterns:
        assert pattern in gi_text, f".gitignore missing multi-host pattern: {pattern}"


def test_frontier_ollama_models_in_catalog():
    """Verify that new frontier Ollama Cloud models exist in getriebe.json catalog."""
    import json
    getriebe_path = REPO_ROOT / "clutch" / "config" / "getriebe.json"
    data = json.loads(getriebe_path.read_text(encoding="utf-8"))
    gaenge = data.get("gaenge", {})
    assert "ollama-kimi-k3" in gaenge, "Missing ollama-kimi-k3 in getriebe.json"
    assert "ollama-glm-5.3" in gaenge, "Missing ollama-glm-5.3 in getriebe.json"
    assert gaenge["ollama-kimi-k3"]["model_id"] == "kimi-k3:cloud"
    assert gaenge["ollama-glm-5.3"]["model_id"] == "glm-5.3:cloud"


def test_pep621_license_files():
    """Verify that pyproject.toml defines license-files for packaging compliance."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "license-files = [" in pyproject_text, "Missing license-files in pyproject.toml"
    assert '"LICENSE"' in pyproject_text, "Missing LICENSE in license-files"
    assert '"NOTICE"' in pyproject_text, "Missing NOTICE in license-files"
    assert '"THIRD_PARTY_LICENSES.md"' in pyproject_text, "Missing THIRD_PARTY_LICENSES.md in license-files"
    assert '"THIRD_PARTY_LICENSES.txt"' in pyproject_text, "Missing THIRD_PARTY_LICENSES.txt in license-files"


def test_readme_target_personas_and_discoverability():
    """Verify that both READMEs document the 4 Target Personas."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    for persona in ["[PERSONA-01]", "[PERSONA-02]", "[PERSONA-03]", "[PERSONA-04]"]:
        assert persona in readme_en, f"README.md missing {persona}"
        assert persona in readme_de, f"README_de.md missing {persona}"


def test_comparative_matrix_vs_alternatives_parity():
    """Verify that both READMEs document the 10-dimension comparative matrix vs alternatives."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    assert "Comparative Matrix vs. Alternatives" in readme_en
    assert "Vergleichsmatrix gegenüber Alternativen" in readme_de
    canonical_invariants = [
        "INV-LOCAL-01", "INV-LOCAL-02", "INV-UNPRIV-03", "INV-CIRCUIT-04",
        "INV-OVERLAY-05", "INV-FALLBACK-06", "INV-BUDGET-07", "INV-PURPOSE-08",
        "INV-LEDGER-09", "INV-SLA-10"
    ]
    for inv in canonical_invariants:
        assert inv in readme_en, f"README.md missing invariant {inv} in comparison matrix"
        assert inv in readme_de, f"README_de.md missing invariant {inv} in comparison matrix"


def test_third_party_licenses_inventory_and_zero_copyleft():
    """Verify THIRD_PARTY_LICENSES.md completeness, zero-copyleft guarantee, and RunAsInvoker."""
    lic_file = REPO_ROOT / "THIRD_PARTY_LICENSES.md"
    assert lic_file.is_file(), "THIRD_PARTY_LICENSES.md missing"
    lic_text = lic_file.read_text(encoding="utf-8")

    assert "Zero-Copyleft Guarantee" in lic_text
    assert "RunAsInvoker" in lic_text
    for pkg in ["anthropic", "google-genai", "requests", "fastapi", "uvicorn", "pytest", "ruff"]:
        assert pkg in lic_text, f"THIRD_PARTY_LICENSES.md missing package {pkg}"
    canonical_invariants = [
        "INV-LOCAL-01", "INV-LOCAL-02", "INV-UNPRIV-03", "INV-CIRCUIT-04",
        "INV-OVERLAY-05", "INV-FALLBACK-06", "INV-BUDGET-07", "INV-PURPOSE-08",
        "INV-LEDGER-09", "INV-SLA-10"
    ]
    for inv in canonical_invariants:
        assert inv in lic_text, f"THIRD_PARTY_LICENSES.md missing invariant {inv}"


def test_pyproject_marketing_urls():
    """Verify that pyproject.toml includes URLs for Third-Party Licenses, Marketing Log, and LLM Ready."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert '"Third-Party Licenses"' in pyproject_text
    assert '"Marketing Log"' in pyproject_text
    assert '"LLM Ready"' in pyproject_text


def test_marketing_log_recency():
    """Verify that MARKETING-LOG.txt contains the 2026-09-28 Pfad B entry."""
    mkt_text = (REPO_ROOT / "MARKETING-LOG.txt").read_text(encoding="utf-8")
    assert "Date: 2026-09-28" in mkt_text
    assert "Pfad B (Marketing & Design / Discoverability)" in mkt_text


def test_sec_dual_html_anchors_parity():
    """Verify that both READMEs contain dual reciprocal HTML anchors sec-01 through sec-18."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")

    for i in range(1, 19):
        anchor = f'<a id="sec-{i:02d}"></a>'
        assert anchor in readme_en, f"README.md missing anchor {anchor}"
        assert anchor in readme_de, f"README_de.md missing anchor {anchor}"


def test_canonical_notice_attribution():
    """Verify that NOTICE exists, attributes Lukas Geiger, ellmos-ai, and references SBOMs."""
    notice_file = REPO_ROOT / "NOTICE"
    assert notice_file.is_file(), "NOTICE file missing"
    notice_text = notice_file.read_text(encoding="utf-8")

    assert "clutch" in notice_text
    assert "Lukas Geiger" in notice_text
    assert "ellmos-ai" in notice_text
    assert "open-bricks" in notice_text
    assert "THIRD_PARTY_LICENSES.md" in notice_text
    assert "THIRD_PARTY_LICENSES.txt" in notice_text


def test_third_party_licenses_plain_text_companion():
    """Verify THIRD_PARTY_LICENSES.txt plain-text Level 1 SBOM companion completeness."""
    sbom_file = REPO_ROOT / "THIRD_PARTY_LICENSES.txt"
    assert sbom_file.is_file(), "THIRD_PARTY_LICENSES.txt missing"
    sbom_text = sbom_file.read_text(encoding="utf-8")

    assert "LEVEL 1 SBOM INVENTORY" in sbom_text
    assert "Zero-Copyleft Guarantee" in sbom_text
    assert "RunAsInvoker" in sbom_text
    assert "INV-UNPRIV-03" in sbom_text
    assert "§ 521 BGB" in sbom_text

    for inv in [
        "INV-LOCAL-01", "INV-LOCAL-02", "INV-UNPRIV-03", "INV-CIRCUIT-04",
        "INV-OVERLAY-05", "INV-FALLBACK-06", "INV-BUDGET-07", "INV-PURPOSE-08",
        "INV-LEDGER-09", "INV-SLA-10"
    ]:
        assert inv in sbom_text, f"THIRD_PARTY_LICENSES.txt missing invariant {inv}"


def test_statutory_notice_bgb_521_and_48h_sla():
    """Verify § 521 BGB statutory notice and 48h SLA across READMEs, SECURITY.md, and llms.txt."""
    readme_en = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    readme_de = (REPO_ROOT / "README_de.md").read_text(encoding="utf-8")
    sec_text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    llms_text = (REPO_ROOT / "llms.txt").read_text(encoding="utf-8")

    assert "§ 521 BGB" in readme_en
    assert "§ 521 BGB" in readme_de
    assert "§ 521 BGB" in sec_text
    assert "§ 521 BGB" in llms_text
    assert "48h" in readme_en or "48 hours" in readme_en
    assert "48h" in readme_de or "48 Stunden" in readme_de


def test_pyproject_topics_saturation():
    """Verify that pyproject.toml keywords are saturated with 20 GitHub repositoryTopics."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    expected_topics = [
        "agent-framework", "ai", "auto-routing", "budget-tracking", "circuit-breaker",
        "llm", "llm-agents", "llm-orchestration", "llm-router", "local-first",
        "model-routing", "multi-agent", "multi-provider", "open-source", "orchestration",
        "provider-neutral", "python", "python-library", "sqlite", "zero-egress"
    ]
    for topic in expected_topics:
        assert f'"{topic}"' in pyproject_text, f"pyproject.toml missing topic {topic}"


def test_pyproject_project_urls_expansion():
    """Verify that pyproject.toml project.urls includes Notice, Third-Party Licenses (Text), and Level 1 SBOM."""
    pyproject_text = (REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert "Notice = " in pyproject_text
    assert '"Third-Party Licenses (Text)" = ' in pyproject_text
    assert '"Level 1 SBOM" = ' in pyproject_text


def test_changelog_unreleased_pfad_b_entry():
    """Verify that CHANGELOG.md contains the 2026-09-28 Pfad B unreleased entry."""
    cl_text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Pfad B Marketing, Discoverability & Level 1 SBOM Text Companion (2026-09-28)" in cl_text


def test_pytest_isolation_and_multihost_gitignore():
    """Verify that .gitignore excludes .pytest_temp/ and multi-host device names."""
    gi_text = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".pytest_temp/" in gi_text
    assert "*-IDEAPAD*" in gi_text
    assert "*-MacBook*" in gi_text
