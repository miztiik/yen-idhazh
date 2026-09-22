# The shell scripts become Python

**Last Updated**: 2026-09-22

**The filename keeps its old slug.** Three live plans and `TODO/STATUS.md` link this file by name, and one of them is in flight; renaming it costs four edits in other agents' files to change an address nobody reads for meaning.

**Level**: 4, and row 3 is why. It rewrites the download and start path the daily run depends on, and only a live dispatch proves it, so a revert would land after a failed publish - CLAUDE.md section 6's Level-4 test. Row 1 is Level 3: `one_bare_word` at `backend/utilities/model_refs.py:41` refuses whitespace and nothing else, while **13 model-file values are pasted textually into `run:` bodies across four workflows**, where a value spelling `$(id)` executes. That is this repository's own env-not-paste rule failing on a maintainer-written config file. **It is not a Guardrail #11 question** - Guardrail #11 is about fetched web text, and a model file is neither fetched nor web. Rows 2, 4 and 5 are Level 2.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight - two, because section 1b's readiness table shows two disjoint pairs and never three; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Ten shell scripts sit between this repository's data and what runs on a runner, and **every invented data format in the repository sits exactly where Python hands something to one of them.** `backend/utilities/llama_argv.py:54` writes the llama-server command line NUL-joined so `start-llama-server.sh:63` can read it back with `mapfile -d ''`. `sample-rss.sh` writes a `python-procs.tsv` because shell cannot hold a structure. The model's own JSON file is retyped through four layers - a printer, a job output, an action input and an environment variable - before a `curl` sees it, and the arity is welded at two files, so a model shipping three cannot be described. `model_refs.py:41` refuses whitespace only, so `../../x.gguf`, `x.gguf$(id)` and a branch name in place of a commit all pass. The pin is spelled in two places. The production cache key names no companion. **Every one of these is a shell script being asked to do a program's job.** |
| The rule | **A program is written in Python. A workflow step calls one.** Where Python already owns the answer - the server command line, the memory sampler, the model file - the shell stops being the courier, and the format invented to reach it goes with it. |
| The second rule | **A value this project computes is published, never composed a second time downstream, and never serialised to cross a process this plan can delete.** |
| The measure | **Lines of shell in `.github/scripts/`, and invented data formats.** Shell 883 -> 483 in this plan, and -> 0 when row 6 lands. Invented formats: 2 -> 0. |
| Hard scope - in | Eight of the ten scripts are deleted and their work moves into Python: the llama.cpp pin, the runtime install, the weights fetch, the server launch, the pipeline-test case runner, the memory sampler, and the two CI-selection scripts. The model file gets one reader with a closed field grammar, a landed path, a declared-size check and a cache key over the whole declared set. |
| Hard scope - out | See the table below. Every line there is a dated decision with a price, never a law (CLAUDE.md section 0d). |
| Supersedes | Plan 42 rows 7 to 11, which are `COLLAPSED` in that plan's Reckoner. |
| Assumes | **Plan 41 merged as #1036 and #1039.** `COMPANION_FIELDS`, `_companions()` and the companion-joining `_cache_key` are on `main`. |
| ESCALATE triggers | (1) **Row 3's first commit is tests only and lands RED.** If a commit moves the fetch before those tests exist, stop - C12 says why the order is the control. (2) Row 3 must leave a digest check that runs on a cache hit. The download runs behind `cache-hit != 'true'`, so a check living only inside it never sees a restored entry. (3) If any step between the cache restore and the verify acquires `continue-on-error: true`, or the cache step is split into `actions/cache/restore` plus a save with `if: always()`, stop. Both make `actions/cache`'s `post-if: success()` untrue, which is the only thing stopping a failed job writing a bad entry (C11). (4) If the cache key can be anything but 64 lowercase hex characters, stop: `llm--<build>-v5` is one key every model shares. (5) **If row 1 deletes any published output key, stop.** Row 1 is additive on keys; `measure.yml` reads seven of them and is in neither of the first two pull requests (row 1 decision 1). (6) **If the two weights cache keys move in different commits, stop.** (7) **If any row edits `.github/scripts/commit-and-push.sh` or `take-state-from-the-tip.sh`, stop.** Those are row 6, and row 6 is blocked on plan 46. (8) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | **Five pull requests in three waves, then one blocked row.** Two pairs are genuinely disjoint, so the pool is two wide in waves 1 and 3. Fowler ruled the grouping, the row collapse and the test rewrites; Carmack the download path, the cache, the dispatches and the process launch; Andre the grammar, the refusal messages and the paste rule. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2 - two disjoint pairs, never three.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **`.github/scripts/commit-and-push.sh` (436 lines) and `take-state-from-the-tip.sh` (47)** | 483 lines of shell survive this plan, and the repository still has a 436-line bash program with eight call sites across five workflows and a `$EPOCHREALTIME` deadline loop | **Nothing. They are row 6 of this plan**, blocked on plan 46 and tracked in the Reckoner so they are not forgotten. Plan 46 is rewriting parts of `commit-and-push.sh` right now across seven waves; a port landed underneath it conflicts on every merge. Row 6 opens when plan 46's Reckoner reads all-DONE |
| **`measure.yml`'s four inline weights downloads and its four `candidate_draft_*` job outputs** | The printer keeps a one-companion projection - four `draft_*` keys on one verb - and `measure.yml` keeps its own copy of the pin at `:125-127` and its own `byte_count` cross-check at `:596` and `:923` | The four arms reach neither the composite action nor the shared download; the `batched` arm spells `MODEL_*` and is a different shape; and the `llama-bench` arm unpacks its own tarball rather than calling the shared installer. `measure.yml` is plan 46's file in two of its rows. **It becomes a row in plan 46**, which owns the file: four arms, about 14 consumer lines, one bench dispatch to re-prove against a 330 min bound. Carmack |
| **Refusing `needs.*.outputs.*` inside any `run:` body, repository-wide** | **28** job-output expressions keep reaching a shell through textual substitution rather than `env:`. A value spelling `$(id)` executes, and nothing mechanical refuses a 29th | **It is plan 46's row.** Plan 46 already owns `test_triggers.py`, `digest.yml`, `measure.yml` and `validate.yml` in its group A. Counted by parsing each workflow and matching `needs.<job>.outputs.<key>` inside every step's `run` string, all scalar forms. **What this plan takes free instead**, inside row 3: the same rule scoped to jobs reaching the shared download, which fails today on 8 of the 13 and whose 8 producers row 3 deletes. Andre proposed it; Fowler ruled on where it lands |
| **Cutting `backend/tests/workflows/_harness.py` to names more than one module reads** | The module stays 2,248 lines with 241 top-level names, and **a one-file change still has to touch 143 of them** - 10 that nothing imports plus 133 that exactly one module imports | Plan 46's Reckoner all-DONE **and** this plan's row 3 merged. Plan 46 writes `_harness.py` across seven waves. Re-run the census - never read a recorded table - and run it as its own plan. The earlier draft's "nine of 45 orphans are internal" was wrong: it is 35 of 45 |
| **Every `run:` body in every workflow** | Workflow steps still contain shell, and some of it is long | Out of reach and out of scope: a composite action and a workflow step run a shell by definition. What this plan changes is that a step's body becomes **one call to a program**, not a program |
| **A third-party HTTP library** | The downloads use `urllib.request` plus a small retry, which is what `backend/idhazh/fetch.py` already does for every page this project reads | Guardrail #8 asks for a mature library and prices the dependency. `httpx` or `requests` would be the candidates, and neither is declared in `pyproject.toml` today. **What brings it in:** a measurement showing the hand-written retry has cost a run. Until then the house pattern is stdlib, and it is already load-bearing at `fetch.py:400` |

### What a change costs today

Measured on `origin/main`, 2026-09-22, by reading the files.

| Reading | Value | Where |
| --- | --- | --- |
| Lines of shell under `.github/scripts/` | **883** across 10 files | `commit-and-push.sh` 436, `sample-rss.sh` 108, `start-llama-server.sh` 72, `run-pipeline-test-case.sh` 54, `fetch-model-runtime.sh` 53, `take-state-from-the-tip.sh` 47, `install-llama-runtime.sh` 43, `llama-cpp-pin.sh` 34, `changed-docs.sh` 32, `browser-suite-needed.sh` 4 |
| Invented data formats, and where each sits | **2**, both at a Python-to-shell boundary | `llama_argv.py:54` writes NUL-joined argv, read by `start-llama-server.sh:63` with `mapfile -d ''`; `sample-rss.sh` writes `python-procs.tsv` |
| Whether Python already builds the llama-server command | **yes.** `start-llama-server.sh:11-13` says so itself: "the argv is still built by `idhazh.llm.server.server_argv` ... This script never names one" | `backend/utilities/llama_argv.py`, 59 lines |
| Whether Python already samples process memory the way `sample-rss.sh` does | **yes**, and the function has the same name | `runtime_sweep.py:294` `read_status` reads `VmRSS:`/`VmHWM:`; `:529` starts a `sample_rss` thread |
| Scripts that are **sourced** rather than executed | **2**, and this is the only real obstacle | `llama-cpp-pin.sh` into `install-llama-runtime.sh`; `install-llama-runtime.sh` into `fetch-model-runtime.sh`. A sourced script sets variables in its caller's shell, which a Python program cannot - and which stops mattering the moment both are one program |
| Places the llama.cpp pin is spelled | **2** | `llama-cpp-pin.sh:26-28` and `measure.yml:125-127`. The pin file's own header says it exists because the pin "used to be written in six places that had to change together" |
| Hops from the model file to the download | **4** - printer, job output, action input, environment | `model_refs.py` -> `$GITHUB_OUTPUT` -> `action.yml:107-115` -> `fetch-model-runtime.sh:30-32` |
| What `one_bare_word` refuses | **whitespace and empty only** | `model_refs.py:41`. Admitted on a direct call: `../../x.gguf`, `x.gguf$(id)`, `` x.gguf`id` ``, `a"b`, `a;b`, `$(curl${IFS}evil)`, `%2e%2e%2fx`, `/etc/passwd`, `..`, `.hidden`, `x.txt`. **`$(...)` needs no whitespace and `${IFS}` supplies whitespace without a space character** |
| Whether `model_refs.py`'s own docstring is true | **no.** `:1-4` says it is "where a value carrying a space, a quote or a newline stops". `'a"b'.split() == ['a"b']` | it also cites Guardrail #11 for a committed config file |
| Model-file values pasted into a `run:` body | **13** - `digest.yml:604`; `idhazh-pipeline-tests.yaml:201`; `measure.yml:330`, `:587`, `:596`, `:914`, `:923`; `validate.yml:320`, `:321`, `:329`, `:367`, `:368`, `:399` | measured by parsing every workflow and matching inside each step's `run` string |
| Of those 13, how many row 3 removes | **8** - every one in a job reaching the shared download | `measure.yml`'s 5 are out of scope |
| Whether the weights `file` has any segment rule | **none, in either layer** | `ModelRef.file` is `Field(min_length=1)`; `CompanionFile` validates companions only, in Pydantic, which never runs on the shell path because `model_refs.py` reads raw JSON |
| Whether `byte_count` is checked at all before printing | **no** | `model_refs.py:153` prints it straight. A newline in that value writes extra `key=value` lines into `$GITHUB_OUTPUT` |
| Whether every companion's `sha256` is checked | **no** - the projection checks the first companion only, while `_cache_key` digests every one | `model_refs.py:68-84` against `:86-97`. **A two-companion entry today keys on two files and fetches one** |
| Key length if the existing hyphen-join met seven files | **519 characters**, past GitHub's 512-character cap | `_cache_key` at `model_refs.py:97` |
| Companion files the production cache key names | **0** | `action.yml:93`. Its `-v4` suffix is four hand bumps already paid |
| Second hand-copy of that key format | **1**, also `-v4`, invisible to the guarding test because that test scopes its closed world to the action's callers | `idhazh-pipeline-tests.yaml:167` against `test_weights_and_model_refs.py:344` |
| Which arms are already protected from the companion hole | the benchmark and qualification arms - they key on `candidate_cache_key`, the printer's key, which already digests every companion | `measure.yml:268`, `:549`, `:878`; `validate.yml:284`. **Production is the only uncovered one** |
| Inline Python programs walking a model file inside a workflow | **6, of which 5 are in scope** | in scope: `action.yml:136`, `:183`; `idhazh-pipeline-tests.yaml:196`, `:274`, `:354`. Out: `measure.yml:1151` |
| Places `backend/models/<file>` is composed by hand | **9** | `action.yml:147`; `fetch-model-runtime.sh:38`, `:42`, `:51`; `digest.yml:583`, `:604`; `validate.yml:320`, `:337`, `:399`; `idhazh-pipeline-tests.yaml:201`, `:247`, `:327` |
| Committed model files declaring a companion | **1 of 5**, and it is a bench candidate rather than the pointer | `config/models/gemma-4-e4b-qat.json:5` |
| Consumers of `candidate_draft_*` outside the first two pull requests | **4 arms, 14 lines** | `measure.yml:150-153`, `:308-331`, `:503-506`, `:853-856`. **This is why row 1 deletes no key** |
| The production weights entry | **5.68 GB** (`5,680,522,464` bytes) | `config/models/qwen3.5-9b-q4km.json`. The benchmark seconds below were taken on the 4.28 GB gemma arm and scale by about 1.33 |
| A cold weights fetch against the restore it replaces | download **57 to 338 s**, restore **38 to 95 s** | `docs/reference/benchmarks/what-a-bench-dispatch-costs.md`, eight `runtime` jobs, 2026-09-14 to 2026-09-16 |
| Whether `actions/cache@v6` saves when the job failed | **no.** Its manifest declares `post-if: "success()"`; `save-always` is inert and deprecated | read from the v6 manifest, 2026-09-22 |
| External tools the deleted scripts need, which leave with them | `jq` leaves the model path entirely; `curl`, `tar`, `find`, `cp -a`, `sha256sum`, `stat`, `mapfile` leave the eight scripts | `git` stays, because row 6's two scripts are git programs |

## Section 0b - What this plan does, in one list

1. The model file gets one reader: a closed field grammar, a landed path, a declared size, a cache key over the whole declared set, and no key deleted.
2. The two CI-selection scripts go - one becomes Python, the other is a four-line shim whose caller can call the thing directly.
3. The model path becomes one Python program: the pin, the runtime install, the weights download and the server launch, with both invented formats deleted and the composite action down to four inputs.
4. The pipeline-test case runner becomes Python.
5. The memory sampler joins the Python sampler that already exists.
6. The last two scripts - plan 46's - are tracked here and ported when plan 46 closes.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The model file gets one reader, and the grammar closes | - | A | PENDING | - | - | - |
| 2 | The two CI-selection scripts go | - | A | PENDING | - | - | - |
| 3 | The model path becomes one Python program | 1 | B | PENDING | - | - | - |
| 4 | The pipeline-test case runner becomes Python | 3 | C | PENDING | - | - | - |
| 5 | The memory sampler joins the one that already exists | 3 | C | PENDING | - | - | - |
| 6 | The last two scripts go | plan 46 | D | BLOCKED | - | - | - |
| 7 | The benchmark arms learn the server died, and the repeat count is config | - | E | DONE | p42p5 | - | P5 |
| 8 | The harness keeps only what more than one module reads | - | F | COLLAPSED | - | - | - |

**Row 6 is BLOCKED, not out.** It carries `.github/scripts/commit-and-push.sh` and `take-state-from-the-tip.sh`, the two scripts plan 46 is editing. It opens when plan 46's Reckoner reads all-DONE. **It is a row rather than a scope-out line so the plan cannot close while 483 lines of shell survive** - and ESCALATE trigger 7 stops any other row reaching into those two files early.

**The cache key has no row of its own.** It cannot: `action.yml:93` spells `inputs.weights_file` and `inputs.weights_revision`, and row 3 deletes both. A composite action referencing a deleted input resolves it to the empty string, so a separate cache row would leave `llm---<build>-v4` - one key every model shares - for the length of one commit. Row 3 owns it.

**Row 7 landed ahead of the earlier sequence and nothing is owed for it.** `runtime_sweep.py:328` carries `START_GRACE_SECONDS: Final = 2.0`; `backend/idhazh/contracts/knobs/bench.py:47` carries `repeats`.

**Row 8 is COLLAPSED into the fourth line of the hard-scope-out table**, with its cost and the condition that brings it back. Both collapsed and blocked rows stay in this table rather than being deleted: a row deleted from a Reckoner turns a priced decision into a proposal with no author.

### Section 1a - The pull requests and the files each owns

**No two pull requests in flight at once own one file.** `test_weights_and_model_refs.py` is in PR-A and PR-B, and that is safe because PR-B cannot start until PR-A merges.

| PR | Rows | Wave | Files it owns |
| --- | --- | --- | --- |
| **PR-A - the model file's reader** | 1 | 1 | `backend/utilities/model_refs.py`, `backend/tests/workflows/test_weights_and_model_refs.py`, `backend/tests/workflows/test_pipeline_tests_workflow.py`, `backend/idhazh/llm/server.py` (one docstring at `:437-439`) |
| **PR-C - the CI-selection scripts** | 2 | 1, beside PR-A | `.github/scripts/browser-suite-needed.sh` (delete), `.github/scripts/changed-docs.sh` (delete), `.github/workflows/ci.yml`, `frontend/scripts/test-scope.ts`, `backend/utilities/changed_docs.py` (new), `backend/tests/workflows/test_ci_selection.py` |
| **PR-B - the model path** | 3 | 2, alone | `.github/scripts/llama-cpp-pin.sh`, `install-llama-runtime.sh`, `fetch-model-runtime.sh`, `start-llama-server.sh` (all four deleted), `.github/actions/model-server/action.yml`, `.github/workflows/digest.yml`, `llm-council.yml`, `validate.yml`, `idhazh-pipeline-tests.yaml`, `measure.yml` (two lines: the server-start call and the pin), `config/llama-cpp-pin.json` (new), `backend/utilities/model_runtime.py` (new), `backend/utilities/llama_argv.py` (deleted), `backend/utilities/runtime_sweep.py`, `backend/tests/workflows/test_weights_and_model_refs.py`, `_harness.py`, `test_pinned_versions.py`, `test_model_server_jobs.py`, `docs/reference/ci-model-runtime.md`, `docs/architecture/summarize/model-boundary.md` |
| **PR-D - the case runner** | 4 | 3 | `.github/scripts/run-pipeline-test-case.sh` (delete), `.github/workflows/idhazh-pipeline-tests.yaml`, `backend/utilities/pipeline_test_case.py` (new), `backend/tests/workflows/test_pipeline_tests_workflow.py` |
| **PR-E - the sampler** | 5 | 3, beside PR-D | `.github/scripts/sample-rss.sh` (delete), `.github/workflows/digest.yml`, `backend/utilities/memory_sampler.py` (new), `backend/utilities/runtime_sweep.py`, `backend/tests/workflows/_harness.py` |
| **PR-F - the last two scripts** | 6 | after plan 46 | `.github/scripts/commit-and-push.sh`, `take-state-from-the-tip.sh`, and whatever plan 46 leaves of their callers |

**`measure.yml` enters PR-B for two lines and no more**: the `start-llama-server.sh` call and the pin copy at `:125-127`. Its four inline weights arms stay out (scope-out table). That is a smaller claim than plan 46's rows on the same file and rebases under them.

**PR-D and PR-E are disjoint** - one owns `idhazh-pipeline-tests.yaml`, the other `digest.yml`. **PR-E and PR-B both touch `runtime_sweep.py`**, which is why PR-E waits.

### Section 1b - Readiness, computed rather than read off a letter

| When this is true | Ready together | Held, and why |
| --- | --- | --- |
| now | **rows 1 and 2** | rows 3, 4, 5 need row 1's contracts or row 3's files. Row 6 is blocked |
| row 1 merged | **row 3**, and row 2 if still in flight | rows 4 and 5 share workflow files with row 3 |
| row 3 merged | **rows 4 and 5** | row 6 |
| plan 46 all-DONE | **row 6** | nothing |

**Peak workers: 2**, in waves 1 and 3. Wave 2 is one pull request by file arithmetic - after row 3 it owns every workflow the model touches.

### Section 1c - The interlock with plan 46

Plan 46 is in flight. PR-B shares three files with it: `digest.yml` (six of plan 46's ten pull requests write it), `validate.yml`, `measure.yml` and `_harness.py`. PR-E shares `digest.yml` and `_harness.py`.

**Ruling: land them when ready and let plan 46's branches merge `main` in.** PR-B's `_harness.py` hunk is four dictionary entries, one constant and one literal, textually far from plan 46's `COMMIT_REFRESH_PATHS` work. A small branch rebasing under a large one is the cheap direction. **The owner tells plan 46's owner the file list at each dispatch**, so a rebase is expected rather than discovered. **Row 6 is the exception and it does not rebase - it waits**, because a 436-line port cannot be reconciled with seven waves of edits to the same file.

## Section 1d - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent any shape below; it reads this section.** No persisted payload changes, so CLAUDE.md section 11 owes nothing.

### C1 - What the model file's reader publishes (row 1)

`backend/utilities/model_refs.py` keeps one question - what does this model declare, and is every value safe to hand to a program - and it stays **stdlib-only and runnable by path**. It imports nothing from `idhazh` and nothing from `utilities`.

**Row 1 is additive on published keys. It deletes one thing: the `--repo-root` argument.** No caller passes it, verified across all five invocations.

**The verbs are renamed. Every one is a verb, per CLAUDE.md:113.** The two existing names are adjectives and go with the rest.

| Today | After | Callers |
| --- | --- | --- |
| `configured` | `describe-pinned-model` | the composite action, `digest.yml`, `llm-council.yml`, and `measure.yml` through `--also-pinned` |
| `candidate` | `describe-trial-model` | `idhazh-pipeline-tests.yaml`, `measure.yml`, `validate.yml` |
| - | `list-model-files` | **nothing outside Python.** It returns objects to `model_runtime.py`; there is no text form and no separator to choose |
| - | `fingerprint-model-files` | the cache step in the action and in `idhazh-pipeline-tests.yaml` |

**`--also-configured` becomes `--also-pinned`.** All four verbs take `--config-root`, default `config`.

**There is no row format.** `list-model-files` returns a list of frozen dataclasses. The earlier draft had it print seven tab-separated columns so a shell loop could read them; row 3 deletes the shell loop, so the format deletes itself. **A worker that reintroduces a text form for this has reintroduced the defect this plan is named after.**

**The declared file, as a Python object.** One per file the model declares, weights first, then companions in declared order.

| Field | Content | May be absent |
| --- | --- | --- |
| `repo` | the hub repository | no |
| `revision` | the commit | no |
| `file` | the filename | no |
| `sha256` | the digest | no |
| `flag` | the server flag this file is passed under | **yes** - every weights row has none |
| `landed_path` | `MODELS_DIR` plus the validated `file` | no |
| `byte_count` | the entry's declared size | **yes** - absent means the entry declares no size |

**Three keys are added to both describe verbs**, so nothing downstream composes a path or re-reads the model file: `weights_path` (the weights file's `landed_path`), `cache_key` (the C5 digest; the trial verb already publishes it) and `id` (the served alias).

**Every key `describe-pinned-model` emits begins `summarize_`; every key `describe-trial-model` emits begins the caller's `--prefix`.** The six pinned keys are `summarize_repo`, `summarize_revision`, `summarize_file`, `summarize_id`, `summarize_weights_path`, `summarize_cache_key`, and no seventh. **Why the prefix is mandatory rather than tidy:** `measure.yml:184` runs the trial verb with `--prefix candidate_ --also-pinned`, writing both sets into one `$GITHUB_OUTPUT` block, and `validate.yml:160` uses the **empty** prefix. A bare `cache_key` from each would land in one block and resolve last-write-wins with nothing red. A unit test asserts `set(pinned) & set(trial at empty prefix) == set()`.

**The one-companion projection survives, renamed and refusing.** The four `draft_*` keys on the trial verb are the reason row 1 deletes nothing.

| Case | What it does |
| --- | --- |
| how it is built | from the **same objects `list-model-files` returns**, taking the companions and never re-reading the entry |
| entry declares none | four empty strings, exactly as today. `measure.yml`'s `[ -n "${DRAFT_FILE}" ]` guard skips |
| entry declares two or more | **raises**, naming the models file and the count. Not truncation |

The two-companion refusal is free - no committed entry declares two - and closes a defect live on `main`: the projection publishes companion 0 while the cache key digests all of them, so a two-companion dispatch today keys on two files, fetches one, and the server arm restores a short entry. The declaring line carries the removal condition (Guardrail #6): *delete these four keys when `measure.yml`'s four inline weights downloads move onto the shared download; nothing else reads them.*

**`models_file` is published as the proved path** - `path.relative_to(<the --config-root>).as_posix()`, not the raw input, and not relative to the repository root: `candidate-config` writes it into a scratch `idhazh.json` under `backend/var/candidate-config`.

### C2 - The grammar (row 1)

**Declared in `model_refs.py` itself, with `re.compile` and nothing but stdlib `re`.** Not imported from `measure_llm.py`, and not moved to a shared third module. Both break a job with no install:

| Direction | What breaks |
| --- | --- |
| `model_refs.py` imports `measure_llm` | `from utilities.measure_llm import ...` resolves only because each caller ran `pip install -e .` and hatchling's editable `.pth` exposes all of `backend/`. `pyproject.toml:175` declares `packages = ["backend/idhazh"]`; `utilities` is not a declared package. The failure is invisible to every local gate, because pytest sets `pythonpath = ["backend"]`. `measure.yml:158-164` carries the written invariant, added after a dispatch died on `ModuleNotFoundError` |
| a shared third module | `measure_llm.py` runs **two** ways - by path at `measure.yml:376` in the `llama-bench` job, which has no `setup-python` and no install, and as `utilities.measure_llm` under pytest. No single plain import statement works in both |

**Every pattern keeps its `^` and `$`, and is applied with `re.fullmatch`** - never `re.match`, never `re.search`. `$` matches before a trailing newline, so `match` admits a value the anchors look like they refuse.

| Value | Rule | State |
| --- | --- | --- |
| `repo` | `^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$` | exists as `REPO_RE`, `measure_llm.py:28`. Gated |
| `revision` | `^[0-9a-f]{40}$` - a commit, never a branch | exists as `REVISION_RE`, `measure_llm.py:32`. Gated |
| weights `file` | `^[A-Za-z0-9][A-Za-z0-9._-]*\.gguf$` | exists as `GGUF_RE`, `measure_llm.py:29`. Gated. **The live gap** |
| companion `file` | `^[A-Za-z0-9][A-Za-z0-9._-]*$` - the same segment rule, **without the suffix rule** | new. `CompanionFile` has no suffix rule because a companion may be a projector, an adapter or a vocoder |
| `sha256`, weights and **every** companion | `^[0-9a-f]{64}$`, **required, no exception** | new |
| `id` | `^[a-z0-9]+(?:-[a-z0-9]+)*$` | new. **Gated against `SLUG_PATTERN` at `backend/idhazh/contracts/base.py:49`** |
| `quantisation` | `^[A-Za-z0-9_.-]+$` | new |
| `byte_count` | **empty, or** `^[1-9][0-9]*$` on the emitted string. Empty means the entry declares no size. Non-empty refuses `0`, a leading zero, a sign and a float | new. No check at all today |
| `flag` | **empty, or** `^--?[A-Za-z0-9][A-Za-z0-9-]*$`. **One dash is legal**: llama.cpp's short form for a draft model is `-md`, and the live model's `server` block carries eleven single-dash flags | new |
| the set | two entries resolving to one filename is refused, and the message names both | exists, `measure_llm.py:71-75` |
| **every emitted value, last** | the string is **empty, or `^[\x21-\x7E]+$`** - printable ASCII with no space. **Empty is legal for exactly `flag` and `byte_count`** | **the backstop, and the load-bearing row** |

**The backstop is a character class, never `str.isprintable()`.** That call admits `e` with a combining acute and DIVISION SLASH, either of which builds a hub URL that is not the one a reviewer read. No-space rather than admit-space: `one_bare_word` refuses whitespace today, so a backstop that admitted it would be a regression dressed as a hardening.

**Four values have no rule of their own, and that is a decision rather than an omission.** `ref` is `f"{repo}@{revision}:{file}"` - all three parts ruled, and its only consumer re-parses it with the same three patterns at `measure_llm.py:58-75`; **the invariant to state beside it is that `@`, `:` and `,` stay outside those three classes or the re-parse mis-splits.** `weights_path` and `landed_path` are `MODELS_DIR` plus a ruled `file`. `cache_key` is hex by construction, **asserted `^[0-9a-f]{64}$` anyway** - that assertion is what catches a worker who keeps the hyphen-join. `models_file` is **containment-proved rather than pattern-checked**: `resolve_under_config` resolves the path and proves it is under the config root, which is stronger than a regex because `..` is what resolving exists to defeat.

**All five committed model files clear every rule**, checked field by field on 2026-09-22. The grammar refuses nothing that exists today.

**The duplications are gated by tests rather than by attention.** One contract test holds an explicit tuple `("REPO_RE", "REVISION_RE", "GGUF_RE")` and asserts, for each, that the name exists on both modules and that `.pattern` and `.flags` are equal - flags are not optional, because `re.IGNORECASE` on one side is a second grammar sharing one pattern string. A fourth assertion covers the slug against `contracts/base.py:49`. **The test can import `idhazh`; the reader cannot. That asymmetry is why the copy is legal and why the gate is mandatory.**

**Three Guardrail #11 citations are wrong and are corrected in the commit that touches each file**: `model_refs.py:1-4` (row 1), and the comments in the action and the deleted script (row 3). The replacement names what is true: these values are pasted into `run:` bodies where the Actions engine substitutes before bash parses, so the reader refuses them before a program sees one.

### C3 - The refusal message (row 1)

**On a malformed entry the verb raises and exits non-zero. Not a skip**: a skipped companion is a server that fails to start over a missing file, or one that starts and silently does nothing.

**Every refusal names four things in this order: the models file, where in it, the rule in plain words, and the offending value in `repr()`** so a control character is visible. "Where in it" has three forms and no fourth: a **field** gets its dotted JSON path including every list index; a **composed value** is reported against the field it was composed from, with the composed value in `repr()`; a **whole-set rule** names the entry, the rule, and **every** participating location and value, because one location would name a file that is not wrong on its own. **Never print a regex.**

```
config/models/gemma-4-e4b-qat.json: summarize.companion_files[0].file:
  not one path segment: '../../x.gguf'
config/models/qwen3.5-9b-q4km.json: summarize.revision:
  not a 40-character commit: 'main'
config/models/x.json: summarize: two files land on one name:
  summarize.file 'x.gguf' and summarize.companion_files[1].file 'x.gguf'
```

### C4 - The landed path, composed in exactly one place (rows 1, 3)

`model_refs.py` declares `MODELS_DIR: Final = "backend/models"`, its only spelling, and composes `landed_path` and `weights_path` from it. That removes the composition from nine sites: three in the deleted download script, one in the action, and five across four workflows, each of which reads a published `weights_path` instead. `backend/idhazh/llm/server.py:437-439` is corrected in row 1 - it carries a **false docstring plan 41 landed**, claiming `model_refs.py` imports `companion_path`, and `model_refs.py` imports nothing from `idhazh`.

**No cross-module test between `model_refs.py` and `idhazh.llm.server`.** `companion_path` is one line with one caller; a test asserting two values agree would not have caught the docstring already wrong on `main`.

### C5 - The cache key (rows 1, 3)

| Property | Value |
| --- | --- |
| Shape | **a fixed-width SHA-256 hex digest**, never a join. The existing hyphen-join reaches 519 characters at seven files, past GitHub's 512-character cap |
| What it covers | `repo`, `revision`, `file` and `sha256` per file, in declared order |
| Serialisation, to the byte | `hashlib.sha256(b"\n".join(b"\t".join(f.encode("ascii") for f in (repo, revision, file, sha256)) for each file)).hexdigest()`. TAB between fields, LF between rows, **no trailing LF**, ASCII, lowercase hex. This is an internal digest input, not a published format - nothing reads it back |
| Why a plain `.encode("ascii")` is safe | every one of those four values has already passed its field rule and the backstop, so the digest can assume ASCII with no tab and no newline. **Nothing enters the digest the grammar has not already seen** |
| What it must **not** cover | **`flag`** - it reaches the server command line, not the download, so digesting it discards the whole entry when the flag is edited for zero byte change. **`landed_path`** - derived from `file`. **`byte_count`** - derived from the bytes `sha256` already covers. **The config root** - it is how the files were found, never part of what is hashed |
| Why excluding the config root is a contract | the closing dispatch only hits because one caller reads `backend/var/candidate-config` and another reads `config`, and two roots holding the same entry must produce the same key. A unit test drives exactly that. **A worker who "fixes" a cross-caller miss by putting the root into the key has destroyed the property that makes the dispatch work** |
| Shape assertion | the verb refuses to return anything but `^[0-9a-f]{64}$` |
| The suffix | `-v4` becomes `-v5`, declared once as `WEIGHTS_CACHE_SUFFIX` at `_harness.py:357`. **It is kept, and it is not a version of the key format** - it is the manual eviction handle for the three things the digest cannot see: an entry already poisoned, a llama.cpp release re-uploaded under one build tag, and a change to the runtime install that alters `backend/bin`, which is in `path:` and in no key component. It costs one character and zero bytes, because it rides the invalidation the digest already causes |
| Paths | unchanged: `backend/models` and `backend/bin`, together, on one key. **No `restore-keys`** - a prefix restore would serve a stale file set under a key that says otherwise |

**Both spellings move in one commit** - `action.yml:93` and `idhazh-pipeline-tests.yaml:167`. They are one format written twice; `action.yml:47-52` records them drifting once already. Row 3 widens the guarding test's closed world from the action's callers to **every `actions/cache` step whose `path:` names `backend/models`**, and adds a resolved-value equality clause across that set. **That clause is a guard, not an oracle**: it is green the day it is written, and its job is to refuse a commit that moves one spelling alone.

### C6 - The llama.cpp pin becomes data (row 3)

`.github/scripts/llama-cpp-pin.sh` is deleted. Its three constants move to **`config/llama-cpp-pin.json`**, read by `model_runtime.py`.

| Property | Value |
| --- | --- |
| Shape | `{"build": "b10598", "asset": "llama-b10598-bin-ubuntu-x64.tar.gz", "sha256": "d77a09db..."}` |
| Why `config/` | it is a tunable that changes on an upgrade, so Guardrail #6 puts it there. **No schema is owed**: the owner ruling of 2026-09-21 says a configuration file this project authors needs no declared shape, because nothing but this repository writes one and nothing but this repository reads one |
| Why not a module constant | five workflow steps read the build to name a cache key, and a cache step runs **before** anything is downloaded - so the pin has to be readable without installing anything, which is exactly what a JSON file beside the other config is |
| What reads it | `model_runtime.py`, and nothing else. The four workflows that run the old script for its `llama_cpp_build=` line call `python3 backend/utilities/model_runtime.py print-pinned-build >> "$GITHUB_OUTPUT"` instead |
| The comment it carries | the pin file's own header, kept: this exists because the pin used to be written in six places that had to change together. **`measure.yml:125-127` is the seventh and it is still there** - row 3 repoints those three lines at the new file and does not touch the rest of that workflow |
| `sha256` | the release API's own `digest` for that asset, confirmed 2026-08-25 by downloading the 16,377,727-byte archive and hashing it. That sentence moves with the data |

**The sourcing problem disappears here.** `llama-cpp-pin.sh` was sourced into `install-llama-runtime.sh`, which was sourced into `fetch-model-runtime.sh`, because a sourced script sets variables in its caller's shell. One Python program has no caller to export into.

### C7 - `backend/utilities/model_runtime.py`, the one program (row 3)

**One new module replaces four scripts and 202 lines of shell.** Its question: *what does this runner need in order to serve the model the config names, and is it here and correct?*

**It is stdlib-only and runnable by path**, for the same reason `model_refs.py` is (C2). It imports `model_refs` **by path-relative import**, which works because both sit in `backend/utilities/` and the module is only ever run as `python3 backend/utilities/model_runtime.py`, never imported. **A test asserts it is never imported**, so the day somebody wants to import it they hit a red test rather than a `ModuleNotFoundError` in CI.

| Verb | What it does |
| --- | --- |
| `print-pinned-build` | prints `llama_cpp_build=<build>` from `config/llama-cpp-pin.json`. Replaces running `llama-cpp-pin.sh` |
| `install-runtime` | replaces `install-llama-runtime.sh` |
| `download-model-files` | replaces `fetch-model-runtime.sh`'s download half |
| `verify-model-files` | the restore-time check, callable on a cache hit where nothing was downloaded |
| `start-server` | replaces `start-llama-server.sh` |

**`install-runtime`, step by step.** Every external tool the shell version needed is gone.

```
1. Read config/llama-cpp-pin.json.
2. GET https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/<build>
   with Authorization: Bearer <GITHUB_TOKEN>, urllib.request, json.loads.
   Authenticated because every shard asks at once and anonymous
   api.github.com allows 60 requests an hour.
3. Find the asset whose name == <asset>. Absent -> raise, naming both.
4. Download browser_download_url to a temp file (C8's downloader).
5. hashlib.sha256 == <sha256>, or raise naming both digests.
6. tarfile.extractall to a temp directory.
7. shutil.copytree(src, "backend/bin", symlinks=True, dirs_exist_ok=True)
   where src is the directory holding `llama-server`.
   symlinks=True is load-bearing: these builds ship versioned shared
   objects as symlinks, and a binary copied without its shared objects
   dies at exec with a 127 that names a library rather than the mistake.
8. os.chmod("backend/bin/llama-server", 0o755).
```

**`download-model-files`, step by step.**

```
1. files = model_refs.list_model_files(config_root)   # every C2 refusal here
2. Refuse an empty list by name.
3. For each file, in declared order:
     a. Already present with the right size and digest -> skip, log it.
        Present and wrong -> raise naming the path, do not overwrite.
     b. Download to "<landed_path>.part" (C8's downloader).
     c. Check the digest, and the declared size where the entry gives one.
     d. os.replace(".part", landed_path).   Atomic; a killed job leaves
        no half file under the cache key.
4. Assert the count downloaded plus skipped equals the count declared.
```

**`verify-model-files`** re-reads the declaration and, for every declared file, checks the digest and the declared size where there is one. **It runs on a cache hit, where nothing was downloaded**, which is the whole reason it is a separate verb (C11).

**`start-server`, and the format it deletes.**

```
1. subprocess.run(["sudo","prlimit","--memlock=unlimited","--pid",str(os.getpid())])
   Log the before and after ulimit. A failure here WARNS and continues,
   exactly as the script does: an unlocked model is slower, not wrong.
2. argv = idhazh.llm.server.server_argv(...)   -- in process.
   backend/utilities/llama_argv.py and its NUL-joined file are DELETED.
3. subprocess.Popen(argv, stdout=log, stderr=STDOUT,
                    env={... "LD_LIBRARY_PATH": "backend/bin"},
                    start_new_session=True)
4. Write the pid file. `runtime_sweep.py` and the health checks read it.
5. Sleep 2 s, then confirm the process has not exited. On exit, print the
   last 50 log lines and fail - the shape start-llama-server.sh:67-72 has.
```

**Step 2 is the point of the whole row.** `start-llama-server.sh:11-13` already says the argv is built by `idhazh.llm.server.server_argv` and that the script never names a flag. The only reason it was serialised is that a shell had to hand it to `nohup`.

**This verb imports `idhazh`**, unlike the rest of the module - `server_argv` lives there. That is legal because `start-server` runs in a job that has already installed the package; `install-runtime` and `download-model-files` run in the same job but must keep working if it has not, so **the `idhazh` import is inside `start-server`, never at module scope.** A test asserts no `idhazh` name appears at module level.

### C8 - The downloader (row 3)

**One function, used by `install-runtime` and `download-model-files`.** `urllib.request`, not `curl`: a subprocess to a binary is neither a mature library nor a custom build worth defending, and `backend/idhazh/fetch.py` already reads every page this project fetches through `urllib` with its own opener and retry.

| Property | Value |
| --- | --- |
| Transport | `urllib.request.urlopen`, streamed to the destination in chunks, never `read()` into memory - the production entry is 5.68 GB against a 16 GB runner |
| Retry | up to 3 attempts, on a connection error and on a 5xx, with a short backoff. **Never on a 4xx**: retrying a permanent failure burns the budget the transient ones need, which is the sentence `fetch.py:298` already carries |
| Destination | always `<final>.part`, renamed with `os.replace` only after the digest passes |
| Resume | **not carried over.** `curl --continue-at -` resumed a partial file; the `.part`-plus-rename shape means a partial never survives to be resumed. Say so where it is written, because it is a deliberate loss |
| Progress | log the URL, the byte count and the elapsed seconds per file, at `INFO`. That is what makes a slow shard diagnosable, and it is what the `curl` output gave for free |
| Timeout | a read timeout, so a stalled connection fails rather than holding a job to its 200-minute bound |

### C9 - The composite action after row 3 (row 3)

**Ten inputs become four: `github_token`, `port`, `llama_cpp_build`, `config_root`** (`required: false`, `default: 'config'`). It gains an `outputs:` block, which it has none of today - without one, `digest.yml`'s reads resolve to empty and a `sha256sum` runs on a directory.

```yaml
outputs:
  weights_path:
    description: 'The landed relative path of the weights, as the reader composed it.'
    value: ${{ steps.model.outputs.summarize_weights_path }}
```

| # | Step | After |
| --- | --- | --- |
| 1 | **new, `id: model`** | `python3 backend/utilities/model_refs.py describe-pinned-model --config-root "$CONFIG_ROOT"`, **captured into a variable, asserted to carry a 64-hex `summarize_cache_key`, then appended** to `$GITHUB_OUTPUT`. Capture then append, never append straight: a reader that dies mid-stream would otherwise leave half its keys behind. ESCALATE trigger 4 is enforced on this step |
| 2 | Cache, `id: weights` | `key: llm-${{ steps.model.outputs.summarize_cache_key }}-${{ inputs.llama_cpp_build }}-v5`. Paths unchanged, no `restore-keys` |
| 3 | Install the runtime and download the model | `if: steps.weights.outputs.cache-hit != 'true'`. Body is two calls: `model_runtime.py install-runtime` then `model_runtime.py download-model-files --config-root "$CONFIG_ROOT"` |
| 4 | Verify the model files | **no `if:`**, unchanged position. `env: CONFIG_ROOT` - **it is a separate step and inherits nothing.** Body is one call: `model_runtime.py verify-model-files --config-root "$CONFIG_ROOT"`. The inline Python at `:136` goes |
| 5 | Start the model | `model_runtime.py start-server --role summarize --name llama-server --config-root "$CONFIG_ROOT"`, with `LLAMA_PORT` in `env:`. The `backend/models/` composition at `:147` goes |
| 6 | Check model health | the alias comes from `steps.model.outputs.summarize_id`; the `/props` check reads `steps.model.outputs.summarize_file`. The inline Python at `:183` goes |

**The key is computed inside the action, never passed in.** A caller-computed key is hop 3 of the four this plan deletes, and it would cost three lines each in `digest.yml` and `llm-council.yml`. Computed, it costs zero lines in both callers and it is provably the set the download reads.

**`jq` leaves the model path.** Two uses remain in the action's health check, which stays a `curl`-plus-`jq` step; converting that is not this row's business and is not worth a row of its own.

### C10 - The three small ports (rows 2, 4, 5)

| Script | Becomes | The one thing a worker must not get wrong |
| --- | --- | --- |
| `browser-suite-needed.sh` (4 lines) | **nothing.** It is `exec node frontend/scripts/test-scope.ts --ci`. `ci.yml:77` calls node directly and the file is deleted | **`frontend/scripts/test-scope.ts:172` names this script inside a regex** that decides which tests a change needs. That regex loses the script and gains `.github/workflows/ci.yml`, which it already lists - so the selection is unchanged. Its own tests at `frontend/scripts/tests/test-scope.test.mjs` are the gate |
| `changed-docs.sh` (32 lines) | `backend/utilities/changed_docs.py`, called at `ci.yml:118`. `subprocess.run(["git", ...])` for the two git calls, and the same two `$GITHUB_OUTPUT` keys | **It never fails a run.** The script's own header says so: this measures and gates nothing, so a range it cannot resolve answers `any=false` rather than reddening a check. Three cases keep that: an empty or absent `BASE`, the all-zero SHA, and a `BASE` this clone cannot resolve |
| `run-pipeline-test-case.sh` (54 lines) | `backend/utilities/pipeline_test_case.py`, called three times from `idhazh-pipeline-tests.yaml` | It already shells to `python -m idhazh work`; that becomes an in-process call or a `subprocess.run`, and the **exit code 2 for a missing case directory or a missing plan is preserved**, because the workflow distinguishes it |
| `sample-rss.sh` (108 lines) | `backend/utilities/memory_sampler.py`, and **this is a merge, not a port.** `runtime_sweep.py:294` already has `read_status` reading `VmRSS:` and `VmHWM:`, and `:529` already starts a thread called `sample_rss` | It is **backgrounded** by `digest.yml:627-629` with `nohup` and a pid file, and it must **outlive** the server it watches. As Python: `subprocess.Popen(..., start_new_session=True)`, same pid file. The per-process rows it writes stop being a `.tsv` and become the same JSON the rest of the telemetry uses (CLAUDE.md section 1b) - **and the schema question does not arise, because this is a run artifact rather than a persisted payload a later run reads** |

### C11 - What stops a bad cache entry being written (row 3)

| Half | Where | Runs on a hit? |
| --- | --- | --- |
| **restore-time - the control** | `verify-model-files`, in a step with **no `if:`**, in every caller, after the download and before the first read of `backend/models` | **yes.** This is the only one that does |
| download-time - an early exit | inside `download-model-files`, per file | no. That verb runs behind `cache-hit != 'true'` |

**`actions/cache@v6` does not save when the job failed.** Its manifest declares `post-if: "success()"`; `save-always` is inert and deprecated. So a failed verify writes no entry - on the miss path as well, because the verify sits in the same job and `post-if` runs after every step.

**The door `post-if` cannot see** is a download that exits 0 having fetched fewer files than the model declares. `download-model-files` step 4 names it inside the program; the no-`if:` verify catches it either way.

**The standing rule:** no step between the cache restore and the verify may carry `continue-on-error: true`, and the cache step is never split into `actions/cache/restore` plus a save with `if: always()`. Either makes `post-if: success()` untrue. Neither exists in the model path today.

### C12 - The commit order that protects the verify step (row 3)

**The first commit is tests only, and it lands RED.** The second commit does everything else.

| Clause | State when written |
| --- | --- |
| **the paste rule** (C13) | **red: 8 sites** - `digest.yml:604`, `idhazh-pipeline-tests.yaml:201`, `validate.yml:320`, `:321`, `:329`, `:367`, `:368`, `:399` |
| **every declared file reaches a digest check in a step with no `if:`** | red: no verify step reads the declaration today |
| **the verify step's config root equals the download step's** | red: the download step names no root today |
| **the companion-sensitivity oracle** - two fixture entries differing only in one companion digest render different cache keys | red: `action.yml:93` names no companion |
| **`.github/scripts/` holds no file this row deletes** | red: four are there |
| **the resolved-value equality guard** across every `actions/cache` step whose `path:` names `backend/models` | **green, and it stays green.** A guard against one spelling moving alone |
| the three clauses already green at `test_weights_and_model_refs.py:59-88` - closed-world discovery, the step names in order, no `if:` on the check | green, and not rewritten |

**Why the order is the control.** The most likely failure in this plan is a worker seeing a digest check inside `download-model-files` and a second in the verify step, reading the second as redundant, deleting it, and going green everywhere. With the tests landing first and red, the worker goes red locally before the push. **One review rule rides with it: row 3's diff must not remove `assert "if" not in check` at `test_weights_and_model_refs.py:84`.**

**`WEIGHTS_CHECKS` shrinks from eight entries to four, and `test_weights_and_model_refs.py:71` stays an equality.** Discovery still finds eight jobs, because `download-model-files` still reaches `huggingface.co`. The written table keeps `measure.yml`'s four; the four converted jobs are **derived** from the shared shape at assertion time. **Do not weaken `:71` to a subset.** A converted job's digest anchor is `model_runtime.py verify-model-files`.

### C13 - The paste rule, stated in terms a test can evaluate (row 3)

**In every job of the closed world, no `run:` body carries an expression that resolves to a value the model file's reader published.**

| Clause | Rule |
| --- | --- |
| the closed world | computed, never listed: every `(workflow, job)` that calls `./.github/actions/model-server` or runs `model_runtime.py download-model-files`. A ninth job that starts downloading weights joins it with no edit |
| what it walks | `_harness._steps(workflow, job)` - which resolves a repository-local composite action's steps in place - and from each step the `run:` string. **`env:`, `with:`, `key:` and `if:` are out of scope**: the point of the rule is that `env:` is where these values are allowed to be |
| what it matches | every `${{ ... }}` by `re.findall(r"\$\{\{(.*?)\}\}", body, re.S)`. Take the dotted segments; skip unless the **first** is `steps`, `needs` or `inputs` - `github.run_id` ends in `_id` and is not one of ours. Let `S` be the **last** segment |
| the predicate | fails if `S in PUBLISHED_KEYS` or `S.endswith("_" + key)` for any key. The suffix arm catches the prefixed spellings without the test holding a prefix list that goes stale |
| `PUBLISHED_KEYS` | **read from the reader, never retyped**: the union of its two field tuples and a new `PUBLISHED_EXTRA` constant naming exactly `("models_file", "ref", "byte_count", "cache_key", "weights_path")`. **Row 1 adds it and the emit path iterates it**, so a key published later without joining that tuple fails the reader's own round-trip test. A literal list in the test file is the one implementation this clause forbids |
| the message | names the workflow, the job, the step, the expression and the key it matched, and says the repair in one line: *move it to `env:` and read it as a shell variable* |
| what it cannot settle | `measure.yml`'s five paste sites. They reach neither the action nor the shared download, so the closed world excludes them by construction rather than by exemption |

### C14 - The rule that keeps the shell from coming back (rows 2 to 5)

**A test asserts `.github/scripts/` contains exactly the files this plan has not yet deleted**, by name, with the two row-6 scripts listed and a one-line reason beside each. It lands red in row 2's commit at eight names, and each row makes it less red. When row 6 lands, the list is empty and the test asserts the directory is gone.

**It cannot go red by accident** - only a human adding a script turns it red - so it is a structure test rather than a data-dependent one (CLAUDE.md section 13). It is the one mechanical thing stopping the eleventh script.

## Section 2 - Row 1 - The model file gets one reader, and the grammar closes

- **Scope:** Give `model_refs.py` the four renamed verbs, three new published keys, a closed field grammar, one spelling of the models directory, and the file-set digest - deleting no published key and no argument but `--repo-root`.
- **Files touched:** `backend/utilities/model_refs.py`; `backend/tests/workflows/test_weights_and_model_refs.py`; `backend/tests/workflows/test_pipeline_tests_workflow.py` (it imports two row builders and a field tuple at `:683-694`); `backend/idhazh/llm/server.py` (the docstring at `:437-439` only).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q` and `python -m pytest backend/tests/test_measure_llm.py -q`; CI - full suite. No dispatch.
- **Oracle:** **stated against the verb production runs today.** Run the existing trial verb against a fixture models file whose `summarize.file` is `../../etc/passwd.gguf`, and a second whose `summarize.file` is `x$(id).gguf`; assert a non-zero exit naming the field. **Today both exit 0 and print the value into `$GITHUB_OUTPUT`.** Second failing case: a fixture declaring seven companions must render a key of at most 64 characters - **today the hyphen-join renders 519, past GitHub's 512-character cap.** **What it cannot settle:** whether a program ever sees an unvalidated value. No test here runs a workflow; row 3's paste rule settles it.
- **The two tests this row rewrites, and the one it must not:**

 | Test | Today | After | Why that is not tautological |
 | --- | --- | --- | --- |
 | `test_an_entry_with_no_draft_head_keeps_the_key_it_already_had` at `:494` | asserts the key **equals the entry's own `sha256`** | **rename it `test_the_key_moves_when_the_declared_set_moves`.** Two fixture entries identical except that one declares a companion render **different** keys, and the no-companion entry's key is **not** equal to any single field | two different inputs, one comparison, so it cannot pass by calling the reader twice. **A clause that calls the reader twice with the same input and compares the results asserts nothing and does not satisfy this row** |
 | a new unit test | - | two config roots holding the same entry render **one** key | it is what makes the closing dispatch's cross-caller proof possible |
 | `CANDIDATE_STEPS` at `:407-410` and the `draft_*` assertion at `:485` | asserts the trial verb publishes the four `draft_*` keys at both prefixes | **unchanged.** Row 1 deletes no key | - |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Row 1 is additive on published keys.** `measure.yml:150-153` publishes four `candidate_draft_*` job outputs consumed by four arms, and `measure.yml` is not in this pull request. A deleted step output resolves to empty rather than failing, so the `:308` guard would go false, the draft would not be downloaded, the no-`if:` draft verify at `:326` would become a no-op that exits 0, and the runtime arm would report speculative-decode throughput for a configuration that never ran. A committed candidate declares a companion today | Carmack and Fowler |
 | 2 | The one-companion projection is built from the **same objects `list-model-files` returns**, and **refuses an entry declaring two or more**. Today it truncates in silence while the key digests all of them | Carmack |
 | 3 | **`list-model-files` returns objects, not text.** The earlier draft printed seven tab-separated columns so a shell could read them; row 3 deletes the shell. Every invented format in this repository sits at a Python-to-shell boundary, and this plan exists to delete those boundaries | Owner ruling, 2026-09-22 |
 | 4 | **All four verbs are verbs** (CLAUDE.md:113). `configured` and `candidate` were adjectives that did not say "model"; `files` and `cache-key` were nouns. Renaming the two old ones is free here because their five call sites are already inside this plan | Owner ruling, 2026-09-22 |
 | 5 | The grammar is **declared in `model_refs.py`** with stdlib `re`, gated by equality tests against `measure_llm.py` and `contracts/base.py:49`. Both alternatives break a job with no install, and the failure is invisible to every local gate | Carmack |
 | 6 | Every pattern keeps `^`/`$` and is applied with `re.fullmatch`. `$` matches before a trailing newline | Andre |
 | 7 | The backstop is `empty, or ^[\x21-\x7E]+$`, and **empty is legal for exactly `flag` and `byte_count`** - every weights file has no flag, and an empty `byte_count` is the declared "nobody has fetched this yet" signal. A backstop refusing empty would take the daily run down on the first merge | Andre |
 | 8 | The backstop is a character class, never `str.isprintable()` | Andre |
 | 9 | `flag` allows **one or two** leading dashes. llama.cpp's short form for a draft model is `-md` | Andre |
 | 10 | The weights `file` gets the `.gguf` suffix rule; a companion `file` gets the segment rule without it | Andre |
 | 11 | The digest covers `repo`, `revision`, `file` and `sha256` only, with C5's serialisation. **Not the config root** - excluding it is what makes the closing dispatch's cross-caller proof possible | Carmack and Andre |
 | 12 | All four verbs take `--config-root`, default `config`; `--repo-root` is deleted. No caller passes it | Fowler |
 | 13 | Every pinned key begins `summarize_`; every trial key begins the caller's prefix, asserted disjoint at the empty prefix | Fowler |
 | 14 | `MODELS_DIR` is declared once, and `server.py:437-439`'s false docstring is corrected in the same commit | Fowler |
 | 15 | `PUBLISHED_EXTRA` is a real module constant the emit path iterates, not a list in a test file | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete the `draft_*` keys here | Five workflows read them; `measure.yml` is not in this pull request, and the failure is silent - a guard goes false and a verify becomes a no-op | A bench arm measuring a model that never loaded its draft head, with the catching test deleted in the same commit | Carmack and Fowler |
 | 2 | Print the file set as TSV, or as CSV | Both invent a format so a shell can read it, and row 3 deletes the shell. CSV would at least match the 275 committed CSV files against 5 TSV, but the right count is zero | A format nobody reads, in the plan named after deleting formats nobody reads | Owner |
 | 3 | Import the patterns from `measure_llm.py` | It resolves only through hatchling's editable `.pth`, which `pyproject.toml` does not pin. Doing it safely means `-m` at six invocation sites, two in files plan 46 owns | Five workflow edits and a `ModuleNotFoundError` class every local gate hides | Carmack |
 | 4 | Keep the hyphen-join and add companions to it | It crosses GitHub's 512-character key cap at about seven files, and nobody would connect that failure to its cause | Nothing saved over a digest | Fowler |
 | 5 | Bare `weights_path` and `cache_key` on the pinned verb | `--also-pinned` at the empty prefix writes two `cache_key=` lines into one output block, and the later silently wins | Ten characters saved, against a collision nothing refuses | Fowler |
 | 6 | Leave `configured` and `candidate` named as they are | They are adjectives on an action, they do not say "model", and this plan edits all five of their call sites anyway | Nothing saved; a reader meets one good surface and one bad one | Owner |

## Section 3 - Row 2 - The two CI-selection scripts go

- **Scope:** Delete `browser-suite-needed.sh` by having `ci.yml` call node directly, and port `changed-docs.sh` to `backend/utilities/changed_docs.py`.
- **Files touched:** `.github/scripts/browser-suite-needed.sh` (delete), `.github/scripts/changed-docs.sh` (delete), `.github/workflows/ci.yml` (`:77`, `:118`), `frontend/scripts/test-scope.ts` (`:172`), `backend/utilities/changed_docs.py` (new), `backend/tests/workflows/test_ci_selection.py`, and the `.github/scripts/` inventory test from C14 (new, lands red).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_ci_selection.py -q` and `npm --prefix frontend run test:changed -- --list` then the selected node checks; CI - full suite.
- **Oracle:** the C14 inventory test - `.github/scripts/` contains exactly the files the plan has not yet deleted. **It lands red at eight names and this row takes it to six.** Plus: `changed_docs.py` answers `any=false` for each of the three unresolvable-range cases, and the node selection for a change to `.github/workflows/ci.yml` is byte-identical before and after the regex edit. **What it cannot settle:** whether the CI job that reads these outputs still behaves the same, which only a real pull request shows. Both outputs are already exercised by every pull request, so the first one after merge is the proof.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | `browser-suite-needed.sh` becomes **nothing**, not Python. It is `exec node <a TypeScript file>`; rewriting it in Python would make it Python calling node. `ci.yml` calls node directly | Fowler |
 | 2 | `frontend/scripts/test-scope.ts:172` names that script inside the regex deciding which tests a change needs. The name goes and nothing replaces it: the regex already lists `.github/workflows/ci.yml`, which is the file that now carries the call | Fowler |
 | 3 | `changed_docs.py` **never fails a run**, preserving the three cases the script's own header names: an empty or absent `BASE`, the all-zero SHA, and a `BASE` this clone cannot resolve. It measures and gates nothing | Fowler |
 | 4 | This row runs beside row 1. Its file list and row 1's are disjoint, which is the only reason the pool is two wide in wave 1 | Fowler |
 | 5 | The C14 inventory test lands in **this** row, not row 3, because this is the first row that deletes a script | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Port `browser-suite-needed.sh` to Python | Python calling node to do what the workflow can call directly | One more process and one more file, for no change in behaviour | Fowler |
 | 2 | Fold both into one Python module | They answer two unrelated questions - which browser tests to run, and which docs changed - and live in two different jobs | One file answering two questions (CLAUDE.md section 1a) | Fowler |
 | 3 | Make `changed_docs.py` fail on an unresolvable range | A force-push or a first push on a branch leaves a base this clone cannot resolve, and this gates nothing | A red check on every first push, for a measurement nobody acts on | Fowler |

## Section 4 - Row 3 - The model path becomes one Python program

- **Scope:** Delete the four model-path scripts and `llama_argv.py`; move the pin to `config/`; put the runtime install, the weights download, the verify and the server launch in `backend/utilities/model_runtime.py`; cut the composite action to four inputs and let it compute its own key, alias and weights path; delete the five relay blocks and five inline Python programs in the callers; and move both weights cache keys onto the digest, in one commit.
- **Commit sequence:**

 | # | Commit | Contents | State |
 | --- | --- | --- | --- |
 | 1 | tests only | the paste rule; the digest clauses; the verify-root clause; the companion-sensitivity oracle; the C14 inventory list dropping to two; the widened cache closed world and its equality guard | **RED** on five clauses, green on the guard |
 | 2 | the change | `model_runtime.py`, `config/llama-cpp-pin.json`, the four script deletions, `llama_argv.py`'s deletion, the action, the five callers including both cache keys, `runtime_sweep.py`, `_harness.py`, both doc pages | **GREEN** |

- **Files touched, with the line lists a worker acts on:**

 | File | What happens |
 | --- | --- |
 | `.github/scripts/llama-cpp-pin.sh`, `install-llama-runtime.sh`, `fetch-model-runtime.sh`, `start-llama-server.sh` | **deleted**, 202 lines |
 | `backend/utilities/llama_argv.py` | **deleted**, 59 lines. Its NUL-joined output was the second invented format |
 | `config/llama-cpp-pin.json` | **new**, C6 |
 | `backend/utilities/model_runtime.py` | **new**, C7 and C8 |
 | `.github/actions/model-server/action.yml` | ten inputs to four; new `id: model` step; the key at `:93`; the install and download step; the verify body; the start step; the health step. C9 |
 | `.github/workflows/digest.yml` | `:95-101` delete 7 job outputs; `:172-178` delete the `models` step whole; **`:195`** the pin call becomes `model_runtime.py print-pinned-build`; **`:546` add `id: model_server`**; `:550-552` delete; **`:553` KEEP, it is `llama_cpp_build`**; `:554-557` delete; `:583` reads `${{ steps.model_server.outputs.weights_path }}`; `:604` takes the same value through `env:` and reads `"$WEIGHTS_PATH"` in the body |
 | `.github/workflows/llm-council.yml` | `:77-83` delete 7 job outputs; `:168-171` delete the `models` step; **`:179`** the pin call; `:311-313` delete; **`:314` KEEP**; `:315-318` delete. No `id:` needed - the file holds no `backend/models` literal |
 | `.github/workflows/validate.yml` | `:100-102` and `:104-110` delete; **`:99`, `:103`, `:111` KEEP** - `:270` needs the models file, `:367` the alias, `:284` the key; **`:138`** the pin call; `:294-308` the download step becomes two `model_runtime.py` calls with `CONFIG_ROOT: backend/var/candidate-config`; **`:314-333` the verify step as ONE unit** - `:320` defines `WEIGHTS` and `:321`/`:325` read it, so deleting `:320` alone leaves an unbound variable under `set -u`; `:335-337` and `:394-399` read `weights_path`; `:367-368` alias paste moves to `env:` |
 | `.github/workflows/idhazh-pipeline-tests.yaml` | `:165` the pin call; `:167` the cache key; `:172-182` the download step; **`:190-204` the verify step as one unit** - `:196` inline Python, `:201` paste and `:202-204` draft block all go; `:245-247` and `:323-327` read `weights_path`; `:270-274` and `:350-354` inline Python become `candidate_id` |
 | `.github/workflows/measure.yml` | **two places only**: `:125-127`, the pin copy, repointed at `config/llama-cpp-pin.json`; and the one `start-llama-server.sh` call, which becomes `model_runtime.py start-server`. **Nothing else in this file** |
 | `backend/utilities/runtime_sweep.py` | its `start-llama-server.sh` call becomes a `model_runtime.py start-server` call |
 | `backend/tests/workflows/_harness.py` | four `WEIGHTS_CHECKS` entries go; `DRAFT_REF_OUTPUTS` at `:329-334` goes; `WEIGHTS_CACHE_SUFFIX` at `:357` becomes `"v5"`; the script-name constants for the four deleted scripts go. **Not delete-only** |
 | `backend/tests/workflows/test_weights_and_model_refs.py`, `test_pinned_versions.py`, `test_model_server_jobs.py` | the three tests that name the deleted scripts move to the new verbs. `test_pinned_versions.py`'s caller discovery reads `run:` bodies for the shared script names, so its constant changes and its assertions do not |
 | `docs/reference/ci-model-runtime.md`, `docs/architecture/summarize/model-boundary.md` | section 8 |

- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, and `ruff` plus `mypy` over the new module; CI - full suite; **plus the three dispatches in section 7.** `shellcheck` no longer runs on the four deleted scripts and that is the point.
- **Oracle:** **the paste rule** (C13). It fails today on 8 sites, and row 3 removes all 8 by removing their producers. Siblings: the C14 inventory drops from six names to two, which fails today at six; and a fixture pair differing only in one companion digest renders two different cache keys, which fails today because `action.yml:93` names no companion. **What it cannot settle:** whether a real runner downloads the right bytes and serves them. Only the dispatches settle that, and the N=2 dispatch is the only thing that ever executes the multi-file path. ESCALATE triggers 1, 2, 3, 4, 6 and 7 apply.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The first commit is tests only and lands RED.** Without that order a worker deletes the workflow verify step as redundant and every local gate stays green | Fowler |
 | 2 | **Both cache keys move in the same commit.** `action.yml:93` spells two inputs this row deletes, and a composite action resolves a deleted input to empty - the key would become `llm---<build>-v4`. And no ordering of two commits lets the closing dispatches share a key | Fowler |
 | 3 | The verify is a separate verb in a step with **no `if:`**. The download runs behind `cache-hit != 'true'` | Carmack |
 | 4 | The download's own digest check is an **early exit**, named as one, not half of the control | Carmack |
 | 5 | **`urllib.request` with a small retry, not a `curl` subprocess.** Guardrail #8 asks for a mature library over a custom build; shelling to a binary is neither, and `fetch.py` already reads every page this project fetches through `urllib`. The lost `--continue-at -` resume is named where the downloader is written | Owner ruling, 2026-09-22 |
 | 6 | Downloads stream to `<final>.part` and `os.replace` only after the digest passes. `curl -o` wrote straight to the destination, so a killed job left a half file under the cache key | Carmack |
 | 7 | The pin becomes `config/llama-cpp-pin.json`. **It owes no schema** - the owner ruling of 2026-09-21 exempts a configuration file this project authors | Fowler |
 | 8 | **`server_argv` is called in process.** `llama_argv.py` and its NUL-joined file go. That format existed only so a shell could reach a Python answer | Owner ruling, 2026-09-22 |
 | 9 | The `idhazh` import lives **inside** `start-server`, never at module scope, so the install and download verbs keep working in a job that has not installed the package. A test asserts it | Carmack |
 | 10 | The action **computes** its key, alias and weights path in one new first step, capturing then appending | Carmack and Fowler |
 | 11 | The action gains an `outputs:` block and `digest.yml`'s call gains an `id:` | Carmack |
 | 12 | The verify step declares `CONFIG_ROOT` in its own `env:`. It is a separate step and inherits nothing | Carmack |
 | 13 | **`WEIGHTS_CHECKS` shrinks to four and the closed-world equality stays an equality.** Discovery still finds eight because the download still reaches `huggingface.co`; the four converted jobs are derived at assertion time | Fowler |
 | 14 | `measure.yml` is edited in **two places and no more**. Its four inline arms stay out | Carmack |
 | 15 | The paste rule shipped here is the **scoped** one. The repository-wide rule is plan 46's row | Andre proposed; Fowler ruled on where it lands |
 | 16 | `jq` leaves the model path but stays in the action's health check. Converting that is not this row's business | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep `fetch-model-runtime.sh` and have it loop rows the reader prints | It invents a data format so a shell can do what Python already does better - and `measure_llm.py:156-195` already downloads with a `.part` file, a digest check and a skip-if-correct that the shell version has never had | A third invented format, in the plan named after deleting them | Owner |
 | 2 | Keep `curl` as a subprocess | It is a custom build wearing a binary. Guardrail #8 asks for a library | Nothing saved; the resume flag, which the `.part` shape makes unreachable anyway | Owner |
 | 3 | Keep the pin as a shell file and parse it from Python | A shell-variable parser written to read a file we control | About 20 lines of parser, and a file format with one producer and one consumer that is not JSON for no reason | Fowler |
 | 4 | Split the key change into its own row | The action's key spells inputs this row deletes, so the split produces `llm---<build>-v4` for one commit, and no ordering lets the dispatches share a key | A guard test red between two commits, which is a test saying those commits are one change | Fowler |
 | 5 | Drop the `-v5` suffix | Unnecessary only for changes the digest can see. Three it cannot: an entry already poisoned, a llama.cpp release re-uploaded under one tag, and a runtime-install change altering `backend/bin`, which is in `path:` and in no key component | One character, against `gh cache delete` needing a permission and leaving no record in git | Carmack |
 | 6 | Take `measure.yml`'s four inline arms here | Four blocks in the largest pull request in the plan, none of which reaches the shared download, in a file plan 46 owns in two rows | Its own row in plan 46, priced in the scope-out table | Fowler |
 | 7 | Leave `start-llama-server.sh` alone and do only the download | It keeps the NUL-joined argv file - one of the two invented formats - inside the plan that exists to delete them | Two small diffs saved, in `measure.yml` and `runtime_sweep.py` | Owner |

## Section 5 - Rows 4 and 5 - The case runner and the sampler

These two run together. They are disjoint: one owns `idhazh-pipeline-tests.yaml`, the other `digest.yml`.

### Row 4 - The pipeline-test case runner becomes Python

- **Scope:** Replace `run-pipeline-test-case.sh` with `backend/utilities/pipeline_test_case.py`.
- **Files touched:** `.github/scripts/run-pipeline-test-case.sh` (delete), `.github/workflows/idhazh-pipeline-tests.yaml` (three call sites), `backend/utilities/pipeline_test_case.py` (new), `backend/tests/workflows/test_pipeline_tests_workflow.py`, `backend/tests/workflows/_harness.py` (the script-name constant).
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows/test_pipeline_tests_workflow.py -q`; CI - full suite. No dispatch: the workflow that runs it is the one row 3's dispatches already exercise.
- **Oracle:** the C14 inventory drops from two names to... two - **this row does not change it, because the inventory counts only the scripts row 6 holds by then.** The failing check this row owns is narrower: **exit code 2 for a missing case directory and for a missing plan**, driven from a fixture tree, asserted against the workflow's own conditional. **What it cannot settle:** whether a real case run produces the same output as before, which the next pipeline-tests dispatch shows.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Exit code 2 is preserved** for a missing case directory and a missing plan. The workflow distinguishes it from a pipeline failure | Fowler |
 | 2 | The `python -m idhazh work` call stays a subprocess rather than an in-process call. The case is meant to run the pipeline the way a shard does, and a shard is a process | Carmack |
 | 3 | The elapsed-seconds line it prints stays, in the same words. It is read by a person scanning a run log, not by a program | Reader |
 | 4 | This row runs after row 3 because both edit `idhazh-pipeline-tests.yaml` | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Fold it into `model_runtime.py` | That module answers what a runner needs to serve a model. Running a pipeline case is a different question | One file with two answers | Fowler |
 | 2 | Call `idhazh.work` in process | A case is meant to run the way a shard runs, and a shard is a process with its own memory | A measurement that no longer matches what it measures | Carmack |

### Row 5 - The memory sampler joins the one that already exists

- **Scope:** Replace `sample-rss.sh` with `backend/utilities/memory_sampler.py`, sharing the `/proc` read that `runtime_sweep.py` already has.
- **Files touched:** `.github/scripts/sample-rss.sh` (delete), `.github/workflows/digest.yml` (`:627-629`), `backend/utilities/memory_sampler.py` (new), `backend/utilities/runtime_sweep.py`, `backend/tests/workflows/_harness.py` (the script-name constant).
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'sampler or sweep' -q`; CI - full suite.
- **Oracle:** the sampler, driven against a short-lived process in a fixture, writes one record per process per sample and **outlives the process it watches** - it must still be running when the target dies, and must stop after. **This fails today only in the sense that the shell version is not under test at all**, which is itself the finding: 108 lines of sampling logic with no test. **What it cannot settle:** whether the numbers match the shell version's on a real runner. They are the same `/proc` fields read the same way, and a side-by-side is not worth a digest run.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **This is a merge, not a port.** `runtime_sweep.py:294` already reads `VmRSS:` and `VmHWM:` and `:529` already starts a thread called `sample_rss`. The shared read moves into the new module and both call it | Carmack |
 | 2 | It is still a **separate process**, backgrounded with `subprocess.Popen(..., start_new_session=True)` and a pid file. It has to outlive the server it watches, and the job that starts it does other work | Carmack |
 | 3 | **The per-process rows stop being a `.tsv` and become JSON**, matching every other telemetry record (CLAUDE.md section 1b). No schema is owed: it is a run artifact, not a persisted payload a later run reads | Fowler |
 | 4 | The two marks it takes - for python as well as for llama-server - are kept, with the reason the script's header gives: llama-server is not the whole job | Carmack |
 | 5 | This row runs after row 3 because both edit `runtime_sweep.py` | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Make it a thread inside the job's main Python process | It must outlive a process that job starts and stops, and a thread dies with its interpreter | A sampler that stops recording exactly when the interesting part happens | Carmack |
 | 2 | Keep the `.tsv` | It is an invented format with one producer and one reader, and this plan is named after deleting those | Nothing saved | Fowler |
 | 3 | Delete the sampler entirely and rely on the sweep's thread | The sweep runs on a bench dispatch; this one runs on the daily digest, which is where the 16 GB ceiling actually binds | The only memory record the production run produces | Carmack |

## Section 6 - Row 6 - The last two scripts go

- **Status: BLOCKED on plan 46.** It is a row and not a scope-out line so the plan cannot close while 483 lines of shell survive.
- **Scope:** Replace `.github/scripts/commit-and-push.sh` (436 lines) and `take-state-from-the-tip.sh` (47) with Python, and delete `.github/scripts/`.
- **The condition that opens it:** plan 46's Reckoner reads all-DONE. Check it, do not assume it.
- **What the worker does first, before any code:** re-read both scripts on `main`. **Plan 46 is rewriting parts of `commit-and-push.sh` across seven waves, so the 436 lines this row was sized against will not be the 436 lines it finds.** Re-take the reading and re-price the row; if it has grown a capability plan 46 added, that capability is in scope and its cost goes in this row's table before dispatch.
- **Files touched:** the two scripts, their eight call sites across `backfill.yml`, `digest.yml`, `llm-council.yml`, `measure.yml` and `validate.yml`, `backend/tests/workflows/_harness.py`, and the four test modules that name them.
- **Acceptance gates:** to be set when the row is unblocked and re-measured. **At minimum: one real dispatch that pushes, and one that races a concurrent push and rebases**, because the retry-under-collision path is the whole of what the script does and no test exercises it.
- **Oracle:** the C14 inventory test asserts `.github/scripts/` is **gone**. It fails until this row lands.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | It waits rather than rebasing. A 436-line port cannot be reconciled with seven waves of edits to the same file; every other row in this plan rebases under plan 46, and this one does not | Fowler |
 | 2 | ESCALATE trigger 7 stops any other row reaching into these two files early | Fowler |
 | 3 | The row is re-measured at dispatch, not read off this page. Two claims about the repository went stale between writing and reading in this plan's own history | Fowler |
 | 4 | `$EPOCHREALTIME` and `mapfile` are the two shell features the port has to answer for. `time.monotonic()` and a list replace them, and the deadline semantics are what the tests must pin | Carmack |
 | 5 | `git` stays a subprocess. It is a program with a stable interface, not a format this project invented, and no Python git library is declared | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Do it now, rebasing under plan 46 | Seven waves of edits to the same 436-line file. Every merge is a hand resolution of a program being rewritten twice | A resolution nobody reviewed, on the step that pushes to `main` | Fowler |
 | 2 | Drop it from the plan and file it separately | A plan that deletes eight of ten scripts and writes down nothing about the other two leaves a reader thinking the job is done | 483 lines of shell that nobody is tracking | Owner ruling, 2026-09-22 |
 | 3 | Add a Python git library | Nothing declares one, and `git` is a stable command-line interface this project already drives from Python in four utilities | A dependency, its install time and its shipped bytes, for a subprocess that works | Carmack |

## Section 7 - The three dispatches, after row 3's second commit

Four things a dispatch must prove that nothing cheaper can: the download fetches **every** declared file on a real runner and each one's digest and size pass; the verify runs on a **restored** entry; the key Actions resolves is the key the reader renders; and the action's key equals the inline caller's.

| # | Dispatch | Workflow, branch, inputs | What it proves | When it finishes | Cost |
| --- | --- | --- | --- | --- | --- |
| D1 | **the multi-file path** | `idhazh-pipeline-tests.yaml`, PR-B's branch, `candidate_models_file: config/models/gemma-4-e4b-qat.json` | the download actually loops; the per-file digest and size on a companion; the count check; the `backend/var/candidate-config` root; the landed path; the new server launch | **read the log for two downloads and two digest passes.** One means it did not loop. Cancel once the verify is green - the three cases prove nothing this plan needs | one cold 4.28 GB fetch. `permissions: contents: read`, so it cannot push |
| D2 | **the production key** | same workflow, same branch, **after D1 finishes**, `candidate_models_file` empty | the production key string resolves with no literal `${{` left in it, and **the entry saves under it** | read the resolved key off the cache step and compare it character-for-character with the action's. Cancel at the verify | one cold 5.68 GB fetch. This entry is what `digest.yml` hits on its next cron |
| D3 | **the hit** | `llm-council.yml`, same branch, **after D2**, `date` empty | the no-`if:` verify over **restored** bytes; cross-caller key equality - the hit itself is the proof; and the server starting from Python | if it misses, that is a finding rather than a re-run: read the two resolved keys off the two logs, fix the fold, re-run D3 only | no weights download. **It pushes council verdicts to the branch - drop that commit with a revert before merge, never a rewind** |

**D1 and D2 cannot run concurrently.** Both are `idhazh-pipeline-tests.yaml`, whose `concurrency: group: pipeline-tests, cancel-in-progress: false` puts the second in `pending`. Serial by the platform.

**Neither covers the other.** The live pointer declares no companion, so an empty dispatch exercises a one-file download indistinguishable from today's - the arity this plan exists to unweld would ship unexecuted. A gemma dispatch writes a key nothing else will hit.

**D3's timing.** Its cron is `0 22 * * *`, group `llm-council`, `cancel-in-progress: false` - a dispatch **queues behind** a running cron rather than cancelling it. Start it before 21:00 UTC or after the 22:00 run finishes. Be present when it lands, because of the push.

**D1 is guaranteed to miss** only because both key spellings move in one commit. `digest.yml` crons five times a day on `main`, refreshing the `-v4` entry, and Actions restores from the current branch **and** the default branch.

## Section 8 - The docs

| Page | Section | What it becomes | Row |
| --- | --- | --- | --- |
| `docs/reference/ci-model-runtime.md` | `### Where the three values are written, and how many places that still is` (`:25`) | `### Where the model file is read, and how many places that is` - one place. **The stale `LLAMA_SCRIPT_CALLERS` citation at `:51` is deleted**; that symbol exists nowhere in the repository | 3 |
| `docs/reference/ci-model-runtime.md` | `### What the cache key holds` (`:59`) | the literal becomes `llm-<digest over every declared file>-<build>-v5`. **Plus the one `## Design rationale` entry this plan owes** | 3 |
| `docs/reference/ci-model-runtime.md` | `## Every download fails loudly, and every weight is checked` (`:113`) and `### The digest settles the bytes, and the declared size settles the document` (`:156`) | the four-row "Digest read from" table collapses to one row; the declared-size check becomes shared; **the production entry size is corrected to 5.68 GB**, with the note that the 57 to 338 s download and 38 to 95 s restore figures were taken on the 4.28 GB gemma arm and scale by about 1.33 | 3 |
| `docs/reference/ci-model-runtime.md` | `### Every download names a commit` (`:226`) | "one bare word" becomes the closed grammar row 1 ships | 3 |
| `docs/architecture/summarize/model-boundary.md` | **delete `## What is wrong with the boundary today` (`:504-544`)**; gain the declaration contract and the one-companion refusal | six paragraphs; four are dated status prose about work already done. **The two that survive become rows in `## Which side each fact lives on` (`:88`)**: `:522` "The entry declares its architecture..." and `:533` "The entry names the weights it was set for...". Folding creates no duplicate | 3 |

**The page pays the split test before it is added to** (AGENTS.md). `model-boundary.md` is 555 lines and its own `:542` says it "describes the boundary rather than tracking work", so the status section is the cut and one addition buys exactly that one cut. `ci-model-runtime.md` passes without a cut. **Run `python backend/utilities/doc_load.py` before and after.**

**One `## Design rationale` entry, on `ci-model-runtime.md` under `### What the cache key holds`: the cache key is computed inside the action from the model file, not passed in by the caller.** It earns one because a real alternative is what every caller does today, reversing it costs every caller a full re-download, and it crosses the workflow-to-action boundary. No other decision here earns one.

## Section 9 - What this plan costs, all of it

| Arm | Key expression after | Jobs missing together | Caused by | Bytes | Seconds |
| --- | --- | --- | --- | --- | --- |
| Production - the action, called by `digest.yml/work` and `llm-council.yml/judge` | `llm-<64hex>-<build>-v5` | up to 8, plus council's matrix | **row 3** | 5.68 GB plus `backend/bin` | download estimated 100 s median, 76 to 449 s, replacing a roughly 60 s restore - **about +40 s median** |
| Pipeline-tests | the same string when the input is empty | 1 | **row 3** | same | same. It shares production's entry, so it hits once that is warm |
| Qualify - `validate.yml:284` | expression unchanged, **value** changes | up to 8 | **row 1** | 4.22 to 6.64 GB per candidate | same order |
| Bench - `measure.yml:268`, `:549`, `:878` | expression unchanged, **value** changes | 1 each | **row 1** | per candidate | same order |

**Rows 1 and 3 invalidate disjoint sets**, so merging them on different days costs nothing extra. The seconds are an estimate scaled from the measured 4.28 GB figures by 5.68/4.28; **what settles it is the first cold `work` job's step timing after PR-B merges.**

**Eviction is certain and is the desired outcome.** Old production (5.68 GB) plus new (5.68) plus one gemma qualify entry (4.28) is 15.64 GB against a 10 GB allowance; GitHub evicts least-recently-used, and the old entry is the least recently used the moment PR-B merges.

**None of this can fail a run.** The two numbers that fail a run are the 6 h job cap and the 1 GB site, and neither is touched. `shard_timeout_minutes` is 200 against a worst-case cold fetch of about 7.5 min. The production digest is 164 to 184 min against 360. The 10 GB allowance is GitHub's and it evicts rather than errors.

**The one runtime risk this plan adds, named:** the download moves from `curl` to `urllib`. `curl --retry 3 --retry-all-errors` is battle-tested against flaky hub responses and the replacement is not. C8's retry rule is the mitigation, D1 and D2 are the proof, and the revert is one commit because the old script is one `git revert` away for as long as the branch exists.

## See also

- [`20260921-42-lane-b-workflows-plan.md`](20260921-42-lane-b-workflows-plan.md) - the parent, whose rows 1 to 6 landed and whose rows 7 to 11 this plan carries.
- [`20260922-46-no-file-has-two-writers-plan.md`](20260922-46-no-file-has-two-writers-plan.md) - in flight. Section 1c is the interlock; row 6 waits on it, and three of this plan's scope-out lines become rows there.
- [`20260922-47-the-pipeline-stops-naming-a-server-plan.md`](20260922-47-the-pipeline-stops-naming-a-server-plan.md) - shares one docstring in `backend/idhazh/llm/server.py`. Whoever lands second rebases one hunk.
- [`../docs/reference/ci-model-runtime.md`](../docs/reference/ci-model-runtime.md) - the page that owns the model path and the cache key.
- [`../docs/architecture/summarize/model-boundary.md`](../docs/architecture/summarize/model-boundary.md) - the page that owns what the model file declares.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed.



