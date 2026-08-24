"""The turn-driving loop — outside the core, and the only thing the adapters expose.

Owns the turn, yields typed requests to a driver rather than calling an agent, and
owns the retry bound. It may use what `core` re-exports and nothing deeper.

See `docs/decisions/0001-agent-seam.md` and `docs/decisions/0005-retry-bounds.md`.
"""

from __future__ import annotations

from srd_rules_engine.loop.drivers import (
    DriverExhausted,
    HumanCliDriver,
    ScriptedDriver,
    drive,
)
from srd_rules_engine.loop.turn import (
    DEFAULT_BUDGET,
    BlockedFactRequest,
    DeclarationRequest,
    Declared,
    FactsSupplied,
    Narrated,
    NarrationOwed,
    NarrationRequest,
    Obligation,
    Request,
    Response,
    TerminalReason,
    TurnEnd,
    TurnLoop,
    TurnOutcome,
)

__all__ = [
    "DEFAULT_BUDGET",
    "BlockedFactRequest",
    "DeclarationRequest",
    "Declared",
    "DriverExhausted",
    "FactsSupplied",
    "HumanCliDriver",
    "Narrated",
    "NarrationOwed",
    "NarrationRequest",
    "Obligation",
    "Request",
    "Response",
    "ScriptedDriver",
    "TerminalReason",
    "TurnEnd",
    "TurnLoop",
    "TurnOutcome",
    "drive",
]
