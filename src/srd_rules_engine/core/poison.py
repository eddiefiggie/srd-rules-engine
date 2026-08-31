"""p. 197's four poison delivery types, and the one whose exposure the engine can see (#141).

p. 197 enumerates *"Poisons come in the following four types"* — a closed named set with its
own rules subsection, which is `closed-named-set` (0013, Q4) admitting all four as shapes the
way it admitted the eight weapon masteries. The individual poisons are **content**: Purple
Worm Poison and Serpent Venom compose shapes already inventoried, so they are #21's, not this
module's.

## Only Injury is built, and the reason is in the document

#141 held all five affliction shapes on one reading: *exposure is a narrative fact, so the
engine cannot determine it*. p. 197 gives each type its own exposure sentence, and they are
not the same kind of thing:

* **Contact** — *"touches contact poison with exposed skin"*. Narrative.
* **Ingested** — *"must swallow an entire dose"*. Narrative.
* **Inhaled** — *"subjects creatures in a 5-foot Cube"*. An area, and a duration: the cloud
  *"dissipates immediately afterward"*.
* **Injury** — *"A creature that takes **Piercing or Slashing** damage from an object coated
  with the poison is exposed to its effects."*

The last is a **damage-type condition**, and this engine already resolves damage types. So
Injury needs no memory-port fact at all, and #141's blocker does not reach it. The other
three stay unbuilt and are named rather than omitted (R32).

## Nothing here is a rule value

A `Poison` carries the DC and the rule its effects resolve under, both supplied by a ruleset.
No SRD poison ships, for the reason `SpellSlots` ships no table of slot counts: p. 197's
prices, DCs and damage are content that has not been verified entry by entry (#21), and
compiling them here would be the inferred rule value R31 forbids.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.rules import (
    Verification,
    VerificationMethod,
    VerificationState,
)

POISON_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Gameplay Toolbox -> Poison, p. 197 ("Poisons come in the following four '
        'types"), with Injury\'s exposure ("A creature that takes Piercing or Slashing damage '
        'from an object coated with the poison is exposed to its effects"), its application '
        '("can be applied as a Bonus Action") and its expiry ("remains potent until delivered '
        'through a wound or washed off")'
    ),
    date="2026-08-31",
    method=VerificationMethod.ASSERTED,
)


class Delivery(StrEnum):
    """p. 197's four types. All four named; only `INJURY` is reachable (R32).

    Named rather than omitted because an enum with one member would say the document has one
    delivery type, and a reader who cannot see the other three cannot tell a modelled rule
    from an unmodelled one — which is the disclosure R32 exists for.
    """

    #: p. 197: smeared on an object, and a creature "that touches contact poison with exposed
    #: skin suffers its effects". Narrative — the engine cannot see a touch.
    CONTACT = "contact"
    #: p. 197: "A creature must swallow an entire dose." Narrative, and it carries a **GM
    #: option** rather than a rule — "You *may* decide that a partial dose has a reduced
    #: effect" — so the reduction is the caller's and not a mechanic to build.
    INGESTED = "ingested"
    #: p. 197: "subjects creatures in a 5-foot Cube", whose cloud "dissipates immediately
    #: afterward". An area and a duration rather than a fact.
    #:
    #: p. 197 also states an explicit **non**-interaction, which is worth carrying because the
    #: opposite inference is the obvious one: "Holding one's breath is ineffective against
    #: inhaled poisons". This engine models breath-holding, in `core.hazards`.
    INHALED = "inhaled"
    #: p. 197, and the only one the engine can observe: "A creature that takes Piercing or
    #: Slashing damage from an object coated with the poison is exposed to its effects."
    INJURY = "injury"


#: p. 197's exposure condition for an Injury poison, and the whole of why this type is
#: buildable while the other three are not. Piercing **or** Slashing — a coated club delivers
#: nothing, which is the case an implementation drops by firing on any damage at all.
DELIVERING_DAMAGE: Final[frozenset[DamageType]] = frozenset(
    {DamageType.PIERCING, DamageType.SLASHING}
)


@dataclass(frozen=True)
class Poison:
    """One poison, as a ruleset states it (p. 197).

    **Ruleset data the creature holds**, exactly as 0040 made a weapon an `Item` rather than
    something the engine carries a table of. The DC is stated by whoever supplies the poison,
    and `rule_id` names the resolver its effects resolve under — the same seam 0038 clause 3
    gives a spell, and for the same reason: p. 197's poisons deal damage and apply conditions
    that are content rather than engine rules.
    """

    name: str
    delivery: Delivery
    #: The DC of the Constitution save p. 197's poisons all compel. Ruleset data.
    save_dc: int
    #: The rule the poison's own effects resolve under, once the save is rolled.
    rule_id: str
    #: p. 197 states a Constitution save for every poison it prints, and states no other, so
    #: this is not a parameter the document leaves open — it is here because a ruleset may
    #: state a poison the SRD does not.
    save_ability: str = "con"

    def __post_init__(self) -> None:
        if not self.name or not self.rule_id:
            raise ValueError("a poison needs a name and the rule its effects resolve under")

    @property
    def is_deliverable_by_a_wound(self) -> bool:
        """Whether taking damage can expose a creature to this (p. 197).

        True only for `INJURY`. The other three are exposed by a touch, a swallow or a cloud,
        and none of those is a thing this engine observes — so a coated weapon carrying a
        Contact poison delivers nothing through a wound, and saying so here keeps the
        distinction where the document put it.
        """
        return self.delivery is Delivery.INJURY

    def delivers(self, damage_type: DamageType | None) -> bool:
        """Whether damage of this type delivers the poison (p. 197).

        Piercing or Slashing, and nothing else. Untyped damage delivers nothing rather than
        everything: `None` means the rule that dealt it named no type, and treating an unnamed
        type as a match would make the exposure condition unfalsifiable.
        """
        return self.is_deliverable_by_a_wound and damage_type in DELIVERING_DAMAGE
