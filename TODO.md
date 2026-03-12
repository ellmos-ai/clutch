# TODO — clutch (Kupplung)

Public-readiness checklist before switching repo `lukisch/clutch` from private to public.

---

## BLOCKER (must fix before public)

### 1. Remove BACH-internal documents
- [ ] `git rm BACH_EINHÄNGEPUNKTE.md` — internal BACH integration doc, not relevant for public
- [ ] `git rm BACH_INTEGRATION.md` — internal BACH architecture doc, not relevant for public
- [ ] Add both to `.gitignore` to prevent re-commit

### 2. Language decision for code identifiers
The entire codebase uses German identifiers (Fahrer, Getriebe, Kupplung, etc.) as a deliberate automotive metaphor. **Decide one of:**

- **Option A (recommended):** Keep German identifiers as domain language, translate only:
  - [ ] All docstrings → English
  - [ ] All comments → English
  - [ ] All print statements in `demo.py`, `live_test.py`, `claude_code_test.py` → English
  - [ ] Description fields in `config/*.json` → English
  - [ ] Estimated effort: 2-4h

- **Option B:** Full English refactor (rename all classes, methods, variables, configs)
  - Estimated effort: 8-12h, high risk of regressions

---

## HIGH PRIORITY

### 3. Translate user-facing strings
- [ ] `demo.py` — German print statements ("Tschuess!", "Verfuegbare Motoren", "ZUSAMMENFASSUNG")
- [ ] `live_test.py` — German output text
- [ ] `claude_code_test.py` — German output text

### 4. Translate config descriptions
- [ ] `config/strecken.json` — German `beschreibung` fields
- [ ] `config/kupplung.json` — German field names (fahrschule, tankuhr, erkundungsrate)
- [ ] `config/getriebe.json` — German fields (gaenge, leistung, staerken, schwaechen)
- [ ] `config/fitness_criteria.json` — check for German content

### 5. Verify pyproject.toml author email
- [ ] Confirm `lukas@lukisch.dev` is intentionally public (currently in `pyproject.toml` line 13)

---

## LOW PRIORITY

### 6. Translate Python docstrings and comments
Files with German docstrings/comments (all under `kupplung/`):
- [ ] `fahrer.py`
- [ ] `strecke.py`
- [ ] `getriebe.py`
- [ ] `kupplung.py`
- [ ] `gas_bremse.py`
- [ ] `fahrtenbuch.py`
- [ ] `bordcomputer.py`
- [ ] `tankuhr.py`
- [ ] `tacho.py`
- [ ] `fahrschule.py`
- [ ] `motorblock.py`
- [ ] `patterns/kolonne.py`
- [ ] `patterns/team.py`
- [ ] `patterns/schwarm.py`
- [ ] `patterns/hybrid.py`

### 7. Add English inline glossary
- [ ] Consider adding a `GLOSSARY.md` mapping German terms → English equivalents for international contributors

---

## STATUS

| Check          | Result |
|----------------|--------|
| Secrets        | PASS — no hardcoded keys |
| Private data   | PASS — only standard author info |
| BACH internals | FAIL — 2 files to remove |
| Bilingual      | FAIL — code is German, docs are English |
| **Overall**    | **NOT READY for public** |

Last audited: 2026-03-12
