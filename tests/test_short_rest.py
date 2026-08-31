"""p. 187's Short Rest: the sixth occasion, and the first of a third kind (#406, 0082).

The five occasions before this were one of two shapes, and p. 187 is neither:

* a **drain** — `end_day`, and the Concentration and Topple saves. The engine compels, the
  creature has no choice, and the loop empties a queue until it is empty.
* a **declaration slot** — the agent proposes, **once**, and the engine adjudicates.

p. 187 says "You can decide to spend an additional Hit Point Die **after each roll**", so
the engine offers, adjudicates, and offers **again**, and the caller ends it by declining.
That is what made #406 a gate rather than a wiring job.

Each spend is a testless `Proposal` (0027 clause 6) — no D20 Test, because nothing is being
tested against a target number — resolved through the one adjudication entry point (R1) with
the engine rolling the Hit Point Die (R4).
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from fixtures.ruleset import fixture_catalogue
from srd_rules_engine.core.adjudicate import Adjudicator, EffectKind
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.rests import HIT_DIE_RULE_ID, hit_die_resolver, hit_die_rule
from srd_rules_engine.core.rules import load_ruleset
from srd_rules_engine.core.state import Combatant, EncounterState, HitDice
from srd_rules_engine.loop.turn import (
    HitDieRequest,
    Narrated,
    ShortRest,
    SpendDeclined,
    SpendHitDie,
    TurnLoop,
)
from srd_rules_engine.memory.store import JsonMemoryStore

SEED = 7
ABILITIES = {"str": 10, "dex": 10, "con": 14, "int": 10, "wis": 10, "cha": 10}


def _rester(*, hp: int = 4, dice: HitDice | None = None) -> Combatant:
    return Combatant(
        id="pc",
        name="Wren",
        hit_points=hp,
        max_hit_points=30,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        is_player_character=True,
        hit_dice=HitDice(size=8, total=3) if dice is None else dice,
    )


def _loop(tmp_path: Path, *, seed: int = SEED) -> TurnLoop:
    shutil.rmtree(tmp_path, ignore_errors=True)
    tmp_path.mkdir(parents=True, exist_ok=True)
    return TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_ruleset((hit_die_rule(),)),
            resolvers={HIT_DIE_RULE_ID: hit_die_resolver()},
            fact_types={},
            port=JsonMemoryStore(tmp_path / "memory.json"),
            ledger=Ledger.open(
                tmp_path / "ledger.jsonl",
                engine_version="t",
                catalogue_version=fixture_catalogue().version,
                session_id="s",
            ),
            catalogue=fixture_catalogue(),
            seed_source=lambda: seed,
        )
    )


def _rest(
    tmp_path: Path,
    *,
    spends: int,
    combatant: Combatant | None = None,
    seed: int = SEED,
    seen: list[HitDieRequest] | None = None,
    interrupted: bool = False,
) -> ShortRest:
    """Drive a rest that says yes `spends` times and then stops."""
    state = EncounterState.new([combatant or _rester()])
    gen = _loop(tmp_path, seed=seed).short_rest(state, "pc", interrupted=interrupted)
    remaining = spends
    try:
        request = next(gen)
        while True:
            if isinstance(request, HitDieRequest):
                if seen is not None:
                    seen.append(request)
                if remaining > 0:
                    remaining -= 1
                    request = gen.send(SpendHitDie())
                else:
                    request = gen.send(SpendDeclined())
            else:
                request = gen.send(Narrated("Wren catches their breath"))
    except StopIteration as stop:
        assert isinstance(stop.value, ShortRest)
        return stop.value


# --- The precondition -------------------------------------------------------------------


def test_a_creature_at_zero_hit_points_cannot_start_one(tmp_path: Path) -> None:
    """p. 187: "To start a Short Rest, you must have at least 1 Hit Point" — the same
    precondition p. 185 puts on a Long Rest, and the one an implementation drops because
    every benefit below it reads as unconditional."""
    state = EncounterState.new([_rester(hp=0)])
    with pytest.raises(ValueError, match="at least 1"):
        next(_loop(tmp_path).short_rest(state, "pc"))


# --- The third kind of occasion ---------------------------------------------------------


def test_the_offer_is_repeated_after_every_roll(tmp_path: Path) -> None:
    """The sentence that made this a gate: "You can decide to spend an additional Hit Point
    Die **after each roll**." A drain would empty the dice without asking, and a declaration
    slot would ask once — so this asserts the count of *offers*, which is the thing neither
    other occasion shape produces."""
    seen: list[HitDieRequest] = []
    outcome = _rest(tmp_path, spends=2, seen=seen)

    assert len(seen) == 3, "offered, spent, offered, spent, offered — then declined"
    assert outcome.spent == 2
    assert len(outcome.rulings) == 2, "one Ruling per die, each with its own roll"


def test_each_offer_reports_the_state_the_decision_is_made_against(tmp_path: Path) -> None:
    """p. 187 puts the decision after each roll, so the second decision is made against the
    hit points the first one produced. An offer carrying stale numbers would be asking the
    caller to decide on the previous roll's world."""
    seen: list[HitDieRequest] = []
    _rest(tmp_path, spends=2, seen=seen)

    assert [request.remaining for request in seen] == [3, 2, 1]
    assert seen[0].hit_points == 4
    assert seen[1].hit_points > seen[0].hit_points, "the first die healed before the second"


def test_declining_immediately_is_a_legal_rest_that_decided_nothing(tmp_path: Path) -> None:
    """p. 187 says a creature **can** spend "one or more", so spending none is a choice. A
    rest that produced no ruling is not a defect and not a skip — there was no outcome to
    have."""
    outcome = _rest(tmp_path, spends=0)

    assert outcome.spent == 0
    assert outcome.rulings == ()
    rested = outcome.state.combatant("pc")
    assert rested.hit_points == 4, "nothing happened"
    assert rested.hit_dice is not None
    assert rested.hit_dice.remaining == 3


def test_the_loop_ends_when_the_dice_run_out(tmp_path: Path) -> None:
    """A caller that keeps saying yes is stopped by the resource rather than by a count the
    engine guessed. Asking again with none left would offer a spend p. 187 cannot pay for."""
    seen: list[HitDieRequest] = []
    outcome = _rest(tmp_path, spends=99, seen=seen)

    assert outcome.spent == 3, "three dice held, three spent"
    assert len(seen) == 3, "and it stopped offering rather than asking a fourth time"
    rested = outcome.state.combatant("pc")
    assert rested.hit_dice is not None
    assert rested.hit_dice.remaining == 0


# --- p. 187's interruptions (#409) ------------------------------------------------------


def test_an_interrupted_rest_offers_nothing_and_confers_nothing(tmp_path: Path) -> None:
    """p. 187: "An interrupted Short Rest confers no benefits."

    **It needed no un-applying**, which is what #409 assumed it would. The sentence one line
    above the spend settles it: "Benefits of the Rest. *When you finish the rest*, you gain
    the following benefits." Benefits are conferred at the finish, and an interruption stops
    the rest before it gets there — so nothing was ever applied and there is nothing to take
    back. This occasion *is* the finish; it does not simulate the hour.
    """
    seen: list[HitDieRequest] = []
    outcome = _rest(tmp_path, spends=3, interrupted=True, seen=seen)

    assert seen == [], "no die is even offered, because the rest never finished"
    assert outcome.rulings == ()
    assert outcome.spent == 0
    assert outcome.state.combatant("pc").hit_points == 4, "not one hit point was regained"
    held = outcome.state.combatant("pc").hit_dice
    assert held is not None and held.remaining == 3, "and not one die was spent"


def test_an_interrupted_rest_is_not_a_rest_the_creature_declined(tmp_path: Path) -> None:
    """The two produce the same empty result and are different facts. `ReactionDeclined`'s
    reasoning, applied to the whole occasion: the ledger should not have to guess whether a
    rest was broken or simply unspent."""
    broken = _rest(tmp_path, spends=3, interrupted=True)
    declined = _rest(tmp_path, spends=0)

    assert broken.interrupted
    assert not declined.interrupted
    assert (broken.rulings, broken.spent) == (declined.rulings, declined.spent)


def test_the_hit_point_precondition_is_asked_before_the_interruption(tmp_path: Path) -> None:
    """A creature at 0 hit points could not have started a rest for anything to interrupt, so
    p. 187's precondition is the first question and refuses whichever way the second is
    answered."""
    state = EncounterState.new([_rester(hp=0)])
    with pytest.raises(ValueError, match="at least 1"):
        next(_loop(tmp_path).short_rest(state, "pc", interrupted=True))


# --- What a spend actually does ---------------------------------------------------------


def test_a_spend_rolls_the_die_and_heals_by_what_it_rolled(tmp_path: Path) -> None:
    """R4: the engine rolls. p. 187 rolls the Hit Point Die and adds the Constitution
    modifier, and the ruling shows its working rather than reporting a total from nowhere."""
    outcome = _rest(tmp_path, spends=1)
    (ruling,) = outcome.rulings

    healing = [e for e in ruling.effects if e.kind is EffectKind.HEALING]
    assert len(healing) == 1
    assert "d8" in healing[0].description, "the expression is in the working"
    assert "+ 2" in healing[0].description, "and so is the Constitution modifier"
    assert outcome.state.combatant("pc").hit_points == 4 + healing[0].amount


def test_a_total_below_one_regains_one_hit_point(tmp_path: Path) -> None:
    """p. 187: "You regain Hit Points equal to the total (**minimum of 1 Hit Point**)."

    The floor is a rule, not a guard, and it only ever binds for a creature with a negative
    Constitution modifier — Wren's +2 can never reach it, which is why every other test here
    stayed green when the minimum was removed. Seed 1 rolls a 1 on the d4, so the total is
    **-1** and the document says the creature regains 1.
    """
    frail = replace(
        _rester(hp=4, dice=HitDice(size=4, total=2)),
        abilities={**ABILITIES, "con": 6},
    )
    outcome = _rest(tmp_path, spends=1, combatant=frail, seed=1)
    (ruling,) = outcome.rulings

    (healing,) = [e for e in ruling.effects if e.kind is EffectKind.HEALING]
    assert "minimum 1" in healing.description, "and the working says the floor applied"
    assert healing.amount == 1, "not -1, and not 0"
    assert outcome.state.combatant("pc").hit_points == 5


def test_a_spend_records_the_die_as_a_separate_effect(tmp_path: Path) -> None:
    """Two effects, not one. Folding the decrement into the healing would put a resource
    change where the ledger cannot see it apart from the roll, and the two are different
    facts: the die is gone whatever the roll came to."""
    outcome = _rest(tmp_path, spends=1)
    (ruling,) = outcome.rulings

    spends = [e for e in ruling.effects if e.kind is EffectKind.HIT_DIE_SPENT]
    assert len(spends) == 1
    assert spends[0].amount == 1
    rested = outcome.state.combatant("pc")
    assert rested.hit_dice is not None
    assert rested.hit_dice.remaining == 2


def test_the_spend_carries_no_d20_test(tmp_path: Path) -> None:
    """0027 clause 6: an outcome may exist without a D20 Test. Nothing here is tested
    against a target number, and giving it a save shape would invent a DC p. 187 never
    states."""
    outcome = _rest(tmp_path, spends=1)
    (ruling,) = outcome.rulings

    assert ruling.result is None, "no D20 Test, and the ruling says so rather than faking one"
    assert ruling.effects, "and it still produced effects"


def test_a_creature_at_full_hit_points_is_still_offered_a_spend(tmp_path: Path) -> None:
    """p. 187 does not forbid it, and the minimum is 1 Hit Point regained, so a die spent
    for nothing is a legal choice the document permits. Refusing to offer it would be this
    engine inventing a rule — the direction R31 names."""
    seen: list[HitDieRequest] = []
    outcome = _rest(tmp_path, spends=1, combatant=_rester(hp=30), seen=seen)

    assert seen, "offered even at full hit points"
    assert outcome.spent == 1
    rested = outcome.state.combatant("pc")
    assert rested.hit_points == 30, "capped, and the die is still gone"
    assert rested.hit_dice is not None
    assert rested.hit_dice.remaining == 2


def test_a_creature_with_no_dice_recorded_is_never_offered_one(tmp_path: Path) -> None:
    """`None` is unrecorded rather than zero (p. 183), so there is nothing to offer and
    nothing to invent."""
    seen: list[HitDieRequest] = []
    outcome = _rest(
        tmp_path,
        spends=3,
        combatant=Combatant(
            id="pc",
            name="Boar",
            hit_points=4,
            max_hit_points=11,
            armour_class=11,
            abilities=ABILITIES,
            proficiency_bonus=2,
        ),
        seen=seen,
    )

    assert seen == []
    assert outcome.spent == 0
    assert outcome.rulings == ()


# --- R29's debt -------------------------------------------------------------------------


def test_every_ruling_demands_its_narration(tmp_path: Path) -> None:
    """It lives on `TurnLoop` for 0081's reason: `_owed` is held per loop, so an occasion
    that produces rulings and demands narrations belongs to the object tracking that debt.
    A rest whose rulings owed nothing would be a hole in R29 rather than a tidier design."""
    outcome = _rest(tmp_path, spends=2)

    assert len(outcome.narrations) == 2
    assert not outcome.missing_narration
    assert all(text == "Wren catches their breath" for text in outcome.narrations)
