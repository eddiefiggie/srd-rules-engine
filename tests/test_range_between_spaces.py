"""A range runs from the edge of a space, as the grid measures it (#456, 0086).

> p. 13, *Ranges*. To determine the range on a grid between two things — whether creatures or
> objects — count squares from a square adjacent to one of them and stop counting in the space
> of the other one. Count by the shortest route.

In feet along 0014's straight line: the distance between two points, less what each thing's
space exceeds one square. A Medium creature's excess is zero, so every range test that held
before 0086 holds after it; what changed is that a Medium creature reaches a Huge one from ten
feet away, five of them the giant's own. Each consumer of a range is asserted here with the
same pair — a Huge creature in range from where a Medium one is not — because a reach
measured one way for attacks and another for Opportunity Attacks is a creature that can hit
what it could not stop leaving.
"""

from __future__ import annotations

from fractions import Fraction

import pytest

from srd_rules_engine.core import Combatant, Condition, Conditions, EncounterState, Grapple
from srd_rules_engine.core.combat import _hit_is_automatically_critical, _out_of_range
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.equipment import (
    Carriage,
    Carried,
    DetachedObject,
    Weapon,
    reachable_objects,
)
from srd_rules_engine.core.grappling import ended_by_circumstance
from srd_rules_engine.core.position import Position, distance_feet, within
from srd_rules_engine.core.reactions import provocations
from srd_rules_engine.core.read_surface import cleave_attack_key, read
from srd_rules_engine.core.sight import Lighting, LightLevel, Senses, Visibility
from srd_rules_engine.core.size import SPACE_FEET, Size, range_slack
from srd_rules_engine.core.spellcasting import RangeForm, SpellRange, spell_reaches

ORIGIN = Position(0, 0, 0)
#: Ten feet along x: in reach of a Huge creature's edge and out of reach of a Medium one's.
TEN = Position(10, 0, 0)

SPEAR = Weapon(id="spear", weight=3, damage_dice=1, damage_sides=6, ability="str", melee=True)
GREATAXE = Weapon(
    id="fixture:greataxe",
    weight=7,
    damage_dice=1,
    damage_sides=12,
    ability="str",
    melee=True,
    cleave=True,
    hands_when_held=2,
)


def _creature(
    cid: str, position: Position | None = ORIGIN, *, size: Size | None = Size.MEDIUM, **kw: object
) -> Combatant:
    base: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 12,
        "abilities": {"str": 14, "dex": 12, "con": 12},
        "proficiency_bonus": 2,
        "position": position,
        "size": size,
    }
    base.update(kw)
    return Combatant(**base)  # type: ignore[arg-type]


def _lit(*combatants: Combatant, ambient: LightLevel = LightLevel.BRIGHT) -> EncounterState:
    state = EncounterState(
        generation=0, combatants=tuple(combatants), lighting=Lighting(ambient=ambient)
    )
    return state.with_initiative({c.id: 20 - i for i, c in enumerate(combatants)})


# --- The measure ---------------------------------------------------------------------------


def test_the_excess_is_what_a_space_has_beyond_one_square() -> None:
    """p. 14's table, less 2½ feet, floored at zero: Tiny is not further away for being small
    (0086 clause 3), and the three sizes that fit one square add nothing."""
    assert {size: size.range_excess for size in Size} == {
        Size.TINY: Fraction(0),
        Size.SMALL: Fraction(0),
        Size.MEDIUM: Fraction(0),
        Size.LARGE: Fraction(5, 2),
        Size.HUGE: Fraction(5),
        Size.GARGANTUAN: Fraction(15, 2),
    }
    for size in Size:
        assert size.range_excess == max(Fraction(0), SPACE_FEET[size] / 2 - Fraction(5, 2))


def test_the_slack_sums_both_spaces_and_an_unsized_creature_adds_nothing() -> None:
    assert range_slack(Size.HUGE, Size.LARGE) == Fraction(15, 2)
    assert range_slack(Size.MEDIUM, Size.MEDIUM) == 0
    assert range_slack(None, Size.HUGE) == Fraction(5), "unknown is not Medium, and not larger"
    assert range_slack() == 0


def test_within_is_exact_at_a_half_foot_boundary() -> None:
    """A Large creature's excess is 2½ feet, so a Medium attacker with 5 feet of reach reaches
    it from 7 and not from 8 — a boundary no integer lands on, decided by squaring a Fraction."""
    slack = range_slack(Size.MEDIUM, Size.LARGE)
    assert within(ORIGIN, Position(7, 0, 0), 5, slack=slack)
    assert not within(ORIGIN, Position(8, 0, 0), 5, slack=slack)
    with pytest.raises(ValueError, match="nothing further away"):
        within(ORIGIN, TEN, 5, slack=Fraction(-1))


def test_the_diagonal_stays_a_straight_line() -> None:
    """0086 clause 2: the grid would call a Medium creature at (10, 10) adjacent to a Huge one at
    the origin; the straight line 0014 drew says 14.1 less 5, and that is not 5. The same
    deviation the engine already has for two Medium creatures at (5, 5), and no second kind."""
    assert not within(ORIGIN, Position(10, 10, 0), 5, slack=range_slack(Size.HUGE, Size.MEDIUM))
    assert not within(ORIGIN, Position(5, 5, 0), 5)


def test_distance_feet_takes_the_slack_off_before_rounding() -> None:
    huge = range_slack(Size.HUGE)
    assert distance_feet(ORIGIN, Position(14, 0, 0), slack=huge) == 9
    assert distance_feet(ORIGIN, Position(3, 4, 0), slack=huge) == 0, "inside, not negative"
    # The largest whole n with (n + 5)² ≤ 10² + 10²: 14.14 - 5 = 9.14, so 9.
    assert distance_feet(ORIGIN, Position(10, 10, 0), slack=huge) == 9
    assert distance_feet(ORIGIN, Position(10, 10, 0)) == 14, "unchanged without a slack"


# --- Every consumer, with the same pair ---------------------------------------------------


def _armed(cid: str, position: Position, size: Size) -> Combatant:
    return _creature(
        cid, position, size=size, equipment=(Carried(item=SPEAR, carriage=Carriage.HELD),)
    )


def test_a_melee_attack_reaches_a_huge_creature_from_ten_feet_and_a_medium_one_does_not() -> None:
    attacker = _armed("pc", ORIGIN, Size.MEDIUM)
    assert not _out_of_range(SPEAR, attacker, _creature("giant", TEN, size=Size.HUGE))
    with pytest.raises(ValueError, match="10 feet away"):
        _out_of_range(SPEAR, attacker, _creature("foe", TEN, size=Size.MEDIUM))


def test_the_attackers_own_space_counts_too() -> None:
    """p. 13 counts "from a square adjacent to one of them", whichever: a Huge attacker reaches
    a Medium creature ten feet from its point, five of them its own."""
    giant = _armed("giant", ORIGIN, Size.HUGE)
    assert not _out_of_range(SPEAR, giant, _creature("pc", TEN, size=Size.MEDIUM))


def test_leaving_a_huge_creatures_reach_provokes_from_where_a_medium_one_could_not_reach() -> None:
    """p. 185, through `_left_reach`: the reactor's space and the mover's both shorten the
    reach, so a Medium guard is left by a Huge creature walking off from ten feet."""
    guard = _armed("guard", ORIGIN, Size.MEDIUM)
    giant = _lit(guard, _creature("giant", TEN, size=Size.HUGE))
    walker = _lit(guard, _creature("walker", TEN, size=Size.MEDIUM))

    assert [p.reactor_id for p in provocations(giant, "giant", frm=TEN, to=Position(30, 0, 0))] == [
        "guard"
    ]
    assert provocations(walker, "walker", frm=TEN, to=Position(30, 0, 0)) == ()


def test_an_unconscious_huge_creature_is_hit_critically_from_ten_feet() -> None:
    """p. 191: a Critical Hit "if the attacker is within 5 feet of you"."""
    out_cold = Conditions(applied=frozenset({Condition.UNCONSCIOUS}))
    attacker = _creature("pc", ORIGIN)
    assert _hit_is_automatically_critical(
        attacker, _creature("giant", TEN, size=Size.HUGE, conditions=out_cold)
    )
    assert not _hit_is_automatically_critical(
        attacker, _creature("foe", TEN, size=Size.MEDIUM, conditions=out_cold)
    )


def test_a_prone_huge_creature_gives_advantage_from_ten_feet() -> None:
    """p. 186: Advantage "if the attacker is within 5 feet", Disadvantage otherwise."""
    prone = Conditions(applied=frozenset({Condition.PRONE}))
    near = prone.attack_rolls_against(
        attacker=ORIGIN, target=TEN, slack=range_slack(Size.MEDIUM, Size.HUGE)
    )
    far = prone.attack_rolls_against(attacker=ORIGIN, target=TEN, slack=range_slack(Size.MEDIUM))
    assert near is Advantage.ADVANTAGE
    assert far is Advantage.DISADVANTAGE


def _hewer() -> Combatant:
    return _creature(
        "pc",
        ORIGIN,
        hands=2,
        equipment=(Carried(GREATAXE, Carriage.HELD),),
        weapon_proficiencies=frozenset({GREATAXE.id}),
        mastery_weapons=frozenset({GREATAXE.id}),
    )


def _cleave_keys(second: Combatant) -> set[str]:
    boar = _creature("boar", Position(4, 0, 0))
    state = _lit(_hewer(), boar, second).with_cleave_opening("pc", GREATAXE.id, "boar")
    return {a.key for a in read(state.with_attack_made("pc"), "pc").actions}


def test_cleaves_reach_is_measured_to_the_second_creatures_space() -> None:
    """Nine feet from the wielder and five from the first target: the spread holds for either
    size, so only the reach separates them, and a Huge second creature is in it."""
    assert cleave_attack_key(GREATAXE.id, "giant") in _cleave_keys(
        _creature("giant", Position(9, 0, 0), size=Size.HUGE)
    )
    assert cleave_attack_key(GREATAXE.id, "ogre") not in _cleave_keys(
        _creature("ogre", Position(9, 0, 0), size=Size.MEDIUM)
    )


def test_cleaves_spread_is_measured_to_the_second_creatures_space() -> None:
    """Nine feet from the first target and 9.85 from the wielder: a Huge creature is within
    five of both once its space comes off, and a Medium one is within neither."""
    assert cleave_attack_key(GREATAXE.id, "giant") in _cleave_keys(
        _creature("giant", Position(4, 9, 0), size=Size.HUGE)
    )
    assert cleave_attack_key(GREATAXE.id, "ogre") not in _cleave_keys(
        _creature("ogre", Position(4, 9, 0), size=Size.MEDIUM)
    )


def _grappled_by(grappler_id: str) -> Conditions:
    return Conditions(
        applied=frozenset({Condition.GRAPPLED}),
        sources={Condition.GRAPPLED: frozenset({grappler_id})},
        grapple=Grapple(escape_dc=13, range_feet=5),
    )


def test_a_huge_grappler_holds_from_ten_feet_where_a_medium_one_has_let_go() -> None:
    """p. 182 ends a grapple when the distance "exceeds the grapple's range"."""
    captive = _creature("pc", TEN, conditions=_grappled_by("ogre"))
    giant = EncounterState.new([_creature("ogre", ORIGIN, size=Size.HUGE), captive])
    man = EncounterState.new([_creature("ogre", ORIGIN, size=Size.MEDIUM), captive])

    assert ended_by_circumstance(giant) == ()
    assert ended_by_circumstance(man) == ("pc",)


def test_darkvision_reaches_a_huge_creature_its_range_would_not_reach_the_point_of() -> None:
    """pp. 177, 180, 190: a sense's range, measured to the space. Twenty-four feet is beyond a
    20-foot Darkvision to a point, and within it to a Huge creature's edge."""
    watcher = _creature("watcher", ORIGIN, senses=Senses(darkvision=20))
    far = Position(24, 0, 0)
    giant = _lit(watcher, _creature("giant", far, size=Size.HUGE), ambient=LightLevel.DARKNESS)
    man = _lit(watcher, _creature("man", far, size=Size.MEDIUM), ambient=LightLevel.DARKNESS)

    assert giant.can_see("watcher", "giant").verdict is Visibility.CAN_SEE
    assert man.can_see("watcher", "man").verdict is Visibility.CANNOT_SEE


def test_a_huge_creature_reaches_an_object_ten_feet_from_its_point() -> None:
    """0041's objects are points and add nothing; the reacher's own space still counts."""
    dropped = DetachedObject(item=SPEAR, position=TEN)
    assert reachable_objects((dropped,), ORIGIN, 5, slack=range_slack(Size.HUGE)) == (dropped,)
    assert reachable_objects((dropped,), ORIGIN, 5, slack=range_slack(Size.MEDIUM)) == ()


def test_a_spells_range_runs_from_the_casters_space() -> None:
    """p. 105: Touch "within their reach", Distance in feet — both from the caster, whose space
    is the only one on the line, because the origin is a point."""
    touch = SpellRange(RangeForm.TOUCH)
    assert spell_reaches(
        TEN, caster=ORIGIN, spell_range=touch, reach_feet=5, caster_slack=range_slack(Size.HUGE)
    )
    assert not spell_reaches(TEN, caster=ORIGIN, spell_range=touch, reach_feet=5)
    thirty = SpellRange(RangeForm.DISTANCE, feet=30)
    assert spell_reaches(
        Position(34, 0, 0),
        caster=ORIGIN,
        spell_range=thirty,
        reach_feet=5,
        caster_slack=range_slack(Size.HUGE),
    )
    assert not spell_reaches(Position(34, 0, 0), caster=ORIGIN, spell_range=thirty, reach_feet=5)


# --- The callers that pass the slack, proved through their own doors ------------------------


def test_the_attack_path_passes_the_slack_to_prones_adjacency() -> None:
    """`core.combat` hands `attack_rolls_against` the pair's slack, so a Prone Huge creature
    ten feet away is attacked with Advantage — adjacent by p. 13 — where a point-to-point
    reading would have called the same attack Disadvantaged from out of reach."""
    from srd_rules_engine.core import Declaration, Intent, attack_resolver
    from srd_rules_engine.core.read_surface import attack_key

    prone = Conditions(applied=frozenset({Condition.PRONE}))
    state = _lit(
        _armed("pc", ORIGIN, Size.MEDIUM), _creature("giant", TEN, size=Size.HUGE, conditions=prone)
    )
    proposal = attack_resolver()(
        state=state,
        declaration=Declaration(
            actor_id="pc", intent=Intent(action_key=attack_key(SPEAR.id, "giant")), rule_id="attack"
        ),
        facts={},
    )
    assert proposal.test is not None
    assert proposal.test.has_advantage and not proposal.test.has_disadvantage


def test_the_read_surface_offers_an_object_a_huge_creature_can_reach() -> None:
    """The four `reachable_objects` sites pass the actor's own space."""
    dropped = DetachedObject(
        item=Weapon(
            id="dropped-spear", weight=3, damage_dice=1, damage_sides=6, ability="str", melee=True
        ),
        position=TEN,
    )

    def offered(size: Size) -> set[str]:
        state = _lit(
            _creature("pc", ORIGIN, size=size, hands=2), _creature("foe", Position(3, 0, 0))
        )
        state = EncounterState(
            **{
                **{f: getattr(state, f) for f in state.__dataclass_fields__},
                "detached_objects": (dropped,),
            }
        )
        return {a.key for a in read(state, "pc").actions if "dropped-spear" in a.key}

    assert offered(Size.HUGE), "a Huge creature reaches ten feet past its point"
    assert not offered(Size.MEDIUM), "a Medium one does not"


def test_perception_measures_a_sense_to_the_targets_space() -> None:
    """`perception_of` is the second site that reads a distance for a sense. Twenty-four feet
    in darkness is Heavily Obscured to a 20-foot Darkvision when the target is a point, and
    Dim Light when it is a Huge creature whose edge is nineteen feet off."""
    watcher = _creature("watcher", ORIGIN, senses=Senses(darkvision=20))
    far = Position(24, 0, 0)
    giant = _lit(watcher, _creature("giant", far, size=Size.HUGE), ambient=LightLevel.DARKNESS)
    man = _lit(watcher, _creature("man", far, size=Size.MEDIUM), ambient=LightLevel.DARKNESS)

    assert "Heavily Obscured" in man.perception_of("watcher", "man").because
    assert "Heavily Obscured" not in giant.perception_of("watcher", "giant").because
