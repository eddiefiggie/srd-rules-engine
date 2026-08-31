"""p. 183's Hide: the two conditions it needs, the DC it produces, and how it ends (#432).

Nothing here is new machinery. Every piece arrived for something else — Three-Quarters and
Total Cover (#416), `Obscurement`, the sight chain, the Invisible condition, and
`Conditions.causes` to scope its ending (0083). This is the rule that finally asks for them
together.

**The clause worth reading twice** is `Visibility.UNSTATED`. p. 183 requires being out of
every enemy's line of sight, and an encounter that tracks no positions cannot answer that.
`UNSTATED` is *the document does not say* — not "no" — so it **blocks** hiding. Reading it as
a "no" would let a creature standing in an open room with no positional data hide from
everyone in it.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from srd_rules_engine.core.conditions import Condition, Conditions
from srd_rules_engine.core.hiding import refusal_to_hide
from srd_rules_engine.core.obstructions import Cover, Obstruction
from srd_rules_engine.core.position import Position
from srd_rules_engine.core.read_surface import HIDE_DC, hide_key, read
from srd_rules_engine.core.sight import Lighting, LightLevel
from srd_rules_engine.core.state import HIDE_RULE_ID, Combatant, EncounterState

ABILITIES = {"str": 10, "dex": 14, "con": 10, "int": 10, "wis": 10, "cha": 10}


def _at(x: int, cid: str) -> Combatant:
    return Combatant(
        id=cid,
        name=cid.title(),
        hit_points=20,
        max_hit_points=20,
        armour_class=13,
        abilities=ABILITIES,
        proficiency_bonus=2,
        position=Position(x, 0, 0),
        is_player_character=cid == "pc",
    )


def _scene(degree: Cover | None = None, *, opaque: bool = True) -> EncounterState:
    """A hider at x=0 and a watcher at x=20, with an optional barrier between.

    **The light is stated**, because the sight chain answers `UNSTATED` without it and every
    question here would come back "the engine cannot say" — which is the correct answer to a
    scene nobody described, and not the one these tests are about.
    """
    state = replace(
        EncounterState.new([_at(0, "pc"), _at(20, "boar")]).with_initiative({"pc": 20, "boar": 5}),
        lighting=Lighting(ambient=LightLevel.BRIGHT),
    )
    if degree is None:
        return state
    return replace(
        state,
        obstructions=(
            Obstruction(
                lo=Position(8, -10, -10),
                hi=Position(12, 10, 10),
                degree=degree,
                blocks_sight=opaque,
            ),
        ),
    )


# --- p. 183's two conditions, and both must hold -------------------------------------------


def test_total_cover_hides_because_it_also_breaks_the_line_of_sight() -> None:
    """The case p. 183 plainly contemplates: a creature behind a wall is both out of sight
    and behind Total Cover, so both halves of the entry are satisfied at once."""
    assert refusal_to_hide(_scene(Cover.TOTAL), _at(0, "pc")) is None


def test_a_watched_creature_cannot_hide_however_good_its_cover() -> None:
    """p. 183 joins its two conditions with **and**, and cover does not imply concealment.

    A barrier gives Three-Quarters Cover and does **not** block sight — a low wall, a
    railing — so the creature behind it is protected and plainly visible. p. 183 refuses it,
    and this is why cover and sight are two questions rather than one."""
    refusal = refusal_to_hide(_scene(Cover.THREE_QUARTERS, opaque=False), _at(0, "pc"))

    assert refusal is not None
    assert "line of sight" in refusal


def test_three_quarters_cover_that_also_blocks_sight_is_enough() -> None:
    """And the other way: p. 183 does not require Total Cover, only Three-Quarters — so a
    barrier that gives that much *and* is opaque satisfies both conditions."""
    assert refusal_to_hide(_scene(Cover.THREE_QUARTERS, opaque=True), _at(0, "pc")) is None


def test_half_cover_is_not_among_the_degrees_p183_names() -> None:
    """p. 183 names Three-Quarters and Total and stops. Admitting Half would be a rule the
    document does not state, in the direction that helps the hider."""
    from srd_rules_engine.core.hiding import HIDING_COVER

    assert frozenset({Cover.THREE_QUARTERS, Cover.TOTAL}) == HIDING_COVER
    assert Cover.HALF not in HIDING_COVER


def test_an_open_field_refuses() -> None:
    """In stated Bright Light with nothing between them, the watcher sees the hider — so the
    line-of-sight half refuses first, before cover is even asked about."""
    refusal = refusal_to_hide(_scene(), _at(0, "pc"))

    assert refusal is not None
    assert "line of sight" in refusal


# --- UNSTATED is not a "no" ----------------------------------------------------------------


def test_an_encounter_with_no_positions_cannot_answer_and_so_refuses() -> None:
    """`Visibility.UNSTATED` is *the document does not say*, and p. 183 needs it said.

    Written against the implementation that reads "not CAN_SEE" as hidden — which is what I
    wrote first, and which offered Hide to a creature standing in an open room with no
    positional data at all."""
    nowhere = EncounterState.new(
        [
            Combatant(
                id="pc",
                name="Pc",
                hit_points=20,
                max_hit_points=20,
                armour_class=13,
                abilities=ABILITIES,
                proficiency_bonus=2,
            ),
            Combatant(
                id="boar",
                name="Boar",
                hit_points=20,
                max_hit_points=20,
                armour_class=13,
                abilities=ABILITIES,
                proficiency_bonus=2,
            ),
        ]
    )

    refusal = refusal_to_hide(nowhere, nowhere.combatant("pc"))

    assert refusal is not None
    assert "cannot say" in refusal
    assert hide_key() not in read(nowhere, "pc").keys, "and it is not offered either"


# --- The read surface ----------------------------------------------------------------------


def test_hide_is_offered_only_when_p183_permits_it() -> None:
    """R18: an action the rules forbid is not a legal action, and offering it would invite a
    declaration the resolver has to refuse."""
    assert hide_key() in read(_scene(Cover.TOTAL), "pc").keys
    assert hide_key() not in read(_scene(), "pc").keys, "seen, in an open field"
    assert hide_key() not in read(_scene(Cover.THREE_QUARTERS, opaque=False), "pc").keys, (
        "covered but visible"
    )


def test_the_offer_reports_the_dc_and_the_bonus() -> None:
    """Both are what a caller needs to decide, and the DC is the document's rather than the
    situation's — unlike p. 187's Search and p. 189's Study."""
    offer = next(a for a in read(_scene(Cover.TOTAL), "pc").actions if a.key == hide_key())

    assert offer.detail["dc"] == HIDE_DC == 15
    assert offer.detail["bonus"] == 2, "Dexterity +2, and no Stealth proficiency"


# --- The ending is scoped to the Invisible hiding granted ----------------------------------


def test_breaking_hiding_ends_only_the_invisible_that_hiding_caused() -> None:
    """0083, and the reason it exists. A creature Invisible by other means is not revealed by
    drawing a bow — p. 183's entry never says when the condition ends, so the ending belongs
    to the cause."""
    hidden = _scene(Cover.TOTAL).with_hidden("pc", 17)
    hidden = hidden.with_condition("pc", Condition.INVISIBLE, caused_by=HIDE_RULE_ID)

    revealed = hidden.with_hiding_broken("pc", "an attack roll was made").combatant("pc")

    assert revealed.hidden_dc is None
    assert Condition.INVISIBLE not in revealed.conditions.held


def test_another_invisibility_survives_the_hiding_ending() -> None:
    spell = "fixture:a-spell-of-vanishing"
    both = _scene(Cover.TOTAL).with_hidden("pc", 17)
    both = both.with_condition("pc", Condition.INVISIBLE, caused_by=HIDE_RULE_ID)
    both = both.with_condition("pc", Condition.INVISIBLE, caused_by=spell)

    after = both.with_hiding_broken("pc", "an attack roll was made").combatant("pc")

    assert after.hidden_dc is None, "the hiding ended"
    assert Condition.INVISIBLE in after.conditions.held, "and the spell did not"
    assert after.conditions.causes[Condition.INVISIBLE] == frozenset({spell})


def test_breaking_hiding_on_a_creature_that_was_not_hidden_changes_nothing() -> None:
    """p. 183 says what ends hiding; it says nothing about a creature with none to end."""
    plain = _scene(Cover.TOTAL)
    assert plain.with_hiding_broken("pc", "a noise") is plain


# --- The DC is the roll, and the engine supplies it ----------------------------------------


def test_the_hidden_dc_is_recorded_and_is_the_finding_dc() -> None:
    """p. 183: "Make note of your check's total, which is the DC for a creature to find you
    with a Wisdom (Perception) check.\""""
    hidden = _scene(Cover.TOTAL).with_hidden("pc", 19).combatant("pc")
    assert hidden.hidden_dc == 19


def test_a_hiding_total_cannot_be_declared_without_a_test_to_take_it_from() -> None:
    """R4 in the negative. p. 183's DC *is* the check, so a testless proposal has no total to
    record — and a resolver supplying a number would be supplying a result."""
    from srd_rules_engine.core.adjudicate import HidingTotal, _roll_declared

    with pytest.raises(ValueError, match="nothing to record"):
        _roll_declared((HidingTotal(target_id="pc"),), seed=3, total=None)


def test_the_conditions_default_carries_no_hidden_state() -> None:
    """A creature nobody hid has no DC to find it by, which is what `None` means here — the
    number and the marker are one field, so they cannot disagree."""
    assert Conditions().causes == {}
    assert _at(0, "pc").hidden_dc is None
