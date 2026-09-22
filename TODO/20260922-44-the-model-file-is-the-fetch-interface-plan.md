# The model file is the fetch interface

**Last Updated**: 2026-09-22

**Level**: 4, and row 2 is why. It rewrites the download path the daily run depends on, and only a live dispatch proves it, so a revert would land after a failed publish - CLAUDE.md section 6's Level-4 test. Row 1 is Level 3: `one_bare_word` at `backend/utilities/model_refs.py:41` refuses whitespace and nothing else, while **13 model-file values are pasted textually into `run:` bodies across four workflows**, where a value spelling `$(id)` executes. That is this repository's own env-not-paste rule failing on a maintainer-written config file. **It is not a Guardrail #11 question** - Guardrail #11 is about fetched web text, and a model file is neither fetched nor web.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 1 row in flight - one, because the plan has exactly two dispatchable rows and the second imports contracts the first declares, so a second slot can never fill; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | One JSON file says which bytes a model needs. Its contents still travel through a Python printer, a job output, a composite-action input and an environment variable before a `curl` sees them - four hops, and the arity is welded at two files, so a model shipping three cannot be described. `model_refs.py:41` refuses whitespace only, so `../../x.gguf`, `x.gguf$(id)`, `` x.gguf`id` `` and a branch name in place of a commit all pass, and 13 of those values are pasted into `run:` bodies where the Actions engine substitutes before bash parses. The production cache key at `.github/actions/model-server/action.yml:93` names no companion at all, so a companion change that keeps the weights filename produces a hit missing a declared file - and every re-run then fails identically until a person bumps the key by hand. The key ends `-v4`, which is that bump already paid four times. |
| The rule | **The model json is the interface. It names every file the model needs and where each comes from; one reader turns that into downloads, checks, a landed path, a size check and a cache key. Everything else that relays a model fact through a workflow is deleted.** Owner ruling 2026-09-21. |
| The second rule | **A value this project computes is published, never composed a second time downstream.** `backend/models/<file>` is composed at nine places today. After row 2 the printer composes it once and everybody else reads it. |
| The measure | **Hops from the model file to the download, and places a model fact is spelled.** Hops 4 -> 1. Spellings of the field names between config and `curl`: 5 -> 3 - three, not two, because `measure.yml`'s four inline arms keep one, priced in the scope-out table. |
| Hard scope - in | Give the printer a `files` verb emitting the whole file set with its landed path and declared size, a `cache-key` verb over those same rows, three new published keys, and a field grammar that refuses every value a shell or a `run:` body could misread. Make the fetch script read a config root and loop. Make the composite action compute its own key, alias and weights path, so its ten inputs become four. Delete the six relay blocks and five inline Python programs in the four callers, and move both spellings of the weights cache key onto the digest in one commit. |
| Hard scope - out | See the table below. Every line there is a dated decision with a price, never a law (CLAUDE.md section 0d). |
| Supersedes | Plan 42 rows 7 to 11, which are `COLLAPSED` in that plan's Reckoner. |
| Assumes | **Plan 41 merged as #1036 and #1039.** `COMPANION_FIELDS`, `_companions()` and the companion-joining `_cache_key` are on `main`. No plan-41 coupling remains. |
| ESCALATE triggers | (1) **Row 2's first commit is tests only and lands RED.** If a commit moves the fetch before those tests exist, stop - C9 says why the order is the control. (2) Row 2 must leave a digest check that runs on a cache hit. The fetch script runs behind `cache-hit != 'true'`, so a check living only inside it never sees a restored entry. (3) If any step between the cache restore and the verify acquires `continue-on-error: true`, or the cache step is split into `actions/cache/restore` plus a save with `if: always()`, stop. Both make `actions/cache`'s `post-if: success()` untrue, which is the only thing stopping a failed job writing a bad entry (C8). (4) If the `cache-key` verb can print anything but 64 lowercase hex characters, stop: `llm--<build>-v5` is one key every model shares, which is worse than the wedge being fixed. (5) **If row 1 deletes any published output key, stop.** Row 1 is additive on keys; `measure.yml` reads seven of them and is in neither pull request (C2). (6) **If the two weights cache keys move in different commits, stop.** `action.yml:93` and `idhazh-pipeline-tests.yaml:167` move together or the closing dispatch proves nothing. (7) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | **Two pull requests, three commits, strictly sequential, then three dispatches.** PR-A is the printer and shares no file with any plan in flight. PR-B is the fetch interface and the key. Fowler ruled the grouping, the row collapse and the test rewrites; Carmack the fetch path, the cache, the dispatches and the size check; Andre the grammar, the refusal messages and the paste rule. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1 - two dispatchable rows, and the second imports contracts the first declares.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **`measure.yml`'s four inline weights downloads, and the four `candidate_draft_*` job outputs that feed them** | The printer keeps a one-companion projection - `_draft_rows` and four `draft_*` keys on the `candidate` verb - so the plan's own "spellings 5 -> 2" is 5 -> 3. `measure.yml:596` and `:923` keep their own `byte_count` cross-check and their own paste sites | **This is the single largest scope decision in the plan and it is what keeps `measure.yml` out of it.** The four arms at `:318`, `:572`, `:901` and `:1136` reach neither the action nor the script; the `batched` arm spells `MODEL_*` and is a different shape; and the `llama-bench` arm unpacks `llama-bench` from its own tarball rather than sourcing `install-llama-runtime.sh`, so the shared script is not a drop-in there. `measure.yml` is also plan 46's file in two of its rows. **It becomes a row in plan 46**, which owns the file: four arms, about 14 consumer lines, and one bench dispatch to re-prove, against a 330 min bound. Carmack |
| **Refusing `needs.*.outputs.*` inside any `run:` body, repository-wide** | **28** job-output expressions keep reaching a shell through textual substitution rather than `env:` - `digest.yml` 15, `validate.yml` 8, `measure.yml` 5. A value spelling `$(id)` executes, and nothing mechanical refuses a 29th. Five of the 13 model-file pastes stay in that state, all of them `measure.yml`'s | **It is plan 46's row.** Plan 46 already owns `test_triggers.py`, `digest.yml`, `measure.yml` and `validate.yml`, and holds all four in its group A. Added there it inherits one file list, one worktree and one merge order instead of fighting them. **Counted by parsing each workflow and matching `needs.<job>.outputs.<key>` inside every step's `run` string, all scalar forms** - a line regex over `run: \|` blocks gives 25 and misses single-line `run:` and expressions carrying an operator. **What this plan takes free instead**, inside row 2: the same rule scoped to jobs reaching the action or the script, which fails today on 8 of the 13 and whose 8 producers row 2 deletes. Andre proposed it and withdrew his own scope-out line; Fowler ruled on where it lands |
| **Cutting `backend/tests/workflows/_harness.py` to names more than one module reads** (the draft's row 5) | The module stays 2,248 lines with 241 top-level names, and **a one-file change still has to touch 143 of them** - 10 that nothing imports plus 133 that exactly one module imports. Twenty-one consumer modules pay that read every time a workflow test is added | **Plan 46's Reckoner reads all-DONE, and this plan's row 2 has merged.** Plan 46 writes `_harness.py`, `test_triggers.py`, `test_staged_paths.py` and `test_daily_commit_steps.py` across seven waves; a 133-name move landed underneath it conflicts on every merge. Row 2 rewrites `test_weights_and_model_refs.py`, where about 22 of those names belong. Then re-run the census - never read a recorded table - and run it as its own plan. **The draft's "nine of 45 orphans are internal" was wrong: it is 35 of 45, so only 10 deletions exist and the row is almost entirely a move.** Fowler |
| **Splitting the runtime binary onto its own cache key** | A llama.cpp pin bump keeps discarding the weights beside it | **Refused on arithmetic the draft got backwards.** A cold download is 57 to 338 s and the restore it replaces is 38 to 95 s, so the marginal cost is about **30 s at the median and can be negative** (`docs/reference/benchmarks/what-a-bench-dispatch-costs.md`, eight `runtime` jobs on the 4.28 GB gemma arm, 2026-09-14 to 2026-09-16). A pin bump happens a couple of times a year. Against that, `install-llama-runtime.sh` has one caller and `measure.yml` carries four inline copies of it, so the split needs a second skip condition at each. Carmack |
| **Declaring the field grammar in `backend/idhazh/contracts/knobs/models.py`** | The grammar is declared in `model_refs.py`, and `measure_llm.py` and `contracts/base.py` each hold a copy of part of it, gated by equality tests | The right long-run home - one declaration, three importers - and it needs `utilities` to become an installed package or every call site to move to `-m`. `pyproject.toml:175` declares `packages = ["backend/idhazh"]`, so `utilities` is importable today purely through hatchling's editable `.pth`. **What brings it in:** a packaging row that makes `utilities` a declared package, after which the copies collapse to one import. Carmack and Fowler |
| **Any process-boundary value - the port, the host** | Nothing | **Plan 47 owns it**, and after `measure.yml` and `runtime_sweep.py` leave this plan, plan 47's claim that it shares no file with plan 44 is true. Fowler |

### What a change costs today

Measured on `origin/main`, 2026-09-22, by reading the files. **Every line number in the draft's equivalent table was stale; these were re-taken, and two figures the first refinement carried are corrected below.**

| Reading | Value | Where |
| --- | --- | --- |
| Hops from the model file to the download | **4** - printer, job output, action input, environment | `model_refs.py` -> `$GITHUB_OUTPUT` -> `action.yml:107-115` -> `fetch-model-runtime.sh:30-32` |
| Places a model-file field name is spelled between config and a `curl` | **5** | `model_refs.py`'s `draft_*` output keys, `digest.yml:95-101`, `action.yml:28-47`, `action.yml:107-115`, `fetch-model-runtime.sh:30-32` |
| Files a model file can declare | **exactly 2**, welded | `COMPANION_FIELDS` at `model_refs.py:27`, `_draft_rows` at `:68`, `_cache_key` at `:86` |
| Composite action inputs | **10, of which 4 are draft** | `action.yml:12-47` |
| What `one_bare_word` refuses | **whitespace and empty only** | `model_refs.py:41`. Admitted on a direct call: `../../x.gguf`, `x.gguf$(id)`, `` x.gguf`id` ``, `a"b`, `a;b`, `a\|b`, `$(curl${IFS}evil)`, `%2e%2e%2fx`, `/etc/passwd`, `..`, `.hidden`, `x.txt`. **`$(...)` needs no whitespace and `${IFS}` supplies whitespace without a space character** |
| Whether `model_refs.py`'s own docstring is true | **no.** `:1-4` says it is "where a value carrying a space, a quote or a newline stops". `'a"b'.split() == ['a"b']` | it also cites Guardrail #11 for a committed config file |
| Model-file values pasted into a `run:` body, where `${{ }}` substitutes before bash parses | **13** - `digest.yml:604`; `idhazh-pipeline-tests.yaml:201`; `measure.yml:330`, `:587`, `:596`, `:914`, `:923`; `validate.yml:320`, `:321`, `:329`, `:367`, `:368`, `:399` | measured by parsing every workflow and matching inside each step's `run` string |
| Of those 13, how many row 2 removes | **8** - every one in a job reaching the action or the script | `measure.yml`'s 5 are out of scope by the table above |
| Whether the weights `file` has any segment rule | **none, in either layer** | `ModelRef.file` is `Field(min_length=1)`; `CompanionFile` validates companions only, in Pydantic, which never runs on the shell path because `model_refs.py` reads raw JSON |
| Whether `byte_count` is checked at all before printing | **no** | `model_refs.py:153` prints it straight. A newline in that value writes extra `key=value` lines into `$GITHUB_OUTPUT` |
| Whether every companion's `sha256` is checked | **no** - `_draft_rows` checks the first companion only, while `_cache_key` digests every one | `model_refs.py:68-84` against `:86-97`. **A two-companion entry today keys on two files and fetches one**, saves a short bench entry, and the server arm restores it |
| Key length if the existing hyphen-join met seven files | **519 characters**, past GitHub's 512-character cap | `_cache_key` at `model_refs.py:97` |
| Companion files the production cache key names | **0** | `action.yml:93`, keyed on weights file, weights revision and build |
| Second hand-copy of that key format | **1**, also ending `-v4`, invisible to the guarding test because that test scopes its closed world to the action's callers | `idhazh-pipeline-tests.yaml:167` against `test_weights_and_model_refs.py:344` |
| Which arms are already protected | the benchmark and qualification arms - they key on `candidate_cache_key`, which is the printer's key and already digests every companion | `measure.yml:268`, `:549`, `:878`; `validate.yml:284`. **Production is the only uncovered one** |
| Inline Python programs walking a model file inside a workflow or action | **6, of which 5 are in scope** | in scope: `action.yml:136`, `:183`; `idhazh-pipeline-tests.yaml:196`, `:274`, `:354`. Out: `measure.yml:1151` |
| Places `backend/models/<file>` is composed by hand | **9** | `action.yml:147`; `fetch-model-runtime.sh:38`, `:42`, `:51`; `digest.yml:583`, `:604`; `validate.yml:320`, `:337`, `:399`; `idhazh-pipeline-tests.yaml:201`, `:247`, `:327` |
| Committed model files declaring a companion | **1 of 5**, and it is a bench candidate rather than the pointer | `config/models/gemma-4-e4b-qat.json:5`, one entry, `mtp-gemma-4-E4B-it.gguf` |
| Consumers of `candidate_draft_*` outside this plan's file list | **4 arms, 14 lines** | `measure.yml:150-153`, `:308-331`, `:503-506`, `:853-856`. **This is why row 1 deletes no key** |
| **The production weights entry, corrected** | **5.68 GB** (`5,680,522,464` bytes), not the 4.28 GB the first refinement quoted | `config/models/qwen3.5-9b-q4km.json`. The benchmark seconds were taken on the 4.28 GB gemma arm and scale by about 1.33 |
| Whether `actions/cache@v6` saves a cache entry when the job failed | **no.** Its manifest declares `post-if: "success()"`, and `save-always` is inert with a deprecation message | read from the v6 manifest, 2026-09-22. v4.0.0 had `post-if: success() \|\| ...save-always`; v4.2.0 dropped it |
| The door that `post-if` cannot see | a fetch loop that exits 0 having downloaded fewer files than the model declares | closed by C6 step 12 and by the no-`if:` verify, which runs on the miss path too |
| `_harness.py` census, re-taken | 2,248 lines, 241 top-level names, 45 with no importer of which **35 are used inside the module itself**, 133 with exactly one importer, 39 with two or three, 24 with four or more, 21 consumer modules | AST census over `backend/tests/**/*.py` |

## Section 0b - What this plan does, in one list

1. The printer learns the whole file set, its landed path, its declared size, a fixed-width key over it, and a grammar that refuses every value a shell or a `run:` body could misread. It deletes no published key.
2. The workflows read the model file instead of relaying it: the script loops, the action computes its own key and alias and drops to four inputs, the six relay blocks and five inline Python programs go, and both spellings of the weights cache key move onto the digest in one commit.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The printer learns the whole file set, and the grammar closes | - | A | PENDING | - | - | - |
| 2 | The workflows read the model file, and the cache names the set it declares | 1 | B | PENDING | - | - | - |
| 3 | The cache names the set, in both places that spell it | 2 | B | COLLAPSED | - | - | - |
| 4 | The benchmark arms learn the server died, and the repeat count is config | - | C | DONE | p42p5 | - | P5 |
| 5 | The harness keeps only what more than one module reads | - | D | COLLAPSED | - | - | - |

**Row 3 is COLLAPSED into row 2.** Its key change cannot be reverted without reverting row 2, because `action.yml:93` spells `inputs.weights_file` and `inputs.weights_revision`, and row 2 deletes both - a composite action referencing a deleted input resolves it to the empty string, so row 2 landing alone would produce `llm---<build>-v4`, one key every model shares. That is this plan's own ESCALATE trigger 4 firing inside the commit meant to prevent it.

**Row 4 landed ahead of the draft's sequence and nothing was owed for it.** `runtime_sweep.py:328` carries `START_GRACE_SECONDS: Final = 2.0`, used at `:348`; `backend/idhazh/contracts/knobs/bench.py:47` carries `repeats`. The draft claimed a coupling to row 3 through `gguf_cache_hit`. There is none: that value is a CLI argument (`runtime_sweep.py:727`, set at `measure.yml:607` and `:1138`) reporting whether the **bench** key hit, and the bench key already covers companions.

**Row 5 is COLLAPSED into the third line of the hard-scope-out table**, with its cost and the condition that brings it back. Both collapsed rows stay in this table rather than being deleted: this plan exists because plan 42 kept its collapsed rows, and a row deleted from a Reckoner turns a priced decision into a proposal with no author.

### Section 1a - The two pull requests and the files each owns

**No two pull requests in this plan are ever open at the same time**, so a file both touch is never contested. `test_weights_and_model_refs.py` is in both and that is safe for exactly that reason.

| PR | Rows | Wave | Files it owns |
| --- | --- | --- | --- |
| **PR-A - the printer** | 1 | 1, alone | `backend/utilities/model_refs.py`, `backend/tests/workflows/test_weights_and_model_refs.py`, `backend/tests/workflows/test_pipeline_tests_workflow.py`, `backend/idhazh/llm/server.py` (one docstring at `:437-439`) |
| **PR-B - the fetch interface and the cache** | 2 | 2, alone | `.github/scripts/fetch-model-runtime.sh`, `.github/actions/model-server/action.yml`, `.github/workflows/digest.yml`, `llm-council.yml`, `validate.yml`, `idhazh-pipeline-tests.yaml`, `backend/tests/workflows/test_weights_and_model_refs.py`, `backend/tests/workflows/_harness.py`, `docs/reference/ci-model-runtime.md`, `docs/architecture/summarize/model-boundary.md` |

**`measure.yml` and `backend/utilities/runtime_sweep.py` are in neither list.** Row 2 reaches neither: `measure.yml`'s four weights downloads are inline, and its three cache keys read `candidate_cache_key`, whose **value** changes when row 1 changes the key shape while its **expression** does not. Same for `validate.yml:284`.

**`backend/tests/workflows/test_pinned_versions.py` is deliberately not in PR-B's list.** Its caller set comes from `_fetch_script_callers` at `:41`, which discovers by scanning a workflow's own `run:` bodies for `LLAMA_SHARED_SCRIPTS`. Row 2 moves no workflow on or off its own `run:` line, so nothing in that file changes. It is a **gate row 2 must not break**, which is not the same as a file row 2 writes - see row 2's acceptance gates.

**`_harness.py` is not delete-only.** `WEIGHTS_CACHE_SUFFIX: Final = "v4"` lives at `:357` and the key change edits it; `DRAFT_REF_OUTPUTS` at `:329` dies; four `WEIGHTS_CHECKS` entries die. That matters because `_harness.py` is plan 46's contested file.

**PR-A shares no file with plan 45 or plan 46.** It can start the hour the user authorizes.

### Section 1b - Readiness, computed rather than read off a letter

| When this is true | Dispatch | Do not dispatch |
| --- | --- | --- |
| now | **PR-A** (row 1) | anything else |
| PR-A merged to `main` | **PR-B** (row 2) | anything else |
| PR-B's second commit merged | **D1** - `idhazh-pipeline-tests.yaml`, `candidate_models_file: config/models/gemma-4-e4b-qat.json` | D2 |
| D1 finished | **D2** - same workflow, `candidate_models_file` empty | D3 |
| D2 finished and the key read back | **D3** - `llm-council.yml`, `date` empty | a re-run of D1 or D2 |
| D3 read a hit | the plan is closed | - |

**Peak workers: 1.** Two dispatchable rows and the second imports contracts the first declares, so there is never a second ready row. **What would make this plan two wide is bringing row 5 back**, which needs plan 46 closed - the third line of the scope-out table.

### Section 1c - The one interlock with plan 46

Plan 46 is in flight with three worktrees cut. PR-B shares three files with it: `digest.yml` (six of plan 46's ten pull requests write it), `validate.yml` (its row 11, wave 4) and `_harness.py` (a group-A row in wave 1).

**Ruling: land PR-B when it is ready and let plan 46's branches merge `main` in.** PR-B's `_harness.py` hunk is four dictionary entries at `:258-313`, one constant at `:329` and one literal at `:357`, textually far from plan 46's `COMMIT_REFRESH_PATHS` work. Its `digest.yml` diff is about -15 net against plan 46's much larger ones. A small branch rebasing under a large one is the cheap direction; the reverse stalls a Level-4 fix behind a ten-pull-request plan's first wave. **The owner tells plan 46's owner the file list at PR-B's dispatch**, so a rebase is expected rather than discovered.

## Section 1d - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent any shape below; it reads this section.** No persisted payload changes, so CLAUDE.md section 11 owes nothing - `gguf_cache_hit` appears in no file under `schemas/` and is a CLI argument, not a declared shape.

### C1 - What the printer publishes (row 1)

`backend/utilities/model_refs.py` keeps one question - which model files will a shell see, and is every field safe - at a new arity. It stays **stdlib-only and runnable by path**: `python3 backend/utilities/model_refs.py <verb>`. It imports nothing from `idhazh` and nothing from `utilities`.

**Row 1 is additive on published keys. It deletes exactly one thing: the `--repo-root` argument.** No caller passes it - verified across all five invocations - so that deletion reaches no workflow. Every other change adds.

**Four verbs. All four take `--config-root`, default `config`.**

| Verb | Callers | What it prints |
| --- | --- | --- |
| `configured` | `.github/actions/model-server/action.yml` (new first step), `digest.yml:178`, `llm-council.yml:171`, and `measure.yml:184` through `--also-configured` | six `summarize_*` lines |
| `candidate` | `idhazh-pipeline-tests.yaml:123`, `measure.yml:184`, `validate.yml:160` | `KEY=value` lines at the caller's `--prefix` |
| `files` | `fetch-model-runtime.sh`, and the verify step in every caller | **TAB-separated rows**, one per file |
| `cache-key` | `idhazh-pipeline-tests.yaml:167` only | one line, `cache_key=<64 lowercase hex>` |

**`cache-key` has exactly one caller.** The composite action does not use it - it reads `summarize_cache_key` off its `configured` call, one step, one traversal.

**`files` output: seven TAB-separated columns, one row per file, weights first, then companions in declared order.** Never a missing field; an absent optional is an empty field.

| Column | Content | May be empty |
| --- | --- | --- |
| 1 | `repo` | no |
| 2 | `revision` | no |
| 3 | `file` | no |
| 4 | `sha256` | no |
| 5 | `flag` | **yes** - every weights row is empty here today |
| 6 | **the landed relative path** - `MODELS_DIR` plus the validated `file` | no |
| 7 | **`byte_count`, the entry's declared size** | **yes** - empty means the entry declares no size |

**Column 6 is what removes the shell's composition.** `fetch-model-runtime.sh` writes it verbatim as the `-o` destination and composes no path of its own. **Column 7 is what keeps the declared-size cross-check alive** - `validate.yml:325-333` measures `stat -c %s` against it today, and that check moves into the shared verify body rather than being deleted by the rewrite. It then runs on a cache hit as well as a miss, which it does not today, and it gives production a check it has never had.

**The file ends with a trailing newline.** `read` on an unterminated last line assigns the fields and returns non-zero, so bash skips that row while `wc -l` under-counts by the same one - and the fetch script's count check would then agree with itself about a set it never fetched.

**The companion list is read from `companion_files` and from nothing else.** Zero committed `config/models/*.json` carries a `draft` key. An entry with no `companion_files` prints exactly one row - which is the live pointer `config/models/qwen3.5-9b-q4km.json`.

**Three keys are added to `configured` and `candidate`**, so nothing downstream composes a path or re-reads the model file:

| Key | Value |
| --- | --- |
| `weights_path` | column 6 of the weights row |
| `cache_key` | the C5 digest. `candidate` already publishes it; `configured` gains it |
| `id` | the model alias. `CANDIDATE_FIELDS` already carries `id`; `CONFIGURED_FIELDS` gains it |

**Every key `configured` emits begins `summarize_`. Every key `candidate` emits begins the caller's `--prefix`.** `configured` emits these six and no seventh: `summarize_repo`, `summarize_revision`, `summarize_file`, `summarize_id`, `summarize_weights_path`, `summarize_cache_key`. It does **not** emit `models_file`; that key belongs to `candidate` alone.

**Why the prefix is mandatory rather than tidy.** `measure.yml:184` runs `candidate --prefix candidate_ --also-configured`, writing both sets into one `$GITHUB_OUTPUT` block, and `validate.yml:160` calls `candidate` with an **empty** prefix. The day somebody combines the two - legal today, nothing refuses it - a bare `cache_key` from each lands in one output block and GitHub resolves it last-write-wins with nothing red. A unit test asserts it cannot happen: build one fixture config tree, call `configured_rows()` and `candidate_rows(..., prefix="")` over it, and assert `set(configured) & set(candidate) == set()` with a message naming every colliding key.

**`_draft_rows` survives on the `candidate` verb, as a projection.** It is the reason row 1 deletes no key.

| Case | What it does |
| --- | --- |
| what it calls | the **same row builder `files` calls** - one traversal, validated once. It takes rows `[1:]`, the companions, and never re-reads the entry |
| entry declares none | four empty strings, exactly as today. `measure.yml`'s `[ -n "${DRAFT_FILE}" ]` guard skips. No change |
| entry declares two or more | **raises**, naming the models file and the count. Not truncation |

The two-companion refusal is free - no committed entry declares two - and it closes a defect that is live on `main` now: `_draft_rows` publishes companion 0 while `_cache_key` digests all of them, so a two-companion dispatch today keys on two files, fetches one, saves a short bench entry, and the server arm restores it and starts without a file it declared.

The declaring line carries the removal condition (Guardrail #6):

```
The first companion's four refs, projected from the rows `files` prints.

`measure.yml` fetches its weights inline and reads these four keys. Delete this
function and its four keys when that file fetches through
`fetch-model-runtime.sh`; nothing else reads them.

One companion is all this shape can carry, so an entry declaring two is refused
rather than truncated: a short set starts a server missing a file and reports a
measurement for a model that never ran.
```

**`models_file` is published as the proved path, not the raw input** - `path.relative_to(<the --config-root>).as_posix()`. The config root, not the repository root: the committed value is `models/qwen3.5-9b-q4km.json`, and `candidate-config` writes it back into a scratch `idhazh.json` under `backend/var/candidate-config`, which a repository-root-relative value would make unreadable.

### C2 - The grammar, and where it is declared (row 1)

**Declared in `model_refs.py` itself, with `re.compile` and nothing but stdlib `re`.** Not imported from `backend/utilities/measure_llm.py`, and not moved to a shared third module. Both break a job that has no install:

| Direction | What breaks |
| --- | --- |
| `model_refs.py` imports `measure_llm` | `from utilities.measure_llm import ...` resolves only because each caller ran `pip install -e .` and hatchling's editable `.pth` exposes all of `backend/`. `pyproject.toml:175` declares `packages = ["backend/idhazh"]`; `utilities` is not a declared package. Fixing it properly means `PYTHONPATH=backend python3 -m utilities.model_refs` at **six** invocation sites, two of them in files plan 46 owns - and the failure is invisible to every local gate, because pytest sets `pythonpath = ["backend"]`. `measure.yml:158-164` carries the written invariant, added after a dispatch died on `ModuleNotFoundError` |
| a shared third module | `measure_llm.py` runs **two** ways - by path at `measure.yml:376` in the `llama-bench` job, which has no `setup-python` and no install, and as `utilities.measure_llm` under pytest. No single plain import statement works in both |

**Every pattern keeps its `^` and `$`** - `measure_llm.py` has them and the equality test is on `.pattern`. **Every pattern is applied with `re.fullmatch`, never `re.match` and never `re.search`**: `$` matches before a trailing newline, so `match` admits a value the anchors look like they refuse, and that value then writes a stray line into `$GITHUB_OUTPUT`.

**The rules. Applied to every value the printer emits, at the one point that writes a row.**

| Emitted value | Rule | State |
| --- | --- | --- |
| `repo` | `^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$` | exists as `REPO_RE`, `measure_llm.py:28`. Gated |
| `revision` | `^[0-9a-f]{40}$` - a commit, never a branch name | exists as `REVISION_RE`, `measure_llm.py:32`. Gated |
| weights `file` | `^[A-Za-z0-9][A-Za-z0-9._-]*\.gguf$` | exists as `GGUF_RE`, `measure_llm.py:29`. Gated. **The live gap** |
| companion `file` | `^[A-Za-z0-9][A-Za-z0-9._-]*$` - the same segment rule, **without the suffix rule** | new. `CompanionFile` has no suffix rule because a companion may be a projector, an adapter or a vocoder; importing `GGUF_RE` here would ship a second grammar for one field |
| `sha256`, weights and **every** companion | `^[0-9a-f]{64}$`, **required, no exception** | new |
| `id` | `^[a-z0-9]+(?:-[a-z0-9]+)*$` | new. **Gated against `SLUG_PATTERN` at `backend/idhazh/contracts/base.py:49`** |
| `quantisation` | `^[A-Za-z0-9_.-]+$` | new |
| `byte_count` | **empty, or** `^[1-9][0-9]*$` on the string the printer is about to emit. Empty means the entry declares no size. Non-empty refuses `0`, a leading zero, a sign and a float, none of which `stat -c %s` will ever equal | new. No check at all today, and a newline in it writes extra lines into `$GITHUB_OUTPUT` |
| `flag` | **empty, or** `^--?[A-Za-z0-9][A-Za-z0-9-]*$` - one or two leading dashes, then a name. No `=`, no space | new. **One dash is legal**: llama.cpp's short form for a draft model is `-md`, and `config/models/qwen3.5-9b-q4km.json`'s own `server` block carries `-fa`, `-ctk`, `-np` and eight more |
| the set | two entries resolving to one filename is refused | exists, `measure_llm.py:71-75` |
| **every emitted value, last** | the emitted string is **empty, or `^[\x21-\x7E]+$`** - printable ASCII with no space. **Empty is legal for exactly two emitted values, `flag` and `byte_count`, and refused for every other.** No newline, no tab, no non-ASCII | **the backstop, and the load-bearing row** |

**The backstop is written as a character class, never as `str.isprintable()`.** `'e\u0301'.isprintable()` is `True` and `'\u2215'.isprintable()` is `True`; a `repo` carrying either builds a Hugging Face URL that is not the one a reviewer read. And it is no-space rather than admit-space on purpose: `one_bare_word` refuses whitespace today, so a backstop that admitted it would be a regression dressed as a hardening. A tab is refused because a tab ends a TSV column early.

**Five emitted values have no rule of their own, and that is a decision rather than an omission.**

| Emitted value | Composed from | Why no rule |
| --- | --- | --- |
| `ref` | `f"{repo}@{revision}:{file}"` | all three parts ruled, and its only consumer re-parses it with the same three patterns at `measure_llm.py:58-75`. **The invariant to state beside it: `@`, `:` and `,` stay outside the `repo`, `revision` and `file` classes, or `parse_model_refs` mis-splits** |
| `weights_path`, column 6 | `MODELS_DIR` + `/` + the ruled `file` | a rule here would be a second grammar for `file` plus a constant. The `/` is the printer's, not the config's |
| `cache_key` | `hashlib.sha256(...)` over ruled columns 1 to 4 | hex by construction. **Asserted `^[0-9a-f]{64}$` anyway** - that assertion is what catches a worker who keeps the hyphen-join (ESCALATE trigger 4) |
| `models_file` | the dispatch input | **containment is proved, not pattern-checked.** `resolve_under_config` resolves the path, proves `is_relative_to` the config root, requires `.json` and `is_file()`. Stronger than a regex, because `..` is what resolving exists to defeat. It still clears the backstop, which admits `/` |

**All five committed model files clear every rule above**, checked field by field on 2026-09-22 - four `id` values, three `quantisation` values, five `byte_count` integers, five weights filenames, one companion filename and one `flag`. The grammar refuses nothing that exists today.

**Three duplications, each gated by a test rather than by attention.** One contract-tier test in `test_weights_and_model_refs.py` - which already does `from utilities import model_refs` at `:12` - holds an **explicit** tuple `("REPO_RE", "REVISION_RE", "GGUF_RE")` and, for each name, asserts it exists on both modules and that `.pattern` and `.flags` are equal. Flags are not optional: `re.IGNORECASE` on one side is a second grammar sharing one pattern string. A fourth assertion covers the slug: `model_refs.SLUG_RE.pattern == idhazh.contracts.base.SLUG_PATTERN`. **The test can import `idhazh`; the printer cannot. That asymmetry is why the copy is legal and why the gate is mandatory.** The tuple is explicit, never derived by intersecting the modules.

**Three Guardrail #11 citations are wrong and are corrected in the commit that touches each file.** `model_refs.py:1-4` (row 1), `action.yml`'s comment above the fetch step and `fetch-model-runtime.sh`'s header (row 2). The replacement sentence names what is true: these values are pasted into `run:` bodies where the Actions engine substitutes before bash parses, so the printer refuses them before a shell sees one.

### C3 - The refusal message (row 1)

**On a malformed entry the verb raises and exits non-zero. Not a skip**: a skipped companion is a server that fails to start over a missing file, or one that starts and silently does nothing.

**Every refusal names four things, in this order: the models file, where in it, the rule in plain words, and the offending value in `repr()`** so a control character is visible. "Where in it" has three forms and no fourth.

| Form | Shape |
| --- | --- |
| a field with a JSON location | the dotted path including every list index: `summarize.companion_files[0].file` |
| a TSV column | **the JSON location of the field that fills it, never a column number.** Column 6 is reported against the `file` it was composed from, with the composed value in `repr()`: `summarize.file (landed path)`. A column number is a fact about the printer; the field is the fact about the thing the maintainer must edit |
| a whole-set rule, where no single field is at fault | the entry, the rule, then **every** participating location and value. One location would name a file that is not wrong on its own |

**Never print a regex. Never print only the first offender when the rule is about a pair.**

```
config/models/gemma-4-e4b-qat.json: summarize.companion_files[0].file:
  not one path segment: '../../x.gguf'
config/models/qwen3.5-9b-q4km.json: summarize.revision:
  not a 40-character commit: 'main'
config/models/x.json: summarize: two files land on one name:
  summarize.file 'x.gguf' and summarize.companion_files[1].file 'x.gguf'
```

### C4 - The landed path, composed in exactly one place (rows 1, 2)

| Step | What it removes |
| --- | --- |
| `model_refs.py` declares `MODELS_DIR: Final = "backend/models"`, its only spelling, and composes column 6 and `weights_path` from it | the composition at nine sites |
| `fetch-model-runtime.sh` writes column 6 verbatim. Its only `backend/models` literal is the `mkdir -p` | three literals in the script |
| Each caller reads a `weights_path` where it spells `backend/models/<file>` today | six literals across four workflows, plus `action.yml:147` |
| `backend/idhazh/llm/server.py:437-439` is corrected in row 1 | a **false docstring plan 41 landed**: it says `model_refs.py` "imports it rather than spelling the join a second time", and `model_refs.py` imports nothing from `idhazh` |

**No cross-module test between `model_refs.py` and `idhazh.llm.server`.** `companion_path` at `server.py:434` is one line with one caller at `:492`; a test asserting two values agree would not have caught the docstring that is already wrong.

### C5 - The cache key (rows 1, 2)

| Property | Value |
| --- | --- |
| Shape | **a fixed-width SHA-256 hex digest**, never a join. The existing hyphen-join reaches 519 characters at seven files, past GitHub's 512-character cap |
| What it covers | `repo`, `revision`, `file` and `sha256` per row, in the order `files` prints them |
| Serialisation, stated so two implementations agree | `hashlib.sha256(b"\n".join(b"\t".join(f.encode("ascii") for f in (repo, revision, file, sha256)) for each row)).hexdigest()`. TAB between fields, LF between rows, **no trailing LF**, ASCII, lowercase hex. Computed by calling the same row function `files` prints, never by re-reading the entry |
| Why that is safe to spell as a plain `.encode("ascii")` | every one of those four columns has already passed its field rule and the backstop, so the digest can assume ASCII with no tab and no newline. **Nothing enters the digest that the grammar has not already seen** |
| What it must **not** cover | **column 5, `flag`** - it reaches the server command line, not the download, so digesting it discards the whole entry when the flag is edited for zero byte change. **Column 6** - derived from column 3. **Column 7** - derived from the bytes column 4 already digests, so digesting it would discard the entry the day somebody fills in a previously-empty `byte_count`. **The config root** - it is how the rows were found, never part of what is hashed |
| Why the config root is excluded, stated as a contract | D3 only hits because `idhazh-pipeline-tests.yaml` reads `backend/var/candidate-config` and `llm-council.yml` reads `config`, and two roots holding the same `summarize` entry must produce the same key. A unit test drives two config roots holding one entry and asserts one key. **A worker who "fixes" a cross-caller miss by putting the root into the key has destroyed the property that makes the closing dispatch work** |
| Shape assertion | the verb refuses to print anything but `^[0-9a-f]{64}$`. A worker who keeps the hyphen-join fails here rather than at 519 characters in a GitHub error nobody attributes |
| The suffix | `-v4` becomes `-v5`, declared once as `WEIGHTS_CACHE_SUFFIX` at `_harness.py:357`. **It is kept, and it is not a version of the key format** - it is the manual eviction handle for the three things the digest cannot see: an entry already poisoned, a llama.cpp release re-uploaded under one build tag, and a change to `install-llama-runtime.sh` that alters what lands in `backend/bin`, which is in `path:` and in no key component. It costs one character and zero bytes, because it rides the same invalidation the digest already causes. The alternatives on a bad day are `gh cache delete`, which needs a permission and leaves no record in git, or editing a declared field to move the digest, which puts a lie in the config |
| Paths | unchanged: `backend/models` and `backend/bin`, together, on one key. **No `restore-keys`** - a prefix restore would serve a stale file set under a key that says otherwise, which is the wedge this plan exists to close |

**Both spellings move in one commit.** `action.yml:93` and `idhazh-pipeline-tests.yaml:167` are the same format written twice; `action.yml:47-52` records them drifting once already. The guarding test at `test_weights_and_model_refs.py:344` scopes its closed world to the action's callers, and pipeline-tests does not call the action - so the hand-copy is invisible to a test whose docstring says there is one key now. Row 2 widens that closed world to **every `actions/cache` step whose `path:` names `backend/models`**, and adds a resolved-value equality clause across that set.

**That equality clause is a guard, not an oracle.** It is green the day it is written - the two keys have different expression text and the same resolved value today - and its job is to refuse a commit that moves one spelling and not the other. A worker must not try to make it fail first.

### C6 - What `fetch-model-runtime.sh` does (row 2)

Environment, and nothing else: `GITHUB_TOKEN` for the pinned release lookup, `CONFIG_ROOT` with no default in the script. **It stops reading `WEIGHTS_REPO`, `WEIGHTS_REVISION`, `WEIGHTS_FILE`, `DRAFT_REPO`, `DRAFT_REVISION` and `DRAFT_FILE`** - those six are the relay.

```
 1. set -euo pipefail                          unchanged, top of file
 2. Refuse any positional argument             [ "$#" -ne 0 ] -> usage, exit 2
 3. : "${CONFIG_ROOT:?CONFIG_ROOT must name the config tree this job reads}"
 4. : "${GITHUB_TOKEN:?GITHUB_TOKEN looks the pinned release up}"
 5. TSV="$(mktemp)"; trap 'rm -f "$TSV"' EXIT
 6. python3 backend/utilities/model_refs.py files --config-root "$CONFIG_ROOT" > "$TSV"
 7. rows=$(wc -l < "$TSV")
    [ "$rows" -ge 1 ] || { echo "the model declares no files" >&2; exit 1; }
    [ -z "$(tail -c 1 "$TSV")" ] || { echo "the printer left the last row unterminated" >&2; exit 1; }
 8. . .github/scripts/install-llama-runtime.sh
 9. mkdir -p backend/models                    the only backend/models literal
10. downloaded=0
11. # shellcheck disable=SC2034  # `flag` and `declared` are the caller's, not the fetch's
    while IFS=$'\t' read -r repo revision file sha256 flag dest declared <&3; do
      [ -n "$dest" ] || { echo "row $((downloaded + 1)) has no landed path" >&2; exit 1; }
      curl -fsSL --retry 3 --retry-all-errors -o "$dest" \
        "https://huggingface.co/$repo/resolve/$revision/$file?download=true" </dev/null
      printf '%s  %s\n' "$sha256" "$dest" | sha256sum --check
      downloaded=$((downloaded + 1))
    done 3< "$TSV"
12. [ "$downloaded" -eq "$rows" ] \
      || { echo "downloaded ${downloaded} of ${rows} declared files" >&2; exit 1; }
```

**Refusal order: arguments, then environment, then the whole file set's grammar, then the install, then per-row bytes, then the count.** Steps 6 and 8 are in that order because the file's own header promises it - a caller that got a field wrong fails in a second rather than after unpacking a runtime it will not use.

Four things in that listing are load-bearing and a worker will not guess them:

- **`mktemp`, not `backend/var`.** `.gitignore:40` ignores `backend/var/`, so it is absent from a fresh checkout. `validate.yml` and `idhazh-pipeline-tests.yaml` get it from `candidate-config`, `digest.yml` gets it as a side effect of an artifact download, and **`llm-council.yml` does not get it at all on a night where the registered tenant selects no work** - `actions/download-artifact` with a `pattern:` creates nothing when nothing matches. `mktemp` needs no directory, is cleaned by the trap, and adds no path literal.
- **File descriptor 3, not stdin.** `done < "$TSV"` hands the loop body the same fd 0, so a body command that reads stdin eats rows exactly as it would from a pipe. Reading a file rather than a pipe is what keeps the loop out of a subshell and keeps `downloaded` alive; it is not what protects the loop's input.
- **`downloaded=0` before the loop.** Under `set -u`, `downloaded=$((downloaded + 1))` on an unset variable exits 1 on the first row.
- **`rows` from `wc -l`, paired with step 7's trailing-newline check.** Without that check, `read` drops an unterminated last row and `wc -l` under-counts by the same one, so step 12 agrees with itself about a set it never fetched.

**Step 12 is a cheap invariant assertion, not the control.** Under `set -euo pipefail` a failed `curl` or a failed digest already exits, and the no-`if:` verify re-reads every declared row on both the hit and the miss path. It earns its two lines by naming the count inside the script rather than inside a `sha256sum` pipe, and by protecting a future caller that runs the fetch with no verify behind it.

**Python is there, and the property rather than the line numbers is what to rely on: the printer needs `python3` and nothing installed.** All four callers run `actions/setup-python@v7` before the fetch, and `ubuntu-latest` carries a system `python3` besides. The script spells no `PYTHONPATH` and no `-m`, because C2 keeps the printer runnable by path.

**Where `CONFIG_ROOT` comes from, per caller:**

| Caller | `CONFIG_ROOT` | Built by |
| --- | --- | --- |
| `action.yml` (for `digest.yml` and `llm-council.yml`) | `config` | the action's new `config_root` input, default `config`. Neither caller passes it |
| `validate.yml:308`, the `qualify` job | `backend/var/candidate-config` | `./.github/actions/candidate-config` at `:268`, before the cache step at `:279` |
| `idhazh-pipeline-tests.yaml:182`, the `cases` job | `backend/var/candidate-config` | the same action at `:137`, before the cache step at `:162` |

### C7 - The composite action after row 2 (row 2)

**Ten inputs become four: `github_token`, `port`, `llama_cpp_build`, `config_root`** (`required: false`, `default: 'config'`). The three weights inputs and the four draft inputs go.

**It gains an `outputs:` block, which it has none of today.** Without one, `steps.<id>.outputs.weights_path` at `digest.yml:583` and `:604` is empty and the `sha256sum` runs on a directory.

```yaml
outputs:
  weights_path:
    description: 'The landed relative path of the weights, as the printer composed it.'
    value: ${{ steps.model.outputs.summarize_weights_path }}
```

| # | Step | After |
| --- | --- | --- |
| 1 | **new, `id: model`** | `env: CONFIG_ROOT: ${{ inputs.config_root }}`. It runs `OUT=$(python3 backend/utilities/model_refs.py configured --config-root "$CONFIG_ROOT")`, asserts `^cache_key=` carries 64 hex, then `printf '%s\n' "$OUT" >> "$GITHUB_OUTPUT"`. **Capture then append, never append straight**: a printer that dies mid-stream would otherwise leave half its keys in `$GITHUB_OUTPUT`. ESCALATE trigger 4 is enforced on this step |
| 2 | Cache weights and runtime, `id: weights` | `key: llm-${{ steps.model.outputs.summarize_cache_key }}-${{ inputs.llama_cpp_build }}-v5`. Paths unchanged, no `restore-keys` |
| 3 | Fetch runtime and weights | condition unchanged; `env:` becomes `GITHUB_TOKEN` and `CONFIG_ROOT` only |
| 4 | Verify the weights | **no `if:`**, unchanged position. `env: CONFIG_ROOT` - **it is a separate step and inherits nothing**. Body in C7a. The inline Python at `:136` goes |
| 5 | Start the model | `LLAMA_WEIGHTS: ${{ steps.model.outputs.summarize_weights_path }}`. The composition at `:147` goes |
| 6 | Check model health | the alias comes from `steps.model.outputs.summarize_id` through `env:`; the `/props` check reads `steps.model.outputs.summarize_file`. The inline Python at `:183` goes |

**The key is computed inside the action, never passed in.** A caller-computed key is hop 3 of the four this plan deletes, and it would cost three lines each in `digest.yml` and `llm-council.yml`. Computed, it costs zero lines in both callers and it is provably the set the loop downloads.

#### C7a - The verify body, shared by all four callers

```bash
set -euo pipefail
python3 backend/utilities/model_refs.py files --config-root "$CONFIG_ROOT" > "$TSV"
awk -F'\t' '{print $4 "  " $6}' "$TSV" | sha256sum --check
while IFS=$'\t' read -r _ _ _ _ _ dest declared; do
  [ -n "$declared" ] || continue
  observed=$(stat -c %s "$dest")
  [ "$observed" = "$declared" ] || {
    echo "$dest is $observed bytes; its entry declares $declared" >&2; exit 1; }
done < "$TSV"
```

`pipefail` is load-bearing: without it a printer that exits non-zero is masked by `sha256sum`'s own status. Empty input still fails - `sha256sum --check` reports "no properly formatted checksum lines found" and exits 1 - so no extra row assertion is needed. **Two spaces between digest and path** is the canonical GNU form and matches every other check in this repository; one space also works.

**The size loop is what keeps `validate.yml:325-333`'s declared-size cross-check alive.** It is in the shared body rather than per caller because that way it runs on a hit as well as a miss, costs zero per-caller lines, and removes a paste site instead of relocating it. `measure.yml:596` and `:923` keep their own copies and their own pastes, out of scope.

### C8 - What stops a bad cache entry being written (row 2)

| Half | Where | Runs on a hit? |
| --- | --- | --- |
| **restore-time - the control** | a step with **no `if:`**, in every caller, after the fetch and before the first read of `backend/models` | **yes.** This is the only one that does |
| download-time - an early exit | inside the fetch loop, per row | no. The script runs behind `cache-hit != 'true'` |

**`actions/cache@v6` does not save when the job failed.** Its manifest declares `post-if: "success()"`; `save-always` is inert and deprecated. So a failed verify writes no entry - on the miss path as well as the hit path, because the verify sits in the same job and `post-if` runs after every step.

**The door `post-if` cannot see** is a fetch loop that exits 0 having downloaded fewer files than the model declares. C6 step 12 names it inside the script; the no-`if:` verify catches it either way.

**The standing rule:** no step between the cache restore and the verify may carry `continue-on-error: true`, and the cache step is never split into `actions/cache/restore` plus a save with `if: always()`. Either one makes `post-if: success()` untrue. Neither exists in the fetch path today; the 18 `continue-on-error` lines across `digest.yml`, `measure.yml` and `validate.yml` are all ledger, harvest and push steps that run after the server is up.

### C9 - The commit order that protects the verify step (row 2)

**The first commit is tests only, and it lands RED.** The second commit does everything else.

| Clause | State when written |
| --- | --- |
| **the paste rule** (C10) | **red: 8 sites** - `digest.yml:604`, `idhazh-pipeline-tests.yaml:201`, `validate.yml:320`, `:321`, `:329`, `:367`, `:368`, `:399` |
| **every printed row reaches `sha256sum --check`** in each verify step | red: no verify step reads the printer today |
| **the verify step's config root equals the fetch step's** | red: the fetch step names no root today |
| **the companion-sensitivity oracle** - two fixture entries differing only in one companion digest produce different rendered keys | red: `action.yml:93` names no companion |
| **the resolved-value equality guard** across every `actions/cache` step whose `path:` names `backend/models` | **green, and it stays green.** It is a guard against one spelling moving alone |
| the three clauses already green at `test_weights_and_model_refs.py:59-88` - closed-world discovery, the three step names in order, no `if:` on the check | green, and not rewritten |

**Why the order is the control.** The most likely failure in this plan is a worker seeing two `sha256sum --check` calls, reading the workflow step as redundant, deleting it, and going green everywhere. With the tests landing first and red, the worker goes red locally before the push. **One review rule rides with it: row 2's diff must not remove `assert "if" not in check` at `test_weights_and_model_refs.py:84`.**

**`WEIGHTS_CHECKS` shrinks from eight entries to four, and `test_weights_and_model_refs.py:71` stays an equality.** Discovery through `_weights_fetch_steps` still finds eight jobs, because the rewritten fetch script still spells `huggingface.co/`. The written table keeps `measure.yml`'s four; the four converted jobs are **derived** from the shared shape at assertion time. **Do not weaken `:71` to a subset or a difference assertion.** A converted job's digest source is the printer: the anchor string is `model_refs.py files`, and the check asserts the body pipes it into `sha256sum --check`.

### C10 - The paste rule, stated in terms a test can evaluate (row 2)

**In every job of the closed world, no `run:` body carries an expression that resolves to a value the printer published.**

| Clause | Rule |
| --- | --- |
| the closed world | computed, never listed: every `(workflow, job)` that calls `./.github/actions/model-server` (`_harness._model_server_callers`) or runs `.github/scripts/fetch-model-runtime.sh`. A ninth job that starts fetching weights joins it with no edit |
| what it walks | `_harness._steps(workflow, job)` - which resolves a repository-local composite action's steps in place, so the action's own `run:` bodies are inside the closed world - and from each step the `run:` string. **`env:`, `with:`, `key:` and `if:` are out of scope**: the whole point of the rule is that `env:` is where these values are allowed to be |
| what it matches | every `${{ ... }}` by `re.findall(r"\$\{\{(.*?)\}\}", body, re.S)`. Take the expression's dotted segments; skip it unless the **first** is `steps`, `needs` or `inputs` - `github.run_id` ends in `_id` and is not a printer value. Let `S` be the **last** segment |
| the predicate | the body fails if `S in PRINTER_KEYS` or `S.endswith("_" + key)` for any `key in PRINTER_KEYS`. The suffix arm catches the prefixed spellings - `candidate_sha256`, `summarize_file`, `candidate_models_file` - without the test holding a prefix list that goes stale |
| `PRINTER_KEYS` | **read from the printer, never retyped**: `set(model_refs.CANDIDATE_FIELDS) | set(model_refs.CONFIGURED_FIELDS) | set(model_refs.PUBLISHED_EXTRA)`, where `PUBLISHED_EXTRA` is a new `model_refs` constant naming exactly `("models_file", "ref", "byte_count", "cache_key", "weights_path")`. **Row 1 adds it, and the module's own emit path iterates it** - so a key published later without joining that tuple fails the printer's own round-trip test. A literal list in the test file is the one implementation this clause forbids: it passes forever while admitting the ninth site |
| the failure message | names the workflow, the job, the step name, the offending expression and the key it matched, and says the repair in one line: *move it to `env:` and read it as a shell variable* |
| what it cannot settle | `measure.yml`'s five paste sites. They reach neither the action nor the script, so the closed world excludes them by construction rather than by exemption |

## Section 2 - Row 1 - The printer learns the whole file set, and the grammar closes

- **Scope:** Give `model_refs.py` a `files` verb printing seven columns, a `cache-key` verb, three new published keys, one spelling of the models directory, and a field grammar that refuses every value a shell or a `run:` body could misread - deleting no published key and no argument but `--repo-root`.
- **Files touched:**
  - `backend/utilities/model_refs.py`
  - `backend/tests/workflows/test_weights_and_model_refs.py`
  - `backend/tests/workflows/test_pipeline_tests_workflow.py` (it imports `candidate_rows`, `configured_rows` and `CONFIGURED_FIELDS` at `:683-694`)
  - `backend/idhazh/llm/server.py` (the false docstring at `:437-439`, and nothing else in the file)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q` and `python -m pytest backend/tests/test_measure_llm.py -q`; CI - full suite. No dispatch.
- **Oracle:** **stated against the verb production runs today, not against the new one.** Run the existing `candidate` verb against a fixture models file whose `summarize.file` is `../../etc/passwd.gguf`, and a second whose `summarize.file` is `x$(id).gguf`; assert a non-zero exit naming the field. **Today both exit 0 and print the value into `$GITHUB_OUTPUT`.** Second failing case: run `candidate` against a fixture declaring seven companions and assert the `cache_key` row is at most 64 characters - **today the hyphen-join prints 519, past GitHub's 512-character cap.** The `files` verb's own refusal cases are coverage of new code rather than an oracle: a test of a verb that does not exist errors on invocation rather than failing. **What it cannot settle:** whether a shell or a `run:` body ever sees an unvalidated value. No test here executes `fetch-model-runtime.sh`; row 2's paste rule settles it.
- **The two tests this row must rewrite, and the one it must not:**

 | Test | Asserts today | Must assert after | Why that is not tautological |
 | --- | --- | --- | --- |
 | `test_an_entry_with_no_draft_head_keeps_the_key_it_already_had` at `:494` | the four `draft_*` keys are empty, and **`cache_key` equals the entry's own `sha256` field** | **rename it `test_the_key_moves_when_the_declared_set_moves`.** Two fixture entries identical except that one declares a companion produce **different** keys; and the no-companion entry's key is **not** equal to any single field's value | two different inputs, one comparison - so it cannot pass by running the same call twice. The second clause is what catches a digest implemented as "return the weights sha256". **A clause that calls the printer twice with the same input and compares the results asserts nothing and does not satisfy this row** |
 | a new unit test | - | two config roots holding the same `summarize` entry produce **one** key | it is what makes the closing dispatch's cross-caller proof possible (C5) |
 | `CANDIDATE_STEPS` at `:407-410` and `published[f"{prefix}draft_{field}"] == value` at `:485` | the `candidate` verb publishes the four `draft_*` keys at both prefixes | **unchanged.** Row 1 deletes no key, so this survives untouched | - |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Row 1 is additive on published keys.** `measure.yml:150-153` publishes four `candidate_draft_*` job outputs consumed by four arms at `:308-331`, `:503-506` and `:853-856`, and `measure.yml` is in neither pull request. A deleted step output resolves to empty rather than failing, so the `:308` guard would go false, the draft would not be fetched, the no-`if:` draft verify at `:326` would become a no-op that exits 0, and the runtime arm would report speculative-decode throughput for a configuration that never ran. `config/models/gemma-4-e4b-qat.json` declares a companion today, so this is live machinery, not a future shape | Carmack and Fowler |
 | 2 | `_draft_rows` survives on `candidate` as a **projection of the rows `files` prints**, so the two cannot disagree, and **refuses an entry declaring two or more companions**. Today it truncates in silence while `_cache_key` digests all of them | Carmack |
 | 3 | The grammar is **declared in `model_refs.py`** with stdlib `re`, gated by equality tests against `measure_llm.py` (three patterns) and `contracts/base.py:49` (the slug). Both alternatives break a job that has no install, and the import failure is invisible to every local gate | Carmack |
 | 4 | Every pattern keeps `^`/`$` and is applied with `re.fullmatch`. `$` matches before a trailing newline, so `re.match` admits a value the anchors look like they refuse | Andre |
 | 5 | The backstop is `empty, or ^[\x21-\x7E]+$`, and **empty is legal for exactly `flag` and `byte_count`**. Every weights row's column 5 is empty, and `byte_count` empty is the declared "nobody has fetched this yet" signal - a backstop that refused empty would take the daily run down on the first merge | Andre |
 | 6 | The backstop is a character class, never `str.isprintable()`. That call admits `e` with a combining acute and DIVISION SLASH, either of which builds a hub URL that is not the one a reviewer read | Andre |
 | 7 | `flag` allows **one or two** leading dashes. llama.cpp's short form for a draft model is `-md`, and the live model's own `server` block carries eleven single-dash flags | Andre |
 | 8 | The weights `file` gets the `.gguf` suffix rule; a companion `file` gets the segment rule **without** it. `CompanionFile` has no suffix rule because a companion may be a projector, an adapter or a vocoder | Andre |
 | 9 | **`byte_count` becomes column 7 of the `files` row**, so the declared-size cross-check moves into the shared verify body in row 2 rather than being deleted by the rewrite. It then runs on a hit as well as a miss, costs zero per-caller lines, and removes a paste site instead of relocating it | Carmack |
 | 10 | The cache key digests `repo`, `revision`, `file` and `sha256` only, with the serialisation spelled in C5. Not `flag` - it reaches the server command line. Not columns 6 or 7 - derived. **Not the config root** - excluding it is what makes the closing dispatch's cross-caller proof possible | Carmack and Andre |
 | 11 | All four verbs take `--config-root`, default `config`; `--repo-root` is deleted. No caller passes it, verified across all five invocations | Fowler |
 | 12 | Every `configured` key begins `summarize_`; every `candidate` key begins the caller's `--prefix`, asserted disjoint at the empty prefix. `--also-configured` writes both sets into one output block and `validate.yml` uses the empty prefix, so a bare `cache_key` from each would resolve last-write-wins with nothing red | Fowler |
 | 13 | `MODELS_DIR` is declared once here, and `server.py:437-439`'s docstring is corrected in the same commit. It claims `model_refs.py` imports `companion_path`; `model_refs.py` imports nothing from `idhazh` | Fowler |
 | 14 | `PUBLISHED_EXTRA` is a real module constant the emit path iterates, not a list in a test file. It is what makes row 2's paste rule read the printer instead of a copy | Andre |
 | 15 | The Guardrail #11 citation in `model_refs.py:1-4` is replaced. Its current sentence - "where a value carrying a space, a quote or a newline stops" - is also false: `'a"b'.split() == ['a"b']` | Andre |

- **What this row costs:** `_cache_key`'s string changes for **every** model, including no-companion ones, so every `qualify-*` and `bench-*` entry goes cold when PR-A merges. Both are dispatch-only paths, so the daily run pays nothing and the next dispatch pays once: 4.22 to 6.64 GB per candidate, download 57 to 338 s against a 38 to 95 s restore. `validate.yml`'s qualify misses up to 8-wide. **No run can fail on it.**
- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete `_draft_rows` and the `draft_*` keys here, as the draft said | Five workflows read them; `measure.yml` is in neither pull request, and the failure is silent - a guard goes false and a verify becomes a no-op | A bench arm measuring a model that never loaded its draft head, with the catching test deleted in the same commit | Carmack and Fowler |
 | 2 | Take `measure.yml`'s four job outputs and 14 consumer lines into this plan | The three inline `curl` blocks would still need a repo, revision and filename from somewhere, and the only non-relay answer is the `files` verb - so it collapses into the full conversion, in a file plan 46 owns | The plan's clean interlock, plus a bench dispatch to re-prove against a 330 min bound | Carmack |
 | 3 | `model_refs.py` imports the patterns from `measure_llm.py` | It resolves only through hatchling's editable `.pth`, which `pyproject.toml` does not pin. Doing it safely means `PYTHONPATH=backend python3 -m utilities.model_refs` at six invocation sites, two of them in `measure.yml` and `digest.yml` | Five workflow edits, a sixth spelling inside a shell script no test reads, and a `ModuleNotFoundError` class every local gate hides | Carmack |
 | 4 | A shared third module both import | It moves the trap into the file with two execution modes. `measure_llm.py` runs by path in `llama-bench`, which has no install, and as `utilities.measure_llm` under pytest | The same silent class, relocated | Carmack |
 | 5 | Keep the hyphen-join and add companions to it | It reaches 519 characters at seven files, past GitHub's 512-character cap, and nobody would connect that failure to its cause | Nothing saved over a digest | Fowler |
 | 6 | Bare `weights_path` and `cache_key` on `configured` | `--also-configured` at the empty prefix writes two `cache_key=` lines into one `$GITHUB_OUTPUT`, and the later silently wins | Ten characters saved, against a collision nothing refuses | Fowler |
 | 7 | A cross-module test asserting the printer's landed path equals `companion_path` | It polices one file out of six that spell `backend/models`, and it would not have caught the false docstring already on `main` | A test and an import coupling, for a property one constant already holds | Fowler |
 | 8 | Keep the declared-size cross-check where it is, or delete it | `validate.yml:333` reads it inside a `run:` body, so row 2's own paste rule fails on that line - leaving it was never available. Deleting it removes the only check that reads the config document against reality | Nine lines saved, against production never gaining the check | Carmack and Andre |

## Section 3 - Row 2 - The workflows read the model file, and the cache names the set it declares

- **Scope:** Make the fetch script read a config root and loop over the printer's rows; cut the composite action to four inputs and let it compute its own key, alias and weights path; delete the six relay blocks and five inline Python programs in the four callers; and move both weights cache keys - `action.yml:93` and the hand-copy at `idhazh-pipeline-tests.yaml:167` - onto the digest, in one commit.
- **Commit sequence:**

 | # | Commit | Contents | State |
 | --- | --- | --- | --- |
 | 1 | tests only | the paste rule; the two digest clauses; the verify-root clause; the companion-sensitivity oracle; the widened cache closed world and its resolved-value equality guard | **RED** on four clauses, green on the guard |
 | 2 | the change | the script, the action, the four callers including both cache keys, `_harness.py`, both doc pages | **GREEN** |

- **Files touched, with the line lists a worker acts on:**

 | File | Lines | What happens |
 | --- | --- | --- |
 | `.github/scripts/fetch-model-runtime.sh` | whole file | C6's twelve steps. Its only `backend/models` literal is the `mkdir -p`; three go (`:37`, `:42`, `:51`). **It must keep `. .github/scripts/install-llama-runtime.sh`** |
 | `.github/actions/model-server/action.yml` | `:12-47` inputs -> four; new first step `id: model`; `:93` key; `:107-115` env; `:128-143` verify body; `:147` `LLAMA_WEIGHTS`; `:183` alias; add the `outputs:` block | C7 |
 | `.github/workflows/digest.yml` | `:95-101` delete 7 job outputs - **`:98-101` are the draft four and `:95-97` the weights three** ; `:172-178` delete the `models` step whole ; **`:546` add `id: model_server`** ; `:550-552` delete ; **`:553` KEEP - it is `llama_cpp_build`** ; `:554-557` delete ; `:583` -> `${{ steps.model_server.outputs.weights_path }}` ; `:604` take the same value through a new `env:` entry and read `"$WEIGHTS_PATH"` in the body | 17 relay lines, net about -15 |
 | `.github/workflows/llm-council.yml` | `:77-83` delete 7 job outputs ; `:168-171` delete the `models` step ; `:311-313` delete ; **`:314` KEEP - `llama_cpp_build`** ; `:315-318` delete. **No `id:` needed** - the file holds no `backend/models` literal | 14 lines |
 | `.github/workflows/validate.yml` | `:100-102` and `:104-110` delete ; **`:99`, `:103`, `:111` KEEP** - `:270` needs the models file, `:367` the alias, `:284` the key ; `:294-308` fetch `env:` -> `GITHUB_TOKEN` and `CONFIG_ROOT: backend/var/candidate-config` ; **`:314-333` the verify step as ONE unit** -> C7a; `:320` defines `WEIGHTS` and `:321`/`:325` read it, so deleting `:320` alone leaves an unbound variable under `set -u` ; `:335-337` -> `weights_path` ; `:367-368` alias paste -> `env:` ; `:394-399` `--weights` -> `weights_path` | 6 of the 8 removed pastes are here |
 | `.github/workflows/idhazh-pipeline-tests.yaml` | `:167` the cache key ; `:172-182` fetch `env:` -> `CONFIG_ROOT: backend/var/candidate-config` ; **`:190-204` the verify step as one unit** - `:196` inline Python, `:201` paste and `:202-204` draft block all go ; `:245-247` -> `weights_path` ; `:270-274` inline Python -> `candidate_id` ; `:323-327` -> `weights_path` ; `:350-354` inline Python -> `candidate_id` | 3 of the 5 inline Python programs |
 | `backend/tests/workflows/_harness.py` | `:258-313` delete four `WEIGHTS_CHECKS` entries and rewrite `:253-256`'s comment ; `:329-334` delete `DRAFT_REF_OUTPUTS` ; `:357` `WEIGHTS_CACHE_SUFFIX` -> `"v5"` | **not delete-only** |
 | `backend/tests/workflows/test_weights_and_model_refs.py` | `:59-88` three clauses stay, the digest-source clause changes to the `model_refs.py files` anchor ; `:202-230` `test_the_plan_job_publishes_the_model_refs_it_read_from_config` is rewritten to read the action's `model` step rather than a job output, and drops `DRAFT_REF_OUTPUTS` ; `:344-380` the widened closed world and the equality guard ; new: the paste rule, the every-row clause, the config-root clause. **`assert "if" not in check` at `:84` must survive the diff** | the red-first commit |
 | `docs/reference/ci-model-runtime.md`, `docs/architecture/summarize/model-boundary.md` | section 5 | - |

- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q` and `shellcheck .github/scripts/fetch-model-runtime.sh`; CI - full suite; **plus the three dispatches in section 4, all after the second commit.** `test_pinned_versions.py::test_the_shared_fetch_script_is_the_one_home_of_the_pin_for_every_caller_on_it` must stay green **unedited** - it goes red if the rewritten script stops sourcing `install-llama-runtime.sh`, which is C6 step 8.
- **Oracle:** **the paste rule** (C10). It fails today on 8 sites, and row 2 removes all 8 by removing their producers. Sibling assertions: `fetch-model-runtime.sh` contains no `backend/models/` literal other than the `mkdir -p`, which **fails today at 3 occurrences**; and a fixture pair differing only in one companion digest renders two different cache keys, which **fails today** because `action.yml:93` names no companion. **What it cannot settle:** `measure.yml`'s 5 paste sites and its four inline arms. They reach neither the action nor the script, they are out of scope by the table in section 0, and the oracle is scoped to say so rather than to fail forever. ESCALATE triggers 1, 2, 3 and 6 apply.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The first commit is tests only and lands RED.** Without that order a worker deletes the workflow verify step as redundant and every local gate stays green | Fowler |
 | 2 | **Both cache keys move in the same commit.** `action.yml:93` spells two inputs this row deletes, and a composite action referencing a deleted input resolves it to empty - so the key would become `llm---<build>-v4`, one key every model shares. And the closing dispatch cannot work across two commits: D2 saves under one shape and D3 misses | Fowler |
 | 3 | The restore-time check survives as a step with **no `if:`**. The script runs behind `cache-hit != 'true'` | Carmack |
 | 4 | The in-loop digest check is an **early exit**, named as one, not half of the control. Calling it a half is the framing that invites the next worker to delete the wrong one | Carmack |
 | 5 | The script writes to `mktemp`, not `backend/var`. That directory is gitignored and `llm-council.yml` lacks it on a night where the tenant selects no work | Carmack |
 | 6 | The loop reads on file descriptor 3. `done < file` hands the body the same fd 0, so a body command that reads stdin eats rows exactly as from a pipe | Carmack |
 | 7 | The action **computes** its key, alias and weights path in one new first step, capturing then appending. A caller-computed key is hop 3 of the four this plan deletes | Carmack and Fowler |
 | 8 | The action gains an `outputs:` block and the `digest.yml` call gains an `id:`. Without both, `:583` and `:604` read empty and the `sha256sum` runs on a directory | Carmack |
 | 9 | The verify step declares `CONFIG_ROOT` in its own `env:`. It is a separate step and inherits nothing | Carmack |
 | 10 | **`WEIGHTS_CHECKS` shrinks to four and `:71` stays an equality.** Discovery still finds eight because the script still spells `huggingface.co/`; the four converted jobs are derived at assertion time. Do not weaken `:71` to a subset | Fowler |
 | 11 | `test_pinned_versions.py` is a gate, not a file this row writes. Listing a file that needs no edit invites a worker to invent one | Fowler |
 | 12 | The paste rule shipped here is the **scoped** one, in this plan's own test module. The repository-wide rule over all 28 `needs.*.outputs.*` expressions is plan 46's row | Andre proposed; Fowler ruled on where it lands |
 | 13 | The `/props` check reads `summarize_file`; the alias check reads `summarize_id`. Both pass an `endswith` test, and they print different error text | Fowler |
 | 14 | `validate.yml:107-110` is **unchanged** by this row. It reads the `candidate` verb, which keeps `draft_*` | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Move the digest check entirely into the fetch loop | The loop is skipped on a cache hit, so a restored entry is never checked | Nothing saved, and a wrong model reaching the server unnoticed | Carmack |
 | 2 | Split the key change into its own row and commit | The action's key spells inputs this row deletes, so the split produces `llm---<build>-v4` for one commit; and no ordering of two commits lets the closing dispatches share a key | A guard test that is red between two commits, which is a test saying those commits are one change | Fowler |
 | 3 | Drop the `-v5` suffix, since the digest makes a hand bump unnecessary | It is unnecessary only for changes the digest can see. Three it cannot: an entry already poisoned, a llama.cpp release re-uploaded under one build tag, and an `install-llama-runtime.sh` change altering `backend/bin`, which is in `path:` and in no key component | One character saved, against `gh cache delete` needing a permission and leaving no record in git, or editing a declared field to move the digest, which puts a lie in the config | Carmack |
 | 4 | Strand `digest.yml`'s relay lines in a third pull request | The file is load-bearing here: `:583` and `:604` read a job output this row deletes the producer of, so stranding them leaves `LLAMA_WEIGHTS: backend/models/` and a `sha256sum` on a directory. A composite action does warn rather than fail on an undeclared input, so stranding would have been mechanically safe; it is refused on the 17 lines, not on the risk | A production run with `LLAMA_WEIGHTS` empty between two merges | Fowler |
 | 5 | Pass the cache key into the action as an input | Hop 3 of four, and it makes the key a value computed somewhere other than where the set is read | Three lines in each of two callers, and a key no longer provably the downloaded set | Carmack |
 | 6 | Give the script a base-URL seam so a test can execute it | A seam that exists only for a test is a mock by another name (Guardrail #7) | About 15 lines and a second code path. `shellcheck` plus the three dispatches is the honest answer | Fowler |

## Section 4 - The three dispatches, and what each proves

Four things a dispatch must prove that nothing cheaper can: the loop downloads **every** declared file on a real runner and each row's digest and size pass; the no-`if:` verify runs on a **restored** entry; the key Actions resolves is the key the printer prints; and the action's key equals the inline caller's.

| # | Dispatch | Workflow, branch, inputs | What it proves | When it finishes | Cost |
| --- | --- | --- | --- | --- | --- |
| D1 | **the loop, at N=2** | `idhazh-pipeline-tests.yaml`, PR-B's branch, `candidate_models_file: config/models/gemma-4-e4b-qat.json` | the loop actually loops; the per-row digest and size on a companion; C6 step 12's count check; the `backend/var/candidate-config` root; the landed path | **read the fetch log for two `curl` lines and two `sha256sum --check` OKs.** One means the loop did not loop. Cancel once `Verify the weights` is green - the three cases prove nothing this plan needs | one cold 4.28 GB fetch. `permissions: contents: read`, so it cannot push. Leaves an entry nothing else hits |
| D2 | **the production key** | same workflow, same branch, **after D1 finishes**, `candidate_models_file` empty | the production key string resolves with no literal `${{` left in it, and **the entry saves under it** so D3 has something to hit | read the resolved key off the cache step and compare it character-for-character with the action's. Cancel at the verify | one cold 5.68 GB fetch. This entry is what `digest.yml` hits on its next cron, so production's cold fetch is paid here |
| D3 | **the hit** | `llm-council.yml`, same branch, **after D2**, `date` empty | the no-`if:` verify over **restored** bytes, over every row; and cross-caller key equality - the hit itself is the proof | if it misses, that is a finding rather than a re-run: read the two resolved keys off the two logs, fix the fold, re-run D3 only. D1 and D2 stand | no weights download. **It pushes council verdicts to the branch - drop that commit with a revert before merge, never a rewind** |

**D1 and D2 cannot run concurrently.** Both are `idhazh-pipeline-tests.yaml`, whose workflow-level `concurrency: group: pipeline-tests, cancel-in-progress: false` puts the second in `pending`. Serial by the platform, not by discipline.

**Neither covers the other.** The live pointer declares no companion, so an empty dispatch exercises a one-row loop indistinguishable from today's single-file fetch - the arity this plan exists to unweld would ship unexecuted. A gemma dispatch writes a gemma key nothing else will ever hit, so it cannot pre-warm production.

**D3's timing, practically.** Its cron is `0 22 * * *`, group `llm-council`, `cancel-in-progress: false` - a dispatch **queues behind** a running cron rather than cancelling it. Start it before 21:00 UTC, or after the 22:00 run has finished. If the cron is mid-run, queue it and leave it; be present when it lands, because of the push.

**Not `digest.yml` and not `validate.yml`.** `digest.yml` is the production digest - 164 to 184 min - and it pushes to `main`. `validate.yml` uses the inline fetch shape D1 already proved.

**Why D1 is guaranteed to miss.** Its key is `llm-<64hex>-<build>-v5`, a string no entry on the branch or on `main` carries. That is only true because decision 2 moves both key spellings in one commit: `digest.yml` crons five times a day on `main`, refreshing the `-v4` entry, and Actions restores from the current branch **and** the default branch - so a D1 run against an unchanged `idhazh-pipeline-tests.yaml:167` would have hit main's warm entry and proved nothing.

## Section 5 - The docs

| Page | Section | What it becomes | Row |
| --- | --- | --- | --- |
| `docs/reference/ci-model-runtime.md` | `### Where the three values are written, and how many places that still is` (`:25`) | `### Where the model file is read, and how many places that is` - one place, the printer; every caller hands it a config root. **The stale `LLAMA_SCRIPT_CALLERS` citation at `:51` is deleted** - that symbol exists nowhere in the repository; the harness constant is `LLAMA_SHARED_SCRIPTS` at `_harness.py:185` and the discovery is `_fetch_script_callers` | 2 |
| `docs/reference/ci-model-runtime.md` | `### What the cache key holds` (`:59`) | same title; the literal becomes `llm-<digest over every declared row>-<build>-v5`. **Plus the one `## Design rationale` entry this plan owes** | 2 |
| `docs/reference/ci-model-runtime.md` | `## Every download fails loudly, and every weight is checked` (`:113`) and `### The digest settles the bytes, and the declared size settles the document` (`:156`) | the four-row "Digest read from" table collapses to one row - the printer's `files` verb, column 4 - and the declared-size check becomes shared rather than per caller. **The production entry size is corrected to 5.68 GB**, with the note that the 57 to 338 s download and 38 to 95 s restore figures were taken on the 4.28 GB gemma arm and scale by about 1.33 | 2 |
| `docs/reference/ci-model-runtime.md` | `### Every download names a commit` (`:226`) | "one bare word" becomes the closed grammar row 1 ships | 2 |
| `docs/architecture/summarize/model-boundary.md` | **delete `## What is wrong with the boundary today` (`:504-544`)**; gain the `files` contract, the seventh column and the one-companion refusal | six paragraphs; four are dated status prose about work already done and go with the heading. **The two that survive become rows in `## Which side each fact lives on` (`:88`)**, by their opening words: `:522` "The entry declares its architecture, and case 4 is what makes that a fact." and `:533` "The entry names the weights it was set for, and load refuses a mismatch." Folding creates no duplicate - `arch` appears only at `:523` and `declared_for` at `:196` in a different role | 2 |

**The page pays the split test before it is added to** (AGENTS.md). `model-boundary.md` is 555 lines with 11 top-level headings and its own `:542` says it "describes the boundary rather than tracking work" - so the status section is the cut, and one addition buys exactly that one cut. `ci-model-runtime.md` passes without a cut: it answers "what happens to a model on a runner", every rewritten section is that question, and the relay prose it deletes roughly balances the loop prose it gains. **Run `python backend/utilities/doc_load.py` before and after.**

**One `## Design rationale` entry, on `ci-model-runtime.md` under `### What the cache key holds`: the cache key is computed inside the action from the model file, not passed in by the caller.** It earns one because a real alternative is what every caller does today, reversing it is a key-shape change that costs every caller a full re-download, and it crosses the workflow-to-action boundary. No other decision here earns one: the grammar, the `summarize_` prefix and the column order are implementation shape, and `model-boundary.md` is taking a deletion rather than a decision.

## Section 6 - What this plan costs, all of it

| Arm | Key expression after | Jobs missing together | Caused by | Bytes | Seconds |
| --- | --- | --- | --- | --- | --- |
| Production - `action.yml`, called by `digest.yml/work` and `llm-council.yml/judge` | `llm-<64hex>-<build>-v5` | up to 8, plus council's matrix | **row 2** | 5.68 GB + `backend/bin` | download estimated 100 s median, 76 to 449 s, replacing a roughly 60 s restore - **about +40 s median** |
| Pipeline-tests - `:167` | the same string when the input is empty | 1 | **row 2** | same | same. It shares production's entry, so it hits once that is warm |
| Qualify - `validate.yml:284` | expression unchanged, **value** changes | up to 8 | **row 1** | 4.22 to 6.64 GB per candidate | same order |
| Bench - `measure.yml:268`, `:549`, `:878` | expression unchanged, **value** changes | 1 each | **row 1** | per candidate | same order |

**Rows 1 and 2 invalidate disjoint sets**, so merging them on different days costs nothing extra and no arm is refetched twice. The seconds are an estimate scaled from the measured 4.28 GB figures by 5.68/4.28; **what settles it is the first cold `work` job's step timing after PR-B merges.**

**Eviction is certain and is the desired outcome.** The old `-v4` production entry (5.68 GB) plus the new one (5.68) plus one gemma qualify entry (4.28) is 15.64 GB against a 10 GB allowance. GitHub evicts least-recently-used; the old `-v4` entry is the least recently used the moment the second commit merges and nothing references it again, so it goes first, automatically.

**None of this can fail a run.** The two numbers that fail a run are the 6 h job cap and the 1 GB site, and neither is touched. `shard_timeout_minutes` is 200 against a worst-case cold fetch of about 7.5 min - 3.8 percent. The production digest is 164 to 184 min against 360. The 10 GB allowance is GitHub's and it evicts rather than errors. **This plan costs tens of seconds, once per arm.**

## See also

- [`20260921-42-lane-b-workflows-plan.md`](20260921-42-lane-b-workflows-plan.md) - the parent, whose rows 1 to 6 landed and whose rows 7 to 11 this plan carries.
- [`20260922-46-no-file-has-two-writers-plan.md`](20260922-46-no-file-has-two-writers-plan.md) - in flight; section 1c is the interlock, and two of this plan's scope-out lines become rows there.
- [`20260922-47-the-pipeline-stops-naming-a-server-plan.md`](20260922-47-the-pipeline-stops-naming-a-server-plan.md) - owns `runtime_sweep.py`'s address lines; its claim of sharing no file with this plan is true once `measure.yml` and `runtime_sweep.py` leave here.
- [`../docs/reference/ci-model-runtime.md`](../docs/reference/ci-model-runtime.md) - the page that owns the fetch path and the cache key.
- [`../docs/architecture/summarize/model-boundary.md`](../docs/architecture/summarize/model-boundary.md) - the page that owns what the model file declares.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed.




