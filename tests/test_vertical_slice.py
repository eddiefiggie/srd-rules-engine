"""The milestone's demonstration: one character, one encounter, end to end.

**The assertion is the report, not a sequence of intermediate states.** A slice that passed
because each step was checked in isolation would not have demonstrated the property the
milestone exists to demonstrate — every unit's own tests already do that, and they were all
green while the report was silently mis-flagging an answered challenge.

**What this proves, stated plainly.** A scripted driver asserts exactly what it is told to,
so it cannot produce an unprompted silent skip. These tests show the report **detects** each
defect condition when one is deliberately injected. They do not show that a live agent
**cannot evade** it — that is the contract's primary criterion, it needs a real model, and
it is filed as [#42](https://github.com/eddiefiggie/srd-rules-engine/issues/42). Reading a
green run here as having met the contract's bar is the misreading this milestone most
invites.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest

from fixtures.encounter import (
    ENGINE_VERSION,
    SESSION_ID,
    SliceDriver,
    build_adjudicator,
    claims_no_test,
    crosses_properly,
    needs_nerve,
    opening_state,
    policy_declaration,
    run_encounter,
    with_a_stale_token,
)
from fixtures.ruleset import (
    ATTACK,
    CROSSING,
    LOOSE_GROUND,
    LOOSE_SCREE,
    RULES,
    STEADYING,
    fixture_catalogue,
)
from srd_rules_engine.core import (
    MAX_SAFE_INTEGER,
    EncounterState,
    Fact,
    Flag,
    Provenance,
    ReplayVerdict,
    RuleLoadError,
    Status,
    Writer,
    canonicalize,
    load_ruleset,
    read,
    read_ledger,
    render,
    replay,
    session_report,
)
from srd_rules_engine.loop.drivers import drive
from srd_rules_engine.loop.turn import DeclarationRequest, TurnLoop

FIRM = Provenance(writer=Writer.OUT_OF_BAND, reference="the character's own scouting")


def _declaration_request(state: EncounterState, actor_id: str) -> DeclarationRequest:
    """What the loop would have handed the driver, built outside it.

    Two tests below need a declaration the loop cannot produce, because the loop always
    asks again. Building the request the same way the loop does keeps those declarations
    honest — they carry a real read token over the real offered set.
    """
    return DeclarationRequest(state=state, actor_id=actor_id, offered=read(state, actor_id))


# --- The encounter runs ---------------------------------------------------------------------


def test_a_full_encounter_runs_with_no_model_and_no_network(tmp_path: Path) -> None:
    """R8. The whole fight, from initiative to a combatant at 0, driven by a fixed policy.

    Asserted by construction as well as by outcome: the driver holds no client, no model
    name, and no endpoint, because a reference binding that needed one would couple the
    engine to a model — a declared non-goal — and make every test a model call.
    """
    run = run_encounter(tmp_path / "fight")

    assert run.finished, "a combatant reached 0 hit points"
    assert len(run.outcomes) >= 2, "and both sides acted"
    assert all(o.produced_outcome for o in run.outcomes)

    driver = run.driver
    assert not any(hasattr(driver, name) for name in ("client", "model", "endpoint", "api_key"))


def test_the_report_accounts_for_every_turn_and_flags_nothing(tmp_path: Path) -> None:
    """The milestone's clean baseline. An instrument that cannot read clean means nothing."""
    run = run_encounter(tmp_path / "clean")
    report = session_report(run.ledger)

    assert not report.corrupted
    assert report.engine_version == ENGINE_VERSION
    assert report.catalogue_version == fixture_catalogue().version
    assert report.session_id == SESSION_ID
    assert len(report.turns) == len(run.outcomes), "every declaration slot appears once"
    assert report.flags == ()
    assert report.orphan_narrations == 0

    for turn in report.turns:
        assert turn.status == "ruled"
        assert turn.outcome, "the derivation is on the record"
        assert turn.narration, "and so is the prose it licensed"


def test_no_asserted_outcome_originated_outside_a_ruling(tmp_path: Path) -> None:
    """R26, read off the ledger rather than off the driver's memory.

    Every narration in the session sits in a slot that produced a Ruling. A narration
    anywhere else is prose describing an outcome the engine never reached, which is the
    defect the whole product exists to remove.
    """
    run = run_encounter(tmp_path / "origin")
    report = session_report(run.ledger)

    narrated = [t for t in report.turns if t.narration is not None]
    assert narrated, "the run produced narration at all"
    assert all(t.status == "ruled" for t in narrated)
    assert report.orphan_narrations == 0
    assert not report.flagged(Flag.NARRATION_WITHOUT_RULING)


# --- AE1: the silent skip is refused, and the resubmission is adjudicated --------------------


def test_a_no_test_claim_is_challenged_and_the_resubmission_is_adjudicated(
    tmp_path: Path,
) -> None:
    """AE1, end to end and inside a real encounter rather than against a stub.

    Both attempts appear in the report as **one slot with two attempts** — because that is
    what happened. Reporting them as two turns would flag the challenge as never answered,
    which is the flag saying the opposite of the truth.
    """
    driver = SliceDriver(scripted=[claims_no_test, crosses_properly])
    run = run_encounter(tmp_path / "ae1", driver=driver, situation=LOOSE_SCREE)
    report = session_report(run.ledger)

    first = report.turns[0]
    assert first.attempts == 2, "the refusal was fed back and answered in the same slot"
    assert first.rule_id == CROSSING.id, "the resubmission named a rule"
    assert first.status == "ruled"
    assert not first.flags, "an answered challenge is not an unanswered one"

    challenges = [e for e in read_ledger(run.ledger).entries if e.type == "challenge"]
    assert len(challenges) == 1, "and the challenge itself is on the record"
    fired = challenges[0].payload["fired"]
    assert isinstance(fired, list)
    assert [row["id"] for row in fired] == [LOOSE_GROUND.id]
    assert fired[0]["grounding"] == "authored", "the grounding is disclosed, not implied"


def test_the_challenged_declaration_produced_no_outcome(tmp_path: Path) -> None:
    """R6. A challenge is a refusal to rule, so nothing may be claimed from it."""
    driver = SliceDriver(scripted=[claims_no_test, crosses_properly])
    run = run_encounter(tmp_path / "ae1b", driver=driver, situation=LOOSE_SCREE)

    challenged = run.outcomes[0].refusals[0]
    assert challenged.status is Status.CHALLENGED
    assert challenged.result is None
    assert challenged.effects == ()
    assert any(
        "no outcome was produced" in c or "must be re-declared" in c
        for c in challenged.bounds.may_not
    )


# --- AE3 and AE4, through invented fixture facts ----------------------------------------------


def test_an_absent_fact_blocks_and_is_named_rather_than_assumed(tmp_path: Path) -> None:
    """AE3. The engine says what it is missing instead of filling it in."""
    driver = SliceDriver(scripted=[needs_nerve])
    run = run_encounter(tmp_path / "ae3", driver=driver)

    assert run.outcomes[0].terminal is not None
    assert run.outcomes[0].unresolved == ("nerve",)

    report = session_report(run.ledger)
    flagged = report.flagged(Flag.TERMINATED)
    assert flagged and flagged[0].terminal_reason == "fact-unavailable"
    assert Flag.RULING_WITHOUT_NARRATION not in flagged[0].flags, "there was no Ruling to narrate"


def test_a_supplied_fact_unblocks_the_same_declaration(tmp_path: Path) -> None:
    """A block is a suspension, not a refusal: the declaration resumes rather than being
    re-made, so the slot shows one attempt and not two."""
    driver = SliceDriver(scripted=[needs_nerve], facts=[Fact("nerve", "pc", True, FIRM)])
    run = run_encounter(tmp_path / "ae3b", driver=driver)

    report = session_report(run.ledger)
    assert report.turns[0].status == "ruled"
    assert report.turns[0].attempts == 1, "the agent was not asked again"
    assert report.turns[0].rule_id == STEADYING.id


def test_a_resolved_fact_moves_the_target_number_and_is_cited_with_its_provenance(
    tmp_path: Path,
) -> None:
    """AE4. The same declaration under two footings resolves against two difficulties, and
    each Ruling says which fact value set the number and where the value came from."""
    firm = SliceDriver(scripted=[crosses_properly], known=[Fact("footing", "pc", "firm", FIRM)])
    run_firm = run_encounter(tmp_path / "ae4-firm", driver=firm)
    firm_ruling = run_firm.outcomes[0].ruling

    # No fact supplied: the type's engine-chosen default applies, and says so.
    run_default = run_encounter(
        tmp_path / "ae4-default", driver=SliceDriver(scripted=[crosses_properly])
    )
    default_ruling = run_default.outcomes[0].ruling

    assert firm_ruling is not None and firm_ruling.result is not None
    assert default_ruling is not None and default_ruling.result is not None
    assert firm_ruling.result.target != default_ruling.result.target, "the fact moved it"

    assert "footing='firm'" in firm_ruling.result.target_basis
    assert FIRM.reference in firm_ruling.result.target_basis, "with the provenance named"
    assert "fact:footing=firm" in firm_ruling.citations

    assert "engine-chosen" in default_ruling.result.target_basis
    assert default_ruling.facts[0].defaulted is not None, "a default is disclosed as one"


# --- AE5: replay ---------------------------------------------------------------------------


def test_every_ruling_in_the_encounter_replays_to_an_identical_outcome(
    tmp_path: Path,
) -> None:
    """AE5, over a whole session rather than a single entry."""
    run = run_encounter(tmp_path / "ae5")
    replays = replay(read_ledger(run.ledger), engine_version=ENGINE_VERSION)

    assert len(replays) == len(run.outcomes)
    assert all(r.verdict is ReplayVerdict.IDENTICAL for r in replays)
    assert not any(r.is_integrity_failure for r in replays)


def test_the_same_seed_reruns_the_encounter_to_a_byte_identical_ledger(
    tmp_path: Path,
) -> None:
    """Chain digests included, which is the part a per-entry replay cannot check.

    Two runs agreeing entry by entry could still differ in what was written, in what order,
    or in what each entry committed to. Byte identity is the only form of this claim that
    covers the whole record rather than the parts somebody thought to compare.
    """
    first = run_encounter(tmp_path / "rerun-a")
    second = run_encounter(tmp_path / "rerun-b")

    assert first.ledger.read_bytes() == second.ledger.read_bytes()
    digest = hashlib.sha256(first.ledger.read_bytes()).hexdigest()
    assert digest == hashlib.sha256(second.ledger.read_bytes()).hexdigest()

    sums = [e.sum for e in read_ledger(first.ledger).entries]
    assert sums == [e.sum for e in read_ledger(second.ledger).entries]
    assert len(set(sums)) == len(sums), "and each entry commits to a distinct chain state"


def test_a_different_seed_produces_a_different_encounter(tmp_path: Path) -> None:
    """Otherwise byte-identity would be proving the harness ignores the seed."""
    first = run_encounter(tmp_path / "seed-a", seed=11)
    second = run_encounter(tmp_path / "seed-b", seed=2)
    assert first.ledger.read_bytes() != second.ledger.read_bytes()


# --- The report detects each injected defect ---------------------------------------------------


def test_a_withheld_narration_is_reported_as_a_ruling_with_no_narration(
    tmp_path: Path,
) -> None:
    run = run_encounter(tmp_path / "no-narration", driver=SliceDriver(narrate=False))
    report = session_report(run.ledger)

    flagged = report.flagged(Flag.RULING_WITHOUT_NARRATION)
    assert flagged, "the gap is reported, not tolerated"
    assert flagged[0].status == "ruled"
    assert flagged[0].narration is None


def test_a_challenge_left_un_resubmitted_is_reported_as_never_re_adjudicated(
    tmp_path: Path,
) -> None:
    """The session stopped on a challenge, and the report says so.

    This one cannot be produced through the turn loop, and that is worth stating rather
    than working around: the loop always asks again after a refusal, so an unanswered
    challenge inside a driven session always ends as a *termination* instead — which the
    next test asserts. The condition R30 names arises when the session itself ends on a
    challenge: the process exits, or the person walks away. So the injection is a direct
    adjudication with nothing after it, which is exactly that.
    """
    adjudicator = build_adjudicator(tmp_path / "unanswered", seed=11)
    state = opening_state(seed=11)
    request = _declaration_request(state, "pc")
    ruling, _ = adjudicator.adjudicate(state, claims_no_test(request), situation=LOOSE_SCREE)
    assert ruling.status is Status.CHALLENGED

    report = session_report(tmp_path / "unanswered" / "ledger.jsonl")
    flagged = report.flagged(Flag.CHALLENGE_NEVER_READJUDICATED)
    assert flagged
    assert flagged[0].status == "challenged"
    assert flagged[0].narration is None
    assert flagged[0].terminal_reason is None, "nothing terminated it — the session just ended"


def test_repeating_a_challenged_claim_terminates_the_slot_instead(tmp_path: Path) -> None:
    """The loop's own answer to the same behaviour, and it is a different finding.

    Two structurally identical refusals terminate at once, ahead of the budget: a repeat
    proves the feedback is not being used. The report names that as a termination with its
    reason, not as a challenge nobody answered — the agent answered, with the same thing.
    """
    driver = SliceDriver(scripted=[claims_no_test, claims_no_test, claims_no_test])
    run = run_encounter(tmp_path / "repeat", driver=driver, situation=LOOSE_SCREE)

    report = session_report(run.ledger)
    flagged = report.flagged(Flag.TERMINATED)
    assert flagged
    assert flagged[0].terminal_reason == "no-progress"
    assert flagged[0].attempts == 2, "it was asked again, and repeated itself"
    assert Flag.RULING_WITHOUT_NARRATION not in flagged[0].flags


def test_a_narration_after_a_challenge_is_reported_as_having_no_ruling(
    tmp_path: Path,
) -> None:
    """The defect the product exists to remove, showing up inside the product's record.

    A challenge produced no outcome. Prose describing one anyway is exactly the failure the
    engine is meant to make impossible, and the report has to be able to see it.
    """
    adjudicator = build_adjudicator(tmp_path / "orphan", seed=11)
    state = opening_state(seed=11)
    ruling, _ = adjudicator.adjudicate(
        state, claims_no_test(_declaration_request(state, "pc")), situation=LOOSE_SCREE
    )
    assert ruling.status is Status.CHALLENGED

    adjudicator.record_narration(ruling, "the character strolls across, sure-footed")

    report = session_report(tmp_path / "orphan" / "ledger.jsonl")
    assert report.orphan_narrations == 1
    assert report.flagged(Flag.NARRATION_WITHOUT_RULING)


def test_a_stale_read_token_is_reported_with_a_verdict_other_than_fresh(
    tmp_path: Path,
) -> None:
    """R18/R19. The alternatives are the agent's claim about what it was offered, and an
    unverified claim occupies the place where evidence should be."""
    driver = SliceDriver(scripted=[with_a_stale_token])
    run = run_encounter(tmp_path / "stale", driver=driver)
    report = session_report(run.ledger)

    flagged = report.flagged(Flag.ALTERNATIVES_NOT_FRESH)
    assert flagged
    assert flagged[0].alternatives_verdict != "verified-fresh"


@pytest.mark.parametrize(
    ("label", "flag"),
    [
        ("ruling-without-narration", Flag.RULING_WITHOUT_NARRATION),
        ("challenge-never-re-adjudicated", Flag.CHALLENGE_NEVER_READJUDICATED),
        ("alternatives-not-fresh", Flag.ALTERNATIVES_NOT_FRESH),
        ("terminated", Flag.TERMINATED),
        ("narration-without-ruling", Flag.NARRATION_WITHOUT_RULING),
    ],
)
def test_every_defect_condition_has_a_flag_the_report_can_raise(label: str, flag: Flag) -> None:
    """The milestone's list, asserted as a list. A flag that exists but is never raised by
    any test is a flag nobody has seen work."""
    assert str(flag) == label


def test_the_engine_draws_a_seed_the_record_can_hold(tmp_path: Path) -> None:
    """Found by the slice, and it was in shipped code rather than in the fixture.

    `secrets.randbits(64)` produces a seed with no canonical form roughly all of the time,
    so in production the Ruling could not be written down and nothing escaped the engine.
    Every test before this one used seeds small enough to miss it — which is the shape of
    defect a vertical slice exists to catch, and the reason the slice is not redundant with
    the units it composes.
    """
    from srd_rules_engine.core.adjudicate import SEED_BITS, _system_seed

    assert 2**SEED_BITS - 1 <= MAX_SAFE_INTEGER
    drawn = [_system_seed() for _ in range(200)]
    assert all(0 <= s <= MAX_SAFE_INTEGER for s in drawn)
    assert len(set(drawn)) > 190, "and it is still unpredictable, not a constant"

    for seed in drawn:
        canonicalize({"seed": seed})  # raises if any drawn seed has no canonical form


def test_a_seed_the_record_cannot_hold_is_refused_at_the_seed_source(tmp_path: Path) -> None:
    """Naming the seed source, not the ledger. The seed is never clamped: a quietly altered
    seed reproduces a different roll on replay, so the honest options are as-given or a
    refusal."""
    adjudicator = build_adjudicator(tmp_path / "wide", seed=11)
    object.__setattr__(adjudicator, "_seed_source", lambda: MAX_SAFE_INTEGER + 1)

    state = opening_state(seed=11)
    with pytest.raises(ValueError, match="seed source returned"):
        adjudicator.adjudicate(state, policy_declaration(_declaration_request(state, "pc")))


def test_a_terminated_slot_does_not_swallow_the_next_declaration(tmp_path: Path) -> None:
    """Two turns by the same actor, the first terminated. They are two slots, not one.

    A terminated slot is closed — the loop gave up on it and moved on. Absorbing the next
    declaration as a *retry* of it would report the second turn as never having happened
    and the first as having taken two attempts, so a session would lose a whole turn from
    the count the milestone is read from.
    """
    adjudicator = build_adjudicator(tmp_path / "twice", seed=11)
    loop = TurnLoop(adjudicator=adjudicator)
    state = opening_state(seed=11)

    for _ in range(2):
        outcome = drive(loop.run(state, "pc"), SliceDriver(scripted=[needs_nerve]))
        assert outcome.terminal is not None

    report = session_report(tmp_path / "twice" / "ledger.jsonl")
    assert len(report.turns) == 2, "two declaration slots, one per turn"
    assert all(turn.attempts == 1 for turn in report.turns)
    assert all(turn.terminal_reason == "fact-unavailable" for turn in report.turns)


# --- The fixture ruleset cannot escape ----------------------------------------------------------


def test_the_fixture_ruleset_is_refused_when_loaded_as_a_shipped_ruleset() -> None:
    """KTD2's gate, and it is identity rather than policy: the shipped loader does not
    accept fixture provenance at all, so loosening the fixture loader cannot make an
    unverified entry admissible here."""
    with pytest.raises(RuleLoadError, match="cannot be loaded as SRD-derived"):
        load_ruleset(RULES)


def test_no_fixture_rule_claims_srd_provenance() -> None:
    for rule in RULES:
        assert str(rule.provenance) == "fixture"
        assert rule.verification is None
        assert rule.rationale and "nvented" in rule.rationale, (
            "each fixture rule says on its own record that its numbers came from nowhere"
        )


def test_the_slice_names_no_creature_or_weapon_the_srd_names() -> None:
    """R31/R32, while #3 is open. A plausible name in a fixture is the one most likely to be
    copied out later, and by then nothing distinguishes it from a transcription.

    Only the fixtures are scanned. This file necessarily *contains* the forbidden names —
    it is the list — and scanning itself would make the guard fail on its own definition.
    """
    named = ("longsword", "shortsword", "greataxe", "shortbow", "goblin", "orc", "wolf", "boar")
    fixtures = Path(__file__).parent / "fixtures"
    scanned = sorted(fixtures.glob("*.py"))

    assert len(scanned) == 3, "every fixture module is scanned, not a list that drifts"
    for path in scanned:
        body = path.read_text().lower()
        for name in named:
            # Whole words only: "orc" is a substring of "enforces", and a guard that fires
            # on prose is a guard somebody will disable.
            assert not re.search(rf"\b{name}\b", body), (
                f"{name!r} in {path.name} is an SRD value, not a fixture"
            )


def test_the_catalogue_rows_are_authored_and_say_so() -> None:
    """The catalogue is known-incomplete and project-authored. A row claiming a citation it
    does not have would launder the project's judgment as the document's."""
    for row in fixture_catalogue().triggers:
        assert str(row.grounding) == "authored"
        assert row.reference is None
        assert row.rationale


# --- The rendered report ------------------------------------------------------------------------


def test_the_rendered_report_reads_as_a_session_review(tmp_path: Path) -> None:
    run = run_encounter(tmp_path / "render")
    text = render(session_report(run.ledger))

    assert "SESSION REVIEW" in text
    assert SESSION_ID in text
    assert ENGINE_VERSION in text
    assert "meets or beats" in text or "falls short of" in text
    assert ATTACK.id in text or "attack:" in text


def test_the_policy_never_names_an_action_it_was_not_offered(tmp_path: Path) -> None:
    """So an injected illegal declaration is visible as an injection, not as noise."""
    run = run_encounter(tmp_path / "policy")
    report = session_report(run.ledger)

    for turn, outcome in zip(report.turns, run.outcomes, strict=True):
        offered = {a.key for a in outcome.offered}
        if turn.action_key is not None:
            assert turn.action_key in offered
    assert policy_declaration is not None


def test_the_opening_state_has_initiative_and_a_moved_generation() -> None:
    state = opening_state(seed=11)
    assert state.in_combat
    assert state.round_number == 1
    assert state.generation > 0, "applying initiative is a change, so it moves the generation"
    assert all(c.initiative is not None for c in state.combatants)
