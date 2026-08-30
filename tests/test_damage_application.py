"""Resistance, Vulnerability and Immunity, and the order they apply in (#16).

The order is the point. p. 17 states one rather than leaving it to arithmetic, because
halving and doubling do not commute once rounding is involved — and the document prints a
worked example whose answer differs depending on which you do first. That example is the
first test here.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.damage import (
    DAMAGE_VERIFICATION,
    DamageType,
    Defences,
    after_defences,
)
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.spellcasting import CONCENTRATION_RULE_ID, Concentration
from srd_rules_engine.core.state import Combatant, EncounterState, ForcedSave

FIRE = DamageType.FIRE
NECROTIC = DamageType.NECROTIC


def combatant(**defence_kwargs: object) -> Combatant:
    return Combatant(
        id="hero",
        name="Hero",
        hit_points=40,
        max_hit_points=40,
        armour_class=15,
        abilities={"str": 14},
        proficiency_bonus=2,
        is_player_character=True,
        defences=Defences(**defence_kwargs),  # type: ignore[arg-type]
    )


# --- The document's own worked example ------------------------------------------------


def test_the_documents_worked_example_produces_the_number_it_prints() -> None:
    """p. 17: a creature with Resistance to all damage and Vulnerability to Fire, inside an
    aura reducing all damage by 5, taking 28 Fire damage. The document walks it: 28 reduced
    by 5 is 23, "then halved for the creature's Resistance (and rounded down to 11), then
    doubled for its Vulnerability (to 22)".

    The aura is an *adjustment*, applied first and so already folded into the amount that
    arrives here. Everything after it is this function's job.
    """
    defences = Defences(vulnerabilities=frozenset({FIRE}), resists_all=True)
    outcome = after_defences(23, FIRE, defences)

    assert outcome.amount == 22
    assert "11" in outcome.derivation(), "the rounding happens at the halving"


def test_doubling_before_halving_would_give_a_different_answer() -> None:
    """Which is why the document fixes an order. 23 doubled is 46, halved is 23 — not 22.

    This is the test that makes the order load-bearing rather than decorative: an
    implementation that applied Vulnerability first passes every other test in this file.
    """
    defences = Defences(vulnerabilities=frozenset({FIRE}), resists_all=True)
    assert after_defences(23, FIRE, defences).amount == 22
    assert (23 * 2) // 2 == 23, "the wrong order's answer, stated so the difference is visible"


# --- Each defence on its own ----------------------------------------------------------


def test_resistance_halves_and_rounds_down() -> None:
    """p. 187: "damage of that type is halved against you (round down)."""
    defences = Defences(resistances=frozenset({FIRE}))
    assert after_defences(10, FIRE, defences).amount == 5
    assert after_defences(7, FIRE, defences).amount == 3, "round down, not to 3.5 or 4"
    assert after_defences(1, FIRE, defences).amount == 0


def test_vulnerability_doubles() -> None:
    """p. 191: "damage of that type is doubled against you."""
    assert after_defences(7, FIRE, Defences(vulnerabilities=frozenset({FIRE}))).amount == 14


def test_immunity_takes_none_of_it() -> None:
    """p. 183: "it doesn't affect you in any way." Not reduced — none."""
    outcome = after_defences(99, FIRE, Defences(immunities=frozenset({FIRE})))
    assert outcome.amount == 0
    assert "Immunity" in outcome.derivation()


def test_immunity_outranks_vulnerability() -> None:
    """ "Doesn't affect you in any way" leaves nothing for Vulnerability to double."""
    defences = Defences(immunities=frozenset({FIRE}), vulnerabilities=frozenset({FIRE}))
    assert after_defences(30, FIRE, defences).amount == 0


def test_a_defence_only_applies_to_its_own_damage_type() -> None:
    defences = Defences(resistances=frozenset({FIRE}), vulnerabilities=frozenset({NECROTIC}))
    assert after_defences(10, NECROTIC, defences).amount == 20
    assert after_defences(10, FIRE, defences).amount == 5
    assert after_defences(10, DamageType.COLD, defences).amount == 10


def test_untyped_damage_matches_no_defence() -> None:
    """A resolver need not name a type, and an untyped amount is not secretly typed."""
    defences = Defences(resistances=frozenset({FIRE}), immunities=frozenset({NECROTIC}))
    assert after_defences(10, None, defences).amount == 10


def test_resistance_to_all_damage_covers_an_unnamed_type() -> None:
    assert after_defences(10, DamageType.THUNDER, Defences(resists_all=True)).amount == 5
    assert after_defences(10, None, Defences(resists_all=True)).amount == 5


# --- No stacking ----------------------------------------------------------------------


def test_two_resistances_to_the_same_type_halve_it_once() -> None:
    """p. 17: "Multiple instances of Resistance or Vulnerability that affect the same
    damage type count as only one instance." The document's own example is Resistance to
    Necrotic *plus* Resistance to all damage, which halves Necrotic once.

    Sets rather than counters make the stacking reading unrepresentable rather than merely
    untaken — the same move `has_advantage` makes for the d20.
    """
    defences = Defences(resistances=frozenset({NECROTIC}), resists_all=True)
    assert after_defences(20, NECROTIC, defences).amount == 10
    assert len(after_defences(20, NECROTIC, defences).steps) == 2, "one halving, not two"


def test_resistance_and_vulnerability_do_not_cancel() -> None:
    """They are applied in order, not netted off. The document's worked example has both
    on the same instance and lands on 22 from 23, never on 23.

    Cancelling them would be the advantage rule imported into a place the document never
    put it — and it is exactly the shortcut a reasonable implementer takes.
    """
    defences = Defences(resistances=frozenset({FIRE}), vulnerabilities=frozenset({FIRE}))
    assert after_defences(7, FIRE, defences).amount == 6, "halved to 3, doubled to 6"
    assert after_defences(7, FIRE, defences).amount != 7


# --- Through the state transition -----------------------------------------------------


def test_defences_resolve_before_hit_points_move() -> None:
    state = EncounterState.new([combatant(resistances=frozenset({FIRE}))])
    reduced = state.with_damage("hero", 10, damage_type=FIRE)
    assert reduced.combatant("hero").hit_points == 35, "5 taken, not 10"


def test_immunity_means_no_damage_and_so_no_death_save_failure() -> None:
    """Everything downstream is about damage *taken*. p. 18 charges a failure for "any
    damage" at 0 hit points, and a creature immune to the type takes none — so applying
    defences after the death rules would charge a failure for a blow that never landed.
    """
    down = EncounterState.new(
        [
            Combatant(
                id="hero",
                name="Hero",
                hit_points=0,
                max_hit_points=40,
                armour_class=15,
                abilities={"str": 14},
                proficiency_bonus=2,
                is_player_character=True,
                defences=Defences(immunities=frozenset({FIRE})),
            )
        ]
    )
    after = down.with_damage("hero", 30, damage_type=FIRE)
    assert after.combatant("hero").death_saves.failures == 0
    assert not after.combatant("hero").death_saves.dead


def test_resistance_can_save_a_character_from_massive_damage() -> None:
    """Massive Damage measures the remainder of the damage *taken* (p. 17). A character on
    6 of 12 hit points takes 18 and dies — unless Resistance halved it to 9 first, leaving
    a remainder of 3.
    """

    def hero(resists: bool) -> EncounterState:
        return EncounterState.new(
            [
                Combatant(
                    id="hero",
                    name="Hero",
                    hit_points=6,
                    max_hit_points=12,
                    armour_class=15,
                    abilities={"str": 14},
                    proficiency_bonus=2,
                    is_player_character=True,
                    defences=Defences(resistances=frozenset({FIRE})) if resists else Defences(),
                )
            ]
        )

    assert hero(False).with_damage("hero", 18, damage_type=FIRE).combatant("hero").death_saves.dead
    survived = hero(True).with_damage("hero", 18, damage_type=FIRE).combatant("hero")
    assert not survived.death_saves.dead
    assert survived.hit_points == 0


# --- The damage threshold (p. 180, #214) ----------------------------------------------
#
# A defence rather than a conditional effect, and 0032's document sweep is what separated
# them: the entry says "has **Immunity** to all damage unless…", and what it modifies is the
# damage itself rather than some other effect keyed off it.

WALL = Defences(damage_threshold=10)


def test_the_documents_own_worked_example_for_a_threshold() -> None:
    """p. 180, both halves of it: "if an object has a damage threshold of 10, the object
    takes no damage if 9 damage is dealt to it… If the same object is dealt 11 damage, it
    takes all of that damage."

    Note the second half. Below the threshold nothing lands; at or above it, the **whole**
    instance lands — the threshold is a gate, never a reduction, so 11 does not become 1.
    """
    assert after_defences(9, FIRE, WALL).amount == 0
    assert after_defences(11, FIRE, WALL).amount == 11


def test_an_instance_exactly_equal_to_the_threshold_gets_through() -> None:
    """The boundary the worked example cannot settle, because it uses 9 against 10 where
    both readings agree. Two operative sentences settle it and they agree with each other:
    "**equal to or greater than** its damage threshold", and damage "that fails to **meet or
    exceed**" it is superficial. Only the example's gloss abbreviates to "fails to exceed".
    """
    assert after_defences(10, FIRE, WALL).amount == 10
    assert after_defences(9, FIRE, WALL).amount == 0


def test_the_threshold_is_asked_of_the_instance_and_resistance_acts_after_it() -> None:
    """#214's whole question, and the case where the two readings disagree.

    p. 17's Order of Application names three steps and the threshold is not one of them, so
    its position is derived from p. 180 calling it Immunity rather than read off an ordering
    the document does not give. Comparing the *halved* figure instead would make this
    creature Immune and deal nothing.
    """
    resistant = Defences(damage_threshold=10, resistances=frozenset({FIRE}))
    outcome = after_defences(12, FIRE, resistant)

    assert outcome.amount == 6, "12 meets the threshold, then p. 17 halves it"
    assert "damage threshold" not in outcome.derivation(), "the gate reduced nothing"


def test_an_instance_below_the_threshold_is_immune_even_with_vulnerability() -> None:
    """The mirror, and the reason 0030 clause 1 must not be reached here (0031 clause 2).

    Resolving "away from invention" would compare after Resistance — less damage — but
    before Vulnerability, also less damage. That is not one rule read two ways; it is a
    thumb on the scale, picked per case to minimise a number. The rule is the same in both
    directions: the gate is asked of the instance.
    """
    fragile = Defences(damage_threshold=10, vulnerabilities=frozenset({FIRE}))
    assert after_defences(6, FIRE, fragile).amount == 0, "6 never meets 10"
    assert after_defences(10, FIRE, fragile).amount == 20, "10 meets it, then doubles"


def test_the_threshold_short_circuits_as_immunity_and_says_so() -> None:
    """R5. The derivation names the rule that produced the zero, because a bare 0 cannot be
    told from Immunity to the type, or from a roll of nothing."""
    outcome = after_defences(9, FIRE, WALL)
    assert outcome.amount == 0
    assert "Immunity" in outcome.derivation()
    assert "damage threshold of 10" in outcome.derivation()


def test_a_creature_with_no_threshold_is_unaffected_by_the_gate() -> None:
    """Almost everything. `None` is not a threshold of 0 — every instance meets 0, so a
    zero would be a threshold that does nothing rather than the absence of one."""
    assert Defences().damage_threshold is None
    assert Defences().meets_threshold(0)
    assert Defences(damage_threshold=0).meets_threshold(0)
    assert after_defences(3, FIRE, Defences()).amount == 3


def test_a_negative_threshold_is_refused() -> None:
    """p. 180 compares an instance against it, and no instance is negative."""
    with pytest.raises(ValueError, match="not a quantity of damage"):
        Defences(damage_threshold=-1)


def test_the_threshold_reaches_the_state_transition_too() -> None:
    """The gate has to act where defences act, or the death save for "any damage" and
    Massive Damage's remainder would both be computed from a number it had not zeroed."""
    state = EncounterState.new([combatant(damage_threshold=10)])
    assert state.with_damage("hero", 9, damage_type=FIRE).combatant("hero").hit_points == 40
    assert state.with_damage("hero", 11, damage_type=FIRE).combatant("hero").hit_points == 29


# --- Provenance and shape -------------------------------------------------------------


def test_there_are_thirteen_damage_types() -> None:
    """p. 180's table. A closed set: "Damage types have no rules of their own, but other
    rules, such as Resistance, rely on the types."
    """
    assert len(DamageType) == 13
    assert {t.value for t in DamageType} >= {"fire", "necrotic", "bludgeoning", "psychic"}


def test_negative_damage_is_refused() -> None:
    with pytest.raises(ValueError, match="not negative"):
        after_defences(-1, FIRE, Defences())


def test_the_damage_rules_carry_a_verified_citation() -> None:
    assert DAMAGE_VERIFICATION.state is VerificationState.VERIFIED
    assert DAMAGE_VERIFICATION.reference is not None
    for cited in ("p. 17", "p. 180", "p. 183", "p. 187", "p. 191"):
        assert cited in DAMAGE_VERIFICATION.reference


# --- p. 179: damage compels a Concentration save, recorded but never rolled here --------


def caster(
    *, hp: int = 40, spell: str | None = "hold-person", **defence_kwargs: object
) -> Combatant:
    held = Concentration() if spell is None else Concentration().begin(spell)
    return Combatant(
        id="mage",
        name="Mage",
        hit_points=hp,
        max_hit_points=40,
        armour_class=12,
        abilities={"con": 14},
        proficiency_bonus=2,
        is_player_character=True,
        concentration=held,
        defences=Defences(**defence_kwargs),  # type: ignore[arg-type]
    )


def _owed(state: EncounterState) -> list[tuple[str, str, int]]:
    """Each debt as (who owes it, which rule compelled it, the DC) — 0048's shape.

    The queue held a damage amount until the generalisation; the DC and its derivation are
    now computed where the trigger fires, so what a test reads is the number the save will
    actually be rolled against. The amount survives inside `dc_basis`, which is asserted
    separately where it is the point.
    """
    return [(d.combatant_id, d.rule_id, d.dc) for d in state.forced_saves_owed]


def test_damage_to_a_concentrating_creature_records_a_save_owed() -> None:
    state = EncounterState.new([caster()]).with_damage("mage", 12)
    assert _owed(state) == [("mage", CONCENTRATION_RULE_ID, 10)], "10 or half of 12 (p. 179)"
    assert "12 damage taken" in state.forced_saves_owed[0].dc_basis


def test_nothing_is_owed_by_a_creature_that_is_not_concentrating() -> None:
    state = EncounterState.new([caster(spell=None)]).with_damage("mage", 12)
    assert state.forced_saves_owed == ()


def test_two_instances_in_one_turn_owe_two_saves() -> None:
    """0036 clause 3, and the reason the debt is not `discharged`.

    p. 179 compels a save on *every* instance of damage. A Multiattack landing twice owes
    two. `discharged` is keyed `(actor_id, rule_id)` and cleared per turn, so reusing it
    would record the first and silently swallow the second — a compelled save that never
    happens, which leaves no trace in play because the spell simply stays up.

    The amounts are kept apart rather than summed: each DC derives from its own instance,
    and 8 then 8 is two DC 10 saves while 16 at once is one DC 10 save. Summing would also
    invent a DC of 18 that no single blow justified.
    """
    state = EncounterState.new([caster()]).with_damage("mage", 8).with_damage("mage", 30)

    assert _owed(state) == [
        ("mage", CONCENTRATION_RULE_ID, 10),  # 10 or half of 8
        ("mage", CONCENTRATION_RULE_ID, 15),  # 10 or half of 30
    ]


def test_damage_fully_absorbed_by_immunity_owes_nothing() -> None:
    """0036 clause 5. p. 179 says "the damage taken", and an Immune creature takes none.

    Recording before defences would compel a save — one that can *fail* — for a blow that
    never landed.
    """
    state = EncounterState.new([caster(immunities=frozenset({FIRE}))]).with_damage(
        "mage", 20, damage_type=FIRE
    )

    assert state.combatant("mage").hit_points == 40, "the immunity applied"
    assert state.forced_saves_owed == ()


def test_resistance_halves_the_dc_the_save_will_use() -> None:
    """The debt carries damage *taken*, so Resistance moves the DC as well as the wound."""
    state = EncounterState.new([caster(resistances=frozenset({FIRE}))]).with_damage(
        "mage", 30, damage_type=FIRE
    )

    assert _owed(state) == [("mage", CONCENTRATION_RULE_ID, 10)], "half of 15, not of 30"
    assert "15 damage taken" in state.forced_saves_owed[0].dc_basis


def test_a_debt_survives_the_turn_advancing() -> None:
    """**Not** cleared by `advanced_turn`, unlike `discharged` one field above it.

    This is the case reflex gets wrong, because every neighbouring structure resets there
    and the comment beside `discharged` says obligations are "owed once per turn". A
    Concentration debt is incurred by whoever took the damage — usually not the creature
    whose turn is ending — so clearing it on advance would discard the caster's save
    because the *attacker's* turn finished.
    """
    state = (
        EncounterState.new([caster(), combatant()])
        .with_initiative({"mage": 20, "hero": 5})
        .with_damage("mage", 12)
    )
    assert state.forced_saves_owed, "precondition: a debt exists"

    advanced = state.advanced_turn()

    assert advanced.discharged == frozenset(), "the once-per-turn set does clear"
    assert _owed(advanced) == [("mage", CONCENTRATION_RULE_ID, 10)], (
        "the per-instance debt does not"
    )


def test_recording_a_debt_produces_no_result_of_its_own() -> None:
    """0036 clause 2: detection here, production in the loop.

    `with_damage` appends a debt and nothing else — no roll, no Ruling, no ledger entry.
    Asserted because the tempting shortcut is to resolve the save where the damage lands,
    which is 0023 clause 5's literal shape and would put a produced outcome in `core.state`
    (R1).
    """
    state = EncounterState.new([caster()]).with_damage("mage", 12)
    debt = state.forced_saves_owed[0]

    assert isinstance(debt, ForcedSave)
    assert not hasattr(debt, "rolled"), "a debt is what is owed, never what came of it"
    assert state.combatant("mage").concentration.active, (
        "the Concentration is untouched — whether it survives is the save's to decide"
    )


def test_a_debt_with_no_dc_is_refused_rather_than_stored() -> None:
    """0048 moved the validation with the field. The queue used to refuse a zero *amount*,
    because 0 damage breaks no Concentration; it now refuses a DC no save could be rolled
    against, which is the same refusal one step later and covers every rule rather than one.
    """
    with pytest.raises(ValueError, match="positive target number"):
        ForcedSave(
            combatant_id="mage",
            rule_id=CONCENTRATION_RULE_ID,
            ability="con",
            dc=0,
            dc_basis="a DC nothing could derive",
            label="an impossible save",
        )


def test_a_debt_with_no_derivation_is_refused() -> None:
    """R30. A target number the reader cannot check is what the basis exists to prevent, and
    the old queue could not express one because its DC was computed from a carried amount."""
    with pytest.raises(ValueError, match="derivation of its DC"):
        ForcedSave(
            combatant_id="mage",
            rule_id=CONCENTRATION_RULE_ID,
            ability="con",
            dc=12,
            dc_basis="",
            label="a save with an unexplained DC",
        )
