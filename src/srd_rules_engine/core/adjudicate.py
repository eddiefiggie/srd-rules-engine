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
from typing import Final, Protocol

from srd_rules_engine.core.canonical import MAX_SAFE_INTEGER
from srd_rules_engine.core.d20 import (
    DAMAGE_OFFSET,
    DIE_SIDES,
    Critical,
    D20Result,
    D20Test,
)
from srd_rules_engine.core.d20 import resolve as roll_d20
from srd_rules_engine.core.d20 import roll as dice
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
#: 2 records the advantage the test was declared under. A v1 roll cannot be reconstructed
#: — a reader would build a test with neither flag set, roll one die where two were rolled,
#: and report a mismatch that looks like drift. Replay refuses those rather than guessing.
RULING_VERSION = 2
NARRATION_VERSION = 1
TERMINATION_VERSION = 1


class Status(StrEnum):
    """What an adjudication produced. Only `RULED` and `NO_TEST` are outcomes."""

    RULED = "ruled"
    NO_TEST = "no-test-accepted"
    CHALLENGED = "challenged"
    REJECTED = "rejected"
    BLOCKED = "blocked"


class RejectionCode(StrEnum):
    """Why a declaration was refused, as a code rather than a sentence.

    The retry bound compares refusals structurally — never by message text, which is
    templated on situational values and would make two identical refusals look different.
    """

    UNKNOWN_ACTOR = "unknown-actor"
    ACTION_NOT_LEGAL = "action-not-legal"
    UNKNOWN_RULE = "unknown-rule"
    UNDECLARED_FACT = "undeclared-fact"


class EffectKind(StrEnum):
    DAMAGE = "damage"
    HEALING = "healing"
    #: Death saves (p. 17-18). Marks rather than hit points: a success or failure "has no
    #: effect by itself", so they are their own effect rather than a healing of zero.
    DEATH_SAVE_SUCCESS = "death-save-success"
    DEATH_SAVE_FAILURE = "death-save-failure"
    STABILISED = "stabilised"
    DEATH = "death"


@dataclass(frozen=True)
class Effect:
    """A mechanical change a ruling applies. The engine applies it; the narrator reports it."""

    kind: EffectKind
    target_id: str
    amount: int
    description: str
    #: Damage only. p. 18 makes a Critical Hit cost two death save failures rather than
    #: one, so the state transition has to know where the damage came from.
    critical: bool = False


@dataclass(frozen=True)
class DamageDice:
    """Damage a resolver **declares** and the engine rolls. Never a total.

    A resolver returning `Effect(amount=7)` for a longsword would be a caller supplying a
    roll, which R4 exists to make impossible. So a proposal states the dice and the engine
    rolls them — from the same seed as the attack, at `DAMAGE_OFFSET`, which is what makes
    a replay reproduce the damage as well as the hit.

    A fixed `Effect` is still legitimate in a branch: some rules deal a stated amount. The
    distinction is whether the number came from dice, and dice belong to the engine.
    """

    target_id: str
    count: int
    sides: int
    modifier: int = 0
    source: str = "damage"

    def __post_init__(self) -> None:
        if self.count < 0 or self.sides < 1:
            raise ValueError(f"{self.count}d{self.sides} is not a damage expression")


#: What a proposal may put in a branch: a stated effect, or dice for the engine to roll.
Declared = Effect | DamageDice


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
    on_success: tuple[Declared, ...] = ()
    #: Branches selected by the **natural die** rather than by success or failure. The
    #: death save needs them and nothing else does yet: p. 18 makes a natural 1 cost two
    #: failures and a natural 20 restore a hit point, neither of which is "the save
    #: succeeded" or "the save failed". Left `None`, the ordinary branch runs.
    on_natural_20: tuple[Declared, ...] | None = None
    on_natural_1: tuple[Declared, ...] | None = None
    on_failure: tuple[Declared, ...] = ()
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


#: How much entropy a seed carries. **Not 64.** A seed is recorded in the ledger, and the
#: canonical form admits only integers an ECMAScript number represents exactly — so a
#: 64-bit seed has no canonical form and the adjudication that drew it cannot be written
#: down. The failure is total (the Ruling never escapes) but it looked like a ledger
#: problem, and every test until the vertical slice used seeds small enough to miss it.
SEED_BITS: Final = 52


def _system_seed() -> int:
    """Unpredictable, and inside the range the record can hold. R5 needs both."""
    return secrets.randbits(SEED_BITS)


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
    reason_code: RejectionCode | None = None
    reason_subject: str | None = None
    unresolved: tuple[str, ...] = ()
    fired: tuple[Trigger, ...] = ()

    @property
    def signature(self) -> tuple[str, ...]:
        """Structural identity, for telling one refusal from a repeat of the same one."""
        if self.status is Status.CHALLENGED:
            return tuple(trigger.id for trigger in self.fired)
        if self.status is Status.REJECTED:
            return (str(self.reason_code), self.reason_subject or "")
        return ()

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

    @property
    def port(self) -> MemoryPort:
        """The memory port, so a driver's supplied facts reach the same store."""
        return self._port

    def record_narration(self, ruling: Ruling, text: str) -> None:
        """R29. The narration is appended against the Ruling and the bounds it was issued under.

        Its own escape boundary: a narration is not an outcome, so it is not covered by the
        adjudication's sync, and R29 already provides for one that never arrives.
        """
        with self._ledger.escape_boundary():
            self._ledger.append(
                "narration",
                v=NARRATION_VERSION,
                payload={
                    COMPAT: NARRATION_VERSION,
                    "actor": ruling.declaration.actor_id,
                    "rule_id": ruling.rule_id,
                    "text": text,
                    "bounds": {
                        "may": list(ruling.bounds.may),
                        "may_not": list(ruling.bounds.may_not),
                    },
                },
            )

    def record_termination(self, actor_id: str, reason: str, refusals: Sequence[Ruling]) -> None:
        """A declaration slot that ended without a Ruling, recorded as the event it is.

        R30's report is generated from the ledger, so a turn that terminated leaves no
        trace unless something writes one — and a run of refusals followed by silence is
        indistinguishable from a session that simply stopped. Naming the reason is what
        lets triage tell an over-broad catalogue row from a confused agent.

        Its own escape boundary, for the same reason a narration has one: exhaustion is
        not an outcome, so it is not covered by an adjudication's sync.
        """
        with self._ledger.escape_boundary():
            self._ledger.append(
                "exhaustion",
                v=TERMINATION_VERSION,
                payload={
                    COMPAT: TERMINATION_VERSION,
                    "actor": actor_id,
                    "reason": reason,
                    "refusals": [
                        {
                            "status": str(r.status),
                            "reason_code": str(r.reason_code) if r.reason_code else None,
                            "reason_subject": r.reason_subject,
                            "fired": [t.id for t in r.fired],
                        }
                        for r in refusals
                    ],
                },
            )

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
            return _refused(declaration, verdict, *refusal), state

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
        seed = _checked_seed(self._seed_source())
        result = roll_d20(proposal.test, seed=seed)
        branch = _branch(proposal, result)
        effects = _roll_declared(branch, seed=seed, critical=result.critical)
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

    def _validate(
        self, state: EncounterState, declaration: Declaration
    ) -> tuple[str, RejectionCode, str] | None:
        """R3, against the same derivation the read surface enumerates with.

        Returns the sentence, the code, and the specific subject — the last two are what
        the retry bound compares, because message text is templated and would make two
        identical refusals look different.
        """
        if not state.has(declaration.actor_id):
            return (
                f"no combatant {declaration.actor_id!r} in this encounter",
                RejectionCode.UNKNOWN_ACTOR,
                declaration.actor_id,
            )

        offered = legal_actions(state, declaration.actor_id)
        key = declaration.intent.action_key
        if key is not None and key not in {action.key for action in offered}:
            return (
                f"{key!r} is not legal for {declaration.actor_id!r} right now; "
                f"the read surface offers {', '.join(a.key for a in offered) or 'nothing'}",
                RejectionCode.ACTION_NOT_LEGAL,
                key,
            )

        if declaration.rule_id is not None:
            if declaration.rule_id not in self._ruleset:
                return (
                    f"no rule {declaration.rule_id!r} in this ruleset",
                    RejectionCode.UNKNOWN_RULE,
                    declaration.rule_id,
                )
            for fact_type in self._ruleset.rule(declaration.rule_id).consumes:
                if fact_type not in self._fact_types:
                    return (
                        f"rule {declaration.rule_id!r} consumes undeclared fact {fact_type!r}",
                        RejectionCode.UNDECLARED_FACT,
                        fact_type,
                    )
        return None


# --- Ruling constructors ------------------------------------------------------------


def _refused(
    declaration: Declaration,
    verdict: Verdict,
    reason: str,
    code: RejectionCode,
    subject: str,
) -> Ruling:
    return Ruling(
        status=Status.REJECTED,
        declaration=declaration,
        alternatives_verdict=verdict,
        reason=reason,
        reason_code=code,
        reason_subject=subject,
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


def _checked_seed(seed: int) -> int:
    """Refuse a seed the record cannot hold, and name the seed source rather than the ledger.

    Without this the failure surfaces at the ledger write, as `LedgerUnavailable` — which
    points at the ledger for a defect in whatever supplied the seed. The seed is never
    clamped: a quietly altered seed reproduces a different roll on replay, so the only
    honest options are the seed as given or a refusal.
    """
    if not 0 <= seed <= MAX_SAFE_INTEGER:
        raise ValueError(
            f"the seed source returned {seed}, which is outside the range a ledger entry "
            f"can record exactly (0..{MAX_SAFE_INTEGER}). R5 requires the seed to be part "
            "of the record, so a seed that cannot be written cannot be rolled with"
        )
    return seed


def _branch(proposal: Proposal, result: D20Result) -> Sequence[Declared]:
    """Which branch the roll selected.

    The natural-die branches win where a resolver supplied one, because the rules that
    need them say so in terms: a natural 1 on a death save costs two failures *instead of*
    the one an ordinary failure costs, not as well as.
    """
    if result.used == DIE_SIDES and proposal.on_natural_20 is not None:
        return proposal.on_natural_20
    if result.used == 1 and proposal.on_natural_1 is not None:
        return proposal.on_natural_1
    return proposal.on_success if result.succeeded else proposal.on_failure


def _roll_declared(
    branch: Sequence[Declared], *, seed: int, critical: Critical = Critical.NONE
) -> tuple[Effect, ...]:
    """Turn a branch into settled effects, rolling any dice the resolver declared.

    Each expression consumes its own stretch of the seed's index space, so two damage
    dice in one branch cannot silently share a die and report the same number twice.

    On a Critical Hit the Rules Glossary (p. 179) says to "roll all of the attack's damage
    dice twice and add them together. Then add any relevant modifiers." Two things follow,
    and both are easy to get wrong: **every** damage expression in the branch doubles, not
    just the weapon's, and the **modifier does not** — it is added once, after.

    Doubling the count rather than rolling the same dice twice is deliberate: it consumes
    twice the index space, so the two halves of a critical cannot land on the same die.
    """
    settled: list[Effect] = []
    offset = DAMAGE_OFFSET
    for declared in branch:
        if isinstance(declared, Effect):
            settled.append(declared)
            continue
        count = declared.count * 2 if critical is Critical.HIT else declared.count
        faces = dice(seed, count=count, sides=declared.sides, offset=offset)
        offset += count
        total = max(0, sum(faces) + declared.modifier)
        crit = " (Critical Hit: damage dice doubled)" if critical is Critical.HIT else ""
        settled.append(
            Effect(
                kind=EffectKind.DAMAGE,
                target_id=declared.target_id,
                amount=total,
                critical=critical is Critical.HIT,
                description=(
                    f"{declared.source}: {count}d{declared.sides}"
                    f"{_signed(declared.modifier)}{crit} -> "
                    f"{' + '.join(str(f) for f in faces) or '0'}"
                    f"{_signed(declared.modifier)} = {total}"
                ),
            )
        )
    return tuple(settled)


def _signed(modifier: int) -> str:
    return "" if modifier == 0 else f" {'+' if modifier > 0 else '-'} {abs(modifier)}"


def _apply(state: EncounterState, effects: Sequence[Effect]) -> EncounterState:
    for effect in effects:
        if effect.kind is EffectKind.DAMAGE:
            state = state.with_damage(effect.target_id, effect.amount, critical=effect.critical)
        elif effect.kind is EffectKind.HEALING:
            state = state.with_healing(effect.target_id, effect.amount)
        elif effect.kind is EffectKind.DEATH_SAVE_SUCCESS:
            state = state.with_death_save(effect.target_id, successes=effect.amount)
        elif effect.kind is EffectKind.DEATH_SAVE_FAILURE:
            state = state.with_death_save(effect.target_id, failures=effect.amount)
        elif effect.kind is EffectKind.STABILISED:
            state = state.with_stabilised(effect.target_id)
        else:
            state = state.with_death(effect.target_id)
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
        "reason_code": str(ruling.reason_code) if ruling.reason_code else None,
        "reason_subject": ruling.reason_subject,
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
            # Without these the recorded dice cannot be re-derived: the count, and which
            # of them was used, both depend on the advantage the test was declared under.
            "declared_advantage": result.declared_advantage,
            "declared_disadvantage": result.declared_disadvantage,
            "effective_advantage": str(result.effective),
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
