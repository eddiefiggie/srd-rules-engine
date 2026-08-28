"""What is legal right now, and the token that makes the agent's claim about it checkable.

R18 gives the agent a thick read surface so it chooses from engine-supplied options
rather than recalling rules from training. R19 makes those calls idempotent,
non-mutating, and forbidden from appending to the ledger — so **there is no
server-side record of the menu the agent was shown**, and the alternatives on a
declaration are the agent's claim about what it was offered.

That is worse than a missing field. A missing field is honestly absent; an unverified
claim occupies the place where evidence should be and reads as evidence.

The read token closes that without touching R19. It carries the **state generation** the
set was derived from and a **digest of the set**, and it is derived and returned, never
stored. Recording the generation is what dissolves the ambiguity that made re-derivation
look unusable: a digest mismatch is a false claim, and an older generation is an agent
deciding from state that has since changed. Those are different problems, and neither is
ambiguous.

In a single-actor sequential loop `verified-stale` should be unreachable — nothing can
move state between a read and the declaration that follows it. That is exactly why it is
worth having. The realistic cause is an agent **caching a read across turns**, which is
plausible behaviour and otherwise entirely invisible, because a cached menu that happens
to still be correct is indistinguishable from a fresh one right up until it isn't.

**Legality has one derivation.** `legal_actions` is used here to enumerate and by
adjudication to validate, so what is offered and what is accepted cannot drift. A second
implementation would make that a property to test rather than a property to have.

A digest suffices because the agent is an LLM rather than an adversary with a debugger:
a garbled set fails the digest, an invented token fails to parse, and a replayed genuine
token fails the generation check. Only computing a valid digest for a fabricated set is
uncovered, and that is not a threat a text generator poses.

See `docs/decisions/0007-alternatives-verification.md`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType
from typing import Final

from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.canonical import CanonicalizationError, digest
from srd_rules_engine.core.conditions import Condition
from srd_rules_engine.core.d20 import Advantage
from srd_rules_engine.core.equipment import Weapon
from srd_rules_engine.core.position import MovementMode, distance_feet
from srd_rules_engine.core.reactions import SIGHT_QUALIFIER
from srd_rules_engine.core.sight import LightLevel, Senses
from srd_rules_engine.core.spellcasting import CastingTime
from srd_rules_engine.core.state import Combatant, EncounterState

#: Marks the token's encoding. An unrecognised prefix yields `unread` rather than an
#: error — 0007 already has the right verdict for "no usable token".
TOKEN_SCHEME: Final = "rt1"

#: How much of the digest a token carries. Enough that an LLM cannot hit it by accident,
#: short enough that a token stays readable in a ledger entry.
TOKEN_DIGEST_LENGTH: Final = 32

END_TURN: Final = "end-turn"

#: Attack keys are `attack:<target-id>`. The target rides in the key and in `detail`, so
#: adjudication reads it from the structure a token commits to rather than from prose.
ATTACK: Final = "attack"


#: Actions the economy can offer once an Action is available. Each is defined in the
#: Rules Glossary and implemented in `core.actions`; the eight that are not here need
#: skills, attitudes, spellcasting or reaction triggers.
DASH: Final = "dash"
DODGE: Final = "dodge"
DISENGAGE: Final = "disengage"


def attack_key(weapon_id: str, target_id: str) -> str:
    """The key one attack option is offered under (0040 clause 3).

    **One per (held weapon, reachable target)**, because which weapon an attack uses is a
    choice the creature makes from what it holds — enumerated the way 0038 clause 4 enumerates
    a spell's payable slot levels, so it is picked from a menu the engine computed rather than
    named in a declaration the engine checks afterwards.

    It named only the target until #258, when a weapon stopped being data bound to a resolver
    and became something the creature holds.
    """
    return f"{ATTACK}:{weapon_id}:{target_id}"


BONUS_ATTACK: Final = "bonus-attack"


def bonus_attack_key(weapon_id: str, target_id: str) -> str:
    """The key p. 89's extra Light-weapon attack is offered under.

    Its own prefix rather than an ordinary attack key, because the two differ in what they
    cost and in what they deal: this one spends the **Bonus Action**, and drops a positive
    ability modifier from its damage. A resolver deriving which it was from the action economy
    would be reading a consequence to recover a choice the engine already made.
    """
    return f"{BONUS_ATTACK}:{weapon_id}:{target_id}"


def bonus_attack_declared(action_key: str | None) -> tuple[str, str] | None:
    """The weapon and target a bonus-attack key names, or `None` if it is not one."""
    if action_key is None or not action_key.startswith(f"{BONUS_ATTACK}:"):
        return None
    weapon_id, _, target_id = action_key[len(BONUS_ATTACK) + 1 :].rpartition(":")
    if not weapon_id or not target_id:
        return None
    return weapon_id, target_id


def attack_declared(action_key: str | None) -> tuple[str, str] | None:
    """The weapon and the target an attack key names, or `None` if it is not an attack.

    Parsed from the right, because a weapon's id may itself contain colons — `fixture:blade`
    is an ordinary id — while a combatant id is one segment.
    """
    if action_key is None or not action_key.startswith(f"{ATTACK}:"):
        return None
    weapon_id, _, target_id = action_key[len(ATTACK) + 1 :].rpartition(":")
    if not weapon_id or not target_id:
        return None
    return weapon_id, target_id


def attack_weapon(action_key: str | None) -> str | None:
    """The weapon an attack key names, or `None` if the key is not an attack."""
    declared = attack_declared(action_key)
    return declared[0] if declared else None


#: Which action each casting time spends (p. 105, p. 185). Stated here rather than imported
#: from `core.casting`, which imports state and so cannot be imported back — and `core.casting`
#: reads it from here, so the two cannot disagree about what a Bonus Action spell costs.
ACTION_FOR_CASTING: Final[Mapping[CastingTime, ActionKind]] = MappingProxyType(
    {
        CastingTime.ACTION: ActionKind.ACTION,
        CastingTime.BONUS_ACTION: ActionKind.BONUS_ACTION,
        CastingTime.REACTION: ActionKind.REACTION,
    }
)

#: p. 190's Unarmed Strike, as both the rule id and the "weapon" segment of the action key —
#: because p. 177 makes it one of the Attack action's two options rather than a separate act:
#: "you can make one attack roll **with a weapon or an Unarmed Strike**".
UNARMED_STRIKE_ID: Final = "unarmed-strike"

#: p. 190: "a target **within 5 feet of you**". Stated by the entry rather than taken from the
#: creature's reach, and p. 186 defers to it — "A creature has a reach of 5 feet **unless a
#: rule says otherwise**", and this rule says otherwise by naming its own distance.
UNARMED_REACH_FEET: Final = 5

CAST: Final = "cast"


#: The modes Dash offers a choice between (p. 180): "If you have a **special speed**, such as
#: a Fly Speed or Swim Speed, you can use that speed instead of your Speed."
#:
#: **Crawling is excluded, and it is the one that would slip in.** `Speeds.for_mode` answers
#: Speed for it, because p. 179 makes crawling an ordinary move that costs more rather than a
#: speed of its own — so iterating `MovementMode` offers a "Dash (crawl)" the document does
#: not describe, at a number that is just Speed again.
DASHABLE_MODES: Final = (
    MovementMode.WALK,
    MovementMode.CLIMB,
    MovementMode.SWIM,
    MovementMode.FLY,
    MovementMode.BURROW,
)


def dash_key(mode: MovementMode) -> str:
    """The key one Dash option is offered under (p. 180).

    One per speed the creature actually has, because p. 180 gives it the choice: "If you have
    a special speed, such as a Fly Speed or Swim Speed, you can use that speed instead of your
    Speed… **You choose which speed to use each time you take it**." A single Walk-only offer
    would make that choice for the creature.
    """
    return f"{DASH}:{mode.value}"


def dash_mode(action_key: str | None) -> MovementMode | None:
    """The speed a Dash key names, or `None` if the key is not a Dash."""
    if action_key is None or not action_key.startswith(f"{DASH}:"):
        return None
    try:
        return MovementMode(action_key[len(DASH) + 1 :])
    except ValueError:
        return None


def cast_key(rule_id: str, slot_level: int) -> str:
    """The key one castable option is offered under (0038 clause 4).

    One per **payable slot level**, not one per spell: `SpellSlots.payable_by` already
    computes which levels can pay, so the level is chosen from a menu the engine derived
    rather than supplied as a number the engine has to trust. Level 0 means no slot, which is
    p. 104's cantrip and not a slot of no size.
    """
    return f"{CAST}:{rule_id}:{slot_level}"


def cast_declared(action_key: str | None) -> tuple[str, int] | None:
    """The spell and the slot level a cast key names, or `None` if it is not a cast.

    Parsed from the right, because a rule id may itself contain colons — `spell:bless` is a
    perfectly ordinary id and splitting from the left would take `spell` as the whole of it.
    """
    if action_key is None or not action_key.startswith(f"{CAST}:"):
        return None
    body = action_key[len(CAST) + 1 :]
    rule_id, _, level = body.rpartition(":")
    if not rule_id or not level.isdigit():
        return None
    return rule_id, int(level)


def attack_target(action_key: str | None) -> str | None:
    """The target an attack key names, or `None` if the key is not an attack."""
    declared = attack_declared(action_key)
    return declared[1] if declared else None


class Verdict(StrEnum):
    """What the engine can say about an alternatives claim."""

    FRESH = "verified-fresh"
    STALE = "verified-stale"
    UNVERIFIED = "unverified"
    UNREAD = "unread"


@dataclass(frozen=True)
class LegalAction:
    """One enumerated option. `key` and `detail` are matched on; `label` never is."""

    key: str
    label: str
    detail: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "detail", MappingProxyType(dict(self.detail)))

    def identity(self) -> Mapping[str, object]:
        """The part of an action a token commits to — structure, never prose.

        The label is excluded for the same reason the trigger matcher never sees the
        declaration's free-text label: the moment prose enters a comparison, wording
        starts changing outcomes.
        """
        return {"key": self.key, "detail": dict(self.detail)}


@dataclass(frozen=True)
class Situation:
    """The actor's own state, in typed values (R18).

    R18 asks for "active conditions **with their mechanical effects**", because a name
    alone puts the agent back to recalling 5e from training. So every field here is a value
    the agent can act on rather than a label it has to interpret, and nothing is prose.

    Not covered by the read token, and deliberately. The token commits to the *offered set*
    — the alternatives a declaration claims it was shown (decision 0007). A situation is
    not a menu. Staleness is still caught, because it is derived from the same generation
    the token carries, so a stale read fails the generation check either way.
    """

    hit_points: int
    max_hit_points: int
    #: Held conditions, with implication already resolved.
    conditions: tuple[Condition, ...]
    #: How long each held condition lasts, as the engine computed it when the condition was
    #: applied (#18). A condition missing from this map has no span the engine can count,
    #: and `conditions_until_removed` names it — R18 asks for mechanical effects rather than
    #: labels, and "how long" is one of them.
    condition_durations: Mapping[Condition, str]
    #: Held conditions nothing in this engine will retire on its own (0021 clause 6). Named
    #: rather than left to look permanent, the same disclosure `unenforced_clauses` makes.
    conditions_until_removed: tuple[Condition, ...]
    #: Conditions that repeat a save at the end of this creature's turns (p. 63), as
    #: condition to the ability and DC. Reported, never rolled here — a save is an outcome
    #: and R1 leaves outcomes to adjudication.
    saves_due: Mapping[Condition, tuple[str, int]]
    #: What an attack against this creature has, before the attacker's own state.
    attack_rolls_against_you: Advantage
    #: What this creature's attacks have, before the target is known — Grappled's
    #: "any target other than the grappler" cannot be answered without one.
    your_attack_rolls: Advantage
    cannot_act: bool
    speed: int
    movement_remaining: int
    #: How much farther this creature may move in each mode it *can* use (p. 188, #206).
    #: One shared spend, a different number per mode: a creature with a Speed of 30 and a
    #: Fly Speed of 40 that has flown 10 feet has 20 feet of walking left and 30 of flying.
    #: `movement_remaining` above is this map's walking entry, kept because it is the
    #: number for a creature with no special speed at all — which is most of them.
    #:
    #: A mode the creature cannot use is **absent** rather than 0. Flying and burrowing are
    #: granted only by the speed itself (pp. 178, 182), and "no flight" is a different fact
    #: from "no flight left" — the agent that reads a 0 here would be told the creature had
    #: run out of something it never had.
    movement_remaining_by_mode: Mapping[MovementMode, int]
    action_available: bool
    bonus_action_available: bool
    reaction_available: bool
    #: Level to slots remaining. Empty for a creature with no spellcasting.
    spell_slots: Mapping[int, int]
    #: What this creature is concentrating on, or `None` (p. 179). A typed value, not prose:
    #: it is the effect's id as the caster's declaration named it, which is what an agent
    #: needs to decide whether casting again is worth losing.
    #:
    #: Reported, never ended here. p. 179's damage save is an outcome and R1 leaves outcomes
    #: to adjudication — the same line `saves_due` above draws, and for the same reason.
    concentrating_on: str | None
    #: How many hands are free (p. 105, p. 90), or `None` because **no SRD rule says how many
    #: a creature has** — see `Combatant.hands`. An agent deciding whether it can cast a spell
    #: with Somatic or Material components needs this, and `None` means the question cannot be
    #: answered rather than that the answer is zero.
    #:
    #: **One free hand serves Somatic and Material together** (p. 105), so an agent reading 1
    #: here is not short of a hand for an S,M spell. The count is reported; the rule that
    #: consumes it is #245.
    free_hands: int | None
    #: What the creature is carrying, in pounds (p. 178). Reported without a verdict, because
    #: whether it is too much needs the creature `Size` p. 178's table is keyed on and this
    #: engine has none (#259).
    carried_weight: float
    #: Elapsed campaign time in minutes (decision 0020). Ordinal `round_number` is not
    #: reported here and does not convert into it — p. 13 says a round represents *about*
    #: 6 seconds, which is the document declining an exact conversion.
    elapsed_minutes: int
    #: Minutes until a Stable creature regains 1 hit point (p. 18), or `None` when it is
    #: not Stable. Reported so the agent can narrate toward it; the outcome is still the
    #: engine's, applied by `EncounterState.with_time_passed`.
    minutes_until_recovery: int | None
    #: Rules the engine holds but does not enforce, named rather than left to discovery.
    #: The light where this creature is standing, or `None` when nobody has stated one or
    #: the encounter tracks no positions (0025 clause 7). Reported rather than resolved:
    #: what the level *means* for this creature is the table #150 has not filled, so the
    #: surface states the input and declines the conclusion.
    light_level: LightLevel | None
    #: This creature's special senses, as ranges in feet. Reported for the same reason and
    #: with the same limit — a range the engine cannot yet apply is still a fact the agent
    #: is entitled to know it has.
    senses: Senses
    unenforced_clauses: tuple[str, ...]


@dataclass(frozen=True)
class ReadResult:
    """What a read-surface call returns: the offered set, and the token committing to it."""

    actor_id: str
    generation: int
    actions: tuple[LegalAction, ...]
    token: str
    situation: Situation | None = None

    @property
    def keys(self) -> tuple[str, ...]:
        return tuple(action.key for action in self.actions)


def legal_actions(state: EncounterState, actor_id: str) -> tuple[LegalAction, ...]:
    """The single derivation of what is legal, shared with adjudication.

    M1 derives only what the state alone settles: ending the turn, and an attack against
    each opponent still standing. Movement, spells, and conditions arrive with the units
    that implement them — this is the seam they extend, not a placeholder for them.

    Attacks are enumerated here rather than in `core.combat` because legality has one
    derivation: this function both offers the set and validates against it, so a second
    enumeration living beside combat would make agreement a property to test rather than
    a property to have. What an attack *does* is combat's business; that one is on the
    menu is the state's.
    """
    if not state.has(actor_id):
        raise KeyError(f"no combatant {actor_id!r} in this encounter")

    actor = state.combatant(actor_id)
    if actor.is_down:
        return ()
    if state.in_combat and not state.is_active(actor_id):
        return ()

    actions: list[LegalAction] = []
    if state.in_combat:
        actions.append(
            LegalAction(
                key=END_TURN,
                label="End your turn",
                detail={"round": state.round_number},
            )
        )

    # p. 184: "You can't take any action, Bonus Action, or Reaction." Ending the turn
    # survives, because a creature that can do nothing must still be able to stop —
    # offering nothing at all would strand the loop with no legal answer.
    if actor.conditions.cannot_act():
        return tuple(actions)

    has_action = actor.actions.available(ActionKind.ACTION, actor.conditions)

    # p. 176: "On your turn, you can take one action", and p. 177 makes an attack one — so an
    # attack leaves the menu once the Action is gone. It did not until #252, because nothing
    # charged the Action for an attack and the offer had nothing to be conditional on.
    if has_action:
        actions.extend(_attackable(state, actor))

    # p. 89's extra Light attack is made **as a Bonus Action**, so it is offered outside the
    # `has_action` branch — by the time it is available the Action has already been spent
    # buying it, which is the whole condition. Nesting it inside cost nothing to write and
    # made it unreachable.
    actions.extend(_light_bonus_attacks(state, actor))

    actions.extend(_castable(state, actor))

    if has_action:
        speed = actor.conditions.speed_after(actor.speeds.walk)
        # p. 180's choice of speed, enumerated rather than assumed — one entry per speed the
        # creature has, so the choice is the creature's and the number is the engine's.
        speeds = actor.conditions.speeds_after(actor.speeds)
        actions.extend(
            LegalAction(
                key=dash_key(mode),
                label=f"Dash ({mode.value})" if mode is not MovementMode.WALK else "Dash",
                detail={"extra_movement": feet, "mode": mode.value},
            )
            for mode in DASHABLE_MODES
            if (feet := speeds.for_mode(mode)) is not None
        )
        actions.append(LegalAction(key=DODGE, label="Dodge", detail={"holds": speed > 0}))
        actions.append(LegalAction(key=DISENGAGE, label="Disengage", detail={}))

    return tuple(actions)


def _castable(state: EncounterState, actor: Combatant) -> tuple[LegalAction, ...]:
    """Every spell this creature may cast right now, one entry per payable slot level.

    R18 asks for the legality question to be **computable**, not checkable after the fact, so
    three rules are asked here rather than left to fail at adjudication:

    * **The action the casting time costs is still available** (p. 105, p. 185). A spell that
      needs the Magic action is not castable once the Action is spent.
    * **A slot can pay** (p. 104). `SpellSlots.payable_by` computes which levels can, and each
      one is its own entry — so the level is picked from a menu rather than supplied.
    * **p. 105's one slot per turn.** "On a turn, you can expend only one spell slot to cast a
      spell." Once one has gone, levelled spells drop off the menu and **cantrips do not**,
      because p. 104 puts a level 0 spell outside the slot economy entirely.

    What is **not** asked is components and armour training, which this engine cannot check.
    `core.casting` discloses that in full: an offer here means castable as far as this engine
    can tell, which is not the same as castable.
    """
    offered: list[LegalAction] = []
    spent_a_slot = actor.id in state.slots_expended_this_turn

    for spell in actor.spells:
        kind = ACTION_FOR_CASTING.get(spell.casting_time)
        if kind is None or not actor.actions.available(kind, actor.conditions):
            continue

        if spell.is_cantrip:
            levels: tuple[int, ...] = (0,)
        elif spent_a_slot or actor.slots is None:
            continue
        else:
            levels = actor.slots.payable_by(spell.level)

        offered.extend(
            LegalAction(
                key=cast_key(spell.rule_id, level),
                label=f"Cast {spell.rule_id}" + (f" at level {level}" if level else ""),
                detail={
                    "spell_level": spell.level,
                    "slot_level": level,
                    "casting_time": str(spell.casting_time),
                    "concentration": spell.requires_concentration,
                },
            )
            for level in levels
        )
    return tuple(offered)


def _attackable(state: EncounterState, actor: Combatant) -> tuple[LegalAction, ...]:
    """Every attack this creature may make right now, one per held weapon and target.

    **This used to report the distance and decline to judge**, and said so:

        Whether a target is in range depends on the *weapon* … and the read surface does not
        know which weapon an attack will use. So it supplies the fact and leaves the
        judgement, rather than filtering on an assumption.

    That was honest and it is no longer true. Since #258 a weapon is an `Item` the creature
    holds (0040 clause 1), so the surface knows exactly which weapon each offer is for and
    R18's "computable rather than checkable afterwards" applies to range as it does to
    everything else. A menu that knows an attack is impossible and offers it anyway is a menu
    that lies.

    **A shot beyond normal range stays on the menu.** p. 90 imposes Disadvantage past the
    first range and forbids the attack only past the second, so filtering at normal range
    would remove a shot the document allows. The Disadvantage is the resolver's to apply.

    **Unknown positions offer the attack.** A creature with no position cannot be measured
    against, and refusing on that basis would invent a distance — the direction 0030 clause 1
    keeps away from.

    **A creature holding no weapon is offered no attack, and that is a disclosed gap** (R32).
    p. 177 allows "one attack roll with a weapon **or an Unarmed Strike**", and the Unarmed
    Strike (p. 190) is an unimplemented shape — so this offers the weapon half of the sentence
    and none of the other. Before #258 the single `attack:<target>` offer covered an unarmed
    creature by accident, because the surface could not consult a weapon; now the narrowing is
    visible in play, and it is filed as
    [#267](https://github.com/eddiefiggie/srd-rules-engine/issues/267) rather than left for a
    reader to infer from an empty menu that a creature can do nothing.
    """
    offered: list[LegalAction] = []

    # p. 177: "one attack roll **with a weapon or an Unarmed Strike**". The second half was
    # missing until #267 — offering per held weapon offered only the first, so a creature that
    # dropped its sword was offered nothing at all. p. 190 puts the strike at 5 feet, stated
    # by its own entry rather than taken from the creature's reach (p. 186 defers: "unless a
    # rule says otherwise").
    for target in state.combatants:
        if target.id == actor.id or target.is_down:
            continue
        if not _within(actor, target, UNARMED_REACH_FEET):
            continue
        offered.append(
            LegalAction(
                key=attack_key(UNARMED_STRIKE_ID, target.id),
                label=f"Unarmed Strike against {target.name}",
                detail={
                    "target": target.id,
                    "weapon": UNARMED_STRIKE_ID,
                    "armour_class": target.armour_class,
                },
            )
        )

    for weapon in actor.weapons_held:
        for target in state.combatants:
            if target.id == actor.id or target.is_down:
                continue
            if not _within_weapon_range(actor, weapon, target):
                continue
            offered.append(
                LegalAction(
                    key=attack_key(weapon.id, target.id),
                    label=f"Attack {target.name} with {weapon.id}",
                    detail=_attack_detail(actor, weapon, target),
                )
            )

    return tuple(offered)


def _light_bonus_attacks(state: EncounterState, actor: Combatant) -> tuple[LegalAction, ...]:
    """p. 89's extra attack, offered only when all of its conditions hold.

    > When you take the Attack action on your turn **and attack with a Light weapon**, you can
    > make one extra attack as a Bonus Action later on the same turn. That extra attack must
    > be made with a **different** Light weapon.

    Four conditions, and each is asked here rather than left to fail at adjudication (R18):
    the Attack action was taken this turn with a Light weapon, a Bonus Action is available,
    the creature is holding a *different* Light weapon, and the target is in its range.

    **"Different" means a different weapon, not a different kind.** p. 89's own example is a
    Shortsword in one hand and a Dagger in the other — two things held at once — so the test
    is the item's identity, which is what `Carried` already distinguishes.
    """
    used = {weapon for who, weapon in state.light_attacks_this_turn if who == actor.id}
    if not used:
        return ()
    if not actor.actions.available(ActionKind.BONUS_ACTION, actor.conditions):
        return ()

    offered: list[LegalAction] = []
    for weapon in actor.weapons_held:
        if not weapon.light or weapon.id in used:
            continue
        for target in state.combatants:
            if target.id == actor.id or target.is_down:
                continue
            if not _within_weapon_range(actor, weapon, target):
                continue
            offered.append(
                LegalAction(
                    key=bonus_attack_key(weapon.id, target.id),
                    label=f"Bonus attack on {target.name} with {weapon.id}",
                    detail={
                        **_attack_detail(actor, weapon, target),
                        # p. 89 drops the ability modifier from this attack's damage unless it
                        # is negative, which an agent weighing the extra attack needs to know.
                        "ability_modifier_on_damage": min(0, actor.modifier(weapon.ability)),
                    },
                )
            )
    return tuple(offered)


def _within(actor: Combatant, target: Combatant, feet: int) -> bool:
    """Whether the target is within that many feet, offering the attack when it cannot be
    measured — refusing on an unmeasurable distance would invent one (0030 clause 1)."""
    if actor.position is None or target.position is None:
        return True
    return bool(distance_feet(actor.position, target.position) <= feet)


def _within_weapon_range(actor: Combatant, weapon: Weapon, target: Combatant) -> bool:
    """Whether this weapon can reach that target at all (p. 90, p. 186).

    "Can reach at all" rather than "reaches without penalty": long range is the bound, and the
    Disadvantage inside it is a modifier rather than a refusal.
    """
    if actor.position is None or target.position is None:
        return True
    distance = distance_feet(actor.position, target.position)
    if weapon.long_range is not None:
        return bool(distance <= weapon.long_range)
    return bool(distance <= actor.reach)


def _attack_detail(actor: Combatant, weapon: Weapon, target: Combatant) -> dict[str, object]:
    """What the agent needs to judge an attack it has already been told is possible."""
    detail: dict[str, object] = {
        "target": target.id,
        "weapon": weapon.id,
        "armour_class": target.armour_class,
    }
    if actor.position is not None and target.position is not None:
        distance = distance_feet(actor.position, target.position)
        detail["distance"] = distance
        detail["reach"] = actor.reach
        # p. 90: "When attacking a target beyond normal range, you have Disadvantage on the
        # attack roll." Reported so the agent can weigh the shot it is being offered.
        if weapon.normal_range is not None:
            detail["beyond_normal_range"] = distance > weapon.normal_range
    return detail


def read(state: EncounterState, actor_id: str) -> ReadResult:
    """Answer what is legal for an actor right now. Mutates nothing, records nothing."""
    actions = legal_actions(state, actor_id)
    return ReadResult(
        actor_id=actor_id,
        generation=state.generation,
        actions=actions,
        token=issue_token(state.generation, actions),
        situation=situation(state, actor_id),
    )


def situation(state: EncounterState, actor_id: str) -> Situation:
    """The actor's own state, with every condition's effects already resolved (R18).

    Everything here is derived, never stored, and the call mutates nothing (R19). The
    aggregates are what the agent needs to *decide* with: it should not have to know that
    Unconscious implies Prone, or that Prone's effect on incoming attacks depends on the
    attacker's distance, in order to read what its own attacks currently have.

    `your_attack_rolls` is reported without a target, so Grappled's "any target other than
    the grappler" is not folded in — that question needs a target and is answered when one
    is named. Reporting the unconditional part is honest; guessing a target would not be.
    """
    actor = state.combatant(actor_id)
    conditions = actor.conditions
    speed = conditions.speed_after(actor.speeds.walk)

    unenforced = list(conditions.unenforced_clauses())
    unenforced.extend(c for c in actor.actions.unenforced_clauses() if c not in unenforced)
    # A creature holding a Reaction is a creature the engine cannot tell when to spend it:
    # p. 185's Opportunity Attack fires on a mover "that you can see", and sight is the
    # mapping #150 has not filled. Disclosed here rather than left for a reader to notice
    # that no reaction has ever been offered.
    if actor.actions.available(ActionKind.REACTION, conditions):
        unenforced.append(SIGHT_QUALIFIER)

    return Situation(
        hit_points=actor.hit_points,
        max_hit_points=actor.max_hit_points,
        conditions=tuple(sorted(conditions.held, key=lambda c: c.value)),
        condition_durations=MappingProxyType(
            {c: d.derivation() for c, d in conditions.durations.items()}
        ),
        conditions_until_removed=conditions.unretirable(),
        saves_due=MappingProxyType(
            {c: (s.ability, s.dc) for c, s in conditions.saves_due_after(actor_id).items()}
        ),
        attack_rolls_against_you=conditions.attack_rolls_against(attacker=None, target=None),
        your_attack_rolls=conditions.own_attack_rolls(),
        cannot_act=conditions.cannot_act(),
        speed=speed,
        movement_remaining=actor.movement_remaining,
        movement_remaining_by_mode=MappingProxyType(
            {
                mode: remaining
                for mode in MovementMode
                if (remaining := actor.movement_remaining_in(mode)) is not None
            }
        ),
        action_available=actor.actions.available(ActionKind.ACTION, conditions),
        bonus_action_available=actor.actions.available(ActionKind.BONUS_ACTION, conditions),
        reaction_available=actor.actions.available(ActionKind.REACTION, conditions),
        spell_slots=MappingProxyType(
            {level: actor.slots.remaining(level) for level in sorted(actor.slots.total)}
            if actor.slots is not None
            else {}
        ),
        # The stored value, which since #238 is the only answer there is. This derived it
        # through `Concentration.after_conditions` — because nothing wrote the field when a
        # condition landed, and a raw read would have said a spell was still up after the
        # condition that broke it. The derivation covered that direction and could not cover
        # the other: p. 179 *ends* Concentration, so the spell must not return when the
        # condition lifts. `Combatant.__post_init__` now spends it where the event happens
        # (0037 clause 4), which leaves this a plain read and still no mutation (R19).
        concentrating_on=actor.concentration.rule_id,
        free_hands=actor.free_hands,
        carried_weight=actor.carried_weight,
        elapsed_minutes=state.clock.elapsed_minutes,
        minutes_until_recovery=(
            max(0, actor.death_saves.recovers_at_minute - state.clock.elapsed_minutes)
            if actor.death_saves.recovers_at_minute is not None
            else None
        ),
        light_level=(
            state.lighting.level_at(actor.position) if actor.position is not None else None
        ),
        senses=actor.senses,
        unenforced_clauses=tuple(unenforced),
    )


def issue_token(generation: int, actions: Sequence[LegalAction]) -> str:
    """Derive the token for an offered set. Never stored — the digest is the record."""
    body = digest({"actions": [action.identity() for action in actions]})
    return f"{TOKEN_SCHEME}.{generation}.{body[:TOKEN_DIGEST_LENGTH]}"


def verify(token: str | None, claimed: Sequence[LegalAction], current_generation: int) -> Verdict:
    """Judge an alternatives claim against the token it was issued with.

    Never raises and never blocks adjudication: the alternatives are metadata about a
    decision, not the decision, and R3 validates the named test independently. A false
    claim makes the *record* wrong, which is reported rather than refused.
    """
    parsed = _parse(token)
    if parsed is None:
        return Verdict.UNREAD

    generation, body = parsed
    try:
        expected = digest({"actions": [action.identity() for action in claimed]})
    except CanonicalizationError:
        return Verdict.UNVERIFIED

    if expected[:TOKEN_DIGEST_LENGTH] != body:
        return Verdict.UNVERIFIED
    if generation > current_generation:
        # A token from a generation that has not happened cannot be genuine.
        return Verdict.UNVERIFIED
    return Verdict.FRESH if generation == current_generation else Verdict.STALE


def _parse(token: str | None) -> tuple[int, str] | None:
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != TOKEN_SCHEME:
        return None
    generation, body = parts[1], parts[2]
    if not generation.isdigit() or not body:
        return None
    return int(generation), body
