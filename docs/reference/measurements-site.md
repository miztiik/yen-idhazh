# Site Measurements

**Last Updated**: 2026-09-10

Every number about **what the reader downloads**: the compression level the
origin serves, each page's ceiling, what a cold load costs, how fast the site
fills, and the weight of the archive, the search index and the published ledger.

[measurements.md](measurements.md) is the other half and holds the **producer**:
the model, the runner, prefill and decode, memory, shard cost and the corpus.
The two never cite each other's figures, and they read different config objects
- this page backs `page_weight`, `retention`, `ui`, `console` and `assist`,
where the other backs `models`, `run` and `extract`.

Both pages obey the two rules stated in full on
[measurements.md](measurements.md): a figure is either measured, with its date
and spread, or it is listed as unmeasured; and **a second and a resident set
belong to the box that took them, where a byte, a token and a pixel do not.**
Almost every figure here is a byte or a pixel, which is why almost none of them
names a machine - what they name instead is the runtime, because node's zlib and
python's `gzip` disagree by about 2 percent on the same file and that difference
is real.

## What compression level the reader actually pays, 2026-09-10

Toolchain: node 24.12.0. Date: 2026-09-10.
Method: fetch the live Pages origin with `accept-encoding: gzip`, read
`content-length` off the response, gzip the decoded body locally at every level
from 1 to 9 and find the nearest. n=1 per URL; the numbers are deterministic for
a given body, so a repeat measures the same thing.

**The page ceilings were `gzip -9` until this measurement and `gzip -5` after
it, and this is why.**

| Served | On the wire | Local `-5` | Local `-9` | Nearest local level |
| --- | --- | --- | --- | --- |
| `/console/` | 46,917 B | 46,787 B | 45,077 B | **-5**, 0.28 pct low |
| `/archive/` | 5,760 B | 5,755 B | 5,686 B | **-5**, 0.09 pct low |
| `telemetry/2026-09.csv` | 168,438 B | 164,742 B | 156,789 B | between -4 and -5, 2.19 pct low at -5 |

**What it means.** On a document, `-5` lands within a third of a percent of what
the origin sends and `-9` understates it by 3.9 percent. A ceiling meant to catch
growth, measured in a unit four percent below the wire, is four percent of growth
nobody sees - and four percent of `/console/` is 1,800 bytes, which is more than
a small regression costs. On a large CSV `-5` is 2.2 percent **low** rather than
high, so a payload ceiling in this unit flatters the payload slightly; that is
stated rather than corrected, because the alternative is a per-file fudge factor
nobody could check.

**The level and the six committed values had to move in one commit.** At `-5` the
tree already stood over two of the `-9` ceilings - `/console/model/` measured
56,652 against 56,385 and `/console/machine/` 44,960 against 44,706 - so either
half on its own leaves the build red.

## The page ceilings re-aimed at the migrated tree, 2026-09-10

Toolchain: node 24.12.0. Date: 2026-09-10.
Method: `gzip -5` over each prerendered `index.html` in `frontend/build`,
heaviest page per route class, **five builds of one tree**, heaviest per route
and never a mean - which is the method `bundle-gate.mjs` prints when a console
route fires.

| Route | Heaviest of five | Spread | Ceiling before (`-9`) | Ceiling set that day | Headroom |
| --- | --- | --- | --- | --- | --- |
| `/404` | 2,153 B | 7 B | 2,200 | 2,400 | 11.5 pct |
| `/archive/` | 5,744 B | 7 B | 7,553 | 6,400 | 11.4 pct |
| `/console/` | 46,775 B | 9 B | 335,051 | 52,000 | 11.2 pct |
| `/console/machine/` | 44,966 B | 11 B | 44,706 | 50,000 | 11.2 pct |
| `/console/model/` | 56,664 B | 16 B | 56,385 | 63,000 | 11.2 pct |
| `/evals/` | 3,232 B | 8 B | 3,279 | 3,600 | 11.4 pct |
| `/` | 180,086 B | 8 B | none | none | renders a day - counted, not capped |

**The six numbers in the fourth column stood for one day.** The owner ruled that
evening that a ceiling is a guideline and not a rule, and every one was replaced
by a guardrail at twice the page - the section below carries the live values. The
page weights either side of them are still the record of what the migrated tree
weighs.

**What it means.** The spread between two builds of the same tree is at most 16
bytes, which is 0.03 percent, so the distance above the page is a choice and not
noise. A tenth was the choice that evening, and it replaced four different
conventions the old set had accumulated - the old `/archive/` carried 43 percent
and the old `/404` carried 3.9. A tenth turned out to be the wrong choice for the
reason the next section gives.

**`/console/` fell by a factor of 6.4, and that is the finding rather than a
tidy-up.** It was sized on 2026-09-06 against a document that inlined the
telemetry and weighed 3.88 MB. Row 10 moved the telemetry to a browser fetch on
2026-09-09, the document became 46,775 bytes, and the ceiling stayed. For four
days it stood at 7.2 times the page it bounded, so nothing short of a sevenfold
regression could have fired it. **Nothing in the build fails when a number drifts
away from the page it bounds**, which is why it went unnoticed for four days.
That is a different fault from the distance a guardrail keeps on purpose: 7.2
times was nobody's choice and nobody could see it, where twice the page is
written down and re-derived.

There are **no dated ceilings and there never were**. `page_weight.ceilings_bytes`
has never named `/` or any `/<date>/` route, so row 14 removing every dated
document removed no key and the gate's unmatched-ceiling check never had anything
to say about them.

### What `BASE_PATH` does to the same document

Same box and date. One build with `BASE_PATH=/yen-idhazh`, the way `pages.yml`
builds, against the heaviest of the five plain builds `ci.yml` makes:

| Route | Plain | `BASE_PATH` | Delta |
| --- | --- | --- | --- |
| `/404` | 2,153 B | 2,172 B | **+19 B, +0.88 pct** |
| `/archive/` | 5,744 B | 5,749 B | +5 B |
| `/` | 180,086 B | 180,094 B | +8 B |
| `/evals/` | 3,232 B | 3,235 B | +3 B |
| `/console/` | 46,775 B | 46,778 B | +3 B |
| `/console/machine/` | 44,966 B | 44,964 B | -2 B |
| `/console/model/` | 56,664 B | 56,659 B | -5 B |

**What it means.** The sub-path is eleven repeated characters and gzip charges
almost nothing for a repeat, so the biggest move is 19 bytes on the smallest page
and every other route moves less than the spread between two plain builds. The
document CI measures is the document the reader is served, which is why
`bundle-gate` is not added to the deploy job
([../architecture/publishing/layout.md](../architecture/publishing/layout.md)).

## The guardrails at twice the page, 2026-09-10

Toolchain: node 24.12.0. Date: 2026-09-10, tree `c40eda91`.
Method: the same one as the section above - `gzip -5` over each prerendered
`index.html` in `frontend/build`, **five builds of one tree**, heaviest per route
and never a mean, with `frontend/build` and `frontend/.svelte-kit/output` deleted
between builds and no `BUILD_VERSION` set, so the tree matches what CI measures.

Owner ruling, the same day: "any ceiling is a guideline not a rule - increase
with twice the buffer and document it is a guard rail."

| Route | Heaviest of five | Spread | Guardrail | Times the page |
| --- | --- | --- | --- | --- |
| `/404` | 2,154 B | 7 B | **4,400** | 2.04 |
| `/archive/` | 5,761 B | 8 B | **12,000** | 2.08 |
| `/console/` | 47,077 B | 8 B | **96,000** | 2.04 |
| `/console/machine/` | 45,254 B | 3 B | **92,000** | 2.03 |
| `/console/model/` | 57,488 B | 5 B | **116,000** | 2.02 |
| `/evals/` | 3,227 B | 3 B | **6,600** | 2.05 |
| `/` | 43,737 B | 2 B | none | renders a day - counted, not guarded |

The three payload numbers were measured in the same runs and **none of them
moved**, because each was already past twice what it bounds:

| Payload | Heaviest of five | Guardrail | Times the payload |
| --- | --- | --- | --- |
| `console/band.json` | 777 B | 2,000 | 2.47 at its retention bound |
| `telemetry/2026-09.csv` | 167,505 B | 1,100,000 | 6.57 |
| a cold console load | 503,292 B | 3,400,000 | 6.76 |

`console/band.json` is priced at its bound rather than at today's size: its
`months` list is the union of the published month shards, every
`observability.public_*_keep_months` is 14, so a full list takes the payload to
about 809 bytes on the wire against 777 today.

**What it means.** A tenth over the page is a budget. Measured against the six
routes, an ordinary content day reaches it - so what fires the gate is a publish
rather than a regression, and the operator who is stopped raises the number,
which is the whole reason `/archive/` was raised twice in one day on 2026-08-26.
Twice the page cannot be reached by a day's content, so the only thing that fires
it is a change of a different order, and the answer is to find what took on the
bytes. Where the bytes are earned the number is re-derived to twice the new
heaviest, never nudged up to just clear the new page.

**`/` reads 43,737 B here against 180,086 B in the section above, and neither is
wrong.** `/` inlines the newest committed day, and the newest day between the two
measurements changed: `2026-09-10` holds 72 items where the mature days behind it
hold 282 to 627. So a `/` weight is a statement about one day's item count and
not about the page, which is exactly why no route that renders a day carries a
number. Anybody quoting a `/` figure says which day it inlined.

## What a cold console load costs and how deep its chain is, 2026-09-10

Toolchain: node 24.12.0, Chromium via Playwright.
Date: 2026-09-10. Method: a fresh browser context against `vite preview` over the
real build, recording Chromium's own `Request.timing` for every request. n=1;
the request set is deterministic, and the byte figures are read off the files
rather than off the clock.

| | |
| --- | --- |
| Requests on a cold `/console/` | 47 |
| On the wire, all 47 | 737,467 B |
| Of that, payloads | 303,306 B - two telemetry shards and nothing else |
| Serial round trips, payloads only | **3** against a ceiling of 4 |
| Round trips the verdict band costs | **0** |

**What it means.** The band is free on a cold load. `console/+layout.ts` is a
universal load on a prerendered route, so SvelteKit runs it at build time and
serialises the verdict into the document - it costs a request only on a
client-side navigation into the console. The three hops are the document, then
one telemetry shard, then the next: `loadVisibleMonths` awaits each month in turn,
so **a month is a hop**. That is the headroom being spent - a fourth month in the
default window is a fourth hop, and the ceiling is four.

**The default window can reach three months, not two.** A run of 30 consecutive
days lands in three calendar months when it starts on the 31st and February is in
the middle. A reader sees two on 363 days of the year and three on the other two.
The code comment saying "two of them and never more" is right about the ordinary
case and wrong about that pair of days; nothing is broken by it, because the page
fetches what the window reaches.

### The payloads, and what bounds them

`gzip -5` over `frontend/build`, same box and date:

| Payload | Now | Ceiling | Basis |
| --- | --- | --- | --- |
| `console/band.json` | 794 B | **2,000** | `months` caps at 14 by `observability.public_telemetry_keep_months` and `verdict.runs` at the cron slots, so 12 more month strings is all the growth there is |
| `telemetry/2026-09.csv` | 164,742 B | **1,100,000** | a full 31-day month at the heaviest day ever run |
| `telemetry/2026-08.csv` | 145,192 B | **1,100,000** | " |
| cold load, worst case | 495,020 B | **3,400,000** | the band plus three shards, each at its own ceiling, plus 3 pct |

**The telemetry ceiling is a full month and not today's file, and the difference
is 6.7 times.** Measured over both committed shards: 2026-08 holds 5,227 rows
over 8 days and 2026-09 holds 4,796 over 9, so **neither month is full** - the
archive starts on 2026-08-24 and the measurement was taken on the 10th. The
heaviest day ever run is 1,000 rows (2026-08-24 and 2026-08-25) and the heaviest
row costs 34.35 B at `gzip -5`, so a full 31-day month at that rate is 1,064,850
B. A ceiling set from what a shard weighs today would go red in October because a
month filled up, which is the failure that got the `/archive/` ceiling removed in
August.

**What it costs to set it there, stated rather than hidden:** at 6.7 times the
current file, this ceiling will not catch a doubling. It catches a shard that has
stopped being a shard. The instrument for a doubling is the round-trip count
beside it, which moves the day a month is added.

**A per-row ceiling was the rejected alternative** - "no telemetry row may cost
more than 40 gzipped bytes" fires the day a column is added and never fires on
ordinary growth, which is the Rule #12 shape. It was refused because it puts two
units in one config object, and a mixed-unit knob is read wrong once and then
trusted.

**`gzip -5` in node is not `gzip -5` in python.** The same 2026-08 shard measures
145,192 B under node's zlib and 142,291 B under python's `gzip.compress(data, 5)`,
a 2 percent gap. The gate is node, so every ceiling on this page is a node figure.

## What the shell migration saved, and the run that got it wrong, 2026-09-10

**The site ships at 98.7 MB in 581 files, and it has 727 published days of
runway to the 800 MB alarm point.** That is 13.3 MB and 182 files less than the
same tree carried on 2026-09-08, and 126 more days of runway.

Hardware: the stock GitHub-hosted `ubuntu-latest`. Method: `python -m idhazh
site-weight --site-tree build` in the `site` job of `ci.yml`, which builds the
tree the deploy uploads and measures that. n=4, across three commits on `main`
plus one merge candidate, read off runs `34413270718`, `34414162819`,
`34416869407` and `34445729013` between 2026-09-09T22:40Z and
2026-09-10T06:34Z. **All four printed the same four lines to the byte and to the
day, so the spread is zero** - a byte count over a fixed tree has none, and the
three trees differed only in source, which the site does not carry.

| | Before, 2026-09-08 | Shipping, 2026-09-10 | Change |
| --- | ---: | ---: | ---: |
| Built site | 112.0 MB | **98.7 MB** | -13.3 MB |
| Files | 763 | **581** | -182 |
| Bytes a published item | 15,013 | **12,644** | -15.8 pct |
| Slope at the 80-item ceiling | 1.15 MB a day | **0.96 MB a day** | -16.5 pct |
| Days to the 800 MB alarm | 601 | **727** | **+126 days** |
| Days to the 1024 MB cap | 796 | **959** | +163 days |

By directory today: `assist` 43.2 MB, `_app` 22.6, `digest` 19.0, `scores` 4.4,
`index` 4.3, `console` 1.3. The `assist` line is the committed encoder weights,
which stayed - row #17 of
[the shell-and-fetch plan](../../TODO/20260908-shell-and-fetch-plan.md) was
descoped when a GitHub Release asset turned out not to be readable
cross-origin, so the 22.59 MiB was forfeited deliberately.

### The run that was supposed to answer this measured something else

`.github/workflows/measure-migrated-tree.yml`, dispatched 2026-09-08 on
`ubuntu-latest` as run `34287508030`, ran two arms on one commit: the tree as it
shipped, and a "migrated" tree with the encoder weights removed and the dated
directories deleted. It reported **112.0 MB in 763 files and 601 days** for the
first and **89.4 MB in 757 files and 777 days** for the second, twice, 121 bytes
apart.

**The second arm did not delete the dated directories, and its own output says
so.** The file count moved by six, which is exactly the six files under
`frontend/static/assist/models/`. The `by directory` line moved `assist` from
43.2 MB to 20.6 MB and left `digest` at 18.2 MB and `console` at 7.9 MB
untouched. The `find frontend/build -maxdepth 1 -type d -regex` step that was
meant to remove them matched nothing.

**So 777 days is the runway of a tree nobody built and nobody will**: weights
gone and dated documents kept, which is the exact inverse of what shipped. It
may not be quoted for the site, and the plan's headline claim rested on it. The
727 above replaces it, and it needed no harness - the site as it ships **is** the
migrated tree, so the ordinary `site` job answers the question.

**What the fake arm did measure, and it is still worth having:** removing the
encoder weights alone is worth 22.6 MB and 176 published days of runway. That is
the price of keeping them, and the owner paid it on 2026-09-09 knowing the cap is
not close.

## What the encoder costs on the wire from Hugging Face, 2026-09-09

**A reader who searches will pay 6.75 MB more than today, and every byte of that
is one file.** Hugging Face serves `onnx/model_quantized.onnx` with no
`Content-Encoding` header at all - 22,972,370 bytes of
`application/octet-stream` - where our own origin serves the same file gzipped
at 16.22 MB. A first search goes from 21.6 MB to **28.4 MB, a 31 percent rise**.
Nothing else in the move costs anything: the tokenizer arrives gzipped from the
hub at 212,991 bytes against 0.21 MB from our origin, which is the same number.

This settles the fork Carmack left open on 2026-09-08 for
[row #1 of the shell-and-fetch plan](../../TODO/20260908-shell-and-fetch-plan.md):
it is the expensive arm. The 6.75 MB is what gzip was taking off the quantised
ONNX weights, 29.4 percent of them, and a hub that serves them as an opaque
octet-stream gives that back to the reader.

**Method.** curl 8.21.0 with zlib 1.3.2, over a residential connection reaching the
CloudFront edge `AMS58-P3`. Taken 2026-09-08 at 22:25 to 22:27 UTC, which is
2026-09-09 local. `curl -sIL -H 'Origin: https://miztiik.github.io' -H
'Accept-Encoding: gzip' <url>` for the headers, and `curl -s -L -o /dev/null -w
'%{size_download}'` with the same two headers for the bytes actually
transferred. Five files, three repetitions each: **every one of the fifteen
returned the same byte count, so the spread is zero.** `revision=main`, which
is acceptable for this measurement only - row #15 pins the revision that ships.

| File | Wire bytes, gzip offered | `Content-Encoding` | Bytes on disk |
| --- | --- | --- | --- |
| `onnx/model_quantized.onnx` | 22,972,370 | **absent** | 22,972,370 |
| `tokenizer.json` | 212,991 | `gzip` | 711,661 |
| `tokenizer_config.json` | 366 | absent | 366 |
| `special_tokens_map.json` | 125 | absent | 125 |
| `config.json` | 650 | absent | 650 |
| **Five files** | **23,186,502 = 23.19 MB** | | 23,685,172 |

The two columns disagree by 498,670 bytes and all of it is the tokenizer, which
is the only file the hub compresses. The 20.64 MiB ONNX runtime under
`frontend/static/assist/wasm/` is not in this table and is not moving: Hugging
Face is a model hub and does not host it, so a reader still fetches those
5.18 MB gzipped from our own origin, before and after.

**What this does not measure.** One network and one CDN edge. A byte count here
is a `Content-Length` the origin declares rather than a throughput, so a second
network would change the seconds and not the bytes - no seconds are quoted
above. What a second network genuinely could change is whether a different edge
negotiates gzip differently for the same object, and that is untested.

### Two facts the same five responses carried

Both are recorded here because they came off the responses measured above, and
both bear on rows #15 and #16.

**The upstream revision is `751bff37182d3f1213fa05d7196b954e230abad9`.** Every
one of the five responses returned it as `X-Repo-Commit`. `PROVENANCE.md`
records no commit SHA, which is why the plan carries an escalation trigger for
being unable to resolve one.

**The bytes we serve today are the bytes at that revision, on all five files.**
The hub's `ETag` is a git blob SHA-1 for the four small files and a SHA-256 for
the model, so each was checked against the matching thing we hold: `git rev-parse
HEAD:<path>` for the four, and SHA-256 of the working file for the model.

| File | Ours | Hub at `751bff37` | |
| --- | --- | --- | --- |
| `config.json` | `72147e4f...` | `72147e4f...` | git blob SHA-1, match |
| `special_tokens_map.json` | `a8b3208c...` | `a8b3208c...` | git blob SHA-1, match |
| `tokenizer_config.json` | `37fca747...` | `37fca747...` | git blob SHA-1, match |
| `tokenizer.json` | `c17ed520...` | `c17ed520...` | git blob SHA-1, match |
| `onnx/model_quantized.onnx` | `afdb6f1a...` | `afdb6f1a...` | SHA-256, match |

**A cross-origin read is allowed, and the check that says otherwise is wrong.**
With `Origin: https://miztiik.github.io` all five responses echoed that origin
back in `Access-Control-Allow-Origin`, and the model's CDN response answered
`*`. Sending no `Origin` header is the trap: the hub then answers
`Access-Control-Allow-Origin: https://huggingface.co` under a `Vary: Origin`,
which reads exactly like a refusal and is not one. Any later check of this has
to send an origin.

## Whether a browser can read the encoder from a second origin, 2026-09-09

**A GitHub Release asset cannot be read by a browser from another origin.** It
carries no `Access-Control-Allow-Origin` header on any hop, so Chromium refuses
the `fetch` before a byte arrives, and no setting of ours changes that -
`connect-src` is our list, CORS is the other origin's answer, and both have to
say yes. The failover origin
[row #15 of the shell-and-fetch plan](../../TODO/20260908-shell-and-fetch-plan.md)
named therefore does not work as a fetch target, and this is the row's
escalation trigger 2 firing rather than a detail.

Two origins that do work were measured in the same run, and both returned our
exact bytes on all five files. `raw.githubusercontent.com` at the release tag
answers in one hop with `Access-Control-Allow-Origin: *`. Hugging Face at the
pinned revision answers with the requesting origin echoed back, and hands the
23 MB weights to a CDN that answers `*`.

**The pinned revision is `751bff37182d3f1213fa05d7196b954e230abad9`** and the
bytes we hold are the bytes at it. That closes the escalation trigger for being
unable to resolve one: `PROVENANCE.md` recorded no commit SHA, and now the
repository does.

### The pin, and why the head of `main` is the right one

`Xenova/all-MiniLM-L6-v2` has 17 commits. `751bff37` is the head of `main`, so it
is what a `revision=main` fetch resolves to today, and it is what the five
committed files were taken from on 2026-08-22. Two independent checks agree:

- **The file tree at that revision.** `GET /api/models/Xenova/all-MiniLM-L6-v2/tree/751bff37...?recursive=1`
 returns a git blob SHA-1 for each small file and an LFS SHA-256 for the model.
 All five equal what we hold - `72147e4f`, `a8b3208c`, `37fca747`, `c17ed520`
 and `afdb6f1a...` - computed with `git hash-object` for the four and
 `Get-FileHash -Algorithm SHA256` for the model.
- **The response headers at that revision.** Every file returns
 `X-Repo-Commit: 751bff37...`, and the model returns
 `X-Linked-ETag: "afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1"`.

**The digests do not identify one commit, and a checker that assumes they do is
wrong.** The parent commit `48a5a372879ed2ed147ab84836e345977276d9b2` carries the
same five digests: the head commit added other ONNX variants and left the
quantised one alone. So "the commit whose digests match" is a set of at least
two, and the pin is chosen as the head of `main` at the fetch date rather than
derived from the bytes.

### The release, published and checked both ways

Tag `encoder-2026-08-22` on `miztiik/yen-idhazh`, targeting commit
`5f1eaf60067cc036a2927dc838935ad1fb8ece86`. A Release asset name cannot contain
`/`, so the five are flat. Each was uploaded from the committed file, then
downloaded again and hashed; **all five matched, so the spread is zero.**

| Asset | Path under the model directory | Bytes | SHA-256, committed file and downloaded asset |
| --- | --- | --- | --- |
| `config.json` | `config.json` | 650 | `7135149f7cffa1a573466c6e4d8423ed73b62fd2332c575bf738a0d033f70df7` |
| `special_tokens_map.json` | `special_tokens_map.json` | 125 | `b6d346be366a7d1d48332dbc9fdf3bf8960b5d879522b7799ddba59e76237ee3` |
| `tokenizer_config.json` | `tokenizer_config.json` | 366 | `9261e7d79b44c8195c1cada2b453e55b00aeb81e907a6664974b4d7776172ab3` |
| `tokenizer.json` | `tokenizer.json` | 711,661 | `da0e79933b9ed51798a3ae27893d3c5fa4a201126cef75586296df9b4d2c62a0` |
| `model_quantized.onnx` | `onnx/model_quantized.onnx` | 22,972,370 | `afdb6f1a0e45b715d0bb9b11772f032c399babd23bfc31fed1c170afc848bdb1` |

The release is kept even though a browser cannot read its assets, because the
**tag** is what makes the working alternative work: it holds the commit where the
weights are still committed, so `raw.githubusercontent.com` at that tag keeps
serving them after they leave `main`.

**What the tag costs, stated rather than left to be discovered.**
`.github/workflows/prune.yml` force-pushes `main` and pushes no tags, so this tag
survives every prune and keeps its commit - and that commit's whole tree,
`corpus/` included - reachable for ever. The prune bounds the repository by
making old commits unreachable; a tag is a ref, and a ref is reachability. This
is the first tag in the repository, so nothing was paying that before.

**Method.** over a residential connection. Taken 2026-09-09 between
04:21 and 04:22 local. The browser is Chromium 151.0.7922.34 driven by
Playwright 1.62.1 on node v24.12.0, from
`backend/utilities/encoder_origin_probe.mjs` - an operator tool, run by hand,
not a spec and in no suite, because Rule #7 forbids a test that touches the
network. The page is `https://miztiik.github.io/yen-idhazh/`, the deployed Pages
origin; `location.origin` and `isSecureContext` were read out of the loaded
document to prove it. Every fetch runs inside that document, so the `Origin`
header and the CORS check are production's. Twenty fetches per repetition,
**three repetitions of the widened arm and one of the as-deployed arm: every
verdict and every byte count was identical in all of them, so the spread is
zero.** Each fetched body is hashed in the page with `crypto.subtle.digest` and
compared against the file on disk, so a match means the browser got our bytes
and not merely a 200.

### Two arms, because one arm cannot tell the two gates apart

| Arm | What the document's `connect-src` said | Result |
| --- | --- | --- |
| As deployed | `'self'` | all 15 fetches refused, and the browser recorded no hop - the request never left |
| Widened | `'self'` plus the six hosts below | 10 of 20 read, 10 refused; the refusals are the other origin's, not ours |

The widened arm rewrites the `connect-src` directive in the CSP meta tag the
Pages document ships, and changes nothing else. Same scheme, same host, same
port, same document - only our own policy differs, and that policy is what
row #16 changes. Running one arm alone would have reported our CSP as a CORS
refusal, or a CORS refusal as our CSP.

### The four routes, and where each one breaks

Every row below is all five files. The chain is what Chromium recorded, hop by
hop; `BLOCKED` is where the browser stopped following it.

| Route | Chain | Verdict |
| --- | --- | --- |
| `github.com/miztiik/yen-idhazh/releases/download/encoder-2026-08-22/<asset>` | `github.com` **BLOCKED**, `net::ERR_FAILED`, no `Access-Control-Allow-Origin` | refused, 15 of 15 |
| `api.github.com/repos/miztiik/yen-idhazh/releases/assets/<id>` with `Accept: application/octet-stream` | `api.github.com` 302, `Access-Control-Allow-Origin: *` -> `release-assets.githubusercontent.com` **BLOCKED**, no header | refused, 15 of 15 |
| `raw.githubusercontent.com/miztiik/yen-idhazh/encoder-2026-08-22/<path>` | `raw.githubusercontent.com` 200, `Access-Control-Allow-Origin: *`, no redirect | read, 15 of 15, every digest matched |
| `huggingface.co/Xenova/all-MiniLM-L6-v2/resolve/751bff37.../<path>` | four small files: `huggingface.co` 307 -> `huggingface.co` 200, header echoes the origin. The model: `huggingface.co` 302 -> `us.aws.cdn.hf.co` 200, `Access-Control-Allow-Origin: *` | read, 15 of 15, every digest matched |

**The two GitHub release routes fail at different hops and for the same reason.**
The download URL fails at hop one, because a CORS request will not follow a
redirect whose response carries no header - so `github.com` in `connect-src` buys
nothing at all. The API URL gets past hop one and dies on the object host. Both
end at `release-assets.githubusercontent.com`, which sends no CORS header on a
GET, a HEAD or after a redirect, and `github.com` answers an `OPTIONS` preflight
with a 404 HTML page.

### The `connect-src` list, measured

Three hosts and `'self'`, not the four the plan expected:

```text
connect-src 'self' https://huggingface.co https://us.aws.cdn.hf.co https://raw.githubusercontent.com
```

`us.aws.cdn.hf.co` is the hub's LFS CDN and it is where the 23 MB file actually
comes from; listing `huggingface.co` alone passes the four small JSON files and
blocks the weights, which is the half-loaded failure Andre named on 2026-09-08.
That prediction is confirmed. What is amended is the rest of his list:
`github.com` and `objects.githubusercontent.com` were expected to carry the
failover and neither appears here - `objects.githubusercontent.com` is not even
the host a release download redirects to any more, and
`release-assets.githubusercontent.com`, which is, cannot be fetched from at all.
**Adding an unusable host to `connect-src` widens the exfiltration surface and
buys nothing**, so all three are left out.

### Three traps this run walked into

They are tool quirks rather than readings, so they live where a reader looking
for one would search: the CORS failure Playwright's `response` event cannot see
and the disagreement between `curl -I` and a browser are in
[agent-notes/browser.md](agent-notes/browser.md), and the `ETag` that is not the
SHA-256 is in
[agent-notes/shell-and-tools.md](agent-notes/shell-and-tools.md).

### What this does not measure

One machine, one network, one browser engine. Firefox and Safari implement the
same CORS rule, but they were not run, so the refusal above is Chromium's and
the inference to other engines is a prior rather than evidence. Nothing here
measures a rate limit: `raw.githubusercontent.com` is documented as
rate-limited and no request in this run was throttled, which says nothing about
what happens when a hundred readers search in a minute. And no arm measured a
reader who already holds the bytes, because every fetch ran with
`cache: 'no-store'`.

## What the reading page does with a wide screen, 2026-09-02

Toolchain: node 24.12.0, Chromium headless
through Playwright 1.62. Date: 2026-09-02. Method: `npm run build` on the
committed digest, then `vite preview`, then one page load per width and per
root font size, reading `getBoundingClientRect.width` off the frame, the
first item, and the item's summary. The route is `/`, which carries the whole
day inline - a dated route seeds 15 stories and fetches the rest, so a layout
measured on its first paint is a layout measured on a seed. Spread is zero by
construction: a used width is a layout fact and repeats exactly.

### Before: the item did not waste the page, and the card wasted 230 px of itself

At a 1536 px viewport, on `origin/main` at `06ddd84a`:

| Quantity | Value | Share |
| --- | --- | --- |
| the frame's content box | **1,216 px** | - |
| the frame's used width | **1,280 px** | 83.3 percent of the viewport |
| the item's used width | **1,216 px** | 100 percent of the content box |
| the summary's used width | **659.81 px** | 54.3 percent of the content box |

**So the page-level waste was zero and the card-level waste was 230.19 px.** The
item filled the content box exactly; inside it the card body was 890 px and the
summary 659.81, and the strip between the summary and the item's 224 px footer
rail stood empty on every one of the day's stories. That is 18.9 percent of the
content box, at every width from 1,280 px up.

This number was taken before a layout was chosen, and it moved the design twice.
It killed the idea that the frame is the problem: at 801 px the frame is 789 and
the item 725, which is 91.9 percent, and at 1536 the item takes all 1,216 px it
is offered. And it sized what could be spent, which is one column of at most
27.1 rem once a 68-character measure and a 1.75 rem mark are paid for.

### After: an aside takes 288 px of it, and the measure never moves

Same method, same widths, on the branch:

| Quantity | Before | After |
| --- | --- | --- |
| the frame's content box | 1,216 px | **1,216 px** |
| the frame's used width | 1,280 px | **1,280 px** |
| the item's used width | 1,216 px | **896 px** |
| the summary's used width | 659.81 px | **659.81 px** |

The item is narrower because the day's leading stories now stand beside it in an
18 rem column instead of above it: 896 + 32 gap + 288 aside = 1,216, so the
content box is still full. Empty width beside the summary falls from 230.19 px
to 146.19 px, and the width that carries something rises from 872 px
(659.81 summary + 212 rail) to 948 px (659.81 summary + 288 aside), which is
71.7 percent to 78.0 percent of the content box.

**The measure did not move, at any width.** That was the constraint: a wide card
holding a 68-character paragraph is not wasted space, and widening the paragraph
is what the measure exists to prevent.

### No zone is a pixel count, and this is how that was checked

Every zone is a `rem` knob in `config/appearance.json`. Raising the root font
size from 16 px to 22 px - the reader's own setting, not a browser zoom, which
would scale the CSS pixel and move a hardcoded zone too - moves all of them by
the same 1.375x:

| Zone | Token | At a 16 px root | At a 22 px root | Factor |
| --- | --- | --- | --- | --- |
| the source mark | `--zone-mark` | 28 px | 38.5 px | 1.375 |
| the item's footer rail | `--zone-rail` | 224 px | 308 px | 1.375 |
| the day's aside | `--zone-aside` | 288 px | 396 px | 1.375 |
| the gap between them | `--space-6` | 32 px | 44 px | 1.375 |

`frontend/tests/item-zones.spec.ts` is the memory. It reads each zone's used
width at both root sizes and fails if one did not scale, and it prints both
numbers in the failure so the assertion cannot pass on a layout it never
measured.

## What the time rail costs and what it removes, 2026-09-02

Toolchain: Python 3.14.2. Date: 2026-09-02.
Method: read every `frontend/public/digest/**/digest.json`, re-order each day by
`published_at` descending with `item_id` breaking a tie, then walk the result
counting the group changes at the committed 60-minute grouping. Spread is zero
by construction: the input is committed bytes and the arithmetic is a sort and a
scan.

### The re-order keeps the day, on every day

| Days | Stories | Days whose story set changed |
| --- | --- | --- |
| 12 | 4,713 | **0** |

That is the claim the row rests on and it is the one worth checking rather than
asserting: a sort that drops a story looks exactly like a day that published
fewer, and nothing on the page would say which. `frontend/tests/time-rail.spec.ts`
re-runs it over every committed day on every build.

### The rail draws 907 labels where a label per story would draw 4,713

| Day | Stories | Markers | Labels not drawn |
| --- | --- | --- | --- |
| 2026-08-21 | 4 | 4 | 0 |
| 2026-08-22 | 10 | 4 | 6 |
| 2026-08-23 | 147 | 56 | 91 |
| 2026-08-24 | 731 | 209 | 522 |
| 2026-08-25 | 724 | 208 | 516 |
| 2026-08-26 | 621 | 146 | 475 |
| 2026-08-27 | 334 | 76 | 258 |
| 2026-08-28 | 117 | 26 | 91 |
| 2026-08-29 | 366 | 75 | 291 |
| 2026-08-30 | 431 | 34 | 397 |
| 2026-08-31 | 601 | 36 | 565 |
| 2026-09-01 | 627 | 33 | 594 |
| **total** | **4,713** | **907** | **3,806** |

**80.8 percent of the labels a marker-per-story rail would print are duplicates
the rail leaves out.** The two newest days are the ones to read: 2026-09-01
draws 33 markers over 627 stories, so a reader scrolling the busiest day meets a
time about every nineteen stories rather than beside every one.

The older days draw more markers per story, and the reason is a fact about the
feeds rather than about the rail: before 2026-08-31 the day carried stories
whose feed stamps run years back, so the hour groups are sparse. 2026-08-24 has
275 stories dated before the day it published on, spread over 1,978 days.

### Which clock, over every committed day

| `time_source` | Stories | Share |
| --- | --- | --- |
| `feed` | 970 | 20.6 percent |
| `first_seen` | 10 | 0.2 percent |
| `unknown` | 0 | 0 |
| absent (published before the field existed) | 3,733 | 79.2 percent |

And which form each story gets. The counts are the 2026-09-02 census and have
not been re-taken; the strings in the left column are what the rail prints from
2026-09-06, when it collapsed to digits and the words came off:

| Form | Stories | Share |
| --- | --- | --- |
| `14:05` - the day being read | 3,547 | 75.3 percent |
| `06-11 08:15` - any earlier day, `2019-06-11 08:15` across a year | 1,156 | 24.5 percent |
| `06:20` with a mark - our clock | 10 | 0.2 percent |
| nothing - no stamp at all | 0 | 0 |

The two dated rows were counted separately before the collapse - 776 stories,
16.5 percent, older than the day before, and 380, 8.1 percent, on the day before
itself, which printed `Yesterday 23:40`. They print the same shape now, so they
are one row.

**`unknown` is empty and that is why the canary day plants one.** A branch no
fixture reaches ships with no test, and this one decides whether a story with no
time at all still renders rather than throwing. The canary carries one story of
every form.

**47 of the 4,713 stories are stamped exactly `T00:00:00Z`**, 1.0 percent, which
is what a date-only feed date parses to and also what a story genuinely
published at midnight parses to. That figure is why the rail still prints a
clock on a midnight stamp: blanking it would hide the real midnight stories
inside the same 1.0 percent, and the payload cannot say which they are
([../architecture/publishing/layout.md](../architecture/publishing/layout.md#the-rail-is-what-reads-it-and-what-it-can-and-cannot-say-2026-09-02)).

### A phone gets no rail column, and this is the number that decided it

Toolchain: node 24.12.0, Chromium headless
through Playwright 1.62. Date: 2026-09-02. Method: the canary build served by
`vite preview`, one page load per viewport and per root font size, reading
`getBoundingClientRect.width` off the stream grid, the first item and its
summary. Spread is zero by construction.

The rail was first drawn as a `3.5rem` column at every width. At 360px that is
what it cost:

| Quantity | Rail as a phone column | Rail as a rule above the group |
| --- | --- | --- |
| the frame's content box | 328 px | 328 px |
| the rail column plus its gap | 68 px | **0** |
| the item's used width | 260 px | **328 px** |
| the summary's used width | **186 px** | **254 px** |

**186px is about 25 characters, and it broke `Interconnector` across two lines
in the title.** The item already spends 40px on the read mark and its gap and
32px on its own padding, so a phone cannot carry a rail column, the mark and a
readable line at once. Below the small breakpoint the marker is a rule across
the top of its group with the time under it, which costs the reading column
nothing. What the reader loses is the label sitting level with the story it
opens.

From the small breakpoint the column is a `rem` and it scales:

| Viewport | Root 16 px | Root 22 px | Factor | Summary at 16 px |
| --- | --- | --- | --- | --- |
| 360 | no column | no column | - | 254 px |
| 801 | 88 px | 121 px | 1.375 | 559 px |
| 1280 | 88 px | 121 px | 1.375 | 659.81 px |
| 1536 | 88 px | 121 px | 1.375 | 659.81 px |

**The measure did not move at any width above the small breakpoint**: the
summary is 659.81px with the rail, which is what it was without it. The rail
takes its 104px from the item's own empty width rather than from the prose.

On the canary day - eight stories planted to carry every state - the rail draws
**7 markers and one glyph** at every one of those widths, in this order:
`14:58`, `11:00`, `09:20`, `06:20` with the glyph, `08-19 23:40`, `06-11 08:15`,
and an empty marker for the story with no stamp. The eighth story is at `14:05`,
inside the first marker's hour, so it carries no label - which is the grouping
doing its job on a fixture small enough to read by eye. The widths above were
measured 2026-09-02 against the old word labels; the collapse to digits on
2026-09-06 made every label shorter or the same, so the column was not re-taken.

## Published payload size

### Prose compression

Date: 2026-08-20. Method: gzip over 32 prose
files, 276,887 B -> 94,690 B.

**2.92x.** This is the ratio the day-payload arithmetic uses.

### The day payload

Date: 2026-08-21. Method: gzip level 9 over
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

### The prerendered page, on the wire

### The archive day list stops growing a row a day

Toolchain: node 24.12.0. Date: 2026-09-01.
Method: two fixture archives generated under `$env:TEMP` and read through
`DIGEST_ROOT`, so nothing under `frontend/public/` moved. Both cover the **same
24 calendar months**, 2 October 2024 to 1 September 2026, one at 700 published
days and one at 182 - so the difference between the two is days and nothing
else. Each arm is one `npm run build` and `gzip -9` over
`build/archive/index.html`. The before arm is `origin/main`'s own archive
source, checked out in place over this branch's and copied back afterwards, in
the worktree that built the after arm.

| Arm | Published days | `gzip -9` of `/archive/` | Day-list markup, raw | Day links |
| --- | ---: | ---: | ---: | ---: |
| Before, 700 days | 700 | 12,045 | 74,621 | 700 |
| Before, 182 days | 182 | 6,319 | 19,457 | 182 |
| After, 700 days | 700 | 10,484 | 73,385 | 707 |
| After, 182 days | 182 | 6,348 | 26,460 | 189 |

Growth per published day, over the 518 days between the two arms of each pair:

| | Bytes a day, `gzip -9` | Day-list markup, raw bytes a day |
| --- | ---: | ---: |
| Before | 11.05 | 106.5 |
| After | **8.0** | 90.6 |

**The document still grows with days, 27.7 percent more slowly.** The row that
produced this asked for a document growing with months and not with days, and
that is not what the measurement says. The design was kept and the claim was
corrected: reaching zero means not emitting a link for each published day, and a
reader with no script would then reach seven days and no further
([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md#the-day-list-grows-with-months-on-the-page-and-with-days-in-the-document)).

**What a reader sees is the number that did change.** At 700 days the list is
**18 rows** - seven days, nine months of the newest published year, and one row
each for 2025 and 2024 - against 700 links before. Opening every year tops out
at a row a month.

**The saving is in the serialised data, not the markup.** At 700 days the
document went 115,563 -> 88,925 raw bytes while the day-list markup barely moved
(74,621 -> 73,385). A flat list of `{date, items, partial}` objects became a list
of day-of-month numbers under a month key, and the serialiser holds the 31
distinct numbers once however many months there are.

**11.05 cross-checks the 12.21 in the next section**, which was taken a
different way - one built page grown k days in place, on a six-day corpus, on
2026-08-27. That table's own marginal rate falls with size and reads 11.47 at
730 days, so the two methods agree to within 4 percent at the same scale. The
committed archive is 12 days, so the `/archive/` ceiling derivation below is
untouched by this row; what changes is that its headroom now shrinks about 8
bytes a publish instead of about 12, so the year it was sized for gets longer
rather than shorter.

### The archive stops carrying the corpus

Toolchain: node 24.12.0. Date: 2026-08-27. Method:
one checkout, one set of committed day payloads, built twice - once with the
frontend source at `9d25827` and once with search reading the month index. Only
`frontend/src` and `frontend/scripts` differ between the arms, so nothing the
pipeline published between builds can move the number.

| Route | Eager day payloads | Month index | Change |
| --- | ---: | ---: | ---: |
| `/archive/` | 1,766,682 | 2,912 | **-1,763,770, which is 99.8 percent** |
| Every prerendered page, summed | 13,247,645 | 11,483,881 | -1,763,764 |

Two builds of each arm agree to 1 byte on the old source and to 8 bytes on the
new one, so the noise floor is far below anything here. **1.7 MB is what the
archive charged a reader for opening a page to find one story**, and the whole
of it was the day payloads on-device search read the vectors out of.

**Growth per published day, which is the shape rather than the size.** The same
two sources built over two fixture corpora that differ by exactly one real
committed day - 2026-08-26, which holds 621 items:

| Source | 5 days, 1,616 items | 6 days, 2,237 items | One day of 621 items costs |
| --- | ---: | ---: | ---: |
| Eager day payloads | 1,276,839 | 1,766,682 | **+489,843**, or 788.8 bytes an item |
| Month index | 2,888 | 2,912 | **+24**, or 0.039 bytes an item |

24 bytes is the day's own link in the compact row and the digits of two counts.
It does not move with how many stories the day published, which is the property
the index exists to buy: **the page now grows per day, and it used to grow per
story.** At the old rate a year of publishing added 179 MB to one document; at
the new one it adds 8.8 KB.

**What it costs elsewhere, stated rather than left to be discovered.** The
bundle gains the two files search now fetches and the day payloads a result
renders from: `static/index` goes from 378,869 bytes to 1,237,109 (the
sibling `.bin` joins the JSON), and `static/digest` from 1,055,600 to 6,976,807
(six `digest.json` join 87 rendered images). That is 6.78 MB on disk against
1.76 MB off the page, and the two are paid by different people - every visitor
pays the page, and only a reader who searches and then opens a result pays a day
payload.

#### The ceiling that holds the saving, and where its headroom comes from

Toolchain: node 24.12.0. Date: 2026-08-27. Commit
`6cef91e`, which is the archive branch with the search field and `origin/main` at
`3df9ed7` merged in. Method: `npm run build` then
`frontend/scripts/bundle-gate.mjs`, five builds of one tree, six committed days,
2,237 items.

| Route | 1 | 2 | 3 | 4 | 5 | Range | Ceiling committed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `/archive/` | 3,032 | 3,033 | 3,029 | 3,029 | 3,027 | 6 | **7,553** |

**The base is the merged tree, and that is the whole reason this number was
re-derived.** An earlier pass measured 2,899 to 2,906 bytes on a tree that did
not yet carry the archive search field. The field landed, the page grew about
127 bytes, and a ceiling derived from the older base would have spent that
straight out of the headroom and fired at day 362 rather than at a year. A
ceiling is set from a measurement of the merged result, never of a branch.

**The number this replaces is not a smaller one, it is no number at all.** The
`/archive/` ceiling was deleted on 2026-08-26 because a page that inlined every
committed day could not hold one. So the page went from 1,766,585 bytes with
nothing above it - measured by CI on `origin/main` at `48d6207`, run
`33032515368` - to 3,033 bytes with a ceiling 234 times smaller than the weight
it used to carry.

**The headroom is a measured year of publishing, not a round number.** The other
two capped routes sit 55 to 72 bytes under their ceilings, because `/404` and
`/evals/` move only when the source moves and 64 bytes is the build noise floor.
`/archive/` is deliberately not on that convention: it renders one link per
published day, so the tight convention would fire on the fourth ordinary publish
- which is exactly the countdown that got the last `/archive/` ceiling deleted.

What a day costs was measured directly on the built page rather than derived
from the two-corpus table above: take `build/archive/index.html`, add k future
days everywhere a day appears - the compact day row, the serialized `days`
array, the month keys those days need, and the day and story counts the page
prints - give each one a real item count cycled from the six committed days, and
`gzip -9` the result. The base row is the fifth build, 3,027 bytes, because the
table is one page grown k times; the growth is a delta and it is what carries
over to the heaviest build.

| Days added | `gzip -9` | Added | Bytes a day |
| ---: | ---: | ---: | ---: |
| 0 | 3,027 | 0 | - |
| 1 | 3,045 | 18 | 18.00 |
| 7 | 3,161 | 134 | 19.14 |
| 30 | 3,488 | 461 | 15.37 |
| 90 | 4,227 | 1,200 | 13.33 |
| 300 | 6,799 | 3,772 | 12.57 |
| **365** | **7,483** | **4,456** | **12.21** |
| 371 | 7,557 | 4,530 | 12.21 |
| 730 | 11,400 | 8,373 | 11.47 |

The marginal day gets cheaper as the page grows, from 18 bytes for the next one
to 12.21 averaged over a year, because each day link is nearly a copy of the one
above it and gzip charges less for a repeat. So the arithmetic is:

```text
 3,033 heaviest of five builds
+ 4,456 a year of ordinary publishing, measured
+ 64 the build noise floor derived below
= 7,553
```

**What the headroom cannot absorb.** 4,520 bytes of slack sounds generous until
it is priced in the unit of the regression: a day payload back on the page costs
788.8 gzipped bytes an item (measured above), so the ceiling fires the moment
six items' payloads return. The regression it exists to catch is not six items -
it is the whole corpus, 1,763,773 bytes, which is **390 times the headroom**.
Restoring the eager load was run against this ceiling on 2026-08-27: the page
built at 1,766,806 bytes and the gate failed with `/archive/ weighs 1,766,806 B
(1766.8 KB), 1,759,253 B over the 7,553 B ceiling`.

**The headroom tightens on its own.** It is at its loosest the day it is set and
shrinks 12 to 18 bytes every publish, so by day 300 there are about 750 bytes of
slack - less than one item. A ceiling that gets stricter without anybody editing
it is the opposite of the one this replaces, which got looser every time
somebody raised it.

**Revisit at a year, or when the archive page starts rendering something new.**
The headroom survives 370 days of ordinary publishing: at 370 days the page
measures 7,538 bytes with 15 to spare, and at 371 it measures 7,563 and the gate
fires on an ordinary publish. That is the design: re-measure and re-derive then,
rather than add a digit. If the page ever renders per-story markup again the
per-day figure above is void and the ceiling has to be re-derived before it is
raised.

**Twelve of those days were spent on 2026-09-06, and the runway is shorter for
it.** `ui.archive_recent_days` moved from seven to fourteen, so the block of day
rows above the month list is twice as long. Toolchain: node 24.12.0. Date:
2026-09-06. Method: `npm run build` then
`frontend/scripts/bundle-gate.mjs` on one worktree at 16 committed days, once at
each setting. Spread: not taken - one build an arm, and the 64-byte noise floor
derived above is four hundred times smaller than the move. `/archive/` weighs
**5,015 bytes at seven rows and 5,163 at fourteen**, so seven extra rows cost
148 bytes, which is 21.1 a row. That is a one-off step and not a change of
slope: the knob fixes the row count, so it does not grow with publishing. At the
12.21 bytes a day a year averages, it spends about **twelve of the 370 days**,
putting the re-derivation around day 358. Nothing else in the derivation moves.

Toolchain: onnxruntime 1.29.0. Date: 2026-08-26.
Method: decode each committed vector, re-encode its item's `title. summary`
through `idhazh.embed`, and compare - cosine on the decoded pair, and the item's
top-10 neighbours within its own day computed from each side.

| Day | Vectors compared | Cosine min | Cosine median | At or above 0.9999 | Byte-identical | Max byte delta | Top-10 moved |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 2026-08-21 | 4 | 0.992538 | 0.994693 | 0/4 | 0/4 | 2 | 0/4 |
| 2026-08-22 | 10 | 0.991415 | 0.993853 | 0/10 | 0/10 | 3 | 6/10 |
| 2026-08-23 | 137 | 0.988646 | 0.993482 | 0/137 | 0/137 | 3 | 134/137 |
| 2026-08-24 | 145 | 0.987867 | 0.993621 | 1/145 | 1/145 | 3 | 138/145 |
| 2026-08-25 | 143 | 0.989480 | 0.993632 | 0/143 | 0/143 | 3 | 135/143 |
| **2026-08-26** (CI wrote it that day) | 80 | 0.996260 | **1.000000** | 58/80 | 54/80 | 2 | not measured |

The last row is the control, and it is what makes the other five readable. A
Windows re-encode reproduces the day CI had written hours earlier at a median
cosine of exactly 1.000000, with 54 of 80 vectors byte-identical - so the
machine is not the variable. Every closed day predates `a995b18`, the commit
that stopped `encode` padding its input and batching it, so those vectors carry
an arithmetic the browser's query encoder no longer uses. That is why a short
day is re-encoded whole rather than topped up.

After the repair, the same test over the repaired days reads cosine 1.000000,
60 of 60 byte-identical, maximum byte delta 0 and zero rank movement on each of
2026-08-23, 2026-08-24 and 2026-08-25. The only vectors still below the bar are
the 14 on 2026-08-21 and 2026-08-22, which already had one for every item they
earned and were therefore skipped.

Encode cost: 0.16 s an item, one sequence per forward pass. 1,602 items in
511 s, single-threaded, on a loaded machine.

### Days to the 1 GB Pages ceiling

**This section divided by the wrong tree until 2026-08-27, and both of its
answers were wrong by about twenty times.** It took the headroom of the
**published site** and divided it by the daily growth of the **committed payload
tree** under `frontend/public/digest/`. Those are two different directories.
Measured 2026-08-27 on this checkout: the payload tree is 7,027,075 bytes and
the built site is 128,064,853 - eighteen times larger, and twenty-one times
before PR #171 moved it. Neither "593 days" nor its correction to "516 days"
was a number about anything. The same mistake was in the code: the site alarm
measured the payload tree, so it could not have fired until the site was already
six times past the cap ([../architecture/publishing/layout.md](../architecture/publishing/layout.md)).

**The site is `frontend/build/`, because that is the directory the Pages deploy
uploads.** Everything below divides its headroom by its own growth.

| Quantity | Bytes | What it means |
| --- | ---: | --- |
| The cap (Rule #2) | 1,073,741,824 | 1 GiB. Past it the site is outside what Pages allows. |
| The site, 2026-08-27 | 128,064,853 | 11.9 percent of the cap used. |
| Headroom | 945,676,971 | What is left. |
| Growth, one published day | 16,641,956 +/- 1,294,368 | What each new day costs. |

`945,676,971 / 16,641,956 = 56.8` **published days**. Counting whole days from
2026-08-27 - a partial day is not a day, the convention the alarm arithmetic
below already uses - the site crosses 1 GB on about **2026-10-22**. At the edges
of the spread it is 52.7 and 61.6 days, so **2026-10-18 to 2026-10-27**. Round
those up instead of down and the window is 2026-10-19 to 2026-10-28; the
difference is a rounding convention, not a measurement.

**Before PR #171 it was 41 days and 2026-10-07.** That commit narrowed the
staged day payload: 146,696,452 bytes down to 128,064,853, and 22,200,123 down
to 16,641,956 bytes a published day. The size cut bought 0.8 of a day; the rate
cut bought the other 14.2. **The rate is what moves a cap date.** A one-off
saving buys a fraction of a day forever; a saving on what every future day costs
buys days that keep arriving.

**Measured on an node 24.12.0, 2026-08-27**, by
summing every file under `frontend/build/` after `npm run build`, over the six
committed days and 2,237 items. n=1 per arm. CI's own `du -sb build` on the same
commit agreed to 0.0006 percent, so a local build is a trustworthy stand-in for
the runner's.

**The per-day rate uses the three mature days only** - 731, 724 and 621 items.
The first three published days ran 4, 10 and 147 items; including them halves
the answer and mixes two regimes, because those days are what a corpus looks
like while it is starting rather than while it is running.

#### How fast the site actually fills (2026-09-06)

**The published site is 47.2 MB smaller than it was six published days ago,
while carrying 3,314 more items.** Differencing the two committed dates the way
this page's earlier rows were taken gives **-47,215,748 bytes**, which is 29.8
percent off the level it started at. That is a real saving and it is not a
growth rate: the day pages stopped inlining their payload between the two dates,
so the difference is dominated by a code change rather than by six days of news.

The same change, on one identical day measured in both builds: `build/2026-08-24/`
holds **16,376,153 bytes** at the earlier commit and **631,201** at the later
one - 25.9 times smaller for the same 731 items.

**So a fill rate needs one code and two corpora, not two dates.** Three builds
were taken. Toolchain: node v24.12.0.
Date: 2026-09-06. n=1 per arm - a byte count over a fixed tree has no spread, and
the spread that matters is on the rate and is given below.

| Arm | What it is | Bytes | Files | Items | Published days |
| --- | --- | ---: | ---: | ---: | ---: |
| E | `f75f42bc`, the 2026-08-31 tip | 158,567,231 | 380 | 3,485 | 10 |
| Aug | today's code, September removed | 96,235,704 | 440 | 4,086 | 11 |
| T | `40a96ef7`, the 2026-09-06 tip | 111,351,483 | 666 | 6,799 | 16 |

Arm Aug is arm T's code built against a copy of `frontend/public/` and `state/`
with every September day taken out - the digest days, the month's search-index
shard, the month's telemetry and ledger shards, and the 2,713 September rows of
the flat published ledger this project then held. September is cut whole because
every ledger here is
sharded by month, so a month boundary is the only cut that leaves each shard
either untouched or absent. **No day was cloned or synthesised**; both corpora
are real published days.

**Arm E is the control that proves the method.** The 2026-08-30 reading above is
147,986,756 bytes over 3,054 items; arm E is 158,567,231 over 3,485. The step
between them is **24,549 bytes an item**, against **24,378** measured
independently on 2026-08-29 over seven mature days - **0.7 percent apart**, from
a different tree state and a different method. A local build of an older commit
reproduces the committed record.

**The rate, at today's code.**

| Quantity | Value | Over |
| --- | ---: | --- |
| The whole site | **3,023,156 B a published day** | 5 days |
| The whole site | **5,572 B an item** | 2,713 items |
| The dated day pages - route plus staged payload | 11,335,261 B, 75.0 percent of it | 5 days |
| Everything undated | 3,780,518 B, 25.0 percent of it | 5 days |

**Two methods, 4.4 percent apart on the part both can see.** The first fits
`bytes = fixed + rate x items` over the thirteen mature per-date subtrees of the
arm T build alone - a partition of one tree, never reading arm Aug - and gets
**1,197,991 bytes a published day plus 1,785 an item**, with a root-mean-square
residual of 178,369 bytes a day, 8.5 percent of a mean day. Applied to the five
removed days and their 2,713 items it predicts **10,831,453** bytes against the
**11,335,261** the two builds measure. Either is inside the other by less than a
twentieth.

**A per-date method cannot see a quarter of the fill, and that is the finding.**
The 25.0 percent it misses is not day pages at all:

| Where | Bytes over 5 days | A published day | Driven by |
| --- | ---: | ---: | --- |
| `console/` | 2,539,469 | 507,894 | days and runs, out to `console.max_window_days` = 366 |
| `index/` - the search index | 1,501,352 | 300,270 | items, at 553 B each |
| `telemetry/` | 424,320 | 84,864 | rows |
| `archive/` | 1,026 | 205 | one day link a day |
| `index.html` and `__data.json` | -685,586 | -137,117 | not growth: the home page carries the newest day, and 2026-09-05 published 374 items where 2026-08-31 published 601 |

The home page swing is a level artefact rather than a rate. Removing it raises
the whole-site figure to 3,160,273 bytes a published day, 4.5 percent higher and
inside the residual above. The measured figure is the one recorded.

**The committed payload tree, measured separately, and it agrees with itself to
0.8 percent.** The tree under `frontend/public/digest/` is **22,830,395 bytes in
402 files** over the same 6,799 items and 16 days at `40a96ef7`.

| Method | Bytes an item | Bytes a published day |
| --- | ---: | ---: |
| Differencing two commits: 11,269,707 B at `f75f42bc` to 22,830,395 at `40a96ef7`, by summing git blob sizes | 3,488 | 1,926,781 |
| The runner's own `site_bytes`, median over the twelve mature day-to-day steps of the sixteen committed run manifests | 3,517 +/- 448 | 1,910,234 +/- 642,682 |

These two are independent in every input: a different machine (a GitHub-hosted
runner against this laptop), a different code path (`retention.measure` during
the run against `git ls-tree -l` afterwards), and a different arithmetic (a
dated level series against a two-endpoint difference). The last committed
`site_bytes`, 22,827,239, is 0.014 percent under the tree measured here, which is
the manifest the run wrote after it measured.

**The per-day figure carries a 34 percent spread and the per-item figure 12.7
percent, because a published day is 117 to 731 items.** The rate per item is the
one that holds still, which is why `site-weight` prints that one.

**The repository pack, differenced across the same two commits** (Rule #2's other
budget: the prune bounds the past, and nothing bounds a growing present). Each
figure is a fresh clone of one commit followed by `git gc --aggressive
--prune=now`, so it is a repacked size and not an accident of how the local
repository happened to be packed.

| What | 2026-08-31 `f75f42bc` | 2026-09-06 `40a96ef7` | A published day | An item |
| --- | ---: | ---: | ---: | ---: |
| One snapshot of the tree, no history | 35,697,900 B | 43,098,644 B | 1,233,457 B | 2,233 B |
| A full clone, with history | 41,399,433 B, 530 commits | 49,579,643 B, 818 commits | 1,363,368 B | 2,468 B |

**History costs 10.5 percent more than the tree it carries, so the prune reaches
an eighth of the problem.** Six published days added 7,400,744 bytes to the
working tree and 8,180,210 to a clone of it, so only the 779,466-byte difference
- 9.5 percent of the growth - is history that `prune.yml` can ever squash. On
the level it is the same story: 6,480,999 bytes of the 49,579,643-byte clone are
history, 13.1 percent. A clone today is 47.3 MiB against a site of 106.2, and it
grows at 45 percent of the site's rate.

**The runway, from the arm T level at the measured rate.**

| Quantity | Value |
| --- | ---: |
| The site now | 111,351,483 B, 106.19 MiB, **10.4 percent of the 1 GiB cap** |
| Published days to the 800 MiB alarm | **240.6** |
| Published days to the 1 GiB cap | **318.3** |
| The same, at the heaviest day on record (731 items, 3,258,604 B) | **223.3** and **295.3** |

**The layout change bought about 151 published days of alarm headroom.** The
2026-08-30 reading above printed 89.1 days to the alarm and 119.4 to the cap.
Both were correct for the tree they measured.

**`site-weight`'s printed runway is no longer the floor it is documented as.**
On the arm T tree it prints 277.6 published days to the alarm against the 240.6
measured here - **15.4 percent long**. It counts the right bytes: its 106.2 MB
and 6,799 items match the independent sum above exactly. Two recorded premises
in its arithmetic now point opposite ways and nearly cancel. Charging the fixed
directories to the items makes its per-item rate 16,378 bytes against a measured
5,572, which is 2.94 times too high; pricing a day at `run.safety_ceiling_per_run`
= 160 items against the 543 a published day the differenced interval actually ran
is 3.39 times too low. The second premise is the one already filed above as long
by the same kind of factor. It was left alone again here, because the measurement
found no defect in what it counts and the premise belongs to a decision about the
knob rather than to this row.

### Where the alarm fires, and what it buys

`retention.site_budget_mb` is the size at which a build logs a warning. It is an
alarm and not a gate: it fails no build and deletes nothing
([../concepts/config.md](../concepts/config.md)). The **cap** is the gate, and
they are different lines - see the design rationale in
[../architecture/publishing/layout.md](../architecture/publishing/layout.md).
This section is the only home for why the alarm sits where it does.

**Derived, not measured separately.** Days of warning is
`(1024 - alarm_mb) * 1024 / KB_per_day`, on the same binary megabyte the code
uses. Whole days, rounded down - a partial day is not a day of warning.

**The rate changed on 2026-08-27 and so did every number in this table.** It
used to be taken over the committed payload tree, which is not the thing the cap
bounds. The live rate is now **16,252 binary KB a published day** - the measured
16,641,956 bytes, rounded up - and it is nearly twice the fastest hypothetical
row the old table carried.

| Alarm point | Headroom | Days at the measured 16,252 KB/day | Days at the old PNG row (8,537) |
| --- | --- | ---: | ---: |
| 600 MB | 424 MB | 26 | 50 |
| 700 MB | 324 MB | 20 | 38 |
| **800 MB (shipped)** | **224 MB** | **14** | **26** |
| 900 MB | 124 MB | 7 | 14 |
| 1000 MB | 24 MB | 1 | 2 |
| 1023 MB | 1 MB | 0 | 0 |

**The target is 14 days, and the target is a judgement (Rule #10).** Nothing here
measures how long one maintainer takes to read one issue, so nothing here can
ground it. Two things around it are measured and bound the window rather than
set it: the pipeline runs five times a day, so the site is measured every four
hours and the alarm is never more than a few hours late, and the fix - a config
edit and a redeploy - costs about 25 minutes of CI. Every remaining day is
a person noticing. Fourteen days lets a maintainer be away for a week and still
have a week to act.

**The shipped 800 MB now clears the target by one tenth of a day, where the old
table said it cleared by 1.9x.** 224 MB buys 14.1 days at 16,252 KB/day. That is
a live gate rather than a comfortable one, and it is meant to read that way: the
next measurement that finds growth any faster fails
`test_the_alarm_buys_the_days_it_was_derived_to_buy` and forces the alarm point
to be re-derived here before it can be changed there.

**At the fast edge of the spread the 800 MB point buys 13 days and misses the
target.** 17,516 KB a day - the measured rate plus one spread - leaves 13.1 whole
days. **Recorded, not fixed.** Moving the alarm point is its own decision with
its own derivation, and it needs a rate measured over more than three days
before anybody moves a number on it. What this row does is make the number
honest; picking a new one is the next row's work.

**Why the alarm point cannot be checked by size alone.** A test that only asks
whether the alarm sits below 1,024 MB passes at 1,023 MB, which is the last row
of the table and zero days of warning. `backend/tests/test_retention.py` pins the
days instead, against the rate above.

## The month search index, as written

The section above sized a shape nobody had built. This one measures the file
that now exists: `frontend/public/assist/index/2026-08.json` and its sibling
`2026-08.bin`, written by `assemble.rebuild_search_index`.

Toolchain: CPython 3.12.12.
Date: 2026-08-26. Corpus: the six committed days at commit `d0fd926` -
**2,237 items, 2,235 of which carry a vector**. Method: rebuild the shard from
the committed day payloads, then measure the bytes on disk with the same
`gzipped` helper `backend/utilities/index_sizing.py` uses, so both sections are
on one unit. `gzip -5` is what the Pages edge serves; `gzip -9` is the unit
every page-weight number elsewhere on this page uses.

**The sha is part of the measurement.** The scheduled pipeline rewrites a day
and pushes it, so a byte count against `frontend/public/` is stale within the
hour. These numbers were taken again after the last merge of `origin/main`, and
they moved: the same run at `e4affe6` had 2,121 items and a 106,365-byte index.
The per-entry rate barely moved with it, 50.15 to 50.03, which is the useful
part.

### The bijection holds

Deterministic file arithmetic, so the spread is zero and n=1.

| Quantity | Count |
| --- | ---: |
| Committed items in 2026-08 | 2,237 |
| Entries in the index | **2,237** |
| Entries carrying a byte offset | 2,235 |
| Entries carrying an explicit null | 2 |
| Vectors in the day payloads | 2,235 |
| Offsets whose bytes were dequantised and compared | 2,235 |
| **Mismatches** | **0** |

Every offset's 384 bytes dequantise to the same unit vector `from_base64` gives
for that item's committed base64. The `.bin` is exactly 858,240 bytes, which is
2,235 times 384 with nothing over. Rebuilding the shard twice produces
byte-identical `.json` and `.bin`, which is the guarantee that lets there be one
code path instead of an incremental one and a repair one.

### What it costs on the wire

| File | Raw | `gzip -5` | `gzip -9` | Per entry at `gzip -5` |
| --- | ---: | ---: | ---: | ---: |
| `2026-08.json` | 378,869 | **111,927** (109.3 KB) | 109,196 | **50.03** |
| `2026-08.bin` | 858,240 | **558,278** (545 KB) | 558,278 | 249.79 |

**An entry costs 50.03 gzipped bytes, 10 percent more than the 45.5 the shape
study priced.** The study used one-letter keys and had no vector field; a real
entry spells `date`, `item_id`, `title`, `vertical` and `vector`. gzip absorbs
most of the repetition - the raw difference is 169.36 against 133.31, which is
27 percent - so the honest reading is that real key names cost about a third of
what they look like they cost.

**The vector file confirms the earlier number to two decimal places**: 249.79
here against 249.82 there, and `gzip -5` and `gzip -9` are the same byte count
because quantised embedding bytes are close enough to random that the extra
search finds nothing.

Projected onto a 30-day month at the two rates
([Sizing the archive index](../archive/measurements-2026-08.md#sizing-the-archive-index) has where the rates come
from):

| Rate | Items a month | Browse index | Vector file |
| --- | ---: | ---: | ---: |
| observed, 353.5 items a day | 10,605 | **518 KB** | 2.53 MB |
| structural ceiling, 800 a day | 24,000 | **1.15 MB** | 5.72 MB |

Both sit under the triggers written down in
[../architecture/publishing/layout.md](../architecture/publishing/layout.md#when-to-reconsider-the-month):
1.5 MB for the browse index and 8 MB for the vectors.

### What the summary would have cost

The question was whether a search result could render straight out of the index
instead of fetching the day payload it names. Same 2,237 entries, same
serializer, with `summary` added to each:

| Shape | Raw | `gzip -5` | Per entry | A month, observed | A month, at the ceiling |
| --- | ---: | ---: | ---: | ---: | ---: |
| As shipped | 378,869 | 111,927 | 50.03 | 518 KB | 1.15 MB |
| With the summary | 1,976,870 | 710,301 | **317.52** | **3.21 MB** | **7.27 MB** |

**Carrying the summary is 6.35 times the entry**, and it puts a month past the
1.5 MB trigger at the observed rate, never mind the ceiling. It also charges
every visitor who only browses the full text of every item in the month. Ten
results spanning ten days cost at most ten day-payload fetches instead, and a
day already open is reused.

### What the rebuild costs

Answer 4 of the plan made the rebuild the only path, so the cost is paid on
every assemble run. Seven repeats per row on a shared developer machine with
four other agents building and testing on it, so take the fastest as the
uncontended cost and the median as what a busy machine does to it.

| Days | Items | Fastest | Median | Fastest, microseconds an item |
| ---: | ---: | ---: | ---: | ---: |
| 1 | 4 | 6.4 ms | 7.9 ms | 1,600 |
| 2 | 14 | 6.8 ms | 8.3 ms | 489 |
| 3 | 161 | 12.5 ms | 14.6 ms | 77.5 |
| 4 | 892 | 42.8 ms | 47.0 ms | 48.0 |
| 5 | 1,616 | 68.7 ms | 92.5 ms | 42.5 |
| 6 | 2,237 | **122.0 ms** | 224.2 ms | 54.5 |

A separate timed run of the whole month on the same corpus got **88 ms fastest,
112 ms median, 142 ms slowest** over seven repeats, which is 39.3 microseconds
an item. Take the two runs together: **about 40 to 55 microseconds an item once
past a few hundred**, holding across a 2.5x range of month size. The tiny days
are fixed per-file cost, not a different rate.

**So a month at the structural ceiling - 24,000 items - projects to about one
second, and to 1.3 seconds on the contended readings.** That is a projection
from a measured rate, not a measurement.

Against the assemble job's 20-minute timeout that is **0.1 percent of the
budget** (Rule #2). Five runs a day spend about five seconds a day on it at the
ceiling. The payloads it reads are the same ones assemble already opens, so the
cost is a second parse rather than a second download.

## How fast archive search slides under a frozen label set

The 60-query label set was pooled on 2026-08-26 and nothing has been added to it
since. Every published day adds right answers no labeller judged, and the metric
counts each of them as a wrong answer, so `recall@10` falls for a reason that is
not a ranking regression. This is how fast.

Toolchain: CPython 3.14.2,
`onnxruntime` 1.29.0, alone on the machine. Date: 2026-08-31, at commit
`fb6a65a`. Method: one forward pass per query through the committed encoder,
shared by every row; then `retrieval.evaluate` over the committed day payloads
restricted to the days up to and including each date. Same queries, same labels,
same ranking code, same run - only the corpus moves. 80.2 s of wall clock for
the whole table plus the four decomposition arms.

| Archive through | Items | Carrying a vector | reachable recall@10 | +/- se |
| --- | ---: | ---: | ---: | ---: |
| 2026-08-21 | 4 | 4 | 1.00000 | 0.00000 |
| 2026-08-22 | 14 | 14 | 1.00000 | 0.00000 |
| 2026-08-23 | 161 | 161 | 0.96970 | 0.03030 |
| 2026-08-24 | 892 | 891 | 0.89200 | 0.02250 |
| 2026-08-25 | 1,616 | 1,614 | 0.80254 | 0.03093 |
| 2026-08-26 | 2,237 | 2,235 | **0.75571** | 0.03731 |
| 2026-08-27 | 2,571 | 2,569 | 0.73583 | 0.03839 |
| 2026-08-28 | 2,688 | 2,686 | 0.73398 | 0.03858 |
| 2026-08-29 | 3,054 | 3,052 | 0.71126 | 0.03969 |
| 2026-08-30 | 3,485 | 3,483 | 0.69163 | 0.04092 |
| 2026-08-31 | 3,596 | 3,594 | **0.68978** | 0.04124 |

**The 2026-08-26 row is the check that this series is sound.** It reads 0.75571
over 2,237 items, and the measurement recorded on that corpus in
[../concepts/evaluation.md](../concepts/evaluation.md) reads 0.756 over 2,237
items. A series taken today reproduces a number taken five days ago on the same
corpus, which is what a deterministic instrument is supposed to do.

**The first five rows are not the rate.** An archive of 4 items scores 1.000
because there is nothing for a right answer to lose a slot to. The slope only
means something once the label set is closed, from 2026-08-27 on:

| Fit | Slope | Points |
| --- | ---: | ---: |
| Whole series, per published day | -0.03584 | 11 |
| Whole series, per published item | -0.00008912 | 11 |
| **From 2026-08-27, per published day** | **-0.01345** | 5 |
| **From 2026-08-27, per published item** | **-0.00004793** | 5 |

**Read the per-item slope, and convert.** A published day is not a fixed size -
the eleven days range from 4 items to 731 - so the per-day figure carries
whatever the last five days happened to publish. Those five published 1,359
items, 272 a day; the eleven-day archive averages 327 a day. **So 0.01 of recall
costs about 209 published items, which is between 0.6 and 0.8 of a published
day.**

That is what sets the expiry on `assist.recall_min`. The bar is 0.61 against a
reading of 0.690, which is 0.080 of room, which is **1,660 published items - six
days at the rate the last five ran, five at the archive's mean.**

## The published ledger

**Re-measured 2026-08-26** off the runner (CPython
3.12.12), over the ledger as `831fdac0ec36b3c7d38dd7cd26e3a8d2ba2a4755` holds
it, immediately before and after
`backend/utilities/migrate_published_ledger.py` rewrote the file. This is
deterministic file arithmetic, so the spread is zero and the hardware matters
only for the in-memory figure at the end. It supersedes a 2026-08-25 reading of
1,449 rows at 214.9 B, which was taken before the column below was dropped.

**Re-run 2026-08-27 against `origin/main` at `1eacb45`, and every number came
back the same.** That commit holds the same 476,809-byte file as
`831fdac0ec36b3c7d38dd7cd26e3a8d2ba2a4755`, so no run published between the two
and there was nothing new to weigh. A figure taken off this file is otherwise
stale within the hour, because CI commits it several times a day. Re-run the
migration against whatever `origin/main` holds before trusting the table.

The row lost `canonical_url` in that commit. Nothing on the read path opened it,
and the address it carried is still recoverable - the join, and what it cost, is
[../architecture/sources/freshness.md](../architecture/sources/freshness.md).

| Quantity | Before | After | Method |
| --- | --- | --- | --- |
| Rows | 2,213 | 2,213 | `csv.DictReader` |
| Bytes | 476,809 (465.6 KB) | **244,910 (239.2 KB)** | `stat` |
| Mean row | 215.5 B | **110.7 B** | bytes / rows |
| `version` share | 37,629 B, 7.9% | 37,629 B, 15.4% | field-width sum, one separator per cell |
| `url_key` share | 143,853 B, 30.2% | 143,853 B, 58.7% | same |
| **`canonical_url` share** | **231,899 B, 48.6%** | **gone** | same |
| `published_on` share | 24,356 B, 5.1% | 24,356 B, 9.9% | same |
| `item_id` share | 39,072 B, 8.2% | 39,072 B, 16.0% | same |

The rewrite removed 231,899 bytes - 48.6 percent of the file, and 104.8 bytes
off every row. Nothing else moved: the same 2,213 rows carry the same 2,213
`(url_key, published_on)` pairs, in the same order, and those two cells are the
whole of what the skip read opens.

Projected forward at the two mean rows above:

| Rows a day | A year of rows | Was | Now | Saved |
| --- | --- | --- | --- | --- |
| 553, the ledger's own rate over the four days it holds | 201,936 | 43.5 MB | **22.3 MB** | 21.2 MB |
| 1,000, the structural ceiling below | 365,000 | 78.6 MB | **40.4 MB** | 38.2 MB |
| 200, one run's worth | 73,000 | 15.7 MB | 8.1 MB | 7.6 MB |

The ledger spans 2026-08-23 to 2026-08-26 and records only what a run
introduced, so 2,213 over four days is the real publish rate rather than a count
of what the days carry. It reads slightly low: the last of those four days was
still running when the file was measured. The ceiling row is the one to design
against.

**What it costs to read.** `ledger.load_published` parses the whole file into a
list of dicts and then folds it into one map. `tracemalloc` peak over the
narrowed ledger is **1,102,193 B**, 498.1 B a row, for 2,213 rows. At the
365,000-row structural ceiling that is **182 MB**, or 1.1 percent of the
runner's 16 GB (Rule #2). The 2026-08-25 reading was 716 B a row, so the
narrowing took about 30 percent off the read - but that reading was on CPython
3.14 and this one is on 3.12.12, so the interpreter is not held constant and the
two are not a clean before-and-after. The conclusion is the same either way: a
year of this file is a rounding error against 16 GB.

The plan stage is also the job that loads no model, so this allocation never
sits beside 4.68 GiB of weights.

**The address survived the column.** Every one of the 2,213 committed rows joins
to a `source_url`: `published_on` picks the day directory and `item_id` picks
the item inside `digest.json`, with no absent day and no absent item (measured
2026-08-26 over the whole file). What the column bought was a grep by address,
and that is what was given up - see
[../architecture/sources/freshness.md](../architecture/sources/freshness.md).

## What a reader route costs on a real day (2026-09-02)

What a browser fetches before a reader does anything: the prerendered document, plus every `_app/immutable` asset the document itself names. gzip -9, which is what a static host serves. Taken on node 24.12.0, over the thirteen committed days to 2026-09-02. The heaviest instance of each route class stands for the class, which is how the bundle gate reads the same tree.

| route | document | JavaScript | CSS | first load | assets | heaviest instance |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| `/` | 73,796 | 57,685 | 9,329 | **140,810** | 30 | the newest day, 128 stories inline |
| `/<date>/` | 23,388 | 58,249 | 9,282 | **90,919** | 31 | `2026-09-01`, 627 stories, 20 seeded |
| `/<date>/<topic>/` | 17,725 | 58,354 | 9,282 | **85,361** | 31 | `2026-08-30/energy` |
| `/archive/` | 5,024 | 59,288 | 8,707 | **73,019** | 28 | thirteen days |
| `/evals/` | 3,113 | 43,272 | 6,806 | **53,191** | 23 | the signpost to the console |
| `/404` | 1,604 | 42,397 | 6,806 | **50,807** | 21 | the fallback shell |

**The spread is the build's own noise and nothing else.** Two builds of one unchanged tree, back to back in the same worktree, moved each route's first load by **10 to 19 bytes** - `/` +19, `/<date>/` +18, `/<date>/<topic>/` +16, `/archive/` +12, `/evals/` +10, `/404` +10. Every document moved by 1 byte or less; all of it is JavaScript. That is `kit.version.name` defaulting to `Date.now`, which lands in the content hash of every chunk filename ([agent-notes/gates-and-builds.md](agent-notes/gates-and-builds.md#running-the-gates)). The version was deliberately **not** pinned to take these two arms: the pin stops every page hydrating when `BUILD_VERSION` is unset, which costs more than the noise it removes. 64 bytes remains the working tolerance, and 19 is well inside it.

**The home page is proportional to the day and a dated route is not, and one publish measured both.** The same instrument ran a few hours earlier over the twelve days to 2026-09-01, when the newest day was that day's **627** stories rather than 2026-09-02's 128:

| route | document then, 627 stories | document now, 128 stories |
| --- | ---: | ---: |
| `/` | 310,901 | 73,796 |
| `/<date>/` (`2026-09-01`, unchanged content) | 23,389 | 23,388 |

`/` fell by **76.3 percent** on a day that published one fifth as much, because it is the one reading route that still puts a whole day in its document. `/<date>/` for the same 627-story day moved 1 byte, because its document carries the seed of fifteen plus the day's five leads and the browser fetches the rest. **At 627 stories the dated route was 4.2 times lighter than the home page on identical content**, and the gap grows with every story a day publishes. `/archive/` grew 16 bytes across the two, which is the day link a publish adds - the one route here whose growth is priced and capped.

**`/` is uncapped on purpose and this is what that costs.** The bundle gate caps `/404`, `/archive/`, `/evals/` and the three console routes, and deliberately caps neither `/` nor a dated route, because the only way under such a ceiling is to publish fewer items ([../how-to/run-the-gates.md](../how-to/run-the-gates.md)). What holds those two is the marker count in `frontend/tests/payload-weight.spec.ts`. This table is the level that count has no opinion about, and it has a date on it.

## See also

- [measurements.md](measurements.md) - the producer half: the model, the runner, memory and throughput.
- [../archive/measurements-2026-08.md](../archive/measurements-2026-08.md) - finished experiments and superseded levels.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - the published-size arithmetic these numbers feed.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - the reader's surface these figures were taken on.
- [../how-to/run-the-gates.md](../how-to/run-the-gates.md) - the bundle gate that reads every ceiling here.
- [../concepts/config.md](../concepts/config.md) - the knobs these numbers set.
- [../../CLAUDE.md](../../CLAUDE.md) - Rule #2 (the runner is the architecture) and #10 (measured, not estimated).
