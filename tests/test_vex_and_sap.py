"""p. 90's Vex and Sap: advantage that outlives the roll granting it (#318, #319).

> **Vex.** If you hit a creature with this weapon **and deal damage to the creature**, you
> have Advantage on your next attack roll against that creature before the **end** of your
> next turn.

> **Sap.** If you hit a creature with this weapon, that creature has Disadvantage on its next
> attack roll before the **start** of your next turn.

One mechanism, reversed on all four axes — sign, holder, scope, and which end of the turn it
dies at. Every other source of Advantage in this engine is a standing fact recomputed at the
moment of the roll; these are **granted, held, and spent**, which is what makes them new.

The window is the trap. Both are measured against the **attacker's** turns — "before the end
of *your* next turn", "before the start of *your* next turn" — even though Sap's token belongs
to somebody else. Getting one boundary right proves nothing about the other, so both are
asserted at the tick either side of the line.
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
from srd_rules_engine.core.d20 import Advantage, _effective_advantage
from srd_rules_engine.core.pending_rolls import (
    SAP_RULE_ID,
    VEX_RULE_ID,
    PendingAdvantage,
    TurnBoundary,
    is_live,
)
from srd_rules_engine.core.position import Position

#: p. 91 gives Vex to the Handaxe, Dart, Rapier, Shortsword, Shortbow, Blowgun and Hand
#: Crossbow; Sap to the Mace, Spear, Flail, Longsword, Morningstar and War Pick. Fixtures.
RAPIER = Weapon(id="fixture:rapier", damage_dice=1, damage_sides=8, vex=True, hands_when_held=1)
MACE = Weapon(id="fixture:mace", damage_dice=1, damage_sides=6, sap=True, hands_when_held=1)
#: The same weapons without the properties, so a difference is the property's doing.
CLUB = Weapon(id="fixture:club", damage_dice=1, damage_sides=6, hands_when_held=1)


def fighter(
    weapon: Weapon = RAPIER, *, cid: str = "pc", masters: bool = True, at: int = 0
) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=40,
        max_hit_points=40,
        armour_class=13,
        abilities={"str": 16, "dex": 14},
        proficiency_bonus=2,
        position=Position(at, 0, 0),
        hands=2,
        equipment=(Carried(weapon, Carriage.HELD),),
        weapon_proficiencies=frozenset({weapon.id}),
        mastery_weapons=frozenset({weapon.id}) if masters else frozenset(),
    )


def boar(cid: str = "boar", *, at: int = 5) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=200,
        max_hit_points=200,
        armour_class=10,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(at, 0, 0),
        hands=2,
        equipment=(Carried(CLUB, Carriage.HELD),),
        weapon_proficiencies=frozenset({CLUB.id}),
    )


def encounter(*combatants: Combatant) -> EncounterState:
    people = combatants or (fighter(), boar())
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


def granted(proposal: Proposal) -> list[Effect]:
    return [e for e in _effects(proposal.on_success) if e.kind is EffectKind.ADVANTAGE_PENDING]


def spent(proposal: Proposal) -> list[Effect]:
    return [e for e in _effects(proposal.always) if e.kind is EffectKind.ADVANTAGE_SPENT]


# --- what each property grants -----------------------------------------------------------


def test_vex_grants_the_attacker_advantage_against_the_creature_it_hit() -> None:
    [effect] = granted(propose(encounter(), "pc", RAPIER, "boar"))
    token = effect.pending_advantage
    assert token is not None

    assert token.holder_id == "pc", "Vex is the attacker's"
    assert token.state is Advantage.ADVANTAGE
    assert token.against_id == "boar", '"against that creature"'
    assert token.rule_id == VEX_RULE_ID


def test_sap_gives_the_creature_that_was_hit_disadvantage_on_anything() -> None:
    state = encounter(fighter(MACE), boar())
    [effect] = granted(propose(state, "pc", MACE, "boar"))
    token = effect.pending_advantage
    assert token is not None

    assert token.holder_id == "boar", "Sap is the target's, which is the reversal"
    assert token.state is Advantage.DISADVANTAGE
    assert token.against_id is None, '"its next attack roll", with no target named'
    assert token.rule_id == SAP_RULE_ID


def test_a_weapon_with_neither_property_grants_nothing() -> None:
    assert granted(propose(encounter(fighter(CLUB), boar()), "pc", CLUB, "boar")) == []


def test_neither_is_granted_to_a_wielder_with_no_feature_unlocking_it() -> None:
    """0047 clause 6: every mastery takes the gate, checked beside its own flag."""
    assert (
        granted(propose(encounter(fighter(RAPIER, masters=False), boar()), "pc", RAPIER, "boar"))
        == []
    )
    assert (
        granted(propose(encounter(fighter(MACE, masters=False), boar()), "pc", MACE, "boar")) == []
    )


# --- the triggers, which differ by one clause --------------------------------------------


def test_vex_is_conditional_on_damage_and_sap_is_not() -> None:
    """Vex says "and deal damage to the creature"; Sap says only "if you hit".

    The condition is 0032's machinery, and **the subject is the creature that was hit** while
    the token is granted to the attacker (0049). Reading the predicate against the effect's
    own target would look for damage the attacker took, find none, and withhold Vex on every
    hit that ever landed.
    """
    [vex] = granted(propose(encounter(), "pc", RAPIER, "boar"))
    [sap] = granted(propose(encounter(fighter(MACE), boar()), "pc", MACE, "boar"))

    assert vex.when is not None, "Vex waits on damage"
    assert vex.when_subject_id == "boar", "the damage that decides it is the defender's"
    assert vex.target_id == "pc", "and the benefit is the attacker's"

    assert sap.when is None, "Sap fires on the bare hit"


# --- the windows, which is where the two differ most -------------------------------------


def test_vex_expires_at_the_end_of_the_attackers_next_turn() -> None:
    [effect] = granted(propose(encounter(), "pc", RAPIER, "boar"))
    token = effect.pending_advantage
    assert token is not None

    assert token.expires_after_actor_id == "pc", "measured against the attacker's turn"
    assert token.expires_at is TurnBoundary.END
    assert token.expires_in_round == encounter().round_number + 1, "the round after this one"


def test_sap_expires_at_the_start_of_the_attackers_next_turn() -> None:
    """**The boundary with no precedent.** `DurationKind.END_OF_NEXT_TURN` is Vex's window;
    nothing in `core.duration` counts to the *start* of a turn, and Sap's token belongs to a
    creature whose own turns are irrelevant to when it dies."""
    state = encounter(fighter(MACE), boar())
    [effect] = granted(propose(state, "pc", MACE, "boar"))
    token = effect.pending_advantage
    assert token is not None

    assert token.expires_after_actor_id == "pc", "the attacker's turn, not the holder's"
    assert token.expires_at is TurnBoundary.START


ORDER = ("pc", "boar", "ogre")


def live(boundary: TurnBoundary, *, round_number: int, turn_index: int | None) -> bool:
    token = PendingAdvantage(
        holder_id="pc",
        state=Advantage.ADVANTAGE,
        rule_id=VEX_RULE_ID,
        against_id=None,
        expires_after_actor_id="pc",
        expires_in_round=1,
        expires_at=boundary,
    )
    return is_live(token, round_number=round_number, turn_index=turn_index, order=ORDER)


def test_the_end_boundary_survives_the_whole_turn_it_names() -> None:
    """ "before the **end** of your next turn" — so the turn itself is inside the window, and
    the token dies as it closes."""
    assert live(TurnBoundary.END, round_number=0, turn_index=2), "an earlier round"
    assert live(TurnBoundary.END, round_number=1, turn_index=0), "during that very turn"
    assert not live(TurnBoundary.END, round_number=1, turn_index=1), "once it has passed"
    assert not live(TurnBoundary.END, round_number=2, turn_index=0), "a later round"


def test_the_start_boundary_dies_as_that_turn_begins() -> None:
    """ "before the **start** of your next turn" — one tick earlier than the end boundary, and
    the tick that separates them is the whole difference between Vex and Sap."""
    assert live(TurnBoundary.START, round_number=1, turn_index=None), "not yet begun"
    assert live(TurnBoundary.START, round_number=0, turn_index=2), "an earlier round"
    assert not live(TurnBoundary.START, round_number=1, turn_index=0), "that turn has begun"

    # The tick both boundaries are asked about, answering differently. Without this the two
    # could share an implementation and every other case here would still pass.
    assert live(TurnBoundary.END, round_number=1, turn_index=0)
    assert not live(TurnBoundary.START, round_number=1, turn_index=0)


def test_a_token_whose_clock_left_the_encounter_stays_live() -> None:
    """The boundary it named can no longer arrive. Withdrawing a granted benefit because the
    creature that bounded it is gone would be the engine deciding an outcome the document
    does not decide — so it errs toward honouring what was granted."""
    token = PendingAdvantage(
        holder_id="pc",
        state=Advantage.ADVANTAGE,
        rule_id=VEX_RULE_ID,
        against_id=None,
        expires_after_actor_id="departed",
        expires_in_round=1,
        expires_at=TurnBoundary.END,
    )

    assert is_live(token, round_number=1, turn_index=2, order=ORDER)


# --- spending ---------------------------------------------------------------------------


def held(base: EncounterState, **kw: object) -> EncounterState:
    fields: dict[str, object] = {
        "holder_id": "pc",
        "state": Advantage.ADVANTAGE,
        "rule_id": VEX_RULE_ID,
        "against_id": "boar",
        "expires_after_actor_id": "pc",
        "expires_in_round": base.round_number,
        "expires_at": TurnBoundary.END,
    }
    fields.update(kw)
    return base.with_pending_advantage(PendingAdvantage(**fields))  # type: ignore[arg-type]


def test_a_held_token_reaches_the_roll_it_was_granted_for() -> None:
    proposal = propose(held(encounter()), "pc", RAPIER, "boar")

    assert proposal.test is not None
    assert proposal.test.has_advantage, "p. 90's Advantage reached the roll"


def test_a_sap_token_gives_its_holder_disadvantage() -> None:
    state = held(
        encounter(),
        holder_id="boar",
        state=Advantage.DISADVANTAGE,
        rule_id=SAP_RULE_ID,
        against_id=None,
    )
    proposal = propose(state, "boar", CLUB, "pc")

    assert proposal.test is not None
    assert proposal.test.has_disadvantage


def test_the_token_is_spent_by_the_roll_whether_it_hits_or_misses() -> None:
    """p. 90 says "your **next** attack roll". Spent from `always`, which is the branch that
    runs either way — putting it in `on_success` would keep it alive through every miss and
    turn "your next attack roll" into "every attack until one lands"."""
    proposal = propose(held(encounter()), "pc", RAPIER, "boar")

    [effect] = spent(proposal)
    assert effect.pending_advantage is not None
    assert effect.pending_advantage.rule_id == VEX_RULE_ID


def test_vex_is_not_spent_by_an_attack_on_somebody_else() -> None:
    """ "against **that creature**". A token out of scope is neither honoured nor consumed,
    and conflating the two would let one attack on a bystander burn it."""
    state = held(encounter(fighter(), boar(), boar("ogre", at=3)))
    proposal = propose(state, "pc", RAPIER, "ogre")

    assert proposal.test is not None
    assert not proposal.test.has_advantage
    assert spent(proposal) == []


def test_a_sap_token_is_spent_by_an_attack_on_anyone() -> None:
    """Sap names no target — "its next attack roll" — so the first roll its holder makes
    consumes it, which is the axis where it differs from Vex."""
    state = held(
        encounter(fighter(), boar(), boar("ogre", at=3)),
        holder_id="boar",
        state=Advantage.DISADVANTAGE,
        rule_id=SAP_RULE_ID,
        against_id=None,
    )
    proposal = propose(state, "boar", CLUB, "ogre")

    assert proposal.test is not None
    assert proposal.test.has_disadvantage
    assert len(spent(proposal)) == 1


def test_a_dead_token_left_in_state_is_neither_honoured_nor_spent() -> None:
    """**Liveness is the rule, and the sweep is only hygiene** (0049 clause 3).

    Written after the corruption proof for this clause came back green. The test below reaches
    the dead token through `advanced_turn`, which sweeps it — so the roll saw an empty queue
    and would have passed however `pending_advantage_for` behaved. That is the whole claim
    untested: that a token past its boundary changes no roll *even if nothing swept it*.

    Placed directly, at a boundary already behind the encounter, so only the derived check can
    refuse it.
    """
    state = held(encounter(), expires_in_round=0)
    assert state.round_number == 1, "precondition: the boundary is already behind us"
    assert state.pending_advantage, "precondition: and the token is still in state"

    proposal = propose(state, "pc", RAPIER, "boar")

    assert proposal.test is not None
    assert not proposal.test.has_advantage
    assert spent(proposal) == []


def test_an_expired_token_is_neither_honoured_nor_spent() -> None:
    """Liveness is derived, so a token past its boundary changes no roll even if nothing has
    swept it — which is the direction that cannot invent an outcome (0049)."""
    state = held(encounter())
    assert state.round_number == 1 and state.turn_index == 0, "precondition: pc's turn, round 1"

    # The token dies at the end of pc's turn in round 1, so one advance passes it.
    passed = state.advanced_turn()
    assert passed.turn_index == 1, "precondition: pc's turn has closed"

    proposal = propose(passed, "pc", RAPIER, "boar")

    assert proposal.test is not None
    assert not proposal.test.has_advantage
    assert spent(proposal) == []


def test_advantage_and_disadvantage_cancel_by_p8_rather_than_a_second_mechanism() -> None:
    """A creature holding a Sap penalty attacking a target it has Vex on rolls straight.

    Both reach the same pair of flags every other circumstance reaches, so p. 8's
    cancellation rule resolves them — asserted because a token kept in its own channel would
    stack instead, and that is a rule the document does not have.
    """
    state = held(
        held(encounter()),
        holder_id="pc",
        state=Advantage.DISADVANTAGE,
        rule_id=SAP_RULE_ID,
        against_id=None,
    )
    proposal = propose(state, "pc", RAPIER, "boar")

    assert proposal.test is not None
    assert proposal.test.has_advantage and proposal.test.has_disadvantage
    assert _effective_advantage(proposal.test) is Advantage.NONE, "p. 8: one of each is neither"


# --- the sweep ---------------------------------------------------------------------------


def test_the_turn_advance_sweeps_what_has_died() -> None:
    """Hygiene rather than the rule: liveness is derived, so the sweep only keeps the queue
    from growing. A token still inside its window survives it."""
    later = held(encounter(), expires_in_round=encounter().round_number + 1)

    # Round 1 turn 0 -> ... -> round 2 turn 1, which is past the end of pc's turn in round 2.
    assert later.advanced_turn().pending_advantage, "still live inside its window"
    swept = later.advanced_turn().advanced_turn().advanced_turn()
    assert (swept.round_number, swept.turn_index) == (2, 1), "precondition: past the boundary"
    assert swept.pending_advantage == ()


def test_a_token_with_no_state_is_refused() -> None:
    with pytest.raises(ValueError, match="Advantage or Disadvantage"):
        PendingAdvantage(
            holder_id="pc",
            state=Advantage.NONE,
            rule_id=VEX_RULE_ID,
            against_id=None,
            expires_after_actor_id="pc",
            expires_in_round=1,
            expires_at=TurnBoundary.END,
        )
