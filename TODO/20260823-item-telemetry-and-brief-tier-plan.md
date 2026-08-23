# Item telemetry, short sources, and an honest console - plan

**Last Updated**: 2026-08-23
**Level**: 4 (structural, multi-file, crosses `backend/`, `state/`, `schemas/`, `frontend/`, `config/`)

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The run of 2026-08-23 published 8 of 17 items, recorded the cause of none of them, and destroyed the evidence in 24 hours. Diagnosing it needed an expiring artifact and 9 URLs re-fetched by hand. |
| Hard scope - in | A per-item-per-run census ledger under `state/`; a stable failure-code enum; the extraction floor moved off length onto shape; a labelled brief tier for short sources; a paywall discriminator; the console's failure and compression views; prompt-cache measurement; the docs for all of it. |
| Hard scope - out | Retiring or demoting any source by rule (blocked on 30 days of rows, Rule #10); PDF text extraction; a hosted log sink; changing `EvalRow`'s meaning; the saturated faithfulness thresholds; `SummaryStatus.SKIPPED`. |
| ESCALATE triggers | (1) Any proposal to serve `state/` raw to a reader (a narrow published projection is the sanctioned path - row 10). (2) Any threshold in row 11 being read by ranking before 30 days of rows exist. (3) A `determinism_violation` appearing after the prompt reorder in row 9. (4) Any move to publish a metered or paywalled source - `CLAUDE.md` section 0a forbids it and row 7 enforces it. (5) Adding a failure breakdown to `RunManifest`. |
| Chosen strategy | Contract, then writer, then reader, then view. The column lands before the chart; the rubric waits for the rows. Ruled jointly by Fowler (Q1, Q4) and Jony (blocking finding). |
| **Owner overrides** | Five, recorded below. They supersede the persona rulings they touch (`CLAUDE.md` section 0). |
| **Precondition** | **SATISFIED 2026-08-23.** PRs #1 and #2 merged; `state/`, `ledger.py`, `contracts/feed_health.py`, `contracts/seen.py`, `discover.resting()` and `docs/architecture/sources/health.md` are on `main`. PR #7 landed the Rule rename and the Rule #1 amendment that O1 depends on. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3.` |

### Owner overrides (2026-08-23)

| # | Override | What it replaces | Why |
| --- | --- | --- | --- |
| O1 | **The console charts are interactive: client-side JS reads a published CSV, and the reader pans and zooms a time viewport. A charting library is expected.** | Jony Q1's build-time-only, no-library ruling and its premise that "Rule #1 forbids the fetch that would feed one". | The premise was wrong when written - Rule #1 always permitted fetching our own committed files - and PR #7 has since cut the rule at *a service* rather than *an origin*. A third-party library is now judged on bytes and licence under section 8, like any dependency. |
| O2 | **The 30-day window is a viewport, never a deletion.** Today need not sit at an edge; the view may centre or right-align it, and the reader scrolls back through everything. | The plan's reading of the ask as "roll the file". | The owner never asked to delete data. Fowler's append-only ledger is unchanged and now serves the viewport instead of arguing with it. |
| O3 | **Length is not an editorial test. News is news at one line or fifty.** | Reader's rejection of the llama.cpp release items, and any drop-on-shape rule. | Newsworthiness is the owner's judgement, not a persona's. The pipeline may **record** that a page is a listing; it may not **discard** the item for it unless the owner sets the knob. |
| O4 | **The metered-paywall rejection stands.** | - | Upheld. Agrees with Reader and with `CLAUDE.md` section 0a. |
| O5 | **Every defect found in this investigation gets a fix row, not a footnote.** | The original "Known defects this plan records but does not fix" table. | A defect parked in a table is a defect nobody owns. |


### Facts this plan rests on (all measured 2026-08-23 unless noted)

| # | Fact | How it was established |
| --- | --- | --- |
| F1 | `items_failed = planned - succeeded - skipped`. A subtraction, not a diagnosis. | `assemble.py:257` |
| F2 | `failure_detail` exists on Article/Summary/Route but lands only in gitignored `backend/var/`, artifact retention 1 day. | `.gitignore:47`, `digest.yml` |
| F3 | `stage_assemble` skips a failed item entirely: `if not (article_path.exists() and summary_path.exists()): continue`. The failure payload is on disk and never read. | `cli.py:668` |
| F4 | `EvalRow` already carries `source_word_count`, `source_seen_word_count`, `summary_word_count`, `compression` - but only for items the scorer measured. | `contracts/eval_row.py:149-153` |
| F5 | The console charts `fetch_ms`, `extract_ms`, `summarize_ms` from `scores.csv`. Those columns are not in the header. Three medians are structurally always zero. | `console/+page.server.ts:152-154` vs `state/scores.csv` header |
| F6 | `ledger._append` has no header guard; `evals/writer.append` has one. A column added to `FeedHealthRow`/`SeenRow`/`PublishedRow` silently shifts every historical cell. | Fowler, code read |
| F7 | `boilerplate_ratio()` and `boilerplate_ratio_max` both exist. No production caller - tests only. | grep: only `extract.py` def + `test_extract.py` |
| F8 | The 801-token system prompt is NOT constant. `band_for()` substitutes `$target_words_min/max` at line 30 of 79. Three distinct prompts; universal prefix ends ~line 29. | Andre and Carmack, independently |
| F9 | Prefill 12.1 tok/s (8B, 4 threads, EPYC 9V74, llama.cpp b10580, 3 repeats, 2026-08-22) -> 801 tokens = 66.2 s per re-prefill. | `docs/reference/measurements.md` |
| F10 | The 7 floor failures are correctly extracted short-form pages, not slow sources and not JS shells. Fetches 0.45-0.80 s. | Re-fetch + markup-prose comparison |
| F11 | `config.summarize.bands[0]` already asks 50-90 words of a 0-699 word article; the gate already accepts 40. Only `min_source_words=250` drops the item. | `config/idhazh.json` |
| F12 | `state/` is never served to Pages; only `frontend/build` is uploaded. | `pipeline-loop.md:73`, `payload.ts:34` - re-verify `pages.yml` in row 2 |
| F13 | `state/`, `ledger.py`, `FeedHealthRow` and `health.md` are NOT on `main`. They sit on open PRs #1 and #2. Persona rulings that cite them read the feature-branch working tree. | `git ls-tree origin/main -- state/` returns empty |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Header guard into `ledger._append` | - | A | PENDING | - | - | - |
| 2 | `ItemHealthRow` contract + schema | - | A | PENDING | - | - | - |
| 3 | Measure the prompt cache | - | A | PENDING | - | - | - |
| 4 | Extract `_item_payloads()` from `stage_assemble` | 1 | B | PENDING | - | - | - |
| 5 | Classifier + writer + `items_failed` becomes a count | 2, 4 | C | PENDING | - | - | - |
| 6 | Stage timings onto the census row | 5 | D | PENDING | - | - | - |
| 7 | Prose-shape gate, `boilerplate_ratio` wired, paywall discriminator | 5 | D | PENDING | - | - | - |
| 8 | Brief tier: floor, band, gate, reader sentence | 7 | E | PENDING | - | - | - |
| 9 | Prompt reorder for prefix reuse | 3 | D | PENDING | - | - | - |
| 10 | Console: interactive viewport over the census | 5, 6 | E | PENDING | - | - | - |
| 11 | Source yield rubric - recorded only, reads nothing | 5 | F (BLOCKED 30 days) | PENDING | - | - | - |
| 12 | Docs: every page this plan moves | 5, 8, 9, 10, 13 | F | PENDING | - | - | - |
| 13 | llama-server runtime sweep: measure every flag we do not set | 3 | D | PENDING | - | - | - |
| 14 | Stop serialising on CI: parallel dispatch in the process docs | - | A | PENDING | - | - | - |
| 15 | Repair the ledger header, and stop it drifting again | 1 | B | PENDING | - | - | - |
| 16 | A dead model server says so | 2 | C | PENDING | - | - | - |
| 17 | Per-request timeout sized from an item, not from the shard | - | A | PENDING | - | - | - |
| 18 | Fold `/evals` into `/console` | 10 | F | PENDING | - | - | - |
| 19 | The band reads its own counterweights | - | D | PENDING | - | - | - |
| 20 | Two frontend defects: `EmptyDay` notice, baked build date | - | A | PENDING | - | - | - |

Parallel groups run in order A -> B -> C -> D -> E -> F. Row 11 is additionally gated on 30 days of committed rows.

Rows 15-20 are the defect fixes required by O5. Rows 19 and 20 come from the owner's own [`20260823-known-defects-plan.md`](20260823-known-defects-plan.md); its remaining entries (saturated bands, Level 5) stay there because they need rows before they can be re-cut.

---

## Row #1 - Header guard into `ledger._append`

- **Scope:** `ledger._append` refuses to append when the committed header does not match the contract's columns, matching `evals/writer.append`.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/evals/writer.py`
  - `backend/tests/test_ledger.py`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate.
- **Oracle:** A committed CSV carrying yesterday's header plus a contract with a new column MUST raise. Assert on all three merged ledgers (`feed-health`, `seen`, `published`).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Move Function: one guard, shared, not a second implementation. | Fowler |
  | 2 | Lands first, alone. It is latent silent corruption of three already-merged ledgers, not a follow-up. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Fix it inside the telemetry PR | Mixes a live-defect fix with a new surface; the fix is invisible in review. | Fowler |
  | 2 | Tolerate a mismatch and pad | `payload.ts:readCsv` maps by header position. Padding writes wrong data under right names. | Fowler |

---

## Row #2 - `ItemHealthRow` contract + schema

- **Scope:** The Pydantic contract for one row per item per run, its generated schema, and its enums. No writer yet.
- **Files touched:**
  - `backend/idhazh/contracts/item_health.py`
  - `backend/idhazh/contracts/export.py`
  - `schemas/item-health-row.schema.json`
  - `backend/tests/test_contracts.py`
  - `tests/fixtures/contracts/item-health-row/*.json`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate regenerates byte-identical.
- **Oracle:** Every cross-field invariant rejects a bad row. Specifically `outcome=ok` with a non-null `code`, `code` not belonging to its `stage`, and `http_status` on a non-`fetch` row must each raise.
- **The columns (16):** `version, date, run_id, item_id, url_key, canonical_url, vertical, source_id, stage, outcome, code, http_status, source_chars, source_words, summary_words, detail`
- **The enums:**
  - `ItemStage = plan | fetch | extract | summarize | publish`
  - `ItemOutcome = ok | failed`
  - `FailureCode` (15): `not_attempted`; `robots_denied`, `robots_unreachable`, `blocked_address`, `http_client_error`, `http_rate_limited`, `http_server_error`, `network_error`; `no_text`, `too_short`; `model_unreachable`, `output_truncated`, `bad_shape`, `length_out_of_range`; `unknown`
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | ONE file, every planned item, successes and failures. A failure-only file cannot produce a rate, and a rate is what a chart needs. | Fowler, citing `health.md`'s own rejected alternative |
  | 2 | `state/item-health/<YYYY-MM>.csv`. Monthly shards, following `state/seen/` and `state/feed-health/`. | Fowler, Carmack |
  | 3 | Append-only, never pruned. The 30-day window is a read-side parameter. Deleting history deletes the answer to next year's question. | Fowler |
  | 4 | `canonical_url` is on the row. ~80 bytes buys back the 24-hour artifact hunt that made 2026-08-23 expensive. | Fowler |
  | 5 | `url_key` as well as `item_id`. `item_id` is a per-day ordinal and moves between runs; a trend about one article needs the stable key. | Fowler |
  | 6 | `detail` is `str \| None`, max 200, populated ONLY when `code = unknown`. The column is designed to empty itself; a non-empty cell is a work item meaning "mint an enum member". | Fowler |
  | 7 | `route` and `render` are not stages an item can terminate at - a render failure degrades the item and never fails it. | Fowler, citing `contracts/route.py` |
  | 8 | Nine of the fifteen codes are marked as never counting against a source. That marking is the input to row 11. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Two files - failures, and word counts | Two parses, two schemas, two things to keep in sync, for one row's worth of facts. | Fowler, Carmack |
  | 2 | Store `compression` on the row | A derived value. Both operands are on the same row; the chart divides. A second ratio is two numbers free to disagree. | Fowler |
  | 3 | Reuse `state/scores.csv` | It means "items the scorer measured", not "items that happened". An item failing the floor never reaches it - the sample is censored exactly where the signal is. | Fowler |
  | 4 | Persist `failure_detail` free text as the signal | A chart cannot group free text; two runs phrasing one cause differently grows 400 buckets. | Fowler, Jony |
  | 5 | Mint `boilerplate`, `paywall`, `skipped` now | An enum member with no writer is speculative generality. Mint each in the commit that mints its writer. | Fowler |
  | 6 | `attempt`, `recorded_at`, `title`, `source_url` columns | No query attached; `date` + `run_id` already address the row. | Fowler |

---

## Row #3 - Measure the prompt cache

- **Scope:** Answer whether the system prefix is reused, using the log the runner already writes. No production code change.
- **Files touched:**
  - `.github/workflows/digest.yml` (upload `llama-server.log` as an artifact; add an always-run grep step)
  - `docs/reference/measurements.md`
- **Acceptance gates:** One dispatched `digest` run; the numbers land in `measurements.md` with hardware, date and spread.
- **Oracle:** For three consecutive items in one shard, record `p0` from `kv cache rm [p0, end)` and `N` from `prompt eval time = X ms / N tokens`. `p0 == 0` is a total miss; `p0 ~= 801` is a full hit; `p0 ~= 315` is head-only reuse. Also capture `n_slots` and `n_ctx_per_seq`.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Measure before building. If the prefix is already reused, rows 3 and 9 close with a recorded number and no code. | Carmack, Rule #10 |
  | 2 | The log is the instrument. `usage.prompt_tokens` reports the full prompt whether cached or not, which is exactly why this is invisible today. | Carmack |
  | 3 | Check `n_ctx_per_seq` in the same pass. `--parallel` defaults to auto; llama.cpp divides `n_ctx` across slots, and the measured worst case is 4201 tokens. If auto opens 2+ slots the worst case does not fit. **Report as a defect if confirmed.** | Carmack |
  | 4 | `cache_prompt` is sent explicitly rather than inherited from a server default the code never asserted. | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Cite the README's `--cache-ram` default as evidence | A flag existing is not a measurement that our prompts hit it. | Carmack, Andre |
  | 2 | Add `timings` capture to the payload first | The log answers it this run with no contract change. Persist the field once there is a reason. | Carmack |

---

## Row #4 - Extract `_item_payloads()` from `stage_assemble`

- **Scope:** Structural only. Pull the per-item payload read out of `stage_assemble`'s loop so it can also yield items that have an `article.json` but no `summary.json`. Output byte-identical.
- **Files touched:**
  - `backend/idhazh/cli.py`
  - `backend/tests/test_pipeline.py`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`; golden fixture run produces byte-identical `digest.json` and `run.json`.
- **Oracle:** Byte-identical `digest.json` and `run.json` before and after. A structural commit that moves a byte is not structural.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Tidy First: this is the "make the change easy" step, so row 5 is then one obvious change. Separate commit, separate PR. | Fowler / Beck |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Do it inside row 5 | A mixed-hat commit. The behavioural change hides inside the move. | Fowler |

---

## Row #5 - Classifier + writer + `items_failed` becomes a count

- **Scope:** Map every terminal item state to a `FailureCode`, append one census row per planned item per run, and make `items_failed` a count of `outcome=failed` rows.
- **Files touched:**
  - `backend/idhazh/telemetry.py` (the classifier)
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/assemble.py`
  - `.github/workflows/digest.yml` (`git add state/item-health`)
  - `backend/tests/test_telemetry.py`, `backend/tests/test_pipeline.py`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate. One dispatched run writes real rows.
- **Oracle:** **The classifier reaches every `FailureCode` member from a real fixture.** A member no fixture can produce is a member with no writer - delete it. Plus: a planned item with no `article.json` yields a `not_attempted` row rather than a silent decrement, so `items_planned == ok + failed` holds by construction.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `assemble` is the SOLE writer, once per run. Four shards appending and pushing would race the 3-attempt push loop and fail a shard on a telemetry commit - inverting "degrade, do not fail". | Carmack |
  | 2 | Shards contribute per-item JSON through the existing `items-*` artifact; assemble merges. That shape is already in use for every other item payload. | Carmack |
  | 3 | `detail` is written by the classifier, never copied from `Article.failure_detail`. Ours by construction, not by audit. Truncate to 200 (note `UntrustedLine` allows 500). | Fowler |
  | 4 | Sanitize on write in three passes: `sanitize.sanitize()`, then a formula guard stripping a leading `=`, `+`, `-`, `@`, tab or CR, then truncate and collapse whitespace. | Fowler |
  | 5 | One row per item per run, one terminal stage per row. An item that failed extraction does not also get a summarize row - that double-counts. | Fowler |
  | 6 | Fix `cli.py`'s `OSError` path, which today substitutes an empty completion and reports `JSONDecodeError` - blaming the model for a dead server. `model_unreachable` cannot classify correctly until it is marked. | Fowler |
  | 7 | `RunManifest` schema does not change. `items_failed` keeps its name and type and becomes an honest count. No changelog entry - the shape did not move. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Add a failure breakdown to `RunRecord` | Two records of one fact, free to disagree. The console loader already reads both surfaces and can join. Also a disguised breaking change: the obvious `sum(codes) == items_failed` validator rejects every `run.json` already committed. | Fowler |
  | 2 | Per-shard writers | Four concurrent rebases on one append-only file; the push loop exhausts and a shard fails on telemetry. | Carmack |
  | 3 | Emit to the log and scrape it later | `telemetry.md`: logs are evidence, ledgers are the record. CI logs age out. | Fowler, Jony |

---

## Row #6 - Stage timings onto the census row

- **Scope:** Add `fetch_ms`, `extract_ms`, `summarize_ms` to `ItemHealthRow` and repoint the console. Fixes F5.
- **Files touched:**
  - `backend/idhazh/contracts/item_health.py`, `schemas/item-health-row.schema.json`
  - `backend/idhazh/telemetry.py`
  - `frontend/src/routes/console/+page.server.ts`
  - `backend/tests/`, `frontend/tests/`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate, `npm run check`, `npm run build`, browser smoke per `CLAUDE.md` section 12.
- **Oracle:** The console's three timing medians are non-zero on a real run, and zero only when the ledger is genuinely empty.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Timings belong on the per-item-per-run census, not on `EvalRow` (the scored subset). The console repoints. | Fowler |
  | 2 | Appended at the END of the column list, never inserted. `EvalRow`'s own comment states the rule: a column inserted mid-row shifts every historical cell under a positional reader. | Fowler, citing `eval_row.py:177-184` |
  | 3 | Separate row from 5 because "which ledger carries stage timings" is its own decision and must not be made inside a failure-telemetry PR. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Add the columns to `EvalRow` | `EvalRow` is written only when the scorer runs. Timings would be missing exactly on the runs that were slow enough to matter. | Fowler |
  | 2 | Delete the three charts | The operator question "is it getting slower" is real; the data was simply never written. | Jony |

---

## Row #7 - Prose-shape gate, `boilerplate_ratio` wired, paywall discriminator

- **Scope:** Move junk rejection off length onto shape. Three deterministic checks, each with a `config/` knob and its own failure code.
- **Files touched:**
  - `backend/idhazh/extract.py`
  - `backend/idhazh/contracts/{app_config,article,item_health}.py`
  - `config/idhazh.json`, `schemas/*.schema.json`
  - `tests/fixtures/short-sources/*` (the 7 captured pages + 10 known-good)
  - `backend/tests/test_extract.py`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate.
- **Oracle:** Exact disposition match over `{publish_full, publish_brief, reject_listing, reject_paywalled}` on the 17-page labelled set, AND the failure reason for each. Baseline measured today: current code gets **4 of 7 dispositions and 0 of 7 reasons** right. Target 7/7 and 7/7.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Prose-shape check: require >= 3 sentences of >= 8 words. Below that the page is a listing -> `not_prose`. This catches the GitHub release page at 51 words AND at 500. `_SENTENCE_SPLIT` already exists in `evals/metrics.py`. **RECORDED, NOT ENFORCED** - see decision 7. | Andre, amended by O3 |
| 7 | **`not_prose` and `boilerplate` are recorded signals, never a drop.** `extract.reject_not_prose` and `extract.reject_boilerplate` are `config/` knobs defaulting to **false**: the item publishes, the row carries the code, the console shows it. Length and shape are evidence for the editor, not a verdict by the pipeline. Only `paywalled` and a genuine `no_text` drop an item. | **Owner override O3**, above Reader and Andre |
  | 2 | Wire `boilerplate_ratio` to `extraction_suspect` -> `boilerplate`. It is built, configured, tested and has no caller (F7). v1 compares same-run siblings only. | Andre |
  | 3 | Paywall discriminator ships in the SAME commit as the floor change in row 8, or the floor change is a regression that publishes paywalled content. | Andre; `CLAUDE.md` section 0a |
  | 4 | Paywall detection is publisher-declared and deterministic: `isAccessibleForFree: false` in JSON-LD, plus the `hasPart`/`cssSelector` paywall block. **Whether the Japan Times captures carry it is UNMEASURED - check the fixtures first.** Fall back to a `paywall_markers` lexicon in `config/` only if the markup is absent. | Andre |
  | 5 | Mint `not_prose`, `boilerplate` and `paywalled` codes here - the commit that mints their writers. | Fowler |
  | 6 | A feed-item that IS a PDF (`.pdf` URL or `application/pdf`) gets `unsupported_form`, not `extract_failed`. Today it reports "extractor found no article text", sending a reader to blame trafilatura. | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A model call to decide "is this a real article" | A classifier with no ground truth, on the runner's clock, for a job two string checks do. | Andre |
  | 2 | Keep using length to reject junk | A 51-word list of binary names and a 51-word paragraph of prose are the same number. Length cannot see shape. | Andre |
  | 3 | A per-host boilerplate store in `state/` | Same-run siblings first. Add persistence when a measured miss rate justifies it. | Andre |
  | 4 | Fetch the host's front page to learn its boilerplate | One more fetch per host per run for a signal the siblings already give. | Andre |

---

## Row #8 - Brief tier: floor, band, gate, reader sentence

- **Scope:** Publish short sources with an honest sentence instead of dropping them. Depends on row 7 shipping the paywall guard.
- **Files touched:**
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/{article,summary,digest_day}.py`
  - `backend/idhazh/prompts/summarize.txt`, `backend/idhazh/summarize.py`
  - `config/sources.json` (per-feed `form: abstract`)
  - `frontend/src/lib/components/*`, `schemas/*`
  - `backend/tests/`, `frontend/tests/`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate, `npm run check`, `npm run build`, browser smoke per section 12.
- **Oracle:** The 7 fixtures reach their ruled disposition: NBER x2, Marginal Revolution **and both llama.cpp release items** publish (llama.cpp carries `not_prose` in the ledger and publishes anyway, per O3); Japan Times x2 reject as `paywalled`. AND `verbatim_run <= 0.5` on every brief item.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `min_source_words: 250 -> 60`, **derived not chosen**: `brief_target_words_min / brief_compression_ceiling = 30 / 0.5`. It moves when the tier moves. | Andre |
  | 2 | New band 0 `{0, 30, 45}`; existing bands shift up one. `evaluation.summary_words_min: 40 -> 25`. The gate move is FORCED - the `AppConfig` validator rejects a band asking below the gate. | Andre |
  | 3 | This also drops the decoder's character rail from 200 to 125. **That is the point.** At `summary_words_min=40` the grammar physically cannot stop before ~35-40 words, so the decoder was a padding machine on a 100-word source and the model resolved the conflict by inventing. Hallucination caused by our own rail. | Andre |
  | 4 | `verbatim_run > 0.5` on a brief item fails it as a truncation, not a summary. 0.5 is the arithmetic ceiling that makes a 30-word ask possible at 60 source words - not a quality threshold. | Andre |
  | 5 | Compression stays recorded and unbanded. The ratio is identical for a genuine 30-word compression and the first 30 words copied; `verbatim_run` is the instrument that separates them. | Andre, upholding `evaluation.md`'s existing rejection |
  | 6 | Brevity is NOT a confidence band. Do not reuse `ConfidenceBand` - it means faithfulness, and a brief of a 100-word post can be perfectly faithful. Separate axes. | Andre |
  | 7 | The reader label is a **sentence in the summary's voice, never a badge or a coloured pill**. A badge is learned and ignored in one day; a sentence is read because it is in the text. | Reader, Jony |
  | 8 | The wording: for an abstract, "This is a summary of the paper's abstract. The full paper is a PDF." For a partial read, "We could only read the first part of this page." | Reader |
  | 9 | A note appears ONLY where a reader would be surprised without it. If most items carry a tag, every tag becomes wallpaper and the one that mattered disappears. No label on the Marginal Revolution post. | Reader |
  | 10 | The label is built from a count WE computed, never from source text. A label echoing a page's own words is a new unlabelled channel for a stranger's bytes (Rule #11). | Andre |
  | 11 | `form: abstract` is DECLARED per feed in `config/sources.json`, never detected. NBER, arXiv and SSRN are whole-feed properties a curator knows for certain. | Andre |
  | 12 | Page-level footer: "We skipped N stories today because we could not read enough of the page to summarize them fairly." Invisible restraint earns nothing; this is the only evidence a reader gets that somebody is saying no on their behalf. | Reader |
  | 13 | An abstract is the authors describing their own work. The summary says "The authors report that...", never states it as fact of the world. | Reader |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Publish the Japan Times items with a paywall warning | Hard no. The reader hits a wall and feels had; a metered wall works for some readers and not others so the rule cannot be learned; and `CLAUDE.md` section 0a already forbids paywalled sources. | Reader, Andre |
  | 2 | Publish the llama.cpp release items | The page is a list of file names. The best honest summary is "a new version came out", which is a calendar entry, not a story. | Reader - **OVERRULED by O3.** Newsworthiness is the owner's call. The signal is recorded; the item publishes. |
  | 3 | Fetch and summarize the PDF | Reverses Rule #11 - the PDF address is discovered inside a stranger's page and the sanitizer deliberately strips it. Plus a new dependency, a multi-MB download, and a 6,000-word paper truncated to its first third anyway. | Andre, Carmack |
  | 4 | A `pdf_url` payload field populated from the page body | The field IS the vulnerability. Do not mint it. If a PDF link is ever wanted it is derived by a per-source rule in config, so the address is ours. | Andre |
  | 5 | Republish the abstract as the summary | The abstract is the article body. Republishing a body is a project non-goal. It is summarized like any other source under the same verbatim cap. | Andre |
  | 6 | Labels "Short source", "Brief", "Limited source text" | "Brief" is the worst - it promises a fast read and hides what is missing. The others are jargon or an apology about our pipeline printed on the reader's page. | Reader |
  | 7 | Drop the floor without the paywall guard | Admits the two metered stubs and publishes paywalled content. Same commit or not at all. | Andre |

---

## Row #9 - Prompt reorder for prefix reuse

- **Scope:** Move every band-varying number to the tail of the system prompt so the shared prefix grows from roughly a third to nearly all of it. Gated on row 3's measurement.
- **Files touched:**
  - `backend/idhazh/prompts/summarize.txt`, `backend/idhazh/summarize.py`
  - `backend/idhazh/cli.py` (sort each shard's items by band)
  - `.github/workflows/digest.yml` (drop `--no-warmup`; start the server before `pip install`)
  - `docs/reference/measurements.md`, `docs/architecture/summarize/prompt.md`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`; the golden set (n=20) re-run.
- **Oracle:** `p0` from `kv cache rm` rises to ~the full system prompt on items 2..N of a shard, AND **no `output_digest` flips on the golden set**. A digest flip is an ESCALATE trigger.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Do nothing until row 3 reports. If the prefix is already reused, this row closes as COLLAPSED with a recorded number. | Carmack, Rule #10 |
  | 2 | The prize, if it is being re-prefilled: 801 tok / 12.1 tok/s = 66.2 s per item; 13 recoverable items = 14.4 min of CPU, ~4.4 min of wall clock per shard, ~17% off a 25-minute run. | Carmack, from F9 |
  | 3 | Sort each shard's items by band before the loop. Free, no config, no runtime cost, and independent of the reorder. Items are content-addressed and independent, so ordering changes nothing about correctness. | Carmack |
  | 4 | Drop `--no-warmup` AND start llama-server before `pip install`, so the 4.68 GiB faults in behind a network-bound step. Poll `/health` immediately before the work step instead of immediately after start. | Carmack |
  | 5 | Watch `determinism_violation`. Prefix reuse changes batch composition, and float accumulation in llama.cpp is not guaranteed bit-identical across batch shapes. The alarm already exists. | Andre |
  | 6 | A richer system prompt is NOT free. Only prefill of the invariant prefix is amortized. Decode, KV context budget and attention dilution are not - every one of up to 900 output tokens attends over all 801 system tokens on every item. | Andre, Carmack |
  | 7 | Anyone proposing to add prompt tokens on the grounds that "the cache pays for it" owes an eval delta on the golden set, not a cache-hit rate. A cache measurement reports a quality regression as a success. | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | The joke warmup request | Warms the wrong thing. A joke shares ZERO token prefix with the system prompt; prefix reuse is a token-id match, not a "model feels warm" state. It also burns decode, the most expensive token type on this hardware. | Andre, Carmack |
  | 2 | Any warmup hidden behind article fetching | The premise does not exist: `stage_work` interleaves fetch/extract/summarize per item, there is no bulk fetch phase. And fetches are 0.45-0.80 s - you cannot hide 66 s behind 4 s. | Carmack |
  | 3 | A correctly-written prefix warm request | Costs 66.2 s and saves the first item exactly 66.2 s. Net zero. | Carmack |
  | 4 | `--keep N` | Governs context-shift survival during long generation. Irrelevant at 4201 of 8192 with no shift. | Carmack |
  | 5 | More shards | The tail is already at its floor - you cannot split an item. 8 shards adds ~624 s of duplicated fixed cost to shave a tail bounded below by one article, and doubles the cold prefills. | Carmack |
  | 6 | A shared llama-server across shards | Four jobs, four processes, four caches is the shard model working. Sharing one serialises the run. | Carmack |

---

## Row #10 - Console: an interactive time viewport over the census

- **Scope:** A published telemetry series the browser fetches, and a console that lets the reader pan and zoom a time window over it. Failure panels, failure list, compression scatter.
- **Files touched:**
  - `frontend/package.json`, `frontend/package-lock.json`
  - `frontend/src/lib/charts/{series,viewport}.ts`
  - `frontend/src/lib/components/{FailurePanels,FailureList,CompressionScatter,Viewport}.svelte`
  - `frontend/src/routes/console/+page.server.ts`, `+page.svelte`
  - `backend/idhazh/publish_telemetry.py`
  - `frontend/public/telemetry/<YYYY-MM>.csv`
  - `config/idhazh.json` (`console.*`)
  - `frontend/tests/console.spec.ts`
- **Acceptance gates:** `npm run check`, `npm run build`, `pytest`, drift gate, the existing bundle gate, browser smoke per section 12 including **the page renders with the series absent** and **zero new console `[error]` or `404`**.
- **Oracle:** With the published series deleted the console still renders every frame, axis and an honest empty line. With it present, panning to a month with no runs shows a gap rather than interpolated data. Keyboard alone can pan and zoom.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **The chart is interactive and client-side.** JS fetches the published series and the reader pans and zooms. Rule #1 permits this on two counts after PR #7: fetching our own committed files was always allowed, and every computation still happens in the reader's browser. | **Owner override O1** |
  | 2 | **The window is a viewport, not a deletion.** Default 30 days; the reader scrolls back through everything published. The ledger stays append-only. | **Owner override O2** |
  | 3 | **Today is not pinned to an edge.** `console.default_window_days` and `console.today_anchor` (`right` \| `centre`) are `config/` knobs. With less than a window of history the view fits what exists instead of drawing empty space. | Owner, O2 |
  | 4 | **Library: `uplot`.** ~47 KB minified / ~18 KB gzipped, MIT, zero dependencies, purpose-built for time series, with pan and zoom in the box. It is the smallest thing that clears the bar O1 sets. | Owner O1 + section 8 |
  | 5 | **The library is self-hosted from `node_modules`, not a CDN.** Rule #1 now permits either, and section 8 decides: at ~18 KB gzipped a third-party request costs more in DNS, TLS and a privacy question than the bytes are worth. Bundling also keeps the existing bundle gate meaningful. | Section 8 |
  | 6 | **uPlot renders to canvas, so the theme must be passed in, not inherited.** Read `tokens.css` custom properties via `getComputedStyle` at mount and on a theme change, and hand uPlot the resolved colours. This is the one real cost of the canvas choice and it is named here so nobody rediscovers it. | Jony's theming objection, carried forward |
  | 7 | **The 30-day default view is also server-rendered as static SVG**, so the page is correct before JS runs and correct if it never does. Pan and zoom are the enhancement. Section 12 requires the page to render with its data absent; this is how both survive. | Jony, preserved under O1 |
  | 8 | **The browser reads a PUBLISHED projection, never `state/` raw.** `publish_telemetry.py` writes `frontend/public/telemetry/<YYYY-MM>.csv` carrying `date, run_id, item_id, vertical, source_id, stage, outcome, code, source_words, summary_words`. It drops `canonical_url`, `url_key` and `detail` - roughly halving the bytes and keeping untrusted free text off the published surface entirely. | Fowler, Rule #11 |
  | 9 | **Monthly shards, fetched on demand.** ~15.6 KB/month at 4 runs a day. The page loads the current month and fetches an older one only when the reader pans into it. A year of history is 12 small requests, never one large one. Yearly shards are rejected: ~190 KB in one blob to draw 30 days. | Carmack's sizing, owner's sharding ask |
  | 10 | A month that 404s or fails to parse degrades to a gap and logs to the browser console. It never white-screens the page. | Section 12, degrade-do-not-fail |
  | 11 | Bars not lines; small multiples for the three categories; rate primary with the raw pair in the label; outlined bars below `console.min_attempts_for_rate`; one ink, colour only for a floor breach. Jony's Q2/Q3 rulings survive - they were about honesty, not about where the geometry runs. | Jony |
  | 12 | The compression view keeps its form: x = source words (log), y = summary words, the `config.summarize.bands` step function as a reference band, `truncation_flagged` as a shape. Zoom now applies to it too. | Jony |
  | 13 | Keyboard and touch are first-class: arrow keys pan, `+`/`-` zoom, the viewport control is a labelled focusable element with a visible focus ring. Basic ARIA and keyboard nav are in scope (`CLAUDE.md` section 0a). | Jony, section 0a |
  | 14 | The failure LIST is what a panel click filters. After a spike an operator wants which items failed and why - rows, not a bigger chart. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Build-time only, no interaction | The owner requires pan and zoom, and the amended Rule #1 permits it. | O1 |
  | 2 | Hand-authored SVG with a bespoke pan/zoom | This was Jony's ruling and it was right for a static chart. Interaction is where hand-rolling stops paying: pointer capture, wheel semantics, touch pinch, hit-testing and axis re-ticking are the library's actual value. | O1, section 8 |
  | 3 | **Chart.js + zoom plugin** | ~70 KB plus a plugin for the same job uPlot does in 18 KB, and its time-series performance is worse at every point count. | Section 8 |
  | 4 | **ECharts / Highcharts** | ECharts is several hundred KB. Highcharts is not free for commercial use. | Section 8 |
  | 5 | **LayerChart / LayerCake** | Svelte-native and SVG, so it would theme from `tokens.css` directly - the one place it beats uPlot. Rejected on weight and on churn: it is a composition kit whose interaction story we would still assemble ourselves. Reconsider only if the `getComputedStyle` theming in decision 6 proves fragile. | Section 8 |
  | 6 | **Observable Plot** | No built-in pan or zoom; we would write the interaction anyway, on top of a heavier base. | Section 8 |
  | 7 | **d3 (scale + shape + zoom)** | The closest technical fit and roughly uPlot's size once `d3-zoom` is in. Rejected because it is a toolkit, not a chart: we would write and maintain the renderer, which is the part uPlot has already debugged. | Section 8 |
  | 8 | A CDN copy of the library | Rule #1 now permits it, section 8 does not: 18 KB does not justify a third-party request and its privacy question, and it would blind the bundle gate. | Section 8 |
  | 9 | Serve `state/item-health/` directly | It carries `canonical_url` and untrusted `detail`. Publish a narrow projection instead. | Fowler, Rule #11 |
  | 10 | One file for all history | Grows without bound in a single request. | Carmack |
  | 11 | One file per day | 30 requests to draw the default view. | Carmack |
  | 12 | Client-side rendering only, no SSR fallback | A page blank until JS runs fails section 12. | Jony |
  | 13 | Dual y axes, log scale, stacked area, normalized share | Each distorts: an axis-dependent crossing point; `log(0)` undefined on the most common day; a false baseline; and a view where 1 failure and 30 both read as 100%. | Jony |
  | 14 | Deleting rows outside the window | Never asked for, and it deletes the answer to next year's question. | O2, Fowler |

---

## Row #11 - Source yield rubric (recorded only)

- **Scope:** Compute `yield_rate` and `robots_share` per source and surface them. **Nothing reads them to change behaviour.**
- **Files touched:**
  - `backend/idhazh/contracts/app_config.py` (`sources.*` knobs)
  - `backend/idhazh/discover.py`
  - `frontend/src/routes/console/*`
  - `docs/architecture/sources/health.md`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate, browser smoke.
- **Oracle:** A source whose every row is `robots_denied` reports yield **not applicable**, never 0%. A source with fewer than `min_attempts` countable rows reports "not measurable", never a percentage.
- **BLOCKED:** Do not start until `state/item-health/` holds 30 days of rows. Writing the rule first means inventing the evidence - the mistake `health.md`'s own rationale names.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The feed half is built and correct. Do not touch it. A second quarantine mechanism beside it would be two answers to one question. | Fowler |
  | 2 | The gap it cannot see: a feed can answer 200 with 20 entries every run while every article fails to extract. `FeedHealthRow` reports healthy - correctly. The feed works; the site is not extractable. That is the 2026-08-23 shape. | Fowler |
  | 3 | Nine of fifteen codes are excluded from BOTH numerator and denominator. Robots codes leave the fraction entirely - in it as a failure we demote a site for behaving correctly; in it as a success we inflate a broken one. | Fowler |
  | 4 | Our own failures (`not_attempted`, `model_unreachable`, `output_truncated`, `bad_shape`, `length_out_of_range`, `blocked_address`, `http_rate_limited`) never count against a publisher. Charging a source for our runner dying is the fastest way to retire a good source. | Fowler |
  | 5 | **Thresholds ship as ESTIMATES labelled as such in the field description, and nothing reads them for 30 days.** Rule #10 forbids naming a threshold off ten rows. Precedent: `evidential_density` shipped recorded-only for the same reason. | Fowler |
  | 6 | The rule that makes a bad afternoon survivable: **a source is not measurable until it has `min_attempts` countable rows.** Three attempts and three failures is not a broken source; it is three attempts. | Fowler |
  | 7 | The rule against retrying a dead source forever: **retirement escalates to a human on a clock, never happens by itself.** Quarantined `retire_after_days` with zero successes -> a console line and ONE CI issue naming the set. | Fowler |
  | 8 | `degraded` lowers the ranking weight and nothing else. It does not skip the feed and never touches `config/sources.json`. A health multiplier applies at read time on top of the curator's weight. | Fowler |
  | 9 | A source with `robots_share = 1.0` gets its own console line - "this source has asked us not to read it". That is a retirement recommendation, not a health problem. A human acts. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A run that edits `config/sources.json` | A robot deleting sources a person curated, in a commit nobody reviewed. | Fowler, existing `health.md` |
  | 2 | Naming thresholds now | Ten rows in the ledger. Any number is an estimate, and an unmeasured number may not justify a design. | Fowler, Rule #10 |
  | 3 | Replacing the self-lifting rest with permanent deletion | The rest already caps cost at one request per cycle. What is missing is visibility, not a stronger deletion. | Fowler |
  | 4 | Counting robots refusals in the yield fraction | Demotes a site for behaving exactly as it asked to be treated. | Fowler |

---

## Row #12 - Docs

- **Scope:** Every page this plan moves, routed per `docs/reference/documentation-structure.md`. **Mandatory, not optional.**
- **Files touched:**

  | Doc | Change |
  | --- | --- |
  | `docs/concepts/telemetry.md` | The census ledger as the item-level record; the `FailureCode` vocabulary; restate that a log is evidence and the ledger is the record. |
  | `docs/architecture/sources/item-health.md` (NEW) | The row, the codes, the invariants, the monthly shard, what counts against a source. Sibling to `health.md`. |
  | `docs/architecture/sources/health.md` | Cross-link to item-health; name the gap feed health cannot see. |
  | `docs/architecture/sources/trust-boundary.md` | The prose-shape gate, the paywall discriminator, and that `detail` is ours by construction. |
  | `docs/architecture/summarize/prompt.md` | The brief band; the reordered prompt and WHY (prefix reuse); that the decoder rail derives from the new gate floor. |
  | `docs/concepts/digest.md` | The brief item; the note is a sentence not a badge; the note appears only where a reader would be surprised; the skipped-today footer. |
  | `docs/concepts/evaluation.md` | `verbatim_run > 0.5` fails a brief item; compression stays recorded and unbanded; the gate floor moves to 25. |
  | `docs/concepts/config.md` | Every new knob: `min_source_words` derivation, brief band, `console.min_attempts_for_rate`, `sources.*`. |
  | `docs/concepts/design-system.md` | Amend line 60 in place: hand-written markup still holds, and now says why an axis does not need a library. |
  | `docs/architecture/publishing/frontend.md` | The console's views, the published telemetry projection, the viewport, and the client-side data path. |
  | `docs/concepts/design-system.md` | Amend the "hand-written markup" line in place: it held for a static chart and stops holding once the view is interactive. Record `uplot` and why canvas forces the theme to be passed in. |
  | `docs/architecture/publishing/telemetry-series.md` (NEW) | The published projection: which columns cross to the browser, which never do, and the monthly shard. |
  | `docs/reference/measurements.md` | Row 3's cache numbers; row 7's disposition baseline (4/7 and 0/7) and result; row 9's before/after; row 13's flag sweep; the row 15 header-drift evidence. All with hardware, date, spread. |
  | `docs/how-to/run-the-pipeline.md` | How to read a failure from the census instead of a 24-hour artifact. |
  | `docs/how-to/execute-a-plan.md`, `docs/how-to/ship-a-pr.md` | Row 14: dispatch does not wait on CI; only the merge serialises. |
  | `docs/concepts/evaluation.md` | Row 19: a failed counterweight caps the band at `medium`. Plus `verbatim_run > 0.5` fails a brief item; compression stays recorded and unbanded; the gate floor moves to 25. |

- **Acceptance gates:** ASCII-only; every doc has H1, `Last Updated`, and "See also"; depth <= 3; no concept defined twice.
- **Oracle:** Every decision in rows 1-11 is discoverable from `docs/` alone, without reading this plan. A decision that exists only here has not landed.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Rationale lives as `## Design rationale` / `## Rejected alternatives` ON the page it impacts. No ADR file, no `decisions/` directory. | `CLAUDE.md` section 5 |
  | 2 | `item-health.md` is a new subsystem doc, not a section of `health.md`. Feed health and item health are different grains with different denominators. | Fowler |
  | 3 | Docs land WITH their row where the row is small enough, and this row sweeps whatever remains. A docs-only PR is a code smell. | `CLAUDE.md` section 5 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Fold item-health into `health.md` | One page defining two different denominators is how a reader comes to believe a feed metric is an article metric. | Fowler |
  | 2 | Defer docs to a follow-up | Section 9 makes canonical docs part of Definition of Done. | `CLAUDE.md` |

---
## Row #13 - llama-server runtime sweep

- **Scope:** Measure every llama-server flag we do not set, on the runner, and adopt the ones that pay. The goal is wall-clock.
- **Files touched:**
  - `.github/workflows/measure.yml` (a `runtime` job)
  - `backend/idhazh/llm/server.py` (`server_argv`)
  - `backend/idhazh/contracts/app_config.py` (`InferenceConfig`)
  - `config/idhazh.json`
  - `docs/reference/measurements.md`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate. Every adopted flag lands in `measurements.md` with hardware, date and spread.
- **Oracle:** Wall-clock of a fixed 5-article shard, 3 repeats, one flag changed at a time from a pinned baseline. A flag is adopted only if it beats the baseline outside the spread **and** the golden set's `output_digest` values are unchanged.
- **Current argv (verified 2026-08-23):** `--model --alias --ctx-size 8192 --batch-size 512 --ubatch-size 512 --threads 4 --port 8080 --no-warmup`
- **The sweep, in priority order:**

  | # | Flag | Hypothesis | Risk |
  | --- | --- | --- | --- |
  | 1 | `-np 1` | Pin one slot. Default `-1` is auto, and llama.cpp **divides `n_ctx` across slots** - auto may be giving each sequence 4096 or 2048 against a measured 4201-token worst case. Also guarantees every request lands in the slot that holds the prefix. | **Possibly a live truncation bug, not an optimization.** Row 3 reads `n_ctx_per_seq` first. |
  | 2 | `-b 2048` | We set `--batch-size 512`; the llama.cpp default is **2048**. A smaller logical batch can throttle prefill, and prefill is where the 801-token prompt and the 2500-token article are paid. We may be hand-braking the phase we are trying to speed up. | Peak memory. Measure RSS. |
  | 3 | drop `--no-warmup` | Faults 4.68 GiB in at startup instead of inside the first request. Pairs with row 9's step reorder so it happens behind `pip install`. | None. The cost is paid either way. |
  | 4 | `-fa on` | Flash attention is `auto` today. Assert it and measure; if the CPU build declines it, the log says so and the row records that. | A different attention path - check `output_digest`. |
  | 5 | `-lm mmap+mlock` | Keeps weights resident on a 16 GB runner also holding the scorer. Prevents a page-out that shows up as one mysteriously slow item. `--mlock` and `--no-mmap` are deprecated in favour of `--load-mode`. | 4.68 GiB pinned; measure against the scorer's footprint. |
  | 6 | `-ctk q8_0 -ctv q8_0` | Halves KV memory, which is what buys headroom for #7. | **Quantised KV changes the numbers.** Digest-identical on the golden set or it is rejected outright. |
  | 7 | `-np 2` with two in-flight requests | Continuous batching is already on. Two concurrent requests may raise aggregate throughput if one cannot saturate 4 threads. Needs `-c 16384` to keep 8192 per sequence, hence #6. | Changes batch composition -> the determinism alarm. Raises peak RSS. |
  | 8 | `--prio 2`, `--poll 100` | Priority and busy-polling once `pip install` is done competing. | Burns CPU during any overlap; measure with the row 9 reorder in place. |
  | 9 | `-tb N` | Separate thread count for prefill; defaults to `--threads`. Only interesting if #2 shows prefill is the bottleneck. | None. |

- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One flag at a time against a pinned baseline, 3 repeats, wall-clock of a fixed shard. A sweep that changes two things measures neither. | Carmack, Rule #10 |
  | 2 | Every flag becomes an `InferenceConfig` field, never a literal in the workflow. `server_argv` already builds the process from config **and is a fingerprint input** - a flag added outside it silently breaks the determinism stamp. | Rule #6; `llm/server.py` docstring |
  | 3 | Adoption requires the golden set's `output_digest` unchanged. A faster run that quietly changed the summaries is a regression. | Andre |
  | 4 | `-np 1` is investigated as a **suspected defect first**, an optimization second. | Carmack |
  | 5 | A warm request is permitted as a measured candidate, but it must carry the **exact rendered system prompt** of the first item's band with `max_tokens: 1` - never a joke, never real output. Andre and Carmack both showed arbitrary text shares zero token prefix and warms nothing that matters. | Andre, Carmack, owner's speed goal |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Adopt the flags without measuring | An unmeasured number may not justify a design, and several interact: `-np` with `-c`, `-ctk` with RSS. | Rule #10 |
  | 2 | `--numa distribute` | A 4 vCPU cloud runner is one NUMA node, and the flag's own docs want a page-cache drop to mean anything. | Carmack |
  | 3 | A joke or arbitrary-text warm request | Zero shared token prefix with the system prompt. It warms weights, which dropping `--no-warmup` does for free. | Andre, Carmack |
  | 4 | Raising `--ctx-size` | Worst case is 4201 of 8192. No pressure, and a larger context costs KV on every request. | Carmack |
  | 5 | Speculative decoding (`--spec-*`) | Needs a second model resident beside a 4.68 GiB model and the scorer, in 16 GB. Out until #1-#9 are exhausted. | Carmack |

---

## Row #14 - Stop serialising on CI

- **Scope:** The process docs stop telling an orchestrator to idle on a green tick. Parallel dispatch becomes the documented default.
- **Files touched:**
  - `docs/how-to/execute-a-plan.md`
  - `docs/how-to/ship-a-pr.md`
  - `docs/agents/bootstrap.md`
  - `AGENTS.md`
- **Acceptance gates:** ASCII-only; the docs stay domain-neutral per section 5; no rule restated that `CLAUDE.md` already owns.
- **Oracle:** An orchestrator following the doc dispatches the next independent row while the previous row's checks are still running, and still never merges a red or stale branch.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **Waiting on CI is not a dependency.** A row whose `Depends-on` is satisfied dispatches immediately, even with a sibling's checks in flight. Measured 2026-08-23: `ci` about 2 min, `site` about 2 min, `pages` about 50 s, a `digest` run 25 min. Serialising on a tick spends more wall-clock idle than working. | Owner |
  | 2 | **Parallelise the work, serialise only the merge.** `execute-a-plan.md` already says this for the merge; the amendment makes explicit that the *dispatch* of the next row does not wait either. The merge queue stays one-at-a-time and still re-checks each branch against the advanced `main`. | Owner |
  | 3 | Green gates remain mandatory **before merge**. This changes when an agent waits, never whether the gate is honoured. | Section 9 |
  | 4 | Worktree isolation is what makes it safe: two rows in flight never share a checkout. Already the documented topology. | Fowler |
  | 5 | The publish stage is named as the long pole so nobody re-introduces a wait on it. | Owner |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Merge without waiting for checks | Section 9 requires green gates at merge. Stop idling, not checking. | `CLAUDE.md` |
  | 2 | Restate the rule in `AGENTS.md` in full | `AGENTS.md` is derived, not authoritative. It gets a pointer. | Section 5 |
  | 3 | Skip `pages` on every PR | It is the deploy gate; a docs PR that breaks the build must fail somewhere. | Owner |

---

## Row #15 - Repair the ledger header, and stop it drifting again

- **Scope:** Fix the committed `state/scores.csv` header and give `ledger._append` the guard `evals/writer.append` already has. **This defect is live, not theoretical.**
- **Files touched:**
  - `state/scores.csv`
  - `backend/idhazh/ledger.py`, `backend/idhazh/evals/writer.py`
  - `backend/tests/test_ledger.py`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`; a parse of every committed `state/*.csv` asserting header width equals row width.
- **Oracle:** Every row in every committed `state/` CSV has exactly as many cells as its header names. A contract with a new column must **raise** on append against a stale header, not write a wider row.
- **Evidence (measured 2026-08-23, during the PR #1 merge):**

  | Stage | Header cols | Row widths |
  | --- | --- | --- |
  | `main` before the merge | 30 | **30 x 10, 31 x 9** |

  The 9 wide rows carry `score_ms` (values 2057-18656 ms). The contract gained the field, the committed header was never migrated, and nothing refused the write. `payload.ts:readCsv` maps by header position, so every cell after the insertion point reads under the wrong name. Repaired by hand during the merge; the guard is what stops it recurring.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One guard, shared by both writers - Move Function, not a second implementation. | Fowler |
  | 2 | The repair migrates the header and pads historical rows with the contract's own defaults: `0` for `score_ms`, null for both densities. **Null, not zero** - a row written before a column existed measured nothing, and that is different from measuring zero. | Fowler, `eval_row.py`'s own changelog |
  | 3 | A CI check parses every committed `state/` CSV and asserts header width equals row width. The guard protects the writer; this protects the file. | Fowler |
  | 4 | This row supersedes row 1's scope where they overlap; row 1 stays as the pure Move Function so the repair is reviewable on its own. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Drop the 9 wide rows | They are good data - the first eval rows automation ever wrote. The header was wrong, not the rows. | Fowler |
  | 2 | Widen the header and leave the older rows short | A short row and a wide row under one header is the same defect from the other end. | Fowler |
  | 3 | Tolerate a mismatch and pad on read | `payload.ts` maps by position. Padding on read writes wrong data under right names. | Fowler |

---

## Row #16 - A dead model server says so

- **Scope:** Stop reporting infrastructure failure as a model failure.
- **Files touched:**
  - `backend/idhazh/cli.py`, `backend/idhazh/summarize.py`
  - `backend/idhazh/contracts/item_health.py`
  - `backend/tests/test_pipeline.py`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate.
- **Oracle:** With no llama-server listening, every item's row carries `model_unreachable` - never `bad_shape`, never a `JSONDecodeError` detail.
- **Evidence:** `cli.py` catches `OSError` from the model server, substitutes `Completion(content="")`, and lets it fall through to `parse_draft`, which fails with `JSONDecodeError`. The recorded reason blames the model for a server that was never up.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Mark the transport failure where it happens rather than inferring it downstream. An empty completion is not a model output. | Fowler |
  | 2 | `model_unreachable` never counts against a source (row 11's countable set). Charging a publisher for our dead server is how a good source gets retired. | Fowler |
  | 3 | Blocks row 5's oracle: the classifier cannot reach every `FailureCode` from a fixture until this path is marked. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Fail the shard when the server is down | A run that publishes nothing on a bad day makes its bad days invisible. Degrade and record. | `pipeline-loop.md` |
  | 2 | Infer it from the detail string | Free text is not a signal. That is the whole argument of row 2. | Fowler |

---

## Row #17 - Per-request timeout sized from an item

- **Scope:** `_summarize_one` currently passes the whole shard budget as one request's timeout.
- **Files touched:**
  - `backend/idhazh/cli.py`
  - `backend/idhazh/contracts/app_config.py`
  - `config/idhazh.json`
  - `backend/tests/test_pipeline.py`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`, drift gate.
- **Oracle:** One hung request costs one item, not the shard. A fixture whose request never returns yields a `model_unreachable` row and the shard finishes its remaining items.
- **Evidence:** `timeout=shard_timeout_minutes * 60` - 150 minutes for a single POST.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Size it from the worst measured item: 597 s of decode plus a 66 s cold prefix, doubled - about 22 minutes. `inference.request_timeout_minutes`, a `config/` knob. | Carmack |
  | 2 | A per-request budget is not a shard budget. The shard timeout stays as the outer bound. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Leave it | One hung request silently eats the whole shard and the day loses 4-5 items with no recorded cause. | Carmack |
  | 2 | A tight timeout from the median | The corpus standard deviation is roughly its mean. A median-sized budget kills the long articles that most need summarizing. | Carmack |

---

## Row #18 - Fold `/evals` into `/console`

- **Scope:** One route answers "how is the pipeline doing", not two.
- **Files touched:**
  - `frontend/src/routes/evals/`, `frontend/src/routes/console/`
  - `frontend/tests/`
- **Acceptance gates:** `npm run check`, `npm run build`, browser smoke, and the old path still resolves.
- **Oracle:** `/evals` continues to resolve for anyone who bookmarked it; the per-day band counts appear exactly once in the codebase.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `/evals` redirects to `/console`. The published dashboard keeps the route per `CLAUDE.md` section 3; the duplicate rendering goes. | Jony, owner's defect 3 |
  | 2 | Fold before adding. Row 10 adds three views; doing it while two routes render the same counts would triple the duplication. | Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Delete `/evals` outright | Section 3 says the dashboard keeps the route. A redirect honours that and still removes the duplicate. | `CLAUDE.md` section 3 |
  | 2 | Keep both and diverge them | Two surfaces answering one question is how they come to disagree. | Jony |

---

## Row #19 - The band reads its own counterweights

- **Scope:** `lead_coverage` and `hedge_dropped` are measured, written to the eval row, and never reach the band a reader sees.
- **Files touched:**
  - `backend/idhazh/evals/score.py`, `backend/idhazh/cli.py`
  - `docs/concepts/evaluation.md`
  - `backend/tests/test_evals.py`
- **Acceptance gates:** `pytest`, `ruff`, `mypy --strict`; re-band the 19 committed rows and record what moves.
- **Oracle:** An item with `lead_coverage = 0.00` cannot publish as `high`. Evidence: `ai-03` did.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `band()` and `counterweight_band()` collapse into one function. Two band functions where only one is called is how the counterweights got orphaned. | Fowler |
  | 2 | **A failed counterweight caps the band at `medium`; it does not force `low`.** A faithful summary that missed the lead is worth less confidence, not no confidence. | Owner's known-defects open question, resolved |
  | 3 | The threshold re-cut this exposes (all 19 rows band `high`) stays in the owner's known-defects doc as Level 5. Capping is a bug fix; re-cutting the bands is a design consultation. | `CLAUDE.md` section 6 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Let a counterweight force `low` | Overcorrects: it would band a good summary of a badly-extracted page as untrustworthy, when the extraction is what failed. | Owner |
  | 2 | Fix the saturated thresholds in the same row | Level 5, and it needs more than 19 rows. Different decision, different clock. | Rule #10 |

---

## Row #20 - Two frontend defects

- **Scope:** `EmptyDay` points at a notice that is not on the page; the home page bakes the build date and calls it today.
- **Files touched:**
  - `frontend/src/lib/components/EmptyDay.svelte`
  - `frontend/src/routes/+page.server.ts`
  - `frontend/tests/`
- **Acceptance gates:** `npm run check`, `npm run build`, browser smoke.
- **Oracle:** `EmptyDay` names only things a reader can see. The home page's "today" comes from the payload's own date, so a stale deploy cannot claim to be current.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The date a reader sees is the date the payload carries, never the build's clock. A site rebuilt on Tuesday must not tell a reader that Monday's digest is Tuesday's. | Owner's known-defects 5 |
  | 2 | Both are Level 1-2 and land together because they are the same class: a surface asserting something it cannot know. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Compute "today" in the browser | Then the page differs by the reader's timezone and disagrees with the payload it is rendering. | Owner |

---

## Defects recorded but deliberately not fixed here

| # | Defect | Where | Why not here |
| --- | --- | --- | --- |
| 1 | shard_of() is round-robin over plan position, and its docstring claims it spreads article lengths evenly. It cannot - length is unknown until extraction. Balancing by predicted cost means moving extraction into the `plan` job. | `cli.py` | That is a contract change to where the trust boundary is crossed. Level 4-5, its own consultation. |
| 2 | `SummaryStatus.SKIPPED` has no writer, so `RunRecord.items_skipped` is structurally 0. | `summarize.py` | Either wire it or delete the member. A one-line grep decides, and it is not this plan's question. |
| 3 | The faithfulness bands are saturated - all 19 committed rows band `high`, observed 0.923-0.978 against a 0.80 floor. | `config/idhazh.json` | Level 5: the thresholds are a reader-facing promise. It also needs more rows. Tracked in the owner's [20260823-known-defects-plan.md](20260823-known-defects-plan.md). |

Row 19 fixes the counterweight half of #3 - a summary with zero lead coverage can no longer publish as `high` - without touching the thresholds.

---

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 3; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.
