# Determinism and the Pipeline Fingerprint

**Last Updated**: 2026-08-25

How the pipeline proves a re-run changed nothing, and how it records the times that claim turns out to be false. This page owns the stamp, the ledger that expands it, the skip rule built on it, and the violation policy.

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

## The stamp is the enumeration

`PipelineInputs` is a model whose fields **are** the fingerprint, and the digest is taken over that model's own canonical serialization:

```
pipeline_fingerprint = sha256(canonical_json(PipelineInputs))
```

Two properties fall out of digesting the model rather than a hand-assembled string, and both are the point:

- A field added to the model changes every fingerprint, automatically. There is no second list to remember to update.
- A field that is not declared cannot be forgotten, because it was never claimed to be covered.

The declared inputs are the weights digest, the quantisation, the runtime build, the chat-template / prompt / output-schema digests, the truncation cap, the sampling spelling, `n_ctx` / `n_batch` / `n_ubatch` / `n_threads`, the runner class, and the extractor and sanitizer versions.

**The weights digest is of the file the runtime opened, not the one config named.** `ModelRef.sha256` is an expectation; the stamp is an observation. The two disagreeing is precisely the event this exists to expose.

**Prompts and templates are digested, never stored.** A prompt in a committed ledger would put text into a persisted payload that nothing downstream needs, and the digest answers the only question anyone asks of it: did it move?

### Current implementation gap

The contract above is not fully implemented. `stage_work` passes
`ModelRef.sha256` - what config expected, not what the server opened - and
records the literal `llama-server-local` as the runtime build. It does not
observe the GGUF file the server opened or the production llama.cpp build.

The zero-digest half of that gap is closed. `build_inputs` raises on a missing
or placeholder digest instead of substituting sixty-four zeroes, so a run
without a recorded weight digest stops rather than stamping one that validates
and says nothing (Rule #10). The `work` job checks the file on disk against
`models.summarize.sha256` with `sha256sum` before `llama-server` starts, on a
cache hit as well as a miss, and its health check asserts the server serves the
configured alias and loaded the configured filename. That gate is what lets the
config value stand in for the observed one until the observation is wired.

What remains matters most during a model swap: a changed runtime can still look
unchanged. The work command must receive the observed GGUF SHA-256 and runtime
build from the process that downloaded and started them, compare the GGUF digest
with config, and carry both into `PipelineInputs`. Until then, fingerprint rows
do not prove runtime identity.

The remaining identity fields are also incomplete: `stage_work` uses the model
id as chat-template identity and `local` as runner class.

Article input is deliberately not a `PipelineInputs` field: that model answers
"which pipeline configuration", and the same value must group many items. The
missing article digest belongs in a separate per-item work identity used by a
future skip key.

The ledger and skip path are not wired into production. `stage_work` computes a
fingerprint but never reads `state/fingerprints.csv` or calls `classify`;
`assemble` never calls `append_new`; and the committed ledger has only its
header. The sections below describe the intended contract and tested helpers,
not current run behaviour.

The Qwen3.5 adoption plan defers skip wiring. A future skip needs a separate
typed per-item work identity containing both article-input digest and pipeline
fingerprint. Article identity does not belong inside the configuration
fingerprint.

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

The five blind spots are real. Move one and a summary can change while the stamp holds still. They stay undigested here on purpose: row 4 of [`../../../TODO/20260825-qwen35-9b-swap-plan.md`](../../../TODO/20260825-qwen35-9b-swap-plan.md), "wire truthful fingerprint identity and model-separated drift", digests them, and that row resets every fingerprint anyway. Digesting them here would spend that reset twice.

`server_argv` used to claim in its own docstring that every knob it passes is a fingerprint input. It never was. The docstring now points at `NOT_DIGESTED` rather than claim coverage nobody checked.

## `host_cpu` is recorded and never digested

It sits on the ledger row, outside `PipelineInputs`, so exclusion is structural rather than a filter someone can forget.

Including it would make every runner a different fingerprint, which would hide the one failure the stamp exists to catch: the same inputs producing different words on different hardware. It is the only field that *explains* a violation, so it has to be recorded and it must not be digested.

## The ledger contract (not wired)

`state/fingerprints.csv` is intended to be **append-only and never pruned**, one
row the first time a stamp is seen. Each row expands the digest into every
component that produced it, plus the host.

Without it a fingerprint is meaningless hex three years from now - it would prove two runs differed while saying nothing about how.

The column order is defined once, by the contract, and flattened one level so every cell is a scalar. The committed header is asserted against that definition, because a hand-edited header would silently reorder every future row.

## Future skip uses work identity, not fingerprint alone

A safe skip compares a future per-item `WorkIdentity` containing both pipeline
fingerprint and article-input digest:

| Prior work identity | Then | Meaning |
| --- | --- | --- |
| absent | `first_run` | run the work |
| different pipeline or article digest | `inputs_changed` | run the work |
| same | `unchanged` | do nothing, and write no eval row |
| same, forced run, different words | `determinism_violation` | record it |

The current `classify` helper compares only pipeline fingerprint. It is not wired
and is insufficient for skip because a publisher can change article bytes at
the same URL. Replace or expand it with `WorkIdentity` before use.

Under the future safe path, an unchanged item writes no eval row. The violation
case is observable only when a matching work identity is forced to run.

## Intended violation handling

When wired, `determinism_violation` lands on the eval row and its count lands on
the run record. The build does not fail.

A gate here would fire across runner CPU classes for reasons unrelated to any regression, and a flaky gate gets switched off within a month - at which point the project has neither the gate nor the signal. Recorded and counted, it stays visible and stays trustworthy.

The comparison is over the **published words only** - generated title, summary
and key points - so a re-run that produced the same text in a different
wall-clock or token count does not read as drift.

## Design rationale

Enumerating sixteen ways an output can move and finding that eleven are silent is what makes the stamp worth its cost. The alternative is trusting `temperature=0`, which is not a claim about the pipeline at all - it is a claim about the sampler, and the sampler is not where drift comes from. The cost is one model, one module and one CSV; the benefit is that "nothing changed" becomes checkable rather than asserted. Authority: Andre ([../../../.github/agents/andre.agent.md](../../../.github/agents/andre.agent.md)).

Digesting the model's own serialization rather than a hand-written concatenation is the same move as generating schemas from models: it removes a second list that has to be kept in step by hand, and the class of bug where someone adds an input and forgets to stamp it stops existing. Authority: Fowler.

The scope statement above is honest, so the defect was the `server_argv` docstring that claimed more coverage than the scope statement gave. Fixing the sentence alone would have left the gap unwritten, and digesting the five blind spots here would have burned the eval-clock reset that the model swap already pays for. The third option is what shipped: name the exclusions, say which ones matter, and make a contract test hold the list closed. The list now costs one line per knob and cannot go stale in silence. Authority: Fowler ([../../../.github/agents/fowler.agent.md](../../../.github/agents/fowler.agent.md)).

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Trust `temperature=0, seed=0` and skip the stamp | Eleven of sixteen enumerated drift sources are silent without it, including a publisher rewriting an article at the same URL. | Andre |
| Fail the build on a determinism violation | It will fire across runner CPU classes for reasons unrelated to a regression, and a flaky gate gets switched off within a month. Record it, count it, do not smooth it. | Andre |
| Include `host_cpu` in the digest | Every runner becomes a different fingerprint, which hides the cross-hardware divergence the stamp exists to expose. | Andre |
| Hand-assemble the digest input from a list of names | A second enumeration to keep in step with the model, and forgetting an entry is silent by construction. | Fowler |
| Store the prompt text on the ledger row | Puts text nothing downstream reads into a permanent committed record; the digest answers the only question asked of it. | Andre |
| Write an eval row for an unchanged item | Makes every trend on the dashboard a function of how often the job ran rather than of how the summaries changed. | Andre |
| Digest the five blind spots now | Every fingerprint resets when they enter the stamp, and row 4 of the Qwen3.5-9B swap plan resets them all anyway. Two resets buy one. | Fowler |
| Put all ten undigested knobs on the ledger row the way `host_cpu` is | `host_cpu` earns its column because it explains a violation. A KV cache setting explains nothing on its own, and ten more columns cost every future row. | Fowler |
| Correct the fields and leave the docstring | The fields were never the defect. The scope statement already said an undeclared field is not covered; only the docstring claimed otherwise. | Fowler |
| Delete the false sentence and add nothing | The gap stays real and stays unwritten, so the next reader re-derives it from the argv list. | Fowler |

## See also

- [schemas.md](schemas.md) - how these shapes are authored, versioned and generated.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the skip rule in the context of the run.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - what an eval row measures, and why an empty re-run must not write one.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - the identity and replay requirements for a model change.
- [../../reference/measurements.md](../../reference/measurements.md) - where a measured number carries its hardware and date.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #10, section 11.
