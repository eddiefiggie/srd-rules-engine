# 0039 — Equipment is what a creature holds, wears and carries

- **Status:** Accepted, 2026-08-28
- **Settles:** [#256](https://github.com/eddiefiggie/srd-rules-engine/issues/256)
- **Requirements:** R15, R17, R18, R19, R31, R32
- **Related:** [0038 — a spell is data the caster carries](0038-a-spell-is-data-the-caster-carries.md),
  which settled the same question for spells and whose clauses 1 and 2 this follows;
  [0026 — terrain enters as state](0026-terrain-enters-as-state.md), clause 1, which is why
  the list rides on the creature; [0019 — kind is a filing label](0019-kind-is-a-filing-label.md),
  for why *where an item is* is one field rather than three booleans

## Context

There is no equipment model in this engine, in any form. A `Weapon` is closure data on a
resolver — `attack_resolver(weapon)` closes over one, and `legal_actions` enumerates attacks
**without consulting a weapon at all**. Nothing records that a creature is holding anything,
wearing anything, or carrying anything.

That was invisible while nothing depended on it, and three printed rules now do:

> **Somatic (S).** A spellcaster must use at least one of their hands to perform these
> movements. — p. 105
>
> **Casting in Armor.** You must have training with any armor **you are wearing** to cast
> spells while wearing it. — p. 104
>
> **Carrying Capacity.** Your size and Strength score determine the maximum weight in pounds
> that you can **carry**. — p. 178

Wearing, holding, carrying. The document distinguishes three states and the engine has none
of them.

Thirteen shapes in the inventory are unimplemented and each needs some part of this:
`armor-training`, `attunement`, `carrying-capacity`, `improvised-weapons`,
`spellcasting-focus`, `item-charges`, `spell-cast-from-item`, `item-destruction`, and the five
weapon properties.

### The part that cannot ship

pp. 93-97 are tables of item names, weights and costs. That is **content**, in the same
category as p. 26's class tables and the spell descriptions, and R31 forbids compiling one
here. So equipment is ruleset data, and the only question is what shape it takes.

## Options considered

**Option 1 — an item catalogue in the engine.** Rejected outright, for the reason the spell
catalogue was: it is the content this repository does not ship, and every row would be a rule
value nobody could verify.

**Option 2 — equipment passed to the queries that need it.** Rejected, and it is the option
that would have arrived looking reasonable. `legal_actions(state, actor_id)` takes state and
nothing else; a caller handing it a creature's gear is a caller deciding what that creature
may do, one call at a time. [0026](0026-terrain-enters-as-state.md) clause 1 refused exactly
this for lighting and walls, and [0038](0038-a-spell-is-data-the-caster-carries.md) clause 1
refused it again for spells. Three subsystems, one answer.

**Option 3 — three boolean fields per item: worn, held, carried.** Rejected. They are
mutually exclusive and a boolean triple can express states the rules have no meaning for —
worn *and* held, or neither. A closed vocabulary refuses those by construction.

**Option 4 — model hands individually.** Rejected as inventing structure. p. 105 asks "at
least one of their hands" and p. 90's Two-Handed asks for two; neither asks *which*, and no
SRD rule this sweep found distinguishes left from right. Counting is what the document does.

## Decision

**1. Equipment is ruleset data carried by the creature.** A `Combatant` holds what it has,
beside `spells` and `slots`, for [0026](0026-terrain-enters-as-state.md) clause 1's reason.
What an item *is* — its name, its price, its description — is the ruleset's and does not
appear here.

**2. The engine holds only the fields it has rules about.** Three, and each traces to a
printed sentence:

- **Weight**, because p. 178 computes a carrying maximum in pounds.
- **How many hands holding it occupies**, because p. 105 needs a free one and p. 90's
  Two-Handed takes both.
- **Whether it is a Spellcasting Focus, and whether it is a Component Pouch**, because p. 105
  and p. 188 let either stand in for Material components.

No name, no cost, no rarity, no description. A field the engine has no rule about is a field
nothing reads, which is the decay this repository has now found three times.

**Note what is *not* on the item: whether a spell's materials are consumed, and whether they
have a cost.** p. 105 makes the substitution conditional on "a spell doesn't consume its
materials and doesn't specify a cost for them" — those are properties of **the spell's
component**, not of the pouch. They belong with the spell's component data, which
[0038](0038-a-spell-is-data-the-caster-carries.md) clause 2 deliberately deferred.

**3. Where an item is, is one field with a closed vocabulary: worn, held, or stowed.**
Mutually exclusive, because the rules that read them are mutually exclusive — armour you are
wearing is not occupying a hand, and a pouch in a pack is not one you can reach. "Stowed"
rather than "carried" because all three are carried: p. 178's capacity counts everything.

**4. Hands are counted, not identified, and one free hand serves both S and M.** p. 105:
"The spellcaster must have a hand free to access them, **but it can be the same hand used to
perform Somatic components, if any**." So a spell with both components needs **one** free
hand, not two. An implementation that charges a hand per component is wrong for every S,M
spell, which is most of them.

**5. A weapon is equipment.** Decided here and built later
([#258](https://github.com/eddiefiggie/srd-rules-engine/issues/258)). The closure was right
while nothing depended on what a creature holds; p. 177 already had a rule it could not
express — "You can either equip or unequip one weapon when you make an attack as part of this
action" — and all five weapon properties are about how a weapon is held or spent. Deciding it
now and building it later is what keeps a large behavioural change to combat out of the change
that introduces the subsystem.

**6. Size is a creature's property and does not ride in on this.** p. 178's Carrying Capacity
is a table keyed on Size and Strength, so the shape is blocked on a `Size` this engine does
not have — and p. 188 defines size as what "determines how much space the creature occupies in
combat", which is about positions and areas rather than about gear. Filed as
[#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259) so that carrying capacity
is blocked on the right thing.

**7. What this still will not check, disclosed rather than implied (R32).** Attunement
(p. 177) needs a bond formed over time and a limit of three, none of which this models. Item
charges, item destruction and spells cast from items each need more of an item than clause 2
holds. The model this record settles is the floor those stand on, not a substitute for them.

## Why

**Three subsystems have now asked the same question and got the same answer**, which is the
strongest evidence the answer is structural rather than convenient. Terrain (0026), spells
(0038), equipment (here): each time, the thing a query needs in order to decide legality has
to be *on the state*, because the alternative lets a caller choose the outcome by choosing the
argument. Naming the pattern is most of this record's value.

**Clause 4 is the clause this record would have got wrong.** "Somatic needs a hand, Material
needs a hand" reads as two hands, and it is one — p. 105 says so in a subordinate clause at
the end of a paragraph about pouches. A model built from the summary would refuse spells the
document permits, and it would look careful doing it.

**Clause 2's exclusions are not gaps and should not be filed as any.** Price and description
are content. Consumed-and-cost belong to the spell. The list of things an item does *not*
carry is short precisely because the engine's rules about items are few, and a longer list
would be a model of equipment rather than a model of the rules about equipment.

**Clause 5 is a decision rather than a deferral.** The alternative — leaving whether a weapon
is equipment open — produces two models to reconcile later, and this repository has just paid
for that: 0037 clause 3 named a place for retirement that clause 4 then made wrong, and the
correction cost a section of a record. Deciding now and slicing the build is cheaper than
deciding twice.

## Consequences

**Accepted costs.**

- **`Combatant` grows again** — `spells` in #248, equipment here. It is becoming the place
  where ruleset data about a creature accumulates, which is what clause 1 chose deliberately
  and is worth watching.
- **A weapon will move**, and combat's seam changes when it does. That is a known future cost,
  named and filed rather than discovered.
- **"Stowed" is this record's word**, not the document's. p. 178 says "carry" for the whole
  and the rules do not name the residual state. A coined term is a small debt; the alternative
  was three booleans that can express nonsense.

**Follow-on effects.**

- **#245's two halves separate cleanly.** The equipment model is
  [#257](https://github.com/eddiefiggie/srd-rules-engine/issues/257); the component check
  needs the spell's V/S/M data as well and stays on #245.
- **#247's Casting in Armor** gains half of what it needs — "any armor you are wearing" — and
  still needs armour training, which is a proficiency rather than an item.
- **Coverage does not move on this record.** It decides; the slices build.

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 104** (*Casting in Armor*),
**p. 105** (*Components*, all three, including the free-hand clause), **p. 177**
(*Attack [Action]*'s equip/unequip, and *Attunement*), **p. 178** (*Carrying Capacity*, with
its table and its Speed consequence), **p. 183** (*Improvised Weapons*), **p. 188**
(*Spellcasting Focus*, and *Size*), and **pp. 93-97**, which are the item tables this
repository does not ship.

In the tree:

- `attack_resolver(weapon)` closes over ruleset data; `legal_actions` never consults a weapon.
- `Combatant` has no field for anything held, worn or carried, and no `Size`.
- `core.inventory` is the effect-shape inventory rather than a creature's possessions — a
  name collision that makes this gap look filled from a file listing.
- Thirteen inventory shapes are unimplemented and blocked on some part of this.

## Status of implementation

**Clauses 1-5 and 7 are built** — 1-4 and 7 by [#257](https://github.com/eddiefiggie/srd-rules-engine/issues/257), clause 5 by
[#258](https://github.com/eddiefiggie/srd-rules-engine/issues/258). Clause 6 is decided and tracked by [#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259).

**What the build found that this record did not.** Clause 4 said hands are counted and did not
say where the count comes from — and **no rule in SRD v5.2.1 states how many hands a creature
has**. Every printed rule is relational, so the number is ruleset data with no engine default:
`Combatant.hands` is `int | None`, and a creature whose ruleset did not say has an unanswerable
count rather than two. Assuming two would have been the inferred rule value R31 forbids, and it
would have looked like common sense.

| Clause | State |
|---|---|
| 1 — equipment is ruleset data on the creature | **Built.** `Combatant.equipment`, and `legal_actions` still takes state and `actor_id` only |
| 2 — the engine holds weight, hands, and the two component flags | **Built.** `Item` has exactly those five fields, and a test pins the set so a sixth cannot arrive quietly |
| 3 — worn, held or stowed, as one closed field | **Built** as `Carriage`, defaulting to stowed — the direction that cannot invent a free hand or armour nobody put on |
| 4 — hands are counted, and one free hand serves both S and M | **Built, and the clause gained a finding.** The count is `int \| None` because **no SRD rule states how many hands a creature has** — the record assumed one could be held and did not say where the number comes from. p. 105's shared-hand sentence is now an asserted verifier clause. The check that reads it is still [#245](https://github.com/eddiefiggie/srd-rules-engine/issues/245) |
| 5 — a weapon is equipment | **Built.** `Weapon` is a keyword-only subtype of `Item` and rides on `Combatant.equipment`; [0040](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md) settled the shape and [#258](https://github.com/eddiefiggie/srd-rules-engine/issues/258) built it |
| 6 — Size is the creature's, not the equipment's | **Decided, not built.** [#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259), which is what `carrying-capacity` is actually blocked on |
| 7 — what is still unchecked, disclosed | **Built.** `core.equipment`'s docstring names attunement, item charges, carrying capacity, weapons and armour training, each pointing at its issue; guarded |

**#256 is closed by this record.** #245 keeps its spell-side half, #247 keeps armour training,
and #19 stays open as the umbrella.

_Written 2026-08-28 against SRD v5.2.1._

_Corrected 2026-08-29 ([#291](https://github.com/eddiefiggie/srd-rules-engine/issues/291)). Clause 5 read "**Decided, not built.** #258" from the
day #258 merged until an audit compared every "not built" row against live issue state. The row
cited a **closed** issue for work that had shipped — which reads as finished and as absent at
the same time, and is the defect #291 exists to make mechanically detectable. Nothing about the
decision changed; only this section, which is the one part of a record that moves._
