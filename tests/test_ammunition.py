"""p. 89's Ammunition property: a thing there can be twenty of (#273, 0044).

> **Ammunition.** You can use a weapon that has the Ammunition property to make a ranged
> attack **only if you have ammunition to fire from it**. The type of ammunition required is
> specified with the weapon's range. **Each attack expends one piece of ammunition.** Drawing
> the ammunition is part of the attack (you need a free hand to load a one-handed weapon).
> After a fight, you can spend 1 minute to recover half the ammunition (round down) you used
> in the fight; the rest is lost.

Four things here are easy to get wrong:

* **The count is a fact about the creature, not the item** (0044 clause 1). It rides on
  `Carried`, where `proficient` and the grip both ended up after being fields on `Weapon`.
* **Having ammunition is a condition of the attack**, so it is legality rather than a refusal
  after the fact — the shot is not offered.
* **An unknown hand count does not block the load.** `Combatant.__post_init__` already settles
  that direction: "an unstated count cannot be exceeded (R31)."
* **The used-tally only ever rises**, because p. 89 recovers half of what was *used* and that
  is not derivable from what remains.
"""

from __future__ import annotations

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
    attack_key,
    attack_resolver,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.equipment import Multiattack
from srd_rules_engine.core.position import Position
from srd_rules_engine.memory.store import JsonMemoryStore

BOLT = Item(id="fixture:bolt", weight=0.075)
#: Two-handed, so the free-hand clause is out of the way except where it is the subject.
BOW = Weapon(
    id="fixture:bow",
    damage_dice=1,
    damage_sides=8,
    melee=False,
    ammunition_id=BOLT.id,
    normal_range=80,
    long_range=320,
    hands_when_held=2,
)
#: One-handed, which is the case p. 89's parenthesis is about.
HAND_BOW = Weapon(
    id="fixture:hand-bow",
    damage_dice=1,
    damage_sides=6,
    melee=False,
    ammunition_id=BOLT.id,
    normal_range=30,
    long_range=120,
    hands_when_held=1,
)
#: No Ammunition property, so the refusals below are shown to be the property's doing.
SLING = Weapon(
    id="fixture:sling",
    damage_dice=1,
    damage_sides=4,
    melee=False,
    normal_range=30,
    long_range=120,
    hands_when_held=1,
)
SHIELD = Item(id="fixture:shield", weight=6.0, hands_when_held=1)

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no weapon table ships here.",
)
RULESET = load_fixture_ruleset("ammunition", [STRIKE])


def archer(
    *,
    carried: tuple[Carried, ...] = (),
    hands: int | None = 2,
    multiattack: Multiattack | None = None,
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
        hands=hands,
        equipment=carried or (Carried(BOW, Carriage.HELD), Carried(BOLT, quantity=2)),
        weapon_proficiencies=frozenset({BOW.id, HAND_BOW.id, SLING.id}),
        multiattack=multiattack,
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
    return EncounterState.new([actor or archer(), boar()]).with_initiative({"pc": 20, "boar": 5})


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


def shoot(state: EncounterState, path: Path, weapon: Weapon = BOW) -> EncounterState:
    _ruling, after = build(path).adjudicate(state, declare(state, attack_key(weapon.id, "boar")))
    return after


# --- the count, and where it lives (0044 clause 1) --------------------------------------


def test_a_count_rides_on_the_relation_not_on_the_item() -> None:
    """Two creatures may hold different numbers of the same thing, which is what makes a count
    a fact about the having. `Item` carries no quantity at all."""
    assert "quantity" not in Item.__dataclass_fields__
    assert Carried(BOLT, quantity=20).quantity == 20
    assert Carried(BOLT).quantity == 1, "one, because carrying means having it"


def test_carrying_nought_of_something_is_refused() -> None:
    """Spending the last piece removes the entry, so a zero here would describe carrying
    nought of a thing."""
    with pytest.raises(ValueError, match="one or more of a thing"):
        Carried(BOLT, quantity=0)


# --- firing (clauses 2 and 3) -----------------------------------------------------------


def test_each_attack_expends_one_piece(tmp_path: Path) -> None:
    state = encounter()
    assert state.ammunition_for("pc", BOLT.id) == 2
    after = shoot(state, tmp_path)
    assert after.ammunition_for("pc", BOLT.id) == 1


def test_the_last_piece_takes_its_entry_with_it(tmp_path: Path) -> None:
    state = encounter(archer(multiattack=Multiattack(attacks=3)))
    after = shoot(shoot(state, tmp_path / "a"), tmp_path / "b")
    assert after.ammunition_for("pc", BOLT.id) == 0
    assert [c.item.id for c in after.combatant("pc").equipment] == [BOW.id]


def test_the_shot_is_not_offered_without_ammunition(tmp_path: Path) -> None:
    """p. 89 makes having it a condition of the attack, so this is legality (R18) rather than
    a refusal after the fact — and the rolls the Action bought still remain."""
    state = encounter(archer(multiattack=Multiattack(attacks=4)))
    after = shoot(shoot(state, tmp_path / "a"), tmp_path / "b")
    assert after.attacks_remaining("pc") == 2, "the Action still has rolls left"
    assert attack_key(BOW.id, "boar") not in keys(after), "and none of them is this"


def test_a_weapon_without_the_property_is_unaffected() -> None:
    """Which shows the refusal is Ammunition's doing rather than the range's.

    **A deliberate control, and it covers nothing on its own** — it stayed green under all
    four corruption proofs, because no corruption of the ammunition path can change what a
    weapon without the property does. Named rather than left to look like coverage
    ([#298](https://github.com/eddiefiggie/srd-rules-engine/issues/298)).
    """
    state = encounter(archer(carried=(Carried(SLING, Carriage.HELD),)))
    assert attack_key(SLING.id, "boar") in keys(state)


def test_firing_what_is_not_there_is_refused() -> None:
    """The transition refuses too, below the legality that stops it being offered."""
    with pytest.raises(ValueError, match="no 'fixture:bolt' to fire"):
        encounter(archer(carried=(Carried(BOW, Carriage.HELD),))).with_ammunition_spent(
            "pc", BOLT.id
        )


def test_the_piece_is_spent_on_a_miss_too(tmp_path: Path) -> None:
    """p. 89 does not return the arrow on a miss, so the cost rides in `always` rather than in
    a hit branch."""
    state = encounter(archer(carried=(Carried(BOW, Carriage.HELD), Carried(BOLT, quantity=1))))
    armoured = Combatant(**{**vars(state.combatant("boar")), "armour_class": 30})
    state = EncounterState.new([state.combatant("pc"), armoured]).with_initiative(
        {"pc": 20, "boar": 5}
    )
    ruling, after = build(tmp_path, seed=1).adjudicate(
        state, declare(state, attack_key(BOW.id, "boar"))
    )
    assert ruling.result is not None and not ruling.result.succeeded
    assert after.ammunition_for("pc", BOLT.id) == 0


def test_the_expenditure_is_its_own_recorded_effect(tmp_path: Path) -> None:
    ruling, _after = build(tmp_path).adjudicate(
        encounter(), declare(encounter(), attack_key(BOW.id, "boar"))
    )
    spent = [e for e in ruling.effects if e.kind is EffectKind.AMMUNITION_SPENT]
    assert len(spent) == 1 and spent[0].item_id == BOLT.id


# --- the free hand (clause 4) -----------------------------------------------------------


def test_a_one_handed_weapon_needs_a_free_hand_to_load() -> None:
    """p. 89: "(you need a free hand to load a one-handed weapon)". Both hands committed —
    the bow in one and a shield in the other — so there is none to load with."""
    full = archer(
        carried=(
            Carried(HAND_BOW, Carriage.HELD),
            Carried(SHIELD, Carriage.HELD),
            Carried(BOLT, quantity=5),
        )
    )
    assert full.free_hands == 0
    assert attack_key(HAND_BOW.id, "boar") not in keys(encounter(full))


def test_a_two_handed_weapon_needs_no_spare_hand() -> None:
    """The parenthesis says *one-handed*, so a bow held in both is not asking for a third."""
    state = encounter()
    assert state.combatant("pc").free_hands == 0
    assert attack_key(BOW.id, "boar") in keys(state)


def test_an_unstated_hand_count_does_not_refuse_the_shot() -> None:
    """`Combatant.__post_init__` already settles this direction for p. 90's Two-Handed: "no
    SRD rule states how many hands a creature has, so an unstated count cannot be exceeded
    (R31)." Refusing on `None` would assert the count the engine declines to assume."""
    unstated = archer(
        hands=None, carried=(Carried(HAND_BOW, Carriage.HELD), Carried(BOLT, quantity=5))
    )
    assert unstated.free_hands is None
    assert attack_key(HAND_BOW.id, "boar") in keys(encounter(unstated))


# --- the tally (clause 6) ---------------------------------------------------------------


def test_the_used_tally_counts_the_fight_and_only_rises(tmp_path: Path) -> None:
    """p. 89 recovers "half the ammunition (round down) **you used in the fight**", which is
    not derivable from what remains — a creature that started with six and holds two may have
    fired four, or fired one and dropped three."""
    state = encounter(archer(multiattack=Multiattack(attacks=3)))
    after = shoot(shoot(state, tmp_path / "a"), tmp_path / "b")
    assert after.ammunition_used[("pc", BOLT.id)] == 2


def test_the_tally_survives_the_turn_advancing(tmp_path: Path) -> None:
    """The first structure on `EncounterState` that does not clear with the turn: the six
    beside it are per-turn and this one is per-fight (0044 clause 6)."""
    after = shoot(encounter(), tmp_path)
    assert after.advanced_turn().ammunition_used[("pc", BOLT.id)] == 1
