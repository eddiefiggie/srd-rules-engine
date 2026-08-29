"""The read surface must answer without recording, and the token must make the answer checkable.

Two properties carry the weight. R19 says a read never mutates and never appends — proved
here directly, by snapshotting everything and running every call. And the token must
separate a *false* claim from a *stale* one, because those are different problems: one
is an agent misreporting what it saw, the other an agent deciding from state that has
since moved.

`verified-stale` should be unreachable in a single-actor sequential loop. It is here for
the case that makes it reachable — an agent caching a read across turns — which is
otherwise entirely invisible.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable

import pytest

from fixtures.ruleset import FIXTURE_BLADE
from srd_rules_engine.core.actions import ActionBudget, ActionKind
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.equipment import Carriage, Carried, DetachedObject, Item
from srd_rules_engine.core.position import MovementMode, Position, Speeds
from srd_rules_engine.core.read_surface import (
    ATTACK_DROP,
    ATTACK_STOW,
    DISENGAGE,
    DODGE,
    END_TURN,
    TOKEN_SCHEME,
    UNARMED_STRIKE_ID,
    LegalAction,
    Verdict,
    attack_key,
    attack_swap_key,
    dash_key,
    issue_token,
    legal_actions,
    read,
    situation,
    verify,
)
from srd_rules_engine.core.spellcasting import Concentration, SpellSlots
from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 16, "dex": 12, "con": 14}


def fighter(cid: str = "pc", hp: int = 20) -> Combatant:
    """Armed since #258: an attack is offered for a weapon in hand (0040 clause 1), and these
    fighters have no positions, so reach cannot be measured and the offer stands (0030
    clause 1 — refusing on an unmeasurable distance would invent one)."""
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=hp,
        max_hit_points=20,
        armour_class=15,
        abilities=ABILITIES,
        proficiency_bonus=2,
        hands=2,
        equipment=(Carried(FIXTURE_BLADE, Carriage.HELD),),
        weapon_proficiencies=frozenset({FIXTURE_BLADE.id}),
    )


def encounter(*, in_combat: bool = True) -> EncounterState:
    state = EncounterState.new([fighter("pc"), fighter("boar", hp=11)])
    if in_combat:
        state = state.with_initiative({"pc": 18, "boar": 9})
    return state


# --- R19: a read changes nothing ---------------------------------------------------


def test_a_read_leaves_the_state_and_the_generation_unchanged() -> None:
    """Snapshot everything, run every read-surface call, assert nothing moved.

    `repr` rather than `astuple`: the latter deep-copies, and the ability mapping is a
    `mappingproxy` precisely so it cannot be written through. The repr renders every
    field including the mapping's contents, so any change to any of them shows up.
    """
    state = encounter()
    before_generation = state.generation
    before = repr(state)

    for actor in ("pc", "boar"):
        read(state, actor)
        legal_actions(state, actor)

    assert state.generation == before_generation
    assert repr(state) == before


def test_the_state_cannot_be_mutated_through_what_a_read_receives() -> None:
    """Immutability settles R19 structurally rather than by convention."""
    state = encounter()
    with pytest.raises(dataclasses.FrozenInstanceError):
        state.round_number = 5  # type: ignore[misc]
    with pytest.raises(TypeError):
        state.combatant("pc").abilities["str"] = 20  # type: ignore[index]


def test_two_identical_reads_at_the_same_generation_return_identical_tokens() -> None:
    state = encounter()
    assert read(state, "pc").token == read(state, "pc").token


def test_a_read_is_idempotent_in_its_whole_result() -> None:
    state = encounter()
    assert read(state, "pc") == read(state, "pc")


# --- The generation moves only on mutation -----------------------------------------


def test_a_mutation_increments_the_generation_and_changes_the_token() -> None:
    state = encounter()
    first = read(state, "pc")

    moved = state.with_damage("pc", 3)
    assert moved.generation == state.generation + 1
    assert read(moved, "pc").token != first.token


def test_every_mutator_advances_the_generation() -> None:
    """A mutator that forgot to bump would leave a stale token reading as current."""
    state = encounter()
    changes: tuple[Callable[[EncounterState], EncounterState], ...] = (
        lambda s: s.with_damage("pc", 1),
        lambda s: s.with_healing("pc", 1),
        lambda s: s.advanced_turn(),
        lambda s: s.with_initiative({"pc": 5, "boar": 4}),
    )
    for change in changes:
        assert change(state).generation == state.generation + 1


def test_a_mutator_cannot_override_the_generation() -> None:
    """`_evolve` discards a generation a caller tries to set, so bumping is unskippable."""
    state = encounter()
    assert state._evolve(generation=99, round_number=7).generation == state.generation + 1


# --- What the derivation offers ----------------------------------------------------


def test_the_active_combatant_is_offered_actions() -> None:
    """Ending the turn, an attack per opponent still standing, and the three actions the
    economy can now offer while an Action remains (p. 180, p. 181)."""
    state = encounter()
    assert read(state, "pc").keys == (
        END_TURN,
        # p. 177 offers "one attack roll with a weapon **or an Unarmed Strike**", and #267
        # added the second half — so a creature with a blade in hand is offered both, and one
        # with empty hands is still offered the strike.
        attack_key(UNARMED_STRIKE_ID, "boar"),
        attack_key(FIXTURE_BLADE.id, "boar"),
        # p. 177's one equip or unequip, offered against the attack that permits it (#283,
        # 0042 clause 3). The blade is held, so its two unequip destinations are offered and
        # its equip is not — you cannot draw what is already in your hand. Nothing is stowed
        # and nothing is on the ground, so those two sources contribute nothing here.
        attack_swap_key(FIXTURE_BLADE.id, "boar", FIXTURE_BLADE.id, swap=ATTACK_STOW),
        attack_swap_key(FIXTURE_BLADE.id, "boar", FIXTURE_BLADE.id, swap=ATTACK_DROP),
        dash_key(MovementMode.WALK),
        DODGE,
        DISENGAGE,
    )


def test_a_combatant_whose_turn_it_is_not_is_offered_nothing() -> None:
    state = encounter()
    assert read(state, "boar").keys == ()


def test_a_downed_combatant_is_offered_nothing() -> None:
    state = encounter().with_damage("pc", 999)
    assert state.combatant("pc").is_down
    assert read(state, "pc").keys == ()


def test_an_unknown_actor_is_an_error_not_an_empty_set() -> None:
    """Silence would read as "nothing is legal" rather than "there is no such actor"."""
    with pytest.raises(KeyError, match="ghost"):
        read(encounter(), "ghost")


def test_the_offered_set_carries_structured_detail() -> None:
    state = encounter()
    action = read(state, "pc").actions[0]
    assert action.detail["round"] == 1


# --- The token: false claims and stale claims are different problems ----------------


def test_a_token_echoed_with_the_set_it_was_issued_for_verifies_fresh() -> None:
    state = encounter()
    result = read(state, "pc")
    assert verify(result.token, result.actions, state.generation) is Verdict.FRESH


def test_a_claim_missing_an_alternative_does_not_verify() -> None:
    state = EncounterState.new([fighter("pc")]).with_initiative({"pc": 10})
    result = read(state, "pc")
    trimmed = result.actions[:-1]
    assert verify(result.token, trimmed, state.generation) is Verdict.UNVERIFIED


def test_a_claim_with_an_added_alternative_does_not_verify() -> None:
    state = encounter()
    result = read(state, "pc")
    padded = (*result.actions, LegalAction(key="fly", label="Fly away"))
    assert verify(result.token, padded, state.generation) is Verdict.UNVERIFIED


def test_a_claim_whose_detail_was_altered_does_not_verify() -> None:
    """Detail is structure, so it is committed to; only the label is excluded."""
    state = encounter()
    result = read(state, "pc")
    altered = (dataclasses.replace(result.actions[0], detail={"round": 99}),)
    assert verify(result.token, altered, state.generation) is Verdict.UNVERIFIED


def test_relabelling_an_alternative_still_verifies() -> None:
    """Prose never enters the comparison — the same discipline R6 imposes on the matcher."""
    state = encounter()
    result = read(state, "pc")
    relabelled = tuple(
        dataclasses.replace(action, label=f"Wrap it up {n}")
        for n, action in enumerate(result.actions)
    )
    assert verify(result.token, relabelled, state.generation) is Verdict.FRESH


def test_a_token_from_an_earlier_generation_is_genuine_but_stale() -> None:
    """Distinct from a false claim: the agent decided from state that has since moved."""
    state = encounter()
    cached = read(state, "pc")
    moved = state.with_damage("boar", 2)

    assert verify(cached.token, cached.actions, moved.generation) is Verdict.STALE


def test_stale_and_unverified_are_told_apart() -> None:
    state = encounter()
    cached = read(state, "pc")
    moved = state.with_damage("boar", 2)

    assert verify(cached.token, cached.actions, moved.generation) is Verdict.STALE
    assert verify(cached.token, (), moved.generation) is Verdict.UNVERIFIED


def test_a_token_from_a_generation_that_has_not_happened_cannot_be_genuine() -> None:
    state = encounter()
    ahead = issue_token(state.generation + 5, read(state, "pc").actions)
    assert verify(ahead, read(state, "pc").actions, state.generation) is Verdict.UNVERIFIED


# --- No token, and tokens that are not tokens --------------------------------------


def test_no_token_yields_unread_rather_than_an_error() -> None:
    """The expected verdict for a caller outside the turn loop, not a failure."""
    state = encounter()
    assert verify(None, read(state, "pc").actions, state.generation) is Verdict.UNREAD
    assert verify("", read(state, "pc").actions, state.generation) is Verdict.UNREAD


def test_an_invented_token_yields_unread() -> None:
    state = encounter()
    actions = read(state, "pc").actions
    for invented in ("nonsense", "rt1.notanumber.abc", "rt9.1.abc", "rt1.1", f"{TOKEN_SCHEME}.1."):
        assert verify(invented, actions, state.generation) is Verdict.UNREAD, invented


def test_an_empty_offered_set_still_produces_a_verifiable_token() -> None:
    """A combatant offered nothing still made a claim, and it is still checkable."""
    state = encounter()
    result = read(state, "boar")
    assert result.actions == ()
    assert verify(result.token, (), state.generation) is Verdict.FRESH
    assert verify(result.token, read(state, "pc").actions, state.generation) is Verdict.UNVERIFIED


# --- The derivation is shared, not duplicated --------------------------------------


def test_the_read_surface_reports_exactly_what_the_derivation_returns() -> None:
    """One derivation, so what is offered and what will be accepted cannot drift."""
    state = encounter()
    assert read(state, "pc").actions == legal_actions(state, "pc")


# --- The state's own mechanics -----------------------------------------------------


def test_damage_clamps_at_zero_rather_than_going_negative() -> None:
    """Negative hit points would make `is_down` true and the arithmetic meaningless."""
    state = encounter().with_damage("boar", 99)
    assert state.combatant("boar").hit_points == 0
    assert state.combatant("boar").is_down


def test_healing_clamps_at_the_maximum() -> None:
    state = encounter().with_damage("pc", 5).with_healing("pc", 99)
    assert state.combatant("pc").hit_points == state.combatant("pc").max_hit_points


def test_damage_and_healing_refuse_negative_amounts() -> None:
    """Healing by negative damage would bypass whatever rule governs healing."""
    state = encounter()
    with pytest.raises(ValueError, match="damage is not negative"):
        state.with_damage("pc", -1)
    with pytest.raises(ValueError, match="healing is not negative"):
        state.with_healing("pc", -1)


def test_the_turn_advances_through_the_order_and_wraps_into_the_next_round() -> None:
    state = encounter()
    assert (state.active_id, state.round_number) == ("pc", 1)

    state = state.advanced_turn()
    assert (state.active_id, state.round_number) == ("boar", 1)

    state = state.advanced_turn()
    assert (state.active_id, state.round_number) == ("pc", 2), "wrapped into round 2"


def test_advancing_a_turn_before_initiative_is_an_error() -> None:
    with pytest.raises(ValueError, match="no turn order"):
        EncounterState.new([fighter("pc")]).advanced_turn()


def test_initiative_orders_by_roll_descending() -> None:
    state = EncounterState.new([fighter("a"), fighter("b"), fighter("c")])
    ordered = state.with_initiative({"a": 4, "b": 20, "c": 12})
    assert [c.id for c in ordered.combatants] == ["b", "c", "a"]
    assert ordered.active_id == "b"


def test_an_initiative_tie_breaks_by_the_order_given() -> None:
    """Deterministic, because replay must reproduce the order from the same inputs."""
    state = EncounterState.new([fighter("first"), fighter("second")])
    ordered = state.with_initiative({"first": 10, "second": 10})
    assert [c.id for c in ordered.combatants] == ["first", "second"]


def test_initiative_must_cover_every_combatant() -> None:
    state = EncounterState.new([fighter("a"), fighter("b")])
    with pytest.raises(ValueError, match="every combatant"):
        state.with_initiative({"a": 10})


def test_initiative_refuses_a_combatant_not_in_the_encounter() -> None:
    state = EncounterState.new([fighter("a")])
    with pytest.raises(KeyError, match="ghost"):
        state.with_initiative({"ghost": 10})


def test_an_unknown_combatant_is_a_key_error() -> None:
    with pytest.raises(KeyError, match="ghost"):
        encounter().combatant("ghost")


def test_the_ability_modifier_rounds_down_for_negatives() -> None:
    """Truncation toward zero would make a score of 7 read as -1 instead of -2."""
    weak = dataclasses.replace(fighter("pc"), abilities={"str": 7, "dex": 10, "con": 20})
    assert weak.modifier("str") == -2
    assert weak.modifier("dex") == 0
    assert weak.modifier("con") == 5
    assert weak.modifier("absent") == 0, "an unrecorded ability defaults to 10"


# --- The situation the agent decides from (R18) --------------------------------------


PC_START = Position(0, 0, 0)
#: Out of a 5-foot reach on purpose: since #258 reach decides whether an attack is offered.
BOAR_START = Position(25, 0, 0)


def _rich(
    *,
    pc_at: Position = PC_START,
    boar_at: Position = BOAR_START,
    **kw: object,
) -> EncounterState:
    """An encounter whose player character has conditions, slots and a spent economy.

    It **holds** a blade since #258, because an attack is offered for a weapon in hand
    (0040 clause 1) — and the positions are parameters because reach now decides whether the
    offer appears at all.
    """
    pc = Combatant(
        id="pc",
        name="Wizard",
        hit_points=9,
        max_hit_points=22,
        armour_class=13,
        abilities={"str": 8, "dex": 14},
        proficiency_bonus=2,
        is_player_character=True,
        position=pc_at,
        speeds=Speeds(walk=30),
        hands=2,
        equipment=(Carried(FIXTURE_BLADE, Carriage.HELD),),
        weapon_proficiencies=frozenset({FIXTURE_BLADE.id}),
        **kw,  # type: ignore[arg-type]
    )
    boar = Combatant(
        id="boar",
        name="Boar",
        hit_points=11,
        max_hit_points=11,
        armour_class=12,
        abilities={"str": 12},
        proficiency_bonus=2,
        position=boar_at,
    )
    return EncounterState.new([pc, boar]).with_initiative({"pc": 18, "boar": 6})


def test_the_situation_reports_effects_rather_than_condition_names_alone() -> None:
    """R18 asks for "active conditions **with their mechanical effects**", because a name
    alone puts the agent back to recalling 5e from training — which is the capability this
    engine exists to remove.

    So the agent is told it attacks at Disadvantage, not merely that it is Poisoned.
    """
    result = read(_rich(conditions=Conditions(held=frozenset({Condition.POISONED}))), "pc")
    assert result.situation is not None
    assert Condition.POISONED in result.situation.conditions
    assert result.situation.your_attack_rolls is Advantage.DISADVANTAGE


def test_implied_conditions_are_reported_too() -> None:
    """The agent should not have to know that Unconscious implies Prone and Incapacitated
    in order to read what it can do."""
    situation = read(_rich(conditions=Conditions(held=frozenset({Condition.UNCONSCIOUS}))), "pc")
    assert situation.situation is not None
    assert Condition.PRONE in situation.situation.conditions
    assert Condition.INCAPACITATED in situation.situation.conditions
    assert situation.situation.cannot_act


def test_the_situation_reports_speed_after_conditions_have_acted_on_it() -> None:
    """Exhaustion reduces Speed by 5 per level (p. 181), and the agent is told the number
    it actually has rather than the one on its sheet."""
    result = read(_rich(conditions=Conditions(exhaustion_levels=("a-tiring-march",) * 1)), "pc")
    assert result.situation is not None
    assert result.situation.speed == 25
    assert result.situation.movement_remaining == 25


def test_the_situation_reports_the_action_economy_and_remaining_slots() -> None:
    spent = ActionBudget(bonus_action_granted=True).spend(ActionKind.ACTION)
    result = read(_rich(actions=spent, slots=SpellSlots(total={1: 4, 2: 2}).cast(1)), "pc")

    assert result.situation is not None
    assert not result.situation.action_available
    assert result.situation.bonus_action_available
    assert result.situation.reaction_available
    assert dict(result.situation.spell_slots) == {1: 3, 2: 2}


def test_a_creature_with_no_spellcasting_reports_no_slots() -> None:
    """`None` slots and no slots left are different states, and neither is an empty lie."""
    result = read(_rich(), "pc")
    assert result.situation is not None
    assert dict(result.situation.spell_slots) == {}


def test_unenforced_clauses_reach_the_agent() -> None:
    """A rule the engine holds but does not apply is something the agent needs to know, or
    it will assume the engine handled it."""
    frightened = Conditions(held=frozenset({Condition.FRIGHTENED}))
    result = read(_rich(conditions=frightened), "pc")
    assert result.situation is not None
    assert "cannot-willingly-approach-the-source" in result.situation.unenforced_clauses


# --- What the economy now puts on the menu -------------------------------------------


def test_dash_dodge_and_disengage_are_offered_while_an_action_remains() -> None:
    state = _rich()
    assert {dash_key(MovementMode.WALK), DODGE, DISENGAGE} <= set(read(state, "pc").keys)


def test_they_are_withdrawn_once_the_action_is_spent() -> None:
    """The menu is what is legal, so an action already spent is not on it."""
    spent = ActionBudget().spend(ActionKind.ACTION)
    keys = set(read(_rich(actions=spent), "pc").keys)
    assert not {dash_key(MovementMode.WALK), DODGE, DISENGAGE} & keys
    assert END_TURN in keys, "ending the turn survives"


def test_dash_offers_the_speed_the_creature_actually_has() -> None:
    """p. 180: "The increase equals your Speed **after applying any modifiers**.\""""
    state = _rich(conditions=Conditions(exhaustion_levels=("a-tiring-march",) * 1))
    dash = next(a for a in read(state, "pc").actions if a.key == dash_key(MovementMode.WALK))
    assert dash.detail["extra_movement"] == 25


def test_an_incapacitated_creature_is_offered_only_the_end_of_its_turn() -> None:
    """p. 184 removes every action, but a creature that can do nothing must still be able
    to stop — offering nothing at all would strand the loop with no legal answer."""
    stunned = Conditions(held=frozenset({Condition.STUNNED}))
    assert read(_rich(conditions=stunned), "pc").keys == (END_TURN,)


def test_an_attack_out_of_reach_is_not_offered_at_all() -> None:
    """**This test asserted the opposite until #258**, and the reason it gave was true:

        Whether a target is in range depends on the *weapon*, which the read surface does not
        know. So it supplies the distance and leaves the judgement.

    A weapon is an `Item` the creature holds now (0040 clause 1), so the surface knows exactly
    which weapon each offer is for — and R18 asks for legality to be computable rather than
    checkable afterwards. A menu that knows an attack is impossible and offers it anyway is a
    menu that lies.

    The blade has a 5-foot reach and the boar is 25 feet away, so there is no offer to find.
    """
    offered = {a.key for a in read(_rich(), "pc").actions}
    assert attack_key(FIXTURE_BLADE.id, "boar") not in offered


def test_an_attack_in_reach_still_reports_the_distance() -> None:
    """Gating is not a reason to stop reporting: the agent weighs the shot it is offered, and
    R18 wants values it can act on rather than a bare yes."""
    close = _rich(pc_at=Position(0, 0, 0), boar_at=Position(5, 0, 0))
    attack = next(
        a for a in read(close, "pc").actions if a.key == attack_key(FIXTURE_BLADE.id, "boar")
    )
    assert attack.detail["distance"] == 5
    assert attack.detail["reach"] == 5
    assert attack.detail["weapon"] == FIXTURE_BLADE.id


def test_the_token_still_commits_only_to_the_offered_set() -> None:
    """Decision 0007: the token is about the *menu*, because that is what a declaration's
    alternatives claim. A situation is not a menu — and staleness is caught anyway, since
    both are derived from the same generation the token carries.
    """
    state = _rich()
    first, second = read(state, "pc"), read(state, "pc")
    assert first.token == second.token
    assert verify(first.token, first.actions, state.generation) is Verdict.FRESH


# --- Concentration reaches the surface derived, not as stored (p. 179, 0036) -------------


def _concentrating(cid: str = "pc", spell: str = "hold-person") -> EncounterState:
    state = encounter()
    caster = dataclasses.replace(state.combatant(cid), concentration=Concentration().begin(spell))
    return EncounterState(
        generation=state.generation,
        combatants=tuple(c if c.id != cid else caster for c in state.combatants),
        turn_index=state.turn_index,
        round_number=state.round_number,
    ).with_initiative({"pc": 18, "boar": 9})


def test_a_creature_not_concentrating_reports_nothing_rather_than_a_blank() -> None:
    """`None`, not `""`. "Not concentrating" and "concentrating on something unnamed" are
    different facts, and `Concentration.begin` refuses the second outright."""
    result = read(encounter(), "pc")
    assert result.situation is not None
    assert result.situation.concentrating_on is None


def test_what_a_caster_is_concentrating_on_reaches_the_agent() -> None:
    result = read(_concentrating(), "pc")
    assert result.situation is not None
    assert result.situation.concentrating_on == "hold-person"


def test_the_surface_reports_no_concentration_once_a_condition_has_broken_it() -> None:
    """p. 179: "Your Concentration ends if you have the Incapacitated condition."

    **This test used to assert the opposite mechanism.** It required the surface to *derive*
    the answer, because nothing wrote the field when a condition landed and a raw read would
    have said a spell was still up after the condition that broke it. The derivation covered
    that direction and could not cover the other — p. 179 *ends* Concentration, and the spell
    came back when the condition lifted (#238).

    So the field is written where the event happens and the surface reports it plainly. The
    observable behaviour asserted here is unchanged; what changed is which layer is
    responsible, and that the answer now survives the condition going away.
    """
    state = _concentrating()
    stunned = dataclasses.replace(
        state.combatant("pc"), conditions=Conditions(held=frozenset({Condition.STUNNED}))
    )
    state = EncounterState(
        generation=state.generation,
        combatants=tuple(c if c.id != "pc" else stunned for c in state.combatants),
        turn_index=state.turn_index,
        round_number=state.round_number,
    )

    assert state.combatant("pc").concentration.rule_id is None, (
        "the end is materialised now, so the field itself is the answer the surface reports"
    )
    result = read(state, "pc")
    assert result.situation is not None
    assert result.situation.concentrating_on is None, (
        "Stunned implies Incapacitated (R14), which p. 179 says ends Concentration"
    )


# --- 0041: detached objects on the read surface (#279) ----------------------------------


ORIGIN = Position(0, 0, 0)


def _with_objects(*objects: DetachedObject, position: Position | None = ORIGIN) -> EncounterState:
    actor = Combatant(
        id="pc",
        name="PC",
        hit_points=10,
        max_hit_points=10,
        armour_class=12,
        abilities={"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10},
        proficiency_bonus=2,
        position=position,
    )
    return EncounterState(generation=1, combatants=(actor,), detached_objects=objects)


def test_the_surface_refuses_reach_rather_than_reporting_none_in_reach() -> None:
    """0041 clause 4. A creature with no position gets `None`, not an empty tuple.

    The distinction is the whole discipline: an encounter that tracks no positions **cannot
    answer**, and an empty list would report that it had computed distances and found
    nothing. Same shape as `free_hands`, and for the same reason.
    """
    state = _with_objects(DetachedObject(Item(id="dagger"), Position(0, 0, 0)), position=None)
    assert situation(state, "pc").reachable_objects is None


def test_the_surface_names_the_objects_no_rule_has_placed() -> None:
    """R32. "Out of reach" and "nobody said where it fell" are different answers, and one
    empty list would render them identical — so the second is disclosed rather than left to
    be inferred from an absence."""
    situ = situation(_with_objects(DetachedObject(Item(id="lost-sword"))), "pc")
    assert situ.reachable_objects == ()
    assert situ.unplaced_objects == ("lost-sword",)


def test_a_placed_object_within_reach_is_offered_as_a_fact() -> None:
    """The fact, not the action. p. 177's equip and p. 12's object interaction are clause 6
    and are #283 — this reports what is reachable and stops there."""
    situ = situation(
        _with_objects(
            DetachedObject(Item(id="dagger"), Position(5, 0, 0)),
            DetachedObject(Item(id="halberd"), Position(30, 0, 0)),
        ),
        "pc",
    )
    assert situ.reachable_objects == ("dagger",)
    assert situ.unplaced_objects == ()


def test_an_encounter_where_nobody_dropped_anything_reports_empty_rather_than_unknown() -> None:
    """0026 clause 5's reading, carried over: an empty tuple means nobody has dropped
    anything, which is the right answer for a scene where nobody has."""
    assert EncounterState(generation=1, combatants=()).detached_objects == ()
    situ = situation(_with_objects(), "pc")
    assert situ.reachable_objects == ()
    assert situ.unplaced_objects == ()
