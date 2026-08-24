"""Adapters: the surfaces an agent reaches the engine through.

The core takes no LLM and no network dependency (R33), and `[project].dependencies` staying
empty is the machine-readable form of that promise. Anything an adapter needs is an extra,
so installing the library never installs a transport.

`tests/test_layer_boundaries.py` enforces the direction: nothing in `core` imports an
adapter, and nothing here imports a `core` submodule — adapters use what `core` re-exports,
which is what makes "the adapters are built over the same contract" checkable rather than
aspirational.
"""

from __future__ import annotations

from srd_rules_engine.adapters.session import (
    AwaitingDeclaration,
    AwaitingFacts,
    AwaitingNarration,
    Finished,
    Pending,
    Session,
    SessionError,
    TurnEnded,
)
from srd_rules_engine.adapters.surface import FORBIDDEN_COMMAND_NAMES, pending_members

__all__ = [
    "FORBIDDEN_COMMAND_NAMES",
    "AwaitingDeclaration",
    "AwaitingFacts",
    "AwaitingNarration",
    "Finished",
    "Pending",
    "Session",
    "SessionError",
    "TurnEnded",
    "pending_members",
]
