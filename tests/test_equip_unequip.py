"""p. 177's one equip or unequip, ridden on the attack that permits it (#283, 0042).

> **Equipping and Unequipping Weapons.** You can either equip or unequip one weapon when you
> make an attack as part of this action. You do so either before or after the attack. If you
> equip a weapon before an attack, you don't need to use it for that attack. Equipping a
> weapon includes drawing it from a sheath or picking it up. Unequipping a weapon includes
> sheathing, stowing, or dropping it.

Three things here are easy to get wrong, and each has a test below:

* **The swap is licensed by *making an attack*.** A creature that does not attack does not
  swap a weapon, so there is no standalone equip action — 0042 clause 1, and the reason
  Option 3 was rejected.
* **"Before or after" is not a field.** It decides one thing — whether the newly equipped
  weapon is available to *this* attack — and the pair `(attack weapon, equipped item)` is
  equal in exactly that case (0042 clause 2). The enumeration has to be able to *produce*
  the equal pair, which is the bug the build found.
* **p. 177 gives three destinations and the engine has two shapes.** Sheathing and stowing
  are a carriage change; dropping leaves the creature and is 0041's detachment.
"""

from __future__ import annotations

from dataclasses import replace
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
    Item,
    Ledger,
    Rule,
    RuleProvenance,
    Weapon,
    attack_resolver,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.equipment import DetachedObject
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import (
    ATTACK_DROP,
    ATTACK_EQUIP,
    ATTACK_STOW,
    OBJECT_INTERACTION_CAP,
    attack_swap_declared,
    attack_swap_key,
)
from srd_rules_engine.memory.store import JsonMemoryStore

BLADE = Weapon(id="fixture:blade", damage_dice=1, damage_sides=6, hands_when_held=1)
AXE = Weapon(id="fixture:axe", damage_dice=1, damage_sides=8, hands_when_held=1)
ROCK = Item(id="fixture:rock", weight=2.0, hands_when_held=1)

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no weapon table ships here.",
)
RULESET = load_fixture_ruleset("equip", [STRIKE])


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


def carriage_of(state: EncounterState, item_id: str) -> Carriage | None:
    for carried in state.combatant("pc").equipment:
        if carried.item.id == item_id:
            return carried.carriage
    return None


# --- the key encoding -------------------------------------------------------------------


def test_a_swap_key_round_trips_ids_containing_colons() -> None:
    """`attack_declared` parses from the right because a weapon id may contain colons while a
    combatant id is one segment — which works for exactly **one** multi-segment field. A swap
    key carries two item ids, so the boundary stops being recoverable and the segments are
    escaped instead. `fixture:blade` is an ordinary id in this very file."""
    key = attack_swap_key("fixture:blade", "boar", "a%b:c", swap=ATTACK_EQUIP)
    assert attack_swap_declared(key) == ("fixture:blade", "boar", "a%b:c", ATTACK_EQUIP)


def test_a_plain_attack_key_is_not_a_swap() -> None:
    assert attack_swap_declared("attack:fixture:blade:boar") is None
    assert attack_swap_declared(None) is None


# --- what is offered (0042 clause 3) ----------------------------------------------------


def test_each_destination_gets_its_own_offer() -> None:
    """p. 177 names three — sheathing, stowing, dropping — and the engine has two shapes for
    them. Collapsing the last two would give two offers one key, which is the bug this
    enumeration had before the prefixes were split."""
    offered = keys(encounter())
    assert attack_swap_key(BLADE.id, "boar", BLADE.id, swap=ATTACK_STOW) in offered
    assert attack_swap_key(BLADE.id, "boar", BLADE.id, swap=ATTACK_DROP) in offered
    # The **list**, not the set `keys()` returns — a set cannot express a duplicate, so
    # comparing its length to its own is an assertion that can never fail. Collapsing the
    # two destinations onto one prefix is exactly what this has to catch.
    emitted = [action.key for action in read(encounter(), "pc").actions]
    assert len(emitted) == len(set(emitted)), f"duplicate offer keys: {emitted}"


def test_a_stowed_weapon_can_be_drawn_and_used_in_the_same_attack() -> None:
    """0042 clause 2's equal pair, and the case the first enumeration could not express.

    p. 177: "If you equip a weapon before an attack, you **don't need to use it** for that
    attack." *Don't need to* is what makes using it optional and therefore permitted, so an
    enumeration that only ever pairs a drawn weapon with a *different* attack weapon cannot
    encode the ordering 0042 says the pair encodes.
    """
    assert attack_swap_key(AXE.id, "boar", AXE.id, swap=ATTACK_EQUIP) in keys(encounter())


def test_a_drawn_weapon_may_also_go_unused() -> None:
    """The other half of the same sentence: draw the axe, swing the blade."""
    assert attack_swap_key(BLADE.id, "boar", AXE.id, swap=ATTACK_EQUIP) in keys(encounter())


def test_a_held_weapon_is_not_offered_as_something_to_draw() -> None:
    """You cannot draw what is already in your hand."""
    assert attack_swap_key(BLADE.id, "boar", BLADE.id, swap=ATTACK_EQUIP) not in keys(encounter())


def test_a_reachable_object_can_be_picked_up_and_an_unplaced_one_cannot() -> None:
    """0041 clause 4's accepted cost, arriving where a player meets it (0042 clause 5).

    An object no rule placed is not reachable, so it is not on the menu — and `Situation`
    reports it under `unplaced_objects` so the gap reads as *nobody said where it fell*
    rather than as an empty menu (#267).
    """
    state = encounter(
        detached_objects=(
            DetachedObject(ROCK, Position(5, 0, 0)),
            DetachedObject(Item(id="fixture:lost")),
        )
    )
    offered = keys(state)
    assert attack_swap_key(BLADE.id, "boar", ROCK.id, swap=ATTACK_EQUIP) in offered
    assert attack_swap_key(BLADE.id, "boar", "fixture:lost", swap=ATTACK_EQUIP) not in offered
    situation = read(state, "pc").situation
    assert situation is not None
    assert situation.unplaced_objects == ("fixture:lost",)


def test_a_picked_up_rock_is_equippable_but_not_attackable_with() -> None:
    """p. 183 makes a swung rock an improvised weapon dealing "1d4 damage of a type the GM
    thinks is appropriate" — a person's judgement this engine may not invent (#264). So a
    non-weapon object may be picked up beside an attack and never *be* the attack."""
    state = encounter(detached_objects=(DetachedObject(ROCK, Position(5, 0, 0)),))
    assert attack_swap_key(ROCK.id, "boar", ROCK.id, swap=ATTACK_EQUIP) not in keys(state)


# --- what a ruling does (0042 clauses 1 and 4) ------------------------------------------


def test_drawing_and_swinging_the_axe_leaves_it_held(tmp_path: Path) -> None:
    """The equip resolves **before** the attack, because the attack names a weapon the
    creature is not yet holding. Derived rather than declared — 0042 clause 2 one level
    down."""
    state = encounter()
    ruling, after = build(tmp_path).adjudicate(
        state, declare(state, attack_swap_key(AXE.id, "boar", AXE.id, swap=ATTACK_EQUIP))
    )
    assert carriage_of(after, AXE.id) is Carriage.HELD
    assert ruling.result is not None
    assert EffectKind.CARRIAGE_CHANGED in {e.kind for e in ruling.effects}


def test_stowing_after_the_attack_leaves_the_blade_stowed(tmp_path: Path) -> None:
    state = encounter()
    _ruling, after = build(tmp_path).adjudicate(
        state, declare(state, attack_swap_key(BLADE.id, "boar", BLADE.id, swap=ATTACK_STOW))
    )
    assert carriage_of(after, BLADE.id) is Carriage.STOWED


def test_dropping_routes_through_detachment_and_lands_unplaced(tmp_path: Path) -> None:
    """p. 177's third destination leaves the creature entirely (0041 clause 2), and the object
    arrives with no position because p. 177 does not say where it goes (0041 clause 4)."""
    state = encounter()
    _ruling, after = build(tmp_path).adjudicate(
        state, declare(state, attack_swap_key(BLADE.id, "boar", BLADE.id, swap=ATTACK_DROP))
    )
    assert carriage_of(after, BLADE.id) is None
    assert [o.item.id for o in after.detached_objects] == [BLADE.id]
    assert after.detached_objects[0].position is None


def test_picking_up_a_rock_takes_it_out_of_the_encounter(tmp_path: Path) -> None:
    state = encounter(detached_objects=(DetachedObject(ROCK, Position(5, 0, 0)),))
    _ruling, after = build(tmp_path).adjudicate(
        state, declare(state, attack_swap_key(BLADE.id, "boar", ROCK.id, swap=ATTACK_EQUIP))
    )
    assert after.detached_objects == ()
    assert carriage_of(after, ROCK.id) is Carriage.HELD


def test_the_swap_happens_whether_or_not_the_attack_lands(tmp_path: Path) -> None:
    """p. 177 licenses the swap by *making* an attack, not by hitting — so it rides in
    `Proposal.always` beside the action charge rather than in a hit branch."""
    state = encounter(actor=fighter(abilities={"str": 1, "dex": 1}))
    armoured = replace(state.combatant("boar"), armour_class=30)
    state = replace(state, combatants=(state.combatant("pc"), armoured))
    ruling, after = build(tmp_path, seed=1).adjudicate(
        state, declare(state, attack_swap_key(BLADE.id, "boar", BLADE.id, swap=ATTACK_DROP))
    )
    assert ruling.result is not None and not ruling.result.succeeded
    assert [o.item.id for o in after.detached_objects] == [BLADE.id]


# --- 0042 clause 6: the silence, disclosed -----------------------------------------------


def test_the_cap_is_disclosed_as_the_engines_rather_than_the_documents() -> None:
    """0045 clause 1, and R32.

    p. 13 grants one object interaction a turn; p. 177 grants one weapon swap per attack.
    **The document never states their relationship**, so the engine takes the intersection —
    one, whichever route spends it — and says the cap is its own.

    This replaces `free-object-interaction-unmodelled`, which disclosed the silence while
    nothing else could spend an interaction. #288 built p. 13's route, which made the two
    readings distinguishable in play, and a disclosure a reader can catch the engine
    contradicting is a way of not deciding (0045 Options, rejecting Option 3).
    """
    situation = read(encounter(), "pc").situation
    assert situation is not None
    assert OBJECT_INTERACTION_CAP in situation.unenforced_clauses
