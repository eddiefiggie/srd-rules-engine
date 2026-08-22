"""The file-backed reference implementation of the memory port.

Holds current fact values only. The ledger is the system of record for fact history,
so this store is a projection that rebuilds from it — which is why it is flat JSON on
a substrate separate from the ledger rather than a database.

See `docs/decisions/0009-reference-memory-store.md`.
"""

from __future__ import annotations

__all__: list[str] = []
