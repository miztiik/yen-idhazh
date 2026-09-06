# Constant-Cost Reads: Ranks 1 And 10

**Last Updated**: 2026-09-06
**Level**: 5 (a new persisted contract, a published-payload change, and reader-facing removals)

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 4; honor the ESCALATE triggers in section 0.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Every finding in ranks 1 and 10 of [the growth audit](../docs/reference/data-growth-audit.md) - 43 in all - so that an ordinary build, page load or click stops re-reading history it does not need. |
| Hard scope - in | Audit findings 11, 12, 61-75, 84-89, 93-113 as listed in section 1. Config knobs those rows need. The month-partition pattern and its doc. The day-facts contract. The archive window control. |
| Hard scope - out | Any other audit finding. Model or summary quality. Retrieval accuracy. Deleting telemetry shards. Changing the article ID format. Virtualizing the story list. |
| ESCALATE triggers | (a) Row 21 before the day-facts schema is written. (b) Row 17 before any all-history chart is narrowed to a window. (c) Row 26 - the day payload contract - authored only, never implemented. (d) Any row that would delete a committed state or telemetry file. (e) Any row that cannot hold its Oracle without weakening an existing trust or sanitization control. |
| Chosen strategy | Bound the input first, then delete the repeated reduction. Store facts at publication; read them at build. Ruled by Fowler (contracts before logic) and Carmack (measure the visit count, not the clock). |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

Growth claims cited per row come from [the research handover](20260906-data-growth-research.md), which pins them to `76c2d27cbfb7ba9d868e0747dea366b2223e408f`. A worker re-reads the current file before editing; the audit is evidence, not a description of today's `main`.

## 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Config knobs and contract | - | A | PENDING | - | - | - |
| 2 | One-pass build reductions | 1 | B | PENDING | - | - | - |
| 3 | Pointer readout and dead readout work | 1 | B | PENDING | - | - | - |
| 4 | Read marks on a calendar window | 1 | B | PENDING | - | - | - |
| 5 | Day list order, filter and reveal | 1 | B | PENDING | - | - | - |
| 6 | Day request ownership | 1 | B | PENDING | - | - | - |
| 7 | One observer for waiting visuals | 1 | B | PENDING | - | - | - |
| 8 | Offline cache discipline | 1 | B | PENDING | - | - | - |
| 9 | Chart lifetime and style updates | 1 | B | PENDING | - | - | - |
| 10 | Month-partition pattern and doc | 1 | B | PENDING | - | - | - |
| 11 | Failure panels and failure list | 2 | C | PENDING | - | - | - |
| 12 | Band distance, stage timings, run family | 2 | C | PENDING | - | - | - |
| 13 | Glance and ranked builders | 2 | C | PENDING | - | - | - |
| 14 | Chart geometry and coverage | 3 | C | PENDING | - | - | - |
| 15 | Model route instruments | 2 | C | PENDING | - | - | - |
| 16 | Hardware route context | 2 | C | PENDING | - | - | - |
| 17 | Console route strips and row eviction | 2 | C | PENDING | - | - | - |
| 18 | Throughput trend window | 2 | C | PENDING | - | - | - |
| 19 | Telemetry publication by partition | 10 | D | PENDING | - | - | - |
| 20 | Source health by recorded date | 10 | D | PENDING | - | - | - |
| 21 | Day-facts contract | 10 | D | PENDING | - | - | - |
| 22 | Producer writes day facts | 21 | E | PENDING | - | - | - |
| 23 | Console reads day facts | 22 | F | PENDING | - | - | - |
| 24 | Band facts | 22 | F | PENDING | - | - | - |
| 25 | Archive window control | 1 | C | PENDING | - | - | - |
| 26 | Day payload contract - author only | 21 | F | PENDING | - | - | - |
| 27 | Living docs sweep | 23, 24 | G | PENDING | - | - | - |

Coverage: rows 2-26 carry all 43 findings exactly once. Rows 1, 10 and 27 carry no finding; they carry the knobs, the pattern and the docs the others need.

## 2 - Row #1 - Config knobs and contract

- **Scope:** Every tunable this plan needs, in one commit, so no later row edits the config contract.
- **Files touched:**
  - `config/appearance.json`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `schemas/appearance-config.schema.json`
  - `frontend/src/lib/server/config.ts`
  - `backend/tests/test_contracts.py`
- **Acceptance gates:** local - the shared test selector, plus the contract drift gate so schemas and frontend types regenerate byte-identical. CI - full suite.
- **Oracle:** the drift gate. Regenerated schema and generated frontend types must match the committed bytes exactly, and every existing config file must still validate against the new model.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `read_mark_days` moves from 7 to 14 in both config files, and its meaning changes from "the newest N dates holding marks" to "N calendar days back from today". | Owner, 2026-09-06 |
  | 2 | `archive_recent_days` moves from 7 to 14 so its stated pairing with `read_mark_days` stays true. | Owner, 2026-09-06 |
  | 3 | `window_presets` becomes `[1, 7, 14, 30, 90]`; `min_window_days` drops from 7 to 1 so the new preset satisfies the existing range validator. | Owner, 2026-09-06 |
  | 4 | `max_window_days` stays 366. It bounds nothing a reader can reach - the preset radio buttons are the only span control - and lowering it only permits deleting month shards sooner, which this plan does not want. | Owner, 2026-09-06 |
  | 5 | A new byte ceiling bounds the offline day cache. `offline_days_kept` stays 14; a day count is not a byte bound. | Row 8 need; Carmack |
  | 6 | A new archive window knob reuses the console preset list rather than declaring a second one. | Fowler |
  | 7 | The `version` date-stamp and a `changelog` entry land in the same commit, per CLAUDE.md section 11. | CLAUDE.md |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Lower `max_window_days` to 90 or 180. | It is a retention floor, not a viewport clamp. Lowering it authorises shard deletion, and the audit shows no UI path past 90 days today. | Owner, 2026-09-06 |
  | 2 | Add 180 to the presets. | A wider preset pulls more month files, which works against the goal of this plan. | Owner, 2026-09-06 |
  | 3 | Let each row edit the contract it needs. | Six rows would contend for one file. | execute-a-plan.md |

## 3 - Row #2 - One-pass build reductions

- **Scope:** Replace bucket-copy grouping, the run-to-health join, per-article band sorting, per-bin rescans and repeated config parsing with single passes producing identical output. Findings 64, 65, 66, 69, 71, 95.
- **Files touched:**
  - `frontend/src/lib/server/config.ts`
  - `frontend/src/lib/server/model-work.ts`
  - `frontend/src/lib/server/runtime-counters.ts`
  - `frontend/src/lib/charts/series.ts`
  - the matching specs under `frontend/tests/`
- **Acceptance gates:** local - the shared test selector plus the console specs, run against a canary day built first. CI - full suite.
- **Oracle:** counted-visit parity. A test doubles both runs and health rows and asserts the output is byte-identical to the current implementation while the counted visits grow linearly, not quadratically. The audit records the present figures: 4 runs over 16 health rows cost 64 checks, 8 over 32 cost 256, 16 over 64 cost 1,024.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Output must be byte-identical. This row changes no number on any page. | Fowler |
  | 2 | Exact percentile interpolation over values is preserved; a histogram alone cannot recover it. | Andre |
  | 3 | The conflicting-scrape refusal in the run-to-health join is preserved. | Carmack |

## 4 - Row #3 - Pointer readout and dead readout work

- **Scope:** Pick the column under the pointer by coordinate arithmetic where the axis is affine and by ordered binary search otherwise; delete readout strings and hidden branches with no reader. Findings 103, 113.
- **Files touched:**
  - `frontend/src/lib/charts/frame.ts`
  - `frontend/tests/` chart readout specs
- **Acceptance gates:** local - the shared test selector plus the chart readout specs. CI - full suite.
- **Oracle:** selection parity over a generated column set that includes duplicate positions and exact ties. Every pointer position must select the same column the linear scan selects, first-on-tie.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Duplicate positions and first-on-tie behaviour are preserved exactly. | Fowler |
  | 2 | Only internal output proven to have no reader is deleted. A public payload field merely unused by this bundle is not touched. | Fowler |
  | 3 | Element geometry reads and selected text output stay; they are separate costs and not this row's target. | Carmack |

## 5 - Row #4 - Read marks on a calendar window

- **Scope:** Prune stored read marks to the configured calendar window and write only the affected day. Finding 88.
- **Files touched:**
  - `frontend/src/lib/readstate.ts`
  - `frontend/src/lib/components/DigestList.svelte` (call site only)
  - `frontend/tests/` read-state specs
- **Acceptance gates:** local - the shared test selector plus the read-state specs. CI - full suite.
- **Oracle:** a click's write cost is independent of unrelated days. A test seeds marks across many dates, marks one story, and asserts the bytes written cover that day alone and that every date outside the window is gone.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Calendar expiry trusts the device clock. The present rule avoids that deliberately; the owner accepts the trade for a predictable window. | Owner, 2026-09-06 |
  | 2 | The per-day forget button keeps its exact behaviour. | Reader |
  | 3 | Read state still may change only how an item looks, never where it sits, whether it appears, or how it ranks. | readstate.ts contract |
  | 4 | A clock that reads earlier than a stored date drops nothing; the window only removes dates older than its floor. | Fowler |

## 6 - Row #5 - Day list order, filter and reveal

- **Scope:** Lowercase searchable fields once per day, hold story positions in a map, and build only the visible prefix plus outlying leads. Findings 85, 86.
- **Files touched:**
  - `frontend/src/lib/components/DigestList.svelte`
  - `frontend/tests/` digest list specs
- **Acceptance gates:** local - the shared test selector plus the digest list specs and one browser smoke per CLAUDE.md section 12. CI - full suite.
- **Oracle:** result parity. For a generated day, every filter string and every hide-read state must produce the identical ordered story list, and a deep link must resolve to the same story.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Substring matching stays exact and stays linear in the day's text. This row removes repeated lowercasing, not the search. | Andre |
  | 2 | The rendered prefix is not virtualized. | Owner, 2026-09-06 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | An inverted token index for the filter. | Not equivalent to substring search; a gram index still needs candidate verification and worst-case linear work. | Andre |
  | 2 | Virtualize the story list. | Breaks find-in-page, selection, printing, focus and speech. A product trade, not an optimization. | Jony, Reader |

## 7 - Row #6 - Day request ownership

- **Scope:** Stop caching failures, key held days by content revision, bound the held set, and share one lookup index per day revision. Findings 87, 93.
- **Files touched:**
  - `frontend/src/lib/assist/day.ts`
  - `frontend/tests/` day loading specs
- **Acceptance gates:** local - the shared test selector plus the day loading specs. CI - full suite.
- **Oracle:** a failed fetch followed by a successful one returns the day. Today the failure resolves to a cached null that is reused for the life of the session.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A rejected or empty result is removed from the held set so a retry can succeed. This is a defect fix, not tuning. | Fowler |
  | 2 | Keys carry the payload's content revision, so a republished day is not served stale. | Fowler |
  | 3 | Single-flight sharing of an in-progress request is kept. Only the unbounded lifetime is removed. | Carmack |
  | 4 | Missing-day and missing-item fallbacks are preserved. | Reader |

## 8 - Row #7 - One observer for waiting visuals

- **Scope:** Share a single intersection observer across waiting visuals and detach obsolete requests on unmount. Finding 110.
- **Files touched:**
  - `frontend/src/lib/components/ItemVisual.svelte`
  - `frontend/tests/` visual reveal specs
- **Acceptance gates:** local - the shared test selector plus the visual specs and one browser smoke. CI - full suite.
- **Oracle:** observer count stays flat as revealed stories grow, and every visual still draws when it reaches the viewport.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Drawing safety scans are not removed. Deleting them is not a lossless optimization. | Andre |
  | 2 | Spoken content is not removed. | Reader |

## 9 - Row #8 - Offline cache discipline

- **Scope:** Add a byte ceiling to the cached-day set and stop the shell cache absorbing arbitrary same-origin responses. Finding 111.
- **Files touched:**
  - `frontend/src/service-worker.ts`
  - `frontend/src/lib/offline.ts`
  - `frontend/scripts/build-worker-switch.mjs`
  - `frontend/tests/` service worker specs
- **Acceptance gates:** local - the shared test selector plus the service worker specs. CI - full suite.
- **Oracle:** held bytes stay under the ceiling across a sequence of large and small days, and every asset a retained day needs is still present after eviction.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `offline_days_kept` stays 14. The audit records a day payload of 8,231 to 1,373,593 bytes, median 727,622, measured 2026-09-02 - so a day count cannot bound bytes. | Owner, 2026-09-06 |
  | 2 | Shell assets and reading data stay in separate caches with separate rules. | Fowler |
  | 3 | Eviction reduces offline reach; a retained day never loses the assets it needs. | Reader |
  | 4 | Days survive a deploy. A reader's data is not spent re-fetching what they had. | existing offline design |

## 10 - Row #9 - Chart lifetime and style updates

- **Scope:** Give each chart an explicit lifetime, avoid work for charts that are offscreen or obsolete, and update style without copying data. Finding 106.
- **Files touched:**
  - `frontend/src/lib/charts/engine.ts`
  - `frontend/tests/` chart engine specs
- **Acceptance gates:** local - the shared test selector plus the chart specs and one browser smoke. CI - full suite.
- **Oracle:** a marks-based test. After a theme change and a resize, the drawn marks match the expected set, and destroyed charts leave no live instance.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Server rendering behaviour is preserved. | Fowler |
  | 2 | The chart library's own repaint is not claimed to be constant. This row bounds what we hand it, not what it does. | Carmack |

## 11 - Row #10 - Month-partition pattern and doc

- **Scope:** Name the existing month-partition layout as the project's pattern, add the freeze rule, and give it one concept doc every later row cites.
- **Files touched:**
  - `docs/concepts/month-partitions.md` (new)
  - `docs/architecture/` the state and telemetry living docs
  - `docs/reference/documentation-structure.md` cross-link if routing needs it
- **Acceptance gates:** documentation only - no application suite. The shared test selector must select nothing but the whitespace check.
- **Oracle:** the doc names, for each existing partitioned collection, its path pattern, its writer, and what makes a partition closed. A collection that cannot state its closed rule is listed as not yet partitioned rather than described loosely.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The layout is already `<YYYY-MM>` and is confirmed present in `state/scores/`, `state/item-health/`, `state/feed-health/`, `state/seen/` and `frontend/public/assist/index/`. This row adds the rule, not the layout. | Owner, 2026-09-06 |
  | 2 | The rule: a closed month is rewritten only when a correction targets it. Every other run touches the current partition alone. | Owner, 2026-09-06 |
  | 3 | Correction, deletion and late arrival are named in the doc. A pattern that only handles appends is a trap. | Fowler |
  | 4 | The doc is a concept doc - one term, defined once - per the documentation routing reference. | documentation-structure.md |

## 12 - Row #11 - Failure panels and failure list

- **Scope:** One pass for codes and stacks; bounded ranked lists and drilldown. Findings 96, 97.
- **Files touched:**
  - `frontend/src/lib/components/FailurePanels.svelte`
  - `frontend/src/lib/components/FailureList.svelte`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the console specs against a canary day. CI - full suite.
- **Oracle:** identical panels, identical ranked order and identical drilldown rows before and after.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Thin-sample behaviour is unchanged: a rate on too few attempts stays outlined. | Andre |
  | 2 | Distinct counts and top lists are not obtained by adding daily distinct counts. | Andre |

## 13 - Row #12 - Band distance, stage timings, run family

- **Scope:** Remove repeated recomputation in the summary-band, stage-timing, run-length, source-range, swap and histogram components. Findings 98, 99, 101.
- **Files touched:**
  - `frontend/src/lib/components/BandDistance.svelte`
  - `frontend/src/lib/components/StageTimings.svelte`
  - `frontend/src/lib/components/RunLengths.svelte` and its sibling range, swap and histogram components
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the console specs against a canary day. CI - full suite.
- **Oracle:** drawn-mark parity per component across a window change and a resize.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Paired lengths from the winning observation are preserved. | Andre |
  | 2 | Timing paths stay proportional to marks and never bridge a missing measurement. | Carmack |
  | 3 | A per-source cap does not bound the number of distinct cap marks; that output keeps its own bound. | Fowler |

## 14 - Row #13 - Glance and ranked builders

- **Scope:** Derive glance plots and ranked, stacked and sparkline options without full sorts before a cap and without repeated normalization. Findings 102, 105.
- **Files touched:**
  - `frontend/src/lib/charts/glance.ts`
  - `frontend/src/lib/charts/rank.ts`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the console specs against a canary day. CI - full suite.
- **Oracle:** the capped list is identical to the list produced by sorting everything and slicing, including ties.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Null denominators and non-monotonic counts keep their present meaning. | Andre |
  | 2 | A tiny fixed input is left alone; indexing it costs more than it saves. | Carmack |

## 15 - Row #14 - Chart geometry and coverage

- **Scope:** Index dates, prepare extents once, advance months directly, and separate data changes from resize geometry. Finding 104.
- **Files touched:**
  - `frontend/src/lib/charts/frame.ts`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the chart specs. CI - full suite.
- **Oracle:** axis, tick and gap output identical across a data change, a window change and a resize.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Gap semantics and output-sized mark placement are preserved. | Jony |
  | 2 | Fixed-density tick fitting is not described as growing with history; the tick count is configured and small. | Carmack |

## 16 - Row #15 - Model route instruments

- **Scope:** Compute one selected-view result and reuse it across cards, swaps, reasons and notes. Finding 107.
- **Files touched:**
  - `frontend/src/routes/console/model/+page.svelte`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the console specs against a canary day and one browser smoke. CI - full suite.
- **Oracle:** every card, marker and explanatory reading identical across each preset.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Whether a measure describes a middle day or a middle summary is preserved and stated where it is displayed. | Andre |

## 17 - Row #16 - Hardware route context

- **Scope:** Reuse prepared run context and latency curves across preset and resize changes. Finding 108.
- **Files touched:**
  - `frontend/src/routes/console/machine/+page.svelte`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the console specs against a canary day. CI - full suite.
- **Oracle:** identical run context and curve output per preset.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A display cap on runs is not a bound on the run population the page prepares; the preparation gets its own bound. | Carmack |

## 18 - Row #17 - Console route strips and row eviction

- **Scope:** Reuse revision-owned maps for the run and feed strips; mark a month loaded only on success; bound the held telemetry rows. Findings 94, 109.
- **Files touched:**
  - `frontend/src/routes/console/+page.svelte`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the console specs against a canary day and one browser smoke. CI - full suite.
- **Oracle:** a failed month load leaves the month unloaded, so a later attempt fills it. Today the month is marked before the fetch and the gap never heals.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Held months are bounded by the count of months the widest window can touch, so one ceiling governs memory, fetches and the retention floor together. | Carmack |
  | 2 | A shard replaces its own owned rows, so a corrected-away row can be retracted. Today the merge can only add. | Fowler |
  | 3 | Legitimate duplicate observation identities are preserved. | Andre |

## 19 - Row #18 - Throughput trend window

- **Scope:** Decide and implement the span the throughput view covers. Finding 100.
- **Files touched:**
  - `frontend/src/lib/components/ThroughputTrend.svelte`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the console specs against a canary day. CI - full suite.
- **Oracle:** the rendered span equals the stated span, and a calendar gap draws as a gap rather than a bridge.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | This row changes what the chart claims, so it is an ESCALATE stop. The worker proposes the span and pauses. | Owner |
  | 2 | If it stays all-history, it reads stored day facts rather than every published day. | Fowler |

## 20 - Row #19 - Telemetry publication by partition

- **Scope:** Publish only changed month partitions; freeze closed ones. Finding 11.
- **Files touched:**
  - `backend/idhazh/publish_telemetry.py`
  - `backend/tests/` the matching specs
- **Acceptance gates:** local - the backend suite for the touched module. CI - full suite.
- **Oracle:** a re-run with no new data writes no partition file. A run adding one day rewrites that day's partition and no other. Byte comparison, not a timing.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The freeze rule and its vocabulary come from row 10; this row does not invent a second one. | Fowler |
  | 2 | A correction targeting a closed month rewrites that month, and the test covers it. | Fowler |
  | 3 | A changed partition still costs its full output bytes. The saving is the partitions not touched. | Carmack |

## 21 - Row #20 - Source health by recorded date

- **Scope:** Select the required complete recorded dates first, then read only those. Finding 12.
- **Files touched:**
  - `backend/idhazh/publish_source_health.py`
  - `backend/tests/` the matching specs
- **Acceptance gates:** local - the backend suite for the touched module. CI - full suite.
- **Oracle:** identical published source-health output, with the rows read bounded by the dates selected rather than the history present.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Gaps, completeness and per-address counts are preserved. | Editor |
  | 2 | Calendar subtraction is not an equivalent query for "complete recorded dates". | Fowler |

## 22 - Row #21 - Day-facts contract

- **Scope:** The persisted shape a run writes once per published day and every console reducer later reads. No producer and no reader changes in this row.
- **Files touched:**
  - `backend/idhazh/contracts/` a new model
  - `schemas/` its generated schema
  - `backend/tests/test_contracts.py`
- **Acceptance gates:** local - the contract drift gate and the shared test selector. CI - full suite.
- **Oracle:** the drift gate, plus a round-trip test proving a written record validates and reads back identically.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One record per published day, rewritten when that day is corrected. No running totals, because a total needs a decrement path for every correction and that is the part that fails quietly. | Owner, 2026-09-06 |
  | 2 | Sums and counts are stored directly. Medians, distinct counts and top lists cannot be added across days and each names how it is answered. | Andre |
  | 3 | Reader before writer: this contract lands before any producer writes it and before any reducer reads it. | Fowler |
  | 4 | The record carries the publication revision it describes, so a stale record is detectable. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Maintained running counters. | Corrections and deletions need a decrement path; a missed one is silent and permanent. | Owner, 2026-09-06 |
  | 2 | One monolithic facts file. | It reintroduces a file that grows without bound and must be rewritten whole. | Carmack |

## 23 - Row #22 - Producer writes day facts

- **Scope:** The pipeline writes the day-facts record at publication. Findings 61, 62, 63, 67, 68, 70, 73, 74, 75 are answered by what this record carries.
- **Files touched:**
  - `backend/idhazh/` the publication path
  - `backend/tests/` the matching specs
- **Acceptance gates:** local - the backend suite for the touched modules. CI - full suite.
- **Oracle:** for the canary day, every figure in the record equals the figure the present reducers compute from raw history. Equality is the whole point of the row.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The record is written by the publication step alone. One writer. | Fowler |
  | 2 | A day republished for a correction rewrites its record in the same step. | Fowler |
  | 3 | The record never carries article text; it carries counts and facts about a day. | CLAUDE.md section 0a |

## 24 - Row #23 - Console reads day facts

- **Scope:** Point the console reducers at the stored records and delete the raw-history readers they replace.
- **Files touched:**
  - `frontend/src/lib/server/payload.ts`
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/src/routes/console/model/+page.server.ts`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the console specs against a canary day and a browser smoke on all three console routes. CI - full suite.
- **Oracle:** every console figure identical to the pre-change build, and the count of day files opened bounded by the window rather than by the archive.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A raw-history reader is deleted only once its replacement produces the identical figure. | Fowler |
  | 2 | Private state files are never served to a reader for drilldown. | CLAUDE.md Rule #1 |
  | 3 | Dropping vectors after parsing saves nothing; the read and the parse already happened. | Carmack |

## 25 - Row #24 - Band facts

- **Scope:** Store the three standing-band facts at publication and have the shared console layout read them. Finding 72.
- **Files touched:**
  - `frontend/src/lib/server/console-shell.ts`
  - `frontend/src/routes/console/+layout.server.ts`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the console specs against a canary day and a browser smoke on all three console routes. CI - full suite.
- **Oracle:** the band renders identically on all three routes and does not change when any route's window control moves.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The band stays all-time. It stops computing all-time. No guardrail exception is needed. | Owner, 2026-09-06 |
  | 2 | The stated reason for it being unwindowed is preserved verbatim in the code: a figure that moved when one route's control moved would read as three different sites. | existing design |
  | 3 | The duplicated publication-count call in that function is removed. | Carmack |

## 26 - Row #25 - Archive window control

- **Scope:** Give the archive a window control over the existing preset list and fetch only the month files the window spans. Finding 89.
- **Files touched:**
  - `frontend/src/routes/archive/+page.svelte`
  - `frontend/src/routes/archive/+page.server.ts`
  - `frontend/src/lib/assist/month.ts`
  - the matching specs
- **Acceptance gates:** local - the shared test selector plus the archive specs and a browser smoke. CI - full suite.
- **Oracle:** a topic with no stories in the window returns an empty list after fetching only the months the window spans. Today the loop walks back through the archive until it fills a page.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The index is already month-partitioned - `frontend/public/assist/index/<YYYY-MM>.json` with a sibling vector file - so a window maps to a bounded set of files with no reshard. | Owner, 2026-09-06 |
  | 2 | A window may span months. The control reuses the console preset list rather than declaring its own. | Owner, 2026-09-06 |
  | 3 | An empty result inside the window is stated plainly, with the window named, and offers a wider one. | Susan, Reader |
  | 4 | Exhaustive scoring over the fetched entries stays the correctness oracle for search. This row bounds the input, not the ranking. | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Reshard the vector files by date range. | Unnecessary. Fetching the month and filtering to the window costs one loop and no rebuild. | Carmack |
  | 2 | Build a per-topic index. | A window already bounds the sparse-topic walk. A second index is a new persisted shape earning little. | Fowler |

## 27 - Row #26 - Day payload contract - author only

- **Scope:** Author the decision record for bounding what a reading page downloads. Finding 84. No implementation.
- **Files touched:**
  - this plan-doc, amended in place with the ruling
- **Acceptance gates:** documentation only.
- **Oracle:** the record states the page size bound, the byte bound, the navigation behaviour and what instant whole-day filtering costs once the whole day is no longer present.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Today's contract is whole-day. Bounding the download is a new static page contract and a reader-facing change, so it is authored and stopped, never implemented inside this plan. | Owner |
  | 2 | Instant substring filtering over a whole day cannot survive a byte-bounded fetch without a separate local index. That cost is named before anything is built. | Andre |

## 28 - Row #27 - Living docs sweep

- **Scope:** Update the living docs every landed row changed, and close the audit IDs in the research handover.
- **Files touched:**
  - `docs/architecture/` the frontend, telemetry and state living docs
  - `docs/concepts/` the pages whose vocabulary moved
  - `docs/reference/data-growth-audit.md`
  - `TODO/20260906-data-growth-research.md`
- **Acceptance gates:** documentation only - the shared test selector must select nothing but the whitespace check.
- **Oracle:** every finding this plan closed is marked closed with its PR, and every living doc a row changed states the new behaviour rather than the old one.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Historical source evidence in the audit is not overwritten to look current; closure is recorded alongside it. | CLAUDE.md section 5 |
  | 2 | The month-partition concept doc from row 10 is the single definition; other docs link to it. | documentation-structure.md |

## See also

- [data-growth-research.md](20260906-data-growth-research.md) - the 155-finding research handover this plan draws rows 2-26 from.
- [../docs/reference/data-growth-audit.md](../docs/reference/data-growth-audit.md) - the audit and its evidence.
- [../docs/how-to/execute-a-plan.md](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan stamps.
- [../docs/how-to/run-the-gates.md](../docs/how-to/run-the-gates.md) - the gate commands every row's acceptance section names.
