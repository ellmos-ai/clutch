"""Repository metadata, document links, and packaging contracts for clutch."""
from pathlib import Path
import re
try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib
from urllib.parse import unquote, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
READMES = (
    "README.md",
    "README_de.md",
    "README_es.md",
    "README_ja.md",
    "README_ru.md",
    "README_zh-Hans.md",
)


def test_core_documentation_and_package_manifest_exist():
    required = (
        *READMES,
        "docs/archive/README-2026-10-12.md",
        "docs/archive/README_de-2026-10-12.md",
        "LICENSE",
        "SECURITY.md",
        "THIRD_PARTY_LICENSES.md",
        "CHANGELOG.md",
        "llms.txt",
        "MARKETING-LOG.txt",
        "MANIFEST.in",
        "pyproject.toml",
    )
    for relative in required:
        path = REPO_ROOT / relative
        assert path.is_file(), f"Missing repository file: {relative}"
        assert path.stat().st_size > 0, f"Repository file is empty: {relative}"


def test_version_consistency():
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    init_text = (REPO_ROOT / "clutch" / "__init__.py").read_text(encoding="utf-8")
    llms_text = (REPO_ROOT / "llms.txt").read_text(encoding="utf-8")
    version = pyproject["project"]["version"]
    match = re.search(r'__version__\s*=\s*"([^"]+)"', init_text)
    assert match, "clutch.__version__ is missing"
    assert version == match.group(1)
    assert version in llms_text


def _markdown_anchor_ids(text: str) -> set[str]:
    anchors = set(re.findall(r"<a\b[^>]*\bid=[\"']([^\"']+)[\"']", text, flags=re.IGNORECASE))
    used_slugs: dict[str, int] = {}
    for heading in re.findall(r"(?m)^#{1,6}\s+(.+?)\s*#*\s*$", text):
        heading = re.sub(r"<[^>]+>", "", heading)
        heading = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", heading)
        heading = re.sub(r"`([^`]+)`", r"\1", heading).strip().lower()
        slug = re.sub(r"[^\w -]", "", heading, flags=re.UNICODE)
        slug = re.sub(r"\s+", "-", slug.strip())
        count = used_slugs.get(slug, 0)
        used_slugs[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def test_markdown_local_links_resolve():
    markdown_files = [REPO_ROOT / name for name in READMES]
    markdown_files.extend(
        REPO_ROOT / name
        for name in (
            "SECURITY.md",
            "THIRD_PARTY_LICENSES.md",
            "CHANGELOG.md",
            "llms.txt",
            "docs/archive/README-2026-10-12.md",
            "docs/archive/README_de-2026-10-12.md",
        )
    )
    link_pattern = re.compile(r"!?(?:\[[^\]]*\])\(([^)]+)\)")
    for markdown_file in markdown_files:
        text = markdown_file.read_text(encoding="utf-8")
        for target in link_pattern.findall(text):
            target = target.strip().split()[0].strip("<>")
            if not target:
                continue
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith("//"):
                continue
            path_part = unquote(parsed.path)
            linked_file = (markdown_file.parent / Path(path_part)) if path_part else markdown_file
            assert linked_file.exists(), (
                f"{markdown_file.relative_to(REPO_ROOT)} has a broken local link: {target}"
            )
            if parsed.fragment:
                linked_text = linked_file.read_text(encoding="utf-8")
                assert unquote(parsed.fragment) in _markdown_anchor_ids(linked_text), (
                    f"{markdown_file.relative_to(REPO_ROOT)} has a broken local anchor: {target}"
                )


def test_readme_language_navigation_and_architecture_diagrams():
    for readme in READMES:
        text = (REPO_ROOT / readme).read_text(encoding="utf-8")
        for language_file in READMES:
            assert f"({language_file})" in text, f"{readme} should link to {language_file}"
    archives = {
        "README.md": ("docs/archive/README-2026-10-12.md", "README-2026-10-12.md"),
        "README_de.md": ("docs/archive/README_de-2026-10-12.md", "README_de-2026-10-12.md"),
    }
    section_ids = (
        "1-features",
        "2-architecture",
        "3-target-personas--discoverability",
        "4-comparative-matrix-vs-alternatives",
        "5-dual-mermaid-diagrams",
        "6-governance--runtime-invariants",
        "7-road-types",
        "8-installation",
        "9-quick-start",
        "10-command-line-interface",
        "11-api-keys--credentials",
        "12-configuration",
        "13-supported-providers",
        "14-execution-patterns",
        "15-ecosystem--sibling-tools",
        "16-third-party-licenses--transparency",
        "17-security-policy--liability",
        "18-verification--test-suite",
    )
    legacy_anchors = {
        "README.md": tuple((section, re.sub(r"^\d+-", "", section)) for section in section_ids),
        "README_de.md": (
            ("1-features", "features", "funktionen"),
            ("2-architecture", "architecture", "architektur"),
            ("3-target-personas--discoverability", "target-personas--discoverability", "zielgruppen--auffindbarkeit"),
            ("4-comparative-matrix-vs-alternatives", "comparative-matrix-vs-alternatives", "vergleichsmatrix-gegenueber-alternativen"),
            ("5-dual-mermaid-diagrams", "dual-mermaid-diagrams", "duale-mermaid-diagramme"),
            ("6-governance--runtime-invariants", "governance--runtime-invariants", "governance--laufzeit-invarianten"),
            ("7-road-types", "road-types", "streckentypen"),
            ("8-installation", "installation"),
            ("9-quick-start", "quick-start", "kurzanleitung"),
            ("10-command-line-interface", "command-line-interface", "kommandozeilen-schnittstelle"),
            ("11-api-keys--credentials", "api-keys--credentials", "api-keys--zugangsdaten"),
            ("12-configuration", "configuration", "konfiguration"),
            ("13-supported-providers", "supported-providers", "unterstuetzte-provider"),
            ("14-execution-patterns", "execution-patterns", "ausfuehrungsmuster"),
            ("15-ecosystem--sibling-tools", "ecosystem--sibling-tools", "verwandte-tools--oekosystem"),
            ("16-third-party-licenses--transparency", "third-party-licenses--transparency", "drittanbieter-lizenzen--transparenz"),
            ("17-security-policy--liability", "security-policy--liability", "sicherheitsrichtlinie--haftung"),
            ("18-verification--test-suite", "verification--test-suite", "verifikation--testsuite"),
        ),
    }
    for readme, (archive_path, archive_name) in archives.items():
        text = (REPO_ROOT / readme).read_text(encoding="utf-8")
        root_anchors = _markdown_anchor_ids(text)
        archive = (REPO_ROOT / archive_path).read_text(encoding="utf-8")
        assert "flowchart TD" in archive
        assert "sequenceDiagram" in archive
        assert all(f'<a id="{section}">' in archive for section in section_ids)
        assert all(f"({archive_path}#{section})" in text for section in section_ids)
        assert all(anchor in root_anchors for group in legacy_anchors[readme] for anchor in group), (
            f"{readme} must retain its previous numbered and alias anchors at the root"
        )
        assert archive_name in text


def test_ci_matrix_and_lint_contract():
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "ubuntu-latest" in ci and "windows-latest" in ci and "macos-latest" in ci
    assert all(version in ci for version in ('"3.10"', '"3.11"', '"3.12"', '"3.13"'))
    assert "ruff check ." in ci
    assert "python -m pytest" in ci


def test_review_gate_jobs_have_timeouts():
    workflow = (REPO_ROOT / ".github" / "workflows" / "review-gate.yml").read_text(encoding="utf-8")
    for job in ("pending", "dispatch"):
        assert re.search(rf"(?m)^  {job}:\n    timeout-minutes: 5\n", workflow), (
            f"{job} must declare a bounded job timeout"
        )


def test_pyproject_metadata_and_runtime_extras():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert project["project"]["requires-python"] == ">=3.10"
    assert project["project"]["license"] == "MIT"
    assert project["project"]["license-files"] == ["LICENSE"]
    assert project["project"]["scripts"]["clutch"] == "clutch.cli:main"
    assert any(requirement.startswith("python-multipart") for requirement in project["project"]["optional-dependencies"]["web"])


def test_project_urls_target_existing_public_documents():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    urls = project["urls"]
    expected = {
        "Changelog": "CHANGELOG.md",
        "Security": "SECURITY.md",
        "Third-Party Licenses": "THIRD_PARTY_LICENSES.md",
        "Marketing Log": "MARKETING-LOG.txt",
        "LLM Ready": "llms.txt",
    }
    for label, filename in expected.items():
        assert filename in urls[label]
        assert (REPO_ROOT / filename).is_file()


def test_package_data_covers_declared_runtime_resources():
    project = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = project["tool"]["setuptools"]["package-data"]["clutch"]
    assert "config/*.json" in package_data
    assert "locales/*.json" in package_data
    assert "web/*" in package_data
    web_dir = REPO_ROOT / "clutch" / "web"
    page = (web_dir / "index.html").read_text(encoding="utf-8")
    asset_refs = re.findall(r'''(?:src|href)=["']([^"'#]+)["']''', page)
    for reference in asset_refs:
        if reference.startswith(("http://", "https://", "data:")):
            continue
        assert (web_dir / reference).is_file(), f"Web page refers to missing package asset: {reference}"


def test_security_reporting_channels_are_documented():
    text = (REPO_ROOT / "SECURITY.md").read_text(encoding="utf-8")
    assert "# Sicherheitsrichtlinie" in text and "# Security Policy" in text
    assert "https://github.com/ellmos-ai/clutch/security/advisories/new" in text
    assert "security@ellmos.ai" in text
    assert "security@open-bricks.org" in text
