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


def attack_key(target_id: str) -> str:
    return f"{ATTACK}:{target_id}"


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
    """The target an attack key names, or None if the key is not an attack."""
    if action_key is None or not action_key.startswith(f"{ATTACK}:"):
        return None
    return action_key.split(":", 1)[1] or None


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
        actions.extend(
            LegalAction(
                key=attack_key(other.id),
                label=f"Attack {other.name}",
                detail=_attack_detail(actor, other),
            )
            for other in state.combatants
            if other.id != actor_id and not other.is_down
        )

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


def _attack_detail(actor: Combatant, target: Combatant) -> dict[str, object]:
    """What the agent needs to judge an attack, including the distance to the target.

    The distance is reported rather than used to gate the offer. Whether a target is in
    range depends on the *weapon* — reach for a melee one, normal and long range for a
    ranged one — and the read surface does not know which weapon an attack will use. So it
    supplies the fact and leaves the judgement, rather than filtering on an assumption.
    Adjudication still refuses an attack beyond reach or long range.
    """
    detail: dict[str, object] = {"target": target.id, "armour_class": target.armour_class}
    if actor.position is not None and target.position is not None:
        detail["distance"] = distance_feet(actor.position, target.position)
        detail["reach"] = actor.reach
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
