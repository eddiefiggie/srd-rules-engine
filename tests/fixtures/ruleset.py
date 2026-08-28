"""The invented ruleset the slice runs on: rules, fact types, a weapon, and a catalogue.

Every value here is made up, and each one says so where a real ruleset would cite a
section. The `rationale` field on a fixture rule is doing that work — it is the place the
record admits the number came from nowhere, which is what keeps an invented value from
reading like a verified one after it has been copied twice.

The catalogue is deliberately small and deliberately conditioned on **situational state**
rather than on what the declaration was called. R6's projection has no field for the free
text, so a row cannot be written against prose even here — which is the point of testing
the real matcher rather than a stub.
"""

from __future__ import annotations

from srd_rules_engine.core import (
    Catalogue,
    DefaultKind,
    FactType,
    Grounding,
    MatchCondition,
    Operator,
    Rule,
    RuleProvenance,
    Ruleset,
    Trigger,
    ValueKind,
    Weapon,
    load_fixture_ruleset,
)

# --- The invented creature and its invented weapon --------------------------------------

#: Invented, and named so it has no counterpart in the document — a creature nobody can
#: look up cannot be mistaken for a transcription of one.
CREATURE_NAME = "scree-hound"

#: Invented armour value, invented damage die, invented ability score. Named `fixture-*`
#: so a grep for a plausible weapon name finds nothing to copy.
#: Held, since #258 — a weapon is an `Item` the creature carries (0040 clause 1), so a
#: fixture creature is given one to hold rather than a resolver being bound to it. Proficiency
#: moved to the wielder in the same change (p. 89), so it is no longer a field here.
FIXTURE_BLADE = Weapon(
    id="fixture-blade",
    damage_dice=2,
    damage_sides=6,
    ability="str",
    weight=3.0,
    hands_when_held=1,
)
FIXTURE_FANGS = Weapon(
    id="fixture-fangs",
    damage_dice=1,
    damage_sides=8,
    ability="str",
    weight=0.0,
    hands_when_held=1,
)

# --- Fact types -------------------------------------------------------------------------

#: A choice fact with an honest default: unknown footing is treated as `uncertain`, which
#: is the cautious reading rather than the convenient one.
FOOTING = FactType(
    name="footing",
    kind=ValueKind.CHOICE,
    choices=("firm", "uncertain", "treacherous"),
    default_kind=DefaultKind.ENGINE_CHOSEN,
    default="uncertain",
)

#: No default at all. A rule consuming this blocks rather than guessing, which is what
#: AE3 is about: the absence is disclosed instead of being filled in silently.
NERVE = FactType(name="nerve", kind=ValueKind.BOOLEAN)

FACT_TYPES = {FOOTING.name: FOOTING, NERVE.name: NERVE}

# --- The rules ---------------------------------------------------------------------------

ATTACK = Rule(
    id="fixture-weapon-attack",
    summary="An attack with a held weapon, against the target's armour value.",
    provenance=RuleProvenance.FIXTURE,
    rationale=(
        "Invented. The mechanism — a d20 against the target's armour value — is the one "
        "under test; the armour value, the damage die, and the ability score are all made "
        "up, because no number in this repository has been checked against the document."
    ),
)

CROSSING = Rule(
    id="fixture-scree-crossing",
    summary="Crossing loose ground, where the footing moves the difficulty.",
    provenance=RuleProvenance.FIXTURE,
    consumes=("footing",),
    rationale=(
        "Invented. It exists so a resolved fact can be seen moving a target number and "
        "being cited with its provenance — the mechanism AE4 is about, which is indifferent "
        "to which rule happens to consume the fact."
    ),
)

STEADYING = Rule(
    id="fixture-steadying-nerve",
    summary="Holding steady, where nerve decides whether the attempt is made at all.",
    provenance=RuleProvenance.FIXTURE,
    consumes=("nerve",),
    rationale=(
        "Invented, and consumes a fact with no honest default so the engine has to block "
        "and say what it is missing rather than assume it (AE3)."
    ),
)

RULES = (ATTACK, CROSSING, STEADYING)


def fixture_ruleset() -> Ruleset:
    """The slice's ruleset. Named, so it is always asked for deliberately."""
    return load_fixture_ruleset("vertical-slice", RULES)


# --- The trigger catalogue ----------------------------------------------------------------

#: Authored, not cited. The SRD supplies explicit triggers only for forced saves, attacks,
#: and stated hazards; everything else is the project's judgment, and the judgment is what
#: goes on the record. See `docs/decisions/0004-trigger-catalogue.md`.
LOOSE_GROUND = Trigger(
    id="fixture-hazard-loose-ground",
    grounding=Grounding.AUTHORED,
    when=(
        MatchCondition(field="improvised", operator=Operator.EQUALS, value=True),
        MatchCondition(field="surface", operator=Operator.EQUALS, value="loose-scree"),
    ),
    message=(
        "crossing loose scree is a hazard the fixture treats as warranting a check, so a "
        "claim that no test is needed collides with it"
    ),
    rationale=(
        "Invented hazard. It exists so a silent skip has something to collide with that is "
        "not about how the declaration was worded."
    ),
)

WOUNDED = Trigger(
    id="fixture-hazard-wounded-actor",
    grounding=Grounding.AUTHORED,
    when=(
        MatchCondition(field="improvised", operator=Operator.EQUALS, value=True),
        MatchCondition(field="actor_is_down", operator=Operator.EQUALS, value=True),
    ),
    message="a combatant at 0 hit points is not improvising past a check",
    rationale="Invented. A second row, so two rows can be seen firing on one declaration.",
)

CATALOGUE_VERSION = 1


def fixture_catalogue() -> Catalogue:
    return Catalogue(version=CATALOGUE_VERSION, triggers=(LOOSE_GROUND, WOUNDED))


#: The situation the slice declares under. `surface` is what the hazard row reads; it is
#: situational state supplied by the caller, not anything derived from a label.
LOOSE_SCREE = {"surface": "loose-scree"}
