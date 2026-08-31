"""Which rule caused a condition, and the two endings p. 184 needs it for (0083, #428).

p. 191's Unconscious entry states the condition's **effects** and never says when it ends, so
the ending belongs to whatever applied it. p. 184 states two endings for a creature knocked
out — regaining any hit points, and first aid — and neither may touch a creature that is
Unconscious for some other reason.

`Conditions` already answered the adjacent question twice. `sources` says **who** imposed a
condition (p. 182's Grappled turns on the grappler), and `exhaustion_levels` keys each level
by the **rule** that caused it (0028 clause 1). `causes` is the second of those shapes applied
to a general condition.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.state import KNOCKED_OUT_RULE_ID, Combatant, EncounterState

OTHER = "fixture:a-sleeping-draught"
ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}


def _creature(hp: int = 1) -> Combatant:
    return Combatant(
        id="pc",
        name="Wren",
        hit_points=hp,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        is_player_character=True,
    )


def _knocked_out(hp: int = 1) -> EncounterState:
    return EncounterState.new([_creature(hp)]).with_condition(
        "pc", Condition.UNCONSCIOUS, caused_by=KNOCKED_OUT_RULE_ID
    )


# --- The shape of the field ---------------------------------------------------------------


def test_a_cause_belongs_to_an_applied_condition_not_an_implied_one() -> None:
    """p. 184's Unconscious implies Incapacitated and Prone, and neither of those is
    knocked-out-ness. `durations` is keyed the same way and for the same reason."""
    conditions = Conditions(
        held=frozenset({Condition.UNCONSCIOUS}),
        causes={Condition.UNCONSCIOUS: frozenset({KNOCKED_OUT_RULE_ID})},
    )

    assert Condition.INCAPACITATED in conditions.held, "implied, as p. 191 says"
    assert Condition.INCAPACITATED not in conditions.causes, "and it has no cause of its own"

    with pytest.raises(ValueError, match="nothing to have caused"):
        Conditions(
            held=frozenset({Condition.PRONE}),
            causes={Condition.UNCONSCIOUS: frozenset({KNOCKED_OUT_RULE_ID})},
        )


def test_an_empty_cause_set_is_refused() -> None:
    """ "Caused by nothing" is not a state — it is an entry that should be absent, and a set
    that empties should take its key with it."""
    with pytest.raises(ValueError, match="at least one rule"):
        Conditions(
            held=frozenset({Condition.UNCONSCIOUS}), causes={Condition.UNCONSCIOUS: frozenset()}
        )


def test_a_condition_holds_many_causes_because_it_does_not_stack() -> None:
    """p. 179: "A condition doesn't stack with itself; a recipient either has a condition or
    doesn't." So a creature knocked out *and* put to sleep holds one Unconscious with two
    causes — which is `sources`' shape, one question along."""
    state = _knocked_out().with_condition("pc", Condition.UNCONSCIOUS, caused_by=OTHER)

    assert state.combatant("pc").conditions.causes[Condition.UNCONSCIOUS] == frozenset(
        {KNOCKED_OUT_RULE_ID, OTHER}
    )


# --- p. 184's first ending: any hit points ------------------------------------------------


def test_healing_wakes_a_creature_that_was_knocked_out() -> None:
    """p. 184: "remains Unconscious until it regains **any** Hit Points". Any — so one point
    does it, the way one point clears the death saves."""
    woken = _knocked_out().with_healing("pc", 1).combatant("pc")

    assert Condition.UNCONSCIOUS not in woken.conditions.held
    assert woken.hit_points == 2


def test_healing_does_not_wake_a_creature_unconscious_for_another_reason() -> None:
    """The reason `causes` exists. p. 191 never says when Unconscious ends, so the ending
    belongs to the cause — and without this field the two are the same condition and a cure
    wound would rouse a sleeper."""
    asleep = EncounterState.new([_creature()]).with_condition(
        "pc", Condition.UNCONSCIOUS, caused_by=OTHER
    )

    still = asleep.with_healing("pc", 5).combatant("pc")

    assert Condition.UNCONSCIOUS in still.conditions.held
    assert still.hit_points == 6, "healed, and still asleep"


def test_healing_a_doubly_unconscious_creature_removes_one_cause_only() -> None:
    """The arithmetic that makes the field worth having. Healing satisfies p. 184 and says
    nothing about the draught, so the condition stays and only its cause leaves — an
    implementation that ended the condition outright would wake a sleeper with a bandage."""
    both = _knocked_out().with_condition("pc", Condition.UNCONSCIOUS, caused_by=OTHER)

    after = both.with_healing("pc", 3).combatant("pc")

    assert Condition.UNCONSCIOUS in after.conditions.held, "the draught still holds"
    assert after.conditions.causes[Condition.UNCONSCIOUS] == frozenset({OTHER})


def test_healing_a_creature_nobody_knocked_out_changes_no_conditions() -> None:
    """The ordinary case: most healing happens to creatures who were never subdued."""
    hurt = EncounterState.new([_creature(hp=4)])
    assert hurt.with_healing("pc", 3).combatant("pc").conditions.held == frozenset()


# --- p. 184's second ending: first aid ----------------------------------------------------


def test_first_aid_wakes_only_the_knocked_out() -> None:
    """p. 184's other ending, and it restores no hit points — the creature wakes at whatever
    it was left on."""
    woken = _knocked_out().with_first_aid("pc").combatant("pc")

    assert Condition.UNCONSCIOUS not in woken.conditions.held
    assert woken.hit_points == 1, "p. 184 restores none"

    asleep = EncounterState.new([_creature()]).with_condition(
        "pc", Condition.UNCONSCIOUS, caused_by=OTHER
    )
    assert Condition.UNCONSCIOUS in asleep.with_first_aid("pc").combatant("pc").conditions.held


# --- What removal must not carry ----------------------------------------------------------


def test_the_prone_that_survives_unconscious_carries_no_cause() -> None:
    """p. 191: "When this condition ends, you remain Prone." `without` re-applies Prone on its
    own behalf, so it was not caused by whatever caused the Unconscious — and carrying the
    cause across would say it was."""
    woken = _knocked_out().with_healing("pc", 1).combatant("pc").conditions

    assert Condition.PRONE in woken.held, "p. 191's exception still holds"
    assert Condition.PRONE not in woken.causes
    assert woken.causes == {}


def test_a_prone_with_its_own_cause_does_not_carry_it_through_p191() -> None:
    """The case clause 7 exists for, and it needs both conditions to end at once.

    p. 191 re-applies Prone **on its own behalf** when Unconscious ends. A creature that was
    also Prone for some other reason, and whose Prone ends in the same breath, gets that Prone
    back from p. 191 — not from the rule that had caused the old one. Keeping the cause would
    say a creature is still prone *because it was tripped*, when what is holding it down is
    p. 191's sentence.

    The first version of this test only ended Unconscious, where `c in remaining` already
    filters the entry out, so it stayed green with the guard removed."""
    tripped = Conditions(
        held=frozenset({Condition.UNCONSCIOUS, Condition.PRONE}),
        causes={
            Condition.UNCONSCIOUS: frozenset({KNOCKED_OUT_RULE_ID}),
            Condition.PRONE: frozenset({"fixture:a-caltrop"}),
        },
    )

    after = tripped.without(frozenset({Condition.UNCONSCIOUS, Condition.PRONE}))

    assert Condition.PRONE in after.held, "p. 191 puts it back"
    assert Condition.PRONE not in after.causes, "but not for the reason it was there before"
