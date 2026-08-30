"""p. 190's Grapple and Shove, and the seam that lets the target choose its save (0053).

Three blockers stood in front of these two options and each was cleared by its own record: the
size test needed 0051's `Size`, the way out of a grapple needed 0052's p. 182 rules, and
"a Strength or Dexterity saving throw (**it chooses which**)" needed a creature that declares
nothing to be able to choose.

The last is the one this file is mostly about. Two saves in the whole document say it, and both
are here.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Combatant,
    Condition,
    Declaration,
    EncounterState,
    Intent,
    Ledger,
    Size,
    Status,
    load_ruleset,
    read,
)
from srd_rules_engine.core.conditions import Conditions, Grapple
from srd_rules_engine.core.equipment import Carriage, Carried, Item
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import (
    grapple_key,
    shove_prone_key,
    shove_push_key,
)
from srd_rules_engine.core.state import ForcedSave
from srd_rules_engine.core.unarmed_strike import (
    GRAPPLE_RULE_ID,
    SHOVE_RULE_ID,
    option_dc,
    unarmed_option_resolvers,
    unarmed_option_rules,
)
from srd_rules_engine.loop.drivers import ScriptedDriver, drive
from srd_rules_engine.loop.turn import SaveAbilityRequest, TurnLoop
from srd_rules_engine.memory.store import JsonMemoryStore

RULESET = load_ruleset(unarmed_option_rules())

#: A d20 plus a small modifier cannot reach 30 and cannot miss 1, so a test naming an outcome
#: is naming the rule rather than the seed.
UNREACHABLE = 30
CERTAIN = 1

TORCH = Item(id="fixture:torch", weight=1.0, hands_when_held=1)


def hero(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 13,
        "abilities": {"str": 16, "dex": 12, "con": 12},
        "proficiency_bonus": 2,
        "is_player_character": True,
        "position": Position(0, 0, 0),
        "size": Size.MEDIUM,
        "hands": 2,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def ogre(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "ogre",
        "name": "Ogre",
        "hit_points": 30,
        "max_hit_points": 30,
        "armour_class": 11,
        "abilities": {"str": 19, "dex": 8, "con": 16},
        "proficiency_bonus": 2,
        "position": Position(0, 0, 0),
        "size": Size.LARGE,
        "hands": 2,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(*combatants: Combatant) -> EncounterState:
    people = combatants or (hero(), ogre())
    return EncounterState.new(list(people)).with_initiative({"pc": 20, "ogre": 5})


def build(path: Path, *, seed: int = 5) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers=unarmed_option_resolvers(),
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: seed,
    )


def declare(state: EncounterState, key: str, rule_id: str) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=key),
        rule_id=rule_id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def offered_keys(state: EncounterState, actor_id: str = "pc") -> set[str]:
    return {action.key for action in read(state, actor_id).actions}


# --- p. 190's shared qualifier ---------------------------------------------------------------


def test_both_options_are_offered_against_a_creature_one_size_larger() -> None:
    """p. 190: "only if the target is **no more than one size larger** than you". Large is one
    larger than Medium, so both are offered."""
    keys = offered_keys(encounter())
    assert grapple_key("ogre") in keys
    assert shove_prone_key("ogre") in keys


def test_neither_is_offered_against_a_creature_two_sizes_larger() -> None:
    """Huge is two larger than Medium. The boundary is the assertion above and this one
    together — a test on one side only would pass against a check that never refused."""
    keys = offered_keys(encounter(hero(), ogre(size=Size.HUGE)))
    assert grapple_key("ogre") not in keys
    assert shove_prone_key("ogre") not in keys


def test_neither_is_offered_when_a_size_was_never_stated() -> None:
    """0051's refusal, reaching its first consumer. p. 14 sources a size from a species or a
    stat block and neither ships here, so a comparison against an unstated size is one the
    engine cannot make — and Medium would be the invented value R31 refuses."""
    unsized = offered_keys(encounter(hero(size=None), ogre()))
    assert grapple_key("ogre") not in unsized

    unsized_target = offered_keys(encounter(hero(), ogre(size=None)))
    assert grapple_key("ogre") not in unsized_target


def test_the_dc_is_eight_plus_strength_and_proficiency_unconditionally() -> None:
    """p. 190: "8 plus your Strength modifier and Proficiency Bonus", with no proficiency to
    have — the same flat reading the Damage option's attack bonus takes."""
    assert option_dc(hero()) == 13, "8 + 3 Strength + 2 proficiency"


# --- The free hand, which belongs to one option and not the other ----------------------------


def test_a_grapple_needs_a_free_hand_and_a_shove_does_not() -> None:
    """p. 190 asks for one in the Grapple sentence and not in the Shove sentence. That is the
    document's own distinction, so a creature with both hands full may still Shove."""
    full = hero(equipment=(Carried(TORCH, Carriage.HELD), Carried(TORCH, Carriage.HELD)))
    assert full.free_hands == 0
    keys = offered_keys(encounter(full, ogre()))
    assert grapple_key("ogre") not in keys
    assert shove_prone_key("ogre") in keys


def test_an_unstated_hand_count_is_not_a_free_hand() -> None:
    """0039: `hands` is `int | None` because no SRD rule says how many a creature has. p. 190
    asks for a free hand outright, and a creature that cannot be shown to have one has not
    been shown to satisfy the rule."""
    unstated = hero(hands=None)
    assert unstated.free_hands is None
    assert grapple_key("ogre") not in offered_keys(encounter(unstated, ogre()))


# --- The option compels a save and settles nothing --------------------------------------------


def test_the_grapple_compels_an_unsettled_save_and_decides_nothing(tmp_path: Path) -> None:
    """p. 190 gives the attacker no roll at all: the whole of the option is a save the target
    owes. So this is a testless proposal whose outcome is the compelled save."""
    state = encounter()
    ruling, after = build(tmp_path).adjudicate(
        state, declare(state, grapple_key("ogre"), GRAPPLE_RULE_ID)
    )

    assert ruling.status is Status.RULED
    assert ruling.result is None, "the attacker rolls nothing"
    assert Condition.GRAPPLED not in after.combatant("ogre").conditions.held

    owed = after.forced_saves_owed
    assert len(owed) == 1
    debt = owed[0]
    assert debt.combatant_id == "ogre", "the target owes it, not the attacker"
    assert debt.rule_id == GRAPPLE_RULE_ID
    assert debt.dc == 13
    assert debt.ability_choices == ("str", "dex")
    assert not debt.is_settled, "nobody has chosen yet"
    assert debt.source_id == "pc", "and the condition's own text will need the grappler"


def test_a_save_with_a_choice_will_not_roll_until_it_is_settled(tmp_path: Path) -> None:
    """The resolver refuses rather than picking. This is the guarantee the whole record is
    for: an engine that rolled here would have chosen, and p. 190 gives the choice away."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(
        state, declare(state, grapple_key("ogre"), GRAPPLE_RULE_ID)
    )
    compelled = Declaration(
        actor_id="ogre", intent=Intent(improvised=True, label="the save"), rule_id=GRAPPLE_RULE_ID
    )
    # It **raises** rather than refusing politely, which is what every resolver here does with
    # a declaration it cannot honour. Reaching this is a caller adjudicating directly instead
    # of through the turn loop — the case AGENTS.md already discloses as getting outcome
    # authority without the loop's guarantees — and a quiet rejection would let it pass for a
    # save that merely failed.
    with pytest.raises(ValueError, match="has not chosen"):
        build(tmp_path / "b").adjudicate(after, compelled)


# --- The choice, through the loop -------------------------------------------------------------


def loop_for(path: Path, *, seed: int) -> TurnLoop:
    return TurnLoop(adjudicator=build(path, seed=seed))


def compelled_state(path: Path, dc_override: int | None = None) -> EncounterState:
    """The state after a Grapple, with the save owed and unsettled."""
    state = encounter()
    _, after = build(path).adjudicate(state, declare(state, grapple_key("ogre"), GRAPPLE_RULE_ID))
    if dc_override is None:
        return after
    debt = after.forced_saves_owed[0]
    return after.with_forced_save_discharged("ogre").with_forced_save(replace(debt, dc=dc_override))


def test_the_loop_asks_the_target_and_offers_both_abilities(tmp_path: Path) -> None:
    """0053 clause 2. The request goes to the **target**, not to whoever is acting, and it
    carries each ability's modifier — a choice presented without them is not a choice an agent
    can make."""
    state = compelled_state(tmp_path)
    seen: list[SaveAbilityRequest] = []

    def spy(request: object) -> object:
        if isinstance(request, SaveAbilityRequest):
            seen.append(request)
        return ScriptedDriver(narrations=["ok"] * 8, save_abilities=["str"])(request)  # type: ignore[arg-type]

    drive(loop_for(tmp_path / "l", seed=5).end_turn(state, "pc"), spy)  # type: ignore[arg-type]

    assert len(seen) == 1
    request = seen[0]
    assert request.actor_id == "ogre", "the target chooses, not the attacker"
    assert request.dc == 13
    assert [(o.ability, o.modifier) for o in request.options] == [("str", 4), ("dex", -1)]


def test_the_chosen_ability_is_the_one_rolled(tmp_path: Path) -> None:
    """And it is the creature's choice even when it is the worse one — the ogre's Dexterity is
    -1 against its Strength of +4. An engine that optimised would never produce this."""
    state = compelled_state(tmp_path)
    end = drive(
        loop_for(tmp_path / "l", seed=5).end_turn(state, "pc"),
        ScriptedDriver(narrations=["ok"] * 8, save_abilities=["dex"]),
    )

    assert len(end.rulings) == 1
    result = end.rulings[0].result
    assert result is not None
    assert [m.source for m in result.modifiers] == ["ability:dex"]


def test_a_failed_save_grapples_and_carries_the_escape_dc(tmp_path: Path) -> None:
    """p. 190: "The DC for the saving throw **and any escape attempts**" is one number, so it
    travels with the application rather than being recomputed — 0052 clause 4 from the other
    end. The grappler travels too, because p. 182's Disadvantage names it."""
    state = compelled_state(tmp_path, dc_override=UNREACHABLE)
    end = drive(
        loop_for(tmp_path / "l", seed=5).end_turn(state, "pc"),
        ScriptedDriver(narrations=["ok"] * 8, save_abilities=["str"]),
    )

    target = end.state.combatant("ogre")
    assert Condition.GRAPPLED in target.conditions.held
    assert target.conditions.grappler_id == "pc"
    assert target.conditions.grapple == Grapple(escape_dc=UNREACHABLE, range_feet=None)


def test_a_grapple_made_here_states_no_range(tmp_path: Path) -> None:
    """p. 190 states the reach of the **strike** and no range for the grapple, so the distance
    ending declines rather than reading one as the other (#346). 0052 clause 3 settled the
    direction: the grapple is held, never lifted against an invented bound."""
    state = compelled_state(tmp_path, dc_override=UNREACHABLE)
    end = drive(
        loop_for(tmp_path / "l", seed=5).end_turn(state, "pc"),
        ScriptedDriver(narrations=["ok"] * 8, save_abilities=["str"]),
    )
    grapple = end.state.combatant("ogre").conditions.grapple
    assert grapple is not None and grapple.range_feet is None


def test_a_successful_save_does_nothing_at_all(tmp_path: Path) -> None:
    """p. 190 states one consequence and states it for the failure. Success is its absence."""
    state = compelled_state(tmp_path, dc_override=CERTAIN)
    end = drive(
        loop_for(tmp_path / "l", seed=5).end_turn(state, "pc"),
        ScriptedDriver(narrations=["ok"] * 8, save_abilities=["str"]),
    )

    target = end.state.combatant("ogre")
    assert Condition.GRAPPLED not in target.conditions.held
    assert target.conditions.grapple is None
    assert end.state.forced_saves_owed == (), "and the debt is discharged either way"


def test_declining_to_choose_leaves_the_save_unresolved(tmp_path: Path) -> None:
    """0053 clause 5. There is no fallback ability, because any fallback is the engine
    choosing. The grapple neither lands nor misses, and the obligation says so."""
    state = compelled_state(tmp_path, dc_override=UNREACHABLE)
    end = drive(
        loop_for(tmp_path / "l", seed=5).end_turn(state, "pc"),
        ScriptedDriver(narrations=["ok"] * 8, save_abilities=[None]),
    )

    assert end.rulings == ()
    assert [o.rule_id for o in end.unresolvable] == [GRAPPLE_RULE_ID]
    assert Condition.GRAPPLED not in end.state.combatant("ogre").conditions.held
    assert end.state.forced_saves_owed == (), "dropped rather than spun on"


# --- Shove ------------------------------------------------------------------------------------


def test_a_failed_shove_save_knocks_the_target_prone(tmp_path: Path) -> None:
    state = encounter()
    _, after = build(tmp_path).adjudicate(
        state, declare(state, shove_prone_key("ogre"), SHOVE_RULE_ID)
    )
    debt = after.forced_saves_owed[0]
    assert debt.rule_id == SHOVE_RULE_ID
    hard = after.with_forced_save_discharged("ogre").with_forced_save(replace(debt, dc=UNREACHABLE))
    end = drive(
        loop_for(tmp_path / "l", seed=5).end_turn(hard, "pc"),
        ScriptedDriver(narrations=["ok"] * 8, save_abilities=["dex"]),
    )

    target = end.state.combatant("ogre")
    assert Condition.PRONE in target.conditions.held
    assert Condition.GRAPPLED not in target.conditions.held
    assert target.conditions.grapple is None, "a shove is not a grapple and states no terms"


def test_both_shove_effects_are_offered_now() -> None:
    """This asserted `shove-cannot-push-only-knock-prone` was disclosed, while p. 190 offered
    two effects and this engine built one. 0055 built the other, so the clause came off — and
    the assertion is replaced by the thing that makes its removal honest.

    p. 190: "you **either** push it 5 feet away **or** cause it to have the Prone condition."
    Two entries, because the choice is the attacker's.
    """
    keys = offered_keys(encounter())
    assert shove_prone_key("ogre") in keys
    assert shove_push_key("ogre") in keys


# --- What the seam leaves alone ----------------------------------------------------------------


def test_a_save_the_document_names_outright_carries_no_choice() -> None:
    """p. 179's Concentration and p. 90's Topple state their ability, so `ability_choices` is
    empty and the loop never asks. The seam exists for two saves and touches no others."""
    settled = ForcedSave(
        combatant_id="pc", rule_id="concentration", ability="con", dc=10, dc_basis="b", label="l"
    )
    assert settled.ability_choices == ()
    assert settled.is_settled


def test_a_save_with_no_ability_and_no_choice_is_refused() -> None:
    """An empty ability with no choices means the engine would have to pick one, which is the
    state `ability_choices` exists to make unreachable."""
    with pytest.raises(ValueError, match="states its ability"):
        ForcedSave(combatant_id="pc", rule_id="r", ability="", dc=10, dc_basis="b", label="l")


def test_only_an_offered_ability_may_be_settled() -> None:
    with pytest.raises(ValueError, match="not one of the abilities"):
        ForcedSave(
            combatant_id="pc",
            rule_id="r",
            ability="",
            dc=10,
            dc_basis="b",
            label="l",
            ability_choices=("str", "dex"),
        ).with_ability("con")


def test_a_grapples_terms_survive_another_condition_landing_on_the_creature() -> None:
    """`with_condition` rebuilds the creature's `Conditions`, and rebuilding it without the
    grapple would erase the escape DC whenever anything else was applied — a Prone landing on
    a grappled creature and taking p. 182's number with it.

    Found while building 0053, because the Shove that knocks a grappled creature Prone is the
    ordinary case rather than an exotic one.
    """
    grappled = replace(
        hero(),
        conditions=Conditions(
            applied=frozenset({Condition.GRAPPLED}),
            sources={Condition.GRAPPLED: frozenset({"ogre"})},
            grapple=Grapple(escape_dc=13, range_feet=5),
        ),
    )
    after = encounter(grappled, ogre()).with_condition("pc", Condition.PRONE)
    held = after.combatant("pc").conditions

    assert Condition.PRONE in held.held
    assert held.grapple == Grapple(escape_dc=13, range_feet=5), "the DC survived"
    assert held.grappler_id == "ogre"
