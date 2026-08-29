"""p. 90's Nick: p. 89's extra attack, carried by the Attack action (#320).

> **Nick.** When you make the extra attack of the Light property, you can make it as part of
> the Attack action instead of as a Bonus Action. You can make this extra attack only once
> per turn.

Nick introduces no new attack. It **re-routes** one that already ships, so almost everything
worth asserting here is about what stayed the same and what stopped being charged.

**It belongs to the weapon making the extra attack.** p. 89's extra attack "must be made with
a **different** Light weapon", and every mastery property describes an attack made *with that
weapon* — so Nick is carried by the second weapon rather than the one that bought the attack.
p. 91's table settles it: all four weapons with Nick — Dagger, Light Hammer, Sickle, Scimitar
— are Light, and no weapon that is not Light has it.

**"Instead of" is a cap, and it needed a new record.** Until Nick, the Bonus Action spend
*was* the bookkeeping for p. 89's "one extra attack": a second was refused because no Bonus
Action remained. A Nick attack spends nothing, so nothing stopped a creature taking one by
each route — which is `EncounterState.extra_attacks_this_turn`.

**Both routes are offered.** p. 90 says "you **can** make it as part of the Attack action",
which grants an option rather than withdrawing one, so a Nick wielder with a Bonus Action to
spare sees both keys. Offering only the cheaper one would be the engine choosing tactically on
the agent's behalf, which R18 does not ask it to do — the read surface reports what is legal.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    DamageDice,
    Declaration,
    EncounterState,
    Intent,
    Ledger,
    Rule,
    RuleProvenance,
    Weapon,
    attack_key,
    attack_resolver,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.actions import ActionBudget, ActionKind
from srd_rules_engine.core.adjudicate import Proposal
from srd_rules_engine.core.equipment import Multiattack
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import bonus_attack_key, nick_attack_key
from srd_rules_engine.memory.store import JsonMemoryStore

#: The weapon the Attack action is spent on. Light, so it buys p. 89's extra attack; no
#: mastery of its own, so nothing here turns on it.
SHORTSWORD = Weapon(
    id="fixture:shortsword", damage_dice=1, damage_sides=6, light=True, hands_when_held=1
)
#: The weapon the extra attack is made with, carrying Nick — p. 91 gives it to the Dagger.
DAGGER = Weapon(
    id="fixture:dagger", damage_dice=1, damage_sides=4, light=True, nick=True, hands_when_held=1
)
#: The same weapon without the property, so a difference is the property's doing.
SICKLE = Weapon(id="fixture:sickle", damage_dice=1, damage_sides=4, light=True, hands_when_held=1)
#: Nick on a weapon that is **not** Light. No invariant refuses one — p. 90 never says the
#: property requires Light, and asserting it would be the inferred rule value #284 found in
#: `Range`'s own check — so the engine has to make it inert rather than impossible. p. 91
#: gives Nick to four weapons and all four are Light, so nothing like this ships.
CUDGEL = Weapon(id="fixture:cudgel", damage_dice=1, damage_sides=6, nick=True, hands_when_held=1)

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no weapon table ships here.",
)
RULESET = load_fixture_ruleset("nick", [STRIKE])


def duellist(
    *,
    held: tuple[Weapon, ...] = (SHORTSWORD, DAGGER),
    masters: tuple[Weapon, ...] | None = None,
    bonus: bool = True,
    multiattack: Multiattack | None = None,
) -> Combatant:
    """`masters` defaults to everything held: p. 90 gates every mastery property on a feature
    the wielder has (0047), so a test about Nick has to grant it before Nick exists at all."""
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 16, "dex": 12},
        proficiency_bonus=2,
        position=Position(0, 0, 0),
        hands=2,
        equipment=tuple(Carried(w, Carriage.HELD) for w in held),
        weapon_proficiencies=frozenset(w.id for w in held),
        mastery_weapons=frozenset(w.id for w in (held if masters is None else masters)),
        multiattack=multiattack,
        actions=ActionBudget(bonus_action_granted=bonus),
    )


def boar() -> Combatant:
    return Combatant(
        id="boar",
        name="Boar",
        hit_points=200,
        max_hit_points=200,
        armour_class=8,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(5, 0, 0),
    )


def encounter(actor: Combatant | None = None) -> EncounterState:
    return EncounterState.new([actor or duellist(), boar()]).with_initiative({"pc": 20, "boar": 5})


def build(path: Path, *, seed: int = 3) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers={STRIKE.id: attack_resolver()},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: seed,
    )


def swing(state: EncounterState, path: Path, key: str) -> EncounterState:
    offered = read(state, "pc")
    _ruling, after = build(path).adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=key),
            rule_id=STRIKE.id,
            alternatives=offered.actions,
            read_token=offered.token,
        ),
    )
    return after


def keys(state: EncounterState) -> set[str]:
    return {a.key for a in read(state, "pc").actions}


def opened(path: Path, **kw: object) -> EncounterState:
    """The Attack action spent on the Shortsword, which is what buys p. 89's extra attack."""
    state = encounter(duellist(**kw))  # type: ignore[arg-type]
    return swing(state, path, attack_key(SHORTSWORD.id, "boar"))


# --- the re-route ------------------------------------------------------------------------


def test_nick_offers_the_extra_attack_inside_the_attack_action(tmp_path: Path) -> None:
    """The property, in one assertion: the extra attack is available under its own key."""
    assert nick_attack_key(DAGGER.id, "boar") in keys(opened(tmp_path))


def test_a_weapon_without_nick_offers_only_the_bonus_action_route(tmp_path: Path) -> None:
    """Shown to be the property's doing. The Sickle is Light and buys the same extra attack,
    and without Nick that attack costs the Bonus Action."""
    after = opened(tmp_path, held=(SHORTSWORD, SICKLE))

    assert bonus_attack_key(SICKLE.id, "boar") in keys(after)
    assert nick_attack_key(SICKLE.id, "boar") not in keys(after)


def test_nick_is_refused_to_a_wielder_with_no_feature_unlocking_it(tmp_path: Path) -> None:
    """0047 clause 6: every mastery takes the gate, checked beside its own flag. The same
    Dagger, in the same hand — only the permission differs."""
    granted = opened(tmp_path / "granted")
    withheld = opened(tmp_path / "withheld", masters=(SHORTSWORD,))

    assert nick_attack_key(DAGGER.id, "boar") in keys(granted)
    assert nick_attack_key(DAGGER.id, "boar") not in keys(withheld)
    assert bonus_attack_key(DAGGER.id, "boar") in keys(withheld), "p. 89's route is untouched"


def test_the_nick_attack_spends_no_action(tmp_path: Path) -> None:
    """**The whole value of the property.** "as part of the Attack action instead of as a
    Bonus Action" — and that Action was already spent buying the attack that triggered it, so
    this one costs nothing further. A Bonus Action still held afterwards is the assertion."""
    after = swing(opened(tmp_path), tmp_path / "nick", nick_attack_key(DAGGER.id, "boar"))
    pc = after.combatant("pc")

    assert pc.actions.available(ActionKind.BONUS_ACTION, pc.conditions)


def test_the_bonus_action_route_still_spends_the_bonus_action(tmp_path: Path) -> None:
    """The comparison that makes the assertion above mean something: the same extra attack,
    taken the other way, costs what it always did."""
    after = swing(opened(tmp_path), tmp_path / "bonus", bonus_attack_key(DAGGER.id, "boar"))
    pc = after.combatant("pc")

    assert not pc.actions.available(ActionKind.BONUS_ACTION, pc.conditions)


def test_nick_is_offered_when_the_bonus_action_is_already_gone(tmp_path: Path) -> None:
    """The case p. 90 exists for. A creature with no Bonus Action left has no route to p. 89's
    extra attack at all — unless the weapon carries Nick."""
    spent = opened(tmp_path, bonus=False)

    assert bonus_attack_key(DAGGER.id, "boar") not in keys(spent)
    assert nick_attack_key(DAGGER.id, "boar") in keys(spent)


def test_both_routes_are_offered_when_both_are_legal(tmp_path: Path) -> None:
    """p. 90 says "you **can** make it as part of the Attack action", granting an option
    rather than withdrawing one. Offering only the cheaper of two identical outcomes would be
    the engine deciding a tactical question the agent is entitled to decide (R18)."""
    after = opened(tmp_path)

    assert {nick_attack_key(DAGGER.id, "boar"), bonus_attack_key(DAGGER.id, "boar")} <= keys(after)


# --- "only once per turn", which is the clause that needed a new record -------------------


def test_the_nick_attack_is_the_extra_attack_and_not_a_second_one(tmp_path: Path) -> None:
    """**"instead of", enforced.** p. 89 grants one extra attack and p. 90 re-routes that same
    one. Taking it by Nick must therefore close the Bonus Action route as well — and until
    #320 nothing did, because the Bonus Action spend had been the only thing recording that
    the extra attack was used, and a Nick attack spends nothing.
    """
    after = swing(opened(tmp_path), tmp_path / "nick", nick_attack_key(DAGGER.id, "boar"))

    assert after.has_taken_extra_attack("pc")
    assert bonus_attack_key(DAGGER.id, "boar") not in keys(after)
    assert nick_attack_key(DAGGER.id, "boar") not in keys(after)


def test_the_bonus_route_also_closes_the_nick_route(tmp_path: Path) -> None:
    """The mirror, and it is not symmetric by construction: the Bonus Action spend closes its
    own route for free, so only an explicit record closes Nick's."""
    after = swing(opened(tmp_path), tmp_path / "bonus", bonus_attack_key(DAGGER.id, "boar"))

    assert nick_attack_key(DAGGER.id, "boar") not in keys(after)


def test_the_allowance_returns_next_turn(tmp_path: Path) -> None:
    """ "Only once per **turn**". A per-encounter record would refuse an attack the document
    allows, which is the mistake #271 found in Loading's cap keyed the same way."""
    after = swing(opened(tmp_path), tmp_path / "nick", nick_attack_key(DAGGER.id, "boar"))
    assert after.has_taken_extra_attack("pc")

    # Both boundaries, because `advanced_turn` clears at two sites — the ordinary step to the
    # next combatant, and the wrap into the next round — and a test that only wraps is green
    # while either one of them works. The corruption proof for this clause said so.
    assert not after.advanced_turn().has_taken_extra_attack("pc"), "the step to the next turn"
    assert not after.advanced_turn().advanced_turn().has_taken_extra_attack("pc"), "the wrap"


def test_the_allowance_returns_when_the_round_wraps(tmp_path: Path) -> None:
    """The same clearing, at the other site — and it needs its own fixture to be visible.

    `advanced_turn` clears per-turn records in two places: the ordinary step to the next
    combatant, and the wrap into the next round. Which one runs depends on where the actor
    sits in initiative, so the test above — whose actor goes **first** — is green while only
    the step works. Here the actor goes **last**, so its turn ends on the wrap. Without this,
    a creature at the bottom of the order would carry p. 89's spent extra attack into the next
    round and be refused an attack the document allows.
    """
    state = EncounterState.new([duellist(), boar()]).with_initiative({"pc": 5, "boar": 20})
    pcs_turn = state.advanced_turn()
    assert pcs_turn.active_id == "pc", "precondition: the actor goes last"

    opened_last = swing(pcs_turn, tmp_path / "open", attack_key(SHORTSWORD.id, "boar"))
    after = swing(opened_last, tmp_path / "nick", nick_attack_key(DAGGER.id, "boar"))
    assert after.has_taken_extra_attack("pc")

    assert not after.advanced_turn().has_taken_extra_attack("pc")


def test_the_resolver_refuses_a_nick_key_the_surface_would_not_offer(tmp_path: Path) -> None:
    """The second gate on the same fact, and it is reachable rather than decorative.

    `legal_actions` never offers Nick without the property, and a declaration naming an
    unoffered key is rejected before it reaches a resolver. But `attack_resolver` is callable
    directly — which is exactly the limit this project ships disclosed, that the skip
    guarantee holds only for callers the turn loop drives. Such a caller gets outcome
    authority, so the property is re-checked where the outcome is produced.

    Written because the corruption proof for this refusal came back green: nothing declared a
    Nick key the surface had withheld, so the check was inspecting nothing.
    """
    withheld = opened(tmp_path, masters=(SHORTSWORD,))

    with pytest.raises(ValueError, match=r"does not carry p\. 90's Nick"):
        _propose(withheld, nick_attack_key(DAGGER.id, "boar"))


def test_the_resolver_refuses_a_nick_key_for_a_weapon_without_the_property(
    tmp_path: Path,
) -> None:
    """The other half: mastery granted, but the weapon simply has no Nick to unlock."""
    plain = opened(tmp_path, held=(SHORTSWORD, SICKLE))

    with pytest.raises(ValueError, match=r"does not carry p\. 90's Nick"):
        _propose(plain, nick_attack_key(SICKLE.id, "boar"))


# --- what the re-route must not change ---------------------------------------------------


def _damage(effects: tuple[object, ...]) -> DamageDice:
    dice = [e for e in effects if isinstance(e, DamageDice)]
    assert len(dice) == 1
    return dice[0]


def _propose(state: EncounterState, key: str) -> Proposal:
    return attack_resolver()(
        state=state,
        declaration=Declaration(actor_id="pc", intent=Intent(action_key=key), rule_id=STRIKE.id),
        facts={},
    )


def test_the_nick_attack_keeps_p89s_damage_exception(tmp_path: Path) -> None:
    """p. 89 drops the ability modifier from **the extra attack's** damage unless it is
    negative. That exception belongs to the extra attack, not to the Bonus Action carrying
    it, so re-routing must not restore a modifier the document withholds.

    **Asserted on the resolver's own damage, not on the read surface's `detail`.** The detail
    recomputes `min(0, modifier)` independently, so a test reading it passes whatever the
    resolver does — which the corruption proof for this clause demonstrated by staying green
    while `is_extra` was swapped back to `is_bonus`.
    """
    after = opened(tmp_path)

    assert _damage(_propose(after, attack_key(SHORTSWORD.id, "boar")).on_success).modifier == 3
    assert _damage(_propose(after, nick_attack_key(DAGGER.id, "boar")).on_success).modifier == 0
    assert _damage(_propose(after, bonus_attack_key(DAGGER.id, "boar")).on_success).modifier == 0


def test_the_nick_attack_is_not_one_of_the_attack_actions_rolls(tmp_path: Path) -> None:
    """p. 257 counts the rolls the Attack action **bought**. p. 89's extra attack is not one
    of them by either route — "as part of" the Attack action is not "bought by" it — and
    counting it would quietly cost a Multiattack creature one of its own rolls.
    """
    two = Multiattack(attacks=2)
    after = swing(
        opened(tmp_path, multiattack=two), tmp_path / "nick", nick_attack_key(DAGGER.id, "boar")
    )

    assert after.attacks_remaining("pc") == 1, "one Shortsword roll spent, the Nick one free"
    assert attack_key(SHORTSWORD.id, "boar") in keys(after)


def test_the_extra_attack_still_needs_a_different_light_weapon(tmp_path: Path) -> None:
    """p. 89's condition is untouched by Nick. A creature holding only the weapon it attacked
    with has nothing to make the extra attack with, whatever masteries it has."""
    lone = opened(tmp_path, held=(SHORTSWORD,))

    assert not any(k.startswith("nick-attack:") for k in keys(lone))


def test_nick_on_a_weapon_that_is_not_light_offers_nothing(tmp_path: Path) -> None:
    """**The property is inert rather than impossible**, and the distinction is deliberate.

    p. 90 never says Nick requires a Light weapon, so `Weapon.__post_init__` refuses no such
    thing — asserting it would be the inferred rule value #284 found already shipped in
    `Range`'s own check (R31). What makes it harmless is p. 89: the extra attack "must be made
    with a **different Light** weapon", so a Nick weapon that is not Light can never be the
    one making it.

    Written because the corruption proof for the Light requirement came back green: the test
    above holds a single weapon, so `weapon.id in used` excluded it whether or not the Light
    check ran, and the assertion was true for a reason unrelated to the rule it named.
    """
    with_cudgel = opened(tmp_path, held=(SHORTSWORD, CUDGEL))

    assert nick_attack_key(CUDGEL.id, "boar") not in keys(with_cudgel)
    assert bonus_attack_key(CUDGEL.id, "boar") not in keys(with_cudgel)
