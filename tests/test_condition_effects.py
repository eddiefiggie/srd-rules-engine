"""A condition reaches state through a ruling, or it does not reach state (#119, R1).

Before `CONDITION_APPLIED` and `CONDITION_ENDED`, the only route a condition had into
`EncounterState` was `with_condition`, called directly by whoever wanted one. That is a
mechanical change with no roll, no seed, no citation and no ledger entry behind it — an
outcome that came into existence outside the one adjudication entry point, which is the
precise thing R1 exists to prevent. Decision 0023 clause 4 named the gap while settling
something else: a save's success had no way to reach `with_condition_ended`.

So these tests are about *route* rather than about what the fifteen conditions do. The
mechanical effects are `tests/test_conditions.py` and the spans are
`tests/test_condition_duration.py`; what is checked here is that the only door into a
condition is a ruling, that the door refuses malformed effects rather than passing them
through, and that the record afterwards says which condition changed.

Two of these guard a hazard rather than a feature:

* **`_apply`'s trailing `else` used to be `DEATH`.** Any effect kind added after it and
  not given a branch became a death, silently. `test_an_unhandled_effect_kind_raises`
  is that branch's alarm, and it is the reason the restructure is not merely tidier.
* **A condition effect's `amount` is 0 and means nothing.** R7 leaves narration to the
  caller, which reads `Effect.amount`; a number riding on a condition would be narrated
  as though it counted. `__post_init__` makes the combination unconstructible.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest

from srd_rules_engine.core import (
    Adjudicator,
    Carriage,
    Carried,
    Combatant,
    Condition,
    Declaration,
    Duration,
    DurationKind,
    EncounterState,
    Intent,
    Item,
    Ledger,
    Proposal,
    Rule,
    RuleProvenance,
    Weapon,
    attack_key,
    condition_applied,
    condition_ended,
    load_fixture_ruleset,
    read,
)
from srd_rules_engine.core.adjudicate import (
    CONDITION_KINDS,
    RULING_VERSION,
    Effect,
    EffectKind,
    When,
    _apply,
)
from srd_rules_engine.core.conditions import EFFECTS
from srd_rules_engine.core.d20 import D20Test, Modifier, TestKind
from srd_rules_engine.core.damage import DamageType, Defences
from srd_rules_engine.core.memory_port import Resolution
from srd_rules_engine.memory.store import JsonMemoryStore

# An encounter-axis span, so `derivation()` has something to say beyond "until removed".
THREE_ROUNDS = Duration(kind=DurationKind.ROUNDS, ends_after_round=3, ends_after_actor_id="pc")


#: Invented, and held: since #258 an attack is offered for a weapon in hand (0040 clause 1).
GRIP = Weapon(id="fixture-grip", damage_dice=1, damage_sides=4, hands_when_held=1)


def encounter() -> EncounterState:
    return EncounterState.new(
        [
            Combatant(
                id="pc",
                name="Pc",
                hit_points=20,
                max_hit_points=20,
                armour_class=13,
                abilities={"str": 16, "dex": 14},
                proficiency_bonus=2,
                hands=2,
                equipment=(Carried(GRIP, Carriage.HELD),),
                weapon_proficiencies=frozenset({GRIP.id}),
            ),
            Combatant(
                id="troll",
                name="Troll",
                hit_points=40,
                max_hit_points=40,
                armour_class=13,
                abilities={"str": 18, "dex": 13},
                proficiency_bonus=2,
            ),
        ]
    )


def apply_one(state: EncounterState, effect: Effect) -> EncounterState:
    after, _, _withheld = _apply(state, (effect,), seed=1)
    return after


# --- The type refuses what a reader could not read correctly ---------------------------


def test_a_condition_effect_names_which_condition() -> None:
    """The failure this prevents is a record saying a condition changed and not which."""
    with pytest.raises(ValueError, match="names which condition"):
        Effect(
            kind=EffectKind.CONDITION_APPLIED,
            target_id="troll",
            amount=0,
            description="something happened to something",
        )


def test_a_condition_ended_effect_also_names_one() -> None:
    with pytest.raises(ValueError, match="names which condition"):
        Effect(
            kind=EffectKind.CONDITION_ENDED,
            target_id="troll",
            amount=0,
            description="something stopped",
        )


def test_a_damage_effect_may_not_smuggle_a_condition() -> None:
    """Otherwise a reader has to guess whether a condition riding on another kind was
    meant to take effect — and `_apply` would not have applied it, so the record and the
    state would disagree."""
    with pytest.raises(ValueError, match="does not carry a condition"):
        Effect(
            kind=EffectKind.DAMAGE,
            target_id="troll",
            amount=6,
            description="a blow that also knocks prone, allegedly",
            condition=Condition.PRONE,
        )


def test_a_condition_effect_carries_no_number() -> None:
    """A non-zero amount would be read as meaning something — stacking, or a level — and
    nothing in the document says what."""
    with pytest.raises(ValueError, match="carries no number"):
        Effect(
            kind=EffectKind.CONDITION_APPLIED,
            target_id="troll",
            amount=1,
            description="poisoned, intensity one",
            condition=Condition.POISONED,
        )


def test_a_condition_ending_acquires_no_span() -> None:
    """The duration belongs to the application that imposed the condition. A condition on
    its way out does not pick one up."""
    with pytest.raises(ValueError, match="states no duration"):
        Effect(
            kind=EffectKind.CONDITION_ENDED,
            target_id="troll",
            amount=0,
            description="the poison passes",
            condition=Condition.POISONED,
            duration=THREE_ROUNDS,
        )


def test_only_an_application_names_a_source() -> None:
    with pytest.raises(ValueError, match="names no second creature"):
        Effect(
            kind=EffectKind.CONDITION_ENDED,
            target_id="troll",
            amount=0,
            description="the grapple ends",
            condition=Condition.GRAPPLED,
            source_id="pc",
        )


def test_damage_may_not_carry_a_duration_either() -> None:
    """The guard is stated over every kind that is not an application, not over conditions
    alone — so a span cannot ride on a blow.

    The duration and source halves are separate refusals since #323, because the sets that
    may carry them stopped being the same one: p. 90's Cleave names a second creature and
    states no span.
    """
    with pytest.raises(ValueError, match="states no duration"):
        Effect(
            kind=EffectKind.DAMAGE,
            target_id="troll",
            amount=6,
            description="a blow with a span, somehow",
            duration=THREE_ROUNDS,
        )


# --- The constructors, and the zero written once ---------------------------------------


def test_condition_applied_carries_the_span_and_the_source() -> None:
    effect = condition_applied(
        "troll",
        Condition.GRAPPLED,
        description="seized in both arms",
        duration=THREE_ROUNDS,
        source_id="pc",
    )

    assert effect.kind is EffectKind.CONDITION_APPLIED
    assert effect.condition is Condition.GRAPPLED
    assert effect.duration is THREE_ROUNDS
    assert effect.source_id == "pc"
    assert effect.amount == 0, "written once here, not at every call site"


def test_condition_ended_carries_neither() -> None:
    effect = condition_ended("troll", Condition.POISONED, description="the save lands")

    assert effect.kind is EffectKind.CONDITION_ENDED
    assert effect.condition is Condition.POISONED
    assert effect.duration is None
    assert effect.source_id is None
    assert effect.amount == 0


def test_an_unstated_span_is_until_removed_rather_than_permanent() -> None:
    """`duration=None` is not a default span. The state reports the condition as one this
    engine cannot retire, which is visible rather than merely never happening."""
    effect = condition_applied("troll", Condition.BLINDED, description="a flash of light")
    assert effect.duration is None

    after = apply_one(encounter(), effect)
    held = after.combatant("troll").conditions
    assert held.has(Condition.BLINDED)
    assert Condition.BLINDED in held.unretirable(), "named, rather than left to look permanent"


def test_condition_kinds_names_exactly_the_two() -> None:
    """Three places test membership. A drifting fourth is what the constant prevents."""
    assert frozenset({EffectKind.CONDITION_APPLIED, EffectKind.CONDITION_ENDED}) == CONDITION_KINDS


# --- The route into state ---------------------------------------------------------------


def test_an_applied_condition_reaches_the_combatant() -> None:
    after = apply_one(
        encounter(),
        condition_applied("troll", Condition.POISONED, description="a venomous bite"),
    )
    assert after.combatant("troll").conditions.has(Condition.POISONED)


def test_an_applied_span_reaches_the_combatant_too() -> None:
    """The span is the reason `duration` is on the effect at all — the ruling that imposes
    a condition is the only place that knows it."""
    after = apply_one(
        encounter(),
        condition_applied(
            "troll", Condition.RESTRAINED, description="bound", duration=THREE_ROUNDS
        ),
    )
    assert after.combatant("troll").conditions.durations[Condition.RESTRAINED] is THREE_ROUNDS


def test_an_applied_grappler_reaches_the_combatant_too() -> None:
    """p. 182's Disadvantage is "against any target other than the grappler", so who did
    the grappling is mechanical rather than colour."""
    after = apply_one(
        encounter(),
        condition_applied("troll", Condition.GRAPPLED, description="seized", source_id="pc"),
    )
    assert after.combatant("troll").conditions.grappler_id == "pc"


def test_an_ended_condition_leaves_the_combatant() -> None:
    held = apply_one(
        encounter(),
        condition_applied("troll", Condition.POISONED, description="a venomous bite"),
    )
    lifted = apply_one(
        held, condition_ended("troll", Condition.POISONED, description="the save lands")
    )
    assert not lifted.combatant("troll").conditions.has(Condition.POISONED)


def test_the_effect_route_carries_implication_with_it() -> None:
    """Applying Unconscious through a ruling must imply exactly what applying it directly
    implies — otherwise the new door is a second, subtly different rule."""
    after = apply_one(
        encounter(),
        condition_applied("troll", Condition.UNCONSCIOUS, description="struck senseless"),
    )
    conditions = after.combatant("troll").conditions

    assert conditions.has(Condition.INCAPACITATED), "p. 191, resolved when the set is built"
    assert conditions.has(Condition.PRONE)
    assert conditions.applied == frozenset({Condition.UNCONSCIOUS}), (
        "and the implied two are held without having been applied, so ending the source "
        "does not have to know it was implying them"
    )


def test_ending_unconscious_through_a_ruling_leaves_prone_standing() -> None:
    """p. 191: "when this condition ends, you remain Prone". The rule lives in
    `Conditions.without`, and the point here is that the effect route reaches it."""
    struck = apply_one(
        encounter(),
        condition_applied("troll", Condition.UNCONSCIOUS, description="struck senseless"),
    )
    woken = apply_one(
        struck, condition_ended("troll", Condition.UNCONSCIOUS, description="shaken awake")
    )
    conditions = woken.combatant("troll").conditions

    assert not conditions.has(Condition.UNCONSCIOUS)
    assert conditions.has(Condition.PRONE)


# --- The branch that used to be a silent death -------------------------------------------


def test_death_still_reaches_state_now_that_it_has_its_own_branch() -> None:
    """`DEATH` was the trailing `else`. Giving it a named branch is exactly the kind of
    change that drops a case, so its own behaviour is pinned before the alarm below."""
    after = apply_one(
        encounter(),
        Effect(kind=EffectKind.DEATH, target_id="troll", amount=0, description="slain"),
    )
    assert after.combatant("troll").death_saves.dead


def test_an_unhandled_effect_kind_raises() -> None:
    """The hazard #119 removed. While the trailing branch was `DEATH`, any kind added and
    left unhandled became a death — a wrong outcome, produced silently, by the one object
    that exists to stop outcomes being invented.

    The cast fakes a future `EffectKind` member, because every real one now has a branch;
    that is the situation being guarded, and it cannot be reached with a member that
    exists.
    """
    invented = Effect(
        kind=cast(EffectKind, "some-kind-added-later"),
        target_id="troll",
        amount=0,
        description="a kind from a later build",
    )
    with pytest.raises(ValueError, match="no state transition for"):
        _apply(encounter(), (invented,), seed=1)


# --- The record afterwards ---------------------------------------------------------------

SEIZE = Rule(
    id="fixture-seize",
    summary="A hold that imposes Grappled on the target it lands against.",
    provenance=RuleProvenance.FIXTURE,
    rationale=(
        "An invented hold. No rule value is inferred: Grappled and its grappler clause are "
        "real (p. 182), and the test target and span are declared fixture values."
    ),
)
RULESET = load_fixture_ruleset("condition-effects", [SEIZE])


def seize_resolver(
    *, state: EncounterState, declaration: Declaration, facts: Mapping[str, Resolution]
) -> Proposal:
    """A resolver that imposes a condition on success — the first one in the engine that
    does. #119 built the route; until something walks it, nothing proves it connects."""
    return Proposal(
        test=D20Test(
            kind=TestKind.CHECK,
            # 1, so the roll lands whatever the seed. What is under test is the effect the
            # success carries, not whether a die cleared a bar.
            target=1,
            target_basis="fixture: a hold that always lands",
            modifiers=(Modifier(source="ability:str", value=3),),
        ),
        on_success=(
            condition_applied(
                "troll",
                Condition.GRAPPLED,
                description="seized in both arms",
                duration=THREE_ROUNDS,
                source_id="pc",
            ),
        ),
        citations=("p. 182: Grappled",),
        may_claim=("that the troll is held",),
        may_not_claim=("that the troll is harmed — this ruling dealt no damage",),
    )


def seize(path: Path, state: EncounterState) -> tuple[object, EncounterState]:
    adjudicator = Adjudicator(
        ruleset=RULESET,
        resolvers={SEIZE.id: seize_resolver},
        fact_types={},
        port=JsonMemoryStore(path / "memory.json"),
        ledger=Ledger.open(
            path / "ledger.jsonl", engine_version="t", catalogue_version=1, session_id="s"
        ),
        seed_source=lambda: 7,
    )
    offered = read(state, "pc")
    return adjudicator.adjudicate(
        state,
        Declaration(
            actor_id="pc",
            intent=Intent(action_key=attack_key(GRIP.id, "troll")),
            rule_id=SEIZE.id,
            alternatives=offered.actions,
            read_token=offered.token,
        ),
    )


def ruling_entries(path: Path) -> list[Mapping[str, object]]:
    lines = (path / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
    entries = [json.loads(line) for line in lines]
    return [e for e in entries if e["type"] == "ruling"]


def test_a_condition_reaches_state_through_the_adjudication_entry_point(
    tmp_path: Path,
) -> None:
    """The whole point of #119, end to end: a condition that exists because a ruling put
    it there, rather than because a caller reached past the adjudicator."""
    _, after = seize(tmp_path, encounter())
    held = after.combatant("troll").conditions

    assert held.has(Condition.GRAPPLED)
    assert held.grappler_id == "pc"


def test_the_ledger_records_which_condition_changed(tmp_path: Path) -> None:
    """Without these fields the entry says a condition changed and not which — and a replay
    comparing effects would call two different conditions identical."""
    seize(tmp_path, encounter())
    effects = cast(list[Mapping[str, object]], ruling_entries(tmp_path)[0]["payload"])
    recorded = cast(list[Mapping[str, object]], effects["effects"])[0]  # type: ignore[call-overload]

    assert recorded["kind"] == "condition-applied"
    assert recorded["condition"] == "grappled"
    assert recorded["source"] == "pc"
    assert recorded["amount"] == 0


def test_the_ledger_records_how_the_span_was_derived(tmp_path: Path) -> None:
    """`derivation()` rather than the object, so the entry states how the expiry point was
    arrived at instead of leaving a reader to recompute it (R5)."""
    seize(tmp_path, encounter())
    effects = cast(list[Mapping[str, object]], ruling_entries(tmp_path)[0]["payload"])
    recorded = cast(list[Mapping[str, object]], effects["effects"])[0]  # type: ignore[call-overload]

    assert recorded["duration"] == THREE_ROUNDS.derivation()
    assert "round 3" in str(recorded["duration"])


def test_the_payload_version_moved_for_the_new_fields() -> None:
    """Additive, so `RULING_COMPAT` does not move with it — 0022's rule that compat is what
    a reader must be to read a payload *correctly*, not a record of it having changed."""
    from srd_rules_engine.core.adjudicate import RULING_COMPAT

    assert RULING_VERSION >= 4, "3 -> 4 carried condition, duration and grappler"
    assert RULING_COMPAT < RULING_VERSION, "a v3 reader misreads none of them"


# --- Conditional effects, and the shapes that are resolver defects (0032, #173) ---------


def _defended(defences: Defences) -> EncounterState:
    """The shared `encounter()` with the actor's defences replaced, so these tests can drive
    p. 17 without touching a helper twenty other tests depend on."""
    state = encounter()
    actor = replace(state.combatant("pc"), defences=defences)
    return replace(state, combatants=(actor, *(c for c in state.combatants if c.id != "pc")))


def _prone(target_id: str = "pc", *, when: When | None = None) -> Effect:
    return condition_applied(
        target_id, Condition.PRONE, description="an invented conditional", when=when
    )


def _hurt(target_id: str = "pc", amount: int = 4) -> Effect:
    return Effect(
        kind=EffectKind.DAMAGE, target_id=target_id, amount=amount, description="an invented blow"
    )


def test_a_conditional_effect_applies_when_the_damage_landed() -> None:
    """0032 clause 2, the positive branch. The predicate reads the accumulator `_apply`
    fills as it walks, so the damage has to precede it — and does."""
    _, landed, withheld = _apply(encounter(), (_hurt(), _prone(when=When.DAMAGE_TAKEN)), seed=1)
    assert [e.kind for e in landed] == [EffectKind.DAMAGE, EffectKind.CONDITION_APPLIED]
    assert withheld == ()


def test_a_conditional_effect_is_withheld_when_the_damage_came_to_nothing() -> None:
    """The negative branch, driven by Immunity so no dice are involved: the accumulator
    holds what `damage_after_defences` left, which for an immune target is zero."""
    immune = _defended(Defences(immunities=frozenset({DamageType.FIRE})))
    blow = replace(_hurt(amount=9), damage_type=DamageType.FIRE)
    _, landed, withheld = _apply(immune, (blow, _prone(when=When.DAMAGE_TAKEN)), seed=1)

    assert [e.kind for e in landed] == [EffectKind.DAMAGE]
    assert [e.condition for e in withheld] == [Condition.PRONE]


def test_the_predicate_reads_the_taken_number_and_not_the_rolled_one() -> None:
    """0032 clause 2 in one assertion, and the whole of #173.

    Resistance to a 1 halves to 0. An implementation asking one function earlier would see
    the rolled 1, find it greater than zero, and apply the effect — which is the bug, in a
    more elaborate form than the one being fixed.
    """
    resistant = _defended(Defences(resistances=frozenset({DamageType.FIRE})))
    one_point = replace(_hurt(amount=1), damage_type=DamageType.FIRE)
    _, landed, withheld = _apply(resistant, (one_point, _prone(when=When.DAMAGE_TAKEN)), seed=1)

    damage = next(e for e in landed if e.kind is EffectKind.DAMAGE)
    assert (damage.rolled, damage.amount) == (1, 0), "rolled 1, took none"
    assert [e.condition for e in withheld] == [Condition.PRONE]


def test_a_predicate_reads_only_damage_to_its_own_target() -> None:
    """The accumulator is per target. A blow landing on someone else says nothing about
    whether this creature took any, and reading a shared total would knock down bystanders."""
    _, landed, withheld = _apply(
        encounter(), (_hurt("troll"), _prone("pc", when=When.DAMAGE_TAKEN)), seed=1
    )
    assert [e.kind for e in landed] == [EffectKind.DAMAGE]
    assert [e.target_id for e in withheld] == ["pc"]


def test_a_conditional_with_no_damage_before_it_is_refused_at_proposal_time() -> None:
    """A resolver defect, not a rule question. Every predicate reads what a sibling settled
    to, so one placed first is false before the branch runs — and an effect that never
    applies looks exactly like a rule that never fires."""
    with pytest.raises(ValueError, match="no damage to that creature precedes it"):
        Proposal(outcome=(_prone(when=When.DAMAGE_TAKEN), _hurt()))


def test_a_conditional_after_damage_to_someone_else_is_refused_too() -> None:
    """The same defect wearing a disguise. Order alone is not the test — the damage has to
    be to the creature the predicate asks about."""
    with pytest.raises(ValueError, match="no damage to that creature precedes it"):
        Proposal(outcome=(_hurt("troll"), _prone("pc", when=When.DAMAGE_TAKEN)))


def test_every_branch_is_checked_not_only_the_first() -> None:
    """`on_failure` and the natural-die branches are branches too. A guard covering one of
    five certifies exactly the four it does not look at."""
    test = D20Test(kind=TestKind.CHECK, target=10, target_basis="invented")
    bad = (_prone(when=When.DAMAGE_TAKEN),)
    refused = "no damage to that creature precedes it"

    with pytest.raises(ValueError, match=refused):
        Proposal(test=test, on_success=bad)
    with pytest.raises(ValueError, match=refused):
        Proposal(test=test, on_failure=bad)
    with pytest.raises(ValueError, match=refused):
        Proposal(test=test, on_natural_20=bad)
    with pytest.raises(ValueError, match=refused):
        Proposal(test=test, on_natural_1=bad)


def test_damage_cannot_itself_be_conditional_on_damage() -> None:
    """Whether it applied would turn on where it sat in the branch, because a damage effect
    both feeds the accumulator and would read it. No rule the sweep behind 0032 asks for
    this, so it is refused rather than given an order-dependent meaning."""
    with pytest.raises(ValueError, match="damage cannot be conditional on damage"):
        replace(_hurt(), when=When.DAMAGE_TAKEN)


# --- 0041 clause 7: detachment is an outcome (#280) -------------------------------------


ARMOUR = Item(id="fixture-mail", weight=55.0)
ROPE = Item(id="fixture-rope", weight=10.0)


def _laden() -> EncounterState:
    """The `pc` holding a weapon, wearing armour, and with a rope stowed.

    All three carriages, because p. 191 sheds exactly one of them.
    """
    state = encounter()
    laden = replace(
        state.combatant("pc"),
        equipment=(
            Carried(GRIP, Carriage.HELD),
            Carried(ARMOUR, Carriage.WORN),
            Carried(ROPE, Carriage.STOWED),
        ),
    )
    return EncounterState.new([laden, state.combatant("troll")])


def test_falling_unconscious_drops_what_is_held_and_nothing_else() -> None:
    """p. 191, *Unconscious*: "Inert. You have the Incapacitated and Prone conditions, and
    **you drop whatever you're holding**."

    "Holding" is the word, so worn armour and a stowed rope stay. Until #280 this clause was
    disclosed in `unenforced_clauses` and did nothing.
    """
    after = apply_one(
        _laden(),
        condition_applied("pc", Condition.UNCONSCIOUS, description="struck senseless"),
    )
    still_carried = {c.item.id for c in after.combatant("pc").equipment}
    assert still_carried == {ARMOUR.id, ROPE.id}
    assert [obj.item.id for obj in after.detached_objects] == [GRIP.id]


def test_the_dropped_weapon_lands_nowhere_the_document_states() -> None:
    """0041 clause 4. p. 191 sheds the weapon and does not say where it goes, so it arrives
    unplaced rather than in the creature's space — the default p. 217's Dancing Sword has to
    spend a clause stating for itself."""
    after = apply_one(
        _laden(),
        condition_applied("pc", Condition.UNCONSCIOUS, description="struck senseless"),
    )
    assert after.detached_objects[0].position is None


def test_the_drop_is_its_own_recorded_effect_rather_than_a_silent_state_change() -> None:
    """R1 and R5. A mechanical change the ledger cannot see is one no narrator can report
    and no replay can reproduce — so the drop lands as an `Effect` beside the condition,
    not as a side effect of applying it."""
    _after, landed, _withheld = _apply(
        _laden(),
        (condition_applied("pc", Condition.UNCONSCIOUS, description="struck senseless"),),
        seed=1,
    )
    kinds = [effect.kind for effect in landed]
    assert kinds == [EffectKind.CONDITION_APPLIED, EffectKind.OBJECT_DETACHED]
    assert landed[1].item_id == GRIP.id
    assert landed[1].target_id == "pc"


def test_the_engine_derives_the_drop_rather_than_trusting_a_resolver_to_emit_it() -> None:
    """The reason this is engine-derived and not a resolver's job: a ruleset that forgot
    would keep a sword in an unconscious hand and nothing would say so. The caller here
    emits **only** the condition, and the drop happens anyway."""
    only_the_condition = condition_applied(
        "pc", Condition.UNCONSCIOUS, description="struck senseless"
    )
    assert only_the_condition.item_id is None
    after = apply_one(_laden(), only_the_condition)
    assert after.detached_objects


def test_unconscious_no_longer_discloses_a_clause_it_now_enforces() -> None:
    """The disclosure and the behaviour are asserted **together**, and that pairing is the
    point: nothing pinned `"drops-what-it-holds"` before, so it could have been deleted
    without the rule being built — an overclaim no guard would have caught. R32 is only
    honest while the removal and the enforcement move as one.
    """
    disclosed = EFFECTS[Condition.UNCONSCIOUS].unenforced_clauses
    assert "drops-what-it-holds" not in disclosed
    # `remains-prone-when-this-ends` left too, in #292 — it was stale in the harmless
    # direction, because `Conditions.without` enforces p. 191's "you remain Prone".
    # Two of Unconscious's three disclosures have now come off by this same pairing, and the
    # set is pinned in `tests/test_disclosures_are_pinned.py` so a third cannot go quietly.
    assert disclosed == ("unaware",)
    after = apply_one(
        _laden(),
        condition_applied("pc", Condition.UNCONSCIOUS, description="struck senseless"),
    )
    assert after.detached_objects


def test_falling_unconscious_twice_drops_nothing_the_second_time() -> None:
    """Idempotent because it is derived from what is *held*, not specially cased — a
    creature that already dropped its sword is holding nothing to drop."""
    state = _laden()
    once = apply_one(
        state, condition_applied("pc", Condition.UNCONSCIOUS, description="struck senseless")
    )
    twice = apply_one(
        once, condition_applied("pc", Condition.UNCONSCIOUS, description="still senseless")
    )
    assert len(twice.detached_objects) == 1


def test_a_condition_that_states_no_drop_sheds_nothing() -> None:
    """Only p. 191 says this, so only Unconscious does it. Poisoned leaves the sword in hand."""
    after = apply_one(
        _laden(), condition_applied("pc", Condition.POISONED, description="a venomous bite")
    )
    assert after.detached_objects == ()
    assert len(after.combatant("pc").equipment) == 3


def test_detaching_an_item_a_creature_does_not_have_is_refused() -> None:
    """Inventing an object out of a name would put a weapon on the floor that never
    existed — the direction that quietly adds rather than quietly loses."""
    with pytest.raises(ValueError, match="no item"):
        encounter().with_object_detached("pc", "fixture-nonexistent")


def test_an_item_effect_names_the_item_and_no_other_kind_may() -> None:
    """Widened by #283 from one item kind to three — detach, carriage change, pick up — so
    the rule is now `ITEM_KINDS` rather than a single `is`. All three name an item; nothing
    else may."""
    for kind in (
        EffectKind.OBJECT_DETACHED,
        EffectKind.CARRIAGE_CHANGED,
        EffectKind.OBJECT_PICKED_UP,
    ):
        with pytest.raises(ValueError, match="names the item it moves"):
            Effect(kind=kind, target_id="pc", amount=0, description="x")
    with pytest.raises(ValueError, match="names the item it moves"):
        Effect(
            kind=EffectKind.HEALING,
            target_id="pc",
            amount=1,
            description="x",
            item_id=GRIP.id,
        )


def test_only_a_carriage_change_names_where_the_item_went() -> None:
    """Detaching has no carriage at all and picking up always arrives held, so a carriage on
    either would describe a destination its transition ignores."""
    with pytest.raises(ValueError, match="names where the item went"):
        Effect(
            kind=EffectKind.OBJECT_DETACHED,
            target_id="pc",
            amount=0,
            description="x",
            item_id=GRIP.id,
            carriage=Carriage.STOWED,
        )
    with pytest.raises(ValueError, match="names where the item went"):
        Effect(
            kind=EffectKind.CARRIAGE_CHANGED,
            target_id="pc",
            amount=0,
            description="x",
            item_id=GRIP.id,
        )
