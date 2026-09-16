# The model boundary

**Last Updated**: 2026-09-16

How the summarizer stays generic while the model behind it changes. This page
owns the shape of the boundary - what crosses it, which side each fact lives
on, and what proves the two sides agree. The prompt's wording is
[prompt.md](prompt.md); what a call costs is [throughput.md](throughput.md).

## The shape

The app hands over article text, its own instructions and its own output
schema, and gets back a payload in its own shape. Between those two points sit
two thin pieces of model-shaped code. Nothing else in `backend/` knows which
model is loaded.

```mermaid
flowchart LR
  subgraph app_in["The app - knows no model"]
    direction TB
    A1["article text<br/><i>sanitized once, at the trust boundary</i>"]
    A2["the instructions<br/>backend/idhazh/prompts/*.txt"]
    A3["the output schema<br/><i>generated from the contract</i>"]
  end

  subgraph shim_in["Inward shim - render_prompt, completion_payload"]
    direction TB
    S1["place the system text<br/><i>its own turn, or folded into the first user turn</i>"]
    S2["wrap every turn<br/><i>opening, closing, reply opening</i>"]
    S3["build the request<br/><i>schema, prompt cache, budgets</i>"]
    S1 --> S2 --> S3
  end

  subgraph engine["llama-server - one process, one model"]
    direction TB
    M1["grammar masks the logits<br/><i>schema converted to a grammar</i>"]
    M2["decode"]
    M1 --> M2
  end

  subgraph shim_out["Outward shim - parse_completion"]
    direction TB
    O1["read either reply envelope"]
    O2["drop the reasoning block"]
    O3["validate against the same schema"]
    O1 --> O2 --> O3
  end

  OUT["Summary payload<br/><i>the app's own shape again</i>"]

  A1 --> S1
  A2 --> S1
  A3 --> S3
  S3 -->|"prompt bytes"| M1
  M2 -->|"reply bytes"| O1
  O3 --> OUT

  ENTRY["config/models/&lt;slug&gt;.json<br/><b>every model-shaped fact, in one file</b><br/><i>weights, turn envelope, window, budgets</i>"]
  ENTRY -.->|declares| S1
  ENTRY -.->|declares| S2
  ENTRY -.->|declares| M1
  ENTRY -.->|declares| O2

  subgraph meas["Performance measurement - manual dispatch, never a merge gate"]
    direction TB
    B1["case 1 - llama-bench<br/><i>raw prefill and decode, no server</i>"]
    B2["case 2 - llama-server + real work<br/><i>samples drawn from corpus/holdout.txt</i>"]
    B1 --> B2
  end

  REC["docs/reference/models/&lt;slug&gt;.md<br/><i>one current reading of each quantity</i>"]

  ENTRY -.-> B1
  M2 -.->|"tokens a second, resident set"| B2
  OUT -.->|"seconds an item"| B2
  B2 -.->|"a person transcribes"| REC

  style shim_in fill:#eef2ff,stroke:#4c6ef5
  style shim_out fill:#eef2ff,stroke:#4c6ef5
  style meas fill:#fff4e6,stroke:#f08c00
  style ENTRY fill:#ebfbee,stroke:#2f9e44
```

Dotted lines carry no data at run time. They are declarations - the entry
saying what the shims must do - and measurement taps, which only exist during a
dispatched benchmark.

## Which side each fact lives on

The line is between the **envelope** and the **content**, and it is the whole
design.

| Fact | Side | Why |
| --- | --- | --- |
| How a turn opens and closes | Envelope, per model | Different between model families; nothing this project wrote decides it |
| How an assistant reply opens | Envelope, per model | A generation prompt ends with more than a role header, and what it ends with is the model's |
| Whether a system role exists, and where its text goes when it does not | Envelope, per model | A turn topology. The bytes do not change; their address does. `turns.system_role` is a closed choice of two, and `turns.system_joiner` is what separates the two blocks when they share a turn |
| Which template keyword turns reasoning off | Envelope, per model | It is a variable name belonging to that model's template. `turns.thinking_kwarg` carries it, and null means the template reads none |
| The window, the batch sizes, the budgets | Envelope, per model | Measured against those weights, and pinned to their digest |
| **Which control tokens the sanitizer strips** | **Content, global** | A forged turn is written in whatever syntax the attacker picks, so a pattern that knew only the model in use is a pattern an attacker walks around. See below |
| **The instructions** | **Content, global** | See below |
| **The output schema** | **Content, global** | It is the one control that survives an injection, and a per-model control is a per-model hole |
| **Every gate threshold** | **Content, global** | A gate never moves to let a candidate through |

### Why the control tokens are global and the refusal is not

The sanitizer is the control that keeps a forged turn out of an article
(Guardrail #11), and it is the one model-shaped fact that does **not** move onto
the entry. An article is fetched once and read by whatever is loaded, and the
attacker picks the syntax - so a pattern derived from the configured entry's own
markers would defend the one family nobody was attacking. The pattern knows
seven families: ChatML and its pipe-delimited descendants, Llama 2's instruct
brackets, markdown role headers, DeepSeek's fullwidth-pipe tokens, Mistral's
bracket directives, the bare angle-bracket token Gemma and Nemotron use, and the
reasoning channel the incumbent opens its own replies with.

That list cannot be complete - somebody ships a new family every few months - so
the per-model half is a **refusal, not a pattern**. `idhazh.config.load` renders
every marker the entry declares, asks
`idhazh.sanitize.why_a_forged_turn_would_survive` whether the pattern strips it,
and stops the run naming the marker when it does not. An unknown family is then
a config error before anything is fetched rather than an open turn boundary on
the first article.

It asks two questions, because either alone lets a marker through. **Is the
marker recognised at all** - one the pattern never matches is one an article may
write out in full. **Is anything structural left** - a marker matched only in
part leaves its delimiters behind. The second question is what refuses a model
whose turn boundary is ordinary words, `USER: `, and that refusal is the right
answer rather than a gap: a pattern wide enough to strip it would strip a line
of dialogue out of an article.

### Why the instructions never become per-model

Three reasons, and the first is mechanical.

**The run stamp would go blind.** `prose_changed_alone` reports nothing
whenever the model digest moved. Per-model wording means a prompt edit made
*because* the new model needed it is permanently invisible - hidden inside the
swap that carried it. The one alarm that survives a model change stops working
on exactly the day it is needed.

**Qualification would stop measuring one thing.** The eleven gates compare two
models on one frozen corpus. Different words on each side measures two changes
and reports one number.

**A candidate could be fitted to the gates.** A model that needs different
instructions to score well is a model that failed, not a model that needs a
file. Keeping the words fixed is what makes the comparison honest.

A model with no system role is the case that looks like an exception and is
not. The same bytes go to a different address: `turns.system_role` says which
address, and `backend/idhazh/prompts/*.txt` is untouched either way.

**The two stamps disagree about whether they can see that, and the difference
is the reason the envelope is declared rather than inferred.** The digest run's
`prompt_sha256` renders both turns through the envelope, so a placement change
moves it exactly as a reworded instruction would - measured 2026-09-14: the
same two turns render 28 bytes shorter under the fold and the digest moves. The
qualification run's stamp does not. `stages/qualify.py` hands `build_inputs`
the content-only digest from `summarize.prompt_inputs`, which takes no envelope
and carries no turn marker, so nothing on `turns` can move it - and the eleven
gates are what adopt a model. A candidate compared through a digest that is
blind to how its turns were written needs the envelope stated on the entry and
checked against the running server, which is case 1 of the start-up proof.

## Two shapes, and which one a run writes down

The entry is two things at once, so it is two contracts.

| Shape | Who writes it | Carries |
| --- | --- | --- |
| `ModelEntry` | a person, in `config/` | the weights, the runtime settings, **and the turn envelope** |
| `ModelRef` | a run, into `run.json` | the weights and the runtime settings |

The envelope is required on the declared shape and absent from the recorded
one. Required, because an entry that forgets its markers must fail rather than
inherit the incumbent's: inherited markers render a prompt with no turn
structure that the grammar still accepts, so the only symptom is worse
summaries. Absent from the record, because no `model_ref` a run has ever
written carries markers, and a required field there would stop today's build
reading yesterday's day (`CLAUDE.md` section 11).

What that gives up is that `run.json` never says how the turns were written.
It is paid for by `RunRecord.inputs.prompt_sha256`, which digests both turns
**rendered through** the envelope - so a marker that moved still moves the
stamp, and `prose_changed_alone` still has something to compare. Ruled by
Fowler, 2026-09-13.

**The same split is why `turns.declared_for` is optional where
`inference.declared_for` is not.** A person writing an entry always knows which
weights the markers were recorded against, so config load refuses a mismatch.
But a field that were required here would have to be present in every payload
embedding the recorded shape - and no run written before 2026-09-14 carries an
envelope at all. Optional is what lets today's build read yesterday's run; the
refusal that matters lives on the declared shape, where somebody can act on it.

The envelope reached the entry on 2026-09-13. Before that it was one global
file, `backend/idhazh/prompts/turn_markers.json`, with no model key - so a
model whose turns differ was a source edit, and one process holding two
candidates would have rendered both with the first one's markers. The lookup is
keyed by the entry now, and config load refuses that path if the file comes
back.

## The inward shim

Three steps, in order, all reading the entry and never a model name.

1. **Place the system text.** Its own turn, or folded into the first user turn
   behind a declared joiner. A closed choice of two, because each is a turn
   topology and a free-form string would be a template language in config. The
   joiner is required under the fold and refused beside a system turn, so the
   field is never set on the case that would ignore it.
2. **Wrap the turns.** Substitute the role into the opening, append the
   closing, and end with the reply opening the model expects.
3. **Build the request.** Attach the output schema, ask for the prompt cache,
   and set the budgets.

The second call of an item is a literal byte-extension of the first, which is
what lets the prefix cache hold. That property lives in the expression itself
rather than in an agreement between call sites.

## The outward shim

Thinner than the inward one, on purpose. The grammar has already forced the
reply into our schema, and a grammar is a runtime control that behaves
identically on any model. So only two things on the way out are model-shaped:
which envelope the runtime wrapped the reply in, and whether a reasoning block
is present and has to be dropped before anything reads it.

The envelope is also where the runtime says why the decode stopped, and the two
routes spell that differently: the chat route writes `finish_reason`, the
rendered-completion route writes `stop_type`. Three of `stop_type`'s words
translate - `limit` is `length`, and `eos` and `word` are both a decode that
ended itself, which is `stop`. **A word not in that set is carried through as
the server wrote it, and a reply that named no reason at all carries none.**
Both used to arrive as `stop`, so a novel ending and an unreported one reached
the census as an ordinary clean stop, with nothing left in the row to tell them
apart by (Guardrail #10). It is not an enum for the reason
`ItemHealthRow.label_finish_reason` gives: the vocabulary belongs to
llama-server, and a row that would not validate because the runtime minted a
word would lose the whole item over a label.

The envelope also says which prefix-cache slot answered the call. Three fields
carry it, and all three arrive on the route the summarizer already posts to, so
reading them costs no extra request (measured 2026-09-15 on build
`b10598-56db501e7`, [measurements.md](../../reference/measurements.md)).

| Census column | Reply field | What it says |
| --- | --- | --- |
| `slot_id` | `id_slot` | which slot answered. `0` at `-np 1`, which is every committed model entry |
| `kv_tokens_at_start` | `tokens_cached` | what the slot holds once this prompt is in it - where the next call starts from |
| `prefix_shared_with_previous` | `timings.cache_n` above zero | whether this call read anything back out of the slot |

**An item makes two calls and the row has one set of those columns, so the row
carries the FIRST call's.** The second call's prompt is the first one's extended
- that is the whole point of the continuation - so its `cache_n` is above zero
on every row and its slot state is a fact about the item itself. Only the first
call's slot was last touched by the item *before* this one, which is the
question these three exist to answer.

`timings.cache_n` is read once, in `parse_completion`, and both
`label_cached_tokens` and `prefix_shared_with_previous` come off that one
reading. A boolean derived anywhere else would be the same reading written
twice, and two writings drift (Guardrail #10).

**An absent field is null and never zero.** Slot `0` is a real slot, and a cold
slot really does reuse nothing, so a default would put a number nobody measured
on every row. A field the server sends as something that is not a whole number
is absent too: these fill an instrument column, and an instrument may not cost
an item.

Everything after that is the app's own validation.

## What proves the two sides agree

A declared envelope nobody checks is worse than a single global file, because
a wrong marker renders a prompt with no turn structure that the grammar still
accepts - worse summaries and no error anywhere. So the server is asked, once,
before the first item:

| Case | Question | Refuses |
| --- | --- | --- |
| 1 | Does our render match the server's own render of the same turns? | Compared as token ids, not bytes, so a leading sequence token is not counted twice |
| 2 | Did the slot reuse any of the previous call's prefix? | A silent doubling of prefill cost per item |
| 3 | Does the schema still constrain the decode? | A grammar converter that quietly dropped a feature |
| 4 | Are the loaded weights the declared weights? | A repackaged model under a familiar name |
| 5 | Is the window inside what the model was trained for? | A short native window under a larger configured one |

None has a skip flag. The proof is what pays for declaring the envelope in
config at all. An unread proof refuses too: a server that will not answer, a
model list that names no trained length, or a weights file whose header cannot
be read stops the run exactly as a disagreement does.

`idhazh.llm.server.prove_the_entry` is the whole of it, and `digest.yml` calls
it in the work job between the health check and the first item. Each case is a
function of its own over recorded values, so each is driven from a fixture in
both directions - once with the agreeing value, once with one value changed -
and every refusal names what was declared beside what was reported.

**Where each case reads its fact.** Cases 1, 2, 3 and 5 read the running server:
`/apply-template` and `/tokenize` for the render, two `/completions` calls for
the cache and the grammar, `/v1/models` for the trained length. Case 4 reads the
weights file itself, because llama-server does not publish an architecture.
`/props` carries the path, the alias, the file type, the build and the window;
`/v1/models` adds the vocabulary, the embedding width, the parameter count and
the trained length. Neither carries `general.architecture`, so the probe reads
that key off the front of the file the server was pointed at - a few kilobytes,
not a size that follows the model - beside the `/props` filename assertion
`digest.yml` already makes. The filename says which file; the header says what
that file is.

**Case 3 builds its schema from the one the run really sends.** The reply schema
is generated from a model, so a committed probe schema would be a second copy
that drifts. `prove_the_entry` takes the schema as an argument instead - which
is also what keeps the model layer at the bottom of the dependency graph, since
the module that builds that schema imports this one.

**Case 2 asks whether the slot reused anything, not whether it reused all of
it.** The first version wanted the second call's reused count to reach the first
call's prompt length, on the reasoning that the first prompt is a byte prefix of
the second one. The premise is true and the conclusion does not follow: the slot
does not resume at the end of the previous prompt, it restores a context
checkpoint written part way through it and resumes from there. Where the
checkpoint sits is the runtime's business and it moves with the build, so there
is no count to demand and no threshold that would not be an invented number
(Guardrail #10). Zero is the whole of the line, and it is enough - the four
failures the case exists to catch (a flipped prompt-cache default, a seam that
re-splits, a leading-token mismatch, a slot lost to parallelism) all reuse
nothing rather than a little less than everything.

Measured 2026-09-14, GitHub `ubuntu-latest`, llama.cpp `b10598`,
Qwen3.5-9B-Q4_K_M, run 34820209002: first probe 31 tokens prefilled, slot
checkpointed at position 26, second probe 27 of 60 reused and 33 evaluated.
Prefill was cut, not doubled. The version that wanted 31 refused all four work
shards on the first real run it ever saw, and 2026-09-14 planned 80 stories and
published none.

### Design rationale - a start-up proof runs against the runtime, not against a model of it

Case 2 passed every test and every rehearsal and was wrong in production, because
its rule was derived from what the prompt bytes must be rather than from what
the server does with them. The general shape: a proof over a runtime's internal
bookkeeping states the property the bookkeeping is *for* - here, that the prefix
was not re-read - and never a number the runtime is free to choose. Anything
finer is a second implementation of the runtime, kept in a docstring, drifting.

## The lifecycle of a model

```mermaid
flowchart LR
  C["a candidate<br/><i>repo at a pinned commit, file, expected digest</i>"]
  B["benchmark<br/><i>does it fit?</i>"]
  Q["qualify<br/><i>is it good?</i>"]
  AD["adopt<br/><i>one line in config/idhazh.json</i>"]
  RV["revert<br/><i>the same line, back</i>"]
  X["rejected<br/><i>the dossier records why</i>"]

  C --> B
  B -->|"fits"| Q
  B -->|"does not fit"| X
  Q -->|"eleven gates pass, a person decides"| AD
  Q -->|"any gate fails"| X
  AD -.->|"quality drops in the archive"| RV

  style AD fill:#ebfbee,stroke:#2f9e44
  style X fill:#fff5f5,stroke:#e03131
```

The benchmark is cheap and answers whether a model fits the runner. The
qualification is expensive and answers whether its summaries are good. They are
not chained, because chaining spends the expensive one on candidates already
dead.

Reverting costs one line because adopting never modified the previous model's
file. Its weights cache key is its own digest, so that cache is still valid.

## A second, smaller model that guesses ahead

`models.summarize.draft` is null and nearly always stays null. Not null names a
second GGUF - a repository, a commit, a filename and a digest of its own - that
drafts a few tokens at a time which the real model then verifies.

**The text does not change, and that is a property of the mechanism rather than
a hope.** The target model checks every drafted token and rejects any it would
not itself have produced, so a drafted run and an undrafted run write the same
words. This is why the block is priced on what it costs and how hard it is to
undo, rather than waiting on a quality measurement: there is no quality to
measure ([`CLAUDE.md`](../../../CLAUDE.md) Guardrail #10).

**What it can do is waste time.** A draft the target keeps rejecting costs a
forward pass per rejected token and buys nothing. The acceptance rate is the
number that says whether it paid, and `llama-server` publishes it -
`llamacpp:spec_decode_num_accepted_tokens_total` over
`llamacpp:spec_decode_num_draft_tokens_total`, both already in the `/metrics`
body each shard reads at job end. Both read zero when no draft head is
configured, so the columns are legible on every day either way.

**Three things it costs.** A second download and its checksum, both in the same
steps as the target's so the two cannot drift apart. Memory for a second set of
weights, which comes out of the headroom
[`measurements.md`](../../reference/measurements.md) records rather than out of
the KV budget. And the draft's own digest in the run record, so a day that was
drafted can be told from a day that was not - a run that cannot answer that
cannot explain its own throughput.

**Every case that starts a server fetches it, and that had to be made true.** The
daily run always did. The two measurement cases below and the qualification case
did not: each downloaded exactly one file, so the first entry ever to declare a
draft head benched by starting `llama-server` against a path that did not exist.
The server exits during load, which surfaces as a health check that never passes
rather than as a missing file, and the job that hit it had already paid for its
download. All four now fetch the head and check its digest - on a restored cache
as well as on a fresh download, because a restored entry is the one copy nobody
watched arrive.

**The cache key names the head's digest too, or the fetch never runs.** Both
bench cases share one cache entry so the second does not download the weights the
first already has. An entry keyed on the target alone is a complete-looking hit
with the head missing: the fetch step is skipped because the cache reported a
hit, and the server fails at load anyway. So the key is the target's digest, and
the head's where an entry declares one. An entry that declares no head keeps the
key it already had, which is what stops this costing every other model a
refetch. The raw case never runs a draft head - `llama-bench` has no speculative
path - and fetches it regardless, because it is the case that fills the cache the
server case restores.

**The flag spellings are the trap, and they are not the ones on most pages.**
`--draft-max` and `--draft-min` were removed from llama.cpp; the pinned build
exits telling the operator to use `--spec-draft-n-max` and `--spec-draft-n-min`.
`idhazh.llm.server.server_argv` is the one place in this repository a
llama-server flag may be spelled, and a test pins all four current spellings and
refuses the two retired ones by name - so a rename in either direction fails
here rather than on a runner.

**The spelling of the flag's VALUE is the second trap, and it is quieter.**
`spec_type` says which kind of speculation the runtime should drive, and naming
the wrong kind is not a slow server - it is a dead one. The Gemma entry declared
a multi-token head as `draft-simple`; the server started, loaded the head, and
then failed every single request on `decode() failed: failed to process
speculative batch`. Five articles of five, deterministic, one hour of bench time
on run 34941400155. It reached the pipeline as `model_unreachable`, which is a
network word for a decode failure and is why that mapping is worth splitting.

The build accepts eleven values and the contract offers three - `draft-simple`,
`draft-mtp` and `ngram-simple`. The rest need either a draft head nobody has
published for our weights or a lookup cache nothing here writes, and a closed
choice is what stops an operator naming one and getting a server that drafts
nothing. **The agreement between the two lists is now a test rather than a
memory**: `tests/fixtures/runtime/b10598-llama-server-help.txt` is what the
pinned build printed for `--help`, and the contract's values must be a subset of
the list on its `--spec-type` line. The fixture is named for the build, so
moving the pin without re-recording fails on a missing file rather than passing
against a binary nobody runs.

**The recording comes from `.github/workflows/probe.yml`**, which installs the
pinned asset, runs `--help` and keeps the output. It exists because the
alternative way to learn what a build accepts is the hour the Gemma run spent.

## The two measurement cases

Both are manual dispatch. Neither gates a merge: the fastest and slowest shard
of one run differ by up to 4.35 times on prefill, so a merge gate on a
throughput number is a gate on the runner lottery.

### Case 1 - llama-bench

Raw prefill and decode rates at several prompt lengths, against a pinned
runtime build verified by digest. No server, no pipeline, no prompt.

It answers one question well: how fast does this model move tokens on this
class of machine. It cannot answer seconds per item, and it never observes a
resident set, because it never starts the server the pipeline talks to.

### Case 2 - llama-server with real samples

The server starts through the same argv builder production uses, at the
candidate's declared window, and real pipeline work runs against it.

**The samples come from `corpus/holdout.txt`**, which lists item digests held
out of training. Holdout rows are the only honest source: benchmarking a
fine-tuned model on rows it was trained on measures memorisation rather than
summarization. The rows themselves are in `corpus/corpus.jsonl`, and
`corpus/corpus.meta.json` records how many models contributed - a count worth
reading before training, because a swap makes the corpus mixed-teacher.

What case 2 records that case 1 cannot:

| Quantity | Why the server is needed |
| --- | --- |
| Seconds an item | The whole two-call sequence, not a token rate |
| Peak resident set | `llama-bench` never starts the process whose memory matters |
| Model load time, cold and warm | The first day after a swap is cold on every shard at once |
| Prompt-cache hit between calls | Only observable on the real call sequence |
| Output digests | Determinism, by replaying the same rows |

Case 2 never scores quality. The eleven gates judge quality and they live
elsewhere; a scorer inside a bench becomes the thing that selects, and the
alarm stops being able to detect drift.

### Where a reading lands

A dispatched run uploads an artifact, and an artifact is deleted on a retention
clock - so a decision taken weeks later cannot cite one. The run therefore
emits the body of a model page, numbers filled in, and a person commits it to
`docs/reference/models/<slug>.md`. That page carries one current reading of
each quantity rather than a log of runs, and links to the benchmark records
behind it.

CI does not commit that page. Doc routing is reviewed in a pull request, and
every commit CI makes lands in the range the scheduled prune has to rewrite.

## Design rationale

**One complete file per model, never a merge.** A layered shape - global
defaults with per-model overrides - makes the same swap a one-line edit, so the
edit was never the argument. The cost is that no file contains the value that
won, and the two refusals that protect a swap would run against a product no
file holds. With one role configured, deduplication saves nothing. Revisit if a
second role becomes real.

**The envelope is data; the strategies are code.** Which placement a model
needs is a value. What "folded into the first user turn" means is a code path.
Expressing the second as data requires a template language in config, which is
a second renderer nobody tests.

**No free-form flag map on the entry.** It would put an operator-supplied
string onto a process argv and move flag spelling out of the single function
allowed to spell one. Every knob is a named field with a type and a default.

**No branch on a model's identity, anywhere under `backend/idhazh/llm/`.** A
branch on a value is configuration. A branch on an identity is a fork, and the
second one arrives within a release of the first.

## What is wrong with the boundary today

Both shims exist and both work, and the schema constrains the decode on both
transports - measured on build b10444, 2026-09-12. The system placement and the
thinking keyword stopped being source on 2026-09-14 and are entry fields now.

The control-token pattern was the last thing still written for the family we
happen to run, and it stopped being that on 2026-09-14. It knew three families
and now knows seven, and an entry whose markers it would not strip is refused at
config load with the marker named. What it still cannot do is anticipate a
family nobody has shipped yet - which is why the refusal exists, and why the
failure it produces is a config error rather than a summary that obeyed a page.

The turn envelope is no longer part of that list. It sits on the model entry,
and since 2026-09-14 the five proofs above reconcile it against the running
server before the first item - so a wrong marker now refuses the shard instead
of yielding worse summaries with nothing red.

**The entry declares its architecture, and case 4 is what makes that a fact.**
`arch` is the `general.architecture` key written inside the GGUF - `qwen35` for
the configured weights, `gemma4` for a Gemma 4 entry. It is required with no
default, for the same reason `turns` is: an entry that inherits the incumbent's
architecture is claiming something nobody checked. The probe reads the key back
out of the file the server was pointed at, which costs a few kilobytes of header
rather than a second download, and refuses the run when the two disagree. That
is the one case where the digest, the alias and the filename all agree and only
the words get worse - a repackaged GGUF under a familiar name.

**Both declared blocks name the weights they were set for, and load refuses a
mismatch.** `inference.declared_for` and `turns.declared_for` each hold the
entry's own `sha256`. The failure this stops is five strings edited in place -
repo, file, revision, digest and id - with the blocks underneath them untouched,
which used to raise nothing and then stand a server up on numbers derived for
weights it never opened. It is not hypothetical: the summarizer moved from the
8B to the 9B on 2026-08-27 and the settings block did not move with it. The two
blocks fail differently on purpose - re-derive the numbers, or re-record the
markers off the server that applies them.

**This page describes the boundary rather than tracking work**, so it changes
when the shape changes. [Swap the Summarizer
Model](../../how-to/evaluate-new-summarizer-model.md) is the procedure.

## See also

- [prompt.md](prompt.md) - what the instructions say and why they are ordered that way.
- [throughput.md](throughput.md) - what a call costs, and where the time goes.
- [../contracts/schemas.md](../contracts/schemas.md) - how a persisted shape is declared, versioned and migrated.
- [../contracts/determinism.md](../contracts/determinism.md) - what the run stamp records, and what it cannot see.
- [../../concepts/config.md](../../concepts/config.md) - the config shape and every knob on it.
- [../../how-to/evaluate-new-summarizer-model.md](../../how-to/evaluate-new-summarizer-model.md) - the runbook for benchmarking, adopting and reverting.
- [../../how-to/fine-tune-a-model.md](../../how-to/fine-tune-a-model.md) - the training corpus, and what a base swap does to an adapter.
- [../../reference/measurements.md](../../reference/measurements.md) - the instrument log.
