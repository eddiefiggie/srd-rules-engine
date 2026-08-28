"""The two verification proofs live in scripts, and the steps that make them work are pinned.

`AGENTS.md` prescribes two proofs before a change is trusted: that a new test goes red against
the pre-change tree, and that a new guard goes red against a corrupt input. Both were written as
prose, and both prescribed a procedure that does not work in this repository.

The pre-change proof (#154) was defeated by the editable install: a `.pth` in `site-packages`
points at the working tree's `src`, so `pytest` run inside an exported base tree imports the
working tree. The new code is already there, the new tests pass, and the run reports success for
the wrong reason. It produced a false green three times — #123, #136, and #153 — and the
correction lived in PR bodies each time. Nobody greps closed PRs before running a procedure the
instruction file states directly, which is the argument `AGENTS.md` already makes about plans.

The corruption proof (#155) said "then restore" as though restoring were the trivial part. The
reflex is `git checkout -- <file>`, and it is wrong in both states a corruption proof is run in:
on a file carrying an uncommitted edit it reverts the whole file and discards the new code, and
on an untracked file it fails outright and leaves the corruption in the tree.

So the knowledge moved out of prose and into `scripts/prove_against_base.sh` and
`scripts/prove_guard_red.sh`, where following it is cheaper than not. This guard exists because
that only helps while the scripts still do the thing they were written to do.

**What is pinned, and why each one.** The `__file__` assertion is the only step that can tell a
real red from a false green — #154 says so explicitly, and without it the other steps produce a
confident wrong answer rather than a visible failure. `PYTHONPATH` is what makes the export win
over the `.pth` in the first place. The unconditional restore is what makes the corruption proof
safe on an untracked file. And `AGENTS.md` must still point at both scripts, because a procedure
nobody is directed to is the failure this whole pair of issues is about.

**It matches text, not behaviour**, which is a real limit rather than a hedge: a rewrite that
keeps the words and breaks the logic passes here. The behaviour is proven by running the scripts
against a known-red and a known-green case, which is a hand step because it needs a base commit.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
AGENTS_MD = REPO_ROOT / "AGENTS.md"

PROVE_AGAINST_BASE = REPO_ROOT / "scripts" / "prove_against_base.sh"
PROVE_GUARD_RED = REPO_ROOT / "scripts" / "prove_guard_red.sh"

SCRIPTS = (PROVE_AGAINST_BASE, PROVE_GUARD_RED)


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda s: s.name)
def test_the_proof_scripts_exist(script: Path) -> None:
    """`AGENTS.md` directs the reader to each script, so each script must be there."""
    assert script.is_file(), f"{script.name} is missing; AGENTS.md prescribes running it"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda s: s.name)
def test_the_proof_scripts_are_executable(script: Path) -> None:
    """Prescribed as `scripts/<name>.sh ...`, which needs the bit set."""
    assert os.access(script, os.X_OK), f"{script.name} is not executable"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda s: s.name)
def test_agents_md_points_at_each_script(script: Path) -> None:
    """A procedure nobody is directed to is the failure #154 and #155 are about."""
    relative = f"scripts/{script.name}"
    assert relative in AGENTS_MD.read_text(), (
        f"AGENTS.md no longer names {relative}, so the procedure is prose again"
    )


def test_the_base_proof_still_asserts_where_the_package_resolved() -> None:
    """The one step that separates a real red from a false green (#154).

    Without this the script runs, imports the working tree, and reports a pass that means
    nothing. Every other step can be wrong and still fail visibly; this one cannot.
    """
    source = PROVE_AGAINST_BASE.read_text()
    assert "srd_rules_engine.__file__" in source, (
        "prove_against_base.sh no longer resolves srd_rules_engine.__file__; "
        "it can no longer tell a real red from the false green of #154"
    )
    assert "ABORT" in source, (
        "prove_against_base.sh no longer aborts on a resolution outside the export"
    )


def test_the_base_proof_still_sets_pythonpath_to_the_export() -> None:
    """What makes the export win over the editable install's `.pth` (#154)."""
    source = PROVE_AGAINST_BASE.read_text()
    assert 'PYTHONPATH="$EXPORT_DIR/src"' in source, (
        "prove_against_base.sh no longer puts the export on PYTHONPATH, so pytest "
        "will import the working tree through the editable install"
    )


def test_the_guard_proof_restores_unconditionally() -> None:
    """The restore must survive failure and interrupt, or #155 mode 2 returns.

    A corruption left behind is worse than a lost proof: the value a guard test uses is by
    construction the wrong value that looks right.
    """
    source = PROVE_GUARD_RED.read_text()
    assert "trap restore EXIT INT TERM" in source, (
        "prove_guard_red.sh no longer restores on every exit path; a failed or "
        "interrupted proof can now leave the corruption in the tree (#155)"
    )


def test_the_guard_proof_invalidates_bytecode_when_it_restores() -> None:
    """Restoring the source is not enough, and the shortfall is invisible.

    CPython treats a cached `.pyc` as current when the source mtime it recorded — whole
    seconds — and the source size both still match. A corruption that changes neither, of
    which `30` -> `31` is the ordinary case, restored inside the same second the corrupt run
    compiled in, satisfies both checks. `git diff` is then empty, the script reports the
    tree restored, and **the engine goes on running the corrupted constant**.

    That is this script's own failure mode reappearing one layer down, and it is worse than
    the version #155 fixed: there, the corruption was at least visible in the tree.

    Found by proving the Concentration DC cap red for #215 and watching the full suite fail
    afterwards on a file `git` reported as clean.
    """
    source = PROVE_GUARD_RED.read_text()
    assert "__pycache__" in source, (
        "prove_guard_red.sh no longer deletes the restored module's bytecode. A same-size "
        "corruption restored within the same second leaves a stale .pyc that CPython "
        "considers current, so the engine keeps running the corrupt value"
    )


def test_the_guard_proof_refuses_to_corrupt_itself() -> None:
    """Found by running the proof on the proof, which is how it should be found.

    bash reads a script incrementally as it executes, so corrupting `prove_guard_red.sh`
    while it is running makes the interpreter resume into rewritten bytes and die on a
    syntax error somewhere unrelated. The trap still restored the file correctly — but the
    guard never ran, and the failure reads as a broken corruption rather than a refusal.
    Refusing up front is the difference between a clear message and a confusing one.
    """
    source = PROVE_GUARD_RED.read_text()
    assert "cannot corrupt itself" in source, (
        "prove_guard_red.sh no longer refuses itself as a target; corrupting it mid-run "
        "crashes the interpreter instead of testing the guard"
    )


def test_the_guard_proof_survives_a_hang() -> None:
    """#175. The restore must outlive a guarded run that never returns.

    Bash defers a trap handler until the current foreground command returns, so when the
    guarded run hung, the handler was queued behind the very process that would not exit —
    and the corruption stayed in the tree. That is the failure this script exists to
    prevent, reached by a route its first version did not cover.

    Three things have to hold together, so all three are pinned: the run is backgrounded
    (a foreground command cannot be interrupted), it is watched (nothing else would notice),
    and the trap kills the children before restoring (or it waits on the hang itself).
    """
    source = PROVE_GUARD_RED.read_text()
    assert "PROOF_TIMEOUT" in source, (
        "prove_guard_red.sh no longer bounds the guarded run, so a corruption that hangs "
        "the suite leaves itself in the tree (#175)"
    )
    assert 'wait "$PYTEST_PID"' in source, (
        "the guarded run is no longer waited on in the background; a foreground command "
        "defers the trap until it returns, which is the whole of #175"
    )
    assert 'kill -TERM "$pid"' in source, (
        "the trap no longer kills the guarded run before restoring, so it queues behind "
        "the process that would not exit"
    )


def test_a_timeout_is_not_reported_as_a_proof() -> None:
    """A run that never terminates shows the corruption broke something — not that the
    assertion under test fires. Reporting it as PROOF HELD would be the script agreeing
    with itself, which is the shape every guard here exists to avoid."""
    source = PROVE_GUARD_RED.read_text()
    assert "TIMED OUT" in source
    assert "NOT a proof" in source
    assert "exit 124" in source, "a timeout must be distinguishable from a red by exit code"


def test_agents_md_forbids_the_unsafe_restore() -> None:
    """`git checkout -- <file>` is the reflex, and it is what #155 was filed about."""
    text = AGENTS_MD.read_text()
    assert "Never restore with `git checkout -- <file>`" in text, (
        "AGENTS.md no longer warns against git checkout as the restore; that is the "
        "reflex that discarded uncommitted work and left a corruption in place (#155)"
    )
