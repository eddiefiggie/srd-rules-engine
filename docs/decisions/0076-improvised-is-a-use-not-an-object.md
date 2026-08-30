# 0076 — Improvised is a use, not an object

- **Status:** Accepted, 2026-08-30
- **Settles:** [#264](https://github.com/eddiefiggie/srd-rules-engine/issues/264)
- **Requirements:** R12, R15, R18, R31, R32
- **Related:** [0040 — a weapon is an item and proficiency is the wielder's](0040-a-weapon-is-an-item-and-proficiency-is-the-wielders.md),
  whose clause 5 decided this shape;
  [0075 — ties are a person's](0075-ties-are-a-persons-and-initiative-is-a-dexterity-check.md),
  the same question one build earlier and with a different answer;
  [0039 — equipment is what a creature carries](0039-equipment-is-what-a-creature-carries.md),
  clause 2, whose test `Item.improvised_damage_type` has to pass

## Context

p. 183:

> An improvised weapon is an object wielded as a makeshift weapon, such as broken glass, a
> table leg, or a frying pan. **A Simple or Martial weapon also counts as an improvised weapon
> if it's wielded in a way contrary to its design**; if you use a Ranged weapon to make a
> melee attack or throw a Melee weapon that lacks the Thrown property, the weapon counts as an
> improvised weapon.

> **Proficiency.** Don't add your Proficiency Bonus to attack rolls with an improvised weapon.
> **Damage.** On a hit, the weapon deals 1d4 damage of a type **the GM thinks is appropriate**
> for the object.
> **Range.** If you throw the weapon, it has a normal range of 20 feet and a long range of 60
> feet.
> **Weapon Equivalents.** If an improvised weapon resembles a Simple or Martial weapon, the GM
> may say it functions as that weapon and uses that weapon's rules.

Three sites in the engine deferred to this issue by refusing: a Melee weapon thrown without
Thrown, a non-weapon object being equipped-and-attacked-with, and the throw menu.

## Decision

1. **Improvised-ness is a property of the attack**, expressed by its own action key
   (`improvised-attack:<object>:<target>`) and resolved by its own resolver. The second
   sentence of p. 183 forecloses the alternative: an `ImprovisedWeapon` type, or a flag on
   `Item`, could not express a longbow swung as a club — which is the document's own example.

2. **Its own resolver rather than a branch on the weapon path**, for the reason the Unarmed
   Strike has one. Two of p. 183's four rules *contradict* that path — the dice are 1d4
   whatever the object's are, and the Proficiency Bonus is never added rather than added when
   proficient — so a flag would suppress more of it than it kept.

3. **The damage type is supplied by the ruleset**, on `Item.improvised_damage_type`. p. 183
   hands it to a person, and this is the channel `Weapon.damage_type` already uses for exactly
   the same kind of fact.

4. **An unstated type refuses, and is not untyped damage.** The read surface offers no attack
   with an object nobody has ruled on, and the resolver refuses one that arrives anyway.
   Untyped damage would be *worse* than a refusal: it would interact with Resistance,
   Vulnerability and Immunity as though somebody had ruled, and the ruling would be the
   engine's.

5. **The ability modifier stays on both rolls.** p. 183 alters the dice and removes the
   Proficiency Bonus *from the attack roll*. It says nothing about the ability modifier, so
   the general rule applies rather than an exception being read into a sentence that does not
   make one.

6. **Five feet**, from p. 190's Unarmed Strike rather than the wielder's reach. p. 186 defers
   to any rule that says otherwise, p. 183 states no reach, and a Glaive-holder does not get
   ten feet of frying pan.

7. **Weapon Equivalents is stated and not modelled.** "the GM **may** say it functions as that
   weapon" is a person choosing to substitute one thing for another, and a ruleset expresses it
   by supplying that weapon. There is no mechanism to build.

8. **The thrown half is not built**, and is filed as
   [#390](https://github.com/eddiefiggie/srd-rules-engine/issues/390). Offering a throw
   without its 20/60 range would be a rule half-applied; the numbers are read and asserted so
   whoever builds it does not re-read them.

## Why

### #264 posed the damage type as a three-way choice, and the answer is two of the three

The issue framed it as: a supplied fact, or a refusal, or untyped damage with the gap
disclosed — "**That choice is the work here.**"

It is a supplied fact **and** a refusal, and they are not alternatives. The ruleset supplies
what it has ruled on; the engine refuses what nobody has. What is rejected is the third:
untyped damage is not an absence of a ruling, it is a ruling — that Resistance to Bludgeoning
does not apply — made by whoever left the field blank.

### Two builds, two questions the document hands to a person, two different answers

[0075](0075-ties-are-a-persons-and-initiative-is-a-dexterity-check.md), one build earlier, met
the same shape in initiative ties and answered it differently: **declare a convention**. The
difference is worth stating, because a reader meeting both will otherwise think one of them is
inconsistent.

A tie must resolve — the engine needs a total order to be reproducible at all, and there is no
"refuse to order the combatants". So it adopts a stable convention and says it is one.

An improvised attack need not happen. Nothing forces the engine to produce a swing with no
stated damage type, and refusing costs a caller one field of ruleset data. **When declining is
possible, decline; when it is not, declare a convention.** That is the general rule the two
records together establish, and neither could have stated it alone.

### Why the field passes 0039 clause 2

`Item` deliberately holds "the fields the engine has rules about, and no others", and
`tests/test_equipment.py` pins the set. A fourth field needs the test that clause sets, in both
directions: the engine has a rule about this one (1d4 of *that* type, no Proficiency Bonus),
and something reads it. It is not a name or a price by another route — those describe the
object, while this is a person's ruling about what happens when it is swung.

## Consequences

- **Three deferring comments can be re-pointed.** The `_weapon_and_target` refusal for a
  thrown Melee weapon now stands on #390 rather than on #264: half its stated reason — the
  unavailable judgement — has a home, and what remains is the range.
- **`improvised-weapons` stays unclaimed in the inventory**, because p. 183 has four rules and
  the throw is one of them. A shape claimed at three-quarters is the overstatement #371 found
  a build ago, in this same file.

## Status of implementation

| Clause | State |
|---|---|
| 1 — a use, with its own key | **Built** |
| 2 — its own resolver | **Built.** `improvised_attack_resolver` |
| 3 — the type is the ruleset's | **Built.** `Item.improvised_damage_type` |
| 4 — unstated refuses, at both surfaces | **Built** |
| 5 — the ability modifier stays | **Built** |
| 6 — five feet | **Built** |
| 7 — Weapon Equivalents stated, not modelled | **Built**, in the sense that the decision is to hold no mechanism |
| 8 — the thrown 20/60 | **Not built.** [#390](https://github.com/eddiefiggie/srd-rules-engine/issues/390) |

`scripts/verify_d20_rules.py` carries 291 clauses, up from 287; all four of p. 183's rules are
asserted including the one clause 8 defers, and the whole file was re-run against the document.

### Evidence

Seven corruption proofs, each red on the assertion written for it.

| Corruption | Went red on |
|---|---|
| the Proficiency Bonus added | `test_the_proficiency_bonus_is_not_added` |
| the dice widened to d8 | `test_the_damage_is_one_d4_of_the_type_the_ruleset_supplied`, `test_a_weapons_own_dice_and_type_do_not_carry_into_the_swing` |
| the unstated-type filter removed from the menu | `test_an_object_nobody_has_ruled_on_is_offered_nothing` |
| the unstated-type refusal removed from the resolver | `test_the_resolver_refuses_an_object_nobody_has_ruled_on` |
| weapons excluded from the offer | `test_a_real_weapon_is_offered_improvisedly_too` |
| the thrown normal range changed to 30 | `test_the_thrown_range_is_read_and_has_no_consumer_yet` |
| the verification's page blanked | `test_p183_is_asserted_against_its_page` |

The fifth is the one that matters: it corrupts the engine into treating improvised-ness as a
property of *objects that are not weapons*, which is the modelling this record exists to
reject, and it goes red on the document's own example.
