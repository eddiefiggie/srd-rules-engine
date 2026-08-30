# 0057 — Prone crawls or stands, and both were built together

- **Status:** Accepted, 2026-08-30
- **Settles:** [#353](https://github.com/eddiefiggie/srd-rules-engine/issues/353)
- **Requirements:** R1, R14, R18, R31, R32
- **Related:** [0056 — a move is refused where it is made](0056-a-move-is-refused-where-it-is-made.md),
  which built the seam and deferred this;
  [0052 — the exit is built before the entrance](0052-the-exit-is-built-before-the-entrance.md),
  whose ordering rule decided the scope;
  [0055 — a creature moved by something other than itself](0055-a-creature-moved-by-something-other-than-itself.md),
  whose effect kind this one is the mirror of;
  [0027 — occasions and outcomes without a roll](0027-occasions-and-outcomes-without-a-roll.md),
  clause 6

## Context

> p. 186, *Prone*: **Restricted Movement.** Your only movement options are to crawl or to spend
> an amount of movement equal to half your Speed (round down) to right yourself and thereby end
> the condition. If your Speed is 0, you can't right yourself.

One sentence, two mechanics, and they are not the same kind of thing:

- **The crawl restriction is a refusal**, and 0056 settled where one lives —
  `EncounterState.with_movement`, beside the four already there.
- **Righting yourself is a capability.** It ends a condition, so R1 puts it behind the one
  adjudication entry point.

0056 built Frightened's clause on that seam and left these two alone, because building the
refusal without the exit would leave a creature able to crawl and unable to stand — 0052's
asymmetry, which this record is the other half of.

## The thing that had to exist first

The disclosure said these needed "a movement model that distinguishes standing from moving".
That was right, and the shape it turned out to be is two effect kinds that are mirrors:

| kind | ground covered | movement spent |
|---|---|---|
| `MOVED_BY_FORCE` (0055) | yes | none |
| `MOVEMENT_SPENT` (here) | none | yes |

`with_movement` couples the two, and p. 190's shove and p. 186's righting each need one half
without the other. Neither is a *movement*, and that is why.

## Decision

1. **A Prone creature's move is refused unless it is crawling**, in `with_movement`.
   `MovementMode.CRAWL` is already priced by p. 179 — an extra foot per foot — so the option
   p. 186 leaves costs something.

2. **Righting yourself is a testless proposal** (0027 clause 6). p. 186 states the cost and the
   effect and asks nothing of the dice. The charge and the ending are both in `outcome`, because
   they are one sentence: there is no branch in which a creature pays and stays down.

3. **The cost is half the *effective* walking Speed, rounded down.** p. 188 makes "your Speed"
   the walking one, and a creature slowed by p. 90's Slow pays half of what it has left rather
   than half of what its stat block says. The rounding is the document's, not a choice.

4. **"If your Speed is 0, you can't right yourself" is its own rule**, checked separately from
   the cost. Half of nothing is nothing, so a reading that derived the refusal from the cost
   would grant a *free stand* to exactly the creature p. 186 forbids it to.

5. **It costs movement and not an action**, so the offer is not gated on a spare Action and a
   creature that has already acted can still get up.

6. **A creature cannot spend movement it does not have**, refused both at the offer
   (`can_stand`) and at the charge (`with_movement_spent`). Two places because they answer
   different questions — one keeps the key off the menu, the other refuses a caller who reached
   past it.

## Why

### Clause 4 is the clause a careful reading gets wrong

p. 186 could be read as stating a cost and letting a Speed of 0 fall out of it: half of zero is
zero, so standing is free. That reading grants the ability to precisely the creature the next
sentence denies it to, and it is the reading an implementation arrives at by *simplifying*. The
document spends a sentence on it, so this spends a branch on it, and a corruption proof
confirms removing the branch goes red.

### Two refusals for one rule is not duplication

`can_stand` and `with_movement_spent` both refuse an unaffordable stand, and a corruption proof
showed why both are needed: removing the state-level refusal left every test green, because they
all stopped at the menu. The offer is a menu, not a promise, and a caller adjudicating directly
is the case AGENTS.md already discloses as getting outcome authority without the loop's
guarantees. The test for it was written after the proof failed.

## Consequences

- **Both of Prone's disclosures retire**, in the change that builds their rules and asserted
  together. Prone joins Frightened as a condition that discloses nothing.
- **Ten of the fifteen conditions now disclose nothing.** The five that remain are Charmed,
  Invisible, Petrified, Unconscious and Grappled.
- **No coverage figure moves — 116 of 210.** `prone` was already claimed, and correctly by
  R17's terms: the condition resolved while two of its clauses reached nothing. The third time
  this shape has been recorded (0054, 0056), which is worth noticing about the instrument.
- **Two clauses added to `scripts/verify_d20_rules.py`**, which reports 274 verified. The
  crawling one was written from memory, failed, and was corrected against the page — the second
  time the verifier has caught an author in four builds.

## Evidence

- p. 186 — the two movement options in one sentence, and the Speed-0 exception in its own.
- p. 179 — crawling priced at an extra foot per foot, which is what makes the first option cost
  something.

## Status of implementation

**Every clause is built** by [#353](https://github.com/eddiefiggie/srd-rules-engine/issues/353).

| Clause | State |
|---|---|
| 1 — crawl or nothing | **Built.** `with_movement`, asserted over three modes and against crawling |
| 2 — righting is a testless ruling | **Built.** `core.prone.stand_resolver` |
| 3 — half the effective Speed, rounded down | **Built.** `righting_cost`, asserted against a slowed creature and an odd Speed |
| 4 — Speed 0 is its own rule | **Built.** Asserted with the cost shown to permit it |
| 5 — movement, not an action | **Built.** Asserted with the Action already spent |
| 6 — refused at the offer and at the charge | **Built.** `can_stand` and `with_movement_spent`, asserted separately |
