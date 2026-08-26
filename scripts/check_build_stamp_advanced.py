#!/usr/bin/env python3
"""Fail when a pull request's build stamp has not advanced past the base branch (#147).

    scripts/check_build_stamp_advanced.py [base-ref]

`base-ref` defaults to `origin/main`. Exits 0 when the working tree's `__version__` is a
strictly later stamp than the one at `base-ref`, and non-zero with the two stamps named
otherwise.

## Why this is not a pytest test

It needs git, a base branch, and a network fetch to be meaningful, and it answers nothing at
all on `main` itself or in a clone with no remote. A test that skipped in every one of those
cases would be a guard inspecting nothing for most of its life, which is the failure mode this
repository names most often. So the ordering rule — the part that is pure and where the
mistakes actually are — lives in `srd_rules_engine.build_stamp` and is unit-tested there, and
this file is the plumbing that runs in CI on a pull request and nowhere else.

## The base branch TIP, not the merge base

[#147](https://github.com/eddiefiggie/srd-rules-engine/issues/147) proposed comparing against
"its value on the merge base". **That does not catch the collision.** It was tried on the day
this was written and would have passed both halves of it:

    main                    ...  #207 (.30)  ──  #208 (.31)  ──  #210 (.32)
                                       │
    branch for #208 ───────────────────┤  bumped .30 → .31   merge base .30, advanced ✓
    branch for #210 ───────────────────┘  bumped .30 → .31   merge base .30, advanced ✓

Both branched from `.30` and both bumped to `.31`. Each advanced past its own merge base, so a
merge-base guard is green on both — and the second one to merge publishes a `.31` that already
means a different build. The question is not "did this branch move" but "is this stamp free",
and only the base branch **tip at merge time** answers it.

That leaves one gap this cannot close, and it is disclosed rather than papered over: CI re-runs
when the *pull request* is pushed to, not when `main` moves underneath it. A branch that passed
this check and then sat while another merged is stale, and only re-running makes it visible.
The repository-side fix is GitHub's "Require branches to be up to date before merging", which
is a branch-protection setting and not something this script can assert.

## The shallow-clone wrinkle

`actions/checkout` fetches depth 1 by default, so `origin/main` is not present and `git show`
against it fails with a message about an unknown revision rather than about a build stamp. The
workflow fetches the base branch explicitly; this script says so when the ref is missing, so the
failure is legible when someone copies the step and drops the fetch.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = "src/srd_rules_engine/__init__.py"
VERSION_LINE = re.compile(r'^__version__ = "(?P<version>[^"]+)"', re.MULTILINE)

DEFAULT_BASE = "origin/main"

sys.path.insert(0, str(REPO_ROOT / "src"))

from srd_rules_engine.build_stamp import MalformedStamp, advanced  # noqa: E402


def _version_in(text: str, where: str) -> str:
    match = VERSION_LINE.search(text)
    if match is None:
        raise SystemExit(f'{where} has no `__version__ = "..."` line to read')
    return match["version"]


def base_version(base_ref: str) -> str:
    """The stamp at the tip of the base branch, read through git rather than the filesystem."""
    result = subprocess.run(
        ["git", "show", f"{base_ref}:{VERSION_FILE}"],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"cannot read {VERSION_FILE} at {base_ref!r}: {result.stderr.strip()}\n\n"
            "If this is CI, the checkout is probably shallow and the base branch was never "
            "fetched — `git fetch --depth=1 origin main:refs/remotes/origin/main` before "
            "running this."
        )
    return _version_in(result.stdout, f"{VERSION_FILE} at {base_ref}")


def working_version() -> str:
    return _version_in((REPO_ROOT / VERSION_FILE).read_text(encoding="utf-8"), VERSION_FILE)


def main(argv: list[str]) -> int:
    base_ref = argv[1] if len(argv) > 1 else DEFAULT_BASE
    base = base_version(base_ref)
    here = working_version()

    try:
        moved = advanced(here, base)
    except MalformedStamp as exc:
        raise SystemExit(str(exc)) from None

    if not moved:
        verb = "is the same build as" if here == base else "is older than"
        raise SystemExit(
            f"the build stamp did not advance: this branch is {here!r} and {base_ref} "
            f"{verb} it at {base!r}.\n\n"
            "AGENTS.md asks for a bump on every pull request, and the README's build line is "
            "the build record — there is no changelog to fall back on, so a stamp that stands "
            "still loses the record of what shipped. Bump `__version__` and both README "
            "stamps together, and say what actually shipped.\n\n"
            "If the base moved under you after you branched, rebase: your bump has to be free "
            "at merge time, not merely later than where you started."
        )

    print(f"  ok  build stamp advanced: {base} ({base_ref}) -> {here}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
