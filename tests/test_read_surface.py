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

from srd_rules_engine.core.read_surface import (
    END_TURN,
    TOKEN_SCHEME,
    LegalAction,
    Verdict,
    attack_key,
    issue_token,
    legal_actions,
    read,
    verify,
)
from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 16, "dex": 12, "con": 14}


def fighter(cid: str = "pc", hp: int = 20) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=hp,
        max_hit_points=20,
        armour_class=15,
        abilities=ABILITIES,
        proficiency_bonus=2,
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
    """Ending the turn, and one attack per opponent still standing."""
    state = encounter()
    assert read(state, "pc").keys == (END_TURN, attack_key("boar"))


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
