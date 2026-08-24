"""The HTTP adapter over the turn loop (R34, #133).

The third and last transport R34 names. What is asserted here is mostly the same **shape**
the other two are held to — no route reaches an outcome, no route waives an obligation, every
`Pending` state is reachable — because those are the properties that make "the adapters are
built over the same contract" true rather than aspirational.

Two things are specific to this transport and worth stating as rules rather than conventions:

* **Reads are GET.** R19 says read-surface calls are idempotent, mutate nothing, and append
  nothing. The method is checkable evidence of the same property, and a `look` that had to
  become POST would be a sign the read surface had stopped being one.
* **One server holds one session.** Not a design decision this adapter made: `AGENTS.md`
  declines multiplayer and shared sessions as a non-goal, and a registry keyed by a
  caller-supplied identifier would build that surface in the one layer nobody inspects for
  it.

`serve()` is deliberately untested here. It is the socket half — a thin binding over
`handle`, which is where every route actually lives — and a test that opened a port would be
testing `http.server` rather than this engine.
"""

from __future__ import annotations

import ast
import inspect
from http import HTTPStatus
from pathlib import Path
from typing import Any

import pytest

from fixtures.encounter import build_adjudicator, opening_state
from fixtures.ruleset import LOOSE_SCREE
from srd_rules_engine.adapters import cli as cli_module
from srd_rules_engine.adapters import http as http_module
from srd_rules_engine.adapters import mcp as mcp_module
from srd_rules_engine.adapters.cli import COMMAND_NAMES
from srd_rules_engine.adapters.http import (
    BEGIN,
    DECLARE,
    END_TURN,
    FACTS,
    LOOK,
    NARRATE,
    READ_ROUTES,
    REPORT,
    ROUTES,
    WRITE_ROUTES,
    HttpAdapter,
)
from srd_rules_engine.adapters.session import Session
from srd_rules_engine.adapters.surface import FORBIDDEN_COMMAND_NAMES, pending_members
from srd_rules_engine.loop import TurnLoop

SEED = 20260823


def _adapter(tmp: Path) -> HttpAdapter:
    adjudicator = build_adjudicator(tmp, seed=SEED)
    session = Session(loop=TurnLoop(adjudicator=adjudicator), state=opening_state(seed=SEED))
    return HttpAdapter(session=session, ledger=tmp / "ledger.jsonl")


def _no_test_body() -> dict[str, Any]:
    return {
        "improvised_label": "I stride across, I am sure-footed",
        "no_test_reason": "the character is athletic, so no test is needed",
    }


def _code_of(module: Any) -> str:
    """Source with docstrings stripped, so prose about a rule cannot be mistaken for the
    rule being broken — the trap the CLI adapter's waiver test fell into first."""
    tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef) and ast.get_docstring(
            node
        ):
            node.body = node.body[1:]
    return ast.unparse(tree)


# --- The absences, now asserted over all three adapters --------------------------------


@pytest.mark.parametrize(
    "surface",
    [
        pytest.param(tuple(r.lstrip("/") for r in ROUTES), id="http"),
        pytest.param(COMMAND_NAMES, id="cli"),
        pytest.param(mcp_module.TOOL_NAMES, id="mcp"),
    ],
)
def test_no_adapter_reaches_an_outcome_without_the_loop(surface: tuple[str, ...]) -> None:
    """R34's three, held to one rule. `AGENTS.md`: a consumer calling adjudication directly
    gets outcome authority without skip prevention."""
    assert not set(surface) & FORBIDDEN_COMMAND_NAMES
    assert "adjudicate" not in surface


@pytest.mark.parametrize(
    "module",
    [
        pytest.param(http_module, id="http"),
        pytest.param(cli_module, id="cli"),
        pytest.param(mcp_module, id="mcp"),
    ],
)
def test_no_adapter_waives_an_end_of_turn_obligation(module: Any) -> None:
    """`advanced_turn`'s waiver is for a consumer that legitimately wants to fast-forward.
    An agent is not that consumer, and no transport should be the one that disagrees."""
    code = _code_of(module)
    assert "waive_obligations" not in code
    assert "advanced_turn" not in code, "advancing a turn is the caller's job, not an adapter's"


# --- R19 is visible in the method ---------------------------------------------------------


def test_reads_are_get_and_everything_else_is_post() -> None:
    assert set(READ_ROUTES) | set(WRITE_ROUTES) == set(ROUTES)
    assert not set(READ_ROUTES) & set(WRITE_ROUTES)
    assert set(READ_ROUTES) == {LOOK, REPORT}, "R19: these are the calls that mutate nothing"


def test_a_read_route_refuses_post(tmp_path: Path) -> None:
    """The method is evidence, so accepting either would throw the evidence away."""
    response = _adapter(tmp_path).handle("POST", LOOK, {"actor_id": "pc"})
    assert response.status == HTTPStatus.METHOD_NOT_ALLOWED
    assert "GET" in response.body["error"]


def test_a_write_route_refuses_get(tmp_path: Path) -> None:
    response = _adapter(tmp_path).handle("GET", BEGIN, {"actor_id": "pc"})
    assert response.status == HTTPStatus.METHOD_NOT_ALLOWED


def test_looking_does_not_start_a_turn(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    assert adapter.handle("GET", LOOK, {"actor_id": "pc"}).ok
    assert adapter.session.pending is None


# --- Driving a turn -------------------------------------------------------------------------


def test_a_turn_runs_from_begin_to_the_turns_end(tmp_path: Path) -> None:
    """The whole loop over HTTP, including 0023's ordering: the declaration slot finishing is
    not the turn ending, and the payload says which comes next."""
    adapter = _adapter(tmp_path)

    opened = adapter.handle("POST", BEGIN, {"actor_id": "pc"})
    assert opened.body["awaiting"] == "declaration"

    ruled = adapter.handle("POST", DECLARE, _no_test_body())
    assert ruled.body["awaiting"] == "narration"

    finished = adapter.handle("POST", NARRATE, {"text": "the character picks their way across"})
    assert finished.body["awaiting"] is None
    assert finished.body["next"] == END_TURN, "an agent stopping here stops one phase early"

    ended = adapter.handle("POST", END_TURN, {"actor_id": "pc"})
    assert ended.body["obligations_resolved"] == 0
    assert ended.body["next"] is None


def test_a_skip_that_collides_comes_back_challenged(tmp_path: Path) -> None:
    """The product's core claim, over the third transport."""
    adapter = _adapter(tmp_path)
    adapter.handle("POST", BEGIN, {"actor_id": "pc", "situation": dict(LOOSE_SCREE)})

    again = adapter.handle("POST", DECLARE, _no_test_body())
    assert again.body["awaiting"] == "declaration", "challenged, so it is asked again"
    assert again.body["refusals"], "and the refusal carries what fired, not just a status"
    assert again.body["refusals"][0]["triggers"]


def test_the_declaration_reuses_the_token_it_was_offered(tmp_path: Path) -> None:
    """0007: a client retyping what it was handed would get `unread` for the ordinary case."""
    adapter = _adapter(tmp_path)
    adapter.handle("POST", BEGIN, {"actor_id": "pc"})
    adapter.handle("POST", DECLARE, _no_test_body())

    ruling = getattr(adapter.session.pending, "ruling", None)
    assert ruling is not None
    assert str(ruling.alternatives_verdict) == "verified-fresh"


def test_the_report_comes_from_the_ledger(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    adapter.handle("POST", BEGIN, {"actor_id": "pc"})
    adapter.handle("POST", DECLARE, _no_test_body())
    adapter.handle("POST", NARRATE, {"text": "something happened"})

    assert "session" in adapter.handle("GET", REPORT).body["report"].lower()


# --- Refusals are statuses, not crashes ------------------------------------------------------


def test_an_unknown_route_is_404_and_names_what_exists(tmp_path: Path) -> None:
    response = _adapter(tmp_path).handle("POST", "/adjudicate", {})
    assert response.status == HTTPStatus.NOT_FOUND
    assert set(response.body["routes"]) == set(ROUTES)


def test_answering_the_wrong_question_is_409_rather_than_400(tmp_path: Path) -> None:
    """The request is well formed; the conversation is out of step. A 400 would tell a
    client to fix its JSON, which is not the problem."""
    adapter = _adapter(tmp_path)
    adapter.handle("POST", BEGIN, {"actor_id": "pc"})

    response = adapter.handle("POST", NARRATE, {"text": "nothing was ruled yet"})
    assert response.status == HTTPStatus.CONFLICT
    assert "AwaitingDeclaration" in response.body["error"]


def test_a_malformed_declaration_is_400(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    adapter.handle("POST", BEGIN, {"actor_id": "pc"})

    response = adapter.handle("POST", DECLARE, {})
    assert response.status == HTTPStatus.BAD_REQUEST
    assert "action_key or improvised_label" in response.body["error"]


def test_a_missing_actor_is_400_rather_than_a_traceback(tmp_path: Path) -> None:
    response = _adapter(tmp_path).handle("GET", LOOK, {})
    assert response.status == HTTPStatus.BAD_REQUEST


def test_facts_is_501_rather_than_absent(tmp_path: Path) -> None:
    """Unwired over every adapter. A route that fails loudly beats one quietly missing from
    the list a client plans against."""
    response = _adapter(tmp_path).handle("POST", FACTS, {})
    assert response.status == HTTPStatus.NOT_IMPLEMENTED
    assert "typed value" in response.body["error"]


def test_a_trailing_slash_and_a_query_string_reach_the_same_route(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    assert adapter.handle("GET", "/look/?actor_id=ignored", {"actor_id": "pc"}).ok


# --- Completeness, which is #134's general form ------------------------------------------------


def test_every_pending_state_is_reachable_over_http(tmp_path: Path) -> None:
    """A phase the loop can enter and this adapter cannot drive is a turn a client cannot
    finish — which is exactly what #134 was."""
    reachable = {"AwaitingDeclaration", "AwaitingNarration", "Finished", "TurnEnded"}
    names = {m.__name__ for m in pending_members()}
    assert names - reachable == {"AwaitingFacts"}, (
        "AwaitingFacts is reachable only once /facts is wired; every other state must have "
        "a route today"
    )
    for route in (BEGIN, DECLARE, NARRATE, END_TURN):
        assert route in ROUTES


def test_the_server_is_not_built_at_import_time() -> None:
    """`serve` imports `http.server` inside the function, so importing this adapter never
    costs a socket and never starts anything."""
    code = _code_of(http_module)
    assert "import http.server" not in code.split("def serve")[0]
    assert "ThreadingHTTPServer" not in code.split("def serve")[0]


def test_the_default_host_is_loopback() -> None:
    """A rules engine holding a live campaign is not a thing to expose on a network
    interface by accident, and the default is the one that cannot."""
    assert http_module.DEFAULT_HOST == "127.0.0.1"
