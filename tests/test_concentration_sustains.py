"""p. 179's first consequence: an effect ends when its creator's Concentration does (#240).

> Some spells and other effects require Concentration to remain active, as specified in their
> descriptions. **If the effect's creator loses Concentration, the effect ends.**

[0037](../docs/decisions/0037-a-concentration-is-an-early-out-not-an-axis.md) settled the shape
and #238 built only the end itself. This is the half that makes the end mean something.

Three things here are easy to get wrong, and each wrong version passes most of a test suite:

* **A fifth `DurationKind` loses the span.** p. 179's own third sentence says the description
  states a maximum duration, and `Duration` sets exactly one expiry point — so putting
  Concentration in the `kind` slot keeps a spell up for its full hour because nobody was hit.
  It is an early-out beside `save`, not an axis.
* **`with_concentration_ended` is only two of the four routes.** Incapacitated and death end
  Concentration in `Combatant.__post_init__` and never reach that method, so an implementation
  hooked there passes the failed-save and voluntary-end cases and silently keeps the effect up
  for the other two.
* **`UNTIL_REMOVED` plus an early-out is retirable.** p. 179 says "**If** the effect has a
  maximum duration", so a Concentration spell that states none has no span and still ends. An
  engine reading only the kind would disclose that it cannot end something it ends itself.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core import Combatant, Condition, EncounterState
from srd_rules_engine.core.conditions import Conditions
from srd_rules_engine.core.duration import Duration, DurationKind, SaveEnds
from srd_rules_engine.core.spellcasting import Concentration

HELD = Duration(kind=DurationKind.UNTIL_REMOVED, concentration_of="mage")


def caster(*, spell: str | None = "hold-person") -> Combatant:
    return Combatant(
        id="mage",
        name="Mage",
        hit_points=40,
        max_hit_points=40,
        armour_class=12,
        abilities={"str": 8, "dex": 12, "con": 14},
        proficiency_bonus=2,
        is_player_character=True,
        concentration=Concentration(spell=spell),
    )


def victim(
    duration: Duration | None = HELD, condition: Condition = Condition.PARALYZED
) -> Combatant:
    conditions = (
        Conditions(held=frozenset({condition}), durations={condition: duration})
        if duration is not None
        else Conditions(held=frozenset({condition}))
    )
    return Combatant(
        id="ogre",
        name="Ogre",
        hit_points=30,
        max_hit_points=30,
        armour_class=11,
        abilities={"str": 16, "dex": 8, "con": 14},
        proficiency_bonus=2,
        conditions=conditions,
    )


def encounter(*combatants: Combatant) -> EncounterState:
    people = combatants or (caster(), victim())
    return EncounterState.new(list(people)).with_initiative(
        {c.id: 10 - i for i, c in enumerate(people)}
    )


def holds(
    state: EncounterState, who: str = "ogre", condition: Condition = Condition.PARALYZED
) -> bool:
    return state.combatant(who).conditions.has(condition)


# --- The early-out is expressible, and honest about itself -------------------------------


def test_a_duration_can_name_whose_concentration_sustains_it() -> None:
    """0037 clause 1. Beside the span, never instead of it."""
    minute = Duration(
        kind=DurationKind.ROUNDS,
        ends_after_round=10,
        ends_after_actor_id="mage",
        concentration_of="mage",
    )
    assert minute.concentration_of == "mage"
    assert minute.ends_after_round == 10, "the span p. 179's third sentence states survives"


def test_an_until_removed_span_with_an_early_out_is_retirable() -> None:
    """p. 179: "**If** the effect has a maximum duration". A Concentration spell that states
    none still ends — so reading only the kind would have the engine disclose that it cannot
    end an effect it ends by itself, which 0037 rejected as a wrong disclosure."""
    assert HELD.retirable
    assert not Duration(kind=DurationKind.UNTIL_REMOVED).retirable


def test_a_repeated_save_is_not_a_second_way_to_be_retirable() -> None:
    """p. 63's save is an outcome the turn loop rolls, and it may keep failing. The engine
    cannot end the condition on its own account, which is what `retirable` is asked."""
    saved = Duration(kind=DurationKind.UNTIL_REMOVED, save=SaveEnds(ability="wis", dc=13))
    assert not saved.retirable


def test_the_derivation_names_the_span_and_the_early_out_separately() -> None:
    """R5. They are separate reasons an effect might end, and a reader checking a ruling
    needs to know which one it was waiting for."""
    both = Duration(
        kind=DurationKind.ROUNDS,
        ends_after_round=10,
        ends_after_actor_id="mage",
        concentration_of="mage",
    )
    text = both.derivation()
    assert "round 10" in text
    assert "mage's Concentration ends" in text

    assert "no span either axis can count" in HELD.derivation()
    assert "mage's Concentration ends" in HELD.derivation()


def test_an_early_out_naming_nobody_is_refused() -> None:
    with pytest.raises(ValueError, match="names whose Concentration"):
        Duration(kind=DurationKind.UNTIL_REMOVED, concentration_of="")


# --- The query -----------------------------------------------------------------------------


def test_only_conditions_that_named_this_creature_are_sustained_by_it() -> None:
    """0037 clause 2. Ending one caster's Concentration must not touch another's."""
    conditions = Conditions(
        held=frozenset({Condition.PARALYZED, Condition.FRIGHTENED}),
        durations={
            Condition.PARALYZED: HELD,
            Condition.FRIGHTENED: Duration(
                kind=DurationKind.UNTIL_REMOVED, concentration_of="druid"
            ),
        },
    )
    assert conditions.sustained_by("mage") == frozenset({Condition.PARALYZED})
    assert conditions.sustained_by("druid") == frozenset({Condition.FRIGHTENED})
    assert conditions.concentrations_relied_on() == frozenset({"mage", "druid"})


def test_an_implied_condition_is_not_sustained_on_its_own_account() -> None:
    """`durations` is keyed by what was *applied*. A condition held only because another
    implies it lifts when its source does, which is why it carries no ending of its own."""
    conditions = Conditions(
        held=frozenset({Condition.PARALYZED}), durations={Condition.PARALYZED: HELD}
    )
    assert Condition.INCAPACITATED in conditions.held, "precondition: Paralyzed implies it"
    assert conditions.sustained_by("mage") == frozenset({Condition.PARALYZED})


def test_the_query_changes_nothing() -> None:
    """R19. It answers and mutates nothing, so asking twice gives one answer."""
    conditions = Conditions(
        held=frozenset({Condition.PARALYZED}), durations={Condition.PARALYZED: HELD}
    )
    assert conditions.sustained_by("mage") == conditions.sustained_by("mage")
    assert conditions.has(Condition.PARALYZED)


# --- The two routes a `with_concentration_ended` hook would miss ---------------------------


def test_incapacitating_the_caster_drops_what_it_was_holding_up() -> None:
    """The first route that never calls `with_concentration_ended`. p. 179 ends Concentration
    on Incapacitated in `Combatant.__post_init__` (#238), so an implementation hooked on that
    method passes every other test in this file and keeps the spell up here."""
    state = encounter()
    assert holds(state), "precondition: the effect is up"

    stopped = state.with_condition("mage", Condition.INCAPACITATED)
    assert not stopped.combatant("mage").concentration.active
    assert not holds(stopped)


def test_killing_the_caster_drops_it_too() -> None:
    """The second route, and the one with no caller to make the omission obvious. Death is
    not one of the fifteen conditions, so nothing about a condition ever fires."""
    state = encounter().with_death("mage")
    assert not holds(state)


def test_the_voluntary_end_drops_it() -> None:
    """p. 179: "The creator can end Concentration at any time (no action required)." Ending
    it is the whole action; the effect going is a consequence, not a second decision."""
    assert not holds(encounter().with_concentration_ended("mage"))


def test_damage_that_breaks_concentration_drops_it() -> None:
    """The route 0036 built. `EffectKind.CONCENTRATION_ENDED` reaches
    `with_concentration_ended`, and the retirement follows from the state it leaves."""
    state = encounter()
    broken = state.with_concentration_ended("mage")
    assert not broken.combatant("mage").concentration.active
    assert not holds(broken)


# --- What must survive ---------------------------------------------------------------------


def test_another_casters_effect_is_untouched() -> None:
    """0037 clause 2's point: ending X's Concentration retires exactly what X sustained."""
    druid = replace(
        caster(), id="druid", name="Druid", concentration=Concentration(spell="entangle")
    )
    both = replace(
        victim(),
        conditions=Conditions(
            held=frozenset({Condition.PARALYZED, Condition.RESTRAINED}),
            durations={
                Condition.PARALYZED: HELD,
                Condition.RESTRAINED: Duration(
                    kind=DurationKind.UNTIL_REMOVED, concentration_of="druid"
                ),
            },
        ),
    )
    state = encounter(caster(), druid, both)
    assert holds(state) and holds(state, condition=Condition.RESTRAINED)

    ended = state.with_concentration_ended("mage")
    assert not holds(ended)
    assert holds(ended, condition=Condition.RESTRAINED), "the druid is still concentrating"


def test_a_condition_with_no_early_out_survives_the_concentration_ending() -> None:
    """Nothing here decides that a caster's other effects are theirs to lose. A Grapple and a
    Concentration spell have the same source and must not end together — which is why 0037
    rejected reading `Conditions.sources`."""
    state = encounter(caster(), victim(duration=None, condition=Condition.GRAPPLED))
    ended = state.with_concentration_ended("mage")
    assert holds(ended, condition=Condition.GRAPPLED)


def test_an_effect_survives_while_its_creator_still_concentrates() -> None:
    """The control. Every other assertion here is about something going away."""
    state = encounter()
    assert holds(state.with_condition("ogre", Condition.POISONED))
    assert holds(state.advanced_turn())


# --- The edges the invariant has to be right about ----------------------------------------


def test_a_sustainer_absent_from_the_encounter_sustains_nothing() -> None:
    """A duration naming a creature this encounter does not contain is holding an effect up
    on nothing observable, so it goes. Stated rather than left to be discovered."""
    orphan = replace(
        victim(),
        conditions=Conditions(
            held=frozenset({Condition.PARALYZED}),
            durations={
                Condition.PARALYZED: Duration(
                    kind=DurationKind.UNTIL_REMOVED, concentration_of="someone-else"
                )
            },
        ),
    )
    assert not holds(encounter(caster(), orphan))


def test_the_caster_can_sustain_something_on_itself() -> None:
    """Nothing in p. 179 says the creator cannot be the target, and the walk must not treat
    that as a cycle."""
    self_held = replace(
        caster(),
        conditions=Conditions(
            held=frozenset({Condition.INVISIBLE}), durations={Condition.INVISIBLE: HELD}
        ),
    )
    state = encounter(self_held, victim())
    assert state.combatant("mage").conditions.has(Condition.INVISIBLE)
    assert (
        not state.with_concentration_ended("mage")
        .combatant("mage")
        .conditions.has(Condition.INVISIBLE)
    )


def test_retirement_settles_in_one_pass() -> None:
    """Retiring a condition cannot end another Concentration — `Combatant.__post_init__` ends
    one only when a breaking condition is *present*, and this only removes conditions. So the
    invariant needs no second pass, which is what keeps a constructor from recursing.

    The case that would cascade if anything did: the sustained condition is itself one that
    breaks Concentration, on a creature who is also concentrating.
    """
    druid = replace(
        caster(),
        id="druid",
        name="Druid",
        concentration=Concentration(spell="entangle"),
        conditions=Conditions(
            held=frozenset({Condition.INCAPACITATED}), durations={Condition.INCAPACITATED: HELD}
        ),
    )
    victim_of_druid = replace(
        victim(),
        conditions=Conditions(
            held=frozenset({Condition.PARALYZED}),
            durations={
                Condition.PARALYZED: Duration(
                    kind=DurationKind.UNTIL_REMOVED, concentration_of="druid"
                )
            },
        ),
    )
    state = encounter(caster(), druid, victim_of_druid)

    # The druid was Incapacitated on the way in, so its own Concentration is already spent
    # and what it was sustaining is already gone — settled during construction, not after it.
    assert not state.combatant("druid").concentration.active
    assert not state.combatant("ogre").conditions.has(Condition.PARALYZED)
    # And the mage's own effect on the druid is still there, because the mage still holds it.
    assert state.combatant("druid").conditions.has(Condition.INCAPACITATED)


# --- R32: the boundary is disclosed rather than implied ------------------------------------


def test_the_reach_of_retirement_is_disclosed() -> None:
    """R32, and 0037 clause 6. "The effect ends" will read as total to anyone who does not
    find the limit, and the limit is real: what this engine retires is a condition carrying a
    duration, so a Concentration spell's area, obstruction or summoned creature is not ended
    because it was never modelled.

    A disclosure rather than an enumeration, because there is no list of the things that are
    not modelled — `Conditions.unretirable` can only speak about conditions that exist. This
    guard exists because a prose disclosure is exactly the kind that decays quietly, which is
    the decay #228 found in `core.inventory` and #215 found in `core.duration` itself.
    """
    from pathlib import Path

    module = (
        Path(__file__).resolve().parents[1] / "src" / "srd_rules_engine" / "core" / "duration.py"
    ).read_text()

    assert 'What "the effect ends" reaches, and what it does not' in module, (
        "core.duration no longer discloses how far retiring a concentration effect reaches. "
        "0037 clause 6 makes that an R32 obligation, and the sentence is the whole of it"
    )
    assert "condition carrying a duration" in module
