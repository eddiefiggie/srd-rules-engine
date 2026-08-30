"""p. 105's longer casting times, and the slot that is not spent (#250, 0065).

> While you cast a spell with a casting time of 1 minute or more, you must take the Magic
> action on each of your turns, and you must maintain Concentration while you do so. **If your
> Concentration is broken, the spell fails, but you don't expend a spell slot.** To cast the
> spell again, you must start over.

The refund clause is the interesting half, and it is not a refund: the slot is spent when the
casting **completes**, so there is nothing to give back. An implementation that expended up
front and refunded would be inventing a transaction the document does not describe.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Combatant,
    D20Test,
    Declaration,
    EffectKind,
    EncounterState,
    Intent,
    Ledger,
    Proposal,
    Rule,
    RuleProvenance,
    Status,
    TestKind,
    cast_key,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.actions import ActionBudget, ActionKind
from srd_rules_engine.core.casting import spell_resolver
from srd_rules_engine.core.read_surface import cast_declared, continue_cast_key
from srd_rules_engine.core.spellcasting import (
    TURNS_PER_MINUTE,
    CastingTime,
    LongCast,
    Spell,
    SpellSlots,
    turns_to_cast,
)
from srd_rules_engine.memory.store import JsonMemoryStore

RITE = Spell(
    rule_id="fixture:rite",
    level=2,
    casting_time=CastingTime.MINUTES,
    casting_minutes=1,
    requires_concentration=True,
)
QUICK = Spell(rule_id="fixture:spark", level=1, casting_time=CastingTime.ACTION)

RULES = tuple(
    Rule(
        id=spell.rule_id,
        summary=f"An invented spell of level {spell.level}.",
        provenance=RuleProvenance.FIXTURE,
        rationale=(
            "The mechanism is p. 105's and the spell is not. No SRD spell description ships "
            "in this repository, so every spell exercised here is declared fixture."
        ),
    )
    for spell in (RITE, QUICK)
)
RULESET = load_fixture_ruleset("long-casting", RULES)


def no_effects(*, state, declaration, facts):  # type: ignore[no-untyped-def]
    """What a ruleset brings: the spell's own effect, and nothing about what it cost.

    A flat check, so a test about the *casting* is not also a test about what the spell does.
    """
    return Proposal(
        test=D20Test(kind=TestKind.CHECK, target=10, target_basis="invented flat difficulty 10"),
        citations=("fixture:rite",),
    )


def caster(**overrides: object) -> Combatant:
    fields: dict[str, object] = {
        "id": "mage",
        "name": "Mage",
        "hit_points": 30,
        "max_hit_points": 30,
        "armour_class": 12,
        "abilities": {"int": 16, "con": 12, "dex": 12, "str": 10},
        "proficiency_bonus": 2,
        "is_player_character": True,
        "slots": SpellSlots(total={1: 2, 2: 2}),
        "spells": (RITE, QUICK),
        "prepared": frozenset({RITE.rule_id, QUICK.rule_id}),
    }
    fields.update(overrides)
    return Combatant(**fields)  # type: ignore[arg-type]


def encounter(actor: Combatant | None = None) -> EncounterState:
    return EncounterState.new([actor or caster()]).with_initiative({"mage": 20})


def build(path: Path) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers={
            RITE.rule_id: spell_resolver(RITE, no_effects),
            QUICK.rule_id: spell_resolver(QUICK, no_effects),
        },
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 4,
    )


def declare(state: EncounterState, key: str, rule_id: str) -> Declaration:
    offered = read(state, "mage")
    return Declaration(
        actor_id="mage",
        intent=Intent(action_key=key),
        rule_id=rule_id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def begun(path: Path) -> EncounterState:
    """The state one Magic action into a one-minute casting."""
    state = encounter()
    _, after = build(path).adjudicate(
        state, declare(state, cast_key(RITE.rule_id, 2), RITE.rule_id)
    )
    return after


# --- The representation --------------------------------------------------------------------


def test_a_long_casting_states_its_own_minutes() -> None:
    """p. 105 says "1 minute or more" and leaves each spell to say how many, so one number for
    all of them would be a duration the document does not give."""
    with pytest.raises(ValueError, match="states none"):
        Spell(rule_id="x", level=1, casting_time=CastingTime.MINUTES)
    with pytest.raises(ValueError, match="describes nothing"):
        Spell(rule_id="x", level=1, casting_time=CastingTime.ACTION, casting_minutes=3)


def test_a_minute_is_ten_turns() -> None:
    """0021: a round is exactly six seconds, and a creature takes one turn per round."""
    assert TURNS_PER_MINUTE == 10
    assert turns_to_cast(RITE) == 10
    assert turns_to_cast(replace(RITE, casting_minutes=10)) == 100


def test_a_short_spell_has_no_turn_count() -> None:
    with pytest.raises(ValueError, match="takes no turns of its own"):
        turns_to_cast(QUICK)


# --- Beginning ------------------------------------------------------------------------------


def test_beginning_spends_the_action_and_no_slot(tmp_path: Path) -> None:
    """0065 clause 2, and the clause an implementation gets wrong."""
    state = encounter()
    ruling, after = build(tmp_path).adjudicate(
        state, declare(state, cast_key(RITE.rule_id, 2), RITE.rule_id)
    )

    assert ruling.status is Status.RULED
    mage = after.combatant("mage")
    assert mage.slots is not None
    assert mage.slots.remaining(2) == 2, "no slot has left the caster"
    assert not mage.actions.available(ActionKind.ACTION, mage.conditions), "the Action has"
    assert mage.concentration.active
    assert mage.long_cast == LongCast(spell_id=RITE.rule_id, slot_level=2, turns_remaining=10)


def test_a_level_it_could_never_pay_is_refused_at_the_start(tmp_path: Path) -> None:
    """Checked when the casting starts even though it is not spent until the end: a caster who
    could never pay has nothing to spend ten turns on."""
    broke = caster(slots=SpellSlots(total={1: 1}))
    state = encounter(broke)
    with pytest.raises(ValueError, match="cannot pay"):
        spell_resolver(RITE, no_effects)(
            state=state,
            declaration=Declaration(
                actor_id="mage",
                intent=Intent(action_key=cast_key(RITE.rule_id, 2)),
                rule_id=RITE.rule_id,
            ),
            facts={},
        )


# --- Continuing -----------------------------------------------------------------------------


def ready_to_continue(path: Path) -> EncounterState:
    """A caster one Magic action into the casting, with a fresh turn's Action in hand."""
    fresh = replace(begun(path).combatant("mage"), actions=ActionBudget())
    return EncounterState.new([fresh]).with_initiative({"mage": 20})


def test_the_menu_offers_the_continuation(tmp_path: Path) -> None:
    """p. 105 owes the Magic action on **each** turn, so the menu has to say so — a rule the
    caller cannot see is a rule the caller skips."""
    offered = {a.key: a for a in read(ready_to_continue(tmp_path), "mage").actions}
    key = continue_cast_key(RITE.rule_id)
    assert key in offered
    assert offered[key].detail["turns_remaining"] == 10
    assert offered[key].detail["finishes_now"] is False


def test_no_new_casting_is_offered_while_one_is_in_progress(tmp_path: Path) -> None:
    """p. 105: "to cast the spell again, you must start over" — so beginning a second casting
    would abandon the first, and the menu does not quietly offer one."""
    keys = {a.key for a in read(ready_to_continue(tmp_path), "mage").actions}
    assert not any(cast_declared(k) for k in keys)


def test_a_caster_with_no_action_left_is_offered_no_casting(tmp_path: Path) -> None:
    """The continuation costs the Action like any other Magic action, so a turn that has
    spent one owes p. 105 nothing it can pay."""
    mid = begun(tmp_path)
    keys = {a.key for a in read(mid, "mage").actions}
    assert continue_cast_key(RITE.rule_id) not in keys


def test_each_turn_costs_the_action_and_still_no_slot(tmp_path: Path) -> None:
    ready = ready_to_continue(tmp_path)
    ruling, after = build(tmp_path / "b").adjudicate(
        ready, declare(ready, continue_cast_key(RITE.rule_id), RITE.rule_id)
    )
    mage = after.combatant("mage")
    assert ruling.status is Status.RULED
    assert mage.slots is not None and mage.slots.remaining(2) == 2, "still nothing spent"
    assert mage.long_cast is not None and mage.long_cast.turns_remaining == 9
    assert not any(e.kind is EffectKind.SPELL_SLOT_EXPENDED for e in ruling.effects)


def test_continuing_a_casting_that_never_began_is_refused() -> None:
    """R1 lives in the resolver, not the menu: a caller reaching adjudication directly gets
    the same answer the read surface would have given by not offering the key."""
    with pytest.raises(ValueError, match="not part-way through"):
        spell_resolver(RITE, no_effects)(
            state=encounter(),
            declaration=Declaration(
                actor_id="mage",
                intent=Intent(action_key=continue_cast_key(RITE.rule_id)),
                rule_id=RITE.rule_id,
            ),
            facts={},
        )


def test_continuing_a_different_spell_is_refused(tmp_path: Path) -> None:
    """p. 105: one casting at a time, and starting over is starting over."""
    state = begun(tmp_path)
    with pytest.raises(ValueError, match="start over"):
        spell_resolver(QUICK, no_effects)(
            state=state,
            declaration=Declaration(
                actor_id="mage",
                intent=Intent(action_key=continue_cast_key(QUICK.rule_id)),
                rule_id=QUICK.rule_id,
            ),
            facts={},
        )


# --- Completing, and failing --------------------------------------------------------------


def at_the_last_turn(path: Path) -> EncounterState:
    state = begun(path)
    mage = state.combatant("mage")
    assert mage.long_cast is not None
    return EncounterState.new(
        [
            replace(
                mage, actions=ActionBudget(), long_cast=replace(mage.long_cast, turns_remaining=1)
            )
        ]
    ).with_initiative({"mage": 20})


def test_the_last_turn_spends_the_slot_and_resolves_the_spell(tmp_path: Path) -> None:
    """The slot leaves the caster **here**, ten turns after the casting began."""
    ready = at_the_last_turn(tmp_path)
    ruling, after = build(tmp_path / "c").adjudicate(
        ready, declare(ready, continue_cast_key(RITE.rule_id), RITE.rule_id)
    )

    assert ruling.status is Status.RULED
    mage = after.combatant("mage")
    assert mage.slots is not None and mage.slots.remaining(2) == 1, "now it is spent"
    assert mage.long_cast is None, "and the casting is over"
    assert any(e.kind is EffectKind.SPELL_SLOT_EXPENDED for e in ruling.effects)


def test_a_broken_concentration_refunds_nothing_because_nothing_was_spent(tmp_path: Path) -> None:
    """p. 105's clause, and the reason the ordinary order could not be used.

    The caster loses Concentration part-way through. No slot was expended, so none comes back —
    and the slot count is the same as it was before the casting started.
    """
    state = begun(tmp_path)
    before = state.combatant("mage").slots
    assert before is not None and before.remaining(2) == 2

    broken = state.with_concentration_ended("mage")
    assert not broken.combatant("mage").concentration.active
    after = broken.with_long_cast_abandoned("mage")

    mage = after.combatant("mage")
    assert mage.long_cast is None
    assert mage.slots is not None and mage.slots.remaining(2) == 2, "unchanged, not refunded"


def test_continuing_without_concentration_is_refused(tmp_path: Path) -> None:
    """The casting has already failed; p. 105 does not let it limp on."""
    state = begun(tmp_path).with_concentration_ended("mage")
    with pytest.raises(ValueError, match="no longer concentrating"):
        spell_resolver(RITE, no_effects)(
            state=state,
            declaration=Declaration(
                actor_id="mage",
                intent=Intent(action_key=continue_cast_key(RITE.rule_id)),
                rule_id=RITE.rule_id,
            ),
            facts={},
        )


def test_concentration_is_not_restarted_on_each_turn(tmp_path: Path) -> None:
    """It began with the casting. p. 179's replacement rule would otherwise end and restart it
    every turn, which is a mechanic the document does not describe."""
    ready = ready_to_continue(tmp_path)
    ruling, _ = build(tmp_path / "d").adjudicate(
        ready, declare(ready, continue_cast_key(RITE.rule_id), RITE.rule_id)
    )
    assert not any(e.kind is EffectKind.CONCENTRATION_BEGUN for e in ruling.effects)


def test_a_casting_in_progress_owes_at_least_one_more_action() -> None:
    """A casting with none owing has finished, and a finished casting is not in progress."""
    with pytest.raises(ValueError, match="at least one more"):
        LongCast(spell_id="x", slot_level=1, turns_remaining=0)
