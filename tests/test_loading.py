"""p. 90's Loading property: one shot per action used (#271).

> **Loading.** You can fire only one piece of ammunition from a Loading weapon when you use an
> action, a Bonus Action, or a Reaction to fire it, **regardless of the number of attacks you
> can normally make**.

That final clause is the whole property, and it had nothing to bite on for the life of this
repository. #271 was filed saying Light would be the trigger, corrected when
[#270](https://github.com/eddiefiggie/srd-rules-engine/issues/270) landed and turned out not to
be — p. 89's extra attack is a **Bonus Action**, a separate action, so one shot each was always
within the cap — and blocked on something granting two attacks inside one action. p. 257's
Multiattack (#289) is that thing.

Two things here are easy to get wrong:

* **The cap is per action used, not per turn.** A creature with an Action and a Bonus Action
  may fire once with each, and a per-turn key would refuse the second.
* **It is not per weapon.** Two Loading weapons do not buy two shots from one action.
"""

from __future__ import annotations

from pathlib import Path

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    Declaration,
    EffectKind,
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
from srd_rules_engine.core.equipment import Multiattack
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import bonus_attack_key
from srd_rules_engine.memory.store import JsonMemoryStore

#: A Loading weapon, and a Light one so p. 89's Bonus Action can be reached.
CROSSBOW = Weapon(
    id="fixture:crossbow",
    damage_dice=1,
    damage_sides=8,
    melee=False,
    loading=True,
    light=True,
    normal_range=80,
    long_range=320,
    hands_when_held=1,
)
#: The same weapon without the property, so the cap is shown to be the property's doing.
SLING = Weapon(
    id="fixture:sling",
    damage_dice=1,
    damage_sides=4,
    melee=False,
    light=True,
    normal_range=30,
    long_range=120,
    hands_when_held=1,
)

#: A second Loading weapon, because p. 89's extra attack needs a *different* Light one.
HAND_CROSSBOW = Weapon(
    id="fixture:hand-crossbow",
    damage_dice=1,
    damage_sides=6,
    melee=False,
    loading=True,
    light=True,
    normal_range=30,
    long_range=120,
    hands_when_held=1,
)

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no weapon table ships here.",
)
RULESET = load_fixture_ruleset("loading", [STRIKE])


def shooter(
    *,
    held: tuple[Weapon, ...] = (CROSSBOW,),
    multiattack: Multiattack | None = None,
    bonus: bool = False,
) -> Combatant:
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=30,
        max_hit_points=30,
        armour_class=13,
        abilities={"str": 14, "dex": 16},
        proficiency_bonus=2,
        position=Position(0, 0, 0),
        hands=2,
        equipment=tuple(Carried(w, Carriage.HELD) for w in held),
        weapon_proficiencies=frozenset(w.id for w in held),
        multiattack=multiattack,
        actions=ActionBudget(bonus_action_granted=True) if bonus else ActionBudget(),
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
        position=Position(20, 0, 0),
    )


def encounter(actor: Combatant | None = None) -> EncounterState:
    return EncounterState.new([actor or shooter(), boar()]).with_initiative({"pc": 20, "boar": 5})


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


def declare(state: EncounterState, key: str) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=key),
        rule_id=STRIKE.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def keys(state: EncounterState) -> set[str]:
    return {a.key for a in read(state, "pc").actions}


def fire(state: EncounterState, path: Path, key: str) -> EncounterState:
    _ruling, after = build(path).adjudicate(state, declare(state, key))
    return after


# --- the clause that had nothing to bite on ---------------------------------------------


def test_a_multiattack_fires_a_loading_weapon_once(tmp_path: Path) -> None:
    """p. 90's "regardless of the number of attacks you can normally make", finally reachable.

    Three rolls bought by one Action, and the crossbow may fill exactly one of them.
    """
    state = encounter(shooter(multiattack=Multiattack(attacks=3)))
    assert attack_key(CROSSBOW.id, "boar") in keys(state)

    after = fire(state, tmp_path, attack_key(CROSSBOW.id, "boar"))
    assert after.attacks_remaining("pc") == 2, "the Action still has rolls left"
    assert attack_key(CROSSBOW.id, "boar") not in keys(after), "and none of them is this"


def test_the_other_rolls_are_still_offered(tmp_path: Path) -> None:
    """The cap is on the weapon, not on the creature: a second held weapon without the
    property fills the remaining rolls.

    No Unarmed Strike is asserted here, and that is the fixture rather than the rule — the
    boar stands at 20 feet and p. 190's strike reaches 5.
    """
    state = encounter(shooter(held=(CROSSBOW, SLING), multiattack=Multiattack(attacks=3)))
    after = fire(state, tmp_path, attack_key(CROSSBOW.id, "boar"))
    assert attack_key(CROSSBOW.id, "boar") not in keys(after)
    assert attack_key(SLING.id, "boar") in keys(after)


def test_a_weapon_without_the_property_fires_every_roll(tmp_path: Path) -> None:
    """Which shows the refusal above is Loading's doing rather than the Multiattack's.

    **A deliberate control, and it covers nothing on its own** — it stayed green under all
    three corruption proofs, because removing the cap cannot change what an uncapped weapon
    does. Named rather than left to look like coverage, which is what the standing rule added
    by [#298](https://github.com/eddiefiggie/srd-rules-engine/issues/298) asks for.
    """
    state = encounter(shooter(held=(SLING,), multiattack=Multiattack(attacks=3)))
    after = fire(state, tmp_path, attack_key(SLING.id, "boar"))
    assert after.attacks_remaining("pc") == 2
    assert attack_key(SLING.id, "boar") in keys(after)


# --- per action used, not per turn ------------------------------------------------------


def test_the_bonus_action_buys_its_own_shot(tmp_path: Path) -> None:
    """p. 90 caps the shot "when you use an action, a Bonus Action, or a Reaction to fire it",
    so the Action's shot and the Bonus Action's are separate.

    This is what #271 originally got wrong in the other direction: it guessed Light would make
    the cap bite, and p. 89's extra attack is a Bonus Action — a *second* allowance, never a
    second shot from the first.
    """
    # **Two Loading weapons**, because p. 89 requires the extra attack be made with a
    # *different* Light weapon — so the crossbow cannot bonus-attack itself, and testing the
    # per-action cap needs a second one that also has the property.
    state = encounter(shooter(held=(CROSSBOW, HAND_CROSSBOW), bonus=True))
    after = fire(state, tmp_path / "a", attack_key(CROSSBOW.id, "boar"))
    assert after.has_fired_loading("pc", str(ActionKind.ACTION))
    assert not after.has_fired_loading("pc", str(ActionKind.BONUS_ACTION))
    assert bonus_attack_key(HAND_CROSSBOW.id, "boar") in keys(after), (
        "the Bonus Action is a second allowance, not a second shot from the first"
    )

    spent = fire(after, tmp_path / "b", bonus_attack_key(HAND_CROSSBOW.id, "boar"))
    assert spent.has_fired_loading("pc", str(ActionKind.BONUS_ACTION))
    assert not any(k.startswith("bonus-attack:") for k in keys(spent))


def test_the_shot_is_recorded_as_its_own_effect(tmp_path: Path) -> None:
    """R5. The cap is keyed by the action used, and a Multiattack's later rolls spend no
    action of their own — so the pair is not recoverable from the attack tally beside it and
    has to be recorded rather than derived."""
    state = encounter(shooter(multiattack=Multiattack(attacks=2)))
    ruling, _after = build(tmp_path).adjudicate(
        state, declare(state, attack_key(CROSSBOW.id, "boar"))
    )
    fired = [e for e in ruling.effects if e.kind is EffectKind.LOADING_FIRED]
    assert len(fired) == 1
    assert fired[0].action is ActionKind.ACTION


def test_the_cap_clears_when_the_turn_advances(tmp_path: Path) -> None:
    after = fire(encounter(), tmp_path, attack_key(CROSSBOW.id, "boar"))
    assert after.has_fired_loading("pc", str(ActionKind.ACTION))
    assert not after.advanced_turn().has_fired_loading("pc", str(ActionKind.ACTION))
