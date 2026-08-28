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

from dataclasses import dataclass
from enum import StrEnum


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
    """One item, and where the creature has it."""

    item: Item
    carriage: Carriage = Carriage.STOWED

    @property
    def hands_used(self) -> int:
        """What this costs in hands right now — nothing unless it is being held (p. 105)."""
        return self.item.hands_when_held if self.carriage is Carriage.HELD else 0


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
