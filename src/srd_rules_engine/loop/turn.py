"""The turn loop: it owns the turn, and the agent is invoked only at defined points.

R8 puts this outside the LLM-free core, and expresses the invocation as a **generator
yielding typed requests** rather than a callback. Control inversion means one rules
implementation serves synchronous, asynchronous, scripted, and human drivers — a callback
shape would need a second async loop whose rules logic measured identical after stripping
`await`, and a divergence between the two would be a rules bug visible only to async
consumers.

The seam is also the session transcript, so replay and the session-review report derive
from it without the agent's cooperation.

## Three loops, and only one of them is the agent's fault

- **Refusals** — a challenge or a rejection. The agent named the wrong thing, or claimed a
  skip that collided. One budget per declaration slot covers both, because they interleave:
  a challenge answered with an illegal test produces a rejection.
- **A block** — a declared fact the port cannot supply. This is a **suspension, not a
  refusal**: the declaration was accepted and stalled only at fact resolution, so it
  resumes rather than being re-made and the budget is not charged. Charging it would spend
  an agent's retries on a driver's omission.
- **Narration** — R29 refuses the next declaration for an actor until the previous Ruling's
  narration is submitted, and a turn that advances without one carries an explicit marker.

**Two structurally identical refusals terminate at once**, ahead of the budget. Identity is
the trigger identifier set, or the rejection code and its subject — **never message text**,
which is templated on situational values and would make two identical refusals look
different. A repeat proves the feedback is not being used, and under the trigger catalogue
that usually means an over-broad row rather than a confused agent.

**The blocked loop needs no count bound.** A rule's fact dependencies are static, so the
unresolved set can only shrink and the loop terminates in at most as many rounds as the
rule declares facts. A count bound could only cut off a sequence that was progressing —
which in a human-driven session is a person supplying facts one at a time.

**Exhaustion is a terminal turn outcome, not a rules status.** No rule says a badly-declared
action has a result. The engine never breaks a loop by choosing a test: that would let an
agent reach an adjudicated outcome *by failing*, putting a second path beside the
declaration it is accountable for.

See `docs/decisions/0001-agent-seam.md`, `0005-retry-bounds.md`, and `0010-blocked-loop.md`.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Final, TypeVar

from srd_rules_engine.core import (
    BURNING_RULE_ID,
    CONCENTRATION_RULE_ID,
    DEATH_SAVE_RULE_ID,
    SUFFOCATION_RULE_ID,
    Adjudicator,
    Declaration,
    EncounterState,
    Fact,
    Intent,
    LegalAction,
    ReadResult,
    Ruling,
    Status,
    read,
    save_ends_rule_id,
)

#: 0005's default. Room for the realistic recovery — challenged, then a wrong test
#: rejected, then correct — while keeping a confused agent to a few model calls.
DEFAULT_BUDGET: Final = 3


class TerminalReason(StrEnum):
    """Why a slot ended without a Ruling. Named so triage can tell them apart."""

    NO_PROGRESS = "no-progress"
    CHALLENGE_CHURN = "challenge-churn"
    REJECTION_CHURN = "rejection-churn"
    MIXED_CHURN = "mixed-churn"
    FACT_UNAVAILABLE = "fact-unavailable"


# --- The seam: typed requests out, typed responses in -------------------------------


@dataclass(frozen=True)
class DeclarationRequest:
    """What the driver needs to declare: the state, what is legal, and what was refused."""

    state: EncounterState
    actor_id: str
    offered: ReadResult
    refusals: tuple[Ruling, ...] = ()


@dataclass(frozen=True)
class NarrationRequest:
    """R29. The Ruling and the bounds it was issued under."""

    ruling: Ruling


@dataclass(frozen=True)
class BlockedFactRequest:
    """0010. Every unresolved fact at once, so one round can supply them all."""

    declaration: Declaration
    unresolved: tuple[str, ...]


Request = DeclarationRequest | NarrationRequest | BlockedFactRequest


@dataclass(frozen=True)
class Declared:
    declaration: Declaration


@dataclass(frozen=True)
class Narrated:
    """`text=None` is an explicit refusal to narrate, which R29 marks rather than hides."""

    text: str | None


@dataclass(frozen=True)
class FactsSupplied:
    facts: tuple[Fact, ...] = ()


Response = Declared | Narrated | FactsSupplied


# --- What a turn produced -----------------------------------------------------------


@dataclass(frozen=True)
class TurnOutcome:
    """The turn's result. A terminal reason means no Ruling was produced at all."""

    state: EncounterState
    ruling: Ruling | None = None
    terminal: TerminalReason | None = None
    refusals: tuple[Ruling, ...] = ()
    offered: tuple[LegalAction, ...] = ()
    narration: str | None = None
    missing_narration: bool = False
    unresolved: tuple[str, ...] = ()
    #: Rulings this turn *incurred* rather than declared: every forced save the queue owed
    #: (0036 clause 7, 0048). Two rules produce them today — p. 179's Concentration save and
    #: p. 90's Topple — and this field needed no change for the second, because it is named
    #: for what a ruling **is** rather than for the rule that caused it. Additive and
    #: defaulted, because `TurnOutcome` is COMMITTED — nothing is removed or renamed and
    #: `API_VERSION` does not move.
    #:
    #: Its own field rather than a second value in `ruling`, because they are answers to
    #: different questions: `ruling` is what the agent's declaration came to, and this is
    #: what followed from it whether anyone declared anything or not. A driver reporting
    #: the turn needs both, and a driver checking what the agent achieved needs only one.
    consequential: tuple[Ruling, ...] = ()
    #: One per entry in `consequential`, in the same order. `None` is R29's unfilled debt,
    #: named the way `TurnStart.narrations` names it rather than dropped.
    consequential_narrations: tuple[str | None, ...] = ()
    #: Consequential obligations no rule in the ruleset could resolve — the same field, the
    #: same meaning and the same type as on `TurnStart` and `TurnEnd`. A ruleset without the
    #: Concentration rule is a deployment fact, and a save that silently did not happen is
    #: the failure this engine exists to prevent.
    #:
    #: Not to be read as `unresolved` above, which is a different question with a different
    #: type: that one is the **fact types** a blocked declaration could not obtain.
    unresolvable: tuple[Obligation, ...] = ()

    @property
    def produced_outcome(self) -> bool:
        return self.ruling is not None and self.ruling.is_outcome


@dataclass(frozen=True)
class Obligation:
    """Something a turn requires of a creature, derived from state (0023 clause 2).

    Never declared. p. 63 gives the creature no choice about repeating a save, and p. 17
    gives it none about a death save, so offering either through a declaration slot would
    offer a decision the document does not give — and a slot in which declining is
    expressible is a slot in which the save can fail to happen.

    **Identified by its rule id, not by a condition** (0027 clause 2). It carried a
    `condition` until the turn's start acquired obligations of its own: a death save has no
    condition, and Burning is not one of the fifteen. The field generalised by being
    *removed* rather than widened into a union or joined by a `kind` — a kind in the data is
    a branch in every consumer, which is what 0019 refuses. What an obligation is, is
    already answered by which rule resolves it.
    """

    actor_id: str
    rule_id: str
    #: What the engine-authored declaration says this creature is doing. A field rather than
    #: a property derived from a condition, for the same reason the condition went.
    label: str


@dataclass(frozen=True)
class TurnStart:
    """What the start of the turn produced (0027 clause 1).

    Shaped like `TurnEnd` and deliberately not merged with it. They carry the same fields
    today, and a single type would say the two phases are interchangeable — which is the
    assumption that nearly put the death save at the turn's end.
    """

    state: EncounterState
    rulings: tuple[Ruling, ...] = ()
    narrations: tuple[str | None, ...] = ()
    #: Obligations no rule in the ruleset could resolve. A ruleset without the death-save
    #: rule is a deployment fact, and a turn that cannot begin is worse than one that begins
    #: with the gap recorded.
    unresolvable: tuple[Obligation, ...] = ()

    @property
    def missing_narration(self) -> bool:
        """R29. Any ruling here that was not narrated."""
        return any(text is None for text in self.narrations)


@dataclass(frozen=True)
class TurnEnd:
    """What the end of the turn produced. One entry per obligation, in the order run."""

    state: EncounterState
    rulings: tuple[Ruling, ...] = ()
    narrations: tuple[str | None, ...] = ()
    #: Obligations no rule in the ruleset could resolve. Named rather than raised: a
    #: ruleset that omits a save-ends rule is a deployment fact, and a turn that cannot
    #: end is worse than one that ends with the gap recorded. The ledger carries the
    #: rejection either way, because the declaration was still adjudicated.
    unresolvable: tuple[Obligation, ...] = ()

    @property
    def missing_narration(self) -> bool:
        """R29. Any ruling here that was not narrated."""
        return any(text is None for text in self.narrations)


class NarrationOwed(Exception):
    """R29. The previous Ruling for this actor has no narration yet."""


class ObligationOwed(Exception):
    """0027 clause 4. The turn's start has obligations this creature has not discharged.

    Raised by `run` rather than by `advanced_turn`, which is the asymmetry that matters: an
    end-of-turn obligation is *overdue* by the time the pointer moves, while a start-of-turn
    one is newly due — so the guard has to sit where the creature next tries to act.
    """


@dataclass
class TurnLoop:
    """Owns the turn. Invokes the driver only at the points R8 defines."""

    adjudicator: Adjudicator
    budget: int | None = DEFAULT_BUDGET
    _owed: dict[str, Ruling] = field(default_factory=dict)

    def owes_narration(self, actor_id: str) -> bool:
        return actor_id in self._owed

    def run(
        self,
        state: EncounterState,
        actor_id: str,
        *,
        situation: Mapping[str, object] | None = None,
    ) -> Generator[Request, Response, TurnOutcome]:
        """One declaration slot, end to end. Yields requests; returns what the turn produced."""
        if actor_id in self._owed:
            raise NarrationOwed(
                f"{actor_id!r} owes a narration for its previous Ruling. R29 refuses the next "
                "declaration until it is submitted, so a turn cannot quietly advance past one"
            )

        # 0027 clause 4. The symmetric guard to `advanced_turn` refusing while an
        # end-of-turn obligation is owed (0023 clause 6) — and it cannot live there, because
        # by the time the pointer has moved the incoming creature's start-of-turn
        # obligations are *newly* due rather than overdue. Refusing the declaration is what
        # makes the skip structurally impossible rather than merely serviced by well-behaved
        # callers: a creature that must roll a death save before acting cannot act first.
        outstanding = self.start_turn_obligations(state, actor_id)
        if outstanding:
            owed = ", ".join(o.label for o in outstanding)
            raise ObligationOwed(
                f"{actor_id!r} owes the start of its turn before it may act: {owed}. "
                "Run TurnLoop.start_turn first — the obligation is derived from state and "
                "is not the creature's to decline"
            )

        offered = read(state, actor_id)
        refusals: list[Ruling] = []
        situation = situation or {}

        while True:
            response = yield DeclarationRequest(
                state=state, actor_id=actor_id, offered=offered, refusals=tuple(refusals)
            )
            declaration = _expect(response, Declared).declaration

            ruling, state, unresolved = yield from self._resolve(state, declaration, situation)
            if unresolved is not None:
                return self._terminated(
                    actor_id,
                    TerminalReason.FACT_UNAVAILABLE,
                    state=state,
                    refusals=tuple(refusals),
                    offered=offered.actions,
                    unresolved=unresolved,
                )

            if ruling.status in {Status.CHALLENGED, Status.REJECTED}:
                terminal = self._terminal_for(refusals, ruling)
                refusals.append(ruling)
                if terminal is not None:
                    return self._terminated(
                        actor_id,
                        terminal,
                        state=state,
                        refusals=tuple(refusals),
                        offered=offered.actions,
                    )
                continue

            narration = yield from self._narrate(actor_id, ruling)

            # 0036 clause 6. The declared action is what dealt the damage, so its ruling
            # and its narration come first and the saves it compelled follow. Only on this
            # path: a refusal and a termination both produce no effects, so neither can
            # have put a debt on the queue.
            (
                state,
                consequential,
                consequential_narrations,
                unresolvable,
            ) = yield from self._concentration_saves(state)
            return TurnOutcome(
                state=state,
                ruling=ruling,
                refusals=tuple(refusals),
                offered=offered.actions,
                narration=narration,
                missing_narration=narration is None
                or any(text is None for text in consequential_narrations),
                consequential=consequential,
                consequential_narrations=consequential_narrations,
                unresolvable=unresolvable,
            )

    # --- The turn's end: a phase the loop owns (0023) ---------------------------------

    def start_turn_obligations(
        self, state: EncounterState, actor_id: str
    ) -> tuple[Obligation, ...]:
        """Every obligation the **start** of this creature's turn incurs (0027 clause 1).

        Two of them.

        **The death save** — p. 17: "Whenever you start your turn with 0 Hit Points, you
        must make a Death Saving Throw." That is the start of a turn, not its end, and 0023
        declined to place it from memory rather than assume it matched save-ends' timing.
        Had it assumed, the save would have been rolled at the wrong moment and looked
        correct doing it.

        **Burning** — p. 178: "A burning creature or object takes 1d4 Fire damage at the
        start of each of its turns." The same phase, which is not a coincidence worth
        smoothing over: #140 guessed the death save was one of three obligations on one
        seam, when in fact Burning shares the death save's occasion and Suffocation is on
        the other one.

        **Order is death save first, and it is not arbitrary.** A creature at 0 hit points
        that is also burning has both owed, and the save decides whether it is still alive
        to take the damage. Rolling the damage first would be resolving a fire against a
        creature whose death this turn had not been settled — and p. 17's third failure is a
        death, not a hit point total.

        Scoped to this occasion rather than taking one as an argument (0027 clause 3): a
        single enumerator returning obligations tagged with their occasion puts the occasion
        back in the data, which is the shape clause 2 refuses.
        """
        if not state.has(actor_id):
            return ()
        actor = state.combatant(actor_id)
        owed: list[Obligation] = []

        if actor.makes_death_saves and (actor_id, DEATH_SAVE_RULE_ID) not in state.discharged:
            owed.append(
                Obligation(
                    actor_id=actor_id,
                    rule_id=DEATH_SAVE_RULE_ID,
                    label=("makes a death saving throw, starting its turn at 0 hit points (p. 17)"),
                )
            )

        if actor.hazards.burning and (actor_id, BURNING_RULE_ID) not in state.discharged:
            owed.append(
                Obligation(
                    actor_id=actor_id,
                    rule_id=BURNING_RULE_ID,
                    label="takes the fire's damage, starting its turn burning (p. 178)",
                )
            )

        return tuple(owed)

    def end_turn_obligations(self, state: EncounterState, actor_id: str) -> tuple[Obligation, ...]:
        """Every obligation the **end** of this creature's turn incurs, read off state.

        Save-ends, and Suffocation. The death save is not here and never was: p. 17 puts it
        at the turn's start, which is `start_turn_obligations`.

        **Save-ends first.** A creature that is suffocating and holds a save-ends condition
        owes both, and the save may end a condition whose effects would otherwise still be
        described as holding when the Exhaustion lands. The reverse order decides nothing
        differently today — an Exhaustion level changes no save's DC — so this is a stable
        order rather than a rule, and it is stated because a reader would otherwise assume
        one exists.
        """
        if not state.has(actor_id):
            return ()
        owed = [
            Obligation(
                actor_id=actor_id,
                rule_id=save_ends_rule_id(condition),
                label=f"repeats the save that ends {condition.value} (p. 63)",
            )
            for condition in state.obligations_outstanding(actor_id)
        ]

        actor = state.combatant(actor_id)
        if actor.hazards.suffocating and (actor_id, SUFFOCATION_RULE_ID) not in state.discharged:
            owed.append(
                Obligation(
                    actor_id=actor_id,
                    rule_id=SUFFOCATION_RULE_ID,
                    label="gains an Exhaustion level, ending its turn without breath (p. 189)",
                )
            )

        return tuple(owed)

    def start_turn(
        self, state: EncounterState, actor_id: str
    ) -> Generator[Request, Response, TurnStart]:
        """Resolve every obligation the start of this creature's turn incurs (0027 clause 1).

        The caller runs this, then `run` — which refuses until it has, so the ordering is
        enforced rather than documented. That is 0023 clause 1's shape one phase earlier,
        and clauses 2 and 3 of that record hold unchanged: each obligation goes through the
        **one adjudication entry point**, the engine rolls it (R1, R4), and each ruling
        yields a `NarrationRequest` so R29's bounds reach the narrator exactly as they do
        for a declared action.

        Nothing here creates a second path to an outcome. It creates a third *occasion* on
        which the existing path is taken.

        **This is not the adapters' `begin_turn`**, which maps to `run` and opens a
        declaration slot. 0027 clause 1 names that collision because the two would read as
        the same thing.
        """
        rulings: list[Ruling] = []
        narrations: list[str | None] = []
        unresolvable: list[Obligation] = []

        # Re-read each time, as `end_turn` does: an obligation resolved may change what is
        # outstanding, and a list snapshotted up front would keep rolling for one that has
        # already gone.
        while True:
            # 0036 clause 6, and this is the phase that proves the clause: Burning deals
            # its damage here (p. 178), so a concentrating creature that starts its turn on
            # fire owes a save before the turn goes any further. At the top of each pass
            # rather than after the last obligation, so the final pass — the one that finds
            # nothing pending and breaks — still discharges what the previous one incurred.
            (
                state,
                compelled,
                compelled_narrations,
                compelled_unresolvable,
            ) = yield from self._concentration_saves(state)
            rulings.extend(compelled)
            narrations.extend(compelled_narrations)
            unresolvable.extend(compelled_unresolvable)

            pending = self.start_turn_obligations(state, actor_id)
            if not pending:
                break
            obligation = pending[0]

            ruling, state = self.adjudicator.adjudicate(state, _obligation_declaration(obligation))
            # Discharged whether it succeeded, failed, or was refused. p. 17 gives one death
            # save per turn either way, and an obligation that stayed outstanding after a
            # rejection would spin this loop forever.
            state = state.with_obligation_discharged(actor_id, obligation.rule_id)

            if ruling.status is Status.REJECTED:
                unresolvable.append(obligation)
                continue

            rulings.append(ruling)
            narrations.append((yield from self._narrate(actor_id, ruling)))

        return TurnStart(
            state=state,
            rulings=tuple(rulings),
            narrations=tuple(narrations),
            unresolvable=tuple(unresolvable),
        )

    def end_turn(
        self, state: EncounterState, actor_id: str
    ) -> Generator[Request, Response, TurnEnd]:
        """Resolve every obligation the end of this creature's turn incurs (0023 clause 1).

        The caller runs this, then `advanced_turn` — which refuses until it has, so the
        ordering is enforced rather than documented.

        Each obligation goes through the **one adjudication entry point**, the engine rolls
        it (R1, R4), and each ruling yields a `NarrationRequest` so R29's bounds reach the
        narrator exactly as they do for a declared action. Nothing here creates a second
        path to an outcome; it creates a second *occasion* on which the existing path is
        taken.
        """
        if actor_id in self._owed:
            raise NarrationOwed(
                f"{actor_id!r} owes a narration for its previous Ruling. The turn cannot "
                "end while R29's debt for the declared action is outstanding"
            )

        rulings: list[Ruling] = []
        narrations: list[str | None] = []
        unresolvable: list[Obligation] = []

        # Re-read each time: a save that ends a condition changes what is outstanding, and
        # an obligation list snapshotted up front would keep rolling for a condition that
        # has already gone.
        while True:
            # 0036 clause 6. Nothing at the turn's end deals damage today — p. 63 states no
            # penalty for a failed save and Suffocation deals Exhaustion — so this phase
            # discharges what an earlier one left rather than what it creates. The clause is
            # that all three adjudicating phases drain through one helper: three call sites
            # is how one gets missed, and the rule that eventually deals damage here should
            # be correct on arrival rather than by review.
            (
                state,
                compelled,
                compelled_narrations,
                compelled_unresolvable,
            ) = yield from self._concentration_saves(state)
            rulings.extend(compelled)
            narrations.extend(compelled_narrations)
            unresolvable.extend(compelled_unresolvable)

            pending = self.end_turn_obligations(state, actor_id)
            if not pending:
                break
            obligation = pending[0]

            ruling, state = self.adjudicator.adjudicate(state, _obligation_declaration(obligation))
            # Discharged whether it succeeded, failed, or was refused. p. 63 gives one
            # attempt per turn, and a rejected obligation that stayed outstanding would
            # spin this loop forever.
            state = state.with_obligation_discharged(actor_id, obligation.rule_id)

            if ruling.status is Status.REJECTED:
                unresolvable.append(obligation)
                continue

            rulings.append(ruling)
            narrations.append((yield from self._narrate(actor_id, ruling)))

        return TurnEnd(
            state=state,
            rulings=tuple(rulings),
            narrations=tuple(narrations),
            unresolvable=tuple(unresolvable),
        )

    # --- The fourth occasion: saves damage compelled (0036) ---------------------------

    def _concentration_saves(
        self, state: EncounterState
    ) -> Generator[
        Request,
        Response,
        tuple[EncounterState, tuple[Ruling, ...], tuple[str | None, ...], tuple[Obligation, ...]],
    ]:
        """Roll every Concentration save owed, oldest first (0036 clause 1).

        The **fourth occasion**. `start_turn`'s docstring states the principle: nothing here
        creates a second path to an outcome, it creates another occasion on which the
        existing path is taken. Each owed save is turned into an engine-authored
        `Declaration` by `_obligation_declaration`, exactly as a turn obligation is, and
        `Adjudicator.adjudicate` produces the result (R1). The engine rolls it (R4).

        **One helper, called from all three adjudicating phases** (0036 clause 6). Burning
        deals its damage at the start of a turn (p. 178) and an attack deals it in the
        middle, so a discharge point after `run` alone would serve attacks and silently miss
        the hazard — and the hazard is the case with no attacker to make the omission
        obvious.

        **Drained, not iterated** — and more sharply than in `start_turn`, because a save
        that fails ends the Concentration the *remaining* debts were owed for. Re-reading
        each pass is what lets that be noticed.

        **Not keyed by `discharged`** (0036 clause 3). A debt is owed once per damage
        instance; `discharged` means owed once per turn. A creature struck twice by a
        Multiattack owes two saves, and keying them the existing way would suppress the
        second — a compelled save that silently does not happen.
        """
        rulings: list[Ruling] = []
        narrations: list[str | None] = []
        unresolvable: list[Obligation] = []

        while True:
            owed = state.forced_saves_owed
            if not owed:
                break
            debt = owed[0]

            # Whether the save is still owed is read off state, the way
            # `start_turn_obligations` reads whether Burning is (0027 clause 2). A debt for a
            # creature that has left the encounter is dropped rather than rolled. This is not
            # a skip — there is nobody for the outcome to be about.
            #
            # **The second test is p. 179's and only p. 179's** (0048). A creature that has
            # already lost the Concentration an earlier failed save ended owes nothing: the
            # save is compelled *to maintain* Concentration, and there is nothing left to
            # maintain. Topple has no counterpart — a creature already Prone still rolls, and
            # p. 90 states no exemption — so the branch is keyed by rule rather than applied
            # to every debt. A third rule with its own staleness adds a branch here; a fourth
            # wants a registry, and this comment is where that decision starts.
            if not state.has(debt.combatant_id):
                state = state.with_forced_save_discharged(debt.combatant_id)
                continue
            target = state.combatant(debt.combatant_id)
            if debt.rule_id == CONCENTRATION_RULE_ID and not target.concentration.active:
                state = state.with_forced_save_discharged(debt.combatant_id)
                continue

            # The label was written where the trigger fired (0048): the loop sees a debt, and
            # only the rule that recorded it knows what happened.
            obligation = Obligation(
                actor_id=debt.combatant_id,
                rule_id=debt.rule_id,
                label=debt.label,
            )
            ruling, state = self.adjudicator.adjudicate(state, _obligation_declaration(obligation))
            # Dropped whether it succeeded, failed or was refused, for the reason the two
            # obligation loops discharge regardless of outcome: p. 179 gives one save per
            # instance of damage either way, and a debt that outlived its adjudication
            # would spin this loop forever.
            state = state.with_forced_save_discharged(debt.combatant_id)

            if ruling.status is Status.REJECTED:
                unresolvable.append(obligation)
                continue

            rulings.append(ruling)
            # Narrated **for the creature that took the damage**, who is usually not the
            # creature whose turn it is: an attack on the monster's turn breaks the
            # player's Concentration, and R29's debt belongs to whoever the ruling is about.
            narrations.append((yield from self._narrate(debt.combatant_id, ruling)))

        return state, tuple(rulings), tuple(narrations), tuple(unresolvable)

    def _terminated(
        self,
        actor_id: str,
        reason: TerminalReason,
        *,
        state: EncounterState,
        refusals: tuple[Ruling, ...],
        offered: tuple[LegalAction, ...],
        unresolved: tuple[str, ...] = (),
    ) -> TurnOutcome:
        """Record the termination, then return it.

        R30's report is derived from the ledger without the agent's cooperation, so a slot
        that ended without a Ruling has to leave a trace of its own. Returning the reason
        to the driver and not writing it down would put the one fact triage needs in the
        only place a session review cannot reach.
        """
        self.adjudicator.record_termination(actor_id, str(reason), refusals)
        return TurnOutcome(
            state=state,
            terminal=reason,
            refusals=refusals,
            offered=offered,
            unresolved=unresolved,
        )

    # --- The three loops -------------------------------------------------------------

    def _resolve(
        self,
        state: EncounterState,
        declaration: Declaration,
        situation: Mapping[str, object],
    ) -> Generator[Request, Response, tuple[Ruling, EncounterState, tuple[str, ...] | None]]:
        """Adjudicate, suspending on a block until the unresolved set stops shrinking.

        A block resumes *this* declaration. The agent is not asked again, and the retry
        budget is not charged — the declaration was accepted, and a driver's omission is
        not the agent's failure.
        """
        outstanding: tuple[str, ...] | None = None
        while True:
            # `resuming` is what keeps the record honest about who acted (#59). The agent
            # declared once; every pass after the first is the engine asking its own port
            # again, and an unmarked second `declaration` entry said otherwise.
            ruling, state = self.adjudicator.adjudicate(
                state, declaration, situation=situation, resuming=outstanding is not None
            )
            if ruling.status is not Status.BLOCKED:
                return ruling, state, None

            if outstanding is not None and set(ruling.unresolved) >= set(outstanding):
                # The set did not shrink, so another round has nothing to wait for.
                return ruling, state, ruling.unresolved
            outstanding = ruling.unresolved

            response = yield BlockedFactRequest(
                declaration=declaration, unresolved=ruling.unresolved
            )
            for fact in _expect(response, FactsSupplied).facts:
                self.adjudicator.port.put(fact)

    def _narrate(self, actor_id: str, ruling: Ruling) -> Generator[Request, Response, str | None]:
        """R29. A narration that never arrives is a named state, not a silent hole."""
        self._owed[actor_id] = ruling
        response = yield NarrationRequest(ruling=ruling)
        text = _expect(response, Narrated).text
        if text is None:
            return None
        self._owed.pop(actor_id, None)
        self.adjudicator.record_narration(ruling, text)
        return text

    def _terminal_for(self, previous: Sequence[Ruling], latest: Ruling) -> TerminalReason | None:
        """0005. No-progress first, then the budget; churn is named by what differed."""
        if previous and previous[-1].signature == latest.signature:
            return TerminalReason.NO_PROGRESS
        if self.budget is None:
            return None
        if len(previous) + 1 < self.budget:
            return None

        statuses = {r.status for r in [*previous, latest]}
        if statuses == {Status.CHALLENGED}:
            return TerminalReason.CHALLENGE_CHURN
        if statuses == {Status.REJECTED}:
            return TerminalReason.REJECTION_CHURN
        return TerminalReason.MIXED_CHURN


def _obligation_declaration(obligation: Obligation) -> Declaration:
    """The declaration an obligation is adjudicated under, authored by the engine.

    A `Declaration` is the artefact the *agent* is accountable for, and this one is not the
    agent's — which is the point of 0023 clause 2. It is marked improvised because the
    obligation is not one of the read surface's enumerated legal actions: p. 63 compels it
    rather than offering it, so it is legal in a sense the action list does not model.

    `alternatives` is empty and `read_token` is `None`, so the ruling's verdict comes back
    `unread`. That is the honest value: no read surface offered this, because nothing was
    choosing.
    """
    return Declaration(
        actor_id=obligation.actor_id,
        intent=Intent(improvised=True, label=obligation.label),
        rule_id=obligation.rule_id,
    )


_T = TypeVar("_T", bound=Declared | Narrated | FactsSupplied)


def _expect(response: Response, kind: type[_T]) -> _T:
    """A driver that answers the wrong request is a driver bug, named as one."""
    if not isinstance(response, kind):
        raise TypeError(
            f"the loop asked for {kind.__name__} and the driver sent {type(response).__name__}"
        )
    return response
