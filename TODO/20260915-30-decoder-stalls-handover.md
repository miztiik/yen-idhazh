# Handover: the decoder stall, the worker's clock, and the label call's dead weight

**Written**: 2026-09-15. **For**: an agent with no prior context.
**Read first**: [`CLAUDE.md`](../CLAUDE.md), then [`docs/agents/bootstrap.md`](../docs/agents/bootstrap.md).

Everything below is measured. Where a number appears, the command that produced
it is given, so you can re-take it rather than trust it.

---

## 1. What already landed, so you do not redo it

| id | Change | Where |
| --- | --- | --- |
| L1 | The element-id pattern bounds its own length: `^[a-z]{1,8}-[0-9]{1,6}-[0-9]{1,6}$` | merged, `c1c186ac` (#756) |
| L2 | A contract test: no `pattern` in any decoder schema may hold `+`, `*` or `{n,}` | `backend/tests/contracts/test_decoder_grammar.py` |
| L3 | `visuals.enabled_kinds` gets its first reader in `reachable_types` | `backend/idhazh/visual_planner.py` |
| L4 | The heartbeat names the call in flight instead of saying `summarize` for both | `backend/idhazh/itemrecord.py` |
| L5 | The prefill rates divide by tokens the server really evaluated | `backend/idhazh/stages/work.py` |
| L6 | The item clock stops across the queue; `queue_wait_ms` subtracts `extract_ms` | `backend/idhazh/itemrecord.py` |
| L7 | `backend/utilities/pipeline_artifact_analyzer.py` reads an item's calls as a report | new utility, `docs/how-to/analyze-a-pipeline-artifact.md` |
| L8 | The seed-gate test builds the day it needs instead of borrowing the newest | merged, #758, by another agent |

### The bug L1 fixed, because everything else is downstream of it

`llama.cpp`'s schema-to-grammar converter honours a `pattern` **or** a length
bound, never both. `schemas/visual-plan.schema.json` declared `maxLength: 22`
beside `pattern: "^[a-z]+-[0-9]+-[0-9]+$"`, so the bound never reached the
grammar and the decoder got `[a-z]+` - a state admitting no space and no
capital, whose only exit is a hyphen then a digit, which is never the argmax
once a model is inside an English phrase.

On 2026-09-14 one reply wrote **15,472 characters into that 22-character
field**, burning **15.8 minutes** of a 4 vCPU runner, on an item whose own
`decision` field already read `"none"` - it had decided against a picture and
then spent a quarter of an hour drawing one.

---

## 2. The branch waiting for you

**Worktree**: `yen-idhazh.worktrees/p31-clock`. **Branch**:
`fix/a-worker-gets-a-clock`, off `247e386a`. **Pull request
[#766](https://github.com/miztiik/yen-idhazh/pull/766)**, out of draft.

`ruff` and `mypy` are clean and every test passes. The suite was run locally on
the merge commit; read CI's own verdict before merging, because a local pass and
an absent check are not the same thing (section 8).

### What the branch contains

- `FailureCode.MODEL_TIMED_OUT` and `FailureCode.SHARD_OUT_OF_TIME`
- `TimeoutError` caught **ahead of** `OSError` at both call sites in
  `backend/idhazh/stages/common.py`. This is the whole of the attribution bug:
  a socket timeout is a `TimeoutError`, `TimeoutError` subclasses `OSError`, and
  the handler meaning "nothing answered" swallowed "answered too slowly".
- `run.shard_wrap_up_minutes`, default 12, in
  `backend/idhazh/contracts/knobs/run.py`
- A deadline in `stage_work`'s model loop: stop starting items once the time
  left is less than the slowest item this shard has already finished. Needs no
  estimate and calibrates itself to whichever processor the shard drew.
- `backend/tests/pipeline/test_assembly.py::test_a_hung_model_request_costs_one_item_not_the_shard`
  corrected - **it asserted `MODEL_UNREACHABLE` against a server that accepts
  every request and answers none, so it documented the defect**
- A new `test_a_shard_out_of_clock_stops_itself_instead_of_being_killed`
- Five contract changelog entries stamped `2026-09-15T22:10`

### The three failures, and what closed them

All six are closed. The branch is green: `ruff` 0, `mypy` 0 over 354 files, the
schema drift gate byte-clean, and the whole backend suite exit 0 on
2026-09-15. Re-run with:

```powershell
$w = 'c:\...\yen-idhazh.worktrees\p31-clock'
cd $w; $env:PYTHONPATH="$w\backend"
..\..\yen-idhazh\.venv\Scripts\python.exe -m pytest backend/tests -n auto -q
```

| id | Failing test | What closed it |
| --- | --- | --- |
| B1 | `test_telemetry.py::test_every_failure_code_has_a_real_fixture_writer[shard_out_of_time]` | **The code had no `ItemHealthRow` writer at all, so adding it to `_NO_REPLY_DETAIL` alone would have been a fixture nothing produces.** A skipped item wrote the code into its log record and no summary payload, and the census row is built from the payloads - so `telemetry.classify_item` filed it `unknown` carrying "summary payload missing", a throughput problem reported as a mystery. `stage_work` now writes the refusal as a summary payload as well, which is what makes `shard_out_of_time` reach the ledger the code was minted for. The new test's "no `.summary.json` was written" assertion was a proxy for "nothing was asked of the model"; it now asserts that directly, on `call_1 is None` |
| B2 | `test_taxonomy_and_prompts.py::test_recorded_item_health_codes_never_count_against_a_source` | The second counter was the test's own literal. `docs/architecture/sources/item-health.md` already carried the word. The set is 19 with `model_refused` merged in from `main` |
| B3 | `test_taxonomy_and_prompts.py::test_the_pages_that_name_the_summarize_codes_still_agree_with_the_enum` | `docs/how-to/troubleshoot-one-url.md` gained a row for each code, each naming the knob an operator should read next |

Also done: the app-config fixture (`shard_wrap_up_minutes: 7`), the
`model_timed_out` fixture writer, the schema drift gate, and
`docs/concepts/config.md` line 1195 saying a hung request records
`model_timed_out`.

This is **Level 5** - it crosses contracts, config and a stage loop.

---

## 3. The bug list, everything still open

| id | Bug | Evidence | Where to start |
| --- | --- | --- | --- |
| F1 | **The budget can never fire before the clock.** `request_timeout_minutes` is 22.1 minutes (1,326 s). The summary budget of 4,735 tokens needs 954 s on an EPYC and **1,259 s on a Xeon - 5% headroom**. The label budget of 6,491 tokens needs 1,284 s to 1,699 s and **fits on no machine**. Hitting the budget is graceful (`recovered_completion` keeps the summary); hitting the clock loses the whole item | 4 items lost on shard 1 of run 34943695821 | Make the budget derived: `min(widest_json_budget, timeout_seconds * floor_decode_rate)`, plus an import-time check. `backend/idhazh/classify/calls.py` |
| F2 | **The job log and the committed ledger disagree** about whether the label call ran. The log records `label_finish_reason: stop` with `label_ms` filled; the ledger leaves both empty and carries only `label_output_tokens` | Same four items | Find where the failed row is projected into `state/item-health/`. `backend/idhazh/telemetry.py`, `backend/idhazh/stages/record.py` |
| F3 | **Six label fields reach no reader**, and two may never reach one | Section 5 below | Section 5 |
| F4 | **`not_attempted` covers two different things** - items the plan never reached, and items the clock never reached | 248 rows on 09-14 | **Closed.** An item the clock never reached now records `shard_out_of_time` in `state/item-health/` as well as in the log, because the worker writes the refusal as a summary payload and the census row is built from the payloads |
| F5 | **The element-column docs are five rows where fifteen are needed** | `docs/architecture/extraction/elements.md` line 331 | Section 5's table is written; paste it |
| F6 | **`copied_source` at 0.817** - one summary was 81.7% a single unbroken run copied from the article | `india-fas136vmnffehhzp`, 09-15 | Not investigated. May or may not be the same decoder failure wearing a different coat |
| F7 | **Sort the model loop by exact word count, not just by band.** `_summarize_band_sort_key` already sorts ascending by length band; inside a band the order is arbitrary. With the branch's deadline, exact ascending order means whatever the clock cuts is always the longest and least likely to publish | Section 4a: failure rises from 11.7% under 300 words to 53.8% over 1,500 | One line in `backend/idhazh/stages/work.py:137` |
| F8 | **`key_points` and `keyphrases` are one character apart and unrelated.** One is the published bullet list from the summarize call; the other is a dead search facet from the label call. Rename one | Section 5 | A published key is frozen while its Python name moves - see `docs/architecture/contracts/schemas.md` |

---

## 4. Research results you do not need to repeat

### 4a. Article length predicts failure. The sort already exists.

545 item rows across 2026-09-14 and 09-15:

| words | items | published | fail % | median label output |
| --- | --- | --- | --- | --- |
| 0-300 | 103 | 91 | **11.7%** | 521 tokens |
| 300-600 | 89 | 67 | 24.7% | 921 |
| 600-1000 | 51 | 38 | 25.5% | 998 |
| 1000-1500 | 22 | 14 | 36.4% | 1,094 |
| 1500-2500 | 13 | 6 | **53.8%** | 1,606 |
| 2500+ | 1 | 0 | 100% | - |

Correlation between article words and label output tokens: **r = 0.474** over
273 pairs. Length explains about a fifth of the variance - real, but not the
whole story.

**`_summarize_band_sort_key` in `backend/idhazh/stages/work.py:137` already
sorts the model loop ascending by length band.** Short articles already go
first. The refinement available is to sort by exact word count inside a band,
which is one line. **Combined with the branch's deadline this is the whole
answer to "stop a shard losing work"**: cheap high-success items run first, so
whatever the clock cuts is always the longest and least likely to publish.

Re-take with `backend/utilities/` style script over `state/item-health/2026/09/*.csv`.

### 4b. Fetch has not got slower, and extract is 50 ms

| day | items | median fetch | p90 fetch | median extract |
| --- | --- | --- | --- | --- |
| 09-01 | 634 | 596 ms | 2,137 ms | 52 ms |
| 09-11 | 376 | 648 ms | 1,759 ms | 50 ms |
| 09-14 | 202 | **706 ms** | 1,805 ms | 48 ms |
| 09-15 | 72 | **496 ms** | 1,419 ms | 50 ms |

The 706 ms is the month's highest but 09-03 was 646 and the next day was 496,
the month's lowest. p90 is flat throughout. This is noise in a sample that
shrank from 634 articles to 202, not a regression.

### 4c. Overlapping fetch with the model is not worth building

Across run 34943695821, fetch plus extract is **0.10% to 0.18% of a shard** -
12 to 22 seconds of a 157 to 202 minute shard. If both were entirely free each
shard would finish 12-22 seconds earlier. **One runaway plan cost 1,039 to
1,132 seconds.** The prize is fifty times smaller than a single stall, and it
would add concurrency to the one loop that is currently simple. 81% of a shard
is the model. Do not build this.

### 4d. Can a cut reply be continued? It already is, and a true resume is not available.

`llama-server` exposes no way to resume a **grammar-constrained** decode: the
grammar state at the cut point is not part of the API, so a "continue" request
is a fresh prefill under a fresh grammar and would cost more than it saves.

What exists instead is better. The reply shape puts `summary` before `visual`,
so a reply cut by its budget still carries a complete summary, and
`recovered_completion` in `backend/idhazh/classify/calls.py` rescues it. That is
the continue-equivalent and it already ships. **This is also the argument for
F1**: make the budget fire before the clock, because the budget path keeps the
article and the clock path loses it.

### 4e. The run budget is per job, not one pool

`.github/workflows/digest.yml`: `plan` has `timeout-minutes: 30`, `work` has
`shard_timeout_minutes` (200), `assemble` has `timeout-minutes: 20`. These are
separate jobs, each with its own GitHub six-hour ceiling, so the shards are not
eating the assembly's budget. What they do share is the day's wall clock:
30 + 200 + 20 = 250 minutes from dispatch to published day.

---

## 5. `keyphrases`: the answer, and what to do

### The direct question, answered

**Is `keyphrases` deterministic Python costing no tokens? NO.**

It is a field on `LabelReply` (`backend/idhazh/classify/calls.py:328`) and the
prompt asks for it explicitly
(`backend/idhazh/prompts/label_article_elements.txt:71`: *"up to eight short
phrases, each copied from the item, that say what it is about"*). **The model
decodes it, and it costs decode tokens on every article.**

Measured from the captures of run 34943695821 shard 3: **70 to 73 tokens an
article, 8 to 10 percent of the label reply**, and **138 keyphrases across 20
articles**. At the measured 4.9 tokens a second that is about 15 seconds an
article, roughly 5 minutes a shard.

### Why it was built - the document you asked for

[`TODO/20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md)
line 999:

> | **Topical keyphrases**, 5-8, verbatim | **The only search surface that needs no embedding model.** Also an archive facet | ~50 | 4.5 min | **TAKE.** Verbatim and span-anchored, or not at all |

So the reason was **search without an embedding model**, costed at the time at
about 50 tokens and 4.5 minutes a shard. It was never for dedup and never for
the title.

The two-call summariser plan (delivered) carried it into its design as part of
"about 140 output tokens, 12.5 minutes of shard wall clock at 20 items".

**The premise then died.** Search now runs on an embedding vector in the month
index (`backend/idhazh/contracts/observation_index.py`), which carries date,
item id, title, vertical and the vector - and **no keyphrase field**. The thing
keyphrases existed to avoid is the thing that shipped.

[`TODO/20260914-27-pipeline-observability-plan.md`](20260914-27-pipeline-observability-plan.md)
line 28 already lists retiring it as out of scope, blocked on "a reading of what
those two arrays cost in decoded tokens". **That reading now exists and is in
this file.** The block is cleared.

### Useless for dedup, and you were right about why

The prompt says *"Copy them; do not invent them."* Verbatim copies cannot
support semantic dedup - two articles about one story in different words share
no phrases. Dedup does not use them and never did: it lives in
`backend/idhazh/rank.py` and `backend/idhazh/discover.py`, shipped by **PR #467,
"plan: record-only semantic dedup of the same story at two addresses"**, merged
2026-09-06. That PR touched `cli.py`, `discover.py`, `rank.py`, `app_config.py`
and `config/idhazh.json`, and no part of the label call.

### `key_points` and `keyphrases` are two unrelated things

| | `key_points` | `keyphrases` |
| --- | --- | --- |
| Which call | the **summarize** call | the **label** call |
| What it is | the 2-3 bullet points under a published summary | up to 8 phrases copied from the article |
| Who reads it | **every reader, on the page** | nobody |
| Cost | part of a ~250-token summary | 70-73 tokens an article |

Two different calls, two different purposes, names one character apart. Renaming
one is worth a row on its own.

### Recommendation

Delete `keyphrases` and `lede_sentence_ids` from `LabelReply` and from the
prompt. Both stated consumers already exist and neither reads these fields:
search uses the embedding, and `lead_coverage` is a deterministic function in
`backend/idhazh/evals/metrics.py`. Saving is about 80 tokens and 17 seconds an
article. Nothing is lost.

---

## 6. What the label call asks for, and why - the fifteen-row table

`docs/architecture/extraction/elements.md` line 331 has a five-row version.
Replace it with this. Counts are from run 34943695821 shard 3, 20 articles.

| Field | What we ask for | Why | Who reads it | Found |
| --- | --- | --- | --- | --- |
| `labels[].element_id` | The address of a figure the pattern pass found | Points rather than types, so a number cannot be invented | element table -> chart | 60 |
| `labels[].measure` | What the figure measures, in the article's words | "4,200" is not an axis label; "exports" is | the chart's axis | - |
| `labels[].dimension` | What it varies over - year, region | What makes a series a series | the chart | - |
| `labels[].entity` | Whose figure it is | Two numbers share a chart only if they measure comparable things | the chart's grouping | - |
| `labels[].time_element_id` | The address of the date this figure belongs to | The whole of a time series | the chart's time axis | - |
| `labels[].attribution` | named / self_reported / anonymous / unattributed | A figure a company said about itself is not one a regulator published | element table | - |
| `labels[].hedge` | Did the article say "about", "expects", "may" | A hedged figure must not be drawn as a fact | element table | - |
| `labels[].salience` | primary / supporting / background | Which figure the story is about. A word, never a score - the model may not type `0.83` | the chart's ranking | - |
| `proposed[]` | A figure in digits the pattern pass missed | The regex misses figures inside odd punctuation. Model proposes, code re-reads the characters | the chart | **0 of 20** |
| `entity_mentions[]` | Organisations and people, and where each is named | Groups "OpenAI", "ChatGPT", "the company" into one thing | **nobody** - published entities come from the watchlist match | 87 |
| `place_mentions[]` | The same, for locations | Same | **nobody** | 15 |
| `quotes[]` | Two sentence addresses, no text | Indices only: an exact text search rejects a real quote over one changed word, silently | **nobody, and barred** - the sentences are the article's (`CLAUDE.md` section 0a) | 24 |
| `claims[]` | The same, for the article's own assertions | Same | **nobody, and barred** | 73 |
| `keyphrases[]` | Up to 8 phrases copied from the article | "The only search surface that needs no embedding model" | **nobody** - search uses the embedding | 138 |
| `lede_sentence_ids[]` | The 1-2 sentences carrying the main point | "Carried for `lead_coverage`" | **nobody** - `lead_coverage` is deterministic | 20 |

`labels` was empty on **8 of 20** articles and `proposed` on **all 20**. The two
fields with a path to a reader produced 60 entries; the six without produced 357.

---

## 7. How to see what the model was actually sent

Captures are a run artifact with 90-day retention, never committed, because a
rendered prompt carries the article body and republishing one is a non-goal
(`CLAUDE.md` section 0a).

```powershell
gh run download <run-id> --repo miztiik/yen-idhazh --name captures-<shard> --dir cap
python backend/utilities/pipeline_artifact_analyzer.py cap
python backend/utilities/pipeline_artifact_analyzer.py cap --item <part-of-an-id> --out out.md
```

Without `--item` it lists every item with four sizes. With `--item` it prints
label prompt, label reply, summarize prompt, summarize reply in the order the run
made them, says what share of the second prompt is the first one, and flags any
unbroken lowercase run over 200 characters - which is what a decoder stuck in a
loose grammar looks like on sight.

Ten worked examples from run 34943695821 shard 3 are in
`test-results/prompt-evals/` (gitignored). One of them,
`business-economy-576464r9tm9ajzwk.md`, is a 17.9-minute runaway.

---

## 8. Traps that cost time in the session that wrote this

- `gh api .../jobs/<id>/logs` returns **HTTP 404 while a job is in progress**.
  Only finished jobs serve logs.
- `gh run watch` and `gh pr checks --watch` open the alternate screen buffer and
  wedge the terminal tool. Set `$env:GH_PAGER='cat'`.
- **`main` is unprotected**, so `gh pr merge --auto` merges immediately rather
  than waiting for checks. Check the gates yourself first.
- **An absent check is not a passing check.** PR #766 recorded **zero** check
  runs against its pushed commit - `gh pr checks` says "no checks reported on
  the branch" and `gh api repos/.../commits/<sha>/check-runs` returns an empty
  list. `ci.yml` triggers on `pull_request` with no draft filter, so why it did
  not run is unresolved; the likeliest cause is its `cancel-in-progress`
  concurrency group under several agents pushing at once. Before you trust a
  quiet PR, look for the check runs on the SHA, not at the absence of red.
- Several agents work this repository at once, and **they will take your
  worktree path**. `yen-idhazh.worktrees/p31-clock` was recreated by another
  agent following section 2 of this page, and then also used for unrelated
  workflow edits. Pick a path nobody has been told to use, guard every command
  with a unique tag, and put `if ($PWD.Path -ne $target) { exit 9 }` after every
  `Set-Location`.
- Adding one `FailureCode` member breaks a fixture writer, three docs assertions
  and a config fixture. That is the suite working, not a problem - budget for it.
- `config.Settings` is a dataclass, not a Pydantic model. Use
  `dataclasses.replace`, not `model_copy`.
- `ruff format` would reformat 172 files and is **not** a project gate. Only
  `ruff check` is. Wrap long strings by hand.

## See also

- [`docs/architecture/summarize/throughput.md`](../docs/architecture/summarize/throughput.md) - the two rates and what they mean
- [`docs/architecture/contracts/schemas.md`](../docs/architecture/contracts/schemas.md) - "a pattern in a decoder schema must bound its own length"
- [`docs/reference/github-actions.md`](../docs/reference/github-actions.md) - the artifacts and how to read the captures
- [`docs/architecture/sources/item-health.md`](../docs/architecture/sources/item-health.md) - the failure codes, and the page B3 and B4 need updated
