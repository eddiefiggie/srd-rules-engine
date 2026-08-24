# 0021 — A round is exactly six seconds, and the clock still does not advance itself

- **Status:** Accepted, 2026-08-23
- **Settles:** [#108](https://github.com/eddiefiggie/srd-rules-engine/issues/108)
- **Requirements:** R31 · touches R9, R13, R18, R20
- **Amends:** [0020 — two kinds of time](0020-two-kinds-of-time.md), clause 1 and one of its
  consequences. The rest of 0020 stands.
- **Related:** [0017 — verification is asserted, not read](0017-verification-is-asserted-not-read.md),
  which draws the line this record leans on between transcription and modelling

## Context

0020 settled what time is in this engine: ordinal `round_number` for encounter time, monotonic
elapsed minutes for campaign time. Its clause 1 said the two **do not convert**, and rested that
on p. 13:

> A round represents **about** 6 seconds in the game world.

0020 read *about* as the document declining to give an exact conversion, so deriving campaign
minutes from a round count would manufacture precision the SRD withholds — the inferred rule
value R31 forbids, in the one form that looks like arithmetic rather than a guess.

#18 then needed condition duration, and duration is where that reading had to be used rather
than merely stated. Checking it against the document turned up a sentence 0020 did not consider.

## The fact that decides it

**p. 98, the Oil entry, prints the conversion:**

> …the oil burns until the end of the turn **2 rounds** from when the oil was lit (**or 12
> seconds**) and deals 5 Fire damage to any creature that enters the area or ends its turn
> there.

Two rounds is twelve seconds. Not *about* twelve — the parenthesis exists to give the reader the
exact equivalent, and it is doing rules work: it defines when the fire stops. The same entry
measures the oil drying in minutes ("after 1 minute"), so one item uses both axes and the
document moves between them without remark.

Counted across the whole document: "6 seconds" appears once, hedged, on p. 13. "12 seconds"
appears once, exact, on p. 98. 0020 saw the first and not the second.

p. 106 puts the two units in one category rather than two:

> **Time Span.** A duration that provides a time span specifies how long the spell lasts in
> **rounds, minutes, hours, or the like**.

And rounds are a real spell duration unit, not a hypothetical: Tsunami (p. 171) is
"Concentration, up to 6 rounds".

## Options considered

**Keep clause 1 as written.** Defensible on p. 13 alone, and now known to be defensible only by
not having read p. 98. It would also make the engine refuse an arithmetic the document performs
in front of the reader, which is not caution — it is a different error in the same family, since
a declared gap that the source does not actually have is as misleading as a filled one it does.

**Overturn 0020 and let a turn advance the clock.** Rejected, and it is the tempting one because
it makes minute durations work in combat for free. It would have the engine invent elapsed time:
campaign time also passes outside encounters, so a three-hour march followed by a six-round fight
would either double-count or silently drop the march. 0020's real argument was never the *about*
— it was that the engine cannot know how much campaign time passed between two encounters. That
argument is untouched.

**Split conversion from propagation.** Chosen.

## Decision

**1. A round is exactly six seconds, cited to p. 98.** `core.clock` carries it as a named
constant with that citation. This is transcription of an equivalence the document performs, not a
modelling choice — the distinction 0017 drew, applied to a number instead of a stat block.

**2. `advanced_turn` still leaves `Clock` untouched, permanently.** 0020's test asserting it stays
exactly as it is. Advancing a turn is not the passage of campaign time, and the agent remains the
only source of elapsed minutes (0020 clause 3). **This clause is the one that must not be
relaxed**, and clause 1 above does not weaken it: knowing what a round is worth is a different
claim from knowing how much time has passed.

**3. Conversion is applied once, when a duration is applied — never on query.** A duration stated
in minutes becomes a round count at the moment the effect lands, and that count is stored. This is
0020 clause 4's reasoning, unchanged: a value re-derived on every query is a value a caller can
re-draw by choosing when to ask.

**4. The conversion is recorded where the duration is, so it is visible rather than implied.** A
duration that was converted says so, the same way a damage effect now carries `rolled` alongside
the amount taken (#105). An engine that quietly restates the caller's unit is an engine whose
arithmetic cannot be checked from the record.

**5. Nothing converts in the other direction.** Elapsed campaign minutes are never expressed as a
round count. The document converts rounds into seconds; it never takes a wall-clock span and asks
how many rounds it was, and outside an encounter the question has no meaning — there are no
rounds to count.

**6. Where a duration cannot be retired, it is reported, not dropped.** A held condition whose
duration this engine cannot yet resolve is named through the read surface rather than left to
look permanent, exactly as `unenforced_clauses` names the effects the engine holds but does not
apply.

## Why

### The gap this closes is much smaller than it looks

Counted from the document — 347 `Duration:` entries, cross-tabulated against Concentration:

| unit | Concentration | plain |
|---|---:|---:|
| rounds | 1 | 4 |
| minutes | **103** | **23** |
| hours | 27 | 55 |
| days | 2 | 8 |
| Instantaneous | 0 | 108 |
| until dispelled | 0 | 14 |

Two entries did not parse — "Special" and "Until the stone stops rolling" — and are excluded
rather than bucketed into a category they might not belong to.

**103 of the 126 minute-scale durations are Concentration**, which the engine already models: they
end when the caster's concentration ends, and no clock is consulted. So the population that
actually needed this decision is the **23 plain minute durations**, not the 126 it appears to be
at first count. Getting that number right changed how urgent this looked, which is why it is here
rather than in a commit message.

### Duration is not a property of a condition

All fifteen glossary entries state *effects*. Only two carry an ending rule of their own — Prone
(p. 186: spend half your Speed to right yourself) and Exhaustion (p. 181: a Long Rest removes a
level). Every other condition ends because whatever imposed it says when, which is why duration
belongs to the application and not to the `Condition`. A `duration` field on the condition itself
would model something the document does not have.

### *About* describes the fiction; the parenthesis does the arithmetic

The two sentences are not in tension once you notice they are doing different jobs. p. 13 is
telling a reader what a round *feels like* in the world, and hedges because combat rounds are an
abstraction over continuous action. p. 98 needs a number to say when a fire goes out, and gives
an exact one. The engine is in p. 98's position every time it retires a duration.

Taking the hedged sentence as the binding one, when an exact sentence exists and is the one doing
rules work, would be reading the document for the answer we already had rather than for the answer
it gives.

## Consequences

**Accepted costs.**

- **0020's consequence "a duration in rounds cannot be expressed in minutes, and vice versa" is
  now half wrong**, and the record says so rather than being quietly left to read as current. The
  vice-versa half stands, by clause 5.
- **A converted duration can disagree with the campaign clock.** If the agent advances the clock
  mid-encounter *and* rounds pass, the same span is counted on both axes. The engine cannot detect
  this, because clause 2 means it never learns that the rounds were also minutes. Reported through
  clause 4's visibility rather than solved.
- **One citation carries clause 1.** p. 98 is the only exact conversion in the document. A single
  sentence is a thin foundation, and it is the one a reviewer should attack first.
- **Six seconds per round is exact, but a round is not a fixed span of fiction.** The engine now
  states a precision the game's own text hedges at, in the one place the text stops hedging.

**Follow-on effects.**

- #18's remaining scope can proceed on the encounter axis without waiting for the clock question,
  and its minute-scale durations have a defined answer when they arrive.
- #19's plain-minute spell durations inherit clause 3 rather than needing their own decision.
- `scripts/verify_d20_rules.py` gains p. 98's sentence, so the constant cannot drift from the page
  it came from.

## Evidence

The p. 98 sentence was read from the official PDF at printed page 98 and is added to
`scripts/verify_d20_rules.py` as an asserted clause (0017), so it is re-checkable rather than
quoted once. The duration cross-tabulation was computed over all 347 `Duration:` occurrences in
the document rather than sampled, and its two unparsed entries are named above rather than
absorbed.

p. 13's *about* is already a verified clause from 0020 and is unchanged. Both sentences now sit in
the verifier, which is the form of this record that survives someone disagreeing with its
reasoning.
