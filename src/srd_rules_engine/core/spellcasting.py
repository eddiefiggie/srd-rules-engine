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

* **Long Rest recovery has no trigger.** "Finishing a Long Rest restores any expended spell
  slots" (p. 104). `restored()` is that operation and nothing calls it. `core.clock` now
  supplies the campaign time this was waiting on (#85), so what is missing is the rest
  itself — a Long Rest is "a period of extended downtime—at least 8 hours" (p. 185) with
  benefits this module does not model — [#19](https://github.com/eddiefiggie/srd-rules-engine/issues/19).
* **Components, and the Spellcasting Focus that substitutes for them** (p. 188), need item
  and inventory state that does not exist. So does a Ritual's ten extra minutes (p. 187).
* **Prepared versus known** is class data, and `modify-a-spell` and `multiclass-spell-slots`
  likewise. None is claimed.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.conditions import Conditions
from srd_rules_engine.core.d20 import D20Test, TestKind
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
    """What a creature is concentrating on, if anything (p. 179)."""

    spell: str | None = None

    @property
    def active(self) -> bool:
        return self.spell is not None

    def begin(self, spell: str) -> Concentration:
        """Start concentrating, ending whatever came before.

        p. 179: "You lose Concentration on an effect the moment you **start casting** a
        spell that requires Concentration." Replacement rather than refusal, and at the
        moment casting starts rather than when it resolves — so a caster cannot hold two by
        having the second one fail.
        """
        if not spell:
            raise ValueError("a concentration effect is named, or it cannot be ended later")
        return Concentration(spell=spell)

    def ended(self) -> Concentration:
        """p. 179: "The creator can end Concentration at any time (no action required).\""""
        return Concentration()

    def after_conditions(self, conditions: Conditions) -> Concentration:
        """p. 179: "Your Concentration ends if you have the Incapacitated condition."

        `core.conditions` already reports `concentration_broken` for Incapacitated, so this
        reads that rather than re-deciding which conditions qualify — one rule, one place.
        """
        if any(effects.concentration_broken for effects in conditions.effects):
            return Concentration()
        return self


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
