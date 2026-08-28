"""Combat, which is where the invariant either holds or is obviously theatre.

Every other unit could be right and this one wrong, and the product would still be broken:
an attack is the moment an agent has the strongest reason to want a particular number. So
the tests here are mostly about *who produced the number* rather than what it was.

The seeds are found rather than written down. Dice derive from the seed, so a change to
the derivation would silently invalidate a literal and these tests would go on passing
while testing something else.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
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
from srd_rules_engine.core.actions import ActionBudget, ActionKind, dodging
from srd_rules_engine.core.adjudicate import Proposal, _apply, _roll_declared
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import DAMAGE_OFFSET, INITIATIVE_BAND, D20Test, TestKind, roll
from srd_rules_engine.core.d20 import resolve as roll_d20
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.position import Position
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
BLADE = Weapon(id="fixture blade", damage_dice=2, damage_sides=6, ability="str")

RULESET = load_fixture_ruleset("combat", [STRIKE])


def damage_effect(ruling: Ruling) -> Effect:
    """The damage this attack dealt.

    Selected by kind rather than by position, because since #252 an attack's first effect is
    the **Action it spent** (p. 176, p. 177) — a cost in `Proposal.always`, applied before the
    branch the roll selected. Indexing `effects[0]` for the damage was only ever right while
    nothing an adjudication did cost anything.
    """
    damage = [e for e in ruling.effects if e.kind is EffectKind.DAMAGE]
    assert len(damage) == 1, f"expected one damage effect, got {[e.kind for e in ruling.effects]}"
    return damage[0]


def d20(proposal: Proposal) -> D20Test:
    """Narrow `Proposal.test`, which became optional with #170 (0027 clause 6).

    Every resolver exercised in this file proposes a d20 test; a testless proposal is a
    different shape and is covered in `tests/test_outcome_without_a_roll.py`. Asserting it
    here keeps these tests reading as assertions about the test rather than about `None`.
    """
    assert proposal.test is not None, "this resolver must propose a d20 test"
    return proposal.test


def strike_with(state: EncounterState, weapon: Weapon, target: str = "boar") -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=attack_key(weapon.id, target)),
        rule_id=STRIKE.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def encounter(
    *, pc_ac: int = 13, boar_ac: int = 13, weapon: Weapon = BLADE, proficient: bool = True
) -> EncounterState:
    """The pc **holds** its weapon since #258 — a weapon is an `Item` a creature carries
    (0040 clause 1), so an attack is offered for what is in hand rather than for whatever
    weapon a resolver happened to close over.

    `proficient` is the wielder's now (p. 89), so it is a fact about the combatant here
    rather than a field on the weapon."""
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
                hands=2,
                equipment=(Carried(weapon, Carriage.HELD),),
                weapon_proficiencies=frozenset({weapon.id}) if proficient else frozenset(),
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


def build(path: Path, *, seed: int) -> Adjudicator:
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


def strike(state: EncounterState, actor: str = "pc", target: str = "boar") -> Declaration:
    offered = read(state, actor)
    return Declaration(
        actor_id=actor,
        intent=Intent(action_key=attack_key(BLADE.id, target)),
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

    # From initiative's own band (#82), not index 0 — sharing the d20's band is what let a
    # combatant's initiative alias onto a die of the same seed.
    faces = roll(7, count=2, sides=20, offset=INITIATIVE_BAND.start)
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
    assert not [e for e in ruling.effects if e.kind is EffectKind.DAMAGE], (
        "a miss deals no damage — the Action it spent is a cost, not a consequence"
    )
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
    dealt = damage_effect(ruling).amount

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
    proposal = attack_resolver()(state=state, declaration=strike(state), facts={})

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
    assert damage_effect(ruling).amount == sum(faces) + 3, "str 16 is +3"


def test_the_effect_names_the_weapon_that_dealt_the_damage(tmp_path: Path) -> None:
    """The effect description is the audit trail a reader reconstructs the fight from. A
    generic "damage: 4 + 3" leaves two weapons indistinguishable in the ledger, which is
    the point at which a replay stops settling arguments."""
    state = encounter()
    ruling, _ = build(tmp_path / "n", seed=seed_that(True, state, tmp_path)).adjudicate(
        state, strike(state)
    )

    assert damage_effect(ruling).description.startswith(f"{BLADE.id}:")
    assert "2d6" in damage_effect(ruling).description, "and the dice it was rolled from"


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
    assert attack_key(BLADE.id, "boar") in read(state, "pc").keys

    downed = state.with_damage("boar", 999)
    assert attack_key(BLADE.id, "boar") not in read(downed, "pc").keys


def test_the_offered_attack_states_the_armour_value_it_will_be_resolved_against() -> None:
    """R18's read surface is thick so the agent chooses from engine-supplied facts rather
    than recalling them. An option carrying only a key would send it back to its training
    for the target's armour class — and the token would commit to nothing but the name."""
    state = encounter(boar_ac=17).with_initiative({"pc": 18, "boar": 4})
    option = next(a for a in read(state, "pc").actions if a.key == attack_key(BLADE.id, "boar"))

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
    # The damage alone, because since #252 the ruling also carries the Action it spent and
    # re-applying *that* raises `ActionUnavailable` — a louder failure than the quiet one
    # this test is about, and one that would hide it.
    reapplied, _, _withheld = _apply(after, (damage_effect(ruling),), seed=1)
    assert reapplied.combatant("boar").hit_points < after.combatant("boar").hit_points, (
        "the private applier is not idempotent — which is exactly why it is not public"
    )


def test_an_attack_costs_the_action(tmp_path: Path) -> None:
    """#252. p. 176: "On your turn, you can take one action", and p. 177 makes an attack one:
    "When you take the Attack action, you can make **one attack roll**."

    It cost nothing until #252, because nothing an adjudication did cost anything —
    `ActionBudget.spend` had no caller outside `dodging()`. So the read surface consulted an
    economy that was never charged, and a driver could attack as many times as it asked to.

    **Extra Attack would make one-Action-one-roll wrong**, and it is class content this
    repository ships none of. p. 177 mentions it under *Moving between Attacks* — "a feature,
    such as Extra Attack, that gives you more than one attack as part of the Attack action" —
    so the day a ruleset can bring one, this is the line that has to change.
    """
    state = encounter()
    ruling, after = build(tmp_path / "a", seed=seed_that(True, state, tmp_path)).adjudicate(
        state, strike(state)
    )

    spent = [e for e in ruling.effects if e.kind is EffectKind.ACTION_SPENT]
    assert [e.action for e in spent] == [ActionKind.ACTION]
    assert not after.combatant("pc").actions.available(ActionKind.ACTION)


def test_the_action_is_charged_even_when_the_attack_misses(tmp_path: Path) -> None:
    """A cost, not a consequence. p. 177 spends the action on *taking* the Attack action, and
    a miss is still an attack made — so the charge is in `always` rather than in a branch."""
    state = encounter()
    ruling, after = build(tmp_path / "m", seed=seed_that(False, state, tmp_path)).adjudicate(
        state, strike(state)
    )

    assert not [e for e in ruling.effects if e.kind is EffectKind.DAMAGE], "precondition: a miss"
    assert not after.combatant("pc").actions.available(ActionKind.ACTION)


# --- Reading the target ------------------------------------------------------------------


def test_the_target_is_read_from_the_action_key_never_from_the_label(tmp_path: Path) -> None:
    """R6's discipline, one layer down. The token commits to the key and not to prose, so a
    target taken from the label would be a target outside anything the engine verified."""
    state = encounter()
    offered = read(state, "pc")
    mislabelled = Declaration(
        actor_id="pc",
        intent=Intent(action_key=attack_key(BLADE.id, "boar"), label="I strike at myself"),
        rule_id=STRIKE.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )
    ruling, _ = build(tmp_path / "t", seed=seed_that(True, state, tmp_path)).adjudicate(
        state, mislabelled
    )
    assert damage_effect(ruling).target_id == "boar", "the key's target, not the label's"
    assert [e.target_id for e in ruling.effects if e.kind is not EffectKind.ACTION_SPENT] == [
        "boar"
    ], "and nothing else the attack did landed on anyone the key did not name"


def test_attack_target_reads_only_attack_keys() -> None:
    assert attack_target(attack_key(BLADE.id, "boar")) == "boar"
    assert attack_target("end-turn") is None
    assert attack_target("attack:") is None
    assert attack_target(None) is None


def test_a_resolver_handed_a_non_attack_says_so() -> None:
    """It cannot silently pick a target — an attack with an invented victim is worse than
    a crash, because it resolves."""
    state = encounter()
    resolver = attack_resolver()
    not_an_attack = Declaration(
        actor_id="pc", intent=Intent(improvised=True, label="I glare"), rule_id=STRIKE.id
    )
    with pytest.raises(ValueError, match="not an attack"):
        resolver(state=state, declaration=not_an_attack, facts={})


# --- The weapon is data ------------------------------------------------------------------


def _source_of(module: object) -> str:
    """A module's source, with the `__file__` narrowing mypy wants."""
    path = getattr(module, "__file__", None)
    assert path is not None, f"{module} has no file to read"
    return Path(path).read_text()


def test_no_weapon_list_ships_in_this_module() -> None:
    """R31/R32: no rule value is inferred, and #3 is still open.

    A table of longswords compiled from memory would be indistinguishable from a verified
    one once it was inside a finished Ruling — so the module defines the *shape* a weapon
    has and ships none. Checked against the parse tree rather than the text, because the
    text says the word "longsword" in exactly the sentence explaining why it must not.
    """
    import ast

    import srd_rules_engine.core.combat as combat
    import srd_rules_engine.core.equipment as equipment

    # **Both modules**, since #258. `Weapon` moved to `core.equipment` when it became an
    # `Item` subtype, and a guard that watched only its old home would have stopped watching
    # the file the type now lives in — which is the quiet way a guard becomes decorative.
    for module in (combat, equipment):
        built = [
            node.func.id
            for node in ast.walk(ast.parse(_source_of(module)))
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        ]
        assert "Weapon" not in built, (
            f"a weapon constructed in {module.__name__} is a rule value, not machinery"
        )

    tree = ast.parse(_source_of(combat))

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
    # A rule value may live here, but only carrying what it was checked against. The
    # threshold Heavy names is exactly such a value, and a bare 13 would be
    # indistinguishable from an invented one — which is the failure this guard names.
    # `HEAVY_SCORE_THRESHOLD` left this module with `Weapon` in #258 and is now guarded in
    # `core.equipment` — where the same reasoning applies to it unchanged.
    allowed = {"INITIATIVE_DIE", "WEAPON_PROPERTY_VERIFICATION", "UNARMED_STRIKE_VERIFICATION"}
    assert constants == allowed, (
        f"{constants - allowed} are module constants; a rule value hiding in one "
        "reads exactly like a verified one"
    )

    from srd_rules_engine.core.combat import WEAPON_PROPERTY_VERIFICATION
    from srd_rules_engine.core.rules import VerificationState

    assert WEAPON_PROPERTY_VERIFICATION.state is VerificationState.VERIFIED
    assert WEAPON_PROPERTY_VERIFICATION.reference is not None
    assert "pp. 89-90" in WEAPON_PROPERTY_VERIFICATION.reference, (
        "the rule values in this module cite the pages they were read from"
    )


def test_the_weapon_supplies_the_modifiers_and_proficiency_is_conditional() -> None:
    def sources(weapon: Weapon, *, proficient: bool = True) -> set[str]:
        return {m.source for m in d20(_propose_with(weapon, proficient=proficient)).modifiers}

    assert sources(BLADE) == {"ability:str", "proficiency"}

    # p. 89: "Anyone can wield a weapon, but **you** must have proficiency with it." The same
    # weapon, in the hands of someone who lacks the proficiency — which was unexpressible
    # while `proficient` was a field on the weapon (0040 clause 2).
    assert sources(BLADE, proficient=False) == {"ability:str"}


def test_the_weapons_ability_reaches_both_the_roll_and_the_damage(tmp_path: Path) -> None:
    """A weapon using one ability to hit and another to hurt is a defect the totals hide."""
    finesse = Weapon(id="fixture needle", damage_dice=1, damage_sides=4, ability="dex")
    proposal = _propose_with(finesse)

    declared = proposal.on_success[0]
    assert isinstance(declared, DamageDice)
    assert declared.modifier == 2, "dex 14 is +2"
    assert {m.value for m in d20(proposal).modifiers if m.source == "ability:dex"} == {2}


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


# --- A weapon's numeric bonus reaches both rolls (#15) -------------------------------


def test_a_weapon_bonus_reaches_the_attack_roll_and_the_damage_roll() -> None:
    """Magic Items p. 213, Berserker Axe: "a +1 bonus to attack rolls **and** damage rolls
    made with this magic weapon".

    Both halves are asserted because a bonus that reached only the attack would be
    invisible in every hit that lands — the damage would simply be one lower than the
    rules say, in a number nobody has anything to compare against.
    """
    without = _propose_with(Weapon(id="axe", damage_dice=1, damage_sides=12))
    with_bonus = _propose_with(Weapon(id="axe +1", damage_dice=1, damage_sides=12, bonus=1))

    def modifier_total(test: D20Test) -> int:
        return sum(m.value for m in test.modifiers)

    assert modifier_total(d20(with_bonus)) == modifier_total(d20(without)) + 1
    assert any("bonus" in m.source for m in d20(with_bonus).modifiers)

    assert with_bonus.on_success[0].modifier == without.on_success[0].modifier + 1  # type: ignore[union-attr]


def test_a_weapon_without_a_bonus_adds_no_modifier_at_all() -> None:
    """A zero bonus is absent rather than recorded as +0, so the derivation stays readable."""
    proposal = _propose_with(Weapon(id="axe", damage_dice=1, damage_sides=12))
    assert not any("bonus" in m.source for m in d20(proposal).modifiers)


def _dice(proposal: Proposal) -> DamageDice:
    """The damage the proposal declares, narrowed. A branch holds `Effect | DamageDice`."""
    declared = proposal.on_success[0]
    assert isinstance(declared, DamageDice)
    return declared


def _miss_effect(proposal: Proposal) -> Effect:
    declared = proposal.on_failure[0]
    assert isinstance(declared, Effect)
    return declared


def encounter_with_scores(scores: dict[str, int]) -> EncounterState:
    """An encounter whose player character has the given ability scores."""
    base = encounter()
    pc = base.combatant("pc")
    return EncounterState.new(
        [dataclasses.replace(pc, abilities={**dict(pc.abilities), **scores})]
        + [c for c in base.combatants if c.id != "pc"]
    )


# --- Weapon properties and mastery (#16) --------------------------------------------


def _propose_with(
    weapon: Weapon,
    *,
    actor: str = "pc",
    target: str = "boar",
    state: EncounterState | None = None,
    proficient: bool = True,
) -> Proposal:
    """The proposal for attacking with that weapon, **held**.

    Since #258 a weapon is an `Item` the creature carries, so exercising one means putting it
    in a hand rather than handing it to `attack_resolver` — which takes no weapon at all now
    and reads what was swung off the key the read surface offered (0040 clauses 1 and 4).
    """
    if state is None:
        state = encounter(weapon=weapon, proficient=proficient)
    else:
        # A caller that built its own state — for cover, light, conditions — still has to put
        # the weapon in the actor's hand, because that is where the resolver reads it from.
        # Doing it here rather than at thirty call sites is the whole point of the helper.
        armed = dataclasses.replace(
            state.combatant(actor),
            hands=2,
            equipment=(Carried(weapon, Carriage.HELD),),
            weapon_proficiencies=frozenset({weapon.id}) if proficient else frozenset(),
        )
        state = dataclasses.replace(
            state,
            combatants=tuple(armed if c.id == actor else c for c in state.combatants),
        )
    return attack_resolver()(
        state=state,
        declaration=Declaration(
            actor_id=actor,
            intent=Intent(action_key=attack_key(weapon.id, target)),
            rule_id="attack",
        ),
        facts={},
    )


def test_a_finesse_weapon_may_use_dexterity_and_the_same_modifier_reaches_both_rolls() -> None:
    """p. 89: "use your choice of your Strength or Dexterity modifier for the attack and
    damage rolls. You must use the same modifier for both rolls."

    The *choice* is the wielder's and arrives as `ability`. What the engine holds is the
    constraint, and the half worth testing is that one modifier reaches both rolls — a
    weapon attacking on Dexterity and damaging on Strength is the mistake this forbids.
    """
    rapier = Weapon(id="rapier", damage_dice=1, damage_sides=8, ability="dex", finesse=True)
    proposal = _propose_with(rapier)

    dex = next(m.value for m in d20(proposal).modifiers if m.source == "ability:dex")
    assert _dice(proposal).modifier == dex, "the same modifier, on both rolls"


def test_a_finesse_weapon_may_not_use_a_third_ability() -> None:
    """The document offers Strength or Dexterity and no others."""
    with pytest.raises(ValueError, match="Strength or Dexterity"):
        Weapon(id="odd", damage_dice=1, damage_sides=8, ability="cha", finesse=True)


def test_heavy_gives_disadvantage_below_a_strength_of_13() -> None:
    """p. 89: Disadvantage "if it's a Melee weapon and your Strength score isn't at least
    13". The **score**, not the modifier — a modifier comparison puts the boundary in a
    different place, and 13 is where the document puts it.
    """
    greataxe = Weapon(id="greataxe", damage_dice=1, damage_sides=12, heavy=True)

    weak = encounter_with_scores({"str": 12, "dex": 14})
    strong = encounter_with_scores({"str": 13, "dex": 14})

    assert d20(_propose_with(greataxe, state=weak)).has_disadvantage
    assert not d20(_propose_with(greataxe, state=strong)).has_disadvantage, "13 is enough"


def test_heavy_reads_dexterity_for_a_ranged_weapon() -> None:
    """The same sentence's other half: "or if it's a Ranged weapon and your Dexterity score
    isn't at least 13". Reading Strength for a longbow would be the wrong ability."""
    longbow = Weapon(
        id="longbow", damage_dice=1, damage_sides=8, heavy=True, melee=False, ability="dex"
    )
    assert d20(
        _propose_with(longbow, state=encounter_with_scores({"str": 18, "dex": 12}))
    ).has_disadvantage
    assert not d20(
        _propose_with(longbow, state=encounter_with_scores({"str": 8, "dex": 13}))
    ).has_disadvantage


def test_a_weapon_without_heavy_never_takes_the_penalty() -> None:
    plain = Weapon(id="club", damage_dice=1, damage_sides=4)
    assert not d20(_propose_with(plain, state=encounter_with_scores({"str": 3}))).has_disadvantage


def test_versatile_uses_the_larger_die_only_in_two_hands() -> None:
    """p. 90: a Versatile weapon "deals that damage when used with two hands to make a
    melee attack". Both halves are conditions."""
    one = Weapon(id="longsword", damage_dice=1, damage_sides=8, versatile_sides=10)
    two = Weapon(
        id="longsword", damage_dice=1, damage_sides=8, versatile_sides=10, wielded_two_handed=True
    )

    assert _dice(_propose_with(one)).sides == 8
    assert _dice(_propose_with(two)).sides == 10


def test_versatile_is_a_melee_property() -> None:
    with pytest.raises(ValueError, match="melee property"):
        Weapon(id="odd", damage_dice=1, damage_sides=8, versatile_sides=10, melee=False)


def test_graze_deals_the_ability_modifier_on_a_miss() -> None:
    """p. 90: "If your attack roll with this weapon misses a creature, you can deal damage
    to that creature equal to the ability modifier you used to make the attack roll."

    The miss branch is normally empty, so this is the first thing that puts damage in it.
    """
    greataxe = Weapon(
        id="greataxe", damage_dice=1, damage_sides=12, graze=True, damage_type=DamageType.SLASHING
    )
    proposal = _propose_with(greataxe)

    assert proposal.on_failure, "a Graze weapon deals damage on a miss"
    effect = _miss_effect(proposal)
    ability = next(m.value for m in d20(proposal).modifiers if m.source.startswith("ability:"))
    assert effect.amount == ability
    assert effect.damage_type is DamageType.SLASHING, "the same type the weapon deals"


def test_a_weapon_without_graze_misses_for_nothing() -> None:
    plain = Weapon(id="club", damage_dice=1, damage_sides=4)
    assert _propose_with(plain).on_failure == ()


def test_graze_never_heals() -> None:
    """A negative ability modifier would be negative damage, and the document gives no rule
    for a miss that heals — "the damage can be increased only by increasing the ability
    modifier", so nothing else may be folded in either.
    """
    feeble = encounter_with_scores({"str": 4})
    greataxe = Weapon(id="greataxe", damage_dice=1, damage_sides=12, graze=True)
    assert _propose_with(greataxe, state=feeble).on_failure == ()


# --- Reach and weapon range (#20) ----------------------------------------------------


def _placed(actor_at: Position, target_at: Position, *, reach: int = 5) -> EncounterState:
    base = encounter()
    pc, boar = base.combatant("pc"), base.combatant("boar")
    return EncounterState.new(
        [
            dataclasses.replace(pc, position=actor_at, reach=reach),
            dataclasses.replace(boar, position=target_at),
        ]
    )


def test_a_melee_attack_beyond_reach_is_refused() -> None:
    """p. 186: a creature reaches 5 feet unless a rule says otherwise. An attack on
    something further away is not a harder attack — it is one that cannot be made."""
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    _propose_with(club, state=_placed(Position(0, 0, 0), Position(5, 0, 0)))

    with pytest.raises(ValueError, match="reach of 5 feet"):
        _propose_with(club, state=_placed(Position(0, 0, 0), Position(10, 0, 0)))


def test_reach_counts_elevation() -> None:
    """A creature 10 feet overhead is out of reach, which a flat model could not say."""
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    with pytest.raises(ValueError, match="reach of 5 feet"):
        _propose_with(club, state=_placed(Position(0, 0, 0), Position(0, 0, 10)))


def test_a_longer_reach_is_honoured() -> None:
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    _propose_with(club, state=_placed(Position(0, 0, 0), Position(10, 0, 0), reach=10))


def test_beyond_normal_range_is_disadvantage_not_a_refusal() -> None:
    """p. 90: "When attacking a target beyond normal range, you have Disadvantage on the
    attack roll." """
    bow = Weapon(
        id="shortbow",
        damage_dice=1,
        damage_sides=6,
        melee=False,
        ability="dex",
        normal_range=80,
        long_range=320,
    )
    near = _propose_with(bow, state=_placed(Position(0, 0, 0), Position(50, 0, 0)))
    far = _propose_with(bow, state=_placed(Position(0, 0, 0), Position(200, 0, 0)))

    assert not d20(near).has_disadvantage
    assert d20(far).has_disadvantage


def test_beyond_long_range_no_attack_may_be_made() -> None:
    """The second sentence of the same rule: "You can't attack a target beyond the long
    range." Not a penalty, so it is refused rather than resolved — a ruling here would be
    an outcome for something that never happened.
    """
    bow = Weapon(
        id="shortbow",
        damage_dice=1,
        damage_sides=6,
        melee=False,
        ability="dex",
        normal_range=80,
        long_range=320,
    )
    with pytest.raises(ValueError, match="beyond the long range"):
        _propose_with(bow, state=_placed(Position(0, 0, 0), Position(400, 0, 0)))


def test_range_and_heavy_do_not_stack_into_two_disadvantages() -> None:
    """The d20 takes a single flag, so the cancellation rule holds by construction — two
    sources of Disadvantage are still one Disadvantage (p. 8)."""
    heavy_bow = Weapon(
        id="longbow",
        damage_dice=1,
        damage_sides=8,
        melee=False,
        ability="dex",
        heavy=True,
        normal_range=150,
        long_range=600,
    )
    state = _placed(Position(0, 0, 0), Position(300, 0, 0))
    proposal = _propose_with(heavy_bow, state=state)
    assert d20(proposal).has_disadvantage is True


def test_a_weapon_range_lists_two_numbers() -> None:
    """p. 90: "The range lists two numbers." One without the other is not a range."""
    with pytest.raises(ValueError, match="two numbers"):
        Weapon(id="odd", damage_dice=1, damage_sides=6, melee=False, normal_range=80)
    with pytest.raises(ValueError, match="not shorter"):
        Weapon(id="odd", damage_dice=1, damage_sides=6, melee=False, normal_range=80, long_range=40)
    with pytest.raises(ValueError, match="ranged-weapon property"):
        Weapon(id="odd", damage_dice=1, damage_sides=6, normal_range=80, long_range=320)


def test_an_encounter_without_positions_asks_no_range_question() -> None:
    """Position is optional. An encounter that tracks none cannot answer a range question,
    and the honest result is to not ask it rather than to assume everyone is adjacent."""
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    assert d20(_propose_with(club, state=encounter())).has_disadvantage is False


# --- Conditions reach the attack roll (#18) ------------------------------------------


def _conditioned(
    *,
    attacker: Conditions | None = None,
    defender: Conditions | None = None,
    at: Position | None = None,
) -> EncounterState:
    base = encounter()
    pc, boar = base.combatant("pc"), base.combatant("boar")
    return EncounterState.new(
        [
            dataclasses.replace(
                pc, position=Position(0, 0, 0), conditions=attacker or Conditions()
            ),
            dataclasses.replace(
                boar, position=at or Position(5, 0, 0), conditions=defender or Conditions()
            ),
        ]
    )


def test_a_poisoned_attacker_swings_at_disadvantage() -> None:
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    poisoned = Conditions(held=frozenset({Condition.POISONED}))
    assert d20(_propose_with(club, state=_conditioned(attacker=poisoned))).has_disadvantage


def test_a_restrained_defender_is_attacked_at_advantage() -> None:
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    restrained = Conditions(held=frozenset({Condition.RESTRAINED}))
    assert d20(_propose_with(club, state=_conditioned(defender=restrained))).has_advantage


def test_conditions_on_both_sides_cancel_by_the_d20s_own_rule() -> None:
    """A poisoned attacker (Disadvantage) against a restrained defender (Advantage) rolls
    one plain d20 — p. 8, resolved by the same flags every other circumstance uses rather
    than by a second mechanism.
    """
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    proposal = _propose_with(
        club,
        state=_conditioned(
            attacker=Conditions(held=frozenset({Condition.POISONED})),
            defender=Conditions(held=frozenset({Condition.RESTRAINED})),
        ),
    )
    assert d20(proposal).has_advantage and d20(proposal).has_disadvantage
    result = roll_d20(d20(proposal), seed=7)
    assert len(result.dice) == 1, "both states, so neither — one plain d20"


def test_prone_reaches_the_attack_roll_in_both_directions() -> None:
    """The rule this whole slice exists to get right: Advantage within 5 feet,
    Disadvantage beyond, decided by the position the engine already holds."""
    bow = Weapon(
        id="shortbow",
        damage_dice=1,
        damage_sides=6,
        melee=False,
        ability="dex",
        normal_range=80,
        long_range=320,
    )
    prone = Conditions(held=frozenset({Condition.PRONE}))

    close = _propose_with(bow, state=_conditioned(defender=prone, at=Position(3, 0, 0)))
    far = _propose_with(bow, state=_conditioned(defender=prone, at=Position(40, 0, 0)))

    assert d20(close).has_advantage and not d20(close).has_disadvantage
    assert d20(far).has_disadvantage and not d20(far).has_advantage


# --- Dodge reaches the attack roll (#16) ---------------------------------------------


def test_a_dodging_defender_is_attacked_at_disadvantage() -> None:
    """p. 181, through the resolver rather than only in the budget."""
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    base = encounter()
    pc, boar = base.combatant("pc"), base.combatant("boar")
    state = EncounterState.new(
        [
            dataclasses.replace(pc, position=Position(0, 0, 0)),
            dataclasses.replace(
                boar,
                position=Position(5, 0, 0),
                actions=dodging(ActionBudget(), Conditions(), 30),
            ),
        ]
    )
    assert d20(_propose_with(club, state=state)).has_disadvantage


def test_a_dodge_that_no_longer_stands_does_not_reach_the_roll() -> None:
    """Grappled sets Speed to 0, and p. 181 ends the Dodge with it. The flag is still set;
    the benefit is gone, and the resolver reads the benefit rather than the flag."""
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    base = encounter()
    pc, boar = base.combatant("pc"), base.combatant("boar")
    state = EncounterState.new(
        [
            dataclasses.replace(pc, position=Position(0, 0, 0)),
            dataclasses.replace(
                boar,
                position=Position(5, 0, 0),
                actions=dodging(ActionBudget(), Conditions(), 30),
                conditions=Conditions(held=frozenset({Condition.GRAPPLED})),
            ),
        ]
    )
    proposal = _propose_with(club, state=state)
    assert not d20(proposal).has_disadvantage


# --- Invisible's exception, through the resolver that wires it (#193) --------------------


def _invisible_target_state(*, seer: bool = False) -> EncounterState:
    """The boar is Invisible. `seer` gives the attacker Truesight, which is one of the two
    routes p. 184's "somehow see you" is answered for."""
    from dataclasses import replace as _replace

    from srd_rules_engine.core.conditions import Condition, Conditions
    from srd_rules_engine.core.position import Position
    from srd_rules_engine.core.sight import Lighting, LightLevel, Senses

    state = encounter()
    hidden = _replace(
        state.combatant("boar"),
        conditions=Conditions(held=frozenset({Condition.INVISIBLE})),
        position=Position(5, 0, 0),
    )
    watcher = _replace(
        state.combatant("pc"),
        senses=Senses(truesight=120) if seer else Senses(),
        position=Position(0, 0, 0),
    )
    return _replace(
        state,
        combatants=tuple({"boar": hidden, "pc": watcher}.get(c.id, c) for c in state.combatants),
        lighting=Lighting(ambient=LightLevel.BRIGHT),
    )


def test_an_unstated_view_keeps_the_invisible_targets_disadvantage() -> None:
    """The resolver's own wiring, which #193's first guard did not reach.

    `can_see` says `UNSTATED` for an Invisible target under ordinary sight, and p. 184's
    exception needs *certainty* to fire. Dropping the Disadvantage on `UNSTATED` would make
    every attacker hit an invisible creature more often on a guess (0030 clause 1).
    """
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    proposal = _propose_with(club, state=_invisible_target_state())
    assert d20(proposal).has_disadvantage
    assert not d20(proposal).has_advantage


def test_truesight_drops_it_through_the_resolver() -> None:
    """The control: with certainty the exception fires, so the same attack is unmodified."""
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    proposal = _propose_with(club, state=_invisible_target_state(seer=True))
    assert not d20(proposal).has_disadvantage


def test_an_invisible_attacker_gains_advantage_only_against_a_blind_target() -> None:
    """The other half of p. 184's exception, through the resolver that wires it.

    Certainty is required to *grant* here, where certainty was required to *remove* above —
    0030 clause 3, in one condition. Granting Advantage on a guess makes the invisible
    creature hit more often and manufactures damage.
    """
    from dataclasses import replace as _replace

    from srd_rules_engine.core.conditions import Condition, Conditions
    from srd_rules_engine.core.position import Position
    from srd_rules_engine.core.sight import Lighting, LightLevel

    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    state = encounter()
    unseen = _replace(
        state.combatant("pc"),
        conditions=Conditions(held=frozenset({Condition.INVISIBLE})),
        position=Position(0, 0, 0),
    )
    sighted = _replace(state.combatant("boar"), position=Position(5, 0, 0))
    lit = _replace(
        state,
        combatants=tuple({"pc": unseen, "boar": sighted}.get(c.id, c) for c in state.combatants),
        lighting=Lighting(ambient=LightLevel.BRIGHT),
    )
    assert not d20(_propose_with(club, state=lit)).has_advantage, (
        "the boar's view of an Invisible creature is UNSTATED, so the Advantage is withheld"
    )

    blind_boar = _replace(sighted, conditions=Conditions(held=frozenset({Condition.BLINDED})))
    blinded = _replace(
        lit,
        combatants=tuple({"pc": unseen, "boar": blind_boar}.get(c.id, c) for c in lit.combatants),
    )
    assert d20(_propose_with(club, state=blinded)).has_advantage, (
        "p. 177 says the boar cannot see, so p. 184's exception does not fire"
    )


# --- Total Cover cannot be targeted (#20, p. 179) -----------------------------------------


def _walled_state(*, blocking_wall: bool) -> EncounterState:
    """The boar is five feet away; the wall is between them, or beside them."""
    from dataclasses import replace as _replace

    from srd_rules_engine.core.obstructions import Obstruction
    from srd_rules_engine.core.position import Position

    wall = (
        Obstruction(lo=Position(2, -20, 0), hi=Position(3, 20, 20))
        if blocking_wall
        else Obstruction(lo=Position(-20, 10, 0), hi=Position(20, 11, 20))
    )
    state = encounter()
    return _replace(
        state,
        combatants=tuple(
            _replace(c, position=Position(0, 0, 0) if c.id == "pc" else Position(5, 0, 0))
            for c in state.combatants
        ),
        obstructions=(wall,),
    )


def test_an_attack_through_total_cover_is_refused() -> None:
    """p. 179: Total Cover "can't be targeted directly".

    A refusal rather than a penalty, for the reason a shot beyond long range is refused —
    the rules forbid the attack, so a ruling for it would be an outcome for something that
    never happened.

    Until #20 nothing in this module looked at cover, and an arrow flew through a stone
    wall. The geometry was ready from #91 and the walls have been state since 0026; what was
    missing was anyone asking.
    """
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    with pytest.raises(ValueError, match="Total Cover"):
        _propose_with(club, state=_walled_state(blocking_wall=True))


def test_a_wall_beside_them_is_not_cover() -> None:
    """Blocking is per-line (#91). The control that says the refusal is the wall's position
    doing work rather than the wall's presence."""
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    proposal = _propose_with(club, state=_walled_state(blocking_wall=False))
    assert d20(proposal).kind is TestKind.ATTACK


def test_an_encounter_without_walls_is_unaffected() -> None:
    """The common case, and the one that must not acquire a wall by implication."""
    club = Weapon(id="club", damage_dice=1, damage_sides=4)
    assert d20(_propose_with(club)).kind is TestKind.ATTACK
