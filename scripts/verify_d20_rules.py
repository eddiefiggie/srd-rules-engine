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
        17,
        "p. 17's Instant Death has THREE clauses, and the third has no antecedent: nothing "
        "in this engine reduces a hit point maximum, so 'reaches 0' is unreachable rather "
        "than unbuilt (#426)",
        r"Hit Point Maximum of 0\.\s*A creature dies if its Hit Point maximum reaches 0",
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
    # --- Where the light rules actually live (#228, 0033 clause 3) ---------------------
    # p. 11, *Vision and Light -> Light*. The Rules Glossary is an index into the rules and
    # not the boundary of one, and this block is the evidence: the glossary repeats **some**
    # of these consequences on pp. 180 and 181, and does not repeat Bright Light's. So the
    # three sentences are asserted here as well as there, deliberately — the redundancy is
    # what shows the pattern rather than merely pinning the fact.
    #
    # 0033 clause 3 makes this obligatory rather than tidy: `bright-light` is claimed on
    # text outside its own entry, so the page is cited and the sentence asserted, or the
    # published coverage figure moves on reasoning that decays in a commit message.
    (
        11,
        "Bright Light lets most creatures see normally — the mechanic p. 178's entry points "
        "at and does not state, and the sentence `bright-light`'s claim rests on (0033)",
        r"Bright Light lets most creatures see normally",
    ),
    (
        11,
        "Dim Light creates a Lightly Obscured area — the same rule p. 181 repeats, asserted "
        "in both places to show the glossary is an index rather than the boundary",
        r"Dim Light, also called shadows, creates a Lightly Obscured area",
    ),
    (
        11,
        "Darkness creates a Heavily Obscured area — the same rule p. 180 repeats",
        r"Darkness creates a Heavily Obscured area",
    ),
    # --- The nine sight shapes (#150, 0025 clause 5) ---------------------------------
    # These are the rule values `core.sight` refused to state until they were read. Each is
    # the sentence one row of the mapping rests on.
    (
        178,
        "the glossary entry for Bright Light names no obscurement, which is why "
        "Obscurement.NONE is this engine's absence rather than a glossary term — the "
        "mechanic itself is p. 11's sentence above (0033 supersedes the reading that this "
        "entry's silence meant the shape had no consequence to produce)",
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
    # --- The Perception check that finally reads obscurement (#138) ---------------------
    # p. 184's Disadvantage was produced by nothing until these were composed. The third
    # clause is the one an implementer drops: p. 182 says a CONDITION applies, and what that
    # condition costs a check is p. 177's sentence, not p. 182's.
    (
        177,
        "Blinded does not merely obscure — it AUTOMATICALLY FAILS a check that needs sight, "
        "which is what makes p. 182's Heavily Obscured an outcome rather than a penalty",
        r"You can.t see and automatically fail any ability check that requires sight",
    ),
    (
        188,
        "a skill is an area of specialization, and proficiency in one ADDS the Proficiency "
        "Bonus to an ability check associated with it",
        r"If you have proficiency in a skill, you can add your Proficiency Bonus when you "
        r"make an ability check associated with that skill",
    ),
    (
        186,
        "and proficiency comes in FOUR kinds, which is why the `proficiency` shape stays "
        "unclaimed with two of them modelled (#138)",
        r"A creature might have proficiency in a skill or saving throw or with a weapon or "
        r"tool",
    ),
    (
        9,
        "the Skills table pairs Perception with WISDOM — the pairing is the mechanical half, "
        "and a set of names without it leaves every caller recalling which ability applies",
        r"Perception Wisdom Using a combination of senses, notice something that.s easy to "
        r"miss",
    ),
    (
        187,
        "the Search action is the occasion: a Wisdom check to discern something that isn't "
        "obvious, with Perception the skill for a concealed creature",
        r"When you take the Search action, you make a Wisdom check to discern something "
        r"that isn.t obvious",
    ),
    (
        186,
        "Passive Perception is 10 + the check bonus, shifted 5 by Advantage or Disadvantage "
        "— and the worked example is 14 for Wisdom 15 with proficiency at level 1",
        r"a level 1 character with a Wisdom of 15 and proficiency in Perception has a "
        r"Passive Perception of 14 \(10 \+ 2 \+ 2\)",
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
    (
        179,
        "a condition is binary and Exhaustion is the stated exception — which is why a "
        "creature frightened by two things has ONE Frightened condition with two sources, "
        "and why 0028 gave Exhaustion levels rather than a flag (#192)",
        r"A condition doesn.t stack with itself; a recipient either has a condition or "
        r"doesn.t\.\s*The Exhaustion condition is an exception to that rule",
    ),
    # --- What the document does NOT say about sight (#166) ------------------------------
    (
        172,
        "Wall of Force is INVISIBLE while giving Total Cover — the counter-example that "
        "makes any single global answer wrong, whichever way it went (#188)",
        r"An Invisible wall of force springs into existence at a point you choose within "
        r"range",
    ),
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
    # --- Flying, and what brings a flyer down ---------------------------------------------
    (
        182,
        "a flyer falls on Incapacitated, on Prone, or on a Fly Speed reduced to 0 — and "
        "hovering is the single exception to all three",
        r"While flying, you fall if you have the Incapacitated or Prone condition or your "
        r"Fly Speed is reduced to 0\.\s*You can stay aloft in those circumstances if you "
        r"can hover",
    ),
    (
        182,
        "and otherwise a Fly Speed keeps you up until something ends it",
        r"While you have a Fly Speed, you can stay aloft until you land, fall, or die",
    ),
    (
        179,
        "a Climb Speed removes the extra cost rather than adding a speed — which is what "
        "movement_cost already implements",
        r"A Climb Speed can be used in place of Speed to traverse a vertical surface "
        r"without expending the extra movement normally associated with climbing",
    ),
    (
        189,
        "and a Swim Speed says the same for water",
        r"A Swim Speed can be used to swim without expending the extra movement normally "
        r"associated with swimming",
    ),
    (
        178,
        "a Burrow Speed moves through sand, earth, mud or ice and NOT solid rock — the "
        "clause that keeps this shape unclaimed, because no medium is modelled",
        r"can use that speed to move through sand, earth, mud, or ice\.\s*The creature "
        r"can.t burrow through solid rock unless the creature has a trait that allows it to "
        r"do so",
    ),
    # --- Jumping ------------------------------------------------------------------------
    (
        184,
        "a Long Jump is the Strength SCORE in feet, and needs a 10-foot run-up",
        r"When you make a Long Jump, you leap horizontally a number of feet up to your "
        r"Strength score if you",
    ),
    (
        185,
        "standing halves it, every foot costs a foot of movement, and landing in Difficult "
        "Terrain is a DC 10 Dexterity (Acrobatics) check or Prone",
        r"When you make a standing Long Jump, you can leap only half that distance\.\s*"
        r"Either way, each foot you jump costs a foot of movement\.\s*If you land in "
        r"Difficult Terrain, you must succeed on a DC 10 Dexterity \(Acrobatics\) check or "
        r"have the Prone condition",
    ),
    (
        183,
        "a High Jump is 3 plus the Strength MODIFIER, floored at 0 — a different number "
        "from the Long Jump's, and the pair is easy to conflate",
        r"you leap into the air a number of feet equal to 3 plus your Strength modifier "
        r"\(minimum of 0 feet\) if you move at least 10 feet on foot immediately before the "
        r"jump",
    ),
    (
        183,
        "and its reach adds one and a half times the creature's HEIGHT, which this engine "
        "does not model — so the High Jump shape stays unclaimed",
        r"you can reach a distance equal to the height of the jump plus 1.{0,3}. times your "
        r"height",
    ),
    # --- Longer casting times (#250, 0065) ----------------------------------------------
    (
        105,
        "a casting time is one of four things, and the fourth is measured in time rather "
        "than in a slice of a turn",
        r"Most spells require the Magic action to cast, but some spells require a Bonus "
        r"Action, a Reaction, or 1 minute or more",
    ),
    (
        105,
        "**a Ritual is one of the longer casting times**, which is the sentence that makes "
        "p. 187's ten extra minutes a thing the turn loop charges rather than a number the "
        "engine merely computes. Unasserted until #371, and the clause that whole issue "
        "rests on — `core.casting` quoted it in a docstring while the verifier had never "
        "read it",
        r"Certain spells.{0,3}including a spell cast as a Ritual.{0,3}require more time to "
        r"cast: minutes or even hours",
    ),
    (
        105,
        "a casting of a minute or more owes the Magic action on EACH turn, and "
        "Concentration throughout",
        r"While you cast a spell with a casting time of 1 minute or more, you must take the "
        r"Magic action on each of your turns, and you must maintain Concentration",
    ),
    (
        105,
        "and the clause that decides when the slot leaves the caster: a broken "
        "Concentration expends none, so it cannot have been spent when the casting began",
        r"If your Concentration is broken, the spell fails, but you don.t expend a spell "
        r"slot\.\s*To cast the spell again, you must start over",
    ),
    # --- What may be targeted at all (#20) ----------------------------------------------
    (
        105,
        "a spell's range takes one of three forms, and only one of them is a number — "
        "Touch is the caster's reach and Self is the caster",
        r"A range usually takes one of the following forms: Distance\.\s*The range is "
        r"expressed in feet\.\s*Touch\.\s*The spell.s effect originates on something, as "
        r"defined by the spell, that the spellcaster must touch within their reach\.\s*"
        r"Self\.",
    ),
    (
        105,
        "and a movable effect is NOT re-checked against the range once cast, which is the "
        "clause an implementation adds by accident",
        r"If a spell has movable effects, they aren.t restricted by its range unless the "
        r"spell.s description says otherwise",
    ),
    # --- Dehydration and Malnutrition (#315) ---------------------------------------------
    (
        181,
        "Dehydration: a size-keyed requirement, **less than half** a day's water, one level "
        "at the day's end, and no die — which is what makes it bookkeeping rather than an "
        "adjudication (0080)",
        r"A creature that drinks less than half the required water for a day gains 1 "
        r"Exhaustion level at the day.s end\.\s*Exhaustion caused by dehydration can.t be "
        r"removed until the creature drinks the full amount of water required for a day",
    ),
    (
        181,
        "the Water Needs per Day table, whose quarter-gallon is why the engine holds these as "
        "fractions: half of a quarter is an eighth, and no binary float holds either",
        r"Tiny 1/4 gallon Small 1 gallon Medium 1 gallon",
    ),
    (
        185,
        "Malnutrition is **two rules, not one** — a DC 10 Constitution save for eating too "
        "little, and an *automatic* level after five days with nothing. 0027 clause 8 called "
        "it an outcome and Dehydration bookkeeping; the second half is bookkeeping too (#399)",
        r"must succeed on a DC 10 Constitution saving throw or gain 1 Exhaustion level at the "
        r"day.s end\.\s*A creature that eats nothing for 5 days automatically gains 1 "
        r"Exhaustion level at the end of the fifth day",
    ),
    # --- Armour training (#367) ----------------------------------------------------------
    (
        177,
        "p. 177's Armor Training entry **whole**, and both of the drawbacks this engine had "
        "already built: the Disadvantage on **any D20 Test** involving Strength or Dexterity "
        "(0064) and the casting prohibition (0063). **Neither sentence was asserted anywhere "
        "until #367**, so two shipped rules rested on a page nobody had read — the case the "
        "standing rule added at build 08302026.32 is about",
        r"If you wear Light, Medium, or Heavy armor and lack training with it, you have "
        r"Disadvantage on any D20 Test that involves Strength or Dexterity, and you can.t "
        r"cast spells\.\s*If you use a Shield and lack training with it, you don.t gain its "
        r"AC bonus",
    ),
    (
        92,
        'the same drawbacks in "Equipment", where the Shield clause is its own paragraph — '
        "and the sentence that makes the *category* content this repository does not ship: a "
        "character's class determines training, and a monster's stat block does",
        r"A character.s class and other features determine the character.s armor training\. "
        r"A monster has training with any armor in its stat block",
    ),
    # --- Armour Class (#380) -------------------------------------------------------------
    (
        177,
        "the base AC calculation, and the clause that makes armour an **alternative** rather "
        "than an addition: another calculation is *chosen between*, never combined. This is "
        "the structure #380 turns on, and it is stated rather than inferred (0077)",
        r"Your base AC calculation is 10 plus your Dexterity modifier\.\s*If a rule gives "
        r"you another base AC calculation, you choose which calculation to use; you can.t "
        r"use more than one",
    ),
    (
        92,
        "a Shield's AC benefit is **conditional on training**, which is the half of #367 "
        "that waits on AC being derived — there is no bonus to withhold from a stored total",
        r"You gain the Armor Class benefit of a Shield only if you have training with it",
    ),
    (
        92,
        "one suit and one Shield, which is what makes the base a single choice rather than a "
        "set to be summed",
        r"A creature can wear only one suit of armor at a time and wield only one Shield at "
        r"a time",
    ),
    (
        92,
        "a monster's training comes from its stat block, so a stat-block AC is not an "
        "unverified number — it is the other base calculation p. 177 permits",
        r"A monster has training with any armor in its stat block",
    ),
    # --- Improvised weapons (#264) -------------------------------------------------------
    (
        183,
        "an improvised weapon is a **use rather than an object** — a Simple or Martial "
        "weapon counts as one when wielded contrary to its design, which is why this cannot "
        "be a flag on the item (0076)",
        r"A Simple or Martial weapon also counts as an improvised weapon if it.s wielded in "
        r"a way contrary to its design",
    ),
    (
        183,
        "the Proficiency Bonus is **not added**, which is a prohibition rather than a "
        "proficiency the wielder happens to lack — so there is no branch for a creature that "
        "has one",
        r"Don.t add your Proficiency Bonus to attack rolls with an improvised weapon",
    ),
    (
        183,
        "1d4, and a damage type **the document hands to a person** — the one rule here the "
        "engine may not supply, and the reason `Item.improvised_damage_type` exists",
        r"the weapon deals 1d4 damage of a type the GM thinks is appropriate for the object",
    ),
    (
        183,
        "a thrown improvised weapon is 20/60 — asserted so the number is read rather than "
        "recalled when #390 builds the throw",
        r"If you throw the weapon, it has a normal range of 20 feet and a long range of 60 "
        r"feet",
    ),
    # --- Initiative (#385) --------------------------------------------------------------
    (
        13,
        "initiative is a **Dexterity check**, which is what lets `initiative_order` carry a "
        "verified default instead of asking a caller which ability to roll — a caller "
        "choosing the ability is a caller choosing the modifier (0026's dial)",
        r"every participant rolls Initiative; they make a Dexterity check that determines "
        r"their place in the Initiative order",
    ),
    (
        13,
        "the order is ranked highest to lowest and **stays the same from round to round**, "
        "which is what `EncounterState.with_initiative` sorts once and never re-sorts",
        r"ranks the combatants, from highest to lowest Initiative\.\s*This is the order in "
        r"which they act during each round\.\s*The Initiative order remains the same from "
        r"round to round",
    ),
    (
        13,
        "**ties are a person's to break**, and the document says so in three clauses rather "
        "than leaving it open. This engine has no person, so its insertion order is a "
        "convention it declares rather than a rule it implements (0075)",
        r"If a tie occurs, the GM decides the order among tied monsters, and the players "
        r"decide the order among tied characters\.\s*The GM decides the order if the tie is "
        r"between a monster and a player character",
    ),
    (
        184,
        "the glossary's Initiative entry, including the **score** variant a GM may use "
        "instead of rolling — modelled by nothing here, and disclosed rather than silently "
        "absent",
        r"Your Initiative score equals 10 plus your Dexterity modifier\. If you have "
        r"Advantage on Initiative rolls, increase your Initiative score by 5",
    ),
    # --- Rituals and preparation (#19) --------------------------------------------------
    (
        187,
        "a Ritual needs the spell PREPARED and tagged, costs 10 minutes more, and expends "
        "no slot — and the consequence the document draws itself, which an implementer "
        "drops: no slot means no upcasting",
        r"If you have a spell prepared that has the Ritual tag, you can cast that spell as "
        r"a Ritual\.\s*The Ritual version of a spell takes 10 minutes longer to cast than "
        r"normal\.\s*It also doesn.t expend a spell slot, which means the ritual version of "
        r"a spell can.t be cast at a higher level",
    ),
    (
        104,
        "WHEN a prepared list may change, and how many, is the spellcasting feature's to "
        "say — class data this engine ships none of, the way it ships no slot table",
        r"your spellcasting feature specifies when you can change the list and the number "
        r"of spells you can change",
    ),
    (
        104,
        "an always-prepared spell is prepared, and only the CHANGE LIMIT treats it "
        "differently — so castability needs one set, not two",
        r"a spell that you always have prepared doesn.t count against the number of spells "
        r"on that list",
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
        "and it restores every lost hit point AND every spent Hit Point Die — one sentence "
        "carrying two benefits, of which the engine expressed only the first until #407. "
        "The third clause of it, a reduced maximum returning to normal, has no antecedent: "
        "nothing here reduces one",
        r"Regain All HP\.\s*You regain all lost Hit Points and all spent Hit Point Dice",
    ),
    # --- p. 14's Creature Size and Space, and the two occupancy entries (#337, 0084) ----
    (
        14,
        "a size determines the WIDTH OF A SQUARE SPACE, and the second sentence is what "
        "bounds the field's reach: a space is what a creature CONTROLS, not a volume it "
        "displaces — which is why it answers occupancy and not distance",
        r"A creature belongs to a size category, which determines the width of the square "
        r"space the creature occupies on a map",
    ),
    (
        14,
        "and the table itself, with Tiny at TWO AND A HALF feet — the row that decides the "
        "type, since an int loses the half and a float rounds it",
        r"Tiny 2. by 2. feet",
    ),
    (
        185,
        "a space is occupied if a creature is in it OR if it is completely filled by objects "
        "— and the second clause is unbuilt, because this engine's objects are equipment "
        "rather than occupants (0084 clause 9, #451)",
        r"A space is occupied if a creature is in it or if it is completely filled by objects",
    ),
    (
        191,
        "and p. 191 states the negative in the same two terms",
        r"A space is unoccupied if no creatures are in it and it isn.t completely filled by "
        r"objects",
    ),
    # --- p. 16's Underwater Combat: asserted although unbuilt, so #446 does not re-read -
    (
        16,
        "the melee clause turns on a Swim Speed and exempts PIERCING weapons, and the ranged "
        "clause AUTOMATICALLY MISSES beyond normal range — which is neither Disadvantage nor "
        "a refusal, and is #224's unbuilt shape (#446)",
        r"A ranged attack roll with a weapon underwater automatically misses a target beyond "
        r"the weapon.s normal range, and the attack roll has Disadvantage against a target "
        r"within normal range",
    ),
    (
        16,
        "and everything underwater resists Fire, which `Defences` can already express",
        r"Fire Resistance Anything underwater has Resistance to Fire damage",
    ),
    # --- p. 190's Teleportation (#444), built once 0084 gave a creature a space ---------
    (
        190,
        "a teleport arrives instantly and traces NO line — the contrast with a walk and a "
        "push, whose lines `line_is_blocked` reads; `with_teleport` asks only about the "
        "arrival (#444)",
        r"If you teleport, you disappear and reappear elsewhere instantly, without moving "
        r"through the intervening space",
    ),
    (
        190,
        "a teleport expends NO movement and NEVER provokes an Opportunity Attack — both "
        "behavioural contrasts against `TurnLoop.move`, which spends a speed and offers the "
        "provocation; 'unless a rule tells you otherwise' has no rule in this engine to "
        "tell it (#444)",
        r"This transportation doesn.t expend movement unless a rule tells you otherwise, and "
        r"teleportation never provokes Opportunity Attacks",
    ),
    (
        190,
        "equipment travels with the creature, which holds by construction: it is a field on "
        "the creature and the creature is what moves",
        r"When you teleport, all the equipment you.re wearing and carrying teleports with you",
    ),
    (
        190,
        "a touched creature stays behind unless the effect says otherwise — touching is not "
        "a fact this engine holds, so the default applies and a passenger is the effect's "
        "own second effect (R32)",
        r"If you.re touching another creature when you teleport, that creature doesn.t "
        r"teleport with you unless the teleportation effect says otherwise",
    ),
    (
        190,
        "and its destination rule, which 0084's `is_unoccupied` answers: a taken destination "
        "diverts to the NEAREST unoccupied space, and 'of your choice' is the caller's — "
        "`with_teleport` checks the stated landing against `teleport_destinations` rather "
        "than trusting it or picking one",
        r"If the destination space of your teleportation is occupied by another creature or "
        r"blocked by a solid obstacle, you instead appear in the nearest unoccupied space of "
        r"your choice",
    ),
    (
        190,
        "whether the destination must be seen is the effect's to say — `can_see` relates two "
        "creatures rather than a creature and a point, and there are no spells (#21) whose "
        "descriptions could say it (R32)",
        r"The description of a teleportation effect tells you if you must see the "
        r"teleportation.s destination",
    ),
    # --- p. 187's Simultaneous Effects (#442) ------------------------------------------
    (
        187,
        "the person WHOSE TURN IT IS decides the order when two things coincide — so the "
        "engine taking `pending[0]` was choosing something the document gives away, and it "
        "is consequential: a death save and Burning's damage at one instant",
        r"If two or more things happen at the same time on a turn, the person at the game "
        r"table.player or GM.\s*whose turn it is decides the order in which those things "
        r"happen",
    ),
    # --- p. 189's Surprise (#440) ------------------------------------------------------
    (
        189,
        "Surprise's whole mechanic is Disadvantage on the INITIATIVE roll, and the entry "
        "states nothing else — no lost turn, no condition. It is also not one of the "
        "fifteen, which is why it lives on the creature rather than in `Conditions`",
        r"If a creature is caught unawares by the start of combat, that creature is "
        r"surprised, which causes it to have Disadvantage on its Initiative roll",
    ),
    # --- p. 180's Dead (#438) ----------------------------------------------------------
    (
        180,
        "a dead creature CANNOT REGAIN hit points, and the only exception is revival magic — "
        "which does not exist here, so the refusal is total and says so",
        r"A dead creature has no Hit Points and can.t regain them unless it is first revived "
        r"by magic such as the Raise Dead or Revivify spell",
    ),
    # --- p. 186's Ready: asserted although unbuilt, so #436 does not re-read it --------
    (
        187,
        "a readied spell is cast and PAID FOR now, holding only its energy — the reverse of "
        "0065's long cast, which spends its slot on completion. The two are opposite on the "
        "exact axis that record settled (#436)",
        r"When you Ready a spell, you cast it as normal \(expending any resources used to "
        r"cast it\) but hold its energy, which you release with your Reaction when the "
        r"trigger occurs",
    ),
    (
        187,
        "and holding it needs a Concentration bounded at a TURN BOUNDARY, which the built "
        "Concentration machinery does not attach to one — and a break makes the spell "
        "dissipate with no effect, which is #224's unbuilt shape",
        r"holding on to the spell.s magic requires Concentration, which you can maintain up "
        r"to the start of your next turn\.\s*If your Concentration is broken, the spell "
        r"dissipates without taking effect",
    ),
    (
        186,
        "the trigger is a PERCEIVABLE CIRCUMSTANCE, which is narrative — so the caller says "
        "when it fires, as it does a rest's interruption and a Cover degree",
        r"First, you decide what perceivable circumstance will trigger your Reaction",
    ),
    # --- p. 183's Help: asserted although unbuilt, so #434 does not re-read it ---------
    (
        183,
        "Help's ability-check half scopes its Advantage to a SKILL OR TOOL, which "
        "`PendingAdvantage.against_id` cannot express — it answers which target, not which "
        "skill — and tools are not modelled at all (#434)",
        r"That ally has Advantage on the next ability check they make with the chosen skill "
        r"or tool",
    ),
    (
        183,
        "and its attack half grants to an UNNAMED ally — the holder is whichever ally "
        "attacks first, where Vex grants to the attacker and Sap to the creature hit, both "
        "known when the token is made",
        r"giving Advantage to the next attack roll by one of your allies against that enemy",
    ),
    (
        183,
        "and the two expiries differ by a word: the ability-check benefit expires if unused "
        "BEFORE the start of your next turn, the attack benefit AT it",
        r"This benefit expires if the ally doesn.t use it before the start of your next turn",
    ),
    # --- p. 183's Hide (#432) ----------------------------------------------------------
    (
        183,
        "the DC is the document's, the skill is named rather than suggested, and BOTH "
        "conditions must hold — obscurement or Three-Quarters/Total Cover, AND out of any "
        "enemy's line of sight. Half Cover is not among the degrees named",
        r"you must succeed on a DC 15 Dexterity \(Stealth\) check while you.re Heavily "
        r"Obscured or behind Three-Quarters Cover or Total Cover, and you must be out of any "
        r"enemy.s line of sight",
    ),
    (
        183,
        "the check's TOTAL becomes the DC to find the hider, which is why the engine fills "
        "the number from the roll it just made rather than a resolver supplying one (R4)",
        r"Make note of your check.s total, which is the DC for a creature to find you with a "
        r"Wisdom \(Perception\) check",
    ),
    (
        183,
        "and the four endings, of which the engine observes two — an attack roll and a "
        "Verbal spell. Being found is a Perception check against the stored DC; a sound "
        "louder than a whisper is a narrative fact a caller states",
        r"You stop being hidden immediately after any of the following occurs: you make a "
        r"sound louder than a whisper, an enemy finds you, you make an attack roll, or you "
        r"cast a spell with a Verbal component",
    ),
    # --- p. 184's Knocking Out a Creature (#428) ---------------------------------------
    (
        184,
        "the subduing blow: MELEE only, and it leaves the creature at 1 rather than 0, which "
        "is why p. 17's Monster Death and Massive Damage both stop applying without a branch "
        "— each needs a reduction to 0 and there is none",
        r"When you would reduce a creature to 0 Hit Points with a melee attack, you can "
        r"instead reduce the creature to 1 Hit Point",
    ),
    (
        184,
        "and the recovery clause, which is NOT built: p. 191's Unconscious entry never says "
        "when the condition ends, so honouring this needs a condition to carry its cause",
        r"The creature remains Unconscious until it regains any Hit Points or until someone "
        r"uses an action to administer first aid to it, which requires a successful DC 10 "
        r"Wisdom \(Medicine\) check",
    ),
    # --- p. 182's Expertise (#424) -----------------------------------------------------
    (
        182,
        "the Proficiency BONUS is doubled, not the check — the arithmetic an implementation "
        "gets wrong by scaling whatever it has added up so far",
        r"When you make an ability check with a skill proficiency in which you have "
        r"Expertise, your Proficiency Bonus is doubled for that check",
    ),
    (
        182,
        "and it is granted only in a skill already held, which is why Expertise without "
        "proficiency is refused rather than quietly worth nothing",
        r"If you gain Expertise, you gain it in one skill in which you have proficiency",
    ),
    (
        182,
        "and it cannot be held twice, which the shape of a set makes unrepresentable rather "
        "than needing a guard",
        r"You can.t have Expertise in the same skill proficiency more than once",
    ),
    # --- p. 197's four exposures: asserted although unbuilt, so #141 does not re-read ---
    (
        197,
        "Injury poison's exposure is a DAMAGE TYPE condition, which this engine already "
        "resolves — so it needs no memory-port fact at all, and #141's blocker does not "
        "reach it",
        r"A creature that takes Piercing or Slashing damage from an object coated with the "
        r"poison is exposed to its effects",
    ),
    (
        197,
        "and it states its own action cost, which is a Bonus Action the engine models",
        r"Injury poison can be applied as a Bonus Action to a weapon, a piece of ammunition, "
        r"or similar object",
    ),
    (
        197,
        "Inhaled poison's exposure is an AREA and a duration, not a fact: a 5-foot Cube whose "
        "cloud dissipates immediately",
        r"Blowing the powder or releasing the gas subjects creatures in a 5-foot Cube to its "
        r"effect\.\s*The resulting cloud dissipates immediately afterward",
    ),
    (
        197,
        "an explicit NON-interaction with p. 189's breath-holding, which this engine models — "
        "connecting the two is the obvious and wrong inference",
        r"Holding one.s breath is ineffective against inhaled poisons",
    ),
    (
        197,
        "and the expiry, which an implementation drops by building the exposure half and "
        "stopping: without it one smeared dagger poisons every creature it ever hits",
        r"The poison remains potent until delivered through a wound or washed off",
    ),
    (
        197,
        "and Contact and Ingested are the two that genuinely are narrative facts, which is "
        "what the exposure fact type is for",
        r"A creature that touches contact poison with exposed skin suffers its effects",
    ),
    # --- The three attitudes, and p. 184's Influence (#142) ----------------------------
    (
        182,
        "Friendly gives ADVANTAGE on the check, stated as a property of the check rather "
        "than a bonus somebody has to size",
        r"A Friendly creature views you favorably\.\s*You have Advantage on an ability check "
        r"to influence a Friendly creature",
    ),
    (
        183,
        "and Hostile gives Disadvantage, which is the same sentence reversed",
        r"A Hostile creature views you unfavorably\.\s*You have Disadvantage on an ability "
        r"check to influence a Hostile creature",
    ),
    (
        184,
        "Indifferent states NO effect on the check, which is what makes it the neutral case "
        "rather than a third modifier — and it states the DEFAULT, so R22's classification "
        "is srd-prescribed rather than engine-chosen",
        r"An Indifferent creature has no desire to help or hinder you\.\s*Indifferent is the "
        r"default attitude of a monster",
    ),
    (
        184,
        "the DC is the higher of 15 and the monster's Intelligence SCORE — not its modifier, "
        "which every other DC-adjacent number in this engine is",
        r"which has a default DC equal to 15 or the monster.s Intelligence score, whichever "
        r"is higher",
    ),
    (
        184,
        "two of the three determinations throw no die, so compliance and refusal are "
        "outcomes recorded rather than narrated into existence (0027 clause 6)",
        r"If your urging aligns with the monster.s desires, no ability check is necessary; "
        r"the monster fulfills your request in a way it prefers",
    ),
    (
        184,
        "and THE sentence that dissolved #142's fourth design question: the monster complies, "
        "and nothing about its attitude moves — so no EffectKind writes a fact",
        r"On a successful check, the monster does as urged\.\s*On a failed check, you must "
        r"wait 24 hours",
    ),
    # --- Cover: asserted although unbuilt, so #416 does not re-read it -----------------
    (
        179,
        "the three degrees and their benefits, and that only the MOST PROTECTIVE applies "
        "rather than the degrees adding — the clause an implementation most easily gets "
        "wrong by summing them (#416)",
        r"Half Cover \(\+2 bonus to AC and Dexterity saving throws\), Three-Quarters Cover "
        r"\(\+5 bonus to AC and Dexterity saving throws\), and Total Cover \(can.t be "
        r"targeted directly\)",
    ),
    (
        15,
        "and the sentence that makes cover DIRECTIONAL, which is the whole of why #416 is a "
        "gate: a bonus that is a property of the target alone grants it against every "
        "attacker",
        r"A target can benefit from cover only when an attack or other effect originates on "
        r"the opposite side of the cover",
    ),
    (
        15,
        "what earns each degree — a judgement about how much of the target is covered, which "
        "the document supplies no method for measuring, so the degree is STATED on the "
        "obstruction as 0051 has a Size stated (#416)",
        r"Another creature or an object that covers at least half of the target",
    ),
    (
        15,
        "and the degrees do not add, which is the clause an implementation gets wrong by "
        "summing bonuses: p. 15's own example would give +7, a number the rules never make",
        r"If a target is behind multiple sources of cover, only the most protective degree "
        r"of cover applies; the degrees aren.t added together",
    ),
    # --- p. 18's Temporary Hit Points, and p. 177's Bloodied (#412) --------------------
    (
        18,
        "the buffer is lost FIRST and the remainder carries over, with the document's own "
        "worked example — the one case an implementation cannot argue with",
        r"If you have Temporary Hit Points and take damage, those points are lost first, and "
        r"any leftover damage carries over to your Hit Points",
    ),
    (
        18,
        "and they are a buffer against LOSING Hit Points rather than against taking damage, "
        "which is the reading p. 179's Concentration save and p. 18's death-save failure "
        "both turn on (#413). p. 17's Resistance says 'halve the damage'; this says nothing "
        "of the kind",
        r"Temporary Hit Points, which are a buffer against losing actual Hit Points",
    ),
    (
        18,
        "they do not stack, and the CREATURE decides which set to keep — so a grant over an "
        "existing set refuses rather than taking the larger",
        r"If you have Temporary Hit Points and receive more of them, you decide whether to "
        r"keep the ones you have or to gain the new ones",
    ),
    (
        18,
        "they are not healing: a creature at full Hit Points may receive them, and death "
        "saves are not reset because p. 17 resets on regaining HIT POINTS",
        r"Temporary Hit Points can.t be added to your Hit Points, healing can.t restore "
        r"them, and receiving Temporary Hit Points doesn.t count as healing",
    ),
    (
        18,
        "and at 0 Hit Points they do not restore consciousness",
        r"If you have 0 Hit Points, receiving Temporary Hit Points doesn.t restore you to "
        r"consciousness\.\s*Only true healing can save you",
    ),
    (
        18,
        "their duration is stated here rather than on p. 185, which lists what a Long Rest "
        "restores and never mentions them",
        r"Temporary Hit Points last until they.re depleted or you finish a Long Rest",
    ),
    (
        177,
        "p. 177's Bloodied is a derived read on the current total — 'while', not a state "
        "something applies and something else removes",
        r"A creature is Bloodied while it has half its Hit Points or fewer remaining",
    ),
    # --- Search and Study: one mechanism, two entries, no DC (#411) --------------------
    (
        187,
        "p. 187's Search names the ability and states NO difficulty, which is why the DC is "
        "the caller's and carries its derivation (R5)",
        r"When you take the Search action, you make a Wisdom check to discern something that "
        r"isn.t obvious",
    ),
    (
        187,
        "and its table SUGGESTS rather than requires, which is why a check with no skill is "
        "legal and a skill absent from the table is not refused",
        r"The Search table suggests which skills are applicable when you take this action",
    ),
    (
        189,
        "p. 189's Study is the same sentence with a different ability, and likewise states "
        "no difficulty",
        r"When you take the Study action, you make an Intelligence check to study your "
        r"memory, a book, a clue, or another source of knowledge",
    ),
    (
        189,
        "and its table likewise suggests. The five areas are Arcana, History, Investigation, "
        "Nature and Religion — every one an Intelligence skill, which is the reading the "
        "wrong-ability refusal rests on",
        r"The Areas of Knowledge table suggests which skills are applicable to various areas "
        r"of knowledge",
    ),
    # --- p. 187's Short Rest, the sixth occasion (#406, 0082) --------------------------
    (
        187,
        "a creature at 0 hit points cannot START a Short Rest either — the same precondition "
        "p. 185 puts on a Long Rest, and the one an implementation drops",
        r"To start a Short Rest, you must have at least 1 Hit Point",
    ),
    (
        187,
        "the spend is a ROLL plus the Constitution modifier, so the engine rolls it (R4) and "
        "a resolver stating a total would be a caller supplying one",
        r"For each Hit Point Die you spend in this way, roll the die and add your "
        r"Constitution modifier to it",
    ),
    (
        187,
        "and the floor is the document's, not a guard: a negative Constitution modifier can "
        "total less than one on a small die",
        r"You regain Hit Points equal to the total \(minimum of 1 Hit Point\)",
    ),
    (
        187,
        "THE sentence that made #406 a gate: the decision comes after each roll, so a Short "
        "Rest is neither a drain nor a declaration slot but an offer repeated until the "
        "caller stops",
        r"You can decide to spend an additional Hit Point Die after each roll",
    ),
    (
        187,
        "an interrupted rest confers no benefits (#409) — built, and it needed no "
        "un-applying at all",
        r"An interrupted Short Rest confers no benefits",
    ),
    (
        187,
        "and THE sentence that made that true: benefits are conferred WHEN YOU FINISH. An "
        "interruption stops the rest before the finish, so nothing was ever applied and "
        "there is nothing to take back — which is what #409 assumed would be the hard part",
        r"Benefits of the Rest\.\s*When you finish the rest, you gain the following benefits",
    ),
    # --- The resource that sentence restores (#407) ------------------------------------
    (
        183,
        "p. 183 states the mechanic of Hit Point Dice as the SPEND, which is why holding the "
        "resource is not claiming the shape: the Short Rest that spends one is #406, and a "
        "shape claimed at half is the overstatement #371 and #264 each found",
        r"A creature can spend Hit Dice during a Short Rest to regain Hit Points",
    ),
    (
        183,
        "and the die SIZE is deferred to Character Creation and to stat blocks rather than "
        "stated here, which is why no table of sizes ships (R31)",
        r"Hit Point Dice, or Hit Dice for short, help determine a player character.s Hit "
        r"Point maximum, as explained in .Character Creation\.?.",
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
    # The second contradiction, and unlike #182's it fits in one paragraph (0031, #205).
    # Both halves are asserted so the pair goes red together if a revision reworded either —
    # which is the only way this project can learn the publisher resolved it rather than us.
    (
        188,
        "a change to Speed reaches a special speed by AN EQUAL AMOUNT — feet, subtracted",
        r"If an effect increases or decreases your Speed for a time, any special speed you "
        r"have increases or decreases by an equal amount for the same duration",
    ),
    (
        188,
        "and the same paragraph then works it PROPORTIONALLY, which is a different number "
        "the moment two speeds differ. The document states both and reconciles neither (#205)",
        r"if your Speed is halved and you have a Fly Speed, your Fly Speed is also halved",
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
    # --- What else depends on damage already dealt (0032, #173) ------------------------
    # Asserted ahead of any implementation, because the TAXONOMY is the design question and
    # it should be settled against the sentences rather than against a memory of them — the
    # same reason the five hazards above are asserted. Seven rules key off damage dealt and
    # they are three different shapes; sorting them wrongly would put a defence outside the
    # one place defences are applied.
    (
        18,
        "the third branch of p. 18, which the clause above stops short of: death is decided "
        "by the damage NUMBER against the hit point maximum, so this is a predicate over a "
        "settled amount and not merely over whether any landed (0032 clause 2)",
        r"If the damage equals or exceeds your Hit Point maximum, you die",
    ),
    (
        124,
        "Disintegrate keys on the STATE AFTER the damage rather than on the amount — "
        '"reduces it to 0 Hit Points" is answerable only once the blow has been applied',
        r"On a failed save, the target takes 10d6 \+ 40 Force damage\.\s*If this damage "
        r"reduces it to 0 Hit Points, it and everything nonmagical it is wearing and "
        r"carrying are disintegrated into gray dust",
    ),
    (
        314,
        "and a monster says the same thing in the same words, which is what makes it a "
        "shape rather than one spell's phrasing",
        r"If this damage reduces the target to 0 Hit Points, the target becomes Stable, and "
        r"it has the Poisoned condition for 1 hour",
    ),
    (
        311,
        "the one instance that is NOT a predicate: the second effect's magnitude is a "
        "function of the first's settled amount. 0032 clause 6 leaves it out of scope (#216)",
        r"If the target takes damage from the Dream spell, the target.s Hit Point maximum "
        r"decreases by an amount equal to that damage",
    ),
    (
        180,
        "and Damage Threshold is NOT this shape at all: the document says IMMUNITY, and what "
        "it modifies is the damage itself, which places it beside p. 17 rather than among "
        "conditional effects (#214)",
        r"has Immunity to all damage unless it takes an amount of damage from a single "
        r"attack or effect equal to or greater than its damage threshold, in which case it "
        r"takes that entire instance of damage",
    ),
    (
        180,
        "the same boundary from the other side — damage that fails to MEET OR EXCEED it is "
        "superficial, so both operative sentences say >= and the equal case gets through",
        r"Any damage that fails to meet or exceed the damage threshold is superficial and "
        r"doesn.t reduce Hit Points",
    ),
    (
        180,
        "and the worked example, which names the amount DEALT rather than any later figure "
        "— the evidence that the threshold gates the arriving instance (#214)",
        r"if an object has a damage threshold of 10, the object takes no damage if 9 damage "
        r"is dealt to it.{0,120}If the same object is dealt 11 damage, it takes all of that "
        r"damage",
    ),
    (
        17,
        "and the Order of Application names THREE steps, none of them the threshold — which "
        "is why its position is derived from p. 180 calling it Immunity rather than read off "
        "an ordering the document does not give (#214)",
        r"Modifiers to damage are applied in the following order: adjustments such as "
        r"bonuses, penalties, or multipliers are applied first; Resistance is applied "
        r"second; and Vulnerability is applied third",
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
        90,
        "Nick moves the Light property's extra attack into the Attack action, once a turn",
        r"When you make the extra attack of the Light property, you can make it as part of "
        r"the Attack action instead of as a Bonus Action\. You can make this extra attack "
        r"only once per turn",
    ),
    (
        90,
        "Slow needs damage and reduces the Speed by 10 feet to the START of your next turn",
        r"If you hit a creature with this weapon and deal damage to it, you can reduce its "
        r"Speed by 10 feet until the start of your next turn",
    ),
    (
        90,
        "and Slow's reduction is capped across sources rather than per hit",
        r"If the creature is hit more than once by weapons that have this property, the "
        r"Speed reduction doesn.t exceed 10 feet",
    ),
    (
        90,
        "Cleave opens a second melee swing beside the first, once a turn",
        r"you can make a melee attack roll with the weapon against a second creature within "
        r"5 feet of the first that is also within your reach",
    ),
    (
        90,
        "and Cleave's damage drops a positive ability modifier, once per turn",
        r"the second creature takes the weapon.s damage, but don.t add your ability modifier "
        r"to that damage unless that modifier is negative\. You can make this extra attack "
        r"only once per turn",
    ),
    (
        90,
        "Vex needs damage as well as a hit, and runs to the END of your next turn",
        r"If you hit a creature with this weapon and deal damage to the creature, you have "
        r"Advantage on your next attack roll against that creature before the end of your "
        r"next turn",
    ),
    (
        90,
        "Sap needs only a hit, and runs to the START of your next turn",
        r"If you hit a creature with this weapon, that creature has Disadvantage on its next "
        r"attack roll before the start of your next turn",
    ),
    (
        90,
        "Topple fires on a hit and compels a Constitution save",
        r"If you hit a creature with this weapon, you can force the creature to make a "
        r"Constitution saving throw",
    ),
    (
        90,
        "and the Topple DC is 8 plus the attack's ability modifier plus the Proficiency Bonus",
        r"DC 8 plus the ability modifier used to make the attack roll and your Proficiency "
        r"Bonus\)\. On a failed save, the creature has the Prone condition",
    ),
    (
        188,
        "Speed is the distance a creature covers when it moves ON ITS TURN",
        r"A creature has a Speed, which is the distance in feet the creature can cover "
        r"when it moves on its turn",
    ),
    (
        188,
        "the allowance is per mode against one shared spend, not one pool from Speed (#206)",
        r"If you have more than one speed, choose which one to use when you move; you can "
        r"switch between the speeds during your move\.\s*Whenever you switch, subtract the "
        r"distance already moved from the new speed",
    ),
    (
        188,
        "and a mode whose speed the spend has exhausted is refused, not merely reduced",
        r"If the result is 0 or less, you can.t use the new speed during the current move",
    ),
    (
        188,
        "the document's own worked example, which no single-pool reading reaches (#206)",
        r"if you have a Speed of 30 and a Fly Speed of 40, you could fly 10 feet, walk 10 "
        r"feet, and leap into the air to fly 20 feet more",
    ),
    (
        180,
        "Dash sizes its pool from a special speed if the creature chooses one",
        r"If you have a special speed, such as a Fly Speed or Swim Speed, you can use that "
        r"speed instead of your Speed when you take this action",
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
        "one action per turn — which nothing enforced until #252 gave it consumers",
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
        89,
        "Light buys ONE extra attack, as a Bonus Action, with a DIFFERENT Light weapon",
        r"you can make one extra attack as a Bonus Action later on the same turn\. That "
        r"extra attack must be made with a different Light weapon",
    ),
    (
        89,
        "and the damage exception is the whole of the damage rule: unless it is negative",
        r"you don.t add your ability modi-?\s*fier to the extra attack.s damage unless that "
        r"modi-?\s*fier is negative",
    ),
    (
        90,
        "Two-Handed requires two hands, which is a claim about the wielder's hands",
        r"A Two-Handed weapon requires two hands when you attack with it",
    ),
    (
        190,
        "the Unarmed Strike's bonus is Strength PLUS Proficiency, with no proficiency to have",
        r"Your bonus to the roll equals your Strength modifier plus your Proficiency Bonus",
    ),
    (
        190,
        "and its damage is flat rather than rolled — 1 plus the Strength modifier",
        r"the target takes Bludgeoning damage equal to 1 plus your Strength modifier",
    ),
    (
        190,
        "Grapple and Shove turn on a size comparison, which is why #259 blocks both",
        r"possible only if the target is no more than one size larger than you",
    ),
    (
        177,
        "the Attack action buys ONE attack roll, absent a feature that grants more",
        r"When you take the Attack action, you can make one attack roll with a weapon or an "
        r"Unarmed Strike",
    ),
    (
        180,
        "Dash grants the creature's speed after modifiers, and it chooses which speed",
        r"you can use that speed instead of your Speed when you take this action\. You "
        r"choose which speed to use each time you take it",
    ),
    (
        181,
        "Disengage suppresses Opportunity Attacks for the rest of the turn",
        r"your movement doesn.t provoke Opportunity Attacks for the rest of the current turn",
    ),
    (
        105,
        "ONE free hand serves Somatic and Material together — the clause a summary drops",
        r"must have a hand free to access them, but it can be the same hand used to perform "
        r"Somatic components",
    ),
    (
        178,
        "carrying capacity is keyed on Size as well as Strength, which is why #259 blocks it",
        r"Your size and Strength score determine the maximum weight in pounds that you can "
        r"carry",
    ),
    (
        188,
        "a Spellcasting Focus substitutes only for materials neither consumed nor priced",
        r"use in place of a spell.s Material components if those materials aren.t consumed by "
        r"the spell and don.t have a cost specified",
    ),
    (
        105,
        "only one spell slot may be expended on a turn, whichever actions are used",
        r"On a turn, you can expend only one spell slot to cast a spell",
    ),
    (
        104,
        "a cantrip is cast without a spell slot, which is why casting and spending differ",
        r"Cantrips\. A cantrip is cast without a spell slot",
    ),
    (
        185,
        "the Magic action is what an action-timed spell costs",
        r"When you take the Magic action, you cast a spell that has a casting time of an "
        r"action",
    ),
    (
        179,
        "damage is the occasion, and the save it compels is a Constitution save",
        r"If you take damage, you must succeed on a Constitution saving throw to maintain "
        r"Concentration",
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
        179,
        "the voluntary end is the creator's outright, and costs no action",
        r"The creator can end Concentration at any time \(no action required\)",
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
    # --- The three cases of an attack roll (#229, 0034) --------------------------------
    # 0034 files `weapon-attack` as vocabulary because the document defines the term and
    # never uses it. These three clauses pin the text that argument reads, and the count it
    # rests on is in DOCUMENT_CLAUSES below — presence alone cannot state an absence.
    (
        177,
        "an attack roll's own entry enumerates its three cases — weapon, Unarmed Strike, "
        "spell — so `weapon-attack` restates one of them rather than extending anything "
        "(0034 clause 1)",
        r"An attack roll is a D20 Test that represents making an attack with a weapon, an "
        r"Unarmed Strike, or a spell",
    ),
    (
        191,
        "and Weapon Attack's whole entry fixes a parameter of that roll and states nothing "
        "else — the sentence 0034 declines to count as a second shape",
        r"A weapon attack is an attack roll made with a weapon",
    ),
    (
        188,
        "Spell Attack reads the same way and is a shape anyway, which is why 0034 clause 2 "
        "turns on consumers rather than on how an entry is phrased",
        r"A spell attack is an attack roll made as part of a spell or another magical "
        r"effect",
    ),
    (
        106,
        "because a spell attack has a bonus formula of its own that an attack roll does not "
        "state — the mechanism `spell-attack` is claimed for",
        r"Spell attack modifier = your spellcasting ability modifier \+ your Proficiency "
        r"Bonus",
    ),
    (
        217,
        "the Dancing Sword's 'hovering weapon attacks' is a noun and a verb, not the "
        "defined term — the third raw hit the sweep discards, pinned so the count below "
        "reads as 3 rather than looking like an off-by-one (0034 Evidence)",
        r"After the hovering weapon attacks for the fourth time",
    ),
    # --- A target is a role, not a mechanic (#453, 0085) --------------------------------
    # 0085 files `target` as vocabulary because p. 190's entry defines the receiving end of
    # three mechanics and states no consequence of its own. The first clause pins the entry
    # ENTIRE — one sentence, followed by the next heading — so a revision that gave it a
    # second sentence goes red here rather than leaving the entry filed on a reading nobody
    # re-ran. The absence it also rests on is in DOCUMENT_CLAUSES below.
    (
        190,
        "Target's whole entry is one sentence naming what a target IS — the creature or "
        "object at the receiving end of an attack roll, a forced save or a spell's effect — "
        "and it is followed by the next heading, so there is no second sentence stating a "
        "consequence (0085 clause 1)",
        r"A target is the creature or object targeted by an attack roll, forced to make a "
        r"saving throw by an effect, or selected to receive the effects of a spell or "
        r"another phenomenon\. Telepathy",
    ),
    # p. 106's Targets section is the strongest reading against 0085, under 0033 clause 1:
    # a shape's content is what the document states about the term anywhere. These five
    # clauses pin what it states, so the record's reading — every rule here is the SPELL's,
    # and the two with consequences are claimed under `cover` and `area-of-effect` — is
    # checkable against the sentences rather than against a paraphrase. The first was
    # quoted in `spell_reaches`'s docstring and asserted nowhere, which is the #371 shape.
    (
        106,
        "a spell needs a clear path to its target, which is p. 179's Total Cover refusal "
        "from the spell's side — the sentence `spell_reaches` rests on, and the consequence "
        "`cover` is claimed for (0085 clause 5)",
        r"To target something with a spell, a caster must have a clear path to it, so it "
        r"can.t be behind Total Cover",
    ),
    (
        106,
        "a spell that targets a creature of your choice may target the caster — a rule "
        "about the spell's choice, which needs a spell with a target clause (#21)",
        r"If a spell targets a creature of your choice, you can choose yourself unless the "
        r"creature must be Hostile or specifically a creature other than you",
    ),
    (
        106,
        "an area of effect decides what a spell targets — the consequence `area-of-effect` "
        "is claimed for, stated from the spell's side",
        r"The area determines what the spell targets",
    ),
    (
        106,
        "the one sentence in the document about BEING targeted says the target does not "
        "know it happened — no state changes, which is why it is not a consequence 0085 "
        "could claim or hold",
        r"Unless a spell has a perceptible effect, a creature doesn.t know it was targeted "
        r"by the spell",
    ),
    (
        106,
        "an invalid target gets nothing and the slot is spent anyway — `core.casting` ties "
        "expenditure to the casting rather than to the outcome (p. 104), so the half that "
        "is a mechanic already holds; the half that needs a spell's own target clause is #21",
        r"If you cast a spell on someone or something that can.t be affected by it, nothing "
        r"happens to that target, but if you used a spell slot to cast the spell, the slot "
        r"is still expended",
    ),
    # --- p. 13's grid measure, which decides how a range meets a space (#456, 0086) -------
    (
        13,
        "a range between two things is counted from a square ADJACENT to one of them into "
        "the SPACE of the other — the document's one measuring rule, and it runs from edge "
        "to edge, which is why a creature that fills more than one square is nearer than its "
        "point (0086 clause 1)",
        r"To determine the range on a grid between two things.whether creatures or "
        r"objects.\s*count squares from a square adjacent to one of them and stop counting "
        r"in the space of the other one",
    ),
    (
        13,
        "by the shortest route, which on a grid is a diagonal counted as one square; the "
        "straight line 0014 chose already departs from that, and 0086 adds no second "
        "departure",
        r"Count by the shortest route",
    ),
    (
        13,
        "a square is five feet, so the one square a range stops in is the 5 that a Medium "
        "creature's point already carries — the excess 0086 takes off is what a space has "
        "beyond that square",
        r"Squares\. Each square represents 5 feet",
    ),
    (
        15,
        "a 5-foot reach attacks targets within 5 feet — 'targets', which p. 13 measures to "
        "the space of, so a Medium creature reaches a Huge one from ten feet away",
        r"A creature has a 5-foot reach and can thus attack targets within 5 feet when "
        r"making a melee attack",
    ),
    # --- p. 14's Moving around Other Creatures: asserted although unbuilt (#451, #456) --
    # Built on 0084's reads and set aside: reach is point-to-point, so every melee position
    # against a Huge creature is inside its space, and these four sentences read that as
    # forbidden, doubled and Prone. #456 holds the reach question; these hold the text.
    (
        14,
        "who may be passed through: an ally, an Incapacitated creature, a Tiny one, or one "
        "two sizes larger or smaller — four permissions, so a Large creature may not enter "
        "reach of a Huge one at all while reach is point-to-point (#456)",
        r"During your move, you can pass through the space of an ally, a creature that has "
        r"the Incapacitated condition .see .Rules Glossary.., a Tiny creature, or a creature "
        r"that is two sizes larger or smaller than you",
    ),
    (
        14,
        "whose space is Difficult Terrain: TWO exemptions here, not four — an Incapacitated "
        "enemy may be crossed and would cost double to cross",
        r"Another creature.s space is Difficult Terrain for you unless that creature is "
        r"Tiny or your ally",
    ),
    (
        14,
        "where a move may not end: no exception at all, so an ally's space may be crossed "
        "and may not be stopped in — and, read against point-to-point reach, nowhere in "
        "reach of a Huge creature may be stopped in either, which is the collision (#456)",
        r"You can.t willingly end a move in a space occupied by another creature",
    ),
    (
        14,
        "and the Prone for ending a turn in a space with someone — 'somehow', because the "
        "sentence before forbids doing it by moving, so it is a push, a teleport or a "
        "placement, and an end-of-turn obligation rather than a movement refusal",
        r"If you somehow end a turn in a space with another creature, you have the Prone "
        r"condition .see .Rules Glossary.. unless you are Tiny or are of a larger size than "
        r"the other creature",
    ),
    (
        176,
        "what an ally is: four disjuncts and every one a designation somebody states, which "
        "is why the design set aside on #456 holds a stated side and infers nothing (#434 "
        "needs the same fact)",
        r"A creature is your ally if it is a member of your adventuring party, your friend, "
        r"on your side in combat, or a creature that the rules or the GM designates as your "
        r"ally",
    ),
    # --- One thing under two names (#230, 0035) ----------------------------------------
    # 0035 files `save` as vocabulary because p. 187 states outright that it and `saving
    # throw` name one thing. Unlike 0034, the evidence here is a PRESENCE — two printed
    # sentences — so two ordinary clauses assert it and no document-wide count is added.
    # A count would assert something the argument does not rest on (0035 clause 6).
    (
        187,
        "Save's whole entry renames a saving throw and states no mechanic of its own — the "
        "sentence 0035 declines to count as a second shape",
        r"Save is another name for a saving throw",
    ),
    (
        187,
        "and the PARENT entry declares the alias itself, which is what makes the identity a "
        "statement of the document rather than a comparison of two entries (0035 clause 1)",
        r"A saving throw.also called a save.represents an attempt to avoid or resist a "
        r"threat",
    ),
    # --- 0041: an item that leaves a creature ------------------------------------------
    (
        191,
        "a weapon IS an object, so letting go of one is not a change of type (0041 clause 1)",
        r"A weapon is an object that is in the Simple or Martial weapon category",
    ),
    (
        177,
        "the Attack action's unequip clause, which is one of the five rules that detach an "
        "item and state no destination (0041 clause 4)",
        r"Unequipping a weapon includes sheathing, stowing, or dropping it",
    ),
    (
        191,
        "and Unconscious detaches without a destination too, which is why 0041 is a "
        "vocabulary decision rather than a weapon-property one",
        r"You have the Incapacitated and Prone conditions, and you drop whatever you.re "
        r"holding",
    ),
    (
        190,
        "teleportation moves what is worn and carried - the rule that makes a fourth "
        "`Carriage` member a dropped sword that teleports away with its dropper (0041 "
        "clause 2)",
        r"all the equipment you.re wearing and carrying teleports with you",
    ),
    (
        217,
        "the Dancing Sword states its own destination, in its own entry, as a magic item - "
        "the evidence that no general rule states one (0041 clause 4)",
        r"the weapon falls to the ground in your space",
    ),
    (
        12,
        "picking an object back up is one free interaction per turn, and the Utilize action "
        "beyond that - the half of 0041 that is fully printed (clause 6)",
        r"interactions with objects are limited: one free interaction per turn",
    ),
    # --- 0042: equipping rides on the attack that permits it ----------------------------
    (
        177,
        "the swap is licensed by making an attack, which is why it is not an action of its "
        "own (0042 clause 1)",
        r"You can either equip or unequip one weapon when you make an attack as part of this "
        r"action",
    ),
    (
        177,
        "and 'before or after' decides one thing only - whether the newly equipped weapon is "
        "available to THIS attack, which the next sentence then makes optional (0042 clause 2)",
        r"You do so either before or after the attack\. If you equip a weapon before an "
        r"attack, you don.t need to use it for that attack",
    ),
    (
        177,
        "and both directions name the ground, which is why 0041's detachment is what a "
        "drop and a pick-up route through (0042 clause 4)",
        r"Equipping a weapon includes drawing it from a sheath or picking it up\. Unequipping "
        r"a weapon includes sheathing, stowing, or dropping it",
    ),
    (
        13,
        "the OTHER budget, stated per turn rather than per attack - the second half of the "
        "pair 0042 clause 6 declines to compose",
        r"You can interact with one object or feature of the environment for free, during "
        r"either your move or action",
    ),
    (
        13,
        "and a second object needs the Utilize action, which is the sentence that makes the "
        "budget a budget rather than a suggestion",
        r"If you want to interact with a second object, you need to take the Utilize action",
    ),
    (
        191,
        "and p. 191 puts the two in one sentence WITHOUT composing them: drawing a sword in "
        "the Attack action is an example of interacting 'while doing something else', and "
        "the entry never says the free interaction is thereby spent (0042 clause 6)",
        r"You normally interact with an object while doing something else, such as when you "
        r"draw a sword as part of the Attack action",
    ),
    (
        177,
        "and the Attack action grants ONE attack roll, which is why the two readings cannot "
        "diverge yet - the reachability argument clause 6 rests on",
        r"When you take the Attack action, you can make one attack roll with a weapon or an "
        r"Unarmed Strike",
    ),
    # --- #284: Thrown ------------------------------------------------------------------
    (
        90,
        "a Thrown weapon is thrown to make a RANGED attack, and carries its own equip",
        r"you can throw the weapon to make a ranged attack, and you can draw that weapon as "
        r"part of the attack",
    ),
    (
        90,
        "and a thrown MELEE weapon keeps the modifier it uses in melee - the sentence that "
        "stops a ranged attack silently becoming a Dexterity one",
        r"If the weapon is a Melee weapon, use the same ability modifier for the attack and "
        r"damage rolls that you use for a melee attack with that weapon",
    ),
    (
        90,
        "and Range attaches to the Ammunition OR THROWN property - so a Melee weapon carries "
        "one exactly when it is Thrown, which the range invariant refused until #284",
        r"A Range weapon has a range in parentheses after the Ammunition or Thrown property",
    ),
    (
        183,
        "throwing a Melee weapon that lacks Thrown makes it improvised, whose damage type is "
        "a person's judgement - so the engine refuses the throw rather than resolving it",
        r"if you use a Ranged weapon to make a melee attack or throw a Melee weapon that "
        r"lacks the Thrown property, the weapon counts as an improvised weapon",
    ),
    (
        128,
        "and a thrown weapon is elsewhere whether it HITS OR MISSES, which is why the "
        "detachment rides in `always` rather than in a hit branch",
        r"A thrown weapon or piece of ammunition returns to normal size imme-?\s*diately "
        r"after it hits or misses a target",
    ),
    # --- 0045 / #288: Utilize ----------------------------------------------------------
    (
        13,
        "a second object needs the Utilize action, which is what the action DOES here - one "
        "more of the four moves the engine models (0045 clause 3)",
        r"If you want to interact with a second object, you need to take the Utilize action",
    ),
    (
        14,
        "and the GM may escalate an otherwise-free interaction to an action - a person's "
        "judgement the engine may not make, and may not conclude away from (0045 clause 5)",
        r"the GM might require you to take the Utilize action to open a stuck door or turn a "
        r"crank to lower a drawbridge",
    ),
    # --- #249: preparation ---------------------------------------------------------------
    (
        104,
        "preparation is a precondition of casting ANY spell, which ritual_cast has enforced "
        "since #19 and ordinary casting did not ask until #249",
        r"Before you can cast a spell, you must have the spell prepared in your mind or have "
        r"access to the spell from a magic item",
    ),
    (
        104,
        r"and the CHANGEABLE list is of level 1\+ spells - so a cantrip never counts against "
        "its size, while still needing to be prepared by the sentence above",
        r"If you have a list of level 1\+ spells you prepare, your spellcasting feature "
        r"specifies when you can change the list and the number of spells you can change",
    ),
    # --- #245: spell components --------------------------------------------------------
    (
        105,
        "Somatic asks for a hand and NOT a free one - the word 'free' appears for Material "
        "and not here, which is the whole of the distinction (#245)",
        r"A spellcaster must use at least one of their hands to perform these movements",
    ),
    (
        105,
        "and Material asks for a FREE hand, which the same hand may be - so an S,M spell "
        "needs one free hand rather than two (0039 clause 4)",
        r"The spellcaster must have a hand free to access them, but it can be the same hand "
        r"used to perform Somatic components, if any",
    ),
    (
        106,
        "a Pouch needs a free hand and a Focus is HELD - which is why a focus is the only "
        "route by which a full-handed caster provides Material components",
        r"To use a Component Pouch, you must have a hand free to reach into it, and to use a "
        r"Spellcasting Focus, you must hold it unless its description says otherwise",
    ),
    (
        188,
        "and a Focus substitutes only for materials neither consumed nor costed - properties "
        "of the SPELL's component, which is why 0039 clause 2 kept them off `Item`",
        r"in place of a spell.s Material compo-?\s*nents if those materials aren.t consumed by "
        r"the spell and don.t have a cost specified",
    ),
    # --- 0044 / #273: Ammunition -------------------------------------------------------
    (
        89,
        "ammunition is a condition of the attack and one piece goes per attack - so the shot "
        "is refused rather than resolved, and the count is spent (0044 clauses 2-3)",
        r"only if you have ammunition to fire from it\. The type of ammunition required is "
        r"specified with the weapon.s range\. Each attack expends one piece of ammunition",
    ),
    (
        89,
        "and recovery is a function of how much was USED, not of how much remains - which is "
        "why the tally is its own per-encounter structure (0044 clause 6)",
        r"After a fight, you can spend 1 minute to recover half the ammunition \(round down\) "
        r"you used in the fight; the rest is lost",
    ),
    (
        14,
        "the document DOES say when combat ends, and three of its five conditions are "
        "judgements about the fiction - so the engine may evaluate none of it (0044 clause 5)",
        r"Combat ends when one side or the other is defeated, which can mean the creatures "
        r"are killed or knocked out or have surrendered or fled\. Combat can also end when "
        r"both sides agree to end it",
    ),
    # --- #271: Loading -----------------------------------------------------------------
    (
        90,
        "Loading caps the shot per ACTION USED and not per turn, and the final clause is the "
        "whole property - unreachable until one action bought several rolls",
        r"You can fire only one piece of ammunition from a Loading weapon when you use an "
        r"action, a Bonus Action, or a Reaction to fire it, regardless of the number of "
        r"attacks you can normally make",
    ),
    # --- 0043: Multiattack -------------------------------------------------------------
    (
        257,
        "Multiattack is the ATTACK ACTION buying more than one roll, not a second action - "
        "which is what makes 0042 clause 6's silence reachable (0043 clause 1)",
        r"Some creatures can make more than one attack when they take the Attack action",
    ),
    (
        257,
        "and the entry's contents are the monster's, which is why the composition is ruleset "
        "data and not an engine grammar (0043 clause 2)",
        r"This entry details the attacks a creature can make, as well as any additional "
        r"abili-?\s*ties it can use, as part of the Attack action",
    ),
    # --- 0051: Size, and the one table keyed on it --------------------------------------
    (
        188,
        "the six categories, and that a creature BELONGS TO one - which is why `None` on a "
        "combatant means nobody stated it rather than that the creature has no size",
        r"A creature or an object belongs to a size category: Tiny, Small, Medium, Large, "
        r"Huge, or Gargantuan",
    ),
    (
        14,
        "where a size comes from, and both sources are content this repository does not ship "
        "- so Medium is a species' answer and never the engine's (R31)",
        r"A character.s size is determined by species, and a monster.s size is specified in "
        r"the monster.s stat block",
    ),
    (
        14,
        "the order the categories are in, which `Size.rank` rests on",
        r"lists the sizes from smallest \(Tiny\) to largest \(Gargantuan\)",
    ),
    (
        178,
        "the table is keyed on the Strength SCORE, not the modifier - a factor of seven, and "
        "both readings produce a believable load",
        r"Your size and Strength score determine the maximum weight in pounds that you can "
        r"carry",
    ),
    (
        178,
        "and the OTHER maximum in the same table, one line away - a haul above it is refused "
        "outright rather than merely slowed (0067 clause 4)",
        r"The table also shows the maximum weight you can drag, lift, or push",
    ),
    (
        178,
        "p. 178's table, both columns and all six rows - and Small/Medium printed as ONE row, "
        "which is what makes counting as one size larger worthless to a Small creature",
        r"Creature Size Carry Drag/Lift/Push Tiny Str\. . 7\.5 lb\. Str\. . 15 lb\. "
        r"Small/Medium Str\. . 15 lb\. Str\. . 30 lb\. Large Str\. . 30 lb\. Str\. . 60 lb\. "
        r"Huge Str\. . 60 lb\. Str\. . 120 lb\. Gargantuan Str\. . 120 lb\. Str\. . 240 lb\.",
    ),
    (
        178,
        "the consequence that is disclosed and NOT applied (#336) - note it fires on dragging, "
        "lifting or pushing rather than on carrying too much",
        r"While dragging, lifting, or pushing weight in excess of the maximum weight you can "
        r"carry, your Speed can be no more than 5 feet",
    ),
    (
        12,
        "and that the subsystem is a person's call at all, which is the second reason the cap "
        "is not applied",
        r"the GM might require you to abide by the rules for carrying capacity",
    ),
    (
        86,
        "Powerful Build, scoped to carrying capacity by its own sentence - which is why the "
        "flag is not a general 'counts as larger'",
        r"You also count as one size larger when determining your carrying capacity",
    ),
    (
        357,
        "and the mule says it again, which is why it is one flag and not two (0035)",
        r"The mule counts as one size larger for the purpose of determining its carrying "
        r"capacity",
    ),
    # --- 0052: Grappling, and the endings that come with it ------------------------------
    (
        182,
        "the sentence that makes these rules independent of whatever imposed the grapple - "
        "which is why they are built before any initiator",
        r"However a grapple is initiated, it follows these rules",
    ),
    (
        182,
        "the escape check: an ACTION, either of two skills, against the grapple's own DC, "
        "ending the condition only on a success",
        r"A Grappled creature can use its action to make a Strength \(Athletics\) or "
        r"Dexterity \(Acrobatics\) check against the grapple.s escape DC, ending the "
        r"condition on itself on a success",
    ),
    (
        182,
        "the two endings nobody decides, and note the second is EXCEEDS rather than reaches",
        r"The condition also ends if the grappler has the Incapacitated condition or if the "
        r"distance between the Grappled target and the grappler exceeds the grapple.s range",
    ),
    (
        182,
        "the release, and that it costs nothing - which is why the offer is not gated on a "
        "spare Action (#341 holds the timing this engine cannot yet reach)",
        r"the grappler can release the target at any time \(no action required\)",
    ),
    (
        182,
        "Grappled's first clause, which is built",
        r"Speed 0\. Your Speed is 0 and can.t increase",
    ),
    (
        182,
        "its second, which is built and is RELATIONAL - answered with a target rather than by "
        "a flat field",
        r"You have Disadvantage on attack rolls against any target other than the grappler",
    ),
    (
        182,
        "and its third, now built (#340, 0066) - two exemptions, and the cost is the "
        'GRAPPLER\'s: "costs IT 1 extra foot"',
        r"The grappler can drag or carry you when it moves, but every foot of movement costs "
        r"it 1 extra foot unless you are Tiny or two or more sizes smaller than it",
    ),
    (
        259,
        "a stat block states an escape DC outright, which is why the DC is stored with the "
        "grapple rather than recomputed from the grappler",
        r"the rug can give it the Grappled condition \(escape DC 13\)",
    ),
    # --- 0053: the target chooses, and the engine rolls ----------------------------------
    (
        190,
        "the Unarmed Strike offers THREE options and the attacker picks one - which is why "
        "each is its own action key rather than a parameter",
        r"Whenever you use your Unarmed Strike, choose one of the following options for its "
        r"effect",
    ),
    (
        190,
        "Grapple: the TARGET chooses which of two abilities it saves with, and the failure "
        "applies the condition",
        r"Grapple\. The target must succeed on a Strength or Dexterity saving throw \(it "
        r"chooses which\), or it has the Grappled condition",
    ),
    (
        190,
        "and one DC serves the save AND every later escape attempt, which is why it is stored "
        "on the grapple rather than recomputed (0052 clause 4)",
        r"The DC for the saving throw and any escape attempts equals 8 plus your Strength "
        r"modifier and Proficiency Bonus",
    ),
    (
        190,
        "Grapple's two qualifiers, and the free hand is asked for HERE and not in Shove",
        r"This grapple is possible only if the target is no more than one size larger than you "
        r"and if you have a hand free to grab it",
    ),
    (
        190,
        "Shove: the same choice of save, and TWO effects the attacker picks between - only the "
        "Prone one is built (#345)",
        r"Shove\. The target must succeed on a Strength or Dexterity saving throw \(it chooses "
        r"which\), or you either push it 5 feet away or cause it to have the Prone condition",
    ),
    (
        190,
        "and Shove's qualifier is the size test ALONE - no free hand, which is the document's "
        "own distinction rather than an omission",
        r"This shove is possible only if the target is no more than one size larger than you",
    ),
    (
        190,
        "the distance p. 190 states is the STRIKE's, not the grapple's - which is why a "
        "grapple made here carries no range (#346)",
        r"a melee attack that involves you using your body to damage, grapple, or shove a "
        r"target within 5 feet of you",
    ),
    (
        187,
        "Restrained gives Disadvantage on DEXTERITY saves only, which is why the better "
        "modifier is not the better save and the engine may not choose (#344)",
        r"Saving Throws Affected\. You have Disadvantage on Dexterity saving throws",
    ),
    # --- 0054: what the roller's own state does to a saving throw -------------------------
    (
        186,
        "Paralyzed fails Strength and Dexterity saves outright - and names those two only, "
        "which is why a Paralyzed creature still rolls Constitution",
        r"Paralyzed \[Condition\].{0,400}?Saving Throws Affected\. You automatically fail "
        r"Strength and Dexterity saving throws",
    ),
    (
        189,
        "Stunned says it in the same words",
        r"Stunned \[Condition\].{0,400}?Saving Throws Affected\. You automatically fail "
        r"Strength and Dexterity saving throws",
    ),
    (
        191,
        "and so does Unconscious",
        r"Unconscious \[Condition\].{0,400}?Saving Throws Affected\. You automatically fail "
        r"Strength and Dexterity saving throws",
    ),
    (
        181,
        "the Dodge action's Advantage on DEXTERITY saves, and the two things that take it "
        "back - which is why `is_dodging` re-asks rather than trusting a flag",
        r"you make Dexterity saving throws with Advantage\. You lose these benefits if you "
        r"have the Incapacitated condition or if your Speed is 0",
    ),
    (
        17,
        "a Death Saving Throw is tied to NO ability score, which is why none of the rules "
        "above reaches it - and why an Unconscious creature still rolls one",
        r"Unlike other saving throws, this one isn.t tied to an ability score",
    ),
    # --- 0055: a creature moved by something other than itself -----------------------------
    (
        90,
        "Push: UP TO ten feet, so the wielder chooses the distance, and only if the target is "
        "Large or smaller",
        r"Push If you hit a creature with this weapon, you can push the creature up to 10 feet "
        r"straight away from yourself if it is Large or smaller",
    ),
    (
        190,
        "Shove's push is EXACTLY five feet, not a maximum - so there is no distance to choose "
        "and none in the key",
        r"or you either push it 5 feet away or cause it to have the Prone condition",
    ),
    (
        185,
        "forced movement provokes NO Opportunity Attack: the trigger names the three actions "
        "and the speeds, and a shove uses none of them",
        r"You can make an Opportunity Attack when a creature that you can see leaves your "
        r"reach using its action, its Bonus Action, its Reaction, or one of its speeds",
    ),
    (
        169,
        "Thunderwave states its distance rather than a maximum, which is the other half of "
        "the up-to distinction",
        r"a creature takes 2d8 Thunder damage and is pushed 10 feet away from you",
    ),
    (
        320,
        "a pull is the same line read the other way - and it stops AT the puller, since a "
        "creature reeled past it would be somewhere no rule put it",
        r"The roper pulls each creature Grappled by it up to 30 feet straight toward it",
    ),
    # --- 0056: a move is refused where it is made ------------------------------------------
    (
        182,
        "Frightened forbids moving CLOSER and forbids it WILLINGLY - one word decides that a "
        "push is exempt, and the other that circling at a constant distance is permitted",
        r"Can.t Approach\. You can.t willingly move closer to the source of fear",
    ),
    (
        186,
        "Prone's two movement options are one rule, which is why the restriction waits for "
        "the way out of it (#353)",
        r"Restricted Movement\. Your only movement options are to crawl or to spend an amount "
        r"of movement equal to half your Speed \(round down\) to right yourself and thereby end "
        r"the condition",
    ),
    # --- 0057: Prone's two options, built together -----------------------------------------
    (
        186,
        "and the Speed-0 exception is p. 186's OWN sentence, not a consequence of the cost "
        "being zero - half of nothing is nothing, and a free stand is what a naive reading "
        "would grant",
        r"If your Speed is 0, you can.t right yourself",
    ),
    (
        179,
        "crawling is priced, so the option p. 186 leaves a Prone creature costs something",
        r"Crawling While you.re crawling, each foot of movement costs 1 extra foot",
    ),
    # --- 0058: condition effects that reached no roll --------------------------------------
    (
        186,
        "Paralyzed: any HIT within 5 feet is a Critical Hit - a hit, so a natural 1 is "
        "untouched, and 5 feet is the condition's number rather than the attacker's reach",
        r"Automatic Critical Hits\. Any attack roll that hits you is a Critical Hit if the "
        r"attacker is within 5 feet of you",
    ),
    (
        186,
        "Petrified resists ALL damage, which `Defences.resists_all` already expressed and no "
        "condition had ever set",
        r"Resist Damage\. You have Resistance to all damage",
    ),
    (
        186,
        "and is Immune to the Poisoned CONDITION, which p. 183 makes a no-op rather than an error",
        r"Poison Immunity\. You have Immunity to the Poisoned condition",
    ),
    (
        183,
        "p. 183's Immunity: it does not affect you IN ANY WAY, which is why applying Poisoned "
        "to a statue returns the state unchanged rather than raising",
        r"Immunity If you have Immunity to a damage type or a condition, it doesn.t affect "
        r"you in any way",
    ),
)

#: Clauses about the document as a whole rather than about one page, as
#: (what it settles, pattern, comparison, count). Checked case-insensitively across every
#: page's normalised text.
#:
#: **These make the opposite kind of claim to `CLAUSES`, which is why they are a separate
#: table rather than a flag on the tuple above.** A `CLAUSES` row says a sentence is *there*;
#: a row here says a term is used a given number of times, which is the only way to assert
#: that something is *absent*. 0034 clause 3 requires it: a claim resting on text outside an
#: entry cites the page and asserts the sentence (0033 clause 3), so a declassification
#: resting on the **absence** of such text has to assert the absence, or it decays silently —
#: nothing goes red when a term the document did not use starts being used.
DOCUMENT_CLAUSES: tuple[tuple[str, str, str, int], ...] = (
    # --- The absence 0034 rests on, and the control that proves the sweep ran ------------
    (
        "the defined term 'weapon attack' is used nowhere in the document but its own p. 191 "
        "entry (heading plus one sentence) and p. 217's Dancing Sword verb phrase — so it "
        "gates no mechanic, and `weapon-attack` is vocabulary rather than a second shape",
        r"weapon attack",
        "exactly",
        3,
    ),
    (
        "'spell attack', by contrast, is used throughout. This is a CONTROL, not a rule the "
        "engine depends on. It does not guard against a text layer that extracted NOTHING — "
        "`exactly 3` already goes red at 0, which was proved rather than assumed. It guards "
        "the narrower and likelier case: an extraction that degrades PARTIALLY, losing "
        "column-split or hyphenated occurrences. 3 is a small number a damaged parse can "
        "reach by accident; 62 is not, so this row certifies the sweep read a substantially "
        "intact document rather than merely a non-empty one",
        r"spell attack",
        "at least",
        20,
    ),
    # --- The absence 0041 rests on ------------------------------------------------------
    (
        "no general rule says where a released object lands. 'falls to the ground' occurs "
        "five times and every one is an effect stating its own outcome - pp. 133, 171, 209 "
        "and 217 twice - so a sixth occurrence means the document grew a sentence 0041 "
        "clause 4 assumed was absent, and the `Position | None` refusal would become an "
        "invention of the opposite kind: refusing a value the document now supplies",
        r"falls to the ground",
        "exactly",
        5,
    ),
    (
        "and the return trip is named exactly once, on p. 177, which is why 0041 clause 6 "
        "cites the Attack action rather than a general pick-up rule",
        r"picking it up",
        "exactly",
        1,
    ),
    # --- The absence 0085 rests on, and the two controls that prove the instrument ------
    # `target` is used 1,214 times, so no count of the term can state an absence the way
    # `weapon attack` at 3 did. What CAN be counted is the form the document uses to state a
    # held state — "has the X condition" (313 times), "is Bloodied" (10) — and whether the
    # term ever takes it. It never does. That is the narrow claim: target-ness is never
    # stated as a state something is in or becomes, which is the form 0013's criterion asks
    # for. It is NOT a claim that no effect branches on the role — Levitate's "If you are
    # the target" (p. 144) and the Rod of Absorption's "If you are targeted by a spell"
    # (p. 241) do, and 0085 clause 3 reads them as the effect's own branch, exactly as
    # `creature` is branched on twenty times ("is a creature") and is vocabulary.
    (
        "the document never states target-ness as a state: 'is a target', 'becomes a "
        "target' and 'counts as a target' occur nowhere — so nothing gates on it the way a "
        "held state is gated on, and `target` is vocabulary (0085 clause 4)",
        r"\b(?:is|becomes|counts as) a target\b",
        "exactly",
        0,
    ),
    (
        "'target' itself is used throughout. This is a CONTROL, not a rule the engine "
        "depends on: an `exactly 0` row is the one shape of assertion a sweep that read "
        "NOTHING passes, so this row proves the sweep reads the noun at all — 1,214 "
        "occurrences in this edition, and a partial extraction would still clear the floor",
        r"\btarget\b",
        "at least",
        1000,
    ),
    (
        "and the phrasing family is one the document uses for a state it does hold. This "
        "is the second CONTROL: 'is Bloodied' is p. 177's held state in exactly the form the "
        "row above says 'target' never takes, so the instrument finds the form where it "
        "exists and its zero above is an absence rather than a pattern that matches nothing",
        r"\bis Bloodied\b",
        "at least",
        5,
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

    for settles, pattern, comparison, expected in DOCUMENT_CLAUSES:
        found = sum(len(re.findall(pattern, text, re.I)) for text in pages.values())
        held = found == expected if comparison == "exactly" else found >= expected
        if not held:
            failures.append(
                f"document: {pattern!r} occurs {found} times, expected {comparison} "
                f"{expected}\n    settles: {settles}"
            )
        else:
            print(f"  ok  doc     {pattern!r} x{found} ({comparison} {expected})")

    if failures:
        raise SystemExit(
            "\nthe cited text no longer matches the document:\n\n"
            + "\n".join(failures)
            + "\n\ncore.d20 and core.death rest on these sentences. Re-read the "
            "document before touching the implementation to make this pass."
        )

    print(
        f"\nall {len(CLAUSES)} clauses and {len(DOCUMENT_CLAUSES)} document-wide "
        f"clauses verified against {pdf.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
