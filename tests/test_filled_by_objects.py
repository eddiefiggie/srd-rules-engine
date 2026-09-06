"""p. 185's second clause: a space "completely filled by objects" (#459, 0092).

> **Occupied Space** (p. 185): A space is occupied if a creature is in it or if it is
> completely filled by objects.
> **Unoccupied Space** (p. 191): A space is unoccupied if no creatures are in it and it isn't
> completely filled by objects.

[0084](../docs/decisions/0084-a-space-is-a-control-area-not-a-volume.md) built the creature
half and left this one unasked, because the engine had no object that fills a space — an
`Obstruction` is a barrier, and a wall giving Total Cover is a different fact from a space a
body cannot stand in. The clause is `Obstruction.fills_space` now: **stated by the placer**,
as a barrier's degree of cover and whether it blocks sight are stated, because "completely"
is a judgement the document hands to a person. `filled_by_objects` reads it, `is_unoccupied`
reads both halves, and p. 190's teleport diverts on it under the word the sentence uses.

The module is new, so its collection error against the base tree is indivisible; every
assertion here was proved by corrupting the behaviour it guards and watching this test go
red, except the two marked as "nothing changed" guards.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core.obstructions import Cover, Obstruction
from srd_rules_engine.core.position import Position, Speeds
from srd_rules_engine.core.size import Size
from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}

#: A five-foot cube of crates, stacked to the ceiling — the placer says so.
CRATES = Obstruction(Position(8, -2, 0), Position(12, 2, 5), fills_space=True)
#: The same cube as a wall: Total Cover, and nobody has said it fills the space.
WALL = Obstruction(Position(8, -2, 0), Position(12, 2, 5), degree=Cover.TOTAL)
#: A heap of loose sacks that fills the space and covers nobody.
HEAP = Obstruction(Position(8, -2, 0), Position(12, 2, 5), degree=Cover.NONE, fills_space=True)

INSIDE = Position(10, 0, 0)
ON_A_FACE = Position(12, 0, 0)
JUST_OUTSIDE = Position(13, 0, 0)


def _creature(cid: str, x: int) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        position=Position(x, 0, 0),
        size=Size.MEDIUM,
        speeds=Speeds(walk=30),
    )


def _scene(*boxes: Obstruction) -> EncounterState:
    state = EncounterState.new([_creature("pc", 0)]).with_initiative({"pc": 20})
    return replace(state, obstructions=boxes)


# --- The read -----------------------------------------------------------------------------


def test_a_space_the_placer_said_is_full_is_occupied() -> None:
    """Both entries, from both sides of the box's face. `Box.contains` includes its faces,
    so the face is filled and the first foot beyond it is not."""
    crated = _scene(CRATES)

    assert crated.filled_by_objects(INSIDE)
    assert crated.filled_by_objects(ON_A_FACE)
    assert not crated.filled_by_objects(JUST_OUTSIDE)

    assert not crated.is_unoccupied(INSIDE)
    assert crated.is_unoccupied(JUST_OUTSIDE)


def test_filling_is_stated_and_never_read_off_cover() -> None:
    """The discriminating pair. A Total Cover wall nobody said is full leaves the space
    unoccupied — 0084 clause 9's direction, kept for the unstated case — and a heap that
    covers nobody fills it, because its placer said so. Inferring either from the other would
    be the engine measuring "completely", which the document gives it no way to do."""
    assert _scene(WALL).is_unoccupied(INSIDE), "a barrier is not an occupant"
    assert not _scene(HEAP).is_unoccupied(INSIDE), "the placer's word is the fact"


def test_the_default_is_a_barrier_and_not_an_occupant() -> None:
    """Every obstruction placed before this field existed meant a barrier, and still does."""
    assert Obstruction(Position(0, 0, 0), Position(5, 5, 5)).fills_space is False


def test_occupants_of_still_names_creatures_only() -> None:
    """**A deliberate "nothing changed" guard.** `occupants_of` answers the creature half by
    name, because every consumer says which half it means — p. 14's "another creature" and
    p. 190's "another creature" both — so crates are not among its occupants."""
    assert _scene(CRATES).occupants_of(INSIDE) == ()


# --- p. 190's teleport --------------------------------------------------------------------


def test_a_teleport_is_diverted_from_a_filled_space_and_says_why() -> None:
    """ "If the destination space of your teleportation is occupied by another creature or
    blocked by a solid obstacle, you instead appear in the nearest unoccupied space." A
    filled space is occupied, so the destination is refused under that word and every
    landing offered is outside the crates."""
    crated = _scene(CRATES)

    landings = crated.teleport_destinations("pc", INSIDE)
    assert INSIDE not in landings
    assert landings and all(not CRATES.contains(p) for p in landings)
    with pytest.raises(ValueError, match="completely filled by objects"):
        crated.with_teleport("pc", INSIDE)


def test_a_heap_that_covers_nobody_still_diverts() -> None:
    """The case that separates the two clauses of p. 190: smoke does not divert a teleport
    (it gives no cover, so it is not a solid obstacle) and a heap that gives no cover does,
    because it fills the space. Cover is one question and occupancy another."""
    assert INSIDE not in _scene(HEAP).teleport_destinations("pc", INSIDE)


def test_the_two_clauses_of_p190_are_named_apart() -> None:
    """The reason a refusal gives is the clause it fired on: a wall is "blocked by a solid
    obstacle" and crates are "occupied", which is the word p. 185 uses of them."""
    with pytest.raises(ValueError, match="blocked by a solid obstacle"):
        _scene(WALL).with_teleport("pc", INSIDE)
    with pytest.raises(ValueError, match="occupied, completely filled by objects"):
        _scene(CRATES).with_teleport("pc", INSIDE)


# --- p. 14's move --------------------------------------------------------------------------


def test_ending_a_move_in_a_filled_space_is_not_refused_by_p14() -> None:
    """**A deliberate "nothing changed" guard.** p. 14 says "You can't willingly end a move in
    a space occupied by another **creature**", and names no object; extending its refusal to
    crates would be a rule the document does not state (R31). What a walk does about a wall
    in its way is a separate question `with_movement` has never asked, and 0092 leaves it
    where it was rather than answering half of it here."""
    moved = _scene(CRATES).with_movement("pc", INSIDE)
    assert moved.combatant("pc").position == INSIDE
