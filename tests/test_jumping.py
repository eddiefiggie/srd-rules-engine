"""Jumping, and the pair of numbers that is easiest to swap (pp. 183-185).

A Long Jump is the Strength **score** in feet. A High Jump is 3 plus the Strength
**modifier**. Both are "up to N feet if you move at least 10 feet immediately before", both
halve for a standing jump, and both cost a foot of movement per foot jumped — so the entries
read almost identically and the one thing that differs between them is which number they take.

A Strength 16 creature long-jumps **16 feet** and high-jumps **6**. An engine that used the
modifier for both would give it 3 and 3, and nothing about that looks wrong.

`high-jump` is deliberately not claimed in the inventory. p. 183 also says what the creature
can *reach* — "the height of the jump plus 1½ times your height" — and nothing here knows how
tall anything is. The arithmetic exists; the entry says more than it computes.
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Catalogue,
    Combatant,
    Condition,
    EffectKind,
    EncounterState,
    Ledger,
    Status,
    load_ruleset,
)
from srd_rules_engine.core.adjudicate import Declaration, Intent
from srd_rules_engine.core.hazards import (
    LANDING_DC,
    LANDING_RULE_ID,
    landing_resolver,
    landing_rule,
)
from srd_rules_engine.core.position import high_jump_feet, long_jump_feet
from srd_rules_engine.core.read_surface import read
from srd_rules_engine.memory.store import JsonMemoryStore

# --- The two numbers -----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("score", "running", "feet"), [(16, True, 16), (16, False, 8), (3, True, 3)]
)
def test_a_long_jump_is_the_strength_score(score: int, running: bool, feet: int) -> None:
    """pp. 184-185: "a number of feet up to your Strength score", halved standing."""
    assert long_jump_feet(score, running=running) == feet


@pytest.mark.parametrize(
    ("modifier", "running", "feet"), [(3, True, 6), (3, False, 3), (0, True, 3), (1, False, 2)]
)
def test_a_high_jump_is_three_plus_the_modifier(modifier: int, running: bool, feet: int) -> None:
    """p. 183. Note 3 + 1 = 4, halved is 2 — rounded down like everything else (p. 187)."""
    assert high_jump_feet(modifier, running=running) == feet


def test_the_two_take_different_numbers_from_the_same_creature() -> None:
    """The whole point of testing them together. Strength 16 is score 16, modifier +3."""
    assert long_jump_feet(16) == 16
    assert high_jump_feet(3) == 6, "an engine using the modifier for both would say 3 and 3"


def test_a_high_jump_is_floored_at_zero_and_never_negative() -> None:
    """p. 183: "(minimum of 0 feet)". A Strength 1 creature has a -5 modifier, and 3 + -5
    is not a distance anything leaps."""
    assert high_jump_feet(-5) == 0
    assert high_jump_feet(-5, running=False) == 0


def test_a_negative_strength_score_is_refused() -> None:
    with pytest.raises(ValueError, match="Strength score"):
        long_jump_feet(-1)


# --- The landing, which is the half an implementation drops ---------------------------------


def _jumper(cid: str = "pc", *, dex: int = 10) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 16, "dex": dex},
        proficiency_bonus=2,
    )


def _loop(tmp_path: Path, *, seed: int) -> Adjudicator:
    tmp_path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=load_ruleset((landing_rule(),)),
        resolvers={LANDING_RULE_ID: landing_resolver()},
        fact_types={},
        port=JsonMemoryStore(tmp_path / "m.json"),
        ledger=Ledger.open(
            tmp_path / "l.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        catalogue=Catalogue(version=1, triggers=()),
        seed_source=lambda: next(itertools.cycle((seed,))),
    )


def _land(tmp_path: Path, *, seed: int, dex: int = 10) -> tuple[object, EncounterState]:
    state = EncounterState.new([_jumper(dex=dex)]).with_initiative({"pc": 10})
    offered = read(state, "pc")
    declaration = Declaration(
        actor_id="pc",
        intent=Intent(improvised=True, label="lands in the scree"),
        rule_id=LANDING_RULE_ID,
        alternatives=offered.actions,
        read_token=offered.token,
    )
    return _loop(tmp_path, seed=seed).adjudicate(state, declaration)


def _seed_where(tmp_path: Path, *, succeeds: bool) -> int:
    for seed in range(400):
        ruling, _ = _land(tmp_path / f"probe-{seed}", seed=seed)
        result = ruling.result  # type: ignore[attr-defined]
        if result is not None and result.succeeded is succeeds:
            return seed
    raise AssertionError("no seed found in 400")


def test_the_landing_is_a_dc_ten_dexterity_check(tmp_path: Path) -> None:
    """p. 185, and unlike Falling this one *is* a test — the document states a DC, so the
    d20 decides it rather than a distance."""
    ruling, _ = _land(tmp_path / "one", seed=7)
    result = ruling.result  # type: ignore[attr-defined]

    assert result is not None
    assert result.target == LANDING_DC == 10
    assert any(m.source == "ability:dex" for m in result.modifiers)


def test_a_failed_landing_leaves_the_creature_prone(tmp_path: Path) -> None:
    seed = _seed_where(tmp_path / "fails", succeeds=False)
    ruling, after = _land(tmp_path / "prone", seed=seed)

    assert ruling.status is Status.RULED  # type: ignore[attr-defined]
    applied = [e for e in ruling.effects if e.kind is EffectKind.CONDITION_APPLIED]  # type: ignore[attr-defined]
    assert [e.condition for e in applied] == [Condition.PRONE]
    assert after.combatant("pc").conditions.has(Condition.PRONE)


def test_a_successful_landing_leaves_it_standing(tmp_path: Path) -> None:
    """The control. p. 185 gives Prone on a failure and nothing on a success — an engine
    that applied it either way would pass every test that only jumps badly."""
    seed = _seed_where(tmp_path / "passes", succeeds=True)
    ruling, after = _land(tmp_path / "upright", seed=seed)

    assert not [e for e in ruling.effects if e.kind is EffectKind.CONDITION_APPLIED]  # type: ignore[attr-defined]
    assert not after.combatant("pc").conditions.has(Condition.PRONE)


def test_the_landing_deals_no_damage(tmp_path: Path) -> None:
    """p. 185 gives Prone and no damage. Falling is the entry that deals damage, and the two
    are easy to blend because both are about arriving on the ground."""
    seed = _seed_where(tmp_path / "nodmg", succeeds=False)
    ruling, _ = _land(tmp_path / "checked", seed=seed)
    assert not [e for e in ruling.effects if e.kind is EffectKind.DAMAGE]  # type: ignore[attr-defined]


def test_the_bounds_refuse_a_claim_about_the_distance(tmp_path: Path) -> None:
    """R7. The check decides footing, not whether the jump was long enough — and a narrator
    told only that the roll failed would reasonably say the creature fell short."""
    ruling, _ = _land(tmp_path / "bounds", seed=7)
    assert any("fell short" in line for line in ruling.bounds.may_not)  # type: ignore[attr-defined]
