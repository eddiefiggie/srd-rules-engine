"""Casting a spell: the engine spends what it costs, the ruleset says what it does (#248).

[0038](../docs/decisions/0038-a-spell-is-data-the-caster-carries.md) is the reasoning. Three
things here are easy to get wrong, and each wrong version passes most of a suite:

* **Casting and spending a slot are separate facts.** p. 104's *Casting without Slots* names
  four routes that expend none, and an implementation that couples them passes every levelled
  test and is wrong for every cantrip — the most frequently cast thing in play.
* **The cost is not a consequence.** A slot is spent because the casting happened, not because
  the roll went one way, so it lives in `Proposal.always`. Duplicating it into every branch is
  safe until someone adds a branch.
* **The engine owns the cost, not the ruleset.** A spell is the first mechanic whose effect
  comes from outside, so a resolver that expended its own slot could forget to — and the
  failure is invisible: the spell works, the ledger records a Ruling, only the count is wrong.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Combatant,
    Condition,
    D20Test,
    Declaration,
    EffectKind,
    EncounterState,
    Intent,
    Ledger,
    Proposal,
    Resolution,
    Rule,
    RuleProvenance,
    Status,
    TestKind,
    cast_key,
    load_fixture_ruleset,
    read,
    read_ledger,
    spell_resolvers,
)
from srd_rules_engine.core.actions import ActionBudget, ActionKind
from srd_rules_engine.core.casting import spell_resolver
from srd_rules_engine.core.read_surface import cast_declared
from srd_rules_engine.core.spellcasting import CastingTime, Spell, SpellSlots
from srd_rules_engine.memory.store import JsonMemoryStore

# --- Invented spells. No SRD spell content ships here, now or ever (R31). ---------------

SPARK = Spell(rule_id="fixture:spark", level=0)
BOLT = Spell(rule_id="fixture:bolt", level=1)
HOLD = Spell(rule_id="fixture:hold", level=2, requires_concentration=True)
QUICK = Spell(rule_id="fixture:quick", level=1, casting_time=CastingTime.BONUS_ACTION)
ALL_SPELLS = (SPARK, BOLT, HOLD, QUICK)

RULES = tuple(
    Rule(
        id=spell.rule_id,
        summary=f"An invented spell of level {spell.level}.",
        provenance=RuleProvenance.FIXTURE,
        rationale=(
            "The mechanism is real and the spell is not. No SRD spell description ships in "
            "this repository, so every spell exercised here is declared fixture."
        ),
    )
    for spell in ALL_SPELLS
)
RULESET = load_fixture_ruleset("casting", RULES)


def effects_of(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    """What a ruleset brings: the spell's own effect, and nothing about what it cost."""
    return Proposal(
        test=D20Test(kind=TestKind.CHECK, target=10, target_basis="invented flat difficulty 10"),
        citations=("fixture:spell",),
    )


def caster(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "mage",
        "name": "Mage",
        "hit_points": 30,
        "max_hit_points": 30,
        "armour_class": 12,
        "abilities": {"str": 8, "dex": 14, "con": 12, "int": 16},
        "proficiency_bonus": 2,
        "is_player_character": True,
        "slots": SpellSlots(total={1: 2, 2: 1}),
        "spells": ALL_SPELLS,
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def boar() -> Combatant:
    return Combatant(
        id="boar",
        name="Boar",
        hit_points=11,
        max_hit_points=11,
        armour_class=11,
        abilities={"str": 12, "dex": 10, "con": 12},
        proficiency_bonus=2,
    )


def encounter(actor: Combatant | None = None) -> EncounterState:
    return EncounterState.new([actor or caster(), boar()]).with_initiative({"mage": 20, "boar": 5})


def build(path: Path, *, seed: int = 4) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers=spell_resolvers({spell: effects_of for spell in ALL_SPELLS}),
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: seed,
    )


def cast(state: EncounterState, spell: Spell, level: int) -> Declaration:
    offered = read(state, "mage")
    return Declaration(
        actor_id="mage",
        intent=Intent(action_key=cast_key(spell.rule_id, level)),
        rule_id=spell.rule_id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def slots_left(ruling_state: EncounterState, level: int) -> int:
    slots = ruling_state.combatant("mage").slots
    assert slots is not None
    return slots.remaining(level)


# --- p. 104: casting and spending a slot are separate facts -------------------------------


def test_a_cantrip_costs_no_slot(tmp_path: Path) -> None:
    """p. 178: "A cantrip is a level 0 spell, which is cast **without a spell slot**." An
    implementation that couples casting to expenditure passes every other test in this file."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, cast(state, SPARK, 0))

    assert slots_left(after, 1) == 2, "a cantrip touched no slot"
    assert "mage" not in after.slots_expended_this_turn, (
        "p. 105's one slot per turn has nothing to say about a spell that spends none"
    )


def test_a_levelled_spell_expends_the_slot_it_was_declared_at(tmp_path: Path) -> None:
    """p. 104: "you expend a slot of that spell's level or higher"."""
    state = encounter()
    ruling, after = build(tmp_path).adjudicate(state, cast(state, BOLT, 2))

    assert slots_left(after, 2) == 0 and slots_left(after, 1) == 2, (
        "the declared slot, not the cheapest"
    )
    spent = [e for e in ruling.effects if e.kind is EffectKind.SPELL_SLOT_EXPENDED]
    assert [e.amount for e in spent] == [2]


def test_the_cost_applies_however_the_roll_went(tmp_path: Path) -> None:
    """0038 clause 6. p. 104 ties expenditure to the casting, not to the outcome — so the
    slot goes whether the spell's own test succeeded or failed."""
    outcomes = set()
    for seed in range(40):
        state = encounter()
        ruling, after = build(tmp_path / f"s{seed}", seed=seed).adjudicate(
            state, cast(state, BOLT, 1)
        )
        assert ruling.result is not None
        outcomes.add(ruling.result.succeeded)
        assert slots_left(after, 1) == 1, "the slot went regardless"
    assert outcomes == {True, False}, "precondition: the sweep saw the test both ways"


def test_the_cost_is_recorded_in_the_ledger(tmp_path: Path) -> None:
    """R5/R30. A cost the record does not show is a cost a session review cannot audit."""
    state = encounter()
    build(tmp_path).adjudicate(state, cast(state, BOLT, 1))

    kinds: list[object] = []
    for entry in read_ledger(tmp_path / "ledger.jsonl").entries:
        if entry.type != "ruling":
            continue
        effects = entry.payload.get("effects", ())
        assert isinstance(effects, list)
        kinds.extend(effect["kind"] for effect in effects)
    assert str(EffectKind.SPELL_SLOT_EXPENDED) in kinds


def test_the_cost_is_recorded_before_the_consequence(tmp_path: Path) -> None:
    """The order they happened in. `always` is walked first so a conditional in the selected
    branch reads a state the cost has already settled."""
    state = encounter()
    ruling, _ = build(tmp_path).adjudicate(state, cast(state, HOLD, 2))

    kinds = [e.kind for e in ruling.effects]
    assert kinds[:3] == [
        EffectKind.ACTION_SPENT,
        EffectKind.SPELL_SLOT_EXPENDED,
        EffectKind.CONCENTRATION_BEGUN,
    ]


# --- p. 179: a Concentration names a rule id ----------------------------------------------


def test_a_concentration_spell_begins_concentration_naming_its_rule(tmp_path: Path) -> None:
    """0038 clause 7, and #241. The rule id rather than a spell name, because p. 179 also
    covers "activate another effect that requires Concentration" and an item's effect has no
    spell name to record."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, cast(state, HOLD, 2))

    assert after.combatant("mage").concentration.rule_id == HOLD.rule_id
    situation = read(after, "mage").situation
    assert situation is not None
    assert situation.concentrating_on == HOLD.rule_id


def test_casting_a_second_concentration_spell_replaces_the_first(tmp_path: Path) -> None:
    """p. 179's replacement, reached through casting for the first time. Nothing new is
    built for it — `Concentration.begin` has held the rule since #19 and had no caller."""
    state = encounter(replace(caster(), slots=SpellSlots(total={2: 2})))
    _, after = build(tmp_path).adjudicate(state, cast(state, HOLD, 2))
    assert after.combatant("mage").concentration.rule_id == HOLD.rule_id

    advanced = after.advanced_turn().advanced_turn()
    _, again = build(tmp_path / "b").adjudicate(advanced, cast(advanced, HOLD, 2))
    assert again.combatant("mage").concentration.rule_id == HOLD.rule_id


def test_a_spell_that_does_not_require_concentration_starts_none(tmp_path: Path) -> None:
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, cast(state, BOLT, 1))
    assert not after.combatant("mage").concentration.active


# --- p. 105: one spell slot per turn -------------------------------------------------------


def test_only_one_slot_may_be_expended_in_a_turn(tmp_path: Path) -> None:
    """p. 105, and **the document's own example**: "you can't, for example, cast a spell with
    a spell slot using the Magic action and another one using a Bonus Action on the same
    turn."

    So the case has to be built the way p. 105 builds it — one spell on each action — because
    two action-timed spells are already impossible for a reason that has nothing to do with
    slots: the Action is gone. A test that cast twice with the Action would pass against an
    engine modelling p. 105 not at all.
    """
    granted = replace(caster(), actions=ActionBudget(bonus_action_granted=True))
    state = encounter(granted)

    _, after = build(tmp_path).adjudicate(state, cast(state, QUICK, 1))
    assert "mage" in after.slots_expended_this_turn
    assert after.combatant("mage").actions.available(ActionKind.ACTION), (
        "precondition: the Action is untouched, so only p. 105 can refuse the second spell"
    )

    offered = {a.key for a in read(after, "mage").actions}
    assert cast_key(BOLT.rule_id, 1) not in offered, "p. 105 refuses the second slot"
    assert cast_key(SPARK.rule_id, 0) in offered, "a cantrip spends no slot, so p. 105 is silent"


def test_the_turn_advancing_restores_the_slot_allowance(tmp_path: Path) -> None:
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, cast(state, BOLT, 1))
    assert after.advanced_turn().slots_expended_this_turn == frozenset()


def test_casting_spends_the_action_the_casting_time_names(tmp_path: Path) -> None:
    """p. 185: "When you take the Magic action, you cast a spell that has a casting time of
    an action."

    **The first thing an adjudication has ever charged.** `ActionBudget.spend` has been
    complete since the economy landed and had no caller outside `dodging()`, so an attack does
    not cost the Action even now — a gap filed rather than half-fixed here.
    """
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, cast(state, SPARK, 0))

    assert not after.combatant("mage").actions.available(ActionKind.ACTION)
    assert not any(a.key.startswith("cast:") for a in read(after, "mage").actions), (
        "a cantrip costs no slot and still costs the Action, so nothing more is castable"
    )


def test_a_bonus_action_spell_leaves_the_action_alone(tmp_path: Path) -> None:
    """p. 105 gives casting times their own actions, and p. 186 makes a Reaction free of the
    other two. Charging the wrong one would be invisible until a turn ran short."""
    granted = replace(caster(), actions=ActionBudget(bonus_action_granted=True))
    state = encounter(granted)
    _, after = build(tmp_path).adjudicate(state, cast(state, QUICK, 1))

    budget = after.combatant("mage").actions
    assert budget.available(ActionKind.ACTION)
    assert not budget.available(ActionKind.BONUS_ACTION)


def test_the_allowance_is_not_the_obligation_record(tmp_path: Path) -> None:
    """0036 clause 3's lesson, pointed at a resource. Same cardinality, different meaning:
    `discharged` records an obligation met, this records a resource spent."""
    state = encounter()
    _, after = build(tmp_path).adjudicate(state, cast(state, BOLT, 1))
    assert after.discharged == frozenset()


# --- 0038 clause 4: upcasting is enumerated -----------------------------------------------


def test_one_entry_is_offered_per_payable_slot_level() -> None:
    """R18. Not "you may cast bolt" but "at level 1 or 2" — the level is picked from a menu
    the engine computed rather than supplied as a number it has to trust."""
    offered = {a.key for a in read(encounter(), "mage").actions}

    assert cast_key(BOLT.rule_id, 1) in offered
    assert cast_key(BOLT.rule_id, 2) in offered, "p. 104: a slot of the spell's level or higher"
    assert cast_key(HOLD.rule_id, 1) not in offered, "a level 2 spell does not fit a level 1 slot"
    assert cast_key(HOLD.rule_id, 2) in offered


def test_a_cantrip_is_offered_once_with_no_slot() -> None:
    offered = [
        a for a in read(encounter(), "mage").actions if a.key.startswith("cast:fixture:spark")
    ]
    assert [a.key for a in offered] == [cast_key(SPARK.rule_id, 0)]
    assert offered[0].detail["slot_level"] == 0


def test_a_caster_with_no_slots_left_is_offered_only_cantrips() -> None:
    spent = replace(caster(), slots=SpellSlots(total={1: 1}, spent={1: 1}))
    offered = {a.key for a in read(encounter(spent), "mage").actions}
    assert cast_key(SPARK.rule_id, 0) in offered
    assert not any(k.startswith("cast:fixture:bolt") for k in offered)


def test_the_key_round_trips_through_a_rule_id_containing_colons() -> None:
    """Parsed from the right, because `fixture:bolt` is an ordinary id and splitting from the
    left would take `fixture` as the whole of it."""
    assert cast_declared(cast_key("a:b:c", 3)) == ("a:b:c", 3)
    assert cast_declared("attack:boar") is None
    assert cast_declared(None) is None


# --- p. 185: the action casting costs -----------------------------------------------------


def test_nothing_is_offered_once_the_action_is_spent() -> None:
    """p. 185: "When you take the Magic action, you cast a spell that has a casting time of
    an action." No Action left, no action-timed spell."""
    spent = replace(caster(), actions=ActionBudget().spend(ActionKind.ACTION))
    offered = {a.key for a in read(encounter(spent), "mage").actions}
    assert not any(k.startswith(f"cast:{BOLT.rule_id}") for k in offered)
    assert not any(k.startswith(f"cast:{SPARK.rule_id}") for k in offered)


def test_a_bonus_action_spell_needs_a_granted_bonus_action() -> None:
    """p. 177: a Bonus Action exists only if a rule grants one, so a caster without the grant
    is not offered a Bonus Action spell however many slots it has."""
    offered = {a.key for a in read(encounter(), "mage").actions}
    assert not any(k.startswith(f"cast:{QUICK.rule_id}") for k in offered)

    granted = replace(caster(), actions=ActionBudget(bonus_action_granted=True))
    with_grant = {a.key for a in read(encounter(granted), "mage").actions}
    assert cast_key(QUICK.rule_id, 1) in with_grant


def test_an_incapacitated_caster_is_offered_nothing() -> None:
    """p. 184 removes all three actions, so there is nothing to cast with."""
    stunned = replace(caster(), conditions=caster().conditions)
    state = encounter(stunned).with_condition("mage", Condition.STUNNED)
    assert not any(a.key.startswith("cast:") for a in read(state, "mage").actions)


# --- 0038 clause 3: the engine owns the cost ----------------------------------------------


def test_the_registry_wraps_what_it_is_given() -> None:
    """The guard 0038 clause 3 asks for, built as the only documented path rather than as a
    runtime check. A consumer cannot register a bare effects resolver *through here*."""
    registered = spell_resolvers({BOLT: effects_of})
    assert set(registered) == {BOLT.rule_id}
    assert registered[BOLT.rule_id] is not effects_of


def test_a_bare_effects_resolver_would_cast_for_free(tmp_path: Path) -> None:
    """Why the wrapper exists, asserted rather than argued: registered unwrapped, the spell
    works, the ledger records a Ruling, and only the slot count is wrong. That is the failure
    mode `spell_resolvers` makes unreachable through the documented path."""
    state = encounter()
    only_bolt = load_fixture_ruleset(
        "casting-unwrapped", [r for r in RULES if r.id == BOLT.rule_id]
    )
    adjudicator = Adjudicator(
        ruleset=only_bolt,
        resolvers={BOLT.rule_id: effects_of},  # deliberately not wrapped
        fact_types={},
        port=JsonMemoryStore(tmp_path / "memory.json"),
        ledger=Ledger.open(
            tmp_path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 4,
    )
    ruling, after = adjudicator.adjudicate(state, cast(state, BOLT, 1))

    assert ruling.status is Status.RULED, "it looks exactly like a correct casting"
    assert slots_left(after, 1) == 2, "and the slot was never spent"


def test_the_wrapper_refuses_a_level_no_slot_can_pay(tmp_path: Path) -> None:
    state = encounter()
    with pytest.raises(ValueError, match="cannot pay"):
        spell_resolver(HOLD, effects_of)(state=state, declaration=cast(state, HOLD, 1), facts={})


def test_the_wrapper_refuses_a_cantrip_cast_with_a_slot(tmp_path: Path) -> None:
    state = encounter()
    with pytest.raises(ValueError, match="without a spell slot"):
        spell_resolver(SPARK, effects_of)(state=state, declaration=cast(state, SPARK, 1), facts={})


def test_the_wrapper_refuses_a_declaration_that_names_no_cast(tmp_path: Path) -> None:
    state = encounter()
    declaration = Declaration(
        actor_id="mage", intent=Intent(improvised=True, label="waves"), rule_id=BOLT.rule_id
    )
    with pytest.raises(ValueError, match="does not name it"):
        spell_resolver(BOLT, effects_of)(state=state, declaration=declaration, facts={})


def test_the_ruleset_decides_only_what_the_spell_does(tmp_path: Path) -> None:
    """The boundary, from the other side: the wrapper passes the inner proposal's test,
    citations and bounds through untouched."""
    state = encounter()
    ruling, _ = build(tmp_path).adjudicate(state, cast(state, BOLT, 1))
    assert ruling.result is not None
    assert ruling.result.target == 10, "the ruleset's test, unmodified"
    assert "fixture:spell" in ruling.citations


# --- R32: what the engine does not check --------------------------------------------------


def test_the_unchecked_requirements_are_disclosed() -> None:
    """R32. An offer means castable *as far as this engine can tell*. Components and armour
    training are not checked, and a caller reading a silent pass as the rule being satisfied
    is the confusion the disclosure exists to prevent."""
    module = (
        Path(__file__).resolve().parents[1] / "src" / "srd_rules_engine" / "core" / "casting.py"
    ).read_text()

    assert "What this does not check, and cannot" in module
    for issue in ("#245", "#246", "#247", "#250"):
        assert issue in module, f"the disclosure no longer points at {issue}"
