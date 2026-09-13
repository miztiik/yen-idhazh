# Determinism and the Recorded Input Manifest

**Last Updated**: 2026-09-12

What a run records about its own inputs, the one alarm built on that record, and how the pipeline notes the times "nothing changed" turns out to be false. This page owns the enumeration, where each input is read from, and the violation policy.

**It records and it gates nothing.** Owner decision, 2026-09-10. Until 2026-09-12 the same enumeration was reduced to one digest, `pipeline_fingerprint`, which did two jobs and did neither. The skip-if-unchanged half was never wired to a caller. The eval-window half withheld a quality number until N consecutive run-days ran at one digest - and the digest moves on any of seventeen inputs, so measured over the whole committed ledger on 2026-08-27 the longest unbroken run at one digest was three days against a requirement of ten, reached zero times. It turned evolution into a fault. What is left is the reading: `RunRecord.inputs` on each day's `run.json`, read by a person and by the console's model-change boundary, and by nothing that decides anything.

The shapes themselves are contracts like any other; see [schemas.md](schemas.md) for how they are authored and generated.

## `temperature=0` is not determinism

It is determinism *given identical logits*. Everything that changes the logits changes the output while every line of this repository stays the same:

| What moves | Example |
| --- | --- |
| The weights | A quantisation swap, or a re-upload at the same Hugging Face path. |
| The runtime | A llama.cpp rebuild changing a kernel's summation order. |
| The framing | A reworded prompt, a chat template bump, a widened output schema. |
| The batching | `n_ctx`, `n_batch`, `n_ubatch` and thread count all change how partial sums are accumulated. |
| The input | A wider truncation cap, a changed extractor or sanitizer, or a publisher quietly rewriting an article at the same URL. |

`seed` is *dead code under greedy decoding*. It is enumerated as an input so a future move off greedy cannot change an output silently, and it is never cited as the determinism control.

## The record is the enumeration

`PipelineInputs` is a model whose fields **are** the record. It hangs off
`RunRecord.inputs`, one per run, and every value is named rather than hashed.

Two properties fall out of declaring the model rather than assembling a string,
and both are the point:

- A field added to the model is recorded by every run from that commit on. There is no second list to remember to update.
- A field that is not declared cannot be forgotten, because it was never claimed to be covered.

**Named values rather than one digest, and that is what makes it a record.** One
opaque hex token affords exactly one operation - equality - which is a gate's
operation and the only one. A set of named values affords reading, so a reader
can see *which* input moved and the console's boundary can say so. Ruled by
Fowler, 2026-09-12.

The declared inputs are the weights digest, the quantisation, the runtime build, the chat-template / prompt / output-schema digests, the truncation cap, the sampling spelling, `n_ctx` / `n_batch` / `n_ubatch` / `n_threads`, the runner class, and the extractor and sanitizer versions. `RunRecord.config_digests` sits beside it and says which config bytes the run read.

**The weights digest is of the file the runtime opened, not the one config named.** `ModelRef.sha256` is an expectation; the record is an observation. The two disagreeing is precisely the event this exists to expose.

**Prompts and templates are digested, never stored.** A prompt in a committed payload would put text into a permanent record that nothing downstream needs, and the digest answers the only question anyone asks of it: did it move?

## The one alarm

`prose_changed_alone` compares this run's record against the newest earlier run
on the same manifest and answers one question: **did the words we ask for move
while the model and the binary held still?**

It is empty on a first run, on a run where nothing moved, and on a run where the
weights or the build moved too - the last of those is a model change, which an
operator already reads off the boundary the console draws. What is left is the
case nothing else can see: the same weights, the same binary, and different
words asked of them.

**It reports and it never blocks.** The run publishes, every number is read, and
the warning names which input moved. Owner decision, 2026-09-10. The comparison
is against one earlier payload the caller already holds, so it costs the same on
a repository of one published day and of a thousand (Guardrail #12).

### Where each input comes from

Every field is read from the thing it describes, not from a literal beside the call:

| Field | Read from | When that source is silent |
| --- | --- | --- |
| `model_sha256` | `models.summarize.sha256` in config, which is not yet the observation the contract asks for - see the gap below | Raises. A run without a recorded weights digest stops rather than stamping one that validates and says nothing. |
| `runtime_build` | `LLAMA_CPP_BUILD`, set by `digest.yml` beside the download it checks against a recorded sha256 | `build-not-recorded`. It is not a llama.cpp release tag and cannot be read as one. |
| `chat_template_sha256` | the Jinja source `llama-server` returns from `GET /props` - the template it will apply to every request | a digest of `chat-template-not-recorded`. |
| `runner_class` | `RUNNER_ENVIRONMENT` / `RUNNER_OS` / `RUNNER_ARCH` | `local/<system>/<machine>` from `platform`. A machine that publishes none of the three is a developer machine and says so. |
| `host_cpu` (not digested) | the `model name` line of `/proc/cpuinfo` | `platform.processor`, then the architecture. |

Degrading is not the same as inventing. A degraded run stamps a value nothing else can produce, so its rows sit apart from every run whose runtime was named, and a reader can see which is which without being told (Guardrail #10, section 1a).

### Current implementation gap

Two things the contract above describes are still not observed.

`model_sha256` is what config expected, not what the server opened. The `work`
job checks the file on disk against `models.summarize.sha256` with `sha256sum`
before `llama-server` starts, on a cache hit as well as a miss, and its health
check asserts the server serves the configured alias and loaded the configured
filename. That gate is what lets the config value stand in for the observed one.
`/props` names the file the server opened; it does not digest it, and digesting
five gigabytes in every shard is a cost nobody has measured against the gate it
would replace. The qualification path does digest the file it is about to run
(`_candidate_identity`), so the observation exists and production has not adopted
it.

The five blind spots below are still outside the record.

Article input is deliberately not a `PipelineInputs` field: that model answers
"which pipeline configuration", and the same value must group many items.

**There is no skip, and there is no longer a plan for one.** `classify`,
`SKIPPABLE` and the four-way `Observation` enum were deleted on 2026-09-12 along
with the digest, because nothing had ever called them and nothing had asked.
A run re-summarizes every item it plans, which is what it already did. A safe
skip would need a per-item work identity carrying the article bytes as well as
the configuration; that identity was never written, and writing one is a design
somebody would have to argue on its own evidence.

Fetch policy is outside the record, and unlike the two above that is an omission
rather than a decision. `FETCHER_VERSION` in `backend/idhazh/fetch.py` is bumped
when fetch behaviour changes, and nothing records it - `PipelineInputs` carries
the extractor and the sanitizer versions and not this one. Changing which pages a
run is allowed to read therefore leaves the record where it was, so two runs
under different fetch policies read as one. The constant was bumped to
`idhazh-fetch-2` on 2026-09-02 when `protego` replaced `urllib.robotparser`
([../sources/trust-boundary.md](../sources/trust-boundary.md)), which is the
change that showed the gap. Adding it is one field and one changelog entry; it is
unwritten because nothing has yet needed to tell two fetch policies apart in the
ledger.

### A placeholder digest used to stamp clean, and now it raises

Sixty-four zeroes satisfy the `Sha256` type. A stamp built on them validated,
published and said nothing at all about which weights ran - so "nobody measured
the weights" and "these are the weights" were the same fingerprint. Every stamp
written that way was valid and false.

`build_inputs` now refuses an absent or placeholder `model_sha256` and names the
file whose digest is missing. Refusing is right where degrading was right for
`runtime_build` and `chat_template_sha256`: those record a source that did not
answer, which is a fact about the run and stamps apart from every run whose
source did answer. A placeholder weights digest records nothing and stamps
*together* with every other unmeasured run, which is the one shape that makes the
ledger lie (Guardrail #10).

The defect was found by the 2026-08-26 model qualification, which is the first
thing that had a reason to compare an expectation against an observation
([../../reference/measurements.md](../../reference/measurements.md#two-defects-the-qualification-exposed-both-fixed)).

## Which inference knobs the stamp carries

"A field that is not declared cannot be forgotten" holds only if somebody writes down what is not declared. `idhazh.fingerprint.NOT_DIGESTED` is that record, and a contract test holds it closed against `InferenceConfig`: each knob is either digested or named there with a reason. Add a knob but classify nothing, and the test fails. It names the knob.

Ten of the nineteen knobs stay outside the stamp. Nine of the ten reach `server_argv`; the tenth is a request timeout. Five of the ten can move the words:

| Knob | In the stamp? | Why |
| --- | --- | --- |
| `n_ctx`, `n_batch`, `n_ubatch`, `n_threads` | yes, under their own names | They change how the partial sums accumulate. |
| `temperature`, `top_p`, `seed`, `max_output_tokens`, `thinking` | yes, folded into `sampling` | One canonical spelling of the decoding parameters. |
| `cache_type_k`, `cache_type_v` | **no - blind spot** | A quantised KV cache changes the attention arithmetic. |
| `flash_attention` | **no - blind spot** | Another kernel adds the same values in another order. |
| `n_parallel` | **no - blind spot** | Slots divide the context, which changes the batch shapes. |
| `n_threads_batch` | **no - blind spot** | Prompt threads change how the partial sums accumulate. |
| `load_mode` | no, and safe | mmap and mlock move where the weights sit, not what they hold. |
| `priority`, `poll` | no, and safe | Scheduler and wait behaviour. They calculate nothing. |
| `startup_warmup` | no, and safe | A pass before the run. It decodes nothing that we keep. |
| `request_timeout_minutes` | no, and safe | A clock bound on one POST. It stops a call, it does not reword one. |

The five blind spots are real. Move one and a summary can change while the stamp holds still. They stay undigested here on purpose: adding a field to `PipelineInputs` resets every fingerprint, and the 2026-08-27 summarizer swap already spent one reset. Digesting them apart from a reset something else is paying for spends the reset twice, so the next one to move the model ref is the commit that should carry them.

`server_argv` used to claim in its own docstring that every knob it passes is a fingerprint input. It never was. The docstring now points at `NOT_DIGESTED` rather than claim coverage nobody checked.

## `host_cpu` is recorded and never digested

It is a diagnostic, outside `PipelineInputs`, so exclusion is structural rather than a filter someone can forget.

Including it would make every runner a different record, which would hide the one failure this exists to catch: the same inputs producing different words on different hardware. It is the only field that *explains* a violation, so it has to be recorded and it must not be part of the identity.

## The ledger is retired

`state/fingerprints.csv` held one row the first time a digest was seen, expanding
it into every component that produced it. Nothing has written it since
2026-09-12: a digest with nothing to expand it into is meaningless hex three
years from now, and once the digest went the expansion had nothing left to
explain. The ten rows it holds still read back. `FingerprintRow`, its schema and
the file go together in the commit that drops the field from every contract.

What replaced it is the same enumeration on the run record, which a reader
already opens for everything else a run did, and which needs no join.

### Two stages, one record

The inputs are observed in `work` and committed in `assemble`:

1. `stage_work` is the only stage that can see the runtime, so it writes the record into the run's items directory as `inputs.json`.
2. That directory is what a shard uploads, so the record survives a runner whose checkout is thrown away when the job ends.
3. `stage_assemble` reads it and hangs it on the run record it is about to write.

One name rather than one per shard. Every shard of a run observes the same
configuration and writes the same bytes, so the atomic rename settles it and
there is nothing to reconcile.

## Intended violation handling

When wired, `determinism_violation` lands on the eval row and its count lands on
the run record. The build does not fail.

A gate here would fire across runner CPU classes for reasons unrelated to any regression, and a flaky gate gets switched off within a month - at which point the project has neither the gate nor the signal. Recorded and counted, it stays visible and stays trustworthy.

The comparison is over the **published words only** - generated title, summary
and key points - so a re-run that produced the same text in a different
wall-clock or token count does not read as drift.

## Design rationale

**The digest was deleted as a gate and as the eval-window key, and the
enumeration was kept (2026-09-12).** Owner decision, 2026-09-10, under
`CLAUDE.md` section 0. The enumeration is the part that was worth its cost: it
is what makes "nothing changed" checkable rather than asserted. The digest over
it was worth nothing at all, because both jobs it was built for failed. The skip
was never wired - no `skip_if_unchanged` key, no caller, no branch - and the
window never opened, because the digest moved faster than the window was wide.

What that cost, stated rather than implied. The skip is gone as a design, not
deferred: a safe skip needed a per-item work identity carrying the article bytes
as well as the configuration, that identity was never written, and nothing has
asked for it since. The `classify` helper, `SKIPPABLE` and the four-way
`Observation` enum went with it rather than sitting unwired for another quarter.
A run now re-summarizes every item it plans, which is what it already did.

What it bought. A quality number over a window that spans a reworded prompt is a
number again: measured on the base commit `0e049ed8` over
`tests/fixtures/evals/prompt-changed-window.csv`, three rows of one day summarised
as two cohorts of two rows and one row, so the day had no faithfulness figure
over its own window; after, one cohort of three rows at 0.80.

Enumerating sixteen ways an output can move and finding that eleven are silent is what makes the stamp worth its cost. The alternative is trusting `temperature=0`, which is not a claim about the pipeline at all - it is a claim about the sampler, and the sampler is not where drift comes from. The cost is one model, one module and one CSV; the benefit is that "nothing changed" becomes checkable rather than asserted. Authority: Andre ([../../../.github/agents/andre.agent.md](../../../.github/agents/andre.agent.md)).

Digesting the model's own serialization rather than a hand-written concatenation is the same move as generating schemas from models: it removes a second list that has to be kept in step by hand, and the class of bug where someone adds an input and forgets to stamp it stops existing. Authority: Fowler.

The scope statement above is honest, so the defect was the `server_argv` docstring that claimed more coverage than the scope statement gave. Fixing the sentence alone would have left the gap unwritten, and digesting the five blind spots here would have burned the eval-clock reset that the model swap already pays for. The third option is what shipped: name the exclusions, say which ones matter, and make a contract test hold the list closed. The list now costs one line per knob and cannot go stale in silence. Authority: Fowler ([../../../.github/agents/fowler.agent.md](../../../.github/agents/fowler.agent.md)).

The three identity fields were a literal, a model slug and a second literal, and every one of them held still while the thing it named moved. `pipeline_fingerprint` - not `model_id` - is the attribution key on an eval row, so a slug that does not move when the prompt, the truncation cap or the llama.cpp build moves attributes a changed score to an unchanged pipeline. Reading each field from the thing it describes is what makes the key mean what the ledger says it means. Authority: Andre, with Carmack on the two runtime fields.

The chat template is read from the running server rather than reconstructed. The template ships inside the GGUF and the server applies it, so the pipeline never renders one and had nothing local to digest that was not either the model id, which never moves, or an invented restatement of the request shape. `GET /props` returns the Jinja source the server will use, which is the same doctrine as the weights digest: the stamp is an observation of the runtime, and the runtime disagreeing with config is the event the stamp exists to expose. Authority: Andre.

The record is written in `work` and committed in `assemble` because a work shard's checkout does not survive its job. Four to eight shards run the same inputs on disposable runners and upload one directory each; only `assemble` has a checkout that is committed. Writing the run record inside `stage_work` would write it into a directory thrown away with the runner. Carrying it as a payload keeps the observation where it is observable and the commit where commits happen (section 1a). Authority: Fowler.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Trust `temperature=0, seed=0` and skip the stamp | Eleven of sixteen enumerated drift sources are silent without it, including a publisher rewriting an article at the same URL. | Andre |
| Fail the build on a determinism violation | It will fire across runner CPU classes for reasons unrelated to a regression, and a flaky gate gets switched off within a month. Record it, count it, do not smooth it. | Andre |
| Include `host_cpu` in the digest | Every runner becomes a different fingerprint, which hides the cross-hardware divergence the stamp exists to expose. | Andre |
| Hand-assemble the digest input from a list of names | A second enumeration to keep in step with the model, and forgetting an entry is silent by construction. | Fowler |
| Store the prompt text on the ledger row | Puts text nothing downstream reads into a permanent committed record; the digest answers the only question asked of it. | Andre |
| Write an eval row for an unchanged item | Makes every trend on the dashboard a function of how often the job ran rather than of how the summaries changed. | Andre |
| Digest the five blind spots now | Every fingerprint resets when they enter the stamp, and the 2026-08-27 model swap reset them all anyway. Two resets buy one. | Fowler |
| Put all ten undigested knobs on the ledger row the way `host_cpu` is | `host_cpu` earns its column because it explains a violation. A KV cache setting explains nothing on its own, and ten more columns cost every future row. | Fowler |
| Correct the fields and leave the docstring | The fields were never the defect. The scope statement already said an undeclared field is not covered; only the docstring claimed otherwise. | Fowler |
| Delete the false sentence and add nothing | The gap stays real and stays unwritten, so the next reader re-derives it from the argv list. | Fowler |
| Keep `model_id` as the attribution key and leave the three identity fields alone | A slug does not move when the prompt, the truncation cap or the runtime build moves, and all three move the score. | Andre |
| Digest the request envelope instead of asking the server for its template | The envelope is our own shape and the prompt and output-schema digests already carry it. Reconstructing a template the server owns restates config under a name that promises an observation. | Andre |
| Raise when `LLAMA_CPP_BUILD` is absent, the way a missing weights digest raises | It would stop every developer run and every test that composes the stages, to protect a field that explains a run rather than gating one. A recorded absence stamps apart from every pinned run, says the same thing, and still runs. | Carmack |
| Write the run record from `stage_work` | A shard's checkout is discarded when the job ends, so the record would never reach a committed file. | Fowler |
| Have `assemble` rebuild the stamp from config | It runs on another machine after the server is gone, so it would record its own runner class and its own host as the ones that summarized nothing. | Carmack |
| Backfill the stamps already in `state/scores.csv` | They predate any recorded runtime, so expanding them means manufacturing a measurement nobody took (Guardrail #10). They stay unexpandable, and that is the honest record. | Andre |
| A `reason` or `superseded_by` column on the ledger row | Nothing parses a sentence in a CSV, and the machine-readable "why" already lives in `state/validation-<date>.csv`. | Fowler |

## See also

- [schemas.md](schemas.md) - how these shapes are authored, versioned and generated.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the run, which measures every item it produces because nothing skips.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - what an eval row measures, and why an empty re-run must not write one.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - the identity and replay requirements for a model change.
- [../../reference/measurements.md](../../reference/measurements.md) - where a measured number carries its hardware and date.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10, section 11.
