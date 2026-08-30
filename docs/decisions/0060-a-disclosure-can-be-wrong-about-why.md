# 0060 — A disclosure can be wrong about why

- **Status:** Accepted, 2026-08-30
- **Settles:** [#360](https://github.com/eddiefiggie/srd-rules-engine/issues/360)
- **Requirements:** R14, R17, R18, R32
- **Related:** [0058 — a field nothing reads is a rule modelled and not applied](0058-a-field-nothing-reads-is-a-rule-not-applied.md),
  which wrote two of the three disclosures this corrects;
  [0056 — a move is refused where it is made](0056-a-move-is-refused-where-it-is-made.md),
  which found the same failure in Frightened's disclosure;
  [#356](https://github.com/eddiefiggie/srd-rules-engine/issues/356)

## Context

0058 found seven `ConditionEffects` fields populated and read by nothing, built three, and
disclosed four. #359 built two of the four. These are the last three, and **two of their
disclosures were wrong about why** — written two builds ago, by me, in this repository.

> `checks-requiring-sight-not-identified` — "which checks *require sight* is not tabulated by
> the document ... so the automatic failure has nothing to key on"

It has one. `EncounterState.perception_of` has enforced p. 178's automatic failure since #138 —
by naming `Condition.BLINDED` directly and **quoting the very sentence the field is transcribed
from**. The rule was built, in a second module, with nothing holding the two copies together.

## Decision

1. **`perception_of` reads `Conditions.auto_fails_checks_requiring_sight`** rather than naming
   the condition. One source of truth, and a second condition carrying the flag now works at
   the check instead of working in the table and nowhere else.

   `can_see` still names `Condition.BLINDED`, and correctly: that is p. 178's *other* clause —
   "You can't see" — which is about sight rather than about checks.

2. **Blinded's disclosure says what is actually missing.**
   `only-seeing-declares-that-it-requires-sight`: the rule is applied to the one check this
   engine knows requires sight, and no other check declares which sense it needs.

3. **Deafened's is not the same gap, and now says so.** `no-check-requires-hearing` — there is
   not even one consumer, which is a different state from Blinded's and was described
   identically.

4. **Incapacitated's is sharper than "speech is not modelled".**
   `no-rule-consumes-speech`: p. 105's Verbal component is speech's one mechanical consumer in
   the document, and **Incapacitated is the only condition that sets `cannot_speak` while also
   setting `cannot_act`** — so a creature that cannot speak cannot cast either, and the link
   would be unreachable code. What is missing is a rule about speech that is not casting.

5. **No accessor is written for a field with no consumer.** One was, for hearing, "so whoever
   builds the check finds the question asked" — and a corruption proof showed it **defeated the
   guard**: an accessor is a read, so a property nothing calls makes an unconsumed field look
   consumed. It was removed and the reason is recorded where the next person will reach for it.

## Why

### A disclosure is a claim, and claims can be wrong

R32's machinery names a gap so it is not discovered later. Nothing checks that the *naming* is
accurate. This is the second time in four builds a disclosure has been found misdiagnosed —
0056 found Frightened's saying the clause needed a direction when it needed two distances, and
that error had propagated into two issues before anyone checked.

`tests/test_disclosures_are_pinned.py` says outright that whether a clause's rule is genuinely
unbuilt is the judgement no machine makes. This record is the other half of that sentence: the
*reason* attached to a clause is not checked either, and a wrong one is worse than a vague one
because it redirects whoever reads it.

### The guard can be defeated by satisfying it

#356's guard asks whether a field is read. An accessor written *for* the guard reads it. That is
not a hypothetical — it happened in this change, in good faith, and only the corruption proof
caught it. The rule is now stated where the temptation lives: an accessor is written when a
consumer needs it, not before.

## Consequences

- **Five of the original seven fields are now read**, and two remain disclosed with accurate
  reasons.
- **Two vacuous assertions were found by proofs and fixed.** One checked
  `not can_see(...).can_see` for a Blinded creature — true for a *sighted* one too, because
  nobody stated the light and 0025 clause 2 refuses to assume daylight. It asserts the verdict
  now.
- **No coverage figure moves — 116 of 210.** The fifth record to say so.

## Evidence

- p. 178 — Blinded's two clauses, and that the check one is the sentence `perception_of` quotes.
- p. 180 — Deafened's automatic failure.
- p. 184 — Incapacitated's "You can't speak", beside "You can't take any action".
- p. 105 — the Verbal component, speech's one mechanical consumer.

## Status of implementation

**Every clause is built** by [#360](https://github.com/eddiefiggie/srd-rules-engine/issues/360).

| Clause | State |
|---|---|
| 1 — one source of truth for the sight failure | **Built.** `perception_of`, asserted with a condition that is not Blinded |
| 2 — Blinded's disclosure corrected | **Built.** `only-seeing-declares-that-it-requires-sight` |
| 3 — Deafened's distinguished from it | **Built.** `no-check-requires-hearing` |
| 4 — Incapacitated's sharpened | **Built.** `no-rule-consumes-speech` |
| 5 — no accessor without a consumer | **Built.** The hearing accessor was removed and the reason recorded |
