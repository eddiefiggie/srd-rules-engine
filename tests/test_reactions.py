"""What provokes an Opportunity Attack, and the half that is still missing (#381, 0015).

p. 185: *"You can make an Opportunity Attack when a creature that you can see leaves your
reach."* Every clause in that sentence is answerable against state this engine holds — reach
(p. 186), the Reaction budget (p. 186), Incapacitated (p. 184), Disengage (p. 181) — and
**"that you can see" became answerable when #150 read the nine sight pages** on 2026-08-25.

These tests pinned the opposite for five days. `provocations` withheld every offer on a
blocker that had closed, and this module asserted that it did, so the suite defended the
staleness rather than catching it. That is what a guard written against a *reason* rather
than against a *behaviour* does when the reason lapses.

So the shape of the file changes: sight is now asked per reactor, and `can_see`'s three
verdicts are three different results.

* `CAN_SEE` — offerable, `withheld is None`.
* `CANNOT_SEE` — **no provocation at all**. p. 185 grants the attack *when* you can see; a
  reactor who cannot was never owed one, so it is absent rather than withheld.
* `UNSTATED` — withheld, naming `SIGHT_UNSTATED`. The document states no answer for this
  pair, and "the SRD does not say" must not become a no.

**The withholding is still the safe direction, and the opposite of what `core.conditions`
does for Frightened.** There, the qualifier is ignored and the penalty applied, because
erring toward a penalty cannot invent a success. Here, firing an attack the rules would not
grant produces damage out of nothing — an invention rather than an omission — so the error
runs the other way. `test_an_unstated_view_is_withheld_rather_than_offered` is what keeps
that from being quietly reversed by someone reading the withholding as an oversight.

**An encounter that states no light is `UNSTATED`, not Bright.** `Lighting.ambient` of `None`
means nobody has said (0025 clause 2), so a fixture that sets no light gets no offer — which
is why the lit fixture below is explicit about it rather than relying on a default.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core.actions import ActionBudget, ActionKind
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.inventory import load_inventory
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.reactions import (
    OFFER_NEVER_MADE,
    REACTION_VERIFICATION,
    SIGHT_UNSTATED,
    Provocation,
    provocations,
)
from srd_rules_engine.core.read_surface import situation
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.sight import Lighting, LightLevel, Senses
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
    """No lighting stated, so `can_see` answers `UNSTATED` and every offer is withheld."""
    return EncounterState(generation=0, combatants=tuple(combatants))


def _lit(*combatants: Combatant) -> EncounterState:
    """Bright Light everywhere, which is what makes `can_see` answer `CAN_SEE`.

    Stated rather than defaulted: `Lighting()` means nobody has said, and this engine does
    not assume daylight.
    """
    return EncounterState(
        generation=0,
        combatants=tuple(combatants),
        lighting=Lighting(ambient=LightLevel.BRIGHT),
    )


ADJACENT = Position(0, 0, 0)
GUARD_AT = Position(5, 0, 0)
AWAY = Position(30, 0, 0)


# --- The geometry, which is finished ------------------------------------------------


def test_leaving_reach_provokes() -> None:
    state = _encounter(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT))

    found = provocations(state, "mover", frm=ADJACENT, to=AWAY)

    assert found == (Provocation(reactor_id="guard", mover_id="mover", withheld=SIGHT_UNSTATED),)


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


# --- p. 185's sight clause, now that it is answerable --------------------------------


def test_a_reactor_who_can_see_the_mover_may_be_offered_the_attack() -> None:
    """The flip #150 made possible and #381 performed. Bright Light, no obstruction, no
    condition — every clause of p. 185 answered, so nothing is withheld."""
    state = _lit(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT))

    found = provocations(state, "mover", frm=ADJACENT, to=AWAY)

    assert found == (Provocation(reactor_id="guard", mover_id="mover", withheld=None),)
    assert all(p.may_be_offered for p in found)


def test_a_reactor_who_cannot_see_the_mover_provokes_nothing() -> None:
    """Not withheld — **absent**. p. 185 grants the attack *when* you can see the mover, so a
    Blinded reactor is not owed one at all, and reporting a withheld offer would say the
    engine could not answer a question it answered."""
    blinded = Conditions(held=frozenset({Condition.BLINDED}))
    state = _lit(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT, conditions=blinded))

    assert provocations(state, "mover", frm=ADJACENT, to=AWAY) == ()


def test_darkness_is_the_same_refusal_and_reaches_it_through_obscurement() -> None:
    """p. 182: a creature is Blinded while trying to see into a Heavily Obscured space, and
    Darkness is Heavily Obscured. The route differs from the condition above; the answer does
    not, which is what makes it worth asserting separately."""
    state = EncounterState(
        generation=0,
        combatants=(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT)),
        lighting=Lighting(ambient=LightLevel.DARKNESS),
    )

    assert provocations(state, "mover", frm=ADJACENT, to=AWAY) == ()


def test_darkvision_restores_the_offer_that_darkness_took_away() -> None:
    """The negative case for the test above: same Darkness, same geometry, one sense added.
    Without this, that assertion would pass for a `provocations` that consulted nothing about
    senses at all."""
    seer = _combatant("guard", GUARD_AT, senses=Senses(darkvision=60))
    state = EncounterState(
        generation=0,
        combatants=(_combatant("mover", ADJACENT), seer),
        lighting=Lighting(ambient=LightLevel.DARKNESS),
    )

    found = provocations(state, "mover", frm=ADJACENT, to=AWAY)

    assert found == (Provocation(reactor_id="guard", mover_id="mover", withheld=None),)


def test_an_unstated_view_is_withheld_rather_than_offered() -> None:
    """The guard on the whole module. `UNSTATED` is "the document does not say", and turning
    it into a yes would fire an attack the rules may not grant — inventing damage rather than
    omitting it. An encounter that states no light is exactly this case (0025 clause 2)."""
    state = _encounter(_combatant("mover", ADJACENT), _combatant("guard", GUARD_AT))

    found = provocations(state, "mover", frm=ADJACENT, to=AWAY)

    assert found, "the geometry must still be computed — the gap is the answer, not the trigger"
    assert all(not p.may_be_offered for p in found)
    assert all(p.withheld == SIGHT_UNSTATED for p in found)


def test_the_read_surface_says_the_offer_is_the_thing_that_is_missing() -> None:
    """R18. A reaction that is never offered would otherwise look like a rule this engine
    does not have, rather than one it has and does not fire.

    **The clause names the offer, not sight** (#381). It named sight until #150 made sight
    answerable, and then went on naming it for five days — a disclosure accurate that
    something was missing and wrong about what, which 0056 and 0060 each found once before.
    """
    state = _lit(_combatant("pc", ADJACENT))

    assert OFFER_NEVER_MADE in situation(state, "pc").unenforced_clauses


def test_the_disclosure_stands_even_where_sight_is_fully_answerable() -> None:
    """The sharp end of the correction. In Bright Light with no obstruction there is nothing
    sight cannot answer, and the creature is *still* never offered a reaction — so a
    disclosure keyed on sight would have gone quiet here while the gap remained."""
    state = _lit(_combatant("pc", ADJACENT), _combatant("other", GUARD_AT))

    assert OFFER_NEVER_MADE in situation(state, "pc").unenforced_clauses


def test_a_creature_with_no_reaction_left_is_not_told_about_the_clause() -> None:
    spent = ActionBudget().spend(ActionKind.REACTION, Conditions())
    state = _lit(_combatant("pc", ADJACENT, actions=spent))

    assert OFFER_NEVER_MADE not in situation(state, "pc").unenforced_clauses


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
    """The shape the flip took: one field, not a new type."""
    assert replace(Provocation("guard", "mover", SIGHT_UNSTATED), withheld=None).may_be_offered


def test_withheld_has_no_default_so_no_construction_answers_it_silently() -> None:
    """The fail-open direction invents an attack, so the field cannot be allowed to default.

    A default of `None` would make a carelessly-built `Provocation` offerable; a default of a
    clause name would make one that *should* be offerable silently withheld. Requiring it
    removes the question rather than choosing an answer to it.
    """
    with pytest.raises(TypeError):
        Provocation("guard", "mover")  # type: ignore[call-arg]
