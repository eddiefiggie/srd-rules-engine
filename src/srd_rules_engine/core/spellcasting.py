"""Spell slots, spell save DCs and spell attacks, and Concentration (R15).

Read off "Spells" ("Casting Spells"), pp. 104-106, and the Rules Glossary entries for
Cantrip p. 178, Concentration p. 179, Spell Attack p. 188 and Spellcasting Focus p. 188.

## Concentration is the reason this module matters

The project's own README calls it the most-forgotten rule in play, and it is forgotten in a
specific direction: a caster starts a second concentration spell and keeps the first. p. 179
is explicit that the first ends "the moment you start casting" the second — before the new
spell resolves, and whether or not it succeeds. `begin` models that by replacing rather than
refusing, so keeping both is unrepresentable rather than merely discouraged.

Three things break it, and they are three different rules:

* **Another Concentration effect** — replacement, above.
* **Damage** — a Constitution save whose "DC equals 10 or half the damage taken (round
  down), whichever number is higher, up to a maximum DC of 30". Both the floor and the cap
  are easy to omit, and omitting the floor makes small hits free.
* **Incapacitated or dead** — no save. `core.conditions` already reports
  `concentration_broken` for Incapacitated, so the two agree by construction.

## No slot table ships here

p. 26 prints slots per class level, and that is content: a table of them compiled here would
be the inferred rule value R31 forbids. `SpellSlots` is the shape a ruleset fills in.

## What is deliberately absent

* **Components, and the Spellcasting Focus that substitutes for them** (p. 188), need item
  and inventory state that does not exist.
* **Which spells a class prepares, when, and how many** is class data — p. 104 puts it in the
  spellcasting feature and summarises it per class. Not claimed, for the reason no slot table
  ships. *Whether a given spell is prepared* is state (`Combatant.prepared`, #19), because
  that is the question castability asks.
* **Enumerating what is castable right now** needs a spell list, and this engine ships none
  ([#21](https://github.com/eddiefiggie/srd-rules-engine/issues/21)). So R18's "never offered
  as legal" half waits: `spell_reaches` answers the range question for a spell a caller
  names, and nothing can walk the spells to offer them.
* `modify-a-spell` and `multiclass-spell-slots` are class data likewise, and unclaimed.

Long Rest recovery had no trigger until #19. It has one now —
`EncounterState.with_long_rest` calls `restored()` — and this paragraph said otherwise for a
build after that landed, which is the failure mode a stale disclosure has: it reads as an
explanation long after it has become a description of a bug.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.d20 import D20Test, TestKind
from srd_rules_engine.core.obstructions import Obstruction, line_is_blocked
from srd_rules_engine.core.position import Position, within
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

#: p. 178: "A cantrip is a level 0 spell, which is cast without a spell slot."
CANTRIP_LEVEL: Final = 0

#: p. 104: "Every spell has a level from 0 to 9, which is indicated in a spell's
#: description." Slots therefore run 1 to 9 rather than 0 to 9, because p. 178 puts a level 0
#: spell outside the slot economy entirely — a derivation from two asserted sentences, not a
#: bound read off a table.
#:
#: This cited p. 26's class table until #130. The value was right and the citation was the
#: weaker of the two available: p. 26 is the class data this module refuses to ship, so the
#: one number taken off that page was the one thing here resting on content rather than rule.
MAX_SPELL_LEVEL: Final = 9

#: p. 179: "The DC equals 10 or half the damage taken (round down), whichever number is
#: higher, up to a maximum DC of 30."
CONCENTRATION_DC_FLOOR: Final = 10
CONCENTRATION_DC_CAP: Final = 30

#: R31.
SPELLCASTING_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Spells ("Casting Spells" -> "Spell Slots"), p. 104, including the '
        "sentence bounding a spell's level at 0 to 9; spell save DC and spell attack "
        "modifier p. 106; Rules Glossary, Cantrip p. 178, Concentration p. 179, Spell "
        "Attack p. 188"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


class NoSlotAvailable(Exception):
    """A spell was cast with no slot able to pay for it. Refused, never improvised."""


@dataclass(frozen=True)
class SpellSlots:
    """Slots by level, and how many of each are spent.

    No table of slot counts ships here — p. 26's is class data, and compiling one would be
    the inferred rule value R31 forbids. A ruleset supplies `total`.
    """

    total: Mapping[int, int]
    spent: Mapping[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for level in {*self.total, *self.spent}:
            if not 1 <= level <= MAX_SPELL_LEVEL:
                raise ValueError(
                    f"spell slots run from level 1 to {MAX_SPELL_LEVEL}; level {level} is "
                    "not one. A cantrip is level 0 and uses no slot at all (p. 178)"
                )
        object.__setattr__(self, "total", MappingProxyType(dict(self.total)))
        object.__setattr__(self, "spent", MappingProxyType(dict(self.spent)))

    def remaining(self, level: int) -> int:
        return max(0, self.total.get(level, 0) - self.spent.get(level, 0))

    def payable_by(self, spell_level: int) -> tuple[int, ...]:
        """Which slot levels could cast a spell of this level, lowest first.

        p. 104: "you expend a slot of that spell's level **or higher**" — so a level 1 spell
        fits any slot and a level 2 spell fits nothing smaller. Returning every option
        rather than choosing one keeps the choice with the caster, who may want to upcast.
        """
        if spell_level == CANTRIP_LEVEL:
            return ()
        return tuple(
            level for level in range(spell_level, MAX_SPELL_LEVEL + 1) if self.remaining(level) > 0
        )

    def can_cast(self, spell_level: int) -> bool:
        """Whether this spell is castable right now (R18 wants this computable)."""
        return spell_level == CANTRIP_LEVEL or bool(self.payable_by(spell_level))

    def expend(self, slot_level: int) -> SpellSlots:
        """Spend one slot of exactly this level, or refuse."""
        if self.remaining(slot_level) <= 0:
            raise NoSlotAvailable(f"no level {slot_level} spell slot remains")
        spent = dict(self.spent)
        spent[slot_level] = spent.get(slot_level, 0) + 1
        return SpellSlots(total=self.total, spent=spent)

    def cast(self, spell_level: int, *, at_level: int | None = None) -> SpellSlots:
        """Cast a spell, expending the slot that pays for it.

        A cantrip expends nothing (p. 178). `at_level` upcasts deliberately; left out, the
        lowest slot that can pay is used, which is the choice a caster almost always makes
        and never the engine inventing one that was unavailable.
        """
        if spell_level == CANTRIP_LEVEL:
            return self

        options = self.payable_by(spell_level)
        if not options:
            raise NoSlotAvailable(
                f"a level {spell_level} spell needs a slot of level {spell_level} or "
                "higher, and none remains (p. 104)"
            )
        chosen = options[0] if at_level is None else at_level
        if chosen < spell_level:
            raise NoSlotAvailable(
                f"a level {spell_level} spell does not fit a level {chosen} slot: it "
                "expends a slot of its own level or higher (p. 104)"
            )
        return self.expend(chosen)

    def restored(self) -> SpellSlots:
        """p. 104: "Finishing a Long Rest restores any expended spell slots."

        Called by `EncounterState.with_long_rest` since #19. It went a build without one
        after the rest landed in #185 — the operation existed, the occasion existed, and
        nothing joined them, which is the shape a disclosed gap takes when its reason expires
        and the disclosure does not.
        """
        return SpellSlots(total=self.total)


def spell_save_dc(ability_modifier: int, proficiency_bonus: int) -> int:
    """p. 106: "Spell save DC = 8 + your spellcasting ability modifier + your Proficiency
    Bonus"."""
    return 8 + ability_modifier + proficiency_bonus


def spell_attack_modifier(ability_modifier: int, proficiency_bonus: int) -> int:
    """p. 106: "Spell attack modifier = your spellcasting ability modifier + your
    Proficiency Bonus" — the same two terms as the save DC, without the 8."""
    return ability_modifier + proficiency_bonus


@dataclass(frozen=True)
class Concentration:
    """What a creature is concentrating on, if anything (p. 179).

    **A rule id, not a spell name** (0038 clause 7). The field was `spell` until #241, which
    is the half of p. 179's clause the tree had quoted: the rule is "the moment you start
    casting a spell that requires Concentration **or activate another effect that requires
    Concentration**". A magic item's effect has no spell name to put in a field called
    `spell`, and a rule id is what this engine uses everywhere else to say which mechanic
    something is.
    """

    rule_id: str | None = None

    @property
    def active(self) -> bool:
        return self.rule_id is not None

    def begin(self, rule_id: str) -> Concentration:
        """Start concentrating, ending whatever came before.

        p. 179: "You lose Concentration on an effect the moment you **start casting** a
        spell that requires Concentration or activate another effect that requires
        Concentration." Replacement rather than refusal, and at the moment casting starts
        rather than when it resolves — so a caster cannot hold two by having the second one
        fail.
        """
        if not rule_id:
            raise ValueError("a concentration effect is named, or it cannot be ended later")
        return Concentration(rule_id=rule_id)

    def ended(self) -> Concentration:
        """p. 179: "The creator can end Concentration at any time (no action required)."

        Every route that ends Concentration comes through here — the voluntary end this
        sentence licenses, the failed damage save (0036), and the Incapacitated-or-Dead
        clause `Combatant.__post_init__` materialises (0037 clause 4).

        **There was an `after_conditions` beside this until #238**, deriving the
        Incapacitated end from the conditions held whenever somebody asked. It is gone
        rather than repaired: p. 179 says Concentration *ends*, and a function of the
        present conditions cannot record that a condition arrived and departed. The spell
        came back when the condition lifted, and `with_damage` — asking the same derivation
        so that state and the read surface would agree — then compelled a save to maintain
        it.
        """
        return Concentration()


class CastingTime(StrEnum):
    """How long a spell takes to cast (p. 105).

    "Most spells require the Magic action to cast, but some spells require a Bonus Action, a
    Reaction, or 1 minute or more."

    Four values are printed and three are modelled. The fourth is
    [#250](https://github.com/eddiefiggie/srd-rules-engine/issues/250) and is **absent rather
    than approximated**: a 10-minute cast treated as an action is an engine casting instantly
    something the document takes ten minutes over, which is wrong in the direction nobody
    notices. A `Spell` that needs one cannot be built rather than being built wrongly.
    """

    ACTION = "action"
    BONUS_ACTION = "bonus-action"
    REACTION = "reaction"


@dataclass(frozen=True)
class Spell:
    """A spell, as much of one as this engine holds (0038 clauses 1 and 2).

    **The fields the engine has rules about, and no others.** It picks the slot from the
    level, spends the action the casting time names, asks `spell_reaches` about the range,
    and starts Concentration when the spell requires it. Everything else about a spell —
    above all what it *does* — is the resolver the ruleset supplies.

    **No school.** p. 105: "Each spell belongs to a school of magic […] These categories help
    describe spells but **have no rules of their own**." A field for it would be a field
    nothing reads, and this repository has found that decay twice (#228, #215). It is not a
    gap and should not be filed as one.

    **No components, yet.** p. 105 states the rule — "If the spellcaster can't provide one or
    more of a spell's components, the spellcaster can't cast the spell" — and this engine can
    check none of the three: Verbal needs gagged-or-magically-silenced, and Somatic and
    Material need an equipment model that does not exist. Holding V/S/M while enforcing
    nothing would be the same decay in a slower form, so the field arrives with the subsystem
    that can read it (#245, #246). The gap is disclosed in this module's docstring (R32).

    **No name.** `rule_id` is the identity, because that is what a `Declaration` names and
    what the ledger records. A display name is the ruleset's to hold.
    """

    rule_id: str
    level: int
    casting_time: CastingTime = CastingTime.ACTION
    requires_concentration: bool = False
    #: Where the spell may originate (p. 105). `None` when the ruleset states none, which is
    #: the honest value for a spell whose range this engine was not told.
    spell_range: SpellRange | None = None

    def __post_init__(self) -> None:
        if not self.rule_id:
            raise ValueError("a spell is identified by the rule that resolves it")
        if not CANTRIP_LEVEL <= self.level <= MAX_SPELL_LEVEL:
            raise ValueError(
                f"p. 104: every spell has a level from {CANTRIP_LEVEL} to {MAX_SPELL_LEVEL}, "
                f"not {self.level}"
            )

    @property
    def is_cantrip(self) -> bool:
        """p. 178: "A cantrip is a level 0 spell, which is cast without a spell slot.\""""
        return self.level == CANTRIP_LEVEL


def concentration_save_dc(damage: int) -> int:
    """p. 179: "10 or half the damage taken (round down), whichever number is higher, up to
    a maximum DC of 30."

    Both bounds matter and both are easy to drop. Without the floor a 2-damage hit would set
    DC 1 and never threaten anything; without the cap a 90-damage hit would set DC 45, which
    almost nothing could make.
    """
    if damage < 0:
        raise ValueError("damage is not negative")
    return min(CONCENTRATION_DC_CAP, max(CONCENTRATION_DC_FLOOR, damage // 2))


def concentration_save(damage: int) -> D20Test:
    """The Constitution saving throw damage forces, as a test the engine can roll.

    The modifiers are the caster's and arrive from the caller; what this fixes is the kind
    and the target, which are the rule.
    """
    dc = concentration_save_dc(damage)
    return D20Test(
        kind=TestKind.SAVE,
        target=dc,
        target_basis=(
            f"Constitution save to maintain Concentration, DC {dc} — 10 or half of "
            f"{damage} damage taken, whichever is higher, capped at 30 (p. 179)"
        ),
    )


#: p. 187: "The Ritual version of a spell takes 10 minutes longer to cast than normal."
#: Minutes, which is `core.clock`'s unit (0020) — a ritual is campaign-scale by construction.
RITUAL_EXTRA_MINUTES: Final = 10

#: R31. p. 187's entry, asserted whole in `scripts/verify_d20_rules.py` — including the
#: consequence it draws for itself, which is the half that gets dropped.
RITUAL_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary, Ritual p. 187 — the prepared-and-tagged precondition, "
        "the 10 extra minutes, the slot it does not expend, and the upcasting that "
        "therefore cannot happen"
    ),
    date="2026-08-25",
    method=VerificationMethod.ASSERTED,
)


@dataclass(frozen=True)
class RitualCast:
    """What casting a spell as a Ritual costs (p. 187).

    Two facts and no dice: it takes longer and it spends nothing. The engine states them; a
    caller advances the clock, because how long a thing took is campaign time and
    `with_time_passed` is where that lands.
    """

    spell_id: str
    extra_minutes: int = RITUAL_EXTRA_MINUTES
    expends_slot: bool = False


def ritual_cast(
    *,
    spell_id: str,
    prepared: frozenset[str],
    has_ritual_tag: bool,
    at_level: int | None = None,
) -> RitualCast:
    """Cast a prepared, Ritual-tagged spell as a Ritual (p. 187).

    Three refusals, and the third is the one an implementation drops.

    **Prepared.** "If you have a spell prepared that has the Ritual tag" — a spell merely
    known is not enough, and the sentence puts the precondition before the permission.

    **Tagged.** The tag is the spell's, so it arrives from the ruleset: this engine ships no
    spell list (#21) and cannot look it up.

    **Not upcast.** "It also doesn't expend a spell slot, **which means the ritual version of
    a spell can't be cast at a higher level.**" The document draws that consequence itself
    rather than leaving it to be inferred, and an engine that accepted `at_level` here would
    let a caster upcast for free — the one thing this clause exists to prevent.
    """
    if spell_id not in prepared:
        raise ValueError(
            f"{spell_id!r} is not prepared, and p. 187 casts a Ritual only from a spell you "
            "have prepared. A spell that is merely known is not one you may ritual"
        )
    if not has_ritual_tag:
        raise ValueError(
            f"{spell_id!r} carries no Ritual tag. The tag is the spell's own and comes from "
            "the ruleset; this engine ships no spell list to look it up in (#21)"
        )
    if at_level is not None:
        raise ValueError(
            f"a Ritual expends no spell slot, so {spell_id!r} cannot be cast at level "
            f"{at_level} — p. 187 draws that consequence itself. Upcasting is paid for with "
            "a higher slot, and there is no slot here to be higher"
        )
    return RitualCast(spell_id=spell_id)


class RangeForm(StrEnum):
    """The three forms p. 105 gives a spell's range. Only one of them is a number."""

    DISTANCE = "distance"
    TOUCH = "touch"
    SELF = "self"


@dataclass(frozen=True)
class SpellRange:
    """How far from the caster a spell's effect may originate (p. 105).

    "A spell's range indicates how far from the spellcaster the spell's effect can originate,
    and the spell's description specifies which part of the effect is limited by the range."

    **The range bounds the origin, not the effect.** p. 105 is explicit that the description
    says which part is limited, and that "if a spell has movable effects, they aren't
    restricted by its range" — so a spell whose area later moves is not re-checked. Nothing
    here re-checks one, and that is the clause an implementation adds by accident rather than
    one it drops.
    """

    form: RangeForm
    feet: int | None = None

    def __post_init__(self) -> None:
        if self.form is RangeForm.DISTANCE:
            if self.feet is None or self.feet < 0:
                raise ValueError(
                    "a Distance range is expressed in feet (p. 105), and a negative or "
                    "absent one is not a distance"
                )
        elif self.feet is not None:
            raise ValueError(
                f"a {self.form.value} range carries no distance — p. 105 gives Touch as the "
                "caster's reach and Self as the caster, neither of which is a number this "
                "engine may invent"
            )


def spell_reaches(
    origin: Position,
    *,
    caster: Position,
    spell_range: SpellRange,
    reach_feet: int,
    obstructions: Sequence[Obstruction] = (),
) -> bool:
    """Whether a spell of this range may originate there, from a caster standing here.

    Two independent tests, both from the document, and a spell must pass both:

    **The range** (p. 105). `Self` is the caster's own space; `Touch` is the caster's reach,
    which p. 186 puts at 5 feet unless a rule says otherwise; `Distance` is the number.

    **A clear path** (p. 106): "To target something with a spell, a caster must have a clear
    path to it, so it can't be behind Total Cover." That is the same refusal `core.combat`
    makes for a weapon attack, from a different page — and the reason obstructions are a
    parameter here rather than a caller's choice is that this function takes them from
    `EncounterState` at its one call site, per 0026.
    """
    if obstructions and line_is_blocked(caster, origin, obstructions):
        return False
    if spell_range.form is RangeForm.SELF:
        return origin == caster
    if spell_range.form is RangeForm.TOUCH:
        return within(caster, origin, reach_feet)
    assert spell_range.feet is not None  # __post_init__ refuses one without
    return within(caster, origin, spell_range.feet)
