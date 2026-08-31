"""p. 18's Temporary Hit Points, and p. 177's Bloodied (#412).

p. 190's glossary entry for Temporary Hit Points is an **index**, not the rule: it says they
are "granted by certain effects and act as a buffer" and points at "Playing the Game". The
mechanic is p. 18, in five clauses, and 0033 is the record that says a glossary entry does not
bound a shape.

The clause that matters most is the one an implementation answers by accident: **the buffer
absorbs damage without reducing it**. p. 18 calls them "a buffer against losing actual Hit
Points", and p. 17's Resistance is the contrast — it says "halve the damage", so a resisted
blow really is smaller. Nothing on p. 18 says that, so a fully-absorbed blow is still damage
taken, and p. 179's Concentration save and p. 18's death-save failure both still fire (#413).
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.conditions import Conditions
from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}


def _creature(*, hp: int = 20, maximum: int = 20, temporary: int = 0) -> Combatant:
    return Combatant(
        id="pc",
        name="Wren",
        hit_points=hp,
        max_hit_points=maximum,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        is_player_character=True,
        temporary_hit_points=temporary,
        conditions=Conditions(),
    )


def _state(creature: Combatant | None = None) -> EncounterState:
    return EncounterState.new([creature or _creature()])


# --- Lose Temporary Hit Points First ----------------------------------------------------


def test_the_document_s_own_example() -> None:
    """p. 18: "if you have 5 Temporary Hit Points and take 7 damage, you lose those points
    and then lose 2 Hit Points." Asserted as printed, because a worked example in the
    document is the one case an implementation cannot argue with."""
    after = _state(_creature(hp=20, temporary=5)).with_damage("pc", 7).combatant("pc")

    assert after.temporary_hit_points == 0
    assert after.hit_points == 18, "7 damage, 5 absorbed, 2 carried over"


def test_a_partly_spent_buffer_keeps_what_is_left() -> None:
    after = _state(_creature(hp=20, temporary=5)).with_damage("pc", 2).combatant("pc")

    assert after.temporary_hit_points == 3
    assert after.hit_points == 20, "nothing carried over, so no Hit Points were lost"


# --- They are a buffer against LOSING hit points, not against taking damage (#413) -------


def test_a_fully_absorbed_blow_is_still_damage_taken() -> None:
    """The reading everything else rests on. p. 18 never says Temporary Hit Points reduce
    damage — p. 17's Resistance says "halve the damage" and this does not — so a creature at
    0 Hit Points still suffers p. 18's Death Saving Throw failure for "any damage", even when
    the buffer swallowed all of it.

    Written against the opposite implementation, which is the one a subtraction in the wrong
    place produces and which nothing else here would catch."""
    downed = _state(_creature(hp=0, temporary=10))
    after = downed.with_damage("pc", 6).combatant("pc")

    assert after.temporary_hit_points == 4, "the buffer took it"
    assert after.hit_points == 0
    assert after.death_saves.failures == 1, "and the creature still took damage at 0 (p. 18)"


# --- They're Not Hit Points or Healing ---------------------------------------------------


def test_a_creature_at_full_hit_points_can_receive_them() -> None:
    """p. 18 says so outright: "a creature can be at full Hit Points and receive Temporary
    Hit Points"."""
    after = _state(_creature(hp=20)).with_temporary_hit_points("pc", 8).combatant("pc")

    assert after.hit_points == 20
    assert after.temporary_hit_points == 8


def test_receiving_them_does_not_reset_death_saves() -> None:
    """p. 17 resets both counts "when you regain any Hit Points", and p. 18 says these are
    not Hit Points and that receiving them "doesn't count as healing". `with_healing` resets
    and this must not — the difference is the whole reason they are two methods."""
    downed = _state(_creature(hp=0)).with_death_save("pc", failures=2)
    assert downed.combatant("pc").death_saves.failures == 2

    after = downed.with_temporary_hit_points("pc", 12).combatant("pc")

    assert after.temporary_hit_points == 12
    assert after.death_saves.failures == 2, "not reset — p. 18: only true healing saves you"
    assert after.hit_points == 0, "and it is still unconscious"


# --- They Don't Stack, and the choice is the creature's ---------------------------------


def test_a_second_grant_refuses_rather_than_choosing() -> None:
    """p. 18: "If you have Temporary Hit Points and receive more of them, **you decide**
    whether to keep the ones you have or to gain the new ones." Taking the larger is the
    engine choosing, and the document's own example is 12 offered over 10 — where keeping
    10 is a legal answer."""
    held = _state(_creature(temporary=10))

    with pytest.raises(ValueError, match="cannot be added together"):
        held.with_temporary_hit_points("pc", 12)


def test_the_creature_may_keep_the_smaller_set() -> None:
    """The case that proves the refusal is not theatre. An engine that quietly took the
    larger would pass every other test in this file."""
    held = _state(_creature(temporary=10))

    kept = held.with_temporary_hit_points("pc", 12, replacing=False).combatant("pc")
    taken = held.with_temporary_hit_points("pc", 12, replacing=True).combatant("pc")

    assert kept.temporary_hit_points == 10, "12 offered, 10 kept, and 22 never available"
    assert taken.temporary_hit_points == 12


def test_a_first_grant_needs_no_choice() -> None:
    """There is nothing to choose between, so requiring a decision would be ceremony."""
    after = _state(_creature()).with_temporary_hit_points("pc", 7).combatant("pc")
    assert after.temporary_hit_points == 7


# --- Duration -----------------------------------------------------------------------------


def test_a_long_rest_ends_them() -> None:
    """p. 18: "Temporary Hit Points last until they're depleted or you finish a Long Rest."
    Stated where the buffer is defined rather than on p. 185, which lists what a rest
    restores and never mentions them."""
    after = _state(_creature(hp=4, temporary=9)).with_long_rest("pc").combatant("pc")

    assert after.temporary_hit_points == 0
    assert after.hit_points == 20, "and the rest still did what p. 185 says"


# --- p. 177's Bloodied --------------------------------------------------------------------


def test_bloodied_is_half_hit_points_or_fewer() -> None:
    """p. 177: "A creature is Bloodied while it has half its Hit Points or fewer remaining.\""""
    assert not _creature(hp=11, maximum=20).is_bloodied
    assert _creature(hp=10, maximum=20).is_bloodied, "half is Bloodied, not just below it"
    assert _creature(hp=1, maximum=20).is_bloodied
    assert _creature(hp=0, maximum=20).is_bloodied


def test_an_odd_maximum_needs_no_rounding_rule() -> None:
    """Compared doubled rather than halved, because the document supplies no rounding rule
    for an odd maximum and inventing one would be a rule value R31 forbids."""
    assert _creature(hp=10, maximum=21).is_bloodied, "20 <= 21"
    assert not _creature(hp=11, maximum=21).is_bloodied, "22 > 21"


def test_temporary_hit_points_do_not_lift_it() -> None:
    """p. 18: they "can't be added to your Hit Points". So a creature on 4 of 20 behind a
    buffer of 30 is Bloodied — the buffer is deep and its Hit Points are still half or
    fewer."""
    assert _creature(hp=4, maximum=20, temporary=30).is_bloodied


def test_nothing_stores_it() -> None:
    """*While* is the operative word: p. 177 states a condition on the current total rather
    than a state something applies and something else removes. A stored flag could disagree
    with the hit points it is about, which is the one way this rule goes wrong."""
    healed = _state(_creature(hp=4)).with_healing("pc", 10).combatant("pc")

    assert not healed.is_bloodied, "recomputed from the total, not carried"
