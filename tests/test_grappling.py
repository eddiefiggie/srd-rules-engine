"""p. 182's Grappling rules: the endings, before anything can impose the condition (#335).

> However a grapple is initiated, it follows these rules.

That sentence is the scope. p. 190's Unarmed Strike is one initiator and the bestiary is full
of others, each stating its own escape DC — so the rules for getting out are common to all of
them and are built once.

**The exit ships before the entrance deliberately.** A condition the engine can impose and
cannot lift ends a playthrough; one it cannot impose merely fails to start one.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Combatant,
    Condition,
    Conditions,
    Declaration,
    EffectKind,
    EncounterState,
    Grapple,
    Intent,
    Ledger,
    Status,
    load_ruleset,
    read,
)
from srd_rules_engine.core.actions import ActionKind
from srd_rules_engine.core.grappling import (
    ESCAPE_RULE_ID,
    ESCAPE_SKILLS,
    RELEASE_RULE_ID,
    can_be_escaped,
    ended_by_circumstance,
    escape_key,
    grappling_resolvers,
    grappling_rules,
    release_key,
)
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import RELEASE_ONLY_ON_YOUR_TURN
from srd_rules_engine.core.skills import Skill
from srd_rules_engine.memory.store import JsonMemoryStore

RULESET = load_ruleset(grappling_rules())

#: A DC nothing can reach and one nothing can miss, so a test naming an outcome is naming the
#: rule rather than the seed. The escape check is 1d20 + bonus, so 30 is unreachable at these
#: modifiers and 1 is automatic.
UNREACHABLE_DC = 30
CERTAIN_DC = 1


def grappled_by(
    grappler_id: str, *, escape_dc: int | None = 13, range_feet: int | None = 5
) -> Conditions:
    return Conditions(
        applied=frozenset({Condition.GRAPPLED}),
        sources={Condition.GRAPPLED: frozenset({grappler_id})},
        grapple=Grapple(escape_dc=escape_dc, range_feet=range_feet),
    )


def hero(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "pc",
        "name": "Pc",
        "hit_points": 20,
        "max_hit_points": 20,
        "armour_class": 13,
        "abilities": {"str": 14, "dex": 14, "con": 12},
        "proficiency_bonus": 2,
        "is_player_character": True,
        "position": Position(0, 0, 0),
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
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(*combatants: Combatant) -> EncounterState:
    people = combatants or (hero(), ogre())
    return EncounterState.new(list(people)).with_initiative({"pc": 20, "ogre": 5})


def ogre_acting(*combatants: Combatant) -> EncounterState:
    """The same encounter with the grappler acting.

    p. 182 lets a grappler release "at any time", and the read surface offers actions only to
    the creature whose turn it is — so the release is reachable on the ogre's turn and is
    disclosed as narrowed (`RELEASE_ONLY_ON_YOUR_TURN`, #341). These tests exercise what is
    built; `test_the_release_timing_is_disclosed_not_enforced` covers what is not.
    """
    people = combatants or (hero(), ogre())
    return EncounterState.new(list(people)).with_initiative({"pc": 5, "ogre": 20})


def build(path: Path) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers=grappling_resolvers(),
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 5,
    )


def declare(state: EncounterState, key: str, rule_id: str, actor_id: str = "pc") -> Declaration:
    offered = read(state, actor_id)
    return Declaration(
        actor_id=actor_id,
        intent=Intent(action_key=key),
        rule_id=rule_id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


# --- The terms of the grapple ---------------------------------------------------------------


def test_the_terms_belong_to_the_grapple_and_the_grappler_to_the_condition() -> None:
    """p. 182 says "the **grapple's** escape DC" and "the **grapple's** range", while who is
    holding you is what `sources` already answers for Frightened too. One identity, one home."""
    held = grappled_by("ogre", escape_dc=13, range_feet=5)
    assert held.grappler_id == "ogre"
    assert held.grapple is not None
    assert held.grapple.escape_dc == 13
    assert held.grapple.range_feet == 5


def test_terms_without_a_grapple_are_refused() -> None:
    """The refusal `durations` already makes for a span nobody applied: numbers describing a
    grapple that does not exist describe nothing."""
    with pytest.raises(ValueError, match="not Grappled"):
        Conditions(grapple=Grapple(escape_dc=13))


# --- The escape check, which is a decision --------------------------------------------------


def test_both_checks_are_offered_and_the_choice_is_the_creature_s() -> None:
    """p. 182: "a Strength (Athletics) **or** Dexterity (Acrobatics) check". Two entries rather
    than one parameterised entry, because the choice is p. 182's own — the shape the Dash uses
    for its choice of speed."""
    state = encounter(replace(hero(), conditions=grappled_by("ogre")), ogre())
    offered = {action.key for action in read(state, "pc").actions}
    assert offered >= {escape_key(Skill.ATHLETICS), escape_key(Skill.ACROBATICS)}


def test_each_offer_carries_the_bonus_that_tells_them_apart() -> None:
    """Two entries an agent cannot distinguish are not a choice. The hero has Athletics and not
    Acrobatics, so the Proficiency Bonus separates them."""
    athletic = replace(hero(), conditions=grappled_by("ogre"), skills=frozenset({Skill.ATHLETICS}))
    state = encounter(athletic, ogre())
    detail = {a.key: a.detail for a in read(state, "pc").actions if a.key.startswith("escape-")}
    assert detail[escape_key(Skill.ATHLETICS)]["bonus"] == 4, "+2 Strength, +2 proficiency"
    assert detail[escape_key(Skill.ACROBATICS)]["bonus"] == 2, "+2 Dexterity, no proficiency"


def test_a_grapple_with_no_stated_dc_offers_no_check() -> None:
    """A check without a target number is not a check. The engine declines rather than choosing
    a DC the document never stated (R31) — and the other endings still work, so this is not a
    grapple with no exit."""
    unstated = replace(hero(), conditions=grappled_by("ogre", escape_dc=None))
    assert not can_be_escaped(unstated)
    offered = {a.key for a in read(encounter(unstated, ogre()), "pc").actions}
    assert not any(key.startswith("escape-grapple") for key in offered)


def test_a_creature_that_is_not_grappled_is_offered_no_escape() -> None:
    offered = {a.key for a in read(encounter(), "pc").actions}
    assert not any(key.startswith("escape-grapple") for key in offered)


def test_a_successful_check_ends_the_condition(tmp_path: Path) -> None:
    """p. 182: "ending the condition on itself on a success"."""
    state = encounter(replace(hero(), conditions=grappled_by("ogre", escape_dc=CERTAIN_DC)), ogre())
    ruling, after = build(tmp_path).adjudicate(
        state, declare(state, escape_key(Skill.ATHLETICS), ESCAPE_RULE_ID)
    )

    assert ruling.status is Status.RULED
    assert Condition.GRAPPLED not in after.combatant("pc").conditions.held


def test_a_failed_check_costs_the_action_and_nothing_else(tmp_path: Path) -> None:
    """p. 182 gives failure no consequence beyond the spent action — the grapple is not made
    worse, and the creature does not move."""
    state = encounter(
        replace(hero(), conditions=grappled_by("ogre", escape_dc=UNREACHABLE_DC)), ogre()
    )
    ruling, after = build(tmp_path).adjudicate(
        state, declare(state, escape_key(Skill.ATHLETICS), ESCAPE_RULE_ID)
    )

    assert ruling.status is Status.RULED
    escaper = after.combatant("pc")
    assert Condition.GRAPPLED in escaper.conditions.held, "still held"
    assert escaper.conditions.grapple == state.combatant("pc").conditions.grapple, "terms unchanged"
    assert escaper.position == state.combatant("pc").position, "p. 182 grants no movement"
    spare = escaper.actions.available(ActionKind.ACTION, escaper.conditions)
    assert not spare, "and the Action is spent either way"


def test_the_check_is_rolled_against_the_grapples_own_dc(tmp_path: Path) -> None:
    """R4, and the reason the DC is stored rather than recomputed: a stat block states it
    outright ("escape DC 13", p. 259) and p. 190 derives it from the grappler at the moment of
    the grapple. Recomputing it now would produce a different number for the first and ignore
    what was recorded for the second."""
    state = encounter(replace(hero(), conditions=grappled_by("ogre", escape_dc=17)), ogre())
    ruling, _ = build(tmp_path).adjudicate(
        state, declare(state, escape_key(Skill.ACROBATICS), ESCAPE_RULE_ID)
    )
    assert ruling.result is not None
    assert ruling.result.target == 17
    assert "17" in ruling.result.target_basis and "p. 182" in ruling.result.target_basis


# --- The release, which costs nothing --------------------------------------------------------


def test_the_grappler_is_offered_a_release_and_it_costs_no_action() -> None:
    """p. 182: "the grappler can release the target at any time (**no action required**)". So
    the offer is deliberately not gated on a spare Action."""
    spent = replace(ogre(), actions=replace(ogre().actions, action_spent=True))
    state = ogre_acting(replace(hero(), conditions=grappled_by("ogre")), spent)
    offered = {a.key: a.detail for a in read(state, "ogre").actions}
    assert release_key("pc") in offered
    assert offered[release_key("pc")] == {"costs_action": False}


def test_releasing_ends_the_condition(tmp_path: Path) -> None:
    state = ogre_acting(replace(hero(), conditions=grappled_by("ogre")), ogre())
    ruling, after = build(tmp_path).adjudicate(
        state, declare(state, release_key("pc"), RELEASE_RULE_ID, actor_id="ogre")
    )

    assert ruling.status is Status.RULED
    assert Condition.GRAPPLED not in after.combatant("pc").conditions.held
    assert any(e.kind is EffectKind.CONDITION_ENDED for e in ruling.effects)


def test_the_grappled_creature_is_not_offered_the_release() -> None:
    """The negative case, and the first version of it asserted nothing.

    It checked that the pc was not offered `release-grapple:ogre` — but the ogre is not
    grappled by anyone, so no offer naming it could exist under any implementation, correct or
    not. The corruption proof caught it: replacing "is this **my** grapple" with "is this
    anyone's grapple" left the assertion green.

    What the rule actually forbids is the **victim** releasing the grapple it is held in. p. 182
    gives the release to the grappler, and letting go of yourself is not a thing it offers.
    """
    state = encounter(replace(hero(), conditions=grappled_by("ogre")), ogre())
    offered = {a.key for a in read(state, "pc").actions}
    assert release_key("pc") not in offered, "the held creature may not release itself"
    assert not any(key.startswith("release-grapple") for key in offered)


def test_the_release_timing_is_disclosed_not_enforced() -> None:
    """p. 182 says "at any time" and this engine says "on your turn" (#341).

    The narrowing is in the safe direction — what is offered **is** p. 182's release, with its
    effect and its zero cost; only its timing is short. So it is named rather than left for a
    reader to discover by wondering why the ogre cannot let go.

    Disclosed to the grappler, because that is the only creature the clause can bite.
    """
    state = ogre_acting(replace(hero(), conditions=grappled_by("ogre")), ogre())

    grappler = read(state, "ogre").situation
    assert grappler is not None
    assert RELEASE_ONLY_ON_YOUR_TURN in grappler.unenforced_clauses

    # And not to a bystander, who has no grapple to be told about the timing of.
    alone = EncounterState.new([hero()]).with_initiative({"pc": 20})
    bystander = read(alone, "pc").situation
    assert bystander is not None
    assert RELEASE_ONLY_ON_YOUR_TURN not in bystander.unenforced_clauses


# --- The two endings nobody decides ----------------------------------------------------------


def test_an_incapacitated_grappler_ends_the_grapple() -> None:
    """p. 182: "The condition also ends if the grappler has the Incapacitated condition"."""
    limp = replace(ogre(), conditions=Conditions(applied=frozenset({Condition.INCAPACITATED})))
    state = encounter(replace(hero(), conditions=grappled_by("ogre")), limp)
    assert ended_by_circumstance(state) == ("pc",)


def test_distance_beyond_the_grapples_range_ends_it() -> None:
    """p. 182: "or if the distance between the Grappled target and the grappler exceeds the
    grapple's range". **Exceeds**, so the range itself still holds."""
    at_range = encounter(
        replace(hero(), conditions=grappled_by("ogre", range_feet=5), position=Position(5, 0, 0)),
        ogre(),
    )
    assert ended_by_circumstance(at_range) == (), "5 feet does not exceed a range of 5"

    beyond = encounter(
        replace(hero(), conditions=grappled_by("ogre", range_feet=5), position=Position(10, 0, 0)),
        ogre(),
    )
    assert ended_by_circumstance(beyond) == ("pc",)


def test_an_unstated_range_leaves_the_grapple_held() -> None:
    """0030 clause 1. Lifting a condition against a bound the engine had to invent would remove
    a grapple the rules did not remove; declining leaves the state a ruleset stated."""
    far = encounter(
        replace(
            hero(), conditions=grappled_by("ogre", range_feet=None), position=Position(500, 0, 0)
        ),
        ogre(),
    )
    assert ended_by_circumstance(far) == ()


def test_an_encounter_with_no_positions_leaves_the_grapple_held() -> None:
    """The same refusal for the same reason: an engine with no distance to measure has not
    found the creatures close enough, it has found nothing."""
    nowhere = encounter(
        replace(hero(), conditions=grappled_by("ogre"), position=None),
        replace(ogre(), position=None),
    )
    assert ended_by_circumstance(nowhere) == ()


def test_a_grapple_whose_grappler_left_the_encounter_is_left_alone() -> None:
    """p. 182 does not say what becomes of it, and inventing a release is inventing an
    outcome."""
    orphaned = EncounterState.new(
        [replace(hero(), conditions=grappled_by("gone"))]
    ).with_initiative({"pc": 20})
    assert ended_by_circumstance(orphaned) == ()


def test_the_endings_are_applied_where_state_settles_not_only_on_a_turn_boundary(
    tmp_path: Path,
) -> None:
    """The derivation runs inside `_apply`, so a grapple p. 182 has already ended is lifted as
    the ruling lands rather than at the next turn boundary.

    The escape check **fails** here, against a DC nothing can reach — and the creature is freed
    anyway, because its grappler is Incapacitated and p. 182 ends the grapple for a reason the
    escape attempt has nothing to do with. A sweep alone would have left it held by an
    unconscious ogre for the rest of the turn.
    """
    limp = replace(ogre(), conditions=Conditions(applied=frozenset({Condition.INCAPACITATED})))
    state = encounter(
        replace(hero(), conditions=grappled_by("ogre", escape_dc=UNREACHABLE_DC)), limp
    )
    assert Condition.GRAPPLED in state.combatant("pc").conditions.held

    ruling, after = build(tmp_path).adjudicate(
        state, declare(state, escape_key(Skill.ATHLETICS), ESCAPE_RULE_ID)
    )

    assert ruling.status is Status.RULED
    assert ruling.result is not None and not ruling.result.succeeded, "the check missed"
    assert Condition.GRAPPLED not in after.combatant("pc").conditions.held
    assert not any(e.kind is EffectKind.CONDITION_ENDED for e in ruling.effects), (
        "and no ruling claimed the ending — nothing decided it (p. 182)"
    )


# --- What p. 182 offers and this does not ----------------------------------------------------


def test_both_checks_share_one_rule_id() -> None:
    """p. 182 states one rule that offers a choice of check. A rule id per check would report
    two rules in the ledger where the document has one."""
    assert {rule.id for rule in grappling_rules()} == {ESCAPE_RULE_ID, RELEASE_RULE_ID}
    assert set(grappling_resolvers()) == {ESCAPE_RULE_ID, RELEASE_RULE_ID}


def test_the_two_derived_endings_have_no_rule_id() -> None:
    """They are not decisions. Giving them a rule id would invite a caller to declare one, and
    a declared ending is an ending somebody chose."""
    assert len(grappling_rules()) == 2, "the escape and the release, and nothing else"


def test_the_document_offers_exactly_these_two_checks() -> None:
    assert ESCAPE_SKILLS == (Skill.ATHLETICS, Skill.ACROBATICS)
    with pytest.raises(ValueError, match="neither"):
        escape_key(Skill.PERCEPTION)
