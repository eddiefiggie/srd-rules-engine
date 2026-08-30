"""Getting up off the ground (p. 186, 0057).

> **Restricted Movement.** Your only movement options are to crawl or to spend an amount of
> movement equal to **half your Speed (round down)** to right yourself and thereby end the
> condition. If your Speed is 0, you can't right yourself.

One sentence, two mechanics, and they are not the same kind of thing. The crawl restriction is
a **refusal** and lives where a move is made — `EncounterState.with_movement`, beside the four
refusals already there (0056). Righting yourself is a **capability**: it ends a condition, so R1
puts it behind the one adjudication entry point.

## Why both shipped together

Building the restriction alone would leave a Prone creature able to crawl and unable to stand,
held in a state p. 186 gives it an exit from. That is
[0052](../../../docs/decisions/0052-the-exit-is-built-before-the-entrance.md)'s ordering rule:
an engine that cannot start something declines a rule, and one that cannot end something ends
the session.

## It spends movement and covers no ground

Which is why `EffectKind.MOVEMENT_SPENT` exists. It is the mirror of `MOVED_BY_FORCE`, added one
build earlier: that one moves a creature and spends nothing, this one spends and moves nobody.
Between them they are the reason neither is a *movement* — `with_movement` couples the two, and
p. 186 and p. 190 each need one half without the other.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import (
    Declaration,
    Proposal,
    Resolver,
    condition_ended,
    movement_spent,
)
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import STAND, can_stand, righting_cost
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.state import EncounterState

STAND_RULE_ID: Final = STAND

#: R31. Both clauses are asserted in `scripts/verify_d20_rules.py` against p. 186.
STANDING_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference="SRD v5.2.1, Rules Glossary: Prone p. 186; Crawling p. 179",
    date="2026-08-30",
    method=VerificationMethod.ASSERTED,
)


def stand_rule() -> Rule:
    return Rule(
        id=STAND_RULE_ID,
        summary=(
            "A Prone creature spends half its Speed, rounded down, to right itself and end "
            "the condition. A creature whose Speed is 0 cannot."
        ),
        provenance=RuleProvenance.SRD,
        verification=STANDING_VERIFICATION,
    )


def stand_resolver() -> Resolver:
    """p. 186's righting, as a testless proposal (0027 clause 6).

    p. 186 states what it costs and what it does and asks nothing of the dice, so inventing a
    check to reach the outcome would invent a roll the rules do not call for.

    **The cost is charged and the condition ends in one ruling**, both in `outcome`, because
    the two are one sentence. There is no branch in which a creature pays and stays down.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        if Condition.PRONE not in actor.conditions.held:
            raise ValueError(
                f"{actor.name} is not Prone, so p. 186 has nothing to right. Standing up ends "
                "a condition the creature has to be holding"
            )
        if actor.effective_speeds.walk == 0:
            raise ValueError(
                f"{actor.name} has a Speed of 0, and p. 186 says so in its own sentence: "
                '"If your Speed is 0, you can\'t right yourself"'
            )
        cost = righting_cost(actor)
        if not can_stand(actor):
            raise ValueError(
                f"{actor.name} has less than the {cost} feet p. 186 charges to right itself. "
                "A creature cannot spend movement it does not have"
            )

        return Proposal(
            outcome=(
                movement_spent(
                    actor.id,
                    cost,
                    description=(
                        f"half of {actor.name}'s Speed of {actor.effective_speeds.walk}, "
                        f"rounded down: {cost} feet to right itself (p. 186)"
                    ),
                ),
                condition_ended(
                    actor.id,
                    Condition.PRONE,
                    description=f"{actor.name} got to its feet (p. 186)",
                ),
            ),
            citations=("srd:rules-glossary/prone",),
            may_claim=(
                f"that {actor.name} pushed itself upright",
                "that getting up took effort, which is what the movement paid for",
            ),
            may_not_claim=(
                "that standing cost an action; p. 186 charges movement and nothing else",
                "that the creature moved anywhere — it is where it fell",
            ),
        )

    return resolve


def prone_resolvers() -> dict[str, Resolver]:
    return {STAND_RULE_ID: stand_resolver()}
