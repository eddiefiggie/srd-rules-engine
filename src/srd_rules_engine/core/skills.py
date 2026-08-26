"""The eighteen skills, and what proficiency in one adds (#138).

p. 188, *Skill*: "A skill is an area of specialization associated with an ability check. If
you have proficiency in a skill, you can add your Proficiency Bonus when you make an ability
check associated with that skill."

That is the whole entry, and this module is the whole of it: a closed set of names, the
ability each is associated with, and the rule that proficiency adds the bonus. What a skill
is *for* is example text — p. 9's table gives "notice something that's easy to miss" for
Perception — and example text is not a mechanic.

## Why the table is transcribed rather than the names alone

p. 9's Skills table pairs each skill with exactly one ability, and the pairing is the
mechanical half: a Wisdom (Perception) check is a Wisdom check, so the modifier comes from
Wisdom whoever is rolling it. A set of names without the abilities would leave every caller
to remember which ability a skill uses, which is the recalled-from-training failure this
engine exists to remove.

## Proficiency is NOT claimed by this module, and the reason is p. 186

"A creature might have proficiency in a skill or saving throw or with a weapon or tool."
Four kinds. This module builds the first; `Weapon.proficient` has built the third since #16.
Saving throws and tools are not modelled, so the `proficiency` shape stays unclaimed —
claiming it here would report two of four as four.

## Expertise is not here either

p. 182 doubles the Proficiency Bonus for a skill you have Expertise in. It is a class
feature rather than a property of the skill, and this engine ships no class data for the
same reason `core.spellcasting` ships no slot table.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)


class Skill(StrEnum):
    """The eighteen skills p. 9's table names. A closed set, like `DamageType`."""

    ACROBATICS = "acrobatics"
    ANIMAL_HANDLING = "animal-handling"
    ARCANA = "arcana"
    ATHLETICS = "athletics"
    DECEPTION = "deception"
    HISTORY = "history"
    INSIGHT = "insight"
    INTIMIDATION = "intimidation"
    INVESTIGATION = "investigation"
    MEDICINE = "medicine"
    NATURE = "nature"
    PERCEPTION = "perception"
    PERFORMANCE = "performance"
    PERSUASION = "persuasion"
    RELIGION = "religion"
    SLEIGHT_OF_HAND = "sleight-of-hand"
    STEALTH = "stealth"
    SURVIVAL = "survival"


#: The ability each skill is associated with (p. 9's Skills table), transcribed rather than
#: recalled. Six abilities, and Constitution appears for none of them — which is the
#: document's shape and not an omission here.
SKILL_ABILITY: Final[Mapping[Skill, str]] = MappingProxyType(
    {
        Skill.ACROBATICS: "dex",
        Skill.ANIMAL_HANDLING: "wis",
        Skill.ARCANA: "int",
        Skill.ATHLETICS: "str",
        Skill.DECEPTION: "cha",
        Skill.HISTORY: "int",
        Skill.INSIGHT: "wis",
        Skill.INTIMIDATION: "cha",
        Skill.INVESTIGATION: "int",
        Skill.MEDICINE: "wis",
        Skill.NATURE: "int",
        Skill.PERCEPTION: "wis",
        Skill.PERFORMANCE: "cha",
        Skill.PERSUASION: "cha",
        Skill.RELIGION: "int",
        Skill.SLEIGHT_OF_HAND: "dex",
        Skill.STEALTH: "dex",
        Skill.SURVIVAL: "wis",
    }
)

#: R31. Both sentences the module rests on are clauses in `scripts/verify_d20_rules.py`:
#: p. 188's proficiency rule, and p. 9's table pairing Perception with Wisdom.
SKILLS_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary, Skill p. 188 and Proficiency p. 186; the Skills table, p. 9"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


@dataclass(frozen=True)
class PerceptionCheck:
    """What a Wisdom (Perception) check to see one creature has, before it is rolled.

    Here rather than in `core.perception` because `EncounterState` returns one, and
    `core.perception` imports `EncounterState` to build its resolver — the type has to sit
    below both. `core.sight` splits the same way for the same reason: the values are pure
    and the relation that derives them needs the encounter.

    `automatic_failure` is not "Disadvantage, but worse". p. 177 settles the outcome without
    a die, so a proposal built from this carries an `outcome` rather than a `test`, and
    `because` carries the sentence so a refusal to roll explains itself.
    """

    advantage: Advantage
    because: str
    #: p. 177: the check fails and no d20 is thrown.
    automatic_failure: bool = False

    @property
    def is_rolled(self) -> bool:
        return not self.automatic_failure
