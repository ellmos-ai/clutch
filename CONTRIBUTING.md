# Beitragsrichtlinie / Contributing Guide

## Deutsch

Beiträge sind willkommen. Melde Fehler und schlage Änderungen über ein Issue im [ellmos-ai/clutch-Repository](https://github.com/ellmos-ai/clutch/issues) vor. Für Änderungen am Code erstelle einen Pull Request. Größere Änderungen sollten vor der Umsetzung mit einem Issue abgestimmt werden.

### Hinweis zur CLA-Vorlage

Die bisherige Contributor-Vorlage verlangt eine CLA-Zustimmung, verweist aber auf eine im Repository nicht vorhandene `CLA.md`. Die geltende Contributor-Lizenzregel ist daher vom Repository-Owner zu klären. Dieser Leitfaden schafft keine neue CLA-Pflicht und hebt keine bestehende Regel auf.

### Entwicklungsumgebung

Voraussetzung ist Python 3.10 oder neuer. Klone das Repository und installiere die Testwerkzeuge:

```bash
git clone https://github.com/ellmos-ai/clutch.git
cd clutch
python -m pip install -e ".[test]" build
python -m pytest -ra -v
ruff check .
python -m compileall -q clutch tests
```

Für die optionale Weboberfläche installiere zusätzlich das web-Extra:

```bash
python -m pip install -e ".[web,test]"
```

Bitte verwende UTF-8, vermeide fest codierte Hostpfade oder Zugangsdaten und führe relevante Tests vor dem Pull Request aus. GitHub Actions führt die Plattform- und Python-Matrix für jeden Pull Request aus.

## English

Contributions are welcome. Report bugs or propose changes through an issue in the [ellmos-ai/clutch repository](https://github.com/ellmos-ai/clutch/issues). Submit code changes as a pull request. Discuss larger changes in an issue before implementation.

### CLA template note

The existing contributor template asks contributors to agree to a CLA but links to a `CLA.md` that is not present in the repository. The repository owner needs to clarify the applicable contributor-licensing rule. This guide neither creates a new CLA requirement nor removes an existing rule.

### Development setup

Python 3.10 or newer is required. Clone the repository and install the test tools:

```bash
git clone https://github.com/ellmos-ai/clutch.git
cd clutch
python -m pip install -e ".[test]" build
python -m pytest -ra -v
ruff check .
python -m compileall -q clutch tests
```

To install the optional web interface dependencies as well:

```bash
python -m pip install -e ".[web,test]"
```

Use UTF-8, avoid hard-coded host paths or credentials, and run relevant tests before opening a pull request. GitHub Actions runs the platform and Python matrix for each pull request.
