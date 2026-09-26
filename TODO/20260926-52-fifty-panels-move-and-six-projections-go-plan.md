# Plan 52 - Fifty panels move to the query door and six projections go

**Last Updated**: 2026-09-26
**Status**: **PLACEHOLDER. Not execution-ready and not startable.** It holds the
scope two earlier plans handed forward, so that work has an address instead of a
phrase. Nothing here is a row yet. **A worker must not pick this up.**

## What this file is for

Plans 50 and 51 both stop at a boundary and both call what lies past it "the
route plan". That phrase named no file, so a reader who went looking found
nothing - or worse, found `20260905-02-retire-the-route-name-plan.md`, which is
about something else entirely. This page is that file. Everything those two
plans defer arrives here, and they now link to it by name.

**This is a holding page, not a plan.** It has no Status Reckoner with rows in
it, no acceptance gates and no oracles, because none have been written. Turning
it into a plan is a `prepare-plan` pass over the material below, and that pass
has not happened.

## The intent this plan will serve

**A console panel should ask the question it wants answered, against the data
`state/` already holds, at the moment a reader looks at it.** Today most panels
cannot. A panel reads a file the build wrote in advance - a projection - so the
question it can ask was fixed by whoever wrote the projection, months earlier
and for a different reason. Nine of the redraws and seven of the new panels in the
panel verdicts below exist only because that restriction goes.

The second half of the intent is subtraction. **A projection that outlives its
last reader is a file that can disagree with `state/`**, and one of them already
does: `frontend/public/machine/<YYYY-MM>.csv` joins `host-fingerprint` to
aggregated `item-health` rows, so it carries values neither collection holds
alone and either can move underneath it. Six such directories go, about 4.1 MB
leaves the published site, and each one leaves in the same pull request that
moves its last reader.

## What is already settled, so this plan does not re-argue it

| What | Where it was settled | What that means here |
| --- | --- | --- |
| The chart vocabulary - nine types, and a tenth is an escalation | Plan 51 section 2.6 | A row picks a type from that list. Minting a tenth is an escalation, not a row decision |
| The readout strip - one module, every chart, hover a keyboard can reach | Plan 51 section 2.7 | Every panel this plan moves uses it. No panel ships its own tooltip |
| The ten sufficiency gates, each decidable | Plan 51 section 2.8 | A panel passes them or the row says in one line why not |
| The screenshot gate and the panel capture group | Plan 51 section 2.9 | A moved panel joins the capture group in the row that moves it |
| **Every panel, and what each becomes** | **The panel verdicts below** | Fifty-one panels, each ruled KEEP, REDRAW, REPLACE, DELETE or NEW by Susan on 2026-09-26, with the columns each queries and the chart it becomes. **That table is this plan's contract**, moved here from plan 51 so this plan owns the backlog it executes. Panel 6b is delivered by plan 51's row 8 and is the one entry this plan does not own |
| The query door, and that the browser needs no collection list | Plan 51 section 2.2 | Rows here call the door. They do not extend it |
| Where a collection lives on disk, and how a period is addressed | Plan 50 sections 2 and 5.4 | A row reads through the published collection, never by building a path |

**Plan 51's rows 4 to 7 exist to make this plan cheap, not to be it.** By the
time this plan starts, the vocabulary, the strip, the gates and one worked
panel end to end are all in the tree.

## The shape this plan is expected to take

One row per console route. Each row moves that route's panels to the query
door, and **each row's scope line ends with the projection under
`frontend/public/` it deletes**.

| Route | Projection it deletes | Note |
| --- | --- | --- |
| `/console/machine` | `machine` | Panel 6b is already moved by plan 51 row 8; this row moves the rest of the route |
| the model route | `telemetry` | - |
| the last route out | `day-metrics`, `run-days`, `run-timeline`, `span-rollup` | Four at once, because they share their last readers |

`console/band.json` **stays**. It is the freshness header every route fetches
first, not a projection.

**A route is not done while the projection it fed survives.**

### What it is expected to cost, so nobody discovers it mid-flight

About **seventeen pull requests in total**, of which plan 51's rows 4 to 7 are
four. The redraws batch by the chart type each becomes - about four pull
requests, so one builder is edited once - and the new panels batch by which
`UNREAD_CELLS` group they read, so each batch moves one group of names into
`COLUMN_READERS` as one reviewable diff.

## What this plan inherits and must close

| # | Inherited from | What it is |
| --- | --- | --- |
| 1 | Plan 51 section 0, Hard scope - out | **Three of the five routes draw no panel id today.** The gates and the captures reach 26 panels on two routes until a row here wraps the other three. A row must do that before those routes can be judged |
| 2 | Plan 51, `echarts` | `echarts@^5.6.0` and sixteen importers stay installed while two grammars coexist. **The last row here uninstalls it**, and that deletion is the signal the plan is finished |
| 3 | Plan 50 row titled *The three ledgers the console's routes read become parquet* | `backend/utilities/migrate_to_parquet.py` carries "delete when every `state/item-health`, `state/scores` and `state/host-fingerprint` CSV is gone from `main`". **The first row here names it in its scope line** |
| 4 | Plan 50 row titled *`span-rollup` becomes parquet* | `migrate_span_rollup.py` carries the same shape of condition for `state/span-rollup`. Same treatment |
| 5 | Plan 51, telemetry-intent N7 and N8 | Neither gets its stone until the projections go. This plan is where they are answered |

## Open questions this plan starts from, rather than discovers

Both were found while writing plan 50, verified as out of its scope, and
recorded here so the first row of this plan begins with them already asked.

- **Is `scores` named for what it measures?** It is keyed per item, per run and
  per attempt. If what it scores is the feed rather than the item, the
  collection and its columns are misnamed, and no migration fixes that - a
  rename has to happen before or instead of the move.
- **Does `span-rollup` belong inside `item-health`?** The grains differ: per run
  and per stage against per item, so merging would repeat a span row once per
  item. **Measured 2026-09-25: two collections in one file save 24 bytes against
  two separate files.** There is no size argument for merging any pair of these,
  so if they merge it is a modelling decision and this plan has to make it.

## What must be true before this becomes a plan

1. Plan 50 has merged, so the query door and the four migrated collections exist.
2. Plan 51 rows 4 to 7 have merged, so the vocabulary, the strip, the gates and
   one worked panel exist.
3. A `prepare-plan` pass turns the panel verdicts below into rows, with the
   parallel group, the acceptance gates, the oracles and the decisions each row
   needs. **Until that pass runs, this page is a note and not a plan.**

## The panel verdicts (Susan, 2026-09-26)

This is the contract this plan turns into rows. Verdicts: **KEEP** - question and chart both right. **REDRAW** - right question, wrong chart, because the projection forced it. **REPLACE** - wrong question. **DELETE** - answers nothing an operator needs. **NEW** - should exist and does not. Panel 6b is delivered by plan 51's row 8; every other row is this plan's.

**Two panels want a mark the nine chart types do not host.** Panel 7 (a machine-speed range - fill to a median, notch at the max) and panel 17 (a feed-discount target bar) need a mark none of plan 51 section 2.6's nine types draws. That is plan 51's ESCALATE trigger 5: the row that builds either one first restates it onto an existing type, or escalates a tenth type with its signature and component and gets it ruled - it does not improvise the mark.

**A panel must be addressable before it can be judged.** Three of the five routes draw no `data-console-panel-id` today, so the gates and captures reach only the panels on the two routes that do until a row here wraps the other three (inherited item 1 above).

| # | Panel | Route | Verdict | What it answers after |
| --- | --- | --- | --- | --- |
| 1 | At a glance; Run health; What one more article costs; Where an item's time went; Time per item by stage; Reading the prompt; Writing the summary; Where the run's time went; Visuals drawn; Whether the yield is falling | `/console/` | **KEEP** | unchanged |
| 2 | What is failing, by stage | `/console/` | **REDRAW** | queries `stage`, `outcome`, `code`, `failed_rule`. Stays a stacked date series by stage; selecting a stage opens a ranked list of the rules that refused. One glance: not "summarize is failing" but "one rule refused most of them" |
| 3 | Item telemetry viewport | `/console/` | **REPLACE** | wrong question, and its title is two subsystem words (CLAUDE.md section 0b). Becomes **whether a run is getting slower on the same work**: seconds per article over `source_words`, a date series, with the settings rule across it. **The reader loses** the raw items-per-minute figure; it returns above the run timeline, which counts the whole run |
| 4 | How much of each prompt was already in memory | `/console/` | **DELETE** | the same question is drawn properly on Hardware. **The reader loses** the figure on the route they land on; the band keeps the worst-case number and the title links across |
| 5 | What the extractor found | `/console/` | **REDRAW** | queries `element_class`, `span_integrity`, `source_form`, `elements_found`. Figure cards stay; the table becomes a ranked list of element classes, with `span_integrity` as a second segment. One glance: what kind of fact the extractor gets, and how often the span it cited was intact |
| 6 | Trust the speed numbers; processor taken by another tenant; memory taken back; which machines this run got; the slowest articles getting slower; what is holding the memory; what one article costs; reading against writing; what this would have cost elsewhere | `/console/machine/` | **KEEP** | unchanged |
| 6b | What kinds of machine we keep being given | `/console/machine/` | **REDRAW** | **delivered by plan 51's row 8** and the one panel this plan does not own: five colour stops instead of seven, a new shape under the threshold, a new merge rule, and d3 instead of ECharts |
| 7 | Whether some machines do the same work slower | `/console/machine/` | **REDRAW** | queries `item_total_ms`, `prefill_ms`, `decode_ms` joined to `cpu_model`. Wants one range mark per machine kind - fill at the median seconds an article, notch at the worst - which needs a mark the nine types do not host (see the tenth-type note above). **Its id is `reading-against-writing` and belongs to another panel**, which is how it drifted |
| 8 | Which parts of the last run took longest | `/console/machine/` | **REDRAW** | the projection summed per shard, so it could only rank shards - and an operator acts on an article. Queries `item_id`, `source_id`, `shard`, `item_total_ms`, `fetch_ms`, `extract_ms`, `summarize_ms`, `queue_wait_ms`. Becomes a ranked list of the twenty slowest articles, each a segmented track of its four stages |
| 9 | How close an article came to using up memory | `/console/machine/` | **REDRAW** | same grain defect. Queries `item_id`, `source_id`, `os_mem_available_min_bytes`, `llama_rss_bytes`, `source_words`. A ranked list of the twenty articles that left the machine least, each naming its length. One glance: whether long articles are what fills the machine |
| 10 | How much of the reading limit an article takes | `/console/machine/` | **REDRAW** | a percentile refuses "what does the tail look like". Queries `summary_input_tokens`, `label_input_tokens`, `n_ctx_configured`, `source_words_before_cap`, `truncation_cap_tokens`. Becomes a log-binned distribution with a rule at the reading limit and a second at the truncation cap, both printing their value |
| 11 | How much text the model reads again | `/console/machine/` | **REDRAW** | the server publishes its own answer and we compute a second one. Queries `label_cache_pct` and `summary_cache_pct` - **both unread today**. Becomes a date series of the server's own cache share, label and summary as two lines; the derived figure stays as a printed check beside it |
| 12 | The eleven model cards, the daily table, why a summary was doubted, faithfulness by day, which sources the checker doubts, what one summary cost, how long summaries came out, what the model change moved, how each measure is scored | `/console/model/` | **KEEP** | unchanged |
| 13 | Measured, and nothing acts on it | `/console/model/` | **REPLACE** | "which instruments are unwired" is a backlog, not an operator's question. Each instrument moves to the panel that owns its question and carries a `no threshold agreed` marker in words. **The reader loses** the one place listing unwired instruments; `eval-instruments.ts`'s contract test already fails on a column in no panel, so the list moves off the page into the test that was already keeping it |
| 14 | Stories the day merged; where the merge line sits; whether the judge agrees with itself; what the record still needs; what the judge said about the line; pairs marked apart | `/console/judgement/` | **KEEP** | unchanged. **This route is out of reach for now**: it reads `state/published/` and `state/llm-council/`, neither of which the browser can query. Its panels are KEEP because nothing here can change them |
| 15 | What the model made of each article | `/console/judgement/` | **DELETE** | a heading with no panel under it. **The reader loses** a promise that was never kept. It returns as a row in whichever plan wires `state/content-similarity-judge/` |
| 16 | Sources we may ask and what they yield; sources close to retiring; sources cut short most often | `/console/voices/` | **KEEP** | unchanged |
| 17 | How far the ranking discounts each feed | `/console/voices/` | **REDRAW** | it draws the ranker's input and never what the ranker did. Queries `feed_weight`, `feed_reliability`, `authority_score`, `tier_score`, `selection_score` - **all unread today** - against a count of items that published. Wants the discount as a target bar (see the tenth-type note above), the count as a figure on the same row. One glance: a source we discount heavily that still places |
| 18 | Feeds that failed | `/console/voices/` | **REDRAW** | a feed answering while its articles return 403 is invisible today. Queries `http_status`, `outcome`, `code`, `source_id`. Two tile rows a source on one date axis: feed outcome above, article fetch below. One glance: the source whose feed is green and whose articles are gone |
| 19 | **Why today's articles were chosen** | `/console/` | **NEW** | `partsOfOne`. Queries `selection_score`, `authority_score`, `tier_score`, `feed_weight`, `recency_bonus`, `lens_bonus`, `watchlist_bonus`, `carriage_step`. Twenty rows ranked by score, each a segmented track of what made it, fixed order. One glance: whether one component decides every row - **if `feed_weight` fills every track, the ranker is a whitelist wearing a score**. Nothing on this site says why an article was chosen |
| 20 | **What the watchlist caught** | `/console/` | **NEW** | `tileStrip`. Queries `watchlist_hit`, `watchlist_bonus`, `on_front_page`, `carried_by`. One tile a day, three states, the finding as a sentence above. **If it is always quiet, that is the answer and it should be visible** |
| 21 | **Where a fetch actually spent its time** | `/console/voices/` | **NEW** | `rankedList` with a four-segment track. Queries `fetch_connect_ms`, `fetch_ttfb_ms`, `robots_ms`, `retry_total_ms`, `retry_count`. One glance: which of four reasons a source is slow - a slow server, a flaky one, an uncached robots fetch, or a retry storm. **Three different actions, one number today** |
| 22 | **What the source answered** | `/console/voices/` | **NEW** | `tileStrip`, one tile a day a source, tinted by status class. Queries `http_status`, `source_form`, `tier`, `canonical_url`. One glance: the day a source started returning 403. **The most actionable feed-decay signal in the row, unread** |
| 23 | **How old an article was when we published it** | `/console/` | **NEW** | `distribution`. Queries `published_at`, `time_source`, `item_started_at`. Log-binned hours from publication to our run, a rule at the median, `time_source` splitting where the timestamp was inferred. One glance: whether we publish yesterday's news, and how much of the answer is a guess |
| 24 | **How a model call ended** | `/console/model/` | **NEW** | `dateSeries`, stacked, fixed order, `length` at the bottom. Queries `summary_finish_reason`, `label_finish_reason`, `recovered`. One glance: **a summary that ran out of output budget and that the console reports as a success today** |
| 25 | **Which rule refused a reply** | `/console/model/` | **NEW** | `rankedList` by count, divisor printed. Queries `failed_rule`. Panel 2 says the stage; nothing says the rule |
| 26 | **The settings-change rule** | everywhere | **NEW, not a panel** | a dashed vertical on **every** `dateSeries`, carrying the date and what changed. Reads `model_quantisation`, `n_parallel`, `temperature`, `label_budget_tokens`, `summary_budget_tokens`, `truncation_cap_tokens`, `run_visual_decision` - five of them unread. **These are the confounders under every trend on this console**, which is why plan 51 gate 6 makes it a gate and not a nicety |
| 27 | `failed_field` | - | **REFUSED** | no panel. Empty on every committed row - it has no writer, not just no reader. Drawing it would publish a blank column as a finding. It belongs in a row that gives it a writer or deletes it |

## See also

- [`20260924-50-idhazh-gardener-plan.md`](20260924-50-idhazh-gardener-plan.md) - the collections, the door and the schedule this plan reads through.
- [`20260924-51-console-fetches-and-draws-its-own-data-plan.md`](20260924-51-console-fetches-and-draws-its-own-data-plan.md) - the vocabulary, the strip, the gates and the fifty-one panel verdicts that are this plan's contract.
- [`../docs/concepts/console-design.md`](../docs/concepts/console-design.md) - what the console is for.
- [`../docs/concepts/telemetry-intent.md`](../docs/concepts/telemetry-intent.md) - N7 and N8, which this plan answers.
