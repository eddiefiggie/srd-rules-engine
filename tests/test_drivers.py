"""Two reference drivers, and the point of both is that neither is an LLM.

R8 ships bindings so v1 is playable with no model and no network. A reference binding that
needed a model would make every test a model call and would quietly couple the engine to
one, which is a declared non-goal.

The human driver takes its input and output as callables. That is not only for tests: an
adapter embedding the loop elsewhere needs the same seam, and a driver that reaches for
the process's streams cannot be embedded twice.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Catalogue,
    Combatant,
    Condition,
    D20Test,
    Declaration,
    EncounterState,
    Fact,
    FactType,
    Grounding,
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
)
from srd_rules_engine.loop.drivers import HumanCliDriver, ScriptedDriver, drive
from srd_rules_engine.loop.turn import (
    BlockedFactRequest,
    Narrated,
    NarrationRequest,
    TerminalReason,
    TurnLoop,
)
from srd_rules_engine.memory.store import JsonMemoryStore

OMEN = FactType(name="omen", kind=ValueKind.BOOLEAN)
PLAIN = Rule(
    id="plain-effort",
    summary="An invented check.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Something legal to name at a prompt.",
)
NEEDY = Rule(
    id="needy",
    summary="An invented check consuming a fact with no honest default.",
    provenance=RuleProvenance.FIXTURE,
    consumes=("omen",),
    rationale="Drives the blocked prompt.",
)
RULESET = load_fixture_ruleset("drivers", [PLAIN, NEEDY])
NOTED = Provenance(writer=Writer.OUT_OF_BAND, reference="notes")

SKIPS = Trigger(
    id="fixture-skips-collide",
    grounding=Grounding.AUTHORED,
    when=(Condition(field="in_combat", operator=Operator.EQUALS, value=True),),
    message="an invented row, so a skip has something to collide with",
    rationale="Drives the refusal prompt.",
)


def _proposal(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    return Proposal(
        test=D20Test(kind=TestKind.CHECK, target=10, target_basis="invented flat difficulty 10"),
        may_claim=("that the effort was made",),
    )


def encounter() -> EncounterState:
    who = [
        Combatant(
            id=cid,
            name=cid.title(),
            hit_points=20,
            max_hit_points=20,
            armour_class=13,
            abilities={"str": 16},
            proficiency_bonus=2,
        )
        for cid in ("pc", "boar")
    ]
    return EncounterState.new(who).with_initiative({"pc": 18, "boar": 4})


def loop_for(tmp_path: Path, *, budget: int | None = 3) -> TurnLoop:
    catalogue = Catalogue(version=1, triggers=(SKIPS,))
    return TurnLoop(
        adjudicator=Adjudicator(
            ruleset=RULESET,
            resolvers={"plain-effort": _proposal, "needy": _proposal},
            fact_types={"omen": OMEN},
            port=JsonMemoryStore(tmp_path / "memory.json"),
            ledger=Ledger.open(
                tmp_path / "ledger.jsonl",
                engine_version="t",
                catalogue_version=1,
                session_id="s",
            ),
            catalogue=catalogue,
            seed_source=lambda: 2,
        ),
        budget=budget,
    )


class Terminal:
    """A scripted terminal: answers come from a list, output is captured."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.shown: list[str] = []

    def ask(self, prompt: str) -> str:
        self.shown.append(prompt)
        return self.answers.pop(0) if self.answers else ""

    def show(self, line: str) -> None:
        self.shown.append(line)


# --- The human driver ----------------------------------------------------------------


def test_a_person_can_run_a_whole_turn_at_a_terminal(tmp_path: Path) -> None:
    """No model, no network — the slice is playable by hand."""
    terminal = Terminal(["end-turn", "plain-effort", "The effort lands."])
    outcome = drive(
        loop_for(tmp_path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    assert outcome.produced_outcome
    assert outcome.narration == "The effort lands."


def test_the_prompt_states_what_is_legal(tmp_path: Path) -> None:
    terminal = Terminal(["end-turn", "plain-effort", "done"])
    drive(
        loop_for(tmp_path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    assert any("Legal for pc: end-turn" in line for line in terminal.shown)


def test_the_prompt_states_why_the_last_declaration_was_refused(tmp_path: Path) -> None:
    """A driver not told why it was refused will repeat, and a repeat ends the slot."""
    terminal = Terminal(["end-turn", "", "nothing at stake", "end-turn", "plain-effort", "done"])
    outcome = drive(
        loop_for(tmp_path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    assert outcome.produced_outcome
    assert any("Refused: challenged" in line for line in terminal.shown)


def test_the_narration_prompt_shows_the_bounds(tmp_path: Path) -> None:
    """R7 is advisory, so the person must be told what they may and may not claim."""
    terminal = Terminal(["end-turn", "plain-effort", "done"])
    drive(
        loop_for(tmp_path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    claims = next(line for line in terminal.shown if line.startswith("You may claim:"))
    assert "that the ability-check" in claims, "the outcome leads"
    assert "that the effort was made" in claims, "and the resolver's own claim follows"
    assert any(
        "its own declaration" in line
        for line in terminal.shown
        if line.startswith("You may not claim:")
    ), "the standing limit is shown, not only the resolver's additions"


def test_a_blank_narration_declines_rather_than_narrating_nothing(tmp_path: Path) -> None:
    terminal = Terminal(["end-turn", "plain-effort", "   "])
    outcome = drive(
        loop_for(tmp_path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    assert outcome.missing_narration
    assert outcome.narration is None


def test_a_blank_action_key_declares_an_improvised_intent(tmp_path: Path) -> None:
    terminal = Terminal(["", "", "it seemed safe", "I edge along the ledge"])
    outcome = drive(
        loop_for(tmp_path, budget=1).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    refused = outcome.refusals[0]
    assert refused.declaration.intent.improvised
    assert refused.declaration.intent.label == "I edge along the ledge"


def test_the_blocked_prompt_names_the_unresolved_facts(tmp_path: Path) -> None:
    terminal = Terminal(["end-turn", "needy", "read at last"])
    outcome = drive(
        loop_for(tmp_path).run(encounter(), "pc"),
        HumanCliDriver(
            ask=terminal.ask,
            show=terminal.show,
            facts_for=lambda _: (Fact("omen", "pc", True, NOTED),),
        ),
    )
    assert any("Blocked on: omen" in line for line in terminal.shown)
    assert outcome.produced_outcome


def test_a_human_driver_that_supplies_nothing_ends_the_turn(tmp_path: Path) -> None:
    terminal = Terminal(["end-turn", "needy"])
    outcome = drive(
        loop_for(tmp_path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    assert outcome.terminal is TerminalReason.FACT_UNAVAILABLE


# --- The scripted driver --------------------------------------------------------------


def test_the_scripted_driver_needs_no_model_and_no_network(tmp_path: Path) -> None:
    """Asserted by construction: the driver holds only data it was handed."""
    driver = ScriptedDriver(declarations=[], narrations=["x"])
    assert not hasattr(driver, "client")
    assert not hasattr(driver, "model")


def test_the_scripted_driver_can_decline_to_narrate(tmp_path: Path) -> None:
    state = encounter()
    from srd_rules_engine.core import Intent
    from srd_rules_engine.core.read_surface import END_TURN, read

    offered = read(state, "pc")
    outcome = drive(
        loop_for(tmp_path).run(state, "pc"),
        ScriptedDriver(
            declarations=[
                Declaration(
                    actor_id="pc",
                    intent=Intent(action_key=END_TURN),
                    rule_id="plain-effort",
                    alternatives=offered.actions,
                    read_token=offered.token,
                )
            ],
            narrations=[None],
        ),
    )
    assert outcome.ruling is not None and outcome.ruling.status is Status.RULED
    assert outcome.missing_narration


def test_drive_returns_what_the_loop_returned(tmp_path: Path) -> None:
    """The pump adds nothing — it only carries answers back."""
    terminal = Terminal(["end-turn", "plain-effort", "done"])
    outcome = drive(
        loop_for(tmp_path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    assert outcome.ruling is not None
    assert outcome.state.generation >= 0


def test_a_driver_sees_only_requests_never_the_ledger_or_the_dice() -> None:
    """A driver that could reach the dice would be a caller supplying a roll."""
    request_fields = set(NarrationRequest.__dataclass_fields__) | set(
        BlockedFactRequest.__dataclass_fields__
    )
    assert not any(name in request_fields for name in ("ledger", "seed", "dice", "adjudicator"))


def test_a_narration_response_carries_only_text() -> None:
    assert set(Narrated.__dataclass_fields__) == {"text"}


def test_the_human_driver_does_not_touch_the_process_streams() -> None:
    """Injected callables, so the same driver embeds in an adapter without rewiring."""
    fields = HumanCliDriver.__dataclass_fields__
    assert {"ask", "show", "facts_for"} <= set(fields)
    with pytest.raises(TypeError):
        HumanCliDriver()  # type: ignore[call-arg]
