"""Whether one creature sees another — and the three places the document stops (#166).

0025 clause 4 decided visibility is derived on demand and stored nowhere. #150 read the nine
pages and filled the obscurement chain. This is the question those were for, and answering it
turned up something bigger than the modelling gap #166 was filed about.

**The SRD never says that an obstruction blocks sight, and it never defines "line of sight".**

The term appears on pp. 130, 131, 173, 182, 183 and 310 and is defined on none of them. Total
Cover is defined by what it does to *targeting* — "can't be targeted directly" (p. 179). The
clearest evidence is p. 173, where a spell's wall has to state that it "blocks line of sight":
if an obstruction did that by default, the clause would be redundant.

So `Visibility.UNSTATED` is a real answer rather than a stub, and it is permanent until the
document says otherwise. Answering `CANNOT_SEE` for a target behind a wall would infer a rule
(R31); answering `CAN_SEE` would be worse.

**Blindsight is the exception**, and the only one: p. 177 gives its bound outright — "anything
that isn't behind Total Cover even if you have the Blinded condition or are in Darkness".

Three things here are tested against the wrong answer:

* **A wall does not make the answer `CANNOT_SEE`.** That is the intuition the document does
  not support, and it is the one an implementer supplies from life rather than from p. 179.
* **Unlit is not dark.** Nobody stating the light is a question nobody answered, not Darkness.
* **Tremorsense never contributes**, because p. 190 says it "doesn't count as a form of sight".
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.obstructions import Obstruction
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.sight import (
    Lighting,
    LightLevel,
    Sense,
    Senses,
    Visibility,
)
from srd_rules_engine.core.state import Combatant, EncounterState

WALL = Obstruction(lo=Position(10, -20, 0), hi=Position(12, 20, 20))
HERE = Position(0, 0, 0)
THIRTY_FEET_EAST = Position(30, 0, 0)


def creature(cid: str, where: Position | None, *, senses: Senses | None = None) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"dex": 10},
        proficiency_bonus=2,
        position=where,
        senses=senses or Senses(),
    )


def scene(
    *,
    observer: Senses | None = None,
    target_at: Position = THIRTY_FEET_EAST,
    ambient: LightLevel | None = LightLevel.BRIGHT,
    walls: tuple[Obstruction, ...] = (),
    observer_at: Position | None = HERE,
) -> EncounterState:
    return EncounterState(
        generation=0,
        combatants=(
            creature("watcher", observer_at, senses=observer),
            creature("quarry", target_at),
        ),
        lighting=Lighting(ambient=ambient),
        obstructions=walls,
    )


# --- What the document does say ----------------------------------------------------------


def test_a_creature_in_bright_light_is_seen() -> None:
    sight = scene().can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CAN_SEE
    assert sight.by is None, "ordinary sight, no special sense involved"


def test_a_creature_in_darkness_is_not_seen() -> None:
    """p. 180 makes Darkness Heavily Obscured; p. 182 gives the Blinded condition while
    trying to see something in such a space."""
    sight = scene(ambient=LightLevel.DARKNESS).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CANNOT_SEE
    assert "Heavily Obscured" in sight.because


def test_darkvision_reaches_into_darkness_within_its_range() -> None:
    """p. 180 reads Darkness as Dim Light, and Dim Light is only Lightly Obscured (p. 181) —
    a Perception penalty rather than a bar to seeing."""
    seen = scene(observer=Senses(darkvision=60), ambient=LightLevel.DARKNESS)
    assert seen.can_see("watcher", "quarry").verdict is Visibility.CAN_SEE


def test_darkvision_stops_at_its_range() -> None:
    """The case that separates a range from a switch."""
    far = scene(
        observer=Senses(darkvision=20),
        ambient=LightLevel.DARKNESS,
        target_at=Position(30, 0, 0),
    )
    assert far.can_see("watcher", "quarry").verdict is Visibility.CANNOT_SEE


def test_blindsight_sees_in_darkness() -> None:
    """p. 177: within range, "even if you have the Blinded condition or are in Darkness"."""
    sight = scene(observer=Senses(blindsight=60), ambient=LightLevel.DARKNESS).can_see(
        "watcher", "quarry"
    )
    assert sight.verdict is Visibility.CAN_SEE
    assert sight.by is Sense.BLINDSIGHT


def test_truesight_sees_in_darkness() -> None:
    """p. 190: "You can see in normal and magical Darkness"."""
    sight = scene(observer=Senses(truesight=60), ambient=LightLevel.DARKNESS).can_see(
        "watcher", "quarry"
    )
    assert sight.verdict is Visibility.CAN_SEE
    assert sight.by is Sense.TRUESIGHT


# --- Where the document stops -------------------------------------------------------------


def test_a_wall_does_not_make_the_answer_no() -> None:
    """The finding this issue turned on, and the intuition an implementer supplies from life.

    A target behind Total Cover is `UNSTATED`: the SRD defines Total Cover by what it does to
    targeting (p. 179), defines "line of sight" nowhere, and has a spell's wall state that it
    blocks line of sight (p. 173) — which it would not need to if obstructions did so.
    """
    sight = scene(walls=(WALL,)).can_see("watcher", "quarry")

    assert sight.verdict is Visibility.UNSTATED
    assert not sight.can_see, "UNSTATED is not a yes"
    assert "nobody has said whether that barrier blocks sight" in sight.because


def test_blindsight_alone_is_ruled_out_by_a_wall() -> None:
    """p. 177 gives Blindsight's bound outright, so this much IS stated — and it still does
    not settle the question, because the other routes remain unstated."""
    sight = scene(observer=Senses(blindsight=60), walls=(WALL,)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.UNSTATED


def test_a_wall_that_is_not_between_them_settles_nothing_either_way() -> None:
    """Blocking is per-line (#91), so standing beside a wall is not standing behind it."""
    beside = scene(walls=(WALL,), target_at=Position(0, 40, 0))
    assert beside.can_see("watcher", "quarry").verdict is Visibility.CAN_SEE


def test_unlit_is_not_dark() -> None:
    """0025 clause 2: the default states no light at all, and this engine does not assume
    daylight. Nobody having said is a question nobody answered."""
    sight = scene(ambient=None).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.UNSTATED
    assert "nobody has stated the light" in sight.because


def test_an_encounter_without_positions_cannot_answer() -> None:
    """Reporting either answer would invent the geometry it does not have."""
    sight = scene(observer_at=None).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.UNSTATED


# --- Tremorsense is not a form of sight ----------------------------------------------------


def test_tremorsense_never_contributes() -> None:
    """p. 190 says so outright: it "doesn't count as a form of sight". It pinpoints a
    location, which is a different question, and an engine that let it answer this one would
    have a creature seeing through a wall by feeling the floor."""
    sight = scene(observer=Senses(tremorsense=120), ambient=LightLevel.DARKNESS).can_see(
        "watcher", "quarry"
    )
    assert sight.verdict is Visibility.CANNOT_SEE
    assert sight.by is not Sense.TREMORSENSE


def test_tremorsense_does_not_rescue_a_blocked_view_either() -> None:
    sight = scene(observer=Senses(tremorsense=120), walls=(WALL,)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.UNSTATED


# --- The shape of the answer ---------------------------------------------------------------


@pytest.mark.parametrize("verdict", list(Visibility))
def test_only_can_see_reads_as_yes(verdict: Visibility) -> None:
    """`UNSTATED` must not be truthy anywhere. A caller that treated it as a yes would have
    the engine assert exactly what it declined to."""
    from srd_rules_engine.core.sight import Sight

    assert Sight(verdict=verdict, because="x").can_see == (verdict is Visibility.CAN_SEE)


def test_every_answer_says_what_it_rests_on() -> None:
    """A refusal that does not explain itself is indistinguishable from a bug."""
    for state in (scene(), scene(walls=(WALL,)), scene(ambient=None)):
        assert state.can_see("watcher", "quarry").because


# --- The Invisible condition, which says less than its name -------------------------------


def _invisible_quarry(**kwargs: object) -> EncounterState:
    state = scene(**kwargs)  # type: ignore[arg-type]
    hidden = replace(
        state.combatant("quarry"),
        conditions=Conditions(held=frozenset({Condition.INVISIBLE})),
    )
    return replace(
        state,
        combatants=tuple(hidden if c.id == "quarry" else c for c in state.combatants),
    )


def test_ordinary_sight_of_an_invisible_creature_is_unstated() -> None:
    """p. 184 never says an Invisible creature cannot be seen.

    It says an effect needing sight misses it "unless the effect's creator can somehow see
    you", and leaves *somehow* to the table. An engine that answered `CANNOT_SEE` would be
    reading the condition's name rather than its text — which is the 2024 reframing this
    repository already flags as `unless-seen-exception` in `Conditions.unenforced_clauses`.
    """
    sight = _invisible_quarry().can_see("watcher", "quarry")

    assert sight.verdict is Visibility.UNSTATED
    assert "somehow" in sight.because


def test_blindsight_sees_an_invisible_creature() -> None:
    """p. 177: "Moreover, in that range, you can see something that has the Invisible
    condition." One of the two routes the document answers for."""
    sight = _invisible_quarry(observer=Senses(blindsight=60)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CAN_SEE
    assert sight.by is Sense.BLINDSIGHT


def test_truesight_sees_an_invisible_creature() -> None:
    """p. 190: "You see creatures and objects that have the Invisible condition."""
    sight = _invisible_quarry(observer=Senses(truesight=60)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CAN_SEE
    assert sight.by is Sense.TRUESIGHT


def test_darkvision_does_not_see_an_invisible_creature() -> None:
    """Darkvision converts a light level and says nothing about Invisibility (p. 180). The
    sense that helps most in the dark is the one that does not help here."""
    sight = _invisible_quarry(observer=Senses(darkvision=60)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.UNSTATED


# --- A Blinded observer, which the document is absolute about -----------------------------


def _blind_watcher(**kwargs: object) -> EncounterState:
    state = scene(**kwargs)  # type: ignore[arg-type]
    blind = replace(
        state.combatant("watcher"),
        conditions=Conditions(held=frozenset({Condition.BLINDED})),
    )
    return replace(
        state,
        combatants=tuple(blind if c.id == "watcher" else c for c in state.combatants),
    )


def test_a_blinded_observer_sees_nothing_however_bright_it_is() -> None:
    """p. 177: "You can't see." Absolute, and the case an engine that only ever consults the
    *light* would get wrong in the most obvious way available."""
    sight = _blind_watcher().can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CANNOT_SEE
    assert "Blinded" in sight.because


def test_blindsight_is_the_one_sense_that_overrides_being_blinded() -> None:
    """p. 177 says so in terms — "even if you have the Blinded condition"."""
    sight = _blind_watcher(observer=Senses(blindsight=60)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CAN_SEE
    assert sight.by is Sense.BLINDSIGHT


def test_truesight_does_not_override_being_blinded() -> None:
    """p. 190 never claims it does, and granting it that reach would be inventing an ability
    the document withholds — the direction that adds a capability rather than a limit."""
    sight = _blind_watcher(observer=Senses(truesight=60)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CANNOT_SEE


def test_darkvision_does_not_override_being_blinded() -> None:
    sight = _blind_watcher(observer=Senses(darkvision=60)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CANNOT_SEE


# --- 0029: the barrier says, and the document answers it both ways ------------------------

OPAQUE = Obstruction(lo=Position(10, -20, 0), hi=Position(12, 20, 20), blocks_sight=True)
CLEAR = Obstruction(lo=Position(10, -20, 0), hi=Position(12, 20, 20), blocks_sight=False)
FURTHER_OPAQUE = Obstruction(lo=Position(20, -20, 0), hi=Position(22, 20, 20), blocks_sight=True)


def test_a_barrier_that_blocks_sight_settles_it() -> None:
    """Wall of Thorns: "The wall blocks line of sight" (p. 173)."""
    sight = scene(walls=(OPAQUE,)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CANNOT_SEE


def test_a_barrier_that_does_not_block_sight_is_seen_through() -> None:
    """Wall of Force: "An Invisible wall of force" (p. 172). Total Cover, and transparent.

    This is the case that makes any global rule wrong: the same engine has to answer
    `CANNOT_SEE` for the thorns and `CAN_SEE` here, and both walls are printed three pages
    apart.
    """
    sight = scene(walls=(CLEAR,)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CAN_SEE


def test_an_opaque_barrier_beats_a_transparent_one_on_the_same_line() -> None:
    """One barrier known to block sight is enough, whatever else is between."""
    sight = scene(walls=(CLEAR, FURTHER_OPAQUE)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.CANNOT_SEE


def test_an_undescribed_barrier_is_not_assumed_transparent() -> None:
    """0029 clause 4: unstated loses to opaque and beats transparent.

    A wall nobody has described cannot borrow its neighbour's answer — that would let a
    caller make a barrier see-through by putting a pane of glass next to it.
    """
    sight = scene(walls=(CLEAR, WALL)).can_see("watcher", "quarry")
    assert sight.verdict is Visibility.UNSTATED


def test_a_transparent_barrier_still_blocks_an_area_of_effect() -> None:
    """p. 177 blocks a line of *effect* with Total Cover, and 0029 does not touch it. A
    Fireball is stopped by Wall of Force; a glance is not — two questions over one box."""
    from srd_rules_engine.core.areas import Sphere

    state = scene(walls=(CLEAR,))
    assert state.can_see("watcher", "quarry").verdict is Visibility.CAN_SEE
    assert state.creatures_in(Sphere(HERE, 60)) == ("watcher",), "the quarry is not reached"


def test_blocks_sight_defaults_to_unstated() -> None:
    """The SRD supplies no default and this engine invents none (0029 clause 2)."""
    assert Obstruction(lo=HERE, hi=Position(1, 1, 1)).blocks_sight is None
