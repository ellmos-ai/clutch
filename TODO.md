# TODO - clutch

Public-readiness was completed before the repository was published as
`ellmos-ai/clutch`. This file now tracks follow-up work for a public,
provider-neutral LLM orchestration library.

## Current

- [ ] Keep German code identifiers as the stable domain language, but make all
  contributor-facing explanations bilingual or English-first.
- [ ] Review `demo.py`, `live_test.py`, and `claude_code_test.py` as manual
  provider smoke scripts; keep them out of normal `pytest` collection.
- [ ] Add focused tests for provider availability checks without requiring live
  Anthropic, Google, Ollama, or Claude Code credentials.
- [ ] Decide whether `clutch/config/` display strings should stay German or gain parallel
  English descriptions.
- [ ] Verify current provider model IDs before the next release.

## STATUS

| Category | Status | Notes |
|----------|--------|-------|
| Secrets | PASS | Gate check found no secret patterns in tracked files. |
| Private Data (PII) | PASS | Gate check found no known PII patterns. |
| .gitignore | PASS | Minimum release entries are present, including explicit `*.pyc`. |
| Language (English) | PASS | README is English-first; German domain terms are intentional. |
| BACH Internals | PASS | BACH-internal release blocker files are absent. |
| Database Files | PASS | No tracked `.db` files. |
| README.md | PASS | Public README is present. |
| LICENSE | PASS | MIT license is present. |
| Overall | READY | Public repository is already published; current follow-ups are non-blocking. |

## Done

- [x] Removed BACH-internal public-readiness blockers before publication.
- [x] Kept German identifiers as intentional domain language.
- [x] Published public repository under `ellmos-ai/clutch`.
- [x] Added `llms.txt` for LLM crawler discovery.
- [x] Added `GLOSSARY.md` for contributor orientation.
