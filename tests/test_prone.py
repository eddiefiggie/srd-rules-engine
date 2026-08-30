"""p. 186's two movement options, built together (#353, 0057).

> **Restricted Movement.** Your only movement options are to crawl or to spend an amount of
> movement equal to half your Speed (round down) to right yourself and thereby end the
> condition. If your Speed is 0, you can't right yourself.

One sentence and two mechanics of different kinds: the crawl restriction is a **refusal**, and
righting yourself is a **capability** that ends a condition. Shipping the first alone would have
left a creature able to crawl and unable to stand, which is 0052's ordering rule.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Combatant,
    Condition,
    Declaration,
    EffectKind,
    EncounterState,
    Intent,
    Ledger,
    Status,
    load_ruleset,
    read,
)
from srd_rules_engine.core.conditions import EFFECTS, Conditions
from srd_rules_engine.core.position import MovementMode, Position, SpeedReduction, Speeds
from srd_rules_engine.core.prone import STAND_RULE_ID, prone_resolvers, stand_rule
from srd_rules_engine.core.read_surface import STAND, can_stand, righting_cost
from srd_rules_engine.core.turn_span import TurnBoundary
from srd_rules_engine.memory.store import JsonMemoryStore

RULESET = load_ruleset((stand_rule(),))
ORIGIN = Position(0, 0, 0)

PRONE = Conditions(applied=frozenset({Condition.PRONE}))


def creature(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 12,
        "abilities": {"str": 12, "dex": 12, "con": 12},
        "proficiency_bonus": 2,
        "is_player_character": True,
        "position": ORIGIN,
        "speeds": Speeds(walk=30),
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(actor: Combatant | None = None) -> EncounterState:
    return EncounterState.new([actor or creature(conditions=PRONE)]).with_initiative({"pc": 20})


def build(path: Path) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers=prone_resolvers(),
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 5,
    )


def declare(state: EncounterState) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=STAND),
        rule_id=STAND_RULE_ID,
        alternatives=offered.actions,
        read_token=offered.token,
    )


# --- The refusal ------------------------------------------------------------------------------


# Burrowing and flying are absent because a creature without those speeds is refused earlier
# and for a different reason (pp. 178, 182) — a test that passed for the wrong reason would be
# asserting the refusal it did not mean.
@pytest.mark.parametrize("mode", [MovementMode.WALK, MovementMode.CLIMB, MovementMode.SWIM])
def test_a_prone_creature_may_not_move_except_by_crawling(mode: MovementMode) -> None:
    """p. 186: "Your only movement options are to crawl or to ... right yourself." Every other
    mode is neither."""
    with pytest.raises(ValueError, match="is Prone"):
        encounter().with_movement("pc", Position(5, 0, 0), mode=mode)


def test_it_may_crawl() -> None:
    """The other of the two options, and the one that keeps the refusal from being a ban on
    movement. p. 179 already prices crawling at an extra foot per foot."""
    after = encounter().with_movement("pc", Position(5, 0, 0), mode=MovementMode.CRAWL)
    assert after.combatant("pc").position == Position(5, 0, 0)
    assert after.combatant("pc").movement_used == 10, "5 feet at 1 extra foot each (p. 179)"


def test_a_creature_that_is_not_prone_walks() -> None:
    after = encounter(creature()).with_movement("pc", Position(5, 0, 0))
    assert after.combatant("pc").position == Position(5, 0, 0)


# --- The way out ------------------------------------------------------------------------------


def test_standing_is_offered_and_costs_half_the_speed() -> None:
    """p. 186: "half your Speed (round down)". Thirty feet of Speed costs fifteen."""
    offered = {a.key: a.detail for a in read(encounter(), "pc").actions}
    assert STAND in offered
    assert offered[STAND] == {"costs_movement": 15, "costs_action": False}


def test_the_cost_is_half_the_speed_after_modifiers() -> None:
    """p. 188 makes "your Speed" the walking one, and `effective_speeds` is what applies the
    conditions to it. A creature slowed by p. 90's Slow pays half of what it has left."""
    slowed = creature(
        conditions=PRONE,
        speed_reductions=(
            SpeedReduction(
                feet=10,
                rule_id="mastery-slow",
                expires_after_actor_id="pc",
                expires_in_round=99,
                expires_at=TurnBoundary.START,
            ),
        ),
    )
    assert slowed.effective_speeds.walk == 20
    assert righting_cost(slowed) == 10, "half of twenty, not half of thirty"


def test_an_odd_speed_rounds_down() -> None:
    """ "(round down)", stated by the document rather than chosen here."""
    assert righting_cost(creature(conditions=PRONE, speeds=Speeds(walk=25))) == 12


def test_standing_ends_the_condition_and_charges_the_movement(tmp_path: Path) -> None:
    state = encounter()
    ruling, after = build(tmp_path).adjudicate(state, declare(state))

    assert ruling.status is Status.RULED
    assert ruling.result is None, "p. 186 asks nothing of the dice"
    stood = after.combatant("pc")
    assert Condition.PRONE not in stood.conditions.held
    assert stood.movement_used == 15
    assert stood.position == ORIGIN, "it is where it fell; standing moves nobody"
    assert {e.kind for e in ruling.effects} == {
        EffectKind.MOVEMENT_SPENT,
        EffectKind.CONDITION_ENDED,
    }


def test_standing_costs_no_action(tmp_path: Path) -> None:
    """p. 186 charges movement and says nothing about an action, so a creature that has spent
    its Action can still get up — and the offer is not gated on one."""
    spent = creature(conditions=PRONE, actions=replace(creature().actions, action_spent=True))
    assert can_stand(spent)
    assert STAND in {a.key for a in read(encounter(spent), "pc").actions}


# --- Where p. 186 says no ---------------------------------------------------------------------


def test_a_creature_with_a_speed_of_zero_cannot_right_itself() -> None:
    """p. 186 says it in its own sentence: "If your Speed is 0, you can't right yourself." It
    is a separate clause rather than a consequence of the cost being zero — half of nothing is
    nothing, and a free stand is what a naive reading would grant."""
    still = creature(conditions=PRONE, speeds=Speeds(walk=0))
    assert righting_cost(still) == 0, "the cost alone would permit it"
    assert not can_stand(still)
    assert STAND not in {a.key for a in read(encounter(still), "pc").actions}


def test_a_creature_that_has_spent_its_movement_cannot_stand() -> None:
    """p. 186 states a cost, and a creature cannot spend what it does not have —
    `with_movement` refuses an unaffordable step for the same reason."""
    tired = creature(conditions=PRONE, movement_used=25)
    assert not can_stand(tired), "5 feet left, and standing costs 15"
    assert STAND not in {a.key for a in read(encounter(tired), "pc").actions}


def test_the_charge_itself_refuses_what_cannot_be_afforded() -> None:
    """The state guard behind the offer, and it is not the same assertion.

    `can_stand` keeps the key off the menu; `with_movement_spent` refuses the charge. A
    corruption proof found this untested — removing the state refusal left every test green,
    because they all stopped at the menu.
    """
    tired = encounter(creature(conditions=PRONE, movement_used=25))
    with pytest.raises(ValueError, match="5 feet of movement left"):
        tired.with_movement_spent("pc", 15)


def test_a_creature_that_is_not_prone_is_offered_no_stand() -> None:
    assert STAND not in {a.key for a in read(encounter(creature()), "pc").actions}


def test_the_resolver_refuses_what_the_offer_refuses(tmp_path: Path) -> None:
    """The menu is a menu, not a promise. A caller reaching adjudication directly gets the
    same refusal, which is where the rule actually lives."""
    still = creature(conditions=PRONE, speeds=Speeds(walk=0))
    with pytest.raises(ValueError, match="Speed of 0"):
        prone_resolvers()[STAND_RULE_ID](
            state=encounter(still),
            declaration=Declaration(
                actor_id="pc", intent=Intent(action_key=STAND), rule_id=STAND_RULE_ID
            ),
            facts={},
        )


# --- The disclosures, retired against the rules -----------------------------------------------


def test_the_retired_prone_disclosures_are_enforced_now() -> None:
    """Both clauses come off in the change that builds them, and both are asserted here — the
    pairing AGENTS.md asks for, on the one condition that disclosed two halves of one sentence.

    They left **together** on purpose: the refusal without the exit is a creature able to crawl
    and unable to stand.
    """
    assert EFFECTS[Condition.PRONE].unenforced_clauses == ()

    # `movement-limited-to-crawling`
    with pytest.raises(ValueError, match="is Prone"):
        encounter().with_movement("pc", Position(5, 0, 0))

    # `righting-costs-half-speed`
    assert righting_cost(creature(conditions=PRONE)) == 15
    assert can_stand(creature(conditions=PRONE))
