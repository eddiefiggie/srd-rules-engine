"""Dash, Dodge and Disengage: three Actions that were offered and did nothing (#252).

Each was claimed in `ENGINE_SHAPES` as implemented and reachable by nothing. Declaring one
was accepted as `no-test-accepted`, produced no effects, spent no Action and granted no
movement — while `core.combat` had been reading `is_dodging` the whole time, so the
*consequence* was wired and the **occasion** was missing. That is the third time this
repository has found the shape: `concentration_save_dc` before #215, `Concentration` before
#235, and these.

The attack half of #252 is here too, because it is the same rule: p. 176 gives a turn one
action, and until now nothing an adjudication did cost anything at all.
"""

from __future__ import annotations

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
from srd_rules_engine.core.actions import ActionBudget, ActionKind
from srd_rules_engine.core.position import MovementMode, Speeds
from srd_rules_engine.core.read_surface import DISENGAGE, DODGE, dash_key, dash_mode
from srd_rules_engine.core.turn_actions import (
    DASH_RULE_ID,
    DISENGAGE_RULE_ID,
    DODGE_RULE_ID,
    turn_action_resolvers,
    turn_action_rules,
)
from srd_rules_engine.memory.store import JsonMemoryStore

RULESET = load_ruleset(turn_action_rules())


def hero(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 13,
        "abilities": {"str": 14, "dex": 14, "con": 12},
        "proficiency_bonus": 2,
        "is_player_character": True,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def boar() -> Combatant:
    return Combatant(
        id="boar",
        name="Boar",
        hit_points=11,
        max_hit_points=11,
        armour_class=11,
        abilities={"str": 12, "dex": 10, "con": 12},
        proficiency_bonus=2,
    )


def encounter(actor: Combatant | None = None) -> EncounterState:
    return EncounterState.new([actor or hero(), boar()]).with_initiative({"pc": 20, "boar": 5})


def build(path: Path) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers=turn_action_resolvers(),
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 5,
    )


def declare(state: EncounterState, key: str, rule_id: str) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=key),
        rule_id=rule_id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


# --- The occasion exists at all -----------------------------------------------------------


def test_dashing_grants_the_movement_it_promises(tmp_path: Path) -> None:
    """p. 180: "you gain extra movement for the current turn. The increase equals your Speed
    after applying any modifiers." Offered since the read surface existed; granted by nothing
    until #252."""
    state = encounter()
    ruling, after = build(tmp_path).adjudicate(
        state, declare(state, dash_key(MovementMode.WALK), DASH_RULE_ID)
    )

    assert ruling.status is Status.RULED
    assert after.combatant("pc").actions.extra_movement == 30


def test_dodging_makes_the_attacker_roll_at_disadvantage(tmp_path: Path) -> None:
    """The consequence was wired the whole time — `core.combat` reads `is_dodging` — so this
    asserts the *behaviour* rather than the flag: what the Dodge was for now happens."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, DODGE, DODGE_RULE_ID))

    assert after.combatant("pc").is_dodging
    assert after.combatant("pc").actions.attack_rolls_against().value == "disadvantage"


def test_disengaging_sets_the_flag_nothing_reads_yet(tmp_path: Path) -> None:
    """p. 181's flag, set truthfully. Opportunity Attacks are an unimplemented shape, so
    nothing consults it — which is a gap in *them*, not a reason to leave Disengage doing
    nothing at all, which is what it did."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, DISENGAGE, DISENGAGE_RULE_ID))

    assert after.combatant("pc").actions.disengaged


def test_none_of_them_rolls_anything(tmp_path: Path) -> None:
    """0027 clause 6. p. 180 and p. 181 state what each does and ask nothing of the dice, so
    inventing a test to reach the outcome would invent a roll the rules do not call for."""
    for key, rule_id in (
        (dash_key(MovementMode.WALK), DASH_RULE_ID),
        (DODGE, DODGE_RULE_ID),
        (DISENGAGE, DISENGAGE_RULE_ID),
    ):
        state = encounter()
        ruling, _ = build(tmp_path / rule_id).adjudicate(state, declare(state, key, rule_id))
        assert ruling.result is None, f"{rule_id} proposed a d20 test"


# --- p. 176: one action per turn ----------------------------------------------------------


def test_each_of_them_costs_the_action(tmp_path: Path) -> None:
    """p. 176: "On your turn, you can take one action." All three are `[Action]`-tagged, and
    none of them charged anything before #252."""
    for key, rule_id in (
        (dash_key(MovementMode.WALK), DASH_RULE_ID),
        (DODGE, DODGE_RULE_ID),
        (DISENGAGE, DISENGAGE_RULE_ID),
    ):
        state = encounter()
        _, after = build(tmp_path / rule_id).adjudicate(state, declare(state, key, rule_id))
        assert not after.combatant("pc").actions.available(ActionKind.ACTION), rule_id


def test_a_dodge_that_confers_nothing_still_costs_the_action(tmp_path: Path) -> None:
    """p. 181 ties the benefit to the state, not to the taking: "You lose these benefits if
    you have the Incapacitated condition or if your Speed is 0." The Action is gone either
    way, and the charge now lives with the ruling rather than inside `dodging()`."""
    still = hero(speeds=Speeds(walk=0))
    state = encounter(still)
    _, after = build(tmp_path).adjudicate(state, declare(state, DODGE, DODGE_RULE_ID))

    assert not after.combatant("pc").is_dodging
    assert not after.combatant("pc").actions.available(ActionKind.ACTION)


def test_they_leave_the_menu_once_the_action_is_gone(tmp_path: Path) -> None:
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, DODGE, DODGE_RULE_ID))

    keys = {a.key for a in read(after, "pc").actions}
    assert not any(k.startswith("dash") for k in keys)
    assert DODGE not in keys and DISENGAGE not in keys


# --- p. 180's choice of speed --------------------------------------------------------------


def test_dash_offers_one_entry_per_speed_the_creature_has() -> None:
    """p. 180: "If you have a special speed, such as a Fly Speed or Swim Speed, you can use
    that speed instead of your Speed… **You choose which speed to use each time you take
    it**." A single Walk-only offer would make that choice for the creature."""
    flier = hero(speeds=Speeds(walk=30, fly=60))
    keys = {a.key for a in read(encounter(flier), "pc").actions}

    assert dash_key(MovementMode.WALK) in keys
    assert dash_key(MovementMode.FLY) in keys
    assert dash_key(MovementMode.SWIM) not in keys, "it has no Swim Speed"


def test_crawling_is_not_a_speed_and_is_not_offered() -> None:
    """The entry that would slip in. `Speeds.for_mode` answers Speed for crawling, because
    p. 179 makes it an ordinary move that costs more rather than a speed of its own — so
    iterating every `MovementMode` offers a "Dash (crawl)" the document does not describe, at
    a number that is just Speed again."""
    keys = {a.key for a in read(encounter(), "pc").actions}
    assert dash_key(MovementMode.CRAWL) not in keys


def test_dashing_in_a_special_speed_grants_that_speed(tmp_path: Path) -> None:
    flier = hero(speeds=Speeds(walk=30, fly=60))
    state = encounter(flier)
    _, after = build(tmp_path).adjudicate(
        state, declare(state, dash_key(MovementMode.FLY), DASH_RULE_ID)
    )
    assert after.combatant("pc").actions.extra_movement == 60


def test_the_increase_is_the_speed_after_modifiers(tmp_path: Path) -> None:
    """p. 180's own worked example: "If your Speed of 30 feet is reduced to 15 feet, you can
    move up to 30 feet this turn if you Dash." Exhaustion is what this engine can reduce it
    with, and the reduction has to reach the Dash."""
    from srd_rules_engine.core import SUFFOCATION_RULE_ID

    state = encounter().with_exhaustion("pc", SUFFOCATION_RULE_ID, 2)
    reduced = state.combatant("pc").conditions.speed_after(30)
    assert reduced == 20, "precondition: p. 181 takes 5 feet per level"

    _, after = build(tmp_path).adjudicate(
        state, declare(state, dash_key(MovementMode.WALK), DASH_RULE_ID)
    )
    assert after.combatant("pc").actions.extra_movement == reduced


def test_the_key_names_the_mode_and_nothing_else() -> None:
    assert dash_mode(dash_key(MovementMode.FLY)) is MovementMode.FLY
    assert dash_mode("dash:hovering") is None
    assert dash_mode("dodge") is None
    assert dash_mode(None) is None


def test_a_dash_in_a_speed_the_creature_lacks_is_refused(tmp_path: Path) -> None:
    from srd_rules_engine.core.turn_actions import dash_resolver

    state = encounter()
    with pytest.raises(ValueError, match="no fly speed"):
        dash_resolver()(
            state=state,
            declaration=declare(state, dash_key(MovementMode.FLY), DASH_RULE_ID),
            facts={},
        )


# --- p. 177: an attack is an action too ----------------------------------------------------


def test_an_attack_leaves_the_menu_once_the_action_is_gone() -> None:
    """p. 176 again, from the read surface. The offer had nothing to be conditional on while
    nothing charged the Action."""
    spent = hero(actions=ActionBudget().spend(ActionKind.ACTION))
    keys = {a.key for a in read(encounter(spent), "pc").actions}
    assert not any(k.startswith("attack:") for k in keys)


def test_an_incapacitated_creature_is_offered_none_of_them() -> None:
    """p. 184 removes all three actions, and ending the turn survives — a creature that can
    do nothing must still be able to stop."""
    state = encounter().with_condition("pc", Condition.STUNNED)
    keys = {a.key for a in read(state, "pc").actions}
    assert keys == {"end-turn"}


# --- The costs are costs, not consequences -------------------------------------------------


def test_the_action_is_recorded_as_a_cost_before_what_the_act_did(tmp_path: Path) -> None:
    """0038 clause 6's ordering, which these inherit: `always` first, then the branch. The
    ledger reads in the order the things happened."""
    state = encounter()
    ruling, _ = build(tmp_path).adjudicate(
        state, declare(state, dash_key(MovementMode.WALK), DASH_RULE_ID)
    )
    assert [e.kind for e in ruling.effects] == [EffectKind.ACTION_SPENT, EffectKind.DASHED]
