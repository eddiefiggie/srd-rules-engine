"""p. 13's free object interaction, and p. 191's Utilize action (#288, 0045).

> p. 13, *Your Turn*: You can interact with **one object or feature of the environment for
> free**, during either your move or action… **If you want to interact with a second object,
> you need to take the Utilize action.**

This route did not exist until #288, and 0042 shipped its absence as an accepted cost: "the
engine offers no way to sheathe a sword on a quiet turn."

Three things here are easy to get wrong:

* **It is one allowance with two routes.** p. 177's swap during an attack and p. 13's free
  interaction spend the same thing, which is 0043 clause 3's intersection applied a second
  time — two are legal under the independent reading and not under the shared one.
* **Utilize does not restore the free one.** It is the action you take *because* the free one
  is gone, so it spends the Action and the allowance both.
* **An unplaced object stays unreachable.** 0041 clause 4's cost does not soften because a new
  route arrived.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    Declaration,
    EffectKind,
    EncounterState,
    Intent,
    Item,
    Ledger,
    Rule,
    RuleProvenance,
    Weapon,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.actions import ActionBudget, ActionKind
from srd_rules_engine.core.combat import object_interaction_resolver
from srd_rules_engine.core.equipment import DetachedObject
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import (
    ATTACK_STOW,
    OBJECT_INTERACTION_CAP,
    VERB_DROP,
    VERB_EQUIP,
    VERB_STOW,
    attack_swap_key,
    interaction_declared,
    interaction_key,
)
from srd_rules_engine.memory.store import JsonMemoryStore

BLADE = Weapon(id="fixture:blade", damage_dice=1, damage_sides=6, hands_when_held=1)
AXE = Weapon(id="fixture:axe", damage_dice=1, damage_sides=8, hands_when_held=1)
ROCK = Item(id="fixture:rock", weight=2.0, hands_when_held=1)

INTERACT_RULE = Rule(
    id="object-interaction",
    summary="p. 13's free object interaction, or p. 191's Utilize action.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no object table ships here.",
)
RULESET = load_fixture_ruleset("interact", [INTERACT_RULE])


def fighter(**kw: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 13,
        "abilities": {"str": 16, "dex": 12},
        "proficiency_bonus": 2,
        "position": Position(0, 0, 0),
        "hands": 2,
        "equipment": (Carried(BLADE, Carriage.HELD), Carried(AXE, Carriage.STOWED)),
        "weapon_proficiencies": frozenset({BLADE.id, AXE.id}),
    }
    fields.update(kw)
    return Combatant(**fields)  # type: ignore[arg-type]


def boar() -> Combatant:
    return Combatant(
        id="boar",
        name="Boar",
        hit_points=20,
        max_hit_points=20,
        armour_class=8,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(5, 0, 0),
    )


def encounter(
    actor: Combatant | None = None,
    detached_objects: tuple[DetachedObject, ...] = (),
) -> EncounterState:
    state = EncounterState.new([actor or fighter(), boar()]).with_initiative({"pc": 20, "boar": 5})
    return replace(state, detached_objects=detached_objects)


def build(path: Path, *, seed: int = 3) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers={INTERACT_RULE.id: object_interaction_resolver()},
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
        rule_id=INTERACT_RULE.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def keys(state: EncounterState) -> set[str]:
    return {a.key for a in read(state, "pc").actions}


def do(state: EncounterState, path: Path, key: str) -> EncounterState:
    _ruling, after = build(path).adjudicate(state, declare(state, key))
    return after


def carriage_of(state: EncounterState, item_id: str) -> Carriage | None:
    for carried in state.combatant("pc").equipment:
        if carried.item.id == item_id:
            return carried.carriage
    return None


# --- the route 0042 shipped as an accepted cost -----------------------------------------


def test_a_sword_can_be_sheathed_on_a_quiet_turn(tmp_path: Path) -> None:
    """0042's accepted cost, lifted: "the engine offers no way to sheathe a sword on a quiet
    turn — that is p. 13's free interaction, which clause 6 does not model.\""""
    state = encounter()
    key = interaction_key(VERB_STOW, BLADE.id)
    assert key in keys(state)
    assert carriage_of(do(state, tmp_path, key), BLADE.id) is Carriage.STOWED


def test_the_four_moves_are_the_same_four(tmp_path: Path) -> None:
    """0045 clause 2. Stowed becomes drawable, held becomes stowable and droppable, and a
    reachable object becomes pick-up-able — the moves p. 177's swap already performed."""
    state = encounter(detached_objects=(DetachedObject(ROCK, Position(5, 0, 0)),))
    offered = keys(state)
    assert interaction_key(VERB_EQUIP, AXE.id) in offered, "stowed"
    assert interaction_key(VERB_STOW, BLADE.id) in offered, "held"
    assert interaction_key(VERB_DROP, BLADE.id) in offered, "held"
    assert interaction_key(VERB_EQUIP, ROCK.id) in offered, "on the ground"


def test_dropping_routes_through_detachment(tmp_path: Path) -> None:
    after = do(encounter(), tmp_path, interaction_key(VERB_DROP, BLADE.id))
    assert [o.item.id for o in after.detached_objects] == [BLADE.id]
    assert after.detached_objects[0].position is None


def test_picking_up_takes_the_object_out_of_the_encounter(tmp_path: Path) -> None:
    state = encounter(detached_objects=(DetachedObject(ROCK, Position(5, 0, 0)),))
    after = do(state, tmp_path, interaction_key(VERB_EQUIP, ROCK.id))
    assert after.detached_objects == ()
    assert carriage_of(after, ROCK.id) is Carriage.HELD


def test_an_unplaced_object_stays_unreachable() -> None:
    """0045 clause 6. 0041 clause 4's cost does not soften because a new route arrived."""
    state = encounter(detached_objects=(DetachedObject(Item(id="fixture:lost")),))
    assert interaction_key(VERB_EQUIP, "fixture:lost") not in keys(state)


# --- one allowance, two routes (clause 1) -----------------------------------------------


def test_the_free_interaction_is_spent_once(tmp_path: Path) -> None:
    """**The negative assertion names no single key, and that is deliberate.** An earlier
    version asserted a `drop` of the stowed axe was absent — which it is whether or not the
    allowance exists, because a stowed item is never droppable. The corruption proof caught
    it green ([#298](https://github.com/eddiefiggie/srd-rules-engine/issues/298)); asking
    whether *any* free interaction survives is the question the cap actually decides.
    """
    state = encounter()
    assert any(k.startswith("interact:") for k in keys(state))
    after = do(state, tmp_path, interaction_key(VERB_STOW, BLADE.id))
    assert "pc" in after.object_interactions_this_turn
    assert not any(k.startswith("interact:") for k in keys(after)), "the free one is gone"


def test_a_swap_during_an_attack_spends_the_same_allowance(tmp_path: Path) -> None:
    """0043 clause 3's intersection, applied a second time: two interactions are legal under
    the independent reading and not under the shared one, so the engine offers one."""
    from srd_rules_engine.core import attack_resolver

    state = encounter()
    swapper = Adjudicator(
        ruleset=RULESET,
        resolvers={INTERACT_RULE.id: attack_resolver()},
        fact_types={},
        port=JsonMemoryStore(tmp_path / "memory.json"),
        ledger=Ledger.open(
            tmp_path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 3,
    )
    _ruling, after = swapper.adjudicate(
        state, declare(state, attack_swap_key(BLADE.id, "boar", BLADE.id, swap=ATTACK_STOW))
    )
    assert "pc" in after.object_interactions_this_turn
    assert not any(k.startswith("interact:") for k in keys(after)), "and none is free"


def test_the_allowance_clears_when_the_turn_advances(tmp_path: Path) -> None:
    after = do(encounter(), tmp_path, interaction_key(VERB_STOW, BLADE.id))
    assert "pc" not in after.advanced_turn().object_interactions_this_turn


# --- Utilize buys another (clauses 3 and 4) ---------------------------------------------


def test_utilize_buys_a_second_interaction(tmp_path: Path) -> None:
    """p. 13: "If you want to interact with a second object, you need to take the Utilize
    action." The same moves reappear at a different price."""
    state = do(encounter(), tmp_path / "a", interaction_key(VERB_STOW, BLADE.id))
    assert interaction_key(VERB_EQUIP, AXE.id, utilize=True) in keys(state)
    after = do(state, tmp_path / "b", interaction_key(VERB_EQUIP, AXE.id, utilize=True))
    assert carriage_of(after, AXE.id) is Carriage.HELD


def test_utilize_spends_the_action(tmp_path: Path) -> None:
    state = do(encounter(), tmp_path / "a", interaction_key(VERB_STOW, BLADE.id))
    ruling, after = build(tmp_path / "b").adjudicate(
        state, declare(state, interaction_key(VERB_EQUIP, AXE.id, utilize=True))
    )
    assert EffectKind.ACTION_SPENT in {e.kind for e in ruling.effects}
    assert not after.combatant("pc").actions.available(
        ActionKind.ACTION, after.combatant("pc").conditions
    )


def test_no_action_means_no_utilize(tmp_path: Path) -> None:
    """p. 176 gives one action a turn, so a creature that spent it is offered neither the free
    interaction it already used nor the Utilize it cannot afford (0045 clause 4)."""
    spent = do(
        encounter(fighter(actions=ActionBudget().spend(ActionKind.ACTION))),
        tmp_path,
        interaction_key(VERB_STOW, BLADE.id),
    )
    assert not any(k.startswith(("interact:", "utilize:")) for k in keys(spent))


def test_the_free_one_is_offered_before_the_paid_one() -> None:
    """A deliberate control on the ordering: while the free interaction is unspent, no
    `utilize:` key is offered, because paying for what is free would be the engine charging
    the Action for nothing."""
    offered = keys(encounter())
    assert any(k.startswith("interact:") for k in offered)
    assert not any(k.startswith("utilize:") for k in offered)


# --- the key, and the disclosure --------------------------------------------------------


def test_an_interaction_key_round_trips_ids_containing_colons() -> None:
    key = interaction_key(VERB_EQUIP, "a%b:c", utilize=True)
    assert interaction_declared(key) == (VERB_EQUIP, "a%b:c", True)
    assert interaction_declared("attack:fixture:blade:boar") is None
    assert interaction_declared(None) is None


def test_the_cap_is_disclosed_as_the_engines() -> None:
    situation = read(encounter(), "pc").situation
    assert situation is not None
    assert OBJECT_INTERACTION_CAP in situation.unenforced_clauses


def test_a_declaration_that_is_not_an_interaction_is_refused(tmp_path: Path) -> None:
    state = encounter()
    with pytest.raises(ValueError, match="not an object interaction"):
        object_interaction_resolver()(
            state=state,
            declaration=Declaration(
                actor_id="pc",
                intent=Intent(action_key="attack:fixture:blade:boar"),
                rule_id=INTERACT_RULE.id,
            ),
            facts={},
        )
