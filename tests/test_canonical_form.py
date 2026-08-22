"""The canonical form is what makes the ledger's hash chain mean anything.

A chain over a non-canonical serialization fails on files with nothing wrong with them,
and reports the failure as tamper detection. These tests hold the two properties the
chain actually depends on: two structures differing only in key order produce identical
bytes, and anything without a faithful canonical form is refused rather than
approximated.

The float rejection is the load-bearing refusal. `0.1 + 0.2` is `0.30000000000000004`,
and a coerced value in an authoritative record would first surface as a replay mismatch
on a different machine — the most confusing possible symptom for the least obvious
cause.
"""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

import pytest

from srd_rules_engine.core import CanonicalizationError, canonicalize, digest

# --- Determinism -------------------------------------------------------------------


def test_key_insertion_order_does_not_change_the_bytes() -> None:
    first = {"seq": 1, "type": "ruling", "prev": None}
    second = {"prev": None, "type": "ruling", "seq": 1}
    assert canonicalize(first) == canonicalize(second)


def test_nested_structures_are_ordered_at_every_depth() -> None:
    first = {"outer": {"b": [{"y": 2, "x": 1}], "a": 0}}
    second = {"outer": {"a": 0, "b": [{"x": 1, "y": 2}]}}
    assert canonicalize(first) == canonicalize(second)
    assert canonicalize(first) == b'{"outer":{"a":0,"b":[{"x":1,"y":2}]}}'


def test_list_order_is_significant() -> None:
    """Object keys are unordered and arrays are not — reordering a list is a change."""
    assert canonicalize([1, 2]) != canonicalize([2, 1])


def test_there_is_no_insignificant_whitespace() -> None:
    assert canonicalize({"a": 1, "b": [2, 3]}) == b'{"a":1,"b":[2,3]}'


def test_non_ascii_survives_repeated_canonicalization_byte_identically() -> None:
    value = {"nom": "Élodie", "地": "図", "emoji": "🎲"}
    once = canonicalize(value)
    twice = canonicalize(json.loads(once.decode("utf-8")))
    assert once == twice
    assert "🎲".encode() in once, "non-ASCII is emitted as literal UTF-8, not escaped"


def test_keys_sort_by_utf16_code_unit_not_code_point() -> None:
    """JCS orders by UTF-16 code unit, which diverges once a key leaves the BMP.

    U+FF01 is a single UTF-16 unit; U+10000 is a surrogate pair beginning U+D800.
    By code point U+FF01 (65281) sorts first, since it is the smaller scalar. By UTF-16
    code unit the surrogate 0xD800 sorts first, since it is below 0xFF01. The two
    orderings disagree, and JCS specifies the second.
    """
    bmp, astral = "\uff01", "\U00010000"  # escaped so intent is unambiguous
    assert bmp < astral  # Python's own ordering, by code point
    emitted = canonicalize({bmp: 1, astral: 2}).decode("utf-8")
    assert emitted.index(astral) < emitted.index(bmp)


# --- Types with no canonical form --------------------------------------------------


def test_a_float_at_the_top_level_is_refused() -> None:
    with pytest.raises(CanonicalizationError, match="is a float"):
        canonicalize(1.5)


def test_a_float_nested_inside_a_list_inside_a_mapping_is_refused() -> None:
    payload = {"roll": {"dice": [3, 4.0]}}
    with pytest.raises(CanonicalizationError) as excinfo:
        canonicalize(payload)
    assert ".roll.dice[1]" in str(excinfo.value), "the error names where the float is"


def test_a_whole_valued_float_is_still_refused() -> None:
    """`4.0` looks harmless and is the easiest float to admit by accident."""
    with pytest.raises(CanonicalizationError, match="is a float"):
        canonicalize({"damage": 4.0})


def test_nan_and_infinity_are_refused_as_floats() -> None:
    for value in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(CanonicalizationError, match="is a float"):
            canonicalize(value)


def test_a_decimal_is_refused_rather_than_silently_accepted() -> None:
    with pytest.raises(CanonicalizationError, match="Decimal has no canonical form"):
        canonicalize(Decimal("1.5"))


def test_an_integer_beyond_the_safe_range_is_refused() -> None:
    """Beyond 2**53 a conformant reader parses the bytes back as a different number."""
    with pytest.raises(CanonicalizationError, match="outside the range"):
        canonicalize(2**53)
    assert canonicalize(2**53 - 1) == b"9007199254740991"


def test_a_non_string_object_key_is_refused() -> None:
    payload: dict[Any, int] = {1: 1}
    with pytest.raises(CanonicalizationError, match="must be a string"):
        canonicalize(payload)


def test_an_unsupported_type_is_refused_by_name() -> None:
    with pytest.raises(CanonicalizationError, match="set has no canonical form"):
        canonicalize({1, 2})
    with pytest.raises(CanonicalizationError, match="bytes has no canonical form"):
        canonicalize(b"x")
    with pytest.raises(CanonicalizationError, match="tuple has no canonical form"):
        canonicalize((1, 2))


# --- Types that only look like numbers ---------------------------------------------


def test_a_string_that_looks_like_a_float_is_preserved() -> None:
    """The rule is about types, not appearances — this is how a fraction is carried."""
    assert canonicalize({"cr": "1/8", "weight": "1.5"}) == b'{"cr":"1/8","weight":"1.5"}'


def test_booleans_are_not_integers() -> None:
    """`bool` subclasses `int`, so an unguarded integer branch emits True as 1."""
    assert canonicalize({"crit": True, "fumble": False}) == b'{"crit":true,"fumble":false}'
    assert canonicalize(True) != canonicalize(1)


def test_none_is_null() -> None:
    assert canonicalize({"prev": None}) == b'{"prev":null}'


# --- Boundaries --------------------------------------------------------------------


def test_empty_containers_have_a_canonical_form() -> None:
    assert canonicalize({}) == b"{}"
    assert canonicalize([]) == b"[]"


def test_control_characters_and_quotes_are_escaped() -> None:
    assert canonicalize({"a": 'line\n"quoted"\\'}) == b'{"a":"line\\n\\"quoted\\"\\\\"}'


def test_deep_nesting_is_handled() -> None:
    value: object = 1
    for _ in range(50):
        value = {"n": [value]}
    assert canonicalize(value) == canonicalize(json.loads(canonicalize(value).decode("utf-8")))


# --- The digest --------------------------------------------------------------------


def test_the_digest_is_stable_across_key_ordering() -> None:
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})


def test_the_digest_changes_when_any_value_changes() -> None:
    """A recomputed-checksum edit is what the chain exists to catch."""
    assert digest({"roll": 17}) != digest({"roll": 18})


def test_the_digest_refuses_what_canonicalization_refuses() -> None:
    """The canonical form is the only input to a digest, so the refusal reaches here."""
    with pytest.raises(CanonicalizationError, match="is a float"):
        digest({"roll": 17.5})
