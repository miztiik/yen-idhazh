# Lane B - the workflows stop being a closed world

**Last Updated**: 2026-09-21

**Level**: 4 (about 2,300 lines of workflow test leave the tree, the work shard stops installing a graphics-card build of PyTorch onto a machine with no graphics card, one workflow stops carrying its own copy of the llama.cpp pin, one workflow and one utility are deleted, and the 2,361-line test-support module is cut to what more than one module reads. No persisted shape changes.)

Execute per docs/how-to/execute-a-plan.md: one owner, one worktree per pull request, rows in the order the Reckoner gives; Parallel N = 1, because rows 3 to 7 all edit `.github/workflows/measure.yml` and `backend/tests/workflows/_harness.py`, and two branches on those files is the churn this grouping exists to remove; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Every work shard installs a graphics-card build of PyTorch onto a runner that has no graphics card, five times a day - 4 minutes against 0.41 for a plain install, at the front of every shard. `backend/tests/workflows/` is 11,659 lines guarding 6,216 lines of `.github/`, the highest ratio in the repository, and of the 24 assertions a careful reading kept, **ten name a defect and fourteen name an author's choice**. Adding a workflow that stands a model server up means editing 5 constant tables before the suite will pass. Bumping the llama.cpp pin means editing 3 places. Two tests assert the format of somebody else's log. One workflow exists to ask a binary what it accepts, for a capability the repository is deleting. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** Owner ruling 2026-09-21. |
| The second rule | **Where a check is worth keeping, keep it in the thing that runs, not in a test against a recorded fixture.** A step that counts and prints reports on the real build on every run; a test against a capture says what was true on one day. Five of the fourteen removals below are this move, not a loss. |
| The measure | **Edits per future change, and minutes off the front of a shard.** Lines are the smaller number and the easier one to report. |
| Hard scope - in | Stop the faithfulness install pulling a graphics-card wheel, and make the plan job close the clock it already opens so its cost is a committed number rather than a recollection. Delete the capability probe workflow. Delete the image benchmark, which installs three undeclared packages including an unpinned third-party checkout inside a step that cannot fail. Delete the draft head from every workflow. Convert the benchmark workflow onto the shared fetch script and delete the pin copy it carries, in one commit with the census that policed that copy. Cut five workflow test modules to the ten assertions that name a defect, moving five of the removed checks into the step or the module they were checking. Make the benchmark arms notice a dead server in two seconds instead of fifteen minutes, and make the repeat count a config value like its neighbour. Cut the test-support module to what more than one module reads. |
| Hard scope - out | See the table below. |
| Supersedes | Plan 39 rows 3 (workflow half), 4, 9, 10, 13, 14 and 20. Those rows are `COLLAPSED` in plan 39's Reckoner and are not executed from there. Plan 39 row 5 is out of every plan; see the scope-out table. |
| Assumes | **Plan 41 is DONE before row 2 starts.** The typed model shape is gone, `SpeculationType` is gone, and **plan 41 row 3 has deleted `backend/tests/workflows/test_runtime_accepts.py`**, because that module imports the symbol row 3 there removes and a deleted import raises at test collection rather than at an assertion. This plan does not delete that test and is not blocked waiting to. |
| ESCALATE triggers | (1) Row 5 converts `measure.yml` onto the shared fetch script **and** deletes the same-pin census in one commit. If they separate, stop - the window between them is where the benchmark pins one build and the pipeline runs another, and every dossier number written in that window carries a wrong build name (Guardrail #10). (2) Row 6 converts written lists to computed ones. Every converted check asserts its computed list is **non-empty**, or the row stops - a discovery over an empty glob is a green suite proving nothing. (3) Row 6 moves five checks out of a test and into the thing being checked. Each move ships in the same commit as the deletion it replaces, or the row stops. (4) **`tests/fixtures/runtime/b10598-llama-server-help.txt` is not deleted by any row here.** It has six readers outside the probe's test; see C3. (5) Any row that would change a weights cache key. See C2. (6) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Three pull requests, split by what can fail. B1 is two small changes to production's critical path whose oracle is the next nightly's own job log. B2 is every deletion plus the one conversion a runner can fail. B3 is structural with zero behaviour. Carmack rules the runtime and the workflow shape, Fowler the test tiers and the module structure, Andre the evaluation integrity. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

### Hard scope - out

Every line here is a dated decision with a price, never a law (CLAUDE.md section 0d).

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Splitting the weights cache key in two** - `weights-<file>-<revision>` over `backend/models` and `runtime-<build>` over `backend/bin` | A llama.cpp pin bump throws away 4.22 GB of weights that did not change, on every shard of the first run after it. Roughly 1.5 to 2.5 extra minutes per shard: a cold fetch is 5.29 GiB in 118 s (n=1, stock `ubuntu-latest`, 2026-08-23, `docs/reference/models/qwen3.5-9b-q4km.md:155`) against a warm restore of 0.63 to 1.58 min (`docs/reference/benchmarks/what-a-bench-dispatch-costs.md:124`). At 4.3 GB an entry the 10 GB allowance holds two; split, it holds two weight sets and every build tag used this week | **The owner has accepted the orphaning cost, so the objection that blocked this is gone.** It stays out because four cache sites must change together - `action.yml:81-93`, `idhazh-pipeline-tests.yaml:167`, `measure.yml:266/581/910`, `validate.yml:278` - and the fetch script must learn two skip conditions where it has one. About 25 lines across four sites. **It is the first row of the plan after this one.** The one reading still missing is the runtime tarball's size, settled by one `curl -sI` against the release asset. Carmack, 2026-09-21 |
| **Folding the `plan` job into `work`** | The plan job keeps its own provisioning, measured at 0.41 min (`docs/reference/benchmarks/what-a-bench-dispatch-costs.md:26`) | **Refused as written, and the thing the owner wants is priced instead.** `backend/idhazh/stages/plan.py:135` reads every feed over the network and line 100 stamps `generated_at = clock()`, so four shards planning independently read the feeds at four different instants: some articles get summarised twice under two addresses and others never, and every source we do not own is read four to eight times a run. The matrix is also circular - `max-parallel` and `matrix.shard` at `digest.yml:409-411` come from the plan job and are resolved before any step runs. **What does get the overlap: a cheap `decide` job.** Checkout, install, the date, `model_refs.py`, `llama-cpp-pin.sh`, `shard_bound.py`, and a fanout read from `run.max_parallel` instead of from the plan - about 30 s. `plan` then needs `decide`; `work` needs **only** `decide`, runs its whole prelude beside the plan job, and blocks on the plan artifact with a bounded `gh api` poll that fails the moment the plan job concludes non-success. That hides the entire plan job behind a prelude Carmack measures at 5 to 6 min, worth 2.6 to 3.6 percent of an 83.5 to 117.5 min slowest shard (`docs/reference/pipeline-cost.md:478`). About 90 lines moved and 30 added, all in `digest.yml`. **It is a row in the plan after this one, and row 1 here is its instrument: take the measurement before spending the 120 lines.** Carmack, 2026-09-21 |
| **Moving the plan job's `state` commit onto assemble's** | One commit, one push and one rebase-retry stay in the plan job | **It stays, and the reason survives inspection.** `digest.yml:322-329` commits `state/seen`, `state/feed-health`, `state/feed-retirements` and `state/counterfactual-scores`; first sight is the only age an undated article has, and a feed never recorded is a feed that cannot be quarantined. The run that dies in `work` is exactly the run whose feed health matters most, and it is the run that would lose both ledgers. The saving is an estimate, labelled: 10 to 20 s for a few CSV rows, under 0.3 percent of a run. And once the `decide` split lands, this commit is off the critical path without being touched. Carmack, 2026-09-21 |
| **One composite action for the four callers that fetch, verify, start and health-check as a unit** (`digest.yml` work, `llm-council.yml` judge, `validate.yml` qualify, `measure.yml` budgets) | Four sites keep their own spelling of the same four steps | A countable condition: **how many merged pull requests in the last quarter changed more than one of the four in the same commit.** Zero means four copies cost nothing, because duplication is only expensive when it is edited together. Two or more means the action pays for itself. **Row 8's closure takes that count** - it is one `git log` and it settles a standing argument. A fifth caller brings it in immediately. Taking it today would add three inputs for one caller: `action.yml:119` hardwires `models["summarize"]` out of `config/`, and every benchmark arm runs against `backend/var/candidate-config`. Carmack |
| **A model file naming its own llama build** (plan 39 row 5) | This plan keeps the repository-wide pin as the only build | **Right as a design, and out of this plan because it is not a workflow-shape change.** If the model json is the interface, the binary that decodes the weights is part of it, and `llama-cpp-pin.sh` becomes a default a model file may override. **It is a generic interface, not a fork special case** - the pipeline is developed irrespective of any particular model (owner ruling 2026-09-21), and the installer change is about eight lines in `llama-cpp-pin.sh` and `fetch-model-runtime.sh`. It sits in plan 40 row 1 today because that is where the first model file wanting a different binary is declared; it moves to whichever plan declares the second one. It also wants the cache split above first, or every extra build tag multiplies a 4.3 GB entry against a 10 GB allowance. **The guard it owes, corrected:** a fork binary loads a stock model file happily and `validate.yml` job `qualify` decides publication, so the refusal is **a qualification whose recorded build is not the build the qualified model entry declares**, with `UNRECORDED_BUILD` refused outright. An earlier draft of this page said "not the repository pin"; that is wrong once the interface is generic, because it would pass a stock binary qualifying a model that declared a fork. `backend/idhazh/fingerprint.py:103` already records the value. Carmack and Fowler, agreed 2026-09-21 |
| **`companion_files`** - a general list of extra files a model fetches (plan 39 row 3 decision 2) | Speculative decoding cannot return as configuration; it would be a code change again | Nothing today. It appears nowhere in the repository except the plan that proposed it. It is an extension point with zero consumers built to hold a capability this repository measured on 2026-09-12 as changing the output on nine articles of nine. Three concrete usages earn an abstraction. Fowler and Carmack, agreed |
| **Merging `install-llama-runtime.sh` into `fetch-model-runtime.sh`** | `.github/scripts/` keeps 9 scripts | **Proposed in an earlier draft of this plan and withdrawn: it was wrong.** `fetch-model-runtime.sh:35` **sources** the installer, and the fetch script has three live callers - `action.yml:115`, `idhazh-pipeline-tests.yaml:182`, `validate.yml:302`. The installer is the build half of a live path, not dead code. Its only forcing function was `test_script_invocation.py:99`, which row 6 removes, and a separate runtime installer is what the cache split above wants. Fowler, 2026-09-21 |
| **Collapsing the four `commit-and-push.sh` calls in `digest.yml`** (plan 39 row 20) | Four calls stay | Nothing. `digest.yml` has three jobs - plan L85-395, work L396-941, assemble L942-1352 - and the calls at L372, L734 and L1147 are in three of them, on three different runners, with L734 inside a sharded matrix. The remaining pair, L1147 and L1244, is separated by a prune step whose own comment says the fold deletes a committed file and may only run once the push it might collide with has landed. Mergeable calls: **zero of four**. Carmack |
| **Splitting `_harness.py` into four files** - YAML parsing, the real-git-repo commit-script fixture, the inline-Python analyser, the tables | The module keeps four answers in one file after row 8 cuts it | The right end state and a separate structural pull request with its own review. One addition buys one cut (`docs/reference/documentation-structure.md`). Fowler |
| The `langfuse` extra | 32,656,612 bytes and a measured 260.9 s mean install (n=3, spread 24.9 s, `pyproject.toml:183-191`) stay declared | **It costs CI nothing** - no workflow installs it, and `.[dev]` does not carry it. It names its beneficiary and is the correct shape under Guardrail #8. Plan 39 row 15 deletes the sink it serves; the extra leaves with that row, not this one. Carmack |
| `backend/tests/workflows/test_staged_paths.py`, `test_daily_commit_steps.py`, `test_commit_script.py`, `test_triggers.py` | 1,572 lines stay | The commit surface is not this lane's, now that the four-calls row is dead. `test_commit_script.py` drives the real script through race and rebase cases against real repositories. **`test_triggers.py:191-199` is the workflow-side control for Guardrail #11**: it is closed-world over every declared dispatch input and asserts a read-by-name input never appears in a `run:` body and must arrive through `env`. Row 6's shrink must not reach it. Andre |

### What a change costs today

Measured on the tree at `origin/main`, 2026-09-21, except where a row says estimate.

| Reading | Value | Where |
| --- | --- | --- |
| Front of every work shard, `.[faithfulness]` install | **4 min**, against **0.41 min** for a plain editable install - about **3.6 min**, and because shards run in parallel that is 3.6 min of run wall clock, every run | `docs/archive/measurements-2026-08.md:1933` and `docs/reference/benchmarks/what-a-bench-dispatch-costs.md:26` |
| That against the critical path | **3 to 4 percent** of an 83.5 to 117.5 min slowest shard | `docs/reference/pipeline-cost.md:478` |
| Workflows naming a wheel index when installing PyTorch | **1 of 3**, and it is the one being deleted | `measure.yml:430` names `https://download.pytorch.org/whl/cpu`; `digest.yml:443` and `validate.yml:243` name none |
| Committed duration for the plan job | **none** | no ledger, no day-metrics file and no telemetry shard carries a job or stage duration. `digest.yml:243-262` opens a `HostFingerprintRow` with `--job plan` and never closes it |
| Test lines guarding workflow lines | 11,659 guarding 6,216 - a ratio of **1.88** | `backend/tests/workflows/*.py` against `.github/**/*.yml`, `*.yaml`, `*.sh` |
| Assertions a careful reading kept, of which name a defect | **24 kept, 10 name a defect** | C4 |
| Constant tables to edit before a new server-starting job passes its suite | **5** | `EXPECTED_WORKFLOWS`, `MODEL_SERVER_CALLERS`, `SERVER_STARTERS`, `WEIGHTS_CHECKS`, `LLAMA_RUNTIME_WORKFLOWS` |
| Places the llama.cpp pin is written | **3** | `.github/scripts/llama-cpp-pin.sh:26-28`, `.github/workflows/measure.yml:102-104`, `backend/tests/workflows/_harness.py:218-222` |
| Workflows that hand-write the runtime install rather than calling the shared script | **1 of 6** | `LLAMA_INLINE_RUNTIME_WORKFLOWS = LLAMA_RUNTIME_WORKFLOWS - LLAMA_SCRIPT_CALLERS` at `_harness.py:261` resolves to `{measure.yml}` |
| Top-level names in `_harness.py` | **255** in 2,361 lines | 36 imported by nobody, 151 by exactly one module, 43 by two or three, 25 by four or more |
| Undeclared packages the image benchmark installs onto a runner | **3** - `transformers`, `accelerate`, and `diffusers` from an unpinned git main branch | `measure.yml:430-431`, inside a step whose next command ends `\|\| echo` and so cannot fail |
| Seconds before a benchmark arm notices llama-server died at start | **900** at `measure.yml:989` (`seq 1 180` at 5 s), **600** at `backend/utilities/runtime_sweep.py:284` (120 at 5 s), against **2** in `digest.yml` and `validate.yml` | `.github/scripts/start-llama-server.sh:67` does `sleep 2; kill -0`; the two benchmark arms nohup inline and never check the process is alive |

## Section 0b - What this plan does, in one list

Eight rows, three pull requests. Read this before the tables.

1. Stop the faithfulness install pulling a graphics-card wheel onto a runner with no graphics card, and make the plan job close the clock it already opens.
2. Delete the capability probe workflow.
3. Delete the image benchmark, its job, its utility, its extras, and three undeclared installs with it.
4. Delete the draft head from every workflow, action, script and workflow test.
5. Convert the benchmark workflow onto the shared fetch script and delete the pin copy it carries, with the census that policed that copy, in one commit.
6. Cut five workflow test modules to the ten assertions that name a defect, and move five of the removals into the thing they were checking.
7. Make the benchmark arms notice a dead server in two seconds, and make the repeat count a config value like its neighbour.
8. Cut the test-support module to the names more than one module reads.

## Section 1 - Status Reckoner

**Rows are grouped into three pull requests. A pull request is one worktree, one branch, one review.** Rows inside a pull request run in the order below, in that one branch.

| # | Row title | PR | Depends-on | Parallel-group | Status | Worktree | PR link | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The runner stops paying for a graphics card it does not have | B1 | - | A | PENDING | - | - | - |
| 2 | The capability probe goes | B2 | - | B | PENDING | - | - | - |
| 3 | The image benchmark goes | B2 | - | B | PENDING | - | - | - |
| 4 | The draft head leaves the workflows | B2 | - | B | PENDING | - | - | - |
| 5 | The benchmark joins the shared script and drops its own pin | B2 | 4 | B | PENDING | - | - | - |
| 6 | The workflow tests shrink to ten assertions | B2 | 2, 3, 4, 5 | B | PENDING | - | - | - |
| 7 | The benchmark arms learn the server died, and the repeat count is config | B2 | 5, 6 | B | PENDING | - | - | - |
| 8 | The harness keeps only what more than one module reads | B3 | 6, 7 | C | PENDING | - | - | - |

### The three pull requests

| PR | Rows | Can a runner see it | What it can break | The one oracle that can actually fail |
| --- | --- | --- | --- | --- |
| **B1 - the install and the clock** | 1 | **yes, on production's critical path** | the faithfulness scorer, if the chosen wheel cannot load the cross-encoder | **The next nightly's own job log**: the install step names a `+cpu` wheel and takes materially less than 4 min, and the run still writes a faithfulness score for a sampled item. Nothing local can fail this - a local install proves a wheel resolves on this box, not on the runner |
| **B2 - the deletions and the conversion** | 2, 3, 4, 5, 6, 7 | **yes, and row 5 is the only one that can** | the benchmark arm downloads the wrong build, or nothing | **A real dispatch of `measure.yml` on its shortest target**, printing the resolved build tag and the sha256 it verified, both equal to what `llama-cpp-pin.sh` prints. Every other check in this pull request is a grep against YAML the same commit wrote |
| **B3 - the harness** | 8 | no | nothing. Zero behaviour | **The collected test count, identical before and after.** Not pass or fail: a suite stays green when a constant moves to a module nobody imports it from, so pass and fail cannot see this change |

**Why B1 is alone.** Its whole value is an attributable timing change on the job that runs five times a day. Bundled with two thousand deleted test lines, nobody can say which change moved the number.

**Why B2 is one and not four.** Rows 2 to 7 all edit `measure.yml` and `_harness.py`. Splitting them buys branches on one file and nothing else.

**Why B3 is separate.** It changes no behaviour and its oracle is a collected count, which is a different kind of evidence from a dispatch. Inside B2, structural and behavioural changes also stay in separate commits: the `measure.yml` conversion is behavioural, and the harness constant removals that follow from it are structural.

## Section 1a - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent one of these; it reads this section.**

### C1 - The composite action's input surface (row 4)

`.github/actions/model-server/action.yml`. After row 4:

| Input | Required | Note |
| --- | --- | --- |
| `github_token`, `port`, `weights_repo`, `weights_revision`, `weights_file`, `llama_cpp_build` | yes | unchanged |
| `draft_repo`, `draft_revision`, `draft_file`, `draft_sha256` | - | **removed**, lines 30-43 |

**No input is added by this plan.** No `models_file` input, no mode input, no new output. The five steps keep their names and their order.

### C2 - The weights cache keys (every row)

**Unchanged, byte for byte, in this plan.** Three families exist and all three stay as spelled: `llm-...-v4` at `action.yml:93` and `idhazh-pipeline-tests.yaml:167`; `bench-...` at `measure.yml:266`, `:581`, `:910`; `qualify-...` at `validate.yml:278`.

**The reason is no longer the orphaning cost, which the owner has accepted.** It is that the right change is a split - weights under one key, the runtime binary under another - and four cache sites plus the fetch script's skip condition must move together. That is the first row of the plan after this one, with Carmack's numbers in the scope-out table. A half-done split is worse than neither.

**The unconditional verify after a cache restore stays unconditional** in all five places - `action.yml:105`, `measure.yml:945`, `validate.yml:304`, `idhazh-pipeline-tests.yaml:202` - because a restored entry is the one case where nobody watched the bytes arrive. ESCALATE trigger 5 governs both halves.

### C3 - What leaves the repository entirely, and what does not

| Path | Lines | Row |
| --- | --- | --- |
| `.github/workflows/probe.yml` | 136 | 2 |
| `backend/utilities/bench_image.py` | 168 | 3 |
| `.github/workflows/measure.yml` job `image` | 34 (L416-449) | 3 |
| the `bench-image` extra and the empty `measure = []` extra | `pyproject.toml:144-147`, `:149-150` | 3 |
| `backend/tests/workflows/test_bench_input_drift.py` | 198 | 6 |
| the four `tests/fixtures/runtime/2026-08-29-3-shard-*.server-head.txt` captures | - | 6 |

**What does NOT leave, and an earlier draft of this plan was wrong about both:**

| Path | Why it stays |
| --- | --- |
| `tests/fixtures/runtime/b10598-llama-server-help.txt` (705 lines) | **Six readers outside the probe's test.** `backend/tests/test_summarize.py:1783` reads it to prove `-1` is llama.cpp's own spelling for an uncapped prediction. `backend/idhazh/llm/server.py` cites it at lines 98, 629 and 806 as the provenance for flag spellings. `docs/architecture/summarize/model-boundary.md:461`, `docs/reference/models/gemma-4-e4b-qat.md:64` and `:254` cite it, the last inside a measurement-provenance row. ESCALATE trigger 4 |
| `.github/scripts/install-llama-runtime.sh` (45 lines) | **`fetch-model-runtime.sh:35` sources it**, and that script has three live callers. It is the build half of a live path. `probe.yml:109` was only its one direct command-line caller |
| `backend/tests/workflows/test_runtime_accepts.py` (52 lines) | **Plan 41 row 3 deletes it**, because it imports `SpeculationType` and a deleted import raises at collection. This plan does not wait on it and does not delete it |
| `.github/scripts/start-llama-server.sh` | Unchanged |

`.github/scripts/` still ships 9 scripts after this plan.

### C4 - The assertions that survive, and the fourteen that do not (row 6)

**This is the keep-list. A worker deletes everything in these five modules that is not marked KEEP, and ships each MOVE in the same commit as the deletion it replaces (ESCALATE trigger 3).** Line numbers are on `origin/main`, 2026-09-21.

| Module and line | What the test is for | Verdict |
| --- | --- | --- |
| `test_bench_targets.py:78` (106-110) | three benchmark jobs spell one weights cache key identically | **REMOVE** - a cache miss is already printed in the run log, free |
| `test_bench_targets.py:177` | the benchmark measures a scratch config copy, not the committed one | **MOVE** - the field-write refusal belongs in `candidate_pointer.py`'s own unit test, where it covers every caller |
| `test_bench_targets.py:240` | the server case reads the raw case's artifact and emits one page | **REMOVE** - a missing artifact directory already fails the emit step loudly |
| `test_bench_targets.py:273` | the raw case passes `--expect-sha256` when it downloads weights | **MOVE** - make the flag required in `measure_llm.py`; that covers every caller, not one YAML file |
| `test_bench_targets.py:436` | a benchmark machine row lands in the benchmark state root only | **KEEP** - it reaches a published operator panel silently, and nothing else sees it |
| `test_bench_targets.py:587` | every pipeline stage a benchmark runs gets the scratch config | **KEEP** the discovery, drop its closed-world tail - a benchmark marking stories seen already cost a day |
| `test_model_server_jobs.py:229` | the start script exits 2 on a role it cannot serve | **KEEP** - it drives our own shipped script; three cases, about thirty lines |
| `test_model_server_jobs.py:255` | a locked-memory refusal does not hide a missing server binary | **REMOVE** - the script's own `sleep 2; kill -0` catches it, and eight exact strings are authorship |
| `test_model_server_jobs.py:341` | the sampler's columns and the operator print agree by position | **MOVE** - make the print read the header by name and the whole class of defect dies |
| `test_model_server_jobs.py:367` | the kernel memory peak is copied once and printed from the copy | **REMOVE** - a job log a person reads, and a small disagreement |
| `test_model_server_jobs.py:420`, `:447` | our grep patterns match llama.cpp's own log format | **MOVE** - two lines in the step at `digest.yml:737`: count matched, count total, echo `matched N of M`. That reports on the real build on every run; the tests could only say what was true on 2026-08-29 |
| `test_weights_and_model_refs.py:69` | every weights download uses `curl -f` and retries | **REMOVE** - the unconditional checksum in the same job already fails it loudly |
| `test_weights_and_model_refs.py:88` | every discovered fetch has a digest check before any reader | **KEEP** - the single control on every byte this project downloads |
| `test_weights_and_model_refs.py:119` | the health check compares the served alias and the loaded file | **REMOVE as its own test**, folding its comparison into the row below |
| `test_weights_and_model_refs.py:138` | every step waiting on health also asks which model answered | **KEEP**, absorbing the row above - it also reaches the arm outside the composite action |
| `test_weights_and_model_refs.py:182` | no workflow writes a model reference or a branch reference | **KEEP** - this is the bring-your-own-model rule on the workflow side, and the owner's ruling makes it load-bearing rather than incidental |
| `test_weights_and_model_refs.py:372` | every config key an inline program indexes exists in the file | **REMOVE** - one key in one workflow, and the failure is a loud crash |
| `test_weights_and_model_refs.py:415` | no inline program rebinds a name it read from the environment | **REMOVE - it is vacuous.** Zero of the eight inline programs bind a name from `os.environ`, so it passes by finding nothing, and unlike its neighbour at L371 it carries no anti-vacuity anchor. It is also not the Guardrail #11 control; `test_triggers.py:191-199` is, and no row touches it |
| `test_weights_and_model_refs.py:456` | the weights cache key names the model, revision and build | **KEEP the property**, drop the composed string. Convert its `MODEL_SERVER_CALLERS` enumeration to discovery |
| `test_pinned_versions.py:45` | every workflow spells the same pin in its own `env:` | **REMOVE** - after row 5 its input set is empty, so it asserts over nothing. The conversion is what kills it |
| `test_pinned_versions.py:63` | the llama.cpp pin is spelled in exactly one shipped script | **KEEP**, reduced to the four discovery checks in C5 - a wrong build name is silent on every dossier number |
| `test_pinned_versions.py:136` | the llama.cpp fetch is pinned to a tag and digest-checked | **REMOVE as its own test** - after row 5 it is one line inside the row above |
| `test_pinned_versions.py:151` | no workflow asks for whichever llama.cpp release is newest | **REMOVE as its own test** - same one-line grep, folded into the same place |
| `test_pinned_versions.py:167` | every action reference is pinned to an approved major | **REMOVE the approval table**, keep one line: every non-local `uses` carries an `@` |
| `test_pinned_versions.py:197` | every `setup-python` pin sits inside the declared interpreter range | **KEEP** - pip falls back to a source build and hangs silently inside a six-hour job |
| `test_script_invocation.py:68` | a script named as a bare command is committed executable | **KEEP** - a Windows checkout cannot show the bit, and this is its only reader |
| `test_script_invocation.py:99` | every shipped script is run by a workflow, and conversely | **REMOVE.** One direction fails on the runner in seconds with exit 127 naming the path; the other is tidiness. It is also the assertion that was dictating pull-request shape |
| `test_bench_input_drift.py`, all 8 | a dispatch form's options match a Python module's options | **REMOVE the file.** Two are draft cases; six assert the author wired it the way the author wired it |

**Ten KEEP, five MOVE, fourteen REMOVE.** The three questions that decided every row: can a run break it, or only a person; is the failure already loud on the runner; and would a cheaper instrument inside the workflow report the same fact on every real run. Where the answer to the third was yes, the row is a MOVE and the move ships with the deletion.

**Consequence to book:** `test_script_invocation.py`'s docstring then answers half a question. Rename the module for the file-mode question or fold it into `test_pinned_versions.py`.

### C5 - The one rule for a written list (row 6)

**If the repository can compute the list, compute it - and assert the computed list is non-empty. If the list encodes a judgement the repository does not contain, keep it written down.** Carmack's ruling; it applies to any of the 255 names in `_harness.py` without asking. The non-empty clause is the anti-vacuity anchor generalised, and ESCALATE trigger 2 governs it.

| Constant | Ruling |
| --- | --- |
| `MODEL_SERVER_CALLERS` | **Discover** - every job whose steps carry `uses: ./.github/actions/model-server`. Non-empty |
| `SERVER_STARTERS`, `EXPECTED_WORKFLOWS`, `MEASUREMENT_TARGETS`, `RUNTIME_CANDIDATES`, `APPROVED_ACTION_MAJORS` | computable or pure authorship. They die with the tests that read them |
| `WEIGHTS_CHECKS` | **Splits on the rule** - the checks that exist are discoverable and become one; the checks that *ought* to exist are the assertion and stay written |
| `PINNED_LLAMA_BUILD`, `PINNED_LLAMA_ASSET`, `PINNED_LLAMA_SHA256` | **Read from `.github/scripts/llama-cpp-pin.sh`**, not duplicated. This is what takes a pin bump from 3 edits to 1 |
| `LLAMA_SCRIPT_CALLERS`, `LLAMA_INLINE_RUNTIME_WORKFLOWS` | redundant after row 5 converts the last inline caller |
| `RUNTIME_LOG_LINES`, `RUNTIME_LOG_CAPTURES`, `RUNTIME_LOG_UNCLAIMED_TAG`, `RUNTIME_LOG_SUMMARY_STEPS` | die with the two log-format assertions |
| `DISPATCH_INPUT_SHAPES` | **stays written** - it encodes the shape an input must have, and `test_triggers.py` is out of scope |

`test_pinned_versions.py:63` after the conversion keeps four checks, all discoveries: no shipped script other than the pin script spells a pin name; the fetch script's call closure reaches the pin script; no workflow carries a pin value in any string; and the set of workflows reaching the fetch script is non-empty. The two folded-in one-liners are: no workflow or script asks for whichever release is newest, and every llama.cpp fetch names a tag and checks a digest.

### C6 - The harness, after the pass (row 8)

**`_harness.py` holds only names imported by two or more modules, plus the real-git-repo commit-script fixture.** That is the rule, and it is mechanically checkable. Every name imported by exactly one module moves into that module.

**No line-count target is written down.** 25 names shared by four or more modules are about 240 lines and the git fixture is about 400 on its own. Record the before and after as a reading (Guardrail #10).

| Reading | Value, 2026-09-21 |
| --- | --- |
| Top-level names | 255 |
| Imported by nobody | 36 - **grep each as a string before deleting it**; a name can be reached by text rather than by import. Two are already dead everywhere: `CLOCK_STEP`, `CLOCK_VARIABLES` |
| Imported by exactly one module | 151 |
| Imported by two or three | 43 |
| Imported by four or more | 25 |
| Consumer modules | 22 |

**The real-git-repo commit-script fixture stays whole and is not dragged into the move-to-consumer pass.** `test_staged_paths.py`, `test_daily_commit_steps.py` and `test_commit_script.py` all use it.

### C7 - What this plan does not touch

| Surface | Why |
| --- | --- |
| `config/models/` | Plan 41's. Two branches on one file is the churn the grouping exists to remove |
| `backend/idhazh/contracts/knobs/models.py`, `inference.py`, `turns.py`; `backend/idhazh/llm/`; `backend/idhazh/config.py` | Plan 41's. **`backend/idhazh/contracts/knobs/bench.py` is this plan's** - row 7 adds one field to it, and plan 41 does not touch that file |
| The three weights cache keys | C2, and the split named in the scope-out table |
| `test_triggers.py`, `test_staged_paths.py`, `test_daily_commit_steps.py`, `test_commit_script.py` | the scope-out table |
| `tests/fixtures/runtime/b10598-llama-server-help.txt`, `.github/scripts/install-llama-runtime.sh`, `backend/tests/workflows/test_runtime_accepts.py` | C3 |
| Guardrail #11, Guardrail #12, `CLAUDE.md` | No clause of the engineering contract is contradicted by any row here |

### C8 - The readings this plan is judged on

Re-measured at B3's close and written into `docs/reference/ci-model-runtime.md` (Guardrail #10).

| Reading | Before | Gate |
| --- | --- | --- |
| Minutes at the front of every work shard, for wheels | 4 min install | **under 1 min**, and the wheel named in the log carries a `+cpu` local version |
| Committed duration for the plan job | none | **one cell, every run** |
| Test lines per workflow line | 1.88 (11,659 / 6,216) | **at or under 1.3.** **The gate tightens against itself and that is intended**: this plan deletes roughly 250 workflow lines, so the denominator falls to about 5,966 and the numerator has to reach about 7,756. It is reachable only with row 8, which is why row 8 is not optional |
| Places the llama.cpp pin is written | 3 | **1** |
| Constant tables to edit before a new server-starting job passes | 5 | **0** |
| Seconds before a benchmark arm notices a dead server | 900 and 600 | **2 and 2** |

`backend/tests/workflows/` lands near 7,800 lines from 11,659 by arithmetic on the per-module rulings. That is a projection, not a measurement, and it is not a gate. **The ratio is the gate.**

## Section 2 - Row #1 - The runner stops paying for a graphics card it does not have

- **Scope:** Name a processor-only wheel index on the two faithfulness installs, and make the plan job close the job clock it already opens.
- **Files touched:**
  - `.github/workflows/digest.yml` (the install at L441-443; a `JOB_STARTED_AT` stamp before the checkout at L117, copied from L415-419; and `python -m idhazh job-clock --job plan --shard 0` as the job's last step)
  - `.github/workflows/validate.yml` (the install at L243)
  - `docs/how-to/run-the-gates.md` (line 230, which describes the extra as multi-gigabyte)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite. **And the next nightly run watched to completion before the row closes.**
- **Oracle, two parts, both on the runner:** the install step's own log names a wheel carrying a `+cpu` local version and the step takes materially less than the 4 min recorded at `docs/archive/measurements-2026-08.md:1933`; and the same run still writes a faithfulness score for a sampled item, so the cross-encoder still loads. **Nothing local can fail this** - a local install proves a wheel resolves on this box, not on the runner. What it cannot settle: how much of the saving is download against unpacking, which `setup-python`'s pip cache makes a second question.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The mechanism is an estimate and the fix does not wait on it.** The default PyPI `torch` wheel for Linux x86_64 is the graphics-card build, and Guardrail #2 says the runner has none. The free measurement is reading the wheel filename out of any work job's install log and looking for `+cpu`. **The fix is two lines either way, and it cannot make the output worse** (Guardrail #10) | Carmack |
 | 2 | **The repository already knows the answer and applies it in the one file that does not need it.** `measure.yml:430` names `https://download.pytorch.org/whl/cpu`; `digest.yml:443` and `validate.yml:243` name no index, and they are the two that run in production | Carmack |
 | 3 | **The plan job's clock is eight lines and no new contract.** `HostFingerprintRow` already carries `job`, `shard` and `job_seconds`; `digest.yml:243-262` already opens a row with `--job plan`; `stage_job_clock` at `backend/idhazh/telemetry/silicon.py:426` writes the seconds as a second row of the same key and `compact` unions the two. `work` already calls it at `digest.yml:668`. The plan job does not. No schema, no version stamp, no migration | Carmack |
 | 4 | **The clock lands before anything that changes the plan job's shape.** The argument for splitting the plan job rests on a two-minute figure given from memory that nothing in this repository can check | Carmack |
 | 5 | The three server cells on the plan's row stay empty. That function's own docstring already rules that the degrade path | Fowler |
 | 6 | A latent defect is named and not fixed here: `digest.yml:441` branches on the dispatch input, while `backend/idhazh/contracts/knobs/observability.py:227` draws the scorer per run from a digest of the run id. At the committed default of 1.0 they agree. Below 1.0 every shard of an unsampled run pays for wheels to score nothing. It bites the day somebody turns the knob | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Measure first, then fix | The measurement is free and the fix is two lines that cannot make the output worse. Waiting costs 3.6 min a run, five times a day, for the length of the wait | One job log read, and the same two lines afterwards | Carmack |
 | 2 | Declare a processor-only `torch` in the extra instead | An extra cannot carry an index URL portably, and pinning a `+cpu` local version in the manifest breaks a developer on a machine that has a graphics card | A manifest that is wrong on half the machines that read it | Fowler |
 | 3 | Measure the plan stage rather than the plan job | The job clock covers checkout and install too, which is exactly what the split question needs to know. A per-stage number is a second instrument, decided after the first one reports | One more cell and a second decision nobody has needed yet | Carmack |

## Section 3 - Row #2 - The capability probe goes

- **Scope:** Delete the workflow that asked the pinned build what it accepts, and repoint every page that describes it.
- **What the probe was for, so the deletion is not blind:** it dispatched a job that asked the pinned llama.cpp binary and the runner what they support - `llama-server --help` plus six `/proc` and `/sys` reads - and kept the help text as an artifact. It exists because a model entry naming a speculation kind the build refused started a server that drafted nothing and burned an hour of benchmark time. Plan 41 deletes the typed field that could name such a kind, so the class of mistake it guarded cannot be made.
- **Files touched:**
  - `.github/workflows/probe.yml` (deleted)
  - `backend/tests/workflows/_harness.py` (the `probe.yml` entry in `EXPECTED_WORKFLOWS` at line 76, in `LLAMA_RUNTIME_WORKFLOWS` at line 234, in `LLAMA_SCRIPT_CALLERS` at line 258, and the `LLAMA_SERVER_WORKFLOWS` subtraction at line 279)
  - `docs/reference/ci-model-runtime.md` (lines 13, 14, 42, 100, 105)
  - `docs/reference/github-actions.md` (lines 26, 714, 731, 743)
  - `docs/reference/host-metrics.md` (line 174)
  - `docs/architecture/summarize/model-boundary.md` (line 467)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, and `python backend/utilities/doc_load.py` before and after; CI - full suite.
- **Oracle:** no file outside `TODO/` names `probe.yml`, proved by a census across `.github/`, `backend/`, `frontend/`, `config/` and `docs/`. What it cannot settle: whether anything wanted the recorded help text. It did, and this row does not touch it - see the decisions.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The 705-line help fixture stays.** An earlier draft of this plan said the probe's test was its only committed consumer. That is false: six other places read or cite it, including a live assertion at `backend/tests/test_summarize.py:1783` and three provenance citations in `backend/idhazh/llm/server.py`. ESCALATE trigger 4 | Fowler |
 | 2 | **`test_runtime_accepts.py` is plan 41 row 3's to delete**, because it imports `SpeculationType` and a deleted import raises at test collection, taking the module rather than one assertion. The row that removes the symbol removes its reader | Fowler |
 | 3 | **`install-llama-runtime.sh` stays and is not merged into anything.** `fetch-model-runtime.sh:35` sources it and that script has three live callers. `probe.yml:109` was only its one direct command-line caller. An earlier draft of this plan proposed the merge; it was wrong | Fowler |
 | 4 | The probe is dispatch-only with no consumer left. A dispatchable workflow with no consumer is a file people have to reason about | Carmack |
 | 5 | **Six doc references, not one.** A deletion that leaves dangling references in the pages the agent bootstrap routes to is how the thing comes back | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the probe as an operator tool | A dispatchable workflow with no consumer is a file people have to reason about | 136 lines kept. The same answer is one command against a running server | Carmack |
 | 2 | Delete the help fixture with the workflow | Six readers, one of them a live test assertion | A red suite and an orphaned measurement-provenance row in `docs/reference/models/gemma-4-e4b-qat.md:254` | Fowler |

## Section 4 - Row #3 - The image benchmark goes

- **Scope:** Delete the image-diffusion benchmark, its job, its utility and two extras - and with them three undeclared packages including an unpinned third-party checkout inside a step that cannot fail.
- **Files touched:**
  - `backend/utilities/bench_image.py` (deleted)
  - `.github/workflows/measure.yml` (the `image` job at L416-449, the `image` dispatch target, and the `pip install -e ".[measure]"` at L476)
  - `pyproject.toml` (the `bench-image` extra at L144-147, the empty `measure = []` at L149-150, and the `diffusers.*` entry in the type-checker override)
  - `backend/tests/workflows/_harness.py` (`MEASUREMENT_TARGETS`)
  - `backend/tests/workflows/test_bench_targets.py` (the image target cases)
  - `docs/how-to/run-the-gates.md` (lines 229, 233)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, and `pip install -e ".[dev]"` resolving in a clean environment; CI - full suite.
- **Oracle:** no file imports `diffusers`, the dependency declaration no longer names it, and **no workflow step installs a package from a git reference** - proved by a census over `.github/`, `backend/` and `pyproject.toml`. What it cannot settle: whether anybody wanted the measurement. Nobody dispatched it, and the job's own comment records that both earlier attempts died before the image finished.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The reason is the unpinned checkout, not the wheels.** `measure.yml:431` runs `pip install "git+https://github.com/huggingface/diffusers"` - a moving main branch, no pin, no digest - inside a job whose next command ends `\|\| echo "Z-Image-Turbo did not complete on this runner"` and so cannot fail. That is the exact shape the pinned-release rule exists to refuse, one package manager along | Carmack |
 | 2 | **Three undeclared installs leave the runner, not one wheel from the manifest.** `measure.yml:431` also installs `transformers` and `accelerate`, neither of which is declared anywhere. From the manifest, only `diffusers` leaves: `torch>=2.5` is in both the `bench-image` and `faithfulness` extras and `faithfulness` is installed live by `digest.yml:443` and `validate.yml:243` | Carmack |
 | 3 | `measure = []` is an empty extra that `measure.yml:476` installs, resolving to the base package. It goes here | Fowler |
 | 4 | Timing image diffusion on a runner answers nothing about a news digest, and Guardrail #8 asks a dependency to name its beneficiary feature. When the feature goes, the dependency goes in the same change | Carmack and Fowler |
 | 5 | The faithfulness scorer's wheels stay. `backend/idhazh/evals/hhem.py:119` lazily imports `AutoModelForSequenceClassification` to load a pinned cross-encoder revision, and a qualification gate that decides publication reads its score | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Pin the diffusers install and keep the job | Pins a package for a measurement nobody has dispatched and nobody reads, in a job that still cannot fail | One pin line, a 120-minute dispatch slot, and a step that reports nothing | Carmack |
 | 2 | Keep the utility as an operator tool outside the workflow | The tool is the dependency, and the unpinned install is in the workflow rather than the tool | The extra, for a measurement nobody has asked for | Carmack |

## Section 5 - Row #4 - The draft head leaves the workflows

- **Scope:** Delete speculative decoding from every workflow, action, script and workflow test - a pure deletion with no replacement mechanism.
- **Files touched:**
  - `.github/actions/model-server/action.yml` (the four draft inputs at L30-43, the pass-through at L112-114, the draft verify at L122-130)
  - `.github/scripts/fetch-model-runtime.sh` (the `DRAFT_*` documentation at L14 and the conditional fetch at L45-52)
  - `.github/workflows/digest.yml` (L98-101), `llm-council.yml` (L80-83), `validate.yml` (L107-110, L299-301), `idhazh-pipeline-tests.yaml`
  - `.github/workflows/measure.yml` (the `no_draft` and `draft_depth` dispatch options at L64-65, the fetch and verify draft steps at L303-332)
  - `backend/tests/workflows/_harness.py` (`DRAFT_REF_OUTPUTS`, the draft entries in `WEIGHTS_CHECKS` and `MODEL_ENV_NAMES`)
  - `backend/tests/workflows/test_weights_and_model_refs.py` (the draft tests at lines 279, 575, 602, 621), `test_bench_targets.py` (770, 786, 808, 833)
  - `docs/` pages describing it
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** no file under `.github/` or `backend/tests/workflows/` contains `draft`, `spec-type` or `speculat`, proved by grep. What it cannot settle: whether the Python and contract surface is gone - that half is plan 41 row 3's, and the census closes again at this plan's close.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | It is deleted rather than kept unused. A measurement on 2026-09-12 found it changes the output on nine articles of nine, so it was never a free speed-up | Owner ruling 2026-09-21 |
 | 2 | **No `companion_files`, no landed-path output, no general fetch loop.** You do not build an extension point with zero consumers to hold a capability this repository measured as harmful | Fowler and Carmack, agreed |
 | 3 | **This row touches no model file.** The draft blocks in the two gemma entries leave with plan 41 row 3. A workflow that stops reading a key from a file that still carries it is correct for one release | Fowler |
 | 4 | **The `WEIGHTS_CHECKS` entry for `("measure.yml", "llama-bench")` names the two draft steps and goes in the same commit as the steps.** Row 6 keeps the per-entry weights guard; a kept guard pointing at a deleted step fails on merge | Carmack |
 | 5 | Two generated artefacts embed the probe's name inside a speculation-kind description - `schemas/run-manifest.schema.json` and `frontend/src/contracts/run-manifest.ts`. They regenerate when plan 41 retypes `ModelRef.inference`; this row's census expects them clean by then and reports rather than edits them | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Generalise the fetch into a list of companion files | An extension point with zero consumers, built to hold a capability measured as harmful, inside a plan named for deletion | About 60 lines across the action, the script and the installer's output surface, plus a bare-word check on three new fields | Fowler and Carmack |
 | 2 | Keep the action's four draft inputs as optional and unused | Four required-looking inputs a caller has to decide about, for a path nothing takes | 18 lines in the action and a question every new caller asks | Carmack |

## Section 6 - Row #5 - The benchmark joins the shared script and drops its own pin

- **Scope:** Convert `measure.yml`'s inline runtime install onto the shared fetch script, delete the `env:` pin copy it carries, and delete the census that existed to hold that copy equal - in one commit.
- **Files touched:**
  - `.github/workflows/measure.yml` (the `env:` pin at L102-104, and the inline install inside the blocks at L259-332, L576-714, L905-1020)
  - `.github/scripts/fetch-model-runtime.sh`
  - `backend/tests/workflows/test_pinned_versions.py` (the same-pin test at L45, whose input set becomes empty)
  - `backend/tests/workflows/_harness.py` (`LLAMA_INLINE_RUNTIME_WORKFLOWS`, `LLAMA_SCRIPT_CALLERS`)
  - `docs/reference/ci-model-runtime.md`, `docs/reference/github-actions.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, `shellcheck`; CI - full suite, **and one real dispatch of `measure.yml` on its shortest target, watched to completion, before the row closes.** ESCALATE trigger 1 applies.
- **Oracle:** the dispatch prints the build tag it resolved and the sha256 it verified, and both equal what `.github/scripts/llama-cpp-pin.sh` prints. **Only a runner can fail this.** A shell-level dry run is a proxy and is not accepted alone. What it cannot settle: how long the fetch takes, which this row does not change.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **`measure.yml` is the only workflow that hand-writes the install.** `LLAMA_INLINE_RUNTIME_WORKFLOWS` at `_harness.py:261` resolves to `{measure.yml}`; `validate.yml:302` and `idhazh-pipeline-tests.yaml:182` already call the shared script, and `digest.yml` and `llm-council.yml` reach it through the composite action at `action.yml:115`. **Converting `measure.yml` is what "reuse digest's flow" means at this layer** | Carmack |
 | 2 | **The conversion and the census deletion are one commit, or neither happens.** `test_pinned_versions.py:45` is the only thing holding `measure.yml:102-104` equal to the pin script. Delete the census while the literal is still there and the benchmark can pin one build while the pipeline runs another, and every dossier number written in that window carries a wrong build name (Guardrail #10) | Andre |
 | 3 | **No cache key changes here.** See C2 and the split named in the scope-out table | Carmack |
 | 4 | **The `budgets` arm does not move onto the composite action.** It is the only benchmark arm that starts a server as a step, so the action would gain three inputs for one caller: a config root, a models key and a cache key taken rather than composed. `action.yml:119` hardwires `models["summarize"]` out of `config/`, and every benchmark arm runs against `backend/var/candidate-config`. That is an abstraction earning its keep at one consumer, which this plan rejects one row along | Carmack |
 | 5 | The `runtime` arm keeps starting its server inside `backend/utilities/runtime_sweep.py`, because it sweeps a setting and needs the process handle. Row 7 gives it a liveness check. `llama-bench` and `batched` start no server at all | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Write one composite action taking a model file path, replacing all seven sites | The seven sites are four different shapes - fetch-verify-start-health as a unit; fetch-verify then a benchmark binary with no server; one fetch then two starts with different slot counts; fetch then start inside a Python module. One action covering four needs a mode input, which is the copies with a dispatch on top, in a file nobody reads | A week of arguing about the modes, and a merged thing that saves no edits because a new workflow still picks one | Carmack |
 | 2 | Change the cache key in this row | The right change is a split, and four sites plus the fetch script's skip condition must move together. A half-done split is worse than neither | About 25 lines across four sites, and its own dispatch. It is the first row of the next plan | Carmack |
 | 3 | Convert first and delete the census in a follow-up | That gap is the window in decision 2 | Nothing saved; it is a sequencing error with a wrong-name consequence | Andre |

## Section 7 - Row #6 - The workflow tests shrink to ten assertions

- **Scope:** Cut five workflow test modules to the ten assertions in C4 that name a defect, move five of the removed checks into the step or module they were checking, and convert every written list the repository can compute into a computed one with a non-empty assertion.
- **Files touched:**
  - `backend/tests/workflows/test_bench_targets.py`, `test_model_server_jobs.py`, `test_weights_and_model_refs.py`, `test_pinned_versions.py`, `test_script_invocation.py`
  - `backend/tests/workflows/test_bench_input_drift.py` (deleted)
  - `backend/tests/workflows/_harness.py` (every constant named in C5)
  - `.github/workflows/digest.yml` (the `Prompt cache log summary` step at L737 gains a matched-of-total count)
  - `backend/utilities/measure_llm.py` (`--expect-sha256` becomes required)
  - `backend/utilities/candidate_pointer.py` and its unit test (the field-write refusal moves here)
  - the memory sampler's operator print (reads the header by name, not by position)
  - `tests/fixtures/runtime/2026-08-29-3-shard-*.server-head.txt` (deleted)
- **Acceptance gates:** local - `python -m pytest backend/tests -q`; CI - full suite. ESCALATE triggers 2 and 3 apply.
- **Oracle:** **a new workflow that stands a model server up passes the suite with no constant edited**, demonstrated against a throwaway workflow file added and removed inside the test run. That check fails on the base tree, which is the defect the row exists for. Second half, and the one that can fail quietly: every converted check asserts its computed list is non-empty, verified by a deliberate empty-glob arm. What it cannot settle: whether a deleted assertion was load-bearing - C4 is the keep-list, written from the code with a verdict and a reason on every row.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Fourteen of twenty-four go, and five of those become a cheaper instrument rather than a loss.** C4 carries the verdict and the reason for every one. The three questions that decided each: can a run break it or only a person; is the failure already loud on the runner; would an instrument inside the workflow report the same fact on every real run | Fowler |
 | 2 | **A MOVE ships in the same commit as the deletion it replaces.** Deleting a test and promising its replacement later is how the check disappears | Fowler, ESCALATE trigger 3 |
 | 3 | **The two log-format assertions become two lines in the step.** `digest.yml:737` is `if: always()`, its grep ends `\|\| true`, and it writes only to the job log. Count matched, count total, echo `matched N of M`. That reports on the real log, on the real build, on every run, and it tells the truth when llama.cpp renames a field | Fowler |
 | 4 | **`--expect-sha256` becomes required in `measure_llm.py`.** A required argument covers every caller; a test over one YAML file covers one caller | Fowler |
 | 5 | **The memory sampler's print reads the header by name.** The whole class of column-position defect dies rather than being asserted against | Fowler |
 | 6 | **`test_weights_and_model_refs.py:415` is deleted, not anchored.** Zero of the eight inline programs bind a name from `os.environ`, so it cannot fail, and a test that cannot fail is worse than none because a reviewer reads it as cover. `test_triggers.py:191-199` is the Guardrail #11 holder and the pull request body says so | Andre and Carmack, agreed |
 | 7 | **`test_script_invocation.py:99` goes, and with it the only reason the probe deletion needed a script merge.** One direction of its set equality fails on the runner in seconds with exit 127 naming the path; the other is tidiness. A tidiness assertion was dictating pull-request shape | Fowler |
 | 8 | **The harness reads the pin from `llama-cpp-pin.sh` instead of duplicating it.** That is what takes a pin bump from three edits to one | Carmack |
 | 9 | **The discovery rule is one line and a worker applies it without asking**, with the non-empty clause load-bearing. C5 applies it to each constant | Carmack |
 | 10 | Keep every per-entry weights guard that survives C4: the digest check before any reader, the health check naming the weights that answered, and the refusal to measure before it passes. Those guard bytes this project downloads and numbers it reports | Carmack |
 | 11 | **`test_weights_and_model_refs.py:182` is load-bearing by argument, not by accident.** Once the model json is the only place a model is named, "no workflow writes a model reference" is the rule that keeps it that way | Fowler, on the owner's bring-your-own-model ruling |
 | 12 | `test_triggers.py` is untouched. It is the workflow-side Guardrail #11 control | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete the five modules whole | Ten of their assertions name a defect, including the one control on every byte this project downloads and the one that stops a benchmark reaching the production state root | About 2,700 lines removed and ten controls with them | Fowler |
 | 2 | Keep all twenty-four and only convert the closed-world tables | Leaves fourteen tests asserting an author's choice, and leaves five checks in a fixture where a step could report them on every run | About 1,400 lines, and the same argument again next quarter | Fowler |
 | 3 | Delete the five MOVE targets instead of moving them | Three of them - the digest flag, the sampler's column agreement, the log count - are this project's own code being able to be wrong, which is the one thing the rule keeps a check for | Three real defects with nothing watching | Fowler |

## Section 8 - Row #7 - The benchmark arms learn the server died, and the repeat count is config

- **Scope:** Give the two benchmark arms that start a server outside `start-llama-server.sh` the two-second liveness check that script already does, and move the benchmark repeat count into config beside its neighbour.
- **Files touched:**
  - `.github/workflows/measure.yml` (after the inline start at L988, before the health loop at L989; and the `runtime_repeats` dispatch input at L58-60)
  - `backend/utilities/runtime_sweep.py` (after the start at L284, before the wait loop; and the config read)
  - `backend/idhazh/contracts/knobs/bench.py` (a `repeats` field beside `corpus_items`)
  - `config/idhazh.json`
  - `backend/tests/` for the sweep's start path and the new field
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'runtime or sweep or bench' -q`, `shellcheck`; CI - full suite. Covered by row 5's dispatch.
- **Oracle:** a server started with a flag the build refuses is reported within about two seconds in both arms, driven by starting the real binary with a deliberately bad flag in a local test rather than by a dispatch. What it cannot settle: the class where the build accepts a flag at parse and refuses it at decode. No health endpoint decodes a token, so `/health`, `/v1/models` and `/props` cannot see it; the decisions name where that is caught today.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **This is the honest replacement for the signal row 2 deletes.** The probe existed because a run died after five hours on a flag the build refused | Andre |
 | 2 | **Two seconds against 900 and 600.** `measure.yml:989` loops `seq 1 180` at 5 s and `runtime_sweep.py:284` loops 120 at 5 s, and neither checks the process is alive. `start-llama-server.sh:67` already does `sleep 2; kill -0`. The saving is a worst-case bound read off the literals, not a measurement | Andre and Carmack |
 | 3 | **The decode-time refusal is caught in the digest path and nowhere else, and that is stated rather than fixed here.** `backend/idhazh/llm/server.py:1599` is the only pre-flight decode and `digest.yml:513` is its only caller; plan 41 keeps it. The benchmark and qualification arms find that class on the first measured item. What settles whether to add one: time the two real completions at benchmark context length on a stock runner, three repetitions, hardware and date recorded, against a threshold Carmack sets at 10 s | Carmack |
 | 4 | **`bench.repeats` joins `bench.corpus_items` on `BenchConfig`**, default 3, `ge=2`, and `runtime_repeats` becomes empty-follows-config exactly like `runtime_corpus_items`. The floor in `runtime_sweep.py` stays, because a config default of 3 does not remove the need to refuse a dispatch of 1 | Carmack |
 | 5 | **The reason is not symmetry.** `backend/idhazh/contracts/knobs/bench.py:22` already carries the worked arithmetic on the job timeout - three repeats is six passes, 236 minutes, 71.6 percent, and it fits. Repeats is the other multiplier in that sentence. Split across two files, the next person raises one without the other and finds out at 330 minutes | Carmack |
 | 6 | **No oracle changes with the repeat move.** The only test pairing the dispatch form to the module is `test_bench_input_drift.py:119`, and row 6 deletes that file | Carmack |
 | 7 | `backend/idhazh/contracts/knobs/bench.py` is this plan's file. Plan 41 touches `models.py`, `inference.py` and `turns.py` and not this one | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Take nothing, since this is an addition in a deletion plan | Row 2 removes a signal; the honest replacement for a removed check is the cheaper check that catches the same class. Four lines total | Fifteen minutes of runner time per occurrence in the arm most often re-dispatched | Carmack |
 | 2 | Route both arms through `start-llama-server.sh` | The `runtime` arm sweeps a setting and needs the process handle, which is why it starts its server inside a Python module | A rewrite of the sweep's process handling for a check two lines give it | Carmack |
 | 3 | Add a pre-flight decode to both arms now | A call plus its failure handling in two more arms, in files this pull request is already rewriting | One measurement and a 10 s threshold to decide it. Decision 3 names both | Carmack |
 | 4 | Leave the repeat count a dispatch input | Its neighbour is already config-driven, and the timeout arithmetic that governs both lives in the config model | Nothing saved; the two halves of one calculation stay in two files | Carmack |

## Section 9 - Row #8 - The harness keeps only what more than one module reads

- **Scope:** Move every name in `_harness.py` imported by exactly one module into that module, delete the names nothing reads, record the before and after, and take the one count the plan owes.
- **Files touched:**
  - `backend/tests/workflows/_harness.py`
  - the 22 modules under `backend/tests/workflows/` that import from it
  - `docs/reference/ci-model-runtime.md` (the C8 readings)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows --collect-only -q` before and after, and the full workflow suite; CI - full suite. No application behaviour changes, so no browser smoke is owed.
- **Oracle:** **the collected test count is identical before and after** - not pass or fail, because a suite stays green when a constant moves to a module nobody imports it from. Second half: `_harness.py` contains no name imported by fewer than two modules, checked by the same import census that drove the moves. What it cannot settle: whether a moved constant is now in the right module. It is in its only consumer, which is the definition used.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The rule is the contract, not a line count.** After the pass, `_harness.py` holds only names imported by two or more modules, plus the real-git-repo commit-script fixture. That is mechanically checkable and cannot be gamed | Carmack |
 | 2 | **No line-count target is written down.** Record the before and after as a reading (Guardrail #10) | Carmack |
 | 3 | **The 36 names nothing imports are grepped as strings before deletion**, because a name can be reached by text rather than by import. Two are already dead everywhere: `CLOCK_STEP` and `CLOCK_VARIABLES` | Carmack and Fowler |
 | 4 | **The commit-script fixture stays whole and is not dragged into the move.** Three surviving modules use it | Carmack |
 | 5 | **The row takes the count the plan owes**: how many merged pull requests in the last quarter changed more than one of the four server-starting callers in the same commit. One `git log`, and it settles the standing argument about a single composite action. The answer goes in the write-up, not in a new row here | Carmack and Fowler |
 | 6 | **It runs last and alone in its own pull request.** It is structural with no behaviour, and its oracle is a collected count rather than a dispatch | Fowler |
 | 7 | This row writes the C8 readings into `docs/reference/ci-model-runtime.md`. A plan whose headline number is never re-measured cannot say whether it worked | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Split the harness into four files in this plan | A different question - one file answering many - and it belongs to its own pull request | A large structural refactor bundled into a deletion plan | Fowler |
 | 2 | Delete the unimported names and stop | Leaves 151 one-consumer names, which is 59 percent of the top-level surface and the reason every workflow change is a two-file change | About 36 names removed and the two-file change untouched | Fowler |
 | 3 | Do the move inside B2, beside the deletions | Puts a structural change and a behavioural change in one review, and the oracle for each is different - a collected count against a runner dispatch | Nothing saved; one review that cannot judge either half | Fowler |
