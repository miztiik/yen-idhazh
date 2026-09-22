# The model file is the fetch interface

**Last Updated**: 2026-09-22

**Level**: 4, and row 2 is why. It rewrites the download path the daily run depends on, and only a live dispatch proves it, so a revert would land after a failed publish - CLAUDE.md section 6's Level-4 test. Row 1 is Level 3: `one_bare_word` at `backend/utilities/model_refs.py:41` refuses whitespace and nothing else, while **13 model-file values are pasted textually into `run:` bodies across four workflows**, where a value spelling `$(id)` executes. That is this repository's own env-not-paste rule failing on a maintainer-written config file. **It is not a Guardrail #11 question** - Guardrail #11 is about fetched web text, and a model file is neither fetched nor web. Row 3 is Level 3.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 1 row in flight - one, because row 2 imports verbs row 1 declares and rows 2 and 3 are two commits of one pull request, so a second slot can never fill (section 1c proves it); consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | One JSON file says which bytes a model needs. Its contents still travel through a Python printer, a job output, a composite-action input and an environment variable before a `curl` sees them - four hops, and the arity is welded at two files, so a model shipping three cannot be described. `model_refs.py:41` refuses whitespace only, so `../../x.gguf`, `x$(id).gguf` and a branch name in place of a commit all pass, and 13 of those values are pasted into `run:` bodies where the Actions engine substitutes before bash parses. The production cache key at `.github/actions/model-server/action.yml:93` names no companion at all, so a companion change that keeps the weights filename produces a hit missing a declared file - and then every re-run fails identically until a person bumps the key by hand. The key ends `-v4`, which is that bump already paid four times. |
| The rule | **The model json is the interface. It names every file the model needs and where each comes from; one reader turns that into downloads, checks, a landed path and a cache key. Everything else that relays a model fact through a workflow is deleted.** Owner ruling 2026-09-21. |
| The second rule | **A value this project computes is published, never composed a second time downstream.** `backend/models/<file>` is composed at nine places today. After row 2 the printer composes it once and everybody else reads it. |
| The measure | **Hops from the model file to the download, and places a model fact is spelled.** Hops 4 -> 1. Spellings of the field names between config and `curl`: 5 -> 2. |
| Hard scope - in | Give the printer a `files` verb emitting the whole file set with its landed path, a `cache-key` verb over those same rows, a `weights_path` key on the two existing verbs, and a field grammar that refuses every value a shell or a `run:` body could misread. Make the fetch script read a config root and loop. Make the composite action compute the key and the alias itself, so its ten inputs become four. Delete the four inline Python programs and the six relay blocks in the four callers. |
| Hard scope - out | See the table below. Every line there is a dated decision with a price, never a law (CLAUDE.md section 0d). |
| Supersedes | Plan 42 rows 7 to 11, which are `COLLAPSED` in that plan's Reckoner. |
| Assumes | **Plan 41 merged as #1036 and #1039.** `COMPANION_FIELDS`, `_companions()` and the companion-joining `_cache_key` are on `main`. No plan-41 coupling remains, and this plan's earlier section on it is deleted. |
| ESCALATE triggers | (1) **Row 2's first commit is the paste-rule assertion and the two new digest clauses, landing RED against the unchanged tree.** If a commit moves the fetch before that test exists, stop - section 1d C8 says why the order is the control. (2) Row 2 must leave a digest check that runs on a cache hit. The fetch script runs behind `cache-hit != 'true'`, so a check living only inside the script never sees a restored entry. (3) If any step between the cache restore and the verify acquires `continue-on-error: true`, or the cache step is split into `actions/cache/restore` plus a save with `if: always()`, stop. Both make `actions/cache`'s `post-if: success()` untrue, which is the only thing stopping a failed job writing a bad entry (C7). (4) If the `cache-key` verb can print an empty string, stop: `llm--<build>-v5` is one key every model shares, which is worse than the wedge being fixed. (5) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | **Two pull requests, three commits, strictly sequential.** PR-A is the printer and shares no file with any plan in flight. PR-B is the fetch interface and the key, and row 3's file set is a strict subset of row 2's. Fowler ruled the grouping and the level; Carmack the fetch path, the cache and the dispatch sequence; Andre the grammar and the paste surface. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1 - PR-B depends on PR-A and rows 2 and 3 are two commits of one pull request, so a second slot can never fill.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Row 5 of the draft: cutting `backend/tests/workflows/_harness.py` to names more than one module reads** | The module stays 2,248 lines with 241 top-level names, and **a one-file change still has to touch 143 of them** - 10 that nothing imports plus 133 that exactly one module imports. Twenty-one consumer modules pay that read every time a workflow test is added, and the tax is paid per future change, not once | **Plan 46's Reckoner reads all-DONE, and this plan's row 2 has merged.** Plan 46 writes `_harness.py`, `test_triggers.py`, `test_staged_paths.py` and `test_daily_commit_steps.py` across seven waves; a 133-name move landed underneath it conflicts on every merge. Row 2 rewrites `test_weights_and_model_refs.py` and `test_pinned_versions.py`, where about 22 of those names belong. Then re-run the census - never read a recorded table - and run it as its own plan. **The draft's "nine of 45 orphans are internal" is wrong: it is 35 of 45, so only 10 deletions exist and the row is almost entirely a move.** Fowler |
| **Refusing `needs.*.outputs.*` inside any `run:` body, repository-wide** | **28** job-output expressions keep reaching a shell through textual substitution rather than `env:` - `digest.yml` 15, `validate.yml` 8, `measure.yml` 5. A value spelling `$(id)` executes, and nothing mechanical refuses a 29th. Five of the 13 model-file pastes stay in that state, all of them `measure.yml`'s | **It is plan 46's row, not this one's.** Plan 46 already owns `test_triggers.py`, `digest.yml`, `measure.yml` and `validate.yml`, and holds all four in its group A. Added there it inherits one file list, one worktree and one merge order instead of fighting them. The owner triggers it by adding the row to plan 46's Reckoner. **What this plan takes free instead**, inside row 2: the same rule scoped to jobs reaching the action or the script, which fails today on 8 of the 13 and whose 8 producers row 2 deletes. Andre proposed the general rule and withdrew his own scope-out line; Fowler ruled on where it lands |
| **Converting `measure.yml`'s four inline weights downloads to the shared fetch** | Four blocks at `:318`, `:572`, `:901` and `:1136` keep their own spelling of repo, revision and filename, and `WEIGHTS_CHECKS` survives with four entries instead of dying | They reach neither the composite action nor the fetch script, and `measure.yml` is plan 46's file in two of its rows. **This is also why `WEIGHTS_CHECKS` shrinks to four rather than dying whole** - the draft's claim that it dies is false for half the list. Its own closing act is deleting that constant. Fowler |
| **Splitting the runtime binary onto its own cache key** | A llama.cpp pin bump keeps discarding 4.28 GB of unchanged weights | **Refused on arithmetic the draft got backwards.** A cold download is 57 to 338 s, median about 75, and the restore it replaces is 38 to 95 s - so the marginal cost is about **30 s at the median and can be negative** (`docs/reference/benchmarks/what-a-bench-dispatch-costs.md`, eight `runtime` jobs, 2026-09-14 to 2026-09-16). A pin bump happens a couple of times a year. Against that, `install-llama-runtime.sh` has one caller and `measure.yml` carries four inline copies of it, so the split needs a second skip condition at each. Carmack |
| **Declaring the field grammar in `backend/idhazh/contracts/knobs/models.py`** | The grammar is declared in `model_refs.py` and `measure_llm.py` holds a second copy of three patterns, gated by an equality test | The right long-run home - one declaration, three importers - and it needs `utilities` to become an installed package or every call site to move to `-m`. `pyproject.toml` declares `packages = ["backend/idhazh"]` only, so `utilities` is importable today purely through hatchling's editable `.pth`. **What brings it in:** a packaging row that makes `utilities` a declared package, after which the two copies collapse to one import. Carmack and Fowler |
| **Making `LLAMA_PORT`, `LLAMA_HOST` or any other process-boundary value part of this** | Nothing | **Plan 47 owns it**, and after `measure.yml` and `runtime_sweep.py` leave this plan, plan 47's claim that it shares no file with plan 44 is true. Fowler |

### What a change costs today

Measured on `origin/main`, 2026-09-22, by reading the files. **Every line number in the draft's equivalent table was stale; these were re-taken.**

| Reading | Value | Where |
| --- | --- | --- |
| Hops from the model file to the download | **4** - printer, job output, action input, environment | `model_refs.py` -> `$GITHUB_OUTPUT` -> `action.yml:107-115` -> `fetch-model-runtime.sh:30-32` |
| Places a model-file field name is spelled between config and a `curl` | **5** | `model_refs.py`'s `draft_*` output keys, `digest.yml:95-101`, `action.yml:28-47`, `action.yml:107-115`, `fetch-model-runtime.sh:30-32` |
| Files a model file can declare | **exactly 2**, welded | `COMPANION_FIELDS` at `model_refs.py:27`, `_draft_rows` at `:68`, `_cache_key` at `:86` |
| Composite action inputs | **10, of which 4 are draft** | `action.yml:12-47` |
| What `one_bare_word` refuses | **whitespace and empty only** | `model_refs.py:41`. Admitted on a direct call: `../../x.gguf`, `x.gguf$(id)`, `` x.gguf`id` ``, `a"b`, `a;b`, `a\|b`, `$(curl${IFS}evil)`, `%2e%2e%2fx`, `/etc/passwd`, `..`, `.hidden`, `x.txt` |
| Model-file values pasted into a `run:` body, where `${{ }}` substitutes before bash parses | **13**, across 4 workflows - `digest.yml` 1, `idhazh-pipeline-tests.yaml` 1, `validate.yml` 6, `measure.yml` 5 | measured with `_harness._load_workflows` over every `run:` body |
| Of those 13, how many row 2 removes | **8** - every one in a job reaching the action or the script | `measure.yml`'s 5 are out of scope by the table above |
| Whether the weights `file` has any segment rule | **none, in either layer** | `ModelRef.file` is `Field(min_length=1)`; `CompanionFile` validates companions only, in Pydantic, which never runs on the shell path because `model_refs.py` reads raw JSON |
| Whether `byte_count` is checked at all before printing | **no** | `model_refs.py:151` prints it straight. A newline in that value writes extra `key=value` lines into `$GITHUB_OUTPUT` |
| Whether every companion's `sha256` is checked | **no** - `_draft_rows` checks the first companion only, while `_cache_key` reads every one | `model_refs.py:68-84` against `:86-97` |
| Key length if the existing hyphen-join met seven files | **519 characters**, past GitHub's 512-character cap | `_cache_key` at `model_refs.py:97` |
| Companion files the production cache key names | **0** | `action.yml:93`, keyed on weights file, weights revision and build |
| Times that key has been bumped by hand | **4** - it ends `-v4` | same line |
| Second hand-copy of that key format | **1**, also ending `-v4`, invisible to the guarding test because that test scopes its closed world to the action's callers | `idhazh-pipeline-tests.yaml:167` against `test_weights_and_model_refs.py:344` |
| Which arms are already protected | the benchmark and qualification arms - they key on `candidate_cache_key`, which is the printer's key and already joins every companion digest | `measure.yml:268`, `:549`, `:878`; `validate.yml:284`. **Production is the only uncovered one** |
| Inline Python programs walking a model file inside a workflow or action | **6** | `action.yml:136`, `:183`; `idhazh-pipeline-tests.yaml:196`, `:274`, `:354`; `measure.yml:1151` |
| Places `backend/models/<file>` is composed by hand | **9** | `action.yml:147`, `fetch-model-runtime.sh:38`, `:42`, `:51`, `digest.yml:583`, `:604`, `validate.yml:320`, `:337`, `:399`, plus `idhazh-pipeline-tests.yaml:201`, `:247`, `:327` |
| Whether `actions/cache@v6` saves a cache entry when the job failed | **no.** Its manifest declares `post-if: "success()"`. The `save-always` input is inert and carries a deprecation message | the version history is the tell: v4.0.0 had `post-if: success() \|\| ...save-always`, v4.2.0 dropped it |
| The door that IS open | a fetch loop that exits 0 having downloaded fewer files than the model declares. `post-if` cannot see that | closed by C5 step 9 and by the no-`if:` verify |
| A cold weights fetch, against the restore it replaces | download **57 to 338 s, median about 75**; restore **38 to 95 s**. Marginal cost about **30 s at the median**, and it can be negative | `docs/reference/benchmarks/what-a-bench-dispatch-costs.md`, eight `runtime` jobs, 4.28 GB, 2026-09-14 to 2026-09-16 |
| `_harness.py` census, re-taken | 2,248 lines, 241 top-level names, 45 with no importer of which **35 are used inside the module itself**, 133 with exactly one importer, 39 with two or three, 24 with four or more, 21 consumer modules | AST census over `backend/tests/**/*.py` |

## Section 0b - What this plan does, in one list

1. The printer learns the whole file set, its landed path and a fixed-width key over it, and refuses every value a shell or a `run:` body could misread.
2. The workflows read the model file instead of relaying it: the script loops, the action computes its own key and alias and drops to four inputs, and the six relay blocks and four inline Python programs go.
3. The production cache key names the set the model declares, in both places that spell it.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The printer learns the whole file set, and the grammar closes | - | A | PENDING | - | - | - |
| 2 | The workflows read the model file instead of relaying it | 1 | B | PENDING | - | - | - |
| 3 | The cache names the set, in both places that spell it | 2 | B | PENDING | - | - | - |
| 4 | The benchmark arms learn the server died, and the repeat count is config | - | C | DONE | p42p5 | - | P5 |
| 5 | The harness keeps only what more than one module reads | - | D | COLLAPSED | - | - | - |

**Row 4 landed ahead of the draft's sequence and nothing was owed for it.** `runtime_sweep.py:328` carries `START_GRACE_SECONDS: Final = 2.0`, used at `:348`; `backend/idhazh/contracts/knobs/bench.py:47` carries `repeats`. The draft claimed this row was coupled to row 3 through the `gguf_cache_hit` column. It is not: that value is a CLI argument (`runtime_sweep.py:727`, set at `measure.yml:607` and `:1138`) reporting whether the **bench** key hit, and the bench key already covers companions. No coupling, no shape question, and `runtime_sweep.py` leaves this plan.

**Row 5 is COLLAPSED into the first line of the scope-out table**, with its cost and the condition that brings it back. It serves no behavioural change here, it shares `_harness.py` with plan 46, and its `Depends-on` was file contention rather than logic. Fowler ruled; the user reverses it by moving that scope-out line into a row.

### Section 1a - The two pull requests and the files each owns

**Two pull requests never own one file, and that claim is at file level, not line level.**

| PR | Rows | Wave | Files it owns, exclusively |
| --- | --- | --- | --- |
| **PR-A - the printer** | 1 | 1, alone | `backend/utilities/model_refs.py`, `backend/tests/workflows/test_weights_and_model_refs.py`, `backend/tests/workflows/test_pipeline_tests_workflow.py`, `backend/idhazh/llm/server.py` (one docstring, `:437-439`) |
| **PR-B - the fetch interface and the cache** | 2, 3 | 2, alone | `.github/scripts/fetch-model-runtime.sh`, `.github/actions/model-server/action.yml`, `.github/workflows/digest.yml`, `llm-council.yml`, `validate.yml`, `idhazh-pipeline-tests.yaml`, `backend/tests/workflows/test_weights_and_model_refs.py`, `test_pinned_versions.py`, `backend/tests/workflows/_harness.py` (delete-only, four `WEIGHTS_CHECKS` entries), `docs/reference/ci-model-runtime.md`, `docs/architecture/summarize/model-boundary.md` |

**`measure.yml` and `backend/utilities/runtime_sweep.py` are in neither list.** Rows 2 and 3 reach neither: `measure.yml`'s four weights downloads are inline, and its three cache keys read `candidate_cache_key`, whose **value** changes when row 1 changes the key shape while its **expression** does not. Same for `validate.yml:284`. The draft named both files on a coupling that does not exist.

**PR-A shares no file with plan 45 or plan 46.** Neither names `model_refs.py`, `test_weights_and_model_refs.py`, `test_pipeline_tests_workflow.py` or `server.py`. It can start the hour the user authorizes.

### Section 1b - Why the pull requests fall where they do

| Question | Answer |
| --- | --- |
| Why row 1 runs alone | It is the grammar fix, it has unit oracles that fail on today's tree with no runner, and it shares no file with any plan in flight. Rows 2 and 3 close on a live dispatch. Merging them would put the grammar behind a runner queue and inside the largest pull request in the plan |
| Why rows 2 and 3 share a pull request | Row 3's file set is a **strict subset** of row 2's, and row 3 changes no Python at all because row 1 already shipped the `cache-key` verb. Two commits, never two pull requests |
| Why PR-B runs alone | After row 2 it owns every workflow file this plan touches. That is arithmetic, not churn avoidance |
| Why there is no third pull request | The draft proposed stranding `digest.yml`'s eight draft lines. `digest.yml` carries **17** model-relay lines, and rows `:583` and `:604` read a job output row 2 deletes the producer of - so stranding them leaves `LLAMA_WEIGHTS: backend/models/` and a `sha256sum` on a directory. The file is load-bearing in row 2, not a crumb |

### Section 1c - Readiness, computed rather than read off a letter

**A row is ready when every `Depends-on` is DONE and its `Files touched` list shares no entry with a row in flight.** The owner diffs those lists before each dispatch.

| At this point | Ready together | Held, and why |
| --- | --- | --- |
| Now | **row 1**, alone | row 2 needs the `files`, `cache-key` and `weights_path` contracts. Rows 4 and 5 are settled |
| Row 1 merged | **row 2**, then **row 3** in the same worktree | nothing else exists |
| Row 3 merged | nothing | the plan is closed |

**Peak workers: 1, and the pool is declared at 1 for that reason.** A pool of 2 would cost a second worktree, a second branch, a second brief and an orchestrator polling two settle scripts, and buy an idle slot. This repository has already measured the failure mode in the other direction: a plan run three-wide on rows that shared a surface produced a hand resolution at every merge after the first. **What would make this plan two wide is bringing row 5 back**, which needs plan 46 closed - the first line of the scope-out table.

### Section 1d - The one interlock with plan 46, and the ruling on it

Plan 46 is in flight with three worktrees cut (`p46a`, `p46b`, `p46f`). PR-B shares three files with it: `digest.yml` (six of plan 46's ten pull requests write it), `validate.yml` (its row 11, wave 4) and `_harness.py` (a group-A row in wave 1).

**Ruling: land PR-B when it is ready and let plan 46's branches merge `main` in.** PR-B's `_harness.py` hunk is four dictionary entries deleted at `:257-312`, textually far from plan 46's `COMMIT_REFRESH_PATHS` work, so that merge auto-resolves. Its `digest.yml` diff is about -15 net against plan 46's much larger ones. A small branch rebasing under a large one is the cheap direction; the reverse stalls a Level-4 fix behind a ten-pull-request plan's first wave. **The owner tells plan 46's owner the file list at PR-B's dispatch**, so a rebase is expected rather than discovered.

**`measure.yml` is not contested.** This plan has no claim on it.

## Section 1e - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent any shape below; it reads this section.** No persisted payload changes, so CLAUDE.md section 11 owes nothing - `gguf_cache_hit` appears in no file under `schemas/` and is a CLI argument, not a declared shape.

### C1 - What the printer publishes (row 1)

`backend/utilities/model_refs.py` keeps one question - which model files will a shell see, and is every field safe - at a new arity. It stays **stdlib-only and runnable by path**: `python3 backend/utilities/model_refs.py <verb>`. It imports nothing from `idhazh` and nothing from `utilities`.

**Four verbs. All four take `--config-root`, default `config`. `--repo-root` is deleted** - one uniform argument replaces two, and the script and the action both need to name a config tree that is not `config/`.

| Verb | Callers | What it prints |
| --- | --- | --- |
| `configured` | `.github/actions/model-server/action.yml` (new step) | `KEY=value` lines for the pointed-at entry |
| `candidate` | `idhazh-pipeline-tests.yaml:123`, `measure.yml:184`, `validate.yml:160` | `KEY=value` lines, prefixed, for a named models file |
| `files` | `.github/scripts/fetch-model-runtime.sh`, and the verify step in every caller | **TAB-separated rows**, one per file |
| `cache-key` | the cache step in `action.yml` and in `idhazh-pipeline-tests.yaml` | one line, `cache_key=<64 lowercase hex>` |

**`files` output, the contract the shell reads.** One row per file, weights first, then companions in declared order. TAB-separated, six columns, never a missing field.

| Column | Content | Absent optional |
| --- | --- | --- |
| 1 | `repo` | - |
| 2 | `revision` | - |
| 3 | `file` | - |
| 4 | `sha256` | - |
| 5 | `flag`, or empty | empty field, never a missing one |
| 6 | **the landed relative path** - `MODELS_DIR` plus the validated `file` | - |

**Column 6 is what removes the shell's composition.** `fetch-model-runtime.sh` writes it verbatim as the `-o` destination and composes no path of its own.

**The companion list is read from `companion_files` and from nothing else.** Zero committed `config/models/*.json` carries a `draft` key; the draft's dual-shape reader and its removal condition were both stale, and a `draft` arm would ship dead with its own removal condition already met. An entry with no `companion_files` prints exactly one row - which is the live pointer `config/models/qwen3.5-9b-q4km.json` today.

**Three keys are added to `configured` and `candidate`**, so nothing downstream composes a path or re-reads the model file:

| Key | Value | Who needed it |
| --- | --- | --- |
| `weights_path` | column 6 of the weights row | `LLAMA_WEIGHTS` at four sites, `--weights` at `validate.yml:399`, and the `sha256sum` at `digest.yml:604` |
| `cache_key` | the C4 digest | `action.yml:93` and `idhazh-pipeline-tests.yaml:167`. `candidate` already publishes it; `configured` gains it |
| `id` | the model alias | the two health checks that read it today with inline Python. `CANDIDATE_FIELDS` already carries `id`; `CONFIGURED_FIELDS` gains it |

**`_draft_rows` and every `draft_*` output key are deleted in row 1.** They are the only consumer-facing name in the module that describes one companion out of N, and the workflows that read them are all rewritten in row 2. Row 1 deleting them is what makes row 2's grep oracle possible.

**On a malformed entry the verb raises, prints the models file path, the dotted JSON location including the list index, the rule in plain words, and the offending value in `repr()`, and exits non-zero.** Not a skip: a skipped companion is a server that fails to start over a missing file, or one that starts and silently does nothing. Never print a regex.

```
config/models/gemma-4-e4b-qat.json: summarize.companion_files[0].file:
  not one path segment: '../../x.gguf'
config/models/qwen3.5-9b-q4km.json: summarize.revision:
  not a 40-character commit: 'main'
```

**`models_file` is published as the proved path, not the raw input** - `path.relative_to(root).as_posix()`. Today the object that was checked and the object that is published are two different objects.

### C2 - The grammar, and where it is declared (row 1)

**Declared in `model_refs.py` itself, with `re.compile` and nothing but stdlib `re`.** Not imported from `backend/utilities/measure_llm.py`, and not moved to a shared third module. Both of those break a job that has no install:

| Direction | What breaks | Where |
| --- | --- | --- |
| `model_refs.py` imports `measure_llm` | `from utilities.measure_llm import ...` resolves only because each caller ran `pip install -e .` and hatchling's editable `.pth` exposes all of `backend/`. `pyproject.toml` declares `packages = ["backend/idhazh"]`; `utilities` is not a declared package. Fixing it properly means `PYTHONPATH=backend python3 -m utilities.model_refs` at **six** invocation sites, two of them in files plan 46 owns - and the failure is invisible to every local gate, because pytest sets `pythonpath = ["backend"]` | `measure.yml:158-164` carries the written invariant, added after a dispatch died on `ModuleNotFoundError` |
| `measure_llm.py` imports a shared module | `measure_llm.py` runs **two** ways - by path at `measure.yml:376` in the `llama-bench` job, which has no `setup-python` and no install, and as `utilities.measure_llm` from `runtime_sweep.py:33` and the tests. No single plain import statement works in both | measured 2026-09-22 |

**The duplication is gated, so a reviewer does not have to catch it.** One contract-tier test in `backend/tests/workflows/test_weights_and_model_refs.py` - which already does `from utilities import model_refs` at `:12` - holds an **explicit** tuple `("REPO_RE", "REVISION_RE", "GGUF_RE")` and, for each name, asserts it exists on both modules, that `.pattern` is equal and that `.flags` is equal. Flags are not optional: `re.IGNORECASE` on one side is a second grammar sharing one pattern string. The tuple is explicit, never derived by intersecting the two modules - `sha256` is genuinely new here and a derived list would either fail on it or silently drop a name.

**The rules. Applied to every value the printer emits, weights and companion alike, at the one point that writes a row.**

| Field | Rule | State today |
| --- | --- | --- |
| `repo` | `^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$` | exists as `REPO_RE`, `measure_llm.py:28` |
| `revision` | `^[0-9a-f]{40}$` - a commit, never a branch name | exists as `REVISION_RE`, `measure_llm.py:32` |
| weights `file` | `^[A-Za-z0-9][A-Za-z0-9._-]*\.gguf$` - one segment, no `/`, no `\`, not `.`, not `..`, no leading dot, and percent-encoding cannot pass because `%` is outside the class | exists as `GGUF_RE`, `measure_llm.py:29`. **This is the live gap** |
| companion `file` | `^[A-Za-z0-9][A-Za-z0-9._-]*$` - the same segment rule, **without the suffix rule** | new. `CompanionFile` deliberately has no suffix rule because a companion may be a projector, an adapter or a vocoder; importing `GGUF_RE` for it would ship a second grammar for one field |
| `sha256`, weights and **every** companion | `^[0-9a-f]{64}$`, **required, no exception** | new. `_draft_rows` checks the first companion only while `_cache_key` reads every one |
| `byte_count` | optional; when present, `^[1-9][0-9]*$` on the stringified value | **no check at all today**, and a newline in it writes extra lines into `$GITHUB_OUTPUT` |
| `flag` | optional; `^--[a-z0-9-]+$` | new |
| `id` | the repository's slug shape, `^[a-z0-9]+(?:-[a-z0-9]+)*$` | new. It is pasted into a commit message and an artifact name |
| `quantisation` | `^[A-Za-z0-9_.-]+$` | new |
| the set | two entries resolving to one filename is refused | exists in `parse_model_refs`, `measure_llm.py:71-75` |
| **every emitted value, last** | printable ASCII, and none of `$ \` " ' ; \| & < > ( ) { }` or any newline | **the backstop, and the load-bearing row.** The rules above fix the fields that exist; this one refuses the field added in six months by default instead of admitting it by default |

**Why `sha256` is required is diagnosability, not integrity.** A blank expected digest makes `sha256sum --check` exit 1 with "no properly formatted checksum lines found", so the run fails loudly either way - but that message names a pipe, where the printer names the models file, the list index and the field. Stating it as a security argument invites the next person to read it as a bluff.

**Three Guardrail #11 citations are wrong and are corrected in the commit that touches each file.** `model_refs.py`'s module docstring at `:1-4` claims this is "where a value carrying a space, a quote or a newline stops" - `'a"b'.split() == ['a"b']`, so it does not stop a quote - and it cites a guardrail about fetched web text for a committed config file. `action.yml`'s comment above the fetch step carries the same citation (row 2 corrects it). The replacement sentence names what is true: these values are pasted into `run:` bodies where the Actions engine substitutes before bash parses, so they are refused here.

### C3 - The landed path, composed in exactly one place (rows 1, 2)

| Step | What it removes |
| --- | --- |
| `model_refs.py` declares `MODELS_DIR: Final = "backend/models"`, the module's only spelling of it, and composes column 6 and `weights_path` from it | the composition at nine sites |
| `fetch-model-runtime.sh` writes column 6 verbatim. Its only `backend/models` literal is the `mkdir -p` | three literals in the script |
| Each caller reads `weights_path` where it spells `backend/models/<file>` today | six literals across four workflows, plus `action.yml:147` |
| `backend/idhazh/llm/server.py:437-439` is corrected in row 1 | a **false docstring plan 41 landed**: it says `model_refs.py` "imports it rather than spelling the join a second time", and `model_refs.py` imports nothing from `idhazh` |

**No cross-module test between `model_refs.py` and `idhazh.llm.server`.** `companion_path` is one line with one caller at `server.py:492`; a test asserting two values agree would not have caught the docstring that is already wrong, and policing one file out of six is theatre. A named constant and a corrected sentence are the fix.

### C4 - The cache key (rows 1, 3)

| Property | Value |
| --- | --- |
| Shape | **a fixed-width SHA-256 hex digest**, never a join. The existing hyphen-join reaches 519 characters at seven files, past GitHub's 512-character key cap |
| What it covers | `repo`, `revision`, `file` and `sha256` per row, in declared order, and **nothing else** |
| What it must not cover | **column 5, `flag`** - it reaches the server command line, not the download, so digesting it discards 4.28 GB for zero byte change when the flag is edited. **Column 6** - it is derived from column 3, so it is noise |
| Where it is computed | the `cache-key` verb, over exactly what `files` prints. One traversal, so the key is provably the set the loop downloads. Declared as a verb so a worker cannot implement it as a private helper that walks the entry a second time |
| Empty | the verb refuses to print an empty key, and the step that reads it refuses an empty value. `llm--<build>-v5` is one key every model shares - a worse wedge than the one being fixed (ESCALATE trigger 4) |
| The suffix | `-v4` becomes `-v5`, once, in row 3. It is the fifth hand bump and the last, because the key now moves when the set moves |
| Paths | unchanged: `backend/models` and `backend/bin`, together, on one key |

**Why the key changes in both places that spell it.** `action.yml:93` and `idhazh-pipeline-tests.yaml:167` are the same format written twice; `action.yml:47-52` records them drifting once already. The guarding test at `test_weights_and_model_refs.py:344` scopes its closed world to the action's callers, and pipeline-tests does not call the action - so the hand-copy is invisible to a test whose docstring says there is one key now. **Row 3 widens that closed world to every `actions/cache` step whose `path:` names `backend/models`.**

**The companion hole alone does not pay for this change.** The live pointer declares no companion, so the production key is correct today and the defect is latent. What pays for it is the duplicate: two files carry one format, they have drifted, and the printer is the one place that can compute it once. The companion fix rides along free.

### C5 - What `fetch-model-runtime.sh` does (row 2)

Environment, and nothing else: `GITHUB_TOKEN` required for the pinned release lookup, `CONFIG_ROOT` required with no default in the script. **It stops reading `WEIGHTS_REPO`, `WEIGHTS_REVISION`, `WEIGHTS_FILE`, `DRAFT_REPO`, `DRAFT_REVISION` and `DRAFT_FILE`** - those six are the relay.

```
1. Refuse any positional argument.  [ "$#" -ne 0 ] -> exit 2.  Unchanged.
2. Refuse a missing CONFIG_ROOT.    : "${CONFIG_ROOT:?...}"
3. Refuse a missing GITHUB_TOKEN.   : "${GITHUB_TOKEN:?...}"
4. Run the printer to a FILE:
     python3 backend/utilities/model_refs.py files \
       --config-root "$CONFIG_ROOT" > backend/var/model-files.tsv
   Every C2 refusal lands on this line.
5. Refuse an empty file. Zero rows is a model that declares nothing.
6. Source install-llama-runtime.sh.
7. mkdir -p backend/models.  The only backend/models literal in this file.
8. Loop over the FILE, never over a pipe:
     while IFS=$'\t' read -r repo revision file sha256 flag dest; do
       curl -fsSL --retry 3 --retry-all-errors -o "$dest" \
         "https://huggingface.co/$repo/resolve/$revision/$file?download=true"
       echo "$sha256  $dest" | sha256sum --check
       downloaded=$((downloaded + 1))
     done < backend/var/model-files.tsv
9. Refuse a short set. [ "$downloaded" -eq "$rows" ] or exit 1.
```

**Refusal order in one line: arguments, then environment, then the whole file set's grammar, then the install, then per-row bytes, then the count.** Steps 4 and 6 are in that order because the file's own header promises it - a caller that got a field wrong fails in a second rather than after unpacking a runtime it will not use. Step 8 reads a file rather than a pipe because `printer | while read` runs the body in a subshell where the loop's own accounting is lost, and because a command in the body can eat the loop's stdin.

**Step 9 is the only control for the door `post-if: success()` cannot see** (C7). The per-row `sha256sum --check` inside the loop is an **early exit**, declared as one: it saves the remaining downloads and names the failing file. It is not half of the control.

**Python is there.** All four callers run `actions/setup-python@v7` before the fetch: `digest.yml:492`, `llm-council.yml:275`, `idhazh-pipeline-tests.yaml:83`, `validate.yml:236`. The script spells no `PYTHONPATH` and no `-m`, because C2 keeps the printer runnable by path.

**Where `CONFIG_ROOT` comes from, per caller:**

| Caller | `CONFIG_ROOT` | Built by |
| --- | --- | --- |
| `action.yml` (for `digest.yml` and `llm-council.yml`) | `config` | the action's new `config_root` input, default `config`. Neither caller passes it |
| `validate.yml:308`, the `qualify` job | `backend/var/candidate-config` | `./.github/actions/candidate-config` at `:268`, before the cache step at `:284` |
| `idhazh-pipeline-tests.yaml:182`, the `cases` job | `backend/var/candidate-config` | the same action at `:137`, before the cache step at `:164`. Its verify step at `:196` already reads that root |

### C6 - The composite action after row 2 (rows 2, 3)

**Ten inputs become four: `github_token`, `port`, `llama_cpp_build`, `config_root`.** The three weights inputs and the four draft inputs go.

| Step | After |
| --- | --- |
| **new, `id: model`, first** | `python3 backend/utilities/model_refs.py configured --config-root "$CONFIG_ROOT" >> "$GITHUB_OUTPUT"`. One call publishes `summarize_repo`, `summarize_revision`, `summarize_file`, `summarize_id`, `weights_path` and `cache_key`. It refuses an empty `cache_key` |
| Cache weights and runtime | `key: llm-${{ steps.model.outputs.cache_key }}-${{ inputs.llama_cpp_build }}-v5`. Paths unchanged |
| Fetch runtime and weights | unchanged condition `cache-hit != 'true'`; `env:` is now `GITHUB_TOKEN` and `CONFIG_ROOT` only |
| Verify the weights | **no `if:`**, unchanged position. Its body becomes `python3 backend/utilities/model_refs.py files --config-root "$CONFIG_ROOT" \| awk -F'\t' '{print $4 "  " $6}' \| sha256sum --check`. The inline Python at `:136` goes |
| Start the model | `LLAMA_WEIGHTS: ${{ steps.model.outputs.weights_path }}`. The composition at `:147` goes |
| Check model health | the alias comes from `steps.model.outputs.summarize_id`. The inline Python at `:183` goes |

**The action publishes `weights_path` as an action output**, so `digest.yml:583` and `:604` read it from the action call rather than from a job output row 2 deletes. The action call in `digest.yml` gains an `id:`.

**The key is computed inside the action, never passed in.** A caller-computed key is hop 3 of the four this plan exists to delete, and it costs three lines each in `digest.yml` and `llm-council.yml` - a `cache_key` output on `configured`, a job output, and a pass-through. Computed, it costs zero lines in both callers and it is provably the set the loop downloads, which a separately-computed value is not.

### C7 - What stops a bad cache entry being written (row 2)

The control is a SHA-256 checksum, and it has one half that is load-bearing and one that is convenience.

| Half | Where | Runs on a hit? |
| --- | --- | --- |
| **restore-time - the control** | a workflow or action step with **no `if:`**, in every caller, after the fetch and before the first read of `backend/models` | **yes.** This is the only one that does |
| download-time - an early exit | inside the fetch loop, per row | no. The script runs behind `cache-hit != 'true'` |

**`actions/cache@v6` does not save when the job failed.** Its manifest declares `post-if: "success()"`; the `save-always` input is inert and carries a deprecation message. The version history is the tell - v4.0.0 had `post-if: success() || ...save-always`, v4.2.0 dropped it. So a failed verify writes no entry.

**The door `post-if` cannot see** is a fetch loop that exits 0 having downloaded fewer files than the model declares: a successful job saves a short set, every later run hits it, skips the fetch and fails the verify identically. C5 step 9 closes the miss side; the no-`if:` verify closes the hit side.

**The standing rule, written where it can be read:** no step between the cache restore and the verify may carry `continue-on-error: true`, and the cache step is never split into `actions/cache/restore` plus a save with `if: always()`. Either one makes `post-if: success()` untrue. Neither exists in the fetch path today.

### C8 - The commit order that protects the verify step (row 2)

**Row 2's first commit is tests only, and it lands RED.** The second commit moves the fetch.

| Clause | Lands |
| --- | --- |
| **the paste rule** - no value the printer publishes appears inside a `run:` body of any job reaching the action or the script | red: **8 sites** today - `digest.yml` 1, `idhazh-pipeline-tests.yaml` 1, `validate.yml` 6 |
| **every printed row reaches `sha256sum --check`** in each verify step | red: no verify step reads the printer today |
| **the verify step's config root equals the fetch step's** | red: the fetch step names no root today |
| the four clauses already green at `test_weights_and_model_refs.py:59-88` - closed-world discovery, the three step names in order, no `if:` on the check, the literal `sha256sum --check` | green, and **they are not rewritten** |

**Why the order is the control, not a preference.** The most likely failure in this plan is a worker seeing two `sha256sum --check` calls, reading the workflow step as redundant, deleting it, and going green everywhere - because the only test guarding it is one row 2 itself edits, and an assertion re-pointed at the script finds a check there and passes. With the tests landing first and red, the worker goes red locally before the push. **One review rule rides with it: row 2's diff must not remove `assert "if" not in check`.**

## Section 2 - Row 1 - The printer learns the whole file set, and the grammar closes

- **Scope:** Give `model_refs.py` a `files` verb, a `cache-key` verb, three new published keys, a field grammar that refuses every value a shell or a `run:` body could misread, and one spelling of the models directory - and delete the `draft_*` output keys.
- **Files touched:**
  - `backend/utilities/model_refs.py`
  - `backend/tests/workflows/test_weights_and_model_refs.py`
  - `backend/tests/workflows/test_pipeline_tests_workflow.py` (it imports `candidate_rows`, `configured_rows` and `CONFIGURED_FIELDS` at `:683-691`)
  - `backend/idhazh/llm/server.py` (the false docstring at `:437-439`, and nothing else in the file)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q` and `python -m pytest backend/tests/test_measure_llm.py -q`; CI - full suite. No dispatch.
- **Oracle:** **stated against the verb production runs today, not against the new one.** Run `candidate` against a fixture models file whose `summarize.file` is `../../etc/passwd.gguf`, and a second whose `summarize.file` is `x$(id).gguf`; assert a non-zero exit naming the field. **Today both exit 0 and print the value into `$GITHUB_OUTPUT`.** Second failing case: run `candidate` against a fixture declaring seven companions and assert the `cache_key` row is at most 64 characters - **today the hyphen-join prints 519, past GitHub's 512-character cap.** The `files` verb's own refusal cases are coverage of new code, not an oracle: a test of a verb that does not exist errors on invocation rather than failing. **What it cannot settle:** whether a shell or a `run:` body ever sees an unvalidated value. No test here executes `fetch-model-runtime.sh`; row 2's paste rule and closure assertion settle it, and this row's cases are worth less without them.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The grammar is **declared in `model_refs.py`** with stdlib `re`, not imported from `measure_llm.py` and not moved to a shared module. Both alternatives break a job that has no install, and the import failure is invisible to every local gate because pytest puts `backend` on `sys.path`. C2 has the measurement | Carmack |
 | 2 | The duplication is gated by an explicit three-name equality test on `.pattern` **and** `.flags`. A reviewer does not have to catch a drift a test refuses | Carmack and Fowler |
 | 3 | The companion list is read from `companion_files` and nothing else. Zero committed model files carry `draft`, so a `draft` arm would ship dead with its removal condition already met - Guardrail #6 inverted | Fowler |
 | 4 | The weights `file` gets the `.gguf` suffix rule; a companion `file` gets the segment rule **without** it. `CompanionFile` deliberately has no suffix rule because a companion may be a projector, an adapter or a vocoder | Andre |
 | 5 | `byte_count`, `id` and `quantisation` are checked before printing. `byte_count` has no check of any kind today and a newline in it writes extra lines into `$GITHUB_OUTPUT` | Andre |
 | 6 | A final backstop refuses any emitted value carrying a shell metacharacter or a newline. The field rules fix the fields that exist; the backstop refuses the field added in six months by default | Andre |
 | 7 | `sha256` is required on every companion, with no exception, **for diagnosability rather than integrity** - a blank digest already fails the run, but `sha256sum` names a pipe where the printer names the file, the index and the field | Carmack |
 | 8 | The cache key is a **fourth verb over the printed rows**, digesting `repo`, `revision`, `file` and `sha256` only. Not `flag` - it reaches the server command line, so digesting it discards 4.28 GB for zero byte change when it is edited. Not column 6 - it is derived from column 3 | Carmack |
 | 9 | All four verbs take `--config-root`, default `config`; `--repo-root` is deleted. One uniform argument replaces two, and the script and the action both name a config tree that is not `config/` | Fowler |
 | 10 | `_draft_rows` and every `draft_*` key are deleted **in this row**, not row 2. They are the only name in the module describing one companion out of N, and leaving them is how two verbs end up contradicting each other about one entry while both are green | Fowler |
 | 11 | `MODELS_DIR` is declared once here, and `server.py:437-439`'s docstring is corrected in the same commit. It claims `model_refs.py` imports `companion_path`; `model_refs.py` imports nothing from `idhazh` | Fowler |
 | 12 | The three wrong Guardrail #11 citations in `model_refs.py:1-4` are replaced with what is true: these values are pasted into `run:` bodies where the Actions engine substitutes before bash parses | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | `model_refs.py` imports the patterns from `measure_llm.py` | It resolves only through hatchling's editable `.pth`, which `pyproject.toml` does not pin. Doing it safely means `PYTHONPATH=backend python3 -m utilities.model_refs` at six invocation sites, two of them in `measure.yml` and `digest.yml` - so the grammar fix acquires a five-workflow blast radius and a plan-46 collision | Five workflow edits, a sixth spelling inside a shell script that no test reads, and a `ModuleNotFoundError` class that every local gate hides | Carmack |
 | 2 | A shared third module both import | It moves the trap into the file with two execution modes. `measure_llm.py` runs by path in `llama-bench`, which has no install, and as `utilities.measure_llm` under pytest - no single plain import works in both | The same silent class, relocated | Carmack |
 | 3 | Declare the grammar in `backend/idhazh/contracts/knobs/models.py` | The right long-run home, and it needs `utilities` to be a declared package first. `pyproject.toml` declares `packages = ["backend/idhazh"]` | A packaging row, after which the two copies collapse to one import | Fowler |
 | 4 | Keep the hyphen-join and add companions to it | It reaches 519 characters at seven files, past GitHub's 512-character cap, and nobody would connect that failure to its cause | Nothing saved over a digest | Fowler |
 | 5 | A cross-module test asserting the printer's landed path equals `companion_path`'s | It polices one file out of six that spell `backend/models`, and it would not have caught the false docstring already on `main`. A named constant plus the corrected sentence is strictly stronger | A test and an import coupling, for a property one constant already holds | Fowler |
 | 6 | Keep `_draft_rows` until row 2 deletes its readers | Two verbs describing one entry at two arities, both green, is what the draft's predecessor shipped | Four lines kept, and a contradiction a reviewer has to hold in their head across two pull requests | Fowler |

## Section 3 - Row 2 - The workflows read the model file instead of relaying it

- **Scope:** Make the fetch script read a config root and loop over the printer's rows; make the composite action compute its own key, alias and weights path and drop to four inputs; delete the six relay blocks and four inline Python programs in the four callers.
- **Files touched:**
  - `.github/scripts/fetch-model-runtime.sh`
  - `.github/actions/model-server/action.yml`
  - `.github/workflows/digest.yml` (the 17 relay lines: `:95-101`, `:178`, `:550-557`, `:583`, `:604`)
  - `.github/workflows/llm-council.yml` (`:77-83`, `:171`, `:311-318`)
  - `.github/workflows/validate.yml` (`:107-110`, `:299-301`, `:305-307`, `:316-317`, `:320`, `:337`, `:399`)
  - `.github/workflows/idhazh-pipeline-tests.yaml` (`:176-181`, `:192-204`, `:247`, `:274`, `:327`, `:354`)
  - `backend/tests/workflows/test_weights_and_model_refs.py`, `test_pinned_versions.py`
  - `backend/tests/workflows/_harness.py` (delete-only: the four `WEIGHTS_CHECKS` entries that become derivable)
  - `docs/reference/ci-model-runtime.md`, `docs/architecture/summarize/model-boundary.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q` and `shellcheck .github/scripts/fetch-model-runtime.sh`; CI - full suite; **plus dispatch D1 in the sequence below, before row 3's commit.**
- **Oracle:** **the paste rule.** No value the printer publishes appears inside a `run:` body of any job reaching the composite action or the fetch script. **It fails today on 8 sites** - `digest.yml` 1, `idhazh-pipeline-tests.yaml` 1, `validate.yml` 6 - and row 2 removes all 8 by removing their producers. A sibling assertion: `fetch-model-runtime.sh` contains no `backend/models/` literal other than the `mkdir -p`, which **fails today at 3 occurrences** (`:37`, `:42`, `:51`). **What it cannot settle:** `measure.yml`'s 5 paste sites. They reach neither the action nor the script, they are out of scope by the table in section 0, and the oracle is scoped to say so rather than to fail forever. ESCALATE triggers 1, 2 and 3 apply.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The first commit is tests only and lands RED** - the paste rule plus the two new digest clauses. The second moves the fetch. Without that order a worker deletes the workflow verify step as redundant and every local gate stays green. C8 has the detail | Fowler |
 | 2 | The restore-time check survives as a step with **no `if:`**. The script runs behind `cache-hit != 'true'`, so a check living only inside it never sees a restored entry | Carmack |
 | 3 | The in-loop digest check is an **early exit**, named as one, not half of the control. Calling it a half is the framing that invites the next worker to delete the wrong one | Carmack |
 | 4 | The loop reads a file, not a pipe, and the script refuses a short set at the end. `post-if: success()` cannot see a loop that exits 0 having downloaded fewer files than the model declares | Carmack |
 | 5 | The action **computes** its key, alias and weights path in one new first step. A caller-computed key is hop 3 of the four this plan deletes, and it costs three lines in each of two callers; computed, it costs zero and is provably the set the loop downloads | Carmack and Fowler |
 | 6 | The action ends at **four** inputs: `github_token`, `port`, `llama_cpp_build`, `config_root` | Carmack |
 | 7 | `digest.yml` is edited in this pull request, not stranded. It carries 17 relay lines, and `:583` and `:604` read a job output this row deletes the producer of - stranding them leaves `LLAMA_WEIGHTS: backend/models/` and a `sha256sum` on a directory | Fowler |
 | 8 | **`WEIGHTS_CHECKS` shrinks from eight entries to four, and does not die.** `digest.yml/work`, `llm-council.yml/judge`, `validate.yml/qualify` and `idhazh-pipeline-tests.yaml/cases` become derivable and go; `measure.yml`'s four stay, because all four of its downloads are inline and stay inline. Its comment is rewritten to say the list is now exactly the downloads that bypass the shared path | Fowler |
 | 9 | The grep oracle is scoped to jobs reaching the action or the script. An unscoped version cannot pass while `measure.yml` carries four independent downloads | Fowler |
 | 10 | The paste rule shipped here is the **scoped** one, in this plan's own test module. The repository-wide rule over all 28 `needs.*.outputs.*` expressions is plan 46's row - it needs `test_triggers.py`, `digest.yml`, `measure.yml` and `validate.yml` together, and plan 46 already holds all four | Andre proposed; Fowler ruled on where it lands |
 | 11 | The alias the health checks read comes from `summarize_id` and `candidate_id`, published by the printer. `CONFIGURED_FIELDS` gains `id`; `CANDIDATE_FIELDS` already has it. That is what lets the four inline Python programs go | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Move the digest check entirely into the fetch loop | The loop is skipped on a cache hit, so a restored entry is never checked. That is the exact case the step exists for | Nothing saved, and a wrong model reaching the server unnoticed | Carmack |
 | 2 | Strand `digest.yml`'s relay lines in a third pull request, dispatched when plan 46's grip lifts | The file is load-bearing here, not a crumb - see decision 7. A composite action does warn rather than fail on an undeclared input, so stranding would have been mechanically safe; it is refused on the 17 lines, not on the risk | A production run left with `LLAMA_WEIGHTS` empty between the two merges | Fowler |
 | 3 | Pass the cache key into the action as an input | Hop 3 of four, and it makes the key a value computed somewhere other than where the set is read | Three lines in each of two callers, and a key that is no longer provably the downloaded set | Carmack |
 | 4 | Convert `measure.yml`'s four inline downloads here | Four more blocks in the largest pull request in the plan, none of which uses the action, in a file plan 46 owns | Its own row, priced in section 0 | Fowler |
 | 5 | Give the script a base-URL seam so a test can execute it | A seam that exists only for a test is a mock by another name (Guardrail #7) | About 15 lines and a second code path. `shellcheck` plus dispatch D1 is the honest answer | Fowler |
 | 6 | Keep the four draft inputs on the action as optional | They are the relay this plan removes, and optional means a caller can still pass them | Four inputs and four pass-through lines per caller | Carmack |

## Section 4 - Row 3 - The cache names the set, in both places that spell it

- **Scope:** Key the production weights cache on the digest over the whole declared file set, in the composite action and in the hand-copy that shares its format, and widen the guarding test's closed world to reach both.
- **Files touched:**
  - `.github/actions/model-server/action.yml` (the key at `:93`, `-v4` -> `-v5`)
  - `.github/workflows/idhazh-pipeline-tests.yaml` (the hand-copy at `:167`)
  - `backend/tests/workflows/test_weights_and_model_refs.py` (the closed world at `:344`)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite; **plus dispatch D2 in the sequence below.**
- **Oracle:** render the action's `key:` expression for two fixture models files identical except for one companion digest, and assert the two keys differ. **It fails today**: the key is `llm-<weights_file>-<weights_revision>-<build>-v4`, which names no companion, so the two are identical. Driven from the workflow file, **no dispatch and no cold fetch** - a dispatch could not isolate it anyway, because a miss can come from any key component. **What it cannot settle:** whether restored bytes are correct on a hit whose key did match. That is row 2's no-`if:` verify, and it is why both rows exist. ESCALATE trigger 4 applies.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The defect is a wedged pipeline, not a saving. A hit missing a declared file fails the verify, and every re-run fails identically because a hit refreshes last-access so the entry never ages out. `-v4` is that bump already paid four times | Carmack |
 | 2 | **Both spellings change together.** `action.yml:93` and `idhazh-pipeline-tests.yaml:167` are one format written twice; `action.yml:47-52` records them drifting once already. Changing one leaves the copy that already drifted, inside the change that was supposed to remove copies | Carmack |
 | 3 | The guarding test's closed world widens from the action's callers to **every `actions/cache` step whose `path:` names `backend/models`**. Today the hand-copy is invisible to a test whose docstring says there is one key now | Fowler |
 | 4 | The paths stay together on one key. Two sibling directories written by two different scripts cannot overlap, so the disjointness question the draft escalated guarded a tautology | Carmack |
 | 5 | **`backend/utilities/runtime_sweep.py` and `gguf_cache_hit` are not in this row.** That value is a CLI argument reporting whether the *bench* key hit, and the bench key already covers companions. No persisted shape moves, so CLAUDE.md section 11 owes nothing | Fowler |
 | 6 | `measure.yml` and `validate.yml` need no edit. Their keys read `candidate_cache_key`, whose value changes when row 1 changes the key shape while the expression does not | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Extend the existing hyphen-join to N digests | Key length crosses GitHub's 512-character cap at about seven files, and the failure would read as unrelated | Nothing saved over a digest | Fowler |
 | 2 | Split `backend/bin` onto its own key | A cold download is 57 to 338 s against a 38 to 95 s restore, so the marginal cost of a shared key is about 30 s at the median and can be negative. The split needs a second skip condition at each of the four inline installer copies in `measure.yml` | Under three minutes of download a year, measured, against four new skip conditions | Carmack |
 | 3 | Bump to `-v5` and change nothing else | It clears today's latent wedge and leaves the mechanism, so `-v6` follows | One character, and the fifth manual bump with a sixth queued | Carmack |
 | 4 | Change only the action, leaving the hand-copy | Half a fix inside the change that exists to delete hand-copies | Two key formats that have already drifted once, now diverging on purpose | Carmack |

## Section 5 - The two dispatches, and what each proves

Four things a dispatch must prove that nothing cheaper can: the loop downloads every declared file on a real runner and each row's digest passes; the no-`if:` verify runs on a **restored** entry and passes over every declared row; the key Actions resolves is the key the printer prints; and the action's key and the inline caller's key resolve to the same string.

| # | Dispatch | Workflow, branch, inputs | What it proves | Cost |
| --- | --- | --- | --- | --- |
| D1 | **the miss** | `idhazh-pipeline-tests.yaml`, PR-B's branch, `candidate_models_file` empty | the loop, the per-row digest, the `backend/var/candidate-config` root, the landed path, and that the new key's entry saves. Empty input reads the committed pointer, so its key is the production key | one cold fetch, about 30 s over the restore it replaces at the median. It carries `permissions: contents: read` and writes only an artifact, so **it cannot push** |
| D2 | **the hit** | `llm-council.yml`, same branch, `date` empty | the restore-time verify over restored bytes, the resolved key's stability, **and cross-caller key equality all at once** - the hit itself proves the action's key equals the inline caller's | no weights download. **It pushes council verdicts to the branch; drop that commit before merge** |

**Strictly sequential.** D1 must finish before D2 starts; they are in different concurrency groups and nothing enforces it, and run in parallel both miss and D2 proves nothing.

**The collapse is not an accident, and a worker must not break it.** The key is a digest over what the printer prints, and the printer prints no config path - so two config roots holding the same `summarize` entry produce the same key by design. A worker who "fixes" a cross-caller miss by putting the config root into the key has destroyed the property that makes D2 work.

**If D2 misses, that is a finding, not a re-run.** Read the two resolved key strings off the two run logs, fix the fold, re-run D2 only. D1's proof stands.

**Not `digest.yml` and not `validate.yml`.** `digest.yml` is the production digest - 164 to 184 min, and it pushes to `main`. `validate.yml` uses the inline fetch shape D1 already proved.

## See also

- [`20260921-42-lane-b-workflows-plan.md`](20260921-42-lane-b-workflows-plan.md) - the parent, whose rows 1 to 6 landed and whose rows 7 to 11 this plan carries.
- [`20260922-46-no-file-has-two-writers-plan.md`](20260922-46-no-file-has-two-writers-plan.md) - in flight; section 1d is the interlock, and two of this plan's scope-out lines become rows there.
- [`20260922-47-the-pipeline-stops-naming-a-server-plan.md`](20260922-47-the-pipeline-stops-naming-a-server-plan.md) - owns `runtime_sweep.py`'s address lines; its claim of sharing no file with this plan is true once `measure.yml` and `runtime_sweep.py` leave here.
- [`../docs/reference/ci-model-runtime.md`](../docs/reference/ci-model-runtime.md) - the page that owns the fetch path and gains the new interface.
- [`../docs/architecture/summarize/model-boundary.md`](../docs/architecture/summarize/model-boundary.md) - the page that owns what the model file declares.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed.


