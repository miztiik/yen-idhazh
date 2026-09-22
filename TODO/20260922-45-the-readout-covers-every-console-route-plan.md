# Plan 45 - Every drawing on the console declares

**Last Updated**: 2026-09-22
**Correction level**: 3 - it changes published pages and the test that judges every published page of its kind.

## 0. Operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The console holds one rule: a drawing either prints a hover strip naming the column under the pointer, or it says in words why it has no column to name. Five drawings across two routes obey neither. The note that records the exclusion is false about both routes. And two drawings that already obey it print a broken heading on the live site - `21 Septhe newest day` - because their call sites pass the resting note with no separator. |
| A2 | Hard scope - in | The three undeclared drawings on `/console/judgement/`; the two undeclared day matrices on `/console/voices/`; the run-together resting heading on the two judgement charts that do declare; the two chart specs' route lists; the stale clause on the page that owns the rule. |
| A3 | Hard scope - out | Table B. |
| A4 | ESCALATE triggers | Table C. |
| A5 | Chosen strategy | Four surface rows land the drawings and their own assertions, each in its panel's own dedicated spec. A fifth row then widens the two console-wide specs so the rule judges the new surfaces. The rule row lands separately from the surfaces it judges, so a red oracle names which of the two broke. |
| A6 | Execution | Workpool, parallel N = 2. Three pull requests in two waves (Table E). |

### 0a. Hard scope - out

| # | Out of scope | What it costs to leave alone | What would bring it in |
| --- | --- | --- | --- |
| B1 | Widening the chart census in `console-readout.spec.ts` from `svg` to any `role="img"` drawing | Drawings that are not `<svg>` stay outside the declare-or-say-why oracle. Today that is the KPI card fill tracks, the prompt-reuse bars and the voices standing-weight tracks. The voices day matrices are still reached by this plan, through the second census that seeds on the declaration itself (Contract 6). | A console-wide pass that declares every non-`<svg>` drawing first. Widening the seed before those surfaces declare turns three console routes red on merge. That is a Level 3 plan of its own, not a row here. |
| B2 | A hover strip over either voices day matrix | Nothing. Each square already names its own day and what that day did, in its own `<title>`. A strip would reprint the list the reader is already pointing at. | A reading in which a square's own title is unreachable - it is reachable today by pointer and by keyboard. |
| B3 | Tinting the `eligible-disagreed` cell on `VerdictSplit` when it is above zero | An operator scanning the panel reads a number that means "the two judges split" in the same weight as the numbers that mean nothing is wrong. | A decision that the cell is a warning surface, which is a colour-system question for the design system page, not a readout question. |
| B4 | Deriving the console route lists from one exported constant | Each spec keeps its own hand-written route list, so adding a route means editing every list that should cover it. | Nothing. The owner ruled on this at `frontend/src/lib/console/band.ts:131-133`: the lists stay hand-written per spec file, because a shared constant makes a spec cover a route nobody chose for it. Row 5 edits two lists by hand for that reason. |
| B5 | Per-chart `hint` text on the new strips | The new strips carry the shared default hint. | A reading that the default hint is wrong for a specific chart. |

### 0b. ESCALATE triggers

| # | Trigger | Why it stops the row |
| --- | --- | --- |
| C1 | A row needs a change under `frontend/src/lib/charts/` or in `frontend/src/lib/components/ChartReadout.svelte` | Both are shared by every console route. In particular: the missing separator in the resting heading is fixed at the two call sites, never at `ChartReadout.svelte:51`. A separator added there prints `21 Sept, , the newest day` on the twenty-one call sites that already pass their own. |
| C2 | `MergedStoriesPanel` cannot resolve two distinct columns under the pointer on a real build | The panel draws a bar and a dot at the same `columnsX[index]`. If they do not resolve to one column, the strip design in Contract 2 is wrong and the row needs a new one. |
| C3 | A reason string in Table F is refused on reading grounds | The string is the whole of what the reader gets in place of a strip. A worker does not reword it alone. |
| C4 | Row 5's widened declaration loop turns red on a route this plan does not declare on | That is a console-wide declaration gap, which is B1's plan and not this one. |
| C5 | Any row would add a second `[data-readout]` strip inside an element that already carries one | The declaration pair permits exactly one (Contract 1). Two strips under one `data-readout-columns` is a design error, not a test to relax. |

### 0c. What the rows cost to run

Measured 2026-09-22 from GitHub job step timestamps on `main`, n = 30 for the browser suite step and n = 15 for the job, SD 28 s.

| # | Reading | What it means |
| --- | --- | --- |
| D1 | The console group costs 211 s of the browser suite step's 320 s mean | Two thirds of the step is the console. The job is 432 s with the group and 216 s with `SKIP_CONSOLE_SUITE` set. |
| D2 | The console group is 443 of the browser suite's 630 browser-driving test blocks | 70 percent of the blocks and 66 percent of the wall clock. A further 441 console blocks never open a browser and cost nothing measurable. |
| D3 | A browser-driving console test is about 1.9 s of serial work | 4 workers x 211 s / 443 blocks. This is the unit to price a new test in. |
| D4 | These five rows add about 24 browser-driving blocks: 19 to 45 s of serial work, 0 to 28 s of wall clock | The step's own spread is 236 to 350 s, SD 28 s. CI cannot see this change. It ships on cost and revert, not on a measurement (CLAUDE.md Guardrail #10). |
| D5 | The 6 h job kill line sits at 2.2 percent of use at the worst observed run of 481 s | It does not bind. Our own 25-minute browser cap sits at 32 percent, sized at 3.1x the worst observed run. The 1 GB site cap is not in play - this plan ships no new asset. |

Playwright runs `fullyParallel: false` with 4 workers, so it parallelises by file. Adding blocks to an existing spec extends one worker's bin; only a new spec file opens a new bin. Every row here adds to an existing spec, which is why D4's wall-clock floor is zero.

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The merged-stories chart prints its column | - | J | Landed | p45j | #1045 | - |
| 2 | The two single-population figures say why they have none | - | J | Landed | p45j | #1045 | - |
| 3 | The judgement strips stop running a date into a note | - | J | Landed | p45j | #1045 | - |
| 4 | The two day matrices on voices declare | - | V | Not started | - | - | - |
| 5 | The rule reaches the judgement route and the voices reasons | 1, 2, 4 | R | Not started | - | - | - |

### 1a. Pull requests and file ownership

| # | PR | Wave | Rows | Files it owns, and nobody else touches |
| --- | --- | --- | --- | --- |
| E1 | PR-J - the judgement route declares | 1 | 1, 2, 3 | `frontend/src/routes/console/judgement/MergedStoriesPanel.svelte`, `HoldoutMargin.svelte`, `VerdictSplit.svelte`, `JudgeAgreement.svelte`, `MergeLinePlot.svelte`, `+page.svelte`; `frontend/tests/console-judgement-merges.spec.ts`, `console-judgement-holdout.spec.ts`, `console-judgement-verdict.spec.ts`, `console-judgement-agreement.spec.ts`, `console-judgement-line.spec.ts` |
| E2 | PR-V - the voices matrices declare | 1 | 4 | `frontend/src/routes/console/voices/+page.svelte`; `frontend/tests/console-voices-feeds.spec.ts`, `console-voices-retiring.spec.ts` |
| E3 | PR-R - the rule covers them | 2 | 5 | `frontend/tests/console-readout.spec.ts`, `console-chrome.spec.ts`; `docs/architecture/publishing/console-charts.md` |

E1 and E2 share not one file. E3 waits for both to merge.

### 1b. Why the split falls here

Rows 1, 2 and 3 are one idea - the judgement route obeys the rule - reviewed once, on one route, in one browser run. Splitting them into three pull requests buys a reviewer nothing and costs two extra browser jobs.

Row 4 is a different route, a different reviewer question, and provably disjoint files. It runs beside PR-J rather than behind it.

Row 5 is alone because it changes the rule that judges the page. Landed with the surfaces, a red oracle cannot say whether the surface is wrong or the rule is. Landed after them, it can only be the rule.

Every row ships its own assertions in its own surface's dedicated spec. That is what makes the file sets disjoint and what makes CLAUDE.md Guardrail #9 hold inside each pull request rather than across the pair.

### 1c. Workpool

Parallel N = 2. Wave 1 runs PR-J and PR-V at the same time in two worktrees. Wave 2 runs PR-R alone.

N is 2 and not 4 because rows 1 to 3 are one branch, and it is not 1 because row 4 shares no file with them and no reviewer question either. A slot refills the moment its worker returns; a worker never waits on a merge that is not in its Depends-on column.

`backend/utilities/gate_lock.py` serialises `pytest`, `npm run build` and `npm run test:browser` across worktrees. It bounds how fast two workers can gate, not how many may author. Two workers will queue behind each other at the browser gate for about 430 s. That is the whole of the contention cost.

## 2. Contracts

Everything in this section is settled before any code is written (CLAUDE.md Guardrail #3). A worker does not re-derive these from a live file. They are numbered Contract 1 to Contract 8; the lettered ids elsewhere belong to tables.

### 2a. Where the machinery is

Copy the strip wiring from `frontend/src/routes/console/judgement/MergeLinePlot.svelte` lines 164-178 (building the columns), 201-221 (the declaration pair, the `<svg>` wiring, the focus-visible class, `tabindex="0"`, `use:pointerReadout`, and the `<!-- svelte-ignore a11y_no_noninteractive_tabindex -->` that must precede it) and 391 (the `<ChartReadout>` call).

`DayReadout`, `ReadoutRow`, `ReadoutMark`, `readoutMarks`, `dayColumns` and `pointerReadout` all live in `frontend/src/lib/charts/frame.ts`. `columnStrip` is for engine-drawn charts and writes `x: 0`; do not use it - build the column array inline from `columnsX`.

### 2b. Contract 1 - the declaration pair

Every `<svg>` chart inside `[data-surface="operator"]` resolves through `closest()` to exactly one ancestor carrying either:

- `data-readout-columns` - an integer of 1 or more. That element holds exactly one `[data-readout]` strip and no competing swatch; or
- `data-readout-none` - free text, at least five whitespace-separated words, saying why the drawing has no column to name.

Never both on one element, and never a second strip under one `data-readout-columns`. `console-readout.spec.ts` asserts each half in a different block, so breaking the pair turns three tests red, not one.

### 2c. Contract 2 - what the merged-stories strip emits

| # | Field | Value |
| --- | --- | --- |
| G1 | strip name | `merged-stories` |
| G2 | row 1 label | `Merged` |
| G3 | row 1 colour | `var(--chart-1)` |
| G4 | row 1 value | `3 of 412 published`; at a zero column `0 of 412 published`; on a day that published nothing `no story published` |
| G5 | row 2 label | `Biggest group` |
| G6 | row 2 colour | `var(--chart-2)` |
| G7 | row 2 value | `2 stories`; when no group formed `none formed` |
| G8 | rows printed | Both, at every column, including columns where the count is zero. A row that disappears at zero makes the reader compare a two-row strip with a one-row strip. |
| G9 | resting note | `, the newest published day` - the leading comma and space are part of the string (Contract 5) |
| G10 | `readoutMaxShare` | passed as a prop from `judgement/+page.svelte`, reading `data.chart.readout_max_share`, exactly as lines 103 and 120 of that file already do |
| G11 | strip position | between the `observeWidth` div and `.merge-note`, below the plot. Never over it. |
| G12 | the per-column `<title>` | stays. It is what a screen reader and a slow pointer get, and the strip does not replace it. |

The denominator rides inside G4's value. There is no third `Published` row: a strip row whose value is not a mark on the axis is a key describing something the picture does not contain.

When the window holds no column at all, the strip slot holds one `<p>` with a `min-height` equal to the loaded strip - a day heading, two rows and the hint line - carrying exactly `No column in this window, so there is nothing to point at.` The panel height must not move (Contract 7).

### 2d. Contract 3 - the exact strings

Paste these. Do not reword them. If one is refused on reading grounds, that is Table C row C3.

| # | File and line on `main` | String |
| --- | --- | --- |
| F1 | `HoldoutMargin.svelte:175`, added to the `<div data-holdout ...>` | `data-readout-none="one score axis with no column to share, so each dot carries its own title and each row prints its ends in words"` |
| F2 | `VerdictSplit.svelte:122`, added to the `<div data-verdict-split ...>` | `data-readout-none="two population ranges on one score axis, so there is no column to share, and each range prints its lowest, middle and highest in words"` |
| F3 | `voices/+page.svelte:500-507`, added to the `<div data-windowed="feed-outcomes" ...>` | `data-readout-none="one square a day for every feed, each naming its own day and what that day did, so a strip would reprint the whole list"` |
| F4 | `voices/+page.svelte:625-636`, added to the `<div data-retiring="table" ...>` | `data-readout-none="one square a day for every source, each naming its own day and what that day did, so a strip would reprint the whole list"` |
| F5 | `VerdictSplit.svelte:170-172`, the visible strip label | becomes ``${strip.words}: ${reads(strip.at.min)} to ${reads(strip.at.max)}, middle ${reads(strip.at.median)}`` |
| F6 | `HoldoutMargin.svelte:373`, the visible strip label | becomes ``read as one story: ${agreedAt.min.toFixed(4)} to ${agreedAt.max.toFixed(4)}, middle ${agreedAt.median.toFixed(4)}, ${agreedBelow} below the line`` |
| F7 | `JudgeAgreement.svelte:269` | `restingNote=", the newest day"` |
| F8 | `MergeLinePlot.svelte:391` | `restingNote=", the newest day"` |

F5 renders as `called one story: 0.912 to 0.998, middle 0.961`. F6 renders as `read as one story: 0.9120 to 0.9980, middle 0.9610, 4 below the line`.

`middle` is not a new word on this route. `HoldoutMargin.svelte:392` already uses it inside a `<title>`. F5 and F6 make what the picture draws - the median circle at `VerdictSplit.svelte:185-191` and at `HoldoutMargin.svelte:376` - readable without a pointer. Without them F2's reason is a false sentence: the range does not print its middle today.

### 2e. Contract 4 - the route lists after row 5

`frontend/tests/console-readout.spec.ts` ends with two lists, and they are not the same list.

| # | List | Routes |
| --- | --- | --- |
| H1 | `ROUTES` at line 23 - the census that seeds on `svg` | `/console/`, `/console/machine/`, `/console/throughput/`, `/console/judgement/` |
| H2 | a second list, looped by the declare-or-say-why block (~line 151) and the reason-in-words block (~line 191) only | H1's four, plus `/console/voices/` |

`/console/voices/` is in H2 and not in H1 because it draws no `<svg>` of its own (Contract 6). The nine-line exclusion comment at lines 24-32 is deleted - it is false about both routes after this plan.

`frontend/tests/console-chrome.spec.ts` `ROUTES` at line 38 gains `/console/judgement/`.

`frontend/tests/console-voices.spec.ts` already lists all five routes and needs no edit. `frontend/tests/console-window-claims.spec.ts` spells routes without leading or trailing slashes and is not touched by this plan.

### 2f. Contract 5 - the resting note carries its own separator

`ChartReadout.svelte:51` renders `{readout.date}{resting ? restingNote : ''}` with nothing between them. Twenty-one of the twenty-three call sites pass a leading `", "`. The two that do not are F7 and F8, and they print `21 Septhe newest day` on the live site today.

The fix is at the call sites. A separator inside `ChartReadout.svelte` prints `21 Sept, , the newest day` in twenty-one places (Table C, C1).

Every existing spec that pins this text uses `toContainText`, which is a substring match, so it passes before and after: `console.spec.ts:1325`, `console-throughput.spec.ts:184` and `:236`, `console-timings.spec.ts:280` and `:328`.

### 2g. Contract 6 - which census reaches which drawing

`console-readout.spec.ts` runs two scans and they seed differently on purpose.

- `chartsOn()` seeds on `svg`. It is the one that asks "does this chart declare?", so it can only ask it of an `<svg>`.
- `declarationsOn()` seeds on `[data-readout-none]`. It is the one that asks "is this reason worth reading?", so it reaches anything that declares, `<svg>` or not.

The voices day matrices are `<div>` tables. They are invisible to the first scan and reachable by the second. That asymmetry is why row 4's own assertions live in the voices specs rather than in the shared one: `declarationsOn` holds their reasons to the five-word floor, and only a named positive assertion in each matrix's own spec proves the attribute is there at all.

`declarationsOn()` has no `closest()` walk-up today and does not need one.

### 2h. Contract 7 - the merged-stories panel height is fixed

`frontend/tests/console-judgement-merges.spec.ts:120` asserts `new Set(heights).size === 1` across every entry in `console.window_presets`, on `[data-console-panel="Stories the day merged"]`. A strip that appears at one preset and not another turns it red. So does a strip whose height changes with its content.

The `.merge-note` CSS comment in `MergedStoriesPanel.svelte` claims the note is the only variable-height part of the panel. That comment is part of the contract the test enforces; update it in row 1 rather than leaving it to contradict the code.

### 2i. Contract 8 - the two voices declaring elements

| # | Element | Line on `main` | Why this element and not another |
| --- | --- | --- | --- |
| I1 | `<div class="console-table mt-3" data-windowed="feed-outcomes" ...>` | 500-507 | It is the matrix. The per-row strips at line 549 carry `data-feed-strip`; putting the attribute there declares the matrix once per feed - about sixty times - and `declarationsOn` reads every one of them. |
| I2 | `<div class="console-table mt-3" data-retiring="table" ...>` | 625-636 | Same. The per-row strips are at lines 696 and 803. |

Both already carry `data-model-rule="no"` with a `data-model-rule-none` reason, under the parallel rule about which surfaces a model touched. That is a different rule with a different question. Carrying one does not satisfy the other.

## 3. Row 1 - The merged-stories chart prints its column

### Scope

`MergedStoriesPanel` draws one column a day for stories the day merged, and one dot a day for the biggest group, both at the same `columnsX[index]`. It declares nothing today, so an operator can read the biggest group only by hovering each dot one at a time. Give it a shared-column strip per Contract 2.

### Files touched

| # | File | Change |
| --- | --- | --- |
| J1 | `frontend/src/routes/console/judgement/MergedStoriesPanel.svelte` | Add the declaration pair, the `<svg>` wiring, the column array and the `<ChartReadout>` call, per Contract 2 and section 2a. Import `readoutMarks` and `pointerReadout` from `frontend/src/lib/charts/frame.ts`; they are not imported today. Accept a `readoutMaxShare` prop. Update the `.merge-note` comment per Contract 7. Change the empty-state text at line 193 from `fill="var(--color-text-tertiary)"` to `fill="var(--color-text-secondary)"` - it is the only sentence on the panel when the window is empty and it is currently drawn in the weight reserved for asides. |
| J2 | `frontend/src/routes/console/judgement/+page.svelte` | Pass `readoutMaxShare={data.chart.readout_max_share}` to `<MergedStoriesPanel` at line 88, matching lines 103 and 120. |
| J3 | `frontend/tests/console-judgement-merges.spec.ts` | Add the assertions below. |

### Acceptance gates

| # | Gate |
| --- | --- |
| K1 | `npm --prefix frontend run check` clean |
| K2 | `npm --prefix frontend run lint` clean |
| K3 | `npx playwright test console-judgement-merges` green, including the existing height invariant at line 120 |
| K4 | Browser smoke on `/console/judgement/` per CLAUDE.md section 12: zero new `[error]`, zero new `404`, and the page still renders with the panel's data absent |

### Oracle

Three new blocks in `console-judgement-merges.spec.ts`:

1. Pointing at a column prints a strip with exactly two rows, labelled `Merged` and `Biggest group`, in that order.
2. A column whose merged count is zero still prints both rows, and row 1 reads `0 of N published`.
3. The resting heading contains a comma before `the newest published day` - not a bare substring match on the note, which passes with the defect Contract 5 describes.

**What the oracle cannot settle.** It cannot tell whether the two rows are worth a reader's attention, or whether `Biggest group` is the right name for what row 2 counts. That is a reading judgement, and the strings in Contract 2 are the answer this plan carries.

### Decisions

| # | Decision | Reason |
| --- | --- | --- |
| L1 | `readoutMaxShare` stays a prop rather than gaining a default inside `ChartReadout` | Two callers on this route already read `data.chart.readout_max_share`. A default inside the component hard-codes a knob that lives in config (CLAUDE.md Guardrail #6). |
| L2 | The per-column `<title>` stays | It is the keyboard and screen-reader path. The strip is an addition, not a replacement. |
| L3 | The strip sits below the plot, between the `observeWidth` div and `.merge-note` | A strip over the plot covers the column the reader is pointing at. |
| L4 | The empty window reserves the strip's height with a fixed-height `<p>` | Contract 7. A strip that only exists at some window presets changes the panel height and turns line 120 red. |

### Rejected alternatives

| # | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| M1 | A one-row strip naming only the merged count | `ChartReadout` exists to print every series at one column. A one-row strip leaves `var(--chart-2)` - the dot the reader is pointing at - named nowhere. | Reopening the question of what the dot is for, and either deleting it or giving it its own figure. |
| M2 | A third `Published` row carrying the denominator | A strip row whose value is not a mark on the axis is a key describing something the picture does not contain. | A wider reading of what a strip row is, applied to all twenty-three call sites, not just this one. |
| M3 | `data-readout-none` on this panel instead, saying the columns are too narrow | False. The columns resolve; `MergeLinePlot` on the same route proves it on the same day axis. | Nothing - it is not available. A false reason fails Contract 1's five-word floor on reading, not on length. |

## 4. Row 2 - The two single-population figures say why they have none

### Scope

`HoldoutMargin` and `VerdictSplit` both draw a score axis with no day column to share. Neither declares. Each one already has a named wrapper that is an ancestor of its `<svg>`, so the declaration goes on the element that is already there.

Both also draw a median circle whose value is printed nowhere a reader can see without a pointer. F2's reason says each range prints its middle in words. Row 2 makes that true.

### Files touched

| # | File | Change |
| --- | --- | --- |
| N1 | `frontend/src/routes/console/judgement/HoldoutMargin.svelte` | Add F1 to the `<div data-holdout data-holdout-state ...>` at lines 175-183. It is the ancestor of the `<svg>` at line 209. Apply F6 to the visible strip label at line 373. |
| N2 | `frontend/src/routes/console/judgement/VerdictSplit.svelte` | Add F2 to the `<div data-verdict-split data-verdict-line data-verdict-days>` at line 122. Apply F5 to the label at lines 170-172. |
| N3 | `frontend/tests/console-judgement-holdout.spec.ts` | Add the assertions below. |
| N4 | `frontend/tests/console-judgement-verdict.spec.ts` | Add the assertions below. |

### Acceptance gates

| # | Gate |
| --- | --- |
| O1 | `npm --prefix frontend run check` clean |
| O2 | `npm --prefix frontend run lint` clean |
| O3 | `npx playwright test console-judgement-holdout console-judgement-verdict` green |
| O4 | Browser smoke on `/console/judgement/` per CLAUDE.md section 12 |

### Oracle

In `console-judgement-holdout.spec.ts`: the `[data-holdout]` wrapper carries `data-readout-none`, and the visible strip label contains `middle` followed by a four-decimal number.

In `console-judgement-verdict.spec.ts`: the `[data-verdict-split]` wrapper carries `data-readout-none`; every `[data-verdict-strip-label]` that is not the `Nothing was ... yet` case contains `middle`; and the printed middle equals the `cx` the median circle is drawn at, read back through the same scale.

**What the oracle cannot settle.** It cannot settle whether a reader who never hovers now knows enough. It can only prove the number reached the page.

### Decisions

| # | Decision | Reason |
| --- | --- | --- |
| P1 | The declaration goes on the existing named wrapper, not a new `<div>` | An arbitrary new `data-*` element is invisible to `declarationsOn`, which seeds on `[data-readout-none]` itself (Contract 6), and a second wrapper is a layout change nobody asked for. |
| P2 | The median ships in this row, not a later one | Without it F2 is a false sentence on the live page. A reason that describes something the page does not do is worse than no reason. |
| P3 | `middle` is the word, in both files | `HoldoutMargin.svelte:392` already uses it. A second word for the same idea on one route is a second name for one thing (CLAUDE.md section 0b). |

### Rejected alternatives

| # | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| Q1 | Give both figures a hover strip keyed on the population rather than a day | There is no shared column. Each dot and each range already carries its own `<title>`, and a strip would reprint the one thing the pointer is already on. | Redrawing both figures around a column axis they do not have. |
| Q2 | Print the median only in the `<title>` | It is already there on `HoldoutMargin`. A value reachable only by pointer is what this plan exists to remove. | Nothing gained; the reason string stays false. |
| Q3 | Tint `VerdictSplit`'s `eligible-disagreed` cell when it is above zero | B3. It is a colour-system decision, two lines, and it belongs to the design system page. | One design-system ruling on whether that cell is a warning surface, then two lines here. |

## 5. Row 3 - The judgement strips stop running a date into a note

### Scope

`JudgeAgreement` and `MergeLinePlot` already declare and already print a strip. Both pass `restingNote` without the leading separator that the other twenty-one call sites pass, so the live site prints `21 Septhe newest day` in two places on `/console/judgement/`.

### Files touched

| # | File | Change |
| --- | --- | --- |
| R1 | `frontend/src/routes/console/judgement/JudgeAgreement.svelte` | Line 269 becomes F7. |
| R2 | `frontend/src/routes/console/judgement/MergeLinePlot.svelte` | Line 391 becomes F8. |
| R3 | `frontend/tests/console-judgement-agreement.spec.ts` | Add the assertion below. |
| R4 | `frontend/tests/console-judgement-line.spec.ts` | Add the assertion below. |

### Acceptance gates

| # | Gate |
| --- | --- |
| S1 | `npm --prefix frontend run check` clean |
| S2 | `npx playwright test console-judgement-agreement console-judgement-line` green |
| S3 | Browser smoke on `/console/judgement/` per CLAUDE.md section 12, reading the resting heading of both strips |

### Oracle

One block per spec: the resting `[data-readout-day]` matches `/, the newest day$/`. A `toContainText('the newest day')` match is not the oracle - it passes with the defect present, which is how the defect reached the live site past five existing assertions (Contract 5).

**What the oracle cannot settle.** Nothing outstanding. The defect is a string and the assertion is on the string.

### Decisions

| # | Decision | Reason |
| --- | --- | --- |
| T1 | The fix is at the two call sites | Contract 5, and Table C row C1. `ChartReadout.svelte:51` is shared by twenty-three callers and twenty-one of them are correct. |
| T2 | The new assertion anchors on the end of the string | The five existing assertions use `toContainText` and all five pass with the defect. An oracle that cannot fail is not an oracle. |

### Rejected alternatives

| # | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| U1 | Put the separator in `ChartReadout.svelte` and drop it from every call site | It touches a shared component and twenty-three call sites to fix two strings, and it turns `console.spec.ts:1325`, `console-throughput.spec.ts:184` and `:236`, `console-timings.spec.ts:280` and `:328` into assertions nobody re-read. | A Level 3 pass over the component and every caller, with its own browser run. Available later; not worth it for two strings. |
| U2 | Fold this row into row 1 | It is a different defect on different files, and a reviewer reading "add a strip" would not expect a string fix. Separate commits inside the same pull request cost nothing and read better. | Nothing. They ship in the same pull request either way. |

## 6. Row 4 - The two day matrices on voices declare

### Scope

`/console/voices/` draws no `<svg>` of its own, which is why the exclusion note said a reader loses nothing there. That is measurably false: the route draws two day matrices - one square a day for every feed, and one a day for every source - carrying up to about six hundred facts, each reachable only by pointing at a square.

Neither matrix needs a strip (B2). Each square already names its own day and what that day did. What is missing is the sentence saying so. Add F3 and F4 to the two declaring elements named in Contract 8.

### Files touched

| # | File | Change |
| --- | --- | --- |
| V1 | `frontend/src/routes/console/voices/+page.svelte` | Add F3 to the `<div>` at lines 500-507 and F4 to the `<div>` at lines 625-636. Two attributes, nothing else. |
| V2 | `frontend/tests/console-voices-feeds.spec.ts` | Add the assertion below. |
| V3 | `frontend/tests/console-voices-retiring.spec.ts` | Add the assertion below. |

### Acceptance gates

| # | Gate |
| --- | --- |
| W1 | `npm --prefix frontend run check` clean |
| W2 | `npx playwright test console-voices-feeds console-voices-retiring` green |
| W3 | Browser smoke on `/console/voices/` per CLAUDE.md section 12, including the page with its feed data absent |

### Oracle

One block per spec: the matrix's own wrapper - `[data-windowed="feed-outcomes"]` and `[data-retiring="table"]` - carries a non-empty `data-readout-none`.

**What the oracle cannot settle.** It does not check the five-word floor or the reading quality of the reason. That is row 5's job, through `declarationsOn`, which seeds on the declaration and so reaches a `<div>` (Contract 6). This row proves the attribute is on the right element; row 5 proves the sentence is worth reading.

### Decisions

| # | Decision | Reason |
| --- | --- | --- |
| X1 | The attribute goes on the matrix wrapper, not the per-row strip | Contract 8. The per-row strips are at lines 549, 696 and 803. Declaring there repeats the reason once per feed and once per source, and `declarationsOn` reads every repeat. |
| X2 | This row is its own pull request, beside the judgement pull request | Different route, different reviewer question, and not one shared file. |
| X3 | The route is not added to `console-readout.spec.ts` `ROUTES` | H1 seeds on `svg` and this route draws none of its own. The route joins the second list, H2, in row 5. |

### Rejected alternatives

| # | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| Y1 | A hover strip over each matrix | B2. The square under the pointer already carries the fact, and a strip would reprint it. | Redrawing both matrices around a single shared column, which they do not have - each row has its own scale. |
| Y2 | Reuse the existing `data-model-rule-none` text as the readout reason | They answer different questions. `data-model-rule-none` says no model touched this surface. The readout reason says why there is no column to point at. | Nothing gained; the sentence would be off-topic and fail on reading. |
| Y3 | Widen `chartsOn` to reach these matrices so no new attribute is needed | B1. The widened seed newly un-declares the KPI card fill tracks, the prompt-reuse bars and the standing-weight tracks, turning three routes red on merge. | A console-wide declaration pass, Level 3, ahead of this plan. |

## 7. Row 5 - The rule reaches the judgement route and the voices reasons

### Scope

Rows 1 to 4 make five drawings obey a rule that does not currently look at them. This row points the rule at them, and deletes the note that says it never will.

### Files touched

| # | File | Change |
| --- | --- | --- |
| Z1 | `frontend/tests/console-readout.spec.ts` | `ROUTES` at line 23 gains `/console/judgement/` (H1). Add the second list (H2) and loop it from the declare-or-say-why block at about line 151 and the reason-in-words block at about line 191. Delete the nine-line exclusion comment at lines 24-32. Leave the four column-driven blocks at lines 225, 308, 364 and 393 on `ROUTES` - they need a column axis and `/console/voices/` has none. |
| Z2 | `frontend/tests/console-chrome.spec.ts` | `ROUTES` at line 38 gains `/console/judgement/`. |
| Z3 | `docs/architecture/publishing/console-charts.md` | Delete the stale clause at line 139 - "a bar of counts has no mark to land on and its column already carries a `<title>`". Row 1 makes it false. Record the declaration rule's two halves and the Contract 6 asymmetry in its place, in the page's own voice. |

### Acceptance gates

| # | Gate |
| --- | --- |
| AA1 | `npm --prefix frontend run check` clean |
| AA2 | `npx playwright test console-readout console-chrome` green |
| AA3 | The full console group green - this row changes what every console route is held to |
| AA4 | Browser smoke on `/console/judgement/` and `/console/voices/` per CLAUDE.md section 12 |

### Oracle

The widened loops are the oracle. They pass only if rows 1, 2 and 4 landed correctly, which is why this row waits for them.

Before pushing, prove the widened loop can fail: remove one of F1 to F4 from a working tree, watch the declare-or-say-why block go red on that route, restore it from the commit. Do the break and the restore as separate commands, and restore from `git checkout HEAD -- <path>` on a committed file, never over an uncommitted edit.

**What the oracle cannot settle.** It cannot prove the rule now reaches every drawing on the console - it does not, by B1. It proves the rule reaches every `<svg>` on four routes and every declared surface on five.

### Decisions

| # | Decision | Reason |
| --- | --- | --- |
| AB1 | No new spec file | `console-readout.spec.ts` already asks this exact question as its first sentence and already loops a route list. A second file asking it again is a second answer to one question (CLAUDE.md section 1a) and opens a new Playwright worker bin for nothing. |
| AB2 | Two lists in one file, not one | H1's four blocks need a column axis. Forcing `/console/voices/` through them asserts a column on a route that has none. |
| AB3 | The route lists stay hand-written | B4, and the owner ruling at `frontend/src/lib/console/band.ts:131-133`. |
| AB4 | This row ships alone, after the surfaces | A red oracle in a merged pull request that carries both the rule and the surfaces cannot say which one is wrong. |

### Rejected alternatives

| # | Alternative | Why not | What it would cost to take |
| --- | --- | --- | --- |
| AC1 | A new `console-declaration.spec.ts` looping every route | Duplicates a question the file above already owns, and its first assertion - that a route has at least one declaration - cannot fail on any route this plan touches. | One more file in the console group, a new worker bin, and a second place to edit every time a route is added. |
| AC2 | Land row 5 in the same pull request as rows 1 to 4 | AB4. | Nothing saved: the browser job runs per push either way. |
| AC3 | Add `/console/voices/` to `console-chrome.spec.ts` as well | Its strip-driven assertions at about lines 302 and 331 need a strip, and the voices matrices declare `none`. | An `if` inside a shared loop, which is how a route list stops meaning one thing. |

## Execution

Execute per `docs/how-to/execute-a-plan.md`: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honour the ESCALATE triggers in Table C.

**AUTHOR-AND-STOP.** This plan is written, not started. No row begins until the owner says so.
