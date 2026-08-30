# 0056 — A move is refused where it is made

- **Status:** Accepted, 2026-08-30
- **Settles:** [#350](https://github.com/eddiefiggie/srd-rules-engine/issues/350)
- **Requirements:** R1, R14, R18, R32
- **Related:** [0052 — the exit is built before the entrance](0052-the-exit-is-built-before-the-entrance.md),
  whose ordering rule is why half of #350 is deferred;
  [0055 — a creature moved by something other than itself](0055-a-creature-moved-by-something-other-than-itself.md),
  which this is deliberately *not* built on;
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  clause 1

## Context

> p. 182, *Frightened*: **Can't Approach.** You can't willingly move closer to the source of
> fear.

Disclosed as `cannot-willingly-approach-the-source` since the condition shipped, and the
disclosure's stated reason was wrong twice over.

**It said the clause needed a direction relative to a creature**, and repeated that in
[#345](https://github.com/eddiefiggie/srd-rules-engine/issues/345) and
[#324](https://github.com/eddiefiggie/srd-rules-engine/issues/324) as a dependency on the
forced-movement primitive. "Closer" is a comparison of two distances:

```python
squared_distance(destination, source) < squared_distance(origin, source)
```

`core.position` has answered that exactly — without a square root — since 0014, and the source
of fear has been recorded on the condition since #192. Both operands were available the whole
time.

**What was actually missing was a refusal.** Nothing in this engine told a caller a move was
illegal.

### The tension #350 stated, and why it is not one

#350 framed the choice as: check legality at the read surface, which cannot enumerate every
destination; or refuse at the state transition, which "puts a rule outside the one adjudication
entry point, R1".

The second horn is false, and the evidence is in the method itself. `with_movement` **already
refuses three ways** — a creature with no position, a mode the creature has no speed for, and a
cost exceeding what is left:

> Refused when the cost exceeds what is left, because a move a creature cannot afford is not a
> move it makes slowly — it is one the rules do not allow.

R1 says no other API "produces, modifies, or implies a **result**". A refusal produces no
result; it is the absence of one. Enforcing a fourth rule where three are already enforced is
consistency, not a new exception.

## Decision

1. **A movement rule is enforced in `EncounterState.with_movement`**, beside the three
   refusals already there. A refusal is not a result, so R1 is untouched.

2. **p. 182's Can't Approach is built** as a comparison of two distances, and needs no
   direction, no ray, and nothing from 0055.

3. **"Closer", not "toward".** A creature circling a source of fear at a constant distance is
   doing something p. 182 permits, and a refusal keyed on direction would stop it.

4. **A source whose distance cannot be measured forbids nothing** — one that has left the
   encounter, one nobody placed, one nobody recorded. Refusing a move on a distance the engine
   could not measure would forbid what the rules may permit, which is the direction `_within`
   already takes at the read surface.

5. **`with_forced_movement` is not subject to it**, and that is the word the rule turns on.
   p. 182 forbids a creature moving itself closer and says nothing about a creature being
   *thrown* closer. **Willingly** is what decides which of the two methods carries the check.

6. **Prone's two clauses are deliberately not built**, and 0052's ordering rule is why —
   see below. [#353](https://github.com/eddiefiggie/srd-rules-engine/issues/353).

## Why

### The disclosure was wrong, not merely stale

`unenforced_clauses` exists so a gap is named rather than discovered. This one was named and
**misdiagnosed**, and the misdiagnosis propagated: two issues repeated it as a dependency on a
primitive that had nothing to do with it, and it survived until the forced-movement gate made
someone check.

A disclosure is a claim about *why* something is missing, and that claim is as capable of being
wrong as any other. Nothing guards it — `tests/test_disclosures_are_pinned.py` holds the
strings and says explicitly that whether a clause's rule is genuinely unbuilt is the judgement
no machine makes.

### Prone waits, because the restriction without the exit is a trap

p. 186 gives a Prone creature two movement options: crawl, or spend half its Speed to stand.
They are one rule — the restriction and the way out of it — and building the refusal alone
would leave a creature able to crawl and **unable to stand**, held in a state the document
gives it an exit from.

That is 0052's asymmetry exactly: an engine that cannot start something declines a rule; one
that cannot end something ends the session. Righting yourself is also a *capability* rather than
a refusal, and it spends movement without covering ground, which nothing here expresses. So
both clauses stay disclosed and go together (#353).

## Consequences

- **`cannot-willingly-approach-the-source` is retired** in the change that builds its rule, and
  the two are asserted together.
- **Frightened now discloses nothing at all.** `line-of-sight-qualifier` left in #192 and this
  one leaves here, so the condition is fully enforced — the first of the fifteen to reach that
  state after having disclosed something.
- **Three tests that used Frightened as the example of an unenforced clause** now assert the
  whole list rather than one membership, so a third clause appearing would not pass unnoticed.
- **No coverage figure moves.** `frightened` was already claimed, correctly by R17's terms: the
  condition resolved and one clause reached nothing. The same shape 0054 recorded.

## Evidence

- p. 182 — "You can't **willingly** move closer to the source of fear", the whole of clause 2
  and clause 5.
- p. 186 — Prone's two movement options, which are why clause 6 defers.

## Status of implementation

**Every clause is built** by [#350](https://github.com/eddiefiggie/srd-rules-engine/issues/350),
except clause 6, which defers by design.

| Clause | State |
|---|---|
| 1 — enforced in `with_movement` | **Built.** Beside the three refusals already there |
| 2 — Can't Approach | **Built.** `EncounterState._fear_approached` |
| 3 — closer, not toward | **Built.** Asserted with a creature circling at constant distance |
| 4 — an unmeasurable source forbids nothing | **Built.** Asserted for a source gone, unplaced and unrecorded |
| 5 — a push is not willing | **Built.** Asserted through `with_forced_movement` |
| 6 — Prone waits for its exit | **Deferred by design.** Both clauses stay disclosed, and [#353](https://github.com/eddiefiggie/srd-rules-engine/issues/353) builds them together |
