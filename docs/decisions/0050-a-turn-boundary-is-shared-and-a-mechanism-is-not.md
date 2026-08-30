# 0050 — A turn boundary is shared and a mechanism is not

- **Status:** Accepted, 2026-08-30
- **Settles:** the design half of [#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322)
- **Requirements:** R15, R18, R31
- **Related:** [0049 — advantage that outlives its roll](0049-advantage-that-outlives-its-roll.md),
  whose boundary this extracts and whose clause 3 it deliberately does not follow;
  [0047 — a mastery property is unlocked by the wielder](0047-a-mastery-property-is-unlocked-by-the-wielder.md),
  clause 6

## Context

> **Slow.** If you hit a creature with this weapon **and deal damage to it**, you can reduce
> its Speed by 10 feet until the **start** of your next turn. If the creature is hit more than
> once by weapons that have this property, the Speed reduction **doesn't exceed 10 feet**.

Slow borrows one half from each neighbour: Vex's trigger, Sap's window. Its own contribution is
a cap across sources, which no other mastery has.

Sap's window is the interesting inheritance. 0049 built `TurnBoundary` and `is_live` because
nothing counted to the **start** of a turn, and it put them in `core.pending_rolls` — a module
about advantage. Slow needs the same window and is not about rolls at all.

## Decision

**1. The boundary is extracted; the mechanism is not shared.** `TurnBoundary` and `is_live`
move to `core.turn_span`, and `core.pending_rolls` re-exports both so nothing 0049 shipped
moved for a reader. `is_live` becomes structural over a `TurnBounded` protocol rather than
typed to one class, because the two things that satisfy it share **no behaviour**: a
`PendingAdvantage` is *spent* by the roll it applies to, and a `SpeedReduction` simply stands
until its window closes. They agree about how a window is named and about nothing else.

Merging them into one structure was available and is refused for the reason 0048 merged two
queues: same cardinality means one structure, and these do not have the same lifecycle at all.

**2. The reduction is held on the creature, not on the encounter — and this reverses 0049
clause 3 knowingly.** Speed is read through `Combatant.effective_speeds`, a property that by
design sees no encounter. Deriving liveness there would mean threading the turn order into
every reader of a creature's Speed and putting turn-order knowledge inside a property about
one creature.

`Combatant.conditions` already modifies Speed from exactly this seam — Grappled sets it to 0,
Exhaustion reduces it — and is retired by a turn phase. A Slow reduction joins them there
rather than opening a second route to the same number.

**The cost is that liveness is applied rather than derived**, which 0049 clause 3 declined for
advantage, and the trade-off lands differently because the reading paths differ: there the
consumer was the attack resolver, which already had state in hand, so deriving cost nothing.
The failure directions differ too. A missed sweep there would grant Advantage past its window;
here it leaves a creature slowed past its own. Neither is good and only the first invents
something.

**3. One sweep, both mechanisms.** `EncounterState._swept` retires the advantage tokens and the
Speed reductions through the same function and the same predicate. Two sweeps is how one gets
remembered and the other forgotten — 0036 clause 6's rule, and the reason it matters more here
is that the sweep *is* the rule for Slow and only hygiene for advantage.

**4. The cap is Slow's, not the Speed's.** "the Speed reduction doesn't exceed 10 feet" bounds
*this property*: a future rule taking 15 feet is not quietly limited by p. 90's sentence. So
`slow_feet_taken` sums the reductions whose `rule_id` is Slow's and caps that sum, rather than
capping every reduction a creature carries.

Two Slow hits therefore take ten feet **between them**, and each keeps its own expiry — so a
creature struck by two wielders stays slowed until the later boundary passes. A per-hit
reduction takes twenty, and a single-attacker fixture cannot tell the two apart.

**5. It reaches the walking Speed only.** p. 90 says "its **Speed**", which p. 188 makes the
walking one. A reduction reaching a Fly or Swim Speed would be a rule the sentence does not
state (R31). Floored at zero, because a Speed is a distance and not a debt.

## Consequences

The inventory moves to **110 of 210**. Weapon masteries are **7 of 8** — only Push remains
([#324](https://github.com/eddiefiggie/srd-rules-engine/issues/324)), blocked on a Size nothing
carries ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)) and on forced
movement.

**`core.turn_span` is now where a third turn-bounded mechanism starts.** Several conditions and
spells end at a turn boundary the `Duration` axis cannot count, and none of them now needs a
vocabulary of its own.

## Status of implementation

**Every clause is built** by [#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322).

| Clause | State |
|---|---|
| 1 — the boundary extracted, the mechanism not shared | **Built.** `core.turn_span`, with `TurnBounded` a protocol and `core.pending_rolls` re-exporting ([#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322)) |
| 2 — held on the creature, liveness applied | **Built.** `Combatant.speed_reductions`, read by `effective_speeds` ([#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322)) |
| 3 — one sweep, both mechanisms | **Built.** `EncounterState._swept`, asserted over both in one test ([#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322)) |
| 4 — the cap is Slow's, across sources | **Built.** `slow_feet_taken`, asserted with two reductions and with a foreign one ([#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322)) |
| 5 — the walking Speed only, floored at zero | **Built.** Asserted against a creature with Fly and Swim speeds, and one with Speed 5 ([#322](https://github.com/eddiefiggie/srd-rules-engine/issues/322)) |
