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

from srd_rules_engine.core.canonical import CanonicalizationError, canonicalize, digest

__all__ = ["CanonicalizationError", "canonicalize", "digest"]
