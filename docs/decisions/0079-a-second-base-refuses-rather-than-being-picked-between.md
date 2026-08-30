# 0079 — A second base refuses rather than being picked between

- **Status:** Accepted, 2026-08-30
- **Settles:** [#394](https://github.com/eddiefiggie/srd-rules-engine/issues/394)
- **Requirements:** R15, R18, R31, R32
- **Related:** [0077 — Armour Class is a chosen base, plus bonuses](0077-armour-class-is-a-chosen-base-and-bonuses.md),
  whose clause 6 this settles;
  [0076](0076-improvised-is-a-use-not-an-object.md) and
  [0075](0075-ties-are-a-persons-and-initiative-is-a-dexterity-check.md), whose
  decline-or-declare rule this applies;
  [0058 — a field nothing reads is a rule modelled and not applied](0058-a-field-nothing-reads-is-a-rule-not-applied.md),
  which is why the *stating* half is not built

## Context

p. 177: *"If a rule gives you another base AC calculation, **you choose** which calculation to
use; you can't use more than one."*

0077 clause 6 decided the choice is the creature's and is stated rather than computed, and
[#393](https://github.com/eddiefiggie/srd-rules-engine/issues/393) built the derivation
assuming one base. #394 asked what an *unstated* choice does, and said refusing was the likely
answer and should be argued rather than assumed.

## Decision

1. **An unstated choice refuses.** Reading `effective_armour_class` for a creature with two
   base calculations raises, naming p. 177 and saying the engine has nowhere to record which
   was chosen.

2. **p. 92's one-suit rule and p. 177's one-calculation rule are separate checks.** They were
   one, and coincided only while worn armour was the engine's single source of a base.

3. **The mechanism for *stating* a choice is not built**, and is not filed. Nothing in this
   engine can give a creature a second base except a second worn item, and p. 92 already
   refuses two suits — so a stating mechanism would be machinery with no reachable case, which
   is the shape 0058 names and #371 and #264 each found claimed. It becomes buildable when a
   *feature* can grant a calculation, which needs class data this repository does not ship.

## Why

### Refusing is available here, and that is not obvious

0075 and 0076 established: *when declining is possible, decline; when it is not, declare a
convention.* An attack must meet **an** AC, which looks like the tie case — you cannot refuse
to have an Armour Class mid-roll.

But the refusal does not happen mid-roll. `effective_armour_class` is read *before* anything
is rolled, and a creature whose AC cannot be determined is a creature whose ruleset has not
finished describing it. So declining **is** possible, and the rule gives the same answer it
gave for an improvised weapon with no stated damage type.

### Both ways of picking are worse, and differently

- **Taking the highest** optimises invisibly. An optimised AC looks exactly like a chosen one,
  and nothing downstream distinguishes them — the property that makes an invention worse than
  an omission everywhere else in this engine.
- **Taking the first** depends on the order a ruleset happened to list the creature's
  equipment. It is arbitrary rather than optimal, which is better, and it is still a decision
  the document assigned to somebody else.

p. 177 did not leave the question open. It assigned it, the way p. 13 assigns initiative ties
and p. 183 assigns an improvised weapon's damage type. **An engine filling an assignment is
overriding an instruction, not filling a gap** — the distinction 0076 drew.

### The conflated check, and how it surfaced

`effective_armour_class` refused when it found more than one base, and reported it as
*"wearing N suits of armour, and p. 92 allows one at a time"*. That counted **calculations**
and called them **suits**.

While worn armour was the only source of a base the two were the same number, so the message
was true by coincidence. A worn item that is not armour breaks it: a creature in one suit of
plate and a pair of bracers has one suit and two calculations, and was told it wore two suits —
false, and citing the rule it had not broken.

Separating them is what makes p. 177's refusal survive a feature arriving. p. 92's is about
what a creature **wears**; p. 177's is about what it **uses**, and only the second is the one
#394 exists to protect.

### A corruption proof that came back green, and why it is recorded rather than counted

Replacing the base selection with `max(bases, key=...)` — the "pick the highest" invention —
left every assertion passing. That is not a vacuous test. **It is unreachable code**: the
refusal precedes the selection, so there is never more than one base to take a maximum of.

The distinction matters, because this repository has twice found a green proof meaning the
opposite. Here it means picking is **structurally impossible rather than merely avoided**,
which is the stronger property and the one #394 asked for. `tests/test_armour_class.py` asserts
the invariant directly, and the selection carries a comment saying why a corruption there
cannot be observed.

## Status of implementation

| Clause | State |
|---|---|
| 1 — an unstated choice refuses | **Built.** `Combatant.effective_armour_class` |
| 2 — p. 92 and p. 177 as separate checks | **Built** |
| 3 — the mechanism for stating a choice | **Deliberately not built and not filed.** Nothing can grant a second base, so it would be machinery with no case |

Clause 3 is `AGENTS.md`'s first filing exception — a note recorded so a later audit does not
re-raise it. **When a feature can grant a base calculation, the stating mechanism is what that
work needs**, and this record is where it is described.

### Evidence

Two corruption proofs held; the third is the one worth reading.

| Corruption | Result |
|---|---|
| p. 177's refusal disabled | red on `test_two_base_calculations_are_refused_by_p177_and_not_picked_between` and the separation test |
| p. 92's check widened to every worn item with a base | red on `test_p92_and_p177_are_different_rules_and_refuse_for_different_reasons` |
| the selection replaced with `max(...)` | **green — unreachable**, and asserted as such rather than counted as a proof |
