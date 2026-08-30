"""The initiative rules, against the pages they come from (#385, 0075).

`scripts/verify_d20_rules.py` carried **no initiative clause at all**, and `core.combat` held
`Verification` objects for weapon properties and the Unarmed Strike only. So every initiative
rule the engine implemented or declined to implement was unasserted — including the two that
had been decided by default rather than by reading:

* **which ability is rolled.** `initiative_order` took `ability` as an argument with a `"dex"`
  default, and the module said why: "which ability the modifier comes from is a rule with a
  section citation, so it is a *parameter* rather than a constant here". Correct while the
  page was unread, and the wrong shape once it was.
* **what happens on a tie.** `with_initiative` broke them by insertion order and called it
  "the order given", which is a convention. Whether it matched the document was checkable by
  nobody, because the document had not been checked.

Reading p. 13 answered both, and the second answer is the one worth having: **the SRD assigns
ties to a person.** There is no rule here to implement, and an engine that invented one would
be inventing a decision the document gave away.
"""

from __future__ import annotations

import inspect

from srd_rules_engine.core.combat import (
    INITIATIVE_ABILITY,
    INITIATIVE_VERIFICATION,
    initiative_order,
)
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 20, "dex": 6, "con": 10, "int": 10, "wis": 10, "cha": 10}


def _combatant(cid: str, **kwargs: object) -> Combatant:
    base: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 10,
        "max_hit_points": 10,
        "armour_class": 12,
        "abilities": ABILITIES,
        "proficiency_bonus": 2,
    }
    base.update(kwargs)
    return Combatant(**base)  # type: ignore[arg-type]


# --- The pages this module rests on --------------------------------------------------


def test_the_initiative_rules_are_asserted_against_their_pages() -> None:
    """R31. `core.combat` held no initiative verification at all until #385, so the rules
    below were machinery asserted by nobody."""
    assert INITIATIVE_VERIFICATION.state is VerificationState.VERIFIED
    reference = INITIATIVE_VERIFICATION.reference or ""
    assert "p. 13" in reference
    assert "p. 184" in reference


# --- Which ability ---------------------------------------------------------------------


def test_initiative_rolls_dexterity_and_a_caller_cannot_choose() -> None:
    """p. 13: "they make a **Dexterity check** that determines their place in the Initiative
    order."

    The fixture's abilities are deliberately lopsided — Strength 20, Dexterity 6 — so a roll
    that consulted the wrong ability would come out visibly different rather than coincide.
    """
    assert INITIATIVE_ABILITY == "dex"
    assert "ability" not in inspect.signature(initiative_order).parameters

    creature = _combatant("a")
    state = EncounterState.new([creature, _combatant("b")])

    rolled = initiative_order(state, seed=7)

    # -2 for Dexterity 6, and emphatically not +5 for Strength 20.
    assert all(value <= 20 - 2 for value in rolled.values())


# --- Ties ------------------------------------------------------------------------------


def test_a_tie_breaks_by_the_order_given_and_that_is_a_convention() -> None:
    """p. 13, *Ties*: "the GM decides the order among tied monsters, and the players decide
    the order among tied characters."

    **The document assigns ties to a person rather than leaving them open**, so there is no
    rule here for the engine to implement. Insertion order is a convention it declares — the
    construction `Lighting` uses for overlapping volumes — and the person's decision reaches
    the engine as the order the combatants are passed in.
    """
    first = EncounterState.new([_combatant("alice"), _combatant("bob")])
    second = EncounterState.new([_combatant("bob"), _combatant("alice")])
    tied = {"alice": 15, "bob": 15}

    assert [c.id for c in first.with_initiative(tied).combatants] == ["alice", "bob"]
    assert [c.id for c in second.with_initiative(tied).combatants] == ["bob", "alice"]


def test_the_order_is_highest_to_lowest_and_survives_the_round() -> None:
    """p. 13: "The GM ranks the combatants, from highest to lowest Initiative … The
    Initiative order remains the same from round to round." Sorted once and never re-sorted.
    """
    state = EncounterState.new([_combatant("slow"), _combatant("quick")])

    ordered = state.with_initiative({"slow": 3, "quick": 18})
    assert [c.id for c in ordered.combatants] == ["quick", "slow"]

    later = ordered.advanced_turn().advanced_turn()
    assert later.round_number == 2
    assert [c.id for c in later.combatants] == ["quick", "slow"], "the order does not re-sort"
