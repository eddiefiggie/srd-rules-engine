# 0093 — A readied spell is cast, and what waits is its effect

- **Status:** Accepted, 2026-09-12
- **Settles:** [#436](https://github.com/eddiefiggie/srd-rules-engine/issues/436)
- **Requirements:** R14, R15, R17, R18, R31, R32
- **Related:** [0065 — a long cast spends its slot on completion](0065-a-long-cast-spends-its-slot-on-completion.md),
  which the gate reported this record as reversing and which it leaves untouched;
  [0038 — a spell is data the caster carries](0038-a-spell-is-data-the-caster-carries.md),
  clause 6, whose ordering both castings still obey; [0015 — reactions and the agent
  seam](0015-reactions-and-the-agent-seam.md), which is the seam the release travels on;
  [0037 — a concentration is an early-out, not an axis](0037-a-concentration-is-an-early-out-not-an-axis.md)
  and [0036 — a fourth occasion owed by whoever took the damage](0036-a-fourth-occasion-owed-by-whoever-took-the-damage.md),
  the Concentration this one caps; [0049 — advantage that outlives its
  roll](0049-advantage-that-outlives-its-roll.md), for the `TurnBoundary` vocabulary the cap
  is written in; [0061 — a shape resolves, and a clause may not](0061-a-shape-resolves-and-a-clause-may-not.md),
  for why `ready` stays unclaimed while a stated case refuses

## Context

p. 186, *Ready [Action]*, whole:

> You take the Ready action to wait for a particular circumstance before you act. To do so,
> you take this action **on your turn**, which lets you act by taking a **Reaction before the
> start of your next turn**. First, you decide what **perceivable circumstance** will trigger
> your Reaction. Then, you choose the **action** you will take in response to that trigger, or
> you choose to **move up to your Speed** in response to it. […] When the trigger occurs, you
> can either take your Reaction right after the trigger finishes **or ignore the trigger**.
>
> When you **Ready a spell**, you cast it as normal (**expending any resources used to cast
> it**) but **hold its energy**, which you release with your Reaction when the trigger occurs.
> To be readied, a spell must have a **casting time of an action**, and holding on to the
> spell's magic requires **Concentration**, which you can maintain **up to the start of your
> next turn**. If your Concentration is broken, the spell **dissipates without taking effect**.

#436 read this as two halves in tension with a settled record, and asked whether the half that
does not involve a spell could ship on its own. Both parts of that framing turn out to be
wrong, and the gate closes by saying why rather than by choosing between them.

## Options considered

**Option 1 — model a readied spell as a `LongCast` with a flag that inverts 0065.** Rejected,
and it is the option the gate was written to refuse. It is refused here for a stronger reason
than the gate gave: the two states cannot describe the same spell at all, so there is no flag
to add. See clause 1.

**Option 2 — ship the non-spell half now as its own mechanism, and add the spell half later as
a second one.** Rejected. It accepts the gate's division, and the division is not in the
document — p. 186 has the readier choose *the action* they will take, and casting is one of
the actions. Two mechanisms would put a second path beside a declaration the engine is
accountable for, which is the shape 0005 named a bypass.

**Option 3 — wait for the spell case, and build nothing until it is ready.** Rejected. The
mechanism is p. 186's first three paragraphs and they are buildable now; holding them back
buys nothing, and `ready` being unclaimed is a fact about coverage rather than a reason to
leave the trigger, the Reaction and the declining unwritten.

**Option 4 — build the mechanism, and refuse the Magic action case with its reason until the
held-energy clauses land.** Chosen. It is R32's existing idiom for a rule the engine knows it
does not yet resolve, and the refusal is what keeps the coverage claim honest.

## Decision

**1. A readied spell is not a long cast, and the two can never meet.** p. 186 admits a spell
to being readied only if it has "a casting time of an action" — `CastingTime.ACTION`.
`LongCast` exists only for `CastingTime.MINUTES`, which is what p. 105 is about. The
vocabularies are **disjoint by the document's own admission rule**, so no spell is ever
describable as both and there is no axis on which one reverses the other.

**2. "Cast it as normal" means the casting completes, so 0065 is untouched.** 0065 clause 2
spends the slot when the casting completes. p. 186 spends "any resources used to cast it" at
the moment of casting — which *is* that casting's completion, because a casting time of an
action completes within the action. **Both spend on completion.** The gate's table read "at
the start" against "on completion" and those are two different clocks: the start of the *wait*
is the completion of the *casting*. Nothing inverts.

**3. What is suspended is the effect, not the casting.** `LongCast` holds a casting that has
not finished and has paid nothing. A readied spell holds a casting that **has** finished and
**has** paid, whose effect has not happened. That is a state this engine does not have, and it
is new because of clause 2 rather than in spite of it.

**4. Ready is one mechanism.** p. 186 has the readier "choose the action you will take in
response to that trigger", and the Magic action is one of the actions. There is no non-spell
half and spell half; there is Ready, and a case of it whose chosen action carries three extra
clauses of its own. Building "the non-spell half" is building the mechanism.

**5. The mechanism ships, and the Magic action case refuses with its reason.** R32's idiom for
a rule the engine will not resolve: readying the Magic action is refused, and the refusal names
the clauses that are not built rather than reporting the action as illegal. Silently accepting
it and dropping the held energy would be the quiet direction.

**6. `ready` stays unclaimed while clause 5 refuses.** The shape does not resolve when a case
the document states comes back refused, so the coverage figure does not move and the inventory
is not touched. This is narrower than 0061's disclosed-clause instrument, which counts
sentences inside a shape that *does* resolve; here nothing resolves yet.

**7. The trigger is caller-stated.** "A perceivable circumstance" is a narrative judgement, and
this project has a settled answer for those — the caller says when it fires, as it states a
rest's interruption and a Cover degree. The engine neither reads the circumstance nor decides
that it occurred.

**8. "Or ignore the trigger" is `ReactionDeclined`**, and the reaction economy, the action
cost, and "move up to your Speed" as the readied response are all built. Nothing new is needed
for them.

**9. The Concentration cap is `TurnBoundary.START` attached to a Concentration.** 0049's
vocabulary already distinguishes "before the start" from "before the end", and p. 186's
"up to the start of your next turn" is the former. The *attachment* is new — no Concentration
currently carries an upper bound — but the vocabulary is not, and a second one must not be
invented for it.

**10. "Dissipates without taking effect" is expressible, and was not when the gate was
written.** #436 named it as [#224](https://github.com/eddiefiggie/srd-rules-engine/issues/224)'s
unbuilt shape. #224 has since closed, so an outcome that decides a failure and changes no state
is available and this clause needs nothing new.

## Why

**The gate's central finding was an artefact of comparing two clocks.** It set 0065's "slot
spent on completion" against p. 186's "expending any resources" and called them opposite on
the one axis 0065 decided. They are the same moment described from different ends, and the
sentence that settles it — "to be readied, a spell must have a casting time of an action" — is
in the same paragraph as the one that raised the alarm. Reading the admission rule first
dissolves the conflict instead of adjudicating it. **A record that appears to reverse a settled
one deserves the check that the two are talking about the same thing at all**, and here they
were not: one governs castings of a minute or more, the other governs castings that finish
inside an action, and the document draws that line by hand.

**The division into halves came from the engine's shape, not the document's.** A reader who
knows this codebase sees spellcasting as a subsystem and everything else as the turn loop, so
"Ready a spell" reads as a second feature. p. 186 does not write it that way: it writes one
action whose chooser picks an action, then adds what changes when the chosen one is Magic.
Taking the document's division gives one mechanism and a refused case; taking the engine's
gives two mechanisms that have to agree with each other forever.

**Clause 5 is the restraint.** Ready is worth building now, and the temptation that comes with
building it is to let a readied spell through on the strength of "the casting is built, and the
Reaction is built" — which is true and leaves the held energy nowhere. A spell that is paid for
and then quietly never happens is the failure this whole project exists to make impossible.

## Consequences

**Accepted costs.**

- **`ready` stays unclaimed after a real piece of work lands**, which is the cost #436
  identified and it is real. Coverage does not move; the mechanism does.
- **A caller who readies the Magic action gets a refusal, not an outcome.** That is a stated
  rule the engine declines to resolve, disclosed at the point of use rather than in a document.
- **Held energy is deferred, not designed.** Clause 3 names the state and clause 9 names the
  cap; neither says how they are carried. That is the next piece of work and it is filed, not
  answered here.

**Follow-on effects.**

- Coverage does not move: **146 of 210**. No shape resolves and none is added.
- 0065 is neither superseded nor amended. Its row for #436 should read that the gate closed
  without touching it.
- The mechanism is [#468](https://github.com/eddiefiggie/srd-rules-engine/issues/468) and the
  held-energy state with its capped Concentration is
  [#469](https://github.com/eddiefiggie/srd-rules-engine/issues/469), so the next reader finds
  two scopes rather than a gate.

## Evidence

Read in the official SRD v5.2.1 PDF, pp. 186-187:

- **p. 186**, *Ready [Action]*, whole and including the continuation past the page break —
  quoted above and verified verbatim against the document rather than from the issue body.
- **p. 186**, the admission rule clause 1 rests on: "To be readied, a spell must have a
  casting time of an action."
- **p. 105**, *Longer Casting Times*, already asserted for 0065, which is what `LongCast` is
  built from and what clause 1 shows it cannot reach.

Engine side, read at `0d3555b`:

- `core.spellcasting.CastingTime` holds all four of p. 105's values, and `core.spellcasting.LongCast`
  is reachable only through `CastingTime.MINUTES` (`core.casting`, `long_cast = spell.casting_time
  is CastingTime.MINUTES`). That is clause 1 as code.
- `core.turn_span.TurnBoundary` holds `START` and `END`, which is clause 9's vocabulary.
- `loop.turn.ReactionDeclined` exists and is produced by both reference drivers, which is
  clause 8.
- [#224](https://github.com/eddiefiggie/srd-rules-engine/issues/224) is closed, which is
  clause 10; the gate was written while it was open.

No guard was proved red for this record, because it adds no code. The corruption proofs belong
to the change that builds clauses 5 through 8.

## Status of implementation

**Decided, not built.** A gate closes by producing this record; the work it scopes is filed.

| Clause | State |
|---|---|
| 1 — a readied spell is not a long cast | **Decided.** A finding about two existing vocabularies; nothing to build |
| 2 — "cast it as normal" completes the casting | **Decided.** 0065 stands unchanged |
| 3 — the effect is suspended, not the casting | **Decided, not built.** [#469](https://github.com/eddiefiggie/srd-rules-engine/issues/469) |
| 4 — Ready is one mechanism | **Decided, not built.** [#468](https://github.com/eddiefiggie/srd-rules-engine/issues/468) |
| 5 — the Magic action case refuses with its reason | **Decided, not built.** [#468](https://github.com/eddiefiggie/srd-rules-engine/issues/468), and the refusal comes off in [#469](https://github.com/eddiefiggie/srd-rules-engine/issues/469) |
| 6 — `ready` stays unclaimed while clause 5 refuses | **Decided, not built.** [#468](https://github.com/eddiefiggie/srd-rules-engine/issues/468); the shape is claimed by [#469](https://github.com/eddiefiggie/srd-rules-engine/issues/469) |
| 7 — the trigger is caller-stated | **Decided, not built.** [#468](https://github.com/eddiefiggie/srd-rules-engine/issues/468) |
| 8 — "ignore the trigger" is `ReactionDeclined` | **Decided.** The mechanism exists; this record only names it as the one to use, and [#468](https://github.com/eddiefiggie/srd-rules-engine/issues/468) wires it up |
| 9 — the Concentration cap is `TurnBoundary.START` | **Decided, not built.** [#469](https://github.com/eddiefiggie/srd-rules-engine/issues/469). The vocabulary exists; the attachment does not |
| 10 — "dissipates without taking effect" is expressible | **Decided.** [#224](https://github.com/eddiefiggie/srd-rules-engine/issues/224) built it |
