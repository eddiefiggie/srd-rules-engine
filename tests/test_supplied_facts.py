"""Answering a blocked declaration, and everything a caller is not allowed to say (#144).

Decision 0010 makes a block a *suspension*: the declaration was accepted, the port could not
resolve a fact it consumes, and the same declaration resumes once the value arrives — the
agent is not asked again and 0005's retry budget is not charged. Every transport declared a
command for that and every one of them raised, so a turn that blocked had no route forward
over MCP, HTTP or the CLI. `Session.supply_values` is that route.

**The interesting half is what the caller may not supply.** A `Fact` has four fields and
three of them are ways for a supplied value to become something it is not:

* the **subject**, which would let a turn suspended on one creature write about another;
* the **kind**, which would let a caller disagree with the engine about what it just stored
  (R20 — the port takes typed values, so a generous reading is a wrong value with a right
  shape);
* the **writer**, which is the sharpest of the three. `Writer.RULING` means a value an
  adjudicated outcome produced. A caller able to claim it would be dressing an unrolled
  fact as a ruling's product, which is the failure this whole engine exists to remove.

So the caller supplies a name and a value, and the engine decides the rest. These tests are
mostly about refusals, because the refusals are the design.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from fixtures.encounter import build_adjudicator, needs_nerve, opening_state
from fixtures.ruleset import NERVE
from srd_rules_engine.adapters import AwaitingDeclaration, AwaitingFacts, Session
from srd_rules_engine.adapters.session import DEFAULT_FACT_REFERENCE, FactRefused
from srd_rules_engine.core import Writer
from srd_rules_engine.core.report import session_report
from srd_rules_engine.loop import TurnLoop

SEED = 20260823


def _blocked_session(tmp: Path) -> Session:
    """A session suspended on `nerve`, which has no honest default to fall back on."""
    adjudicator = build_adjudicator(tmp, seed=SEED)
    session = Session(loop=TurnLoop(adjudicator=adjudicator), state=opening_state(seed=SEED))
    pending = session.begin("pc")
    assert isinstance(pending, AwaitingDeclaration)
    pending = session.declare(needs_nerve(pending))  # type: ignore[arg-type]
    assert isinstance(pending, AwaitingFacts), "the fixture rule must block"
    assert pending.unresolved == (NERVE.name,)
    return session


# --- The route that did not exist --------------------------------------------------


def test_a_supplied_value_resumes_the_same_declaration(tmp_path: Path) -> None:
    """0010: a suspension, not a refusal. The slot shows one attempt, not two."""
    session = _blocked_session(tmp_path)

    session.supply_values({"nerve": True})

    report = session_report(tmp_path / "ledger.jsonl")
    assert report.turns[0].attempts == 1, "the agent was asked again, so this was a retry"
    assert report.turns[0].status in {"ruled", "no-test"}


def test_the_stored_fact_is_about_the_actor_the_turn_suspended_on(tmp_path: Path) -> None:
    session = _blocked_session(tmp_path)

    session.supply_values({"nerve": True})

    stored = session.loop.adjudicator.port.get("nerve", "pc")
    assert stored is not None, "the value was not written for the blocked actor"
    assert stored.value is True


def test_a_supplied_value_is_written_out_of_band_and_never_as_a_ruling(tmp_path: Path) -> None:
    """R25. The writer is not an argument, so a caller cannot dress an unrolled fact as an
    adjudicated outcome — which would make it indistinguishable from one the dice decided."""
    session = _blocked_session(tmp_path)

    session.supply_values({"nerve": True})

    stored = session.loop.adjudicator.port.get("nerve", "pc")
    assert stored is not None
    assert stored.provenance.writer is Writer.OUT_OF_BAND
    assert stored.provenance.reference == DEFAULT_FACT_REFERENCE


def test_a_caller_may_say_where_the_value_came_from(tmp_path: Path) -> None:
    session = _blocked_session(tmp_path)

    session.supply_values({"nerve": False}, reference="session 3 notes")

    stored = session.loop.adjudicator.port.get("nerve", "pc")
    assert stored is not None
    assert stored.provenance.reference == "session 3 notes"
    assert stored.provenance.writer is Writer.OUT_OF_BAND, "a note does not change the writer"


# --- What the caller may not say ---------------------------------------------------


def test_a_fact_nobody_asked_for_is_refused(tmp_path: Path) -> None:
    """A suspension answers a question; it does not open the store to writes."""
    session = _blocked_session(tmp_path)

    with pytest.raises(FactRefused, match="not what the engine is blocked on"):
        session.supply_values({"footing": "firm"})

    assert session.loop.adjudicator.port.get("footing", "pc") is None


def test_a_value_of_the_wrong_kind_is_refused_rather_than_read_generously(
    tmp_path: Path,
) -> None:
    """R20. "yes" is not a Boolean, and deciding that it probably meant one is the engine
    interpreting again."""
    session = _blocked_session(tmp_path)

    with pytest.raises(FactRefused, match="not true or false"):
        session.supply_values({"nerve": "yes"})


def test_a_number_is_not_a_boolean(tmp_path: Path) -> None:
    session = _blocked_session(tmp_path)

    with pytest.raises(FactRefused, match="not true or false"):
        session.supply_values({"nerve": 1})


def test_nothing_supplied_is_refused_by_name(tmp_path: Path) -> None:
    session = _blocked_session(tmp_path)

    with pytest.raises(FactRefused, match="nerve"):
        session.supply_values({})


def test_a_refused_value_leaves_the_turn_suspended(tmp_path: Path) -> None:
    """The refusal is not a terminal state — the caller can try again with a real value,
    and the declaration it was blocked on is still the one waiting."""
    session = _blocked_session(tmp_path)

    with pytest.raises(FactRefused):
        session.supply_values({"nerve": "yes"})

    assert isinstance(session.pending, AwaitingFacts)
    session.supply_values({"nerve": True})
    assert session_report(tmp_path / "ledger.jsonl").turns[0].attempts == 1


def test_supplying_facts_outside_a_block_is_refused(tmp_path: Path) -> None:
    adjudicator = build_adjudicator(tmp_path, seed=SEED)
    session = Session(loop=TurnLoop(adjudicator=adjudicator), state=opening_state(seed=SEED))
    session.begin("pc")

    with pytest.raises(Exception, match="waiting for"):
        session.supply_values({"nerve": True})
