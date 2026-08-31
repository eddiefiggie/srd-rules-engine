"""p. 187's Search and p. 189's Study: one mechanism, two entries, and no DC anywhere.

Both entries are the same sentence twice — take the action, make a check of a named ability
to learn something — and both state **no difficulty**. That is `perception_resolver`'s
situation exactly, and its answer: the caller supplies the DC with its derivation, because
"a DC the document does not state must say where it came from" (R5). Setting a difficulty is
interpretation, which is the agent's half. Rolling against it is the outcome, which never is.

The skill is **optional**, because both entries say the table "suggests which skills are
applicable" rather than requiring one.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.adjudicate import Declaration, EffectKind, Intent
from srd_rules_engine.core.d20 import TestKind
from srd_rules_engine.core.skills import Skill
from srd_rules_engine.core.state import Combatant, EncounterState
from srd_rules_engine.core.turn_actions import (
    SEARCH_RULE_ID,
    SEARCH_SKILLS,
    STUDY_SKILLS,
    search_resolver,
    study_resolver,
)

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 16, "wis": 14, "cha": 10}


def _seeker(skills: frozenset[Skill] = frozenset()) -> Combatant:
    return Combatant(
        id="pc",
        name="Wren",
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=3,
        is_player_character=True,
        skills=skills,
    )


def _propose(  # type: ignore[no-untyped-def]
    resolver, actor: Combatant | None = None, *, rule_id: str = SEARCH_RULE_ID
):
    state = EncounterState.new([actor or _seeker()])
    return resolver(
        state=state,
        declaration=Declaration(
            actor_id="pc",
            intent=Intent(improvised=True, label="look"),
            rule_id=rule_id,
        ),
        facts={},
    )


# --- The ability each entry names -------------------------------------------------------


def test_search_is_a_wisdom_check_and_study_an_intelligence_one() -> None:
    """p. 187 says Wisdom and p. 189 says Intelligence. The two differ in exactly this and
    in their table, which is why they are one helper and two shapes."""
    search = _propose(search_resolver(dc=15, basis="the tracks are half washed out"))
    study = _propose(study_resolver(dc=15, basis="the cipher is an old one"))

    assert search.test is not None and search.test.ability == "wis"
    assert study.test is not None and study.test.ability == "int"
    assert search.test.kind is TestKind.CHECK, "an ability check, not a save"


def test_the_dc_is_the_callers_and_carries_its_derivation() -> None:
    """R5. Neither entry states a DC, so one that appeared from nowhere would be a rule value
    R31 forbids — and one with no stated basis would be unfalsifiable."""
    proposal = _propose(search_resolver(dc=17, basis="the hatch is well fitted"))

    assert proposal.test is not None
    assert proposal.test.target == 17
    assert proposal.test.target_basis == "the hatch is well fitted"
    assert any("came from" in claim for claim in proposal.may_not_claim), (
        "and the bounds say the difficulty was not the document's"
    )


# --- The skill is suggested, never required ---------------------------------------------


def test_a_check_with_no_skill_at_all_is_legal() -> None:
    """Both entries say the table "suggests which skills are applicable". Requiring one
    would turn a suggestion into a gate, which is the direction R31 names."""
    proposal = _propose(study_resolver(dc=12, basis="a half-remembered rite"))

    assert proposal.test is not None
    (modifier,) = proposal.test.modifiers
    assert modifier.source == "ability:int"
    assert modifier.value == 3, "the Intelligence modifier alone, with no Proficiency Bonus"


def test_a_suggested_skill_adds_its_proficiency_bonus() -> None:
    """p. 188: proficiency in a skill adds the bonus to a check associated with it."""
    proficient = _seeker(skills=frozenset({Skill.SURVIVAL}))
    proposal = _propose(
        search_resolver(dc=12, basis="a cold trail", skill=Skill.SURVIVAL), proficient
    )

    assert proposal.test is not None
    (modifier,) = proposal.test.modifiers
    assert modifier.source == "skill:survival"
    assert modifier.value == 5, "Wisdom +2 and a Proficiency Bonus of 3"


def test_a_skill_of_the_wrong_ability_is_refused() -> None:
    """A Proficiency Bonus in an Intelligence skill cannot reach a Wisdom check, and every
    skill the document suggests for each action is of that action's ability. Accepting one
    would silently add a bonus the rules never grant."""
    with pytest.raises(ValueError, match="cannot apply"):
        search_resolver(dc=12, basis="a cipher", skill=Skill.ARCANA)
    with pytest.raises(ValueError, match="cannot apply"):
        study_resolver(dc=12, basis="a scent", skill=Skill.SURVIVAL)


def test_a_skill_absent_from_the_table_is_still_accepted() -> None:
    """The refusal above is about the *ability*, not about membership of the table. p. 187
    suggests four skills and does not forbid a fifth, so Animal Handling — a Wisdom skill it
    never lists — is legal. Refusing it would make a suggestion into a closed set."""
    assert Skill.ANIMAL_HANDLING not in SEARCH_SKILLS
    proposal = _propose(
        search_resolver(dc=12, basis="the horse is uneasy", skill=Skill.ANIMAL_HANDLING)
    )

    assert proposal.test is not None
    assert proposal.test.modifiers[0].source == "skill:animal-handling"


# --- The tables, as the document prints them --------------------------------------------


def test_every_suggested_skill_is_of_its_actions_ability() -> None:
    """The reading the refusal rests on, asserted rather than assumed. p. 187's four are all
    Wisdom skills and p. 189's five are all Intelligence ones — if that were not so, the
    refusal would be contradicting the document's own table."""
    from srd_rules_engine.core.skills import SKILL_ABILITY

    assert {SKILL_ABILITY[skill] for skill in SEARCH_SKILLS} == {"wis"}
    assert {SKILL_ABILITY[skill] for skill in STUDY_SKILLS} == {"int"}
    assert len(SEARCH_SKILLS) == 4, "p. 187 prints four rows"
    assert len(STUDY_SKILLS) == 5, "p. 189 prints five"


# --- The action economy -----------------------------------------------------------------


def test_both_spend_the_action() -> None:
    """Both are `[Action]` entries, and p. 176 gives one action per turn."""
    for proposal in (
        _propose(search_resolver(dc=10, basis="a quick look")),
        _propose(study_resolver(dc=10, basis="a moment's thought")),
    ):
        spent = [e for e in proposal.always if e.kind is EffectKind.ACTION_SPENT]
        assert len(spent) == 1
