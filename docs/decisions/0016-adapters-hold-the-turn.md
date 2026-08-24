# 0016 — An adapter holds the suspended turn, and never exposes adjudication

- **Status:** Accepted, 2026-08-23
- **Settles:** the adapter shape for [#97](https://github.com/eddiefiggie/srd-rules-engine/issues/97)
- **Requirements:** R8, R33 · touches R1, R19, R29
- **Related:** [0001 — the agent seam is a generator](0001-agent-seam.md), whose shape forces this;
  [0002 — ledger durability](0002-ledger-durability.md), which is what makes a lost session
  recoverable; [0015](0015-reactions-and-the-agent-seam.md), which relied on the same property for
  a different reason

## Context

The engine had no surface an LLM could speak to. The turn loop is a **generator** yielding typed
requests; MCP, HTTP and CLI all make **stateless calls**. A call cannot resume a generator that a
previous call left suspended unless something holds it.

That is a genuine impedance mismatch, and the way it is resolved decides whether the product still
works over an adapter.

## Options considered

**Expose adjudication as a tool.** Simplest, stateless, and it forfeits the entire product.
`AGENTS.md` states the limit plainly:

> The skip guarantee holds only for callers the turn loop drives. A consumer calling adjudication
> directly gets outcome authority without skip prevention.

An adapter offering an `adjudicate` tool would therefore ship a **supported, documented route to an
outcome with no challenge detection** — the exact failure the engine exists to remove, presented as
a feature. Rejected outright, and the rejection is asserted by a test rather than remembered.

**Re-derive the loop position from the ledger on each call.** Attractive because it is stateless and
the ledger is already durable. It does not work: the ledger records what *happened*, not where the
generator was *suspended*. A challenge awaiting a re-declaration and a ruling awaiting its narration
are loop state, and reconstructing them would mean a second implementation of the loop's control
flow — the same "two implementations that must agree" problem decision 0001 rejected for callbacks.

**Hold the suspended generator per session.** Chosen.

## Decision

**1. One `Session` owns one live turn, and answers what the engine is waiting for.** `begin` and
each answer return a `Pending` — one of `AwaitingDeclaration`, `AwaitingFacts`, `AwaitingNarration`,
`Finished`. A caller reads the state and calls the matching method; answering the wrong question
raises rather than being coerced, because a coerced response is a declaration nobody made.

**2. No adapter exposes adjudication.** `FORBIDDEN_TOOL_NAMES` names the shapes that would, and a
test asserts none of them is on the tool list. Every path goes through `Session`, which goes through
the loop.

**3. The transport is an extra, never a dependency.** The MCP SDK is imported inside `build_server`,
so importing `srd_rules_engine.adapters` never requires it and `[project].dependencies` stays empty
(R33). A test parses the module's AST and fails if the SDK appears at module scope.

**4. `begin_turn` takes the situation.** The trigger catalogue matches against what is physically
around the actor, so a tool that could not carry it would leave the challenge mechanism silently
unreachable — the product's central feature, disabled by an omitted parameter rather than by a
decision.

**5. A refusal carries the triggers that fired, with their grounding.** A challenge whose substance
is dropped is useless: an agent told only "challenged" has nothing to re-declare against. Each
trigger carries its message, its reference where the SRD supplies one, and whether it is *authored*
or *cited* — decision 0004's distinction, surfaced rather than flattened.

## Why

### The stateless option is not simpler, it is a different product

It looks like an engineering trade and is not. Holding a generator costs process state; exposing
adjudication costs the guarantee the project exists to provide. Those are not comparable, and
treating them as comparable is how a product loses its point during an integration.

### A lost session is recoverable, and the ledger is why

The suspension is process state and will sometimes be lost. What survives is everything durable:
entries are written before anything escapes the engine (0002), so the record of what happened is
intact. What is lost is the *position within a turn*.

That surfaces rather than corrupts. A new session starts a fresh turn from the recorded state, and
R29's narration debt notices anything dangling — a ruling whose narration never arrived leaves the
actor owing one, and the loop refuses its next declaration until it is paid. A lost session
therefore appears as a refusal, not as a silently skipped turn.

**The debt lives on the `TurnLoop`, not on the session**, so it survives a session only if the loop
does. That is a real limit and it is disclosed in `core.adapters.session` rather than assumed away.

### One session, because the product is one character

`AGENTS.md` lists multiplayer and shared sessions as a declined non-goal. A registry keyed by a
caller-supplied identifier would be the first piece of concurrency machinery in a codebase that
assumes none, so the server holds one session and refuses a second concurrent turn.

## Consequences

**Accepted costs.**

- The adapter is stateful, and it is the only stateful thing in the project. Everything it returns
  is frozen; the mutability is confined to one suspended generator.
- A crash between a ruling and its narration leaves a debt that a fresh loop does not know about.
  Disclosed, not solved.
- `supply_facts` is declared as a tool and raises `NotImplementedError`: wiring it needs the memory
  port's typed value constructor, which is the next slice of #97. A tool that fails loudly is better
  than one quietly missing from the list an agent plans against.

**Follow-on effects.**

- HTTP and CLI adapters reuse `Session` unchanged; only the transport binding differs.
- The MCP tool list is the first public API surface with a stability question, which is
  [#39](https://github.com/eddiefiggie/srd-rules-engine/issues/39)'s territory.

## Evidence

The server was built against the real MCP SDK (2.0.0) outside CI, since the extra is not installed
there: `build_server` returns a `Server` reporting a tools capability, the six tools are declared,
and a `begin_turn` call through the adapter returns a JSON-serialisable declaration request.

The challenge path was exercised end to end over the adapter: a no-test claim against loose scree
comes back `challenged`, carrying the trigger `fixture-hazard-loose-ground`, its message, and
`grounding: authored`.

## Status of implementation

**Implemented.** `adapters/session.py` and `adapters/mcp.py`, with the `mcp` extra declared in
`pyproject.toml`. `supply_facts` is the one declared tool that does not yet work.
