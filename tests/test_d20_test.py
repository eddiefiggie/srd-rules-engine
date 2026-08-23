"""One primitive, three kinds, and a roll that reproduces itself from its own record.

The replay guarantee is what most of this file is about. R28 requires a ruling entry to
replay to an identical outcome from its recorded seed and inputs — so the dice must be a
function of the seed and nothing else, stable across processes, machines, and Python
versions. A die drawn from `random` would satisfy the tests and quietly break that
promise on some future interpreter, because bit consumption there is an implementation
detail rather than a specification.

The distribution is checked too. A loaded die inside an engine built for auditable
outcomes is not a defect anyone would find by inspection.
"""

from __future__ import annotations

import dataclasses
import subprocess
import sys
from collections import Counter

import pytest

from srd_rules_engine.core.d20 import (
    ADVANTAGE_VERIFICATION,
    DIE_SIDES,
    Advantage,
    D20Test,
    Modifier,
    TestKind,
    die,
    resolve,
)
from srd_rules_engine.core.rules import VerificationState

STRENGTH = Modifier(source="ability:strength", value=3)
PROFICIENCY = Modifier(source="proficiency", value=2)


def check(target: int = 15, **overrides: object) -> D20Test:
    fields: dict[str, object] = {
        "kind": TestKind.CHECK,
        "target": target,
        "target_basis": "difficulty class set for a rain-slick wall",
    }
    fields.update(overrides)
    return D20Test(**fields)  # type: ignore[arg-type]


# --- Determinism, which is what replay depends on ----------------------------------


def test_the_same_seed_and_inputs_produce_identical_dice() -> None:
    first = resolve(check(), seed=4242)
    second = resolve(check(), seed=4242)
    assert first.dice == second.dice
    assert first == second, "the whole result reproduces, not only the dice"


def test_different_seeds_produce_different_dice_over_a_run() -> None:
    rolls = {resolve(check(), seed=seed).used for seed in range(200)}
    assert len(rolls) > 1, "a seed that changes nothing is not a seed"


def test_the_dice_reproduce_in_a_separate_process() -> None:
    """`random`'s bit consumption is an implementation detail; a hash is a specification."""
    script = (
        "from srd_rules_engine.core.d20 import D20Test, TestKind, resolve;"
        "print(resolve(D20Test(kind=TestKind.CHECK, target=15, target_basis='b'), seed=99).used)"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert int(result.stdout.strip()) == resolve(check(), seed=99).used


def test_replaying_a_recorded_seed_and_inputs_gives_an_identical_result() -> None:
    """The verification U8 asks for: replay from the record, assert identity."""
    original = resolve(
        check(target=13, modifiers=(STRENGTH, PROFICIENCY), has_advantage=True), seed=7
    )
    replayed = resolve(
        D20Test(
            kind=original.kind,
            target=original.target,
            target_basis=original.target_basis,
            modifiers=original.modifiers,
            has_advantage=original.declared_advantage,
            has_disadvantage=original.declared_disadvantage,
        ),
        seed=original.seed,
    )
    assert replayed == original


# --- The die itself ------------------------------------------------------------------


def test_every_face_is_within_range() -> None:
    for seed in range(500):
        assert 1 <= resolve(check(), seed=seed).used <= DIE_SIDES


def test_the_die_is_not_loaded() -> None:
    """Rejection sampling rather than a modulo, so no face is likelier than the others."""
    counts = Counter(resolve(check(), seed=seed).used for seed in range(20_000))
    assert len(counts) == DIE_SIDES, "every face appears"
    expected = 20_000 / DIE_SIDES
    assert max(counts.values()) < expected * 1.15
    assert min(counts.values()) > expected * 0.85


# --- Advantage, disadvantage, and their cancellation --------------------------------


def test_advantage_rolls_two_dice_and_takes_the_higher() -> None:
    result = resolve(check(has_advantage=True), seed=11)
    assert len(result.dice) == 2
    assert result.used == max(result.dice)
    assert result.effective is Advantage.ADVANTAGE


def test_disadvantage_rolls_two_dice_and_takes_the_lower() -> None:
    result = resolve(check(has_disadvantage=True), seed=11)
    assert len(result.dice) == 2
    assert result.used == min(result.dice)
    assert result.effective is Advantage.DISADVANTAGE


def test_advantage_and_disadvantage_cancel_to_a_single_roll() -> None:
    """They cancel rather than accumulating, so the result is a plain roll."""
    result = resolve(check(has_advantage=True, has_disadvantage=True), seed=11)
    assert len(result.dice) == 1
    assert result.effective is Advantage.NONE
    assert result.used == resolve(check(), seed=11).used, "identical to a plain roll"


def test_a_plain_roll_uses_onedie() -> None:
    result = resolve(check(), seed=11)
    assert len(result.dice) == 1
    assert result.effective is Advantage.NONE


def test_the_declared_state_is_recorded_alongside_the_effective_one() -> None:
    """A cancelled roll must not read as though neither state was ever present."""
    result = resolve(check(has_advantage=True, has_disadvantage=True), seed=11)
    assert result.declared_advantage and result.declared_disadvantage
    assert result.effective is Advantage.NONE


def test_the_two_dice_are_drawn_independently() -> None:
    """If both dice came from the same material, advantage would roll one number twice.

    Every ordering assertion still passes in that case, because `max(d, d)` is `d` — so
    advantage would silently do nothing and nothing else here would notice.
    """
    pairs = [resolve(check(has_advantage=True), seed=seed).dice for seed in range(200)]
    differing = sum(1 for first, second in pairs if first != second)
    assert differing > 150, f"only {differing}/200 pairs differed — the dice are not independent"


def test_advantage_skews_high_and_disadvantage_skews_low() -> None:
    """The behavioural form of the same property: the mechanism has to actually help."""
    seeds = range(2_000)
    plain = sum(resolve(check(), seed=s).used for s in seeds)
    better = sum(resolve(check(has_advantage=True), seed=s).used for s in seeds)
    worse = sum(resolve(check(has_disadvantage=True), seed=s).used for s in seeds)

    assert better > plain > worse


def test_adjacent_seeds_do_not_share_dice() -> None:
    """Seed and die index must not be separable, or consecutive rolls correlate.

    Folding the index into the seed — deriving die `i` of seed `n` from `n + i` — leaves
    each roll internally independent and still makes seed `n`'s second die identical to
    seed `n + 1`'s first, every time. Seeds are drawn per adjudication, so that is a
    visible pattern across a session rather than a curiosity.
    """
    overlaps = sum(
        resolve(check(has_advantage=True), seed=n).dice[1]
        == resolve(check(has_advantage=True), seed=n + 1).dice[0]
        for n in range(200)
    )
    assert overlaps < 40, f"{overlaps}/200 adjacent rolls shared a die — the derivation separates"


def test_the_hashed_material_is_unambiguous_across_seed_and_index() -> None:
    """Fixed-width fields, because a concatenated encoding conflates specific pairs.

    `f"{seed}{index}"` renders (1, 11) and (11, 1) as the same string, and likewise (1, 23)
    and (12, 3) — so those rolls would share a die *every time*. An averaged rate does not
    see it: only a handful of digit-string coincidences collide, and the rest of the grid
    dilutes them into noise. So the pairs are named rather than sampled.

    Two dice can still land on the same face by chance, one time in twenty. Six pairs all
    agreeing has probability 20**-6, so the assertion is on how many agree.
    """
    conflated = [
        ((1, 11), (11, 1)),
        ((2, 22), (22, 2)),
        ((3, 33), (33, 3)),
        ((1, 23), (12, 3)),
        ((4, 45), (44, 5)),
        ((5, 56), (55, 6)),
    ]
    for left, right in conflated:
        assert f"{left[0]}{left[1]}0" == f"{right[0]}{right[1]}0", "the pair is genuinely conflated"

    agreeing = sum(die(*left) == die(*right) for left, right in conflated)
    assert agreeing <= 2, (
        f"{agreeing}/6 conflated pairs produced the same die — the encoding is ambiguous"
    )


def test_a_seed_outside_the_supported_range_is_refused() -> None:
    with pytest.raises(ValueError, match="non-negative 64-bit integer"):
        resolve(check(), seed=-1)
    with pytest.raises(ValueError, match="non-negative 64-bit integer"):
        resolve(check(), seed=2**64)


def test_advantage_and_disadvantage_take_from_the_same_pair_of_dice() -> None:
    """The seed determines the dice; only which one is used differs."""
    with_advantage = resolve(check(has_advantage=True), seed=31)
    with_disadvantage = resolve(check(has_disadvantage=True), seed=31)
    assert with_advantage.dice == with_disadvantage.dice
    assert with_advantage.used >= with_disadvantage.used


# --- One primitive: the kind changes only where the target came from ----------------


def test_a_check_a_save_and_an_attack_resolve_identically() -> None:
    """R11: they are one primitive, differing in what supplies the target number."""
    results = [
        resolve(
            D20Test(
                kind=kind,
                target=14,
                target_basis="whatever supplied it",
                modifiers=(STRENGTH,),
            ),
            seed=77,
        )
        for kind in TestKind
    ]
    assert len({(r.dice, r.used, r.total, r.succeeded) for r in results}) == 1
    assert {r.kind for r in results} == set(TestKind)


def test_the_target_basis_is_carried_through_to_the_result() -> None:
    result = resolve(check(target_basis="armour class 15 from studded leather"), seed=3)
    assert "studded leather" in result.target_basis
    assert "studded leather" in result.derivation()


def test_a_target_number_without_its_derivation_is_refused() -> None:
    """R5 requires the Ruling to show where the number came from, not just what it was."""
    with pytest.raises(ValueError, match="carries its derivation"):
        D20Test(kind=TestKind.CHECK, target=15, target_basis="")


# --- Modifiers -----------------------------------------------------------------------


def test_modifiers_accumulate_into_the_total() -> None:
    result = resolve(check(modifiers=(STRENGTH, PROFICIENCY)), seed=5)
    assert result.total == result.used + 5
    assert result.modifier_total == 5


def test_the_recorded_modifier_order_is_the_order_supplied() -> None:
    """Addition commutes, so order does not change the total — it makes the record read back."""
    result = resolve(check(modifiers=(PROFICIENCY, STRENGTH)), seed=5)
    assert result.modifiers == (PROFICIENCY, STRENGTH)
    assert result.derivation().index("proficiency") < result.derivation().index("strength")


def test_a_modifier_names_its_source() -> None:
    with pytest.raises(ValueError, match="names its source"):
        Modifier(source="", value=2)


def test_negative_modifiers_subtract() -> None:
    penalty = Modifier(source="circumstance:exhausted", value=-4)
    result = resolve(check(modifiers=(penalty,)), seed=5)
    assert result.total == result.used - 4
    assert "-4 (circumstance:exhausted)" in result.derivation()


def test_the_derivation_reads_as_arithmetic_a_person_can_check() -> None:
    result = resolve(check(target=12, modifiers=(STRENGTH,)), seed=5)
    line = result.derivation()
    assert str(result.used) in line
    assert "+3 (ability:strength)" in line
    assert f"= {result.total}" in line


# --- Success -------------------------------------------------------------------------


def test_meeting_the_target_succeeds() -> None:
    """Meets *or beats* — an equal total is a success, not a near miss."""
    result = resolve(check(target=1), seed=5)
    assert result.succeeded

    exact = resolve(check(target=resolve(check(), seed=5).used), seed=5)
    assert exact.succeeded


def test_falling_short_of_the_target_fails() -> None:
    result = resolve(check(target=DIE_SIDES + 100), seed=5)
    assert not result.succeeded
    assert "falls short of" in result.derivation()


def test_the_raw_dice_are_returned_alongside_the_total() -> None:
    """R5: a Ruling shows the arithmetic rather than asserting the outcome."""
    result = resolve(check(has_advantage=True, modifiers=(STRENGTH,)), seed=5)
    assert result.dice
    assert result.used in result.dice
    assert result.total == result.used + 3


# --- What the document says, checked against what the primitive does ------------------
#
# #52 asked four questions about the advantage rules, which until now were machinery the
# M1 plan asserted rather than behaviour read off SRD v5.2.1. These encode the answers.
# `scripts/verify_d20_rules.py` checks the other half — that the cited sentences still say
# what these tests assume — against the document, which CI does not carry.


def test_the_advantage_semantics_carry_a_verified_citation() -> None:
    """R31: SRD-derived machinery names what it was checked against, or it is not trusted."""
    assert ADVANTAGE_VERIFICATION.state is VerificationState.VERIFIED
    assert ADVANTAGE_VERIFICATION.reference is not None
    assert "SRD v5.2.1" in ADVANTAGE_VERIFICATION.reference
    # The pages the sentences actually sit on. A citation naming the wrong page is the
    # defect scripts/verify_d20_rules.py caught on its first run against the document.
    for cited in ("pp. 7-8", "p. 176", "p. 181"):
        assert cited in ADVANTAGE_VERIFICATION.reference


def test_the_documents_own_worked_example_resolves_as_it_says() -> None:
    """p. 8: "if you have Disadvantage and roll an 18 and a 3, use the 3. If you instead
    have Advantage and roll those numbers, use the 18."

    The seed search finds a real pair rather than stubbing the dice, so this exercises the
    same path a ruling takes.
    """
    seed = next(
        s
        for s in range(10_000)
        if sorted(resolve(check(has_advantage=True), seed=s).dice) == [3, 18]
    )

    assert resolve(check(has_disadvantage=True), seed=seed).used == 3
    assert resolve(check(has_advantage=True), seed=seed).used == 18


def test_cancellation_is_presence_based_rather_than_count_based() -> None:
    """p. 8: the roll has neither state "even if multiple circumstances impose
    Disadvantage and only one grants Advantage or vice versa".

    This is the question #52 raised, and the reading it rules out — that four sources of
    Disadvantage against one of Advantage leaves you with Disadvantage — is the one a
    reasonable implementer would reach for. It is unrepresentable here: the test carries
    two booleans rather than two counters, so a caller cannot state a count for the
    engine to get wrong. That is asserted as a property of the type, not just of a roll.
    """
    fields = {f.name for f in dataclasses.fields(D20Test)}
    assert {"has_advantage", "has_disadvantage"} <= fields
    for name in ("has_advantage", "has_disadvantage"):
        assert D20Test.__annotations__[name] == "bool"

    both = resolve(check(has_advantage=True, has_disadvantage=True), seed=11)
    assert both.effective is Advantage.NONE
    assert len(both.dice) == 1


def test_sources_on_the_same_side_do_not_accumulate_into_more_dice() -> None:
    """p. 8: "If multiple situations affect a roll and they all grant Advantage on it, you
    still roll only two d20s." Two is the ceiling as well as the floor.
    """
    for state in ({"has_advantage": True}, {"has_disadvantage": True}):
        assert len(resolve(check(**state), seed=11).dice) == 2


def test_both_dice_are_retained_so_neither_can_be_called_the_discarded_one() -> None:
    """p. 8, Interactions with Rerolls: something that lets you reroll or replace the d20
    replaces "only one die, not both. You choose which one."

    So the pair is individually addressable and the unused die is not spent. Recording
    only `used` would foreclose every reroll shape in the inventory (#78). This guards the
    record rather than the arithmetic, which is why it is separate from the tests above.
    """
    result = resolve(check(has_advantage=True), seed=11)
    assert len(result.dice) == 2
    assert result.used in result.dice

    remaining = list(result.dice)
    remaining.remove(result.used)
    assert remaining == [min(result.dice)], "the die that lost is still on the record"

    # And it is a real second die, not a copy of the one that counted. A pair that always
    # agreed would satisfy every assertion above while making a reroll meaningless.
    assert any(len(set(resolve(check(has_advantage=True), seed=s).dice)) == 2 for s in range(50))
