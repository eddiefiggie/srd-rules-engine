"""Every build stamp the README prints must match the package version.

Not ceremony. The README is the only place a reader learns what this build is and
what shipped in it, and a README that lags the code is worse than one that is
absent: it reads as current. Bumping the version and forgetting the README is the
single easiest mistake to make here, so it is the one thing CI refuses.

The README prints the stamp **twice** — the header's `**Current build:**` line and
the footer's `_Last updated:_` line — and this test long checked only the header, so
the footer sat two builds behind the package with CI green. A guard covering one of
two copies certifies exactly the drift it exists to catch. Both are checked here,
and a third stamp added later belongs in `STAMP_SITES` rather than uncovered.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from srd_rules_engine import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

BUILD_LINE = re.compile(r"^\*\*Current build:\*\* `(?P<version>[^`]+)`", re.MULTILINE)
FOOTER_LINE = re.compile(r"^_Last updated: [^_]*?build `(?P<version>[^`]+)`\._$", re.MULTILINE)
BUILD_STAMP = re.compile(r"^\d{8}\.\d+$")

# Every place the README states the build, described as a reader would find it.
STAMP_SITES = (
    ("header", "the '**Current build:** `mmddyyyy.x`' line", BUILD_LINE),
    ("footer", "the '_Last updated: ... build `mmddyyyy.x`._' line", FOOTER_LINE),
)


def test_version_is_a_well_formed_build_stamp() -> None:
    assert BUILD_STAMP.match(__version__), (
        f"__version__ is {__version__!r}; expected the mmddyyyy.x build stamp format."
    )


@pytest.mark.parametrize(
    ("where", "pattern"),
    [(where, pattern) for _, where, pattern in STAMP_SITES],
    ids=[site for site, _, _ in STAMP_SITES],
)
def test_readme_declares_the_current_build(where: str, pattern: re.Pattern[str]) -> None:
    match = pattern.search(README.read_text(encoding="utf-8"))
    assert match is not None, (
        f"README.md has no {where}. Restore it rather than relaxing this test — it "
        "is what keeps the README honest."
    )
    assert match.group("version") == __version__, (
        f"README.md's {where} says build {match.group('version')!r} but the package "
        f"is {__version__!r}. Bump every build stamp in the README together, and "
        "record what shipped."
    )
