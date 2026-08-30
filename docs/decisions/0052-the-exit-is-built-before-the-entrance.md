# 0052 — The exit is built before the entrance

- **Status:** Accepted, 2026-08-30
- **Settles:** the p. 182 half of [#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335)
- **Requirements:** R1, R15, R18, R30, R31, R32
- **Related:** [0050 — a turn boundary is shared and a mechanism is not](0050-a-turn-boundary-is-shared-and-a-mechanism-is-not.md),
  clause 3, whose one-sweep rule this applies to a second pair of call sites;
  [0051 — a size is stated, or it is unknown](0051-a-size-is-stated-or-it-is-unknown.md),
  which removed the blocker this record's initiators still wait behind;
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  clause 1;
  [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  clause 6

## Context

> p. 182, *Grappling*: A creature can grapple another creature. Characters typically grapple by
> using an Unarmed Strike. Many monsters have special attacks that allow them to quickly
> grapple prey. **However a grapple is initiated, it follows these rules.**

[#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335) asked for p. 190's Grapple
and Shove. Reading p. 182 first changed what the first change should be.

The Grappled *condition* was already two-thirds built — Speed 0 through `speed_zero`, and
"Disadvantage on attack rolls against any target other than the grappler" through
`own_attack_rolls(target_id=...)`, which is relational and so could never have been a flat
field. `Conditions.sources` already recorded who was grappling. What did not exist anywhere was
**a way out**: no escape DC, no escape check, no release, and no answer to either of the two
endings p. 182 states.

### A condition with no exit is worse than one with no entrance

That asymmetry decided the ordering. If p. 190's options had landed first, the engine would
have gained the ability to impose a condition that sets a creature's Speed to 0 and that
nothing in the codebase could lift. The failure modes are not comparable: an engine that cannot
start a grapple merely declines a rule, and an engine that cannot end one ends the session.

So this record builds p. 182 and leaves p. 190 to a second change. That is not a narrowing of
#335 — it is the document's own seam, and the inventory already files the two separately
(`grappling`, p. 182; `unarmed-strike`, p. 190).

## The four endings are not four of a kind

p. 182 states four ways out, and they belong to three different mechanisms:

1. **The escape check.** "A Grappled creature can use its action to make a Strength (Athletics)
   or Dexterity (Acrobatics) check against the grapple's escape DC, ending the condition on
   itself on a success." A declared action, a d20, an outcome — an adjudication.
2. **The grappler is Incapacitated.**
3. **The distance between the two exceeds the grapple's range.**
4. **The grappler releases**, "at any time (no action required)".

2 and 3 are **derived**. Nothing decides them; they are true of the state or they are not, and a
creature whose grappler drops unconscious is not grappled whether or not anyone asks. 4 is a
declaration that rolls nothing and costs nothing.

## Options considered

**Option 1 — retire 2 and 3 on the turn sweep**, where 0050 retires Slow. Rejected, and it is
the option that looked obviously right. Slow is retired on a boundary because it *expires* at
one; these two are conditions on the present state, and a creature held by an unconscious ogre
for the remainder of a turn is held by a rule the document had already stopped applying.

**Option 2 — derive them at read time**, so `Situation` reports the truth. Rejected. It leaves
`Combatant.conditions.held` saying GRAPPLED while the read surface says otherwise — two answers
to one question, which is the drift `grappler_id` living in exactly one place was meant to
avoid.

**Option 3 — apply them wherever state settles.** Chosen. `grapples_released` runs at the end
of `_apply` and inside the turn sweep, and it is one function called twice for 0050 clause 3's
reason.

**Option 4 — give 2 and 3 rule ids and let a caller declare them.** Rejected. A declared ending
is an ending somebody chose, and p. 182 gives nobody that choice.

## Decision

1. **p. 182's rules are built before any initiator**, because a condition the engine can impose
   and cannot lift is the worse of the two incomplete states.

2. **A grapple's terms are the grapple's, and its grappler is the condition's.**
   `Conditions.grapple` holds `escape_dc` and `range_feet` — p. 182 says "the **grapple's**
   escape DC" and "the **grapple's** range", and a stat block states them per attack ("escape
   DC 13", p. 259). Who is holding you stays in `Conditions.sources`, which answers the same
   question for Frightened. Two homes for one identity is how the two come to disagree.

3. **Both are `int | None`, and each `None` refuses rather than defaults.** No escape DC means
   p. 182's check has no target number, so it is not offered — and a grapple with no stated DC
   is not a grapple with no exit, because the other three endings still work. No range means the
   distance ending cannot be evaluated, and the same is true of an encounter tracking no
   positions. Every one of those refusals leaves the condition **held**, which is 0030 clause
   1's direction: lifting a grapple against a bound the engine invented removes a condition the
   rules did not remove, while declining leaves the state a ruleset stated.

4. **The escape DC is stored, never recomputed.** p. 190 derives it from the grappler's Strength
   and Proficiency Bonus *at the moment of the grapple*, and a stat block states it outright.
   Recomputing would ignore what was recorded for the second and drift for the first (R4).

5. **Which check is the escaping creature's choice, and it needs no new seam.** p. 182 offers
   Athletics or Acrobatics and lets the creature pick. Because the escape is an action it
   *declares*, the choice is which action key it declares — one entry per check, the shape the
   Dash uses for p. 180's choice of speed. Each offer carries its bonus in `detail`, because two
   entries an agent cannot tell apart are not a choice.

6. **One rule id for both checks.** p. 182 states one rule that offers a choice, not two rules.
   A rule id per check would report two rules in the ledger where the document has one.

7. **The release is a testless proposal** (0027 clause 6) and states its ending in `outcome`
   rather than `always` — it rolls nothing and charges nothing, so there is no cost for `always`
   to carry. It goes through adjudication rather than a caller mutating state, because R1 admits
   one entry point and an ending that reached state without a ruling would carry no citation and
   no ledger entry.

8. **Two clauses ship disclosed.** p. 182's *Movable* is not built
   ([#340](https://github.com/eddiefiggie/srd-rules-engine/issues/340)), and the release is
   offered only on the grappler's turn where p. 182 says "at any time"
   ([#341](https://github.com/eddiefiggie/srd-rules-engine/issues/341)).

## Why

### The narrowing that is safe, and the one that would not have been

The release is short in its *timing* and correct in everything else: it is p. 182's release,
with p. 182's effect, at p. 182's cost of nothing. The read surface answers what is legal for a
creature *now*, and "now" is a turn — so a creature that is not acting is offered nothing,
which is right for every action that costs something and wrong for the one that costs nothing.

The alternative was to route it through `core.reactions`, which does reach off-turn. That would
have charged a Reaction the document does not charge — trading a missing option for a wrong
one, which is the trade this repository refuses.

### What the escape check does not do, and why the test says so

p. 182 gives failure no consequence. The failed attempt costs the Action and nothing else: the
grapple is not made worse, the terms do not change, and the creature does not move. That last
one is worth asserting because "escape" reads like movement and is not — ending the condition
is not a step, and p. 182 grants no distance.

### `grappling` cannot import `state`, so the derivation lives where state can reach it

`ended_by_circumstance` and `grapples_released` need `EncounterState` and are called from inside
it, so they are defined in `core.state` and re-exported by `core.grappling` — the arrangement
`core.hazards` already uses for the rule ids that key state. The action keys make the same trip
in the other direction: they live in `core.read_surface`, which offers them, and the resolver
module imports them back, exactly as `core.combat` does for Nick's and Cleave's.

## Consequences

- **`grappling` becomes implemented**, 113 of 210. `unarmed-strike` (p. 190) stays false and is
  the rest of #335.
- **Two new pinned disclosures**, both additions:
  `grappled-creature-is-movable-by-the-grappler` on the condition, and
  `grapple-release-offered-only-on-the-grapplers-turn` at the read surface. The condition half
  of the pin derives from `EFFECTS` and caught the first the moment it was added; the other half
  derives from the source since [#334](https://github.com/eddiefiggie/srd-rules-engine/issues/334)
  and caught the second.
- **Eight clauses added to `scripts/verify_d20_rules.py`**, which reports 252 verified.
- **p. 190's Grapple and Shove remain unbuilt**, and their blocker is now precisely one thing:
  the target of a forced save chooses between two abilities ("it chooses which") and declares
  nothing, so the choice cannot ride on an action key the way the escape check's does. That is
  the seam #335 has left to settle, and it is stated here so the next change starts from it
  rather than rediscovering it.

## Evidence

Every clause is matched against the printed page by `scripts/verify_d20_rules.py`.

- p. 182 — "However a grapple is initiated, it follows these rules"; the escape check in full;
  the two derived endings, where the distance one reads **exceeds** rather than reaches; the
  release and its "no action required"; and all three clauses of the Grappled condition.
- p. 259 — a stat block stating an escape DC outright, which is why the DC is stored.

## Status of implementation

**Every clause is built** by [#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335)'s
p. 182 half.

| Clause | State |
|---|---|
| 1 — the exit before the entrance | **Built.** `core.grappling`, with p. 190's initiators left to the rest of [#335](https://github.com/eddiefiggie/srd-rules-engine/issues/335) |
| 2 — terms on the grapple, grappler on the condition | **Built.** `Conditions.grapple` and `Conditions.sources`, asserted together |
| 3 — each `None` refuses and leaves the condition held | **Built.** Asserted for an unstated DC, an unstated range, an encounter with no positions, and a grappler that left |
| 4 — the escape DC is stored, never recomputed | **Built.** `escape_resolver` reads it from the condition; asserted against a DC of 17 |
| 5 — one offer per check, each carrying its bonus | **Built.** `legal_actions`, asserted with a creature proficient in one skill and not the other |
| 6 — one rule id for both checks | **Built.** `grappling_resolvers` dispatches on the action key |
| 7 — the release is testless and states its ending in `outcome` | **Built.** `release_resolver` (0027 clause 6) |
| 8 — two clauses disclosed | **Built as disclosures.** The rules are unbuilt and tracked by [#340](https://github.com/eddiefiggie/srd-rules-engine/issues/340) and [#341](https://github.com/eddiefiggie/srd-rules-engine/issues/341) |
