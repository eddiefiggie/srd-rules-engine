"""The action economy: what a creature may spend on its turn, and when it refreshes (R12).

Read off the Rules Glossary — Action p. 176, Bonus Action p. 177, Reaction p. 186, Dash
p. 180, Disengage p. 181, Dodge p. 181, Opportunity Attacks p. 185.

## Three budgets, and only two of them refresh together

* **Action.** "On your turn, you can take one action" (p. 176).
* **Bonus Action.** One per turn, "and you have a Bonus Action to take only if a rule
  explicitly says so" (p. 177) — so having one is a permission, not a default. `granted`
  models that: a creature with no feature granting one cannot take one at all, which is a
  different state from having spent it.
* **Reaction.** One, and it refreshes at **the start of your next turn** rather than at the
  end of the round (p. 186). Those differ whenever a creature acts late in one round and
  early in the next: an end-of-round refresh would hand it two Reactions in quick
  succession, which is the version usually played by mistake.

A Reaction is also free of the other two: "if you take it on your turn, you can do so even
if you also take an action, a Bonus Action, or both."

## Durations differ, and each one is a different word in the document

* **Disengage** lasts "for the rest of the current turn" (p. 181) — it ends when the turn
  ends.
* **Dodge** lasts "until the start of your next turn" (p. 181) — it survives everyone
  else's turn, which is the whole point of taking it.

Both are cleared by `refreshed()`, but for different reasons, and a single "clear at end of
turn" would silently remove Dodge before the attacks it exists to blunt.

## What is deliberately absent

**Opportunity Attacks are not fired here.** The Reaction budget they spend is modelled, and
`disengaged` records the flag that suppresses them, but nothing detects a creature leaving
another's reach. That detection is movement-triggered and belongs with the turn loop —
decision [0015](../../../docs/decisions/0015-reactions-and-the-agent-seam.md) records that
the seam already supports it and what remains.

**Dodge's "if you can see the attacker" qualifier** needs sight, which needs
[#91](https://github.com/eddiefiggie/srd-rules-engine/issues/91)'s obstructions. The base
effect applies and the qualifier is named in `unenforced_clauses`, the same treatment
`core.conditions` gives Frightened's line-of-sight clause.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum
from typing import Final

from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

#: R31.
ACTION_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary: Action p. 176, Bonus Action p. 177, Dash p. 180, "
        "Disengage p. 181, Dodge p. 181, Opportunity Attacks p. 185, Reaction p. 186"
    ),
    date="2026-08-23",
    method=VerificationMethod.ASSERTED,
)


class ActionKind(StrEnum):
    """What a creature can spend. Movement is not one of these — it is feet."""

    ACTION = "action"
    BONUS_ACTION = "bonus-action"
    REACTION = "reaction"


class ActionUnavailable(Exception):
    """A spend the economy does not permit. Raised rather than silently ignored."""


@dataclass(frozen=True)
class ActionBudget:
    """What is left of a creature's action economy, and what its actions have set.

    Spent flags rather than counters: the document allows exactly one of each, so a count
    could represent two Actions and a boolean cannot. The same move `has_advantage` makes
    for the d20 and `Defences` makes for Resistance.
    """

    action_spent: bool = False
    bonus_action_spent: bool = False
    reaction_spent: bool = False
    #: p. 177: a Bonus Action exists only if a rule grants one.
    bonus_action_granted: bool = False
    #: p. 180, Dash: extra movement for the current turn, in feet.
    extra_movement: int = 0
    #: p. 181, Disengage: movement does not provoke, for the rest of this turn.
    disengaged: bool = False
    #: p. 181, Dodge: until the start of this creature's next turn.
    dodging: bool = False

    def available(self, kind: ActionKind, conditions: Conditions | None = None) -> bool:
        """Whether this kind may be spent right now.

        Incapacitated removes all three: "You can't take any action, Bonus Action, or
        Reaction" (p. 184). It is asked here rather than at the call site so that a caller
        cannot spend one by forgetting to check.
        """
        if conditions is not None and conditions.cannot_act():
            return False
        if kind is ActionKind.ACTION:
            return not self.action_spent
        if kind is ActionKind.BONUS_ACTION:
            return self.bonus_action_granted and not self.bonus_action_spent
        return not self.reaction_spent

    def spend(self, kind: ActionKind, conditions: Conditions | None = None) -> ActionBudget:
        """Spend one, or refuse. A Reaction is free of the other two (p. 186)."""
        if not self.available(kind, conditions):
            raise ActionUnavailable(
                f"no {kind.value} is available: it is spent, ungranted, or the creature "
                "has the Incapacitated condition"
            )
        field = {
            ActionKind.ACTION: "action_spent",
            ActionKind.BONUS_ACTION: "bonus_action_spent",
            ActionKind.REACTION: "reaction_spent",
        }[kind]
        return replace(self, **{field: True})

    def refreshed(self) -> ActionBudget:
        """What this creature has at the start of its next turn.

        Everything resets here, and the two durations that end are ending for different
        reasons: Disengage expired with the turn it was taken on, and Dodge lasts "until
        the start of your next turn" — which is now.

        `bonus_action_granted` survives, because it is a property of the creature's
        features rather than something a turn spends.
        """
        return ActionBudget(bonus_action_granted=self.bonus_action_granted)

    def dashed(self, speed: int) -> ActionBudget:
        """p. 180: "The increase equals your Speed after applying any modifiers."

        Speed *after modifiers*, so a creature slowed by Exhaustion Dashes the shorter
        distance — the caller passes the speed conditions have already acted on.
        """
        return replace(self, extra_movement=self.extra_movement + speed)

    def attack_rolls_against(self) -> Advantage:
        """p. 181: while Dodging, "any attack roll made against you has Disadvantage"."""
        return Advantage.DISADVANTAGE if self.dodging else Advantage.NONE

    def dexterity_saves(self) -> Advantage:
        """p. 181: "you make Dexterity saving throws with Advantage"."""
        return Advantage.ADVANTAGE if self.dodging else Advantage.NONE

    def unenforced_clauses(self) -> tuple[str, ...]:
        return ("dodge-requires-seeing-the-attacker",) if self.dodging else ()


def dodging(budget: ActionBudget, conditions: Conditions, speed: int) -> ActionBudget:
    """Take the Dodge action, and lose it immediately if it cannot be held.

    p. 181: "You lose these benefits if you have the Incapacitated condition or if your
    Speed is 0." Both are checked when it is taken *and* whenever it is read, because a
    creature can be grappled after Dodging — so this returns a budget whose `dodging` flag
    is already false in that case rather than one that lies until someone re-checks.

    **It does not spend the Action, and did until #252.** Every action this engine charges
    is charged in one place now — an `EffectKind.ACTION_SPENT` in the ruling's `always`
    branch — so a Dodge that also spent here would be billed twice, and `ActionBudget.spend`
    would raise on the second. Deciding whether the benefit holds is this function's job;
    charging for it is the economy's.
    """
    holds = not conditions.cannot_act() and speed > 0
    return replace(budget, dodging=holds)


def still_dodging(budget: ActionBudget, conditions: Conditions, speed: int) -> bool:
    """Whether a Dodge taken earlier still stands (p. 181)."""
    if not budget.dodging:
        return False
    return not conditions.has(Condition.INCAPACITATED) and speed > 0
