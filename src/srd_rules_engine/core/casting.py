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
Longer casting times are no longer in that list — #250 built them, and
[0065](../../../docs/decisions/0065-a-long-cast-spends-its-slot-on-completion.md) is the
reasoning. Two things about them are still not modelled, and both are named rather than left
to be found:

- **Hours are expressed in minutes.** p. 105 says "minutes or even hours" and the engine holds
  one unit, so a two-hour casting is `casting_minutes=120`. The arithmetic is exact; what is
  missing is a caller's ability to say "hours" and be understood. That is a vocabulary gap
  rather than a rules gap, and it is disclosed because a reader who sees only `MINUTES` would
  reasonably conclude the longer half is unsupported.
- **A Ritual runs through this since
  [#371](https://github.com/eddiefiggie/srd-rules-engine/issues/371)**, and did not before.
  p. 105's sentence is explicitly about rituals — "including a spell cast as a Ritual" —
  and `ritual_cast` computed p. 187's extra ten minutes without ever becoming a `LongCast`,
  so a Ritual's turns were counted and nothing charged them.
  [0074](../../../docs/decisions/0074-a-ritual-is-a-long-casting.md) joins the two. **The
  sentence itself was asserted nowhere** until then: this docstring quoted it to explain the
  gap while the verifier had never read it.

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
from dataclasses import replace

from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.adjudicate import (
    Declaration,
    Proposal,
    Resolver,
    action_spent,
    concentration_begun,
    long_cast_begun,
    long_cast_continued,
    spell_slot_expended,
)
from srd_rules_engine.core.equipment import untrained_armour
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import ACTION_FOR_CASTING as ACTION_FOR_CASTING
from srd_rules_engine.core.read_surface import (
    cast_declared,
    continue_cast_declared,
    ritual_declared,
)
from srd_rules_engine.core.spellcasting import (
    CastingTime,
    LongCast,
    Spell,
    component_refusal,
    ritual_cast,
    ritual_turns_to_cast,
    turns_to_cast,
)
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

        # p. 105's continuation, answered before the slot level is read: a continuation names
        # no level. The one the casting will spend was fixed when it began and rides on
        # `Combatant.long_cast`, so re-reading it off the key would let ten turns of casting
        # be redirected to a different slot on the last one.
        if continue_cast_declared(declaration.intent.action_key) is not None:
            return _continued(state, declaration, spell, effects)

        # p. 187's Ritual, answered before the ordinary cast key is read, because a ritual
        # names no slot level and `cast_declared` would find none to parse (#371, 0074).
        if ritual_declared(declaration.intent.action_key) is not None:
            return _ritual_begun(state, declaration, spell)

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
        long_cast = spell.casting_time is CastingTime.MINUTES
        if long_cast and caster.long_cast is None:
            # p. 105: the first Magic action of a casting that takes minutes. **No slot is
            # expended** — the casting has not happened yet, and a broken Concentration
            # refunds nothing because nothing was spent (#250, 0065 clause 2).
            if caster.slots is None or slot_level not in caster.slots.payable_by(spell.level):
                raise ValueError(
                    f"{caster.name} cannot pay for {spell.rule_id!r} with a level "
                    f"{slot_level} slot. The level is checked when the casting **starts** "
                    "even though it is not spent until the casting finishes, because a "
                    "caster who could never pay has nothing to spend ten turns on"
                )
            # `outcome` rather than `always`: 0027 clause 6 — a rule that resolves without
            # a d20 states its effects there, and beginning a casting has no branch to be
            # conditional on.
            return Proposal(
                outcome=(
                    *costs,
                    concentration_begun(
                        caster_id,
                        description=(
                            f"{caster.name} begins concentrating for the "
                            f"{spell.casting_minutes}-minute casting of {spell.rule_id} "
                            "(p. 105)"
                        ),
                    ),
                    long_cast_begun(
                        caster_id,
                        LongCast(
                            spell_id=spell.rule_id,
                            slot_level=slot_level,
                            # **Minus this one**, which has just been charged above.
                            # `turns_remaining` counts the actions still owed "this turn's
                            # included", so storing the full count here counted the opening
                            # Magic action twice and a one-minute casting cost eleven turns
                            # (#371 found it while building the ritual on this machinery).
                            turns_remaining=turns_to_cast(spell) - 1,
                        ),
                        description=(
                            f"{spell.rule_id} takes {spell.casting_minutes} minutes, so "
                            f"{turns_to_cast(spell)} Magic actions of it — this is the first "
                            "(p. 105)"
                        ),
                    ),
                ),
                citations=("srd:spells/casting-spells",),
                may_claim=(
                    f"that {caster.name} began a long casting and is still at it",
                    "that nothing has been spent yet, because nothing has",
                ),
                may_not_claim=(
                    "that the spell happened; p. 105 takes minutes and this is the start",
                    "that a slot was expended — none is until the casting completes",
                ),
            )

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

        # p. 104: "You must have training with any armor you are wearing to cast spells while
        # wearing it." Asked here as well as at the offer, which is 0062's rule applied in the
        # change after it rather than three builds later.
        untrained = untrained_armour(caster.equipment, caster.armour_training)
        if untrained:
            raise ValueError(
                f"{caster.name} is wearing {', '.join(untrained)} without training, and "
                "p. 104 forbids casting while wearing armour you lack training with. p. 177 "
                'says it again: "you can\'t cast spells"'
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


def _ritual_begun(state: EncounterState, declaration: Declaration, spell: Spell) -> Proposal:
    """The first Magic action of a Ritual (p. 105, p. 187, #371, 0074).

    p. 105 names rituals in the sentence that introduces longer casting times — "Certain
    spells, including a spell cast as a Ritual, require more time to cast" — so a Ritual runs
    through the same machinery as any casting of a minute or more: a Magic action on each
    turn, Concentration throughout, and nothing produced until the last one.

    **`ritual_cast` is what refuses**, rather than a second copy of p. 187's three
    preconditions. It has enforced them since #19 and had no caller until now, which is why
    a Ritual could be computed and never charged.

    **No slot, and that is a `None` rather than a zero.** p. 187: "It also doesn't expend a
    spell slot, which means the ritual version of a spell can't be cast at a higher level."
    The casting carries no level to spend, so `LongCast.slot_level` is `None` and the
    completion spends nothing.

    **The refund clause is satisfied twice over.** p. 105 says a broken Concentration expends
    no slot; a Ritual had none to expend in the first place. Both readings agree and the
    second is the stronger, which is worth stating because it is the clause an implementation
    reaches for when it wants to refund something.
    """
    caster_id = declaration.actor_id
    caster = state.combatant(caster_id)

    if caster.long_cast is not None:
        raise ValueError(
            f"{caster.name} is already part-way through casting "
            f"{caster.long_cast.spell_id!r}. p. 105 runs one casting at a time — "
            '"To cast the spell again, you must start over"'
        )

    # p. 187's three refusals, from the one function that owns them.
    ritual_cast(
        spell_id=spell.rule_id,
        prepared=frozenset(caster.prepared),
        has_ritual_tag=spell.ritual,
    )

    turns = ritual_turns_to_cast(spell)
    # Minus this one, for the reason the ordinary long cast subtracts it: the Magic action
    # charged just below is the casting's first, and `turns_remaining` counts this turn's.
    return Proposal(
        outcome=(
            action_spent(
                caster_id,
                ActionKind.ACTION,
                description=(
                    f"the Magic action p. 105 charges for this turn of ritualling "
                    f"{spell.rule_id} ({turns} owed, this one included)"
                ),
            ),
            concentration_begun(
                caster_id,
                description=(
                    f"{caster.name} begins concentrating for the ritual casting of "
                    f"{spell.rule_id} (p. 105)"
                ),
            ),
            long_cast_begun(
                caster_id,
                LongCast(spell_id=spell.rule_id, slot_level=None, turns_remaining=turns - 1),
                description=(
                    f"a Ritual takes 10 minutes longer than normal (p. 187), so "
                    f"{spell.rule_id} owes {turns} Magic actions — this is the first"
                ),
            ),
        ),
        citations=("srd:spells/casting-spells", "srd:rules-glossary/ritual"),
        may_claim=(
            f"that {caster.name} began a ritual and is still at it",
            "that nothing has been spent, and that nothing will be — a Ritual expends no slot",
        ),
        may_not_claim=(
            "that the spell happened; a Ritual takes ten minutes longer and this is the start",
            "that a slot was expended or reserved; p. 187 expends none at all",
        ),
    )


def _continued(
    state: EncounterState, declaration: Declaration, spell: Spell, effects: Resolver
) -> Proposal:
    """One more Magic action toward a casting of a minute or more (p. 105, 0065).

    > While you cast a spell with a casting time of 1 minute or more, you must take the Magic
    > action on each of your turns, and you must maintain Concentration while you do so.

    **The last one is the casting**, and only there does the slot leave the caster. Everything
    before it costs an Action and produces nothing, which is exactly what p. 105 describes and
    is why a broken Concentration refunds nothing: there is nothing to refund.

    Concentration is **not re-begun** on each turn. It began with the casting and p. 179's
    replacement rule would otherwise end and restart it every turn, which is a mechanic the
    document does not describe.
    """
    caster_id = declaration.actor_id
    caster = state.combatant(caster_id)
    in_progress = caster.long_cast
    if in_progress is None:
        raise ValueError(
            f"{caster.name} is not part-way through a long casting, so p. 105 has no Magic "
            "action to charge. A continuation names a casting that has begun"
        )
    if in_progress.spell_id != spell.rule_id:
        raise ValueError(
            f"{caster.name} is part-way through {in_progress.spell_id!r} and this continues "
            f'{spell.rule_id!r}. p. 105: "To cast the spell again, you must start over" — '
            "there is one casting at a time and this is not it"
        )
    if not caster.concentration.active:
        raise ValueError(
            f"{caster.name} is no longer concentrating, so the casting of {spell.rule_id!r} "
            "has already failed (p. 105). Nothing is refunded, because nothing was spent"
        )

    spent = action_spent(
        caster_id,
        ActionKind.ACTION,
        description=(
            f"the Magic action p. 105 charges for this turn of casting {spell.rule_id} "
            f"({in_progress.turns_remaining} owed, this one included)"
        ),
    )
    if not in_progress.finishes_now:
        return Proposal(
            outcome=(
                spent,
                long_cast_continued(
                    caster_id,
                    description=(
                        f"{in_progress.turns_remaining - 1} more Magic actions before "
                        f"{spell.rule_id} is cast (p. 105)"
                    ),
                ),
            ),
            citations=("srd:spells/casting-spells",),
            may_claim=(f"that {caster.name} is still casting {spell.rule_id}",),
            may_not_claim=(
                "that the spell happened; it has not, and no slot has been spent",
                "that the casting is safe — losing Concentration ends it with nothing to show",
            ),
        )

    # The last turn. The slot leaves the caster **now**, and the spell resolves — unless
    # there is no slot, which is p. 187's Ritual: "It also doesn't expend a spell slot"
    # (#371). A ritual completes having spent nothing but Magic actions, so the only cost
    # that appears here is the last of those.
    proposal = effects(state=state, declaration=declaration, facts={})
    slot_level = in_progress.slot_level
    return replace(
        proposal,
        always=(
            spent,
            long_cast_continued(
                caster_id, description=f"the last Magic action {spell.rule_id} needed (p. 105)"
            ),
            *(
                (
                    spell_slot_expended(
                        caster_id,
                        slot_level,
                        description=(
                            f"a level {slot_level} slot, expended as the casting of "
                            f"{spell.rule_id} **completes** rather than when it began (p. 105)"
                        ),
                    ),
                )
                if slot_level is not None
                else ()
            ),
            *proposal.always,
        ),
    )


def spell_resolvers(spells: Mapping[Spell, Resolver]) -> dict[str, Resolver]:
    """Every spell's resolver, wrapped and keyed by the rule id the declaration will name.

    **The only documented way to register a spell**, and that is 0038 clause 3's guard rather
    than a convenience. A consumer building the mapping by hand can register a bare effects
    resolver and get a spell that costs nothing; going through here, that is not expressible,
    because the wrapping is what this function does.
    """
    return {spell.rule_id: spell_resolver(spell, effects) for spell, effects in spells.items()}
