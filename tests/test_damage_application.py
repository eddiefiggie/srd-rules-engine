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
from srd_rules_engine.core.state import Combatant, EncounterState

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
