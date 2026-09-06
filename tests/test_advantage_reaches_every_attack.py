"""What the two creatures put on an attack roll reaches every resolver that makes one (#464, 0091).

`attack_resolver` composed the attacker's conditions, the defender's, p. 181's Dodge and
p. 90's Vex and Sap into the roll's two flags, and neither the Unarmed Strike nor either
improvised use consulted any of it: a Blinded creature punched without Disadvantage, a
Paralyzed one was hit by a frying pan without Advantage, and a Dodging one imposed nothing on
either. Each of those is a rule the document states for "attack rolls" (pp. 179-192, p. 181,
p. 90), which every one of these is. The composition is `_circumstances` now, read by all three;
p. 16's water reaches the improvised weapon as the weapon it is wielded as, and — by the same
page — does not reach a punch.

The module is new, so its collection error against the base tree is indivisible; every
assertion here was proved by corrupting the behaviour it guards and watching this test go red.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from srd_rules_engine.core import (
    UNARMED_STRIKE_ID,
    Declaration,
    EncounterState,
    Intent,
    Position,
    attack_key,
    unarmed_strike_resolver,
)
from srd_rules_engine.core.actions import ActionBudget
from srd_rules_engine.core.adjudicate import Effect, EffectKind, Proposal
from srd_rules_engine.core.combat import improvised_attack_resolver
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.equipment import Carriage, Carried, Item
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.pending_rolls import (
    SAP_RULE_ID,
    VEX_RULE_ID,
    PendingAdvantage,
    TurnBoundary,
)
from srd_rules_engine.core.position import Speeds
from srd_rules_engine.core.read_surface import improvised_attack_key, improvised_throw_key
from srd_rules_engine.core.state import Combatant

#: p. 183's own example, and the ruleset has said what it deals.
PAN = Item(id="fixture:pan", weight=4, improvised_damage_type=DamageType.BLUDGEONING)
#: Broken glass the ruleset has ruled Piercing — p. 16's exemption, read off this use.
GLASS = Item(id="fixture:glass", weight=1, improvised_damage_type=DamageType.PIERCING)

ABILITIES = {"str": 16, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10}


def _combatant(cid: str, position: Position, **kwargs: object) -> Combatant:
    base: dict[str, object] = {
        "id": cid,
        "name": cid.title(),
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 12,
        "abilities": ABILITIES,
        "proficiency_bonus": 3,
        "position": position,
        "speeds": Speeds(walk=30),
    }
    base.update(kwargs)
    return Combatant(**base)  # type: ignore[arg-type]


def _brawler(*items: Item, **kwargs: object) -> Combatant:
    return _combatant(
        "brawler",
        Position(0, 0, 0),
        equipment=tuple(Carried(item=i, carriage=Carriage.HELD) for i in items),
        **kwargs,
    )


def _encounter(actor: Combatant, *, feet: int = 5, **boar: object) -> EncounterState:
    target = _combatant("boar", Position(feet, 0, 0), **boar)
    state = EncounterState(generation=0, combatants=(actor, target))
    return state.with_initiative({"brawler": 20, "boar": 5})


def _held(*conditions: Condition) -> Conditions:
    return Conditions(held=frozenset(conditions))


def _token(state: EncounterState, rule_id: str, advantage: Advantage) -> EncounterState:
    """A Vex or Sap token in scope for the brawler's next roll against the boar (0049).

    Both are the brawler's to spend. Vex was granted by the brawler's own earlier hit and
    dies at the end of its next turn; Sap was put on the brawler by the boar's mace and dies
    at the start of the **boar's** next turn — so its clock is the boar's, or it is already
    dead on the brawler's turn.
    """
    vex = rule_id == VEX_RULE_ID
    return state.with_pending_advantage(
        PendingAdvantage(
            holder_id="brawler",
            state=advantage,
            rule_id=rule_id,
            against_id="boar" if vex else None,
            expires_after_actor_id="brawler" if vex else "boar",
            expires_in_round=state.round_number,
            expires_at=TurnBoundary.END if vex else TurnBoundary.START,
        )
    )


FACTS: Mapping[str, Resolution] = {}


def _swing(state: EncounterState, item_id: str = PAN.id) -> Proposal:
    declaration = Declaration(
        actor_id="brawler",
        intent=Intent(action_key=improvised_attack_key(item_id, "boar")),
        rule_id="fixture:improvised",
    )
    return improvised_attack_resolver()(state=state, declaration=declaration, facts=FACTS)


def _throw(state: EncounterState, item_id: str = PAN.id) -> Proposal:
    declaration = Declaration(
        actor_id="brawler",
        intent=Intent(action_key=improvised_throw_key(item_id, "boar")),
        rule_id="fixture:improvised",
    )
    return improvised_attack_resolver()(state=state, declaration=declaration, facts=FACTS)


def _punch(state: EncounterState) -> Proposal:
    declaration = Declaration(
        actor_id="brawler",
        intent=Intent(action_key=attack_key(UNARMED_STRIKE_ID, "boar")),
        rule_id=UNARMED_STRIKE_ID,
    )
    return unarmed_strike_resolver()(state=state, declaration=declaration, facts=FACTS)


def _spent(proposal: Proposal) -> list[Effect]:
    return [
        e for e in proposal.always if isinstance(e, Effect) and e.kind is EffectKind.ADVANTAGE_SPENT
    ]


def _flags(proposal: Proposal) -> tuple[bool, bool]:
    assert proposal.test is not None
    return proposal.test.has_advantage, proposal.test.has_disadvantage


# --- The attacker's conditions --------------------------------------------------------------


def test_a_blinded_brawler_swings_and_throws_with_disadvantage() -> None:
    """p. 179's Blinded: "Attack rolls against you have Advantage, and your attack rolls have
    Disadvantage." The second half, on both of p. 183's uses."""
    blind = _encounter(_brawler(PAN, conditions=_held(Condition.BLINDED)))

    assert _flags(_swing(blind)) == (False, True)
    assert _flags(_throw(blind)) == (False, True)


def test_a_poisoned_puncher_has_disadvantage() -> None:
    """p. 186's Poisoned, on the Unarmed Strike — which read no condition at all before
    0091."""
    sick = _encounter(_brawler(conditions=_held(Condition.POISONED)))

    assert _flags(_punch(sick)) == (False, True)


# --- The defender's ---------------------------------------------------------------------------


def test_a_paralyzed_target_is_hit_with_advantage_by_a_pan_and_a_fist() -> None:
    """p. 186's Paralyzed: "Attack rolls against you have Advantage." The automatic Critical
    Hit beside it was already read by both resolvers; the Advantage was not."""
    helpless = _encounter(_brawler(PAN), conditions=_held(Condition.PARALYZED))

    assert _flags(_swing(helpless)) == (True, False)
    assert _flags(_punch(helpless)) == (True, False)


def test_a_prone_target_gives_advantage_up_close_and_disadvantage_to_a_throw() -> None:
    """p. 186's Prone is the reason the composition takes positions: "has Advantage if the
    attacker is within 5 feet of you. Otherwise, that attack roll has Disadvantage." A throw
    from thirty feet is the second half — and beyond normal range besides, so the one flag
    carries both."""
    near = _encounter(_brawler(PAN), conditions=_held(Condition.PRONE))
    far = _encounter(_brawler(PAN), feet=30, conditions=_held(Condition.PRONE))

    assert _flags(_swing(near)) == (True, False)
    assert _flags(_throw(far)) == (False, True)


def test_a_dodging_target_puts_disadvantage_on_a_punch_and_a_swing() -> None:
    """p. 181's Dodge: "any attack roll made against you has Disadvantage"."""
    dodging = _encounter(_brawler(PAN), actions=ActionBudget(dodging=True))

    assert _flags(_punch(dodging)) == (False, True)
    assert _flags(_swing(dodging)) == (False, True)


# --- p. 90's tokens ------------------------------------------------------------------------


def test_a_vex_token_reaches_the_unarmed_strike_and_is_spent_by_it() -> None:
    """p. 90: "Advantage on your next attack roll against that creature" — the next attack
    roll, whatever makes it. A punch is one, and it spends the token whether it lands (0049)."""
    vexed = _token(_encounter(_brawler()), VEX_RULE_ID, Advantage.ADVANTAGE)

    proposal = _punch(vexed)
    assert _flags(proposal) == (True, False)
    assert [e.pending_advantage.rule_id for e in _spent(proposal) if e.pending_advantage] == [
        VEX_RULE_ID
    ]


def test_a_sap_penalty_reaches_the_improvised_throw_and_is_spent_by_it() -> None:
    """p. 90: "that creature has Disadvantage on its next attack roll" — and a thrown chair is
    the creature's next attack roll."""
    sapped = _token(_encounter(_brawler(PAN)), SAP_RULE_ID, Advantage.DISADVANTAGE)

    proposal = _throw(sapped)
    assert _flags(proposal) == (False, True)
    assert [e.pending_advantage.rule_id for e in _spent(proposal) if e.pending_advantage] == [
        SAP_RULE_ID
    ]


def test_without_a_token_nothing_is_spent() -> None:
    """The discriminating case for the spend: an `always` that emitted a spend for a token
    nobody held would drop a token that was never there — harmless — and would be wrong the
    day it was not."""
    assert _spent(_punch(_encounter(_brawler()))) == []
    assert _spent(_swing(_encounter(_brawler(PAN)))) == []


# --- p. 8's cancellation, by construction -----------------------------------------------------


def test_a_blinded_puncher_and_a_paralyzed_target_reach_both_flags() -> None:
    """Every source lands on the same pair of flags, so p. 8's rule — "if circumstances cause
    a roll to have both Advantage and Disadvantage, the roll has neither" — is the d20's to
    apply and not a second mechanism here. Both flags set is the whole of this resolver's
    answer."""
    both = _encounter(
        _brawler(conditions=_held(Condition.BLINDED)), conditions=_held(Condition.PARALYZED)
    )

    assert _flags(_punch(both)) == (True, True)


# --- p. 16's water -------------------------------------------------------------------------


def _underwater(state: EncounterState) -> EncounterState:
    return replace(state, underwater=True)


def test_a_bludgeoning_object_swung_underwater_is_impeded() -> None:
    """p. 16: "a creature that lacks a Swim Speed has Disadvantage on the attack roll unless
    the weapon deals Piercing damage" — and an improvised weapon is "an object wielded as a
    makeshift weapon" (p. 183), which is a weapon in p. 16's sentence."""
    assert _flags(_swing(_underwater(_encounter(_brawler(PAN))))) == (False, True)


def test_a_piercing_object_and_a_swimmer_are_both_exempt() -> None:
    """The two exemptions, each on its own: the type the ruleset stated for this use, and a
    Swim Speed on the wielder."""
    glass = _underwater(_encounter(_brawler(GLASS)))
    swimmer = _underwater(_encounter(_brawler(PAN, speeds=Speeds(walk=30, swim=30))))

    assert _flags(_swing(glass, GLASS.id)) == (False, False)
    assert _flags(_swing(swimmer)) == (False, False)


def test_a_throw_underwater_has_disadvantage_within_twenty_feet_and_misses_beyond() -> None:
    """p. 16's ranged clause, with p. 183's normal range where p. 90's would be: Disadvantage
    within it, and beyond it an automatic miss that rolls nothing — while the object still
    leaves the hand, because the throw was made."""
    near = _underwater(_encounter(_brawler(PAN), feet=15))
    far = _underwater(_encounter(_brawler(PAN), feet=30))

    assert _flags(_throw(near)) == (False, True)

    missed = _throw(far)
    assert missed.test is None
    assert [e.kind for e in missed.outcome if isinstance(e, Effect)] == [
        EffectKind.AUTOMATIC_FAILURE
    ]
    assert EffectKind.OBJECT_DETACHED in {e.kind for e in missed.always if isinstance(e, Effect)}


def test_a_punch_underwater_is_not_impeded() -> None:
    """p. 16 impedes "a melee attack roll with a weapon", and p. 177 counts "a weapon or an
    Unarmed Strike" as two things. A fist is not the first, so the clause does not reach it —
    a rule the document does not state, excluded rather than extended (R31)."""
    assert _flags(_punch(_underwater(_encounter(_brawler())))) == (False, False)


# --- The page -----------------------------------------------------------------------------


def test_p16s_melee_clause_is_asserted_now_that_a_rule_rests_on_it() -> None:
    """`_impeded_underwater` has quoted p. 16's melee sentence since #446, and the verifier
    asserted only the ranged one — a quotation is not an assertion (#371's shape). The
    improvised swing rests on the melee sentence, so 0091 adds it; the pattern is the sentence
    as recalled, and a run of the verifier by somebody holding the document confirms it."""
    # Loaded by name rather than imported: the script's optional PDF reader is not a
    # dependency of the test suite, and an import statement would put the whole script in
    # front of mypy for one tuple.
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    clauses = importlib.import_module("verify_d20_rules").CLAUSES

    melee = [
        pattern
        for page, _note, pattern in clauses
        if page == 16 and "lacks a" in pattern and "Swim Speed" in pattern
    ]
    assert len(melee) == 1
    assert "unless the weapon deals Piercing" in melee[0]
