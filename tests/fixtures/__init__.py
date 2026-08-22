"""Invented rules, an invented creature, and the harness that runs one encounter.

Everything here is fixture provenance and nothing here states an SRD value. That is not
tidiness: [#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3) is open, so no
number in this repository has been checked against the official document, and a plausible
one sitting in a test would be indistinguishable from a verified one the moment somebody
copied it out. The rule is R31 — a visible gap beats a confident wrong number.

The loader enforces the separation rather than trusting it: `load_fixture_ruleset` refuses
SRD provenance and `load_ruleset` refuses fixture provenance, so these rules cannot reach a
shipped ruleset even by accident.
"""
