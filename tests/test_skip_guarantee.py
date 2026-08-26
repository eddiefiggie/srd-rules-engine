"""What a session review can and cannot prove about the skip guarantee (#42).

The product contract's primary success criterion is that **a solo session produces no
asserted outcome that did not originate in a Ruling**, measured from the session-review
report. `Flag.NARRATION_WITHOUT_RULING` is the flag that measures it.

These tests drive a real session over a real SRD rule — an attack, resolved by
`core.combat.attack_resolver` — and ask what the instrument actually reads.

**The instrument measures a weaker property than the criterion states.** It measures that
every narration *has* a Ruling. It does not compare what the narration asserts against what
the Ruling decided, and R7 makes the narration bounds advisory by design, so an agent can
narrate a kill over a recorded miss and the report comes back clean.

That is not a defect in the report. It is the gap between two claims that are easy to
conflate, and #42 exists because a green report reads like the criterion cleared. These
tests pin the gap so it cannot be discovered later as a surprise:

* the instrument catches what it measures — a narration with no Ruling behind it;
* the instrument does not catch what it does not — a narration that exceeds its Ruling;
* the engine still did its part, because the bounds said so and nothing enforced them.

**Every test here is a deliberate "nothing changed" guard** — `AGENTS.md`'s named exception
to proving a new test red against the pre-change tree. They all pass against the base commit,
because none of them changes the engine: they pin what it already does, so that the gap
between the criterion and the instrument is a checked fact rather than a paragraph somebody
has to find. A test that went red here would mean the report's behaviour had moved.

The seed is found rather than written down: dice derive from it, so a literal would stop
meaning "a miss" the moment the derivation changed.
"""

from __future__ import annotations

from pathlib import Path

from srd_rules_engine.core import (
    Adjudicator,
    Catalogue,
    Combatant,
    EncounterState,
    Ledger,
    Weapon,
    attack_key,
    attack_resolver,
    load_fixture_ruleset,
    session_report,
)
from srd_rules_engine.core.adjudicate import NARRATION_COMPAT, NARRATION_VERSION
from srd_rules_engine.core.ledger import COMPAT
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.rules import Rule, RuleProvenance
from srd_rules_engine.loop import HumanCliDriver, TurnLoop, drive
from srd_rules_engine.memory.store import JsonMemoryStore

CLUB = Weapon(name="club", damage_dice=1, damage_sides=4)

STRIKE = Rule(
    id="attack",
    summary="An attack with a weapon, resolved by core.combat.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Wires the real SRD attack resolver for a session-level test.",
)


class Terminal:
    """A scripted stand-in for whoever is answering — a person or an agent."""

    def __init__(self, answers: list[str]) -> None:
        self.answers = list(answers)
        self.shown: list[str] = []

    def ask(self, prompt: str) -> str:
        self.shown.append(prompt)
        return self.answers.pop(0) if self.answers else ""

    def show(self, line: str) -> None:
        self.shown.append(line)


def combatant(cid: str, *, ac: int, where: Position) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=ac,
        abilities={"str": 10, "dex": 10},
        proficiency_bonus=2,
        position=where,
    )


def encounter() -> EncounterState:
    """The boar's AC is high enough that a miss is findable, and reachable at 5 feet."""
    state = EncounterState.new(
        [
            combatant("pc", ac=13, where=Position(0, 0, 0)),
            combatant("boar", ac=19, where=Position(5, 0, 0)),
        ]
    )
    return state.with_initiative({"pc": 18, "boar": 4})


def loop_for(path: Path, *, seed: int) -> TurnLoop:
    path.mkdir(parents=True, exist_ok=True)
    return TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_fixture_ruleset("skip-guarantee", [STRIKE]),
            resolvers={STRIKE.id: attack_resolver(CLUB)},
            fact_types={},
            port=JsonMemoryStore(path / "memory.json"),
            ledger=Ledger.open(
                path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
            ),
            catalogue=Catalogue(version=1, triggers=()),
            seed_source=lambda: seed,
        ),
        budget=3,
    )


def _seed_that_misses(tmp_path: Path) -> int:
    """Found, not written down. A literal would stop meaning "a miss" if the derivation
    changed, and the test would keep passing while testing something else."""
    for seed in range(500):
        probe = tmp_path / f"probe-{seed}"
        terminal = Terminal([attack_key("boar"), STRIKE.id, "."])
        outcome = drive(
            loop_for(probe, seed=seed).run(encounter(), "pc"),
            HumanCliDriver(ask=terminal.ask, show=terminal.show),
        )
        ruling = outcome.ruling
        if ruling is not None and ruling.result is not None and not ruling.result.succeeded:
            return seed
    raise AssertionError("no seed in 500 produced a miss; the encounter is wrong")


# --- What the instrument does measure -----------------------------------------------------


def test_a_narration_with_no_ruling_behind_it_is_flagged(tmp_path: Path) -> None:
    """The criterion's own shape, and the report reads it. An instrument that only ever
    comes back clean is worse than none, so this is the control for everything below."""
    path = tmp_path / "orphan"
    path.mkdir(parents=True, exist_ok=True)
    ledger = Ledger.open(
        path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
    )
    ledger.append(
        "narration",
        v=NARRATION_VERSION,
        payload={COMPAT: NARRATION_COMPAT, "actor": "pc", "text": "It dies."},
    )
    ledger.commit()

    report = session_report(path / "ledger.jsonl")
    assert report.orphan_narrations == 1, "a narration standing alone is counted"


# --- What it does not ----------------------------------------------------------------------


def test_a_narration_that_exceeds_its_ruling_is_not_flagged(tmp_path: Path) -> None:
    """**The gap #42 is about.**

    The attack misses. The agent narrates a kill. There *is* a Ruling behind the narration,
    so `NARRATION_WITHOUT_RULING` does not fire — and nothing else compares the words to the
    outcome, because R7 makes the bounds advisory and the report reads structure rather than
    prose.

    A green report therefore does not mean the criterion cleared. It means every narration
    had a Ruling, which is a weaker claim and an easy one to mistake for the stronger.
    """
    seed = _seed_that_misses(tmp_path)
    path = tmp_path / "evasion"

    terminal = Terminal([attack_key("boar"), STRIKE.id, "The club caves its skull in. It dies."])
    outcome = drive(
        loop_for(path, seed=seed).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )

    ruling = outcome.ruling
    assert ruling is not None and ruling.result is not None
    assert not ruling.result.succeeded, "the engine recorded a miss"
    assert all(e.kind.value != "damage" for e in ruling.effects), "and dealt no damage"

    report = session_report(path / "ledger.jsonl")
    assert not report.corrupted
    assert report.flags == (), "the report is clean over a narrated kill that never happened"


def test_the_engine_still_said_what_may_not_be_claimed(tmp_path: Path) -> None:
    """The other half, and the reason this is a disclosed limit rather than a defect.

    R7: the engine states the bounds and does not enforce them. It did state them — so the
    gap is between the report and the criterion, not between the engine and its contract.
    """
    seed = _seed_that_misses(tmp_path)
    path = tmp_path / "bounds"

    terminal = Terminal([attack_key("boar"), STRIKE.id, "It dies."])
    outcome = drive(
        loop_for(path, seed=seed).run(encounter(), "pc"),
        HumanCliDriver(ask=terminal.ask, show=terminal.show),
    )

    ruling = outcome.ruling
    assert ruling is not None
    assert any("attack-roll failed" in line for line in ruling.bounds.may), (
        "the bounds name what happened"
    )
    # Sharper than a generic refusal: the engine named the exact claim the narration went
    # on to make. It is not that the bounds were vague — they were specific and advisory.
    assert any(
        "is dead, unless its hit points reached 0" in line for line in ruling.bounds.may_not
    ), "and forbade precisely the claim an evading narration makes"
