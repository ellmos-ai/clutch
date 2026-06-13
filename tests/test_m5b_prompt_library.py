"""Tests für M5b -- Prompt-Bibliothek (clutch.prompt_library).

Strategie: Kein Netzwerk, kein LLM. Alle Tests laufen offline
mit einer temporären SQLite-DB (tmp_path).
"""

import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from clutch.prompt_library import PromptItem, PromptLibrary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def lib(tmp_path):
    """Frische PromptLibrary mit temporärer DB."""
    return PromptLibrary(db_path=tmp_path / "test_clutch.db")


@pytest.fixture
def beispiel_item() -> PromptItem:
    return PromptItem(
        id="",
        typ="prompt",
        name="Mein Testprompt",
        content="Erkläre mir {thema} in einfachen Worten.",
        category="Erklärung",
        tags=["erklärung", "einfach"],
        source="test",
    )


# ---------------------------------------------------------------------------
# upsert + get
# ---------------------------------------------------------------------------

class TestUpsertGet:
    def test_upsert_vergibt_id_wenn_leer(self, lib, beispiel_item):
        """Leere ID wird automatisch per uuid4 gefüllt."""
        gespeichert = lib.upsert(beispiel_item)
        assert gespeichert.id != ""

    def test_get_findet_gespeicherten_eintrag(self, lib, beispiel_item):
        gespeichert = lib.upsert(beispiel_item)
        geladen = lib.get(gespeichert.id)
        assert geladen is not None
        assert geladen.name == beispiel_item.name
        assert geladen.content == beispiel_item.content
        assert geladen.category == "Erklärung"
        assert "erklärung" in geladen.tags

    def test_get_gibt_none_bei_unbekannter_id(self, lib):
        assert lib.get("nicht-vorhanden") is None

    def test_upsert_aktualisiert_bestehenden_eintrag(self, lib, beispiel_item):
        """Zweimaliges upsert mit derselben ID überschreibt den Eintrag."""
        gespeichert = lib.upsert(beispiel_item)
        gespeichert.content = "Neuer Inhalt"
        lib.upsert(gespeichert)
        geladen = lib.get(gespeichert.id)
        assert geladen is not None
        assert geladen.content == "Neuer Inhalt"

    def test_upsert_setzt_updated_at(self, lib, beispiel_item):
        gespeichert = lib.upsert(beispiel_item)
        assert gespeichert.updated_at != ""

    def test_typ_normalisierung(self, lib):
        """Typ wird auf erlaubte Werte normalisiert."""
        item = PromptItem(id="", typ="SKILL", name="Skill-Test", content="x")
        gespeichert = lib.upsert(item)
        geladen = lib.get(gespeichert.id)
        assert geladen.typ == "skill"

    def test_ungueltiger_typ_faellt_auf_prompt_zurueck(self, lib):
        item = PromptItem(id="", typ="UNBEKANNT", name="Fallback", content="x")
        gespeichert = lib.upsert(item)
        geladen = lib.get(gespeichert.id)
        assert geladen.typ == "prompt"


# ---------------------------------------------------------------------------
# liste mit Filtern
# ---------------------------------------------------------------------------

class TestListe:
    def _fuege_items_ein(self, lib):
        """Hilfsmethode: 3 Einträge verschiedener Typen einfügen."""
        lib.upsert(PromptItem(id="", typ="prompt", name="Erklärungs-Prompt",
                              content="Erkläre mir ...", tags=["erklärung", "basis"]))
        lib.upsert(PromptItem(id="", typ="skill", name="Code-Review-Skill",
                              content="Prüfe den Code auf ...", tags=["code", "review"]))
        lib.upsert(PromptItem(id="", typ="workflow", name="Recherche-Workflow",
                              content="Schritt 1: Thema definieren ...", tags=["recherche"]))

    def test_liste_alle(self, lib):
        self._fuege_items_ein(lib)
        ergebnis = lib.liste()
        assert len(ergebnis) == 3

    def test_liste_filter_typ(self, lib):
        self._fuege_items_ein(lib)
        skills = lib.liste(typ="skill")
        assert len(skills) == 1
        assert skills[0].typ == "skill"

    def test_liste_filter_typ_leer(self, lib):
        self._fuege_items_ein(lib)
        agenten = lib.liste(typ="agent")
        assert agenten == []

    def test_liste_filter_tag(self, lib):
        self._fuege_items_ein(lib)
        code_items = lib.liste(tag="code")
        assert len(code_items) == 1
        assert "code" in code_items[0].tags

    def test_liste_filter_tag_case_insensitiv(self, lib):
        self._fuege_items_ein(lib)
        assert lib.liste(tag="REVIEW") == lib.liste(tag="review")

    def test_liste_filter_suche_im_name(self, lib):
        self._fuege_items_ein(lib)
        ergebnis = lib.liste(suche="Erklärungs")
        assert len(ergebnis) == 1

    def test_liste_filter_suche_im_content(self, lib):
        self._fuege_items_ein(lib)
        ergebnis = lib.liste(suche="Prüfe den Code")
        assert len(ergebnis) == 1
        assert ergebnis[0].typ == "skill"

    def test_liste_filter_suche_case_insensitiv(self, lib):
        self._fuege_items_ein(lib)
        gross = lib.liste(suche="CODE")
        klein = lib.liste(suche="code")
        assert len(gross) == len(klein)

    def test_liste_kombinierter_filter_typ_und_suche(self, lib):
        self._fuege_items_ein(lib)
        # typ=prompt, suche trifft auch workflow → nur prompt sollte zurückkommen
        ergebnis = lib.liste(typ="prompt", suche="Erkläre")
        assert len(ergebnis) == 1
        assert ergebnis[0].typ == "prompt"

    def test_liste_leer_bei_keinen_eintraegen(self, lib):
        assert lib.liste() == []


# ---------------------------------------------------------------------------
# loesche
# ---------------------------------------------------------------------------

class TestLoesche:
    def test_loesche_vorhandenen_eintrag(self, lib, beispiel_item):
        gespeichert = lib.upsert(beispiel_item)
        ergebnis = lib.loesche(gespeichert.id)
        assert ergebnis is True
        assert lib.get(gespeichert.id) is None

    def test_loesche_gibt_false_bei_unbekannter_id(self, lib):
        assert lib.loesche("nicht-vorhanden") is False

    def test_loesche_entfernt_nur_zielobjekt(self, lib):
        a = lib.upsert(PromptItem(id="", typ="prompt", name="A", content="inhalt a"))
        b = lib.upsert(PromptItem(id="", typ="prompt", name="B", content="inhalt b"))
        lib.loesche(a.id)
        assert lib.get(b.id) is not None


# ---------------------------------------------------------------------------
# copy_text
# ---------------------------------------------------------------------------

class TestCopyText:
    def test_copy_text_gibt_content_zurueck(self, lib, beispiel_item):
        gespeichert = lib.upsert(beispiel_item)
        text = lib.copy_text(gespeichert.id)
        assert text == beispiel_item.content

    def test_copy_text_gibt_leer_bei_unbekannter_id(self, lib):
        assert lib.copy_text("nicht-vorhanden") == ""


# ---------------------------------------------------------------------------
# import_promptboard
# ---------------------------------------------------------------------------

class TestImportPromptboard:
    def _erstelle_library_json(self, pfad: Path, items: list) -> Path:
        json_pfad = pfad / "library.json"
        json_pfad.write_text(
            json.dumps({"items": items}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return json_pfad

    def test_import_zaehlt_eintraege(self, lib, tmp_path):
        items = [
            {
                "id": "abc1",
                "item_type": "PROMPT",
                "name": "Erster Prompt",
                "content": "Inhalt eins",
                "category": "Allgemein",
                "tags": ["tag1"],
                "source": "promptboard",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "id": "abc2",
                "item_type": "SKILL",
                "name": "Zweiter Skill",
                "content": "Inhalt zwei",
                "category": "Code",
                "tags": ["code", "review"],
                "source": "promptboard",
                "created_at": "2026-01-02T00:00:00+00:00",
                "updated_at": "2026-01-02T00:00:00+00:00",
            },
        ]
        json_pfad = self._erstelle_library_json(tmp_path, items)
        anzahl = lib.import_promptboard(json_pfad)
        assert anzahl == 2

    def test_import_eintraege_aufrufbar_via_liste(self, lib, tmp_path):
        items = [
            {
                "id": "x1",
                "item_type": "WORKFLOW",
                "name": "Mein Workflow",
                "content": "Schritt 1 ...",
                "category": "Prozess",
                "tags": ["workflow"],
                "source": "",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "id": "x2",
                "item_type": "ROLLE",
                "name": "Reviewer-Rolle",
                "content": "Du bist ein erfahrener Reviewer ...",
                "category": "Rollen",
                "tags": ["rolle", "review"],
                "source": "",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            },
        ]
        json_pfad = self._erstelle_library_json(tmp_path, items)
        lib.import_promptboard(json_pfad)

        alle = lib.liste()
        assert len(alle) == 2

        typen = {item.typ for item in alle}
        assert "workflow" in typen
        assert "rolle" in typen

    def test_import_typ_mapping_lowercase(self, lib, tmp_path):
        """PROMPT → prompt, SKILL → skill, WORKFLOW → workflow etc."""
        items = [
            {"id": "t1", "item_type": "PROMPT", "name": "P",
             "content": "c", "category": "", "tags": [], "source": "",
             "created_at": "2026-01-01T00:00:00+00:00",
             "updated_at": "2026-01-01T00:00:00+00:00"},
            {"id": "t2", "item_type": "AGENT", "name": "A",
             "content": "c", "category": "", "tags": [], "source": "",
             "created_at": "2026-01-01T00:00:00+00:00",
             "updated_at": "2026-01-01T00:00:00+00:00"},
        ]
        json_pfad = self._erstelle_library_json(tmp_path, items)
        lib.import_promptboard(json_pfad)
        typen = {item.typ for item in lib.liste()}
        assert typen == {"prompt", "agent"}

    def test_import_namenskollision_neuer_eintrag(self, lib, tmp_path):
        """Beim Import wird KEIN bestehender Eintrag überschrieben.

        Gleicher Name → neuer Eintrag mit eigener ID.
        """
        # Vorhandener Eintrag
        bestehend = lib.upsert(PromptItem(
            id="", typ="prompt", name="Duplikat-Test", content="Original"
        ))
        items = [
            {
                "id": "dup1",
                "item_type": "PROMPT",
                "name": "Duplikat-Test",
                "content": "Import-Version",
                "category": "",
                "tags": [],
                "source": "",
                "created_at": "2026-01-01T00:00:00+00:00",
                "updated_at": "2026-01-01T00:00:00+00:00",
            }
        ]
        json_pfad = self._erstelle_library_json(tmp_path, items)
        lib.import_promptboard(json_pfad)

        # Beide Einträge müssen vorhanden sein
        alle = lib.liste()
        assert len(alle) == 2
        inhalte = {item.content for item in alle}
        assert "Original" in inhalte
        assert "Import-Version" in inhalte

    def test_import_leere_datei(self, lib, tmp_path):
        json_pfad = self._erstelle_library_json(tmp_path, [])
        anzahl = lib.import_promptboard(json_pfad)
        assert anzahl == 0
        assert lib.liste() == []
