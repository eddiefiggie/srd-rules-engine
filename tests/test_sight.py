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
    effective_light,
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


# --- Clause 5: the rules are read, and every row traces to a page -----------------


def test_a_row_may_exist_only_because_the_pages_were_read() -> None:
    """The inverse of the guard clause 5 shipped with, now that #150 has read them.

    R31 is unchanged: a rule value that reached the engine without being read off the
    document is indistinguishable from one that was. What changed is which state is correct
    — and the two must move together, so a table filled while the verification still said
    `unverified` would be exactly the defect the original guard was watching for.
    """
    assert SIGHT_VERIFICATION.state is VerificationState.VERIFIED
    assert OBSCUREMENT_BY_LIGHT, "the pages are read but no row exists"
    assert SENSE_LIGHT_SHIFTS, "the pages are read but no sense converts anything"


def test_the_verification_names_every_page_a_row_rests_on() -> None:
    """Nine shapes, seven pages. A block citing a range it does not rest on is the defect
    #129 and #131 were filed for, and #150 would reproduce it at scale."""
    reference = SIGHT_VERIFICATION.reference or ""
    for page in ("p. 177", "p. 178", "p. 180", "p. 181", "p. 182", "p. 184", "p. 190"):
        assert page in reference, f"{page} carries a row and is not cited"


def test_dim_light_is_lightly_obscured_and_darkness_is_heavily() -> None:
    """p. 181 and p. 180. The glossary says each light level **is** an obscurement rather
    than relating the two by some further rule, so this is a transcription, not a join."""
    assert OBSCUREMENT_BY_LIGHT[LightLevel.DIM] is Obscurement.LIGHTLY_OBSCURED
    assert OBSCUREMENT_BY_LIGHT[LightLevel.DARKNESS] is Obscurement.HEAVILY_OBSCURED


def test_bright_light_obscures_nothing_and_that_is_this_engines_word() -> None:
    """p. 178 says only that Bright Light "is normal illumination" — it names no
    obscurement. `Obscurement.NONE` is this engine's absence, the same construction as
    `Cover.NONE`, rather than a glossary term."""
    assert OBSCUREMENT_BY_LIGHT[LightLevel.BRIGHT] is Obscurement.NONE


def test_darkvision_converts_and_the_others_do_not() -> None:
    """p. 180 gives Darkvision as a conversion; the other three resolve sight by routes that
    are not conversions at all (#166). Modelling them here would be a wrong number that
    looked right."""
    assert SENSE_LIGHT_SHIFTS[Sense.DARKVISION][LightLevel.DIM] is LightLevel.BRIGHT
    assert SENSE_LIGHT_SHIFTS[Sense.DARKVISION][LightLevel.DARKNESS] is LightLevel.DIM
    assert set(SENSE_LIGHT_SHIFTS) == {Sense.DARKVISION}


def test_a_second_converting_sense_would_need_a_combining_rule_first() -> None:
    """`effective_light` returns on the first sense that converts, which is unambiguous only
    while one sense converts. The document supplies no rule for combining two, so adding one
    without reading that rule would make the answer depend on enum order."""
    assert len(SENSE_LIGHT_SHIFTS) == 1, (
        "a second converting sense exists. The document states no rule for combining two "
        "conversions, so effective_light's first-match return is now an invented precedence "
        "— read the combining rule off the document before adding it"
    )


def test_darkvision_stops_at_its_range() -> None:
    """p. 180 converts "within a specified range". Beyond it the creature reads the level
    as everyone else does, which is why obscurement takes a distance at all."""
    assert effective_light(LightLevel.DARKNESS, senses=DARKVISION_60, distance_feet=60) is (
        LightLevel.DIM
    )
    assert effective_light(LightLevel.DARKNESS, senses=DARKVISION_60, distance_feet=61) is (
        LightLevel.DARKNESS
    )


def test_darkness_is_only_lightly_obscuring_to_darkvision_in_range() -> None:
    """The chain end to end: the sense re-reads the level, and the level is the obscurement."""
    assert (
        obscurement_at(LightLevel.DARKNESS, senses=DARKVISION_60, distance_feet=30)
        is Obscurement.LIGHTLY_OBSCURED
    )
    assert (
        obscurement_at(LightLevel.DARKNESS, senses=Senses(), distance_feet=30)
        is Obscurement.HEAVILY_OBSCURED
    )


def test_visibility_is_asked_of_the_encounter_rather_than_of_this_module() -> None:
    """#166 moved it. `EncounterState.can_see` needs the encounter's obstructions and its
    light, and taking either as an argument is the dial 0026 removed — so it lives where
    `creatures_in` does, for the same reason. Nothing here answers it."""
    import srd_rules_engine.core.sight as sight_module

    assert not hasattr(sight_module, "can_see")
    assert hasattr(EncounterState, "can_see")


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


def test_only_the_sight_shapes_whose_consequence_is_produced_are_claimed() -> None:
    """Structure is not resolution, and neither is a partial answer.

    The standard is one sentence: **a shape is claimed when the engine produces the
    consequence its entry states.** #138 applied it to the four this test originally grouped
    together and did not separate, and it splits them two and two.

    Four resolve:

    * **Blindsight** — every clause of its entry `EncounterState.can_see` answers: range, the
      Total Cover bound, Darkness, the Blinded override and the Invisible condition.
    * **Darkvision** — its entry *is* the conversion `effective_light` performs.
    * **Heavily Obscured** (p. 182) — "You have the Blinded condition **while trying to see
      something** in a Heavily Obscured space". Scoped to the attempt, so it is a relation
      between observer and target rather than a condition on a creature; `can_see` answers
      that relation and cites that sentence. There is no wholesale Blinded left unapplied.
    * **Darkness** (p. 180) — "An area of Darkness is Heavily Obscured" is the whole entry,
      and the consequence flows: the mapping produces it and `can_see` acts on it.

    Six are not claimed, and each for its own reason rather than for want of effort:

    * **Truesight** also pierces visual illusions, transformations and the Ethereal Plane
      (p. 190). `can_see` answers two of its five clauses.
    * **Tremorsense** pinpoints a location and "doesn't count as a form of sight" (p. 190).
      Nothing here answers the question it does answer.
    * **Lightly Obscured** costs Disadvantage on Perception checks (p. 184), and nothing
      produces that penalty — `can_see` treats the space as visible, which it is.
    * **Dim Light** (p. 181) *is* Lightly Obscured, which the mapping produces — and which
      nothing then reads, because the penalty above is unproduced. Computed, then consumed by
      nobody, which resolves nothing.
    * **Bright Light** (p. 178) states no consequence at all — "normal illumination" — so
      there is nothing for the engine to be judged as producing. Claiming it would count a
      definition.
    * **Telepathy** is not in this chain at all (0025 clause 1, #149).

    The count is what makes "full SRD 5.2 coverage" falsifiable, so a shape half-answered is
    a shape unclaimed — and a shape fully answered and left unclaimed is the same instrument
    lying in the other direction (#207).
    """
    sight_shapes = [s for s in load_inventory().shapes if s.kind in ("sense", "environment")]
    assert len(sight_shapes) == 10

    claimed = {s.id for s in sight_shapes if s.implemented}
    assert claimed == {"blindsight", "darkness", "darkvision", "heavily-obscured"}


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
