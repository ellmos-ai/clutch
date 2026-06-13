"""Regressionstest: globales --lang vor einem Subcommand (Positional-Erkennung)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from clutch import cli


def test_lang_vor_subcommand_de(capsys):
    rc = cli.main(["--lang", "de", "route", "Fix den Bug"])
    out = capsys.readouterr().out
    assert rc == 0
    # Deutscher Header, NICHT in den Prompt-Modus gerutscht
    assert "Routing-Entscheidung" in out
    assert "de route" not in out  # der --lang-Wert darf nicht im Prompt landen


def test_lang_vor_subcommand_en(capsys):
    rc = cli.main(["--lang", "en", "route", "Fix the bug"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Routing decision" in out


def test_ohne_lang_weiter_subcommand(capsys):
    rc = cli.main(["route", "Fix den Bug"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Routing" in out


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
