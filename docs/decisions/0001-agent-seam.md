# 0001 — The agent seam is a generator of typed requests

- **Status:** Accepted, 2026-08-21
- **Settles:** [#4](https://github.com/eddiefiggie/srd-rules-engine/issues/4)
- **Requirements:** R8, R33, R34 · touches R2, R6, R12, R22, R28, R29, R30
- **Supersedes:** nothing

## Context

R8 says a turn-driving loop ships as a v1 deliverable outside the LLM-free core, owns the turn,
and invokes the agent only at defined points. It did not say *how* that invocation is expressed,
and the answer is public API — every adapter (R34) and every third-party agent binds to it.

Two constraints made this more than a taste question.

**The non-goal.** The engine must serve any agent, or none. A seam that imports a framework
breaches that in practice even while the core stays clean under R33.

**Ergonomics are a correctness concern here, not polish.** The skip guarantee — the entire point
of the project — holds only for callers the loop drives. A consumer who calls adjudication
directly gets outcome authority with no skip prevention. So an awkward loop doesn't merely
annoy; it gets bypassed, and a bypassed loop is a silent return to the defect this project
exists to fix.

### The hard cases

Any candidate had to survive four situations that a naive "one agent call per turn" design does
not:

1. **Out-of-turn invocation.** Mid-resolution of the hero's move, an ogre gets an opportunity
   attack (R12). The loop must obtain a declaration from a *different actor* while the first
   actor's action is still unresolved.
2. **Multiple exchanges at one decision point.** A challenged no-test claim must be re-declared
   (R6, F2), a rejected declaration resubmitted (F3), both under a retry bound (#11).
3. **The narration handshake.** After a Ruling the agent must narrate, and the loop refuses the
   next declaration for that actor until the narration arrives (R29).
4. **A question that is not for the agent at all.** A missing fact with no default returns
   `blocked` (R22) and may need the human, not the model.

## Options considered

**A. A callback Protocol.** `Agent` with `declare()` and `narrate()`; the loop calls it.
Familiar, and pleasingly symmetrical with the memory port.

**B. A generator of typed requests.** The loop yields an `AgentRequest`; the driver sends back an
`AgentResponse`. Control is inverted: the loop never calls the agent, it asks.

**C. A queue the caller pumps.** Similar properties to B, but session state moves out of the
generator's own stack into mutable queues, and ordering guarantees must then be built by hand.

**D. A subclass hook.** Rejected on sight. Inheritance couples consumers to internals, and an
overridable loop makes the single adjudication entry point (R1) easier to subvert, not harder.

Both A and B handle all four hard cases. The decision turned on what happened next.

## Decision

**The primitive is a generator (B). An object-shaped adapter ships on top of it (A as sugar).**

```python
TurnLoop = Generator[AgentRequest, AgentResponse, TurnOutcome]

# What the loop asks for
NeedDeclaration(actor, legal_actions, reason, challenge=None, attempt=1)
NeedNarration(actor, ruling, bounds)
NeedFact(fact)  # R22 blocked — often a human question, not a model one

# What the driver sends back
Declared(test | None, reason)  # test=None is an explicit no-test claim (R2)
Narrated(text)
FactProvided(value)
```

Drivers are user code and carry no rules logic:

```python
def drive(loop, answer):  # synchronous
    try:
        request = next(loop)
        while True:
            request = loop.send(answer(request))
    except StopIteration as done:
        return done.value


async def drive_async(loop, answer):  # identical, one `await`
    ...
```

And for the common case, an adapter restores the familiar object shape in about ten lines, so
nobody who doesn't want the primitive has to meet it:

```python
class Agent(Protocol):
    def declare(self, request: NeedDeclaration) -> Declared: ...
    def narrate(self, request: NeedNarration) -> Narrated: ...
```

**Reference bindings: yes, two, and neither is an LLM.** A scripted agent for tests, and a CLI
driver where the human answers the prompts. Both are zero-dependency.

## Why

### The duplication cost of A is total, and invisible to review

A spike implemented the same turn — reaction interrupt, challenge loop, narration handshake,
blocked fact — in both shapes. Real LLM clients are async-first, so shape A must offer an async
loop; that loop is a line-by-line restatement of the sync one.

Measured by AST comparison, stripping the word `await`:

| | |
|---|---|
| Statements in A's sync loop | 25 |
| Statements in A's async loop | 25 |
| **Identical statements** | **25 (100%)** |
| Genuine differences | **0** |

The problem is not writing it twice. It is that from then on every rule change must land in both,
correctly, forever — and because the two functions *read the same*, a divergence passes review. A
rules bug that only async consumers can see is exactly the class of defect this project is built
to make impossible.

Shape B has no such fork: sync, async, scripted, and human drivers in the spike all ran the same
loop and produced **byte-identical ledgers**.

### The seam is the transcript, so R28 and R30 come free

Because every agent contribution crosses exactly one seam, recording is a wrapper around the
driver's `answer` — no instrumentation of the agent, no cooperation from it required. In the
spike, a full turn serialised to 1,393 bytes of JSON, replayed to an identical ledger, and
produced a session-review report (R30) listing each declaration, the challenge that forced a
re-declaration, the narration bounds, and the blocked fact — **derived from the transcript
alone**.

Replay also *detects divergence* rather than absorbing it: replaying a tampered transcript
against the loop raised `replay diverged: expected NeedNarration, loop asked NeedDeclaration`.
Under shape A the same capability requires every agent implementation to cooperate in its own
auditing, which is not a thing a third-party agent can be relied upon to do.

### Out-of-turn invocation needs no machinery

The ogre's opportunity attack is the *same* `NeedDeclaration` type, carrying a different actor
and `reason="reaction"`. Nothing in the loop special-cases it. This mattered more than expected:
it is the case that kills designs assuming one agent call per turn, and it costs nothing here.

### Why the reference bindings are not an LLM

The argument for shipping a model binding was that v1 is otherwise unplayable without the user
writing glue. The human-driven CLI answers that directly: **v1 is playable by a person, with no
model and no network**, which also makes it the honest way to sit down and check whether the
challenge mechanism actually feels right in play.

That removes the only real case for putting a vendor in the repository. The LLM binding is
documented as a pattern instead — with this seam it is a function from `AgentRequest` to
`AgentResponse`, which is small enough to be worth writing rather than depending on.

## Consequences

**Accepted costs.**

- `send()`-driven generators are less familiar than an object with methods, and misuse is
  possible — priming, or sending the wrong response type. Mitigated by the `Agent` adapter, which
  most consumers will use, and by responses being typed rather than positional.
- The generator holds session state on its own stack, so a loop cannot be paused across a process
  boundary without the transcript. Since the transcript exists for R28 anyway, resuming means
  replaying it — acceptable, and worth stating rather than discovering.

**Follow-on effects.**

- Adapters (R34) become thin: MCP, HTTP, and CLI each translate one request type to their
  transport and back. None of them re-implement the turn.
- The retry bound (#11) lives naturally on `NeedDeclaration.attempt`; whatever that gate decides
  about *what happens at the bound*, the shape already carries it.
- Testing the rules with no model in the loop stops being a special mode. It is just a driver.

## Evidence

The spike is not committed — it was throwaway, and shipping it would imply implementation that
M0 has not authorised yet. To reproduce: implement one turn covering the four hard cases in both
shapes, compare A's sync and async loops by parsing each into an AST and diffing the unparsed
statements with `await` stripped, then wrap a driver's `answer` to record and replay.

## Status of implementation

**None, deliberately.** M0 holds that nothing is implemented until the gates close, because an
open gate otherwise gets settled by whoever writes the code first. This record specifies the
seam; the module lands when M1 opens.
