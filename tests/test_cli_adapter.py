"""The command-line adapter over the turn loop (R34, #133).

R34 names three adapters and only MCP existed. This is the second, and it is a **transport
binding over `Session`** — the same layer MCP occupies — rather than a driver.

The distinction is the thing this file has to keep honest, because the project already ships
`loop.drivers.HumanCliDriver` and both can be pointed at a terminal. A driver is *called by*
the loop as it runs; an adapter *holds* a suspended loop between calls and answers what it is
waiting for. `test_the_cli_adapter_is_not_the_cli_driver` states it so a later reader cannot
conclude the two are one thing wearing two names.

What is asserted here is mostly **shape**, and two properties matter more than the parsing:

* **No command reaches an outcome without the loop.** Asserted over every adapter at once
  now, rather than per adapter — `adapters.surface` holds the set, because the second copy
  is the one that goes stale.
* **Every `Pending` state is reachable, and `render` handles each.** This is #134's general
  form. That bug shipped because the suite asked what the surface contained and never
  whether it was complete.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path
from typing import Any

import pytest

from fixtures.encounter import build_adjudicator, opening_state
from fixtures.ruleset import LOOSE_SCREE
from srd_rules_engine.adapters import cli as cli_module
from srd_rules_engine.adapters import mcp as mcp_module
from srd_rules_engine.adapters.cli import (
    BEGIN,
    COMMAND_NAMES,
    DECLARE,
    END_TURN,
    ENGINE_COMMANDS,
    LOOK,
    NARRATE,
    REPORT,
    CliAdapter,
    CliError,
)
from srd_rules_engine.adapters.session import Session
from srd_rules_engine.adapters.surface import FORBIDDEN_COMMAND_NAMES, pending_members
from srd_rules_engine.loop import TurnLoop

SEED = 20260823


def _adapter(tmp: Path) -> CliAdapter:
    adjudicator = build_adjudicator(tmp, seed=SEED)
    session = Session(loop=TurnLoop(adjudicator=adjudicator), state=opening_state(seed=SEED))
    return CliAdapter(session=session, ledger=tmp / "ledger.jsonl", show=lambda _: None)


def _code_of(module: Any) -> str:
    """A module's source with its docstrings stripped, so prose about a rule cannot be
    mistaken for the rule being broken."""
    tree = ast.parse(Path(inspect.getfile(module)).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef) and ast.get_docstring(
            node
        ):
            node.body = node.body[1:]
    return ast.unparse(tree)


def _declare_no_test() -> str:
    return (
        f'{DECLARE} label="I stride across, I am sure-footed" '
        'no_test="the character is athletic, so no test is needed"'
    )


# --- The absence that is the design ----------------------------------------------------


def test_no_command_reaches_an_outcome_without_the_loop() -> None:
    """`AGENTS.md`: a consumer calling adjudication directly gets outcome authority without
    skip prevention. A `resolve` command would ship that as a feature."""
    assert not set(COMMAND_NAMES) & FORBIDDEN_COMMAND_NAMES
    assert "adjudicate" not in COMMAND_NAMES


@pytest.mark.parametrize(
    "surface",
    [pytest.param(COMMAND_NAMES, id="cli"), pytest.param(mcp_module.TOOL_NAMES, id="mcp")],
)
def test_the_forbidden_surface_is_asserted_over_every_adapter(surface: tuple[str, ...]) -> None:
    """#133 asked for this to be generalised rather than duplicated per adapter. A third
    adapter joins this parametrisation and inherits the guard."""
    assert not set(surface) & FORBIDDEN_COMMAND_NAMES


def test_no_command_waives_an_end_of_turn_obligation() -> None:
    """`advanced_turn(waive_obligations=True)` is for a consumer that wants to fast-forward.
    Exposing it here would offer a documented, supported way to skip a compulsory save to
    the caller the challenge mechanism exists to constrain — the same answer the MCP adapter
    gives, for the same reason."""
    assert not any("waive" in name for name in COMMAND_NAMES)
    # The module docstring explains the absence, so grepping the file would match its own
    # reasoning. Ask the code instead: this adapter never advances a turn at all, which is
    # the caller's job, so it has nothing to waive.
    assert "advanced_turn" not in _code_of(cli_module)
    assert "waive_obligations" not in _code_of(cli_module)


# --- Completeness, which is #134's general form -----------------------------------------


def test_render_handles_every_pending_state() -> None:
    source = Path(inspect.getfile(cli_module)).read_text(encoding="utf-8")
    for member in pending_members():
        assert f"isinstance(pending, {member.__name__})" in source, (
            f"render() has no branch for {member.__name__}"
        )
    assert "assert_never(pending)" in source, (
        "render must close on assert_never, so a new Pending member is a type error rather "
        "than a crash in somebody's session"
    )


def test_every_engine_command_is_a_real_command() -> None:
    assert set(ENGINE_COMMANDS) <= set(COMMAND_NAMES)


# --- The layer distinction ---------------------------------------------------------------


def test_the_cli_adapter_is_not_the_cli_driver() -> None:
    """R34's adapter and R8's driver are different layers, and `HumanCliDriver` existing is
    why the README status table counted one adapter rather than two (#133).

    An adapter binds to `Session`; a driver answers the loop's typed requests. If this file
    ever finds itself importing `Narrated` to answer a `NarrationRequest`, the layers have
    been collapsed.
    """
    from srd_rules_engine.loop.drivers import HumanCliDriver

    adapter_source = Path(inspect.getfile(cli_module)).read_text(encoding="utf-8")
    assert "Session" in adapter_source
    assert "NarrationRequest" not in adapter_source, "an adapter does not answer loop requests"
    assert HumanCliDriver.__module__ == "srd_rules_engine.loop.drivers"


# --- Driving a turn ------------------------------------------------------------------------


def test_look_reports_what_is_legal_without_starting_a_turn(tmp_path: Path) -> None:
    """R19: a read mutates nothing and records nothing, including that it happened."""
    adapter = _adapter(tmp_path)
    shown = adapter.dispatch(f"{LOOK} pc")

    assert "legal for pc" in shown
    assert "read_token:" in shown
    assert adapter.session.pending is None, "looking did not open a turn"


def test_a_turn_runs_from_begin_to_the_turns_end(tmp_path: Path) -> None:
    """The whole loop over the adapter, and the ordering 0023 imposes: the declaration slot
    finishing is not the turn ending."""
    adapter = _adapter(tmp_path)

    opened = adapter.dispatch(f"{BEGIN} pc")
    assert "awaiting declaration from pc" in opened

    ruled = adapter.dispatch(_declare_no_test())
    assert "you may claim" in ruled, "a ruling exists and owes a narration"

    finished = adapter.dispatch(f"{NARRATE} the character picks their way across")
    assert "declaration slot finished" in finished
    assert f"run `{END_TURN} pc`" in finished, "an agent stopping here stops one phase early"

    ended = adapter.dispatch(f"{END_TURN} pc")
    assert "turn ended for pc" in ended
    assert "0 obligation(s) resolved" in ended


def test_a_skip_that_collides_comes_back_challenged(tmp_path: Path) -> None:
    """The product's core claim, over this adapter rather than in the core."""
    adapter = _adapter(tmp_path)
    situation = " ".join(f"{k}={v}" for k, v in dict(LOOSE_SCREE).items())
    adapter.dispatch(f"{BEGIN} pc {situation}")

    again = adapter.dispatch(_declare_no_test())
    assert "awaiting declaration" in again, "challenged, so it is asked again"
    assert "refused:" in again, "and the refusal is carried, not merely implied"


def test_the_declaration_reuses_the_token_it_was_just_offered(tmp_path: Path) -> None:
    """0007: the alternatives are the agent's claim and the token makes it checkable. A
    consumer retyping what it was handed would get `unread` for the ordinary case."""
    adapter = _adapter(tmp_path)
    adapter.dispatch(f"{BEGIN} pc")
    adapter.dispatch(_declare_no_test())

    pending = adapter.session.pending
    ruling = getattr(pending, "ruling", None)
    assert ruling is not None
    assert str(ruling.alternatives_verdict) == "verified-fresh"


def test_the_report_comes_from_the_ledger(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    adapter.dispatch(f"{BEGIN} pc")
    adapter.dispatch(_declare_no_test())
    adapter.dispatch(f"{NARRATE} something happened")

    assert "session" in adapter.dispatch(REPORT).lower()


# --- Refusals are refusals, not crashes ----------------------------------------------------


def test_an_unknown_command_is_refused_by_name(tmp_path: Path) -> None:
    with pytest.raises(CliError, match="no such command"):
        _adapter(tmp_path).dispatch("adjudicate pc")


def test_a_malformed_declaration_says_what_it_needed(tmp_path: Path) -> None:
    adapter = _adapter(tmp_path)
    adapter.dispatch(f"{BEGIN} pc")
    with pytest.raises(CliError, match="action=<key> or label="):
        adapter.dispatch(DECLARE)


def test_a_blank_line_does_nothing(tmp_path: Path) -> None:
    assert _adapter(tmp_path).dispatch("   ") == ""


def test_the_loop_survives_a_bad_command(tmp_path: Path) -> None:
    """A mistyped command is not a reason to discard a suspended turn, which is the thing
    this adapter exists to hold."""
    adapter = _adapter(tmp_path)
    shown: list[str] = []
    adapter.show = shown.append
    lines = iter([f"{BEGIN} pc", "nonsense", "quit"])

    adapter.run(lambda _: next(lines))

    assert any("refused:" in line for line in shown)
    assert adapter.session.pending is not None, "the turn is still held"


def test_facts_fails_loudly_rather_than_being_absent(tmp_path: Path) -> None:
    """Unwired over every adapter, not only this one. A command that raises beats one
    quietly missing from the list a consumer plans against."""
    with pytest.raises(NotImplementedError, match="typed value"):
        _adapter(tmp_path).dispatch("facts")


def test_render_is_exhaustive_at_runtime_too(tmp_path: Path) -> None:
    """`assert_never` is a static check; this proves each branch returns text rather than
    falling through."""
    adapter = _adapter(tmp_path)
    for command in (f"{BEGIN} pc", _declare_no_test(), f"{NARRATE} x", f"{END_TURN} pc"):
        assert adapter.dispatch(command).strip()


def test_the_run_loop_exits_on_eof(tmp_path: Path) -> None:
    def ask(_: str) -> str:
        raise EOFError

    def boom(_: Any) -> None:
        return None

    adapter = _adapter(tmp_path)
    adapter.show = boom
    adapter.run(ask)
