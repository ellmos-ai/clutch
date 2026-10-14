"""Tests fuer StreckenAnalyse -- Task-Klassifikation und Profil-Erstellung."""

import sys
import json
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch.strecke import StreckenAnalyse, StreckenTyp, StreckenProfil, Tempo
from clutch.getriebe import Getriebe
from clutch.kupplung import Kupplung


def _role_route(tmp_path, role_models):
    path = tmp_path / "user_overrides.json"
    path.write_text(json.dumps({"role_preferred_models": role_models}), encoding="utf-8")
    gearbox = Getriebe(overrides_path=path)
    clutch = Kupplung(gearbox)
    clutch.set_erkundungsrate(0)
    profile = StreckenAnalyse().analysiere("Fix the typo in the docstring")
    return clutch, profile


def test_role_overlay_is_consumed_without_changing_legacy_route(tmp_path):
    clutch, profile = _role_route(tmp_path, {"reviewer": ["claude-haiku"]})
    baseline = clutch.einlegen(profile)
    selected = clutch.einlegen(profile, rolle="reviewer")
    assert selected.gang.name == "claude-haiku"
    assert clutch.einlegen(profile).gang.name == baseline.gang.name


def test_role_rejects_unknown_or_unavailable_model(tmp_path):
    clutch, profile = _role_route(tmp_path, {"reviewer": ["not-in-registry"]})
    with pytest.raises(ValueError, match="unknown model"):
        clutch.einlegen(profile, rolle="reviewer")
    with pytest.raises(ValueError, match="unknown routing role"):
        clutch.einlegen(profile, rolle="old-reviewer")
    clutch, profile = _role_route(tmp_path, {"reviewer": ["claude-haiku"]})
    with pytest.raises(RuntimeError, match="no available model"):
        clutch.einlegen(profile, rolle="reviewer", ausschluss=["claude-haiku"])


def test_role_respects_hard_candidate_gates(tmp_path):
    clutch, profile = _role_route(tmp_path, {"reviewer": ["claude-opus"]})
    with pytest.raises(RuntimeError, match="no available model"):
        clutch.einlegen(profile, rolle="reviewer", max_gang=3)
    clutch, profile = _role_route(tmp_path, {"reviewer": ["claude-code"]})
    with pytest.raises(RuntimeError, match="no available model"):
        clutch.einlegen(profile, rolle="reviewer", vertrauenswuerdig=False)
    path = tmp_path / "user_overrides.json"
    path.write_text(json.dumps({
        "role_preferred_models": {"reviewer": ["claude-haiku"]},
        "disabled_models": ["claude-haiku"],
    }), encoding="utf-8")
    gearbox = Getriebe(overrides_path=path)
    clutch = Kupplung(gearbox)
    clutch.set_erkundungsrate(0)
    with pytest.raises(RuntimeError, match="no available model"):
        clutch.einlegen(profile, rolle="reviewer")


def test_cli_role_reaches_private_overlay_reader(tmp_path, monkeypatch, capsys):
    from clutch.cli import main

    monkeypatch.setenv("CLUTCH_HOME", str(tmp_path))
    (tmp_path / "user_overrides.json").write_text(json.dumps({
        "role_preferred_models": {"reviewer": ["claude-haiku"]},
        "disabled_models": ["claude-haiku"],
    }), encoding="utf-8")
    result = main(["route", "Fix the typo in the docstring", "--rolle", "reviewer",
                   "--db", str(tmp_path / "route.db"), "--json"])
    # The private overlay disables the named model. The CLI must read the
    # overlay and fail closed instead of substituting a different model.
    assert result == 1
    assert "no available model for role: reviewer" in capsys.readouterr().err


def _write_role_profile(tmp_path, models):
    path = tmp_path / "models.profile.json"
    path.write_text(json.dumps({"schema_version": "1.0.0", "models": models}), encoding="utf-8")
    return path


def _profile_model(name="claude-haiku", provider="anthropic", verified=True,
                   roles=None):
    return {"id": name, "provider": provider, "verified": verified,
            "deprecated": False, "roles": roles or ["reviewer"]}


def test_explicit_private_profile_is_read_and_mapped_to_role_candidates(tmp_path):
    profile_path = _write_role_profile(tmp_path, [_profile_model()])
    override_path = tmp_path / "user_overrides.json"
    override_path.write_text(json.dumps({"role_profile_path": str(profile_path)}), encoding="utf-8")
    gearbox = Getriebe(overrides_path=override_path)
    clutch = Kupplung(gearbox)
    clutch.set_erkundungsrate(0)
    task = StreckenAnalyse().analysiere("Fix the typo in the docstring")
    baseline = clutch.einlegen(task).gang.name
    assert gearbox.role_preferred_models("reviewer") == ["claude-haiku"]
    assert clutch.einlegen(task, rolle="reviewer").gang.name == "claude-haiku"
    assert clutch.einlegen(task).gang.name == baseline
    profile_path.write_text(json.dumps({"schema_version": "1.0.0",
                                        "models": [_profile_model(verified=False)]}),
                            encoding="utf-8")
    with pytest.raises(ValueError, match="unverified"):
        clutch.einlegen(task, rolle="reviewer")
    assert clutch.einlegen(task).gang.name == baseline


def test_explicit_profile_cannot_override_disabled_budget_or_trust_gates(tmp_path):
    profile_path = _write_role_profile(tmp_path, [_profile_model(name="claude-opus")])
    override_path = tmp_path / "user_overrides.json"
    override_path.write_text(json.dumps({"role_profile_path": str(profile_path)}), encoding="utf-8")
    clutch = Kupplung(Getriebe(overrides_path=override_path))
    clutch.set_erkundungsrate(0)
    task = StreckenAnalyse().analysiere("Fix the typo in the docstring")
    with pytest.raises(RuntimeError, match="no available model"):
        clutch.einlegen(task, rolle="reviewer", max_gang=3)
    profile_path.write_text(json.dumps({"schema_version": "1.0.0", "models": [
        _profile_model(name="claude-code", provider="claude-code")]}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no available model"):
        clutch.einlegen(task, rolle="reviewer", vertrauenswuerdig=False)
    override_path.write_text(json.dumps({"role_profile_path": str(profile_path),
                                         "disabled_models": ["claude-code"]}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="no available model"):
        Kupplung(Getriebe(overrides_path=override_path)).einlegen(task, rolle="reviewer")


def test_explicit_model_and_role_must_match_and_obey_hard_gates(tmp_path):
    profile_path = _write_role_profile(tmp_path, [_profile_model()])
    override_path = tmp_path / "user_overrides.json"
    override_path.write_text(json.dumps({"role_profile_path": str(profile_path)}), encoding="utf-8")
    clutch = Kupplung(Getriebe(overrides_path=override_path))
    task = StreckenAnalyse().analysiere("Fix the typo in the docstring")
    assert clutch.einlegen(task, rolle="reviewer", model_override="claude-haiku").gang.name == "claude-haiku"
    with pytest.raises(ValueError, match="not configured for role"):
        clutch.einlegen(task, rolle="reviewer", model_override="claude-opus")
    with pytest.raises(RuntimeError, match="exceeds budget limit"):
        clutch.einlegen(task, rolle="reviewer", model_override="claude-haiku", max_gang=0)
    with pytest.raises(RuntimeError, match="gesperrt"):
        clutch.einlegen(task, rolle="reviewer", model_override="claude-haiku", ausschluss=["claude-haiku"])


@pytest.mark.parametrize("models, error", [
    ([_profile_model(verified=False)], "unverified"),
    ([_profile_model(name="gpt-6-luna", provider="openai-codex")], "unregistered"),
    ([_profile_model(provider="openai-codex")], "provider"),
    ([_profile_model(roles=["old-reviewer"])], "invalid roles"),
    ([_profile_model(), _profile_model()], "duplicate"),
])
def test_private_profile_rejects_unverified_unknown_and_ambiguous_entries(
    tmp_path, models, error,
):
    profile_path = _write_role_profile(tmp_path, models)
    override_path = tmp_path / "user_overrides.json"
    override_path.write_text(json.dumps({"role_profile_path": str(profile_path)}), encoding="utf-8")
    gearbox = Getriebe(overrides_path=override_path)
    with pytest.raises(ValueError, match=error):
        gearbox.role_preferred_models("reviewer")


def test_private_profile_path_schema_and_conflicting_manual_map_fail_closed(tmp_path):
    profile_path = _write_role_profile(tmp_path, [_profile_model()])
    override_path = tmp_path / "user_overrides.json"
    override_path.write_text(json.dumps({"role_profile_path": str(profile_path),
                                         "role_preferred_models": {"reviewer": ["claude-haiku"]}}),
                             encoding="utf-8")
    with pytest.raises(ValueError, match="mutually exclusive"):
        Getriebe(overrides_path=override_path).role_preferred_models("reviewer")
    override_path.write_text(json.dumps({"role_profile_path": 42,
                                         "role_preferred_models": {"reviewer": ["claude-haiku"]}}),
                             encoding="utf-8")
    with pytest.raises(ValueError, match="mutually exclusive"):
        Getriebe(overrides_path=override_path).role_preferred_models("reviewer")
    override_path.write_text(json.dumps({"role_profile_path": 42}), encoding="utf-8")
    with pytest.raises(ValueError, match="nonempty absolute string"):
        Getriebe(overrides_path=override_path).role_preferred_models("reviewer")
    override_path.write_text(json.dumps({"role_profile_path": ""}), encoding="utf-8")
    with pytest.raises(ValueError, match="nonempty absolute string"):
        Getriebe(overrides_path=override_path).role_preferred_models("reviewer")
    override_path.write_text(json.dumps({"role_profile_path": "relative.json"}), encoding="utf-8")
    with pytest.raises(ValueError, match="absolute"):
        Getriebe(overrides_path=override_path).role_preferred_models("reviewer")
    profile_path.write_text("{bad json", encoding="utf-8")
    override_path.write_text(json.dumps({"role_profile_path": str(profile_path)}), encoding="utf-8")
    with pytest.raises(ValueError, match="invalid JSON"):
        Getriebe(overrides_path=override_path).role_preferred_models("reviewer")
    profile_path.write_text(json.dumps({"schema_version": "future", "models": []}), encoding="utf-8")
    with pytest.raises(ValueError, match="schema"):
        Getriebe(overrides_path=override_path).role_preferred_models("reviewer")


def test_feldweg_erkennung():
    """Triviale Tasks (Typos, Formatting) -> Feldweg."""
    a = StreckenAnalyse()

    profil = a.analysiere("Rename the variable foo to bar")
    assert profil.typ == StreckenTyp.FELDWEG, f"Expected FELDWEG, got {profil.typ}"

    profil = a.analysiere("Fix the typo in the docstring")
    assert profil.typ == StreckenTyp.FELDWEG, f"Expected FELDWEG, got {profil.typ}"

    profil = a.analysiere("Format the indentation in utils.py")
    assert profil.typ == StreckenTyp.FELDWEG, f"Expected FELDWEG, got {profil.typ}"

    print("[OK] Feldweg-Erkennung")


def test_autobahn_erkennung():
    """Architektur-Tasks -> Autobahn."""
    a = StreckenAnalyse()

    profil = a.analysiere("Refactor the entire architecture of the auth module")
    assert profil.typ == StreckenTyp.AUTOBAHN, f"Expected AUTOBAHN, got {profil.typ}"

    profil = a.analysiere("Design a new API interface for the payment system")
    assert profil.typ == StreckenTyp.AUTOBAHN, f"Expected AUTOBAHN, got {profil.typ}"

    profil = a.analysiere("Migration der gesamten Datenbankstruktur")
    assert profil.typ == StreckenTyp.AUTOBAHN, f"Expected AUTOBAHN, got {profil.typ}"

    print("[OK] Autobahn-Erkennung")


def test_bundesstrasse_erkennung():
    """Bugfix-Tasks -> Bundesstrasse."""
    a = StreckenAnalyse()

    profil = a.analysiere("Fix the crash when user clicks login button")
    assert profil.typ == StreckenTyp.BUNDESSTRASSE, f"Expected BUNDESSTRASSE, got {profil.typ}"

    profil = a.analysiere("Debug the exception in the payment module")
    assert profil.typ == StreckenTyp.BUNDESSTRASSE, f"Expected BUNDESSTRASSE, got {profil.typ}"

    print("[OK] Bundesstrasse-Erkennung")


def test_rallye_erkennung():
    """Bulk-Operations -> Rallye."""
    a = StreckenAnalyse()

    profil = a.analysiere("Batch rename all test files")
    assert profil.typ == StreckenTyp.RALLYE, f"Expected RALLYE, got {profil.typ}"

    profil = a.analysiere("Format all files in the src directory")
    assert profil.typ == StreckenTyp.RALLYE, f"Expected RALLYE, got {profil.typ}"

    print("[OK] Rallye-Erkennung")


def test_testfahrt_erkennung():
    """Test-Generierung -> Testfahrt."""
    a = StreckenAnalyse()

    profil = a.analysiere("Write unit tests for the payment module")
    assert profil.typ == StreckenTyp.TESTFAHRT, f"Expected TESTFAHRT, got {profil.typ}"

    profil = a.analysiere("Add pytest coverage for the auth handler")
    assert profil.typ == StreckenTyp.TESTFAHRT, f"Expected TESTFAHRT, got {profil.typ}"

    print("[OK] Testfahrt-Erkennung")


def test_tempo_erkennung():
    """Tempo-Keywords korrekt erkannt."""
    a = StreckenAnalyse()

    profil = a.analysiere("Schnell den Fehler beheben bitte!")
    assert profil.tempo == Tempo.EILIG, f"Expected EILIG, got {profil.tempo}"

    profil = a.analysiere("Gruendlich und sorgfaeltig den Code pruefen, keine Eile")
    assert profil.tempo == Tempo.GEMUETLICH, f"Expected GEMUETLICH, got {profil.tempo}"

    profil = a.analysiere("Implement the new user login feature")
    assert profil.tempo == Tempo.NORMAL, f"Expected NORMAL, got {profil.tempo}"

    print("[OK] Tempo-Erkennung")


def test_tempo_kontext_override():
    """Kontext-Dict ueberschreibt Tempo-Erkennung."""
    a = StreckenAnalyse()

    # Ohne Kontext: "schnell" -> eilig
    profil = a.analysiere("Schnell den Bug fixen", {})
    assert profil.tempo == Tempo.EILIG

    # Mit Kontext-Override: erzwinge gemuetlich
    profil = a.analysiere("Schnell den Bug fixen", {"tempo": "gemuetlich"})
    assert profil.tempo == Tempo.GEMUETLICH, f"Expected GEMUETLICH, got {profil.tempo}"

    print("[OK] Tempo-Kontext-Override")


def test_schwierigkeit_signale():
    """Schwierigkeitssignale beeinflussen den Score."""
    a = StreckenAnalyse()

    # Explizit schwierig
    profil_schwer = a.analysiere("This is a very complex and challenging task that is difficult")
    # Explizit einfach
    profil_leicht = a.analysiere("Simple small quick one-liner change")

    assert profil_schwer.schwierigkeit > profil_leicht.schwierigkeit, (
        f"Schwer ({profil_schwer.schwierigkeit}) sollte > leicht ({profil_leicht.schwierigkeit}) sein"
    )

    print(f"[OK] Schwierigkeit (schwer={profil_schwer.schwierigkeit:.2f}, leicht={profil_leicht.schwierigkeit:.2f})")


def test_schwierigkeit_kontext_override():
    """Schwierigkeit kann per Kontext exakt vorgegeben werden."""
    a = StreckenAnalyse()

    profil = a.analysiere("Irgendwas", {"schwierigkeit": 0.95})
    assert profil.schwierigkeit == 0.95, f"Expected 0.95, got {profil.schwierigkeit}"

    print("[OK] Schwierigkeit-Kontext-Override")


def test_etappen_schaetzung():
    """Etappen werden korrekt geschaetzt."""
    a = StreckenAnalyse()

    # Einzelne Aufgabe
    profil = a.analysiere("Fix the login bug")
    assert profil.etappen >= 1

    # Mehrere Aufgaben durch 'und/and'
    profil = a.analysiere("Fix the login bug and update the tests and refactor the handler")
    assert profil.etappen >= 3, f"Expected >= 3, got {profil.etappen}"

    print("[OK] Etappen-Schaetzung")


def test_etappen_kontext_override():
    """Etappen koennen per Kontext gesetzt werden."""
    a = StreckenAnalyse()

    profil = a.analysiere("Grosses Projekt", {"etappen": 7})
    assert profil.etappen == 7, f"Expected 7, got {profil.etappen}"

    print("[OK] Etappen-Kontext-Override")


def test_strecken_profil_felder():
    """StreckenProfil hat alle erwarteten Felder."""
    a = StreckenAnalyse()
    profil = a.analysiere("Design the new system architecture")

    assert isinstance(profil, StreckenProfil)
    assert isinstance(profil.typ, StreckenTyp)
    assert isinstance(profil.tempo, Tempo)
    assert 0.0 <= profil.schwierigkeit <= 1.0
    assert profil.etappen >= 1
    assert isinstance(profil.braucht_spezialisten, bool)
    assert isinstance(profil.ist_pipeline, bool)
    assert 0.0 <= profil.konfidenz <= 1.0
    assert isinstance(profil.erkannte_keywords, list)

    # Autobahn braucht Spezialisten
    assert profil.braucht_spezialisten, "Autobahn sollte Spezialisten brauchen"

    print("[OK] StreckenProfil-Felder")


def test_konvoi_pipeline_flag():
    """Konvoi setzt ist_pipeline auf True."""
    a = StreckenAnalyse()
    profil = a.analysiere("Execute the pipeline step by step")
    assert profil.typ == StreckenTyp.KONVOI, f"Expected KONVOI, got {profil.typ}"
    assert profil.ist_pipeline, "Konvoi sollte ist_pipeline=True setzen"

    print("[OK] Konvoi-Pipeline-Flag")


def test_unbekannte_aufgabe_fallback():
    """Nicht erkannte Aufgabe -> Landstrasse (Fallback)."""
    a = StreckenAnalyse()
    profil = a.analysiere("Mach was mit dem Ding")
    assert profil.typ == StreckenTyp.LANDSTRASSE, f"Expected LANDSTRASSE, got {profil.typ}"
    assert profil.konfidenz <= 0.5, "Unbekannte Aufgabe sollte niedrige Konfidenz haben"

    print("[OK] Unbekannte Aufgabe -> Landstrasse-Fallback")


if __name__ == "__main__":
    test_feldweg_erkennung()
    test_autobahn_erkennung()
    test_bundesstrasse_erkennung()
    test_rallye_erkennung()
    test_testfahrt_erkennung()
    test_tempo_erkennung()
    test_tempo_kontext_override()
    test_schwierigkeit_signale()
    test_schwierigkeit_kontext_override()
    test_etappen_schaetzung()
    test_etappen_kontext_override()
    test_strecken_profil_felder()
    test_konvoi_pipeline_flag()
    test_unbekannte_aufgabe_fallback()
    print("\n=== ALLE 14 STRECKEN-TESTS BESTANDEN ===")
