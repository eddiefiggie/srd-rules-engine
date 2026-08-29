# 0043 — One action, several attacks, and one swap

- **Status:** Accepted, 2026-08-29
- **Settles:** the design half of [#289](https://github.com/eddiefiggie/srd-rules-engine/issues/289),
  which stays open as the build, and answers
  [0042](0042-equipping-rides-on-the-attack-that-permits-it.md) clause 6
- **Requirements:** R1, R15, R18, R31, R32
- **Related:** [0042 — equipping rides on the attack that permits it](0042-equipping-rides-on-the-attack-that-permits-it.md),
  whose clause 6 this answers; [0040 — a weapon is an item](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  clause 2, whose split between engine mechanism and ruleset content applies here;
  [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md)

## Context

0042 clause 6 recorded a silence and named the two shapes that would make it reachable.
`multiattack` is one of them, and p. 257 is why:

> **Multiattack.** Some creatures can make more than one attack **when they take the Attack
> action**. Such creatures have the Multiattack entry in the "Actions" section of their stat
> block. This entry details the attacks a creature can make, as well as any additional
> abilities it can use, **as part of the Attack action**.

**Multiattack is not a second action; it is the Attack action buying more than one attack
roll.** That settles the question 0042 clause 6 left open in the direction that makes it
*bite*: p. 177 grants "one weapon when you make an attack as part of this action", so a
creature with three attacks has three occasions to swap in a single turn — while p. 13 grants
"one object or feature of the environment for free" per turn and sends the second to the
Utilize action.

The engine has been carrying the other half of this since the action economy landed, and said
so. `attack_resolver`:

> **Extra Attack would make this wrong**, and it is a class feature this repository ships none
> of: a feature that "gives you more than one attack as part of the Attack action" (p. 177)
> would need the Action charged once for several rolls. There is nothing to model it with
> today, and the day there is, this is the line that has to change.

That day is this issue.

## Options considered

**Option 1 — the two budgets are independent: three attacks buy three swaps.** Rejected. It
is the literal reading of p. 177 in isolation and it is still a choice the document does not
make: p. 191 puts drawing a sword during the Attack action inside the object-interaction
frame, and if that frame applies then p. 13's cap does too.

**Option 2 — the budgets are shared: p. 177's swap *is* p. 13's free interaction.** Rejected
for the mirror reason. It reads p. 177's "when you make an attack" as decoration, which is a
poor way to treat a phrase the document chose over "on your turn".

**Option 3 — refuse Multiattack until the document is clearer.** Rejected. The silence is
about the *swap*, not about the attacks, and refusing a whole mechanic to avoid a question
about an adjacent one is a larger exclusion than the gap warrants (R32 asks for the gap to be
disclosed, not widened).

**Option 4 — the intersection: at most one swap per turn, whatever the attack count.**
Chosen.

## Decision

**1. Multiattack is the Attack action, and one Action buys several attack rolls.** p. 257
says so outright, so this is not a new action kind, not a Bonus Action, and not a second
charge against the economy. The Action is spent once; the attacks it bought are counted down.

**2. How many attacks, and which, is ruleset data on the creature.** p. 257: "This entry
details the attacks a creature can make, as well as any additional abilities it can use." The
details are per-monster — the aboleth's "two Tentacle attacks and uses either Consume Memories
or Dominate Mind", the assassin's "three attacks, using Shortsword or Light Crossbow **in any
combination**", the balor's "one Flame Whip attack and one Lightning Blade attack" — and the
stat blocks are content this repository ships six of (#99, #21). So the engine holds *how many
remain and whether this attack is among the permitted ones*, and a ruleset says what the entry
was. The same split as 0040 clause 2's proficiency-by-id: the engine holds what a rule reads,
the ruleset holds what a table says.

**3. At most one weapon swap per turn, whatever the attack count. This is 0042 clause 6's
answer, and it is an intersection rather than a choice between the two readings.**

One swap is legal under **both**: independent budgets permit it, and a shared budget permits
it. Two swaps are legal under exactly one, and the document does not say which. So the engine
offers what both readings allow and refuses what only one does — which is the only option here
that cannot produce an outcome the rules forbid.

**This narrows a mechanic and the narrowing is disclosed, not silent.** A three-attack creature
that has already swapped is offered no second swap, and the read surface says the cap is the
engine's rather than the document's. `free-object-interaction-unmodelled` is replaced by a
clause that names what was decided instead of what was skipped.

**4. The per-turn swap count is state, and it is the third structure of its kind.** It joins
`discharged`, `slots_expended_this_turn` and `light_attacks_this_turn`, and it means a fourth
thing: not an obligation met, nor a resource spent, nor what was done and with what, but **how
many times a per-turn allowance has been drawn on**. A count rather than a set, because the
question is "how many" and a set of actors cannot answer it.

**5. Nothing here models p. 13's free interaction, and clause 6 stays open in that direction.**
This decides only the swap's cap. Whether a creature may *also* open a door is still
unanswerable, because the engine has no route to a general object interaction —
[#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) is still the shape that
makes that half reachable, and it inherits a narrower question than it had: not "how do these
compose" but "does the one swap this engine permits also spend the free interaction".

## Why

**Clause 3 is the clause this record exists for, and the intersection is the move worth
naming.** Faced with two defensible readings, the reflex is to pick the better-argued one and
write it down with its reasoning — which is what Options 1 and 2 are, and either would survive
review. Both are inventions: a composition rule the document does not state, made
indistinguishable from a printed one by being inside a ruling.

The intersection is available because the readings **overlap** rather than contradict. That is
not always true — [0031](0031-a-contradiction-in-the-document-is-an-absent-rule.md) covers the
case where two clauses genuinely conflict and the rule is absent — and it is worth
distinguishing: here the readings agree about one swap and disagree only past it, so there is a
non-empty answer both permit. **When two readings overlap, the overlap is a rule; only the
disagreement is a silence.**

**Clause 1 is a line the tree has been waiting for, and it was flagged rather than forgotten.**
The comment in `attack_resolver` names this exact feature, says why it would be wrong, and says
which line changes. That is what a disclosed limitation is supposed to do, and it is worth
noting that it worked — the constraint was found by reading the code that documented it rather
than by a bug report.

**Clause 2 keeps a bestiary out of the engine.** The temptation with Multiattack is to model
the *compositions* — "two of these and one of those", "any combination" — because they look
like a small grammar. They are content, and a grammar for them in the engine would be a weapon
table by another name (R31).

## Consequences

**Accepted costs.**

- **A multi-attacking creature may swap only once per turn**, which is possibly narrower than
  the rules allow. Disclosed, and the direction that cannot manufacture a legal-looking
  outcome the document may forbid.
- **The engine cannot say what a monster's Multiattack *is*** — only how many attacks remain
  and whether one is permitted. A ruleset that supplies nothing gets one attack per action,
  which is the pre-existing behaviour and stays correct.
- **0042 clause 6 is half-answered**, and the remaining half is narrower rather than gone.
  Recording it as narrowed rather than closed is the honest state.

**Follow-on effects.**

- **[#271](https://github.com/eddiefiggie/srd-rules-engine/issues/271)'s Loading becomes
  reachable.** p. 90 caps a Loading weapon at one shot "regardless of the number of attacks you
  can normally make", and that final clause has had nothing to bite on. This is what gives it
  something.
- **p. 179's concentration debt gets its first real exercise.** `concentration_saves_owed` is a
  sequence rather than a set because "a creature struck twice by a Multiattack owes two" — the
  reasoning anticipated this shape and nothing has exercised it.
- **[#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) inherits a narrower
  question**, stated in clause 5.
- **Coverage moves by one** when the build lands: `multiattack` resolves.

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 12**, **p. 13** (the free-interaction
budget, whole), **p. 177** (*Attack [Action]*, whole), **p. 191** (*Utilize [Action]*),
**p. 255** (*Running a Monster*, the Multiattack paragraph), **p. 257** (*Multiattack*, whole),
and the entries on **pp. 258, 259, 260, 261, 262** for the shapes a Multiattack entry takes.

**The sweep behind clause 2.** Every `Multiattack` occurrence in the document was read. Outside
the stat blocks there are exactly three kinds: p. 61's *Multiattack Defense*, a Ranger feature
and a different term; p. 255's advice to a GM about when to use it; and p. 257's definition.
Everything else is a monster or a summoned creature stating its own composition — including
pp. 136, 166 and 232, where a **spell's** summoned creature has one, which is why the shape has
to live on the creature rather than in the bestiary loader.

In the tree:

- `attack_resolver`'s `always` charges `ActionKind.ACTION` once per attack, with a comment
  naming Extra Attack as the feature that would make it wrong.
- `EncounterState` carries `discharged`, `slots_expended_this_turn` and
  `light_attacks_this_turn`, each cleared or not by `advanced_turn` according to what it means.
- `Situation.unenforced_clauses` carries `free-object-interaction-unmodelled` as of #283.
- `multiattack` is `implemented: false` in `effect_shapes.json`.

## Status of implementation

**Clauses 1 to 4 are built** by [#289](https://github.com/eddiefiggie/srd-rules-engine/issues/289). Clause 5 is decided and its remaining half is
held by [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288).

**Two things the build found that this record did not.**

**Clause 4 conflated two structures.** It argued for a count rather than a set, and that is
right for the attack tally and wrong for the swap beside it: the swap's cap is *one*, so the
only question is whether this creature has taken it, and a set of actors answers exactly that.
A count there would carry a number nothing may read past 1. `attacks_this_turn` is the count
the clause was reasoning about; `swaps_this_turn` is a set.

**"Rolls remain" is not "the Action bought them."** `attacks_remaining` counts rolls and cannot
say what the Action was spent on, so a creature that took the Dodge action had three rolls
remaining by arithmetic and was offered an attack. Having **already attacked this turn** is
what says the Action went to the Attack action, and the offer turns on that instead.

| Clause | State |
|---|---|
| 1 — Multiattack is the Attack action; one Action buys several rolls | **Built.** `action_spent` is emitted only on the turn's first roll, and the attack stays on the menu while rolls remain ([#289](https://github.com/eddiefiggie/srd-rules-engine/issues/289)) |
| 2 — how many and which is ruleset data on the creature | **Built** as `Combatant.multiattack`. `permitted` empty means *any held weapon*, the reading that refuses nothing; a fixed composition like the balor's one-each is not expressible and is disclosed ([#289](https://github.com/eddiefiggie/srd-rules-engine/issues/289)) |
| 3 — at most one swap per turn, as the intersection of two readings | **Built**, and named as the engine's cap in `Situation.unenforced_clauses`. p. 191's Unconscious drop deliberately does not spend it, which is why `WEAPON_SWAPPED` is its own effect ([#289](https://github.com/eddiefiggie/srd-rules-engine/issues/289)) |
| 4 — the swap count is per-turn state | **Built, and the clause gained a finding.** Two structures, not one: `attacks_this_turn` is a count and `swaps_this_turn` is a set, because a cap of one asks a different question ([#289](https://github.com/eddiefiggie/srd-rules-engine/issues/289)) |
| 5 — p. 13's free interaction stays unmodelled, and clause 6 is narrowed rather than closed | **Decided.** Nothing to build; [#288](https://github.com/eddiefiggie/srd-rules-engine/issues/288) carries the remaining half |

_Written 2026-08-29 against SRD v5.2.1._
