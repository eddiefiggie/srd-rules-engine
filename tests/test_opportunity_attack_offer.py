"""p. 185's Opportunity Attack, offered and resolved (#382, 0072).

[#381](https://github.com/eddiefiggie/srd-rules-engine/issues/381) made the sight clause
answerable and left the offer unbuilt: `core.reactions.provocations` had no production caller
and `EncounterState.with_movement` deliberately did not consult it. This is the other half.

**The phase, not the state method, is what provokes.** The offer needs the agent seam and the
seam lives in the loop, so `TurnLoop.move` wraps `with_movement` — asks who is provoked, offers
each of them the attack, spends the Reaction and adjudicates, and only then applies the move. A
consumer calling `with_movement` directly still provokes nothing, and
`test_a_direct_state_move_provokes_nothing` pins that limit rather than leaving it to be
discovered (0072 clause 6).

**The attacks resolve before the move**, which is geometry rather than a reading of p. 185's
silence: provoking means the mover was in reach and is leaving it, so at the destination a
melee attack has nothing in range.
"""

from __future__ import annotations

import sys
from collections.abc import Generator
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fixtures.encounter import build_adjudicator
from fixtures.ruleset import ATTACK
from srd_rules_engine.core import (
    Declaration,
    EncounterState,
    Intent,
    Position,
    Status,
    opportunity_attack_key,
    reaction_options,
)
from srd_rules_engine.core.actions import ActionBudget, ActionKind
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.equipment import Carriage, Carried, Weapon
from srd_rules_engine.core.sight import Lighting, LightLevel
from srd_rules_engine.core.state import Combatant
from srd_rules_engine.loop.turn import (
    Declared,
    MoveOutcome,
    Narrated,
    ReactionDeclined,
    ReactionRequest,
    Request,
    Response,
    TurnLoop,
)

ABILITIES = {"str": 16, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10}

SPEAR = Weapon(
    id="spear",
    weight=3,
    damage_dice=1,
    damage_sides=6,
    ability="str",
    melee=True,
    damage_type=DamageType.PIERCING,
)
#: A Ranged weapon, so p. 185's "one **melee** attack" excludes it. Its own fixture rather
#: than a flag flipped on the spear, because the offer is filtered on the weapon.
BOW = Weapon(
    id="bow",
    weight=2,
    damage_dice=1,
    damage_sides=8,
    ability="dex",
    melee=False,
    damage_type=DamageType.PIERCING,
    normal_range=80,
    long_range=320,
)

ORIGIN = Position(0, 0, 0)
GUARD_AT = Position(5, 0, 0)
AWAY = Position(20, 0, 0)


def _combatant(cid: str, position: Position | None, **kwargs: object) -> Combatant:
    base: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 20,
        "max_hit_points": 20,
        # Low enough that the fixture's d20 lands a hit, so the damage path is exercised
        # rather than only the offer.
        "armour_class": 1,
        "abilities": ABILITIES,
        "proficiency_bonus": 2,
        "position": position,
    }
    base.update(kwargs)
    return Combatant(**base)  # type: ignore[arg-type]


def _armed(cid: str, position: Position | None, weapon: Weapon = SPEAR, **kw: object) -> Combatant:
    return _combatant(
        cid, position, equipment=(Carried(item=weapon, carriage=Carriage.HELD),), **kw
    )


def _encounter(*combatants: Combatant, lit: bool = True) -> EncounterState:
    """Bright Light stated, so `can_see` answers p. 185's sight clause (0025 clause 2)."""
    state = EncounterState(
        generation=0,
        combatants=tuple(combatants),
        lighting=Lighting(ambient=LightLevel.BRIGHT) if lit else Lighting(),
    )
    return state.with_initiative({c.id: 20 - index for index, c in enumerate(combatants)})


def _loop(tmp_path: Path) -> TurnLoop:
    return TurnLoop(adjudicator=build_adjudicator(tmp_path, seed=7))


def _take(weapon_id: str = "spear", reactor: str = "guard") -> Declaration:
    return Declaration(
        actor_id=reactor,
        intent=Intent(action_key=opportunity_attack_key(weapon_id, "mover")),
        rule_id=ATTACK.id,
    )


def _drive(gen: Generator[Request, Response, MoveOutcome], *answers: Response) -> MoveOutcome:
    """Feed scripted answers to the phase and return what it produced."""
    pending = list(answers)
    try:
        next(gen)
        while True:
            assert pending, "the phase asked for more than this test scripted"
            gen.send(pending.pop(0))
    except StopIteration as stop:
        assert not pending, f"the phase never asked for {pending}"
        assert isinstance(stop.value, MoveOutcome)
        return stop.value


# --- The offer ----------------------------------------------------------------------


def test_leaving_reach_offers_the_attack_to_the_creature_left(tmp_path: Path) -> None:
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT))

    request = next(_loop(tmp_path).move(state, "mover", AWAY))

    assert isinstance(request, ReactionRequest)
    assert request.reactor_id == "guard"
    assert request.mover_id == "mover"
    assert opportunity_attack_key("spear", "mover") in {a.key for a in request.offered}


def test_a_declined_reaction_spends_nothing_and_the_move_still_happens(tmp_path: Path) -> None:
    """p. 185 says a creature "**can** make" one, so declining is an answer (0072 clause 4)."""
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT))

    outcome = _drive(_loop(tmp_path).move(state, "mover", AWAY), ReactionDeclined())

    assert outcome.reactions == ()
    assert outcome.moved
    assert not outcome.state.combatant("guard").actions.reaction_spent


def test_a_taken_reaction_is_adjudicated_and_the_move_still_happens(tmp_path: Path) -> None:
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT))

    outcome = _drive(
        _loop(tmp_path).move(state, "mover", AWAY), Declared(_take()), Narrated("the spear bites")
    )

    assert [r.status for r in outcome.reactions] == [Status.RULED]
    assert outcome.moved
    assert outcome.state.combatant("mover").position == AWAY


def test_moving_inside_the_reach_offers_nothing(tmp_path: Path) -> None:
    """p. 185 says *leaves* the reach, and the trigger is `provocations`' to decide."""
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT))

    outcome = _drive(_loop(tmp_path).move(state, "mover", Position(5, 5, 0)))

    assert outcome.reactions == ()
    assert outcome.moved


# --- What it costs ------------------------------------------------------------------


def test_the_attack_spends_the_reaction_and_not_the_action(tmp_path: Path) -> None:
    """p. 186's Reaction buys it, and the reactor has no Action to spend on another
    creature's turn. The ordinary `attack:` key charges the Action (p. 176-177), which is the
    whole reason p. 185's offer carries a key of its own (0072 clause 4)."""
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT))

    outcome = _drive(
        _loop(tmp_path).move(state, "mover", AWAY), Declared(_take()), Narrated("struck")
    )

    budget = outcome.state.combatant("guard").actions
    assert budget.reaction_spent
    assert not budget.action_spent
    assert not budget.bonus_action_spent


def test_a_reactor_that_already_attacked_this_turn_is_still_charged(tmp_path: Path) -> None:
    """The Multiattack clause suppresses the Action charge for a creature that has already
    swung this turn, and it must not reach p. 185's attack — a reactor's tally is whatever its
    own turn left there, so falling through would make the Opportunity Attack **free**."""
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT))
    state = state.with_attack_made("guard")

    outcome = _drive(
        _loop(tmp_path).move(state, "mover", AWAY), Declared(_take()), Narrated("struck")
    )

    assert outcome.state.combatant("guard").actions.reaction_spent


# --- Who is not offered one ---------------------------------------------------------


def test_a_reactor_with_no_reaction_left_is_not_asked(tmp_path: Path) -> None:
    spent = ActionBudget().spend(ActionKind.REACTION, Conditions())
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT, actions=spent))

    assert _drive(_loop(tmp_path).move(state, "mover", AWAY)).reactions == ()


def test_a_disengaging_mover_provokes_nobody(tmp_path: Path) -> None:
    """p. 181, reached through `provocations` rather than restated here."""
    mover = _combatant("mover", ORIGIN, actions=ActionBudget(disengaged=True))
    state = _encounter(mover, _armed("guard", GUARD_AT))

    assert _drive(_loop(tmp_path).move(state, "mover", AWAY)).reactions == ()


def test_a_blinded_reactor_is_not_asked(tmp_path: Path) -> None:
    """p. 185 grants the attack against a creature "that you can see"."""
    blinded = Conditions(held=frozenset({Condition.BLINDED}))
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT, conditions=blinded))

    assert _drive(_loop(tmp_path).move(state, "mover", AWAY)).reactions == ()


def test_an_unstated_view_is_reported_as_withheld_rather_than_offered(tmp_path: Path) -> None:
    """An encounter that states no light answers `UNSTATED`, and "the SRD does not say" must
    not become a yes. The clause rides out on the outcome so a caller can see what was not
    asked, rather than the silence looking like nobody was provoked."""
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT), lit=False)

    outcome = _drive(_loop(tmp_path).move(state, "mover", AWAY))

    assert outcome.reactions == ()
    assert outcome.withheld == ("opportunity-attack-sight-unstated",)


def test_a_ranged_weapon_is_not_offered_and_the_unarmed_strike_still_is(tmp_path: Path) -> None:
    """p. 185 grants "one **melee** attack", so the bow is filtered out of the menu.

    The reactor is still asked, and correctly: p. 177 allows "one attack roll with a weapon
    **or an Unarmed Strike**", and a creature holding a bow at five feet can still punch. An
    earlier version of this test asserted nobody was asked, which would have made an empty
    menu the evidence for a rule about melee — two things at once, and the wrong one.
    """
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT, weapon=BOW))

    weapons = {a.detail.get("weapon") for a in reaction_options(state, "guard", "mover")}

    assert "bow" not in weapons, "p. 185 grants a melee attack and a bow is not one"
    assert weapons == {"unarmed-strike"}
    assert isinstance(next(_loop(tmp_path).move(state, "mover", AWAY)), ReactionRequest)


def test_a_ranged_opportunity_attack_is_refused_by_the_resolver_too(tmp_path: Path) -> None:
    """0062: the menu is not a promise, so the rule is asked here as well as there. A caller
    reaching adjudication directly with a bow gets the same answer the menu gave."""
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT, weapon=BOW))

    outcome = _drive(
        _loop(tmp_path).move(state, "mover", AWAY),
        Declared(_take(weapon_id="bow")),
    )

    assert [r.status for r in outcome.reactions] == [Status.REJECTED]
    assert outcome.moved, "a refused reaction does not stop the move"


# --- Ordering, and what a dropped mover does ----------------------------------------


def test_a_mover_dropped_by_the_attack_does_not_move(tmp_path: Path) -> None:
    """0072 clause 3. Not an interruption — the engine states no rule about interrupting
    movement and must not invent one. The attack resolves first, the mover reaches 0, and
    `with_movement` refuses because this engine holds "at 0 hit points a combatant stops
    acting".

    **That refusal was missing until this change**, and the clause first claimed it was
    already built. Nothing applies Unconscious at 0 hit points here, so the Prone route the
    record originally named does not exist — a creature dropped to 0 walked twenty feet.
    """
    state = _encounter(_combatant("mover", ORIGIN, hit_points=1), _armed("guard", GUARD_AT))

    outcome = _drive(
        _loop(tmp_path).move(state, "mover", AWAY), Declared(_take()), Narrated("through")
    )

    assert outcome.state.combatant("mover").hit_points == 0
    assert not outcome.moved
    assert outcome.refusal is not None and "0 hit points" in outcome.refusal
    assert outcome.state.combatant("mover").position == ORIGIN


def test_a_creature_at_zero_hit_points_cannot_be_moved_at_all(tmp_path: Path) -> None:
    """The general form of the rule above, asserted against the state method directly so it
    is not mistaken for something the Opportunity Attack introduced. `legal_actions` has
    refused a downed creature since the read surface shipped; movement never asked."""
    state = _encounter(_combatant("mover", ORIGIN, hit_points=0), _armed("guard", GUARD_AT))

    with pytest.raises(ValueError, match="0 hit points"):
        state.with_movement("mover", AWAY)


# --- The limit this ships disclosed --------------------------------------------------


def test_a_direct_state_move_provokes_nothing(tmp_path: Path) -> None:
    """0072 clause 6. `EncounterState.with_movement` is still callable and still reactionless,
    because the offer needs the agent seam and the seam lives in the loop.

    Pinned rather than left to be discovered: it is the same shape `AGENTS.md` discloses for
    skips — the guarantee holds for callers the turn loop drives.
    """
    state = _encounter(_combatant("mover", ORIGIN), _armed("guard", GUARD_AT))

    moved = state.with_movement("mover", AWAY)

    assert moved.combatant("mover").position == AWAY
    assert not moved.combatant("guard").actions.reaction_spent
    assert moved.combatant("guard").hit_points == 20
