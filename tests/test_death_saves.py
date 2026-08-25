"""Death saving throws, and what damage at 0 hit points costs (#15).

Every rule here is checked against SRD v5.2.1, pp. 17-18, and the clauses they rest on are
re-checked against the document by `scripts/verify_d20_rules.py`, which CI cannot run.

Two of these rules are easy to implement plausibly and wrongly, so both are tested against
the failure rather than only the success:

* **Massive Damage kills on the remainder**, not on the whole blow. Comparing the full
  damage against the hit point maximum passes every test that only checks a big hit kills.
* **A monster does not make death saves at all.** An engine that gave every combatant the
  player-character rule would look right for the whole of a fight the party wins.
"""

from __future__ import annotations

import pytest

from srd_rules_engine.core.adjudicate import EffectKind, Proposal
from srd_rules_engine.core.d20 import DIE_SIDES, D20Test, TestKind, resolve
from srd_rules_engine.core.death import (
    DEATH_SAVE_DC,
    DEATH_SAVE_VERIFICATION,
    death_save_resolver,
)
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.state import DeathSaves, EncounterState


def d20(proposal: Proposal) -> D20Test:
    """Narrow `Proposal.test`, which became optional with #170 (0027 clause 6).

    Every resolver exercised in this file proposes a d20 test; a testless proposal is a
    different shape and is covered in `tests/test_outcome_without_a_roll.py`. Asserting it
    here keeps these tests reading as assertions about the test rather than about `None`.
    """
    assert proposal.test is not None, "this resolver must propose a d20 test"
    return proposal.test


def encounter(
    *, hp: int = 20, max_hp: int = 20, pc: bool = True, saves: DeathSaves | None = None
) -> EncounterState:
    from srd_rules_engine.core.state import Combatant

    return EncounterState.new(
        [
            Combatant(
                id="hero",
                name="Hero",
                hit_points=hp,
                max_hit_points=max_hp,
                armour_class=15,
                abilities={"str": 14, "dex": 12, "con": 12},
                proficiency_bonus=2,
                is_player_character=pc,
                death_saves=saves or DeathSaves(),
            )
        ]
    )


def hero(state: EncounterState):  # type: ignore[no-untyped-def]
    return state.combatant("hero")


# --- Who makes them at all -----------------------------------------------------------


def test_a_player_character_at_zero_makes_death_saves() -> None:
    assert hero(encounter(hp=0)).makes_death_saves


def test_a_monster_dies_instead_of_making_them() -> None:
    """p. 17: "A monster dies the instant it drops to 0 Hit Points."

    Not a shortcut — a different rule. An engine applying the player-character rule to
    everything would look correct for every fight the party wins.
    """
    state = encounter(hp=4, pc=False).with_damage("hero", 4)
    assert hero(state).death_saves.dead
    assert not hero(state).makes_death_saves


def test_a_character_above_zero_makes_none() -> None:
    assert not hero(encounter(hp=1)).makes_death_saves


def test_a_stable_character_makes_none_though_still_at_zero() -> None:
    """p. 18: "A Stable creature doesn't make Death Saving Throws even though it has 0 Hit
    Points." Being down is not sufficient, which is why Stable is tracked separately."""
    state = encounter(hp=0, saves=DeathSaves(stable=True))
    assert hero(state).is_down
    assert not hero(state).makes_death_saves


# --- The save itself -----------------------------------------------------------------


def test_the_save_is_dc_10_and_carries_no_modifier() -> None:
    """p. 17: "Unlike other saving throws, this one isn't tied to an ability score."

    The empty modifier tuple is the rule, not an omission, so it is asserted rather than
    left to be noticed. The character has a positive Constitution modifier available and
    it must not appear.
    """
    proposal = _propose(encounter(hp=0))
    assert d20(proposal).kind is TestKind.SAVE
    assert d20(proposal).target == DEATH_SAVE_DC == 10
    assert d20(proposal).modifiers == ()
    assert "no modifier applies" in d20(proposal).target_basis


def test_the_resolver_refuses_a_character_who_is_not_making_saves() -> None:
    with pytest.raises(ValueError, match="not making death saving throws"):
        _propose(encounter(hp=12))


def test_a_success_and_a_failure_are_marks_rather_than_hit_points() -> None:
    """p. 17: "A success or failure has no effect by itself.\""""
    proposal = _propose(encounter(hp=0))
    assert proposal.on_success[0].kind is EffectKind.DEATH_SAVE_SUCCESS  # type: ignore[union-attr]
    assert proposal.on_failure[0].kind is EffectKind.DEATH_SAVE_FAILURE  # type: ignore[union-attr]


def test_a_natural_1_costs_two_failures_and_a_natural_20_restores_a_hit_point() -> None:
    """p. 18, and both are "instead of" rather than "as well as" — which is why they are
    their own branches rather than extra effects on the ordinary ones."""
    proposal = _propose(encounter(hp=0))

    assert proposal.on_natural_1 is not None
    assert proposal.on_natural_1[0].kind is EffectKind.DEATH_SAVE_FAILURE  # type: ignore[union-attr]
    assert proposal.on_natural_1[0].amount == 2  # type: ignore[union-attr]

    assert proposal.on_natural_20 is not None
    assert proposal.on_natural_20[0].kind is EffectKind.HEALING  # type: ignore[union-attr]
    assert proposal.on_natural_20[0].amount == 1  # type: ignore[union-attr]


def test_the_natural_branches_win_over_success_and_failure() -> None:
    """A natural 20 is a success and a natural 1 is a failure, so an implementation that
    checked `succeeded` first would run the ordinary branch and never reach these."""
    from srd_rules_engine.core.adjudicate import _branch

    proposal = _propose(encounter(hp=0))
    for face, expected in ((DIE_SIDES, proposal.on_natural_20), (1, proposal.on_natural_1)):
        seed = next(s for s in range(4000) if resolve(d20(proposal), seed=s).used == face)
        result = resolve(d20(proposal), seed=seed)
        assert _branch(proposal, result) == expected


# --- Three of a kind -----------------------------------------------------------------


def test_three_successes_stabilise_and_three_failures_kill() -> None:
    stable = encounter(hp=0, saves=DeathSaves(successes=2)).with_death_save(
        "hero", successes=1, seed=1
    )
    assert hero(stable).death_saves.stable
    assert not hero(stable).death_saves.dead

    dead = encounter(hp=0, saves=DeathSaves(failures=2)).with_death_save("hero", failures=1)
    assert hero(dead).death_saves.dead


def test_the_marks_need_not_be_consecutive() -> None:
    """p. 17: "The successes and failures don't need to be consecutive; keep track of both
    until you collect three of a kind."

    A single net-progress counter would resolve two and two to zero and report a character
    one roll from death as untouched.
    """
    state = encounter(hp=0)
    for successes, failures in ((1, 0), (0, 1), (1, 0), (0, 1)):
        state = state.with_death_save("hero", successes=successes, failures=failures, seed=1)

    assert hero(state).death_saves == DeathSaves(successes=2, failures=2)
    assert hero(state.with_death_save("hero", failures=1)).death_saves.dead


def test_a_resolved_character_stops_accumulating() -> None:
    """Three is the end of it. A fourth failure against a dead character, or any mark
    against a Stable one, would be the engine continuing to resolve a settled question."""
    dead = encounter(hp=0, saves=DeathSaves(failures=3, dead=True))
    assert dead.with_death_save("hero", successes=1) is dead

    stable = encounter(hp=0, saves=DeathSaves(stable=True))
    assert stable.with_death_save("hero", failures=1) is stable


def test_regaining_any_hit_points_resets_both_counts() -> None:
    """p. 17: "reset to zero when you regain any Hit Points". *Any* — one point clears it."""
    state = encounter(hp=0, saves=DeathSaves(successes=2, failures=2)).with_healing("hero", 1)
    assert hero(state).hit_points == 1
    assert hero(state).death_saves == DeathSaves()


def test_becoming_stable_resets_them_too() -> None:
    state = encounter(hp=0, saves=DeathSaves(successes=1, failures=2)).with_stabilised(
        "hero", seed=1
    )
    saves = hero(state).death_saves
    assert (saves.successes, saves.failures, saves.stable, saves.dead) == (0, 0, True, False)
    assert saves.recovers_at_minute is not None, (
        "becoming Stable fixes when the creature regains 1 hit point (p. 18); a Stable "
        "creature without a recovery time never wakes"
    )


# --- Damage at 0 hit points ----------------------------------------------------------


def test_damage_at_zero_hit_points_is_a_failure() -> None:
    state = encounter(hp=0).with_damage("hero", 3)
    assert hero(state).death_saves.failures == 1


def test_damage_from_a_critical_hit_is_two_failures() -> None:
    state = encounter(hp=0).with_damage("hero", 3, critical=True)
    assert hero(state).death_saves.failures == 2


def test_being_reduced_to_zero_starts_the_saves_without_failing_one() -> None:
    """p. 18 charges a failure for damage taken *while at* 0 hit points. The blow that put
    the character there is not also a failure, and charging one would kill on two hits."""
    state = encounter(hp=5).with_damage("hero", 5)
    assert hero(state).hit_points == 0
    assert hero(state).death_saves == DeathSaves()
    assert hero(state).makes_death_saves


def test_damage_ends_stable_and_costs_a_failure() -> None:
    """p. 18: "If the creature takes damage, it stops being Stable and starts making Death
    Saving Throws again." Both happen — it is not merely un-stabilised."""
    state = encounter(hp=0, saves=DeathSaves(stable=True)).with_damage("hero", 2)
    assert not hero(state).death_saves.stable
    assert hero(state).death_saves.failures == 1
    assert hero(state).makes_death_saves


# --- Massive damage, on the remainder ------------------------------------------------


def test_massive_damage_uses_the_remainder_not_the_whole_blow() -> None:
    """p. 17, with the document's own example: a hit point maximum of 12, currently 6,
    taking 18 — the remainder is 12, which equals the maximum, so the character dies.

    The paired case is what makes this test worth having. 12 damage from 6 hit points
    leaves a remainder of 6, well under the maximum, so the character lives and starts
    making saves. An implementation comparing the *full* damage against the maximum kills
    them, and would pass any test that only checked a big hit kills.
    """
    killed = encounter(hp=6, max_hp=12).with_damage("hero", 18)
    assert hero(killed).death_saves.dead

    survived = encounter(hp=6, max_hp=12).with_damage("hero", 12)
    assert not hero(survived).death_saves.dead
    assert hero(survived).hit_points == 0
    assert hero(survived).makes_death_saves


def test_massive_damage_applies_to_a_character_already_at_zero() -> None:
    """At 0 the remainder is the whole blow, which is what p. 18 says in its own words:
    "If the damage equals or exceeds your Hit Point maximum, you die.\""""
    assert hero(encounter(hp=0, max_hp=12).with_damage("hero", 12)).death_saves.dead
    assert not hero(encounter(hp=0, max_hp=12).with_damage("hero", 11)).death_saves.dead


# --- Provenance ----------------------------------------------------------------------


def test_the_death_save_rules_carry_a_verified_citation() -> None:
    assert DEATH_SAVE_VERIFICATION.state is VerificationState.VERIFIED
    assert DEATH_SAVE_VERIFICATION.reference is not None
    assert "SRD v5.2.1" in DEATH_SAVE_VERIFICATION.reference
    for cited in ("pp. 17-18", "p. 181"):
        assert cited in DEATH_SAVE_VERIFICATION.reference


def _propose(state: EncounterState) -> Proposal:
    from srd_rules_engine.core.adjudicate import Declaration, Intent

    return death_save_resolver()(
        state=state,
        declaration=Declaration(
            actor_id="hero", intent=Intent(action_key="death-save"), rule_id="death-save"
        ),
        facts={},
    )


# --- The timing anchor #124 was blocked on ---------------------------------------------


def test_the_verification_names_the_sentence_that_says_when() -> None:
    """R31. The module cited pp. 17-18 for what a death save *is* while nothing in this
    repository said *when* it is made — the gap 0023 named and #124 held open.

    The reference has to name it now, because a verification block that cites a page range
    it does not actually rest on is the defect #129 and #131 were both filed for.
    """
    assert DEATH_SAVE_VERIFICATION.state is VerificationState.VERIFIED
    reference = DEATH_SAVE_VERIFICATION.reference or ""
    assert "p. 17" in reference
    assert "timing" in reference, (
        "the reference does not mention the timing sentence, so a reader cannot tell "
        "whether the page range covers when the save is made or only what it is"
    )


def test_the_timing_clause_is_asserted_against_the_document() -> None:
    """The half a machine here can hold: that the sentence is re-checkable.

    `scripts/verify_d20_rules.py` is not run in CI — the SRD is CC BY 4.0 but not ours to
    redistribute, so CI has no copy. This asserts the clause is *present* to be re-run, not
    that it currently matches; only someone holding the PDF can establish that.

    It is worth pinning because the clause is what separates a transcribed sentence from a
    remembered one, and the remembered answer here is wrong in a specific and costly way:
    it would put the save at the end of a turn, in the phase save-ends lives in.
    """
    from pathlib import Path

    verifier = (Path(__file__).resolve().parents[1] / "scripts" / "verify_d20_rules.py").read_text()
    assert "Whenever you start your turn with 0 Hit Points" in verifier, (
        "the death-save timing clause is gone from verify_d20_rules.py, so the sentence "
        "core.death rests on is no longer re-checkable against the document (#124)"
    )
