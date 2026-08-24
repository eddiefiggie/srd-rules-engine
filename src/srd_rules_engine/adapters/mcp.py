"""An MCP server over the turn loop (#97).

Import this only with the `mcp` extra installed:

    pip install 'srd-rules-engine[mcp]'

The dependency is imported inside `build_server` rather than at module scope, so importing
`srd_rules_engine.adapters` never requires it and `[project].dependencies` stays empty
(R33). The core takes no network dependency; an adapter declaring one is the whole reason
extras exist.

## The tools, and the one that is absent

| Tool | What it does |
|---|---|
| `look` | What is legal for an actor, and its own situation. Mutates nothing (R19). |
| `begin_turn` | Opens a turn and returns the first question. |
| `declare` | Answers a declaration request. May come back challenged or rejected. |
| `narrate` | Pays R29's narration debt for a ruling. |
| `end_turn` | Resolves the obligations the turn's end incurs (0023, #110). |
| `supply_facts` | Answers a blocked declaration with what the port could not resolve. |
| `session_report` | The session review, derived from the ledger. |

**`end_turn` is a separate tool because the turn's end is a separate phase.** Decision 0023
put it there: `TurnLoop.run` owns a declaration slot and returns when it resolves, so
`Finished` means the slot is done and *not* that the turn is over. The rendered payload says
so — a `Finished` carries `"next": "end_turn"` — because an agent that reads it as "turn
over" stops one phase early, which is the skip `EncounterState.advanced_turn` now refuses to
let pass.

**The obligation waiver is not exposed, and that is a decision rather than an oversight.**
`advanced_turn(waive_obligations=True)` exists for a consumer that legitimately wants to
fast-forward. An agent is not that consumer: putting the waiver in this tool list would put
a *documented, supported* way to skip a compulsory save in front of the one caller the
challenge mechanism exists to constrain. A consumer that genuinely needs it holds the state
and can call the core directly, which `AGENTS.md` already discloses forfeits the skip
guarantee.

**There is no `adjudicate` tool, and that absence is the design.** `AGENTS.md`: "The skip
guarantee holds only for callers the turn loop drives. A consumer calling adjudication
directly gets outcome authority without skip prevention." Exposing it would be a supported
route to an outcome with no challenge detection — the failure this engine exists to remove,
shipped as a feature. Every tool here goes through `Session`, which goes through the loop.

## One session, because the product is one player character

`AGENTS.md` lists multiplayer and shared sessions as a declined non-goal, so the server holds
a single `Session` rather than a registry keyed by some caller-supplied identifier. A second
concurrent turn is refused by `Session` itself.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, assert_never

from srd_rules_engine.adapters.session import (
    AwaitingDeclaration,
    AwaitingFacts,
    AwaitingNarration,
    Finished,
    Pending,
    Session,
    TurnEnded,
)
from srd_rules_engine.adapters.surface import FORBIDDEN_COMMAND_NAMES
from srd_rules_engine.core import Declaration, Intent, session_report

#: Tool names, in one place so the server and its tests cannot disagree about them.
LOOK = "look"
BEGIN_TURN = "begin_turn"
DECLARE = "declare"
NARRATE = "narrate"
END_TURN = "end_turn"
SUPPLY_FACTS = "supply_facts"
SESSION_REPORT = "session_report"

TOOL_NAMES: tuple[str, ...] = (
    LOOK,
    BEGIN_TURN,
    DECLARE,
    NARRATE,
    END_TURN,
    SUPPLY_FACTS,
    SESSION_REPORT,
)

#: Kept as an alias: the set is shared with every other adapter now (#133), because a
#: second copy of a rule this load-bearing is the copy that goes stale.
FORBIDDEN_TOOL_NAMES: frozenset[str] = FORBIDDEN_COMMAND_NAMES


def tool_definitions() -> tuple[dict[str, Any], ...]:
    """The tool list, as plain dictionaries so it can be inspected without the MCP types."""
    return (
        {
            "name": LOOK,
            "description": (
                "What is legal for an actor right now, and its own situation: conditions "
                "with their mechanical effects, movement remaining, action economy, and "
                "spell slots. Mutates nothing and records nothing."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"actor_id": {"type": "string"}},
                "required": ["actor_id"],
            },
        },
        {
            "name": BEGIN_TURN,
            "description": (
                "Open a turn for an actor and return the engine's first question. "
                "`situation` describes what is physically around the actor — loose scree, "
                "a ledge, deep water. The trigger catalogue matches against it, so a "
                "no-test claim can only be challenged by a hazard the situation names. "
                "Omitting it does not make the turn safer; it makes the hazard invisible."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "actor_id": {"type": "string"},
                    "situation": {"type": "object", "additionalProperties": True},
                },
                "required": ["actor_id"],
            },
        },
        {
            "name": DECLARE,
            "description": (
                "Declare which test applies, or that none does and why. A no-test claim "
                "that collides with a trigger comes back challenged, with the citation, "
                "and must be re-declared. Echo the read token and the alternatives you "
                "were offered."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "actor_id": {"type": "string"},
                    "action_key": {"type": ["string", "null"]},
                    "rule_id": {"type": ["string", "null"]},
                    "no_test_reason": {"type": ["string", "null"]},
                    "improvised_label": {"type": ["string", "null"]},
                    "read_token": {"type": ["string", "null"]},
                },
                "required": ["actor_id"],
            },
        },
        {
            "name": NARRATE,
            "description": (
                "Submit the narration for the ruling just returned. The ruling's narration "
                "bounds say what may and may not be asserted; they are advisory, and this "
                "is what R29 requires before the actor declares again."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"text": {"type": ["string", "null"]}},
                "required": [],
            },
        },
        {
            "name": END_TURN,
            "description": (
                "Resolve every obligation the end of this creature's turn incurs — today, "
                "the saves a condition repeats at the end of each of its turns (p. 63). "
                "The engine derives them from state and rolls them; you are not asked "
                "whether they happen, because the rules give the creature no choice. Each "
                "produces a ruling to narrate. Call this after the turn's declaration "
                "finishes: the encounter state refuses to advance while an obligation "
                "stands."
            ),
            "input_schema": {
                "type": "object",
                "properties": {"actor_id": {"type": "string"}},
                "required": ["actor_id"],
            },
        },
        {
            "name": SUPPLY_FACTS,
            "description": (
                "Supply the typed facts a blocked declaration named. Values only — the "
                "memory port never accepts prose."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "facts": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type_name": {"type": "string"},
                                "subject": {"type": "string"},
                                "value": {},
                            },
                            "required": ["type_name", "subject", "value"],
                        },
                    }
                },
                "required": ["facts"],
            },
        },
        {
            "name": SESSION_REPORT,
            "description": (
                "The session review derived from the ledger: every turn, its arithmetic, "
                "and any flags such as a narration that no ruling supports."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
    )


def render(pending: Pending) -> dict[str, Any]:
    """A pending state as JSON the agent can act on, with effects attached (R18).

    Typed values throughout: an agent told only that it is Poisoned is back to recalling 5e
    from training, which is the capability this engine removes.
    """
    if isinstance(pending, AwaitingDeclaration):
        situation = pending.offered.situation
        return {
            "awaiting": "declaration",
            "actor_id": pending.actor_id,
            "read_token": pending.offered.token,
            "offered": [
                {"key": a.key, "label": a.label, "detail": dict(a.detail)}
                for a in pending.offered.actions
            ],
            "situation": _situation(situation),
            "refusals": [_refusal(r) for r in pending.refusals],
        }
    if isinstance(pending, AwaitingFacts):
        return {
            "awaiting": "facts",
            "actor_id": pending.actor_id,
            "unresolved": list(pending.unresolved),
        }
    if isinstance(pending, AwaitingNarration):
        ruling = pending.ruling
        return {
            "awaiting": "narration",
            "actor_id": pending.actor_id,
            "derivation": ruling.result.derivation() if ruling.result else None,
            "may_claim": list(ruling.bounds.may) if ruling.bounds else [],
            "may_not_claim": list(ruling.bounds.may_not) if ruling.bounds else [],
            "citations": list(ruling.citations),
        }
    if isinstance(pending, Finished):
        return {
            "awaiting": None,
            "actor_id": pending.actor_id,
            # The declaration slot is over; the turn is not (0023). `end_turn` is what
            # follows, and saying so here is the difference between an agent that ends its
            # turn and one that stops at the last thing it was asked for.
            "next": END_TURN,
            "terminal_reason": (
                str(pending.outcome.terminal) if pending.outcome.terminal else None
            ),
            "produced_outcome": pending.outcome.produced_outcome,
            "missing_narration": pending.outcome.missing_narration,
        }
    if isinstance(pending, TurnEnded):
        ended = pending.ended
        return {
            "awaiting": None,
            "actor_id": pending.actor_id,
            "next": None,
            "obligations_resolved": len(ended.rulings),
            "missing_narration": ended.missing_narration,
            # A ruleset with no rule for an obligation cannot resolve it. Named rather than
            # silent: the ledger carries the rejection either way, and an agent told only
            # that the turn ended would read an unresolvable save as a resolved one.
            "unresolvable": [
                {"condition": str(o.condition), "rule_id": o.rule_id} for o in ended.unresolvable
            ],
        }
    # Every `Pending` member has a branch, and a sixth is a type error here rather than an
    # AssertionError in somebody's session. `assert isinstance(pending, Finished)` used to
    # close this function, which is why #110's `TurnEnded` could be added to the union with
    # nothing complaining (#134).
    assert_never(pending)


def _refusal(ruling: Any) -> dict[str, Any]:
    """A challenge or rejection, with the thing that caused it.

    The substance of a challenge is the **triggers that fired**, not the status: an agent
    told only "challenged" has nothing to re-declare against. Each carries its message, its
    reference where the SRD supplies one, and its `grounding` — because the trigger
    catalogue is *grounded in* rather than *cited from* the document (decision 0004), and an
    agent should be able to tell an authored trigger from a cited one.
    """
    return {
        "status": str(ruling.status),
        "citations": list(ruling.citations),
        "reason": ruling.reason,
        "reason_code": str(ruling.reason_code) if ruling.reason_code else None,
        "triggers": [
            {
                "id": trigger.id,
                "message": trigger.message,
                "reference": trigger.reference,
                "grounding": str(trigger.grounding),
            }
            for trigger in ruling.fired
        ],
    }


def _situation(situation: object) -> dict[str, Any] | None:
    if situation is None:
        return None
    fields = (
        "hit_points",
        "max_hit_points",
        "cannot_act",
        "speed",
        "movement_remaining",
        "action_available",
        "bonus_action_available",
        "reaction_available",
    )
    out: dict[str, Any] = {name: getattr(situation, name) for name in fields}
    out["conditions"] = [str(c) for c in situation.conditions]  # type: ignore[attr-defined]
    out["attack_rolls_against_you"] = str(situation.attack_rolls_against_you)  # type: ignore[attr-defined]
    out["your_attack_rolls"] = str(situation.your_attack_rolls)  # type: ignore[attr-defined]
    out["spell_slots"] = dict(situation.spell_slots)  # type: ignore[attr-defined]
    out["unenforced_clauses"] = list(situation.unenforced_clauses)  # type: ignore[attr-defined]
    # #18. An agent told a condition's name but not how long it lasts is back to recalling
    # 5e, which is the capability this engine removes — so the span travels with the name.
    out["condition_durations"] = {
        str(c): d
        for c, d in situation.condition_durations.items()  # type: ignore[attr-defined]
    }
    out["conditions_until_removed"] = [
        str(c)
        for c in situation.conditions_until_removed  # type: ignore[attr-defined]
    ]
    out["saves_due"] = {
        str(c): {"ability": ability, "dc": dc}
        for c, (ability, dc) in situation.saves_due.items()  # type: ignore[attr-defined]
    }
    return out


@dataclass
class Adapter:
    """Binds tool calls to one session. Transport-free, so it is testable without MCP."""

    session: Session
    ledger: Path

    def call(self, name: str, arguments: Mapping[str, Any]) -> dict[str, Any]:
        """Dispatch one tool call. Unknown names are refused rather than ignored."""
        if name == LOOK:
            result = self.session.look(str(arguments["actor_id"]))
            return {
                "actor_id": result.actor_id,
                "offered": [
                    {"key": a.key, "label": a.label, "detail": dict(a.detail)}
                    for a in result.actions
                ],
                "read_token": result.token,
                "situation": _situation(result.situation),
            }
        if name == BEGIN_TURN:
            situation = arguments.get("situation")
            return render(
                self.session.begin(
                    str(arguments["actor_id"]),
                    situation=dict(situation) if isinstance(situation, Mapping) else None,
                )
            )
        if name == DECLARE:
            return render(self.session.declare(_declaration(arguments)))
        if name == NARRATE:
            text = arguments.get("text")
            return render(self.session.narrate(None if text is None else str(text)))
        if name == END_TURN:
            return render(self.session.end_turn(str(arguments["actor_id"])))
        if name == SUPPLY_FACTS:
            raise NotImplementedError(
                "supply_facts needs the memory port's Fact constructor, which takes a typed "
                "value kind; wiring it is the next slice of #97"
            )
        if name == SESSION_REPORT:
            return {"report": _report_text(self.ledger)}
        raise KeyError(f"no such tool: {name!r}")


def _declaration(arguments: Mapping[str, Any]) -> Declaration:
    """Build a Declaration from tool arguments. The engine validates it; this only shapes it."""
    action_key = arguments.get("action_key")
    label = arguments.get("improvised_label")
    intent = (
        Intent(action_key=str(action_key))
        if action_key
        else Intent(improvised=True, label=str(label) if label else None)
    )
    rule_id = arguments.get("rule_id")
    reason = arguments.get("no_test_reason")
    token = arguments.get("read_token")
    return Declaration(
        actor_id=str(arguments["actor_id"]),
        intent=intent,
        rule_id=str(rule_id) if rule_id else None,
        no_test_reason=str(reason) if reason else None,
        read_token=str(token) if token else None,
    )


def _report_text(ledger: Path) -> str:
    from srd_rules_engine.core import render as render_report

    return render_report(session_report(ledger))


def build_server(adapter: Adapter, *, name: str = "srd-rules-engine") -> Any:
    """Construct the MCP server. Imports `mcp` here, so the extra is only needed to *run*."""
    try:
        from mcp import types
        from mcp.server import Server
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise ImportError(
            "the MCP adapter needs the `mcp` extra: pip install 'srd-rules-engine[mcp]'"
        ) from exc

    async def on_list_tools(_context: Any, _params: Any) -> Any:
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=definition["name"],
                    description=definition["description"],
                    inputSchema=definition["input_schema"],
                )
                for definition in tool_definitions()
            ]
        )

    async def on_call_tool(_context: Any, params: Any) -> Any:
        payload = adapter.call(params.name, params.arguments or {})
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(payload, indent=1))]
        )

    return Server(name, on_list_tools=on_list_tools, on_call_tool=on_call_tool)
