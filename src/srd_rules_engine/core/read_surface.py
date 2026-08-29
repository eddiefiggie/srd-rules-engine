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
from srd_rules_engine.core.equipment import (
    Carriage,
    Item,
    Weapon,
    reachable_objects,
    unplaced_objects,
)
from srd_rules_engine.core.position import MovementMode, distance_feet
from srd_rules_engine.core.reactions import SIGHT_QUALIFIER
from srd_rules_engine.core.sight import LightLevel, Senses
from srd_rules_engine.core.spellcasting import CastingTime, component_refusal
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


#: 0045 clause 1. One object interaction a turn is the **engine's** cap, taken as the
#: intersection of two readings the document does not choose between — p. 13's per-turn free
#: interaction and p. 177's per-attack swap. Named rather than left to look like a printed rule
#: an agent could cite.
#:
#: It replaces `free-object-interaction-unmodelled` and `one-swap-per-turn-is-the-engines-cap`,
#: which disclosed the two halves of a silence that is now decided (0042 clause 6, 0043
#: clause 3). The three moved together, which is
#: [#292](https://github.com/eddiefiggie/srd-rules-engine/issues/292)'s point.
OBJECT_INTERACTION_CAP: Final = "one-object-interaction-a-turn-is-the-engines-cap"

#: 0045 clause 5. p. 14 lets the GM escalate an otherwise-free interaction to an action, and
#: p. 177's *Breaking Objects* lets one be broken with Attack or Utilize. Both are a person's
#: judgement, and the engine models neither the objects nor the escalation — so the Utilize
#: offered here reaches the four moves the engine has and nothing else.
UTILIZE_REACHES_FOUR_MOVES: Final = "utilize-reaches-only-the-engines-object-moves"

#: p. 105 refuses a Verbal component to "a creature who is gagged or in an area of magical
#: silence", and the engine models neither (#246). A spell carrying one is offered anyway, so
#: the rule that went unchecked is named rather than inferred from a silent pass.
VERBAL_UNCHECKED: Final = "verbal-component-gagged-or-silenced-unchecked"

#: A standalone object interaction — p. 13's free one — and the Utilize action that buys
#: another (p. 13, p. 191, 0045 clauses 2-3).
INTERACT: Final = "interact"
UTILIZE: Final = "utilize"

#: The three moves an interaction may be. `EQUIP` covers both of p. 177's sources, drawing
#: from stowed and picking up, because which one applies is a fact about where the item is
#: rather than a choice the creature makes.
VERB_EQUIP: Final = "equip"
VERB_STOW: Final = "stow"
VERB_DROP: Final = "drop"

#: An attack that also equips or unequips one weapon (p. 177, 0042 clauses 1-3).
#:
#: **Three prefixes for p. 177's three destinations**, not two. "Equipping a weapon includes
#: drawing it from a sheath or picking it up. Unequipping a weapon includes sheathing,
#: stowing, or dropping it." Sheathing and stowing are one shape — the item stays with the
#: creature and changes carriage — while dropping crosses the creature's boundary and is
#: 0041's detachment. Collapsing the last two would give two offers one key.
ATTACK_EQUIP: Final = "attack-equip"
ATTACK_STOW: Final = "attack-stow"
ATTACK_DROP: Final = "attack-drop"

#: The prefix for each destination, and the destination for each prefix.
SWAP_PREFIXES: Final = (ATTACK_EQUIP, ATTACK_STOW, ATTACK_DROP)


def _escape(segment: str) -> str:
    """Make one id safe to sit in a colon-delimited key.

    `attack_declared` parses from the right because a weapon id may itself contain colons
    while a combatant id is one segment — which works for exactly one multi-segment field.
    A swap key carries **two** item ids, so the position of the boundary stops being
    recoverable and the parse has to stop guessing at it.

    Percent-escaping is used rather than forbidding a character in `Item.id`, because a
    constraint on ruleset ids would be this engine's encoding leaking into a ruleset's
    vocabulary — and 0039 clause 2 keeps `Item` to facts the document states. `%` first, or
    unescaping an id that legitimately contains `%3A` would produce a colon nobody wrote.
    """
    return segment.replace("%", "%25").replace(":", "%3A")


def _unescape(segment: str) -> str:
    """Invert `_escape`. `%25` last, for the reason `%` is escaped first."""
    return segment.replace("%3A", ":").replace("%25", "%")


def attack_swap_key(weapon_id: str, target_id: str, item_id: str, *, swap: str) -> str:
    """The key for an attack that also swaps one weapon (0042 clause 3).

    One offer per (attack, item), enumerated the way 0038 clause 4 enumerates a spell's
    payable slot levels — so the swap is chosen from a menu the engine computed rather than
    named in a declaration the engine validates afterwards.

    **No ordering segment**, and that is 0042 clause 2: p. 177's "before or after" decides
    only whether the newly equipped weapon is available to *this* attack, and the pair
    `(weapon_id, item_id)` already says so — they are equal when it was equipped and used.
    """
    if swap not in SWAP_PREFIXES:
        raise ValueError(f"{swap!r} is not one of p. 177's three destinations: {SWAP_PREFIXES}")
    return f"{swap}:{_escape(weapon_id)}:{_escape(target_id)}:{_escape(item_id)}"


def attack_swap_declared(action_key: str | None) -> tuple[str, str, str, str] | None:
    """`(weapon_id, target_id, item_id, swap)` a swap key names, or `None`.

    Every segment is escaped, so this splits on colons without guessing where an id ends —
    the ambiguity that made the plain attack key's right-partition parse unextendable.
    """
    if action_key is None:
        return None
    for prefix in SWAP_PREFIXES:
        if not action_key.startswith(f"{prefix}:"):
            continue
        parts = action_key[len(prefix) + 1 :].split(":")
        if len(parts) != 3 or not all(parts):
            return None
        weapon_id, target_id, item_id = (_unescape(part) for part in parts)
        return weapon_id, target_id, item_id, prefix
    return None


#: A weapon thrown to make a ranged attack (p. 90, #284). Its own prefix rather than an
#: ordinary attack key, because the two differ in what bounds them and in what they leave
#: behind: this one is bounded by the weapon's range rather than the wielder's reach, and the
#: weapon ends the attack out of the creature's hands.
ATTACK_THROW: Final = "attack-throw"


def attack_throw_key(weapon_id: str, target_id: str) -> str:
    """The key one throw is offered under (p. 90, 0042 clause 3's enumeration)."""
    return f"{ATTACK_THROW}:{weapon_id}:{target_id}"


def attack_throw_declared(action_key: str | None) -> tuple[str, str] | None:
    """The weapon and target a throw key names, or `None` if it is not one.

    Parsed from the right for `attack_declared`'s reason: a weapon id may contain colons
    while a combatant id is one segment. A throw carries no second item id, so it needs none
    of the escaping p. 177's swap keys do.
    """
    if action_key is None or not action_key.startswith(f"{ATTACK_THROW}:"):
        return None
    weapon_id, _, target_id = action_key[len(ATTACK_THROW) + 1 :].rpartition(":")
    if not weapon_id or not target_id:
        return None
    return weapon_id, target_id


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
    #: Item ids of detached objects within this creature's reach (0041 clauses 3 and 4), or
    #: `None` when the creature has no position and no distance is computable. `None` is a
    #: refusal rather than "none in reach" — an encounter tracking no positions cannot answer
    #: the question, and an empty tuple would say it had.
    reachable_objects: tuple[str, ...] | None
    #: Item ids of detached objects **no rule has placed** (R32). Reported beside the list
    #: above because an object missing from it for want of a stated position and one missing
    #: because it is genuinely far away are different answers, and an empty reachable list
    #: renders them identical.
    #:
    #: Five printed rules detach an item and none says where it lands (0041 clause 4), so
    #: this is the ordinary case rather than an error: a ruleset that states where the sword
    #: fell moves an entry from here to there.
    unplaced_objects: tuple[str, ...]
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
    # p. 257: "Some creatures can make more than one attack **when they take the Attack
    # action**", so the Action buys several rolls and the attack stays on the menu while any
    # remain. A creature with no Multiattack has exactly one, which is the pre-existing
    # behaviour written as a special case of the general one (0043 clause 1).
    # **And only once the Action went to the Attack action.** `attacks_remaining` alone says
    # a creature that spent its Action on Dodge may still attack, because it counts rolls
    # rather than asking what the Action bought. Having already made one this turn is what
    # says the Action was spent here.
    mid_multiattack = bool(
        state.attacks_this_turn.get(actor.id, 0) and state.attacks_remaining(actor.id)
    )
    if has_action or mid_multiattack:
        actions.extend(_attackable(state, actor))

    # p. 89's extra Light attack is made **as a Bonus Action**, so it is offered outside the
    # `has_action` branch — by the time it is available the Action has already been spent
    # buying it, which is the whole condition. Nesting it inside cost nothing to write and
    # made it unreachable.
    actions.extend(_light_bonus_attacks(state, actor))

    actions.extend(_castable(state, actor))
    # p. 13's free interaction, and p. 191's action for a second. Outside the `has_action`
    # branch because the free one costs no action at all (0045 clauses 1 and 3).
    actions.extend(_interactions(state, actor))

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

    * **The components can be provided** (p. 105, #245), which was the fourth thing this
      surface could not ask until an equipment model existed. `component_refusal` computes it
      from the caster's hands and what it holds; a spell whose components cannot be provided
      is not offered, and the reason is p. 105's own sentence.

    What is **still** not asked is Verbal and armour training. p. 105 refuses a Verbal
    component to "a creature who is gagged or in an area of magical silence" and the engine
    models neither (#246); armour training is #247. `core.casting` discloses both: an offer
    here means castable as far as this engine can tell, which is still not the same as
    castable.
    """
    offered: list[LegalAction] = []
    spent_a_slot = actor.id in state.slots_expended_this_turn

    for spell in actor.spells:
        kind = ACTION_FOR_CASTING.get(spell.casting_time)
        if kind is None or not actor.actions.available(kind, actor.conditions):
            continue

        # p. 105: "If the spellcaster can't provide one or more of a spell's components, the
        # spellcaster can't cast the spell." Legality rather than a refusal afterwards (R18),
        # so a spell whose Somatic or Material components this creature cannot provide simply
        # is not offered (#245).
        if component_refusal(spell, actor.equipment, actor.hands) is not None:
            continue

        # p. 104: "Before you can cast a spell, you must have the spell **prepared in your
        # mind** or have access to the spell from a magic item." Enforced here since #249;
        # `ritual_cast` has enforced the same sentence since #19 — "a spell merely known is
        # not enough" — and ordinary casting was the half that did not ask (R18).
        if spell.rule_id not in actor.prepared:
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
        # p. 257: the entry "details the attacks a creature can make", so a Multiattack that
        # named a set restricts which weapons may fill its rolls. An empty set permits any
        # held weapon — the reading that refuses nothing for a ruleset that stated a count
        # and no list (0043 clause 2).
        if actor.multiattack is not None and not actor.multiattack.allows(weapon.id):
            continue
        # p. 90's Loading cap, "regardless of the number of attacks you can normally make".
        # An attack made as part of the Attack action spends the Action — including a
        # Multiattack's second and third rolls, which spend no action of their *own* but were
        # bought by that one — so one shot is all this weapon offers here (#271).
        if weapon.loading and state.has_fired_loading(actor.id, str(ActionKind.ACTION)):
            continue
        if not _can_fire(state, actor, weapon):
            continue
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
            offered.extend(_swaps(state, actor, weapon, target))

    offered.extend(_throwable(state, actor))
    offered.extend(_draw_and_use(state, actor))

    return tuple(offered)


def _throwable(state: EncounterState, actor: Combatant) -> tuple[LegalAction, ...]:
    """Every throw this creature may make right now (p. 90, #284).

    > **Thrown.** If a weapon has the Thrown property, you can throw the weapon to make a
    > ranged attack, and you can draw that weapon as part of the attack. If the weapon is a
    > Melee weapon, use the same ability modifier for the attack and damage rolls that you use
    > for a melee attack with that weapon.

    **Held weapons and stowed ones both**, because p. 90's second clause says so outright —
    "you can draw that weapon as part of the attack" is the Thrown property carrying its own
    equip, and it needs no Attack-action swap to spend.

    **Bounded by the weapon's range, not the wielder's reach**, which is the distinction
    `_within_weapon_range` now takes a parameter for: the same Dagger reaches five feet when
    swung and sixty when thrown.

    **A Melee weapon that lacks Thrown is not offered here.** p. 183 makes throwing one an
    improvised weapon dealing "1d4 damage of a type the GM thinks is appropriate" — a person's
    judgement this engine may not invent, and
    [#264](https://github.com/eddiefiggie/srd-rules-engine/issues/264)'s territory.
    """
    offered: list[LegalAction] = []
    for carried in actor.equipment:
        item = carried.item
        if not isinstance(item, Weapon) or not item.thrown:
            continue
        if carried.carriage not in (Carriage.HELD, Carriage.STOWED):
            continue
        for target in state.combatants:
            if target.id == actor.id or target.is_down:
                continue
            if not _within_weapon_range(actor, item, target, thrown=True):
                continue
            offered.append(
                LegalAction(
                    key=attack_throw_key(item.id, target.id),
                    label=f"Throw {item.id} at {target.name}",
                    detail={
                        **_attack_detail(actor, item, target),
                        "thrown": True,
                        # p. 90: a Melee weapon thrown keeps the modifier it uses in melee,
                        # which is what stops a thrown Dagger silently becoming a Dexterity
                        # attack because it is now a ranged one.
                        "ability": item.ability,
                        "drawn_as_part_of_the_attack": carried.carriage is Carriage.STOWED,
                        # 0041 clause 4: it leaves the hand and no rule says where it lands.
                        "lands": "unplaced",
                    },
                )
            )
    return tuple(offered)


def _draw_and_use(state: EncounterState, actor: Combatant) -> tuple[LegalAction, ...]:
    """Equip a weapon and attack with **that** weapon — p. 177's "before", used.

    > If you equip a weapon before an attack, you **don't need to use it** for that attack.

    "Don't need to" is the sentence that makes using it optional, and therefore permitted.
    0042 clause 2 says the pair `(attack weapon, equipped item)` carries the whole before/after
    distinction, and it is **equal** in exactly this case — so an enumeration that never
    produces the equal pair cannot express the ordering the record says it encodes. Every
    other offer here attacks with something already in hand.

    **Only weapons.** A creature may pick up a rock and swing it, and p. 183 makes that an
    improvised weapon with a damage type "the GM thinks is appropriate" — a person's
    judgement this engine may not invent ([#264](https://github.com/eddiefiggie/srd-rules-engine/issues/264)).
    So a non-weapon object is equippable beside an attack and is not attackable *with*.

    Range is measured for the weapon being drawn, not the one in hand: a creature holding a
    dagger and reaching for a bow is asking about the bow's range.
    """
    offered: list[LegalAction] = []
    if actor.id in state.object_interactions_this_turn:  # 0043 clause 3, as in `_swaps`
        return ()
    equippable: list[tuple[Item, str]] = [
        (c.item, str(Carriage.STOWED)) for c in actor.equipment if c.carriage is Carriage.STOWED
    ]
    reachable = reachable_objects(state.detached_objects, actor.position, actor.reach)
    equippable.extend((obj.item, "detached") for obj in reachable or ())

    for item, source in equippable:
        if not isinstance(item, Weapon):
            continue
        for target in state.combatants:
            if target.id == actor.id or target.is_down:
                continue
            if not _within_weapon_range(actor, item, target):
                continue
            offered.append(
                LegalAction(
                    key=attack_swap_key(item.id, target.id, item.id, swap=ATTACK_EQUIP),
                    label=f"Draw {item.id} and attack {target.name} with it",
                    detail={
                        **_attack_detail(actor, item, target),
                        "equip": item.id,
                        "from": source,
                        "used_for_this_attack": True,
                    },
                )
            )
    return tuple(offered)


def interaction_key(verb: str, item_id: str, *, utilize: bool = False) -> str:
    """The key one standalone object interaction is offered under (0045 clauses 2-3).

    `utilize=True` is the same move bought with the Action, which is p. 13's "if you want to
    interact with a second object, you need to take the Utilize action" — same verb, same
    item, a different price.
    """
    return f"{UTILIZE if utilize else INTERACT}:{verb}:{_escape(item_id)}"


def interaction_declared(action_key: str | None) -> tuple[str, str, bool] | None:
    """`(verb, item_id, utilize)` an interaction key names, or `None`."""
    if action_key is None:
        return None
    for prefix, utilize in ((INTERACT, False), (UTILIZE, True)):
        if not action_key.startswith(f"{prefix}:"):
            continue
        verb, _, item = action_key[len(prefix) + 1 :].partition(":")
        if verb not in (VERB_EQUIP, VERB_STOW, VERB_DROP) or not item:
            return None
        return verb, _unescape(item), utilize
    return None


def _interaction_options(
    state: EncounterState, actor: Combatant
) -> tuple[tuple[str, Item, str], ...]:
    """Every `(verb, item, source)` this creature could interact with right now.

    Shared by p. 177's attack-time swap and p. 13's standalone interaction, because 0045
    clause 2 settles that they are **the same four moves** — the second route offers what the
    first already did, and enumerating them twice is how the two would drift apart.

    An unplaced detached object is absent, and stays absent: 0041 clause 4's cost does not
    soften because a new route arrived (0045 clause 6).
    """
    options: list[tuple[str, Item, str]] = []
    for carried in actor.equipment:
        if carried.carriage is Carriage.STOWED:
            options.append((VERB_EQUIP, carried.item, str(Carriage.STOWED)))
        elif carried.carriage is Carriage.HELD:
            options.append((VERB_STOW, carried.item, str(Carriage.HELD)))
            options.append((VERB_DROP, carried.item, str(Carriage.HELD)))
    reachable = reachable_objects(state.detached_objects, actor.position, actor.reach)
    options.extend((VERB_EQUIP, obj.item, "detached") for obj in reachable or ())
    return tuple(options)


def _interactions(state: EncounterState, actor: Combatant) -> tuple[LegalAction, ...]:
    """p. 13's one free object interaction, and the Utilize action that buys another.

    > You can interact with **one object or feature of the environment for free**, during
    > either your move or action… **If you want to interact with a second object, you need to
    > take the Utilize action.**

    **This route did not exist until #288**, and 0042 shipped its absence as an accepted cost:
    "the engine offers no way to sheathe a sword on a quiet turn." It is the same four moves
    p. 177 offers during an attack, offered without one.

    **Free first, then the Action.** The free interaction is offered while unspent; once it is
    gone the same moves reappear under `utilize:`, which spends the Action. A creature with no
    Action left is offered neither, and that is p. 176's economy rather than a special case
    (0045 clause 4).
    """
    free = actor.id not in state.object_interactions_this_turn
    utilize = not free and actor.actions.available(ActionKind.ACTION, actor.conditions)
    if not free and not utilize:
        return ()
    return tuple(
        LegalAction(
            key=interaction_key(verb, item.id, utilize=utilize),
            label=(
                f"{verb.capitalize()} {item.id}"
                + (" (Utilize action)" if utilize else " (free interaction)")
            ),
            detail={
                "verb": verb,
                "item": item.id,
                "from": source,
                # p. 13 gives one free; p. 191's action buys the next.
                "costs_action": utilize,
            },
        )
        for verb, item, source in _interaction_options(state, actor)
    )


def _swaps(
    state: EncounterState, actor: Combatant, weapon: Weapon, target: Combatant
) -> tuple[LegalAction, ...]:
    """p. 177's one equip or unequip, offered against the attack that permits it.

    > You can either equip or unequip **one** weapon when you make an attack as part of this
    > action. You do so either before or after the attack. If you equip a weapon before an
    > attack, you don't need to use it for that attack.

    **Enumerated rather than checked afterwards** (0042 clause 3), and the multiplier is
    `stowed + held + reachable detached objects` per attack — bounded by what the creature
    carries and can reach, not a product with an ordering flag.

    **No ordering is offered, and that is 0042 clause 2.** "Before or after" decides one thing
    — whether the newly equipped weapon is available to *this* attack — and the pair already
    says so: an offer whose equipped item **is** the attack weapon is the "before, and used"
    case. Every other pairing is indistinguishable between before-and-unused and after, which
    p. 177's own next sentence is what makes true.

    **An unplaced object is absent from here** (0041 clause 4, 0042 clause 5). `Situation`
    reports it under `unplaced_objects`, so the gap reads as *nobody said where it fell*
    rather than as an empty menu (#267).
    """
    offered: list[LegalAction] = []
    # 0043 clause 3: at most one swap per turn, whatever the attack count. p. 177 grants one
    # per attack and p. 13 one object interaction per turn, and nothing composes them — one
    # swap is legal under both readings and two under only one, so the engine offers the
    # intersection. The cap is the engine's, and `Situation.unenforced_clauses` says so.
    if actor.id in state.object_interactions_this_turn:
        return ()

    for carried in actor.equipment:
        if carried.carriage is Carriage.STOWED:
            offered.append(
                LegalAction(
                    key=attack_swap_key(weapon.id, target.id, carried.item.id, swap=ATTACK_EQUIP),
                    label=f"Draw {carried.item.id}, then attack {target.name} with {weapon.id}",
                    detail={
                        **_attack_detail(actor, weapon, target),
                        "equip": carried.item.id,
                        "from": str(Carriage.STOWED),
                        # p. 177: equipped before, and used, exactly when the attack names it.
                        "used_for_this_attack": carried.item.id == weapon.id,
                    },
                )
            )
        elif carried.carriage is Carriage.HELD:
            offered.append(
                LegalAction(
                    key=attack_swap_key(weapon.id, target.id, carried.item.id, swap=ATTACK_STOW),
                    label=f"Attack {target.name} with {weapon.id}, then stow {carried.item.id}",
                    detail={
                        **_attack_detail(actor, weapon, target),
                        "unequip": carried.item.id,
                        "to": str(Carriage.STOWED),
                    },
                )
            )
            offered.append(
                LegalAction(
                    key=attack_swap_key(weapon.id, target.id, carried.item.id, swap=ATTACK_DROP),
                    label=f"Attack {target.name} with {weapon.id}, then drop {carried.item.id}",
                    detail={
                        **_attack_detail(actor, weapon, target),
                        "unequip": carried.item.id,
                        # Dropping leaves the creature entirely (0041 clause 2), and the
                        # object arrives unplaced because p. 177 does not say where.
                        "to": "dropped",
                    },
                )
            )

    reachable = reachable_objects(state.detached_objects, actor.position, actor.reach)
    for obj in reachable or ():
        offered.append(
            LegalAction(
                key=attack_swap_key(weapon.id, target.id, obj.item.id, swap=ATTACK_EQUIP),
                label=f"Pick up {obj.item.id}, then attack {target.name} with {weapon.id}",
                detail={
                    **_attack_detail(actor, weapon, target),
                    "equip": obj.item.id,
                    "from": "detached",
                    "used_for_this_attack": obj.item.id == weapon.id,
                },
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
        # p. 90 caps the Loading shot per **action used**, and this one spends the Bonus
        # Action — a separate charge from the Attack action's, so a creature may fire once
        # with each. Keying the cap per turn would refuse a shot the document allows (#271).
        if weapon.loading and state.has_fired_loading(actor.id, str(ActionKind.BONUS_ACTION)):
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


def _can_fire(state: EncounterState, actor: Combatant, weapon: Weapon) -> bool:
    """Whether p. 89's Ammunition property permits this shot (#273).

    > You can use a weapon that has the Ammunition property to make a ranged attack **only if
    > you have ammunition to fire from it**… Drawing the ammunition is part of the attack (you
    > need a free hand to load a one-handed weapon).

    Both halves are conditions of the attack, so they are **legality** rather than a refusal
    after the fact (R18) — the shot is not offered.

    **An unknown hand count does not refuse it.** `Combatant.__post_init__` already settles
    this direction for p. 90's Two-Handed: "no SRD rule states how many hands a creature has,
    so an unstated count cannot be exceeded (R31)." Only a *known* zero blocks the load, and
    refusing on `None` would assert the count the engine declines to assume (0039 clause 4).
    """
    if weapon.ammunition_id is None:
        return True
    if not state.ammunition_for(actor.id, weapon.ammunition_id):
        return False
    # `== 0` and not `not ...`: `free_hands` is `int | None`, and `None` means the count is
    # unstated rather than exhausted.
    return not (weapon.hands_when_held == 1 and actor.free_hands == 0)


def _within_weapon_range(
    actor: Combatant, weapon: Weapon, target: Combatant, *, thrown: bool = False
) -> bool:
    """Whether this weapon can reach that target at all (p. 90, p. 186).

    "Can reach at all" rather than "reaches without penalty": long range is the bound, and the
    Disadvantage inside it is a modifier rather than a refusal.

    **Which bound applies is a question about the attack, not about the weapon** (#284). p. 90
    gives a Thrown weapon a range and a Dagger is a Melee weapon that may be thrown, so the
    same object is bounded by the wielder's reach when swung and by its range when thrown.
    Reading `long_range is not None` alone — which is what this did while no melee weapon had
    a range — would let a Dagger stab a target sixty feet away.
    """
    if actor.position is None or target.position is None:
        return True
    distance = distance_feet(actor.position, target.position)
    if (thrown or not weapon.melee) and weapon.long_range is not None:
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
    # p. 13 grants "one object or feature of the environment for free, during either your
    # move or action", and a second needs the Utilize action. p. 177 separately grants one
    # weapon swap per attack made as part of the Attack action. **The document never states
    # their relationship**, and 0042 clause 6 records that rather than resolving it: the
    # engine tracks p. 177's allowance and claims nothing about the other, which is honest
    # only while nothing else can spend an object interaction. #288 (`utilize`) and #289
    # (`multiattack`) are the two shapes that would make the readings diverge, and each
    # carries the clause. Disclosed here because an agent reading a swap offer would
    # otherwise reasonably infer the free interaction had been spent, or preserved.
    unenforced.append(UTILIZE_REACHES_FOUR_MOVES)
    # Only while the creature actually carries a Verbal spell: a disclosure about a rule that
    # cannot apply to this creature is noise, and #292 pins the set so it has to be deliberate.
    if any(spell.verbal for spell in actor.spells):
        unenforced.append(VERBAL_UNCHECKED)
    # 0045 clause 1. Only while the creature could still interact: once it has, the refusal is
    # visible in the menu and the disclosure has done its work.
    if actor.id not in state.object_interactions_this_turn:
        unenforced.append(OBJECT_INTERACTION_CAP)

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
        reachable_objects=(
            None
            if (reachable := reachable_objects(state.detached_objects, actor.position, actor.reach))
            is None
            else tuple(obj.item.id for obj in reachable)
        ),
        unplaced_objects=tuple(obj.item.id for obj in unplaced_objects(state.detached_objects)),
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
