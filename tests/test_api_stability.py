"""The committed surface resolves, and has not changed without somebody deciding (#39, 0018).

A stability policy written in prose degrades the moment somebody renames a symbol during a
refactor and nobody connects it to the document. This project has watched that happen twice
already — `source.section` was wrong for five sweeps because it was a hand-written literal
nobody compared to the data, and a no-prose guard passed while inspecting nothing because it
tested content rather than shape.

So the promise is enumerated and this file checks it. A committed name that stops resolving,
or a set that changes, turns red — which forces the change to be a decision rather than a
diff nobody noticed.
"""

from __future__ import annotations

import importlib

import pytest

from srd_rules_engine.stability import API_VERSION, COMMITTED, PROVISIONAL


def _resolve(qualified: str) -> object:
    module_name, _, attribute = qualified.rpartition(".")
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


@pytest.mark.parametrize("qualified", COMMITTED)
def test_every_committed_name_resolves(qualified: str) -> None:
    """A promise to something that does not exist is worse than no promise."""
    assert _resolve(qualified) is not None


@pytest.mark.parametrize("qualified", PROVISIONAL)
def test_every_provisional_name_resolves(qualified: str) -> None:
    """Provisional means expected to move, not free to be wrong today."""
    assert _resolve(qualified) is not None


def test_the_committed_set_is_exactly_this() -> None:
    """The pin. Adding a surface is a deliberate edit here; removing one turns this red.

    Listed rather than counted, because a count would let a rename pass — one name out, one
    name in, the total unchanged and the promise broken.
    """
    assert set(COMMITTED) == {
        "srd_rules_engine.adapters.AwaitingDeclaration",
        "srd_rules_engine.adapters.AwaitingFacts",
        "srd_rules_engine.adapters.AwaitingNarration",
        "srd_rules_engine.adapters.Finished",
        "srd_rules_engine.adapters.Session",
        "srd_rules_engine.adapters.SessionError",
        "srd_rules_engine.core.Declaration",
        "srd_rules_engine.core.Effect",
        "srd_rules_engine.core.EffectKind",
        "srd_rules_engine.core.Entry",
        "srd_rules_engine.core.Fact",
        "srd_rules_engine.core.FactType",
        "srd_rules_engine.core.Finding",
        "srd_rules_engine.core.Intent",
        "srd_rules_engine.core.LegalAction",
        "srd_rules_engine.core.MemoryPort",
        "srd_rules_engine.core.Provenance",
        "srd_rules_engine.core.READER_VERSION",
        "srd_rules_engine.core.ReadResult",
        "srd_rules_engine.core.Resolution",
        "srd_rules_engine.core.Ruling",
        "srd_rules_engine.core.Status",
        "srd_rules_engine.core.ValueKind",
        "srd_rules_engine.core.Verdict",
        "srd_rules_engine.core.read",
        "srd_rules_engine.core.read_ledger",
        "srd_rules_engine.loop.BlockedFactRequest",
        "srd_rules_engine.loop.DeclarationRequest",
        "srd_rules_engine.loop.Declared",
        "srd_rules_engine.loop.FactsSupplied",
        "srd_rules_engine.loop.Narrated",
        "srd_rules_engine.loop.NarrationRequest",
        "srd_rules_engine.loop.TurnLoop",
        "srd_rules_engine.loop.TurnOutcome",
    }


def test_no_name_is_committed_twice() -> None:
    assert len(COMMITTED) == len(set(COMMITTED))


def test_the_two_tiers_do_not_overlap() -> None:
    """A surface is committed or provisional, never both — the tiers make different
    promises and a name in each would make neither checkable."""
    assert not set(COMMITTED) & set(PROVISIONAL)


def test_the_mcp_tool_names_are_provisional_and_the_session_is_not() -> None:
    """The tool list is six names old. Committing to it would either freeze a first draft or
    make `API_VERSION` meaningless within a month — so a consumer wanting stability builds
    on `adapters.Session`, which is committed.
    """
    assert "srd_rules_engine.adapters.mcp.TOOL_NAMES" in PROVISIONAL
    assert "srd_rules_engine.adapters.Session" in COMMITTED
    assert not any(name.startswith("srd_rules_engine.adapters.mcp") for name in COMMITTED)


def test_the_api_version_is_independent_of_the_build_stamp() -> None:
    """0011 fixed that the build stamp carries no compatibility information. These answer
    different questions and must not be derived from one another."""
    from srd_rules_engine import __version__

    stamp, iteration = __version__.split(".")
    assert isinstance(API_VERSION, int)
    # Not a *component* of the build stamp. Plain substring containment is the obvious
    # check and the wrong one: a single-digit API version matches any date carrying that
    # digit, so the assertion would pass or fail on the calendar rather than on the code.
    assert str(API_VERSION) not in {stamp, iteration}


def test_the_api_version_is_independent_of_the_schema_versions() -> None:
    """A schema bump need not be an API break, and an API break need not touch a schema.
    `RULING_VERSION` is 3 while the API is at 2, which is the distinction in the data rather
    than only in the record.
    """
    from srd_rules_engine.core.adjudicate import RULING_VERSION

    # The two moved together once — #105 changed what an effect's `amount` means, which is
    # both a payload change and a committed-behaviour change — and they still hold different
    # values, because they have counted different things since before that.
    assert RULING_VERSION == 3
    assert API_VERSION == 2
    assert RULING_VERSION != API_VERSION


def test_most_of_core_is_deliberately_unpromised() -> None:
    """R34 requires outer layers to use what `core` re-exports, so the export list is long
    for an import reason rather than a contractual one. Stating that is more useful than a
    promise across 110 names that nobody could keep.
    """
    import srd_rules_engine.core as core

    committed_from_core = {n for n in COMMITTED if n.startswith("srd_rules_engine.core.")}
    assert len(core.__all__) > 3 * len(committed_from_core), (
        "if the committed set ever approaches the export list, the tiers have stopped "
        "meaning anything and 0018 needs revisiting"
    )
