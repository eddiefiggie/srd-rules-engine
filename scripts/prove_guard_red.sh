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

#: How long the guarded run may take before it is treated as hung. Override with
#: PROOF_TIMEOUT for a legitimately slow suite.
#:
#: A hang is a *normal* result of a corruption proof rather than a freak event (#175):
#: corrupting a discharge, a counter or a loop bound is an ordinary way to prove a guard,
#: and each of those can turn a terminating suite into a non-terminating one.
TIMEOUT_SECONDS="${PROOF_TIMEOUT:-120}"

SNAPSHOT="$(mktemp)"
TIMED_OUT="$(mktemp)"
cp "$TARGET" "$SNAPSHOT"

PYTEST_PID=""
WATCHDOG_PID=""

# Restore on every exit path — success, failure, interrupt, or hang. This is the whole
# point of the script; nothing below is allowed to leave the tree corrupt.
#
# **Killing the children first is load-bearing** (#175). Bash defers a trap handler until
# the current foreground command returns, so when the guarded run hung, the handler was
# queued behind the very process that would not exit and the restore never ran — leaving
# the corruption in the tree, which is the failure this script exists to prevent. The run
# below is backgrounded and waited on for the same reason: `wait` is interruptible by a
# signal where a foreground command is not.
#
# **Restoring the source is not enough for a Python target**, and the gap is invisible
# (#237). CPython decides a cached `.pyc` is current by comparing the recorded source
# mtime — whole seconds — and size against the file. A corruption that changes neither, of
# which `30` -> `31` is the ordinary case, restored inside the same second the corrupt run
# compiled in, leaves a `.pyc` that still satisfies both checks. The tree then reads clean,
# `git diff` is empty, and the *engine* keeps running the corrupted constant until
# something else invalidates the cache. That is the exact failure mode this script exists
# to prevent, one layer down. Deleting the target's bytecode is decisive where touching
# the file is not.
restore() {
    for pid in "$PYTEST_PID" "$WATCHDOG_PID"; do
        [ -n "$pid" ] && kill -TERM "$pid" 2>/dev/null
    done
    cp "$SNAPSHOT" "$TARGET"
    case "$TARGET" in
        *.py)
            rm -f "$(dirname "$TARGET")/__pycache__/$(basename "$TARGET" .py)."*.pyc
            ;;
    esac
    rm -f "$SNAPSHOT" "$TIMED_OUT"
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
"$PY" -m pytest "$@" -q &
PYTEST_PID=$!

# The watchdog writes the marker *before* signalling, so a run that finishes in the same
# instant is read as finished rather than as hung.
# Redirected to /dev/null deliberately: killing this subshell does NOT kill the `sleep`
# it is blocked in, and an orphaned child holding this script's stdout keeps any pipeline
# reading it open until the sleep expires. That turns a fast proof into a two-minute one
# for anyone piping the output — which is how the first version of this fix behaved.
(
    sleep "$TIMEOUT_SECONDS"
    printf 'hung' > "$TIMED_OUT"
    kill -TERM "$PYTEST_PID" 2>/dev/null
) >/dev/null 2>&1 &
WATCHDOG_PID=$!

wait "$PYTEST_PID"
PYTEST_STATUS=$?

kill -TERM "$WATCHDOG_PID" 2>/dev/null
wait "$WATCHDOG_PID" 2>/dev/null
WATCHDOG_PID=""
PYTEST_PID=""
set -e

echo
if [ -s "$TIMED_OUT" ] && [ "$PYTEST_STATUS" -gt 128 ]; then
    echo "TIMED OUT: the guard did not finish within ${TIMEOUT_SECONDS}s against a corrupt"
    echo "${TARGET}, so it was killed."
    echo
    echo "This is NOT a proof. A run that never terminates shows the corruption broke"
    echo "something, not that the assertion you meant to test fires — and the two are"
    echo "different claims. Corrupting a discharge, a counter or a loop bound is an"
    echo "ordinary way to reach this."
    echo
    echo "Either corrupt something narrower, or raise PROOF_TIMEOUT if the suite is"
    echo "legitimately slow."
    echo "(The working tree has been restored from the snapshot.)"
    exit 124
fi

if [ "$PYTEST_STATUS" -eq 0 ]; then
    echo "PROOF FAILED: the guard stayed green against a corrupt ${TARGET}."
    echo "It is inspecting something other than what you think, or nothing."
    echo "(The working tree has been restored from the snapshot.)"
    exit 1
fi

# Only exit 1 — "tests were collected and some failed" — is a red. pytest spends 2, 3, 4
# and 5 on runs that did not happen: interrupted, internal error, bad usage, and nothing
# collected. Every one of them is a non-zero status that this script used to report as
# PROOF HELD, which made the instrument that checks whether a guard inspects anything
# capable of inspecting nothing itself. A mistyped path is the ordinary way in — quoting
# the pytest arguments as one word yields exit 4 and a confident green.
if [ "$PYTEST_STATUS" -ne 1 ]; then
    echo "NOT A PROOF: pytest exited ${PYTEST_STATUS} against a corrupt ${TARGET}."
    echo
    case "$PYTEST_STATUS" in
    2) echo "Exit 2 is an interrupted run or an error during collection. If the corruption" ;;
    3) echo "Exit 3 is an internal pytest error. If the corruption" ;;
    4) echo "Exit 4 is a usage error — most often a mistyped or mis-quoted path. If it" ;;
    5) echo "Exit 5 means no tests were collected at all. If the selector" ;;
    *) echo "That status is not one pytest spends on a failing assertion. If the run" ;;
    esac
    echo "stopped the run from happening, no assertion was ever evaluated — and a guard"
    echo "that was never run is exactly what this script exists to detect. Fix the"
    echo "invocation, or corrupt something narrower, and try again."
    echo "(The working tree has been restored from the snapshot.)"
    exit 1
fi

echo "PROOF HELD: the guard went red against a corrupt ${TARGET} (pytest exit ${PYTEST_STATUS})."
echo "(The working tree has been restored from the snapshot.)"
