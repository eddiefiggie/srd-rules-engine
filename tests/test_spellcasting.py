"""Spell slots, save DCs, spell attacks and Concentration (#19).

Concentration is what this file is really about. The project's README calls it the
most-forgotten rule in play, and it is forgotten in one direction: a caster starts a second
concentration spell and keeps the first. Every test here that could be written loosely is
written against that failure instead.
"""

from __future__ import annotations

import dataclasses

import pytest

from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import TestKind
from srd_rules_engine.core.obstructions import Obstruction
from srd_rules_engine.core.position import Position
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
    RangeForm,
    SpellRange,
    SpellSlots,
    concentration_save,
    concentration_save_dc,
    ritual_cast,
    spell_attack_modifier,
    spell_reaches,
    spell_save_dc,
)
from srd_rules_engine.core.state import Combatant

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
    that requires Concentration **or activate another effect that requires Concentration**."

    Replacement rather than refusal, and at the moment casting *starts* rather than when it
    resolves — so a caster cannot keep the first by having the second one fail. Holding two
    is unrepresentable here rather than merely discouraged.

    **What is held is a rule id**, not a spell name (#241, 0038 clause 7). The second half of
    the sentence is why: an effect activated from a magic item requires Concentration too, and
    it has no spell name to put in a field. So the ids here are rule ids, and the fact that
    one of them could name an item's effect rather than a spell is the point.
    """
    holding = Concentration().begin("spell:bless")
    assert holding.rule_id == "spell:bless"

    second = holding.begin("item:necklace-of-prayer-beads")
    assert second.rule_id == "item:necklace-of-prayer-beads"
    assert second.active


def test_concentration_can_be_ended_at_will() -> None:
    """p. 179: "The creator can end Concentration at any time (no action required).\""""
    assert not Concentration().begin("spell:bless").ended().active


def test_incapacitation_ends_concentration_without_a_save() -> None:
    """p. 179: "Your Concentration ends if you have the Incapacitated condition." No roll.

    **The rule moved out of `Concentration` in #238 and the rule did not change.** It was a
    pure `after_conditions(conditions)` derivation here; it is now materialised by
    `Combatant.__post_init__`, because p. 179 says *ends* and a derivation cannot record an
    event — the spell came back when the condition lifted (0037 clause 4).

    Which conditions qualify is still `core.conditions`' own `concentration_broken` and is
    still asked in one place, so Stunned qualifies by implying Incapacitated (R14) rather
    than by being listed anywhere.
    """
    holding = Combatant(
        id="pc",
        name="Pc",
        hit_points=10,
        max_hit_points=10,
        armour_class=12,
        abilities={"con": 12},
        proficiency_bonus=2,
        concentration=Concentration().begin("spell:bless"),
    )
    assert holding.concentration.active, "precondition: it is up while nothing has broken it"

    stunned = dataclasses.replace(
        holding, conditions=Conditions(held=frozenset({Condition.STUNNED}))
    )
    assert not stunned.concentration.active

    # And it stays ended, which is the half the derivation could not express.
    assert not dataclasses.replace(stunned, conditions=Conditions()).concentration.active


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


def test_the_clauses_that_end_concentration_are_asserted_against_the_document() -> None:
    """Presence, not truth — the verifier needs the PDF and CI has no copy.

    Two sentences, and the engine now rests on both. p. 179's "Incapacitated **or you die**"
    is what `Combatant.__post_init__` materialises, and the death half is the part a
    conditions-only reading drops — it was unreachable until #238 and is easy to lose again,
    because death is not one of the fifteen conditions.

    "(no action required)" is a **rule value**, not colour: it is why the voluntary end is a
    transition a driver calls rather than a `LegalAction` the surface prices. An engine that
    charged an action for it would be inventing a cost the document declines to state.

    Proved to catch the plausible-wrong value: "at any time (no action required)" was
    corrupted to "as an action" on a copy of the verifier and the clause reported unmatched.
    """
    from pathlib import Path as _Path

    verifier = (
        _Path(__file__).resolve().parents[1] / "scripts" / "verify_d20_rules.py"
    ).read_text()
    assert "Incapacitated condition or you die" in verifier, (
        "the death half of p. 179's clause is gone from verify_d20_rules.py, so the "
        "sentence Combatant.__post_init__ rests on is no longer re-checkable (#238)"
    )
    assert "no action required" in verifier, (
        "the voluntary end's cost is no longer asserted, so nothing goes red if the engine "
        "starts charging an action for something p. 179 gives away"
    )


def test_the_floor_and_the_cap_are_the_documents_own_numbers() -> None:
    """The literals, pinned as literals — and this was missing until #215 proved it.

    Every assertion above compares against `CONCENTRATION_DC_FLOOR` and
    `CONCENTRATION_DC_CAP` rather than against 10 and 30, so **all of them stay green
    against a wrong floor**: with the floor at 11, `concentration_save_dc(2)` returns 11 and
    equals the constant, `(22)` returns 11 and matches its literal, and so on down the file.
    The corruption proof for the floor found this by staying green.

    A wrong DC here is the shape R31 is about: indistinguishable from a right one once it is
    inside a finished ruling, and the sentence it comes from is asserted against the document
    in `scripts/verify_d20_rules.py` — which is what makes these two numbers checkable rather
    than merely agreed with themselves.
    """
    assert CONCENTRATION_DC_FLOOR == 10
    assert CONCENTRATION_DC_CAP == 30


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


def test_the_concentration_damage_clause_is_asserted_against_the_document() -> None:
    """Presence, not truth — the same half a machine here can hold.

    The DC's floor and cap have been asserted since #19. What #215 added is the sentence
    that says *when* the save happens at all, and it is the half that had no clause: p. 179
    names damage as the occasion and names the ability as Constitution. Both are rule values
    and both are the kind of thing recall gets almost right.

    Proven to catch the plausible-wrong value: the ability was corrupted to Wisdom on a copy
    of the verifier and the clause reported unmatched.
    """
    from pathlib import Path as _Path

    verifier = (
        _Path(__file__).resolve().parents[1] / "scripts" / "verify_d20_rules.py"
    ).read_text()
    assert "must succeed on a Constitution saving throw to maintain" in verifier, (
        "the Concentration damage-trigger clause is gone from verify_d20_rules.py, so the "
        "sentence core.concentration rests on is no longer re-checkable (#215)"
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
    """R32. The exclusions are named, and named as what they currently are.

    This test used to assert the docstring said "Long Rest recovery has no trigger". #19
    gave it one, and the sentence became false while the guard kept it in place — a guard on
    a disclosure keeps the disclosure honest only if it moves when the fact does, and this
    one held a stale claim for a build.

    So it now pins the gaps that are open, and the paragraph recording that the recovery gap
    closed. A disclosure that quietly disappears is as misleading as one that quietly
    persists: a reader who remembers it should be able to see what happened.
    """
    from srd_rules_engine.core import spellcasting

    doc = spellcasting.__doc__
    assert doc is not None
    assert "Long Rest recovery had no trigger until #19" in doc, (
        "the closed gap is recorded as closed rather than deleted"
    )
    assert "Components, and the Spellcasting Focus" in doc, "still open, and still said"
    assert "issues/21" in doc, (
        "enumerating what is castable needs a spell list, and the disclosure has to point "
        "at the issue that is open or it reads as tracked when it is not"
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


# --- A spell's range, and the clear path it also needs (#20) ------------------------------


def test_the_three_forms_a_range_takes() -> None:
    """p. 105. Only one of them is a number, which is why this is a form and a distance
    rather than an integer with sentinel values."""
    assert SpellRange(RangeForm.DISTANCE, 60).feet == 60
    assert SpellRange(RangeForm.TOUCH).feet is None
    assert SpellRange(RangeForm.SELF).feet is None


def test_a_distance_range_needs_a_distance() -> None:
    with pytest.raises(ValueError, match="expressed in feet"):
        SpellRange(RangeForm.DISTANCE)


def test_touch_and_self_carry_no_number_to_invent() -> None:
    """p. 105 gives Touch as the caster's reach and Self as the caster. Neither is a
    distance this engine may supply, so neither may carry one."""
    with pytest.raises(ValueError, match="carries no distance"):
        SpellRange(RangeForm.TOUCH, 5)


def test_self_reaches_only_the_caster() -> None:
    here, there = Position(0, 0, 0), Position(5, 0, 0)
    assert spell_reaches(here, caster=here, spell_range=SpellRange(RangeForm.SELF), reach_feet=5)
    assert not spell_reaches(
        there, caster=here, spell_range=SpellRange(RangeForm.SELF), reach_feet=5
    )


def test_touch_reaches_as_far_as_the_caster_does() -> None:
    """p. 105 defers to the caster's reach, and p. 186 puts that at 5 feet unless a rule
    says otherwise — so a creature with longer reach touches further, and this engine takes
    the number from the creature rather than from a constant."""
    here = Position(0, 0, 0)
    touch = SpellRange(RangeForm.TOUCH)
    assert spell_reaches(Position(5, 0, 0), caster=here, spell_range=touch, reach_feet=5)
    assert not spell_reaches(Position(10, 0, 0), caster=here, spell_range=touch, reach_feet=5)
    assert spell_reaches(Position(10, 0, 0), caster=here, spell_range=touch, reach_feet=10)


def test_a_distance_range_reaches_exactly_that_far() -> None:
    here = Position(0, 0, 0)
    sixty = SpellRange(RangeForm.DISTANCE, 60)
    assert spell_reaches(Position(60, 0, 0), caster=here, spell_range=sixty, reach_feet=5)
    assert not spell_reaches(Position(65, 0, 0), caster=here, spell_range=sixty, reach_feet=5)


def test_total_cover_stops_a_spell_however_close_it_is() -> None:
    """p. 106: "To target something with a spell, a caster must have a clear path to it, so
    it can't be behind Total Cover."

    A second, independent test — the range being satisfied is not enough, and a wall five
    feet away defeats a 120-foot spell.
    """
    wall = Obstruction(lo=Position(2, -20, 0), hi=Position(3, 20, 20))
    assert not spell_reaches(
        Position(10, 0, 0),
        caster=Position(0, 0, 0),
        spell_range=SpellRange(RangeForm.DISTANCE, 120),
        reach_feet=5,
        obstructions=(wall,),
    )


def test_a_wall_that_is_not_between_them_stops_nothing() -> None:
    """Blocking is per-line (#91). Standing beside a wall is not standing behind it."""
    wall = Obstruction(lo=Position(2, -20, 0), hi=Position(3, 20, 20))
    assert spell_reaches(
        Position(0, 30, 0),
        caster=Position(0, 0, 0),
        spell_range=SpellRange(RangeForm.DISTANCE, 120),
        reach_feet=5,
        obstructions=(wall,),
    )
