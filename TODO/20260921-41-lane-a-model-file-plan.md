# Lane A - the model file stops being a type

**Last Updated**: 2026-09-21

**Level**: 5 (the model configuration stops being a typed shape, a typed block inside a committed run record is retyped, the startup probe loses four cases of five, the turn block leaves the repository, and two clauses of the engineering contract are amended to match)

Execute per docs/how-to/execute-a-plan.md: one owner, one worktree per pull request, rows in the order the Reckoner gives; Parallel N = 1, because every row edits `backend/idhazh/llm/server.py` and two branches on that file is the churn this grouping exists to remove; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Naming one more llama-server option costs six edits across five files. Thirty inference keys carry names this project invented for options llama-server already names, and nineteen of the thirty exist for no other purpose than to be translated back. Eight turn markers are a hand-copy of each model's own chat template, and a startup check exists to compare our copy against the original. A run-identity closure of about 190 lines has no production caller at all. None of it is load-bearing and all of it is in the way of standing a new model up. |
| The rule | **A validator earns its place where this project's own code is the thing that could be wrong. Everywhere else the producer writes its file, the consumer reads it, and a mistake fails loudly at the moment it is made.** Owner ruling 2026-09-21. |
| Hard scope - in | Delete the reader that parses the server's log. Delete the decode stamp whole, and the dead run fingerprint with it. Delete the draft-head fields. Delete both decode caps and the arithmetic that reconciled them. Make the model file carry llama-server's own flag spellings in a server block, with a request block beside it for the four values that are not server flags - which deletes the translation tables, the deny list and the import-time assertion together. Delete the run-identity closure, which has no production caller. Derive each model's turn markers from its own template at server start, holding them in memory, which deletes the turn block, its eight keys and the check that audited our copy of it. Amend the two clauses of the engineering contract this plan contradicts, in the pull request that contradicts them. |
| Hard scope - out | See the table below. |
| Supersedes | Plan 39 rows 2, 6, 11, 16, 18, 21, the model-shape half of row 3, and the Guardrail #3 and section 11 clauses of row 12. Those rows are `COLLAPSED` in plan 39's Reckoner and are not executed from there. |
| Hands to Lane B | Plan 39 row 5 (the installer stops naming a repository) runs as Lane B's last row, behind row 13 and behind pull request A of this plan - it adds `<role>.runtime` to the model file, which the typed shape refuses until row 5 here lands. Plan 39 row 3's workflow half is absorbed by row 13. The two log-format assertions at `backend/tests/workflows/test_model_server_jobs.py:446` and `:487` belong to plan 39 row 10, not to row 1 here. |
| ESCALATE triggers | (1) Row 7 moves the turn-marker boundary check from configuration load to server start. It must still run in every process that decodes, before the first article, and refuse identically. If it cannot, stop - that is Guardrail #11's control, and only its position moves. (2) Row 5 retypes `ModelRef.inference`, which all 34 committed `run.json` files embed; the run manifest's version stamp and changelog line ship in the same commit or the row stops. (3) Row 3 deletes `ModelRef.draft`, which 6 committed run records carry; the read-side line ships in the same commit or the row stops. (4) Rows 2 and 4 remove columns from committed ledgers; each uses that ledger's retired-cell mechanism, and where none exists the row builds one rather than rewriting committed data by hand. (5) `MODELS_FILE_PATTERN` must survive byte-identical. (6) Row 6 amends `CLAUDE.md`; it lands inside pull request A, never after. (7) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | Two pull requests, split at the prompt path. A carries everything that cannot change a rendered prompt. B carries the markers, which is the only change here that can, so a moved prompt has exactly one candidate cause. Fowler rules the contracts, Carmack the runtime, Andre the decode surface. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 1.` |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| Moving the production two-call path onto the message-shaped chat route | The pipeline keeps speaking llama-server's own request shape on that path, so a server that speaks only the chat shape needs a new builder | A plan of its own, and a benchmark page that does not exist yet. Two things hold the native route: the judge posts a literal grammar and reads first-token alternatives, neither of which the chat route returns on the pinned build; and the per-item two-**call** prefix reuse, where the second call continues the first one's prompt string in the same slot. **The cost of losing that reuse has been quoted in this plan and has no instrument log** (Guardrail #10). Before this is decided, that reading gets a page under `docs/reference/benchmarks/` with hardware, date and spread, or it is not cited again |
| The server address as a tunable | The address stays where it is written today | Nothing in the tree points at another server and the request shape cannot move, so an address knob reaches no consumer. It arrives with the plan that moves the shape |
| `slot_id`, `kv_tokens_at_start`, `prefix_shared_with_previous` | Three llama-specific cells stay on the item record | They leave with the transport that made them so |
| The trust boundary: the marker check, `_CHAT_CONTROL_FAMILIES`, `untrusted_block`, `sanitize` | A model family whose markers no pattern recognises cannot load until a pattern is added | Nothing here. Row 7 moves where the check runs and changes nothing about what it refuses |
| `decoding_still_constrains` (`backend/idhazh/llm/server.py:1292`) | One probe case and one short decode stay at every server start | **It is kept, and row 7 says why.** It builds from the schema this run really sends, so it catches our own generated schema gaining a construct the converter drops - this project's own code being wrong, which is the one thing the rule keeps a check for |
| The Pydantic models for payloads a run writes and a later run reads | The producer keeps validating its own output as it writes it | One program checking its own work in one language. Row 5 retypes exactly one field inside one of them and stamps it |
| The weights checksum and byte-count check | Two steps and one test stay in every fetch path | They guard bytes this project downloaded |

### What a change costs today

| Reading | Value | Where |
| --- | --- | --- |
| Edits to name one more llama-server option | six, across five files | a typed field, a branch in the argv builder, a regenerated schema, a version stamp, a changelog line, a test |
| Edits to name one more option after row 5 | one | the model file. The builder emits what the block holds and never names a key |
| Inference keys that exist only to be translated into a flag | 19 of 30 | no reader outside `server_argv` and the run-identity spelling, censused 2026-09-21 |
| Inference keys read by name elsewhere in this project | `n_ctx`, `n_batch`, `n_threads`, `n_parallel`, `load_mode`, `temperature`, `top_p`, `seed`, `request_timeout_minutes` | `classify/dag.py`, `evals/qualify.py`, `stages/work.py`, `stages/common.py`, `similarity/judge.py`, `llm/server.py` |
| Lines of the run fingerprint with no production caller | about 190 of 472 | `NOT_DIGESTED`, `MODEL_FIELD_SPELLING` and both digested-field functions reach only themselves and two test modules |
| Committed model files where a key is set by exactly one of the five | 9 keys | `config/models/`, censused 2026-09-21 |
| Committed `run.json` files that embed the typed inference block | every one | which is why row 5 stamps the run manifest |
| Committed `run.json` files carrying a draft head | 6 | the one read-side line this plan owes |
| Turn markers derivable from the model's own rendering | 6 of 8 | `thinking_kwarg` is an input to the render; `thinking_close` is what the model writes |
| Recorded times the startup render check has refused a run | none | no commit, plan row or page records one. Its sibling prefix-cache case refused all four shards on its first real run, so that day planned 80 items and published none |

## Section 0b - What this plan does, in one list

Seven rows, two pull requests. Read this before the tables.

1. Delete the reader that parses the model server's log, and the dead retired-marker guard beside it.
2. Delete the decode stamp whole, and the run fingerprint nothing calls.
3. Delete the draft-head fields, with the one read-side line six committed run records need.
4. Delete both decode caps, the arithmetic that reconciled them, and the item-health column one of them fed.
5. Let the model file carry llama-server's own flag spellings. The translation tables, the deny list and the import-time assertion never exist; the run-identity closure goes with them.
6. Amend Guardrail #3 and section 11 of the engineering contract, inside the pull request that contradicts them.
7. Derive each model's turn markers from its own template at server start. The turn block, its eight keys and the check that audited our copy all go.

## Section 1 - Status Reckoner

**Rows are grouped into two pull requests. A pull request is one worktree, one branch, one review.** Rows inside a pull request run in the order below, in that one branch.

| # | Row title | PR | Depends-on | Parallel-group | Status | Worktree | PR link | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The server-log reader goes | A | - | A | DONE | p41a | - | worker |
| 2 | The decode stamp and the dead fingerprint go | A | 1 | A | DONE | p41a | - | worker |
| 3 | The draft head goes from the model shape | A | 2 | A | PENDING | - | - | - |
| 4 | Both decode caps go | A | 3 | A | PENDING | - | - | - |
| 5 | The model file carries llama-server's own flags | A | 4 | A | PENDING | - | - | - |
| 6 | The engineering contract catches up | A | 5 | A | PENDING | - | - | - |
| 7 | The markers are derived at server start | B | 6 | B | PENDING | - | - | - |

### The two pull requests

| PR | Rows | Can it change a rendered prompt | What proves it |
| --- | --- | --- | --- |
| **A - the model file stops being a type** | 1, 2, 3, 4, 5, 6 | no | the command line and the request body built from each of the five committed model files, against fixtures captured before any edit |
| **B - the markers come from the model** | 7 | **yes, and it is the only one here that can** | the rendered prompt for each committed entry is byte-identical to the one the hand-typed markers produced, driven from a recorded server response |

**Why two and not one.** Row 7 is the only change that can move a rendered prompt. Landing it alone means a moved prompt has exactly one candidate cause. Pull request A's base is main and B's base is A's merge commit.

**Why two and not three.** Rows 1 to 4 are pure deletions and row 5 rewrites what they leave behind; they share `backend/idhazh/llm/server.py` and `fingerprint.py`, so splitting them buys two branches on one file and nothing else.

**No dispatch is required by any row.** Every oracle in this plan is a local assertion or a recorded server response. The previous draft carried a two-dispatch evidence gate; it was deleted because its four machine assertions were re-derivations of a local one, and its pass condition asked a person to rank runner nondeterminism.

## Section 1a - The contracts, declared before any code

CLAUDE.md section 0d: intent, then contract, then code. **A worker does not invent one of these; it reads this section.**

### C1 - The model file (rows 3, 4, 5)

`config/models/<name>.json`. No Pydantic model for its contents, no generated schema, no compliance test, no bound on any value.

**The file carries llama-server's own flag spellings.** Nineteen of the thirty inference keys exist for no purpose except to be translated into a flag, so they are written as the binary writes them and emitted verbatim. That is what removes the translation entirely rather than reorganising it: there is no key-to-flag table, no switch table, no presence table, no deny list and no import-time disjointness assertion, because none of them has anything left to do.

Two blocks under each role:

| Block | Holds | Who reads it |
| --- | --- | --- |
| `server` | llama-server's own flags, exactly as the binary spells them - `"--ctx-size": 49152`, `"--flash-attn": "on"`, `"--no-warmup": null`. A null value means a bare flag with no argument | the command-line builder, and nothing else |
| `request` | the four values that are not server flags at all: `temperature`, `top_p`, `seed`, `request_timeout_minutes` | the request body, and this project's own HTTP client |

**A sampling value cannot reach the command line, by construction.** The builder reads only the `server` block. That is the same guarantee the deny list was asserting, obtained by where the values live rather than by a check that has to be kept in step.

**The builder is four lines**: for each key and value in `server`, emit the key, and emit `str(value)` beside it when the value is not null. `--model`, `--no-context-shift`, `--port` and the alias stay in code because no key produces them.

**Only one key is required: `--ctx-size`.** A key is required when this project's own code computes on it, because a default in our code plus a default in the server is two answers for one value. `--ctx-size` is real arithmetic - the window budget in `backend/idhazh/classify/dag.py:241` and the context gate in `backend/idhazh/evals/qualify.py:414` - and the published site reads it at build time. `request_timeout_minutes` is required in the `request` block for the same reason: four call sites multiply it by 60 and there is no server-side default to fall back to, and the loader coerces it with `float()` so a string raises at load rather than inside a request mid-item.

**Everything else is optional and the file may stay silent on it.** Absent means the flag is not emitted and the key is not sent, which is llama-server's own default. A model file carries what that model changes and says nothing about the rest.

**No key gets a bound.** `top_p`'s interval is the only one in the file today and it goes with the type. Keeping one interval while `min_p`, `top_k` and `mirostat` arrive makes every new key an argument about whether it deserves a check too, and a key being swept is the worst possible case for a bound. Owner ruling 2026-09-21.

**Nine keys this project reads by name** - `n_ctx`, `n_batch`, `n_threads`, `n_parallel`, `load_mode`, `temperature`, `top_p`, `seed`, `request_timeout_minutes` - reach their readers through one nine-entry alias map from our name to the flag name, declared once beside the builder. Four of them are persisted under our names on the run record and drawn in words on a console panel, which is why the alias map exists rather than a rename.

Entry-level keys keep their current names: `id`, `repo`, `revision`, `file`, `sha256`, `byte_count`, `arch`. `<role>.runtime` arrives with Lane B and is not declared here. `turns` leaves entirely in row 7.

**Deleted from the file**: `declared_for` on the turns block, `draft`, `max_answer_tokens`, `max_think_tokens`, and every key's old name once the server block carries the flag. All five committed files are rewritten once, mechanically, in row 5.

**`inference.declared_for` survives as a four-line loader check**, beside the judge-weights rule. It is not redundant: it catches one specific edit, a weights string changed in place with the block left behind, and then the value holds the old digest and the load refuses. Nothing else in the tree sees a half-done model swap, and a stale weights reference is silent.

**`MODELS_FILE_PATTERN` and `ModelsFile` survive byte-identical**, moved into the module that declares the application configuration. The loader joins rather than checks and says so on the line, so that grammar is the only thing ruling out a traversal, an absolute path and a Windows separator (Guardrail #11). Row 5's ruling is about the file's contents, never about the path to it.

**Read-side migration on the file: none.** The file is read key by key, so a key no reader names is never looked at.

### C2 - The turn markers, derived at server start (row 7)

**The turn block leaves the repository.** `backend/idhazh/contracts/knobs/turns.py`, its eight keys in all five committed files, and the hand-transcription they represent all go.

**The markers are derived once per server start, held in memory, and written nowhere.** The startup probe already posts the probe conversation to the server's template-applying route and already tokenises both sides. Deriving the six recoverable markers from that same rendering makes this project's render the server's render **by construction** rather than by agreement - which is why the check that compared the two goes with them. A check that compares a value against the thing it was just derived from cannot fail.

| Marker | Source |
| --- | --- |
| `turn_opening`, `turn_closing`, `reply_opening`, `reply_opening_thinking`, `system_role`, `system_joiner` | derived at server start from the model's own rendering, three template calls, no decode |
| `thinking_close` | stays on the entry. A generation prompt never contains it - it is what the model writes, not what the template writes. A wrong one means the span never stops and the item lands `model_timed_out`, loudly and per item |
| `thinking_kwarg` | stays on the entry. A rendering cannot return a name that was never sent; it is an input to the render |

**The boundary check moves from configuration load to server start, and changes nothing about what it refuses.** It still runs in every process that decodes, still before the first article, still over a plain mapping, and still refuses a marker family the sanitizer cannot strip. What changes is that it now reads markers the server produced rather than markers a person typed. No reader is exposed between load and server start, because no item has run. Guardrail #11's control is unchanged in force; only its position moves, and ESCALATE trigger 1 governs it.

### C3 - The run fingerprint, after the closure goes (rows 2, 5)

`backend/idhazh/fingerprint.py` survives as the thing that builds and compares a run's recorded inputs. About 190 of its 472 lines do not: `NOT_DIGESTED`, `MODEL_FIELD_SPELLING`, `digested_inference_fields` and `digested_model_fields` reach only themselves and two test modules, with **no production caller anywhere**.

**They go, and no closure replaces them.** The closure's job was to refuse a new option that reached no stamp. Follow what the stamp feeds and it ends at one GitHub annotation that prints and returns - `fingerprint.py` says it itself: it reports, it never gates. Taxing every future option with a written entry to protect an annotation is the six-edit toll re-growing under a new name. A misspelled flag is now caught by llama-server refusing to start and naming it, at every server start, for free.

What stays live: `build_inputs`, `prose_changed_alone`, both canonical spellings and the three environment readers, all of which have production callers in `stages/assemble.py`, `stages/work.py` and `stages/qualify.py`.

**`PipelineInputs` keeps its shape and its fields**, because a console panel draws a rule from it naming which input moved on which day. **`PipelineInputs.fingerprint()` goes** in row 2 - its stated purpose is rebuilding a stamp on rows written before 2026-09-12 and nothing rebuilds one, which is the argument this plan already wins against the decode stamp.

**`ModelRef.inference` is retyped to a plain mapping, and the run manifest is stamped in the same commit.** Every committed `run.json` embeds it, so this is a persisted-contract change under CLAUDE.md section 11: a version stamp and a changelog line on `run_manifest.py`, in row 5, or the row stops. No data migration is owed - a JSON object loads into a mapping - and the retype is what lets committed records carrying `declared_for`, `max_think_tokens` and retired option names keep reading.

### C4 - The committed columns this plan removes (rows 2, 4)

Three ledgers lose a column. Each uses that ledger's own retired-cell mechanism, and the row that removes the column carries that work in its scope rather than discovering it.

| Column | Ledger | Mechanism |
| --- | --- | --- |
| `decode_digest` | the similarity scored-pairs day files, the score distribution and one archive record | **none exists on these ledgers.** Row 2 builds one, modelled on the item-health ledger's retired-cell list. This is the row's real work, not a first step |
| `max_output_tokens` | the item-health day files | the item-health retired-cell list already exists. One line |
| the decode stamp on the judge records | three contract modules | each takes a version stamp and a changelog line |

**One consequence stated rather than discovered**: the similarity archive filename is built from the record's stamp over its compared values, so **new archive records land under different filenames**. Existing archives stay readable and nothing re-reads one by a recomputed name.

**The judge's change detector keeps eleven of its twelve compared fields** - the model, the prompt digest, the grammar digest, the sampler temperature and the thinking flag among them - so a moved judge still holds the merge line. Nothing on the judge's stamp surface is orphaned by row 2 except what row 2 deletes.

### C5 - What runs before the first article (rows 4, 5, 7)

| Check | Where | What it catches |
| --- | --- | --- |
| the turn-marker boundary check | server start, every process that decodes | a marker family a forged turn would survive (Guardrail #11) |
| `--ctx-size` and `request_timeout_minutes` present, and the timeout coerced to a number | configuration load, no server | a missing or unusable value this project computes on. It raises naming the key |
| the weights checksum and byte count | the fetch step | a truncated download, an error page saved as weights, a revision that moved under a name |
| `inference.declared_for` against the weights digest | configuration load, no server | a weights string changed in place with the block left behind |
| llama-server's own refusal | server start | a flag this build does not accept. It names it and does not start |
| the health check naming the weights that answered | the workflow | a server up on a different file, or not up |
| **`decoding_still_constrains`** | server start, one short decode | the schema-to-grammar conversion getting looser, **and our own generated schema gaining a construct the converter drops**. The second is this project's own code being wrong, which is why this case is the one that stays |

**What still reaches a reader with nothing red.** A configured window larger than the window the weights were trained for: the reply is well shaped, the decode ends itself, and the summary is worse. The owner ruled this an observation rather than a refusal, and the probe case that read it is deleted with the other three - a request plus a log line nothing commits is not a check. The next move is named rather than left open: it becomes a committed cell beside the configured window once plan 39 row 1 makes a new field cost one line instead of six.

### C6 - The engineering contract clauses that move (row 6)

| Clause | What it must say |
| --- | --- |
| Guardrail #3 | The producer declares and validates its own payloads in its own language. A configuration file this project authors needs no declared shape |
| Section 11 | Scoped to persisted payloads a later run reads. A configuration file this project authors is out |

The section 1a, section 9 and section 10 amendments stay with plan 39 row 1, because they are about generation and drift, which this plan does not remove. Guardrail #11 and Guardrail #12 are untouched. Each clause that moves carries a dated line naming who moved it (CLAUDE.md section 1).

## Section 2 - Row #1 - The server-log reader goes

- **Scope:** Delete the reader that parses the model server's log to learn whether an optimisation engaged, its enumerated states, and the dead retired-marker guard in the configuration loader.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (`flash_attention_state` and its states)
  - `backend/idhazh/config.py` (`RETIRED_TURN_MARKERS` and the load-time raise that reads it)
  - `backend/tests/test_summarize.py`
  - `tests/fixtures/runtime/` (only the log captures nothing surviving reads)
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'summarize or config'`; CI - full suite.
- **Oracle:** no reader of the server's log text survives except the ones producing the run's own cost figures, proved by a census across `backend/`, `frontend/src/`, `backend/utilities/` and `.github/`. What it cannot settle: whether the optimisation is engaged - after this row the runtime's own startup output is where a person looks.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | Whether an optimisation engaged is the runtime's business, and this project asked by parsing a log line at a raised verbosity | Carmack |
 | 2 | **The census runs before the deletion, not after.** `flash_attention_state` has no caller in the tree today, so no console surface loses a field and no browser smoke is owed - but the row proves that rather than assuming it | Carmack and Fowler |
 | 3 | `RETIRED_TURN_MARKERS` guards against a file deleted on 2026-09-13 reappearing. Nine lines, no consumer, and no mechanism that could recreate it. It rides with this row because this row already opens the loader | Fowler |
 | 4 | The two log-format assertions in `backend/tests/workflows/test_model_server_jobs.py` are not about this reader. They check a workflow's log-matching step, which is plan 39 row 10's subject | Carmack |
 | 5 | The error-body classifier stays. It sorts a failure into this project's own taxonomy | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep the reader, drop the tests | A parser with no check on it goes wrong silently | About 20 lines kept | Carmack |

## Section 3 - Row #2 - The decode stamp and the dead fingerprint go

- **Scope:** Delete `decode_digest` whole - the function, the excluded-key set, the completion field, the judge stamp field, the three contract fields, the comparison that reads it, the tests and the committed column - and delete `PipelineInputs.fingerprint()` with it. Build the retired-cell mechanism the similarity ledgers lack. See C3 and C4.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (`decode_digest`, its excluded-key set, the completion field and its setter)
  - `backend/idhazh/similarity/stamps.py`, `backend/idhazh/similarity/counting.py`
  - `backend/idhazh/contracts/judge_call.py`, `story_similarity_pair.py`, `story_similarity_distribution.py`
  - `backend/idhazh/contracts/fingerprint.py` (`fingerprint()`)
  - `backend/idhazh/ledger.py` (the retired-cell mechanism for the similarity ledgers)
  - `backend/tests/test_summarize.py`, `test_similarity_judge.py`, `test_similarity_counting.py`, `test_similarity_fit.py`, `test_fingerprint.py`, `backend/tests/contracts/test_judge_call.py`, `test_story_similarity.py`
  - `docs/architecture/contracts/determinism.md`
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'summarize or similarity or judge or fingerprint'`, then the contract export with zero drift; CI - full suite.
- **Oracle:** an append to a committed similarity day file succeeds after the column is gone, run against the two real day files. That is the half that can fail, and it fails today if the row skips the retired-cell work. What it cannot settle: whether anything wanted the stamp - the census in the row's scope proves nothing did.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Determinism is not a goal of this project**, so a stamp whose only job was to prove two runs asked for the same thing has no job. Deleted whole | Owner ruling 2026-09-21 |
 | 2 | The record it duplicates stays. The run's recorded inputs carry the values as readable text and name the field that moved, which is what a person wants; a digest can only say that something moved | Fowler |
 | 3 | **`PipelineInputs.fingerprint()` goes in the same row.** Its stated purpose is rebuilding a stamp on rows written before 2026-09-12; nothing rebuilds one. That is the same argument, one file along | Fowler |
 | 4 | **Building the retired-cell mechanism for the similarity ledgers is this row's work**, not a first step to discover. The item-health ledger's list is the model to copy | Fowler and Carmack |
 | 5 | **New similarity archive records land under different filenames.** The archive name is the record's stamp over its compared values. Existing archives stay readable and nothing re-reads one by a recomputed name | Carmack |
 | 6 | The judge's change detector keeps eleven of twelve compared fields, so a moved judge still holds the merge line. The census is already clean; nothing else is orphaned | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete only the dead summarize half | Leaves the judge half, which is the part with committed columns, and leaves the function alive to be reused | The same argument again later | Fowler |
 | 2 | Keep it as a cheap audit trail | It answers no question a person asks, and it would move on every sampler sweep once more sampler keys arrive - a re-archive per experiment for a reading nobody uses | About 80 lines across six files and a column on three ledgers | Owner |

## Section 4 - Row #3 - The draft head goes from the model shape

- **Scope:** Delete the draft-head configuration from the model shape and the command-line builder, and add the one read-side line that keeps six committed run records loading.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/models.py` (the draft shape, its enumerated kinds, the entry field)
  - the module declaring `ModelRef` (the read-side line)
  - `backend/idhazh/llm/server.py` (the draft arguments)
  - `backend/idhazh/fingerprint.py` (its not-digested entry)
  - `config/models/gemma-4-e4b-qat.json`, `config/models/gemma-4-e4b-qat-no-draft.json`
  - `backend/tests/test_summarize.py`, `backend/tests/test_fingerprint.py`
  - the documentation pages that describe it
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'summarize or fingerprint or model'`; CI - full suite. ESCALATE trigger 3 applies.
- **Oracle:** a committed `run.json` carrying a draft head parses after the change, asserted against one of the six real files; and no Python module or contract mentions a draft head, a speculation kind or a speculative argument, proved by census. The first half can fail and is why this is its own row. What it cannot settle: whether the workflow wiring is gone - that half is Lane B's.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | It is deleted rather than kept unused. A measurement on 2026-09-12 found it changes the output on nine articles of nine, so it was never a free speed-up | Owner ruling 2026-09-21 |
 | 2 | **The row splits at the seam its own scope carries.** The model-shape half runs here because it edits the files row 5 rewrites. The fetch half - a companion-file list, a download loop and an installer publishing each landed path - touches no contract module and runs in Lane B with row 13 | Carmack and Fowler |
 | 3 | The census closes twice: here for the Python and contract surface, and again at Lane B's close, because the fetch half is what makes speculative decoding reachable again as configuration | Carmack |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete the field with no read-side line | Six committed run records carry it and the reader forbids extra keys, so the next build cannot read yesterday's record. CLAUDE.md section 11 names that a release blocker | A broken read of six committed payloads | Fowler |
 | 2 | Keep the argument builder and drop only the configuration | Leaves code nothing can reach | About 25 lines kept and a dead branch | Carmack |

## Section 5 - Row #4 - Both decode caps go

- **Scope:** Delete `max_answer_tokens` and `max_think_tokens`, the addition that summed them, the rule that a null cap means omitting the key, the two route-specific spellings, and the item-health column one of them fed.
- **Files touched:**
  - `backend/idhazh/llm/server.py` (both request builders, the span builder, the sum branch and the omit-the-key branch)
  - `backend/idhazh/stages/common.py` (the parameter and its default of zero), `two_calls.py`, `backend/idhazh/summarize.py`, `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/evals/qualify.py`, `backend/idhazh/classify/dag.py` (the arithmetic that reserved window for a cap)
  - `backend/idhazh/stages/work.py` (it writes `max_output_tokens` onto the item-health row)
  - `backend/idhazh/contracts/item_health.py` (the column and its retired-cell entry)
  - `backend/idhazh/fingerprint.py` (both terms in the sampling spelling)
  - `config/models/` (all five files)
  - `backend/tests/test_summarize.py`, `test_classify.py`, `test_fingerprint.py`, `backend/tests/contracts/`
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'summarize or classify or judge or fingerprint or qualif or item_health'`, then the contract export with zero drift; CI - full suite. ESCALATE trigger 4 applies.
- **Oracle, three parts, each able to fail:**
  1. For all five committed model files, the request body posted on each route carries **no token-cap key at all**, and is otherwise byte-identical to today's.
  2. An append to a committed item-health day file succeeds with `max_output_tokens` retired. **This fails today if the row forgets the column**, which is the defect the row exists to avoid.
  3. A thinking entry still makes **two** requests and a non-thinking entry still makes **one**, driven from a recorded server response. This fails if the split is collapsed.

  What it cannot settle: how long a model runs before it stops on its own. Neither cap binds on the live model today.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **Both caps go, because they are the same kind of thing.** Each is a number this project sends where llama-server's own default is already unlimited, bounded by the window, and the server is started without a prediction flag | Owner ruling 2026-09-21 |
 | 2 | **The four moving parts go with them**: two caps, two route-specific spellings, an addition because the chat route cannot split the spans, and a rule that a null in the sum means omitting the key. Four parts answering one question - when does the decode stop - all created by sending a number the runtime did not need | Owner ruling 2026-09-21 |
 | 3 | **The bounds that remain already exist and already fail loudly, per item**: the per-request timeout lands `model_timed_out`; the window with no context shift lands `CONTEXT_EXCEEDED`. No new code, no new cell | Carmack |
 | 4 | **The item-health column is this row's, not a discovery.** `stages/work.py` writes the answer cap onto every item row and the column is in committed day files. The item-health ledger already has a retired-cell list, so this is one line - but the row names it | Fowler and Carmack |
 | 5 | **The split stays.** The first request leaves the decode unconstrained while the model reasons; the second puts the shape back for the answer. A collapsed split applies the shape from the first token, so a reasoning model cannot reason and still returns a well-shaped summary | Fowler and Andre |
 | 6 | **This changes nothing that ships today.** No committed model file sets a thinking cap, and the answer cap on the live pointer is not reached by any committed item. For a new model that rambles, the first sign becomes a slow item rather than a truncated one | Andre |
 | 7 | The parameter default of zero in the shared caller goes with the fields, and with it the trap where a caller that forgets the argument decodes a zero-token thought and still returns a well-shaped summary | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Delete the thinking cap and keep the answer cap | The same request-body field under two names. Keeping either keeps the two spellings and the sum | Two of the four moving parts, and the argument again on the next model | Owner |
 | 2 | Keep one cap as a circuit breaker, set generously | A breaker set where it never fires is a number nobody can justify and nobody will revisit, and it keeps the sum and the null rule alive to serve it. The timeout is already the breaker | One key, the sum, the null rule, and a number with no derivation | Owner |
 | 3 | Set a cap from the committed timings | The only per-item timing is a stopwatch with the queue inside it, so summing it across a shard overcounts, and the repository's own shard benchmark is from a retired model at a different item load. No number derived from either is defensible | A benchmark that isolates decode from queue, before any cap could be justified | Carmack |

## Section 6 - Row #5 - The model file carries llama-server's own flags

- **Scope:** Rewrite the model file into a `server` block spelled as llama-server spells it and a `request` block beside it, delete the typed model configuration and the whole translation layer, delete the run-identity closure, and retype the recorded inference block with its stamp. See C1 and C3.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/models.py` (the entry and registry shapes, the rename refusals, the turns-block validators)
  - `backend/idhazh/contracts/knobs/inference.py` (deleted whole)
  - `backend/idhazh/contracts/run_manifest.py` (`ModelRef.inference` retyped, version stamped, changelog appended)
  - `backend/idhazh/config.py` (the loader, the served-role list, the entry list, the judge-weights rule, the `declared_for` check, the timeout coercion)
  - `backend/idhazh/llm/server.py` (`server_argv` becomes the four-line emitter; the request bodies read the request block)
  - `backend/idhazh/fingerprint.py` (the closure deleted; both spellings read the alias map)
  - `backend/idhazh/stages/work.py`, `common.py`, `two_calls.py`, `summarize.py`, `similarity/judge.py`, `evals/qualify.py`, `classify/dag.py` (the nine keys read through the alias map)
  - `config/models/` (all five files rewritten once, mechanically)
  - `backend/tests/contracts/test_model_registry.py`, `backend/tests/test_summarize.py`, `test_classify.py`, `test_fingerprint.py`, `test_app_config.py`
  - `schemas/models-config.schema.json`, `frontend/src/contracts/models-config.ts` (deleted; the run-manifest and qualification artefacts regenerate and are committed)
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'config or model or summarize or fingerprint or classify'`, then the contract export with zero drift; CI - full suite. ESCALATE triggers 2 and 5 apply.
- **Oracle, four arms, each able to fail:**
  1. **Golden command line and golden request body.** For each of the five committed model files, both equal fixtures **captured from the tree before any edit and committed**. Any wrong flag in any rewritten file fails this.
  2. **A sampling value cannot reach the command line.** A fixture entry putting `temperature` in the `server` block by mistake emits it, llama-server accepts it, and the test asserts the builder never reads the request block - so the fixture proves the blocks are the control rather than a rule.
  3. **An unknown flag reaches the server unchanged.** A fixture carrying a flag no reader of ours names is emitted verbatim.
  4. **A committed run record still parses** after `ModelRef.inference` is retyped, asserted against a real `run.json` carrying `declared_for` and a retired option name.

  What it cannot settle: whether a misspelled flag is caught before a dispatch. It is not - llama-server refuses at start and names it, which is the loud failure this plan's rule asks for and the reason the closure goes.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | **The file spells the flag.** Nineteen of thirty keys exist only to be translated, so the translation is deleted rather than reorganised. No key-to-flag table, no switch table, no presence table, no deny list, no import-time assertion | Carmack |
 | 2 | **Two blocks, and that is the control.** A sampling value cannot reach the command line because the builder never reads the block it lives in. A guarantee obtained by structure beats the same guarantee asserted by a check somebody has to keep in step | Carmack |
 | 3 | **One required key in each block.** `--ctx-size` because real arithmetic reads it and the published site reads it; `request_timeout_minutes` because four call sites multiply it by 60 and there is no server default to fall back to. Everything else is optional and absent means the server's own default | Owner ruling 2026-09-21 |
 | 4 | **No key gets a bound.** `top_p`'s interval goes with the type. A key being swept is the worst possible case for a bound, and more sampler keys are coming | Owner ruling 2026-09-21 |
 | 5 | **The run-identity closure goes.** About 190 lines with no production caller, guarding a stamp whose only consumer prints a warning annotation and returns. Taxing every future option with an entry to protect an annotation is the toll this plan deletes | Carmack and Fowler |
 | 6 | **`ModelRef.inference` is retyped and the run manifest is stamped in the same commit.** Every committed run record embeds it, so this is a persisted-contract change (CLAUDE.md section 11). No data migration is owed, and the retype is what lets old records carrying retired keys keep reading | Fowler and Carmack |
 | 7 | **`inference.declared_for` survives as a loader check.** It catches a weights string changed in place with the block left behind, and nothing else in the tree sees a half-done model swap. The turns-block copy goes with the turns block | Fowler |
 | 8 | **The judge-weights rule survives as a loader check** over the mapping. No server is started for a judge entry, so one naming different weights decodes on the summariser's weights while every verdict is recorded under a model that never saw the pair, and nothing raises | Fowler |
 | 9 | **The model-file pointer keeps its grammar, byte-identical.** The loader joins rather than checks and says so, so the grammar is the only thing ruling out a traversal (Guardrail #11). Decision 1 is about contents, never the path | Fowler |
 | 10 | Nine keys this project reads by name reach their readers through one alias map. Four are persisted under our names and drawn in words on a console panel, so a rename would move a published string; an alias does not | Carmack |
 | 11 | The `runtime_flags` spelling now enumerates flag names rather than field names, which moves that recorded string once. The console will report the server switches moved on the first run after. It is a one-time true statement and the row says so rather than hiding it | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Keep our names and declare three spelling tables plus a deny list | That is rebuilding the type system with dictionaries. Eight declared constants and four checks to replace one Pydantic model, and a new option still costs three edits in three files | About 150 lines of new declarations, and the plan's own cost table falsified | Carmack and Fowler |
 | 2 | Keep typed fields for the values this project's own code reads | Two ways to declare a value and a rule about which wins | About 60 lines kept, and a reader who cannot tell which half of the file they are in | Owner |
 | 3 | Keep the closure so a misspelled option is caught in the suite | llama-server catches it at every server start and names it, for free. The closure costs a written entry per option forever | About 190 lines kept and a toll on every future option | Carmack |
 | 4 | Leave `ModelRef.inference` typed | `InferenceConfig` is deleted by this row, so the field would name a shape that no longer exists | The whole typed inference block kept for a recorded payload nothing computes on | Fowler |

## Section 7 - Row #6 - The engineering contract catches up

- **Scope:** Amend the two clauses of the engineering contract that rows 3, 4 and 5 contradict, inside the pull request that contradicts them.
- **Files touched:**
  - `CLAUDE.md` (Guardrail #3, section 11)
  - `docs/architecture/contracts/schemas.md`, `docs/architecture/contracts/determinism.md`
  - `docs/reference/repository-layout.md`
  - `TODO/STATUS.md`
- **Acceptance gates:** `python backend/utilities/doc_load.py` before and after, and the split test on any page gaining a section. This row ships inside pull request A and rides its suite. ESCALATE trigger 6 applies.
- **Oracle:** no clause of the engineering contract requires a declared shape, a generated schema or a stamped version for a configuration file this project authors - checked clause by clause against the tree, not against this plan. What it cannot settle: whether the amended clause is the right rule. That is section 0's question and the owner answers it by authorizing this plan.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The amendment ships with row 5, not after it. CLAUDE.md section 0 requires a conflicting rule to be amended in the same change | Owner, CLAUDE.md section 0 |
 | 2 | Only Guardrail #3 and section 11 move here. Section 1a, section 9 and section 10 are about generation and drift, which this plan does not remove, so they stay with plan 39 row 1 | Fowler |
 | 3 | Each clause that moves carries a dated line naming who moved it (CLAUDE.md section 1) | Fowler |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | Take a named exception per row instead of amending the clause | Three exceptions to one rule is the rule being wrong | Three dated notes and a guardrail nobody believes | Fowler |
 | 2 | Amend after the rows land | Leaves the repository in a state where its own contract forbids its own code | Nothing saved; it is a sequencing error | Owner |

## Section 8 - Row #7 - The markers are derived at server start

- **Scope:** Delete the turn block, its eight keys in five committed files, and the startup check that compared our render against the model's. Derive the six recoverable markers at server start from the rendering the probe already asks for, hold them in memory, and keep two on the entry. Cut the startup probe to the boundary check, the marker derivation and `decoding_still_constrains`. See C2 and C5.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/turns.py` (deleted whole)
  - `backend/idhazh/llm/server.py` (the marker readers, the envelope digest, the render check, the three deleted probe cases and the weights-header parser)
  - `backend/idhazh/config.py` (the boundary check moves to server start)
  - `backend/idhazh/fingerprint.py` (the envelope digest reads the derived markers)
  - `backend/utilities/prove_the_entry.py`
  - `config/models/` (all five files lose the turn block except two keys)
  - `backend/tests/contracts/test_turn_envelope.py`, `backend/tests/test_summarize.py`, `test_classify.py`, `test_config.py`
  - `docs/architecture/` pages describing the envelope
- **Acceptance gates:** local - `python -m pytest backend/tests -q -k 'summarize or classify or judge or config or turn'`; CI - full suite. ESCALATE trigger 1 applies.
- **Oracle:** for each of the five committed entries, the prompt rendered from the derived markers is **byte-identical** to the prompt the hand-typed markers produce today, driven from a recorded server response so nothing touches the network. That is the whole check and it can fail. What it cannot settle: whether the derivation holds for a model family none of the five uses - that is found the day one is added, at server start, before the first article.
- **Decisions:**

 | # | Decision | Authority |
 | --- | --- | --- |
 | 1 | The template is the model's, not ours. A configuration field that restates somebody else's file is the same mistake as a schema that restates a Pydantic model | Owner ruling 2026-09-21 |
 | 2 | **Derive at server start, hold in memory, write nothing.** The probe already posts the probe conversation to the template route and already tokenises both sides. A recorder that writes the derived values into tracked configuration adds a write path over a file a person owns, five refusal conditions, and a new silent-wrongness class - and then needs a check to audit itself | Carmack |
 | 3 | **The render check goes, and it goes for free.** Once our render is the server's render by construction, a check comparing the two cannot fail. It has never refused a run in the tree's history; its sibling prefix-cache case refused all four shards on its first real run, so that day planned 80 items and published none | Carmack and Fowler |
 | 4 | **`decoding_still_constrains` stays.** It builds from the schema this run really sends, so it catches our own generated schema gaining a construct the converter drops - this project's own code being wrong, which is the one thing the rule keeps a check for. One short decode | Andre |
 | 5 | **Two markers stay on the entry.** A rendering cannot return a variable name that was never sent, and a generation prompt never contains the marker the model writes to close a reasoning block. Both fail loudly per item when wrong | Carmack and Andre |
 | 6 | **The boundary check moves to server start and changes nothing about what it refuses.** Same process, still before the first article, still over a plain mapping. No reader is exposed between configuration load and server start because no item has run | Owner decision required, ESCALATE trigger 1 |
 | 7 | The transport does not change. This project keeps building the prompt and posting it to the route it uses, so the judge's literal grammar, its first-token reading and the per-item prefix reuse are all unaffected | Fowler and Andre |
 | 8 | The trained-window probe case goes with the other three. A request plus a log line nothing commits is not a check; the committed cell that would replace it waits for plan 39 row 1 | Andre |

- **Rejected alternatives:**

 | # | Option | Why rejected | What it would cost to take | Authority |
 | --- | --- | --- | --- | --- |
 | 1 | A recorder that writes the derived markers into the model file | It trades one human error mode for one machine error mode, then needs the render check to audit itself - so it removes no step and adds one. Its saving is eight keys per model, against a write path over tracked configuration, five refusal conditions, and a derivation that may hold on one template family and not the next | About 200 lines, and the check it was built to retire kept anyway | Carmack and Andre |
 | 2 | Keep transcribing by hand | Every new model needs eight markers typed and they can be silently wrong | Eight fields per model forever, and the check that polices them | Owner |
 | 3 | Delete the turn block and send messages instead | The judge posts a literal grammar and reads first-token alternatives, neither of which the chat route returns on the pinned build; and the per-item two-call prefix reuse ends. The cost of losing that reuse has no benchmark page, so it cannot be quoted as a reason either way until one exists | A new request builder, the judge's confidence reading, and an unmeasured throughput loss | Andre and Carmack |
 | 4 | An evidence gate of two dispatches and a person reading summary pairs | Its machine assertions were re-derivations of the byte-identical prompt assertion this row already takes locally, and its pass condition asked a person to rank runner nondeterminism | Two dispatches at up to 140 minutes each and a dispatch input built for the purpose | Carmack and Andre |
