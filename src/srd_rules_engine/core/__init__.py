"""The adjudication core — the only thing that may decide how a ruling turns out.

Holds the read surface, the legality derivation, adjudication, the trigger matcher,
the ledger, and the memory-port protocol. Two import rules bound this package, and
`tests/test_layer_boundaries.py` enforces both:

1. Nothing here may import from an outer layer. An empty `[project].dependencies`
   constrains what the package pulls in from outside, not how its own layers depend
   on each other — a core module importing an adapter would break R33 while that
   list still read empty.
2. Nothing outside the core may import a *submodule* of this package. Outer layers
   use what this module re-exports, which is what makes R34's "built over the same
   contract" a fact about the import graph rather than a description of intent.

See `docs/decisions/0011-module-layout-and-versioning.md`.
"""

from __future__ import annotations

from srd_rules_engine.core.adjudicate import (
    Adjudicator,
    Declaration,
    Effect,
    EffectKind,
    Intent,
    NarrationBounds,
    Proposal,
    Resolver,
    Ruling,
    Status,
)
from srd_rules_engine.core.canonical import CanonicalizationError, canonicalize, digest
from srd_rules_engine.core.d20 import (
    DIE_SIDES,
    Advantage,
    D20Result,
    D20Test,
    Modifier,
    TestKind,
)
from srd_rules_engine.core.ledger import Ledger, LedgerUnavailable
from srd_rules_engine.core.ledger_reader import (
    READER_VERSION,
    Entry,
    Finding,
    LedgerReport,
    read_ledger,
    repair_truncated_tail,
    summarize,
)
from srd_rules_engine.core.memory_port import (
    FACT_WRITE,
    DefaultKind,
    Fact,
    FactType,
    LedgerBackedPort,
    MemoryError_,
    MemoryPort,
    Provenance,
    Resolution,
    ValueKind,
    Writer,
    check_storable,
    fact_from_payload,
    fact_write_payload,
    is_extension,
    resolve,
)
from srd_rules_engine.core.read_surface import (
    LegalAction,
    ReadResult,
    Verdict,
    issue_token,
    legal_actions,
    read,
    verify,
)
from srd_rules_engine.core.rules import (
    Rule,
    RuleLoadError,
    RuleProvenance,
    Ruleset,
    Verification,
    VerificationState,
    load_fixture_ruleset,
    load_ruleset,
)
from srd_rules_engine.core.state import Combatant, EncounterState

__all__ = [
    "DIE_SIDES",
    "FACT_WRITE",
    "READER_VERSION",
    "Adjudicator",
    "Advantage",
    "CanonicalizationError",
    "Combatant",
    "D20Result",
    "D20Test",
    "Declaration",
    "DefaultKind",
    "Effect",
    "EffectKind",
    "EncounterState",
    "Entry",
    "Fact",
    "FactType",
    "Finding",
    "Intent",
    "Ledger",
    "LedgerBackedPort",
    "LedgerReport",
    "LedgerUnavailable",
    "LegalAction",
    "MemoryError_",
    "MemoryPort",
    "Modifier",
    "NarrationBounds",
    "Proposal",
    "Provenance",
    "ReadResult",
    "Resolution",
    "Resolver",
    "Rule",
    "RuleLoadError",
    "RuleProvenance",
    "Ruleset",
    "Ruling",
    "Status",
    "TestKind",
    "ValueKind",
    "Verdict",
    "Verification",
    "VerificationState",
    "Writer",
    "canonicalize",
    "check_storable",
    "digest",
    "fact_from_payload",
    "fact_write_payload",
    "is_extension",
    "issue_token",
    "legal_actions",
    "load_fixture_ruleset",
    "load_ruleset",
    "read",
    "read_ledger",
    "repair_truncated_tail",
    "resolve",
    "summarize",
    "verify",
]
