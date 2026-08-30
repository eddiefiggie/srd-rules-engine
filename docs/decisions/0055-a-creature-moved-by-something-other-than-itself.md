# 0055 — A creature moved by something other than itself

- **Status:** Accepted, 2026-08-30
- **Settles:** [#349](https://github.com/eddiefiggie/srd-rules-engine/issues/349), and with it
  [#345](https://github.com/eddiefiggie/srd-rules-engine/issues/345) and
  [#324](https://github.com/eddiefiggie/srd-rules-engine/issues/324)
- **Requirements:** R4, R15, R18, R30, R31, R32
- **Related:** [0014 — position is three integer coordinates in feet](0014-positional-state.md),
  whose no-float rule is the whole difficulty;
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  clause 1; [0051 — a size is stated, or it is unknown](0051-a-size-is-stated-or-it-is-unknown.md);
  [0047 — a mastery property is unlocked by the wielder](0047-a-mastery-property-is-unlocked-by-the-wielder.md),
  clause 6

## Context

> p. 90, *Push.* If you hit a creature with this weapon, you can push the creature **up to 10
> feet** straight away from yourself if it is Large or smaller.
>
> p. 169, *Thunderwave.* ...a creature takes 2d8 Thunder damage and is **pushed 10 feet** away
> from you.

Twenty-odd rules across a Barbarian feature (p. 29), a Fighter one (p. 52), an Eldritch
Invocation (p. 74), a weapon mastery (p. 90), four spells, a magic item and fourteen stat
blocks. Building it for one caller would build it narrowly.

### The geometry is the gate

0014 makes a `Position` three **integer** feet and is emphatic that distance is never a float.
"Straight away from yourself" is the ray from the anchor through the creature, and `d` feet
along it lands on integer coordinates only when that ray is axis-aligned. A source at
`(0,0,0)` pushing a creature at `(5,5,0)` ten feet lands at `(12.07…, 12.07…, 0)`.

## Options considered

**Option 1 — round to the nearest integer foot.** The obvious one. Rejected as stated, because
it can round *outward*: a push that overshoots carries a creature past a boundary the rule did
not reach.

**Option 2 — the furthest lattice point at or within the distance.** Right for "up to N feet"
and wrong for the exact form, and both are common. Rejected alone; kept as the constraint.

**Option 3 — refuse a direction that is not exactly representable.** Cannot invent anything and
refuses the majority case. Rejected.

**Option 4 — the grid variant's metric.** Rejected: the SRD publishes the grid as optional and
this project treats grid movement as a non-goal *as the default*, so it would make forced
movement work only under a variant.

**Option 5 — the nearest lattice point, bounded by the stated distance.** Chosen: Option 1's
objective under Option 2's constraint.

## Decision

1. **The destination is the lattice point nearest the exact one that is never further from the
   origin than the rule allows.** One objective and one hard constraint.

   *Nearest the exact destination* serves both goals at once — the exact destination lies on
   the ray at exactly the stated distance, so a point near it is near the ray **and** near the
   right distance. One number to minimise rather than two to trade off.

   *Never further* is 0030 clause 1. Overshooting moves a creature further than the rule
   grants; falling short withholds distance it did grant. Only the first manufactures
   something.

2. **`Displacement` records what was asked for and what was achieved**, because they are
   usually different numbers and a reader checking a push against the page needs both (R30).

3. **Ties break on the coordinates**, so a 45-degree push resolves the same way on every run
   (R4).

4. **No ray, no push.** Two creatures sharing a position, or either without one, is refused
   rather than resolved — picking a direction would be the engine deciding where a creature is
   thrown.

5. **A pull stops at the puller.** p. 320 reels a creature *toward* the roper; one that arrived
   on the far side would be somewhere no rule put it.

6. **Forced movement is its own effect kind, not a movement.** p. 185 provokes an Opportunity
   Attack only when a creature "leaves your reach **using its action, its Bonus Action, its
   Reaction, or one of its speeds**", and a shove uses none of those. It spends none of the
   moved creature's allowance either, because it is not the creature moving.

7. **"Up to N feet" is a menu; "N feet" is not.** p. 90's Push offers one entry per five feet
   because the wielder chooses; p. 190's Shove offers one, because p. 190 states the distance.
   Five-foot steps because **every push and pull distance the document names is a multiple of
   five** — its own vocabulary rather than the grid's — and the distances between the steps are
   disclosed as not offered
   ([#351](https://github.com/eddiefiggie/srd-rules-engine/issues/351)).

8. **Push is declared, not automatic.** p. 90 says "you **can** push", so the wielder's choice
   is which key it declares — its own prefix beside Nick's and Cleave's, gated on the property,
   on the feature that unlocks it (0047 clause 6), and on "Large or smaller", which refuses a
   creature nobody sized (0051).

## Why

### Three proofs failed, and two of them were findings

- **The nearest-point objective was untested.** Inverting it changed nothing, because on almost
  every push the distance bound leaves exactly one legal corner and the objective never runs. A
  test over a genuinely multi-candidate case — origin `(0,1,3)`, pushed 10 feet, where `(0,4,12)`
  and `(0,5,12)` are both legal — now covers it.
- **The ordering key was computed in two places**, in the loop and in a helper, and the
  corruption showed the two could disagree with nothing noticing. Replaced by a single `min`
  over one expression.
- The third was my own regex, twice.

### What is not modelled, and is not silently ignored

The document says nothing about a push that meets a wall or an occupied space, so neither does
this. `core.obstructions` could answer where a barrier is; what a push *does* when it reaches
one is a rule the SRD does not state, and inventing an interruption is inventing a rule.

## Consequences

- **`mastery-push` and `forced-movement` become implemented**, 116 of 210, and **weapon
  masteries reach 8 of 8** — the last of p. 90's eight, blocked since the cluster began.
- **`shove-cannot-push-only-knock-prone` is retired**, in the change that builds its rule.
- **One new disclosure**, `push-offered-in-five-foot-steps` (#351).
- **Five clauses added to `scripts/verify_d20_rules.py`**, which reports 270 verified.

## Evidence

- p. 90 — Push, its maximum, and its size qualifier.
- p. 190 — Shove's push, stated as a distance rather than a maximum.
- p. 185 — the Opportunity Attack trigger, which forced movement does not meet.
- p. 169 — Thunderwave, the exact-distance form.
- p. 320 — the roper's pull, the same line read the other way.

## Status of implementation

**Every clause is built** by [#349](https://github.com/eddiefiggie/srd-rules-engine/issues/349).

| Clause | State |
|---|---|
| 1 — nearest lattice point, bounded | **Built.** `core.forced_movement.displaced`, swept over every distance the document names |
| 2 — both numbers recorded | **Built.** `Displacement.derivation` |
| 3 — deterministic ties | **Built.** Asserted over repeated calls |
| 4 — no ray, no push | **Built.** Asserted for co-located creatures |
| 5 — a pull stops at the puller | **Built.** Asserted past and short of the anchor |
| 6 — its own effect kind, no allowance and no Opportunity Attack | **Built.** `EffectKind.MOVED_BY_FORCE` and `with_forced_movement` |
| 7 — a menu for "up to", one entry for an exact distance | **Built.** `push_distances`; the steps are disclosed ([#351](https://github.com/eddiefiggie/srd-rules-engine/issues/351)) |
| 8 — Push is declared and triply gated | **Built.** `core.combat._push` and `_pushes`, asserted on each gate |
