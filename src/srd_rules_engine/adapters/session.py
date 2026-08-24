"""A turn held between calls, so a stateless transport can drive a generator (#97).

The turn loop is a generator yielding typed requests (decision 0001). A transport like MCP
makes stateless calls. A call cannot resume a generator a previous call left suspended
unless something holds it, so this does: one `Session` owns one live loop and answers
**what the engine is waiting for right now**.

## Why the alternative is not available

The obvious stateless design exposes adjudication as a tool and lets the caller assemble
turns itself. That forfeits the product. `AGENTS.md` is explicit:

> The skip guarantee holds only for callers the turn loop drives. A consumer calling
> adjudication directly gets outcome authority without skip prevention.

So an adapter that reached `adjudicate` would be a *supported* way to get outcome authority
without challenge detection — the exact failure this engine exists to remove, shipped as a
feature. Every path here goes through the loop, and there is no tool that does otherwise.

## What a lost session costs, and what it does not

The suspension is process state. If it is lost — a crash, a restart — the *ledger survives*,
because entries are durable before anything escapes the engine (decision 0002). What is lost
is the position within a turn: a challenge awaiting a re-declaration, or a ruling awaiting
its narration.

That is recoverable rather than corrupting. A new `Session` starts a fresh turn from the
recorded state, and R29's narration debt is what notices anything left dangling: a ruling
whose narration never arrived leaves the actor owing one, and the loop refuses its next
declaration until it is paid. A lost session therefore surfaces as a refusal, not as a
silently skipped turn.

The debt lives on the `TurnLoop`, not here, so it survives a session only if the loop does.
That is a real limit and it is disclosed rather than assumed away.

## The shape

`begin` and each `answer` return a `Pending` — one of four states saying what is wanted
next. A caller never guesses; it reads the state and calls the matching method. Sending the
wrong kind raises rather than being coerced, because a coerced response is a declaration
nobody made.
"""

from __future__ import annotations

from collections.abc import Generator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from srd_rules_engine.core import (
    Declaration,
    EncounterState,
    Fact,
    LegalAction,
    ReadResult,
    Ruling,
    read,
)
from srd_rules_engine.loop import (
    BlockedFactRequest,
    DeclarationRequest,
    Declared,
    FactsSupplied,
    Narrated,
    NarrationRequest,
    Request,
    Response,
    TurnEnd,
    TurnLoop,
    TurnOutcome,
)

#: What a session is doing when it is not waiting for anything.
IDLE: Final = "idle"


class SessionError(Exception):
    """A call that does not match what the engine is waiting for."""


@dataclass(frozen=True)
class AwaitingDeclaration:
    """The engine wants a declaration for `actor_id`.

    `refusals` carries the challenges and rejections already returned this slot, so a caller
    that reconnected mid-turn can see why it is being asked again rather than assuming the
    first attempt was lost.
    """

    actor_id: str
    offered: ReadResult
    refusals: tuple[Ruling, ...] = ()


@dataclass(frozen=True)
class AwaitingFacts:
    """The declaration was accepted and stalled: these facts are unresolved.

    A suspension rather than a refusal (decision 0010), so the declaration is not re-made and
    the retry budget is not charged.
    """

    actor_id: str
    unresolved: tuple[str, ...]


@dataclass(frozen=True)
class AwaitingNarration:
    """A Ruling exists and R29 owes it a narration before this actor declares again."""

    actor_id: str
    ruling: Ruling


@dataclass(frozen=True)
class Finished:
    """The declaration slot ended. `outcome` carries what it produced, terminal reason and
    all.

    **Not the same as the turn being over.** 0023 clause 1 puts the turn's end in its own
    phase, so a caller finishes here and then calls `end_turn` — which `EncounterState`
    enforces rather than documents, by refusing to advance while an obligation stands.
    """

    actor_id: str
    outcome: TurnOutcome


@dataclass(frozen=True)
class TurnEnded:
    """Every end-of-turn obligation resolved (0023). The turn may now advance."""

    actor_id: str
    ended: TurnEnd


Pending = AwaitingDeclaration | AwaitingFacts | AwaitingNarration | Finished | TurnEnded


@dataclass
class Session:
    """One live turn loop, held between calls.

    Mutable by necessity — a suspended generator is state — and the only mutable thing in
    the adapter. Everything it returns is frozen.
    """

    loop: TurnLoop
    state: EncounterState
    #: The live phase — a declaration slot or a turn end. One field rather than two,
    #: because a session holds at most one suspension and two would let it hold both.
    _turn: Generator[Request, Response, TurnOutcome] | None = field(default=None, repr=False)
    _ending: Generator[Request, Response, TurnEnd] | None = field(default=None, repr=False)
    _actor: str | None = field(default=None, repr=False)
    _pending: Pending | None = field(default=None, repr=False)

    @property
    def pending(self) -> Pending | None:
        """What the engine is waiting for, or `None` between turns."""
        return self._pending

    def look(self, actor_id: str) -> ReadResult:
        """The read surface, without starting a turn (R19: mutates nothing, records nothing).

        Separate from `begin` on purpose: an agent may want to look before committing to a
        turn, and looking must never be the thing that starts one.
        """
        return read(self.state, actor_id)

    def begin(self, actor_id: str, *, situation: Mapping[str, object] | None = None) -> Pending:
        """Start a turn and run it to its first question."""
        if self._turn is not None:
            raise SessionError(
                f"a turn for {self._actor!r} is already open. Finish it, or the engine would "
                "be holding two suspensions and answering for the wrong one"
            )
        self._actor = actor_id
        self._turn = self.loop.run(self.state, actor_id, situation=situation)
        return self._advance(None)

    def end_turn(self, actor_id: str) -> Pending:
        """Resolve the end of `actor_id`'s turn (0023 clause 1).

        Held exactly as a declaration slot is, because an adapter that could suspend one
        phase and not the other would make the turn's end the one part of a turn a
        stateless transport could not drive.
        """
        if self._turn is not None or self._ending is not None:
            raise SessionError(
                f"a phase for {self._actor!r} is already open. Finish it, or the engine "
                "would be holding two suspensions and answering for the wrong one"
            )
        self._actor = actor_id
        self._ending = self.loop.end_turn(self.state, actor_id)
        return self._advance(None)

    def declare(self, declaration: Declaration) -> Pending:
        """Answer an `AwaitingDeclaration` with the agent's declaration."""
        self._expect(AwaitingDeclaration)
        return self._advance(Declared(declaration))

    def narrate(self, text: str | None) -> Pending:
        """Answer an `AwaitingNarration`. `None` withholds it, which R29 records rather than
        forbids — narration bounds are advisory (R7), and the debt is what enforces order."""
        self._expect(AwaitingNarration)
        return self._advance(Narrated(text))

    def supply(self, facts: Sequence[Fact]) -> Pending:
        """Answer an `AwaitingFacts` with what the port could not resolve."""
        self._expect(AwaitingFacts)
        return self._advance(FactsSupplied(tuple(facts)))

    def _expect(self, kind: type[Pending]) -> None:
        if self._turn is None and self._ending is None:
            raise SessionError("no phase is open; call begin or end_turn first")
        if not isinstance(self._pending, kind):
            raise SessionError(
                f"the engine is waiting for {type(self._pending).__name__}, not "
                f"{kind.__name__}. Answering the wrong question would put a response in the "
                "record against a request nobody made"
            )

    def _advance(self, response: Response | None) -> Pending:
        """Push whichever phase is live one step and translate what it asks for next."""
        assert self._actor is not None
        phase: Generator[Request, Response, TurnOutcome] | Generator[Request, Response, TurnEnd]
        phase = self._turn if self._turn is not None else self._ending  # type: ignore[assignment]
        assert phase is not None
        try:
            request = phase.send(response) if response is not None else next(phase)
        except StopIteration as stop:
            produced = stop.value
            self.state = produced.state
            finishing = self._turn is not None
            self._turn = None
            self._ending = None
            self._pending = (
                Finished(actor_id=self._actor, outcome=produced)
                if finishing
                else TurnEnded(actor_id=self._actor, ended=produced)
            )
            self._actor = None
            return self._pending

        self._pending = _translate(request)
        return self._pending


def _translate(request: Request) -> Pending:
    """One typed request in, one typed pending state out. No behaviour, just shape."""
    if isinstance(request, DeclarationRequest):
        return AwaitingDeclaration(
            actor_id=request.actor_id,
            offered=request.offered,
            refusals=tuple(request.refusals),
        )
    if isinstance(request, BlockedFactRequest):
        return AwaitingFacts(
            actor_id=request.declaration.actor_id, unresolved=tuple(request.unresolved)
        )
    if isinstance(request, NarrationRequest):
        return AwaitingNarration(
            actor_id=request.ruling.declaration.actor_id, ruling=request.ruling
        )
    raise SessionError(
        f"the loop yielded {type(request).__name__}, which this adapter cannot serve"
    )


def offered_keys(pending: Pending) -> tuple[str, ...]:
    """The action keys on offer, or empty for any state that is not offering a menu."""
    return pending.offered.keys if isinstance(pending, AwaitingDeclaration) else ()


def offered_actions(pending: Pending) -> tuple[LegalAction, ...]:
    return pending.offered.actions if isinstance(pending, AwaitingDeclaration) else ()
