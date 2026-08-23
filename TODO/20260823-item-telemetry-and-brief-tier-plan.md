# Item telemetry, short sources, and an honest console - plan

**Last Updated**: 2026-08-23
**Level**: 4 (structural, multi-file, crosses `backend/`, `state/`, `schemas/`, `frontend/`, `config/`)

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The run of 2026-08-23 published 8 of 17 items, recorded the cause of none of them, and destroyed the evidence in 24 hours. Diagnosing it needed an expiring artifact and 9 URLs re-fetched by hand. |
| Hard scope - in | A per-item-per-run census ledger under `state/`; a stable failure-code enum; the extraction floor moved off length onto shape; a labelled brief tier for short sources; a paywall discriminator; the console's failure and compression views; prompt-cache measurement; the docs for all of it. |
| Hard scope - out | Retiring or demoting any source by rule (blocked on 30 days of rows, Holy Law #10); PDF text extraction; a charting library; a hosted log sink; changing `EvalRow`'s meaning; the saturated faithfulness thresholds; `SummaryStatus.SKIPPED`. |
| ESCALATE triggers | (1) Any proposal to serve `state/` to a reader. (2) Any threshold in row 11 being read by ranking before 30 days of rows exist. (3) A `determinism_violation` appearing after the prompt reorder in row 9. (4) Any move to publish a metered or paywalled source - `CLAUDE.md` section 0a forbids it and row 5 enforces it. (5) Adding a failure breakdown to `RunManifest`. |
| Chosen strategy | Contract, then writer, then reader, then view. The column lands before the chart; the rubric waits for the rows. Ruled jointly by Fowler (Q1, Q4) and Jony (blocking finding). |
| **Precondition** | **PRs #1 (`freshness-identity-health`) and #2 (`summarizer-evidentiality`) must merge to `main` first.** They carry `state/`, `ledger.py`, `contracts/feed_health.py`, `contracts/seen.py`, `discover.resting()` and `docs/architecture/sources/health.md`. Rows 1, 2, 5 and 11 all read or extend those. Verified 2026-08-23: `git ls-tree origin/main -- state/` is empty; both PRs are OPEN. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3.` |

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
| 10 | Console: `scale.ts`, failure panels, failure list, compression scatter | 5, 6 | E | PENDING | - | - | - |
| 11 | Source yield rubric - recorded only, reads nothing | 5 | F (BLOCKED 30 days) | PENDING | - | - | - |
| 12 | Docs: every page this plan moves | 5, 8, 9, 10 | F | PENDING | - | - | - |

Parallel groups run in order A -> B -> C -> D -> E -> F. Row 11 is additionally gated on 30 days of committed rows.

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
  | 1 | Measure before building. If the prefix is already reused, rows 3 and 9 close with a recorded number and no code. | Carmack, Holy Law #10 |
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
  | 1 | Prose-shape check: require >= 3 sentences of >= 8 words. Below that the page is a listing -> `not_prose`. This catches the GitHub release page at 51 words AND at 500. `_SENTENCE_SPLIT` already exists in `evals/metrics.py`. | Andre |
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
- **Oracle:** The 7 fixtures reach their ruled disposition: NBER x2 and Marginal Revolution publish as brief; GitHub x2 reject as `not_prose`; Japan Times x2 reject as `paywalled`. AND `verbatim_run <= 0.5` on every brief item.
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
  | 10 | The label is built from a count WE computed, never from source text. A label echoing a page's own words is a new unlabelled channel for a stranger's bytes (Holy Law #11). | Andre |
  | 11 | `form: abstract` is DECLARED per feed in `config/sources.json`, never detected. NBER, arXiv and SSRN are whole-feed properties a curator knows for certain. | Andre |
  | 12 | Page-level footer: "We skipped N stories today because we could not read enough of the page to summarize them fairly." Invisible restraint earns nothing; this is the only evidence a reader gets that somebody is saying no on their behalf. | Reader |
  | 13 | An abstract is the authors describing their own work. The summary says "The authors report that...", never states it as fact of the world. | Reader |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Publish the Japan Times items with a paywall warning | Hard no. The reader hits a wall and feels had; a metered wall works for some readers and not others so the rule cannot be learned; and `CLAUDE.md` section 0a already forbids paywalled sources. | Reader, Andre |
  | 2 | Publish the llama.cpp release items | The page is a list of file names. The best honest summary is "a new version came out", which is a calendar entry, not a story. Two on one day reads as padding. | Reader |
  | 3 | Fetch and summarize the PDF | Reverses Holy Law #11 - the PDF address is discovered inside a stranger's page and the sanitizer deliberately strips it. Plus a new dependency, a multi-MB download, and a 6,000-word paper truncated to its first third anyway. | Andre, Carmack |
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
  | 1 | Do nothing until row 3 reports. If the prefix is already reused, this row closes as COLLAPSED with a recorded number. | Carmack, Holy Law #10 |
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

## Row #10 - Console: `scale.ts`, failure panels, failure list, compression scatter

- **Scope:** Three new views over the census ledger, plus the one shared scale module they all use.
- **Files touched:**
  - `frontend/src/lib/server/scale.ts`
  - `frontend/src/lib/server/payload.ts`
  - `frontend/src/routes/console/+page.server.ts`, `+page.svelte`
  - `config/idhazh.json` (`console.min_attempts_for_rate`)
  - `frontend/tests/console.spec.ts`
- **Acceptance gates:** `npm run check`, `npm run build`, `pytest` for any config contract change, drift gate, browser smoke per section 12 including **the page renders with the ledger absent**.
- **Oracle:** Every view renders its frame, axis and an honest empty line with zero committed rows. No view white-screens on missing data.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | **No charting library.** Hand-authored SVG plus one shared `scale.ts` (`linear`, `log`, `niceTicks`, `bars`), computed in `+page.server.ts` which is never bundled for a client. 0 bytes to the browser, 0 install seconds. | Jony |
  | 2 | The current charts are poor because they have no axis, no zero, no ticks and a moving-target scale - not because there is no library. A library fixes that only by accident. | Jony |
  | 3 | **Small multiples**, not three lines on one chart. Three stacked panels, one shared x axis, each scaled to its own series with its peak printed. A vertical scan still answers "did they move together". | Jony |
  | 4 | **Bars, not lines.** A line interpolates across a day with no run and invents data. A line lies across a gap; a bar leaves a hole. Runs fail entirely, so gaps are real. | Jony |
  | 5 | **Rate is primary**, denominator `attempted = succeeded + failed`, skipped excluded. Axis label reads "share of attempted items that failed" - not "rate", not a bare "%". | Jony |
  | 6 | Every bar's label carries the raw pair, "3 of 41 attempted". A day below `console.min_attempts_for_rate` draws as an OUTLINED bar - a shape difference, not a tint. | Jony |
  | 7 | One ink for every bar. Position encodes the category, so colour has nothing left to say. When a new code joins the vocabulary the view gains a panel, not a colour negotiation. | Jony |
  | 8 | Colour appears once: a bar crossing the `100 - run.success_floor_pct` line takes `--band-low` AND a printed number. Colour is never the only signal. | Jony |
  | 9 | The compression view is a **scatter**: one dot per item, x = source words on a log axis, y = summary words linear. The reference band is drawn from `config.summarize.bands` as a step function - so **a dot outside the band is an item that missed the ask the config made of it**. | Jony |
  | 10 | `truncation_flagged` is a shape (hollow ring), not a colour. Today's items filled and larger; history faint. No trend line, ever. | Jony |
  | 11 | The failure LIST replaces drill-down charts. After a spike an operator wants which items failed and why - that is rows, not a bigger chart. | Jony |
  | 12 | Build-time aggregation to a ~30-point series baked into the page. Never serve the CSV - at 30 days it is ~510 KB, five times the entire day payload. | Carmack, Jony |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | LayerChart / Chart.js / ECharts / Highcharts | All are interaction engines. Nothing on this page is interactive and nothing can be - Holy Law #1 forbids the fetch that would feed one. Chart.js also needs a canvas: a bitmap, not selectable, not themable. | Jony |
  | 2 | d3-scale + d3-shape | Closest call. Rejected because the two things needed are a scale and a polyline - about thirty lines. `payload.ts` set this precedent in this exact situation: "Twenty lines beat a dependency for two build-time readers." | Jony |
  | 3 | vl-convert / Vega-Lite (already owned, used for digest visuals) | Would compute the rollups a second time in Python at a different moment, so the table and the picture beside it could disagree. Also bakes hex fills - a white chart on a dark console. | Jony |
  | 4 | Dual y axes | The crossing point becomes an artifact of the ranges the author picked. | Jony |
  | 5 | Log scale for failures | `log(0)` is undefined, and a zero-failure day is the good day and the most common one. **A chart that cannot draw a perfect day is the wrong chart for failures.** | Jony |
  | 6 | Stacked area | Only the bottom band has a flat baseline; a steady series riding a swinging one looks like it is swinging. | Jony |
  | 7 | Normalized share of total failures | A day with 1 failure and a day with 30 both read as 100%. Deletes the only thing the operator came for. | Jony |
  | 8 | Per-category drill-down charts | Each category holds at most thirty numbers. A page showing the same thirty numbers larger is a click that returns nothing. | Jony |
  | 9 | Box or violin per day | A day carries 4-12 items. A box plot over six points is a box drawn around six points you should have just drawn. | Jony |
  | 10 | Histogram of `compression` as primary | Discards source length, the variable that explains the ratio. 0.08 means one thing at 5000 words and another at 100. | Jony |
  | 11 | A pie of failure composition, a site-size chart, cumulative all-time totals, a mean-faithfulness trend | Three numbers already said with time attached; a line flat at zero for years; a number with no decision attached; a saturated metric that draws a flat line. | Jony |
  | 12 | A third dashboard route | `/evals` and `/console` already render per-day band counts from the same ledger. Fold one into the other before adding anything. | Jony |

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
  | 5 | **Thresholds ship as ESTIMATES labelled as such in the field description, and nothing reads them for 30 days.** Holy Law #10 forbids naming a threshold off ten rows. Precedent: `evidential_density` shipped recorded-only for the same reason. | Fowler |
  | 6 | The rule that makes a bad afternoon survivable: **a source is not measurable until it has `min_attempts` countable rows.** Three attempts and three failures is not a broken source; it is three attempts. | Fowler |
  | 7 | The rule against retrying a dead source forever: **retirement escalates to a human on a clock, never happens by itself.** Quarantined `retire_after_days` with zero successes -> a console line and ONE CI issue naming the set. | Fowler |
  | 8 | `degraded` lowers the ranking weight and nothing else. It does not skip the feed and never touches `config/sources.json`. A health multiplier applies at read time on top of the curator's weight. | Fowler |
  | 9 | A source with `robots_share = 1.0` gets its own console line - "this source has asked us not to read it". That is a retirement recommendation, not a health problem. A human acts. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | A run that edits `config/sources.json` | A robot deleting sources a person curated, in a commit nobody reviewed. | Fowler, existing `health.md` |
  | 2 | Naming thresholds now | Ten rows in the ledger. Any number is an estimate, and an unmeasured number may not justify a design. | Fowler, Holy Law #10 |
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
  | `docs/architecture/publishing/frontend.md` | The three console views and the build-time aggregation rule. |
  | `docs/reference/measurements.md` | Row 3's cache numbers; row 7's disposition baseline (4/7 and 0/7) and result; row 9's before/after. All with hardware, date, spread. |
  | `docs/how-to/run-the-pipeline.md` | How to read a failure from the census instead of a 24-hour artifact. |

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

## Known defects this plan records but does not fix

| # | Defect | Where | Disposition |
| --- | --- | --- | --- |
| 1 | `_summarize_one` passes `shard_timeout_minutes * 60` as a PER-REQUEST timeout. One hung request eats the whole shard. Size from the worst measured item (~22 min), not 150. | `cli.py` | Own row, after row 5. Carmack. |
| 2 | `--parallel` defaults to auto; llama.cpp divides `n_ctx` across slots. If auto opens 2+ slots, `n_ctx_per_seq` is 4096 or 2048 and the measured 4201-token worst case does not fit. | `digest.yml` | Row 3 measures it. If confirmed, own row immediately. Carmack. |
| 3 | `shard_of()` is round-robin over plan position and its docstring claims it spreads article lengths evenly. It cannot - length is unknown until extraction. Balancing by predicted cost requires moving extraction into `plan`, which is a contract question. | `cli.py` | Recorded. Level 4-5. Not in this plan. |
| 4 | `SummaryStatus.SKIPPED` has no writer, so `RunRecord.items_skipped` is structurally 0. | `summarize.py` | Confirm by grep, then wire or delete. Not here. |
| 5 | `to_eval_row` never calls `counterweight_band`; faithfulness thresholds are saturated (10 of 10 items band `high`, 0.923-0.978 against a 0.80 floor). | `evals/` | Pre-existing. Andre's call, not a chart's. |
| 6 | `EmptyDay` tells the reader "the run notice above says which it was". On the home page it renders with nothing above it, so the sentence points at empty space - at the moment a reader is deciding whether the site is broken. | `EmptyDay.svelte` | Level 1. Verified 2026-08-23. |
| 7 | `+page.server.ts` computes `new Date()`, and every route prerenders, so the home page bakes the build date and calls it today. A day after a deploy with no run it names a date that is not today. It also passes `latest={null}`, suppressing the one link that would rescue the reader. | `routes/+page.server.ts` | Level 2. Verified 2026-08-23. |

---

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 3; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.
