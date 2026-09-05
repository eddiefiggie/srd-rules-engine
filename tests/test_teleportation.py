"""p. 190's Teleportation (#444), built once 0084 gave a creature a space.

> If you teleport, you disappear and reappear elsewhere instantly, without moving through the
> intervening space. This transportation doesn't expend movement unless a rule tells you
> otherwise, and teleportation never provokes Opportunity Attacks. When you teleport, all the
> equipment you're wearing and carrying teleports with you. [...] If the destination space of
> your teleportation is occupied by another creature or blocked by a solid obstacle, you
> instead appear in the nearest unoccupied space of your choice.

Two of the sentences are **behavioural contrasts**, and the issue was explicit that asserting
them any other way would be vacuous — a method that never calls the provocation path passes
trivially. So the same displacement is driven both ways here: a walk through `TurnLoop.move`
that asks a reactor, and a teleport through the one adjudication door that asks nobody, with
`provocations` made to blow up so the negative is a thing that would have fired.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from fixtures.encounter import ENGINE_VERSION, SESSION_ID, build_adjudicator, seeds_from
from fixtures.ruleset import ATTACK, FACT_TYPES, fixture_catalogue
from srd_rules_engine.core import (
    Adjudicator,
    Combatant,
    Declaration,
    EncounterState,
    Intent,
    Ledger,
    Proposal,
    Resolution,
    Status,
    attack_resolver,
)
from srd_rules_engine.core.adjudicate import Effect, EffectKind, moved_by_force, teleported
from srd_rules_engine.core.equipment import Carriage, Carried, Weapon
from srd_rules_engine.core.obstructions import Cover, Obstruction
from srd_rules_engine.core.position import Position, squared_distance
from srd_rules_engine.core.reactions import provocations
from srd_rules_engine.core.rules import Rule, RuleProvenance, Ruleset
from srd_rules_engine.core.sight import Lighting, LightLevel
from srd_rules_engine.core.size import Size
from srd_rules_engine.core.state import TELEPORT_SEARCH_FEET
from srd_rules_engine.loop.turn import ReactionRequest, TurnLoop
from srd_rules_engine.memory.store import JsonMemoryStore

ABILITIES = {"str": 16, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10}

SPEAR = Weapon(id="spear", weight=3, damage_dice=1, damage_sides=6, ability="str", melee=True)

ORIGIN = Position(0, 0, 0)
GUARD_AT = Position(5, 0, 0)
AWAY = Position(20, 0, 0)
#: A Medium creature standing here controls every point within 2½ feet of it in its plane.
TAKEN = Position(10, 0, 0)
#: The four free points nearest a Medium occupant at `TAKEN`, three feet out along the axes.
#: Two and a half feet is the half-width, no integer point lands on it, and three is the first
#: whole foot outside — (3, 1) is already √10 away.
NEAREST_TO_TAKEN = (Position(7, 0, 0), Position(10, -3, 0), Position(10, 3, 0), Position(13, 0, 0))


def _creature(cid: str, position: Position | None, **kw: object) -> Combatant:
    base: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 10,
        "abilities": ABILITIES,
        "proficiency_bonus": 2,
        "position": position,
        "size": Size.MEDIUM,
    }
    base.update(kw)
    return Combatant(**base)  # type: ignore[arg-type]


def _state(*combatants: Combatant, obstructions: tuple[Obstruction, ...] = ()) -> EncounterState:
    """Bright Light stated, so p. 185's sight clause answers and a walk genuinely provokes."""
    state = EncounterState(
        generation=0,
        combatants=tuple(combatants),
        lighting=Lighting(ambient=LightLevel.BRIGHT),
        obstructions=obstructions,
    )
    return state.with_initiative({c.id: 20 - index for index, c in enumerate(combatants)})


# --- The transportation itself -------------------------------------------------------------


def test_a_free_destination_is_where_the_creature_appears() -> None:
    state = _state(_creature("mover", ORIGIN))

    after = state.with_teleport("mover", AWAY)

    assert after.combatant("mover").position == AWAY


def test_no_movement_is_spent_where_a_walk_would_spend_it() -> None:
    """p. 190: "doesn't expend movement". Asserted as a contrast rather than as a zero — the
    same twenty feet walked costs twenty, so the zero is a thing the rule withheld."""
    state = _state(_creature("mover", ORIGIN))

    walked = state.with_movement("mover", AWAY).combatant("mover")
    teleported_to = state.with_teleport("mover", AWAY).combatant("mover")

    assert walked.movement_used == 20
    assert teleported_to.movement_used == 0
    assert teleported_to.position == walked.position


def test_equipment_travels_with_the_creature() -> None:
    """p. 190: "all the equipment you're wearing and carrying teleports with you". It holds by
    construction — equipment is a field on the creature — and is asserted so that a later
    model that moved items to the map would have to come here and say so."""
    held = (Carried(item=SPEAR, carriage=Carriage.HELD),)
    state = _state(_creature("mover", ORIGIN, equipment=held))

    after = state.with_teleport("mover", AWAY).combatant("mover")

    assert after.equipment == held
    assert after.weapons_held == (SPEAR,)


def test_no_line_is_traced_through_the_intervening_space() -> None:
    """p. 190: "without moving through the intervening space". A wall of Total Cover standing
    between origin and destination is not in the way, because nothing is between."""
    wall = Obstruction(Position(9, -5, 0), Position(11, 5, 10), degree=Cover.TOTAL)
    state = _state(_creature("mover", ORIGIN), obstructions=(wall,))

    after = state.with_teleport("mover", AWAY)

    assert after.combatant("mover").position == AWAY


# --- Never provokes, asserted as a contrast ------------------------------------------------

TELEPORT = Rule(
    id="fixture-teleport",
    summary="Vanish and reappear at a stated point, as p. 190 describes.",
    provenance=RuleProvenance.FIXTURE,
    rationale=(
        "Invented, because there are no spells (#21) and so nothing in the engine causes a "
        "teleport. What it exercises is the transition and the door it goes through."
    ),
)


def _teleport_adjudicator(
    path: Path, to: Position, *, landing: Position | None = None
) -> Adjudicator:
    """An adjudicator whose fixture teleport puts the actor at `to`, through R1's one door."""

    def resolver(
        *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
    ) -> Proposal:
        return Proposal(
            outcome=(
                teleported(
                    declaration.actor_id,
                    to,
                    landing=landing,
                    description=f"vanished and reappeared at ({to.x}, {to.y}, {to.z})",
                ),
            ),
            citations=(f"fixture:{TELEPORT.id}",),
        )

    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=Ruleset(
            provenance=RuleProvenance.FIXTURE,
            rules={ATTACK.id: ATTACK, TELEPORT.id: TELEPORT},
            name="teleport-fixture",
        ),
        resolvers={ATTACK.id: attack_resolver(), TELEPORT.id: resolver},
        fact_types=FACT_TYPES,
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl",
            engine_version=ENGINE_VERSION,
            catalogue_version=fixture_catalogue().version,
            session_id=SESSION_ID,
        ),
        catalogue=fixture_catalogue(),
        seed_source=seeds_from(11),
    )


def _vanish() -> Declaration:
    return Declaration(
        actor_id="mover", intent=Intent(improvised=True, label="blink away"), rule_id=TELEPORT.id
    )


def _guarded() -> EncounterState:
    """A mover in a spear-wielder's reach, so leaving provokes p. 185's attack."""
    guard = _creature("guard", GUARD_AT, equipment=(Carried(item=SPEAR, carriage=Carriage.HELD),))
    return _state(_creature("mover", ORIGIN), guard)


def test_a_teleport_never_provokes_where_a_walk_would(tmp_path: Path) -> None:
    """p. 190: "teleportation never provokes Opportunity Attacks."

    The walk is asserted first, so the teleport's silence is the absence of a thing that was
    there to fire: the same creature leaving the same reach through `TurnLoop.move` is met
    with a `ReactionRequest` before anything moves.
    """
    state = _guarded()
    assert provocations(state, "mover", frm=ORIGIN, to=AWAY), "the fixture must provoke"
    walk = TurnLoop(adjudicator=build_adjudicator(tmp_path / "walk", seed=7)).move(
        state, "mover", AWAY
    )
    assert isinstance(next(walk), ReactionRequest)

    ruling, after = _teleport_adjudicator(tmp_path / "blink", AWAY).adjudicate(state, _vanish())

    assert ruling.status is Status.RULED
    assert [e.kind for e in ruling.effects] == [EffectKind.TELEPORTED]
    assert after.combatant("mover").position == AWAY
    assert after.combatant("mover").movement_used == 0
    assert not after.combatant("guard").actions.reaction_spent, "nobody was asked, nobody spent"


def test_the_provocation_path_is_never_consulted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The negative made falsifiable. `provocations` is replaced by something that raises, so
    a teleport that so much as asked who it would provoke fails here — and the same patch is
    shown to bite the walk, so the silence is not a patch that landed nowhere."""
    state = _guarded()

    def never(*args: object, **kwargs: object) -> tuple[()]:
        raise AssertionError("asked who a teleport would provoke")

    monkeypatch.setattr("srd_rules_engine.loop.turn.provocations", never)
    monkeypatch.setattr("srd_rules_engine.core.reactions.provocations", never)

    with pytest.raises(AssertionError, match="asked who"):
        next(
            TurnLoop(adjudicator=build_adjudicator(tmp_path / "walk", seed=7)).move(
                state, "mover", AWAY
            )
        )

    ruling, after = _teleport_adjudicator(tmp_path / "blink", AWAY).adjudicate(state, _vanish())
    assert ruling.status is Status.RULED
    assert after.combatant("mover").position == AWAY


# --- The destination rule (p. 190, via 0084) -----------------------------------------------


def test_an_occupied_destination_offers_every_nearest_free_point() -> None:
    """p. 190: "the nearest unoccupied space of your choice" — the engine enumerates the choice
    and picks nothing. Nearest is asserted the hard way: every point strictly closer to the
    destination than the offered ones is shown to be taken."""
    state = _state(_creature("mover", ORIGIN), _creature("bystander", TAKEN))

    offered = state.teleport_destinations("mover", TAKEN)

    assert offered == NEAREST_TO_TAKEN
    least = squared_distance(TAKEN, offered[0])
    assert all(squared_distance(TAKEN, p) == least for p in offered), "one distance, many points"
    assert all(state.is_unoccupied(p) for p in offered)
    closer = [
        Position(TAKEN.x + dx, TAKEN.y + dy, TAKEN.z + dz)
        for dx in range(-3, 4)
        for dy in range(-3, 4)
        for dz in range(-3, 4)
        if 0 < dx * dx + dy * dy + dz * dz < least
    ]
    assert closer, "the sweep must have something to check"
    assert all(not state.is_unoccupied(p) for p in closer), "nothing nearer is free"


def test_a_free_destination_offers_itself_and_nothing_else() -> None:
    state = _state(_creature("mover", ORIGIN), _creature("bystander", TAKEN))
    assert state.teleport_destinations("mover", AWAY) == (AWAY,)


def test_the_control_area_is_a_column_so_up_is_not_out() -> None:
    """0084 clause 5: a space is a square, not a cube, so the point five feet above an occupant
    is still in its space and the nearest free points are in the destination's own plane."""
    state = _state(_creature("mover", ORIGIN), _creature("bystander", TAKEN))
    above = Position(10, 0, 5)

    assert not state.is_unoccupied(above)
    assert state.teleport_destinations("mover", above) == tuple(
        Position(p.x, p.y, 5) for p in NEAREST_TO_TAKEN
    )


def test_the_choice_is_the_callers_and_is_checked() -> None:
    """Three refusals and one acceptance, and each refusal names the nearest set so the caller
    can choose from it rather than guess."""
    state = _state(_creature("mover", ORIGIN), _creature("bystander", TAKEN))

    with pytest.raises(ValueError, match=r"occupied by Bystander.*\(7, 0, 0\)"):
        state.with_teleport("mover", TAKEN)
    with pytest.raises(ValueError, match="not one of the nearest"):
        state.with_teleport("mover", TAKEN, landing=AWAY)  # free, and not nearest
    with pytest.raises(ValueError, match="not one of the nearest"):
        state.with_teleport("mover", TAKEN, landing=Position(11, 0, 0))  # taken

    for choice in NEAREST_TO_TAKEN:
        assert state.with_teleport("mover", TAKEN, landing=choice).combatant("mover").position == (
            choice
        )


def test_a_landing_stated_for_a_free_destination_is_refused() -> None:
    """p. 190 diverts only when the destination is taken. Accepting a landing otherwise would
    let a caller move a creature further than the rule did, under the rule's name."""
    state = _state(_creature("mover", ORIGIN))
    with pytest.raises(ValueError, match="is unoccupied"):
        state.with_teleport("mover", AWAY, landing=Position(25, 0, 0))


def test_a_diverted_landing_goes_through_the_one_door(tmp_path: Path) -> None:
    state = _state(_creature("mover", ORIGIN), _creature("bystander", TAKEN))
    choice = NEAREST_TO_TAKEN[0]

    ruling, after = _teleport_adjudicator(tmp_path, TAKEN, landing=choice).adjudicate(
        state, _vanish()
    )

    assert ruling.status is Status.RULED
    assert after.combatant("mover").position == choice
    assert after.combatant("bystander").position == TAKEN


def test_a_solid_obstacle_diverts_and_smoke_does_not() -> None:
    """ "Blocked by a solid obstacle." An `Obstruction` that gives cover is something a body
    cannot appear inside; one that gives none is smoke (p. 181), which it can."""
    wall = Obstruction(Position(8, -2, 0), Position(12, 2, 10), degree=Cover.TOTAL)
    smoke = Obstruction(
        Position(8, -2, 0), Position(12, 2, 10), degree=Cover.NONE, blocks_sight=True
    )

    walled = _state(_creature("mover", ORIGIN), obstructions=(wall,))
    smoky = _state(_creature("mover", ORIGIN), obstructions=(smoke,))

    assert TAKEN not in walled.teleport_destinations("mover", TAKEN)
    assert all(not wall.contains(p) for p in walled.teleport_destinations("mover", TAKEN))
    with pytest.raises(ValueError, match="blocked by a solid obstacle"):
        walled.with_teleport("mover", TAKEN)
    assert smoky.teleport_destinations("mover", TAKEN) == (TAKEN,)
    assert smoky.with_teleport("mover", TAKEN).combatant("mover").position == TAKEN


def test_a_creatures_own_space_is_not_occupied_by_another() -> None:
    """p. 190 says "another creature", so a hop inside one's own control area is a destination
    like any other."""
    state = _state(_creature("mover", ORIGIN))
    assert state.with_teleport("mover", Position(1, 0, 0)).combatant("mover").position == (
        Position(1, 0, 0)
    )


def test_a_creature_nobody_sized_occupies_nothing() -> None:
    """0051's reading, reaching here through `occupants_of`: an unstated size is unknown rather
    than Medium, so nothing is diverted around a creature nobody sized."""
    state = _state(_creature("mover", ORIGIN), _creature("shade", TAKEN, size=None))
    assert state.with_teleport("mover", TAKEN).combatant("mover").position == TAKEN


def test_a_creature_at_zero_hit_points_can_be_teleported() -> None:
    """Where `with_movement` refuses (0072): a teleport is done *to* a creature, and an
    unconscious body carried by another's spell is the ordinary case."""
    state = _state(_creature("mover", ORIGIN, hit_points=0))

    with pytest.raises(ValueError, match="0 hit points"):
        state.with_movement("mover", AWAY)
    assert state.with_teleport("mover", AWAY).combatant("mover").position == AWAY


def test_a_creature_with_no_position_has_nowhere_to_vanish_from() -> None:
    state = _state(_creature("mover", None))
    with pytest.raises(ValueError, match="no position"):
        state.with_teleport("mover", AWAY)


def test_the_search_is_bounded_and_the_bound_is_a_refusal() -> None:
    """A scene walled off further than the sweep looks is refused rather than answered with a
    place further out that the engine chose."""
    reach = TELEPORT_SEARCH_FEET + 5
    everywhere = Obstruction(
        Position(TAKEN.x - reach, TAKEN.y - reach, TAKEN.z - reach),
        Position(TAKEN.x + reach, TAKEN.y + reach, TAKEN.z + reach),
    )
    state = _state(_creature("mover", Position(-100, 0, 0), size=None), obstructions=(everywhere,))

    with pytest.raises(ValueError, match=f"no unoccupied space within {TELEPORT_SEARCH_FEET}"):
        state.teleport_destinations("mover", TAKEN)


# --- The effect ----------------------------------------------------------------------------


def test_the_effect_carries_no_distance_and_its_landing_belongs_to_it_alone() -> None:
    effect = teleported("mover", AWAY, landing=None, description="blinked")
    assert effect.kind is EffectKind.TELEPORTED
    assert effect.amount == 0, "p. 190 covers no intervening space, so no distance travelled"
    assert effect.position == AWAY and effect.landing is None

    with pytest.raises(ValueError, match="carries no landing"):
        Effect(
            kind=EffectKind.MOVED_BY_FORCE,
            target_id="mover",
            amount=5,
            description="shoved",
            position=AWAY,
            landing=ORIGIN,
        )
    with pytest.raises(ValueError, match="names no destination"):
        Effect(kind=EffectKind.DAMAGE, target_id="mover", amount=3, description="x", position=AWAY)
    with pytest.raises(ValueError, match="names destination"):
        Effect(kind=EffectKind.TELEPORTED, target_id="mover", amount=0, description="x")
    assert moved_by_force("mover", AWAY, feet=5, description="shoved").position == AWAY
