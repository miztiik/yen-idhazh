# Lane A - the model file stops being a type

**Last Updated**: 2026-09-21

**Level**: 5 (the model configuration stops being a typed shape, a field leaves a persisted run record, the startup probe loses four checks of five, and two clauses of the engineering contract are amended to match)

Execute per docs/how-to/execute-a-plan.md: one owner, one worktree per pull request, rows in the order the Reckoner gives; Parallel N = 1, because every row in a pull request edits `backend/idhazh/llm/server.py` and two branches on that file is the churn this grouping exists to remove; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Naming one more llama-server option costs six edits across five files - a typed field, a branch in the argv builder, a regenerated schema, a version stamp, a changelog line and a test - before the file that exists to carry options can carry it. Eight turn markers are a hand-copy of each model's own chat template, a startup check exists largely to catch that copy being wrong, and four more startup checks re-ask facts already settled by a checksum or by a parser. None of it is load-bearing and all of it is in the way of standing a new model up. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** Owner ruling 2026-09-21. |
| Hard scope - in | Delete the draft-head fields from the model shape. Make the model configuration a plain mapping with no Pydantic model, no generated schema and no compliance test, keeping the flag spellings as declared tables and denying six keys the command line. Put a number on span one's prediction cap. Read the server address from the environment so the pipeline can point at another compatible server. Delete the reader that parses the server's log. Record each model's turn markers from its own template instead of transcribing them by hand. Cut the startup probe from five checks to one. Amend the two clauses of the engineering contract this plan contradicts, in the pull request that contradicts them. |
| Hard scope - out | See the table below. |
| Supersedes | Plan 39 rows 2, 6, 11, 16, 18, 21, the model-shape half of row 3, and the Guardrail #3 and section 11 clauses of row 12. Those rows are `COLLAPSED` in plan 39's Reckoner and are not executed from there. |
| Hands to Lane B | Plan 39 row 5 (the installer stops naming a repository) runs as Lane B's last row, behind row 13 and behind pull request A1 of this plan - it adds `<role>.runtime` to the model file, which the typed shape refuses until row 4 here lands. Plan 39 row 3's workflow half - a companion-file list, the fetch loop and the draft pass-through in `fetch-model-runtime.sh`, `action.yml`, `digest.yml`, `validate.yml` and `measure.yml` - is absorbed by row 13. The two log-format assertions at `backend/tests/workflows/test_model_server_jobs.py:446` and `:487` belong to plan 39 row 10, not to row 1 here. |
| ESCALATE triggers | (1) The marker check must keep running at configuration load, in every process, over a plain mapping, with no server. If the recorded markers cannot be checked that way, stop - that is Guardrail #11's control point, not a preference. (2) Row 3 deletes `ModelRef.draft`, and 6 of 31 committed `run.json` files carry it; the read-side line ships in the same commit or the row stops. (3) `MODELS_FILE_PATTERN` must survive byte-identical; if the model-file pointer cannot keep its grammar, stop. (4) Row 6 amends `CLAUDE.md`; it lands inside pull request A1, never after. (5) Any row that would raise a runner budget figure (Guardrail #2). (6) Pull request A2's evidence gate failing sends the work back to row 7's recording, not to the gate. |
| Chosen strategy | Two pull requests, split at the prompt path. A1 carries everything that cannot move a rendered prompt and needs no dispatch. A2 carries the markers, which is the only change here that can move one, so a moved prompt digest has exactly one candidate cause. Fowler rules the contracts, Carmack the runtime and the cap arithmetic, Andre the prompt and the evidence gate. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Moving the pipeline off llama.cpp's native completion route onto the message-shaped route (plan 39 row 21's original scope) | The request shape still names one runtime, so pointing at a server that speaks only the widely-supported shape needs a new request builder written. Row 2 here buys the address, not the shape | A plan of its own, priced against the measurement already taken: the message route re-renders the conversation, drops the generation prompt's empty reasoning block when a turn becomes history, and re-reads the whole label reply - a median 928 tokens and 74.9 s an item, p90 156.8 s, worst 318.5 s, and 25.6 to 39.8 minutes on a 20-item shard (measured 2026-09-21 over 518 items in `state/item-health`, days 2026-09-19 to 2026-09-21). It also loses the judge's literal grammar, its first-token alternatives, and the prompt splice both continuation paths depend on |
| `decode_digest`, `slot_id`, `kv_tokens_at_start` and `prefix_shared_with_previous` | Four cells stay on the item and judge records | They leave only with the transport that made them llama-specific. `decode_digest` is compared inside `inputs_changed` (`backend/idhazh/similarity/counting.py:220`), feeds the archive filename through the record stamp so deleting it renames every future archive file, and is in the header of two committed CSVs under `state/content-similarity-judge/scored-pairs/2026/09/`. Deleting it is a three-surface migration, not a deletion |
| The trust boundary: `refuse_markers_the_boundary_cannot_hold`, `_CHAT_CONTROL_FAMILIES`, `untrusted_block`, `sanitize` | A model family whose turn markers no pattern recognises cannot load until a pattern is added | Nothing here. Guardrail #11 protects a reader from a stranger's web page; an agent surfaces it and never overrules it |
| The Pydantic models for payloads a run writes and a later run reads | The producer keeps validating its own output at the moment it writes it | This is one program checking its own work in one language. What goes is the shape for a file a person authors, not the shape for a payload a machine wrote |
| The weights checksum and byte-count check | Two steps and one test stay in every fetch path | They guard bytes this project downloaded. A web error page saved as model weights is the failure they exist for |
| `server_argv` as the one place a flag is spelled | One function every server start goes through | Row 4 shrinks it to three declared tables and a loop. Deleting it would make each caller spell its own flags, which is more code, not less |
| The qualification path sending one chat request where production sends two spans | Qualification scores a decoding production does not perform on a thinking candidate | One row of its own: run one thinking entry through both transports on one dispatch and compare the two summaries. Until that reading exists, a qualification verdict on a thinking candidate is a verdict on the chat transport, and this plan says so rather than implying otherwise |

### What a change costs today

| Reading | Value | Where |
| --- | --- | --- |
| Edits to name one more llama-server option | six, across five files | a typed field, a branch in the argv builder, a regenerated schema, a version stamp, a changelog line, a test |
| Edits to name one more option after row 4 | two | the model file, and the key list. A third only when the flag spelling is not the key with hyphens |
| Inference keys set by all five committed model files | 11 of 29 | `config/models/`, censused 2026-09-21 |
| Inference keys set by exactly one committed file | 9 of 29 | same census. This is why direct indexing needs two lists, not one |
| Committed model files that set `max_think_tokens` | none of five | same census |
| Committed model files whose `turns.thinking_close` is set, so span one can ever run | 3 of 5 - `gemma-4-e4b-qat.json`, `gemma-4-e4b-qat-no-draft.json`, `qwen3.5-9b-q4km-thinking.json`. The live pointer `models/qwen3.5-9b-q4km.json` is not one of them | same census |
| Committed `run.json` files carrying `models.<role>.draft` | 6 of 31 | `state/`, censused 2026-09-21. This is the one read-side migration this plan owes |
| Turn markers derivable from the model's own rendering | 6 of 8 | `thinking_kwarg` is an input to the render; `thinking_close` is what the model writes, not what the template writes |
| Startup probe checks whose failure is silent | 1 of 5 | the render check, `backend/idhazh/llm/server.py:1212` |

## Section 0b - What this plan does, in one list

Eight rows, two pull requests. Read this before the tables.

1. Delete the reader that parses the model server's log to learn whether an optimisation engaged.
2. Read the server's base address from the environment, so the pipeline can point at another compatible server with no code change.
3. Delete the draft-head fields from the model shape, and add the one read-side line that keeps six committed run records loading.
4. Make the model file a plain mapping - no Pydantic model, no schema, no compliance test - keeping the flag spellings as three declared tables and denying six keys the command line.
5. Put a number on span one's prediction cap, on the three entries that can ever run one.
6. Amend Guardrail #3 and section 11 of the engineering contract, inside the pull request that contradicts them.
7. Record each model's turn markers from its own template. Two of the eight stay hand-typed, and both are checked.
8. Cut the startup probe to the one check whose failure is silent, and log the trained window beside the configured one.

## Section 1 - Status Reckoner

**Rows are grouped into two pull requests. A pull request is one worktree, one branch, one review.** Rows inside a pull request run in the order below, in that one branch.

| # | Row title | PR | Depends-on | Parallel-group | Status | Worktree | PR link | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The server-log reader goes | A1 | - | A | PENDING | - | - | - |
| 2 | The server address is a value the job sets | A1 | 1 | A | PENDING | - | - | - |
| 3 | The draft head goes from the model shape | A1 | 2 | A | PENDING | - | - | - |
| 4 | The model file is a plain mapping | A1 | 3 | A | PENDING | - | - | - |
| 5 | Span one gets a cap | A1 | 4 | A | PENDING | - | - | - |
| 6 | The engineering contract catches up | A1 | 4 | A | PENDING | - | - | - |
| 7 | The model's own template writes the markers | A2 | 6 | B | PENDING | - | - | - |
| 8 | The startup probe keeps the render check | A2 | 7 | B | PENDING | - | - | - |

### The two pull requests

| PR | Rows | Can it move a rendered prompt | What proves it | Dispatches |
| --- | --- | --- | --- | --- |
| **A1 - the model file stops being a type** | 1, 2, 3, 4, 5, 6 | no | the argv and the request body built from each of the five committed model files, against fixtures captured before any edit | none |
| **A2 - the model's own template writes the markers** | 7, 8 | **yes, and it is the only one here that can** | the turn-marker digest unchanged for all five files, then the evidence gate in section 1b | one to run the recorder, then the gate's pair |

**Why two and not one.** A moved prompt digest in a single branch would have two candidate causes - the untyped file and the recorded markers - and telling them apart costs a dispatch pair at 40 to 50 minutes an attempt (owner estimate 2026-09-21). A1 needs no dispatch at all, and A2's base is A1's merge commit.

**Why two and not four.** Rows 1, 2 and 5 are a few lines each and cannot reach the prompt path. A pull request of their own buys a smaller diff and costs a review cycle.

## Section 1a - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent one of these; it reads this section.**

### C1 - The model file (rows 3, 4, 5, 7)

`config/models/<name>.json`. No Pydantic model, no generated schema, no test of its contents. Read as a mapping.

**Two key lists, not one.** A required key must be present; its value may be null, and null means the flag is not emitted. An optional key may be absent, and absent means what null means. A missing required key raises at load naming the key. A missing optional key is the ordinary case - 9 of the 29 inference keys are set by one committed file out of five, so one list with direct indexing would break four files of five on the first request.

All eleven required keys are present in all five committed files today, so no committed file is edited to satisfy the list.

| Key group | Keys | Presence |
| --- | --- | --- |
| Read by this project's own code | `n_ctx`, `n_batch`, `n_ubatch`, `n_threads`, `temperature`, `top_p`, `seed`, `max_answer_tokens`, `request_timeout_minutes` | required |
| Emitted as a bare or inverted flag, so absence is ambiguous | `metrics`, `startup_warmup` | required |
| Everything else the argv builder spells | `cache_prompt`, `cache_ram`, `cache_type_k`, `cache_type_v`, `checkpoint_min_step`, `cpu_range`, `cpu_strict`, `ctx_checkpoints`, `flash_attention`, `jinja`, `load_mode`, `log_verbosity`, `n_parallel`, `n_threads_batch`, `poll`, `priority`, `reasoning_preserve`, `slot_prompt_similarity` | optional |
| Span one's prediction cap | `max_think_tokens` | required where `turns.thinking_close` is set, refused where it is not (row 5) |

Entry-level keys keep their current names and meanings: `id`, `repo`, `revision`, `file`, `sha256`, `byte_count`, `arch`, `inference`, `turns`. `<role>.runtime` arrives with Lane B's row 5 and is not declared here.

**Deleted from the file**: `declared_for` on both blocks, and `draft`. Both are removed from all five committed files in the same commit that stops reading them.

**The flag spellings survive as three declared tables. Only the types go.** There is no pass-through by key name for the keys already spelled: 18 of them map to a flag the key does not derive, and five need a branch a flag name cannot express. Deleting the type does not delete that mapping - it only removes the place a typo used to be caught - so the mapping is declared rather than branched.

| Table | Shape | Emit rule |
| --- | --- | --- |
| `FLAG_SPELLINGS` | key -> flag | emit the flag and `str(value)` when the value is not null |
| `SWITCH_SPELLINGS` | key -> (spelling when true, spelling when false) | emit one of the two when the value is not null |
| `PRESENCE_SPELLINGS` | key -> (flag, the boolean that emits it) | emit the flag alone when the value equals that boolean |

**The spellings are read out of the existing `server_argv` branches, one for one. This plan does not restate them, because a restated spelling is a second place for it to be wrong.** A key in none of the three tables and not denied below is emitted as `--<key with underscores turned to hyphens>` with its value; llama-server refuses an option it does not accept and names it, which is the loud failure this plan's rule asks for. `--model`, `--no-context-shift`, `--port` and the alias stay in code, because no key produces them.

**Six keys are denied the command line**: `temperature`, `top_p`, `seed`, `max_answer_tokens`, `request_timeout_minutes` and `max_think_tokens`. The first three are real llama-server flags under different spellings, so letting one reach the process gives this project two answers for one value - the per-request body and the server-wide default - with nothing saying which won, nothing raised and every word changed. The other three are not flags at all, so a pass-through would emit an option the binary refuses and the server would not start. The builder asserts at import that this set is disjoint from all three tables.

**`top_p` keeps an interval check at load**: above 0 and at most 1, raising and naming the key. It is the only key in the file carrying a real interval today (`backend/idhazh/contracts/knobs/inference.py:163-165`); `temperature` has a floor and no ceiling, and `seed` is a bare whole number. At `top_p` 0 the sampler still keeps one token, so the run decodes greedily; above 1 it truncates nothing. Neither is refused by the runtime, both change every word, and no cell reports it.

**What the published site reads out of this file**: `n_ctx`, at build time, through `frontend/src/lib/server/config.ts:939`, which parses JSON and declares its own one-field interface rather than importing a generated type. `frontend/src/lib/console/settings-moved.ts` reads `n_threads` and `n_batch` off the committed item-health row, not off this file. All three keys are on the required list, and that guarantee is the required list's second reason for existing. No site file changes in this plan.

**Read-side migration on the file: none, and none is written.** The file is read key by key - required keys by direct indexing, optional keys by membership - so a key no reader names is never looked at. A committed file still spelling `declared_for`, `draft` or a retired option loads and runs unchanged. There is no release window, no implementer and nothing to define.

### C2 - The turn markers, recorded not typed (row 7)

Eight keys under `<role>.turns`, keeping their current names, meanings and place in the file. What changes is who writes them.

**The recorder** is a `--record` flag on `backend/utilities/prove_the_entry.py`, which already loads the entry, already holds the endpoint and the timeout, and already posts to the template-applying route. It defaults to a dry run; a write flag rewrites the one named file in place, keys sorted, nothing else touched. A person runs it locally against a llama-server they started, once per model, and reads the diff before committing. It is not a workflow step: the chat template ships inside the weights, so the rendering is a property of the model rather than of the runner, and a job that edits tracked configuration and pushes is a second writer of a file a person owns.

Three posts to the template route, each carrying sentinel strings no template can contain, reading the rendered prompt back:

| Render | Body | What it settles |
| --- | --- | --- |
| R1 | a system turn, a user turn and an assistant turn, no thinking keyword | the turn frame, the seam, the reply opening |
| R2 | the user turn alone | isolates the system block by difference against R1 |
| R3 | R1 plus the thinking keyword set true | the thinking reply opening |

| Key | Source | The rule, or what catches it when wrong |
| --- | --- | --- |
| `turn_opening` | R1 | the bytes before each role word, with the role word written back as the role placeholder. Three turns with three role words make the substitution position unambiguous |
| `turn_closing` | R1 | the bytes that repeat after each turn's sentinel. Refused when empty - an empty seam joins two turns into one |
| `reply_opening` | R1 | the tail after the last turn closing. Refused when empty |
| `reply_opening_thinking` | R3 | the same rule. Refused when it equals `reply_opening` while the entry declares a `thinking_close` - the keyword did nothing and the entry claims a mode the template has not got |
| `system_role` | R1 against R2 | an extra opening-and-closing pair around the system sentinel is a turn of its own; the system sentinel inside the user's turn is the fold |
| `system_joiner` | R1 | under the fold, the bytes between the two sentinels. Null under a turn of its own, which is what the reader requires |
| `thinking_close` | **hand-typed** | a rendering of a fresh conversation never contains it - it is what the model writes, not what the template writes. A wrong one means span one never stops, decodes to the window, and the item lands `context_exceeded` or `model_timed_out` with `summary_finish_reason` of `length`. Loud, per item, committed |
| `thinking_kwarg` | **hand-typed, machine-confirmed** | a rendering cannot return a name that was never sent. The recorder posts R1 and R3 and refuses the recording when the two are the same bytes: a template that reads the name answers differently, one that does not cannot |

The recorder carries both hand-typed values through byte-identical from the file it is rewriting, prints one line each saying they were carried rather than recorded, and refuses to write a file where one is set and the other null - the pair rule the typed shape enforces today, which must live inside the recorder once row 4 deletes the model that enforced it.

**The claim this replaces.** Not "a person never types a marker". A person types two of eight, both are facts a rendered prompt cannot carry, and both are checked - one by the item's own decoding failing loudly, one by the recorder refusing a name the template does not answer to.

**The marker check does not move.** `refuse_markers_the_boundary_cannot_hold` still runs at configuration load, in every process, over a plain mapping, with no server. Guardrail #11 is untouched.

### C3 - The run's recorded inputs (row 4)

**`PipelineInputs` keeps its shape. Nothing is removed from it and nothing is retyped.** It lives at `backend/idhazh/contracts/fingerprint.py:32` - not in `qualification.py`, which plan 39 named - and it is persisted inside `RunRecord.inputs`, `QualificationShard.inputs` and `QualificationReport.inputs`, three committed payload families. Its four named integers - `n_ctx`, `n_batch`, `n_ubatch`, `n_threads` - are all on C1's required list, so they are read out of the mapping by name and direct indexing is safe.

What changes is one line inside each of the two canonical spellings: they enumerate C1's declared key lists in a fixed order and read an absent key as null, instead of enumerating a Pydantic model's fields. Today every field has a value because the type supplies one, so the spelling includes the nine keys four files omit; spelled over each file's own keys instead, those four files would produce a different string and the first run after this change would report that the runtime flags moved when nothing moved. Enumerating the declared lists costs nothing and removes that false alarm.

**Row 4 therefore does not touch `backend/idhazh/contracts/qualification.py`.** That file belongs to Lane C, and the collision plan 39 declared is gone.

### C4 - What closes the settings universe (row 4)

`NOT_DIGESTED` (`backend/idhazh/fingerprint.py:216-330`) is a closed set, and the closure is the only thing stopping a new option landing in no stamp with nothing saying so. `digested_inference_fields()` computes it from `InferenceConfig.model_fields` and `digested_model_fields()` from `ModelEntry.model_fields` and `TurnsConfig.model_fields`. Delete those shapes and the test passes over an empty set.

Four declared names replace `model_fields`, and they are the same names the loader reads with: `REQUIRED_INFERENCE_KEYS`, `OPTIONAL_INFERENCE_KEYS`, `REQUIRED_ENTRY_KEYS` (the surviving `ModelRef` fields plus `arch` and `turns`), and `TURN_MARKER_KEYS`. `ModelRef` stays a Pydantic model - it is a persisted payload inside the run manifest - so the entry-level universe is still mostly read off a type.

Four checks hold the closure, all over this project's own files:

| Check | What it catches |
| --- | --- |
| every inference key in every committed model file is in the universe | a misspelled option, and a new option nobody classified |
| every key in the three argv tables is in the universe | a flag added with no declaration beside it |
| every key in the universe is carried by `PipelineInputs` under its own name or a canonical spelling, or named in `NOT_DIGESTED` with a reason | an option that moves the words and reaches no stamp |
| `NEVER_ON_THE_COMMAND_LINE` is disjoint from the three argv tables | a second sampler default |

The first of these is why row 4 gives up less than plan 39 claimed: a misspelled option is caught in the suite, before a dispatch, rather than only at server start.

Row 3 removes the `draft` and `declared_for` entries from `NOT_DIGESTED` with their fields. `thinking_kwarg` stays, because it is one of the eight turn markers.

### C5 - The one read-side migration this plan owes (row 3)

Six of thirty-one committed `run.json` files carry `models.<role>.draft`, and the model that reads them forbids extra keys, so deleting the field refuses them - a release blocker under CLAUDE.md section 11. `ModelRef` gains the one line `without_retired_keys` (`backend/idhazh/contracts/base.py:614`) already serves at `day_metrics.py:519` and `run_manifest.py:297`, with the reason on the line and a test that parses a committed record carrying `draft`.

`declared_for` and `max_think_tokens` need no such line. Both sit inside `inference`, which becomes an untyped mapping, and an untyped mapping refuses no key. Twelve committed run records carry `declared_for` and six carry `max_think_tokens`; all keep reading.

### C6 - What runs before the first article (rows 7, 8)

Six checks stand in front of the first article. Four cost nothing and two are already paid.

| Check | Where | What it catches |
| --- | --- | --- |
| the turn-marker boundary check | configuration load, every process, no server | an entry whose markers a forged turn would survive (Guardrail #11) |
| direct indexing of every key this project reads | configuration load, every process, no server | a missing or misspelt required key. It raises naming the key |
| the weights checksum and byte count | the fetch step | a truncated download, an error page saved as weights, a revision that moved under a name |
| llama-server's own refusal | server start | an inference key this build does not accept. It names the key and does not start |
| the health check naming the weights that answered | the workflow, before anything measures | a server up on a different file, or not up |
| **the render check** (`backend/idhazh/llm/server.py:1212`) | in process, before item one | a turn envelope that does not render what this model's own template renders |

**The render check stays permanently.** A wrong `reply_opening` or `turn_opening` renders a prompt with no turn structure that the output shape still accepts, so the reply parses, the decode ends itself, the finish reason says `stop`, the word cap has not moved, and every summary that day is flat with nothing red. It is the only thing in the tree that catches it, and its cost is three requests and no decoding, under a second.

**What still reaches a reader with nothing red after this plan lands.**

| Failure | Why no cell sees it | What stands in for a check |
| --- | --- | --- |
| the shape-to-grammar conversion gets looser, so constrained decoding stops being the control an injection meets | a looser grammar accepts every good reply | the llama.cpp build is pinned to one release, its bytes are checksummed at fetch, and moving the pin is a reviewed commit. That is a review standing in for a measurement, and it is named here so nobody reads the absence of a test as an absence of risk |
| `n_ctx` larger than the window the weights were trained at | the reply is well shaped, the decode ends itself, the finish reason says `stop` | row 8 keeps the one request that reads the trained length and writes it beside the configured one as a log record, raised to a warning when the configured window is larger. It never refuses (owner ruling 2026-09-21). A committed cell for it waits until plan 39 row 1 lands, because before that a new field costs the six edits this plan exists to delete |
| a sampling value outside its useful range | nothing computes on it; the run record carries it for a person to read | `top_p` gets its interval back at load (C1). `temperature` and `seed` do not, and that is stated rather than implied |

### C7 - The engineering contract clauses that move (row 6)

| Clause | What it says today | What it must say |
| --- | --- | --- |
| Guardrail #3 | Every persisted shape is declared as a schema before logic reads it, and every downstream artifact is generated from it | The producer declares and validates its own payloads in its own language. A configuration file this project authors needs no declared shape; what it needs is declared key lists the loader and the stamp both read |
| Section 11 | Every configuration file and persisted surface is a model with a stamped version and a changelog | Scoped to persisted payloads a later run reads. A configuration file this project authors is out |

The section 1a, section 9 and section 10 amendments stay with plan 39 row 1, because they are about generation and drift, which this plan does not remove. Guardrail #11 and Guardrail #12 are untouched. Each clause that moves carries a dated line naming who moved it (CLAUDE.md section 1).

## Section 1b - The evidence gate on pull request A2

Row 7 changes the bytes handed to the model. Nothing else in this plan does. The gate is what proves it did not make the digest worse, and it is a gate rather than a row because a row can be marked done and a gate cannot be skipped.

**One input the base tree does not have.** The pipeline test seeds its article draw from the run id, so two dispatches read different articles and there are no pairs to compare. The gate needs one dispatch input - a draw seed, empty meaning the run id, which is today's behaviour. One input, one line, and without it the gate cannot exist. It ships in row 7.

**The two dispatches**: `.github/workflows/idhazh-pipeline-tests.yaml` on the commit A2 branched from, and on A2's branch head, same model file, same draw seed, separate destinations. The workflow already uploads what each case produced as a per-run artifact, so two dispatches are already two readable destinations and the gate does not wait for Lane C's committed summaries collection. Confirm when the row is picked up that the case output carries the summary payload per article and not only timings; if it carries only timings, add the summary write to the upload rather than waiting.

| What the machine asserts | Verdict |
| --- | --- |
| the turn-marker digest is the same on both sides | a difference fails the gate |
| the rendered-prompt digest and the chat-template digest are the same on both sides | a difference fails the gate |
| every planned article has the same failure code on both sides, or none on both | a difference fails the gate |
| the configured window, the output cap and the two budget cells are the same per item | a difference fails the gate |
| the count of articles whose summary text differs, and the character distance for each | reported, never a verdict. It ranks which pairs the person reads |

The first four cannot be moved by runner noise. The fifth is the half noise reaches, which is why it decides nothing.

**What a person reads**: six pairs - the dispatch plans two articles across three cases - worst difference first. **Pass** when the four machine assertions match and the person names no pair where the tip summary is worse: no entity present at the base and gone at the tip, no opening that describes the article instead of reporting it, no sentence lifted whole from the source's first line. **Fail** sends the work back to row 7's recording.

**Cost**: two dispatches at up to 140 minutes each, run one after the other; about 20 minutes of a person's reading (estimate, 2026-09-21); 40 to 50 minutes to re-dispatch on a fail (owner estimate 2026-09-21).

## Section 2 - Row #1 - The server-log reader goes

- **Scope:** Delete the reader that parses the model server's log to learn whether an optimisation engaged, and its enumerated states.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (`flash_attention_state` and its states)
  - `backend/tests/test_summarize.py`
  - `tests/fixtures/runtime/` (only the log captures nothing surviving reads)
- **Acceptance gates:** local - `python -m pytest backend/tests/test_summarize.py -q`; CI - full suite.
- **Oracle:** no reader of the server's log text survives except the ones producing the run's own cost figures, proved by a census across `backend/`, `frontend/src/`, `backend/utilities/` and `.github/`. What it cannot settle: whether the optimisation is engaged - after this row the runtime's own startup output is where a person looks.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | Whether an optimisation engaged is the runtime's business, and this project asked by parsing a log line at a raised verbosity | Carmack |
 | 2 | **The census runs before the deletion, not after.** `flash_attention_state` has no caller in the tree today, so "any console surface carrying the reading" is an empty set and no browser smoke is owed - but the row proves that rather than assuming it | Carmack and Fowler, verified 2026-09-21 |
 | 3 | The two log-format assertions in `backend/tests/workflows/test_model_server_jobs.py` are not about this reader. They check a workflow's log-matching step against committed captures, which is plan 39 row 10's subject | Carmack |
 | 4 | The error-body classifier stays. It sorts a failure into this project's own taxonomy | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the reader, drop the tests | A parser with no check on it goes wrong silently | About 20 lines kept | Carmack |
 | 2 | Delete the workflow's log-matching step too | It belongs to the file plan 39 row 10 owns, and splitting it across two branches is the churn this grouping removes | Nothing saved; it is a sequencing error | Carmack |

## Section 3 - Row #2 - The server address is a value the job sets

- **Scope:** Read the server's base address from the environment beside the port, so the pipeline can point at another compatible server with no code change. About ten lines.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (the default endpoint and the default health address)
  - `backend/tests/test_summarize.py`
- **Not touched:** the request shape, the response parser, `decode_digest`, `backend/idhazh/contracts/item_health.py`, `backend/idhazh/similarity/counting.py`, any contract module, any committed payload.
- **Acceptance gates:** local - `python -m pytest backend/tests/test_summarize.py -q`; CI - full suite.
- **Oracle:** with the variable unset the address is byte-identical to today's, and with it set every derived address - the completion route, the health route, the model list, the template route - moves with it, asserted in one test that reads all four. What it cannot settle: whether a different server would accept the request this project sends. It would not, today, and that is what the scope-out table prices.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The address is a process-boundary value, not a tunable, so it goes beside the port in the environment rather than into a configuration file - no contract field, no version stamp, no changelog entry (Guardrail #6, CLAUDE.md section 11) | Fowler |
 | 2 | One helper already derives every route from the base address, so one change moves all four | Fowler |
 | 3 | **The request shape does not move.** Pointing at another server that speaks the widely-supported shape needs a new request builder, and that is a transport decision with a measured cost, priced in the scope-out table and out of this plan | Fowler, Carmack and Andre, 2026-09-21 |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Put the address on the model entry | The address is where the server this job started is listening, which is a property of the job, not of the weights. A per-model address would be wrong the first time two jobs ran the same model | One key and a reader who has to work out which of two places wins | Fowler |
 | 2 | Move the request shape in this row | It re-renders the conversation and re-reads the label reply on every item: a median 928 tokens and 74.9 s, p90 156.8 s, worst 318.5 s, and 25.6 to 39.8 minutes on a 20-item shard (measured 2026-09-21, 518 items). It also loses the judge's literal grammar, its first-token alternatives and the prompt splice both continuation paths use | The measured throughput above, three broken readings, and a three-surface migration for `decode_digest` | Carmack and Andre |

## Section 4 - Row #3 - The draft head goes from the model shape

- **Scope:** Delete the draft-head configuration from the model shape and the argv builder, and add the one read-side line that keeps six committed run records loading.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/models.py` (the draft shape, its enumerated kinds, the entry field)
  - the module declaring `ModelRef` (the read-side line)
  - `backend/idhazh/llm/server.py` (the draft arguments)
  - `backend/idhazh/fingerprint.py` (its entry in the not-digested mapping)
  - `config/models/gemma-4-e4b-qat.json`, `config/models/gemma-4-e4b-qat-no-draft.json`
  - `backend/tests/test_summarize.py`, `backend/tests/test_fingerprint.py`
  - the documentation pages that describe it
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'summarize or fingerprint or model'`; CI - full suite. ESCALATE trigger 2 applies.
- **Oracle:** a committed `run.json` carrying `models.<role>.draft` parses after the change, asserted against one of the six real files; and no Python module or contract mentions a draft head, a speculation kind or a speculative argument, proved by census. The first half can fail and is why this is its own row. What it cannot settle: whether the workflow wiring is gone - that half is Lane B's, and the census closes again at its pull request.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | It is deleted rather than kept unused. A measurement on 2026-09-12 found it changes the output on nine articles of nine, so it was never a free speed-up | Owner ruling 2026-09-21 |
 | 2 | **The row splits at the seam its own scope carries.** The model-shape half runs here, because it edits the four files row 4 rewrites. The fetch half - a companion-file list, a download loop and an installer publishing each landed path - touches no contract module and runs in Lane B with row 13, which is already collapsing the fetch scripts | Carmack and Fowler, 2026-09-21 |
 | 3 | The census closes twice: here for the Python and contract surface, and again at Lane B's close, because the fetch half is what makes speculative decoding reachable again as configuration | Carmack |
 | 4 | The two model files lose the draft block. They are entries for a model, not for a draft head | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the row whole in Lane B | Lane A and Lane B would edit the model shape, the argv builder and the run fingerprint in two branches at once - three hand resolutions, two of them semantic rather than textual | Three merges nobody can check by eye, against one extra Reckoner line | Carmack |
 | 2 | Delete the field with no read-side line | Six of thirty-one committed run records carry it and the reader forbids extra keys, so the next build cannot read yesterday's record. CLAUDE.md section 11 names that a release blocker | A broken read of six committed payloads | Fowler |
 | 3 | Keep the argument builder and drop only the configuration | Leaves code nothing can reach | About 25 lines kept and a dead branch | Carmack |

## Section 5 - Row #4 - The model file is a plain mapping

- **Scope:** Delete the typed model configuration - the entry, the inference block and their validators - read the file as a mapping through declared key lists, and replace the argv builder's chain of branches with three declared spelling tables and a loop.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/models.py` (the entry and registry shapes, the rename refusals, the `declared_for` validators)
  - `backend/idhazh/contracts/knobs/inference.py` (deleted whole)
  - `backend/idhazh/config.py` (the loader, the served-role list, the entry list, the judge-weights rule, the `top_p` interval)
  - `backend/idhazh/llm/server.py` (`server_argv` reads the three tables; the request bodies read the mapping)
  - `backend/idhazh/fingerprint.py` (the two canonical spellings and the two digested-field functions read the declared lists)
  - `backend/idhazh/stages/common.py`, `two_calls.py`, `summarize.py`, `similarity/judge.py` (the readers of inference values)
  - `backend/idhazh/evals/qualify.py` (the one line that adds span one's cap to the context requirement)
  - `config/models/` (all five files lose `declared_for`)
  - `backend/tests/contracts/test_model_registry.py`, `backend/tests/test_summarize.py`, `test_classify.py`, `test_fingerprint.py`
  - `schemas/models-config.schema.json`, `frontend/src/contracts/models-config.ts` (deleted; the run-manifest and qualification-shard artefacts regenerate and are committed)
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'config or model or summarize or fingerprint or classify'`, then the contract export with zero drift; CI - full suite. ESCALATE trigger 3 applies.
- **Oracle, four arms, each able to fail:**
  1. **Golden argv and golden request body.** For each of the five committed model files, the built command line and the built request body equal fixtures **captured from the tree before any edit and committed**, argument for argument and key for key. Any wrong table entry for any key any committed file carries fails this.
  2. **An unknown key reaches the server.** A fixture entry carrying a key no table names emits it as a flag with its value and raises nothing.
  3. **A denied key never reaches the command line.** A fixture setting all six denied keys produces an argv containing none of them, and a request body from the same mapping carrying the three sampling values.
  4. **Direct indexing bites.** A fixture missing `n_ctx` raises at load naming `n_ctx`; a fixture with a zero cap produces a span one asking for zero tokens. **The second half fails on the base tree**, where zero reads as uncapped, which is the proof this is an oracle and not a snapshot.

  What it cannot settle: whether a misspelled option is caught. It is - by the universe check in C4, in the suite, before a dispatch - but not by these four arms.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Anything that crosses from the model file to llama-server gets no type, no enumerated choice, no schema and no compliance test.** The file is a mapping; the builder spells it; the runtime refuses what it does not accept and names it | Owner ruling 2026-09-21 |
 | 2 | **The flag spellings survive as three declared tables.** Eighteen are not a mechanical transform of the key and five need a branch a flag name cannot express, so the mapping is the one thing here this project genuinely cannot derive and must record. Deleting the type does not delete it. With the tables, naming one more option is two lines | Carmack and Fowler, 2026-09-21 |
 | 3 | **Two key lists, not one.** Nine of twenty-nine inference keys are set by one committed file of five, so a single required list with direct indexing breaks four files of five on the first request | Fowler, censused 2026-09-21 |
 | 4 | **Six keys are denied the command line.** Three are real llama-server flags under different spellings, so a pass-through gives this project two answers for one sampling value with nothing saying which won. Three are not flags at all and would stop the server | Carmack |
 | 5 | **`top_p` keeps an interval check at load - above 0, at most 1.** It is the only key in the file carrying a real interval, the runtime accepts a wrong value, every word changes, and no cell reports it. Two comparisons are the cheapest instrument for the one failure class this plan says must fail loudly, written where the loader already raises on a missing key. This is a named exception to decision 1 | Andre, on the owner's authorization of this plan |
 | 6 | **`PipelineInputs` keeps its shape.** Removing its four named integers would cost a read-side migration on three committed payload families and would make the change record name a string where it names a knob today. The two canonical spellings enumerate the declared key lists in a fixed order, which reproduces today's strings byte for byte for all five files and removes a false alarm on the first run after | Fowler |
 | 7 | **The declared key lists close the settings universe.** The closed-set test computes its universe from a Pydantic model's fields today; deleting the shapes would leave it passing over an empty set, and that test is the only thing stopping a new option landing in no stamp with nothing saying so | Fowler |
 | 8 | **The model-file pointer keeps its grammar, byte-identical.** The loader joins rather than checks and says so on the line, so the grammar is the only thing ruling out a traversal, an absolute path and a Windows separator. Decision 1 is about the file's contents, never about the path to it (Guardrail #11) | Fowler |
 | 9 | **The judge-weights rule survives as a loader check over the mapping.** No server is started for a judge entry, so one naming different weights decodes on the summariser's weights while every verdict is recorded under a model that never saw the pair, and nothing raises. Four lines, beside the marker check | Fowler |
 | 10 | `declared_for` is deleted. It was refused unless it equalled a digest already in the same object, so it carried no information. The rename refusals go with it - they are migration scaffolding for renames that already landed, and no committed file carries an old spelling | Fowler |
 | 11 | **The reader indexes required keys directly and compares against null explicitly.** Two defects exist today and both get worse untyped: a cap of zero reads as uncapped, and a missing turn-marker key renders an anonymous turn. Direct indexing raises at load and names the key. This costs nothing | Andre |
 | 12 | The served-role list and the entry list become declared values in the loader. They read the distinction off a type annotation today, which an untyped file cannot carry, and the annotation evaluates to one served role | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep typed fields for the values this project's own code reads | Two ways to declare a value and a rule about which wins. The code that reads them can read a key | About 60 lines kept, and a reader who cannot tell which half of the file they are in | Owner ruling 2026-09-21 |
 | 2 | Emit every key mechanically as its own name with hyphens, with no tables | Eighteen of twenty-four spellings are not the key, so the server refuses most of them and does not start. The three sampling keys are worse: they are accepted, and set a second server-wide default | A pipeline that does not start, or one that samples twice | Carmack |
 | 3 | Validate option names against a recorded listing of what the build accepts | Rebuilds the thing plan 39 row 4 deletes, at the same cost and for the same reason | A recording per build, and a pin that cannot move without a dispatch | Carmack |
 | 4 | Fold the four named integers on the run record into one canonical string | Three committed payload families need a read-side migration, and the change record stops naming which knob moved | A migration on three families, and a worse record | Fowler |
 | 5 | Keep the schema and generate it from whatever keys the file holds | A schema derived from the file it validates passes by construction | About 30 lines for a check that cannot fail | Fowler |

## Section 6 - Row #5 - Span one gets a cap

- **Scope:** Delete the invented framing and the null path around span one's prediction cap, and put a number on it for the three entries that can ever run one.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (the two request bodies and the span builder)
  - `backend/idhazh/stages/common.py` (the parameter and its default of zero)
  - `backend/idhazh/evals/qualify.py`, `backend/idhazh/summarize.py` (the two context sums)
  - `backend/idhazh/fingerprint.py` (the term in the sampling spelling)
  - `config/models/gemma-4-e4b-qat.json`, `gemma-4-e4b-qat-no-draft.json`, `qwen3.5-9b-q4km-thinking.json`
  - `backend/tests/test_summarize.py`, `test_classify.py`, `test_fingerprint.py`
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'summarize or classify or judge or fingerprint'`; CI - full suite.
- **Oracle, three parts:**
  1. For all five committed model files, the request body posted by each path is byte-identical before and after, except for the cap on the three thinking entries. This fails if any read site was doing something the null path was hiding.
  2. A thinking entry still makes **two** requests and a non-thinking entry still makes **one**, driven from a recorded server response. This fails if the split is collapsed.
  3. Span one's request carries a stop marker and no output shape; the answer span carries the shape. This fails if the shape or the alternatives request leaks into span one.

  What it cannot settle: how long a reasoning model runs before it answers under the new cap. Plan 40's dispatch is where that reading is taken, and it is what would overturn the estimate below.
- **The cap, and the arithmetic in one line:**

 `floor(((shard_timeout_minutes - shard_wrap_up_minutes) * 60 / items_a_shard - worst_measured_summary_seconds) * slowest_measured_decode_rate)` = `floor((564 - 376.2) * 3.30)` = 620, **set at 600** for a round figure with slack an item.

 | Input | Value | Measurement or estimate |
 | --- | --- | --- |
 | shard timeout | 200 min | measurement - `config/idhazh.json`, read 2026-09-21 |
 | shard wrap-up | 12 min | measurement - same file |
 | items a shard at a full run | 20 | derived from the safety ceiling of 80 over four shards |
 | per-item budget | 564 s | derived |
 | worst summary time on the newest committed day | 376.2 s (median 96.5, p95 263.6) | measurement - `state/item-health/2026/09/21.csv`, 74 timed rows of 80 |
 | slowest summary decode rate, same day | 3.30 tok/s (median 4.33, p95 5.33) | measurement - same file |
 | span one's decode rate | assumed equal to the above | **estimate.** No committed entry has ever run a span one, because the live pointer's thinking close is null. Plan 40's dispatch is the measurement that would overturn it |

- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The key stays; the invented framing and the null path go.** The cap is not a parameter this project invented - it is llama.cpp's own prediction cap applied to the first span, and the file's own comment names it as such. What this project invented is the word "budget". Deleting a cap nobody is using is free; deleting the **ability** to cap costs exactly when plan 40 puts a reasoning model behind it. After row 4 the file is a mapping, so keeping it costs one key and zero types - no field, no schema, no stamp, no changelog | Carmack, Fowler and Andre, 2026-09-21. **This reverses the owner ruling of 2026-09-21, whose stated premise was that the runtime carries no such parameter** |
 | 2 | **The split stays.** Span one exists to leave the decode unconstrained while the model reasons; span two puts the shape back for the answer. A collapsed split applies the shape from the first token, so a reasoning model cannot reason and still returns a well-shaped summary, with nothing red | Fowler and Andre |
 | 3 | **The null path is deleted, which kills the zero defect by construction.** Zero means zero tokens, minus one means uncapped in llama.cpp's own spelling, and absent raises at load naming the key. The parameter default of zero in the shared caller goes with it, and so does the trap where a caller that forgets the argument decodes a zero-token thought and still returns a well-shaped summary | Andre |
 | 4 | **This changes nothing that runs today.** No committed model file carries the key, and the live pointer's thinking close is null, so the three entries that gain a number are three candidates rather than production | Andre, censused 2026-09-21 |
 | 5 | **This is a cost priced, not a budget raised.** The shard timeout is this project's own number in this project's own configuration, so it is a cost to move. The six-hour job kill is GitHub's and cannot move (Guardrail #2). Twenty items each allowed to run to the per-request timeout is 7 h 22 m, which GitHub kills - so an uncapped span one on a 20-item shard is a design that does not fit, and the cap is the design that does. No row here asks for a larger figure of either kind | Carmack |
 | 6 | The span-count cells on the two judge records stay, because there are still two spans | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete the key outright, as plan 39 row 16 said | Its premise - that the runtime has no such parameter - is wrong, and it removes the only lever that bounds span one without a code change (Guardrail #6). The hazard it leaves is real: 20 items each running to the per-request timeout is 7 h 22 m against a 6 h kill | One dictionary key saved, against a design that does not fit the day plan 40 runs a reasoning model | Carmack |
 | 2 | Set the cap at 1,800 tokens | Wrong by a factor of three. 1,800 tokens at the slowest measured decode rate is 545 s of decoding alone, against a 564 s per-item budget whose worst measured item already spends 376 s. Twenty such items is 307 minutes, past the 200-minute shard timeout | A shard the run cancels | Carmack |
 | 3 | Keep the budget and delete only the typed field | Leaves an unreachable branch in three files and a parameter default of zero that decodes nothing | About 40 lines and one trap | Andre |
 | 4 | Wait for plan 40's dispatch before setting a number | The dispatch measures a model with no cap applied, which is already what runs, so it would return a reading about nothing. A number set now is an estimate that names what would overturn it (Guardrail #10) | One dispatch, and a reading about nothing | Andre |

## Section 7 - Row #6 - The engineering contract catches up

- **Scope:** Amend the two clauses of the engineering contract that rows 3, 4 and 5 contradict, inside the pull request that contradicts them.
- **Files touched:**
  - `CLAUDE.md` (Guardrail #3, section 11)
  - `docs/architecture/contracts/schemas.md` (the model-configuration paragraphs only)
  - `docs/reference/repository-layout.md` (the `config/models/` line)
  - `TODO/STATUS.md`
- **Acceptance gates:** `python backend/utilities/doc_load.py` before and after, and the split test on any page gaining a section. This row is not a documentation-only closure - it ships inside pull request A1 and rides its suite. ESCALATE trigger 4 applies.
- **Oracle:** no clause of the engineering contract requires a declared shape, a generated schema or a stamped version for a configuration file this project authors - checked clause by clause against the tree, not against this plan. What it cannot settle: whether the amended clause is the right rule. That is section 0's question and the owner answers it by authorizing this plan.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The amendment ships with row 4, not after it. CLAUDE.md section 0 requires a conflicting rule to be amended in the same change | Owner, CLAUDE.md section 0 |
 | 2 | Only Guardrail #3 and section 11 move here. Section 1a, section 9 and section 10 are about generation and drift, which this plan does not remove, so they stay with plan 39 row 1 | Fowler |
 | 3 | Each clause that moves carries a dated line naming who moved it (CLAUDE.md section 1) | Fowler |
 | 4 | Guardrail #11 and Guardrail #12 are untouched. One protects a reader from a stranger's web page, the other protects the repository from itself | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Take a named exception for each row instead of amending the clause | Three exceptions to one rule is the rule being wrong | Three dated notes and a guardrail nobody believes | Fowler |
 | 2 | Amend after the rows land | Leaves the repository in a state where its own contract forbids its own code | Nothing saved; it is a sequencing error | Owner |

## Section 8 - Row #7 - The model's own template writes the markers

- **Scope:** Stop transcribing each model's chat template into configuration by hand. Ask the server to render a known conversation through the model's own template, derive six of the eight markers from the rendering, and carry the other two through with a check on each.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/turns.py` (deleted; the eight names become a declared list)
  - `backend/idhazh/llm/server.py` (the marker readers, the envelope digest, the two prompt builders)
  - `backend/idhazh/config.py` (the marker check reads the mapping)
  - `backend/idhazh/fingerprint.py` (the envelope digest reads the declared list)
  - `backend/utilities/prove_the_entry.py` (the record flag)
  - `config/models/` (all five files, re-recorded)
  - `.github/workflows/idhazh-pipeline-tests.yaml` (the draw-seed input the evidence gate needs)
  - `backend/tests/contracts/test_turn_envelope.py`, `backend/tests/test_summarize.py`, `test_classify.py`
  - `docs/architecture/` pages describing the envelope
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'summarize or classify or judge or config or turn'`; CI - full suite; **and the evidence gate in section 1b before the pull request closes.** ESCALATE triggers 1 and 6 apply.
- **Oracle:** the turn-marker digest is unchanged for all five committed model files after re-recording - a local assertion against the hand-typed values, needing no server. **And the prompt cache still serves the second call of an article**, asserted on the cached-token count the item record already derives, which is where the evidence gate's dispatch earns its cost. The first half proves the recording is right; the second is the half that can fail. What it cannot settle: whether the recorder would work on a model family none of the five committed files uses - that is found the day one is added.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The template is the model's, not ours. A configuration field that restates somebody else's file is the same mistake as a schema that restates a Pydantic model | Owner ruling 2026-09-21 |
 | 2 | **The transport does not change.** This project keeps building the prompt and posting it to the route it uses, so the judge's literal grammar, its first-token alternatives, the two continuation splices and the decode identity on every committed row are all unaffected | Fowler and Andre |
 | 3 | **The trust boundary does not move.** The marker check keeps reading a plain mapping at configuration load, in every process, with no server. The mapping is now machine-recorded rather than typed, which is the whole point | Andre, Guardrail #11 |
 | 4 | **Six of eight are derived; two are typed and both are checked.** `thinking_kwarg` is a variable name inside somebody else's template source and is an input to the render rather than an output of it. `thinking_close` is what the model writes, not what the template writes, so a rendering of a fresh conversation never contains it. Plan 39's claim that all eight are derivable is corrected here | Carmack and Andre, 2026-09-21 |
 | 5 | **The render check is not retired.** It is repointed at the recorded mapping. A derived value that was derived wrongly renders a prompt the model's own template does not render, and nothing else in the tree sees that | Andre |
 | 6 | Recording is a person's local command, once per model, against a server they started - not a workflow step. The template ships inside the weights, so the rendering is a property of the model rather than of the runner, and a job that edits tracked configuration and pushes is a second writer of a file a person owns | Carmack |
 | 7 | The recorder refuses rather than guesses: an empty seam, an empty reply opening, a thinking opening equal to the plain one while the entry declares a thinking close, and a thinking keyword the template does not answer to are each a refusal with the key named | Carmack and Andre |
 | 8 | The draw-seed dispatch input ships in this row, because the evidence gate cannot exist without it and no other row needs it | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep transcribing by hand | Every new model needs eight markers typed, they can be silently wrong, and a startup check exists largely to catch that | Eight fields typed per model, forever | Owner |
 | 2 | Move to the message-shaped route so the server renders from a message list | It re-renders the conversation, drops the generation prompt's empty reasoning block when a turn becomes history, and re-reads the whole label reply: a median 928 tokens and 74.9 s an item, and 25.6 to 39.8 minutes on a 20-item shard (measured 2026-09-21, 518 items). It also has no prompt key for either continuation splice to extend, which collapses the two-span split row 5 exists to keep | The measured throughput above, the judge's grammar and alternatives, and every reasoning model silently not reasoning | Carmack and Andre |
 | 3 | Derive all eight by parsing the template source the server publishes | The source assembles a marker by concatenation rather than listing it, only two are directly recoverable, and no template parser is a dependency here. Parsing a reasoning close out of the replay path would record a defect: a measurement on 2026-09-12 found this template drops a marker on replay | A template-language parser as a dependency, and a recorded marker copied from a defect | Carmack |
 | 4 | Run the recorder as a nightly step | It would edit tracked configuration and push, for a value recorded once per model rather than once per run | A second writer of a file a person owns | Carmack |

## Section 9 - Row #8 - The startup probe keeps the render check

- **Scope:** Reduce the startup probe from five checks to the one whose failure is silent, and log the trained window beside the configured one as an observation.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (the four deleted predicates and the weights-header parser)
  - `backend/utilities/prove_the_entry.py`
  - `backend/tests/test_summarize.py`, `backend/tests/test_classify.py`
  - `docs/architecture/contracts/determinism.md`
- **Acceptance gates:** local - `python -m pytest backend/tests/test_summarize.py backend/tests/test_classify.py -q`; CI - full suite.
- **Oracle:** a model file whose turn envelope disagrees with the weights' own chat template is still refused at start, driven from a recorded server response so nothing touches the network; and a configured window larger than the trained one produces a warning record naming both numbers and does not refuse. What it cannot settle: whether a summary is good - the probe never measured that.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Keep the render check, permanently.** A wrong reply opening or turn opening renders a prompt with no turn structure that the output shape still accepts: the reply parses, the decode ends itself, the finish reason says stop, the word cap has not moved, and every summary that day is flat with nothing red. It is the only thing in the tree that catches it. Plan 39's "then to none" clause is deleted | Andre |
 | 2 | Delete the output-shape check. A reply that breaks the shape fails at the parser, on that article, with a named failure | Andre |
 | 3 | Delete the prefix-cache check. It guards a speed reading, not an output | Carmack |
 | 4 | **Keep reading the trained window and write it beside the configured one as a warning record. It never refuses** | Owner ruling 2026-09-21 |
 | 5 | Delete the architecture check and the weights-header parser with it. The weights checksum already pins the exact file, so reading a string out of its header to compare with a string we typed is a second check of the same fact | Carmack |
 | 6 | A committed cell for the trained window waits until plan 39 row 1 lands. Before that a new field costs the six edits this plan exists to delete; after it, one line. What the deferral costs is named: the run log says it on the day, and nothing committed says it afterwards, so a person cannot ask last Tuesday's run whether its window was too big | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete all five | The render check is the only one whose failure is silent, and the rule this plan runs on is that a mistake must fail loudly | About 25 more lines removed, and a wrong turn envelope reaching readers as flat summaries | Andre |
 | 2 | Keep the render check but retire it once the markers are recorded | A derived value can be derived wrongly, and the check is what sees that. Retiring it on the strength of the recording is retiring the only thing that audits the recording | About 40 lines, and a recorder nobody checks | Andre |
 | 3 | Refuse a configured window larger than the trained one | Owner ruling 2026-09-21: it is an observation, not a refusal | A run that will not start on a window a person chose on purpose | Owner |
