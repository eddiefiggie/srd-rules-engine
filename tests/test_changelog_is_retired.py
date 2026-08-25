"""Nothing may promise a changelog entry, because there is no changelog to enter it in.

`CHANGELOG.md` is retired and frozen at build `08232026.36`
([0024](../docs/decisions/0024-the-build-line-is-the-build-record.md), #146). README's
`**Current build:**` line is the build record.

The reason #146 happened is worth restating here, because this guard exists to stop it
recurring in reverse. The obligation to update the changelog lived in exactly one place — an
unenforced checkbox in the pull-request template — and it went green through fifteen merged
PRs while the file sat untouched. A rule with nothing behind it is a rule the repository
breaks silently. Retiring the file and leaving the promises pointing at it would reproduce
that shape exactly: a dead venue, still promised.

Two of those promises were load-bearing rather than decorative. `stability.py` told a
consumer of the Provisional surface — the MCP tool names, the CLI commands, the HTTP routes —
that a change there "is recorded in the changelog", which is the whole compensation for that
tier raising no `API_VERSION`. The plan's M1 acceptance criteria listed the file beside the
build stamp. Neither would have failed a test.

**Where this looks, and where it deliberately does not.** Obligations live in code, in the
templates that prompt an author, in the plan, and in the two instruction files. Not in
`docs/decisions/`: records are immutable by rule, so [0018](../docs/decisions/0018-api-stability.md)
still reads "recorded in the changelog" and correctly describes what was decided at the time —
0024 amends the venue and the trail is the point. `CHANGELOG.md` itself is exempt because it
describes its own retirement.

**It matches phrasings, not meaning**, and that is a real limit rather than a hedge: a new way
of writing the same promise passes. It is red against the pre-change tree on all three live
obligations that existed when it was written, which is the evidence that the pattern set is
worth what it claims — not proof that it is complete.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Where a live obligation could be written. `docs/decisions/` is immutable history and
#: `CHANGELOG.md` describes its own retirement; both are exempt by design, not oversight.
SEARCHED = (
    REPO_ROOT / "src",
    REPO_ROOT / ".github",
    REPO_ROOT / "docs" / "plans",
    REPO_ROOT / "AGENTS.md",
    REPO_ROOT / "CONTRIBUTING.md",
)

SKIP_DIRS = {"__pycache__", ".ruff_cache", ".mypy_cache", ".pytest_cache"}

#: This file necessarily quotes the phrasings it forbids.
SELF = Path(__file__).name

#: A promise that some change gets written down in the retired file. Each pattern is one that
#: existed in the tree, or the obvious variant of one.
FORBIDDEN: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("a change recorded in the changelog", re.compile(r"(?i)recorded in the changelog")),
    ("a changelog entry as an obligation", re.compile(r"(?i)\bis a changelog entry\b")),
    ("adding a changelog entry", re.compile(r"(?i)add(?:s|ed|ing)? (?:an? )?changelog entry")),
    ("CHANGELOG.md recording a build", re.compile(r"(?i)`?CHANGELOG\.md`? records\b")),
    ("updating CHANGELOG.md", re.compile(r"(?i)updat(?:e|es|ed|ing) `?CHANGELOG\.md`?")),
)


def _searched_files() -> list[Path]:
    found: list[Path] = []
    for target in SEARCHED:
        if target.is_file():
            found.append(target)
            continue
        for path in target.rglob("*"):
            if path.is_file() and not SKIP_DIRS.intersection(path.parts):
                found.append(path)
    return found


def test_the_search_covers_the_places_an_obligation_lives() -> None:
    """A path that stops existing turns this guard into one that inspects nothing."""
    missing = [t.name for t in SEARCHED if not t.exists()]
    assert not missing, f"searched paths that no longer exist: {missing}"
    assert len(_searched_files()) > 50, "the file walk found almost nothing; check SKIP_DIRS"


def test_nothing_promises_a_changelog_entry() -> None:
    hits: list[str] = []
    for path in _searched_files():
        if path.name == SELF:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue  # Not prose, so not a promise.
        for what, pattern in FORBIDDEN:
            for match in pattern.finditer(text):
                line = text[: match.start()].count("\n") + 1
                hits.append(f"{path.relative_to(REPO_ROOT)}:{line} — {what}: {match.group(0)!r}")
    assert not hits, (
        "CHANGELOG.md is retired (0024, #146); these still promise an entry in it:\n  "
        + "\n  ".join(hits)
        + "\nRecord the change in README's '**Current build:**' line instead."
    )
