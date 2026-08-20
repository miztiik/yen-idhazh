# yen-idhazh - static-first article digest pipeline - plan

**Last Updated**: 2026-08-20
**Level**: 4 (structural, new subsystem) with named Level-5 ESCALATE triggers.

Execute per `docs/how-to/execute-a-plan.md`: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 3; honor the ESCALATE triggers in section 0. A trigger that fires mid-execution is handled per `docs/how-to/handle-scope-change.md`.

---

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Ship a daily job that summarizes public articles with a small LM inside GitHub Actions, scores every summary for faithfulness, and commits a dated JSON digest payload a static site renders - with no runtime backend. |
| Hard scope - in | Config-driven multi-vertical source discovery (a curated RSS/Atom feed list per vertical, cross-source repetition ranking, cross-cutting lenses, an entity watchlist); `trafilatura` extraction; Qwen3-8B summarization under constrained decoding; four-way visual routing; Vega-Lite + Mermaid deterministic renderers; CPU diffusion for narrative items; HHEM dual-score eval + CSV; GitHub Pages eval dashboard; per-URL atomic worker jobs. |
| Hard scope - out | Runtime backend or hosted inference; accounts; push notifications; paywalled sources; republishing article bodies; LLM-as-judge evaluation; fine-tuning; GPU runners; larger-than-9GB models. |
| ESCALATE triggers | (1) Row 7 model-validation gate fails its decision rule -> model pick is re-derived, PAUSE. (2) Any move to hosted inference (GitHub Models) - reverses the static-first premise. (3) Row 9 canaries fail against the chosen image model. (4) 3x cost overrun on any row. |
| Chosen strategy | Runtime pipeline is orchestrator + disposable sharded workers, mirroring the plan-execution model: a `plan` job emits and shards the URL list, a `matrix` of workers each handles ~5 URLs on its own VM and writes one content-addressed JSON per URL, an `assemble` job renders the digest. Ruled by Fowler (contracts before logic) and Carmack (fresh-VM-per-job is the parallelism primitive; shard size is set by measured model-load amortization). |
| Execution | autonomous orchestrator per `docs/how-to/execute-a-plan.md`. Parallel N = 3. |
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
 shard urls[]             write backend/var/run/<date>/<sha256(url)[:12]>.json
 (no model)                                                               publish frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json
```

Shard rather than one-VM-per-URL: section 2.1 measured model load at roughly half of
per-URL wall-clock. Per-URL atomicity survives inside the shard via content-addressed
writes plus skip-if-exists.

Both levels use the same rule: the orchestrator never does the work, and a worker failure is contained to one unit.

---

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Contracts, schemas and repo scaffold | - | A | PENDING | - | - | - |
| 2 | Measurement harness: throughput + corpus shape | - | A | PART-MEASURED (local 4B + 8B done, see 2.1/2.2; runner + corpus + image outstanding) | - | - | - |
| 3 | Source discovery, fetch + extract | 1 | B | PENDING | - | - | - |
| 4 | Eval harness: HHEM dual-score + deterministic metrics | 1 | B | PENDING | - | - | - |
| 5 | Injection canary fixtures + CI assertion | 1 | B | PENDING | - | - | - |
| 6 | Summarize worker | 1, 2, 5 | C | PENDING | - | - | - |
| 7 | Model validation gate (ESCALATE) | 3, 4, 6 | D | PENDING | - | - | - |
| 8 | Route worker + deterministic renderers | 6, 7 | E | PENDING | - | - | - |
| 9 | Image model selection + renderer | 2, 5, 8 | F | PENDING | - | - | - |
| 10 | Pipeline orchestrator workflow | 3, 6, 8 | F | PENDING | - | - | - |
| 11 | Pages eval dashboard | 4 | F | PENDING | - | - | - |
| 12 | Drift benchmark: weekly golden re-run + quarterly refresh | 4, 7 | F | PENDING | - | - | - |
| 13 | Published layout, date routing and the frontend shell | 1, 10 | F | PENDING | - | - | - |
| 14 | Retention job + site-budget alarm | 13 | G | PENDING | - | - | - |

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
| 2 | Per-item output is content-addressed at `backend/var/run/<date>/<sha256(url)[:12]>.json` (reproducible, gitignored); the COMMITTED record is the published digest under `frontend/public/` plus the eval rows. The digest is a rendering, never a source of truth. | Fowler |
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

---

## Row #5 - Injection canary fixtures + CI assertion

- **Scope:** Five planted articles carrying known attacks, asserted in CI on every prompt or model change.
- **Files touched:** `tests/fixtures/canaries/*.json`, `backend/tests/test_canaries.py`, `.github/workflows/ci.yml`
- **Acceptance gates:** five distinct attacks covered - direct instruction override, fake system delimiter, encoded payload, tool-call injection, exfiltration-via-URL; the suite runs on every PR.
- **Oracle:** all five canaries fail to inject. A single success fails the build.

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
| 6 | **Shard, do not fan out per URL.** Section 2.1 measured ~90 s of model cache-restore per job against ~173 s of work, so one-VM-per-URL spent ~50% of wall-clock loading weights. Each worker job takes a shard of ~5 URLs and loads the model once. Per-URL atomicity is preserved *inside* the shard by the content-addressed write plus skip-if-exists, so a re-run redoes only the unfinished URLs of a failed shard. This is the row-2 measurement changing the architecture, which is what row 2 is for. | Carmack |
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
| 7 | **A day is monotonic and positions are frozen.** An item's position is assigned once, at first publication, and never recomputed. A later run appends; it never reorders, never removes, never renumbers. Ranking decides which items enter and in what initial order - it does not get a second vote. | Reader |
| 8 | **A revision is visible or it does not happen.** If a later run changes an item's summary text, that item carries an `updated_at` and says so. Silently swapping better wording under a reader who already read it makes them doubt their own memory, and the summaries are the entire product. | Reader |
| 9 | When a day has more than one run, the page carries one plain line - "5 stories added since this morning" - and the new items are findable without re-skimming the old ones. | Reader |
| 10 | **No run identifier in any data path or any reader URL.** A run id in the path means one item at two paths and content-addressing is dead. The run id lives in the footer and in `run.json`. | Fowler |
| 11 | A topic is **a filter on the day**, with a shareable dated URL - not a destination a reader must choose before being given anything. The default interaction is an in-page anchor; the section heading is the permalink. | Reader |
| 12 | No title-derived slug in any URL. Titles come from fetched text, and fetched text never becomes a URL (Holy Law #11). | Jony |
| 13 | **Stack: Svelte 5 + Vite + TypeScript + Tailwind + vitest + Playwright + `json-schema-to-typescript` + `ajv`.** Matches both sibling repos' spine and yen-tamizh's lean profile. `ajv` over `zod` because it consumes the committed JSON Schema the drift gate already generates, where `zod` would need a second generator. | Fowler, Jony, Carmack |

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
frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json     the whole day, all items
frontend/public/digest/<YYYY>/<MM>/<DD>/run.json        append-only runs[] for that date
frontend/public/digest/<YYYY>/<MM>/<DD>/<item_id>.webp  optional visual, adjacent to what names it
evals/scores.csv                                        the ledger - never published, copied into dist at build
```

Routes, under the Pages project base:

```
/                          the newest published day, rendered inline    (moving)
/<YYYY-MM-DD>/             that day, all verticals                      (canonical, immutable)
/<YYYY-MM-DD>/<vertical>/  that day, one vertical - a projection        (canonical, immutable)
/<YYYY-MM-DD>/#<item_id>   an item anchor within the day
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

## 2. Open questions (blocking, not deferred work)

| # | Question | Blocks | Resolution path |
| --- | --- | --- | --- |
| 1 | Hosted inference (GitHub Models free tier) versus local weights. | Row 6 | Decide on row 2 measurement; reverses the static-first premise, so ESCALATE. |
| 2 | Who reads the digest? If nobody, the eval loop is the product and the digest is a test fixture. | Row 11 | User decision; changes whether row 11 ships at all. |
| 3 | What rots at month 6? Extraction breaking silently on a site redesign is the live risk - a faithfulness score will happily reward a summary of navigation chrome. | Row 4 | `word_count` and `extractiveness` need alert thresholds, not just CSV columns. Fold into row 4 acceptance gates. Feed-level rot - a source that stops publishing rather than one that changes shape - is handled separately by row 3 decision 6. |
| 4 | Do extremely low-bit (1-2 bit) quantisations change the model fit? Published for several open-weights families; unevaluated here. | Row 7 | Research + measure. Andre on whether quality survives, Carmack on whether it fits - both measured, not assumed. See `docs/how-to/set-up-local-inference.md`. |
| 5 | Who curates the ~125 feeds, and in what order? Row 3 will not ship a vertical below its 25-feed floor, so the five cannot start together. | Row 3 | Curate `ai` first - most tier-1 primary sources, fewest editorial judgement calls - and prove the loop end to end on one vertical. Then add one vertical per week under `status: draft` until each clears the floor. |
| 6 | **`temperature=0, seed=0` is not determinism.** It is determinism *given identical logits*, and logits move with batch shape, thread count, KV-prefix reuse, `llama.cpp` build and CPU dispatch path. `seed` is dead code under greedy decoding - it consumes no RNG. Eleven of sixteen enumerated drift sources are silent today because no published item stamps the model, quantisation, prompt, output schema or truncation cap that produced it. | Rows 4, 6, 10, 12 | Andre's ruling: replace skip-if-exists with **skip-if-fingerprint-matches** over a `pipeline_fingerprint`; scope row 6's determinism oracle to one runner class at fixed threads and batch shape; treat a fingerprint match with unequal output as a recorded `determinism_violation` rather than a build failure. Needs its own row before row 6 ships. |

### RESOLVED

| # | Question | Resolution |
| --- | --- | --- |
| - | Which repo does this live in? Not yen-tamizh - that is a Tamil word game and this violates its CLAUDE.md scope. | **`yen-idhazh`** (2026-08-20). Own repo, own contract, own persona roster. Tamil *idhazh* = journal / magazine. |
