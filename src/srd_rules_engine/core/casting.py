"""Casting a spell: the engine spends what it costs, the ruleset says what it does.

[0038](../../../docs/decisions/0038-a-spell-is-data-the-caster-carries.md) settled the shape
and this is the whole of it that runs. `core.spellcasting` holds `Spell` as data, because
`Combatant` carries one and cannot import a module that imports state; the resolver lives
here for the reason `core.concentration` and `core.save_ends` do — a resolver takes an
`EncounterState`, so it belongs beside the state it reads.

## Why a wrapper rather than a resolver

A spell is the **first mechanic whose effect comes from outside the engine**. Every other
rule here is resolved by code this repository ships and can verify; a spell's effect is a
`Resolver` a consumer brings, because spell descriptions are content this repository does not
carry (R31).

So "the engine holds outcome authority" has to mean something more specific for spells than
it does anywhere else: **the engine owns the costs and the compelled consequences, and the
ruleset owns only what the spell does.** `spell_resolver` is that boundary. It pays the slot,
starts Concentration when the spell requires it, and then asks the ruleset's resolver what
happens.

A ruleset that expended its own slot could forget to, and the failure would be invisible: the
spell works, the ledger records a Ruling, and only the slot count is wrong. `spell_resolvers`
is therefore the **only** documented way to register a spell — it wraps what you give it, so
an unwrapped effects resolver cannot reach the engine through the path the documentation
describes (0038 clause 3).

## What the costs are, and why they are not in a branch

p. 104: "When you cast a spell, you expend a slot of that spell's level or higher." The
expenditure is tied to the *casting*, not to how the roll came out, so it goes in
`Proposal.always` rather than being duplicated into every branch (0038 clause 6).

**Casting and spending a slot are separate facts.** p. 104's *Casting without Slots* names
four routes that expend none — Cantrips, Rituals, Special Abilities and Magic Items — so the
wrapper asks what this casting costs rather than assuming a slot. A cantrip is not a special
case bolted on afterwards; it is the second-most ordinary case the page describes, and this
engine builds that one.

## What this does not check, and cannot

R32, and it is a real boundary rather than a formality. Three of p. 104-105's requirements
are **not enforced**, so a spell this engine offers as castable is castable *as far as this
engine can tell* rather than castable:

- **Components** (p. 105). "If the spellcaster can't provide one or more of a spell's
  components, the spellcaster can't cast the spell." Verbal turns on being gagged or in an
  area of magical silence, neither of which this engine models
  ([#246](https://github.com/eddiefiggie/srd-rules-engine/issues/246)); Somatic and Material
  turn on hands and on held materials, and there is no equipment model here at all
  ([#245](https://github.com/eddiefiggie/srd-rules-engine/issues/245)). `Spell` therefore
  holds no components: a field enforcing nothing is the decay this repository has found twice.
- **Casting in Armor** (p. 104). "You must have training with any armor you are wearing to
  cast spells while wearing it." A flat prohibition, and nothing models worn armour or armour
  training ([#247](https://github.com/eddiefiggie/srd-rules-engine/issues/247)). This is the
  one that matters most, because it is a **legality** rule: the read surface will offer
  casting to a creature the document forbids from casting.
- **Longer casting times** (p. 105), which are absent from `CastingTime` rather than
  approximated ([#250](https://github.com/eddiefiggie/srd-rules-engine/issues/250)).

And two things this module *does* charge, which the rest of the engine does not:

- **Casting spends its action** (p. 185), and it is the first thing an adjudication has ever
  charged. **An attack still does not cost the Action**
  ([#252](https://github.com/eddiefiggie/srd-rules-engine/issues/252)) — disclosed here
  because an engine that charges one act and not another is more confusing than one that
  charges neither.
- **p. 185's entry has a second half** — a feature or magic item activated as a Magic action —
  which is unbuilt, so `ENGINE_SHAPES` does not claim the `magic` shape
  ([#253](https://github.com/eddiefiggie/srd-rules-engine/issues/253)).

Preparation is not in this list. A caster carries the spells it can cast; *how that list is
arrived at* is [#249](https://github.com/eddiefiggie/srd-rules-engine/issues/249), and 0038
clause 8 is why it refines one list rather than adding a second.
"""

from __future__ import annotations

from collections.abc import Mapping

from srd_rules_engine.core.adjudicate import (
    Declaration,
    Proposal,
    Resolver,
    action_spent,
    concentration_begun,
    spell_slot_expended,
)
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import ACTION_FOR_CASTING as ACTION_FOR_CASTING
from srd_rules_engine.core.read_surface import cast_declared
from srd_rules_engine.core.spellcasting import Spell, component_refusal
from srd_rules_engine.core.state import EncounterState

#: Re-exported, not restated (p. 105, p. 185). `core.read_surface` owns the map because it is
#: what decides legality, and a second copy here is a second thing to keep true. p. 185's
#: Magic action is what an action-timed spell costs: "When you take the Magic action, you cast
#: a spell that has a casting time of an action."


def spell_resolver(spell: Spell, effects: Resolver) -> Resolver:
    """Wrap a ruleset's effects resolver so the engine pays what casting costs.

    The costs go in `Proposal.always`, so they apply whatever the roll decides and are
    recorded before the consequence — which is the order they happened in.

    Nothing here reads the spell's description, and nothing here decides what the spell does.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        caster_id = declaration.actor_id
        caster = state.combatant(caster_id)
        declared = cast_declared(declaration.intent.action_key)
        if declared is None or declared[0] != spell.rule_id:
            raise ValueError(
                f"{spell.rule_id!r} was adjudicated under an action key that does not name "
                "it. The slot level a casting spends is read off the key the read surface "
                "offered, so a declaration that names no cast has no level to spend"
            )
        slot_level = declared[1]

        # p. 185: "When you take the Magic action, you cast a spell that has a casting time
        # of an action." The action is charged first, because it is what the act *is* —
        # a caster with no Action left has not cast a spell cheaply, it has not cast one.
        costs = [
            action_spent(
                caster_id,
                ACTION_FOR_CASTING[spell.casting_time],
                description=(
                    f"the {spell.casting_time.value} {caster.name} spent casting "
                    f"{spell.rule_id} (p. 105, p. 185)"
                ),
            )
        ]
        if spell.is_cantrip:
            # p. 178: "A cantrip is a level 0 spell, which is cast without a spell slot."
            if slot_level:
                raise ValueError(
                    f"{spell.rule_id!r} is a cantrip and is cast without a spell slot "
                    f"(p. 178), so it cannot be cast with a level {slot_level} one"
                )
        else:
            if caster.slots is None or slot_level not in caster.slots.payable_by(spell.level):
                raise ValueError(
                    f"{caster.name} cannot pay for {spell.rule_id!r} with a level "
                    f"{slot_level} slot. p. 104 fills a slot of the spell's level or higher, "
                    "and the read surface offers only the levels that can pay — so a level "
                    "that reaches here unoffered is a declaration the engine never made"
                )
            costs.append(
                spell_slot_expended(
                    caster_id,
                    slot_level,
                    description=(
                        f"a level {slot_level} spell slot, expended to cast a level "
                        f"{spell.level} spell (p. 104)"
                    ),
                )
            )

        # p. 104: "Before you can cast a spell, you must have the spell **prepared in your
        # mind** or have access to the spell from a magic item." The read surface has asked
        # since #249 and this had not — the same half-enforcement the components below carried,
        # found by reading the one function while fixing the other (0062).
        if spell.rule_id not in caster.prepared:
            raise ValueError(
                f"{caster.name} does not have {spell.rule_id!r} prepared, and p. 104 casts "
                "only a prepared spell. Carrying a spell is not preparing it — the read "
                "surface offers only what is prepared, so one that reaches here was never "
                "offered"
            )

        # p. 105: "If the spellcaster can't provide one or more of a spell's components, the
        # spellcaster can't cast the spell." Asked **here** as well as at the read surface,
        # because the menu is a menu and not a promise: `legal_actions` drops a spell whose
        # components the caster cannot provide, and a caller that reaches adjudication without
        # consulting it would otherwise cast one anyway (#245, 0062).
        #
        # The same function answers both, so the offer and the refusal cannot disagree about
        # which hand is free.
        refusal = component_refusal(spell, caster.equipment, caster.hands)
        if refusal is not None:
            raise ValueError(
                f"{caster.name} cannot provide {spell.rule_id!r}'s components: {refusal} "
                "(p. 105). The read surface drops a spell it cannot cast, so one that reaches "
                "here is a declaration the engine never offered"
            )

        if spell.requires_concentration:
            # p. 179's replacement is inside `Concentration.begin`: whatever came before ends
            # at the moment this starts. Recorded as a cost because it is what casting did,
            # not what the roll decided.
            costs.append(
                concentration_begun(
                    caster_id,
                    description=(
                        f"{caster.name} begins concentrating, ending whatever it was "
                        "concentrating on before (p. 179)"
                    ),
                )
            )

        proposed = effects(state=state, declaration=declaration, facts=facts)
        return Proposal(
            test=proposed.test,
            citations=proposed.citations,
            always=(*costs, *proposed.always),
            outcome=proposed.outcome,
            on_success=proposed.on_success,
            on_natural_20=proposed.on_natural_20,
            on_natural_1=proposed.on_natural_1,
            on_failure=proposed.on_failure,
            may_claim=proposed.may_claim,
            may_not_claim=proposed.may_not_claim,
        )

    return resolve


def spell_resolvers(spells: Mapping[Spell, Resolver]) -> dict[str, Resolver]:
    """Every spell's resolver, wrapped and keyed by the rule id the declaration will name.

    **The only documented way to register a spell**, and that is 0038 clause 3's guard rather
    than a convenience. A consumer building the mapping by hand can register a bare effects
    resolver and get a spell that costs nothing; going through here, that is not expressible,
    because the wrapping is what this function does.
    """
    return {spell.rule_id: spell_resolver(spell, effects) for spell, effects in spells.items()}
