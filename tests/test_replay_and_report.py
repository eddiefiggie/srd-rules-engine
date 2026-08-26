"""Replay (R28) and the session-review report (R30).

These two are the instruments the product is measured with, so the tests are mostly about
whether they *can* report a failure — an instrument that only ever reads clean is worse
than none, because it is trusted.

The seeds are found rather than written down: dice derive from the seed, so a hardcoded
literal would quietly stop meaning what it says the moment the derivation changed.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Catalogue,
    Combatant,
    D20Test,
    Declaration,
    EncounterState,
    Fact,
    FactType,
    Flag,
    Grounding,
    Intent,
    Ledger,
    MatchCondition,
    MemoryPort,
    Operator,
    Proposal,
    Provenance,
    Replay,
    ReplayVerdict,
    Resolution,
    Rule,
    RuleProvenance,
    SessionReport,
    TestKind,
    Trigger,
    ValueKind,
    Weapon,
    Writer,
    attack_key,
    attack_resolver,
    load_fixture_ruleset,
    read,
    read_ledger,
    render,
    replay,
    replay_entry,
    session_report,
)
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.ledger_reader import Entry
from srd_rules_engine.core.obstructions import Obstruction
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import END_TURN
from srd_rules_engine.core.report import REPLAYABLE_FROM
from srd_rules_engine.loop.drivers import HumanCliDriver, drive
from srd_rules_engine.loop.turn import TurnLoop
from srd_rules_engine.memory.store import JsonMemoryStore

ENGINE = "engine-under-test"

STRIKE = Rule(
    id="weapon-attack",
    summary="An attack with a held weapon.",
    provenance=RuleProvenance.FIXTURE,
    rationale="An invented weapon; the mechanism is real and the numbers are fixture.",
)
NEEDY = Rule(
    id="needy",
    summary="An invented check consuming a fact with no honest default.",
    provenance=RuleProvenance.FIXTURE,
    consumes=("omen",),
    rationale="Drives the blocked and fact-unavailable paths.",
)
RULESET = load_fixture_ruleset("replay", [STRIKE, NEEDY])
BLADE = Weapon(name="fixture blade", damage_dice=2, damage_sides=6, ability="str")
OMEN = FactType(name="omen", kind=ValueKind.BOOLEAN)
NOTED = Provenance(writer=Writer.OUT_OF_BAND, reference="notes")

SKIPS = Trigger(
    id="fixture-skips-collide",
    grounding=Grounding.AUTHORED,
    when=(MatchCondition(field="in_combat", operator=Operator.EQUALS, value=True),),
    message="an invented row, so a claimed skip has something to collide with",
    rationale="Drives the challenge path.",
)


def encounter() -> EncounterState:
    return EncounterState.new(
        [
            Combatant(
                id="pc",
                name="Pc",
                hit_points=20,
                max_hit_points=20,
                armour_class=13,
                abilities={"str": 16, "dex": 14},
                proficiency_bonus=2,
            ),
            Combatant(
                id="boar",
                name="Boar",
                hit_points=11,
                max_hit_points=11,
                armour_class=13,
                abilities={"str": 12, "dex": 10},
                proficiency_bonus=2,
            ),
        ]
    ).with_initiative({"pc": 18, "boar": 4})


def _needy(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    return Proposal(
        test=D20Test(kind=TestKind.CHECK, target=10, target_basis="invented flat difficulty 10"),
        may_claim=("that the effort was made",),
    )


def build(
    path: Path,
    *,
    seed: int = 3,
    engine: str = ENGINE,
    port: MemoryPort | None = None,
) -> Adjudicator:
    return Adjudicator(
        ruleset=RULESET,
        resolvers={STRIKE.id: attack_resolver(BLADE), NEEDY.id: _needy},
        fact_types={"omen": OMEN},
        port=port or JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version=engine, catalogue_version=1, session_id="s1"
        ),
        catalogue=Catalogue(version=1, triggers=(SKIPS,)),
        seed_source=lambda: seed,
    )


def strike(state: EncounterState) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(action_key=attack_key("boar")),
        rule_id=STRIKE.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def one_ruling(path: Path, *, seed: int = 3, engine: str = ENGINE) -> Path:
    """A ledger holding a session entry, a declaration, and one ruling."""
    path.mkdir(parents=True, exist_ok=True)
    state = encounter()
    build(path, seed=seed, engine=engine).adjudicate(state, strike(state))
    return path / "ledger.jsonl"


def entries(ledger: Path, entry_type: str) -> list[Entry]:
    return [e for e in read_ledger(ledger).entries if e.type == entry_type]


def rewrite(ledger: Path, seq: int, mutate: Callable[[dict[str, Any]], object]) -> None:
    """Rewrite one entry's payload in place. Breaks the chain — deliberately, in some tests."""
    lines = ledger.read_text().splitlines()
    out = []
    for line in lines:
        entry = json.loads(line)
        if entry.get("seq") == seq:
            mutate(entry["payload"])
        out.append(json.dumps(entry))
    ledger.write_text("\n".join(out) + "\n")


def _flat_ruling(
    path: Path, *, seed: int, has_advantage: bool = False, has_disadvantage: bool = False
) -> Path:
    """A ledger holding one ruling from a flat check declared under `flags`."""
    path.mkdir(parents=True, exist_ok=True)

    def resolver(
        *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
    ) -> Proposal:
        return Proposal(
            test=D20Test(
                kind=TestKind.CHECK,
                target=10,
                target_basis="invented flat difficulty 10",
                has_advantage=has_advantage,
                has_disadvantage=has_disadvantage,
            )
        )

    adjudicator = Adjudicator(
        ruleset=RULESET,
        resolvers={STRIKE.id: attack_resolver(BLADE), NEEDY.id: resolver},
        fact_types={"omen": OMEN},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version=ENGINE, catalogue_version=1, session_id="s1"
        ),
        seed_source=lambda: seed,
    )
    adjudicator.port.put(Fact("omen", "pc", True, NOTED))
    state = encounter()
    offered = read(state, "pc")
    adjudicator.adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=END_TURN),
            rule_id=NEEDY.id,
            alternatives=offered.actions,
            read_token=offered.token,
        ),
    )
    return path / "ledger.jsonl"


# --- Replay (R28, AE5) -------------------------------------------------------------------


def test_a_ruling_entry_replays_to_an_identical_outcome(tmp_path: Path) -> None:
    """AE5, which is the whole of R28's promise."""
    ledger = one_ruling(tmp_path / "a")
    replays = replay(read_ledger(ledger), engine_version=ENGINE)

    assert len(replays) == 1
    assert replays[0].verdict is ReplayVerdict.IDENTICAL
    assert replays[0].reproduced
    assert replays[0].recorded_total == replays[0].replayed_total
    assert replays[0].recorded_succeeded == replays[0].replayed_succeeded


def test_replay_re_derives_the_dice_rather_than_trusting_the_recorded_ones(
    tmp_path: Path,
) -> None:
    """A replay that recomputed from the recorded dice would agree by construction — it
    would restate the arithmetic and never notice a change to the derivation."""
    ledger = one_ruling(tmp_path / "b")
    entry = entries(ledger, "ruling")[0]
    roll = entry.payload["roll"]
    assert isinstance(roll, Mapping)

    tampered = dict(entry.payload)
    tampered["roll"] = {**roll, "dice": [1], "used": 1}
    forged = type(entry)(
        seq=entry.seq,
        type=entry.type,
        v=entry.v,
        prev=entry.prev,
        sum=entry.sum,
        payload=tampered,
        line=entry.line,
        interpretable=True,
    )
    outcome = replay_entry(forged, engine_version=ENGINE, recorded_engine=ENGINE)
    assert outcome.verdict is ReplayVerdict.DIVERGED, (
        "the seed still says what the dice were, so a rewritten die is caught"
    )


def test_replay_cannot_query_the_memory_port() -> None:
    """R28's "without re-querying the port", settled by the signature rather than by care.

    A port lookup here would read *today's* memory into *yesterday's* outcome, and the
    disagreement would surface as a replay that passed — the worst available failure, since
    it is reported as a success.
    """
    import inspect

    from srd_rules_engine.core import report as module

    for name in ("replay", "replay_entry"):
        signature = inspect.signature(getattr(module, name))
        assert "port" not in signature.parameters, f"{name} takes a port"
        assert "MemoryPort" not in str(signature), f"{name} is annotated with a port"

    source = Path(module.__file__).read_text()
    assert "MemoryPort" not in source, "replay has no port type to call, not merely no call"
    assert "resolve_fact" not in source


def test_replay_reproduces_a_ruling_whose_memory_store_no_longer_exists(
    tmp_path: Path,
) -> None:
    """The same guarantee from the outside. The resolved fact values are on the entry, so
    the store the session ran against can be gone entirely and replay is unaffected."""
    path = tmp_path / "c"
    path.mkdir()
    adjudicator = build(path)
    adjudicator.port.put(Fact("omen", "pc", True, NOTED))
    state = encounter()
    offered = read(state, "pc")
    adjudicator.adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=END_TURN),
            rule_id=NEEDY.id,
            alternatives=offered.actions,
            read_token=offered.token,
        ),
    )

    store = path / "memory.json"
    assert store.exists()
    store.unlink()

    replays = replay(read_ledger(path / "ledger.jsonl"), engine_version=ENGINE)
    assert replays and all(r.reproduced for r in replays)


def test_a_differing_engine_version_reconciles_rather_than_accusing(tmp_path: Path) -> None:
    """R28. A rules fix is not corruption, so this is never an integrity verdict."""
    ledger = one_ruling(tmp_path / "d")
    rewrite(ledger, entries(ledger, "ruling")[0].seq, lambda p: p["roll"].update(total=99))

    outcome = replay(read_ledger(ledger), engine_version="a-later-engine")[0]
    assert outcome.verdict is ReplayVerdict.RECONCILIATION
    assert not outcome.is_integrity_failure
    assert outcome.recorded_engine == ENGINE
    assert outcome.replay_engine == "a-later-engine"
    assert outcome.recorded_total == 99
    assert outcome.replayed_total != 99, "and both outcomes are named"
    assert ENGINE in outcome.detail and "a-later-engine" in outcome.detail


def test_the_same_engine_disagreeing_with_itself_is_an_integrity_failure(
    tmp_path: Path,
) -> None:
    """The distinction R28 turns on. Without it, every real regression reads as a rules fix."""
    ledger = one_ruling(tmp_path / "e")
    rewrite(ledger, entries(ledger, "ruling")[0].seq, lambda p: p["roll"].update(total=99))

    outcome = replay(read_ledger(ledger), engine_version=ENGINE)[0]
    assert outcome.verdict is ReplayVerdict.DIVERGED
    assert outcome.is_integrity_failure


def test_a_roll_recording_no_advantage_is_unreplayable_not_assumed_plain(
    tmp_path: Path,
) -> None:
    """The count of dice and which one was used both depend on the advantage declared.

    Replaying a v1 entry as though it had none would roll one die where two were rolled and
    report a mismatch indistinguishable from real drift — so it says it cannot.
    """
    ledger = one_ruling(tmp_path / "f")
    seq = entries(ledger, "ruling")[0].seq
    rewrite(ledger, seq, lambda p: p["roll"].pop("declared_advantage"))

    outcome = replay(read_ledger(ledger), engine_version=ENGINE)[0]
    assert outcome.verdict is ReplayVerdict.UNREPLAYABLE
    assert not outcome.is_integrity_failure
    assert "advantage" in outcome.detail


def test_a_ruling_made_with_advantage_replays_identically(tmp_path: Path) -> None:
    """Two dice, and the used one chosen between them — the case a v1 roll could not record."""
    ledger = _flat_ruling(tmp_path / "g", has_advantage=True, seed=5)
    entry = entries(ledger, "ruling")[0]
    roll = entry.payload["roll"]

    assert isinstance(roll, Mapping)
    assert len(roll["dice"]) == 2, "advantage rolls two"
    assert roll["declared_advantage"] is True
    assert roll["used"] == max(roll["dice"]), "advantage takes the higher"
    assert replay_entry(entry, engine_version=ENGINE, recorded_engine=ENGINE).reproduced


def test_a_rewritten_success_flag_is_caught_even_when_the_total_agrees(
    tmp_path: Path,
) -> None:
    """Success is compared as well as the total. They are derived from each other in a
    sound record, so this only diverges when the record is not sound — which is exactly the
    case replay exists for, and the one where checking the redundant field pays."""
    ledger = one_ruling(tmp_path / "x1")
    seq = entries(ledger, "ruling")[0].seq
    recorded = entries(ledger, "ruling")[0].payload["roll"]
    assert isinstance(recorded, Mapping)
    rewrite(ledger, seq, lambda p: p["roll"].update(succeeded=not p["roll"]["succeeded"]))

    outcome = replay(read_ledger(ledger), engine_version=ENGINE)[0]
    assert outcome.verdict is ReplayVerdict.DIVERGED
    assert outcome.recorded_total == outcome.replayed_total, "the totals still agree"
    assert outcome.recorded_succeeded != outcome.replayed_succeeded


def test_a_ruling_made_with_disadvantage_replays_identically(tmp_path: Path) -> None:
    """The mirror of advantage, and not the same code path: one takes the higher die and
    one the lower, so a replay that reconstructed either flag as the other would agree on
    the count of dice and disagree on which was used."""
    path = tmp_path / "x2"
    ledger = _flat_ruling(path, has_disadvantage=True, seed=5)

    entry = entries(ledger, "ruling")[0]
    roll = entry.payload["roll"]
    assert isinstance(roll, Mapping)
    assert len(roll["dice"]) == 2 and roll["declared_disadvantage"] is True
    assert roll["used"] == min(roll["dice"]), "disadvantage takes the lower"
    assert replay_entry(entry, engine_version=ENGINE, recorded_engine=ENGINE).reproduced


def test_the_ruling_payload_names_a_schema_version_and_a_reader_floor_separately(
    tmp_path: Path,
) -> None:
    """Two numbers on two number lines (#106, decision 0022).

    `v` is the payload's **schema** version and moves whenever its shape does. `compat` is
    the lowest **reader** that can read it, and moves only when this repository's reading
    surface changes such that an older one would get the payload wrong. Deriving the second
    from the first is what made every ruling entry in every ledger report as uninterpretable
    the moment `RULING_VERSION` first left 1.

    This test used to assert `compat >= REPLAYABLE_FROM`, which is that derivation written
    down as an expectation. The protection it was reaching for — that replay refuses a
    payload whose roll predates `declared_advantage` rather than assuming it away — is
    structural, and `test_a_roll_recording_no_advantage_is_unreplayable_not_assumed_plain`
    covers it directly by removing the field and checking the refusal.
    """
    from srd_rules_engine.core.ledger import COMPAT
    from srd_rules_engine.core.ledger_reader import READER_VERSION

    ledger = one_ruling(tmp_path / "x3")
    entry = entries(ledger, "ruling")[0]

    roll = entry.payload["roll"]
    assert isinstance(roll, Mapping) and "declared_advantage" in roll
    assert entry.v >= REPLAYABLE_FROM, "the schema version moved with the schema"
    floor = entry.payload[COMPAT]
    assert isinstance(floor, int) and floor <= READER_VERSION, (
        "and the floor names a reader that exists"
    )
    assert entry.interpretable, "which is the reader now reading it"


def test_a_non_ruling_entry_is_unreplayable_rather_than_silently_skipped() -> None:
    """A narration has no roll. Saying so beats returning nothing, which reads as a pass."""
    from srd_rules_engine.core.ledger_reader import Entry

    narration = Entry(
        seq=4, type="narration", v=1, prev=None, sum="x", payload={}, line=5, interpretable=True
    )
    outcome = replay_entry(narration, engine_version=ENGINE, recorded_engine=ENGINE)
    assert outcome.verdict is ReplayVerdict.UNREPLAYABLE
    assert "narration" in outcome.detail


def test_each_ruling_replays_against_the_engine_version_governing_it(tmp_path: Path) -> None:
    """A ledger reopened under a new engine carries a second session entry, so the version
    in force is the nearest preceding one — never the file's first."""
    path = tmp_path / "h"
    ledger = one_ruling(path, engine="engine-one")
    state = encounter()
    build(path, engine="engine-two").adjudicate(state, strike(state))

    replays = replay(read_ledger(ledger), engine_version="engine-two")
    assert [r.recorded_engine for r in replays] == ["engine-one", "engine-two"]
    assert replays[0].verdict is ReplayVerdict.RECONCILIATION or replays[0].reproduced
    assert replays[1].reproduced


# --- Integrity comes first (R30) ----------------------------------------------------------


def test_a_broken_chain_is_reported_as_corrupted_rather_than_summarised(
    tmp_path: Path,
) -> None:
    """The most dangerous artifact available here is a tidy per-turn table computed over
    entries that do not chain, because it reads exactly like a clean session."""
    ledger = one_ruling(tmp_path / "i")
    rewrite(ledger, entries(ledger, "ruling")[0].seq, lambda p: p.update(actor="somebody-else"))

    report = session_report(ledger)
    assert report.corrupted
    assert report.turns == (), "nothing is summarised from a ledger that does not verify"
    assert report.findings


def test_a_corrupted_report_renders_its_findings_and_no_turn_table(tmp_path: Path) -> None:
    ledger = one_ruling(tmp_path / "j")
    rewrite(ledger, entries(ledger, "ruling")[0].seq, lambda p: p.update(actor="somebody-else"))

    text = render(session_report(ledger))
    assert "CORRUPTED" in text
    assert "seq" not in text.lower().replace("sequence", "")


def test_a_truncated_tail_is_corruption_too(tmp_path: Path) -> None:
    ledger = one_ruling(tmp_path / "k")
    ledger.write_text(ledger.read_text()[:-12])
    assert session_report(ledger).corrupted


# --- The report (R30) ---------------------------------------------------------------------


def loop_for(path: Path, *, seed: int = 3, budget: int | None = 3) -> TurnLoop:
    path.mkdir(parents=True, exist_ok=True)
    return TurnLoop(adjudicator=build(path, seed=seed), budget=budget)


class Terminal:
    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.shown: list[str] = []

    def ask(self, prompt: str) -> str:
        self.shown.append(prompt)
        return self.answers.pop(0) if self.answers else ""

    def show(self, line: str) -> None:
        self.shown.append(line)


def test_the_report_names_the_engine_and_catalogue_versions_the_session_ran_under(
    tmp_path: Path,
) -> None:
    """R30 requires both by name. A report that cannot say which rules were in force
    cannot settle the argument it exists to settle."""
    report = session_report(one_ruling(tmp_path / "l"))
    assert report.engine_version == ENGINE
    assert report.catalogue_version == 1
    assert report.session_id == "s1"
    assert ENGINE in render(report)


def test_the_report_lists_the_declaration_the_alternatives_the_ruling_and_the_narration(
    tmp_path: Path,
) -> None:
    path = tmp_path / "m"
    terminal = Terminal([attack_key("boar"), STRIKE.id, "The blade lands."])
    drive(
        loop_for(path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )

    report = session_report(path / "ledger.jsonl")
    assert not report.corrupted
    assert len(report.turns) == 1

    turn = report.turns[0]
    assert turn.actor == "pc"
    assert turn.action_key == attack_key("boar")
    assert turn.rule_id == STRIKE.id
    assert turn.alternatives, "what was offered is on the record, not only what was chosen"
    assert turn.status == "ruled"
    assert turn.outcome and "meets or beats" in turn.outcome
    assert turn.narration == "The blade lands."
    assert turn.flags == ()


def test_a_ruling_with_no_narration_is_flagged(tmp_path: Path) -> None:
    """R29 gates the next declaration on it, so an unnarrated Ruling is a stalled turn."""
    path = tmp_path / "n"
    terminal = Terminal([attack_key("boar"), STRIKE.id, "   "])
    outcome = drive(
        loop_for(path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    assert outcome.missing_narration

    report = session_report(path / "ledger.jsonl")
    assert [t.flags for t in report.turns] == [(Flag.RULING_WITHOUT_NARRATION,)]


def test_a_narration_with_no_ruling_is_flagged(tmp_path: Path) -> None:
    """Prose arriving where nothing was adjudicated is the original defect, in the ledger.

    A challenged declaration produced no Ruling, so a narration following it is describing
    an outcome the engine never reached — which is exactly the failure the product exists
    to remove, showing up inside the product's own record.
    """
    path = tmp_path / "o"
    path.mkdir()
    adjudicator = build(path)
    state = encounter()
    offered = read(state, "pc")
    challenged, _ = adjudicator.adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=END_TURN),
            no_test_reason="nothing at stake",
            alternatives=offered.actions,
            read_token=offered.token,
        ),
    )
    assert challenged.status.value == "challenged"

    adjudicator.record_narration(challenged, "the boar simply died")

    report = session_report(path / "ledger.jsonl")
    assert report.orphan_narrations == 1
    assert report.flagged(Flag.NARRATION_WITHOUT_RULING)


def test_a_narration_before_any_declaration_is_an_orphan_with_no_turn_to_belong_to(
    tmp_path: Path,
) -> None:
    path = tmp_path / "p"
    path.mkdir()
    source = build(tmp_path / "p-source")
    state = encounter()
    ruling, _ = source.adjudicate(state, strike(state))

    build(path).record_narration(ruling, "the fight was already over")

    report = session_report(path / "ledger.jsonl")
    assert report.orphan_narrations == 1
    assert report.turns == ()


def test_a_turn_that_ended_in_exhaustion_is_flagged_with_its_reason(tmp_path: Path) -> None:
    """And is *not* also flagged as a missing narration — it produced no Ruling to narrate.

    Double-flagging would inflate the number the primary success criterion is read from,
    in the flattering direction: a session looks worse, so the instrument looks stricter.
    """
    path = tmp_path / "q"
    terminal = Terminal(["", "", "nothing at stake", "I do a thing"] * 4)
    outcome = drive(
        loop_for(path, budget=1).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    assert outcome.terminal is not None

    report = session_report(path / "ledger.jsonl")
    flagged = report.flagged(Flag.TERMINATED)
    assert flagged, "the termination is on the record, not only in the driver's return value"
    assert flagged[0].terminal_reason == str(outcome.terminal)
    assert Flag.RULING_WITHOUT_NARRATION not in flagged[0].flags


def test_a_turn_that_ended_fact_unavailable_is_flagged(tmp_path: Path) -> None:
    path = tmp_path / "r"
    terminal = Terminal([END_TURN, NEEDY.id])
    outcome = drive(
        loop_for(path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )

    report = session_report(path / "ledger.jsonl")
    flagged = report.flagged(Flag.TERMINATED)
    assert flagged and flagged[0].terminal_reason == str(outcome.terminal)
    assert flagged[0].terminal_reason == "fact-unavailable"


def test_a_challenge_never_re_adjudicated_is_flagged(tmp_path: Path) -> None:
    """A challenge is the engine asking again. One that is never answered is a skip that
    got through by the agent simply stopping."""
    path = tmp_path / "s"
    path.mkdir()
    adjudicator = build(path)
    state = encounter()
    offered = read(state, "pc")
    ruling, _ = adjudicator.adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=END_TURN),
            no_test_reason="nothing at stake",
            alternatives=offered.actions,
            read_token=offered.token,
        ),
    )
    assert ruling.status.value == "challenged"

    report = session_report(path / "ledger.jsonl")
    assert report.flagged(Flag.CHALLENGE_NEVER_READJUDICATED)


def test_an_alternatives_verdict_other_than_fresh_is_flagged(tmp_path: Path) -> None:
    """The claim about what was offered is the agent's, and an unverified one occupies the
    place where evidence should be."""
    path = tmp_path / "t"
    path.mkdir()
    state = encounter()
    declaration = Declaration(
        actor_id="pc",
        intent=Intent(action_key=attack_key("boar")),
        rule_id=STRIKE.id,
        alternatives=read(state, "pc").actions,
        read_token="rt1.0.notarealdigestnotarealdigest00",
    )
    build(path).adjudicate(state, declaration)

    report = session_report(path / "ledger.jsonl")
    flagged = report.flagged(Flag.ALTERNATIVES_NOT_FRESH)
    assert flagged and flagged[0].alternatives_verdict == "unverified"


def test_a_clean_session_carries_no_flags_at_all(tmp_path: Path) -> None:
    """The instrument has to be able to read clean, or a flag means nothing."""
    path = tmp_path / "u"
    terminal = Terminal([attack_key("boar"), STRIKE.id, "The blade lands."])
    drive(
        loop_for(path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    report = session_report(path / "ledger.jsonl")
    assert report.flags == ()
    assert not report.corrupted


def test_the_rendered_report_shows_the_turns_and_their_flags(tmp_path: Path) -> None:
    path = tmp_path / "v"
    terminal = Terminal([attack_key("boar"), STRIKE.id, "   "])
    drive(
        loop_for(path).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )
    text = render(session_report(path / "ledger.jsonl"))

    assert "SESSION REVIEW" in text
    assert attack_key("boar") in text
    assert str(Flag.RULING_WITHOUT_NARRATION) in text


def test_an_absent_ledger_is_reported_rather_than_raising(tmp_path: Path) -> None:
    report = session_report(tmp_path / "nothing-here.jsonl")
    assert report.turns == ()
    assert report.engine_version is None


# --- Shape --------------------------------------------------------------------------------


def test_a_reconciliation_is_never_an_integrity_failure() -> None:
    """Stated once as a property of the type, so no call site has to remember it."""
    for verdict in ReplayVerdict:
        example = Replay(seq=0, verdict=verdict, detail="")
        assert example.is_integrity_failure == (verdict is ReplayVerdict.DIVERGED)


def test_a_report_is_either_corrupted_or_summarised_never_both() -> None:
    corrupted = SessionReport(path=Path("x"), corrupted=True, findings=("broken",))
    assert corrupted.turns == ()
    assert corrupted.flags == ()


def test_the_flag_names_are_stable_strings() -> None:
    """They are counted across sessions, so renaming one silently resets a measurement."""
    assert {str(f) for f in Flag} == {
        "narration-without-ruling",
        "ruling-without-narration",
        "challenge-never-re-adjudicated",
        "alternatives-not-fresh",
        "terminated",
    }


def test_replaying_an_empty_ledger_returns_nothing_without_raising(tmp_path: Path) -> None:
    assert replay(read_ledger(tmp_path / "absent.jsonl"), engine_version=ENGINE) == ()


@pytest.mark.parametrize("missing", ["seed", "target", "kind", "target_basis"])
def test_a_roll_missing_any_test_input_is_unreplayable(tmp_path: Path, missing: str) -> None:
    """Each of these is an input to the test. Guessing any of them would produce a replay
    that disagreed for a reason the report could not name."""
    ledger = one_ruling(tmp_path / f"w-{missing}")
    rewrite(ledger, entries(ledger, "ruling")[0].seq, lambda p: p["roll"].pop(missing))

    outcome = replay(read_ledger(ledger), engine_version=ENGINE)[0]
    assert outcome.verdict is ReplayVerdict.UNREPLAYABLE


# --- The compat floor, against real payloads (#106, decision 0022) ---------------------


def test_every_entry_the_engine_writes_is_interpretable_by_the_reader_that_ships_with_it(
    tmp_path: Path,
) -> None:
    """The guard that was missing, and the only reason #106 survived two builds.

    `tests/test_ledger_reader.py` asserts this too, but over payloads it hand-writes with
    `compat: 1` — so the one entry type whose floor had drifted was the one its ledgers never
    contained. A reader and a writer that ship together must agree, and the only way to know
    they do is to write with the real writer and read with the real reader.

    While it was broken, every `ruling` entry in every ledger reported `interpretable=False`:
    the reader R35 makes public, telling every consumer it could not read the one entry type
    that carries an outcome.
    """
    from srd_rules_engine.core.ledger import COMPAT
    from srd_rules_engine.core.ledger_reader import READER_VERSION

    ledger = one_ruling(tmp_path / "compat")
    report = read_ledger(ledger)

    assert report.entries, "the fight wrote something"
    assert {e.type for e in report.entries} >= {"session", "declaration", "ruling"}
    assert not report.unauditable, (
        "an entry this engine wrote is unreadable by the reader it shipped with: "
        f"{[(e.type, e.v, e.payload.get(COMPAT)) for e in report.unauditable]}"
    )
    for entry in report.entries:
        floor = entry.payload[COMPAT]
        assert isinstance(floor, int) and floor <= READER_VERSION


def test_a_schema_version_moving_does_not_move_the_reader_floor(tmp_path: Path) -> None:
    """0011 clause 5, and the clause the defect broke: a bump raises `compat` *only* when an
    older reader would get the payload wrong.

    `RULING_VERSION` is 3 while the ruling payload's floor is 1, and that divergence is the
    distinction made visible in the data rather than only asserted in a record. It would be
    impossible if the floor were still derived from the schema version — which is exactly
    what `COMPAT: RULING_VERSION` was.
    """
    from srd_rules_engine.core.adjudicate import RULING_COMPAT, RULING_VERSION
    from srd_rules_engine.core.ledger import COMPAT

    assert RULING_VERSION > RULING_COMPAT, "three schema versions, none of which moved the floor"

    entry = entries(one_ruling(tmp_path / "floor"), "ruling")[0]
    assert entry.v == RULING_VERSION
    assert entry.payload[COMPAT] == RULING_COMPAT


def test_no_payload_writer_derives_its_floor_from_its_schema_version() -> None:
    """The defect in the form it actually took, caught by shape rather than by outcome.

    Every writer read `COMPAT: <ITS_OWN>_VERSION`. That is correct arithmetic only while
    every schema is at 1, so it passed for as long as nothing had moved and broke silently
    the moment something did. Asserting the floors are *named separately* is what makes the
    next person's `COMPAT: SOME_VERSION` fail here rather than in a user's ledger.
    """
    import inspect

    from srd_rules_engine.core import adjudicate, ledger, memory_port

    for module in (adjudicate, ledger, memory_port):
        source = inspect.getsource(module)
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("COMPAT:") and stripped.endswith("_VERSION,"):
                raise AssertionError(
                    f"{module.__name__} derives a compat floor from a schema version: "
                    f"{stripped!r}. They are different number lines (decision 0022) — name "
                    "the floor with its own constant"
                )


# --- Terrain, and the replay gap it did not open (#159) --------------------------------


def _feared_from_behind_a_wall(*, walled: bool) -> EncounterState:
    """A Frightened attacker, its source of fear across the room, and optionally a wall.

    The wall is between the attacker and the **source of fear**, not between it and the
    target. Putting it on the line to the target gives Total Cover, and `attack_resolver`
    refuses the attack outright (p. 179) — there would be no roll to replay, which is a
    different rule and not this one.
    """
    pc = Combatant(
        id="pc",
        name="Pc",
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 16, "dex": 14},
        proficiency_bonus=2,
        position=Position(0, 0, 0),
        conditions=Conditions(
            held=frozenset({Condition.FRIGHTENED}),
            sources={Condition.FRIGHTENED: frozenset({"ghoul"})},
        ),
    )
    boar = Combatant(
        id="boar",
        name="Boar",
        hit_points=11,
        max_hit_points=11,
        armour_class=13,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(5, 0, 0),
    )
    ghoul = Combatant(
        id="ghoul",
        name="Ghoul",
        hit_points=22,
        max_hit_points=22,
        armour_class=12,
        abilities={"str": 14, "dex": 12},
        proficiency_bonus=2,
        position=Position(0, 50, 0),
    )
    walls = (
        (Obstruction(lo=Position(-5, 25, -5), hi=Position(5, 25, 5), blocks_sight=True),)
        if walled
        else ()
    )
    state = replace(EncounterState.new([pc, boar, ghoul]), obstructions=walls)
    return state.with_initiative({"pc": 18, "boar": 4, "ghoul": 2})


def test_terrain_reaches_a_roll_and_the_entry_records_the_derived_value(tmp_path: Path) -> None:
    """#159 asked that when terrain first modifies a d20 test, the ruling entry record the
    **derived** value rather than the terrain. It already does, and terrain already does.

    `#192` and `#193` wired `EncounterState.can_see` into `attack_resolver`, and `can_see`
    reads the encounter's obstructions and its lighting. So a wall now changes whether p. 182's
    Frightened qualifier holds, which changes whether the attack has Disadvantage, which
    changes **how many dice are rolled and which one is used**. #159's "nothing feeds terrain
    into a roll yet" stopped being true without anyone noticing.

    The gap it feared did not open, and the reason is structural rather than lucky: the ruling
    entry records `declared_disadvantage`, and `replay_entry` takes no `EncounterState` at all.
    A ruling cannot record the terrain even by accident, because nothing hands the terrain to
    the recorder.

    Everything below is held constant except the wall — same seed, same declaration, same
    combatants — so the two rows differ *only* by terrain. Note that they differ in exactly
    the way `REPLAYABLE_FROM = 2` exists to prevent: two dice against one. Replaying the
    unwalled ruling as though it had no Disadvantage would take 17 instead of 10 and report a
    mismatch indistinguishable from real drift.
    """
    rulings = {}
    for walled in (False, True):
        path = tmp_path / f"walled-{walled}"
        path.mkdir(parents=True)
        state = _feared_from_behind_a_wall(walled=walled)
        assert state.fear_in_sight("pc") is not walled, "the wall is what moves the qualifier"

        build(path, seed=5).adjudicate(state, strike(state))
        entry = entries(path / "ledger.jsonl", "ruling")[0]
        roll = entry.payload["roll"]
        assert isinstance(roll, Mapping)
        rulings[walled] = (entry, roll)

    (_, open_ground), (_, behind_wall) = rulings[False], rulings[True]

    assert open_ground["declared_disadvantage"] is True, "the source of fear is in sight"
    assert len(open_ground["dice"]) == 2
    assert open_ground["used"] == min(open_ground["dice"])

    assert behind_wall["declared_disadvantage"] is False, "the wall put it out of sight"
    assert len(behind_wall["dice"]) == 1
    assert behind_wall["used"] == behind_wall["dice"][0]

    # The whole point: the entry alone reproduces each, with no state and no terrain.
    for entry, _ in rulings.values():
        assert replay_entry(entry, engine_version=ENGINE, recorded_engine=ENGINE).reproduced

    # And no entry carries the terrain it was derived from. Recording that would make replay
    # recompute the derivation, which reproduces the arithmetic and nothing else — the same
    # mistake as trusting the recorded dice.
    for entry, roll in rulings.values():
        assert not {"obstructions", "lighting", "cover", "terrain"} & set(roll)
        assert not {"obstructions", "lighting"} & set(entry.payload)
