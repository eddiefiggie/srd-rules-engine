"""The end of a turn is a phase the loop owns, and it rolls what it owes (#110, 0023).

`Conditions.saves_due_after` reported a repeated save from the day #18 landed, and nothing
ever rolled it. Two docstrings promised "the turn loop consults it"; decision 0023 found
why it never did — `TurnLoop.run` is a *declaration slot*, `advanced_turn` is called by the
caller, and **nothing owned the end of a turn**. There was no moment for the save to happen
in.

So the tests here are about a phase existing and being impossible to skip, rather than about
p. 63's arithmetic:

* **An obligation is derived, never declared** (clause 2). p. 63 gives the creature no
  choice about repeating the save, so a declaration slot — one in which declining is
  expressible — would be offering a decision the document does not give.
* **The outcome still goes through the one entry point** (clause 3). This is a second
  *occasion* on which the existing path is taken, not a second path.
* **`advanced_turn` refuses while an obligation stands** (clause 6). That is what makes the
  skip structurally impossible rather than serviced by well-behaved callers — and it is the
  clause 0023 said it was least confident in, so it gets the most tests.

The death save is deliberately absent, and `test_the_death_save_is_not_wired_and_says_why`
holds that line: `core.death` never states *when* a death save is made, and assuming it
shares p. 63's timing would be inferring a rule value (R31).
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Combatant,
    Condition,
    EncounterState,
    Ledger,
    ObligationOutstanding,
    SaveEnds,
    Status,
    load_ruleset,
    save_ends_resolvers,
    save_ends_rule_id,
    save_ends_rules,
)
from srd_rules_engine.loop import TurnEnd, TurnLoop
from srd_rules_engine.loop.drivers import ScriptedDriver, drive
from srd_rules_engine.memory.store import JsonMemoryStore

POISON = SaveEnds(ability="con", dc=13)
#: A DC nothing can fail: the modifier is at worst -5 and the d20 at worst 1.
ALWAYS = SaveEnds(ability="con", dc=1)
#: A DC nothing can make: 30 is beyond 20 plus any modifier this fixture carries.
NEVER = SaveEnds(ability="con", dc=30)


def fighter(combatant_id: str, name: str) -> Combatant:
    return Combatant(
        id=combatant_id,
        name=name,
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 14, "dex": 12, "con": 14},
        proficiency_bonus=2,
    )


def encounter() -> EncounterState:
    state = EncounterState.new([fighter("first", "First"), fighter("second", "Second")])
    return state.with_initiative({"first": 20, "second": 10})


def poisoned(save: SaveEnds = POISON, who: str = "first") -> EncounterState:
    """`who` holds Poisoned with a one-minute span and the repeated save p. 63 states."""
    state = encounter()
    return state.with_condition(
        who, Condition.POISONED, duration=state.for_minutes(1, who, save=save)
    )


def build_loop(path: Path, *, seed: int = 11) -> TurnLoop:
    """A loop over the real SRD save-ends ruleset — not a fixture one.

    The rules under test ship with the engine, so a fixture ruleset here would prove the
    phase works against rules nobody uses.
    """
    path.mkdir(parents=True, exist_ok=True)
    return TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_ruleset(save_ends_rules()),
            resolvers=save_ends_resolvers(),
            fact_types={},
            port=JsonMemoryStore(path / "memory.json"),
            ledger=Ledger.open(
                path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
            ),
            seed_source=lambda: seed,
        )
    )


def end_turn(
    loop: TurnLoop, state: EncounterState, actor_id: str, narrations: Sequence[str | None] = ()
) -> TurnEnd:
    driver = ScriptedDriver(narrations=list(narrations) or ["it shrugs, or does not"] * 4)
    return drive(loop.end_turn(state, actor_id), driver)


# --- The obligation is read off state --------------------------------------------------


def test_a_held_save_ends_condition_is_an_obligation(tmp_path: Path) -> None:
    loop = build_loop(tmp_path)
    obligations = loop.obligations(poisoned(), "first")

    assert [o.condition for o in obligations] == [Condition.POISONED]
    assert obligations[0].rule_id == save_ends_rule_id(Condition.POISONED)


def test_a_condition_with_no_stated_save_is_no_obligation(tmp_path: Path) -> None:
    """p. 63 states the DC per effect. A condition imposed without one has no early-out, and
    inventing a DC for it would be exactly the rule value R31 forbids."""
    state = encounter()
    state = state.with_condition(
        "first", Condition.POISONED, duration=state.for_minutes(1, "first")
    )
    assert build_loop(tmp_path).obligations(state, "first") == ()


def test_a_creature_with_nothing_held_owes_nothing(tmp_path: Path) -> None:
    assert build_loop(tmp_path).obligations(encounter(), "first") == ()


def test_an_unknown_actor_owes_nothing_rather_than_raising(tmp_path: Path) -> None:
    """The turn's end is driven for whoever just acted, and a caller naming a stranger has
    made a different mistake than one this phase should raise on."""
    assert build_loop(tmp_path).obligations(encounter(), "nobody") == ()


# --- The save is rolled, through the one entry point ------------------------------------


def test_the_save_is_actually_rolled(tmp_path: Path) -> None:
    """The defect #110 reported, stated as its repair: something rolls it now."""
    ended = end_turn(build_loop(tmp_path), poisoned(), "first")

    assert len(ended.rulings) == 1
    ruling = ended.rulings[0]
    assert ruling.result is not None, "a d20 was thrown"
    assert ruling.result.target == POISON.dc
    assert ruling.status is Status.RULED


def test_a_successful_save_ends_the_condition_through_the_ruling(tmp_path: Path) -> None:
    """Clause 4's payoff, and only possible since #119: the success reaches
    `with_condition_ended` through `_apply` rather than beside it."""
    ended = end_turn(build_loop(tmp_path), poisoned(ALWAYS), "first")

    assert ended.rulings[0].result is not None and ended.rulings[0].result.succeeded
    assert not ended.state.combatant("first").conditions.has(Condition.POISONED)


def test_a_failed_save_leaves_the_condition_and_costs_nothing_further(tmp_path: Path) -> None:
    """p. 63 says the effect ends "on a success" and states no penalty for a failure, so an
    engine-chosen consequence here would be a rule value the document does not give."""
    before = poisoned(NEVER)
    ended = end_turn(build_loop(tmp_path), before, "first")

    assert ended.rulings[0].result is not None and not ended.rulings[0].result.succeeded
    after = ended.state.combatant("first")
    assert after.conditions.has(Condition.POISONED)
    assert after.hit_points == before.combatant("first").hit_points


def test_the_ruling_carries_the_derivation_of_the_dc(tmp_path: Path) -> None:
    """R5. The DC came from the imposing effect, and the ruling has to say so rather than
    leaving a bare 13 nobody can trace."""
    ended = end_turn(build_loop(tmp_path), poisoned(), "first")
    basis = ended.rulings[0].result.target_basis if ended.rulings[0].result else ""

    assert "DC 13 con" in basis
    assert "p. 63" in basis


def test_every_obligation_is_narrated(tmp_path: Path) -> None:
    """R29. A turn-end ruling carries bounds like any other, so the narrator gets them the
    same way — otherwise the one kind of ruling nobody declared is the one nobody narrates."""
    ended = end_turn(build_loop(tmp_path), poisoned(), "first", narrations=["it sweats it out"])

    assert ended.narrations == ("it sweats it out",)
    assert not ended.missing_narration


def test_a_withheld_narration_is_marked_rather_than_hidden(tmp_path: Path) -> None:
    ended = end_turn(build_loop(tmp_path), poisoned(), "first", narrations=[None])
    assert ended.missing_narration


def test_two_conditions_produce_two_rulings(tmp_path: Path) -> None:
    """Each is its own save. One ruling covering both would make a single roll decide two
    outcomes the document rolls separately."""
    state = poisoned(NEVER)
    state = state.with_condition(
        "first", Condition.BLINDED, duration=state.for_minutes(1, "first", save=NEVER)
    )
    ended = end_turn(build_loop(tmp_path), state, "first")

    assert len(ended.rulings) == 2
    assert {r.declaration.rule_id for r in ended.rulings} == {
        save_ends_rule_id(Condition.POISONED),
        save_ends_rule_id(Condition.BLINDED),
    }


def test_the_obligation_is_not_declared_by_the_driver(tmp_path: Path) -> None:
    """Clause 2, asserted where it would break: a driver with **no declarations at all**
    still gets the save rolled. If the phase asked for one, `ScriptedDriver` would raise
    `DriverExhausted` instead.
    """
    driver = ScriptedDriver(declarations=[], narrations=["something"])
    ended = drive(build_loop(tmp_path).end_turn(poisoned(), "first"), driver)

    assert len(ended.rulings) == 1


def test_the_engine_authored_declaration_claims_no_read(tmp_path: Path) -> None:
    """Decision 0007's verdict, told the truth: nothing offered this and nothing was
    choosing, so `unread` is the honest value rather than a missing one."""
    ended = end_turn(build_loop(tmp_path), poisoned(), "first")

    assert str(ended.rulings[0].alternatives_verdict) == "unread"
    assert ended.rulings[0].declaration.intent.improvised


# --- The turn cannot advance past it (clause 6) ------------------------------------------


def test_advancing_the_turn_is_refused_while_a_save_is_owed() -> None:
    """The clause that turns "the driver should remember" into "the driver cannot forget"."""
    with pytest.raises(ObligationOutstanding, match="poisoned"):
        poisoned().advanced_turn()


def test_the_refusal_names_what_is_owed_and_how_to_proceed() -> None:
    with pytest.raises(ObligationOutstanding) as raised:
        poisoned().advanced_turn()

    message = str(raised.value)
    assert "p. 63" in message
    assert "end_turn" in message
    assert "waive_obligations" in message


def test_a_creature_owing_nothing_advances_as_before() -> None:
    """The guard has to be inert for every turn that owes nothing, which is nearly all."""
    assert encounter().advanced_turn().active_id == "second"


def test_only_the_departing_creature_blocks_the_turn() -> None:
    """p. 63 is "the end of *its* turns". Another creature's outstanding save is not this
    creature's obligation, and blocking on it would deadlock the encounter."""
    state = poisoned(who="second")
    assert state.active_id == "first"
    assert state.advanced_turn().active_id == "second"


def test_the_waiver_advances_and_has_to_be_asked_for() -> None:
    """A parameter rather than silence: the fact that matters is *that a turn advanced
    unresolved*, so a caller has to say it."""
    assert poisoned().advanced_turn(waive_obligations=True).active_id == "second"


def test_the_turn_advances_once_the_obligation_is_discharged(tmp_path: Path) -> None:
    """The whole sequence: end the turn, then advance. No waiver needed."""
    ended = end_turn(build_loop(tmp_path), poisoned(NEVER), "first")
    assert ended.state.advanced_turn().active_id == "second"


def test_a_failed_save_does_not_deadlock_the_turn(tmp_path: Path) -> None:
    """The trap in clause 6, and the reason `discharged` exists at all. A failed save leaves
    the condition held, so a guard reading `saves_due_after` alone would refuse to advance
    for as long as the creature stayed poisoned — a rule that ends the encounter."""
    ended = end_turn(build_loop(tmp_path), poisoned(NEVER), "first")

    assert ended.state.combatant("first").conditions.has(Condition.POISONED), "still held"
    assert ended.state.obligations_outstanding("first") == (), "but no longer owed this turn"
    ended.state.advanced_turn()


def test_the_obligation_returns_on_the_next_turn(tmp_path: Path) -> None:
    """p. 63 is "each of its turns", so discharging one turn's save must not discharge the
    next. The record of having met it does not outlive the turn."""
    ended = end_turn(build_loop(tmp_path), poisoned(NEVER), "first")
    assert ended.state.obligations_outstanding("first") == (), "met, for this turn"

    # The discharge record is cleared as the turn advances, so the obligation is owed
    # again by the time the order comes back round. It is not owed *by whoever is acting*
    # in between — the guard only ever consults the departing creature.
    state = ended.state.advanced_turn()
    assert state.active_id == "second"
    assert state.obligations_outstanding("second") == (), "second holds nothing"

    round_two = state.advanced_turn()
    assert round_two.active_id == "first" and round_two.round_number == 2
    assert round_two.obligations_outstanding("first") == (Condition.POISONED,)


# --- R29 ordering, and the absences ------------------------------------------------------


def test_the_turn_cannot_end_while_the_declared_action_owes_a_narration(tmp_path: Path) -> None:
    """R29 gates the turn's end the same way it gates the next declaration. Otherwise the
    turn-end rulings land in the ledger ahead of the narration for the act that preceded
    them."""
    from srd_rules_engine.loop.turn import NarrationOwed

    loop = build_loop(tmp_path)
    loop._owed["first"] = object()  # type: ignore[assignment]
    with pytest.raises(NarrationOwed):
        next(loop.end_turn(poisoned(), "first"))


def test_the_death_save_is_not_wired_and_says_why(tmp_path: Path) -> None:
    """The absence 0023 insisted on, held as a test so it cannot be closed by assumption.

    `core.death` cites pp. 17-18 for what a death saving throw *is* and never states when it
    is made. Wiring it here on the assumption that it shares p. 63's timing would be
    inferring a rule value — the one thing this project will not do to close a gap.
    """
    state = encounter()
    downed = state.with_damage("first", 40)
    assert downed.combatant("first").is_down

    assert build_loop(tmp_path).obligations(downed, "first") == ()
    downed.advanced_turn(), "and nothing blocks the turn on its account"
