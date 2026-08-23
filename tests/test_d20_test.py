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
    ADJUSTMENT_OFFSET,
    ADVANTAGE_VERIFICATION,
    CRITICAL_VERIFICATION,
    DAMAGE_OFFSET,
    DIE_SIDES,
    MAX_ADJUSTMENT_DICE,
    REPLACEMENT_OFFSET,
    REROLL_VERIFICATION,
    Adjustment,
    Advantage,
    Critical,
    D20Test,
    Modifier,
    TestKind,
    adjust_roll,
    die,
    override_to_success,
    passive_score,
    replace_die,
    resolve,
    roll,
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
    only `used` would foreclose every reroll shape in the inventory. `replace_die` is what
    now acts on this (#78), and the tests for it are below; this one guards the record it
    depends on, which is why it stays separate from the arithmetic tests above.
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


# --- Replacing one die of a pair (#78) ---------------------------------------------


def test_one_named_die_of_a_pair_is_replaced_and_the_other_is_left_alone() -> None:
    """p. 8, Interactions with Rerolls: "only one die, not both. You choose which one."

    The caller names the position; the engine supplies what it became. A seam that
    replaced the pair, or that let the caller hand in a value, would give away R4 in the
    one place the document is most explicit about the choice being the holder's.
    """
    rolled = resolve(check(has_advantage=True), seed=11)
    before = rolled.dice

    for position in (0, 1):
        after = replace_die(rolled, position=position, source="Heroic Inspiration")
        assert len(after.dice) == len(before)
        untouched = 1 - position
        assert after.dice[untouched] == before[untouched], "the other die was not the one chosen"
        assert (
            after.dice[position] != before[position]
            or after.replacements[0].value == before[position]
        ), "the replaced die is whatever the engine rolled, including the same face"


def test_the_record_shows_the_original_pair_which_die_moved_and_what_replaced_it() -> None:
    """R5: the Ruling shows the arithmetic. A reroll that erased what it replaced would
    assert its outcome, which is the failure this whole engine exists to remove."""
    rolled = resolve(check(has_advantage=True), seed=7)
    after = replace_die(rolled, position=0, source="Halfling Luck")

    assert after.original_dice == rolled.dice, "the pair as first rolled is still recoverable"
    assert len(after.replacements) == 1

    record = after.replacements[0]
    assert record.position == 0
    assert record.original == rolled.dice[0]
    assert record.value == after.dice[0]
    assert record.value in record.dice, "the value that counted came from the dice recorded"
    assert record.source == "Halfling Luck"


def test_a_replacement_names_what_caused_it() -> None:
    rolled = resolve(check(has_advantage=True), seed=3)
    with pytest.raises(ValueError, match="names what replaced the die"):
        replace_die(rolled, position=0, source="")


def test_replacing_a_die_that_does_not_exist_is_refused() -> None:
    """A plain roll has one die. "You choose which one" presumes the die exists."""
    plain = resolve(check(), seed=3)
    assert len(plain.dice) == 1
    with pytest.raises(ValueError, match="no die at position 1"):
        replace_die(plain, position=1, source="Heroic Inspiration")


def test_the_new_roll_is_binding_rather_than_the_better_of_the_two() -> None:
    """p. 183 Heroic Inspiration and p. 86 Halfling Luck both say "you must use the new
    roll". A reroll that kept the higher of old and new would be a strictly better rule
    than the document's, and would pass any test that only checked the total went up.

    Proven on a seed where the replacement is *worse* than what it replaced.
    """
    worsened = [
        (seed, before, after)
        for seed in range(200)
        for before in [resolve(check(has_advantage=True), seed=seed)]
        for after in [replace_die(before, position=0, source="Heroic Inspiration")]
        if after.replacements[0].value < after.replacements[0].original
    ]
    assert worsened, "no seed in range produced a worse replacement; the test proves nothing"

    after = worsened[0][2]
    record = after.replacements[0]
    assert after.dice[0] == record.value, "the new die stands even though it is worse"
    assert after.dice[0] < record.original
    assert after.used == max(after.dice), "advantage still picks from the pair as it now stands"


def test_the_advantage_rule_reapplies_to_the_pair_as_it_now_stands() -> None:
    """The replacement does not change whether the *test* had advantage — it changes one
    die. The higher-of-two rule then runs again over the new pair."""
    for seed in range(60):
        rolled = resolve(check(has_advantage=True), seed=seed)
        after = replace_die(rolled, position=0, source="Heroic Inspiration")
        assert after.used == max(after.dice)
        assert after.total == after.used + after.modifier_total
        assert after.succeeded == (after.total >= after.target)

        lowered = resolve(check(has_disadvantage=True), seed=seed)
        after_low = replace_die(lowered, position=1, source="Heroic Inspiration")
        assert after_low.used == min(after_low.dice)


def test_a_forced_reroll_can_itself_carry_advantage_or_disadvantage() -> None:
    """p. 175, Wish: "You can force the reroll to be made with Advantage or Disadvantage."

    A seam returning a single substitute value cannot express this, which is why the
    replacement records dice of its own rather than one face.
    """
    rolled = resolve(check(has_advantage=True), seed=5)

    plain = replace_die(rolled, position=0, source="Wish")
    assert len(plain.replacements[0].dice) == 1
    assert plain.replacements[0].effective is Advantage.NONE

    better = replace_die(rolled, position=0, source="Wish", with_advantage=True)
    assert len(better.replacements[0].dice) == 2
    assert better.replacements[0].effective is Advantage.ADVANTAGE
    assert better.replacements[0].value == max(better.replacements[0].dice)

    worse = replace_die(rolled, position=0, source="Wish", with_disadvantage=True)
    assert worse.replacements[0].effective is Advantage.DISADVANTAGE
    assert worse.replacements[0].value == min(worse.replacements[0].dice)


def test_a_forced_reroll_with_both_states_cancels_by_the_same_rule_as_the_roll() -> None:
    """One cancellation rule, not two. The count-versus-presence question #52 settled
    would otherwise get a second chance to be answered differently here."""
    rolled = resolve(check(has_advantage=True), seed=5)
    cancelled = replace_die(
        rolled, position=0, source="Wish", with_advantage=True, with_disadvantage=True
    )
    assert cancelled.replacements[0].effective is Advantage.NONE
    assert len(cancelled.replacements[0].dice) == 1

    plain = replace_die(rolled, position=0, source="Wish")
    assert cancelled.replacements[0].dice == plain.replacements[0].dice


def test_a_rerolled_result_replays_from_the_original_seed() -> None:
    """R28. The replacement is drawn from the roll's own seed, so seed plus the record of
    what was replaced is enough to reconstruct the outcome."""
    test = check(has_advantage=True, modifiers=(STRENGTH,))
    first = replace_die(resolve(test, seed=4242), position=1, source="Heroic Inspiration")
    again = replace_die(resolve(test, seed=4242), position=1, source="Heroic Inspiration")

    assert first == again
    assert first.dice == again.dice
    assert first.replacements == again.replacements
    assert first.total == again.total


def test_replay_from_a_fresh_seed_does_not_reproduce_the_reroll() -> None:
    """The failure this guards is quiet: a replacement drawn from a *new* seed would
    reproduce the roll and not the reroll, so replay would look like it worked.

    If `replace_die` ever stops deriving from `result.seed`, this goes red.
    """
    test = check(has_advantage=True)
    rolled = resolve(test, seed=4242)
    faithful = replace_die(rolled, position=0, source="Heroic Inspiration")

    from_elsewhere = [
        replace_die(resolve(test, seed=other), position=0, source="Heroic Inspiration")
        for other in range(4200, 4300)
        if other != 4242
    ]
    assert any(
        other.replacements[0].value != faithful.replacements[0].value for other in from_elsewhere
    ), "a different seed must be able to produce a different reroll"


def test_a_replacement_draws_from_its_own_band_of_the_seed_index_space() -> None:
    """The index space is banded — d20 at 0-1, damage from 100, replacements from 200 — so
    a reroll cannot land on the die it is replacing, or on a damage die of the same roll.

    A collision would not raise. It would produce a reroll that agreed with the original
    suspiciously often, which is the kind of defect nobody finds by inspection. So this
    pins the exact index each replacement draws from rather than asserting a property that
    a colliding implementation would also satisfy.
    """
    seed = 99
    stride = 2

    # The bands must be ordered, and this is asserted against the *constants* rather than
    # against values derived from them. An expectation computed from REPLACEMENT_OFFSET
    # moves when REPLACEMENT_OFFSET moves, so it cannot notice the offset being wrong —
    # a mutation setting it to 0 survived an earlier version of this test for exactly that
    # reason, and this is the assertion that catches it.
    assert DAMAGE_OFFSET > 1, "the d20 occupies indices 0-1; damage must start above them"
    assert REPLACEMENT_OFFSET > DAMAGE_OFFSET, "replacements must start above the damage band"

    for generation, position in ((1, 0), (1, 1), (2, 0), (3, 1)):
        index = REPLACEMENT_OFFSET + generation * stride * 2 + position * stride
        assert index >= REPLACEMENT_OFFSET, "a replacement stays inside its own band"
        assert index not in (0, 1), "a replacement must not reuse a d20 index"
        assert not DAMAGE_OFFSET <= index < REPLACEMENT_OFFSET, "nor a damage index"

    rolled = resolve(check(has_advantage=True), seed=seed)

    first = replace_die(rolled, position=1, source="Heroic Inspiration")
    assert first.replacements[0].value == die(seed, REPLACEMENT_OFFSET + 1 * 4 + 1 * 2)

    second = replace_die(first, position=0, source="Wish", with_advantage=True)
    base = REPLACEMENT_OFFSET + 2 * 4 + 0 * 2
    assert second.replacements[1].dice == (die(seed, base), die(seed, base + 1))

    # And the bands really are disjoint from what this same seed produces elsewhere.
    damage = roll(seed, count=40, sides=DIE_SIDES, offset=DAMAGE_OFFSET)
    assert len(damage) == 40
    assert first.replacements[0].value == die(seed, REPLACEMENT_OFFSET + 6), "unchanged by damage"


def test_replacements_accumulate_in_order_and_each_is_recoverable() -> None:
    """Halfling Luck can fire, and Heroic Inspiration can then be spent on the same roll.
    The lineage is a sequence, not a single slot."""
    rolled = resolve(check(has_advantage=True), seed=13)
    once = replace_die(rolled, position=0, source="Halfling Luck")
    twice = replace_die(once, position=1, source="Heroic Inspiration")

    assert [r.source for r in twice.replacements] == ["Halfling Luck", "Heroic Inspiration"]
    assert twice.original_dice == rolled.dice, "walking back both replacements gives the first pair"
    assert twice.replacements[0].original == rolled.dice[0]
    assert twice.replacements[1].original == once.dice[1]


def test_the_documents_worked_reroll_example_is_expressible() -> None:
    """p. 8: with Advantage or Disadvantage, rolling a 3 and an 18, Heroic Inspiration
    rerolls "one of those dice, not both of them".

    The engine rolls, so the pair is not dialled in — this asserts the *shape* the example
    requires: a two-die result where replacing one leaves the other exactly as it was.
    """
    rolled = resolve(check(has_advantage=True), seed=11)
    assert len(rolled.dice) == 2

    after = replace_die(rolled, position=0, source="Heroic Inspiration")
    assert after.dice[1] == rolled.dice[1], "the die not chosen is untouched"
    assert len(after.replacements) == 1, "exactly one die moved"
    assert after.original_dice == rolled.dice


def test_the_reroll_semantics_carry_their_own_verified_citation() -> None:
    """R31, and a *separate* citation from the advantage one on purpose.

    The reroll rules rest on different sentences in different sections. Folding them into
    `ADVANTAGE_VERIFICATION` would let a revision reword one set while the other's date
    went on vouching for both.
    """
    assert REROLL_VERIFICATION.state is VerificationState.VERIFIED
    assert REROLL_VERIFICATION.reference is not None
    assert REROLL_VERIFICATION.reference != ADVANTAGE_VERIFICATION.reference
    assert "SRD v5.2.1" in REROLL_VERIFICATION.reference
    for cited in ("p. 8", "p. 183", "p. 86", "p. 175"):
        assert cited in REROLL_VERIFICATION.reference, f"{cited} is a page the seam rests on"


def test_an_unrerolled_result_carries_an_empty_lineage() -> None:
    """The common case stays clean: nothing to read, and `original_dice` is the pair."""
    rolled = resolve(check(has_advantage=True), seed=8)
    assert rolled.replacements == ()
    assert rolled.original_dice == rolled.dice


# --- What a natural 20 or 1 means (#15) ----------------------------------------------


def attack(target: int = 15, **overrides: object) -> D20Test:
    fields: dict[str, object] = {
        "kind": TestKind.ATTACK,
        "target": target,
        "target_basis": "armour class 15, worn by a bandit",
    }
    fields.update(overrides)
    return D20Test(**fields)  # type: ignore[arg-type]


def _seed_where(test: D20Test, face: int, limit: int = 4000) -> int:
    """The first seed whose *used* die is `face`. Searched, never dialled in — R4."""
    for seed in range(limit):
        if resolve(test, seed=seed).used == face:
            return seed
    raise AssertionError(f"no seed under {limit} produced a used die of {face}")


def test_a_natural_20_hits_however_bad_the_arithmetic_is() -> None:
    """p. 7: the attack "hits regardless of any modifiers or the target's AC".

    Set against an AC no total could reach and a penalty that makes it worse. If the
    implementation ever falls back to comparing the total, this goes red.
    """
    test = attack(target=99, modifiers=(Modifier(source="curse", value=-20),))
    result = resolve(test, seed=_seed_where(test, DIE_SIDES))

    assert result.critical is Critical.HIT
    assert result.succeeded, "a natural 20 hits regardless of any modifiers or the target's AC"
    assert result.total < result.target, "and it hit while falling short — that is the rule"


def test_a_natural_1_misses_however_good_the_arithmetic_is() -> None:
    """p. 7, the same rule from the other end: the attack "misses regardless"."""
    test = attack(target=2, modifiers=(Modifier(source="blessed", value=20),))
    result = resolve(test, seed=_seed_where(test, 1))

    assert result.critical is Critical.MISS
    assert not result.succeeded
    assert result.total >= result.target, "it missed while beating the target — that is the rule"


def test_checks_and_saves_have_no_criticals() -> None:
    """The document gives "Rolling 20 or 1" for an **attack roll** and never extends it to
    ability checks or saving throws.

    This is the rule as written rather than the one most tables play, so it is exactly the
    kind of thing that gets 'fixed' by someone confident from memory. R31: a widely-known
    5e behaviour that the SRD does not state is still a guess.
    """
    for kind, basis in ((TestKind.CHECK, "difficulty class"), (TestKind.SAVE, "save DC")):
        test = D20Test(kind=kind, target=99, target_basis=basis)
        result = resolve(test, seed=_seed_where(test, DIE_SIDES))
        assert result.used == DIE_SIDES
        assert result.critical is Critical.NONE
        assert not result.succeeded, "a natural 20 on a check is a 20, and 20 does not beat 99"


def test_the_critical_is_read_off_the_used_die_not_the_pair() -> None:
    """With Disadvantage on a 20 and a 3 the roll is a 3. A 20 that was never used is a 20
    nobody rolled for this test, and treating it as a critical would invent a hit."""
    unlucky = [
        (seed, r)
        for seed in range(3000)
        for r in [resolve(attack(has_disadvantage=True), seed=seed)]
        if DIE_SIDES in r.dice and r.used != DIE_SIDES
    ]
    assert unlucky, "no seed rolled a 20 that disadvantage discarded; the test proves nothing"

    _, result = unlucky[0]
    assert result.critical is Critical.NONE
    assert result.succeeded == (result.total >= result.target)


def test_replacing_a_die_can_create_or_destroy_a_critical() -> None:
    """The critical follows the die that counts, so a reroll has to recompute it. A
    replacement that left `critical` stale would report a hit the dice no longer support.
    """
    made = next(
        (
            after
            for seed in range(3000)
            for before in [resolve(attack(target=99), seed=seed)]
            if before.critical is Critical.NONE
            for after in [replace_die(before, position=0, source="Heroic Inspiration")]
            if after.critical is Critical.HIT
        ),
        None,
    )
    assert made is not None, "no seed turned a plain attack into a critical"
    assert made.succeeded, "the replacement created the critical, so the attack now hits"

    lost = next(
        (
            after
            for seed in range(3000)
            for before in [resolve(attack(target=99), seed=seed)]
            if before.critical is Critical.HIT
            for after in [replace_die(before, position=0, source="Heroic Inspiration")]
            if after.critical is not Critical.HIT
        ),
        None,
    )
    assert lost is not None, "no seed replaced a natural 20 away"
    assert not lost.succeeded, "the critical went with the die; the attack no longer hits"


# --- A score used without rolling ----------------------------------------------------


def test_passive_perception_is_ten_plus_the_bonus() -> None:
    """p. 186, including the document's own worked example: a level 1 character with
    Wisdom 15 and Perception proficiency has a Passive Perception of 14 (10 + 2 + 2)."""
    assert passive_score(4) == 14
    assert passive_score(0) == 10
    assert passive_score(-1) == 9


def test_advantage_and_disadvantage_shift_a_passive_score_by_five() -> None:
    assert passive_score(4, has_advantage=True) == 19
    assert passive_score(4, has_disadvantage=True) == 9


def test_a_passive_score_cancels_by_the_same_rule_as_a_roll() -> None:
    """Holding both is the cancellation rule, not +5 and -5 arriving in a lucky order —
    they happen to reach the same number here, which is exactly why it needs saying.
    """
    assert passive_score(4, has_advantage=True, has_disadvantage=True) == passive_score(4)


def test_the_critical_semantics_carry_their_own_verified_citation() -> None:
    """R31, and a third citation rather than a third clause on an existing one: these
    rules sit in different sections from the advantage and reroll ones."""
    assert CRITICAL_VERIFICATION.state is VerificationState.VERIFIED
    assert CRITICAL_VERIFICATION.reference is not None
    assert CRITICAL_VERIFICATION.reference not in (
        ADVANTAGE_VERIFICATION.reference,
        REROLL_VERIFICATION.reference,
    )
    for cited in ("p. 7", "p. 179", "p. 186"):
        assert cited in CRITICAL_VERIFICATION.reference


# --- Dice applied after the roll, and failures overridden (#15) ----------------------


def test_a_die_applied_after_the_roll_can_turn_a_failure_into_a_success() -> None:
    """p. 32, Bardic Inspiration: when a creature "fails a D20 Test, the creature can roll
    the Bardic Inspiration die and add the number rolled to the d20, potentially turning
    the failure into a success"."""
    failed = next(
        r
        for seed in range(2000)
        for r in [resolve(check(target=15), seed=seed)]
        if not r.succeeded and r.total >= 9
    )
    adjusted = adjust_roll(failed, count=1, sides=6, source="Bardic Inspiration")

    assert adjusted.total > failed.total
    assert adjusted.adjustments[0].source == "Bardic Inspiration"
    assert adjusted.adjustments[0].value == sum(adjusted.adjustments[0].dice)
    assert adjusted.succeeded == (adjusted.total >= adjusted.target)


def test_the_same_shape_applies_as_a_penalty() -> None:
    """p. 88, Boon of Fate: "apply the total rolled as a bonus **or penalty** to the d20
    roll". A caller passing a negative count could not express this, which is why the
    direction is its own flag."""
    rolled = resolve(check(target=5), seed=11)
    worse = adjust_roll(rolled, count=2, sides=4, source="Boon of Fate", penalty=True)

    assert worse.total == rolled.total - worse.adjustments[0].value
    assert worse.adjustments[0].penalty
    assert worse.adjustments[0].applied == -worse.adjustments[0].value


def test_a_die_applied_to_a_natural_1_still_misses() -> None:
    """p. 7: a natural 1 on an attack misses "regardless of any modifiers", and a die
    applied afterwards is a modifier. The total rises and the attack does not land.

    This is the clause doing real work rather than decorating a docstring — an
    implementation that recomputed `total >= target` would quietly turn it into a hit.
    """
    missed = resolve(attack(target=2), seed=_seed_where(attack(target=2), 1))
    assert missed.critical is Critical.MISS and not missed.succeeded

    adjusted = adjust_roll(missed, count=8, sides=6, source="Bardic Inspiration")
    assert adjusted.total > adjusted.target
    assert not adjusted.succeeded, "a natural 1 misses regardless of any modifiers"


def test_applied_dice_come_from_the_rolls_own_seed_and_their_own_band() -> None:
    """Replay reproduces the adjustment, and it cannot land on a die the seed already
    produced — the bands are stated in one place in `core.d20`."""
    rolled = resolve(check(), seed=4242)
    first = adjust_roll(rolled, count=2, sides=4, source="Boon of Fate")
    again = adjust_roll(resolve(check(), seed=4242), count=2, sides=4, source="Boon of Fate")
    assert first == again

    base = ADJUSTMENT_OFFSET
    assert first.adjustments[0].dice == (die(4242, base, 4), die(4242, base + 1, 4))
    assert ADJUSTMENT_OFFSET > REPLACEMENT_OFFSET > DAMAGE_OFFSET > 1


def test_adjustments_accumulate_and_each_draws_from_its_own_block() -> None:
    rolled = resolve(check(), seed=8)
    once = adjust_roll(rolled, count=1, sides=6, source="Bardic Inspiration")
    twice = adjust_roll(once, count=2, sides=4, source="Boon of Fate")

    assert [a.source for a in twice.adjustments] == ["Bardic Inspiration", "Boon of Fate"]
    assert twice.total == rolled.total + twice.adjustments[0].applied + twice.adjustments[1].applied
    assert twice.adjustments[1].dice[0] == die(8, ADJUSTMENT_OFFSET + MAX_ADJUSTMENT_DICE, 4)


def test_an_adjustment_names_its_source_and_rolls_a_sane_number_of_dice() -> None:
    rolled = resolve(check(), seed=8)
    with pytest.raises(ValueError, match="names its source"):
        adjust_roll(rolled, count=1, sides=6, source="")
    with pytest.raises(ValueError, match="between 1 and"):
        adjust_roll(rolled, count=0, sides=6, source="Bardic Inspiration")
    with pytest.raises(ValueError, match="between 1 and"):
        adjust_roll(rolled, count=MAX_ADJUSTMENT_DICE + 1, sides=6, source="Bardic Inspiration")


def test_a_failed_test_can_be_overridden_to_a_success() -> None:
    """p. 88 Peerless Aim — "When you miss with an attack roll, you can hit instead" — and
    p. 258 Legendary Resistance — "If the aboleth fails a saving throw, it can choose to
    succeed instead". One shape since decision 0013; only the test kind differs.
    """
    for test in (attack(target=99), check(target=99)):
        failed = resolve(test, seed=3)
        assert not failed.succeeded

        overridden = override_to_success(failed, source="Peerless Aim")
        assert overridden.succeeded
        assert overridden.override is not None
        assert overridden.override.source == "Peerless Aim"
        assert overridden.total == failed.total, "no die moved; only the outcome did"


def test_overriding_a_test_that_already_succeeded_is_refused() -> None:
    """Both features are written as a response to failing. Recording one against a success
    would put a use of the feature in the ledger that the rules never called for."""
    succeeded = resolve(check(target=2), seed=3)
    assert succeeded.succeeded
    with pytest.raises(ValueError, match="only a failed test"):
        override_to_success(succeeded, source="Peerless Aim")


def test_an_override_outranks_a_later_penalty() -> None:
    """An override is a decision to succeed and nothing later un-makes it. A penalty
    applied afterwards lowers the total and the test still succeeded."""
    failed = resolve(check(target=99), seed=3)
    overridden = override_to_success(failed, source="Legendary Resistance")
    worse = adjust_roll(overridden, count=2, sides=4, source="Boon of Fate", penalty=True)

    assert worse.total < overridden.total
    assert worse.succeeded


def test_an_override_names_what_granted_it() -> None:
    failed = resolve(check(target=99), seed=3)
    with pytest.raises(ValueError, match="names what granted it"):
        override_to_success(failed, source="")


def test_the_derivation_shows_what_happened_after_the_roll() -> None:
    """R5: the Ruling shows the arithmetic. A total that silently grew by 4 would be a
    number the record cannot explain."""
    failed = resolve(check(target=99), seed=3)
    adjusted = adjust_roll(failed, count=1, sides=6, source="Bardic Inspiration")
    assert "(Bardic Inspiration)" in adjusted.derivation()

    overridden = override_to_success(failed, source="Peerless Aim")
    assert "overridden to a success by Peerless Aim" in overridden.derivation()


def test_an_unadjusted_result_carries_an_empty_record() -> None:
    rolled = resolve(check(), seed=8)
    assert rolled.adjustments == ()
    assert rolled.override is None
    assert Adjustment(dice=(3,), value=3, penalty=False, source="x").applied == 3
