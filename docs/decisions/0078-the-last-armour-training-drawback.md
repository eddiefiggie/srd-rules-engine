# 0078 — The last armour-training drawback

- **Status:** Accepted, 2026-08-30
- **Settles:** [#367](https://github.com/eddiefiggie/srd-rules-engine/issues/367)
- **Requirements:** R15, R18, R31, R32
- **Related:** [0077 — Armour Class is a chosen base, plus bonuses](0077-armour-class-is-a-chosen-base-and-bonuses.md),
  which built the derivation this withholds from;
  [0063 — training is a legality rule](0063-training-is-a-legality-rule.md) and
  [0064 — any D20 Test, not any saving throw](0064-any-d20-test-not-any-saving-throw.md),
  the first two drawbacks;
  [0040 — a weapon is an item](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  clause 2, whose by-item-id relation is why the *category* was never needed

## Context

p. 177, *Armor Training*, states three drawbacks:

> If you wear Light, Medium, or Heavy armor and lack training with it, you have **Disadvantage
> on any D20 Test that involves Strength or Dexterity**, and **you can't cast spells**. If you
> use a **Shield** and lack training with it, **you don't gain its AC bonus**.

Two were built. The casting prohibition landed with 0063 as a legality rule the read surface
answers; the Disadvantage landed with 0064, once `D20Test.ability` was passed by every site
that builds a test rather than by the six that build saves.

The Shield's stayed disclosed as `untrained-shield-still-grants-ac`, and #367 recorded its
dependency as *"AC being derived from what a creature wears, which is its own subsystem"*.
[0077](0077-armour-class-is-a-chosen-base-and-bonuses.md) and #393 built that, so this is the
last of the three.

## Decision

1. **`Combatant.armour_class_bonus` withholds the bonus of a Shield the creature lacks
   training with.** One condition, over a relation that already existed.

2. **The one-Shield refusal is asked before the training filter.** p. 92's "wield only one
   Shield at a time" is about *wielding*, and a creature holding two is holding two whether it
   may benefit from either. Filtering first would let an untrained Shield hide a second one.

3. **`untrained-shield-still-grants-ac` retires**, in the change that builds its rule and
   asserted beside it. p. 177 now discloses nothing.

4. **`untrained_shields` is removed.** It existed for one build to tell R32's disclosure which
   creature to name; the disclosure is gone, and a helper with no reader is the decay 0058
   describes.

5. **p. 177's Armor Training entry is asserted**, and p. 92's training sentence with it.
   Neither had been read — see below.

## Why

### It never needed the armour category, and looked for four builds as though it did

#367 recorded the Shield clause as blocked on `Item.is_armour` not distinguishing a Shield from
worn armour, and on that distinction requiring p. 177's *category* — content this repository
does not ship (R31). That framing survived four builds.

Both halves were wrong. **Carriage distinguishes them**: armour is worn and a Shield is held,
which is what 0039 clause 3 made a closed vocabulary for. And **training is by item id**, which
0040 clause 2 settled precisely so that the category would not be needed.

What was actually missing was a *derivation to withhold from*. Nothing can be taken out of a
stored total whose parts are unknown, and that is what #393 supplied. The disclosure's stated
reason said so, in a sentence that read like a subsystem dependency and was really a one-line
condition waiting on one.

### Two shipped rules were resting on a page nobody had read

`scripts/verify_d20_rules.py` carried **no armour-training clause at all** — not for the
casting prohibition 0063 built, nor for the Disadvantage 0064 built. Both were correct. Neither
was verified.

This is the standing rule added two builds earlier arriving for the third time in three
workloads, and the pattern is now specific enough to name: **the rules most likely to be
unasserted are the ones that were easy to implement.** A hard mechanic sends somebody to the
page; a one-sentence drawback gets built from the sentence somebody already quoted in an issue.
p. 177's entry is asserted whole here, so the two older builds acquire the provenance they
shipped without.

### The disclosure was also unreachable, and that is recorded in 0077

Between #393 and this record, `untrained-shield-still-grants-ac` was gated on
`untrained_armour`, which reads worn items — so it never reached a creature holding an
untrained Shield. It was pinned, disclosed, and could not fire for its own case. Fixed in #393
and retired here, one build later.

## Consequences

- **The published clause figure falls to 14**, from 15. It is the figure that improves by going
  down, and p. 177 no longer contributes to it.
- **`tests/test_casting.py`'s assertion is replaced**, not amended: it asserted the clause *was*
  disclosed, which was true and — as #393 found — true for the wrong creature.

## Status of implementation

| Clause | State |
|---|---|
| 1 — the bonus withheld without training | **Built.** `Combatant.armour_class_bonus` |
| 2 — the one-Shield refusal precedes the filter | **Built**, and proved by corrupting the order |
| 3 — the disclosure retired | **Built**, asserted beside the rule and removed from the pin |
| 4 — `untrained_shields` removed | **Built** |
| 5 — p. 177 and p. 92 asserted | **Built.** 297 clauses, up from 295 |

p. 177's three drawbacks are now enforced in full, which is the first entry in the Rules
Glossary this engine can say that about after having disclosed part of it.

### Evidence

Three corruption proofs, each red on the assertion written for it.

| Corruption | Went red on |
|---|---|
| the training filter removed | `test_an_untrained_shield_adds_nothing`, and the casting-side assertion |
| the one-Shield refusal disabled | `test_two_shields_are_refused_even_when_neither_is_trained` |
| the retired disclosure re-appended | `test_every_armour_training_drawback_is_now_enforced`, and the pin |

The second is the one worth keeping: it is the case where a creature holds two Shields and is
trained with neither, which a training-filter-first implementation would let through silently.
