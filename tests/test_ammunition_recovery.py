"""p. 89's minute spent recovering ammunition, and a fight boundary the engine cannot see
(#301, 0044 clause 5).

> **After a fight, you can spend 1 minute to recover half the ammunition (round down) you used
> in the fight; the rest is lost.**

The arithmetic is small. The interesting part is the boundary:

> p. 14, *Ending Combat*: Combat ends when one side or the other is defeated, which can mean
> the creatures are **killed** or **knocked out** or have **surrendered** or **fled**. Combat
> can also end when **both sides agree to end it**.

**Five conditions; the engine can observe two** — and the two it can see are the ones that
answer *yes*, so inferring from them would end fights early and hand back arrows on the
engine's own authority. So the claim is accepted, and the acceptance is disclosed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    Declaration,
    EffectKind,
    EncounterState,
    Intent,
    Item,
    Ledger,
    Rule,
    RuleProvenance,
    Weapon,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.combat import ammunition_recovery_resolver
from srd_rules_engine.core.equipment import RECOVERY_MINUTES
from srd_rules_engine.core.position import Position
from srd_rules_engine.memory.store import JsonMemoryStore

BOLT = Item(id="fixture:bolt", weight=0.075)
BOW = Weapon(
    id="fixture:bow",
    damage_dice=1,
    damage_sides=8,
    melee=False,
    ammunition_id=BOLT.id,
    normal_range=80,
    long_range=320,
    hands_when_held=2,
)

RECOVER = Rule(
    id="ammunition-recovery",
    summary="p. 89's minute spent recovering ammunition after a fight.",
    provenance=RuleProvenance.FIXTURE,
    rationale="Invented, because no weapon table ships here.",
)
RULESET = load_fixture_ruleset("recovery", [RECOVER])


def archer(*, bolts: int = 5) -> Combatant:
    equipment: tuple[Carried, ...] = (Carried(BOW, Carriage.HELD),)
    if bolts:
        equipment = (*equipment, Carried(BOLT, quantity=bolts))
    return Combatant(
        id="pc",
        name="Pc",
        hit_points=30,
        max_hit_points=30,
        armour_class=13,
        abilities={"str": 14, "dex": 16},
        proficiency_bonus=2,
        position=Position(0, 0, 0),
        hands=2,
        equipment=equipment,
        weapon_proficiencies=frozenset({BOW.id}),
    )


def spent(used: int, *, remaining: int = 0) -> EncounterState:
    """An encounter in which the archer has fired `used` bolts and has `remaining` left.

    The archer starts with `used + remaining`, because you cannot fire what you never had —
    the transition refuses it, which is #273's guard doing its job on a fixture.
    """
    state = EncounterState.new([archer(bolts=used + remaining)])
    for _ in range(used):
        state = state.with_ammunition_spent("pc", BOLT.id)
    return state


def build(path: Path) -> Adjudicator:
    path.mkdir(parents=True, exist_ok=True)
    return Adjudicator(
        ruleset=RULESET,
        resolvers={RECOVER.id: ammunition_recovery_resolver()},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 3,
    )


def declare(state: EncounterState) -> Declaration:
    offered = read(state, "pc")
    return Declaration(
        actor_id="pc",
        intent=Intent(improvised=True, label="a minute spent recovering ammunition"),
        rule_id=RECOVER.id,
        alternatives=offered.actions,
        read_token=offered.token,
    )


def recover(state: EncounterState, path: Path) -> EncounterState:
    _ruling, after = build(path).adjudicate(state, declare(state))
    return after


# --- half, rounding down ----------------------------------------------------------------


def test_half_of_what_was_used_comes_back(tmp_path: Path) -> None:
    state = spent(4, remaining=1)
    assert state.recoverable_ammunition("pc") == {BOLT.id: 2}
    after = recover(state, tmp_path)
    assert after.ammunition_for("pc", BOLT.id) == 3, "one left, plus two recovered"


def test_an_odd_count_rounds_down(tmp_path: Path) -> None:
    """p. 89: "half the ammunition (**round down**)"."""
    after = recover(spent(3), tmp_path)
    assert after.ammunition_for("pc", BOLT.id) == 1


def test_a_single_piece_recovers_nothing(tmp_path: Path) -> None:
    """Half of one rounds to none, and "the rest is lost" — so nothing comes back and nothing
    is left to try again for."""
    after = recover(spent(1), tmp_path)
    assert after.ammunition_for("pc", BOLT.id) == 0
    assert after.ammunition_used == {}


def test_the_rest_is_lost_so_a_second_minute_recovers_nothing(tmp_path: Path) -> None:
    """The tally clears whatever the half came to. Leaving it would let a second minute
    recover from the same fight, which "the rest is lost" forbids."""
    once = recover(spent(4), tmp_path / "a")
    assert once.ammunition_used == {}
    with pytest.raises(ValueError, match="used no ammunition in this fight"):
        build(tmp_path / "b").adjudicate(once, declare(once))


def test_a_creature_that_spent_the_lot_gets_the_entry_back(tmp_path: Path) -> None:
    """The last piece took the entry with it (#273), so recovery has to recreate one."""
    state = spent(4)
    assert state.ammunition_for("pc", BOLT.id) == 0
    after = recover(state, tmp_path)
    assert after.ammunition_for("pc", BOLT.id) == 2
    entry = next(c for c in after.combatant("pc").equipment if c.item.id == BOLT.id)
    assert entry.carriage is Carriage.STOWED, "0039 clause 3's residual; p. 89 does not say"


# --- the minute (0020 clause 3's other kind of time) ------------------------------------


def test_the_minute_is_the_documents_number_not_the_agents(tmp_path: Path) -> None:
    """0020 clause 3 governs *agent-supplied* elapsed time — "only the agent knows the party
    walked for three hours". p. 89 is not asking: it says 1 minute. So the ruling states it,
    and `with_time_passed` still decides every consequence."""
    before = spent(4)
    assert before.clock.elapsed_minutes == 0
    after = recover(before, tmp_path)
    assert after.clock.elapsed_minutes == RECOVERY_MINUTES == 1


def test_the_minute_is_its_own_recorded_effect(tmp_path: Path) -> None:
    state = spent(4)
    ruling, _after = build(tmp_path).adjudicate(state, declare(state))
    kinds = {e.kind for e in ruling.effects}
    assert EffectKind.AMMUNITION_RECOVERED in kinds
    assert EffectKind.TIME_PASSED in kinds


# --- the boundary the engine cannot see (0044 clause 5) ---------------------------------


def test_recovering_nothing_is_refused_rather_than_resolved(tmp_path: Path) -> None:
    """A minute spent recovering nothing is not a rule the document states."""
    state = EncounterState.new([archer()])
    with pytest.raises(ValueError, match="used no ammunition in this fight"):
        build(tmp_path).adjudicate(state, declare(state))


def test_the_engine_does_not_check_that_the_fight_ended(tmp_path: Path) -> None:
    """0044 clause 5. p. 14 gives five conditions and the engine can observe two — and the two
    it can see are the ones that answer *yes*, so refusing on them would overrule the agent on
    the three it cannot see, while inferring from them would end fights early.

    The archer here is mid-fight by any observable measure: a conscious hostile stands five
    feet away. The recovery is accepted anyway, and the bound says the claim was not checked.
    """
    hostile = Combatant(
        id="boar",
        name="Boar",
        hit_points=200,
        max_hit_points=200,
        armour_class=8,
        abilities={"str": 12, "dex": 10},
        proficiency_bonus=2,
        position=Position(5, 0, 0),
    )
    state = EncounterState.new([archer(bolts=5), hostile]).with_initiative({"pc": 20, "boar": 5})
    for _ in range(4):
        state = state.with_ammunition_spent("pc", BOLT.id)

    ruling, after = build(tmp_path).adjudicate(state, declare(state))
    assert after.ammunition_for("pc", BOLT.id) == 3, "accepted while a hostile stands adjacent"
    assert any("did not check" in bound for bound in ruling.bounds.may_not)
