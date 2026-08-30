# 0065 — A long cast spends its slot on completion

- **Status:** Accepted, 2026-08-30
- **Settles:** [#250](https://github.com/eddiefiggie/srd-rules-engine/issues/250)
- **Requirements:** R1, R4, R15, R18, R19, R31, R32
- **Related:** [0038 — a spell is data the caster carries](0038-a-spell-is-data-the-caster-carries.md),
  clause 6, which put the slot in `Proposal.always` and is the ordering this record inverts;
  [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md) clause 6,
  for why the beginning of a casting states its effects in `outcome`;
  [0021 — a round is six seconds](0021-a-round-is-six-seconds.md), which is where ten turns
  to the minute comes from

## Context

p. 105, *Longer Casting Times*:

> Certain spells—including a spell cast as a Ritual—require more time to cast: minutes or
> even hours. While you cast a spell with a casting time of 1 minute or more, you must take
> the Magic action on each of your turns, and you must maintain Concentration while you do
> so. **If your Concentration is broken, the spell fails, but you don't expend a spell slot.**
> To cast the spell again, you must start over.

Everything the engine had built for casting assumed the act was instantaneous. `CastingTime`
held three values, all of them slices of one turn; `spell_resolver` charged the action,
expended the slot and asked the ruleset what happened, in that order, inside a single
adjudication. p. 105 describes an act that spans ten turns and can fail in the middle.

The bolded sentence is the whole difficulty. Every other cost in this engine is paid when the
act happens; this one is described by its *absence* — the document tells you what is **not**
expended, and only in the failure case.

## Options considered

**Option 1 — expend the slot when the casting begins, and refund it if Concentration
breaks.** Rejected, and it is the option that arrives looking correct because it preserves
0038 clause 6's ordering. It fails for a reason that is about the document rather than about
the code: **there is no refund in the SRD.** p. 105 does not say the slot comes back; it says
it is never expended. An engine that expends and refunds has invented a transaction, and the
invention is observable — the ledger records a `SPELL_SLOT_EXPENDED` that the document says
did not happen, and any read of the caster's slots during those ten turns is wrong. R31
forbids inferring a rule value, and "expended then returned" is a rule value inferred from a
sentence that states the opposite.

**Option 2 — expend nothing and let the ruleset decide.** Rejected outright. A slot is a cost
and 0038 clause 3 is why the engine owns costs: a ruleset that forgot would fail invisibly.

**Option 3 — expend the slot when the casting completes.** Chosen. It is what the sentence
describes read forwards rather than backwards: nothing is spent until the spell is cast, so a
casting that never finishes spent nothing, so there is nothing to refund. The refund clause
stops being a mechanic and becomes a consequence.

**Option 4 — model the casting as a `Duration` or a `TurnBounded` span.** Rejected. Both
existing vocabularies are about something *expiring*, and a casting does not expire — it
completes, and the completion is the event. A span that dies at a boundary would need a
separate signal for "and now the spell happens", which is the whole of what this is.

## Decision

**1. A casting time of a minute or more is a fourth `CastingTime`, and the spell states its
own count.** `CastingTime.MINUTES` with `Spell.casting_minutes`. p. 105 says "1 minute or
more" and leaves each spell to say how many, so one number held for all of them would be a
duration the document does not give. Both directions are refused at construction: `MINUTES`
without a count, and a count on a casting that has none.

**2. The slot is expended when the casting completes.** Not when it begins, and not refunded.
This is the clause the record exists for, and it inverts 0038 clause 6 for exactly one
casting time.

**3. A casting in progress is state the creature carries.** `Combatant.long_cast`, holding the
spell, the slot level fixed when it began, and the Magic actions still owed. Not a computed
value, because it has to survive between turns and be visible to the read surface.

**4. Ten turns to the minute, derived rather than chosen.** `TURNS_PER_MINUTE = 10` follows
from [0021](0021-a-round-is-six-seconds.md)'s six-second round and one turn per creature per
round. It is stated here rather than in the spell data so that a ruleset cannot disagree
with the document about how long a minute is.

**5. The slot level is fixed when the casting begins and is not re-read.** A continuation
names no level: the key is `continue-cast:<spell>` and the level rides on `long_cast`.
Re-reading it off a key would let ten turns of casting be redirected to a different slot on
the last one, which is upcasting for the price of a first-level commitment.

**6. Payability is checked at the start even though nothing is spent there.** A caster who
could never pay has nothing to spend ten turns on, and finding out on turn ten is a worse
answer than finding out on turn one. This is the one place the record charges a check to a
moment the document does not name, and it refuses rather than expends, so it invents no
outcome.

**7. While a casting is in progress it is the only casting the menu offers.** p. 105: "To
cast the spell again, you must start over" — so beginning a second would abandon the first,
and R18 puts that in `legal_actions` rather than in a refusal afterwards. A caster with no
Action left is offered nothing, because the continuation costs the Action like any other
Magic action.

**8. Concentration begins with the casting and is not re-begun each turn.** p. 179's
replacement rule would otherwise end and restart it every turn — a mechanic the document
does not describe, and one that would make the casting immune to the very failure p. 105
is about.

**9. The continuation is answered in the resolver, not only in the menu.** R1: a consumer
reaching adjudication directly gets the same three refusals the read surface expresses by
not offering the key — no casting in progress, a different spell, and lapsed Concentration.

**10. What this still does not model, disclosed rather than implied (R32).** Hours are
expressed in minutes, so a two-hour casting is `casting_minutes=120` — exact arithmetic and
a missing vocabulary. And a Ritual, which p. 105's sentence names explicitly, does not run
through any of this: `ritual_cast` computes p. 187's extra ten minutes and nothing charges
them ([#371](https://github.com/eddiefiggie/srd-rules-engine/issues/371)).

## Why

**Clause 2 is the record.** Everything else is structure around it. The reason to write it
down is that Option 1 is what an implementer reaches for — it preserves the existing order,
it looks like every other cost in the engine, and it passes a test suite that only ever
checks the *end* state of a successful casting. The two orders differ only while the casting
is in flight, which is a window no test written for instantaneous spells would ever look at.

**The document's own phrasing is the evidence.** "The spell fails, but you don't expend a
spell slot" is a sentence about what never happened. Reading it as a refund requires adding
an event the SRD does not mention, in the one direction R31 exists to refuse.

**Clause 5 is a defect this record avoided rather than found.** The first shape of the
resolver read the slot level off the action key, because that is what ordinary casting does —
and the continuation branch sat after that read. It went red for a reason unrelated to slot
levels (a continuation key names no cast, so the read raised), and moving the branch above it
was the fix. Had the continuation key carried a level, it would have worked, and nothing would
have shown that ten turns of commitment could be redirected on the last one.

**Clause 6 is the compromise, and it is named as one.** p. 105 says nothing about checking
payability at the start. The alternative is a casting that runs its full length and then
raises, which is a worse experience and no more faithful — the document does not describe
that either. It refuses rather than resolving, so no outcome is invented, which is the test
this repository applies to a genuinely ambiguous call.

## Consequences

**Accepted costs.**

- **0038 clause 6 is no longer universal**, and a reader who learns the rule from that record
  will be wrong about one casting time. Named here, and in `core.casting`'s docstring.
- **`Combatant` grows again** — a fourth field about spells. 0039's consequences already
  flagged this accumulation as worth watching, and this is another turn of it.
- **The begin branch states its effects in `outcome` rather than `always`**, which reads as
  inconsistent beside the ordinary path until you notice it has no test and therefore no
  branch to be conditional on (0027 clause 6).
- **Hours are a vocabulary this does not have.** Disclosed, not approximated.

**Follow-on effects.**

- **#19's spellcasting umbrella loses its last large well-specified slice.** What remains
  under it is components (#245), Verbal (#246) and preparation refinements.
- **[#371](https://github.com/eddiefiggie/srd-rules-engine/issues/371) is new**, and it exists
  because this record read p. 105's first sentence rather than only its third.
- **[#365](https://github.com/eddiefiggie/srd-rules-engine/issues/365) gains a fifth
  instance** in the other direction: the continuation is the first rule in a while whose
  refusals were built at the resolver *and* at the menu deliberately, and clause 9 says so.

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 105** (*Casting Time*, *One Spell
with a Spell Slot per Turn*, *Reaction and Bonus Action Triggers*, and *Longer Casting Times*
in full), **p. 104** (*Casting without Slots*, for what a slot expenditure is separable from),
**p. 179** (*Concentration*, for the replacement rule clause 8 avoids), **p. 185** (*Magic*,
for the action each turn costs), and **p. 187** (*Ritual*, for clause 10's gap).

Three clauses were added to `scripts/verify_d20_rules.py`, taking it to 281: the four casting
times, the each-turn Magic action with Concentration, and the sentence clause 2 turns on.

## Status of implementation

**All ten clauses are built**, by [#250](https://github.com/eddiefiggie/srd-rules-engine/issues/250), except clause 10 which is a disclosure and
whose second half is tracked by [#371](https://github.com/eddiefiggie/srd-rules-engine/issues/371).

| Clause | State |
|---|---|
| 1 — `CastingTime.MINUTES`, and the spell states its own count | **Built.** `Spell.casting_minutes`, refused in both directions at construction |
| 2 — the slot is expended on completion | **Built.** `_continued`'s final branch is the only place `spell_slot_expended` reaches a long casting |
| 3 — a casting in progress is state | **Built.** `Combatant.long_cast`, with `with_long_cast_begun`, `_continued` and `_abandoned` |
| 4 — ten turns to the minute | **Built.** `TURNS_PER_MINUTE`, derived from 0021 and pinned by `test_spellcasting.py`'s constant guard |
| 5 — the slot level is fixed at the start | **Built.** The continuation branch is answered before the action key is read for a level |
| 6 — payability is checked at the start | **Built**, and it refuses rather than expending |
| 7 — one casting on the menu at a time | **Built.** `_castable` returns the continuation and nothing else while `long_cast` is set |
| 8 — Concentration is not re-begun | **Built**, and asserted by a test that fails when a `concentration_begun` is added to the continuation |
| 9 — the resolver refuses what the menu declines to offer | **Built.** Three refusals, each with its own test |
| 10 — hours and rituals, disclosed | **Built as a disclosure** in `core.casting`'s docstring. The Ritual half is [#371](https://github.com/eddiefiggie/srd-rules-engine/issues/371) |

_Written 2026-08-30 against SRD v5.2.1._
