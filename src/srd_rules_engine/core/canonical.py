"""The canonical byte form of a value, and the only input any digest is taken over.

The ledger's hash chain (R26) requires each entry to carry a checksum of its own body
and the digest of its predecessor. That is unimplementable over JSON as such: JSON has
no canonical form, and key order, whitespace, escaping, and number formatting all vary
between serializers. Two writers disagreeing on any of them produce a chain that fails
to verify against a file with nothing wrong with it — reported as *tamper detected*,
which is the worst available misdiagnosis.

So the form is fixed here: **RFC 8785 (JSON Canonicalization Scheme), restricted to
exclude floating-point numbers.** UTF-8, object keys sorted by UTF-16 code unit, no
insignificant whitespace.

Excluding floats is what makes the restriction implementable without a dependency —
JCS's genuinely hard requirement is ECMAScript number serialization, and the domain
needs none of it. Dice, damage, difficulty classes, armour values, hit points,
modifiers, spell slot levels, and distances in feet are all integers. The SRD's few
fractional quantities are carried as exact strings or integer subunits instead.

That is a correctness decision before it is a convenience one. `0.1 + 0.2` is
`0.30000000000000004`, and a record whose purpose is to be authoritative about what
happened must not contain values that are approximately what they say. A float is
therefore refused rather than coerced: a coerced value is silently wrong, and the
symptom would first appear as a replay mismatch on a different machine.

See `docs/decisions/0006-ledger-format.md`.
"""

from __future__ import annotations

import hashlib
import json

# ECMAScript numbers are IEEE 754 doubles, so JCS can only faithfully represent
# integers inside the safe range. An integer beyond it canonicalizes to bytes a
# conformant reader would parse back as a different number — the same class of
# defect as a float, and refused for the same reason.
MAX_SAFE_INTEGER = 2**53 - 1
MIN_SAFE_INTEGER = -MAX_SAFE_INTEGER


class CanonicalizationError(TypeError):
    """A value has no canonical form, and no approximation of one will be invented."""


def _reject(reason: str, path: str) -> CanonicalizationError:
    where = path or "the value"
    return CanonicalizationError(f"{where}: {reason}")


def _validate(value: object, path: str) -> None:
    # bool is a subclass of int in Python, so it is settled before the integer case
    # or True would canonicalize as 1.
    if value is None or isinstance(value, bool):
        return

    if isinstance(value, float):
        raise _reject(
            f"{value!r} is a float, and no ledger value may be one. Carry a fractional "
            "quantity as an exact string or an integer subunit instead",
            path,
        )

    if isinstance(value, int):
        if not MIN_SAFE_INTEGER <= value <= MAX_SAFE_INTEGER:
            raise _reject(
                f"{value!r} is outside the range an ECMAScript number represents exactly, "
                "so it has no faithful canonical form",
                path,
            )
        return

    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as exc:  # lone surrogates
            raise _reject(f"the string is not encodable as UTF-8 ({exc.reason})", path) from exc
        return

    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate(item, f"{path}[{index}]")
        return

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise _reject(
                    f"the key {key!r} is a {type(key).__name__}, and a key must be a string",
                    path,
                )
            _validate(key, f"{path}.{key} (key)")
            _validate(item, f"{path}.{key}")
        return

    raise _reject(f"a {type(value).__name__} has no canonical form", path)


def _emit_string(value: str) -> str:
    # The stdlib already implements the escaping JCS inherits from ECMAScript —
    # `"`, `\`, and the control characters, with the short forms where they exist —
    # and `ensure_ascii=False` leaves everything else as literal UTF-8.
    return json.dumps(value, ensure_ascii=False)


def _emit(value: object) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return _emit_string(value)
    if isinstance(value, list):
        return "[" + ",".join(_emit(item) for item in value) + "]"
    if isinstance(value, dict):
        # JCS orders keys by UTF-16 code unit, which is not the same as Python's
        # code-point ordering once a key carries a character outside the BMP.
        # Encoding to UTF-16 big-endian and comparing bytes reproduces it exactly.
        pairs = sorted(value.items(), key=lambda kv: str(kv[0]).encode("utf-16-be"))
        return "{" + ",".join(f"{_emit_string(str(k))}:{_emit(v)}" for k, v in pairs) + "}"

    # Unreachable: _validate has already refused anything that reaches here.
    raise _reject(f"a {type(value).__name__} has no canonical form", "")


def canonicalize(value: object) -> bytes:
    """Return the canonical UTF-8 bytes of `value`, or refuse it.

    Two structures that differ only in key insertion order canonicalize identically;
    two that differ in any value do not.
    """
    _validate(value, "")
    return _emit(value).encode("utf-8")


def digest(value: object) -> str:
    """The SHA-256 hex digest of a value's canonical form.

    Every digest in the ledger is taken through this function rather than over bytes a
    caller assembled, so "the canonical form is the only input to any digest" holds by
    construction rather than by convention.
    """
    return hashlib.sha256(canonicalize(value)).hexdigest()
