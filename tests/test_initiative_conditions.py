"""p. 184's two Initiative clauses, which reached no roll (#359, 0059).

> **Incapacitated.** You have Disadvantage on Initiative.
> **Invisible.** You have Advantage on Initiative.

`ConditionEffects.initiative` held both, transcribed from the glossary, and
`core.combat.initiative_order` rolled one d20 per combatant and consulted nothing else.

The fix is a **seed-layout** change rather than a modifier added to a roll, which is why it was
disclosed by 0058 and built separately.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core import Combatant, Condition, EncounterState
from srd_rules_engine.core.combat import DICE_PER_COMBATANT, INITIATIVE_DIE, initiative_order
from srd_rules_engine.core.conditions import EFFECTS, Conditions
from srd_rules_engine.core.d20 import INITIATIVE_BAND, Advantage, roll

#: Two seeds, because one cannot discriminate both directions. A pair is `(first, second)`
#: and the engine takes `first` when nothing modifies the roll — so Advantage is only
#: distinguishable when `second > first`, and Disadvantage only when `second < first`.
#:
#: Written out because a seed that fails to discriminate makes the test pass for the wrong
#: reason, which is what seed 7 did here: its pair is (11, 13), and `min` of that is 11, which
#: is exactly what a creature holding no condition at all would have rolled.
ASCENDING_SEED = 2
DESCENDING_SEED = 4
SEED = ASCENDING_SEED


def creature(cid: str, **overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 10,
        "max_hit_points": 10,
        "armour_class": 10,
        # Every modifier is zero, so a test naming a face is naming the die.
        "abilities": {"str": 10, "dex": 10, "con": 10},
        "proficiency_bonus": 2,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def holding(*conditions: Condition) -> Conditions:
    return Conditions(applied=frozenset(conditions))


def encounter(*people: Combatant) -> EncounterState:
    return EncounterState.new(list(people))


def faces_for(count: int, seed: int = SEED) -> tuple[int, ...]:
    return roll(seed, count=count, sides=INITIATIVE_DIE, offset=INITIATIVE_BAND.start)


# --- The layout -------------------------------------------------------------------------------


def test_two_dice_are_drawn_for_every_combatant() -> None:
    """Two always, not two for the creatures that need them.

    A per-creature count would make one combatant's seed offset depend on the **conditions** of
    the combatants before it — reproducible, and fragile in exactly the way #82 was, where a
    run walked out of its band and aliased onto another's dice.
    """
    assert DICE_PER_COMBATANT == 2
    rolled = initiative_order(encounter(creature("a"), creature("b")), seed=SEED)
    faces = faces_for(4)
    assert rolled["a"] == faces[0], "the first of its pair"
    assert rolled["b"] == faces[2], "and the second creature's pair starts at index 2"


def test_the_unused_die_is_still_drawn() -> None:
    """The consequence the uniform layout was chosen for: adding a condition to the *first*
    creature cannot move the *second* one's dice.

    **This one states a property rather than guarding an implementation**, and it is worth
    saying so. Under the layout above it is true by construction, and no single-line corruption
    violates it — the failure it describes needs a per-creature die count, which is a structural
    change rather than an edit. `test_two_dice_are_drawn_for_every_combatant` is what actually
    holds the layout, and this is what would fail if somebody replaced it with the fragile one.
    """
    plain = initiative_order(encounter(creature("a"), creature("b")), seed=SEED)
    afflicted = initiative_order(
        encounter(creature("a", conditions=holding(Condition.INVISIBLE)), creature("b")),
        seed=SEED,
    )
    assert afflicted["b"] == plain["b"], "the second creature's roll did not move"
    # And the first one's did, or the fixture would not be exercising the condition at all.
    assert afflicted["a"] != plain["a"]


def test_the_band_refuses_an_encounter_it_cannot_seed() -> None:
    """`roll` checks the run against its band (#82), so the ceiling is stated rather than
    aliased. Two dice each in a 256-slot band puts it at 128 combatants."""
    crowd = encounter(*(creature(f"c{n}") for n in range(129)))
    with pytest.raises(ValueError, match="outside the initiative band"):
        initiative_order(crowd, seed=SEED)

    assert initiative_order(encounter(*(creature(f"c{n}") for n in range(128))), seed=SEED), (
        "and 128 is fine"
    )


# --- The two clauses ---------------------------------------------------------------------------


def test_incapacitated_rolls_at_disadvantage() -> None:
    """p. 184. The lower of the pair — on a seed whose pair **descends**, so the lower is not
    also the first and the assertion can tell Disadvantage from no condition at all."""
    faces = faces_for(2, DESCENDING_SEED)
    assert min(faces) != faces[0], "or this cannot distinguish Disadvantage from nothing"

    rolled = initiative_order(
        encounter(creature("a", conditions=holding(Condition.INCAPACITATED))),
        seed=DESCENDING_SEED,
    )
    assert rolled["a"] == min(faces)


def test_invisible_rolls_at_advantage() -> None:
    """p. 184. The higher of the pair — on a seed whose pair **ascends**, for the same reason
    its twin above uses a descending one."""
    faces = faces_for(2)
    assert max(faces) != faces[0], "or this cannot distinguish Advantage from nothing"

    rolled = initiative_order(
        encounter(creature("a", conditions=holding(Condition.INVISIBLE))), seed=SEED
    )
    assert rolled["a"] == max(faces)


def test_holding_both_rolls_flat() -> None:
    """p. 8: sources on opposite sides cancel. The two clauses disagree, so a creature that is
    both Incapacitated and Invisible takes the first die like anybody else."""
    rolled = initiative_order(
        encounter(creature("a", conditions=holding(Condition.INCAPACITATED, Condition.INVISIBLE))),
        seed=SEED,
    )
    faces = faces_for(2)
    assert rolled["a"] == faces[0]
    assert min(faces) != max(faces), "and the pair differs, so flat is distinguishable"


def test_a_creature_with_neither_takes_the_first_die() -> None:
    rolled = initiative_order(encounter(creature("a")), seed=SEED)
    assert rolled["a"] == faces_for(2)[0]


def test_the_modifier_is_added_after_the_pick() -> None:
    """The die is chosen and then the ability modifier applies, not the other way round —
    which is only distinguishable because the two dice differ."""
    quick = initiative_order(
        encounter(creature("a", abilities={"dex": 16}, conditions=holding(Condition.INVISIBLE))),
        seed=SEED,
    )
    assert quick["a"] == max(faces_for(2)) + 3


def test_the_conditions_aggregate_answers_the_cancellation() -> None:
    """Through `_combine`, the same helper every other aggregate here uses, rather than a
    second copy of p. 8's rule."""
    assert holding(Condition.INCAPACITATED).initiative_advantage is Advantage.DISADVANTAGE
    assert holding(Condition.INVISIBLE).initiative_advantage is Advantage.ADVANTAGE
    assert (
        holding(Condition.INCAPACITATED, Condition.INVISIBLE).initiative_advantage is Advantage.NONE
    )
    assert holding().initiative_advantage is Advantage.NONE


# --- The disclosures, retired against the rules --------------------------------------------------


def test_the_retired_initiative_disclosures_are_enforced_now() -> None:
    """Both come off in the change that builds them, and both are asserted here.

    They were **two strings** rather than one — Incapacitated's is a Disadvantage and
    Invisible's an Advantage — because the pin refuses a repeated clause, and it was right to:
    a shared string would have made one removal look like both.
    """
    assert (
        "initiative-disadvantage-not-applied"
        not in EFFECTS[Condition.INCAPACITATED].unenforced_clauses
    )
    assert "initiative-advantage-not-applied" not in EFFECTS[Condition.INVISIBLE].unenforced_clauses

    slow = initiative_order(
        encounter(creature("a", conditions=holding(Condition.INCAPACITATED))),
        seed=DESCENDING_SEED,
    )
    quick = initiative_order(
        encounter(creature("a", conditions=holding(Condition.INVISIBLE))), seed=SEED
    )
    assert slow["a"] == min(faces_for(2, DESCENDING_SEED))
    assert quick["a"] == max(faces_for(2))
