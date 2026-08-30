"""When a turn-bounded effect dies, and whether the encounter has passed it (0050).

Extracted from `core.pending_rolls`, which
[0049](../../../docs/decisions/0049-advantage-that-outlives-its-roll.md) wrote it for.
p. 90's Slow needs the same vocabulary and is not about rolls at all — it reduces a Speed —
so the boundary lives here and both mechanisms import it. `pending_rolls` re-exports both
names, so nothing 0049 shipped moved for a reader.

**What is shared is the boundary, not the mechanism.** A `PendingAdvantage` is *spent* by the
roll it applies to; a Slow reduction simply stands until its window closes. They agree only
about how a window is named and when it has passed, which is exactly what is here.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class TurnBounded(Protocol):
    """Anything that dies at a named turn boundary (0050).

    A structural type rather than a base class, because the two things that satisfy it share
    no behaviour: `PendingAdvantage` is spent by a roll and a Slow reduction simply stands.
    What they have in common is three fields and the question below.
    """

    @property
    def expires_after_actor_id(self) -> str: ...

    @property
    def expires_in_round(self) -> int: ...

    @property
    def expires_at(self) -> TurnBoundary: ...


class TurnBoundary(StrEnum):
    """Which end of a turn a span is measured to.

    A vocabulary rather than a boolean, because the two are mutually exclusive and a
    `bool` at a call site reads as neither (0019). `Duration` needs no such thing — every
    span it counts ends at `END` — so this lives here with the one mechanism that needs both.
    """

    #: "before the **start** of your next turn" (p. 90, Sap).
    START = "start"
    #: "before the **end** of your next turn" (p. 90, Vex).
    END = "end"


def is_live(
    token: TurnBounded,
    *,
    round_number: int,
    turn_index: int | None,
    order: tuple[str, ...],
) -> bool:
    """Whether the encounter has yet to pass the boundary this token dies at.

    `turn_index is None` is an encounter that has not started, so nothing has been passed and
    every token is live — the same honest answer `active_id` gives for the same state.

    A token whose expiring creature has left the order is live: the boundary it named can no
    longer arrive, and withdrawing a granted benefit because its clock left the encounter
    would be the engine deciding an outcome nothing in the document decides.
    """
    if turn_index is None:
        return True
    if round_number < token.expires_in_round:
        return True
    if round_number > token.expires_in_round:
        return False
    if token.expires_after_actor_id not in order:
        return True
    at = order.index(token.expires_after_actor_id)
    if token.expires_at is TurnBoundary.START:
        # Dies the moment that turn begins, so reaching it is already too late.
        return turn_index < at
    # Survives that whole turn, and dies as it closes.
    return turn_index <= at
