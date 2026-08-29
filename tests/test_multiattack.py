"""p. 257's Multiattack: one Action, several attack rolls, and one swap (#289, 0043).

> **Multiattack.** Some creatures can make more than one attack **when they take the Attack
> action**. Such creatures have the Multiattack entry in the "Actions" section of their stat
> block. This entry details the attacks a creature can make, as well as any additional
> abilities it can use, **as part of the Attack action**.

Three things here are easy to get wrong:

* **It is the Attack action, not a second one.** So the Action is spent once and buys every
  roll — the line `attack_resolver` carried a comment about since the economy landed.
* **"Rolls remain" is not the same question as "the Action bought them."** A creature that
  spent its Action on Dodge has rolls remaining by arithmetic and no Attack action to
  continue, which is a bug this file caught during the build.
* **p. 89's extra Light attack is a Bonus Action**, so it is an attack roll and not one of
  p. 257's — a separate action, which is exactly why #271's Loading cap still has nothing to
  bite on here.
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
from srd_rules_engine.core.read_surface import (
    ATTACK_STOW,
    SWAP_CAP_IS_THE_ENGINES,
    attack_swap_key,
)
from srd_rules_engine.memory.store import JsonMemoryStore

BLADE = Weapon(id="fixture:blade", damage_dice=1, damage_sides=6, hands_when_held=1)
AXE = Weapon(id="fixture:axe", damage_dice=1, damage_sides=8, hands_when_held=1)

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no weapon table ships here.",
)
RULESET = load_fixture_ruleset("multiattack", [STRIKE])


def brute(multiattack: Multiattack | None = None, **kw: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 30,
        "max_hit_points": 30,
        "armour_class": 13,
        "abilities": {"str": 16, "dex": 12},
        "proficiency_bonus": 2,
        "position": Position(0, 0, 0),
        "hands": 2,
        "equipment": (Carried(BLADE, Carriage.HELD), Carried(AXE, Carriage.STOWED)),
        "weapon_proficiencies": frozenset({BLADE.id, AXE.id}),
        "multiattack": multiattack,
    }
    fields.update(kw)
    return Combatant(**fields)  # type: ignore[arg-type]


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


def encounter(multiattack: Multiattack | None = None, **kw: object) -> EncounterState:
    return EncounterState.new([brute(multiattack, **kw), boar()]).with_initiative(
        {"pc": 20, "boar": 5}
    )


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


def swing(state: EncounterState, path: Path, weapon: Weapon = BLADE) -> EncounterState:
    _ruling, after = build(path).adjudicate(state, declare(state, attack_key(weapon.id, "boar")))
    return after


# --- clause 1: one Action, several rolls ------------------------------------------------


def test_one_action_buys_three_rolls_and_then_the_menu_closes(tmp_path: Path) -> None:
    """p. 257. The Action is spent once; the rolls it bought are counted down."""
    state = encounter(Multiattack(attacks=3))
    for expected in (3, 2, 1):
        assert state.attacks_remaining("pc") == expected
        assert any(k.startswith("attack:") for k in keys(state))
        state = swing(state, tmp_path / f"r{expected}")
    assert state.attacks_remaining("pc") == 0
    assert not any(k.startswith("attack:") for k in keys(state))


def test_the_action_is_charged_once_not_per_roll(tmp_path: Path) -> None:
    """The line `attack_resolver` has carried a comment about since the economy landed:
    "a feature that gives you more than one attack as part of the Attack action would need
    the Action charged once for several rolls\"."""
    state = encounter(Multiattack(attacks=2))
    first, after = build(tmp_path / "a").adjudicate(
        state, declare(state, attack_key(BLADE.id, "boar"))
    )
    assert EffectKind.ACTION_SPENT in {e.kind for e in first.effects}
    second, _ = build(tmp_path / "b").adjudicate(
        after, declare(after, attack_key(BLADE.id, "boar"))
    )
    assert EffectKind.ACTION_SPENT not in {e.kind for e in second.effects}
    assert EffectKind.ATTACK_MADE in {e.kind for e in second.effects}


def test_a_creature_with_no_multiattack_still_gets_exactly_one(tmp_path: Path) -> None:
    """The pre-existing behaviour, written as a special case of the general one — a ruleset
    that says nothing keeps exactly what it had."""
    state = encounter()
    assert state.attacks_remaining("pc") == 1
    state = swing(state, tmp_path / "one")
    assert state.attacks_remaining("pc") == 0
    assert not any(k.startswith("attack:") for k in keys(state))


def test_rolls_remaining_is_not_permission_to_attack() -> None:
    """The bug this file caught during the build.

    `attacks_remaining` counts rolls and cannot say what the Action bought. A creature that
    spent its Action on something else has rolls remaining by arithmetic and no Attack action
    to continue — so the offer turns on having *already attacked* this turn.
    """
    spent = encounter(Multiattack(attacks=3), actions=ActionBudget().spend(ActionKind.ACTION))
    assert spent.attacks_remaining("pc") == 3
    assert not any(k.startswith("attack:") for k in keys(spent))


def test_the_tally_clears_when_the_turn_advances(tmp_path: Path) -> None:
    state = swing(encounter(Multiattack(attacks=2)), tmp_path / "t")
    assert state.attacks_this_turn.get("pc") == 1
    assert state.advanced_turn().attacks_this_turn.get("pc", 0) == 0


# --- clause 2: which weapons may fill the rolls -----------------------------------------


def test_a_multiattack_that_names_weapons_restricts_the_rolls() -> None:
    """p. 257: the entry "details the attacks a creature can make"."""
    state = encounter(Multiattack(attacks=2, permitted=frozenset({AXE.id})))
    assert attack_key(BLADE.id, "boar") not in keys(state)


def test_naming_no_weapons_permits_any_held_one() -> None:
    """Empty means *any*, not *none* — the reading that refuses nothing for a ruleset that
    stated a count and no list. "None may" would make the entry unusable."""
    state = encounter(Multiattack(attacks=2))
    assert attack_key(BLADE.id, "boar") in keys(state)


# --- clause 3: one swap per turn, and the cap is the engine's ---------------------------


def test_a_second_swap_is_refused_however_many_attacks_remain(tmp_path: Path) -> None:
    """0043 clause 3, and the whole reason this record was needed.

    p. 177 grants one swap **per attack** and p. 13 one object interaction **per turn**, and
    nothing composes them. One swap is legal under both readings; two under only one. The
    engine offers the intersection.
    """
    # **Both weapons held**, and that detail is load-bearing. An earlier version of this test
    # stowed the creature's only weapon, which left it holding nothing — so no attack was
    # offered, so `_swaps` was never reached, and the assertion passed without the cap
    # existing at all. The corruption proof caught it: removing the cap left the test green.
    state = encounter(
        Multiattack(attacks=3),
        equipment=(Carried(BLADE, Carriage.HELD), Carried(AXE, Carriage.HELD)),
    )
    swap = attack_swap_key(BLADE.id, "boar", AXE.id, swap=ATTACK_STOW)
    assert swap in keys(state)
    _ruling, after = build(tmp_path).adjudicate(state, declare(state, swap))
    assert "pc" in after.swaps_this_turn
    assert after.attacks_remaining("pc") == 2, "rolls remain"
    assert any(k.startswith("attack:") for k in keys(after)), "and the blade is still in hand"
    assert not any(k.startswith("attack-") for k in keys(after)), "and no second swap"


def test_the_cap_is_disclosed_as_the_engines_rather_than_the_documents() -> None:
    """R32. An agent shown one swap and refused a second is entitled to know the cap was
    decided here — 0043 clause 3 is an intersection of two readings, not a printed rule."""
    situation = read(encounter(Multiattack(attacks=3)), "pc").situation
    assert situation is not None
    assert SWAP_CAP_IS_THE_ENGINES in situation.unenforced_clauses


def test_unconsciouss_drop_does_not_spend_the_swap_allowance(tmp_path: Path) -> None:
    """p. 191 detaches an item too, and the creature never chose to. Spending p. 177's
    allowance on it would refuse a swap the rules permit — which is why `WEAPON_SWAPPED` is
    its own effect rather than inferred from the carriage change beside it."""
    from srd_rules_engine.core.adjudicate import _apply, condition_applied
    from srd_rules_engine.core.conditions import Condition

    state = encounter(Multiattack(attacks=3))
    after, _landed, _withheld = _apply(
        state,
        (condition_applied("pc", Condition.UNCONSCIOUS, description="struck senseless"),),
        seed=1,
    )
    assert after.detached_objects, "p. 191 dropped the blade"
    assert "pc" not in after.swaps_this_turn


def test_the_swap_record_clears_when_the_turn_advances(tmp_path: Path) -> None:
    state = encounter(Multiattack(attacks=2))
    _ruling, after = build(tmp_path).adjudicate(
        state,
        declare(state, attack_swap_key(BLADE.id, "boar", BLADE.id, swap=ATTACK_STOW)),
    )
    assert "pc" in after.swaps_this_turn
    assert "pc" not in after.advanced_turn().swaps_this_turn


# --- the type refuses what a reader could not read correctly ----------------------------


def test_a_multiattack_buys_at_least_one_roll() -> None:
    import pytest

    with pytest.raises(ValueError, match="at least one attack roll"):
        Multiattack(attacks=0)
