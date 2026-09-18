# Handover: the instrument is built, the slowdown is not fixed

**Last Updated**: 2026-09-16

**Level**: 3 for everything open here, except the two marked Level 5 in section 6.

You have no context. This page carries all of it. Read section 1 to know what is already done, section 3 to know what is still broken, and section 6 for the questions only the owner can answer. **Ask those questions before writing code** - three of them change what the work is.

## 0. The one paragraph that explains why this exists

A change landed on 2026-09-13 that made the pipeline five times slower an article. It ran for six days before anybody could say what had happened, because no per-item record reached an operator during a run and the published telemetry could not see the second model call at all. [`20260914-27-pipeline-observability-plan.md`](20260914-27-pipeline-observability-plan.md) built the instrument that makes the next one visible in minutes. **It deliberately did not fix the slowdown.** That is the work waiting for you.

## 1. What already landed, so you do not redo it

Sixteen rows across thirteen pull requests, all merged, `main` green.

| # | PR | What it did |
| --- | --- | --- |
| 1 | #738 | Renamed the two model calls; widened `state/item-health/` from 42 columns to 113 |
| 2 | #733 | `PlannedItem` carries the eight terms its ranking score is made of, not just the total |
| 3 | #732 | Five logging flags in `config/idhazh.json`, each carrying its removal condition |
| 4 | #742 | `work.py` emits start, stage, heartbeat, done, abandoned and shard records |
| 5 | #743 | Fetch reports connect time, time to first byte, robots time, retry count and retry time |
| 6 | #735 | A shard killed by its timeout now uploads the items it finished |
| 7 | #739 | `recovered_completion` got its caller: a reply cut in the plan half keeps its summary |
| 8 | #740, #746, #748 | `.github/workflows/idhazh-pipeline-tests.yaml` - two drawn articles, three cases, one runner |
| 9 | #750 | A page's own `<title>` is used when the feed carries no headline |
| 10 | #754 | The article title moved inside the prompt fence |
| 11 | #751 | The published telemetry mirror went 32 columns to 49; one console panel shows where an item's time went |
| 12 | #752, #755 | Every constrained string column folds its own cell; the ledger append reads one line instead of the file |
| 13 | #747 | Repaired a day file that carried two headers; `migrate_header` widens only |
| 14 | #741, #744, #753, #745, #758 | Documentation corrections, two vocabulary retirements, one test moved onto a fixture |

## 2. The measurements already taken - do not repeat these

Every number here is in force. A new measurement replaces the reading rather than sitting beside it (Guardrail #10).

| # | Quantity | Reading | Taken |
| --- | --- | --- | --- |
| 1 | Median model time an item, before | 97,879 ms | run `34745383977`, 2026-09-13, stock `ubuntu-latest` |
| 2 | Median model time an item, after | 475,890 ms - **4.9x** | run `34852763827`, 2026-09-14, same runner class |
| 3 | Median output tokens an item | 229 -> 1,158 - **5.1x** | same two runs |
| 4 | Prompt reuse, summarize-and-plan call | **98.2 percent** of 240,814 tokens | run `34852763827`, 58 two-call items |
| 5 | Prompt reuse, label call | 53.6 percent of 184,371 tokens | same |
| 6 | Model time split | label prefill 21.6, label decode 39.3, summary prefill 0.8, summary decode 38.2 percent | same, four shards |
| 7 | Between-runner spread | **4.2x** across CPU models; 17 percent of draws land on the fast part (54 of 325 rows) | ledger census, 2026-09-14 |
| 8 | Per-row contract validation | 42.85 us a row; 3.43 ms a run against 38,071 s of item work - **1 part in 11.1 million** | i7-1265U, 2026-09-15, within-run A against B, spread 22.63 |
| 9 | `state/item-health/` at the 14-month ceiling | 426 files, 170,400 rows, 72.7 MB, then **flat forever** | measured on a built tree, 2026-09-15 |
| 10 | Ledger append, header question | whole file plus scan -> **one line** | 2026-09-15; the line count is the instrument, the clock has a wider spread than the effect |
| 11 | First measurement from the test rig | 2,172,743 ms over two articles - **about 18 minutes an article** | run `34922935385`, 2026-09-15, one run, no spread, runner model not recorded |

**Numbers 1, 2 and 3 are the whole diagnosis.** 2 and 3 agree within 4 percent, so the entire slowdown is decoded-token volume at an unchanged decode rate. The model is not slower. It is writing five times as much.

**Number 4 kills the obvious theory.** Prompt caching was never broken. The summarize-and-plan call re-reads 76 fresh tokens an article and its prefill is 0.8 percent of a run's model time. The cost is decode, not prefill, and not the cache.

## 3. What is still broken

### 3.1 The slowdown itself - this is the main event

Root cause, settled: commit `e067db60` (#680, 2026-09-13) retired a small model and its job, and in doing so deleted the `run.two_calls_per_item: false` flag. The two-call sequence became unconditional. The flag's removal condition named **a plan row rather than a reading**, which is why nobody noticed it was load-bearing.

What the instrument now makes available to argue a fix against:

- the per-call decode rates, per item, in `state/item-health/`
- `stage_gap_ms` - time the named stages do not account for
- the summary-versus-picture split of the second call
- a dispatch-only rig that runs two articles in about 40 minutes instead of 200

Facts a fix will have to confront:

- The label call's median 887 output tokens is **9.2x the design's own written baseline of 96**, and that 96 came from a benchmark of three articles of which two returned empty - n=1 non-degenerate. Recorded in [`../docs/reference/benchmarks/two-call-re-read.md`](../docs/reference/benchmarks/two-call-re-read.md).
- Run-wide `charts_drafted` was **0** on run `34852763827`. The label call spent 39.3 percent of the run's model time and produced no chart.
- `keyphrases` and `lede_sentence_ids` in the label call's reply have **zero consumers** anywhere in the pipeline.
- Eight items failed `model_unreachable` structurally: the label call's 6,491-token budget cannot decode inside the 22.1-minute request timeout at 3.5 to 4.1 tokens a second.
- Runs now exceed their own four-hour cron, so the concurrency group serialises and the backlog compounds.

**Do not change an output budget, a truncation cap or the call sequence without the owner.** That is an escalation line plan 27 held throughout and it still stands.

### 3.2 The instrument writes 31 of its 113 columns

The contract declares 113 columns. `telemetry._row` names **31**. Measured on the committed archive 2026-09-15: 12,197 rows, **70 columns empty in every single row**.

Plan 27 row 5 landed the log records and the contract. The producer wiring that fills the ledger row did not land. Until it does, the spine the owner asked for is 31 columns wide.

`failed_field`, `failed_rule`, `model_quantisation`, `runner_name`, `cpu_model` and both finish reasons are filled in **zero** rows.

### 3.3 The test rig has never completed all three cases

`.github/workflows/idhazh-pipeline-tests.yaml` draws two articles from 24 in `config/pipeline-tests.json`, seeded on the run id, and runs three cases in sequence on one runner: baseline, the visual decision off, and two server slots.

Dispatch history: the first died on a file mode; the second and third produced nothing because every candidate lacked a title; the fourth ran one case and hit the job bound. **One case is about 36 minutes, so three need roughly 115.** The bound was raised to 140 to leave buffer. Nobody has dispatched it since.

Fire it with `gh workflow run idhazh-pipeline-tests.yaml --ref main`. It publishes nothing and commits nothing. The report step prints a table of case, items, summaries, model milliseconds and failures.

### 3.4 Three columns cannot be filled, and one record is unreachable

`slot_id`, `kv_tokens_at_start` and `prefix_shared_with_previous` are declared and empty because the model server does not report them on the completions route. Check whether its `/slots` endpoint does.

**Answered, and the premise was wrong.** The pinned build reports all three on the completions route the summarizer already posts to - `id_slot`, `tokens_cached` and `timings.cache_n`, at no extra request ([`docs/reference/pipeline-cost.md`](../docs/reference/pipeline-cost.md)). The row has carried them off the item's first call since 2026-09-16, so `/slots` was never needed and this heading's first sentence is history.

`item.abandoned` is wired but unreachable - the model loop cannot exit early, so the sweep over unclosed recorders is always empty. It is there so that an early exit added later says so rather than dropping items silently.

## 4. The ten tests that read committed data - closed

CLAUDE.md section 13 forbids a test that reads committed data to ask whether the data is well formed. An audit found twelve. Two were deleted by #755 once the settlement pass took over their question. **The remaining ten landed on 2026-09-15 and this section is the record of what each one became.**

**A fourth case the rule does not name, and it was the biggest group here:** a test asking a legitimate question about *code* that happens to be driven from committed data. That is not a data-hygiene check. It is a good test wired to the wrong input, and the fix was to build the input.

| # | Where | What it really asked | What it reads now |
| --- | --- | --- | --- |
| 1 | `backend/tests/test_ledger.py` - the prefill-rate oracle | does the oracle compute a rate | run `2026-08-26-5`'s 160 rows, captured under `tests/fixtures/state/prefill-oracle/`. Pools to the same 11.1755 tok/s the committed file did, so the fixture is the same evidence rather than a smaller one |
| 2 | `backend/tests/test_telemetry.py` - the item-health append | does the read-side migration work | a day file written under a header from before the truncation counters existed. The old row's `source_words_before_cap` has to migrate to empty, which the archive no longer holds an example of |
| 3 | `backend/tests/pipeline/test_eval_ledger.py` | same, for `EvalRow` | **deleted.** `test_appending_under_a_stale_header_fails_loudly` and `test_the_ledger_writes_its_header_once` already prove both halves from built files |
| 4 | `backend/tests/test_publish_telemetry.py` | same, for `PublicTelemetryRow` | **deleted.** Two built shards already prove the prefix read and the refusal. Its one unique claim, LF, moved onto a shard the test publishes |
| 5 | `backend/tests/test_measure_budgets.py` - five tests | does the sampler sample | a corpus the test writes from the committed `corpus-row` fixture, ten rows of different lengths |
| 6 | `backend/tests/contracts/test_committed_days.py` - three callers | does the validator validate | the day the seed case already proves the gate accepts whole. The default is still followed: `common.PUBLIC_ROOT` is redirected to a built tree |
| 7 | `backend/tests/workflows/test_staged_paths.py` | - | the `exists()` assertion is **deleted**. Staging `state` whole is correct whether or not the two late stores have appeared |
| 8 | `backend/tests/contracts/test_run_plan.py` - `min_feeds` | - | **moved to the producer.** `stages/plan._plan_desks` warns by name when an active desk goes silent on its floor |
| 9 | `backend/tests/test_search_index.py` - four tests | does the writer hold its bijection | a month built to carry a vector, a gap and a day with no embeddings block. The archive has never held all three at once |
| 10 | `backend/tests/test_ledger.py` - seeded stores | - | **moved to `backend/utilities/check_seeded_stores.py`**, which pytest does not collect. The path and header assertions stayed, because a code change can break those |

**Two of the same kind were left, and neither was on the audit's list.** `test_staged_paths.py::test_every_path_the_day_stages_exists_in_a_fresh_checkout` is a larger clone check that also shells out to `git ls-files`. `test_search_index.py::TestTheCommittedShard` is explicitly about the published shard agreeing with the published days, which is a reader-facing claim and wants a producer home rather than a fixture.

### The pattern still worth writing into the contract

Three of these - rows 1, 7 and the one already fixed - asserted something **production owns**: a retention roll, a store being created, a day being long enough. **None can be fired by a code change, so none was catchable in review.** They went red on a pull request that did not touch them.

CLAUDE.md section 13 already names the migration case. It does not name this one. **Proposing that sentence is still open, and it is the owner's to approve.**

## 5. Casual observations, none of them urgent

- **A mechanical rename over English prose breaks sentences where the old phrase was a verb.** #738 substituted "call one" and it took two follow-up pull requests, #744 and #745, to repair 21 sentences. Seven of them the substitution missed entirely because a line wrap had split the phrase. If you run a rename, read every sentence afterwards and grep for split lines.
- **`merge=union` plus a schema widening equals a silently stacked file.** A scheduled run on a checkout taken before a widening wrote the old shape into a file that already carried the new one. Git called the merge clean. It took `main` red and every open pull request with it. `migrate_header` now widens only and refuses to narrow, but the trigger - a run on an old checkout - cannot be removed.
- **A file mode is invisible to a YAML test, to lint and to shellcheck.** The rig's first dispatch died on exit 126 because a script shipped mode 644 and was invoked bare. There is now a test that reads `git ls-files -s`.
- **"Arm" was pre-existing jargon, not new.** 23 uses in `measure.yml` and 16 in `docs/concepts/evaluation.md` before plan 27 started. It is now retired in favour of "case".
- **The census over-reported published stories by 3.5x for a week.** The ledger recorded 46 published on 2026-09-14; the committed day holds 13. Three killed shards recorded 33 articles as published whose payloads reached no reader. Fixed in #735, but the short day is committed history and will sit in the archive for its retention - it is what took the seed-gate test red.
- **An empty headline killed a whole work shard**, and any feed entry without a title would have done it. Live in production until #748.
- **The page title reached the model unfenced** until #754, and #750 had just made that title far more attacker-controlled. One line to fix, and nobody had looked.

## 6. Questions for the owner - ask these before writing code

| # | Question | Why it is not yours to decide |
| --- | --- | --- |
| 1 | **Fix the slowdown how?** The instrument is built and the diagnosis is settled. The fix will touch an output budget, a truncation cap, or the call sequence | Section 3.1's escalation line. **Level 5** |
| 2 | **Should the label call still ask for `keyphrases` and `lede_sentence_ids`?** Zero consumers, and the call is 39.3 percent of model time | Editor rules what the digest carries |
| 3 | **Is a story with no headline dropped or published untitled?** It is dropped today. Every downstream surface already has an "Untitled item" fallback, so publishing is a one-line revert | Editor rules what runs, CLAUDE.md section 14 |
| 4 | ~~Plan the ten tests in section 4, or just execute them?~~ **Closed 2026-09-15: executed.** Section 4 is now the record of what each became | - |
| 5 | Should the published telemetry mirror move from month grain to day, to match `state/`? | The console's 90-day view is 5 fetches at month grain and up to 90 at day grain. **Level 5** - the day-sharding plan lists it as an escalation trigger |
| 6 | Is `n_parallel: 2` worth taking to production? | Unmeasured. Section 3.3's rig answers it in 140 minutes |

The owner has already ruled on these, so do not reopen them: the published mirror stays monthly for now; prompts and replies go to a 90-day artifact rather than the log; per-row validation on append is refused because a row Python writes is validated by construction; `state/` files are day-sharded and `frontend/public/` files are monthly because they answer different questions.

## 7. Traps that cost time in the session that wrote this

- **`[IO.File]::ReadAllText` with a relative path writes to the wrong worktree.** It resolves against the .NET process working directory, which `Set-Location` does not move. In a repository with eight worktrees it silently edits a different checkout and exits 0. Build the absolute path first, or use the editor's own file tools. After any scripted edit, assert the changed line COUNT, not the exit code.
- **In a rebase, `--ours` is upstream and `--theirs` is your commit.** Prove it by reading the file; do not recall it. For anything generated, never pick a stage - take upstream's file whole, re-run the exporter, and diff against `git show origin/main:<path>`.
- **`git checkout origin/main -- schemas/` resurrects a file your branch deleted.** The exporter only writes; it never prunes. `git rm` afterwards and verify.
- **pytest exit 5 means a misspelled path, not contention.** Under `-n auto` a path that does not exist reports as "no tests collected". Verify each path with `Test-Path`, or re-run once with `-n 0` for the real error.
- **Re-serialising `config/*.json` through its model ADDS default keys the committed files deliberately omit.** Rename keys in place.
- **A `gh` command's exit code decides nothing.** Ask for the count afterwards.
- **`Start-Sleep` inside a foreground terminal command gets killed when siblings are active.** Put the loop inside a detached process that writes a file, and poll the file with one-shot reads.
- **Eight agents share this machine.** Run lint, type checks and the contract export through `python backend/utilities/gate_lock.py -- <command>`. A gate log that has not changed is queued, not hung.

## 8. Where things are

`main` is green. No open pull requests from this work. Sibling agents hold worktrees named `capreport`, `dedup2`, `knobprose`, `orch`, `p29-draw`, `p29-trial` and `p31-clock` - leave those alone.

[`20260915-30-decoder-stalls-handover.md`](20260915-30-decoder-stalls-handover.md) is a different session's handover covering the decoder stall, the worker's clock and the label call's dead weight. It overlaps section 3.1 here. Read both before starting on the slowdown; `p31-clock` is already executing part of it.

## See also

- [`20260914-27-pipeline-observability-plan.md`](20260914-27-pipeline-observability-plan.md) - the plan this hands over from. Its section 13 records what execution surfaced that the plan did not predict.
- [`20260915-30-decoder-stalls-handover.md`](20260915-30-decoder-stalls-handover.md) - the overlapping handover on the decoder stall.
- [`../CLAUDE.md`](../CLAUDE.md) - the engineering contract. Sections 0a, 0b, 0c, 0d, 1, 6, 11, 13 all bind this work.
- [`../docs/agents/bootstrap.md`](../docs/agents/bootstrap.md) - which page owns what.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the environment and every gate command.
- [`../docs/architecture/sources/item-health.md`](../docs/architecture/sources/item-health.md) - the ledger this plan widened.
- [`../docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - what a read over a growing collection has to declare.
