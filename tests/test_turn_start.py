"""The turn's start, and the death save that finally fires there (#124, 0027 clauses 1-4).

0023 found that the save-ends save and the death save were **one missing phase rather than
two oversights**, and built one of them. It could not place the death save, because the
sentence saying when a death save is made was not in this repository — and it refused to
supply it from memory rather than assume it matched save-ends' timing.

The document says the start of a turn (p. 17). Had 0023 assumed, the save would have been
rolled at the end, and **nothing downstream distinguishes a save rolled at the wrong moment
from one rolled at the right one** — no test would have caught it, and the code would have
read as correct.

Three things here are easy to get wrong and are tested against the wrong answer:

* **A monster does not make death saves at all** (p. 17 kills it outright), so an engine
  that fires this phase for every downed creature looks right for a whole fight the party
  wins.
* **A Stable creature does not either**, so being at 0 hit points is not the trigger.
* **The obligation must not repeat within one turn.** One death save per turn, and a failed
  one discharges the obligation exactly as a successful one does — an obligation that stayed
  outstanding after a failure would spin the phase forever.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from pathlib import Path

import pytest

from srd_rules_engine.core import (
    DEATH_SAVE_RULE_ID,
    Adjudicator,
    Combatant,
    EncounterState,
    Ledger,
    Status,
    death_save_resolver,
    death_save_rule,
    load_ruleset,
)
from srd_rules_engine.loop import Narrated, NarrationRequest, TurnLoop
from srd_rules_engine.loop.turn import ObligationOwed, TurnStart
from srd_rules_engine.memory.store import JsonMemoryStore


def build_loop(path: Path, *, seed: int = 11) -> TurnLoop:
    """A loop over the real SRD death-save rule, not a fixture one."""
    path.mkdir(parents=True, exist_ok=True)
    return TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_ruleset((death_save_rule(),)),
            resolvers={DEATH_SAVE_RULE_ID: death_save_resolver()},
            fact_types={},
            port=JsonMemoryStore(path / "memory.json"),
            ledger=Ledger.open(
                path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
            ),
            seed_source=lambda: seed,
        )
    )


def creature(cid: str, *, player: bool) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities={"str": 14, "dex": 12, "con": 14},
        proficiency_bonus=2,
        is_player_character=player,
    )


def encounter() -> EncounterState:
    state = EncounterState.new([creature("hero", player=True), creature("bear", player=False)])
    return state.with_initiative({"hero": 20, "bear": 10})


def downed(who: str = "hero") -> EncounterState:
    state = encounter().with_damage(who, 20)
    assert state.combatant(who).is_down
    return state


def start_turn(
    loop: TurnLoop,
    state: EncounterState,
    actor_id: str,
    narrations: Sequence[str | None] = ("it hangs on",),
) -> TurnStart:
    """Drive the phase, answering each narration request in turn."""
    generator = loop.start_turn(state, actor_id)
    supplied = list(narrations)
    try:
        request = next(generator)
        while True:
            assert isinstance(request, NarrationRequest)
            text = supplied.pop(0) if supplied else "narrated"
            request = generator.send(Narrated(text=text))
    except StopIteration as stop:
        result: TurnStart = stop.value
        return result


# --- The obligation is read off state ---------------------------------------------------


def test_a_downed_player_character_owes_a_death_save(tmp_path: Path) -> None:
    """The gap #124 held open, closed. p. 17: "Whenever you start your turn with 0 Hit
    Points, you must make a Death Saving Throw"."""
    obligations = build_loop(tmp_path).start_turn_obligations(downed(), "hero")

    assert [o.rule_id for o in obligations] == [DEATH_SAVE_RULE_ID]
    assert "death saving throw" in obligations[0].label


def test_a_monster_at_zero_owes_nothing(tmp_path: Path) -> None:
    """p. 17: "A monster dies the instant it drops to 0 Hit Points." An engine that fired
    this phase for every downed creature would look right for a whole winning fight."""
    state = encounter().with_damage("bear", 20)
    assert state.combatant("bear").is_down
    assert build_loop(tmp_path).start_turn_obligations(state, "bear") == ()


def test_a_stable_creature_owes_nothing(tmp_path: Path) -> None:
    """p. 18: "A Stable creature doesn't make Death Saving Throws even though it has 0 Hit
    Points." Being down is the wrong trigger, which is why Stable is tracked separately."""
    state = downed().with_stabilised("hero", seed=7)
    assert build_loop(tmp_path).start_turn_obligations(state, "hero") == ()


def test_a_creature_on_its_feet_owes_nothing(tmp_path: Path) -> None:
    assert build_loop(tmp_path).start_turn_obligations(encounter(), "hero") == ()


def test_an_unknown_actor_owes_nothing_rather_than_raising(tmp_path: Path) -> None:
    assert build_loop(tmp_path).start_turn_obligations(encounter(), "nobody") == ()


# --- The save is rolled, through the one entry point -------------------------------------


def test_the_death_save_is_actually_rolled(tmp_path: Path) -> None:
    """R1 and R4. The engine rolls it, and it reaches an outcome the same way a declared
    action does — a third occasion on which the existing path is taken, not a new path."""
    started = start_turn(build_loop(tmp_path), downed(), "hero")

    (ruling,) = started.rulings
    assert ruling.status is Status.RULED
    assert ruling.result is not None, "a death save is a d20 test"
    assert ruling.rule_id == DEATH_SAVE_RULE_ID


def test_every_ruling_here_asks_for_a_narration(tmp_path: Path) -> None:
    """R29's bounds must reach the narrator exactly as they do for a declared action, or the
    one occasion the agent did not choose is the one it never has to account for."""
    started = start_turn(build_loop(tmp_path), downed(), "hero", narrations=("it shudders",))

    assert started.narrations == ("it shudders",)
    assert not started.missing_narration


def test_the_save_is_recorded_against_the_creature(tmp_path: Path) -> None:
    """A mark either way. The count is what p. 17's three-of-a-kind rule reads."""
    started = start_turn(build_loop(tmp_path), downed(), "hero")
    saves = started.state.combatant("hero").death_saves
    assert saves.successes + saves.failures >= 1


def test_the_obligation_does_not_repeat_within_one_turn(tmp_path: Path) -> None:
    """One death save per turn (p. 17), discharged whether it passed or failed.

    An obligation that stayed outstanding after a failure would spin the phase forever, and
    the creature would roll until it died — which is a hang that produces a plausible ruling
    at every step.
    """
    loop = build_loop(tmp_path)
    started = start_turn(loop, downed(), "hero")

    assert len(started.rulings) == 1
    assert loop.start_turn_obligations(started.state, "hero") == ()


def test_the_obligation_returns_after_the_turn_advances(tmp_path: Path) -> None:
    """Discharge is per turn, not per encounter — `advanced_turn` clears it."""
    loop = build_loop(tmp_path)
    started = start_turn(loop, downed(), "hero")
    assert loop.start_turn_obligations(started.state, "hero") == ()

    later = started.state.advanced_turn().advanced_turn()
    assert loop.start_turn_obligations(later, "hero"), "a new turn owes a new save"


def test_a_creature_owing_nothing_produces_an_empty_phase(tmp_path: Path) -> None:
    """The common case: every turn runs this phase, and almost none of them do anything."""
    started = start_turn(build_loop(tmp_path), encounter(), "hero", narrations=())

    assert started.rulings == ()
    assert started.narrations == ()
    assert started.state.generation == encounter().generation, "and nothing moved"


# --- Clause 4: the skip guarantee at the turn's start -------------------------------------


def test_a_creature_that_owes_a_death_save_may_not_declare_an_action(tmp_path: Path) -> None:
    """0027 clause 4, and the clause that record is least confident in.

    The symmetric guard to `advanced_turn` refusing while an end-of-turn obligation is owed
    — and it cannot live there, because by the time the pointer has moved the incoming
    creature's obligations are *newly* due rather than overdue.
    """
    loop = build_loop(tmp_path)
    with pytest.raises(ObligationOwed, match="death saving throw"):
        next(loop.run(downed(), "hero"))


def test_the_refusal_names_the_phase_that_clears_it(tmp_path: Path) -> None:
    """A refusal that does not say how to proceed is a wall. 0023's own refusal names
    `end_turn`; this one names `start_turn`."""
    loop = build_loop(tmp_path)
    with pytest.raises(ObligationOwed, match=re.escape("TurnLoop.start_turn")):
        next(loop.run(downed(), "hero"))


def test_the_declaration_is_accepted_once_the_save_is_discharged(tmp_path: Path) -> None:
    """The other half: the guard must open again, or a downed creature could never act.

    p. 17 does not say a creature at 0 hit points cannot act — it says it makes a save when
    its turn starts. Refusing forever would be inventing a rule out of a guard.
    """
    loop = build_loop(tmp_path)
    started = start_turn(loop, downed(), "hero")

    request = next(loop.run(started.state, "hero"))
    assert request is not None, "the slot opens once the obligation is met"


def test_a_creature_owing_nothing_is_never_blocked(tmp_path: Path) -> None:
    loop = build_loop(tmp_path)
    assert next(loop.run(encounter(), "hero")) is not None


# --- What a rejected obligation does -------------------------------------------------------


def test_an_unresolvable_obligation_is_named_rather_than_raised(tmp_path: Path) -> None:
    """A ruleset without the death-save rule is a deployment fact. A turn that cannot begin
    is worse than one that begins with the gap recorded — and the ledger carries the
    rejection either way, because the declaration was still adjudicated."""
    empty = TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_ruleset(()),
            resolvers={},
            fact_types={},
            port=JsonMemoryStore(tmp_path / "memory.json"),
            ledger=Ledger.open(
                tmp_path / "ledger.jsonl",
                engine_version="t",
                catalogue_version=1,
                session_id="s",
            ),
            seed_source=lambda: 11,
        )
    )
    started = start_turn(empty, downed(), "hero", narrations=())

    assert started.rulings == ()
    assert [o.rule_id for o in started.unresolvable] == [DEATH_SAVE_RULE_ID]


def test_a_rejected_obligation_still_discharges(tmp_path: Path) -> None:
    """Otherwise the phase spins: the obligation stays outstanding, is rejected again, and
    the loop never terminates. `_rulings` would grow without bound and nothing would say
    why."""
    empty = TurnLoop(
        adjudicator=Adjudicator(
            ruleset=load_ruleset(()),
            resolvers={},
            fact_types={},
            port=JsonMemoryStore(tmp_path / "m.json"),
            ledger=Ledger.open(
                tmp_path / "l.jsonl", engine_version="t", catalogue_version=1, session_id="s"
            ),
            seed_source=lambda: 11,
        )
    )
    started = start_turn(empty, downed(), "hero", narrations=())
    assert empty.start_turn_obligations(started.state, "hero") == ()
