"""A Ritual is a long casting, and now runs through the machinery (#371, 0074).

p. 105 names rituals in the sentence that introduces longer casting times:

> Certain spells—**including a spell cast as a Ritual**—require more time to cast: minutes or
> even hours. While you cast a spell with a casting time of 1 minute or more, you must take
> the Magic action on each of your turns, and you must maintain Concentration.

[#250](https://github.com/eddiefiggie/srd-rules-engine/issues/250) built that machinery for
spells whose `CastingTime` is `MINUTES`. A Ritual reached it by no path at all: `ritual_cast`
computed p. 187's ten extra minutes and **had no caller anywhere in the engine**, so a caller
could ritual a spell and take zero turns over it.

**That sentence was also asserted nowhere.** `core.casting` quoted it in a docstring to
explain the gap, and `scripts/verify_d20_rules.py` had never read it — so the clause the whole
issue rests on was, by this repository's own standard, a rule the engine had not verified. It
is asserted now, which is what licenses everything below (R31).
"""

from __future__ import annotations

import sys
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from fixtures.ruleset import fixture_catalogue
from srd_rules_engine.core import (
    Declaration,
    EncounterState,
    Intent,
    Status,
    legal_actions,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.actions import ActionBudget
from srd_rules_engine.core.adjudicate import Adjudicator, Proposal, Resolver
from srd_rules_engine.core.casting import spell_resolvers
from srd_rules_engine.core.d20 import D20Test, TestKind
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import continue_cast_key, ritual_key
from srd_rules_engine.core.rules import Rule, RuleProvenance
from srd_rules_engine.core.spellcasting import (
    CastingTime,
    Spell,
    SpellSlots,
    ritual_turns_to_cast,
)
from srd_rules_engine.core.state import Combatant
from srd_rules_engine.memory.store import JsonMemoryStore

#: An action-timed spell with the tag. p. 187 adds ten minutes to "normal", and normal here
#: is an action — so the whole casting is ten minutes, which is 100 Magic actions.
RITE = Spell(rule_id="fixture:rite", level=1, ritual=True)
#: A spell that already takes a minute, so the ritual is eleven minutes rather than ten. The
#: case that discriminates "ten minutes" from "ten minutes **longer than normal**".
SLOW_RITE = Spell(
    rule_id="fixture:slow-rite",
    level=1,
    ritual=True,
    casting_time=CastingTime.MINUTES,
    casting_minutes=1,
)
#: No tag. p. 187 rituals "a spell prepared that has the Ritual tag" and nothing else.
PLAIN = Spell(rule_id="fixture:plain", level=1)

ALL_SPELLS = (RITE, SLOW_RITE, PLAIN)

RULESET = load_fixture_ruleset(
    "ritual",
    tuple(
        Rule(
            id=spell.rule_id,
            summary=f"An invented spell of level {spell.level}.",
            provenance=RuleProvenance.FIXTURE,
            rationale=(
                "The mechanism is real and the spell is not. No SRD spell description ships "
                "in this repository."
            ),
        )
        for spell in ALL_SPELLS
    ),
)


def _effects(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    return Proposal(
        test=D20Test(kind=TestKind.CHECK, target=10, target_basis="invented flat difficulty 10"),
        citations=("fixture:spell",),
    )


def _caster(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "mage",
        "name": "Mage",
        "hit_points": 30,
        "max_hit_points": 30,
        "armour_class": 12,
        "abilities": {"str": 8, "dex": 14, "con": 12, "int": 16},
        "proficiency_bonus": 2,
        "slots": SpellSlots(total={1: 2}),
        "spells": ALL_SPELLS,
        "prepared": frozenset(spell.rule_id for spell in ALL_SPELLS),
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def _encounter(actor: Combatant | None = None) -> EncounterState:
    other = Combatant(
        id="boar",
        name="Boar",
        hit_points=11,
        max_hit_points=11,
        armour_class=11,
        abilities={"str": 12, "dex": 10, "con": 12},
        proficiency_bonus=2,
    )
    return EncounterState.new([actor or _caster(), other]).with_initiative({"mage": 20, "boar": 5})


def _adjudicator(path: Path) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    resolvers: dict[Spell, Resolver] = {spell: _effects for spell in ALL_SPELLS}
    return Adjudicator(
        ruleset=RULESET,
        resolvers=spell_resolvers(resolvers),
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl",
            engine_version="t",
            catalogue_version=fixture_catalogue().version,
            session_id="s",
        ),
        catalogue=fixture_catalogue(),
        seed_source=lambda: 3,
    )


def _ritual(state: EncounterState, spell: Spell) -> Declaration:
    offered = read(state, "mage")
    return Declaration(
        actor_id="mage",
        intent=Intent(action_key=ritual_key(spell.rule_id)),
        rule_id=spell.rule_id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


# --- How long it takes ---------------------------------------------------------------


def test_an_action_timed_ritual_owes_ten_minutes_of_magic_actions() -> None:
    """p. 187's ten minutes, at 0021's ten turns a minute. The spell's normal casting time is
    an action, which contributes no minutes — and is not lost, because it *is* one of the
    Magic actions p. 105 charges on every turn."""
    assert ritual_turns_to_cast(RITE) == 100


def test_a_ritual_adds_its_ten_minutes_to_the_spells_own() -> None:
    """ "10 minutes **longer to cast than normal**", so a one-minute spell rituals in eleven.

    The discriminating case: an implementation reading p. 187 as "a ritual takes ten minutes"
    passes the test above and fails this one.
    """
    assert ritual_turns_to_cast(SLOW_RITE) == 110


# --- What the menu offers ------------------------------------------------------------


def test_a_prepared_tagged_spell_is_offered_as_a_ritual() -> None:
    keys = {action.key for action in legal_actions(_encounter(), "mage")}

    assert ritual_key(RITE.rule_id) in keys


def test_a_spell_without_the_tag_is_not_offered_as_a_ritual() -> None:
    keys = {action.key for action in legal_actions(_encounter(), "mage")}

    assert ritual_key(PLAIN.rule_id) not in keys


def test_a_spell_that_is_not_prepared_is_not_offered_as_a_ritual() -> None:
    """p. 187 puts the precondition before the permission: "If you have a spell **prepared**
    that has the Ritual tag"."""
    state = _encounter(_caster(prepared=frozenset()))

    keys = {action.key for action in legal_actions(state, "mage")}

    assert ritual_key(RITE.rule_id) not in keys


def test_a_ritual_is_offered_with_every_slot_spent() -> None:
    """The clause that makes a Ritual worth casting, and the one a slot-gated offer would
    remove exactly when the document makes it most useful. p. 187: "It also doesn't expend a
    spell slot"."""
    empty = _caster(slots=SpellSlots(total={1: 1}, spent={1: 1}))
    state = _encounter(empty)

    keys = {action.key for action in legal_actions(state, "mage")}

    assert ritual_key(RITE.rule_id) in keys
    assert not any(key.startswith("cast:") for key in keys), "no slot is payable, so no cast"


def test_the_offer_names_no_slot_level(tmp_path: Path) -> None:
    """p. 187 draws the consequence itself — "which means the ritual version of a spell can't
    be cast at a higher level" — so a key carrying a level would offer what that sentence
    forbids. `ritual:<spell>` has nowhere to put one."""
    offer = next(
        action
        for action in legal_actions(_encounter(), "mage")
        if action.key == ritual_key(RITE.rule_id)
    )

    assert "slot_level" not in offer.detail
    assert offer.detail["expends_slot"] is False


# --- Beginning one -------------------------------------------------------------------


def test_beginning_a_ritual_starts_a_long_cast_that_owes_no_slot(tmp_path: Path) -> None:
    """The whole of #371 in one assertion: the ritual becomes a `LongCast`, which is what
    charges the turns, and its slot level is `None` rather than a number."""
    state = _encounter()

    ruling, state = _adjudicator(tmp_path).adjudicate(state, _ritual(state, RITE))

    assert ruling.status is Status.RULED
    in_progress = state.combatant("mage").long_cast
    assert in_progress is not None
    assert in_progress.spell_id == RITE.rule_id
    # **99, not 100.** The opening Magic action was charged by this adjudication, and
    # `turns_remaining` counts this turn's among those owed — so a hundred here would count
    # it twice. Building the ritual on this machinery is what found the ordinary long cast
    # doing exactly that (#371); a one-minute casting cost eleven turns.
    assert in_progress.turns_remaining == 99
    assert in_progress.slot_level is None
    assert not in_progress.expends_slot


def test_beginning_a_ritual_begins_concentration(tmp_path: Path) -> None:
    """p. 105: "you must maintain Concentration while you do so", and a Ritual is one of the
    castings that sentence is about."""
    state = _encounter()

    _, state = _adjudicator(tmp_path).adjudicate(state, _ritual(state, RITE))

    assert state.combatant("mage").concentration.active


def test_beginning_a_ritual_spends_no_slot(tmp_path: Path) -> None:
    state = _encounter()
    before = state.combatant("mage").slots

    _, state = _adjudicator(tmp_path).adjudicate(state, _ritual(state, RITE))

    assert state.combatant("mage").slots == before


# --- Finishing one -------------------------------------------------------------------


def _run_to_completion(state: EncounterState, adjudicator: Adjudicator) -> EncounterState:
    ruling, state = adjudicator.adjudicate(state, _ritual(state, RITE))
    assert ruling.status is Status.RULED
    guard = 0
    while state.combatant("mage").long_cast is not None:
        state = state.advanced_turn().advanced_turn()
        ruling, state = adjudicator.adjudicate(
            state,
            Declaration(
                actor_id="mage",
                intent=Intent(action_key=continue_cast_key(RITE.rule_id)),
                rule_id=RITE.rule_id,
            ),
        )
        guard += 1
        assert guard <= 200, "a ritual that never finishes is a loop bound, not a rule"
    return state


def test_a_completed_ritual_expends_no_slot(tmp_path: Path) -> None:
    """p. 187: "It also doesn't expend a spell slot."

    The ordinary long cast spends its slot on the last Magic action (0065); a ritual reaches
    the same line with nothing to spend.
    """
    state = _encounter()
    before = state.combatant("mage").slots

    state = _run_to_completion(state, _adjudicator(tmp_path))

    assert state.combatant("mage").slots == before
    assert state.combatant("mage").long_cast is None


def test_a_ritual_charges_every_one_of_its_turns(tmp_path: Path) -> None:
    """The defect this issue names: "a caller can ritual a spell and take zero turns doing
    it". A hundred Magic actions is what ten minutes costs."""
    state = _encounter()
    adjudicator = _adjudicator(tmp_path)

    _, state = adjudicator.adjudicate(state, _ritual(state, RITE))
    charged = 1
    while state.combatant("mage").long_cast is not None:
        state = state.advanced_turn().advanced_turn()
        _, state = adjudicator.adjudicate(
            state,
            Declaration(
                actor_id="mage",
                intent=Intent(action_key=continue_cast_key(RITE.rule_id)),
                rule_id=RITE.rule_id,
            ),
        )
        charged += 1
        assert charged <= 200

    assert charged == 100


# --- What is refused -----------------------------------------------------------------


def test_no_second_ritual_is_offered_while_one_is_running(tmp_path: Path) -> None:
    """p. 105: "To cast the spell again, you must start over" — one casting at a time, and
    the menu says so rather than offering a ritual that would abandon the first.

    Asserted with the Action handed back, because a caster mid-ritual has spent it and an
    empty menu would pass this for the wrong reason — the same vacuous-fixture shape
    `AGENTS.md` names.
    """
    state = _encounter()
    _, state = _adjudicator(tmp_path).adjudicate(state, _ritual(state, RITE))
    refreshed = replace(state.combatant("mage"), actions=ActionBudget())
    state = replace(state, combatants=(refreshed, state.combatant("boar")))

    keys = {action.key for action in legal_actions(state, "mage")}

    assert continue_cast_key(RITE.rule_id) in keys, "the fixture has an Action to spend"
    assert not any(key.startswith("ritual:") for key in keys)


def test_the_resolver_refuses_a_second_ritual_even_though_the_menu_will_not_offer_one(
    tmp_path: Path,
) -> None:
    """[0062](../docs/decisions/0062-the-menu-is-not-a-promise.md): the resolver asks the rule
    itself rather than deriving legality from the menu, so the guard is reached directly here.

    It is unreachable through adjudication — `_validate` rejects the key before the resolver
    runs — which is exactly why it needs a test of its own rather than one that would pass on
    the rejection and prove nothing about the guard.
    """
    state = _encounter()
    _, state = _adjudicator(tmp_path).adjudicate(state, _ritual(state, RITE))

    resolver = spell_resolvers({SLOW_RITE: _effects})[SLOW_RITE.rule_id]

    with pytest.raises(ValueError, match="already part-way through"):
        resolver(
            state=state,
            declaration=Declaration(
                actor_id="mage",
                intent=Intent(action_key=ritual_key(SLOW_RITE.rule_id)),
                rule_id=SLOW_RITE.rule_id,
            ),
            facts={},
        )


def test_a_cantrip_cannot_carry_the_ritual_tag() -> None:
    """p. 187 rituals a *prepared* spell and saves a slot; a cantrip is neither prepared in
    that sense nor spends one. The document describes no ritual version of a cantrip, so the
    combination is refused rather than resolved into a guess."""
    with pytest.raises(ValueError, match="cantrip carrying the Ritual tag"):
        Spell(rule_id="fixture:spark", level=0, ritual=True)


def test_a_long_cast_slot_level_of_none_is_not_a_level_of_zero() -> None:
    """A cantrip is a level 0 spell cast without a slot; a Ritual of a level 3 spell is a
    level 3 casting that spends nothing. Collapsing the two would say a ritualised spell was
    a cantrip, which is a claim about the spell rather than about how it was cast."""
    from srd_rules_engine.core.spellcasting import LongCast

    ritual = LongCast(spell_id="x", slot_level=None, turns_remaining=1)
    cantrip = LongCast(spell_id="x", slot_level=0, turns_remaining=1)

    assert not ritual.expends_slot
    assert cantrip.expends_slot, "level 0 is a level; None is the absence of one"


def test_the_ritual_shape_is_claimed_over_something_with_a_caller() -> None:
    """`ENGINE_SHAPES` claimed `ritual` over `ritual_cast`, which had **no caller anywhere in
    the engine** — the same overstatement #381 found withheld for Opportunity Attacks, except
    already asserted. A caller could not cast a ritual at all; the function computed a value
    and returned it to nobody.

    Asserted here rather than only in the record, because the claim is the thing that has to
    stay true.
    """
    from srd_rules_engine.core.inventory import load_inventory

    shape = next(s for s in load_inventory().shapes if s.id == "ritual")
    assert shape.implemented

    source = Path("src/srd_rules_engine/core/casting.py").read_text()
    assert "ritual_cast(" in source, "the refusals are reached from the casting path"
    assert "_ritual_begun" in source, "and a ritual becomes a LongCast"
