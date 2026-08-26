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
from dataclasses import replace
from pathlib import Path

import pytest

from srd_rules_engine.core.adjudicate import (
    Adjudicator,
    Declaration,
    EffectKind,
    Intent,
    Status,
)
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.damage import DamageType, Defences
from srd_rules_engine.core.hazards import (
    BURNING_DIE_SIDES,
    BURNING_RULE_ID,
    BURNING_VERIFICATION,
    FALLING_VERIFICATION,
    MAX_FALLING_DICE,
    burning_resolver,
    burning_rule,
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
    load_ruleset,
)
from srd_rules_engine.core.state import Combatant, EncounterState, Hazards
from srd_rules_engine.core.triggers import Catalogue
from srd_rules_engine.loop import Narrated, TurnLoop
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


# --- Burning: the other hazard with an occasion (#140, 0027 clause 5) --------------------


def _burning(cid: str = "pc") -> EncounterState:
    state = encounter()
    alight = replace(state.combatant(cid), hazards=Hazards(burning=True))
    return EncounterState(
        generation=0,
        combatants=tuple(alight if c.id == cid else c for c in state.combatants),
    ).with_initiative({"pc": 18, "boar": 4})


def _burn_loop(tmp_path: Path, *, seed: int = 31337) -> TurnLoop:
    return TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_ruleset((burning_rule(),)),
            resolvers={BURNING_RULE_ID: burning_resolver()},
            fact_types={},
            port=JsonMemoryStore(tmp_path / "m.json"),
            ledger=Ledger.open(
                tmp_path / "l.jsonl", engine_version="t", catalogue_version=1, session_id="s"
            ),
            seed_source=lambda: seed,
        )
    )


def _run_start(loop: TurnLoop, state: EncounterState, actor_id: str = "pc") -> object:
    generator = loop.start_turn(state, actor_id)
    try:
        next(generator)
        while True:
            generator.send(Narrated(text="it burns"))
    except StopIteration as stop:
        return stop.value


def test_burning_is_not_one_of_the_fifteen_conditions() -> None:
    """0027 clause 5. Filing it among the conditions would corrupt the one structure whose
    completeness is a checked claim — 15/15 means fifteen."""
    assert "burning" not in {c.value for c in Condition}
    assert not hasattr(Conditions(), "burning")
    assert Hazards().burning is False


def test_a_burning_creature_owes_the_fire_at_the_start_of_its_turn(tmp_path: Path) -> None:
    """p. 178: "at the start of each of its turns" — the phase the death save fires in, not
    the one save-ends lives in."""
    obligations = _burn_loop(tmp_path).start_turn_obligations(_burning(), "pc")

    assert [o.rule_id for o in obligations] == [BURNING_RULE_ID]
    assert "burning" in obligations[0].label


def test_a_creature_that_is_not_burning_owes_nothing(tmp_path: Path) -> None:
    assert _burn_loop(tmp_path).start_turn_obligations(encounter(), "pc") == ()


def test_burning_is_not_an_end_of_turn_obligation(tmp_path: Path) -> None:
    """The phase distinction, pinned. Suffocation is the hazard that fires at a turn's end
    (p. 189), and it is not built — an engine that put Burning there would deal its damage
    once per turn and look entirely correct."""
    assert _burn_loop(tmp_path).end_turn_obligations(_burning(), "pc") == ()


def test_the_fire_deals_a_d4_of_fire_damage(tmp_path: Path) -> None:
    """p. 178, and the type matters: a creature with Resistance or Immunity to Fire is the
    common case for a thing that is on fire."""
    started = _run_start(_burn_loop(tmp_path), _burning())
    (ruling,) = started.rulings  # type: ignore[attr-defined]

    damage = next(e for e in ruling.effects if e.kind is EffectKind.DAMAGE)
    assert "1d4" in damage.description
    assert 1 <= damage.amount <= BURNING_DIE_SIDES


def test_immunity_to_fire_leaves_a_burning_creature_unharmed(tmp_path: Path) -> None:
    """p. 17's defences act on it like any other damage, which is the whole reason the
    resolver names a damage type rather than proposing a bare amount."""
    immune = Defences(immunities=frozenset({DamageType.FIRE}))
    state = encounter(defences=immune)
    alight = replace(state.combatant("pc"), hazards=Hazards(burning=True))
    state = EncounterState(
        generation=0,
        combatants=tuple(alight if c.id == "pc" else c for c in state.combatants),
    ).with_initiative({"pc": 18, "boar": 4})

    started = _run_start(_burn_loop(tmp_path), state)
    ruling = started.rulings[0]  # type: ignore[attr-defined]
    assert next(e for e in ruling.effects if e.kind is EffectKind.DAMAGE).amount == 0


def test_burning_resolves_without_a_d20(tmp_path: Path) -> None:
    """0027 clause 6. p. 178 asks nothing of the dice but the damage."""
    started = _run_start(_burn_loop(tmp_path), _burning())
    assert started.rulings[0].result is None  # type: ignore[attr-defined]


def test_the_fire_burns_once_per_turn(tmp_path: Path) -> None:
    """Discharged like any other obligation. One that stayed outstanding would burn the
    creature to death inside a single turn, producing a plausible ruling at every step."""
    loop = _burn_loop(tmp_path)
    started = _run_start(loop, _burning())

    assert len(started.rulings) == 1  # type: ignore[attr-defined]
    assert loop.start_turn_obligations(started.state, "pc") == ()  # type: ignore[attr-defined]


def test_a_creature_not_burning_cannot_be_ruled_as_burning(tmp_path: Path) -> None:
    """Read off state, never declared. A resolver that trusted the declaration would let a
    caller set fire to anything by naming the rule."""
    resolver = burning_resolver()
    with pytest.raises(ValueError, match="not burning"):
        resolver(
            state=encounter(),
            declaration=Declaration(
                actor_id="pc", intent=Intent(improvised=True, label="x"), rule_id=BURNING_RULE_ID
            ),
            facts={},
        )


def test_nothing_here_claims_the_fire_went_out(tmp_path: Path) -> None:
    """R7, and the disclosed gap. p. 178 puts fire out when doused, submerged, suffocated or
    by an action — none of which this engine can observe or spend, so a burning creature
    burns until a caller clears the flag."""
    started = _run_start(_burn_loop(tmp_path), _burning())
    assert any("went out" in line for line in started.rulings[0].bounds.may_not)  # type: ignore[attr-defined]


def test_burning_carries_a_verified_citation() -> None:
    assert BURNING_VERIFICATION.state is VerificationState.VERIFIED
    assert "p. 178" in (BURNING_VERIFICATION.reference or "")
