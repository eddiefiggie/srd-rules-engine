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
    Adjudicator,
    Declaration,
    EncounterState,
    Fact,
    LegalAction,
    ReadResult,
    Ruling,
    Status,
    read,
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

    @property
    def produced_outcome(self) -> bool:
        return self.ruling is not None and self.ruling.is_outcome


class NarrationOwed(Exception):
    """R29. The previous Ruling for this actor has no narration yet."""


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
            return TurnOutcome(
                state=state,
                ruling=ruling,
                refusals=tuple(refusals),
                offered=offered.actions,
                narration=narration,
                missing_narration=narration is None,
            )

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
            ruling, state = self.adjudicator.adjudicate(state, declaration, situation=situation)
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


_T = TypeVar("_T", bound=Declared | Narrated | FactsSupplied)


def _expect(response: Response, kind: type[_T]) -> _T:
    """A driver that answers the wrong request is a driver bug, named as one."""
    if not isinstance(response, kind):
        raise TypeError(
            f"the loop asked for {kind.__name__} and the driver sent {type(response).__name__}"
        )
    return response
