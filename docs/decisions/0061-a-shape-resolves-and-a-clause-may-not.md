# 0061 — A shape resolves, and a clause may not

- **Status:** Accepted, 2026-08-30
- **Settles:** [#356](https://github.com/eddiefiggie/srd-rules-engine/issues/356)
- **Requirements:** R17, R32
- **Related:** [0058 — a field nothing reads is a rule modelled and not applied](0058-a-field-nothing-reads-is-a-rule-not-applied.md),
  which built this issue's other half;
  [0060 — a disclosure can be wrong about why](0060-a-disclosure-can-be-wrong-about-why.md)

## Context

R17 makes "full SRD 5.2 coverage is the definition of done" falsifiable by counting effect
shapes. The instrument works for what it measures and **cannot see a shape that resolves while
a sentence of it reaches no roll.**

Five consecutive builds fixed exactly that and published no change:

| record | what was built | figure |
|---|---|---|
| [0054](0054-a-save-is-rolled-by-a-creature.md) | conditions reaching saving throws | 114 → 114 |
| [0056](0056-a-move-is-refused-where-it-is-made.md) | Frightened's Can't Approach | 116 → 116 |
| [0057](0057-prone-crawls-or-stands.md) | Prone's crawl restriction and its exit | 116 → 116 |
| [0059](0059-initiative-draws-a-pair-for-everyone.md) | Initiative's two clauses | 116 → 116 |
| [0060](0060-a-disclosure-can-be-wrong-about-why.md) | the sight failure's single source of truth | 116 → 116 |

Each was correct by R17's own terms: the shape resolved, was applied, was held and was
reported. Each record said so, and by the fifth it had stopped being a note.

## Decision

1. **The instrument gains a second published figure: the number of disclosed clauses.** It sits
   beside the coverage sentence in `README.md` and is derived from both halves —
   condition clauses from `EFFECTS`, and the rest from the AST walk that pins them. A published
   number nobody derives is the hand-maintained pin [#334](https://github.com/eddiefiggie/srd-rules-engine/issues/334) was.

2. **It is the one figure that improves by going down.** Coverage rises as shapes are built;
   this falls as *sentences* are. The five builds above reduced it and would now be visible.

3. **The guard fails when a clause is built and the figure stands still**, which is the
   direction that made the last five builds look like they changed nothing.

4. **A second guard asserts the two figures measure different things** — that at least one
   claimed shape carries an unenforced clause. If none ever did, the second figure would be
   redundant and this record wrong.

5. **The other half of #356 shipped in 0058** and is not restated here: a field on a rule-data
   structure that nothing reads is a rule modelled and not applied, guarded by an AST walk.

## Why

### Two instruments, because there are two ways to be incomplete

A shape can be absent — the engine cannot resolve it at all, which coverage counts. Or a shape
can be present and a sentence of it unenforced, which `unenforced_clauses` names and nothing
counted. `frightened` was `implemented: true` for forty builds while "you can't willingly move
closer to the source of fear" was enforced by nothing, and both statements were true at once.

### The figure is not a quality score and should not be read as one

A disclosure being *added* is usually good news: it means a gap that existed silently is now
named. 0058 raised this number from ten to seventeen without the engine losing anything, and
0060 corrected three of those seventeen without changing the count at all. What the number
measures is **how much of the document the engine holds and does not apply** — falling is
progress, and rising is either a regression or an honesty improvement, which is why the diff is
still where the judgement happens.

## Consequences

- **17 clauses are published today.** Ten on conditions, seven at the read surface.
- **Three corruptions hold the figure**, including one that builds a rule and leaves the number
  alone.
- **No coverage figure moves.** For the sixth time — and now the second figure says why.

## Status of implementation

**Every clause is built** by [#356](https://github.com/eddiefiggie/srd-rules-engine/issues/356).

| Clause | State |
|---|---|
| 1 — a second published figure, derived | **Built.** `test_the_disclosed_clause_count_is_the_one_the_engine_holds` |
| 2 — it improves by going down | **Built as prose**, in the README sentence itself |
| 3 — the guard catches a still figure | **Built.** Proven red by building a clause |
| 4 — the two figures differ | **Built.** `test_the_two_figures_measure_different_things` |
| 5 — the field guard | **Built by 0058**, not restated |
