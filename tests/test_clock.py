"""Campaign time, and the Stable creature's recovery it exists to hang (#85, decision 0020).

Two of these are guards against a plausible-and-wrong implementation rather than checks
that the arithmetic adds up:

* **The 1d4 is rolled at stabilisation, not on demand.** Rolling it when somebody asks
  "has it recovered yet" passes every test that only advances the clock once, and hands a
  caller a re-draw: advance an hour, ask, advance an hour, ask, until the answer is the one
  it wanted.
* **Recovery restores a hit point and touches no condition.** p. 18 says the creature
  regains 1 Hit Point and does not say the Unconscious condition ends. The sentence that
  does end a condition on regaining hit points (p. 17) is about Knocking Out a Creature.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.clock import (
    MINUTES_PER_HOUR,
    RECOVERY_OFFSET,
    STABLE_RECOVERY_HIT_POINTS,
    STABLE_RECOVERY_SIDES,
    TIME_VERIFICATION,
    Clock,
    hours,
    stable_recovery_minute,
)
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import ADJUSTMENT_OFFSET, DAMAGE_OFFSET, REPLACEMENT_OFFSET
from srd_rules_engine.core.read_surface import situation
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.state import Combatant, DeathSaves, EncounterState


def encounter(
    *,
    hp: int = 0,
    max_hp: int = 20,
    saves: DeathSaves | None = None,
    conditions: Conditions | None = None,
    clock: Clock | None = None,
) -> EncounterState:
    state = EncounterState.new(
        [
            Combatant(
                id="hero",
                name="Hero",
                hit_points=hp,
                max_hit_points=max_hp,
                armour_class=15,
                abilities={"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 12, "cha": 8},
                proficiency_bonus=2,
                is_player_character=True,
                death_saves=saves or DeathSaves(),
                conditions=conditions or Conditions(),
            )
        ]
    )
    return EncounterState(
        generation=state.generation,
        combatants=state.combatants,
        clock=clock or Clock(),
    )


def hero(state: EncounterState) -> Combatant:
    return state.combatant("hero")


# --- The clock itself --------------------------------------------------------------------


def test_the_clock_counts_forward_only() -> None:
    """A duration that could be un-elapsed would let a caller withdraw a consequence the
    engine had already decided."""
    with pytest.raises(ValueError, match="backwards"):
        Clock(120).advanced(-1)
    with pytest.raises(ValueError, match="not negative"):
        Clock(-1)


def test_advancing_by_zero_is_allowed_and_changes_nothing() -> None:
    assert Clock(90).advanced(0) == Clock(90)


def test_whole_hours_only() -> None:
    """Floor division, so fifty-nine minutes is not an hour — a partial hour that rounded up
    would fire a duration early, which is the direction that invents an outcome."""
    assert Clock(59).elapsed_hours == 0
    assert Clock(60).elapsed_hours == 1
    assert Clock(119).elapsed_hours == 1


def test_hours_converts_and_refuses_a_negative_duration() -> None:
    assert hours(3) == 3 * MINUTES_PER_HOUR
    with pytest.raises(ValueError, match="not negative"):
        hours(-1)


def test_a_round_number_never_becomes_a_clock_minute() -> None:
    """The cited half of 0020. p. 13: a round represents *about* 6 seconds — "about" is the
    document declining an exact conversion, so advancing turns must leave the clock alone."""
    base = encounter(hp=10, clock=Clock(500))
    state = EncounterState(
        generation=base.generation,
        combatants=base.combatants,
        round_number=1,
        turn_index=0,
        clock=base.clock,
    )
    advanced = state.advanced_turn()
    assert advanced.round_number == 2, "the round did move, so this is not a vacuous check"
    assert advanced.clock == Clock(500), "a round is not a number of clock minutes"


# --- The recovery die --------------------------------------------------------------------


def test_the_recovery_die_is_a_d4_measured_in_hours() -> None:
    """p. 18: "regains 1 Hit Point after 1d4 hours". One to four, never zero and never five."""
    rolled = {stable_recovery_minute(Clock(), seed=s) // MINUTES_PER_HOUR for s in range(400)}
    assert rolled == {1, 2, 3, 4}
    assert max(rolled) == STABLE_RECOVERY_SIDES


def test_the_recovery_die_draws_from_its_own_seed_band() -> None:
    """`core.d20` bands the seed's index space so a die can never land on one that seed has
    already produced. The recovery die needs its own band for the same reason."""
    assert max(DAMAGE_OFFSET, REPLACEMENT_OFFSET, ADJUSTMENT_OFFSET) < RECOVERY_OFFSET


def test_the_recovery_time_is_fixed_when_the_creature_becomes_stable() -> None:
    """The anti-re-draw guard, and the reason the roll is not lazy.

    A caller that could re-roll by asking again would advance an hour, look, advance an
    hour, look — and stop when it liked the answer. So the deadline is set once and every
    subsequent advance only compares against it.
    """
    state = encounter(saves=DeathSaves(successes=2)).with_death_save("hero", successes=1, seed=7)
    deadline = hero(state).death_saves.recovers_at_minute
    assert deadline is not None

    for _ in range(30):
        state = state.with_time_passed(1)
        if hero(state).death_saves.stable:
            assert hero(state).death_saves.recovers_at_minute == deadline


def test_stabilising_without_a_seed_is_refused_rather_than_left_unset() -> None:
    """A Stable creature silently missing its deadline is a creature that never wakes up,
    which is the quiet direction to fail in."""
    with pytest.raises(ValueError, match="seed"):
        encounter().with_stabilised("hero")
    with pytest.raises(ValueError, match="seed"):
        encounter(saves=DeathSaves(successes=2)).with_death_save("hero", successes=1)


def test_a_recovery_time_belongs_only_to_a_stable_creature() -> None:
    with pytest.raises(ValueError, match="Stable"):
        DeathSaves(recovers_at_minute=120)


# --- What elapsing time decides ----------------------------------------------------------


def test_a_stable_creature_regains_one_hit_point_at_its_deadline_and_not_before() -> None:
    """p. 18, and exactly one hit point — not a heal to full, and not a fraction of one."""
    state = encounter().with_stabilised("hero", seed=7)
    deadline = hero(state).death_saves.recovers_at_minute
    assert deadline is not None

    just_short = state.with_time_passed(deadline - 1)
    assert hero(just_short).hit_points == 0
    assert hero(just_short).death_saves.stable

    arrived = just_short.with_time_passed(1)
    assert hero(arrived).hit_points == STABLE_RECOVERY_HIT_POINTS
    assert not hero(arrived).death_saves.stable
    assert hero(arrived).death_saves == DeathSaves()


def test_recovery_touches_no_condition() -> None:
    """p. 18 says the creature regains 1 Hit Point. It does not say the Unconscious
    condition ends, so the engine does not end it — the tidy version would be a rule the
    document does not contain."""
    state = encounter(conditions=Conditions(held=frozenset({Condition.UNCONSCIOUS})))
    state = state.with_stabilised("hero", seed=7)
    deadline = hero(state).death_saves.recovers_at_minute
    assert deadline is not None
    after = state.with_time_passed(deadline)
    assert Condition.UNCONSCIOUS in hero(after).conditions.held


def test_healing_before_the_deadline_voids_it() -> None:
    """p. 18 applies to a Stable creature *that isn't healed*. The deadline lives inside the
    record healing resets, so this holds structurally rather than by a check somebody has to
    remember."""
    state = encounter().with_stabilised("hero", seed=7)
    healed = state.with_healing("hero", 3)
    assert healed.combatant("hero").death_saves.recovers_at_minute is None
    much_later = healed.with_time_passed(hours(100))
    assert hero(much_later).hit_points == 3, "a healed creature does not recover again"


def test_damage_before_the_deadline_ends_stable_and_the_deadline_with_it() -> None:
    """p. 18: "If the creature takes damage, it stops being Stable"."""
    state = encounter().with_stabilised("hero", seed=7)
    struck = state.with_damage("hero", 2)
    assert not hero(struck).death_saves.stable
    assert hero(struck).death_saves.recovers_at_minute is None
    later = struck.with_time_passed(hours(100))
    assert hero(later).hit_points == 0, "a creature that stopped being Stable does not wake"


def test_a_dead_creature_does_not_recover() -> None:
    state = encounter(saves=DeathSaves(failures=2)).with_death_save("hero", failures=1)
    assert hero(state).death_saves.dead
    later = state.with_time_passed(hours(100))
    assert hero(later).hit_points == 0
    assert hero(later).death_saves.dead


def test_recovery_never_exceeds_the_hit_point_maximum() -> None:
    state = encounter(max_hp=1).with_stabilised("hero", seed=7)
    deadline = hero(state).death_saves.recovers_at_minute
    assert deadline is not None
    assert hero(state.with_time_passed(deadline)).hit_points == 1


# --- The read surface --------------------------------------------------------------------


def test_the_read_surface_reports_elapsed_time_and_the_countdown() -> None:
    """R18. The agent narrates toward the recovery; the engine still decides it."""
    state = encounter(clock=Clock(30)).with_stabilised("hero", seed=7)
    reported = situation(state, "hero")
    assert reported.elapsed_minutes == 30
    deadline = hero(state).death_saves.recovers_at_minute
    assert deadline is not None
    assert reported.minutes_until_recovery == deadline - 30

    moved_on = state.with_time_passed(60)
    assert situation(moved_on, "hero").elapsed_minutes == 90


def test_a_creature_that_is_not_stable_reports_no_countdown() -> None:
    assert situation(encounter(hp=10), "hero").minutes_until_recovery is None


# --- Provenance --------------------------------------------------------------------------


def test_every_time_value_is_verified_against_the_document() -> None:
    """R31/R32: only `verified` reaches the engine."""
    assert TIME_VERIFICATION.state is VerificationState.VERIFIED
    reference = TIME_VERIFICATION.reference
    assert reference is not None
    assert "p. 18" in reference
    assert "p. 13" in reference
