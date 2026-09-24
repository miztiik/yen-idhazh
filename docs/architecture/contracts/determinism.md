# The Recorded Input Manifest

**Last Updated**: 2026-09-22

What a run records about its own inputs, where each value is read from, and the one alarm built on that record. This page owns the enumeration and what the record cannot see.

**It records and it gates nothing.** No run, no pool, no window and no published number turns on these values: a run whose inputs moved is counted, averaged and published exactly as one whose inputs held still. The record is `RunRecord.inputs` on each day's `run.json`, read by a person and by the console's model-change boundary.

The shapes themselves are contracts like any other; see [schemas.md](schemas.md) for how they are authored and generated.

## `temperature=0` is not determinism, and the pipeline does not run at 0

It is determinism *given identical logits*, which is weaker than it sounds. Everything that changes the logits changes the output while every line of this repository stays the same:

| What moves | Example |
| --- | --- |
| The weights | A quantisation swap, or a re-upload at the same Hugging Face path. |
| The runtime | A llama.cpp rebuild changing a kernel's summation order. |
| The framing | A reworded prompt, a chat template bump, a widened output schema. |
| The batching | `n_ctx`, `n_batch`, `n_ubatch` and thread count all change how partial sums are accumulated. |
| The input | A wider truncation cap, a changed extractor or sanitizer, or a publisher quietly rewriting an article at the same URL. |

**Every committed model entry pins `temperature: 0.2`.** Determinism is not a property a summarizer needs, so the pipeline does not buy one.

**`seed` is what repeatability rests on.** Same inputs and the same seed is the same reply; same inputs and a different seed is a different one. It is never the *determinism* control, because there is no determinism to control - it is the reproducibility control, which is a different and honest claim.

**What this costs, stated.** Two runs over one article can differ in wording with nothing changed and nothing wrong. The gate that would refuse that is retired, and there is no temperature at which it comes back: a summarizer does not need to say a thing the same way twice, and a gate that fires across runner CPU classes for reasons unrelated to a regression gets switched off within a month. What a run records instead is `wording_spread`, a count of how many distinct wordings each item drew, with its denominator, blocking nothing ([../../concepts/evaluation.md](../../concepts/evaluation.md)). Qualification has ten gates and every one of them is asked of every run.

## The record is the enumeration

`PipelineInputs` is a model whose fields **are** the record. It hangs off
`RunRecord.inputs`, one per run, and every value is named rather than hashed.

Two properties fall out of declaring the model rather than assembling a string,
and both are the point. It is the same move as generating schemas from models:

- A field added to the model is recorded by every run from that commit on. There is no second list to remember to update.
- A field that is not declared cannot be forgotten, because it was never claimed to be covered.

**Named values rather than one digest, and that is what makes it a record.** One
opaque hex token affords exactly one operation - equality - which is a gate's
operation and the only one. A set of named values affords reading, so a reader
can see *which* input moved and the console's boundary can say so.

The declared inputs are the weights digest, the quantisation, the runtime build, the chat-template / prompt / output-schema digests, the turn-envelope digest, the truncation cap, the sampling settings, the runtime switches, `n_ctx` / `n_batch` / `n_ubatch` / `n_threads`, the runner class, and the extractor and sanitizer versions. `RunRecord.config_digests` sits beside it and says which config bytes the run read.

**The turn envelope is digested twice, and the second one is not redundant.** The prompt digest covers the envelope already, because the two calls render their own bytes through it. It stops short of two facts all the same: which of the two reply openings a call ends on, and the marker the thinking span stops at. An entry that changed only the string that closes its reasoning block would decode differently and move no rendered prompt, so `turn_markers_sha256` carries the envelope whole - every marker, the system placement and its joiner. **An absent key means a run written before 2026-09-14**, when a marker first became able to move at all; it never means a default value.

**One knob is absent on purpose, and it is the one people look for.** There is no reasoning flag in the stamp. Reasoning is declared by `models.<role>.thinking_close`, so it arrives in the envelope digest and in the rendered prompt's choice of reply opening. A flag beside a marker would be two places to disagree.

**The weights digest answers which bytes decoded, not which bytes config named.** `ModelRef.sha256` is an expectation and the record wants an observation, because the two disagreeing is exactly the event this exists to expose. Production has not closed that gap yet; what stands in for it is below.

**Prompts and templates are digested, never stored.** A prompt in a committed payload would put text into a permanent record that nothing downstream needs, and the digest answers the only question anyone asks of it: did it move?

**There is one comparison and it is `changed_inputs`.** It names the input that moved, which is what a reader and the console's model-change boundary both need; a digest over the whole record could only say that one did. `PipelineInputs.fingerprint()` was that digest, and it went on 2026-09-21 with the decode stamp beside it - nothing called either, and both existed to answer "did two runs ask for the same thing?", which is a question about determinism and not a property this pipeline claims. Rows in `state/scores/` written before the manifest replaced the digest still carry their own stamp; nothing rebuilds one, and expanding them was never possible in any case (see the rejected alternatives below).

## The one alarm

`prose_changed_alone` compares this run's record against the newest earlier run
in the same `RunManifest` and answers one question: **did the words we ask for
move while the model and the binary held still?**

It is empty on a first run, on a run where nothing moved, and on a run where the
weights or the build moved too - the last of those is a model change, which an
operator already reads off the boundary the console draws. What is left is the
case nothing else can see: the same weights, the same binary, and different
words asked of them.

**It reports and it never blocks.** The run publishes, every number is read, and
the warning names which input moved. The comparison is against one earlier
payload the caller already holds, so it costs the same on a repository of one
published day and of a thousand (Guardrail #12).

### Where each input comes from

Every field is read from the thing it describes, not from a literal beside the call:

| Field | Read from | When that source is silent |
| --- | --- | --- |
| `model_sha256` | `models.summarizer.sha256` in the active model file, which is not yet the observation the contract asks for - see the gap below | Raises. A run without a recorded weights digest stops rather than stamping one that validates and says nothing. |
| `runtime_build` | `LLAMA_CPP_BUILD`, handed to the work step by the `plan` job that read `config/llama-cpp-pin.json` - the same file the install reads, so the build stamped and the build installed are one answer | `build-not-recorded`, and the same when `model_server.base_url` is not loopback, because the environment names a build on this machine and that is not where the weights decoded. It is not a llama.cpp release tag and cannot be read as one. |
| `chat_template_sha256` | the Jinja source `llama-server` returns from `GET /props` - the template it will apply to every request | a digest of `chat-template-not-recorded`. |
| `runner_class` | `RUNNER_ENVIRONMENT` / `RUNNER_OS` / `RUNNER_ARCH` | `local/<system>/<machine>` from `platform`. A machine that publishes none of the three is a developer machine and says so. |
| `host_cpu` (not digested) | the `model name` line of `/proc/cpuinfo` | `platform.processor`, then the architecture. |

Degrading is not the same as inventing. A degraded run stamps a value nothing else can produce, so its rows sit apart from every run whose runtime was named, and a reader can see which is which without being told (Guardrail #10, section 1a).

### What the record still cannot see

**`model_sha256` is what config expected, not what the server opened.** The
`work` job checks the file on disk against `models.summarizer.sha256` with
`sha256sum` before `llama-server` starts, on a cache hit as well as a miss, and
its health check asserts the server serves the configured alias and loaded the
configured filename. That gate is what lets the config value stand in for the
observed one. `/props` names the file the server opened; it does not digest it,
and digesting five gigabytes in every shard is a cost nobody has measured against
the gate it would replace. The qualification path does digest the file it is
about to run (`_candidate_identity`), so the observation exists and production
has not adopted it. When `model_server.base_url` is not loopback the run cannot
see which build answered either, so `runtime_build` records `build-not-recorded`
rather than this machine's; reconciling the record against the server's own
`/props` is not done.

**A build recorded for a server on another machine would be borrowed, so it is
not recorded at all.** Every other field of the manifest is read from the process
that ran the pipeline, and `LLAMA_CPP_BUILD` names the build installed there - so
against a second machine the tag is well formed, validates, and is false. That
costs one reading. Two runs against two different builds elsewhere record the
same value, so a build change reads as no change, and `prose_changed_alone`
compares the machine inputs first - it will call a prompt change a lone one on a
day the build moved as well. This was already true of a developer machine that
pins nothing. It is now true of a configuration this project supports, and what
would settle it is reading the server's own `/props`.

**Fetch policy is outside the record, and that one is an omission rather than a
decision.** `FETCHER_VERSION` in `backend/idhazh/fetch.py` is bumped when fetch
behaviour changes, and nothing records it - `PipelineInputs` carries the
extractor and the sanitizer versions and not this one. Changing which pages a run
is allowed to read therefore leaves the record where it was, so two runs under
different fetch policies read as one
([../sources/trust-boundary.md](../sources/trust-boundary.md)). Adding it is one
field and one changelog entry; it is unwritten because nothing has yet needed to
tell two fetch policies apart.

**The article itself is deliberately absent.** `PipelineInputs` answers which
pipeline configuration ran, and the same value has to group many items. A record
that moved per article could not, which is what makes a skip a different design
rather than a missing field.

## Which knobs the record carries

The model file spells llama-server's own flags, so the record enumerates flags rather than field names. `idhazh.fingerprint.DIGESTED_FLAGS` is the list, and it is a choice about which switches can move a decode rather than a closed set over a declared shape - there is no declared shape to close over any more (`CLAUDE.md` Guardrail #3, owner ruling 2026-09-21).

**A flag the file leaves out records as `runtime-default`.** What the server picks is a real and different choice from pinning a value, and writing our guess at its default into the record would file a guess as a measurement (Guardrail #10). A bare flag - one the file names with no argument - records as `set`.

**What replaced the closed set is llama-server itself.** The list it held closed existed to refuse an option that reached no stamp; a misspelled flag is now refused by the binary at every server start, which names it and does not start. That is louder, it is free, and it costs no written entry per option.

| Knob | Where it lands |
| --- | --- |
| `--ctx-size`, `--batch-size`, `--ubatch-size`, `--threads` | Their own fields, under this project's names for them. They change how the partial sums accumulate. |
| `temperature`, `top_p`, `seed`, and every other sampler the entry declares | `sampling`, one key each, and the whole block the request sent. Three were read by name until 2026-09-23 while the body carried thirteen, so ten keys could move the decode with this record unchanged. A key the file leaves out is a key that is absent: there is no list of every sampler to write a default against, and inventing one would file a guess as a measurement (Guardrail #10). No span budget is in it, because no span carries one: the two decode caps left the settings on 2026-09-21, and what bounds a span is the window and the per-request timeout, both enumerated elsewhere. |
| `-ctk`, `-ctv`, `-fa`, `-np`, `-tb` and the cache and template switches | `runtime_flags`, one key each, under llama-server's own flag names. A quantised KV cache, another attention kernel, a second slot and a different prompt-thread count each change how the partial sums accumulate. |
| The turn envelope | `turn_markers_sha256`, and `prompt_sha256` as well, because the prompt is rendered through the envelope. |

**The switches fold into one field rather than one each, and that is not a shortcut.** They are absent on almost every run, so a column each would be a dozen lines nobody reads. One field, read key by key, is what lets the console name the switch that moved while still costing the contract one entry.

**A temperature is recorded to four decimal places, and that is a shipped tolerance.** Two temperatures closer together than 1e-4 record as the same value, so the console reports no change between them. It is the right tolerance - no sampler here is steered by the fifth decimal, and a full float repr would report a change every time a JSON round trip landed one bit out - but it is a choice, so it is written here and asserted on both sides in `backend/tests/test_fingerprint.py`.

**`runtime_flags` records the request, not the applied configuration.** Every key is read off the model file, so a llama.cpp build that changes its own default for a flag we leave out moves the decode with this mapping unchanged. `runtime_build` is the only field that catches that, which is why a reading either side of a build change is compared on the build first.

### Design rationale - the two settings blocks are mappings, not joined strings

Both were one `a=1;b=2` string until 2026-09-22. Joined, the whole field moved when any one term did, and two of the things that move a term move no token at all: a rename, and a setting that stopped being sent.

Plan 41 did both in one week. The model file took llama-server's own flag names on 2026-09-21, so `cache_type_k=q8_0` became `-ctk=q8_0` - the same switch, the same value, a different word. The same plan deleted two decode caps that bounded nothing. Joined, the console would have told an operator that **the sampling settings, the model server switches and the turn markers changed** on the first day plan 41 published: three of seventeen recorded inputs, all false, on a change whose whole intent was to emit the same flags verbatim. A published day is never rewritten, so the rule would have been permanent, and every reading either side of it marked uncomparable.

Read key by key it is not a change at all. The console's rule already says a day that only STOPPED using one of yesterday's values changed nothing, so a deleted setting is a key that is absent. A renamed switch is read through `RENAMED_FLAGS` in `backend/idhazh/contracts/fingerprint.py` and compares against itself. The rule is computed when the page renders rather than stored, so it applies to the days already published as readily as to tomorrow's.

The third field, `turn_markers_sha256`, could not be saved the same way: a published day carries the digest and not the markers, so there is nothing to recompute from. It moved once on 2026-09-22 for a reason worth naming - every one of the eight markers came back byte-identical when they stopped being typed and started being read off the model's own template, and the digest moved because it covered `string.Template`'s source, where `$role` and `${role}` differ and substitute the same. `turn_markers_digest` now digests what the markers write rather than what writes them, so a placeholder spelling can never move the record again.

The migration is a read-side one, in the same commit as the shape (`CLAUDE.md` section 11). One old format is parsed and no chain of them: three historical spellings exist and all three split the same way, because a term the rename table does not name keeps its own name and compares against itself.

## `host_cpu` is recorded and never digested

It is a diagnostic, outside `PipelineInputs`, so exclusion is structural rather than a filter someone can forget.

Including it would make every runner a different record, which would hide the one failure this exists to catch: the same inputs producing different words on different hardware. It is the only field that *explains* a violation, so it has to be recorded and it must not be part of the identity.

## Two stages, one record

The inputs are observed in `work` and committed in `assemble`:

1. `stage_work` is the only stage that can see the runtime, so it writes the record into the run's items directory as `inputs.json`.
2. That directory is what a shard uploads, so the record survives a runner whose checkout is thrown away when the job ends.
3. `stage_assemble` reads it and hangs it on the run record it is about to write.

One name rather than one per shard. Every shard of a run observes the same
configuration and writes the same bytes, so the atomic rename settles it and
there is nothing to reconcile.

## What a violation does

`determinism_violation` is a column on the eval row. Its count reaches the day
metrics and the run record, the console reads it, and a row carrying it is kept
out of the training corpus. The build does not fail.

**A production run never sets it.** Setting it needs two decodes of one prompt to
compare, and a run summarizes each item once. Repeats happen in qualification,
which is where both the gate and the diagnostic live.

**The gate is gone and the column is not.** There is no determinism gate at any
temperature: a summarizer is not asked to say a thing the same way twice, so
`wording_spread` is what a qualification run records - how many distinct wordings
each item drew, against its own denominator - and it blocks nothing.
`determinism_violation` survives as a column because the days already committed
carry it and the console still reads them.

A gate that failed the build would fire across runner CPU classes for reasons
unrelated to any regression, and a flaky gate gets switched off within a month -
at which point the project has neither the gate nor the signal. Recorded and
counted, it stays visible and stays trustworthy.

The comparison is over the **published words only** - the generated title and
summary - so a re-run that produced the same text in a different wall-clock or
token count does not read as drift. Key points were in it until 2026-09-24 and
left with the field.

## Design rationale

**A record, not a gate.** The same enumeration was once reduced to one digest,
and the digest gated a skip and keyed an eval window. A digest affords one
operation - equality - so anything built on it treats every input as equally
disqualifying, and a repository whose prompts and vocabularies change weekly
moves the digest faster than any window is wide. That turns evolution into a
fault. The enumeration is the half worth its cost: it makes "nothing changed"
checkable rather than asserted, for one model and one module.

**Named values rather than a digest.** A reader wants to know which input moved,
and the console's model-change boundary has to say so. Equality answers neither
question - which is also why nothing downstream may key on this record.

**The chat template is read from the running server rather than reconstructed.**
The template ships inside the GGUF and the server applies it, so the pipeline
never renders one and has nothing local to digest that is not either the model
id, which never moves, or an invented restatement of the request shape. `GET
/props` returns the Jinja source the server will use. That is the same doctrine
as the weights digest: the record is an observation of the runtime, and the
runtime disagreeing with config is the event it exists to expose.

**An absent weights digest raises where an absent build degrades.** A degraded
value stamps apart from every run whose source did answer, so it records a fact.
A placeholder weights digest stamps *together* with every other unmeasured run,
so it records nothing while reading as a measurement - the one shape that makes
the record lie (Guardrail #10).

## Rejected alternatives

| Option | Why rejected |
| --- | --- |
| Trust `temperature=0, seed=0` and record nothing | Every class in the table at the top of this page moves an output while this repository holds still, including a publisher rewriting an article at the same URL. |
| Fail the build on a violation | It fires across runner CPU classes for reasons unrelated to a regression, and a flaky gate gets switched off within a month. Record it, count it, do not smooth it. |
| Include `host_cpu` in the identity | Every runner becomes a different record, which hides the cross-hardware divergence the record exists to expose. |
| Hand-assemble the record from a list of names | A second enumeration to keep in step with the model, where forgetting an entry is silent by construction. |
| Store the prompt text on the record | Puts text nothing downstream reads into a permanent committed payload; the digest answers the only question asked of it. |
| Write an eval row for an unchanged item | Makes every trend on the dashboard a function of how often the job ran rather than of how the summaries changed. |
| Skip an item whose recorded inputs did not move | This record answers which pipeline configuration ran, so its value has to group many items. A safe skip needs a per-item work identity carrying the article bytes as well as the configuration, which is a different payload and a different design. |
| Put the excluded knobs on the record the way `host_cpu` is | `host_cpu` earns its place because it explains a violation. A KV cache setting explains nothing on its own, and every extra column costs every future run. |
| Raise when `LLAMA_CPP_BUILD` is absent, the way a missing weights digest raises | It would stop every developer run and every test that composes the stages, to protect a field that explains a run rather than gating one. A recorded absence stamps apart from every pinned run, says the same thing, and still runs. |
| Write the run record from `stage_work` | A shard's checkout is discarded when the job ends, so the record would never reach a committed file. |
| Have `assemble` rebuild the record from config | It runs on another machine after the server is gone, so it would record its own runner class and its own host as the ones that summarized nothing. |
| Backfill the stamps already in `state/scores/` | They predate any recorded runtime, so expanding them means manufacturing a measurement nobody took (Guardrail #10). They stay unexpandable, and that is the honest record. |
| Identify a run by the model slug | A slug does not move when the prompt, the truncation cap or the runtime build moves, and all three move the words. |
| Digest the request envelope instead of asking the server for its template | The envelope is our own shape and the prompt and output-schema digests already carry it. Reconstructing a template the server owns restates config under a name that promises an observation. |

## See also

- [schemas.md](schemas.md) - how these shapes are authored, versioned and generated.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the run, which measures every item it produces because nothing skips.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - what an eval row measures, and why an empty re-run must not write one.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - the identity and replay requirements for a model change.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - where a measured number carries its hardware and date.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10, section 11.
