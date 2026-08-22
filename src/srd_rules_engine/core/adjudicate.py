"""The single path by which an outcome comes into existence.

R1 says no other API produces, modifies, or implies a result. Everything the engine can
say about what happened comes back from `adjudicate`, in a `Ruling` that carries enough
to explain it and enough to replay it.

The shape follows from three requirements that pull in the same direction:

- **R4 — the engine rolls.** A caller supplies neither a roll nor a *seed*. A seed is not
  a roll, but a caller who chooses it chooses the outcome by searching for a favourable
  one, so the engine draws its own from a source that is unpredictable by default. Tests
  substitute the source; nothing substitutes the value.
- **R5 — the Ruling shows its working.** Status, the test performed, the raw dice and the
  seed, the target number *and its derivation*, applied effects, every resolved fact with
  its provenance, the alternatives the declaration recorded with their verdict, citations,
  and narration bounds. A reader must be able to ask why a result came out this way from
  the record alone.
- **R26 — nothing escapes before its record is durable.** The whole adjudication runs
  inside one escape boundary: the declaration and the ruling reach storage in a single
  synchronising write, and a failure raises rather than returning a rules status.

**Validation uses the same legality derivation the read surface does** (R3, R18), so what
was offered and what is accepted cannot drift.

A rule is a *declaration* — verifiable, provenance-tracked, loaded through U7's gates — and
a **resolver** is the code that turns it into a target number and effects. Keeping them
apart is what the seed decision found the hard way: no dataset supplies effect shapes, so
the data is the numbers and the code is the meaning.
"""

from __future__ import annotations

import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Protocol

from srd_rules_engine.core.d20 import D20Result, D20Test
from srd_rules_engine.core.d20 import resolve as roll_d20
from srd_rules_engine.core.ledger import COMPAT, Ledger
from srd_rules_engine.core.memory_port import (
    DefaultKind,
    FactType,
    MemoryPort,
    Resolution,
)
from srd_rules_engine.core.memory_port import (
    resolve as resolve_fact,
)
from srd_rules_engine.core.read_surface import LegalAction, Verdict, legal_actions, verify
from srd_rules_engine.core.rules import Ruleset
from srd_rules_engine.core.state import EncounterState
from srd_rules_engine.core.triggers import Catalogue, MatchContext, Trigger, challenge_text

DECLARATION_VERSION = 1
RULING_VERSION = 1


class Status(StrEnum):
    """What an adjudication produced. Only `RULED` and `NO_TEST` are outcomes."""

    RULED = "ruled"
    NO_TEST = "no-test-accepted"
    CHALLENGED = "challenged"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class EffectKind(StrEnum):
    DAMAGE = "damage"
    HEALING = "healing"


@dataclass(frozen=True)
class Effect:
    """A mechanical change a ruling applies. The engine applies it; the narrator reports it."""

    kind: EffectKind
    target_id: str
    amount: int
    description: str


@dataclass(frozen=True)
class Intent:
    """R2. Structured, or explicitly improvised — the label is carried and never matched on."""

    action_key: str | None = None
    improvised: bool = False
    label: str | None = None

    def __post_init__(self) -> None:
        if self.improvised and self.action_key is not None:
            raise ValueError("an improvised intent has no enumerated action key")
        if not self.improvised and not self.action_key:
            raise ValueError("an intent is either enumerated or marked improvised")


@dataclass(frozen=True)
class Declaration:
    """R2. What the agent believes applies, or an explicit claim that nothing does."""

    actor_id: str
    intent: Intent
    rule_id: str | None = None
    no_test_reason: str | None = None
    alternatives: tuple[LegalAction, ...] = ()
    read_token: str | None = None

    def __post_init__(self) -> None:
        if bool(self.rule_id) == bool(self.no_test_reason):
            raise ValueError(
                "a declaration names the test it believes applies, or claims no test is "
                "needed and states why. Exactly one, because a skip with no reason is the "
                "defect this engine exists to make impossible"
            )

    @property
    def claims_no_test(self) -> bool:
        return self.no_test_reason is not None


@dataclass(frozen=True)
class NarrationBounds:
    """R7. Advisory to the caller — the engine states them and does not enforce them."""

    may: tuple[str, ...] = ()
    may_not: tuple[str, ...] = ()


@dataclass(frozen=True)
class Proposal:
    """What a resolver returns: the test to roll, and what follows from either outcome."""

    test: D20Test
    citations: tuple[str, ...] = ()
    on_success: tuple[Effect, ...] = ()
    on_failure: tuple[Effect, ...] = ()
    may_claim: tuple[str, ...] = ()
    may_not_claim: tuple[str, ...] = ()


class Resolver(Protocol):
    """Turns a rule plus resolved facts into a proposal. This is code, not data."""

    def __call__(
        self,
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal: ...


class SeedSource(Protocol):
    """Where a seed comes from. Unpredictable in production; substituted in tests."""

    def __call__(self) -> int: ...


def _system_seed() -> int:
    return secrets.randbits(64)


@dataclass(frozen=True)
class Ruling:
    """R5. The only object that constitutes an outcome, and it shows its working."""

    status: Status
    declaration: Declaration
    alternatives_verdict: Verdict
    rule_id: str | None = None
    result: D20Result | None = None
    effects: tuple[Effect, ...] = ()
    facts: tuple[Resolution, ...] = ()
    citations: tuple[str, ...] = ()
    bounds: NarrationBounds = field(default_factory=NarrationBounds)
    reason: str | None = None
    unresolved: tuple[str, ...] = ()
    fired: tuple[Trigger, ...] = ()

    @property
    def is_outcome(self) -> bool:
        return self.status in {Status.RULED, Status.NO_TEST}

    def why(self) -> str:
        """The one-line account a reader can check without reconstructing the session."""
        if self.status is Status.REJECTED:
            return f"rejected: {self.reason}"
        if self.status is Status.CHALLENGED:
            return f"challenged: {challenge_text(self.fired)}"
        if self.status is Status.BLOCKED:
            return f"blocked on {', '.join(self.unresolved)}"
        if self.result is None:
            return f"no test needed: {self.declaration.no_test_reason}"
        return self.result.derivation()


class Adjudicator:
    """Holds the ruleset, its resolvers, the port, and the ledger. Rules through one door."""

    def __init__(
        self,
        *,
        ruleset: Ruleset,
        resolvers: Mapping[str, Resolver],
        fact_types: Mapping[str, FactType],
        port: MemoryPort,
        ledger: Ledger,
        catalogue: Catalogue | None = None,
        seed_source: SeedSource = _system_seed,
    ) -> None:
        missing = [rule.id for rule in ruleset if rule.id not in resolvers]
        if missing:
            raise ValueError(
                f"no resolver for {', '.join(sorted(missing))}. A rule that cannot be "
                "resolved would be admitted by the loader and then fail at the table"
            )
        self._ruleset = ruleset
        self._resolvers = dict(resolvers)
        self._fact_types = dict(fact_types)
        self._port = port
        self._ledger = ledger
        self._catalogue = catalogue or Catalogue(version=1)
        self._seed_source = seed_source

    def adjudicate(
        self,
        state: EncounterState,
        declaration: Declaration,
        *,
        situation: Mapping[str, object] | None = None,
    ) -> tuple[Ruling, EncounterState]:
        """The single entry point. Returns the Ruling and the state it left behind."""
        with self._ledger.escape_boundary():
            self._ledger.append(
                "declaration",
                v=DECLARATION_VERSION,
                payload=_declaration_payload(declaration, self._catalogue.version),
            )
            ruling, next_state = self._decide(state, declaration, situation or {})
            self._ledger.append(
                _entry_type(ruling.status), v=RULING_VERSION, payload=_ruling_payload(ruling)
            )
        return ruling, next_state

    # --- The decision, in the order R5 requires it to be reconstructable ------------

    def _decide(
        self,
        state: EncounterState,
        declaration: Declaration,
        situation: Mapping[str, object],
    ) -> tuple[Ruling, EncounterState]:
        verdict = self._verdict(state, declaration)

        refusal = self._validate(state, declaration)
        if refusal is not None:
            return _refused(declaration, verdict, refusal), state

        if declaration.claims_no_test:
            # R6. The matcher sees a projection with no field for the free-text label,
            # so a skip cannot be waved through by how it was worded.
            fired = self._catalogue.matching(project(declaration, state, situation))
            if fired:
                return _challenged(declaration, verdict, fired), state
            return _no_test(declaration, verdict), state

        assert declaration.rule_id is not None  # guaranteed by Declaration.__post_init__
        rule = self._ruleset.rule(declaration.rule_id)

        resolutions = [
            resolve_fact(self._port, self._fact_types[name], declaration.actor_id)
            for name in rule.consumes
        ]
        blocked = tuple(r.type_name for r in resolutions if r.blocked)
        if blocked:
            # R22: name *every* unresolved fact, not the first. The set can only shrink,
            # so a driver that supplies them all at once resolves in one round.
            return _blocked(declaration, verdict, blocked, tuple(resolutions)), state

        proposal = self._resolvers[rule.id](
            state=state, declaration=declaration, facts={r.type_name: r for r in resolutions}
        )
        result = roll_d20(proposal.test, seed=self._seed_source())
        effects = proposal.on_success if result.succeeded else proposal.on_failure
        next_state = _apply(state, effects)

        return (
            Ruling(
                status=Status.RULED,
                declaration=declaration,
                alternatives_verdict=verdict,
                rule_id=rule.id,
                result=result,
                effects=effects,
                facts=tuple(resolutions),
                citations=proposal.citations,
                bounds=_bounds(proposal, result),
            ),
            next_state,
        )

    def _verdict(self, state: EncounterState, declaration: Declaration) -> Verdict:
        return verify(declaration.read_token, declaration.alternatives, state.generation)

    def _validate(self, state: EncounterState, declaration: Declaration) -> str | None:
        """R3, against the same derivation the read surface enumerates with."""
        if not state.has(declaration.actor_id):
            return f"no combatant {declaration.actor_id!r} in this encounter"

        offered = legal_actions(state, declaration.actor_id)
        key = declaration.intent.action_key
        if key is not None and key not in {action.key for action in offered}:
            return (
                f"{key!r} is not legal for {declaration.actor_id!r} right now; "
                f"the read surface offers {', '.join(a.key for a in offered) or 'nothing'}"
            )

        if declaration.rule_id is not None:
            if declaration.rule_id not in self._ruleset:
                return f"no rule {declaration.rule_id!r} in this ruleset"
            for fact_type in self._ruleset.rule(declaration.rule_id).consumes:
                if fact_type not in self._fact_types:
                    return f"rule {declaration.rule_id!r} consumes undeclared fact {fact_type!r}"
        return None


# --- Ruling constructors ------------------------------------------------------------


def _refused(declaration: Declaration, verdict: Verdict, reason: str) -> Ruling:
    return Ruling(
        status=Status.REJECTED,
        declaration=declaration,
        alternatives_verdict=verdict,
        reason=reason,
        bounds=NarrationBounds(may_not=("that anything happened — no outcome was produced",)),
    )


def _challenged(declaration: Declaration, verdict: Verdict, fired: tuple[Trigger, ...]) -> Ruling:
    """R6. Names every row that fired, in identifier order, and produces no outcome."""
    return Ruling(
        status=Status.CHALLENGED,
        declaration=declaration,
        alternatives_verdict=verdict,
        fired=fired,
        bounds=NarrationBounds(
            may_not=("that anything happened — the skip must be re-declared as a test",)
        ),
    )


def project(
    declaration: Declaration, state: EncounterState, situation: Mapping[str, object]
) -> MatchContext:
    """Build what the matcher sees. The free-text label has nowhere to go."""
    derived: dict[str, object] = {
        "in_combat": state.in_combat,
        "round": state.round_number,
        "actor_is_active": state.is_active(declaration.actor_id),
    }
    if state.has(declaration.actor_id):
        actor = state.combatant(declaration.actor_id)
        derived["actor_hit_points"] = actor.hit_points
        derived["actor_is_down"] = actor.is_down
    return MatchContext(
        actor_id=declaration.actor_id,
        action_key=declaration.intent.action_key,
        improvised=declaration.intent.improvised,
        situation={**derived, **situation},
    )


def _no_test(declaration: Declaration, verdict: Verdict) -> Ruling:
    return Ruling(
        status=Status.NO_TEST,
        declaration=declaration,
        alternatives_verdict=verdict,
        bounds=NarrationBounds(
            may=("that the action happened as described, with no mechanical outcome",),
            may_not=("any consequence a rule would have had to resolve",),
        ),
    )


def _blocked(
    declaration: Declaration,
    verdict: Verdict,
    unresolved: tuple[str, ...],
    facts: tuple[Resolution, ...],
) -> Ruling:
    return Ruling(
        status=Status.BLOCKED,
        declaration=declaration,
        alternatives_verdict=verdict,
        rule_id=declaration.rule_id,
        facts=facts,
        unresolved=unresolved,
        bounds=NarrationBounds(may_not=("that anything happened — no outcome was produced",)),
    )


def _bounds(proposal: Proposal, result: D20Result) -> NarrationBounds:
    """R7. What may be claimed, and the standing limit on everything else."""
    outcome = "succeeded" if result.succeeded else "failed"
    return NarrationBounds(
        may=(f"that the {result.kind} {outcome}", *proposal.may_claim),
        may_not=(
            "any consequence this ruling did not resolve; it needs its own declaration",
            *proposal.may_not_claim,
        ),
    )


def _apply(state: EncounterState, effects: Sequence[Effect]) -> EncounterState:
    for effect in effects:
        if effect.kind is EffectKind.DAMAGE:
            state = state.with_damage(effect.target_id, effect.amount)
        else:
            state = state.with_healing(effect.target_id, effect.amount)
    return state


# --- Ledger payloads ----------------------------------------------------------------


def _entry_type(status: Status) -> str:
    if status is Status.REJECTED:
        return "rejection"
    if status is Status.CHALLENGED:
        return "challenge"
    return "ruling"


def _declaration_payload(declaration: Declaration, catalogue_version: int) -> Mapping[str, object]:
    return {
        COMPAT: DECLARATION_VERSION,
        # R6: replay uses the catalogue version in force, not the current one, so a
        # grown catalogue never reports a sound ledger as inconsistent.
        "catalogue_version": catalogue_version,
        "actor": declaration.actor_id,
        "intent": {
            "action_key": declaration.intent.action_key,
            "improvised": declaration.intent.improvised,
            "label": declaration.intent.label,
        },
        "rule_id": declaration.rule_id,
        "no_test_reason": declaration.no_test_reason,
        "alternatives": [dict(a.identity()) for a in declaration.alternatives],
        "read_token": declaration.read_token,
    }


def _ruling_payload(ruling: Ruling) -> Mapping[str, object]:
    result = ruling.result
    return {
        COMPAT: RULING_VERSION,
        "status": str(ruling.status),
        "actor": ruling.declaration.actor_id,
        "rule_id": ruling.rule_id,
        "alternatives_verdict": str(ruling.alternatives_verdict),
        "reason": ruling.reason,
        "unresolved": list(ruling.unresolved),
        "fired": [
            {"id": t.id, "grounding": str(t.grounding), "basis": t.reference or t.rationale}
            for t in ruling.fired
        ],
        "citations": list(ruling.citations),
        "facts": [
            {
                "type": r.type_name,
                "subject": r.subject,
                "value": r.value,
                "defaulted": str(r.defaulted) if r.defaulted else None,
                "provenance": dict(r.provenance.as_payload()) if r.provenance else None,
            }
            for r in ruling.facts
        ],
        "effects": [
            {
                "kind": str(e.kind),
                "target": e.target_id,
                "amount": e.amount,
                "description": e.description,
            }
            for e in ruling.effects
        ],
        "bounds": {"may": list(ruling.bounds.may), "may_not": list(ruling.bounds.may_not)},
        "roll": None
        if result is None
        else {
            "kind": str(result.kind),
            "seed": result.seed,
            "dice": list(result.dice),
            "used": result.used,
            "target": result.target,
            "target_basis": result.target_basis,
            "modifiers": [{"source": m.source, "value": m.value} for m in result.modifiers],
            "total": result.total,
            "succeeded": result.succeeded,
            "derivation": result.derivation(),
        },
    }


def defaulted_kinds(ruling: Ruling) -> Mapping[str, DefaultKind]:
    """Which facts defaulted, and which kind of default applied (R22, AE3)."""
    return {r.type_name: r.defaulted for r in ruling.facts if r.defaulted is not None}
