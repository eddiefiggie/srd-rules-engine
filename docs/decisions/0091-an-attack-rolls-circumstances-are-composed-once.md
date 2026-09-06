# 0091 — An attack roll's circumstances are composed once, for every resolver that makes one

- **Status:** Accepted, 2026-09-06
- **Settles:** [#464](https://github.com/eddiefiggie/srd-rules-engine/issues/464)
- **Requirements:** R12, R14, R31, R32
- **Related:** [0049 — Advantage that outlives its roll](0049-advantage-that-outlives-its-roll.md),
  whose tokens now reach three resolvers; [0076 — improvised is a use, not an object](0076-improvised-is-a-use-not-an-object.md)
  and [0090 — a thrown improvised weapon is a ranged attack](0090-a-thrown-improvised-weapon-is-a-ranged-attack.md),
  which built the two uses this completes and filed the gap; [0030 — the reading that cannot
  manufacture an outcome](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  whose defaults the composition carries unchanged

## Context

`attack_resolver` composed an attack roll's Advantage and Disadvantage from four sources —
the attacker's conditions (`own_attack_rolls`), the defender's (`attack_rolls_against`:
Prone's two halves, Paralyzed, Invisible's exception), p. 181's Dodge, and p. 90's Vex and
Sap tokens — and folded the weapon's own contributions in beside them: Heavy, a ranged
weapon's normal range, and p. 16's water. Two other resolvers make an attack roll, and
neither read any of the four. `unarmed_strike_resolver` (#267) and
`improvised_attack_resolver` (0076, 0090) built their `D20Test` with neither flag set, so:

- a Blinded, Poisoned, Frightened, Restrained or Prone attacker punched or swung a frying pan
  without Disadvantage;
- a Paralyzed, Stunned, Restrained or Prone defender was hit by either without the attacker's
  Advantage — while the automatic Critical Hit *beside* Paralyzed was read by both;
- a Dodging defender imposed nothing on either;
- a Vex token sat unspent through a punch, and a Sap penalty through a thrown chair.

[#464](https://github.com/eddiefiggie/srd-rules-engine/issues/464) named it while 0090 was
being built, and declined to fold it in because it was the swing's gap as much as the throw's
and predated both. Each item is a rule the document states for **attack rolls** — p. 179's
Blinded says "your attack rolls have Disadvantage", p. 90's Vex "your next attack roll",
p. 181's Dodge "any attack roll made against you" — and every one of these three resolvers
makes one. It is the plainest kind of gap: a built mechanic with a built antecedent that one
resolver did not consult.

The same reading found a second thing. `_impeded_underwater` has quoted p. 16's melee
sentence in its docstring since #446, word for word, and the verifier asserted only the
ranged one. The improvised swing rests on the melee sentence, so the quotation was not
enough (#371's shape).

## Options considered

**Option 1 — copy the block into each resolver.** Rejected. Three copies of a composition
that has already changed four times (#192, #193, 0049, 0086) is three places for the next
change to miss one, which is exactly how this gap was made.

**Option 2 — fold the Unarmed Strike and the improvised uses into `attack_resolver` as
flags.** Rejected for the reason each has its own resolver: the Unarmed Strike's bonus is a
second rule beside the weapon's, and p. 183's two uses contradict the weapon path on the
dice and the Proficiency Bonus. A flag would suppress more of that path than it kept
(0076 clause 2).

**Option 3 — one helper composing the creatures' half, and each resolver ORs its own half
in.** Taken. What the two creatures and the tokens between them put on the roll does not
depend on what is in the attacker's hand; what the hand contributes — Heavy, a range, the
water — does, and stays with the resolver that knows the hand.

**On p. 16 and the improvised weapon, two readings.** 0076 clause 1 says no object *is* an
improvised weapon, which invites reading p. 16's "a weapon" as excluding a frying pan. Rejected:
p. 183 defines the thing as "an object **wielded as a makeshift weapon**" and speaks of
"attack rolls with an improvised weapon" in its own third sentence, so an attack made with
one is an attack with a weapon in the document's words. 0076's point is that the property
belongs to the *use*, and the use is exactly what p. 16 is asked about. Taken: the water
reaches both uses.

**On p. 16 and the Unarmed Strike, two readings.** Extend the melee clause to a punch by
analogy — a fist swung underwater is as impeded as a club. Rejected as a rule the document
does not state (R31): p. 16 impedes "a melee attack roll **with a weapon**", and p. 177
counts "a weapon or an Unarmed Strike" as two things in one sentence. Taken: the clause does
not reach a punch, and this record is where that is written down.

## Decision

**1. `_Circumstances`, composed by `_circumstances(state, actor, target)`.** The attacker's
conditions with p. 182's fear qualifier and p. 184's Invisible exception, the defender's
conditions with Prone's positions and p. 184's other half, p. 181's Dodge, and the p. 90
tokens in scope — into `advantage`, `disadvantage`, and the tokens themselves. Every default
0030 settled is carried unchanged, because the code moved and was not rewritten.

**2. Read by all three resolvers.** `attack_resolver` reads it where its inline block was and
ORs Heavy, the range and the water in beside it, as before; its behaviour is unchanged and
its existing tests say so. `unarmed_strike_resolver` and `improvised_attack_resolver` read it
for the first time. Every source lands on the same pair of flags, so p. 8's cancellation is
the d20's to apply: a Blinded creature punching a Paralyzed one sets both and rolls straight.

**3. A token is spent by whichever attack roll it reaches.** p. 90 says "your **next** attack
roll", so a punch or a thrown chair spends a Vex or Sap token exactly as a Rapier does, in
`always`, hit or miss (0049 clause 2). This is a behaviour change for the Unarmed Strike: a
token that would have survived a punch is consumed by it.

**4. p. 16's water reaches the improvised weapon.** The melee clause reads the type the
ruleset stated for this use and the wielder's Swim Speed, as it reads a weapon's type and
the same speed; the ranged clause misses the throw outright beyond p. 183's twenty feet and
puts Disadvantage on it within, as it does a Thrown weapon at p. 90's. The automatic miss is
`_missed_by_the_water`, shared with `attack_resolver`, and it keeps `always` — so the object
still leaves the hand, because the throw was made.

**5. p. 16's water does not reach the Unarmed Strike**, by p. 177's two-term sentence. This
is not an `unenforced_clauses` disclosure, because it is not a mechanic the engine holds and
declines to enforce; it is a clause that does not apply, and the test that pins it is the
discriminating one for the whole change — a composition that read `state.underwater` for
every attack would pass everything else here.

**6. The melee sentence is asserted.** Added to `scripts/verify_d20_rules.py` beside the
ranged one, with the pattern taken from the sentence as recalled; a run by somebody holding
the document is what confirms the wording.

**Not touched, and why.** p. 89's Heavy is a property of a weapon, and 0076 clause 1 makes
the improvised use a use of the object: the offer carries none of the weapon's properties
and none is applied here. Dodge's "if you can see the attacker" qualifier is read by none of
the three resolvers, was not before, and is already disclosed by `ActionBudget` as
`dodge-requires-seeing-the-attacker`.

## Why

**The composition is one rule's worth of reading, and it was three resolvers' worth of
forgetting.** Nothing in the document distinguishes a punch's attack roll from a sword's for
any of these four sources; the distinction existed only in which function happened to be
written first. A block three resolvers must agree on is a block that lives in one place, and
the proof that it now does is that the corruption proofs for the Unarmed Strike and the
improvised uses go red by corrupting `_circumstances` — the same lines `attack_resolver`
reads.

**Clause 5 is the one worth the record.** The other clauses are the engine catching up with
itself. Clause 5 is a reading, and the tempting one is wrong in the permissive direction for
the attacker: extending p. 16 to a fist would put a Disadvantage the document does not state
on every underwater brawl. R31 excludes it, and the test asserts the exclusion so that a
future "fix" has to argue with the page.

## Consequences

**Accepted costs.**

- **A dataclass for three fields.** `_Circumstances` could be a tuple; it is a class so that
  `spent()` lives beside the tokens it spends and no resolver rebuilds the description.
- **The Unarmed Strike now spends tokens** (clause 3). A creature holding Vex against a target
  and punching it uses the token on the punch. That is what "your next attack roll" says.

**Follow-on effects.**

- Coverage does not move: **146 of 210**. No shape is claimed or released; `unarmed-strike`
  and `improvised-weapons` were claimed on their own rules, and this reaches rules other
  shapes hold.
- **384** clauses in the verifier, from 383.
- 0090's Consequences bullet that filed #464 gains a dated note pointing here; 0049's Status
  gains one for clause 3.

## Evidence

Read in the official SRD v5.2.1 PDF for the records that built each source, and asserted in
`scripts/verify_d20_rules.py`:

- **pp. 179–186**, the conditions' attack-roll clauses — asserted by #18 and since.
- **p. 181**, *Dodge*: "any attack roll made against you has Disadvantage" — asserted.
- **p. 90**, *Vex* and *Sap*: "your next attack roll" and "its next attack roll" — asserted
  by 0049.
- **p. 16**, *Impeded Weapons*, the ranged sentence — asserted by #446. The melee sentence —
  "a creature that lacks a Swim Speed has Disadvantage on the attack roll unless the weapon
  deals Piercing damage" — **added by this change**, patterned from recall; the verifier run
  by a holder of the document confirms it.
- **p. 177**: "one attack roll with a weapon or an Unarmed Strike" — asserted by #267; the
  sentence clause 5 rests on.
- **p. 183**: "Don't add your Proficiency Bonus to attack rolls with an improvised weapon" —
  asserted by 0076; the phrase clause 4 rests on.

Engine side: eighteen corruption proofs through `scripts/prove_guard_red.sh`, each red on
the test written for it — the two flags on each of the two new resolvers, Dodge, the two
token kinds held and the two spent, Prone's positions, the water on the swing, the Piercing
and Swim exemptions each alone, the automatic miss and the detachment it keeps, the punch
the water does not reach, and the verifier's clause. Against the base tree, eleven of the
module's fourteen tests go red on their own; three stay green there and are proved by
corruption alone, and each is a "nothing is read" case by design: nothing spent without a
token, a punch not impeded, and the two p. 16 exemptions — which the base tree satisfied by
reading nothing at all, and which the two exemption proofs show the new code satisfies by
reading the right thing.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — `_Circumstances`, composed once | **Built.** `core.combat._circumstances` |
| 2 — read by all three resolvers | **Built**, with `attack_resolver`'s behaviour unchanged |
| 3 — a token is spent by whichever roll it reaches | **Built.** `_Circumstances.spent` in each `always` |
| 4 — p. 16 reaches the improvised weapon | **Built.** `_impeded_underwater` on the use's two facts; `_missed_by_the_water` shared |
| 5 — p. 16 does not reach the Unarmed Strike | **Built** by exclusion, and asserted |
| 6 — the melee sentence asserted | **Built**, pending the verifier run that confirms the pattern |

_Written 2026-09-06 against SRD v5.2.1._
