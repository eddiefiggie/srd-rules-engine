"""Which game turn a declaration slot happened in (#120, 0073).

A `Turn` in the report is a **declaration slot**, not a game turn, and two things open one
inside another creature's turn:

* an engine-authored obligation — a save-ends save or a death save
  ([0023](../docs/decisions/0023-the-turns-end-is-a-loop-owned-phase.md));
* a reaction ([0072](../docs/decisions/0072-movement-is-a-phase-the-loop-drives.md)), which
  is the second source [0015](../docs/decisions/0015-reactions-and-the-agent-seam.md) said
  would bite and which did not exist until the build before this one.

`_turns` grouped by position in the sequence, so an Opportunity Attack made mid-move was
filed as a turn of its own — the mover's turn ended, in the report, at the moment somebody
else reacted to it.

**`improvised` was never enough to tell them apart**, and that is what building the second
source showed. It is `True` for an engine-authored obligation and `False` for a reaction,
because a reaction is the agent's own declaration. A reader following the old
`SessionReport.not_measured` advice would have caught one source and silently missed the
other, which is why the turn is now **recorded** on the entry rather than derived from a flag.
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fixtures.encounter import build_adjudicator
from fixtures.ruleset import ATTACK
from srd_rules_engine.core import (
    Declaration,
    EncounterState,
    Intent,
    Position,
    attack_key,
    opportunity_attack_key,
    read,
    session_report,
)
from srd_rules_engine.core.adjudicate import RULING_VERSION
from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.equipment import Carriage, Carried, Weapon
from srd_rules_engine.core.ledger import Ledger
from srd_rules_engine.core.report import render
from srd_rules_engine.core.sight import Lighting, LightLevel
from srd_rules_engine.core.state import Combatant
from srd_rules_engine.loop.turn import Declared, Narrated, TurnLoop

SPEAR = Weapon(
    id="spear",
    weight=3,
    damage_dice=1,
    damage_sides=6,
    ability="str",
    melee=True,
    damage_type=DamageType.PIERCING,
)


def _combatant(cid: str, position: Position) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=1,
        abilities={"str": 16, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        proficiency_bonus=2,
        position=position,
        equipment=(Carried(item=SPEAR, carriage=Carriage.HELD),),
    )


def _encounter() -> EncounterState:
    state = EncounterState(
        generation=0,
        combatants=(_combatant("mover", Position(0, 0, 0)), _combatant("guard", Position(5, 0, 0))),
        lighting=Lighting(ambient=LightLevel.BRIGHT),
    )
    return state.with_initiative({"mover": 20, "guard": 5})


def _acted_then_reacted(tmp_path: Path) -> Path:
    """One game turn: the mover attacks, then moves, and the guard reacts as it leaves.

    Three ledger events under one turn — the mover's own slot, and the guard's interjection.
    """
    state = _encounter()
    loop = TurnLoop(adjudicator=build_adjudicator(tmp_path, seed=11))

    offered = read(state, "mover")
    own = loop.run(state, "mover")
    next(own)
    own.send(
        Declared(
            Declaration(
                actor_id="mover",
                intent=Intent(action_key=attack_key("spear", "guard")),
                rule_id=ATTACK.id,
                alternatives=offered.actions,
                read_token=offered.token,
            )
        )
    )
    try:
        own.send(Narrated("the mover lunges"))
    except StopIteration as stop:
        state = stop.value.state

    moving = loop.move(state, "mover", Position(20, 0, 0))
    next(moving)
    moving.send(
        Declared(
            Declaration(
                actor_id="guard",
                intent=Intent(action_key=opportunity_attack_key("spear", "mover")),
                rule_id=ATTACK.id,
            )
        )
    )
    with contextlib.suppress(StopIteration):
        moving.send(Narrated("the guard's spear follows"))

    return tmp_path / "ledger.jsonl"


# --- The attribution ----------------------------------------------------------------


def test_a_reaction_is_attributed_to_the_turn_it_interrupted(tmp_path: Path) -> None:
    """The defect. Before #120 these were two turns in the report and one in the game."""
    report = session_report(_acted_then_reacted(tmp_path))

    assert [t.actor for t in report.turns] == ["mover", "guard"]
    assert [t.during for t in report.turns] == ["mover", "mover"]
    assert [t.round_number for t in report.turns] == [1, 1]


def test_the_two_slots_group_into_one_game_turn(tmp_path: Path) -> None:
    report = session_report(_acted_then_reacted(tmp_path))

    assert len(report.turns) == 2, "two declaration slots, which is what a Turn counts"
    assert len(report.game_turns) == 1, "and one game turn, which is what a reader wants"

    group = report.game_turns[0]
    assert group.actor == "mover"
    assert group.round_number == 1
    assert [t.actor for t in group.slots] == ["mover", "guard"]


def test_the_reaction_is_marked_as_an_interjection(tmp_path: Path) -> None:
    """`interjected` is the slot-level form: this belongs to somebody other than the
    creature whose turn it is."""
    report = session_report(_acted_then_reacted(tmp_path))

    assert [t.interjected for t in report.turns] == [False, True]
    assert [t.actor for t in report.game_turns[0].interjections] == ["guard"]


def test_improvised_does_not_tell_the_two_apart(tmp_path: Path) -> None:
    """The reason the turn is recorded rather than derived.

    `SessionReport.not_measured` used to say "`Turn.improvised` tells them apart today". It
    does for an engine-authored obligation and **not** for a reaction, which is the agent's
    own declaration — so the advice would have caught one source of interleaving and missed
    the other silently. Asserted rather than described, because it is the load-bearing fact
    under the whole design.
    """
    report = session_report(_acted_then_reacted(tmp_path))

    assert [t.improvised for t in report.turns] == [False, False]
    assert report.turns[1].interjected, "and yet the second is plainly an interjection"


# --- Ledgers written before the field existed ---------------------------------------


def _legacy_ledger(tmp_path: Path) -> Path:
    """A ledger written the way `DECLARATION_VERSION` 2 wrote one: no turn recorded.

    **Written rather than edited.** The ledger is checksummed and chained, so removing a
    field from a finished file reads as tampering — correctly, and the report says
    `corrupted` rather than answering questions about it. The only honest way to test an
    older ledger is to append entries the older shape, which is what this does.
    """
    tmp_path.mkdir(parents=True, exist_ok=True)
    ledger = Ledger.open(
        tmp_path / "legacy.jsonl", engine_version="t", catalogue_version=1, session_id="old"
    )
    with ledger.escape_boundary():
        for actor, key in (
            ("mover", attack_key("spear", "guard")),
            ("guard", "attack:spear:mover"),
        ):
            ledger.append(
                "declaration",
                v=2,
                payload={
                    "compat": 1,
                    "resumption": False,
                    "catalogue_version": 1,
                    "actor": actor,
                    "intent": {"action_key": key, "improvised": False, "label": None},
                    "rule_id": ATTACK.id,
                    "no_test_reason": None,
                    "alternatives": [],
                    "read_token": None,
                },
            )
            ledger.append(
                "ruling",
                v=RULING_VERSION,
                payload={
                    "compat": 1,
                    "status": "ruled",
                    "actor": actor,
                    "rule_id": ATTACK.id,
                    "alternatives_verdict": "unread",
                    "effects": [],
                    "withheld": [],
                    "facts": [],
                    "citations": [],
                    "fired": [],
                },
            )
    return tmp_path / "legacy.jsonl"


def test_an_older_ledger_is_reported_unattributable_rather_than_guessed(
    tmp_path: Path,
) -> None:
    """Ledgers outlive the code that wrote them, and this engine does not reconstruct the
    turn from actor changes — that inference would guess at exactly the case the field was
    added for. `attributable` is what says so, and it is keyed on the field being *present*
    rather than on its value: `during=None` is "outside combat", a different claim.
    """
    report = session_report(_legacy_ledger(tmp_path))

    assert not report.corrupted, "a v2 ledger is sound; it simply says less"
    assert len(report.turns) == 2
    assert all(not t.attributable for t in report.turns)
    assert all(t.during is None for t in report.turns)
    assert all(not t.interjected for t in report.turns), "no claim, rather than a wrong one"
    assert all(not group.attributable for group in report.game_turns)


def _out_of_combat(tmp_path: Path) -> Path:
    """One slot declared with no initiative rolled, so there is no turn to be inside."""
    state = EncounterState(
        generation=0,
        combatants=(_combatant("mover", Position(0, 0, 0)), _combatant("guard", Position(5, 0, 0))),
        lighting=Lighting(ambient=LightLevel.BRIGHT),
    )
    assert not state.in_combat, "the whole point of this fixture"

    adjudicator = build_adjudicator(tmp_path, seed=5)
    adjudicator.adjudicate(
        state,
        Declaration(
            actor_id="mover",
            intent=Intent(action_key=attack_key("spear", "guard")),
            rule_id=ATTACK.id,
        ),
    )
    return tmp_path / "ledger.jsonl"


def test_outside_combat_is_recorded_as_no_turn_rather_than_as_no_record(
    tmp_path: Path,
) -> None:
    """The distinction `attributable` exists for, and the one a truthiness check collapses.

    A slot outside combat has `during=None` **and the field present**: the ledger recorded
    that there was no turn. A slot from an older ledger has no field at all. Both leave
    `during` as `None`, so a reader keying on the value cannot tell "the engine says there
    was no turn" from "this ledger cannot say" — and only the second is a limit.

    Written after a corruption proof came back **green**: keying `attributable` on the value
    rather than on the key's presence left every assertion here passing, because the legacy
    fixture has the field absent in both readings. Nothing about reading those assertions
    revealed it (`AGENTS.md`, "vacuous under its own fixture").
    """
    report = session_report(_out_of_combat(tmp_path))

    assert len(report.turns) == 1
    slot = report.turns[0]
    assert slot.during is None
    assert slot.round_number is None
    assert slot.attributable, "the ledger recorded that there was no turn, which is a fact"
    assert not slot.interjected, "no turn to be inside means nothing to interject into"

    assert [g.attributable for g in report.game_turns] == [True]
    assert "outside combat" in render(report)


def test_the_limit_is_published_for_older_ledgers_only(tmp_path: Path) -> None:
    """R30's `not_measured` is what keeps a clean report from being read for more than it
    says. It named turn grouping as undecided; the grouping is decided, and what remains
    unmeasurable is a ledger that predates the field."""
    report = session_report(_acted_then_reacted(tmp_path))
    published = " ".join(report.not_measured)

    assert "DECLARATION_VERSION` 3" in published
    assert "game_turns" in published


# --- What a reader actually sees -----------------------------------------------------


def test_the_rendered_report_shows_the_turn_and_names_the_interjection(
    tmp_path: Path,
) -> None:
    """The artefact R13's session review reads. A reaction rendered as a bare slot reads as
    the turn's own creature acting twice, which is the misreading the grouping exists to
    stop."""
    text = render(session_report(_acted_then_reacted(tmp_path)))

    assert "round 1, mover's turn" in text
    assert "guard (interjected)" in text
    assert "game turns:        1" in text
    assert "declaration slots: 2" in text


def test_the_rendered_report_says_when_it_cannot_attribute(tmp_path: Path) -> None:
    text = render(session_report(_legacy_ledger(tmp_path)))

    assert "turn unrecorded" in text
    assert "interjected" not in text, "an unattributable slot makes no claim about whose turn"
