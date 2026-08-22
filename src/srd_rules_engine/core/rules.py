"""Rule definitions, their verification state, and the two loaders that admit them.

R31 requires every SRD-derived mechanic to be verified against the official SRD v5.2.1
before it is trusted, and R32 requires a failed verification to be *excluded and
disclosed* rather than silently dropped. This is where both are enforced.

**Provenance selects the entry point, not a branch inside one.** `load_ruleset` admits
SRD-derived rules that are verified and refuses any fixture outright; `load_fixture_ruleset`
admits fixtures and refuses any SRD-derived rule outright. There is no mode flag, so
widening one cannot widen the other.

That shape exists because correctness was never the weak point. A single loader with a
strict arm and a lenient arm *reads* as an inconsistency to anyone who has not read the
reasoning, and the natural repair is to loosen it — which would admit unverified SRD
entries and reproduce the exact defect the seed decision exists to prevent.

The two share parsing, shape validation, and R21's core-fact-type check, so a fixture
ruleset exercises the real machinery rather than a construction path production never uses.

A rule declares the fact types it consumes, and **may declare core types only** (R21).
A namespaced extension type is a load-time error rather than a runtime failure: it is a
defect in the definition and should be impossible to ship, not merely impossible to hit.

See `docs/decisions/0012-fixture-provenance.md` and
`docs/decisions/0003-seed-and-verification.md`.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType

from srd_rules_engine.core.memory_port import is_extension

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class RuleLoadError(Exception):
    """A rule definition is malformed, or a loader refused it. Never a rules status."""


class RuleProvenance(StrEnum):
    """Where a rule came from, which is what selects the loader that may admit it."""

    SRD = "srd"
    FIXTURE = "fixture"


class VerificationState(StrEnum):
    """R31/R32. Only `verified` reaches the engine, and an exclusion is disclosed."""

    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    EXCLUDED = "excluded"


@dataclass(frozen=True)
class Verification:
    """What was checked, against what, and when — or why the entry was excluded."""

    state: VerificationState
    reference: str | None = None
    date: str | None = None
    reason: str | None = None

    def __post_init__(self) -> None:
        if self.state is VerificationState.VERIFIED:
            if not self.reference:
                raise RuleLoadError(
                    "a verified entry names the SRD v5.2.1 section it was verified against"
                )
            if not self.date or not _ISO_DATE.match(self.date):
                raise RuleLoadError("a verified entry carries the ISO date it was verified on")
        if self.state is VerificationState.EXCLUDED and not self.reason:
            raise RuleLoadError(
                "an excluded entry states why it failed. R32 excludes and discloses; "
                "an exclusion with no reason is a silent drop wearing a label"
            )


@dataclass(frozen=True)
class Rule:
    """One mechanic, with the facts it consumes and the provenance that governs it."""

    id: str
    summary: str
    provenance: RuleProvenance
    consumes: tuple[str, ...] = ()
    verification: Verification | None = None
    rationale: str | None = None

    def __post_init__(self) -> None:
        if not self.id or not self.summary:
            raise RuleLoadError("a rule carries an id and a summary")

        for fact_type in self.consumes:
            if is_extension(fact_type):
                raise RuleLoadError(
                    f"{self.id!r} declares {fact_type!r}, which carries a namespace and is "
                    "therefore an extension type. A rule may declare core fact types only, "
                    "so no consumer-defined fact can move an outcome"
                )

        if self.provenance is RuleProvenance.SRD:
            if self.verification is None:
                raise RuleLoadError(
                    f"{self.id!r} is SRD-derived and carries no verification block. Its state "
                    "against SRD v5.2.1 is the whole basis for trusting it"
                )
            if self.rationale is not None:
                raise RuleLoadError(
                    f"{self.id!r} is SRD-derived, so it cites a section rather than a rationale"
                )
        else:
            if not self.rationale:
                raise RuleLoadError(
                    f"{self.id!r} is a fixture and carries no rationale. It has nothing to "
                    "verify against, so what it is for is the only account of it there is"
                )
            if self.verification is not None:
                raise RuleLoadError(
                    f"{self.id!r} is a fixture, so it has nothing to verify against and may "
                    "not carry a verification block"
                )

    @property
    def is_verified(self) -> bool:
        return self.verification is not None and self.verification.state is (
            VerificationState.VERIFIED
        )


@dataclass(frozen=True)
class Ruleset:
    """A loaded set of rules, and the provenance every member of it shares."""

    provenance: RuleProvenance
    rules: Mapping[str, Rule]
    name: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "rules", MappingProxyType(dict(self.rules)))

    def __iter__(self) -> Iterator[Rule]:
        return iter(self.rules.values())

    def __len__(self) -> int:
        return len(self.rules)

    def __contains__(self, rule_id: object) -> bool:
        return rule_id in self.rules

    def rule(self, rule_id: str) -> Rule:
        try:
            return self.rules[rule_id]
        except KeyError:
            raise RuleLoadError(f"no rule {rule_id!r} in this ruleset") from None


def load_ruleset(rules: Iterable[Rule]) -> Ruleset:
    """Admit SRD-derived rules that are verified. Refuses a fixture outright.

    Refusing a fixture is a matter of identity rather than policy: this loader does not
    accept fixture provenance at all, so loosening the fixture loader cannot make an
    unverified SRD entry admissible here.
    """

    def gate(rule: Rule) -> None:
        if rule.provenance is not RuleProvenance.SRD:
            raise RuleLoadError(
                f"{rule.id!r} carries {rule.provenance} provenance and cannot be loaded as "
                "SRD-derived. Fixtures are admitted only by load_fixture_ruleset, which "
                "refuses SRD-derived rules in turn"
            )
        assert rule.verification is not None  # guaranteed by Rule.__post_init__
        state = rule.verification.state
        if state is VerificationState.EXCLUDED:
            raise RuleLoadError(
                f"{rule.id!r} is excluded: {rule.verification.reason}. R32 discloses an "
                "exclusion rather than dropping it silently"
            )
        if state is not VerificationState.VERIFIED:
            raise RuleLoadError(
                f"{rule.id!r} is {state} and does not reach the engine. Only an entry "
                "verified against SRD v5.2.1 is trusted"
            )

    return Ruleset(provenance=RuleProvenance.SRD, rules=_admit(rules, gate))


def load_fixture_ruleset(name: str, rules: Iterable[Rule]) -> Ruleset:
    """Admit invented rules for tests. Refuses an SRD-derived rule outright.

    The name is required so a fixture ruleset is always asked for deliberately, never
    reached by default.
    """
    if not name:
        raise RuleLoadError("a fixture ruleset is named, so it is always asked for by name")

    def gate(rule: Rule) -> None:
        if rule.provenance is not RuleProvenance.FIXTURE:
            raise RuleLoadError(
                f"{rule.id!r} carries {rule.provenance} provenance and cannot be loaded as a "
                "fixture. SRD-derived rules are admitted only by load_ruleset, which applies "
                "the verification gate"
            )

    return Ruleset(provenance=RuleProvenance.FIXTURE, rules=_admit(rules, gate), name=name)


def _admit(rules: Iterable[Rule], gate: Callable[[Rule], None]) -> dict[str, Rule]:
    """Shared by both loaders: collect, refuse duplicates, and apply the caller's gate.

    Everything except the gate lives here, which is what makes a fixture ruleset exercise
    the real machinery rather than a construction path production never uses.
    """
    admitted: dict[str, Rule] = {}
    for rule in rules:
        if rule.id in admitted:
            raise RuleLoadError(f"{rule.id!r} appears twice; a ruleset has one rule per id")
        gate(rule)
        admitted[rule.id] = rule
    return admitted
