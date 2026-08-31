# 0082 — A Short Rest is an offer repeated until the caller stops

- **Status:** Accepted, 2026-08-31
- **Settles:** [#406](https://github.com/eddiefiggie/srd-rules-engine/issues/406)
- **Requirements:** R1, R4, R17, R18, R29, R31, R32
- **Related:** [0081 — a campaign day's end is the fifth occasion](0081-a-campaign-days-end-is-the-fifth-occasion.md),
  which settled *where* a non-turn occasion lives and left *what shape it is* open;
  [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  whose clause 6 supplies the testless proposal this needs and had never been used in a loop
  that asks again;
  [0023 — the turn's end is a loop-owned phase](0023-the-turns-end-is-a-loop-owned-phase.md),
  whose sentence is the answer for the sixth time;
  [0072 — movement is a phase the loop drives](0072-movement-is-a-phase-the-loop-drives.md),
  whose `ReactionRequest` is the only other *offer* the loop makes

## Context

p. 187's Short Rest has exactly one mechanical benefit this engine can reach:

> **Spend Hit Point Dice.** You can spend one or more of your Hit Point Dice to regain Hit
> Points. For each Hit Point Die you spend in this way, roll the die and add your Constitution
> modifier to it. You regain Hit Points equal to the total (minimum of 1 Hit Point). **You can
> decide to spend an additional Hit Point Die after each roll.**

A die is thrown and hit points change, so each spend is an outcome (R1, R4). 0081 had already
settled where such an occasion lives — `_owed` is R29's narration debt and it is held per
loop, so anything producing rulings belongs to `TurnLoop`. What it did not settle is **what
shape this occasion is**, and every occasion the engine had was one of two:

- a **drain** — `end_day`, and the Concentration and Topple saves. The engine compels, nobody
  is choosing, and the loop empties a queue until it is empty.
- a **declaration slot** — the agent proposes, **once**, and the engine adjudicates.

p. 187 is neither. The last sentence puts the decision *after each roll*, so the number of
dice cannot be declared up front without contradicting it.

## Options considered

**Option 1 — take a count up front.** Rejected, and it is the implementation this rule
invites. `spend(n)` reads naturally, resolves in one ruling, and contradicts the only
sentence that matters: a creature deciding on three dice in advance is deciding without the
first roll, which p. 187 gives it. It also collapses three outcomes into one, so the ledger
records one roll where the document had three.

**Option 2 — drain the dice.** Rejected outright. A drain spends everything, and p. 187 says
"can spend **one or more**". Spending a creature's last die on its behalf is the engine
choosing, which is the capability this project removes.

**Option 3 — a `RestLoop`.** Rejected for 0081's reason, unchanged. `_owed` is per loop, so a
second driver lets a creature owe a narration to one object and act through another. The
tidier diagram is the same hole a `CampaignLoop` would have been.

**Option 4 — an offer, repeated.** Taken.

## Decision

**1. `TurnLoop.short_rest` is the sixth occasion, and the first of a third kind.** It offers,
adjudicates, and offers again, ending when the caller declines or the dice run out. The two
kinds that existed are unchanged; this is a third, and the record says so rather than
stretching either.

**2. The offer is `HitDieRequest` and the answers are `SpendHitDie` and `SpendDeclined`.**
Declining is a first-class answer rather than an absent one, for `ReactionDeclined`'s reason:
"I stop" and "I have nothing to declare" are different facts and the ledger should not have
to guess. `ReactionRequest` is the nearest existing shape and differs in the one way that
matters — a Reaction is offered once per move; this is offered again after every roll.

**3. `SpendHitDie` carries no count.** p. 187 offers one decision, and the *how much* is the
engine's (R4). A count would re-admit option 1 through the response type.

**4. Each spend is a testless `Proposal`** (0027 clause 6). Nothing is tested against a target
number, so `Proposal.test` is `None` and `Proposal.outcome` is the branch. Giving it a save
shape would invent a DC p. 187 never states. This is the first use of clause 6 inside a loop
that asks again, which the clause allowed and nothing had exercised.

**5. The healing is `HealingDice`, which the engine rolls.** A resolver returning
`Effect(kind=HEALING, amount=6)` would be a caller supplying a roll, which R4 exists to make
impossible. It is its own type rather than a `DamageDice` with a sign flipped: damage passes
through p. 17's Immunity, Resistance and Vulnerability inside `with_damage` and healing passes
through none of them, so sharing the type would put a `damage_type` on a Hit Point Die and
invite a defence being consulted on one.

**6. `minimum` is a rule, not a safety net.** p. 187 states "(minimum of 1 Hit Point)", and a
creature with a negative Constitution modifier can total less than one. It defaults to 0
because no other rule here states such a floor, and applying one to all healing would be
R31's inferred rule value.

**7. The spend and the healing are sibling effects.** `EffectKind.HIT_DIE_SPENT` is its own
kind, for #119's reason applied to a resource: a die decremented outside a Ruling is a
mechanical change with no roll, no seed, no citation and no ledger entry behind it. They are
also different facts — the die is gone whatever the roll came to.

**8. The loop ends on the dice, never on the hit points.** A creature at full hit points is
still offered a spend. p. 187 does not forbid one, and the minimum is 1 Hit Point regained, so
a die spent for nothing is a legal choice the document permits. Refusing to offer it would be
this engine inventing a rule in the direction R31 names.

**9. A creature at 0 hit points cannot start one.** p. 187: "To start a Short Rest, you must
have at least 1 Hit Point" — the same precondition p. 185 puts on a Long Rest, and the one an
implementation drops because every benefit below it reads as unconditional.

**10. `short-rest` is not claimed; `hit-point-dice` is.** p. 183's entry states its mechanic
as the spend, and the spend is now built end to end, so the resource shape is whole. p. 187's
entry states a second mechanic — "An interrupted Short Rest confers no benefits" — which is
**unbuilt**, and unlike a benefit with no antecedent its antecedents are observable: rolling
Initiative, taking damage, and casting a non-cantrip spell are all things this engine sees.
A shape claimed at half is the overstatement [#371](https://github.com/eddiefiggie/srd-rules-engine/issues/371)
and [#264](https://github.com/eddiefiggie/srd-rules-engine/issues/264) each found, and
`malnutrition` is sitting unclaimed two builds ago for the same reason.

## Why

**The gate's three sub-questions dissolved two-to-one, as #399's did.** Whether each die is a
separate Ruling was answered by 0027 clause 6, which had allowed exactly this and never been
used for it. Whether refusing a spend at full hit points invents a rule was answered by
reading p. 187 and finding no prohibition. What was left is the one the issue led with — what
shape the occasion is — and the answer is a third kind, arrived at by the document refusing
both existing ones in a single sentence.

**The sentence is the whole decision.** "You can decide to spend an additional Hit Point Die
after each roll" is eleven words that rule out a count, a drain, and a single ruling. Every
clause above follows from it.

## Consequences

- Six occasions produce rulings, in three kinds: four drains, one declaration slot, one
  repeated offer.
- `Declared` gains a third member, so a proposal branch may now hold healing the engine rolls.
  Nothing but `hit_die_resolver` declares one today.
- Coverage moves to **120 of 210**. `short-rest` and `long-rest` both stay unclaimed, and both
  are held by the same unbuilt clause ([#409](https://github.com/eddiefiggie/srd-rules-engine/issues/409)).
- A Short Rest is as long as the caller says it was. Neither p. 187's hour nor its three
  interruptions are modelled, which is disclosed on `TurnLoop.short_rest` and tracked.

## Status of implementation

**Decided and built, in the change that carries this record.**

| Clause | State |
|---|---|
| 1 — a sixth occasion, of a third kind | **Built.** `TurnLoop.short_rest` |
| 2 — `HitDieRequest`, `SpendHitDie`, `SpendDeclined` | **Built**, and both drivers answer it |
| 3 — the response carries no count | **Built.** `SpendHitDie` has no fields, which is what keeps option 1 out |
| 4 — a testless proposal | **Built.** `core.rests.hit_die_resolver`; the ruling carries no `result` |
| 5 — `HealingDice`, rolled by the engine | **Built** in `core.adjudicate`, and a third member of `Declared` |
| 6 — `minimum` is p. 187's floor | **Built**, defaulting to 0 so no other rule inherits it |
| 7 — the spend is its own effect kind | **Built.** `EffectKind.HIT_DIE_SPENT`, applied by `with_hit_dice_spent` |
| 8 — offered at full hit points | **Built**, and asserted against the opposite implementation |
| 9 — the 1 hit point precondition | **Built**, refusing before the first offer |
| 10 — `hit-point-dice` claimed, `short-rest` not | **Built.** 120 of 210; `short-rest` waits on [#409](https://github.com/eddiefiggie/srd-rules-engine/issues/409) |

### Evidence

Six corruption proofs, each red on the assertion written for it — and the sixth exists
because a proof **failed**. Removing p. 187's `minimum` left every test green: Wren's
Constitution modifier is +2, so the floor could never bind, and the rule was asserted by
nothing. `test_a_total_below_one_regains_one_hit_point` is the test that case needed, over a
creature with a -2 modifier rolling a 1 on a d4. Five clauses of p. 187 in
`scripts/verify_d20_rules.py`, including the interruption sentence clause 10 rests on —
asserted although unbuilt, so whoever takes #409 does not re-read it and cannot quietly
disagree with it.
