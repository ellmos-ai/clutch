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

## Done

- [x] Removed BACH-internal public-readiness blockers before publication.
- [x] Kept German identifiers as intentional domain language.
- [x] Published public repository under `ellmos-ai/clutch`.
- [x] Added `llms.txt` for LLM crawler discovery.
- [x] Added `GLOSSARY.md` for contributor orientation.
