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
import re

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

    `TurnEnded` and `TurnEnd` were added by #133. They should have arrived with #125: four of
    `Pending`'s five members were already committed, and a consumer matching on the union has
    to handle the fifth. The pin is what made adding them a deliberate edit rather than a
    silent one, which is the whole point of listing them here.
    """
    assert set(COMMITTED) == {
        "srd_rules_engine.adapters.AwaitingDeclaration",
        "srd_rules_engine.adapters.AwaitingFacts",
        "srd_rules_engine.adapters.AwaitingNarration",
        "srd_rules_engine.adapters.Finished",
        "srd_rules_engine.adapters.TurnEnded",
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
        "srd_rules_engine.loop.TurnEnd",
        "srd_rules_engine.loop.TurnOutcome",
    }


def test_no_name_is_committed_twice() -> None:
    assert len(COMMITTED) == len(set(COMMITTED))


def test_the_two_tiers_do_not_overlap() -> None:
    """A surface is committed or provisional, never both — the tiers make different
    promises and a name in each would make neither checkable."""
    assert not set(COMMITTED) & set(PROVISIONAL)


BUILD_STAMP = re.compile(r"^\d{8}\.\d+$")


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
    different questions and must not be derived from one another.

    **Independence is asserted structurally, not by comparing the values.** The earlier
    version of this test asserted `str(API_VERSION) not in {stamp, iteration}`, which went
    red on build `08242026.2` — the day's second build, against an API at 2 — while nothing
    about the code had changed. Its own comment warned about exactly that failure mode for
    substring containment and then reproduced it one line down: two independent numbers
    coincide sooner or later, and a test that treats a coincidence as a defect fails on the
    calendar.

    What "not derived from" actually means is that the module defining `API_VERSION` does
    not read the build stamp. That is checkable, and it stays true whatever today's date is.
    """
    import inspect

    from srd_rules_engine import __version__, stability

    assert isinstance(API_VERSION, int)
    assert BUILD_STAMP.match(__version__), "the stamp is still a stamp"

    source = inspect.getsource(stability)
    assert "__version__" not in source, (
        "srd_rules_engine.stability reads the build stamp. The two answer different "
        "questions — 0011 — and deriving one from the other would make a date carry a "
        "compatibility claim"
    )


def test_the_api_version_is_independent_of_the_schema_versions() -> None:
    """A schema bump need not be an API break, and an API break need not touch a schema.
    `RULING_VERSION` is 6 while the API is at 2, which is the distinction in the data rather
    than only in the record.
    """
    from srd_rules_engine.core.adjudicate import RULING_VERSION

    # The two moved together once — #105 changed what an effect's `amount` means, which is
    # both a payload change and a committed-behaviour change — and they still hold different
    # values, because they have counted different things since before that.
    #
    # #119 is the clean counter-example: the ruling payload grew three fields and `Effect`
    # grew three optional ones, so the schema moved to 4 and the API did not move at all.
    # Optional fields with defaults break no consumer.
    #
    # #192 is the third and the only one that RENAMED a field: an effect's `grappler`
    # became `source` when Grappled stopped being the only condition whose text turned
    # on who imposed it. Not additive — a v5 reader finds nothing under the old key —
    # and still not an API break, because `Effect` is Internal and no committed name
    # moved. Schema 6, API 2.
    #
    # #170 is the second, and a sharper one: `Proposal.test` became OPTIONAL and the payload
    # grew `testless`, so a resolver written against the old shape still compiles and still
    # behaves — the field it stopped being required to pass, it passes anyway. The schema
    # moved to 5 and the API did not move.
    assert RULING_VERSION == 6
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


def test_every_exported_name_resolves() -> None:
    """#200. `from srd_rules_engine.core import *` raised on `main` for three of 159 names.

    `core/__init__.py` exists to be R34's re-export surface: an outer layer may reach a core
    symbol **only** through it. So a name in `__all__` that resolves to nothing is not an
    untidy list — it is a capability the engine claims and an adapter cannot reach.

    All three were worse than unreachable. `DeathSaves`, `adjust_roll` and
    `override_to_success` are each named in `ENGINE_SHAPES` as what resolves an inventory
    shape, so the inventory said the engine could do it, R34 said there was one way to get
    at it, and that way raised.

    `tests/test_layer_boundaries.py` cannot see this: it checks the *direction* of imports,
    and a name missing from a re-export is not an import at all. Nothing else looked, which
    is how a hand-maintained list of 159 entries drifted.
    """
    import srd_rules_engine.core as core

    unresolvable = sorted(name for name in core.__all__ if not hasattr(core, name))
    assert unresolvable == [], (
        f"{unresolvable} are exported by name and resolve to nothing. An outer layer "
        "following R34 cannot reach them, and `from core import *` raises"
    )


def test_nothing_is_exported_twice() -> None:
    """The other way a hand-maintained list drifts. A duplicate is harmless to Python and is
    a reliable sign that two edits added the same name without either seeing the other.

    **A deliberate "nothing changed" guard** — `AGENTS.md`'s named exception. It passes
    against the base commit, because the list happened to be free of duplicates; the sibling
    above is the one that was red. It is here because the two failure modes of a
    hand-maintained list are drift in each direction, and checking one of them would have
    read as checking the list.
    """
    import srd_rules_engine.core as core

    duplicates = sorted({n for n in core.__all__ if core.__all__.count(n) > 1})
    assert duplicates == [], f"{duplicates} appear more than once in core.__all__"


# --- What a name at the package root resolves to (#112) --------------------------------


def test_condition_at_the_package_root_is_the_srd_condition() -> None:
    """R34 sends every outer layer to `core` for its names, so `core.Condition` is the one
    a consumer will reach for — and until #112 it was the trigger predicate.

    Both types existed under that name. The failure was loud only where an enum member was
    looked up; anywhere both satisfied a signature it was silent, and the SRD enum is by far
    the more likely thing to want, since `Situation.conditions` is full of it.

    Pinned by identity rather than by name, so re-exporting the wrong module cannot satisfy
    it.
    """
    import srd_rules_engine.core as core
    from srd_rules_engine.core.conditions import Condition as SrdCondition

    assert core.Condition is SrdCondition
    # Not `is not MatchCondition`: mypy now proves the two types cannot be the same object,
    # which makes that assertion a tautology it rejects — and the fact that it *can* prove it
    # is the fix working. The module check still fails at runtime if the export moves back.
    assert core.Condition.__module__.endswith(".conditions"), "not the trigger module"
    assert len(core.Condition) == 15, "the fifteen the Rules Glossary tags [Condition]"


def test_the_trigger_predicate_is_not_named_condition_anywhere() -> None:
    """The rename is the fix; re-adding the old alias would restore the collision while
    every other test kept passing."""
    from srd_rules_engine.core import triggers

    assert not hasattr(triggers, "Condition"), (
        "the trigger predicate is `MatchCondition` — decision 0004's own term for it, and "
        "not `Predicate`, which 0004 uses for the callable design it rejected"
    )
    assert "MatchCondition" in triggers.Trigger.__dataclass_fields__["when"].type
