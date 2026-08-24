"""What this package promises, and what it does not (R35, decision 0018).

`core` re-exports 110 names. Most of them exist because R34 requires outer layers to use
what `core` re-exports rather than reaching into submodules — they are there to satisfy an
import rule, not because a consumer was ever meant to depend on them. A policy promising
stability across all of them would be promising something nobody can keep.

So the question this module answers is not *how stable is the API* but **which of it is an
API at all**.

## Three tiers

* **Committed** — enumerated in `COMMITTED` below. Breaking one raises `API_VERSION`, and a
  removed name stays importable for at least one `API_VERSION` with a `DeprecationWarning`
  naming its replacement.
* **Provisional** — the MCP tool names and their argument schemas. Named, documented, and
  expected to move; a change is recorded in the changelog and raises nothing. The `Session`
  underneath them *is* committed, so a consumer wanting stability builds on that.
* **Internal** — everything else. Importable, unpromised.

## `API_VERSION` is not a smaller semver

Semver's minor-versus-patch split answers "may I upgrade without reading". For this surface
there is no such distinction: either what you built against still resolves and behaves, or it
does not. A monotonic integer is honest about carrying exactly one bit.

It is independent of the build stamp (which identifies a build, and 0011 fixed that it
carries no compatibility information), and of the data schema versions (which answer "can I
interpret this file"). A schema bump need not be an API break, and an API break need not
touch a schema — 0006 drew that line between engine version and schema version, and it holds.

## Two fixed points this cannot relax

The ledger **envelope can never change** (0006), and the payload's reserved `compat` key is
fixed alongside it (0011). Both are committed regardless of what `API_VERSION` says, and
nothing here has the authority to loosen them.
"""

from __future__ import annotations

from typing import Final

#: Raised when a committed surface breaks. Monotonic, and independent of everything else.
API_VERSION: Final = 1

#: The committed surface, by qualified name. Enumerated rather than described, because a
#: policy in prose degrades the moment somebody renames a symbol and nobody connects it to
#: the document. `tests/test_api_stability.py` resolves every name and pins the set, so a
#: removal turns red rather than passing unnoticed.
COMMITTED: Final[tuple[str, ...]] = (
    # R35: the ledger reader is public, and reading a ledger is the one thing a consumer
    # can do without running the engine at all.
    "srd_rules_engine.core.Entry",
    "srd_rules_engine.core.Finding",
    "srd_rules_engine.core.READER_VERSION",
    "srd_rules_engine.core.read_ledger",
    # R20: the memory port is a protocol consumers implement, so its shape is theirs to
    # depend on. Typed values only — the moment it returns prose the engine is interpreting
    # narrative again.
    "srd_rules_engine.core.Fact",
    "srd_rules_engine.core.FactType",
    "srd_rules_engine.core.MemoryPort",
    "srd_rules_engine.core.Provenance",
    "srd_rules_engine.core.Resolution",
    "srd_rules_engine.core.ValueKind",
    # 0001: the agent seam. A driver is written against these four request and response
    # types and nothing else.
    "srd_rules_engine.loop.BlockedFactRequest",
    "srd_rules_engine.loop.DeclarationRequest",
    "srd_rules_engine.loop.Declared",
    "srd_rules_engine.loop.FactsSupplied",
    "srd_rules_engine.loop.Narrated",
    "srd_rules_engine.loop.NarrationRequest",
    "srd_rules_engine.loop.TurnLoop",
    "srd_rules_engine.loop.TurnOutcome",
    # 0016: the adapter session, which is what a transport binds to. The MCP tool names on
    # top of it are provisional; this is not.
    "srd_rules_engine.adapters.AwaitingDeclaration",
    "srd_rules_engine.adapters.AwaitingFacts",
    "srd_rules_engine.adapters.AwaitingNarration",
    "srd_rules_engine.adapters.Finished",
    "srd_rules_engine.adapters.Session",
    "srd_rules_engine.adapters.SessionError",
    # What a Ruling is made of. A consumer reading an outcome depends on these whether it
    # drives the loop or reads a ledger.
    "srd_rules_engine.core.Declaration",
    "srd_rules_engine.core.Effect",
    "srd_rules_engine.core.EffectKind",
    "srd_rules_engine.core.Intent",
    "srd_rules_engine.core.Ruling",
    "srd_rules_engine.core.Status",
    # The read surface an agent decides from (R18), and the token that makes its claim
    # checkable (0007).
    "srd_rules_engine.core.LegalAction",
    "srd_rules_engine.core.ReadResult",
    "srd_rules_engine.core.Verdict",
    "srd_rules_engine.core.read",
)

#: Surfaces named and documented but expected to move. A change here is a changelog entry,
#: not an `API_VERSION` bump.
PROVISIONAL: Final[tuple[str, ...]] = ("srd_rules_engine.adapters.mcp.TOOL_NAMES",)
