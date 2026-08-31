"""The Wisdom (Perception) check that finally reads obscurement (#138).

`core.sight` has been able to say a space is Lightly or Heavily Obscured since #150 filled
its tables, and **nothing read the answer**. p. 184's Disadvantage was produced by nothing,
so by the sweep's own standard — *a shape is claimed when the engine produces the consequence
its entry states* — `lightly-obscured` and `dim-light` had not resolved, while the table that
decides them was complete.

Three sentences compose here, and the third is the one an implementer drops:

* p. 184: "You have Disadvantage on Wisdom (Perception) checks to see something in a Lightly
  Obscured space."
* p. 182: "You have the Blinded condition **while trying to see something** in a Heavily
  Obscured space."
* p. 177: "You can't see and **automatically fail any ability check that requires sight**."

Reading only the first two leaves Heavily Obscured as *a worse Disadvantage*, which is
plausible and is not what the document says. It is an automatic failure, and the sentence
that makes it one is in Blinded's entry rather than in the obscurement's.
"""

from __future__ import annotations

from dataclasses import replace

from srd_rules_engine.core import (
    Combatant,
    EncounterState,
    Skill,
    perception_resolver,
    perception_rule,
)
from srd_rules_engine.core.adjudicate import Declaration, Effect, EffectKind, Intent
from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.d20 import Advantage, passive_score
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.rules import VerificationState
from srd_rules_engine.core.sight import Lighting, LightLevel, Senses
from srd_rules_engine.core.skills import SKILL_ABILITY

FAR = Position(10, 0, 0)
NO_SENSES = Senses()
NOTHING_HELD = Conditions()


def looking(
    *,
    light: LightLevel | None = LightLevel.BRIGHT,
    senses: Senses = NO_SENSES,
    conditions: Conditions = NOTHING_HELD,
    proficient: bool = True,
    wisdom: int = 15,
) -> EncounterState:
    """An observer at the origin and a target ten feet away, in a stated light.

    Wisdom 15 with proficiency is p. 186's own worked example, so the bonus this produces is
    checkable against a printed number rather than against arithmetic done here.
    """
    observer = Combatant(
        id="pc",
        name="Pc",
        hit_points=10,
        max_hit_points=10,
        armour_class=12,
        abilities={"wis": wisdom},
        proficiency_bonus=2,
        position=Position(0, 0, 0),
        skills=frozenset({Skill.PERCEPTION}) if proficient else frozenset(),
        senses=senses,
        conditions=conditions,
    )
    target = Combatant(
        id="imp",
        name="Imp",
        hit_points=10,
        max_hit_points=10,
        armour_class=12,
        abilities={"dex": 14},
        proficiency_bonus=2,
        position=FAR,
    )
    state = EncounterState.new([observer, target])
    return replace(state, lighting=Lighting(ambient=light))


# --- The skill, and what proficiency adds (p. 188) --------------------------------------


def test_the_documents_own_passive_perception_example() -> None:
    """p. 186: "a level 1 character with a Wisdom of 15 and proficiency in Perception has a
    Passive Perception of 14 (10 + 2 + 2)".

    Checked through `check_bonus` and `passive_score` together, because the printed number
    is the sum of both and either alone could be wrong in a way the other hid.
    """
    observer = looking().combatant("pc")
    assert observer.check_bonus(Skill.PERCEPTION) == 4, "+2 Wisdom, +2 proficiency"
    assert passive_score(observer.check_bonus(Skill.PERCEPTION)) == 14

    # "If that character has Advantage on Wisdom (Perception) checks, the score becomes 19."
    assert passive_score(observer.check_bonus(Skill.PERCEPTION), has_advantage=True) == 19


def test_proficiency_is_added_only_when_the_skill_is_held() -> None:
    """p. 188 states the whole rule: "**If** you have proficiency in a skill, you can add
    your Proficiency Bonus." Without it the check is the bare ability modifier."""
    assert looking(proficient=False).combatant("pc").check_bonus(Skill.PERCEPTION) == 2
    assert looking(proficient=True).combatant("pc").check_bonus(Skill.PERCEPTION) == 4


def test_the_ability_is_the_skills_own_and_not_the_callers() -> None:
    """p. 9's table pairs each skill with one ability, and the pairing is the mechanical
    half: a Wisdom (Perception) check is a Wisdom check whoever rolls it. A creature with a
    towering Strength and a dismal Wisdom is still bad at noticing things."""
    assert SKILL_ABILITY[Skill.PERCEPTION] == "wis"
    assert SKILL_ABILITY[Skill.ATHLETICS] == "str"
    assert SKILL_ABILITY[Skill.STEALTH] == "dex"

    brawny = looking(wisdom=6)
    observer = replace(brawny.combatant("pc"), abilities={"wis": 6, "str": 20})
    assert observer.check_bonus(Skill.PERCEPTION) == 0, "-2 Wisdom, +2 proficiency"


def test_there_are_eighteen_skills_and_each_has_an_ability() -> None:
    """p. 9's table, closed like `DamageType`. Constitution is associated with none of
    them, which is the document's shape rather than an omission here."""
    assert len(Skill) == 18
    assert set(SKILL_ABILITY) == set(Skill)
    assert "con" not in set(SKILL_ABILITY.values())


# --- What obscurement does to the check (pp. 184, 182, 177) -----------------------------


def test_bright_light_obscures_nothing() -> None:
    check = looking(light=LightLevel.BRIGHT).perception_of("pc", "imp")
    assert check.advantage is Advantage.NONE
    assert check.is_rolled


def test_dim_light_gives_disadvantage() -> None:
    """p. 181 says Dim Light **is** Lightly Obscured, and p. 184 says what that costs. The
    two sentences meeting here is the whole of #138's keystone — before this, the first was
    computed and the second was produced by nothing."""
    check = looking(light=LightLevel.DIM).perception_of("pc", "imp")
    assert check.advantage is Advantage.DISADVANTAGE
    assert check.is_rolled
    assert "p. 184" in check.because


def test_darkness_fails_the_check_outright_rather_than_hindering_it() -> None:
    """The sentence an implementer drops. p. 182 says a Heavily Obscured space gives the
    **Blinded condition** while trying to see something in it — and p. 177 says a Blinded
    creature "automatically fail[s] any ability check that requires sight".

    Reading only p. 182 leaves this as a second Disadvantage, which is plausible, believable
    in play, and not what the document says.
    """
    check = looking(light=LightLevel.DARKNESS).perception_of("pc", "imp")
    assert check.automatic_failure
    assert not check.is_rolled
    assert "p. 182" in check.because and "p. 177" in check.because


def test_an_unstated_light_is_not_a_penalty() -> None:
    """0025 clause 2 refuses to assume daylight. Assuming Dim Light instead would be the
    same invention pointing the other way, so an unstated light obscures nothing and the
    reason says which it is."""
    check = looking(light=None).perception_of("pc", "imp")
    assert check.advantage is Advantage.NONE
    assert check.is_rolled
    assert "nobody has stated the light" in check.because


# --- The senses, which is where the whole chain pays off --------------------------------


def test_darkvision_reads_dim_light_as_bright_and_removes_the_penalty() -> None:
    """p. 180: Darkvision sees Dim Light "as if it were Bright Light". So the space is not
    Lightly Obscured *for this creature*, and p. 184 never applies."""
    check = looking(light=LightLevel.DIM, senses=Senses(darkvision=60)).perception_of("pc", "imp")
    assert check.advantage is Advantage.NONE


def test_darkvision_turns_an_automatic_failure_into_a_disadvantage() -> None:
    """The sharpest demonstration that the chain is a chain. p. 180 reads Darkness "as if it
    were Dim Light", p. 181 makes Dim Light Lightly Obscured, and p. 184 makes that
    Disadvantage — so three entries in sequence turn a check that could not be rolled into
    one that can. No single sentence says this."""
    dark = looking(light=LightLevel.DARKNESS)
    assert dark.perception_of("pc", "imp").automatic_failure

    seeing = looking(light=LightLevel.DARKNESS, senses=Senses(darkvision=60))
    check = seeing.perception_of("pc", "imp")
    assert not check.automatic_failure
    assert check.advantage is Advantage.DISADVANTAGE


def test_darkvision_beyond_its_range_does_not_help() -> None:
    """ "within a specified range" (p. 180). A creature with Darkvision 5 looking ten feet
    into Darkness is as blind as one with none."""
    check = looking(light=LightLevel.DARKNESS, senses=Senses(darkvision=5)).perception_of(
        "pc", "imp"
    )
    assert check.automatic_failure


def test_blindsight_ignores_the_light_entirely() -> None:
    """p. 177: Blindsight sees "without relying on physical sight ... even if you have the
    Blinded condition or are in Darkness". It is an exemption from the chain rather than a
    position along it, so there is no penalty to shift — charging one would invent a cost
    the document does not."""
    check = looking(light=LightLevel.DARKNESS, senses=Senses(blindsight=60)).perception_of(
        "pc", "imp"
    )
    assert check.advantage is Advantage.NONE
    assert check.is_rolled


# --- Conditions, and the flags that had no consumer -------------------------------------


def test_a_blinded_observer_fails_whatever_the_light_is() -> None:
    """p. 177 directly, in Bright Light so nothing else could explain it.

    `auto_fail_checks_requiring_sight` has been set on Blinded since #18 and **nothing ever
    read it** — this is its first consumer.
    """
    blind = looking(conditions=Conditions(held=frozenset({Condition.BLINDED})))
    check = blind.perception_of("pc", "imp")
    assert check.automatic_failure
    assert "p. 177" in check.because


def test_poisoned_gives_disadvantage_on_a_check_that_has_nothing_to_do_with_sight() -> None:
    """p. 186 gives Poisoned "Disadvantage on attack rolls and ability checks", flat. Like
    Blinded's flag, `own_ability_checks` was transcribed correctly and read by nothing.

    In Bright Light, so the penalty cannot be coming from obscurement — and the reason says
    a condition rather than the light, because a message naming the light here would send a
    reader looking for a torch.
    """
    check = looking(conditions=Conditions(held=frozenset({Condition.POISONED}))).perception_of(
        "pc", "imp"
    )
    assert check.advantage is Advantage.DISADVANTAGE
    assert "condition" in check.because
    assert "Lightly Obscured" not in check.because


def test_frightened_carries_its_line_of_sight_qualifier_here_too() -> None:
    """p. 182 gives Frightened's Disadvantage "while the source of fear is within line of
    sight", and #192 made that askable. The qualifier reaches ability checks by the same
    route it reaches attack rolls, rather than being dropped because this is a new caller."""
    afraid = Conditions(
        held=frozenset({Condition.FRIGHTENED}),
        sources={Condition.FRIGHTENED: frozenset({"imp"})},
    )
    assert looking(conditions=afraid).perception_of("pc", "imp").advantage is (
        Advantage.DISADVANTAGE
    )


# --- Through adjudication, because a value nothing rolls has resolved nothing ------------


def declare() -> Declaration:
    return Declaration(
        actor_id="pc", intent=Intent(improvised=True, label="look"), rule_id=perception_rule().id
    )


def test_the_check_reaches_a_d20_test_with_the_disadvantage_applied() -> None:
    """The point of building a resolver rather than only a read: p. 184's Disadvantage has
    to reach a die, or it is a value nothing consumes — which is the state that kept
    `lightly-obscured` unclaimed in the first place."""
    state = looking(light=LightLevel.DIM)
    resolve = perception_resolver("imp", dc=15, basis="an invented difficulty, for this test")
    proposal = resolve(state=state, declaration=declare(), facts={})

    assert proposal.test is not None
    assert proposal.test.has_disadvantage
    assert not proposal.test.has_advantage
    assert proposal.test.target == 15
    assert [m.value for m in proposal.test.modifiers] == [4], "p. 186's +2 Wisdom, +2 proficiency"


def test_a_check_the_rules_have_already_failed_is_recorded_rather_than_refused() -> None:
    """p. 177 settled it, and this records that it did (#224).

    It used to **refuse**, on the reasoning that a testless proposal with no effects is the
    shape `Proposal.__post_init__` rejects. That reasoning had a false step: the guard
    refuses a proposal with no test **and no outcome**, and an effect in `outcome` satisfies
    it. What was missing was an `EffectKind` that changes no state, which `INFLUENCED` had
    already stopped being unthinkable.

    The gain is the **ledger entry**. `perception_of` reported the failure as a read all
    along (R19), and still does — but a session review could not tell "the observer never
    looked" from "the observer looked and the rules failed it", which is the R30 gap #224
    was filed for.
    """
    state = looking(light=LightLevel.DARKNESS)
    resolve = perception_resolver("imp", dc=15, basis="an invented difficulty")

    proposal = resolve(state=state, declaration=declare(), facts={})

    assert proposal.test is None, "the rules settled it, so no die is thrown"
    (effect,) = proposal.outcome
    assert isinstance(effect, Effect)
    assert effect.kind is EffectKind.AUTOMATIC_FAILURE
    assert "automatically fails" in effect.description
    assert any("without a die" in claim for claim in proposal.may_not_claim)


def test_the_automatic_failure_changes_no_state() -> None:
    """The property that made #224 look impossible: a rule decided something, and nothing in
    the encounter moved. `_apply` has no branch for this kind — which is the honest shape
    rather than an omission, and is `INFLUENCED`'s shape exactly."""
    from srd_rules_engine.core.adjudicate import _apply, automatically_failed

    state = looking(light=LightLevel.DARKNESS)
    after, landed, withheld = _apply(
        state, (automatically_failed("watcher", description="p. 177 settled it"),), seed=1
    )

    assert after == state, "nothing moved"
    assert len(landed) == 1, "and it is still recorded as having landed"
    assert withheld == ()


def test_the_difficulty_comes_from_the_caller_and_says_so() -> None:
    """The SRD sets no DC for seeing a creature — p. 187 says only that you "make a Wisdom
    check to discern something that isn't obvious", and against a hider it would be
    contested by Stealth, which is not built. So the difficulty is a closure parameter like
    `falling_resolver`'s distance, and its basis is recorded (R5)."""
    resolve = perception_resolver("imp", dc=12, basis="the imp's Stealth check, supplied")
    proposal = resolve(state=looking(), declaration=declare(), facts={})

    assert proposal.test is not None
    assert proposal.test.target == 12
    assert proposal.test.target_basis == "the imp's Stealth check, supplied"


# --- Provenance --------------------------------------------------------------------------


def test_the_rule_is_verified_and_says_the_packaging_is_this_engines() -> None:
    """R31/R32. Every clause is printed, and the *composition* is not — the document names a
    Search action that may use the skill, not a "perception-check" rule. `RuleProvenance`
    cannot express "composed from printed clauses", so the summary does."""
    rule = perception_rule()
    assert rule.verification is not None
    assert rule.verification.state is VerificationState.VERIFIED
    for cited in ("p. 184", "p. 182", "p. 177", "p. 188", "p. 187", "p. 9"):
        assert cited in (rule.verification.reference or "")
    assert "this engine's, not the document's" in rule.summary
