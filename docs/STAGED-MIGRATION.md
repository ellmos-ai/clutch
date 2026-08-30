# Staged Migration: Anthropic Session-Fenster als Zweite Tankuhr-Dimension

**Status:** Stufe 1 aktiv (Schattenmodus). Seit clutch 0.6.0 existiert daneben
eine eng begrenzte rote Verfügbarkeitssperre (siehe unten), aber weiterhin
keine EMA-basierte Boost-/Drossel-Migration. **User-Entscheidung:** T1=E
(USMC-Notiz 923, aus Ticket `T-20260825-322087069`, umgesetzt in
`T-20260825-939511775`).

## Worum es geht

Zwei unabhängige Budget-Systeme laufen heute nebeneinander, ohne dass eines
vom anderen weiß:

1. **Tankuhr** (`clutch/tankuhr.py`) trackt USD-Kosten pro Provider über alle
   Tools/Agenten hinweg -- kein Bezug zu einem bestimmten Account-Limit.
2. **sparmodus/notaus** (`~/.claude/hooks/token_budget_guard.py`) beobachtet
   das kontobasierte Anthropic-Session-Limit (5h-Fenster, `rate_limits.
   five_hour.used_percentage` aus der Claude-Code-Statusline) und schaltet bei
   Schwellen (Default 50/80/90 %) Sparmodus- bzw. Notaus-Verhalten.

Architektonisch ist das Boosten/Drosseln nach Durchsatz eigentlich
**Routing-Politik** -- also eine Aufgabe von clutch, nicht von sparmodus. Die
Migration dorthin geschieht **gestuft**, nicht in einem Schritt, weil
sparmodus/notaus heute die einzige *verlässliche* Notbremse sind und das
bleiben müssen, bis clutch nachweislich denselben Job zuverlässig erledigt.

## Die drei Stufen

### Sicherheits-Gate seit 0.6.0 (W195, keine Vorwegnahme von Stufe 2/3)

`Bordcomputer.pruefe()` liest ein frisches rotes 5h- **oder** 7d-Signal als
harte Provider-Nichtverfügbarkeit und persistiert die Sperre mit Reset-Zeit in
`~/.clutch/availability.json`. Gleiches gilt für `sparmodus mode=notaus`.
Fehlende oder veraltete Bridge-Daten erzeugen keine neue Sperre; ein zuvor
belegter roter Zustand bleibt bis `until` wirksam.

Dieses Gate bewertet weder EMA-Rate noch Verbrauchstrend und ersetzt keinen
Hook. Vor W195 war kein `clutch_shadow_protocol.jsonl` vorhanden; damit war das
unten definierte Reifekriterium nicht belegbar. Die allgemeine
Boost-/Drossel-Strategie bleibt deshalb unverändert in Stufe 1.

### Stufe 1 -- Schattenmodus (AKTIV, dieses Ticket)

- Ein neues, eigenständiges Modul `clutch/token_throughput.py` liest die
  bestehende Bridge-Datei (`~/.claude/state/token_budget.json`, geschrieben
  von `token_budget_statusline.py`) **read-only**, führt ein eigenes
  Rolling-Log (`~/.claude/state/token_throughput_log.jsonl`) und berechnet
  daraus eine EMA-geglättete Durchsatzrate (Prozentpunkte/Stunde) -- Vorbild:
  Antigravity `token_analytics_engine` (7d-Burn-Rate).
- `Tankuhr.anthropic_schatten_stand()` ist eine **neue, rein optionale**
  Methode, die diese Werte plus eine informative Zonen-Einordnung
  (green/yellow/orange/red, dieselben Schwellen wie sparmodus) zurückgibt.
  Sie wird nirgendwo automatisch aufgerufen und beeinflusst `stand()`,
  `zone()`, `verbrauch_pct()` oder irgendeine Gas/Bremse-Entscheidung **nicht**.
- Ein **Schatten-Protokoll** (`~/.claude/state/clutch_shadow_protocol.jsonl`,
  via `record_shadow_decision()` bzw. `anthropic_schatten_stand(record_
  shadow_log=True)`) hält fest, was die Schatten-Zone **vorgeschlagen hätte**
  vs. was sparmodus **real** getan hat -- reine Beobachtung, kein Eingriff.
- **Nichts an bestehendem Hook-Verhalten ändert sich.** Keine Datei in
  `~/.claude/hooks/` oder `~/.claude/settings.json` wird angefasst; die
  bestehenden Zustandsdateien (`token_budget_guard_state.json`,
  `sparmodus_state.json`) werden höchstens gelesen, nie geschrieben.

### Stufe 2 -- Beobachtungsfenster (geplant, eigenes Folgeticket)

- Das Schatten-Protokoll aus Stufe 1 wird über einen längeren Zeitraum
  ausgewertet: Wie oft weicht die Schatten-Zone vom realen sparmodus-Modus
  ab? Gibt es Fehlalarme (Schatten-Zone rot, aber kein echter Engpass) oder
  verpasste Warnungen (Schatten-Zone grün, aber sparmodus musste eskalieren)?
- Erst wenn das Reifekriterium (unten) erfüllt ist, beginnt clutch, das
  Signal **aktiv** für Boost-/Drossel-Entscheidungen zu nutzen (z. B.
  Gang-Wahl in `getriebe.py`/`gas_bremse.py` an die EMA-Rate koppeln) --
  weiterhin **parallel** zu sparmodus/notaus, nicht anstelle davon.

### Stufe 3 -- Strategie-Migration (geplant)

- sparmodus wird auf eine reine **Verhaltens-/Textstufe** reduziert (Kurztext-
  Hinweise, Kommunikationsstil), die eigentliche Routing-Entscheidung
  (welches Modell, wie viel Parallelität) liegt vollständig bei clutch.
- notaus bleibt als **Reflex- und Fail-Safe-Mechanismus dauerhaft lokal** in
  den Hooks bestehen -- eine harte Notbremse, die auch dann noch greift, wenn
  clutch aus irgendeinem Grund nicht erreichbar oder fehlkonfiguriert ist.
  Diese Rolle wird **nie** vollständig an clutch abgegeben.

## Reifekriterium für den Übergang Stufe 1 → Stufe 2

Stufe 1 gilt als "reif genug" für Stufe 2, wenn **alle** der folgenden
Bedingungen erfüllt sind:

1. **Mindestens 14 aufeinanderfolgende Tage** mit aktivem Schatten-Protokoll
   ohne Datenlücken von mehr als 24 h (Bridge-Datei muss regelmäßig
   geschrieben worden sein -- eine interaktive Session mit Statusline muss in
   diesem Zeitraum wiederholt gelaufen sein).
2. **Keine EMA-Ausreißer**, die bei einer manuellen Stichprobe (mindestens 10
   Zufallspunkte aus dem Rolling-Log) als offensichtlich falsch (z. B.
   physikalisch unmögliche Raten, negative Prozentwerte, NaN) auffallen.
3. **Übereinstimmungsrate zwischen Schatten-Zone und realem sparmodus-Modus
   von mindestens 90 %** über den Beobachtungszeitraum (`agreement`-Feld im
   Schatten-Protokoll) -- Abweichungen sind erwartbar (sparmodus reagiert auf
   User-Kommandos, die Zone rein auf den 5h-Wert), aber eine systematische
   Diskrepanz zeigt, dass die Schatten-Zone kein verlässliches Signal ist.
4. **Keine Regression der bestehenden Tests** (`tests/test_clutch.py`,
   `tests/test_m13_token_throughput.py`) über den gesamten Zeitraum.

Das Reifekriterium wird **nicht automatisch geprüft** -- es ist eine
menschliche Entscheidung auf Basis der geloggten Daten, dokumentiert als
Folgeticket zu Stufe 2.

## Was Stufe 1 bewusst NICHT tut

- Keine Änderung an `token_budget_guard.py`, `token_budget_statusline.py`
  oder einer der Sparmodus-Skills (`skills/sparmodus`, `skills/notaus`).
- Keine neue Hook-Registrierung in `~/.claude/settings.json`.
- Keine automatische EMA-/Schattenentscheidung --
  `anthropic_schatten_stand()` muss aktiv aufgerufen werden, sonst passiert
  dort nichts. Davon getrennt ist ausschließlich das oben dokumentierte harte
  rote Verfügbarkeits-Gate aktiv.
- Kein Ersatz für sparmodus/notaus als Notbremse -- die bleibt unverändert
  wirksam, solange Stufe 1/2 läuft.
