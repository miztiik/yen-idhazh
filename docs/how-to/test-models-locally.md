# Test the models locally

**Last Updated**: 2026-08-23

How to run the pipeline's models on your own machine, compare them, and read the
result. Everything here also runs in CI - the point of doing it locally is a
fast loop, not a different answer.

There are four models in this project and they are tested differently:

| Model | Role | How you test it |
| --- | --- | --- |
| Qwen3-8B-Q4_K_M | writes the summaries | serve it, run `work`, read the eval rows |
| Qwen3-4B-Q4_K_M | decides chart / diagram / nothing | serve it, run `route`, look at the SVG |
| HHEM-2.1-Open | scores summaries against their source | it loads inside `work`; check `hhem` in the ledger |
| all-MiniLM-L6-v2 | on-device search, in the browser | committed under `frontend/static/`; `npm run test:browser` |

## Before anything

```bash
python -m venv .venv
.venv/bin/pip install -e ".[dev,faithfulness]"   # .venv/Scripts/pip on Windows
```

`faithfulness` pulls torch and transformers - several hundred megabytes. Without
it the pipeline still runs and still publishes; you simply get no faithfulness
scores, and every item is banded by the model-free counterweights instead.

## Get llama.cpp and the weights

Neither is committed. Both are gitignored.

```bash
mkdir -p backend/bin backend/models
```

**The runtime.** Take the newest `llama-b*-bin-<your-platform>.tar.gz` (or
`.zip` on Windows) from <https://github.com/ggml-org/llama.cpp/releases> and
unpack the whole `bin` directory into `backend/bin/`.

For a controlled comparison with the hosted model and thread measurements, use
build `b10598`. The workflow verifies the Linux archive against SHA-256
`d77a09db4165f8850b513629ed0ffeaab7851bb03e7cc3870b74e721f894694c`.
A number from another build is a separate measurement.

> Copy the **directory**, not just `llama-server`. These builds link against
> `libllama-common.so.0` and friends, and several of those are symlinks. Copying
> the one binary produces a `127` at exec that names a library rather than the
> mistake.

**The weights.**

```bash
curl -L -o backend/models/Qwen3-8B-Q4_K_M.gguf \
  "https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/main/Qwen3-8B-Q4_K_M.gguf?download=true"
curl -L -o backend/models/Qwen3-4B-Q4_K_M.gguf \
  "https://huggingface.co/Qwen/Qwen3-4B-GGUF/resolve/main/Qwen3-4B-Q4_K_M.gguf?download=true"
```

4.7 GB and 2.4 GB. Measured on a runner 2026-08-22: 180 s and 32 s to download.

To compare the Qwen3.5 candidate against the configured summarizer, add:

```bash
curl -L -o backend/models/Qwen3.5-9B-Q4_K_M.gguf \
  "https://huggingface.co/unsloth/Qwen3.5-9B-GGUF/resolve/main/Qwen3.5-9B-Q4_K_M.gguf?download=true"
```

That file is 5.29 GiB. It took 118 s to download on `ubuntu-latest` on
2026-08-23, `n=1`; spread is unavailable. The download rate is not stable
enough to extrapolate from.

### Local files are not the GitHub Actions cache

`backend/models/` is ordinary disk on your machine. The files stay there until
you delete them. List them on Windows:

```powershell
Get-ChildItem backend\models -Filter *.gguf |
  Select-Object Name, @{Name = "GiB"; Expression = {[math]::Round($_.Length / 1GB, 2)}}
```

On Linux:

```bash
du -h backend/models/*.gguf
```

The 5.2 GiB cache reported during the Qwen3.5 measurement was different. It was
an `actions/cache` archive stored by GitHub and restored only onto hosted
runners. It was never on the developer machine. Inspect repository caches with:

```bash
gh cache list --limit 100
```

Delete one by its numeric ID with `gh cache delete <id>`. The arbitrary-model
measurement job no longer caches weights: a cache keyed independently of the
`models` input can restore the wrong model, and one cache holding several
candidates can exceed the repository's 10 GB ceiling. Scheduled pipeline jobs
still cache their one configured model under a model-specific key.

## Serve a model

The flags are not yours to choose. `server_argv` builds them from `config/`, and
that argv is a fingerprint input, so a flag typed by hand here is a different
server from the one CI runs. Ask for the command instead of copying one:

```bash
python backend/utilities/llama_server_argv.py \
  --config config \
  --binary backend/bin/llama-server \
  --weights backend/models/Qwen3-8B-Q4_K_M.gguf \
  --alias qwen3-8b-q4-k-m \
  --format shell
```

Today that prints:

```bash
backend/bin/llama-server --model backend/models/Qwen3-8B-Q4_K_M.gguf \
  --alias qwen3-8b-q4-k-m --ctx-size 8192 --batch-size 512 \
  --ubatch-size 512 --threads 4 --port 8080
```

Run it with `LD_LIBRARY_PATH=backend/bin` in front. On Windows, use
`backend\bin\llama-server.exe`; the generator prints the same flags.

`digest.yml` starts its server the same way, from the same generator, and a test
fails if the two ever disagree. **`--no-warmup` is no longer passed** - the page
fault is paid either way, so the workflow now pays it during `pip install`
instead of inside the first request.

**Use `--threads 4` when reproducing the current runner baseline.** GitHub gives
the VM four scheduler-visible CPUs. That does not mean four physical cores plus
eight extra logical processors. If simultaneous multithreading is exposed, its
logical processors are already included in that count. The process can create
eight software threads, but the guest still schedules them onto four vCPUs.

Do not assume that oversubscription is slower either. Measure it. The
`measure.yml` workflow accepts a comma-separated thread list and records
`nproc`, the CPU-to-core map, SMT sibling lists and the cgroup CPU quota beside
the result.

Check it is up before you blame anything else:

```bash
curl -sf http://127.0.0.1:8080/health
```

## Run one day

```bash
python -m idhazh plan     --date 2026-08-22
python -m idhazh work     --date 2026-08-22 --shard 0 --shards 1
python -m idhazh route    --date 2026-08-22   # restart the server on the 4B first
python -m idhazh assemble --date 2026-08-22
```

Add `--no-faithfulness` to skip the scorer. The digest still publishes; the
ledger stays empty and every item is banded by the counterweights.

What you get:

```
backend/var/run/2026-08-22/items/*.article.json    what was fetched
backend/var/run/2026-08-22/items/*.summary.json    what the model wrote
backend/var/run/2026-08-22/items/*.eval.json       what it scored
frontend/public/digest/2026/08/22/digest.json      the published day
frontend/public/digest/2026/08/22/*.svg            any rendered visual
state/scores.csv                                   one row per scored item
```

## Read the timings

`work` logs each stage separately, because a slow item is either a slow host or
a slow model and only one of those is yours to fix:

```
item scored id=energy-01 band=high fetch=812ms extract=140ms model=214300ms score=1840ms
```

The same four numbers land in the payloads as `fetch_ms`, `extract_ms`,
`summarize_ms` and `score_ms`, and the published `/console/` page shows the
daily medians.

## Compare two models properly

This is the gate from Row #7. It exists because a published leaderboard ranks
models against **their** prompt, **their** extraction and **their** corpus -
three variables between that number and yours.

```bash
# plan the corpus once, so both models score the identical list
python -m idhazh plan --date 2026-08-22

# with the 8B served
python -m idhazh validate --date 2026-08-22 --leaderboard 0.75

# restart llama-server on the 4B, then
python -m idhazh validate --date 2026-08-22 --leaderboard 0.74

python -m idhazh decide --runner local
```

The corpus is the day's own run plan, not a curated list of addresses. A
hand-picked set decays immediately - the first one this project had lost three
of twenty within hours.

Plan takes no size flag. There is no daily cap to raise: the plan is whatever
the day's sources supplied, ranked
([../architecture/sources/freshness.md](../architecture/sources/freshness.md)).
A quiet day gives you a small corpus, and a small corpus is a weak comparison -
plan a busier date rather than tuning a number.

`validate` writes one result file per model under `backend/var/validation/`.
`decide` applies the rule and writes `state/validation-<date>.csv`.

The rule, in full:

- The incumbent measuring more than **0.10** below its published score means the
  ranking was not describing your pipeline. Score the others too.
- A challenger ahead by at least **0.05** on your corpus changes the pick.
- Fewer than **20** scored articles on either side means it refuses to judge
  rather than judging on thin evidence.

Both thresholds are in `config/idhazh.json` under `evaluation`.

`decide` exits non-zero on a switch. That is deliberate: swapping the model
changes a persisted contract and re-goldens every fixture, so it pauses for a
human instead of doing it.

### What the gate said on 2026-08-22

Measured on `ubuntu-latest`, 17 of 20 articles (three addresses had already
rotted):

| Model | Published score | Measured here |
| --- | --- | --- |
| Qwen3-8B-Q4_K_M | 0.750 | **0.887** |
| Qwen3-4B-Q4_K_M | 0.740 | **0.891** |

Both beat their published number by about 0.14, and the two are within 0.004 of
each other - well inside the 0.05 margin, so no switch. The verdict was still
`rescore_candidates`, because 17 is below the 20 the gate requires. That is the
rule working: it declined to conclude.

## Benchmark raw throughput

Speed, separately from quality:

```bash
LD_LIBRARY_PATH=backend/bin backend/bin/llama-bench \
  -m backend/models/Qwen3-8B-Q4_K_M.gguf \
  -p 730,1800,4850 -n 250 -t 4 -r 3 -o json > backend/var/llm.json

python backend/utilities/summarise_bench.py backend/var/llm.json \
  --system-prompt-tokens 879 --truncation-cap-tokens 2500 --parallel 4
```

`730 / 1800 / 4850` are the token counts a short, medium and long article
actually produce. The summariser turns tok/s into seconds per article using the
**measured** length buckets, not assumed ones. Derived seconds require the
rendered prompt count for that model. Omit `--system-prompt-tokens` when
comparing models with different tokenizers; raw prefill and decode rates remain
comparable, but one model's prompt count is not the other's.

On the runner, 2026-08-22: the 8B decodes at 7.28 tok/s; the 4B at 13.00 tok/s.
Using the current maximum 879-token prompt, the derived blends are 229 s and
130 s per article for the 8B and 4B respectively. The throughput is measured;
the per-article figures are derived from it, the measured corpus buckets and
the production 2500-token truncation cap.

### Compare two models and several thread counts locally

The cross-platform utility downloads any missing files into the gitignored
model directory, hashes them, finds `llama-bench` under `backend/bin`, runs exact
paths and prints one result per model and thread count:

```bash
python backend/utilities/measure_llm.py \
  --models "Qwen/Qwen3-8B-GGUF:Qwen3-8B-Q4_K_M.gguf,unsloth/Qwen3.5-9B-GGUF:Qwen3.5-9B-Q4_K_M.gguf" \
  --threads "1,2,4,8"
```

On Windows, use `.venv\Scripts\python.exe` if `python` is not the project
interpreter. On Linux, set `LD_LIBRARY_PATH=backend/bin` if the prebuilt runtime
uses shared libraries.

The raw result lands at `backend/var/llm.json`; runtime and weight SHA-256
digests land at `backend/var/weights.txt`; cgroup CPU, pressure and memory
snapshots before and after each point land at `backend/var/resources.json`.
All three paths are gitignored.

This can take hours at one thread. To answer only whether eight threads beat the
current four-thread setting, use `--threads "4,8"`.

Check the local topology before interpreting the result:

```powershell
Get-CimInstance Win32_Processor |
  Select-Object Name, NumberOfCores, NumberOfLogicalProcessors
[Environment]::ProcessorCount
```

```bash
nproc
lscpu -e=CPU,CORE,SOCKET,NODE,ONLINE
```

A local optimum is only a local result. Production changes only after the same
sweep runs on `ubuntu-latest` with three repeats and the spread recorded
(Rule #10).

Run the hosted sweep after this workflow version is on the default branch:

```bash
gh workflow run measure.yml \
  -f target=llm \
  -f models='Qwen/Qwen3-8B-GGUF:Qwen3-8B-Q4_K_M.gguf' \
  -f threads='4,8'
```

The LLM job downloads only that model, runs both thread counts and uploads
`hardware.txt`, `weights.txt`, `resources.json` and `llm.json` in the
`bench-llm` artifact. Image and corpus jobs are separate suites, so a CPU
question does not start two unrelated jobs.

If eight threads win that screen outside the measured spread, test the actual
five-item server path before changing production:

```bash
gh workflow run measure.yml \
  -f target=runtime \
  -f runtime_candidate=threads \
  -f runtime_threads=8
```

That job runs the current four-thread baseline and the eight-thread candidate
three times each against one fixed five-article plan, interleaved by repeat. It
rejects the candidate if source text or any output digest changes. Production
stays at four threads until both measurements agree **and** production runs the
same recorded llama.cpp bytes; production does not pin that build yet.

## Test the browser model

The search encoder is committed, so there is nothing to download:

```bash
cd frontend
npm ci
npx playwright install chromium
npm run build
npm run test:browser
```

Seventeen tests: eight injection canaries on the published surface, the visual
path, and a hand-labelled retrieval bar.

To prove the digest does not depend on it at all:

```bash
mv static/assist ../assist-parked && npm run build
test ! -d build/assist && grep -q Archive build/archive/index.html
mv ../assist-parked static/assist
```

The digest must render complete with the model directory gone. CI runs exactly
this.

## When it goes wrong

| Symptom | Cause |
| --- | --- |
| `error while loading shared libraries: libllama-common.so.0` | You copied `llama-server` alone. Copy the whole `bin` directory - some of those files are symlinks. |
| Every item logs `model unreachable` | The server is not up. `curl` the health endpoint before blaming the pipeline. |
| `'HHEMv2ForSequenceClassification' has no attribute 'all_tied_weights_keys'` | transformers is too new. The pin is `<5`; check what actually resolved. |
| The reply "did not hold its shape" | Usually the output budget, not the model. `models.inference.max_output_tokens` is 900 - a crash guard, not a length control. At 250 it ran out mid-object and failed as a shape error, which named the wrong cause. |
| An item degrades with "page furniture is short" | Extraction found under `extract.min_source_words` (60). That floor is derived, not chosen: `brief_target_words_min / brief_compression_ceiling`, or 30 / 0.5. A short release note no longer trips it - it publishes as a brief and the census row carries `not_prose`. |
| A summary is dropped for word count | `evaluation.summary_words_min/max`, currently 25 and 250. |

## See also

- [troubleshoot-one-url.md](troubleshoot-one-url.md) - fetch, extract and summarize one URL without publishing a digest.
- [`run-the-pipeline.md`](run-the-pipeline.md) - the run and its stages.
- [`set-up-local-inference.md`](set-up-local-inference.md) - llama.cpp in more detail.
- [`../reference/measurements.md`](../reference/measurements.md) - every measured number, with hardware and date.
- [`../concepts/evaluation.md`](../concepts/evaluation.md) - what the scores mean.
