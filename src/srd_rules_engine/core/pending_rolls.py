"""Advantage that outlives the roll that granted it (p. 90, #318, #319, 0049).

p. 90's Vex and Sap are one mechanism seen from two sides:

> **Vex.** If you hit a creature with this weapon **and deal damage to the creature**, you
> have Advantage on your next attack roll against that creature before the **end** of your
> next turn.

> **Sap.** If you hit a creature with this weapon, that creature has Disadvantage on its next
> attack roll before the **start** of your next turn.

Every other source of Advantage in this engine is a **standing** fact asked at the moment of
the roll — a condition held, a target Dodging, a weapon that is Heavy in these hands. Each is
recomputed from state every time, and nothing is spent. These two are not: they are granted by
one roll, held, and consumed by another.

## Four axes, and Vex and Sap differ on all four

|  | Vex | Sap |
|---|---|---|
| Sign | Advantage | Disadvantage |
| Held by | the attacker | the creature that was hit |
| Scoped to | attacks **against that creature** | any attack the holder makes |
| Expires | **end** of the attacker's next turn | **start** of the attacker's next turn |

The last row is the one with no precedent. `DurationKind.END_OF_NEXT_TURN` is Vex's window
exactly, and the encounter axis retires it where every condition is retired — at the end of a
named creature's turn. Sap ends at the **start** of one, and nothing in `core.duration` counts
that: `Duration`'s own docstring says the encounter axis is "the end of that creature's turn,
in that round".

## Liveness is derived, and the sweep is hygiene

A token names the boundary it dies at, and whether it is still live is **computed** from where
the encounter has reached rather than applied by a phase that has to remember. Two reasons, and
the second is the one that decided it:

* Sap would otherwise need a start-of-turn retirement hook the loop does not have, and adding
  one to serve a single property is the shape 0036 clause 6 warns about.
* A derived answer **cannot silently outlive its window**. A missed sweep leaves a dead row in
  state; a missed retirement grants Advantage in a round the document had already ended. Those
  fail in opposite directions and only one of them is visible.

`EncounterState.advanced_turn` sweeps what has died, so the queue does not grow without bound.
That is tidiness, and the rule is `is_live`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from srd_rules_engine.core.d20 import Advantage

# Re-exported, not merely imported (0050). Both moved to `core.turn_span` so
# p. 90's Slow could share the vocabulary without importing a module about rolls.
from srd_rules_engine.core.turn_span import TurnBoundary as TurnBoundary
from srd_rules_engine.core.turn_span import is_live as is_live

#: p. 90's Vex, as a rule id. A literal repeated at both ends is a literal that drifts.
VEX_RULE_ID: Final = "mastery-vex"

#: p. 90's Sap.
SAP_RULE_ID: Final = "mastery-sap"


@dataclass(frozen=True)
class PendingAdvantage:
    """Advantage or Disadvantage granted by one roll and spent by another (0049).

    **Spent, not merely expired.** p. 90 says "your **next** attack roll", so the first roll
    in scope consumes it whether it hits or misses. A token that only expired would grant
    Advantage on every attack in the window, which is a different and much larger rule.
    """

    #: Who rolls with it. Vex grants to the attacker; Sap to the creature that was hit.
    holder_id: str
    state: Advantage
    #: Which rule granted it, and therefore which sentence explains it in a ruling.
    rule_id: str
    #: Vex: "against **that creature**", so only attacks on this id are in scope. Sap names
    #: no target — "its next attack roll" — so `None` means any attack the holder makes.
    against_id: str | None
    #: Whose turn bounds it, in which round, and at which end of that turn.
    expires_after_actor_id: str
    expires_in_round: int
    expires_at: TurnBoundary

    def __post_init__(self) -> None:
        if self.state is Advantage.NONE:
            raise ValueError(
                "a pending roll state is Advantage or Disadvantage; NONE is the absence of "
                "one and a row recording it would be a token that changes no roll"
            )
        if not self.holder_id or not self.expires_after_actor_id:
            raise ValueError("a pending roll state names its holder and the turn that ends it")
        if self.expires_in_round < 0:
            raise ValueError("rounds are counted forward, so an expiry round is not negative")

    def applies_to(self, attacker_id: str, target_id: str) -> bool:
        """Whether this token is in scope for that attack.

        Scope is the holder plus, for Vex, the creature named. Liveness is a separate
        question and `is_live` answers it — an out-of-scope token is not spent, while a dead
        one is not honoured, and conflating them would let Vex be consumed by an attack on
        somebody else.
        """
        if attacker_id != self.holder_id:
            return False
        return self.against_id is None or self.against_id == target_id
