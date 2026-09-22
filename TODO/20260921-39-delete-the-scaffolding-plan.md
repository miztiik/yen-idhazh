# Delete the scaffolding

**Last Updated**: 2026-09-22

**Level**: 5 (the generated contract layer is deleted whole, the model configuration stops being a typed shape, the startup probe that gates every run keeps one check of five, and three clauses of the engineering contract are amended to match)

**This plan dispatches nothing. It is the ledger of where its twenty-one rows went.** Section 1 says which pull request landed each one and which plan on disk carries the rest, verified against `main` rather than against a plan document. Execute nothing from here; open the plan section 1 names.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Three habits have put about forty thousand lines between a person and a change they meant to make in one file. The repository generates 24,639 lines of JSON schema and 9,640 lines of TypeScript from them; three import statements in the whole site reach any of it, and where a shape is genuinely shared the site keeps its own hand-written copy and ignores the generated one. Naming one more llama-server option costs a typed field, a branch in a builder, a regenerated schema, a version stamp, a changelog line and a test - six edits before the file that exists to carry options can carry it. And the test suite spends most of its refusals asserting that somebody else's binary honours its own parameters, log format and response shape. None of it is load-bearing, and all of it is in the way. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** This binds every pipeline, not only the model surface. Owner ruling 2026-09-21. |
| Hard scope - in | Delete the generated contract layer whole - every JSON schema, every generated TypeScript file, both generators, the drift tests and the continuous-integration job that ran them - inlining by hand the three types the site actually imports. Make the model configuration plain JSON with no typed shape, no schema and no compliance tests. Delete the speculative-decoding draft head everywhere it reaches. Delete the runtime capability probe workflow, the recorded option listing it produced, and the test that read it. Let the model file name the llama build it needs, so the installer stops naming a repository. Cut the startup probe to the one check whose failure is silent. Take the replay dimension out of qualification, which no gate's verdict reads. Make both test pipelines commit what they produce. Delete the closed-world workflow censuses that turn a new job into a test edit. Delete the reader that parses the server's log. Amend the engineering contract in the same change that contradicts it. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | (1) Row #1 deletes the artefacts a drift gate protects; if the inline of the three live types cannot be made byte-equivalent to what the site compiles against today, stop. (2) Row #2 removes the typed model shape; if the turn-marker check cannot run against a plain dictionary, stop - that check is a boundary, not a preference. (3) Row #7 deletes fields that committed qualification payloads carry - the read-side migration ships in the same commit or the row stops. (4) Row #12 amends the engineering contract; it lands in the same pull request as the first row that contradicts it, never after. (5) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Delete the generated layer first, because every other row is smaller once it is gone. Then take the model configuration out of the type system, then the features and tests that only exist to police somebody else's software. Fowler rules the contract deletions, Carmack the runtime and workflow censuses, Andre the startup probe. |
| Execution | `none. Parallel N = 0 - this plan dispatches nothing; section 1 routes each row to the plan that does.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| The trust boundary: `refuse_markers_the_boundary_cannot_hold` (`backend/idhazh/config.py:80-116`), `_CHAT_CONTROL_FAMILIES` (`backend/idhazh/sanitize.py:63-97`), `untrusted_block`, `sanitize` | A model family whose turn markers no pattern recognises cannot load until a pattern is added. That cost is paid on the next new model | Nothing here. Guardrail #11 protects a reader from a stranger's web page; an agent surfaces it and never overrules it. Moving it is a decision taken on its own |
| The Pydantic models for payloads a run writes and a later run reads | The producer keeps validating its own output at the moment it writes it | This is not scaffolding - it is one program checking its own work in one language. The rule is about not re-checking somebody else's software. What goes is the **generated** layer on top, not the models |
| The weights digest check and the fail-loudly download | Two steps and one test stay in every fetch path | They guard bytes this project downloaded. A web error page saved as model weights is the failure they exist for |
| The ten qualification gates | Validate keeps its verdict | This plan changes how many times they are asked, never what they ask |
| `server_argv` as the one place an option is spelled | One function every server start goes through | Row #2 shrinks it to spelling a dictionary. Deleting it would make each caller spell options itself, which is more code, not less |

### What a change costs today

| Reading | Value | Where |
| --- | --- | --- |
| Edits to name one more llama-server option | six, across five files | a typed field, a branch in the argv builder, a regenerated schema, a version stamp, a changelog line, a test |
| Places a new model must be wired into a workflow | seven, in three files | only the nightly run and the council call the shared block; the rest carry copies |
| Import statements in the whole site that reach a generated contract | 3 of 66 files | `frontend/src/lib/server/config.ts`, `frontend/src/lib/server/host-fingerprint.ts` |
| Shapes the site needs and keeps its own copy of instead | at least four | `frontend/src/lib/day-shape.ts`, `assist/index.ts`, `console/band.ts`, `server/payload.ts` |
| Fields on the inference block that are only a llama-server option | 24 of 31 | `backend/idhazh/contracts/knobs/inference.py` lines 17-133 |
| Fields on the turn envelope that re-implement the model's own chat template | 8 | `backend/idhazh/contracts/knobs/turns.py` |
| Gates whose verdict changes when the replay count falls to one | none of ten | scores compute under `if repeat == 1` at `backend/idhazh/stages/qualify.py:529`; canaries run on shard 0 only |
| Cost of a two-address dispatch that fails | 40 to 50 minutes | owner estimate 2026-09-21 |

## Section 0b - What this plan does, in one list

Twenty rows. Read this before the tables.

1. Delete the generated contract layer whole - every JSON schema, every generated TypeScript file, both generators, the drift tests and the continuous-integration job. Inline by hand the three types the site imports.
2. Make the model file plain JSON. No typed field, no enumerated choice, no schema and no test for anything that crosses from it to the model server.
3. Delete speculative decoding everywhere it reaches.
4. Delete the capability probe workflow, the recorded option listing and the test that read it.
5. Let a model file name the llama build it needs, so the installer stops naming one repository.
6. Cut the startup probe from five checks to one, and then to none once row 18 makes the last one unnecessary.
7. Take the replay dimension out of qualification. No gate's verdict reads it.
8. Commit what each test pipeline produces, including a summary file per article under the model's own name.
9. Delete the benchmark workflow's target and option enumerations.
10. Delete the closed-world censuses that make a new workflow a test edit first.
11. Delete the reader that parses the model server's log.
12. Amend the four contract clauses this plan contradicts, in the change that contradicts them.
13. Collapse seven hand-copied server-start blocks into one action that takes a model file path.
14. Delete the image benchmark and the two heavy dependencies it alone needs.
15. Delete the hosted trace sink and its dependency.
16. Delete the reasoning budget this project invented. Keep the two-request split, which does a second job.
17. Delete the utilities, evaluations and plan tooling nothing calls.
18. Record each model's turn markers from its own template instead of transcribing them by hand.
19. Replace nine hand-written console route lists in the site's tests with one exported constant.
20. Collapse four copies of the commit-and-push call inside one workflow file.

## Section 1 - Status Reckoner

**No row is executed from here, and every status below was read off `main` rather than off a plan.** Plans 41 and 42 were rewritten after this table first pointed at them and both files are now deleted, so a pointer of the form "plan 41 row 8" resolves to nothing. The `Where it went` column names the pull request that landed the work, or the plan file on disk that still carries it. The `Verified` column is what the tree says on 2026-09-22, with the line that proves it.

| # | Row title | Where it went | Verified on `main`, 2026-09-22 | Proof |
| --- | --- | --- | --- | --- |
| 1 | The generated contract layer goes | plan 43 row 5 | **OPEN** | `schemas/` holds 65 files; `frontend/src/contracts/`, `backend/idhazh/contracts/export.py` and `backend/tests/contracts/test_schema_drift.py` all present |
| 2 | The model file is plain JSON | PR #1036 | **LANDED** | `server: dict[str, Any]` at `backend/idhazh/contracts/knobs/models.py:147`; `schemas/models-config.schema.json` gone. Four fields stay typed - `arch`, `thinking_close`, `thinking_kwarg`, `declared_for` - which is what the amended Guardrail #3 asks for: declare what the file's own readers compute on |
| 3 | The draft head goes | PR #1036, **reversed** | **NOT DONE, by decision** | Relocated rather than deleted: `CompanionFile` at `models.py:22`, `companion_files` in `config/models/gemma-4-e4b-qat.json`. Deleting it would have destroyed the only committed control for the A/B pair that measures what the head is worth |
| 4 | The capability probe goes | PR #1035 | **LANDED** | `.github/workflows/probe.yml` deleted in `ff2f2842` |
| 5 | The installer stops naming a repository | plan 40 row 1 | **OPEN** | `.github/scripts/install-llama-runtime.sh:27` still spells `repos/ggml-org/llama.cpp`; no model file carries a `runtime` block |
| 6 | The startup probe keeps one check, then none | PR #1039 | **LANDED IN PART** | `prove_the_entry` at `backend/idhazh/llm/server.py:1532` is now marker derivation, with the boundary check riding inside it, plus one decode under a one-document schema. Five checks to one. **The "then none" half is refused in the code's own docstring**: the derivation cannot say whether the generated schema has grown a construct the grammar converter drops |
| 7 | Qualification asks each article once | plan 43 row 1 | **OPEN**; the one-pass cut refused | `--repeats` still on the dispatch surface at `backend/idhazh/cli.py:345`. Cutting three passes to one moves the measured side of the only gate reading Guardrail #2 without moving the bound - plan 43 scope-out |
| 8 | Both test pipelines commit what they produce | plan 43 row 3 | **OPEN** | no `summaries` write anywhere in `backend/idhazh/stages/record.py` |
| 9 | The benchmark workflow's closed-world tests go | PR #1037 | **LANDED** | `backend/tests/workflows/test_bench_input_drift.py` deleted |
| 10 | The workflow censuses go | PR #1037 | **LANDED** | both censuses now discover: `test_model_server_jobs.py:116` and `test_script_invocation.py:55` each walk `SCRIPTS_DIR.glob("*.sh")` |
| 11 | The server-log reader goes | PR #1036 | **LANDED** | the optimisation reader is gone from `backend/idhazh/llm/`. `model_load_ms` at `backend/idhazh/telemetry/silicon.py:473` reads the log for one telemetry number and was never in this row's scope |
| 12 | The engineering contract and the pages catch up | PR #1036 and #1044, then plan 43 row 6 | **LANDED IN PART** | Guardrail #3 (`CLAUDE.md:90`) and section 11 (`:260`) carry the owner ruling of 2026-09-21. Section 1a (`:105` and `:110`), section 9 (`:221`) and section 13 (`:299`) still describe a generated layer that row 1 deletes |
| 13 | The entry path is one action taking a model file | plan 44 row 2 | **OPEN** | `.github/actions/model-server/action.yml` still takes `weights_repo`, `weights_revision`, `weights_file`, `llama_cpp_build` and three `draft_*` inputs, and has no `models_file`. Two workflows call the action; two call `fetch-model-runtime.sh` themselves |
| 14 | The image benchmark goes, and two heavy wheels with it | PR #1035 | **LANDED** | `backend/utilities/bench_image.py` deleted in `ff2f2842`. One wheel, not two |
| 15 | The hosted span sink goes | plan 43 row 7 | **OPEN. The refusal is lifted** | The 2026-08-30 ruling at `docs/concepts/telemetry.md:553` was reversed by owner approval on 2026-09-22 (CLAUDE.md section 0). `langfuse_sink` at `backend/idhazh/telemetry/sinks.py:113` is still there |
| 16 | The thinking budget goes; the two-span call stays | PR #1036 | **LANDED** | `max_think_tokens` is gone from `backend/idhazh/` and `config/`; the only remaining mentions are the changelog assertions in `test_schema_drift.py` |
| 17 | The utilities and evaluations nothing calls go | plan 43 row 2 | **OPEN** | 68 Python files in `backend/utilities/`; `plan_status.py`, `label_queue.py` and `probe_feeds.py` all present |
| 18 | The model's own template renders the prompt | PR #1039 | **LANDED** | `derive_turn_markers` at `backend/idhazh/llm/server.py:1434`; no `turn_opening` key in any `config/models/*.json` |
| 19 | One console route list, not nine | PR #1040, then plan 45 | **LANDED IN PART**; the single-list design refused | Five of nine lists were widened to all five routes. The refusal is recorded in the code at `frontend/src/lib/console/band.ts:131-133`. The two specs that still miss a route are plan 45 |
| 20 | One commit call in the workflow that has four | nowhere | **NOT DONE, by decision** | The premise was wrong: `.github/workflows/idhazh-pipeline-tests.yaml` has **zero** commit-and-push calls today, so there are no four to merge |
| 21 | One request builder, and the pipeline stops naming a server | PR #1036 for the stamp; the rest is now plan 47 | **LANDED IN PART; most of the rest refused** | The stamp went in #1036. The four builders at `server.py:496`, `:554`, `:608`, `:783` stay - they are four shapes carrying four different Guardrail #11 controls. The move to the widely-supported route is refused by a measurement at `server.py:58-66` dated after this row was written. The three slot cells stay - `backend/utilities/slot_probe.py` is their named instrument. **What survives is the host**, and it is [`20260922-47-the-pipeline-stops-naming-a-server-plan.md`](20260922-47-the-pipeline-stops-naming-a-server-plan.md) |

**Eight rows landed whole, four landed in part, seven are open and two are not being done.** That accounts for all twenty-one.

### The last row to find a home, and what it turned out to be

**Row 21 was orphaned until 2026-09-22, and reading it against the tree shrank it to one line.** Three of its four demands no longer hold.

| What row 21 asked for | What is true on `main` |
| --- | --- |
| Delete the decode-identity stamp | Done, #1036 |
| Replace two request builders with one | There are **four**, and they are four shapes rather than four spellings - a `messages` array, a `prompt` string, a `grammar` field, and a prior body extended. Each names a different Guardrail #11 control in its own docstring |
| Move to the widely-supported route | Refused by a measurement at `server.py:58-66` taken 2026-09-12, after this row was written: on the compatibility route the `json_schema` field survives a layer that already drops `response_format`, and no workflow pins a llama.cpp build, so a build that started stripping it would turn constrained decoding off for every item at once |
| Delete the llama-specific slot cells | There are **three**, not two, and they have a named instrument at `backend/utilities/slot_probe.py`, a reader at `item_health_provenance.py:236-238` and three doc pages. Measured: 1,668 of 14,346 committed rows carry them - the first call of a two-call stage, sparse by design |
| **The pipeline stops naming a server** | **Still true, and the only part that is.** The port is already `LLAMA_PORT`; the host is spelled `127.0.0.1` in three module constants with no parameter, config field or environment variable reaching it |

That last line is [`20260922-47-the-pipeline-stops-naming-a-server-plan.md`](20260922-47-the-pipeline-stops-naming-a-server-plan.md) - **six rows, two pull requests, Level 2**, not the Level 5 this page estimated before the measurement. It shares one file with plan 44, `backend/idhazh/llm/server.py`, and no lines within it.

### Where the work is now

| Plan on disk | Which of these rows it carries | State |
| --- | --- | --- |
| [`20260921-40-bonsai-probe-plan.md`](20260921-40-bonsai-probe-plan.md) | 5 | all 7 rows PENDING |
| [`20260921-43-the-ledgers-and-the-generated-layer-plan.md`](20260921-43-the-ledgers-and-the-generated-layer-plan.md) | 1, 7, 8, 12, 15, 17, and 19's residue | row 4 DONE, six PENDING |
| [`20260922-44-the-model-file-is-the-fetch-interface-plan.md`](20260922-44-the-model-file-is-the-fetch-interface-plan.md) | 13 | row 4 DONE, four PENDING |
| Plan 45, the readout over every console route | 19's residue | all 5 rows LANDED in #1045, #1046 and #1049; distilled to [`docs/architecture/publishing/console-charts.md`](../docs/architecture/publishing/console-charts.md) and deleted |
| [`20260922-47-the-pipeline-stops-naming-a-server-plan.md`](20260922-47-the-pipeline-stops-naming-a-server-plan.md) | 21's remainder | all 6 rows PENDING |

Lane A ran from `20260921-41-lane-a-model-file-plan.md`, delivered in PRs #1036 and #1039, and was deleted on close. Lane B ran from `20260921-42-lane-b-workflows-plan.md`, delivered in PRs #1034, #1035 and #1037, and was deleted on close. Both were renumbered while they ran, so their row numbers are not quoted here - the pull request is what a reader can still open.

**Parallel N = 0 here.** This plan dispatches nothing. The rows stay listed so their numbers still resolve.

## Section 1b - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. Every persisted or interface shape this plan moves is declared here. **A worker does not invent one of these; it reads this section.** Where a shape is deleted rather than changed, the read-side behaviour for payloads already written is declared too.

### C1 - The model file (rows 2, 5, 16, 18)

`config/models/<name>.json`. No Pydantic model, no generated schema, no test of its contents. Read as a mapping.

| Key | Shape | Who reads it | Note |
| --- | --- | --- | --- |
| `summarize` | mapping | everything below | one required role |
| `judge` | mapping, optional | the similarity judge | same shape as `summarize` |
| `<role>.id` | string | the argv builder's alias, the decision record | |
| `<role>.repo`, `.revision`, `.file` | string | the weights fetch | |
| `<role>.sha256`, `.byte_count` | string, integer | the weights check | **kept** - guards bytes we fetched |
| `<role>.arch` | string | census its readers in row 6 before keeping | |
| `<role>.runtime` | mapping, optional | the installer | **new in row 5**: `repo`, `build`, `asset`, `sha256`. Absent means the repository-wide pin |
| `<role>.inference` | mapping | the argv builder, the request body, our own loop | **untyped**. Every key is passed through unless named below |
| `<role>.turns` | mapping | the prompt render, the marker check | **machine-recorded in row 18**, not typed by hand |

**Keys under `inference` this project's own code reads**, and which must therefore be present - a worker uses direct indexing so a missing one raises at load naming the key, never `.get` with a default:

| Key | Read by |
| --- | --- |
| `n_ctx` | the window arithmetic in `classify/dag.py` and the context gate in `evals/qualify.py` |
| `max_answer_tokens` | the answer request's token cap |
| `temperature`, `top_p`, `seed` | the request body and the qualification report |
| `request_timeout_minutes` | our own HTTP client |

**Deleted from this file**: `declared_for` on both blocks, `max_think_tokens`, `draft`, and every enumerated choice. **Read-side migration**: a file that still carries a deleted key is ignored, not refused, for one release.

### C2 - The turn markers, recorded not typed (row 18)

Eight keys under `<role>.turns`: `turn_opening`, `turn_closing`, `reply_opening`, `reply_opening_thinking`, `thinking_close`, `system_role`, `system_joiner`, `thinking_kwarg`.

They keep their current meanings and their current place in the file. **What changes is who writes them.** A one-off utility posts a known message list to the server's template-applying route, reads back the model's own rendering, derives the eight values from it, and writes them into the model file. A person runs it once per model and never types a marker.

**The marker check is unchanged in force and in position**: `refuse_markers_the_boundary_cannot_hold` still runs at configuration load, in every process, over a plain mapping, with no server. Guardrail #11 does not move.

### C3 - The qualification record (rows 7, 17)

| Change | Shape | Read-side migration |
| --- | --- | --- |
| `repeats` removed from the shard and the report | integer | a committed payload carrying it still loads; the value is ignored |
| `repeat` removed from an observation | integer | same |
| Five demoted scores removed from the report's diagnostics | named strings | same. **The measuring functions are untouched** - see row 17 decision 7 |

**Not touched by any row**: `backend/idhazh/evals/metrics.py`, `backend/idhazh/evals/score.py`, `backend/idhazh/corpus.py`. Those set the published confidence line and filter the fine-tuning corpus.

### C4 - The summaries collection (row 8)

**New committed collection.** `state/<model id>/summaries/<YYYY>/<MM>/<DD>/<item id>.json`.

| Property | Value |
| --- | --- |
| Payload | the summary shape the pipeline already produces. No new shape is invented |
| One file per | article |
| Written by | the record stage, and only when a trial state root is set |
| Directory name | the model's own identifier, so the tree says which model wrote it |
| Retention | a window declared on the line that creates the collection (Guardrail #12) |
| Production | never writes it - the nightly run leaves the trial root unset |

### C5 - The entry action (row 13)

`.github/actions/model-server/action.yml`.

| Input | Before | After |
| --- | --- | --- |
| `github_token` | required | required |
| `port` | required | required |
| `models_file` | absent | **new** - path to the model file, defaulting to the committed pointer |
| `weights_repo`, `weights_revision`, `weights_file`, `llama_cpp_build` | required | **removed** - read from the model file |
| `draft_repo`, `draft_revision`, `draft_file` | optional | **removed** with row 3 |

Steps go from five to four: cache, fetch-and-verify, start, one health check. The three shell scripts become one.

### C6 - What leaves the repository entirely (rows 1, 3, 4, 11, 14, 15, 17)

`schemas/`, `frontend/src/contracts/`, the two generators, the drift tests and the drift job. The draft-head configuration and its argv flags. The capability probe workflow, the recorded option listing and its test. The server-log optimisation reader. The image benchmark and its two dependencies. The hosted trace sink and its dependency. The utilities, evaluations and plan tooling with no caller.

**Three types are inlined by hand before the generated layer goes**, next to the code that imports them: one panel-group type in the site's configuration reader, and two in its machine-fingerprint reader.

### C7 - The engineering contract (row 12)

| Clause | After |
| --- | --- |
| Guardrail #3 | The producer declares and validates its own payloads in its own language. A configuration file this project authors needs no declared shape. Generation into a second language happens where a second language reads the bytes - today, nowhere |
| Section 1a, second bullet | Deleted. Nothing generates and nothing drifts |
| Section 9, the drift-gate line | Deleted from the Definition of Done, along with the schema version-stamp line |
| Section 10, hand-editing a generated artifact | Deleted - there are none |
| Section 11 | Scoped to persisted payloads a later run reads. A configuration file this project authors is out |
| `AGENTS.md` | The three phrases saying contracts are generated from the models, named and removed |

**Guardrail #11 and Guardrail #12 are untouched.**

### C8 - The pre-flight position, stated once

Rows 6 and 18 together leave **no check running before the first article is fetched**. That is the intended end state and it is written here so it is never a surprise: after this plan, a wrong model file is found by the run failing, by the ledger's own cells, or by a person reading the summaries. The cells that report it are `summary_finish_reason`, `OUTPUT_TRUNCATED`, `CONTEXT_EXCEEDED` and `source_words_before_cap`, all committed per item. The failure none of them sees is a window declared larger than the weights were trained for; the run stamp records the trained length beside the configured one as an observation, never a refusal. The rest of the documentation follows row #1.

## Section 1a - What the advisory review changed, 2026-09-21

Fowler, Carmack and Andre reviewed the plan. Three of its statements were wrong and the order was wrong.

| What the plan said | What is true | Ruled |
| --- | --- | --- |
| Row #1 runs first, because everything shrinks after it | Generated lines are the cheapest in the repository to hold and the most expensive to remove. The toll a person actually pays - six edits to name one option - is removed by row #2, and standing a model up is made cheap by row #13. Row #1 now runs late | Owner, on all three advisors agreeing |
| Row #13 calls the benchmark, qualification and pipeline-test workflows "call sites" of the shared model-server action | They are not call sites. Only the nightly run and the council call it. The other three each carry their **own copy** of fetch, verify, start and health - seven copies, about 465 lines. Row #13 now deletes the copies | Carmack |
| Row #13's action takes a token and a port | It takes a **model file path**. The action reads the summarize role out of one fixed configuration file today, which is exactly why three workflows wrote their own copy | Carmack |
| Row #7's oracle is that all ten gates return the same verdict | That oracle cannot fail: the row's own evidence is that no gate reads the replay dimension, so it passes whether the code is right or wrong. The oracle is now the read-side migration on committed payloads | Fowler |
| Plan 40: a 27B at two bits projects near 14 GiB against a 16 GB runner | Memory is not the leading risk. The incumbent peaks at 12.57 to 13.16 GiB for the server on a 5.29 GiB model, driven by the 65,536 window and its cache rather than the weights. At a 32,768 window the larger model fits with more headroom than production has now. The risks in order are: does the fork binary execute, then decode rate, then the window, then the packing | Carmack |

Two zero-cost defects were found while reading and are folded into row #2: a thinking budget of zero reads as uncapped because the code spells it `or 0`, and a missing turn-marker key renders an anonymous turn because the reader spells it `.get(..., "")`. Row #2 uses direct indexing and an explicit `is None` instead.

Four proposals were declined. Keeping the capability probe until the fork is proven (owner: gone now). Keeping a second startup check (owner: one check). Pointing the benchmark target at the fork before the cleanup (owner: clean up first). Bounding the summaries collection by dispatch count rather than days (Fowler proposed it; the retention window stays, because a collection with no time bound is the growth Guardrail #12 names).

## Section 2 - Row #1 - The generated contract layer goes

- **Scope:** Delete every generated JSON schema and every generated TypeScript contract, the two generators that wrote them, the drift tests and the continuous-integration job that ran them, after inlining by hand the three types the site imports.
- **Files touched:**
  - `schemas/` (all 66 files)
  - `frontend/src/contracts/` (all 66 files)
  - `backend/idhazh/contracts/export.py`
  - `backend/idhazh/contracts/typescript.py`
  - `backend/idhazh/contracts/base.py`, `derived.py` (the schema-writing parts only)
  - `backend/tests/contracts/test_schema_drift.py`
  - `backend/tests/contracts/test_typescript_contracts.py`
  - `backend/tests/contracts/test_cell_shapes.py`
  - `.github/workflows/ci.yml` (the drift job)
  - `frontend/src/lib/server/config.ts`, `frontend/src/lib/server/host-fingerprint.ts` (the three inlined types)
  - `frontend/scripts/tests/test-scope.test.mjs`
  - `frontend/package.json` (any generation script)
- **Acceptance gates:** local - `npm --prefix frontend run check` and `npm --prefix frontend run test:changed -- --list` then the selected checks; `python -m pytest backend/tests/contracts -q`; CI - full suite and the browser smoke. ESCALATE trigger 1 applies.
- **Oracle:** the site compiles and every page renders with no generated file present, and the three inlined types are structurally identical to the generated ones they replace - compared field by field before the deletion. The browser smoke is the second half: every route loads with zero new console errors and zero new missing files.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The layer is deleted whole rather than pruned to the used files. 62 of 66 have no importer, and a generator kept for four types is a generator | Owner ruling 2026-09-21 |
 | 2 | The three live types are inlined by hand next to the code that imports them. Hand-written is what the site already does for the day payload, the search index and the console band | Fowler |
 | 3 | The drift gate goes with the artefacts. It checked that a generated file still matched the thing that generated it, which is a loop | Fowler |
 | 4 | The Pydantic models stay. They are the validation; the schemas were a copy of them in another notation | Fowler |
 | 5 | **The page that describes the layer is deleted, not refreshed.** `docs/architecture/contracts/schemas.md` is routed to by the agent bootstrap, so the next agent reading a page titled for schemas builds what it describes. This is the single most likely way the whole layer returns | Fowler |
 | 6 | **The agent pointer is amended by its words.** `AGENTS.md` says the contracts are generated from the models in three places, and agent tools read that file instead of the engineering contract. An unnamed amendment is one nobody checks, so row #12's clause table names those three phrases the way it names the five | Fowler |
 | 7 | **The changelog requirement dies with its consumer.** The prose on every contract is copied into the generated schema and nowhere else, and a guard raises when it is empty. Deleting the consumer and leaving the requirement taxes every future contract with two sentences nobody reads. The version stamp stays; the prose, the guard and the test that walks every contract file go | Fowler |
 | 8 | **A green suite is not the proof here.** Three surviving tests are parametrized over a glob of the deleted directory and will pass with zero cases rather than fail. The check is a comparison of collected test counts before and after, not pass or fail, and the shared constant pointing at the deleted directory is removed in the same commit | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete only the 62 unimported TypeScript files | Leaves the generator, both drift tests, the continuous-integration job and 24,639 lines of schema in place to serve four types | About 8,700 lines removed instead of about 34,000, and the same six-edit ritual for every field | Fowler |
 | 2 | Keep the schemas, delete the TypeScript | The schemas' only readers after that are the generator that writes them and the test that checks the generator | About 9,600 lines removed, and a gate policing itself | Fowler |
 | 3 | Point the site at the generated types instead of its hand-written copies | The opposite change, and defensible - one declaration per shape. It loses because nobody has wanted it for 66 shapes over the life of the project, and the hand-written copies are the ones under test | A rewrite of the payload, search and console layers, against a need nobody has expressed | Fowler |

## Section 3 - Row #2 - The model file is plain JSON

- **Scope:** Delete the typed model configuration - the entry, the inference block, the turns block and their validators - and read the file as plain JSON, keeping only the turn-marker check against the sanitizer.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/models.py`
  - `backend/idhazh/contracts/knobs/inference.py`
  - `backend/idhazh/contracts/knobs/turns.py`
  - `backend/idhazh/config.py`
  - `backend/idhazh/llm/server.py` (`server_argv` spells a dictionary)
  - `backend/idhazh/fingerprint.py` (the run identity hashes the whole options map)
  - `backend/idhazh/contracts/qualification.py` (`PipelineInputs` stops naming five options individually)
  - `config/models/` (all five files)
  - `backend/tests/contracts/test_model_registry.py`
  - `backend/tests/contracts/test_turn_envelope.py`
  - `backend/tests/test_summarize.py`, `backend/tests/test_classify.py`, `backend/tests/test_fingerprint.py`
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'config or model or summarize or fingerprint' -q`; CI - full suite. ESCALATE trigger 2 applies.
- **Oracle:** the command line built from each of the five committed model files is byte-identical to the one built from it today, argument for argument and in the same order. That is what proves the plain file carries exactly what the typed shape carried. What it cannot settle: whether a misspelled option is caught. After this row it is not - llama-server refuses to start and names it, which is the intended behaviour.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Anything that crosses from the model file to llama-server gets no type, no enumerated choice, no schema and no test.** Not a sampling value, not a window size, not a thread count, not a cache kind, not a budget, not a timeout, and not whatever is added next. The file is a dictionary; the builder spells it; the runtime refuses what it does not accept and says which key | Owner ruling 2026-09-21 |
 | 2 | The values named in earlier drafts - the sampling temperature and the nucleus cut-off - were examples of the rule, never the extent of it. No field is carved out for being read by this project's own code on the way past | Owner ruling 2026-09-21 |
 | 3 | `declared_for` is deleted. It was refused unless it equalled a digest already in the same object, so it carried no information | Fowler |
 | 4 | The refusals for renamed keys are deleted. They are migration scaffolding for renames that already landed, and no committed file carries an old spelling | Fowler |
 | 5 | The turn-marker check stays and runs against the plain dictionary. It is the trust boundary, not a type check | Fowler, Guardrail #11 |
 | 6 | The run's recorded identity hashes the whole options map in a canonical form - keys sorted, scalars normalised - so a change in key order cannot move the stamp. It also prints the sampling values beside the hash, because a person reading a failed verdict needs the number, not a digest | Fowler, with Andre on what an evaluation record must carry |
 | 7 | **The reader indexes directly and compares against `None` explicitly.** Two defects exist today and both get worse untyped: a thinking budget of zero reads as uncapped because the code spells it `or 0`, and a missing turn-marker key renders an anonymous turn because the reader spells it `.get(..., "")`. Direct indexing raises at load and names the key. This costs nothing | Andre |
 | 8 | **The field on the application configuration that holds the model file becomes an untyped mapping that permits unknown keys.** Left typed with extras forbidden, the first new option is a validation error and re-adding the field is the obvious fix | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep typed fields for the six values this project's own code reads | Two ways to declare a value and a rule about which wins. The code that reads them can read a key | About 60 lines kept, and a reader who cannot tell which half of the file they are in | Owner ruling 2026-09-21 |
 | 2 | Validate option names against a recorded listing of what the build accepts | Rebuilds the thing row #4 deletes, at the same cost and for the same reason | A recording per build, and a pin that cannot move without a dispatch | Carmack |
 | 3 | Keep the schema and generate it from whatever keys the file holds | A schema derived from the file it validates passes by construction | About 30 lines for a check that cannot fail | Fowler |

## Section 4 - Row #3 - The draft head goes

- **Scope:** Delete speculative decoding everywhere it reaches - the configuration, the enumerated kinds, the argument builder, the weights fetch, four workflows' pass-through wiring, two model files and the tests.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/models.py` (`DraftConfig`, `SpeculationType`, the entry field)
  - `backend/idhazh/llm/server.py` (the draft arguments)
  - `backend/idhazh/fingerprint.py` (its entry in the not-digested mapping)
  - `.github/scripts/fetch-model-runtime.sh`
  - `.github/actions/model-server/action.yml`
  - `.github/workflows/digest.yml`, `validate.yml`, `measure.yml`
  - `config/models/gemma-4-e4b-qat.json`, `config/models/gemma-4-e4b-qat-no-draft.json`
  - `backend/tests/test_summarize.py`
  - the documentation pages that describe it
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'summarize or workflow'`; CI - full suite.
- **Oracle:** no file in the repository mentions a draft head, a speculation kind or a speculative argument, proved by grep; and the command line built from every remaining model file is unchanged. This is a deletion, so the check is the census.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | It is deleted rather than kept unused. A measurement on 2026-09-12 found it changes the output on nine articles of nine, so it was never a free speed-up | Owner ruling 2026-09-21 |
 | 2 | **The fetch generalises rather than losing a capability.** The model file gains `companion_files`: a list, each entry naming a repository, an exact commit, a filename and a checksum. One loop downloads each and checks each. Adding a draft or multi-token head to any model is then one more entry in that list, never a code change. Absent or empty means weights only, which is every model today | Fowler and Carmack, agreed 2026-09-21 |
 | 3 | **The installer publishes each landed path.** A speculative head is named to the server as a *path*, and an untyped options map cannot name a file the installer chose. Without this, speculative decoding cannot come back as configuration at all | Carmack |
 | 4 | Every field that becomes part of a web address or a command argument is a single bare word, checked before it is used. These cross to a download and to a shell, not to the model server, so row #2's ruling does not reach them (Guardrail #11) | Fowler |
 | 5 | The two model files lose the typed draft block. They are entries for a model, not for a draft head | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the argument builder and drop only the configuration | Leaves code nothing can reach | About 25 lines kept and a dead branch | Carmack |

## Section 5 - Row #4 - The capability probe goes

- **Scope:** Delete the workflow that asked the pinned build what it accepts, the recording it produced, and the test that read it.
- **Files touched:**
  - `.github/workflows/probe.yml`
  - `backend/tests/workflows/test_runtime_accepts.py`
  - `tests/fixtures/runtime/b10598-llama-server-help.txt`
  - `backend/tests/workflows/_harness.py` (the pinned-build constant, if nothing else reads it)
  - `docs/reference/ci-model-runtime.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** changing the pinned build touches no test fixture, proved by grep finding no reader that resolves a filename from the build. The probe workflow's only consumer was the deleted test, which is the census this row runs first.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The probe's only consumer is the test being deleted, so it goes with it rather than staying as a workflow nobody dispatches | Carmack |
 | 2 | The defect it was written for now fails at the health check or the first article, costing job minutes rather than an hour of benchmark time, and it cannot reach a reader | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the probe as an operator tool | A dispatchable workflow with no consumer is a file people have to reason about | 184 lines kept. The same answer is one command against a running server | Carmack |

## Section 6 - Row #5 - The installer stops naming a repository

- **Scope:** Let the model file name the llama build it needs, and make the installer resolve a release from whatever repository it is handed, defaulting to the repository-wide pin.
- **Files touched:**
  - `.github/scripts/llama-cpp-pin.sh`
  - `.github/scripts/install-llama-runtime.sh`
  - `backend/utilities/llama_runtime.py` (new; prints the resolved values, mirroring `llama_argv.py`)
  - `config/models/` (entries that need a build other than the pin)
  - `backend/tests/workflows/_harness.py`
  - `docs/reference/ci-model-runtime.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, `shellcheck` on both scripts; CI - full suite.
- **Oracle:** with no model naming a build, the release address the installer resolves is byte-identical to today's; with one naming a build, it is that build's address. Both arms assert a string and download nothing.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The build lives in the model file, because the file naming the weights should name the binary that decodes them. After row #2 that is four more keys | Carmack |
 | 2 | The installer reads them from the environment rather than as arguments, matching the weights half, so no value is pasted into the program before it is a value (Guardrail #11) | Carmack |
 | 3 | The repository-wide pin stays as the default, so every current model is unchanged | Carmack |
 | 4 | The stamp a run records needs no change: it already reads the build from the environment | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | A second pin file for a fork | Two files holding a build with nothing tying either to the model that needs it, and a fork binary loads an ordinary model file happily - a green run measured on a binary production does not ship | About 10 lines, and drift | Carmack |

## Section 7 - Row #6 - The startup probe keeps one check

- **Scope:** Reduce the startup probe from five checks to the one whose failure is silent.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (`prove_the_entry` and the four deleted predicates, plus the header parser)
  - `backend/utilities/prove_the_entry.py`
  - `backend/tests/test_summarize.py`, `backend/tests/test_classify.py`
  - `docs/architecture/contracts/determinism.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/test_summarize.py backend/tests/test_classify.py -q`; CI - full suite.
- **Oracle:** a model file declaring a turn envelope that disagrees with the weights' own chat template is still refused at start, driven from a recorded server response so nothing touches the network. What it cannot settle: whether a summary is good - the probe never measured that.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | Keep the render check. It compares this project's prompt rendering against the model's own template, and a disagreement produces flat summaries with nothing going red. After row #2 nothing else checks the turn envelope at all | Andre |
 | 2 | Delete the schema-constraint check. A reply that breaks the schema fails at the parser, on that article, with a named failure | Andre |
 | 3 | Delete the prefix-cache check. It guards a speed reading, not an output | Carmack |
 | 4 | Delete the trained-window check. Owner ruling 2026-09-21 | Owner |
 | 5 | Delete the architecture check and the header parser with it. The weights digest already pins the exact file, so reading a string out of its header to compare with a string we typed is a second check of the same fact | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete all five | The render check is the only one on the list whose failure is silent, and the rule this plan runs on is that a mistake must fail loudly | About 25 more lines removed, and a wrong turn envelope reaching readers as flat summaries | Andre |

## Section 8 - Row #7 - Qualification asks each article once

- **Scope:** Remove the replay dimension from qualification - the dispatch input, the loop, the freeze that existed to make replays identical, and the one diagnostic that consumed it.
- **Files touched:**
  - `.github/workflows/validate.yml`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/stages/qualify.py`
  - `backend/idhazh/evals/qualify.py`
  - `backend/idhazh/contracts/qualification.py`
  - `backend/tests/workflows/test_qualification_and_browser.py` and the qualification tests
  - `docs/concepts/evaluation.md`
- **Acceptance gates:** local - `python -m pytest backend/tests -k qualif -q`; CI - full suite. ESCALATE trigger 3 applies.
- **Oracle:** a qualification payload written before this change still reads after it, asserted against a committed payload that carries the deleted fields. That is the check, and it can fail. **The obvious oracle - that all ten gates return the same verdict - cannot fail**, because the row's own evidence is that no gate reads the replay dimension, so it passes whether the code is right or wrong. What the migration check cannot settle: how widely a sampler's wording varies; that reading leaves with the diagnostic and nothing replaces it.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | No gate's verdict depends on replays. Seven read observations that are properties of the request; three read scores, and scores compute on the first pass only | Fowler, verified against the code 2026-09-21 |
 | 2 | The freeze goes with the replays. Its purpose was byte-identity across them | Fowler |
 | 3 | The wording-spread diagnostic goes. On one pass it can only report nothing | Andre |
 | 4 | The dispatch input is deleted, not defaulted. A knob nobody should raise is a knob somebody will | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Default the replay count to one and keep the machinery | Keeps the loop, the freeze, the contract fields and the diagnostic for a value nobody sets | About 200 lines, and two thirds of the model calls back the moment somebody raises it | Fowler |

## Section 9 - Row #8 - Both test pipelines commit what they produce

- **Scope:** Keep the qualification workflow's verdict commit, and give the pipeline test its own committed collection of the summaries each article produced.
- **Files touched:**
  - `.github/workflows/validate.yml` (unchanged commit; the fold step reviewed)
  - `.github/workflows/idhazh-pipeline-tests.yaml`
  - `backend/idhazh/ledger.py` (a path for the new collection)
  - `backend/idhazh/stages/record.py`
  - `backend/idhazh/contracts/knobs/retention.py`
  - `backend/tests/workflows/test_staged_paths.py`, `test_validation_state_root.py`
  - `docs/reference/repository-layout.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows backend/tests -k 'state or ledger or record' -q`; CI - full suite.
- **Oracle:** a pipeline-test dispatch writes a summary file for every planned article, all of them inside the run's own state root and none outside it - the staged-path check already refuses a path outside the root.
- **The path:** `state/<model id>/summaries/<YYYY>/<MM>/<DD>/<item id>.json`. The existing trial redirect at `backend/idhazh/cli.py:519` moves every state collection under a named directory, so the directory name **is** the model's own identifier. Two models summarising one article land in two trees a person can read side by side.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | A producer commits what it produces. No census of who reads it, and no consumer's absence changes what a producer writes | Owner ruling 2026-09-21 |
 | 2 | The qualification workflow keeps its verdict commit and its write permission for the same reason | Owner ruling 2026-09-21 |
 | 3 | **Each dispatch names its own destination, and its own model file.** Both are dispatch inputs on all three workflows - the qualification run, the pipeline test and the benchmark - defaulting to the model's own identifier. Today the qualification run hard-codes a directory named after a different workflow, and the benchmark names none at all | Owner ruling 2026-09-21 |
 | 4 | **The whole telemetry set is committed, not only the summaries**: the item-health rows, the host fingerprint, the traces and the segments. They already follow the destination automatically - one redirect happens before any stage runs, and every stage reads it - so this is a dispatch input, not new code | Owner ruling 2026-09-21 |
 | 5 | Production is never touched. The nightly run leaves the destination unset and writes where it writes today | Fowler |
 | 6 | One file an article on the day tree, not one file a day. A file an article means a re-run replaces exactly what it re-summarised | Fowler |
 | 7 | The summaries collection carries a retention window on the line that declares it (Guardrail #12) | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep per-article output as an upload only | An upload expires and has to be downloaded. The point is reading one model's writing against another's months later | Nothing - it is today's behaviour | Owner |
 | 2 | Commit the whole run directory | The article text is the largest part and is fetchable from its address; the cost and health rows already land in their own ledgers | Several times the bytes for readings recorded elsewhere | Fowler |

## Section 10 - Row #9 - The benchmark workflow's closed-world tests go

- **Scope:** Delete the tests that assert the benchmark workflow's exact target list, option list and job wiring, and remove the draft cases from its dispatch.
- **Files touched:**
  - `backend/tests/workflows/test_bench_targets.py`
  - `backend/tests/workflows/test_bench_input_drift.py`
  - `.github/workflows/measure.yml`
  - `backend/tests/workflows/_harness.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** adding or removing a benchmark option requires no test edit, demonstrated by the draft-case removal in this row passing with no constant changed. That check fails on the base tree, which is the defect the row exists for.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | A test enumerating a workflow's options makes every option change a two-file change | Carmack |
 | 2 | The benchmark workflow keeps its jobs. This row removes the tests that fossilise them and the draft cases row #3 orphaned | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Edit the constants and keep the tests | Pays the toll once and leaves it standing | About 8 lines now and the same again every time | Carmack |
 | 2 | Delete the benchmark workflow entirely | It answers a real question - raw throughput on a machine - that no other workflow answers | 1,226 lines removed and no way to measure a model's ceiling. Revisit once the pipeline test reports per-article speed | Carmack |

## Section 11 - Row #10 - The workflow censuses go

- **Scope:** Delete the closed-world assertions over which jobs may start a model server, which steps that block must contain, which files may spell the build pin, and which module every server start must reach - keeping the checks that guard fetched bytes and that a server is proven healthy before anything measures it.
- **Files touched:**
  - `backend/tests/workflows/test_model_server_jobs.py`
  - `backend/tests/workflows/test_pinned_versions.py`
  - `backend/tests/workflows/test_weights_and_model_refs.py`
  - `backend/tests/workflows/_harness.py`
  - `.github/workflows/measure.yml` (its inline pin, converted so no file keeps a copy)
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** a new workflow that stands a model server up passes the suite with no constant edited - demonstrated by the pipeline-test changes in plan 40, which fail this suite on the base tree.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | Keep every fetch pinned to one release and digest-checked, and keep the refusal to take whichever release is newest. Those guard bytes this project downloads | Carmack |
 | 2 | Keep the health check naming the weights that answered, and the refusal to measure before it passes. A number taken against the wrong weights is a wrong number under a right name | Carmack |
 | 3 | Delete the caller enumerations, the five-step closed world, the one-home census and the argument-builder census. All four police authorship, and all four refuse the shape the next workflow needs | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete all of them | Two are about bytes this project fetches, which the scope-out table keeps | About 40 more lines, and a fetch that could silently take the newest release | Carmack |
 | 2 | Delete the shared composite action too | It stops five steps being re-spelled per caller, so deleting it makes a new workflow longer | About 200 lines removed and five steps added to each caller | Carmack |

## Section 12 - Row #11 - The server-log reader goes

- **Scope:** Delete the reader that parses the model server's log to learn whether an optimisation engaged, and the tests that assert this project's patterns match the runtime's log format.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (`flash_attention_state` and its enumerated states)
  - `backend/tests/test_summarize.py`
  - `backend/tests/workflows/test_model_server_jobs.py` (the two log-format assertions)
  - `tests/fixtures/runtime/` (the log captures)
  - any console surface carrying the reading
- **Acceptance gates:** local - `python -m pytest backend/tests/test_summarize.py backend/tests/workflows -q`; CI - full suite, plus the browser smoke if a console surface loses a field.
- **Oracle:** no reader of the server's log text survives except the ones producing the run's own cost figures, proved by grep.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | Whether an optimisation engaged is the runtime's business, and this project asked by parsing a log line at a raised verbosity | Carmack |
 | 2 | The two log-format tests go with it. A test asserting our pattern matches a third party's log fails on their release note, not our defect | Carmack |
 | 3 | The error-body classifier stays. It sorts a failure into this project's own taxonomy | Fowler |
 | 4 | A console panel showing the reading loses the field rather than keeping a cell that can only say it could not tell | Susan |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the reader, drop the tests | A parser with no check on it goes wrong silently | About 20 lines kept | Carmack |

## Section 13 - Row #12 - The engineering contract and the pages catch up

- **Scope:** Amend the clauses of the engineering contract this plan contradicts, in the change that contradicts them, and refresh every page whose description of the contract layer, the model file, the startup probe or the qualification record is now wrong.
- **Files touched:**
  - `CLAUDE.md` (Guardrail #3, section 1a, section 9, section 10, section 11)
  - `AGENTS.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/reference/ci-model-runtime.md`
  - `docs/architecture/contracts/determinism.md`
  - `docs/concepts/evaluation.md`
  - `docs/reference/repository-layout.md`
  - `docs/how-to/run-the-gates.md`
  - `TODO/STATUS.md`
- **Acceptance gates:** `python backend/utilities/doc_load.py` before and after, and the split test on any page gaining a section. No application suite is required for a documentation-only closure. ESCALATE trigger 4 applies.
- **Oracle:** no clause of the engineering contract requires a generated artefact, a schema file, or a typed shape for a configuration file - checked clause by clause against the tree, not against this plan. The five clauses below are the ones that must move.
- **The clauses that change:**

 | Clause | What it says today | What it must say |
 | --- | --- | --- |
 | Guardrail #3 | Every persisted shape is declared as a schema before logic reads it, and every downstream artifact is generated from it | The producer declares and validates its own payloads in its own language. A configuration file this project authors needs no declared shape. Generation into a second language happens where a second language reads the bytes - today, nowhere |
 | Section 1a, second bullet | Schemas are generated from the models, the site's types from the schemas, and a drift gate fails on any difference | Deleted. Nothing generates and nothing drifts |
 | Section 9 | The contract drift gate must be green | Deleted from the list |
 | Section 10 | Hand-editing a generated artifact is an anti-pattern | Deleted - there are none |
 | Section 11 | Every configuration file and persisted surface is a model with a stamped version and a changelog | Scoped to persisted payloads a later run reads. A configuration file this project authors is out |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The amendment ships with row #1, not after it. CLAUDE.md section 0 requires a conflicting rule to be amended in the same change | Owner, CLAUDE.md section 0 |
 | 2 | Each guardrail that moves records who moved it and when, on the line that moved (CLAUDE.md section 1) | Fowler |
 | 3 | Guardrail #11 and Guardrail #12 are untouched. One protects a reader from a stranger's web page, the other protects the repository from itself | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Take a named exception for each row instead of amending the contract | Twelve exceptions to one rule is the rule being wrong | Twelve dated notes and a guardrail nobody believes | Fowler |
 | 2 | Amend the contract after the rows land | Leaves the repository in a state where its own contract forbids its own code | Nothing saved; it is a sequencing error | Owner |

## Section 14 - Row #13 - The entry path is one action taking a model file

- **Scope:** Delete the seven hand-copied blocks of fetch, verify, start and health spread across three workflows, collapse the three shell scripts into one, and let the composite action take a model file path instead of eight values a caller dug out of a fixed configuration.
- **Files touched:**
  - `.github/scripts/llama-cpp-pin.sh`, `install-llama-runtime.sh`, `fetch-model-runtime.sh` (three become one)
  - `.github/scripts/start-llama-server.sh` (its one-arm role dispatch and its limit echoes)
  - `.github/actions/model-server/action.yml`
  - `.github/workflows/measure.yml` (four copies), `validate.yml` (one), `idhazh-pipeline-tests.yaml` (one)
  - `.github/workflows/digest.yml`, `llm-council.yml` (their call sites, for the new input)
  - `backend/tests/workflows/_harness.py`
  - `docs/reference/ci-model-runtime.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, `shellcheck` on the merged script; CI - full suite, and one real dispatch of the pipeline test before the row closes.
- **Oracle:** every workflow that stands a model up does it through one action call, proved by grep finding no remaining inline fetch or health step; and the binary and weights that land on the runner are byte-identical to what lands today, proved by the digest checks that already run on both ends.
- **The count, corrected 2026-09-21:** only the nightly run and the council call the shared action. The benchmark workflow carries four copies of the block, the qualification workflow one and the pipeline test one - about 465 lines. Adding the three shell scripts (132), the action itself (195) and the start script (72), it is roughly 860 lines to install a binary, download a file and start a process.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The action takes a **model file path**, defaulting to the committed pointer. It reads one fixed configuration file today, which is the coupling that made three workflows write their own copy | Carmack |
 | 2 | The seven copies are deleted, not tidied. Per-workflow freedom to start a server differently is what produced four copies of one download | Carmack |
 | 3 | The three scripts become one. They were split so one caller could install the binary without weights; row #4 deletes that caller | Carmack |
 | 4 | The health check asks one endpoint. Asking three was belt and suspenders over a digest check that already pins the file | Owner ruling 2026-09-21 |
 | 5 | The weights digest check stays. It is the one step on this path that guards bytes rather than restating configuration | Carmack |
 | 6 | The candidate weights cache leaves the three dispatch workflows and stays in the nightly run and the council. A candidate is always a cache miss, so restoring it costs a fraction of a dispatch and buys nothing | Carmack |
 | 7 | **The cache key is the build tag plus a digest of the file listing** - one line per file, its name and its checksum, sorted. Fixed length whatever the file count, so a model needing three files moves nothing about the key's shape. The repository and the commit leave the key: once it names content, the address is redundant and including it throws away a valid multi-gigabyte entry when an upload moves a revision without moving a byte | Carmack |
 | 8 | **No prefix fallback, and no separate verify step.** A fallback hands a job an entry built for a different listing. Instead, per file: if it is there and its checksum matches, skip it; else download, check, rename. A half-filled directory then heals itself into one small download rather than a failed job, and the standalone verify pass is deleted because this one replaces it | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the three scripts and only drop the action's inputs | The split's stated reason is deleted by row #4, and the seven copies survive - which is the actual cost | About 465 lines left standing, and every future workflow copying an eighth time | Carmack |
 | 2 | Delete the composite action and inline its steps everywhere | That is the current state, and it is what this row exists to end | About 195 lines removed and roughly 400 added | Carmack |
 | 3 | Collapse the configuration action in too | It builds the configuration a dispatch runs on, which is a different job | About 50 lines, and one file with two answers | Fowler |

## Section 15 - Row #14 - The image benchmark goes, and two heavy wheels with it

- **Scope:** Delete the image-diffusion benchmark and its job, which is the only thing in the repository that needs two of the largest dependencies declared.
- **Files touched:**
  - `backend/utilities/bench_image.py`
  - `.github/workflows/measure.yml` (the image job and its dispatch target)
  - `pyproject.toml` (the extra that carries the two wheels)
  - `backend/tests/workflows/test_bench_targets.py`
  - `docs/reference/` pages naming the target
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite.
- **Oracle:** no file in the repository imports either wheel, and the dependency declaration no longer names them, proved by grep and by a clean install resolving without them. The census is the check.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | Timing image diffusion on a runner answers nothing about a news digest. It is the only reader of both wheels | Carmack |
 | 2 | The wheels leave the repository with it. An extra nobody installs is still a line somebody has to decide about | Carmack |
 | 3 | Guardrail #8 asks each dependency to name its beneficiary feature. When the feature goes, so does the dependency, in the same change | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep it as an operator tool outside the workflow | The tool is the dependency. Keeping one keeps both | The two wheels and the extra, for a measurement nobody has asked for | Carmack |
 | 2 | Delete the faithfulness scorer's wheels too | It has a live consumer - a qualification gate that decides publication | The gate, and a qualification that measures nothing. Out of scope here | Andre |

## Section 16 - Row #15 - The hosted span sink goes

- **Scope:** Delete the optional hosted trace viewer, its sink, its configuration knob and its dependency, keeping the local trace file the pipeline already writes with the standard library.
- **Files touched:**
  - `backend/idhazh/telemetry/sinks.py` (the hosted sink)
  - `backend/idhazh/telemetry/__init__.py`
  - `backend/idhazh/contracts/knobs/observability.py`
  - `backend/idhazh/stages/work.py`
  - `pyproject.toml` (the extra)
  - `backend/tests/` tests for the sink
  - `docs/` pages describing it
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'telemetry or trace or observability' -q`; CI - full suite.
- **Oracle:** a run still writes one trace line per span to the local trace file, byte-identical to today, and nothing in the repository can send a span anywhere else. The first half is the behaviour that must not change; the second is what the row removes.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The local trace file is the whole feature. The hosted viewer is a second path nobody's pipeline runs - continuous integration installs neither the extra nor a key | Fowler |
 | 2 | It also reads against the engineering contract's own words: logging is local by construction, with no log sink and no log service (CLAUDE.md section 1b) | Fowler |
 | 3 | A developer who wants a span tree drawn reads the local file. That is the cost, and it is named | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep it, since the extra is opt-in and unused | An unused second implementation is the thing that rots, and it is a sink pointed at a third party sitting in a repository whose contract says there is no sink | About 120 lines across four files, a knob, an extra, and a contradiction a reader has to resolve | Fowler |
 | 2 | Keep the sink interface and delete only the hosted implementation | An interface with one implementation is the implementation | About 40 lines kept for a shape with nothing behind it | Fowler |

## Section 17 - Row #16 - The thinking budget goes; the two-span call stays

- **Scope:** Delete the reasoning-token budget, which llama-server has no parameter for and this project invented. **Keep the two-request split**, which carries a second job the first draft of this row missed.
- **Corrected 2026-09-21 after the second advisory round.** The first draft deleted the split as well, on the stated ground that it existed only to apply the budget. The code says otherwise: a schema or grammar binds the decode from the very first token, and the first request deliberately strips the schema, the grammar and the token-probability request so the model is free to reason. Collapsing to one request applies the shape from token zero, so **a reasoning model cannot reason at all** - and it still returns a well-shaped summary, so nothing goes red. That is the exact silent failure this plan exists to avoid creating.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (`thinking_span`, `answer_span`, the budget arithmetic in the request bodies)
  - `backend/idhazh/stages/common.py` (the two-span caller)
  - `backend/idhazh/stages/two_calls.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/summarize.py`
  - `backend/idhazh/evals/qualify.py` (the context arithmetic that adds the budget)
  - `backend/idhazh/fingerprint.py`
  - `backend/idhazh/contracts/knobs/inference.py`
  - `backend/idhazh/contracts/judge_call.py`, `story_similarity_pair.py` (the span-count cells)
  - `config/models/` (the entries that declare a budget)
  - `backend/tests/` for each of the above
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'summarize or classify or judge or qualif' -q`; CI - full suite.
- **Oracle:** one reasoning call is one request, and the answer it returns satisfies the same schema it satisfies today - asserted against a recorded server response for a thinking entry and a non-thinking entry. What it cannot settle: how long a reasoning model now runs before it answers. That is a measurement, and plan 40's dispatch is where it is taken.
- **The finding:** llama-server carries no reasoning-budget parameter. `server_argv` spells no such option - `--reasoning-preserve` controls whether reasoning text is returned, not how much is produced. The budget is this project's own construction: one call is sent twice, once with the reasoning cap and once with the schema.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | A budget this project invented for a runtime that has no such parameter is this project's scaffolding, and it goes | Owner ruling 2026-09-21 |
 | 2 | **The split stays.** The first request exists to leave the decode unconstrained while the model thinks; the second puts the shape back for the answer. Deleting it would silently stop every reasoning model reasoning. Removing the budget alone is one line: the first request keeps an uncapped prediction count and its stop marker | Fowler and Andre, second round |
 | 3 | The risk that remains is named rather than guarded: a reasoning model now thinks until it stops on its own. Plan 40's dispatch measures what that costs, which is the experiment the owner asked for | Owner ruling 2026-09-21 |
 | 4 | The span-count cells on the two judge records stay, because there are still two spans | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the budget, delete only the typed field | The field is not the cost. The two-span call is, and it is two requests and a re-prefill for every reasoning item | About 250 lines kept, and one extra request a call | Carmack |
 | 2 | Wait for plan 40's dispatch before deciding | The dispatch measures what running without a budget costs. It cannot measure that while the budget is still applied | One dispatch, and a reading about the budget rather than the model | Andre |

## Section 18 - Row #17 - The utilities and evaluations nothing calls go

- **Scope:** Delete the command-line utilities with no caller anywhere, the evaluation paths with no consumer, and the plan-queue tooling that parses markdown a person wrote.
- **Files touched:**
  - `backend/utilities/` - the eleven with no code reference, confirmed by census before each deletion
  - `backend/utilities/plan_status.py` and its test
  - `backend/idhazh/evals/labels.py`, `backend/idhazh/contracts/label_row.py`, `backend/utilities/label_queue.py` and their tests
  - `backend/idhazh/evals/retrieval.py` and its test, plus the two configuration knobs only that test reads
  - `backend/idhazh/evals/qualify.py`, `backend/idhazh/evals/metrics.py`, `backend/idhazh/contracts/qualification.py` (five demoted score fields no gate reads)
  - `backend/tests/test_marks.py`
  - `docs/` pages describing each
- **Acceptance gates:** local - `python -m pytest backend/tests -q`; CI - full suite.
- **Oracle:** every deleted module has no importer and no workflow invocation, established by census **before** each deletion rather than after. The census is the check, and it must include `.github/` and `docs/` as well as the code, because a utility named only in a runbook still has a user.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | A one-shot measurement utility retires once its answer is written down. Re-taking the measurement costs writing the script again, which is the correct price for something run once | Fowler |
 | 2 | The human-label queue goes. It has zero committed rows and was run once; it returns as a short script the day somebody labels something | Andre |
 | 3 | The retrieval evaluation goes. Its only reader is its own test, it walks the growing committed archive - which CLAUDE.md section 13 forbids by name - and its bar is a date a person bumps to keep it green | Andre |
 | 4 | Five demoted score fields go **from the qualification report only**. See decision 7 | Andre |
 | 5 | The plan-queue tooling goes. It is tooling to read a file a person wrote, and an agent reads the file | Fowler |
 | 6 | What is lost is named, not waved away: nothing then measures whether archive search finds the right story. The replacement is a fixture of query and answer pairs, written the day search changes | Andre |
 | 7 | **The measuring functions are out of scope, and this is the row's hardest boundary.** Three of the measures the qualification report prints are not diagnostics anywhere else: they set the confidence line published beside an item every day, and they are the admission filter on the fine-tuning corpus. Measured over the committed days: taking the functions rather than the report fields would move 2,193 of 11,654 scored items across a confidence band, promote 2,100 of them to the highest band with nothing measured to justify it, and delete the disclosure sentence from 1,988 published items. **This row deletes report fields. It does not touch `backend/idhazh/evals/metrics.py`, `evals/score.py` or `corpus.py`** | Editor, second round |
 | 8 | The census in the oracle covers `frontend/` as well as `backend/`, `.github/` and `docs/`. One of these measures is read by a published console page | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the retrieval evaluation as the only search-quality measure | An evaluation whose input grows with the archive and whose bar is a hand-bumped date is a maintenance cost wearing a measurement's clothes | About 990 lines, and a test that goes red because somebody published a day | Fowler |
 | 2 | Delete the two counterweight score fields as well | A faithfulness floor with no counterweight rewards copying the source, which is the failure the counterweights exist to see | About 40 lines, and a quality signal that moves the wrong way | Andre |
 | 3 | Delete the commit-and-push script, also large | It has eight call sites and a test that drives the real script through race and rebase cases against real repositories. That is this project's own code being wrong, which is what the plan's rule keeps a check for | A retry loop in five workflows, none of them executable in a test | Fowler |

## Section 19 - Row #18 - The model's own template renders the prompt, not our copy of it

- **Scope:** Stop transcribing each model's chat template into configuration by hand. Ask the server to render the conversation through the model's own template, then send that rendered prompt the way we send one today.
- **Corrected 2026-09-21 after the second advisory round.** The first draft moved every call to the message-based endpoint. Three separate breaks were found and it would have been a trust-boundary breach: the check that refuses a marker family the sanitizer cannot strip reads our declared markers at configuration load, in every process, with no server running - and its proposed replacement cannot be built, because the server publishes its template as source code in which a marker is assembled by concatenation rather than listed. Only two markers are directly recoverable, and no template parser is a dependency here. The message endpoint also loses the literal grammar the judge posts, the first-token alternatives it reads, and moves the decode identity stamped on every committed row. A measurement on 2026-09-12 also found the template drops a marker when a turn is replayed as history, which re-reads about a hundred tokens an item - the exact regression the current design was changed to remove.
- **The shape that gets what the owner wants**: the server already exposes a route that applies the model's own template to a message list and returns the rendered prompt. Post there once, take the rendering, send it on the route production already uses. The hand transcription dies; the grammar, the first-token alternatives, the prompt splice, the decode stamp and the marker check all survive untouched.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/turns.py` (deleted)
  - `backend/idhazh/llm/server.py` (`render_prompt`, `continued_prompt`, `turn_markers`, `turn_markers_digest`, `the_render_agrees`, the completion payload builders)
  - `backend/idhazh/config.py` (the marker check finds the markers in the model's own template instead of in our file)
  - `backend/idhazh/stages/common.py`, `two_calls.py`, `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/fingerprint.py` (the envelope digest)
  - `config/models/` (every entry loses its turn block)
  - `backend/tests/contracts/test_turn_envelope.py`, `backend/tests/test_summarize.py`, `test_classify.py`
  - `docs/architecture/` pages describing the envelope
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'summarize or classify or judge or config' -q`; CI - full suite, and one real pipeline-test dispatch before the row closes.
- **Oracle:** the prompt the server receives, tokenised, is the same sequence for a committed model entry before and after - driven from a recorded server response so nothing touches the network. **And the prefix cache still serves the second call of an article**, asserted on the cached-token count the record already derives. The second half is the risk, and it is the half that can fail.
- **The finding:** the eight turn-envelope fields are a hand-copy of the model's own chat template. llama-server applies that template itself when told to, and the chat endpoint takes a message list. The constant for that endpoint is already in the code; production rewrites it to the raw-prompt endpoint and sends text we built. Copying a template by hand is why a new model needs its markers recorded, why they can be wrong, and why a startup check exists to compare our copy against the original.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The template is the model's, not ours. A configuration field that restates somebody else's file is the same mistake as a schema that restates a Pydantic model | Owner ruling 2026-09-21 |
 | 2 | **The transport does not change.** Production keeps the route it uses, so the grammar the judge posts, the first-token alternatives it reads, the two slot cells on the item ledger and the decode identity on every committed row are all unaffected | Fowler and Andre, second round |
 | 3 | **The trust boundary does not move.** The marker check keeps reading a plain dictionary at configuration load, in every process, with no server needed. The dictionary is now machine-recorded rather than typed, which is the whole point | Andre, Guardrail #11 |
 | 4 | The render-agreement check retires, because the fields were recorded from the template rather than transcribed. That is the check's own reason for existing | Andre |
 | 5 | This row no longer depends on the two-span call, which row #16 now keeps | Fowler |
 | 6 | Recording is a one-off per model, not a step in every run. A new model's entry is filled by asking the server once; the run reads the file | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep rendering ourselves | Every new model needs its markers transcribed by hand, they can be silently wrong, and a startup check exists solely to catch that | Eight configuration fields, the rendering machinery and the check, kept forever | Owner |
 | 2 | Do this before the Bonsai run | The new model's markers would have to be transcribed first, which is exactly the work this row deletes. Doing it first is better, and it is why this row is not last | Andre |
 | 3 | Keep the raw-prompt path for the judge only | Two prompt paths is the drift this project keeps finding in other places | About 80 lines kept, and one model family rendering differently from the rest | Fowler |

## Section 20 - Row #19 - One console route list, not nine

- **Scope:** Replace nine hand-written lists of the site's console routes, spread across nine test files, with one exported constant they all read.
- **Files touched:**
  - `frontend/tests/console-axis.spec.ts`, `console-chrome.spec.ts`, `console-model-rule.spec.ts`, `console-nav.spec.ts`, `console-polarity.spec.ts`, `console-readout.spec.ts`, `console-title.spec.ts`, `console-voices.spec.ts`, `console-window-claims.spec.ts`
  - one new exported constant beside them, or the existing route source if one can be read at test time
- **Acceptance gates:** local - `npm --prefix frontend run test:browser -- --project console`; CI - full suite.
- **Oracle:** every console route the site serves is visited by every spec that claims to cover all of them. **This check fails on the base tree today**, which is the defect: the site serves five console routes, three of those specs list three and two list four, so one route is visited by none of the five.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | Adding a console route is one edit, not nine. This is the same closed-world census rows #9 and #10 delete on the backend, one language along | Fowler |
 | 2 | The list is derived from what the site actually serves where that is readable at test time, and is a single exported constant otherwise | Fowler |
 | 3 | The row fixes the coverage hole it finds rather than preserving it. A spec that claimed to cover every route and missed one was not covering anything | Susan |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Correct the nine lists and leave them nine | Fixes today's hole and keeps tomorrow's. The tenth route repeats it | Nine edits now and nine again per route | Fowler |
 | 2 | Split the two very large console specs at the same time | A different question - one file answering many - and it belongs to its own row | A large refactor bundled into a small fix | Fowler |

## Section 21 - Row #20 - One commit call in the workflow that has four

- **Scope:** Collapse the four separate commit-and-push invocations inside the nightly workflow into one call that stages what that job produced.
- **Files touched:**
  - `.github/workflows/digest.yml`
  - `backend/tests/workflows/test_staged_paths.py`, `test_daily_commit_steps.py`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`; CI - full suite, and the nightly run's next dispatch watched to completion before the row closes.
- **Oracle:** the set of paths committed by a nightly run is identical before and after, asserted against the staged-path list rather than against a run. What it cannot settle: whether a single call is as resilient to a push race as four were - the script's own race handling is unchanged, and it is the script that handles the race, not the number of calls.
- **The finding:** the shared commit script has eight call sites across five workflows, and **four of the eight are in one file**. That is the same copy pattern row #13 removes from the server-start block, one directory along.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The script itself stays whole. It has real call sites and a test that drives it through race and rebase cases against real repositories, which is this project's own code being wrong | Fowler and Carmack, agreed |
 | 2 | Four calls in one file is the defect, not the script. Each stages a different set of paths at a different point in the job; where two can be one, they are | Carmack |
 | 3 | A call that must stay separate because its paths do not exist yet at the earlier point stays separate, and the row says which and why | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Rewrite the script to take an explicit mode argument | A real improvement to its shape - the mode is currently implicit in which of three variables are set, with three illegal combinations guarded by hand - but it is a structural change with no behaviour behind it and belongs in its own commit | A refactor of a 308-line script in a plan about deletion | Fowler |
 | 2 | Leave all four | The nightly job is the one that runs five times a day, so a redundant commit step is paid five times daily | Nothing to take | Carmack |

## Section 22 - Row #21 - One request builder, and the pipeline stops naming a server

- **Scope:** Replace the two request builders with one that speaks the widely-supported shape, move every call onto that route, and delete the decode-identity stamp rather than migrating it.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (both builders, the response parser, the stamp and its helper)
  - `backend/idhazh/llm/__init__.py`
  - `backend/idhazh/summarize.py`, `backend/idhazh/stages/common.py`, `two_calls.py`, `backend/idhazh/similarity/judge.py`, `backend/idhazh/stages/judge_shard.py`
  - `backend/idhazh/fingerprint.py` (the stamp leaves the run record)
  - `backend/idhazh/contracts/item_health.py` (the two llama-specific slot cells)
  - `backend/idhazh/contracts/` wherever the stamp is a field
  - `backend/tests/` for each
  - `docs/architecture/summarize/prompt.md`, `docs/architecture/contracts/determinism.md`
- **Acceptance gates:** local - `python -m pytest backend/tests -k 'summarize or classify or judge' -q`; CI - full suite, and one real pipeline-test dispatch before the row closes.
- **Oracle:** the same article, put through the pipeline before and after, produces a summary satisfying the same schema, with the constrained decode still refusing an off-schema reply - driven from a recorded server response. **And the endpoint is a configuration value**: pointing it at a different compatible server needs no code change, proved by a test that builds a request for a second address.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | One builder. Two shapes with a caller choosing between them is the drift this plan keeps finding elsewhere | Fowler |
 | 2 | The widely-supported shape is the one that survives. The pipeline should be able to point at a different server tomorrow, and naming one runtime in the request shape is what prevents that | Owner ruling 2026-09-21 |
 | 3 | **The decode-identity stamp is deleted - code, tests and documentation.** It was determinism scaffolding. This removes the only reason this row would have needed a migration: nothing downstream compares stamps once there are none | Owner ruling 2026-09-21 |
 | 4 | If a settings fingerprint is ever wanted it is written fresh over the values that affect the output, sorted, never over the shape of the request. Ten lines, the day somebody needs it | Owner ruling 2026-09-21 |
 | 5 | The code adapts to the new response shape rather than the row reporting a loss. The first-token alternatives are read from their new position; the judge's rules are sent as a schema instead of as literal grammar | Owner ruling 2026-09-21 |
 | 6 | Two llama-specific cells on the item record go: the slot number, which is always zero because every model runs one sequence, and the tokens-already-held reading, which the cached-token cells beside it already carry | Owner ruling 2026-09-21 |
 | 7 | The startup flag that enables prompt caching is unaffected. It is set when the server starts, not on each request, so only the per-request repetition of it goes | Carmack |
 | 8 | **The two-call design is not a constraint on this row.** A prompt rewrite may make it one call or three; the reuse-between-calls question belongs to that decision, not to this one | Owner ruling 2026-09-21 |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the native route and wrap it behind an interface | Keeps a second shape alive behind a name, and the interface is then shaped by the runtime it hides | About 80 lines, and a swap that still needs a new back-end written | Owner |
 | 2 | Migrate the stamp instead of deleting it | A migration for every change of shape is the tax this plan exists to remove, and the stamp answered a question nobody asks | A read-side migration and the stamp kept forever | Owner |
 | 3 | Keep the two slot cells by reading them another way | One is always zero. The other duplicates cells on the same row | About 20 lines for a column of zeros and a duplicate | Carmack |
