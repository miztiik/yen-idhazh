# The shell scripts become Python

**Last Updated**: 2026-09-22

**The filename keeps its old slug.** Three live plans and `TODO/STATUS.md` link this file by name, and one of them is in flight; renaming costs four edits in other agents' files to change an address nobody reads for meaning.

**Level**: 4, and row 3 is why. It rewrites the download and start path the daily run depends on, and only a live dispatch proves it, so a revert lands after a failed publish - CLAUDE.md section 6's Level-4 test. Row 6 is Level 4 for the same reason on the push path. Row 1 is Level 3: `one_bare_word` at `backend/utilities/model_refs.py:41` refuses whitespace and nothing else, while **13 model-file values are pasted textually into `run:` bodies across four workflows**, where a value spelling `$(id)` executes. **It is not a Guardrail #11 question** - that guardrail is about fetched web text, and a model file is neither fetched nor web. Rows 2, 4 and 5 are Level 2.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight - two, because section 1b's readiness table shows two disjoint pairs and never three; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Eleven shell scripts sit between this repository's data and what runs on a runner, and **every invented data format in the repository sits exactly where Python hands something to one of them.** `backend/utilities/llama_argv.py:54` writes the llama-server command line NUL-joined so four workflow blocks can read it back with `mapfile -d ''`. `sample-rss.sh` writes two tab-separated files because shell cannot hold a structure. The model's own JSON is retyped through four layers before anything downloads it, and the arity is welded at two files. `model_refs.py:41` refuses whitespace only, so `../../x.gguf`, `x.gguf$(id)` and a branch name in place of a commit all pass. The llama.cpp pin is spelled twice. The production cache key names no companion. **Every one of these is a shell script being asked to do a program's job.** |
| The rule | **A program is written in Python. A workflow step calls one.** Where Python already owns the answer - the server command line, the memory sampler, the model file - the shell stops being the courier, and the format invented to reach it goes with it. |
| The second rule | **A value this project computes is published, never composed a second time downstream, and never serialised to cross a process this plan can delete.** |
| The measure | **Lines of shell in `.github/scripts/`, and invented data formats.** Shell **1,053 -> 653** in rows 1 to 5, and **-> 0** when row 6 lands; the directory is then deleted. Invented formats: **3 -> 0**. **Re-take both readings at dispatch**: `commit-and-push.sh` grew from 436 to 556 lines and `push-rewritten-history.sh` appeared, both while this plan was being written. |
| Hard scope - in | All eleven scripts are deleted and their work moves into Python: the llama.cpp pin, the runtime install, the weights download, the server launch, the pipeline-test case runner, the memory sampler, the two CI-selection scripts, and - in a blocked row - the commit-and-push program, the state restore and the prune's force-push. The model file gets one reader with a closed field grammar, a landed path, a declared-size check and a cache key over the whole declared set. |
| Hard scope - out | See the table below. Every line there is a dated decision with a price, never a law (CLAUDE.md section 0d). |
| Supersedes | Plan 42 rows 7 to 11, which are `COLLAPSED` in that plan's Reckoner. |
| Assumes | **Plan 41 merged as #1036 and #1039.** `COMPANION_FIELDS`, `_companions()` and the companion-joining `_cache_key` are on `main`. |
| ESCALATE triggers | (1) **Row 3's first commit is tests only and lands RED.** If a commit moves the download before those tests exist, stop - C12 says why the order is the control. (2) Row 3 must leave a digest check that runs on a cache hit. The download runs behind `cache-hit != 'true'`. (3) If any step between the cache restore and the verify acquires `continue-on-error: true`, or the cache step is split into `actions/cache/restore` plus a save with `if: always()`, stop. Both make `actions/cache`'s `post-if: success()` untrue (C11). (4) If the cache key can be anything but 64 lowercase hex characters, stop. (5) **If row 1 deletes any published output key, stop.** The configured verb publishes **ten** keys today, four of them `draft_*` that two production workflows consume (C1). (6) **If the two `llm-` cache keys move in different commits, stop.** (7) **If any row before row 6 edits `commit-and-push.sh`, `take-state-from-the-tip.sh` or `push-rewritten-history.sh`, stop.** (8) **If `_harness.py:1637`'s fetch discovery is not widened in row 3's tests-only commit, stop** - after row 3 the hub URL is inside Python, discovery silently falls from 8 jobs to 4, and the weights oracle goes green covering less than it did (C12). (9) **If a new `.sh` file is added under `.github/scripts/`, stop.** That is a Level 3 design question; one appeared mid-plan and had no owner. (10) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | **Six pull requests in four waves.** Two pairs are disjoint, so the pool is two wide in waves 1 and 3. Fowler ruled the grouping, the import convention and the row transfer; Carmack the download path, the process launch, the cache and the dispatches; Andre the grammar, the refusal messages and the paste rule. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2 - two disjoint pairs, never three.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **`measure.yml`'s four inline weights downloads, its four `candidate_draft_*` job outputs, and its copy of the pin at `:125-127`** | The reader keeps a one-companion projection - four `draft_*` keys - and the pin has two homes. `measure.yml:596` and `:923` keep their own declared-size cross-check and their own paste sites | The four arms reach neither the composite action nor the shared download; the `batched` arm spells `MODEL_*` and is a different shape; the `llama-bench` arm unpacks its own tarball. **And `:125-127` is a workflow-level `env:` block, which cannot read a file** - moving it means adding a pin-reading step to jobs that have no `setup-python` at all (`llama-bench` at `:235`, `batched` at `:1043`). `measure.yml` is plan 46's file in two of its rows. **It becomes a row in plan 46**, which owns the file. **Row 3 adds a test that the three `env:` literals equal the JSON's three**, so the seventh copy cannot drift from the first. Carmack |
| **Refusing `needs.*.outputs.*` inside any `run:` body, repository-wide** | **28** job-output expressions keep reaching a shell through textual substitution rather than `env:` | **It is plan 46's row.** Plan 46 already owns `test_triggers.py`, `digest.yml`, `measure.yml` and `validate.yml` in its group A. Counted by parsing each workflow and matching `needs.<job>.outputs.<key>` inside every step's `run` string, all scalar forms. **What this plan takes free instead**, inside row 3: the same rule scoped to jobs reaching the shared download, which fails today on 8 of the 13. Andre proposed it; Fowler ruled on where it lands |
| **Cutting `backend/tests/workflows/_harness.py` to names more than one module reads** | The module stays 2,248 lines with 241 top-level names, and **a one-file change still has to touch 143 of them** | Plan 46 all-DONE **and** this plan's row 3 merged. Re-run the census - never read a recorded table - and run it as its own plan. An earlier draft's "nine of 45 orphans are internal" was wrong: it is 35 of 45 |
| **Every `run:` body in every workflow** | Workflow steps still contain shell, and some of it is long | Out of reach: a composite action and a workflow step run a shell by definition. What this plan changes is that a step's body becomes **one call to a program**, not a program |
| **A third-party HTTP library** | The downloads use `urllib.request` plus the retry rule in C8 | Guardrail #8 asks for a mature library and prices the dependency. Neither `httpx` nor `requests` is declared in `pyproject.toml`, and neither streams better than a 1 MiB loop. **What brings it in:** the transport failing on the first eight-shard cold fan-out (section 9) |
| **A transport probe comparing `urllib` against `curl` on a real runner** | No head-to-head number | **Refused on Guardrail #10's first clause: the number cannot change what gets built.** The owner ruled the transport, and a probe finding `curl` faster does not reverse it. It also could not see what it would measure: a cold fetch is 57 to 338 s, a 5.9x spread, so three samples an arm is a coin toss with a decimal point, and a paired design with power costs about 68 GB of hub egress. **What replaces it at zero extra runner time:** C8's per-file `INFO` line, one 4.28 GB sample from D1, one 5.68 GB sample from D2, and eight production samples from the first cold fan-out - written into `docs/reference/benchmarks/what-a-bench-dispatch-costs.md` with hardware and date. Carmack |

### What a change costs today

Measured on `origin/main`, 2026-09-22, by reading the files.

| Reading | Value | Where |
| --- | --- | --- |
| Shell scripts, and lines | **11 files, 1,053 lines** | `commit-and-push.sh` **556**, `sample-rss.sh` 108, `start-llama-server.sh` 72, `run-pipeline-test-case.sh` 54, `fetch-model-runtime.sh` 53, `push-rewritten-history.sh` **50**, `take-state-from-the-tip.sh` 47, `install-llama-runtime.sh` 43, `llama-cpp-pin.sh` 34, `changed-docs.sh` 32, `browser-suite-needed.sh` 4 |
| Two of those that did not exist when this plan was first drafted | `commit-and-push.sh` gained **120 lines** in #1051 and #1052; `push-rewritten-history.sh` **landed whole** in #1053 | both on 2026-09-22. This is why re-measuring is a gate rather than advice |
| Invented data formats, and where each sits | **3**, all at a Python-to-shell boundary | `llama_argv.py:54` writes NUL-joined argv, read by **four** workflow blocks with `mapfile -d ''`; `sample-rss.sh:74-76` writes `rss-samples.tsv` and `python-procs.tsv`, the first read by an `awk` program at `digest.yml:888-917` |
| Call sites of `llama_argv.py` | **5**, and **4 are live workflow blocks** outside the script | `idhazh-pipeline-tests.yaml:253`, `:336`; `validate.yml:347`; `measure.yml:972`; `start-llama-server.sh:59`. **Deleting the module without converting all five kills the qualify job, both pipeline-test server arms and the bench runtime arm** |
| Whether Python already builds the llama-server command | **yes.** `start-llama-server.sh:11-13` says so itself | `backend/utilities/llama_argv.py`, 59 lines |
| Whether Python already samples process memory | **yes**, and the function has the same name | `runtime_sweep.py:294` `read_status` reads `VmRSS:`/`VmHWM:`; `:529` starts a `sample_rss` thread |
| Whether `runtime_sweep.py` calls the server script | **no.** It builds `server_argv` in process at `:508` and `Popen`s at `:520` | it is the precedent for the new verb, not a caller to convert |
| Scripts that are **sourced** rather than executed | **2** | `llama-cpp-pin.sh` into `install-llama-runtime.sh`; that into `fetch-model-runtime.sh`. A sourced script sets variables in its caller's shell, which stops mattering the moment both are one program |
| Places the llama.cpp pin is spelled | **2** | `llama-cpp-pin.sh:26-28` and `measure.yml:125-127`. The pin file's header says it exists because the pin "used to be written in six places that had to change together" |
| What `one_bare_word` refuses | **whitespace and empty only** | `model_refs.py:41`. Admitted on a direct call: `../../x.gguf`, `x.gguf$(id)`, `` x.gguf`id` ``, `a"b`, `a;b`, `$(curl${IFS}evil)`, `%2e%2e%2fx`, `/etc/passwd`, `..`, `.hidden`, `x.txt` |
| Keys the configured verb publishes today | **ten, not six** - three `summarize_*` plus **four bare `draft_*`** | `model_refs.py:130` calls `_draft_rows(..., prefix="")`. They are republished at `digest.yml:99-102` and `llm-council.yml:80-83` and consumed at `digest.yml:563-566` and `llm-council.yml:315-318` |
| Model-file values pasted into a `run:` body | **13** | `digest.yml:604`; `idhazh-pipeline-tests.yaml:201`; `measure.yml:330`, `:587`, `:596`, `:914`, `:923`; `validate.yml:320`, `:321`, `:329`, `:367`, `:368`, `:399` |
| Of those 13, how many row 3 removes | **8** - every one in a job reaching the shared download | `measure.yml`'s 5 are out of scope |
| How the weights oracle discovers a fetch | **a literal `huggingface.co/` match on a step's `run:` body** | `_harness.py:1637`. After row 3 the URL is inside Python, so **discovery falls 8 -> 4 and `test_weights_and_model_refs.py:71`'s equality still passes against a four-entry table.** ESCALATE trigger 8 exists for this |
| Cache key formats over `backend/models` | **three, in six steps**, and they are deliberately different | `llm-` at `action.yml:93` and `idhazh-pipeline-tests.yaml:167`; `qualify-` at `validate.yml:284`; `bench-` at `measure.yml:289`, `:570`, `:899`. **A blanket equality clause across all six is false by construction** |
| Whether the weights `file` has any segment rule | **none, in either layer** | `ModelRef.file` is `Field(min_length=1)`; `CompanionFile` validates companions only, in Pydantic, which never runs on the shell path |
| Whether `byte_count` is checked before printing | **no** | `model_refs.py:153` prints it straight |
| Whether every companion's `sha256` is checked | **no** - the projection checks the first only, while `_cache_key` digests every one | `model_refs.py:68-84` against `:86-97` |
| Key length if the existing hyphen-join met seven files | **519 characters**, past GitHub's 512-character cap | `_cache_key` at `model_refs.py:97` |
| Committed model files declaring a companion | **1 of 5**, and it is a bench candidate rather than the pointer | `config/models/gemma-4-e4b-qat.json:5` |
| The production weights entry | **5.68 GB** (`5,680,522,464` bytes) | `config/models/qwen3.5-9b-q4km.json` |
| A cold weights fetch against the restore it replaces | download **57 to 338 s, median about 75**; restore **38 to 95 s**. A **5.9x** spread | `docs/reference/benchmarks/what-a-bench-dispatch-costs.md`, eight `runtime` jobs on the 4.28 GB arm, 2026-09-14 to 2026-09-16 |
| Whether `actions/cache@v6` saves when the job failed | **no.** Its manifest declares `post-if: "success()"`; `save-always` is inert and deprecated | read from the v6 manifest, 2026-09-22 |
| Whether a cache entry written on a branch can be restored on `main` | **no.** Actions restores from the current branch or the default branch | so no dispatch can warm production; the first cron after row 3 merges is eight cold shards |
| Assertions that require `.github/scripts/` to be non-empty | **3**, plus a glob | `test_ci_selection.py:52`, `test_pinned_versions.py:100`, `test_script_invocation.py:99`; `_harness.py:164`'s `SHELLCHECK_COMMAND`. **Row 6 retires all four** |
| Whether `sudo prlimit` runs in the four non-action launch sites | **no - only the action's does today**, while `config/models/qwen3.5-9b-q4km.json:36` asks for `mmap+mlock` and the candidate-config action copies that block onto every candidate | putting it in the shared verb fixes four jobs for free |

## Section 0b - What this plan does, in one list

1. The model file gets one reader: a closed field grammar, a landed path, a declared size, a cache key over the whole declared set, and no published key deleted.
2. The two CI-selection scripts go, and the inventory constant that refuses a twelfth script lands.
3. The model path becomes one Python program - pin, runtime install, download, verify, server launch - the verbs are renamed, both invented argv formats die, and the composite action drops to four inputs.
4. The pipeline-test case runner becomes Python.
5. The memory sampler joins the Python sampler that already exists, and its two tab-separated files become JSON.
6. The last three scripts - the commit-and-push program, the state restore and the prune's force-push - go, and `.github/scripts/` is deleted.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The model file gets one reader, and the grammar closes | - | A | DONE | p44r1 | - | R1 |
| 2 | The two CI-selection scripts go | - | A | DONE | p44r2 | - | R2 |
| 3 | The model path becomes one Python program, and the verbs are renamed | 1 | B | DONE | p44r3 | - | R3 |
| 4 | The pipeline-test case runner becomes Python | 3 | C | PENDING | - | - | - |
| 5 | The memory sampler joins the one that already exists | 3 | C | PENDING | - | - | - |
| 6 | The last three scripts go | plan 46 all-DONE | D | BLOCKED | - | - | - |
| 7 | The benchmark arms learn the server died, and the repeat count is config | - | E | DONE | p42p5 | - | P5 |
| 8 | The harness keeps only what more than one module reads | - | F | COLLAPSED | - | - | - |

**The verb rename lives in row 3, not row 1.** Renaming `configured`, `candidate` and `--also-configured` edits five workflow call sites. In row 1 that would put `digest.yml`, `llm-council.yml`, `validate.yml`, `measure.yml` and `idhazh-pipeline-tests.yaml` into PR-A, PR-A would stop being disjoint from PR-B and PR-E, and wave 1 would collapse to one worker. Row 3 is already rewriting every one of those lines. **Row 1 stays purely additive on the Python side and touches no workflow.**

**The cache key has no row of its own.** `action.yml:93` spells `inputs.weights_file` and `inputs.weights_revision`, and row 3 deletes both; a composite action resolves a deleted input to the empty string, so a separate cache row would leave `llm---<build>-v4` - one key every model shares - for the length of one commit.

**Row 6 is BLOCKED, not out.** It carries `commit-and-push.sh` (556), `take-state-from-the-tip.sh` (47) and `push-rewritten-history.sh` (50) - **653 lines across three files** - and it is the row that deletes `.github/scripts/`. It is a row rather than a scope-out line so this plan cannot close while those lines survive. Its gates are written now, in section 6, not deferred to unblock. **ESCALATE trigger 7 stops any other row reaching into those three files early.**

**Row 7 landed ahead of the earlier sequence and nothing is owed for it.** `runtime_sweep.py:328` carries `START_GRACE_SECONDS: Final = 2.0`; `backend/idhazh/contracts/knobs/bench.py:47` carries `repeats`.

**Row 8 is COLLAPSED into the third line of the hard-scope-out table.** Both collapsed and blocked rows stay in this table: a row deleted from a Reckoner turns a priced decision into a proposal with no author.

### Section 1a - The pull requests and the files each owns

| PR | Rows | Wave | Files it owns |
| --- | --- | --- | --- |
| **PR-A - the model file's reader** | 1 | 1 | `backend/utilities/model_refs.py`; `backend/tests/workflows/test_weights_and_model_refs.py`; `backend/tests/workflows/test_pipeline_tests_workflow.py` (`:683-694` only); `backend/idhazh/llm/server.py` (`:437-439` docstring only). **No workflow, no `_harness.py`** |
| **PR-C - the CI-selection scripts** | 2 | 1, beside PR-A | delete `.github/scripts/browser-suite-needed.sh` (4) and `changed-docs.sh` (32); `.github/workflows/ci.yml` (`:77`, `:118`); `frontend/scripts/test-scope.ts` (`:172`); `backend/utilities/changed_docs.py` (new); `backend/tests/workflows/test_ci_selection.py` (`:52`, `:113`); `backend/tests/workflows/_harness.py` - **the new `SHIPPED_SCRIPTS` constant only** (C14) |
| **PR-B - the model path** | 3 | 2, alone | see the per-file table in section 4 |
| **PR-D - the case runner** | 4 | 3 | delete `.github/scripts/run-pipeline-test-case.sh` (54); `.github/workflows/idhazh-pipeline-tests.yaml` (`:304`, `:315`, `:374`); `backend/utilities/pipeline_test_case.py` (new); `backend/tests/workflows/test_pipeline_tests_workflow.py` (`:94`, `:655`); `_harness.py` (`SHIPPED_SCRIPTS`, one name) |
| **PR-E - the sampler** | 5 | 3, beside PR-D | delete `.github/scripts/sample-rss.sh` (108); `.github/workflows/digest.yml` (`:619`, `:627-629`, `:888-917`); `backend/utilities/memory_sampler.py` (new); `backend/utilities/runtime_sweep.py` (`:294` and `:529`); `backend/tests/workflows/_harness.py` (`SAMPLE_SCRIPT:530`, `RSS_SAMPLE_FILE:512`, the stale `:526-529` comment, `SHIPPED_SCRIPTS`); `backend/tests/workflows/test_model_server_jobs.py` (`:382`); **plus the two plan-doc edits of section 6's transfer** |
| **PR-F - the last three scripts** | 6 | after plan 46 | section 6 |

**PR-D and PR-E both edit `_harness.py`'s `SHIPPED_SCRIPTS` constant**, because each deletes a script. That is one guaranteed conflict, and the resolution rule is mechanical so nobody has to think: **keep both sides' deletions - the list only ever shrinks.** Budget one merge-resolve-push cycle for whichever lands second. The same rule settled the Reckoner conflict between rows 1 and 2 on 2026-09-22: keep each side's own rows.

**`runtime_sweep.py` is not in PR-B.** It has no call to convert. What moves out of it in row 3 is three names - `refuse_a_server_that_died_at_startup`, `START_GRACE_SECONDS`, `LOG_TAIL_LINES` - which go to `backend/idhazh/llm/server.py` beside `server_argv`, where both `runtime_sweep.py` and the new launcher import them. Zero new import edges: both already import that module. The comment at `runtime_sweep.py:322-327` says the duplication exists "because a sweep needs the process handle and so cannot call it"; that reason dies once the function takes a `Popen`, which it already does. **Row 5 still waits on row 3, but because both write `digest.yml`, not because of this file.**

### Section 1b - Readiness, computed rather than read off a letter

| When this is true | Ready together | Parallel N | What it costs |
| --- | --- | --- | --- |
| now | **rows 1 and 2** | **2** | genuinely disjoint - PR-A touches no workflow and no `_harness.py`; PR-C touches `ci.yml` and the new constant only |
| row 1 merged | **row 3**, and row 2 if still in flight | **1 for row 3** | PR-B owns every workflow the model touches. PR-C and PR-B share nothing |
| row 3 merged | **rows 4 and 5** | **2, with one known conflict** | the `SHIPPED_SCRIPTS` constant, resolved by the shrink rule above |
| plan 46 all-DONE | **row 6** | **1** | - |

**Peak workers: 2**, in waves 1 and 3.

### Section 1c - The interlock with plan 46

Plan 46 is in flight with 9 of 17 rows PENDING across waves 3 to 7. PR-B shares `digest.yml`, `validate.yml`, `measure.yml` and `_harness.py` with it; PR-E shares `digest.yml` and `_harness.py`.

**Ruling: land them when ready and let plan 46's branches merge `main` in.** A small branch rebasing under a large one is the cheap direction. **The owner tells plan 46's owner the file list at each dispatch**, so a rebase is expected rather than discovered. **PR-B's `_harness.py` hunk is 18 sites, not the "four entries and a constant" an earlier draft claimed** (section 4's table). That does not change the ruling, but it must be stated at its real size.

**Row 6 is the exception and it does not rebase - it waits**, because a 653-line port cannot be reconciled with edits to the same files in flight.

## Section 1d - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent any shape below; it reads this section.** No persisted payload changes, so CLAUDE.md section 11 owes nothing.

### C0 - How every module in this plan is invoked and imported

**One convention, and it is the one already in the tree.** Every module is run as `python3 backend/utilities/<module>.py <verb>`, and a module that needs a sibling writes `from utilities import <sibling>`.

| Question | Answer |
| --- | --- |
| Why that import works on a runner | `pip install -e .` writes an editable path file exposing the whole of `backend/`, so `import utilities` resolves with no `PYTHONPATH`. **`runtime_sweep.py:33` already does exactly this and runs by path in production at `measure.yml:681`** |
| Why it works under pytest | `pyproject.toml:224` sets `pythonpath = ["backend"]` |
| Why not a bare `import model_refs` | it resolves only when `sys.path[0]` is `backend/utilities`, which is true for a path run and **false under pytest** - it would make the new module untestable, and row 3 ships about 300 lines of download and launch logic that owes a unit tier (CLAUDE.md section 13) |
| Why not `python -m utilities.<module>` with `PYTHONPATH=backend` | there are **38** path invocations under `.github/` and **zero** `-m` invocations; moving even one is a second convention for no gain |
| The failure this hides, and the control | a missing `pip install -e .` is invisible locally because pytest's `pythonpath` covers it. **Row 3 ships a workflow test**: every job that reaches `model_runtime.py`, directly or through the composite action, runs `pip install -e .` in an earlier step. `_harness._steps()` already resolves a repository-local composite action in place, so the walk exists. It is a structure test - only a human editing YAML turns it red |
| There is no "never imported" test | an earlier draft proposed one. It would have cost the entire unit tier on the daily-run download path. **What replaces it:** an AST pass asserting no `idhazh` name appears at module scope in `model_runtime.py`, so the install and download verbs keep working in a job that has not installed the package |

**Every `KEY=value` line any module in this plan writes to `$GITHUB_OUTPUT` passes C2's backstop first. No value is ever escaped for that file; a value that would need escaping is refused.** The heredoc delimiter form appears nowhere in this plan, and a worker who reaches for it has found a value that should have been refused instead.

### C1 - What the model file's reader publishes (rows 1, 3)

`backend/utilities/model_refs.py` keeps one question - what does this model declare, and is every value safe to hand to a program.

**Row 1 is additive on published keys.** It deletes one thing: the `--repo-root` argument, which no caller passes. **Row 3 renames the verbs**, because that edits five workflow call sites.

| Today | After row 3 | Callers |
| --- | --- | --- |
| `configured` | `describe-pinned-model` | the composite action, and `measure.yml` through `--also-pinned` |
| `candidate` | `describe-trial-model` | `idhazh-pipeline-tests.yaml`, `measure.yml`, `validate.yml` |
| - | `list-model-files` | **nothing outside Python.** It returns objects; there is no text form and no separator to choose |
| - | `fingerprint-model-files` | the cache step in `idhazh-pipeline-tests.yaml` only. The action reads its key off the describe call |

`--also-configured` becomes `--also-pinned`. All four verbs take `--config-root`, default `config`.

**There is no row format.** `list-model-files` returns a list of frozen dataclasses. An earlier draft had it print seven tab-separated columns so a shell loop could read them; row 3 deletes the shell loop. **A worker that reintroduces a text form for this has reintroduced the defect this plan is named after.**

**The declared file, as a Python object.** One per file the model declares, weights first, then companions in declared order.

| Field | May be absent |
| --- | --- |
| `repo`, `revision`, `file`, `sha256` | no |
| `flag` - the server flag this file is passed under | **yes** - every weights file has none |
| `landed_path` - `MODELS_DIR` plus the validated `file` | no |
| `byte_count` - the entry's declared size | **yes** |

**The describe verbs publish seven keys today, not six, and row 1 deletes none of them - it adds three, for ten.** (Corrected 2026-09-22 during execution: the first draft of this line said ten were already published. Seven is today's count; ten is the count after row 1. The instruction - delete none, add three - is unchanged.)

| Key group | Names | Who reads them |
| --- | --- | --- |
| the three that exist | `summarize_repo`, `summarize_revision`, `summarize_file` | `digest.yml:95-97`, `llm-council.yml:77-79`, `measure.yml:138-140` -> `:1039-1041` |
| **the four that exist and an earlier draft missed** | `draft_repo`, `draft_revision`, `draft_file`, `draft_sha256`, **bare, no prefix** | `model_refs.py:130` calls `_draft_rows(..., prefix="")`. Republished at `digest.yml:99-102` and `llm-council.yml:80-83`; consumed at `digest.yml:563-566` and `llm-council.yml:315-318` |
| the three row 1 adds | `summarize_weights_path`, `summarize_cache_key`, `summarize_id` | the composite action, after row 3 |

**Deleting the four `draft_*` keys in row 1 would break production between waves.** Row 1 merges in wave 1; row 3 deletes their consumers in wave 2. In between, `digest.yml` (five crons a day) and `llm-council.yml` (nightly) would hand the action four empty draft inputs, `action.yml:120` would skip the draft download and `:135` would skip its digest check - the exact "a guard goes false and a verify becomes a no-op" failure this plan refuses elsewhere. **Row 3 deletes them, with their consumers, in one commit.** The declaring line carries the removal condition (Guardrail #6): *delete these four when `digest.yml:99-102`, `:563-566`, `llm-council.yml:80-83` and `:315-318` go; nothing else reads them.*

**Naming, after row 3.** Every key the pinned verb emits begins `summarize_`; every key the trial verb emits begins the caller's `--prefix`. **The disjointness test is scoped to `--also-pinned`**, which is the only case that writes two sets into one `$GITHUB_OUTPUT` block: `set(also_pinned) & set(trial at the empty prefix) == set()`. A global disjointness assertion is red on `main` today, because the trial verb at an empty prefix also emits `draft_*`.

**The one-companion projection** is built from the same objects `list_model_files` returns, and **refuses an entry declaring two or more** - naming the models file and the count, not truncating. That refusal is free (no committed entry declares two) and closes a defect live on `main`: the projection publishes companion 0 while the cache key digests all of them, so a two-companion dispatch today keys on two files and fetches one.

**`models_file` is published as the proved path** - `path.relative_to(<the --config-root>).as_posix()`, not the raw input and not relative to the repository root.

### C2 - The grammar (row 1)

**Declared in `model_refs.py` itself, with `re.compile` and nothing but stdlib `re`.** Not imported from `measure_llm.py`: that module runs two ways - by path at `measure.yml:376` in a job with no install, and as `utilities.measure_llm` under pytest - and no single plain import statement works in both.

**Every pattern keeps its `^` and `$`, and is applied with `re.fullmatch`** - never `re.match`, never `re.search`. `$` matches before a trailing newline, so `match` admits a value the anchors look like they refuse.

| Value | Rule | State |
| --- | --- | --- |
| `repo` | `^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$` | exists as `REPO_RE`, `measure_llm.py:28`. Gated |
| `revision` | `^[0-9a-f]{40}$` - a commit, never a branch | exists as `REVISION_RE`, `:32`. Gated |
| weights `file` | `^[A-Za-z0-9][A-Za-z0-9._-]*\.gguf$` | exists as `GGUF_RE`, `:29`. Gated. **The live gap** |
| companion `file` | `^[A-Za-z0-9][A-Za-z0-9._-]*$` - the same segment rule, **without the suffix rule** | new. `CompanionFile` has no suffix rule because a companion may be a projector, an adapter or a vocoder |
| `sha256`, weights and **every** companion | `^[0-9a-f]{64}$`, **required, no exception** | new |
| `id` | `^[a-z0-9]+(?:-[a-z0-9]+)*$` | new. **Gated against `SLUG_PATTERN` at `backend/idhazh/contracts/base.py:49`** |
| `quantisation` | `^[A-Za-z0-9_.-]+$` | new |
| `byte_count` | **empty, or** `^[1-9][0-9]*$` on the emitted string | new. No check at all today |
| `flag` | **empty, or** `^--?[A-Za-z0-9][A-Za-z0-9-]*$`. **One dash is legal**: llama.cpp's short form for a draft model is `-md`, and the live model's `server` block carries eleven single-dash flags | new |
| the set | two entries resolving to one filename is refused, and the message names both | exists, `measure_llm.py:71-75` |
| **every emitted value, last** | the string is **empty, or `^[\x21-\x7E]+$`** - printable ASCII with no space. **Empty is legal for exactly `flag` and `byte_count`** | **the backstop, and the load-bearing row** |

**The backstop is a character class, never `str.isprintable()`**, which admits `e` with a combining acute and DIVISION SLASH - either of which builds a hub URL that is not the one a reviewer read. No-space rather than admit-space: `one_bare_word` refuses whitespace today, so a backstop that admitted it would be a regression dressed as a hardening.

**Four values have no rule of their own, by decision rather than omission.** `ref` is `f"{repo}@{revision}:{file}"`, all three parts ruled, and its only consumer re-parses it with the same three patterns - **the invariant to state beside it is that `@`, `:` and `,` stay outside those classes or the re-parse mis-splits**. `weights_path` and `landed_path` are `MODELS_DIR` plus a ruled `file`. `cache_key` is hex by construction, **asserted `^[0-9a-f]{64}$` anyway**. `models_file` is **containment-proved rather than pattern-checked** by `resolve_under_config`, which is stronger than a regex because `..` is what resolving exists to defeat.

**All five committed model files clear every rule**, checked field by field on 2026-09-22.

**The duplications are gated by tests, not attention.** One contract test holds an explicit tuple `("REPO_RE", "REVISION_RE", "GGUF_RE")` and asserts, for each, that the name exists on both modules and that `.pattern` and `.flags` are equal - flags are not optional, because `re.IGNORECASE` on one side is a second grammar sharing one pattern string. A fourth assertion covers the slug against `contracts/base.py:49`. **The test can import `idhazh`; the reader cannot. That asymmetry is why the copy is legal and why the gate is mandatory.**

**Three Guardrail #11 citations are wrong and are corrected in the commit that touches each file**: `model_refs.py:1-4` (row 1), and the comments in the action and the deleted download script (row 3). The replacement names what is true: these values are pasted into `run:` bodies where the Actions engine substitutes before bash parses.

### C3 - The refusal message (row 1)

**On a malformed entry the verb raises and exits non-zero. Not a skip**: a skipped companion is a server that fails to start over a missing file, or one that starts and silently does nothing.

**Every refusal names four things in this order: the models file, where in it, the rule in plain words, and the offending value in `repr()`.** "Where in it" has three forms and no fourth: a **field** gets its dotted JSON path including every list index; a **composed value** is reported against the field it was composed from; a **whole-set rule** names the entry, the rule, and **every** participating location and value, because one location would name a file that is not wrong on its own. **Never print a regex.**

```
config/models/gemma-4-e4b-qat.json: summarize.companion_files[0].file:
  not one path segment: '../../x.gguf'
config/models/qwen3.5-9b-q4km.json: summarize.revision:
  not a 40-character commit: 'main'
config/models/x.json: summarize: two files land on one name:
  summarize.file 'x.gguf' and summarize.companion_files[1].file 'x.gguf'
```

### C4 - The landed path, composed in exactly one place (rows 1, 3)

`model_refs.py` declares `MODELS_DIR: Final = "backend/models"`, its only spelling, and composes `landed_path` and `weights_path` from it. That removes the composition from nine sites. `backend/idhazh/llm/server.py:437-439` is corrected in row 1 - it carries a **false docstring plan 41 landed**, claiming `model_refs.py` imports `companion_path`, and `model_refs.py` imports nothing from `idhazh`. **No cross-module test between them**: `companion_path` is one line with one caller, and a test asserting two values agree would not have caught the docstring already wrong on `main`.

### C5 - The cache key (rows 1, 3)

| Property | Value |
| --- | --- |
| Shape | **a fixed-width SHA-256 hex digest**, never a join. The hyphen-join reaches 519 characters at seven files, past GitHub's 512-character cap |
| What it covers | `repo`, `revision`, `file` and `sha256` per file, in declared order |
| Serialisation, to the byte | `hashlib.sha256(b"\n".join(b"\t".join(f.encode("ascii") for f in (repo, revision, file, sha256)) for each file)).hexdigest()`. TAB between fields, LF between rows, **no trailing LF**, ASCII, lowercase hex. An internal digest input, not a published format |
| Why a plain `.encode("ascii")` is safe | every one of those four values has passed its field rule and the backstop. **Nothing enters the digest the grammar has not already seen** |
| What it must **not** cover | **`flag`** - it reaches the server command line, so digesting it discards the entry when the flag is edited for zero byte change. **`landed_path`** and **`byte_count`** - derived. **The config root** - it is how the files were found, never part of what is hashed |
| Why excluding the config root is a contract | D3 only hits because one caller reads `backend/var/candidate-config` and another reads `config`. A unit test drives exactly that. **A worker who "fixes" a cross-caller miss by putting the root into the key has destroyed the property that makes the closing dispatch work** |
| The suffix | `-v4` becomes `-v5`, declared once as `WEIGHTS_CACHE_SUFFIX` at `_harness.py:357`. **It is the manual eviction handle for the three things the digest cannot see**: an entry already poisoned, a llama.cpp release re-uploaded under one tag, and a runtime-install change altering `backend/bin`, which is in `path:` and in no key component |
| Paths | unchanged: `backend/models` and `backend/bin`, on one key. **No `restore-keys`** |

**Both `llm-` spellings move in one commit** - `action.yml:93` and `idhazh-pipeline-tests.yaml:167`.

**The guard is scoped to the `llm-` format, not to every cache step over `backend/models`.** There are **three** formats in six steps - `llm-`, `qualify-` at `validate.yml:284`, and `bench-` at `measure.yml:289`, `:570`, `:899` - and they are deliberately different, because production must not share an entry with a bench candidate. **Discovery walks all six; the resolved-value equality clause covers only the steps whose key starts `llm-`**, which is the one format written twice. The plan says why the other two differ so nobody widens it.

### C6 - The llama.cpp pin becomes data (row 3)

`.github/scripts/llama-cpp-pin.sh` is deleted. Its three constants move to **`config/llama-cpp-pin.json`**.

| Property | Value |
| --- | --- |
| Shape | `{"build": "...", "asset": "...", "sha256": "..."}` |
| Grammar | `build` and `asset` `^[A-Za-z0-9][A-Za-z0-9._-]*$`; `sha256` `^[0-9a-f]{64}$`. **A second `KEY=value` printer over a second JSON file with no grammar would recreate, one file left, the defect row 1 exists to close.** A unit test asserts `print-pinned-build`'s output matches `^llama_cpp_build=[A-Za-z0-9][A-Za-z0-9._-]*\n$` exactly |
| Why `config/` | it is a tunable that changes on an upgrade (Guardrail #6). **No schema is owed**: the owner ruling of 2026-09-21 exempts a configuration file this project authors |
| Why not a module constant | five workflow steps read the build to name a cache key, and a cache step runs **before** anything is installed |
| What reads it | `model_runtime.py`, **and `_harness.py` at `:202` and `:1617`**, which parse the pin out of the shell file today and must read the JSON. Both are in row 3's `_harness.py` list |
| `measure.yml:125-127` | **stays.** A workflow-level `env:` block cannot read a file, and its consumers are the four inline arms this plan scopes out. **Row 3 adds a test that the three literals equal the JSON's three**, so the second copy cannot drift |
| The comment it carries | the pin file's own header, kept, including that the release API's `digest` was confirmed on 2026-08-25 by downloading the 16,377,727-byte archive and hashing it |

**The sourcing problem disappears here.** Two scripts were sourced so their variables would land in a caller's shell. One Python program has no caller to export into.

### C7 - `backend/utilities/model_runtime.py`, the one program (row 3)

**One new module replaces four scripts and 202 lines of shell.** Its question: *what does this runner need in order to serve the model the config names, and is it here and correct?*

| Verb | Replaces |
| --- | --- |
| `print-pinned-build` | running `llama-cpp-pin.sh` |
| `install-runtime` | `install-llama-runtime.sh` |
| `download-model-files` | `fetch-model-runtime.sh`'s download half |
| `verify-model-files` | the restore-time check, callable where nothing was downloaded |
| `start-server` | `start-llama-server.sh` **and `llama_argv.py`** |

**`install-runtime`**

```
 1. pin = json.loads(Path("config/llama-cpp-pin.json").read_text())
 2. GET https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/<build>
    through its OWN urllib Request carrying Authorization: Bearer <GITHUB_TOKEN>,
    timeout=30.  THIS IS THE ONLY PLACE IN THE MODULE THAT SETS A HEADER.
    Authenticated because every shard asks at once and anonymous
    api.github.com allows 60 requests an hour.
 3. asset = the entry whose name == <asset>.  Absent -> raise, naming the
    build, the asset and the names that were there.
 4. archive = _download(asset.browser_download_url, tmp/"llama.tar.gz")
 5. hashlib.sha256(archive) == <sha256>, or raise naming both digests.
 6. with tarfile.open(archive) as tar:
        tar.extractall(path=tmp/"llama", filter="tar")
    filter= is NAMED, not defaulted: CI pins python 3.12 where the default is
    fully_trusted plus a DeprecationWarning, and 3.14 - which the dev box runs -
    defaults to `data`.  Same call, two behaviours, and the dev box is the one
    that differs.  "tar" is the faithful equivalent of `tar -xzf`.
 7. src = the directory containing "llama-server", found by walking including
    symlinks - NOT os.walk's file list alone.  The shared objects ship as
    symlinks, which is why the shell used `cp -a` over `find -type f`.
 8. shutil.rmtree("backend/bin", ignore_errors=True)
    shutil.copytree(src, "backend/bin", symlinks=True, dirs_exist_ok=True)
    The rmtree is load-bearing: dirs_exist_ok permits existing DIRECTORIES, and
    an existing destination symlink makes os.symlink raise FileExistsError.
    `cp -a` overwrote.  Latent on a cache miss, live on any retry.
 9. os.chmod("backend/bin/llama-server", 0o755)
10. Assert llama-server is a regular file and every symlink under backend/bin
    resolves.  A broken .so link is a 127 at exec naming a library rather
    than the mistake.
```

**`download-model-files`**

```
1. files = model_refs.list_model_files(config_root)   # every C2 refusal here
2. Refuse an empty list by name, naming config_root.
3. For each file, in declared order:
     a. landed exists?  size and digest correct -> log "kept", skip.
        Otherwise -> raise naming the path.  NEVER overwrite.
     b. _download(url, landed + ".part")
     c. sha256 == declared, and size == declared where the entry gives one.
        Mismatch -> unlink the .part, raise naming both.
     d. os.replace(landed + ".part", landed)
4. Assert downloaded + kept == len(files), naming all three counts.
5. Log one line per file: url, bytes, seconds, MB/s.   <- the instrument
```

**`verify-model-files`** re-reads the declaration and, for every declared file, checks the digest and the declared size where there is one. **It runs on a cache hit, where nothing was downloaded** (C11).

**`start-server`**

```
1. Log resource.getrlimit(resource.RLIMIT_MEMLOCK) before.
2. subprocess.run(["sudo","-n","prlimit","--memlock=unlimited",
                   "--pid", str(os.getpid())], check=False)
   os.getpid() is correct: the shell raises the limit on $$ and the server
   inherits at fork; here the server is a child of THIS process, so the same
   inheritance applies.  NOT preexec_fn + resource.setrlimit, which can only
   raise to the hard limit - which is why the shell needs sudo at all.
   `-n` so a password prompt is an instant non-zero the warn path absorbs,
   rather than a hang to the job timeout.  A failure WARNS and continues.
3. Log the limit after.  That pair is the proof the call landed.
4. os.chmod("backend/bin/llama-server", 0o755)
5. from idhazh.llm.server import server_argv       # INSIDE this function only
   argv = server_argv(...)      # llama_argv.py and its NUL-joined file go
6. proc = subprocess.Popen(argv, stdin=subprocess.DEVNULL,
                           stdout=log, stderr=subprocess.STDOUT,
                           env={**os.environ, "LD_LIBRARY_PATH": "backend/bin"},
                           start_new_session=True, close_fds=True)
   env={**os.environ, ...} is load-bearing: the shell form was a PREFIX
   assignment, so everything else survived.  A bare dict removes PATH and HOME.
   stdin=DEVNULL is load-bearing: a detached child holding the step's stdio
   pipe is the classic way an Actions step hangs at completion.
7. Path(f"{name}.pid").write_text(str(proc.pid))
8. time.sleep(2); if proc.poll() is not None: print the last 50 log lines,
   exit 1.  This is refuse_a_server_that_died_at_startup, imported from
   idhazh.llm.server where row 3 moves it beside server_argv.
9. Return without waiting.
```

**The argument contract, and it is smaller than the script's.**

| Argument | Ruling |
| --- | --- |
| `--config-root` | keep, default `config`. Four of five sites pass a non-default |
| `--name` | keep, default `llama-server`. No site passes it; it stays because it is the handle the sampler, the health checks and the failure tail all use |
| `--role` | **deleted.** One role exists, `llama_argv.py:42` already defaults to it, and the script's `case` block refuses a value nothing can produce |
| `--weights` / `LLAMA_WEIGHTS` | **deleted, derived** from the config root's own `models.summarize.file` plus the one `MODELS_DIR` spelling. That removes five more `${{ }}` hops |
| the port | **`LLAMA_PORT` from the environment at all five sites, no `--port` argument.** `llama_argv.py:44-46` already carries the reason: a `--port` argument is a second spelling of a llama-server flag |

**The derivation in row 4 above carries one risk a reading cannot settle**: two pipeline-test case roots are built by a step this plan did not open, so their `models.summarize.file` might not equal what the site pastes today. **Row 3's tests-only commit lands a clause asserting, for each of the five roots, that the derived path equals the pasted one.** It is green the day it is written. Any root where it is red keeps an explicit `--weights`, and the plan names that root.

**On survival across the step.** `start_new_session=True` calls `setsid()`, which is strictly more detached than `nohup` - no controlling terminal, so SIGHUP is never delivered. The property one level down is proved five times a day: `start-llama-server.sh:65` backgrounds a grandchild of the step's bash and llama-server serves through six later steps. What `setsid()` does **not** give is stdio redirection, which is why clause 6 sets all three streams.

**`sudo -n prlimit` runs in all five sites and is called in one today.** Every job is `ubuntu-latest`, where sudo is passwordless. `config/models/qwen3.5-9b-q4km.json:36` carries `"-lm": "mmap+mlock"` and the candidate-config action copies the server block onto every candidate - so four jobs have been starting an mlock-requesting server at the default locked-memory limit. Putting it in the shared verb fixes them for free and cannot make anything worse.

### C8 - The downloader (row 3)

**One function, `_download(url, destination)`, used by `install-runtime` and `download-model-files`.** It is the only thing in the module that touches the network for bytes, so a later change of transport is a one-function change rather than a revert of the row.

| # | Clause | Why |
| --- | --- | --- |
| 1 | **No request headers. Not `Authorization`, not anything.** A test asserts `Authorization` appears in exactly one function in the module | CPython's redirect handler copies every header onto a cross-host redirect target with no host check, unlike `requests`/`httpx` which strip it. The hub and the release CDN are redirects, and a presigned URL that already carries a signature can reject a stray bearer token. Today this is safe by accident - two separate `curl` calls, only the first authed |
| 2 | `urlopen(url, timeout=READ_TIMEOUT)` with `READ_TIMEOUT = 60`. **That is a socket timeout: it bounds one blocking read, not the transfer** | stated so nobody mistakes it for a total bound |
| 3 | An explicit read loop at **1 MiB**, not `shutil.copyfileobj` | `copyfileobj` is correct on memory but gives no progress line, no deadline hook and no throughput floor |
| 4 | **Two bounds a socket timeout cannot give**: a wall-clock deadline for the whole file, and a minimum-throughput floor checked every 30 s after the first 60 s | a connection trickling one byte per 30 s never trips a read timeout and holds a shard to its 200-minute bound |
| 5 | Retry up to 3 attempts, **from byte zero**, on `URLError`, `ConnectionResetError`, `http.client.IncompleteRead`, `socket.timeout`, and `HTTPError` with 5xx, 408 or 429. **Never on a 4xx.** Close the `HTTPError` body before retrying; it is a file object | `urlopen` already raises on any non-2xx, which is `curl -f` for free. From byte zero is **parity with today, not a loss**: `fetch-model-runtime.sh:41` has no `--continue-at`, so curl already restarts from zero on a mid-transfer reset |
| 6 | Always write to `destination + ".part"`; the caller renames | `curl -o` wrote straight to the destination, so a killed job left a half file under the cache key |

**Memory is not a concern and the plan says so rather than leaving it open.** The read loop is 1 MiB; peak RSS of the download process is the interpreter plus that buffer. The model is not resident - `download-model-files` runs in an earlier step and its process is gone before `start-server` runs. Page cache holding a just-written 5.68 GB file is reclaimable and is not RSS.

**The three reasons an earlier draft gave for `urllib` were all wrong and are deleted**: `fetch.py` streams nothing to disk, `measure_llm.py:174` is a `curl` subprocess and is evidence the other way, and there is no resume to lose. **The reason that stands is the owner's ruling of 2026-09-22**, and the honest statement of the risk is in section 9.

### C9 - The composite action after row 3 (row 3)

**Ten inputs become four: `github_token`, `port`, `llama_cpp_build`, `config_root`** (`required: false`, `default: 'config'`). `llama_cpp_build` stays an input because `digest.yml:640` and `validate.yml:390` feed it to `fingerprint.py:104` as `runtime_build`, and two cache keys name it.

**It gains an `outputs:` block, which it has none of today** - without one, `digest.yml`'s reads resolve to empty and a `sha256sum` runs on a directory. Declare all three the callers need:

```yaml
outputs:
  weights_path:
    description: 'The landed relative path of the weights, as the reader composed it.'
    value: ${{ steps.model.outputs.summarize_weights_path }}
  model_id:
    description: 'The alias the served model answers under.'
    value: ${{ steps.model.outputs.summarize_id }}
  weights_file:
    description: 'The bare weights filename, for a loaded-path assertion.'
    value: ${{ steps.model.outputs.summarize_file }}
```

| # | Step | After |
| --- | --- | --- |
| 1 | **new, `id: model`** | `python3 backend/utilities/model_refs.py describe-pinned-model --config-root "$CONFIG_ROOT"`, **captured into a variable, asserted to carry a 64-hex `summarize_cache_key`, then appended** to `$GITHUB_OUTPUT`. Capture then append, never append straight: a reader that dies mid-stream would leave half its keys behind. ESCALATE trigger 4 is enforced here |
| 2 | Cache, `id: weights` | `key: llm-${{ steps.model.outputs.summarize_cache_key }}-${{ inputs.llama_cpp_build }}-v5`. Paths unchanged, no `restore-keys` |
| 3 | Install and download | `if: steps.weights.outputs.cache-hit != 'true'`. Two calls: `install-runtime`, then `download-model-files --config-root "$CONFIG_ROOT"` |
| 4 | Verify | **no `if:`**. `env: CONFIG_ROOT` - **it is a separate step and inherits nothing.** One call: `verify-model-files --config-root "$CONFIG_ROOT"` |
| 5 | Start | `start-server --config-root "$CONFIG_ROOT"`, with `LLAMA_PORT: ${{ inputs.port }}` in `env:` |
| 6 | Health | `env: MODEL_ALIAS: ${{ steps.model.outputs.summarize_id }}` and `WEIGHTS_FILE: ${{ steps.model.outputs.summarize_file }}`, **read as shell variables**. The step already does this through `inputs`; changing the source must not change the discipline, and C13's paste rule fails on the pasted form |

**The key is computed inside the action, never passed in.** A caller-computed key is hop 3 of the four this plan deletes. Computed, it costs zero lines in both callers and it is provably the set the download reads.

**`jq` leaves the model path but stays in the health check.** Converting that is not this row's business.

### C10 - The four small ports (rows 2, 4, 5)

| Script | Becomes | The one thing a worker must not get wrong |
| --- | --- | --- |
| `browser-suite-needed.sh` (4) | **nothing.** It is `exec node frontend/scripts/test-scope.ts --ci`; `ci.yml:77` calls node directly and the file is deleted | **`frontend/scripts/test-scope.ts:172` names this script inside the regex** deciding which tests a change needs. The name goes and nothing replaces it: that regex already lists `.github/workflows/ci.yml`, which is the file now carrying the call, **verified** - so the selection is unchanged |
| `changed-docs.sh` (32) | `backend/utilities/changed_docs.py`, called at `ci.yml:118` | **It never fails a run.** Three cases keep that: an empty or absent `BASE`, the all-zero SHA, and a `BASE` this clone cannot resolve. It measures and gates nothing |
| `run-pipeline-test-case.sh` (54) | `backend/utilities/pipeline_test_case.py`, called three times | **The exit-code mapping is a contract, not a detail.** Exit 2 means a missing case directory or a missing plan; any other non-zero means the pipeline itself failed. The workflow distinguishes them |
| `sample-rss.sh` (108) | `backend/utilities/memory_sampler.py`, and **this is a merge**: `runtime_sweep.py:294` already has `read_status`, and `:529` already starts a thread called `sample_rss` | It writes **two** files, not one - `rss-samples.tsv` and `python-procs.tsv` - and **`digest.yml:888-917` runs an `awk` program over the first**, naming its columns. **Both become JSON Lines and the `awk` becomes a `memory_sampler.py summarize` verb in the same commit**, or the memory summary degrades to "not found" without failing |

**The sampler's launch shape is the same as `start-server`'s**, one shape with two callers: the parent `Popen`s with `start_new_session=True` and all three streams set, writes **the child's** pid, confirms it is alive, and exits 0 in the foreground. **Not backgrounded with `&`.** Today `digest.yml:627-629` records `$!`, which is the pid of the backgrounded *shell*, not of the sampling loop - so a sampler that dies at once leaves a pid file naming a dead shell and a green step. Recording the child's pid is a bug fix riding free.

**`test_model_server_jobs.py:382` asserts the literal `"nohup" in script`** and turns red. It splits, and neither half is a literal:

| Where | Assertion |
| --- | --- |
| the workflow test | the step calls `memory_sampler.py` with the pid the job's own start step wrote, the body does **not** end in `&`, and the pid file it names is the same one later steps read. That agreement between steps is what the old test was protecting - its own docstring says so |
| a new integration test, `skipif(os.name == "nt")` | spawn a short-lived target; launch the sampler from a parent python that then exits; assert the parent exits 0, the pid in the file is alive, **`os.getsid(pid) != os.getsid(0)`**, it wrote at least two records, and it stopped after the target died |

`os.getsid` is the one line that proves detachment rather than describing it.

### C11 - What stops a bad cache entry being written (row 3)

| Half | Where | Runs on a hit? |
| --- | --- | --- |
| **restore-time - the control** | `verify-model-files`, in a step with **no `if:`**, after the download and before the first read of `backend/models` | **yes.** The only one that does |
| download-time - an early exit | inside `download-model-files`, per file | no |

**`actions/cache@v6` does not save when the job failed** - `post-if: "success()"`, and `save-always` is inert and deprecated. **The door `post-if` cannot see** is a download that exits 0 having fetched fewer files than the model declares; `download-model-files` step 4 names it, and the no-`if:` verify catches it either way.

**The standing rule:** no step between the cache restore and the verify may carry `continue-on-error: true`, and the cache step is never split into `actions/cache/restore` plus a save with `if: always()`. Either makes `post-if: success()` untrue.

### C12 - The commit order, and the discovery that must widen with it (row 3)

**The first commit is tests only, and it lands RED.**

| Clause | State when written |
| --- | --- |
| **discovery widens** - `_harness.py:1637` matches `"huggingface.co/" in script` **or** `"model_runtime.py download-model-files" in script`, **and the test asserts the discovered count is 8** | green, and it is the most important clause in the plan. **Without it, row 3 moves the hub URL into Python, discovery falls to 4, and `test_weights_and_model_refs.py:71`'s equality passes against a four-entry table** - the weights oracle for `digest.yml/work` silently leaves the closed world with nothing going red |
| a second clause: **no file under `.github/` that reaches the shared download may spell the hub host.** `.github/workflows/measure.yml` is the one named exception, and the reason rides on the line that names it: *measure.yml's four inline download steps are plan 46's to convert; delete this exception when they go* | red until row 3's second commit |
| **the paste rule** (C13) | **red: 8 sites** |
| **every declared file reaches a digest check in a step with no `if:`** | red |
| **the verify step's config root equals the download step's** | red |
| **the companion-sensitivity oracle** - two fixture entries differing only in one companion digest render different keys | red |
| **the derived-weights-path clause** - for each of the five launch roots, the derived path equals the pasted one | green (C7) |
| **the pin-equality clause** - `measure.yml:125-127`'s three literals equal the JSON's three | green |
| **`SHIPPED_SCRIPTS` loses its four names in the same commit that deletes the four files** | green, and it needs no entry here - see C14 |
| the `llm-` resolved-value equality guard | **green, and it stays green.** A guard against one spelling moving alone |
| the three clauses already green at `test_weights_and_model_refs.py:59-88` | green, not rewritten |

**Why the order is the control.** The most likely failure is a worker seeing a digest check inside `download-model-files` and a second in the verify step, reading the second as redundant, deleting it, and going green everywhere. **One review rule rides with it: row 3's diff must not remove `assert "if" not in check` at `test_weights_and_model_refs.py:84`.**

**`WEIGHTS_CHECKS` shrinks from eight entries to four and `:71` stays an equality.** Discovery still finds eight **because the clause above widens it**. The written table keeps `measure.yml`'s four; the four converted jobs are derived at assertion time, with the anchor `model_runtime.py verify-model-files`. **Do not weaken `:71` to a subset.**

### C13 - The paste rule, stated in terms a test can evaluate (row 3)

**In every job of the closed world, no `run:` body carries an expression that resolves to a value the model file's reader published.**

| Clause | Rule |
| --- | --- |
| the closed world | computed: every `(workflow, job)` that calls `./.github/actions/model-server` or runs `model_runtime.py download-model-files` |
| what it walks | `_harness._steps(workflow, job)` - which resolves a repository-local composite action's steps in place - and each step's `run:` string. **`env:`, `with:`, `key:` and `if:` are out of scope**: `env:` is where these values are allowed to be |
| what it matches | every `${{ ... }}` by `re.findall(r"\$\{\{(.*?)\}\}", body, re.S)`. Take the dotted segments; skip unless the **first** is `steps`, `needs` or `inputs`. Let `S` be the **last** segment |
| the predicate | fails if `S in PUBLISHED_KEYS` or `S.endswith("_" + key)` for any key |
| `PUBLISHED_KEYS` | **read from the reader, never retyped**: the union of its field tuples and a new `PUBLISHED_EXTRA` naming exactly `("models_file", "ref", "byte_count", "cache_key", "weights_path")`. **Row 1 adds it and the emit path iterates it** |
| what it guards after the relays go | **the action's own `id: model` step is a producer inside the closed world, and steps 5 and 6 are its consumers.** The rule does not go green-and-empty; its first catch is C9 step 6 |
| what it cannot settle | `measure.yml`'s five paste sites, which reach neither the action nor the shared download |

### C14 - The constant that keeps the shell from coming back (row 2)

**Corrected 2026-09-22, during row 2, on Fowler's ruling.** The shape below is what shipped; the first draft of this section is described after it, with why it could not be written.

**`SHIPPED_SCRIPTS` is a constant in `_harness.py` naming the scripts the directory is expected to hold - the survivors, not the leavers.** The test asserts `present == listed` in **both** directions, so a `.sh` file nobody declared fails, and a name left behind after its file is deleted fails too. **The list only ever shrinks: a row that deletes a script deletes its name in the same commit that deletes the file.** The failure message names the surplus by name: `a new .sh file under .github/scripts/ is a Level 3 design question, not a convenience. Nothing declares: <name>`.

| After | Names in the constant | What that row deletes from it |
| --- | --- | --- |
| row 2 | **9** | `browser-suite-needed.sh`, `changed-docs.sh` |
| row 3 | 5 | `llama-cpp-pin.sh`, `install-llama-runtime.sh`, `fetch-model-runtime.sh`, `start-llama-server.sh` |
| row 4 | 4 | `run-pipeline-test-case.sh` |
| row 5 | 3 | `sample-rss.sh` |
| row 6 | **0**, and the test asserts **`.github/scripts/` does not exist** | `commit-and-push.sh`, `take-state-from-the-tip.sh`, `push-rewritten-history.sh` |

**Why the first draft could not be written.** It had the constant name the scripts *no row claims*, written once in row 2 and never rewritten, with each later row driving a **surplus** count down 9 -> 6 -> 2 -> 1 -> 0. Two things are wrong with it. The counting direction is unwritable as a test: a constant that never changes cannot tell a deleted script from a script that was never there, so "surplus falls to two" is a number a human tracks rather than an assertion a test evaluates - and a test that only fires at zero is a test that is red for four rows and catches nothing in between. And the leading 9 was already 8 when row 2 measured it: `push-rewritten-history.sh` landed in another plan's pull request after this plan was drafted. **A count of a growing directory is a rotting number** (Guardrail #10); naming the survivors is the property, and it does not rot.

**What this costs rows 3, 4, 5 and 6:** one extra edit each, in a file they already touch, in the commit that deletes the file. **What it buys:** the constant is red the moment a file and its name disagree, in either direction, on every row - not only on the last one.

**Row 6 is what makes the terminal state reachable**, because it takes all three remaining scripts and retires the four assertions that require the directory to be non-empty - `test_ci_selection.py:52`, `test_pinned_versions.py:100`, `test_script_invocation.py:99` and `_harness.py:164`'s `SHELLCHECK_COMMAND` glob.

**The escalation on the declaring line:** *a new `.sh` file here is a Level 3 design question, not a convenience.* One appeared mid-plan, in another plan's pull request, with no owner - which is the reason this constant lands in wave 1 rather than at the end.

## Section 2 - Row 1 - The model file gets one reader, and the grammar closes

- **Scope:** Give `model_refs.py` a closed field grammar, `list_model_files`, the file-set digest, three new published keys and one spelling of the models directory - deleting no published key and no argument but `--repo-root`, and **touching no workflow**.
- **Files touched:** `backend/utilities/model_refs.py`; `backend/tests/workflows/test_weights_and_model_refs.py`; `backend/tests/workflows/test_pipeline_tests_workflow.py` (`:683-694`); `backend/idhazh/llm/server.py` (`:437-439` docstring only).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q` and `python -m pytest backend/tests/test_measure_llm.py -q`; CI - full suite. No dispatch.
- **Oracle:** **stated against the verb production runs today.** Run the existing trial verb against a fixture models file whose `summarize.file` is `../../etc/passwd.gguf`, and a second whose `summarize.file` is `x$(id).gguf`; assert a non-zero exit naming the field. **Today both exit 0 and print the value into `$GITHUB_OUTPUT`.** Second failing case: a fixture declaring seven companions must render a key of at most 64 characters - **today the hyphen-join renders 519, past GitHub's 512-character cap.** **What it cannot settle:** whether a program ever sees an unvalidated value. Row 3's paste rule settles it.
- **The tests this row rewrites, and the ones it must not:**

 | Test | Today | After |
 | --- | --- | --- |
 | `test_an_entry_with_no_draft_head_keeps_the_key_it_already_had` at `:494` | asserts the key **equals the entry's own `sha256`** | **rename it `test_the_key_moves_when_the_declared_set_moves`.** Two fixture entries identical except that one declares a companion render **different** keys, and the no-companion entry's key is **not** equal to any single field. **A clause that calls the reader twice with the same input and compares the results asserts nothing and does not satisfy this row** |
 | a new unit test | - | two config roots holding the same entry render **one** key |
 | a new unit test | - | the `--also-pinned` key set and the trial set at the empty prefix are disjoint. **Scoped to `--also-pinned`**: a global assertion is red on `main`, because the trial verb at an empty prefix also emits `draft_*` |
 | `CANDIDATE_STEPS` at `:407-410` and the `draft_*` assertion at `:485` | asserts the trial verb publishes the four `draft_*` keys at both prefixes | **unchanged.** Row 1 deletes no key |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Row 1 is additive on published keys and touches no workflow.** The configured verb publishes **ten** keys today - `model_refs.py:130` calls `_draft_rows(..., prefix="")` - and four of them are consumed by `digest.yml` and `llm-council.yml`. Deleting them in wave 1 would leave two production workflows handing the action four empty draft inputs until wave 2, skipping the draft download and its digest check | Andre |
 | 2 | **The verb rename moves to row 3.** It edits five workflow call sites; in row 1 that would put five workflows into PR-A and collapse wave 1 to one worker. Row 3 is already rewriting those lines | Fowler |
 | 3 | The one-companion projection is built from the same objects `list_model_files` returns, and **refuses an entry declaring two or more**. Today it truncates in silence while the key digests all of them | Carmack |
 | 4 | **`list_model_files` returns objects, not text.** An earlier draft printed seven tab-separated columns so a shell could read them; row 3 deletes the shell | Owner ruling, 2026-09-22 |
 | 5 | The grammar is **declared in `model_refs.py`** with stdlib `re`, gated by equality tests against `measure_llm.py` and `contracts/base.py:49` | Carmack |
 | 6 | Every pattern keeps `^`/`$` and is applied with `re.fullmatch` | Andre |
 | 7 | The backstop is `empty, or ^[\x21-\x7E]+$`, and **empty is legal for exactly `flag` and `byte_count`**. A backstop refusing empty would take the daily run down on the first merge | Andre |
 | 8 | The backstop is a character class, never `str.isprintable()` | Andre |
 | 9 | `flag` allows **one or two** leading dashes | Andre |
 | 10 | The weights `file` gets the `.gguf` suffix rule; a companion `file` gets the segment rule without it | Andre |
 | 11 | The digest covers `repo`, `revision`, `file` and `sha256` only, with C5's serialisation. **Not the config root** | Carmack and Andre |
 | 12 | All four verbs take `--config-root`, default `config`; `--repo-root` is deleted. No caller passes it | Fowler |
 | 13 | `MODELS_DIR` is declared once, and `server.py:437-439`'s false docstring is corrected in the same commit | Fowler |
 | 14 | `PUBLISHED_EXTRA` is a real module constant the emit path iterates, not a list in a test file | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete the `draft_*` keys here | Two production workflows consume them and row 3 is a wave away. Silent: a guard goes false and a verify becomes a no-op | A nightly and a five-times-daily run serving an unverified draft head | Andre |
 | 2 | Rename the verbs here | Five workflow call sites enter PR-A, which then shares files with PR-B and PR-E, and wave 1 stops being two wide | The only genuine parallelism in the plan | Fowler |
 | 3 | Print the file set as TSV, or as CSV | Both invent a format so a shell can read it, and row 3 deletes the shell | A format nobody reads, in the plan named after deleting them | Owner |
 | 4 | Import the patterns from `measure_llm.py` | That module runs two ways and no single plain import works in both | A `ModuleNotFoundError` class every local gate hides | Carmack |
 | 5 | Keep the hyphen-join and add companions | It crosses GitHub's 512-character key cap at about seven files | Nothing saved over a digest | Fowler |
 | 6 | Assert the pinned and trial key sets disjoint globally | Red on `main`: both emit `draft_*` at the empty prefix | A test that cannot go green until row 3 | Andre |

## Section 3 - Row 2 - The two CI-selection scripts go

- **Scope:** Delete `browser-suite-needed.sh` by having `ci.yml` call node directly, port `changed-docs.sh` to Python, and land the `SHIPPED_SCRIPTS` constant that refuses a twelfth script.
- **Files touched:** `.github/scripts/browser-suite-needed.sh` (delete); `.github/scripts/changed-docs.sh` (delete); `.github/workflows/ci.yml` (`:77`, `:118`); `frontend/scripts/test-scope.ts` (`:172`); `backend/utilities/changed_docs.py` (new); `backend/tests/workflows/test_ci_selection.py` (`:52`, `:113`); `backend/tests/workflows/_harness.py` (**the `SHIPPED_SCRIPTS` constant only**).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_ci_selection.py -q`, and `npm --prefix frontend run test:changed -- --list` then the selected node checks; CI - full suite.
- **Oracle:** the `SHIPPED_SCRIPTS` constant falls from **8 names to 6** and its test reads both directions. (Drafted as 9; 8 was the count when row 2 measured it, because `push-rewritten-history.sh` landed after this plan was written - C14.) Plus: `changed_docs.py` answers `any=false` for each of the three unresolvable-range cases, and the node selection for a change to `.github/workflows/ci.yml` is byte-identical before and after the regex edit. **What it cannot settle:** whether the CI job reading these outputs behaves the same, which the first pull request after merge shows - both outputs are exercised by every one.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | `browser-suite-needed.sh` becomes **nothing**, not Python. It is `exec node <a TypeScript file>`; rewriting it in Python would make it Python calling node | Fowler |
 | 2 | `test-scope.ts:172` loses the script name and gains nothing: **verified** that the regex already lists `.github/workflows/ci.yml`, which is the file now carrying the call, so the selection is unchanged | Carmack |
 | 3 | `changed_docs.py` **never fails a run**, preserving the three cases the script's header names. It measures and gates nothing | Fowler |
 | 4 | The `SHIPPED_SCRIPTS` constant lands **here**, in wave 1, not at the end. A twelfth script appeared mid-plan in another plan's pull request with no owner, and the constant is the only thing that would have caught it | Fowler |
 | 5 | This row runs beside row 1. Their file lists are disjoint, which is the only reason the pool is two wide in wave 1 | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Port `browser-suite-needed.sh` to Python | Python calling node to do what the workflow can call directly | One more process and one more file, no behaviour change | Fowler |
 | 2 | Fold both into one Python module | They answer two unrelated questions and live in two different jobs | One file with two answers (CLAUDE.md section 1a) | Fowler |
 | 3 | Land `SHIPPED_SCRIPTS` in the last row | It would have caught nothing, including the script that appeared while this plan was being written | The whole point of the constant | Fowler |

## Section 4 - Row 3 - The model path becomes one Python program, and the verbs are renamed

- **Scope:** Delete the four model-path scripts and `llama_argv.py`; move the pin to `config/`; put the runtime install, the download, the verify and the server launch in `backend/utilities/model_runtime.py`; rename the reader's verbs at all five call sites; cut the composite action to four inputs; delete the relay blocks and five inline Python programs; and move both `llm-` cache keys onto the digest - in one commit.
- **Commit sequence:**

 | # | Commit | Contents | State |
 | --- | --- | --- | --- |
 | 1 | tests only | **the widened fetch discovery and its count assertion (C12, ESCALATE trigger 8)**; the paste rule; the digest clauses; the verify-root clause; the companion-sensitivity oracle; the derived-weights-path clause; the pin-equality clause; the `llm-` equality guard | **RED** on six clauses, green on four |
 | 2 | the change | everything below | **GREEN** |

- **Files touched:**

 | File | What happens |
 | --- | --- |
 | **deleted** | `.github/scripts/llama-cpp-pin.sh` (34), `install-llama-runtime.sh` (43), `fetch-model-runtime.sh` (53), `start-llama-server.sh` (72), `backend/utilities/llama_argv.py` (59) |
 | **new** | `config/llama-cpp-pin.json` (C6), `backend/utilities/model_runtime.py` (C7, C8) |
 | `.github/actions/model-server/action.yml` | ten inputs to four; new `id: model` step; key `:93`; install and download `:104-115`; verify `:128-144`; start `:153-159`; health `:183` and `:191`; the new `outputs:` block. C9 |
 | `.github/workflows/digest.yml` | `:95-101` delete 7 job outputs, **`:103` keep**; `:172-179` delete the `models` step; `:195` the pin call; **`:546` add `id: model_server`**; `:550-557` delete, **`:553` KEEP - it is `llama_cpp_build`**; `:583`, `:604`, `:605-607` read the action's outputs through `env:`; `:640` unchanged |
 | `.github/workflows/llm-council.yml` | `:77-84` delete 7 job outputs, **`:84` keep**; `:168-171` delete the `models` step; `:179` the pin call; `:311-318` delete, **`:314` KEEP** |
 | `.github/workflows/validate.yml` | `:99-111` (keep `:99`, `:103`, `:111`); `:138` the pin call; `:160` the verb; `:284` the key expression unchanged; `:294-308` the download; **`:314-333` the verify as ONE unit** - `:320` defines `WEIGHTS` and `:321`/`:325` read it, so deleting `:320` alone leaves an unbound variable under `set -u`; `:335-352` **the `Start the candidate` block, which carries a `llama_argv.py` call and a `mapfile -d ''` read**; `:367-368`; `:382-399` |
 | `.github/workflows/idhazh-pipeline-tests.yaml` | `:123` the verb; `:151` the pin call; `:167` the cache key; `:172-182` the download; **`:190-204` the verify as one unit**; **`:245-258` and `:327-341`, the two `Start the model` blocks, each carrying a `llama_argv.py` call and a `mapfile -d ''` read** - the second keeps its kill loop and its log `mv`; `:270-274` and `:350-354` inline Python become `candidate_id` |
 | `.github/workflows/measure.yml` | **three places**: `:205` the verb, `:207` the `--also-pinned` flag, and **`:964-977`, the `Start the tokenizer` block - the fourth `llama_argv.py` caller**. **`:125-127` is NOT edited**; it is a workflow-level `env:` block that cannot read a file, and row 3 adds a test that its three literals equal the JSON's three |
 | `backend/tests/workflows/_harness.py` | **18 sites**: `LLAMA_RUNTIME_SCRIPT:180`, `LLAMA_INSTALL_SCRIPT:183`, `LLAMA_SHARED_SCRIPTS:185` go; `LLAMA_PIN_SCRIPT:187` becomes the JSON path; `LLAMA_PIN_NAMES:192` becomes three JSON keys; `_pinned_llama():202-209` reads JSON; `LLAMA_RUNTIME_WORKFLOWS:222`; `LLAMA_PIN_VALUES:237`; `LLAMA_PINNED_ENDPOINT:240-241`; `WEIGHTS_CHECKS:257` eight to four; `DRAFT_REF_OUTPUTS:329-334` goes; `WEIGHTS_CACHE_SUFFIX:357` to `"v5"`; `SERVER_STARTER_MODULES:503-506` loses `llama_argv.py`; `ARGV_MODULE_CALL:511`; the `_server_starters` guard at `:2327`; `START_SERVER_SCRIPT:2274`, `:2288`, `:2290`; **`_weights_fetch_steps():1637` - the discovery widening**; `_pin_print_shape():1617-1619` |
 | `backend/tests/workflows/test_weights_and_model_refs.py` | `:59-88` three clauses stay, the digest anchor changes; `:202-230` rewritten to read the action's `model` step; `:344-380` the widened closed world and the `llm-`-scoped guard; the new clauses. **`assert "if" not in check` at `:84` must survive the diff** |
 | `backend/tests/workflows/test_pinned_versions.py` | **changes shape, not a constant.** `:68-72`, `:90`, `:99-100`, `:101-106` widen from scripts to every workflow, action and script; `:108-109`'s script closure re-roots on the pin call; `:121-126`'s `WEIGHTS_FETCH_FORM` stops being a `curl` literal; **`:128-147` gains an explicit non-vacuity assertion naming its own count, because after this row its derived set is otherwise empty and the test passes by checking nothing** |
 | `backend/tests/workflows/test_model_server_jobs.py`, `test_script_invocation.py`, `test_pipeline_tests_workflow.py` | `:116`, `:435`, `:516`; the sourcing-chain docstring at `:50`; `RUNTIME_SCRIPT:110` and `PIN_SCRIPT:112` |
 | `backend/idhazh/llm/server.py` | gains `refuse_a_server_that_died_at_startup`, `START_GRACE_SECONDS` and `LOG_TAIL_LINES`, moved from `runtime_sweep.py`; both callers import them here |
 | `docs/reference/ci-model-runtime.md`, `docs/architecture/summarize/model-boundary.md` | section 8 |

- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, plus `ruff` and `mypy` over the new module; CI - full suite; **plus the three dispatches in section 7.**
- **Oracle:** **the paste rule** (C13), red today on 8 sites, all 8 removed by removing their producers. Siblings that also fail today: the companion-sensitivity key clause; and **the hub host appearing in exactly one file repository-wide.** **What it cannot settle:** whether a real runner downloads the right bytes, serves them, and survives the step. Only the dispatches settle that, and D1 is the only thing that ever executes the multi-file path. ESCALATE triggers 1, 2, 3, 4, 6, 7 and 8 apply.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The first commit is tests only and lands RED**, and **it must widen the fetch discovery**. Without that, row 3 moves the hub URL into Python, discovery falls 8 to 4, and the weights oracle for the production shard leaves the closed world with nothing going red | Carmack |
 | 2 | **Both `llm-` cache keys move in the same commit.** `action.yml:93` spells two inputs this row deletes, and a composite action resolves a deleted input to empty | Fowler |
 | 3 | **All five `llama_argv.py` call sites convert.** Four are live workflow blocks; deleting the module without them kills the qualify job, both pipeline-test server arms and the bench runtime arm on `No such file or directory` | Carmack and Andre |
 | 4 | **`runtime_sweep.py` has no call to convert and leaves PR-B's file list.** It already builds `server_argv` in process and owns the handle three things need. What moves is three names, to `server.py` | Carmack |
 | 5 | **`measure.yml:125-127` is not edited.** A workflow `env:` block cannot read a file, and its consumers are the four inline arms this plan scopes out. A test pins the two copies equal instead | Carmack |
 | 6 | The transport is `urllib` with C8's six clauses, behind **one function**, so a later change is a one-function change. The three reasons an earlier draft gave were all wrong and are deleted; the reason that stands is the owner's ruling | Owner, priced by Carmack |
 | 7 | **No transport probe.** It could not change what gets built - the owner ruled the transport - and could not see what it measured: a 5.9x spread means three samples an arm is a coin toss. The instrument is C8's `INFO` line plus D1, D2 and the eight first-cron shards | Carmack, Guardrail #10 |
 | 8 | `_download` sends **no request headers at all**. CPython forwards them across a cross-host redirect; today this is safe only by accident | Carmack |
 | 9 | `tarfile.extractall(filter="tar")` is named, not defaulted - CI pins 3.12 and the dev box runs 3.14, and the default differs between them | Carmack |
 | 10 | `rmtree` before `copytree`. `dirs_exist_ok` permits existing directories, not existing symlinks, and `cp -a` overwrote | Carmack |
 | 11 | `env={**os.environ, ...}`, `stdin=DEVNULL`, `close_fds=True`. The shell form was a prefix assignment; a bare dict removes `PATH`, and a detached child holding the step's stdio hangs the step at completion | Carmack |
 | 12 | `sudo -n prlimit` on `os.getpid()`. `-n` so a prompt is an instant non-zero the warn path absorbs. It runs in all five sites and is called in one today, while the live model asks for `mmap+mlock` | Carmack |
 | 13 | `start-server` has no `--role` and no `--weights`: one role exists, and the path is derived. **A test clause pins the derived path equal to the pasted one at all five roots before the conversion** | Carmack |
 | 14 | The action gains an `outputs:` block with **three** entries, and `digest.yml`'s call gains an `id:` | Carmack |
 | 15 | The health step reads its alias and filename **through `env:`**, not pasted. C13 fails on the pasted form, and the step already does the right thing today | Andre |
 | 16 | **`WEIGHTS_CHECKS` shrinks to four and the closed-world equality stays an equality**, because decision 1 widens discovery | Fowler |
 | 17 | `test_pinned_versions.py` changes shape and gains a non-vacuity assertion. After this row its derived caller set is empty and it would otherwise pass by finding nothing | Fowler |
 | 18 | One convention: path invocation everywhere, `from utilities import model_refs` for the sibling. **Plus a workflow test that every job reaching the new module installs the package first** - the failure is invisible locally because pytest's `pythonpath` hides it | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the download script and have it loop rows the reader prints | It invents a format so a shell can do what Python does better, and `measure_llm.py:156-195` already downloads with a `.part` file, a digest check and a skip-if-correct the shell has never had | A third invented format | Owner |
 | 2 | Keep `curl` as a subprocess | It is a custom build wearing a binary, and the owner ruled against it. **Named honestly: it would carry zero transport risk, and it is the fallback if the first cold fan-out fails** | The plan's thesis by one word | Owner, Carmack dissenting on risk only |
 | 3 | Run the transport probe | Guardrail #10's first clause: the number cannot change what gets built. And with a 5.9x spread, a design with power costs about 68 GB of hub egress | 10 to 45 minutes of runner time for an answer nobody acts on | Carmack |
 | 4 | Keep the pin as a shell file and parse it from Python | A shell-variable parser written to read a file we control | 20 lines of parser and a format that is not JSON for no reason | Fowler |
 | 5 | Split the key change into its own row | The action's key spells inputs this row deletes | A guard red between two commits, which says those commits are one change | Fowler |
 | 6 | Move `measure.yml`'s pin in this row | It is a workflow `env:` block; moving it means a pin-reading step in jobs that have no `setup-python` at all | Two jobs that cannot run the reader | Carmack |
 | 7 | Convert `runtime_sweep.py` to call `start-server` | It trades a live `Popen` handle - which `read_status`, the reaper and the sampler thread all need - for a pid file | A working sweep | Carmack |
 | 8 | Leave `start-llama-server.sh` alone and do only the download | It keeps the NUL-joined argv format and its four workflow readers, inside the plan that exists to delete them | Three small diffs saved | Owner |

## Section 5 - Rows 4 and 5 - The case runner and the sampler

They dispatch together and **share one file**: `_harness.py`'s `SHIPPED_SCRIPTS` constant, because each deletes a script. **The resolution rule is mechanical: keep both sides' deletions - the list only ever shrinks.** Budget one merge-resolve-push cycle for whichever lands second.

### Row 4 - The pipeline-test case runner becomes Python

- **Scope:** Replace `run-pipeline-test-case.sh` with `backend/utilities/pipeline_test_case.py`.
- **Files touched:** `.github/scripts/run-pipeline-test-case.sh` (delete, 54); `.github/workflows/idhazh-pipeline-tests.yaml` (`:304`, `:315`, `:374`); `backend/utilities/pipeline_test_case.py` (new); `backend/tests/workflows/test_pipeline_tests_workflow.py` (`:94`, `:655`); `backend/tests/workflows/_harness.py` (`SHIPPED_SCRIPTS`, one name).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_pipeline_tests_workflow.py -q`; CI - full suite. No dispatch of its own: the workflow that runs it is the one row 3's D1 and D2 already exercise.
- **Oracle:** **the exit-code contract, driven from a fixture tree** - exit 2 for a missing case directory, exit 2 for a missing plan, and any other non-zero for a pipeline failure, asserted against the workflow's own conditional. **It fails today in the sense that nothing tests it**, which is the finding. `SHIPPED_SCRIPTS` falls from 5 names to 4. **What it cannot settle:** whether a real case run produces the same output, which the next pipeline-tests dispatch shows.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The exit-code mapping is a contract, not a detail.** Exit 2 means a missing case directory or a missing plan; any other non-zero means the pipeline failed. The workflow distinguishes them | Fowler |
 | 2 | The `python -m idhazh work` call stays a subprocess. A case is meant to run the way a shard does, and a shard is a process with its own memory | Carmack |
 | 3 | The elapsed-seconds line stays, in the same words. A person scanning a run log reads it | Reader |
 | 4 | This row runs after row 3 because both edit `idhazh-pipeline-tests.yaml` | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Fold it into `model_runtime.py` | That module answers what a runner needs to serve a model; running a pipeline case is a different question | One file with two answers | Fowler |
 | 2 | Call `idhazh.work` in process | A case is meant to run the way a shard runs | A measurement that no longer matches what it measures | Carmack |

### Row 5 - The memory sampler joins the one that already exists

- **Scope:** Replace `sample-rss.sh` with `backend/utilities/memory_sampler.py`, sharing the `/proc` read `runtime_sweep.py` already has, and rewrite the `awk` summary that reads its output.
- **Files touched:** `.github/scripts/sample-rss.sh` (delete, 108); `.github/workflows/digest.yml` (`:619`, `:627-629`, **`:888-917` the `awk` summary**); `backend/utilities/memory_sampler.py` (new); `backend/utilities/runtime_sweep.py` (`:294` extracted, `:529` caller); `backend/tests/workflows/_harness.py` (`SAMPLE_SCRIPT:530`, `RSS_SAMPLE_FILE:512`, the stale `:526-529` comment, `SHIPPED_SCRIPTS`); `backend/tests/workflows/test_model_server_jobs.py` (`:382`); plus the two plan-doc edits of section 6's transfer.
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'sampler or sweep or model_server' -q`; CI - full suite. **No dispatch of its own**: the only workflow that runs this step is `digest.yml`, which has `contents: write` and would publish and push.
- **Oracle:** the **detachment** test - launch the sampler from a parent python that then exits, and assert the parent exits 0, the pid in the file is alive, **`os.getsid(pid) != os.getsid(0)`**, it wrote at least two records, and it stopped after the target died. **It fails today only in the sense that 108 lines of sampling logic have no test at all**, which is itself the finding. Second clause: the `summarize` verb prints the same five figures from a fixture that the `awk` block prints from the equivalent tab-separated file. **What it cannot settle:** whether the numbers match on a real runner - they are the same `/proc` fields read the same way, and a side-by-side is not worth a digest run.
- **The watch, because there is no dispatch:** on the first cron after this merges, read the `work` job's memory summary step. **If it prints only a header, revert.** Worst case is one production run with no memory reading - a lost measurement, not a failed publish.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **This is a merge, not a port.** `runtime_sweep.py:294` already reads `VmRSS:` and `VmHWM:` and `:529` already starts a thread called `sample_rss`. The shared read moves into the new module and both call it | Carmack |
 | 2 | **It writes two files, not one** - `rss-samples.tsv` and `python-procs.tsv` - and `digest.yml:888-917` runs an `awk` program over the first. **Both become JSON Lines and the `awk` becomes a `summarize` verb in the same commit**, or the memory summary degrades to "not found" without failing. No schema is owed: these are run artifacts, not persisted payloads a later run reads | Andre |
 | 3 | The launch is **foreground parent, detached child**: `Popen(start_new_session=True)` with all three streams set, the parent writes **the child's** pid and exits 0. **Not `&`.** Today `$!` records the pid of the backgrounded *shell*, so a sampler that dies at once leaves a pid file naming a dead shell and a green step | Carmack |
 | 4 | It is still a **separate process**. It must outlive a process the job starts and stops, and a thread dies with its interpreter | Carmack |
 | 5 | `test_model_server_jobs.py:382`'s `assert "nohup" in script` splits into a workflow assertion about the pid agreement between steps and an integration test using `os.getsid`. **Neither half is a literal** | Carmack |
 | 6 | The two marks - python as well as llama-server - are kept, with the reason the script's header gives | Carmack |
 | 7 | This row runs after row 3 because both write `digest.yml`. **Not because of `runtime_sweep.py`** - row 3 does not touch it | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | A thread inside the job's main Python process | It must outlive a process that job starts and stops | A sampler that stops recording exactly when the interesting part happens | Carmack |
 | 2 | Keep the two tab-separated files | Two invented formats with one producer each, and one has an `awk` reader | Nothing saved | Fowler |
 | 3 | Delete the sampler and rely on the sweep's thread | The sweep runs on a bench dispatch; this runs on the daily digest, where the 16 GB ceiling actually binds | The only memory record production produces | Carmack |
 | 4 | Background it with `&` as today | It records the shell's pid, not the sampler's | The bug that is already there | Carmack |

## Section 6 - Row 6 - The last three scripts go

**Status: BLOCKED. Depends-on: plan 46 all-DONE.** It is a row and not a scope-out line so this plan cannot close while **653 lines of shell across three files** survive. Plan 44 is reviewed and closed for its own work at rows 1 to 5 DONE; row 6 stays here, and this Reckoner is the only place it is tracked.

- **Scope:** Replace `commit-and-push.sh` (**556 lines today, not 436 - it grew 120 in #1051 and #1052**), `take-state-from-the-tip.sh` (47) and `push-rewritten-history.sh` (50) with Python, and **delete `.github/scripts/`**.
- **Why `push-rewritten-history.sh` is here and not a row of its own:** it landed in #1053 on 2026-09-22 with one caller at `prune.yml:193`. Plan 46 names it once, in **its own row 7's files-touched list, and that row is DONE** - it records a file plan 46 created, not a future row. No PENDING row in any plan proposes porting it. A separate row would need its own pull request, worktree and wave slot and would contend for `_harness.py` with rows 3, 4 and 5. **And without it row 6's oracle is unsatisfiable**: a third script would still be there after row 6 landed.
- **The condition, checked and not assumed:** plan 46's Reckoner reads all-DONE. On 2026-09-22 it has **9 of 17 rows PENDING across waves 3 to 7**, and rows 9 to 15 rewrite the day and ledger staging this script performs - so the blocker is the work itself, not a merge conflict.
- **The narrower condition that would open it sooner, priced:** no PENDING plan-46 row names any of the three scripts in its own files-touched list. On 2026-09-22 the three plan-46 rows that wrote those bodies are DONE, and rows 11, 15 and 17 change the *arguments* to the commit script rather than the script. Establishing it costs one read of plan 46's PENDING rows and **it is a person's call**, because a row that gains the file after the read lands a hand resolution on the step that pushes to `main`.
- **Files touched:** the three scripts; their **ten** call sites - `backfill.yml:114`, `digest.yml:272`, `:440`, `:827`, `:1273`, `:1380`, `llm-council.yml:433`, `measure.yml:835`, `validate.yml:544`, `prune.yml:193`; `_harness.py` (`SCRIPTS_DIR:32`, `SHELLCHECK_COMMAND:164`, `RSS`-era constants, `COMMIT_SCRIPT:564`, `COMMIT_SCRIPT_CALL:566`, `:855`, `:1856-1857`, `TAKE_STATE_SCRIPT:612`, `TAKE_STATE_CALL:614`, `PRUNE_PUSH_SCRIPT:619`, `PRUNE_PUSH_CALL:621`, `:1880`, `SCRIPT_CALL:1548` and `:1557` which become dead); `test_script_invocation.py` (**the whole module retires** - `:99` asserts a workflow names a shipped script); `test_ci_selection.py:41`, `:52`; `test_pinned_versions.py:90`, `:99-100`; `test_daily_commit_steps.py:157`; `test_staged_paths.py:354`; `test_telemetry_cli.py:66`; `test_model_server_jobs.py:116`; `test_llm_council_workflow.py:85`; `backend/tests/workflows/rebuild_day.py:4`; `backend/utilities/drop_raced_assets.py:3`; `backend/idhazh/telemetry/publish/series.py:70`.
- **Acceptance gates, written now and not at unblock.** A gate written at unblock is written by the worker to fit what the worker built (Guardrail #9).

 | # | Gate |
 | --- | --- |
 | 1 | local - `python -m pytest backend/tests/workflows -q`, `ruff`, `mypy` over the new module |
 | 2 | CI - full suite |
 | 3 | **Deadline semantics pinned before the port.** A fixture drives the retry loop to its deadline and asserts the attempt count, the elapsed bound and the exit code. `$EPOCHREALTIME` becomes `time.monotonic()`, and the test is written against **the script's behaviour read on `main` at dispatch**, never against this page |
 | 4 | **One real dispatch that pushes** - `digest.yml` on the branch, one shard. The push path is the whole of what the script does |
 | 5 | **One real dispatch that races a concurrent push and rebases.** Start a second pushing workflow against the same ref while gate 4's push is in its loop. The retry-under-collision path has no test today and is why this row is Level 4 |
 | 6 | `prune.yml`'s tip re-check still refuses when origin moved. A port that drops it re-opens the force-push-over-a-run hole (CLAUDE.md section 8) |
 | 7 | Every commit still sets `miztiik <miztiik@users.noreply.github.com>` with no `Co-authored-by` trailer |
 | 8 | **Re-measure before any code.** Re-read all three scripts on `main` and re-price the row. The counts here were taken 2026-09-22 and one of them moved by 120 lines that day |

- **Oracle:** the `SHIPPED_SCRIPTS` constant is empty and the test asserts **`.github/scripts/` does not exist.** It fails until this row lands. **What it cannot settle:** whether the rebase-and-retry path behaves identically under real contention, which gate 5 settles and nothing cheaper does.
- **The transfer, so the row cannot be lost:**

 | Who | When | What, exactly |
 | --- | --- | --- |
 | the owner of **PR-E (row 5)**, in PR-E itself | the pull request that makes rows 1 to 5 DONE | one line appended to **plan 46's row 14 section body** (`### Row 14 - The concurrency group goes`, its last row): *"When this row lands, plan 46 is all-DONE. Stamp plan 44 row 6 READY in plan 44's Reckoner - it is the last three shell scripts and this plan's rows are what block it."* |
 | - | - | **Not plan 46's Reckoner table.** Every plan-46 branch touches adjacent rows of that table; a row-14 section body does not, so this edit conflicts with nothing in flight |
 | the owner of plan 46's row 14 | when row 14 merges | stamps plan 44 row 6 `READY`, in that same change |
 | - | - | **Row 6 never leaves plan 44's Reckoner. There is no second list** |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | It waits rather than rebasing. A 653-line port cannot be reconciled with edits to the same files in flight; every other row here rebases under plan 46, and this one does not | Fowler |
 | 2 | `push-rewritten-history.sh` folds in rather than becoming its own row. No other plan owns it, and without it this row's oracle cannot pass | Fowler |
 | 3 | The trigger lives in plan 46's row 14 **section body**, not its Reckoner table, so it conflicts with nothing in flight | Fowler |
 | 4 | Gates are written now. Re-measuring may move the size, the file list and the price; it may not move the gate list and it may not re-open whether the row happens | Andre |
 | 5 | `git` stays a subprocess. It is a stable command-line interface this project already drives from Python in four utilities, and no Python git library is declared | Carmack |
 | 6 | `$EPOCHREALTIME` and `mapfile` are the two shell features the port answers for. `time.monotonic()` and a list replace them, and the deadline semantics are what gate 3 pins | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Do it now, rebasing under plan 46 | Nine PENDING rows rewrite the staging this script performs | A hand resolution nobody reviewed, on the step that pushes to `main` | Fowler |
 | 2 | Drop it and file it separately | A plan that deletes eight of eleven scripts and writes nothing about the rest leaves a reader thinking the job is done | 653 lines nobody is tracking | Owner |
 | 3 | Make `push-rewritten-history.sh` its own row | Its own pull request, worktree and wave slot, contending for `_harness.py`, for a 50-line file with one caller | Three sources of friction, and an unsatisfiable oracle in row 6 | Fowler |
 | 4 | Add a Python git library | Nothing declares one and `git` is stable | A dependency and its install time for a subprocess that works | Carmack |

## Section 7 - The three dispatches, after row 3's second commit

Four things a dispatch must prove that nothing cheaper can: the download fetches **every** declared file on a real runner and each one's digest and size pass; the verify runs on a **restored** entry; the key Actions resolves is the key the reader renders; and the server starts from Python and survives into the next step.

| # | Dispatch | Runs | Proves | Read | On failure |
| --- | --- | --- | --- | --- | --- |
| D1 | `idhazh-pipeline-tests.yaml`, PR-B branch, `candidate_models_file: config/models/gemma-4-e4b-qat.json` | first | the download **loops**; per-file digest and size on a companion; the count check; the scratch config root; the landed path; the new launch; the new transport at 4.28 GB | **two download lines, two digest passes**, and the throughput seconds. Cancel at the green verify | one download line means it did not loop - fix the iteration, re-run D1 |
| D2 | same workflow, same branch, empty input, **after D1** | second, serialised by `concurrency: pipeline-tests` | the production key resolves with no `${{` left in it; the entry saves; 5.68 GB through the new transport | the resolved key off the cache step, character-for-character against the action's; the throughput seconds. Cancel at the verify | key mismatch - fix the fold, re-run D2 only |
| D3 | `llm-council.yml`, same branch, empty date, **after D2** | third | the no-`if:` verify over **restored** bytes; cross-caller key equality, where the hit itself is the proof; the server starting from Python and **surviving into the next step** | cache-hit true, verify green, health green | a miss is a finding, not a re-run: read both resolved keys, fix, re-run D3 only |

**D1 and D2 cannot run concurrently** - `concurrency: group: pipeline-tests, cancel-in-progress: false` puts the second in `pending`. **Neither covers the other**: the live pointer declares no companion, so an empty dispatch exercises a one-file download indistinguishable from today's.

**D2 does not warm production.** A cache entry written on a branch is not restorable from `main`. D2 proves the key string and that the entry saves, nothing more. D3 works because it restores on the same branch D2 wrote.

**Eviction is likely between D2 and D3** - 5.68 + 5.68 + 4.28 GB against a 10 GB allowance - so **compare the two resolved key strings from the logs regardless of whether D3 hits.**

**D3 pushes council verdicts to the branch. Drop that commit with a revert before merge, never a rewind.** Its cron is `0 22 * * *` with `cancel-in-progress: false`, so a dispatch **queues behind** a running cron rather than cancelling it: start before 21:00 UTC or after the 22:00 run finishes, and be present when it lands.

**The first post-merge production cron: every shard misses.** The `-v5` key has never been written on `main`, so all shards download 5.68 GB cold, in parallel. The second cron four hours later restores normally. **The operator watches four things, in order:**

1. **Download-step exit codes across all shards. Two or more non-zero fires the revert** - `git revert` of row 3's second commit, which restores the four scripts, `llama_argv.py`, the ten-input action and the `-v4` key together. One non-zero is hub flake: read the log, record the seconds, do nothing.
2. The throughput line's seconds per shard. **Record all eight into `docs/reference/benchmarks/what-a-bench-dispatch-costs.md` with hardware and date** - this is the sample the refused probe would have bought.
3. The cache step on the **second** cron: `cache-hit: true`. False again means the key is not stable across runs, which is a defect and not a cost.
4. The no-`if:` verify on that second cron - restored bytes, on `main`. **No branch dispatch can prove that one.**

## Section 8 - The docs

| Page | Section | What it becomes | Row |
| --- | --- | --- | --- |
| `docs/reference/ci-model-runtime.md` | `### Where the three values are written` (`:25`) | `### Where the model file is read, and how many places that is` - one place. **The stale `LLAMA_SCRIPT_CALLERS` citation at `:51` is deleted**; that symbol exists nowhere in the repository | 3 |
| `docs/reference/ci-model-runtime.md` | `### What the cache key holds` (`:59`) | the literal becomes `llm-<digest over every declared file>-<build>-v5`, **plus the three key formats over `backend/models` and why only `llm-` must resolve equal**, plus the one `## Design rationale` entry this plan owes | 3 |
| `docs/reference/ci-model-runtime.md` | `## Every download fails loudly` (`:113`) and `### The digest settles the bytes` (`:156`) | the four-row "Digest read from" table collapses to one; the declared-size check becomes shared; **C8's six transport clauses and the no-headers rule with its reason**; **the corrected statement that this path has never resumed**; the production entry size corrected to **5.68 GB**, with the note that the 57 to 338 s figures were taken on the 4.28 GB arm | 3 |
| `docs/reference/ci-model-runtime.md` | `### Every download names a commit` (`:226`) | "one bare word" becomes the closed grammar row 1 ships | 3 |
| `docs/architecture/summarize/model-boundary.md` | **delete `## What is wrong with the boundary today` (`:504-544`)**; gain the declaration contract and the one-companion refusal | four of its six paragraphs are dated status prose about work already done. **The two that survive become rows in `## Which side each fact lives on` (`:88`)**: `:522` "The entry declares its architecture..." and `:533` "The entry names the weights it was set for...". Folding creates no duplicate | 3 |
| `docs/reference/agent-notes/gates-and-builds.md` | a new line | **a cache entry written on a feature branch is not restorable from `main`** - measured 2026-09-22, and it is why no dispatch can warm production | 3 |

**The page pays the split test before it is added to** (AGENTS.md). `model-boundary.md` is 555 lines and its own `:542` says it "describes the boundary rather than tracking work", so the status section is the cut and one addition buys exactly that one cut. `ci-model-runtime.md` passes without a cut. **Run `python backend/utilities/doc_load.py` before and after.**

**One `## Design rationale` entry, on `ci-model-runtime.md` under `### What the cache key holds`: the cache key is computed inside the action from the model file, not passed in by the caller.** A real alternative is what every caller does today, reversing it costs every caller a full re-download, and it crosses the workflow-to-action boundary. No other decision here earns one.

## Section 9 - What this plan costs, all of it

| Arm | Key after | Jobs missing together | Caused by | Bytes |
| --- | --- | --- | --- | --- |
| **The first production cron after row 3 merges** | `llm-<64hex>-<build>-v5`, never written on `main` | **every shard, up to 8, concurrently** | row 3 | 8 x 5.68 GB in one burst |
| Production thereafter | same | 0 - the second cron restores | - | - |
| Pipeline-tests | the same string when the input is empty | 1 | row 3 | shares production's entry |
| Qualify - `validate.yml:284` | expression unchanged, **value** changes | the qualify matrix, up to 8 | **row 1** | 4.22 to 6.64 GB per candidate |
| Bench - `measure.yml:289`, `:570`, `:899` | expression unchanged, **value** changes | 1 each | **row 1** | per candidate |

**Rows 1 and 3 invalidate disjoint sets**, so merging them on different days costs nothing extra. Row 1's arms are dispatch-only, so the daily run pays nothing for it and the next dispatch pays once.

**Eviction is certain and is the desired outcome.** Old production plus new plus one gemma qualify entry is 15.64 GB against a 10 GB allowance; GitHub evicts least-recently-used, and the old `-v4` entry is the least recently used the moment row 3 merges.

**This plan crosses neither of the two numbers that fail a run** - the 6 h job cap and the 1 GB site. `shard_timeout_minutes` is 200 against a worst-case cold fetch of 76 to 449 s; the production digest is 164 to 184 min against 360.

**It can fail a job, and the plan says which.** A stalled download, a failed extract or a server that does not survive its step each cost one shard's items, and `assemble` still publishes the day. C8's wall-clock deadline and throughput floor exist because a socket timeout alone would hold that shard to its full 200 minutes.

**The one runtime risk this plan adds, named without hedging:** the download moves from `curl --retry 3 --retry-all-errors` - a decade of flaky-CDN handling - to about 80 lines of transport nothing has run at 5.68 GB. **The first eight-shard cold fan-out is the moment it is tested, and it is the worst possible moment.** The mitigations are C8's six clauses, `_download` being the only function that touches the network so a change of transport is a one-function change, and the revert being one `git revert` of row 3's second commit.

## See also

- [`20260921-42-lane-b-workflows-plan.md`](20260921-42-lane-b-workflows-plan.md) - the parent, whose rows 1 to 6 landed and whose rows 7 to 11 this plan carries.
- [`20260922-46-no-file-has-two-writers-plan.md`](20260922-46-no-file-has-two-writers-plan.md) - in flight. Section 1c is the interlock; row 6 waits on it and writes its trigger into that plan's row 14; three of this plan's scope-out lines become rows there.
- [`20260922-47-the-pipeline-stops-naming-a-server-plan.md`](20260922-47-the-pipeline-stops-naming-a-server-plan.md) - shares one docstring in `backend/idhazh/llm/server.py`. Whoever lands second rebases one hunk.
- [`../docs/reference/ci-model-runtime.md`](../docs/reference/ci-model-runtime.md) - the page that owns the model path and the cache key.
- [`../docs/architecture/summarize/model-boundary.md`](../docs/architecture/summarize/model-boundary.md) - the page that owns what the model file declares.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed.




