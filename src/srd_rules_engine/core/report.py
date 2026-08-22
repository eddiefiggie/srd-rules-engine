"""Replay (R28) and the session-review report (R30), both derived from the ledger alone.

These are the instruments the product is measured with, so they are built to be unable to
flatter it. Two design choices carry that:

**Replay re-derives the roll from the recorded seed; it does not recompute from the
recorded dice.** Trusting the recorded dice would make replay agree with the ledger by
construction — it would reproduce the arithmetic and nothing else, and a change to the die
derivation would sail through. Re-rolling from the seed is what makes a replay a check
rather than a restatement.

**Replay takes no memory port, so R28's "without re-querying the port" is not a rule to
follow but a call that cannot be written.** The resolved fact values are on the entry; a
port lookup at replay time would read *today's* memory into *yesterday's* outcome, and the
result would look like a successful replay.

## What a replay can say

A mismatch under the *same* engine version is a real problem — the engine no longer
reproduces its own record. A mismatch under a *different* engine version is a rules fix
doing its job, so it yields a reconciliation naming both versions and both outcomes and is
never an integrity verdict (R28). And an entry whose record is too thin to reconstruct is
**unreplayable**, reported as such rather than replayed under an assumption: a ruling made
with advantage, replayed as though it had none, would roll one die where two were rolled
and report a mismatch indistinguishable from real drift.

## What the report can say

R30's flags all describe a session that *ran* — they are only meaningful once the ledger is
known intact, so integrity is verified first and a corrupted ledger is reported as
corrupted rather than summarised. The alternative is the worst outcome available here: a
tidy per-turn table computed from entries that do not chain, which reads exactly like a
clean session.

A turn that ended without a Ruling is excluded from the Ruling-with-no-narration check,
because there was no Ruling to narrate. Flagging it twice would inflate the number the
primary success criterion is read from, in the flattering direction.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any, Final

from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.d20 import resolve as roll_d20
from srd_rules_engine.core.ledger import SESSION
from srd_rules_engine.core.ledger_reader import Entry, LedgerReport, read_ledger
from srd_rules_engine.core.read_surface import Verdict

#: The ruling payload version from which a roll records the advantage it was declared
#: under. Below it the test cannot be reconstructed, and replay says so.
REPLAYABLE_FROM: Final = 2

RULING_TYPES: Final = frozenset({"ruling", "challenge", "rejection"})
TERMINATION: Final = "exhaustion"


class ReplayVerdict(StrEnum):
    """What a replay can conclude. Only one of these is an integrity finding."""

    IDENTICAL = "identical"
    DIVERGED = "diverged"
    RECONCILIATION = "reconciliation"
    UNREPLAYABLE = "unreplayable"


class Flag(StrEnum):
    """R30's flags. Named so a report can be counted rather than read."""

    NARRATION_WITHOUT_RULING = "narration-without-ruling"
    RULING_WITHOUT_NARRATION = "ruling-without-narration"
    CHALLENGE_NEVER_READJUDICATED = "challenge-never-re-adjudicated"
    ALTERNATIVES_NOT_FRESH = "alternatives-not-fresh"
    TERMINATED = "terminated"


@dataclass(frozen=True)
class Replay:
    """One entry, replayed. `verdict` is the whole answer; the rest explains it."""

    seq: int
    verdict: ReplayVerdict
    detail: str
    recorded_engine: str | None = None
    replay_engine: str | None = None
    recorded_total: int | None = None
    replayed_total: int | None = None
    recorded_succeeded: bool | None = None
    replayed_succeeded: bool | None = None

    @property
    def reproduced(self) -> bool:
        return self.verdict is ReplayVerdict.IDENTICAL

    @property
    def is_integrity_failure(self) -> bool:
        """A reconciliation is not one. A rules fix is not corruption (R28)."""
        return self.verdict is ReplayVerdict.DIVERGED


@dataclass(frozen=True)
class Turn:
    """One declaration slot as the ledger recorded it."""

    seq: int
    actor: str
    action_key: str | None
    improvised: bool
    rule_id: str | None
    #: How many declarations the slot took. More than one means a refusal was answered.
    attempts: int = 1
    alternatives: tuple[Mapping[str, object], ...] = ()
    alternatives_verdict: str | None = None
    status: str | None = None
    outcome: str | None = None
    narration: str | None = None
    terminal_reason: str | None = None
    flags: tuple[Flag, ...] = ()

    @property
    def produced_ruling(self) -> bool:
        return self.status == "ruled"


@dataclass(frozen=True)
class SessionReport:
    """R30. Corrupted or intact — and when corrupted, it says only that."""

    path: Path
    corrupted: bool
    engine_version: str | None = None
    catalogue_version: int | None = None
    session_id: str | None = None
    turns: tuple[Turn, ...] = ()
    orphan_narrations: int = 0
    findings: tuple[str, ...] = field(default=())

    @property
    def flags(self) -> tuple[tuple[int, Flag], ...]:
        return tuple((turn.seq, flag) for turn in self.turns for flag in turn.flags)

    def flagged(self, flag: Flag) -> tuple[Turn, ...]:
        return tuple(turn for turn in self.turns if flag in turn.flags)


# --- Replay -----------------------------------------------------------------------------


def replay_entry(entry: Entry, *, engine_version: str, recorded_engine: str | None) -> Replay:
    """Re-derive one ruling from its recorded seed and inputs. Takes no memory port.

    R28's "without re-querying the port" is settled by the signature: there is no port to
    query. A lookup here would read today's memory into yesterday's outcome and the
    disagreement would surface as a replay that *passed*.
    """
    roll = entry.payload.get("roll")
    if entry.type not in RULING_TYPES or not isinstance(roll, Mapping):
        return Replay(
            seq=entry.seq,
            verdict=ReplayVerdict.UNREPLAYABLE,
            detail=f"a {entry.type!r} entry carries no roll to replay",
        )

    test = _test_from(roll)
    if test is None:
        return Replay(
            seq=entry.seq,
            verdict=ReplayVerdict.UNREPLAYABLE,
            detail=(
                f"the roll records no advantage, so the test cannot be reconstructed "
                f"(ruling payload v{entry.v}; replayable from v{REPLAYABLE_FROM}). "
                "Replaying it as though it had none would roll the wrong number of dice"
            ),
        )

    seed = roll.get("seed")
    if not isinstance(seed, int) or isinstance(seed, bool):
        return Replay(
            seq=entry.seq,
            verdict=ReplayVerdict.UNREPLAYABLE,
            detail="the roll records no usable seed",
        )

    reproduced = roll_d20(test, seed=seed)
    recorded_total = _int(roll.get("total"))
    recorded_succeeded = roll.get("succeeded")
    recorded_succeeded = recorded_succeeded if isinstance(recorded_succeeded, bool) else None
    recorded_dice = [d for d in _sequence(roll.get("dice")) if isinstance(d, int)]

    def verdict(kind: ReplayVerdict, detail: str) -> Replay:
        return Replay(
            seq=entry.seq,
            verdict=kind,
            detail=detail,
            recorded_engine=recorded_engine,
            replay_engine=engine_version,
            recorded_total=recorded_total,
            replayed_total=reproduced.total,
            recorded_succeeded=recorded_succeeded,
            replayed_succeeded=reproduced.succeeded,
        )

    if (
        reproduced.total == recorded_total
        and reproduced.succeeded == recorded_succeeded
        and list(reproduced.dice) == recorded_dice
    ):
        return verdict(ReplayVerdict.IDENTICAL, "reproduced exactly")

    if recorded_engine != engine_version:
        # R28: a rules fix is not corruption. Name both versions and both outcomes, and
        # stop — deciding which is *right* needs the change, not the ledger.
        return verdict(
            ReplayVerdict.RECONCILIATION,
            f"recorded under engine {recorded_engine!r} and replayed under "
            f"{engine_version!r}: {recorded_total} then {reproduced.total}. A differing "
            "engine version is a rules change, not an integrity finding",
        )

    return verdict(
        ReplayVerdict.DIVERGED,
        f"engine {engine_version!r} no longer reproduces its own record: "
        f"{recorded_total} then {reproduced.total}",
    )


def replay(report: LedgerReport, *, engine_version: str) -> tuple[Replay, ...]:
    """Replay every ruling in a ledger, each against the engine version governing it."""
    governing: str | None = None
    replays: list[Replay] = []
    for entry in report.entries:
        if entry.type == SESSION:
            governing = _text(entry.payload.get("engine_version"))
            continue
        if entry.type in RULING_TYPES:
            replays.append(
                replay_entry(entry, engine_version=engine_version, recorded_engine=governing)
            )
    return tuple(replays)


def _test_from(roll: Mapping[str, object]) -> D20Test | None:
    """Rebuild the test, or None when the record is too thin to rebuild it honestly."""
    advantage = roll.get("declared_advantage")
    disadvantage = roll.get("declared_disadvantage")
    if not isinstance(advantage, bool) or not isinstance(disadvantage, bool):
        return None

    kind = _text(roll.get("kind"))
    target = roll.get("target")
    basis = _text(roll.get("target_basis"))
    if kind is None or basis is None or not isinstance(target, int) or isinstance(target, bool):
        return None

    try:
        return D20Test(
            kind=TestKind(kind),
            target=target,
            target_basis=basis,
            modifiers=tuple(
                Modifier(source=str(m["source"]), value=int(m["value"]))
                for m in _sequence(roll.get("modifiers"))
                if isinstance(m, Mapping)
            ),
            has_advantage=advantage,
            has_disadvantage=disadvantage,
        )
    except (ValueError, KeyError, TypeError):
        return None


# --- The session-review report -----------------------------------------------------------


def session_report(path: Path | str) -> SessionReport:
    """R30. Verify integrity first, then summarise — never the other way round."""
    return report_from(read_ledger(path))


def report_from(ledger: LedgerReport) -> SessionReport:
    """The report, from an already-read ledger.

    Integrity comes first because every flag below describes a session that ran. Computing
    a per-turn table over entries that do not chain would produce the most dangerous
    artifact available here: one that looks like a clean session.
    """
    session = next((e for e in ledger.entries if e.type == SESSION), None)
    header: dict[str, Any] = {
        "engine_version": _text(session.payload.get("engine_version")) if session else None,
        "catalogue_version": _int(session.payload.get("catalogue_version")) if session else None,
        "session_id": _text(session.payload.get("session_id")) if session else None,
    }

    if not ledger.intact:
        return SessionReport(
            path=ledger.path,
            corrupted=True,
            findings=tuple(f"{f.kind} at line {f.line}: {f.detail}" for f in ledger.findings),
            **header,
        )

    turns, orphans = _turns(ledger.entries)
    return SessionReport(
        path=ledger.path, corrupted=False, turns=turns, orphan_narrations=orphans, **header
    )


def _turns(entries: Sequence[Entry]) -> tuple[tuple[Turn, ...], int]:
    """Walk the ledger in order, pairing each *declaration slot* with what followed it.

    A slot is not one declaration. The loop re-declares after a refusal, so a challenge
    answered by a corrected declaration is one slot with two attempts — and reading each
    declaration as its own turn would report every answered challenge as never answered,
    which is the flag saying the opposite of what happened.

    A slot closes on a Ruling, on a termination, or when a different actor declares.
    """
    turns: list[Turn] = []
    pending: dict[str, Any] | None = None
    orphans = 0

    def close() -> None:
        nonlocal pending
        if pending is not None:
            turns.append(_finish(pending))
            pending = None

    def declaration_fields(entry: Entry) -> dict[str, Any]:
        intent = entry.payload.get("intent")
        intent = intent if isinstance(intent, Mapping) else {}
        return {
            "action_key": _text(intent.get("action_key")),
            "improvised": bool(intent.get("improvised")),
            "rule_id": _text(entry.payload.get("rule_id")),
            "alternatives": tuple(
                a for a in _sequence(entry.payload.get("alternatives")) if isinstance(a, Mapping)
            ),
        }

    for entry in entries:
        if entry.type == "declaration":
            actor = _text(entry.payload.get("actor")) or ""
            settled = pending is not None and (
                pending.get("status") == "ruled" or pending.get("terminal_reason") is not None
            )
            if pending is not None and (settled or pending["actor"] != actor):
                close()
            if pending is None:
                pending = {
                    "seq": entry.seq,
                    "actor": actor,
                    "attempts": 1,
                    "statuses": [],
                    "verdicts": [],
                    **declaration_fields(entry),
                }
            else:
                # The same slot again. Count it as an *attempt* only if the agent was asked
                # again — a block is a suspension, so the loop re-adjudicates the same
                # declaration once the facts arrive and the agent is never re-consulted.
                # Counting that as a retry would report a driver's omission as an agent
                # failing to declare correctly, which is the opposite attribution.
                # The duplicate declaration entry a resumption leaves behind is #59.
                if pending.get("status") != "blocked":
                    pending["attempts"] += 1
                pending["status"] = None
                pending.update(declaration_fields(entry))
        elif entry.type in RULING_TYPES and pending is not None:
            status = _text(entry.payload.get("status"))
            pending["statuses"].append(status)
            pending["status"] = status
            pending["verdicts"].append(_text(entry.payload.get("alternatives_verdict")))
            roll = entry.payload.get("roll")
            if isinstance(roll, Mapping):
                pending["outcome"] = _text(roll.get("derivation"))
        elif entry.type == "narration":
            # R30 flags a narration with no *Ruling*, and a challenge or a rejection is not
            # one — the engine refused and reached no outcome. Prose describing an outcome
            # that was never reached is the original defect, inside the product's own record.
            if pending is None or pending.get("status") != "ruled":
                orphans += 1
                if pending is not None:
                    pending["orphan_narration"] = True
            else:
                pending["narration"] = _text(entry.payload.get("text"))
        elif entry.type == TERMINATION and pending is not None:
            pending["terminal_reason"] = _text(entry.payload.get("reason"))

    close()
    return tuple(turns), orphans


def _finish(pending: Mapping[str, Any]) -> Turn:
    """Assign R30's flags to one closed slot."""
    status = pending.get("status")
    terminal = pending.get("terminal_reason")
    statuses: Sequence[str | None] = pending.get("statuses") or ()
    verdicts: Sequence[str | None] = pending.get("verdicts") or ()
    # Any declaration in the slot, not only the last: an agent that claimed a stale menu
    # and then corrected itself still made the claim, and the record should say so.
    stale = next((v for v in verdicts if v is not None and v != str(Verdict.FRESH)), None)

    flags: list[Flag] = []
    if pending.get("orphan_narration"):
        flags.append(Flag.NARRATION_WITHOUT_RULING)
    if terminal is not None:
        flags.append(Flag.TERMINATED)
    # Only a slot that produced a Ruling can owe a narration, and `status == "ruled"` is
    # the whole of R30's exclusion: a terminated slot ends challenged, rejected, or
    # blocked, never ruled. Adding `terminal is None` beside it would read as a second
    # guard while testing nothing, which is worse than no guard — it invites the reader to
    # believe the exclusion is enforced twice.
    if status == "ruled" and pending.get("narration") is None:
        flags.append(Flag.RULING_WITHOUT_NARRATION)
    if "challenged" in statuses and statuses[-1] == "challenged" and terminal is None:
        flags.append(Flag.CHALLENGE_NEVER_READJUDICATED)
    if stale is not None:
        flags.append(Flag.ALTERNATIVES_NOT_FRESH)

    return Turn(
        seq=int(pending["seq"]),
        actor=str(pending["actor"]),
        action_key=pending.get("action_key"),
        improvised=bool(pending.get("improvised")),
        rule_id=pending.get("rule_id"),
        attempts=int(pending.get("attempts") or 1),
        alternatives=tuple(pending.get("alternatives") or ()),
        alternatives_verdict=stale or (verdicts[-1] if verdicts else None),
        status=status,
        outcome=pending.get("outcome"),
        narration=pending.get("narration"),
        terminal_reason=terminal,
        flags=tuple(flags),
    )


def render(report: SessionReport) -> str:
    """The report as text. A corrupted ledger renders its findings and nothing else."""
    if report.corrupted:
        lines = [f"SESSION REVIEW — {report.path.name}", "", "CORRUPTED. Not summarised."]
        return "\n".join([*lines, *(f"  - {f}" for f in report.findings)])

    header = [
        f"SESSION REVIEW — {report.session_id or 'unnamed session'}",
        f"  engine version:    {report.engine_version or 'unrecorded'}",
        f"  catalogue version: {report.catalogue_version if report.catalogue_version else '—'}",
        f"  turns:             {len(report.turns)}",
        f"  flags:             {len(report.flags)}",
        "",
    ]
    body: list[str] = []
    for turn in report.turns:
        named = turn.action_key or (turn.rule_id and f"rule {turn.rule_id}") or "improvised"
        retries = f" after {turn.attempts - 1} refused" if turn.attempts > 1 else ""
        body.append(
            f"seq {turn.seq} — {turn.actor}: {named} [{turn.status or 'no ruling'}]{retries}"
        )
        if turn.outcome:
            body.append(f"    {turn.outcome}")
        if turn.narration:
            body.append(f'    "{turn.narration}"')
        if turn.terminal_reason:
            body.append(f"    ended: {turn.terminal_reason}")
        body.extend(f"    FLAG {flag}" for flag in turn.flags)
    return "\n".join(header + body)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _sequence(value: object) -> Sequence[object]:
    """A payload list, or nothing. A ledger is parsed data, so its shape is never assumed."""
    return value if isinstance(value, list | tuple) else ()
