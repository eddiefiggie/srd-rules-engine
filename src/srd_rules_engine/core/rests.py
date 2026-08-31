"""p. 187's Short Rest: the occasion that spends a Hit Point Die, and the roll it makes.

The Short Rest's *only* mechanical benefit is the spend. p. 187 states two others — a
Special Feature recharge, and what an interruption costs — and neither has an antecedent
here: no feature in this engine has a recharge, and no rest can be interrupted because
nothing advances an hour of downtime.

## Why the spend is a Ruling and not bookkeeping

p. 187: "roll the die and add your Constitution modifier to it. You regain Hit Points equal
to the total (minimum of 1 Hit Point)."

A die is thrown and hit points change, which is an outcome. So it goes through the one
adjudication entry point like every other result (R1), and the engine rolls it (R4) — the
resolver states `1d8 + 2` as `HealingDice` and never a total. 0080 drew the same line for
the two campaign-day hazards: Dehydration inflicts a level outright and is bookkeeping,
Malnutrition compels a save and is an outcome.

## Two effects, not one

The Ruling carries the healing **and** the spend, as siblings. Folding the decrement into
the healing would put a resource change somewhere the ledger cannot see it separately, and
the two are genuinely different facts: a die is gone whatever the roll came to.

## The Constitution modifier is the rester's, read at the roll

p. 187 says "your Constitution modifier" and nothing else, so it is read off the creature
when the die is spent rather than captured when the rest began. A rest is not an instant,
and a modifier that changed mid-rest is the document's problem rather than a snapshot this
module should take on its own authority.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import (
    Declaration,
    Effect,
    EffectKind,
    HealingDice,
    Proposal,
    Resolver,
)
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.state import EncounterState

#: p. 187. The rule id a Hit Point Die spend is adjudicated under.
HIT_DIE_RULE_ID: Final = "srd:rules-glossary/short-rest/spend-hit-point-dice"

#: p. 187: "You regain Hit Points equal to the total (minimum of 1 Hit Point)."
#:
#: A rule rather than a guard. A creature with a negative Constitution modifier can total
#: less than one on a small die, and the document says what happens then — so the floor is
#: cited, not invented.
HIT_DIE_MINIMUM_HP: Final = 1

#: One die per spend. p. 187 lets a creature spend "one or more", and this is the size of
#: each individual spend, because the decision to take another comes **after each roll**.
DICE_PER_SPEND: Final = 1

SHORT_REST_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Rules Glossary -> Short Rest ("Spend Hit Point Dice. You can spend one '
        "or more of your Hit Point Dice to regain Hit Points. For each Hit Point Die you "
        "spend in this way, roll the die and add your Constitution modifier to it. You "
        "regain Hit Points equal to the total (minimum of 1 Hit Point). You can decide to "
        'spend an additional Hit Point Die after each roll"), p. 187'
    ),
    date="2026-08-31",
    method=VerificationMethod.ASSERTED,
)


def hit_die_rule() -> Rule:
    """The SRD rule a Hit Point Die spend resolves under (p. 187)."""
    return Rule(
        id=HIT_DIE_RULE_ID,
        summary=(
            "A creature on a Short Rest can spend a Hit Point Die to regain Hit Points: roll "
            "the die, add the creature's Constitution modifier, and regain that total, to a "
            "minimum of 1 Hit Point. The creature decides whether to spend another after "
            "each roll."
        ),
        provenance=RuleProvenance.SRD,
        verification=SHORT_REST_VERIFICATION,
    )


def hit_die_resolver() -> Resolver:
    """Build the resolver for one Hit Point Die spent on a Short Rest (p. 187).

    **Testless** (0027 clause 6). There is no D20 Test here: p. 187 rolls the Hit Point Die
    itself, and nothing is being tested against a target number. `Proposal.outcome` is the
    branch a testless proposal resolves to, and `adjudicate` skips the d20 while still
    drawing a seed and rolling the declared dice — which is precisely what this needs.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id
        actor = state.combatant(actor_id)

        if actor.hit_dice is None:
            raise ValueError(
                f"{actor.name} has no Hit Point Dice recorded, so p. 187 has nothing to "
                "spend. `None` is unrecorded rather than zero (p. 183)"
            )
        if actor.hit_dice.remaining < DICE_PER_SPEND:
            raise ValueError(
                f"{actor.name} has no Hit Point Dice left to spend; "
                f"{actor.hit_dice.total} are held and all are spent"
            )

        constitution = actor.modifier("con")
        size = actor.hit_dice.size

        return Proposal(
            # p. 187 rolls the die and nothing tests against a target, so there is no test
            # (0027 clause 6). A save shape here would invent a DC the document never gives.
            outcome=(
                Effect(
                    kind=EffectKind.HIT_DIE_SPENT,
                    target_id=actor_id,
                    amount=DICE_PER_SPEND,
                    description=(
                        f"a Hit Point Die spent on a Short Rest (p. 187): "
                        f"{actor.hit_dice.remaining - DICE_PER_SPEND} of "
                        f"{actor.hit_dice.total} remain"
                    ),
                ),
                HealingDice(
                    target_id=actor_id,
                    count=DICE_PER_SPEND,
                    sides=size,
                    modifier=constitution,
                    source=f"Hit Point Die on a Short Rest (p. 187), d{size} + Constitution",
                    minimum=HIT_DIE_MINIMUM_HP,
                ),
            ),
            citations=("srd:rules-glossary/short-rest",),
            may_claim=(
                f"that {actor.name} spent a Hit Point Die and recovered by the amount rolled",
                f"that {actor.name} has one fewer Hit Point Die than before",
            ),
            may_not_claim=(
                f"that {actor.name} recovered any other amount than the ruling records",
                f"that {actor.name} is fully rested — p. 187 restores no dice and grants no "
                "other benefit this engine models",
                "that the rest completed; p. 187's hour is not tracked here",
            ),
        )

    return resolve
