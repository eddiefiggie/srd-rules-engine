# 0020 — Two kinds of time, minutes as the unit, and the round-to-clock bridge left unbuilt

- **Status:** Accepted, 2026-08-23. **Clause 1 amended by**
  [0021 — a round is six seconds](0021-a-round-is-six-seconds.md), 2026-08-23: the document does
  print an exact conversion (p. 98), which this record did not consider. Everything else stands,
  including the clause that matters most — a turn still never advances the clock.
- **Settles:** [#85](https://github.com/eddiefiggie/srd-rules-engine/issues/85)
- **Requirements:** R9, R13 · touches R4, R18, R20, R31
- **Related:** [0014 — positional state](0014-positional-state.md), the same question asked
  about space; [0006 — ledger format](0006-ledger-format.md), whose replay guarantee is why the
  recovery die is rolled where it is

## Context

`core.death` disclosed a rule it could not implement: *"A Stable creature that isn't healed
regains 1 Hit Point after 1d4 hours"* (p. 18). The rule is trivial. The thing it needed did not
exist — `EncounterState` advanced by turns and had no representation of elapsed time at all.

#85 observed that the same absence blocks more than one rule: Short and Long Rests, the
`resource-recharge` shape whose triggers include "dawn" and "finishing a Short or Long Rest",
and any duration measured in minutes or hours. So the question is not how a Stable creature
wakes up but **what time is in this engine at all**.

## The document decides the hardest part

The tempting design is one clock: rounds are six seconds, so a round counter and a campaign
clock are the same number in different units.

p. 13 forecloses it. *"A round represents **about** 6 seconds in the game world."*

**About** is the document declining to give an exact conversion. Deriving campaign minutes
from a round count would manufacture a precision the SRD withholds — the inferred rule value
R31 exists to prevent, in the one form that would look like arithmetic rather than a guess.

There is a second, independent reason: even given an exact round length, the engine cannot know
how much campaign time passed *between* encounters. A clock derived from rounds would be wrong
by everything that happened while nobody was rolling initiative.

## Decision

**1. Two kinds of time, and they do not convert.** *(Amended by [0021](0021-a-round-is-six-seconds.md):
they do convert, exactly, at six seconds to the round per p. 98. What survives is that nothing
converts them **automatically** — see clause 2 of that record.)*

| | What it is | Where it lives | What resolves against it |
|---|---|---|---|
| **Encounter time** | ordinal, per-encounter | `EncounterState.round_number` | "until the end of your next turn" |
| **Campaign time** | monotonic elapsed minutes | `EncounterState.clock` | "after 1d4 hours", rests, durations in minutes and hours |

No function converts one into the other, and `tests/test_clock.py` asserts that advancing a
turn leaves the clock untouched. A caller who wants an encounter's duration on the clock
advances the clock itself, having decided what it was.

**2. The unit is minutes**, because every campaign-scale duration in the document is a whole
number of them: Short Rest one hour (p. 187), Long Rest at least eight (p. 185), sixteen hours
before another may start (p. 185), 1d4 hours (p. 18). Seconds would be a unit nothing uses, and
picking it would invite exactly the bridge clause 1 refuses.

**3. The agent supplies elapsed time; the engine decides every consequence.** Elapsed time is a
narrative fact — only the agent knows the party walked for three hours — so it arrives as a
typed integer of minutes, which is R20's seam working as designed. What that time *does* is
never the agent's call. The invariant is unchanged: the agent decides *that* time passed and
*how much*, and can never decide how it turns out.

**4. A duration's die is rolled when the duration starts, not when it is queried.** The 1d4 is
drawn as the creature becomes Stable, from that adjudication's own seed, and the resulting
minute is stored. Asking whether recovery has happened is then a comparison.

**5. The clock is monotonic.** Time does not run backwards, and `Clock` refuses a negative
advance.

**6. The recovery deadline lives on `DeathSaves`**, not beside the clock, so that p. 18's
condition holds structurally.

**7. Rests are events with cited durations, and are not implemented here.** A rest advances the
clock by its duration and applies its benefits; the durations are verified (pp. 185, 187) and
the benefits are not modelled. That work is [#19](https://github.com/eddiefiggie/srd-rules-engine/issues/19)'s
and [#18](https://github.com/eddiefiggie/srd-rules-engine/issues/18)'s, not this record's.

## Why

### Rolling on demand would hand the caller a re-draw

This is the clause that would have been easy to get wrong, and wrong invisibly. If the 1d4 were
rolled when somebody asked "has it recovered yet", a caller could advance the clock an hour,
ask, advance another, ask — and stop when it liked the answer. Every test that advances the
clock once would still pass.

Rolling at stabilisation makes the outcome un-redrawable, which is the same property
`core.d20`'s banded seed space gives a reroll: a result the engine has produced cannot be
produced again differently. R4 says the engine rolls; this is what it takes for that to mean
anything once time is involved.

### Putting the deadline inside the death-save record makes a condition structural

p. 18 applies to a Stable creature *that isn't healed*. `with_healing` already resets
`DeathSaves` wholesale, so a deadline stored there is voided by healing because healing clears
the object it lives in — not because a later author remembered to check. The alternative, a
recovery table beside the clock, would need that check and would eventually not have it.

### Not converting is a disclosure, not a limitation we are hiding

An engine that reported campaign minutes derived from rounds would be more useful and would be
making them up. This is 0014's finding about distance measurement in a second domain: where the
document supplies no method, the honest engine declines rather than picks one that looks
plausible.

## Consequences

**Accepted costs.**

- **Campaign time rides on `EncounterState`**, which is not campaign-scoped. It is the only
  state carrier the engine has. A real campaign state would own the clock, and this clause is
  what should move when one exists.
- **Nothing advances the clock on its own.** A caller that never calls `with_time_passed` has a
  Stable creature that never recovers, and the engine cannot tell the difference between that
  and a game where no time has passed. Reported through the read surface
  (`minutes_until_recovery`) rather than left to be discovered.
- **A duration in rounds cannot be expressed in minutes, and vice versa.** That is clause 1
  working, and it will read as an omission to someone who expects one timeline. *(Half
  superseded by [0021](0021-a-round-is-six-seconds.md): the first direction is now supported and
  cited; the vice-versa still is not, by that record's clause 5.)*
- **`RECOVERY_OFFSET` extends a seed-band convention that is still unenforced**
  ([#82](https://github.com/eddiefiggie/srd-rules-engine/issues/82)). It sits far above every
  band in use, which is a mitigation rather than a guarantee.

**Follow-on effects.**

- `core.death`'s disclosed limit is removed rather than reworded, which was #85's third box.
- `core.spellcasting`'s Long Rest disclosure now points at #19: the clock it was waiting on
  exists, so what is missing is the rest.
- Condition duration (#18) and rest benefits (#19) have somewhere to resolve against when they
  are implemented.

## Evidence

Five clauses added to `scripts/verify_d20_rules.py` and matched against the official PDF,
bringing it to 92: p. 13's *about* 6 seconds, p. 18's 1d4 hours, p. 187's one-hour Short Rest,
p. 185's at-least-eight-hour Long Rest, and p. 185's sixteen-hour wait. The 1d4 clause was
proven red by changing the pattern to `1d6` — the script exits 1 and names the page.

p. 18 says the creature regains 1 Hit Point. It does not say the Unconscious condition ends;
the sentence that ends a condition on regaining hit points (p. 17) is about Knocking Out a
Creature, a different case. So recovery touches no condition, and a test holds that.

## Status of implementation

**Implemented with this record**: `core.clock`, `EncounterState.clock`,
`DeathSaves.recovers_at_minute`, `EncounterState.with_time_passed`, and the two read-surface
fields. Nineteen tests in `tests/test_clock.py`.
