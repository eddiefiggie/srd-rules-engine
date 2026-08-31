"""p. 184's Knocking Out a Creature: the blow that leaves a target at 1 rather than 0 (#428).

> When you would reduce a creature to 0 Hit Points with a **melee attack**, you can instead
> reduce the creature to 1 Hit Point. The creature then has the **Unconscious** condition and
> starts a Short Rest.

**Two clauses of p. 17 stop applying, and neither needed a branch.** Monster Death fires "the
instant it drops to 0 Hit Points" and Massive Damage begins "when damage reduces a character
to 0 Hit Points" — a subdued creature is at **1**, so neither precondition is met and both
fall out of the arithmetic. That is the document's reading rather than an exemption invented
here, and it is why a subduing blow can knock out a *monster*: p. 184 says "a creature".

**What is not built** is the recovery clause — "remains Unconscious until it regains any Hit
Points or until someone uses an action to administer first aid" — because p. 191's Unconscious
entry states its effects and never when it ends, so honouring p. 184's ending needs the
condition to know it came from being knocked out. `Conditions.applied` is a bare
`frozenset[Condition]` and carries no cause (#429).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    Condition,
    Declaration,
    EncounterState,
    Intent,
    Ledger,
    Status,
    Weapon,
    attack_resolver,
    read,
)
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import subdue_attack_key
from srd_rules_engine.core.rules import Rule, RuleProvenance, load_fixture_ruleset
from srd_rules_engine.memory.store import JsonMemoryStore

STRIKE = Rule(
    id="fixture-strike",
    summary="An attack.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented; the mechanism is what is under test.",
)
RULESET = load_fixture_ruleset("knocking-out", (STRIKE,))

#: A big die, so a hit reliably takes a low-hit-point target past 0.
CLUB = Weapon(
    id="fixture:club",
    damage_dice=4,
    damage_sides=12,
    damage_type=DamageType.BLUDGEONING,
    ability="str",
)
BOW = Weapon(
    id="fixture:bow",
    damage_dice=4,
    damage_sides=12,
    melee=False,
    damage_type=DamageType.PIERCING,
    ability="dex",
    normal_range=80,
    long_range=320,
)


def _attacker(weapon: Weapon = CLUB) -> Combatant:
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=30,
        max_hit_points=30,
        armour_class=13,
        abilities={"str": 18, "dex": 18},
        proficiency_bonus=3,
        position=Position(0, 0, 0),
        equipment=(Carried(weapon, Carriage.HELD),),
        weapon_proficiencies=frozenset({weapon.id}),
    )


def _encounter(*, hp: int = 3, maximum: int = 40, player: bool = False) -> EncounterState:
    victim = Combatant(
        id="boar",
        name="Boar",
        hit_points=hp,
        max_hit_points=maximum,
        armour_class=1,
        abilities={"str": 12, "dex": 10, "con": 10},
        proficiency_bonus=2,
        position=Position(5, 0, 0),
        is_player_character=player,
    )
    return EncounterState.new([_attacker(), victim]).with_initiative({"pc": 20, "boar": 5})


def _swing(path: Path, state: EncounterState, *, key: str, seed: int = 3):  # type: ignore[no-untyped-def]
    path.mkdir(parents=True, exist_ok=True)
    adjudicator = Adjudicator(
        ruleset=RULESET,
        resolvers={STRIKE.id: attack_resolver()},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: seed,
    )
    offered = read(state, "pc")
    return adjudicator.adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=key),
            rule_id=STRIKE.id,
            alternatives=offered.actions,
            read_token=offered.token,
        ),
    )


# --- The rule -----------------------------------------------------------------------------


def test_a_subduing_blow_leaves_the_target_at_one_hit_point(tmp_path: Path) -> None:
    """p. 184's whole sentence: reduced to 1 instead of 0, and Unconscious."""
    _, state = _swing(tmp_path, _encounter(), key=subdue_attack_key(CLUB.id, "boar"))
    victim = state.combatant("boar")

    assert victim.hit_points == 1
    assert Condition.UNCONSCIOUS in victim.conditions.held


def test_an_ordinary_blow_still_kills(tmp_path: Path) -> None:
    """The control, and the reason the option is on the menu at all: without it the same
    swing takes the creature to 0, and p. 17 kills the monster outright."""
    from srd_rules_engine.core.read_surface import attack_key

    _, state = _swing(tmp_path, _encounter(), key=attack_key(CLUB.id, "boar"))
    victim = state.combatant("boar")

    assert victim.hit_points == 0
    assert Condition.UNCONSCIOUS not in victim.conditions.held


# --- p. 17 stops applying, without a branch -----------------------------------------------


def test_a_monster_is_knocked_out_rather_than_killed(tmp_path: Path) -> None:
    """p. 17's Monster Death is "the instant it drops to 0 Hit Points", and a subdued monster
    is at 1 — so it never fires. p. 184 says "a **creature**", not "a character", so this is
    the document's reading rather than an exemption invented here."""
    _, state = _swing(tmp_path, _encounter(player=False), key=subdue_attack_key(CLUB.id, "boar"))

    assert not state.combatant("boar").death_saves.dead
    assert state.combatant("boar").hit_points == 1


def test_massive_damage_does_not_kill_a_subdued_character(tmp_path: Path) -> None:
    """p. 17's Massive Damage begins "when damage reduces a character to 0 Hit Points". A
    subdued character is at 1, so the precondition is never met — and the remainder that
    would otherwise have killed them is never computed.

    The maximum is 4 here, so an ordinary blow of this size would kill outright."""
    _, state = _swing(
        tmp_path,
        _encounter(hp=3, maximum=4, player=True),
        key=subdue_attack_key(CLUB.id, "boar"),
    )
    victim = state.combatant("boar")

    assert not victim.death_saves.dead, "p. 17 needs a reduction to 0, and there was none"
    assert victim.hit_points == 1


# --- What p. 184 does not say -------------------------------------------------------------


def test_a_creature_already_at_zero_is_not_healed_to_one() -> None:
    """p. 184 is "when you **would reduce** a creature to 0 Hit Points". A creature already
    there is not being reduced to 0 by this blow, so the choice is simply unavailable — and a
    bare floor of 1 would silently *heal* it, which is the bug this is written against.

    Asserted against `with_damage` rather than through a swing, and the first attempt was
    **vacuous** for exactly that reason: the read surface does not offer an attack on a
    creature that `is_down`, so the declaration was rejected and no blow ever landed. The
    test passed while asserting nothing, and stayed green when `before > 0` was deleted.

    Reaching the state another way is not a contrivance — `with_damage` is public, p. 18
    charges a death-save failure for damage at 0 hit points, and something has to be able to
    deal it."""
    down = _encounter(hp=0, player=True)

    hurt = down.with_damage("boar", 9, subduing=True).combatant("boar")

    assert hurt.hit_points == 0, "not healed to 1 by being hit"
    assert Condition.UNCONSCIOUS not in hurt.conditions.held, "and not knocked out by it"


def test_a_blow_that_does_not_reach_zero_is_an_ordinary_blow(tmp_path: Path) -> None:
    """The floor applies only when the damage would have reached 0. A subduing swing against
    a healthy creature just hurts it."""
    _, state = _swing(
        tmp_path, _encounter(hp=200, maximum=200), key=subdue_attack_key(CLUB.id, "boar")
    )
    victim = state.combatant("boar")

    assert 0 < victim.hit_points < 200
    assert Condition.UNCONSCIOUS not in victim.conditions.held, "it is still on its feet"


# --- Melee only ----------------------------------------------------------------------------


def test_the_menu_offers_it_for_melee_and_not_for_a_bow() -> None:
    """p. 184: "with a **melee attack**". Offering it for a bow would be a rule the document
    does not state."""
    melee = read(_encounter(), "pc").keys
    assert subdue_attack_key(CLUB.id, "boar") in melee

    ranged = EncounterState.new([_attacker(BOW), _encounter().combatant("boar")]).with_initiative(
        {"pc": 20, "boar": 5}
    )
    assert subdue_attack_key(BOW.id, "boar") not in read(ranged, "pc").keys


def test_the_read_surface_rejects_a_ranged_subduing_declaration(tmp_path: Path) -> None:
    """First line: the key was never offered, so the declaration is refused against the
    alternatives it was given (R18) and never reaches a resolver."""
    ranged = EncounterState.new([_attacker(BOW), _encounter().combatant("boar")]).with_initiative(
        {"pc": 20, "boar": 5}
    )

    ruling, _ = _swing(tmp_path, ranged, key=subdue_attack_key(BOW.id, "boar"))

    assert ruling.status is Status.REJECTED


def test_the_resolver_refuses_it_too_if_something_reaches_it() -> None:
    """Second line, tested where it lives.

    `Adjudicator.adjudicate` re-derives legality itself, so the read surface refuses this
    before any resolver runs and the guard below is unreachable through the public path. It
    is kept and unit-tested rather than deleted, for `_push`'s reason: a resolver is a
    function, the engine ships it, and a consumer calling one directly gets no read surface
    at all. What is *not* claimed is that this fires during a session — it does not, and
    `test_the_read_surface_rejects_a_ranged_subduing_declaration` is what does.
    """
    ranged = EncounterState.new([_attacker(BOW), _encounter().combatant("boar")]).with_initiative(
        {"pc": 20, "boar": 5}
    )

    with pytest.raises(ValueError, match="melee attack"):
        attack_resolver()(
            state=ranged,
            declaration=Declaration(
                actor_id="pc",
                intent=Intent(action_key=subdue_attack_key(BOW.id, "boar")),
                rule_id=STRIKE.id,
            ),
            facts={},
        )
