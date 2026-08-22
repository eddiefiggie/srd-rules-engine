"""Combat, which is where the invariant either holds or is obviously theatre.

Every other unit could be right and this one wrong, and the product would still be broken:
an attack is the moment an agent has the strongest reason to want a particular number. So
the tests here are mostly about *who produced the number* rather than what it was.

The seeds are found rather than written down. Dice derive from the seed, so a change to
the derivation would silently invalidate a literal and these tests would go on passing
while testing something else.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Combatant,
    DamageDice,
    Declaration,
    Effect,
    EffectKind,
    EncounterState,
    Intent,
    Ledger,
    LegalAction,
    Rule,
    RuleProvenance,
    Ruling,
    Status,
    Weapon,
    attack_key,
    attack_resolver,
    attack_target,
    initiative_order,
    legal_actions,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.adjudicate import _apply, _roll_declared
from srd_rules_engine.core.d20 import DAMAGE_OFFSET, roll
from srd_rules_engine.memory.store import JsonMemoryStore

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon, against the target's armour class.",
    provenance=RuleProvenance.FIXTURE,
    rationale=(
        "An invented weapon, because no rule value may be inferred while the official "
        "document is unverified. The mechanism is real; the numbers are declared fixture."
    ),
)

#: Invented, and labelled as such. A longsword compiled from memory would read exactly
#: like a verified one once it was inside a finished Ruling.
BLADE = Weapon(name="fixture blade", damage_dice=2, damage_sides=6, ability="str")

RULESET = load_fixture_ruleset("combat", [STRIKE])


def encounter(*, pc_ac: int = 13, boar_ac: int = 13) -> EncounterState:
    return EncounterState.new(
        [
            Combatant(
                id="pc",
                name="Pc",
                hit_points=20,
                max_hit_points=20,
                armour_class=pc_ac,
                abilities={"str": 16, "dex": 14},
                proficiency_bonus=2,
            ),
            Combatant(
                id="boar",
                name="Boar",
                hit_points=11,
                max_hit_points=11,
                armour_class=boar_ac,
                abilities={"str": 12, "dex": 10},
                proficiency_bonus=2,
            ),
        ]
    )


def build(path: Path, *, seed: int, weapon: Weapon = BLADE) -> Adjudicator:
    return Adjudicator(
        ruleset=RULESET,
        resolvers={STRIKE.id: attack_resolver(weapon)},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: seed,
    )


def strike(state: EncounterState, actor: str = "pc", target: str = "boar") -> Declaration:
    offered = read(state, actor)
    return Declaration(
        actor_id=actor,
        intent=Intent(action_key=attack_key(target)),
        rule_id=STRIKE.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def seed_that(hits: bool, state: EncounterState, tmp_path: Path) -> int:
    """The first seed whose attack lands, or misses. Found, never hardcoded."""
    for candidate in range(500):
        ruling, _ = build(tmp_path / f"probe{candidate}", seed=candidate).adjudicate(
            state, strike(state)
        )
        assert ruling.result is not None
        if ruling.result.succeeded is hits:
            return candidate
    raise AssertionError(f"no seed below 500 produced hits={hits}")


# --- Initiative ------------------------------------------------------------------------


def test_initiative_is_deterministic_from_a_recorded_seed() -> None:
    """R5. An order that cannot be reproduced makes every later turn unreplayable."""
    state = encounter()
    assert initiative_order(state, seed=7) == initiative_order(state, seed=7)
    assert initiative_order(state, seed=7) != initiative_order(state, seed=8)


def test_initiative_covers_every_combatant_and_applies_its_modifier() -> None:
    state = encounter()
    rolled = initiative_order(state, seed=7, ability="dex")
    assert set(rolled) == {"pc", "boar"}

    faces = roll(7, count=2, sides=20)
    assert rolled["pc"] == faces[0] + 2, "dex 14 is +2"
    assert rolled["boar"] == faces[1] + 0, "dex 10 is +0"


def test_the_ability_initiative_uses_is_a_parameter_not_a_constant() -> None:
    """Which ability the SRD ties initiative to is a rule with a citation (R31).

    Baking one in would be an inferred rule value wearing the same face as a verified one.
    """
    state = encounter()
    assert initiative_order(state, seed=7, ability="dex") != initiative_order(
        state, seed=7, ability="str"
    )


def test_applying_initiative_moves_the_generation() -> None:
    state = encounter()
    ordered = state.with_initiative(initiative_order(state, seed=7))
    assert ordered.generation == state.generation + 1
    assert ordered.round_number == 1


# --- Hitting and missing ---------------------------------------------------------------


def test_an_attack_meeting_the_armour_value_hits_and_one_below_it_misses(
    tmp_path: Path,
) -> None:
    """Both produce a Ruling. A miss is an outcome, not an error."""
    state = encounter()
    hit_seed = seed_that(True, state, tmp_path)
    miss_seed = seed_that(False, state, tmp_path)

    landed, _ = build(tmp_path / "hit", seed=hit_seed).adjudicate(state, strike(state))
    missed, _ = build(tmp_path / "miss", seed=miss_seed).adjudicate(state, strike(state))

    for ruling in (landed, missed):
        assert ruling.status is Status.RULED
        assert ruling.result is not None

    assert landed.result is not None and missed.result is not None
    assert landed.result.total >= state.combatant("boar").armour_class
    assert missed.result.total < state.combatant("boar").armour_class


def test_the_armour_value_is_the_targets_own_and_is_named_in_the_basis(
    tmp_path: Path,
) -> None:
    """Reading the wrong combatant's armour is a defect nothing else would catch: the roll
    still resolves, the Ruling still looks ordinary, and only the target basis shows it."""
    state = encounter(pc_ac=2, boar_ac=19)
    ruling, _ = build(tmp_path / "l", seed=1).adjudicate(state, strike(state))
    assert ruling.result is not None
    assert ruling.result.target == 19
    assert "Boar" in ruling.result.target_basis


def test_a_miss_deals_no_damage(tmp_path: Path) -> None:
    state = encounter()
    ruling, after = build(tmp_path / "m", seed=seed_that(False, state, tmp_path)).adjudicate(
        state, strike(state)
    )
    assert ruling.effects == ()
    assert after.combatant("boar").hit_points == state.combatant("boar").hit_points


# --- Damage ----------------------------------------------------------------------------


def test_damage_reduces_hit_points_and_the_read_surface_reports_the_reduced_value(
    tmp_path: Path,
) -> None:
    state = encounter()
    before = state.combatant("boar").hit_points

    ruling, after = build(tmp_path / "d", seed=seed_that(True, state, tmp_path)).adjudicate(
        state, strike(state)
    )
    dealt = ruling.effects[0].amount

    assert dealt > 0
    assert after.combatant("boar").hit_points == before - dealt
    assert after.generation > state.generation, "and the reduced value is a later generation"
    assert read(after, "pc").generation == after.generation


def test_the_resolver_declares_dice_and_never_a_total(tmp_path: Path) -> None:
    """R4, at the point of maximum temptation.

    A resolver is engine code, but it is also the seam a ruleset extends — so it must be
    unable to hand back a number it chose. It returns `DamageDice`; the engine rolls it.
    """
    state = encounter()
    proposal = attack_resolver(BLADE)(state=state, declaration=strike(state), facts={})

    assert len(proposal.on_success) == 1
    declared = proposal.on_success[0]
    assert isinstance(declared, DamageDice)
    assert not hasattr(declared, "amount")
    assert (declared.count, declared.sides) == (2, 6)


def test_damage_is_rolled_from_the_same_seed_as_the_attack(tmp_path: Path) -> None:
    """Otherwise a replay reproduces the hit and not the damage — which is worse than no
    replay, because it looks like it worked."""
    state = encounter()
    seed = seed_that(True, state, tmp_path)
    ruling, _ = build(tmp_path / "s", seed=seed).adjudicate(state, strike(state))

    assert ruling.result is not None and ruling.result.seed == seed
    faces = roll(seed, count=2, sides=6, offset=DAMAGE_OFFSET)
    assert ruling.effects[0].amount == sum(faces) + 3, "str 16 is +3"


def test_the_effect_names_the_weapon_that_dealt_the_damage(tmp_path: Path) -> None:
    """The effect description is the audit trail a reader reconstructs the fight from. A
    generic "damage: 4 + 3" leaves two weapons indistinguishable in the ledger, which is
    the point at which a replay stops settling arguments."""
    state = encounter()
    ruling, _ = build(
        tmp_path / "n", seed=seed_that(True, state, tmp_path), weapon=BLADE
    ).adjudicate(state, strike(state))

    assert ruling.effects[0].description.startswith(f"{BLADE.name}:")
    assert "2d6" in ruling.effects[0].description, "and the dice it was rolled from"


def test_damage_dice_are_drawn_clear_of_the_attack_roll(tmp_path: Path) -> None:
    """A shared index would make the damage a function of the attack roll, so a 3 on the
    d20 would mean a 3 on the damage die — invisible in any single Ruling."""
    state = encounter()
    seed = seed_that(True, state, tmp_path)
    ruling, _ = build(tmp_path / "c", seed=seed).adjudicate(state, strike(state))

    assert ruling.result is not None
    assert len(ruling.result.dice) <= DAMAGE_OFFSET


def test_two_damage_expressions_in_one_branch_do_not_share_a_die() -> None:
    """Two dice on the same indices report identical rolls, which reads as a coincidence."""
    branch = (
        DamageDice(target_id="boar", count=1, sides=6, source="first"),
        DamageDice(target_id="boar", count=1, sides=6, source="second"),
    )
    faces = roll(11, count=2, sides=6, offset=DAMAGE_OFFSET)
    settled = _roll_declared(branch, seed=11)

    assert (settled[0].amount, settled[1].amount) == faces


def test_a_stated_effect_passes_through_unrolled() -> None:
    """Not every effect is dice. A rule dealing a fixed amount stays fixed."""
    stated = Effect(kind=EffectKind.DAMAGE, target_id="boar", amount=4, description="fixed")
    assert _roll_declared((stated,), seed=11) == (stated,)


def test_a_damage_expression_cannot_be_nonsense() -> None:
    with pytest.raises(ValueError):
        DamageDice(target_id="boar", count=1, sides=0)
    with pytest.raises(ValueError):
        DamageDice(target_id="boar", count=-1, sides=6)


def test_damage_never_heals(tmp_path: Path) -> None:
    """A large negative modifier is a plausible ruleset value; a negative total is not."""
    settled = _roll_declared(
        (DamageDice(target_id="boar", count=1, sides=6, modifier=-40),), seed=3
    )
    assert settled[0].amount == 0


# --- Reaching zero ---------------------------------------------------------------------


def test_a_combatant_at_zero_is_reported_down_and_offered_no_actions() -> None:
    state = encounter().with_initiative({"boar": 18, "pc": 4})
    downed = state.with_damage("boar", 999)

    assert downed.combatant("boar").hit_points == 0, "hit points floor at 0, never negative"
    assert downed.combatant("boar").is_down
    assert legal_actions(downed, "boar") == ()


def test_a_downed_combatant_stops_being_offered_as_a_target() -> None:
    """The menu is the agent's only source of what is legal (R18). Leaving a corpse on it
    invites a declaration the engine then has to refuse."""
    state = encounter().with_initiative({"pc": 18, "boar": 4})
    assert attack_key("boar") in read(state, "pc").keys

    downed = state.with_damage("boar", 999)
    assert attack_key("boar") not in read(downed, "pc").keys


def test_the_offered_attack_states_the_armour_value_it_will_be_resolved_against() -> None:
    """R18's read surface is thick so the agent chooses from engine-supplied facts rather
    than recalling them. An option carrying only a key would send it back to its training
    for the target's armour class — and the token would commit to nothing but the name."""
    state = encounter(boar_ac=17).with_initiative({"pc": 18, "boar": 4})
    option = next(a for a in read(state, "pc").actions if a.key == attack_key("boar"))

    assert option.detail["target"] == "boar"
    assert option.detail["armour_class"] == 17
    assert option.identity() != LegalAction(key=option.key, label=option.label).identity(), (
        "the armour value is inside what the token digests, so a menu claiming a "
        "different one fails verification instead of being taken at its word"
    )


def test_attacking_a_downed_combatant_is_refused_not_resolved(tmp_path: Path) -> None:
    """R3 validates against the same derivation the read surface enumerates with, so a
    stale menu cannot be used to reach a roll the engine would not have offered."""
    state = encounter().with_initiative({"pc": 18, "boar": 4})
    stale = strike(state)
    downed = state.with_damage("boar", 999)

    ruling, unchanged = build(tmp_path / "z", seed=1).adjudicate(downed, stale)
    assert ruling.status is Status.REJECTED
    assert ruling.result is None
    assert unchanged is downed


# --- Turn order ------------------------------------------------------------------------


def test_advancing_the_turn_moves_to_the_next_combatant_and_bumps_the_generation() -> None:
    state = encounter().with_initiative({"pc": 18, "boar": 4})
    assert state.active_id == "pc"

    following = state.advanced_turn()
    assert following.active_id == "boar"
    assert following.generation == state.generation + 1
    assert following.round_number == 1


def test_the_order_wraps_into_the_next_round() -> None:
    state = encounter().with_initiative({"pc": 18, "boar": 4})
    wrapped = state.advanced_turn().advanced_turn()
    assert wrapped.active_id == "pc"
    assert wrapped.round_number == 2


def test_only_the_active_combatant_is_offered_anything() -> None:
    state = encounter().with_initiative({"pc": 18, "boar": 4})
    assert legal_actions(state, "boar") == ()
    assert legal_actions(state.advanced_turn(), "pc") == ()


# --- The Ruling is a record, not an instruction ------------------------------------------


def test_there_is_no_public_way_to_apply_a_rulings_effects() -> None:
    """ "Applying damage twice" is not guarded against — it is unrepresentable.

    Adjudication applies effects itself and returns the state it left behind. If a public
    applier existed, a caller could hand it the same Ruling twice and the state would be
    wrong with a perfectly well-formed ledger behind it. So the test is a shape assertion:
    the only applier is private and unexported, and `Ruling.effects` is data.
    """
    import srd_rules_engine.core as core

    exported = set(core.__all__)
    assert not {n for n in exported if "apply" in n.lower()}
    assert not hasattr(core, "apply")
    assert _apply.__name__.startswith("_")
    assert "effects" in Ruling.__dataclass_fields__, "effects is a data field, not a method"
    assert not callable(getattr(Ruling, "apply", None))


def test_the_state_the_ruling_returns_already_has_the_damage(tmp_path: Path) -> None:
    """So a caller has nothing left to apply, which is why there is no way to."""
    state = encounter()
    ruling, after = build(tmp_path / "r", seed=seed_that(True, state, tmp_path)).adjudicate(
        state, strike(state)
    )
    reapplied = _apply(after, ruling.effects)
    assert reapplied.combatant("boar").hit_points < after.combatant("boar").hit_points, (
        "the private applier is not idempotent — which is exactly why it is not public"
    )


# --- Reading the target ------------------------------------------------------------------


def test_the_target_is_read_from_the_action_key_never_from_the_label(tmp_path: Path) -> None:
    """R6's discipline, one layer down. The token commits to the key and not to prose, so a
    target taken from the label would be a target outside anything the engine verified."""
    state = encounter()
    offered = read(state, "pc")
    mislabelled = Declaration(
        actor_id="pc",
        intent=Intent(action_key=attack_key("boar"), label="I strike at myself"),
        rule_id=STRIKE.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )
    ruling, _ = build(tmp_path / "t", seed=seed_that(True, state, tmp_path)).adjudicate(
        state, mislabelled
    )
    assert [e.target_id for e in ruling.effects] == ["boar"]


def test_attack_target_reads_only_attack_keys() -> None:
    assert attack_target(attack_key("boar")) == "boar"
    assert attack_target("end-turn") is None
    assert attack_target("attack:") is None
    assert attack_target(None) is None


def test_a_resolver_handed_a_non_attack_says_so() -> None:
    """It cannot silently pick a target — an attack with an invented victim is worse than
    a crash, because it resolves."""
    state = encounter()
    resolver = attack_resolver(BLADE)
    not_an_attack = Declaration(
        actor_id="pc", intent=Intent(improvised=True, label="I glare"), rule_id=STRIKE.id
    )
    with pytest.raises(ValueError, match="not an attack"):
        resolver(state=state, declaration=not_an_attack, facts={})


# --- The weapon is data ------------------------------------------------------------------


def test_no_weapon_list_ships_in_this_module() -> None:
    """R31/R32: no rule value is inferred, and #3 is still open.

    A table of longswords compiled from memory would be indistinguishable from a verified
    one once it was inside a finished Ruling — so the module defines the *shape* a weapon
    has and ships none. Checked against the parse tree rather than the text, because the
    text says the word "longsword" in exactly the sentence explaining why it must not.
    """
    import ast

    import srd_rules_engine.core.combat as combat

    tree = ast.parse(Path(combat.__file__).read_text())
    built = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    ]
    assert "Weapon" not in built, "a weapon constructed here is a rule value, not machinery"

    constants = {
        target.id
        for node in tree.body
        if isinstance(node, ast.Assign)
        for target in node.targets
        if isinstance(target, ast.Name)
    } | {
        node.target.id
        for node in tree.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert constants == {"INITIATIVE_DIE"}, (
        f"{constants - {'INITIATIVE_DIE'}} are module constants; a rule value hiding in one "
        "reads exactly like a verified one"
    )


def test_the_weapon_supplies_the_modifiers_and_proficiency_is_conditional() -> None:
    state = encounter()
    declaration = strike(state)

    def sources(weapon: Weapon) -> set[str]:
        proposal = attack_resolver(weapon)(state=state, declaration=declaration, facts={})
        return {m.source for m in proposal.test.modifiers}

    assert sources(BLADE) == {"ability:str", "proficiency"}

    untrained = Weapon(name="fixture club", damage_dice=1, damage_sides=4, proficient=False)
    assert sources(untrained) == {"ability:str"}


def test_the_weapons_ability_reaches_both_the_roll_and_the_damage(tmp_path: Path) -> None:
    """A weapon using one ability to hit and another to hurt is a defect the totals hide."""
    state = encounter()
    finesse = Weapon(name="fixture needle", damage_dice=1, damage_sides=4, ability="dex")
    proposal = attack_resolver(finesse)(state=state, declaration=strike(state), facts={})

    declared = proposal.on_success[0]
    assert isinstance(declared, DamageDice)
    assert declared.modifier == 2, "dex 14 is +2"
    assert {m.value for m in proposal.test.modifiers if m.source == "ability:dex"} == {2}


def test_the_bounds_forbid_asserting_a_death_or_a_different_number(tmp_path: Path) -> None:
    """R7 is advisory, so the bounds are the only thing standing between a resolved attack
    and a narrator who decides it was fatal."""
    state = encounter()
    ruling, _ = build(tmp_path / "b", seed=seed_that(True, state, tmp_path)).adjudicate(
        state, strike(state)
    )
    forbidden = " ".join(ruling.bounds.may_not).lower()
    assert "dead" in forbidden
    assert "damage number" in forbidden
