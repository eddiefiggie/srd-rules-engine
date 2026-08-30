"""p. 188's six categories, and p. 178's table read at one (0051).

Every assertion here is proved by corrupting the behaviour it guards, because
`prove_against_base.sh` can only report that this module is new — a collection error against
the base tree arrives whether the file holds one real assertion or twenty.

The numbers are transcribed from the document and re-checked by
`scripts/verify_d20_rules.py`, which matches each clause against the printed page. What is
asserted here is that the engine reads them the way the sentences say.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core import Combatant, EncounterState, read
from srd_rules_engine.core.equipment import Carriage, Carried, Item
from srd_rules_engine.core.read_surface import CARRYING_CAPACITY_SPEED_CAP
from srd_rules_engine.core.size import (
    CARRY_MULTIPLIER,
    DRAG_LIFT_PUSH_MULTIPLIER,
    Size,
    carrying_capacity,
    one_size_larger_for_carrying,
)


def creature(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 13,
        "abilities": {"str": 15, "dex": 12, "con": 12},
        "proficiency_bonus": 2,
        "is_player_character": True,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(actor: Combatant) -> EncounterState:
    return EncounterState.new([actor]).with_initiative({"pc": 10})


# --- p. 178's table, row by row -------------------------------------------------------------


#: The printed table, as (size, Carry multiplier, Drag/Lift/Push multiplier). Transcribed from
#: p. 178 rather than computed, so a wrong entry here is visible beside the document.
PRINTED_TABLE = (
    (Size.TINY, 7.5, 15.0),
    (Size.SMALL, 15.0, 30.0),
    (Size.MEDIUM, 15.0, 30.0),
    (Size.LARGE, 30.0, 60.0),
    (Size.HUGE, 60.0, 120.0),
    (Size.GARGANTUAN, 120.0, 240.0),
)


@pytest.mark.parametrize(("size", "carry", "drag"), PRINTED_TABLE)
def test_each_printed_row_is_the_row_the_engine_reads(
    size: Size, carry: float, drag: float
) -> None:
    """p. 178, at a Strength score of 1 so the multiplier is the result."""
    capacity = carrying_capacity(size, 1)
    assert capacity.carry == pytest.approx(carry)
    assert capacity.drag_lift_push == pytest.approx(drag)


def test_the_multiplier_tables_cover_every_category() -> None:
    """A seventh size added to the enum and forgotten here would raise `KeyError` in the middle
    of a ruling. Asserted over `Size` rather than over the tables' own keys, which would be
    true by construction."""
    assert set(CARRY_MULTIPLIER) == set(Size)
    assert set(DRAG_LIFT_PUSH_MULTIPLIER) == set(Size)


def test_the_table_is_keyed_on_the_strength_score_and_not_the_modifier() -> None:
    """p. 178: "Your size and Strength **score** determine the maximum weight in pounds that
    you can carry."

    The arithmetic an implementation working from memory gets wrong. A Strength of 15 is a
    +2 modifier, so the two readings differ by a factor of seven and both produce a plausible
    number — 225 lb and 30 lb are each a believable load for a person.
    """
    assert carrying_capacity(Size.MEDIUM, 15).carry == pytest.approx(225.0)
    modifier = (15 - 10) // 2
    assert carrying_capacity(Size.MEDIUM, modifier).carry == pytest.approx(30.0)
    assert (
        carrying_capacity(Size.MEDIUM, 15).carry != carrying_capacity(Size.MEDIUM, modifier).carry
    )


def test_a_tiny_creatures_capacity_keeps_its_half_pound() -> None:
    """p. 178 prints the Strength score times 7.5 for Tiny, which is the one row that does not
    land on a whole number. An integer pound would round a bound the document states exactly."""
    assert carrying_capacity(Size.TINY, 11).carry == pytest.approx(82.5)


def test_drag_is_not_derived_from_carry() -> None:
    """It happens to be twice Carry in all six rows and the document states a table, not that
    relation. Both columns are transcribed, so a revision that broke the doubling would be a
    two-line change here rather than a silently wrong second column."""
    for size, carry, drag in PRINTED_TABLE:
        assert DRAG_LIFT_PUSH_MULTIPLIER[size] == pytest.approx(drag)
        assert CARRY_MULTIPLIER[size] == pytest.approx(carry)


# --- The ordering, and the step that is not arithmetic ---------------------------------------


def test_the_categories_are_ordered_smallest_to_largest() -> None:
    """p. 14 lists them "from smallest (Tiny) to largest (Gargantuan)"."""
    ranks = [size.rank for size, _, _ in PRINTED_TABLE]
    assert ranks == sorted(ranks)
    assert Size.TINY.rank == 0
    assert Size.GARGANTUAN.rank == len(PRINTED_TABLE) - 1


def test_categories_above_is_signed() -> None:
    """One number answers all five of the document's size comparisons, which ask in both
    directions — "no more than one size larger" (p. 190) and "at least one size larger"
    (p. 15)."""
    assert Size.LARGE.categories_above(Size.MEDIUM) == 1
    assert Size.MEDIUM.categories_above(Size.LARGE) == -1
    assert Size.MEDIUM.categories_above(Size.MEDIUM) == 0
    assert Size.GARGANTUAN.categories_above(Size.TINY) == 5


def test_counting_as_one_size_larger_gains_a_small_creature_nothing() -> None:
    """The case that makes p. 178 a table and not a doubling.

    p. 178 prints **Small/Medium as one row**, so p. 86's Powerful Build — "you count as one
    size larger when determining your carrying capacity" — moves a Small creature to Medium
    and finds the identical multipliers. An implementation that doubled per step would grant
    it 2x the capacity the document gives, and the result would look entirely reasonable.
    """
    assert one_size_larger_for_carrying(Size.SMALL) is Size.MEDIUM
    assert carrying_capacity(Size.SMALL, 14).carry == carrying_capacity(Size.MEDIUM, 14).carry


def test_counting_as_one_size_larger_does_gain_every_other_category() -> None:
    """The negative case for the assertion above: Small is the exception, not the rule. Without
    this, a `one_size_larger_for_carrying` that returned its argument unchanged would pass."""
    for smaller in (Size.TINY, Size.MEDIUM, Size.LARGE, Size.HUGE):
        larger = one_size_larger_for_carrying(smaller)
        assert larger.rank == smaller.rank + 1
        assert carrying_capacity(larger, 14).carry > carrying_capacity(smaller, 14).carry


def test_gargantuan_has_nothing_above_it_and_stays_where_it_is() -> None:
    """p. 188 names six categories. Inventing a seventh row for p. 86's trait would be the
    engine deciding a rule value; finding no larger row is the reading that cannot."""
    assert one_size_larger_for_carrying(Size.GARGANTUAN) is Size.GARGANTUAN


# --- A size is stated, or it is unknown ------------------------------------------------------


def test_a_creature_nobody_sized_has_no_size_and_no_capacity() -> None:
    """R31. p. 14 sources a size from a species or a stat block and this repository ships
    neither, so Medium would be an inferred rule value — the shape `Combatant.hands` refuses
    for the same reason."""
    unsized = creature()
    assert unsized.size is None
    assert unsized.carrying_size is None
    assert unsized.carrying_capacity is None
    assert unsized.over_carrying_capacity is None, "a refusal, not a verdict of False"


def test_the_refusal_is_not_a_capacity_of_zero() -> None:
    """`None` and 0 would be told apart by nothing at a call site that only checked falsity,
    and they are opposite claims: nobody said, against carries nothing at all."""
    laden = creature(equipment=(Carried(Item(id="fixture:anvil", weight=500.0), Carriage.STOWED),))
    assert laden.carried_weight == pytest.approx(500.0)
    assert laden.over_carrying_capacity is None, "500 lb over an unstated bound is still unstated"


def test_a_stated_size_answers_the_question() -> None:
    sized = replace(creature(), size=Size.MEDIUM)
    capacity = sized.carrying_capacity
    assert capacity is not None
    assert capacity.carry == pytest.approx(225.0), "Strength 15 at Medium (p. 178)"
    assert capacity.drag_lift_push == pytest.approx(450.0)
    assert sized.over_carrying_capacity is False


def test_the_verdict_turns_on_the_carry_column_not_the_drag_column() -> None:
    """p. 178's Speed sentence names "the maximum weight you can **carry**", so a load between
    the two columns is already in excess. Reading the larger column would put a creature at
    300 lb — over its 225 lb carry bound — under the limit instead of over it."""
    heavy = replace(
        creature(),
        size=Size.MEDIUM,
        equipment=(Carried(Item(id="fixture:hoard", weight=300.0), Carriage.STOWED),),
    )
    capacity = heavy.carrying_capacity
    assert capacity is not None
    assert capacity.carry < 300.0 < capacity.drag_lift_push
    assert heavy.over_carrying_capacity is True


def test_the_trait_is_scoped_to_carrying_and_leaves_the_creatures_own_size_alone() -> None:
    """p. 86 and p. 357 both say "for ... carrying capacity". A trait that changed `size`
    itself would silently reach p. 190's Grapple, where no rule grants it."""
    goliath = replace(creature(), size=Size.MEDIUM, carries_as_one_size_larger=True)
    assert goliath.size is Size.MEDIUM, "still Medium to every other rule"
    assert goliath.carrying_size is Size.LARGE
    capacity = goliath.carrying_capacity
    assert capacity is not None
    assert capacity.carry == pytest.approx(450.0), "Strength 15 at the Large row"


def test_the_derivation_names_the_row_that_was_used() -> None:
    """R30. The result alone cannot show the step that matters — a Medium creature's numbers
    being a Large row's is invisible in the number 450."""
    goliath = replace(creature(), size=Size.MEDIUM, carries_as_one_size_larger=True)
    capacity = goliath.carrying_capacity
    assert capacity is not None
    assert "large" in capacity.derivation()
    assert "p. 178" in capacity.derivation()


# --- The read surface ------------------------------------------------------------------------


def test_the_surface_reports_the_size_and_the_bound() -> None:
    situation = read(encounter(replace(creature(), size=Size.LARGE)), "pc").situation
    assert situation is not None
    assert situation.size is Size.LARGE
    assert situation.carrying_capacity is not None
    assert situation.carrying_capacity.carry == pytest.approx(450.0)
    assert situation.over_carrying_capacity is False


def test_the_surface_reports_an_unknown_size_as_unknown() -> None:
    """Not Medium. An agent told a size the engine invented cannot tell it from one a ruleset
    stated, which is the whole of what R31 protects."""
    situation = read(encounter(creature()), "pc").situation
    assert situation is not None
    assert situation.size is None
    assert situation.carrying_capacity is None


def test_the_unapplied_speed_cap_is_disclosed_only_when_it_would_bite() -> None:
    """R32, and the timing `SIGHT_QUALIFIER` uses. p. 178's "your Speed can be no more than 5
    feet" is not applied (#336), so a creature over its bound is told the rule went
    unenforced rather than left to infer it from a Speed that did not change."""
    under = read(encounter(replace(creature(), size=Size.MEDIUM)), "pc").situation
    assert under is not None
    assert CARRYING_CAPACITY_SPEED_CAP not in under.unenforced_clauses

    over = replace(
        creature(),
        size=Size.MEDIUM,
        equipment=(Carried(Item(id="fixture:hoard", weight=300.0), Carriage.STOWED),),
    )
    situation = read(encounter(over), "pc").situation
    assert situation is not None
    assert CARRYING_CAPACITY_SPEED_CAP in situation.unenforced_clauses
    assert situation.speed == over.effective_speeds.walk, "disclosed, and genuinely not applied"


def test_an_unsized_creature_discloses_nothing_about_a_cap_it_cannot_reach() -> None:
    """The disclosure names a rule that went unenforced. A creature whose bound is unknown has
    no unenforced cap — it has no cap — and saying otherwise would report a gap that is not
    this one."""
    situation = read(encounter(creature()), "pc").situation
    assert situation is not None
    assert CARRYING_CAPACITY_SPEED_CAP not in situation.unenforced_clauses
