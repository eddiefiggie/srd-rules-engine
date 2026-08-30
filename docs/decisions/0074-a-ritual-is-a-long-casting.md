# 0074 — A Ritual is a long casting

- **Status:** Accepted, 2026-08-30
- **Settles:** [#371](https://github.com/eddiefiggie/srd-rules-engine/issues/371)
- **Requirements:** R1, R15, R17, R31, R32
- **Related:** [0065 — a long cast spends its slot on completion](0065-a-long-cast-spends-its-slot-on-completion.md),
  whose machinery this joins and whose turn count this corrects;
  [0038 — a spell is data the caster carries](0038-a-spell-is-data-the-caster-carries.md),
  which is why the Ritual tag belongs on `Spell`;
  [0062 — the menu is not a promise](0062-the-menu-is-not-a-promise.md), which is why the
  resolver keeps a guard the menu makes unreachable

## Context

p. 105, *Longer Casting Times*:

> Certain spells—**including a spell cast as a Ritual**—require more time to cast: minutes or
> even hours. While you cast a spell with a casting time of 1 minute or more, you must take
> the Magic action on each of your turns, and you must maintain Concentration.

[#250](https://github.com/eddiefiggie/srd-rules-engine/issues/250) built that machinery for
spells whose `CastingTime` is `MINUTES`. **A Ritual reached it by no path at all.**
`ritual_cast` computed p. 187's ten extra minutes and had **no caller anywhere in the
engine**, so a caller could ritual a spell and take zero turns over it.

### The clause the whole issue rests on was asserted nowhere

`core.casting` quoted p. 105's ritual sentence in a docstring, to explain why rituals were
outside the machinery. `scripts/verify_d20_rules.py` had never read it: the asserted clause
began at *"While you cast a spell with a casting time of 1 minute or more"* and the sentence
naming rituals was not among the 282.

So the sentence licensing this entire change was, by this repository's own standard, a rule
the engine had not verified — quoted accurately, and from memory of a document rather than
from the document. It is asserted now (283 clauses), and everything below rests on it.

### The shape was claimed over a function with no caller

`ENGINE_SHAPES` said `"ritual": "core.spellcasting.ritual_cast"`, and the inventory reported
it **implemented**. `ritual_cast` computed a `RitualCast` and returned it to nobody.

That is the overstatement R17's inventory exists to prevent, and the same one
[#381](https://github.com/eddiefiggie/srd-rules-engine/issues/381) found for Opportunity
Attacks — except that shape was honestly **withheld** while this one was already claimed. A
claim over machinery is exactly what #382's standard rejects: *a detection with no production
caller is machinery rather than a resolved rule.*

## Decision

1. **The Ritual tag is a field on `Spell`.** p. 187 gates a Ritual on "a spell prepared that
   has the Ritual tag", and the tag is the spell's own — ruleset data, since this engine ships
   no spell list (#21). It was an argument to `ritual_cast` and nothing else, which is why the
   read surface could not offer a ritual: it asks the spells a caster carries.

2. **A Ritual is offered under its own key**, `ritual:<spell>`, beside the ordinary casting
   rather than instead of it. A caster holding a slot may still want the version that spends
   one.

   **The key carries no slot level, deliberately.** p. 187 draws the consequence itself —
   "It also doesn't expend a spell slot, which means the ritual version of a spell can't be
   cast at a higher level" — so a key with a level would offer the thing that sentence
   forbids.

3. **It is not gated on a slot.** A Ritual is on the menu for a caster whose slots are all
   spent, which is the case the document makes it most useful for.

4. **A Ritual begins a `LongCast` whose `slot_level` is `None`.** Not zero: a cantrip is a
   level 0 spell cast without a slot, and a Ritual of a level 3 spell is a level 3 casting
   that spends nothing. Collapsing them would say a ritualised spell was a cantrip, which is
   a claim about the spell rather than about how it was cast.

5. **The turns are `(the spell's own minutes, or none) + 10`, times ten.** p. 187 says "10
   minutes **longer to cast than normal**", so a spell that already takes a minute rituals in
   eleven. A spell whose normal casting time is an action adds its ten minutes to a base this
   engine holds no minutes for, and the total is ten minutes.

   That is not a rounding the document declined to give. The normal casting time of such a
   spell **is** one of the Magic actions p. 105 charges — the ritual takes the Magic action
   on every turn regardless — so the action is subsumed by the count rather than dropped.

6. **`ritual_cast` is what refuses**, called from the casting path rather than reimplemented
   there. Its three preconditions have been right since #19 and unreachable since #19.

7. **The resolver keeps a one-casting-at-a-time guard the menu makes unreachable.** 0062: the
   resolver asks the rule itself rather than deriving legality from the menu. The guard has
   its own test, called directly, because a test going through adjudication would pass on the
   menu's rejection and prove nothing about the guard.

## Why

### The turn count was wrong for every long casting, and building on it is what showed

`LongCast.turns_remaining` counts the Magic actions still owed, **this turn's included** — its
own docstring says so. The opening adjudication charged a Magic action *and* stored the full
count, so the first action was counted twice:

```
a 1-minute casting  ->  11 Magic actions charged, not 10
a 10-minute ritual  ->  101, not 100
```

`tests/test_long_casting.py` asserted `turns_remaining=10` after the begin from the day it
shipped, so the suite **encoded** the defect rather than catching it. It was found by writing
a ritual test that counted the actions end to end and got 101 for ten minutes.

It is fixed here rather than filed, because #371 is an `srd-fidelity` issue about charging a
ritual's turns and shipping a ritual that charges one turn too many on top of a base that
charges one turn too many would be building on a known-wrong number. The three assertions that
encoded it are corrected, and say why.

**A one-turn error is six seconds**, which is why nothing noticed. It is also exactly the kind
of error this repository's standing rules are about: wrong in a direction that looks right.

### Why the tag goes on `Spell` rather than staying an argument

0038 clause 1 keeps on `Spell` "the fields the engine has rules about, and no others", and
warns twice about fields nothing reads. The Ritual tag is the opposite case: a fact the engine
has a rule about, held nowhere, so the rule could not be reached. `has_ritual_tag` as a
parameter meant only a caller who already knew a spell was ritualisable could ask — and the
read surface, which must offer the option, had no way to know.

### Why a cantrip carrying the tag is refused

p. 187 rituals a *prepared* spell and saves a slot; a cantrip is outside preparation and
spends none. The document describes no ritual version of a cantrip, so the combination is
refused at construction rather than resolved into a guess about what it would cost (R31).

## Consequences

- **`ritual` is now genuinely resolved**, and `ENGINE_SHAPES` names the casting path rather
  than a function nobody called.
- **The coverage figure does not move**, because the shape was already claimed. That is worth
  saying plainly: this build made a published number *true* rather than larger, and the
  inventory could not have told anyone the difference.
- **Every long casting is one turn shorter**, which is a behaviour change for anything already
  using #250's machinery.

## Status of implementation

| Clause | State |
|---|---|
| 1 — `Spell.ritual` | **Built** |
| 2 — the `ritual:<spell>` key, carrying no level | **Built** |
| 3 — offered with no slots left | **Built** |
| 4 — `LongCast.slot_level` of `None` | **Built** |
| 5 — ten minutes *longer than normal* | **Built.** `ritual_turns_to_cast` |
| 6 — `ritual_cast` reached from the casting path | **Built** |
| 7 — the resolver's own guard, tested directly | **Built** |

p. 105's ritual sentence is asserted in `scripts/verify_d20_rules.py`, which now carries 283
clauses. The whole file was re-run against the document for this change and every clause
passed.

### Evidence

Eight corruption proofs, each red on the assertion written for it. `prove_against_base.sh`
cannot discriminate — `tests/test_ritual.py` is a new module and fails on *import* against the
base tree.

| Corruption | Went red on |
|---|---|
| the ritual key never dispatched | `test_beginning_a_ritual_starts_a_long_cast_that_owes_no_slot` |
| the base minutes forced to zero | `test_a_ritual_adds_its_ten_minutes_to_the_spells_own` |
| the completion made to spend a slot | `test_a_completed_ritual_expends_no_slot` |
| the offer removed | `test_a_prepared_tagged_spell_is_offered_as_a_ritual`, `test_a_ritual_is_offered_with_every_slot_spent` |
| the ritual's `- 1` reverted | `test_a_ritual_charges_every_one_of_its_turns` |
| the **ordinary** long cast's `- 1` reverted | three tests in `test_long_casting.py` |
| `Spell.ritual` defaulted to `True` | `test_a_spell_without_the_tag_is_not_offered_as_a_ritual` |
| the cantrip refusal disabled | `test_a_cantrip_cannot_carry_the_ritual_tag` |

The sixth is the one worth keeping: it proves the corrected turn count on the tests that used
to assert the wrong one, which is the only way to show the correction is load-bearing rather
than cosmetic.
