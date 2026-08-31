"""p. 187's Simultaneous Effects: the engine was choosing an order the document gives away.

> If two or more things happen at the same time on a turn, the person at the game table —
> player or GM — **whose turn it is decides the order** in which those things happen. For
> example, if two effects occur at the start of a player character's turn, the player decides
> which of the effects happens first.

`start_turn` took `pending[0]` and `end_turn` took `pending[0]`, which is list order. That is
not idle: a creature at 0 hit points that is also Burning owes a Death Saving Throw and
Burning's damage **at the same instant**, and which resolves first decides whether it is alive
to take the second.

**This is not R4.** Ordering is not an outcome and the engine still rolls everything. It is
R18's other half — a choice the rules give to a person is one the engine must ask for rather
than make — which is `SaveAbilityRequest`'s shape exactly (0053).

`end_turn_obligations` had already noticed, and said so honestly: its docstring called its own
order *"a stable order rather than a rule ... stated because a reader would otherwise assume
one exists."* The rule exists. It is p. 187, and it gives the choice away.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.save_ends import save_ends_rule_id
from srd_rules_engine.loop.drivers import ScriptedDriver, drive
from srd_rules_engine.loop.turn import OrderChosen, OrderRequest, TurnEnd
from test_turn_end import NEVER, build_loop, poisoned


def _two_owed() -> object:
    """A creature owing two save-ends obligations at the same instant."""
    state = poisoned(NEVER)
    return state.with_condition(
        "first", Condition.BLINDED, duration=state.for_minutes(1, "first", save=NEVER)
    )


def _run(loop, state, *, orders: list[str | None] | None = None):  # type: ignore[no-untyped-def]
    driver = ScriptedDriver(narrations=["it shrugs, or does not"] * 6, orders=orders or [])
    return drive(loop.end_turn(state, "first"), driver)


# --- The engine asks -----------------------------------------------------------------------


def test_two_things_at_once_are_offered_for_ordering(tmp_path: Path) -> None:
    """The request the engine did not make before. Asserted by capturing it rather than by
    the result, because both orders produce two rulings and the result cannot tell them
    apart."""
    seen: list[OrderRequest] = []
    gen = build_loop(tmp_path).end_turn(_two_owed(), "first")  # type: ignore[arg-type]
    request = next(gen)
    try:
        while True:
            if isinstance(request, OrderRequest):
                seen.append(request)
                request = gen.send(OrderChosen(request.pending[0].rule_id))
            else:
                from srd_rules_engine.loop.turn import Narrated

                request = gen.send(Narrated("it shrugs"))
    except StopIteration:
        pass

    assert seen, "p. 187 was never asked"
    assert len(seen[0].pending) == 2
    assert seen[0].actor_id == "first", "p. 187 names the person by whose turn it is"


def test_one_obligation_is_not_two_things_happening_at_once(tmp_path: Path) -> None:
    """Asked only when there is a choice. A single obligation is not "two or more things",
    and asking anyway would be ceremony the document does not ask for."""
    seen: list[OrderRequest] = []

    class Watching(ScriptedDriver):
        def __call__(self, request):  # type: ignore[no-untyped-def]
            if isinstance(request, OrderRequest):
                seen.append(request)
            return super().__call__(request)

    drive(
        build_loop(tmp_path).end_turn(poisoned(NEVER), "first"),
        Watching(narrations=["it shrugs"] * 4),
    )

    assert seen == [], "one thing is not simultaneous with anything"


# --- The answer is honoured -----------------------------------------------------------------


def test_the_chosen_obligation_resolves_first(tmp_path: Path) -> None:
    """The point of asking. Both orders produce two rulings, so the assertion is on which
    ruling came **first** — a test on the count would pass whatever the engine did."""
    blinded = save_ends_rule_id(Condition.BLINDED)
    poison = save_ends_rule_id(Condition.POISONED)

    first = _run(build_loop(tmp_path / "a"), _two_owed(), orders=[blinded])
    second = _run(build_loop(tmp_path / "b"), _two_owed(), orders=[poison])

    assert isinstance(first, TurnEnd) and isinstance(second, TurnEnd)
    assert first.rulings[0].declaration.rule_id == blinded
    assert second.rulings[0].declaration.rule_id == poison
    assert {r.declaration.rule_id for r in first.rulings} == {blinded, poison}, "both still ran"


def test_naming_something_not_owed_is_a_driver_bug(tmp_path: Path) -> None:
    """There is no refusal in p. 187 — the things happen either way, and only their order is
    the person's to decide. So an answer naming something not owed is named as the bug it
    is rather than quietly falling back to the engine's order."""
    with pytest.raises(ValueError, match="not owed at this moment"):
        _run(build_loop(tmp_path), _two_owed(), orders=["srd:not-a-rule-owed-here"])
