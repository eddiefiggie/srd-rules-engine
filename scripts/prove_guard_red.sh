#!/usr/bin/env bash
#
# Prove a guard fails before trusting it.
#
#   scripts/prove_guard_red.sh <target-file> <sed-expression> <pytest-arg>...
#
# Snapshots <target-file>, applies <sed-expression> to corrupt it, runs the named
# guard, and restores from the snapshot unconditionally. The proof SUCCEEDS when
# the guard goes red: a guard that stays green against a corrupt input is a guard
# that might be inspecting nothing.
#
# Why this script exists rather than "corrupt, then restore" (#155): the obvious
# restore is `git checkout -- <file>`, and it is unsafe in exactly the situation
# a corruption proof is run in — mid-change, with uncommitted work in the tree
# and usually untracked new files. It failed two ways while building #153:
#
#   1. On a file with uncommitted edits it reverts the WHOLE FILE, discarding the
#      very code the guard existed to protect. git status then shows the file
#      unmodified and the suite goes green, because what was lost was new code
#      rather than a test of it.
#   2. On an untracked file it fails outright — "pathspec did not match any
#      file(s) known to git" — leaving the corruption in the tree. That is the
#      dangerous mode here, because the corruption a guard test uses is by
#      construction the wrong value that looks right.
#
# The snapshot is a plain file copy and the restore runs from a trap, so it
# happens on success, on failure, and on interrupt, and it is correct for
# tracked, untracked, and uncommitted-edit files alike.
#
set -euo pipefail

if [ "$#" -lt 3 ]; then
    echo "usage: $0 <target-file> <sed-expression> <pytest-arg>..." >&2
    echo "example: $0 src/srd_rules_engine/core/sight.py \\" >&2
    echo "           's/^OBSCUREMENT_BY_LIGHT: .*= {}/OBSCUREMENT_BY_LIGHT = {\"darkness\": \"heavily\"}/' \\" >&2
    echo "           tests/test_sight.py" >&2
    exit 64
fi

TARGET="$1"
SED_EXPR="$2"
shift 2

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if [ ! -f "$TARGET" ]; then
    echo "error: '$TARGET' is not a file in the working tree" >&2
    exit 64
fi

# bash reads a script incrementally as it executes, so corrupting THIS file
# mid-run makes the interpreter resume into rewritten bytes and die on a syntax
# error somewhere unrelated. The trap still restores, but the guard never runs
# and the failure reads as a bug in the corruption rather than a refusal.
if [ "$(cd "$(dirname "$TARGET")" && pwd -P)/$(basename "$TARGET")" = "$(cd "$(dirname "$0")" && pwd -P)/$(basename "$0")" ]; then
    echo "error: this script cannot corrupt itself." >&2
    echo "       bash re-reads the file while running it, so the corruption would" >&2
    echo "       crash the interpreter mid-proof instead of testing the guard." >&2
    echo "       Snapshot it by hand: cp the file aside, sed the original, run the" >&2
    echo "       guard, then cp the snapshot back." >&2
    exit 64
fi

if [ -n "${PYTHON:-}" ]; then
    PY="$PYTHON"
elif [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    PY="$REPO_ROOT/.venv/bin/python"
else
    PY="python3"
fi

SNAPSHOT="$(mktemp)"
cp "$TARGET" "$SNAPSHOT"

# Restore on every exit path — success, failure, or interrupt. This is the whole
# point of the script; nothing below is allowed to leave the tree corrupt.
restore() {
    cp "$SNAPSHOT" "$TARGET"
    rm -f "$SNAPSHOT"
}
trap restore EXIT INT TERM

echo "target:  ${TARGET}"
echo "corrupt: ${SED_EXPR}"
echo "guard:   $*"
echo

# BSD and GNU sed disagree about -i, so edit through a temp file instead.
CORRUPTED="$(mktemp)"
sed "$SED_EXPR" "$TARGET" > "$CORRUPTED"

if cmp -s "$TARGET" "$CORRUPTED"; then
    rm -f "$CORRUPTED"
    echo "ABORT: the sed expression changed nothing in ${TARGET}." >&2
    echo "       A guard cannot be proven red by an input that was never" >&2
    echo "       corrupted. Fix the expression and re-run." >&2
    exit 64
fi

cp "$CORRUPTED" "$TARGET"
rm -f "$CORRUPTED"

echo "--- corruption applied, diff against the snapshot ---"
diff "$SNAPSHOT" "$TARGET" || true
echo

set +e
"$PY" -m pytest "$@" -q
PYTEST_STATUS=$?
set -e

echo
if [ "$PYTEST_STATUS" -eq 0 ]; then
    echo "PROOF FAILED: the guard stayed green against a corrupt ${TARGET}."
    echo "It is inspecting something other than what you think, or nothing."
    echo "(The working tree has been restored from the snapshot.)"
    exit 1
fi

echo "PROOF HELD: the guard went red against a corrupt ${TARGET} (pytest exit ${PYTEST_STATUS})."
echo "(The working tree has been restored from the snapshot.)"
