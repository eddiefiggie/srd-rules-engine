"""A command-line adapter over the turn loop (R34, #133).

## This is not `HumanCliDriver`, and the pair is easy to confuse

`loop.drivers.HumanCliDriver` is R8's reference **driver**: it answers the loop's typed
requests directly, and it is what you use when a person is playing. This is R34's **adapter**:
a transport binding over `adapters.Session`, the same layer `adapters.mcp` occupies, for a
consumer that drives the engine by issuing commands rather than by being handed questions.

The difference is who is in control. A driver is *called by* the loop as it runs; an adapter
*holds* a suspended loop between calls and answers what it is waiting for. Decision 0016 is
why the second exists at all: a stateless caller cannot resume a generator unless something
holds it.

Both can be pointed at a terminal, which is the whole source of the confusion — and why the
status table in `README.md` counts one of R34's three adapters rather than two.

## The session is held for the process, because that is what a turn needs

`run()` is a command loop rather than a one-shot `argv` parser, and that is forced rather
than chosen. A `Session` holds a suspended generator; a process that exits between commands
loses the position within a turn — a challenge awaiting a re-declaration, or a ruling
awaiting its narration. One-shot invocation would make every command its own session and
every turn a single step, which is not a turn.

What is lost on exit is disclosed by 0016 and unchanged here: the ledger survives, because
entries are durable before anything escapes the engine (0002), and a fresh session's R29
narration debt is what notices anything left dangling.

## The commands, and the ones that are absent

| Command | What it does |
|---|---|
| `look <actor>` | What is legal, and the actor's situation. Mutates nothing (R19). |
| `begin <actor>` | Opens a turn and reports the first question. |
| `declare ...` | Answers a declaration request. May come back challenged or rejected. |
| `narrate <text>` | Pays R29's narration debt. Bare `narrate` withholds it, which is
  recorded rather than forbidden. |
| `end_turn <actor>` | Resolves the obligations the turn's end incurs (0023). |
| `facts` | Answers a blocked declaration. Not wired — see below. |
| `report` | The session review, derived from the ledger. |

**No command reaches adjudication.** `adapters.surface.FORBIDDEN_COMMAND_NAMES` names what
must never appear here and a test asserts it over every adapter at once.

**No command waives an end-of-turn obligation.** `EncounterState.advanced_turn` takes
`waive_obligations=True` for a consumer that legitimately wants to fast-forward; exposing it
here would put a documented, supported way to skip a compulsory save in front of the caller
the challenge mechanism exists to constrain. Same reasoning as the MCP adapter, and the same
answer.

## There is no `srd` executable, and there cannot be one yet

This is a library-level binding: a consumer constructs the `Adjudicator`, the `Session` and
this adapter, then calls `run()`. No `[project.scripts]` entry ships, and adding one would be
premature rather than convenient — a console script has to pick a ruleset, and the only rules
this library ships are `core.save_ends`'s fifteen. There is nothing to play. That is
[#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21)'s territory, not this
adapter's, and an executable that started a session with an almost-empty ruleset would look
like a broken game rather than an absent one.

It also takes no dependency. R33 keeps `[project].dependencies` empty and every transport is
an extra; this one needs nothing beyond the standard library, so it has no extra either.

**`facts` is declared and raises.** Wiring it needs the memory port's typed value
constructor, exactly as it does over MCP. A command that fails loudly beats one quietly
missing from the list a consumer plans against.
"""

from __future__ import annotations

import shlex
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, assert_never

from srd_rules_engine.adapters.session import (
    AwaitingDeclaration,
    AwaitingFacts,
    AwaitingNarration,
    Finished,
    Pending,
    Session,
    TurnEnded,
)
from srd_rules_engine.core import Declaration, Intent, session_report
from srd_rules_engine.core import render as render_report

#: Command names, in one place so the loop and its tests cannot disagree about them.
LOOK = "look"
BEGIN = "begin"
DECLARE = "declare"
NARRATE = "narrate"
END_TURN = "end_turn"
FACTS = "facts"
REPORT = "report"
HELP = "help"
QUIT = "quit"

COMMAND_NAMES: Final[tuple[str, ...]] = (
    LOOK,
    BEGIN,
    DECLARE,
    NARRATE,
    END_TURN,
    FACTS,
    REPORT,
    HELP,
    QUIT,
)

#: The commands that reach the engine. `help` and `quit` are the shell's own.
ENGINE_COMMANDS: Final[tuple[str, ...]] = (LOOK, BEGIN, DECLARE, NARRATE, END_TURN, FACTS, REPORT)

USAGE: Final = """\
look <actor>                          what is legal right now
begin <actor> [key=value ...]         open a turn; extra pairs are the situation
declare rule=<id>|no_test=<reason> [action=<key>] [label=<text>]
narrate [text ...]                    pay the narration debt; bare `narrate` withholds it
end_turn <actor>                      resolve the turn's end-of-turn obligations
facts                                 answer a blocked declaration (not wired)
report                                the session review, from the ledger
help / quit"""


class CliError(Exception):
    """A malformed command. Distinct from `SessionError`, which is a well-formed command
    arriving when the engine is waiting for something else."""


@dataclass
class CliAdapter:
    """Binds command lines to one session.

    Input and output are injected rather than reaching for `stdin` and `stdout`, for the
    reason `HumanCliDriver` gives: an adapter embedded elsewhere needs the same seam, and one
    that touches the process's streams cannot be embedded twice. It also makes every test
    below a plain function call.
    """

    session: Session
    ledger: Path
    show: Callable[[str], None] = field(default=print)

    def dispatch(self, line: str) -> str:
        """Run one command line and return what to show. Unknown names are refused."""
        parts = shlex.split(line.strip())
        if not parts:
            return ""
        name, args = parts[0], parts[1:]

        if name == HELP:
            return USAGE
        if name == LOOK:
            return self._look(_one(args, "look <actor>"))
        if name == BEGIN:
            actor, situation = _actor_and_pairs(args, "begin <actor> [key=value ...]")
            return render(self.session.begin(actor, situation=situation or None))
        if name == DECLARE:
            return render(self.session.declare(self._declaration(_pairs(args))))
        if name == NARRATE:
            text = " ".join(args).strip()
            return render(self.session.narrate(text or None))
        if name == END_TURN:
            return render(self.session.end_turn(_one(args, "end_turn <actor>")))
        if name == FACTS:
            raise NotImplementedError(
                "facts needs the memory port's Fact constructor, which takes a typed value "
                "kind; it is unwired over every adapter, not only this one"
            )
        if name == REPORT:
            return render_report(session_report(self.ledger))
        raise CliError(f"no such command: {name!r}. Try `help`.")

    def run(self, ask: Callable[[str], str]) -> None:
        """The command loop. Holds one session for as long as it runs.

        Errors are shown and the loop continues: a mistyped command is not a reason to
        discard a suspended turn, which is the thing this adapter exists to hold.
        """
        self.show(USAGE)
        while True:
            try:
                line = ask("> ")
            except EOFError:
                return
            if line.strip() in {QUIT, "exit"}:
                return
            try:
                self.show(self.dispatch(line))
            except (CliError, NotImplementedError) as refused:
                self.show(f"refused: {refused}")
            except Exception as error:
                self.show(f"{type(error).__name__}: {error}")

    def _look(self, actor_id: str) -> str:
        result = self.session.look(actor_id)
        offered = "\n".join(f"  {a.key}  {a.label}" for a in result.actions) or "  (nothing)"
        return f"legal for {result.actor_id}:\n{offered}\nread_token: {result.token}"

    def _declaration(self, pairs: Mapping[str, str]) -> Declaration:
        """Shape a Declaration from `key=value` pairs. The engine validates it; this does not.

        A pending `AwaitingDeclaration` supplies the read token and the alternatives, so the
        consumer does not retype what it was just offered — and 0007's verdict comes back
        `verified-fresh` rather than `unread` for the ordinary case.
        """
        pending = self.session.pending
        awaiting = pending if isinstance(pending, AwaitingDeclaration) else None
        offered = awaiting.offered if awaiting else None
        actor = pairs.get("actor") or (awaiting.actor_id if awaiting else "")
        if not actor:
            raise CliError("declare needs an actor, and no turn is open to take one from")

        action, label = pairs.get("action"), pairs.get("label")
        if not action and not label:
            raise CliError("declare needs action=<key> or label=<what you are doing>")

        return Declaration(
            actor_id=actor,
            intent=Intent(action_key=action) if action else Intent(improvised=True, label=label),
            rule_id=pairs.get("rule"),
            no_test_reason=pairs.get("no_test"),
            alternatives=offered.actions if offered else (),
            read_token=offered.token if offered else None,
        )


def render(pending: Pending) -> str:
    """A pending state as text a person or a script can act on.

    Exhaustive over `Pending`, closing on `assert_never` so a new member is a type error
    here rather than a crash in somebody's session — which is what #134 was.
    """
    if isinstance(pending, AwaitingDeclaration):
        offered = "\n".join(f"  {a.key}  {a.label}" for a in pending.offered.actions) or "  (none)"
        refusals = "".join(f"\nrefused: {r.why()}" for r in pending.refusals)
        return f"awaiting declaration from {pending.actor_id}:\n{offered}{refusals}"
    if isinstance(pending, AwaitingFacts):
        return (
            f"blocked: {pending.actor_id} needs {', '.join(pending.unresolved)}. "
            "The declaration stands; supplying them resumes it."
        )
    if isinstance(pending, AwaitingNarration):
        ruling = pending.ruling
        may = "; ".join(ruling.bounds.may) if ruling.bounds else ""
        may_not = "; ".join(ruling.bounds.may_not) if ruling.bounds else ""
        return (
            f"ruling: {ruling.why()}\n"
            f"you may claim: {may or 'nothing'}\n"
            f"you may not claim: {may_not or 'nothing'}\n"
            "narrate within those bounds (bounds are advisory — R7)"
        )
    if isinstance(pending, Finished):
        terminal = f" ({pending.outcome.terminal})" if pending.outcome.terminal else ""
        # The slot is over; the turn is not (0023 clause 1). Saying so is the difference
        # between a consumer that ends its turn and one that stops at the last prompt.
        return (
            f"declaration slot finished for {pending.actor_id}{terminal}. "
            f"the turn is not over — run `{END_TURN} {pending.actor_id}`"
        )
    if isinstance(pending, TurnEnded):
        ended = pending.ended
        unresolvable = "".join(
            f"\n  unresolvable: {o.condition} has no rule {o.rule_id!r} in this ruleset"
            for o in ended.unresolvable
        )
        return (
            f"turn ended for {pending.actor_id}: {len(ended.rulings)} obligation(s) "
            f"resolved{unresolvable}"
        )
    assert_never(pending)


def _pairs(args: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for arg in args:
        key, sep, value = arg.partition("=")
        if not sep:
            raise CliError(f"expected key=value, got {arg!r}")
        out[key] = value
    return out


def _actor_and_pairs(args: list[str], usage: str) -> tuple[str, dict[str, str]]:
    if not args:
        raise CliError(f"usage: {usage}")
    return args[0], _pairs(args[1:])


def _one(args: list[str], usage: str) -> str:
    if len(args) != 1:
        raise CliError(f"usage: {usage}")
    return args[0]
