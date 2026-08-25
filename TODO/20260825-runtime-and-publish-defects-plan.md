# Runtime observability, the publish race, and the throughput question - Plan

**Last Updated**: 2026-08-25

**Level**: 3 (highest row). No Level-5 row. Rows 6 and 11 are measurement-only.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 3; honor the ESCALATE triggers in section 0.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | An observational `-np` comparison across runs `32766098026` and `32772221068` found no throughput effect and five unrelated defects: an unnamed runtime binary, a context-full reply reported as unreachable, a push-retry loop that never retries, a false coverage claim on `server_argv`, and shard parallelism capped at 20 percent of the platform ceiling. |
| Hard scope - in | Pinning the llama.cpp build and naming it in the cache key; naming the host, binary and weights in `work`; a `CONTEXT_EXCEEDED` failure code; `--metrics`; extracting and then fixing the commit-and-push step; raising the shard ceiling; the `llama-batched-bench` gate; the conditional paired `-np` measurement; recording the observation. |
| Hard scope - out | Any change to `PipelineInputs` or anything that moves `pipeline_fingerprint`; `temperature` / `top_p` / `seed` / `thinking`; the Qwen3.5-9B swap; `run.shard_size` enforcement; a `kv_unified` config field; `-np` values above 2; prompt reordering; the faithfulness thresholds. |
| ESCALATE triggers | (1) Any edit that would move `pipeline_fingerprint` - that belongs to row 4 of `TODO/20260825-qwen35-9b-swap-plan.md`, not here. (2) Any change to a sampling knob. (3) Any `workflow_dispatch` of `digest.yml` or `measure.yml` - the user authorizes each run. (4) Row 6 reading below 1.4x - COLLAPSE row 11, do not run it. (5) Any `output_digest` moving in a measurement arm - Andre rules before Carmack. (6) Row 10 pushing cache past 10 GB, artifacts past 500 MB, or the site past 1 GB (Rule #2). |
| Chosen strategy | Observability before optimisation, and shard-level parallelism before intra-shard concurrency. Carmack ruled that `-np 2` is worth 10-30 percent on a stage that is not the constraint, while the shard cap is worth about 2x for two workflow literals. Andre ruled that no `-np` work starts before `llama-batched-bench` answers whether CPU decode batches at all. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3.` |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `server_argv` stops claiming coverage it never had | - | A | DONE #81 | yi-r01 (removed) | #81 | worker |
| 2 | Record the `-np` observation and correct the `n_parallel` guidance | - | A | DONE #84 | yi-r02 (removed) | #84 | worker |
| 3 | Pin the llama.cpp build and name it in the cache key | - | A | DONE #82 | yi-r03 (removed) | #82 | worker |
| 4 | A context-full reply stops reporting as unreachable | 1 | B | DONE #88 | yi-r04 (removed) | #88 | worker |
| 5 | The `work` job names its host, its binary and its weights | 3 | B | DONE #87 | yi-r05 (removed) | #87 | worker |
| 6 | `llama-batched-bench` decides whether `-np > 1` is alive | 2 | B | DONE #91, measured #101 | yi-r06, yi-r11 (removed) | #91, #101 | worker |
| 7 | `--metrics` is on and scraped once at job end | 4, 5 | C | DONE #95 | yi-r07 (removed) | #95 | worker |
| 8 | Extract the commit-and-push step, behaviour-neutral | 7 | D | DONE #96 | yi-r08 (removed) | #96 | worker |
| 9 | Assemble refreshes its base and regenerates | 8 | E | DONE #98 | yi-r09 (removed) | #98 | worker |
| 10 | Raise the shard ceiling from 4 to 8 and measure it | 9 | F | MEASURING #100 - run `32869125768` dispatched 2026-08-25 | yi-r10 (removed) | #100 | worker |
| 11 | CONDITIONAL - paired A-B-A `-np` measurement | 6, 7, 10 | G | COLLAPSED - row 6 read 1.055x against a 1.4x gate | - | #101 records the ruling | - |

Row 6's bench (run `32855163822`, AMD EPYC 9V74, 4 vCPU, 2026-08-25) returned
aggregate decode of 1.055x at parallel level 2 and 1.133x at level 4, both under
the 1.4x gate, with a spread of 0.022 over three repeats. ESCALATE trigger 4
fired, so row 11 is COLLAPSED and the whole `-np` line of work is cancelled
rather than deferred. `docs/reference/measurements.md` carries the number and
the ruling.

## Row #1 - `server_argv` stops claiming coverage it never had

- **Scope:** Correct the false invariant in the `server_argv` docstring and replace it with a contract-tier test that cannot drift.
- **Files touched:**
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/fingerprint.py`
  - `backend/tests/test_fingerprint.py`
  - `docs/architecture/contracts/determinism.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; full `pytest` green; contract drift gate green; no schema change expected.
- **Oracle:** Closed-world coverage. Every field of `InferenceConfig` is either a `PipelineInputs` field or a member of a named `NOT_DIGESTED` frozenset carrying its reason. Adding a tenth knob to `InferenceConfig` fails the test until someone classifies it.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The defect is the docstring at `backend/idhazh/llm/server.py` line 63, not the missing fields. `docs/architecture/contracts/determinism.md` enumerates its declared inputs and argues that an undeclared field was never claimed to be covered, so the scope statement is honest and the call-site comment is the thing that lies. | Fowler |
  | 2 | The nine uncovered knobs split five/four. `cache_type_k`, `cache_type_v`, `flash_attention`, `n_parallel` and `n_threads_batch` can move the logits; `load_mode`, `priority`, `poll` and `startup_warmup` cannot. The frozenset records that split with a one-line reason per knob. | Fowler |
  | 3 | Digesting the five is deferred to row 4 of `TODO/20260825-qwen35-9b-swap-plan.md`, which already resets every fingerprint. Doing it here spends the eval-clock reset twice and costs the banked run-days that known-defect 2 needs. | Fowler |
  | 4 | `state/fingerprints.csv` is header-only (verified 2026-08-25, 1 line, zero rows), so no read-side migration is owed by this row. | verified in-session |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Digest all nine knobs | `--prio` and `--poll` cannot move logits, so digesting them makes a throughput sweep read as a producer change and buries the signal the stamp exists to surface | Fowler |
  | 2 | Record all nine on the ledger row undigested, the way `host_cpu` is | `RunManifest.config_digests` already digests `config/idhazh.json`, so the four non-logit knobs are covered; the five logit knobs need digesting, not noting | Fowler |
  | 3 | Fix the fields and leave the docstring | The docstring is the defect that costs nothing to close and is doing the most damage - it tells the next reader not to check | Fowler |
  | 4 | Delete the docstring sentence and add nothing | Prose replaced by prose drifts again; the closed-world test is what makes the claim enforceable | Fowler |

## Row #2 - Record the `-np` observation and correct the `n_parallel` guidance

- **Scope:** Write the observational comparison into `docs/reference/measurements.md` with its own conclusion - that it had no power - and correct the config guidance that `n_parallel: null` and `n_parallel: 1` are not the same runtime.
- **Files touched:**
  - `docs/reference/measurements.md`
  - `docs/concepts/config.md`
  - `docs/architecture/summarize/throughput.md`
  - `docs/reference/agent-notes.md`
- **Acceptance gates:** ASCII-only (CLAUDE.md section 5); every number carries hardware, date and spread (Rule #10); `Last Updated` stamped on each page touched; cross-links resolve.
- **Oracle:** Parity between the recorded table and the artifacts. The per-shard figures in the new section reproduce from the eight `runtime-log-*` artifacts of runs `32766098026` and `32772221068` by dividing each job's total tokens by its total milliseconds - a ratio, not a median of ratios.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The recorded conclusion is "this comparison cannot answer the question", not "`-np 1` is free". Three hardware profiles, prefill spanning 3.4x, and an effect bounded at 18.4 percent. Written in those words so the pooled means 9.61 and 9.54 are never later quoted as a null result. | Andre |
  | 2 | The `kv_unified` flip from `'true'` to `'false'` under `-np 1` is cosmetic. At `n_seq_max = 1`, `n_ctx_seq = n_ctx` either way. Record the arithmetic so nobody re-opens it. | Andre, Carmack |
  | 3 | Output consistency was 93 percent identical within a CPU profile and 10 percent across profiles, on 93 items with byte-identical extracted input. That is a field confirmation of why `host_cpu` is recorded and never digested; link it to `docs/architecture/contracts/determinism.md`. | Andre |
  | 4 | `docs/concepts/config.md` gains one line: `n_parallel: null` yields auto slots with unified KV; any explicit value disables unified KV. Source: llama.cpp `common/arg.cpp`, `-kvu` help text, read 2026-08-25. | Carmack |
  | 5 | `docs/reference/agent-notes.md` gains the cache-key trap: `digest.yml` caches `backend/bin` under a key that names only the model file, so "fetch newest release" is dead code on a cache hit and the runtime is frozen to an unnamed binary. | Carmack |
  | 6 | The llama.cpp build id is recorded as unknown. Verified 2026-08-25: no build line appears in any of the eight `runtime-log-*` artifacts. Do not assert the two runs shared a binary. | verified in-session |
  | 7 | A docs-only PR is a smell under CLAUDE.md section 5. This row takes the exception because Rule #10 requires a measurement be recorded with hardware, date and spread, and the ruling this measurement produced is "change nothing" - there is no code change that could own it. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Record the pooled means as the headline | The difference is host assignment wearing a config label; pooling is what destroyed the signal | Andre |
  | 2 | Put the record in `docs/concepts/config.md` as a per-knob history | That page is a list of what is sweepable and already says a candidate becomes the runtime only after a runner measurement | Andre |
  | 3 | Leave it in `TODO/` | `TODO/` is a cache, not the memory (CLAUDE.md section 5) | Andre |
  | 4 | Fold the record into row 3 so the PR is not docs-only | Mixes a workflow change with a measurement record; two different review questions | Fowler |

## Row #3 - Pin the llama.cpp build and name it in the cache key

- **Scope:** Pin the llama.cpp release and verify its sha256 in `digest.yml` and `validate.yml`, and put the build id into the weights cache key so the binary stops changing silently on eviction.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `.github/workflows/validate.yml`
  - `backend/tests/test_workflows.py`
  - `docs/reference/github-actions.md`
- **Acceptance gates:** `pytest backend/tests/test_workflows.py` green; YAML parses; the pinned asset URL resolves; `sha256sum --check` present on both fetch paths; no `releases?per_page` query left in either file.
- **Oracle:** Contract parity with `measure.yml`. The three env vars (`LLAMA_CPP_BUILD`, `LLAMA_CPP_ASSET`, `LLAMA_CPP_SHA256`) and the `sha256sum --check` line in `digest.yml` and `validate.yml` are byte-equivalent in shape to `.github/workflows/measure.yml` lines 56-58 and 119, and the cache key contains `${{ env.LLAMA_CPP_BUILD }}`.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The sharper defect is the cache key, not the floating fetch. `digest.yml` line 184 keys `backend/models` and `backend/bin` on `llm-${{ env.MODEL_FILE }}-v2`, and the fetch step only runs on a miss. Production already runs a frozen, unnamed binary that changes at an unpredictable time - the instability of floating with none of the freshness. | Carmack |
  | 2 | `measure.yml` already pins `b10598` with a sha256 check while production does not. The measurement harness being reproducible and production not is backwards; copy the harness pattern rather than invent one. | Carmack |
  | 3 | The cache key bumps to a new suffix in the same commit, so the first run after merge refetches once against the pin rather than inheriting the unnamed binary. | Carmack |
  | 4 | `runtime_build="llama-server-local"` at `backend/idhazh/cli.py` line 419 stays hardcoded in this row. Replacing it with the observed build moves every fingerprint, which is ESCALATE trigger 1 and belongs to swap-plan row 4. Record the deferral in the row's PR body. | Fowler |
  | 5 | `validate.yml` is included because it carries the same unpinned fetch at lines 73-74; leaving it floating means the validation arm and production can disagree on the runtime. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep floating, add the build id to the cache key only | Ends the silent freeze but makes the runtime change on every eviction - worst of both | Carmack |
  | 2 | Keep as-is | An unnamed binary, an unnamed change date, and a fingerprint that cannot distinguish them. `-np`'s default and the reasoning-channel behaviour have both already changed underneath this project | Carmack |
  | 3 | Pin by digest of the tarball only, without the build tag | The tag is what a human bumps and reviews as a diff; a bare digest is unreadable in a PR | Carmack |

## Row #4 - A context-full reply stops reporting as unreachable

- **Scope:** Read the `HTTPError` body in the summarize path and give an exceeded context its own failure code instead of `model_unreachable`.
- **Files touched:**
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/contracts/item_health.py`
  - `schemas/item-health-row.schema.json`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_contracts.py`
  - `tests/fixtures/`
  - `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; full `pytest` green; contract drift gate regenerates `schemas/item-health-row.schema.json` byte-identical; `__changelog__` carries a `{version, change, why}` entry date-stamped today and `version` matches it (CLAUDE.md section 11); a fixture proves an item-health row written before this commit still loads.
- **Oracle:** Cause fidelity. A recorded llama.cpp 400 response body carrying `"type": "exceed_context_size_error"` produces `FailureCode.CONTEXT_EXCEEDED` on the item-health row, and a genuine connection refusal still produces `MODEL_UNREACHABLE`. Both from committed fixtures; no test touches the network (Rule #7).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The client swallows the signal today. `urllib.error.HTTPError` subclasses `OSError`, and `_summarize_one` at `backend/idhazh/cli.py` catches `OSError` and records `MODEL_UNREACHABLE`. The 400 body is never read. | Carmack, verified in-session |
  | 2 | llama.cpp maps `ERROR_TYPE_EXCEED_CONTEXT_SIZE` to HTTP 400 with `{"code": 400, "message": ..., "type": "exceed_context_size_error"}` (`tools/server/server-common.cpp`, read 2026-08-25). Match on the `type` field, not the message text. | Andre, Carmack |
  | 3 | `FailureCode` gains exactly one member. Verified 2026-08-25: the enum has no context member today. This is an additive, backwards-compatible change to a persisted contract - append a changelog entry, stamp `version`, and older payloads still validate. | Fowler |
  | 4 | Catch `HTTPError` before `OSError`, read the body once, and fall through to `MODEL_UNREACHABLE` for any non-2xx that is not a recognised context error. An unrecognised status must not become a new silent class. | Carmack |
  | 5 | `--no-context-shift` is added to the server argv in this row. A silent context shift discards the middle of the prompt and the model answers about a document it no longer holds; HHEM then scores it as a hallucination and names the wrong cause. Making it an error is the same defect class this row exists to close. | Andre |
  | 6 | `fits_context` at `backend/idhazh/summarize.py` line 203 compares against `inference.n_ctx` with no division by `n_seq_max`. It is correct today at `n_parallel: 1` and is a named precondition of row 11, not a defect this row fixes. | Andre, Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Detect context exhaustion by grepping `llama-server.log` after the run | The log is retained two days and its grep has already hidden a signal once ("the log did prove it, the grep hid it"). A failure code on a committed item-health row survives | Andre |
  | 2 | Reuse `BAD_SHAPE` or `UNKNOWN` | Names the wrong cause, which is the exact defect being closed, and repeats the `max_output_tokens` mistake already recorded in `backend/idhazh/contracts/app_config.py` | Andre |
  | 3 | Fix `fits_context` in the same row | It is a no-op at `n_parallel: 1`; fixing a scenario that cannot happen adds an untested branch. It moves to row 11 as a precondition | Carmack |
  | 4 | Add a retry at non-zero temperature on a shape failure | No retry exists today, and a retry is a separate design question Andre flagged as off the published path | Andre |

## Row #5 - The `work` job names its host, its binary and its weights

- **Scope:** Print the six identifying lines at the start of every `work` job, add the three missing sha lines to `route`, and widen the runtime-log grep so a fixed pattern list cannot hide a signal again.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/tests/test_workflows.py`
  - `docs/reference/measurements.md`
- **Acceptance gates:** `pytest backend/tests/test_workflows.py` green; YAML parses; the grep pattern matches both `n_ctx_slot` and `n_ctx_seq` spellings; the step runs under `if: always()` so a failed shard still names its host.
- **Oracle:** Coverage. For every `work` shard, the job log contains a CPU model name, `nproc`, llama-server `system_info`, `llama-server --version`, the binary sha256 and the weights sha256. The open row in `docs/reference/measurements.md` that says the host difference "has no name" closes on that evidence.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Mirror what `route` already does at `.github/workflows/digest.yml` lines 412-414, then add the three lines `route` also lacks: `llama-server --version`, `sha256sum backend/bin/llama-server`, `sha256sum backend/models/${MODEL_FILE}`. Without those a run cannot say which bytes produced its output (Rule #10). | Carmack |
  | 2 | Widen the summary grep from a fixed pattern list to `^(srv\|slot) `. The full log is uploaded anyway, so the grep is a convenience and its only job is not to hide anything. | Carmack, Andre |
  | 3 | Grep both `n_ctx_slot` and `n_ctx_seq`. Newer llama.cpp renames the field, and the pin in row 3 does not stop a future bump. | Andre |
  | 4 | Also capture the `f_sim_best` and `f_keep` distribution, not just the presence of the line. Under two slots this is where prefix-reuse loss would show, and row 11 needs the baseline. | Andre |
  | 5 | Sampling RSS is folded into this row: `VmRSS` for the llama-server and python processes every 15 s, plus `/sys/fs/cgroup/memory.peak` at job end, uploaded next to `runtime-log-${shard}`. `measure.yml` already records exactly this and it is not wired into `digest.yml`. Neither of the two observed runs measured memory at all. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Poll `/slots` per request | Per-request HTTP cost for detail the log already carries | Carmack |
  | 2 | Leave the grep as a fixed list and rely on the uploaded artifact | The artifact expires in two days; the job log is the durable surface a reader opens first | Andre |
  | 3 | Add `host_cpu` to the fingerprint now that it is knowable | Every runner becomes a different fingerprint, hiding the cross-hardware divergence the stamp exists to expose - already rejected in `docs/architecture/contracts/determinism.md` | Andre |

## Row #6 - `llama-batched-bench` decides whether `-np > 1` is alive

- **Scope:** Add a `llama-batched-bench` arm to `measure.yml` that reports aggregate decode throughput at parallel levels 1, 2 and 4 on the real runner, and record the number.
- **Files touched:**
  - `.github/workflows/measure.yml`
  - `docs/reference/measurements.md`
- **Acceptance gates:** the arm runs inside the existing pinned-build job shape; it records hardware, date and spread (Rule #10); three repeats; the result lands in `docs/reference/measurements.md` in the same PR.
- **Oracle:** The gate number. Aggregate `S_TG t/s` at PL=2 divided by PL=1, measured self-paired on one host in one job. That single ratio decides whether row 11 runs or collapses.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Invocation: `llama-batched-bench -m backend/models/Qwen3-8B-Q4_K_M.gguf -c 8192 -b 512 -ub 512 -t 4 -npp 900 -ntg 300 -npl 1,2,4`. The prompt and generation lengths track the measured medians: prompt p50 877, generated p50 279 across 293 requests, 2026-08-24. | Andre |
  | 2 | The gate is 1.4x. Decode is 36.8 percent of model time (232.7 min prefill, 135.7 min decode, run `32742672105`, 2026-08-24), so at 1.5x aggregate decode the wall-clock saving is 12.3 percent and at 2.0x it is 18.4 percent. Below 1.4x the whole `-np` line of work is dead. | Andre, Carmack |
  | 3 | Prefill will not improve. `--ubatch-size 512` already presents a 512-column GEMM to 4 threads, and two concurrent prefills share those 4 threads. Do not read a prefill number from this bench as an argument for anything. | Carmack |
  | 4 | Continuous batching is not a second mechanism. "A decodes while B prefills" is the same shared weight pass as batched decode; counting it separately double-counts the gain. The earlier 40 percent ceiling was wrong. | Andre, Carmack |
  | 5 | `-npl 4` is included because the bench gives it free. It is a read, not a build target - PL=4 oversubscribes 4 vCPU at `--threads 4`. | Andre |
  | 6 | `llama-batched-bench` ships in the `llama-b*-bin-ubuntu-x64` release asset (verified 2026-08-25 against the local `backend/bin` contents), so no new download is needed. | verified in-session |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Skip the bench and go straight to a pipeline A/B | A pipeline arm costs ~190 min and cannot separate "batching did not help" from "batching never happened" | Andre |
  | 2 | Fire two concurrent requests from the current worker to exercise slot 2 | It measures our scheduler under contention, not the runtime's batching efficiency, and confounds the two in one number. Against `-np 1` it measures the queue | Andre, Carmack |
  | 3 | Build a `-np` sweep matrix past 2 | At 4 vCPU with `--threads 4` the answer above 2 is arithmetic, not measurement | Andre |

## Row #7 - `--metrics` is on and scraped once at job end

- **Scope:** Expose llama-server's Prometheus endpoint through config, and scrape it once at the end of each `work` job so a run records how close it came to the context wall and how many slots were ever busy.
- **Files touched:**
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/llm/server.py`
  - `config/idhazh.json`
  - `schemas/app-config.schema.json`
  - `.github/workflows/digest.yml`
  - `backend/tests/test_contracts.py`
  - `backend/tests/test_workflows.py`
  - `docs/concepts/config.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; full `pytest` green; contract drift gate regenerates `schemas/app-config.schema.json` byte-identical; `__changelog__` entry plus `version` date-stamp on the config contract (CLAUDE.md section 11); a fresh clone runs on the default.
- **Oracle:** Two numbers present. Every `work` job artifact carries `llamacpp:n_busy_slots_per_decode` and `llamacpp:n_tokens_max`. The first proves whether batching occurred; the second proves the day's context high-water mark against `n_ctx: 8192`.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `metrics` is a new `InferenceConfig` field defaulting to on, not a workflow literal (Rule #6). It joins the runtime sweep surface in `docs/concepts/config.md`. | Fowler |
  | 2 | The new field goes in the `NOT_DIGESTED` frozenset from row 1 with the reason "exposes an endpoint; changes no logit". Row 1's closed-world test fails until it is classified, which is the test working. | Fowler |
  | 3 | Scrape once at job end under `if: always()`, not per request. A failed shard is the shard whose high-water mark matters most. | Carmack |
  | 4 | This is a precondition for row 11. Without `n_busy_slots_per_decode` a null result from a concurrency arm is uninterpretable. | Carmack, Andre |
  | 5 | `--cache-ram` is not set in this row. It defaults to 8192 MiB and is the only allocation that scales with slot count, but Rule #10 forbids capping it before row 5's RSS sampling names a number. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Pass `--metrics` as a workflow literal | Hardcodes a tunable outside `config/` (Rule #6), and the sweep surface is deliberately config-driven so a measurement changes one thing at a time | Fowler |
  | 2 | Derive slot busyness from the log instead | The log reports per-request timings, not the per-decode slot occupancy that settles the batching question | Carmack |
  | 3 | Set `--cache-ram` defensively at the same time | Unmeasured. Rule #10 | Carmack |

## Row #8 - Extract the commit-and-push step, behaviour-neutral

- **Scope:** Extract the duplicated commit-and-push block from the `plan` and `assemble` jobs into one script both jobs call, with no behaviour change, plus a harness that executes it against real local git repositories.
- **Files touched:**
  - `.github/scripts/commit-and-push.sh` (new)
  - `.github/workflows/digest.yml`
  - `backend/tests/test_workflows.py`
  - `CLAUDE.md` (section 3 topology row for `.github/scripts/`)
  - `docs/reference/repository-layout.md`
- **Acceptance gates:** `pytest backend/tests/test_workflows.py` green including the new executable cases; `shellcheck` clean if available, otherwise `bash -n`; the existing text-shape assertion at `backend/tests/test_workflows.py` line 244 still passes; no behaviour change in either job.
- **Oracle:** Behavioural bijection. The script run against a scripted local origin produces byte-identical git state to the pre-extraction inline block on the happy path and on the clean-rebase path. The conflict path is characterised, not fixed, in this row - the test asserts today's exit-1-on-attempt-1 so row 9 has something to flip.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Structural and behavioural do not share a commit. Extraction is this row; the fetch-and-regenerate loop is row 9. | Fowler |
  | 2 | The extraction is the only way the bug becomes catchable. The same ~30 lines sit at `.github/workflows/digest.yml` lines 116-144 and 511-539, and neither copy can be executed by a test. The beneficiary is named and concrete, so this is not speculative generality. | Fowler |
  | 3 | The test is integration tier and runs real git: `git init` a bare origin, clone it, commit a racing change to origin, run the script, assert the outcome. No network, no mocks (Rule #7). | Fowler |
  | 4 | The existing assertion at `backend/tests/test_workflows.py` line 244 is a text-shape check that passed throughout while the loop never looped. Keep it - it pins the noise-discard ordering cheaply - but it is not the instrument for control flow. | Fowler |
  | 5 | `.github/scripts/` is a new directory and gets a row in the CLAUDE.md section 3 topology table in the same commit. | Fowler |
  | 6 | The script takes the path list as an argument so `plan` and `assemble` differ only in what they stage. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Fix the `set -e` bug during the extraction | Mixes structural and behavioural change in one commit, and the extraction's whole value is that it is provably behaviour-neutral | Fowler |
  | 2 | Leave the two copies and test the YAML text | Three visits to this step have already happened; a text assertion cannot observe control flow | Fowler |
  | 3 | Put the script in `backend/utilities/` | It is CI shell, not operator Python tooling; the topology table separates those on purpose | Fowler |

## Row #9 - Assemble refreshes its base and regenerates

- **Scope:** Stop asking git to text-merge derived state. Move the base refresh and the regeneration inside the retry loop so each attempt has a genuinely different base, and guard every command so the loop actually retries.
- **Files touched:**
  - `.github/scripts/commit-and-push.sh`
  - `.github/workflows/digest.yml`
  - `.gitattributes`
  - `backend/tests/test_workflows.py`
  - `docs/reference/github-actions.md` (the section "Both commit steps push through a rebase, and neither rebases on a dirty tree" becomes false)
  - `TODO/20260823-known-defects-plan.md` (defect 9 reopened and closed properly)
- **Acceptance gates:** `pytest backend/tests/test_workflows.py` green including the conflict case; the conflict test that row 8 characterised now asserts a successful publish; `shellcheck` or `bash -n`; every command in the loop guarded so no unguarded failure can exit early under `bash -e`.
- **Oracle:** The conflict case publishes. A scripted origin that has already gained a different `digest: <date>` commit plus an unrelated PR merge, replayed against the script, ends with the day published and both sides' ledger rows present in `state/published.csv`, `state/scores.csv` and `state/item-health/*.csv`.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The `set -e` bug is a symptom. Fixing only the loop would not have published run `32772221068`'s day: attempt 2 dies two lines further down at `git checkout -- .`, which fails on unmerged paths, and the conflict is deterministic - the same commit rebased onto the same tip conflicts three times. | Fowler |
  | 2 | The root cause is base staleness. `actions/checkout@v6` in `assemble` carries no `ref`, so it takes main's tip at trigger time, and the workflow's own comment measures the run at 164-184 min. Assemble always rebuilds the day from a base up to three hours old. | Fowler |
  | 3 | The loop becomes: fetch origin main, refresh only the regenerable payload paths from it, re-run `python -m idhazh assemble`, commit, push. `stage_assemble` already loads `previous_day` and appends - it is the conflict resolver, and it was being run once against a stale base and then thrown at `git merge-file`. | Fowler |
  | 4 | Never `git checkout origin/main -- frontend/public/digest`. The routes artifact writes rendered charts into that directory with `path: .`, and a directory-wide refresh deletes them. Name `digest.json` and `run.json` only. This is what PR #67 was about. | Fowler |
  | 5 | The three ledgers are append-only and line-independent: `state/item-health/*.csv`, `state/published.csv`, `state/scores.csv`. `.gitattributes` `merge=union` is correct for them. `frontend/public/telemetry/*.csv` is a full rewrite of item-health and is regenerated, never merged. | Fowler |
  | 6 | `concurrency: group: digest` already exists at `.github/workflows/digest.yml` line 45, and 7 of the 14 racing commits were human PR merges. A same-date guard fixes nothing. | Fowler |
  | 7 | `build_day` already dedupes by `item_id` and replaces the matching `DigestRunRef`. Idempotency is not the missing piece; the base it is idempotent against is. | Fowler |
  | 8 | Correction level 3. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Guard the loop so it really retries, and stop there | Deterministic conflict; attempt 2 dies at `git checkout -- .`. Necessary, never sufficient - and this would be the third band-aid on this step | Fowler |
  | 2 | `git pull --rebase -X theirs` or `-X ours` | Silently loses either the day or the PR. A band-aid that hides data loss (Rule #5) | Fowler |
  | 3 | A same-date concurrency guard | Already implemented, and half the racing commits were human | Fowler |
  | 4 | Publish to a branch and open a PR | Turns an unattended five-times-daily publish into human work; fails the reader | Fowler |
  | 5 | `.gitattributes merge=union` alone | Correct for three of six paths; the three JSON and telemetry payloads still need regeneration | Fowler |
  | 6 | Fold in the `build_manifest` run-identity asymmetry | `build_manifest` appends its `RunRecord` unconditionally while `build_day` filters by `n`, so two runs can publish under the same `n`. That is a semantics change on a published payload - its own Level-4 row, named here so it is not deferred silently | Fowler |

## Row #10 - Raise the shard ceiling from 4 to 8 and measure it

- **Scope:** Lift the shard cap and `max-parallel` from 4 to 8, then record the measured wall-clock against the 4-shard baseline.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/tests/test_workflows.py`
  - `docs/reference/measurements.md`
  - `docs/reference/github-actions.md`
- **Acceptance gates:** `pytest backend/tests/test_workflows.py` green; the `shards` dispatch input offers 1 through 8; `SHARD_PATTERN` accepts 1 through 8 and rejects 0 and 9; one authorized dispatch at 8 shards completes inside `timeout-minutes: 330`; cache stays under 10 GB and artifacts under 500 MB (Rule #2).
- **Oracle:** Wall-clock parity at half the work. Each of the 8 shards handles about half the items of a 4-shard run, and the slowest shard's model time falls by about half. Cache size is unchanged because every shard shares one key.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Shard parallelism is not exhausted; it is capped by a regex. `.github/workflows/digest.yml` line 86 enforces `^[1-4]$` and line 158 sets `max-parallel: 4`, against Rule #2's 20 concurrent jobs. This dominates `-np 2` on every axis - about 2x for two literals versus 10-30 percent for a client rewrite and a contract change. | Carmack |
  | 2 | Nothing is near a budget today. The slowest observed shard was 105.3 min against `timeout-minutes: 330`. This row buys reader freshness, not headroom, and the PR body says so. | Carmack |
  | 3 | The added cost is four more cache restores and four more model loads, all in parallel and all on the same cache key, so cache footprint is unchanged. The per-restore cost is currently unmeasured; row 5's instrumentation makes it readable from the run. | Carmack |
  | 4 | `run.shard_size` enforcement (blocker 12 of `TODO/20260825-qwen35-9b-swap-plan.md`) is adjacent and out of scope. This row changes the ceiling, not the dispatch rule. | Fowler |
  | 5 | Rule #10 forbids shipping "about 2x" as a claim. The row is not DONE until one authorized 8-shard run is measured and recorded with hardware, date and spread. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Raise the cap and run `-np 2` in the same change | Two variables at once; the measurement then means nothing | Carmack |
  | 2 | Go past 8 shards | Untested against cache contention and the 20-job ceiling shared with `route`, `measure` and CI; 8 is the reversible step | Carmack |
  | 3 | Ship the cap change without a measured run | Rule #10 | Carmack |

## Row #11 - CONDITIONAL - paired A-B-A `-np` measurement

- **Scope:** Only if row 6 reports aggregate decode at PL=2 of at least 1.4x - run one paired, host-controlled A-B-A arm comparing single-slot serial against two in flight, and record the result.
- **Files touched:**
  - `.github/workflows/measure.yml`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/summarize.py`
  - `tests/fixtures/`
  - `backend/tests/test_summarize.py`
  - `docs/reference/measurements.md`
  - `docs/architecture/summarize/throughput.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; full `pytest` green; the arm fits inside `timeout-minutes: 330`; every `output_digest` in the candidate arm matches the baseline arm, or the row ESCALATES to Andre before it proceeds.
- **Oracle:** Paired within-host ratio. For each host, arm B's wall-clock divided by arm A's, with two A measurements bracketing B. If the two A values differ by more than the A-to-B gap, that host is discarded rather than reported.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Gate first. If row 6 reads below 1.4x, this row is COLLAPSED with the bench number cited. Do not run it out of curiosity. | Andre, Carmack |
  | 2 | The concurrency shape is `ThreadPoolExecutor(max_workers=n_parallel)` around the existing model call in `stage_work`, consuming through `Executor.map` over the already band-sorted list. `map` yields in input order, so item write order, eval-row order and `write_atomic` all stay exactly as today. `post` is blocking `urllib`, which releases the GIL - no async rewrite, no queue library. | Andre |
  | 3 | The server arm is `n_parallel: null`, not `n_parallel: 2`. `InferenceConfig.n_parallel` is already `int \| None` and documented as "None omits the flag and keeps the runtime default", and omitting `-np` yields auto slots with unified KV - the exact configuration run `32766098026` already ran. Zero contract change. | Carmack |
  | 4 | A code-only change against the pinned `n_parallel: 1` measures the queue, not the flag. One slot defers the second request; llama.cpp's `common/arg.cpp` disables unified KV whenever `-np` is explicit. | Carmack |
  | 5 | `fits_context` must divide by the effective sequence count before any explicit `-np > 1` ships. It is correct at `n_parallel: null` with unified KV, so this row's chosen arm does not need it - but the guard lands here so the landmine is not left for a later config edit. | Andre, Carmack |
  | 6 | Design: one `workflow_dispatch`, five-way matrix, and inside each job run A-B-A sequentially with the server restarted between arms. Matrix members are replicates, not arms. | Andre, Carmack |
  | 7 | Arms run sequentially, never simultaneously. Two arms on 4 vCPU make the treatment a function of the control - the quantity under test appears on both sides. That is a specification error, not noise. | Andre, Carmack |
  | 8 | The corpus is a committed fixture of about 12-20 articles with a fixed band mix, in identical order in both arms. `measure.yml`'s current five-article corpus is built from that day's plan, so article mix confounds every comparison across dates. Band-sorted order also costs about 11 percent of decode across a job and must be held constant. | Andre, Carmack |
  | 9 | Report per-host paired deltas, never a pooled mean. Pooling is what destroyed the signal in the observation this plan came from. | Andre, Carmack |
  | 10 | The unit of analysis is the repeat, not the request. Requests inside one repeat share a host, a slot cache state and an ordering, so they are not independent. Within-host sampling error is already about 1.3 percent at 35 requests; hosts span 3.4x. | Andre, Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | 100 requests across 3 unpaired invocations | Power about 0.35 against a 12-18 percent effect. Adds samples to a variance component already near 1 percent while leaving the one near 240 percent untouched | Andre, Carmack |
  | 2 | Run the two arms as two shards of one digest run | Different shards get different articles, so arm and article mix are confounded on top of arm and host - strictly worse than the simultaneous design already rejected | Andre |
  | 3 | `n_parallel: 2` alone | Explicit `-np` disables unified KV, splitting the window to 4096 per sequence while `fits_context` believes 8192. Max observed total is 3058, so it fits today with 34 percent headroom and no margin for the 9B swap | Carmack |
  | 4 | Add a `kv_unified` field to `InferenceConfig` | A persisted-contract change under CLAUDE.md section 11 that buys exactly what `n_parallel: null` already buys for free | Carmack |
  | 5 | Raise `n_ctx` to 16384 on the daily path | That is a measurement arm, not a production setting. The daily worst case is 3058 tokens against 8192 | Andre |
  | 6 | An unpaired production A/B across real refreshes | The mistake this plan exists to record. `docs/reference/measurements.md` will already say the `-np 1` observation was not a controlled A/B | Carmack |

## Cross-plan notes

| # | Item | Owner |
| --- | --- | --- |
| 1 | Digesting `cache_type_k`, `cache_type_v`, `flash_attention`, `n_parallel` and `n_threads_batch` into `PipelineInputs`, and adding the `require_matching_header` guard that `fingerprint.append_new` lacks | Row 4 of `TODO/20260825-qwen35-9b-swap-plan.md` - it already resets every fingerprint |
| 2 | Stamping the observed llama.cpp build into `runtime_build`, replacing the hardcoded `"llama-server-local"` | Same - it moves every fingerprint |
| 3 | The `build_manifest` / `build_day` run-identity asymmetry that lets two runs publish under the same `n` | Its own Level-4 row, not yet written |
| 4 | A self-repetition metric on the summary, closing the one blind spot greedy decoding opens - nothing in the harness sees intra-summary repetition today | `docs/concepts/evaluation.md`, needs a `METRICS_VERSION` bump |
| 5 | `run.shard_size` enforcement | Blocker 12 of `TODO/20260825-qwen35-9b-swap-plan.md` |
