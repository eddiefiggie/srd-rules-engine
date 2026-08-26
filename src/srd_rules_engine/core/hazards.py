"""Hazards: the effects the world has on a creature without anyone attacking it.

Two of the five are here.

**Falling** fires on no occasion at all — it resolves when the creature lands — which is why
it was the first that could be built (0027 clause 7, applying
[0023](../../../docs/decisions/0023-the-turns-end-is-a-loop-owned-phase.md) clause 5
unchanged: an event resolves where the event happens, not in a catch-all).

**Burning** fires at the start of each of the creature's turns (p. 178), which is a phase this
engine has held since 0027 clauses 1-4 — the same one the death save fires in.

The other three are not blocked on an occasion any more. Suffocation has one (the turn's end,
built by 0023); Dehydration and Malnutrition fire at a day's end on the campaign axis. Nor are
they blocked on *gaining* an Exhaustion level any more —
[#178](https://github.com/eddiefiggie/srd-rules-engine/issues/178) built
`EffectKind.EXHAUSTION_GAINED` and `EncounterState.with_exhaustion`.

What blocks them now is **removal**, and it is a design question rather than a missing part.
Four rules remove Exhaustion levels and no two agree: a Long Rest removes one (p. 181),
breathing again removes every level *suffocation* caused (p. 189), and dehydration's and
malnutrition's levels are removable by nothing until the creature drinks or eats (pp. 181,
185). Two of those are about a level's **provenance**, and one integer cannot say which of a
creature's levels are which — [#180](https://github.com/eddiefiggie/srd-rules-engine/issues/180).

Suffocation is the one this bites hardest: its removal rule is half its glossary entry, so
building it with a suffocation-shaped counter would answer #180 in code rather than in a
record. Burning needed none of this, because it deals Fire *damage*.

## Falling asks nothing of the d20

p. 182: "A creature that falls takes 1d6 Bludgeoning damage at the end of the fall for every
10 feet it fell, to a maximum of 20d6."

There is no test in that sentence, and until #170 that made it inexpressible: `Proposal.test`
was required and `adjudicate` rolled it unconditionally. Reaching an outcome by inventing a
test would have been inventing a roll the rules do not call for, so the proposal shape moved
instead (0027 clause 6). The dice are still the engine's — the resolver declares `20d6` at
most and never a number.

The distance is a closure parameter, the way `attack_resolver` closes over a weapon and
`save_ends_resolver` over a condition. How far a creature fell is a fact about the world the
caller holds, like which weapon it swung; what the fall *costs* is this engine's, and it is
not told.

## Prone, and the qualifier that is now checked in full

p. 182 continues: "When the creature lands, it has the Prone condition **unless it avoids
taking any damage from the fall**."

That qualifier is about the damage actually **taken**, and the damage is rolled after the
proposal is built. This resolver used to decide the branch anyway, which left three ways to
take no damage and covered two of them:

* **A fall shorter than 10 feet** deals zero dice. Decidable — and this module still refuses
  to adjudicate it at all rather than proposing an outcome that resolves nothing.
* **Immunity to Bludgeoning** zeroes any amount, whatever the dice say. Decidable from
  `Defences.is_immune_to`.
* **Resistance rounding a low roll to zero** was not. p. 17 halves and rounds down, so a
  resistant creature rolling a 1 on a single die takes 0 and by p. 182 must not be Prone —
  and the branch was fixed before the die was thrown, so it was Prone
  ([#173](https://github.com/eddiefiggie/srd-rules-engine/issues/173)).

**The branch moved instead of growing a third case.** Prone is now declared with
`When.DAMAGE_TAKEN` and the engine decides it in `_apply`, against the post-defences figure
([0032](../../../docs/decisions/0032-an-outcome-conditional-on-its-own-damage.md) clauses
1-3). All three ways to take no damage go down the same road, and the resolver no longer
branches on Immunity at all — the case it *could* not reach is the one that mattered, and
special-casing the two it could was what hid it.

Asking one step earlier would not have been enough. `_roll_declared` has the **rolled**
number, and the rolled number in that case is 1: p. 17's Resistance is the entire difference
between rolled and taken, which is why 0032 clause 2 names the moment rather than the
mechanism.

**Neither `may_claim` nor `may_not_claim` mentions Prone** (0032 clause 5). They are fixed
when the proposal is built, so a claim about a conditional effect there would assert a branch
this resolver cannot see — the same defect, moved from the effect to the record of it. The
standing bound "that the effects recorded here happened" covers the applied case, and
`_bounds` adds the refusal when the predicate failed.

## What is not modelled

**The liquid Reaction.** p. 182 lets a creature falling into water use its Reaction for a
DC 15 Strength (Athletics) or Dexterity (Acrobatics) check to halve the damage. Whether a
creature fell *into a liquid* is a narrative fact this engine cannot observe, and the
Reaction economy would have to offer the check before the fall resolved. Excluded and
disclosed (R32), not silently dropped — [#173](https://github.com/eddiefiggie/srd-rules-engine/issues/173).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.adjudicate import (
    DamageDice,
    Declaration,
    Effect,
    EffectKind,
    Proposal,
    Resolver,
    When,
    condition_applied,
)
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)

# Both re-exported: 0028 clause 1 makes a Suffocation level carry its rule id, so the ids
# key state and had to move where state can reach them. This is where callers look.
from srd_rules_engine.core.state import BURNING_RULE_ID as BURNING_RULE_ID
from srd_rules_engine.core.state import SUFFOCATION_RULE_ID as SUFFOCATION_RULE_ID
from srd_rules_engine.core.state import EncounterState

#: p. 182: "1d6 Bludgeoning damage ... for every 10 feet it fell".
FEET_PER_FALLING_DIE: Final = 10

#: p. 182: "to a maximum of 20d6". The cap is on the dice, not on the distance, so a
#: creature that falls 500 feet and one that falls 200 take the same dice.
MAX_FALLING_DICE: Final = 20

#: The die itself. Named rather than inlined so the sentence and the code read alike.
FALLING_DIE_SIDES: Final = 6

#: R31. Both sentences this module rests on are clauses in `scripts/verify_d20_rules.py`
#: (#140), including the Prone qualifier — which is the half of p. 182 easiest to drop.
FALLING_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary, Falling p. 182 — both the damage per 10 feet with its "
        "20d6 cap and the Prone that follows unless no damage was taken"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


def falling_dice(feet: int) -> int:
    """How many d6 a fall of this distance deals (p. 182).

    Integer division, so a 35-foot fall deals 3d6 and not 3.5 — the document counts whole
    10-foot increments and states no rule for a partial one.
    """
    if feet < 0:
        raise ValueError(f"a fall cannot be {feet} feet; distances are non-negative")
    return min(feet // FEET_PER_FALLING_DIE, MAX_FALLING_DICE)


def falling_resolver(feet: int) -> Resolver:
    """Build the resolver for a fall of a given distance.

    A closure over the distance, as `attack_resolver` is a closure over a weapon. The
    caller supplies how far; this decides what it costs, and the engine rolls it (R1, R4).
    """
    dice = falling_dice(feet)
    if dice == 0:
        raise ValueError(
            f"a fall of {feet} feet deals no dice — p. 182 counts whole 10-foot increments, "
            f"so nothing below {FEET_PER_FALLING_DIE} feet has an outcome to adjudicate. "
            "A ruling here would record that nothing happened, which is not the same as a "
            "rule deciding that nothing happens"
        )

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id

        damage = DamageDice(
            target_id=actor_id,
            count=dice,
            sides=FALLING_DIE_SIDES,
            source=f"falling {feet} feet",
            damage_type=DamageType.BLUDGEONING,
        )

        # p. 182's Prone is conditional on damage being *taken*, so it is declared
        # conditional and the engine decides it where the number exists (0032 clauses 1-3).
        # This resolver no longer branches on Immunity: `When.DAMAGE_TAKEN` covers all three
        # ways to take none, and the one it could not reach before is the one that mattered.
        prone = condition_applied(
            actor_id,
            Condition.PRONE,
            description=(
                f"landing after a {feet}-foot fall (p. 182). Prone follows the fall "
                "unless no damage was taken"
            ),
            when=When.DAMAGE_TAKEN,
        )

        return Proposal(
            outcome=(damage, prone),
            citations=("srd:rules-glossary/falling",),
            # 0032 clause 5. Neither list mentions Prone, and that is the fix rather than an
            # omission: these are fixed before the dice are thrown, so a claim about a
            # conditional effect here would assert a branch this resolver cannot see. The
            # standing bound "that the effects recorded here happened" covers it when it
            # applies, and `_bounds` adds the refusal when it does not.
            may_claim=(
                f"that the creature fell {feet} feet and landed",
                "that the landing dealt the damage recorded here, and no more",
            ),
            may_not_claim=(
                "that anything was rolled for, tested, resisted or avoided — a fall is not "
                "a test, and nothing about it can be passed",
                "that the creature broke, died, or was otherwise harmed beyond the damage "
                "recorded; those need their own declarations",
            ),
        )

    return resolve


#: p. 178: "A burning creature or object takes 1d4 Fire damage at the start of each of its
#: turns."
BURNING_DIE_SIDES: Final = 4

#: R31. The sentence is a clause in `scripts/verify_d20_rules.py` (#140), including the part
#: that says *start* — which is what put it in the same phase as the death save rather than
#: the one save-ends lives in.
BURNING_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary, Burning p. 178 — 1d4 Fire damage at the start of each "
        "of the creature's turns"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


def burning_rule() -> Rule:
    """The SRD rule the turn's start incurs for a burning creature (p. 178)."""
    return Rule(
        id=BURNING_RULE_ID,
        summary=("A burning creature takes 1d4 Fire damage at the start of each of its turns."),
        provenance=RuleProvenance.SRD,
        verification=BURNING_VERIFICATION,
    )


def burning_resolver() -> Resolver:
    """Build the resolver for Burning's damage at the start of a turn.

    No d20, like Falling — p. 178 asks nothing of the dice but the damage, and inventing a
    test to reach the outcome would invent a roll the rules do not call for (0027 clause 6).

    **What ends it is not here.** p. 178 puts the fire out when it is "doused, submerged, or
    suffocated", or by an action that gives the creature the Prone condition and rolls it on
    the ground. The first three are narrative facts this engine cannot observe; the fourth
    needs an action to spend and a ruling to apply Prone through. So a burning creature
    burns until a caller clears `Hazards.burning` directly — a disclosed gap rather than a
    silent one, and a consequential one: nothing here can stop it.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id
        actor = state.combatant(actor_id)
        if not actor.hazards.burning:
            raise ValueError(
                f"{actor.name} is not burning, so there is nothing for p. 178 to resolve. "
                "Burning is read off state and never declared"
            )

        return Proposal(
            outcome=(
                DamageDice(
                    target_id=actor_id,
                    count=1,
                    sides=BURNING_DIE_SIDES,
                    source="burning",
                    damage_type=DamageType.FIRE,
                ),
            ),
            citations=("srd:rules-glossary/burning",),
            may_claim=(
                "that the fire is still burning at the start of this turn",
                "that it dealt the damage recorded here, and no more",
            ),
            may_not_claim=(
                "that anything was rolled for, tested, resisted or avoided — Burning is not "
                "a test, and nothing about it can be passed",
                "that the fire went out; this engine cannot observe dousing, submersion or "
                "an action spent putting it out, and it has recorded none",
            ),
        )

    return resolve


#: p. 189: "a number of minutes equal to 1 plus its Constitution modifier (minimum of 30
#: seconds)". Held in **seconds** because the floor is not a whole minute and `core.clock`
#: counts minutes — 0020 says nothing at campaign scale is finer, and it is right about
#: campaign scale. A breath is not campaign scale.
BREATH_FLOOR_SECONDS: Final = 30
SECONDS_PER_MINUTE: Final = 60

#: R31. Every sentence of p. 189 is a clause in `scripts/verify_d20_rules.py` — the breath
#: duration (#178), the gain at the end of each turn, and the removal on breathing again.
SUFFOCATION_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary, Suffocation p. 189 — how long a creature holds its "
        "breath, the Exhaustion level gained at the end of each of its turns, and the "
        "removal of every level suffocation caused once it can breathe again"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


def breath_seconds(constitution_modifier: int) -> int:
    """How long a creature can hold its breath before suffocation begins (p. 189).

    "A number of minutes equal to 1 plus its Constitution modifier (minimum of 30 seconds)".

    Returned in seconds rather than minutes because the floor is half a minute, and there is
    no honest integer-minutes answer for a creature whose Constitution modifier is -1 or
    worse. Rounding it to 0 would say suffocation begins at once; rounding to 1 would give
    it twice the breath the document allows.
    """
    return max(BREATH_FLOOR_SECONDS, (1 + constitution_modifier) * SECONDS_PER_MINUTE)


def suffocation_rule() -> Rule:
    """The SRD rule the turn's end incurs for a suffocating creature (p. 189)."""
    return Rule(
        id=SUFFOCATION_RULE_ID,
        summary=(
            "A creature that has run out of breath or is choking gains 1 Exhaustion level "
            "at the end of each of its turns."
        ),
        provenance=RuleProvenance.SRD,
        verification=SUFFOCATION_VERIFICATION,
    )


def suffocation_resolver() -> Resolver:
    """Build the resolver for Suffocation's Exhaustion at the end of a turn.

    No d20 (0027 clause 6): p. 189 states the level outright and asks nothing of the dice.
    The level carries this rule's id, which is what makes the removal below expressible.

    **Recovery is not here**, and it is not missing either — p. 189 removes the levels "when
    a creature can breathe again", which is a narrative fact rather than an occasion. It
    resolves where the state change happens, which is 0023 clause 5 applied the way 0027
    clause 7 applied it to Falling: `EncounterState.with_breath_regained`.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id
        actor = state.combatant(actor_id)
        if not actor.hazards.suffocating:
            raise ValueError(
                f"{actor.name} is not suffocating, so there is nothing for p. 189 to "
                "resolve. Suffocation is read off state and never declared"
            )

        return Proposal(
            outcome=(
                Effect(
                    kind=EffectKind.EXHAUSTION_GAINED,
                    target_id=actor_id,
                    amount=1,
                    description=(
                        "out of breath at the end of its turn: 1 Exhaustion level (p. 189)"
                    ),
                ),
            ),
            citations=("srd:rules-glossary/suffocation",),
            may_claim=(
                "that the creature is still without breath at the end of this turn",
                "that it is one Exhaustion level worse for it",
            ),
            may_not_claim=(
                "that anything was rolled for, tested, resisted or avoided — running out "
                "of breath is not a test, and nothing about it can be passed",
                "that the creature caught its breath; this engine cannot observe air and "
                "has recorded none",
                "that it died, unless the ruling recorded the sixth level",
            ),
        )

    return resolve


#: p. 185: landing a Long Jump in Difficult Terrain is a DC 10 Dexterity (Acrobatics) check.
LANDING_DC: Final = 10

#: The rule id a landing is adjudicated under.
LANDING_RULE_ID: Final = "long-jump-landing"

#: R31. p. 185's sentence, asserted with the rest of the Long Jump entry.
LANDING_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary, Long Jump pp. 184-185 — the DC 10 Dexterity "
        "(Acrobatics) check on landing in Difficult Terrain, and the Prone that follows a "
        "failure"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


def landing_rule() -> Rule:
    """The SRD rule for landing a Long Jump in Difficult Terrain (p. 185)."""
    return Rule(
        id=LANDING_RULE_ID,
        summary=(
            "A creature landing a Long Jump in Difficult Terrain makes a DC 10 Dexterity "
            "(Acrobatics) check or has the Prone condition."
        ),
        provenance=RuleProvenance.SRD,
        verification=LANDING_VERIFICATION,
    )


def landing_resolver() -> Resolver:
    """Build the resolver for a Long Jump's landing (p. 185).

    "If you land in Difficult Terrain, you must succeed on a DC 10 Dexterity (Acrobatics)
    check or have the Prone condition."

    **Only in Difficult Terrain**, which is a fact about where the creature landed and so
    the caller's to state — `core.position` models Difficult Terrain as a cost, not as a map,
    and this engine holds no terrain grid to look it up in. Adjudicating a landing on ordinary
    ground would invent a check the document does not call for.

    Unlike Falling, this one *is* a test: p. 185 states a DC, so the d20 resolves it and the
    Prone follows a failure rather than a distance.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor_id = declaration.actor_id
        actor = state.combatant(actor_id)

        return Proposal(
            test=D20Test(
                kind=TestKind.CHECK,
                target=LANDING_DC,
                target_basis=(
                    "DC 10 Dexterity (Acrobatics) to land a Long Jump in Difficult Terrain (p. 185)"
                ),
                modifiers=(Modifier(source="ability:dex", value=actor.modifier("dex")),),
            ),
            on_failure=(
                condition_applied(
                    actor_id,
                    Condition.PRONE,
                    description="a stumbled landing in Difficult Terrain (p. 185)",
                ),
            ),
            citations=("srd:rules-glossary/long-jump",),
            may_claim=(
                "that the creature landed where it jumped to",
                "that it kept its feet, or did not, as the roll says",
            ),
            may_not_claim=(
                "that the jump fell short; the distance is not what this check decides",
                "any injury from the landing — p. 185 gives Prone and no damage",
            ),
        )

    return resolve
