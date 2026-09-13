# Model swap as a config edit, and a bench that outlives its artifact

**Last Updated**: 2026-09-13
**Level**: 5 overall (section 6). Rows #2, #6, #10 and #11 change a persisted contract. **Row #10 was signed off by the owner on 2026-09-13 and no longer pauses**; all four proceed under the ESCALATE triggers in section 0.

Execute per [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md): the orchestrator dispatches one worktree-isolated worker per row; workers consult personas on ambiguity; AUTO-merge on green gates; **parallel N = 4**; honour the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Swapping the summarizer is a source edit today, and every benchmark that would inform the choice is deleted after seven days. |
| Hard scope - in | The model's turn envelope onto its entry; one complete config file per model selected by a pointer; a start-up proof with five arms; both benchmark arms chained in one workflow emitting a paste-ready page; a per-model dossier; benchmark filenames lose their date; every tokenizer-shaped constant names its weights; the sanitizer learns the control tokens of the configured model; a runbook whose swap and revert are one line each. |
| Hard scope - out | Adopting any candidate. Layered config overrides. Per-model prompt TEXT. Multi-file weights, vision projectors, speculative draft heads. Any new quality instrument - the eleven gates in `validate.yml` stay the only quality arm. Non-greedy sampling. Committing benchmark prose from CI. |
| ESCALATE triggers | (1) Row #10 changes the summarize contract, three hard refusals and the shard timeout. **The owner signed it off on 2026-09-13, so it runs without a further pause** - but it stops and surfaces if the measured cost per item exceeds the 28 percent the row prices, or if the qualification run does not clear every gate the incumbent clears. (2) Any row that would put a model identity into a branch under `backend/idhazh/llm/` stops and surfaces; row #6 builds the test that catches it. (3) Any row that would make a gate threshold, a prompt string or an output schema configurable per model stops and surfaces. (4) Rows #2 and #11 must render the incumbent's prompt byte-identical; a single differing byte stops the row. (5) Row #12 touches the trust boundary (Guardrail #11), which is surfaced and never adapted - a widening that cannot be proved to strip a declared marker stops the row. |
| Chosen strategy | One complete `ModelsConfig` per file, selected by a pointer - never a merge. Ruled by Fowler, 2026-09-13, on the ground that a merged product is a value with no file to read it from. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

### Section 0.1 - Intent, and what it overturned

The contract follows intent; code follows the contract (section 0d). Every row below serves one of these four.

| # | Intent | Effect | Authority |
| --- | --- | --- | --- |
| 1 | Testing a new model, and reverting, costs the least possible friction against existing code. | The measure of success is that no step in the runbook is a source edit. Rows #2, #6, #11 and #9. | Owner, 2026-09-13 |
| 2 | Reasoning during summarization is correct and wanted - a summarizer that cannot think works with its hands tied. | Overturns the standing position that a reasoning-by-default model is off-policy. Row #10 exists because of this; the argument is now the budget, not the ban. **Row #10 signed off 2026-09-13.** | Owner, 2026-09-13, under section 0 |
| 3 | A benchmark record is named for what it measured and nothing else. | Overturns the dated-filename rule in four places. Row #4. | Owner, 2026-09-13, under section 0 |
| 4 | Per-model benchmark output lives in its own file, with one file pointing at the others. | Creates a doc class. Row #7. | Owner, 2026-09-13 |

### Section 0.2 - The envelope and the content, which is the line this plan draws

| # | Rule | Why |
| --- | --- | --- |
| 1 | **The envelope is per model.** How a turn opens and closes, how a reply opens, where the system text is placed, which template keyword the runtime accepts, and which control tokens the sanitizer must strip. | These differ between model families and nothing this project wrote decides them. |
| 2 | **The content is global.** `summarize.txt`, `write_about_the_item.txt` and `plan_visual.txt` stay one set for every model. | `prompt_sha256` is one input of the run stamp, and `prose_changed_alone` returns nothing whenever `model_sha256` moved. Per-model content makes every prompt edit that rides in on a swap permanently invisible, and blinds the one surviving alarm on the day it is needed. Second reason: qualification compares two models on one frozen corpus, and different words on each side measures two changes and reports one number. |
| 3 | **A model with no system role is a placement change, not a content change.** The same bytes go to a different address - its own turn, or folded into the first user turn behind a declared joiner. | `prompt_sha256` does not move; the envelope field records that the address did. A model that needs different words is a model that failed qualification, not a model that needs a prompt file. |

### Section 0.3 - Two corrections carried into this plan

| # | Correction | What it replaced |
| --- | --- | --- |
| 1 | Cache pressure is not a constraint on holding several candidates. `digest.yml` keys on one model per entry, `validate.yml` keys on the candidate digest, `measure.yml` caches no weights. GitHub's 10 GB total evicts least-recently-used rather than failing. A miss costs one download: 5.29 GiB in 118 s, measured 2026-08-23 on `ubuntu-latest`, `n=1`, spread unavailable. | An earlier draft said two candidates could not both be cached. Withdrawn. |
| 2 | Memory headroom is open, not spent. `peak_rss_bytes` runs 10.06 to 13.82 GiB over 193 rows of `state/runtime-counters.csv`, median 12.40, counted 2026-09-08 from runs on `ubuntu-latest`; the ledger carries no column naming the weights. Weights are mapped, so those pages are file-backed and evictable; **at most 9.02 GiB of the 14.31 GiB worst sum can be anonymous memory - an upper bound derived by subtraction, not a reading.** `cgroup_peak_bytes` is empty on all 225 rows, and nothing has ever run out. | An earlier draft refused a quantisation on an estimated peak built by adding a weights delta to one reading - the arithmetic `docs/reference/measurements.md` retracted on 2026-09-09. Withdrawn. No row refuses anything on memory; row #8 takes the reading instead. |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The runtime sweep reaches for a key that is not there | - | A | PENDING | - | - | - |
| 2 | The turn envelope moves onto the model entry | - | A | DONE | p28-r2 | #692 | Fowler (Architecture and Engineering) |
| 3 | Every tokenizer-shaped constant names the weights it was taken against | - | A | PENDING | - | - | - |
| 4 | Benchmark records lose the date from their filename | 2, 3 | B | PENDING | - | - | - |
| 5 | Five things the server proves before the first item | 2 | C | PENDING | - | - | - |
| 6 | One complete config file per model, selected by a pointer | 2 | C | PENDING | - | - | - |
| 7 | The model dossier, and the index that points at every one | 3, 4 | D | PENDING | - | - | - |
| 11 | Where the system text goes, and which keyword the runtime is told | 5, 6 | D | PENDING | - | - | - |
| 12 | The sanitizer learns the control tokens of the model it guards | 11 | E | PENDING | - | - | - |
| 13 | Retake the two budgets that were sized on a retired vocabulary | 3, 7 | E | PENDING | - | - | - |
| 8 | Both bench arms in one workflow, emitting a page ready to paste | 1, 6, 7 | F | PENDING | - | - | - |
| 9 | The runbook: swap and revert in one line each | 6, 8, 12 | G | PENDING | - | - | - |
| 10 | Two spans on one call, so the model can think | 5, 6, 11 | H | PENDING | - | - | - |

### Parallel groups, derived

Derived from the rows' own `Files touched` lists and verified pairwise on 2026-09-13. It is a hint rather than the dispatcher's input: a row is ready when its `Depends-on` are DONE and its file list is disjoint from every row in flight.

| Group | Rows | Verified disjoint |
| --- | --- | --- |
| A | 1, 2, 3 | Row #1 writes one workflow and its test. Row #2 writes the llm package, the config contract, the stamp and four test modules. Row #3 writes `measured.py`, its test and the instrument log. No pair shares a file. |
| B | 4 | Alone. It shares `backend/idhazh/classify/calls.py`, `docs/architecture/summarize/prompt.md`, `docs/architecture/summarize/throughput.md` and `docs/concepts/config.md` with row #2, and `docs/reference/measurements.md` with row #3, so it cannot run beside either. That file overlap is the whole of its `Depends-on`. |
| C | 5, 6 | Row #5 writes `server.py`, `test_summarize.py`, a new fixture directory and `digest.yml`. Row #6 writes `app_config.py`, the config files, the schemas, `config.py` and `test_contracts.py`. No shared file. |
| D | 7, 11 | Row #7 is documentation only. Row #11 is the contract and the llm package. No shared file. |
| E | 12, 13 | Row #12 writes `sanitize.py`, `app_config.py` and two test modules. Row #13 writes `taxonomy.py`, `visual.py`, `measured.py` and the instrument log. No shared file. |
| F | 8 | Alone. It rewrites the workflow row #1 fixed and reads the shapes rows #6 and #7 created. |
| G | 9 | Alone. It shares the how-to with row #8 and `AGENTS.md` with row #4. |
| H | 10 | Alone. It is the last row and it touches most of the summarize package. |

---

### Row #1 - The runtime sweep reaches for a key that is not there

- **Scope:** The runtime-sweep job builds a candidate config by updating a key that does not exist, so the job dies at that line.
- **Files touched:**
  - `.github/workflows/measure.yml`
  - `backend/tests/test_workflows.py`
- **Acceptance gates:** local - `python backend/utilities/gate_lock.py -- python -m pytest backend/tests/test_workflows.py -q`. CI - `ci.yml`. Manual post-merge proof: one dispatch of `measure.yml` with `target=runtime` and `runtime_candidate=baseline` reaching the server-start step.
- **Oracle:** `python -c "import json; json.load(open('config/idhazh.json'))['models']['summarize']['inference']"` resolves and the same expression without `summarize` raises `KeyError`. The patched line must use the path that resolves.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The correct path is `payload["models"]["summarize"]["inference"]`. Lines 367, 862 and 894 of the same file already read `["models"]["summarize"]["sha256"]`, so the file disagrees with itself. | Carmack, 2026-09-13 |
| 2 | This ships before row #8 rewrites the workflow and before row #6 moves the block again, so the fix is provably the thing that made a dispatch work. | Fowler, 2026-09-13 |
| 3 | A test is added to `backend/tests/test_workflows.py`, which already asserts this file's dispatch inputs, job names and retention at fifteen sites. The assertion is that every config path the workflow's inline Python indexes resolves against the committed config. | Fowler, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Fold the fix into row #8 | Row #8 rewrites the job; a defect fixed inside a rewrite cannot be shown to be the thing that fixed it. | Fowler |
| 2 | Delete the runtime-sweep job as dead | It is the only arm in the tree that starts a real server and runs real work, which is what row #8 needs. Deleting it costs the bench its per-item arm. | Carmack |

---

### Row #2 - The turn envelope moves onto the model entry

- **Scope:** The four turn strings move out of a global package file onto the model entry, so a model whose turns differ is a config change rather than a source edit.
- **Contract introduced:** `ModelRef.turns`, a required nested model with no default, carrying `turn_opening: str`, `turn_closing: str`, `reply_opening: str`, `reply_opening_thinking: str`, `declared_for: Sha256`.
- **Files touched:**
  - `backend/idhazh/prompts/turn_markers.json` (deleted)
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/fingerprint.py`
  - `backend/idhazh/classify/calls.py`
  - `backend/utilities/measure_two_calls.py`
  - `config/idhazh.json`
  - `schemas/app-config.schema.json`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `backend/tests/test_contracts.py`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_classify.py`
  - `docs/concepts/config.md`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/throughput.md`
  - `docs/architecture/summarize/model-boundary.md`
- **Acceptance gates:** local - `python backend/utilities/gate_lock.py -- ruff check backend`, `mypy backend`, the contract export followed by `git diff --exit-code -- schemas/`, and `python -m pytest backend/tests/test_contracts.py backend/tests/test_fingerprint.py backend/tests/test_summarize.py backend/tests/test_classify.py -q`. CI - `ci.yml` full suite and the drift gate.
- **Oracle:** the rendered prompt for a fixture article is **byte-identical** before and after. Capture the render on the base tree into a fixture, assert equality on the branch. One differing byte stops the row (ESCALATE trigger 4).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The block is nested and named `turns`, not four flat fields. The four strings are meaningless apart and always move together. | Fowler, 2026-09-13 |
| 2 | `turns` is required with no default. An entry that forgets its markers must fail rather than inherit the incumbent's. `ModelRef` already requires `id`, `repo`, `file` and `quantisation`, and the config is committed, so a fresh clone is unaffected. | Fowler, 2026-09-13 |
| 3 | `turns.declared_for` must equal the entry `sha256`, the same validator shape `inference` carries. The 8B-to-9B move on 2026-08-27 is the recorded event where a settings block was left behind. | Fowler, 2026-09-13 |
| 4 | `turn_opening` must contain the role placeholder, and `turn_closing` must be non-empty. A template substitution over a string with no placeholder returns it unchanged and renders every turn with no role header. `continued_prompt` splices on `turn_closing`, so an empty seam breaks the prefix silently. | Fowler, 2026-09-13 |
| 5 | The marker lookup is keyed by entry. It is a single-slot cache today with no model key, which is correct for one global file and a correctness bug the instant one process holds two entries - which is what row #8 does. | Carmack, 2026-09-13 |
| 6 | **`opening_of` sorts its candidate openings longest-first before matching.** It tries the thinking opening before the plain one and matches on a suffix, which is safe for the incumbent only because neither string is a suffix of the other. Longest-first is a total fix: a shorter opening can never shadow a longer one. A unit test drives a built entry where one opening is a suffix of the other. | Carmack, 2026-09-13 |
| 7 | **`NOT_DIGESTED`'s closed universe widens from `InferenceConfig.model_fields` to cover `ModelRef` as well.** It would otherwise be closed over the wrong universe the moment a model fact lives outside `InferenceConfig`, leaving per-model prompt-shaping fields in no stamp and in no closed set with no test saying so. The digest itself ships in row #10. | Fowler, 2026-09-13 |
| 8 | `backend/idhazh/prompts/` keeps only text this project wrote and digests as `prompt_sha256`. Facts about somebody else's weights move to config and are pinned by `declared_for`. | Fowler, 2026-09-13 |
| 9 | The deleted file's reappearance is refused at config load. An operator editing a file nothing reads is the silent failure the package location existed to prevent. | Fowler, 2026-09-13 |
| 10 | `AppConfig.version` is stamped and one changelog entry appended. No read-side alias for the old spelling - the precedent is `refuse_a_removed_knob` with `SUPERSEDED_MODELS_NAMES`, because a config file is a file a person can edit and silent acceptance teaches the wrong spelling. | Fowler, 2026-09-13 |
| 11 | The app-config fixture gains `turns` in sorted key order in this same commit. `test_fixture_round_trips_byte_identically` fails otherwise, and a required field absent from the fixture fails validation before that. | Fowler, 2026-09-13 |
| 12 | **`turns.declared_for` is `Sha256 \| None`, not a required `Sha256`.** The row's contract line said required; decision 3's own words say "the same validator shape `inference` carries", and that block is nullable. Required would make the comparison against `entry.sha256` unsatisfiable for an unmeasured entry, silently repealing the "both digests absent is legal" rule the validator states in its own docstring - a narrowing of `sha256` from optional to required that decision 2 never priced. The two blocks are checked in one loop, each carrying its own repair clause. | Fowler, 2026-09-13, during execution |
| 13 | **`turns` is required on a new `ModelEntry(ModelRef)`, not on `ModelRef`.** Found during execution: `run_manifest.ModelUse` embeds `ModelRef`, and no `model_ref` a run has ever written carries markers, so requiring it on the shared class stops `publish_run_days.build_day` reading every committed day (`CLAUDE.md` section 11). `ModelEntry` is what a person declares and `ModelRef` is what a run recorded. What it gives up is that `run.json` never records the envelope; `RunRecord.inputs.prompt_sha256` digests both turns rendered through it, so a moved marker still moves the stamp. `run-manifest.schema.json` moves by one description line and no field. | Fowler, 2026-09-13, during execution |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Leave the file where it is and add a model key inside it | A second place a model fact lives, held apart from the entry that names the weights, with nothing pinning the two together. That is the failure being fixed, relocated. | Fowler |
| 2 | Re-implement the chat template so markers are derived | A second renderer with no tests, against a template the server already holds and will answer for. Row #5 reconciles instead. | Andre |
| 3 | Ship the markers' digest into the run stamp in this row | It is a real hole, but it is behavioural and this row must be byte-identical. It goes to row #10, the first row that makes the markers move. | Fowler |
| 4 | A validator refusing suffix-related openings, instead of decision 6 | It would refuse a legal pair for no gain. Sorting is a total fix. | Carmack |

---

### Row #3 - Every tokenizer-shaped constant names the weights it was taken against

- **Scope:** Constants measured through one model's tokenizer carry no pin to it, so a swap leaves them silently attributed to the wrong model.
- **Contract introduced:** `Measured.subject: Sha256 | None`, required non-null on any record whose method reads a tokenizer.
- **Files touched:**
  - `backend/idhazh/measured.py`
  - `backend/tests/test_measured.py`
  - `docs/reference/measurements.md`
- **Acceptance gates:** local - ruff, mypy, `python -m pytest backend/tests/test_measured.py -q`. CI - `ci.yml`.
- **Oracle:** a built `Measured` whose `subject` is not the configured entry's `sha256` is refused, and the refusal names both digests. Driven from a built value, never from a walk over committed data.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `Measured` gains a `subject` naming the weights digest a reading was taken against, and a gate asserts every tokenizer-derived record's subject equals the configured entry's `sha256`. | Fowler, 2026-09-13 |
| 2 | `when_it_fires` on all four call-one records gains the model swap as a trigger. The field exists and already carries the other two triggers; a record that says when to retake it and omits the largest trigger is worse than one that says nothing. | Fowler, 2026-09-13 |
| 3 | Timing records do not gain a subject. A second and a resident set belong to the box that took them; a token count belongs to the tokenizer. Only tokenizer-derived records are pinned. | Carmack, 2026-09-13 |
| 4 | **The gate names three sites outside `measured.py` that it cannot reach, and row #13 retakes them.** The taxonomy definition budget and the visual plan budgets were measured against the retired 8B, and the extractor's tokens-per-word ratio is tokenizer-shaped. The 8B-to-9B move already left all three behind, which is proof rather than risk. | Fowler, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Retake the three outside constants in this row | They are measurements with their own oracle and their own hardware line. This row builds the gate that names them; row #13 takes the readings. | Fowler |
| 2 | Derive the constants at run time by asking the server to tokenize | Turns a constant into a start-up network call on every shard, for numbers that move only when the model or a prompt moves. | Carmack |

---

### Row #4 - Benchmark records lose the date from their filename

- **Scope:** A benchmark record is named for the question it answers; the date moves inside the page onto the reading.
- **Files touched:**
  - `docs/reference/benchmarks/2026-09-11-day-window-read.md` -> `day-window-read.md`
  - `docs/reference/benchmarks/2026-09-12-instructions-in-front.md` -> `instructions-in-front.md`
  - `docs/reference/benchmarks/2026-09-12-prerender-on-and-off.md` -> `prerender-on-and-off.md`
  - `docs/reference/benchmarks/2026-09-12-two-call-re-read.md` -> `two-call-re-read.md`
  - `docs/reference/benchmarks/2026-09-13-articles-that-state-a-whole.md` -> `articles-that-state-a-whole.md`
  - `docs/reference/benchmarks/2026-09-13-two-call-window-sizing.md` -> `two-call-window-sizing.md`
  - `docs/reference/documentation-structure.md`
  - `docs/reference/measurements.md`
  - `docs/reference/measurements-site.md`
  - `AGENTS.md`
  - `backend/idhazh/classify/calls.py`
  - `docs/architecture/publishing/frontend.md`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/throughput.md`
  - `docs/concepts/config.md`
  - `TODO/20260905-11-two-call-planner-plan.md`
  - `TODO/20260910-23-article-classification-plan.md`
  - `TODO/20260910-24-day-sharded-ledgers-plan.md`
  - `TODO/20260911-26-retire-prerender-plan.md`
- **Acceptance gates:** local - `python backend/utilities/doc_load.py` before and after, and `git grep -c "benchmarks/2026-"` returning nothing. CI - `ci.yml` and the link check.
- **Oracle:** zero matches for `benchmarks/2026-` anywhere in the tree, and every renamed file reachable from at least one inbound link. Twenty-four inbound lines across ten files were counted on 2026-09-13 by `git grep -c`; the row re-counts rather than trusting that number.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The convention becomes `docs/reference/benchmarks/<what-was-measured>.md` - a kebab-case noun phrase naming the question. | Owner, 2026-09-13, under section 0 |
| 2 | A re-run **replaces** the page and moves `Last Updated`; git history holds what it said. A second file answering a question that already has one is the collision, and it becomes visible rather than hidden behind a filename ordering. | Fowler, 2026-09-13 |
| 3 | The class stops being Frozen and becomes Living, one question one answer. The dated filename reproduced across a directory the same log-of-readings failure the instrument log was split to escape. | Fowler, 2026-09-13 |
| 4 | This is more compliant with the measurement guardrail, not less. A reading becomes a variable rather than a log entry; the dated scheme produced several files per quantity where only the ordering said which governs, and a reader arriving by search never sees the ordering. | Andre, 2026-09-13 |
| 5 | **Four sites carry the old rule and all four change in this commit:** `docs/reference/documentation-structure.md` line 51, `docs/reference/measurements.md` line 24, `AGENTS.md` line 41, and `TODO/20260910-23-article-classification-plan.md` line 649. Missing any leaves the old convention alive, and one of them is the page that enforces it. | Fowler, 2026-09-13 |
| 6 | The documentation-structure row needs **three cells changed**, not one: the path cell loses the date element; the mutability cell goes from `**Frozen** - a run happened on a date and its conditions do not change` to `Living, one question one answer - a re-run REPLACES the page and moves **Last Updated**; git history holds what it said`; and the forbidden cell gains `a date in the filename`. | Fowler, 2026-09-13 |
| 7 | The `AGENTS.md` change is exactly `named for what it measured and the date` -> `named for what it measured and nothing else - a re-run replaces that page rather than adding a second one`. The `docs/reference/measurements.md` change is exactly `named for what it measured and the date it` -> `named for what it measured, and it`. | Fowler, 2026-09-13 |
| 8 | Plan-docs under `TODO/` keep their date prefix. They are a dated sequence of work rather than an answer to a question. | Fowler, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the date and add an alias page | Two names for one page, and the alias is the one search finds. | Fowler |
| 2 | Rename only files created from now on | The directory carries two conventions, and the rule deciding which to use is the file's own age. | Fowler |

---

### Row #5 - Five things the server proves before the first item

- **Scope:** A start-up probe proves the entry against the running server on five axes and refuses the run on any disagreement.
- **Files touched:**
  - `backend/idhazh/llm/server.py`
  - `backend/tests/test_summarize.py`
  - `tests/fixtures/llm/apply-template-probe.json` (new; this row creates the directory)
  - `tests/fixtures/llm/props-probe.json` (new)
  - `.github/workflows/digest.yml`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/model-boundary.md`
- **Acceptance gates:** local - ruff, mypy, `python -m pytest backend/tests/test_summarize.py -q`. CI - `ci.yml` full suite. Manual post-merge proof: one `digest.yml` dispatch reaching the first item.
- **Oracle:** every arm has a two-armed test. With the fixture's values the probe agrees and the server starts; with one value changed in a built entry the probe refuses and the message names both sides. A check nobody has made fail is a check nobody has tested.

**The five arms:**

| Arm | What it proves | How | What it catches |
| --- | --- | --- | --- |
| 1 | The render agrees | Send a fixed two-turn probe to the server's own template endpoint and compare **token ids from the tokenize endpoint, not bytes** | Wrong markers rendering a prompt with no turn structure that the grammar still accepts - worse summaries, no error. Token ids rather than bytes because the template's own output includes any leading sequence token, so a byte comparison forces the entry to declare it and the runtime then adds a second one. |
| 2 | The prefix cache is live | Two probe calls; assert the second's cached-token count is at least the first's prompt-token count | A llama.cpp build that flips the prompt-cache default, a seam that re-splits, a leading-token mismatch, or a slot lost to parallelism. Each silently doubles prefill cost per item and nothing currently detects any of them. The cached count is already parsed from the timings block, so this is one comparison against a number already on the wire. |
| 3 | Constrained decoding still constrains | One call under a schema admitting exactly one string; fail the run if the reply differs | The schema-to-grammar converter silently dropping a feature, so the grammar is weaker than the schema with nothing red. Built from `call_two_schema()` itself, never from a fixture, because that schema is derived dynamically and a fixture would be a second copy that drifts. |
| 4 | The loaded weights are the declared weights | Assert the architecture reported by the server properties equals the entry's declared `arch`, beside the filename assertion `digest.yml` already makes | A repackaged GGUF under a familiar name. A candidate reporting a familiar architecture is exactly the case where every other check passes and only the words get worse. |
| 5 | The window is inside the trained window | Assert the configured `n_ctx` does not exceed the model's own trained length as the server reports it | The no-context-shift flag refuses past `n_ctx`, never past the trained length, so a candidate with a short native window under a larger `n_ctx` degrades silently instead of refusing. A conservative default is not an assertion. |

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Arm 1 is the field that converts the declared envelope from a claim into a fact, and row #2 is not safe to have shipped without it. If one pull request is taken from this plan, it is rows #2 and #5 together. | Andre and Fowler, agreeing, 2026-09-13 |
| 2 | `ModelRef` gains `arch: str`, required, carrying the GGUF architecture string. | Carmack, 2026-09-13 |
| 3 | Every arm is driven in tests by a recorded response. No test touches the network. | Fowler, 2026-09-13 |
| 4 | No arm gains a flag to skip it. The proof is what paid for moving the envelope out of the package; a skip returns the tree to worse-summaries-and-no-error with extra ceremony. | Fowler, 2026-09-13 |
| 5 | The template endpoint is already named in `backend/utilities/measure_two_calls.py`, which is one of two sites in the tree that mention it. That file's caution is against using it to tokenize a prompt the server was never sent - a different use from reconciling a render. | Carmack, 2026-09-13 |
| 6 | Arm 2 protects the incumbent today, before any swap, and is the cheapest item in this plan. | Carmack, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Compare the chat template digest off the server properties instead of arm 1 | It records what the runtime would apply on the chat route. The rendered-completion route never applies it, so on the route that summarizes it reconciles nothing. | Andre |
| 2 | Run the probe once per run rather than per server | Shards start their own servers. A per-run probe proves one shard's server. | Carmack |
| 3 | Declare the leading sequence token as an entry field | It makes a correct entry fail the byte probe and an incorrect one pass. Comparing token ids removes the field and the failure together. | Carmack |

---

### Row #6 - One complete config file per model, selected by a pointer

- **Scope:** Each model's whole entry lives in its own file; the committed config names which file is active and carries no model block of its own.
- **Contract introduced:** `AppConfig.models_file: str`, and `ModelsConfig` promoted to a `Contract` with its own generated schema. `AppConfig.models` is removed.
- **Files touched:**
  - `config/models/qwen3.5-9b-q4km.json` (new)
  - `config/idhazh.json`
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/config.py`
  - `schemas/app-config.schema.json`
  - `schemas/models-config.schema.json` (new)
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `tests/fixtures/contracts/models-config/every-knob-differs-from-the-committed-config.json` (new)
  - `backend/tests/test_contracts.py`
  - `docs/concepts/config.md`
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:** local - ruff, mypy, the contract export followed by `git diff --exit-code -- schemas/`, `python -m pytest backend/tests/test_contracts.py -q`. CI - `ci.yml` full suite and the drift gate.
- **Oracle:** the resolved entry is byte-identical to the same entry serialized from **`origin/main` at row #2 DONE**, which is the fixed baseline. The pointer changes where bytes are read from, never what they say.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Self-contained files, never a merge. Each file is one whole models payload; the committed config carries a pointer and no model block. No key exists in two places, so there is no resolution order and no question of which value won. | Fowler, 2026-09-13 |
| 2 | **The swap is one line:** the pointer in `config/idhazh.json` changes from the incumbent's filename to the candidate's. **The revert is the same line, back**, and it costs nothing because adoption never mutated the incumbent's file. | Fowler, 2026-09-13 |
| 3 | The refusal on a settings block declared for different weights, and `refuse_a_removed_knob`, both run per file. They run on one merged product today; per file they name which file is wrong. | Fowler, 2026-09-13 |
| 4 | The run stamp is unaffected. `fingerprint.build_inputs` takes `ModelRef` and `InferenceConfig` objects rather than JSON, so it cannot tell which file they were parsed from. No stamp work is owed by this row. | Fowler, 2026-09-13, verified against `backend/idhazh/fingerprint.py` |
| 5 | The per-model file owns the `turns` block row #2 put on the entry, so a candidate is wholly described by one file. | Andre, 2026-09-13 |
| 6 | The slug is shared by the config file and the dossier page, so one name reaches both. | Fowler, 2026-09-13 |
| 7 | Migration is the deletion of the model block from the committed config in this same commit, plus the version stamp and the changelog entry. No alias, no dual read. | Fowler, 2026-09-13 |
| 8 | `ModelsConfig` becoming a `Contract` needs its own fixture, because `test_every_contract_has_at_least_one_fixture` fails otherwise. | Fowler, 2026-09-13 |
| 9 | **This row builds the identity-branch test.** An ESCALATE trigger with no test is a comment. The shape copies the existing test that keeps `server_argv` the only place a flag is spelled: walk the syntax tree of everything under `backend/idhazh/llm/` and fail on any comparison whose operand is a model id, repo or filename. A branch on a value is config; a branch on an identity is a fork. | Carmack, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Layered defaults with per-model overrides | A future with several roles or several servers would deduplicate shared settings. There is one role, so the saving today is zero and the cost is a resolution order a reader cannot see from any single file. The two refusals would also run against a product no file contains. Revisit when a second role is real. | Fowler |
| 2 | Keep one file and add a second model entry beside the first | The committed config then carries every candidate ever tried, and the refusals cannot tell an active entry from an abandoned one. | Fowler |
| 3 | Put the candidate file only under the gitignored scratch directory | That is where a qualification candidate belongs and row #8 uses it. An adopted model must be committed and reviewable. | Carmack |

---

### Row #7 - The model dossier, and the index that points at every one

- **Scope:** One page per model holding that model's identity and its one current reading of every quantity, plus an index pointing at all of them.
- **Files touched:**
  - `docs/reference/models.md` (new)
  - `docs/reference/models/qwen3.5-9b-q4km.md` (new)
  - `docs/reference/measurements.md`
  - `docs/reference/documentation-structure.md`
  - `docs/agents/bootstrap.md`
- **Acceptance gates:** local - `python backend/utilities/doc_load.py` before and after. CI - `ci.yml` and the link check. Manual post-merge proof: a reader opens the index and reaches every dossier in one hop.
- **Oracle:** every model-specific quantity currently in the instrument log appears exactly once after this row - on the dossier - and the instrument log's former row is a link. No figure exists in two places with two values.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The dossier is a new doc class, Living, and does not replace the benchmark record class, which stays per question. Redefining the record to be per model collapses two mutability rules onto one page. | Fowler, 2026-09-13 |
| 2 | **The page holds:** identity, digest, byte count, licence as an SPDX string, quantisation and architecture; on-disk size against the cache total; one current reading each of prefill at three prompt lengths, decode, peak resident set, model load time and seconds per item; the qualification verdict with its date; a status line; and a link to every benchmark record behind it. | Fowler, 2026-09-13 |
| 3 | The instrument log keeps only quantities that are not model-specific - site weight, fetch, retention. Model-specific rows become a link. That is most of its length. | Fowler, 2026-09-13 |
| 4 | This makes the one-current-reading guardrail mechanically checkable for the first time: one quantity, one model, one row. Naming the decode rate today requires reading which model a row was about. | Andre, 2026-09-13 |
| 5 | The status line is the only place a model's lifecycle is written - `evaluated`, `incumbent`, `superseded` - and row #9's adopt and revert steps move it. | Fowler, 2026-09-13 |
| 6 | `licence` gets no validator. It is a dossier field with one human reader, and a validator over a licence string would assert a legal judgement. | Andre, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Make the dossier the benchmark record | One page would be both per-model and per-run, so a re-run of one arm would either rewrite readings it did not take or append beside them. | Fowler |
| 2 | Generate the dossier from the ledger at build time | The dossier carries a verdict and a status, which are judgements. A workflow cannot write a judgement. | Andre |

---

### Row #11 - Where the system text goes, and which keyword the runtime is told

- **Scope:** The envelope facts a model cannot share - system placement, its joiner, and the thinking keyword - move onto the entry; the prompt text stays one global set.
- **Contract introduced:** on `ModelRef.turns`: `system_role: Literal["own_turn", "fold_into_first_user"]`, `system_joiner: str | None`, `thinking_kwarg: str | None`.
- **Files touched:**
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/fingerprint.py`
  - `config/models/qwen3.5-9b-q4km.json`
  - `schemas/app-config.schema.json`
  - `schemas/models-config.schema.json`
  - `tests/fixtures/contracts/models-config/every-knob-differs-from-the-committed-config.json`
  - `backend/tests/test_contracts.py`
  - `backend/tests/test_summarize.py`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/model-boundary.md`
- **Acceptance gates:** local - ruff, mypy, contract export plus `git diff --exit-code -- schemas/`, `python -m pytest backend/tests/test_contracts.py backend/tests/test_summarize.py -q`. CI - `ci.yml` full suite and the drift gate.
- **Oracle:** two arms. Under `own_turn` the rendered prompt is byte-identical to the incumbent's. Under a built `fold_into_first_user` entry the rendered bytes differ **while `prompt_sha256` is unchanged** - which is the envelope-and-content split of section 0.2 stated as a test.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `system_role` is a closed enum read by `render_prompt`, which never reads a model id. Without it a model with no system role cannot be configured at all, which defeats the plan's intent. | Andre, 2026-09-13 |
| 2 | `system_joiner` is required under `fold_into_first_user` and refused under `own_turn`. A dead field is a field somebody will trust. | Fowler, 2026-09-13 |
| 3 | `thinking_kwarg` defaults to the incumbent's keyword. Null means send no template keywords at all **and** forces `inference.thinking` false, enforced by a cross-field validator. Null with thinking on claims a channel no template carries, and the reasoning refusal then fails every item on shape. | Andre, 2026-09-13 |
| 4 | The keyword name is a model fact, not a project constant. It is spelled in this project's source today and sent to every model. | Fowler, 2026-09-13 |
| 5 | Prompt **text** does not move, and section 0.2 rule 2 is the reason, restated in the row that introduces the envelope: `prose_changed_alone` returns nothing whenever `model_sha256` moved, so a prompt edit made because the new model needed it would be hidden inside the swap forever. | Andre, 2026-09-13 |
| 6 | The two fold strategies are two code paths selected by an enum. A turn topology cannot be a string without inventing a template language, and a template language in config is a second renderer nobody tests. | Fowler, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A per-model prompt text directory | A candidate needing different instruction wording could be tuned into passing. That is the intended loss: it fails qualification honestly instead of being fitted to it, and `prompt_sha256` keeps one meaning. | Andre |
| 2 | A free-form system prefix string instead of the enum | It is a turn topology wearing a string, and it puts untrusted-shaped text into the prompt envelope. | Andre |
| 3 | Fold these fields into row #2 | Row #2 must be byte-identical and these change what `render_prompt` can do. Different risk profile. | Fowler |

---

### Row #12 - The sanitizer learns the control tokens of the model it guards

- **Scope:** The control-token pattern covers the families a configured entry can bring, and an entry whose markers the sanitizer would not strip is refused at load.
- **Files touched:**
  - `backend/idhazh/sanitize.py`
  - `backend/idhazh/contracts/app_config.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_canaries.py`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/model-boundary.md`
- **Acceptance gates:** local - ruff, mypy, `python -m pytest backend/tests/test_summarize.py backend/tests/test_canaries.py -q`. CI - `ci.yml` full suite.
- **Oracle:** built entry, never a walk. An entry declaring a marker the sanitizer does not strip is refused at config load, and the refusal names the marker. Second arm: `SANITIZER_VERSION` moved in the same commit, and a stamp built before and after differs in exactly that one field.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The trust boundary is crossed once, at extraction, and the pattern is the control (Guardrail #11). It knows three families today. A swap to a model outside them reopens forged-turn injection with nothing red. | Andre, 2026-09-13 |
| 2 | The refusal is at config load, not at extraction. An entry whose markers the sanitizer cannot strip is a misconfiguration, and finding it on the first article is finding it too late. | Andre, 2026-09-13 |
| 3 | `SANITIZER_VERSION` moves in the same commit. It is a stamp input, so every item after the widening is correctly marked as produced under a different control. | Fowler, 2026-09-13 |
| 4 | This is a reader-safety boundary, so it is surfaced and never adapted (ESCALATE trigger 5). A widening that cannot be proved to strip a declared marker stops the row rather than shipping with a narrower pattern. | Andre, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Derive the pattern from the entry's markers alone | The threat is forged turns from any family, not only the configured one. A reader is not protected by a filter that only knows the model in use today. | Andre |
| 2 | Leave the pattern as it is and note the limitation | A limitation named with no next move is an unfinished answer (section 0d), and this one is a reader-safety boundary. | Andre |

---

### Row #13 - Retake the two budgets that were sized on a retired vocabulary

- **Scope:** The taxonomy definition budget and the visual plan budgets are re-measured against the configured weights and given a subject, closing the gap row #3's gate names but cannot reach.
- **Files touched:**
  - `backend/idhazh/contracts/taxonomy.py`
  - `backend/idhazh/contracts/visual.py`
  - `backend/idhazh/measured.py`
  - `docs/reference/measurements.md`
- **Acceptance gates:** local - ruff, mypy, `python -m pytest backend/tests/test_measured.py backend/tests/test_contracts.py -q`. CI - `ci.yml`.
- **Oracle:** each retaken number's `subject` equals the configured entry's `sha256`, and row #3's gate refuses a built value whose subject does not. Readings come from the runtime's own tokenizer against the committed weights, with hardware and date inline.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Both budgets were measured against the retired 8B, which is not the incumbent. The 8B-to-9B move left them behind, so this is a correction rather than a precaution. | Fowler, 2026-09-13 |
| 2 | The numbers are taken by asking the runtime's own tokenizer, not by reasoning about a vocabulary. The tokenizer is the model's and it moves when the model does. | Carmack, 2026-09-13 |
| 3 | A number whose retake changes it gets its old reading deleted, not kept beside the new one. A reading is a variable; git history holds what it used to say. | Fowler, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Re-measure these in CI on every swap | A workflow would be writing a measurement into a commit, which this tree reserves for people. The gate names the number as wrong; a person takes the reading. | Carmack |

---

### Row #8 - Both bench arms in one workflow, emitting a page ready to paste

- **Scope:** The benchmark runs raw throughput and a real server with real work as two chained jobs over one candidate, and emits the dossier body already filled in.
- **Files touched:**
  - `.github/workflows/measure.yml`
  - `.github/scripts/start-llama-server.sh`
  - `backend/utilities/measure_llm.py`
  - `backend/tests/test_measure_llm.py`
  - `backend/tests/test_workflows.py`
  - `docs/how-to/evaluate-new-summarizer-model.md`
- **Acceptance gates:** local - ruff, mypy, `python -m pytest backend/tests/test_measure_llm.py backend/tests/test_workflows.py -q`. CI - `ci.yml`. Manual post-merge proof: one real dispatch against the incumbent's own digest.
- **Oracle:** dispatched against the incumbent, the emitted dossier reproduces the committed dossier's readings within their stated spread. A bench that cannot reproduce the model it was calibrated on is measuring something else.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One workflow, two jobs chained by dependency: raw throughput first, then a real server running real work. One candidate slug is typed once, and job two restores job one's weights cache instead of repeating the 118-second download. | Carmack, 2026-09-13 |
| 2 | Two jobs, not one. One job puts both arms under a single six-hour ceiling and loses per-arm restart. | Carmack, 2026-09-13 |
| 3 | The candidate is a repository reference at an immutable commit plus file and expected digest, materialized into the gitignored candidate directory. Empty means today's behaviour. **A candidate is therefore benchmarked without touching the committed config at all.** | Carmack, 2026-09-13 |
| 4 | Raw throughput alone is not enough. It never starts a server, so it yields no seconds per item and no resident set. The project's own how-to already concedes that raw fit is not production fit. | Carmack, 2026-09-13 |
| 5 | Artifact retention rises from seven days to ninety. Seven days is shorter than the gap between benchmarking and deciding, and the emitted files are kilobytes against a 500 MB ceiling. `backend/tests/test_workflows.py` asserts the current value and moves with it. | Carmack, 2026-09-13 |
| 6 | The workflow never writes the committed config, never publishes, and never scores quality. A bench that can score becomes the selector, and a bench that can adopt is an adoption path with no gates in it. | Andre, 2026-09-13 |
| 7 | Qualification is not chained to this. The bench is cheap and answers whether a model fits; qualification is expensive and answers whether it is good. Chaining spends the expensive one on candidates already dead. | Carmack, 2026-09-13 |
| 8 | The resident-set arm records rather than gates, and names the measurement that would settle headroom: the split between anonymous and file-backed pages, taken by the same sampler on the runner. Memory refuses nothing in this plan. | Carmack, 2026-09-13 |
| 9 | **The bench reports a cold arm as well as a warm one.** The first day after a swap is all-cold on every shard at once - the cache key carries the filename and revision - so a warm-box reading is not the first real day. One cold model-load and one cold weights-fetch figure, labelled as such. | Carmack, 2026-09-13 |
| 10 | The artifact is the page body, not JSON to reformat: numbers filled, hardware, build and spread inline, `Last Updated` set. Transcription is a copy. | Fowler, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A third workflow dedicated to benchmarking | A second copy of the weights fetch, the digest verification, the hardware capture and the server start, and a fourth place to look for a number. | Carmack |
| 2 | Commit the dossier from CI | Every CI commit lands in the range the scheduled prune must rewrite, and doc routing loses its review. The precedent is that CI commits ledgers and people commit prose. | Fowler |
| 3 | Carry one faithfulness number in the bench to catch a disaster early | A scorer inside the bench becomes the selector, and the alarm stops being able to detect drift. | Andre |
| 4 | Gate the bench on peak resident set | A candidate that would exhaust a runner passes the bench and fails later in qualification, after the corpus replay is paid for. The number that would justify a gate has never been taken. | Carmack |

---

### Row #9 - The runbook: swap and revert in one line each

- **Scope:** The how-to becomes a runbook whose every step is a real command or a real one-line edit.
- **Files touched:**
  - `docs/how-to/evaluate-new-summarizer-model.md`
  - `docs/how-to/fine-tune-a-model.md`
  - `docs/reference/models.md`
  - `docs/agents/bootstrap.md`
  - `AGENTS.md`
  - `notebooks/finetune.ipynb`
  - `backend/tests/test_notebooks.py`
- **Acceptance gates:** local - `python backend/utilities/doc_load.py`, `python -m pytest backend/tests/test_notebooks.py -q`. CI - `ci.yml` and the link check.
- **Oracle:** read the page and execute it against the incumbent's own digest end to end. Every step runs as written. **A step that says to edit source code fails the row**, and the row then names the change that removes the step.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The page's standing sentence that there is no one-command model swap does not survive. Its replacement is equally honest: the swap is one line in the committed config, and the qualification is not one command and never will be, because eleven gates on a frozen corpus is the price of knowing. | Fowler, 2026-09-13 |
| 2 | Three blocks: benchmark a candidate, adopt, revert. Adopt is the pointer line, the two status lines, and the fine-tune check below. Revert is the pointer line back plus the two status lines, and nothing else - no source edit, no schema regeneration, no cache purge, because the incumbent's cache key is keyed on its own digest and is still valid. | Fowler, 2026-09-13 |
| 3 | The qualification dispatch takes one argument, the model filename, replacing the several candidate arguments it takes today. | Carmack, 2026-09-13 |
| 4 | **A base-model swap invalidates any fine-tuned adapter, and the adopt block says so.** An adapter loads onto a mismatched base without raising and the damage arrives as a quality drop nobody can attribute. The fine-tuning notebook's first cell refuses when the configured entry's base repository is not the one the adapter was trained against. | Fowler and Andre, 2026-09-13 |
| 5 | **A swap makes the training corpus mixed-teacher, and that is recorded rather than prevented.** Corpus rows already carry a model id and the corpus tool already counts the mix; the runbook says to read that count before training. | Andre, 2026-09-13 |
| 6 | The cold-start cost from row #8 decision 9 is stated in the adopt block, so nobody reads the warm bench figure as the first day's cost. | Carmack, 2026-09-13 |
| 7 | Adoption stays a Level 5 decision with a person reading the gates. The gates inform it; they do not make it. | Fowler, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A script that performs the adopt sequence | It would edit the committed config and open a pull request, which is an adoption path that runs without a person reading the gates. | Fowler |
| 2 | Keep the current page and add the runbook beside it | The current page is the one an operator opens. A runbook beside it is a second answer to the same question. | Fowler |
| 3 | Refuse a swap while a fine-tuned adapter is configured | The refusal belongs where the adapter is loaded, not where the base is chosen. Swapping the base is legitimate; loading a stale adapter onto it is not. | Andre |

---

### Row #10 - Two spans on one call, so the model can think

**Level 5, and signed off by the owner on 2026-09-13.** It changes the summarize contract, three hard refusals, and the shard timeout. It runs without a further pause, and stops only on the two conditions in ESCALATE trigger 1.

- **Scope:** A call becomes an unconstrained thinking span followed by a schema-constrained answer span on the same slot, and the thinking is discarded before anything reads it.
- **Contract introduced:** on `ModelRef.turns`, `thinking_close: str | None`. On `InferenceConfig`, `max_think_tokens: int` and `max_answer_tokens: int`; `max_output_tokens` and `thinking` retire into the refused-knob list. `PipelineInputs` gains `turn_markers_sha256`.
- **Files touched:**
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/summarize.py`
  - `backend/idhazh/classify/calls.py`
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/contracts/fingerprint.py`
  - `backend/idhazh/fingerprint.py`
  - `backend/idhazh/evals/qualify.py`
  - `config/models/qwen3.5-9b-q4km.json`
  - `schemas/app-config.schema.json`
  - `schemas/models-config.schema.json`
  - `schemas/run-manifest.schema.json`
  - `tests/fixtures/contracts/models-config/every-knob-differs-from-the-committed-config.json`
  - `backend/tests/test_contracts.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/test_qualify.py`
  - `backend/tests/test_workflows.py`
  - `.github/workflows/digest.yml`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/throughput.md`
  - `docs/architecture/contracts/determinism.md`
- **Acceptance gates:** local - ruff, mypy, contract export plus schema diff, `python -m pytest backend/tests/test_contracts.py backend/tests/test_summarize.py backend/tests/test_classify.py backend/tests/test_fingerprint.py backend/tests/test_qualify.py backend/tests/test_workflows.py -q`. CI - `ci.yml` full suite. **Adoption gate: a qualification run comparing the incumbent against the incumbent-with-thinking on the same frozen corpus, same build, interleaved repeats.**
- **Oracle:** on a recorded thinking reply, the persisted summary contains no part of the think block, the reply replayed into the second call is cut at the answer boundary, and the answer span's budget is the declared answer budget rather than whatever the thinking left over.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Turning the thinking flag on today is not a revert and would not work.** The output schema binds the decode from the first token on both transports, so a think opener is not a legal token. Either the grammar suppresses thinking, making the flag a no-op dressed as a change, or the runtime splits the reasoning channel off and **every item fails on shape** at the unconditional refusal in `backend/idhazh/summarize.py` line 639, with a hard raise at line 391. | Andre, 2026-09-13, verified against the tree |
| 2 | The mechanism is two spans on one call: span one unconstrained with a hard thinking budget and a stop at the closing marker, span two schema-constrained on the same slot. The continuation payload exists and the prompt cache is already requested. | Andre, 2026-09-13 |
| 3 | The three hard refusals become conditional on the entry's thinking declaration in the same commit. A refusal that fires on the normal path is not a control. | Andre, 2026-09-13 |
| 4 | The thinking budget is 256 tokens, hard-capped. **Priced: 42.6 seconds an item** at the measured decode rate of 6.01 +/- 0.11 tokens a second (2026-08-23, `ubuntu-latest`, EPYC 9V74, build b10598, three repeats). Against the 900-token answer worst case of 149.8 seconds, that is **28 percent more time per item**. | Andre and Carmack, 2026-09-13 |
| 5 | Whether span two re-pays prefill on the thinking tokens **is an estimate, not a reading**. The prompt cache is requested, so the slot should hold. If it misses, the cost is an estimated 25.6 seconds an item more. The row logs the second span's evaluated-token count, which settles it, and row #5 arm 2 is the assertion that would catch a miss. | Carmack, 2026-09-13 |
| 6 | The shard size and job timeout are re-derived from the new worst-case item, never carried forward. The current timeout was sized against a 149.8-second worst case. | Carmack, 2026-09-13 |
| 7 | What proves thinking helped is the existing eleven gates on the frozen corpus, incumbent against incumbent-with-thinking. **No new instrument.** Faithfulness alone cannot see this because it rewards bland copying; entity survival, compression ratio and source overlap are the arms that move. A model judge remains banned. | Andre, 2026-09-13 |
| 8 | The markers' digest joins the run stamp in this row. It is the first row that makes the markers move, and today a marker change moves every output with nothing in the stamp saying so. The digest is already computed in `backend/utilities/measure_two_calls.py`; only the stamp lacks it. The reader-side rule is that an absent key means the run predates the knob, never a default value, proved by removing the key from a fixture. | Fowler, 2026-09-13 |
| 9 | The thinking flag retires into the refused-knob list; the entry declares the closing marker and the two budgets instead. A flag plus a marker is two places to disagree, and one budget over two spans cannot tell a long think from a cut answer. | Fowler, 2026-09-13 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Flip the thinking flag and ship it | Decision 1. It is a no-op or a total failure, and neither is a revert. | Andre |
| 2 | Ship the conditional-refusal preparation without the two-span decode | It buys no behaviour on its own and leaves three refusals weakened with nothing exercising the other branch. | Fowler |
| 3 | Let the thinking span run unbounded and stop at the closing marker alone | A model that never closes the block consumes the whole window, and the failure would be recorded as a truncated output rather than as a runaway think. | Andre |
| 4 | Keep the thinking text as evidence | It is model-written text that would then reach a reader-facing surface and the replayed prompt. Discarded before anything reads it. | Andre |

---

## What this plan does not do

| # | Left out | What is lost |
| --- | --- | --- |
| 1 | Adopt any candidate | Adoption is Level 5 and needs a qualification run and a person. This plan makes adoption cheap; it does not perform one. |
| 2 | A multi-file weights list, a vision projector, a speculative draft head | No consumer. The projector is the part not wanted, and on four cores the best conceivable speculative gain is 1.30x on model time against a runner-to-runner spread of up to 4.35x - smaller than the measurement error. |
| 3 | Non-greedy sampling | Truncating knobs are inert at greedy decoding, and the penalties move the chosen token even at greedy - a repetition penalty tuned for agent loops taxes re-using a token that already appeared, which is what a faithful summary of a technical article must do. Adopting a candidate at its recommended sampling is a Level 5 change to the determinism contract, not a knob. |
| 4 | A wider native context window | The binding constraint is the runner, not the model. The default stays conservative so a fresh entry never inherits the last model's window. Row #5 arm 5 refuses a window wider than the model was trained for. |
| 5 | A model name on any reader-facing page | A reader cannot see which model wrote a summary. The model id is on the day payload and on eval rows; the view payload deliberately omits it. It is a fact a reader cannot act on. |
| 6 | Per-item tokenization against the live server | Exact per-item token counts, at the price of a network call per shard start for numbers that move only when a prompt or the model moves. |

## See also

- [`../docs/architecture/summarize/model-boundary.md`](../docs/architecture/summarize/model-boundary.md) - the boundary this plan moves into config, and the two measurement arms.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a worker runs a row, and the no-two-rows-one-file rule.
- [`../docs/how-to/evaluate-new-summarizer-model.md`](../docs/how-to/evaluate-new-summarizer-model.md) - the page row #9 rewrites.
- [`../docs/how-to/fine-tune-a-model.md`](../docs/how-to/fine-tune-a-model.md) - the page row #9 gives a base-swap refusal.
- [`../docs/reference/measurements.md`](../docs/reference/measurements.md) - the instrument log row #7 thins, row #4 renames a rule inside, and row #13 corrects two readings in.
- [`../docs/concepts/config.md`](../docs/concepts/config.md) - the page that owns the config shape rows #2 and #6 change.
