#!/usr/bin/env bash
#
# Prove a new test fails against the pre-change tree.
#
#   scripts/prove_against_base.sh <base-ref> <test-path>...
#
# Exports <base-ref> to a scratch directory, copies the named test files from the
# working tree over it, and runs them there. The proof SUCCEEDS when the run goes
# red: a test that still passes against the base tree is covering none of the diff.
#
# Why this script exists rather than the bare procedure it replaces (#154): the
# venv carries an editable install — a .pth in site-packages pointing at the
# working tree's src — so pytest run inside an export imports the WORKING TREE,
# not the export. The new code is already there, the new tests pass, and the run
# reports success for the wrong reason. That produced a false green three times
# (#123, #136, #153).
#
# Two steps defeat it, and both are mandatory:
#   1. PYTHONPATH=<export>/src, which precedes site-packages on sys.path.
#   2. Asserting srd_rules_engine.__file__ resolves INSIDE the export before
#      trusting the run. This is the only step that can tell a real red from a
#      false green, so the script aborts rather than reporting when it fails.
#
set -euo pipefail

if [ "$#" -lt 2 ]; then
    echo "usage: $0 <base-ref> <test-path>..." >&2
    echo "example: $0 HEAD~1 tests/test_sight.py" >&2
    exit 64
fi

BASE_REF="$1"
shift

REPO_ROOT="$(git rev-parse --show-toplevel)"
cd "$REPO_ROOT"

if ! git rev-parse --verify --quiet "${BASE_REF}^{commit}" >/dev/null; then
    echo "error: '${BASE_REF}' is not a commit this repository knows" >&2
    exit 64
fi
BASE_SHA="$(git rev-parse --short "${BASE_REF}^{commit}")"

# Prefer the venv interpreter — it is the one with pytest installed, and the one
# whose editable install this script exists to defeat.
if [ -n "${PYTHON:-}" ]; then
    PY="$PYTHON"
elif [ -x "$REPO_ROOT/.venv/bin/python" ]; then
    PY="$REPO_ROOT/.venv/bin/python"
else
    PY="python3"
fi

EXPORT_DIR="$(mktemp -d)"
trap 'rm -rf "$EXPORT_DIR"' EXIT

git archive "$BASE_REF" | tar -x -C "$EXPORT_DIR"

for test_path in "$@"; do
    if [ ! -e "$test_path" ]; then
        echo "error: '$test_path' does not exist in the working tree" >&2
        exit 64
    fi
    mkdir -p "$EXPORT_DIR/$(dirname "$test_path")"
    cp -R "$test_path" "$EXPORT_DIR/$(dirname "$test_path")/"
done

echo "base:    ${BASE_REF} (${BASE_SHA})"
echo "export:  ${EXPORT_DIR}"
echo "tests:   $*"
echo

# --- The step whose absence made three runs lie -----------------------------
# Resolve the package the way the pytest run below will resolve it, and refuse
# to report anything if it lands outside the export.
if ! RESOLVED="$(cd "$EXPORT_DIR" && PYTHONPATH="$EXPORT_DIR/src" "$PY" -c '
import os
import sys

import srd_rules_engine

sys.stdout.write(os.path.realpath(srd_rules_engine.__file__))
' 2>/dev/null)"; then
    # The package may legitimately not import on the base tree at all — that is
    # itself a red, and the pytest run below will report it.
    RESOLVED=""
fi

if [ -n "$RESOLVED" ]; then
    EXPORT_REAL="$(cd "$EXPORT_DIR" && pwd -P)"
    case "$RESOLVED" in
        "$EXPORT_REAL"/*)
            echo "import check: srd_rules_engine resolves inside the export — good"
            echo "              ${RESOLVED}"
            ;;
        *)
            echo "ABORT: srd_rules_engine resolved OUTSIDE the export." >&2
            echo "       ${RESOLVED}" >&2
            echo >&2
            echo "The run would have tested the working tree and reported the" >&2
            echo "result as though it were the base tree. This is the false green" >&2
            echo "of #154. Nothing below can be trusted, so nothing is run." >&2
            exit 70
            ;;
    esac
fi
echo

set +e
(cd "$EXPORT_DIR" && PYTHONPATH="$EXPORT_DIR/src" "$PY" -m pytest "$@" -q)
PYTEST_STATUS=$?
set -e

echo
if [ "$PYTEST_STATUS" -eq 0 ]; then
    echo "PROOF FAILED: every test passed against ${BASE_SHA}."
    echo "Those tests cover none of the diff. Either they assert behaviour the"
    echo "base tree already had, or they are asserting nothing at all."
    echo "(Deliberate \"nothing changed\" guards are the exception — say so.)"
    exit 1
fi

echo "PROOF HELD: the tests went red against ${BASE_SHA} (pytest exit ${PYTEST_STATUS})."
echo "A collection error is a legitimate red — the module under test does not"
echo "exist on the base tree."
