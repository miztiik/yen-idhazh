# Delete the scaffolding

**Last Updated**: 2026-09-21

**Level**: 5 (the generated contract layer is deleted whole, the model configuration stops being a typed shape, the startup probe that gates every run keeps one check of five, and three clauses of the engineering contract are amended to match)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Three habits have put about forty thousand lines between a person and a change they meant to make in one file. The repository generates 24,639 lines of JSON schema and 9,640 lines of TypeScript from them; three import statements in the whole site reach any of it, and where a shape is genuinely shared the site keeps its own hand-written copy and ignores the generated one. Naming one more llama-server option costs a typed field, a branch in a builder, a regenerated schema, a version stamp, a changelog line and a test - six edits before the file that exists to carry options can carry it. And the test suite spends most of its refusals asserting that somebody else's binary honours its own parameters, log format and response shape. None of it is load-bearing, and all of it is in the way. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** This binds every pipeline, not only the model surface. Owner ruling 2026-09-21. |
| Hard scope - in | Delete the generated contract layer whole - every JSON schema, every generated TypeScript file, both generators, the drift tests and the continuous-integration job that ran them - inlining by hand the three types the site actually imports. Make the model configuration plain JSON with no typed shape, no schema and no compliance tests. Delete the speculative-decoding draft head everywhere it reaches. Delete the runtime capability probe workflow, the recorded option listing it produced, and the test that read it. Let the model file name the llama build it needs, so the installer stops naming a repository. Cut the startup probe to the one check whose failure is silent. Take the replay dimension out of qualification, which no gate's verdict reads. Make both test pipelines commit what they produce. Delete the closed-world workflow censuses that turn a new job into a test edit. Delete the reader that parses the server's log. Amend the engineering contract in the same change that contradicts it. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | (1) Row #1 deletes the artefacts a drift gate protects; if the inline of the three live types cannot be made byte-equivalent to what the site compiles against today, stop. (2) Row #2 removes the typed model shape; if the turn-marker check cannot run against a plain dictionary, stop - that check is a boundary, not a preference. (3) Row #7 deletes fields that committed qualification payloads carry - the read-side migration ships in the same commit or the row stops. (4) Row #12 amends the engineering contract; it lands in the same pull request as the first row that contradicts it, never after. (5) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Delete the generated layer first, because every other row is smaller once it is gone. Then take the model configuration out of the type system, then the features and tests that only exist to police somebody else's software. Fowler rules the contract deletions, Carmack the runtime and workflow censuses, Andre the startup probe. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| The trust boundary: `refuse_markers_the_boundary_cannot_hold` (`backend/idhazh/config.py:80-116`), `_CHAT_CONTROL_FAMILIES` (`backend/idhazh/sanitize.py:63-97`), `untrusted_block`, `sanitize` | A model family whose turn markers no pattern recognises cannot load until a pattern is added. That cost is paid on the next new model | Nothing here. Guardrail #11 protects a reader from a stranger's web page; an agent surfaces it and never overrules it. Moving it is a decision taken on its own |
| The Pydantic models for payloads a run writes and a later run reads | The producer keeps validating its own output at the moment it writes it | This is not scaffolding - it is one program checking its own work in one language. The rule is about not re-checking somebody else's software. What goes is the **generated** layer on top, not the models |
| The weights digest check and the fail-loudly download | Two steps and one test stay in every fetch path | They guard bytes this project downloaded. A web error page saved as model weights is the failure they exist for |
| The ten qualification gates | Validate keeps its verdict | This plan changes how many times they are asked, never what they ask |
| `server_argv` as the one place an option is spelled | One function every server start goes through | Row #2 shrinks it to spelling a dictionary. Deleting it would make each caller spell options itself, which is more code, not less |

### The measurements this plan rests on

| Reading | Value | Where |
| --- | --- | --- |
| Generated JSON schema | 24,639 lines across 66 files | `schemas/` |
| Generated TypeScript | 9,640 lines across 66 files | `frontend/src/contracts/` |
| Import statements in the whole site that reach a generated file | 3 | `frontend/src/lib/server/config.ts`, `frontend/src/lib/server/host-fingerprint.ts` |
| Generated TypeScript files nothing imports | 62 of 66, about 8,700 lines | the same census |
| Shapes the site needs and keeps its own copy of | at least four - the day payload, the search index, the console band, the day metrics | `frontend/src/lib/day-shape.ts`, `assist/index.ts`, `console/band.ts`, `server/payload.ts` |
| Fields on the inference block that are only a llama-server option | 24 of 31 | `backend/idhazh/contracts/knobs/inference.py` lines 17-133 |
| Gates whose verdict changes when the replay count falls to one | none of ten | scores compute under `if repeat == 1` at `backend/idhazh/stages/qualify.py:529`; canaries run on shard 0 only |
| Draft-head surface | about 600 lines across contracts, argv builder, fetch script, four workflows and two model files | measured 2026-09-21 |
| Cost of a two-address dispatch that fails | 40 to 50 minutes | owner estimate 2026-09-21 |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The generated contract layer goes | - | A | PENDING | - | - | - |
| 2 | The model file is plain JSON | 1 | B | PENDING | - | - | - |
| 3 | The draft head goes | 1 | B | PENDING | - | - | - |
| 4 | The capability probe goes | - | A | PENDING | - | - | - |
| 5 | The installer stops naming a repository | 2 | C | PENDING | - | - | - |
| 6 | The startup probe keeps one check | 2 | C | PENDING | - | - | - |
| 7 | Qualification asks each article once | 1 | B | PENDING | - | - | - |
| 8 | Both test pipelines commit what they produce | 1 | B | PENDING | - | - | - |
| 9 | The benchmark workflow's closed-world tests go | 3,4 | C | PENDING | - | - | - |
| 10 | The workflow censuses go | 3,4 | C | PENDING | - | - | - |
| 11 | The server-log reader goes | - | A | PENDING | - | - | - |
| 12 | The engineering contract and the pages catch up | 1 | B | PENDING | - | - | - |
| 13 | The entry path is one script and one action | 2,3,4,5 | D | PENDING | - | - | - |
| 14 | The image benchmark goes, and two heavy wheels with it | - | A | PENDING | - | - | - |
| 15 | The hosted span sink goes | - | A | PENDING | - | - | - |

**Row #12 is not last.** The clauses it amends are contradicted the moment row #1 lands, and CLAUDE.md section 0 requires a conflicting rule to be amended in the same change. Its first task ships inside row #1's pull request; the rest of the documentation follows once the other rows are done.

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
 | 6 | The run's recorded identity hashes the whole options map. This is better than what it replaces, where an option outside a named list of five moved the output without moving the record | Fowler |

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
 | 2 | If it is wanted again it comes back as keys in a model file and nothing else, which row #2 makes possible | Owner ruling 2026-09-21 |
 | 3 | The two model files lose the field rather than being deleted. They are entries for a model, not for a draft head | Fowler |

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
- **Oracle:** all ten gates return the same verdict on a recorded payload with the replay dimension collapsed to one, gate by gate. Run it against the base tree first to confirm it can fail.
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
 | 3 | The trial directory is named for the model, which answers what the tree means without a lookup | Owner question 2026-09-21, ruled here |
 | 4 | One file an article on the day tree, not one file a day. A file an article means a re-run replaces exactly what it re-summarised | Fowler |
 | 5 | The collection is written only when a trial root is set, so the nightly run never grows it - a condition read from configuration | Fowler, Guardrail #6 |
 | 6 | It carries a retention window on the line that declares it (Guardrail #12) | Fowler |

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

## Section 14 - Row #13 - The entry path is one script and one action

- **Scope:** Collapse the three shell scripts that stand a model up into one, and let the composite action read the model file instead of being handed eight values a caller dug out of it.
- **Files touched:**
  - `.github/scripts/llama-cpp-pin.sh`, `install-llama-runtime.sh`, `fetch-model-runtime.sh` (three become one)
  - `.github/scripts/start-llama-server.sh`
  - `.github/actions/model-server/action.yml`
  - `.github/workflows/digest.yml`, `validate.yml`, `llm-council.yml`, `idhazh-pipeline-tests.yaml`, `measure.yml` (their call sites)
  - `backend/tests/workflows/_harness.py`
  - `docs/reference/ci-model-runtime.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/workflows -q`, `shellcheck` on the merged script; CI - full suite, and one real dispatch of the pipeline test before the row closes.
- **Oracle:** standing a model up is one action call with two inputs, and the binary and weights that land on the runner are byte-identical to what lands today - proved by the digest checks that already run on both. What it cannot settle: whether the merged script is easier to read; that is a judgement, and the line count is the only part of it that is a fact.
- **The count today:** 132 lines across three shell scripts, plus a 195-line action with eight inputs, plus a 72-line start script, plus a 50-line configuration action. About 450 lines to install a binary, download a file and start a process.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The three scripts become one. They were split so one caller could install the binary without downloading weights; row #4 deletes that caller, so the reason is gone | Carmack |
 | 2 | The action takes a token and a port. Everything else it needs is in the model file, which row #2 makes a plain dictionary one utility can read | Carmack |
 | 3 | The three draft inputs go with row #3 | Carmack |
 | 4 | The health check asks one endpoint. Asking three was belt and suspenders over a digest check that already pins the exact file | Carmack |
 | 5 | The weights digest check stays. It is the one step on this path that guards bytes rather than restating configuration | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the three scripts and only drop the inputs | The split's stated reason is deleted by row #4, so keeping it keeps a shape whose justification is gone | About 60 lines and two files a reader has to open to follow one download | Carmack |
 | 2 | Delete the composite action and inline its steps | Five steps re-spelled in each of five workflows | About 195 lines removed and roughly 400 added | Carmack |
 | 3 | Collapse the configuration action in too | It does a different job - it builds the configuration a dispatch runs on - and folding it in makes one thing that does two | About 50 lines, and a file with two answers | Fowler |

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
