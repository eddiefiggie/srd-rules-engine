# 0040 — A weapon is an item, and proficiency is the wielder's

- **Status:** Accepted, 2026-08-28
- **Settles:** [#262](https://github.com/eddiefiggie/srd-rules-engine/issues/262)
- **Requirements:** R1, R15, R18, R31, R32
- **Related:** [0039 — equipment is what a creature holds, wears and carries](0039-equipment-is-what-a-creature-holds-wears-and-carries.md),
  whose clause 5 decided this and left the shape open;
  [0038 — a spell is data the caster carries](0038-a-spell-is-data-the-caster-carries.md),
  clauses 3 and 4, one of which applies here and one of which does not;
  [0026 — terrain enters as state](0026-terrain-enters-as-state.md), clause 1

## Context

0039 clause 5 settled that a weapon is equipment and deferred the build. Building it needs
four decisions, and the tree names the first of them itself. `_attack_detail`:

> The distance is reported rather than used to gate the offer. Whether a target is in range
> depends on the *weapon* — reach for a melee one, normal and long range for a ranged one —
> and **the read surface does not know which weapon an attack will use**. So it supplies the
> fact and leaves the judgement, rather than filtering on an assumption.

That reason ends here. A weapon the creature holds is a weapon `legal_actions` can see.

## Options considered

**Option 1 — composition: `Weapon(item=Item(...), damage_dice=...)`.** Rejected, and it is the
tidy-looking one. `Carried` holds an `Item`, so a ruleset building `Carried(weapon.item)` puts
the *item* in state and leaves the weapon outside it — at which point `legal_actions` is back
to not knowing which weapon an attack will use, and the natural repair is to pass the weapons
in. That is the repair 0026 clause 1, 0038 clause 1 and 0039 clause 1 each refused.

**Option 2 — a ruleset mapping from item id to weapon.** Rejected for the same reason one
step further along: the mapping lives in the ruleset, so state holds an id whose meaning only
the ruleset knows, and legality again needs an argument.

**Option 3 — `Item` grows the weapon fields.** Rejected. 0039 clause 2 holds `Item` to the
fields the engine has rules about *for every item*, and a torch does not have damage dice.
Optional-everywhere is how a type stops describing anything.

**Option 4 — `Weapon` is a subtype of `Item`.** Chosen. A weapon **is** an item — it has
weight and occupies hands — with more rules attached, and the subtype relation is the true
one rather than a convenience. It carries a dataclass wrinkle: `Item.id` has no default and
`Weapon`'s own fields must not follow defaulted ones, which `kw_only=True` settles.

## Decision

**1. `Weapon` is a subtype of `Item`, declared keyword-only.** A creature's `equipment` then
carries weapons as it carries anything else, and `legal_actions` sees the numbers legality
turns on without an argument. `isinstance` is the discriminator, which is a real subtype test
rather than the `kind` field 0019 refuses — the two are distinguishable by whether a
consumer branches on *data* or on *type*.

**2. Proficiency is the wielder's, and moves to the creature.** p. 89: "Anyone can wield a
weapon, but **you** must have proficiency with it to add your Proficiency Bonus." A
creature-weapon relation stored on the weapon works exactly while a weapon belongs to one
wielder, which is the closure world this ends; two creatures holding the same kind of weapon,
or one picking up another's, breaks it silently and in the direction that grants a bonus.

**Keyed by weapon id, and the document's categories are the ruleset's to expand.** p. 89
grants proficiency by category — Simple, Martial — and the categories are in the weapons
table, which is content this repository does not ship (R31). So the engine holds the resolved
relation and a ruleset that knows the categories expands them into ids. That is the same split
as "no spell list ships": the engine holds what a rule reads, the ruleset holds what a table
says.

**3. The read surface gates attacks on reach and range.** The reason it did not is gone, and
R18 asks for legality to be **computable**. One offer per (held weapon, reachable target),
enumerated the way 0038 clause 4 enumerates a spell's payable slot levels — so the weapon is
chosen from a menu the engine computed rather than named in a declaration the engine has to
check afterwards.

**A long-range shot stays on the menu.** p. 90 gives a ranged weapon a normal range and a long
range and imposes Disadvantage beyond the first; only beyond the second is the attack
impossible. Filtering at normal range would remove a shot the document allows.

**4. No wrapper, and the difference from spells is the reason.** 0038 clause 3 wrapped a
spell's resolver because a spell's **effect** comes from outside the engine and a ruleset
could forget to pay the costs. An attack's effect is stated by the document and shipped here:
`attack_resolver` is engine code, and the only ruleset data is the weapon's numbers, which now
ride on the creature. There is nothing outside the engine to wrap. So the resolver reads the
weapon from what the creature holds, and one attack rule replaces one rule per weapon.

**This is a case where copying the spell shape would have been wrong**, which is why it is
written down rather than left to look like an omission.

**5. Improvised is a use, not an object.** p. 183: "A Simple or Martial weapon also counts as
an improvised weapon **if it's wielded in a way contrary to its design**." So improvised-ness
belongs to the attack rather than to the item, and no `ImprovisedWeapon` type is right. Its
damage is "1d4 damage of a type **the GM thinks is appropriate**" — a person's judgement,
which this engine may not invent and which would arrive as a supplied fact or not at all.
Decided here so clause 1's shape leaves room for it; built by nobody yet
([#264](https://github.com/eddiefiggie/srd-rules-engine/issues/264)).

## Why

**Clause 2 is the clause this record exists for.** Moving a weapon onto a creature is a
refactor; noticing that `proficient` was never the weapon's is a rules fix, and it would have
travelled across the refactor unexamined because it is a field that already worked. It fails
in the direction that *adds* a bonus, which is the direction nobody reports.

**Clause 4 is the one the pattern would have got wrong.** Three records in a row have moved
ruleset data onto the creature and two of them wrapped a resolver, so wrapping this one is
what a reader — and an implementer working from the pattern — would expect. The wrapper is not
a house style; it exists for a specific hazard that is absent here. Applying it anyway would
add indirection to protect against nothing.

**Clause 3 turns a disclosed limitation into a promise.** The read surface has been reporting
distance and declining to judge, honestly and with the reason written down. Once it can judge,
continuing to decline would be a menu that knows an attack is impossible and offers it anyway.

## Consequences

**Accepted costs.**

- **`isinstance` enters the engine as a discriminator.** It is a real subtype test and not a
  `kind` field, but it is still a branch, and the next subtype of `Item` will make it a chain.
  Worth watching; not worth a registry today.
- **One rule per weapon becomes one attack rule**, which is a breaking change for any ruleset
  that registered weapons the old way. `API_VERSION` and 0018's tiers govern what that costs,
  and `attack_resolver` is not on the COMMITTED surface.
- **Proficiency by id rather than by category** means a ruleset expands Simple and Martial
  itself. Faithful, and more work for the ruleset than the document implies.

**Follow-on effects.**

- **Five weapon-property shapes become buildable** — `ammunition`, `light`, `loading`,
  `thrown`, `two-handed` — and `improvised-weapons` becomes expressible.
- **p. 177's equip and unequip** — "You can either equip or unequip one weapon when you make
  an attack as part of this action" — becomes statable for the first time, and is
  [#265](https://github.com/eddiefiggie/srd-rules-engine/issues/265).
- **Coverage does not move on this record.** It decides; [#258](https://github.com/eddiefiggie/srd-rules-engine/issues/258) builds.

## Evidence

Read in the official SRD v5.2.1 PDF for this record: **p. 89** (*Weapon Proficiency*, and the
Ammunition, Finesse and Heavy properties), **p. 90** (Two-Handed, Versatile, Range), **p. 177**
(*Attack [Action]*'s equip/unequip clause), **p. 183** (*Improvised Weapons*, whole).

In the tree:

- `_attack_detail`'s docstring states that the read surface does not know which weapon an
  attack will use, and declines to gate on range for that reason.
- `Weapon.proficient: bool = True` is read at `core/combat.py` to add the proficiency bonus.
- `attack_resolver(weapon)` closes over a `Weapon`; a ruleset registers one rule per weapon.
- `Combatant.equipment` and `Item` exist as of #257, and `Carried.item` is typed `Item`.

## Status of implementation

**Decided, and none of it built.** The gate closes with this record, so each clause is tracked:

| Clause | State |
|---|---|
| 1 — `Weapon` is a keyword-only subtype of `Item` | **Decided, not built.** [#258](https://github.com/eddiefiggie/srd-rules-engine/issues/258) |
| 2 — proficiency is the wielder's, keyed by weapon id | **Decided, not built.** [#258](https://github.com/eddiefiggie/srd-rules-engine/issues/258) |
| 3 — the read surface gates on reach and range, long range included | **Decided, not built.** [#258](https://github.com/eddiefiggie/srd-rules-engine/issues/258) |
| 4 — no wrapper, because an attack's effect is the engine's | **Decided, not built.** [#258](https://github.com/eddiefiggie/srd-rules-engine/issues/258) |
| 5 — improvised is a use, not an object | **Decided, not built.** [#264](https://github.com/eddiefiggie/srd-rules-engine/issues/264) |

**#262 is closed by this record.** #258 builds clauses 1-4; the weapon properties it unblocks
are [#263](https://github.com/eddiefiggie/srd-rules-engine/issues/263), and p. 177's
equip/unequip is [#265](https://github.com/eddiefiggie/srd-rules-engine/issues/265).

_Written 2026-08-28 against SRD v5.2.1._
