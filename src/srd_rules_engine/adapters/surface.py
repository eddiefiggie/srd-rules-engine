"""What every adapter must expose, and what none of them may (R34, #133).

Two adapters exist and a third is coming, so the rules that hold across all of them live
here rather than in whichever one was written first. Both are absences or completeness
claims, and both are the kind of thing that survives being written down once and decays
being written down twice.

## The forbidden surface

`AGENTS.md`: "The skip guarantee holds only for callers the turn loop drives. A consumer
calling adjudication directly gets outcome authority without skip prevention."

So an adapter command that reached `adjudicate` would be a **supported** route to an outcome
with no challenge detection — the exact failure this engine exists to remove, shipped as a
feature. `FORBIDDEN_COMMAND_NAMES` is asserted absent from every adapter's surface by
`tests/test_adapters.py`, once, over all of them.

## One rendering, not one per transport

`render_pending` lives here for the same reason as the set above. MCP and HTTP both hand an
agent JSON describing what the engine is waiting for; two copies would be two things that
drift, in the one payload an agent reads to decide what is legal. Only the `next_step` hint
differs between them — a tool name, or a path.

## The completeness claim

`Session` answers with a `Pending` saying what the engine wants next. An adapter that cannot
reach one of those states is an adapter that cannot finish a turn — which is not
hypothetical: #110 added a phase to the loop and the MCP adapter shipped unable to drive it,
with a full green suite, because every test asked what the surface *contained* and none asked
whether it was *complete* (#134).

`pending_members()` is that question in a form a test can ask.
"""

from __future__ import annotations

from typing import Any, Final, assert_never, get_args

from srd_rules_engine.adapters.session import (
    AwaitingDeclaration,
    AwaitingFacts,
    AwaitingNarration,
    Finished,
    Pending,
    TurnEnded,
)

#: Anything that would reach an outcome without the loop. Asserted absent from every
#: adapter, rather than per adapter — the second copy is the one that goes stale.
FORBIDDEN_COMMAND_NAMES: Final[frozenset[str]] = frozenset(
    {"adjudicate", "rule", "resolve", "roll"}
)


def pending_members() -> frozenset[type]:
    """Every state `Session` can be waiting in.

    Derived from the union rather than listed, because a list is what let `TurnEnded` be
    added to `Pending` with nothing noticing that no adapter could reach it.
    """
    return frozenset(get_args(Pending))


def render_pending(pending: Pending, *, next_step: str) -> dict[str, Any]:
    """A pending state as JSON an agent can act on, with effects attached (R18).

    Shared by every adapter that speaks JSON. Two renderings of the same state are two
    things that drift, and the payload an agent decides from is not where a discrepancy
    should be discovered. Only `next_step` differs between transports: MCP names a tool,
    HTTP names a path.

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
            "situation": situation_payload(situation),
            "refusals": [refusal_payload(r) for r in pending.refusals],
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
            "next": next_step,
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
                # `label` rather than a condition since 0027 clause 2 — an obligation is
                # identified by its rule, and two of the three kinds have no condition.
                {"obligation": o.label, "rule_id": o.rule_id}
                for o in ended.unresolvable
            ],
        }
    # Every `Pending` member has a branch, and a sixth is a type error here rather than an
    # AssertionError in somebody's session. `assert isinstance(pending, Finished)` used to
    # close this function, which is why #110's `TurnEnded` could be added to the union with
    # nothing complaining (#134).
    assert_never(pending)


def refusal_payload(ruling: Any) -> dict[str, Any]:
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


def situation_payload(situation: object) -> dict[str, Any] | None:
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
        # p. 179. A `str | None` and so JSON-safe as it stands: the effect's id as the
        # caster's declaration named it, or absent. An agent that cannot see this cannot
        # weigh casting again against losing what is up.
        "concentrating_on",
        # p. 105, p. 178. Both JSON-safe as they stand. `free_hands` is `int | None`, and the
        # `None` is load-bearing: no SRD rule says how many hands a creature has, so a
        # ruleset that did not say leaves the question unanswerable rather than answered zero.
        "free_hands",
        "carried_weight",
        # p. 178. `bool | None`, and the `None` is load-bearing exactly as `free_hands` is:
        # a creature nobody sized has no capacity to be over, which is not the same fact as
        # being under one.
        "over_carrying_capacity",
        # p. 178's Speed cap, now applied (#336, 0067). `bool | None`, and this `None` carries
        # two meanings a caller may want apart: no haul was stated, or the creature is unsized.
        "over_hauling_capacity",
        # 0041 clauses 3 and 4. Both JSON-safe as they stand — tuples of item ids, and the
        # first is `tuple[str, ...] | None` where the `None` is load-bearing in the same way
        # `free_hands` above is: a creature with no position cannot be told what is within
        # its reach, and an empty list would say nothing was.
        "reachable_objects",
        # R32. The objects no rule has placed, named rather than left to be inferred from
        # their absence above — "out of reach" and "nobody said where it fell" are different
        # answers that one empty list would render identical.
        "unplaced_objects",
    )
    out: dict[str, Any] = {name: getattr(situation, name) for name in fields}
    # p. 188, #206: one shared spend, a different allowance per mode. A mode the creature
    # cannot use is absent rather than 0 — see `Situation.movement_remaining_by_mode`.
    out["movement_remaining_by_mode"] = {
        str(mode): feet
        for mode, feet in situation.movement_remaining_by_mode.items()  # type: ignore[attr-defined]
    }
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
    # 0020's two clock fields were on the read surface and on no transport, so an agent
    # driving through an adapter could not see elapsed campaign time at all — including the
    # countdown a Stable creature recovers on. Found by the completeness guard in
    # tests/test_adapters.py, not by playing.
    out["elapsed_minutes"] = situation.elapsed_minutes  # type: ignore[attr-defined]
    out["minutes_until_recovery"] = situation.minutes_until_recovery  # type: ignore[attr-defined]
    # 0025 clause 7. The level is stated and its *meaning* is not, because the table that
    # would resolve it is empty until #150 — so the payload carries the input rather than a
    # conclusion the engine has not earned.
    light = situation.light_level  # type: ignore[attr-defined]
    out["light_level"] = None if light is None else str(light)
    # p. 188, #259. A `Size | None`, where the `None` says no ruleset stated one rather than
    # that the creature is sizeless — p. 14 sources a size from a species or a stat block and
    # neither ships here, so Medium would be the engine inventing the answer (R31).
    size = situation.size  # type: ignore[attr-defined]
    out["size"] = None if size is None else str(size)
    # p. 178's two bounds, with the sentence that reached them. The derivation travels because
    # the result alone cannot show the step that matters: p. 86 and p. 357 read the table one
    # row up, so a Medium creature's numbers can legitimately be a Large row's.
    capacity = situation.carrying_capacity  # type: ignore[attr-defined]
    out["carrying_capacity"] = (
        None
        if capacity is None
        else {
            "carry": capacity.carry,
            "drag_lift_push": capacity.drag_lift_push,
            "read_at_size": str(capacity.size),
            "strength_score": capacity.strength_score,
            "derivation": capacity.derivation(),
        }
    )
    out["senses"] = {
        str(sense): situation.senses.range_of(sense)  # type: ignore[attr-defined]
        for sense in situation.senses.held  # type: ignore[attr-defined]
    }
    return out
