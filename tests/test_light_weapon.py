"""p. 89's Light property: an extra attack, with a different Light weapon (#270).

> When you take the Attack action on your turn and attack with a Light weapon, you can make
> one extra attack as a Bonus Action later on the same turn. That extra attack must be made
> with a **different** Light weapon, and you don't add your ability modifier to the extra
> attack's damage **unless that modifier is negative**.

Two things here are easy to get wrong:

* **The damage exception is the whole of the damage rule.** "You don't add your ability
  modifier … unless that modifier is negative" — so a +3 is dropped and a -1 is kept. An
  implementation that simply drops the modifier is wrong for every creature with a penalty,
  and wrong in the direction that helps them.
* **"Different" means a different weapon, not a different kind.** p. 89's own example is a
  Shortsword in one hand and a Dagger in the other, so the test is the item's identity.
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
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import bonus_attack_key
from srd_rules_engine.memory.store import JsonMemoryStore

SHORTSWORD = Weapon(
    id="fixture:shortsword", damage_dice=1, damage_sides=6, light=True, hands_when_held=1
)
DAGGER = Weapon(id="fixture:dagger", damage_dice=1, damage_sides=4, light=True, hands_when_held=1)
CLUB = Weapon(id="fixture:club", damage_dice=1, damage_sides=6, hands_when_held=1)

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no weapon table ships here.",
)
RULESET = load_fixture_ruleset("light", [STRIKE])


def duellist(
    strength: int = 16, *, held: tuple[Weapon, ...] = (SHORTSWORD, DAGGER), **kw: object
) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 13,
        "abilities": {"str": strength, "dex": 12},
        "proficiency_bonus": 2,
        "position": Position(0, 0, 0),
        "hands": 2,
        "equipment": tuple(Carried(w, Carriage.HELD) for w in held),
        "weapon_proficiencies": frozenset(w.id for w in held),
        "actions": ActionBudget(bonus_action_granted=True),
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


# --- p. 89's four conditions ------------------------------------------------------------


def test_the_extra_attack_is_not_offered_before_the_attack_action(tmp_path: Path) -> None:
    """ "**When you take the Attack action** … and attack with a Light weapon" — both halves
    are conditions, and nothing is bought before the first one happens."""
    assert bonus_attack_key(DAGGER.id, "boar") not in keys(encounter())


def test_attacking_with_a_light_weapon_buys_the_extra_attack(tmp_path: Path) -> None:
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))

    assert after.light_attacks_this_turn == frozenset({("pc", SHORTSWORD.id)})
    assert bonus_attack_key(DAGGER.id, "boar") in keys(after)


def test_attacking_with_a_weapon_that_is_not_light_buys_nothing(tmp_path: Path) -> None:
    """The condition is the weapon's property, read off the weapon rather than trusted from
    the caller — which is what stops a ruleset buying the attack by asserting a property."""
    state = encounter(duellist(held=(CLUB, DAGGER)))
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(CLUB.id, "boar")))

    assert after.light_attacks_this_turn == frozenset()
    assert bonus_attack_key(DAGGER.id, "boar") not in keys(after)


def test_the_extra_attack_must_use_a_different_weapon(tmp_path: Path) -> None:
    """p. 89: "That extra attack must be made with a **different** Light weapon." The one
    just swung is off the menu; the other hand's is on it."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))

    assert bonus_attack_key(SHORTSWORD.id, "boar") not in keys(after)
    assert bonus_attack_key(DAGGER.id, "boar") in keys(after)


def test_a_second_light_weapon_must_actually_be_held(tmp_path: Path) -> None:
    """One Light weapon and one hand buys nothing to swing with."""
    lone = duellist(held=(SHORTSWORD,))
    state = encounter(lone)
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))

    assert after.light_attacks_this_turn == frozenset({("pc", SHORTSWORD.id)})
    assert not any(k.startswith("bonus-attack") for k in keys(after))


def test_it_needs_a_bonus_action_to_spend(tmp_path: Path) -> None:
    """p. 177: a Bonus Action exists only if a rule grants one, and p. 89's extra attack is
    made *as* one — so a creature without the grant buys nothing it can use."""
    ungranted = duellist(actions=ActionBudget())
    state = encounter(ungranted)
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))

    assert after.light_attacks_this_turn, "the condition was met"
    assert not any(k.startswith("bonus-attack") for k in keys(after)), "and cannot be spent"


def test_the_turn_advancing_forgets_it(tmp_path: Path) -> None:
    """ "later on the **same turn**"."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))
    assert after.advanced_turn().light_attacks_this_turn == frozenset()


# --- The damage rule, whose exception is the whole of it -----------------------------------


def _damage(proposal_effects: tuple[object, ...]) -> DamageDice:
    dice = [e for e in proposal_effects if isinstance(e, DamageDice)]
    assert len(dice) == 1
    return dice[0]


def test_a_positive_ability_modifier_is_dropped_from_the_extra_attack(tmp_path: Path) -> None:
    """p. 89: "you don't add your ability modifier to the extra attack's damage"."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))

    ordinary = attack_resolver()(
        state=state, declaration=declare(state, attack_key(SHORTSWORD.id, "boar")), facts={}
    )
    extra = attack_resolver()(
        state=after, declaration=declare(after, bonus_attack_key(DAGGER.id, "boar")), facts={}
    )
    assert _damage(ordinary.on_success).modifier == 3, "Strength 16 reaches ordinary damage"
    assert _damage(extra.on_success).modifier == 0


def test_a_negative_ability_modifier_is_kept(tmp_path: Path) -> None:
    """ "**unless that modifier is negative**" — the exception is the whole of the rule, and
    an implementation that simply dropped the modifier would be wrong for every creature with
    a penalty, in the direction that helps them."""
    feeble = duellist(strength=6)
    assert feeble.modifier("str") == -2, "precondition"

    state = encounter(feeble)
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))
    extra = attack_resolver()(
        state=after, declaration=declare(after, bonus_attack_key(DAGGER.id, "boar")), facts={}
    )
    assert _damage(extra.on_success).modifier == -2


def test_the_attack_roll_keeps_the_modifier_either_way(tmp_path: Path) -> None:
    """p. 89 drops it from the **damage**, and says nothing about the roll."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))
    extra = attack_resolver()(
        state=after, declaration=declare(after, bonus_attack_key(DAGGER.id, "boar")), facts={}
    )
    assert extra.test is not None
    assert {m.source for m in extra.test.modifiers} >= {"ability:str"}
    assert dict((m.source, m.value) for m in extra.test.modifiers)["ability:str"] == 3


# --- What the extra attack costs ------------------------------------------------------------


def test_it_spends_the_bonus_action_and_not_the_action(tmp_path: Path) -> None:
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))
    assert not after.combatant("pc").actions.available(ActionKind.ACTION)

    _, done = build(tmp_path / "b").adjudicate(
        after, declare(after, bonus_attack_key(DAGGER.id, "boar"))
    )
    budget = done.combatant("pc").actions
    assert not budget.available(ActionKind.BONUS_ACTION)


def test_the_extra_attack_buys_no_further_attack(tmp_path: Path) -> None:
    """p. 89 buys the extra attack with the **Attack action**, so the extra one buys nothing:
    "one extra attack", once."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))
    _, done = build(tmp_path / "b").adjudicate(
        after, declare(after, bonus_attack_key(DAGGER.id, "boar"))
    )
    assert done.light_attacks_this_turn == after.light_attacks_this_turn


def test_the_ledger_records_which_weapon_bought_it(tmp_path: Path) -> None:
    """R5. p. 89's condition turns on *which* weapon the Attack action was spent on, and a
    replay that could not see it could not check the extra attack was earned."""
    state = encounter()
    ruling, _ = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))
    spent = [e for e in ruling.effects if e.kind is EffectKind.ACTION_SPENT]
    assert [e.weapon_id for e in spent] == [SHORTSWORD.id]


def test_a_bonus_attack_with_a_weapon_that_is_not_light_is_refused(tmp_path: Path) -> None:
    state = encounter(duellist(held=(SHORTSWORD, CLUB)))
    _, after = build(tmp_path).adjudicate(state, declare(state, attack_key(SHORTSWORD.id, "boar")))
    with pytest.raises(ValueError, match="not a Light weapon"):
        attack_resolver()(
            state=after,
            declaration=declare(after, bonus_attack_key(CLUB.id, "boar")),
            facts={},
        )


def test_only_the_attack_action_buys_it(tmp_path: Path) -> None:
    """p. 89: "When you take the **Attack action** on your turn and attack with a Light
    weapon…" The action matters, not merely the weapon.

    Asserted against the transition directly, because every caller today passes no weapon on
    a Bonus Action — so the clause is shadowed by a convention, and a convention is what this
    engine keeps finding it cannot rely on. A corruption proof caught it: removing the check
    left the suite green.
    """
    state = encounter()
    spent = state.with_action_spent("pc", ActionKind.BONUS_ACTION, weapon_id=SHORTSWORD.id)
    assert spent.light_attacks_this_turn == frozenset(), (
        "a Bonus Action spent with a Light weapon buys nothing — p. 89 names the Attack action"
    )

    bought = state.with_action_spent("pc", ActionKind.ACTION, weapon_id=SHORTSWORD.id)
    assert bought.light_attacks_this_turn == frozenset({("pc", SHORTSWORD.id)})
