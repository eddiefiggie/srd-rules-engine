"""A creature's size category, and the one table this engine keys on it (p. 178, p. 188).

p. 188, *Size*: "A creature or an object belongs to a size category: Tiny, Small, Medium,
Large, Huge, or Gargantuan." Six categories, ordered smallest to largest by p. 14's own
Creature Size and Space table, which lists them "from smallest (Tiny) to largest
(Gargantuan)".

**The order is the primitive, not a convenience.** Five separate rules ask how many categories
apart two creatures are, and each asks it differently:

- p. 14, *Moving around Other Creatures* — you may pass through the space of "a creature that
  is **two sizes** larger or smaller than you".
- p. 15, *Mounted Combat* — a mount must be "at least **one size larger** than a rider".
- p. 86, *Naturally Stealthy* — obscured by "a creature that is at least **one size larger**
  than you".
- p. 190, *Unarmed Strike* — Grapple and Shove are possible "only if the target is **no more
  than one size larger** than you".
- p. 86, *Powerful Build* and p. 357, *Beast of Burden* — you "count as **one size larger**
  when determining your carrying capacity".

`categories_above` answers all five. Only the last is consumed here; the rest are named so the
next one to be built finds the comparison already stated rather than re-deriving an ordering.

## The document's own grouping is not an arithmetic step

p. 178's Carrying Capacity table prints **Small/Medium as one row**. Small and Medium remain
distinct categories everywhere else — p. 14 gives them the same 5-by-5 space but lists them
separately, and p. 86's Human chooses between them — so the ordering keeps them apart and the
table maps two categories onto one multiplier.

That is why the multipliers below are a **table** and not `carry * 2 ** steps`. The shortcut is
right for four of the five steps and wrong for the one that matters: counting as one size
larger takes a Small creature to Medium, which carries **exactly the same weight**. p. 86's
Powerful Build therefore does nothing at all for a Small character's capacity, and an
implementation that multiplied by two would quietly grant it double.

Both columns are transcribed for the same reason. Drag/Lift/Push happens to be twice Carry in
all six rows, but the document states a table rather than that relation, and deriving one
column from the other would survive a revision that changed it.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from types import MappingProxyType
from typing import Final


class Size(StrEnum):
    """One of p. 188's six categories.

    A creature's size is **not defaulted** — see `Combatant.size`. Every value here comes from
    a ruleset that stated one, because p. 14 says where a size comes from and it is content
    this repository does not ship: "A character's size is determined by species, and a
    monster's size is specified in the monster's stat block."
    """

    TINY = "tiny"
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    HUGE = "huge"
    GARGANTUAN = "gargantuan"

    @property
    def rank(self) -> int:
        """Position in p. 14's smallest-to-largest ordering, Tiny at 0.

        An ordinal and not a quantity: the gap between Tiny and Small is one category, and
        the sizes it separates occupy 2½ and 5 feet. Nothing may do arithmetic on this but
        `categories_above`.
        """
        return _ORDER.index(self)

    def categories_above(self, other: Size) -> int:
        """How many categories larger this size is than `other`, negative if smaller.

        The comparison every "one size larger" rule needs, signed so "no more than one size
        larger than you" (p. 190) and "at least one size larger" (p. 15) are both a
        comparison against the same number rather than two different questions.
        """
        return self.rank - other.rank


#: p. 14 lists the categories "from smallest (Tiny) to largest (Gargantuan)". Declared rather
#: than taken from the enum's definition order, so `rank` rests on a sentence of the document
#: instead of on where somebody happened to type a member.
_ORDER: Final[tuple[Size, ...]] = (
    Size.TINY,
    Size.SMALL,
    Size.MEDIUM,
    Size.LARGE,
    Size.HUGE,
    Size.GARGANTUAN,
)

#: p. 178's Carry column, as the multiplier applied to the **Strength score**. p. 178 says
#: "Your size and Strength **score** determine the maximum weight in pounds that you can
#: carry" — the score, not the modifier, which is the arithmetic an implementation working
#: from memory of the game gets wrong.
CARRY_MULTIPLIER: Final[dict[Size, float]] = {
    Size.TINY: 7.5,
    Size.SMALL: 15.0,
    Size.MEDIUM: 15.0,
    Size.LARGE: 30.0,
    Size.HUGE: 60.0,
    Size.GARGANTUAN: 120.0,
}

#: p. 178's Drag/Lift/Push column, transcribed rather than derived (see the module docstring).
DRAG_LIFT_PUSH_MULTIPLIER: Final[dict[Size, float]] = {
    Size.TINY: 15.0,
    Size.SMALL: 30.0,
    Size.MEDIUM: 30.0,
    Size.LARGE: 60.0,
    Size.HUGE: 120.0,
    Size.GARGANTUAN: 240.0,
}


@dataclass(frozen=True)
class CarryingCapacity:
    """Both of p. 178's columns for one creature, in pounds.

    Two numbers rather than one, because the document states two and they bound different
    things: Carry is "the maximum weight in pounds that you can carry", and Drag/Lift/Push is
    a separate, larger maximum for weight you are not carrying so much as shifting.

    **Neither is enforced anywhere.** p. 178's consequence — "your Speed can be no more than 5
    feet" — turns on whether the creature is *dragging, lifting, or pushing*, which is a
    narrative fact this engine does not hold, and p. 12 makes the whole subsystem a person's
    call: "the GM **might** require you to abide by the rules for carrying capacity". So these
    are reported, and the read surface discloses the unapplied cap.
    """

    carry: float
    drag_lift_push: float
    #: The size the table was read at, which is not always the creature's (p. 86, p. 357).
    size: Size
    strength_score: int

    def derivation(self) -> str:
        """The engine's own sentence for how these numbers were reached (R30).

        A bound without its derivation is half a ruling, and this one has a step a reader
        cannot see from the result: a creature counting as one size larger was looked up at
        a size it does not have.
        """
        return (
            f"{self.size.value}, Strength {self.strength_score}: carry "
            f"{self.strength_score} * {CARRY_MULTIPLIER[self.size]:g} = {self.carry:g} lb; "
            f"drag, lift or push {self.strength_score} * "
            f"{DRAG_LIFT_PUSH_MULTIPLIER[self.size]:g} = {self.drag_lift_push:g} lb (p. 178)"
        )


def one_size_larger_for_carrying(size: Size) -> Size:
    """p. 86's Powerful Build and p. 357's Beast of Burden, as a table lookup.

    Both say a creature "counts as one size larger" **for carrying capacity only**, so this
    is deliberately not a general `one_larger` on the enum: it is an effective size for one
    table, and offering it as a size primitive would invite a caller to use it for p. 190's
    Grapple, where no rule grants it.

    **Gargantuan stays Gargantuan.** p. 188 names six categories and there is nothing above
    the last one, so the only reading that does not invent a seventh is that the trait finds
    no larger row to move to. That is 0030's direction — the reading that cannot manufacture
    an outcome — and it costs nothing real, because the trait belongs to a Goliath and a mule.

    Small is the case worth knowing: it moves to Medium, whose multipliers are identical.
    """
    if size is Size.GARGANTUAN:
        return size
    return _ORDER[size.rank + 1]


def carrying_capacity(size: Size, strength_score: int) -> CarryingCapacity:
    """p. 178's table, for a creature of this size and Strength score.

    `size` is the size to read the table **at**, which a caller holding a Powerful Build
    creature has already passed through `one_size_larger_for_carrying`.
    """
    return CarryingCapacity(
        carry=strength_score * CARRY_MULTIPLIER[size],
        drag_lift_push=strength_score * DRAG_LIFT_PUSH_MULTIPLIER[size],
        size=size,
        strength_score=strength_score,
    )


#: p. 181's *Water Needs per Day*, in gallons.
#:
#: **`Fraction`, not `float`.** Tiny needs a quarter of a gallon and the rule turns on *half*
#: of what is required, so the comparison is against an eighth — and a binary float cannot
#: hold either exactly. A hazard that fired on a rounding error would be indistinguishable
#: from one that fired on the rule.
#:
#: **A size-keyed table this engine does ship**, unlike pp. 92-97's equipment. p. 178's
#: carrying capacity is the precedent: a table printed inside a Rules Glossary mechanic is
#: part of the mechanic, while a table of purchasable goods is content (R31).
WATER_PER_DAY: Final[Mapping[Size, Fraction]] = MappingProxyType(
    {
        Size.TINY: Fraction(1, 4),
        Size.SMALL: Fraction(1),
        Size.MEDIUM: Fraction(1),
        Size.LARGE: Fraction(4),
        Size.HUGE: Fraction(16),
        Size.GARGANTUAN: Fraction(64),
    }
)


#: p. 185's *Food Needs per Day*, in pounds. The same six rows as water and the same
#: quarter — see `WATER_PER_DAY` for why these are exact rather than floating (#399).
FOOD_PER_DAY: Final[Mapping[Size, Fraction]] = MappingProxyType(
    {
        Size.TINY: Fraction(1, 4),
        Size.SMALL: Fraction(1),
        Size.MEDIUM: Fraction(1),
        Size.LARGE: Fraction(4),
        Size.HUGE: Fraction(16),
        Size.GARGANTUAN: Fraction(64),
    }
)


def undernourished(size: Size, pounds_eaten: Fraction) -> bool:
    """Whether p. 185 compels this creature a saving throw at the day's end (#399).

    > A creature that **eats but consumes less than half** the required food for a day must
    > succeed on a DC 10 Constitution saving throw or gain 1 Exhaustion level.

    **"Eats but consumes less than half"**, so eating *nothing* is not this rule — it is the
    five-day starvation clause, which compels no save and gains a level outright. That clause
    needs consecutive days counted and is
    [#401](https://github.com/eddiefiggie/srd-rules-engine/issues/401); this returns `False`
    for a creature that ate nothing, which is **not** the same as saying it is unharmed.

    Strictly less than half, as with water: exactly half is enough.
    """
    if pounds_eaten <= 0:
        return False
    return bool(pounds_eaten < FOOD_PER_DAY[size] / 2)


def dehydrated(size: Size, gallons_drunk: Fraction) -> bool:
    """Whether p. 181 gives this creature an Exhaustion level at the day's end (#315).

    > A creature that drinks **less than half** the required water for a day gains 1
    > Exhaustion level at the day's end.

    **Strictly less than half**, which is the whole of the comparison. Exactly half is enough,
    and a `<=` here would inflict a level the document does not.
    """
    return bool(gallons_drunk < WATER_PER_DAY[size] / 2)


#: p. 182, *Grappled*, *Movable*: "two or more sizes smaller than it".
#:
#: The number the second escape is a comparison against, named rather than written `>= 2` at
#: the one call site — it is the rule, and a bare literal there reads as an implementation
#: choice somebody could tune.
CARRIED_FREELY_CATEGORIES_SMALLER: Final = 2


def carried_without_extra_cost(*, passenger: Size | None, grappler: Size | None) -> bool:
    """Whether p. 182's *Movable* clause carries this creature for nothing (#340).

    > **Movable.** The grappler can drag or carry you when it moves, but every foot of
    > movement costs it 1 extra foot **unless you are Tiny or two or more sizes smaller than
    > it.**

    Two escapes, and only the second needs the grappler's size. Tiny is absolute: a Tiny
    creature is carried free by a Gargantuan and by another Tiny, because the sentence says
    so without qualification.

    **An unstated size establishes no escape, and the extra applies.** That is not a size
    guessed at — it is the difference between a rule and its exception. p. 182 states the
    extra foot as what happens, and names two facts that lift it; a fact the ruleset never
    stated is not one of them, so the exception is simply not made out. Reading it the other
    way would grant an exemption on no evidence, which is the invention R31 forbids, and it
    would do so silently in the caller's favour.

    Note the asymmetry that follows: a Tiny passenger is free whatever the grappler is, so an
    unstated **grappler** size only matters for a passenger that is not Tiny.
    """
    if passenger is None:
        return False
    if passenger is Size.TINY:
        return True
    if grappler is None:
        return False
    return grappler.categories_above(passenger) >= CARRIED_FREELY_CATEGORIES_SMALLER


#: p. 178: "your Speed can be no more than 5 feet" while hauling more than you can carry.
#:
#: Named here rather than written at the one place it is applied, because it is the rule and
#: not a bound somebody chose. Five is also p. 182's grapple range and p. 186's auto-crit
#: distance, and each of those is stated by its own sentence — three coincident numbers, and
#: sharing one constant between them would tie together rules that could move apart.
HAULING_SPEED_CAP_FEET: Final = 5
