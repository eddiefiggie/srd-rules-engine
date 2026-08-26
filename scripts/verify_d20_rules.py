"""Verify the d20 rules this engine implements against the official SRD v5.2.1 PDF.

This is the reproducible half of `core.d20.ADVANTAGE_VERIFICATION`. Like
`derive_effect_shapes.py` it is **not** run in CI, because CI has no copy of the document:
the SRD is CC BY 4.0 but it is not ours to redistribute, and this repository deliberately
carries no SRD prose (see `NOTICE.md`). Anyone holding the PDF can re-run it.

A `Verification` block carries a date, and `AGENTS.md` is emphatic that a dated claim
cannot notice its own staleness. This script is what makes the date re-checkable rather
than merely asserted: every clause the implementation relies on is stated here as a
pattern that must match the cited printed page, and the script exits non-zero if any of
them stops matching. If a future SRD revision reworded the cancellation rule, this goes
red rather than the engine quietly resolving rolls against a sentence nobody re-read.

Patterns are matched against whitespace-normalised page text, because the document is set
in two columns with hyphenated line breaks — `Advantage and Dis-\\nadvantage` is one phrase
to a reader and three tokens to a naive search.

Usage: python3 scripts/verify_d20_rules.py /path/to/SRD_CC_v5.2.1.pdf
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

#: Printed page N is PDF index N-1.
PAGE_OFFSET = 1

#: Each clause the implementation depends on, as (printed page, what it settles, pattern).
#: The pattern must match that page's normalised text or the script fails.
CLAUSES: tuple[tuple[int, str, str], ...] = (
    (
        7,
        "advantage and disadvantage are a property of a D20 Test",
        r"Sometimes a D20 Test is modified by Advantage or Disadvantage",
    ),
    (
        8,
        "two dice, higher for advantage",
        r"roll a second d20 when you make the roll\.\s*Use the higher of the two rolls if you "
        r"have Advantage",
    ),
    (
        8,
        "two dice, lower for disadvantage",
        r"use the lower roll if you have Disadvantage",
    ),
    (
        8,
        "the document's own worked example: disadvantage on 18 and 3 uses the 3",
        r"if you have Disadvantage and roll an 18 and a 3, use the 3",
    ),
    (
        8,
        "sources on the same side do not accumulate: still two dice",
        r"If multiple situations affect a roll and they all grant Advantage on it, you still "
        r"roll only two d20s",
    ),
    (
        8,
        "opposing sources cancel to a single plain die",
        r"If circumstances cause a roll to have both Advantage and Disadvantage, the roll has "
        r"neither of them, and you roll one d20",
    ),
    (
        8,
        "cancellation is presence-based, not count-based — the question #52 asked",
        r"This is true even if multiple circumstances impose Disadvantage and only one grants "
        r"Advantage or vice versa",
    ),
    (
        8,
        "both dice stay individually addressable, so neither may be discarded",
        r"you can reroll or replace only one die, not both\.\s*You choose which one",
    ),
    (
        7,
        "a natural 20 on an attack roll hits regardless of modifiers or AC",
        r"If you roll a 20 on the d20 \(called a .natural 20.\) for an attack roll, the "
        r"attack hits regardless of any modifiers or the target.s AC",
    ),
    (
        7,
        "a natural 1 on an attack roll misses regardless of modifiers or AC",
        r"If you roll a 1 on the d20 \(a .natural 1.\) for an attack roll, the attack "
        r"misses regardless of any modifiers or the target.s AC",
    ),
    (
        179,
        "a Critical Hit doubles the damage dice and not the modifiers",
        r"Roll all of the attack.s damage dice twice and add them together\.\s*Then add "
        r"any relevant modifiers",
    ),
    (
        186,
        "Passive Perception is 10 plus the check bonus",
        r"Passive Perception equals 10 plus the creature.s Wisdom \(Perception\) check bonus",
    ),
    (
        186,
        "advantage and disadvantage shift a passive score by 5 rather than rolling",
        r"If the creature has Advantage on such checks, increase the score by 5\.\s*If the "
        r"creature has Disadvantage on them, decrease the score by 5",
    ),
    (
        8,
        "the reroll rule has a subsection of its own, which is what makes it a rule",
        r"Interactions with Rerolls",
    ),
    (
        8,
        "the document's worked reroll example names Heroic Inspiration",
        r"expend your Heroic Inspiration to reroll one of those dice, not both of them",
    ),
    (
        183,
        "Heroic Inspiration replaces one die and the new roll is binding",
        r"expend it to reroll any die immediately after rolling it, and you must use the "
        r"new roll",
    ),
    (
        86,
        "Halfling Luck replaces a natural 1, and is likewise binding",
        r"When you roll a 1 on the d20 of a D20 Test, you can reroll the die, and you must "
        r"use the new roll",
    ),
    (
        175,
        "Wish forces a reroll of a die already rolled",
        r"forcing a reroll of any die roll made within the last round",
    ),
    (
        175,
        "a forced reroll may itself be made with Advantage or Disadvantage — the clause "
        "that decides replace_die returns dice rather than one face",
        r"You can force the reroll to be made with Advantage or Disadvantage",
    ),
    (
        17,
        "WHEN a death save is made — the timing anchor 0023 declined to supply from memory "
        "and #124 was blocked on. It is the START of a turn, not the end, so it is not the "
        "phase save-ends lives in",
        r"Whenever you start your turn with 0 Hit Points, you must make a Death Saving "
        r"Throw",
    ),
    (
        17,
        "a death save is DC 10 and tied to no ability score",
        r"this one isn.t tied to an ability score",
    ),
    (
        17,
        "10 or higher succeeds",
        r"Roll 1d20\.\s*If the roll is 10 or higher, you succeed\.\s*Otherwise, you fail",
    ),
    (
        17,
        "three of a kind resolves it, and they need not be consecutive",
        r"On your third success, you become Stable.{0,120}On your third failure, you die\."
        r"\s*The successes and failures don.t need to be consecutive",
    ),
    (
        17,
        "the counts reset on regaining any hit points or becoming Stable",
        r"reset to zero when you regain any Hit Points or become Stable",
    ),
    (
        17,
        "a monster dies the instant it drops to 0, rather than making saves",
        r"A monster dies the instant it drops to 0 Hit Points",
    ),
    (
        17,
        "massive damage kills on the REMAINDER, not on the whole blow",
        r"When damage reduces a character to 0 Hit Points and damage remains, the character "
        r"dies if the remainder equals or exceeds their Hit Point maximum",
    ),
    (
        18,
        "a natural 1 costs two failures and a natural 20 restores a hit point",
        r"When you roll a 1 on the d20 for a Death Saving Throw, you suffer two failures\."
        r"\s*If you roll a 20 on the d20, you regain 1 Hit Point",
    ),
    (
        18,
        "damage at 0 hit points is a failure, and two from a Critical Hit",
        r"If you take any damage while you have 0 Hit Points, you suffer a Death Saving "
        r"Throw failure\.\s*If the damage is from a Critical Hit, you suffer two failures",
    ),
    (
        18,
        "a Stable creature makes no saves, and damage ends that",
        r"A Stable creature doesn.t make Death Saving Throws.{0,200}If the creature takes "
        r"damage, it stops being Stable",
    ),
    # --- The nine sight shapes (#150, 0025 clause 5) ---------------------------------
    # These are the rule values `core.sight` refused to state until they were read. Each is
    # the sentence one row of the mapping rests on.
    (
        178,
        "Bright Light is normal illumination — it states no obscurement, which is why "
        "Obscurement.NONE is this engine's absence rather than a glossary term",
        r"Bright Light is normal illumination",
    ),
    (
        181,
        "Dim Light IS Lightly Obscured — the light level and the obscurement are the same "
        "fact, not two that need relating",
        r"An area with Dim Light is Lightly Obscured",
    ),
    (
        180,
        "Darkness IS Heavily Obscured",
        r"An area of Darkness is Heavily Obscured",
    ),
    (
        184,
        "what Lightly Obscured costs: Disadvantage on Perception checks to SEE something "
        "in that space — a check penalty, not a condition",
        r"You have Disadvantage on Wisdom \(Perception\) checks to see something in a "
        r"Lightly Obscured space",
    ),
    (
        182,
        "what Heavily Obscured costs, and the clause that decides this subsystem reads "
        "state rather than writing it: Blinded holds WHILE TRYING TO SEE something in the "
        "space. It is scoped to the attempt, so it is a relation per observer and target "
        "rather than a condition on the creature (0025 clause 4, #119)",
        r"You have the Blinded condition while trying to see something in a Heavily "
        r"Obscured space",
    ),
    (
        180,
        "Darkvision re-reads the light level, and is the only sense that does: Dim as "
        "Bright, Darkness as Dim",
        r"you can see in Dim Light within a specified range as if it were Bright Light and "
        r"in Darkness within that range as if it were Dim Light",
    ),
    (
        177,
        "Blindsight does NOT re-read a light level — it sees without relying on physical "
        "sight, and its bound is Total Cover rather than illumination",
        r"you can see within a specific range without relying on physical sight.{0,120}you "
        r"can see anything that isn.t behind Total Cover even if you have the Blinded "
        r"condition or are in Darkness",
    ),
    (
        190,
        "Truesight does NOT re-read a light level either — it pierces Darkness rather than "
        "converting it",
        r"You can see in normal and magical Darkness",
    ),
    (
        190,
        "Tremorsense is not part of the sight chain at all, and the document says so "
        "outright rather than leaving it to be inferred",
        r"Tremorsense can.t detect creatures or objects in the air, and it doesn.t count as "
        r"a form of sight",
    ),
    (
        177,
        "the Blinded condition is absolute about the one thing it names, which is why an "
        "observer holding it settles this question before any light does",
        r"Can.t See\.\s*You can.t see and automatically fail any ability check that "
        r"requires sight",
    ),
    (
        184,
        "the Invisible condition never says you CANNOT be seen — it says effects needing "
        "sight miss you 'unless the effect.s creator can somehow see you', and leaves how "
        "open. So ordinary sight of an Invisible creature is unstated (#166)",
        r"You aren.t affected by any effect that requires its target to be seen unless the "
        r"effect.s creator can somehow see you",
    ),
    (
        177,
        "Blindsight says outright that it does see one",
        r"Moreover, in that range, you can see something that has the Invisible condition",
    ),
    (
        190,
        "and so does Truesight — the two senses the document gives an answer for",
        r"Invisibility\.\s*You see creatures and objects that have the Invisible condition",
    ),
    # --- What the document does NOT say about sight (#166) ------------------------------
    (
        173,
        "a WALL has to say it blocks line of sight, which is the evidence that no general "
        "rule does. If an obstruction blocked sight by default this clause would be "
        "redundant, and the SRD defines 'line of sight' nowhere at all",
        r"The wall blocks line of sight",
    ),
    (
        179,
        "and Total Cover is defined by what it does to TARGETING, not to seeing",
        r"Total Cover \(can.t be targeted directly\)",
    ),
    # --- What finishing a Long Rest does (#185) ----------------------------------------
    (
        185,
        "a creature at 0 hit points cannot START a Long Rest, which is the precondition an "
        "implementation drops because every other benefit reads as unconditional",
        r"To start a Long Rest, you must have at least 1 Hit Point",
    ),
    (
        185,
        "the Long Rest's own statement of the general removal rule: the LEVEL decreases by "
        "one, not the condition ending",
        r"Exhaustion Reduced\.\s*If you have the Exhaustion condition, its level decreases "
        r"by 1",
    ),
    (
        185,
        "and it restores every lost hit point, alongside spent Hit Point Dice and a reduced "
        "maximum — two of the three this engine cannot yet express",
        r"Regain All HP\.\s*You regain all lost Hit Points and all spent Hit Point Dice",
    ),
    # --- Exhaustion levels, and who may remove them (#178) -----------------------------
    (
        181,
        "an Exhaustion level is gained one at a time, and the condition is cumulative — "
        "which is why raising it needs its own effect rather than an application of the "
        "condition, whose arithmetic is entirely in the level",
        r"This condition is cumulative\.\s*Each time you receive it, you gain 1 Exhaustion "
        r"level\.\s*You die if your Exhaustion level is 6",
    ),
    (
        181,
        "the general removal rule: a Long Rest removes ONE level, and the condition ends at "
        "zero rather than being removed outright",
        r"Finishing a Long Rest removes 1 of your Exhaustion levels\.\s*When your Exhaustion "
        r"level reaches 0, the condition ends",
    ),
    (
        189,
        "Suffocation removes ALL the levels IT caused when the creature breathes again — "
        "the sentence that makes a level's source load-bearing, because a bare count cannot "
        "say which levels these are",
        r"When a creature can breathe again, it removes all levels of Exhaustion it gained "
        r"from suffocating",
    ),
    (
        181,
        "and dehydration's levels run the other way: removable by nothing until the "
        "creature drinks a full day's water",
        r"Exhaustion caused by dehydration can.t be removed until the creature drinks the "
        r"full amount of water required for a day",
    ),
    (
        185,
        "as do malnutrition's. Three different removal rules over one integer is why #178 "
        "clause 3 is a design question rather than a field",
        r"Exhaustion caused by malnutrition can.t be removed until the creature eats the "
        r"full amount of food required for a day",
    ),
    (
        189,
        "how long a creature holds its breath — 1 plus its Constitution modifier in "
        "MINUTES, with a floor of 30 seconds that an integer-minutes clock cannot hold",
        r"A creature can hold its breath for a number of minutes equal to 1 plus its "
        r"Constitution modifier \(minimum of 30 seconds\) before suffocation begins",
    ),
    (
        194,
        "a contagion SUPPRESSES the general removal rule outright rather than locking its "
        "own levels — while any Exhaustion is held, a Long Rest reduces none of it. A third "
        "removal shape, and the one that cannot be expressed by marking levels (#180)",
        r"While the creature has any Exhaustion levels, finishing a Long Rest neither "
        r"restores lost Hit Points nor reduces the creature.s Exhaustion level",
    ),
    (
        236,
        "and a Potion of Vitality removes ANY levels regardless of source, which the "
        "dehydration and malnutrition locks say cannot happen. The document states both and "
        "reconciles neither (#182)",
        r"it removes any Exhaustion levels you have and ends the Poisoned condition on you",
    ),
    # --- The five hazards (#140) -------------------------------------------------------
    # Asserted ahead of any implementation, because the OCCASION each one fires on is the
    # design question and it should be settled against the sentences rather than against a
    # memory of them. Three different occasions and one non-occasion turn up below.
    (
        178,
        "Burning fires at the START of a turn — the same phase the death save needs (#124) "
        "and the one this engine does not have",
        r"A burning creature or object takes 1d4 Fire damage at the start of each of its "
        r"turns",
    ),
    (
        189,
        "Suffocation fires at the END of a turn — the phase that does exist (0023)",
        r"it gains 1 Exhaustion level at the end of each of its turns",
    ),
    (
        181,
        "Dehydration fires at the END OF A DAY, on the campaign axis (0020), and inflicts "
        "Exhaustion with no save",
        r"A creature that drinks less than half the required water for a day gains 1 "
        r"Exhaustion level at the day.s end",
    ),
    (
        185,
        "Malnutrition fires on the same axis but IS a save — DC 10 Constitution — which is "
        "why the two cannot share one implementation",
        r"must succeed on a DC 10 Constitution saving throw or gain 1 Exhaustion level at "
        r"the day.s end",
    ),
    (
        182,
        "Falling is not an occasion at all: it resolves on landing, with damage per 10 feet "
        "to a cap, and NO d20 test — which is the shape core.adjudicate cannot express",
        r"takes 1d6 Bludgeoning damage at the end of the fall for every 10 feet it fell, to "
        r"a maximum of 20d6",
    ),
    (
        182,
        "and Falling's Prone is conditional on having taken damage, not on having fallen",
        r"When the creature lands, it has the Prone condition unless it avoids taking any "
        r"damage from the fall",
    ),
    (
        213,
        "a weapon bonus applies to attack rolls AND damage rolls, not one of them",
        r"You gain a \+1 bonus to attack rolls and damage rolls made with this magic weapon",
    ),
    (
        32,
        "a die may be rolled after a failed test and added to the d20",
        r"the creature can roll the Bardic Inspiration die and add the number rolled to "
        r"the d20, potentially turning the failure into a success",
    ),
    (
        88,
        "the same shape applies as a bonus OR a penalty",
        r"you can roll 2d4 and apply the total rolled as a bonus or penalty to the d20 roll",
    ),
    (
        88,
        "a missed attack may be overridden to a hit",
        r"When you miss with an attack roll, you can hit instead",
    ),
    (
        258,
        "and a failed save to a success — the same shape, a different test kind",
        r"If the aboleth fails a saving throw, it can choose to suc-?\s*ceed instead",
    ),
    (
        17,
        "damage modifiers apply in a fixed order: adjustments, Resistance, Vulnerability",
        r"adjustments such as bonuses, penalties, or multipliers are applied first; "
        r"Resistance is applied second; and Vulnerability is applied third",
    ),
    (
        17,
        "the document's worked example rounds AT the halving, and lands on 22",
        r"the damage is first reduced by 5 \(to 23\), then halved for the creature.s "
        r"Resistance \(and rounded down to 11\), then doubled for its Vulnerability \(to 22\)",
    ),
    (
        17,
        "Resistance and Vulnerability do not stack with themselves",
        r"Multiple instances of Resistance or Vulnerability that affect the same damage "
        r"type count as only one instance",
    ),
    (
        187,
        "Resistance halves and rounds down, once per instance of damage",
        r"damage of that type is halved against you \(round down\)\.\s*Resistance is "
        r"applied only once to an instance of damage",
    ),
    (
        191,
        "Vulnerability doubles, once per instance of damage",
        r"damage of that type is doubled against you\.\s*Vulnerability is applied only "
        r"once to an instance of damage",
    ),
    (
        183,
        "Immunity is not a reduction",
        r"If you have Immunity to a damage type or a condition, it doesn.t affect you in any way",
    ),
    (
        180,
        "damage types carry no rules of their own; other rules key off them",
        r"Damage types have no rules of their own, but other rules, such as Resistance, "
        r"rely on the types",
    ),
    (
        89,
        "Finesse offers Strength or Dexterity, and the same modifier for both rolls",
        r"use your choice of your Strength or Dexterity modifier for the attack and damage "
        r"rolls\.\s*You must use the same modifier for both rolls",
    ),
    (
        89,
        "Heavy names a SCORE of 13, and a different ability for melee and ranged",
        r"Disadvantage on attack rolls with a Heavy weapon if it.s a Melee weapon and your "
        r"Strength score isn.t at least 13 or if it.s a Ranged weapon and your Dexterity "
        r"score isn.t at least 13",
    ),
    (
        90,
        "Versatile applies only to a two-handed melee attack",
        r"The weapon deals that damage when used with two hands to make a melee attack",
    ),
    (
        90,
        "Graze deals the ability modifier on a miss, and nothing else may raise it",
        r"If your attack roll with this weapon misses a creature, you can deal damage to "
        r"that creature equal to the ability modifier you used to make the attack roll",
    ),
    (
        90,
        "and Graze damage is the weapon's own type",
        r"This damage is the same type dealt by the weapon, and the damage can be increased "
        r"only by increasing the ability modifier",
    ),
    (
        188,
        "Speed is the distance a creature covers when it moves ON ITS TURN",
        r"A creature has a Speed, which is the distance in feet the creature can cover "
        r"when it moves on its turn",
    ),
    (
        181,
        "Difficult Terrain costs 1 extra foot per foot, and does not stack with itself",
        r"every foot of movement in that space costs 1 extra foot.{0,140}Difficult Terrain "
        r"isn.t cumulative; either a space is Difficult Terrain or it isn.t",
    ),
    (
        178,
        "climbing costs 1 extra foot, waived by a Climb Speed",
        r"While you.re climbing, each foot of movement costs 1 extra foot \(2 extra feet in "
        r"Difficult Terrain\)\.\s*You ignore this extra cost if you have a Climb Speed",
    ),
    (
        189,
        "swimming says the same, waived by a Swim Speed",
        r"While you.re swimming, each foot of movement costs 1 extra foot \(2 extra feet in "
        r"Difficult Terrain\)\.\s*You ignore this extra cost if you have a Swim Speed",
    ),
    (
        179,
        "crawling says the same, and has no speed to waive it",
        r"While you.re crawling, each foot of movement costs 1 extra foot \(2 extra feet in "
        r"Difficult Terrain\)",
    ),
    (
        186,
        "a creature reaches 5 feet unless a rule says otherwise",
        r"A creature has a reach of 5 feet unless a rule says otherwise",
    ),
    (
        14,
        "a move may be broken up around actions",
        r"You can break up your move, using some of its movement before and after any action",
    ),
    (
        90,
        "beyond normal range is Disadvantage; beyond long range there is no attack",
        r"When attacking a target beyond normal range, you have Disadvantage on the attack "
        r"roll\.\s*You can.t attack a target beyond the long range",
    ),
    (
        177,
        "an area of effect has a point of origin, and there are six shapes",
        r"An area of effect has a point of origin, a location from which the effect.s "
        r"energy erupts",
    ),
    (
        177,
        "a blocked location is excluded — the rule this engine does NOT implement (#91)",
        r"If all straight lines extending from the point of origin to a location in the "
        r"area of effect are blocked, that location isn.t included in the area of effect\."
        r"\s*To block a line, an obstruction must provide Total Cover",
    ),
    (
        188,
        "a Sphere extends in all directions and INCLUDES its origin",
        r"A Sphere.s point of origin is included in the Sphere.s area of effect",
    ),
    (
        180,
        "a Cylinder's origin is at the centre of a circular face, and is included",
        r"a point of origin located at the center of the circular top or bottom of the "
        r"Cylinder.{0,180}A Cylinder.s point of origin is included in the area",
    ),
    (
        179,
        "a Cone's width equals the distance, and its origin is EXCLUDED by default",
        r"A Cone.s width at any point along its length is equal to that point.s distance "
        r"from the point of origin.{0,260}A Cone.s point of origin isn.t included in the "
        r"area of effect unless its creator decides otherwise",
    ),
    (
        179,
        "a Cube's origin sits on a face, and is excluded by default",
        r"a point of origin located anywhere on a face of the Cube.{0,160}A Cube.s point of "
        r"origin isn.t included in the area of effect unless its creator decides otherwise",
    ),
    (
        184,
        "a Line has a length and a width, and excludes its origin by default",
        r"A Line.s point of origin isn.t included in the area of effect unless its creator "
        r"decides otherwise",
    ),
    (
        181,
        "an Emanation moves with its source and excludes it by default",
        r"An Emanation moves with the creature or object that is its origin.{0,120}"
        r"An Emanation.s origin \(creature or object\) isn.t included in the area of effect",
    ),
    (
        186,
        "Prone gives Advantage within 5 feet and DISADVANTAGE beyond — both directions",
        r"An attack roll against you has Advantage if the attacker is within 5 feet of "
        r"you\.\s*Otherwise, that attack roll has Disadvantage",
    ),
    (
        191,
        "Unconscious carries both Incapacitated and Prone",
        r"You have the Incapacitated and Prone conditions",
    ),
    (
        184,
        "Incapacitated stops actions, bonus actions and reactions, and breaks Concentration",
        r"You can.t take any action, Bonus Action, or Reaction\..{0,80}Your Concentration "
        r"is broken",
    ),
    (
        181,
        "Exhaustion is cumulative, reduces D20 Tests by 2 per level, and kills at 6",
        r"You die if your Exhaustion level is 6\..{0,120}the roll is reduced by 2 times "
        r"your Exhaustion level",
    ),
    (
        181,
        "and reduces Speed by 5 feet per level",
        r"Your Speed is reduced by a number of feet equal to 5 times your Exhaustion level",
    ),
    (
        182,
        "Grappled spares the grappler from the attack penalty",
        r"You have Disadvantage on attack rolls against any target other than the grappler",
    ),
    (
        186,
        "Paralyzed hands out automatic Critical Hits within 5 feet",
        r"Any attack roll that hits you is a Critical Hit if the attacker is within 5 feet",
    ),
    (
        187,
        "Restrained only hampers Dexterity saves, where four others fail them outright",
        r"You have Disadvantage on Dexterity saving throws",
    ),
    (
        182,
        "Frightened's penalty is qualified by line of sight — the clause not enforced",
        r"You have Disadvantage on ability checks and attack rolls while the source of fear "
        r"is within line of sight",
    ),
    (
        176,
        "one action per turn",
        r"On your turn, you can take one action",
    ),
    (
        177,
        "a Bonus Action exists only if a rule grants one, and only one per turn",
        r"You can.t take more than one Bonus Action on a turn, and you have a Bonus Action "
        r"to take only if a rule explicitly says so",
    ),
    (
        186,
        "a Reaction is free of the other two and refreshes at the START OF YOUR NEXT TURN",
        r"you can do so even if you also take an action, a Bonus Action, or both\.\s*Once "
        r"you take a Reaction, you can.t take another one until the start of your next turn",
    ),
    (
        180,
        "Dash grants extra movement equal to Speed after modifiers",
        r"you gain extra movement for the current turn\.\s*The increase equals your Speed "
        r"after applying any modifiers",
    ),
    (
        181,
        "Dodge lasts until the start of your next turn and is lost to Speed 0",
        r"until the start of your next turn, any attack roll made against you has "
        r"Disadvantage if you can see the attacker, and you make Dexterity saving throws "
        r"with Advantage\.\s*You lose these benefits if you have the Incapacitated "
        r"condition or if your Speed is 0",
    ),
    (
        181,
        "Disengage lasts only for the rest of the current turn",
        r"your movement doesn.t provoke Opportunity Attacks for the rest of the current turn",
    ),
    (
        185,
        "an Opportunity Attack costs a Reaction — the trigger this engine does not detect",
        r"You can make an Opportunity Attack when a creature that you can see leaves your "
        r"reach.{0,140}take a Reaction to make one melee attack",
    ),
    (
        104,
        "the spell-level range, stated outright — 0 to 9. This is what MAX_SPELL_LEVEL "
        "rests on; #130 found it citing p. 26's class table instead, which the module "
        "deliberately ships none of",
        r"Every spell has a level from 0 to 9",
    ),
    (
        104,
        "a spell expends a slot of its own level OR HIGHER",
        r"When you cast a spell, you expend a slot of that spell.s level or higher",
    ),
    (
        104,
        "a Long Rest restores every expended slot",
        r"Finishing a Long Rest restores any expended spell slots",
    ),
    (
        178,
        "a cantrip is level 0 and costs no slot",
        r"A cantrip is a level 0 spell, which is cast without a spell slot",
    ),
    (
        106,
        "the spell save DC is 8 plus the ability modifier plus proficiency",
        r"Spell save DC = 8 \+ your spellcasting ability modifier \+ your Proficiency Bonus",
    ),
    (
        106,
        "and the spell attack modifier is the same without the 8",
        r"Spell attack modifier = your spellcasting ability modifier \+ your Proficiency Bonus",
    ),
    (
        179,
        "starting another Concentration effect ends the first, at the moment casting starts",
        r"You lose Concentration on an effect the moment you start casting a spell that "
        r"requires Concentration",
    ),
    (
        179,
        "the Concentration save DC has BOTH a floor of 10 and a cap of 30",
        r"The DC equals 10 or half the damage taken \(round down\), whichever number is "
        r"higher, up to a maximum DC of 30",
    ),
    (
        179,
        "Incapacitated ends Concentration with no save at all",
        r"Your Concentration ends if you have the Incapacitated condition or you die",
    ),
    (
        176,
        "the Rules Glossary states the same cancellation rule",
        r"Advantage and Dis-?\s*advantage on the same roll cancel each other",
    ),
    (
        181,
        "the glossary's Disadvantage entry agrees with its Advantage entry",
        r"roll two d20s and use the lower roll\. A roll can.t be affected by more than one "
        r"Disadvantage",
    ),
    # --- Time (#85, decisions 0020 and 0021) ----------------------------------------
    (
        13,
        "a round represents *about* 6 seconds — the hedge that describes the fiction",
        r"A round represents about 6 seconds in the game world",
    ),
    (
        98,
        "and the exact conversion the document performs when a rule needs one: 2 rounds "
        "is 12 seconds, so a round is 6 (decision 0021, amending 0020 clause 1)",
        r"2 rounds from when the oil was lit \(or 12 seconds\)",
    ),
    # --- Condition duration (#18) ---------------------------------------------------
    (
        106,
        "a Time Span duration is stated in rounds or in minutes — one taxonomy, several "
        "units, which is why a duration names its own axis",
        r"A duration that provides a time span specifies how long the spell lasts in "
        r"rounds, minutes, hours, or the like",
    ),
    (
        98,
        "counting rounds from an event runs to the end of that turn N rounds later, which "
        "is the only place the document says what that means",
        r"burns until the end of the turn 2 rounds from when the oil was lit",
    ),
    (
        191,
        "Unconscious leaves the creature Prone when it ends, so Prone does not lift with "
        "the condition that was implying it",
        r"When this condition ends, you remain Prone",
    ),
    (
        63,
        "the save-ends shape is stated per-effect, with its own ability and DC — there is "
        "no general rule to read them from",
        r"repeats the save at the end of each of its turns, ending the effect on itself "
        r"on a success",
    ),
    (
        18,
        "a Stable creature regains 1 hit point after 1d4 hours",
        r"A Stable creature that isn.t healed regains 1 Hit Point after 1d4 hours",
    ),
    (
        187,
        "a Short Rest is one hour",
        r"A Short Rest is a 1-hour period of downtime",
    ),
    (
        185,
        "a Long Rest is at least eight hours",
        r"A Long Rest is a period of extended downtime.at least 8 hours",
    ),
    (
        185,
        "sixteen hours must pass before another Long Rest may start",
        r"you must wait at least 16 hours before starting another one",
    ),
)


def normalise(text: str) -> str:
    """Rejoin hyphenated line breaks, then flatten whitespace.

    The document hyphenates across column breaks, so the operative sentence of the
    cancellation rule is physically `Advan-\\ntage and Disadvantage`. Matching the raw text
    would mean encoding this edition's line breaks into the patterns, which would go red on
    a reflow that changed nothing a reader would notice.
    """
    return re.sub(r"\s+", " ", re.sub(r"-\s*\n\s*", "", text))


def page_text(pdf: Path) -> dict[int, str]:
    """Normalised text per printed page number."""
    try:
        import pymupdf
    except ImportError:  # pragma: no cover - developer-machine tooling
        raise SystemExit(
            "pymupdf is required to verify against the PDF: pip install pymupdf"
        ) from None

    with pymupdf.open(pdf) as doc:
        return {
            index + PAGE_OFFSET: normalise(doc[index].get_text()) for index in range(doc.page_count)
        }


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit(f"usage: {argv[0]} /path/to/SRD_CC_v5.2.1.pdf")

    pdf = Path(argv[1])
    if not pdf.is_file():
        raise SystemExit(f"no such file: {pdf}")

    pages = page_text(pdf)
    failures: list[str] = []

    for printed, settles, pattern in CLAUSES:
        text = pages.get(printed)
        if text is None:
            failures.append(f"p. {printed}: no such page in this document")
            continue
        if not re.search(pattern, text):
            failures.append(f"p. {printed}: no match for {settles!r}\n    pattern: {pattern}")
        else:
            print(f"  ok  p. {printed:>3}  {settles}")

    if failures:
        raise SystemExit(
            "\nthe cited text no longer matches the document:\n\n"
            + "\n".join(failures)
            + "\n\ncore.d20 and core.death rest on these sentences. Re-read the "
            "document before touching the implementation to make this pass."
        )

    print(f"\nall {len(CLAUSES)} clauses verified against {pdf.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
