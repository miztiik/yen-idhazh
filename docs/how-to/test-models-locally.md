# Test the models locally

**Last Updated**: 2026-08-22

How to run the pipeline's models on your own machine, compare them, and read the
result. Everything here also runs in CI - the point of doing it locally is a
fast loop, not a different answer.

There are three models in this project and they are tested differently:

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

## Serve a model

```bash
LD_LIBRARY_PATH=backend/bin backend/bin/llama-server \
  --model backend/models/Qwen3-8B-Q4_K_M.gguf \
  --alias qwen3-8b-q4-k-m \
  --ctx-size 8192 --batch-size 512 --ubatch-size 512 \
  --threads 4 --port 8080 --no-warmup
```

On Windows, `backend\bin\llama-server.exe` with the same flags.

**Use `--threads 4` even on a bigger machine.** The runner has 4 vCPU, and a
number measured on eight threads is not a number about production.

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
python -m idhazh plan --date 2026-08-22 --cap 6

# with the 8B served
python -m idhazh validate --date 2026-08-22 --leaderboard 0.75

# restart llama-server on the 4B, then
python -m idhazh validate --date 2026-08-22 --leaderboard 0.74

python -m idhazh decide --runner local
```

The corpus is the day's own run plan, not a curated list of addresses. A
hand-picked set decays immediately - the first one this project had lost three
of twenty within hours. `--cap 6` raises each vertical past its daily cap,
because that cap is how much a reader wants in a morning, not how much a
measurement needs.

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

python backend/utilities/summarise_bench.py backend/var/llm.json
```

`730 / 1800 / 4850` are the token counts a short, medium and long article
actually produce. The summariser turns tok/s into seconds per article using the
**measured** length buckets, not assumed ones.

On the runner, 2026-08-22: the 8B decodes at 7.28 tok/s and blends to 196 s an
article; the 4B at 13.00 tok/s and 112 s.

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
| The reply "did not hold its shape" | Usually the output budget, not the model. `models.inference.max_output_tokens` is 500; at 250 it ran out mid-object and failed as a shape error. |
| An item degrades with "page furniture is short" | Extraction found under `extract.min_source_words` (250). Release-note feeds trip this constantly, which is why it is set there. |
| A summary is dropped for word count | `evaluation.summary_words_min/max`, currently 40 and 250. |

## See also

- [`run-the-pipeline.md`](run-the-pipeline.md) - the daily run and its stages.
- [`set-up-local-inference.md`](set-up-local-inference.md) - llama.cpp in more detail.
- [`../reference/measurements.md`](../reference/measurements.md) - every measured number, with hardware and date.
- [`../concepts/evaluation.md`](../concepts/evaluation.md) - what the scores mean.
