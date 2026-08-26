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

**Agreement is still blind to the pair standing still together** (#147). A pull request
that forgets the bump leaves a version that never moved matching a README that never
moved, and every assertion above passes — which is how build `08232026.39` came to cover
two merged pull requests. Catching that needs a base branch to compare against, so it
lives in `scripts/check_build_stamp_advanced.py` and runs as its own CI job. The ordering
it depends on is `srd_rules_engine.build_stamp`, and it is tested here because it is pure
and because a stamp does **not** sort like a version string.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from srd_rules_engine import __version__
from srd_rules_engine.build_stamp import MalformedStamp, advanced, parse

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


# --- Ordering (#147) ------------------------------------------------------------------
#
# `mmddyyyy.x` is a date and that day's iteration, not a version triple. Every case below is
# one a lexicographic comparison gets wrong or gets right for the wrong reason, which is why
# the ordering is a named function rather than a `>` at the call site.


def test_the_iteration_is_a_number_not_a_string() -> None:
    """`08242026.9` -> `08242026.10` moves forward. As text, `"10" < "9"`."""
    assert advanced("08242026.10", "08242026.9")
    assert not advanced("08242026.9", "08242026.10")


def test_a_new_day_restarts_the_iteration_and_still_moves_forward() -> None:
    """`08252026.1` after `08242026.11` is later, though the iteration went down. Nothing
    carries over from yesterday's count."""
    assert advanced("08252026.1", "08242026.11")
    assert not advanced("08242026.11", "08252026.1")


def test_the_year_is_the_last_field_so_text_comparison_inverts_across_one() -> None:
    """`12312026.1` -> `01012027.1` moves forward, and as text `"01012027" < "12312026"`.

    The case that makes the field order load-bearing rather than incidental: month-first
    means a plain string compare is not merely fragile here, it is backwards.
    """
    assert advanced("01012027.1", "12312026.1")
    assert not advanced("12312026.1", "01012027.1")


def test_the_same_stamp_has_not_advanced() -> None:
    """Strictly later. Equality is the exact failure #147 describes — two pull requests each
    carrying the same stamp, the second publishing a build number that already means
    something else."""
    assert not advanced(__version__, __version__)


def test_a_stamp_nobody_can_parse_raises_rather_than_sorting_last() -> None:
    """A sentinel would let a typo compare as older than everything and pass the guard it
    exists to fail."""
    for bad in ("1.2.3", "8252026.1", "08252026", "08252026.", "v08252026.1", ""):
        with pytest.raises(MalformedStamp):
            parse(bad)


def test_the_shipped_version_parses() -> None:
    """The guard reads this exact string in CI, so a malformed stamp must fail here first —
    where the message is about the format — rather than in the workflow."""
    assert parse(__version__)
