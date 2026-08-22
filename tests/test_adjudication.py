"""The single door an outcome comes through, and everything it must carry on the way.

The Ruling has to answer "why did this come out this way" from the record alone. So these
tests are mostly about what the Ruling *says*, not only what it decides: the target number
and its derivation, every resolved fact with its provenance and whether it defaulted, the
alternatives verdict, the citations, and the bounds on what may be claimed.

The rules here are invented fixtures. No SRD value appears, and the loader that admits
them refuses SRD-provenance entries outright.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping
from pathlib import Path

import pytest

from srd_rules_engine.core.adjudicate import (
    Adjudicator,
    Declaration,
    Effect,
    EffectKind,
    Intent,
    Proposal,
    Ruling,
    Status,
)
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.ledger_reader import read_ledger
from srd_rules_engine.core.memory_port import (
    DefaultKind,
    Fact,
    FactType,
    Provenance,
    Resolution,
    ValueKind,
    Writer,
)
from srd_rules_engine.core.read_surface import END_TURN, Verdict, read
from srd_rules_engine.core.rules import Rule, RuleProvenance, load_fixture_ruleset
from srd_rules_engine.core.state import Combatant, EncounterState
from srd_rules_engine.core.triggers import (
    Catalogue,
    Condition,
    Grounding,
    Operator,
    Trigger,
)
from srd_rules_engine.memory.store import JsonMemoryStore

# --- Invented fixtures. Nothing here is an SRD value. ------------------------------

RESOLVE_ = FactType(
    name="resolve",
    kind=ValueKind.CHOICE,
    choices=("steady", "wavering", "broken"),
    default_kind=DefaultKind.SRD_PRESCRIBED,
    default="steady",
)
OMEN = FactType(name="omen", kind=ValueKind.BOOLEAN)  # no default: blocks
PORTENT = FactType(name="portent", kind=ValueKind.BOOLEAN)  # no default: blocks

FACT_TYPES = {t.name: t for t in (RESOLVE_, OMEN, PORTENT)}

STEEL_YOURSELF = Rule(
    id="steel-yourself",
    summary="An invented check whose difficulty moves with the actor's resolve.",
    provenance=RuleProvenance.FIXTURE,
    consumes=("resolve",),
    rationale="Exercises fact resolution, defaulting, and a fact that moves the target.",
)
READ_THE_OMENS = Rule(
    id="read-the-omens",
    summary="An invented check consuming two facts that have no honest default.",
    provenance=RuleProvenance.FIXTURE,
    consumes=("omen", "portent"),
    rationale="Exercises the blocked path with more than one unresolved fact.",
)
PLAIN = Rule(
    id="plain-effort",
    summary="An invented check that consumes nothing.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Exercises the happy path with no fact resolution involved.",
)

RESOLVE_TARGETS = {"steady": 10, "wavering": 14, "broken": 18}


def steel_yourself(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    resolve_value = str(facts["resolve"].value)
    target = RESOLVE_TARGETS[resolve_value]
    actor = state.combatant(declaration.actor_id)
    return Proposal(
        test=D20Test(
            kind=TestKind.CHECK,
            target=target,
            target_basis=f"invented difficulty {target} for resolve {resolve_value!r}",
            modifiers=(Modifier(source="ability:strength", value=actor.modifier("str")),),
        ),
        citations=("fixture:steel-yourself",),
        may_claim=("that the character steadied themselves",),
        may_not_claim=("that anyone nearby noticed",),
    )


#: Counts calls, so "a block never reaches its resolver" can be asserted rather than
#: implied by a resolver that refuses to run.
OMEN_CALLS: list[Declaration] = []


def read_the_omens(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    OMEN_CALLS.append(declaration)
    reading = "favourable" if facts["omen"].value else "grim"
    return Proposal(
        test=D20Test(
            kind=TestKind.CHECK,
            target=11,
            target_basis=f"invented difficulty 11 for a {reading} reading",
        ),
        citations=("fixture:read-the-omens",),
    )


def plain_effort(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    return Proposal(
        test=D20Test(kind=TestKind.CHECK, target=12, target_basis="invented flat difficulty 12"),
        citations=("fixture:plain-effort",),
        on_success=(
            Effect(
                kind=EffectKind.DAMAGE,
                target_id="boar",
                amount=3,
                description="the boar is winded",
            ),
        ),
        on_failure=(
            Effect(
                kind=EffectKind.DAMAGE, target_id="pc", amount=2, description="the effort costs"
            ),
        ),
    )


RESOLVERS = {
    "steel-yourself": steel_yourself,
    "read-the-omens": read_the_omens,
    "plain-effort": plain_effort,
}
RULESET = load_fixture_ruleset("adjudication", [STEEL_YOURSELF, READ_THE_OMENS, PLAIN])

#: One invented row, so the challenged status can be produced here too.
CATALOGUE = Catalogue(
    version=3,
    triggers=(
        Trigger(
            id="fixture-never-skip-in-combat",
            grounding=Grounding.AUTHORED,
            when=(Condition(field="in_combat", operator=Operator.EQUALS, value=True),),
            message="an invented row, so a skip mid-combat collides with something",
            rationale="Exercises the challenged path from the adjudication side.",
        ),
    ),
)


def combatant(cid: str, hp: int = 20) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=hp,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 16},
        proficiency_bonus=2,
    )


def encounter() -> EncounterState:
    state = EncounterState.new([combatant("pc"), combatant("boar", hp=11)])
    return state.with_initiative({"pc": 18, "boar": 4})


def build(tmp_path: Path, *, seeds: tuple[int, ...] = (12345,)) -> tuple[Adjudicator, Path, Path]:
    store_path, ledger_path = tmp_path / "memory.json", tmp_path / "ledger.jsonl"
    ledger = Ledger.open(ledger_path, engine_version="test", catalogue_version=1, session_id="s-1")
    supply = itertools.cycle(seeds)
    return (
        Adjudicator(
            ruleset=RULESET,
            resolvers=RESOLVERS,
            fact_types=FACT_TYPES,
            port=JsonMemoryStore(store_path),
            ledger=ledger,
            catalogue=CATALOGUE,
            seed_source=lambda: next(supply),
        ),
        store_path,
        ledger_path,
    )


def declare(state: EncounterState, **overrides: object) -> Declaration:
    offered = read(state, "pc")
    fields: dict[str, object] = {
        "actor_id": "pc",
        "intent": Intent(action_key=END_TURN),
        "rule_id": "plain-effort",
        "alternatives": offered.actions,
        "read_token": offered.token,
    }
    fields.update(overrides)
    return Declaration(**fields)  # type: ignore[arg-type]


# --- R2: a declaration names a test or claims none, never both and never neither ----


def test_a_declaration_names_a_test_or_claims_none() -> None:
    with pytest.raises(ValueError, match="Exactly one"):
        Declaration(actor_id="pc", intent=Intent(action_key=END_TURN))
    with pytest.raises(ValueError, match="Exactly one"):
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=END_TURN),
            rule_id="plain-effort",
            no_test_reason="and also no test",
        )


def test_an_intent_is_enumerated_or_improvised_but_not_both() -> None:
    with pytest.raises(ValueError, match="no enumerated action key"):
        Intent(action_key=END_TURN, improvised=True)
    with pytest.raises(ValueError, match="enumerated or marked improvised"):
        Intent()


# --- The happy path, and what the Ruling must show ---------------------------------


def test_a_legal_declaration_produces_a_ruling(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    ruling, _ = adjudicator.adjudicate(encounter(), declare(encounter()))
    assert ruling.status is Status.RULED
    assert ruling.result is not None


def test_the_recorded_derivation_reconstructs_the_target_number(tmp_path: Path) -> None:
    """R5: a reader must be able to check the arithmetic, not take the outcome on trust."""
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, rule_id="steel-yourself"))

    assert ruling.result is not None
    line = ruling.result.derivation()
    assert str(ruling.result.used) in line
    assert "+3 (ability:strength)" in line, "strength 16 gives +3"
    assert f"= {ruling.result.total}" in line
    assert str(ruling.result.target) in line
    assert ruling.result.total == ruling.result.used + 3


def test_the_ruling_carries_its_citations(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    ruling, _ = adjudicator.adjudicate(encounter(), declare(encounter()))
    assert ruling.citations == ("fixture:plain-effort",)


def test_effects_are_applied_and_recorded(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path, seeds=(3,))
    state = encounter()
    ruling, next_state = adjudicator.adjudicate(state, declare(state))

    assert ruling.effects
    effect = ruling.effects[0]
    before = state.combatant(effect.target_id).hit_points
    assert next_state.combatant(effect.target_id).hit_points == before - effect.amount


def test_the_success_branch_fires_on_a_success_and_the_failure_branch_on_a_failure(
    tmp_path: Path,
) -> None:
    """Which branch fires is the whole point of having two.

    Asserting only that *some* damage landed would pass with the branches swapped, and a
    swapped branch means a failed roll harms the wrong party — a rules defect that reads
    as a perfectly ordinary Ruling in the ledger.
    """
    winning, _, _ = build(tmp_path / "won", seeds=(2,))
    state = encounter()
    ruling, after = winning.adjudicate(state, declare(state))

    assert ruling.result is not None and ruling.result.succeeded
    assert [e.target_id for e in ruling.effects] == ["boar"]
    assert after.combatant("boar").hit_points == state.combatant("boar").hit_points - 3
    assert after.combatant("pc").hit_points == state.combatant("pc").hit_points

    losing, _, _ = build(tmp_path / "lost", seeds=(0,))
    ruling, after = losing.adjudicate(state, declare(state))

    assert ruling.result is not None and not ruling.result.succeeded
    assert [e.target_id for e in ruling.effects] == ["pc"]
    assert after.combatant("pc").hit_points == state.combatant("pc").hit_points - 2
    assert after.combatant("boar").hit_points == state.combatant("boar").hit_points


def test_applying_an_effect_advances_the_generation(tmp_path: Path) -> None:
    """So a read token issued before the ruling reads as stale afterwards."""
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    _, next_state = adjudicator.adjudicate(state, declare(state))
    assert next_state.generation > state.generation


# --- R3: validation, against the same derivation the read surface uses -------------


def test_an_action_the_read_surface_does_not_offer_is_rejected(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, unchanged = adjudicator.adjudicate(
        state, declare(state, intent=Intent(action_key="fly"))
    )
    assert ruling.status is Status.REJECTED
    assert "not legal" in (ruling.reason or "")
    assert ruling.result is None, "no outcome is produced"
    assert unchanged is state


def test_a_combatant_whose_turn_it_is_not_is_offered_nothing_and_rejected(
    tmp_path: Path,
) -> None:
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, actor_id="boar"))
    assert ruling.status is Status.REJECTED


def test_an_unknown_actor_is_rejected(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, actor_id="ghost"))
    assert ruling.status is Status.REJECTED
    assert "ghost" in (ruling.reason or "")


def test_a_rule_not_in_the_ruleset_is_rejected(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, rule_id="wish"))
    assert ruling.status is Status.REJECTED
    assert "no rule 'wish'" in (ruling.reason or "")


def test_a_rejection_states_what_was_offered(tmp_path: Path) -> None:
    """A refusal that does not say what would have been legal is hard to act on."""
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, intent=Intent(action_key="fly")))
    assert END_TURN in (ruling.reason or "")


def test_an_adjudicator_refuses_a_ruleset_with_no_resolver(tmp_path: Path) -> None:
    ledger = Ledger.open(
        tmp_path / "l.jsonl", engine_version="t", catalogue_version=1, session_id="s"
    )
    with pytest.raises(ValueError, match="no resolver for"):
        Adjudicator(
            ruleset=RULESET,
            resolvers={"plain-effort": plain_effort},
            fact_types=FACT_TYPES,
            port=JsonMemoryStore(tmp_path / "m.json"),
            ledger=ledger,
        )


# --- R21, R22, R27: facts, defaults, and provenance --------------------------------


def test_an_absent_fact_defaults_and_the_ruling_says_which_kind(tmp_path: Path) -> None:
    """Covers AE3 — the value is disclosed as defaulted rather than presented as known."""
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, rule_id="steel-yourself"))

    resolved = ruling.facts[0]
    assert resolved.type_name == "resolve"
    assert resolved.value == "steady"
    assert resolved.defaulted is DefaultKind.SRD_PRESCRIBED
    assert resolved.provenance is None


def test_a_held_fact_moves_the_target_and_is_cited_with_its_provenance(
    tmp_path: Path,
) -> None:
    """Covers AE4, through an invented fixture fact — the mechanism, not the SRD's rule."""
    adjudicator, store_path, _ = build(tmp_path)
    JsonMemoryStore(store_path).put(
        Fact("resolve", "pc", "broken", Provenance(writer=Writer.RULING, reference="4"))
    )
    adjudicator, _, _ = build(tmp_path)  # reopen so the store is read fresh

    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, rule_id="steel-yourself"))

    assert ruling.result is not None
    assert ruling.result.target == RESOLVE_TARGETS["broken"], "the fact moved the target"
    assert "broken" in ruling.result.target_basis
    resolved = ruling.facts[0]
    assert resolved.defaulted is None
    assert resolved.provenance is not None
    assert resolved.provenance.reference == "4", "traceable to the ruling that produced it"


def test_two_unresolvable_facts_produce_one_blocked_status_naming_both(
    tmp_path: Path,
) -> None:
    """R22 names every unresolved fact, so a driver can supply them in one round."""
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, unchanged = adjudicator.adjudicate(state, declare(state, rule_id="read-the-omens"))

    assert ruling.status is Status.BLOCKED
    assert set(ruling.unresolved) == {"omen", "portent"}
    assert ruling.result is None
    assert unchanged is state, "a block changes nothing"


def test_a_blocked_adjudication_does_not_reach_its_resolver(tmp_path: Path) -> None:
    """Fact resolution comes first, so a resolver never sees a fact it cannot rely on."""
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    OMEN_CALLS.clear()

    ruling, _ = adjudicator.adjudicate(state, declare(state, rule_id="read-the-omens"))
    assert ruling.status is Status.BLOCKED
    assert OMEN_CALLS == [], "the resolver was reached despite an unresolved fact"


def test_supplying_the_blocked_facts_lets_the_same_declaration_proceed(
    tmp_path: Path,
) -> None:
    adjudicator, store_path, _ = build(tmp_path)
    state = encounter()
    declaration = declare(state, rule_id="read-the-omens")
    assert adjudicator.adjudicate(state, declaration)[0].status is Status.BLOCKED

    store = JsonMemoryStore(store_path)
    noted = Provenance(writer=Writer.OUT_OF_BAND, reference="notes")
    store.put(Fact("omen", "pc", True, noted))
    store.put(Fact("portent", "pc", False, noted))

    OMEN_CALLS.clear()
    adjudicator, _, _ = build(tmp_path)
    ruling, _ = adjudicator.adjudicate(state, declaration)

    assert ruling.status is Status.RULED, "the same declaration resumes once the facts exist"
    assert ruling.unresolved == ()
    assert len(OMEN_CALLS) == 1, "and now the resolver does run"
    assert {f.type_name for f in ruling.facts} == {"omen", "portent"}


# --- R7: narration bounds -----------------------------------------------------------


def test_the_bounds_withhold_a_claim_the_ruling_did_not_resolve(tmp_path: Path) -> None:
    """Covers AE2 — the unresolved consequence needs its own declaration."""
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, rule_id="steel-yourself"))

    assert any("its own declaration" in claim for claim in ruling.bounds.may_not)
    assert any("noticed" in claim for claim in ruling.bounds.may_not)
    assert any("steadied" in claim for claim in ruling.bounds.may)


def test_a_refusal_permits_no_claim_that_anything_happened(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, rule_id="wish"))
    assert ruling.bounds.may == ()
    assert any("no outcome was produced" in claim for claim in ruling.bounds.may_not)


# --- R10: the alternatives verdict --------------------------------------------------


def test_a_matching_claim_verifies_fresh(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state))
    assert ruling.alternatives_verdict is Verdict.FRESH


def test_a_claim_that_does_not_match_is_recorded_unverified_and_adjudication_proceeds(
    tmp_path: Path,
) -> None:
    """The alternatives are metadata about a decision, not the decision."""
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, alternatives=()))

    assert ruling.alternatives_verdict is Verdict.UNVERIFIED
    assert ruling.status is Status.RULED, "recorded and reported, never a refusal"


def test_a_declaration_with_no_token_is_unread(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, declare(state, read_token=None))
    assert ruling.alternatives_verdict is Verdict.UNREAD
    assert ruling.status is Status.RULED


# --- R4: the engine rolls, and the caller does not choose the seed ------------------


def test_the_seed_comes_from_the_engine_and_is_recorded(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path, seeds=(777,))
    ruling, _ = adjudicator.adjudicate(encounter(), declare(encounter()))
    assert ruling.result is not None
    assert ruling.result.seed == 777


def test_the_same_seed_reproduces_the_same_roll(tmp_path: Path) -> None:
    first, _, _ = build(tmp_path / "a", seeds=(99,))
    second, _, _ = build(tmp_path / "b", seeds=(99,))
    left, _ = first.adjudicate(encounter(), declare(encounter()))
    right, _ = second.adjudicate(encounter(), declare(encounter()))
    assert left.result is not None and right.result is not None
    assert left.result.dice == right.result.dice


def test_the_declaration_cannot_carry_a_seed() -> None:
    """R4: a caller who chooses the seed chooses the outcome by searching for one."""
    assert not hasattr(Declaration, "seed")
    assert "seed" not in Declaration.__dataclass_fields__


# --- R26: nothing escapes before its record is durable ------------------------------


def test_the_declaration_and_the_ruling_are_both_recorded(tmp_path: Path) -> None:
    adjudicator, _, ledger_path = build(tmp_path)
    adjudicator.adjudicate(encounter(), declare(encounter()))

    types = [e.type for e in read_ledger(ledger_path).entries]
    assert types == ["session", "declaration", "ruling"]


def test_a_rejection_is_recorded_as_a_rejection_not_a_ruling(tmp_path: Path) -> None:
    adjudicator, _, ledger_path = build(tmp_path)
    state = encounter()
    adjudicator.adjudicate(state, declare(state, rule_id="wish"))

    types = [e.type for e in read_ledger(ledger_path).entries]
    assert types == ["session", "declaration", "rejection"]


def test_the_recorded_ruling_carries_the_seed_dice_and_derivation(tmp_path: Path) -> None:
    """R28's replay inputs and R5's explanation are the same record."""
    adjudicator, _, ledger_path = build(tmp_path, seeds=(4242,))
    adjudicator.adjudicate(encounter(), declare(encounter()))

    ruling_entry = read_ledger(ledger_path).entries[-1]
    roll = ruling_entry.payload["roll"]
    assert isinstance(roll, dict)
    assert roll["seed"] == 4242
    assert roll["dice"] and roll["derivation"]
    assert roll["target_basis"]


def test_the_recorded_ruling_carries_the_facts_with_their_provenance(
    tmp_path: Path,
) -> None:
    adjudicator, _, ledger_path = build(tmp_path)
    state = encounter()
    adjudicator.adjudicate(state, declare(state, rule_id="steel-yourself"))

    facts = read_ledger(ledger_path).entries[-1].payload["facts"]
    assert isinstance(facts, list)
    assert facts[0]["type"] == "resolve"
    assert facts[0]["defaulted"] == "srd-prescribed"


def test_the_recorded_ruling_carries_the_bounds_and_the_verdict(tmp_path: Path) -> None:
    adjudicator, _, ledger_path = build(tmp_path)
    adjudicator.adjudicate(encounter(), declare(encounter()))

    payload = read_ledger(ledger_path).entries[-1].payload
    bounds = payload["bounds"]
    assert isinstance(bounds, dict)
    assert bounds["may_not"]
    assert payload["alternatives_verdict"] == "verified-fresh"


def test_an_adjudication_whose_record_cannot_be_written_raises(tmp_path: Path) -> None:
    """R26: infrastructure failure never wears a rules status."""
    from srd_rules_engine.core.ledger import LedgerUnavailable

    adjudicator, _, ledger_path = build(tmp_path)
    ledger_path.chmod(0o400)
    try:
        with pytest.raises(LedgerUnavailable):
            adjudicator.adjudicate(encounter(), declare(encounter()))
    finally:
        ledger_path.chmod(0o600)


def test_nothing_is_recorded_when_the_adjudication_raises_before_the_boundary_closes(
    tmp_path: Path,
) -> None:
    """An outcome that never escaped is not lost — the buffer is discarded, not committed."""
    adjudicator, _, ledger_path = build(tmp_path)
    state = encounter()

    broken = declare(state, rule_id="steel-yourself")

    def exploding(**_: object) -> Proposal:
        raise RuntimeError("resolver failed after the declaration was buffered")

    adjudicator._resolvers["steel-yourself"] = exploding
    with pytest.raises(RuntimeError):
        adjudicator.adjudicate(state, broken)

    assert [e.type for e in read_ledger(ledger_path).entries] == ["session"]


# --- The no-test path (the challenge itself arrives with the trigger catalogue) -----


def quiet_skip(reason: str) -> tuple[EncounterState, Declaration]:
    """A skip outside combat, so the fixture catalogue has nothing to collide with.

    The challenged path belongs to the trigger tests; these are about what an *accepted*
    skip records.
    """
    state = EncounterState.new([combatant("pc")])
    return state, Declaration(
        actor_id="pc",
        intent=Intent(improvised=True, label="something unremarkable"),
        no_test_reason=reason,
    )


def test_a_no_test_claim_is_accepted_and_recorded_distinctly(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    state, declaration = quiet_skip("the door was already open")
    ruling, unchanged = adjudicator.adjudicate(state, declaration)

    assert ruling.status is Status.NO_TEST
    assert ruling.result is None
    assert unchanged is state
    assert "already open" in ruling.why()


def test_a_no_test_claim_still_bounds_what_may_be_narrated(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    state, declaration = quiet_skip("nothing was at stake")
    ruling, _ = adjudicator.adjudicate(state, declaration)
    assert ruling.status is Status.NO_TEST
    assert any("a rule would have had to resolve" in claim for claim in ruling.bounds.may_not)


# --- The one-line account ------------------------------------------------------------


def test_why_reads_as_an_explanation_for_every_status(tmp_path: Path) -> None:
    adjudicator, _, _ = build(tmp_path)
    state = encounter()

    outcomes: list[Ruling] = [
        adjudicator.adjudicate(state, declare(state))[0],
        adjudicator.adjudicate(state, declare(state, rule_id="wish"))[0],
        adjudicator.adjudicate(state, declare(state, rule_id="read-the-omens"))[0],
        adjudicator.adjudicate(
            state, declare(state, rule_id=None, no_test_reason="nothing at stake")
        )[0],
    ]
    # The catalogue fires on a skip in combat, so NO_TEST needs a state that is not.
    outcomes.append(adjudicator.adjudicate(*quiet_skip("nothing at stake"))[0])
    assert {r.status for r in outcomes} == set(Status)
    for ruling in outcomes:
        assert ruling.why(), f"{ruling.status} has no account of itself"
