# 0046 — A default and the rule that says otherwise are two shapes

- **Status:** Accepted, 2026-08-29
- **Settles:** [#316](https://github.com/eddiefiggie/srd-rules-engine/issues/316), and the
  inventory question it raises
- **Requirements:** R17, R18, R31, R32
- **Related:** [0040 — a weapon is an item and proficiency is the wielder's](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  clause 2, whose boundary this is the other side of;
  [0035 — two names for one thing are one shape](0035-two-names-for-one-thing-are-one-shape.md),
  which this does not contradict;
  [0033 — a glossary entry is an index, not a shape's boundary](0033-a-glossary-entry-is-an-index-not-a-shapes-boundary.md)

## Context

SRD 5.2 states the reach of a creature twice, in two sections, and the two sentences are not
the same rule.

> p. 186, Rules Glossary, *Reach*: A creature has a reach of 5 feet **unless a rule says
> otherwise**.

> p. 90, Equipment, *Reach*: A Reach weapon **adds 5 feet to your reach when you attack with
> it**, as well as when determining your reach for Opportunity Attacks with it.

The second is a rule that says otherwise. The first defers to it explicitly.

The inventory filed them as one entry, and said so in the generator:

> `Reach` is here as a weapon property but the Rules Glossary already defines it (p. 186), so
> it is not re-added.

That is true of the **term** and false of the **mechanic**. `reach` carried
`"implemented": true` on the strength of `DEFAULT_REACH_FEET`, which is the 5-foot default
alone — so one flag claimed two rules and the engine had built one of them. A reader consulting
the coverage instrument to find out whether Reach weapons work was told yes, for forty-five
builds.

The engine's behaviour matched the flag rather than the document. `Weapon` had no reach field;
`_within_weapon_range`, `_out_of_range` and `_left_reach` all bounded their answers by
`Combatant.reach`. A Glaive was never offered a target at 10 feet.

**The available workaround was worse than the gap.** `Combatant.reach` is an `int` and can be
set to 10. Doing so is wrong in two directions p. 90 rules out in the same sentence: the bonus
reaches every other weapon the creature holds — a Dagger in the off hand stabbing across 10
feet — and it reaches Opportunity Attacks made with any of them, where the document says "with
it" both times.

## Options considered

**Option 1 — build the property and leave the inventory folded.** Rejected. It repairs the
engine and leaves the instrument unable to distinguish the two mechanics, which is the state
that let the gap survive. The inventory's whole job under R17 is to be falsifiable.

**Option 2 — split the entry: `reach` keeps p. 186's default, `weapon-reach` is p. 90's rule.**
Chosen.

**Option 3 — retire `reach` and let `weapon-reach` carry both.** Rejected. p. 186's default
governs every creature including one holding nothing, and it is consumed independently — by
`_reaches` for an unarmed Opportunity Attack, and by `reachable_objects` for 0041's detached
items. It is a rule, not a preamble to the other one.

## Decision

**1. A default and the rule that displaces it are separate shapes when they fail
independently.** The inventory's stated granularity rule decides this and needed no new
principle: *entries sit at independently-failable granularity*, which is why each of the
fifteen conditions is its own entry. `reach` and `weapon-reach` failed independently for the
life of the file — one built, one not — which is the demonstration rather than the argument.

**2. This does not reopen 0035.** 0035 merged `save` into `saving-throw` because p. 187 says
they are two names for **one** thing, and `ENGINE_SHAPES` resolved both ids to the same
callable. Here the document states two different rules in two sections, and they resolve to
different code. Two names for one mechanic is one shape; two mechanics sharing a name are two.
The test is what the engine must build, not what the document calls it.

**3. A weapon's reach is the weapon's, and it adds.** `Weapon.reach_in_use(creature_reach)`
returns `creature_reach + 5`, not a flat 10. p. 186's 5 feet is a default and not a ceiling, so
a creature that already reaches 10 reaches 15 with a Reach weapon — an implementation returning
10 would *shorten* it. This is 0040 clause 2's boundary from the other side: `proficient` and
the grip were creature facts stored on the weapon, and this was a weapon fact stored on the
creature.

**4. Every consumer of reach takes the weapon, and there are three.** The read surface's offer
(`_within_weapon_range`), adjudication's bound (`_out_of_range`), and the Opportunity Attack
trigger (`_left_reach`). The read surface is the one that mattered most: it withheld the offer
entirely, so no later gate could have caught the omission — an attack the rules permit was
never presented. `_attack_detail` reports the same figure, because a detail saying 5 beside an
offer made at 10 contradicts the offer it describes.

**5. An Opportunity Attack is determined against a *set* of reaches, not a maximum.** p. 185
provokes when a creature "leaves your reach", p. 90 extends that reach "with it", and p. 191's
Unarmed Strike is always available — so the creature's own reach is always a candidate and each
held weapon may add another. A mover going from 5 feet to 7 leaves a Whip-wielder's own reach
while staying inside the Whip's, and provokes: the attack would simply be made with something
else. A maximum reports no provocation there, and taking only the creature's own reach reports
none at 12 feet. Only the set is right at both distances.

**6. Held, not carried.** `_reaches` reads `Carriage.HELD`, because an Opportunity Attack
cannot be made with a stowed weapon. A version reading all equipment passes every other case.

**7. No invariant ties the property to a Melee weapon.** Every weapon the document gives it to
is one, and p. 90 never says it requires one — asserting otherwise is the inferred rule value
#284 found already shipped in `Range`'s own check (R31). On a Ranged weapon it is inert,
because the range branch answers first.

## Consequences

The inventory is **210 shapes, 104 implemented**, up one in both. The denominator moving is a
consequence of the split rather than its purpose, and it moves the same way `save`'s removal
did in 0035 — toward the figure being more true, not toward it being larger.

**Two defects in the instrument were found by trying to use it**, and both are fixed here
because neither could be worked around honestly.

`IMPLEMENTED_SECTION_SHAPES` had drifted six shapes behind the shipped data
([#325](https://github.com/eddiefiggie/srd-rules-engine/issues/325)), so regenerating reported
97 implemented over a shipped 103. `tests/test_effect_shape_inventory.py` guarded the glossary
half of that claim and not this one — the same failure its own docstring describes, one
constant away from where it was looking.

Every section sweep ordered a page's lines by the top of the span bounding box
([#326](https://github.com/eddiefiggie/srd-rules-engine/issues/326)). Headings are 12pt
GillSans-SemiBold and body text is 10pt Cambria, the two fonts declare boxes of very different
height, and a heading therefore sorted *after* its own first body line by a constant 7.14pt.
Every entry's verified text was a window shifted one line late at both ends. Nothing went red,
because every pattern in the file was chosen by someone reading the shifted text — and p. 90's
Reach sentence lives entirely in the lost head, so this shape could not be cited honestly until
it was fixed. Ordering by baseline corrects it and changes no existing row.

## Status of implementation

**Every clause is built** by [#316](https://github.com/eddiefiggie/srd-rules-engine/issues/316).

| Clause | State |
|---|---|
| 1 — a default and the rule displacing it are two shapes | **Built.** `weapon-reach` is its own entry; `reach` keeps p. 186's default ([#316](https://github.com/eddiefiggie/srd-rules-engine/issues/316)) |
| 2 — this does not reopen 0035 | **Built.** The two ids resolve to different callables in `ENGINE_SHAPES`, which is the test 0035 applied ([#316](https://github.com/eddiefiggie/srd-rules-engine/issues/316)) |
| 3 — a weapon's reach adds to the creature's | **Built.** `Weapon.reach_in_use`, asserted against a creature whose own reach is 10 ([#316](https://github.com/eddiefiggie/srd-rules-engine/issues/316)) |
| 4 — all three consumers take the weapon | **Built.** `_within_weapon_range`, `_out_of_range`, `_left_reach`, and `_attack_detail`'s reported figure ([#316](https://github.com/eddiefiggie/srd-rules-engine/issues/316)) |
| 5 — a set of reaches, not a maximum | **Built.** `_reaches`, asserted at both the distance a maximum gets wrong and the one a bare creature reach gets wrong ([#316](https://github.com/eddiefiggie/srd-rules-engine/issues/316)) |
| 6 — held, not carried | **Built.** `items_in(..., Carriage.HELD)`, with a stowed Reach weapon asserted to grant nothing ([#316](https://github.com/eddiefiggie/srd-rules-engine/issues/316)) |
| 7 — no Melee invariant | **Built.** `Weapon.__post_init__` adds no check, and the field's note says why ([#316](https://github.com/eddiefiggie/srd-rules-engine/issues/316)) |
