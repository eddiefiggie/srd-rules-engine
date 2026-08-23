"""Three loops, and only one of them is the agent's fault.

Refusals are the agent's — a challenge or a rejection, sharing one budget because they
interleave. A block is a *suspension*, so it resumes the same declaration and the budget
is not charged: charging it would spend an agent's retries on a driver's omission. And
narration is R29's gate, which refuses the next declaration rather than letting a turn
quietly advance past a Ruling nobody described.

Termination is what most of this file pins. A repeat proves the feedback is not being
used, so two structurally identical refusals end the slot at once — and identity is the
trigger id set or the rejection code and its subject, never message text, which is
templated and would make two identical refusals look different.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Combatant,
    Condition,
    D20Test,
    Declaration,
    EncounterState,
    Fact,
    FactType,
    Grounding,
    Intent,
    Ledger,
    Operator,
    Proposal,
    Provenance,
    Resolution,
    Rule,
    RuleProvenance,
    Status,
    TestKind,
    Trigger,
    ValueKind,
    Writer,
    load_fixture_ruleset,
    read,
    read_ledger,
)
from srd_rules_engine.core import Catalogue as Cat
from srd_rules_engine.core.read_surface import END_TURN
from srd_rules_engine.loop.drivers import DriverExhausted, ScriptedDriver, drive
from srd_rules_engine.loop.turn import (
    BlockedFactRequest,
    DeclarationRequest,
    Declared,
    FactsSupplied,
    Narrated,
    NarrationOwed,
    NarrationRequest,
    Request,
    Response,
    TerminalReason,
    TurnLoop,
)
from srd_rules_engine.memory.store import JsonMemoryStore

# --- Invented fixtures ---------------------------------------------------------------

OMEN = FactType(name="omen", kind=ValueKind.BOOLEAN)
PORTENT = FactType(name="portent", kind=ValueKind.BOOLEAN)
FACT_TYPES = {t.name: t for t in (OMEN, PORTENT)}

PLAIN = Rule(
    id="plain-effort",
    summary="An invented check.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Gives a declaration something legal to name.",
)
NEEDY = Rule(
    id="needy",
    summary="An invented check consuming two facts with no honest default.",
    provenance=RuleProvenance.FIXTURE,
    consumes=("omen", "portent"),
    rationale="Exercises the blocked loop.",
)
RULESET = load_fixture_ruleset("loop", [PLAIN, NEEDY])

SKIPS_ARE_TESTED = Trigger(
    id="fixture-skips-are-tested",
    grounding=Grounding.AUTHORED,
    when=(Condition(field="in_combat", operator=Operator.EQUALS, value=True),),
    message="an invented row, so any skip in combat collides",
    rationale="Exercises the challenge loop.",
)
IMPROVISED_SKIPS = Trigger(
    id="fixture-improvised-skips",
    grounding=Grounding.AUTHORED,
    when=(
        Condition(field="in_combat", operator=Operator.EQUALS, value=True),
        Condition(field="improvised", operator=Operator.EQUALS, value=True),
    ),
    message="an invented row that only an improvised skip collides with",
    rationale="Gives two skips genuinely different signatures, for challenge churn.",
)
CATALOGUE = Cat(version=2, triggers=(SKIPS_ARE_TESTED, IMPROVISED_SKIPS))
NOTED = Provenance(writer=Writer.OUT_OF_BAND, reference="notes")


def _proposal(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    return Proposal(
        test=D20Test(kind=TestKind.CHECK, target=10, target_basis="invented flat difficulty 10")
    )


def combatant(cid: str) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 16},
        proficiency_bonus=2,
    )


def encounter() -> EncounterState:
    state = EncounterState.new([combatant("pc"), combatant("boar")])
    return state.with_initiative({"pc": 18, "boar": 4})


def loop_for(
    tmp_path: Path, *, budget: int | None = 3, catalogue: Cat = CATALOGUE
) -> tuple[TurnLoop, Path]:
    ledger_path = tmp_path / "ledger.jsonl"
    adjudicator = Adjudicator(
        ruleset=RULESET,
        resolvers={"plain-effort": _proposal, "needy": _proposal},
        fact_types=FACT_TYPES,
        port=JsonMemoryStore(tmp_path / "memory.json"),
        ledger=Ledger.open(
            ledger_path, engine_version="t", catalogue_version=catalogue.version, session_id="s"
        ),
        catalogue=catalogue,
        seed_source=lambda: 2,
    )
    return TurnLoop(adjudicator=adjudicator, budget=budget), ledger_path


def declaration(state: EncounterState, **overrides: object) -> Declaration:
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


def skip(state: EncounterState, reason: str = "nothing at stake") -> Declaration:
    return declaration(state, rule_id=None, no_test_reason=reason)


def illegal(state: EncounterState, key: str = "fly") -> Declaration:
    return declaration(state, intent=Intent(action_key=key))


# --- The happy path -------------------------------------------------------------------


def test_a_turn_produces_a_ruling_and_a_narration(tmp_path: Path) -> None:
    loop, _ = loop_for(tmp_path)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[declaration(state)], narrations=["The effort lands."]),
    )
    assert outcome.produced_outcome
    assert outcome.narration == "The effort lands."
    assert outcome.terminal is None
    assert not outcome.missing_narration


def test_a_challenge_answered_with_a_legal_test_never_touches_the_budget(
    tmp_path: Path,
) -> None:
    loop, _ = loop_for(tmp_path, budget=3)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(
            declarations=[skip(state), declaration(state)], narrations=["Resolved after all."]
        ),
    )
    assert outcome.produced_outcome
    assert outcome.terminal is None
    assert len(outcome.refusals) == 1, "the challenge is recorded, and the slot still resolves"


# --- Termination: no-progress first, then the budget ---------------------------------


def test_two_structurally_identical_refusals_terminate_at_once(tmp_path: Path) -> None:
    """Before the budget is spent — a repeat proves the feedback is not being used."""
    loop, _ = loop_for(tmp_path, budget=5)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[skip(state), skip(state), declaration(state)]),
    )
    assert outcome.terminal is TerminalReason.NO_PROGRESS
    assert len(outcome.refusals) == 2, "terminated on the repeat, not after five"


def test_refusals_with_different_text_but_the_same_signature_count_as_identical(
    tmp_path: Path,
) -> None:
    """Identity is the trigger id set — message text is templated and would look different."""
    loop, _ = loop_for(tmp_path, budget=5)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(
            declarations=[
                skip(state, "the floor looked dry"),
                skip(state, "and anyway I am careful"),
                declaration(state),
            ]
        ),
    )
    assert outcome.terminal is TerminalReason.NO_PROGRESS
    reasons = {r.declaration.no_test_reason for r in outcome.refusals}
    assert len(reasons) == 2, "the two refusals were worded differently"


def test_a_refusal_signature_is_structural_and_not_its_message(tmp_path: Path) -> None:
    """Identity is the code and its subject. Two refusals worded differently are one refusal.

    Comparing `reason` instead would be the obvious implementation and a quiet mistake:
    the text is templated on situational values, so it varies while the refusal does not.
    """
    loop, _ = loop_for(tmp_path, budget=5)
    state = encounter()
    first, _ = loop.adjudicator.adjudicate(state, illegal(state, "fly"))

    reworded = replace(first, reason="a completely different sentence about the same refusal")
    assert reworded.reason != first.reason
    assert reworded.signature == first.signature, "structure, not prose"

    other, _ = loop.adjudicator.adjudicate(state, illegal(state, "swim"))
    assert other.signature != first.signature, "a different subject is a different refusal"


def test_challenges_that_differ_exhaust_the_slot_as_challenge_churn(
    tmp_path: Path,
) -> None:
    """Named separately from rejection churn, because they mean different things."""
    loop, _ = loop_for(tmp_path, budget=2)
    state = encounter()
    improvised_skip = Declaration(
        actor_id="pc",
        intent=Intent(improvised=True, label="something vague"),
        no_test_reason="it hardly counts",
    )
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[skip(state), improvised_skip]),
    )
    assert outcome.terminal is TerminalReason.CHALLENGE_CHURN
    signatures = {r.signature for r in outcome.refusals}
    assert len(signatures) == 2, "the two challenges fired different rows"


def test_three_differing_refusals_exhaust_the_slot(tmp_path: Path) -> None:
    loop, _ = loop_for(tmp_path, budget=3)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(
            declarations=[
                illegal(state, "fly"),
                illegal(state, "teleport"),
                illegal(state, "vanish"),
                declaration(state),
            ]
        ),
    )
    assert outcome.terminal is TerminalReason.REJECTION_CHURN
    assert len(outcome.refusals) == 3


def test_the_churn_reason_names_what_actually_differed(tmp_path: Path) -> None:
    """Challenge, rejection, challenge is mixed churn — not one or the other."""
    loop, _ = loop_for(tmp_path, budget=3)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[skip(state, "a"), illegal(state, "fly"), skip(state, "b")]),
    )
    assert outcome.terminal is TerminalReason.MIXED_CHURN


def test_an_unbounded_budget_does_not_terminate_on_count(tmp_path: Path) -> None:
    loop, _ = loop_for(tmp_path, budget=None)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(
            declarations=[illegal(state, f"nonsense-{n}") for n in range(8)] + [declaration(state)],
            narrations=["done"],
        ),
    )
    assert outcome.terminal is None
    assert outcome.produced_outcome
    assert len(outcome.refusals) == 8


def test_an_unbounded_budget_still_terminates_on_no_progress(tmp_path: Path) -> None:
    """The only protection that remains when a driver opts out of the count."""
    loop, _ = loop_for(tmp_path, budget=None)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[illegal(state, "fly"), illegal(state, "fly")]),
    )
    assert outcome.terminal is TerminalReason.NO_PROGRESS


def test_a_terminal_outcome_carries_the_refusals_and_what_was_offered(
    tmp_path: Path,
) -> None:
    """0005: the terminal discloses what would have been accepted, without choosing."""
    loop, _ = loop_for(tmp_path, budget=2)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[illegal(state, "fly"), illegal(state, "swim")]),
    )
    assert outcome.terminal is TerminalReason.REJECTION_CHURN
    assert [a.key for a in outcome.offered] == [
        END_TURN,
        "attack:boar",
        "dash",
        "dodge",
        "disengage",
    ]
    assert all(r.status is Status.REJECTED for r in outcome.refusals)
    assert outcome.ruling is None, "the engine never breaks a loop by choosing a test"


# --- The blocked loop: a suspension, not a refusal -----------------------------------


def test_supplying_the_facts_resumes_the_same_declaration(tmp_path: Path) -> None:
    """The agent is not asked again — the declaration was accepted, not refused."""
    loop, _ = loop_for(tmp_path)
    state = encounter()
    declarations = [declaration(state, rule_id="needy")]

    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(
            declarations=declarations,
            narrations=["the omens were read"],
            facts=[[Fact("omen", "pc", True, NOTED), Fact("portent", "pc", False, NOTED)]],
        ),
    )
    assert outcome.produced_outcome
    assert outcome.refusals == (), "a block is not charged to the agent's budget"


def test_a_block_names_every_unresolved_fact_at_once(tmp_path: Path) -> None:
    loop, _ = loop_for(tmp_path)
    state = encounter()
    seen: list[tuple[str, ...]] = []

    def driver(request: Request) -> Response:
        if isinstance(request, DeclarationRequest):
            return Declared(declaration(state, rule_id="needy"))
        if isinstance(request, BlockedFactRequest):
            seen.append(request.unresolved)
            return FactsSupplied((Fact("omen", "pc", True, NOTED),))
        return Narrated("done")

    drive(loop.run(state, "pc"), driver)
    assert seen[0] == ("omen", "portent"), "both, so one round could have supplied both"


def test_a_round_that_shrinks_the_set_continues(tmp_path: Path) -> None:
    loop, _ = loop_for(tmp_path)
    state = encounter()
    supplied = [
        [Fact("omen", "pc", True, NOTED)],
        [Fact("portent", "pc", False, NOTED)],
    ]
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(
            declarations=[declaration(state, rule_id="needy")],
            narrations=["read at last"],
            facts=supplied,
        ),
    )
    assert outcome.produced_outcome, "one fact per round still progresses"


def test_a_round_that_does_not_shrink_the_set_ends_the_turn(tmp_path: Path) -> None:
    """No count bound is needed — the set can only shrink, so a repeat has nothing to wait for."""
    loop, _ = loop_for(tmp_path)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[declaration(state, rule_id="needy")], facts=[[], []]),
    )
    assert outcome.terminal is TerminalReason.FACT_UNAVAILABLE
    assert set(outcome.unresolved) == {"omen", "portent"}
    assert outcome.refusals == (), "still not the agent's failure"


# --- R29: the narration gate ---------------------------------------------------------


def test_a_second_declaration_is_refused_while_a_narration_is_owed(tmp_path: Path) -> None:
    loop, _ = loop_for(tmp_path)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[declaration(state)], narrations=[None]),
    )
    assert outcome.missing_narration
    assert loop.owes_narration("pc")

    with pytest.raises(NarrationOwed, match="R29"):
        drive(loop.run(outcome.state, "pc"), ScriptedDriver(declarations=[declaration(state)]))


def test_a_submitted_narration_clears_the_gate(tmp_path: Path) -> None:
    loop, _ = loop_for(tmp_path)
    state = encounter()
    first = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[declaration(state)], narrations=["described"]),
    )
    assert not loop.owes_narration("pc")

    second = drive(
        loop.run(first.state, "pc"),
        ScriptedDriver(declarations=[declaration(first.state)], narrations=["again"]),
    )
    assert second.produced_outcome


def test_a_turn_that_advances_without_a_narration_is_marked(tmp_path: Path) -> None:
    """A narration that never arrives is a named state, not a silent hole."""
    loop, _ = loop_for(tmp_path)
    state = encounter()
    outcome = drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[declaration(state)], narrations=[None]),
    )
    assert outcome.missing_narration
    assert outcome.narration is None
    assert outcome.produced_outcome, "the Ruling still happened"


def test_the_narration_is_appended_against_its_ruling(tmp_path: Path) -> None:
    loop, ledger_path = loop_for(tmp_path)
    state = encounter()
    drive(
        loop.run(state, "pc"),
        ScriptedDriver(declarations=[declaration(state)], narrations=["the effort lands"]),
    )
    entries = read_ledger(ledger_path).entries
    assert [e.type for e in entries] == ["session", "declaration", "ruling", "narration"]
    assert entries[-1].payload["text"] == "the effort lands"
    assert entries[-1].payload["bounds"], "recorded against the bounds it was issued under"


# --- The seam ------------------------------------------------------------------------


def test_the_loop_yields_typed_requests_and_never_calls_the_driver(tmp_path: Path) -> None:
    """0001: control inversion, so one rules implementation serves any driver shape."""
    loop, _ = loop_for(tmp_path)
    state = encounter()
    generator = loop.run(state, "pc")

    first = next(generator)
    assert isinstance(first, DeclarationRequest)
    assert first.actor_id == "pc"
    assert [a.key for a in first.offered.actions] == [
        END_TURN,
        "attack:boar",
        "dash",
        "dodge",
        "disengage",
    ]

    second = generator.send(Declared(declaration(state)))
    assert isinstance(second, NarrationRequest)
    assert second.ruling.status is Status.RULED


def test_a_driver_that_answers_the_wrong_request_is_a_named_error(tmp_path: Path) -> None:
    loop, _ = loop_for(tmp_path)
    state = encounter()
    generator = loop.run(state, "pc")
    next(generator)
    with pytest.raises(TypeError, match="asked for Declared"):
        generator.send(Narrated("not a declaration"))


def test_the_declaration_request_carries_the_refusals_so_far(tmp_path: Path) -> None:
    """A driver not told why its last attempt failed will repeat it — and a repeat ends the slot."""
    loop, _ = loop_for(tmp_path, budget=5)
    state = encounter()
    seen: list[int] = []

    def driver(request: Request) -> Response:
        if isinstance(request, DeclarationRequest):
            seen.append(len(request.refusals))
            if len(request.refusals) < 2:
                return Declared(illegal(state, f"nonsense-{len(request.refusals)}"))
            return Declared(declaration(state))
        return Narrated("done")

    drive(loop.run(state, "pc"), driver)
    assert seen == [0, 1, 2]


def test_a_scripted_driver_that_runs_out_says_so(tmp_path: Path) -> None:
    loop, _ = loop_for(tmp_path)
    state = encounter()
    with pytest.raises(DriverExhausted, match="had none left"):
        drive(loop.run(state, "pc"), ScriptedDriver(declarations=[]))
