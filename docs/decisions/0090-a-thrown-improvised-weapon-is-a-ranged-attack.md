# 0090 — A thrown improvised weapon is a ranged attack, and p. 15 decides the rest

- **Status:** Accepted, 2026-09-06
- **Settles:** [#390](https://github.com/eddiefiggie/srd-rules-engine/issues/390)
- **Requirements:** R12, R15, R17, R31, R32
- **Related:** [0076 — improvised is a use, not an object](0076-improvised-is-a-use-not-an-object.md),
  whose clause 8 this builds and whose other seven it leaves standing;
  [0058 — a field nothing reads is a rule not applied](0058-a-field-nothing-reads-is-a-rule-not-applied.md),
  which is the shape #390 named; [0086 — a range runs from the edge of a space](0086-a-range-runs-from-the-edge-of-a-space.md),
  whose measure the throw uses and whose missed offer site this repairs;
  [0041 — an item that leaves a creature](0041-an-item-that-leaves-a-creature-is-an-object-somewhere-unstated.md), whose
  clause 4 says where the object lands

## Context

p. 183's fourth rule:

> **Range.** If you throw the weapon, it has a normal range of 20 feet and a long range of
> 60 feet.

[0076](0076-improvised-is-a-use-not-an-object.md) built the swing and left the throw as
[#390](https://github.com/eddiefiggie/srd-rules-engine/issues/390): the numbers were read,
asserted in the verifier, and held in `core.read_surface` with no consumer — 0058's shape,
filed rather than half-built, because a throw offered without its range would be a rule
half-applied. #390 said the ability was the real question and should be settled from the
page rather than by analogy: p. 90's Thrown clause lets a Melee weapon keep its melee
modifier, and an improvised object has no melee-weapon rule to borrow from.

## Options considered

**Option 1 — Strength, by analogy with p. 90's Thrown weapon.** Rejected. p. 90's second
sentence is an exception for "a weapon [that] has the Thrown property", and p. 183 makes an
object an improvised weapon *because* it is thrown without that property. Borrowing the
exception would apply a rule the document reserves for weapons that have what this one lacks.

**Option 2 — Strength, by analogy with the swing.** Rejected. 0076 clause 5 made the swing
Strength because "this is a melee attack", which is p. 15's general rule for a melee attack;
the throw is a ranged attack, and the same rule's other half answers it.

**Option 3 — the wielder's choice, as for Finesse.** Rejected as a rule the document does not
state (R31): p. 15's choice is for "weapons that have the Finesse or Thrown property".

**Option 4 — Dexterity, by p. 15's general rule for a ranged attack.** Taken. The sentence
that decides the swing decides the throw, and the exception cannot reach either.

**Option 5 — reuse `attack-throw` with an improvised flag.** Rejected for the reason 0076
clause 2 gave the swing its own resolver: the throw contradicts the weapon path on the dice,
the Proficiency Bonus and the ability, and a flag would suppress more of that path than it
kept.

## Decision

**1. A thrown improvised weapon is a ranged attack, so its ability is Dexterity.** p. 15:
"The ability modifier used for a melee attack is Strength, and the ability modifier used for
a ranged attack is Dexterity. Weapons that have the Finesse or Thrown property break this
rule." Both sentences are asserted in the verifier by this change — 0076 rested the swing on
the first without asserting it — and the modifier reaches the attack roll and the damage
roll, as 0076 clause 5 keeps it on the swing.

**2. Its own key, `improvised-throw`, resolved by `improvised_attack_resolver`.** One
resolver for both of p. 183's uses, because they share three of four rules; two keys, because
the fourth rule and the ability differ. A Melee weapon that lacks Thrown — p. 183's own
example — is offered here and never as `attack-throw`, and `_weapon_and_target` refuses the
latter with a message that says where the throw lives.

**3. p. 183's 20/60 are read the way p. 90's Range is.** Refused beyond the long range,
Disadvantage beyond the normal one, both measured from each space's edge (0086 clause 4).
p. 183 states its two ranges in p. 90's terms, so p. 90's consequences follow.

**4. Held only.** p. 90's "you can draw that weapon as part of the attack" is the Thrown
property's, which an improvised weapon lacks by definition; a stowed rock is equipped first
(p. 177) and thrown after. The offer and the resolver both refuse a stowed object.

**5. The object leaves the hand whether the throw hits or misses**, in `always`, as p. 90's
Thrown weapon does, and it lands nowhere the document states (0041 clause 4). The ruling's
bounds forbid narrating where it fell.

**6. The swing is refused beyond p. 190's five feet at the resolver too.** The read surface
has always bounded it there (0076 clause 6); the resolver did not, and 0062 says the menu is
not a promise. Built beside the throw's bound because they are one function.

**7. `_within_weapon_range` measures from each space's edge.** The read surface's weapon
offer stayed point-to-point through 0086, whose test for "melee reach and weapon range"
exercised `_out_of_range` — the resolver's bound — and not the offer. A Medium fighter could
hit a Huge giant from ten feet and was never offered the swing, which is the direction the
menu must not be wrong in: an attack the rules permit and nothing downstream could catch.
The offer's `beyond_normal_range` detail reads the same measure.

**8. `improvised-weapons` is claimed**, against the resolver, now that all four of p. 183's
rules are built.

## Why

**The ability was settled by the sentence that already settled the swing.** 0076 clause 5
said "Strength, because this is a melee attack" and the reasoning was right; what was missing
was the page. p. 15 states the general rule in one sentence with two halves, and names the
exception in the next — and the exception is scoped to weapons *that have* Finesse or
Thrown. An improvised weapon is defined by lacking Thrown, so there is nothing to borrow and
nothing to choose: the general rule applies, and it says Dexterity for a ranged attack.
Asserting p. 15 is what turns 0076's correct reasoning into a checkable one.

**Clause 7 is the third site 0086 missed, and the second kind.** #460 found `_within`'s
three unarmed sites point-to-point; this is the weapon offer, and its miss is worse in one
way — it withholds an attack the resolver would resolve, so the menu and the ruling disagreed
about the same swing. It is here because the throw's offer needed a range measure and the
one beside it was wrong.

**Clause 6 is 0062 applied late.** The swing's five feet were the menu's alone. A declaration
is checkable input rather than a promise, and the throw's refusal beyond long range made the
swing's absence of one visible.

## Consequences

**Accepted costs.**

- **A second key on one resolver.** `improvised-attack` and `improvised-throw` resolve through
  the same function branching on which key arrived. The branch is three lines and the
  alternative is a second resolver sharing everything but them.
- **Two thrown-object menus.** A Dagger is offered under `attack-throw` and a club under
  `improvised-throw`, by whether the weapon has Thrown. That is p. 183's own line, and one
  menu would have to carry a flag the keys already carry.

**Follow-on effects.**

- Coverage moves to **146 of 210**: `improvised-weapons` is claimed. Equipment is 2 of 2.
- 0076's row 8 points here. Its Evidence table's sixth proof — the thrown normal range
  changed to 30, red on "has no consumer yet" — is superseded by this change's proofs, which
  go red on the consumer.
- **Filed, and not this record's:** the Advantage and Disadvantage that conditions, Dodging
  and p. 16's water put on every weapon attack reach neither improvised use
  ([#464](https://github.com/eddiefiggie/srd-rules-engine/issues/464)). It predates the
  throw and is the swing's gap as much as the throw's.

## Evidence

Read in the official SRD v5.2.1 PDF for this record, and asserted in
`scripts/verify_d20_rules.py`:

- **p. 183**, *Improvised Weapons*: "If you throw the weapon, it has a normal range of 20
  feet and a long range of 60 feet" — asserted by 0076.
- **p. 15**, *Attack Rolls — Ability Modifier*: "The ability modifier used for a melee attack
  is Strength, and the ability modifier used for a ranged attack is Dexterity" and "Weapons
  that have the Finesse or Thrown property break this rule" — **added by this change**. The
  patterns are taken from the sentence as recalled while holding no copy of the document;
  the verifier run by somebody who does is what confirms them, and the page number with them.
- **p. 90**, *Range* and *Thrown*: already asserted.

Engine side: corruption proofs through `scripts/prove_guard_red.sh`, each red on the test
written for it — the Dexterity modifier, the long-range refusal, the normal-range
Disadvantage, the space's-edge measure at the offer, the object leaving the hand, the swing's
reach, the held-only bound, the club's key, and the shape claim.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — Dexterity, by p. 15 | **Built**, and both p. 15 sentences asserted |
| 2 — `improvised-throw`, one resolver | **Built.** `improvised_throw_key`, `improvised_attack_resolver` |
| 3 — 20/60 read as p. 90's Range | **Built.** `_improvised_out_of_range` |
| 4 — held only | **Built**, at the offer and the resolver |
| 5 — leaves the hand, lands nowhere | **Built.** `object_detached` in `always` |
| 6 — the swing refused beyond five feet | **Built** |
| 7 — the weapon offer measured from the edge | **Built.** `_within_weapon_range`, and the offer's `beyond_normal_range` |
| 8 — the shape claimed | **Built.** `ENGINE_SHAPES`, `KINDS`, the data file |

_Written 2026-09-06 against SRD v5.2.1._
