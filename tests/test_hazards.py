"""Falling, and the qualifier attached to its Prone (#140).

Two halves of p. 182, and the second is the one an implementer drops:

> A creature that falls takes 1d6 Bludgeoning damage at the end of the fall for every 10
> feet it fell, to a maximum of 20d6. When the creature lands, it has the Prone condition
> **unless it avoids taking any damage from the fall**.

An engine that applies Prone to every fall passes any test that only checks a fall knocks
you down, and both sentences are asserted in `scripts/verify_d20_rules.py` precisely so the
qualifier cannot be quietly dropped.

The arithmetic is tested against the wrong answer as well as the right one, because two
plausible readings of "for every 10 feet" — rounding up, or scaling the distance rather than
the dice — produce a believable number for most falls and the wrong one at the boundaries.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from srd_rules_engine.core.adjudicate import (
    Adjudicator,
    Declaration,
    EffectKind,
    Intent,
    Status,
)
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.damage import DamageType, Defences
from srd_rules_engine.core.hazards import (
    FALLING_VERIFICATION,
    MAX_FALLING_DICE,
    falling_dice,
    falling_resolver,
)
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.read_surface import read
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    VerificationState,
    load_fixture_ruleset,
)
from srd_rules_engine.core.state import Combatant, EncounterState
from srd_rules_engine.core.triggers import Catalogue
from srd_rules_engine.memory.store import JsonMemoryStore

END_TURN = "end-turn"

FALL = Rule(
    id="a-fall",
    summary="A fall, resolved as the hazard it is.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Wires core.hazards.falling_resolver for these tests.",
)


def combatant(cid: str, *, defences: Defences | None = None) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=200,
        max_hit_points=200,
        armour_class=13,
        abilities={"str": 10},
        proficiency_bonus=2,
        defences=defences or Defences(),
    )


def encounter(*, defences: Defences | None = None) -> EncounterState:
    return EncounterState.new(
        [combatant("pc", defences=defences), combatant("boar")]
    ).with_initiative({"pc": 18, "boar": 4})


def build(tmp_path: Path, feet: int, *, seed: int = 31337) -> Adjudicator:
    ledger = Ledger.open(
        tmp_path / "ledger.jsonl", engine_version="test", catalogue_version=1, session_id="s-1"
    )
    supply = itertools.cycle((seed,))
    return Adjudicator(
        ruleset=load_fixture_ruleset("hazards", [FALL]),
        resolvers={"a-fall": falling_resolver(feet)},
        fact_types={},
        port=JsonMemoryStore(tmp_path / "memory.json"),
        ledger=ledger,
        catalogue=Catalogue(version=1, triggers=()),
        seed_source=lambda: next(supply),
    )


def declare(state: EncounterState) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=END_TURN),
        rule_id="a-fall",
        alternatives=offered.actions,
        read_token=offered.token,
    )


# --- The arithmetic, and the two readings that are wrong --------------------------------


@pytest.mark.parametrize(
    ("feet", "dice"),
    [(10, 1), (19, 1), (20, 2), (35, 3), (100, 10)],
)
def test_a_fall_deals_one_die_per_whole_ten_feet(feet: int, dice: int) -> None:
    """p. 182 counts whole 10-foot increments and states no rule for a partial one.

    19 feet is the case that separates this from rounding up: a reading that rounded would
    give 2d6, and would agree with this one at every multiple of ten.
    """
    assert falling_dice(feet) == dice


def test_the_cap_is_on_the_dice_and_not_on_the_distance() -> None:
    """ "to a maximum of 20d6" (p. 182). A creature that falls 500 feet and one that falls
    200 take the same dice, which is the wrong-looking answer that is right."""
    assert falling_dice(200) == MAX_FALLING_DICE == 20
    assert falling_dice(500) == MAX_FALLING_DICE
    assert falling_dice(10_000) == MAX_FALLING_DICE


def test_a_fall_below_ten_feet_deals_nothing() -> None:
    assert falling_dice(0) == 0
    assert falling_dice(9) == 0


def test_a_negative_fall_is_refused() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        falling_dice(-10)


def test_a_fall_too_short_to_deal_dice_is_not_adjudicated() -> None:
    """A ruling recording that nothing happened is not the same as a rule deciding that
    nothing happens, and the ledger cannot tell the two apart afterwards."""
    with pytest.raises(ValueError, match="no dice"):
        falling_resolver(9)


# --- Through the one entry point --------------------------------------------------------


def test_a_fall_resolves_without_a_d20(tmp_path: Path) -> None:
    """0027 clause 6. There is no test in p. 182, so there is none here."""
    ruling, _ = build(tmp_path, 30).adjudicate(encounter(), declare(encounter()))

    assert ruling.status is Status.RULED
    assert ruling.result is None, "a fall is not a test"
    assert ruling.effects


def test_the_engine_rolls_the_falling_damage(tmp_path: Path) -> None:
    """R4. The resolver declares 3d6 for a 30-foot fall and supplies no number."""
    ruling, state = build(tmp_path, 30).adjudicate(encounter(), declare(encounter()))

    damage = next(e for e in ruling.effects if e.kind is EffectKind.DAMAGE)
    assert "3d6" in damage.description
    assert 3 <= damage.amount <= 18
    assert state.combatant("pc").hit_points == 200 - damage.amount


def test_the_damage_is_bludgeoning_so_defences_can_act_on_it(tmp_path: Path) -> None:
    """p. 182 names the type, and without it p. 17's arithmetic cannot run at all."""
    resistant = Defences(resistances=frozenset({DamageType.BLUDGEONING}))
    plain, _ = build(tmp_path / "a", 100).adjudicate(encounter(), declare(encounter()))
    halved, _ = build(tmp_path / "b", 100).adjudicate(
        encounter(defences=resistant), declare(encounter(defences=resistant))
    )

    plain_amount = next(e for e in plain.effects if e.kind is EffectKind.DAMAGE).amount
    halved_amount = next(e for e in halved.effects if e.kind is EffectKind.DAMAGE).amount
    assert halved_amount == plain_amount // 2


# --- The qualifier ----------------------------------------------------------------------


def test_landing_leaves_the_creature_prone(tmp_path: Path) -> None:
    ruling, state = build(tmp_path, 30).adjudicate(encounter(), declare(encounter()))

    applied = [e for e in ruling.effects if e.kind is EffectKind.CONDITION_APPLIED]
    assert [e.condition for e in applied] == [Condition.PRONE]
    assert state.combatant("pc").conditions.has(Condition.PRONE)


def test_a_creature_immune_to_bludgeoning_takes_no_damage_and_is_not_prone(
    tmp_path: Path,
) -> None:
    """p. 182's qualifier, in the one case decidable before the dice are thrown.

    An engine that applies Prone to every fall passes every other test in this file. This
    is the one that separates "it fell" from "it was hurt by falling".
    """
    immune = Defences(immunities=frozenset({DamageType.BLUDGEONING}))
    state = encounter(defences=immune)
    ruling, after = build(tmp_path, 30).adjudicate(state, declare(state))

    damage = next(e for e in ruling.effects if e.kind is EffectKind.DAMAGE)
    assert damage.amount == 0, "immunity zeroes it whatever the dice said"
    assert not [e for e in ruling.effects if e.kind is EffectKind.CONDITION_APPLIED]
    assert not after.combatant("pc").conditions.has(Condition.PRONE)


def test_the_bounds_refuse_the_prone_claim_when_it_was_not_applied(tmp_path: Path) -> None:
    """R7. The narrator is told it may not say the creature is Prone, rather than merely
    not being told that it is — an absence is not a bound."""
    immune = Defences(immunities=frozenset({DamageType.BLUDGEONING}))
    state = encounter(defences=immune)
    ruling, _ = build(tmp_path, 30).adjudicate(state, declare(state))

    assert any("is Prone" in line for line in ruling.bounds.may_not)
    assert not any("now Prone" in line for line in ruling.bounds.may)


def test_a_fall_may_not_be_narrated_as_something_resisted(tmp_path: Path) -> None:
    """There was no test, so nothing was passed, failed, resisted or avoided."""
    ruling, _ = build(tmp_path, 30).adjudicate(encounter(), declare(encounter()))
    assert any("not a test" in line for line in ruling.bounds.may_not)


# --- Provenance -------------------------------------------------------------------------


def test_falling_carries_a_verified_citation_naming_both_sentences() -> None:
    """Both halves of p. 182 are asserted in `scripts/verify_d20_rules.py` (#140). A
    reference naming only the damage would leave the qualifier resting on nothing."""
    assert FALLING_VERIFICATION.state is VerificationState.VERIFIED
    reference = FALLING_VERIFICATION.reference or ""
    assert "p. 182" in reference
    assert "Prone" in reference


def test_the_prone_qualifier_is_asserted_against_the_document() -> None:
    """Presence, not truth — the verifier needs the PDF and CI has no copy."""
    verifier = (Path(__file__).resolve().parents[1] / "scripts" / "verify_d20_rules.py").read_text()
    assert "it has the Prone condition unless it avoids taking any" in verifier
