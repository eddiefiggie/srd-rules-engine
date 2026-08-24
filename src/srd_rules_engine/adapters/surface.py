"""What every adapter must expose, and what none of them may (R34, #133).

Two adapters exist and a third is coming, so the rules that hold across all of them live
here rather than in whichever one was written first. Both are absences or completeness
claims, and both are the kind of thing that survives being written down once and decays
being written down twice.

## The forbidden surface

`AGENTS.md`: "The skip guarantee holds only for callers the turn loop drives. A consumer
calling adjudication directly gets outcome authority without skip prevention."

So an adapter command that reached `adjudicate` would be a **supported** route to an outcome
with no challenge detection — the exact failure this engine exists to remove, shipped as a
feature. `FORBIDDEN_COMMAND_NAMES` is asserted absent from every adapter's surface by
`tests/test_adapters.py`, once, over all of them.

## The completeness claim

`Session` answers with a `Pending` saying what the engine wants next. An adapter that cannot
reach one of those states is an adapter that cannot finish a turn — which is not
hypothetical: #110 added a phase to the loop and the MCP adapter shipped unable to drive it,
with a full green suite, because every test asked what the surface *contained* and none asked
whether it was *complete* (#134).

`pending_members()` is that question in a form a test can ask.
"""

from __future__ import annotations

from typing import Final, get_args

from srd_rules_engine.adapters.session import Pending

#: Anything that would reach an outcome without the loop. Asserted absent from every
#: adapter, rather than per adapter — the second copy is the one that goes stale.
FORBIDDEN_COMMAND_NAMES: Final[frozenset[str]] = frozenset(
    {"adjudicate", "rule", "resolve", "roll"}
)


def pending_members() -> frozenset[type]:
    """Every state `Session` can be waiting in.

    Derived from the union rather than listed, because a list is what let `TurnEnded` be
    added to `Pending` with nothing noticing that no adapter could reach it.
    """
    return frozenset(get_args(Pending))
