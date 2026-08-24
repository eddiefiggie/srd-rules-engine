# 0017 — Verification is a pattern asserted against the document, and it does not cover modelling

- **Status:** Accepted, 2026-08-23
- **Supersedes:** [0003](0003-seed-and-verification.md) **in part** — clause 2's "verified by a
  human against it", and the sentences in its Why and Consequences that rest on it. Everything else
  0003 settled stands.
- **Settles:** the wording drift found while landing [#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21)
- **Requirements:** R31, R32
- **Related:** [0012 — fixture provenance](0012-fixture-provenance.md), which uses the same
  verification block; [0013](0013-effect-shape-normalisation.md), whose evidence was gathered this way

## Context

0003 said every entry "is verified by a human against it", and that an entry marked verified means
"a human compared this to a named section of a named document."

That is not what the project does. Every SRD-derived value here — the effect-shape inventory, the
advantage and reroll rules, the conditions, the movement costs, the areas, and now the bestiary — is
verified by a **pattern that must match the printed page**, run by a script against the PDF.
`scripts/verify_d20_rules.py` holds 87 such clauses and exits non-zero if any stops matching;
`derive_effect_shapes.py` and `derive_bestiary.py` refuse to emit an entry whose pattern fails.

The record and the practice disagreed. That is exactly the drift decision records exist to prevent,
so it gets a record rather than a quiet edit.

## The distinction 0003 was actually making

0003's argument was never about humanity. Read in context, "a human compared this to a named section
of a named document" is doing its work in the second half: the reference is the **official document**,
identified by revision, rather than a seed of unknown fidelity mixing two documents under one
version string. That property is untouched by who or what does the comparing.

## Options considered

**Change the practice to match the record** — read every value by eye and record that. Rejected: it
is strictly weaker. A human read happens once and cannot notice a later revision rewording the
sentence it rested on; a pattern is re-runnable and goes red.

**Say "verification is mechanical" and stop there.** Rejected as an overclaim, for the reason below.

**Name the two halves separately.** Chosen.

## Decision

**1. Verification is a pattern asserted against the official SRD v5.2.1 PDF.** It is machine-checked
and re-runnable, and it is stronger than a human read on the axis that matters most — a dated claim
that cannot notice its own staleness is the failure `verify_d20_rules.py` exists to prevent.

**2. It covers transcription, not modelling.** A pattern proves a sentence or a value appears on the
cited page. It cannot prove the value was put in the right field, that the effect shape chosen is the
right one, or that a rule was read the way the document meant. Those are **editorial** judgements and
they remain human.

This is the split the derivation scripts already state in their own docstrings — "Enumeration is
mechanical... Classification is editorial" — promoted from a comment to a decision.

**3. `Verification` records which was done.** `method` is `asserted` where a pattern checks the
document, `editorial` where a human made a modelling judgement, and `None` where neither has been
recorded. Prose in a record that the data cannot express is the failure 0013 named; this is the same
fix applied to itself.

**4. 0003's clause 2 is superseded only in its "by a human" wording.** The official PDF remaining the
only verification reference, per-entry state, the loader gate, and naming the revision all stand.

## Why

### The overclaim matters more than the underclaim

"Verification is mechanical" invites a reader to believe the numbers were checked *and* correctly
understood. They were not: a pattern would happily confirm that `AC 17` appears on p. 258 while the
derivation wrote 17 into `hit_points`. Nothing in the assertion catches that — a person reading the
result does.

That is not hypothetical. Landing #21, a guard written to enforce the no-prose boundary went green on
the exact corruption it existed to catch, because it tested content rather than shape. Mechanical
checks fail in this direction: they confirm what they were pointed at, precisely, and say nothing
about whether it was the right thing to point at.

### Recording the method costs almost nothing and prevents the same drift

An entry saying `verified` without saying *how* invites the next reader to assume whichever meaning
suits them. The field is one enum, defaulted, and it makes the distinction checkable rather than
rhetorical.

## Consequences

**Accepted costs.**

- `Verification` grows a field, so every existing block gains a default. Where the method is known it
  is set; where it is not, `None` is honest rather than a guess.
- "Editorial" is not itself verified by anything. A modelling judgement is recorded as having been
  made, not as having been made correctly — which is what a decision record and a code review are for.
- 0003 now has to be read alongside this record. That is the cost of immutability, and it is the
  intended one.

**Follow-on effects.**

- 0003's Status line points here, so a reader arriving at the old record is not misled.
- Content population (#21) can state its verification method per entry rather than inheriting an
  ambiguous claim.

## Evidence

`scripts/verify_d20_rules.py` — 87 clauses, each a pattern that must match a cited printed page, run
against the official PDF outside CI. `scripts/derive_effect_shapes.py` and `derive_bestiary.py`
refuse to emit an entry whose pattern fails, and mark it `excluded` with the reason.

The counter-example is in this session's history: three separate guards of mine passed while
inspecting nothing — a self-referential band assertion, a corrupted clause description rather than
its pattern, and the no-prose content heuristic. Each was mechanical and each was satisfied. Only
running them against a deliberate corruption found it.

## Status of implementation

**Implemented with this record.** `VerificationMethod` is added to `core.rules`, every
SRD-derived verification block in the engine records `asserted`, and 0003's header points here.
