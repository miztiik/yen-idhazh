# Runtime and publish follow-ups - Plan

**Last Updated**: 2026-08-25

**Level**: 4 (highest row, #9). Rows 2 and 6 are Level 2. No Level-5 row.

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 3; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Eleven workers closing the runtime and publish-defects plan (PRs #81 to #88, #91, #95, #96, #98, #100, #101, #110, #111; its plan-doc is deleted and git history is the record) reported sixteen follow-up findings. Fifteen reproduce against the code at `420c2dc`, one is already owned by `TODO/20260825-qwen35-9b-swap-plan.md`, and six carry a sub-claim that does not reproduce as stated (section 2). |
| Hard scope - in | Digest-checking the GGUF fetch; deleting the duplicate argv builder by moving the install step; a shell linter and a shape check on the one free-text workflow input; making `run.shard_timeout_minutes` and `run.max_parallel` real; a context-full router failure code; dedupe parity across the two append paths; a repetition diagnostic on the eval row; item-health rows that survive a cancelled run; a committed server-counter snapshot the ledger can be checked against. |
| Hard scope - out | Any edit that moves `pipeline_fingerprint`; `runtime_build`, `runner_class`, `chat_template` or `model_sha256` on the run manifest; an immutable Hugging Face revision pin; `run.shard_size` enforcement; the Qwen3.5-9B swap; the faithfulness thresholds; any band that reads a new metric; sampling knobs; raising any Rule #2 budget. |
| ESCALATE triggers | (1) Any edit that would move `pipeline_fingerprint` - that is row 4 of `TODO/20260825-qwen35-9b-swap-plan.md`. (2) Row 7 measuring a `work` worst case above `run.shard_timeout_minutes` - the config number moves, the job bound does not, and the owner rules. (3) Any `workflow_dispatch` of `digest.yml`, `validate.yml` or `measure.yml` - the user authorizes each run. (4) Any proposal to bump `METRICS_VERSION` - it resets the run-day count that defect 2 of `TODO/20260823-known-defects-plan.md` is banking, and Andre rules. (5) Row 9 adding a field to `RunManifest`, which swap-plan rows 2-4 also open - Fowler rules the field owner first. (6) Any row pushing cache past 10 GB, artifacts past 500 MB, or the published site past 1 GB (Rule #2). |
| Chosen strategy | Integrity before ergonomics, and deletion before synchronisation. The weights fetch is the only step in the pipeline that can write a corrupt file, cache it, and be believed; it goes first. The duplicate argv builder is deleted rather than kept in step, because one step reorder in `digest.yml` removes the reason it exists. Every workflow row is serialised behind its predecessor because all four edit `.github/workflows/digest.yml` and `backend/tests/test_workflows.py`; the backend rows run alongside. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3.` |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The weights fetch cannot cache a file it never checked | - | A | PENDING | - | - | - |
| 2 | A router that ran out of context stops reading as a router that died | - | A | PENDING | - | - | - |
| 3 | The eval row records repetition inside a summary | - | A | PENDING | - | - | - |
| 4 | One llama-server argv builder, every caller, one port | 1 | B | PENDING | - | - | - |
| 5 | Both append paths say why they are safe, and the one that is not, dedupes | 2 | B | PENDING | - | - | - |
| 6 | The shell gets a linter and the free-text input gets a shape | 4 | C | PENDING | - | - | - |
| 7 | The work job's bound and fan-out read the config that declares them | 6 | D | PENDING | - | - | - |
| 8 | A run that dies after `work` keeps the rows `work` earned | 7 | E | PENDING | - | - | - |
| 9 | The ledger's timings can be checked against the server's own counters | 7, 8 | F | PENDING | - | - | - |

## Section 2 - Reported, did not reproduce

Sub-claims that did not hold against the code at `420c2dc`. The parent finding still reproduces in each case; only the detail below is corrected, so a row is not built on it.

| Reported | What the code says | Checked |
| --- | --- | --- |
| All three workflows fetch the weights with a bare `curl -sSL` | `measure.yml` uses `curl -fsSL --retry 3 --retry-all-errors`. Only `digest.yml` and `validate.yml` are bare. `measure.yml` still has no digest check, so it stays in row 1's scope for that reason alone. | `.github/workflows/measure.yml` lines 288 and 791 against `digest.yml` lines 220 and 475 |
| Nine simultaneous fetches of the same 4.7 GB file | Eight `work` shards fetch `MODEL_FILE`; the `route` job fetches `ROUTE_FILE`, a different and smaller model, under a different cache key. Nine askers, two files. | `.github/workflows/digest.yml` lines 189, 220, 452, 475 |
| `route` was cut to 40 minutes, against a stage budget class of about 60 | `route` carries `timeout-minutes: 50`. The 40 is `run.route_budget_minutes` in `config/idhazh.json`, which is the stage's self-stop, not the job bound. No "60 minute stage budget class" appears anywhere in the repository. | `.github/workflows/digest.yml` line 435; `config/idhazh.json` line 125 |
| The port `8080` is a literal in `digest.yml` in three places | Five in `digest.yml`, six in `validate.yml`, one in `measure.yml`, plus the default in `backend/utilities/llama_server_argv.py`. | `Select-String -Path .github/workflows/*.yml -Pattern '8080'`; `backend/utilities/llama_server_argv.py` line 17 |
| The ledger pools to 11.09 tok/s read for `2026-08-25-1` | Reproduces exactly, as `(input_tokens - cached_tokens) / prefill_ms` over 145 paired rows: 13,865.6 s, 276,785 input tokens, 122,974 cached, 11.093 tok/s. The same rows give 19.962 tok/s if cached tokens are not subtracted. The definition, not the arithmetic, is what decides the number. | `state/item-health/2026-08.csv`; `backend/idhazh/contracts/summary.py` line 156 |
| The log-derived figure for the closest run is 13.67 tok/s over 10,935 s | Could not be checked. `runtime-log-*` carries `retention-days: 2` and no committed file holds the server's counters. That inability is row 9's whole subject. | `.github/workflows/digest.yml` line 411 |
| `_published_rows` writing every item has put duplicate rows on the ledger | No duplicate has landed. `state/published.csv` holds 1303 rows and 1303 distinct `url_key` values. The planner excludes already-published addresses, so the loop never sees a carried-forward item. The comment is wrong; the behaviour is right for a reason written nowhere near it. | `state/published.csv`; `backend/idhazh/cli.py` lines 200, 1123-1147 |

## Section 3 - Cross-plan notes

Work another plan already owns. No row here duplicates it.

| Finding | Owner | Evidence |
| --- | --- | --- |
| `stage_work` records `runtime_build="llama-server-local"`, `runner_class="local"`, `chat_template=model.id` and a 64-zero `model_sha256`, so the committed manifest cannot name the bytes that produced a run | `TODO/20260825-qwen35-9b-swap-plan.md` blocker 8, rows 2-4 | Blocker 8 reads "Production fingerprints are not wired to the ledger or skip classifier and record false/zero weight, runtime, template and runner identity." Row 4 is "Wire truthful fingerprint identity and model-separated drift." The defect is at `backend/idhazh/cli.py` lines 416-423 and reproduces; it is not re-opened here. |
| Digesting `cache_type_k`, `cache_type_v`, `flash_attention`, `n_parallel` and `n_threads_batch` into `PipelineInputs`, and the `require_matching_header` guard `fingerprint.append_new` lacks | `TODO/20260825-qwen35-9b-swap-plan.md` blockers 9-10, rows 3-4 | Confirmed absent: `backend/idhazh/fingerprint.py` line 220 `append_new` reads the ledger and filters, and never calls `require_matching_header`, which `backend/idhazh/ledger.py` line 104 defines and `_append` line 119 uses. Both are inside swap-plan row 3's "expand fingerprint event/ledger contract". |
| `run.shard_size` enforcement | `TODO/20260825-qwen35-9b-swap-plan.md` blocker 12 | Blocker 12 reads "Production divides the full plan across a fixed worker count and does not enforce `run.shard_size`." Confirmed: `shard_size: 5` in `config/idhazh.json` has no reader outside `backend/idhazh/contracts/app_config.py` line 62. Row 7 here takes `run.shard_timeout_minutes` and `run.max_parallel`, which the swap plan does not name, and leaves `shard_size` alone. |
| An immutable Hugging Face revision instead of `resolve/main` | `TODO/20260825-qwen35-9b-swap-plan.md` blockers 7 and 16, row 2 | Row 1 here checks the bytes, which fails loudly when the ref moves. Pinning the ref is a reproducibility question that needs a new `ModelRef.revision` field, and `ModelRef` is swap-plan row 2's surface. |
| Validation hardcodes the server flags | `TODO/20260825-qwen35-9b-swap-plan.md` blocker 5, row 5 | Row 4 here closes the server-flags clause of that blocker and nothing else in it. Swap-plan row 5 keeps the capture-once, replay-both, pin-scorer and date-isolation work. Whichever lands first, the other re-reads `.github/workflows/validate.yml` before starting. |

## Row #1 - The weights fetch cannot cache a file it never checked

- **Scope:** Fetch every GGUF with a failing, retrying `curl` and check its sha256 against `config/idhazh.json` before the server starts and after a cache restore.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `.github/workflows/validate.yml`
  - `.github/workflows/measure.yml`
  - `config/idhazh.json`
  - `backend/tests/test_workflows.py`
  - `docs/reference/github-actions.md`
- **Acceptance gates:** `pytest backend/tests/test_workflows.py` green; full `pytest` green; every workflow YAML parses; the two recorded digests are reproduced by `sha256sum` against the published Hugging Face files and carry the date they were taken (Rule #10); `ruff`; `mypy --strict`; contract drift gate green.
- **Oracle:** Closed-world integrity. Every step in `.github/workflows/` that writes a `.gguf` is followed, before any `llama-server` starts, by a `sha256sum --check` against a digest read from `config/idhazh.json`, and the check also runs on the cache-hit path. Adding a tenth workflow that fetches weights fails the test until it carries the same pair.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The sharp edge is `-sSL` without `-f`, not the missing retry. Without `-f`, curl writes an HTTP error body into `backend/models/<file>.gguf` and exits 0. `backend/models` is a cache path (`.github/workflows/digest.yml` lines 186-189), so the bad file is saved under the pinned key and served to every later run until the entry is evicted. Verified 2026-08-25 at `digest.yml` lines 220-221 and 475-476 and `validate.yml` lines 91-94. | Carmack, verified in-session |
  | 2 | The digest lives in `config/idhazh.json`, not in a workflow `env`. `ModelRef.sha256` already exists at `backend/idhazh/contracts/app_config.py` line 38 and is `null` for both models today. A knob in config is Rule #6; a fourth `LLAMA_*`-shaped env var is not. `digest.yml` line 227 already reads `models.summarize.id` out of that file with `python -c`, so the pattern is in the file and proven. | Fowler |
  | 3 | The check runs on the cache-restore path too, not only after a fetch. The fetch step is guarded by `if: steps.weights.outputs.cache-hit != 'true'`, so a corrupt entry written before this row lands is never re-examined by a fetch-side check alone. | Carmack |
  | 4 | `measure.yml` is in scope even though it already retries. It has no digest check either, and a measurement taken against unnamed bytes cannot be quoted under Rule #10. | Carmack |
  | 5 | No cache-key bump. The check turns a bad entry into a loud failure on first restore, which is the signal a silent key bump would hide. A key bump also refetches roughly 7 GB across nine jobs for an entry that is probably fine. | Carmack |
  | 6 | Populating `models.route.sha256` and `models.summarize.sha256` changes `config/idhazh.json`, which `RunManifest.config_digests` hashes. That moves a config digest and not `pipeline_fingerprint`; `backend/idhazh/fingerprint.py` `build_inputs` takes `model_sha256` from `ModelRef.sha256` at `backend/idhazh/cli.py` line 416, so this DOES move the stamp. The row therefore records the intent and defers the config write to swap-plan row 4, and lands the workflow check reading a value that is null until then - which the test asserts fails the job rather than skipping the check. | Fowler, ESCALATE trigger 1 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Add `-f --retry 3 --retry-all-errors` and stop there | Closes the HTML-error-body case and not the truncated-transfer case. A connection that dies mid-body is a 200 that curl already retried, and the bytes on disk are still short | Carmack |
  | 2 | Check a byte-count floor instead of a digest | A floor names a number nobody can derive and passes any corruption above it. `measure.yml` already proves the digest pattern is affordable on the archive | Carmack |
  | 3 | Put the digest in a workflow `env` beside `LLAMA_CPP_SHA256` | The llama.cpp build is a workflow concern; the model is a config concern with a typed home already built and empty. Two homes for one class of fact is what row 4 exists to undo | Fowler |
  | 4 | Bump the cache key so every runner refetches once against the check | Roughly 7 GB across nine jobs to hide the exact failure the check exists to surface | Carmack |
  | 5 | Authenticate the Hugging Face fetch | Anonymous is not the defect; unchecked is. Authentication buys rate headroom this pipeline has never hit and adds a secret to a step that needs none | Carmack |

## Row #2 - A router that ran out of context stops reading as a router that died

- **Scope:** Give `_route_one` the same `HTTPError`-before-`OSError` handling `_summarize_one` received in PR #88, so a context-full router request is distinguishable from an unreachable one.
- **Files touched:**
  - `backend/idhazh/cli.py`
  - `backend/tests/test_route.py`
  - `docs/concepts/pipeline-loop.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; full `pytest` green; no schema change (`FailureCode.CONTEXT_EXCEEDED` already exists); contract drift gate green; no test touches the network (Rule #7).
- **Oracle:** Cause fidelity, from the same fixture PR #88 committed. A recorded llama.cpp 400 body carrying `"type": "exceed_context_size_error"` produces a router log line naming the context, and a genuine connection refusal still produces the unreachable line. A route decision is still written in both cases, so the degrade-do-not-fail contract is unchanged.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The defect reproduces. `backend/idhazh/cli.py` line 825 catches bare `OSError` and substitutes `Completion(content="")`, logging `router unreachable`. `urllib.error.HTTPError` subclasses `OSError`, so a 400 the server chose to send reads as a server that never answered. `_summarize_one` at lines 580-591 already does the correct thing. | Carmack, verified in-session |
  | 2 | Reuse `is_context_exceeded` from `backend/idhazh/llm/server.py`, imported at `backend/idhazh/cli.py` line 61. A second matcher for the same llama.cpp error type is the duplication row 4 exists to remove, in miniature. | Fowler |
  | 3 | The router writes no item-health row, so this is a log-surface change, not a contract change. `FailureCode` gains no member. A route decision is still written on either failure - silence is what turns a skip into a quiet descope, as the `_route_one` docstring already argues. | Fowler |
  | 4 | Level 2, not level 1. It is one file and about twenty lines, but it changes what a published run reports about itself, which is an explicit behaviour change (`CLAUDE.md` section 6). | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Give the router an item-health row so the code lands on a ledger | The router does not own an item's health and never has; widening a persisted contract to carry a log line is a schema bump bought for nothing | Fowler |
  | 2 | Catch `HTTPError` and re-raise, failing the route stage | `route` is `continue-on-error: true` and degrades by design. Failing it loses every other item's visual for one item's context | Carmack |
  | 3 | Wait and fold this into row 4, since both touch the llama-server boundary | Different files, different risk. Row 4 moves a CI step; this changes a Python except clause | Fowler |

## Row #3 - The eval row records repetition inside a summary

- **Scope:** Add one nullable diagnostic column measuring repeated n-grams inside the summary itself, which greedy decoding makes possible and no current metric can see.
- **Files touched:**
  - `backend/idhazh/evals/metrics.py`
  - `backend/idhazh/evals/score.py`
  - `backend/idhazh/contracts/eval_row.py`
  - `schemas/eval-row.schema.json`
  - `backend/tests/test_evals.py`
  - `docs/concepts/evaluation.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; full `pytest` green; contract drift gate regenerates `schemas/eval-row.schema.json` byte-identical; `__changelog__` carries a `{version, change, why}` entry date-stamped today with `version` matching it (`CLAUDE.md` section 11); a fixture proves an eval row written before this commit still loads; `state/scores.csv` still appends without a header migration.
- **Oracle:** Blind-spot closure, on committed fixtures only. A summary that repeats one 4-gram three times scores above the new column's zero point while scoring identically on `extractiveness`, `verbatim_run`, `coverage` and `hhem`. If any existing metric moves for that input, the column is measuring something already covered and does not ship.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The blind spot is real. `backend/idhazh/evals/metrics.py` line 218 builds `_ngrams(summary_tokens)` and intersects it with `_ngrams(source)`. Every n-gram machine in the file compares the summary to the SOURCE. `EvalRow` carries eleven quality columns and not one of them reads the summary against itself. `config` has `evaluation.repetition_weight`, but `backend/idhazh/rank.py` line 168 shows it is cross-source story repetition in the ranker, a different thing under a colliding name. | Andre, verified in-session |
  | 2 | **Do NOT bump `METRICS_VERSION`.** This contradicts the finding as reported. `METRICS_VERSION` is folded into `scorer_version` at `backend/idhazh/evals/metrics.py` line 379, and `docs/concepts/evaluation.md` requires 10 distinct run-days at one `scorer_version` before any threshold moves. Defect 2 of `TODO/20260823-known-defects-plan.md` is at 1 of 10. A column no band reads does not change the instrument the bands use, so bumping would spend a banked run-day to record a fact about nothing. `compression` is the precedent: recorded, diagnostic, not a pass/fail input. | Andre |
  | 3 | Nullable, so every historical row still validates and the change is additive under `CLAUDE.md` section 11. | Fowler |
  | 4 | Reuse `_NGRAM = 4` rather than introducing a second window. Two n-gram sizes in one file is two numbers a reader has to reconcile, and 4 is already the size the extractiveness figure in `docs/concepts/evaluation.md` is stated at. | Andre |
  | 5 | No band, no threshold, no alarm in this row. The moment a band reads the column it becomes a reader-facing promise and a Level-5 question that defect 2 already owns. | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Bump `METRICS_VERSION` to 4 with the column | Resets the run-day count `docs/concepts/evaluation.md` requires, to record a diagnostic no band reads. ESCALATE trigger 4 | Andre |
  | 2 | Detect repetition at generation time and retry at non-zero temperature | No retry path exists, and a retry is a separate design question already ruled off the published path in the closing plan | Andre |
  | 3 | Reuse `verbatim_run` by pointing it at the summary | It answers "how much was copied", which is a different question with a live reader-facing meaning. Overloading it makes both answers unreadable | Andre |
  | 4 | Put the measurement on the item-health row instead | The item-health row is per planned item and exists for outcomes and timings. Quality columns live on the eval row, which is the scored subset by design | Fowler |

## Row #4 - One llama-server argv builder, every caller, one port

- **Scope:** Move the `Install` step above `Start the model` in the two `digest.yml` inference jobs, delete `backend/utilities/llama_server_argv.py`, and make `validate.yml` and both `digest.yml` jobs start the server through `idhazh.llm.server.server_argv` on one configured port.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `.github/workflows/validate.yml`
  - `backend/utilities/llama_server_argv.py` (deleted)
  - `backend/idhazh/llm/server.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_workflows.py`
  - `docs/reference/github-actions.md`
- **Acceptance gates:** `pytest backend/tests/test_summarize.py backend/tests/test_workflows.py` green; full `pytest` green; `ruff`; `mypy --strict`; every workflow YAML parses; `backend/utilities/llama_server_argv.py` is gone and nothing references it; `measure.yml` is untouched because it already imports `server_argv`.
- **Oracle:** Bijection. Exactly one function in the repository spells a `llama-server` flag, and every workflow step that starts a server reaches it. `Select-String -Path .github/workflows/*.yml -Pattern '\-\-ctx-size|--batch-size|--ubatch-size|--no-context-shift'` returns nothing, and `8080` appears once per workflow as an `env` declaration rather than once per curl.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The duplicate exists for exactly one reason and the reason is removable. In `digest.yml`, `Start the model` is step 6 (line 223) and `Install` / `pip install -e .` is step 7 (line 246); the same inversion sits in `route` at lines 478 and 501. The utility's own docstring says "before package install runs". Move the install one step earlier and the utility has no purpose. `measure.yml` already does `from idhazh.llm.server import server_argv` at lines 356 and 497, so two of three consumers are already correct. | Carmack, verified in-session |
  | 2 | Delete rather than synchronise. `backend/tests/test_summarize.py` line 232 keeps the copies in step by running the utility as a subprocess and diffing, which makes every new flag a two-file edit plus a subprocess test. Rule #5 says fix structurally; Rule #8 says prefer the mature thing over the custom one, and here the mature thing is the function that already exists. | Fowler |
  | 3 | `validate.yml` never needed the utility. Its `Install` is step 3 (line 58) and its servers start at lines 115 and 137, so the package has been importable there all along. That is why it drifted: it had no forcing function, and so it missed `--no-context-shift` (PR #88) and `--metrics` (PR #95). | Carmack, verified in-session |
  | 4 | The port becomes a `server_argv` argument fed by one workflow `env: LLAMA_PORT`, and every health-check and metrics curl reads it. Eleven literals across three files is Rule #6, and it is the same class of defect as the argv duplication, so it lands with it rather than as a row of its own. | Carmack |
  | 5 | `test_server_argv_matches_the_digest_workflow_command` is rewritten, not deleted. Its current assertion is `workflow.count("backend/utilities/llama_server_argv.py") == 4`, which is a count of a path this row removes. The replacement asserts the Oracle property. | Fowler |
  | 6 | Moving `Install` before `Start the model` costs nothing in wall-clock. The step runs in the same job either way; only its position changes. No measurement is claimed for it (Rule #10). | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep both builders and widen the diff test to cover `validate.yml` | Keeps a duplicate whose only justification is an ordering that one line removes, and makes every future flag a three-file edit | Fowler |
  | 2 | Have the utility import from `backend/idhazh/llm/server.py` by path manipulation | A `sys.path` insert in a workflow-facing script to reach a package that is about to be installed anyway. It works and it is a monkey patch (Rule #5) | Fowler |
  | 3 | Point `validate.yml` at the utility instead | Fixes validate and keeps the duplicate. The cheaper move deletes the file | Carmack |
  | 4 | Leave the port alone as too small to be worth a diff | It is a Rule #6 violation in the same steps this row is already rewriting, and it costs one env line. Splitting it into its own row is a PR nobody would open | Carmack |

## Row #5 - Both append paths say why they are safe, and the one that is not, dedupes

- **Scope:** Give `ledger._append` the dedupe the eval writer already has, correct the `_published_rows` docstring to describe the filter the code actually applies, and fix the unconditional `RunRecord` append that can put two runs under one `n`.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/cli.py`
  - `backend/tests/test_ledger.py`
  - `backend/tests/test_pipeline.py`
  - `docs/architecture/publishing/`
- **Acceptance gates:** `ruff`; `mypy --strict`; full `pytest` green; contract drift gate green; no schema change (no field is added or retyped); the committed `state/published.csv` still loads and still holds 1303 rows after a replayed run against a fixture plan.
- **Oracle:** Idempotence under replay. Running `assemble` twice against one fixture day produces byte-identical `state/published.csv`, `state/seen/<month>.csv` and `frontend/public/digest/<day>/run.json`, and the second `RunManifest` holds exactly as many `RunRecord` entries as it has distinct `n` values. Today the third of those fails.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The manifest defect is the real one of the three. `backend/idhazh/assemble.py` line 268 derives `run_n` from `previous.runs[-1].n + 1` and line 322 appends unconditionally, while `build_day` at lines 207-210 replaces any entry with a matching `n`. When the manifest is absent and the day is not - a commit that landed `digest.json` and lost `run.json`, which is exactly what the push race in defect 9 of `TODO/20260823-known-defects-plan.md` produced - the two disagree, and `RunRecord.run_id` at line 285 is `f"{plan.date}-{run_n}"`, the join key every ledger row carries. Two records under one `run_id` is a broken join, not a cosmetic duplicate. | Fowler, verified in-session |
  | 2 | `ledger._append` gets a dedupe keyed on the contract's own identity columns, matching `backend/idhazh/evals/writer.py` lines 34 and 82-92. It is correct today only because `backend/idhazh/cli.py` line 200 excludes already-published addresses from the plan - a distant invariant, stated nowhere near the writer. Measured 2026-08-25: `state/published.csv` holds 1303 rows and 1303 distinct `url_key` values, so no duplicate has landed and this is prevention, not repair. | Fowler, verified in-session |
  | 3 | The `_published_rows` docstring is corrected, not the loop. The comment at `backend/idhazh/cli.py` line 1128 claims "Only what this run introduced is recorded"; the loop at line 1134 walks all of `day.items` and filters on membership in `plan.items`. `DigestItem.introduced_by_run` exists and `backend/idhazh/assemble.py` line 309 already uses it, so filtering on it would be one line - and it would replace a correct filter with a narrower one for no measured gain. Prose that lies is the defect. | Fowler |
  | 4 | No schema bump. All three changes are behavioural on the write side, and no persisted field is added, removed or retyped. | Fowler |
  | 5 | Level 3, not level 2. Three files, and one of them changes what a committed manifest can contain. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Leave `ledger._append` alone since no duplicate has landed | Two writers of append-only ledgers behaving differently is a coin toss the next reader has to re-derive. `.gitattributes` already promises `merge=union` on these files on the grounds that "a reader of these ledgers already deduplicates" - which is true of two of the three | Fowler |
  | 2 | Filter `_published_rows` by `introduced_by_run` and keep the comment | Replaces a filter that is right for the whole day with one that is right for one run, on a ledger whose question is "has this address ever been published" | Fowler |
  | 3 | Dedupe in `build_manifest` by rewriting the previous run's record | The manifest is append-only and the docstring says so at line 267. A colliding `n` means the caller's assumption broke; raising names that, and rewriting hides it | Fowler |
  | 4 | Split into three rows, one per file | Three PRs that each change one line of an idempotence property nobody can test in isolation. The Oracle only exists for all three together | Fowler |

## Row #6 - The shell gets a linter and the free-text input gets a shape

- **Scope:** Add `shellcheck` over `.github/scripts/` to the CI gates job, and require every `workflow_dispatch` free-text input to be shape-checked before it reaches a path, a commit message or a `run:` body.
- **Files touched:**
  - `.github/workflows/ci.yml`
  - `.github/workflows/digest.yml`
  - `pyproject.toml`
  - `backend/tests/test_workflows.py`
  - `docs/reference/github-actions.md`
  - `docs/how-to/run-the-gates.md`
- **Acceptance gates:** `shellcheck --severity=style .github/scripts/*.sh` clean; `pytest backend/tests/test_workflows.py` green; full `pytest` green; `ruff`; `mypy --strict`; the new dev dependency names its beneficiary feature and its installed cost with the date it was measured (Rule #8, Rule #10); lockfile-equivalent manifest in sync.
- **Oracle:** Coverage of the untrusted surface. Every `workflow_dispatch` input in `.github/workflows/` is either a `type: choice` with an enumerated option list, or is matched against a regex before its first use, and a test enumerates the inputs so a new one fails until it is classified. `inputs.date` fails that test today; `inputs.shards` and `inputs.faithfulness` pass.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The asymmetry reproduces and is sharper than reported. `inputs.shards` is constrained TWICE - `type: choice` with options 1 through 8 at `.github/workflows/digest.yml` lines 31-43, then a regex at lines 102-106. `inputs.date` is free text with `default: ''` at lines 28-30 and is checked nowhere. It reaches a directory path at line 117, a commit message at line 136, an artifact path at line 146, and a `--date` argument in five `run:` bodies. | Carmack, verified in-session |
  | 2 | State the threat honestly. `permissions: contents: write` at lines 49-50 and `workflow_dispatch` both mean the dispatcher already has write access, so this is not a privilege boundary. It is a correctness boundary: `2026-8-24` or a trailing space publishes a day directory no reader will ever find, silently, after a six-hour run. The regex is worth adding for that, and the injection framing is not what justifies it. | Carmack |
  | 3 | `shellcheck` arrives as `shellcheck-py` in `[project.optional-dependencies].dev`, not as a downloaded binary. A CI step that fetches an unpinned binary is the defect row 1 closes; a pip dependency is pinned by the same manifest as `ruff` and `mypy`. | Fowler |
  | 4 | `shellcheck` covers `.github/scripts/` only. It cannot read a `run:` body, and the tool that can (`actionlint`) is a Go binary this row is not willing to fetch. The `run:` bodies get the `test_workflows.py` gate instead, which is in-repo and needs nothing downloaded. | Carmack |
  | 5 | The one script in scope is the one that pushes. `.github/scripts/commit-and-push.sh` is 100-plus lines of retry and rebase logic, and defect 9 of `TODO/20260823-known-defects-plan.md` records what a bug in it costs: a whole day's digest. One file is enough to justify the gate. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Add `actionlint` and get expression-injection checking for free | A Go binary fetched at CI time. Pinning and digest-checking it is row 1's whole subject, and taking on a second unpinned fetch to close a linting gap is a trade in the wrong direction | Carmack |
  | 2 | Give `date` a `type: choice` like `shards` | The valid set is unbounded. A regex is the right shape for a date and a choice list is not | Carmack |
  | 3 | Validate `date` in Python inside `idhazh plan` instead of in the workflow | The bad value has already reached `day_dir` at line 117 and the artifact path at line 146 by then. The check belongs where the value is first turned into a fact | Fowler |
  | 4 | Skip `shellcheck` because there is only one script | It is the script that decides whether a finished run reaches a reader | Fowler |

## Row #7 - The work job's bound and fan-out read the config that declares them

- **Scope:** Measure what a `work` shard actually costs, set `run.shard_timeout_minutes` and `run.max_parallel` to numbers that measurement supports, and make `digest.yml` read both instead of hardcoding contradicting ones.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `schemas/app-config.schema.json`
  - `backend/tests/test_workflows.py`
  - `docs/reference/measurements.md`
  - `docs/concepts/config.md`
- **Acceptance gates:** `pytest backend/tests/test_workflows.py` green; full `pytest` green; `ruff`; `mypy --strict`; contract drift gate regenerates `schemas/app-config.schema.json` byte-identical; the measured `work` durations carry hardware, date and spread (Rule #10); no job bound is lowered below the measured worst case plus its stated margin (Rule #2).
- **Oracle:** No second home for one number. `timeout-minutes` and `max-parallel` on the `work` job are both derived from `needs.plan.outputs`, which the `decide` step reads out of `config/idhazh.json`, and a test asserts that no integer literal for either appears in the job body. Changing `run.shard_timeout_minutes` in config and re-reading the rendered workflow changes the bound.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Two knobs are dead, and they contradict the workflow rather than merely being unused. `run.shard_timeout_minutes: 150` and `run.max_parallel: 4` in `config/idhazh.json` have no reader outside `backend/idhazh/contracts/app_config.py` lines 67-68, while `.github/workflows/digest.yml` line 152 sets `timeout-minutes: 330` and line 158 sets `max-parallel: 8`. A config file that declares 150 and 4 while production runs 330 and 8 is worse than no config: it is a wrong answer with a schema behind it. Verified 2026-08-25 by grepping the whole repository for each name. | Fowler, verified in-session |
  | 2 | Measure before reconciling, and let the measurement pick the direction. Neither 330 nor 150 has a recorded basis. The row reads the wall-clock of the completed `work` jobs on `digest.yml` and sets the config number to the observed worst case plus a stated margin. If the worst case is above 150, the CONFIG number moves up and the job bound comes down to meet it - the job bound is a backstop and never the budget (Rule #2, and the comment already at lines 425-429 for `route`). | Carmack |
  | 3 | `run.shard_size` stays out. It is blocker 12 of `TODO/20260825-qwen35-9b-swap-plan.md` and it is a different question: how the plan is divided, not how long a division may take. | Fowler |
  | 4 | ESCALATE if the measured worst case exceeds `run.shard_timeout_minutes` by more than its margin. That is the case where honouring config would kill a run that finishes today, and it is the owner's call which number is wrong. | Carmack, ESCALATE trigger 2 |
  | 5 | `route` is already correct and is not touched. `run.route_budget_minutes: 40` is read at `backend/idhazh/cli.py` line 699 and the job bound of 50 sits above it with the reason written in the workflow. That is the shape `work` should copy. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Delete the two knobs, since nothing reads them | The runner budget would then have no declared home at all, and the two numbers that matter would live only in a YAML file no contract validates (Rule #6) | Fowler |
  | 2 | Set `timeout-minutes: 150` to match config and ship | Lowers a live production bound to an unmeasured number. Rule #10: an unmeasured number may not justify a design, and a job that dies at 150 loses the reader a whole day | Carmack |
  | 3 | Raise `run.shard_timeout_minutes` to 330 to match the workflow | Same defect facing the other way. 330 is not measured either, and it is more than half the six-hour platform maximum, which the swap plan already warns against sizing against | Carmack |
  | 4 | Fold this into row 6 since both edit the `decide` step | Row 6 is about untrusted input; this is about the runner budget. Different reviewers, different failure modes | Fowler |

## Row #8 - A run that dies after `work` keeps the rows `work` earned

- **Scope:** Commit the item-health and eval rows a shard produced at the end of the `work` job, so a run cancelled or failed before `assemble` does not lose what it measured.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/idhazh/cli.py`
  - `backend/tests/test_workflows.py`
  - `backend/tests/test_pipeline.py`
  - `docs/concepts/telemetry.md`
- **Acceptance gates:** `pytest backend/tests/test_workflows.py backend/tests/test_pipeline.py` green; full `pytest` green; `ruff`; `mypy --strict`; contract drift gate green; the commit step runs under `if: always()`; a replayed run appends nothing a previous run already appended (depends on row 5's dedupe); the union merge in `.gitattributes` still covers every path the new step stages.
- **Oracle:** Survival across cancellation. A fixture run whose `assemble` never executes still leaves the item-health rows for its completed items in `state/item-health/<month>.csv`, and re-running the same day afterwards appends zero duplicates. Today the first half of that is empty.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The loss reproduces. `backend/idhazh/cli.py` line 1107 is the only caller of `ledger.append_item_health`, and it runs inside `assemble`. A shard's per-item payloads leave the runner only as the `items-${{ matrix.shard }}` artifact at `.github/workflows/digest.yml` lines 414-418, which carries `retention-days: 1`. A run cancelled between `work` and `assemble` has measured every item and recorded none of it after one day. | Carmack, verified in-session |
  | 2 | The `work` job commits its own rows, the way the `plan` job already commits `state/seen` and `state/feed-health` at lines 134-141. The comment there gives the reason verbatim: "A run that dies in the worker still saw what it saw, and the next run needs that." The same argument covers the worker. | Fowler |
  | 3 | Eight shards committing concurrently is what `.gitattributes` `merge=union` on `state/**/*.csv` exists for, and `.github/scripts/commit-and-push.sh` already handles the race with a rebase for record-only jobs. Reuse the script; do not write a second push loop. | Fowler |
  | 4 | Row 5's dedupe is a hard prerequisite, not a nicety. Without it, `assemble` re-appends what `work` already committed, and the ledger doubles on every successful run. That is why this row depends on 7 for the file and on 5 for the behaviour, and the Reckoner records the file dependency because it is the one that blocks dispatch. | Fowler |
  | 5 | Eval rows are included. `state/scores.csv` is written by the same `assemble` call at line 1105 and is lost the same way, and its writer already dedupes at `backend/idhazh/evals/writer.py` line 82. | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Raise `retention-days` on the items artifact from 1 to 30 | Buys 30 days of a file nobody reads and still leaves nothing committed. Rule #2 caps artifacts at 500 MB and this is the largest artifact in the run | Carmack |
  | 2 | Add a recovery command that replays an artifact into the ledger | A manual step that needs a human to notice within a day. The plan job already proved the right answer is to commit at the stage that earned the row | Fowler |
  | 3 | Have `assemble` run under `if: always()` instead | It already needs the worker artifacts, which a cancelled run may not have uploaded, and a cancelled workflow does not run `always()` steps in jobs it never started | Carmack |
  | 4 | Write a second push loop tuned for eight concurrent shards | `.github/scripts/commit-and-push.sh` was extracted in PR #96 precisely so the retry behaviour is written once and testable | Fowler |

## Row #9 - The ledger's timings can be checked against the server's own counters

- **Scope:** Commit the `llamacpp:` counter snapshot each `work` shard already scrapes, and add a check that the ledger's pooled prefill agrees with it within a stated tolerance.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/idhazh/contracts/` (one new counter-snapshot contract)
  - `schemas/`
  - `backend/idhazh/cli.py`
  - `backend/tests/test_workflows.py`
  - `backend/tests/test_contracts.py`
  - `docs/architecture/summarize/throughput.md`
  - `docs/reference/measurements.md`
- **Acceptance gates:** `ruff`; `mypy --strict`; full `pytest` green; contract drift gate regenerates the new schema byte-identical; the new contract carries `version` and a `{version, change, why}` changelog entry date-stamped today (`CLAUDE.md` section 11); every number recorded carries hardware, date and spread (Rule #10); Rule #2 budgets unchanged.
- **Oracle:** Reconciliation. For one committed run, the ledger's pooled `sum(input_tokens - cached_tokens) / sum(prefill_ms)` and the same quantity derived from the committed `llamacpp:` counters agree within a tolerance the row states before it reads either. A disagreement outside the tolerance names which of the two is wrong; today neither can be produced twice.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The premise is "we cannot tell", not "the ledger is wrong". Confirmed 2026-08-25 from `state/item-health/2026-08.csv`: run `2026-08-25-1` has 145 paired rows, 13,865.6 s of `prefill_ms`, 276,785 input tokens and 122,974 cached, which is 11.093 tok/s uncached and 19.962 tok/s counting cached tokens. Both are the ledger's. The reported log figure of 13.67 tok/s could not be checked because `runtime-log-*` carries `retention-days: 2` (`.github/workflows/digest.yml` line 411) and no committed file holds the server's counters. Under Rule #10 an unreconcilable number cannot justify a design, and two documents already rest on this one. | Carmack, verified in-session |
  | 2 | The readers are real and named. `docs/architecture/summarize/throughput.md` line 8 says the rates come from the item-health ledger and line 19 publishes 10.95 tok/s read as a headline. `frontend/src/routes/console/+page.server.ts` lines 109-112 and 291-295 read the same four columns. Neither reads a log. | Jony, Carmack |
  | 3 | Half the disagreement is a definition, not a defect, and the row fixes the definition first. `backend/idhazh/contracts/summary.py` line 156 says `input_tokens` minus `cached_tokens` is what `prefill_ms` paid for. The 1.8x gap between 11.09 and 19.96 is entirely that subtraction. Whichever the console and the doc use, they must say which, in the same commit. | Andre |
  | 4 | `--metrics` is already on and already scraped at `.github/workflows/digest.yml` lines 385-399, and the output goes only to the job log. Committing the scrape is a small, typed addition to a surface that already exists, not new instrumentation. | Carmack |
  | 5 | Level 4: a new persisted contract plus a workflow change plus two documents. `CLAUDE.md` section 6 wants a breakdown before code, and this row is it. It is NOT Level 5 - it adds an observation surface and changes no existing persisted shape, no band and no reader-facing promise. | Fowler |
  | 6 | If the snapshot belongs on `RunManifest` rather than in a file of its own, that is Fowler's call before any field is added, because swap-plan rows 2-4 also open that contract. | Fowler, ESCALATE trigger 5 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Raise `retention-days` on `runtime-log-*` and reconcile by hand | 2 days becomes 30 and the answer still expires. Rule #10 wants the evidence to survive with the claim, and a committed row is the only thing that does | Carmack |
  | 2 | Trust the ledger and delete the log scrape | The ledger sums a client-side field per request. The server's counters are the independent instrument, and deleting the second instrument to end a disagreement is how a wrong number becomes permanent | Andre |
  | 3 | Correct the doc's headline number and close the finding | The number would be corrected against the same unreconciled source that produced it | Andre |
  | 4 | Fold the definition fix into row 3 and drop the rest | Row 3 is a new eval column. This is a timing contract two published surfaces read | Fowler |
  | 5 | Scrape per request instead of once at job end | Both counters are cumulative, so a per-request scrape adds requests to the thing it measures and still reports only the last one - already ruled in PR #95 | Carmack |

## See also

- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - the orchestrator contract this plan is run under.
- [`../docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) - the commands behind every acceptance gate above.
- [`../docs/reference/github-actions.md`](../docs/reference/github-actions.md) - what each workflow owns.
- [`../docs/reference/measurements.md`](../docs/reference/measurements.md) - where rows 7 and 9 record their numbers.
- [`../docs/reference/agent-notes.md`](../docs/reference/agent-notes.md) - execution traps, including the three this plan's authoring session added.
- [`../docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the instrument row 3 extends and the run-day clock it must not reset.
- [`../docs/architecture/summarize/throughput.md`](../docs/architecture/summarize/throughput.md) - the page row 9 makes checkable.
- [`20260825-qwen35-9b-swap-plan.md`](20260825-qwen35-9b-swap-plan.md) - owner of everything in section 3.
- [`20260823-known-defects-plan.md`](20260823-known-defects-plan.md) - defect 2's run-day clock, which ESCALATE trigger 4 protects.
