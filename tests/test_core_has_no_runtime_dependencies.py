"""R33, enforced rather than remembered.

The core takes no LLM dependency and no network dependency. That is an
architectural promise the project sells, and the cheapest way to break it is a
convenience import added in a hurry. `[project].dependencies` staying empty is the
machine-readable form of the promise; this test is what notices when it stops
being true.

Adapters (MCP, HTTP, CLI) legitimately need dependencies. They declare them as
optional extras, which this test deliberately does not police.
"""

from __future__ import annotations

import tomllib
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_core_declares_no_runtime_dependencies() -> None:
    config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    dependencies = config["project"]["dependencies"]
    assert dependencies == [], (
        f"The core declared runtime dependencies: {dependencies}. R33 says the core "
        "takes no LLM and no network dependency. If an adapter needs this, move it "
        "to [project.optional-dependencies]."
    )
