"""What a creature's own state does to a saving throw (#344, 0054).

Three printed rules act on a save because of what the roller is holding, and none of them
belongs to the rule that compelled it:

* four conditions make Strength and Dexterity saves **fail outright** (pp. 186, 189, 191),
* Restrained gives Dexterity saves **Disadvantage** (p. 187),
* the Dodge action gives them **Advantage** (p. 181).

All three were modelled in data and reached no roll. Six resolvers built a save and not one
consulted the creature rolling it.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from dataclasses import replace
from pathlib import Path

import pytest

import srd_rules_engine.core as core_package
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
)
from srd_rules_engine.core.actions import ActionBudget
from srd_rules_engine.core.conditions import Conditions
from srd_rules_engine.core.d20 import Advantage, TestKind
from srd_rules_engine.core.position import Position, Speeds
from srd_rules_engine.core.state import ForcedSave
from srd_rules_engine.core.unarmed_strike import (
    GRAPPLE_RULE_ID,
    unarmed_option_resolvers,
    unarmed_option_rules,
)
from srd_rules_engine.memory.store import JsonMemoryStore

RULESET = load_ruleset(unarmed_option_rules())

#: Unreachable and unmissable, so an outcome names the rule rather than the seed.
UNREACHABLE = 30


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
        "speeds": Speeds(walk=30),
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
        "speeds": Speeds(walk=30),
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


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


def owing_a_save(target: Combatant, *, ability: str, dc: int = 12) -> EncounterState:
    """`target` owes a settled Grapple save of that ability, from the hero."""
    state = EncounterState.new([hero(), target]).with_initiative({"pc": 20, target.id: 5})
    return state.with_forced_save(
        ForcedSave(
            combatant_id=target.id,
            rule_id=GRAPPLE_RULE_ID,
            ability=ability,
            dc=dc,
            dc_basis="a fixture DC (p. 190)",
            label="a grapple",
            # p. 190 offers Strength or Dexterity, so a Constitution save cannot have come
            # from a choice — it is the fixture reaching a third ability to prove the rules
            # here are keyed on the ability rather than on the resolver.
            ability_choices=("str", "dex") if ability in ("str", "dex") else (),
            source_id="pc",
        )
    )


def roll_the_save(path: Path, state: EncounterState, target_id: str, *, seed: int = 5):  # type: ignore[no-untyped-def]
    compelled = Declaration(
        actor_id=target_id,
        intent=Intent(improvised=True, label="the save"),
        rule_id=GRAPPLE_RULE_ID,
    )
    return build(path, seed=seed).adjudicate(state, compelled)


# --- The guard a new resolver cannot get past ------------------------------------------------


def test_every_save_the_core_builds_names_its_ability() -> None:
    """The rules here key on **which ability** a save is of, so a `D20Test` of kind SAVE that
    does not say is a save all three rules silently skip.

    Derived from the source rather than from a list of the six that exist today, which is
    #334's lesson applied before the fact: a seventh resolver written next year is caught by
    this, and would not be caught by a pin naming the six.

    Death saves are the one legitimate `ability=None` and say so at the call site — p. 17 ties
    them to no ability score — so the assertion is that the keyword is **present**, not that it
    is non-`None`. Presence is a decision; absence is an oversight.
    """
    missing: list[str] = []
    checked = 0
    for info in pkgutil.iter_modules(core_package.__path__):
        module = importlib.import_module(f"{core_package.__name__}.{info.name}")
        source = Path(module.__file__ or "").read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if not isinstance(node, ast.Call):
                continue
            name = node.func.id if isinstance(node.func, ast.Name) else None
            if name != "D20Test":
                continue
            keywords = {k.arg for k in node.keywords}
            kind = next((k.value for k in node.keywords if k.arg == "kind"), None)
            is_save = (
                isinstance(kind, ast.Attribute)
                and kind.attr == "SAVE"
                and isinstance(kind.value, ast.Name)
                and kind.value.id == "TestKind"
            )
            if not is_save:
                continue
            checked += 1
            if "ability" not in keywords:
                missing.append(f"core.{info.name}:{node.lineno}")

    assert checked >= 6, (
        f"only {checked} saving throws were found in the core, and there were six before "
        "#344. This walk is looking at the wrong thing."
    )
    assert not missing, (
        f"these build a saving throw without naming its ability: {missing}. Without it, "
        "p. 187's Restrained, p. 181's Dodge and the four automatic failures all skip the "
        "save silently — which is exactly the state #344 found."
    )


# --- Automatic failure is not a roll ----------------------------------------------------------


@pytest.mark.parametrize(
    "condition",
    [Condition.PARALYZED, Condition.PETRIFIED, Condition.STUNNED, Condition.UNCONSCIOUS],
)
@pytest.mark.parametrize("ability", ["str", "dex"])
def test_four_conditions_fail_a_strength_or_dexterity_save_without_rolling(
    tmp_path: Path, condition: Condition, ability: str
) -> None:
    """pp. 186, 189, 191: "You automatically fail Strength and Dexterity saving throws."

    **No die at all.** The ruling carries no `D20Result`, because p. 186 says the save fails
    rather than that it is rolled badly — and a number in the ledger that decided nothing reads
    exactly like a save that was rolled and lost.

    The DC is one the creature would comfortably beat, so a rolled save would very likely have
    succeeded: the failure here is the rule, not the seed.
    """
    state = owing_a_save(
        ogre(conditions=Conditions(applied=frozenset({condition}))), ability=ability, dc=2
    )
    ruling, after = roll_the_save(tmp_path / f"{condition}-{ability}", state, "ogre")

    assert ruling.status is Status.RULED
    assert ruling.result is None, "an automatic failure rolls nothing"
    assert Condition.GRAPPLED in after.combatant("ogre").conditions.held, "and it failed"


def test_the_same_creature_still_rolls_a_constitution_save(tmp_path: Path) -> None:
    """The negative case, and the one that makes the parametrised test above mean something.
    All four sentences name **Strength and Dexterity** and no other ability, so a Paralyzed
    creature's Constitution save is an ordinary roll."""
    paralyzed = ogre(conditions=Conditions(applied=frozenset({Condition.PARALYZED})))
    state = owing_a_save(paralyzed, ability="con", dc=2)
    ruling, _ = roll_the_save(tmp_path, state, "ogre")

    assert ruling.result is not None, "Constitution is not one of the two"


def test_a_death_save_is_reached_by_none_of_this(tmp_path: Path) -> None:
    """p. 17 calls it "a special saving throw" of no ability, and an Unconscious creature is
    exactly who makes one. A rule that failed it automatically would kill every character who
    ever dropped — so `ability=None` is a decision, stated at the call site in `core.death`."""
    unconscious = Conditions(applied=frozenset({Condition.UNCONSCIOUS}))
    assert not unconscious.saves_fail_outright(None)
    assert unconscious.saves_fail_outright("dex"), (
        "while a Dexterity save from the same creature does"
    )


def test_an_automatic_failure_whose_rule_states_no_consequence_is_expressible() -> None:
    """The case that decided where the auto-failure is applied.

    `core.save_ends` builds a save with an **empty** `on_failure`: failing to shake a condition
    off simply leaves it, so there is nothing to record. Rewriting the proposal to carry that
    failure as its `outcome` would produce one `Proposal` refuses to construct — "a proposal
    with no test and no outcome decides nothing" — so the branch is selected by the
    adjudicator instead, and the proposal is never rewritten at all.

    Found by writing the test, not by reading the code.
    """
    from srd_rules_engine.core.adjudicate import Proposal, _save_fails_outright
    from srd_rules_engine.core.d20 import D20Test

    paralyzed = ogre(conditions=Conditions(applied=frozenset({Condition.PARALYZED})))
    state = EncounterState.new([hero(), paralyzed]).with_initiative({"pc": 20, "ogre": 5})
    proposal = Proposal(
        test=D20Test(kind=TestKind.SAVE, ability="dex", target=10, target_basis="b"),
        on_failure=(),
    )

    assert _save_fails_outright(state, "ogre", proposal)
    with pytest.raises(ValueError, match="decides nothing"):
        replace(proposal, test=None, outcome=proposal.on_failure)


def test_what_the_act_cost_survives_an_automatic_failure(tmp_path: Path) -> None:
    """0038 clause 6: `always` is what happened because the action happened, and an automatic
    failure is still the save having been owed and met. Skipping the roll must not skip the
    cost with it."""

    paralyzed = ogre(conditions=Conditions(applied=frozenset({Condition.PARALYZED})))
    state = owing_a_save(paralyzed, ability="dex", dc=2)
    ruling, after = roll_the_save(tmp_path, state, "ogre")

    assert ruling.result is None, "no roll"
    # p. 190's Grapple save charges nothing, so the standing assertion is that the branch the
    # adjudicator selected is `always` followed by `on_failure` rather than `on_failure` alone.
    from srd_rules_engine.core.adjudicate import EffectKind

    assert [e.kind for e in ruling.effects] == [EffectKind.CONDITION_APPLIED]
    assert Condition.GRAPPLED in after.combatant("ogre").conditions.held


# --- Disadvantage, Advantage, and their cancellation --------------------------------------------


def test_restrained_gives_a_dexterity_save_disadvantage(tmp_path: Path) -> None:
    """p. 187: "You have Disadvantage on Dexterity saving throws.\""""
    restrained = ogre(conditions=Conditions(applied=frozenset({Condition.RESTRAINED})))
    ruling, _ = roll_the_save(tmp_path, owing_a_save(restrained, ability="dex"), "ogre")

    assert ruling.result is not None
    assert ruling.result.effective is Advantage.DISADVANTAGE


def test_restrained_leaves_a_strength_save_alone(tmp_path: Path) -> None:
    """The clause names Dexterity. A Restrained creature's Strength save is an ordinary roll,
    which is why the better modifier is not the better save — the whole of 0053's Option 1."""
    restrained = ogre(conditions=Conditions(applied=frozenset({Condition.RESTRAINED})))
    ruling, _ = roll_the_save(tmp_path, owing_a_save(restrained, ability="str"), "ogre")

    assert ruling.result is not None
    assert ruling.result.effective is Advantage.NONE


def test_dodging_gives_a_dexterity_save_advantage(tmp_path: Path) -> None:
    """p. 181: "you make Dexterity saving throws with Advantage". Modelled on `ActionBudget`
    since the action shipped and read by no roll until now."""
    dodging = ogre(actions=ActionBudget(dodging=True))
    ruling, _ = roll_the_save(tmp_path, owing_a_save(dodging, ability="dex"), "ogre")

    assert ruling.result is not None
    assert ruling.result.effective is Advantage.ADVANTAGE


def test_a_restrained_dodger_does_not_cancel_because_it_is_no_longer_dodging(
    tmp_path: Path,
) -> None:
    """The interaction I expected to cancel and which does not, for a better reason.

    p. 187's Restrained sets **Speed 0**, and p. 181 ends the Dodge for exactly that: "You lose
    these benefits if you have the Incapacitated condition **or if your Speed is 0**." So the
    Advantage is gone before the cancellation could happen and the save is at plain
    Disadvantage — which is what `is_dodging` re-asking rather than trusting the flag buys.
    """
    both = ogre(
        actions=ActionBudget(dodging=True),
        conditions=Conditions(applied=frozenset({Condition.RESTRAINED})),
    )
    assert both.effective_speeds.walk == 0
    assert not both.is_dodging, "p. 181 took the benefit back"

    ruling, _ = roll_the_save(tmp_path, owing_a_save(both, ability="dex"), "ogre")
    assert ruling.result is not None
    assert ruling.result.effective is Advantage.DISADVANTAGE


def test_advantage_a_rule_granted_cancels_against_restrained(tmp_path: Path) -> None:
    """p. 8: sources on opposite sides cancel. The flags **accumulate** onto whatever the rule
    itself granted rather than replacing it, because cancellation needs both to arrive — an
    implementation that overwrote would hand a Restrained creature clean Advantage.

    Asserted on the transform, because no rule in the engine yet grants Advantage on a save
    the way a spell or feature would; the mechanism is what has to be right before one does.
    """
    from srd_rules_engine.core.adjudicate import Proposal, _as_this_creature_saves
    from srd_rules_engine.core.d20 import D20Test

    restrained = ogre(conditions=Conditions(applied=frozenset({Condition.RESTRAINED})))
    state = EncounterState.new([hero(), restrained]).with_initiative({"pc": 20, "ogre": 5})
    granted = Proposal(
        test=D20Test(
            kind=TestKind.SAVE,
            ability="dex",
            target=10,
            target_basis="b",
            has_advantage=True,
        )
    )

    after = _as_this_creature_saves(state, "ogre", granted)
    assert after.test is not None
    assert after.test.has_advantage and after.test.has_disadvantage, "both, so p. 8 can cancel"


def test_dodge_is_re_asked_rather_than_remembered(tmp_path: Path) -> None:
    """p. 181: "You lose these benefits if you have the Incapacitated condition or if your
    Speed is 0." `is_dodging` re-checks, so a creature that dodged and was then grappled — Speed
    0 — has no Advantage left to bring to its save."""
    stopped = ogre(
        actions=ActionBudget(dodging=True),
        conditions=Conditions(
            applied=frozenset({Condition.GRAPPLED}),
            sources={Condition.GRAPPLED: frozenset({"pc"})},
        ),
    )
    assert stopped.effective_speeds.walk == 0
    ruling, _ = roll_the_save(tmp_path, owing_a_save(stopped, ability="dex"), "ogre")

    assert ruling.result is not None
    assert ruling.result.effective is Advantage.NONE


def test_a_save_of_no_ability_is_left_exactly_as_the_rule_built_it() -> None:
    """p. 17's Death Saving Throw, at the transform.

    It comes back untouched **because every rule keys on the ability** and answers "nothing"
    for a save that has none — not because the transform checks for one. A guard clause doing
    that was there and was removed: a corruption proof showed it carried no weight, since
    `Conditions` was already refusing underneath it.
    """
    from srd_rules_engine.core.adjudicate import Proposal, _as_this_creature_saves
    from srd_rules_engine.core.d20 import D20Test

    restrained = ogre(conditions=Conditions(applied=frozenset({Condition.RESTRAINED})))
    state = EncounterState.new([hero(), restrained]).with_initiative({"pc": 20, "ogre": 5})
    proposal = Proposal(test=D20Test(kind=TestKind.SAVE, target=10, target_basis="b"))

    assert _as_this_creature_saves(state, "ogre", proposal) is proposal


def test_an_attack_roll_is_not_touched_by_any_of_it() -> None:
    """All three rules say *saving throws*. A Restrained creature's attack rolls are hampered
    by p. 187's other clause, which is a different field and a different code path."""
    from srd_rules_engine.core.adjudicate import Proposal, _as_this_creature_saves
    from srd_rules_engine.core.d20 import D20Test

    restrained = ogre(conditions=Conditions(applied=frozenset({Condition.RESTRAINED})))
    state = EncounterState.new([hero(), restrained]).with_initiative({"pc": 20, "ogre": 5})
    proposal = Proposal(
        test=D20Test(kind=TestKind.ATTACK, ability="dex", target=10, target_basis="b")
    )

    assert _as_this_creature_saves(state, "ogre", proposal) is proposal
