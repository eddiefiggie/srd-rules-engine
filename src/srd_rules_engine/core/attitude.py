"""p. 184's Influence, and the three attitudes that move its check (#142).

**The first core fact type this engine ships.** The port has been built and thoroughly so
since #9, and every `FactType` in the repository was a *fixture* — so R22's `DefaultKind`,
which exists to say what a core type's absence means, had never been applied to a core type.
Attitude is the obvious first one and README has named it as the example since the beginning:
"narrative facts carrying mechanical weight (**attitude**, knowledge, inspiration) arrive
through a typed port".

It is the right first one because the engine cannot derive it. Whether a creature views you
favourably is not computable from anything `EncounterState` holds — it is a narrative fact
carrying mechanical weight, which is the exact boundary R20 draws.

## Four design questions, and the document dissolved all four

#142 raised them and said question 4 was the one that could grow the work well beyond three
shapes. Reading pp. 182-184 answered every one:

1. **A `ValueKind` for a closed three-value set.** `ValueKind.CHOICE` already existed, with a
   `choices` tuple. Nothing to invent.
2. **What the absent-value default is.** p. 184 states it outright — *"Indifferent is the
   default attitude of a monster"* — so it is `SRD_PRESCRIBED` rather than the
   `ENGINE_CHOSEN` guess it would have been. #142 said this had to be checked against the
   document and not assumed, which is the same position #124 and #130 were in.
3. **Who may write it.** `OUT_OF_BAND` only, which follows from 4.
4. **Whether a ruling changes it.** **It does not.** p. 184's Influence ends: *"On a
   successful check, the monster does as urged. On a failed check, you must wait 24 hours
   (or a duration set by the GM) before urging it in the same way again."* The monster
   complies; its attitude is untouched. So no `EffectKind` writes a fact, and #119's shape
   is not needed one layer along.

## What the engine decides, and what it does not

p. 184 gives the GM three determinations — willing, unwilling, hesitant — and only the third
reaches a die. That is the contract exactly: the agent decides *that* a rule applies and
*which*; the engine decides how it turns out. A willing monster's compliance and an unwilling
one's refusal are outcomes with no roll (0027 clause 6), and the engine records them rather
than letting them be narrated into existence.

The **DC is stated**, which is unusual for this document and worth saying plainly: "a default
DC equal to 15 or the monster's Intelligence score, whichever is higher". Not a modifier — the
**score**. So `search_resolver`'s caller-supplied difficulty is not needed here.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.adjudicate import (
    Declaration,
    Effect,
    EffectKind,
    Proposal,
    Resolver,
)
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.memory_port import (
    DefaultKind,
    FactType,
    Resolution,
    ValueKind,
    Writer,
)
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.skills import SKILL_ABILITY, Skill
from srd_rules_engine.core.state import EncounterState

INFLUENCE_RULE_ID: Final = "srd:rules-glossary/influence"

INFLUENCE_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary: Influence p. 184 (the willing/unwilling/hesitant "
        "determination, and \"a default DC equal to 15 or the monster's Intelligence score, "
        'whichever is higher"), Friendly p. 182, Hostile p. 183, Indifferent p. 184 '
        '("Indifferent is the default attitude of a monster")'
    ),
    date="2026-08-31",
    method=VerificationMethod.ASSERTED,
)

#: The name the port stores an attitude under, and the name a resolver asks for.
ATTITUDE_FACT: Final = "attitude"


class Attitude(StrEnum):
    """The three attitudes, each its own glossary entry (pp. 182-184).

    Three shapes rather than one, because the document gives each an entry and each a
    different consequence — which is `closed-named-set` (0013, Q4) admitting them the way it
    admitted the eight weapon masteries.
    """

    #: p. 182: "A Friendly creature views you favorably. You have Advantage on an ability
    #: check to influence a Friendly creature."
    FRIENDLY = "friendly"
    #: p. 184: "An Indifferent creature has no desire to help or hinder you." It states no
    #: effect on the check, which is what makes it the neutral case rather than a third
    #: modifier.
    INDIFFERENT = "indifferent"
    #: p. 183: "A Hostile creature views you unfavorably. You have Disadvantage on an ability
    #: check to influence a Hostile creature."
    HOSTILE = "hostile"


#: p. 184: "a default DC equal to 15 or the monster's Intelligence score, whichever is
#: higher". The **score**, not the modifier — a distinction worth pinning, because every
#: other DC-adjacent number in this engine is a modifier and reaching for one here would
#: silently lower the DC by about seven for an ordinary monster.
INFLUENCE_BASE_DC: Final = 15

#: R22, applied to a core type for the first time. `SRD_PRESCRIBED` because p. 184 states the
#: default rather than leaving it to be chosen: "Indifferent is the default attitude of a
#: monster."
#:
#: `OUT_OF_BAND` only. p. 184's Influence changes nothing about the attitude — a successful
#: check makes the monster comply, not like you — so no ruling writes this, and admitting
#: `Writer.RULING` would be a capability nothing in the document exercises.
ATTITUDE_TYPE: Final = FactType(
    name=ATTITUDE_FACT,
    kind=ValueKind.CHOICE,
    choices=tuple(a.value for a in Attitude),
    default_kind=DefaultKind.SRD_PRESCRIBED,
    default=Attitude.INDIFFERENT.value,
    writable_by=frozenset({Writer.OUT_OF_BAND}),
)

#: Every fact type the engine itself defines. One, and it took until #142 to have any.
CORE_FACT_TYPES: Final[Mapping[str, FactType]] = MappingProxyType(
    {ATTITUDE_TYPE.name: ATTITUDE_TYPE}
)

#: p. 184's Influence Checks table. **Suggests**, as p. 187's Search table does — "The
#: Influence Checks table suggests which ability check to make" and "The GM chooses the
#: check" — so this is held to offer from and never to refuse against.
INFLUENCE_SKILLS: Final[Mapping[Skill, str]] = MappingProxyType(
    {
        Skill.DECEPTION: "deceiving a monster that understands you",
        Skill.INTIMIDATION: "intimidating a monster",
        Skill.PERFORMANCE: "amusing a monster",
        Skill.PERSUASION: "persuading a monster that understands you",
        Skill.ANIMAL_HANDLING: "gently coaxing a Beast or Monstrosity",
    }
)


def influence_dc(intelligence_score: int) -> int:
    """p. 184: 15, or the monster's Intelligence **score**, whichever is higher.

    Not clamped and not averaged. A monster with an Intelligence of 20 sets DC 20; one with
    an Intelligence of 3 sets DC 15, because the floor is the higher of the two rather than
    the sum or the mean.
    """
    return max(INFLUENCE_BASE_DC, intelligence_score)


def attitude_of(facts: Mapping[str, Resolution]) -> tuple[Attitude, str]:
    """The subject's attitude and where it came from, or refuse.

    Returns the provenance alongside the value because R27 requires a ruling that consumed a
    fact to cite it — and because p. 184's default is a *rule* rather than a fallback, so a
    ruling resting on it should say the document supplied it rather than the agent.
    """
    resolved = facts[ATTITUDE_FACT]
    if resolved.blocked:
        raise ValueError(
            "no attitude is recorded for this creature and no default applies, so p. 184's "
            "check cannot be set up. This should be unreachable while `ATTITUDE_TYPE` "
            "carries p. 184's SRD-prescribed default"
        )
    value = Attitude(str(resolved.value))
    if resolved.defaulted is DefaultKind.SRD_PRESCRIBED:
        source = 'p. 184: "Indifferent is the default attitude of a monster"'
    elif resolved.provenance is not None:
        source = resolved.provenance.reference
    else:
        source = "recorded with no provenance"
    return value, source


class Reception(StrEnum):
    """p. 184's three determinations, which the GM makes and the engine does not.

    "The GM then determines whether the monster feels willing, unwilling, or hesitant due to
    your interaction; this determination establishes whether an ability check is necessary."

    So this is the agent's half, arriving as an argument. Deciding it here would need the
    engine to read what the player said, which is the capability this project removes.
    """

    #: "If your urging aligns with the monster's desires, no ability check is necessary; the
    #: monster fulfills your request in a way it prefers."
    WILLING = "willing"
    #: "If your urging is repugnant to the monster or counter to its alignment, no ability
    #: check is necessary; it doesn't comply."
    UNWILLING = "unwilling"
    #: "If you urge the monster to do something that it is hesitant to do, you must make an
    #: ability check, which is affected by the monster's attitude."
    HESITANT = "hesitant"


def influence_rule() -> Rule:
    """The SRD rule an Influence action resolves under (p. 184)."""
    return Rule(
        id=INFLUENCE_RULE_ID,
        summary=(
            "The Influence action urges a monster to do something. A willing monster complies "
            "and an unwilling one refuses, neither with a check. A hesitant one is urged with "
            "an ability check the GM chooses, at DC 15 or the monster's Intelligence score, "
            "whichever is higher, with Advantage if it is Friendly and Disadvantage if it is "
            "Hostile."
        ),
        provenance=RuleProvenance.SRD,
        verification=INFLUENCE_VERIFICATION,
    )


def influence_resolver(
    *, subject_id: str, reception: Reception, skill: Skill | None = None
) -> Resolver:
    """Build the resolver for one Influence action against one monster (p. 184).

    A closure over the subject and the GM's determination, as `perception_resolver` is a
    closure over a target and a difficulty. What the caller supplies is the half p. 184 gives
    the GM: who is being urged, and whether they are willing, unwilling or hesitant. What the
    engine supplies is everything after that — the DC, the attitude's effect on the roll, and
    the outcome.

    **Two of the three branches throw no die**, which is 0027 clause 6 rather than a special
    case: p. 184 says outright that no ability check is necessary for a willing or an
    unwilling monster, and the engine records the outcome so that compliance and refusal are
    *rulings* rather than things narrated into existence.

    **The skill is suggested, not required**, exactly as p. 187's Search table is: "The
    Influence Checks table suggests which ability check to make" and "The GM chooses the
    check". So a check with no skill is legal, and this refuses only a skill whose ability the
    check is not of — the same reading, disclosed the same way (#411).
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        subject = state.combatant(subject_id)

        if reception is Reception.WILLING:
            return Proposal(
                outcome=(
                    Effect(
                        kind=EffectKind.INFLUENCED,
                        target_id=subject_id,
                        amount=1,
                        description=(
                            f"{subject.name} was willing, so p. 184 asks for no check: it "
                            "fulfills the request in a way it prefers"
                        ),
                    ),
                ),
                citations=("srd:rules-glossary/influence",),
                may_claim=(
                    f"that {subject.name} does as urged, in a way it prefers",
                    "that no check was needed, because the urging aligned with its desires",
                ),
                may_not_claim=(
                    f"that {subject.name}'s attitude changed — p. 184 changes none",
                    "that it did more than was urged, or did it the way the urger wanted",
                ),
            )

        if reception is Reception.UNWILLING:
            return Proposal(
                outcome=(
                    Effect(
                        kind=EffectKind.INFLUENCED,
                        target_id=subject_id,
                        amount=0,
                        description=(
                            f"{subject.name} was unwilling, so p. 184 asks for no check: it "
                            "does not comply"
                        ),
                    ),
                ),
                citations=("srd:rules-glossary/influence",),
                may_claim=(f"that {subject.name} refuses",),
                may_not_claim=(
                    "that a check could have changed this; p. 184 asks for none",
                    f"that {subject.name}'s attitude changed — p. 184 changes none",
                ),
            )

        attitude, source = attitude_of(facts)
        if (
            skill is not None
            and SKILL_ABILITY[skill] != "cha"
            and skill is not Skill.ANIMAL_HANDLING
        ):
            raise ValueError(
                f"{skill.value} is a {SKILL_ABILITY[skill]} skill, and p. 184's table offers "
                "Charisma checks and one Wisdom (Animal Handling) check. A check with no "
                "skill at all is legal"
            )

        ability = SKILL_ABILITY[skill] if skill is not None else "cha"
        bonus = actor.check_bonus(skill) if skill is not None else actor.modifier(ability)
        dc = influence_dc(subject.abilities.get("int", 0))

        return Proposal(
            test=D20Test(
                kind=TestKind.CHECK,
                ability=ability,
                target=dc,
                target_basis=(
                    f"DC {dc} — p. 184's higher of 15 and the monster's Intelligence score "
                    f"({subject.abilities.get('int', 0)})"
                ),
                modifiers=(
                    Modifier(
                        source=f"skill:{skill.value}" if skill else f"ability:{ability}",
                        value=bonus,
                    ),
                ),
                # p. 182 and p. 183 state these as properties of the check itself.
                has_advantage=attitude is Attitude.FRIENDLY,
                has_disadvantage=attitude is Attitude.HOSTILE,
            ),
            on_success=(
                Effect(
                    kind=EffectKind.INFLUENCED,
                    target_id=subject_id,
                    amount=1,
                    description=f"the check succeeded, so {subject.name} does as urged (p. 184)",
                ),
            ),
            # p. 184 states a consequence for failure — "you must wait 24 hours (or a
            # duration set by the GM) before urging it in the same way again" — and nothing
            # here tracks it, so the branch carries no effect and the bounds say so (#418).
            on_failure=(),
            citations=("srd:rules-glossary/influence", f"srd:rules-glossary/{attitude.value}"),
            may_claim=(
                f"that {subject.name} was hesitant and the check came out as the roll says",
                f"what its attitude was worth: {attitude.value} (from {source})",
            ),
            may_not_claim=(
                f"that {subject.name}'s attitude changed — p. 184 changes none",
                "that the urger may try the same way again before 24 hours have passed; "
                "p. 184 forbids it and nothing here tracks the wait",
                f"that {subject.name} did anything beyond what was urged",
            ),
        )

    return resolve
