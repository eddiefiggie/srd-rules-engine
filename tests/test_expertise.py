"""p. 182's Expertise: the Proficiency Bonus doubled, and only where the document allows it.

> Expertise is a feature that enhances your use of a skill proficiency. When you make an
> ability check with a skill proficiency in which you have Expertise, your **Proficiency
> Bonus is doubled** for that check unless the bonus is doubled by another feature. If you
> gain Expertise, you gain it in **one skill in which you have proficiency**. You **can't**
> have Expertise in the same skill proficiency **more than once**.

Four sentences, and three of them constrain rather than compute. `check_bonus` has six
consumers — Search, Study, Influence, Perception, the grapple escape and the read surface —
so this lands everywhere a skill check is made rather than in one rule.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.skills import Skill
from srd_rules_engine.core.state import Combatant

#: Wisdom 14 (+2), Dexterity 10 (+0), so the ability modifier and the bonus are never the
#: same number — an implementation that returned the wrong one would otherwise pass.
ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 14, "cha": 10}


def _creature(
    skills: frozenset[Skill] = frozenset(),
    expertise: frozenset[Skill] = frozenset(),
    *,
    proficiency: int = 3,
) -> Combatant:
    return Combatant(
        id="pc",
        name="Wren",
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=proficiency,
        is_player_character=True,
        skills=skills,
        expertise=expertise,
    )


# --- What it doubles ----------------------------------------------------------------------


def test_the_proficiency_bonus_doubles_and_the_ability_modifier_does_not() -> None:
    """p. 182 doubles "your Proficiency Bonus", not the check. Doubling the total is the
    arithmetic an implementation reaches for by scaling whatever it has added up so far, and
    it is wrong by the ability modifier every time."""
    plain = _creature()
    proficient = _creature(frozenset({Skill.PERCEPTION}))
    expert = _creature(frozenset({Skill.PERCEPTION}), frozenset({Skill.PERCEPTION}))

    assert plain.check_bonus(Skill.PERCEPTION) == 2, "Wisdom +2 alone"
    assert proficient.check_bonus(Skill.PERCEPTION) == 5, "+2 and a Proficiency Bonus of 3"
    assert expert.check_bonus(Skill.PERCEPTION) == 8, "+2 and 3 doubled — not 10"


def test_it_reaches_only_the_skill_it_is_held_in() -> None:
    """Expertise is per skill, so a creature expert in one and merely proficient in another
    gets two different bonuses from one call."""
    creature = _creature(
        frozenset({Skill.PERCEPTION, Skill.SURVIVAL}), frozenset({Skill.PERCEPTION})
    )

    assert creature.check_bonus(Skill.PERCEPTION) == 8
    assert creature.check_bonus(Skill.SURVIVAL) == 5, "proficient, and no more"


def test_a_negative_proficiency_bonus_is_not_a_case_the_document_has() -> None:
    """Doubling is multiplication, so it is worth pinning that it scales rather than adds a
    constant: a Proficiency Bonus of 2 gives 4, not 3 + 1 or a flat +2 somewhere."""
    expert = _creature(frozenset({Skill.PERCEPTION}), frozenset({Skill.PERCEPTION}), proficiency=2)
    assert expert.check_bonus(Skill.PERCEPTION) == 6, "Wisdom +2 and 2 doubled"


# --- The three sentences that constrain ---------------------------------------------------


def test_expertise_without_proficiency_is_refused() -> None:
    """p. 182: "you gain it in one skill **in which you have proficiency**."

    Refused rather than ignored. `check_bonus` would otherwise return the bare ability
    modifier for such a skill, which reads as "no Expertise" and hides a creature the
    document cannot describe."""
    with pytest.raises(ValueError, match="without proficiency"):
        _creature(expertise=frozenset({Skill.ARCANA}))

    with pytest.raises(ValueError, match="without proficiency"):
        _creature(frozenset({Skill.PERCEPTION}), frozenset({Skill.PERCEPTION, Skill.ARCANA}))


def test_it_cannot_be_held_twice() -> None:
    """p. 182: "You can't have Expertise in the same skill proficiency more than once."

    The shape of the field is the rule — a set cannot hold a member twice, so stacking is not
    expressible rather than being refused at a check. A count would make it expressible and
    then need a guard nobody would think to write."""
    expert = _creature(frozenset({Skill.PERCEPTION}), frozenset({Skill.PERCEPTION}))

    assert expert.expertise == frozenset({Skill.PERCEPTION})
    assert isinstance(expert.expertise, frozenset)


def test_a_creature_with_no_expertise_is_unchanged() -> None:
    """The default is a creature that has none, and every existing caller constructs one —
    so the bonus this returns has to be exactly what it returned before p. 182 arrived."""
    proficient = _creature(frozenset({Skill.PERCEPTION}))

    assert proficient.expertise == frozenset()
    assert proficient.check_bonus(Skill.PERCEPTION) == 5
