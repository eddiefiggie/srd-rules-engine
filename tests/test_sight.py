"""The sight subsystem's structure, and the refusal where its rules should be (0025, #138).

Decision 0025 settled this design before any of it was built, because #138's shapes are one
mechanism read three ways: a sense decides what a light level means, obscurement is what
light resolves into, and some senses bypass the chain. What lands here is clauses 2, 3, 4
and 7 — light on the state, senses on the creature, visibility derived, and both reported
on the read surface.

**What does not land is the part that would have been invented.** Which light level a sense
converts into which other is a rule value nine times over, at nine printed pages, none of
them asserted anywhere in this repository (#150). So the tables are empty, the queries
refuse, and `test_no_row_may_be_added_while_the_pages_are_unread` is what stops a row
arriving from somebody's memory of a game — the failure `core.spellcasting` avoids by
shipping no slot table at all.

None of this resolves an effect shape. Coverage stays at 76 of 211, which is the README's
standing warning about reading that number as progress.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.inventory import load_inventory
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import situation
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.sight import (
    OBSCUREMENT_BY_LIGHT,
    SENSE_LIGHT_SHIFTS,
    SIGHT_VERIFICATION,
    Lighting,
    LightLevel,
    LitVolume,
    Obscurement,
    Sense,
    Senses,
    SightUnverified,
    can_see,
    obscurement_at,
)
from srd_rules_engine.core.state import Combatant, EncounterState

DARKVISION_60 = Senses(darkvision=60)


def _combatant(**kwargs: object) -> Combatant:
    base: dict[str, object] = {
        "id": "pc",
        "name": "Player",
        "hit_points": 10,
        "max_hit_points": 10,
        "armour_class": 14,
        "abilities": {"str": 10, "dex": 14, "con": 12, "int": 10, "wis": 12, "cha": 8},
        "proficiency_bonus": 2,
    }
    base.update(kwargs)
    return Combatant(**base)  # type: ignore[arg-type]


# --- Clause 5: the rules are absent, and absent loudly ----------------------------


def test_no_row_may_be_added_while_the_pages_are_unread() -> None:
    """The guard clause 5 exists for. R31: a rule value that reached the engine without
    being read off the document is indistinguishable from one that was."""
    assert SIGHT_VERIFICATION.state is VerificationState.UNVERIFIED
    assert not OBSCUREMENT_BY_LIGHT, "a row exists while #150 is open — where did it come from?"
    assert not SENSE_LIGHT_SHIFTS, "a row exists while #150 is open — where did it come from?"


def test_the_unverified_state_says_what_is_missing() -> None:
    """An exclusion with no reason is a silent drop wearing a label (R32)."""
    assert SIGHT_VERIFICATION.reason is not None
    assert "150" in SIGHT_VERIFICATION.reason


def test_asking_what_a_light_level_means_refuses() -> None:
    with pytest.raises(SightUnverified, match="has not read off the document"):
        obscurement_at(LightLevel.DARKNESS, senses=DARKVISION_60)


def test_asking_whether_a_creature_can_see_refuses() -> None:
    with pytest.raises(SightUnverified, match="has not read off the document"):
        can_see(DARKVISION_60, at_level=LightLevel.DIM, distance_feet=30)


# --- Clause 1: Telepathy is not part of this ---------------------------------------


def test_telepathy_is_not_a_sense_here() -> None:
    """It is filed as one in the inventory and does not participate in the chain (#149).
    `kind` is a filing label rather than a model (0019)."""
    assert "telepathy" not in {sense.value for sense in Sense}
    assert not hasattr(Senses(), "telepathy")


def test_the_inventory_still_reports_telepathy_as_unimplemented() -> None:
    """Leaving the subsystem is not the same as being done, and coverage must not say it is."""
    telepathy = next(s for s in load_inventory().shapes if s.id == "telepathy")
    assert not telepathy.implemented


def test_no_sight_shape_is_marked_implemented_by_this_structure() -> None:
    """Structure is not resolution. A shape counts when the engine can resolve it, and
    nothing here can resolve anything until #150."""
    unresolved = [s.id for s in load_inventory().shapes if s.kind in ("sense", "environment")]
    assert len(unresolved) == 10
    assert not any(
        s.implemented for s in load_inventory().shapes if s.kind in ("sense", "environment")
    )


# --- Clause 3: senses are per-creature state, shaped like Speeds --------------------


def test_no_sense_is_the_default() -> None:
    assert Senses().held == ()
    assert Senses().range_of(Sense.DARKVISION) is None


def test_absent_is_not_zero() -> None:
    """The distinction `Speeds` draws: a creature with no Darkvision and one whose
    Darkvision is zero are different creatures."""
    assert Senses().has(Sense.DARKVISION) is False
    assert Senses(darkvision=0).has(Sense.DARKVISION) is True
    assert Senses(darkvision=0).range_of(Sense.DARKVISION) == 0


def test_every_sense_is_reachable_by_its_enum_member() -> None:
    """A `range_of` that silently dropped a member would report a creature as sightless."""
    full = Senses(blindsight=10, darkvision=60, tremorsense=30, truesight=120)
    assert {sense: full.range_of(sense) for sense in Sense} == {
        Sense.BLINDSIGHT: 10,
        Sense.DARKVISION: 60,
        Sense.TREMORSENSE: 30,
        Sense.TRUESIGHT: 120,
    }
    assert full.held == (Sense.BLINDSIGHT, Sense.DARKVISION, Sense.TREMORSENSE, Sense.TRUESIGHT)


# --- Clause 2: light is state, and an unstated encounter stays unstated -------------


def test_an_unlit_encounter_states_no_level() -> None:
    """`None` is not Bright Light. Defaulting to daylight would be a rule value nobody
    supplied, applied invisibly to every roll."""
    assert Lighting().level_at(Position(0, 0, 0)) is None


def test_ambient_covers_everywhere_no_volume_does() -> None:
    lighting = Lighting(ambient=LightLevel.DIM)
    assert lighting.level_at(Position(500, -500, 20)) is LightLevel.DIM


def test_a_volume_overrides_the_ambient_inside_it_and_nowhere_else() -> None:
    lighting = Lighting(
        ambient=LightLevel.DARKNESS,
        volumes=(
            LitVolume(lo=Position(0, 0, 0), hi=Position(10, 10, 10), level=LightLevel.BRIGHT),
        ),
    )
    assert lighting.level_at(Position(5, 5, 5)) is LightLevel.BRIGHT
    assert lighting.level_at(Position(11, 5, 5)) is LightLevel.DARKNESS


def test_the_last_overlapping_volume_wins() -> None:
    """An engine convention, disclosed as one: the document supplies no precedence rule for
    overlapping light, so a caller layering a torch inside a dark room writes it second."""
    room = LitVolume(lo=Position(0, 0, 0), hi=Position(30, 30, 10), level=LightLevel.DARKNESS)
    torch = LitVolume(lo=Position(10, 10, 0), hi=Position(20, 20, 10), level=LightLevel.BRIGHT)
    assert Lighting(volumes=(room, torch)).level_at(Position(15, 15, 5)) is LightLevel.BRIGHT
    assert Lighting(volumes=(torch, room)).level_at(Position(15, 15, 5)) is LightLevel.DARKNESS


def test_a_volume_does_not_care_which_corners_it_was_given() -> None:
    """A caller describing a room should not have to sort its corners — the rule
    `Obstruction` already follows."""
    volume = LitVolume(lo=Position(10, 10, 10), hi=Position(0, 0, 0), level=LightLevel.BRIGHT)
    assert volume.contains(Position(5, 5, 5))
    assert volume.lo == Position(0, 0, 0)
    assert volume.hi == Position(10, 10, 10)


def test_a_volume_includes_its_faces() -> None:
    volume = LitVolume(lo=Position(0, 0, 0), hi=Position(10, 10, 10), level=LightLevel.DIM)
    assert volume.contains(Position(0, 0, 0))
    assert volume.contains(Position(10, 10, 10))
    assert not volume.contains(Position(10, 10, 11))


# --- Clause 7: the read surface reports the input and declines the conclusion --------


def _state_with(lighting: Lighting, *, senses: Senses, position: Position | None) -> EncounterState:
    return EncounterState(
        generation=0,
        combatants=(_combatant(position=position, senses=senses),),
        lighting=lighting,
    )


def test_the_situation_reports_the_light_where_the_actor_stands() -> None:
    state = _state_with(
        Lighting(
            ambient=LightLevel.DARKNESS,
            volumes=(
                LitVolume(lo=Position(0, 0, 0), hi=Position(10, 10, 10), level=LightLevel.BRIGHT),
            ),
        ),
        senses=DARKVISION_60,
        position=Position(5, 5, 5),
    )
    assert situation(state, "pc").light_level is LightLevel.BRIGHT


def test_an_actor_with_no_position_has_no_light_level() -> None:
    """The honest result, and the same one `position` already produces for range questions."""
    state = _state_with(Lighting(ambient=LightLevel.BRIGHT), senses=Senses(), position=None)
    assert situation(state, "pc").light_level is None


def test_the_situation_reports_the_actor_s_senses() -> None:
    state = _state_with(Lighting(), senses=DARKVISION_60, position=Position(0, 0, 0))
    assert situation(state, "pc").senses == DARKVISION_60


def test_reading_the_surface_resolves_no_obscurement() -> None:
    """R18 requires the surface to report what is legal now; 0025 clause 5 forbids it
    inventing what the light *means*. So `Situation` carries no obscurement field at all —
    an absent field is honest where a `None` would read as 'unobscured'."""
    state = _state_with(
        Lighting(ambient=LightLevel.DARKNESS), senses=Senses(), position=Position(0, 0, 0)
    )
    assert not hasattr(situation(state, "pc"), "obscurement")
    assert Obscurement.NONE.value == "none"
