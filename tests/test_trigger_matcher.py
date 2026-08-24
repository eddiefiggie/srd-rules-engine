"""The challenge mechanism, and the absence that makes its central prohibition hold.

R6 forbids matching on the declaration's free-text label. The way that is enforced is not
a rule in a docstring — it is that `MatchContext` **has no field for one**. The first test
here asserts the shape directly, because the guarantee is about what the matcher *can*
see, not about what today's implementation happens to do.

Everything else follows from rows being conjunctions and there being no disjunction: an
alternative is a second row, so each stays separately citable when it fires and separately
narrowable when it fires wrongly.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from pathlib import Path

import pytest

from srd_rules_engine.core.adjudicate import (
    Adjudicator,
    Declaration,
    Intent,
    Proposal,
    Status,
    project,
)
from srd_rules_engine.core.d20 import D20Test, TestKind
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.ledger_reader import read_ledger
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.core.read_surface import END_TURN, read
from srd_rules_engine.core.rules import Rule, RuleProvenance, load_fixture_ruleset
from srd_rules_engine.core.state import Combatant, EncounterState
from srd_rules_engine.core.triggers import (
    Catalogue,
    Grounding,
    MatchCondition,
    MatchContext,
    Operator,
    Trigger,
    TriggerError,
    challenge_text,
)
from srd_rules_engine.memory.store import JsonMemoryStore

# --- Invented fixture rows. Nothing here cites a real SRD section. -----------------

SLICK = Trigger(
    id="fixture-slick-surface",
    grounding=Grounding.AUTHORED,
    when=(MatchCondition(field="surface_is_slick", operator=Operator.EQUALS, value=True),),
    message="a slick surface is a stated hazard; a check is warranted",
    rationale="Invented hazard, standing in for the SRD's stated-hazard family.",
)
UNSTEADY = Trigger(
    id="fixture-unsteady",
    grounding=Grounding.AUTHORED,
    when=(MatchCondition(field="actor_hit_points", operator=Operator.IN, value=(1, 2, 3)),),
    message="an actor this close to falling should be tested",
    rationale="Invented state-only row, so an improvised intent can still collide.",
)
ENDING_TURN = Trigger(
    id="fixture-ending-turn-in-combat",
    grounding=Grounding.AUTHORED,
    when=(
        MatchCondition(field="action_key", operator=Operator.EQUALS, value=END_TURN),
        MatchCondition(field="in_combat", operator=Operator.EQUALS, value=True),
    ),
    message="ending a turn mid-combat is invented as testable, for the conjunction case",
    rationale="Invented two-condition row, so the conjunction can be exercised.",
)

CATALOGUE = Catalogue(version=7, triggers=(ENDING_TURN, SLICK, UNSTEADY))

PLAIN = Rule(
    id="plain-effort",
    summary="An invented check.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Gives a resubmitted declaration something to name.",
)
RULESET = load_fixture_ruleset("triggers", [PLAIN])


def context(**overrides: object) -> MatchContext:
    fields: dict[str, object] = {
        "actor_id": "pc",
        "action_key": END_TURN,
        "improvised": False,
        "situation": {"in_combat": True, "actor_hit_points": 20},
    }
    fields.update(overrides)
    return MatchContext(**fields)  # type: ignore[arg-type]


# --- The absence that makes R6 hold -------------------------------------------------


def test_the_projection_has_no_field_for_the_free_text_label() -> None:
    """The guarantee is about what the matcher can see, not what it currently reads.

    Adding a label field here would put R6's prohibition back in the hands of whoever
    writes the next matcher, and the failure would be silent: a catalogue that reads
    prose behaves *better* on the cases anyone would test.
    """
    fields = set(MatchContext.__dataclass_fields__)
    assert fields == {"actor_id", "action_key", "improvised", "situation"}
    assert "label" not in fields
    assert not any("label" in name for name in fields)


def test_a_declaration_with_a_label_projects_without_it() -> None:
    state = encounter()
    declaration = Declaration(
        actor_id="pc",
        intent=Intent(improvised=True, label="I edge along the ledge, whistling"),
        no_test_reason="it seemed safe enough",
    )
    projected = project(declaration, state, {})
    assert "whistling" not in repr(projected)
    assert projected.improvised is True
    assert projected.action_key is None


# --- Rows are conjunctions; an "or" is a second row --------------------------------


def test_a_row_fires_when_every_condition_holds() -> None:
    assert CATALOGUE.matching(context()) == (ENDING_TURN,)


def test_a_row_with_one_unsatisfied_condition_does_not_fire() -> None:
    """Conjunction, so a partially satisfied row is not partially fired."""
    assert ENDING_TURN not in CATALOGUE.matching(context(situation={"in_combat": False}))


def test_two_rows_matching_the_same_declaration_are_both_reported_in_id_order() -> None:
    fired = CATALOGUE.matching(
        context(situation={"in_combat": True, "surface_is_slick": True, "actor_hit_points": 2})
    )
    assert [t.id for t in fired] == sorted(t.id for t in fired)
    assert {t.id for t in fired} == {SLICK.id, UNSTEADY.id, ENDING_TURN.id}


def test_the_catalogue_has_no_disjunctive_operator() -> None:
    """An alternative is a second row, so each stays separately narrowable."""
    assert {str(op) for op in Operator} == {"equals", "in", "present", "absent"}


# --- The operators -------------------------------------------------------------------


def test_equals_compares_the_projected_value() -> None:
    row = Trigger(
        id="t",
        grounding=Grounding.AUTHORED,
        when=(MatchCondition(field="round", operator=Operator.EQUALS, value=3),),
        message="m",
        rationale="r",
    )
    assert row.fires(context(situation={"round": 3}))
    assert not row.fires(context(situation={"round": 2}))


def test_in_compares_against_a_collection() -> None:
    assert UNSTEADY.fires(context(situation={"actor_hit_points": 2}))
    assert not UNSTEADY.fires(context(situation={"actor_hit_points": 9}))


def test_present_and_absent_test_whether_the_field_was_recorded() -> None:
    """A hazard the agent never wrote cannot collide — the guard narrows discretion."""
    present = MatchCondition(field="hazard", operator=Operator.PRESENT)
    absent = MatchCondition(field="hazard", operator=Operator.ABSENT)
    assert present.holds(context(situation={"hazard": "pit"}))
    assert not present.holds(context(situation={}))
    assert absent.holds(context(situation={}))
    assert not absent.holds(context(situation={"hazard": "pit"}))


def test_a_condition_on_an_unrecorded_field_does_not_fire() -> None:
    row = MatchCondition(field="never_recorded", operator=Operator.EQUALS, value=True)
    assert not row.holds(context(situation={}))


def test_an_operator_needing_a_value_is_refused_without_one() -> None:
    with pytest.raises(TriggerError, match="needs a value"):
        MatchCondition(field="round", operator=Operator.EQUALS)


def test_an_operator_taking_no_value_is_refused_with_one() -> None:
    with pytest.raises(TriggerError, match="takes no value"):
        MatchCondition(field="hazard", operator=Operator.PRESENT, value=True)


def test_in_requires_a_collection() -> None:
    with pytest.raises(TriggerError, match="compares against a collection"):
        MatchCondition(field="round", operator=Operator.IN, value=3)


def test_in_may_not_include_none() -> None:
    """An unrecorded field reads as None, so `in (None, ...)` would fire on nothing at all.

    Trigger firing is bounded by the situational state the agent chose to record — a
    hazard nobody wrote must not collide. A collection containing None would quietly
    invert that, and the row would look perfectly ordinary.
    """
    with pytest.raises(TriggerError, match="may not include None"):
        MatchCondition(field="hazard", operator=Operator.IN, value=(None, "pit"))


def test_a_condition_names_its_field() -> None:
    with pytest.raises(TriggerError, match="names the field"):
        MatchCondition(field="", operator=Operator.PRESENT)


# --- Grounding is two-valued ---------------------------------------------------------


def test_a_cited_row_must_name_a_section_and_may_not_carry_a_rationale() -> None:
    with pytest.raises(TriggerError, match="must name the SRD section"):
        Trigger(id="t", grounding=Grounding.CITED, when=(_any(),), message="m")
    with pytest.raises(TriggerError, match="points at a section, not a case"):
        Trigger(
            id="t",
            grounding=Grounding.CITED,
            when=(_any(),),
            message="m",
            reference="Combat",
            rationale="r",
        )


def test_an_authored_row_must_state_why_and_may_not_claim_a_section() -> None:
    with pytest.raises(TriggerError, match="must state why"):
        Trigger(id="t", grounding=Grounding.AUTHORED, when=(_any(),), message="m")
    with pytest.raises(TriggerError, match="claim grounding it does not have"):
        Trigger(
            id="t",
            grounding=Grounding.AUTHORED,
            when=(_any(),),
            message="m",
            rationale="r",
            reference="Combat",
        )


def test_grounding_has_exactly_two_values() -> None:
    """A judgment-assigned middle tier would stop carrying information."""
    assert {str(g) for g in Grounding} == {"cited", "authored"}


def test_a_row_with_no_conditions_is_refused() -> None:
    """It would fire on every declaration, which is over-firing at maximum volume."""
    with pytest.raises(TriggerError, match="fire on every declaration"):
        Trigger(id="t", grounding=Grounding.AUTHORED, when=(), message="m", rationale="r")


def test_a_catalogue_has_one_row_per_id() -> None:
    with pytest.raises(TriggerError, match="appears twice"):
        Catalogue(version=1, triggers=(SLICK, SLICK))


# --- The challenge, end to end ------------------------------------------------------


def combatant(cid: str, hp: int = 20) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=hp,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 16},
        proficiency_bonus=2,
    )


def encounter() -> EncounterState:
    state = EncounterState.new([combatant("pc"), combatant("boar", hp=11)])
    return state.with_initiative({"pc": 18, "boar": 4})


def build(tmp_path: Path, catalogue: Catalogue = CATALOGUE) -> tuple[Adjudicator, Path]:
    ledger_path = tmp_path / "ledger.jsonl"
    ledger = Ledger.open(
        ledger_path, engine_version="t", catalogue_version=catalogue.version, session_id="s"
    )
    return (
        Adjudicator(
            ruleset=RULESET,
            resolvers={"plain-effort": _plain},
            fact_types={},
            port=JsonMemoryStore(tmp_path / "m.json"),
            ledger=ledger,
            catalogue=catalogue,
            seed_source=lambda: 5,
        ),
        ledger_path,
    )


def skip(state: EncounterState, **overrides: object) -> Declaration:
    offered = read(state, "pc")
    fields: dict[str, object] = {
        "actor_id": "pc",
        "intent": Intent(action_key=END_TURN),
        "no_test_reason": "nothing was at stake",
        "alternatives": offered.actions,
        "read_token": offered.token,
    }
    fields.update(overrides)
    return Declaration(**fields)  # type: ignore[arg-type]


def test_a_skip_colliding_with_a_trigger_is_challenged_and_produces_no_outcome(
    tmp_path: Path,
) -> None:
    """Covers AE1 — the silent skip becomes a recorded, reviewable exchange."""
    adjudicator, _ = build(tmp_path)
    state = encounter()
    ruling, unchanged = adjudicator.adjudicate(
        state, skip(state), situation={"surface_is_slick": True}
    )

    assert ruling.status is Status.CHALLENGED
    assert ruling.result is None, "no outcome is produced"
    assert unchanged is state
    assert {t.id for t in ruling.fired} == {SLICK.id, ENDING_TURN.id}


def test_the_challenge_names_each_row_and_its_grounding(tmp_path: Path) -> None:
    adjudicator, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, skip(state), situation={"surface_is_slick": True})

    account = ruling.why()
    assert SLICK.id in account
    assert "authored" in account
    assert SLICK.rationale is not None and SLICK.rationale in account


def test_a_skip_that_collides_with_nothing_is_accepted(tmp_path: Path) -> None:
    adjudicator, _ = build(tmp_path, Catalogue(version=1, triggers=(SLICK,)))
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, skip(state))
    assert ruling.status is Status.NO_TEST


def test_an_improvised_intent_is_matched_on_situational_state_alone(
    tmp_path: Path,
) -> None:
    """The reduced coverage is disclosed, not closed — but a state-only row still fires."""
    adjudicator, _ = build(tmp_path)
    state = encounter().with_damage("pc", 18)
    declaration = Declaration(
        actor_id="pc",
        intent=Intent(improvised=True, label="I try something clever"),
        no_test_reason="it is only a flourish",
    )
    ruling, _ = adjudicator.adjudicate(state, declaration)

    assert ruling.status is Status.CHALLENGED
    assert {t.id for t in ruling.fired} == {UNSTEADY.id}, "matched on hit points alone"


def test_a_declaration_naming_a_test_is_never_challenged(tmp_path: Path) -> None:
    """The catalogue guards skips. A named test goes to validation and adjudication."""
    adjudicator, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(
        state,
        skip(state, no_test_reason=None, rule_id="plain-effort"),
        situation={"surface_is_slick": True},
    )
    assert ruling.status is Status.RULED


# --- What the ledger records ---------------------------------------------------------


def test_a_challenge_is_recorded_as_a_challenge(tmp_path: Path) -> None:
    adjudicator, ledger_path = build(tmp_path)
    state = encounter()
    adjudicator.adjudicate(state, skip(state), situation={"surface_is_slick": True})

    types = [e.type for e in read_ledger(ledger_path).entries]
    assert types == ["session", "declaration", "challenge"]


def test_the_catalogue_version_in_force_is_recorded_on_the_declaration(
    tmp_path: Path,
) -> None:
    """R28 replays against the recorded version, so a grown catalogue never corrupts a ledger."""
    adjudicator, ledger_path = build(tmp_path)
    state = encounter()
    adjudicator.adjudicate(state, skip(state))

    declaration_entry = read_ledger(ledger_path).entries[1]
    assert declaration_entry.type == "declaration"
    assert declaration_entry.payload["catalogue_version"] == 7


def test_the_recorded_challenge_names_the_rows_that_fired(tmp_path: Path) -> None:
    adjudicator, ledger_path = build(tmp_path)
    state = encounter()
    adjudicator.adjudicate(state, skip(state), situation={"surface_is_slick": True})

    fired = read_ledger(ledger_path).entries[-1].payload["fired"]
    assert isinstance(fired, list)
    assert {row["id"] for row in fired} == {SLICK.id, ENDING_TURN.id}
    assert all(row["basis"] for row in fired), "each row records what grounds it"


def test_the_challenge_bounds_permit_no_claim_that_anything_happened(
    tmp_path: Path,
) -> None:
    adjudicator, _ = build(tmp_path)
    state = encounter()
    ruling, _ = adjudicator.adjudicate(state, skip(state), situation={"surface_is_slick": True})
    assert ruling.bounds.may == ()
    assert any("re-declared" in claim for claim in ruling.bounds.may_not)


# --- Helpers -------------------------------------------------------------------------


def _any() -> MatchCondition:
    return MatchCondition(field="in_combat", operator=Operator.PRESENT)


def _plain(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    return Proposal(
        test=D20Test(kind=TestKind.CHECK, target=10, target_basis="invented flat difficulty 10")
    )


def test_challenge_text_reads_as_something_an_agent_can_act_on() -> None:
    text = challenge_text((SLICK,))
    assert SLICK.id in text and SLICK.message in text and "authored" in text


def test_the_catalogue_orders_its_rows_by_id() -> None:
    """Deterministic ordering is what makes replay reproduce the same challenge."""
    shuffled = Catalogue(version=1, triggers=(UNSTEADY, ENDING_TURN, SLICK))
    assert [t.id for t in shuffled.triggers] == sorted(t.id for t in shuffled.triggers)


def test_a_catalogue_version_starts_at_one() -> None:
    with pytest.raises(TriggerError, match="starts at 1"):
        Catalogue(version=0)


def test_a_trigger_is_frozen() -> None:
    with pytest.raises(dataclasses.FrozenInstanceError):
        SLICK.id = "renamed"  # type: ignore[misc]
