# The model file is the fetch interface

**Last Updated**: 2026-09-22

**Level**: 5, and one row is why. **Row 1 closes a path-traversal hole in the field checker every download path runs through** - that is the trust boundary and a Level-5 surface by CLAUDE.md section 6. Rows 2 and 3 are Level 3: they move the byte check that guards every model download. Rows 4 and 5 are Level 2 and run AUTO once the user authorizes.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight - two, not four, because section 1c's readiness table shows two disjoint file sets at the widest point and every earlier wave is a single pull request; refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Plan 42 rows 1 to 6 landed. What is left is the half that was always the point: one JSON file says where a model's bytes come from, and its contents still travel through a Python printer, job outputs, composite-action inputs and environment variables before a `curl` sees them. The arity is welded at two, so a model shipping three files cannot be described. `model_refs.py:41` refuses only whitespace, so a `file` value of `../../x` reaches `-o "backend/models/${WEIGHTS_FILE}"`. The cache key at `.github/actions/model-server/action.yml:93` names no companion at all, so a restored hit can be missing a file the model declared - and then every re-run fails identically until a person bumps the key by hand. |
| The rule | **The model json is the interface. It names every file the model needs and where each comes from; one reader turns that into downloads, checks and a cache key. Everything else that relays a model fact through a workflow is deleted.** Owner ruling 2026-09-21. |
| The second rule | **A control that already exists is imported, never re-implemented.** A fourth copy of a field grammar is a net loss at a trust boundary: the duplicate is the one a reviewer does not read. |
| The measure | **Edits per future change, and hops from the model file to the download.** Lines are the smaller number and the easier one to report. |
| Hard scope - in | Give the printer a `files` verb that emits the whole file set with its landed path, reading either shape of companion list, and close the traversal hole using the grammar this repository already has. Make the fetch script read a config root and loop, so the four relay hops and the four draft inputs disappear. Make the weights cache key name the set the model declares. Give the benchmark arms a two-second exit check in front of their readiness wait, and make the repeat count a config value. Cut the test-support module to the names more than one module reads. |
| Hard scope - out | See the table below. Every line there is a dated decision with a price, never a law (CLAUDE.md section 0d). |
| Supersedes | Plan 42 rows 7, 8, 9, 10 and 11, which become `COLLAPSED` in that plan's Reckoner. Plan 42 rows 1 to 6 are DONE and are not re-planned here. |
| Blocked by | **Plan 41 merged as #1036 and #1039.** It edited `backend/utilities/model_refs.py` - the file row 1 rewrites - which is what section 1e's decision rule keeps this from deadlocking on. |
| ESCALATE triggers | (1) Row 1 closes a path-traversal hole. Its refusal cases ship in the same commit. (2) **Row 2's first commit strengthens the restore-time digest check against the unchanged tree and does nothing else.** If the fetch moves in the same commit as the check, stop - section 1d C4 says why that ordering is the whole control. (3) Row 2 must leave a digest check that runs on a cache hit. The fetch script runs behind `cache-hit != 'true'`, so a check that lives only inside the script never sees a restored entry. (4) Row 3 changes a cache key five callers share. `gguf_cache_hit` must say what it means after the change, or be removed, in the same commit (CLAUDE.md section 11). (5) Row 4 must not shorten a readiness wait. It adds an exit check in front of one. (6) Row 5 deletes names from a shared module; each deletion is grepped as a string first, because nine orphans are private helpers called inside the module itself. (7) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Four pull requests in three waves. Row 1 runs alone because it is the trust-boundary fix and the contested file; rows 2 and 3 run alone because together they own every workflow file. Carmack rules the fetch path and the cache; Fowler the module structure, the test tiers and the grouping. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| **Splitting the runtime binary onto its own cache key** (plan 42 row 9's second half) | A llama.cpp pin bump keeps discarding 4.216 GB of unchanged weights | **Refused on its own arithmetic.** A cold fetch costs 75 s median over the restore it replaces, and a pin bump happens a couple of times a year - under three minutes annually. What it costs to take is the part nobody priced: `install-llama-runtime.sh` has exactly one caller, and `measure.yml` carries **three inline hand-copies of the installer**, so the split needs a second skip condition at each. It also splits `gguf_cache_hit`, a persisted column written at `runtime_sweep.py:646`, into a boolean that cannot say which half hit. Carmack |
| **Converting `measure.yml`'s four inline weights downloads to the shared fetch** | Four blocks keep their own spelling of repo, revision and filename | The measurement arms at `measure.yml:315`, `:569-572`, `:898-901` and `:1121` are independent of the composite action. Plan 42's row 8 oracle - "no workflow, action or script names a weights repository, revision or filename" - **cannot pass while they exist**, and plan 42 named only one of the four. Row 2's oracle is scoped to jobs reaching the action or the script, and the conversion is its own row in a later plan. Fowler |
| **Declaring the field grammar in `backend/idhazh/contracts/knobs/models.py`** | The grammar lives in `backend/utilities/measure_llm.py` and `model_refs.py` imports it from there | The right long-run home: one declaration, three importers. It loses today because `knobs/models.py` is plan 41's file and plan 41 is an open pull request in conflict - a cross-plan edit is Level 3 and needs a ruling this plan should not spend. **What brings it in:** plan 41 merging, then a one-commit move. Fowler |
| **Folding the `plan` job into `work`** | The plan job keeps its own provisioning, 0.41 min | Unchanged from plan 42: the plan job reads every feed over the network and stamps the clock, so four shards planning independently would read feeds at four instants. What gets the overlap is a cheap `decide` job, about 120 lines in `digest.yml`, hiding the plan job behind a 5 to 6 min prelude. Next plan. Carmack |
| **One composite action for the four callers that fetch, verify, start and health-check as a unit** | Four sites keep their own spelling of four steps | A countable condition: how many merged pull requests in the last quarter changed more than one of the four in the same commit. **Take that count now rather than at this plan's close** - it is one `git log`, it decides whether a different row exists, and plan 42 parked it at the end of a row that has nothing to do with it. Fowler |
| **Splitting `_harness.py` into four files** | The module keeps several answers in one file after row 5 cuts it | The right end state and a separate structural pull request. One addition buys one cut. Fowler |
| `test_triggers.py`, `test_staged_paths.py`, `test_daily_commit_steps.py`, `test_commit_script.py` | About 1,572 lines stay | The commit surface is not this plan's. **`test_triggers.py:191-199` is the workflow-side control for Guardrail #11** - closed-world over every declared dispatch input, asserting a read-by-name input never appears in a `run:` body. Nothing here may reach it. Andre |

### What a change costs today

Measured on `origin/main`, 2026-09-22, except where a line says estimate. **Plan 42's own cost table is stale: every `measure.yml` line number it gives below 449 is off by 35, because its rows 3 and 4 deleted the image job out from under them.**

| Reading | Value | Where |
| --- | --- | --- |
| Hops from the model file to the download | **4** - printer, job output, action input, environment | `model_refs.py` -> `$GITHUB_OUTPUT` -> `.github/actions/model-server/action.yml:107-115` -> `fetch-model-runtime.sh:30-32` |
| Files a model file can declare | **exactly 2**, welded | `COMPANION_FIELDS` at `model_refs.py:24-27`, `_draft_rows`, `_cache_key` |
| Composite action inputs | **10, of which 4 are draft** | `.github/actions/model-server/action.yml:12-47` |
| What `one_bare_word` refuses | **whitespace only** - `../../x` passes and reaches a `-o` destination | `model_refs.py:41` into `fetch-model-runtime.sh:42` |
| Whether the weights filename has any segment rule | **none, in either layer** | `ModelRef.file` is `Field(min_length=1)` |
| Whether that grammar already exists elsewhere | **yes, written and tested** - `REPO_RE`, `GGUF_RE`, `REVISION_RE`, plus a duplicate-filename refusal | `backend/utilities/measure_llm.py:28-32`, used at `:69-73`, refusal at `:71-75`, tests at `backend/tests/test_measure_llm.py:39-77` |
| Companion files the weights cache key names | **0** | `.github/actions/model-server/action.yml:93` keys on weights file, weights revision and build |
| Times that key has been bumped by hand | **4** - it ends `-v4` | same line |
| Inline Python programs walking a model file inside a workflow | **6** | `.github/actions/model-server/action.yml:136`, `:183`; `idhazh-pipeline-tests.yaml:196`, `:274`, `:354`; `measure.yml:1136` |
| Independent weights downloads in `measure.yml` that reach neither the action nor the script | **4** | `:315`, `:569-572`, `:898-901`, `:1121` |
| Seconds before a benchmark arm notices llama-server died at start | **900** at `measure.yml:954`, **600** at `runtime_sweep.py:284` | against a 2 s exit check at `start-llama-server.sh:67-72` |
| What a cold model load legitimately costs | **284 to 447 s, 8.7 to 12.4 percent of a shard** | `docs/archive/measurements-2026-08.md:848`. **The 900 s and 600 s waits are correct and must not shorten** |
| Whether the sweep already samples liveness | **yes, once a second, and discards it** | `runtime_sweep.py:450` starts the thread, `read_status` at `:255` returns `{}` silently when the process is gone |
| Top-level names in `_harness.py` | **242** in 2,253 lines | 45 imported by nobody, 136 by exactly one module, 37 by two or three, 24 by four or more |
| Modules importing `_harness` | **22, none outside `backend/tests/workflows/`** | every one spells `from ._harness import` |
| Names in `_harness.py` a one-file change must touch | **181 of 242** | 45 orphans plus 136 single-consumer |
| Test lines per workflow line | **1.805** (11,043 / 6,119) | plan 42 set a gate of 1.30, which needs 3,088 more lines out. Section 1d C7 says why that gate is deleted |

## Section 0b - What this plan does, in one list

1. The printer learns the whole file set and its landed path, and the traversal closes using the grammar this repository already has.
2. The workflows read the model file instead of relaying it: the script loops, the action drops to five inputs, the inline walks go.
3. The weights cache key names the set the model declares, so a restored hit can no longer be missing a declared file.
4. The benchmark arms notice a dead server in two seconds, in front of a readiness wait that does not change, and the repeat count becomes a config value.
5. The test-support module keeps only the names more than one module reads.

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The printer learns the whole file set, and the traversal closes | plan 41, per section 1e | A | PENDING | - | - | - |
| 2 | The workflows read the model file instead of relaying it | 1 | B | PENDING | - | - | - |
| 3 | The cache names the set | 2 | B | PENDING | - | - | - |
| 4 | The benchmark arms learn the server died, and the repeat count is config | 3 | C | DONE | p42p5 | - | P5 |
| 5 | The harness keeps only what more than one module reads | 3 | D | PENDING | - | - | - |

**Row 4 landed ahead of its `Depends-on`, and decision 4 was not taken.** Rows 1 to 3 are held behind plan 41's #1036, so waiting would have left a dead server costing fifteen minutes of runner time to notice, twice per sweep, for as long as that branch stays open. Its two halves touch `runtime_sweep.py` at the start call and the repeat count, never the `gguf_cache_hit` column row 3 changes, so row 3 merges this branch in rather than around it. Its tests went into `backend/tests/workflows/test_bench_targets.py`, which is where the other bench workflow assertions already live and is already one of row 5's 22 consumers - the disjointness decision 4 buys was worth nothing while row 5 is held behind row 3 as well.

### Section 1a - The four pull requests and the files each owns

**Two pull requests never own one file, and that claim is at file level, not line level.** Plan 42's table gave P4 `measure.yml` and P5 `measure.yml L989`; a line-level claim is not a file-level claim, and that line number was wrong by 35 anyway.

| PR | Rows | Wave | Files it owns, exclusively |
| --- | --- | --- | --- |
| **PR-A - the printer** | 1 | 1, alone | `backend/utilities/model_refs.py`, `backend/tests/workflows/test_weights_and_model_refs.py`, `backend/tests/workflows/test_pipeline_tests_workflow.py` (it imports `candidate_rows`, `configured_rows` and `CONFIGURED_FIELDS` at `:683-691`) |
| **PR-B - the fetch interface and the cache** | 2, 3 | 2, alone | `.github/scripts/fetch-model-runtime.sh`, `.github/actions/model-server/action.yml`, `.github/workflows/digest.yml`, `llm-council.yml`, `validate.yml`, `idhazh-pipeline-tests.yaml`, `measure.yml`, `backend/utilities/runtime_sweep.py`, `backend/tests/workflows/test_weights_and_model_refs.py`, `test_pinned_versions.py`, `backend/tests/workflows/_harness.py` (delete-only), `docs/reference/ci-model-runtime.md`, `docs/architecture/summarize/model-boundary.md` |
| **PR-C - liveness and the repeat count** | 4 | 3 | `.github/workflows/measure.yml`, `backend/utilities/runtime_sweep.py`, `backend/idhazh/contracts/knobs/bench.py`, `config/idhazh.json`, and its tests **outside** `backend/tests/workflows/` |
| **PR-D - the harness** | 5 | 3, beside PR-C | `backend/tests/workflows/_harness.py` and its 22 consumers |

**`runtime_sweep.py` belongs to PR-B, not PR-C.** `gguf_cache_hit` is a persisted column written at `runtime_sweep.py:646` and read at `measure.yml:604` and `:1123`. Changing what the weights key covers changes what that column means, and a persisted-shape question belongs in the commit that breaks it (CLAUDE.md section 11). PR-C rebases onto PR-B.

**PR-C and PR-D are disjoint only if row 4's tests land outside `backend/tests/workflows/`.** That is a requirement on row 4, written into its Files touched, not an observation.

### Section 1b - Why the pull requests fall where they do

| Question | Answer |
| --- | --- |
| Why row 1 runs alone | It is a Guardrail #11 fix with a unit oracle, and it owns the file plan 41 also edits. Rows 2 and 3 close on a live dispatch. Merging them puts a security fix behind a runner queue and puts the contested file inside the largest pull request in the plan |
| Why rows 2 and 3 share | Row 3's file set is a **subset** of row 2's. They are two commits, never two pull requests |
| Why PR-B runs alone | After row 2 it owns every workflow file. That is arithmetic, not churn avoidance |
| Why PR-C and PR-D run together | Disjoint file sets under the condition above, and one is behavioural while the other is structural |

### Section 1c - Readiness, computed rather than read off a letter

**A row is ready when every `Depends-on` is DONE and its `Files touched` list shares no entry with a row in flight.** The owner diffs those lists before each dispatch.

| At this point | Ready together | Held, and why |
| --- | --- | --- |
| Now | nothing | 1 is held by section 1e. 4 is done |
| Section 1e resolved | **1**, alone | 2 needs the `files` verb. 5 shares files with 2 and 3 |
| Row 1 merged | **2**, then **3** in the same worktree | 4 and 5 both touch files rows 2 and 3 own |
| Row 3 merged | **4 and 5** together | nothing |

**Peak workers: 2.** Waves 1 and 2 are one pull request each by file arithmetic, so the pool is only ever wide in wave 3.

**Row 4 changes a measurement surface.** It runs in its own parallel-group and its readings are taken with no sibling writing to the same machine.

### Section 1e - The one live coupling with plan 41, and how it resolves

**Plan 41 is open as PR #1036: CONFLICTING, 164 files, +3,619/-4,832, zero completed checks.** It has already edited `backend/utilities/model_refs.py` - 27 insertions, 17 deletions: `DRAFT_FIELDS` renamed `COMPANION_FIELDS`, a `_companions()` helper added, and `_cache_key` changed to join every companion digest with `-`.

**Everything plan 42's section 1b said plan 41 owed this plan is already written on that branch** - the `companion_files` block, the four decode settings moved into `server`, the relocation rather than deletion of the draft fields, the retyped `ModelRef.draft`, the rewritten registry test, and the decision that the thinking span keeps `UNCAPPED_N_PREDICT`. That list is closed. **What is owed instead is a merge order, and nothing else.**

| Condition at row 1's dispatch | What the owner does |
| --- | --- |
| #1036 merged | Row 1 starts from main and keeps plan 41's `COMPANION_FIELDS` rename. Its `_cache_key` is replaced by C3's verb |
| #1036 still open | The owner withdraws the `model_refs.py` hunk from #1036 - 27 insertions and 17 deletions, the smallest piece of a 164-file branch - and row 1 proceeds. **The plans do not both edit that file** |

**Row 1 has no shape dependency on plan 41.** C1's input contract reads either companion shape, so the verb is correct whichever branch lands first. The dependency is a file, not a field.

## Section 1d - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent any shape below; it reads this section.**

### C1 - The `files` verb (row 1)

`backend/utilities/model_refs.py` gains one verb. **The module keeps one question** - which model files will a shell see, and is every field safe - at a new arity.

```
python3 backend/utilities/model_refs.py files --config-root <root>
```

**The input contract, stable under both companion shapes so neither plan revisits it:**

| Clause | Rule |
| --- | --- |
| Subject | the weights fields of the role entry, then a companion list |
| Where the list comes from | the **first key present** of `companion_files` (a JSON array) and `draft` (a JSON object, read as a one-element array). Both arms are four lines; neither plan owns the other's arm |
| Absent means absent | an entry with neither key prints exactly one row. The live pointer `config/models/qwen3.5-9b-q4km.json` is that case today |
| **Removal condition** (Guardrail #6) | the `draft` arm is deleted in a one-line commit when no committed `config/models/*.json` carries the key. Two do today: `gemma-4-e4b-qat.json`, `gemma-4-e4b-qat-no-draft.json` |
| The JSON key name | **never appears** in any downstream contract, test assertion or workflow. The output shape below is the contract |

**Output: TAB-separated, one row per file, weights first, then companions in declared order.**

| Column | Content | Absent optional |
| --- | --- | --- |
| 1 | `repo` | - |
| 2 | `revision` | - |
| 3 | `file` | - |
| 4 | `sha256` | - |
| 5 | `flag`, or empty | empty field, never a missing one |
| 6 | **the landed relative path**, `backend/models/<validated segment>` | - |

**Column 6 is new and it is what removes the shell's composition** (C3). Every field has passed C2 before it is printed.

**On a malformed entry the verb raises, prints the models file path, the list index and the field name, and exits non-zero.** Not a skip: a skipped companion is a server that fails to start over a missing file, or one that starts and silently does nothing.

**`--config-root` goes on `candidate` and `files`, and `--repo-root` comes off them.** That is a net loss of one argument. `configured` keeps `--repo-root` and gains nothing: it has two callers, both with no argument, both against `config/`, and a knob with one legal value is Guardrail #6 inverted.

**`_draft_rows` and the `draft_*` output keys are row 2's to delete, not row 1's.** Until row 2 lands they publish the **first companion by definition**, not the draft head, and row 1 says so where they are declared. Leaving that unsaid is how the module ends up with a verb emitting N files and a verb emitting 1, both describing one entry, both green - which is what plan 41's branch shipped.

### C2 - The field grammar, declared once (row 1)

**This is a security fix, and nine of its eleven cases are already written and tested.** `model_refs.py` imports the compiled patterns from `backend/utilities/measure_llm.py` - the spelling `runtime_sweep.py:33` already uses - rather than writing a fourth copy. A duplicate control at a trust boundary is the one a reviewer does not read.

| Field | Rule | Already in `measure_llm.py`? |
| --- | --- | --- |
| `repo` | `REPO_RE` - `owner/name` | yes, `:28` |
| `revision` | `REVISION_RE` - 40 lowercase hex, never a branch name | yes, `:32` |
| `file` | `GGUF_RE` - one path segment: no `/`, no `\`, not `.`, not `..`, not leading `.`, ends `.gguf` | yes, `:29`. **Covers percent-encoded traversal too - `%` is outside the character class** |
| `sha256` | 64 hex characters. **Required, no exception** - three fields is a file fetched against a blank digest, and `sha256sum --check` then reports "no properly formatted checksum lines found", naming neither the entry nor the field | **no - the one genuinely new case** |
| `byte_count` | optional, integer at least 1, cross-checked as `validate.yml:325` already does for the weights | - |
| `flag` | optional, matching `--[a-z0-9-]+` | - |
| the set | two entries resolving to one filename is refused | yes, `measure_llm.py:71-75` |
| **the weights `file` itself** | all of the `file` rules above | **no - this is the live hole.** Plan 41's `CompanionFile` validator covers companions only, and it is Pydantic, which never runs on the shell path because `model_refs.py` reads raw JSON |

**The destination is composed, never interpolated**: a constant directory plus the validated segment.

### C3 - The landed path, computed in exactly one place (rows 1, 2)

**Plan 42's C10 asked for the wrong equality.** `companion_path(weights, companion)` on plan 41's branch returns `weights.parent / companion.file` - a **read** path parameterised on where the weights landed. The fetch composes a **write** destination from the constant `backend/models` at `fetch-model-runtime.sh:38` and `:42`. Sharing a *function* would still leave them disagreeing about the *constant*, which is the thing that can actually drift. And importing `idhazh` into a stdlib-only printer couples row 1's merge to a 164-file branch in conflict.

| Step | What it removes |
| --- | --- |
| The `files` verb prints column 6, the landed path, composed by the printer | the shell's composition. `fetch-model-runtime.sh` writes column 6 verbatim and composes nothing |
| A contract-tier test in `backend/tests/workflows/` imports **both** `utilities.model_refs` and `idhazh.llm.server` - legal under pytest, `pythonpath = ["backend"]` - and asserts for the live config that column 6's parent equals `companion_path`'s parent and column 6's name equals the declared file | the drift. **Neither production module imports the other** |
| The same test asserts `fetch-model-runtime.sh` contains no `backend/models/` literal other than the `mkdir -p` | the second implementation |

**Plan 41 owns `companion_path`. This plan owns column 6 and the test.**

### C4 - The two halves of the byte check, and the commit order that protects them (row 2)

The control is a SHA-256 checksum. The verify step at `.github/actions/model-server/action.yml:128-143` runs `sha256sum --check` against the digest in the model file, carrying **no `if:`**, after the fetch and before anything reads `backend/models`.

| Half | Where | Proved by |
| --- | --- | --- |
| download-time | inside `fetch-model-runtime.sh`, per row, immediately after each `curl` | the dispatch |
| **restore-time** | a workflow step with **no `if:`**, in every caller | the surviving test |

Both are needed because the fetch script runs behind `cache-hit != 'true'` at `.github/actions/model-server/action.yml:105`. Put the only check inside the script and a restored entry is never checked again.

**The surviving assertion**, replacing the body of `test_weights_and_model_refs.py:88` in place, asserts four things: the set of jobs running the fetch - directly or through the action - is discovered and non-empty; every such job has a verify step carrying no `if:`, after the fetch and before the first read of `backend/models`; that step pipes **every** row of `model_refs.py files` to `sha256sum --check`; and the root the verify step names equals the root the fetch step names.

**The commit order is the control, not the ESCALATE trigger.** Row 2's **first commit is that strengthened assertion against the unchanged tree, passing, and nothing else.** Only the second commit moves the fetch. Without that order, the most likely failure in this plan is a worker seeing two `sha256sum --check` calls, reading the workflow step as redundant, deleting it, and going green everywhere - because the only test guarding it is one row 2 itself rewrites, and a rewritten assertion pointed at the script finds a check there and passes. With that order the worker goes red locally, before the push.

**`WEIGHTS_CHECKS` at `_harness.py:271` dies whole** after row 2: one fetch shape and one verify shape means all four facts per entry are computable.

### C5 - What `fetch-model-runtime.sh` reads and refuses (row 2)

| Environment | Required |
| --- | --- |
| `GITHUB_TOKEN` | yes - the pinned release lookup |
| `CONFIG_ROOT` | yes - which config tree. No default in the script; the caller passes it |

**Nothing else.** It still refuses any positional argument, and it still sources `install-llama-runtime.sh` at line 35.

**The loop writes the printer's rows to a file, then reads the file.** `printer | while read` runs the body in a subshell, so a failure inside the loop cannot fail the script the way `set -euo pipefail` implies. This is a named trap, not a style preference.

Per row: `curl -fsSL --retry 3 --retry-all-errors` to column 6, then `sha256sum --check` immediately, then the next row.

**Row 2's grep oracle is scoped to jobs reaching the action or the script.** `measure.yml` carries four independent weights downloads that reach neither; converting them is out of scope and in the table above. An unscoped "no workflow names a weights filename" assertion cannot pass, and plan 42 wrote one.

### C6 - The cache key, and the column it changes (row 3)

| Property | Value |
| --- | --- |
| Today | `.github/actions/model-server/action.yml:93` keys on weights file, weights revision and build. **It names no companion**, while `model_refs.py:79-92` composes a key over both files |
| After | the key is a **fixed-width digest over the `files` rows** - a digest, never a join. `-`-joining 64-character digests inside a key crosses GitHub's 512-character cap at about seven files, and plan 41's branch shipped the join |
| Where it comes from | a fourth verb, `cache-key`, computed over what `files` prints. One traversal, so the key is provably the set the loop downloads. Declared as a verb so a worker cannot implement it as a private helper that walks the entry a second time |
| Paths | unchanged: `backend/models` and `backend/bin`, together, on one key |
| `gguf_cache_hit` | written at `runtime_sweep.py:646`, read at `measure.yml:604` and `:1123`. **It must say what it means after the key changes, or be removed, in the same commit** (ESCALATE trigger 4) |

**The defect this fixes is a wedged pipeline, not a saving.** A companion change that keeps the weights filename and revision produces a hit missing a declared file; the fetch is skipped, the verify fails, and every re-run fails identically until a person bumps the key. A hit also refreshes last-access, so the bad entry never ages out. The key ends `-v4`, which is that bump already paid four times. The benchmark and qualification arms are protected today because they key on `candidate_cache_key`, which is the printer's key - production is the one that is not.

### C7 - Liveness, and what is not allowed to change (row 4)

| Property | Value |
| --- | --- |
| What is added | a **2 s exit check in front of the readiness wait**: sleep 2, then confirm the process did not exit, the shape `start-llama-server.sh:67-72` already uses |
| What does **not** change | the readiness waits at `measure.yml:954` (180 iterations of 5 s) and `runtime_sweep.py:284` (120 iterations of 5 s). **A cold model load legitimately costs 284 to 447 s.** Plan 42's line "900 and 600 -> 2 and 2" is wrong and would cost a readiness wait |
| The sweep half | three lines, not a mechanism. `runtime_sweep.py:450` already starts a thread calling `read_status(server.pid)` every second, and `read_status` at `:255` returns `{}` silently when the process is gone. The liveness fact is already sampled and thrown away |
| The repeat count | moves from a literal to `backend/idhazh/contracts/knobs/bench.py` with a default in `config/idhazh.json` |
| Tests | land **outside** `backend/tests/workflows/`, so PR-C and PR-D stay disjoint |

### C8 - The harness rule (row 5)

**`_harness.py` contains no name imported by fewer than two modules.** Mechanically checkable, and it is the oracle.

| Property | Value |
| --- | --- |
| The test | a contract-tier test driven by the same AST census that drives the moves: top-level names in `_harness.py`; for each, the count of `backend/tests/**/*.py` whose `ImportFrom` module ends `_harness` and names it |
| Can it fail | **yes - it fails on 181 of 242 names today.** It lands red in the row's first commit and each move makes it less red. Only a human edit turns it red again, so it is a structure test and not a data-dependent one (CLAUDE.md section 13) |
| The reading at dispatch | **re-run the census; never read the table below.** Plan 42's equivalent table rotted in one day |
| Reading, `origin/main`, 2026-09-22 | 2,253 lines, 242 names, 45 imported by nobody, 136 by exactly one, 37 by two or three, 24 by four or more, 22 consumers, none outside `backend/tests/workflows/` |
| The trap | **nine of the 45 orphans are private helpers called inside `_harness.py` itself** - an importer census marks them orphan and they are not. Grep each as a string before deleting (ESCALATE trigger 6) |
| What stays whole | the real-git-repo commit-script fixture. `test_staged_paths.py`, `test_daily_commit_steps.py` and `test_commit_script.py` all use it |

**No line-count target, and plan 42's ratio gate is deleted.** That gate was "test lines per workflow line at or under 1.30" from 1.88. Today the ratio is 1.805, reaching 1.30 needs 3,088 more lines out of `backend/tests/workflows/`, **row 5 is a move and every destination is inside that directory**, and rows 2 and 3 delete workflow lines, which shrinks the denominator and pushes the ratio up. The gate was unreachable and inverted. The reading is recorded; the gate is the rule above.

**The row's value, stated as the plan's own measure:** names in `_harness.py` a one-file change must touch, **181 to 0**.

## Section 2 - Row 1 - The printer learns the whole file set, and the traversal closes

- **Scope:** Give `model_refs.py` a `files` verb emitting every file a model declares with its landed path, a `cache-key` verb over those rows, `--config-root` on the verbs that need it, and the field grammar imported from where it already lives.
- **Files touched:**
  - `backend/utilities/model_refs.py`
  - `backend/tests/workflows/test_weights_and_model_refs.py`
  - `backend/tests/workflows/test_pipeline_tests_workflow.py` (it imports `candidate_rows`, `configured_rows` and `CONFIGURED_FIELDS` at `:683-691`)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q` and `python -m pytest backend/tests/test_measure_llm.py -q`; CI - full suite.
- **Oracle:** the `files` verb refuses each case in C2 by name, and **the weights `file` field is refused on the same cases as a companion's** - which fails on the base tree today, because `ModelRef.file` has no segment rule in either layer. **What it cannot settle:** whether the shell ever sees an unvalidated value. No test executes `fetch-model-runtime.sh`; row 2's closure assertion is what settles it, and this row's unit cases are meaningless without it. ESCALATE trigger 1 applies.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The grammar is imported from `backend/utilities/measure_llm.py`, not re-written. Nine of eleven cases are already written and tested there; a fourth copy at a trust boundary is the one a reviewer does not read | Fowler |
 | 2 | The verb reads the first key present of `companion_files` and `draft`, so it is correct whichever plan lands first. The JSON key name reaches no downstream contract | Fowler |
 | 3 | The `draft` arm carries its removal condition on the line that declares it (Guardrail #6), naming the two committed model files that still use it | Fowler |
 | 4 | The cache key is a **fourth verb over the printed rows**, not a private helper that walks the entry again. One traversal means the key is provably the set | Fowler |
 | 5 | The key is a fixed-width digest, not a join. A join crosses GitHub's 512-character key cap at about seven files | Fowler |
 | 6 | `_draft_rows` stays until row 2 deletes it, and row 1 records at its declaration that it publishes the first companion by definition. An unsaid contradiction between two verbs about one entry is what plan 41's branch shipped, green | Fowler |
 | 7 | `--config-root` goes on `candidate` and `files` and `--repo-root` comes off them - a net loss of one argument. `configured` keeps what it has; a knob with one legal value is Guardrail #6 inverted | Fowler |
 | 8 | `sha256` is required with no exception. Three fields is a file fetched against a blank digest, and the failure names neither the entry nor the field | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Write the field grammar fresh in `model_refs.py` | A fourth implementation of a control that exists, is tested, and already refuses duplicate filenames | About 25 lines, and a trust-boundary control in four places that must agree | Fowler |
 | 2 | Declare the grammar in `backend/idhazh/contracts/knobs/models.py` and import it everywhere | The right long-run home - one declaration, three importers. It loses today because that file is plan 41's and plan 41 is an open pull request in conflict | A cross-plan Level-3 edit and an owner ruling this plan should not spend. It returns as a one-commit move after plan 41 merges | Fowler |
 | 3 | Import `companion_path` from `idhazh.llm.server` so both plans share one function | It shares the function and still leaves the constant `backend/models` in the shell, which is the half that drifts. It also couples this row's merge to a 164-file branch with zero completed checks | Nothing gained; C3 is strictly stronger for one column | Fowler and Carmack |
 | 4 | Move `_cache_key` into its own module | Ceremony for four lines | A module and an import for one function | Fowler |

## Section 3 - Row 2 - The workflows read the model file instead of relaying it

- **Scope:** Make the fetch script read a config root and loop over the printer's rows, drop the composite action to five inputs, and delete the six inline Python programs that walk a model file inside a workflow.
- **Files touched:**
  - `.github/scripts/fetch-model-runtime.sh`
  - `.github/actions/model-server/action.yml`
  - `.github/workflows/digest.yml`, `llm-council.yml`, `validate.yml`, `idhazh-pipeline-tests.yaml`, `measure.yml` (the action and script callers only)
  - `backend/tests/workflows/test_weights_and_model_refs.py`, `test_pinned_versions.py`
  - `backend/tests/workflows/_harness.py` (`WEIGHTS_CHECKS`, delete-only)
  - `docs/reference/ci-model-runtime.md`, `docs/architecture/summarize/model-boundary.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q` and `shellcheck .github/scripts/fetch-model-runtime.sh`; CI - full suite; **and one real dispatch on a cache miss and one on a cache hit before the row closes.**
- **Oracle:** every job reaching the action or the script has a verify step with no `if:`, after the fetch and before the first read of `backend/models`, piping every printed row to `sha256sum --check`, against a root equal to the fetch step's. **What it cannot settle:** whether the four independent weights downloads in `measure.yml` are safe. They reach neither the action nor the script, they are out of scope by the table in section 0, and the oracle is scoped to say so. ESCALATE triggers 2 and 3 apply.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The first commit is the strengthened restore-time assertion against the unchanged tree, passing, and nothing else.** The second moves the fetch. Without that order a worker deletes the workflow verify step as redundant and every local gate stays green | Fowler |
 | 2 | The restore-time check survives as a workflow step with no `if:`. The script runs behind `cache-hit != 'true'`, so a check living only inside it never sees a restored entry | Carmack |
 | 3 | The loop writes the printer's rows to a file and reads the file. `printer \| while read` runs the body in a subshell, where a failure cannot fail the script | Carmack |
 | 4 | The script reads `GITHUB_TOKEN` and `CONFIG_ROOT` and nothing else, and still refuses positional arguments | Carmack |
 | 5 | The grep oracle is scoped to jobs reaching the action or the script. Plan 42's unscoped version cannot pass while `measure.yml` carries four independent downloads, and it named one of the four | Fowler |
 | 6 | `WEIGHTS_CHECKS` dies whole. After this row there is one fetch shape and one verify shape, so every fact it listed is computable | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Move the digest check entirely into the fetch loop | The loop is skipped on a cache hit, so the restored entry is never checked. This is the exact case the step exists for | Nothing saved, and a wedged or wrong model reaching the server unnoticed | Carmack |
 | 2 | Convert `measure.yml`'s four inline downloads in this row | Four more blocks in the largest pull request in the plan, none of which uses the action | Its own row, priced in section 0 | Fowler |
 | 3 | Give the script a base-URL seam so a test can execute it | A seam that exists only for a test is a mock by another name (Guardrail #7) | About 15 lines and a second code path. `shellcheck` plus the dispatch is the honest answer | Fowler |
 | 4 | Keep the four draft inputs on the action as optional | They are the relay this plan removes, and optional means a caller can still pass them | Four inputs and four pass-through lines per caller | Carmack |

## Section 4 - Row 3 - The cache names the set

- **Scope:** Make the weights cache key a digest over the whole file set the model declares, and settle what the cache-hit column means afterwards.
- **Files touched:**
  - `.github/actions/model-server/action.yml` (the key at `:93`)
  - `.github/workflows/measure.yml`, `validate.yml`, `idhazh-pipeline-tests.yaml` (their key expressions)  - `backend/utilities/runtime_sweep.py` (`gguf_cache_hit` at `:646`)
  - `backend/tests/workflows/test_weights_and_model_refs.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite; **and two real dispatches, a miss then a hit.**
- **Oracle:** a model file whose companion changes while its weights filename and revision do not produces a cache **miss**. That fails on the base tree today - it produces a hit missing a declared file. **What it cannot settle:** whether the restored bytes are correct on a hit whose key did match. That is row 2's restore-time check, and it is why both rows exist. ESCALATE trigger 4 applies.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The defect is a wedged pipeline, not a saving. A hit missing a declared file fails the verify, and every re-run fails identically until a person bumps the key. The key ends `-v4` | Carmack |
 | 2 | **The `backend/bin` split is out.** Section 0 prices it: under three minutes a year, against three inline installer copies in `measure.yml` and a persisted column split in two | Carmack |
 | 3 | The paths stay together on one key, so the disjointness question plan 42 escalated does not arise. Two sibling directories written by two different scripts cannot overlap, and that trigger guarded a tautology | Carmack |
 | 4 | `gguf_cache_hit` says what it means after the change or is removed, in the same commit. Changing what a key covers changes what the column reports | Fowler, CLAUDE.md section 11 |
 | 5 | `runtime_sweep.py` belongs to this pull request, not row 4's, because the column is a persisted shape and the shape question belongs in the commit that breaks it | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Extend the existing concatenation to N digests | Key length grows against a 512-character cap and crosses it at about seven files. Plan 41's branch shipped exactly this | Nothing saved over a digest, and a cap failure nobody would connect to the cause | Fowler |
 | 2 | Split `backend/bin` onto its own key as plan 42 row 9 proposed | Three inline installer copies each need a second skip, and one boolean column becomes unable to say which half hit | Under three minutes of download a year, measured | Carmack |
 | 3 | Bump the key to `-v5` and change nothing else | It clears today's wedge and leaves the mechanism, so `-v6` follows | One character, and the fifth manual bump | Carmack |

## Section 5 - Row 4 - The benchmark arms learn the server died, and the repeat count is config

- **Scope:** Add a two-second exit check in front of the benchmark arms' readiness waits, and move the repeat count from a literal to config.
- **Files touched:**
  - `.github/workflows/measure.yml` (the arm at `:954`)
  - `backend/utilities/runtime_sweep.py` (the start at `:444`, the wait at `:284`)
  - `backend/idhazh/contracts/knobs/bench.py`, `config/idhazh.json`
  - tests **outside** `backend/tests/workflows/`, so this pull request stays disjoint from row 5's
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'sweep or bench' -q`; CI - full suite.
- **Oracle:** a server that exits immediately at start is reported within about two seconds instead of 900 or 600. That fails on the base tree. **What it cannot settle:** whether a slow but healthy start is now misread as a failure. It is not - the exit check tests whether the process is alive, never whether it is ready, and the readiness wait it sits in front of is unchanged.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The readiness waits do not shorten.** A cold model load legitimately costs 284 to 447 s. Plan 42's "900 and 600 -> 2 and 2" is wrong and would have cost a readiness wait | Carmack |
 | 2 | The exit check is the shape `start-llama-server.sh:67-72` already uses: sleep two seconds, confirm the process did not exit. It is not a health check and is not written as one | Carmack |
 | 3 | The sweep half is three lines. `runtime_sweep.py:450` already samples the process every second and `read_status` at `:255` discards the answer silently | Carmack |
 | 4 | This row's tests land outside `backend/tests/workflows/`. That is a requirement, because it is what makes this pull request disjoint from row 5's | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Replace the readiness wait with a short poll | A cold load takes minutes. The arm would report a healthy server dead | Every benchmark dispatch, wrongly failed | Carmack |
 | 2 | Make `read_status` raise instead of returning `{}` | It is called once a second from a sampler thread; raising there kills the thread, not the run | A silent sampler and a louder bug | Carmack |
 | 3 | Leave the 900 s and 600 s waits alone | A dead server costs 15 minutes of runner time to notice, twice per sweep | Nothing to take | Carmack |

## Section 6 - Row 5 - The harness keeps only what more than one module reads

- **Scope:** Move every name in `_harness.py` imported by exactly one module into that module, delete the names nothing imports, and gate the rule with a test.
- **Files touched:** `backend/tests/workflows/_harness.py` and its 22 consumers; `docs/reference/ci-model-runtime.md` for the reading.
- **Commit sequence, all structural:** the census test asserting the rule and landing **red**; then the largest destination; then the next; then the remaining modules; then the deletions, each grepped as a string first.
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** `_harness.py` contains no name imported by fewer than two modules. **It fails on 181 of 242 names on the base tree**, and it keeps failing whenever somebody re-adds a single-consumer name, which is the only thing that stops the module refilling. **What it cannot settle:** whether a moved name landed in the right module. Nothing mechanical can; the destination is the single importer by construction. ESCALATE trigger 6 applies.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The rule is the oracle. Plan 42 wrote it in its contracts section and then talked itself out of having an oracle at all, because it was looking at the collected test count - which proves only that nothing broke, and `pytest` already proves that | Fowler |
 | 2 | The test lands red in the first commit and each move makes it less red. A worker cannot call the row done while it is red | Fowler, Beck |
 | 3 | The census is re-run at dispatch. Plan 42's table was measured on 2026-09-21 and was wrong by 2026-09-22 - rows 5 and 6 orphaned nine more names, and row 2 here will orphan more when `WEIGHTS_CHECKS` dies | Fowler |
 | 4 | **The row runs after row 3.** Row 2 rewrites `test_weights_and_model_refs.py` and `test_pinned_versions.py`, and 22 of the 136 single-consumer names belong in exactly those two modules. Moving names into tests another row is deleting is a guaranteed conflict, not a risk | Fowler |
 | 5 | Nine of the 45 orphans are private helpers called inside `_harness.py` itself. An importer census marks them orphan and they are not. Grep each as a string first | Fowler |
 | 6 | The value is stated as edits per future change - names a one-file change must touch, 181 to 0 - not as lines. The row is a move and removes almost no lines from the tree | Fowler |
 | 7 | The commit-script fixture stays whole and is not dragged into the move; three modules outside this row's concern use it | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep plan 42's ratio gate of 1.30 test lines per workflow line | Unreachable by 3,088 lines, and inverted: this row is a move that removes none of them, while rows 2 and 3 shrink the denominator and push the ratio up | A gate that cannot go green, which is a gate nobody believes | Fowler |
 | 2 | Delete the 45 orphans and stop there | Leaves 136 names that a one-file change still has to touch, which is the tax the row exists to remove | About 150 to 250 lines removed and the structure unchanged | Fowler |
 | 3 | Split `_harness.py` into four modules in this row | The right end state, and a different question - one file answering many | A structural refactor bundled into a move. One addition buys one cut | Fowler |
 | 4 | Ship it as one commit | 136 moves across 18 modules in one diff is unreviewable, and two of the destinations are modules rows 5 and 6 of plan 42 just rewrote | A review nobody can do | Fowler |

## See also

- [`20260921-42-lane-b-workflows-plan.md`](20260921-42-lane-b-workflows-plan.md) - the parent, whose rows 1 to 6 landed and whose rows 7 to 11 this plan carries.
- `20260921-41-lane-a-model-file-plan.md` - delivered in #1036 and #1039 and deleted on close; section 1e was the only coupling.
- [`20260921-43-the-ledgers-and-the-generated-layer-plan.md`](20260921-43-the-ledgers-and-the-generated-layer-plan.md) - lanes C, D and E.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a row is run and closed.
