"""Who imposed a condition, where the condition's own text turns on it (#192).

p. 182 gives Frightened's Disadvantage "while the source of fear is within line of sight".
`EncounterState.can_see` could answer that after #166 and 0029, and nothing could **ask** it:
this engine recorded no source of fear. `Conditions.grappler_id` was the only source it kept,
added for Grappled's "any target other than the grappler" — the one other conditional clause
it enforced.

So the source became state, and generally rather than one field per condition, because two of
the fifteen already needed one.

**A set per condition, and one condition.** p. 179: "A condition doesn't stack with itself; a
recipient either has a condition or doesn't. The Exhaustion condition is an exception to that
rule." A creature frightened by two monsters holds *one* Frightened condition with two
sources — and that sentence is also why 0028 gave Exhaustion levels instead of a flag.

Two things are tested against the wrong answer:

* **Any source in sight is enough.** p. 182 says "the source of fear" because it describes one
  application; an engine that took the singular literally would need to choose which of two
  the sentence meant, and the document does not say.
* **Not knowing keeps the penalty.** 0030 clause 1: applying a Disadvantage the rules may not
  require can only omit a hit, while dropping one they do require produces damage that should
  not exist.
"""

from __future__ import annotations

from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.obstructions import Obstruction
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.sight import Lighting, LightLevel
from srd_rules_engine.core.state import Combatant, EncounterState

OPAQUE = Obstruction(lo=Position(10, -20, 0), hi=Position(12, 20, 20), blocks_sight=True)
UNDESCRIBED = Obstruction(lo=Position(10, -20, 0), hi=Position(12, 20, 20))


def creature(
    cid: str, where: Position, *, frightened_by: frozenset[str] = frozenset()
) -> Combatant:
    conditions = (
        Conditions(
            held=frozenset({Condition.FRIGHTENED}),
            sources={Condition.FRIGHTENED: frightened_by},
        )
        if frightened_by
        else Conditions()
    )
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 12},
        proficiency_bonus=2,
        position=where,
        conditions=conditions,
    )


def scene(
    *, frightened_by: frozenset[str] = frozenset({"ogre"}), walls: tuple[Obstruction, ...] = ()
) -> EncounterState:
    return EncounterState(
        generation=0,
        combatants=(
            creature("pc", Position(0, 0, 0), frightened_by=frightened_by),
            creature("ogre", Position(30, 0, 0)),
            creature("wolf", Position(0, 30, 0)),
        ),
        lighting=Lighting(ambient=LightLevel.BRIGHT),
        obstructions=walls,
    )


# --- The source is state now --------------------------------------------------------------


def test_a_condition_records_who_imposed_it() -> None:
    applied = EncounterState.new([creature("pc", Position(0, 0, 0))]).with_condition(
        "pc", Condition.FRIGHTENED, source_id="ogre"
    )
    assert applied.combatant("pc").conditions.sources_of(Condition.FRIGHTENED) == {"ogre"}


def test_a_second_application_adds_a_source_rather_than_a_condition() -> None:
    """p. 179: "A condition doesn't stack with itself; a recipient either has a condition or
    doesn't." So two frighteners make one condition and two sources."""
    state = EncounterState.new([creature("pc", Position(0, 0, 0))])
    state = state.with_condition("pc", Condition.FRIGHTENED, source_id="ogre")
    state = state.with_condition("pc", Condition.FRIGHTENED, source_id="wolf")

    held = state.combatant("pc").conditions
    assert held.sources_of(Condition.FRIGHTENED) == {"ogre", "wolf"}
    assert tuple(c for c in held.held if c is Condition.FRIGHTENED) == (Condition.FRIGHTENED,)


def test_the_grappler_still_reads_as_one_name() -> None:
    """`grappler_id` survives the generalisation as a lookup. p. 182 speaks of one grappler
    and this engine keeps the singular reading."""
    state = EncounterState.new([creature("pc", Position(0, 0, 0))]).with_condition(
        "pc", Condition.GRAPPLED, source_id="ogre"
    )
    assert state.combatant("pc").conditions.grappler_id == "ogre"


def test_ending_a_condition_forgets_its_source() -> None:
    state = EncounterState.new([creature("pc", Position(0, 0, 0))]).with_condition(
        "pc", Condition.FRIGHTENED, source_id="ogre"
    )
    ended = state.with_condition_ended("pc", Condition.FRIGHTENED)
    assert ended.combatant("pc").conditions.sources_of(Condition.FRIGHTENED) == frozenset()


# --- The qualifier, asked at last -----------------------------------------------------------


def test_a_visible_source_keeps_the_penalty() -> None:
    assert scene().fear_in_sight("pc") is True
    assert (
        scene()
        .combatant("pc")
        .conditions.own_attack_rolls(fear_in_sight=scene().fear_in_sight("pc"))
        is Advantage.DISADVANTAGE
    )


def test_an_opaque_wall_between_them_lifts_it() -> None:
    """p. 182's qualifier, which could not be asked before this issue. Breaking line of sight
    is the point of breaking line of sight."""
    state = scene(walls=(OPAQUE,))
    assert state.fear_in_sight("pc") is False
    assert state.combatant("pc").conditions.own_attack_rolls(fear_in_sight=False) is (
        Advantage.NONE
    )


def test_an_undescribed_wall_keeps_the_penalty() -> None:
    """0030 clause 1. `can_see` answers UNSTATED, and UNSTATED is not "out of sight" —
    dropping a Disadvantage the rules require produces damage that should not exist."""
    assert scene(walls=(UNDESCRIBED,)).fear_in_sight("pc") is True


def test_any_source_in_sight_is_enough() -> None:
    """The ogre is hidden and the wolf is not. p. 182 says "the source of fear" because it
    describes one application; with two, an engine that took the singular literally would
    have to choose which the sentence meant, and the document does not say."""
    state = scene(frightened_by=frozenset({"ogre", "wolf"}), walls=(OPAQUE,))
    assert state.fear_in_sight("pc") is True, "the wolf is still in plain view"


def test_every_source_hidden_lifts_it() -> None:
    """Two walls, one per source. A single box around everything would not do it: a creature
    standing *inside* an obstruction is not blocked from itself (#91)."""
    from_the_wolf = Obstruction(lo=Position(-20, 10, 0), hi=Position(20, 12, 20), blocks_sight=True)
    state = scene(frightened_by=frozenset({"ogre", "wolf"}), walls=(OPAQUE, from_the_wolf))
    assert state.fear_in_sight("pc") is False


def test_a_creature_with_no_recorded_source_keeps_the_penalty() -> None:
    """Every Frightened creature, until a caller starts naming them. The safe direction is
    the one that omits nothing (0030 clause 1)."""
    state = EncounterState.new([creature("pc", Position(0, 0, 0))]).with_condition(
        "pc", Condition.FRIGHTENED
    )
    assert state.fear_in_sight("pc") is True


def test_a_creature_that_is_not_frightened_is_not_asked() -> None:
    state = EncounterState.new([creature("pc", Position(0, 0, 0))])
    assert state.fear_in_sight("pc") is True
