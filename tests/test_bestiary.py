"""Monster statistics, and the gate that keeps unverified ones out (#21).

Decision 0003: "Only `verified` entries reach the engine. The loader refuses `unverified`
and `excluded` entries rather than filtering them silently." A filter would let a stat block
the engine never checked sit in a campaign looking exactly like one it did.

The other property guarded here is a **licensing** one. `NOTICE.md` commits this repository
to not redistributing rules prose, so a stat block's traits and actions are absent by
construction — there is nowhere in `Statistics` to put a sentence. A test asserts that
remains true, because a text field is exactly the kind of thing added helpfully later.
"""

from __future__ import annotations

import json
from importlib import resources
from typing import Any

import pytest

from srd_rules_engine.core.bestiary import (
    ABILITIES,
    BestiaryLoadError,
    Statistics,
    load_bestiary,
    published_bestiary,
)
from srd_rules_engine.core.position import Speeds
from srd_rules_engine.core.rules import Verification, VerificationState

VERIFIED = Verification(
    state=VerificationState.VERIFIED,
    reference="SRD v5.2.1, Monsters, p. 347 (Wolf)",
    date="2026-08-23",
)


def statistics(**kw: object) -> Statistics:
    fields: dict[str, object] = {
        "id": "wolf",
        "name": "Wolf",
        "armour_class": 14,
        "hit_points": 22,
        "hit_dice": "3d10 + 6",
        "speeds": Speeds(walk=50),
        "abilities": {"str": 17, "dex": 15, "con": 15, "int": 3, "wis": 12, "cha": 7},
        "proficiency_bonus": 2,
        "challenge_rating": "1",
        "verification": VERIFIED,
    }
    fields.update(kw)
    return Statistics(**fields)  # type: ignore[arg-type]


def _raw() -> dict[str, Any]:
    raw: dict[str, Any] = json.loads(
        resources.files("srd_rules_engine.data")
        .joinpath("bestiary.json")
        .read_text(encoding="utf-8")
    )
    return raw


# --- The gate -------------------------------------------------------------------------


def test_a_verified_entry_is_admitted() -> None:
    assert len(load_bestiary([statistics()])) == 1


def test_an_unverified_entry_is_refused_loudly() -> None:
    """Not filtered. A silently dropped entry is a gap nobody can see."""
    unverified = statistics(verification=Verification(state=VerificationState.UNVERIFIED))
    with pytest.raises(BestiaryLoadError, match="does not reach the engine"):
        load_bestiary([unverified])


def test_an_excluded_entry_is_refused_with_its_reason() -> None:
    """R32 discloses an exclusion rather than dropping it, so the reason travels with it."""
    excluded = statistics(
        verification=Verification(
            state=VerificationState.EXCLUDED, reason="the stat block did not parse"
        )
    )
    with pytest.raises(BestiaryLoadError, match="did not parse"):
        load_bestiary([excluded])


def test_a_duplicate_id_is_refused() -> None:
    with pytest.raises(BestiaryLoadError, match="appears twice"):
        load_bestiary([statistics(), statistics()])


def test_every_published_entry_is_verified_and_cites_the_revision() -> None:
    """The whole shipped file, through the same gate any caller uses."""
    for entry in _raw()["entries"]:
        assert entry["verification"]["state"] == "verified", entry["id"]
        assert "SRD v5.2.1" in entry["verification"]["reference"], entry["id"]
        assert entry["verification"]["date"]


def test_the_published_bestiary_loads(  # and therefore passed the gate
) -> None:
    bestiary = published_bestiary()
    assert len(bestiary) >= 6
    assert "wolf" in bestiary


# --- No prose, by construction --------------------------------------------------------


def test_statistics_has_nowhere_to_put_a_trait() -> None:
    """`NOTICE.md`: "Rules prose is not redistributed." The absence of a text field is what
    makes that true structurally rather than by discipline — a `traits: str` added later
    would be the whole commitment undone in one line.
    """
    text_fields = {
        name
        for name, field in Statistics.__dataclass_fields__.items()
        if field.type in ("str", "str | None")
    }
    assert text_fields == {"id", "name", "hit_dice", "challenge_rating"}, (
        "every string on a monster is an identifier or a printed expression, never prose"
    )


def test_a_published_entry_carries_exactly_the_expected_fields() -> None:
    """The structural guard, and it has to be a *key set* rather than a content heuristic.

    The first version of this test asked whether any string "looked like a sentence" by
    checking for an internal full stop. Adding `"traits": "The aboleth can breathe air and
    water."` walked straight past it — one sentence, one trailing period, nothing internal.
    A guard that inspects content can always be satisfied by content; a guard that pins the
    shape cannot.
    """
    expected = {
        "id",
        "name",
        "armour_class",
        "hit_points",
        "hit_dice",
        "speeds",
        "abilities",
        "challenge_rating",
        "proficiency_bonus",
        "traits_modelled",
        "verification",
    }
    for entry in _raw()["entries"]:
        assert set(entry) == expected, (
            f"{entry['id']} carries {set(entry) ^ expected}; a field added here is where "
            "rules prose would enter, and NOTICE.md says it does not"
        )


def test_no_monster_claims_its_traits_are_modelled() -> None:
    """They are not, for any of them. An honest field rather than a silent omission — a
    consumer must be able to tell a statistics-only monster from a complete one."""
    assert all(not e.get("traits_modelled", False) for e in _raw()["entries"])
    assert not published_bestiary()["wolf"].traits_modelled


def test_the_scope_note_says_what_is_missing() -> None:
    scope = _raw()["scope"]
    assert "Statistics only" in scope
    assert "traits_modelled" in scope


# --- The values themselves ------------------------------------------------------------


def test_the_wolf_matches_the_document() -> None:
    """SRD v5.2.1, Monsters, p. 347: AC 14, HP 22 (3d10 + 6), Speed 50 ft., CR 1, PB +2."""
    wolf = published_bestiary()["wolf"]
    assert (wolf.armour_class, wolf.hit_points, wolf.hit_dice) == (14, 22, "3d10 + 6")
    assert wolf.speeds.walk == 50
    assert (wolf.challenge_rating, wolf.proficiency_bonus) == ("1", 2)


def test_special_speeds_are_carried() -> None:
    """p. 258: the Aboleth has Speed 10 ft. and a Swim Speed of 40 — a flat walking speed
    would lose the half that matters underwater."""
    aboleth = published_bestiary()["aboleth"]
    assert aboleth.speeds.walk == 10
    assert aboleth.speeds.swim == 40


def test_a_fractional_challenge_rating_stays_a_string() -> None:
    """`core.canonical` refuses floats, and 1/8 is one the moment it is divided."""
    assert published_bestiary()["bandit"].challenge_rating == "1/8"


def test_hit_dice_are_the_printed_expression_not_an_average() -> None:
    """The average is a derived number; the expression is what the document prints, and it
    is what a caller needs to roll hit points rather than assume them."""
    assert published_bestiary()["aboleth"].hit_dice == "20d10 + 40"


def test_modifiers_floor_divide_so_negatives_round_the_right_way() -> None:
    """The Wolf's Intelligence is 3, and (3 - 10) // 2 is -4 rather than -3."""
    assert published_bestiary()["wolf"].modifier("int") == -4


def test_a_stat_block_missing_an_ability_is_refused() -> None:
    """All six are printed, so a partial set means the derivation lost one."""
    with pytest.raises(ValueError, match="missing ability scores"):
        statistics(abilities={"str": 10})


def test_every_published_entry_has_all_six_abilities() -> None:
    for entry in _raw()["entries"]:
        assert set(entry["abilities"]) == set(ABILITIES), entry["id"]


# --- How an entry was checked (0017) --------------------------------------------------


def test_every_published_entry_records_how_it_was_verified() -> None:
    """Decision 0017. An entry saying `verified` without saying *how* invites the next
    reader to assume whichever meaning suits them — which is the drift that decision exists
    to close.
    """
    for entry in _raw()["entries"]:
        assert entry["verification"]["method"] == "asserted", entry["id"]


def test_the_method_survives_the_loader() -> None:
    from srd_rules_engine.core.rules import VerificationMethod

    assert published_bestiary()["wolf"].verification.method is VerificationMethod.ASSERTED
