# 0031 — Two printed rules that disagree state no rule, and 0030's tiebreak must not be reached for them

- **Status:** Accepted, 2026-08-25
- **Settles:** [#182](https://github.com/eddiefiggie/srd-rules-engine/issues/182),
  [#205](https://github.com/eddiefiggie/srd-rules-engine/issues/205)
- **Requirements:** R31, R32 · touches R1, R7
- **Related:** [0030 — an unanswerable qualifier resolves away from invention](0030-an-unanswerable-qualifier-resolves-away-from-invention.md),
  whose clause 1 this record draws a boundary around;
  [0028 — a level carries the rule that caused it](0028-a-level-carries-the-rule-that-caused-it.md),
  during which the first instance was found;
  [0017 — verification is asserted, not read](0017-verification-is-asserted-not-read.md)

## Context

Every standing rule in `AGENTS.md` about rules fidelity assumes the document is **silent or
clear**. "Never infer a rule value. Every mechanic traces to the official SRD v5.2.1 document. If
the SRD does not state it outright, it is excluded and the exclusion disclosed rather than
guessed (R31, R32)."

The SRD v5.2.1 has now been found to do a third thing: **state a value twice, differently.** Two
instances, and neither is a misreading — both pairs were re-read in the PDF for this record.

**#182 — a Potion of Vitality against locked Exhaustion.**

- p. 236: "When you drink this potion, it removes **any** Exhaustion levels you have and ends the
  Poisoned condition on you."
- p. 181: "Exhaustion caused by dehydration **can't be removed** until the creature drinks the full
  amount of water required for a day." p. 185 says the same for food.

A creature holding dehydration levels drinks the potion. "Any" and "can't be removed" cannot both
hold.

**#205 — a proportional change reaching a special speed.** Both sentences are in the *same
paragraph* of p. 188, *Changes to Your Speeds*:

- "If an effect increases or decreases your Speed for a time, any special speed you have increases
  or decreases by **an equal amount** for the same duration."
- "Similarly, if your Speed is **halved** and you have a Fly Speed, your Fly Speed is **also
  halved**."

They agree only when the two speeds are equal. A Speed of 30 halved is a reduction of 15 feet; a
Fly Speed of 40 loses 15 by the first sentence and 20 by the second.

**The reason this needs a record rather than two judgement calls** is that
[0030](0030-an-unanswerable-qualifier-resolves-away-from-invention.md) clause 1 appears to decide
both, and confidently. Resolve away from invention: a smaller remaining Fly Speed cannot
manufacture movement, so take 20; leaving the Exhaustion levels in place cannot manufacture a
recovery, so the locks win. Two plausible answers, arrived at in one step, from the project's
most-reached-for tiebreak.

Both would be inferred rule values, and the failure would be silent — which is precisely the
shape R31 exists to prevent.

## Options considered

**Lex specialis — the more specific rule wins.** Rejected. It is how most systems resolve this,
and it does not decide #205 at all: the two sentences sit in one paragraph, one stating the rule
and one working an example of it, and neither is more specific than the other. A tiebreak that
covers one of the project's two instances is not a rule, it is a coin already flipped.

**The worked example wins over the general statement** (or the reverse). Rejected for the mirror
reason: it decides #205 and says nothing about #182, where the two sentences are on different
pages, in different chapters, about different subsystems.

**Apply [0030](0030-an-unanswerable-qualifier-resolves-away-from-invention.md) clause 1.**
Rejected, and this is the option the record exists to close off. Clause 1 governs a gap in **this
engine's knowledge** — the document is clear and the state cannot answer it. A contradiction is a
gap in **the document**. In 0030's situation exactly one reading is factually right and the engine
does not know which; here neither reading is more right, because the SRD asserts both. Using a
tiebreak built for the first case on the second converts "the document says two things" into "the
engine knows the answer", and the resulting number is indistinguishable from a correct one once it
is inside a finished ruling.

**Pick one and disclose the pick.** Rejected. Disclosure is what R32 asks for an *exclusion*, not
a licence to guess with a footnote. A ruling that resolved a contradiction and mentioned it in
prose would still hand the caller a number no rule produced, and R7 leaves the narrator free to
assert what it finds.

**Ask the errata.** Rejected under [0017](0017-verification-is-asserted-not-read.md). This project
verifies against one document at one version; a correction published elsewhere is not the SRD
v5.2.1, and admitting a second source would make "which document" a per-clause question.

## Decision

**1. Two printed rules that disagree state no rule.** The document has not said what happens, in
the sense R31 means. The remedy is R31's existing remedy and not a new one: the mechanic is
**excluded and the exclusion disclosed**, exactly as for a rule the SRD never states.

**2. [0030](0030-an-unanswerable-qualifier-resolves-away-from-invention.md) clause 1 is not
reached for a contradiction, and this is the operative clause.** The two look alike and are not:

| | 0030 | 0031 |
|---|---|---|
| What is missing | a fact about the world the engine cannot observe | a rule the document declines to settle |
| Is one reading correct? | yes — the engine does not know which | no — both are printed |
| What the engine does | applies or withholds, away from invention | does not model the combination |

Whichever direction clause 1 would point is not evidence about the rule. It is evidence about the
consequences of a guess, and there is no guess to grade.

**3. Prefer non-implementation to refusal, where the choice exists.** A contradiction reached only
by a mechanic nobody has built yet is closed by **not building it** and saying so where the
neighbouring code lives. This is cheaper and more honest than a runtime refusal: nothing is
offered, so nothing has to be declined. Both current instances are here — the Potion of Vitality
and Dehydration are unimplemented, and this engine implements no proportional speed effect.

**4. Where the engine must answer, it refuses the combination and quotes both sentences.** A
contradiction reachable from already-built mechanics cannot be handled by clause 3. The engine
then declines *that combination* — not the whole mechanic — and the refusal names the two pages so
the caller can see it is the document that disagrees rather than the engine that is incomplete.

**5. A refusal under clause 4 is a read-surface refusal, never an adjudication that shrugs.** 0030
rejected refusal for `UNSTATED` because it "does not avoid the choice; it relocates it to the party
who must not have it" (R1). That objection is real and it binds here too. So a clause-4 refusal
must be reachable *before* a ruling is proposed — the caller learns the combination is unmodelled
instead of being handed a half-ruling to finish. If a contradiction is ever found that can only be
discovered mid-adjudication, that is a new question and it gets its own record.

**6. Each instance is named in the tree next to the code that would reach it.** Not only in this
record. A reader arriving at `Conditions.speeds_after` must learn there that p. 188 disagrees with
itself, because that is where someone will otherwise implement the proportional case in an
afternoon and be plausibly wrong.

## Why

**R31 already contained the answer; what was missing was that a contradiction counts as
silence.** "If the SRD does not state it outright" reads, on first pass, as being about absence.
Two printed sentences feel like the opposite of absence — there is *more* text, not less. But the
thing R31 protects is the traceability of a value to the document, and a value traceable to two
mutually exclusive sentences is not traced at all.

**Clause 2 is the part that would have gone wrong, and it would have gone wrong quickly.** 0030 is
the newest record, its clause 1 is stated as a general tiebreak, and its own **Status of
implementation** notes with some satisfaction that it decided a question outside the area it was
written for. That is a record inviting reuse. The next author meeting #205 would have reached for
it, got an answer in one step, and shipped a Fly Speed nobody had verified — and the tell that
something was wrong is subtle: clause 1 grades *consequences*, and grading consequences is only
legitimate when one of the readings is actually true.

**Clause 3 is what keeps this from becoming machinery.** The cheapest correct response to "the
document contradicts itself here" is to not have code there. Both instances are already in that
state, and this record's practical effect today is to say that they should stay there rather than
be resolved by whoever needs the mechanic next.

**Clause 5 is 0030's objection, kept rather than overridden.** It is the one thing this record must
not quietly discard: a refusal that arrives mid-adjudication is the agent deciding how it turns
out, which the Product Contract forbids however good the reason for refusing.

## Consequences

**Accepted costs.**

- **Two mechanics stay unbuilt for a reason that will not go away by itself.** Neither the Potion
  of Vitality nor any proportional speed effect can be implemented under this record without a
  superseding one. That is the intended cost: the alternative is a number nobody can check.
- **A consumer wanting D&D-as-played will find these gaps.** Widely-known 5e handling of the
  Potion of Vitality is not in the SRD's power to settle here, and `AGENTS.md` already excludes
  widely-known behaviour as a source.
- **The count of contradictions is unknown and probably above two.** Nothing sweeps the document
  for them, and nothing can — a contradiction is a semantic relation between two pages, not a
  pattern. New instances arrive by being tripped over, the way both of these did.

**Follow-on effects.**

- Clause 6 needs `Conditions.speeds_after`'s existing disclosure to cite this record rather than
  only the issue. Done in this change.
- Clause 4 has **no instance and therefore no implementation**. Filed as
  [#209](https://github.com/eddiefiggie/srd-rules-engine/issues/209) against the first contradiction
  that a built mechanic can reach.
- Coverage is unchanged at **89 of 211**. A record resolves no shape, and clause 3 is a decision to
  leave two of them unresolved.

## Evidence

Both pairs were read in the official SRD v5.2.1 PDF for this record rather than taken from the
issues that reported them. The pages were extracted and quoted directly:

- p. 236, *Potion of Vitality*: "When you drink this potion, it removes any Exhaustion levels you
  have and ends the Poisoned condition on you."
- p. 181, *Dehydration [Hazard]*: "Exhaustion caused by dehydration can't be removed until the
  creature drinks the full amount of water required for a day."
- p. 185, *Malnutrition [Hazard]*: the same lock, for food.
- p. 188, *Changes to Your Speeds*: both sentences, in one paragraph — "increases or decreases by
  an equal amount", and "if your Speed is halved and you have a Fly Speed, your Fly Speed is also
  halved".

All four are asserted in `scripts/verify_d20_rules.py`, so the pairs go red together if a future
revision reworded either half — which is the only way this record can learn that a contradiction
was resolved by the publisher rather than by us.

In the tree: `Conditions.speeds_after` implements only the feet-denominated effects and says why;
`core.hazards` does not implement Dehydration or Malnutrition, for the separate reason recorded in
[0028](0028-a-level-carries-the-rule-that-caused-it.md).

## Status of implementation

**Decided, and clause 3 means most of it is a decision not to build.**

| Clause | State |
|---|---|
| 1 — a contradiction states no rule | Not a mechanism. It is R31's existing remedy, applied to a third case R31's wording did not obviously cover |
| 2 — 0030 clause 1 is not reached | Not a mechanism, and the reason this record exists. Enforced by review |
| 3 — prefer non-implementation | **Already true for both instances**, and now true on purpose. `Conditions.speeds_after` implements no proportional effect; `core.hazards` implements neither Dehydration nor Malnutrition |
| 4 — refuse the combination where the engine must answer | **Not built, and unreachable today.** No contradiction is reachable from a built mechanic. Filed as [#209](https://github.com/eddiefiggie/srd-rules-engine/issues/209) |
| 5 — a clause-4 refusal is a read-surface refusal | **Not built, with clause 4** — [#209](https://github.com/eddiefiggie/srd-rules-engine/issues/209) holds both. The constraint is recorded now so that whoever builds it does not satisfy clause 4 by raising mid-ruling |
| 6 — each instance is named beside the code | **Built.** `Conditions.speeds_after` cites this record and #205 |

**Neither settled issue is closed by resolving its contradiction**, and that is the point. #182 and
#205 are closed as *decided*: the engine will not model either combination, and the reason is
recorded here rather than re-derived by the next person who needs one of them.

_Written 2026-08-25 against SRD v5.2.1._
