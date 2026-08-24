"""Spell slots, save DCs, spell attacks and Concentration (#19).

Concentration is what this file is really about. The project's README calls it the
most-forgotten rule in play, and it is forgotten in one direction: a caster starts a second
concentration spell and keeps the first. Every test here that could be written loosely is
written against that failure instead.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import TestKind
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.spellcasting import (
    CANTRIP_LEVEL,
    CONCENTRATION_DC_CAP,
    CONCENTRATION_DC_FLOOR,
    MAX_SPELL_LEVEL,
    SPELLCASTING_VERIFICATION,
    Concentration,
    NoSlotAvailable,
    SpellSlots,
    concentration_save,
    concentration_save_dc,
    spell_attack_modifier,
    spell_save_dc,
)

WIZARD = SpellSlots(total={1: 4, 2: 3, 3: 2})


# --- Slots ----------------------------------------------------------------------------


def test_a_spell_fits_a_slot_of_its_own_level_or_higher() -> None:
    """p. 104: "you expend a slot of that spell's level or higher" — the document's own
    image is a groove: "A level 1 spell fits into a slot of any size, but a level 2 spell
    fits only into a slot that's at least level 2.\""""
    assert WIZARD.payable_by(1) == (1, 2, 3)
    assert WIZARD.payable_by(3) == (3,)
    assert WIZARD.payable_by(4) == ()


def test_casting_spends_the_lowest_slot_that_pays() -> None:
    """The choice a caster almost always makes, and never the engine reaching for one that
    was not available."""
    after = WIZARD.cast(1)
    assert after.remaining(1) == 3
    assert after.remaining(2) == 3, "the higher slots are untouched"


def test_upcasting_spends_the_slot_it_was_told_to() -> None:
    after = WIZARD.cast(1, at_level=3)
    assert after.remaining(1) == 4
    assert after.remaining(3) == 1


def test_a_spell_cannot_be_cast_in_a_smaller_slot() -> None:
    with pytest.raises(NoSlotAvailable, match="does not fit"):
        WIZARD.cast(3, at_level=1)


def test_casting_with_nothing_left_is_refused_rather_than_improvised() -> None:
    drained = SpellSlots(total={1: 1}).cast(1)
    assert not drained.can_cast(1)
    with pytest.raises(NoSlotAvailable, match="none remains"):
        drained.cast(1)


def test_a_cantrip_costs_no_slot_at_all() -> None:
    """p. 178: "A cantrip is a level 0 spell, which is cast without a spell slot."

    So it stays castable when everything else has run out, which is the whole point of one.
    """
    drained = SpellSlots(total={1: 1}).cast(1)
    assert drained.can_cast(CANTRIP_LEVEL)
    assert drained.cast(CANTRIP_LEVEL) == drained
    assert WIZARD.payable_by(CANTRIP_LEVEL) == ()


def test_a_long_rest_restores_every_expended_slot() -> None:
    """p. 104. The operation exists; nothing triggers it, because the *rest* is not modelled
    (#19). The clock it used to wait on arrived with #85."""
    spent = WIZARD.cast(1).cast(2).cast(3)
    assert spent.restored().remaining(1) == 4
    assert spent.restored().remaining(3) == 2


def test_slot_levels_outside_one_to_nine_are_refused() -> None:
    with pytest.raises(ValueError, match="level 1 to 9"):
        SpellSlots(total={0: 3})
    with pytest.raises(ValueError, match="level 1 to 9"):
        SpellSlots(total={MAX_SPELL_LEVEL + 1: 1})


# --- Save DC and attack modifier -----------------------------------------------------


def test_the_spell_save_dc_and_attack_modifier_share_two_terms() -> None:
    """p. 106: "Spell save DC = 8 + your spellcasting ability modifier + your Proficiency
    Bonus" and "Spell attack modifier = your spellcasting ability modifier + your
    Proficiency Bonus" — the same two terms, and the 8 belongs to only one of them."""
    assert spell_save_dc(3, 2) == 13
    assert spell_attack_modifier(3, 2) == 5
    assert spell_save_dc(3, 2) - spell_attack_modifier(3, 2) == 8


def test_a_negative_ability_modifier_lowers_both() -> None:
    assert spell_save_dc(-1, 2) == 9
    assert spell_attack_modifier(-1, 2) == 1


# --- Concentration: the rule this module exists for ----------------------------------


def test_starting_a_second_concentration_spell_ends_the_first() -> None:
    """p. 179: "You lose Concentration on an effect the moment you start casting a spell
    that requires Concentration."

    Replacement rather than refusal, and at the moment casting *starts* rather than when it
    resolves — so a caster cannot keep the first by having the second one fail. Holding two
    is unrepresentable here rather than merely discouraged.
    """
    holding = Concentration().begin("Bless")
    assert holding.spell == "Bless"

    second = holding.begin("Hold Person")
    assert second.spell == "Hold Person"
    assert second.active


def test_concentration_can_be_ended_at_will() -> None:
    """p. 179: "The creator can end Concentration at any time (no action required).\""""
    assert not Concentration().begin("Bless").ended().active


def test_incapacitation_ends_concentration_without_a_save() -> None:
    """p. 179: "Your Concentration ends if you have the Incapacitated condition." No roll.

    Read from `core.conditions`' own `concentration_broken` rather than re-deciding which
    conditions qualify, so the two cannot disagree.
    """
    holding = Concentration().begin("Bless")
    stunned = Conditions(held=frozenset({Condition.STUNNED}))
    assert not holding.after_conditions(stunned).active
    assert holding.after_conditions(Conditions()).active


def test_the_concentration_dc_is_ten_or_half_the_damage() -> None:
    """p. 179: "10 or half the damage taken (round down), whichever number is higher.\""""
    assert concentration_save_dc(22) == 11
    assert concentration_save_dc(30) == 15


def test_half_the_damage_rounds_down_on_an_odd_hit() -> None:
    """Every even amount hides this: 22 halves to 11 whichever way it rounds. 23 does not.

    The document says "(round down)", so 23 damage is DC 11 and not 12 — and a rounding-up
    implementation survives any test whose damage values are all even. This one exists
    because mutation testing found exactly that hole.
    """
    assert concentration_save_dc(23) == 11
    assert concentration_save_dc(21) == CONCENTRATION_DC_FLOOR, "10 wins over 10.5 rounded down"
    assert concentration_save_dc(45) == 22


def test_the_floor_makes_small_hits_still_threaten_concentration() -> None:
    """Without the floor, a 2-damage hit would set DC 1 and never break anything — which is
    the version that quietly makes Concentration unloseable."""
    assert concentration_save_dc(2) == CONCENTRATION_DC_FLOOR
    assert concentration_save_dc(0) == CONCENTRATION_DC_FLOOR
    assert concentration_save_dc(19) == CONCENTRATION_DC_FLOOR, "9 is below the floor"


def test_the_cap_keeps_a_huge_hit_makeable() -> None:
    """Without the cap a 90-damage hit would set DC 45, which almost nothing could make."""
    assert concentration_save_dc(90) == CONCENTRATION_DC_CAP
    assert concentration_save_dc(60) == CONCENTRATION_DC_CAP
    assert concentration_save_dc(58) == 29, "just under the cap, still arithmetic"


def test_the_save_is_a_constitution_save_the_engine_can_roll() -> None:
    """The kind and the target are the rule; the modifiers are the caster's and arrive from
    the caller, so nothing here invents a bonus."""
    test = concentration_save(22)
    assert test.kind is TestKind.SAVE
    assert test.target == 11
    assert test.modifiers == ()
    assert "Concentration" in test.target_basis


def test_negative_damage_is_refused() -> None:
    with pytest.raises(ValueError, match="not negative"):
        concentration_save_dc(-1)


def test_a_concentration_effect_is_named() -> None:
    """An unnamed effect could not be ended later, so it is refused at the start."""
    with pytest.raises(ValueError, match="is named"):
        Concentration().begin("")


# --- Provenance and what is absent ---------------------------------------------------


def test_spellcasting_carries_a_verified_citation() -> None:
    assert SPELLCASTING_VERIFICATION.state is VerificationState.VERIFIED
    assert SPELLCASTING_VERIFICATION.reference is not None
    for cited in ("p. 104", "p. 106", "p. 178", "p. 179", "p. 188"):
        assert cited in SPELLCASTING_VERIFICATION.reference


def test_no_slot_table_ships_in_this_module() -> None:
    """p. 26 prints slots per class level, and that is content. A table compiled here would
    be the inferred rule value R31 forbids, and would read exactly like a verified one."""
    import ast
    import inspect

    from srd_rules_engine.core import spellcasting

    tree = ast.parse(inspect.getsource(spellcasting))
    constants = {
        target.id
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
        for target in [node.target]
    }
    assert constants == {
        "CANTRIP_LEVEL",
        "MAX_SPELL_LEVEL",
        "CONCENTRATION_DC_FLOOR",
        "CONCENTRATION_DC_CAP",
        "SPELLCASTING_VERIFICATION",
    }, "a slot table hiding in a module constant would read like a verified rule"


def test_the_module_says_what_it_does_not_carry() -> None:
    from srd_rules_engine.core import spellcasting

    assert spellcasting.__doc__ is not None
    assert "Long Rest recovery has no trigger" in spellcasting.__doc__
    assert "issues/19" in spellcasting.__doc__, (
        "the gap is the rest, not the clock — #85 shipped the clock, so the disclosure has "
        "to point at the issue that is still open or it reads as tracked when it is not"
    )
