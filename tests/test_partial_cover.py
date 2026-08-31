"""Half and Three-Quarters Cover: a degree the engine never measures (#416).

The value machinery has existed since 2026-08-23 — `Cover` with its bonuses, `most_protective`
with p. 15's worked example, and a line test deriving Total Cover — and **Total Cover has been
consumed all along**, refusing an attack through a wall. What had no caller was `Cover.bonus`.

The blocker was never architectural. p. 15 earns Half with "an object that covers at least half
of the target" and Three-Quarters with "at least three-quarters", and the document **supplies no
method for measuring a fraction**. So the degree is stated on the obstruction, the way
`blocks_sight` is stated per barrier because the document answers that per barrier too.

**Directionality needed nothing new.** p. 15 gives the benefit "only when an attack or other
effect originates on the opposite side of the cover", and the line test answers for one pair of
positions — so a creature behind a wall has cover from the archer outside and none from the one
beside it, without anything being stored anywhere.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from srd_rules_engine.core.damage import DamageType
from srd_rules_engine.core.equipment import Carriage, Carried, Weapon
from srd_rules_engine.core.obstructions import (
    Cover,
    Obstruction,
    cover_between,
    most_protective,
    total_cover,
)
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.state import EncounterState

_BOW = Weapon(
    id="fixture:bow",
    damage_dice=1,
    damage_sides=6,
    melee=False,
    damage_type=DamageType.PIERCING,
    ability="dex",
    normal_range=80,
    long_range=320,
)


#: A barrier between x=8 and x=12, so a line from x=0 to x=20 crosses it and one from
#: x=14 to x=20 does not.
def _barrier(degree: Cover) -> Obstruction:
    return Obstruction(lo=Position(8, -10, -10), hi=Position(12, 10, 10), degree=degree)


def _behind(degree: Cover | None, *, from_x: int = 0) -> EncounterState:
    """An attacker at `from_x` and a target at x=20, with the barrier between 8 and 12."""
    from srd_rules_engine.core.state import Combatant

    def _at(x: int, cid: str, ac: int) -> Combatant:
        return Combatant(
            id=cid,
            name=cid.title(),
            hit_points=40,
            max_hit_points=40,
            armour_class=ac,
            abilities={"str": 18, "dex": 18},
            proficiency_bonus=3,
            position=Position(x, 0, 0),
            equipment=(Carried(_BOW, Carriage.HELD),) if cid == "pc" else (),
            weapon_proficiencies=frozenset({_BOW.id}) if cid == "pc" else frozenset(),
        )

    state = EncounterState.new([_at(from_x, "pc", 15), _at(20, "boar", 13)]).with_initiative(
        {"pc": 20, "boar": 5}
    )
    return state if degree is None else replace(state, obstructions=(_barrier(degree),))


def _attack(path: Path, state: EncounterState):  # type: ignore[no-untyped-def]
    from srd_rules_engine.core import (
        Adjudicator,
        Declaration,
        Intent,
        Ledger,
        attack_resolver,
        read,
    )
    from srd_rules_engine.core.rules import Rule, RuleProvenance, load_fixture_ruleset
    from srd_rules_engine.memory.store import JsonMemoryStore

    rule = Rule(
        id="fixture-shot",
        summary="An attack.",
        provenance=RuleProvenance.FIXTURE,
        rationale="Invented; the mechanism is what is under test.",
    )
    path.mkdir(parents=True, exist_ok=True)
    adjudicator = Adjudicator(
        ruleset=load_fixture_ruleset("cover", (rule,)),
        resolvers={rule.id: attack_resolver()},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 3,
    )
    offered = read(state, "pc")
    key = next(a.key for a in offered.actions if a.key == f"attack:{_BOW.id}:boar")
    return adjudicator.adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=key),
            rule_id=rule.id,
            alternatives=offered.actions,
            read_token=offered.token,
        ),
    )


WEST = Position(0, 0, 0)
EAST = Position(20, 0, 0)
#: Beside the target, on its own side of the barrier.
ALONGSIDE = Position(14, 0, 0)


# --- The degree is stated, never measured -------------------------------------------------


def test_a_stated_degree_is_what_the_line_returns() -> None:
    """The engine decides *which* obstructions are between two points. What each one gives is
    the ruleset's, because p. 15 supplies no way to measure a fraction (R31)."""
    for degree in (Cover.HALF, Cover.THREE_QUARTERS, Cover.TOTAL):
        assert cover_between(WEST, EAST, [_barrier(degree)]) is degree


def test_an_obstruction_defaults_to_total() -> None:
    """What every obstruction meant before the field existed — a wall, and the value
    `core.areas` and `core.combat` have always read."""
    assert Obstruction(lo=Position(0, 0, 0), hi=Position(1, 1, 1)).degree is Cover.TOTAL


def test_no_cover_is_legitimate_and_not_refused() -> None:
    """Smoke. p. 181's Heavily Obscured is a fact about *seeing* and p. 15 earns cover by what
    an object *covers* — separate questions, and a barrier may answer them differently, exactly
    as Wall of Force blocks no sight and gives Total Cover."""
    smoke = Obstruction(
        lo=Position(8, -10, -10),
        hi=Position(12, 10, 10),
        degree=Cover.NONE,
        blocks_sight=True,
    )

    assert cover_between(WEST, EAST, [smoke]) is Cover.NONE
    assert smoke.blocks_sight is True


# --- Directional, by the line test rather than by anything stored -------------------------


def test_cover_is_only_had_from_the_far_side() -> None:
    """p. 15: "A target can benefit from cover only when an attack or other effect originates
    on the **opposite side** of the cover."

    This is the sentence that made me file #416 as a gate, on the belief that a per-attack
    relation had nowhere to live. It needed nowhere: two positions and a line test answer it.
    """
    barrier = [_barrier(Cover.THREE_QUARTERS)]

    assert cover_between(WEST, EAST, barrier) is Cover.THREE_QUARTERS, "from across it"
    assert cover_between(ALONGSIDE, EAST, barrier) is Cover.NONE, "and none from beside it"


# --- p. 15's most-protective rule ----------------------------------------------------------


def test_degrees_do_not_add() -> None:
    """p. 15: "only the most protective degree of cover applies; the degrees aren't added
    together." The document's own example — a creature giving Half and a trunk giving
    Three-Quarters — is Three-Quarters. Adding them gives +7, a number the rules never
    produce."""
    creature = Obstruction(lo=Position(4, -2, -2), hi=Position(6, 2, 2), degree=Cover.HALF)
    trunk = _barrier(Cover.THREE_QUARTERS)

    assert cover_between(WEST, EAST, [creature, trunk]) is Cover.THREE_QUARTERS
    assert most_protective([Cover.HALF, Cover.THREE_QUARTERS]).bonus == 5, "not 7"


def test_an_obstruction_off_the_line_contributes_nothing() -> None:
    """The line test is what makes the degrees directional, so a barrier the attack does not
    pass through is not among the degrees compared at all."""
    elsewhere = Obstruction(
        lo=Position(0, 40, 0), hi=Position(4, 44, 4), degree=Cover.THREE_QUARTERS
    )
    assert cover_between(WEST, EAST, [elsewhere]) is Cover.NONE


# --- `total_cover` keeps its narrower question ---------------------------------------------


def test_total_cover_ignores_lesser_degrees() -> None:
    """`core.areas` blocks a line of *effect* with Total Cover (p. 177), and a Fireball is
    stopped by a wall and not by a creature giving Half Cover. So the narrower question keeps
    its own function rather than being folded into `cover_between`."""
    assert total_cover(WEST, EAST, [_barrier(Cover.THREE_QUARTERS)]) is Cover.NONE
    assert total_cover(WEST, EAST, [_barrier(Cover.TOTAL)]) is Cover.TOTAL


def test_the_bonuses_are_the_documents() -> None:
    """p. 15's table: +2 and +5. Total is not a bonus — it is a prohibition."""
    assert (Cover.HALF.bonus, Cover.THREE_QUARTERS.bonus) == (2, 5)
    assert Cover.TOTAL.bonus == 0
    assert not Cover.TOTAL.can_be_targeted


# --- The bonus reaching an attack roll ------------------------------------------------------


def test_cover_raises_the_attacks_target_number_and_says_so(tmp_path: Path) -> None:
    """The consumer `Cover.bonus` did not have, asserted **through a ruling**.

    The first version of this called `_cover_from` and `_ac_basis` directly and then checked
    `armour_class + bonus == 18` — arithmetic the *test* did, true whatever `core.combat`
    wrote. It stayed green when the bonus was removed from the target number entirely.

    p. 15's bonus is "to AC", and a target number that moved must say why (R5): a DC a reader
    cannot trace is one nobody can argue with.
    """
    ruling, _ = _attack(tmp_path, _behind(Cover.THREE_QUARTERS))

    assert ruling.result is not None
    assert ruling.result.target == 18, "armour class 13, and p. 15's +5"
    assert "three-quarters cover" in ruling.result.target_basis
    assert "p. 15" in ruling.result.target_basis


def test_an_attack_with_no_cover_is_unchanged(tmp_path: Path) -> None:
    """The control. An encounter with no barrier between the two answers `NONE` rather than
    inventing one, and the basis says nothing about cover."""
    ruling, _ = _attack(tmp_path, _behind(None))

    assert ruling.result is not None
    assert ruling.result.target == 13
    assert "cover" not in ruling.result.target_basis


def test_cover_from_the_wrong_side_moves_nothing(tmp_path: Path) -> None:
    """p. 15's directional clause, end to end: the same barrier and the same target, attacked
    from its own side of it."""
    ruling, _ = _attack(tmp_path, _behind(Cover.THREE_QUARTERS, from_x=14))

    assert ruling.result is not None
    assert ruling.result.target == 13, "no benefit from cover it is not behind"
