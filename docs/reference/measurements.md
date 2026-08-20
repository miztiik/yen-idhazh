# Measurements

**Last Updated**: 2026-08-21

Every number this project's design rests on, with the hardware it was taken on,
the date, and the spread. Holy Law #10 in one page: **an unmeasured number is
labelled an estimate and may not be used to justify a design.**

Two rules govern this page:

- A figure is either **measured** - and then it carries hardware, date and
  spread - or it is listed under [Still unmeasured](#still-unmeasured) with the
  measurement that would settle it. There is no third category.
- **A laptop measures the laptop.** Every figure below taken on an i7-1265U is
  an order-of-magnitude check, not a runner figure. The runner has a different
  core topology, different memory bandwidth, and a shared host. Nothing here
  substitutes for `.github/workflows/measure.yml` running on `ubuntu-latest`.

## Inference throughput

`llama-bench -m <model> -p 730,1800,4850 -n 250 -t 4`, at the three input
lengths a short, medium and long article actually produce.

### Qwen3-4B-Q4_K_M

Hardware: Intel Core i7-1265U, 4 threads. Date: 2026-08-15. Repeats: 3.

| n_prompt | prefill tok/s | stddev |
| --- | --- | --- |
| 730 | 24.05 | 1.46 |
| 1800 | 18.35 | 4.49 |
| 4850 | 12.34 | 3.02 |
| decode (250) | 6.07 | 0.15 |

### Qwen3-8B-Q4_K_M

Hardware: Intel Core i7-1265U, 4 threads. Date: 2026-08-15. Repeats: 2.

| n_prompt | prefill tok/s | stddev | vs 4B |
| --- | --- | --- | --- |
| 730 | 9.30 | 0.80 | 2.6x slower |
| 1800 | 8.40 | 2.00 | 2.2x slower |
| 4850 | 6.30 | 0.30 | 2.0x slower |
| decode (250) | 1.84 | 0.17 | **3.3x slower** |

### Derived seconds per article

Derived from the two tables above by `backend/utilities/summarise_bench.py`,
using the length buckets in [Corpus shape](#corpus-shape). Derived, not
measured: they inherit both the throughput spread and the bucket error.

| bucket | 4B typical | 8B typical | multiple |
| --- | --- | --- | --- |
| short | 55 s | 160 s | 2.9x |
| medium | 131 s | 323 s | 2.5x |
| long | 435 s | 906 s | 2.1x |
| blended | 173 s | 399 s | 2.3x |

Worst case matters more than the blend for one decision: a single long article
on the 8B is 1223 s worst, so a five-URL shard that draws five long articles is
roughly 102 minutes. Job timeouts are set from that number, not from 399 s.

**Three findings that changed the design**, all of which contradicted an
estimate:

1. **Prefill tok/s degrades with context length** (24.1 -> 18.3 -> 12.3 on the
   4B). The estimate assumed a constant rate; attention is quadratic, so the
   long bucket came out 4.5x worse than predicted while short was only 1.9x
   worse. Any future length estimate has to model prefill as a function of
   context length.
2. **Decode degrades worse than prefill on the larger model** (3.3x against
   2.0x) despite roughly 2x the weights. Decode is memory-bandwidth-bound and
   4.68 GiB streams from RAM with no reuse, while prefill still gets arithmetic
   intensity from batching. Output length is therefore a first-class cost lever
   on the 8B: 250 tokens at 1.84 tok/s is 136 s of pure decode.
3. **Truncation is a performance lever, not only a safety cap.** Capping at
   2500 instead of 6000 input tokens takes a long 8B article from ~906 s to
   ~450 s and the blended figure from 399 s to ~308 s.

The stddev is ~25% of the mean at 1800 and 4850 tokens, which is thermal
throttling on a laptop. A shared-host runner may be better or worse; the CI run
must report its own spread rather than inherit this one.

## Weights on disk

Hardware: local filesystem. Date: 2026-08-21. Method: `stat`.

| File | Bytes | GiB |
| --- | --- | --- |
| `Qwen3-4B-Q4_K_M.gguf` | 2,497,280,256 | 2.33 |
| `Qwen3-8B-Q4_K_M.gguf` | 5,027,783,488 | 4.68 |
| both | 7,525,063,744 | 7.01 |

This is why the weights are cached rather than committed: GitHub hard-rejects
any file over 100 MB, and both files sit inside the 10 GB repository cache with
under 3 GB to spare.

## Published payload size

### Prose compression

Hardware: Intel Core i7-1265U. Date: 2026-08-20. Method: gzip over 32 prose
files, 276,887 B -> 94,690 B.

**2.92x.** This is the ratio the day-payload arithmetic uses.

### The day payload

Hardware: Intel Core i7-1265U. Date: 2026-08-21. Method: gzip level 9 over
`tests/fixtures/contracts/digest-day/two-runs.json`.

| Quantity | Value |
| --- | --- |
| Fixture day, 3 items | 3,650 B raw, 1,078 B gzipped (3.39x) |
| Per item, raw | 1,217 B |

**Read this as the contract's overhead, not as a production day.** The fixture
carries three items with short summaries, and gzip over 3.6 KB has barely
warmed its dictionary. It replaces the earlier ~2.2 KB-per-item estimate as an
order-of-magnitude check on the *shape*; a real 17-item day is measured after
the first pipeline run, not before it.

### Days to the 1 GB Pages ceiling

Derived from the above plus the image estimates below, which are the weak link -
see [Still unmeasured](#still-unmeasured).

| Scenario | KB/day | days to 1 GB |
| --- | --- | --- |
| PNG, an image on every item | 8,537 | 123 (4 months) |
| WebP, an image on every item | 1,567 | 669 (22 months) |
| WebP, an image on one item in three | 547 | 1,917 (5.25 years) |
| no images | 37 | 28,340 |

The ordering of the levers falls straight out of this: encoding buys 5.6x,
honouring the visual rule buys another 2.9x, and retention is what remains
after both. See [../architecture/publishing/layout.md](../architecture/publishing/layout.md).

## Corpus shape

**Still invented.** The cost model assumes articles cluster at 400 / 1200 /
3500 words with a 25 / 55 / 20 share, and every per-article second in this page
is multiplied by that assumption. `backend/utilities/measure_corpus.py` fetches
real links, extracts them the way the pipeline will, and reports the
distribution against those bucket edges. Until the `corpus` job in
`.github/workflows/measure.yml` has run, the buckets are the largest unmeasured
input in the design.

## Still unmeasured

Each line names the measurement that would settle it. Nothing here may be cited
to justify a design decision.

| Quantity | Current basis | What settles it |
| --- | --- | --- |
| Prefill and decode on a real runner | laptop figures above | the `llm` job in `.github/workflows/measure.yml` |
| Article length distribution | invented buckets | the `corpus` job |
| Weight download time, cache-miss | unmeasured | the timed download step, which now records itself into `cache-state.txt` |
| Cache-restore time per job, cache-hit | ~90 s, asserted | the same artifact, on a second run |
| Image render seconds at 512 and 768 | unmeasured | the `image` job, against both candidate models |
| Image bytes, PNG at 768 | ~500 KB, estimate | the `image` job writes the file; measure it |
| Image bytes, WebP q80 at 768 | ~90 KB, estimate | re-encode the same file and measure |
| A production day payload | fixture figure above | the first real pipeline run |
| HHEM scoring seconds per item on CPU | unmeasured | lands with the eval harness |
| Whether 1-2 bit quantisation changes the fit | unevaluated | open question 4 in the plan-doc |

## How to add a row here

Run the measurement, then record the quantity, the value, the spread, the
hardware and the date. If a number arrives without those four, it is an
estimate and belongs in the table above rather than in the tables below it.

When a measurement contradicts a design, the design changes - that has already
happened three times on this page.

## See also

- [../../CLAUDE.md](../../CLAUDE.md) - Holy Law #2 (the runner is the architecture) and #10 (measured, not estimated).
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the published-size arithmetic these numbers feed.
- [../concepts/pipeline-loop.md](../concepts/pipeline-loop.md) - the batch-size rule these numbers set.
- [../how-to/set-up-local-inference.md](../how-to/set-up-local-inference.md) - reproducing the local runs.
