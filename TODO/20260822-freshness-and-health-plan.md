# Freshness, identity and health - execution plan

**Last Updated**: 2026-08-22

Seventeen approved items. This doc records the rulings the five persona advisors
returned on 2026-08-22, the four places they contradicted each other or the
earlier decisions, and the order the work lands in.

Non-authoritative working material (CLAUDE.md section 3). Every decision here is
copied into the living doc it impacts as the item that carries it lands.

## The four conflicts and how they were settled

### 1. Removing the daily cap (item 9)

**Reader dissents.** Their case: 146 feeds will produce ~60 fresh items a day, of
which maybe 12 matter. AI holds 32% of the feeds, so with no per-vertical ceiling
AI eats the page. The cap is the only rule in the set that says "we chose"; take
it away and the ranking score does no work, because nothing is ever cut. They
name this the change most likely to make the digest worse, and they are right
that it is the only one that cannot be patched later.

**Ruling: implement the user's decision, with the dissent recorded.** The user
ruled the cap is replaced by a safety ceiling and supply sets the size. That is
what lands. The ceiling is `run.max_items_per_run` (default 40, from Carmack's
timeout arithmetic) and the per-vertical `daily_cap` becomes `max_per_run` at a
generous default. Both are config knobs, so if Reader's prediction comes true the
correction is one number in `config/taxonomy.json`, not a code change.

Reader's evidence that this is real, not theoretical: the 2026-08-21 page
published 4 items, all AI, and the words Energy, India, World and Business do not
appear on it.

### 2. "Repeats within one day are acceptable" (items 4, 6)

**Reader proves this is a duplicate on one screen, not a repeat across runs.**
`build_day` dedupes on `item_id`, which is the article's rank position. When run 2
ranks a story one place lower, the id changes, the dedupe misses, and the same
story lands on the page twice. Already visible across days: the Google Research
biomarker article is `ai-03` on 21 Aug and `ai-04` on 22 Aug; the NVIDIA
clustering article is `ai-04` then `ai-05`. Same URL, two entries, and the two
runs disagreed about the confidence band - `medium` then `high` for one,
`low` then `high` for the other.

**Ruling: one URL, one entry, ever.** The ruling "a repeat within one day is
acceptable" is read as Fowler read it: we do not need suppression machinery, not
we should print it twice. `build_day` dedupes on `url_key`. `stage_plan` drops
URLs already published. This is what item 4's never-republish asked for anyway;
the only change is that it now also holds within a day.

### 3. Where the seen-URL store lives (item 3)

Fowler wants `state/seen.json`, a whole-file document pruned to 48 hours, with
"did we publish this" answered by reading the committed digests. Carmack wants
`evals/seen/YYYY-MM.csv`, append-only, 90-day window, because reading N days of
digests is an O(days) scan on a job that finishes in under a minute, and because
a file rewritten 4x a day costs 1-3 GB of pack growth a year against ~30 MB for
an append-only one.

**Ruling: Fowler's home, Carmack's format.** `state/seen/YYYY-MM.csv`,
append-only, month-partitioned, retention `collect.seen_retention_days` (90).
One row per event, `event` in `{seen, published}`, folded at read time. It answers
both questions from one file, the current month is the only file that grows, and
older months are immutable blobs git stores once.

`state/` is a new top-level directory: machine-written, must survive a fresh
checkout, never reaches a reader. `frontend/public/` is site input, `evals/` is
read by a published page, `backend/var/` is gitignored, `config/` is
human-edited. Verified against `.github/workflows/pages.yml`: only
`frontend/build` is uploaded, so `state/` cannot count against the 1 GB cap.

### 4. The output token cap (item 14)

Andre sizes it to the longest band's ask (700). Carmack sizes it to the largest
reply the schema permits (1024 at the old bounds). Item 14 says it is a crash
guard and must be labelled as one, so it is sized to the schema, not to the ask.

**Ruling: 1300**, recomputed against the new bounds - a 2800-char summary plus
five key points at 140 chars plus structure and escaping is ~3725 characters, and
3.0 characters per token is the pessimistic end of the observed range. Context
check: 2500 (truncation cap) + 1300 + ~1120 (new prompt overhead) = 4920 against
an 8192 window.

## Rulings adopted without conflict

| Area | Ruling | From |
| --- | --- | --- |
| Item ids | Per-vertical high-water mark. `PlannedVertical.first_ordinal` carries the start; the ordinal validator is parameterized, not weakened. | Fowler |
| Item 1 | Two commits: make `stage_plan` testable by injecting the fetcher and `now`, then the tests. Structural and behavioural never share a commit. | Fowler |
| Retired feeds | New `retired` key, a validator that rejects a retired entry in `feeds`, and a before-validator migration that moves an older payload. | Fowler |
| Dead settings | `SalienceFeedDef.weight` dies. `CollectConfig.quarantine_after_failures` LIVES - item 11 wires it. `CollectConfig.min_feeds_floor` dies instead: dead, and contradicted by `docs/architecture/sources/discovery.md`. | Fowler |
| Feed health | `state/feed-health/YYYY-MM.csv`, outcome as a closed vocabulary `ok / empty / unreachable / unparseable`. `empty` is the state HTTP cannot see and the one that killed 8 feeds. | Fowler, Carmack |
| Schedule | `cron: '17 1,7,13,19 * * *'` - six-hourly, off the hour, off every 6-multiple hour, and the 01:17 run is published before 06:00 UTC. `work` timeout 330 -> 120. `work` gated on a non-empty plan. | Carmack |
| Prompt determinism | `prompt_fingerprint_text()` digests the template plus every band's rendered policy line, so the per-run stamp covers the closed set rather than the one render an item got. | Andre |
| Quotations | A typed `Quote` field, never inside the prose. Verbatim substring of the sanitized text, attribution grounded in the text, one per item, 25 words. Excluded from every copy metric and from the faithfulness hypothesis. | Andre |
| Dashboard | A section of `/console`, placed first, replacing the Runs table's three health columns. Columns are dates, rows are run ordinals, squares are `RunStatus`. New colour tokens - the band ramp means "faithfulness", not "a job finished". | Jony |
| Dashboard window | `min(config_window, days_since_first_run + 1)`, floored at 14. Two days of data must not render as 54 days of outage. | Jony |
| Read mark | One key, `{"d": "<page date>", "ids": [...]}`. Wipe when `d` is not the page's date. `idhazh:hide-read` is a preference and does not wipe. | Jony |

## Defects found during consultation, in scope

- `loadManifests()` walks `publishedDates()`, so a day with a `run.json` and no
  `digest.json` is invisible - exactly the day the health grid exists to show.
- `RunStatus.FAILED` is never written by anything, so the red square is
  undrawable. The workflow must record a failed run.
- No hash handling anywhere in `frontend/src/`, so `#world-03` on an item past
  the 12-item page boundary scrolls nowhere. Lands with item 6.
- `_ROBOTS_CACHE` is a module global that no test can reset.
- `fits_context` is defined and called only from a test.

## Defects found during consultation, out of scope

Recorded here, not fixed by this change set:

- `to_eval_row` calls `band()` and never `counterweight_band()`, so lead coverage
  is computed and ignored. `ai-03` published as `high` confidence with coverage
  0.00.
- The faithfulness thresholds are saturated: all 10 committed items band `high`,
  observed range 0.923-0.978 against a 0.80 floor. A classifier with one class is
  not classifying.
- `/evals` and `/console` both render per-day band counts from the same ledger.
- `EmptyDay` points at a run notice that is not on the page.
- The home page renders the latest day, not today, with nothing saying today has
  not run.

## Order

Item 1 first; nothing else lands before the plan stage has a test. Item 6 before
item 7, because today a second same-day run publishes zero items and four runs a
day would make that three wasted runs instead of one.

| Phase | Items | Why together |
| --- | --- | --- |
| A | 1 | The safety net. Two commits: refactor, then tests. |
| B | 2, 16 | One config shape, one changelog entry, one migration. |
| C | 3, 4, 5 | The store, then the rules that read it. |
| D | 6, 9 | Identity, then what counts against a ceiling. |
| E | 7 | Cadence, only once a second run can publish. |
| F | 8 | Independent, and provably inert today - every feed is weight 1.0. |
| G | 10, 11 | Record, then read the record. Item 11 lands dark until the ledger has history. |
| H | 12, 15 | Surfaces, once there is something to show. |
| I | 13, 14 | The model boundary, alone. |
| J | 17 | The rationale sections land with their items; this is the sweep that proves none was missed. |

## See also

- [`docs/concepts/pipeline-loop.md`](../docs/concepts/pipeline-loop.md)
- [`docs/architecture/sources/discovery.md`](../docs/architecture/sources/discovery.md)
- [`docs/reference/measurements.md`](../docs/reference/measurements.md)
