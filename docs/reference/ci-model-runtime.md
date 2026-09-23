# The model on a runner

**Last Updated**: 2026-09-22

How a job gets the inference runtime and the weights, and how it proves it got
the ones it asked for. Every value here is exact: a pin, a cache key, a digest,
a flag. The workflows that use them are in
[github-actions.md](github-actions.md).

## The inference runtime is pinned, and the cache key says which build

`digest.yml`, `validate.yml`, `measure.yml` and `idhazh-pipeline-tests.yaml`
run one llama.cpp build. Each checks the archive against its digest before it
unpacks anything, and each goes on to download weights.

| Variable | Value |
| --- | --- |
| `LLAMA_CPP_BUILD` | `b10598` |
| `LLAMA_CPP_ASSET` | `llama-b10598-bin-ubuntu-x64.tar.gz` |
| `LLAMA_CPP_SHA256` | `d77a09db4165f8850b513629ed0ffeaab7851bb03e7cc3870b74e721f894694c` |

The SHA-256 is the release API's own `digest` for that asset. It was confirmed
on 2026-08-25 by downloading the 16,377,727-byte archive and hashing it.

### Where the model file is read, and how many places that is

**One place. `backend/utilities/model_refs.py` is the only reader of a model
file**, and `backend/utilities/model_runtime.py` is the only program that acts
on what it says - the pin, the runtime install, the download, the check and the
server start, as five verbs of one program.

| Verb | What it answers |
| --- | --- |
| `print-pinned-build` | which llama.cpp build this run installs, as `key=value` for a step to publish |
| `install-runtime` | put that build in `backend/bin`, archive digest checked before anything unpacks |
| `download-model-files` | fetch every file the model declares, in declared order, each proved before it counts |
| `verify-model-files` | check every declared file against its recorded digest and its declared size |
| `start-server` | start llama-server against one config root and prove the process survived |

**The pin is `config/llama-cpp-pin.json`** - three keys, `build`, `asset` and
`sha256`. It is a tunable that changes on an upgrade, so it lives in `config/`
(Guardrail #6). A workflow step that needs the build runs `print-pinned-build`;
the cache key names the build and the cache step runs before anything is
installed, so the pin has to be readable without downloading anything.

**A step spells no URL, no filename, no digest and no flag.** It passes a config
root and, where the platform will not let a program read it, a token. What used
to travel instead: a plan job read the model file, published seven job outputs,
and a composite action took ten inputs to carry them to a download - four hops,
every one of them a place a value could be pasted into a command.

**`measure.yml` is the one file still declaring the three pin values in its own
`env:` block**, and its four inline download arms are what read them. A workflow
`env:` block cannot read a file, and two of those jobs have no Python set up at
all, so moving it means adding a step to jobs that cannot run one. A test holds
the two copies equal instead, so the second cannot drift from the first.

So the three pin values are written in **two places: the pin file and that one
`env:` block.** It was six until 2026-09-17, and converting `measure.yml` takes
it to one.

What a converted caller is refused is the VALUE, not the name: a job whose stage
records which build decoded the bytes has to put `LLAMA_CPP_BUILD` in that
step's environment, and taking it from the step that published the pin reads the
one home rather than copying it.

### What the cache key holds

The weights cache key is `llm-<digest over every declared file>-<build>-v5`,
written in the shared action and in `idhazh-pipeline-tests.yaml`.

The digest covers `repo`, `revision`, `file` and `sha256` **per file, in
declared order** - the weights first, then every companion. It does not cover a
file's `flag`, which reaches the server command line and would throw several
gigabytes away over an edit that changed no byte on disk, and it does not cover
the config root, which is how the files were found rather than part of what they
are. That last exclusion is what lets a trial dispatch reading a scratch config
restore the entry the daily run already paid to download.

**Three key formats sit over `backend/models`, in six steps, and they are
deliberately different.**

| Format | Where | Why it is its own format |
| --- | --- | --- |
| `llm-` | the shared action, and `idhazh-pipeline-tests.yaml` | the production entry. Written twice because one is reached through a composite action and one is not, so the two are held equal by what they RESOLVE to |
| `qualify-` | `validate.yml` | a candidate under qualification. Production must not share an entry with it |
| `bench-` | `measure.yml`, three steps | a bench candidate, same reason |

An equality across all six would be false by construction, so only `llm-` carries
one.

**The suffix is the manual eviction handle.** It moved to `v5` when the model
half became a digest over the whole declared set. It exists for the three things
the digest cannot see: an entry already poisoned, a llama.cpp release re-uploaded
under one tag, and a runtime-install change that alters `backend/bin`, which is
in `path:` and in no key component.

**The key matters more than the pin.** The fetch step runs only on a cache
miss. Keyed on the weights alone, the cache froze one binary and then served a
different one the first time the entry was evicted - the instability of
following the newest release with none of its freshness, and no record on the
run of which build served the day. A throughput number measured in `measure.yml`
now describes the binary that writes the digest (Guardrail #10).

**The key is not a hash of the program that fetches, and that is deliberate.** A
hashed key moves when a comment moves, which throws a multi-gigabyte entry away
for an edit that changed no byte of what it holds.

The run manifest records `runtime_build` as the build the plan job read out of
the pin and handed to the work step, so a published day names the binary that
decoded it. A run with nothing pinned - a developer machine - records
`build-not-recorded` rather than inventing a tag.

**The only way this entry costs a run is by being absent.** Two things remove
it: the digest not running for 7 days, which deletes it outright; or the entry
sitting unread while newer saves push the repository past its cache limit, since
eviction takes the oldest last-access first. Either way the next run refetches
the weights and reinstalls the runtime, on the publishing path. Both rules are
in [ci-environment.md](ci-environment.md#platform-limits-that-shape-the-workflows).

#### Design rationale

**The cache key is computed inside the action, from the model file, not passed
in by the caller.** Decided 2026-09-22.

The real alternative is what every caller did until this change: a plan job read
the model file, published the filename and the revision as job outputs, and the
action composed the key from two inputs. It worked, and it cost four things. The
key named two fields where the download read a whole file set, so an entry that
gained a companion kept its old name and restored complete with a file missing.
The action resolved a deleted input to the empty string with no error, so any
change to those inputs could silently key every model on one string. Two callers
had to hand over the same six values and could disagree. And the key could not
be proved to describe the set the download would read, because the two were
composed in different places from different reads.

Computed inside the action it costs zero lines in both callers, it is provably
the set the download reads, and the caller hands over only the build - the one
half the model file does not decide. **Reversing it costs every caller a full
re-download**, because the key string changes, and it crosses the
workflow-to-action boundary, which is why it is written down here.

### What the build accepts is recorded, not re-asked

The pin says which binary runs. It does not say what that binary understands,
and an entry naming a flag or a value the build cannot drive fails late and
quietly: the server starts and the job spends its hour before anybody reads the
flag back.

So the answer is committed rather than dispatched.
`tests/fixtures/runtime/b10598-llama-server-help.txt` is what the pinned build
printed for `--help` on 2026-09-15. The fixture is named for the build, so a pin
that moves without a re-recording fails on a missing file rather than passing
against a binary nobody runs. Re-recording it is one command against the
installed build - `llama-server --help`, redirected into a file named for the
new pin.

## Every download fails loudly, and every weight is checked

**One function fetches bytes: `_download` in `model_runtime.py`.** It is the
only thing in the repository's model path that touches the network for a file,
so a change of transport is a change to one function.

| Clause | What it buys |
| --- | --- |
| **no request header at all** | CPython's redirect handler copies every header onto a cross-host redirect target with no host check. Both the hub and the release CDN redirect, so a bearer token added here would follow the redirect to somebody else's server. Only the release lookup sets one, and a test asserts exactly one function does |
| `urlopen` raises on any non-2xx | that is `curl -f` for free. An HTTP error body can never be written into a weights file and then saved under a cache key |
| a socket timeout of 60 s | it bounds one blocking read. It is **not** a bound on the transfer, which is why the next two exist |
| a wall-clock deadline of 30 min per file | a shard is killed at `run.shard_timeout_minutes`, 200 today, and a download that holds it to that ceiling costs the day a shard of stories |
| a throughput floor of 1 MB/s, measured over the last 30 s after the first 60 | a connection that ran at full speed and then stopped keeps a healthy average for a long time. Measuring the last window catches a stall in thirty seconds, and a socket timeout catches it never |
| 3 attempts, each from byte zero, on a reset, a short read, a timeout, a 5xx, a 408 or a 429 - **never on a 4xx** | a 4xx is the server saying the request was wrong, and asking again three times is three ways to be wrong about the same thing |
| the bytes land on a `.part` and the caller renames | `curl -o` wrote straight to the destination, so a job killed mid-transfer left half a file under the cache key for every later run to restore |

**This path has never resumed, and restarting from zero is parity rather than a
loss.** The `curl` call this replaces carried no `--continue-at`.

In the daily run a bad file is worse than a failed step, because `backend/models`
is a cache path. A rate-limited minute that wrote a page of error text where the
weights should be would be saved under the pinned key and restored by every
later run until the entry is evicted.

The digest check is what catches the other failure, a transfer that dies
mid-body. That is a 200 response, so there is nothing to retry and the file on
disk is simply short. **Every declared file is checked against its recorded
digest, after the fetch and before anything reads it, and the check reads the
declaration rather than being handed a filename** - so it cannot cover fewer
files than the cache key digested. **No check carries an `if:`.** The fetch step
is skipped on a cache hit, and a restored entry is the one case where nobody
watched the bytes arrive.

| Workflow and job | Weights | Digest read from |
| --- | --- | --- |
| every job on the shared download | whatever its config root declares | that root's own `models.summarizer.sha256` and each companion's, read by `verify-model-files` |
| `measure.yml`'s four inline arms | the bench candidate, or the summarizer | the `models` job's republished `candidate_sha256`, or `models.summarizer.sha256` |

The four inline arms are the exception, and deliberately: an operator can point
the bench at a model config does not name, so that job resolves the digest once
- from the dispatch input, or from config when there is none - and republishes
it as a job output the whole run reads. The bench's raw case checks the same
digest a step earlier, inside `measure_llm.py`, against the Hub's own record for
that commit.

The workflow contract test that holds this open is closed-world. It finds the
downloads by reading every workflow file rather than by consulting a list, and
fails when the set it finds differs from the set it pins. **It matches the hub
host and the download verb**, because the download is a program now and a
workflow that calls it names no host: matching only the host would have dropped
four of the eight jobs the day the download moved, and every check written over
that search would have gone on passing.

The production entry is **5.68 GB** (`5,680,522,464` bytes). The 57-to-338-second
figures in
[what-a-bench-dispatch-costs.md](benchmarks/what-a-bench-dispatch-costs.md) were
taken on the 4.28 GB bench arm, not on this file.

### The digest settles the bytes, and the declared size settles the document

A digest says the file on disk is the file the entry named. It says nothing
about whether the entry is internally consistent, so **every check also compares
the file's size against the entry's own `byte_count`**, for the weights and for
each companion. An entry that declares no size skips the check, because that is
an entry nobody has fetched yet rather than an entry that disagrees with itself.

It used to be two arms doing this and two not. `validate.yml` had done it since
it was written and `measure.yml` had not; the drift was found on 2026-09-15 by
diffing the two files. Both halves are inside one verb now, so there is no
second place for one of them to be missing from.

### Healthy says a server replied, not which weights replied

Every number a bench reports is filed under the candidate's id, so a server
answering under any other alias makes the whole run a measurement of something
else wearing the candidate's name (Guardrail #10). Nothing in the report would
look wrong: every figure would be internally consistent.

Four server starts exist across the workflows and **all four now ask
`GET /v1/models` before anything is measured** - the daily run's worker, the
bench's runtime arm, the bench's vocabulary arm, and both starts in
`idhazh-pipeline-tests.yaml`. Two of those learned it on 2026-09-15; the daily
run and the validation arm already did it.

The alias comes from the same config the server's flags came from, never from a
second copy, so the two cannot disagree (Guardrail #6). The test is discovery-
based rather than a list: every step whose script waits on `/health` must also
name `/v1/models`, so an arm added later is held to the rule whether or not
anybody remembered it.

## One place writes a production model ref, and it is config

`config/models/<name>.json` holds `models.summarizer`, and `config/idhazh.json`
says which of those files is active through `models_file`. None of the
three workflows that load weights - `digest.yml`, `measure.yml`, `validate.yml` -
holds a model repository, a weights filename or a publisher name of its own.
Grepping all three for a `.gguf` name, a Hugging Face repository or a branch in a
download path returns nothing, and a workflow contract test asserts exactly that.
None of them names the model file either: each one reads the pointer and follows
it, so a swap is one line for a workflow as well.

Each one reads config in a `models` step and publishes job outputs. `digest.yml`
does it inside `plan`, which `work` already needs; `measure.yml` has
a small `models` job of its own that every target depends on, and that job also
decides the bench candidate - the dispatch input where one was given, the
configured model otherwise - so both bench cases read one answer rather than
repeating the fallback; `validate.yml`
resolves the candidate once inside `plan`. **The `needs` context resolves before
a job's first step while `steps` does not**, which is the whole reason the refs
travel as job outputs: it is what lets a cache key and a job-scoped `env` name
the weights they hold. A step cannot.

That second copy was the defect. The alias came from config while the repository
and the filename came from workflow `env`, so editing one served the old bytes
under the new alias and filed every eval row under a model that never ran
(Guardrail #10). Changing the model is now one edit to config, and the cache key moves
with it.

### A dispatch input is not a copy

`measure.yml` exists to benchmark a model config does not name, and `validate.yml`
exists to qualify one. Both keep their inputs, and an input always wins. What was
removed is the literal DEFAULT behind it. A dispatch that fills nothing in now
measures, or re-qualifies, the model config names.

The values for a model under adoption live in
[pipeline-cost.md](pipeline-cost.md), where a target is declared - not in a
workflow file, where nothing would ever check them against the run.

### Every download names a commit

Each ref carries a `revision`, and every fetch path uses it. A branch hands back
whatever was uploaded last, so the bytes can move under a config that still
records the old `sha256`; the run would then fail a check nobody had changed, or
in `measure.yml`, which had no checksum step, quietly measure a different model.

The revision is inside the weights cache key for the same reason the build is.
The fetch step runs only on a cache miss, so a key that cannot tell two uploads
of one filename apart would hold a repinned config on a hit whose bytes fail the
check on every run until the entry expires.

**Every value the reader publishes passes a closed grammar before it is
written**, because each one is substituted straight into a shell command
downstream and nothing after that point can stop a value carrying a space, a
quote or a newline. "One bare word" was the old rule and it refused whitespace
and nothing else, so `../../x.gguf`, `x.gguf$(id)` and a branch name in place of
a commit all passed it.

| Value | Rule |
| --- | --- |
| `repo` | `<owner>/<name>`, each starting alphanumeric, then letters, digits, `.`, `_`, `-` |
| `revision` | 40 lowercase hex characters - a commit, never a branch |
| the weights `file` | one path segment ending `.gguf` |
| a companion `file` | the same segment rule without the suffix - it may be a projector, an adapter or a vocoder |
| `sha256`, weights and every companion | 64 lowercase hex characters, required, no exception |
| `id` | a slug, held equal to `SLUG_PATTERN` in the contracts |
| `quantisation` | letters, digits, `.`, `_`, `-` |
| `byte_count` | empty, or a positive whole number |
| `flag` | empty, or one or two leading dashes then a flag name. One dash is legal: llama.cpp's short form for a draft model is `-md` |
| every emitted value, last | empty, or printable ASCII with no space. Empty is legal for exactly `flag` and `byte_count` |

The backstop is a character class rather than `str.isprintable()`, which admits
a combining accent and DIVISION SLASH - either of which builds a hub URL that is
not the one a reviewer read.

A refusal names four things in this order: the models file, where in it, the
rule in plain words, and the offending value. Never the regex.

`measure.yml` and `validate.yml` keep their own candidate inputs on purpose:
benching or validating a model means naming one that is deliberately not in
config yet. Each keys its own weights entry on the candidate's declared set
rather than on the production one, so the two never share an entry with the
daily run and a dispatch that names nothing simply keys on the configured
model's.

## One function builds the server command, and one variable says the port

`digest.yml`, `llm-council.yml`, `validate.yml` and `measure.yml` each stand up
a `llama-server`, and none of them writes a flag. Every one imports `server_argv`
from `backend/idhazh/llm/server.py`, which renders the whole command from
`config/idhazh.json`. A contract test holds that from both sides: exactly one
Python file spells those flags, and no command in any workflow spells one.

The first two reach the server through `.github/actions/model-server`, which
carries the whole block - cache, fetch, digest check, start, health probe - so
the start call itself is written once for both
([github-actions.md](github-actions.md)).

There used to be a second renderer, `backend/utilities/llama_server_argv.py`,
and it existed for exactly one reason. Both `digest.yml` inference jobs ran
`Start the model` before `Install`, so `pip install -e.` had not run and the
package was not importable yet. `Install` now runs one step earlier, straight
after `setup-python`, and the copy is gone. Moving a step within a job is the
same work in a different position, so no wall-clock claim is made for it
(Guardrail #10).

While the copy existed the two halves drifted, and the case that drifted is the
one nobody diffed. `validate.yml` never needed the utility - its `Install`
already ran before its server started - so for two changes it qualified
candidates on a server the daily run does not run.

**The port lives inside `model_server.base_url`, and a workflow declares only
where its own probes ask.** It was nine literals in `digest.yml` and three in
`validate.yml`, then one `env: LLAMA_PORT` per workflow, and since 2026-09-23 it
is one committed config value (Guardrail #6). The server command reads the port
back out of the config root the job runs under, and every stage posts to that
same address, so the server and its client cannot end up on different ports.
What a workflow still names is `env: MODEL_SERVER_PROBE`, the loopback address
every `/health`, `/v1/models`, `/props` and `/metrics` probe reads - a probe is
a curl against a server that job just started on that runner, and three of the
five workflows run against a scratch config root it cannot read. A test holds
that declaration against the committed address. The probe address decides
nothing about the words, so `idhazh.fingerprint` has nothing to classify and the
run's recorded inputs do not move.

### The batched bench reads a block no model file has

`measure.yml`'s `batched` job reads its four window and threading numbers with
`jq -er '.summarizer.inference.<name>'`. No committed model file carries an
`inference` block - each entry spells those numbers in `server`, under the flag
`llama-server` reads them as. `jq -er` exits non-zero on a path that is not
there and the step runs under `set -e`, so that job stops before it benches
anything. Found 2026-09-23 while the slot was renamed; the rename moved
`summarize` to `summarizer` here and left the second half of the path alone,
because fixing it is not a rename.

Reading `server` directly is what the job cannot do: one function spells a
`llama-server` flag and a test refuses a second spelling in any workflow script,
so the step would have to be handed the numbers by code that imports that
function. This job installs no package, so that costs an `Install` step before
the read, plus a verb that prints the four values.

## See also

- [github-actions.md](github-actions.md) - which workflows exist, when each runs, and what each does.
- [ci-environment.md](ci-environment.md) - the platform behaviour behind the cache and download limits, and who owns the cache size limit.
- [models.md](models.md) - every candidate model, and the dossier behind each one's figures.
- [../how-to/test-models-locally.md](../how-to/test-models-locally.md) - how to run the same runtime on a developer box.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #2 on the runner budget these pins have to fit.
