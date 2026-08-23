"""The action economy: what may be spent, and when it comes back (#16).

The timing is the part worth testing hard. A Reaction refreshes at "the start of your next
turn" (p. 186), not at the end of the round, and those differ whenever a creature acts late
in one round and early in the next — the end-of-round reading hands it two Reactions in
quick succession, which is the version usually played by mistake.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.actions import (
    ACTION_VERIFICATION,
    ActionBudget,
    ActionKind,
    ActionUnavailable,
    dodging,
    still_dodging,
)
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.position import Position, Speeds
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.state import Combatant, EncounterState

GRANTED = ActionBudget(bonus_action_granted=True)


def combatant(**kw: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "hero",
        "name": "Hero",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 15,
        "abilities": {"str": 14, "dex": 14},
        "proficiency_bonus": 2,
        "is_player_character": True,
        "position": Position(0, 0, 0),
        "speeds": Speeds(walk=30),
    }
    fields.update(kw)
    return Combatant(**fields)  # type: ignore[arg-type]


# --- One of each ----------------------------------------------------------------------


def test_one_action_per_turn() -> None:
    """p. 176: "On your turn, you can take one action.\""""
    spent = GRANTED.spend(ActionKind.ACTION)
    assert not spent.available(ActionKind.ACTION)
    with pytest.raises(ActionUnavailable, match="no action is available"):
        spent.spend(ActionKind.ACTION)


def test_a_bonus_action_exists_only_if_a_rule_grants_one() -> None:
    """p. 177: "you have a Bonus Action to take only if a rule explicitly says so."

    Having none is a different state from having spent one, and a model with only a spent
    flag would let every creature take a Bonus Action every turn.
    """
    assert not ActionBudget().available(ActionKind.BONUS_ACTION)
    assert GRANTED.available(ActionKind.BONUS_ACTION)
    with pytest.raises(ActionUnavailable):
        ActionBudget().spend(ActionKind.BONUS_ACTION)


def test_a_reaction_is_free_of_the_other_two() -> None:
    """p. 186: "if you take it on your turn, you can do so even if you also take an action,
    a Bonus Action, or both.\""""
    spent = GRANTED.spend(ActionKind.ACTION).spend(ActionKind.BONUS_ACTION)
    assert spent.available(ActionKind.REACTION)
    assert not spent.spend(ActionKind.REACTION).available(ActionKind.REACTION)


def test_incapacitated_removes_all_three() -> None:
    """p. 184: "You can't take any action, Bonus Action, or Reaction." Asked inside the
    budget rather than at the call site, so a caller cannot spend one by forgetting."""
    stunned = Conditions(held=frozenset({Condition.STUNNED}))
    for kind in ActionKind:
        assert not GRANTED.available(kind, stunned)
        with pytest.raises(ActionUnavailable, match="Incapacitated"):
            GRANTED.spend(kind, stunned)


# --- Refreshing -----------------------------------------------------------------------


def test_refreshing_returns_all_three_and_keeps_the_grant() -> None:
    """The grant is a property of the creature's features, not something a turn spends."""
    spent = (
        GRANTED.spend(ActionKind.ACTION).spend(ActionKind.BONUS_ACTION).spend(ActionKind.REACTION)
    )
    fresh = spent.refreshed()
    assert all(fresh.available(k) for k in ActionKind)
    assert fresh.bonus_action_granted


def test_dodge_and_disengage_both_clear_on_refresh_for_different_reasons() -> None:
    """Disengage lasts "for the rest of the current turn" (p. 181); Dodge lasts "until the
    start of your next turn". Both end here, but a clear-at-end-of-turn would remove Dodge
    before the attacks it exists to blunt.
    """
    active = ActionBudget(dodging=True, disengaged=True, extra_movement=30)
    fresh = active.refreshed()
    assert not fresh.dodging and not fresh.disengaged and fresh.extra_movement == 0


def test_a_reaction_refreshes_at_the_start_of_the_next_turn_not_the_round() -> None:
    """p. 186: "Once you take a Reaction, you can't take another one until the start of your
    next turn."

    Through the encounter, because the timing only shows up in sequence: the reaction is
    spent, another creature's whole turn passes without returning it, and it comes back
    when this creature's own turn begins again.
    """
    boar = combatant(id="boar", name="Boar", position=Position(20, 0, 0), is_player_character=False)
    state = EncounterState.new(
        [combatant(actions=GRANTED.spend(ActionKind.REACTION)), boar]
    ).with_initiative({"hero": 20, "boar": 10})

    assert not state.combatant("hero").actions.available(ActionKind.REACTION)

    others_turn = state.advanced_turn()
    assert not others_turn.combatant("hero").actions.available(ActionKind.REACTION), (
        "it does not come back on somebody else's turn"
    )

    own_turn = others_turn.advanced_turn()
    assert own_turn.combatant("hero").actions.available(ActionKind.REACTION)


# --- Dash -----------------------------------------------------------------------------


def test_dash_adds_speed_to_the_turns_movement() -> None:
    """p. 180, with the document's own example: "With a Speed of 30 feet ... you can move
    up to 60 feet on your turn if you Dash.\""""
    hero = combatant(actions=ActionBudget().dashed(30))
    assert hero.movement_remaining == 60


def test_dash_uses_the_speed_after_modifiers() -> None:
    """ "The increase equals your Speed **after applying any modifiers**", so a creature
    slowed by Exhaustion Dashes the shorter distance rather than the printed one."""
    tired = Conditions(exhaustion_level=2)
    speed = tired.speed_after(30)
    assert speed == 20
    hero = combatant(conditions=tired, actions=ActionBudget().dashed(speed))
    assert hero.movement_remaining == 40


# --- Dodge ----------------------------------------------------------------------------


def test_dodging_gives_disadvantage_against_and_advantage_on_dexterity_saves() -> None:
    """p. 181, both halves."""
    budget = dodging(ActionBudget(), Conditions(), 30)
    assert budget.attack_rolls_against() is Advantage.DISADVANTAGE
    assert budget.dexterity_saves() is Advantage.ADVANTAGE


def test_dodging_costs_the_action() -> None:
    budget = dodging(ActionBudget(), Conditions(), 30)
    assert not budget.available(ActionKind.ACTION)


def test_a_dodge_is_lost_to_incapacitation_or_a_speed_of_zero() -> None:
    """p. 181: "You lose these benefits if you have the Incapacitated condition or if your
    Speed is 0." Checked when taken *and* whenever read — a creature can be grappled after
    Dodging, and a flag that stayed true would keep protecting it.
    """
    held = dodging(ActionBudget(), Conditions(), 30)
    assert still_dodging(held, Conditions(), 30)

    grappled = Conditions(held=frozenset({Condition.GRAPPLED}))
    assert not still_dodging(held, grappled, grappled.speed_after(30))

    stunned = Conditions(held=frozenset({Condition.STUNNED}))
    assert not still_dodging(held, stunned, 30)


def test_dodging_while_already_unable_to_hold_it_grants_nothing() -> None:
    """Taking it with Speed 0 spends the action and confers no benefit — the document ties
    the benefit to the state, not to the taking."""
    budget = dodging(ActionBudget(), Conditions(), 0)
    assert not budget.dodging
    assert not budget.available(ActionKind.ACTION), "the action was still spent"


def test_a_combatant_reports_whether_its_dodge_still_stands() -> None:
    hero = combatant(actions=dodging(ActionBudget(), Conditions(), 30))
    assert hero.is_dodging

    grappled = combatant(
        actions=dodging(ActionBudget(), Conditions(), 30),
        conditions=Conditions(held=frozenset({Condition.GRAPPLED})),
    )
    assert not grappled.is_dodging, "Speed 0 ends it, even though the flag was set"


def test_dodges_sight_qualifier_is_named_rather_than_enforced() -> None:
    """p. 181 qualifies the Disadvantage with "if you can see the attacker". Sight needs
    #91's obstructions, so the base effect applies and the qualifier is named — the same
    treatment `core.conditions` gives Frightened's line-of-sight clause.
    """
    budget = dodging(ActionBudget(), Conditions(), 30)
    assert "dodge-requires-seeing-the-attacker" in budget.unenforced_clauses()
    assert ActionBudget().unenforced_clauses() == ()


# --- Provenance -----------------------------------------------------------------------


def test_the_action_economy_carries_a_verified_citation() -> None:
    assert ACTION_VERIFICATION.state is VerificationState.VERIFIED
    assert ACTION_VERIFICATION.reference is not None
    for cited in ("p. 176", "p. 177", "p. 180", "p. 181", "p. 185", "p. 186"):
        assert cited in ACTION_VERIFICATION.reference


def test_the_module_says_what_it_does_not_fire() -> None:
    """Opportunity Attacks spend a Reaction that is modelled, and nothing detects the
    departure from reach that triggers one. Decision 0015 records why that is not a
    redesign — the seam already serves it."""
    from srd_rules_engine.core import actions

    assert actions.__doc__ is not None
    assert "Opportunity Attacks are not fired here" in actions.__doc__
    assert "0015" in actions.__doc__
