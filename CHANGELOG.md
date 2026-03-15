# Changelog

Alle wesentlichen Aenderungen an **clutch** werden hier dokumentiert.

Das Format orientiert sich an [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [0.3.0] -- 2026-03-12

Erster oeffentlicher Release als `ellmos-ai/clutch`.

### Added
- Provider-neutrale LLM-Orchestration mit Auto-Metapher (Fahrer, Getriebe, Kupplung, etc.)
- Multi-Provider-Support: Anthropic (Claude), Google (Gemini), Ollama (lokal), Claude Code
- Streckenanalyse (Task-Klassifikation) mit 10 Streckentypen (Feldweg bis Langstrecke)
- Getriebe: Modell-Registry mit 8 vordefinierten Gaengen (G1--G5)
- Kupplung: Automatischer Modellwechsel basierend auf Strecke, Budget und Health
- Gas/Bremse: Reasoning-Level-Steuerung (0%--100%)
- Tankuhr: Budget-Tracking mit 4-Zonen-System (green/yellow/orange/red)
- Bordcomputer: Health-Monitor mit Circuit-Breaker pro Modell
- Fahrtenbuch: SQLite-basierte Metrik-Speicherung
- Fahrschule: Lernengine mit Epsilon-Greedy Exploration und Fitness-Scoring
- Tacho: Metriken-Erfassung waehrend der Laufzeit
- Execution Patterns: Einzelfahrt, Kolonne (Chain), Team (Parallel), Schwarm (Bulk), Hybrid
- JSON-basierte Konfiguration (getriebe.json, strecken.json, kupplung.json, fitness_criteria.json)
- 13 Unit-Tests (test_kupplung.py)
- README mit Architektur-Diagramm und Quick Start
- MIT-Lizenz

## [0.3.0-rc1] -- 2026-03-15

### Changed
- Repo-Referenzen auf `ellmos-ai/clutch` aktualisiert
- BACH-interne Dokumente (BACH_EINHAENGEPUNKTE.md, BACH_INTEGRATION.md) entfernt
- Personenbezogene Daten bereinigt

### Fixed
- `.gitignore` um BACH-Dateien ergaenzt
