# Engineering Lessons

## 2026-02-13 - Bakeoff Selection Test Assumptions

- Issue: A test incorrectly assumed baseline (`hash-bow-v1`) would always be selected in embedding bakeoff runs.
- Root cause: The selection gate can validly choose a substitute candidate on small corpora when quality/safety criteria are met.
- Rule going forward: Tests for selection systems must validate gate semantics (eligible candidate + qualification evidence), not hardcode one winner unless the spec explicitly requires deterministic winner lock.
- Applied in: `tests/test_embedding_bakeoff.py`
