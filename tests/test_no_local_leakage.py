"""Nothing about the maintainer's local machine may reach this public repository.

This is a public repo maintained from a private working tree, and the two are easy to
confuse when writing docs: a path that reads naturally in a local note ("resume at
~/Projects/foo") becomes a disclosure the moment it is pushed. Prose is where this
happens, not code — which is why this scans every tracked text file rather than only
Python.

Three categories are refused:

1. **Filesystem paths** — absolute home paths, `~/`-relative paths, and the private
   project-collection taxonomy this repo happens to live inside. They describe the
   maintainer's machine, not the project, and a reader can do nothing with them.
2. **Credentials** — token shapes and authorization headers. Nothing here should ever
   carry one; if one appears it is an accident, and an accident that must not be a push.
3. **Private contact addresses** — mail-relay and personal-webmail addresses. Commits are
   authored with GitHub's noreply address deliberately, and prose should match.

Patterns are assembled from fragments so this file does not trip its own scan.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Binary and vendored content would produce noise, not findings.
SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".zip", ".woff", ".woff2"}

# This file necessarily describes the things it forbids.
SELF = Path(__file__).name

_HOME = "/" + "Users" + "/"
_ALT_HOME = "/" + "home" + "/"
_COLLECTION = "Claude" + "Garage"

FORBIDDEN: list[tuple[str, re.Pattern[str]]] = [
    ("an absolute macOS home path", re.compile(re.escape(_HOME) + r"[A-Za-z0-9._-]+")),
    ("an absolute Linux home path", re.compile(re.escape(_ALT_HOME) + r"[A-Za-z0-9._-]+")),
    ("a home-relative path", re.compile(r"(?<![\w`/])~/[A-Za-z0-9._-]")),
    ("the maintainer's private project collection", re.compile(re.escape(_COLLECTION), re.I)),
    ("a GitHub personal access token", re.compile(r"gh[pousr]_[A-Za-z0-9]{16,}")),
    ("a fine-grained GitHub token", re.compile(r"github" + r"_pat_[A-Za-z0-9_]{20,}")),
    ("an AWS access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("an OpenAI-style secret key", re.compile(r"sk-[A-Za-z0-9]{32,}")),
    ("an Anthropic API key", re.compile(r"sk-ant-[A-Za-z0-9_-]{16,}")),
    ("a hardcoded bearer token", re.compile(r"[Aa]uthorization:\s*[Bb]earer\s+\S+")),
    (
        "a private mail-relay address",
        re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]*privaterelay\.\S+"),
    ),
    (
        "a personal webmail address",
        re.compile(r"[A-Za-z0-9._%+-]+@(gmail|icloud|outlook|hotmail|yahoo|proton(mail)?)\.\S+"),
    ),
]


def _tracked_text_files() -> list[Path]:
    out = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files", "-z"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    paths = []
    for name in out.split("\0"):
        if not name or name == f"tests/{SELF}":
            continue
        path = REPO_ROOT / name
        if path.suffix.lower() in SKIP_SUFFIXES or not path.is_file():
            continue
        paths.append(path)
    return paths


def test_git_is_available_and_files_are_tracked() -> None:
    """A scan of zero files passes vacuously, which would be worse than no scan at all."""
    files = _tracked_text_files()
    assert len(files) > 10, f"Only {len(files)} tracked files found — the scan is not running."


def test_no_local_machine_details_are_committed() -> None:
    findings: list[str] = []
    for path in _tracked_text_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        rel = path.relative_to(REPO_ROOT)
        for lineno, line in enumerate(text.splitlines(), start=1):
            for label, pattern in FORBIDDEN:
                match = pattern.search(line)
                if match:
                    findings.append(f"{rel}:{lineno} contains {label}: {match.group(0)!r}")

    assert not findings, (
        "Local-machine details must not reach this public repository:\n  "
        + "\n  ".join(findings)
        + "\n\nDescribe the project, not the machine it is built on. If a path is genuinely "
        "needed, make it relative to the repository root."
    )
