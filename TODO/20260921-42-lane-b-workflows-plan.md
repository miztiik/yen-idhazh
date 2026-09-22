# Lane B - the model file is the interface, and the workflows stop being a closed world

**Last Updated**: 2026-09-21

**Level**: 5, and two rows are why. **Row 7 strengthens Guardrail #11's control** - it closes a path-traversal hole in the field checker that every download path runs through, which is the trust boundary and a Level-5 surface by CLAUDE.md section 6. **Row 9 changes a cache key five callers share**, and a half-done change leaves a key whose skip condition lies. Every other row here is Level 2 or 3 and runs AUTO once the user authorizes; those two PAUSE for the owner before their pull request opens (docs/how-to/execute-a-plan.md, section Escalation).

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight - two is the peak the per-row `Files touched` lists allow and section 1's readiness table says why - refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | One JSON file already says where a model's bytes come from, and its contents travel through a Python printer, job outputs, composite-action inputs and environment variables before a `curl` sees them - **161 lines across 8 files, 88 of them there to carry a second file**. The arity is welded at two, so a model that ships three files cannot be described. `model_refs.py:34` refuses only whitespace, so a `file` value of `../../x` reaches `-o "backend/models/${WEIGHTS_FILE}"`. The cache key at `action.yml:93` names the weights and the build and **no companion at all**, so a restored hit can be missing a file the model declared. Meanwhile every work shard installs a graphics-card build of PyTorch onto a runner with no graphics card, and `backend/tests/workflows/` is 11,659 lines guarding 6,216 lines of `.github/` - of 24 assertions a careful reading kept, ten name a defect. |
| The rule | **The model json is the interface. It names every file the model needs and where each comes from; one reader turns that into downloads, checks and a cache key. Everything else that relays a model fact through a workflow is deleted.** Owner ruling 2026-09-21. |
| The second rule | **A validator earns its place where this project's own code is the thing that could be wrong.** Elsewhere the producer writes, the consumer reads, and a mistake fails loudly at the moment it is made. |
| The third rule | **Where a check is worth keeping, keep it in the thing that runs, not in a test against a recorded fixture.** A step that counts and prints reports on the real build on every run. Five of the fourteen test removals below are this move, not a loss. |
| The measure | **Edits per future change, and minutes off the front of a shard.** Lines are the smaller number and the easier one to report. |
| Hard scope - in | Give the model file a `companion_files` list and make one printer verb emit the whole file set, with the path-segment rule that closes the traversal. Make the fetch script read a config root and loop, so the four relay hops and the four draft inputs disappear. Name the cache by the set the model declares, and give the runtime binary its own key. Stop the faithfulness install pulling a graphics-card wheel. Make the plan job close the clock it already opens. Delete the capability probe workflow. Delete the image benchmark and the three undeclared packages it installs. Cut five workflow test modules to the ten assertions that name a defect, moving five of the removals into the step or module they were checking. Make the benchmark arms notice a dead server in two seconds, and the repeat count a config value. Cut the test-support module to what more than one module reads. |
| Hard scope - out | See the table below. |
| Supersedes | Plan 39 rows 3 (workflow half), 4, 9, 10, 13, 14 and 20, which are `COLLAPSED` in that plan's Reckoner. Plan 39 row 5 sits in plan 40 row 1. |
| Assumes | **Plan 41 is DONE before row 8 starts.** Specifically plan 41 row 3 must have relocated the draft block into `companion_files` and retyped `ModelRef.draft`, and row 5 must have rewritten the five model files. Rows 1 to 6 assume nothing and may start today. |
| Hands to plan 41 | Six items this plan does not own, listed in section 1b. **The largest is the `companion_files` shape itself: plan 41 declares it, plan 42 declares its reader.** |
| ESCALATE triggers | (1) Row 8 moves the fetch off the environment relay. **The unconditional restore-time check survives as a workflow step with no `if:`** - if the only digest check ends up inside the script, stop: the script runs behind `cache-hit != 'true'`, so a restored entry would never be checked again, which is the exact case that step exists for. (2) Row 9 changes the cache key shape. The two cache paths must be **disjoint** (`backend/models` and `backend/bin`), or a hit on one key restores files the other owns and its skip condition lies. (3) Row 7 closes a path-traversal hole. Its refusal cases ship with it, in the same commit. (4) Row 6 converts written lists to computed ones. Every converted check asserts its computed list is **non-empty**, or the row stops. (5) Row 5 moves five checks out of tests. Each move ships in the same commit as the deletion it replaces. (6) **`tests/fixtures/runtime/b10598-llama-server-help.txt` is not deleted by any row here** - see C3. (7) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Six pull requests in four waves, grouped so no two in flight own a file in common. Carmack rules the runtime and the fetch path, Fowler the contracts, the test tiers and the module structure, Andre the evaluation integrity. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` Two, not the default four, because rows 1 to 4 are the only ones with no predecessor and they fall into exactly two disjoint file sets. Section 1's readiness table is the dispatcher's input. **Two preconditions before any dispatch, from `docs/reference/agent-notes/shell-and-tools.md:121-129` and from what that cost plan 41:** prove delegation works with one real read-only nested invocation, because the refusal is silent rather than an error; and put in every brief that a worker commits before any long gate and leaves the full suite to CI. A worker whose nested turn ends mid-gate returns an empty report and opens no pull request, which reads exactly like a worker that did nothing - **ask the worktree with `git -C <worktree> status --porcelain` before concluding anything, because re-dispatching the row throws its edits away.** |

### Hard scope - out

Every line here is a dated decision with a price, never a law (CLAUDE.md section 0d).

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Folding the `plan` job into `work`** | The plan job keeps its own provisioning, 0.41 min (`docs/reference/benchmarks/what-a-bench-dispatch-costs.md:26`) | **Refused as written; what the owner wants is priced instead.** `backend/idhazh/stages/plan.py:135` reads every feed over the network and line 100 stamps the clock, so four shards planning independently read feeds at four instants - articles summarised twice under two addresses, others never, and every source read 4 to 8 times a run. The matrix is circular too: `max-parallel` and `matrix.shard` at `digest.yml:409-411` come from the plan job and resolve before any step runs. **What gets the overlap: a cheap `decide` job** carrying the date, model refs, pin and a fanout read from `run.max_parallel`. `work` then needs only `decide`, runs its prelude beside the plan job, and blocks on the plan artifact with a bounded `gh api` poll. That hides the whole plan job behind a 5 to 6 min prelude - 2.6 to 3.6 percent of an 83.5 to 117.5 min slowest shard (`docs/reference/pipeline-cost.md:478`). About 120 lines in `digest.yml`. **Next plan, and row 2 here is its instrument: take the measurement before spending the lines.** Carmack |
| **Moving the plan job's `state` commit onto assemble's** | One commit, one push and one rebase-retry stay in the plan job | First sight is the only age an undated article has, and a feed never recorded cannot be quarantined. The run that dies in `work` is the run whose feed health matters most and the one that would lose both ledgers. Saving is an estimate, labelled: 10 to 20 s, under 0.3 percent of a run. The `decide` split takes it off the critical path without touching it. Carmack |
| **One composite action for the four callers that fetch, verify, start and health-check as a unit** | Four sites keep their own spelling of four steps | A countable condition: **how many merged pull requests in the last quarter changed more than one of the four in the same commit.** Zero means four copies cost nothing. Two or more means the action pays for itself. **Row 11's closure takes that count** - one `git log`. A fifth caller brings it in immediately. Carmack |
| **A model file naming its own llama build** (plan 39 row 5) | This plan keeps the repository-wide pin as the only build | A generic interface, not a fork special case, and about eight lines. It sits in plan 40 row 1 because that is where the first model file wanting a different binary is declared. **The guard it owes:** refuse a qualification whose recorded build is not the build the qualified model entry declares, with `UNRECORDED_BUILD` refused outright. `backend/idhazh/fingerprint.py:103` already records the value |
| **Collapsing the four `commit-and-push.sh` calls in `digest.yml`** (plan 39 row 20) | Four calls stay | Nothing. Three of the four are in three different jobs on three runners, one inside a sharded matrix. The remaining pair is separated by a prune step whose comment says the fold deletes a committed file and may only run after the push. **Mergeable: zero of four.** Carmack |
| **Splitting `_harness.py` into four files** | The module keeps four answers in one file after row 11 cuts it | The right end state, and a separate structural pull request. One addition buys one cut. Fowler |
| **Re-filing the band-ladder and prompt-prose tests out of `test_summarize.py`** | ~20 prompt tests and the band-ladder block stay in a module about the worker | `backend/tests/test_summarize.py` is **pipeline tests throughout - zero of its tests grade a summary**, and its docstring holds the line. But `:1361-1502` tests `SummarizeConfig` rather than the worker and belongs beside the other knobs contracts, and `:1442` pins the literal `200` against a tunable. Filing questions, one row in a later plan. Fowler |
| The `langfuse` extra | 32,656,612 bytes and a measured 260.9 s mean install (n=3, `pyproject.toml:183-191`) stay declared | No workflow installs it and `.[dev]` does not carry it, so it costs CI zero and names its beneficiary. It leaves with plan 39 row 15, which deletes the sink it serves |
| `test_staged_paths.py`, `test_daily_commit_steps.py`, `test_commit_script.py`, `test_triggers.py` | 1,572 lines stay | The commit surface is not this lane's. **`test_triggers.py:191-199` is the workflow-side control for Guardrail #11** - closed-world over every declared dispatch input, asserting a read-by-name input never appears in a `run:` body. Row 6's shrink must not reach it. Andre |
| `shard_bound.py` at `digest.yml:198` and the `work` matrix at `digest.yml:409-411` | Two values keep travelling as job outputs | **They look like the relay this plan closes and are not.** `timeout-minutes` and `strategy.matrix` are job-level keys Actions resolves before any step runs, so they must be expressions over a prior job's output. Named here so nobody "fixes" them. Fowler |

### What a change costs today

Measured on the tree at `origin/main`, 2026-09-21, except where a row says estimate.

| Reading | Value | Where |
| --- | --- | --- |
| Lines relaying one JSON file's contents to a `curl` | **161 across 8 files, 88 of them draft-specific** | `model_refs.py`, the models step in five workflows, `action.yml`, `fetch-model-runtime.sh` |
| Hops from the model file to the download | **4** - printer, job output, action input, environment | `model_refs.py` -> `$GITHUB_OUTPUT` -> `action.yml:107-115` -> `fetch-model-runtime.sh:30-32` |
| Files a model file can declare | **exactly 2**, welded | `DRAFT_FIELDS` at `model_refs.py:27`, `_draft_rows` at `:63`, `_cache_key` at `:79` concatenating two digests |
| Composite action inputs | **10, of which 4 are draft** | `.github/actions/model-server/action.yml:12-47` |
| Companion files a committed model actually declares | **1** - `mtp-gemma-4-E4B-it.gguf`, 59,678,016 bytes, 1.4 percent of the weights | `config/models/gemma-4-e4b-qat.json:5-15`, and a benchmark page about it at `docs/reference/benchmarks/what-the-draft-head-is-worth.md` |
| Companion files the weights cache key names | **0** | `action.yml:93` keys on weights file, weights revision and build. Masked only because the live pointer `models/qwen3.5-9b-q4km.json` declares none |
| What `one_bare_word` refuses | **whitespace only** - `../../x` passes and reaches a `-o` destination | `model_refs.py:34-45` into `fetch-model-runtime.sh:42` |
| Inline Python programs walking a model file inside a workflow | **6** | `action.yml:136`, `:183`; `idhazh-pipeline-tests.yaml:196`, `:274`, `:354`; `measure.yml:1171` |
| Front of every work shard, `.[faithfulness]` install | **4 min** against **0.41 min** plain - about **3.6 min**, and shards run in parallel so that is run wall clock, every run | `docs/archive/measurements-2026-08.md:1933`, `docs/reference/benchmarks/what-a-bench-dispatch-costs.md:26` |
| That against the critical path | **3 to 4 percent** of an 83.5 to 117.5 min slowest shard | `docs/reference/pipeline-cost.md:478` |
| Workflows naming a wheel index when installing PyTorch | **1 of 3**, and it is the one being deleted | `measure.yml:430` names the processor-only index; `digest.yml:443` and `validate.yml:243` name none |
| What one cache orphaning actually costs | **about 75 s of run wall clock, once** - a cold download adds 57 to 338 s over the restore it replaces, median about 75, and the most the cache can ever save is 0.6 percent of a dispatch | `docs/reference/benchmarks/what-a-bench-dispatch-costs.md:118-130`. **An earlier draft of this plan said 1.5 to 2.5 minutes per shard; that compared a cold fetch against a free restore and was wrong** |
| Committed duration for the plan job | **none** | `digest.yml:243-262` opens a `HostFingerprintRow` with `--job plan` and never closes it |
| Test lines guarding workflow lines | 11,659 guarding 6,216 - a ratio of **1.88** | `backend/tests/workflows/*.py` against `.github/**` |
| Assertions a careful reading kept, of which name a defect | **24 kept, 10 name a defect** | C4 |
| Constant tables to edit before a new server-starting job passes | **5** | `EXPECTED_WORKFLOWS`, `MODEL_SERVER_CALLERS`, `SERVER_STARTERS`, `WEIGHTS_CHECKS`, `LLAMA_RUNTIME_WORKFLOWS` |
| Places the llama.cpp pin is written | **3** | `llama-cpp-pin.sh:26-28`, `measure.yml:102-104`, `_harness.py:218-222` |
| Top-level names in `_harness.py` | **255** in 2,361 lines | 36 imported by nobody, 151 by exactly one module, 43 by two or three, 25 by four or more |
| Seconds before a benchmark arm notices llama-server died at start | **900** at `measure.yml:989`, **600** at `runtime_sweep.py:284`, against **2** in `digest.yml` and `validate.yml` | `start-llama-server.sh:67` does `sleep 2; kill -0`; the two benchmark arms nohup inline and never check |

## Section 0b - What this plan does, in one list

Eleven rows, six pull requests, four waves.

1. Stop the faithfulness install pulling a graphics-card wheel onto a runner with no graphics card.
2. Make the plan job close the clock it already opens.
3. Delete the capability probe workflow.
4. Delete the image benchmark, its job, its utility, its extras, and three undeclared installs with it.
5. Move five checks out of tests and into the step or module they were checking.
6. Delete fourteen assertions that name an author's choice, and compute every list the repository can compute.
7. Teach the printer the whole file set, and close the path-traversal hole in it.
8. Make the workflows read the model file instead of relaying it: the script loops, the action drops to five inputs, six inline JSON walks go.
9. Name the cache by the set the model declares, and give the runtime binary its own key.
10. Make the benchmark arms notice a dead server in two seconds, and the repeat count a config value.
11. Cut the test-support module to the names more than one module reads.

## Section 1 - Status Reckoner

**A pull request is one worktree, one branch, one review. A pull request is ready when every row's `Depends-on` is DONE and its owned files (section 1a) are disjoint from every pull request in flight.**

| # | Row title | PR | Depends-on | Parallel-group | Status | Worktree | PR link | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The runner stops paying for a graphics card it does not have | P1 | - | **M** | DONE | p42p1 | #1034 | P1 |
| 2 | The plan job closes the clock it opens | P1 | 1 | **M** | DONE | p42p1 | #1034 | P1 |
| 3 | The capability probe goes | P2 | - | A | DONE | p42p2 | - | P2 |
| 4 | The image benchmark goes | P2 | 3 | A | DONE | p42p2 | - | P2 |
| 5 | Five checks move into the thing they check | P3 | 2, 4 | B | DONE | p42p3 | - | P3 |
| 6 | Fourteen assertions go, and the lists become computed | P3 | 5 | B | DONE | p42p3 | - | P3 |
| 7 | The printer learns the whole file set, and the traversal closes | P4 | 6, plan 41 | C | COLLAPSED - plan 44 row 1; the grammar is imported from `measure_llm.py` rather than written a fourth time | - | - | - |
| 8 | The workflows read the model file instead of relaying it | P4 | 7 | C | COLLAPSED - plan 44 row 2; its grep oracle is scoped to jobs reaching the action or the script | - | - | - |
| 9 | The cache names the set, and the binary gets its own key | P4 | 8 | C | COLLAPSED - plan 44 row 3; the set-digest half only, the `backend/bin` split refused and priced | - | - | - |
| 10 | The benchmark arms learn the server died, and the repeat count is config | P5 | 9 | D | COLLAPSED - plan 44 row 4, which is DONE; a 2 s exit check in FRONT of an unchanged readiness wait | - | - | - |
| 11 | The harness keeps only what more than one module reads | P6 | 9 | D | COLLAPSED - plan 44 row 5; the ratio gate in C13 is deleted as unreachable and inverted | - | - | - |

### The six pull requests and the files each owns

**Rows 7 to 11 are executed from [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md), not from here.** That plan re-measured this one against the tree rows 1 to 6 left behind, and four load-bearing facts here had rotted. **Every `measure.yml` line number below 449 in this plan is off by 35**, because rows 3 and 4 deleted the image job. C11's harness table was wrong within a day: 242 names rather than 255, and the orphan count had risen from 36 to 45, because deleting a consumer orphans what only it imported. C13's ratio gate needs 3,088 more lines out of `backend/tests/workflows/`, row 11 is a move that removes none of them, and rows 8 and 9 shrink the denominator and push the ratio the wrong way. And section 1b's six owed items are all already written on plan 41's branch, leaving a merge order as the only real coupling. Read plan 44 for rows 7 to 11 and treat the sections below as the record of what was decided, not as instructions.

**Two pull requests never own one file. That is what lets the pool run two at a time.**

| Wave | PR | Rows | Files it owns, exclusively | Commits, in order |
| --- | --- | --- | --- | --- |
| 1 | **P1 - the install and the clock** | 1, 2 | `digest.yml`, `validate.yml`, `docs/how-to/run-the-gates.md` | (a) the wheel index; (b) the plan job clock. Both behavioural |
| 1 | **P2 - two dead benchmarks** | 3, 4 | `probe.yml`, `backend/utilities/bench_image.py`, the `image` job in `measure.yml`, `pyproject.toml`, six doc pages, `_harness.py` **delete-only** | (a) the probe; (b) the image benchmark. Both behavioural |
| 2 | **P3 - the test modules** | 5, 6 | `test_bench_targets.py`, `test_model_server_jobs.py`, `test_script_invocation.py`, `test_bench_input_drift.py`, `candidate_pointer.py`, `measure_llm.py`, the memory sampler's print, `digest.yml` L737 only, `_harness.py` **delete-only** | (a) the five MOVEs, each with its new unit test - **behavioural**; (b) the fourteen deletions and the discovery conversions - **structural** |
| 3 | **P4 - the model file is the fetch interface** | 7, 8, 9 | `model_refs.py`, `fetch-model-runtime.sh`, `action.yml`, `digest.yml`, `llm-council.yml`, `validate.yml`, `idhazh-pipeline-tests.yaml`, `measure.yml`, `test_weights_and_model_refs.py`, `test_pinned_versions.py` | (a) the printer plus the path-segment rule, calling nothing; (b) the script loops and every caller repoints; (c) the cache split. All behavioural |
| 4 | **P5 - liveness and the repeat count** | 10 | `measure.yml` L989, `runtime_sweep.py`, `backend/idhazh/contracts/knobs/bench.py`, `config/idhazh.json` | one commit, behavioural |
| 4 | **P6 - the harness** | 11 | `_harness.py` and its 22 consumers | one commit, structural |

**Why P3 stacks on P1 and P2 rather than running beside them.** P2 deletes the image cases inside `test_bench_targets.py` while P3 rewrites six other assertions in the same module, and P3's oracle - a new server-starting workflow passing with no constant edited - is only meaningful on the tree P2 leaves. P3 also edits `digest.yml` L737, which P1 owns until it merges.

**Why P4 runs alone.** After the reversal it owns every workflow file. That is arithmetic, not churn avoidance.

**Why P5 and P6 are two pull requests.** P5 is behavioural and P6 is structural, and they own disjoint files, so they run at once in the last wave.

**Peak workers: 2.** The pool never has more than two ready rows with disjoint file lists.

### Readiness, computed rather than read off a letter

**A row is ready when every `Depends-on` is DONE and its `Files touched` list shares no entry with a row already in flight.** `Parallel-group` is the author's hint; the file lists in sections 2 to 12 are the fact, and the owner diffs them before every dispatch (docs/how-to/execute-a-plan.md, section Parallel fan-out). What that computes to here:

| At this point | Ready together | Held, and why |
| --- | --- | --- |
| start | **1 and 3** | 2 waits on 1; 4 waits on 3 |
| after 1 and 3 return | **2 and 4** | 5 shares `digest.yml` with 2 and `test_bench_targets.py` with 4 |
| after P1 and P2 merge | **5**, then **6** | one worker, one branch. 7 waits on plan 41 |
| after P3 merges and plan 41 is DONE | **7**, then **8**, then **9** | P4 owns every workflow file, so nothing runs beside it. That is arithmetic, not caution |
| after P4 merges | **10 and 11** | disjoint files, and one is behavioural while the other is structural |

**Group M runs alone and does not overlap a merge into `digest.yml`.** Row 1's oracle is the next nightly run's own job log, so any other change landing in `digest.yml` between its merge and that nightly makes the timing unattributable - which is the whole reason row 1 is not bundled with the deletions.

### What each row's oracle is, so the owner knows what to run against the base tree

The contract asks the owner to run a row's check against the base tree before dispatching, and to say which of two kinds it is (docs/how-to/execute-a-plan.md, section The owner, point 2).

| Row | Kind | What must be able to fail |
| --- | --- | --- |
| 1 | **runner-only** | nothing local can fail it. The nightly's install log is the check, and it is read after the merge |
| 2 | fails on the base tree | today no host-fingerprint row carries `job=plan` with a `job_seconds` |
| 3, 4 | fails on the base tree | the census finds `probe.yml` and `diffusers` today |
| 5 | fails on the base tree | each of the five new unit tests fails with its move reverted |
| 6 | fails on the base tree | a throwaway server-starting workflow fails the suite today, on five constants |
| 7 | fails on the base tree | the traversal cases pass today, which is the defect |
| 8 | **runner-only for the download half**; the grep half fails on the base tree | a dispatch is the only thing that can prove the loop fetches |
| 9 | **runner-only, and it needs two dispatches** | a miss then a hit. The hit is the half that fails quietly |
| 10 | fails on the base tree | a dead server takes 900 s and 600 s to notice |
| 11 | **behaviour must not change** | the collected test count is identical at both ends by design; what must not break is that every moved name still has its importer. Do not invent a failing check to satisfy a rule |

### The page that owns each surface, so a worker does not re-route

`docs/agents/bootstrap.md` routes. For this plan it resolves to four pages and no more.

| Surface a row touches | Page that owns it |
| --- | --- |
| a workflow, a gate, or what CI runs - **every row** | [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) |
| a persisted shape - rows 2 and 10 | `CLAUDE.md` section 11, then the model under `backend/idhazh/contracts/` |
| which model runs, or a figure that belongs to one - rows 7, 8, 9 | [`docs/reference/models.md`](../docs/reference/models.md), and the dossier it points at |
| anything fetched text reaches - row 7 | `CLAUDE.md` Guardrail #11 |

The two reference pages this plan **writes** are [`docs/reference/ci-model-runtime.md`](../docs/reference/ci-model-runtime.md) (rows 3, 8, 11) and [`docs/reference/github-actions.md`](../docs/reference/github-actions.md) (rows 3, 8).

### The gates, named once so no row repeats them

Every command below is from [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md). A row's Acceptance gates line names which of these apply; it never introduces a new one.

| Check | Command |
| --- | --- |
| the named module | `.\.venv\Scripts\python.exe -m pytest -n 0 backend/tests/<module>.py` |
| lint and types | `.\.venv\Scripts\python.exe -m ruff check .` then `.\.venv\Scripts\python.exe -m mypy` |
| shell, for rows 8, 9, 10 | `.\.venv\Scripts\shellcheck.exe --severity=style (Get-ChildItem .github/scripts/*.sh).FullName` - **PowerShell does not expand a glob, so the paths are handed over literally** |
| the expensive ones, when two workers are live | wrap in `python backend/utilities/gate_lock.py -- <command>`. `ruff`, `mypy` and `shellcheck` stay unwrapped |
| documentation load, for rows 3, 8, 11 | `python backend/utilities/doc_load.py` before and after |

**`ruff format` is not a gate.** The full suite belongs to CI; a list of acceptance gates is not an instruction to repeat every CI job locally.

### Two traps that cost a merge, named so nobody meets them cold

1. **No pull request here may carry `TODO/STATUS.md`.** It is generated from every plan's Reckoner by one job on `main` after a merge, and the gates job **fails any pull request that touches it** (`docs/reference/agent-notes/gates-and-builds.md:232`). A worker stamps its own Reckoner line and nothing else. If a merge of `origin/main` picks the page up anyway, take the trunk's copy - `git checkout origin/main -- TODO/STATUS.md` - rather than re-deriving one, because its section headings carry computed counts and a textual merge can be internally inconsistent and still merge cleanly.
2. **No pull-request body here may contain a continuous-integration skip marker, even inside a code span or a table cell.** A squash merge folds the whole body into the commit message and GitHub scans all of it. Measured 2026-09-12: one merge carried such a marker inside a table row that was arguing against using it, and the push created zero workflow runs - not the suite, and not the Pages publication the change never touched (`gates-and-builds.md:244`). Several rows here discuss workflow triggers, so this is a live risk rather than a general caution.

## Section 1a - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent one of these; it reads this section.**

### C1 - The composite action's inputs, after row 8

`.github/actions/model-server/action.yml`. **Ten inputs become five.** Each survivor is a fact a config file cannot hold.

| Input | Required | Who reads it | Why it cannot come from the model file |
| --- | --- | --- | --- |
| `github_token` | yes | the release lookup | a secret |
| `port` | yes | the start and health steps | a workflow fact |
| `llama_cpp_build` | yes | the runtime cache key | a repository pin, not a model fact |
| `config_root` | yes | the printer, the verify step, the health check | **new** - which config tree this dispatch runs on. Default `config` |
| `models_cache_key` | yes | `actions/cache` | **new** - the set digest, computed once by the caller's models job so the action and the caller cannot disagree |

**Deleted: `weights_repo`, `weights_revision`, `weights_file`, `draft_repo`, `draft_revision`, `draft_file`, `draft_sha256`.** With `config_root` in hand the health check reads the loaded path and the alias from the file, which closes the relay rather than narrowing it - `action.yml:183` already proves the action can read the file itself.

### C2 - The two cache keys, after row 9

| Key | Path | Shape |
| --- | --- | --- |
| `models-<set digest>` | `backend/models` | the digest below. Names the whole declared set |
| `runtime-<llama build>` | `backend/bin` | the pin tag |

**The set digest** is the first 16 hex characters of the SHA-256 over the newline-joined, sorted `<sha256>  <filename>` rows for every declared file, weights first in the listing but sorted for the digest. Fixed length at any arity; changes exactly when a declared file changes; computed by the same function that emits the fetch list, so the key cannot name a set different from what is downloaded.

**The two paths are disjoint and must stay disjoint** (ESCALATE trigger 2). A hit on one key restoring files the other owns makes that key's skip condition lie.

**Five sites change together**: `action.yml:87-93`, `idhazh-pipeline-tests.yaml:167`, `measure.yml:266`, `:581`, `:910`, `validate.yml:278`.

**Why now rather than later.** `<weights_file>-<weights_revision>` cannot name a variable file set, so the key shape changes whatever else happens. Doing the arity change now and the weights-binary split later orphans twice. One orphaning costs about 75 s of run wall clock, once.

**The unconditional restore-time verify survives** and now covers the whole set. See C5.

### C3 - What leaves the repository, and what does not

| Path | Lines | Row |
| --- | --- | --- |
| `.github/workflows/probe.yml` | 136 | 3 |
| `backend/utilities/bench_image.py` | 168 | 4 |
| `measure.yml` job `image` | 34 (L416-449) | 4 |
| the `bench-image` extra and the empty `measure = []` extra | `pyproject.toml:144-150` | 4 |
| `backend/tests/workflows/test_bench_input_drift.py` | 198 | 6 |
| the four `tests/fixtures/runtime/2026-08-29-3-shard-*.server-head.txt` captures | - | 6 |
| the four draft inputs on the action, `DRAFT_FIELDS`, `_draft_rows`, `_cache_key`'s concatenation, both hand-written `curl` blocks, six inline JSON walks | ~120 | 7, 8 |

**What stays, and why - two of these an earlier draft of this plan got wrong:**

| Path | Why it stays |
| --- | --- |
| `tests/fixtures/runtime/b10598-llama-server-help.txt` (705 lines) | `server.py:824` reads `UNCAPPED_N_PREDICT if max_think_tokens is None else max_think_tokens`, so deleting the caps collapses it to `-1` and **`UNCAPPED_N_PREDICT` keeps a production caller**. `backend/tests/test_summarize.py:1776` keeps its subject. `docs/reference/models/gemma-4-e4b-qat.md:254` cites it as the recorded `--spec-type` list from run `34971210901`. ESCALATE trigger 6 |
| `.github/scripts/install-llama-runtime.sh` (45 lines) | `fetch-model-runtime.sh:35` **sources** it, and that script has three live callers. It is the build half of a live path, and it is what row 9's `runtime-<build>` key caches |
| `config/models/gemma-4-e4b-qat.json`'s companion, and `gemma-4-e4b-qat-no-draft.json` | The 2026-09-12 measurement found the head is not output-identical. **That argues against enabling it by default, not against the file existing.** The no-draft entry exists solely as its control and is read by `backend/tests/contracts/test_model_registry.py:396`. The pair is the only committed instrument for the question, the companion is 0.06 GB against a 10 GB allowance, and the live pointer declares no companion so production fetches none either way |
| `.github/scripts/start-llama-server.sh` | Unchanged |
| `backend/tests/workflows/test_runtime_accepts.py` | Plan 41 row 3 deletes it, in the commit that deletes `SpeculationType` |

### C4 - The assertions that survive, and the fourteen that do not (rows 5, 6)

**A worker deletes everything in these five modules that is not marked KEEP, and ships each MOVE in the same commit as the deletion it replaces** (ESCALATE trigger 5). Line numbers on `origin/main`, 2026-09-21.

| Module and line | What the test is for | Verdict |
| --- | --- | --- |
| `test_bench_targets.py:78` (106-110) | three benchmark jobs spell one weights cache key identically | **REMOVE** - a cache miss is already printed in the run log |
| `test_bench_targets.py:177` | the benchmark measures a scratch config copy, not the committed one | **MOVE** to `candidate_pointer.py`'s unit test, where it covers every caller |
| `test_bench_targets.py:240` | server case reads the raw case's artifact | **REMOVE** - a missing directory already fails the emit step loudly |
| `test_bench_targets.py:273` | the raw case passes `--expect-sha256` | **MOVE** - make the flag required in `measure_llm.py` |
| `test_bench_targets.py:436` | a benchmark machine row lands in the benchmark state root only | **KEEP** - silent, and it reaches a published operator panel |
| `test_bench_targets.py:587` | every pipeline stage a benchmark runs gets the scratch config | **KEEP** the discovery, drop its closed-world tail - already cost a published day |
| `test_model_server_jobs.py:229` | the start script exits 2 on a role it cannot serve | **KEEP** - drives our own shipped script, about thirty lines |
| `test_model_server_jobs.py:255` | a locked-memory refusal does not hide a missing server binary | **REMOVE** - the script's own `sleep 2; kill -0` catches it; eight exact strings are authorship |
| `test_model_server_jobs.py:341` | sampler columns and the operator print agree by position | **MOVE** - make the print read the header by name; the class of defect dies |
| `test_model_server_jobs.py:367` | the kernel memory peak is copied once and printed from the copy | **REMOVE** - a job log a person reads, and a small disagreement |
| `test_model_server_jobs.py:420`, `:447` | our grep patterns match llama.cpp's own log format | **MOVE** - two lines in the step at `digest.yml:737`: count matched, count total, echo `matched N of M` |
| `test_weights_and_model_refs.py:69` | every weights download uses `curl -f` and retries | **REMOVE**, and row 8 strengthens the reason: after it there is **one `curl` in the repository**, inside a shellchecked script |
| `test_weights_and_model_refs.py:88` | every fetched file is checked before anything reads it | **KEEP, with a new body.** See C5 - it becomes the restore-time half and it is the one control on every byte this project downloads |
| `test_weights_and_model_refs.py:119` | the health check compares the served alias and the loaded file | **REMOVE as its own test**, folding its comparison into the row below |
| `test_weights_and_model_refs.py:138` | every step waiting on health also asks which model answered | **KEEP**, absorbing the row above |
| `test_weights_and_model_refs.py:182` | no workflow writes a model reference or a branch reference | **KEEP - and it is now load-bearing rather than incidental.** Once the model json is the only place a model is named, this is the rule that keeps it that way |
| `test_weights_and_model_refs.py:372` | every config key an inline program indexes exists in the file | **REMOVE** - row 8 deletes six of the inline programs, and the failure is a loud crash |
| `test_weights_and_model_refs.py:415` | no inline program rebinds a name it read from the environment | **REMOVE - vacuous.** Zero of the eight inline programs bind from `os.environ`, so it passes by finding nothing, and it carries no anti-vacuity anchor. `test_triggers.py:191-199` is the Guardrail #11 holder |
| `test_weights_and_model_refs.py:456` | the weights cache key names the model and the build | **KEEP, with a second clause**: the key names **every** file in the declared set, and the two cache paths are disjoint |
| `test_pinned_versions.py:45` | every workflow spells the same pin in its own `env:` | **REMOVE** - its input set is empty after the conversion in row 8 |
| `test_pinned_versions.py:63` | the pin is spelled in exactly one shipped script | **KEEP**, reduced to the four discovery checks in C6 |
| `test_pinned_versions.py:136` | the llama.cpp fetch is pinned and digest-checked | **REMOVE as its own test** - one line inside the row above |
| `test_pinned_versions.py:151` | nobody takes whichever release is newest | **REMOVE as its own test** - same, folded |
| `test_pinned_versions.py:167` | every action is pinned to an approved major | **REMOVE the approval table**, keep one line: every non-local `uses` carries an `@` |
| `test_pinned_versions.py:197` | the Python pin sits inside the declared interpreter range | **KEEP** - pip falls back to a source build and hangs silently in a six-hour job |
| `test_script_invocation.py:68` | a script named as a bare command is committed executable | **KEEP** - a Windows checkout cannot show the bit, and this is its only reader |
| `test_script_invocation.py:99` | every shipped script is run by a workflow, and conversely | **REMOVE.** One direction is exit 127 in seconds; the other is tidiness |
| `test_bench_input_drift.py`, all 8 | a form's options match a module's options | **REMOVE the file** |

**Ten KEEP, five MOVE, fourteen REMOVE.** The three questions that decided each: can a run break it or only a person; is the failure already loud on the runner; would a cheaper instrument inside the workflow report the same fact on every real run.

### C5 - The one control on every byte, after the fetch moves (rows 8, 9)

**Answering the owner's question: it is a SHA-256 checksum.** `action.yml:128` runs `sha256sum --check` against the digest recorded in the model file, in a step carrying **no `if:`**, positioned after the fetch and before anything reads `backend/models`.

**The check splits in two, and the split is what keeps the property.**

| Half | Where | Oracle |
| --- | --- | --- |
| download-time | inside `fetch-model-runtime.sh`, per row, immediately after each `curl` | the dispatch |
| **restore-time** | a workflow step with **no `if:`**, in every caller | **the surviving test** |

The reason both are needed: the fetch script runs behind `cache-hit != 'true'` (`action.yml:105`). Put the only check inside the script and a restored entry is never checked again - the exact case that step exists for (ESCALATE trigger 1).

**The surviving assertion**, replacing the body of `test_weights_and_model_refs.py:88` in place:

`test_every_file_a_model_declares_is_checked_after_a_restore` asserts four things.

1. The set of jobs running `fetch-model-runtime.sh`, directly or through the action, is **discovered and non-empty**.
2. Every such job has a verify step carrying **no `if:`**, after the fetch and before the first step that reads `backend/models`.
3. That step runs `model_refs.py files --config-root <root>` and pipes **every** row to `sha256sum --check` - so it checks the set the model file declares, not one filename spelled in YAML.
4. The root the verify step names **equals** the root the fetch step names. Today that is held by hand and stated only in a comment at `idhazh-pipeline-tests.yaml:189-193`.

**The defect it catches:** a restored entry missing a declared companion, or carrying a stale one, reaching the server. **That defect is live today** - `action.yml:93` names no companion while `model_refs.py:80-92` composes a key over both files and writes down why.

`WEIGHTS_CHECKS` at `_harness.py:300` **dies whole**: after row 8 there is one fetch shape and one verify shape, so all four facts per entry are computable.

### C6 - The one rule for a written list (row 6)

**If the repository can compute the list, compute it - and assert the computed list is non-empty. If the list encodes a judgement the repository does not contain, keep it written down.** ESCALATE trigger 4 governs the non-empty clause.

| Constant | Ruling |
| --- | --- |
| `MODEL_SERVER_CALLERS` | **Discover** - every job carrying `uses: ./.github/actions/model-server`. Non-empty |
| `WEIGHTS_CHECKS` | **Dies whole** after row 8. See C5 |
| `SERVER_STARTERS`, `EXPECTED_WORKFLOWS`, `MEASUREMENT_TARGETS`, `RUNTIME_CANDIDATES`, `APPROVED_ACTION_MAJORS` | computable or pure authorship. They die with the tests that read them |
| `PINNED_LLAMA_BUILD`, `PINNED_LLAMA_ASSET`, `PINNED_LLAMA_SHA256` | **Read from `llama-cpp-pin.sh`**, not duplicated. This takes a pin bump from 3 edits to 1 |
| `LLAMA_SCRIPT_CALLERS`, `LLAMA_INLINE_RUNTIME_WORKFLOWS` | redundant once row 8 converts the last inline caller |
| `RUNTIME_LOG_*` | die with the two log-format assertions |
| `DISPATCH_INPUT_SHAPES` | **stays written** - it encodes the shape an input must have, and `test_triggers.py` is out of scope |

`test_pinned_versions.py:63` keeps four discoveries: no shipped script other than the pin script spells a pin name; the fetch script's call closure reaches the pin script; no workflow carries a pin value in any string; the set of workflows reaching the fetch script is non-empty. The two folded-in one-liners: nobody asks for the newest release, and every llama.cpp fetch names a tag and checks a digest.

### C7 - The `files` verb (row 7)

`backend/utilities/model_refs.py` gains one verb. **The module keeps one question** - "which model files will a shell see, and is every field safe?" - at a new arity.

```
python3 backend/utilities/model_refs.py files --config-root <root>
```

| Column | Content | Absent optional |
| --- | --- | --- |
| 1 | `repo` | - |
| 2 | `revision` | - |
| 3 | `file` | - |
| 4 | `sha256` | - |
| 5 | `flag`, or empty | empty field, never a missing one |

TAB-separated, one row per file, **weights first**, then companions in declared order. Every field has already passed the rules in C8 before it is printed.

**On a malformed entry the verb raises and prints the models file path, the list index and the field name, and exits non-zero.** Not a skip: a skipped companion is a server that fails to start over a missing file, or one that starts and silently does nothing.

**`--config-root` is added to every verb, not only this one.** `configured` and `candidate` today join `CONFIG_DIRNAME` under `--repo-root` (`model_refs.py:52-60`) while the candidate tree is `backend/var/candidate-config` holding `idhazh.json` directly. Two path conventions in one module is the drift this module exists to remove.

**`_cache_key` at `:79-92` is replaced by a function over the printed rows**, so the key is provably a digest of the set the loop downloads.

### C8 - The path-segment rule (row 7)

**This is a security fix, not a new rule.** `one_bare_word` at `model_refs.py:34-45` refuses only whitespace, so `../../x` passes and reaches `-o "backend/models/${WEIGHTS_FILE}"` at `fetch-model-runtime.sh:42`. Severity is low today because model files are committed and reviewed; the hole is closed anyway, and its refusal cases ship in the same commit (ESCALATE trigger 3).

| Field | Rule |
| --- | --- |
| `repo` | one bare word, of the form `owner/name` |
| `revision` | 40 hexadecimal characters. Never a branch name |
| `file` | one bare word **and one path segment**: no `/`, no `\`, not `.`, not `..`, not starting with `.` |
| `sha256` | 64 hexadecimal characters. **Required, no exception** - three fields is a file fetched against a blank digest, and `sha256sum --check` then reports "no properly formatted checksum lines found", naming neither the entry nor the field (`model_refs.py:24-27`) |
| `byte_count` | optional, integer at least 1. Where present it is cross-checked as `validate.yml:325` already does for the weights |
| `flag` | optional, matching `--[a-z0-9-]+` |

**The destination is composed, never interpolated**: a constant directory plus the validated segment. **Two entries resolving to one filename is refused** - one would silently overwrite the other.

### C9 - What `fetch-model-runtime.sh` reads and refuses (row 8)

| Environment | Required |
| --- | --- |
| `GITHUB_TOKEN` | yes - the pinned release lookup |
| `CONFIG_ROOT` | yes - which config tree. No default in the script; the caller passes it |

**Nothing else.** It still refuses any positional argument, as `fetch-model-runtime.sh:25-28` already does. It still sources `install-llama-runtime.sh` at line 35.

**The loop writes the printer's rows to a file, then reads the file.** `printer | while read` runs the body in a subshell, so a failure inside the loop cannot fail the script the way `set -euo pipefail` at line 23 implies. This is a named trap, not a style preference.

Per row: `curl -fsSL --retry 3 --retry-all-errors` to the composed destination, then `sha256sum --check` immediately, then the next row. One `curl` in the repository when this lands.

### C10 - The landed path, computed in exactly one place (rows 7, 8; shared with plan 41)

The fetch composes a landed path and the argv builder reads one. **They must be the same function.** It lives in `backend/idhazh/llm/server.py` and `model_refs.py` imports it - the direction `backend/utilities/llama_argv.py:1-5` already uses.

**This is the cross-plan contract. Unwritten, plans 41 and 42 invent it separately and drift.** Plan 41 row 5 emits `<flag> <landed path>` on the command line; plan 42 row 8 guarantees the path exists and the bytes match.

### C11 - The harness, after row 11

**`_harness.py` holds only names imported by two or more modules, plus the real-git-repo commit-script fixture.** Mechanically checkable. Every name imported by exactly one module moves into that module.

**No line-count target is written down.** Record the before and after as a reading (Guardrail #10).

| Reading | Value, 2026-09-21 |
| --- | --- |
| Top-level names | 255 |
| Imported by nobody | 36 - **grep each as a string before deleting**; two are dead everywhere: `CLOCK_STEP`, `CLOCK_VARIABLES` |
| Imported by exactly one module | 151 |
| Imported by two or three | 43 |
| Imported by four or more | 25 |
| Consumer modules | 22 |

The commit-script fixture stays whole and is not dragged into the move: `test_staged_paths.py`, `test_daily_commit_steps.py` and `test_commit_script.py` all use it.

### C12 - What this plan does not touch

| Surface | Why |
| --- | --- |
| `config/models/`, `backend/idhazh/contracts/knobs/models.py`, `inference.py`, `turns.py`, `backend/idhazh/llm/`, `backend/idhazh/config.py` | Plan 41's. **Exception: C10's landed-path function, which plan 41 row 5 writes and this plan imports.** `backend/idhazh/contracts/knobs/bench.py` is this plan's |
| `backend/utilities/model_refs.py` | **This plan's**, stated because an earlier draft left it unassigned |
| `test_triggers.py`, `test_staged_paths.py`, `test_daily_commit_steps.py`, `test_commit_script.py` | the scope-out table |
| Guardrail #11, Guardrail #12, `CLAUDE.md` | No clause of the engineering contract is contradicted. **Row 7 strengthens Guardrail #11** rather than adapting it |

### C13 - The readings this plan is judged on

Re-measured at P6's close and written into `docs/reference/ci-model-runtime.md` (Guardrail #10).

| Reading | Before | Gate |
| --- | --- | --- |
| Hops from the model file to a download | 4 | **0** - the reader opens the file |
| Files a model file can declare | 2, welded | **any number** |
| Composite action inputs | 10 | **5** |
| Inline Python programs walking a model file in a workflow | 6 | **0** |
| Minutes at the front of every work shard, for wheels | 4 | **under 1**, and the wheel in the log carries a `+cpu` local version |
| Committed duration for the plan job | none | **one cell, every run** |
| Test lines per workflow line | 1.88 (11,659 / 6,216) | **at or under 1.3.** The gate tightens against itself and that is intended: deleting workflow lines shrinks the denominator, so it is reachable only with row 11 |
| Places the llama.cpp pin is written | 3 | **1** |
| Constant tables to edit before a new server-starting job passes | 5 | **0** |
| Seconds before a benchmark arm notices a dead server | 900 and 600 | **2 and 2** |

## Section 1b - What plan 41 owes this plan

Six items. **Plan 41 declares the shape; this plan declares the reader.** Each is a row or a clause in plan 41, not here.

| # | Item | Where in plan 41 |
| --- | --- | --- |
| 1 | **`companion_files` as a block under `<role>`**, beside `server` and `request`: a list whose entries carry `repo`, `revision`, `file`, `sha256`, optional `byte_count`, optional `flag`. The weights stay where they are - retyping them into the list would move `inference.declared_for`, the health check and `--model` for no gain | C1, row 5 |
| 2 | **`spec_type`, `n_max`, `n_min`, `p_min` move into the `server` block** as `--spec-type`, `--spec-draft-n-max`, `--spec-draft-n-min`, `--spec-draft-p-min`. They are decode settings, not source facts | C1, row 5 |
| 3 | **Row 3 relocates rather than deletes.** `SpeculationType` still dies, because row 5 removes every bound and enum. `DraftConfig`'s five source fields relocate into one companion entry; its four decode fields relocate per item 2; `DraftConfig._a_minimum_above_the_maximum_drafts_nothing` dies with the bounds | row 3 |
| 4 | **`ModelRef.draft` is retyped to `Mapping[str, Any] \| None = None`, not deleted**, sharing row 5's version stamp and changelog line. Six committed `run.json` files carry it and the reader forbids extra keys | row 3, C3 |
| 5 | **`backend/tests/contracts/test_model_registry.py:396` is rewritten** from a `draft is None` assertion to a `companion_files` one. It reads a typed field row 3 removes | row 3 |
| 6 | **Row 4 decides whether the thinking span still sends `-1` at all.** `server.py:824` collapses to `UNCAPPED_N_PREDICT` once `max_think_tokens` goes; if the span stops sending `n_predict` entirely then `UNCAPPED_N_PREDICT` dies and the help fixture loses its last assertion. Row 4 must name that decision, because the fixture's fate hangs off it | row 4 |

## Section 2 - Row #1 - The runner stops paying for a graphics card it does not have

- **Scope:** Name a processor-only wheel index on the two faithfulness installs.
- **Files touched:** `.github/workflows/digest.yml` (L441-443), `.github/workflows/validate.yml` (L243), `docs/how-to/run-the-gates.md` (line 230).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite. **And the next nightly run watched to completion before the row closes.**
- **Oracle, on the runner:** the install step's log names a wheel carrying a `+cpu` local version and takes materially less than the 4 min at `docs/archive/measurements-2026-08.md:1933`; and the same run still writes a faithfulness score for a sampled item. **Nothing local can fail this** - a local install proves a wheel resolves on this box, not on the runner. What it cannot settle: how much of the saving is download against unpacking, which the pip cache makes a second question.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The mechanism is an estimate and the fix does not wait on it.** The default PyPI `torch` wheel for Linux is the graphics-card build and Guardrail #2 says there is none. The free measurement is reading the wheel filename out of any work job's log. **Two lines either way, and it cannot make the output worse** (Guardrail #10) | Carmack |
 | 2 | **The repository already knows the answer and applies it in the one file that does not need it.** `measure.yml:430` names the processor-only index; the two that run in production name none | Carmack |
 | 3 | A latent defect is named, not fixed: `digest.yml:441` branches on the dispatch input while `observability.py:227` draws the scorer per run from a digest of the run id. At the committed default of 1.0 they agree; below it every shard of an unsampled run pays for wheels to score nothing | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Measure first, then fix | The measurement is free and the fix cannot make the output worse. Waiting costs 3.6 min a run, five times a day | One job log read, and the same two lines afterwards | Carmack |
 | 2 | Declare a processor-only `torch` in the extra | An extra cannot carry an index URL portably, and pinning a `+cpu` local version breaks a developer whose machine has a graphics card | A manifest wrong on half the machines that read it | Fowler |

## Section 3 - Row #2 - The plan job closes the clock it opens

- **Scope:** Stamp the plan job's start and call the job clock as its last step, so its cost is a committed number.
- **Files touched:** `.github/workflows/digest.yml` (a `JOB_STARTED_AT` stamp before the checkout at L117, copied from L415-419; and `python -m idhazh job-clock --job plan --shard 0` as the job's last step).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite, plus the next nightly.
- **Oracle:** the next run's host-fingerprint ledger carries a row with `job=plan` and a non-empty `job_seconds`, and `compact` unions it with the row the job already opens. What it cannot settle: how much of that number is the planner against the checkout and install - the job clock covers all three, which is exactly what the `decide` split question needs to know.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Eight lines and no new contract.** `HostFingerprintRow` already carries `job`, `shard` and `job_seconds`; `digest.yml:243-262` already opens a row with `--job plan`; `stage_job_clock` at `backend/idhazh/telemetry/silicon.py:426` writes the seconds as a second row of the same key. `work` already calls it at `digest.yml:668`; the plan job does not. No schema, no version stamp, no migration | Carmack |
 | 2 | **It lands before anything that changes the plan job's shape.** The argument for splitting that job rests on a two-minute figure nothing in this repository can check | Carmack |
 | 3 | The three server cells on the plan's row stay empty; that function's docstring already rules that the degrade path | Fowler |
 | 4 | A per-stage number is a second instrument, decided after the first one reports | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Measure the plan stage rather than the job | The job clock covers checkout and install too, which is what the split question needs | One more cell and a second decision nobody has needed | Carmack |
 | 2 | Split the plan job now and measure afterwards | 120 lines spent against a figure given from memory | The scope-out table prices the split; this row is its instrument | Carmack |

## Section 4 - Row #3 - The capability probe goes

- **Scope:** Delete the workflow that asked the pinned build what it accepts, and repoint every page that describes it.
- **What the probe was for:** it dispatched a job that asked the binary `llama-server --help` plus six `/proc` and `/sys` reads, and kept the help text as an artifact. It exists because a model entry naming a speculation kind the build refused started a server that drafted nothing and burned an hour. **Plan 41 row 5 removes every enumerated choice from the model file, so the class of mistake it guarded is refused by the binary at start-up instead, by name.**
- **Files touched:**
  - `.github/workflows/probe.yml` (deleted)
  - `backend/tests/workflows/_harness.py` (the `probe.yml` entries at lines 76, 234, 258, and the `LLAMA_SERVER_WORKFLOWS` subtraction at line 279) - delete-only
  - `docs/reference/ci-model-runtime.md` (13, 14, 42, 100, 105), `docs/reference/github-actions.md` (26, 714, 731, 743), `docs/reference/host-metrics.md` (174), `docs/architecture/summarize/model-boundary.md` (467)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, `python backend/utilities/doc_load.py` before and after; CI - full suite.
- **Oracle:** no file outside `TODO/` names `probe.yml`, proved by a census across `.github/`, `backend/`, `frontend/`, `config/` and `docs/`. What it cannot settle: whether anything wanted the recorded help text. It does, and this row does not touch it.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The 705-line help fixture stays.** `server.py:824` keeps `UNCAPPED_N_PREDICT` alive as a production caller even after plan 41 deletes both caps, so `backend/tests/test_summarize.py:1776` keeps its subject; `docs/reference/models/gemma-4-e4b-qat.md:254` cites it as live provenance. ESCALATE trigger 6 | Carmack |
 | 2 | **`test_runtime_accepts.py` is plan 41 row 3's to delete**, in the commit that removes `SpeculationType`. A deleted import raises at collection, taking the module rather than one assertion | Fowler |
 | 3 | **`install-llama-runtime.sh` stays and is not merged into anything.** `fetch-model-runtime.sh:35` sources it, that script has three live callers, and row 9 caches its output under its own key | Fowler |
 | 4 | **Six doc references, not one.** A deletion leaving dangling references in pages the agent bootstrap routes to is how the thing comes back | Fowler |
 | 5 | `_harness.py` is **delete-only** in this pull request, so P2 and P3 cannot conflict on it | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the probe as an operator tool | A dispatchable workflow with no consumer is a file people reason about | 136 lines kept. The same answer is one command against a running server | Carmack |
 | 2 | Delete the help fixture with the workflow | It keeps a live assertion and a live provenance citation | A red suite and an orphaned provenance row | Carmack |

## Section 5 - Row #4 - The image benchmark goes

- **Scope:** Delete the image-diffusion benchmark, its job, its utility and two extras - and with them three undeclared packages including an unpinned third-party checkout inside a step that cannot fail.
- **Files touched:** `backend/utilities/bench_image.py` (deleted); `measure.yml` (the `image` job at L416-449, the `image` dispatch target, the `pip install -e ".[measure]"` at L476); `pyproject.toml` (the `bench-image` extra at L144-147, `measure = []` at L149-150, the `diffusers.*` type-checker override); `_harness.py` (`MEASUREMENT_TARGETS`) delete-only; `test_bench_targets.py` (the image cases); `docs/how-to/run-the-gates.md` (229, 233).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, `pip install -e ".[dev]"` resolving clean; CI - full suite.
- **Oracle:** no file imports `diffusers`, the dependency declaration no longer names it, and **no workflow step installs a package from a git reference** - a census over `.github/`, `backend/` and `pyproject.toml`. What it cannot settle: whether anybody wanted the measurement. Nobody dispatched it, and the job's own comment records that both earlier attempts died before the image finished.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The reason is the unpinned checkout, not the wheels.** `measure.yml:431` runs `pip install "git+https://github.com/huggingface/diffusers"` - moving main branch, no pin, no digest - inside a job whose next command ends `\|\| echo` and so cannot fail. That is the shape the pinned-release rule refuses, one package manager along | Carmack |
 | 2 | **Three undeclared installs leave the runner, not one wheel from the manifest.** `transformers` and `accelerate` are installed there too and declared nowhere. From the manifest only `diffusers` leaves: `torch>=2.5` is also in `faithfulness`, which production installs | Carmack |
 | 3 | `measure = []` is an empty extra that `measure.yml:476` installs, resolving to the base package | Fowler |
 | 4 | Guardrail #8 asks a dependency to name its beneficiary feature. When the feature goes, so does the dependency, in the same change | Carmack and Fowler |
 | 5 | The faithfulness wheels stay. `backend/idhazh/evals/hhem.py:119` lazily imports `AutoModelForSequenceClassification` for a pinned cross-encoder revision, and a qualification gate that decides publication reads its score | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Pin the diffusers install and keep the job | Pins a package for a measurement nobody dispatched and nobody reads, in a job that still cannot fail | One pin line and a 120-minute dispatch slot | Carmack |
 | 2 | Keep the utility outside the workflow | The tool is the dependency, and the unpinned install is in the workflow | The extra, for a measurement nobody asked for | Carmack |

## Section 6 - Row #5 - Five checks move into the thing they check

- **Scope:** Move five assertions out of workflow tests and into the step or module they were checking, each with its own unit test.
- **Files touched:** `backend/utilities/candidate_pointer.py` and its unit test; `backend/utilities/measure_llm.py`; the memory sampler's operator print; `.github/workflows/digest.yml` (the `Prompt cache log summary` step at L737); `backend/tests/workflows/test_bench_targets.py`, `test_model_server_jobs.py` (the five deletions that pay for the moves).
- **Acceptance gates:** local - `python -m pytest backend/tests -q`; CI - full suite. ESCALATE trigger 5 applies.
- **Oracle:** each of the five new unit tests fails on the base tree with the move reverted, and the deletion that pays for it is in the same commit. What it cannot settle: whether the moved check is cheaper in practice - it is cheaper by construction, because a required argument or a header read by name covers every caller where a test over one YAML file covered one.
- **The five moves:**

 | From | To | What it becomes |
 | --- | --- | --- |
 | `test_bench_targets.py:177` | `candidate_pointer.py`'s unit test | the field-write refusal, covering every caller |
 | `test_bench_targets.py:273` | `measure_llm.py` | `--expect-sha256` becomes a required argument |
 | `test_model_server_jobs.py:341` | the memory sampler's print | it reads the header by name, so the column-position class of defect dies |
 | `test_model_server_jobs.py:420` and `:447` | `digest.yml:737` | two lines: count matched, count total, echo `matched N of M` |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **A move ships in the same commit as the deletion it replaces.** Deleting a test and promising its replacement later is how the check disappears | Fowler, ESCALATE trigger 5 |
 | 2 | **The two log-format assertions become two lines in the step.** `digest.yml:737` is `if: always()`, its grep ends `\|\| true`, and it writes only to the job log. The count reports on the real log, on the real build, on every run, and it tells the truth when llama.cpp renames a field | Fowler |
 | 3 | This row is the **behavioural** commit of P3; row 6 is the structural one. They never share a commit | Fowler |
 | 4 | P3 waits on P1 because this row edits `digest.yml`, and on P2 because row 6 rewrites a module P2 deletes cases from | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete the five instead of moving them | Three of them - the digest flag, the sampler's column agreement, the log count - are this project's own code being able to be wrong, which is the one thing the rule keeps a check for | Three real defects with nothing watching | Fowler |
 | 2 | Move them in a later plan | A deleted check with a promised replacement is a deleted check | Nothing saved; it is the sequencing error ESCALATE trigger 5 names | Fowler |

## Section 7 - Row #6 - Fourteen assertions go, and the lists become computed

- **Scope:** Delete the fourteen assertions in C4 that name an author's choice, delete `test_bench_input_drift.py`, and convert every written list the repository can compute into a computed one with a non-empty assertion.
- **Files touched:** `test_bench_targets.py`, `test_model_server_jobs.py`, `test_weights_and_model_refs.py`, `test_pinned_versions.py`, `test_script_invocation.py`; `test_bench_input_drift.py` (deleted); `_harness.py` (every constant in C6) delete-only; `tests/fixtures/runtime/2026-08-29-3-shard-*.server-head.txt` (deleted).
- **Acceptance gates:** local - `python -m pytest backend/tests -q`; CI - full suite. ESCALATE trigger 4 applies.
- **Oracle:** **a new workflow that stands a model server up passes the suite with no constant edited**, demonstrated against a throwaway workflow file added and removed inside the test run. That check fails on the base tree, which is the defect the row exists for. Second half, and the one that fails quietly: every converted check asserts its computed list is non-empty, verified by a deliberate empty-glob arm. What it cannot settle: whether a deleted assertion was load-bearing - C4 is the keep-list, written from the code with a verdict and a reason on every row.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Fourteen of twenty-four go.** C4 carries the verdict and the reason for each. The three questions that decided them are in C4's closing line | Fowler |
 | 2 | **`test_weights_and_model_refs.py:415` is deleted, not anchored.** Zero of the eight inline programs bind from `os.environ`, so it cannot fail, and a test that cannot fail is worse than none because a reviewer reads it as cover. `test_triggers.py:191-199` is the holder and the pull request body says so | Andre and Carmack |
 | 3 | **`test_script_invocation.py:99` goes**, and with it the only thing that was making a tidiness assertion dictate pull-request shape | Fowler |
 | 4 | **`test_weights_and_model_refs.py:88` is kept but not rewritten here.** Its new body belongs to row 8, which is what makes the new body true. This row leaves it passing on the old shape | Fowler |
 | 5 | **The harness reads the pin from `llama-cpp-pin.sh` instead of duplicating it.** That takes a pin bump from three edits to one | Carmack |
 | 6 | `test_triggers.py` is untouched - the workflow-side Guardrail #11 control | Andre |
 | 7 | This row is the **structural** commit of P3 | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete the five modules whole | Ten assertions name a defect, including the one control on every byte this project downloads and the one that stops a benchmark reaching the production state root | About 2,700 lines and ten controls | Fowler |
 | 2 | Keep all twenty-four and convert only the tables | Leaves fourteen tests asserting an author's choice and five checks in a fixture where a step could report them every run | About 1,400 lines, and the argument again next quarter | Fowler |

## Section 8 - Row #7 - The printer learns the whole file set, and the traversal closes

- **Scope:** Give `model_refs.py` a `files` verb that prints every file the model declares, add `--config-root` to every verb, replace the two-digest cache key with a set digest over the printed rows, and close the path-traversal hole - calling nothing and changing no workflow.
- **Files touched:** `backend/utilities/model_refs.py`; its unit tests.
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'model_ref or refs' -q`, `ruff`, `mypy`; CI - full suite. ESCALATE trigger 3 applies.
- **Oracle, and it is a pure unit oracle:** for each of the five committed model files the verb prints exactly the files that entry declares, weights first, with every field having passed C8; and each refusal case - a `file` containing `/`, `..`, a leading `.`, a `revision` that is not 40 hex, a missing `sha256`, two entries resolving to one name - raises naming the models file, the index and the field. **The traversal cases fail on the base tree**, which is the defect the row exists for. What it cannot settle: whether the downloads work - this row calls nothing.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The module still answers one question** - "which model files will a shell see, and is every field safe?" - at a new arity. Three verbs, about 240 lines from 185. Split when a fourth question arrives; plan 40's `<role>.runtime` is the likely one | Fowler |
 | 2 | **`--config-root` goes on every verb, not only this one.** `configured` and `candidate` join `CONFIG_DIRNAME` under `--repo-root` while the candidate tree is `backend/var/candidate-config` holding `idhazh.json` directly. Two path conventions in one module is the drift this module exists to remove | Fowler |
 | 3 | **`_cache_key` becomes a function over the printed rows**, so the key is provably a digest of the set the loop downloads. The arity-two concatenation at `:79-92` cannot express a list, and GitHub caps a key at 512 characters | Carmack |
 | 4 | **The traversal fix is this row's, not a later hardening pass.** `one_bare_word` refuses only whitespace today. It is a Guardrail #11 strengthening and its refusal cases ship with it | Carmack and Fowler |
 | 5 | This row lands before row 8 and calls nothing, so a printer defect is caught by a unit test rather than by a dispatch | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Parse the JSON in the fetch script with `jq` | `jq` is preinstalled so it costs no bytes, but the bare-word and path-segment checks move into bash - a second implementation of a trust-boundary control, in the language with the worst quoting | A duplicated control, and the duplicate is the one a reviewer does not read | Carmack |
 | 2 | Pack the file list into one output string and keep the relay | A serialisation format nobody declared, re-split in the shell, with the check and the consumer in different languages | About 35 lines, four hops kept, and a worse trust boundary | Carmack |
 | 3 | Split the cache key into its own module now | A second reader of one file and a second path convention, for one function | Two modules that must agree about what a row is | Fowler |

## Section 9 - Row #8 - The workflows read the model file instead of relaying it

- **Scope:** Make `fetch-model-runtime.sh` take a config root and loop over the printer's rows, drop the composite action to five inputs, repoint every caller, delete the six inline JSON walks, and rewrite the restore-time check to cover the whole declared set.
- **Files touched:**
  - `.github/scripts/fetch-model-runtime.sh` (both hand-written `curl` blocks become one loop; the draft branch at L45-52 goes)
  - `.github/actions/model-server/action.yml` (ten inputs to five; the inline walks at L136 and L183)
  - `.github/workflows/digest.yml`, `llm-council.yml`, `validate.yml`, `idhazh-pipeline-tests.yaml` (L196, L274, L354), `measure.yml` (L1171)
  - `backend/tests/workflows/test_weights_and_model_refs.py` (the new body for `:88`, per C5), `test_pinned_versions.py`
  - `backend/tests/workflows/_harness.py` (`WEIGHTS_CHECKS` dies whole)
  - `docs/reference/ci-model-runtime.md`, `docs/reference/github-actions.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, `shellcheck`; CI - full suite, **and one real dispatch of the pipeline test, watched to completion, before the row closes.** ESCALATE trigger 1 applies.
- **Oracle:** the dispatch downloads exactly the files the model entry declares and the unconditional verify passes over all of them; and no workflow, action or script names a weights repository, revision or filename, proved by grep. **Only a runner can fail the first half.** What it cannot settle: the restore path - that is row 9's dispatch.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The printer is the only thing that touches JSON**, so the shell never sees a value that did not pass C8. That is why the script reads a config root rather than parsing the file itself | Carmack |
 | 2 | **The restore-time check survives as a workflow step with no `if:`.** The script runs behind `cache-hit != 'true'`, so a check that lived only inside it would never see a restored entry - the exact case that step exists for. C5 names the new assertion | Fowler, ESCALATE trigger 1 |
 | 3 | **The loop writes the rows to a file and reads the file.** `printer \| while read` runs the body in a subshell, so a failure inside cannot fail the script the way `set -euo pipefail` implies | Carmack |
 | 4 | **Six inline JSON walks go**, three of them dead outright once the checks read the printer's rows and three becoming a printer call. `test_weights_and_model_refs.py:59-61` records that three were heredoc copies that drifted; this stops them coming back | Fowler |
 | 5 | **The health check reads the loaded path and the alias from the config root**, which is why `weights_file` does not survive as a sixth input. `action.yml:183` already proves the action can read the file | Fowler |
 | 6 | `WEIGHTS_CHECKS` dies whole: after this row there is one fetch shape and one verify shape, so all four facts per entry are computable | Carmack |
 | 7 | **The fetch loop's download half is proved by the dispatch, not by a committed test**, and the row says so. Giving the script a base-URL seam to test it locally would put a second code path in production for no production caller | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the environment relay and generalise arity | Four hops stay, a packed string is re-split in the shell, and the check and the consumer end up in different languages | About 35 lines added and the trust boundary made worse | Carmack |
 | 2 | Keep `weights_file` as a sixth input for the health check | Shortens the relay rather than closing it, and the action already reads the file elsewhere | One input, and a relay nobody finishes | Fowler |
 | 3 | Give the script a base-URL variable and drive it against a local server | A test seam in production code with no production caller, and a wrong base URL becomes expressible | A second code path a reviewer must reason about | Fowler |
 | 4 | Fold this into one composite action for all four all-in-one callers | `action.yml:119` hardwires `models["summarize"]` out of `config/` and every benchmark arm runs against a candidate tree; the four sites are four different shapes | The scope-out table names the count that would settle it | Carmack |

## Section 10 - Row #9 - The cache names the set, and the binary gets its own key

- **Scope:** Replace the single weights-and-runtime cache entry with two keys - a set digest over `backend/models` and the build tag over `backend/bin` - at all five sites.
- **Files touched:** `.github/actions/model-server/action.yml` (L87-93), `.github/workflows/idhazh-pipeline-tests.yaml` (L167), `measure.yml` (L266, L581, L910), `validate.yml` (L278), `.github/scripts/fetch-model-runtime.sh` (two skip conditions where there is one), `backend/tests/workflows/test_weights_and_model_refs.py` (`:456`'s second clause).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, `shellcheck`; CI - full suite, **and two real dispatches - a miss then a hit** - before the row closes. ESCALATE trigger 2 applies.
- **Oracle, and it is the second dispatch that matters:** on the hit, the unconditional verify passes over **every** declared file, and the runtime key restores `backend/bin` without touching `backend/models`. **This is the half that can fail quietly** - a partial restore that looks like a hit. What it cannot settle: how long the first cold run takes, which is priced at about 75 s of run wall clock, once.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The key shape has to change either way**, because `<weights_file>-<weights_revision>` cannot name a variable file set. Doing the arity change now and the weights-binary split later orphans twice | Carmack |
 | 2 | **The two paths are disjoint.** A hit on one key restoring files the other owns makes its skip condition lie | Carmack, ESCALATE trigger 2 |
 | 3 | **Today's key names no companion at all**, while `model_refs.py:80-92` composes a key over both files and writes down why. The action and the printer contradict each other, and only the live pointer declaring no companion hides it | Fowler |
 | 4 | **One orphaning costs about 75 s of run wall clock, once.** A cold download adds 57 to 338 s over the restore it replaces, median about 75, and the most the cache can ever save is 0.6 percent of a dispatch. An earlier draft of this plan said 1.5 to 2.5 minutes per shard and was wrong: it compared a cold fetch against a free restore | Carmack |
 | 5 | A llama.cpp pin bump stops throwing away 4.22 GB of unchanged weights, which is the second reason for the split and the one that keeps paying | Carmack |
 | 6 | This is the third commit of P4 and never separates from the second into another pull request. Row 8 fails loudly - no weights, no server. This one fails quietly - a hit that restores a partial set. Different failure modes, different oracles, one review | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep today's key | It already names no companion, so a restored hit can be missing a declared file - the failure `_cache_key` was written to prevent | Nothing to take, and a silent partial restore | Carmack |
 | 2 | Extend the concatenation to N digests | Key length grows with the list against a 512-character cap, and it still welds weights to the binary | About 6 lines and a cap nobody notices until a third file | Carmack |
 | 3 | One key over a set digest, without splitting the binary out | Correct, but a pin bump still throws away 4.22 GB of unchanged weights | About 10 lines saved, and the split argued again on the next bump | Carmack |
 | 4 | Defer the split to a later plan | The shape changes here anyway, so deferring means two orphanings instead of one | About 15 lines moved, and 75 s paid twice | Carmack |

## Section 11 - Row #10 - The benchmark arms learn the server died, and the repeat count is config

- **Scope:** Give the two benchmark arms that start a server outside `start-llama-server.sh` the two-second liveness check that script already does, and move the benchmark repeat count into config beside its neighbour.
- **Files touched:** `.github/workflows/measure.yml` (after the inline start at L988; the `runtime_repeats` input at L58-60); `backend/utilities/runtime_sweep.py` (after the start at L284; the config read); `backend/idhazh/contracts/knobs/bench.py` (a `repeats` field beside `corpus_items`); `config/idhazh.json`; `backend/tests/`.
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'runtime or sweep or bench' -q`, `shellcheck`; CI - full suite.
- **Oracle:** a server started with a flag the build refuses is reported within about two seconds in both arms, driven by starting the real binary with a deliberately bad flag in a local test. What it cannot settle: the class where the build accepts a flag at parse and refuses it at decode - no health endpoint decodes a token, so `/health`, `/v1/models` and `/props` cannot see it.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **This is the honest replacement for the signal row 3 deletes.** The probe existed because a run died after five hours on a flag the build refused | Andre |
 | 2 | **Two seconds against 900 and 600**, read off the literals rather than measured. `start-llama-server.sh:67` already does `sleep 2; kill -0`; this is the same two lines in two more places | Andre and Carmack |
 | 3 | **The decode-time refusal is caught in the digest path and nowhere else, and that is stated rather than fixed.** `server.py:1599` is the only pre-flight decode and `digest.yml:513` its only caller; plan 41 keeps it. What settles adding one: time the two real completions at benchmark context length on a stock runner, three repetitions, hardware and date recorded, against a threshold Carmack sets at 10 s | Carmack |
 | 4 | **`bench.repeats` joins `bench.corpus_items` on `BenchConfig`**, default 3, `ge=2`, and `runtime_repeats` becomes empty-follows-config like `runtime_corpus_items`. The floor in `runtime_sweep.py:592` stays - a config default of 3 does not remove the need to refuse a dispatch of 1 | Carmack |
 | 5 | **The reason is not symmetry.** `knobs/bench.py:22` already carries the worked arithmetic on the job timeout - three repeats is six passes, 236 minutes, 71.6 percent, and it fits. Repeats is the other multiplier in that sentence, and split across two files the next person raises one without the other and finds out at 330 minutes | Carmack |
 | 6 | **No oracle changes with the repeat move.** The only test pairing the dispatch form to the module is `test_bench_input_drift.py:119`, which row 6 deletes | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Take nothing, since this is an addition in a deletion plan | Row 3 removes a signal; the honest replacement is the cheaper check that catches the same class. Four lines | Fifteen minutes of runner time per occurrence in the most re-dispatched arm | Carmack |
 | 2 | Route both arms through `start-llama-server.sh` | The `runtime` arm sweeps a setting and needs the process handle, which is why it starts its server inside a Python module | A rewrite of the sweep's process handling for a check two lines give it | Carmack |
 | 3 | Add a pre-flight decode to both arms now | A call plus its failure handling in two more arms, in files this pull request already rewrites | One measurement and a 10 s threshold. Decision 3 names both | Carmack |

## Section 12 - Row #11 - The harness keeps only what more than one module reads

- **Scope:** Move every name in `_harness.py` imported by exactly one module into that module, delete the names nothing reads, record the before and after, and take the one count the plan owes.
- **Files touched:** `backend/tests/workflows/_harness.py`; the 22 modules that import from it; `docs/reference/ci-model-runtime.md` (the C13 readings).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows --collect-only -q` before and after, then the full workflow suite; CI - full suite. No application behaviour changes, so no browser smoke is owed.
- **Oracle:** **the collected test count is identical before and after** - not pass or fail, because a suite stays green when a constant moves to a module nobody imports it from. Second half: `_harness.py` contains no name imported by fewer than two modules, checked by the same import census that drove the moves. What it cannot settle: whether a moved constant is in the right module. It is in its only consumer, which is the definition used.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The rule is the contract, not a line count.** C11 states it and it cannot be gamed | Carmack |
 | 2 | **The 36 unimported names are grepped as strings before deletion**, because a name can be reached by text rather than by import. Two are dead everywhere: `CLOCK_STEP`, `CLOCK_VARIABLES` | Carmack and Fowler |
 | 3 | **The commit-script fixture stays whole and is not dragged into the move.** Three surviving modules use it | Carmack |
 | 4 | **The row takes the count the plan owes**: how many merged pull requests in the last quarter changed more than one of the four server-starting callers in the same commit. One `git log`, and it settles the standing argument about a single composite action | Carmack and Fowler |
 | 5 | **Structural only, and it runs beside P5 rather than inside it**, because the two own disjoint files and P5 is behavioural | Fowler |
 | 6 | This row writes the C13 readings into `docs/reference/ci-model-runtime.md`. A plan whose headline number is never re-measured cannot say whether it worked | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Split the harness into four files here | A different question - one file answering many - and it belongs to its own pull request | A large structural refactor bundled into a deletion plan | Fowler |
 | 2 | Delete the unimported names and stop | Leaves 151 one-consumer names, 59 percent of the top-level surface, and the reason every workflow change is a two-file change | About 36 names removed and the two-file change untouched | Fowler |
 | 3 | Do the move inside P4 | Puts a structural change beside the riskiest behavioural one in the plan, and their oracles are a collected count against a dispatch | One review that cannot judge either half | Fowler |
