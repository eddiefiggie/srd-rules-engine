"""A rule the menu asks and nothing else does (#365, 0068).

Four times in one session a rule turned out to be computed once, consumed by `legal_actions`,
and absent from the path that produces outcomes — p. 90's Push bound, p. 182's escape DC,
p. 186's righting cost, p. 105's components. **Every one was found by a person**, writing a
test or reading a neighbouring function while fixing something else.

R18 asks for legality to be *computable*, so the menu check is right and stays. The second
call site is the floor under it, and this walk is what notices when there is only one.

## What it actually asks

Every name `core.read_surface` uses that is **defined somewhere in `core` and used nowhere
else in `core`**. That is deliberately not "the resolver does not call it": the enforcement
this repository wants is often in a state transition rather than in a resolver —
[0056](../docs/decisions/0056-a-move-is-refused-where-it-is-made.md) put a movement refusal in
`with_movement` precisely because that is where a move is made. A guard keyed on resolver
modules reported twenty-seven names and was wrong about most of them.

## Why an annotated list rather than a bare assertion

The walk cannot tell a rule from a value: `movement_remaining` and `attacks_remaining` are the
same shape and only one of them decides anything. So every name it finds carries a verdict a
person wrote — `REPORTED` for a value the surface publishes, or an issue number for a rule
nothing else asks. Both directions are pinned. A **new** name is a menu gate somebody added
without a second call site, and a **vanished** one is a gate that was wired up or deleted;
each should be a deliberate edit to this file, which is the whole point.

The set is derived, so the list cannot quietly fall behind the code — the failure mode
`tests/test_disclosures_are_pinned.py` exists to prevent for disclosures, in the same shape.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final

CORE = Path(__file__).resolve().parents[1] / "src" / "srd_rules_engine" / "core"
READ_SURFACE = CORE / "read_surface.py"

#: Every name the read surface uses that nothing else in `core` does, with what it is.
#:
#: `REPORTED:` means the surface publishes the value and it gates nothing — asking it again
#: elsewhere would be asking a question with no consequence.
#:
#: An issue number means it is a **rule**, and the path that produces outcomes does not ask it.
GATES_ASKED_ONLY_BY_THE_MENU: Final[dict[str, str]] = {
    # --- Values the surface publishes -----------------------------------------------------
    "movement_remaining": (
        "REPORTED: a `Situation` field. What refuses an unaffordable move is `with_movement`, "
        "which computes the cost itself rather than reading this (0056)."
    ),
    "over_carrying_capacity": (
        "REPORTED: a `Situation` field, and p. 178 attaches no consequence to it at all — the "
        "sentence with a rule in it is the hauling one, and `over_hauling_capacity` is read by "
        "`effective_speeds` (0067 clause 6)."
    ),
    "reachable_objects": "REPORTED: a `Situation` field (0041 clause 3).",
    "unplaced_objects": "REPORTED: a `Situation` field, and R32's disclosure (0041 clause 4).",
    "unretirable": (
        "REPORTED: it fills `Situation.conditions_until_removed`, so a caller is not left to "
        "infer permanence from a duration that never counts down."
    ),
    "push_distances": (
        "REPORTED: an **enumerator**, not a predicate — it lists the five-foot steps the menu "
        "offers (0055). The bound itself is `PUSH_MASTERY_FEET`, and the resolver checks it."
    ),
    "untrained_shields": (
        '#367: p. 92 gives a Shield\'s AC benefit "only if you have training with it", and '
        "nothing withholds it. This enumerates who the clause *would* bite, so R32's "
        "disclosure reaches the right creature — a rule the menu names and nothing enforces, "
        "which is what an issue number here means. #393 made the withholding expressible by "
        "deriving AC; #367 is the withholding."
    ),
    # --- Rules the path that produces outcomes does not ask --------------------------------
    # Empty, and it did not start that way. The seven entries here on the day this file was
    # written were p. 89's Extra Attack limit and Cleave, p. 90's Loading and Ammunition, and a
    # stat block's Multiattack — every one of them asked by the menu and by nothing else.
    # #376 gave each its second call site in `core.combat`, and they left this list through the
    # test below rather than by anybody remembering to take them off (0069).
}

#: An entry is a published value or a filed rule. Nothing else is an answer.
VERDICT = re.compile(r"^(REPORTED:|#\d+:)")


def _defined_names(paths: list[Path]) -> dict[str, str]:
    """Every function, method and property name these modules define, to the module."""
    out: dict[str, str] = {}
    for path in paths:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                out.setdefault(node.name, path.stem)
    return out


def _used_names(path: Path) -> set[str]:
    """Every name this module calls or reads as an attribute.

    Attributes as well as calls, because a property is read rather than called and half the
    gates in question are properties — a walk that looked only at `ast.Call` would miss
    `actor.weapons_held` entirely, which is the shape this file is about.
    """
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                names.add(node.func.attr)
        elif isinstance(node, ast.Attribute):
            names.add(node.attr)
    return names


def menu_only_names() -> dict[str, str]:
    """Names the read surface uses that are defined in `core` and used nowhere else in it."""
    others = [p for p in sorted(CORE.glob("*.py")) if p != READ_SURFACE]
    defined = _defined_names(others)
    used_elsewhere: set[str] = set()
    for path in others:
        used_elsewhere |= _used_names(path)

    return {
        name: defined[name]
        for name in _used_names(READ_SURFACE)
        if name in defined and name not in used_elsewhere and not name.startswith("_")
    }


def test_the_walk_finds_something_at_all() -> None:
    """The canary `tests/test_disclosures_are_pinned.py` learned to need.

    A walk that matched nothing would pin an empty set and pass forever, which is the failure
    a derived guard is most exposed to — it looks like a clean bill of health.
    """
    found = menu_only_names()
    assert len(found) > 5, "the walk collapsed; it is inspecting nothing"
    assert found["movement_remaining"] == "state"


def test_every_name_the_walk_finds_carries_a_verdict() -> None:
    """A gate added without a second call site fails here, which is the point of the file."""
    found = menu_only_names()
    unannotated = sorted(set(found) - set(GATES_ASKED_ONLY_BY_THE_MENU))
    assert not unannotated, (
        f"{unannotated} are used by core.read_surface and by nothing else in core. Either the "
        "rule is asked on the path that produces outcomes as well as offered on the menu "
        "(#365), or it is a value the surface publishes — say which in "
        "GATES_ASKED_ONLY_BY_THE_MENU, with an issue number if it is a rule nothing enforces."
    )


def test_a_name_that_stopped_being_menu_only_leaves_this_list() -> None:
    """The other direction, and it is not symmetry for its own sake.

    A name leaving the walk means somebody gave the rule its second call site — the fix #365
    asks for — or deleted it. Either way the annotation is now false, and a false annotation
    about an unenforced rule is exactly what `unenforced_clauses`'s pin exists to prevent.
    """
    found = menu_only_names()
    stale = sorted(set(GATES_ASKED_ONLY_BY_THE_MENU) - set(found))
    assert not stale, (
        f"{stale} are annotated here and are no longer menu-only. If the rule gained its "
        "second call site, take the entry off and close its issue with the evidence "
        "(AGENTS.md: an issue resolved as already-correct still gets closed)."
    )


def test_each_verdict_is_a_published_value_or_a_filed_issue() -> None:
    """ "It is fine" is not a verdict. A rule nothing enforces is tracked or it is untracked,
    and an annotation that says neither is a third state this file will not hold."""
    for name, verdict in GATES_ASKED_ONLY_BY_THE_MENU.items():
        assert VERDICT.match(verdict), (
            f"{name!r} is annotated {verdict!r}. An entry begins with 'REPORTED:' for a value "
            "the surface publishes, or '#N:' for a rule the outcome path does not ask."
        )
