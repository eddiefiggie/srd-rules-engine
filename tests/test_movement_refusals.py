"""A move a rule forbids is refused where the move is made (#350, 0056).

p. 182, *Frightened*: "You can't **willingly** move closer to the source of fear."

The clause was disclosed as unenforceable, and the stated reason was wrong twice over — it said
movement had no notion of a direction relative to a creature. "Closer" needs no direction at
all, only two distances; and what was actually missing was a **refusal**.
"""

from __future__ import annotations

import re

import pytest

from srd_rules_engine.core import Combatant, Condition, EncounterState
from srd_rules_engine.core.conditions import EFFECTS, Conditions
from srd_rules_engine.core.position import Position, Speeds

ORIGIN = Position(0, 0, 0)


def creature(cid: str, name: str, **overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": cid,
        "name": name,
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 12,
        "abilities": {"str": 12, "dex": 12, "con": 12},
        "proficiency_bonus": 2,
        "position": ORIGIN,
        "speeds": Speeds(walk=60),
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


#: Thirty feet from the origin, so a step in is unambiguously closer and a step out is not.
AWAY = Position(30, 0, 0)


def afraid_of(source_id: str, *, at: Position = AWAY) -> Combatant:
    return creature(
        "pc",
        "Pc",
        position=at,
        conditions=Conditions(
            applied=frozenset({Condition.FRIGHTENED}),
            sources={Condition.FRIGHTENED: frozenset({source_id})},
        ),
    )


def encounter(*combatants: Combatant) -> EncounterState:
    people = combatants or (afraid_of("ogre"), creature("ogre", "Ogre"))
    return EncounterState.new(list(people)).with_initiative(
        {c.id: 20 - i for i, c in enumerate(people)}
    )


# --- The rule ---------------------------------------------------------------------------------


def test_a_frightened_creature_may_not_move_closer_to_what_it_fears() -> None:
    """The ogre is at the origin and the creature 30 feet away. A step to 25 feet closes on
    it, which p. 182 forbids."""
    with pytest.raises(ValueError, match="Frightened of Ogre"):
        encounter().with_movement("pc", Position(25, 0, 0))


def test_it_may_move_further_away() -> None:
    """The negative case, and the one that keeps the refusal from being a ban on movement."""
    after = encounter().with_movement("pc", Position(50, 0, 0))
    assert after.combatant("pc").position == Position(50, 0, 0)


def test_it_may_move_sideways_at_the_same_distance() -> None:
    """p. 182 forbids *closer*, not *toward*. A creature circling at a constant distance is
    doing something the sentence permits, and a refusal keyed on direction would stop it."""
    circling = afraid_of("ogre", at=Position(30, 0, 0))
    after = encounter(circling, creature("ogre", "Ogre")).with_movement("pc", Position(0, 30, 0))
    assert after.combatant("pc").position == Position(0, 30, 0)


def test_a_creature_frightened_of_two_things_is_refused_by_either() -> None:
    """p. 179: a condition does not stack, so one Frightened condition holds two sources
    (#192). A move away from one and toward the other is still toward one."""
    both = creature(
        "pc",
        "Pc",
        position=Position(30, 0, 0),
        conditions=Conditions(
            applied=frozenset({Condition.FRIGHTENED}),
            sources={Condition.FRIGHTENED: frozenset({"ogre", "wolf"})},
        ),
    )
    state = encounter(
        both, creature("ogre", "Ogre"), creature("wolf", "Wolf", position=Position(60, 0, 0))
    )
    with pytest.raises(ValueError, match="Frightened of Wolf"):
        state.with_movement("pc", Position(40, 0, 0))


def test_a_creature_that_is_not_frightened_moves_where_it_likes() -> None:
    plain = creature("pc", "Pc", position=Position(30, 0, 0))
    after = encounter(plain, creature("ogre", "Ogre")).with_movement("pc", ORIGIN)
    assert after.combatant("pc").position == ORIGIN


# --- Where the refusal declines to refuse -------------------------------------------------------


def test_a_source_that_has_left_the_encounter_forbids_nothing() -> None:
    """The distance cannot be measured, so the engine has not found the move illegal — it has
    found nothing. Refusing on an unmeasurable distance would forbid what the rules may permit,
    which is the direction `_within` already takes at the read surface."""
    gone = EncounterState.new([afraid_of("ogre")]).with_initiative({"pc": 20})
    assert gone.with_movement("pc", Position(25, 0, 0)).combatant("pc").position == Position(
        25, 0, 0
    )


def test_a_source_nobody_placed_forbids_nothing() -> None:
    unplaced = creature("ogre", "Ogre", position=None)
    state = encounter(afraid_of("ogre"), unplaced)
    assert state.with_movement("pc", Position(25, 0, 0)).combatant("pc").position == Position(
        25, 0, 0
    )


def test_a_source_nobody_recorded_forbids_nothing() -> None:
    """A Frightened condition applied without a source — the condition is held and the clause
    has nothing to measure against."""
    sourceless = creature(
        "pc",
        "Pc",
        position=Position(30, 0, 0),
        conditions=Conditions(applied=frozenset({Condition.FRIGHTENED})),
    )
    state = encounter(sourceless, creature("ogre", "Ogre"))
    assert state.with_movement("pc", Position(25, 0, 0)).combatant("pc").position == Position(
        25, 0, 0
    )


# --- The word the rule turns on -----------------------------------------------------------------


def test_a_push_toward_what_it_fears_is_not_refused() -> None:
    """**"Willingly."** p. 182 forbids a creature moving itself closer; it says nothing about a
    creature being *thrown* closer, and a shove is not something the target does.

    This is why the check lives in `with_movement` and not in `with_forced_movement`, and it is
    the one word that decides which of the two.
    """
    state = encounter()
    after = state.with_forced_movement("pc", Position(5, 0, 0))
    assert after.combatant("pc").position == Position(5, 0, 0)


# --- The disclosure, retired against the rule ------------------------------------------------


def test_the_retired_fear_disclosure_is_enforced_now() -> None:
    """A disclosure comes off in the change that builds its rule, and the two are asserted
    together — the pairing AGENTS.md asks for, and the one `tests/test_disclosures_are_pinned.py`
    says no machine can make on its own.

    Frightened now discloses **nothing**: `line-of-sight-qualifier` left in #192 and this one in
    #350, so the condition is fully enforced.
    """
    assert EFFECTS[Condition.FRIGHTENED].unenforced_clauses == ()
    with pytest.raises(ValueError, match=re.escape("p. 182")):
        encounter().with_movement("pc", Position(25, 0, 0))
