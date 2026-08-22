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

from srd_rules_engine.core.canonical import CanonicalizationError, digest
from srd_rules_engine.core.state import EncounterState

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


def attack_key(target_id: str) -> str:
    return f"{ATTACK}:{target_id}"


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
class ReadResult:
    """What a read-surface call returns: the offered set, and the token committing to it."""

    actor_id: str
    generation: int
    actions: tuple[LegalAction, ...]
    token: str

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
    actions.extend(
        LegalAction(
            key=attack_key(other.id),
            label=f"Attack {other.name}",
            detail={"target": other.id, "armour_class": other.armour_class},
        )
        for other in state.combatants
        if other.id != actor_id and not other.is_down
    )
    return tuple(actions)


def read(state: EncounterState, actor_id: str) -> ReadResult:
    """Answer what is legal for an actor right now. Mutates nothing, records nothing."""
    actions = legal_actions(state, actor_id)
    return ReadResult(
        actor_id=actor_id,
        generation=state.generation,
        actions=actions,
        token=issue_token(state.generation, actions),
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
