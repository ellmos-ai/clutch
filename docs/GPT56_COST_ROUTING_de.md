# GPT-5.6-Kosten und empirisches Routing

Datenstatus: **offizielle Katalog- und Preisfakten, geprüft am 20.08.2026**. Leistungsstatus: **in diesem Dokument nicht gemessen**. Die generierte [Preisgrafik](gpt56_price_facts.svg) entsteht ausschließlich aus `clutch/config/getriebe.json`:

```powershell
python docs/generate_gpt56_price_facts.py
```

## Katalog und API-Transport

clutch führt `gpt-5.6-luna`, `gpt-5.6-terra` und `gpt-5.6-sol`. Alle drei unterstützen `none`, `low`, `medium` (Standard), `high`, `xhigh` und `max`. OpenAI-Aufrufe verwenden die Responses API. `FahrtConfig.effort` protokolliert den angeforderten Wert, `effective_effort` den tatsächlich gesendeten Wert. `max-delegate` ist nur ein clutch-Orchestrierungshinweis und niemals ein API-Wert: Erst bei einem ausdrücklich mit `is_delegate=True` markierten Aufruf wird daraus `max`; andernfalls schlägt der Aufruf geschlossen fehl.

Ein höherer Effort erlaubt mehr Reasoning. Er garantiert weder monoton mehr sichtbare Tokens noch universell bessere Ergebnisse. Jede Modell-/Effort-Kombination ist deshalb ein empirischer Kandidat für eine konkrete Aufgabenklasse.

## Versionierte Preisberechnung

Die einzige Preisquelle im Code ist das verschachtelte `pricing`-Objekt jedes Katalogeintrags. Alle Beträge sind USD pro eine Million Tokens:

| Modell | Input | Cached Input | Output |
|---|---:|---:|---:|
| GPT-5.6 Luna | 0,20 $ | 0,02 $ | 1,20 $ |
| GPT-5.6 Terra | 2,00 $ | 0,20 $ | 12,00 $ |
| GPT-5.6 Sol | 5,00 $ | 0,50 $ | 30,00 $ |

Cache-Schreibvorgänge kosten das 1,25-Fache von uncached Input. Oberhalb von 272.000 Input-Tokens gilt für die gesamte Anfrage: Input-Raten mal 2, Output-Raten mal 1,5. Standard/default hat den Faktor 1; Fast/priority den Faktor 2 für Modell-Tokens. Tool-Gebühren bleiben separat. Reasoning-Tokens sind bereits in den Output-Tokens enthalten und werden niemals ein zweites Mal berechnet.

Vom Provider gemeldete Usage ist `observed`; Eingaben in den Rechner sind standardmäßig `assumed`. Fehlt Usage, bleiben `usage_status=unknown` und `cost_usd=null`—niemals eine erfundene Null.

```powershell
clutch cost --model gpt-5.6-terra --input 100000 --cached-input 20000 --output 10000 --json
clutch cost --model gpt-5.6-sol --input 300000 --output 20000 --service-tier fast --data-status assumed --json
```

Laufzeit, SQLite-Telemetrie, Tankuhr, CLI-JSON, Web-Modell-JSON und Statistik verwenden denselben Rechner oder dessen persistiertes Ergebnis. Pro Fahrt werden Modell, angeforderter/effektiver Effort, Modus, Service-Tier, Aufgabenklasse/Eval-Fall, alle Token-Kategorien, Tool-Gebühren, Preisversion, Kosten und Usage-Status gespeichert.

## Empirische Routenauswahl

`clutch/config/eval_profiles.json` definiert reproduzierbare Fälle, Gates und das vollständige Kandidatenraster, aber keine erfundenen Qualitätswerte. Nur extern gelabelte Läufe mit beobachteter Usage und bekannten Kosten gelangen ins empirische Routing:

1. Mindeststichprobe, Qualitäts-/Pass-Rate-Gate und Latenzgrenze müssen erfüllt sein.
2. Retry- und Fallback-Ausgaben zählen zu den erwarteten Kosten pro erfolgreicher Aufgabe.
3. Daraus entsteht die nicht dominierte Qualitäts-/Kosten-/Latenz-Pareto-Frontier.
4. Gewählt wird die Route mit den geringsten erwarteten Kosten pro Erfolg auf dieser Frontier.

Ohne ausreichende Daten wird die Entscheidung als `cold_start` markiert und verwendet die veröffentlichten Rollen: Luna für volumen-/kostensensitive Arbeit, Terra für Ausgewogenheit und Sol für komplexe professionelle Arbeit. Sol gilt nur dann als empirisch erforderlich, wenn ausreichend geprüfte Nicht-Sol-Kandidaten das Gate verfehlen und Sol es erfüllt. Es gibt keine statische Modell-/Effort-Intelligence-Matrix und kein Polling von Launch-Benchmarks.

## Aktualisierungsroutine

1. Live-Modellseiten, den Latest-Model-Guide und das offizielle Preisupdate prüfen.
2. Raten, `version`, `effective_at`, `checked_at` und `source_url` gemeinsam in `getriebe.json` aktualisieren.
3. SVG neu erzeugen und `pytest`, `ruff check .`, `python -m compileall -q clutch` sowie `git diff --check` ausführen.
4. `clutch models --no-discovery --json` prüfen; nach Ablauf des Frischefensters signalisiert `pricing_stale=true` sichtbar veraltete Preise.

Offizielle Quellen: [Modellkatalog](https://developers.openai.com/api/docs/models), [Latest-Model-Guide](https://developers.openai.com/api/docs/guides/latest-model), [Sol](https://developers.openai.com/api/docs/models/gpt-5.6-sol), [Terra](https://developers.openai.com/api/docs/models/gpt-5.6-terra), [Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna) und das [offizielle Preis-/Leistungsupdate](https://openai.com/index/advancing-the-price-performance-frontier-with-gpt-5-6/).

## Historische Nutzerbilder

Die folgenden Basisdateinamen sind nur Referenzen und wurden nicht als Produktionsdaten importiert:

- `kosten leistung gpt 5.6 modell und effort.png` — SHA-256 `2649c2caa1b9cc041db97c9edd2734d1ada7c5e9a4f98ade04d112781e40366c`; unverifizierter historischer Input.
- `Äquivalenzstufen gpt 5.6.png` — SHA-256 `6450f373a9e1ec9b842cd2a6fce4cdcdffa4d6496fb46c0f5bea1fa47bd8bd8c`; unverifizierter historischer Input.

Kein privater absoluter Pfad wird gespeichert.
