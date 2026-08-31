"""p. 180's Dead: a creature that cannot regain hit points (#438).

> A dead creature has no Hit Points and **can't regain them unless it is first revived by
> magic** such as the Raise Dead or Revivify spell.

Found by a systematic pass over the unclaimed shapes rather than by a failing test. A Cure
Wounds resurrected a corpse: `with_healing` added the hit points and then reset the death
saves — `dead` lives in the same structure as `successes` and `failures`, and p. 17's reset
"when you regain any Hit Points" does not ask whether the creature was alive to regain them.

The refusal is **total**, and that is honest rather than complete: p. 180's exception is
revival magic, and there are no spells (#21), so Raise Dead does not exist to be excepted.
"""

from __future__ import annotations

from srd_rules_engine.core.state import Combatant, EncounterState

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}


def _creature(hp: int = 0) -> Combatant:
    return Combatant(
        id="pc",
        name="Wren",
        hit_points=hp,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        is_player_character=True,
    )


def _dead() -> EncounterState:
    return EncounterState.new([_creature()]).with_death("pc")


# --- p. 180's rule -------------------------------------------------------------------------


def test_healing_a_dead_creature_does_nothing() -> None:
    """The bug this was written against: it healed to 10 and cleared `dead`."""
    after = _dead().with_healing("pc", 10).combatant("pc")

    assert after.hit_points == 0, "p. 180: a dead creature has no Hit Points"
    assert after.death_saves.dead, "and healing does not revive it"


def test_it_is_a_no_op_rather_than_a_refusal() -> None:
    """Healing a corpse is a thing a caller may legitimately try — a cleric pouring a potion
    into a dead friend is a scene, and p. 180 answers it with "nothing happens" rather than
    with an error. The state comes back unchanged and identical."""
    dead = _dead()
    assert dead.with_healing("pc", 10) is dead


def test_a_dying_creature_is_still_healed_and_stabilised() -> None:
    """The case the reset exists for, and the one this must not break. p. 17: both counts are
    reset "when you regain any Hit Points", so a creature at 0 and *not* dead is healed and
    its Death Saving Throws are cleared."""
    dying = EncounterState.new([_creature()]).with_death_save("pc", failures=2)
    assert not dying.combatant("pc").death_saves.dead

    revived = dying.with_healing("pc", 4).combatant("pc")

    assert revived.hit_points == 4
    assert revived.death_saves.failures == 0, "p. 17's reset still applies"


def test_healing_zero_to_a_dead_creature_is_also_nothing() -> None:
    """No edge in the guard: the check is on the creature, not on the amount."""
    dead = _dead()
    assert dead.with_healing("pc", 0) is dead
