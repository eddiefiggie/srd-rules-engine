"""Gaining an Exhaustion level through a ruling (#178).

`Conditions.exhaustion_level` was a field set at construction. Nothing could raise it: no
`EffectKind`, no state mutator, no method on `Conditions`. That is #119's shape one field
along — conditions once reached state only by callers invoking `with_condition` directly,
"a mechanical change with no roll, no seed, no citation and no ledger entry behind it, which
is the thing R1 exists to prevent".

It blocked three of the five hazards, and #140 did not see it: that issue reasoned the
hazards were cheap partly because "Exhaustion is 15/15 implemented". The **condition** is.
Raising a **level** was not, and the inventory cannot show that difference — the shape
`exhaustion` is marked implemented on the strength of the condition and its arithmetic.

Two things here are worth testing against the wrong answer:

* **The level is where all the arithmetic lives.** p. 181 reduces every D20 Test by twice it
  and Speed by five feet times it. An engine that applied `Condition.EXHAUSTION` without a
  level would hold the one member of the fifteen that carries no effect, and look correct.
* **Six is death and seven is nothing.** p. 181: "You die if your Exhaustion level is 6." A
  gain that would pass 6 is refused rather than clamped — clamping discards the caller's
  arithmetic silently, and a creature stuck at 5 that the rules have killed is the quiet
  direction to fail in.

What this does **not** do is remove a level. Four rules do that and no two agree (#180).
"""

from __future__ import annotations

import itertools
from pathlib import Path

import pytest

from srd_rules_engine.core.adjudicate import (
    Adjudicator,
    Declaration,
    Effect,
    EffectKind,
    Intent,
    Proposal,
    Status,
)
from srd_rules_engine.core.conditions import MAX_EXHAUSTION, Condition
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.read_surface import read
from srd_rules_engine.core.rules import Rule, RuleProvenance, load_fixture_ruleset
from srd_rules_engine.core.state import Combatant, EncounterState
from srd_rules_engine.core.triggers import Catalogue
from srd_rules_engine.memory.store import JsonMemoryStore

END_TURN = "end-turn"

#: An invented source, so a level in these tests names a rule the way 0028 requires.
MARCH = "a-tiring-march"

TIRING = Rule(
    id="something-tiring",
    summary="An invented rule that costs an Exhaustion level.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Exercises EffectKind.EXHAUSTION_GAINED through the one entry point.",
)


def tiring(*, state, declaration, facts):  # type: ignore[no-untyped-def]
    return Proposal(
        outcome=(
            Effect(
                kind=EffectKind.EXHAUSTION_GAINED,
                target_id=declaration.actor_id,
                amount=1,
                description="an invented exertion",
            ),
        ),
        citations=("fixture:something-tiring",),
    )


def combatant(cid: str, *, level: int = 0) -> Combatant:
    from srd_rules_engine.core.conditions import Conditions

    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=30,
        max_hit_points=30,
        armour_class=13,
        abilities={"str": 10, "con": 10},
        proficiency_bonus=2,
        conditions=Conditions(exhaustion_levels=(MARCH,) * level),
    )


def encounter(*, level: int = 0) -> EncounterState:
    return EncounterState.new([combatant("pc", level=level), combatant("boar")]).with_initiative(
        {"pc": 18, "boar": 4}
    )


def build(tmp_path: Path) -> Adjudicator:
    return Adjudicator(
        ruleset=load_fixture_ruleset("exhaustion", [TIRING]),
        resolvers={"something-tiring": tiring},
        fact_types={},
        port=JsonMemoryStore(tmp_path / "m.json"),
        ledger=Ledger.open(
            tmp_path / "l.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        catalogue=Catalogue(version=1, triggers=()),
        seed_source=lambda: next(itertools.cycle((7,))),
    )


def declare(state: EncounterState) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=END_TURN),
        rule_id="something-tiring",
        alternatives=offered.actions,
        read_token=offered.token,
    )


# --- The state mutator ------------------------------------------------------------------


def test_a_level_can_be_gained() -> None:
    """The gap #178 was filed for. Before it, nothing could move this number."""
    after = encounter().with_exhaustion("pc", MARCH)
    assert after.combatant("pc").conditions.exhaustion_level == 1


def test_levels_are_cumulative() -> None:
    """p. 181: "This condition is cumulative. Each time you receive it, you gain 1
    Exhaustion level." So it adds rather than sets — an engine that set the level would
    leave a creature exhausted three times no worse off than one exhausted once."""
    after = (
        encounter()
        .with_exhaustion("pc", MARCH)
        .with_exhaustion("pc", MARCH)
        .with_exhaustion("pc", MARCH)
    )
    assert after.combatant("pc").conditions.exhaustion_level == 3


def test_the_condition_follows_from_the_level() -> None:
    """`Conditions` already derives it, so nothing applies Exhaustion alongside the level —
    which would be two sources for one fact."""
    assert not encounter().combatant("pc").conditions.has(Condition.EXHAUSTION)
    assert (
        encounter()
        .with_exhaustion("pc", MARCH)
        .combatant("pc")
        .conditions.has(Condition.EXHAUSTION)
    )


def test_the_arithmetic_moves_with_the_level() -> None:
    """p. 181: the roll is reduced by twice the level, and Speed by five feet times it. This
    is why raising the level is the mechanic and applying the condition is not."""
    tired = encounter().with_exhaustion("pc", MARCH, 2).combatant("pc").conditions
    assert tired.d20_penalty == -4
    assert tired.speed_after(30) == 20


def test_reaching_six_is_death() -> None:
    """p. 181: "You die if your Exhaustion level is 6." Six is a state the rules describe."""
    dying = encounter(level=5).with_exhaustion("pc", MARCH)
    assert dying.combatant("pc").conditions.exhaustion_level == MAX_EXHAUSTION
    assert dying.combatant("pc").conditions.dead_of_exhaustion


def test_passing_six_is_refused_rather_than_clamped() -> None:
    """Seven is not a state the document describes.

    Clamping would discard the caller's arithmetic silently and leave a creature at 5 that
    the rules have killed — the quiet direction to fail in.
    """
    with pytest.raises(ValueError, match="dies at 6"):
        encounter(level=5).with_exhaustion("pc", MARCH, 2)


def test_a_gain_of_less_than_one_is_refused() -> None:
    """Removal runs by its own rules and is not a negative gain (#180). Four rules remove
    levels and no two agree, so a mutator that accepted -1 would be quietly deciding which
    of them applied."""
    with pytest.raises(ValueError, match="at least one level"):
        encounter().with_exhaustion("pc", MARCH, 0)
    with pytest.raises(ValueError, match="at least one level"):
        encounter().with_exhaustion("pc", MARCH, -1)


# --- Through the one entry point ---------------------------------------------------------


def test_a_level_reaches_state_through_a_ruling(tmp_path: Path) -> None:
    """R1, and the whole point of #178. Before it, a level could only be set by constructing
    a `Conditions` — no roll, no seed, no citation, no ledger entry."""
    ruling, state = build(tmp_path).adjudicate(encounter(), declare(encounter()))

    assert ruling.status is Status.RULED
    assert state.combatant("pc").conditions.exhaustion_level == 1


def test_the_ledger_records_which_effect_it_was(tmp_path: Path) -> None:
    """A record that says a creature changed without saying how is the state #119 fixed for
    conditions."""
    ruling, _ = build(tmp_path).adjudicate(encounter(), declare(encounter()))

    (effect,) = ruling.effects
    assert effect.kind is EffectKind.EXHAUSTION_GAINED
    assert effect.amount == 1
