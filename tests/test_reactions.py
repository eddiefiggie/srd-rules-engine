"""What provokes an Opportunity Attack, and why nothing is offered (#16, 0015).

p. 185: *"You can make an Opportunity Attack when a creature that you can see leaves your
reach."* Every clause in that sentence is answerable against state this engine already holds
— reach (p. 186), the Reaction budget (p. 186), Incapacitated (p. 184), Disengage (p. 181) —
except **"that you can see"**, which needs the light-and-sense mapping that ships empty until
#150.

So `provocations` computes who *would* be provoked and withholds every offer, naming the
clause it is waiting on. These tests pin both halves: the geometry, which is finished, and
the withholding, which is not a bug to be fixed by removing the check.

**The withholding is the safe direction, and the opposite of what `core.conditions` does for
Frightened.** There, the qualifier is ignored and the penalty applied, because erring toward
a penalty cannot invent a success. Here, firing an attack the rules would not grant produces
damage out of nothing — an invention rather than an omission — so the error runs the other
way. `test_no_offer_may_be_made_while_sight_is_unanswerable` is what keeps that from being
quietly reversed by someone who reads the withholding as an oversight.
"""

from __future__ import annotations

from dataclasses import replace

from srd_rules_engine.core.actions import ActionBudget, ActionKind
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.inventory import load_inventory
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.reactions import (
    REACTION_VERIFICATION,
    SIGHT_QUALIFIER,
    Provocation,
    provocations,
)
from srd_rules_engine.core.read_surface import situation
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 12, "dex": 14, "con": 12, "int": 10, "wis": 12, "cha": 8}


def _combatant(cid: str, position: Position | None, **kwargs: object) -> Combatant:
    base: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 10,
        "max_hit_points": 10,
        "armour_class": 13,
        "abilities": ABILITIES,
        "proficiency_bonus": 2,
        "position": position,
    }
    base.update(kwargs)
    return Combatant(**base)  # type: ignore[arg-type]


def _encounter(*combatants: Combatant) -> EncounterState:
    return EncounterState(generation=0, combatants=tuple(combatants))


ADJACENT = Position(0, 0, 0)
GUARD_AT = Position(5, 0, 0)
AWAY = Position(30, 0, 0)


# --- The geometry, which is finished ------------------------------------------------


def test_leaving_reach_provokes() -> None:
    state = _encounter(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT))

    found = provocations(state, "mover", frm=ADJACENT, to=AWAY)

    assert found == (Provocation(reactor_id="guard", mover_id="mover"),)


def test_moving_within_reach_does_not_provoke() -> None:
    """p. 185 says *leaves* the reach. Shuffling around inside it is not a trigger, which is
    the clause a distance check alone would miss."""
    state = _encounter(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT))

    assert provocations(state, "mover", frm=ADJACENT, to=Position(5, 5, 0)) == ()


def test_moving_while_already_out_of_reach_does_not_provoke() -> None:
    """Never in reach, so nothing was left."""
    state = _encounter(_combatant("mover", AWAY), _combatant("guard", GUARD_AT))

    assert provocations(state, "mover", frm=AWAY, to=Position(60, 0, 0)) == ()


def test_reach_decides_what_counts_as_leaving() -> None:
    """`reach` is a field because p. 186 makes 5 feet a default rather than a constant. The
    same move leaves one creature's reach and stays inside another's."""
    ogre = _encounter(_combatant("mover", ADJACENT), _combatant("ogre", GUARD_AT, reach=10))
    guard = _encounter(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT))
    seven_feet_from_both = Position(12, 0, 0)

    assert provocations(ogre, "mover", frm=ADJACENT, to=seven_feet_from_both) == ()
    assert provocations(guard, "mover", frm=ADJACENT, to=seven_feet_from_both)


def test_a_mover_does_not_provoke_itself() -> None:
    state = _encounter(_combatant("mover", ADJACENT))

    assert provocations(state, "mover", frm=ADJACENT, to=AWAY) == ()


def test_an_encounter_with_no_positions_provokes_nothing() -> None:
    """The same silence `with_movement` gives a creature with no position: a question the
    encounter cannot answer, rather than one answered by assuming a layout."""
    state = _encounter(_combatant("mover", ADJACENT), _combatant("guard", None))

    assert provocations(state, "mover", frm=ADJACENT, to=AWAY) == ()


def test_every_reactor_in_reach_is_named_not_only_the_first() -> None:
    state = _encounter(
        _combatant("mover", ADJACENT),
        _combatant("guard", GUARD_AT),
        _combatant("archer", Position(0, 5, 0)),
    )

    found = provocations(state, "mover", frm=ADJACENT, to=AWAY)

    assert [p.reactor_id for p in found] == ["archer", "guard"], "id order, so replay is stable"


# --- What suppresses one ------------------------------------------------------------


def test_disengaging_suppresses_provocation() -> None:
    """p. 181: "your movement doesn't provoke Opportunity Attacks for the rest of the current
    turn." The flag existed and nothing consumed it until now (0015)."""
    mover = _combatant("mover", ADJACENT, actions=ActionBudget(disengaged=True))
    state = _encounter(mover, _combatant("guard", GUARD_AT))

    assert provocations(state, "mover", frm=ADJACENT, to=AWAY) == ()


def test_a_reactor_with_no_reaction_left_does_not_provoke() -> None:
    spent = ActionBudget().spend(ActionKind.REACTION, Conditions())
    state = _encounter(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT, actions=spent))

    assert provocations(state, "mover", frm=ADJACENT, to=AWAY) == ()


def test_an_incapacitated_reactor_does_not_provoke() -> None:
    """p. 184: Incapacitated stops reactions. Reached through the budget's own check rather
    than re-stated here, so the two cannot disagree."""
    held = Conditions(held=frozenset({Condition.INCAPACITATED}))
    state = _encounter(
        _combatant("mover", ADJACENT), _combatant("guard", GUARD_AT, conditions=held)
    )

    assert provocations(state, "mover", frm=ADJACENT, to=AWAY) == ()


# --- The clause that is not answerable ----------------------------------------------


def test_no_offer_may_be_made_while_sight_is_unanswerable() -> None:
    """The guard on the whole module. Removing the withholding would fire an attack the
    rules may not grant, which invents damage rather than omitting it."""
    state = _encounter(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT))

    found = provocations(state, "mover", frm=ADJACENT, to=AWAY)

    assert found, "the geometry must still be computed — the gap is the offer, not the trigger"
    assert all(not p.may_be_offered for p in found)
    assert all(p.withheld == SIGHT_QUALIFIER for p in found)


def test_the_read_surface_says_the_clause_is_held_and_not_applied() -> None:
    """R18. A reaction that is never offered would otherwise look like a rule this engine
    does not have, rather than one it has and cannot fire."""
    state = _encounter(_combatant("pc", ADJACENT))

    assert SIGHT_QUALIFIER in situation(state, "pc").unenforced_clauses


def test_a_creature_with_no_reaction_left_is_not_told_about_the_clause() -> None:
    spent = ActionBudget().spend(ActionKind.REACTION, Conditions())
    state = _encounter(_combatant("pc", ADJACENT, actions=spent))

    assert SIGHT_QUALIFIER not in situation(state, "pc").unenforced_clauses


def test_the_opportunity_attack_shape_is_not_claimed() -> None:
    """A trigger that cannot fire has not resolved the shape. The inventory is what makes
    "full SRD 5.2 coverage" falsifiable, and a shape marked on machinery alone breaks it."""
    shape = next(s for s in load_inventory().shapes if s.id == "opportunity-attacks")
    assert not shape.implemented


def test_every_sentence_this_module_uses_is_asserted() -> None:
    """R31. The four pages are already clauses in `scripts/verify_d20_rules.py`, so this
    module transcribes nothing new — which is why it could be written without the document."""
    assert REACTION_VERIFICATION.state is VerificationState.VERIFIED
    reference = REACTION_VERIFICATION.reference or ""
    assert all(page in reference for page in ("p. 185", "p. 186", "p. 184", "p. 181"))


def test_a_provocation_that_could_be_offered_says_so() -> None:
    """The shape the flip takes when #150 lands: one field, not a new type."""
    assert replace(Provocation("guard", "mover"), withheld=None).may_be_offered
