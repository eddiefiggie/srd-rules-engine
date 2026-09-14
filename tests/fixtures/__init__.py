"""Invented rules, an invented creature, and the harness that runs one encounter.

Everything here is fixture provenance and nothing here states an SRD value. That is not
tidiness: a plausible number sitting in a test is indistinguishable from a verified one the
moment somebody copies it out, and the verified ones live where their `Verification` block
and their row in `scripts/verify_d20_rules.py` can be found — `core.save_ends`,
`core.hazards`, `data/bestiary.json`. The rule is R31 — a visible gap beats a confident
wrong number. (This said [#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3)
was open until build `09142026.1`; it closed on 2026-08-23.)

The loader enforces the separation rather than trusting it: `load_fixture_ruleset` refuses
SRD provenance and `load_ruleset` refuses fixture provenance, so these rules cannot reach a
shipped ruleset even by accident.
"""
