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
    RITUAL_EXTRA_MINUTES,
    RITUAL_VERIFICATION,
    SPELLCASTING_VERIFICATION,
    Concentration,
    NoSlotAvailable,
    SpellSlots,
    concentration_save,
    concentration_save_dc,
    ritual_cast,
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


def test_restoring_returns_every_slot() -> None:
    """p. 104, as an operation on `SpellSlots`. Whether anything *calls* it is the next test
    down — it went a build without a caller after the rest landed in #185."""
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


def test_the_spell_level_bound_traces_to_the_sentence_that_states_it() -> None:
    """#130. `MAX_SPELL_LEVEL` was right and cited the wrong page.

    It read "p. 26's table runs to level 9" — and p. 26 is the class data this module
    refuses to ship, so the one number taken off that page was the only thing here resting
    on content rather than on a rule. p. 104 states the bound outright, and p. 104 was
    already in the reference.

    Nine was very likely right, which is exactly why this mattered: a right number and a
    wrong one are indistinguishable once inside a finished ruling, and nothing was checking
    this one.
    """
    assert MAX_SPELL_LEVEL == 9
    reference = SPELLCASTING_VERIFICATION.reference or ""
    assert "p. 104" in reference
    assert "0 to 9" in reference, (
        "the reference names p. 104 but not what is read from it, so a reader cannot tell "
        "the level bound is covered rather than only the slot-expenditure rule"
    )
    assert "p. 26" not in reference, (
        "p. 26 is class content this module ships none of; citing it as a source is what "
        "#130 was filed for"
    )


def test_the_spell_level_clause_is_asserted_against_the_document() -> None:
    """Presence, not truth — `scripts/verify_d20_rules.py` needs the PDF and CI has no copy.

    Proven to catch the plausible-wrong value: the clause was corrupted to read "0 to 10"
    and the verifier went red.
    """
    from pathlib import Path as _Path

    verifier = (
        _Path(__file__).resolve().parents[1] / "scripts" / "verify_d20_rules.py"
    ).read_text()
    assert "Every spell has a level from 0 to 9" in verifier, (
        "the spell-level bound is no longer re-checkable against the document (#130)"
    )


def test_slots_start_at_one_because_a_cantrip_uses_none() -> None:
    """The floor is derived from two asserted sentences rather than read off a table.

    p. 104 puts a spell's level in 0-9; p. 178 puts a level 0 spell outside the slot economy
    entirely. Slots therefore run 1 to 9. Neither sentence says "slots run 1 to 9", and this
    engine does not need one that does.

    **A deliberate "nothing changed" guard** — `AGENTS.md`'s named exception. It passes
    against the base commit, because the refusal already worked; #130 moved the *citation*
    under it, not the behaviour. It is here so that re-citing the bound cannot quietly change
    what the bound does. The tests that cover the diff are the two above.
    """
    assert CANTRIP_LEVEL == 0
    with pytest.raises(ValueError, match="spell slots run from level 1"):
        SpellSlots(total={CANTRIP_LEVEL: 1})


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
        # Added by #19 and each a scalar or a citation, which is the property this guard is
        # really about: a name may join this list, a *table* may not.
        "RITUAL_EXTRA_MINUTES",
        "RITUAL_VERIFICATION",
    }, "a slot table hiding in a module constant would read like a verified rule"


def test_the_module_says_what_it_does_not_carry() -> None:
    from srd_rules_engine.core import spellcasting

    assert spellcasting.__doc__ is not None
    assert "Long Rest recovery has no trigger" in spellcasting.__doc__
    assert "issues/19" in spellcasting.__doc__, (
        "the gap is the rest, not the clock — #85 shipped the clock, so the disclosure has "
        "to point at the issue that is still open or it reads as tracked when it is not"
    )


# --- Rituals, and the preparation they need (#19) -----------------------------------------


def test_a_prepared_tagged_spell_may_be_cast_as_a_ritual() -> None:
    """p. 187: "If you have a spell prepared that has the Ritual tag, you can cast that
    spell as a Ritual"."""
    cast = ritual_cast(
        spell_id="detect-magic", prepared=frozenset({"detect-magic"}), has_ritual_tag=True
    )
    assert cast.spell_id == "detect-magic"
    assert cast.extra_minutes == RITUAL_EXTRA_MINUTES == 10
    assert cast.expends_slot is False


def test_a_spell_that_is_not_prepared_may_not_be_ritualled() -> None:
    """The precondition comes before the permission in p. 187's own sentence. A spell merely
    known is not one you may ritual, and an engine that skipped this would let a caster cast
    anything for free."""
    with pytest.raises(ValueError, match="not prepared"):
        ritual_cast(spell_id="detect-magic", prepared=frozenset(), has_ritual_tag=True)


def test_a_spell_without_the_tag_may_not_be_ritualled() -> None:
    """The tag is the spell's own, and arrives from the ruleset — this engine ships no spell
    list to look it up in (#21)."""
    with pytest.raises(ValueError, match="no Ritual tag"):
        ritual_cast(
            spell_id="magic-missile", prepared=frozenset({"magic-missile"}), has_ritual_tag=False
        )


def test_a_ritual_cannot_be_upcast() -> None:
    """**The clause an implementation drops.** p. 187 draws the consequence itself: "It also
    doesn't expend a spell slot, which means the ritual version of a spell can't be cast at a
    higher level."

    An engine that accepted a level here would let a caster upcast for free, which is the one
    thing the sentence exists to prevent — and it would look like a feature.
    """
    with pytest.raises(ValueError, match="expends no spell slot"):
        ritual_cast(
            spell_id="detect-magic",
            prepared=frozenset({"detect-magic"}),
            has_ritual_tag=True,
            at_level=3,
        )


def test_ritual_carries_a_verified_citation() -> None:
    assert RITUAL_VERIFICATION.state is VerificationState.VERIFIED
    assert "p. 187" in (RITUAL_VERIFICATION.reference or "")


# --- A Long Rest restores the slots (#19, p. 104) ------------------------------------------


def test_the_rest_itself_restores_them() -> None:
    """p. 104: "Finishing a Long Rest restores any expended spell slots."

    Not p. 185 — the Long Rest's own entry never mentions slots, which is why this benefit
    was missing from `with_long_rest` for a build after the rest landed in #185. The
    operation existed and the occasion existed and nothing joined them.
    """
    from srd_rules_engine.core.state import Combatant, EncounterState

    caster = Combatant(
        id="pc",
        name="Pc",
        hit_points=4,
        max_hit_points=20,
        armour_class=13,
        abilities={"int": 16},
        proficiency_bonus=2,
        is_player_character=True,
        slots=SpellSlots(total={1: 4, 2: 2}, spent={1: 3, 2: 2}),
    )
    state = EncounterState.new([caster])
    before = state.combatant("pc").slots
    assert before is not None and before.remaining(1) == 1

    rested = state.with_long_rest("pc")
    slots = rested.combatant("pc").slots
    assert slots is not None
    assert slots.remaining(1) == 4
    assert slots.remaining(2) == 2


def test_a_creature_with_no_slots_rests_without_acquiring_any() -> None:
    """`None` means this creature is not a caster, and a rest does not make it one."""
    from srd_rules_engine.core.state import Combatant, EncounterState

    fighter = Combatant(
        id="pc",
        name="Pc",
        hit_points=4,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 16},
        proficiency_bonus=2,
        is_player_character=True,
    )
    rested = EncounterState.new([fighter]).with_long_rest("pc")
    assert rested.combatant("pc").slots is None


def test_preparation_is_one_set_because_castability_asks_one_question() -> None:
    """p. 104 separates always-prepared spells from the changeable list only for the *change
    limit*: "a spell that you always have prepared doesn't count against the number of spells
    on that list". For "is it prepared now", the distinction does not exist — so this engine
    keeps one set and does not model the limit, which is class data."""
    from srd_rules_engine.core.state import Combatant

    caster = Combatant(
        id="pc",
        name="Pc",
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"int": 16},
        proficiency_bonus=2,
        prepared=frozenset({"detect-magic", "shield"}),
    )
    assert "detect-magic" in caster.prepared
    assert not hasattr(caster, "always_prepared"), "one set, per p. 104's own scoping"
