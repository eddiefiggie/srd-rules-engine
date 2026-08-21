"""The README's build line must match the package version.

Not ceremony. The README is the only place a reader learns what this build is and
what shipped in it, and a README that lags the code is worse than one that is
absent: it reads as current. Bumping the version and forgetting the README is the
single easiest mistake to make here, so it is the one thing CI refuses.
"""

from __future__ import annotations

import re
from pathlib import Path

from srd_rules_engine import __version__

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"

BUILD_LINE = re.compile(r"^\*\*Current build:\*\* `(?P<version>[^`]+)`", re.MULTILINE)
BUILD_STAMP = re.compile(r"^\d{8}\.\d+$")


def test_version_is_a_well_formed_build_stamp() -> None:
    assert BUILD_STAMP.match(__version__), (
        f"__version__ is {__version__!r}; expected the mmddyyyy.x build stamp format."
    )


def test_readme_declares_the_current_build() -> None:
    match = BUILD_LINE.search(README.read_text(encoding="utf-8"))
    assert match is not None, (
        "README.md has no '**Current build:** `mmddyyyy.x`' line. Restore it rather "
        "than relaxing this test — it is what keeps the README honest."
    )
    assert match.group("version") == __version__, (
        f"README.md says build {match.group('version')!r} but the package is "
        f"{__version__!r}. Bump the README's build line and record what shipped."
    )
