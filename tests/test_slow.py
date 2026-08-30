"""p. 90's Slow: ten feet off a Speed, until the start of your next turn (#322).

> **Slow.** If you hit a creature with this weapon **and deal damage to it**, you can reduce
> its Speed by 10 feet until the **start** of your next turn. If the creature is hit more than
> once by weapons that have this property, the Speed reduction **doesn't exceed 10 feet**.

Slow borrows one half from each of its neighbours and adds a clause neither has:

* **Vex's trigger** — "and deal damage to it", which Topple and Sap do not require.
* **Sap's window** — the *start* of the attacker's next turn, measured against a creature that
  is not the one carrying the effect.
* **A cap across sources.** "If the creature is hit more than once… doesn't exceed 10 feet."
  Two Slow hits take ten feet between them, and a per-hit reduction takes twenty. That is the
  clause a single-attacker test cannot see.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core import (
    Carriage,
    Carried,
    Combatant,
    Declaration,
    EncounterState,
    Intent,
    Weapon,
    attack_key,
    attack_resolver,
)
from srd_rules_engine.core.adjudicate import Effect, EffectKind, Proposal
from srd_rules_engine.core.position import (
    SLOW_REDUCTION_FEET,
    SLOW_RULE_ID,
    Position,
    SpeedReduction,
    Speeds,
    slow_feet_taken,
)
from srd_rules_engine.core.turn_span import TurnBoundary

#: p. 91 gives Slow to the Club, Javelin, Light Crossbow, Sling, Whip, Longbow and Musket.
CLUB = Weapon(id="fixture:club", damage_dice=1, damage_sides=4, slow=True, hands_when_held=1)
#: The same weapon without the property, so a difference is the property's doing.
DAGGER = Weapon(id="fixture:dagger", damage_dice=1, damage_sides=4, hands_when_held=1)


def striker(
    weapon: Weapon = CLUB, *, cid: str = "pc", masters: bool = True, at: int = 0
) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=40,
        max_hit_points=40,
        armour_class=13,
        abilities={"str": 16, "dex": 12},
        proficiency_bonus=2,
        position=Position(at, 0, 0),
        hands=2,
        equipment=(Carried(weapon, Carriage.HELD),),
        weapon_proficiencies=frozenset({weapon.id}),
        mastery_weapons=frozenset({weapon.id}) if masters else frozenset(),
    )


def quarry(**kw: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "boar",
        "name": "Boar",
        "hit_points": 200,
        "max_hit_points": 200,
        "armour_class": 10,
        "abilities": {"str": 12, "dex": 10},
        "proficiency_bonus": 2,
        "position": Position(5, 0, 0),
        "speeds": Speeds(walk=30),
    }
    fields.update(kw)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(*combatants: Combatant) -> EncounterState:
    people = combatants or (striker(), quarry())
    return EncounterState.new(list(people)).with_initiative(
        {c.id: 20 - i for i, c in enumerate(people)}
    )


def propose(state: EncounterState, actor: str, weapon: Weapon, target: str) -> Proposal:
    return attack_resolver()(
        state=state,
        declaration=Declaration(
            actor_id=actor,
            intent=Intent(action_key=attack_key(weapon.id, target)),
            rule_id="attack",
        ),
        facts={},
    )


def _effects(branch: tuple[object, ...]) -> list[Effect]:
    return [e for e in branch if isinstance(e, Effect)]


def imposed(proposal: Proposal) -> list[Effect]:
    return [e for e in _effects(proposal.on_success) if e.kind is EffectKind.SPEED_REDUCED]


def reduction(**kw: object) -> SpeedReduction:
    fields: dict[str, object] = {
        "rule_id": SLOW_RULE_ID,
        "feet": SLOW_REDUCTION_FEET,
        "expires_after_actor_id": "pc",
        # The round a real grant names: `state.round_number + 1`, and an encounter begins at
        # round 1. A default of 1 would be dead the moment it was imposed.
        "expires_in_round": 2,
        "expires_at": TurnBoundary.START,
    }
    fields.update(kw)
    return SpeedReduction(**fields)  # type: ignore[arg-type]


def slowed(state: EncounterState, *reductions: SpeedReduction) -> EncounterState:
    for one in reductions or (reduction(),):
        state = state.with_speed_reduction("boar", one)
    return state


# --- what a hit imposes -------------------------------------------------------------------


def test_a_damaging_hit_reduces_the_speed_by_ten_feet() -> None:
    [effect] = imposed(propose(encounter(), "pc", CLUB, "boar"))
    imposed_reduction = effect.speed_reduction
    assert imposed_reduction is not None

    assert effect.target_id == "boar", "the reduction is the target's"
    assert imposed_reduction.feet == 10
    assert imposed_reduction.rule_id == SLOW_RULE_ID


def test_a_weapon_without_slow_imposes_nothing() -> None:
    assert imposed(propose(encounter(striker(DAGGER), quarry()), "pc", DAGGER, "boar")) == []


def test_slow_is_refused_to_a_wielder_with_no_feature_unlocking_it() -> None:
    """0047 clause 6: every mastery takes the gate, beside its own flag."""
    withheld = encounter(striker(masters=False), quarry())
    assert imposed(propose(withheld, "pc", CLUB, "boar")) == []


def test_the_reduction_waits_on_damage() -> None:
    """ "and deal damage to it" — Vex's trigger, which Topple and Sap do not share. A hit
    reduced to nothing by Resistance slows no one."""
    [effect] = imposed(propose(encounter(), "pc", CLUB, "boar"))

    assert effect.when is not None
    assert effect.when_subject_id == "boar", "the damage that decides it is the target's own"


def test_the_window_is_the_start_of_the_attackers_next_turn() -> None:
    """Sap's boundary, and measured against the **attacker** — the creature carrying the
    reduction is not the creature whose turn ends it."""
    [effect] = imposed(propose(encounter(), "pc", CLUB, "boar"))
    imposed_reduction = effect.speed_reduction
    assert imposed_reduction is not None

    assert imposed_reduction.expires_after_actor_id == "pc"
    assert imposed_reduction.expires_at is TurnBoundary.START
    assert imposed_reduction.expires_in_round == encounter().round_number + 1


# --- what it does to the Speed ------------------------------------------------------------


def test_the_reduction_reaches_the_speed_the_creature_can_use() -> None:
    state = slowed(encounter())

    assert state.combatant("boar").speeds.walk == 30, "what the creature has is untouched"
    assert state.combatant("boar").effective_speeds.walk == 20, "what it can use is not"


def test_the_reduction_reaches_the_walking_speed_only() -> None:
    """p. 90 says "its **Speed**", which p. 188 makes the walking one. A reduction reaching a
    Fly or Swim Speed would be a rule the sentence does not state."""
    flier = quarry(speeds=Speeds(walk=30, fly=60, swim=20))
    state = slowed(encounter(striker(), flier))
    speeds = state.combatant("boar").effective_speeds

    assert (speeds.walk, speeds.fly, speeds.swim) == (20, 60, 20)


def test_a_speed_does_not_go_negative() -> None:
    """A Speed is a distance, not a debt. p. 90 states no floor and zero is the only one a
    distance has."""
    slug = quarry(speeds=Speeds(walk=5))
    state = slowed(encounter(striker(), slug))

    assert state.combatant("boar").effective_speeds.walk == 0


# --- the cap, which one attacker cannot show ---------------------------------------------


def test_two_slow_hits_take_ten_feet_between_them() -> None:
    """**The clause a per-hit reduction gets wrong.** "If the creature is hit more than once
    by weapons that have this property, the Speed reduction doesn't exceed 10 feet" — so two
    hits take ten feet, not twenty, and a single-attacker fixture can never see the
    difference.
    """
    state = slowed(encounter(), reduction(), reduction(expires_after_actor_id="boar"))
    creature = state.combatant("boar")

    assert len(creature.speed_reductions) == 2, "both are held, with their own expiries"
    assert creature.effective_speeds.walk == 20, "and they take ten feet between them"


def test_the_cap_counts_only_slows_own_reductions() -> None:
    """The sentence bounds **this** property. A future rule taking fifteen feet is not quietly
    limited by p. 90's ten, so the sum is capped per rule rather than per creature."""
    assert slow_feet_taken((reduction(), reduction())) == 10
    assert slow_feet_taken((reduction(rule_id="some-other-rule", feet=15),)) == 0


def test_a_reduction_of_no_feet_is_refused() -> None:
    with pytest.raises(ValueError, match="takes feet away"):
        reduction(feet=0)


# --- the window closing ------------------------------------------------------------------


def test_the_reduction_stands_until_the_boundary_passes() -> None:
    """It is not spent by anything — unlike 0049's advantage tokens, which the roll they apply
    to consumes. It simply stands, and the turn advance retires it."""
    state = slowed(encounter())
    assert state.round_number == 1 and state.turn_index == 0, "precondition: pc's turn"

    # The reduction dies at the **start** of pc's turn in round 2, so it survives the boar's
    # turn in round 1 and is gone the moment the order comes back round.
    boars_turn = state.advanced_turn()
    assert boars_turn.combatant("boar").effective_speeds.walk == 20, "still slowed"

    back_to_pc = boars_turn.advanced_turn()
    assert (back_to_pc.round_number, back_to_pc.turn_index) == (2, 0), "precondition"
    assert back_to_pc.combatant("boar").speed_reductions == (), "retired"
    assert back_to_pc.combatant("boar").effective_speeds.walk == 30


def test_the_start_boundary_is_a_tick_earlier_than_an_end_one() -> None:
    """The tick that separates p. 90's two windows. A reduction ending at the **end** of pc's
    turn in round 2 survives that turn; Slow's does not, and an implementation sharing one
    boundary for both would pass every other case here."""
    ends = slowed(encounter(), reduction(expires_at=TurnBoundary.END, expires_in_round=2))
    starts = slowed(encounter(), reduction(expires_in_round=2))

    def at_pcs_turn(state: EncounterState) -> EncounterState:
        return state.advanced_turn().advanced_turn()

    assert at_pcs_turn(ends).combatant("boar").speed_reductions, "the END one survives"
    assert at_pcs_turn(starts).combatant("boar").speed_reductions == (), "the START one does not"


def test_one_sweep_retires_both_mechanisms() -> None:
    """0050: the advantage tokens and the Speed reductions go through the same function, so a
    sweep cannot be remembered for one and forgotten for the other."""
    from srd_rules_engine.core.d20 import Advantage
    from srd_rules_engine.core.pending_rolls import SAP_RULE_ID, PendingAdvantage

    state = slowed(encounter()).with_pending_advantage(
        PendingAdvantage(
            holder_id="boar",
            state=Advantage.DISADVANTAGE,
            rule_id=SAP_RULE_ID,
            against_id=None,
            expires_after_actor_id="pc",
            expires_in_round=1,
            expires_at=TurnBoundary.START,
        )
    )

    swept = state.advanced_turn().advanced_turn()

    assert swept.pending_advantage == ()
    assert swept.combatant("boar").speed_reductions == ()
