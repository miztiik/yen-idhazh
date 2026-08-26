# Evaluate and Adopt a New Summarizer Model

**Last Updated**: 2026-08-26

Measure a candidate summarizer against the configured incumbent, decide whether
it clears the bar, and change the model without losing reproducibility.

This procedure is for the build-time summary model. The visual router,
faithfulness scorer and browser search model have different contracts and are
not changed by it.

## Capability boundary

There is no one-command model swap.

What exists:

- `backend/utilities/measure_llm.py` verifies GGUF identity and measures raw
  prefill and decode locally;
- `.github/workflows/measure.yml`, target `llm`, runs the same raw measurement on
  `ubuntu-latest`;
- `llama_server_argv.py` builds the server command from config;
- `work` can exercise the real fetch, extract, sanitize and summarize path;
- `validate` can score model output with HHEM; and
- `.github/workflows/validate.yml` plus `idhazh qualify` and
  `idhazh qualify-decide` freeze a corpus, replay it, run the live canaries and
  evaluate eleven absolute gates. Rebuilt 2026-08-26.

What the qualification arm now does, which the old exploratory one did not:

- builds a candidate config under gitignored `backend/var/candidate-config`, a
  copy of committed `config/` with `models.summarize` replaced and nothing else,
  so it never edits the committed config and never has to restore it;
- fetches the candidate from an **immutable repository revision**, checks its
  SHA-256 and its byte count against the adoption target, and does both before
  the server starts;
- keys the weights cache on the GGUF digest rather than the filename, and holds
  one model per entry;
- plans the addresses once, in one job, and carries the date forward, so a run
  that crosses UTC midnight is still one run;
- freezes each shard's slice exactly once, hashes the model-visible truncated
  text and the sanitized full text, writes the hashes down **before** the first
  inference call, and replays those bytes;
- interleaves the repeats - every item once, then every item again - so a repeat
  never lands on a warm prompt cache and skips its own prefill;
- runs every injection canary on live candidate calls; and
- records every failed call in the denominator, and every diagnostic with the
  denominator it was taken over.

What is still missing:

- a pairwise blind-human label contract and CLI; and
- a candidate-aware runtime-shard measurement.

Two capability gaps were closed on 2026-08-26 and are worth naming because
anything measured before then inherits them:

- `HHEM_REVISION` was the branch name `main`, and `weights_digest` hashed that
  name rather than the loaded weight bytes. It is now pinned to
  `8e4a2e6e96c708cc76c2344f7e4757df2515292c` and the digest walks the loaded
  state dict. A faithfulness number from before this date was measured with an
  instrument nobody can name.
- `leaderboard_hhem` was a required float, so a model with no published result
  had to be recorded as `0.0`. It is now nullable beside a
  `leaderboard_provenance` of `not_reported`.

`measure_llm.py` still resolves Hugging Face `main` and cannot request an
immutable revision or accept an expected SHA. That is sufficient for an
exploratory measurement and not for reproducing an adoption candidate; the
qualification arm does not use it.

## The evidence package

A model is identified by all of these:

| Field | Why |
| --- | --- |
| Repository and immutable repository revision | `main` can move. |
| GGUF filename and quantisation | Two files from one model are different candidates. |
| GGUF byte count and SHA-256 | The runtime opens bytes, not a model-card name. |
| Licence | The pipeline and published project must be allowed to use it. |
| llama.cpp build and archive SHA-256 | Runtime kernels can change output and speed. |
| Chat-template digest | A template change moves prompt framing without moving weights. |
| Model id | Persisted summaries and manifests carry it. |

`measure_llm.py` reads the Hugging Face LFS identity, refuses a same-named local
file with different bytes, and records the runtime and model hashes:

```bash
python backend/utilities/measure_llm.py \
  --models "owner/repository@<40-character commit>:model-Q4_K_M.gguf" \
  --threads "4"
```

The files under `backend/models/` are local, gitignored files. The ad hoc
measurement job does not put them in the repository Actions cache.

`measure_llm.py` requires the commit and reads the file listing at it, so two
runs of one reference compare the same bytes. It still verifies only the LFS
identity it observes there rather than a SHA the caller declares, so it will
download a candidate whose bytes disagree with an adoption target and say
nothing. `validate.yml` is what checks a declared SHA, and it is the arm that
qualifies a candidate.

## 1. Freeze the control

Choose the incumbent and candidate before measuring. Hold these constant:

- llama.cpp build;
- `n_ctx`, `n_batch`, `n_ubatch`, `n_threads` and optional runtime flags;
- prompt template and rendered band values;
- output schema;
- `temperature`, `top_p`, seed, thinking mode and output budget;
- extraction and sanitization versions;
- truncation cap; and
- exact captured Article payloads for the quality comparison.

If more than the weights move, the run measures a bundle. Label it as a bundle
or run it again with one changed input.

## 2. Prove that the model loads

Download the entire llama.cpp binary directory, not one executable. Generate the
candidate server command from a scratch config that differs only in
`models.summarize`:

```bash
python backend/utilities/llama_server_argv.py \
  --config backend/var/candidate-config \
  --binary backend/bin/llama-server \
  --weights backend/models/model-Q4_K_M.gguf \
  --alias candidate-model-id \
  --format shell
```

There is no candidate-config command today. Create the directory under
gitignored `backend/var/`, change only the candidate model id, repository, file,
quantisation and SHA-256, and load it through `AppConfig` before use. Do not edit
the committed config for an experiment.

Start the printed command and check:

```bash
curl -sf http://127.0.0.1:8080/health
```

A load failure rejects the candidate for the current runtime. It is not a
throughput result.

## 3. Re-measure the tokenizer and context

Token counts do not transfer between model families.

For every rendered summary band, including the brief path:

1. Render the exact LF-terminated system prompt.
2. Add the source-form line, feed title, fences and exact sanitized model-visible
   text.
3. Apply the candidate's embedded chat template, including the generation
   suffix.
4. Tokenize that complete request with the candidate runtime and GGUF.
5. Repeat for representative extracted articles from each measured length
   bucket.
6. Record the maximum complete-request count and spread.
7. Recalculate:

   ```text
   complete chat-templated request tokens + output budget
   ```

8. Confirm the result fits `models.inference.n_ctx`.
9. Confirm `fits_context` still over-reserves rather than under-reserves.

The extraction cap is applied through a words-to-tokens estimate before the
candidate tokenizer runs. Do not clamp the exact candidate token count back to
`truncation_cap_tokens`; that would hide tokenizer expansion.

There is no command that automates this whole step. Until the candidate-specific
prompt and article counts exist, do not publish derived seconds per article for
that model. Raw `llama-bench` rates remain valid; model-specific derived times do
not.

## 4. Measure raw runner fit

Run incumbent and candidate in the **same workflow job**:

```bash
gh workflow run measure.yml \
  -f target=llm \
  -f models='incumbent/repo:incumbent-Q4_K_M.gguf,candidate/repo:candidate-Q4_K_M.gguf' \
  -f threads='4'
```

Read the `bench-llm` artifact:

- `hardware.txt`: CPU topology, cgroup limits and runtime identity;
- `weights.txt`: exact GGUF size and SHA-256;
- `llm.json`: prefill and decode rates with spread; and
- `resources.json`: wall time, CPU pressure, throttling and memory events.
  Cgroup `memory.peak` can be absent or cumulative; it is not a per-model RSS
  comparison.

Compare:

- prefill at 730, 1800 and 4850 tokens;
- 250-token decode;
- model load success;
- peak memory and pressure;
- download time, labelled `n=1` when it has no repeats; and
- worst-case shard time after candidate tokenization is measured.

A laptop result is a laptop result. It can reject a candidate quickly and cannot
select production.

Raw `llama-bench` fit is not production fit. Measure the candidate through the
real server with the faithfulness scorer resident, the actual worker population,
peak process RSS, memory events, model load, prefix reuse, prefill, decode, worst
item and job wall-clock.

## 5. Check decode compatibility and safety

Use the candidate scratch config and the real local server. At minimum, run:

- one short, one medium and one truncated long article;
- the brief path;
- repeated identical input at the configured deterministic sampler; and
- every prompt-injection canary.

Require:

- `finish_reason = stop`;
- schema-valid JSON without a repair path;
- no non-empty `reasoning_content`;
- no inline non-empty `<think>` block;
- output inside the wider publishable word gate;
- requested-band adherence recorded as a regression metric;
- identical title, summary, key points and `output_digest` on repeat;
- every canary's `must_not_survive` markers absent;
- every canary's `must_survive` facts present in a non-blank valid reply; and
- zero candidate-only crashes or timeouts.

Use three deterministic repeats for the adoption corpus, not one repeated
example.

The inline-think parser reads every block, so an empty opening block no longer
hides a second one that reasoned. It read only the first until 2026-08-25.

The unit suite uses recorded completions. It proves the parser and controls, not
that a new live model follows this chat template. A live candidate canary runner
does not exist yet. Build that instrument or perform and record the live calls;
do not treat recorded incumbent responses as candidate evidence.

Keep the configured sampler fixed for the first comparison. If a model needs a
different temperature, penalty or thinking mode to work, that is a second
candidate configuration. Measure it separately. Do not adopt a vendor default
silently.

## 6. Compare quality on frozen inputs

Planning the same URLs is not enough. A publisher can change a page between
model A and model B.

A controlled comparison:

1. Fetches and extracts each article once.
2. Stores the sanitized full text and exact model-visible truncated text under
   `backend/var/`, with hashes.
3. Sends the same model-visible bytes through both models and the same full bytes
   to the scorer.
4. Records every failed item, not only scored successes.
5. Scores both outputs with the same scorer version.
6. Reads the deterministic counterweights as well as HHEM.
7. Uses one explicit date and run id from start to decision.
8. Writes to an isolated result directory and refuses stale files.

The current validation workflow does not replay captured Article payloads. Fix
or replace it before using its verdict to adopt a model.

Pin the scorer to an immutable revision and record observed scorer-weight
identity before comparing candidate means. Make leaderboard provenance optional
and represent an absent published score as `not_reported`, never `0.0`.

A long workflow can cross UTC midnight. Do not recompute its date between plan,
model runs and decision. Drift summaries must segment model-dependent metrics by
`model_id`; a model swap is a new series, not an ordinary point on the old one.

Pre-register a deterministic corpus before viewing outputs. It must cover all
four length bands plus brief, abstract and truncated cases. Record the full
attempted denominator, asymmetric failures and the paired-success intersection.
Require at least `evaluation.validation_articles` common successful pairs.
Report paired distributions and spread, not only two unpaired means.

Twenty paired items, two models and three repeats is at least 120 inference
calls before canaries. Prove every job fits the current 330-minute workflow bound
with worst-case margin before dispatch; the six-hour platform maximum is not the
operative timeout. If it is sharded, each job must extract its items once and
run both models while those Article payloads remain on the same ephemeral disk.
Article bodies may not be uploaded as cross-job artifacts. Do not cache both
model files together.

Compare:

- summarize success rate and failure codes;
- mean HHEM and HHEM-full;
- unsupported numbers;
- dropped hedges;
- lead coverage;
- extractiveness and longest verbatim run;
- compression;
- word-band compliance;
- generated-title fallback rate;
- brief, abstract and truncated handling; and
- a human blind review of the same source-summary pairs.

HHEM alone is insufficient. A model can raise faithfulness by copying more or by
writing less.

No generic "no regression" threshold exists. Before revealing outputs, register
the direction, paired statistic and tolerance for every deterministic hard
metric. Compression stays a recorded diagnostic and is not a hard pass/fail
metric.

Register the human selection question and pass threshold before revealing model
identity or outputs. No generic human model-selection threshold exists today.
Without a pre-registered rule, human review can describe a trade and cannot
claim an automatic winner.

The existing human label queue records one summary's support verdict. It cannot
record paired informativeness, title quality or key-point correctness. A model
adoption needs a typed pairwise label shape and human-paced CLI before human
review can act as the selector. That tool must show frozen local source and
summary evidence, keep article bodies uncommitted, and globally shuffle rows so
HHEM-decile order does not leak the hidden score gradient.

## 7. Decide

The configured HHEM arithmetic remains a screening signal:

- fewer than `validation_articles` scored outputs -> no verdict;
- challenger gain below `validation_switch_margin` -> no automatic switch; and
- gain at or above the margin -> `switch_and_pause`.

It must not select the model because HHEM remains the production alarm. The
pre-registered blind human rule selects among candidates that pass the hard
compatibility, safety, success-rate, deterministic-metric and runner-budget
gates.

The owner can approve a model for reasons outside the automated margin. Record
that approval and the measured trade in the pull request and living docs. Do not
rewrite the measurement to make the approval look automatic.

## 8. Adopt the model

Do not change historical payloads or historical measurement rows.

Update the current surfaces:

1. `config/idhazh.json`
   - model id;
   - repository;
   - GGUF file;
   - quantisation; and
   - exact SHA-256.
2. `.github/workflows/digest.yml`
   - summary model repository and file;
   - cache identity includes verified GGUF SHA and pinned runtime identity.
3. `.github/workflows/validate.yml`
   - configured incumbent and generic candidate handling.
4. `.github/workflows/measure.yml`
   - runtime-sweep model when the candidate becomes the incumbent.
5. Current docs and diagrams that name the configured model.
6. Tests that assert the configured default or workflow model. Do not replace
   fixture ids that are intentionally historical or generic.

A value-only model change does not change a JSON shape. If the work also makes
SHA-256 required, adds a runtime-build field, or changes a persisted contract,
update the Pydantic contract, version, changelog, migration, generated schema
and drift tests together.

## 9. Fix identity before trusting the rollout

The determinism contract says the fingerprint records the GGUF file the runtime
opened, llama.cpp build, chat template and runner class. The current `stage_work`
passes `ModelRef.sha256` (or 64 zeroes), the literal `llama-server-local`, the
model id as the chat-template identity and `local` as the runner. It does not
observe those production inputs.

That is a pre-existing implementation gap. A model swap must not leave the new
model recorded as zeroes or the runtime recorded as local. Pass the observed
GGUF SHA-256 and runtime build into `work`, compare the GGUF hash to config, and
test the fingerprint and manifest paths before rollout.

## 10. Cache transition and rollout

The steady-state cache must hold the summary model and router model. The
transition can temporarily hold the old summary model too and cross the 10 GB
repository ceiling. Production derives the worker count from the plan as
`min(ceil(items / run.shard_size), run.max_parallel)`, so a full day at
`run.safety_ceiling_per_run` gives a worker 40 items. Do not size a timeout from
a fictional five-item shard.

Before the first production run:

```bash
gh cache list --limit 100
```

Delete only the old summary-model cache after the new commit is ready:

```bash
gh cache delete <old-summary-cache-id>
```

Keep the router cache.

Then:

1. Run the full local gates.
2. Run a one-URL local smoke through the candidate config.
3. Verify bounded worker selection against the day you plan to run.
4. Run a manual Content refresh only after its measured worker population fits.
5. Inspect item-health failure codes, per-item read/write rates, the fingerprint
   row, run manifest, cache state and published summaries.
6. Confirm no model directory or diagnostic payload is tracked.
7. For rollback, pause normal workers, delete the candidate summary cache,
   revert the adoption commit, fill the incumbent summary cache once without
   fanout, verify its identity and health, then resume normal workers. Do not
   edit historical output.

Do not raise a timeout or lower a quality threshold to make the candidate pass.
Measure the cause or reject the candidate.

## See also

- [test-models-locally.md](test-models-locally.md) - download, serve and measure the local models.
- [troubleshoot-one-url.md](troubleshoot-one-url.md) - run one real URL through fetch, extraction and summarization.
- [run-the-gates.md](run-the-gates.md) - the complete local validation commands.
- [../concepts/evaluation.md](../concepts/evaluation.md) - model-choice arithmetic and metric limits.
- [../concepts/config.md](../concepts/config.md) - model and runtime knobs.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - rendered bands, decoder rails and prompt controls.
- [../architecture/summarize/throughput.md](../architecture/summarize/throughput.md) - read/write rates and prompt reuse.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - the fingerprint contract.
- [../reference/measurements.md](../reference/measurements.md) - candidate facts, runner numbers and open measurements.
- [../../CLAUDE.md](../../CLAUDE.md) - Rules #2, #3, #6, #9, #10 and #11.
