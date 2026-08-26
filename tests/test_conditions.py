"""The fifteen conditions and their mechanical effects (#18).

R18 requires the read surface to report conditions "with their mechanical effects", so the
effects are typed fields and the tests assert the fields rather than the names.

Three things here are the kind of rule a table plays wrong, and each is tested against the
wrong answer as well as the right one:

* **Prone's attack rule has two directions.** Advantage within 5 feet, **Disadvantage
  beyond**. Played as a flat Advantage it helps the attacker at every range.
* **Conditions imply other conditions**, transitively, and Unconscious implies two.
* **An unconscious creature attacked from range has neither Advantage nor Disadvantage** —
  Unconscious grants one, its implied Prone imposes the other, and p. 8 cancels them.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.conditions import (
    CONDITION_VERIFICATION,
    EFFECTS,
    MAX_EXHAUSTION,
    Condition,
    Conditions,
)
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.rules import VerificationState

ADJACENT = Position(2, 0, 0)
DISTANT = Position(30, 0, 0)
TARGET = Position(0, 0, 0)


def held(*conditions: Condition, **kw: object) -> Conditions:
    return Conditions(held=frozenset(conditions), **kw)  # type: ignore[arg-type]


# --- The set is closed under implication ---------------------------------------------


def test_there_are_fifteen_conditions() -> None:
    assert len(Condition) == 15
    assert set(EFFECTS) == set(Condition), "every condition has its effects transcribed"


def test_four_conditions_imply_incapacitated() -> None:
    """pp. 186, 186, 189, 191 — each says "You have the Incapacitated condition."""
    for condition in (
        Condition.PARALYZED,
        Condition.PETRIFIED,
        Condition.STUNNED,
        Condition.UNCONSCIOUS,
    ):
        assert held(condition).has(Condition.INCAPACITATED), condition


def test_unconscious_implies_prone_as_well() -> None:
    """p. 191: "You have the Incapacitated and Prone conditions."""
    unconscious = held(Condition.UNCONSCIOUS)
    assert unconscious.has(Condition.PRONE)
    assert unconscious.has(Condition.INCAPACITATED)


def test_a_condition_applied_twice_is_held_once() -> None:
    """A set, so stacking is unrepresentable rather than merely untaken."""
    assert held(Condition.POISONED, Condition.POISONED).held == frozenset({Condition.POISONED})


def test_implication_is_resolved_when_the_set_is_built() -> None:
    """So a caller asking about Incapacitated never has to know Paralyzed implies it."""
    assert Condition.INCAPACITATED in held(Condition.PARALYZED).held


# --- Prone, in both directions --------------------------------------------------------


def test_prone_gives_advantage_up_close_and_disadvantage_at_range() -> None:
    """p. 186: an attack against a Prone creature "has Advantage if the attacker is within
    5 feet of you. **Otherwise, that attack roll has Disadvantage.**"

    The second sentence is the one played wrong. A flat Advantage helps the attacker at
    every range, and would pass a test that only checked the adjacent case.
    """
    prone = held(Condition.PRONE)
    assert prone.attack_rolls_against(attacker=ADJACENT, target=TARGET) is Advantage.ADVANTAGE
    assert prone.attack_rolls_against(attacker=DISTANT, target=TARGET) is Advantage.DISADVANTAGE


def test_a_prone_creature_attacks_at_disadvantage_regardless() -> None:
    """Its own attacks are unconditional — only attacks *against* it depend on distance."""
    assert held(Condition.PRONE).own_attack_rolls() is Advantage.DISADVANTAGE


def test_without_positions_prone_decides_neither_way() -> None:
    """The engine cannot say which half applies, so it applies neither rather than
    guessing the one that favours the attacker."""
    prone = held(Condition.PRONE)
    assert prone.attack_rolls_against(attacker=None, target=None) is Advantage.NONE


def test_an_unconscious_creature_attacked_from_range_has_neither() -> None:
    """The interaction a table almost always misses. Unconscious grants Advantage on
    attacks against you (p. 191); its implied Prone imposes Disadvantage beyond 5 feet
    (p. 186); and p. 8 says a roll with both "has neither of them".

    Up close the two agree and it is Advantage. At range they oppose and cancel — which is
    the cancellation rule doing real work rather than being restated.
    """
    unconscious = held(Condition.UNCONSCIOUS)
    assert unconscious.attack_rolls_against(attacker=ADJACENT, target=TARGET) is Advantage.ADVANTAGE
    assert unconscious.attack_rolls_against(attacker=DISTANT, target=TARGET) is Advantage.NONE


# --- Grappled, against the grappler and against anyone else --------------------------


def test_grappled_spares_the_grappler() -> None:
    """p. 182: Disadvantage "on attack rolls against any target other than the grappler",
    so attacking the grappler itself is unaffected."""
    grappled = held(Condition.GRAPPLED, grappler_id="ogre")
    assert grappled.own_attack_rolls(target_id="ogre") is Advantage.NONE
    assert grappled.own_attack_rolls(target_id="rat") is Advantage.DISADVANTAGE


def test_grappled_sets_speed_to_zero() -> None:
    assert held(Condition.GRAPPLED).speed_after(30) == 0


# --- Speed, and what beats what -------------------------------------------------------


def test_speed_zero_beats_exhaustion_arithmetic() -> None:
    """Five conditions set Speed to 0 and say it "can't increase", so no later arithmetic
    lifts it — and none lowers it below zero either."""
    for condition in (
        Condition.GRAPPLED,
        Condition.RESTRAINED,
        Condition.PARALYZED,
        Condition.PETRIFIED,
        Condition.UNCONSCIOUS,
    ):
        assert held(condition).speed_after(30) == 0, condition
        assert held(condition, exhaustion_levels=("a-tiring-march",) * 2).speed_after(30) == 0


def test_exhaustion_reduces_speed_by_five_per_level() -> None:
    """p. 181: "reduced by a number of feet equal to 5 times your Exhaustion level"."""
    assert Conditions(exhaustion_levels=("a-tiring-march",) * 1).speed_after(30) == 25
    assert Conditions(exhaustion_levels=("a-tiring-march",) * 3).speed_after(30) == 15


def test_speed_does_not_go_negative() -> None:
    assert Conditions(exhaustion_levels=("a-tiring-march",) * 5).speed_after(20) == 0


# --- Exhaustion ----------------------------------------------------------------------


def test_exhaustion_reduces_every_d20_test_by_two_per_level() -> None:
    """p. 181: "the roll is reduced by 2 times your Exhaustion level" — a penalty, so it is
    arithmetic rather than Disadvantage. Modelling it as Disadvantage would be a different
    rule with a different distribution."""
    assert Conditions(exhaustion_levels=("a-tiring-march",) * 0).d20_penalty == 0
    assert Conditions(exhaustion_levels=("a-tiring-march",) * 3).d20_penalty == -6


def test_a_level_of_six_is_death() -> None:
    """p. 181: "You die if your Exhaustion level is 6."""
    assert Conditions(exhaustion_levels=("a-tiring-march",) * 6).dead_of_exhaustion
    assert not Conditions(exhaustion_levels=("a-tiring-march",) * 5).dead_of_exhaustion


def test_exhaustion_is_held_when_its_level_is_above_zero() -> None:
    assert Conditions(exhaustion_levels=("a-tiring-march",) * 1).has(Condition.EXHAUSTION)
    assert not Conditions(exhaustion_levels=("a-tiring-march",) * 0).has(Condition.EXHAUSTION)


def test_an_impossible_exhaustion_level_is_refused() -> None:
    with pytest.raises(ValueError, match="runs from 0 to 6"):
        Conditions(exhaustion_levels=("a-tiring-march",) * (MAX_EXHAUSTION + 1))

    # A negative level used to need refusing and is now unrepresentable: levels are the
    # rule ids that caused them (0028 clause 1), and there is no such thing as minus one
    # of those. What replaces that check is the one an id makes possible.
    with pytest.raises(ValueError, match="names the rule that caused it"):
        Conditions(exhaustion_levels=("",))


# --- A sample of the individual transcriptions ---------------------------------------


def test_blinded_fails_sight_checks_and_swings_both_attack_rolls() -> None:
    """p. 177 — the two-sided one: attacks against you gain, yours lose."""
    blinded = held(Condition.BLINDED)
    assert EFFECTS[Condition.BLINDED].auto_fail_checks_requiring_sight
    assert blinded.attack_rolls_against(attacker=DISTANT, target=TARGET) is Advantage.ADVANTAGE
    assert blinded.own_attack_rolls() is Advantage.DISADVANTAGE


def test_invisible_swings_both_the_other_way() -> None:
    """p. 184, and it is the mirror of Blinded rather than a different shape."""
    invisible = held(Condition.INVISIBLE)
    assert invisible.attack_rolls_against(attacker=DISTANT, target=TARGET) is Advantage.DISADVANTAGE
    assert invisible.own_attack_rolls() is Advantage.ADVANTAGE
    assert EFFECTS[Condition.INVISIBLE].initiative is Advantage.ADVANTAGE


def test_incapacitated_stops_actions_and_breaks_concentration() -> None:
    """p. 184: "You can't take any action, Bonus Action, or Reaction", and Concentration
    "is broken" — the rule this project's own README calls the most-forgotten in play."""
    effects = EFFECTS[Condition.INCAPACITATED]
    assert effects.cannot_act and effects.concentration_broken and effects.cannot_speak
    assert effects.initiative is Advantage.DISADVANTAGE
    assert held(Condition.STUNNED).cannot_act(), "and it arrives through implication"


def test_paralyzed_and_unconscious_hand_out_automatic_criticals_up_close() -> None:
    """pp. 186, 191: "Any attack roll that hits you is a Critical Hit if the attacker is
    within 5 feet of you." Only those two, and only those two."""
    granting = {c for c in Condition if EFFECTS[c].auto_critical_within_5_feet}
    assert granting == {Condition.PARALYZED, Condition.UNCONSCIOUS}


def test_petrified_resists_all_damage_and_is_immune_to_poison() -> None:
    """p. 186 — the only condition that confers a damage defence."""
    effects = EFFECTS[Condition.PETRIFIED]
    assert effects.resistance_to_all_damage and effects.immune_to_poisoned


def test_four_conditions_make_strength_and_dexterity_saves_fail_outright() -> None:
    failing = {c for c in Condition if EFFECTS[c].auto_fail_strength_and_dexterity_saves}
    assert failing == {
        Condition.PARALYZED,
        Condition.PETRIFIED,
        Condition.STUNNED,
        Condition.UNCONSCIOUS,
    }


def test_restrained_is_the_only_one_that_merely_hampers_dexterity_saves() -> None:
    """p. 187 gives Disadvantage where the four above give automatic failure — a weaker
    rule that is easy to level up to the stronger one."""
    assert EFFECTS[Condition.RESTRAINED].dexterity_saves is Advantage.DISADVANTAGE
    assert not EFFECTS[Condition.RESTRAINED].auto_fail_strength_and_dexterity_saves


# --- What is held but not enforced ---------------------------------------------------


def test_unenforced_clauses_are_named_rather_than_left_to_discovery() -> None:
    """Charmed's "can't attack the charmer" needs target legality (#16); Frightened's
    line-of-sight qualifier needs obstructions (#91). Both are held and reported, and
    neither is enforced — so the gap is a value a caller can read.
    """
    assert "cannot-attack-or-target-the-charmer" in held(Condition.CHARMED).unenforced_clauses()
    assert "line-of-sight-qualifier" in held(Condition.FRIGHTENED).unenforced_clauses()


def test_frightened_applies_its_penalty_without_the_line_of_sight_test() -> None:
    """The stricter reading, and deliberately so: line of sight is not modelled, and
    applying a penalty that might not apply cannot invent a success. Disclosed rather than
    silent — the qualifier is named in `unenforced_clauses`.
    """
    frightened = held(Condition.FRIGHTENED)
    assert frightened.own_attack_rolls() is Advantage.DISADVANTAGE
    assert "line-of-sight-qualifier" in frightened.unenforced_clauses()


def test_the_module_discloses_what_it_does_not_enforce() -> None:
    from srd_rules_engine.core import conditions

    assert conditions.__doc__ is not None
    assert "Line of sight is not modelled" in conditions.__doc__
    assert "#91" in conditions.__doc__


def test_the_conditions_carry_a_verified_citation() -> None:
    assert CONDITION_VERIFICATION.state is VerificationState.VERIFIED
    assert CONDITION_VERIFICATION.reference is not None
    for cited in ("p. 177", "p. 182", "p. 184", "p. 186", "p. 189", "p. 191"):
        assert cited in CONDITION_VERIFICATION.reference
