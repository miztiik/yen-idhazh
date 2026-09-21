# The model on a runner

**Last Updated**: 2026-09-21

How a job gets the inference runtime and the weights, and how it proves it got
the ones it asked for. Every value here is exact: a pin, a cache key, a digest,
a flag. The workflows that use them are in
[github-actions.md](github-actions.md).

## The inference runtime is pinned, and the cache key says which build

`digest.yml`, `validate.yml`, `measure.yml`, `idhazh-pipeline-tests.yaml` and
`probe.yml` run one llama.cpp build. Each checks the archive against its digest
before it unpacks anything. `probe.yml` installs the build and stops there;
the other four go on to download weights.

| Variable | Value |
| --- | --- |
| `LLAMA_CPP_BUILD` | `b10598` |
| `LLAMA_CPP_ASSET` | `llama-b10598-bin-ubuntu-x64.tar.gz` |
| `LLAMA_CPP_SHA256` | `d77a09db4165f8850b513629ed0ffeaab7851bb03e7cc3870b74e721f894694c` |

The SHA-256 is the release API's own `digest` for that asset. It was confirmed
on 2026-08-25 by downloading the 16,377,727-byte archive and hashing it.

### Where the three values are written, and how many places that still is

**One file decides the build: `.github/scripts/llama-cpp-pin.sh`.** Source it
and it assigns all three; run it and it prints the build as `key=value`, which
is what a cache key reads - the key names the build, the cache step runs before
the fetch, so the pin has to be readable without downloading anything.

Two shared scripts read it, and the split is about what a job actually needs.
`.github/scripts/install-llama-runtime.sh` sources the pin, installs the build
and checks the archive; that is the whole of what a job wants when it opens no
weights. `.github/scripts/fetch-model-runtime.sh` sources that one and then
downloads the weights the calling step names through `env`. One script that
always downloaded a model would turn the one-minute probe below into the
slowest question here, and a `WEIGHTS_FILE` allowed to be empty would make the
refusals every other caller depends on optional.

**`digest.yml`, `idhazh-pipeline-tests.yaml`, `probe.yml` and `validate.yml` are
on those scripts.** `measure.yml` is the one still declaring the three variables
in its own `env:` block and fetching the build itself.

So the three values are written in **two places today: the pin file and one
`env:` block.** It was six until 2026-09-17, and converting `measure.yml` takes
it to one.

Nothing read those places against each other before. A contract test now pins
the three variables in every workflow that still spells them and refuses any
copy of them in a workflow that has been converted, so a conversion is one line
in that test's `LLAMA_SCRIPT_CALLERS` set and the check tightens rather than
being rewritten. What a converted caller is refused is the VALUE, not the name:
a job whose stage records which build decoded the bytes has to put
`LLAMA_CPP_BUILD` in that step's environment, and taking it from the step that
published the pin reads the one home rather than copying it. The digest check on
every fetch path and the build inside every runtime cache key are held by the
same file.

### What the cache key holds

The weights cache key names the build: `llm-<weights>-<revision>-<build>-v4` in
the two `digest.yml` jobs and in `idhazh-pipeline-tests.yaml`,
`qualify-<candidate>-<build>` in `validate.yml`. The `digest.yml` suffix
moved to `v4` when the weights half stopped coming from a workflow variable, so
the first run after that refetched once rather than restoring an entry nobody
could attribute.

A converted caller reads `<build>` off the step that ran the pin, never off a
workflow variable. In `digest.yml` and `validate.yml` that step is in the `plan`
job and the build travels as a job output, because `needs` resolves before a
worker's first step and `steps` does not - which is the same reason the model
refs travel that way.

**The key matters more than the pin.** The fetch step runs only on a cache
miss. Keyed on the weights alone, the cache froze one binary and then served a
different one the first time the entry was evicted - the instability of
following the newest release with none of its freshness, and no record on the
run of which build served the day. A throughput number measured in `measure.yml`
now describes the binary that writes the digest (Guardrail #10).

**The key is not a hash of the script that fetches, and that is deliberate.** A
hashed key moves when a comment moves, which throws a multi-gigabyte entry away
for an edit that changed no byte of what it holds. That is why the pin file
prints the build rather than being hashed.

The run manifest records `runtime_build` as the build the `plan` job read out of
the pin and handed to the work step, so a published day names the binary that
decoded it. A run with nothing pinned - a developer machine - records
`build-not-recorded` rather than inventing a tag.

**The only way this entry costs a run is by being absent.** Two things remove
it: the digest not running for 7 days, which deletes it outright; or the entry
sitting unread while newer saves push the repository past its cache limit, since
eviction takes the oldest last-access first. Either way the next run refetches
the weights and reinstalls the runtime, on the publishing path. Both rules are
in [ci-environment.md](ci-environment.md#platform-limits-that-shape-the-workflows).

### `probe.yml` asks the build what it accepts

The pin says which binary runs. It does not say what that binary understands,
and an entry naming a flag or a value the build cannot drive fails late and
quietly: the server starts and the job spends its hour before anybody reads the
flag back. `probe.yml` installs the same asset the three runtime arms install,
runs `llama-server --help`, prints what it found to the job summary, and keeps
the whole help text as a 30-day artifact - so the next question about this build
is answered by downloading that artifact rather than by a second run.

It is a `workflow_dispatch` with no scheduled trigger and it loads no weights,
so it costs about a minute of runner time. It takes no input for a build,
either: it installs the build `llama-cpp-pin.sh` names, through the same shared
install step the runtime arms reach, so its answer cannot describe a binary
production does not run. Probing a candidate build is a branch that moves the
pin, dispatched with `--ref` - the same commit somebody would have to make to
adopt it.

The question that made it was whether the pinned build accepts the kind a Gemma
multi-token head needs, and that is the shape of every question it answers:
read the runtime's own answer rather than a release note's.

## Every download fails loudly, and every weight is checked

Every download in every workflow is spelled `curl -fsSL --retry 3
--retry-all-errors`, and the release lookups that find the llama.cpp archive are
spelled `curl -fsS`. `-f` is the letter that matters. Without it curl treats a
403 or a 502 as a successful transfer: it writes the HTTP error body into the
output file and exits 0. Nothing downstream looks at the file until a server
tries to open it.

In the daily run that is worse than a failed step, because `backend/models` is a
cache path. A rate-limited minute writes a page of error text where the weights
should be, `actions/cache` saves it under the pinned key, and every later run
restores that same page until the entry is evicted. The retries are the cheap
half of the fix; `-f` is the half that stops the bad file being written at all.

The digest check is what catches the other failure, a transfer that dies
mid-body. That is a 200 response, so curl has nothing to retry and the file on
disk is simply short. Every job that downloads weights therefore runs
`sha256sum --check` against a recorded digest, after the fetch and before
anything reads the file. **No check carries an `if:`.** The fetch step is
skipped on a cache hit, and a restored entry is the one case where nobody
watched the bytes arrive - so it is the case that most needs the check.

| Workflow and job | Weights | Digest read from |
| --- | --- | --- |
| `digest.yml` / `work` | the summarizer | `models.summarize.sha256` |
| `measure.yml` / `runtime` | the bench candidate | the `models` job's `candidate_sha256` |
| `measure.yml` / `batched` | the summarizer | `models.summarize.sha256` |
| `validate.yml` / `qualify` | the candidate | the `plan` job's `candidate_sha256` |

The two config digests are the same field, `ModelRef.sha256` in the file
`config/idhazh.json`'s `models_file` points at. The other two are the exception,
and deliberately: an operator can point the bench and the validation case at a
model config does not name, so each resolves the digest once - from the dispatch
input, or from config when there is none - and republishes it as a job output
the whole run reads. The bench's raw case checks the same digest a step earlier,
inside `measure_llm.py`, against the Hub's own record for that commit.

The workflow contract test that holds this open is closed-world. It finds the
downloads by reading every workflow file rather than by consulting a list, and
fails when the set it finds differs from the set it pins. A tenth workflow that
downloads weights fails the test until it carries the same pair of steps.

### The digest settles the bytes, and the declared size settles the document

`sha256sum` says the file on disk is the file the entry named. It says nothing
about whether the entry is internally consistent, so both arms that resolve a
candidate also compare `stat -c %s` against the entry's own `byte_count`. An
entry that declares no size skips the check, because that is an entry nobody has
fetched yet rather than an entry that disagrees with itself.

`validate.yml` has done this since it was written and `measure.yml` had not. The
drift was found on 2026-09-15 by diffing the two files, which is the same way the
last one was found and the reason both are now held by one test.

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

`config/models/<name>.json` holds `models.summarize`, and `config/idhazh.json`
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

The revision is in the weights cache key for the same reason the build is. The
fetch step runs only on a cache miss, so a key that cannot tell two uploads of
one filename apart would hold a repinned config on a hit whose bytes fail the
checksum on every run until the entry expires.

The `models` step asserts each value is one bare word before it writes it. Every
ref is substituted straight into a shell command downstream, and that step is the
only point between config and those commands where a value carrying a space, a
quote or a newline can be stopped.

`measure.yml` and `validate.yml` keep their own candidate variables on purpose:
benching or validating a model means naming one that is deliberately not in
config yet. Each keys its own weights entry on the candidate digest rather than
on the production ref, so the two never share an entry with the daily run and a
dispatch that names nothing simply keys on the configured model's digest.

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

**The port is one `env: LLAMA_PORT` per workflow.** It was nine literals in
`digest.yml` and three in `validate.yml`, and all of them had to move together
or the job failed in a way that reads as an unreachable model (Guardrail #6).
`server_argv` takes it as an argument; every `/health`, `/v1/models`, `/props`
and `/metrics` probe reads it; and `idhazh.llm.server` reads the same variable
for the address the summarize stage posts to, so the server and its client
cannot end up on different ports. It is not a config field. It decides nothing
about the words, so `idhazh.fingerprint` has nothing to classify and the run's
recorded inputs do not move.

## See also

- [github-actions.md](github-actions.md) - which workflows exist, when each runs, and what each does.
- [ci-environment.md](ci-environment.md) - the platform behaviour behind the cache and download limits, and who owns the cache size limit.
- [models.md](models.md) - every candidate model, and the dossier behind each one's figures.
- [../how-to/test-models-locally.md](../how-to/test-models-locally.md) - how to run the same runtime on a developer box.
- [../../CLAUDE.md](../../CLAUDE.md) - Guardrail #2 on the runner budget these pins have to fit.
