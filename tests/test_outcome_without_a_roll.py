"""An outcome that never rolls a d20, and the two places that shape can go wrong (#170).

Until 0027 clause 6 there was one path to an outcome and it always rolled a d20:
`Proposal.test` was a required field and `adjudicate` called `roll_d20` unconditionally.
Falling (p. 182) is damage per 10 feet to a cap with no test anywhere in it, and reaching it
by inventing a test would be inventing a roll the rules do not call for — R4 from the other
direction than usual.

Two things about this are easy to get wrong, and both are silent:

* **Narration.** A testless outcome has no success and no failure. Bounds saying "the save
  succeeded" over a fall would describe a roll that never happened, and R7's bounds are
  advisory — nothing downstream would catch it.
* **Replay.** `UNREPLAYABLE` means *the record is too thin to reconstruct*. A rule that never
  rolled is not thin, it is complete; filing it under that verdict would make every automatic
  outcome permanently unverifiable while reading like an ordinary limitation. The two are
  told apart by a recorded `testless` field rather than by `roll` being absent, because from
  the absence alone they are identical — and inferring from an absence is exactly how the
  advantage gap got in (`REPLAYABLE_FROM = 2`).

The rules here are invented fixtures. No SRD value appears.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from pathlib import Path

import pytest

from srd_rules_engine.core.adjudicate import (
    Adjudicator,
    DamageDice,
    Declaration,
    Effect,
    EffectKind,
    Intent,
    Proposal,
    Status,
)
from srd_rules_engine.core.d20 import D20Test, TestKind
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.ledger_reader import read_ledger
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import read
from srd_rules_engine.core.report import ReplayVerdict, replay
from srd_rules_engine.core.rules import Rule, RuleProvenance, load_fixture_ruleset
from srd_rules_engine.core.state import Combatant, EncounterState
from srd_rules_engine.core.triggers import Catalogue
from srd_rules_engine.memory.store import JsonMemoryStore

END_TURN = "end-turn"

DROP = Rule(
    id="a-long-drop",
    summary="An invented hazard that deals dice and asks nothing of the d20.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Exercises 0027 clause 6: an outcome with no test in it.",
)


def a_long_drop(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    """No test. The dice are still the engine's — declared here, rolled by `adjudicate`."""
    return Proposal(
        citations=("fixture:a-long-drop",),
        outcome=(DamageDice(target_id=declaration.actor_id, count=3, sides=6, source="the drop"),),
        may_claim=("that the fall hurt",),
    )


RULESET = load_fixture_ruleset("testless", [DROP])
RESOLVERS = {"a-long-drop": a_long_drop}
CATALOGUE = Catalogue(version=1, triggers=())


def combatant(cid: str, hp: int = 40) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=hp,
        max_hit_points=40,
        armour_class=13,
        abilities={"str": 10},
        proficiency_bonus=2,
    )


def encounter() -> EncounterState:
    return EncounterState.new([combatant("pc"), combatant("boar")]).with_initiative(
        {"pc": 18, "boar": 4}
    )


def build(tmp_path: Path, *, seed: int = 4242) -> tuple[Adjudicator, Path]:
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = Ledger.open(ledger_path, engine_version="test", catalogue_version=1, session_id="s-1")
    supply = itertools.cycle((seed,))
    return (
        Adjudicator(
            ruleset=RULESET,
            resolvers=RESOLVERS,
            fact_types={},
            port=JsonMemoryStore(tmp_path / "memory.json"),
            ledger=ledger,
            catalogue=CATALOGUE,
            seed_source=lambda: next(supply),
        ),
        ledger_path,
    )


def declare(state: EncounterState) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=END_TURN),
        rule_id="a-long-drop",
        alternatives=offered.actions,
        read_token=offered.token,
    )


# --- The proposal itself ---------------------------------------------------------------


def test_a_proposal_may_carry_no_test() -> None:
    """0027 clause 6. Before #170 this raised, because `test` had no default."""
    proposal = Proposal(
        outcome=(Effect(kind=EffectKind.DAMAGE, target_id="pc", amount=1, description="invented"),)
    )
    assert proposal.test is None
    assert proposal.outcome


def test_a_proposal_with_neither_a_test_nor_an_outcome_is_refused() -> None:
    """It would append a Ruling that decided nothing, which reads exactly like a rule that
    had nothing to decide. A resolver defect, and silent without this."""
    with pytest.raises(ValueError, match="decides nothing"):
        Proposal()


def test_a_proposal_with_both_a_test_and_an_outcome_is_refused() -> None:
    """`outcome` is the branch taken when there is no test, so nothing would select it here
    — the effects would be silently dropped while the proposal looked complete."""
    with pytest.raises(ValueError, match="ambiguous"):
        Proposal(
            test=D20Test(kind=TestKind.CHECK, target=10, target_basis="invented"),
            outcome=(
                Effect(kind=EffectKind.DAMAGE, target_id="pc", amount=1, description="invented"),
            ),
        )


# --- Through the one entry point --------------------------------------------------------


def test_a_testless_rule_produces_an_outcome_and_no_roll(tmp_path: Path) -> None:
    """R1 is unchanged: this came through `adjudicate` like everything else."""
    adjudicator, _ = build(tmp_path)
    ruling, state = adjudicator.adjudicate(encounter(), declare(encounter()))

    assert ruling.status is Status.RULED
    assert ruling.is_outcome
    assert ruling.result is None, "there was no d20"
    assert ruling.effects, "and yet it decided something"
    assert state.combatant("pc").hit_points < 40


def test_the_engine_still_rolled_the_damage(tmp_path: Path) -> None:
    """R4. The resolver declared 3d6 and never supplied a number.

    A fixed amount would be a caller supplying a roll, which is what `DamageDice` exists to
    prevent — and the absence of a d20 must not become an excuse to reintroduce it.
    """
    adjudicator, _ = build(tmp_path)
    ruling, _ = adjudicator.adjudicate(encounter(), declare(encounter()))

    (effect,) = ruling.effects
    assert "3d6" in effect.description, "the record shows the dice, not just a number"
    assert 3 <= effect.amount <= 18, "3d6, and nothing outside its range"


def test_the_same_seed_reproduces_the_same_damage(tmp_path: Path) -> None:
    """The seed is drawn whether or not a d20 is rolled, which is what keeps a testless
    outcome reproducible at all."""
    first, _ = build(tmp_path / "a", seed=99)
    second, _ = build(tmp_path / "b", seed=99)
    one, _ = first.adjudicate(encounter(), declare(encounter()))
    two, _ = second.adjudicate(encounter(), declare(encounter()))
    assert one.effects[0].amount == two.effects[0].amount


# --- R7: what may be said about it ------------------------------------------------------


def test_a_testless_outcome_may_not_be_narrated_as_a_success_or_a_failure(
    tmp_path: Path,
) -> None:
    """Nothing succeeded, because nothing was tested.

    R7's bounds are advisory to the caller, so no machinery catches a narrator who says the
    save was made. The bound existing is the whole of the engine's part.
    """
    adjudicator, _ = build(tmp_path)
    ruling, _ = adjudicator.adjudicate(encounter(), declare(encounter()))

    said = " ".join(ruling.bounds.may)
    assert "succeeded" not in said and "failed" not in said
    assert any("without a d20" in line for line in ruling.bounds.may_not)
    assert "that the fall hurt" in ruling.bounds.may, "the resolver's own claim survives"


# --- Replay: the verdict this must not get ----------------------------------------------


def test_a_testless_ruling_replays_as_no_roll_rather_than_unreplayable(
    tmp_path: Path,
) -> None:
    """The failure #170 was filed to prevent.

    `UNREPLAYABLE` means the record is too thin to reconstruct — a defect. A rule that never
    rolled is not thin, and reporting it that way would make every automatic outcome
    permanently unverifiable while reading like an ordinary limitation.
    """
    adjudicator, ledger_path = build(tmp_path)
    adjudicator.adjudicate(encounter(), declare(encounter()))

    (verdict,) = [
        r for r in replay(read_ledger(ledger_path), engine_version="test") if r.seq is not None
    ] or [None]  # type: ignore[list-item]
    assert verdict is not None
    assert verdict.verdict is ReplayVerdict.NO_ROLL
    assert "no roll to reproduce" in (verdict.detail or "")


def test_no_roll_is_neither_reproduced_nor_diverged(tmp_path: Path) -> None:
    """It must not count as an integrity finding in either direction: there was nothing to
    reproduce, so claiming it reproduced would be as false as claiming it drifted."""
    adjudicator, ledger_path = build(tmp_path)
    adjudicator.adjudicate(encounter(), declare(encounter()))

    for replayed in replay(read_ledger(ledger_path), engine_version="test"):
        if replayed.verdict is ReplayVerdict.NO_ROLL:
            assert not replayed.reproduced
            assert not replayed.is_integrity_failure
            break
    else:  # pragma: no cover - the ruling above guarantees one
        pytest.fail("no testless ruling was replayed")


def test_the_ledger_records_testlessness_rather_than_leaving_it_to_be_inferred(
    tmp_path: Path,
) -> None:
    """A thin record and a rule that never rolled look identical from `roll` being absent.

    Inferring from an absence is how the advantage gap got in: `REPLAYABLE_FROM = 2` exists
    because a ruling made with advantage replayed as though it had none, rolled one die
    where two were rolled, and reported a mismatch indistinguishable from real drift.
    """
    adjudicator, ledger_path = build(tmp_path)
    adjudicator.adjudicate(encounter(), declare(encounter()))

    (entry,) = [e for e in read_ledger(ledger_path).entries if e.type == "ruling"]
    assert entry.payload["testless"] is True
    assert entry.payload["roll"] is None
