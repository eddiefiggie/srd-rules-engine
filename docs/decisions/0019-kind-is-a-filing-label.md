# 0019 — `kind` is a filing label, not a model, and stays one axis

- **Status:** Accepted, 2026-08-23
- **Settles:** [#84](https://github.com/eddiefiggie/srd-rules-engine/issues/84)
- **Requirements:** R17
- **Related:** [0013 — effect-shape normalisation](0013-effect-shape-normalisation.md), which closed
  the enum and deferred this

## Context

0013 closed `kind` as a nineteen-value enum with a guard, and deliberately left one question open:
`kind` appears to conflate **what a shape is** (a condition, a resource, an action) with **what it
applies to** (a d20 test, damage, movement). Heroic Inspiration was `resource` while
`reroll-a-natural-one` was `test-modifier`, though the mechanism is both. 0013's Q5 merge removed
that particular collision without touching the conflation behind it.

#84 asked whether to split `kind` into two fields, rename it, or replace it with a tag set.

## What the measurements showed

**Bucketing the nineteen values by axis splits them 88 / 123** — close enough to even that the
conflation is structural rather than a couple of edge cases. So far this supports splitting.

**But "what it applies to" is plural.** Trying the second axis on real entries:

| Shape | What it is | What it applies to |
|---|---|---|
| `prone` | condition | attack rolls **and** movement |
| `exhaustion` | condition | d20 tests **and** Speed |
| `weapon-finesse` | weapon property | attack **and** damage rolls |

A second single-valued field cannot express any of those. Two enums is the wrong shape, which
leaves a tag set — and a tag set is the option #84 itself called "hardest to guard", in a project
whose defence against drift is that every enum is closed and checked.

**And `kind` drives nothing.** Searching every read of a `Shape.kind` across `src/` returns exactly
one line:

```python
lines.append(f"  [{shape.kind}] {shape.name} — {shape.reference}")
```

That is `coverage_report`, printing it in brackets. Every other `.kind` in the engine belongs to a
different type — `Finding.kind`, `D20Test.kind`, `Effect.kind`.

## The reframing that follows

`kind` is not a taxonomy of mechanics. It is a **filing label on a catalogue**, read once, for
display, so a person scanning 211 shapes can see what is covered.

The semantic model the split would supposedly build **already exists, in code**: `ConditionEffects`
says exactly what Prone does to attack rolls, with typed fields, and it is what the engine consults.
Splitting `kind` would produce a second, weaker description of behaviour beside the real one — and
0013's own finding was that a description living apart from the thing it describes goes stale
silently.

## Options considered

**Two enums.** Rejected: the applies-to axis is plural, so it cannot be one value.

**A tag set.** Rejected: it re-classifies all 211 shapes and bumps the schema to enrich a field read
once for display, and it trades a closed checked enum for an open set in the one place this project
has been bitten by drift twice.

**Rename `kind` to something narrower.** Considered and folded into the decision below rather than
taken on its own — a rename alone changes what a reader assumes without changing what anybody may
rely on.

**Keep one axis, state what it is for, and make that checkable.** Chosen.

## Decision

**1. `kind` stays one axis and one closed enum.** No schema change, no re-classification.

**2. It answers a filing question**: *which part of the rules does this shape belong to, for the
purpose of measuring coverage*. It is not a claim about what the shape does, and nothing may treat
it as one.

**3. The tie-break, for a shape that could be filed two ways: file it under the subsystem that
implements it, or would.** Prone is `condition` because `core.conditions` is where it lives.
`die-replacement` is `test-modifier` because it lives in `core.d20`. This is determinate, it is
useful for the thing `kind` is actually for, and it removes the judgement call that #84 predicted
would be settled differently by each new author.

**4. A guard asserts that no engine code branches on `Shape.kind`.** The claim "it is a label, not a
model" is only worth making if it stays true, and the way it would stop being true is somebody
writing `if shape.kind == ...` in a moment of convenience. Both branching forms are checked — an
`if` and a `match` — because a `match` on a string label is the more natural way to write this in
modern Python, and the first version of the guard walked only comparisons and let one through.

## Why

### The evidence inverted the question

#84 was written as "the conflation is real, how do we fix it". The conflation *is* real. What the
measurement added is that it does not matter: a field read once for display does not need to be a
correct ontology, and making it one would cost 211 re-classifications and a schema bump to improve a
`print`.

Recording that is the useful outcome. The next person to notice the conflation will notice it
correctly, and this record is what stops them spending a week on it.

### Guarding the claim is the part that lasts

A decision saying "this field means nothing operational" degrades the first time a shortcut needs a
category. The guard makes the degradation visible — which is the same move as `0018`'s enumerated
API surface and `0013`'s closed enum, and for the same reason: this project's defences are the ones
that turn red.

## Consequences

**Accepted costs.**

- **The conflation stays.** `affliction` still names a delivery route where `condition` names a
  category, and a reader looking for a consistent ontology will not find one. The record says it is
  not one rather than pretending otherwise.
- **The tie-break points at implementation, so it can move.** If a shape's implementation moves
  between modules, its most natural filing changes. That is acceptable for a coverage index and
  would not be for a schema consumers read.
- **The guard is a name-keyed AST heuristic.** It recognises a shape by the receiver being called
  `shape`, `s`, or `entry`, so a branch written with a differently-named variable would pass.
  Tighter would need type inference. Stated rather than implied, because a guard trusted beyond
  what it inspects is the failure this project has already had twice.
- **A future need for real classification is not served.** If something ever genuinely needs to ask
  "what does this shape apply to", it needs a new field designed for that, and this record should be
  superseded rather than stretched.

**Follow-on effects.**

- #84 closes without a schema change, and the `kind_values` guard from 0013 continues unchanged.

## Evidence

Nineteen values, bucketed 88 / 123 by axis. Three sampled shapes (`prone`, `exhaustion`,
`weapon-finesse`) each have a plural applies-to. One read of `Shape.kind` in `src/`, in
`coverage_report`, for display. Counts taken on 2026-08-23 against 211 shapes.

## Status of implementation

**Implemented with this record**: the filing rule is documented in `scripts/derive_effect_shapes.py`
and `core.inventory`, and `tests/test_effect_shape_inventory.py` asserts that no module under `src/`
branches on a shape's `kind`, in either an `if` or a `match`. Both were proven red: a comparison
against the pre-change tree, and a `match shape.kind:` that the comparison-only first draft passed.
