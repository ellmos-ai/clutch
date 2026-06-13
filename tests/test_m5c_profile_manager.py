"""Tests für M5c — ProfileManager.

Startet mit einer temporären In-Memory-Datenbank bzw. einer Temp-Datei,
damit keine echte clutch.db berührt wird.
"""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

# Sicherstellen, dass das Paket-Root im Suchpfad liegt
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from clutch.profile_manager import Profil, ProfileManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path: Path) -> Path:
    """Temporäre DB-Datei; wird nach dem Test automatisch gelöscht."""
    return tmp_path / "test_clutch.db"


@pytest.fixture
def mgr(tmp_db: Path) -> ProfileManager:
    """ProfileManager mit leerer Temp-DB."""
    return ProfileManager(db_path=tmp_db)


# ---------------------------------------------------------------------------
# 1. speichere + lade (alle 3 Scopes)
# ---------------------------------------------------------------------------

class TestSpeichereUndLade:
    def test_user_profil_roundtrip(self, mgr: ProfileManager) -> None:
        p = Profil(name="lukas", scope="user", payload={"name": "Lukas", "default_profil": "budget"})
        mgr.speichere(p)
        geladen = mgr.lade("lukas", "user")
        assert geladen is not None
        assert geladen.name == "lukas"
        assert geladen.scope == "user"
        assert geladen.payload == {"name": "Lukas", "default_profil": "budget"}

    def test_zweck_profil_roundtrip(self, mgr: ProfileManager) -> None:
        payload = {
            "kosten_gewicht": 0.3,
            "erlaubte_gaenge": ["claude-haiku", "gpt-4o-mini"],
            "max_gang": 3,
            "tages_limit_usd": 5.0,
        }
        p = Profil(name="budget", scope="zweck", payload=payload)
        mgr.speichere(p)
        geladen = mgr.lade("budget", "zweck")
        assert geladen is not None
        assert geladen.payload["kosten_gewicht"] == 0.3
        assert geladen.payload["erlaubte_gaenge"] == ["claude-haiku", "gpt-4o-mini"]
        assert geladen.payload["tages_limit_usd"] == 5.0

    def test_toolset_profil_roundtrip(self, mgr: ProfileManager) -> None:
        payload = {
            "erlaubte_tools": ["bash", "read"],
            "tool_infos": {"bash": "Shell-Ausführung"},
            "mitgesendete_prompts": ["prompt-001"],
            "system_prompt_on": False,
        }
        p = Profil(name="minimal", scope="toolset", payload=payload)
        mgr.speichere(p)
        geladen = mgr.lade("minimal", "toolset")
        assert geladen is not None
        assert geladen.payload["erlaubte_tools"] == ["bash", "read"]
        assert geladen.payload["system_prompt_on"] is False

    def test_lade_nicht_vorhanden_gibt_none(self, mgr: ProfileManager) -> None:
        assert mgr.lade("existiert-nicht", "user") is None

    def test_updated_at_wird_aktualisiert(self, mgr: ProfileManager) -> None:
        p = Profil(name="x", scope="user", payload={})
        mgr.speichere(p)
        erster_ts = mgr.lade("x", "user").updated_at  # type: ignore[union-attr]
        time.sleep(0.01)
        p.payload["name"] = "aktualisiert"
        mgr.speichere(p)
        zweiter_ts = mgr.lade("x", "user").updated_at  # type: ignore[union-attr]
        assert zweiter_ts > erster_ts

    def test_upsert_überschreibt_payload(self, mgr: ProfileManager) -> None:
        p = Profil(name="test", scope="zweck", payload={"kosten_gewicht": 0.5})
        mgr.speichere(p)
        p.payload["kosten_gewicht"] = 0.9
        mgr.speichere(p)
        geladen = mgr.lade("test", "zweck")
        assert geladen is not None
        assert geladen.payload["kosten_gewicht"] == 0.9


# ---------------------------------------------------------------------------
# 2. liste(scope) filtert korrekt
# ---------------------------------------------------------------------------

class TestListe:
    def test_liste_alle(self, mgr: ProfileManager) -> None:
        mgr.speichere(Profil(name="a", scope="user", payload={}))
        mgr.speichere(Profil(name="b", scope="zweck", payload={}))
        mgr.speichere(Profil(name="c", scope="toolset", payload={}))
        alle = mgr.liste()
        assert len(alle) == 3

    def test_liste_nach_scope_filtert(self, mgr: ProfileManager) -> None:
        mgr.speichere(Profil(name="u1", scope="user", payload={}))
        mgr.speichere(Profil(name="u2", scope="user", payload={}))
        mgr.speichere(Profil(name="z1", scope="zweck", payload={}))
        user_profile = mgr.liste("user")
        assert len(user_profile) == 2
        assert all(p.scope == "user" for p in user_profile)

    def test_liste_leer_wenn_keine_einträge(self, mgr: ProfileManager) -> None:
        assert mgr.liste("toolset") == []

    def test_liste_zweck_scope(self, mgr: ProfileManager) -> None:
        mgr.speichere(Profil(name="routing-a", scope="zweck", payload={}))
        mgr.speichere(Profil(name="u1", scope="user", payload={}))
        zweck = mgr.liste("zweck")
        assert len(zweck) == 1
        assert zweck[0].name == "routing-a"


# ---------------------------------------------------------------------------
# 3. loesche
# ---------------------------------------------------------------------------

class TestLoesche:
    def test_loesche_existierendes_profil(self, mgr: ProfileManager) -> None:
        mgr.speichere(Profil(name="weg", scope="user", payload={}))
        assert mgr.loesche("weg", "user") is True
        assert mgr.lade("weg", "user") is None

    def test_loesche_nicht_vorhandenes_gibt_false(self, mgr: ProfileManager) -> None:
        assert mgr.loesche("nirgends", "zweck") is False

    def test_loesche_scope_spezifisch(self, mgr: ProfileManager) -> None:
        """Löschen in scope='user' darf scope='zweck' mit gleichem Namen nicht löschen."""
        mgr.speichere(Profil(name="shared", scope="user", payload={}))
        mgr.speichere(Profil(name="shared", scope="zweck", payload={}))
        mgr.loesche("shared", "user")
        assert mgr.lade("shared", "user") is None
        assert mgr.lade("shared", "zweck") is not None


# ---------------------------------------------------------------------------
# 4. aktives_setzen / aktives Roundtrip
# ---------------------------------------------------------------------------

class TestAktivesRoundtrip:
    def test_aktives_setzen_und_lesen(self, mgr: ProfileManager) -> None:
        mgr.aktives_setzen("user", "lukas")
        assert mgr.aktives("user") == "lukas"

    def test_aktives_ohne_eintrag_gibt_none(self, mgr: ProfileManager) -> None:
        assert mgr.aktives("zweck") is None

    def test_aktives_überschreibt_vorherigen(self, mgr: ProfileManager) -> None:
        mgr.aktives_setzen("toolset", "voll")
        mgr.aktives_setzen("toolset", "minimal")
        assert mgr.aktives("toolset") == "minimal"

    def test_aktives_je_scope_unabhängig(self, mgr: ProfileManager) -> None:
        mgr.aktives_setzen("user", "lukas")
        mgr.aktives_setzen("zweck", "budget")
        assert mgr.aktives("user") == "lukas"
        assert mgr.aktives("zweck") == "budget"
        assert mgr.aktives("toolset") is None


# ---------------------------------------------------------------------------
# 5. system_prompt_an / set_system_prompt
# ---------------------------------------------------------------------------

class TestSystemPrompt:
    def test_default_true_wenn_profil_fehlt(self, mgr: ProfileManager) -> None:
        """Kein Profil → system_prompt_an gibt True zurück."""
        assert mgr.system_prompt_an("existiert-nicht") is True

    def test_default_true_wenn_key_fehlt(self, mgr: ProfileManager) -> None:
        """Profil ohne system_prompt_on-Key → True."""
        mgr.speichere(Profil(name="ts", scope="toolset", payload={"erlaubte_tools": []}))
        assert mgr.system_prompt_an("ts") is True

    def test_set_system_prompt_auf_false(self, mgr: ProfileManager) -> None:
        mgr.set_system_prompt("ts", False)
        assert mgr.system_prompt_an("ts") is False

    def test_set_system_prompt_togglet_zurück(self, mgr: ProfileManager) -> None:
        mgr.set_system_prompt("ts", False)
        mgr.set_system_prompt("ts", True)
        assert mgr.system_prompt_an("ts") is True

    def test_set_system_prompt_legt_profil_an(self, mgr: ProfileManager) -> None:
        """Wenn das Toolset-Profil noch nicht existiert, wird es angelegt."""
        mgr.set_system_prompt("neu", True)
        p = mgr.lade("neu", "toolset")
        assert p is not None
        assert p.payload["system_prompt_on"] is True

    def test_set_system_prompt_erhält_sonstigen_payload(self, mgr: ProfileManager) -> None:
        """Andere Payload-Felder bleiben beim Toggle erhalten."""
        mgr.speichere(Profil(
            name="ts",
            scope="toolset",
            payload={"erlaubte_tools": ["bash"], "system_prompt_on": True},
        ))
        mgr.set_system_prompt("ts", False)
        p = mgr.lade("ts", "toolset")
        assert p is not None
        assert p.payload["erlaubte_tools"] == ["bash"]
        assert p.payload["system_prompt_on"] is False


# ---------------------------------------------------------------------------
# 6. payload Roundtrip (dict bleibt erhalten)
# ---------------------------------------------------------------------------

class TestPayloadRoundtrip:
    def test_verschachtelte_dicts_bleiben_erhalten(self, mgr: ProfileManager) -> None:
        payload = {
            "tool_infos": {
                "bash": {"beschreibung": "Shell", "gefährlich": True},
                "read": {"beschreibung": "Datei lesen"},
            },
            "mitgesendete_prompts": ["p1", "p2", "p3"],
            "system_prompt_on": True,
            "erlaubte_tools": ["bash", "read"],
        }
        mgr.speichere(Profil(name="komplex", scope="toolset", payload=payload))
        geladen = mgr.lade("komplex", "toolset")
        assert geladen is not None
        assert geladen.payload == payload

    def test_leerer_payload_roundtrip(self, mgr: ProfileManager) -> None:
        mgr.speichere(Profil(name="leer", scope="user", payload={}))
        geladen = mgr.lade("leer", "user")
        assert geladen is not None
        assert geladen.payload == {}

    def test_liste_float_typen_bleiben_float(self, mgr: ProfileManager) -> None:
        payload = {"kosten_gewicht": 0.75, "tages_limit_usd": 2.50}
        mgr.speichere(Profil(name="float-test", scope="zweck", payload=payload))
        geladen = mgr.lade("float-test", "zweck")
        assert geladen is not None
        assert isinstance(geladen.payload["kosten_gewicht"], float)
        assert geladen.payload["kosten_gewicht"] == pytest.approx(0.75)

    def test_unicode_in_payload(self, mgr: ProfileManager) -> None:
        payload = {"name": "Müller", "notiz": "Öffentlich ähnliche Überprüfung"}
        mgr.speichere(Profil(name="unicode", scope="user", payload=payload))
        geladen = mgr.lade("unicode", "user")
        assert geladen is not None
        assert geladen.payload["name"] == "Müller"
        assert "Ö" in geladen.payload["notiz"]


# ---------------------------------------------------------------------------
# 7. Ungültiger Scope → ValueError
# ---------------------------------------------------------------------------

class TestValidierung:
    def test_ungültiger_scope_in_profil(self) -> None:
        with pytest.raises(ValueError, match="Scope"):
            Profil(name="x", scope="ungültig", payload={})

    def test_default_profil_factory_alle_scopes(self, mgr: ProfileManager) -> None:
        for scope in ("user", "zweck", "toolset"):
            p = ProfileManager.default_profil(scope)
            assert p.scope == scope
            assert isinstance(p.payload, dict)

    def test_default_profil_factory_ungültig(self) -> None:
        with pytest.raises(ValueError):
            ProfileManager.default_profil("invalid")
