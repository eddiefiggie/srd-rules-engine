# Changelog

Builds are stamped `mmddyyyy.x` — the date they were produced, plus that day's iteration. The
stamp lives in `src/srd_rules_engine/__init__.py`; `tests/test_build_stamp.py` fails CI when
README.md's `**Current build:**` line drifts from it.

Nothing is released yet. Entries below record builds, not releases.

## 08212026.1 — 2026-08-21

Repository established. Scaffolding, governance, and CI only — no engine code.

- Repository initialised from the requirements-only plan produced 2026-08-19.
- MIT for the engine's own code; SRD 5.2 material remains CC BY 4.0 with the attribution
  wording gated until it's verified against the published document (`NOTICE.md`). **No
  SRD-derived content has been committed.**
- `AGENTS.md` (linked as `CLAUDE.md`): the architectural invariant, the issues-are-the-queue
  rule, standing rules, and the non-goals.
- `CONCEPTS.md`: shared vocabulary, each term traced to its requirement.
- Two guard tests that make promises mechanical rather than remembered — the README build stamp
  matching the package version, and R33's empty core dependency list.
- CI across Python 3.11–3.13 running `pytest`, `ruff`, and `mypy --strict`.
- The plan's ten outstanding questions, its attribution dependency, and its four deferred scope
  items filed as issues, per the rule that a plan's deferrals are filed before they can be
  forgotten. Each is annotated with its issue number in the plan itself.
- Six coverage epics filed against v1.0, one per SRD subsystem, plus the effect-shape inventory
  (#14) that makes "full coverage" falsifiable at all — filed against M0 instead, because the
  other six are unscoreable until it exists.
