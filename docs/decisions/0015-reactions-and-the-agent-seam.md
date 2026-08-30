# 0015 — The generator seam already serves reactions; what they need is state and triggers

- **Status:** Accepted, 2026-08-23
- **Settles:** the architectural question [#16](https://github.com/eddiefiggie/srd-rules-engine/issues/16)
  raised about reactions and [#4](https://github.com/eddiefiggie/srd-rules-engine/issues/4)
- **Requirements:** R8, R12
- **Related:** [0001 — the agent seam is a generator of typed requests](0001-agent-seam.md), which
  this record confirms rather than revises

## Context

#16 flags reactions as the part of the action economy worth worrying about early:

> Reactions are the part worth flagging early: they interrupt the turn loop's control flow rather
> than fitting inside a turn, so they interact directly with #4 (how the loop invokes the agent). An
> opportunity attack means the loop must be able to invoke the agent *out of turn*, for a different
> actor, mid-resolution. **A design that assumed one agent invocation per turn will not survive
> this.**

That warning was written before the loop existed. It was worth writing, and it now needs answering
one way or the other, because the answer decides whether the action economy can be built
incrementally or needs a redesign first.

## The answer

**The design it warns about was never built.** `TurnLoop.run` is

```
Generator[Request, Response, TurnOutcome]
```

and `DeclarationRequest` carries its own `actor_id`. The loop already yields several requests per
turn — a declaration, zero or more blocked-fact requests, a narration — and nothing binds a
`DeclarationRequest` to the turn's own actor. Yielding one for a different creature, part-way
through resolving another creature's action, is the same operation the loop already performs.

Decision 0001 chose the generator precisely to avoid the callback shape that would have made this
hard, for a reason that had nothing to do with reactions: a callback seam would have needed a second
asynchronous loop whose rules logic measured identical after stripping `await`. The property that
argument bought — control inversion — is exactly the property reactions need.

## Decision

**1. No redesign of the seam.** Reactions do not require a change to how the loop invokes the agent.
#16's warning is answered in the negative and this record is the evidence, so it does not get
re-raised by the next person to read the issue.

**2. What reactions actually need is three things, none of them architectural.**

- **A budget**, which now exists: one Reaction, refreshed at "the start of your next turn" (p. 186)
  rather than at the end of the round, and free of the Action and Bonus Action.
- **Trigger detection.** An Opportunity Attack fires "when a creature that you can see leaves your
  reach using its action, its Bonus Action, its Reaction, or one of its speeds" (p. 185). That is a
  movement-time question: it belongs where movement resolves, not in the action economy.
- **An interleaving rule for the ledger.** The reaction's declaration, ruling and narration land
  between another creature's entries. The ledger is append-only and each entry names its actor, so
  the entries are well-formed; what is undecided is how `session_report` groups them into turns.

**3. The interleaving is what to settle before building, not the seam.** `core.report._turns`
assembles turns from a flat entry sequence, and a reaction's entries would currently be attributed
to whichever turn was open. That is a reporting question with a right answer, and it is the piece
that will bite.

## Why

### The warning was right to be written and wrong on the facts

An architecture note that turns out not to apply is not a wasted note. It named the property to
check — "can the loop invoke the agent out of turn?" — and that property is now checked and
recorded rather than assumed either way. The cost of leaving it open was that every plan touching
the action economy had to treat it as a possible redesign.

### Answering it narrows the work sharply

With the seam settled, Opportunity Attacks are: detect a departure from reach during movement, ask
the reacting creature's driver whether it spends its Reaction, and resolve one melee attack through
the same adjudication entry point everything else uses. No new outcome path, no second adjudicator,
no async variant.

## Consequences

**Accepted costs.**

- `session_report` will need a rule for attributing interleaved entries, and this record does not
  supply one. It names it as the next question rather than answering it, which is a deferral.
- The Reaction budget ships before anything spends it. That is a real gap between "modelled" and
  "used", and `core.actions` says so.

**Follow-on effects.**

- Opportunity Attacks are unblocked and remain unimplemented. Movement is where they belong, and
  `EncounterState.with_movement` is where a departure from reach becomes detectable.
- `disengaged` exists on the budget and nothing consumes it yet, for the same reason.
- Ready (p. 186) needs the same machinery plus a trigger the agent supplies, so it waits on the same
  work.

## Evidence

`TurnLoop.run`'s signature and `DeclarationRequest.actor_id` are the whole of it — both are in
`src/srd_rules_engine/loop/turn.py`, and the fixture driver in `tests/fixtures/encounter.py` already
answers declaration requests keyed by `request.actor_id` rather than by an actor it assumed.

No spike was needed, which is itself the finding: had the seam been a callback, this record would
have been a redesign proposal instead.

## Status of implementation

**The budget is implemented** in `core.actions`, with the refresh timing p. 186 specifies. Trigger
detection and the ledger interleaving rule are not, and are named above as the remaining work.

| Unbuilt clause | Held by |
|---|---|
| Trigger detection — a departure from reach during movement | **Built** 2026-08-24 as `core.reactions.provocations`, with `disengaged` finally consumed |
| p. 185's "that you can see" | **Built** 2026-08-30. `provocations` consults `EncounterState.can_see` per reactor: `CANNOT_SEE` drops the provocation, `UNSTATED` withholds it naming `SIGHT_UNSTATED`, `CAN_SEE` offers it. It was withheld unconditionally until then, on [#150](https://github.com/eddiefiggie/srd-rules-engine/issues/150) — **which closed on 2026-08-25**, five days before this row was corrected ([#381](https://github.com/eddiefiggie/srd-rules-engine/issues/381)) |
| The Reaction offer itself, and the out-of-turn invocation this record says the seam already serves | **Not built.** [#382](https://github.com/eddiefiggie/srd-rules-engine/issues/382). This row said "unprovable until an offer can be made", and it now *is* provable — [#381](https://github.com/eddiefiggie/srd-rules-engine/issues/381) made `provocations` return offerable results. Disclosed at the read surface as `opportunity-attack-detected-but-never-offered` |
| Ready (p. 186), whose sentence is asserted nowhere | [#16](https://github.com/eddiefiggie/srd-rules-engine/issues/16) |
| The rule `session_report` needs for attributing interleaved entries to turns | [#120](https://github.com/eddiefiggie/srd-rules-engine/issues/120) |

_Table added 2026-08-24 ([#126](https://github.com/eddiefiggie/srd-rules-engine/issues/126)). Both were tracked
already; neither was named here, so a reader of this record alone could not find the work it
deferred._

_Corrected 2026-08-30 ([#381](https://github.com/eddiefiggie/srd-rules-engine/issues/381)). The
trigger row said sight was unanswerable and cited a **closed** issue, and it said so for five
days across four builds. It is worth recording **why no guard caught it**:
`scripts/check_status_rows.py` fails a row that claims `not built` while the issue it cites is
closed, and this row said **Built** — the lapsed blocker was in its prose, not in its claim. That
is a third direction beyond the two `AGENTS.md` names, and the one that reads as a deliberate
limit rather than as an oversight. The sight clause is now its own row, so what is built and
what is not are separately checkable._
