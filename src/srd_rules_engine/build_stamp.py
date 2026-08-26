"""Ordering over `mmddyyyy.x` build stamps (#147).

`tests/test_build_stamp.py` checks that `__version__` and the README's two stamps *agree*.
Agreement is blind to the pair standing still together: a pull request that forgets the bump
leaves a version that never moved matching a README that never moved, and all three assertions
pass. Build `08232026.39` covered two merged pull requests that way.

This module holds the half a machine can decide — **whether one stamp is later than another** —
and nothing else. The plumbing that decides *which* two stamps to compare lives in
`scripts/check_build_stamp_advanced.py`, because it needs git and a base branch and is only
meaningful on a pull request. Splitting it here keeps the ordering rule unit-testable without a
repository, which matters: the ordering is where this is easy to get wrong.

**The stamp is not a version string and does not sort like one.** `mmddyyyy.x` is a date
followed by that day's iteration, so three comparisons a reader expects to be obvious are not:

* `08242026.9` → `08242026.10` moves **forward**. Lexicographically `"10" < "9"`.
* `08252026.1` after `08242026.11` moves **forward**. The iteration went *down*, and the
  lexicographic date `"08242026" < "08252026"` happens to be right only because the month
  is the same.
* `09012026.1` after `08312026.4` moves forward, and lexicographic date comparison agrees —
  but `12312026.1` → `01012027.1` crosses a year and lexicographic comparison says
  **backwards**. The year is the last field in `mmddyyyy`, so it cannot be compared as text.

So a stamp is ordered as `(year, month, day, iteration)`, all integers. There is no
project-wide rule that the date must be *today*; the guard asks only that it advanced.

This module takes no dependency and is importable from the core, which R33 requires of
anything shipped inside the package.
"""

from __future__ import annotations

import re
from typing import Final

#: `mmddyyyy.x` — two-digit month, two-digit day, four-digit year, then the day's iteration.
STAMP: Final = re.compile(r"^(?P<mm>\d{2})(?P<dd>\d{2})(?P<yyyy>\d{4})\.(?P<x>\d+)$")


class MalformedStamp(ValueError):
    """A string that is not a build stamp at all, which is a different fault from a stale one."""


def parse(stamp: str) -> tuple[int, int, int, int]:
    """A stamp as the tuple it sorts by: `(year, month, day, iteration)`.

    Ordering the fields this way is the whole point — see the module docstring for the three
    comparisons that go wrong when a stamp is compared as text.

    Raises `MalformedStamp` rather than returning a sentinel. A stamp nobody can parse must not
    silently compare as older than everything, which would let a typo pass the guard it exists
    to fail.
    """
    match = STAMP.match(stamp)
    if match is None:
        raise MalformedStamp(
            f"{stamp!r} is not an mmddyyyy.x build stamp. The date is two-digit month, "
            "two-digit day and four-digit year, followed by that day's iteration"
        )
    return (
        int(match["yyyy"]),
        int(match["mm"]),
        int(match["dd"]),
        int(match["x"]),
    )


def advanced(candidate: str, over: str) -> bool:
    """Whether `candidate` is a strictly later build than `over`.

    Strictly. Equal stamps are not advanced, and equality is the exact failure #147 describes —
    two pull requests each carrying the same stamp, the second one merging with a build number
    that already means something else.
    """
    return parse(candidate) > parse(over)
