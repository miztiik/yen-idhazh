# Double the truncation cap, and publish what it costs - Plan

**Last Updated**: 2026-08-28

**Level**: 5. Two persisted contracts move (`EvalRow`, `ItemHealthRow`) and the cap is a pipeline-fingerprint input.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 3; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

---

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | 6.10 percent of published items are cut at 1923 words and no committed number says what the cut costs, so the cap has never been tuned on evidence. |
| Hard scope - in | `extract.truncation_cap_tokens` 2500 -> 5000; `truncation_flagged` redefined to the exact fact; one new `ItemHealthRow` column carrying the pre-cap word count; five cut figures and one source table on `/console/`; a pointer readout on two charts; a `/console/` page-weight ceiling; two written rollback triggers; one new Editor persona. |
| Hard scope - out | `n_ctx`, `max_output_tokens`, `request_timeout_minutes`, `run.shard_timeout_minutes`, `run.safety_ceiling_per_run`, shard sizing. Re-cutting any confidence band. Head-plus-tail reading. Deleting `hhem_full` or `hhem_delta`. Generating `frontend/src/lib/payload/types.ts`. Renaming `Item telemetry viewport`. |
| ESCALATE triggers | (1) Any row that requires moving `METRICS_VERSION` from `"3"`. (2) Any row that requires moving `n_ctx`, `request_timeout_minutes` or `run.shard_timeout_minutes`. (3) Rollback trigger A or B firing after Row 8 (see Row 7). (4) A widest-request reading above 7,800 prompt-plus-output tokens on the first run at the new cap - the cap comes down to 4000, the context window does not go up. |
| Chosen strategy | Land the instrument before the change: the console must be able to see a cut before the cap moves, or the change is unmeasurable (Rule #10). Reader-before-writer twice - Row 1 before Row 2, Row 5 before Row 8. Ruled by Fowler (Architecture and Engineering), costed by Carmack (Engine and Runtime), surface ruled by Jony (UI/UX). |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3. |

### Measured basis (all 2026-08-28, worktree at `origin/main` sha `4c99c72`)

Re-derived at `4c99c72` after PR #191 (repairs the 610 impossible ledger rows and makes `EvalRow.source_word_count` nullable) and PR #170 merged. Every figure below moved; none of them changed a decision.

| Fact | Value | Source |
| --- | --- | --- |
| Cut rate, committed digests | 164 of 2688 items, **6.10 percent**, 8 days | `frontend/public/digest/**/digest.json` |
| Cut items per run | 1 to 12 over 14 runs, mean 7.86 | `state/item-health/2026-08.csv` |
| Cut point today / after | 1923 words / 3846 words | `int(cap / TOKENS_PER_WORD)`, `TOKENS_PER_WORD = 1.3` |
| At-cap item cost | 3504 input tokens, 228.7 s reading, 80.2 s writing, 308.9 s total | `state/item-health/2026-08.csv`, n=110 |
| Below-cap item cost | 1781 input tokens, 78.5 s reading, 54.5 s writing, 133.0 s total | same ledger, n=1686 |
| Reading rate / writing rate | 12.05 tok/s uncached prefill / 4.88 tok/s decode. Reading is **61.0 percent** of model milliseconds | same ledger, 14 runs |
| Cost of the change | **+10,300 to 11,000 input tokens a run, +14.3 to 15.2 worker-minutes, about 5 percent more machine time**; +3.6 min typical on the slowest shard, +10.9 min on a bad draw, +47 min pathological | Carmack, arithmetic in Row 8 |
| Binding constraint | `run.shard_timeout_minutes = 150`, slowest measured `work` job **85.6 min** | `config/idhazh.json`, `.github/workflows/digest.yml` L261 |
| Context fit | widest measured request 3775 + 900 of 8192 at cap 2500; projected **7271 to 7447 of 8192** at cap 5000, 9 to 11 percent clear | qualification run `33016222069` |
| `hhem_delta` on cut items | 20 of 22 exactly 0.0, one -0.123512, one **+0.038063**. `truncation_flagged` fired **0 of 22** against a threshold of +0.1 | `state/scores.csv`, the 337 rows stamped `2026-08-27T20:30` |
| Ledger rows whose pre-cap length is unrecoverable | **142**, carrying a null `source_word_count` after PR #191 | `state/scores.csv` |

Three claims that look like measurements and are not, stated so a later reader cannot mistake them: the 1.3 tokens-per-word constant is a **placement estimate**; the before sample for any cap comparison is **22 cut items over two run-days**; and the projected context fit is a scaling of one measured request, not a reading.

---

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Console reads the cut flag through the version boundary | - | A | PENDING | - | - | - |
| 2 | `truncation_flagged` becomes `Article.truncated`; delete `truncation_gap_max` | 1 | B | PENDING | - | - | - |
| 3 | `ItemHealthRow` gains `source_words_before_cap` | - | A | PENDING | - | - | - |
| 4 | Cap reference line and a pointer readout on two charts | 1 | B | PENDING | - | - | - |
| 5 | Console publishes the cut figures and the source table | 3, 4 | C | PENDING | - | - | - |
| 6 | `/console/` gains a page-weight ceiling | 5 | D | PENDING | - | - | - |
| 7 | The two rollback triggers, written down and checkable | - | A | PENDING | - | - | - |
| 8 | `extract.truncation_cap_tokens` 2500 -> 5000 | 2, 5, 6, 7 | E | PENDING | - | - | - |
| 9 | The Editor persona | - | A | PENDING | - | - | - |

---

## Section 2 - Row #1 - Console reads the cut flag through the version boundary

- **Scope:** `readInPart` becomes null for a day whose rows predate the redefinition, instead of counting a column that meant something else.
- **Files touched:**
  - `frontend/src/lib/server/model-work.ts`
  - `frontend/tests/console.spec.ts`
  - `docs/architecture/publishing/telemetry-series.md`
- **Acceptance gates:** `npm run check`; `npm run test:browser`; `npm run bundle-gate`; browser smoke per CLAUDE.md section 12.
- **Oracle:** `readInPart` is non-null for a day **exactly when** that day holds at least one `state/scores.csv` row stamped at or after the boundary, and equals the count of `truncation_flagged` over those rows alone. A two-row fixture ledger, one row either side of the stamp. The predicate is asserted in both directions so it cannot pass by always returning null.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Ships before Row 2, not after. The version branch is inert until a row carries the new stamp, so it is safe first and lossy second. | Fowler |
| 2 | The branch keys on the row's own `version` cell, never on `scorer_version`. Two preceding semantic changes on this contract already used the `version` cell. | Fowler |
| 3 | Absence prints as absence. Zero is forbidden - `model-work.ts` already states "null is a designed state and it is not zero". | Fowler |
| 4 | PR #191 made `EvalRow.source_word_count` nullable and 142 committed rows now carry a null. `compressionPoint()` reads `Number(row.source_word_count ?? 0) \|\| 0` and drops any point at or below zero, so those 142 items silently leave the scatter. That is the correct outcome - their pre-cap length exists nowhere - but the chart must say so rather than shrink in silence. **The caption sentence lands in Row 4**, which owns `CompressionScatter.svelte`; this row only records why it is needed. | measurement 2026-08-28 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Restamp historical rows to today | Erases the only marker of which rows predate the change. `docs/architecture/contracts/schemas.md` states the rule. | Fowler |
| 2 | Leave the console reading the old column until Row 2 lands | The page currently prints "The article was too long, so the machine read the start and stopped" from a cell that holds a faithfulness gap. That is a live Rule #10 breach, and it is cheapest to fix on the read side first. | Fowler |

---

## Section 3 - Row #2 - `truncation_flagged` becomes `Article.truncated`; delete `truncation_gap_max`

- **Scope:** the flag stops reading a value that has no positive range and starts reading whether extract cut the body.
- **Files touched:**
  - `backend/idhazh/evals/score.py`
  - `backend/idhazh/contracts/eval_row.py`
  - `backend/idhazh/contracts/app_config.py`
  - `config/idhazh.json`
  - `schemas/eval-row.schema.json`, `schemas/app-config.schema.json`
  - `backend/tests/test_evals.py`
  - `backend/tests/test_canary_day.py` - line 70 asserts the flag equals the delta rule and pins the defect; line 73, added by PR #191, already asserts the correct rule and must stay
  - `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff check .`; `mypy --strict`; full `pytest`; contract drift gate; `EvalRow.csv_columns()` byte-identical to the committed `state/scores.csv` header; assert `METRICS_VERSION == "3"`.
- **Oracle:** an article built through the **real** `extract.to_article_with_source` from one fixture page longer than the cap and one shorter satisfies `row.truncation_flagged is article.truncated` on both. Building through the real extractor is what makes the cut genuine; restating the arithmetic in the test can pass when both sides are wrong together.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `hhem_delta` is not a threshold problem and `truncation_gap_max` is not a knob to retune. `score_over_chunks` is max over 900-word windows stepping 750, so the cut text's final window (1500 to 1923) is **not** a window of the full text and the two window sets are not nested - the delta can go slightly positive. It does not go far enough to matter: measured over 22 cut items the range is **-0.1235 to +0.0381** against a threshold of **+0.1**, and the flag fired 0 times. Fowler ruled the delta non-positive by arithmetic; the measurement corrected that to positive but far under the threshold, which reaches the same conclusion from a weaker and true premise. | Fowler, corrected by measurement 2026-08-28 |
| 2 | Keep `hhem`, `hhem_full` and `hhem_delta`. They answer a different question - what the cut cost - and that instrument was first wired on 2026-08-27T20:30. Deleting a working instrument two days in on n=22 is the reverse of Rule #10. | Fowler |
| 3 | Delete `evaluation.truncation_gap_max` in the same commit as its last caller, so there is never a state where the knob exists and nothing reads it. | Fowler |
| 4 | Drop the brief-item verbatim clause from the same boolean. `verbatim_run` and `extractiveness` already carry that fact and the console already prints it as "Copied, not rewritten". One predicate per column. | Fowler |
| 5 | No ledger rewrite. `require_matching_header` is called from `_append` and from nothing on the read path; a semantic redefinition adds and removes no field, so the header is byte-identical. | Fowler |
| 6 | Do not move `METRICS_VERSION`. It is folded into `scorer_version`, which is Defect 2's counter; moving it takes that gate from 2 of 10 to 0 of 10. `truncation_flagged` is not a `band()` input, so it does not require the move. | Fowler |
| 7 | The read-side migration branches on the row's `version` cell: a row stamped before `2026-08-28` is **unknown**, never False. Two sub-cases, neither recoverable from the row - before `2026-08-27T20:30` the delta was two scores of one text; between the two stamps the delta was real and the instrument was wrong. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Retune `truncation_gap_max` down to catch the +0.038 case | It would fire on chunk-boundary noise, not on truncation. The one positive value comes from the cut text's shorter final window scoring higher, which is an artifact of where `chunks()` steps - not evidence the cut cost anything. | Fowler, corrected by measurement 2026-08-28 |
| 2 | Keep both columns and let them mean different things | The column's name says "was it cut". A boolean whose name says that must be whether it was cut. Its one consumer prints exactly that sentence. | Fowler |
| 3 | Add a separate "the cut cost us" flag now | A real, different question that needs a threshold with a measured basis. n=22 is not one. It gets its own name and column when it has one. | Fowler |
| 4 | Move `METRICS_VERSION` to be safe | Costs at least ten more run-days on Defect 2 for a column no threshold reads. | Fowler |

---

## Section 4 - Row #3 - `ItemHealthRow` gains `source_words_before_cap`

- **Scope:** the item-health ledger records how long the body was before the cap cut it, so a cut can be detected without a hardcoded word constant.
- **Files touched:**
  - `backend/idhazh/contracts/item_health.py`
  - `backend/idhazh/telemetry.py`
  - `backend/idhazh/publish_telemetry.py`
  - `schemas/item-health-row.schema.json`
  - `state/item-health/*.csv`
  - `frontend/public/telemetry/*.csv`
  - `backend/tests/test_telemetry.py`, `backend/tests/test_publish_telemetry.py`
  - `docs/architecture/sources/item-health.md`, `docs/architecture/publishing/telemetry-series.md`
- **Acceptance gates:** `ruff check .`; `mypy --strict`; full `pytest`; contract drift gate; every migrated row read back through `from_csv_row` before commit.
- **Oracle:** append one new row to a **byte copy of the committed** `state/item-health/2026-08.csv` after migration, then assert every historical cell is where it was and every pre-existing row's new cell is empty. This is the check `docs/architecture/contracts/schemas.md` names under "Widening a row ledger writes an empty cell, never a value invented today".

**The column:**

```python
source_words_before_cap: int | None = Field(
    default=None,
    ge=0,
    description=(
        "Words in the extracted body before extract.truncation_cap_tokens cut it, "
        "taken from Article.source_word_count. source_words is the same counter "
        "after the cut, so source_words_before_cap > source_words is the cut and "
        "nothing else. A count, never the text. Null before 2026-08-28."
    ),
)
```

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The count, not a `truncated` boolean. The boolean is exactly `source_words_before_cap > source_words`; the count additionally answers "by how much", which two published figures read. One migration on this ledger, not two. | Fowler |
| 2 | The name is not `source_word_count`. That is the `EvalRow` spelling and one letter from the existing `source_words` on the same row meaning the opposite. Defect 17 was two word counters one string apart read as truncation. | Fowler |
| 3 | It joins `PUBLIC_COLUMNS`. It is a word count of our own extraction, the same class as `source_words`, which is already public. The forbidden three - `canonical_url`, `url_key`, `detail` - are untouched. | Fowler |
| 4 | Expand-only migration. Append at the end of the model, rewrite each shard with an empty cell on every historical row. Expect a merge conflict on the current month shard; resolve by taking upstream whole and re-running the migration. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Detect a cut with `source_words == int(cap / 1.3)` | The constant becomes 3846 after Row 8, so a 7-day window spanning the change mixes two cut points and any hardcoded value silently breaks. It also mislabels an article sitting exactly on the boundary. | Fowler |
| 2 | Read the cut rate from `state/scores.csv` | No `source_id` on the row, so a per-source table would parse a hostname out of a URL and split `www.` variants. The population is scored items and `evals/writer.py` dedupes on `OBSERVATION_KEY`, so the denominator varies with what an earlier run measured. | Fowler |
| 3 | Read it from `frontend/public/digest/**/digest.json` | The population is published items only, and a cut item is more likely to then fail, so the denominator systematically excludes the population the cap affects most. Keep it as a cross-check, never the source. | Fowler |
| 4 | Persist the pre-cap text | Not ours to republish (CLAUDE.md section 0a). | Fowler |

---

## Section 5 - Row #4 - Cap reference line and a pointer readout on two charts

- **Scope:** the scatter says where the cut falls, and two charts gain a readout that works on touch and keyboard.
- **Files touched:**
  - `frontend/src/lib/charts/frame.ts` (new `pointerReadout` action, beside `observeWidth`)
  - `frontend/src/lib/components/CompressionScatter.svelte`
  - `frontend/src/lib/components/ThroughputTrend.svelte`
  - `frontend/tests/console.spec.ts`
  - `frontend/bundle-baseline.json`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `npm run check`; `npm run test:browser`; `npm run bundle-gate` (the readout is JavaScript and is priced in `bundle-baseline.json` with a sentence saying what those bytes buy); browser smoke per CLAUDE.md section 12 including a touch emulation pass.
- **Oracle:** over a fixture window holding items cut at two different post-cap word counts, the chart draws exactly one dashed line per distinct value, each label names its own value and date range, and **no line is drawn for a cap no visible point was cut by**. A config-derived line would draw when the data holds nothing; a data-derived line cannot.

**The line's value comes from the data, never from config:**

```
capsInView = distinct source_seen_word_count
             among visible points where truncation_flagged
             and source_seen_word_count > 0
```

**Reader-facing strings, exact:**

| Where | Text |
| --- | --- |
| One cap in view | `cut at 1,923 words` |
| Oldest of several | `cut at 1,923 words (to 27 Aug)` |
| Later ones | `cut at 3,846 words (from 28 Aug)` |
| Conditional clause, rendered only when a pre-2026-08-27 cut point is in view | `Articles read before 28 August were measured after the cut, so their diamonds sit on the line rather than past it.` |
| Conditional clause, rendered only when the window holds rows with no recorded article length | `{n} articles in this window recorded no length before the cut, so they are not plotted.` |
| Intro | `Article length uses a log x axis, so a 100-word note and a 10,000-word feature both fit. A diamond is an article that ran past the cap, so the machine read the start and stopped there.` |
| Key | `Dot - one article. Diamond - an article cut at the line. Dashed line - where the cut falls. Shaded band - the summary length we aim for at that article length.` |
| Scatter readout, cut item | `23 Aug - ai-0417291083` / `Article 4,120 words, cut to 1,923. Summary 148 words.` |
| Scatter readout, uncut item | `23 Aug - ai-0417291083` / `Article 812 words. Summary 96 words.` |
| Keyboard hint under each chart | `Keyboard: Left and Right step through the days. Escape closes.` |

**Line treatment:** `<line>` from `box.top` to `box.bottom` at `xAxis.scale(capWords)`, stroke `var(--color-text-tertiary)` at `stroke-opacity="0.7"` width 1, `stroke-dasharray="3 3"`, drawn after the band zone and before the points. Label `<text>` at `font-size="10"`, `fill="var(--color-text-tertiary)"`, y at `box.top + 9` with each further label 12px lower so labels stack and never collide, x at `x + 4` `text-anchor="start"` flipping to `x - 4` `text-anchor="end"` when `x > box.right - 90`. Hook `data-cap-line={capWords}`.

**Readout mechanism:** one Svelte action in `frame.ts`. `pointermove` and `pointerdown` on the `<svg>` (one stream covers mouse, pen and touch), plus `focusin`, `keydown`, `pointerleave`, `focusout`. Hit rule is nearest mark **by x** from the positions the chart already computed. Surface is a plain absolutely-positioned `<div>` inside the existing chart card, **pinned to the top of the plot, never to the pointer**. The `<svg>` gets `tabindex="0"`; Left and Right step, Home and End jump, Escape closes. Focus reaches the series, not 2,571 data points.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The cap is a line on the existing scatter, not a new chart. The cut is a value on the x axis and nothing else. | Jony |
| 2 | The line is derived from `source_seen_word_count` among the visible cut points, not from `extract.truncation_cap_tokens`. A 30-day window may hold two settings, and a config-derived line is a claim about a setting rather than about the data. | Jony |
| 3 | The SVG `<title>` elements stay as the accessible name and are never the publication. Nothing a readout alone can tell you may be required to read the chart - which is also the whole no-JavaScript answer. | Jony |
| 4 | Only `CompressionScatter` and `ThroughputTrend` get the readout. `ThroughputTrend.caption()` already builds the sentence and today it exists only inside a `<title>`; reuse it verbatim, no new copy. | Jony |
| 5 | Not `--band-low` for the line. A red vertical says the cap is a failure. The cap is a setting. | Jony |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A new chart for the cutoff | It is a line. A chart that says what a line says has not earned its place. | Jony |
| 2 | An SVG `<title>` as the tooltip | Does not fire on touch, carries a delay nobody chose, cannot be styled, is not keyboard-reachable, and does not survive a screenshot pasted into an issue. | Jony |
| 3 | A readout pinned to the pointer | A readout under a thumb is a readout nobody reads. | Jony |
| 4 | Tab stops on every data point | A 2,571-stop tab order is a trap, not access. | Jony |
| 5 | A readout on `FailurePanels`, `StageTimings` or the run-health strip | Each already prints its headline in type; three readouts across a three-up row is three things moving at once. | Jony |
| 6 | A charting library | There is none today and this adds none. One action beside `observeWidth`. | Jony |
| 7 | A second shaded region for the cut | The band zone already means "target summary length". Two shadings meaning two things on one plot is one too many. | Jony |

---

## Section 6 - Row #5 - Console publishes the cut figures and the source table

- **Scope:** the console prints, per day and per source, how much the cap is costing.
- **Files touched:**
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `frontend/tests/console.spec.ts`
  - `docs/concepts/design-system.md`
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `npm run check`; `npm run test:browser`; `npm run bundle-gate`; browser smoke per CLAUDE.md section 12, including the page rendered with its data file absent.
- **Oracle:** over a fixture month holding both migrated (empty-cell) and post-migration rows, the source table's row count equals the number of distinct `source_id` with at least one cut item in the window, each count equals `source_words_before_cap > source_words` for that source, and **a source with only empty cells prints `-`, never `0`**.

### Metrics published by this plan

The full catalogue the owner asked for. Every one names the decision it changes; a metric no decision reads is not on this list.

| # | Metric | Reader-facing name | Ledger | Supplied by | Decision it changes |
| --- | --- | --- | --- | --- | --- |
| 1 | Items cut, per day | `Article read only in part` | `state/scores.csv` | exists; Row 1 fixes its read, Row 2 fixes its meaning | Whether the cap is costing articles at all. |
| 2 | Items cut as a share of the day | `Read only in part, as a percent` | `state/scores.csv` | Row 5 | Lets a busy day and a quiet one compare. |
| 3 | Items cut, per run | one clause in the run square's label | `state/item-health/` | Row 5 | Which run drew the long articles. Not published as a figure - see Decision 2. |
| 4 | Sources cut most often, 7 days | `Sources cut short most often` | `state/item-health/` | Rows 3 + 5 | Which source is costing articles, so a source can be traded off. |
| 5 | Longest article per source | `Longest article, words` | `state/item-health/` | Rows 3 + 5 | **Whether doubling the cap actually fixes that source.** If nvidia's longest is 2,100 words, 3,846 fixes it entirely; at 12,000 it fixes nothing. |
| 6 | Words cut - median and max over cut items | inside the source table and the scatter readout | `state/item-health/` | Rows 3 + 5 | Whether the **next** cap move is worth anything. Nothing today says whether the tail past the cut is 200 words or 10,000. |
| 7 | Model milliseconds on cut items against uncut | `Time to write one` split by cut | `state/item-health/` | Row 5 | Whether the day still fits the 240-minute cron gap. |
| 8 | Items refused for length | `code = context_exceeded` count | `state/item-health/` | existing column, zero new fields | **Rollback trigger B.** At cap 2500 this row was impossible by arithmetic. | 
| 9 | Where the cut falls | the dashed cap line | `state/scores.csv` | Row 4 | Nothing - it is the axis annotation that makes 1 to 7 legible. |
| 10 | What the cut cost, with its n | `hhem_full - hhem` over cut items | `state/scores.csv` | recorded, not charted | Whether the cap stays a tuned knob. n=22 today; print the n beside it or it is not a measurement. |

**Rejected metrics**, so nobody re-proposes them: truncation rate per vertical (no decision reads it - a vertical is a topic queue, you cannot drop one; a source you can); mean words cut over all items (a rate wearing a length's units); a truncation trend chart (25.0, 10.0, 7.5, 5.7, 6.2, 6.6, 4.8 percent, and the first two days hold 4 and 10 items - drop those and it is five points spanning 2.7 points, which is charting a constant); `truncated_at_tokens` distribution (`extract.py` returns `cap_tokens` literally, so it is a chart of a config key); anything needing the pre-cap text.

### The source table, exact

| Header | Cell |
| --- | --- |
| `Source` | `source_id` |
| `Cut short` | count |
| `Articles` | denominator |
| `Share cut` | whole percent, or `-` below `console.min_attempts_for_rate` (5) |
| `Longest article, words` | pre-cap word count, thousands grouped, `ps-6` gap |

Heading: `Sources cut short most often`. Intro: `The last 7 days. An article longer than the cap is read from the start and stopped there, so the end never reaches the machine. Sorted by how many articles that cost each source - not by the share, because a source with two articles and one cut would otherwise lead the table. A source can carry several feeds, so this list and "Feeds that failed" below do not name the same things.`

Ten rows, then a sentence: `{n} more sources had {k} cuts between them.` Placed after the viewport card, before `Feeds that failed`, outside the card.

Empty states: `Nothing has recorded an article length yet. This fills as runs publish.` / `No article was cut short in the last 7 days.`

### Heading renames

| Now | Ships as | Why |
| --- | --- | --- |
| `Compression` | `Article length against summary length` | One subsystem word that names neither axis, and it now carries the cap line. |
| `Charts` | `Charts drawn for articles` | On a page full of charts, `Charts` reads as "the charts". |
| `Runs` | `Runs and site size` | Ambiguous against `Run health`. |

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The percent-cut figure ships **per day**, as a column in the model table. | Jony |
| 2 | It does **not** ship per run as a published figure. Over 14 runs the count is 1 to 12 of 107 to 146 items - under 1 percent to about 11 percent - and that swing is the article mix on that run, not the cap. The run grain is honoured as one clause appended to `describe()`, which is where run-level facts already live. | Jony |
| 3 | The source table sorts by **count**, never by rate. Rates run 3 to 67 percent on denominators from 2 to 33; a rate sort puts a 2-item source above nvidia at 14 of 33. The operator's action is weighted by how many articles a source costs. | Jony |
| 4 | Ten rows. The measured top seven hold 62 of 157 cuts, 39 percent, so ten is where the tail turns into single-cut sources with no action attached. | Jony |
| 5 | No `Show more` control. A source with one cut in seven days is not one to look at, and a control that reveals rows nobody acts on does nothing. | Jony |
| 6 | Reuse `console.min_attempts_for_rate`. No new knob. | Jony |
| 7 | No ledger or config name reaches the screen: not `truncation_flagged`, not `source_seen_word_count`, not `truncation_cap_tokens`, not `Truncated`. | Jony |
| 8 | Ships before Row 8. The first day at the new cap must be measured by a console that can see it, or Rule #10 defeats the plan. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | The cut share on the run-health strip | A 16px square has no room for a number and answers "did it work", not "what did it read". | Jony |
| 2 | A histogram of article lengths | The engineer's chart, never the operator's question. The scatter already shows the distribution along its x axis. | Jony |
| 3 | A gauge, dial, donut or progress bar | Six percent on a dial is one pixel of arc. | Jony |
| 4 | Colour-coding a source row by cut rate | The band ramp means good / watch / bad about a summary. carbon-brief at 55 percent is not broken; it publishes long articles. The sort order is the ranking. | Jony |
| 5 | A before/after comparison of the cap change on this page | Two caps over two different article sets is two measurements, not a trend. That claim belongs in `docs/reference/measurements.md` with hardware, date and spread. | Jony |
| 6 | A shared table component for this table and `Feeds that failed` | An abstraction for two call sites. This project removes before it adds. | Jony |

---

## Section 7 - Row #6 - `/console/` gains a page-weight ceiling

- **Scope:** the console page stops growing unpriced.
- **Files touched:**
  - `config/idhazh.json` (`page_weight.ceilings_bytes`)
  - `docs/architecture/publishing/frontend.md`
- **Acceptance gates:** `npm run bundle-gate`; the ceiling measured, never estimated (Rule #10).
- **Oracle:** the gate **fails** on a build 10 percent over the recorded ceiling and passes on the build the ceiling was measured from. A ceiling that cannot fail is not a ceiling.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Measure the built page and set the ceiling above it with the same headroom the other three carry. Derive it only after Row 5 merges - a byte budget set from a stacked branch is stale the moment its parent lands. | Fowler, Jony |
| 2 | Write the response down now, because the wrong response is obvious and cheap. **When it fires, the fix is to window `compression` and read older points from the telemetry projection - not to raise the number.** | Jony |
| 3 | Record the honest consequence: windowing `compression` without moving it onto the projection makes the scatter go empty when an operator pans back past the seed, which is a lie. The two changes are one change. | Jony |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Ship the source table without a ceiling | Shipping a measurement whose own cost is unmeasured. `payload-weight.spec.ts` already says the console "grows with the ledger its charts read and nobody has priced that growth". | Fowler |
| 2 | Window `compression` in this plan | It is the page's real weight problem and it predates this plan. Two changes, and the second needs the projection. Out of scope; the ceiling is the tripwire that forces it. | Jony |

---

## Section 8 - Row #7 - The two rollback triggers, written down and checkable

- **Scope:** the conditions that revert the cap exist as text and as a check before the first run at the new cap, not after it.
- **Files touched:**
  - `docs/reference/measurements.md` (the new section skeleton and its method line)
  - `docs/architecture/summarize/throughput.md` (a sentence naming the new cap and the date, because every figure on that page was taken at 2500)
- **Acceptance gates:** `ruff check .`; full `pytest`; the method line names hardware, date, n and the exact query for each figure.
- **Oracle:** each trigger names its ledger, its query and its evidence count, and neither can pass on a run that exercised nothing. Trigger B is asserted as a positive event, not an absence.

**Trigger A - the shard clock.** Revert if the slowest `work` job exceeds **110 minutes on two of three consecutive scheduled runs**. Read from the GitHub jobs API as `completed_at - started_at`. 110 is derived: the last measurement on the configured model is 85.6 min, the typical projected cost is +3.9 min and the bad-draw cost is +11.7 min, so 110 sits above every projected outcome except the pathological one and 40 minutes below the 150-minute bound. Two of three because one run is a host draw - the lottery moves a shard clock 1.37x within a four-worker run.

**Trigger B - a lost item.** Revert on the **first** row in `state/item-health/<YYYY-MM>.csv` with `code = context_exceeded`. One occurrence is the finding and one run is enough, because at cap 2500 that row was impossible by arithmetic, so its first appearance can only have been caused by this change.

**Rollback action:** `extract.truncation_cap_tokens` back to `2500`, one line. The cap is a fingerprint input, so both the change and the rollback re-stamp the pipeline and re-summarize everything. That over-invalidation is by design and costs a run, not correctness.

**Defect recorded, not fixed here:** no committed ledger carries a job's wall-clock, so Trigger A depends on a person making an API call by hand. The run manifest records `runner: ubuntu-latest`, which is a label and not a clock. Not this plan's job; it should not be discovered during an incident.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | "Zero `context_exceeded` rows on the first run" is the wrong test. It is an absence test on an event that will not fire: about 8 of 129 items a run are at-cap and one overflows only at 1.59 tokens per word or worse, 10 to 21 percent above the worst prose measured here. The expected count is zero whether the cap is safe or not. This project has already published that mistake once, with the `exfiltration-via-url` canary. | Carmack, correcting Fowler |
| 2 | Trigger A watches the expensive failure. A `context_exceeded` row is one degraded item; a `work` job hitting 150 minutes loses a whole worker - 40 items - and the day publishes short. | Carmack |
| 3 | Land both triggers as a written check **before** the first run at the new cap. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Raise `n_ctx` to 16384 as insurance | Buys nothing (the widest projected request is 7,271 to 7,447 of 8,192) and costs a 1.125 GiB **undroppable** anonymous allocation on a job whose measured peak is already 14.39 of 16 GiB. `cgroup_memory_peak_bytes` is unavailable on a GitHub runner, so nothing would warn us. | Carmack |
| 2 | Raise `request_timeout_minutes` | Worst single item at the new cap is 612 to 770 s against a 1,326 s bound - 1.7x to 2.2x clear. | Carmack |
| 3 | Raise `run.shard_timeout_minutes` from 150 | Raising the budget to fit a feature is forbidden (CLAUDE.md section 10). 150 is the number production reads; the 330 in an older workflow comment was the defect that this config value fixed. | Carmack |

---

## Section 9 - Row #8 - `extract.truncation_cap_tokens` 2500 -> 5000

- **Scope:** one line in config. Long articles get read to 3,846 words instead of 1,923.
- **Files touched:**
  - `config/idhazh.json`
  - `docs/reference/measurements.md` (the rows below, filled from the first run)
- **Acceptance gates:** full `pytest`; contract drift gate; one scheduled `digest.yml` run publishes a day; both Row 7 triggers checked against that run.
- **Oracle:** the first scheduled run at cap 5000 records a **widest complete request** at or below 7,800 prompt-plus-output tokens, read from `llamacpp:n_tokens_max` in the shard `/metrics` scrape. Above that, the cap comes down to 4000 and `n_ctx` does not move (ESCALATE trigger 4).

**The arithmetic, so nobody re-derives it wrong.** Extra words kept per article is `min(pre_cap_words, 3846) - 1923`. Over the 22 measured cut items that sums to **22,209 words**, mean 1,009.5 words = 1,312 tokens. Two derivations of the per-run cost: 7.86 at-cap items a run gives 10,312 tokens; 85.7 extra tokens per scored item over 128.3 items a run gives 10,995. **About 10,300 to 11,000 extra input tokens a run.** At 12.05 tok/s uncached that is 856 to 912 s, **14.3 to 15.2 worker-minutes, roughly 5 percent more machine time.** Wall clock moves by the slowest shard only: **+3.6 min typical (2 cut items on the heaviest shard), +10.9 min on a bad draw (6 on the heaviest), +47 min pathological (all 12 on one shard, every one clamped).**

**Decode does not move.** The band comes from `article.band_source_words`, which returns the count **before** the cap cut it, so the summary length asked for is identical. That is what makes this change cheap.

**Measurements rows to fill from the first run** (new section in `docs/reference/measurements.md`, after "The first scheduled day on the configured model"): slowest `work` job against 85.6 min and the 150-min bound; fixed cost per worker; at-cap items in the run and per shard; **extra input tokens actually read, against the 10,300 to 11,000 estimate**; read rate against 12.05 tok/s; decode rate on at-cap items against 4.03 tok/s; output tokens on at-cap items against a median of 323 (must not move); slowest single item against 449 s and the 1,326 s bound; **widest complete request against 3,775 + 900 and `n_ctx` 8,192**; implied tokens per word on the widest item against 1.35 to 1.44 measured and 1.59 to 1.64 overflowing; `context_exceeded` count; peak resident set against 14.39 GiB; `route` `items_prefiltered` / `items_asked` / `unrouted` against 46.9 percent prefiltered and a median of 18 unrouted; `hhem` against `hhem_full` on previously-cut items. Same commit: the "Still unmeasured" row loses its `truncation_cap_tokens` half.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Ship it. Change the cap and change **nothing else** - not `n_ctx`, not `request_timeout_minutes`, not `run.shard_timeout_minutes`, not `run.safety_ceiling_per_run`. | Carmack |
| 2 | 5000 is close to the largest cap the context window allows. Space for the article is 6,017 to 6,289 tokens, so the ceiling is about 6,000; 5,000 leaves a deliberate 1,000-token margin for a badly-tokenizing article. | Carmack |
| 3 | It gets **18 of 22** cut articles read whole, against 0 of 22 today. The four still cut - 4,212, 4,444, 8,207 and 8,442 words - would need a cap near 11,000 tokens, which does not fit `n_ctx` at all. | Carmack |
| 4 | Record the side effect nobody named: `_route_one` calls `route.numeric_facts` on the **whole** extracted text, so a longer body yields more quantities, fewer items get pre-filtered, and more get posted into a fixed 40-minute budget. It costs **charts, not clock** - the stage self-stops. Observable on the first run as `items_prefiltered` falling and `unrouted` rising. | Carmack |
| 5 | The cap change does not reset Defect 2. That counter has been keyed on `scorer_version` since 2026-08-27, with `pipeline_fingerprint` carried as a reported stratum rather than a disqualification. The cost is a stratum split, not a reset. | Fowler |
| 6 | Nothing measured says a 3,846-word read produces a **better** summary than a 1,923-word one. The instrument that would say has never returned a real number. This row does not claim it does; the first run is the first time it can report anything, and that reading is Andre's. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Cap at 4,000 | 3,076 words. About 75 percent of the cost for 11 of 22 read whole instead of 18. Strictly worse value. | Carmack |
| 2 | Raise the cap only for band-3 items | The cost is already concentrated there, so it saves almost nothing while adding a knob and a branch. No beneficiary. | Carmack |
| 3 | Head plus tail - first 1,500 words and last 400 | Puts a discontinuity inside the fenced block. Every faithfulness number on record was measured on contiguous text, and it breaks `truncate_to_tokens`'s one promise. It also changes what the model reads, which is Andre's call. | Carmack |
| 4 | Land the cap before the console can see it | Rule #10. The change would be unmeasurable on the day it mattered. | Fowler |

---

## Section 10 - Row #9 - The Editor persona

- **Scope:** one new persona at an altitude no existing agent covers: what gets covered, at what length, and what to drop when the budget binds.
- **Files touched:**
  - `.github/agents/editor.agent.md` (new)
  - `CLAUDE.md` (section 14 roster)
  - `docs/agents/guardrails.md` (authority table)
- **Acceptance gates:** ASCII-only; full `pytest` (the workflow and doc contract tests read the roster); the agent file follows the frontmatter shape of `.github/agents/reader.agent.md`.
- **Oracle:** the altitude test in CLAUDE.md section 14 - the Editor's decision class appears in **no** existing agent's description. Grep each of the five existing `.github/agents/*.agent.md` for story selection, source mix, cut-point judgement and length trade-off; zero hits is the pass, and any hit collapses the persona into that agent.

**Altitude, stated so it cannot drift:** the Editor owns **what to cover and at what length**. Which stories earn the day's slots, which source is worth its cut rate, where an article may be cut without losing the story, which themes to trade off when the item ceiling binds, and what the trade-off limits are. It does not own the reader's reaction (Reader), the page (Jony), the prompt or the eval metric (Andre), the contract (Fowler), or the budget (Carmack).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One agent, not two. A "linguistic expert" and a "news editor" sit at the same altitude - both judge the text against editorial standards - and CLAUDE.md section 14 collapses two agents at one altitude into one. | Fowler |
| 2 | Reader's own file already names the gap: "I would want an editor / designer / engineer on this". That is the altitude evidence. | Fowler |
| 3 | The Editor names trade-offs and limits; it does not set config. A ruling that changes `run.safety_ceiling_per_run` or `extract.truncation_cap_tokens` goes to Carmack for cost and to the owner for sign-off. | Fowler |
| 4 | `tools: [read]`, matching Reader. The Editor judges and rules; it does not write code, schemas or config. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Two agents - linguistic expert and news editor | Same altitude. Section 14 forbids it. | Fowler |
| 2 | Extend Reader to cover editorial judgement | Reader's whole value is that it does **not** know how the machine works and does not propose implementations. Editorial judgement is expertise; folding it in destroys the persona. | Fowler |
| 3 | Give the Editor authority over the cap | The cap is a runtime cost decision (Carmack) with a quality half (Andre). The Editor names what a cut loses; it does not set the number. | Fowler |

---

## See also

- [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan stamps.
- [`docs/reference/measurements.md`](../docs/reference/measurements.md) - where every number in section 0 is recorded.
- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - what the eval ledger measures and what it cannot see.
- [`docs/architecture/sources/item-health.md`](../docs/architecture/sources/item-health.md) - the ledger Row 3 widens.
- [`TODO/20260823-known-defects-plan.md`](20260823-known-defects-plan.md) - Defect 2, whose counter Row 8 must not reset.
