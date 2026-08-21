# yen-idhazh - static-first article digest pipeline - plan

**Last Updated**: 2026-08-21
**Level**: 4 (structural, new subsystem) with named Level-5 ESCALATE triggers.

Execute per `docs/how-to/execute-a-plan.md`, with one owner override in force (2026-08-21, `CLAUDE.md` section 0): **one agent works this repo and commits direct to `main`** - no worktree isolation, no worker-per-row fan-out and no PRs, because there is no second agent to isolate from and nobody to review a PR. Everything else stands: personas are consulted on ambiguity, rows respect the Depends-on column, gates must be green before a row is marked DONE, parallel N = 3, and the ESCALATE triggers in section 0 are honoured. A trigger that fires mid-execution is handled per `docs/how-to/handle-scope-change.md`.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Ship a daily job that summarizes public articles with a small LM inside GitHub Actions, scores every summary for faithfulness, and commits a dated JSON digest payload a static site renders - with no runtime backend. |
| Hard scope - in | Config-driven multi-vertical source discovery (a curated RSS/Atom feed list per vertical, cross-source repetition ranking, cross-cutting lenses, an entity watchlist); `trafilatura` extraction; Qwen3-8B summarization under constrained decoding; four-way visual routing; Vega-Lite + Mermaid deterministic renderers; HHEM dual-score eval + CSV; GitHub Pages eval dashboard; per-URL atomic worker jobs; dated published layout with topic routes, read-state and pagination; a **secondary, reader-initiated on-device assist** (build-time embeddings, browser semantic search, read-aloud) that the digest never depends on. |
| Hard scope - out | Runtime backend; hosted inference anywhere; accounts; push notifications; paywalled sources; republishing article bodies; LLM-as-judge evaluation; fine-tuning; GPU runners; larger-than-9GB pipeline models; any browser model whose largest single file exceeds GitHub's 100 MB per-file hard limit; any on-device feature on the digest's critical path. |
| ESCALATE triggers | (1) Row 7 model-validation gate fails its decision rule -> model pick is re-derived, PAUSE. (2) Any move to hosted inference - reverses the static-first premise. (3) Row 9 measurement shows images cannot fit the published budget -> the renderer is descoped, PAUSE. (4) 3x cost overrun on any row. (5) A browser model considered for row 23 has a single file over 100 MB - it cannot be committed, PAUSE. (6) Row 21 browser canaries fail against the chosen browser model. |
| Chosen strategy | Runtime pipeline is orchestrator + disposable sharded workers, mirroring the plan-execution model: a `plan` job emits and shards the URL list, a `matrix` of workers each handles a shard on its own VM and writes one JSON per item, an `assemble` job renders the digest. Ruled by Fowler (contracts before logic) and Carmack (fresh-VM-per-job is the parallelism primitive; shard size is set by measured model-load amortization). |
| Execution | Single agent, direct to `main` (owner override, 2026-08-21). Personas still consulted on ambiguity; row order still governed by Depends-on. Parallel N = 3 applies to how many rows may be in flight, not to worktrees. |
| Roster note (2026-08-20) | This plan was authored against a five-persona roster that included Palm (casual-game design) and Player. Both are gone; the roster is now Reader, Jony, Andre, Fowler, Carmack (`CLAUDE.md` section 14). Decisions already ruled stand as written and are NOT reopened. But **Andre (AI / LLM) now owns model quality, prompt strategy, constrained decoding, eval design and metric choice** - so rows 4, 6, 7 and 9 must consult him even where the existing attribution says Fowler or Carmack. The standing split: Andre owns whether a model is good enough, Carmack owns whether it fits. |

### 0.2 Capacity ceilings (platform verified 2026-08-15; corrected and extended 2026-08-20)

| Limit | Free | Pro | Team | Source |
| --- | --- | --- | --- | --- |
| Concurrent jobs | 20 | 40 | 60 | GitHub Actions limits |
| Job execution time | 6 h | 6 h | 6 h | same |
| Matrix jobs / workflow run | 256 | 256 | 256 | same |
| Artifact storage | 500 MB | 1 GB | 2 GB | same |
| Cache storage / repo | 10 GB | 10 GB | 10 GB | same |
| Larger runners (8+ vCPU) | **not available** | **not available** | available | same |

#### Corrections and additions (verified 2026-08-20 against GitHub's Actions-limits, Actions-billing, dependency-caching and Pages-limits references)

| Limit | Value | Why it matters here |
| --- | --- | --- |
| **Actions minutes** | **Free and unmetered** on standard GitHub-hosted runners **because this repository is public.** The 2,000 min/month figure applies to private repositories only. | The monthly-minute ceiling this plan half-assumed does not exist. Wall-clock still matters - a 6 h job cap is a 6 h job cap - but there is no monthly budget to ration. |
| **Published Pages site** | **1 GB, hard.** | **This is the binding ceiling, and it arrives far sooner than section 0.2 originally implied.** At ~20 items/day with an image each, this plan's own growth figure (~3.6 GB/yr) crosses 1 GB in roughly **three to four months**, not twelve. A retention or off-site policy for rendered images is therefore a row-9 / row-11 design input, not a month-12 chore. |
| **Pages deployment timeout** | 10 min | A deploy that grows past this fails the publish even though the pipeline succeeded. Site size is a deploy-reliability concern, not only a storage one. |
| **Pages bandwidth** | 100 GB/month (soft) | Not binding at digest-scale readership. Recorded so nobody re-derives it. |
| **Pages builds/hour** | 10 (soft) - **does not apply** when publishing from a custom Actions workflow | We publish from a workflow, so this does not constrain us. |
| **`GITHUB_TOKEN` API** | **1,000 requests/hour per repository** | Shared by every job in every workflow run that hour. Fine at N=4 workers, but re-runs plus a matrix plus the commit step consume it, and exhausting it fails steps in ways that look unrelated to the cause. |
| **Cache rate limits** | 1,500 downloads/min, 200 uploads/min, 400 deletes/min per repo | Not binding at this scale. |
| **Workflow re-runs** | 50 per run | Relevant only to a pathological debugging session. |
| **Outbound network bandwidth from a runner** | **No documented cap** | GitHub does not publish an egress/ingress limit for Actions runners. So the ~7.2 GB weight download is not metered by GitHub - but it is still wall-clock, and it is still subject to the *upstream* host's own rate limits. |

**The one that changes a design:** the 1 GB published-site cap converts "images accumulate forever" from a slow-burn concern into a hard failure inside the first year. Row 9 (image renderer) and row 11 (dashboard) must both be designed against a published-site budget, and the retention policy is part of the row rather than a follow-up.

**Cache eviction is the ceiling nobody plans for** (verified against GitHub's dependency-caching reference, 2026-08-20): a cache entry **not accessed in over 7 days is deleted**, and once the repo passes 10 GB entries are evicted oldest-access-first. Two consequences for this design:

- The weights survive between runs **only because the schedule is daily.** A pause longer than a week - a holiday, a paused workflow, a repo left alone - costs a full re-download on the next run. That is a recoverable cost, not a failure, but the run that pays it will look anomalously slow and should not be mistaken for a regression.
- **Cache restore happens once per JOB, not once per run.** Every matrix worker restores the weights onto its own fresh VM. Four parallel workers pay it four times. This is the measurement behind row 10 decision 6 (shard rather than fan out per URL) and it is the single largest fixed cost in the pipeline.

Committing the weights instead is not an option and is not a tradeoff worth re-examining: GitHub hard-rejects any file over 100 MB, and the quantisations here are 2.4 GB and 4.8 GB. Git LFS is the only "commit" path and it is strictly worse - the free tier is 1 GB of storage and 1 GB of bandwidth per month against 7.2 GB of weights, and every runner would still download on checkout, only now metered.

Derived article ceilings, using the section 2.1 blended figure:

| | per job (6 h) | x20 concurrent | binding? |
| --- | --- | --- | --- |
| Qwen3-4B @ 173 s/article | 124 | **2,480/day** | no |
| Qwen3-8B @ 399 s/article (measured, 2.2) | 54 | **1,080/day** | no |

**Compute is not the ceiling.** The real limits, in the order they bite:

| # | Ceiling | Value | Why it bites first |
| --- | --- | --- | --- |
| 1 | Source supply | 17/day configured | Set by the per-vertical daily caps in row 3.1, not by any one site. Supersedes the HN-front-page ceiling as of 2026-08-20. |
| 2 | Reader attention | ~10-20/day | **Binding.** Nobody reads 100 summaries. If nobody reads it, open question 2 applies. |
| 3 | **Published Pages site** | **1 GB, hard** | **Corrected 2026-08-20.** At ~20 items/day with an image each this is crossed in roughly 3-4 months - the earliest hard failure in the table, and the reason a retention policy is a row-9 design input rather than a month-12 chore. Exceeding it also risks the 10-minute deploy timeout. |
| 4 | Repo growth | see 0.3 | Committed forever, and permanent: deleting from the working tree does not shrink history, and a rewrite is forbidden by section 8. The only lever on repo size is not committing the bytes in the first place. |
| 5 | Concurrency | 20 jobs | Only reachable at 2,000+ articles/day. |
| - | ~~Actions minutes~~ | **not a ceiling** | Free and unmetered on a public repository. Struck 2026-08-20. |
| - | ~~Artifact storage~~ | **not a ceiling** | **Struck 2026-08-20.** The 500 MB figure is the *private*-repository quota; Actions storage is free on a public repo, and `actions/upload-pages-artifact` defaults to `retention-days: 1`. This is the identical correction already applied to Actions minutes, which the first pass missed. |

**Topic verticals** (the second reading, resolved 2026-08-20): segmenting is a *source-diversity* problem, not a compute one, and the resolution is row 3.1. Five verticals at 25+ feeds each is roughly 125 feeds to curate; that curation, not CPU, is the work. Prior art agrees on the floor - Kagi News will not surface a category below 25 feeds.

**Ruling: cap N at 20/day and do not raise it on compute headroom alone.** Raising N is a supply and readership decision. The ratified taxonomy spends 17 of the 20, leaving headroom for one more vertical without re-opening this ruling.

### 0.3 Published-size arithmetic (2026-08-20)

Text is not the problem. Images are 99.6% of the bytes, and the encoding choice moves the
wall further than any retention policy can.

| Quantity | Value | Label |
| --- | --- | --- |
| Items/day | 17 | ratified, row 3.1 |
| Item JSON payload | ~2.2 KB raw | derived estimate; measure 17 real payloads after row 1 |
| Prose gzip ratio | **2.92x** | **measured** i7-1265U, 2026-08-20, 32 files / 276,887 B -> 94,690 B |
| Day payload, 17 items | 37 KB raw / **12.8 KB gz** | derived from the measured ratio |
| Image, 768px PNG | ~500 KB | **estimate** - `bench_image.py` has never been run |
| Image, 768px WebP q80 | ~90 KB | **estimate** - settle both with row 9 |

Days until the 1 GB Pages cap, by scenario:

| Scenario | KB/day | days to 1 GB | repo @ 5 yr |
| --- | --- | --- | --- |
| A: PNG, image on all 17 | 8,537 | **123 (4 months)** | 15.2 GB |
| B: WebP, image on all 17 | 1,567 | 669 (22 months) | ~3 GB |
| C: WebP, image on 1 in 3 | 547 | **1,917 (5.25 years)** | 1.03 GB |
| D: no images | 37 | 28,340 (77 years) | ~24 MB |

**The levers are ordered, and retention is third.** Encoding WebP instead of PNG buys 5.6x.
Honouring the visual rule already in `docs/concepts/digest.md` - "nothing" is the common
answer, so roughly one item in three carries an image - buys another 2.9x. Combined that is
15.6x, which moves the wall from month 4 to year 5. Retention is what remains after both,
and after both it may never need to be switched on. That is the intended outcome.

**Retention buys the Pages cap, not the repo.** Deleting a committed file leaves the blob in
history forever. Anything that must not grow the repo must not be committed at all.

### 0.1 Runtime topology (distinct from plan execution)

```
plan job                 worker jobs (matrix of SHARDS, fail-fast:false)  assemble job
 poll vertical feeds  ->  1 VM per shard of ~5 URLs, 4 vCPU each      ->   collect artifacts
 dedupe canonical URL     load model once per shard, then per URL:         render digest.json
 rank + tag lens/entity   fetch -> extract -> summarize -> route           append evals CSV
 take top N per vertical  -> render -> eval                                commit once
 shard urls[]             write backend/var/run/<date>/<vertical>-<NN>.json
 (no model)                                                               publish frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json
```

Shard rather than one-VM-per-URL: section 2.1 measured model load at roughly half of
per-URL wall-clock. Per-item atomicity survives inside the shard via a temp-then-rename
write plus skip-if-fingerprint-matches against the run index.

Both levels use the same rule: the orchestrator never does the work, and a worker failure is contained to one unit.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Contracts, schemas and repo scaffold | - | A | DONE | main | direct | - |
| 2 | Measurement harness: throughput + corpus shape | - | A | HARNESS-LANDED (ledger at `docs/reference/measurements.md`; runner run, corpus and image still unmeasured) | main | direct | - |
| 3 | Source discovery, fetch + extract | 1 | B | DONE | main | direct | - |
| 4 | Eval harness: HHEM dual-score + deterministic metrics | 1 | B | LANDED (scorer behind an optional extra; timing still unmeasured) | main | direct | - |
| 5 | Injection canary fixtures + CI assertion | 1 | B | DONE | main | direct | - |
| 15 | Pipeline fingerprint contract | 1 | B | DONE | main | direct | - |
| 6 | Summarize worker | 1, 2, 5, 15 | C | LANDED (determinism oracle needs a real model run - folds into row 7) | main | direct | - |
| 11 | Pages eval dashboard | 4 | C | PENDING (unblocked 2026-08-21: operator surface) | - | - | - |
| 19 | Build-time embeddings in the day payload | 1, 15 | C | PENDING | - | - | - |
| 7 | Model validation gate (ESCALATE) | 3, 4, 6 | D | PENDING | - | - | - |
| 8 | Route worker + deterministic renderers | 6, 7 | E | PENDING | - | - | - |
| 12 | Drift benchmark: weekly golden re-run + quarterly refresh | 4, 7 | E | PENDING | - | - | - |
| 9 | Image model measurement gate + renderer | 2, 5, 8 | F | PENDING | - | - | - |
| 10 | Pipeline orchestrator workflow | 3, 6, 8 | F | LANDED (plan -> sharded workers -> assemble; visual routing still absent) | main | direct | - |
| 13 | Published layout, date routing and the frontend shell | 1, 10 | G | PENDING | - | - | - |
| 14 | Retention job + site-budget alarm | 13 | H | PENDING | - | - | - |
| 16 | Read-state, new-arrivals block and pagination | 13 | H | PENDING | - | - | - |
| 17 | Icon sprite + registry allowlist | 13 | H | PENDING | - | - | - |
| 18 | On-device assist enabler (no feature) | 13 | H | PENDING | - | - | - |
| 22 | Read-aloud via Web Speech API | 13 | H | PENDING | - | - | - |
| 20 | Browser semantic search | 18, 19 | I | PENDING | - | - | - |
| 21 | Browser-runtime injection canaries | 18 | I | PENDING | - | - | - |
| 23 | Browser chat SLM (ESCALATE-gated) | 20, 21 | J | PENDING | - | - | - |

---

## Row #1 - Contracts, schemas and repo scaffold

- **Scope:** Land the typed schemas for every persisted payload plus the config file, before any logic reads or writes them.
- **Files touched:**
  - `backend/idhazh/contracts/{article,summary,route,eval_row,run_manifest,digest_day,sources,taxonomy,watchlist,app_config}.py` (Pydantic; the source of truth)
  - `schemas/{article,summary,route,eval-row,run-manifest,digest-day,sources,taxonomy,watchlist,app-config}.schema.json` (GENERATED from the models, never hand-written)
  - `config/idhazh.json`, `config/sources.json`, `config/taxonomy.json`, `config/watchlist.json`
  - `pyproject.toml`, `README.md`, `.gitignore`
- **Acceptance gates:** every schema validates against a committed fixture; `ruff` + `mypy --strict` clean; no hardcoded tunables outside `config/`.
- **Oracle:** round-trip - each fixture serializes, validates, deserializes, and re-serializes byte-identically.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `version` is a `YYYY-MM-DD` date-stamp with an in-schema `changelog` array. | Fowler |
| 2 | **No hash appears in any path, filename or URL - published or internal.** Per-item output is `backend/var/run/<date>/<vertical>-<NN>.json` (reproducible, gitignored); the COMMITTED record is the published digest under `frontend/public/` plus the eval rows. The digest is a rendering, never a source of truth. | Fowler |
| 2a | Item identity for dedupe and skip lives in a **payload field**, `url_key`, never in a path. Paths are for humans and for globs; identity is for the contract. Skip logic reads the run index, not the filesystem. | Fowler |
| 3 | Tunables (N, truncation cap, score bands, retry budget) live in `config/idhazh.json`. | Fowler |
| 4 | Every persisted shape is a Pydantic model in `backend/idhazh/contracts/` FIRST; `schemas/` and the frontend types are generated from it and gated on drift (CLAUDE.md section 1a). | Fowler |
| 4 | Lens and event vocabularies are closed enums in `schemas/taxonomy.schema.json`, not free-text strings. A new lens or event type is a schema change carrying a `changelog` entry. | Fowler |
| 5 | A vertical id, a lens id and an event id are immutable slugs. `display_name` is a separate, freely mutable field. Renaming what a reader sees must never orphan a payload. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Integer schema versions | Not self-documenting; date-stamp is ASCII-sortable and says when the shape moved. | Fowler |
| 2 | SQLite as the run store | One file per URL is what makes worker jobs independent and re-runnable. | Carmack |

---

## Row #2 - Measurement harness: throughput + corpus shape

- **Scope:** Replace every estimated number in the design with a measured one, on a stock `ubuntu-latest`.
- **Files touched:** `.github/workflows/measure.yml`, `backend/utilities/summarise_bench.py`, `backend/utilities/bench_image.py`, `backend/utilities/measure_corpus.py`, `docs/reference/measurements.md`
- **Acceptance gates:** workflow completes on a real runner; emits `bench-llm` and `bench-image` artifacts; `docs/reference/measurements.md` carries hardware, date and stddev for every figure.
- **Oracle:** coverage - every row currently marked "estimate" in `docs/reference/measurements.md` has a measured replacement with a stddev, or an explicit "still unmeasured" line.

**The canonical ledger is now [`docs/reference/measurements.md`](../docs/reference/measurements.md).** Sections 2.1 and 2.2 below are the working record that produced it and are deleted when this row closes. The harness landed 2026-08-21 - `measure_corpus.py`, a `corpus` job, and a `cache-state.txt` that distinguishes a cache-hit run from a cache-miss one. What remains is executing the workflow on a real runner, which needs the owner to dispatch it (or to authorise the agent to push and dispatch).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `llama-bench -p 730,1800,4850 -n 250 -t 4 -r 3` - prefill measured at the three real article lengths, not one synthetic length. | Carmack |
| 2 | Measure prefill and decode separately; prefill dominates long articles on CPU and is the figure everyone omits. | Carmack |
| 3 | Measure word counts of 200 real HN links; the short/medium/long buckets are invented until this runs. | Carmack |
| 4 | Time the GGUF download separately from inference so cache-hit and cache-miss runs are distinguishable. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Trust published tok/s figures | None are published for a 4-vCPU Azure runner; shared-host memory bandwidth varies ~2x run to run. | Carmack |
| 2 | Benchmark on the developer laptop only | Different core topology and memory bandwidth; a local i7 run measures the laptop, not the runner. | Carmack |

### 2.1 Measured - Qwen3-4B-Q4_K_M, 4 threads, i7-1265U, 2026-08-15

`llama-bench -p 730,1800,4850 -n 250 -t 4 -r 3`. Laptop, NOT a runner - treat as an
order-of-magnitude check pending the CI run.

| n_prompt | prefill tok/s | stddev |
| --- | --- | --- |
| 730 | 24.05 | 1.46 |
| 1800 | 18.35 | 4.49 |
| 4850 | 12.34 | 3.02 |
| decode (250) | 6.07 | 0.15 |

Derived per-article seconds (best / typical / worst):

| bucket | in_tok | typical | vs. estimate |
| --- | --- | --- | --- |
| short | 732 | 55 s | 29 s - 1.9x worse |
| medium | 1796 | 131 s | 49 s - 2.7x worse |
| long | 4855 | 435 s | 96 s - 4.5x worse |
| blended | - | 173 s | 55 s - 3.1x worse |

20 URLs: 58 min serial, 14 min at 4-wide.

**Three findings that changed rows 5, 9 and 10:**

1. **Prefill tok/s degrades with context length** (24.1 -> 18.3 -> 12.3). The estimate
   model assumed a constant prefill rate; attention is quadratic, so the long bucket is
   4.5x worse than predicted while short is only 1.9x. Any future estimate must model
   prefill as a function of context length, not a constant.
2. **The long bucket dominates cost.** At 20% of articles it contributes 87 s of the
   173 s blended - half the total. Truncation is therefore a performance lever, not just
   a safety cap (row 6 decision 6).
3. **Per-URL job granularity is now wrong** (row 10 decision 6). At ~90 s of cache
   restore per job against ~173 s of work, overhead was ~50% of wall-clock.
4. Stddev is 25% of the mean at 1800 and 4850 tokens - thermal throttling on a laptop.
   A shared-host runner may be better or worse; the CI run must report its own stddev.

### 2.2 Measured - Qwen3-8B-Q4_K_M, 4 threads, i7-1265U, 2026-08-15

`llama-bench -p 730,1800,4850 -n 250 -t 4 -r 2`. Same caveat: laptop, not a runner.

| n_prompt | prefill tok/s | stddev | vs 4B |
| --- | --- | --- | --- |
| 730 | 9.30 | 0.80 | 2.6x slower |
| 1800 | 8.40 | 2.00 | 2.2x slower |
| 4850 | 6.30 | 0.30 | 2.0x slower |
| decode (250) | 1.84 | 0.17 | **3.3x slower** |

| bucket | typical | 4B | multiple |
| --- | --- | --- | --- |
| short | 160 s | 55 s | 2.9x |
| medium | 323 s | 131 s | 2.5x |
| long | **906 s** | 435 s | 2.1x |
| blended | **399 s** | 173 s | 2.3x |

20 URLs: 133 min serial (2.22 h of the 6 h cap), 33 min at 4-wide.

**Findings:**

1. **Decode degrades worse than prefill** (3.3x vs 2.0x) despite the model being only
   ~2x the weights. Decode is memory-bandwidth-bound and 4.68 GiB streams from RAM with
   no cache reuse, while prefill still gets arithmetic intensity from batching. So
   output length is a first-class cost lever on the 8B: at 1.84 tok/s a 250-token
   summary is 136 s of pure decode, ~34% of a long article's total.
2. **A single long article costs 906 s typical, 1223 s worst.** Shard sizing must assume
   the worst case: 5 long articles in one shard is ~75 min, still inside the 6 h cap,
   but shard timeout must be set from this number and not from the blended figure.
3. **Truncation is worth more on the 8B than the 4B.** Capping at 2500 instead of 6000
   tokens takes a long article from ~906 s to ~450 s, cutting the blended figure from
   399 s to ~308 s. Row 6 decision 6's sweep is now the highest-leverage tuning knob in
   the plan.
4. The projection of "~2x the 4B" was 12% optimistic (399 s actual vs ~350 s projected).
   Better than the 3.1x miss on the pre-measurement estimate, but still a reminder that
   scaling factors are measured, not reasoned.

---

## Row #3 - Source discovery, fetch and extract

- **Scope:** Turn the configured vertical feed lists into a ranked, deduplicated URL list, then turn one URL into a validated `article` payload - or a recorded failure - without ever failing its sibling workers.
- **Files touched:** `backend/idhazh/discover.py`, `backend/idhazh/rank.py`, `backend/idhazh/fetch.py`, `backend/idhazh/extract.py`, `config/sources.json`, `config/taxonomy.json`, `config/watchlist.json`, `backend/tests/test_discover.py`, `backend/tests/test_rank.py`, `backend/tests/test_fetch.py`, `backend/tests/test_extract.py`, `tests/fixtures/feeds/*`, `tests/fixtures/pages/*`
- **Acceptance gates:** unit tests on local fixtures only (no network in tests); `robots.txt` honoured; 3 retries with exponential backoff; permanent 4xx recorded and skipped; oversized bodies truncated with `truncated: true`; a vertical below its `min_feeds` floor does not render; a dead feed quarantines instead of failing the run.
- **Oracle:** contract - every fixture feed set produces a ranked URL list that validates against `schemas/sources.schema.json`, and every fixture page produces a payload that validates against `schemas/article.schema.json`, including the failure cases.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Three config primitives, not one. `verticals` carry a curated feed list per desk; `lenses` are tags applied to items already fetched at zero extra request cost; `watchlist` is named entities with their own tier-1 feeds. A lens and an entity never get their own source list. | Fowler |
| 2 | Ranking is `tier_weight x cross-source repetition + watchlist hit + front-page boost` - deterministic, no model, computed in the plan job before any weights load. A story carried by three independent feeds is the day's story. | Carmack |
| 3 | Hacker News is a salience signal, not a source. `hnrss.org/frontpage` contributes rank to URLs already in the pool; it never discovers. HN has no topic taxonomy and its only tags are post types. | Fowler |
| 4 | Retire, never delete. A retired vertical, lens or entity keeps its config entry with `status: retired` and `retired_on`, because payloads written under it must still validate (section 11). | Fowler |
| 5 | `status: draft` plus a `min_feeds` floor of 25 lets a vertical be built in the open over weeks without rendering. Below the floor it is not published. Kagi News uses the same floor for the same reason. | Fowler |
| 6 | Feed health is recorded, not configured. N consecutive failures auto-quarantines a feed and degrades its vertical; the run never fails on a dead source. Closes open question 4 at the source stage. | Carmack |
| 7 | Soft retirement before hard: drop a source's `weight`, observe, then set `status: retired`. Reversible in one field. | Fowler |
| 8 | `trafilatura` for boilerplate removal; no custom HTML parsing. | Fowler |
| 9 | Truncate at the configured token cap and set `truncated: true`; never silently drop text. | Fowler |
| 10 | Sanitize before the model sees it: strip zero-width and control characters, HTML comments, base64 blobs. A feed title is data, never instruction (Holy Law #11). | Carmack |
| 11 | Source failure reuses yesterday's URL list marked `stale: true`; never skip a day silently. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | HN as the single source | One global front page, no topic taxonomy, and keyword feeds (`hnrss.org/newest?q=...&points=N`) are lexical - `q=AI` catches everything, `q=model` catches modelling. HN cannot carry world, energy or India at all. | Fowler |
| 2 | A classifier sorting one firehose into verticals | Nobody who solved this does it that way; every shipping multi-vertical digest attaches a curated source list per vertical and treats classification as the fallback. A classifier also costs model time in the plan job, which today loads no weights. | Andre |
| 3 | One vertical per interest (11 of them) | 11 x 25 feeds is 275 feeds to curate, and 11 x 3 items breaks the 20/day ruling. Most of the 11 are not desks: "AI ROI" has no outlet section anywhere, "China" appears inside four verticals, "markets" is an instrument. | Fowler |
| 4 | Stock markets as a daily vertical | A once-a-day statically-committed digest is the wrong instrument for prices - the number is stale before the reader opens it, and they have a broker app. Kept as a lens so a rate decision or a mega-deal still surfaces. | Reader |
| 5 | Splitting AI models from AI ecosystem | The same feed list serves both, so the split doubles curation to buy one taxonomy line. The separation is recovered for free by the `release` event type. | Fowler |
| 6 | A single `model-release` tag | Too coarse for what a reader actually tracks. Replaced by a closed nine-value event enum so "who signed what with whom" is first-class. | Reader |
| 7 | Deleting a retired vertical from config | Deleting an id breaks every payload written under it and forces a read-side migration. A tombstone costs one JSON object. | Fowler |
| 8 | Readability-style custom extractor | Mature OSS exists; a custom extractor is a maintenance surface with no beneficiary feature. | Fowler |
| 9 | Store full article bodies in the repo | Copyright; store the link and our own summary. | Fowler |

### 3.1 Ratified taxonomy (2026-08-20)

**Verticals** - each carries its own feed list, a daily cap, and a lifecycle status:

| id | display_name | daily cap | absorbs |
| --- | --- | --- | --- |
| `ai` | AI | 5 | AI models, AI ecosystem |
| `energy` | Energy | 3 | nuclear, fusion, generators, wind, solar |
| `business-economy` | Business and Economy | 3 | world business, macro economics |
| `world` | World | 3 | world politics, geopolitics |
| `india` | India | 3 | India top news |

17 items/day, inside the section 0.2 ruling of 20.

**Lenses** - tags on items already fetched, zero extra requests: `china`, `ai-roi`, `markets`, `cyber`.

**Events** - closed enum, one or more per item: `release`, `deal`, `acquisition`, `funding`, `capex`, `earnings`, `regulation`, `research`, `incident`.

**Watchlist** - capped at ~30 entities, each with tier-1 feeds. US filers additionally resolve through EDGAR: `data.sec.gov/submissions/CIK##########.json`, no key and no authentication, sub-second dissemination delay, 10 requests/second, and a declared `User-Agent` carrying a contact email is mandatory. Seed ticker -> CIK from `company_tickers.json` rather than hand-writing CIKs. A material contract lands as an 8-K Item 1.01. Non-US entities (TSMC, Samsung, SK Hynix, OpenAI, Anthropic, Mistral, DeepSeek) are newsroom-feed only - EDGAR does not cover them, so the watchlist needs both layers.

**Sources are tiered**, and the tier is the ranking weight: tier 1 is the institution that *is* the fact (lab blog, central bank, IEA, ACLED, an SEC filing, a company newsroom); tier 2 is trade press; tier 3 is community and aggregators.

One story indexes many ways. An Nvidia supply agreement is verticals `ai` + `energy` + `business-economy`, lenses `ai-roi` + `markets`, events `deal` + `capex`, entity `nvidia`: six index entries, one fetch, one summary. That is the whole argument for lenses over verticals.

### 3.2 Ratified `ai` feed list (owner sign-off 2026-08-21)

36 feeds against a floor of 25, **written to `config/sources.json`**. Up to eleven may fail verification and the vertical still renders.

**Every choice here is reversible in one field, which is why sign-off is low-stakes.** Adding a feed is a one-object append. Removing one is decision 7's soft path - drop `weight` to 0, observe a week, then set `status: retired` with `retired_on`, which keeps the id alive so payloads written under it still validate (decision 4). The vertical stays `status: draft` and renders nothing until it clears its floor, so a wrong list costs nothing a reader can see.

**Tier 1 - the institution that IS the fact (23)**

| id | title | url |
| --- | --- | --- |
| `openai-news` | OpenAI | `https://openai.com/news/rss.xml` |
| `anthropic-news` | Anthropic | `https://www.anthropic.com/news` |
| `deepmind-blog` | Google DeepMind | `https://deepmind.google/blog/rss.xml` |
| `google-research-blog` | Google Research | `https://research.google/blog/rss/` |
| `meta-ai-blog` | Meta AI | `https://ai.meta.com/blog/rss/` |
| `microsoft-research-blog` | Microsoft Research | `https://www.microsoft.com/en-us/research/feed/` |
| `nvidia-technical-blog` | NVIDIA Technical Blog | `https://developer.nvidia.com/blog/feed` |
| `nvidia-newsroom` | NVIDIA Newsroom | `https://nvidianews.nvidia.com/releases.xml` |
| `huggingface-blog` | Hugging Face | `https://huggingface.co/blog/feed.xml` |
| `mistral-news` | Mistral AI | `https://mistral.ai/news/rss.xml` |
| `cohere-blog` | Cohere | `https://cohere.com/blog/rss.xml` |
| `ai2-blog` | Allen Institute for AI | `https://allenai.org/blog/rss.xml` |
| `bair-blog` | Berkeley AI Research | `https://bair.berkeley.edu/blog/feed.xml` |
| `stanford-hai` | Stanford HAI | `https://hai.stanford.edu/news/rss.xml` |
| `mit-news-ai` | MIT News - AI | `https://news.mit.edu/rss/topic/artificial-intelligence2` |
| `apple-ml-research` | Apple Machine Learning Research | `https://machinelearning.apple.com/rss.xml` |
| `amazon-science` | Amazon Science | `https://www.amazon.science/index.rss` |
| `ibm-research-blog` | IBM Research | `https://research.ibm.com/blog/rss.xml` |
| `pytorch-blog` | PyTorch | `https://pytorch.org/blog/feed.xml` |
| `databricks-blog` | Databricks | `https://www.databricks.com/blog/feed` |
| `llama-cpp-releases` | llama.cpp releases | `https://github.com/ggml-org/llama.cpp/releases.atom` |
| `vllm-releases` | vLLM releases | `https://github.com/vllm-project/vllm/releases.atom` |
| `transformers-releases` | Transformers releases | `https://github.com/huggingface/transformers/releases.atom` |

**Tier 2 - trade press and named analysts (11)**

| id | title | url |
| --- | --- | --- |
| `ars-technica-ai` | Ars Technica - AI | `https://arstechnica.com/ai/feed/` |
| `techcrunch-ai` | TechCrunch - AI | `https://techcrunch.com/category/artificial-intelligence/feed/` |
| `venturebeat-ai` | VentureBeat - AI | `https://venturebeat.com/category/ai/feed/` |
| `the-verge-ai` | The Verge - AI | `https://www.theverge.com/rss/ai-artificial-intelligence/index.xml` |
| `mit-tech-review-ai` | MIT Technology Review - AI | `https://www.technologyreview.com/topic/artificial-intelligence/feed` |
| `ieee-spectrum-ai` | IEEE Spectrum - AI | `https://spectrum.ieee.org/feeds/topic/artificial-intelligence.rss` |
| `the-register-ai` | The Register - AI/ML | `https://www.theregister.com/software/ai_ml/headlines.atom` |
| `simon-willison` | Simon Willison | `https://simonwillison.net/atom/everything/` |
| `the-batch` | The Batch (DeepLearning.AI) | `https://www.deeplearning.ai/the-batch/feed/` |
| `import-ai` | Import AI | `https://importai.substack.com/feed` |
| `interconnects` | Interconnects | `https://www.interconnects.ai/feed` |

**Tier 3 - community (2)**

| id | title | url |
| --- | --- | --- |
| `localllama` | r/LocalLLaMA | `https://www.reddit.com/r/LocalLLaMA/.rss` |
| `lobsters-ai` | Lobsters - AI tag | `https://lobste.rs/t/ai.rss` |

**Honesty note (Holy Law #10 applied to a URL).** Not one of these 36 has been fetched - no test may touch the network, and the agent has not verified them out of band. Roughly a third use a well-known stable pattern (the GitHub `releases.atom` feeds, the major trade-press category feeds, `machinelearning.apple.com/rss.xml`); the rest are plausible-but-unconfirmed, and `anthropic-news` is a page rather than a known feed and will likely need replacing. **Row 3's first task is a `backend/utilities/check_feeds.py` run that reports which resolve, parse, and carry recent items** - the list is ratified in shape here and corrected in detail there. Decision 6's quarantine mechanism then handles rot after launch.

### 3.3 Verification, measured 2026-08-21 (first live runs)

The list was checked by running the real plan stage, which is a better check than a bespoke script: **26 of 36 feeds resolved on the first pass.** The ten that did not were retired, then five were recovered by finding the real feed URL - four by probing conventional paths, one by reading the site's own `<link rel="alternate">`. **31 live, 5 retired.**

| Feed | First guess | Outcome |
| --- | --- | --- |
| `mistral-news` | `/news/rss.xml` | fixed -> `https://mistral.ai/rss.xml` (81 entries) |
| `ai2-blog` | `/blog/rss.xml` | fixed -> `https://allenai.org/rss.xml` (25 entries) |
| `databricks-blog` | `/blog/feed` | fixed -> `https://www.databricks.com/blog/feed.xml` (10 entries) |
| `ibm-research-blog` | `/blog/rss.xml` | fixed -> `https://research.ibm.com/rss` (20 entries), found in the page's own feed link |
| `meta-ai-blog` | `ai.meta.com/blog/rss/` | **no feed exists.** `ai.meta.com` is a JS application and declares none. Repointed to `https://engineering.fb.com/feed/` and retitled "Meta Engineering" - the id is an immutable slug and the display title is not, which is exactly what that rule is for. |
| `the-batch` | `/the-batch/feed/` | **retired.** `deeplearning.ai` declares no feed on any conventional path. |
| `bair-blog` | `/blog/feed.xml` | **retired.** `robots.txt` unreadable, and an unreadable robots file is a refusal. |
| `the-register-ai`, `localllama`, `lobsters-ai` | - | **retired permanently.** `robots.txt` disallows the path. Not a bug to fix. |

**31 live against a floor of 25** is a real margin rather than the one-feed clearance the first pass left. Two of the five retirements are permanent by the host's own instruction, and two are absent feeds rather than wrong guesses.

Three design defects surfaced that no unit test would have caught, all now fixed:

- **The whole vertical planned from one blog.** On a day when no story is carried twice, every score is identical and the *tie-break* decides the running order - and an alphabetical tie-break silently hands the day to whichever host sorts first. Ties now break on recency, and `collect.max_per_source` caps how much of a vertical any one feed may take.
- **A GitHub `releases.atom` feed produced a git changelog, not an article.** It cleared the 120-word extraction floor and reached the model as commit messages, which summarized to "includes various updates and improvements" - perfectly faithful, and it says nothing. `extract.min_source_words` is now 250, which is well under the shortest real article bucket and well over a changelog stub.
- **Three of five summaries failed as "the reply did not hold its shape", and the shape was not the problem.** `max_output_tokens` was 250, which covers a summary but not a summary *plus* its key points, so the reply ran out of budget mid-object and never closed its JSON. The budget is now 500, and a reply that stops on `length` is reported as itself rather than as a schema error - a diagnostic that named the wrong cause is worse than no diagnostic.

**Excluded on purpose:**

- **arXiv category feeds** (`cs.AI`, `cs.CL`, `cs.LG`). Hundreds of items a day with no cross-source repetition, so they rank below the daily cap every day and surface nothing - while counting toward the 25-feed floor. Padding the floor with feeds that never publish an item defeats what the floor is for.
- **Hacker News.** Already in `config/sources.json` as a salience feed. Decision 3: it is a vote on a URL already in the pool, never a discovery source.
- **Anything paywalled or login-walled** (`CLAUDE.md` section 0a).

---

## Row #4 - Eval harness: HHEM dual-score + deterministic metrics

- **Scope:** Score every summary for faithfulness and for the failure modes faithfulness cannot see, and append one CSV row per article.
- **Files touched:** `backend/idhazh/evals/hhem.py`, `backend/idhazh/evals/metrics.py`, `backend/idhazh/evals/writer.py`, `evals/scores.csv`, `backend/tests/test_evals.py`, `tests/fixtures/golden/*`
- **Acceptance gates:** HHEM-2.1-Open runs CPU-only; golden set of 20 articles with hand-written references committed; CSV validates against `schemas/eval-row.schema.json`.
- **Oracle:** the truncation trap - for a deliberately truncated fixture, `hhem` (vs truncated source) scores high while `hhem_full` (vs full source) scores low, and the row is flagged. If this fixture does not trip the flag, the harness is blind and the row fails.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | HHEM scored twice: against the truncated source and against the full source. Delta > 0.10 is a truncation artifact. | Fowler |
| 2 | Counterweights to HHEM: `coverage` (named/numeric entity survival), `compression` (flag outside 0.03-0.20), `extractiveness` (LCS - high LCS plus high HHEM means copying, not summarizing). | Fowler |
| 3 | Human spot-check 10/week by seeded-random selection; monthly correlation of HHEM against human ratings re-tunes the bands. | Fowler |
| 4 | Bands: `>= 0.80` high, `0.50-0.80` medium, `< 0.50` low. Below 0.50 retries on Qwen3-4B, then publishes with a visible low-confidence marker. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | LLM-as-judge with a 4B model | Circular and unreliable; the judge shares the failure modes of the thing judged. | Fowler |
| 2 | HHEM alone | Scores consistency, not informativeness. "This article discusses technology" scores ~1.0. It rewards verbatim extraction, so alone it drives the system toward bland copying. | Fowler |
| 3 | 3 spot-checks per week | ~2% sampling cannot detect a 5% defect rate inside a month. | Fowler |
| 4 | Summarize twice and compare (any variant) | At `temperature=0, seed=0` a second identical pass is a no-op by construction. Sampling at temp>0 measures stability, not correctness. Two prompts doubles cost with no evidence of prompt fragility. Summarize-then-verify is LLM-as-judge with extra steps. Cross-model (8B vs 4B) disagreement is the only variant with real signal - it proxies selective omission - but `coverage` targets that blind spot directly at ~0 cost, so disagreement is a more expensive route to something already measured. Spend the compute on row 12 instead. | Fowler |
| 5 | Best-of-N with HHEM as the selector | Goodharting, and structurally worse than it looks: HHEM is the *regression detector*. Optimizing against it at inference time destroys its value as a monitor. A metric cannot be both the selector and the alarm. | Fowler |

### 4.1 Andre consult (2026-08-21) - the row as written was wrong in five places

Required by the section 0 roster note. Andre owns eval design and metric choice; the verdicts below supersede the Fowler attributions above where they conflict.

| Item | Verdict | Reason |
| --- | --- | --- |
| HHEM-2.1-Open | KEEP | Right instrument class - a purpose-built cross-encoder satisfies the LLM-as-judge ban directly rather than by argument. Two conditions: pin `trust_remote_code` to an immutable revision and verify the weight digest (it is remote code execution on the build machine otherwise), and derive `scorer_version` rather than typing it. |
| Dual scoring | KEEP | The best decision in the row. But `hhem_full` on a long article needs chunking, and it must aggregate **max-over-chunks, never mean** - a mean drives the score down as the article lengthens, which manufactures a large delta on exactly the longest articles and inverts the flag. |
| The 0.10 delta threshold | DEFER | Arbitrary, and there is no honest way to calibrate it before real rows exist (an untruncated article gives delta exactly 0, so there is no noise floor to measure). Record the raw delta; branch on nothing until ~200 rows. |
| 20 hand-written reference summaries | **DELETE** | No oracle in rows 4, 6, 7 or 12 reads a reference - HHEM and every counterweight are reference-free. The most expensive line item in the row, and no code would have consumed it. |
| Retry on Qwen3-4B | **DELETE** | The 4B carries the worse base hallucination rate (5.7% vs 4.8%, row 6's own table). Worse, a retry writes two rows for one article across two models, which corrupts the ledger's one honest question and would make row 12 alarm on its own retry policy. Publish marked. The retry lever becomes a row 7 experiment; the cheapest candidate is `max_output_tokens` 250 -> 120 on the same model. |
| `coverage` as entity survival | **REPLACE** | Lands near the same low value for a good summary and a bad one - a constant column that looks like a measurement. Replaced by lead-anchored recall. |
| `compression` 0.03-0.20 band | **DELETE the flag, keep the column** | A length detector: at a fixed output budget it fires on roughly a quarter of the corpus for reasons that are purely article length. Replaced by absolute summary-word bounds. |
| LCS extractiveness | **REPLACE** | Subsequence matching permits gaps, so function words match in order almost anywhere. Replaced by 4-gram precision plus the longest unbroken run. |
| `unsupported_numbers` | **ADD** | A wrong number is the most damaging defect a news summary can carry, and every metric previously specified is blind to it - they see omission, never invention. |
| `hedge_dropped` | **ADD** | A rumour asserted as fact. HHEM scores it generously because the entity and the relation both survive; only the uncertainty went missing. |
| `source_seen_word_count` | **ADD** | Otherwise `compression` silently means two different things depending on whether the item was truncated. |
| Spot-check sampler | **CHANGE to stratified** | Seeded-random over all items spends most checks on the band nobody is worried about, and can go a month without labelling a single low-band item. |
| Bands 0.80 / 0.50 | KEEP, mark provisional | 0.50 has provenance (HHEM's own decision boundary); 0.80 is taste. Re-tune against the human-judged defect rate in the high band, not the score histogram - and not before ~120 labels, because 40 cannot estimate a 5% rate. |

**Open question 3 is split by this consult.** Per-item extraction floors belong to row 4 - `min_source_words` (below it the item is not summarized at all) and a cross-page boilerplate ratio feeding `extraction_suspect`. The trend alerts belong to row 12 and must be **per-domain against that domain's own trailing median**: a global 10% month-over-month mean cannot fire for weeks when a single site breaks. The alert that names the failure directly is a domain's faithfulness staying flat or rising *while* its median source word count falls sharply.

### 4.2 Owner rulings (2026-08-21)

1. **Article bodies are never committed to the repo. Only summaries, and the source link for citation.** Absolute. This kills the row's original acceptance gate ("20 articles committed to `tests/fixtures/golden/`") and also kills Andre's redistributable-corpus workaround.
2. **No content digests, no fixed-set fingerprints.** The URL is already unique and is the reference. Andre's URL-plus-content-digest golden corpus is dropped.
3. **Sampled evaluation was proposed and withdrawn** after Andre's REJECT (see 4.3). The ledger is a census over items whose inputs changed.

### 4.3 Why the eval is a census (2026-08-21)

The owner proposed scoring on a ~3-day interval, sampled from one or two copyright-safe sources. Andre returned REJECT. The reasoning now lives in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) under "Why this is a census and not a sample"; the three load-bearing points:

- **A per-item claim to a reader cannot be backed by a sample.** Every item carries a confidence signal; if most items are unscored, the only options are to render "not measured" as "fine", caveat the whole page, or delete the signal.
- **Sampling by source is the one axis guaranteed to bias the result**, and it disarms specific instruments - `hedge_dropped` would report 0 forever on institutional prose, and extraction rot concentrates on exactly the messy sources a clean-source sample never fetches.
- **Copyright does not constrain scoring at all.** Scoring runs in-process on text already in memory and publishes nothing; the pipeline already performs the strictly more aggressive act of generating a published derivative. The constraint applies only to committed bytes, which ruling 1 already forbids.

The economics are settled by measurement rather than preference: the model-free counterweights are a rounding error, and if the faithfulness scorer's measured share of per-item wall-clock exceeds a stated fraction of the budget, **it alone** is sampled - stratified across source tiers, within every day, deterministically selected, recorded as a field on a written row and never as an absent one.

### 4.4 Landed 2026-08-21

- `EvalRow` gains `unsupported_numbers`, `hedge_dropped`, `extraction_suspect`, `verbatim_run`, `source_seen_word_count`; `coverage` and `extractiveness` are redefined; `scorer_version` is derived. Taken now because the ledger has never been written, so it cost one changelog entry rather than a read-side migration.
- `AppConfig` drops `evaluation.compression_min/max` for `summary_words_min/max`, and gains `extract.min_source_words` and `extract.boilerplate_ratio_max`.
- `backend/idhazh/evals/metrics.py` implements every model-free counterweight, with tests written against the defect each one exists to catch and a counter-test that a metric separating nothing fails.
- **One recorded deviation from the consult:** entity detection is a capitalisation rule over the document rather than spaCy. Andre preferred the mature library; the dependency (a package plus a model download on every CI run) was judged not to pay for itself for one signal while the metric is unproven. The rule self-calibrates - a single capitalised word opening a sentence counts only if the same token appears mid-sentence somewhere - and swapping in spaCy is a one-function change behind the same signature. Revisit if lead coverage proves noisy against real articles.
- Still pending in this row: `hhem.py` (pinned revision, chunked, max-over-chunks), the HHEM timing measurement, `writer.py` plus `evals/scores.csv`, the stratified spot-check sampler, and the fixture corpus under rulings 1 and 2.

---

## Row #5 - Injection canary fixtures + CI assertion

- **Scope:** Five planted articles carrying known attacks, asserted in CI on every prompt or model change.
- **Files touched:** `tests/fixtures/canaries/*.json`, `backend/tests/test_canaries.py`, `.github/workflows/ci.yml`
- **Acceptance gates:** five distinct attacks covered - direct instruction override, fake system delimiter, encoded payload, tool-call injection, exfiltration-via-URL; the suite runs on every PR.
- **Oracle:** all five canaries fail to inject. A single success fails the build.

**Landed 2026-08-21.** The canonical page is [`docs/architecture/sources/trust-boundary.md`](../docs/architecture/sources/trust-boundary.md). One deviation from the file list, deliberate: the sanitizer landed here as `backend/idhazh/sanitize.py` rather than inside row 3's `extract.py`. Decision 4 requires the canaries to assert a live control, and a control buried in a stage that does not exist yet cannot be asserted; row 3's extractor imports it rather than owning it. `SANITIZER_VERSION` is also a row 15 fingerprint input, so it needed a home either way.

One finding worth carrying forward to row 6: **stripping the zero-width layer reveals the hidden instruction rather than removing it.** Nothing removes an imperative written in ordinary prose, and nothing should - the fence and the pinned output shape are what make it inert. The canaries assert both directions, so a sanitizer that started deleting article prose to look safer would fail.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Article text never enters the system prompt; it is delimited and labelled untrusted data. | Carmack |
| 2 | Output shape pinned by JSON schema, so an injection cannot change the shape even if it changes content. | Carmack |
| 3 | Model output never becomes a shell argument, file path, or URL to fetch. | Carmack |
| 4 | The canary suite lands before the summarizer (row 6), not after, so the summarizer is written against a live assertion. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Rely on the system prompt telling the model to ignore instructions | A prompt is a request, not a control. The schema and the sanitizer are the control. | Carmack |
| 2 | Add canaries after the pipeline works | Reader-before-writer: the assertion must exist before the surface it guards. | Fowler |

---

## Row #6 - Summarize worker

- **Scope:** Turn one `article` payload into one schema-valid `summary` payload, deterministically.
- **Files touched:** `backend/idhazh/summarize.py`, `backend/idhazh/llm/server.py`, `backend/idhazh/prompts/summarize.txt`, `backend/idhazh/prompts/summarize.schema.json`, `backend/tests/test_summarize.py`
- **Acceptance gates:** `temperature=0`, `top_p=1.0`, `seed=0`; thinking disabled and the empty `<think></think>` block asserted in output; `response_format: json_schema` enforced; ctx 8192 with the token budget asserted; row 5 canaries green.
- **Oracle:** determinism - the golden set re-run at seed 0 produces identical `summary` and `key_points` strings. Not byte-identical JSON (dict ordering and float formatting make that brittle for reasons unrelated to the model).

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Qwen3-8B-Q4_K_M (4.68 GiB on disk, Apache-2.0) - 4.8% hallucination, 99.9% answer rate on HHEM. | Carmack |
| 2 | Thinking OFF. Reasoning models measurably hallucinate more when summarizing (R1 11.3% vs V3 6.1%; o3-pro 23.3%). Summarization is compression; each reasoning token is a chance to leave the source. | Carmack |
| 3 | Assert the `<think>` block is empty rather than trusting the flag took. | Carmack |
| 4 | 8B-first, 4B on retry - **CONFIRMED by section 2.2**. The 8B costs 2.3x the 4B (399 s vs 173 s blended) for 0.9pp better faithfulness, and 20 URLs still lands at 133 min serial / 33 min at 4-wide, using 2.22 h of a 6 h cap. Quality is the product and the headroom exists. Flip to 4B-first only if row 7 shows the faithfulness gap does not survive our own prompt and extraction. | Carmack |
| 5 | `llama-server` prebuilt binary, OpenAI-compatible endpoint - so the transport survives a later move to hosted inference. | Fowler |
| 6 | The truncation cap is a first-class performance lever, not only a safety cap. Section 2.1 shows prefill degrades with context length, so halving the cap more than halves long-article cost. Sweep the cap at 6000 / 4000 / 2500 tokens and read the quality cost off the row 4 `hhem` vs `hhem_full` delta. Pick the knee, do not assume 6000. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | LFM2.5-8B-A1B | Picked originally on AA-Omniscience, which measures closed-book knowledge hallucination, not summarization faithfulness. Absent from HHEM entirely, and reasoning-tuned. | Carmack |
| 2 | Granite-4.0-H-Tiny | Right MoE shape for CPU, 6.4% hallucination. The architecture argument was correct and irrelevant. | Carmack |
| 3 | gemma-3-4b-it | 6.4% looks acceptable until you see the 67.3% answer rate - it silently declines a third of documents. A model that refuses is a stage that fails quietly. | Carmack |
| 4 | Qwen3.5 / GLM / Kimi / DeepSeek | Newer is worse here (qwen3.5-27b 12.1% vs qwen3-4b 5.7%); the rest are 600B+ or trillion-scale and score 9.3-17.9% regardless. | Carmack |
| 5 | `pip install llama-cpp-python` | Compiles from source and costs minutes per run; the prebuilt binary is a download. | Carmack |
| 6 | Gemma-4-26B-A4B (5.2%, MoE) | ~14 GB at Q4 busts the 10 GB cache, forcing a full re-download every run. | Carmack |

**Landed 2026-08-21.** One deviation from the file list, deliberate: there is no committed `prompts/summarize.schema.json`. The constrained-decoding schema is generated from a `SummaryDraft` Pydantic model, because hand-writing it would mean the decoder's constraint and the validator that reads the reply could disagree, and Holy Law #3 forbids hand-writing a schema anyway. Its digest is still a fingerprint input; the serialization is the same canonical one every payload uses, so the stamp is stable.

The tests are all about the failure paths, because a summarizer that handles a good reply is easy and a summarizer that cannot be talked out of its shape is the product: a planted tool call cannot reach a payload, a model that obeyed an injection produces no summary rather than a wrong one, a model that reasoned despite the flag is a recorded failure rather than a curiosity, and a reply outside the publishable word range is refused. The model boundary is driven by recorded llama-server envelopes under `tests/fixtures/completions/` (CLAUDE.md section 13); nothing is mocked and no test runs a model.

**The row's own oracle - the golden set re-run at seed 0 producing identical strings - cannot run here**, because it needs the real weights on a real runner. It folds into row 7, which already stands up the full pipeline against candidate models. Row 15's stamp is what makes that check meaningful when it happens: without it, "identical output" would be a claim about the sampler rather than about the pipeline.

---

## Row #7 - Model validation gate (ESCALATE)

- **Scope:** Confirm the row 6 model pick survives contact with our own prompt and our own extraction, or re-derive it.
- **Files touched:** `docs/reference/measurements.md`, `config/idhazh.json`, `evals/validation-<date>.csv`
- **Acceptance gates:** 20 golden articles scored end-to-end through the real pipeline; results recorded with date and commit SHA.
- **Oracle:** decision rule - if mean HHEM is more than 0.10 below what the leaderboard rank predicts, re-score the other candidates; if any scores >= 0.05 better than Qwen3-8B on our pipeline, switch the pick and re-golden. PAUSE for sign-off before switching.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The leaderboard ranking is a better prior, not evidence. Trusting it unvalidated is the same class of error that produced the LFM2.5 mistake, just better-matched. | Fowler |
| 2 | The rule carries a number. "Materially diverges" is an argument waiting to happen. | Fowler |
| 3 | This row is the ESCALATE point: a model swap changes a persisted contract and pauses for the user. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Ship on the leaderboard number | Their prompt, their extraction, their corpus. Three variables between that number and ours. | Fowler |

---

## Row #8 - Route worker + deterministic renderers

- **Scope:** Classify each summary into `chart | diagram | image | none` and render the two deterministic kinds.
- **Files touched:** `backend/idhazh/route.py`, `backend/idhazh/render/chart.py`, `backend/idhazh/render/diagram.py`, `backend/idhazh/prompts/route.schema.json`, `backend/tests/test_route.py`, `backend/tests/test_render.py`
- **Acceptance gates:** route output schema-pinned to the four-way enum; Vega-Lite spec validates before render; `vl-convert` and Mermaid render headless; render failures degrade to `none`, never to a failed article.
- **Oracle:** contract - every routed `chart` produces a Vega-Lite spec whose data values are a subset of the numbers present in the source article. A number in the chart that is not in the article fails the row.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Numbers -> Vega-Lite spec; process -> Mermaid/DOT. Deterministic, diffable, and the numbers are correct. | Jony |
| 2 | Routing runs on Qwen3-4B, not the 8B. Classification is the easy task; the big model belongs on summarization. | Carmack |
| 3 | A render failure degrades the article to `visual: none`; never fail a digest for a picture. | Jony |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Diffusion for charts | Produces a beautiful picture of a chart with hallucinated axis labels. | Jony |
| 2 | A charting library in the renderer | `vl-convert` takes a spec to PNG/SVG with no browser and no runtime JS. | Carmack |

---

## Row #9 - Image model selection + renderer

- **Scope:** Choose the CPU diffusion model on measured cost, then render narrative-routed items behind the canary gate.
- **Files touched:** `backend/idhazh/render/image.py`, `config/idhazh.json`, `docs/reference/measurements.md`, `backend/tests/test_image_prompt.py`
- **Acceptance gates:** Z-Image-Turbo and Anima-2.9B both timed at 512 and 768 on 4 threads; chosen model recorded with its seconds-per-image; image-prompt allowlist enforced; row 5 canaries re-run against the chosen model.
- **Oracle:** all five canaries fail to inject through the image-prompt hop. No model ships without this passing.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Selection is a measurement, not a preference. Anima-2.9B is roughly half the size, which on CPU matters more than its newness counts against it. | Carmack |
| 2 | The image-prompt hop is the highest-risk boundary in the system - a stranger's web page becoming a generation prompt. Defence is gated on choosing the model, because the prompt surface differs per model. | Carmack |
| 3 | Turbo variants run `guidance_scale=0`; they are distilled and CFG degrades them. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Gemma for image generation | Gemma 4 emits text only. Google ships no open text-to-image model (HF query returned empty). The `any-to-any` HF tag reflects multimodal input and is misleading. | Carmack |
| 2 | FLUX.1-dev | 12B and a non-commercial licence. | Carmack |
| 3 | Skipping images entirely | Narrative articles are the one case the deterministic renderers cannot serve. | Jony |

---

## Row #10 - Pipeline orchestrator workflow

- **Scope:** Wire plan -> sharded worker matrix -> assemble into one daily workflow with contained failures.
- **Files touched:** `.github/workflows/daily.yml`, `backend/idhazh/plan.py`, `backend/idhazh/shard.py`, `backend/idhazh/assemble.py`, `backend/tests/test_assemble.py`, `backend/tests/test_shard.py`
- **Acceptance gates:** `fail-fast: false`; `max-parallel: 4` pending row 2 contention data; shard size from `config/idhazh.json`; per-shard artifacts merged with `merge-multiple: true`; atomic `.tmp` + `os.replace()` writes; skip-if-hash-matches so re-run-failed costs only unfinished URLs; `assemble` runs `if: always()`.
- **Oracle:** containment - kill one shard worker mid-run; the digest still ships, the URLs that shard had already written survive, the unfinished ones are re-done on re-run, the digest carries the `Partial run: N of M` header, and the failure count lands in the CSV as a run-level row.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Each matrix job is its own VM with its own 4 vCPUs - `threads: 4` and `max-parallel: 4` are 4 machines, not 16 threads on one box. Stated at the YAML because a careful reviewer misread it. | Carmack |
| 2 | The digest always commits, even at zero successes; the failure count is a tracked time series, not something noticed when a human complains. | Fowler |
| 3 | `fail-fast: false` - the default cancels every sibling on first failure, which is exactly wrong for independent work items. | Carmack |
| 4 | `max-parallel` starts at 4 and rises only on row 2 evidence. The risk is cache-restore stampede and HF rate limits, not CPU. | Carmack |
| 5 | Below 70% success additionally opens an issue. | Fowler |
| 6 | **Shard, do not fan out per URL.** Section 2.1 measured ~90 s of model cache-restore per job against ~173 s of work, so one-VM-per-URL spent ~50% of wall-clock loading weights. Each worker job takes a shard and loads the model once. Per-item atomicity is preserved *inside* the shard by a temp-then-rename write plus skip-if-fingerprint-matches, so a re-run redoes only the unfinished items of a failed shard. This is the row-2 measurement changing the architecture, which is what row 2 is for. | Carmack |
| 7 | `timeout-minutes` on the shard job is set from the WORST case, not the blended figure. Section 2.2 measures a long article at 1223 s worst on the 8B, so a 5-URL shard that draws five long articles is ~102 min. Set 150 min. A timeout set from the 399 s blended figure would kill healthy shards that happened to draw long articles. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | LangGraph or similar in-process DAG | Actions already is the DAG - `needs:`, `matrix`, artifacts, retries, re-run-failed, rendered graph. Running one inside a job gives two orchestrators where the outer owns retries regardless. Revisit only for cycles, dynamic replanning, or resumable mid-run state. | Fowler |
| 2 | One job processing all URLs serially | A failure at URL 37 costs the first 36. | Fowler |
| 3 | Committing per URL | Forty commits a day for one logical unit of work. | Fowler |

---

## Row #11 - Pages eval dashboard

- **Scope:** Render the eval CSV as stacked high/medium/low bars per model per day on GitHub Pages.
- **Files touched:** `frontend/` (the dashboard surface), `.github/workflows/pages.yml`. The ledger stays at `evals/scores.csv` per CLAUDE.md section 3; the Vite build copies it into `dist/` at build time. It is never committed twice - retention treats the ledger and its published copy oppositely, so there must be exactly one ledger path.
- **Acceptance gates:** static bundle only; no runtime fetch beyond the same-origin CSV; renders with the CSV absent; zero console errors.
- **Oracle:** parity - the rendered band counts equal a direct `group by band` over the CSV.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Plain `fetch` plus hand-written SVG. A chart library would outweigh the data it draws. | Jony |
| 2 | The dashboard reads the committed CSV; it never recomputes scores. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Chart.js / D3 | Kilobytes of dependency for a stacked bar chart over a few hundred rows. | Jony |

---

## Row #12 - Drift benchmark: weekly golden re-run + quarterly refresh

- **Scope:** Detect system-level drift that per-article evals cannot see, on a schedule.
- **Files touched:** `.github/workflows/drift.yml`, `backend/idhazh/drift.py`, `evals/drift.csv`, `backend/tests/test_drift.py`
- **Acceptance gates:** weekly cron re-runs the 20-article golden set through the live pipeline and appends a dated row; alerts on >10% month-over-month or >5% year-over-year movement in mean HHEM, coverage or extractiveness; re-baselines on demand after any model, prompt or `llama.cpp` version change.
- **Oracle:** injected drift - replay the golden set against a deliberately degraded prompt; the alert must fire. A drift detector that never fires has not been shown to work.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Weekly cadence on a fixed 20-article set; ~15 min of runner time. This is the cheapest instrument in the plan and the only one that sees the system rather than the article. | Fowler |
| 2 | Version-stamp every drift row with the `llama.cpp` build, model file SHA-256 and HHEM version. A seed-0 output can change because the runtime changed, not the model. | Carmack |
| 3 | Refresh 50% of the golden set quarterly with articles published since the last refresh, and re-baseline. A frozen golden set stops representing the live corpus. | Fowler |
| 4 | Quarterly, correlate drift-benchmark movement against the weekly human spot-checks. If HHEM trends down while humans trend up, HHEM is the thing that broke. | Fowler |
| 5 | Alert thresholds cover `word_count` and `extractiveness` explicitly - these are the signature of extraction silently breaking on a site redesign (open question 4). | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Re-run the golden set on every daily run | ~58 min/day of runner time to detect something that moves on a scale of weeks. | Carmack |
| 2 | Rely on per-article evals alone | They measure variance within a day. Drift is a trend across months and is invisible in single-article scores. | Fowler |
| 3 | A frozen golden set held forever | The corpus evolves; a 2026 golden set stops representing 2027 news and the benchmark quietly becomes a museum. | Fowler |

---

## Row #13 - Published layout, date routing and the frontend shell

- **Scope:** Fix the committed layout the pipeline writes and the routes a reader walks, as two separate contracts, and stand up the static shell that renders them.
- **Files touched:** `backend/idhazh/publish.py`, `backend/idhazh/contracts/digest_day.py`, `schemas/digest-day.schema.json`, `frontend/` (Svelte shell, routes, prerender), `frontend/public/digest/**`, `backend/tests/test_publish.py`
- **Acceptance gates:** one `digest.json` per published day; a page renders in at most 2 requests regardless of archive age; `/` is a committed file, not a redirect; every dated route resolves or lands in the designed missing state; positions frozen across a re-run; browser smoke per section 12.
- **Oracle:** monotonicity - publish a day, record the rendered order, run the pipeline again with two extra items, and re-render. Every item present in the first render occupies the same position in the second, and the new items appear after them. A single reordered item fails the row.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Route paths and data paths are two separate contracts.** Data is segmented `frontend/public/digest/<YYYY>/<MM>/<DD>/`; the reader's route is a single `<YYYY-MM-DD>` segment. Coupling them means a URL-aesthetics change rewrites committed payloads. | Fowler |
| 2 | Data is segmented by year/month/day because a flat directory of 31,025 items is a 1.40 MB tree object rewritten on every commit; segmented, a daily commit rewrites ~3 KB of trees. **466x less tree churn**, and `digest/2026/07/**` becomes a single prune glob. | Carmack |
| 3 | `/` is a **real committed file rendering the newest day inline**. Not a redirect, not a client-side lookup. A redirect costs a round trip on the site's most-visited URL and blanks the first paint. | Jony |
| 4 | `latest` and `archive` are **derived at build time** from the directory listing and never committed. A committed pointer can disagree with disk after a prune or a raced deploy; a derived one cannot. | Fowler |
| 5 | **One `digest.json` per day carrying all items.** The vertical route is a filter over that same payload, never a second file. The day gzips to 12.8 KB (measured 2.92x ratio). | Carmack |
| 6 | **Requests to render any page is a constant, at most 2, independent of archive age.** Any scheme whose request count or index size grows with history is vetoed at any granularity. | Carmack |
| 7 | **The published order is global, deterministic and identical for every reader, and read-state may never influence it.** Corrected 2026-08-21: the earlier "read items never move" rule was unimplementable, because there is one payload and read-state is per-device - honouring it would require rendering a different page per person. An item is never removed or demoted because someone read it; one reader having read it says nothing about everyone who has not. Ranking is a pure function of the ranking inputs. | Reader, Fowler |
| 8 | **A revision is visible or it does not happen.** If a later run changes an item's summary text, that item carries an `updated_at` and says so. Silently swapping better wording under a reader who already read it makes them doubt their own memory, and the summaries are the entire product. | Reader |
| 9 | When a day has more than one run, the page carries one plain line - "5 stories added since this morning" - and the new items are findable without re-skimming the old ones. | Reader |
| 10 | **No run identifier and no hash in any data path or any reader URL.** An item is addressed by its vertical and its ordinal within the day - `ai-03` - which is predictable, derivable, free of fetched text, and readable aloud. The run id lives in the footer and in `run.json`. | Fowler, Jony |
| 11 | A topic is **a filter on the day**, with a shareable dated URL - not a destination a reader must choose before being given anything. The default interaction is an in-page anchor; the section heading is the permalink. | Reader |
| 12 | No title-derived slug in any URL. Titles come from fetched text, and fetched text never becomes a URL (Holy Law #11). | Jony |
| 13 | **Stack: Svelte 5 + Vite + TypeScript + Tailwind + vitest + Playwright + `json-schema-to-typescript`.** Matches both sibling repos' spine and yen-tamizh's lean profile. | Fowler, Jony, Carmack |
| 14 | **`ajv` is a CI dependency, not a shipped one.** It validates config and published payloads against the generated JSON Schema in the drift gate, where a failure is loud and early. Shipping it would cost every reader ~30 KB of JavaScript to re-check payloads Pydantic already validated on the way out. `zod` is rejected outright: it would need a second generator feeding the same gate. | Fowler |
| 15 | **Published filenames are predictable and derivable from the date.** `digest.json` is the day's current state; each run additionally writes `run-<N>.json` where N is the run sequence for that date. No content hash in the name, no unguessable suffix - a public repo with a public index makes secrecy theatre, and predictability is what makes a path reachable without a lookup. | Fowler, Carmack |
| 16 | **A vertical gets an undated entry route that renders inline and canonicalises to the dated one.** `/world/` shows the newest day's world projection with the date in the heading and `rel=canonical` pointing at `/<YYYY-MM-DD>/world/`; every share affordance on it emits the dated address. A door, not a bookmark. | Jony |
| 17 | Item counts per vertical are **config-driven throughout**. The 17/day figure is today's default, not a constant; no code, route, layout or budget may assume a fixed number of items or runs. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A `/latest/` route | Two moving pointers. A reader bookmarks one and shares the other, and they disagree about which is canonical. `/` already is latest. | Jony |
| 2 | A redirect or meta-refresh at `/` | A blank first paint and a wasted round trip on the connection the reader actually has. | Jony |
| 3 | A committed `latest.json` or `days.json` | Derived data committed as fact. It is exactly the file that goes stale after a prune, and deleting it is what makes retention a one-step operation. | Fowler |
| 4 | One file per item | 17 requests per day-page and 6,205 files/yr instead of 365. gzip over a 2.2 KB body never warms its dictionary; over the 37 KB day file it gets the measured 2.92x. It also buys nothing - an item view needs bytes the day payload already carries. | Carmack |
| 5 | One file per vertical per day | 1,825 files/yr and two sources for one fact, to avoid a client-side filter on a 12.8 KB object. Revisit only if a day file crosses ~250 KB gz, a 20x item increase. | Carmack |
| 6 | A global index of every item ever | 1.49 MB gzipped at year 5, fetched on every page load, growing without bound. | Carmack |
| 7 | Re-ranking a day on a later run | The single most disorienting thing the system could do. A reader who read at 07:00 and returns at 18:00 must never find their memory contradicted. Correct by every internal rule and still feels like the page is gaslighting them. | Reader |
| 8 | A dated page as the canonical page with `/` as a pointer to it | The predicted failure: `/` lags a day, or a bookmark to `/` turns out to have been dated all along. The reader sees healthy-looking stale news, concludes the site is dead, and never reports it. | Reader |
| 9 | DuckDB-WASM, d3, topojson | A multi-megabyte WASM runtime to query a 12.8 KB object; a chart library that outweighs the data it draws; a map projection with no map. No named beneficiary. | Carmack |
| 10 | `transformers.js` | Runtime inference. Holy Law #1 and section 0a forbid it outright. | Carmack |
| 11 | `vite-plugin-pwa` in v1 | A service worker can serve a reader a stale day, which attacks the one rule the whole scheme rests on. Revisit when a real reader asks for offline reading. | Jony |

### 13.1 The layout, literally

Data - committed, immutable, and the deletion atom is one day directory:

```
frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json     the day's current state, all items
frontend/public/digest/<YYYY>/<MM>/<DD>/run-<N>.json    that run's snapshot, N = run sequence
frontend/public/digest/<YYYY>/<MM>/<DD>/run.json        append-only runs[] for that date
frontend/public/digest/<YYYY>/<MM>/<DD>/<vertical>-<NN>.webp  optional visual, adjacent to what names it
evals/scores.csv                                        the ledger - never published, copied into dist at build
```

Routes, under the Pages project base:

```
/                          the newest published day, rendered inline    moving
/<vertical>/               the newest day, one vertical, rendered inline - canonicalises to the dated route
/<YYYY-MM-DD>/             that day, all verticals                      canonical, immutable
/<YYYY-MM-DD>/<vertical>/  that day, one vertical - a projection        canonical, immutable
/<YYYY-MM-DD>/#<vertical>-<NN>   an item anchor, force-revealed by the shell
/archive/                  every surviving day, newest first            (moving)
/evals/                    the dashboard                                (moving)
404.html                   the designed missing-day state
```

Nothing outside a day directory points into its interior except the append-only ledger. That
is what makes row 14 a single `rm -r` with no second edit.

---

## Row #14 - Retention job + site-budget alarm

- **Scope:** Bound the published site against the 1 GB Pages cap without ever deleting a measurement, and measure the ceiling long before the policy is needed.
- **Files touched:** `.github/workflows/retention.yml`, `backend/utilities/prune_assets.py`, `backend/utilities/site_budget.py`, `config/idhazh.json`, `backend/tests/test_retention.py`
- **Acceptance gates:** the job is a separate monthly workflow, never inside `daily.yml`; dry-run by default; refuses to act above `max_deletes_per_run`; ships disabled; `site_bytes` and `site_files` recorded on every daily run from day one.
- **Oracle:** the fuse - point the job at a fixture tree with a deliberately malformed date and assert it deletes nothing, reports the refusal, and exits non-zero. A retention job that cannot refuse is a retention job that will one day delete the archive.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Retention is a Pages-cap instrument, not a repo-size instrument.** Deleting a committed file reduces repo size by exactly zero; the blob stays in history and a rewrite is forbidden by section 8. | Carmack |
| 2 | **The levers are ordered and retention is third**: encode WebP not PNG (5.6x), honour the visual rule so roughly one item in three carries an image (2.9x), then retention. After the first two the wall moves from month 4 to year 5 and the knob may never be switched on. | Carmack |
| 3 | **Images only.** The job never touches a JSON payload, never deletes a date directory, never touches `evals/`, never changes a URL, and never runs inside the daily pipeline. | Carmack |
| 4 | Ships **disabled**: `image_months: -1`, `dry_run: true`. A default is a promise, not a placeholder. | Reader |
| 5 | **Age-based only, never size-threshold.** A size trigger makes the site a function of when the job happened to run. | Carmack |
| 6 | A **fuse**: refuse to act if the delete count exceeds `max_deletes_per_run`. An off-by-one in a date parse must not be able to delete the archive. | Carmack |
| 7 | The dry-run path **runs monthly even while disabled**, so the code is not first executed on the worst day of the year. | Carmack |
| 8 | **A pruned visual is a distinct state from a failed render**, with its own enum member, `version` date-stamp, changelog entry and read-side migration in the same commit. "We could not make this" and "we made it and threw it away" are different facts; one field must not mean both. | Fowler |
| 9 | `site_bytes` and `site_files` are recorded into the run manifest **on every daily run from day one**, and an issue opens above `site_budget_mb`. Measure the ceiling long before the policy exists (Holy Law #10 applied to storage). | Carmack |
| 10 | The retention window is **stated to the reader before anything is deleted** - on the archive page and on `404.html`. Deleting without ever having said you would is what turns mild annoyance into betrayal. | Reader |
| 11 | A pruned day 404s into the designed missing state, never a silent redirect to today. A reader who cannot tell a dead link from a live one has lost the ability to trust any link. | Reader |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | One knob governing both text and images | Text is 0.43% of the bytes. A policy that deletes 17 summaries to save 37 KB while leaving the images is aimed at the wrong axis. | Carmack |
| 2 | Reusing the render-failure state for a prune | A second meaning bolted onto an existing field, which is the band-aid Holy Law #5 forbids. Costs one enum member to do properly. | Fowler |
| 3 | Pruning the eval ledger, the golden fixtures, or the canaries | The ledger is the only record an item existed and the entire time series; a retired golden fixture is what makes a year-over-year claim interpretable; a retired canary is an attack no longer tested for. Under 1 MB/yr of text against gigabytes of images - the arithmetic does not even ask. | Andre |
| 4 | `git filter-repo` to reclaim history | Forbidden by section 8, and it invalidates every existing clone. | Carmack |
| 5 | Deleting a day and leaving its eval rows dangling with no context | Acceptable only if the eval row is self-describing. `source_url`, `date` and `title` must be columns before retention is ever enabled, not after. | Fowler |

---

## Row #15 - Pipeline fingerprint contract

- **Scope:** Stamp every summary, eval row and run manifest with the exact inputs that produced it, so a re-run can prove it changed nothing.
- **Files touched:** `backend/idhazh/contracts/{summary,eval_row,run_manifest}.py`, `backend/idhazh/fingerprint.py`, `schemas/*`, `evals/fingerprints.csv`, `backend/tests/test_fingerprint.py`
- **Acceptance gates:** the fingerprint is a sha256 over a sorted, fully-enumerated input set; `evals/fingerprints.csv` expands each distinct fingerprint into its components; a fingerprint match with unequal output records `determinism_violation` rather than failing the build.
- **Oracle:** the silent-drift trap - change only the truncation cap on a fixture, re-run, and assert the fingerprint changes and a second observation is recorded. If the fingerprint is stable across a changed cap, the stamp is blind and the row fails.

**Landed 2026-08-21.** The canonical page is [`docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md). `PipelineInputs` is the enumeration and the digest is taken over its own serialization, so a field added to the model changes every stamp and a field that was never declared cannot be silently forgotten. The oracle is generalised past the named case: the suite mutates *every* declared input one at a time and asserts each one moves the digest. `host_cpu` is excluded structurally rather than by filter. Skip-if-fingerprint-matches, and the recorded-not-raised violation, live in `backend/idhazh/fingerprint.py`.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `temperature=0, seed=0` is not determinism; it is determinism given identical logits. `seed` is dead code under greedy decoding and may not be cited as a control. | Andre |
| 2 | Fingerprint inputs: `model_sha256`, `quantisation`, `runtime_build`, `chat_template_sha256`, `prompt_sha256`, `output_schema_sha256`, `truncation_cap_tokens`, `sampling`, `n_ctx`, `n_batch`, `n_ubatch`, `n_threads`, `runner_class`, `extractor_version`, `sanitizer_version`. | Andre |
| 3 | `evals/fingerprints.csv` is append-only and never pruned. Without it a fingerprint is meaningless hex three years from now. | Andre |
| 4 | Skip-if-exists becomes **skip-if-fingerprint-matches**. Identical inputs do no work and write no eval row - a re-run that changed nothing measured nothing. | Andre |
| 5 | `host_cpu` is recorded as a diagnostic and excluded from the fingerprint - it is the only field that explains a violation, and including it would make every runner a different fingerprint. | Andre |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Trusting `temperature=0` and skipping the stamp | Eleven of sixteen enumerated drift sources are silent without it, including a publisher silently rewriting an article at the same URL. | Andre |
| 2 | Failing the build on a determinism violation | It will fire across runner CPU classes for reasons unrelated to a regression, and a flaky gate gets switched off within a month. Record it, count it, do not smooth it. | Andre |

---

## Row #16 - Read-state, new-arrivals block and pagination

- **Scope:** Give a returning reader their place back without an account, and make a re-ranked day legible rather than disorienting.
- **Files touched:** `frontend/src/lib/readstate.ts`, `frontend/src/lib/components/{Item,NewBlock,LoadMore}.svelte`, `frontend/tests/*`
- **Acceptance gates:** read-state in `localStorage` only, never a cookie; the page renders fully when storage is unavailable or cleared; read-state never feeds ranking; an anchor link force-reveals its item regardless of pagination; back-button returns to a truthful state.
- **Oracle:** reader-independence - render the same published day in two clients with different read-state, one with every item marked read and one entirely fresh. The rendered item set and item order are identical in both. Any divergence means read-state has leaked into ordering, and the row fails.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | New arrivals are grouped and labelled by **the run that introduced them** - a global fact, true for every reader, asserted without any storage. Never a diff against a remembered last-visit time. | Reader, Fowler |
| 2 | Read is marked on the **title link only**: one step down the text ramp, accent removed, one weight step lighter, plus the gutter marker going filled to hollow. Summary body and source link stay at full strength. | Jony |
| 3 | **Not dimming.** A dimmed item reads as disabled - "you cannot have this" - rather than read - "you already had this". Never colour alone. | Jony |
| 4 | Read is set on **source-link activation only**, never on scroll dwell. A wrong guess silently hides something unread and the reader cannot tell it happened. | Jony |
| 5 | Exactly two controls: a "hide read" toggle, off by default and persisted, and a "forget what I've read" escape in the footer. With no account, `localStorage` is the reader's only record and they need a way out of it. | Jony |
| 6 | Pagination is a **"load more" button** over the already-fetched day payload - zero extra requests. The label carries the remainder so the reader knows the end exists. | Jony |
| 7 | A reader who presses nothing gets the first page and that is the complete experience, not a truncated one. | Reader |
| 8 | Read-state may never influence ranking, ordering or membership - only appearance. The moment it does, the page is personalized with no ground truth, no way to evaluate it, and a shared link stops showing the recipient what the sender saw. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Infinite scroll | Unbounded DOM and a footer the reader can never reach - and the footer carries the run notice and the retention-window promise, both non-negotiable. | Jony |
| 2 | Numbered pages with `?page=` | A second address for a day that already has exactly one canonical address. | Jony |
| 3 | Mark-all-read | An inbox gesture. A digest is not an inbox, and it destroys the only signal the reader has. | Jony |
| 4 | A cookie for read-state | Sent on every request, which puts reading history into the host's access logs. `localStorage` never leaves the device. | Fowler |
| 5 | "3 new since your last visit" wording | It stakes a claim on a memory that evaporates when storage is cleared. Never make a claim about the reader's history that storage cannot back. | Reader |
| 6 | Client-side re-sorting so read items keep their place | Two readers would see different orders at the same URL, so a shared link stops showing the recipient what the sender saw. The order is part of what is being shared. | Fowler |
| 7 | Hiding or demoting an item once it has been read | Reading is one person's private fact. Everyone else has not read it, and a working news front page leaves an important story where its importance puts it. | Reader |

---

## Row #17 - Icon sprite + registry allowlist

- **Scope:** One build-time SVG sprite, referenced by id, with a drift gate that stops the icon set growing quietly.
- **Files touched:** `frontend/scripts/build-sprite.ts`, `frontend/src/lib/icons/allowlist.ts`, `frontend/public/icons/*.svg`, `frontend/tests/icons.test.ts`
- **Acceptance gates:** zero extra HTTP requests - the sprite is inlined once per document; a strict element and attribute allowlist rejects `<script>`, `<foreignObject>`, `href` and every event attribute; a pinned name list equals the manifest ids equals the symbols in the sprite.
- **Oracle:** the injection fixture - an SVG carrying a script element and an event attribute is rejected by the build with a named error. If it builds, the allowlist is decorative.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Glyph means **an inlined SVG `<symbol>` sprite referenced by `<use href="#icon-name">`**, emitted once at build. | Jony |
| 2 | The yen-gov allowlist discipline transfers, because the input is the same: a hand-authored or downloaded SVG can carry script, foreign objects and event handlers. Roughly thirty lines is the difference between an asset and an injection vector. | Jony |
| 3 | A pinned name list in a contract test is the cap on the icon set. Adding an icon is a deliberate two-file edit. | Jony |
| 4 | Budget fuse: the sprite may not exceed a configured fraction of the gzipped day payload. When the chrome outweighs the news, something is inverted. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | An icon font | A fetched face whose failure mode is tofu or a random letter in the middle of a reading page. | Jony |
| 2 | One SVG file per icon | One request per icon, which breaks the constant-request-count rule in row 13. | Jony |
| 3 | A typographic character | The shape varies per platform. You cannot ship a glyph you do not control. | Jony |
| 4 | A variant, size and optimisation pipeline | Overkill for a set this small. The pinned list is the cap. | Jony |

---

## Row #18 - On-device assist enabler (ships no feature)

- **Scope:** Make same-origin, reader-initiated, on-device inference possible and provably optional, without shipping a single reader-facing feature.
- **Files touched:** `frontend/vite.config.ts` (separate entry + budget gate), `frontend/src/lib/assist/loader.ts`, `frontend/public/assist/models/.gitkeep`, `.github/workflows/pages.yml` (CSP), `frontend/tests/assist-absent.spec.ts`
- **Acceptance gates:** no `@huggingface/transformers` symbol may appear in the first-load bundle - CI fails the build if one does; `env.allowRemoteModels = false` and `env.localModelPath` are set as contract, not config; a `connect-src 'self'` CSP is in place; nothing downloads before an explicit reader gesture.
- **Oracle:** the model-absent gate - delete the entire model directory, build, and run the full end-to-end browser suite. Every digest assertion passes and no console error appears. If the digest degrades at all, the feature is on the critical path and the row fails.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Holy Law #1 is amended in the same commit as this row, per CLAUDE.md section 0. The amendment bans egress and third parties, not compute: on-device work over bytes we committed and serve ourselves is permitted, and never sits on the digest's render path. | Fowler |
| 2 | Weights, tokenizer and WASM are committed under `frontend/public/` and served same-origin. `transformers.js` defaults to fetching a third-party hub; disabling that is a contract, not a preference. | Fowler |
| 3 | Nothing downloads or executes before an explicit click. No prefetch, no idle warm-up, no speculative load. | Carmack |
| 4 | A CI budget gate on the first-load bundle. Without it this decays in a single PR. | Carmack |
| 5 | WASM only. WebGPU is not the baseline: it is not universally available and its build costs an extra double-digit megabyte binary. | Carmack |
| 6 | Nothing computed on the device is ever transmitted, and nothing returns to `backend/`, a committed payload, or the ledger. | Fowler |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Loading weights from a third-party CDN | A runtime fetch to another origin, which is the half of Holy Law #1 that did not change. | Fowler |
| 2 | A service worker to enable cross-origin isolation | Row 13 already rejected service workers: one can serve a reader a stale day, which attacks the rule the whole layout rests on. | Jony |
| 3 | Shipping the enabler together with a feature | It would hide the one thing worth proving - that the digest is complete without any of it. | Fowler |

---

## Row #19 - Build-time embeddings in the day payload

- **Scope:** Embed the day's items on the runner and commit the vectors, so the browser only ever embeds a reader's query.
- **Files touched:** `backend/idhazh/embed.py`, `backend/idhazh/contracts/digest_day.py`, `schemas/digest-day.schema.json`, `backend/tests/test_embed.py`
- **Acceptance gates:** vectors are 256-dimension int8, base64-encoded **inside** the day payload rather than a sidecar file, so the request count stays constant; the payload validates against the versioned schema; a day renders identically with the vector block stripped.
- **Oracle:** round-trip - encode, commit, decode in the browser test, and assert cosine similarity against the runner's own computation is within tolerance. A silent dtype or endianness mistake fails here rather than as bad search results.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Embed at build time. The corpus is fixed at publish; embedding it in every reader's browser is repeated work for an identical answer. | Andre |
| 2 | 256 dimensions, int8. Full-width float vectors cost roughly an order of magnitude more for a quality difference nobody has measured here. | Andre |
| 3 | Vectors live in the day payload, not a sidecar, because row 13 fixes the per-page request count. | Carmack |
| 4 | Vectors are a **rendering**, regenerable from committed text, and are therefore exempt from the retention promises that protect the ledger. | Andre |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Embedding every item in the browser on page load | Repeated work for a fixed corpus, and it forces the encoder onto readers who never search. | Andre |
| 2 | Full-width float vectors | An order of magnitude more bytes against an unmeasured quality gain. | Andre |

---

## Row #20 - Browser semantic search

- **Scope:** Search the archive on the reader's own device, using the committed vectors and a query encoder, with no generative model anywhere.
- **Files touched:** `frontend/src/lib/assist/search.ts`, `frontend/src/lib/components/AssistFooter.svelte`, `frontend/public/assist/models/**`, `frontend/tests/search.spec.ts`
- **Acceptance gates:** the encoder is the smallest quantised sentence encoder that clears a measured retrieval bar; every byte is same-origin; the control states the download size before anything is fetched; a load failure degrades to the feature being absent, never to a broken page.
- **Oracle:** relevance - a fixture query set with hand-labelled expected items must retrieve them within the top few results. Without a labelled set this row cannot claim to work, only to run.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Search ships **first** among the assist features. It needs no generative model, it cannot hallucinate, and its worst failure is a bad ranking rather than a confident falsehood. | Andre |
| 2 | The browser embeds the query only. Item vectors are already committed by row 19. | Andre |
| 3 | The surface is one tertiary line in the footer - "search this archive on your device" - not a header search field. A search field promises instant results; this one promises a download. | Jony |
| 4 | The download size is stated in the same breath as the offer, and cached by the browser so a second visit is free. | Jony |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A header search field | It promises instant results and hides a multi-megabyte download behind a familiar affordance. | Jony |
| 2 | Keyword search instead | It would be free, but it cannot answer the question the reader actually has, which is topical rather than lexical. Recorded because it remains the correct fallback if the retrieval bar is not met. | Andre |

---

## Row #21 - Browser-runtime injection canaries

- **Scope:** Extend the canary suite across the trust boundary that now exists inside the reader's tab.
- **Files touched:** `tests/fixtures/canaries/browser/*.json`, `frontend/tests/canaries.spec.ts`, `.github/workflows/ci.yml`
- **Acceptance gates:** the five build-time attacks are carried end-to-end into a published fixture day and driven through the real assist UI in a real browser; three new attacks specific to this boundary are covered - instructing the browser model to render a link, markdown or HTML injection into the transcript, and exfiltration via an image source.
- **Oracle:** all eight canaries fail to inject through the browser surface. A single success fails the build and blocks row 23.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Holy Law #11 applies inside the tab. Our summary is derived from a stranger's page, so feeding it to a second model is the same boundary a second time - with no CI standing behind it. | Andre |
| 2 | Assist output is inserted as text content into a plain-text node. No `innerHTML`, no markdown rendering, no autolinking, no image rendering, ever. That is the mechanical control; a system prompt is not a control. | Andre |
| 3 | The browser model may not call a tool, issue any fetch, or receive any origin data beyond the item currently displayed. | Andre |
| 4 | Generated text and published summary text are structurally distinct surfaces, and generated text never appears inside an item card. | Andre, Jony |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | Reusing the build-time canaries unchanged | They guard a different boundary. The browser surface has attacks the pipeline does not - transcript rendering and exfiltration through markup. | Andre |
| 2 | Instructing the browser model to refuse injected instructions | A prompt is a request, not a control. | Andre |

---

## Row #22 - Read-aloud via Web Speech API

- **Scope:** Let a reader listen to a summary, at zero byte cost.
- **Files touched:** `frontend/src/lib/assist/speak.ts`, `frontend/src/lib/components/Item.svelte`, `frontend/tests/speak.spec.ts`
- **Acceptance gates:** uses the platform `speechSynthesis` already present on the device; ships no model and no weights; absent cleanly where the API is unavailable; reads published summary text only, never generated text.
- **Oracle:** byte parity - the built bundle is byte-identical in size with the feature enabled and disabled, apart from its own small module. If read-aloud costs megabytes, the wrong implementation shipped.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The platform speech API costs zero bytes and is already on the device. A neural voice model costs tens of megabytes against the same 1 GB cap that carries the search encoder. | Carmack |
| 2 | It speaks published, scored summary text verbatim, which makes the whole feature auditable by listening. | Andre |
| 3 | Revisit a neural voice only when a reader complains about the platform voice, and only against a measured byte budget. | Carmack |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A neural TTS model in the bundle | Tens of megabytes plus a phonemiser dependency, to improve a voice the platform already provides free. | Carmack |
| 2 | Generating an audio file in the pipeline | Audio per item per day is the heaviest artifact class in the system, against the cap that is already the binding ceiling. | Carmack |

---

## Row #23 - Browser chat SLM (ESCALATE-gated)

- **Scope:** Let a reader ask a follow-up about the summary in front of them, on their own device, clearly marked as unmeasured.
- **Files touched:** `frontend/src/lib/assist/chat.ts`, `frontend/public/assist/models/**`, `evals/assist-qa.csv`, `frontend/tests/chat.spec.ts`
- **Acceptance gates:** row 21 canaries green; every weight file under GitHub's 100 MB per-file hard limit; off by default behind an explicit reader action; chat answers carry no confidence band; a golden question set with human labels is published on the dashboard as a separate, lower number.
- **Oracle:** the eight browser canaries plus the file-size gate. A single weight file over 100 MB cannot be committed at all, which fails the row before any quality question is asked.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **ESCALATE before starting.** The instruct-tuned models that would make this good are single files far above GitHub's 100 MB limit; only the very smallest class fits. Whether that class is good enough is a question for measurement and a sign-off, not for an executing agent. | Carmack, Andre |
| 2 | Chat is unmeasured by construction - no faithfulness score, no ledger row, no golden set. The absence of a confidence band is the honest signal. | Andre |
| 3 | A human-labelled question set, re-run periodically and published as its own lower number. Not a faithfulness score, not a ledger row, and never a model judging a model. | Andre |
| 4 | Chat appears at an item only after the model has loaded. Rendering a chat control on every item turns a reading page into an application. | Jony |

| # | Option | Why rejected | Authority |
| --- | --- | --- | --- |
| 1 | A mid-size instruct model | Its single largest file exceeds the platform's hard per-file limit, so it cannot be committed at any budget. | Carmack |
| 2 | Sharding weights across files to dodge the per-file limit | It defeats the limit rather than respecting it, and it makes the load path fragile for a feature that is explicitly secondary. | Carmack |
| 3 | Shipping chat before search | Search is 20x smaller and cannot hallucinate. Ordering it second means the risky surface arrives before the safe one has proven the loader. | Andre |
| 4 | A disclaimer as the mitigation for unmeasured output | A reader who gets one fluent wrong answer downgrades their trust in the measured text beside it. A label does not undo that; only keeping the surfaces visibly separate limits it. | Andre |

---

## 2. Open questions (blocking, not deferred work)

| # | Question | Blocks | Needs | Resolution path |
| --- | --- | --- | --- | --- |
| 5 | Who curates the ~125 feeds, and in what order? Row 3 will not ship a vertical below its 25-feed floor, so the five cannot start together. | Row 3 | **OWNER ratifies** | **RESOLVED 2026-08-21.** The 36-feed `ai` list in section 3.2 is ratified and written to `config/sources.json`. The vertical stays `status: draft` until a feed-verification run confirms it clears the floor. Remaining verticals follow one per week under `draft`. |
| 3 | What rots at month 6? Extraction breaking silently on a site redesign is the live risk - a faithfulness score will happily reward a summary of navigation chrome. | Row 4 | agent | **RESOLVED 2026-08-21** by the row 4 Andre consult (section 4.1): per-item floors to row 4, per-domain trend alerts to row 12. |
| 4 | Do extremely low-bit (1-2 bit) quantisations change the model fit? Published for several open-weights families; unevaluated here. | Row 7 | agent, then ESCALATE | Research + measure. Andre on whether quality survives, Carmack on whether it fits - both measured, not assumed. See `docs/how-to/set-up-local-inference.md`. |

### RESOLVED

| # | Question | Resolution |
| --- | --- | --- |
| 2 | Who reads the digest? If nobody, the eval loop is the product and the digest is a test fixture. | **A general reader, the way a newspaper has one** (owner, 2026-08-21). The question was asked because a digest with no reader would make the dashboard the product; the answer inverts that. Row 11 ships, but as **operator instrumentation** - off the reading path, no design budget, obliged only to be correct - while the digest page carries the design effort (rows 13, 16, 17). The evaluation remains the product in the principle-6 sense: it is what makes the digest worth a stranger's two minutes. Recorded in `docs/concepts/vision.md`. |
| 6 | `temperature=0, seed=0` is not determinism, and eleven of sixteen drift sources were silent. | **Row 15** (2026-08-21). A `pipeline_fingerprint` stamps every input that can move an output; skip-if-exists becomes skip-if-fingerprint-matches; row 6's oracle is scoped to one runner class; a fingerprint match with unequal output is a recorded `determinism_violation` rather than a build failure. |
| 1 | Hosted inference (GitHub Models free tier) versus local weights. | **Local weights** (2026-08-21). Settled by contract rather than measurement: CLAUDE.md section 0a makes hosted inference a non-goal anywhere - pipeline, site or browser. On-device inference over committed weights is not hosted inference and is governed by Holy Law #1. |
| - | Which repo does this live in? Not yen-tamizh - that is a Tamil word game and this violates its CLAUDE.md scope. | **`yen-idhazh`** (2026-08-20). Own repo, own contract, own persona roster. Tamil *idhazh* = journal / magazine. |
