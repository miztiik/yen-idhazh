# Model swap as a config edit, and a bench that outlives its artifact

**Last Updated**: 2026-09-14
**Level**: 5 overall (section 6). Rows #2, #6, #10 and #11 change a persisted contract. **Row #10 was signed off by the owner on 2026-09-13 and no longer pauses**; all four proceed under the ESCALATE triggers in section 0.

Execute per [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md): the orchestrator dispatches one worktree-isolated worker per row; workers consult personas on ambiguity; AUTO-merge on green gates; **parallel N = 4**; honour the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Swapping the summarizer is a source edit today, and every benchmark that would inform the choice is deleted after seven days. |
| Hard scope - in | The model's turn envelope onto its entry; one complete config file per model selected by a pointer; a start-up proof with five arms; both benchmark arms chained in one workflow emitting a paste-ready page; a per-model dossier; benchmark filenames lose their date; every tokenizer-shaped constant names its weights; the sanitizer learns the control tokens of the configured model; a runbook whose swap and revert are one line each. |
| Hard scope - out | Adopting any candidate. Layered config overrides. Per-model prompt TEXT. Vision projectors. Any new quality instrument - the eleven gates in `validate.yml` stay the only quality arm. Non-greedy sampling. Committing benchmark prose from CI. **Each carries its price and its reopening condition in "What this plan does not do"; none of them is a law** (CLAUDE.md section 0d). **A second weights file and a speculative draft head left this list on 2026-09-14** - see row 2 of that table. |
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
| 1 | Cache pressure is not a constraint on holding several candidates. `digest.yml` keys on one model per entry, `validate.yml` keys on the candidate digest, and since row #8 `measure.yml` keys its bench entry on the candidate digest too. GitHub's 10 GB total evicts least-recently-used rather than failing. A miss costs one download: 5.29 GiB in 118 s, measured 2026-08-23 on `ubuntu-latest`, `n=1`, spread unavailable. | An earlier draft said two candidates could not both be cached. Withdrawn. |
| 2 | Memory headroom is open, not spent. `peak_rss_bytes` runs 10.06 to 13.82 GiB over 193 rows of `state/runtime-counters.csv`, median 12.40, counted 2026-09-08 from runs on `ubuntu-latest`; the ledger carries no column naming the weights. Weights are mapped, so those pages are file-backed and evictable; **at most 9.02 GiB of the 14.31 GiB worst sum can be anonymous memory - an upper bound derived by subtraction, not a reading.** `cgroup_peak_bytes` is empty on all 225 rows, and nothing has ever run out. | An earlier draft refused a quantisation on an estimated peak built by adding a weights delta to one reading - the arithmetic `docs/reference/measurements.md` retracted on 2026-09-09. Withdrawn. No row refuses anything on memory; row #8 takes the reading instead. |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The runtime sweep reaches for a key that is not there | - | A | DONE | p28-r1 | #693 | owner |
| 2 | The turn envelope moves onto the model entry | - | A | DONE | p28-r2 | #692 | worker |
| 3 | Every tokenizer-shaped constant names the weights it was taken against | - | A | DONE | p28-r3 | #691 | worker |
| 4 | Benchmark records lose the date from their filename | 2, 3 | B | DONE | p28-r4 | #694 | owner |
| 5 | Five things the server proves before the first item | 2, 6 | D | DONE | p28-r5 | - | Carmack |
| 6 | One complete config file per model, selected by a pointer | 2 | C | DONE | p28-r6 | #697 | Fowler |
| 7 | The model dossier, and the index that points at every one | 3, 4 | D | DONE | p28-r7 | - | Fowler |
| 11 | Where the system text goes, and which keyword the runtime is told | 5, 6 | D | DONE | p28-r11 | - | Andre |
| 12 | The sanitizer learns the control tokens of the model it guards | 11 | E | DONE | p28-r12 | #704 | Andre |
| 13a | Ship the budget reader and its dispatch print | 3, 7 | E | DONE | p28-r13a | - | Fowler |
| 13b | Paste the three readings a dispatch takes | 13a | E | DONE | p28-r13b | #722 | worker |
| 8 | Both bench arms in one workflow, emitting a page ready to paste | 1, 6, 7 | F | DONE | p28-r8 | - | Carmack |
| 9 | The runbook: swap and revert in one line each | 6, 8, 12 | G | DONE | p28-r9 | #723 | worker |
| 10 | Two spans on one call, so the model can think | 5, 6, 11 | H | DONE | p28-r10 | #726 | Andre |

### Parallel groups, derived

Derived from the rows' own `Files touched` lists and verified pairwise on 2026-09-13. It is a hint rather than the dispatcher's input: a row is ready when its `Depends-on` are DONE and its file list is disjoint from every row in flight.

| Group | Rows | Verified disjoint |
| --- | --- | --- |
| A | 1, 2, 3 | Row #1 writes one workflow and its test. Row #2 writes the llm package, the config contract, the stamp and four test modules. Row #3 writes `measured.py`, its test and the instrument log. No pair shares a file. |
| B | 4 | Alone. It shares `backend/idhazh/classify/calls.py`, `docs/architecture/summarize/prompt.md`, `docs/architecture/summarize/throughput.md` and `docs/concepts/config.md` with row #2, and `docs/reference/measurements.md` with row #3, so it cannot run beside either. That file overlap is the whole of its `Depends-on`. |
| C | 5, 6 | Row #5 writes `server.py`, `test_summarize.py`, a new fixture directory and `digest.yml`. Row #6 writes `app_config.py`, the config files, the schemas, `config.py` and `backend/tests/contracts/`. **Corrected 2026-09-14: they are not disjoint.** Row #5's decision 2 adds a required field to `ModelRef`, which is `app_config.py`, and the value of that field has to be written into the per-model file row #6 created - so row #5 now depends on row #6 and sits alone in group D. Row #6 also wrote `test_summarize.py`, which row #5 writes. |
| D | 5, 7, 11 | Row #5 writes `server.py`, `app_config.py`, the model file, its schema and `test_summarize.py`. Row #7 is documentation only. Row #11 is the contract and the llm package - it shares `app_config.py` and `server.py` with row #5, so **those two are not disjoint and may not run together**; row #11's own `Depends-on` already names row #5. |
| E | 12, 13a | Row #12 writes `sanitize.py`, `app_config.py` and two test modules. Row #13a writes `measured.py`, `extract.py`, the two contract docstrings, a new utility, `measure.yml` and the instrument log. No shared file. Row #13b waits on #13a and on a box with weights, so it is not in this group. |
| F | 8 | Alone. It rewrites the workflow row #1 fixed and reads the shapes rows #6 and #7 created. |
| G | 9 | Alone. It shares the how-to with row #8 and `AGENTS.md` with row #4. |
| H | 10 | Alone. It is the last row and it touches most of the summarize package. |

---

### Row #1 - The runtime sweep reaches for a key that is not there

- **Scope:** The runtime-sweep job builds a candidate config by updating a key that does not exist, so the job dies at that line.
- **Files touched:**
  - `.github/workflows/measure.yml`
  - `backend/tests/workflows/`
- **Acceptance gates:** local - `python backend/utilities/gate_lock.py -- python -m pytest backend/tests/workflows/ -q`. CI - `ci.yml`. Manual post-merge proof: one dispatch of `measure.yml` with `target=runtime` and `runtime_candidate=baseline` reaching the server-start step.
- **Oracle:** `python -c "import json; json.load(open('config/idhazh.json'))['models']['summarize']['inference']"` resolves and the same expression without `summarize` raises `KeyError`. The patched line must use the path that resolves.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The correct path is `payload["models"]["summarize"]["inference"]`. Lines 367, 862 and 894 of the same file already read `["models"]["summarize"]["sha256"]`, so the file disagrees with itself. | Carmack, 2026-09-13 |
| 2 | This ships before row #8 rewrites the workflow and before row #6 moves the block again, so the fix is provably the thing that made a dispatch work. | Fowler, 2026-09-13 |
| 3 | A test is added to `backend/tests/workflows/`, which already asserts this file's dispatch inputs, job names and retention at fifteen sites. The assertion is that every config path the workflow's inline Python indexes resolves against the committed config. | Fowler, 2026-09-13 |

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
  - `backend/tests/contracts/`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_classify.py`
  - `docs/concepts/config.md`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/throughput.md`
  - `docs/architecture/summarize/model-boundary.md`
- **Acceptance gates:** local - `python backend/utilities/gate_lock.py -- ruff check backend`, `mypy backend`, the contract export followed by `git diff --exit-code -- schemas/`, and `python -m pytest backend/tests/contracts/ backend/tests/test_fingerprint.py backend/tests/test_summarize.py backend/tests/test_classify.py -q`. CI - `ci.yml` full suite and the drift gate.
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
- **Contract introduced:** `TokenizerMeasured(Measured)` with `subject: Sha256`, no default. Reworded from `Measured.subject: Sha256 | None` under decision 5 below, which ruled after the row was written.
- **Files touched:**
  - `backend/idhazh/measured.py`
  - `backend/tests/test_measured.py`
  - `docs/reference/measurements.md`
- **Acceptance gates:** local - ruff, mypy, `python -m pytest backend/tests/test_measured.py -q`. CI - `ci.yml`.
- **Oracle:** a built `TokenizerMeasured` whose `subject` is not the configured entry's `sha256` is refused, and the refusal names both digests. Driven from a built value, never from a walk over committed data.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A tokenizer reading gains a `subject` naming the weights digest it was taken against, and a gate asserts every such record's subject equals the configured entry's `sha256`. Decision 5 settled where the field lives. | Fowler, 2026-09-13 |
| 2 | `when_it_fires` on every tokenizer reading gains the model swap as a trigger. The field exists and already carries the other triggers; a record that says when to retake it and omits the largest trigger is worse than one that says nothing. **Written as the four call-one records and executed as six**: `PROMPT_OVERHEAD_TOKENS` and `WORST_TOKENS_A_WORD` are token counts too, and decision 1 says every tokenizer-derived record. Pinning four of six would have reproduced the defect inside the module that fixes it. | Fowler, 2026-09-13 |
| 3 | Timing records do not gain a subject. A second and a resident set belong to the box that took them; a token count belongs to the tokenizer. Only tokenizer-derived records are pinned. | Carmack, 2026-09-13 |
| 4 | **The gate names three sites outside `measured.py` that it cannot reach, and row #13 retakes them.** The taxonomy definition budget and the visual plan budgets were measured against the retired 8B, and the extractor's tokens-per-word ratio is tokenizer-shaped. The 8B-to-9B move already left all three behind, which is proof rather than risk. | Fowler, 2026-09-13 |
| 5 | **Two types, not a flag.** `Measured` gains nothing; `TokenizerMeasured(Measured)` adds `subject: Sha256` with no default, so a tokenizer reading that omits it fails `mypy backend` and a pin on a timing record cannot be written at all. A `reads_a_tokenizer` flag makes both bad states constructible and then owes a refusal test for each; the subclass owes none. `kw_only=True` goes on the subclass alone, so the base class and all eight existing call sites are untouched. | Fowler, 2026-09-13 |
| 6 | **A module constant in `measured.py` holds the three sites the gate cannot reach - module path and constant name for each - and both readers get it: the gate docstring cites the constant and the refusal text appends it, with row #13 named on the declaring line as the removal condition.** This gate has one trigger, the configured weights digest no longer matching a pinned reading, and that same swap is what makes all three stale, so they are the rest of the same failure rather than noise on an unrelated one. The person swapping a model is reading `config/idhazh.json` and the failing gate, not `measured.py`, and the refusal is the one moment they are provably looking. | Fowler, 2026-09-13 |
| 7 | **The gate is a module-level function taking the expected digest and the records as arguments.** It reads no config and opens no file - `contracts/` is the bottom of the dependency graph and cannot import `idhazh.measured`, so an `AppConfig` validator is not available, and injection is what makes the refusal arm drivable from a built record. No `SHA256_PATTERN` check on `subject`: the equality gate already refuses a malformed digest, and a second check that can only fire when the first would is decoration. | Fowler, 2026-09-13 |

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
- **Acceptance gates:** local - `python backend/utilities/doc_load.py` before and after, and the two greps in the Oracle. CI - `ci.yml` and the link check.
- **Oracle:** from the repository root, `git grep -nE '\]\([^)]*benchmarks/2026-'` returns zero lines - no markdown link points at a dated benchmark path. `git grep -n 'benchmarks/2026-'` returns exactly 8 lines, all of them inside the rename mapping in `TODO/20260913-28-model-swap-plan.md`. Any other count fails the row. Every renamed file is reachable from at least one inbound link.

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
| 9 | **The oracle is the link form, not bare text.** The stated oracle - zero matches for `benchmarks/2026-` anywhere - cannot pass, because this row's own rename mapping quotes the old names and that mapping is the record of what was renamed. Measured on main before the row ran: 32 bare-text matches across 11 files, 17 link-form matches across 8. The mapping is written with backticks and an arrow, so it drops out of the link form entirely. A first ruling for whole-tree link resolution in `doc_load.py` was overturned: it answers a larger question and drags pre-existing breakage into a row that did not cause it. **Accepted gap:** a link repointed to a wrong NEW spelling carries no `benchmarks/2026-` and neither grep sees it; that is a follow-up row that pays off every broken link at once. | Fowler, 2026-09-14, after a measurement |
| 10 | **Decision 7's `measurements.md` half was wrong and is corrected here.** Cutting at `the date it` left `and it was taken` stranded, which is not English (section 0b). The replacement consumes the whole clause: `named for what it measured and the date it was taken.` -> `named for what it measured and nothing else - a re-run replaces that record rather than adding a second one.` It says `record` rather than `page` because the sentence has already named the artefact a record. The `AGENTS.md` half of Decision 7 stands unchanged. | Fowler, 2026-09-14 |
| 11 | **Three files the list omitted were touched, and all three are the same defect.** `docs/reference/benchmarks/instructions-in-front.md`, `two-call-re-read.md` and `two-call-window-sizing.md` cross-link each other by the dated name, so the records pointed at each other's old paths. The six records also each carried `Frozen. This is one run on one day ... A later run gets its own record`, which Decision 3 makes false in both halves; every one of them now states the Living class instead. Leaving them would keep the retired convention alive in the six pages that demonstrate it. | Fowler, 2026-09-14 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Keep the date and add an alias page | Two names for one page, and the alias is the one search finds. | Fowler |
| 2 | Rename only files created from now on | The directory carries two conventions, and the rule deciding which to use is the file's own age. | Fowler |

---

### Row #5 - Five things the server proves before the first item

- **Scope:** A start-up probe proves the entry against the running server on five axes and refuses the run on any disagreement.
- **Files touched:**
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/contracts/app_config.py`
  - `config/models/qwen3.5-9b-q4km.json`
  - `schemas/models-config.schema.json`
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
| 2 | `ModelRef` gains `arch: str`, required, carrying the GGUF architecture string. The field is declared in `backend/idhazh/contracts/app_config.py`; its value is written into the per-model file `config/models/qwen3.5-9b-q4km.json` that row #6 created. `config/idhazh.json` carries the pointer only and is not touched. Adding a required field to a shipped contract stamps `ModelsConfig.version` and appends a `changelog` entry in the same commit (CLAUDE.md section 11). | Carmack, 2026-09-13, ordering corrected by Fowler, 2026-09-14 |
| 3 | Every arm is driven in tests by a recorded response. No test touches the network. **Amended 2026-09-14: the two fixtures are CONSTRUCTED from llama.cpp's documented API shape, not captured.** `backend/models/` does not exist on the machine that wrote them, so a capture needed a multi-gigabyte download. Both declare it in their first three fields - `recorded: false`, `why_not_recorded`, `how_to_record` - and a loader refuses any file under `tests/fixtures/llm/` that omits them or that says it was not captured without saying how, because written honesty decays and a loader that fails does not. This is not Guardrail #7's named-mock exception: a mock makes an assertion pass by pretending, and no arm's pass depends on an invented value - arm 1's rule is positional, arm 5 reads a measured number and a committed declaration, arm 4 builds a real GGUF header. What the tests establish is the comparison rules and the config-derived prompt. **Tokenizer agreement is proved solely by the live probe on a box with weights**, which runs every run rather than once, and that sentence is on the comparator and in the fixture. Re-recording is attached to a trigger, not a date: the first run on a box where `backend/models/` exists replaces both files. | Fowler, 2026-09-13; amended by Fowler and Andre, converging, 2026-09-14 |
| 4 | No arm gains a flag to skip it. The proof is what paid for moving the envelope out of the package; a skip returns the tree to worse-summaries-and-no-error with extra ceremony. | Fowler, 2026-09-13 |
| 5 | The template endpoint is already named in `backend/utilities/measure_two_calls.py`, which is one of two sites in the tree that mention it. That file's caution is against using it to tokenize a prompt the server was never sent - a different use from reconciling a render. | Carmack, 2026-09-13 |
| 6 | Arm 2 protects the incumbent today, before any swap, and is the cheapest item in this plan. | Carmack, 2026-09-13 |
| 7 | Row #6's identity-branch test is already in force, so the probe compares nothing whose operand is a model id, repo or filename. Every arm reads what it compares off the entry or off the server. | Fowler, 2026-09-14 |
| 8 | The field is declared on `ModelEntry`, not on `ModelRef`. Decision 2 named `ModelRef`, and `run_manifest.ModelUse` embeds that shape - so a required field there would stop this build reading every `run.json` already committed (CLAUDE.md section 11). The field name, the value, the file it is written into and the version stamp are exactly as decision 2 wrote them; only the class moved, and it moved to the one `turns` moved to for the same reason. | Carmack, 2026-09-14 |
| 9 | Arm 4 reads the architecture out of the weights file, not off the server. Decision 2 and the arm table both assumed llama-server reports it. It does not, on any build: `get_res_props` publishes the path, the alias, the file type, the modalities, the template, the tokens, the build and the window, and `get_res_model_info` adds the vocabulary, the embedding width, the parameter count, the size, the file type and the trained length. Neither carries `general.architecture`, and the recorded `/props` reading in `docs/reference/measurements.md` (build b10444, 2026-09-09) lists the same set. So the probe reads that key off the front of the weights file the server was pointed at - a few kilobytes, not a cost that follows the model - which sits beside the `/props` filename assertion `digest.yml` already makes exactly as the arm table asks: the filename says which file, the header says what that file is. | Carmack, 2026-09-14 |
| 10 | Arm 5 reads the trained length from `/v1/models`, which is the only route that publishes it. `props-probe.json` keeps the name this row gave it and holds that document, and says inside itself why. | Carmack, 2026-09-14 |
| 11 | `schemas/app-config.schema.json` did not move. Row #6 took the model block out of `AppConfig`, so the new field reaches `schemas/models-config.schema.json` alone. The export was run and the drift gate is clean. | Carmack, 2026-09-14 |

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
  - `backend/tests/contracts/`
  - `docs/concepts/config.md`
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:** local - ruff, mypy, the contract export followed by `git diff --exit-code -- schemas/`, `python -m pytest backend/tests/contracts/ -q`. CI - `ci.yml` full suite and the drift gate.
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
| 10 | The per-model file is digested with the rest of `config/` and travels with the run. Decision 4 rules that the **run stamp** is unaffected and says nothing about `ConfigDigest`; a record that held only the pointer file could not tell a swap from a re-tuning of the file the pointer names. `Settings.digests` therefore carries `config/<models_file>` beside `config/idhazh.json`. | Fowler, 2026-09-14 |

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
| 7 | **The move set is decision 2's list and nothing else.** A quantity decision 2 does not name has no slot on the dossier, so moving it would delete a reading rather than relocate it, and the oracle requires every moved quantity to appear once - on the dossier. Decision 3's "that is most of its length" is a prediction of the effect, not a licence to cut readings with nowhere to go: the log lost 43 lines of 2,178. | Fowler, 2026-09-14 |
| 8 | **The discriminator is whether a quantity is a property of the model or a property of a setting measured while that model ran.** Identity, throughput, memory marks, load time, seconds an item and the verdict are the model's, and they move. The window, cap and shard-timeout pricings measure a config knob and stay, because the instrument log's own rule is that it holds the reading and never the decision. | Fowler, 2026-09-14 |
| 9 | **Only the configured model's readings move.** The retired Qwen3-8B-Q4_K_M, the retired Qwen3-4B-Q4_K_M visual planner and the offline faithfulness scorer have no dossier, so their figures stay in the instrument log labelled as theirs. The index carries the rule that would bring one of them here. | Fowler, 2026-09-14 |
| 10 | **The dossier carries the qualification verdict; the log keeps what one gate taught about the instrument.** The `injection_canaries` failure was a false security finding, and its correction is a Guardrail #10 lesson about a measuring instrument rather than a reading of the weights. Three inbound links already point at that subsection. | Fowler, 2026-09-14 |
| 11 | **Every heading stays and only its body becomes a pointer.** Five inbound anchors from `docs/concepts/evaluation.md`, `docs/archive/measurements-2026-08.md` and the log itself resolve to the two headings whose bodies moved, and those pages are outside this row's file list. | Fowler, 2026-09-14 |
| 12 | **A figure that is a term of the log's own argument stays there at the same value.** The weight byte count remains in the cache-transition sum and in the mapped-memory argument, and 14.31 GiB remains in a section title and in the retraction that needs it. A term of an arithmetic is not a second answer to the quantity, and splitting evidence from the claim it refutes makes the claim unreviewable. | Fowler, 2026-09-14 |

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
  - `backend/tests/contracts/`
  - `backend/tests/test_summarize.py`
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/model-boundary.md`
- **Acceptance gates:** local - ruff, mypy, contract export plus `git diff --exit-code -- schemas/`, `python -m pytest backend/tests/contracts/ backend/tests/test_summarize.py -q`. CI - `ci.yml` full suite and the drift gate.
- **Oracle:** two arms. Under `own_turn` the rendered prompt is byte-identical to the incumbent's. Under a built `fold_into_first_user` entry the rendered bytes differ **while `prompt_sha256` is unchanged** - which is the envelope-and-content split of section 0.2 stated as a test.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `system_role` is a closed enum read by `render_prompt`, which never reads a model id. Without it a model with no system role cannot be configured at all, which defeats the plan's intent. | Andre, 2026-09-13 |
| 2 | `system_joiner` is required under `fold_into_first_user` and refused under `own_turn`. A dead field is a field somebody will trust. | Fowler, 2026-09-13 |
| 3 | `thinking_kwarg` defaults to the incumbent's keyword. Null means send no template keywords at all **and** forces the entry to declare no `turns.thinking_close`, enforced by a cross-field validator. Null with reasoning asked for claims a channel no template carries, and the reasoning refusal then fails every item on shape. **Row #10 moved that validator onto `TurnsConfig` and repointed it at `thinking_close`**, which retired `inference.thinking`; both halves of the pair are facts about one template, so one block owns it. | Andre, 2026-09-13, amended 2026-09-14 |
| 4 | The keyword name is a model fact, not a project constant. It is spelled in this project's source today and sent to every model. | Fowler, 2026-09-13 |
| 5 | Prompt **text** does not move, and section 0.2 rule 2 is the reason, restated in the row that introduces the envelope: `prose_changed_alone` returns nothing whenever `model_sha256` moved, so a prompt edit made because the new model needed it would be hidden inside the swap forever. | Andre, 2026-09-13 |
| 6 | The two fold strategies are two code paths selected by an enum. A turn topology cannot be a string without inventing a template language, and a template language in config is a second renderer nobody tests. | Fowler, 2026-09-13 |
| 7 | **The three fields sit on `TurnsConfig`, which `ModelEntry` carries and `ModelRef` does not.** The row's contract line said `ModelRef.turns`; row #2 put `turns` on the entry precisely so a `run.json` written earlier still reads, and following the line as written would have undone that. | Fowler, 2026-09-14 |
| 8 | **`system_role` is a named `StrEnum`, `SystemPlacement`, rather than an inline `Literal`.** Same two wire values, same closed `enum` in the generated schema. Decision 6 rules the two strategies are two code paths, and a named type is what gives that branch somewhere to say so. | Andre, 2026-09-14 |
| 9 | **All three carry defaults** - `own_turn`, null and `enable_thinking` - where the four markers beside them have none. Required is the consistent choice and the stop condition refuses it: `tests/fixtures/planner/recorded-call-payloads.json` carries a `turns` block and may not change in this row, so a required field would have failed the byte-identity oracle on a validation error rather than on a byte. It is safe on its own terms too - `own_turn` is the topology of every template that HAS a system role, not the incumbent's own string, and arm 1 of `prove_the_entry` refuses a placement declared wrong before the first item. | Andre, 2026-09-14 |
| 10 | **`system_joiner` may not be empty.** Required under the fold means present and non-empty, one rule: a joiner of `""` renders the last instruction and the opening fence of the untrusted block on one line, which is the silent failure the field exists to prevent. | Fowler, 2026-09-14 |
| 11 | **The keyword is a required keyword-only argument of `request_payload` and `summarize.build_request`, with no default.** A default in either signature is the project constant decision 4 retires. It widens the row's file list by five: `backend/idhazh/summarize.py`, `backend/idhazh/stages/common.py`, `backend/idhazh/stages/validate.py`, `backend/utilities/prompt_loop.py` and `backend/tests/test_corpus_harvest.py`. `schemas/app-config.schema.json` is in the list and did not move - row #6 took the models block out of `AppConfig`, so only `schemas/models-config.schema.json` regenerates. | Fowler, 2026-09-14 |
| 12 | **The stamp's closed world widens from two shapes to three.** `fingerprint.MODEL_FIELD_SPELLING` named `turns` and answered for the block rather than for anything inside it, so all three of these could have landed in no stamp and in no closed set. `system_role` and `system_joiner` join the four markers under `prompt_sha256`; `thinking_kwarg` is undigested, because the run's two calls render their own prompt bytes and send no template keywords at all, and whether reasoning was asked for is already recorded in `sampling`. | Fowler, 2026-09-14 |
| 13 | **Arm 2 of the oracle does not read the way the row wrote it, and the row's expectation was already out of date when it was written.** Row #2 made `classify.calls.prompt_inputs` render both turns through the envelope, so the digest run's `prompt_sha256` DOES move on a fold - 28 bytes shorter, and the stamp goes `0f083606...` to `decc300e...`. What stays blind is the qualification run: `stages/qualify.py` hands `build_inputs` the content-only digest from `summarize.prompt_inputs`, so its stamp carries no turn marker at all. The eleven gates are what adopt a model, so that is the surviving reason the envelope is declared on the entry and proved against the server at start-up rather than inferred from a digest. The test asserts both halves. | Andre, 2026-09-14 |
| 14 | **Correction: row #6's identity-branch test DOES exist and this row proved it bites.** A search during this row's execution missed it and reported ESCALATE trigger 2 as having no test behind it. It is `test_no_module_that_opens_a_model_branches_on_which_model_it_is` in `backend/tests/test_summarize.py`, and it is stronger than the row asked for: the identities come from the committed model file AND from shape - `.gguf`, an `owner/NAME-GGUF` repository, the names `Qwen`, `unsloth`, `bartowski`, `TheBloke` - so it fails on a fork written for weights that are not on disk yet. Two-arm proof taken 2026-09-14: clean tree exit 0; with `turns.turn_opening == "qwen3-5-9b-q4-k-m"` planted in `backend/idhazh/llm/server.py` it exits 1 with `backend/idhazh/llm/server.py:204 compares against 'qwen3-5-9b-q4-k-m'`; restored, exit 0. | Andre, 2026-09-14, correcting this row's own report |e digest run's `prompt_sha256` DOES move under a fold - measured 2026-09-14 on the committed entry: the same two turns render 28 bytes shorter and the digest changes. The stamp that is still blind is the qualification run's: `stages/qualify.py` hands `build_inputs` the content-only digest from `summarize.prompt_inputs`, which carries no turn marker at all. The test asserts both halves, because the eleven gates are what adopt a model and they compare candidates through the blind one. | Andre, 2026-09-14 |

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
| 5 | **The refusal lives in `idhazh.config.load`, and the question it asks lives in `idhazh.sanitize`.** It cannot be a validator on `TurnsConfig`: `backend/idhazh/contracts/` is the bottom of the dependency graph and may import no other subpackage (`CLAUDE.md` section 4), so a contract cannot ask the sanitizer anything. `config.load` is the one place every run reads `config/` and it already refuses a models file for a shape the contract caught. The module that owns the pattern owns the question about it - `why_a_forged_turn_would_survive` takes one string and knows nothing about config. | Andre, 2026-09-14 |
| 6 | **The refusal asks two questions, not one.** Is the marker recognised by the pattern at all, and is anything structural left after sanitizing it. Either alone passes a marker the boundary cannot hold: the second alone passes `USER: `, which has no delimiter to leave behind; the first alone passes `[system]<\|im_start\|>$role`, where the pipe-delimited half goes and the bracket stays. | Andre, 2026-09-14 |
| 7 | **A model whose turn boundary is ordinary words is refused, not widened toward.** `USER: ` is a real turn opening on a real family. A pattern wide enough to strip it would strip a line of dialogue out of an article, so the answer is that the model is not a candidate - said at load, rather than discovered from a summary that obeyed a page. | Andre, 2026-09-14 |
| 8 | **The fence removal moved ahead of the chat-control pass.** The new bare-angle-token family matches `<UNTRUSTED_SOURCE_TEXT>` inside `<<<UNTRUSTED_SOURCE_TEXT>>>`, which would have taken the word out of the middle of the fence marker and left `<< >>` standing where a whole marker used to be. Removed first, there is nothing left to half-match. Both orders are idempotent and neither lets text close the fence; the new one leaves no debris. | Andre, 2026-09-14 |
| 9 | **The widening is load-bearing for the incumbent, not a precaution.** `models.summarize.turns.reply_opening` is `<\|im_start\|>assistant\n<think>\n\n</think>\n\n`, and the old pattern knew neither `<think>` nor `</think>` because neither is pipe-delimited. The committed entry would have been refused by this row's own load-time check under the old pattern. `test_the_incumbents_own_reply_opening_is_what_needed_the_widening` pins that. | Andre, 2026-09-14 |
| 10 | **The new families went into a built table in `backend/tests/test_canaries.py`, not into the `fake-system-delimiter` fixture.** That fixture is the one `test_a_canary_is_sized_by_the_words_that_survive_the_boundary` uses to straddle the brief threshold, and it does so with two words of slack: planting five more forged turns in it took the surviving word count from 58 to 80 and failed that test for a reason this row is not about. `CLAUDE.md` section 13 asks for the awkward case to be BUILT anyway, and a table naming one family per row is the more legible artefact. | Andre, 2026-09-14 |
| 11 | **`docs/architecture/sources/trust-boundary.md` was edited though the row's file list did not name it.** It is the canonical page for the sanitizer (`CLAUDE.md` section 5, one concept defined once) and its control table named three families by example, so leaving it would have kept the retired claim alive on the page a reader goes to first. `model-boundary.md` now links to it rather than restating it. | Andre, 2026-09-14 |
| 12 | **The pattern's per-model row in `model-boundary.md` moved from Envelope to Content.** The row read "Which control tokens the sanitizer strips - Envelope, per model". That is the rejected option 1 written into a table: the threat is a forged turn in whatever syntax the attacker picks, so the pattern is global. What is per model is the refusal. | Andre, 2026-09-14 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Derive the pattern from the entry's markers alone | The threat is forged turns from any family, not only the configured one. A reader is not protected by a filter that only knows the model in use today. | Andre |
| 2 | Leave the pattern as it is and note the limitation | A limitation named with no next move is an unfinished answer (section 0d), and this one is a reader-safety boundary. | Andre |

---

### Row #13a - Ship the budget reader and its dispatch print

- **Scope:** The three constants a vocabulary sizes get a record each in `idhazh.measured`, carrying the value in force today and the weights it was taken against, so row #3's gate can read every subject. A reader retakes all three from a running server's own `/tokenize`, a dispatch target prints them paste-ready, and an operator command says which are stale. **No number moves.**
- **Files touched:**
  - `backend/idhazh/measured.py`
  - `backend/idhazh/extract.py`
  - `backend/idhazh/contracts/taxonomy.py`
  - `backend/idhazh/contracts/visual.py`
  - `backend/utilities/measure_budgets.py`
  - `.github/workflows/measure.yml`
  - `backend/tests/test_measure_budgets.py`
  - `backend/tests/test_measured.py`
  - `backend/tests/workflows/`
  - `backend/tests/test_marks.py`
  - `tests/fixtures/llm/budget-probe.json`
  - `docs/reference/measurements.md`
- **Acceptance gates:** local - ruff, mypy, `python -m idhazh.contracts.export` with no drift, `python -m pytest backend/tests/test_measured.py backend/tests/test_measure_budgets.py backend/tests/workflows/ -q`, then the full backend suite. CI - `ci.yml`.
- **Oracle:** `python backend/utilities/measure_budgets.py check` names all three constants, prints the retired digest beside the configured one, and exits 1. Every value at its site is byte-identical to what it was before this row.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Both budgets were measured against the retired 8B, which is not the incumbent. The 8B-to-9B move left them behind, so this is a correction rather than a precaution. | Fowler, 2026-09-13 |
| 2 | The numbers are taken by asking the runtime's own tokenizer, not by reasoning about a vocabulary. The tokenizer is the model's and it moves when the model does. | Carmack, 2026-09-13 |
| 3 | **Row #13 splits.** The reader ships now; the three readings land when a box with weights runs it. Rejected option 1's load-bearing clause was *writing a measurement into a commit*, and printing is not writing - a dispatch that prints a paste-ready block decides nothing, because a person still edits the file. So the machinery is not blocked on the measurement. | Carmack and Fowler, converging, 2026-09-14 |
| 4 | **The staleness check ships with #13a, not with #13b.** Shipped with #13b it would police only itself. Shipped here, the risk that #13b never runs is loud rather than silent: every reading's `subject` names the retired weights and two surfaces say so. | Fowler, 2026-09-14 |
| 5 | **The three records live in `idhazh.measured`, not in `config/`.** All three sites are import-time values - two are in `contracts/`, which may import no other subpackage (`CLAUDE.md` section 4), and `TOKENS_PER_WORD` is read by an import-time assertion in `classify.calls` - so a config edit could stop an import rather than change a behaviour. `measured.py` already says why: a reading's subject is a historical fact and a literal for that reason (Guardrail #6). | Fowler, 2026-09-14 |
| 6 | **The check is an operator command that exits 1, not a test.** All three are stale on every commit until #13b lands, and a test that is red on a state nobody has fixed is a test people learn to scroll past (`CLAUDE.md` section 13). It also rides on row #3's refusal, which fires at the one moment a person is provably looking at weights. | Fowler, 2026-09-14 |
| 7 | **`budgets` is its own dispatch target, not a step on the bench.** Retaking three token counts is minutes; the bench is hours. It shares the bench's weights cache key, so the bytes are paid for once. | Carmack, 2026-09-14 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Re-measure these in CI on every swap | A workflow would be writing a measurement into a commit, which this tree reserves for people. The gate names the number as wrong; a person takes the reading. | Carmack |
| 2 | Move the three constants into `config/` | The substitution test cannot be met where the value is consumed at import: `config/` would then be able to raise an `ImportError`, and `schemas/taxonomy.schema.json` would become a function of `config/idhazh.json`. Decision 5 is the placement that survives it. | Fowler, 2026-09-14 |

---

### Row #13b - Paste the three readings a dispatch takes

- **Scope:** A box with the configured weights runs the `budgets` dispatch, and a person pastes the three values, subjects and dates into `idhazh.measured`. Any constant whose derivation moves with its reading moves in the same commit, with the schema stamped and changelogged where it is a persisted bound.
- **Files touched:**
  - `backend/idhazh/measured.py`
  - `backend/idhazh/contracts/taxonomy.py` (only if the definition bound moves)
  - `backend/idhazh/contracts/visual.py` (only if the plan ceiling moves)
  - `docs/reference/measurements.md`
- **Acceptance gates:** local - ruff, mypy, `python backend/utilities/measure_budgets.py check` exits 0, `python -m pytest backend/tests/test_measured.py backend/tests/test_measure_budgets.py backend/tests/contracts/ -q`. CI - `ci.yml`.
- **Oracle:** each constant carries its number, its `subject` equals the configured weights' digest, and **the retired-vocabulary reading is deleted rather than kept beside the new one** (row #13's Decision 3, Guardrail #10).
- **How to take it:** dispatch `.github/workflows/measure.yml` with `target: budgets`. The run summary carries the paste block. Or, on any box with weights: start `llama-server` on the configured model, then `python backend/utilities/measure_budgets.py read --runner <where you ran it>`.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A number whose retake changes it gets its old reading deleted, not kept beside the new one. A reading is a variable; git history holds what it used to say. | Fowler, 2026-09-13 |

---

### Row #8 - Both bench arms in one workflow, emitting a page ready to paste

- **Scope:** The benchmark runs raw throughput and a real server with real work as two chained jobs over one candidate, and emits the dossier body already filled in.
- **Files touched:**
  - `.github/workflows/measure.yml`
  - `.github/scripts/start-llama-server.sh`
  - `backend/utilities/measure_llm.py`
  - `backend/tests/test_measure_llm.py`
  - `backend/tests/workflows/`
  - `docs/how-to/evaluate-new-summarizer-model.md`
- **Acceptance gates:** local - ruff, mypy, `python -m pytest backend/tests/test_measure_llm.py backend/tests/workflows/ -q`. CI - `ci.yml`. Manual post-merge proof: one real dispatch against the incumbent's own digest.
- **Oracle:** dispatched against the incumbent, the emitted dossier reproduces the committed dossier's readings within their stated spread. A bench that cannot reproduce the model it was calibrated on is measuring something else.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One workflow, two jobs chained by dependency: raw throughput first, then a real server running real work. One candidate slug is typed once, and job two restores job one's weights cache instead of repeating the 118-second download. | Carmack, 2026-09-13 |
| 2 | Two jobs, not one. One job puts both arms under a single six-hour ceiling and loses per-arm restart. | Carmack, 2026-09-13 |
| 3 | The candidate is a repository reference at an immutable commit plus file and expected digest, materialized into the gitignored candidate directory. Empty means today's behaviour. **A candidate is therefore benchmarked without touching the committed config at all.** | Carmack, 2026-09-13 |
| 4 | Raw throughput alone is not enough. It never starts a server, so it yields no seconds per item and no resident set. The project's own how-to already concedes that raw fit is not production fit. | Carmack, 2026-09-13 |
| 5 | Artifact retention rises from seven days to ninety. Seven days is shorter than the gap between benchmarking and deciding, and the emitted files are kilobytes against a 500 MB ceiling. `backend/tests/workflows/` asserts the current value and moves with it. | Carmack, 2026-09-13 |
| 6 | The workflow never writes the committed config, never publishes, and never scores quality. A bench that can score becomes the selector, and a bench that can adopt is an adoption path with no gates in it. | Andre, 2026-09-13 |
| 7 | Qualification is not chained to this. The bench is cheap and answers whether a model fits; qualification is expensive and answers whether it is good. Chaining spends the expensive one on candidates already dead. | Carmack, 2026-09-13 |
| 8 | The resident-set arm records rather than gates, and names the measurement that would settle headroom: the split between anonymous and file-backed pages, taken by the same sampler on the runner. Memory refuses nothing in this plan. | Carmack, 2026-09-13 |
| 9 | **The bench reports a cold arm as well as a warm one.** The first day after a swap is all-cold on every shard at once - the cache key carries the filename and revision - so a warm-box reading is not the first real day. One cold model-load and one cold weights-fetch figure, labelled as such. | Carmack, 2026-09-13 |
| 10 | The artifact is the page body, not JSON to reformat: numbers filled, hardware, build and spread inline, `Last Updated` set. Transcription is a copy. | Fowler, 2026-09-13 |
| 11 | **Decision 5's premise was wrong and the work is an addition, not a move.** No retention assertion for `measure.yml` existed to move: the only one in `backend/tests/` is `retention-days > 0` on `digest.yml`'s review tree. The raw arm declared no retention at all, so it was on the platform default. Both arms now declare ninety and a new test pins the number. | Carmack, 2026-09-14 |
| 12 | **The two arms keep the job names `llm` and `runtime`.** They are the raw arm and the server arm, and renaming them would have rewritten six closed-world entries in `backend/tests/workflows/` plus four pages, one of them an archive record of what the `runtime` job measured in August. The target is what changed: `llm` and `runtime` are gone as dispatch values and `bench` runs both jobs, so the harness lost a path rather than gaining one. | Carmack, 2026-09-14 |
| 13 | **The 95th-percentile row is not on the emitted page.** Five articles cannot carry one, and printing a quantile over five samples is inventing precision (Guardrail #10). The page says so and names what would give the number: the published ledger over a real day. | Carmack, 2026-09-14 |

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
| 3 | The qualification dispatch takes one argument, the model filename, replacing the several candidate arguments it takes today. **Built 2026-09-14.** `validate.yml` and `measure.yml` each take `candidate_models_file` and nothing else about the candidate; the scratch config each builds now differs from the committed tree in the `models_file` line alone, instead of rebuilding the entry field by field and transplanting the incumbent's `inference` and `turns` blocks with their digests overwritten. `ModelRef` gained an optional `byte_count` so the last fact had a home - its old default of 0 made the identity gate compare the observed size to itself. | Carmack, 2026-09-13 |
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
  - `backend/idhazh/stages/common.py` (**not named by the row**: it holds `_ask_the_model`, which both rendered calls go through, so the two-span dispatch belongs there and nowhere else)
  - `backend/idhazh/stages/work.py`, `backend/idhazh/stages/validate.py`, `backend/idhazh/stages/qualify_decide.py` (**not named**: they hand the envelope to the call, the stamp and the gate)
  - `backend/idhazh/contracts/qualification.py` (**not named**: a shard and a report embed `PipelineInputs`, so both schemas moved and both owed a changelog entry)
  - `backend/utilities/prompt_loop.py`, `backend/utilities/measure_two_calls.py`, `backend/utilities/measure_ledgers.py` (**not named**: three readers of the retired budget or the retired flag)
  - `config/models/qwen3.5-9b-q4km.json`
  - `schemas/app-config.schema.json`
  - `schemas/models-config.schema.json`
  - `schemas/run-manifest.schema.json`
  - `tests/fixtures/contracts/models-config/every-knob-differs-from-the-committed-config.json`
  - `backend/tests/contracts/`
  - `backend/tests/test_summarize.py`
  - `backend/tests/test_classify.py`
  - `backend/tests/test_fingerprint.py`
  - `backend/tests/test_qualify.py`
  - `backend/tests/contracts/`, `backend/tests/pipeline/`, `backend/tests/workflows/`
  - `.github/workflows/digest.yml` (**unchanged**: the job reads `run.shard_timeout_minutes` from config, and the re-derivation landed on the number already there)
  - `docs/architecture/summarize/prompt.md`
  - `docs/architecture/summarize/throughput.md`
  - `docs/architecture/contracts/determinism.md`
  - `docs/concepts/config.md`, `docs/how-to/test-models-locally.md`, `docs/how-to/troubleshoot-one-url.md`, `docs/reference/measurements.md` (**not named**: four live pages telling a reader to turn a knob that was renamed)
  - `tests/fixtures/contracts/run-manifest/two-runs.json`, `tests/fixtures/planner/recorded-call-payloads.json` (**not named**: the first is the round-trip payload, the second declares the inputs the frozen prompts were rendered from. **Neither rendered prompt moved**: `call-one.txt` is `2c5f832c...` and `call-two.txt` is `e9119752...` before and after, and the recorded request bodies are byte-identical)
- **Acceptance gates:** local - ruff, mypy, contract export plus schema diff, `python -m pytest backend/tests/contracts/ backend/tests/pipeline/ backend/tests/workflows/ backend/tests/test_summarize.py backend/tests/test_classify.py backend/tests/test_fingerprint.py backend/tests/test_qualify.py -q`. CI - `ci.yml` full suite. **Adoption gate: a qualification run comparing the incumbent against the incumbent-with-thinking on the same frozen corpus, same build, interleaved repeats.**
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
| 10 | **`InferenceConfig` is two shapes at once, and the refusal could not sit on it.** `ModelsConfig` reaches the block through `ModelEntry` - a file a person edits - and `run_manifest.ModelUse` reaches the same block through `ModelRef`, which is a payload yesterday's run wrote. A refusal on the block itself made today's build unable to read every committed `run.json`, which is a release blocker (section 11). So the refusal moved onto `ModelEntry` and the recorded shape gets a read-side migration instead: `max_output_tokens` is renamed to `max_answer_tokens`, carrying the number across because the old key sized one call's answer and so does the new one, and `thinking` is dropped because `ModelRef` carries no envelope and every run written under the flag wrote it false. A payload carrying both spellings is refused rather than guessed at, which is what stops the migration turning `extra=forbid` into `extra=ignore`. | Fowler, 2026-09-14 |
| 11 | **The refusal message names the successor in full, so `refuse_a_removed_knob` gained one rule.** A replacement carrying a dot is already a whole path and is printed as it stands. `models.<role>.inference.thinking` moved block rather than name, and an operator sent to `models.<role>.inference.turns.thinking_close` is sent to a key that does not exist. `SUPERSEDED_MODELS_NAMES["inference"]` becomes the full `models.<role>.inference` under the same rule and renders the same sentence it always did. | Fowler, 2026-09-14 |
| 12 | **The chat route sends one span and the runtime owns the split.** Two spans need a prompt of ours to stop at a marker and continue under a grammar, and the chat route has none - the model's own template wrote those bytes. So `request_payload` sends `max_answer_tokens + max_think_tokens` where the envelope thinks, and the qualification harness runs that route. It is not a second mechanism: the same declaration drives both, and the three conditional refusals are what let the chat route's own reasoning channel through. | Andre, 2026-09-14 |
| 13 | **`request_payload` and `summarize.build_request` take the whole envelope rather than `thinking_kwarg`.** The keyword and the declaration are both facts about one template, and handing over one while reading the other off somewhere else is the two-places-to-disagree defect Decision 9 names, one layer down. It also moved `_a_template_that_reads_no_keyword_cannot_be_asked_to_think` from `ModelEntry` onto `TurnsConfig`, where both halves of the pair now live. | Andre, 2026-09-14 |
| 14 | **The markers' digest covers the whole envelope, not the four strings `measure_two_calls.py` concatenated.** `thinking_close`, `system_role` and `system_joiner` joined it, because the row that makes markers move is the row that makes the closing marker matter. `server.turn_markers_digest` is the one place it is computed and both readers take it from there; a second rendering is a second answer. `thinking_kwarg` stays out for the reason `NOT_DIGESTED` already gives - no published word is decoded under it. | Fowler, 2026-09-14 |
| 15 | **The shard bound and the shard size were re-derived and both land on the number they already held.** The worst of 80 shard rows on 2026-09-02 used 135.4 minutes carrying 40 items, so the worst measured item is 203.1 s; a worker now draws 20, and two thinking spans add 85.2 s, so the derived worst item is 288.3 s and the derived worst shard is 96.1 minutes against a 200-minute bound. `shard_size` would have to rise above 20 to move the fan-out at all. Both descriptions now carry the derivation rather than the one they were set under, which is what stops this being "carried forward". | Carmack, 2026-09-14 |
| 16 | **The measured cost per item does not trip ESCALATE trigger 1.** One span is 42.6 s against the 149.8 s answer worst case, which is 28.4 percent - the figure the row priced. The item-level add is two spans because the digest makes two calls, and that is 85.2 s against a 203.1 s measured worst item, or 42 percent of the item - but the trigger is worded against the per-call figure the row itself derived, and the derived worst shard clears its bound with 2.1 times over. Reported rather than treated as a pause. | Carmack and Andre, 2026-09-14 |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Flip the thinking flag and ship it | Decision 1. It is a no-op or a total failure, and neither is a revert. | Andre |
| 2 | Ship the conditional-refusal preparation without the two-span decode | It buys no behaviour on its own and leaves three refusals weakened with nothing exercising the other branch. | Fowler |
| 3 | Let the thinking span run unbounded and stop at the closing marker alone | A model that never closes the block consumes the whole window, and the failure would be recorded as a truncated output rather than as a runaway think. | Andre |
| 4 | Keep the thinking text as evidence | It is model-written text that would then reach a reader-facing surface and the replayed prompt. Discarded before anything reads it. | Andre |

---

## What this plan does not do

Every row names what leaving it out costs and what would bring it in. A line with no price is a law nobody voted for ([../docs/how-to/author-a-plan.md](../docs/how-to/author-a-plan.md), CLAUDE.md section 0d).

| # | Left out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| 1 | Adopt any candidate | Adoption is Level 5 and needs a qualification run and a person. This plan makes adoption cheap; it does not perform one. | A person running `idhazh qualify` against the frozen corpus and reading the eleven gates. Nothing in this plan blocks it. |
| 2 | A vision projector | Nothing. The pipeline is text-only and a projector is the part not wanted; a multimodal GGUF is adopted by simply never fetching its `mmproj-*` file. | A reader-facing feature that reads images. None is planned. |
| 2a | **A second weights file and a speculative draft head - RETURNED to scope on 2026-09-14, and BUILT the same day.** | **The reason recorded here on 2026-09-13 was wrong, and the error is worth naming because it is a shape that recurs.** It read: "the best conceivable speculative gain is 1.30x on model time against a runner-to-runner spread of up to 4.35x - smaller than the measurement error." That compares a **within-run** delta against a **between-run** spread. An A-against-B in one job on one runner cancels the runner, and row #8 built exactly that instrument. Worse, the argument was a refusal where the guardrail only bans invented precision: an instrument too coarse to see a difference has said nothing about that difference (Guardrail #10, amended 2026-09-14). And speculative decoding is **output-identical by construction** - the target model verifies every drafted token - so it cannot make a summary worse, which takes it out of the class of changes that wait on a quality measurement at all. What it actually costs is a nullable `draft` block on the model entry, flags in `server_argv` whose spelling depends on the pinned llama.cpp build, a second optional download and checksum, and a classification in the run stamp. | **Done.** `models.<role>.draft` is a nullable block carrying the second GGUF's repository, commit, filename, digest and byte count, a closed `spec_type`, and `n_max`, `n_min` and `p_min`. `server_argv` spells the five current flags; a test refuses the four retired spellings by name, because `--draft-max` and `--draft-min` were removed from llama.cpp and a server given them does not start. `digest.yml` fetches and checksums the draft in the same steps as the target. The block is classified `NOT_DIGESTED` with the verification property as its reason. Committed config declares no draft, so nothing changes until somebody adds one. |
| 3 | Non-greedy sampling | Truncating knobs are inert at greedy decoding, and the penalties move the chosen token even at greedy - a repetition penalty tuned for agent loops taxes re-using a token that already appeared, which is what a faithful summary of a technical article must do. | A candidate whose card says it needs its own sampling. That is a Level 5 change to the determinism contract and a person's decision, not a knob - but it is a decision, not a wall. |
| 4 | A wider native context window | Nothing today: the binding constraint is the runner, not the model. The default stays conservative so a fresh entry never inherits the last model's window, and row #5 arm 5 refuses a window wider than the model was trained for. | A measured runner memory reading showing headroom at a larger window, against a candidate whose trained length exceeds the current 49,152. |
| 5 | A model name on any reader-facing page | A reader cannot see which model wrote a summary. The id is on the day payload and on eval rows; the view payload omits it deliberately. | A reader who can act on it. Nobody has named one, and Reader rules that surface. |
| 6 | Per-item tokenization against the live server | Exact per-item token counts, at the price of a network call per shard start for numbers that move only when a prompt or the model moves. | A quantity that genuinely varies per item and changes a decision. Row #13a's reader takes the fixed ones once per swap instead. |

## See also

- [`../docs/architecture/summarize/model-boundary.md`](../docs/architecture/summarize/model-boundary.md) - the boundary this plan moves into config, and the two measurement arms.
- [`../docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) - how a worker runs a row, and the no-two-rows-one-file rule.
- [`../docs/how-to/evaluate-new-summarizer-model.md`](../docs/how-to/evaluate-new-summarizer-model.md) - the page row #9 rewrites.
- [`../docs/how-to/fine-tune-a-model.md`](../docs/how-to/fine-tune-a-model.md) - the page row #9 gives a base-swap refusal.
- [`../docs/reference/measurements.md`](../docs/reference/measurements.md) - the instrument log row #7 thins, row #4 renames a rule inside, and row #13b corrects two readings in.
- [`../docs/concepts/config.md`](../docs/concepts/config.md) - the page that owns the config shape rows #2 and #6 change.
