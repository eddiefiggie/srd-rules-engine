"""The turn-driving loop — outside the core, and the only thing the adapters expose.

Owns the turn, yields typed requests to a driver rather than calling an agent, and
owns the retry bound. It may use what `core` re-exports and nothing deeper.

See `docs/decisions/0001-agent-seam.md` and `docs/decisions/0005-retry-bounds.md`.
"""

from __future__ import annotations

__all__: list[str] = []
