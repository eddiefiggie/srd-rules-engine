"""The session that holds a turn between calls, and the MCP tools over it (#97).

The property worth guarding here is not a rule — it is a **shape**. `AGENTS.md`: "The skip
guarantee holds only for callers the turn loop drives. A consumer calling adjudication
directly gets outcome authority without skip prevention."

So an adapter that exposed adjudication would ship the exact failure this engine exists to
remove, as a supported feature. Several tests below assert the *absence* of that path, which
is the kind of thing that reappears the moment somebody adds a convenience tool.
"""

from __future__ import annotations

import dataclasses
import inspect
import json
import tempfile
from pathlib import Path
from typing import get_args

import pytest

from fixtures.encounter import build_adjudicator, character, needs_nerve, opening_state
from fixtures.ruleset import LOOSE_SCREE
from srd_rules_engine.adapters import (
    AwaitingDeclaration,
    AwaitingFacts,
    AwaitingNarration,
    Finished,
    Session,
    SessionError,
    TurnEnded,
)
from srd_rules_engine.adapters import session as session_module
from srd_rules_engine.adapters import surface as surface_module
from srd_rules_engine.adapters.mcp import (
    BEGIN_TURN,
    DECLARE,
    END_TURN,
    FORBIDDEN_TOOL_NAMES,
    LOOK,
    NARRATE,
    SUPPLY_FACTS,
    TOOL_NAMES,
    Adapter,
    render,
    tool_definitions,
)
from srd_rules_engine.core import Declaration, EncounterState, Intent, Size
from srd_rules_engine.core.read_surface import Situation, read
from srd_rules_engine.loop import TurnLoop

SEED = 20260823


def _session(tmp: Path) -> Session:
    adjudicator = build_adjudicator(tmp, seed=SEED)
    return Session(loop=TurnLoop(adjudicator=adjudicator), state=opening_state(seed=SEED))


def _adapter(tmp: Path) -> Adapter:
    return Adapter(session=_session(tmp), ledger=tmp / "ledger.jsonl")


def _declare_no_test(pending: AwaitingDeclaration) -> Declaration:
    return Declaration(
        actor_id=pending.actor_id,
        intent=Intent(improvised=True, label="I stride across, I am sure-footed"),
        no_test_reason="the character is athletic, so no test is needed",
        read_token=pending.offered.token,
        alternatives=pending.offered.actions,
    )


# --- The session holds one turn ------------------------------------------------------


def test_looking_does_not_start_a_turn(tmp_path: Path) -> None:
    """R19: a read mutates nothing and records nothing — including the fact that it happened.

    Separate from `begin` on purpose: an agent may want to look before committing, and
    looking must never be the thing that commits it.
    """
    session = _session(tmp_path)
    session.look("pc")
    assert session.pending is None


def test_a_turn_runs_to_its_first_question(tmp_path: Path) -> None:
    pending = _session(tmp_path).begin("pc")
    assert isinstance(pending, AwaitingDeclaration)
    assert pending.actor_id == "pc"
    assert pending.offered.token


def test_a_second_turn_is_refused_while_one_is_open(tmp_path: Path) -> None:
    """Two suspensions would mean the engine answering for the wrong one."""
    session = _session(tmp_path)
    session.begin("pc")
    with pytest.raises(SessionError, match="already open"):
        session.begin("pc")


def test_answering_the_wrong_question_is_refused(tmp_path: Path) -> None:
    """A coerced response is a declaration nobody made."""
    session = _session(tmp_path)
    session.begin("pc")
    with pytest.raises(SessionError, match="waiting for AwaitingDeclaration"):
        session.narrate("something happened")


def test_nothing_can_be_answered_before_a_phase_opens(tmp_path: Path) -> None:
    """ "Phase" rather than "turn" since #110: a session can hold a declaration slot or a
    turn end, and neither being open is the same refusal."""
    with pytest.raises(SessionError, match="no phase is open"):
        _session(tmp_path).narrate("x")


def test_a_ruling_leads_to_a_narration_request_then_finishes(tmp_path: Path) -> None:
    """The whole loop, through the adapter: declare, be ruled on, pay R29's debt, finish."""
    session = _session(tmp_path)
    pending = session.begin("pc")
    assert isinstance(pending, AwaitingDeclaration)

    after = session.declare(_declare_no_test(pending))
    assert isinstance(after, AwaitingNarration), "a ruling exists and owes a narration"

    finished = session.narrate("the character picks their way across")
    assert isinstance(finished, Finished)
    assert session.pending is finished


# --- The challenge reaches the agent, with what caused it ----------------------------


def test_a_skip_that_collides_comes_back_challenged_through_the_adapter(tmp_path: Path) -> None:
    """The product's core claim, over the adapter rather than in the core.

    The situation is what the trigger catalogue matches against, so it has to reach the
    engine through `begin_turn` — omitting it does not make the turn safer, it makes the
    hazard invisible.
    """
    session = _session(tmp_path)
    pending = session.begin("pc", situation=dict(LOOSE_SCREE))
    assert isinstance(pending, AwaitingDeclaration)

    again = session.declare(_declare_no_test(pending))
    assert isinstance(again, AwaitingDeclaration), "challenged, so it is asked again"
    assert again.refusals, "and the refusal is carried, not just implied"
    assert str(again.refusals[0].status) == "challenged"


def test_the_rendered_refusal_carries_the_trigger_that_fired(tmp_path: Path) -> None:
    """A challenge whose substance is dropped is useless: an agent told only "challenged"
    has nothing to re-declare against.

    Each trigger carries its `grounding` too, because the catalogue is *grounded in* rather
    than *cited from* the SRD (decision 0004) — an agent should be able to tell an authored
    trigger from a cited one.
    """
    session = _session(tmp_path)
    pending = session.begin("pc", situation=dict(LOOSE_SCREE))
    assert isinstance(pending, AwaitingDeclaration)

    payload = render(session.declare(_declare_no_test(pending)))
    triggers = payload["refusals"][0]["triggers"]
    assert triggers, "the fired triggers are the substance of a challenge"
    assert triggers[0]["message"]
    assert triggers[0]["grounding"] == "authored"


# --- The tool surface ----------------------------------------------------------------


def test_supply_facts_answers_a_block_over_the_tool_call(tmp_path: Path) -> None:
    """The tool #144 found declared-and-raising. A blocked turn now has a route forward over
    MCP, and the values arrive typed by the declared `FactType` rather than by the caller."""
    adapter = _adapter(tmp_path)
    adapter.call(BEGIN_TURN, {"actor_id": "pc"})
    adapter.session.declare(needs_nerve(adapter.session.pending))  # type: ignore[arg-type]
    assert isinstance(adapter.session.pending, AwaitingFacts)

    payload = adapter.call(SUPPLY_FACTS, {"values": {"nerve": True}})

    assert payload
    stored = adapter.session.loop.adjudicator.port.get("nerve", "pc")
    assert stored is not None and stored.value is True


def test_the_supply_facts_schema_does_not_ask_for_a_subject(tmp_path: Path) -> None:
    """It did, in the draft that never ran. The subject is the blocked declaration's actor,
    and a caller naming it could write a fact about a creature the turn is not about."""
    schema = next(d["input_schema"] for d in tool_definitions() if d["name"] == SUPPLY_FACTS)
    assert set(schema["properties"]) == {"values", "reference"}
    assert schema["required"] == ["values"]


def test_every_read_surface_field_reaches_a_transport() -> None:
    """A field on `Situation` that no adapter renders is a field the agent cannot see.

    `situation_payload` is a hand-maintained list of names, which is the shape this project
    keeps getting caught by — #122's build-stamp guard covered one of the README's two
    stamps and went green while the other drifted. It had already happened here: 0020's
    `elapsed_minutes` and `minutes_until_recovery` were on the read surface and on no
    transport, so an agent driving through an adapter could not see elapsed campaign time,
    including the countdown a Stable creature recovers on. Found by writing this test, not
    by playing.

    R18 is the requirement it protects: the surface reports what is legal *for this creature
    now*, and a transport that drops half of it puts the agent back to recalling 5e.
    """
    state = opening_state(seed=SEED)
    payload = surface_module.situation_payload(read(state, "pc").situation)
    assert payload is not None
    missing = [f.name for f in dataclasses.fields(Situation) if f.name not in payload]
    assert not missing, (
        f"Situation fields no adapter renders: {missing}. Add them to situation_payload — "
        "an agent cannot decide from a field it is never sent."
    )


def test_the_situation_payload_survives_the_transport_it_is_built_for() -> None:
    """Present in the dict is not the same as sendable.

    The guard above checks that every field has a **name** in the payload and says nothing
    about its value, so a field rendered as the engine's own dataclass passes it and then
    fails in the adapter at the moment an agent asks for a situation. 0051's
    `carrying_capacity` is a `CarryingCapacity`, which is exactly that shape — the completeness
    guard went green on it while `json.dumps` would not have.

    HTTP and MCP both serialise this, so JSON is the transport rather than an arbitrary
    stand-in for one.

    **The creature is sized deliberately.** Written against `opening_state` alone this test
    was vacuous: nothing in that fixture states a size, so `carrying_capacity` is `None`, the
    dataclass never reaches the payload, and rendering it raw kept the assertion green. The
    corruption proof caught it — which is the whole reason that rule exists — so the sized
    creature is the case under test and the plain fixture is checked beside it.
    """
    json.dumps(surface_module.situation_payload(read(opening_state(seed=SEED), "pc").situation))

    sized = EncounterState.new(
        [dataclasses.replace(character(), size=Size.MEDIUM)]
    ).with_initiative({"pc": 10})
    situation = read(sized, "pc").situation
    assert situation is not None
    assert situation.carrying_capacity is not None, "otherwise this asserts nothing again"
    json.dumps(surface_module.situation_payload(situation))


def test_the_tools_are_exactly_what_is_declared() -> None:
    assert tuple(d["name"] for d in tool_definitions()) == TOOL_NAMES


def test_no_tool_reaches_an_outcome_without_the_loop() -> None:
    """The absence that is the design. `AGENTS.md`: a consumer calling adjudication directly
    gets outcome authority without skip prevention — so exposing it would ship the failure
    this engine removes, as a feature.
    """
    names = {d["name"] for d in tool_definitions()}
    assert not names & FORBIDDEN_TOOL_NAMES
    assert "adjudicate" not in names


def test_every_tool_declares_an_input_schema() -> None:
    for definition in tool_definitions():
        assert definition["description"].strip()
        assert definition["input_schema"]["type"] == "object"


def test_begin_turn_accepts_a_situation_so_hazards_can_fire() -> None:
    """Without it the trigger catalogue matches against nothing, and the challenge
    mechanism is silently unreachable over MCP."""
    begin = next(d for d in tool_definitions() if d["name"] == BEGIN_TURN)
    assert "situation" in begin["input_schema"]["properties"]
    assert "trigger catalogue" in begin["description"]


def test_declare_asks_for_the_read_token() -> None:
    """Decision 0007: the alternatives on a declaration are the agent's claim about what it
    was offered, and the token is what makes that claim checkable."""
    declare = next(d for d in tool_definitions() if d["name"] == DECLARE)
    assert "read_token" in declare["input_schema"]["properties"]


# --- The tool calls themselves -------------------------------------------------------


def test_look_reports_the_menu_and_the_situation(tmp_path: Path) -> None:
    payload = _adapter(tmp_path).call(LOOK, {"actor_id": "pc"})
    assert [o["key"] for o in payload["offered"]]
    assert payload["situation"]["movement_remaining"] >= 0
    assert "conditions" in payload["situation"]


def test_a_tool_call_drives_the_same_loop_as_the_session(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    opened = adapter.call(BEGIN_TURN, {"actor_id": "pc", "situation": dict(LOOSE_SCREE)})
    assert opened["awaiting"] == "declaration"

    challenged = adapter.call(
        DECLARE,
        {
            "actor_id": "pc",
            "improvised_label": "I stride across",
            "no_test_reason": "the character is athletic",
            "read_token": opened["read_token"],
        },
    )
    assert challenged["awaiting"] == "declaration"
    assert challenged["refusals"][0]["triggers"]


def test_an_unknown_tool_is_refused_rather_than_ignored(tmp_path: Path) -> None:
    with pytest.raises(KeyError, match="no such tool"):
        _adapter(tmp_path).call("adjudicate", {})


def test_narration_bounds_reach_the_agent(tmp_path: Path) -> None:
    """R7: bounds are advisory, and the caller cannot honour advice it never receives."""
    adapter = _adapter(tmp_path)
    adapter.call(BEGIN_TURN, {"actor_id": "pc"})
    ruled = adapter.call(
        DECLARE,
        {
            "actor_id": "pc",
            "improvised_label": "I stride across",
            "no_test_reason": "the character is athletic",
        },
    )
    assert ruled["awaiting"] == "narration"
    assert "may_claim" in ruled and "may_not_claim" in ruled

    finished = adapter.call(NARRATE, {"text": "they cross"})
    assert finished["awaiting"] is None


# --- The extra, not a dependency -----------------------------------------------------


def test_importing_the_adapter_does_not_require_the_mcp_sdk() -> None:
    """R33 keeps `[project].dependencies` empty. The SDK is imported inside `build_server`,
    so a checkout without the extra can still import, inspect and test everything above.
    """
    import ast

    source = Path("src/srd_rules_engine/adapters/mcp.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    module_level = {
        node.module for node in tree.body if isinstance(node, ast.ImportFrom) and node.module
    }
    assert not any(name and name.startswith("mcp") for name in module_level), (
        "the MCP SDK must not be imported at module scope, or the extra becomes a dependency"
    )


def test_the_mcp_extra_is_declared_and_the_core_has_none() -> None:
    import tomllib

    with open("pyproject.toml", "rb") as handle:
        config = tomllib.load(handle)

    assert config["project"]["dependencies"] == [], "R33: the core takes no dependency"
    assert any(spec.startswith("mcp") for spec in config["project"]["optional-dependencies"]["mcp"])


def test_a_session_survives_being_rebuilt_from_the_same_state(tmp_path: Path) -> None:
    """A lost session costs the position within a turn, not the record: the ledger is
    durable before anything escapes (decision 0002), and a new session starts a fresh turn
    from the recorded state.
    """
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        first = _session(tmp)
        first.begin("pc")
        # The process "dies" here: the suspension is gone, the ledger is not.
        assert (tmp / "ledger.jsonl").exists()

        second = Session(
            loop=TurnLoop(adjudicator=build_adjudicator(tmp, seed=SEED)), state=first.state
        )
        assert isinstance(second.begin("pc"), AwaitingDeclaration)


# --- The surface is complete, not merely correct -------------------------------------


def test_every_pending_state_is_reachable_through_a_tool() -> None:
    """The general form of #134, and the guard that would have caught it.

    `test_no_tool_reaches_an_outcome_without_the_loop` asserts what must **not** be on the
    surface. Nothing asserted the surface was **complete** — so when #110 added a phase to
    the loop and `TurnEnded` to `Pending`, the MCP adapter could ship with no way to reach
    it and every existing test stayed green.

    Stated over the union rather than as a list of names, because a list is what went stale:
    a seventh `Pending` member added tomorrow fails here until something can reach it.
    """
    reachable = {
        AwaitingDeclaration: BEGIN_TURN,
        AwaitingNarration: DECLARE,
        Finished: NARRATE,
        TurnEnded: END_TURN,
    }
    members = set(get_args(session_module.Pending))
    unreachable = sorted(m.__name__ for m in members - set(reachable) - {AwaitingFacts})
    assert not unreachable, (
        f"{unreachable} cannot be reached through any tool. A phase the loop can enter and "
        "the adapter cannot drive is a turn a consumer cannot finish"
    )
    for name in reachable.values():
        assert name in TOOL_NAMES


def test_render_handles_every_pending_state() -> None:
    """`render` closed with `assert isinstance(pending, Finished)` before #134, so a
    `TurnEnded` would have raised `AssertionError` — a crash at the transport layer for a
    state the loop produces legitimately. mypy did not catch it, because `assert isinstance`
    narrows without requiring exhaustiveness.

    `assert_never` is what makes the next addition a type error instead. This asserts the
    branch exists at all, since `assert_never` is checked statically and not at runtime.

    It reads `adapters.surface` since #133 moved the rendering there: MCP and HTTP hand an
    agent the same JSON, and two copies of it would be two things that drift.
    """
    source = Path(inspect.getfile(surface_module)).read_text(encoding="utf-8")
    for member in get_args(session_module.Pending):
        assert (
            f"isinstance(pending, {member.__name__})" in source or member is AwaitingDeclaration
        ), f"render() has no branch for {member.__name__}"
    assert "assert_never(pending)" in source, (
        "render() must close on assert_never, so a new Pending member is a type error "
        "rather than an AssertionError in somebody's session"
    )


def test_the_end_turn_tool_drives_the_phase(tmp_path: Path) -> None:
    """End to end over the adapter: a turn ends, and the JSON says so."""
    adapter = _adapter(tmp_path)
    opened = adapter.call(BEGIN_TURN, {"actor_id": "pc"})
    adapter.call(
        DECLARE,
        {
            "actor_id": "pc",
            "improvised_label": "I stride across, I am sure-footed",
            "no_test_reason": "the character is athletic, so no test is needed",
            "read_token": opened["read_token"],
        },
    )
    finished = adapter.call(NARRATE, {"text": "the character picks their way across"})
    assert finished["next"] == END_TURN, "the slot is done; the turn is not"

    payload = adapter.call(END_TURN, {"actor_id": "pc"})
    assert payload["awaiting"] is None
    assert payload["next"] is None
    assert payload["obligations_resolved"] == 0, "this fixture holds no save-ends condition"
    assert payload["unresolvable"] == []


def test_a_finished_declaration_slot_says_the_turn_is_not_over(tmp_path: Path) -> None:
    """0023 clause 1 split the two, and an agent that reads `Finished` as "turn over" stops
    one phase early — which is exactly the skip `advanced_turn` now refuses to let pass."""
    session = _session(tmp_path)
    pending = session.begin("pc")
    assert isinstance(pending, AwaitingDeclaration)
    session.declare(_declare_no_test(pending))
    finished = session.narrate("the character picks their way across")

    assert isinstance(finished, Finished)
    assert render(finished)["next"] == END_TURN
