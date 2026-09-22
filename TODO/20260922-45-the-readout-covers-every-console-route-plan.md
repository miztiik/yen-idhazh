# Plan 45 - The readout rule reaches every console route

**Last Updated**: 2026-09-22
**Correction level**: 3 (it crosses the published page and the rule that guards it)

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Two of the five console routes a reader can open are outside the rule that says every chart either prints a hover strip or says in words why it has none, and the note recording that says something untrue about both of them. |
| Hard scope - in | `/console/judgement/`'s three undeclared charts; the two chart specs' route lists; a declaration check that reaches a route whose chart has no shared column; the three notes that describe the old state. |
| Hard scope - out | see the table below |
| ESCALATE triggers | (1) A worker finds that `MergedStoriesPanel` cannot resolve two distinct columns on either build, so the pointer rule cannot be proved - stop and report, do not weaken the assertion. (2) Any row needs a change under `frontend/src/lib/charts/` - the strip engine is shared by every console route and moving it is a different plan. (3) The reason strings in C6 are refused on reading grounds - Susan rules, and the row pauses rather than shipping a placeholder. |
| Chosen strategy | Give the judgement route the declarations it is missing, then widen the rule to it; cover `/console/voices/` with the half of the rule its one chart can answer, in its own spec. Jony ruled the page half, Fowler the spec half. |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. **Parallel N = 1.** Not because rows share files - no two rows in this plan do - but because the four rows ship as two pull requests and each is one worker's job: rows 1 and 2 together, then rows 3 and 4 together. The gates are serial anyway; `gate_lock.py` is one lock across every worktree on the machine, so two workers would author in parallel and queue at the browser run regardless. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Giving `/console/voices/` a chart with a shared column | The route keeps one range plot, its target bars and its day strips. A reader loses nothing today: its one chart has no column two marks share, and both components it draws through already declare a reason | A panel on that route that plots two or more series against a shared category. Then it has a column, and the chart specs cover it with no change to this plan |
| A strip on `HoldoutMargin` or `VerdictSplit` | A reader hovers those two and gets the mark's own `<title>` rather than a column of values | A second series arriving on either plot that shares a category with the first. Both are single-population figures today, and a strip on one would print the row the pointer is already on |
| Deriving the nine console route lists from one exported constant | Adding a sixth route stays nine test edits | The owner relaxing the ruling recorded at `frontend/src/lib/console/band.ts:131-133`. Plan 43 row 4 priced this and it was refused there; nothing has changed |
| Reading the strip's values back against the committed day payloads | The strip's arithmetic is proved against the panel's own drawn marks, not against the ledger the page was built from | A worker finding that the drawn marks and the strip can disagree. Row 1's oracle is written so that is the failure it reports |

## Section 0a - The readings this plan is sized on

Taken 2026-09-22 against `origin/main` at `964356ea`.

| Reading | Value | Where |
| --- | --- | --- |
| Console routes the site serves | **5** | five `+page.server.ts` under `frontend/src/routes/console/` |
| Routes in `console-readout.spec.ts`'s list | **3** - `/console/`, `/console/model/`, `/console/machine/` | `console-readout.spec.ts:23` |
| Routes in `console-chrome.spec.ts`'s list | the same **3** | `console-chrome.spec.ts:38` |
| Charts on `/console/judgement/` that **do** print a strip | **2** - `JudgeAgreement`, `MergeLinePlot`, both since 2026-09-18 (`f555c5ef`, `9eaaa016`) | source |
| Charts on `/console/judgement/` that declare **nothing** | **3** - `MergedStoriesPanel`, `HoldoutMargin`, `VerdictSplit` | source |
| `<svg>` charts on `/console/voices/` | **1** - `SourceCutRange.svelte:183` draws one, used at `voices/+page.svelte:872`. `TargetBar` draws none | source |
| Drawing components `/console/voices/` uses, and their declaration | **2, both already declared** - `TargetBar.svelte:46` (10 words) and `SourceCutRange.svelte:185` (14 words) each carry `data-readout-none` with a reason | source |
| Tests in `console-readout.spec.ts` that go red on `/console/voices/` | **4** - the shared-column compare, the keyboard walk, the tap, and the named-strip count. First failing assertion at lines 225, 308, 364, 393 | measured |
| Tests in `console-chrome.spec.ts` that go red on `/console/voices/` | **3** - first failing assertion at lines 293, 302, 331 | measured |
| Which `content-similarity-judge/fitted-thresholds` rows each build carries | **canary 0, real build 3** (`2026/09/{18,20,21}.csv`) | `frontend/scripts/build-canary.mjs` writes five stores and not that one |
| What a new `console-*.spec.ts` costs in registration | **nothing** - `groupForSpec` routes any name matching `^console(?:-|$)` to the `console` group, and `FILES` is typed `Exclude<FrontendGroup, 'console'>` | `frontend/scripts/test-groups.ts:43` |
| What the console group costs in CI | **229 s of the browser job's 448 s mean** - the job runs 448 s with the group and 219 s with `SKIP_CONSOLE_SUITE` on. Measured 2026-09-22, n=8 and n=3 | `gh api .../actions/runs/<id>/jobs` |
| The number that kills the browser job | **1500 s** (`timeout-minutes: 25`). The job sits at 30 percent of it; the worst run seen is 32 percent | `.github/workflows/ci.yml:344` |
| Console tests today, and the cost of one | **584 of the suite's 997**, so 0.39 s of wall each | `.github/workflows/ci.yml:419`; 229 s / 584 |
| What rows 3 and 4 together add, worst case | **33 s - 7.4 percent of the browser job, 2.2 percent of the 1500 s that kills it.** The 6 h job in Guardrail #2 never binds here; our own 25-minute cap binds first and this plan does not approach it | derived from the four rows above |

**The two claims this plan corrects.** The note in plan 43 and both spec headers say neither route draws a chart that prints a readout strip. That is false for `/console/judgement/`, which draws two - and `console-readout.spec.ts:24-31` contradicts itself two lines later by naming `MergeLinePlot` as declaring its columns. And they say the fix for `/console/voices/` is to give its panels a strip; that route draws one chart, that chart has no column two marks share, and both components it draws through already carry a reason.

**The judgement route's split between columns and reasons is not a fixed number, and no row asserts one.** `MergeLinePlot` and `JudgeAgreement` take their columns from `fittedLines`, which reads `state/content-similarity-judge/fitted-thresholds` through `frontend/src/lib/server/similarity-ledger.ts:99`. No canary generator writes that store, so on the canary build both take the reason branch. After rows 1 and 2 the chart scan reports **one with columns and four with reasons on the canary, three and two on the real build**, and `declarationsOn` reports one reason more than the scan on either build because `RecordGates.svelte:75` declares one and draws no `<svg>`.

## Section 0b - What this plan does, in one list

1. `MergedStoriesPanel` gains a readout strip, because its bar and its dot share a day column.
2. `HoldoutMargin` and `VerdictSplit` declare in words why they have none.
3. Both chart specs add `/console/judgement/` to their route list, and both headers stop saying what is no longer true.
4. A new spec carries the half of the rule a route with no shared column can answer, over all five routes. What that buys today is two assertions on `/console/voices/` and nothing on the other four, and C8 prices it before anyone writes it.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The merged-stories chart prints its column | - | A | PENDING | - | - | - |
| 2 | The two single-population figures say why they have none | - | A | PENDING | - | - | - |
| 3 | Both chart specs cover the judgement route | 1, 2 | B | PENDING | - | - | - |
| 4 | The declaration rule reaches every route the site serves | 1, 2 | B | PENDING | - | - | - |

### Section 1a - The two pull requests and the files each owns

**The two pull requests never own one file, and they land in order.** P2's oracles cannot pass until P1 has merged.

| PR | Rows | Kind | Files it owns, exclusively |
| --- | --- | --- | --- |
| **P1 - the judgement route declares** | 1, 2 | behavioural | `frontend/src/routes/console/judgement/MergedStoriesPanel.svelte`, `HoldoutMargin.svelte`, `VerdictSplit.svelte`, `+page.svelte` |
| **P2 - the rule covers every route** | 3, 4 | behavioural | `frontend/tests/console-readout.spec.ts`, `console-chrome.spec.ts`, `console-declaration.spec.ts` (new), `docs/architecture/publishing/console-charts.md` |

**Rows 3 and 4 are one commit each inside P2.** That is what keeps the review boundary a third pull request would have bought: when the console group goes red, the reviewer reads two commits to tell whether the widened route list or the new spec did it.

### Section 1b - Why the pull requests fall where they do

| Question | Answer |
| --- | --- |
| Why rows 1 and 2 share a pull request | One surface, one risk, one review. Both are the judgement route's panels and neither can be judged without the other: the rule that covers them is row 3, and it is satisfied only when all three charts declare |
| Why P1 and P2 are separate | P1 changes the page; P2 changes the rule that judges the page. Landing them together hides which of the two an oracle was proving |
| Why rows 3 and 4 share a pull request, measured | A third pull request costs 437 s to 481 s of browser job per push, plus a second turn at the machine-wide gate lock - recorded at a 25 to 50 minute wait with siblings running. The tests row 4 carries add 2 s to 25 s per console run. **The separate pull request costs about twenty times what its contents will ever add, and it costs it on every push.** The two rows are both test-only, neither touches a line a reader renders, and their files stay disjoint inside the one pull request |
| Why P1 is not split into two | `MergedStoriesPanel` and the two figures are three files on one route with one reviewer and one browser run. Splitting them buys a second pull request and no isolation |

### Section 1c - Readiness, computed rather than read off a letter

**A row is ready when every `Depends-on` is DONE and its `Files touched` list shares no entry with a row in flight.**

| At this point | Ready together | Held, and why |
| --- | --- | --- |
| Start | **1, 2** - one worker, one pull request | 3 and 4 both need the judgement route to declare before their oracles can pass |
| P1 merged | **3, 4** - one worker, one pull request, a commit each | - |

**Peak workers: 1.** No row here measures anything, so the run-alone rule that applies to a benchmarking row applies to none of them. Two workers would not help even where the rows allowed it: `docs/how-to/run-the-gates.md` has every worker wrap `npm run build` and `npm run test:browser` in `gate_lock.py`, which is one lock across every worktree on this machine, so parallel authors queue at the gate.

## Section 1d - The contracts, declared before any code

Every shape below already exists. Nothing in this plan mints a persisted contract, so no schema moves, no `version` is stamped and no changelog entry is owed. The contracts are restated here at field level so a worker writes against them rather than reading four files to find them.

### C1 - The declaration pair

Every `<svg>` chart on an operator surface resolves, through `closest()`, to exactly one ancestor carrying exactly one of these two attributes.

| Attribute | Type | Meaning | Refused when |
| --- | --- | --- | --- |
| `data-readout-columns` | integer as a string, `>= 1` | This chart shares a column between its marks, and the element also holds exactly one `[data-readout]` strip | The element holds zero or more than one strip; or the element holds an empty-text `<span>`, `<i>` or `<em>` outside the strip, which the spec reads as a colour swatch competing with it |
| `data-readout-none` | free text | This chart has no column two marks share, and this is why | The reason is fewer than five whitespace-separated words |

Written as a pair on one element, exactly as `MergeLinePlot.svelte:201-204` does it:

```
data-readout-columns={columns.length > 0 ? columns.length : undefined}
data-readout-none={columns.length > 0 ? undefined : '<the reason, in words>'}
```

**The declaring element must be an ancestor of the `<svg>` and a descendant of `[data-surface="operator"]`.** The first is what `svg.closest(...)` walks; the second is what `declarationsOn` in `console-readout.spec.ts:126` scans. Where the panel already wraps its plot in a `data-windowed` div, that div is the declaring element.

### C2 - The strip's data shapes

From `frontend/src/lib/charts/frame.ts`. Field names are exact.

| Shape | Field | Type | Meaning |
| --- | --- | --- | --- |
| `ReadoutRow` | `label` | `string` | The series name, as the strip prints it |
| | `value` | `string` | What that series read at this column, already formatted |
| | `colour` | `string` | The series colour, so the strip is also the key. Empty where the chart lends none |
| `DayReadout` | `x` | `number` | The column's x **in the chart's own pixels** |
| | `date` | `string` | The column's name, already written the way a reader reads it |
| | `rows` | `ReadoutRow[]` | One entry per series, every series at this one column |
| `ReadoutMark` | `x` | `number` | The mark's x. The hit rule is nearest by x and nothing else |

`readoutMarks(columns: readonly DayReadout[]): ReadoutMark[]` builds the second from the first. **Build both from one array.** That is what stops the column a pointer lands on and the column the strip prints being two different columns.

### C3 - `ChartReadout` props

From `frontend/src/lib/components/ChartReadout.svelte`.

| Prop | Type | Required | Meaning |
| --- | --- | --- | --- |
| `readout` | `DayReadout \| null` | yes | The column to print. `null` draws nothing at all |
| `name` | `string` | yes | What the strip is of, so a page with several can be told apart. Becomes `data-readout="<name>"` |
| `maxShare` | `number` | yes | `chart.readout_max_share`, reaching the page as `data.chart.readout_max_share` |
| `resting` | `boolean` | no, default `false` | True while no column has been picked |
| `restingNote` | `string` | no, default `''` | Appended to the heading while resting, so a fallback does not read as a choice |
| `hint` | `string` | no | Has a default naming the pointer, the arrow keys and Escape |

### C4 - `pointerReadout` options

From `frame.ts:1022`. A Svelte action: `use:pointerReadout={{ marks, width, onSelect }}`.

| Option | Type | Meaning |
| --- | --- | --- |
| `marks` | `ReadoutMark[]` | Where each column sits, in the pixels `width` is measured in |
| `width` | `number` | The width the chart drew at, so a client x scales into chart pixels |
| `onSelect` | `(index: number \| null) => void` | Called with the column index, or `null` when the pointer leaves |

Bind it to the `<svg>` for a hand-written chart. The `<svg>` takes the focus; a tab stop per mark is a trap.

### C5 - What `MergedStoriesPanel` emits after row 1

The panel already computes `columnsX` (`dayColumns(drawn.length, box, ...)`) and `bars`, and already draws two series with two colours. Row 1 adds the strip and nothing else about the drawing changes.

| Thing | Value |
| --- | --- |
| Declaring element | the existing `<div data-windowed="merged-stories" ...>` |
| New attributes on it | `data-readout-columns` / `data-readout-none` per C1 |
| Strip `name` | `merged-stories` |
| Column `x` | `columnsX[index]` - the same array the bars and the dots are placed from |
| Column `date` | `dayMonth(day.date)` |
| Row 1 of the strip | `label` `Merged`, `value` the day's `merges` as a count, `colour` `var(--chart-1)` - the bar's own fill |
| Row 2 of the strip | `label` `Biggest group`, `value` the day's `largest` as a count, `colour` `var(--chart-2)` - the dot's own fill |
| Resting column | the newest drawn column, matching `MergeLinePlot`'s `columns[selected ?? columns.length - 1]` |
| `resting` prop | `selected === null`, as `MergeLinePlot` computes it |
| `restingNote` prop | `the newest day` - the same string `MergeLinePlot.svelte:386` passes, so two strips on one route do not name the same fallback two ways |
| Reason when `drawn` is empty | `no published day in this window, so there is no column to read` |

**Both rows are printed at every column, including a day whose `merges` is zero.** A row dropped on a zero makes the strip a different height per column and hides the fact that the day folded nothing.

`maxShare` reaches the panel as a new prop; the route already holds `data.chart.readout_max_share` and passes it to `MergeLinePlot` at `judgement/+page.svelte:103`.

**Three lines the strip does not work without, and the spec fails on the third.** Copy them from `MergeLinePlot.svelte:205-221`:

- `let selected = $state<number | null>(null);`
- `<!-- svelte-ignore a11y_no_noninteractive_tabindex -->` immediately above the `<svg>`
- `tabindex="0"` plus `use:pointerReadout={{ marks: readoutMarks(columns), width: box.width, onSelect: (index) => (selected = index) }}` on the `<svg>` itself

`console-readout.spec.ts:281` takes `owner.locator('[tabindex="0"]').first()` and skips the chart when there is none; line 308 then requires that at least one chart on the route was driven from the keyboard. On the canary build `MergedStoriesPanel` is the only element on `/console/judgement/` carrying `data-readout-columns`, so there is no second chart to carry that count.

### C6 - What the two figures declare after row 2

| Component | Attribute | Reason string |
| --- | --- | --- |
| `HoldoutMargin.svelte` | `data-readout-none` | `every mark is one labelled pair on one score axis, so a strip would print the pair the pointer is already on` |
| `VerdictSplit.svelte` | `data-readout-none` | `two population ranges on one score axis, and a range has no column that two series share` |

Both clear the five-word floor and both name the shape rather than the absence. Susan rules a rewording; a worker may not shorten either below five words.

### C7 - The route lists after row 3

| File | Constant | Value after |
| --- | --- | --- |
| `frontend/tests/console-readout.spec.ts:23` | `ROUTES` | `['/console/', '/console/model/', '/console/machine/', '/console/judgement/']` |
| `frontend/tests/console-chrome.spec.ts:38` | `ROUTES` | the same four |

Both keep `/console/voices/` out, and both say why in the corrected header: **that route draws one chart and it has no column two marks share, so every column-driven assertion in these two files has nothing to run on, and row 4's spec is where that route's declarations are checked.** Neither header may keep the sentence saying the two routes draw no chart that prints a strip.

### C8 - What `console-declaration.spec.ts` asserts after row 4

Its question, and its first sentence: **a decision to have no readout is a decision somebody took, and every route the site serves is held to it.**

| # | Assertion | Scope | What it buys that `console-readout.spec.ts` does not |
| --- | --- | --- | --- |
| 1 | No element under `[data-surface="operator"]` carries both `data-readout-columns` and `data-readout-none` | all five routes | **Nothing, while every declaring element follows C1's paired-`undefined` idiom.** Svelte omits an attribute whose value is `undefined`, so exactly one of the pair is ever present. It exists to catch the element somebody writes with both as literals, and the spec says so |
| 2 | Every `data-readout-none` reason is at least five whitespace-separated words | all five routes | The two reasons on `/console/voices/`, and nothing else. `console-readout.spec.ts:191` already runs this on the other four |
| 3 | Every `<svg>` that is not an icon and has a non-zero width resolves through `closest()` to one declaring ancestor | all five routes | `SourceCutRange`'s one chart on `/console/voices/`, and nothing else. `console-readout.spec.ts:160` already runs this on the other four |
| 4 | At least one route declares a reason, and at least one route declares columns | the set, once | It bounds assertions 2 and 3 against a console that drew nothing at all, which is the only way they can pass vacuously |

**The file's shape, fixed here so it is not invented.** One `test()` per route carrying assertions 1, 2 and 3 off a single `page.goto`, plus one `test()` for assertion 4 that loops the five routes. **Six test blocks, ten page loads.** The idiom at `console-readout.spec.ts:151` writes one test per assertion per route instead - 16 blocks and 20 loads for identical coverage, about 15 s more on every console run for ever.

**What this row really buys, priced honestly: two assertions on one route.** The price is a new spec file, a tenth hand-written route list, a section on a 666-line doc page and a bite proof, and 2 s to 25 s per console run. The reader-facing gain is that a reason on `/console/voices/` shortened to `none` would be caught, and a chart added to that route with no declaration would be caught. Nothing on the other four routes moves. **That is worth buying; a third pull request to carry it is not, which is why row 4 ships as a commit inside P2** (section 1b).

**What it cannot settle:** whether a strip prints the right values, or whether a pointer reaches the right column. Those are chart questions and they stay in `console-readout.spec.ts`, which is why assertion 3 here is a membership check and not a count.

### C9 - Registration

A spec whose filename matches `^console(?:-|$)` is routed to the `console` group by `groupForSpec` with no entry in `FILES`. **`frontend/scripts/test-groups.ts` is not edited by this plan.** A spec named anything else throws `No test group owns <file>` for the whole config.

## Section 2 - Row #1 - The merged-stories chart prints its column

- **Scope:** `MergedStoriesPanel` declares its columns and prints a readout strip carrying both series at the hovered day.
- **Files touched:** `frontend/src/routes/console/judgement/MergedStoriesPanel.svelte`, `frontend/src/routes/console/judgement/+page.svelte` (one prop passed through)
- **Acceptance gates:** local - `npm --prefix frontend run check`, then `npm --prefix frontend run test:changed -- --list` and the selected checks; CI - full suite and the browser smoke.
- **Oracle:** pointing at the first and the last drawn column of `merged-stories` yields two different headings, and at each column the strip prints exactly two rows whose labels are `Merged` and `Biggest group` and whose values equal the `data-merge-count` and `data-merge-largest` the same column's `<g>` carries. **What it cannot settle:** whether either number is the right count of merges - that is `mergeTotals`' own arithmetic, already covered by `frontend/tests/merge-line.spec.ts`.
- **Before relying on the canary, count the columns.** The rule needs two distinct drawn columns. Read `data-merge-days` off the built canary page first; where it is under 2, run the oracle against the real build and say so in the report (precedent: plan 38's width oracles, which skip on the canary and are verified on the real build).
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The bar and the dot are one column, so the panel takes columns rather than a reason. Both are counts of stories on one axis and the panel's own docstring says so | Jony |
 | 2 | The strip prints both rows at every column, including a zero | Susan |
 | 3 | The colours are the two the chart already draws, `var(--chart-1)` and `var(--chart-2)`. The strip is the key, so a second swatch anywhere in the panel fails C1 | Jony |
 | 4 | `MergeLinePlot` is the shape to copy, not a new one: same `columns` derivation, same `resting`/`selected` state, same `readoutMarks` call | Fowler |
 | 5 | The `<title>` per column stays. It is the mark's accessible name and the strip is an addition, never a replacement | Reader |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Declare `data-readout-none` and leave the panel alone | The two marks genuinely share a day column, so the reason would be false, and a false reason is worse than no declaration - it passes the rule and lies | Nothing to take; it is the cheaper answer and it is wrong | Jony |
 | 2 | Extract the column builder into `frontend/src/lib/console/merge-line.ts` so it can be unit tested | `MergeLinePlot` and `JudgeAgreement` both build theirs inline; a third shape with a different home is drift. The browser oracle above reaches the same property | About 30 lines and one new export, plus a case in `merge-line.spec.ts`. Worth taking the day a third panel on this route needs the same builder | Fowler |
 | 3 | Add a third strip row for the day's published total | The panel's own docstring keeps the share in type under the chart with its denominator, deliberately, because a rate on this axis is a flat line | Nothing but the row; it re-opens a ruling the panel already carries | Editor |

## Section 3 - Row #2 - The two single-population figures say why they have none

- **Scope:** `HoldoutMargin` and `VerdictSplit` each declare `data-readout-none` with the reason C6 fixes.
- **Files touched:** `frontend/src/routes/console/judgement/HoldoutMargin.svelte`, `frontend/src/routes/console/judgement/VerdictSplit.svelte`
- **Acceptance gates:** local - `npm --prefix frontend run check`, then the selected checks; CI - full suite and the browser smoke.
- **Oracle:** every `<svg>` on `/console/judgement/` resolves through `closest()` to exactly one element carrying one of the two declaration attributes, and the two new reasons are each at least five words. **What it cannot settle:** whether the reason is *true* - that is a reading, and Susan's ruling in C6 is where it is taken.
- **The declaring element.** Put the attribute on the element that already wraps the plot and carries the panel's own name where one exists. Where neither figure has such a wrapper, add one carrying a `data-*` name so the spec's failure message can say which chart failed; a bare `<div>` makes the failure read `unnamed`.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | `HoldoutMargin` gets a reason rather than a strip. Every mark is one pair on one axis, so the nearest-by-x column is the mark the pointer is on | Jony |
 | 2 | `VerdictSplit` gets a reason rather than a strip. Its own docstring records that two ranges replaced a 120-slot chart because 240 marks were a grey wall; a strip would reintroduce the reading it removed | Jony |
 | 3 | Neither reason may be shortened below five words. The floor is the spec's, and it exists because `none` and `n/a` pass an attribute check and tell a reader nothing | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Give both a strip so every chart on the route has one | Both are single-population figures. A strip on either prints the row the cursor is already on, which is the exact reading the `data-readout-none` half of the rule exists to refuse | Two strips and a reader who trusts them less, because one of them repeats what the pointer already showed | Susan |
 | 2 | One shared reason string on a wrapper around both | The two shapes differ - a scatter of pairs against two ranges - and one string would be true of one of them | Nothing; it loses the reason that made each decision | Jony |
 | 3 | Leave them undeclared and exclude them by name in the spec | An exclusion list grows and nothing prunes it, and the next chart added to the route inherits the exclusion silently | One line in the spec and a rule that stops covering the route it claims to cover | Fowler |

## Section 4 - Row #3 - Both chart specs cover the judgement route

- **Scope:** `console-readout.spec.ts` and `console-chrome.spec.ts` add `/console/judgement/` to their route lists, and both headers stop describing the state rows 1 and 2 removed.
- **Files touched:** `frontend/tests/console-readout.spec.ts`, `frontend/tests/console-chrome.spec.ts`
- **Acceptance gates:** local - `npm --prefix frontend run test:changed -- --list`, then the selected checks; where the selection does not reach the console group, `npm --prefix frontend run test:changed -- --group console`. CI - full suite and the browser smoke.
- **Oracle:** every assertion in both files runs against `/console/judgement/` and passes, and the chart scan resolves five `<svg>` charts on that route, every one of them declaring either columns or a reason. **The oracle does not assert the split between the two sides, because it is not a fixed number**: the canary build writes no `content-similarity-judge/fitted-thresholds` rows, so `MergeLinePlot` and `JudgeAgreement` take the reason branch there and the scan reports one with columns and four with reasons; the real build reports three and two. `declarationsOn` reports one reason more than the scan on either build, because `RecordGates` declares one and draws no `<svg>`. **What it cannot settle:** whether the sixth route added next quarter reaches these two lists. Nothing enforces that; the ruling at `band.ts:131-133` is why, and row 4's spec is the only check that would notice.
- **The one fixture fact this row rests on.** `backend/utilities/build_canary_day.py` publishes 20 days (`HISTORY_DAYS = 19` at line 108, plus `DATE`), and `windowOfDays` anchors on the newest date in the data with `today_anchor: "right"` (`config/appearance.json:97`), so all 20 sit inside the 30-day default and `MergedStoriesPanel` declares 20 columns. A red test here means a real defect or a moved fixture, and this line is how a worker tells them apart.
- **The header correction is part of the row, not a follow-up.** Both files currently say neither excluded route draws a chart that prints a strip. After rows 1 and 2 that is false of judgement twice over, and it was already false before them; `console-readout.spec.ts:24-31` already contradicts itself two lines later.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | `/console/voices/` stays out of both lists. It draws one chart and that chart has no shared column, so **seven tests across the two files go red on emptiness rather than on a defect** - four in `console-readout.spec.ts`, first failing at lines 225, 308, 364, 393, and three in `console-chrome.spec.ts` at 293, 302, 331. A rule that has nothing to hold a route to is not covering it | Fowler |
 | 2 | The corrected headers name row 4's spec as where that route's declarations are checked, so a reader of either file can find the other half | Fowler |
 | 3 | The lists stay hand-written and stay in their own files. `band.ts:131-133` records the owner's ruling, and plan 43 row 4 priced the alternative and was refused | Owner, quoted in the code |
 | 4 | `console-window-claims.spec.ts` spells its routes without the leading and trailing slash the others use. This row does not touch it; it changes membership in two files and nothing about form | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Add `/console/voices/` and guard the seven tests that go red on a route with no shared column | The guards reach the shared-column compare, the keyboard walk, the tap, the named-strip count and all three of `console-chrome.spec.ts`'s per-route tests. A spec whose every assertion is guarded against its own subject being absent has stopped asserting it | Seven guards, and a route that would silently pass both files for ever even if it later drew a chart with no strip | Fowler |
 | 2 | Widen all nine console route lists in this row | Seven of the nine have nothing to do with the readout rule, and plan 43 row 4 already made all nine list five routes. This row is about two of them | Seven more files in one review, and a diff where the load-bearing two are hard to find | Fowler |
 | 3 | Leave the headers and fix them in row 4 | Row 4 owns neither file, so the correction would land a pull request later than the change that makes it false | Nothing to take; it splits one edit across two reviews | Fowler |

## Section 5 - Row #4 - The declaration rule reaches every route the site serves

- **Scope:** a new `frontend/tests/console-declaration.spec.ts` holds every operator surface on all five console routes to the rule that a chart declares columns or gives a reason, and records the split in the page that owns the chart machinery.
- **Files touched:** `frontend/tests/console-declaration.spec.ts` (new), `docs/architecture/publishing/console-charts.md`
- **What this row buys, before anyone writes it: two assertions on one route** (C8). Nothing on the other four routes moves. The row is worth taking because `/console/voices/` is the only route where the declaration rule is currently unenforced, and it is refused on that price or on nothing. It ships as its own commit inside P2, not as a third pull request.
- **Acceptance gates:** local - `npm --prefix frontend run test:changed -- --list`, then the selected checks; where the selection does not reach the console group, `npm --prefix frontend run test:changed -- --group console`. `python backend/utilities/doc_load.py` before and after the docs edit. CI - full suite and the browser smoke.
- **Oracle:** assertions 1, 2 and 3 of C8 each go red under a named single-edit bite, and each one is restored byte for byte afterwards. **What it cannot settle:** whether a strip prints the right values or whether a pointer reaches the right column - those stay in `console-readout.spec.ts` - and assertion 4, which bounds the file against a console that drew nothing at all and cannot be bitten by a single edit.
- **The three bites, named, and all of them on `/console/voices/`.** A bite on `/console/` proves only that the older spec still works. Take a copy of the file first, run one bite, restore, compare SHA-256, then run the next.

 | Assertion | The edit | What must go red |
 | --- | --- | --- |
 | 3 | Delete `data-readout-none` at `SourceCutRange.svelte:185` | assertion 3, on `/console/voices/` - that component draws the route's one `<svg>` |
 | 2 | Shorten the same reason to `none` | assertion 2 |
 | 1 | Add `data-readout-columns="3"` beside the reason on the same element | assertion 1 |

**`TargetBar` is not a valid target for any of the three.** It draws no `<svg>`, so removing its reason makes nothing go red - assertion 3 never sees it, assertion 2 has nothing left to measure, and assertion 1 needs an addition rather than a removal.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | A new file rather than a fifth route in an existing one. This asks a different question - is a decision to have no strip a real decision - and it reaches `/console/voices/`, which the two chart specs cannot cover because its one chart has no shared column | Fowler |
 | 2 | The file is named `console-declaration.spec.ts`, so `groupForSpec` routes it to the `console` group with no edit to `test-groups.ts` (C9) | Fowler |
 | 3 | The spec's header states what each assertion buys over `console-readout.spec.ts` (the right-hand column of C8), and states that assertion 1 cannot fail while every declaring element follows C1's paired-`undefined` idiom. A test that cannot fail and does not say so is the defect this plan exists to remove | Fowler |
 | 4 | `docs/architecture/publishing/console-charts.md` records the split - which spec owns which half of the rule - beside the frame and strip machinery it already documents. The page is 666 lines, so the row pays the split test in `docs/reference/documentation-structure.md` before adding to it and says in the pull request why it stays whole | Fowler |
 | 5 | The route list in this file is hand-written like the other nine, for the reason at `band.ts:131-133`. It is the tenth, and the row says so rather than leaving the count to be recounted | Owner, quoted in the code |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Put these assertions in `console-readout.spec.ts` | That file's subject is charts with a shared column and its first sentence says so; a route whose one chart has no column is not its subject, and four of its tests plus three of `console-chrome.spec.ts`'s would need guarding to admit one | The seven guards option 1 of row 3 prices, plus a file answering two questions | Fowler |
 | 2 | Assert a count of declared surfaces per route rather than membership | A count goes stale the day a panel is added or removed, and the failure then names a number rather than a chart | Nothing but the assertion, and a test somebody edits on every console change | Fowler |
 | 3 | Skip `/console/voices/` because its one chart has no column | Assertions 2 and 3 do reach it - two reasons and one `<svg>` - and a reason shortened to `none` on that route would go unnoticed today | Nothing to take. It is the only route where the check is currently unenforced, which is the reason to include it | Susan |
 | 4 | Derive the five routes from `frontend/src/lib/console/band.ts` | Overturns the ruling recorded in the code at `band.ts:131-133`, which plan 43 row 4 priced and the owner refused | The owner relaxing that ruling, and the same question re-opened for all ten files rather than one | Owner |

## Execution

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 1 row in flight, refilling the slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.
