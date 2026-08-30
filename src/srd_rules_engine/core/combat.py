"""Enough of combat to run one fight: turn order, attacks, damage, and dropping to 0.

R12 in full covers reactions, opportunity attacks, and the whole action economy. This is
the slice's share of it. What provokes an Opportunity Attack now lives in `core.reactions`
(#16), which computes the trigger and withholds every offer, because p. 185's sentence turns
on a mover "that you can see" and sight is unanswerable until [#150](https://github.com/eddiefiggie/srd-rules-engine/issues/150).

Two things in this module are machinery rather than content, which is what lets them
exist while [#3](https://github.com/eddiefiggie/srd-rules-engine/issues/3) — the official
document this project verifies against — is still open:

- **Initiative orders combatants and nothing more.** Which ability the modifier comes from
  is a rule with a section citation, so it is a *parameter* rather than a constant here.
- **An attack is the d20 test with the target's armour value as its target number.** That
  is R11 doing its job: the kind changes where the number came from, not how the roll
  resolves.

What a weapon *is* stays outside: `Weapon` is a shape a ruleset fills in, and no weapon
list ships in this module. A table of longswords compiled from memory would be exactly the
inferred rule value R31 forbids, and it would be indistinguishable from a verified one
once it was inside a finished ruling.

**The resolver declares damage; it never states a total.** It returns `DamageDice`, and
the engine rolls it from the same seed as the attack. A resolver handing back
`Effect(amount=7)` would be a caller supplying a roll — the thing R4 exists to make
impossible — and it would also break replay in the quiet direction, reproducing the hit
and not the damage, which looks like it worked.

**A Ruling's effects are a record, not an instruction.** Nothing public applies them: the
adjudication entry point applies effects itself and returns the state it left behind, so
there is no second way to apply the same Ruling and therefore no way to apply it twice.

Criticals were deliberately absent from the slice and are not any more: p. 179's sentence —
a Critical Hit doubles the damage dice and not the modifiers — is asserted in the verifier
and `critical-hit` resolves. This paragraph said otherwise for several builds after that
landed, which is what an unguarded prose claim beside working code does.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.adjudicate import (
    DamageDice,
    Declaration,
    Effect,
    EffectKind,
    Proposal,
    Resolver,
    When,
    action_spent,
    advantage_pending,
    advantage_spent,
    ammunition_recovered,
    ammunition_spent,
    attack_made,
    carriage_changed,
    cleave_opened,
    cleave_taken,
    extra_attack_made,
    loading_fired,
    moved_by_force,
    object_detached,
    object_interacted,
    object_picked_up,
    save_compelled,
    speed_reduced,
    time_passed,
)
from srd_rules_engine.core.d20 import (
    INITIATIVE_BAND,
    Advantage,
    D20Test,
    Modifier,
    TestKind,
    roll,
)
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.equipment import HEAVY_SCORE_THRESHOLD as HEAVY_SCORE_THRESHOLD
from srd_rules_engine.core.equipment import RECOVERY_MINUTES, Carriage, Carried
from srd_rules_engine.core.equipment import Weapon as Weapon
from srd_rules_engine.core.forced_movement import displaced
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.obstructions import Cover, total_cover
from srd_rules_engine.core.pending_rolls import (
    SAP_RULE_ID,
    VEX_RULE_ID,
    PendingAdvantage,
    TurnBoundary,
)
from srd_rules_engine.core.position import (
    SLOW_REDUCTION_FEET,
    SLOW_RULE_ID,
    SpeedReduction,
    distance_feet,
    within,
)
from srd_rules_engine.core.read_surface import (
    ATTACK_DROP,
    ATTACK_EQUIP,
    PUSH_MASTERY_FEET,
    VERB_EQUIP,
    VERB_STOW,
    attack_declared,
    attack_swap_declared,
    attack_throw_declared,
    bonus_attack_declared,
    cleave_attack_declared,
    interaction_declared,
    nick_attack_declared,
    push_attack_declared,
    push_attack_feet,
)
from srd_rules_engine.core.read_surface import UNARMED_REACH_FEET as UNARMED_REACH_FEET
from srd_rules_engine.core.read_surface import UNARMED_STRIKE_ID as UNARMED_STRIKE_ID
from srd_rules_engine.core.rules import (
    Rule,
    RuleProvenance,
    Verification,
    VerificationMethod,
    VerificationState,
)
from srd_rules_engine.core.sight import Visibility
from srd_rules_engine.core.size import Size
from srd_rules_engine.core.state import Combatant, EncounterState, ForcedSave
from srd_rules_engine.core.topple import (
    TOPPLE_RULE_ID,
    TOPPLE_SAVE_ABILITY,
    topple_save_basis,
    topple_save_dc,
)

INITIATIVE_DIE = 20

#: R31. `HEAVY_SCORE_THRESHOLD` is a rule value, not machinery, so it carries what it was
#: checked against. A bare 13 in this module would read exactly like a verified one, which
#: is what `test_no_weapon_list_ships_in_this_module` exists to prevent.
WEAPON_PROPERTY_VERIFICATION = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        'SRD v5.2.1, Equipment ("Properties" -> Finesse, Heavy, Versatile), pp. 89-90; '
        '("Mastery Properties" -> Graze), p. 90'
    ),
    date="2026-08-23",
    method=VerificationMethod.ASSERTED,
)


def initiative_order(
    state: EncounterState, *, seed: int, ability: str = "dex"
) -> Mapping[str, int]:
    """Roll initiative for every combatant, deterministically from one seed.

    Returned rather than applied, because applying it is `EncounterState.with_initiative`
    and that is the only thing allowed to move the generation.
    """
    # #82. Its own band, and a bounded one. This used to draw from index 0 — the d20's
    # band — with one die per combatant and no bound, so a large enough encounter aliased a
    # combatant's initiative onto a damage die of the same seed. Nothing records initiative
    # in the ledger, so moving it rewrites no history.
    faces = roll(
        seed,
        count=len(state.combatants),
        sides=INITIATIVE_DIE,
        offset=INITIATIVE_BAND.start,
    )
    return {
        combatant.id: face + combatant.modifier(ability)
        for combatant, face in zip(state.combatants, faces, strict=True)
    }


def attack_resolver() -> Resolver:
    """The resolver for an attack, whichever weapon the creature swung (0040 clause 4).

    **It closed over a `Weapon` until #258**, and a ruleset registered one rule per weapon.
    That was right while a weapon was ruleset data with nowhere else to live: binding a table
    of them here would make the engine carry rule values it cannot verify. Since 0040 a weapon
    is an `Item` the creature **holds**, so the weapon comes off the state and one attack rule
    replaces one rule per weapon.

    **No wrapper, and the difference from a spell is the reason.** 0038 clause 3 wraps a
    ruleset's spell resolver because a spell's *effect* comes from outside the engine and a
    ruleset that expended no slot would cast for free. An attack's effect is stated by the
    document and shipped here — this function is engine code, and the only ruleset data is the
    weapon's numbers, which now ride on the creature. There is nothing outside the engine to
    wrap, and wrapping anyway would be indirection protecting against nothing.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        # p. 177's swap is settled before the weapon is looked up, because an equip may be
        # what puts the weapon in hand: "If you equip a weapon before an attack, you don't
        # need to use it for that attack" — but you may, and then the attack names something
        # the creature is not yet holding. The lookup therefore runs against the creature as
        # it **will be**, projected through the engine's own transitions rather than a second
        # copy of their logic. The projected state is read and discarded; `_apply` performs
        # the move for real, from the effects returned below.
        before, after = _swap_effects(state, actor, declaration)
        wielded, target_id, is_bonus, is_nick, is_cleave, is_thrown = _weapon_and_target(
            _after_equipping(state, before).combatant(declaration.actor_id), declaration
        )
        assert isinstance(wielded.item, Weapon)
        weapon = wielded.item
        # p. 89's extra attack, by whichever route. Every rule that asks "is this the extra
        # attack" — its damage exception, and its exclusion from the Multiattack tally — is
        # about p. 89 and not about the action carrying it, so p. 90's Nick answers yes to
        # all of them and differs only in what it costs (#320).
        is_extra = is_bonus or is_nick or is_cleave
        # p. 89's **one** extra attack, which Cleave is not: p. 90 gives it its own cap in its
        # own sentence, so a Cleave must not spend the Light property's allowance (#323).
        is_p89_extra = is_bonus or is_nick
        target = state.combatant(target_id)
        ability = actor.modifier(weapon.ability)

        _refuse_if_behind_total_cover(state, actor, target)
        beyond_normal = _out_of_range(weapon, actor, target, thrown=is_thrown)
        # p. 184's exception to Invisible, asked in both directions (#193). Each needs
        # CERTAINTY to move away from the answer that cannot manufacture an outcome, so an
        # UNSTATED view leaves both where 0030 clause 1 puts them.
        target_blind_to_actor = (
            state.can_see(target_id, declaration.actor_id).verdict is Visibility.CANNOT_SEE
        )
        actor_sees_target = (
            state.can_see(declaration.actor_id, target_id).verdict is Visibility.CAN_SEE
        )

        attacker_state = actor.conditions.own_attack_rolls(
            target_id=target_id,
            # p. 182's qualifier, askable since #192 stored the source of fear.
            fear_in_sight=state.fear_in_sight(declaration.actor_id),
            target_blind_to_you=target_blind_to_actor,
        )
        defender_state = target.conditions.attack_rolls_against(
            attacker=actor.position,
            target=target.position,
            attacker_sees_you=actor_sees_target,
        )
        # p. 181: while Dodging, attacks against you have Disadvantage. It reaches the same
        # pair of flags as everything else, so it cancels against Advantage rather than
        # accumulating beside it.
        dodging = target.is_dodging

        modifiers = [Modifier(source=f"ability:{weapon.ability}", value=ability)]
        # p. 89: "Anyone can wield a weapon, but **you** must have proficiency with it to add
        # your Proficiency Bonus to an attack roll you make with it." The wielder's fact, and
        # it was the weapon's field until 0040 clause 2 — which worked only while a weapon
        # belonged to one creature, and failed toward granting a bonus once one could be
        # picked up.
        if weapon.id in actor.weapon_proficiencies:
            modifiers.append(Modifier(source="proficiency", value=actor.proficiency_bonus))
        if weapon.bonus:
            modifiers.append(Modifier(source=f"{weapon.id} bonus", value=weapon.bonus))

        # p. 90's Vex and Sap, granted by an earlier roll and spent by this one (0049). They
        # reach the same pair of flags as every other circumstance, so p. 8's cancellation
        # rule resolves them rather than a second mechanism — a creature holding a Sap
        # penalty and attacking a target it has Vex on rolls straight, which is the document's
        # own answer and not a special case anybody had to write.
        pending = state.pending_advantage_for(declaration.actor_id, target_id)
        pending_advantage_held = any(t.state is Advantage.ADVANTAGE for t in pending)
        pending_disadvantage_held = any(t.state is Advantage.DISADVANTAGE for t in pending)

        return Proposal(
            # p. 176: "On your turn, you can take one action." p. 177 makes an attack one:
            # "When you take the Attack action, you can make **one attack roll**." So one
            # Action buys one attack roll here, and #252 is where that finally cost
            # something — nothing in the adjudication path charged anything until #248.
            #
            # **Extra Attack would make this wrong**, and it is a class feature this
            # repository ships none of: a feature that "gives you more than one attack as
            # part of the Attack action" (p. 177) would need the Action charged once for
            # several rolls. There is nothing to model it with today, and the day there is,
            # this is the line that has to change.
            # p. 177's swap applies whether or not the attack lands — it is licensed by
            # *making* an attack, not by hitting — so it rides in `always` beside the action
            # charge. Equips precede the charge and unequips follow it, which is the derived
            # ordering `_swap_effects` documents.
            always=(
                *before,
                # p. 90: "You can make this extra attack **only once per turn**", spent by
                # making it rather than by landing it — the document caps the *attack*, not
                # the hit, so a missed Cleave is still the one this turn allowed (#323).
                *(
                    (
                        cleave_taken(
                            declaration.actor_id,
                            description=f"p. 90's one Cleave a turn, swung with {weapon.id}",
                        ),
                    )
                    if is_cleave
                    else ()
                ),
                # p. 90: "your **next** attack roll", so a token in scope is spent by this
                # roll whether it hits or misses (0049). In `always` for exactly that reason —
                # either branch would keep it alive through half the outcomes.
                *(
                    advantage_spent(
                        token,
                        description=(
                            f"{token.rule_id}: the {token.state} it granted is spent on this "
                            "attack roll (p. 90)"
                        ),
                    )
                    for token in pending
                ),
                # p. 177's allowance is drawn on when a swap actually happens, and only then.
                # p. 191's Unconscious detaches an item too and must not spend it (0043
                # clause 3).
                *(
                    (
                        object_interacted(
                            declaration.actor_id,
                            description="p. 177's one equip or unequip, drawn on this turn",
                        ),
                    )
                    if (before or after)
                    else ()
                ),
                # p. 89: "Each attack expends one piece of ammunition." A cost that applies
                # because the attack happened, so it sits beside the action charge rather
                # than in a hit branch — p. 89 does not return the arrow on a miss.
                *(
                    (
                        ammunition_spent(
                            declaration.actor_id,
                            weapon.ammunition_id,
                            description=f"one {weapon.ammunition_id} fired from {weapon.id}",
                        ),
                    )
                    if weapon.ammunition_id is not None
                    else ()
                ),
                # p. 90: "You can fire only one piece of ammunition from a Loading weapon
                # when you use an action, a Bonus Action, or a Reaction to fire it,
                # **regardless of the number of attacks you can normally make**." Recorded
                # against the action that fired it, because that final clause is the whole
                # property and it only bites once one action buys several rolls (#271, #289).
                *(
                    (
                        loading_fired(
                            declaration.actor_id,
                            ActionKind.BONUS_ACTION if is_bonus else ActionKind.ACTION,
                            description=f"p. 90's one shot from {weapon.id}",
                            # `is_bonus`, not `is_extra`: a Nick attack is made as part of the
                            # **Action**, so its shot is charged there. No weapon in p. 91's
                            # table has both Loading and Nick, so this is unreachable with SRD
                            # content — and treating that as licence to skip the rule is how a
                            # wrong one ships.
                        ),
                    )
                    if weapon.loading
                    else ()
                ),
                # p. 257 counts the rolls the *Attack action* bought. p. 89's extra attack is
                # not one of them: by the Bonus Action route it is a separate action, which
                # #271 verified against the tree, and by p. 90's Nick it is made "as part of"
                # the Attack action without being bought by it — an **extra** attack either
                # way. Counting the Nick route would quietly cost a Multiattack creature one
                # of its rolls (#320).
                *(
                    ()
                    if is_extra
                    else (
                        attack_made(
                            declaration.actor_id,
                            description=f"an attack roll with {weapon.id} (p. 177, p. 257)",
                        ),
                    )
                ),
                # p. 257: "Some creatures can make more than one attack **when they take the
                # Attack action**", so the Action is spent once and buys them all. Charging it
                # per roll is what `attack_resolver` has carried a comment about since the
                # economy landed, naming this exact feature (0043 clause 1).
                #
                # **This clause is also what makes p. 90's Nick free**, and no separate
                # `is_nick` test belongs here (#320). Nick puts the extra attack "as part of
                # the Attack action", and an attack can only *be* part of an Attack action
                # that was already taken — p. 89 requires one, and taking it emits the
                # `ATTACK_MADE` this reads. So a Nick attack always arrives with the tally
                # non-zero and the Action already charged. Adding `is_nick` here read as
                # load-bearing and was unreachable: the corruption proof for it came back
                # green, because the condition beside it was true in every case that reaches
                # this line.
                *(
                    ()
                    if not is_bonus and state.attacks_this_turn.get(declaration.actor_id, 0)
                    else (
                        action_spent(
                            declaration.actor_id,
                            ActionKind.BONUS_ACTION if is_bonus else ActionKind.ACTION,
                            description=(
                                f"the Bonus Action spent on p. 89's extra Light attack with "
                                f"{weapon.id}"
                                if is_bonus
                                else "the Action spent on the Attack (p. 176, p. 177)"
                            ),
                            # p. 89 reads which weapon the Attack action was spent on, so the
                            # ordinary attack carries it and the bonus one does not — the bonus
                            # attack is what the record *buys*, not what it records.
                            weapon_id=None if is_bonus else weapon.id,
                        ),
                    )
                ),
                # p. 89 grants **one** extra attack, and p. 90 re-routes that same one rather
                # than adding a second. The Bonus Action spend used to enforce that by itself;
                # a Nick attack spends nothing, so the allowance is recorded explicitly (#320).
                *(
                    (
                        extra_attack_made(
                            declaration.actor_id,
                            description=(
                                f"p. 89's one extra Light attack with {weapon.id}, made "
                                + (
                                    "as part of the Attack action (p. 90, Nick)"
                                    if is_nick
                                    else "as a Bonus Action"
                                )
                            ),
                        ),
                    )
                    if is_p89_extra
                    else ()
                ),
                *after,
                # p. 90: the weapon is *thrown*, so it ends the attack out of the creature's
                # hands. Where it lands is stated by nothing — 0041 clause 4 — so it arrives
                # among the detached objects with no position, and the read surface reports it
                # under `unplaced_objects` rather than somewhere invented.
                #
                # In `always` because the weapon leaves the hand whether or not the throw hits:
                # p. 128 says "a thrown weapon or piece of ammunition returns to normal size
                # immediately after it **hits or misses** a target", which is the document
                # treating both outcomes as leaving the weapon elsewhere.
                *(
                    (
                        object_detached(
                            declaration.actor_id,
                            weapon.id,
                            description=f"{actor.name} throws {weapon.id}: p. 90",
                        ),
                    )
                    if is_thrown
                    else ()
                ),
            ),
            test=D20Test(
                kind=TestKind.ATTACK,
                target=target.armour_class,
                target_basis=f"armour class {target.armour_class}, worn by {target.name}",
                modifiers=tuple(modifiers),
                # Heavy (p. 89). The disadvantage is a property of the weapon in these
                # hands, so it is decided here rather than asked of the caller.
                # Heavy (p. 89), or attacking beyond a ranged weapon's normal range
                # (p. 90). Both are Disadvantage and they do not stack — the d20 takes a
                # single flag, which is the cancellation rule holding by construction.
                has_disadvantage=(
                    weapon.heavy_disadvantage(actor.abilities)
                    or beyond_normal
                    or attacker_state is Advantage.DISADVANTAGE
                    or defender_state is Advantage.DISADVANTAGE
                    or dodging
                    or pending_disadvantage_held
                ),
                # Conditions on either side reach the same pair of flags, so the
                # cancellation rule (p. 8) resolves them exactly as it resolves any other
                # pair of circumstances rather than through a second mechanism.
                has_advantage=(
                    attacker_state is Advantage.ADVANTAGE
                    or defender_state is Advantage.ADVANTAGE
                    or pending_advantage_held
                ),
            ),
            on_success=(
                DamageDice(
                    target_id=target_id,
                    count=weapon.damage_dice,
                    # Versatile (p. 90) selects the die; the ability modifier is whichever
                    # one Finesse let the wielder choose, and it reaches both rolls.
                    sides=weapon.sides_in_use(wielded.hands_used),
                    damage_type=weapon.damage_type,
                    # The same bonus, on the other roll. p. 213 says "attack rolls **and**
                    # damage rolls", so a weapon bonus reaching only the attack would be
                    # half a rule — and the half nobody notices.
                    # p. 89, and the exception is the whole of it: on the Light property's
                    # extra attack "you don't add your ability modifier to the extra attack's
                    # damage **unless that modifier is negative**". So a positive modifier is
                    # dropped and a negative one is kept — an implementation that simply
                    # dropped it would be wrong for every creature with a penalty, and wrong
                    # in the direction that helps them. The *attack roll* keeps it either way.
                    modifier=(min(0, ability) if is_extra else ability) + weapon.bonus,
                    source=weapon.id,
                ),
                # p. 90's Cleave, opened by a **melee** hit with a weapon the wielder may use
                # the property of (#323, 0047 clause 6). Recorded rather than resolved: the
                # second swing is a separate attack roll the wielder chooses to make, so it
                # reaches an outcome through the read surface and the one adjudication entry
                # point like any other (R1, R18).
                *(
                    (
                        cleave_opened(
                            actor.id,
                            weapon.id,
                            target.id,
                            description=(
                                f"{weapon.id} (Cleave): a second swing is open against a "
                                f"creature within 5 feet of {target.name}"
                            ),
                        ),
                    )
                    if weapon.cleave
                    and weapon.id in actor.mastery_weapons
                    and weapon.melee
                    and not is_thrown
                    and not is_cleave
                    else ()
                ),
                # Vex, Sap and Slow (p. 90): three properties a hit imposes, sharing one
                # turn boundary vocabulary and differing in what they impose (0049, 0050).
                *_vex_sap_and_slow(state, actor, weapon, target),
                # Topple (p. 90): "If you hit a creature with this weapon, you can force the
                # creature to make a Constitution saving throw." **On the hit branch and not
                # the damage one** — Vex and Slow say "and deal damage to it" and this does
                # not, so a hit reduced to zero by Resistance still topples.
                #
                # Recorded rather than resolved: the save is an outcome, and R1 leaves
                # outcomes to the one adjudication entry point. The DC travels with the debt
                # because its inputs are this attack's (0048, #321).
                *_topple(actor, weapon, target, ability),
                # Push (p. 90): "If you hit a creature with this weapon, you can push the
                # creature up to 10 feet straight away from yourself if it is Large or
                # smaller." On the hit branch beside Topple, and for the same reason — p. 90
                # does not say "and deal damage to it", so a hit reduced to zero still pushes.
                *_push(actor, weapon, target, declaration.intent.action_key),
            ),
            # Graze (p. 90): "If your attack roll with this weapon misses a creature, you
            # can deal damage to that creature equal to the ability modifier you used to
            # make the attack roll." The same modifier, and the weapon's own damage type.
            #
            # The actor is passed because the property is gated on the *wielder* (0047): p. 90
            # makes every mastery property "usable only by a character who has a feature …
            # that unlocks the property". Graze shipped ungated, which is the permissive
            # direction — a mechanic handed to creatures the rules do not give it to.
            on_failure=_graze(actor, weapon, target_id, ability),
            citations=(f"weapon:{weapon.id}",),
            may_claim=(f"that the attack on {target.name} resolved as the roll says",),
            may_not_claim=(
                f"that {target.name} is dead, unless its hit points reached 0",
                "any damage number other than the one the Ruling carries",
            ),
        )

    return resolve


#: R31. Asserted in `scripts/verify_d20_rules.py`.
UNARMED_STRIKE_VERIFICATION: Final = Verification(
    state=VerificationState.VERIFIED,
    reference=(
        "SRD v5.2.1, Rules Glossary, Unarmed Strike, p. 190 (the Damage option: an attack "
        "roll at Strength modifier plus Proficiency Bonus, and Bludgeoning damage equal to 1 "
        'plus the Strength modifier); "Attack [Action]", p. 177'
    ),
    date="2026-08-28",
    method=VerificationMethod.ASSERTED,
)


def unarmed_strike_rule() -> Rule:
    """p. 190's Unarmed Strike, Damage option."""
    return Rule(
        id=UNARMED_STRIKE_ID,
        summary=(
            "A melee attack made with the body against a target within 5 feet, at Strength "
            "modifier plus Proficiency Bonus, dealing Bludgeoning damage equal to 1 plus the "
            "Strength modifier."
        ),
        provenance=RuleProvenance.SRD,
        verification=UNARMED_STRIKE_VERIFICATION,
    )


def object_interaction_resolver() -> Resolver:
    """p. 13's free object interaction, and p. 191's Utilize action (0045, #288).

    > You can interact with **one object or feature of the environment for free**, during
    > either your move or action… If you want to interact with a second object, you need to
    > take the Utilize action.

    **No d20 test.** Sheathing a sword decides nothing — there is no target number and no
    roll — so this proposes effects and no `test`, the shape 0027 clause 6 opened for outcomes
    without one. It is still a ruling: R1 keeps the one entry point the only thing that
    changes state, and #119 stopped a caller reaching past it to move a condition.

    The moves are the same four p. 177's swap performs (0045 clause 2), so they route through
    the same transitions — a carriage change for drawing and stowing, 0041's detachment for
    dropping, and its reverse for picking up.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        declared = interaction_declared(declaration.intent.action_key)
        if declared is None:
            raise ValueError(
                "this declaration is not an object interaction: p. 13's free interaction and "
                "p. 191's Utilize are offered under their own keys, and one carrying neither "
                "names something else"
            )
        verb, item_id, utilize = declared
        effects: list[Effect] = []

        if verb == VERB_EQUIP:
            if any(o.item.id == item_id for o in state.detached_objects):
                effects.append(
                    object_picked_up(
                        actor.id, item_id, description=f"{actor.name} picks up {item_id}: p. 13"
                    )
                )
            else:
                effects.append(
                    carriage_changed(
                        actor.id,
                        item_id,
                        Carriage.HELD,
                        description=f"{actor.name} draws {item_id}: p. 13",
                    )
                )
        elif verb == VERB_STOW:
            effects.append(
                carriage_changed(
                    actor.id,
                    item_id,
                    Carriage.STOWED,
                    description=f"{actor.name} stows {item_id}: p. 13",
                )
            )
        else:
            effects.append(
                object_detached(
                    actor.id, item_id, description=f"{actor.name} drops {item_id}: p. 13"
                )
            )

        # p. 13 gives one free; the second costs the Action (p. 191). The allowance is spent
        # either way, because the Utilize action is what you take *because* the free one is
        # gone — it does not restore it.
        effects.append(
            object_interacted(actor.id, description="this turn's one object interaction (p. 13)")
        )
        if utilize:
            effects.append(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description="the Action spent on Utilize (p. 191)",
                )
            )

        return Proposal(
            # `outcome`, not `always`: 0027 clause 6 gives a testless proposal its own field,
            # and `always` is for costs that ride *beside* a roll. There is no roll here —
            # sheathing a sword decides nothing — so these are the outcome itself.
            outcome=tuple(effects),
            citations=("SRD 5.2.1 p. 13, Interacting with Things", "SRD 5.2.1 p. 191, Utilize"),
            may_claim=(f"that {actor.name} {verb}s {item_id}",),
            may_not_claim=(
                "that anything was found, opened, triggered or learned by the interaction",
            ),
        )

    return resolve


def ammunition_recovery_resolver() -> Resolver:
    """p. 89's minute spent recovering ammunition after a fight (0044 clause 5, #301).

    > After a fight, you can spend 1 minute to recover half the ammunition (round down) you
    > used in the fight; the rest is lost.

    **No d20 test**, for `object_interaction_resolver`'s reason: nothing is decided by a roll.
    The arithmetic is the document's and the minute is the document's; what the agent supplies
    is that the fight is over.

    ## The engine does not check that it is

    p. 14 states the test — "Combat ends when one side or the other is defeated, which can mean
    the creatures are killed or **knocked out** or have **surrendered** or **fled**. Combat can
    also end when **both sides agree to end it**" — and the engine can observe two of its five
    conditions. Surrender, flight and mutual agreement are judgements about the fiction, and
    R20 keeps the memory port typed so the engine never reads prose to find one.

    **So the claim is accepted, and the acceptance is disclosed** (0044 clause 5). Refusing on
    the two observable conditions would be the engine overruling the agent on the three it
    cannot see, and the half it *can* see is the half that answers *yes* — so inferring from it
    would end fights early and hand back arrows on the engine's own authority.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        recoverable = state.recoverable_ammunition(actor.id)
        if not state.ammunition_used or not any(
            who == actor.id for who, _ in state.ammunition_used
        ):
            raise ValueError(
                f"{actor.name} used no ammunition in this fight, so p. 89 has nothing to "
                "recover half of. A minute spent recovering nothing is not a rule the "
                "document states"
            )

        effects: list[Effect] = [
            # Every kind used is closed, including those whose half rounded to nothing:
            # p. 89 says "the rest is lost", so a single piece fired recovers none and
            # leaves nothing behind to recover later.
            ammunition_recovered(
                actor.id,
                item_id,
                pieces,
                description=(
                    f"{pieces} of {item_id} recovered, half of what was used (p. 89)"
                    if pieces
                    else f"none of {item_id} recovered; half of one rounds down (p. 89)"
                ),
            )
            for item_id, pieces in sorted(recoverable.items())
        ]
        effects.append(
            time_passed(actor.id, RECOVERY_MINUTES, description="1 minute spent recovering (p. 89)")
        )

        return Proposal(
            outcome=tuple(effects),
            citations=("SRD 5.2.1 p. 89, Ammunition", "SRD 5.2.1 p. 14, Ending Combat"),
            may_claim=("that the recovered ammunition was gathered up",),
            may_not_claim=(
                "that the fight is over — the engine accepted that claim and did not check it",
                "that the ammunition not recovered is findable later; p. 89 says it is lost",
            ),
        )

    return resolve


def unarmed_strike_resolver() -> Resolver:
    """p. 190's Damage option, and only that one.

    **The other two are built and are not here.** p. 190 offers three effects and this is one
    of them; Grapple and Shove live in `core.unarmed_strike`, because neither is an attack
    roll — each compels a saving throw and rolls nothing for the attacker, so they share none
    of the machinery below. What they share with this resolver is p. 190, and the read surface
    offers all three side by side.

    They took three records to become possible: 0051 for the size test, 0052 for the way out
    of a grapple, and 0053 for the target's choice of saving throw.

    **The Proficiency Bonus is unconditional here, and that is the difference from a weapon.**
    p. 89 adds it only "if you have proficiency with" the weapon; p. 190 states the bonus flat
    — "Your bonus to the roll equals your Strength modifier **plus your Proficiency Bonus**" —
    with no proficiency to have. So this is a second bonus rule beside the weapon path rather
    than a case of it, which is why it has its own resolver instead of a flag on that one.
    """

    def resolve(
        *,
        state: EncounterState,
        declaration: Declaration,
        facts: Mapping[str, Resolution],
    ) -> Proposal:
        actor = state.combatant(declaration.actor_id)
        declared = attack_declared(declaration.intent.action_key)
        if declared is None or declared[0] != UNARMED_STRIKE_ID:
            raise ValueError(
                "this declaration is not an Unarmed Strike: p. 190's strike is offered under "
                f"its own action key, and one naming {declared[0] if declared else None!r} "
                "names something else"
            )
        target = state.combatant(declared[1])
        _refuse_if_behind_total_cover(state, actor, target)

        strength = actor.modifier("str")
        # p. 190: "Bludgeoning damage equal to 1 plus your Strength modifier." Floored at 0,
        # because a creature with a Strength modifier below -1 would otherwise deal negative
        # damage — which is healing, and which the document neither states nor contemplates.
        # 0030 clause 1's direction: the reading that cannot manufacture an outcome.
        dealt = max(0, 1 + strength)

        return Proposal(
            always=(
                action_spent(
                    actor.id,
                    ActionKind.ACTION,
                    description="the Action spent on the Attack (p. 176, p. 177)",
                ),
            ),
            test=D20Test(
                kind=TestKind.ATTACK,
                target=target.armour_class,
                target_basis=f"armour class {target.armour_class}, worn by {target.name}",
                modifiers=(
                    Modifier(source="ability:str", value=strength),
                    # Unconditional (p. 190), unlike a weapon's.
                    Modifier(source="proficiency", value=actor.proficiency_bonus),
                ),
            ),
            on_success=(
                Effect(
                    kind=EffectKind.DAMAGE,
                    target_id=target.id,
                    amount=dealt,
                    damage_type=DamageType.BLUDGEONING,
                    description=(
                        f"unarmed strike: 1 + {strength} Strength modifier "
                        f"= {dealt} Bludgeoning (p. 190)"
                    ),
                ),
            ),
            citations=("srd:rules-glossary/unarmed-strike",),
            may_claim=(
                f"that {actor.name} struck {target.name} with a punch, kick, headbutt or "
                "similar forceful blow",
            ),
            may_not_claim=(
                "that the target was grappled or shoved — p. 190 makes those two other "
                "options of an Unarmed Strike, and this ruling is the Damage one. Both are "
                "offered under their own keys and neither happened here",
                "that the damage was anything but Bludgeoning, or any amount other than the "
                "one recorded",
            ),
        )

    return resolve


def _after_equipping(state: EncounterState, before: tuple[Effect, ...]) -> EncounterState:
    """`state` with p. 177's pre-attack equip already performed, for the weapon lookup only.

    The transitions are the engine's own, so the projection cannot drift from what `_apply`
    will do — a second implementation of "the item is now held" is exactly the kind of
    duplicate that stays right until one of them is fixed.
    """
    for effect in before:
        assert effect.item_id is not None  # only the item kinds reach here
        if effect.kind is EffectKind.OBJECT_PICKED_UP:
            state = state.with_object_picked_up(effect.target_id, effect.item_id)
        elif effect.kind is EffectKind.CARRIAGE_CHANGED:
            assert effect.carriage is not None
            state = state.with_carriage_changed(effect.target_id, effect.item_id, effect.carriage)
    return state


def _swap_effects(
    state: EncounterState, actor: Combatant, declaration: Declaration
) -> tuple[tuple[Effect, ...], tuple[Effect, ...]]:
    """p. 177's one equip or unequip, as `(before the attack, after it)`.

    **The ordering is derived, not declared** — 0042 clause 2 one level down. An equip
    resolves *before*, because the creature has to be holding the weapon for the attack to
    name it; an unequip resolves *after*, because unequipping first would leave nothing to
    swing. Neither is a choice the agent makes, and neither loses anything p. 177 permits:
    "you don't need to use it for that attack" makes equip-before-and-unused identical to
    equip-after, and an unequip before an attack with a *different* weapon reaches the same
    end state as one after it.

    Refusals are the same shape the weapon lookup uses: an item the creature does not have in
    the place the swap assumes is an offer the read surface never made.
    """
    swap = attack_swap_declared(declaration.intent.action_key)
    if swap is None:
        return (), ()
    _weapon_id, _target_id, item_id, kind = swap

    if kind == ATTACK_EQUIP:
        if any(o.item.id == item_id for o in state.detached_objects):
            return (
                object_picked_up(
                    actor.id, item_id, description=f"{actor.name} picks up {item_id}: p. 177"
                ),
            ), ()
        stowed = {c.item.id for c in actor.equipment if c.carriage is Carriage.STOWED}
        if item_id not in stowed:
            raise ValueError(
                f"{item_id!r} is neither stowed nor on the ground, so there is nowhere for "
                "p. 177's equip to draw it from. Equipping what is already held would be a "
                "move the read surface never offered"
            )
        return (
            carriage_changed(
                actor.id,
                item_id,
                Carriage.HELD,
                description=f"{actor.name} draws {item_id}: p. 177",
            ),
        ), ()

    held = {c.item.id for c in actor.equipment if c.carriage is Carriage.HELD}
    if item_id not in held:
        raise ValueError(
            f"{item_id!r} is not held, so there is nothing for p. 177's unequip to put away. "
            "Sheathing, stowing and dropping all start from a hand"
        )
    if kind == ATTACK_DROP:
        # p. 177's third destination leaves the creature entirely, and the object arrives
        # unplaced because no rule says where it lands (0041 clause 4).
        return (), (
            object_detached(actor.id, item_id, description=f"{actor.name} drops {item_id}: p. 177"),
        )
    return (), (
        carriage_changed(
            actor.id,
            item_id,
            Carriage.STOWED,
            description=f"{actor.name} stows {item_id}: p. 177",
        ),
    )


def _weapon_and_target(
    actor: Combatant, declaration: Declaration
) -> tuple[Carried, str, bool, bool, bool, bool]:
    """Which weapon this attack swung, and at whom, read off the key the surface offered.

    The key names both since #258, and the weapon is looked up in what the creature is
    **holding** rather than trusted from the declaration — an agent naming a weapon it has
    stowed, or does not have at all, is refused rather than obliged.
    """
    key = declaration.intent.action_key
    bonus = bonus_attack_declared(key)
    # p. 90's Nick: the same extra attack of p. 89, carried by the Attack action instead of
    # the Bonus Action (#320). It is `extra` for every rule that asks "is this p. 89's extra
    # attack" — the damage exception, the Multiattack tally — and differs only in the cost.
    nick = nick_attack_declared(key)
    # p. 90's Cleave: a second swing the hit opened (#323). Like Nick it is an extra
    # attack for every rule that asks — the damage exception, the Multiattack tally —
    # and unlike Nick it is not p. 89's, so it spends a cap of its own.
    cleave = cleave_attack_declared(key)
    # p. 90's Push: an ordinary attack whose hit shoves the target (#324, 0055). Its own key
    # rather than a flag on the attack's, because p. 90 says "you **can** push" — the wielder
    # chooses, and a menu is how this engine offers a choice it does not make.
    push = push_attack_declared(key)
    thrown = attack_throw_declared(key)
    swap = attack_swap_declared(key)
    # p. 177's swap keys name the same attack with one weapon moved, so the weapon and target
    # are read from them the same way (0042 clauses 1 and 3). The move itself is the ruling's
    # effect, built by `_swap_effects`.
    declared = (
        bonus
        or nick
        or cleave
        or push
        or thrown
        or (swap[:2] if swap else None)
        or attack_declared(key)
    )
    if declared is None:
        raise ValueError(
            "this declaration is not an attack: an attack names the weapon and the target "
            "in its action key, and one carrying neither has no weapon to swing. Reading "
            "either off the label would be the engine taking a mechanic from prose (R6)"
        )
    weapon_id, target_id = declared
    # p. 90: "you can throw the weapon to make a ranged attack, and **you can draw that
    # weapon as part of the attack**" — so a throw may start from a stowed weapon, and the
    # Thrown property carries its own equip rather than spending p. 177's swap.
    allowed = (Carriage.HELD, Carriage.STOWED) if thrown is not None else (Carriage.HELD,)
    for carried in actor.equipment:
        if carried.carriage in allowed and carried.item.id == weapon_id:
            assert isinstance(carried.item, Weapon)
            if (bonus or nick) and not carried.item.light:
                raise ValueError(
                    f"{weapon_id!r} is not a Light weapon, and p. 89's extra attack is bought "
                    "by one and made with another. A bonus attack with anything else is an "
                    "attack the read surface never offered"
                )
            if nick and not (carried.item.nick and weapon_id in actor.mastery_weapons):
                raise ValueError(
                    f"{weapon_id!r} does not carry p. 90's Nick for this wielder, and Nick is "
                    "what puts p. 89's extra attack inside the Attack action. Without it the "
                    "extra attack costs the Bonus Action — a mastery property is usable only "
                    "by a character who has a feature that unlocks it (p. 90, 0047)"
                )
            if thrown is not None and not carried.item.thrown:
                # p. 183: throwing a Melee weapon that lacks Thrown makes it an improvised
                # weapon dealing "1d4 damage of a type the GM thinks is appropriate" — a
                # person's judgement this engine may not invent (#264). Refused rather than
                # resolved as an ordinary throw, which would silently keep the weapon's dice.
                raise ValueError(
                    f"{weapon_id!r} does not have the Thrown property, and p. 183 makes "
                    "throwing one an improvised weapon whose damage type is the GM's to "
                    "choose. The engine has no way to supply that, so no throw is offered"
                )
            return (
                carried,
                target_id,
                bonus is not None,
                nick is not None,
                cleave is not None,
                thrown is not None,
            )
    raise ValueError(
        f"{actor.name} is not holding {weapon_id!r}. p. 177 attacks "
        '"with a weapon or an Unarmed Strike", and the read surface offers only weapons in '
        "hand — so one that reaches here is a weapon the engine never offered"
    )


def _refuse_if_behind_total_cover(
    state: EncounterState, actor: Combatant, target: Combatant
) -> None:
    """p. 179: Total Cover "can't be targeted directly" (#20).

    A refusal rather than a penalty, for the reason a shot beyond long range is refused: the
    rules forbid the attack, so a ruling for it would be an outcome for something that never
    happened. Half and Three-Quarters Cover *are* penalties (+2 and +5 to AC, p. 15), and
    this engine determines neither — the document supplies no method for measuring what
    fraction of a target is covered, so `Cover.bonus` still has no caller and says so.

    Until #20 nothing here looked at cover at all, and an arrow flew through a stone wall.
    The geometry was ready from #91 and the walls have been state since 0026; what was
    missing was anyone asking.

    An encounter tracking no positions or no obstructions cannot answer this, and lets the
    attack through rather than inventing a wall.
    """
    if actor.position is None or target.position is None or not state.obstructions:
        return
    if total_cover(actor.position, target.position, state.obstructions) is Cover.TOTAL:
        raise ValueError(
            f"{target.name} is behind Total Cover from {actor.name}, and p. 179 says Total "
            "Cover can't be targeted directly. This is a refusal rather than a penalty — "
            "the attack the rules forbid has no outcome to record"
        )


def _out_of_range(
    weapon: Weapon, actor: Combatant, target: Combatant, *, thrown: bool = False
) -> bool:
    """Whether the attack is beyond normal range, refusing one beyond long range.

    p. 90: "When attacking a target beyond normal range, you have Disadvantage on the
    attack roll. You can't attack a target beyond the long range." The second sentence is
    not a penalty, so it is refused rather than resolved — a ruling for an attack the rules
    forbid would be an outcome for something that never happened.

    A melee weapon reaches as far as its wielder does (p. 186). An encounter tracking no
    positions cannot answer the question at all, and says so rather than assuming.
    """
    if actor.position is None or target.position is None:
        return False

    # p. 90's range belongs to the *throw*, so a Melee weapon that carries one is still
    # bounded by reach when it is swung (#284). Asking the weapon alone would let a Dagger
    # stab across the room the moment it gained a Thrown range.
    if weapon.normal_range is None or (weapon.melee and not thrown):
        # p. 90's Reach property adds to the wielder's reach "when you attack with it", so
        # the bound is a fact about this weapon in this creature's hands rather than about
        # the creature alone (#316). Asking `actor.reach` directly gave a Glaive 5 feet.
        reach = weapon.reach_in_use(actor.reach)
        if not within(actor.position, target.position, reach):
            raise ValueError(
                f"{target.name} is {distance_feet(actor.position, target.position)} feet "
                f"away and {actor.name} has a reach of {reach} feet with {weapon.id}"
            )
        return False

    assert weapon.long_range is not None
    if not within(actor.position, target.position, weapon.long_range):
        raise ValueError(
            f"{target.name} is beyond the long range of {weapon.id} "
            f"({weapon.long_range} feet), and no attack may be made at all (p. 90)"
        )
    return not within(actor.position, target.position, weapon.normal_range)


def _vex_sap_and_slow(
    state: EncounterState, actor: Combatant, weapon: Weapon, target: Combatant
) -> tuple[Effect, ...]:
    """What a hit imposes, for each property the wielder may use (p. 90, #318, #319, #322).

    Both windows are measured against the **attacker's** turns — "before the end of *your*
    next turn" and "before the start of *your* next turn" — even though Sap's token belongs
    to the creature that was hit. The round it expires in is the current one plus one, which
    is what "your next turn" names whether or not the attacker has already acted this round.

    p. 90 gates every mastery property on a feature the wielder has (0047 clause 6), checked
    beside each property's own flag, which is where that clause puts it.
    """
    effects: list[Effect] = []
    unlocked = weapon.id in actor.mastery_weapons
    next_round = state.round_number + 1

    if weapon.vex and unlocked:
        effects.append(
            advantage_pending(
                PendingAdvantage(
                    holder_id=actor.id,
                    state=Advantage.ADVANTAGE,
                    rule_id=VEX_RULE_ID,
                    against_id=target.id,
                    expires_after_actor_id=actor.id,
                    expires_in_round=next_round,
                    expires_at=TurnBoundary.END,
                ),
                description=(
                    f"{weapon.id} (Vex): Advantage on {actor.name}'s next attack roll against "
                    f"{target.name}, until the end of its next turn"
                ),
                # "and deal damage to the creature" — one of the two masteries whose trigger
                # is not the bare hit (Slow below is the other; Topple and Sap fire on a hit
                # alone), and the damage is the *target's* rather than the holder's.
                when=When.DAMAGE_TAKEN,
                when_subject_id=target.id,
            )
        )
    if weapon.slow and unlocked:
        effects.append(
            speed_reduced(
                target.id,
                SpeedReduction(
                    rule_id=SLOW_RULE_ID,
                    feet=SLOW_REDUCTION_FEET,
                    expires_after_actor_id=actor.id,
                    expires_in_round=next_round,
                    expires_at=TurnBoundary.START,
                ),
                description=(
                    f"{weapon.id} (Slow): {target.name}'s Speed is reduced by "
                    f"{SLOW_REDUCTION_FEET} feet until the start of {actor.name}'s next turn"
                ),
                # "and deal damage to it", which Sap beside it does not require.
                when=When.DAMAGE_TAKEN,
                when_subject_id=target.id,
            )
        )
    if weapon.sap and unlocked:
        effects.append(
            advantage_pending(
                PendingAdvantage(
                    holder_id=target.id,
                    state=Advantage.DISADVANTAGE,
                    rule_id=SAP_RULE_ID,
                    against_id=None,
                    expires_after_actor_id=actor.id,
                    expires_in_round=next_round,
                    expires_at=TurnBoundary.START,
                ),
                description=(
                    f"{weapon.id} (Sap): Disadvantage on {target.name}'s next attack roll, "
                    f"until the start of {actor.name}'s next turn"
                ),
            )
        )
    return tuple(effects)


def _push(
    actor: Combatant, weapon: Weapon, target: Combatant, action_key: str | None
) -> tuple[Effect, ...]:
    """p. 90's Push, if the wielder may use the property and the target is small enough.

    Three gates, and each refuses rather than approximating:

    * **The property, and the feature that unlocks it** (0047 clause 6), checked together
      because p. 90 gates every mastery on both.
    * **"if it is Large or smaller"** — a size comparison, which answers `False` for a
      creature nobody sized (0051). Pushing an unsized creature would decide a rule the
      document conditions.
    * **A ray to push along.** `displaced` refuses when the two share a position or either
      has none, because "straight away from yourself" then names no direction.

    The distance comes from the key, because p. 90 says "up to 10 feet" and the wielder picks
    within it. It is bounded here as well as at the offer: a declaration is checkable input,
    and the offer is a menu rather than a promise.
    """
    feet = push_attack_feet(action_key)
    if feet is None or not weapon.push or weapon.id not in actor.mastery_weapons:
        return ()
    if feet > PUSH_MASTERY_FEET:
        raise ValueError(
            f"p. 90's Push moves a creature up to {PUSH_MASTERY_FEET} feet and this "
            f"declaration names {feet}. The maximum is the rule's, not the menu's"
        )
    if target.size is None or target.size.categories_above(Size.LARGE) > 0:
        return ()
    if actor.position is None or target.position is None:
        return ()
    displacement = displaced(target.position, anchor=actor.position, feet=feet, away=True)
    if displacement is None:
        return ()
    return (
        moved_by_force(
            target.id,
            displacement.to,
            feet=displacement.achieved_feet,
            description=(
                f"{weapon.id} (Push): {target.name} is shoved straight away from "
                f"{actor.name} — {displacement.derivation()} (p. 90)"
            ),
        ),
    )


def _topple(
    actor: Combatant, weapon: Weapon, target: Combatant, ability: int
) -> tuple[Effect, ...]:
    """The save a Topple hit compels, if the wielder may use the property (p. 90, #321).

    The DC is computed **here**, where the attack is, because both its inputs are the
    attack's: p. 89 lets a Finesse wielder choose which ability the roll used, and the
    Proficiency Bonus is the attacker's. By the time the loop rolls the save it has the
    target and nothing else.

    p. 90 gates every mastery property on a feature the wielder has (0047 clause 6), checked
    beside the property's own flag, which is where that clause puts it.
    """
    if not weapon.topple or weapon.id not in actor.mastery_weapons:
        return ()
    return (
        save_compelled(
            target.id,
            ForcedSave(
                combatant_id=target.id,
                rule_id=TOPPLE_RULE_ID,
                ability=TOPPLE_SAVE_ABILITY,
                dc=topple_save_dc(ability, actor.proficiency_bonus),
                dc_basis=topple_save_basis(weapon.ability, ability, actor.proficiency_bonus),
                label=(
                    f"makes a Constitution save or falls Prone, having been hit by "
                    f"{actor.name}'s {weapon.id} (p. 90, Topple)"
                ),
            ),
            description=(
                f"{weapon.id} (Topple): {target.name} must make a Constitution save or "
                "have the Prone condition"
            ),
        ),
    )


def _graze(actor: Combatant, weapon: Weapon, target_id: str, ability: int) -> tuple[Effect, ...]:
    """A miss that still deals the ability modifier, if the wielder may use Graze.

    **Three conditions, and the wielder's permission is the one that was missing** (0047,
    #317). p. 90 opens its Mastery Properties section by gating all eight — "usable only by a
    character who has a feature, such as Weapon Mastery, that unlocks the property for the
    character" — and this fired on `weapon.graze` alone, so any creature handed a Graze weapon
    got Graze. `mastery_weapons` is empty by default, which is also the right answer for every
    monster: p. 89 gives proficiency an explicit monster rule and p. 90 gives mastery none.

    Clamped at zero because a negative modifier would be negative damage, and the document
    gives no rule for a miss that heals. "The damage can be increased only by increasing
    the ability modifier", so nothing else may be folded in here.
    """
    if not weapon.graze or weapon.id not in actor.mastery_weapons or ability <= 0:
        return ()
    return (
        Effect(
            kind=EffectKind.DAMAGE,
            target_id=target_id,
            amount=ability,
            description=(
                f"{weapon.id} (Graze): a miss still deals {ability}, "
                "the ability modifier used for the attack roll"
            ),
            damage_type=weapon.damage_type,
        ),
    )
