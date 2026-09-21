# Lane B - the workflows stop being a closed world

**Last Updated**: 2026-09-21

**Level**: 4 (about 2,000 lines of workflow test leave the tree, one workflow stops carrying its own copy of the llama.cpp pin, one workflow and two utilities are deleted, and the 2,361-line test-support module is cut to what more than one module reads. No persisted shape changes.)

Execute per docs/how-to/execute-a-plan.md: one owner, one worktree per pull request, rows in the order the Reckoner gives; Parallel N = 1, because rows 4 to 8 all edit `.github/workflows/measure.yml` and `backend/tests/workflows/_harness.py`, and two branches on those files is the churn this grouping exists to remove; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | `backend/tests/workflows/` is 11,659 lines guarding 6,216 lines of `.github/` - 1.88 lines of test per line of workflow, the highest ratio in the repository, and 71 of those tests across 2,760 lines contain 20 assertions that name a defect. The rest assert that the author wired it the way the author wired it: 11 workflow names, 5 workflow-and-job pairs that may start a server, 8 that may fetch weights, 5 measurement targets, 30 dispatch input shapes. Adding a workflow that stands a model server up means editing 5 constant tables before the workflow will pass. Bumping the llama.cpp pin means editing 4 places - the pin script, one workflow's own `env:` copy, three harness constants, and a 705-line recorded help text named for the build. And two of those tests assert the format of somebody else's log. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** Owner ruling 2026-09-21. |
| The measure | **Edits per future change, not lines.** Lines are the smaller number and the easier one to report. |
| Hard scope - in | Delete the capability probe workflow, the test that read its recording and the 705-line recording. Fold the runtime installer into the fetch script, because the probe was the only caller that wanted them apart. Delete the image benchmark, which installs an unpinned third-party checkout inside a step that cannot fail. Delete the draft head from every workflow. Convert the benchmark workflow onto the shared fetch script and delete the pin copy it carries, in one commit with the census that policed that copy. Shrink five workflow test modules to the assertions that name a defect, converting a written list to a computed one wherever the repository can compute it. Make the benchmark arms notice a dead server in two seconds instead of fifteen minutes. Cut the test-support module to what more than one module reads. |
| Hard scope - out | See the table below. |
| Supersedes | Plan 39 rows 3 (workflow half), 4, 9, 10, 13, 14 and 20. Those rows are `COLLAPSED` in plan 39's Reckoner and are not executed from there. Plan 39 row 5 is handed to plan 40 row 1; see the scope-out table. |
| Hands to plan 41 | **Pull request B1 of this plan must merge before plan 41 pull request A.** `backend/tests/workflows/test_runtime_accepts.py:11` imports `SpeculationType`, which plan 41 row 3 deletes. A deleted import raises at test **collection**, so the whole module fails and pytest reports a stack trace rather than a defect. |
| Takes from plan 41 | Nothing. This plan does not touch `config/models/`, `backend/idhazh/contracts/`, `backend/idhazh/llm/` or `backend/idhazh/config.py`. The draft blocks in the two gemma model files leave with plan 41 row 3. A workflow that stops reading a key from a file that still carries it is correct for one release. |
| ESCALATE triggers | (1) Row 5 converts `measure.yml` onto the shared fetch script **and** deletes the same-pin census in one commit. If they separate, stop - the window between them is where the benchmark pins one build and the pipeline runs another, and every dossier number written in that window carries a wrong build name (Guardrail #10). (2) Row 7 converts written lists to computed ones. Every converted check asserts its computed list is **non-empty**, or the row stops - a discovery over an empty glob is a green suite proving nothing. (3) Row 1 deletes `probe.yml`, and row 2 must land in the same pull request: `test_script_invocation.py:111` asserts `named == shipped` as set equality, and `probe.yml:109` is the only workflow naming `install-llama-runtime.sh`. (4) Any row that would change a weights cache key. See C2. (5) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Three pull requests. B1 is pure deletion with no runtime behaviour and unblocks plan 41. B2 carries every change a runner can see. B3 is structural with zero behaviour and runs last. Carmack rules the runtime and the workflow shape, Fowler the test tiers and the module structure, Andre the evaluation integrity. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **One composite action for the four callers that fetch, verify, start and health-check as a unit** (`digest.yml` work, `llm-council.yml` judge, `validate.yml` qualify, `measure.yml` budgets) | Four sites keep their own spelling of the same four steps | A countable condition, not an opinion: **how many merged pull requests in the last quarter changed more than one of the four in the same commit.** Zero means four copies cost nothing, because duplication is only expensive when it is edited together. Two or more means the action pays for itself. That count is one `git log` away and should be taken before anyone argues this again. A fifth caller brings it in immediately. Carmack |
| **A model file naming its own llama build** (plan 39 row 5) | This plan keeps the repository-wide pin as the only build, so nothing here can dispatch a fork binary | **It is not descoped - it is handed to [`20260921-40-bonsai-probe-plan.md`](20260921-40-bonsai-probe-plan.md) row 1, which is its only named consumer.** That row already names the fork's repository, release tag, asset and digest, and its decision 3 rules that the entry names its own runtime rather than moving the pin. It belongs where the model that needs it is declared, not in a deletion plan, and it waits on plan 41 pull request A because the typed shape refuses the key until then. **What it must carry, and does not yet declare:** a fork binary loads a stock model file happily, and `validate.yml` job `qualify` decides publication, so a verdict could be measured on one binary and reported under another. The instrument already exists - `backend/idhazh/fingerprint.py:103` records `LLAMA_CPP_BUILD` and falls back to `UNRECORDED_BUILD`, and row 7 here keeps the check that every recording step carries it. The guard is one assertion in the gate that publishes: **refuse a qualification whose recorded build is not the repository pin**, and let the benchmark arms carry a fork. Carmack and Fowler, agreed |
| **A pre-flight decode in the benchmark and qualification arms** | Those two arms find a build that parses a flag and then refuses it at decode only when the first measured item runs. The digest path is covered: plan 41 keeps `decoding_still_constrains` at every server start | `backend/idhazh/llm/server.py:1599` is the only thing that has ever caught this class before an item ran, and it is called from `digest.yml:513` and nowhere else. A call plus its failure handling in two more arms is how three pull requests become five. What settles it: time the two real completions at benchmark context length on a stock runner, three repetitions, hardware and date recorded. Carmack's threshold, set rather than measured: 10 s. Under it, take it in the plan after this one. Over it, the benchmark keeps the liveness check row 8 adds and accepts that a decode-time refusal costs one wasted benchmark job |
| **`companion_files`** - a general list of extra files a model fetches (plan 39 row 3 decision 2) | Speculative decoding cannot return as configuration; it would be a code change again | Nothing today. It appears nowhere in the repository except the plan that proposed it. It is an extension point with zero consumers built to hold a capability this repository measured on 2026-09-12 as changing the output on nine articles of nine. Three concrete usages earn an abstraction. Fowler and Carmack, agreed |
| **Collapsing the four `commit-and-push.sh` calls in `digest.yml`** (plan 39 row 20) | Four calls stay | Nothing. `digest.yml` has three jobs - plan (L85-395), work (L396-941), assemble (L942-1352) - and the calls at L372, L734 and L1147 are in three of them, on three different runners, with L734 inside a sharded matrix. The remaining pair, L1147 and L1244, is separated by a prune step whose own comment says the fold deletes a committed file and may only run once the push it might collide with has landed. Mergeable calls: **zero of four**. Carmack |
| **Splitting `_harness.py` into four files** - YAML parsing, the real-git-repo commit-script fixture, the inline-Python analyser, the tables | The module keeps four answers in one file after row 9 cuts it | The right end state and a separate structural pull request with its own review. One addition buys one cut (`docs/reference/documentation-structure.md`). Fowler |
| `backend/tests/workflows/test_staged_paths.py`, `test_daily_commit_steps.py`, `test_commit_script.py` | 1,272 lines stay | The commit surface is not this lane's, now that the four-calls row is dead. `test_commit_script.py` drives the real script through race and rebase cases against real repositories, which is this project's own code being wrong |
| `backend/tests/workflows/test_triggers.py` | 300 lines stay | **It is the workflow-side control for Guardrail #11.** `test_triggers.py:191-199` is closed-world over every declared dispatch input and asserts a read-by-name input never appears in a `run:` body and must arrive through `env`. No row touches it, and row 7's shrink must not reach it. Andre |
| The weights cache keys | Three key families stay as they are spelled today | See C2. A worker who changes one has left the plan |

### What a change costs today

Measured on the tree at `origin/main`, 2026-09-21.

| Reading | Value | Where |
| --- | --- | --- |
| Test lines guarding workflow lines | 11,659 guarding 6,216 - a ratio of **1.88** | `backend/tests/workflows/*.py` against `.github/**/*.yml`, `*.yaml`, `*.sh` |
| Assertions in the six modules this plan edits that name a defect | **20**, across 71 tests and 2,760 lines | see C4 |
| Constant tables to edit before a new server-starting job passes its suite | **5** | `EXPECTED_WORKFLOWS`, `MODEL_SERVER_CALLERS`, `SERVER_STARTERS`, `WEIGHTS_CHECKS`, `LLAMA_RUNTIME_WORKFLOWS` |
| Places the llama.cpp pin is written | **4** | `.github/scripts/llama-cpp-pin.sh:26-28`, `.github/workflows/measure.yml:102-104`, `backend/tests/workflows/_harness.py:218-222`, and `tests/fixtures/runtime/b10598-llama-server-help.txt` named for the build |
| Workflows that hand-write the runtime install rather than calling the shared script | **1 of 6** | `LLAMA_INLINE_RUNTIME_WORKFLOWS = LLAMA_RUNTIME_WORKFLOWS - LLAMA_SCRIPT_CALLERS` at `_harness.py:261` resolves to `{measure.yml}` |
| Inline fetch, verify, start and health lines across the five sites that do not call the shared action | about **593** | `measure.yml` 259-332, 576-714, 905-1020; `validate.yml` 271-370; `idhazh-pipeline-tests.yaml` 160-410 |
| Top-level names in `_harness.py` | **255** in 2,361 lines | 36 imported by nobody, 151 by exactly one module, 43 by two or three, 25 by four or more |
| Lines row 1 removes | **893** | `probe.yml` 136 + `test_runtime_accepts.py` 52 + the help fixture 705 |
| Wheels the image benchmark removes from the manifest | **1**, `diffusers` | `torch>=2.5` is in both the `bench-image` and `faithfulness` extras, and `faithfulness` is installed live by `digest.yml:443` and `validate.yml:243` |
| Seconds before a benchmark arm notices llama-server died at start | **900** in `measure.yml:989` (`seq 1 180` at 5 s), **600** in `backend/utilities/runtime_sweep.py:284` (120 at 5 s), against **2** in `digest.yml` and `validate.yml` | `.github/scripts/start-llama-server.sh:67` does `sleep 2; kill -0`; the two benchmark arms nohup inline and never check the process is alive |
| Inline Python programs in workflows that bind a name from `os.environ` | **0 of 8** | which is why `test_weights_and_model_refs.py:415` passes by finding nothing |

## Section 0b - What this plan does, in one list

Nine rows, three pull requests. Read this before the tables.

1. Delete the capability probe workflow, the test that read its recording, and the 705-line recording.
2. Fold the runtime installer into the fetch script. The probe was the only caller that wanted them apart.
3. Delete the image benchmark, its job, its utility and its extra - and with them an unpinned third-party checkout living inside a step that cannot fail.
4. Delete the draft head from every workflow, action, script and workflow test.
5. Convert the benchmark workflow onto the shared fetch script and delete the pin copy it carries, with the census that policed that copy, in one commit.
6. Shrink the benchmark tests from 36 to 6 - the six that name a defect.
7. Shrink the server, weights and pin tests to the assertions that name a defect, and convert every written list the repository can compute into a computed one.
8. Make the two benchmark arms notice a dead server in two seconds instead of fifteen minutes.
9. Cut the test-support module to the names more than one module reads.

## Section 1 - Status Reckoner

**Rows are grouped into three pull requests. A pull request is one worktree, one branch, one review.** Rows inside a pull request run in the order below, in that one branch.

| # | Row title | PR | Depends-on | Parallel-group | Status | Worktree | PR link | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The capability probe goes | B1 | - | A | PENDING | - | - | - |
| 2 | Two runtime scripts become one | B1 | 1 | A | PENDING | - | - | - |
| 3 | The image benchmark goes | B1 | - | A | PENDING | - | - | - |
| 4 | The draft head leaves the workflows | B2 | 2 | B | PENDING | - | - | - |
| 5 | The benchmark joins the shared script and drops its own pin | B2 | 4 | B | PENDING | - | - | - |
| 6 | The benchmark tests shrink to the six that name a defect | B2 | 5 | B | PENDING | - | - | - |
| 7 | The server, weights and pin censuses become discovery or die | B2 | 5 | B | PENDING | - | - | - |
| 8 | The benchmark arms learn the server died | B2 | 5 | B | PENDING | - | - | - |
| 9 | The harness keeps only what more than one module reads | B3 | 6, 7, 8 | C | PENDING | - | - | - |

### The three pull requests

| PR | Rows | Can a runner see it | What it can break | The one oracle that can actually fail |
| --- | --- | --- | --- | --- |
| **B1 - the probe and the picture** | 1, 2, 3 | no | every workflow that fetches weights, because the fetch script changes shape | `test_script_invocation.py::test_every_shipped_script_is_one_a_workflow_runs` at line 99. It asserts `named == shipped` as set equality, `_calls()` reads only workflow `run:` bodies, and `probe.yml:109` is the only workflow naming the installer. Delete the probe without merging the scripts and this goes red, correctly: it is saying the deletion is half done |
| **B2 - the censuses** | 4, 5, 6, 7, 8 | **yes, and it is the only one here that can** | the benchmark arm downloads the wrong build, or nothing | **A real dispatch of `measure.yml` on its shortest target**, which prints the resolved build tag and the sha256 it verified, and that string must equal what `llama-cpp-pin.sh` prints. Every local oracle in this pull request is a grep against YAML the same commit wrote. Only a runner can fail this one |
| **B3 - the harness** | 9 | no | nothing. Zero behaviour | **The collected test count, identical before and after.** Not pass or fail: a suite stays green when a constant moves to a module nobody imports it from, so pass and fail cannot see this change |

**Why three and not one.** B1 must merge before plan 41 pull request A and B2 need not. Blocking a foreign plan on a bigger pull request than it needs is the cost. B2 is the only pull request a runner can fail, so a benchmark that downloads the wrong build has exactly one candidate cause. B3 changes no behaviour, so bundling it with either would put a structural change and a behavioural change in one review.

**Why three and not five.** Rows 4 to 8 all edit `measure.yml` and `_harness.py`. Splitting them buys branches on one file and nothing else.

**Inside B2, structural and behavioural changes stay in separate commits.** The `measure.yml` conversion is behavioural; the harness constant removals that follow from it are structural.

## Section 1a - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent one of these; it reads this section.**

### C1 - The composite action's input surface (row 4)

`.github/actions/model-server/action.yml`. After row 4:

| Input | Required | Note |
| --- | --- | --- |
| `github_token` | yes | unchanged |
| `port` | yes | unchanged |
| `weights_repo` | yes | unchanged |
| `weights_revision` | yes | unchanged |
| `weights_file` | yes | unchanged |
| `llama_cpp_build` | yes | unchanged |
| `draft_repo`, `draft_revision`, `draft_file`, `draft_sha256` | - | **removed**, lines 30-43 |

**No input is added by this plan.** No `models_file` input, no mode input, no new output. The five steps keep their names and their order, because `MODEL_SERVER_STEPS` is not what makes them right and changing them costs a caller edit for nothing.

### C2 - The weights cache keys (every row)

**Unchanged, byte for byte.** Three families exist and all three stay as spelled:

| Key | Where |
| --- | --- |
| `llm-${{ inputs.weights_file }}-${{ inputs.weights_revision }}-${{ inputs.llama_cpp_build }}-v4` | `.github/actions/model-server/action.yml:93`, `.github/workflows/idhazh-pipeline-tests.yaml:167` |
| `bench-${{ needs.models.outputs.candidate_cache_key }}-${{ env.LLAMA_CPP_BUILD }}` | `.github/workflows/measure.yml:266`, `:581`, `:910` |
| `qualify-${{ needs.plan.outputs.candidate_cache_key }}-${{ needs.plan.outputs.llama_cpp_build }}` | `.github/workflows/validate.yml:278` |

There are no `restore-keys` anywhere and none is added. **The unconditional verify after a cache restore stays unconditional** in all five places - `action.yml:105`, `measure.yml:945`, `validate.yml:304`, `idhazh-pipeline-tests.yaml:202` - because a restored entry is the one case where nobody watched the bytes arrive, and a per-file skip-or-fetch would turn that loud failure into a silent self-heal that re-downloads 4.22 GB on every run and says nothing. ESCALATE trigger 4 governs this.

### C3 - What leaves the repository entirely

| Path | Lines | Row |
| --- | --- | --- |
| `.github/workflows/probe.yml` | 136 | 1 |
| `backend/tests/workflows/test_runtime_accepts.py` | 52 | 1 |
| `tests/fixtures/runtime/b10598-llama-server-help.txt` | 705 | 1 |
| `.github/scripts/install-llama-runtime.sh` | 45 | 2, folded into `fetch-model-runtime.sh` |
| `backend/utilities/bench_image.py` | 168 | 3 |
| `.github/workflows/measure.yml` job `image` | 34 (L416-449) | 3 |
| the `bench-image` extra and the empty `measure = []` extra | `pyproject.toml:125-128`, `:131` | 3 |
| `backend/tests/workflows/test_bench_input_drift.py` | 198 | 6 |
| the four `tests/fixtures/runtime/2026-08-29-3-shard-*.server-head.txt` captures | - | 7 |

`.github/scripts/` goes from 9 scripts to 8. **`start-llama-server.sh` stays**, unchanged.

### C4 - The assertions that survive, named by the defect each catches (rows 6, 7)

**This is the keep-list. A worker deletes everything in these five modules that is not on it.** Line numbers are on the tree at `origin/main`, 2026-09-21.

| Module | Line | The defect it catches |
| --- | --- | --- |
| `test_bench_targets.py` | 78, lines 106-110 only | Three benchmark jobs compute the weights cache key three times. Two spellings means one job refetches 4.22 GB while its sibling restores. **This is welded to a target enumeration inside one test function and must be split out before the rest of the function is deleted** |
| `test_bench_targets.py` | 177 | A dispatch writes `config/` instead of a scratch copy, so a benchmark silently redefines production |
| `test_bench_targets.py` | 240 | The server case reads nothing from the raw case, so a two-stage measurement reports half a run |
| `test_bench_targets.py` | 273 | The raw case fetches weights with no `--expect-sha256`, so a hub error page is measured as a model |
| `test_bench_targets.py` | 436 | A benchmark machine row lands in the tree the console reads, so an operator panel shows a dispatch as production |
| `test_bench_targets.py` | 587 | A benchmark stage reaches the production state root |
| `test_model_server_jobs.py` | 229 | `start-llama-server.sh` accepts a call it cannot serve |
| `test_model_server_jobs.py` | 255 | The limit check swallows an unrelated startup error, so a real failure reads as a limit |
| `test_model_server_jobs.py` | 341 | The memory sampler appends a column at the end and the reader indexes by position, so a process id prints as a size in kilobytes. The only place in this module where two pieces of our own code disagree silently |
| `test_model_server_jobs.py` | 367 | The kernel peak is written twice, so the second write hides the first |
| `test_weights_and_model_refs.py` | 69 | A fetch without `-f` and `--retry` saves an error page as weights |
| `test_weights_and_model_refs.py` | 88 | A fetched file is read before it is checked |
| `test_weights_and_model_refs.py` | 119 | The health check does not name the weights that answered |
| `test_weights_and_model_refs.py` | 138 | An arm measures before it knows which model answered. A number under the wrong name |
| `test_weights_and_model_refs.py` | 182 | A workflow writes a moving reference, so a rerun fetches different bytes under the same name |
| `test_weights_and_model_refs.py` | 372 | A workflow indexes a config key that does not exist, failing mid-job on a `KeyError` a grep cannot find |
| `test_weights_and_model_refs.py` | 456 | **The weights cache key omits the build, so a cached binary is served under a new build's name.** Keep, and convert its enumeration to discovery |
| `test_pinned_versions.py` | 63, the four checks named in C5 | The pin is spelled in a second place, or a converted caller copies its value |
| `test_pinned_versions.py` | 136 | A llama.cpp fetch that is not pinned and not digest-checked |
| `test_pinned_versions.py` | 151 | A workflow takes whichever release is newest |
| `test_pinned_versions.py` | 167 | An action is not pinned to an approved major |
| `test_pinned_versions.py` | 197 | A `setup-python` version outside `requires-python`, so CI tests an interpreter the package refuses |

**Two things on that list are not kept as written.** The cache-key test at `test_weights_and_model_refs.py:456` iterates `MODEL_SERVER_CALLERS`; row 7 replaces that with discovery. The pin test at `test_pinned_versions.py:63` keeps four of its checks and loses two; C5 says which.

**Named for the avoidance of doubt, because they look like controls and are not:**

| Deleted | Why |
| --- | --- |
| `test_weights_and_model_refs.py:415` ("no inline program rebinds a name it read from the environment") | **Vacuous.** Eight inline programs across four workflows and zero bind a name from `os.environ`, so `assert not shadowed` passes by finding nothing, and unlike its neighbour at line 371 it carries no anti-vacuity anchor. It is also not the Guardrail #11 control - `test_triggers.py:191-199` is, and no row touches it. The pull request body names the holder |
| `test_model_server_jobs.py:420` and `:447` (the two log-format assertions) | They grep llama.cpp's own log format against four committed captures and require a better-than-half line match. The step they guard, `digest.yml:737`, is `if: always()`, its grep ends `\|\| true`, and it writes to the job log and nothing else - no ledger, no gate, no published surface. A llama.cpp release turns them red while production is unaffected. **The structural replacement is two lines in the step**: count matched, count total, echo `matched N of M`. That reports on the real log on the real build on every run |
| `test_model_server_jobs.py:73` (every server-starting job reaches the one argv builder) | Policing authorship. It refuses the shape the next workflow needs |
| `test_model_server_jobs.py:143` (the five-step closed world) | Same |
| `test_pinned_versions.py:45` (every workflow spells the same pin in its own `env:`) | After row 5 its input set `LLAMA_INLINE_RUNTIME_WORKFLOWS` is **empty**, so it asserts over nothing. The conversion is what kills it |
| `test_bench_input_drift.py`, all 8 | Two are draft cases. Six assert that a dispatch form's options match a Python module's options - both sides are ours, and the assertion is that the author wired it the way the author wired it |

### C5 - The one rule for a written list (row 7)

**If the repository can compute the list, compute it - and assert the computed list is non-empty. If the list encodes a judgement the repository does not contain, keep it written down.** Carmack's ruling; it applies to any of the 255 names in `_harness.py` without asking.

The non-empty clause is load-bearing. It is the anti-vacuity anchor generalised, and without it a worker converts a real control into a tautology and the suite goes green on an empty glob. ESCALATE trigger 2 governs it.

Applied:

| Constant | Ruling |
| --- | --- |
| `MODEL_SERVER_CALLERS` | **Discover.** Every job whose steps carry `uses: ./.github/actions/model-server`. Non-empty |
| `SERVER_STARTERS`, `EXPECTED_WORKFLOWS`, `MEASUREMENT_TARGETS`, `RUNTIME_CANDIDATES` | Computable. They die with the tests that read them |
| `WEIGHTS_CHECKS` | **Splits on the rule.** The checks that exist are discoverable and become one; the checks that *ought* to exist are the assertion and stay written |
| `PINNED_LLAMA_BUILD`, `PINNED_LLAMA_ASSET`, `PINNED_LLAMA_SHA256` | **Read from `.github/scripts/llama-cpp-pin.sh`**, not duplicated. This is what takes a pin bump from 4 edits to 1 |
| `LLAMA_SCRIPT_CALLERS`, `LLAMA_INLINE_RUNTIME_WORKFLOWS` | Redundant after row 5 converts the last inline caller. `LLAMA_RUNTIME_WORKFLOWS` becomes a discovery over the workflows that reach the fetch script |
| `RUNTIME_LOG_LINES`, `RUNTIME_LOG_CAPTURES`, `RUNTIME_LOG_UNCLAIMED_TAG`, `RUNTIME_LOG_SUMMARY_STEPS` | Die with the two log-format assertions |
| `DISPATCH_INPUT_SHAPES` | **Stays written.** It encodes the shape an input must have, which the repository does not otherwise contain, and `test_triggers.py` is out of scope |

`test_pinned_versions.py:63` after the conversion keeps four checks, all of them discoveries: no shipped script other than the pin script spells a pin name; the fetch script's call closure reaches the pin script; no workflow carries a pin value in any string; and the set of workflows reaching the fetch script is non-empty.

### C6 - The harness, after the pass (row 9)

**`_harness.py` holds only names imported by two or more modules, plus the real-git-repo commit-script fixture.** That is the rule, and it is mechanically checkable. Every name imported by exactly one module moves into that module.

**No line-count target is written down.** 25 names shared by four or more modules are about 240 lines, the git fixture is about 400 on its own, and 43 names sit at two or three consumers. A number invented on top of those is a target somebody games. Record the before and after as a reading (Guardrail #10).

| Reading | Value, 2026-09-21 |
| --- | --- |
| Top-level names | 255 |
| Imported by nobody | 36 - **grep each as a string before deleting it**, because a name can be reached by text rather than by import |
| Imported by exactly one module | 151 |
| Imported by two or three | 43 |
| Imported by four or more | 25 |
| Consumer modules | 22 |

**The real-git-repo commit-script fixture stays whole and is not dragged into the move-to-consumer pass.** `test_staged_paths.py`, `test_daily_commit_steps.py` and `test_commit_script.py` all use it, and row 20's death leaves all three untouched.

### C7 - What this plan does not touch

| Surface | Why |
| --- | --- |
| `config/models/` | Plan 41's. Two branches on one file is the churn the grouping exists to remove |
| `backend/idhazh/contracts/`, `backend/idhazh/llm/`, `backend/idhazh/config.py` | Plan 41's |
| The three weights cache keys | C2 |
| `test_triggers.py` | It holds Guardrail #11 on the workflow side |
| `test_staged_paths.py`, `test_daily_commit_steps.py`, `test_commit_script.py` | The commit surface, now that the four-calls row is dead |
| Guardrail #11, Guardrail #12, `CLAUDE.md` | No clause of the engineering contract is contradicted by any row here |

### C8 - The reading this plan is judged on

The headline is re-measured at B3's close and written into `docs/reference/ci-model-runtime.md` (Guardrail #10).

| Reading | Before | Gate |
| --- | --- | --- |
| Test lines per workflow line | 1.88 (11,659 / 6,216) | **at or under 1.3.** If the ratio is still near 1.8, an absolute line count that looks good is a failure dressed as a success, and the next question is which module is still enumerating |
| Places the llama.cpp pin is written | 4 | **1** |
| Constant tables to edit before a new server-starting job passes | 5 | **0** |
| Seconds before a benchmark arm notices a dead server | 900 and 600 | **2 and 2** |

`backend/tests/workflows/` lands near 8,000 lines from 11,659 by arithmetic on the per-module rulings. That is a projection, not a measurement, and it is not a gate. **The ratio is the gate.**

## Section 2 - Row #1 - The capability probe goes

- **Scope:** Delete the workflow that asked the pinned build what it accepts, the test that read its recording, the 705-line recording, and every page that describes them.
- **Files touched:**
  - `.github/workflows/probe.yml` (deleted)
  - `backend/tests/workflows/test_runtime_accepts.py` (deleted)
  - `tests/fixtures/runtime/b10598-llama-server-help.txt` (deleted)
  - `backend/tests/workflows/_harness.py` (the `probe.yml` entry in `EXPECTED_WORKFLOWS` at line 76, in `LLAMA_RUNTIME_WORKFLOWS` at line 234, in `LLAMA_SCRIPT_CALLERS` at line 258, and the `LLAMA_SERVER_WORKFLOWS` subtraction at line 279)
  - `docs/reference/ci-model-runtime.md` (lines 13, 14, 42, 100, 105)
  - `docs/reference/github-actions.md` (lines 26, 714, 731, 743)
  - `docs/reference/host-metrics.md` (line 174)
  - `docs/architecture/summarize/model-boundary.md` (line 467)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, and `python backend/utilities/doc_load.py` before and after; CI - full suite. ESCALATE trigger 3 applies.
- **Oracle:** no file outside `TODO/` names `probe.yml`, the help fixture or the recorded option listing, proved by a census across `.github/`, `backend/`, `frontend/`, `config/` and `docs/`. What it cannot settle: whether anything wanted the recording - nothing did, and `test_runtime_accepts.py` was its only committed consumer.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The probe's only consumer is the test being deleted. A dispatchable workflow with no consumer is a file people have to reason about | Carmack |
 | 2 | **The real size is 893 lines, not the 184 the superseded row claimed** - `probe.yml` is 136 and `prune.yml` is 184. The 705-line help fixture is the largest part and the superseded row did not name it | Carmack |
 | 3 | **`PINNED_LLAMA_BUILD` is not deleted here.** `test_pinned_versions.py:57` reads it. Row 7 takes it, by making the harness read the value from the pin script rather than duplicating it | Andre |
 | 4 | **Four doc pages name the probe and the superseded row listed one.** A deletion that leaves dangling references in the pages the agent bootstrap routes to is how the thing comes back | Fowler |
 | 5 | `backend/idhazh/contracts/knobs/models.py:24` also cites the probe. That file is plan 41 row 5's and is deleted there; this row does not touch it | Fowler |
 | 6 | The defect the probe was written for is traced in row 8, not waved away. The superseded row's sentence "now fails at the health check" is false - no health endpoint decodes a token | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the probe as an operator tool | A dispatchable workflow with no consumer is a file people have to reason about, and it is the only workflow calling the installer, which keeps two scripts apart | 893 lines kept, and row 2 blocked. The same answer is one command against a running server | Carmack |
 | 2 | Keep the fixture and refresh it on each pin bump | A recorded help text is a fact about a release note, and refreshing it is the fourth edit in a pin bump | A 705-line file and a permanent re-recording obligation | Fowler |

## Section 3 - Row #2 - Two runtime scripts become one

- **Scope:** Fold `install-llama-runtime.sh` into `fetch-model-runtime.sh`, because the probe was the only caller that wanted the install without weights.
- **Files touched:**
  - `.github/scripts/install-llama-runtime.sh` (deleted, body folded in)
  - `.github/scripts/fetch-model-runtime.sh`
  - `backend/tests/workflows/_harness.py` (`LLAMA_SHARED_SCRIPTS`, `LLAMA_RUNTIME_SCRIPT` and the script-closure helper)
  - `docs/reference/github-actions.md` (line 743, the note explaining why there are two)
  - `docs/reference/ci-model-runtime.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, `shellcheck` on the merged script; CI - full suite. ESCALATE trigger 3 applies.
- **Oracle:** `test_script_invocation.py::test_every_shipped_script_is_one_a_workflow_runs` is green, which requires `set(named) == set(shipped)` over `.github/scripts/*.sh`. **It is red on the base tree once row 1 lands and row 2 has not**, which is the check doing its job. What it cannot settle: whether the merged script still fetches the same bytes - the digest check in the same script settles that, and row 5's dispatch proves it on a runner.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The split's stated reason dies with row 1.** `install-llama-runtime.sh:4-8` says in its own header that it is held apart because `probe.yml` asks the binary and opens no weights | Carmack |
 | 2 | The merged script keeps `fetch-model-runtime.sh`'s name and its environment contract - `GITHUB_TOKEN`, `WEIGHTS_REPO`, `WEIGHTS_REVISION`, `WEIGHTS_FILE`. No caller changes | Carmack |
 | 3 | It still sources `llama-cpp-pin.sh` rather than spelling the pin. One home stays one home | Carmack |
 | 4 | This row is in B1 with row 1, not B2. The set-equality test makes them one change | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep both scripts and let the installer have no caller | `test_script_invocation.py:111` is set equality in both directions, so a shipped script no workflow runs is red | 45 lines kept and a red suite | Fowler |
 | 2 | Delete the installer and inline its body into the action instead | The action is one of three callers of the fetch path; inlining there leaves the other two without an installer | About 45 lines moved and two callers broken | Carmack |

## Section 4 - Row #3 - The image benchmark goes

- **Scope:** Delete the image-diffusion benchmark, its job, its utility, its extra and the empty extra beside it - and with them an unpinned third-party checkout inside a step that cannot fail.
- **Files touched:**
  - `backend/utilities/bench_image.py` (deleted)
  - `.github/workflows/measure.yml` (the `image` job at L416-449, the `image` dispatch target, and the `pip install -e ".[measure]"` at L476)
  - `pyproject.toml` (the `bench-image` extra at L125-128, the empty `measure = []` at L131, and the `diffusers.*` entry in the type-checker override at L218)
  - `backend/tests/workflows/_harness.py` (`MEASUREMENT_TARGETS`)
  - `backend/tests/workflows/test_bench_targets.py` (the image target cases)
  - `docs/how-to/run-the-gates.md` (lines 229, 233)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, and `pip install -e ".[dev]"` resolving in a clean environment; CI - full suite.
- **Oracle:** no file imports `diffusers`, the dependency declaration no longer names it, and no workflow step installs a package from a git reference - proved by a census over `.github/`, `backend/` and `pyproject.toml`. What it cannot settle: whether anybody wanted the measurement. Nobody dispatched it; the job's own comment records that both earlier attempts died before the image finished.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The reason is the unpinned checkout, not the wheels.** `measure.yml:431` runs `pip install "git+https://github.com/huggingface/diffusers"` - a moving main branch, no pin, no digest - inside a job whose next command ends `\|\| echo "Z-Image-Turbo did not complete on this runner"` and so cannot fail. That is the exact shape `test_pinned_versions.py:151` exists to refuse, one package manager along | Carmack |
 | 2 | **It removes one wheel from the manifest, not two.** `torch>=2.5` is in both the `bench-image` and `faithfulness` extras and `faithfulness` is installed live by `digest.yml:443` and `validate.yml:243`. Only `diffusers` leaves, and the job never installed it from the manifest anyway | Carmack |
 | 3 | `measure = []` is an empty extra that `measure.yml:476` installs, resolving to the base package. It is the dependency row's, and it goes here | Fowler |
 | 4 | Timing image diffusion on a runner answers nothing about a news digest, and Guardrail #8 asks a dependency to name its beneficiary feature - when the feature goes, the dependency goes in the same change | Carmack and Fowler |
 | 5 | The faithfulness scorer's wheels stay. It has a live consumer: a qualification gate that decides publication | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Pin the diffusers install and keep the job | Pins a package for a measurement nobody has dispatched and nobody reads, in a job that still cannot fail | One pin line, a 120-minute dispatch slot, and a step that reports nothing | Carmack |
 | 2 | Keep the utility as an operator tool outside the workflow | The tool is the dependency. Keeping one keeps both, and the unpinned install is in the workflow, not the tool | The extra, for a measurement nobody has asked for | Carmack |

## Section 5 - Row #4 - The draft head leaves the workflows

- **Scope:** Delete speculative decoding from every workflow, action, script and workflow test - a pure deletion with no replacement mechanism.
- **Files touched:**
  - `.github/actions/model-server/action.yml` (the four draft inputs at L30-43, the pass-through at L112-114, the draft verify at L122-130)
  - `.github/scripts/fetch-model-runtime.sh` (the `DRAFT_*` documentation at L14 and the conditional fetch at L45-52)
  - `.github/workflows/digest.yml` (L98-101), `llm-council.yml` (L80-83), `validate.yml` (L107-110, L299-301), `idhazh-pipeline-tests.yaml`
  - `.github/workflows/measure.yml` (the `no_draft` and `draft_depth` dispatch options at L64-65, the fetch and verify draft steps at L303-332)
  - `backend/tests/workflows/_harness.py` (`DRAFT_REF_OUTPUTS`, the draft entries in `WEIGHTS_CHECKS` and `MODEL_ENV_NAMES`)
  - `backend/tests/workflows/test_weights_and_model_refs.py` (the draft tests at lines 279, 575, 602, 621), `test_bench_targets.py` (770, 786, 808, 833), `test_bench_input_drift.py` (153, 178)
  - `docs/` pages describing it
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** no file under `.github/` or `backend/tests/workflows/` contains `draft`, `spec-type` or `speculat`, proved by grep. What it cannot settle: whether the Python and contract surface is gone - that half is plan 41 row 3's, and the census closes again at this plan's close.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | It is deleted rather than kept unused. A measurement on 2026-09-12 found it changes the output on nine articles of nine, so it was never a free speed-up | Owner ruling 2026-09-21 |
 | 2 | **No `companion_files`, no landed-path output, no general fetch loop.** You do not build an extension point with zero consumers to hold a capability this repository measured as harmful. Three concrete usages earn an abstraction; there are none | Fowler and Carmack, agreed |
 | 3 | **This row touches no model file.** The draft blocks in `config/models/gemma-4-e4b-qat.json` and `gemma-4-e4b-qat-no-draft.json` leave with plan 41 row 3. A workflow that stops reading a key from a file that still carries it is correct for one release | Fowler |
 | 4 | **The `WEIGHTS_CHECKS` entry for `("measure.yml", "llama-bench")` names the two draft steps and goes in the same commit as the steps.** Row 7 keeps the per-entry weights guards; a kept guard pointing at a deleted step fails on merge | Carmack |
 | 5 | The rule that a value crossing into a web address or a command argument is a single bare word survives with nothing new to apply it to. It already binds `weights_repo`, `weights_revision` and `weights_file`, and `test_triggers.py` holds it (Guardrail #11) | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Generalise the fetch into a list of companion files so the capability returns as configuration | An extension point with zero consumers, built to hold a capability measured as harmful, inside a plan named for deletion | About 60 lines across the action, the script and the installer's output surface, plus a new bare-word check on three fields | Fowler and Carmack |
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
- **Oracle:** the dispatch prints the build tag it resolved and the sha256 it verified, and both equal what `.github/scripts/llama-cpp-pin.sh` prints. **Only a runner can fail this.** A shell-level dry run is a proxy and is not accepted alone - the real download happens once. What it cannot settle: how long the fetch takes, which is not what this row changes.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **`measure.yml` is the only workflow that hand-writes the install.** `LLAMA_INLINE_RUNTIME_WORKFLOWS` at `_harness.py:261` resolves to `{measure.yml}`; `validate.yml:302` and `idhazh-pipeline-tests.yaml:182` already call the shared script. The superseded row's "seven hand-copied blocks" counted shapes, not copies | Carmack |
 | 2 | **The conversion and the census deletion are one commit, or neither happens.** `test_pinned_versions.py:45` is the only thing holding `measure.yml:102-104` equal to the pin script. Delete the census while the literal is still there and the benchmark can pin one build while the pipeline runs another, and every dossier number written in that window carries a wrong build name (Guardrail #10) | Andre |
 | 3 | **No cache key changes.** See C2. The conversion is about where the pin is read, not about what is cached | Carmack |
 | 4 | **No composite action is written here.** The four all-in-one callers keep their own spelling; the scope-out table names the count that would change that | Carmack |
 | 5 | The `budgets` job keeps its own start and health steps. It is the one benchmark arm that stands a server up as a step, and folding it into an action is the out-of-scope question | Carmack |
 | 6 | The `runtime` job starts its server inside `backend/utilities/runtime_sweep.py` because it sweeps a setting and needs the process handle. That stays; row 8 gives it a liveness check | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Write one composite action taking a model file path, replacing all seven sites | The seven sites are four different shapes - fetch-verify-start-health as a unit; fetch-verify then a benchmark binary with no server; one fetch then two starts with different slot counts; fetch then start inside a Python module. One action covering four shapes needs a mode input, which is the copies with a dispatch on top, in a file nobody reads | A week of arguing about the modes, and a merged thing that saves no edits because a new workflow still picks one | Carmack |
 | 2 | Change the cache key to a build tag plus a digest of the file listing | Orphans every existing entry. The production key is `llm-<file>-<revision>-b10598-v4`, weights are 4.22 GB, and `digest.yml` job `work` is a four-shard matrix with a ceiling of eight, so the first run after merge pulls 16.9 GB and 33.8 GB at the ceiling | One run's tax, measurable as the `Fetch runtime and weights` step duration on the next cold run. It cannot fail a run, but it buys nothing this plan needs | Carmack |
 | 3 | Replace the unconditional verify with a per-file skip-or-fetch | Turns a loud failure into a silent self-heal. `action.yml:105` has no `if:` and its comment says why: a restored entry is the one case where nobody watched the bytes arrive. A poisoned entry would be re-downloaded on every run until eviction, and nothing would record it | About 4.22 GB a run, billed silently, for a defect that used to report itself once | Carmack |
 | 4 | Convert first and delete the census in a follow-up | That is the window. See decision 2 | Nothing saved; it is a sequencing error with a wrong-name consequence | Andre |

## Section 7 - Row #6 - The benchmark tests shrink to the six that name a defect

- **Scope:** Cut `test_bench_targets.py` from 28 tests to the six on the keep-list, delete `test_bench_input_drift.py` whole, and split the cache-key agreement out of the test it is welded to before deleting the rest of that function.
- **Files touched:**
  - `backend/tests/workflows/test_bench_targets.py`
  - `backend/tests/workflows/test_bench_input_drift.py` (deleted)
  - `backend/tests/workflows/_harness.py` (`MEASUREMENT_TARGETS`, `BENCH_*`, `RUNTIME_CANDIDATES` and the benchmark dispatch shapes)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** adding or removing a benchmark dispatch option requires no test edit, demonstrated by the draft-case and image-target removals that rows 3 and 4 already made passing with no constant changed. **That check fails on the base tree**, which is the defect the row exists for. What it cannot settle: whether the six kept assertions still cover the benchmark - they cover six named defects and nothing more, and C4 says which.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The split comes before the delete.** `test_bench_targets.py:78` carries the three-job cache-key agreement at lines 106-110 inside a function whose rest is a target enumeration. Deleting the file to remove a table inside it is not a deletion, it is a loss. Extract lines 106-110 into their own test in its own commit, then delete around it | Fowler |
 | 2 | A test enumerating a workflow's options makes every option change a two-file change | Carmack |
 | 3 | The benchmark workflow keeps its jobs. This row removes the tests that fossilise them | Carmack |
 | 4 | `test_bench_input_drift.py` goes whole: two tests are draft cases and six assert that a dispatch form's options match a Python module's options. Both sides are ours, and the assertion is that the author wired it the way the author wired it | Fowler |
 | 5 | `test_bench_targets.py:421` ("every job says what it does") goes. A missing `name:` is a lint, not a defect | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete `test_bench_targets.py` whole | It carries six assertions that name a defect, including the blast-radius guard that stops a benchmark stage reaching the production state root | 1,006 lines removed and six controls with them | Fowler |
 | 2 | Edit the constants and keep the enumerations | Pays the toll once and leaves it standing | About 8 lines now and the same again every time | Carmack |
 | 3 | Delete the benchmark workflow entirely | It answers a real question - raw throughput on a machine - that no other workflow answers | 1,226 lines removed and no way to measure a model's ceiling. Revisit once the pipeline test reports per-article speed | Carmack |

## Section 8 - Row #7 - The server, weights and pin censuses become discovery or die

- **Scope:** Cut three workflow test modules to the assertions on the keep-list, convert every written list the repository can compute into a computed one with a non-empty assertion, delete the two log-format assertions and replace them with a count in the step they guarded, and delete the vacuous environment-rebinding test.
- **Files touched:**
  - `backend/tests/workflows/test_model_server_jobs.py`
  - `backend/tests/workflows/test_weights_and_model_refs.py`
  - `backend/tests/workflows/test_pinned_versions.py`
  - `backend/tests/workflows/_harness.py` (`MODEL_SERVER_CALLERS`, `MODEL_SERVER_STEPS`, `SERVER_STARTERS`, `EXPECTED_WORKFLOWS`, `WEIGHTS_CHECKS`, `LLAMA_RUNTIME_WORKFLOWS`, `PINNED_LLAMA_*`, `LLAMA_PIN_NAMES`, `LLAMA_PIN_VALUES`, `RUNTIME_LOG_*`)
  - `.github/workflows/digest.yml` (the `Prompt cache log summary` step at L737)
  - `tests/fixtures/runtime/2026-08-29-3-shard-*.server-head.txt` (deleted)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite. ESCALATE trigger 2 applies.
- **Oracle:** **a new workflow that stands a model server up passes the suite with no constant edited**, demonstrated against a throwaway workflow file added and removed inside the test run. That check fails on the base tree, which is the defect the row exists for. Second half, and the one that can fail quietly: every converted check asserts its computed list is non-empty, verified by a deliberate empty-glob arm. What it cannot settle: whether a deleted assertion was load-bearing - C4 is the keep-list and it was written from the code, not from the file names.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The rule is one line and a worker applies it without asking:** if the repository can compute the list, compute it and assert it is non-empty; if the list encodes a judgement the repository does not contain, keep it written down. C5 applies it to each constant | Carmack |
 | 2 | **Keep the weights cache-key test at `test_weights_and_model_refs.py:456` and convert its enumeration.** It is a wrong-name control by its own docstring: a key omitting the build serves a cached binary under a new build's name. Discover the callers from the jobs carrying `uses: ./.github/actions/model-server` | Andre |
 | 3 | **The two log-format assertions go, and the fix is in the step, not in a test.** They grep llama.cpp's own format against four committed captures; the step they guard is `if: always()`, its grep ends `\|\| true`, and it writes only to the job log. Replace with two lines in the step: count matched, count total, echo `matched N of M`. That reports on the real log, on the real build, on every run, and it tells the truth when llama.cpp renames a field | Fowler |
 | 4 | **`test_weights_and_model_refs.py:415` is deleted, not anchored.** Zero of the eight inline programs bind a name from `os.environ`, so it cannot fail, and a test that cannot fail is worse than no test because a reviewer reads it as cover. `test_triggers.py:191-199` is the holder and the pull request body says so | Andre and Carmack, agreed |
 | 5 | **The harness reads the pin from `llama-cpp-pin.sh` instead of duplicating it.** That is what takes a pin bump from four edits to one, and it is the plan's own measure | Carmack |
 | 6 | **`test_pinned_versions.py:63` survives with four checks, all discoveries**, and loses two: the pin-script self-comparison, which becomes a tautology once the values are read from the script, and the `LLAMA_SCRIPT_CALLERS` split, which is redundant once row 5 converts the last inline caller | Carmack |
 | 7 | Keep every per-entry weights guard: pinned and digest-checked, the refusal to take whichever release is newest, `curl -f --retry`, the health check naming the weights that answered, and the refusal to measure before it passes. Those guard bytes this project downloads and numbers it reports | Carmack |
 | 8 | Delete the caller enumerations, the five-step closed world, the one-argv-builder census and the workflow census. All four police authorship and all four refuse the shape the next workflow needs | Carmack |
 | 9 | `test_triggers.py` is untouched. It is the workflow-side Guardrail #11 control | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete all three modules | Twenty of the assertions across them name a defect, including seven about bytes this project fetches and the one that stops a number being reported under the wrong build | About 1,500 lines removed and a fetch that could silently take the newest release | Carmack |
 | 2 | Keep the closed-world tables and edit them as workflows arrive | That is today, and it is the five-table toll this row exists to remove | Five edits before any new server-starting workflow passes, every time | Carmack |
 | 3 | Anchor `test_weights_and_model_refs.py:415` instead of deleting it | Authoring a fixture with a shadowed name purely to prove the test can see one, to keep a duplicate of a control `test_triggers.py` already holds | A fixture and a permanent second copy of one control | Carmack |
 | 4 | Keep the two log-format assertions and re-record the captures on each pin bump | A test asserting a grep against a recorded capture can only say what was true on 2026-08-29, and a llama.cpp release turns it red while production is unaffected | About 100 lines, four constants, four fixtures, and a re-recording obligation on every bump | Fowler |

## Section 9 - Row #8 - The benchmark arms learn the server died

- **Scope:** Give the two benchmark arms that start a server outside `start-llama-server.sh` the two-second liveness check that script already does.
- **Files touched:**
  - `.github/workflows/measure.yml` (after the inline start at L988, before the health loop at L989)
  - `backend/utilities/runtime_sweep.py` (after the start at L284, before the wait loop)
  - `backend/tests/test_*` for the sweep's start path
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'runtime or sweep' -q`, `shellcheck`; CI - full suite. Covered by row 5's dispatch.
- **Oracle:** a server started with a flag the build refuses is reported within about two seconds in both arms, driven by starting the real binary with a deliberately bad flag in a local test rather than by a dispatch. What it cannot settle: the class where the build accepts a flag at parse and refuses it at decode. No health endpoint decodes a token, so `/health`, `/v1/models` and `/props` cannot see it; the scope-out table names the measurement that would price a pre-flight decode here.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **This is the honest replacement for what row 1 deletes.** The probe existed because a run died after five hours on a flag the build refused. The superseded row claimed the defect now fails at the health check; it does not, because no health endpoint decodes | Andre |
 | 2 | **Two seconds against 900 and 600.** `measure.yml:989` loops `seq 1 180` at 5 s and `runtime_sweep.py:284` loops 120 at 5 s, and neither checks the process is alive at all. `start-llama-server.sh:67` already does `sleep 2; kill -0`; this is the same two lines in two more places | Andre |
 | 3 | The saving is a worst-case bound read off the literals, not a measurement: 900 s and 600 s become 2 s, in the arm somebody runs repeatedly while sweeping flags, against a 6 h job | Carmack |
 | 4 | It rides in B2 rather than getting its own pull request. Row 5 already rewrites `measure.yml`'s runtime path, so two lines there have no separate review cost | Carmack |
 | 5 | The pre-flight decode for these two arms is named in the scope-out table with the measurement and the threshold that would settle it, not taken here. A call plus its failure handling in two more arms is how three pull requests become five | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Take nothing, since this is an addition in a deletion plan | Row 1 removes a signal; the honest replacement for a removed check is the cheaper check that catches the same class. Four lines total | Fifteen minutes of runner time per occurrence in the arm most often re-dispatched | Carmack |
 | 2 | Route both arms through `start-llama-server.sh` | The `runtime` arm sweeps a setting and needs the process handle, which is why it starts its server inside a Python module | A rewrite of the sweep's process handling for a liveness check two lines give it | Carmack |
 | 3 | Add a pre-flight decode to both arms now | A call plus its failure handling in two more arms, in files this pull request is already rewriting, turns three pull requests into five | One measurement - the two real completions at benchmark context length on a stock runner, three repetitions, hardware and date recorded - and a threshold of 10 s to decide it | Carmack |

## Section 10 - Row #9 - The harness keeps only what more than one module reads

- **Scope:** Move every name in `_harness.py` imported by exactly one module into that module, delete the names nothing reads, and record the before and after.
- **Files touched:**
  - `backend/tests/workflows/_harness.py`
  - the 22 modules under `backend/tests/workflows/` that import from it
  - `docs/reference/ci-model-runtime.md` (the C8 readings)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q --collect-only -q` before and after, and the full workflow suite; CI - full suite. No application behaviour changes, so no browser smoke is owed.
- **Oracle:** **the collected test count is identical before and after** - not pass or fail, because a suite stays green when a constant moves to a module nobody imports it from, so pass and fail cannot see this change. Second half: `_harness.py` contains no name imported by fewer than two modules, checked by the same import census that drove the moves. What it cannot settle: whether a moved constant is now in the right module - it is in its only consumer, which is the definition used.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The rule is the contract, not a line count.** After the pass, `_harness.py` holds only names imported by two or more modules, plus the real-git-repo commit-script fixture. That is mechanically checkable and cannot be gamed | Carmack |
 | 2 | **No line-count target is written down.** 25 shared names are about 240 lines, the git fixture is about 400 on its own, and 43 names sit at two or three consumers. A number on top of those is a target somebody games. Record the before and after as a reading (Guardrail #10) | Carmack |
 | 3 | **The 36 names nothing imports are grepped as strings before deletion**, because a name can be reached by text rather than by import. Two are already dead with zero uses anywhere: `CLOCK_STEP` and `CLOCK_VARIABLES` | Carmack and Fowler |
 | 4 | **The commit-script fixture stays whole and is not dragged into the move.** `test_staged_paths.py`, `test_daily_commit_steps.py` and `test_commit_script.py` all use it | Carmack |
 | 5 | The move is mechanical - the consumer set is computable and a one-consumer move is copy and delete. Two parts need judgement and decisions 3 and 4 name both | Carmack |
 | 6 | **It runs last and alone in its own pull request.** It is a structural change with no behaviour, and bundling it with a behavioural change puts both in one review | Fowler |
 | 7 | The four-way file split - YAML parsing, the git fixture, the inline-Python analyser, the tables - is the right end state and is a separate pull request. One addition buys one cut | Fowler |
 | 8 | This row writes the C8 readings into `docs/reference/ci-model-runtime.md`. A plan whose headline number is never re-measured cannot say whether it worked | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Split the harness into four files in this plan | A different question - one file answering many - and it belongs to its own pull request | A large structural refactor bundled into a deletion plan | Fowler |
 | 2 | Delete the unimported names and stop | Leaves 151 one-consumer names, which is 69 percent of the shared surface and the reason every workflow change is a two-file change | About 36 names removed and the two-file change untouched | Fowler |
 | 3 | Do the move inside B2, beside the deletions | Puts a structural change and a behavioural change in one review, and the oracle for each is different - a collected count against a runner dispatch | Nothing saved; one review that cannot judge either half | Fowler |
