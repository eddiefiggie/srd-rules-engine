"""What a creature holds, wears and carries (p. 104, p. 105, p. 178, p. 188).

[0039](../../../docs/decisions/0039-equipment-is-what-a-creature-holds-wears-and-carries.md)
settled the shape; this is clauses 1 to 4. Equipment is **ruleset data the creature carries**,
for the reason lighting, walls and spells are: `legal_actions(state, actor_id)` takes state and
nothing else, so a caller handing a creature's gear to a query would be a caller deciding what
that creature may do, one call at a time (0026 clause 1, 0038 clause 1).

pp. 93-97 are tables of item names, weights and costs. That is content, and none of it ships
here (R31). What ships is the small set of facts the engine has rules **about**.

## Hands are counted, and the count is not this engine's to assume

Every rule that mentions hands asks a relational question and **no rule in the document says
how many hands a creature has**:

- p. 89, Ammunition: "you need **a free hand** to load a one-handed weapon".
- p. 90, Two-Handed: "requires **two hands** when you attack with it".
- p. 105, Material: "must have **a hand free** to access them".
- p. 182, Grapple: "A creature must have **a hand free** to grapple another creature."

So `Combatant.hands` is `int | None` and defaults to `None`: the ruleset says, or nothing
does. Defaulting to two would be an inferred rule value of exactly the kind R31 forbids —
plausible, universal in most people's memory of the game, and stated nowhere in the SRD. A
creature whose ruleset did not say has **unknown** free hands, and every rule that turns on
them declines rather than guesses. That is the same shape as `slots: SpellSlots | None`, which
distinguishes a creature with no slots from one with none left.

## The clause an implementation gets wrong

p. 105, Material components:

> The spellcaster must have a hand free to access them, **but it can be the same hand used to
> perform Somatic components, if any.**

One free hand satisfies Somatic **and** Material together. A model charging a hand per
component refuses spells the document permits, and most spells with material components have
somatic ones too — so it is the common case rather than an edge (0039 clause 4).

Nothing here performs that check: it also needs the spell's V/S/M data, which 0038 clause 2
deferred. This module supplies the half about the creature —
[#245](https://github.com/eddiefiggie/srd-rules-engine/issues/245) is where the two meet.

## What this does not model, and will not until something else lands

R32, because "the creature's equipment" reads as complete to anyone who does not find the
boundary:

- **Attunement** (p. 177) — a bond formed over time, capped at three. Not modelled at all.
- **Item charges, item destruction, and spells cast from items** — each needs more of an item
  than the fields below, and each is its own unimplemented shape.
- **Carrying capacity** (p. 178) — the weights are here and the *capacity* is not, because
  p. 178's table is keyed on a creature `Size` this engine does not have
  ([#259](https://github.com/eddiefiggie/srd-rules-engine/issues/259)). `carried_weight`
  answers what is carried; nothing yet answers whether it is too much.
- **A weapon is equipment and is not one yet.** 0039 clause 5 decided it;
  [#258](https://github.com/eddiefiggie/srd-rules-engine/issues/258) builds it. Until then a
  `Weapon` remains closure data on `attack_resolver` and a creature holding a sword is not
  expressible.
- **Armour training** (p. 104), which is a proficiency rather than an item
  ([#247](https://github.com/eddiefiggie/srd-rules-engine/issues/247)).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum

from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.position import Position, within


class Carriage(StrEnum):
    """Where an item is, relative to the creature that has it (0039 clause 3).

    **One field rather than three booleans**, because the states are mutually exclusive and a
    boolean triple can express combinations the rules have no meaning for — worn *and* held,
    or none of the three. The vocabulary refuses those by construction (0019).

    Each member is here because a printed rule reads it:

    - `WORN` — p. 104: "any armor **you are wearing**".
    - `HELD` — p. 105: "a hand **free**"; p. 90's Two-Handed.
    - `STOWED` — the residual. p. 178 counts it toward what a creature carries, and nothing
      else in the document asks about it.

    **"Stowed" is this repository's word, not the document's** (0039 Consequences). p. 178
    says "carry" for the whole, and the rules do not name the state of a thing that is neither
    worn nor in a hand.
    """

    WORN = "worn"
    HELD = "held"
    STOWED = "stowed"


@dataclass(frozen=True)
class Item:
    """A piece of equipment, as much of one as this engine holds (0039 clause 2).

    Three facts, and each traces to a printed sentence: what it weighs (p. 178 computes a
    maximum in pounds), how many hands holding it takes (p. 105, p. 90), and whether it can
    stand in for a spell's Material components (p. 105, p. 188).

    **No name, no price, no rarity, no description.** Those are the ruleset's, and a field the
    engine has no rule about is a field nothing reads — the decay this repository has now
    found three times (#228, #215, #252).

    **And not whether a spell's materials are consumed or carry a cost.** p. 188 makes the
    substitution conditional on materials that "aren't consumed by the spell and don't have a
    cost specified" — properties of *the spell's component*, not of the pouch that replaces
    it. They belong with the spell's component data, which 0038 clause 2 deferred.

    `id` is identity rather than a name: it is what a declaration will name and what the
    ledger will record, exactly as `Spell.rule_id` is.
    """

    id: str
    #: Pounds, because p. 178 computes a carrying maximum in them. A float, because p. 178's
    #: own table produces halves — Tiny carries Strength times 7.5 lb — so an integer would
    #: round a bound the document states exactly.
    weight: float = 0.0
    #: How many hands holding it occupies (p. 90, p. 105). Zero for something worn or stowed,
    #: and for a held thing that takes no hand to keep hold of.
    hands_when_held: int = 0
    #: p. 188: "an object that certain creatures can use in place of a spell's Material
    #: components if those materials aren't consumed by the spell and don't have a cost
    #: specified." The second half is the spell's to state; this is the object's half.
    is_spellcasting_focus: bool = False
    #: p. 97: "A Component Pouch is watertight and filled with compartments that hold all the
    #: free Material components of your spells." Its own flag rather than a kind of focus:
    #: p. 105 names them as alternatives to each other, and the classes that grant a Focus are
    #: not the ones that grant a Pouch.
    is_component_pouch: bool = False

    def __post_init__(self) -> None:
        if not self.id:
            raise ValueError("an item is identified, or a declaration cannot name it")
        if self.weight < 0:
            raise ValueError(f"an item's weight is not negative, and {self.weight} is")
        if self.hands_when_held < 0:
            raise ValueError(
                f"an item occupies zero or more hands, not {self.hands_when_held}. A negative "
                "count would free a hand by being picked up"
            )


@dataclass(frozen=True)
class Carried:
    """One item, and where — and how — the creature has it."""

    item: Item
    carriage: Carriage = Carriage.STOWED
    #: How many hands this creature has committed to it, when that differs from the item's
    #: own requirement (p. 90). `None` means the item decides.
    #:
    #: **The grip belongs here rather than on the weapon**, and that is #263's correction.
    #: `Weapon.wielded_two_handed` was a field on the *weapon* describing how the *creature*
    #: was holding it, so two creatures could not hold the same Versatile weapon differently
    #: and one could not change its grip. It is the same mistake `Weapon.proficient` was —
    #: a fact about the wielder stored on the wielded thing — one field further down, and it
    #: survived 0040 clause 2 because that record was looking at proficiency.
    #:
    #: p. 90: "A Versatile weapon can be used with one or two hands", which is a choice the
    #: creature makes each time it picks the thing up.
    hands: int | None = None

    def __post_init__(self) -> None:
        if self.hands is None:
            return
        if self.carriage is not Carriage.HELD:
            raise ValueError(
                f"an item that is {self.carriage.value} commits no hands, so stating a grip "
                "for it describes nothing. p. 90's choice of one hand or two is about a "
                "weapon being *used*"
            )
        if self.hands < 0:
            raise ValueError(f"a grip commits zero or more hands, not {self.hands}")

    @property
    def hands_used(self) -> int:
        """What this costs in hands right now — nothing unless it is being held (p. 105)."""
        if self.carriage is not Carriage.HELD:
            return 0
        return self.item.hands_when_held if self.hands is None else self.hands


def free_hands(equipment: tuple[Carried, ...], hands: int | None) -> int | None:
    """How many hands this creature has free, or `None` if nobody said how many it has.

    `None` is the honest answer rather than a nuisance: **no SRD rule states how many hands a
    creature has**, so a creature whose ruleset did not say has an unanswerable count, and
    every rule that turns on one declines instead of assuming two (R31, R32).

    Never negative. A creature holding more than it has hands for is a ruleset's error, and
    reporting -1 free hands would invite arithmetic on a number that means nothing.
    """
    if hands is None:
        return None
    return max(0, hands - sum(carried.hands_used for carried in equipment))


def carried_weight(equipment: tuple[Carried, ...]) -> float:
    """Everything the creature has, in pounds (p. 178).

    All three carriages, because p. 178 asks for "the maximum weight in pounds that you can
    carry" and worn armour is carried as surely as a stowed rope is. Whether the total is too
    much is not answered here: that needs the Size p. 178's table is keyed on, which this
    engine does not have (#259).
    """
    return sum(carried.item.weight for carried in equipment)


def items_in(equipment: tuple[Carried, ...], carriage: Carriage) -> tuple[Item, ...]:
    """Everything in that carriage, in the order the ruleset gave it."""
    return tuple(carried.item for carried in equipment if carried.carriage is carriage)


#: p. 89: Heavy names a *score* of 13, not a modifier. Comparing modifiers would put the
#: boundary in a different place.
HEAVY_SCORE_THRESHOLD = 13


@dataclass(frozen=True, kw_only=True)
class Weapon(Item):
    """What an attack needs. A ruleset supplies it; this module ships no weapon list.

    **A subtype of `Item` since 0040 clause 1**, because a weapon *is* equipment: it has
    weight and it occupies hands, and a creature holds it. Composition — a `Weapon` wrapping
    an `Item` — would have put the weapon outside `Carried`, so state would hold the item and
    not the weapon and `legal_actions` would need it passed in. That is the repair 0026, 0038
    and 0039 each refused.

    Declared `kw_only` so the fields below need no defaults: `Item.id` has none and dataclass
    inheritance would otherwise refuse a non-defaulted field after a defaulted one.

    `id` is the identity `Item` gives it, and there is no `name` — 0039 clause 2 keeps names
    with the ruleset, and the id is what a declaration names and the ledger records.

    **`proficient` is gone, and that is a rules fix rather than a move** (0040 clause 2).
    p. 89: "Anyone can wield a weapon, but **you** must have proficiency with it to add your
    Proficiency Bonus." It is a fact about the wielder, and it lived here only because a
    weapon used to belong to one resolver and therefore to one creature. See
    `Combatant.weapon_proficiencies`.
    """

    damage_dice: int
    damage_sides: int
    ability: str = "str"
    #: Melee or Ranged (p. 89). Heavy reads a different ability score for each.
    melee: bool = True
    damage_type: DamageType | None = None
    #: Finesse (p. 89): "use your choice of your Strength or Dexterity modifier for the
    #: attack **and** damage rolls. You must use the same modifier for both rolls." The
    #: choice is the wielder's and arrives as `ability`; what the engine holds is the
    #: constraint — a Finesse weapon may use either, anything else may not, and whichever
    #: is chosen reaches both rolls.
    finesse: bool = False
    #: Heavy (p. 89): Disadvantage unless the relevant score is at least 13.
    heavy: bool = False
    #: Light (p. 89): attacking with one as the Attack action buys an extra attack as a Bonus
    #: Action, with a **different** Light weapon. A property of the weapon and not of the
    #: wielder — unlike `proficient` and the grip, both of which were fields here and were
    #: facts about the creature (0040 clause 2, #263).
    light: bool = False
    #: Versatile (p. 90): the damage die when "used with two hands to make a melee attack".
    versatile_sides: int | None = None
    #: Graze (p. 90), a mastery property: damage on a miss equal to the ability modifier.
    graze: bool = False
    #: Thrown (p. 90): "you can throw the weapon to make a ranged attack, and you can draw
    #: that weapon as part of the attack." A property of the weapon, and orthogonal to
    #: `melee` — a Dagger is a Melee weapon that may be thrown, which is why p. 90 spends its
    #: second sentence on which ability such a throw uses.
    thrown: bool = False
    #: Range (p. 90): "The first is the weapon's normal range in feet, and the second is
    #: the weapon's long range."
    #:
    #: **Not Ranged weapons only**, which this said until #284. p. 90's *Range* entry reads
    #: "A Range weapon has a range in parentheses after the **Ammunition or Thrown**
    #: property", so a Melee weapon with Thrown carries one too — and it is the range of the
    #: *throw*, never of a melee swing with the same weapon. Whether these numbers or the
    #: wielder's reach applies is therefore a question about **how the weapon is being used**,
    #: which is why the range checks take the attack mode rather than reading `melee` here.
    normal_range: int | None = None
    long_range: int | None = None
    #: A flat bonus that reaches **both** rolls. Berserker Axe (Magic Items, p. 213) is
    #: the inventory's exemplar: "a +1 bonus to attack rolls and damage rolls made with
    #: this magic weapon". Applying it to only one of the two is the mistake worth
    #: guarding, because an attack-only bonus is invisible in every hit that lands.
    bonus: int = 0

    def __post_init__(self) -> None:
        if self.finesse and self.ability not in ("str", "dex"):
            raise ValueError(
                f"a Finesse weapon uses Strength or Dexterity, not {self.ability!r} — "
                "p. 89 offers the choice between those two and no others"
            )
        if self.versatile_sides is not None and not self.melee:
            raise ValueError(
                "Versatile is a melee property: it applies to two-handed melee attacks"
            )
        if (self.normal_range is None) != (self.long_range is None):
            raise ValueError("Range lists two numbers (p. 90): a normal range and a long range")
        if self.normal_range is not None and self.long_range is not None:
            if self.long_range < self.normal_range:
                raise ValueError("a weapon's long range is not shorter than its normal range")
            # p. 90's *Range* entry: "A Range weapon has a range in parentheses after the
            # **Ammunition or Thrown** property." So a Melee weapon carries one exactly when
            # it is Thrown — a Dagger's 20/60 is the range of the throw, never of the stab.
            # This refused every melee weapon until #284, which was right only while nothing
            # had the Thrown property to give one to.
            if self.melee and not self.thrown:
                raise ValueError(
                    "Range belongs to a Ranged weapon or a Thrown one (p. 90); a Melee "
                    "weapon that is neither uses its wielder's reach"
                )
        if self.thrown and self.normal_range is None:
            raise ValueError(
                "a Thrown weapon states the range of the throw (p. 90): its range sits in "
                "parentheses after the property, and without it nothing bounds the throw"
            )

    def sides_in_use(self, hands: int) -> int:
        """The damage die this attack rolls, for a weapon held in that many hands.

        p. 90: a Versatile weapon "deals that damage **when used with two hands** to make a
        melee attack". Both halves are conditions — a versatile weapon wielded in one hand
        rolls its ordinary die.

        **The grip arrives as an argument since #263**, because it is the creature's and not
        the weapon's: `wielded_two_handed` was a field here, so two creatures could not hold
        the same Versatile weapon differently. `Carried.hands` records it now.
        """
        if self.versatile_sides is not None and hands >= 2 and self.melee:
            return self.versatile_sides
        return self.damage_sides

    def heavy_disadvantage(self, scores: Mapping[str, int]) -> bool:
        """p. 89: Disadvantage "if it's a Melee weapon and your Strength score isn't at
        least 13 or if it's a Ranged weapon and your Dexterity score isn't at least 13".

        The *score*, not the modifier — 13 is the threshold the document names, and a
        modifier comparison would put the boundary in a different place.
        """
        if not self.heavy:
            return False
        required = "str" if self.melee else "dex"
        return scores.get(required, 10) < HEAVY_SCORE_THRESHOLD


@dataclass(frozen=True)
class DetachedObject:
    """An object no creature has (0041 clauses 1, 3 and 4).

    **Not a new kind of thing.** p. 191: "A weapon is an object that is in the Simple or
    Martial weapon category", and p. 12 lists a *sword* among its examples of an object. The
    `Item` that was held is the `Item` that is on the floor, so this wraps one rather than
    subtyping it — what changed is a **relation**, not a type (0041 clause 1). A creature no
    longer has it, so it is not in `Combatant.equipment` and carries no `Carriage`: every
    member of that enum is a way of *being carried*, and p. 190 then teleports the lot.

    ## Its position is unknown until something says otherwise

    **Five printed rules detach an item from a creature and none states where it goes** —
    p. 177's Attack action ("sheathing, stowing, or dropping it"), p. 191's Unconscious ("you
    drop whatever you're holding"), p. 90's Thrown, and the *Command* and *Fear* spells on
    pp. 116 and 130. There is no rule value to read, so `None` is the honest default and
    means *nobody has said*, exactly as it does on `Combatant.position` and `Combatant.hands`.

    **The default that is not written here is the dropping creature's own space.** It is the
    most plausible sentence in this area and it is not in the document: p. 217's Dancing Sword
    spends a clause saying "falls to the ground **in your space**", which a general rule would
    make unnecessary. It is also wrong for the other half of the vocabulary — p. 90 gives a
    thrown weapon a range in feet, so the thrower's position is the one place the javelin
    certainly is not. Dropping and throwing share this type and do not share a destination
    (0041 clause 5), which is why the field refuses a default rather than taking the one that
    serves the commoner rule.

    Nothing else rides here. Which rule detached it, and from whom, are facts no engine rule
    reads today — and a field the engine has no rule about is a field nothing reads, the decay
    #228, #215 and #252 each found.
    """

    item: Item
    #: Where it is, in feet, or `None` because **no rule said**. See the class docstring: this
    #: is a refusal rather than an omission, and `reachable_objects` reports it as one.
    position: Position | None = None


def reachable_objects(
    objects: tuple[DetachedObject, ...],
    actor_position: Position | None,
    reach: int,
) -> tuple[DetachedObject, ...] | None:
    """Which detached objects are within `reach`, or `None` if that cannot be answered.

    Three outcomes rather than two, and the middle one is the point (0041 clause 4):

    - `None` — the **actor** has no position, so no distance is computable. An encounter that
      tracks no positions gets a refusal, not an empty tuple.
    - An empty tuple — distances were computed and nothing is in reach.
    - Objects — those whose own position is stated and within `reach`.

    An object whose position is `None` is in none of these, because it cannot be placed. It is
    **not silently dropped**: `unplaced_objects` names it, and the read surface reports both.
    Returning it as reachable would invent the coordinate this whole type exists to refuse;
    omitting it without a word would show an empty menu whose emptiness a reader has to
    interpret, which is the narrowing #267 caught in 0040 clause 3.
    """
    if actor_position is None:
        return None
    return tuple(
        obj
        for obj in objects
        if obj.position is not None and within(actor_position, obj.position, reach)
    )


def unplaced_objects(objects: tuple[DetachedObject, ...]) -> tuple[DetachedObject, ...]:
    """The detached objects no rule has placed (R32).

    Disclosed rather than left to be inferred from an absence. These are exactly the objects
    a ruleset could make reachable by stating where they are, so a reader seeing them knows
    the gap is *unstated position* rather than *out of reach* — two different answers that an
    empty reachable list would render identical.
    """
    return tuple(obj for obj in objects if obj.position is None)


@dataclass(frozen=True)
class Multiattack:
    """How many attack rolls the Attack action buys this creature (p. 257, 0043 clauses 1-2).

    > Some creatures can make more than one attack **when they take the Attack action**. Such
    > creatures have the Multiattack entry in the "Actions" section of their stat block. This
    > entry details the attacks a creature can make, as well as any additional abilities it
    > can use, **as part of the Attack action**.

    **Not a second action.** The Action is spent once and buys `attacks` rolls, which is why
    `attack_resolver` charges the economy only on the first of them.

    **What the entry says is the ruleset's** (0043 clause 2). The engine holds how many rolls
    remain and whether a weapon is among the permitted ones; the aboleth's "two Tentacle
    attacks", the bandit's "two attacks, using Scimitar and Pistol in any combination" and the
    balor's "one Flame Whip attack and one Lightning Blade attack" are content, and a grammar
    for them here would be a weapon table by another name (R31).

    **It rides on the creature rather than in the bestiary**, because pp. 136, 166 and 232
    give a Multiattack to a **spell's** summoned creature — so it is not a monster-only fact.

    ## What this shape cannot say

    `permitted` is a **pool**: `attacks` rolls drawn from that set in any combination, which is
    the bandit's and the assassin's shape. A *fixed* composition — the balor's one-each — needs
    a per-weapon limit this does not carry, and none of the six shipped stat blocks has one.
    Disclosed rather than guessed at (R32).
    """

    #: How many attack rolls the Attack action buys. At least one; a Multiattack that buys
    #: none is an entry that does nothing, and the creature's ordinary attack covers it.
    attacks: int
    #: Which weapons may fill those rolls, by id. **Empty means any weapon the creature
    #: holds** — the reading that refuses nothing, for a ruleset that stated a count and not a
    #: list. It is not "no weapon may", which would make the entry unusable.
    permitted: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if self.attacks < 1:
            raise ValueError(
                f"a Multiattack buys at least one attack roll, not {self.attacks}. p. 257 "
                "describes making *more than one* attack, and an entry buying none is an "
                "entry with nothing to detail"
            )

    def allows(self, weapon_id: str) -> bool:
        """Whether this weapon may fill one of the rolls (p. 257)."""
        return not self.permitted or weapon_id in self.permitted
