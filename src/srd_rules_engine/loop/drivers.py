"""Two reference drivers, and neither is an LLM.

R8 ships the seam with bindings so v1 is playable with **no model and no network**: a
scripted driver for tests, and a command-line driver where the human answers. That is
deliberate — a reference binding that needed a model would make every test a model call
and would quietly couple the engine to one, which is a declared non-goal.

Both are drivers in the same sense: they answer typed requests with typed responses and
never see the ledger, the dice, or anything that decides an outcome.

The human driver takes its input and output as callables rather than touching `stdin` and
`stdout` directly. That is not only for tests — an adapter embedding the loop elsewhere
needs the same seam, and a driver that reaches for the process's streams cannot be
embedded twice.
"""

from __future__ import annotations

from collections.abc import Callable, Generator, Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import TypeVar

from srd_rules_engine.core import Declaration, Fact, Intent
from srd_rules_engine.loop.turn import (
    BlockedFactRequest,
    DeclarationRequest,
    Declared,
    FactsSupplied,
    HitDieRequest,
    Narrated,
    NarrationRequest,
    ReactionDeclined,
    ReactionRequest,
    Request,
    Response,
    SaveAbilityChosen,
    SaveAbilityRequest,
    SpendDeclined,
    SpendHitDie,
    TurnEnd,
    TurnOutcome,
    TurnStart,
)

_T = TypeVar("_T")


class DriverExhausted(Exception):
    """A scripted driver ran out of answers before the loop ran out of questions."""


_R = TypeVar("_R", TurnOutcome, TurnStart, TurnEnd)


def drive(
    loop: Generator[Request, Response, _R],
    driver: Callable[[Request], Response],
) -> _R:
    """Pump a loop phase with a driver. The loop asks; the driver answers; nothing else.

    Generic over what the phase returns, because all three phases are pumped exactly the
    same way (0023 clause 1) and a second pump differing only in its return annotation is a
    second place for the seam to drift.

    `TurnStart` joined the constraint late, which is the drift this docstring warned about
    happening: 0027 added the phase and not the type here, so `tests/test_turn_start.py`
    hand-rolled a pump of its own. One pump, three phases.
    """
    try:
        request = next(loop)
        while True:
            request = loop.send(driver(request))
    except StopIteration as stop:
        produced: _R = stop.value
        return produced


@dataclass
class ScriptedDriver:
    """Answers from a prepared script. No model, no network, fully deterministic."""

    declarations: Sequence[Declaration] = ()
    narrations: Sequence[str | None] = ()
    facts: Sequence[Sequence[Fact]] = ()
    #: 0053. Which ability to save with, in the order the choices are asked for. A script that
    #: runs out raises like any other, because a save whose choice nobody scripted is a save
    #: the test did not mean to reach — silently substituting one would be the driver choosing.
    save_abilities: Sequence[str | None] = ()
    #: 0072. What to answer each `ReactionRequest` with: a `Declaration` to take p. 185's
    #: Opportunity Attack, or `None` to decline it. A script that runs out raises, for the
    #: reason `save_abilities` does — declining by default would make every unscripted test
    #: silently assert that nobody reacts, which is the assertion most likely to be wrong.
    reactions: Sequence[Declaration | None] = ()
    #: p. 187's offer, one entry per time it is made: `True` spends a Hit Point Die (0082).
    #: Running out declines, because a Short Rest that ends early is a legal rest.
    hit_dice: Sequence[bool] = ()
    _declarations: Iterator[Declaration] = field(init=False)
    _narrations: Iterator[str | None] = field(init=False)
    _facts: Iterator[Sequence[Fact]] = field(init=False)
    _save_abilities: Iterator[str | None] = field(init=False)
    _reactions: Iterator[Declaration | None] = field(init=False)
    _hit_dice: Iterator[bool] = field(init=False)

    def __post_init__(self) -> None:
        self._declarations = iter(self.declarations)
        self._narrations = iter(self.narrations)
        self._facts = iter(self.facts)
        self._save_abilities = iter(self.save_abilities)
        self._reactions = iter(self.reactions)
        self._hit_dice = iter(self.hit_dice)

    def __call__(self, request: Request) -> Response:
        if isinstance(request, DeclarationRequest):
            return Declared(_next(self._declarations, "declaration"))
        if isinstance(request, NarrationRequest):
            return Narrated(_next(self._narrations, "narration"))
        if isinstance(request, SaveAbilityRequest):
            return SaveAbilityChosen(_next(self._save_abilities, "save ability"))
        if isinstance(request, ReactionRequest):
            declared = _next(self._reactions, "reaction")
            return ReactionDeclined() if declared is None else Declared(declared)
        if isinstance(request, HitDieRequest):
            # p. 187's offer (0082). The script says how many dice to spend, and the offer
            # is repeated until it stops saying yes — so a script that runs out declines,
            # rather than raising the way a missing declaration does. A rest that ends early
            # is a legal rest; a turn with no declaration is a driver defect.
            return (
                SpendHitDie()
                if _next(self._hit_dice, "hit die", default=False)
                else (SpendDeclined())
            )
        return FactsSupplied(tuple(_next(self._facts, "facts", default=())))


@dataclass
class HumanCliDriver:
    """A person answers at a terminal. Input and output are injected, never assumed.

    The prompts state what is legal and what was refused, because an agent — human or
    otherwise — that is not told why its last declaration was refused will repeat it, and
    a repeat is what the retry bound terminates on.
    """

    ask: Callable[[str], str]
    show: Callable[[str], None] = print
    facts_for: Callable[[BlockedFactRequest], Iterable[Fact]] = lambda _: ()

    def __call__(self, request: Request) -> Response:
        if isinstance(request, DeclarationRequest):
            return Declared(self._declare(request))
        if isinstance(request, NarrationRequest):
            self.show(f"Ruling: {request.ruling.why()}")
            self.show("You may claim: " + "; ".join(request.ruling.bounds.may or ("nothing",)))
            self.show("You may not claim: " + "; ".join(request.ruling.bounds.may_not))
            text = self.ask("Narrate within those bounds (blank to decline): ").strip()
            return Narrated(text or None)
        if isinstance(request, SaveAbilityRequest):
            # 0053. The person controlling the target picks, and a blank answer is a refusal
            # rather than a default — there is no ability to fall back to that would not be
            # the engine choosing.
            self.show(f"{request.actor_id} must save: {request.label} (DC {request.dc})")
            self.show(f"  {request.dc_basis}")
            offered = ", ".join(
                f"{option.ability} ({option.modifier:+d})" for option in request.options
            )
            self.show(f"  It chooses which: {offered}")
            chosen = self.ask("Save with which ability (blank to decline)? ").strip()
            return SaveAbilityChosen(chosen or None)
        if isinstance(request, ReactionRequest):
            # 0072 clause 4. p. 185 says a creature "**can** make an Opportunity Attack", so
            # declining is an answer rather than a missing one, and a blank line gives it.
            self.show(
                f"{request.reactor_id} may take an Opportunity Attack as "
                f"{request.mover_id} leaves its reach (p. 185)"
            )
            offered = ", ".join(action.key for action in request.offered)
            self.show(f"  Offered: {offered}")
            action = self.ask("Opportunity Attack key (blank to decline): ").strip()
            if not action:
                return ReactionDeclined()
            rule_id = self.ask("Rule id: ").strip()
            return Declared(
                Declaration(
                    actor_id=request.reactor_id,
                    intent=Intent(action_key=action),
                    rule_id=rule_id,
                )
            )
        if isinstance(request, HitDieRequest):
            # p. 187 offers again after every roll, so this is asked once per die. A blank
            # line stops the rest, which is the same shape as declining a Reaction.
            self.show(
                f"{request.resting_id} is on a Short Rest with {request.remaining} Hit "
                f"Point Dice left, on {request.hit_points} of {request.max_hit_points} "
                "hit points (p. 187)"
            )
            spend = self.ask("Spend a Hit Point Die? [y/N] ").strip().lower()
            return SpendHitDie() if spend.startswith("y") else SpendDeclined()
        self.show(f"Blocked on: {', '.join(request.unresolved)}")
        return FactsSupplied(tuple(self.facts_for(request)))

    def _declare(self, request: DeclarationRequest) -> Declaration:
        for refused in request.refusals:
            self.show(f"Refused: {refused.why()}")
        legal = ", ".join(action.key for action in request.offered.actions) or "nothing"
        self.show(f"Legal for {request.actor_id}: {legal}")

        action = self.ask("Action key (blank if improvised): ").strip()
        rule_id = self.ask("Rule id (blank to claim no test is needed): ").strip()
        reason = "" if rule_id else self.ask("Why is no test needed? ").strip()
        label = "" if action else self.ask("Describe what you are doing: ").strip()

        return Declaration(
            actor_id=request.actor_id,
            intent=Intent(action_key=action) if action else Intent(improvised=True, label=label),
            rule_id=rule_id or None,
            no_test_reason=reason or None,
            alternatives=request.offered.actions,
            read_token=request.offered.token,
        )


def _next(source: Iterator[_T], what: str, *, default: _T | None = None) -> _T:
    try:
        return next(source)
    except StopIteration:
        if default is not None:
            return default
        raise DriverExhausted(
            f"the loop asked for a {what} and the script had none left. A scripted driver "
            "answers every question the loop can ask, or the turn cannot finish"
        ) from None
