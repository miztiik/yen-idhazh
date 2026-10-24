# The model's own file

**Last Updated**: 2026-10-24

What `config/` says about a set of weights: which model runs, what runtime
settings are declared for those exact bytes, how a turn is written for it, and
what sizes the corpus that trains the next one. Everything here is a fact about
one model, so it lives in one file of its own and `config/idhazh.json` carries
only a pointer. What a knob is, and what is not one, is [../config.md](../config.md).

## `config/models/<name>.json` - one file per model, and a pointer

Everything that is a fact about one set of weights lives in one file of its own: the repository, the revision, the digest, the flags its server is started with, the sampling values that go in a request body, how long one request may wait, and the two turn-envelope strings no template can answer. `config/idhazh.json` carries `models_file` and nothing else about the model.

**The swap is that one line, and so is the revert.** Point `models_file` at another committed file and the run opens another model; point it back and the previous model's settings are still in its file. Before 2026-09-14 a swap was eleven lines edited in place in the file every other knob lives in, and a revert had to reconstruct the previous model's settings out of a diff.

`models_file` is spelled relative to `config/` and its grammar pins it to `config/models/` and to `.json`, because the value is an operator's edit that becomes a path this build opens (`CLAUDE.md` section 2). It ships a default naming the committed file, so a fresh clone still runs unconfigured.

The current default is `models/ornith-1.5-9b-q5km.json`. Keep it aligned with
the committed selection when that selection changes. Recorded template checks
remain tied to the model that produced their bytes, not the current selection.
Server-setting checks accept the runtime's short and long flag spellings.
The runtime-sweep utility has its own command-line options; these are not
direct server flags. Its server launch must still use the shared argument
builder.

Owner ruling, kumarsnaveen, 2026-10-24: remove the turn-envelope, measurement
and two-call pipeline test modules. This gives up their dedicated coverage,
including stale tokenizer-reading checks in CI. The recorded measurements keep
their original model identity; `backend/utilities/measure_budgets.py check`
still reports stale readings when an operator asks. Judge tests cover role
selection, verdicts and reasoning results without asserting runtime-specific
output-limit or decoding keys. Request-builder tests own those wire details.

**`config/idhazh.json` still carrying a `models` block is refused by name**, and refused rather than lifted onto the new file: a lift would read one model out of the old block while `models_file` named another file, and the run would stand a server up on whichever won.

**Both files travel with the run.** `Settings.digests` records the pointer file and the model file it names, because the pointer moving and the file it points at being re-tuned are two different edits and a record that held only one of them could not tell them apart.

### Design rationale

The alternative was to leave the block where it was and make the swap a careful multi-line edit with a checklist. It was rejected because the checklist is the failure: the summarizer moved from the 8B to the 9B on 2026-08-27 and the settings block did not move with it, which is the incident the `declared_for` rule below exists for. A rule that catches a half-done edit is worth having; not needing the edit is worth more.

The second alternative was one file holding every model, keyed by name, with the pointer naming a key rather than a file. It was rejected because an alternate model would then be an edit to the same file as the active model, so an invalid entry could break the model that is running. Ruled by Fowler, 2026-09-14.

**The `sampling` block is sent whole, and the file is the only place a sampler is named.** Three keys were wired one at a time until 2026-09-23 - `temperature`, `top_p`, `seed` - through a table whose rows for those three mapped each name to itself. A fourth key validated and was dropped in silence, and the request the server really answered carried thirteen: the other ten were llama.cpp's own choices and no diff of ours could move them. The block is now splatted into the request body, so naming one more sampler is a key in this file and no code edit, and a key this runtime does not accept is refused at request time with the key named.

The alternative was to add the ten missing keys to the table. It was rejected because the table is the cost: it would be paid ten more times now and again for every parameter llama.cpp, vLLM or Ollama adds on their own schedules, while buying nothing a schema does not already give. A translation table across those three runtimes was rejected for the same reason one level up - a per-key map maintained against three projects that each change their parameters without telling us.

What the splat may not do is reach a decode control. `response_format`, `json_schema` and `grammar` are how an injection is stopped from changing the shape of a reply, so each route refuses a sampling key that re-spells or disables its own control, and the set of refused keys is declared beside the control rather than in one list somebody has to remember. The refusal runs when the config loads as well as when a body is built, so an operator reads a message about the file they just edited rather than one about a request body, four hundred seconds into a run.

**An output limit is not a shape control.** Owner ruling, kumarsnaveen,
2026-10-24: `sampling.max_tokens` is accepted on every request route. The chat
route defaults to 8,192 output tokens when the value is absent; an explicit
value, including the active model's 4,096-token limit, wins. Rendered completions
use the caller's shape-derived `n_predict` budget when no `max_tokens` is
declared, or 8,192 tokens when the caller supplies no budget. An explicit
`max_tokens` replaces that limit, survives continuations,
and also bounds a separate reasoning span. A request sends only one of these
limit keys. Output schemas and grammars remain enforced, and a reply stopped by
its limit is still reported as truncated rather than published as complete.

**What this pins and what it does not.** The thirteen committed values are the ones the pinned build already applies, so nothing about today's output moves. The sampler chain ORDER is a separate request key, `samplers`, and it is not pinned: a build that reorders the chain can still move the distribution with all thirteen values held.

**The slot is named for what fills it.** `models.summarizer` became `models.summarizer` on 2026-09-23: a slot holds a model, so its key is a noun (`CLAUDE.md` section 1a), and the verb named the job the model does, which is the one thing the key beside it already said. The role string a run records did not move - `summarize` sits in 127 places across 35 published run records - so what moved is the config key and the python name beside it, exactly as the retired visual planner's did.

## The model references are the only values in `config/` with no default

There is no honest default for "which weights" - a wrong guess would silently run the wrong model rather than failing. A reference names the repository, the file, and the `revision` those bytes were uploaded in; the revision is what makes the recorded `sha256` mean anything, because a download that named a branch would get whatever was uploaded last. No workflow keeps a copy of any of it: `digest.yml` and `idhazh-pipeline-tests.yaml` follow `models_file` to the active model file, read `summarizer` out of it, and use the result to load the weights ([../../reference/github-actions.md](../../reference/github-actions.md)).

**Six spellings were retired on 2026-09-13, and a file still carrying one is
refused by name.** Plan 11 row #6 deleted `models.visual_planner`,
`run.two_calls_per_item`, `run.visual_planner_budget_minutes` and
`finetune.student` in one commit, and the two older names that used to migrate
into two of them - `models.route` and `run.route_budget_minutes` - went with
them. The small model they configured is gone: the work stage makes two calls
per item on the summarizer weights, so the same model that writes the summary
decides the picture.

A rename would have been worse than nothing here. `models.route` used to be read
as `models.visual_planner`, so leaving that migration standing would take an
operator's block, file it under a key nothing reads, and raise nothing. Every
one of the six is now refused with its own name and the sentence "is gone and
nothing replaces it" - because nothing does, and pointing a lost operator at a
successor that is also missing is the same defect one level down.
`finetune.teacher` is the one role left and reads `summarizer`; a teacher still
naming the older `summarize`, `visual_planner` or `route` is answered by where
that key went rather than by a list of legal keys, because none of the three is
a typo - one moved and two name a model that is gone.

**The refusal only covers a reader that goes through the contract.** A
workflow step reading the raw JSON, or resolving a `models` key by attribute
name, sees the file and not the model - so `digest.yml`,
`idhazh-pipeline-tests.yaml` and `backend/utilities/model_runtime.py` move with
the key rather than relying on the contract. Retiring a key without moving
those readers breaks the next scheduled run. The same applies to the pointer:
those readers follow
`models_file` to the model's own file rather than naming that file, so a swap
stays one line for them too, and
`backend/tests/workflows/test_weights_and_model_refs.py::test_every_config_key_a_workflow_indexes_is_in_the_committed_config`
resolves each key path against whichever of the two documents the step really
opened.

## Runtime settings

the entry's settings hold the deterministic decode values and server settings.
Each model has its own block, so changing the model also changes the settings
that travel with it:

- `n_ctx`, `n_threads`, `n_batch`, `n_ubatch`
- `n_parallel`, `n_threads_batch`
- `cpu_range`, `cpu_strict`
- `startup_warmup`
- `metrics`
- `flash_attention`
- `load_mode`
- `cache_type_k`, `cache_type_v`
- `priority`, `poll`
- `checkpoint_min_step`, `ctx_checkpoints`, `cache_ram`
- `cache_prompt`, `slot_prompt_similarity`
- `jinja`, `reasoning_preserve`
- `temperature`, `top_p`, `seed` and every other key the `sampling` block holds
- `request_timeout_minutes`, which is a field of the entry rather than a key in
  that block: it is how long the client waits, so it never goes on the wire
- `declared_for`

Optional launch settings default to `null`, which omits their flags. Numeric
zero and boolean `false` are explicit values, not absence. The template and
prompt-cache booleans emit their positive or negative switches. Omitted core
settings such as `n_ctx` still receive the Python defaults and are sent.
`cache_prompt: null` leaves completion requests explicitly cache-enabled, as
before; a configured boolean controls both the startup flag and request body.
`load_mode: "mmap+mlock"` emits `-lm mmap+mlock`, the combined spelling the
runtime recommends instead of the deprecated separate switches.

The daily worker logs its locked-memory limits and raises them with
`sudo prlimit --memlock=unlimited --pid $$` inside the script that starts the
server. The command targets that script's own shell, and the server inherits its
effective limit; a separate workflow step would not carry it over. Each limit
command captures its error and only warns on failure. Other startup errors
still stop the job. The log records the effective limit after the attempt,
not a claim that the operating system locked the model's pages.

`declared_for` is not a sweep knob. It is the sha256 of the entry it sits on,
and `idhazh.config.refuse_a_model_nothing_could_run` refuses a file where the
two disagree - so the settings and the markers travel with the weights or the
config does not open.

`--metrics` is written into every committed file and makes llama-server
publish its counters on `/metrics`. Two of them are what a run is read by:
`llamacpp:n_tokens_max` is the highest context the server ever saw, so it says
how close the day came to the window; `llamacpp:n_busy_slots_per_decode` is the
average number of slots busy per decode, so it says whether batching happened at
all. Without the second, a concurrency measurement that shows no gain cannot
separate "more slots did not help" from "more slots were never used". The
endpoint is llama-server's own loopback surface inside a CI job. No reader
reaches it, so Guardrail #1 is untouched. `digest.yml` reads it once at the end of
each `work` job, keeps the raw body in that shard's runtime artifact, and
commits the counters that matter onto that shard's row of the host-fingerprint
ledger -
the artifact keeps them for two days and the row keeps them forever, which is
what makes the read rate on
[../../architecture/summarize/throughput.md](../../architecture/summarize/throughput.md)
checkable rather than merely reported.

Turning `metrics` off is therefore not free any more. It costs the log lines it
always did, and it also leaves every later run's counter row empty, so the
reconciliation has nothing to hold the ledger against.

`n_parallel: null` and `n_parallel: 1` are not the same runtime. `null` omits
`-np`, so llama.cpp picks its own slot count and reports unified KV; any
explicit value passes `-np` and turns unified KV off. The context each request
gets is unchanged at `n_parallel: 1`, because non-unified KV divides `n_ctx` by
`n_seq_max` and `n_seq_max` is then 1. Source: llama.cpp `common/arg.cpp` and
the `-kvu` help text, read 2026-08-25; both behaviours appear in the run logs
recorded at [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md).

A knob's presence is not evidence that it improves a run. Owner-selected
settings remain labelled unmeasured until a runner measurement records their
hardware, date and spread in
[../../reference/pipeline-cost.md](../../reference/pipeline-cost.md). Setting a value
claims no speed, memory or quality gain on its own.

### A model swap can no longer inherit settings nothing declared for it

Until 2026-09-09 there was one `models.inference` block and both roles were
served on it. Editing `models.summarizer` to name a different repository, file,
revision and digest raised nothing at all: the config loaded, `llama-server`
started on the old numbers, and the run published a whole
plausible day. **It is not hypothetical.** The summarizer moved from the 8B to
the 9B on 2026-08-27 and the block did not move with it, and the 4B visual
planner has run on the summarizer's window and the summarizer's 22.1-minute
request bound since the role existed.

The settings therefore sit on the entry, and the entry carries `declared_for`.
One digest answers for the settings and the markers together, because both are
measurements about one model and the repair is the same sentence. Two shapes of
swap, and it covers both:

- An entry with no settings of its own does not fall back to any. It names
 measured weights and declares nothing they were derived against, and the
 mismatch is refused by name.
- An entry edited in place keeps its settings, and `declared_for` still names
 the old digest. That is the shape a real swap takes, and it is the one a
 per-entry block alone would not have caught.

Both digests absent is legal and means an entry nobody has measured yet. Nothing
runs on one: `idhazh.fingerprint.build_inputs` already refuses to record a run
whose weights have no recorded digest.

### The turn envelope sits on the entry too, and obeys the same rule

Eight strings decide where a turn opens and closes, how a reply begins, and how
this model is asked to reason. They
lived in `backend/idhazh/prompts/turn_markers.json` until 2026-09-13 - one
global file with no model key, in a package this project writes, holding a fact
about somebody else's weights. A model whose turns differ was a source edit, and
a swap that left them behind raised nothing. Six of them are now read off the
model's own template at server start and typed nowhere, and the two that cannot
be - `models.<role>.thinking_close` and `models.<role>.thinking_kwarg` - sit on
the entry, where `declared_for` pins them to its `sha256`.

| Marker | What it is | Where it comes from |
| --- | --- | --- |
| `turn_opening` | opens a turn, with the role substituted into it | the template |
| `turn_closing` | closes a turn, and is where the summarize-and-plan call's prompt splices onto the label call's | the template |
| `reply_opening` | where the model starts writing, reasoning off | the template |
| `reply_opening_thinking` | the same, reasoning on | the template |
| `system_role` | whether this model gives the system block a turn of its own or folds it into the first user turn | the template |
| `system_joiner` | what separates the two blocks where it folds | the template |
| `thinking_close` | what the model writes when it stops reasoning | the entry |
| `thinking_kwarg` | the template variable that turns reasoning on | the entry |

**A template the derivation cannot read refuses the run at server start**, and
that is what replaced the rule that the four strings were required and had no
default. The failure being guarded against did not move: a prompt with no turn
structure renders cleanly, the decoder's grammar still accepts it, and the only
symptom is worse summaries. What moved is who can be wrong. A hand-typed marker
was wrong silently; a template that spells a role its own way, or writes an
opening carrying no role at all, is named in the refusal and the server does not
start.

**What is per model is the envelope, never the words.** The instructions stay
one set for every model - a per-model prompt would hide every wording change
inside the swap that carried it, and would combine two changes in one result
([../../architecture/summarize/model-boundary.md](../../architecture/summarize/model-boundary.md)).

**The file's reappearance is refused at config load.** `idhazh.config.load`
checks the retired path and raises, because the package directory is exactly
where somebody would put the markers back and a file nothing reads is a set of
markers an operator believes are live.

**The recorded shape did not move.** `run_manifest.ModelUse` embeds `ModelRef`,
which is what a run recorded; the envelope sits on `ModelEntry`, which is what a
person declares. No `model_ref` a run has ever written carries markers, and
requiring them there would stop this build reading yesterday's day (`CLAUDE.md`
section 11). What is given up is that `run.json` never says how the turns were
written - `RunRecord.inputs.prompt_sha256` digests both turns rendered through
them, so a marker that moved still moves the stamp. Ruled by Fowler,
2026-09-13.

**The stamp did not move.** `declared_for` reaches no field of
`PipelineInputs`, so `pipeline_fingerprint` is byte-identical
across this change and every committed row stays comparable
([../../architecture/contracts/determinism.md](../../architecture/contracts/determinism.md)).
Digesting it would have moved the stamp on a swap that `model_sha256` already
moves.

## Training-corpus surface

The `finetune` block sizes a file CI commits and two schedules that maintain it.
Nothing in it runs a training step - the runner has no GPU (`CLAUDE.md` section
0a) - and `teacher` and `student` name a **key in `models`**, never a model, so
swapping the summarizer is still one block.

Two pairs of knobs look like one knob each and are not:

- **`corpus_rows` is the window; `train_rows` is the sample.** They price
 differently. The window costs storage and git history, measured 2026-08-27 at
 2.9 KB compressed per row. The sample costs wall-clock on somebody's GPU. So
 window 2000 with sample 1000 is strictly better than window 1000 with sample
 1000: the same training time, twice the pool to draw a diverse 1000 from.
 `train_rows` is a ceiling rather than a demand, because a 600-row corpus
 satisfies `min_rows: 500` and cannot satisfy `train_rows: 1000`, and a session
 that silently trained on 600 while every note said 1000 produces a result
 nobody can attribute.
- **The squash's `every_days` is how often it fires; its `window` is how far back
 it keeps.** Both are in `config/gardener/corpus-squash.json`, not in `finetune`,
 because nothing but the squash reads them. "Prune quarterly" names neither on
 its own. The first costs one force-push each time; the second costs storage,
 and it is also how far `git blame` reaches afterwards.

`harvest_every_days` and the squash's `every_days` are the clearest case in this
project of a knob that **cannot** be workflow syntax.
`on.schedule` is parsed by GitHub Actions before any step runs, so no value in
`config/` can reach a cron line at all - and 5-field cron has no every-N-days
field to write one with. Each cadence is therefore a due-check in a step, reading
durable state out of `corpus/corpus.meta.json`. The cron lines that remain are
wake-ups, not schedules.

`models.<role>.hf_base_repo` is optional and sits on the model entry rather than
in `finetune`, because training reads the safetensors repository while the
pipeline reads the GGUF one. Held in two blocks a model swap moves one string and
leaves the other, and a LoRA adapter loads onto a mismatched base without
raising.

See [../../how-to/fine-tune-a-model.md](../../how-to/fine-tune-a-model.md).

## See also

- [../config.md](../config.md) - what a knob is, and what is not one.
- [../../reference/github-actions.md#pipeline-tests](../../reference/github-actions.md#pipeline-tests) - where model inference runs.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - what a run on these settings has actually cost.
- [../../architecture/summarize/model-boundary.md](../../architecture/summarize/model-boundary.md) - what is per model and what is not.
- [summary-length.md](summary-length.md) - the length the prompt asks for, which is editorial rather than per model.
