# Known defects

**Last Updated**: 2026-09-13

**Two defects are open and neither closes on more of the same code.** Defect 2
needed three repairs before a person could label anything, and all three
shipped. The owner settled the counting rule on 2026-08-27, which took the
draw from 32 of 60 to 60 of 60. What is left is **60 human labels** and eight
more run-days at one scorer, and neither is code. Defect 18 is the opposite
shape: the code now works and the measurement it produces still cannot fire, so
what it needs is a ruling on which instrument to keep. **This file cannot be
deleted by writing more of it.**

Defects 15, 16 and 17 closed on 2026-08-27. Defects 19 and 20 were filed later,
on 2026-09-12, by two rows that found them and declined to widen into them. Both
closed on 2026-09-13. Defect 20 got its ruling and the ruling moved the fix: the
fingerprint was right and the producer was wrong. Defect 21 came from plan 24,
which ruled it a row on 2026-09-12 and never cut one; it closed on 2026-09-13.
Defect 22 was reported from the published days on 2026-09-14 and closed the same
day; like defect 20, the symptom pointed at a number and the fault was upstream
of it.

Closed rows are removed after checking their current production code, regression
tests and canonical docs. Git history holds their execution record; the living
docs hold the rules they established.

Non-authoritative working material (CLAUDE.md section 3). Nothing here is a
decision. Current project behaviour belongs in `docs/` (Guardrail #4).

| # | Defect | Level | Status |
| --- | --- | --- | --- |
| 2 | The faithfulness thresholds have no labelled error rate | 5 | **OPEN - queue repaired, counting rule settled; 0 of 60 labels; 2 of 10 run-days** |
| 15 | A stage that did not run and a stage that took no time arrive as the same zero | 3 | CLOSED 2026-08-27 (PR #180) |
| 16 | The truncation-gap detector has never been fed, and the run pays twice for the answer | 5 | CLOSED 2026-08-27 |
| 17 | Two different word counters share one string and read as truncation | 5 | CLOSED 2026-08-27 |
| 18 | The truncation flag still cannot fire, now for a different reason | 5 | **OPEN - not measurable without the scorer weights** |
| 19 | A summarize call that failed on its reply reports no cost at all | 2 | CLOSED 2026-09-13 (PR #657) |
| 20 | The `publishing` group dirties a file the build fingerprint hashes, so it can never certify its own build | 2 | CLOSED 2026-09-13 (PR #660) |
| 21 | A test walked every published telemetry shard, and it was the only thing reading them back | 2 | CLOSED 2026-09-13 |
| 22 | The same story publishes several times in one day, and each copy says only one source carried it | 3 | CLOSED 2026-09-14 |

## 22 - The same story publishes several times in one day (CLOSED 2026-09-14)

On 2026-08-25 Dolly Parton's death ran five times from five feeds. On 2026-09-03
one acquisition ran five times under two spellings of its price. Across the 25
committed days, 42 groups of items from **different** sources published under one
headline and the pass grouped 15 of them.

**The threshold was not the fault.** `collapse_same_story` scores vectors built
by `embed.text_for` over `f"{title}. {summary}"`, and the summary is our own
model's prose about one article - roughly nineteen words in twenty of the
encoded text. Two outlets writing the same story give our summariser two
different articles, so the comparison is dominated by the one part guaranteed to
differ. The 53 cross-source pairs whose headlines match score a median of
**0.9177** against a floor of **0.94**, and the pair a person has already marked
as two stories sits at **0.9317** - above that median. No floor separates the two
populations, so lowering one would have traded this defect for a worse one.

**What shipped is a second joiner, not a new number.** Two items are also the
same story when their reduced headlines are identical - threshold-free, still
vector-gated, still across sources, still all-pairs. `assemble.duplicate_similarity_min`
is untouched at 0.94. Replayed through the shipped pass over every committed day:
**27 of the 42 were apart before, 2 after**. Digits survive the reduction, which
leaves the `$12.9` / `$12.93` / `$13` spellings of that acquisition as separate
groups; Andre ruled the stop there on 2026-09-14 and the reasoning, the two
headline classes that would break the rule, and the guard measurements that say
neither fires today are in
[../docs/architecture/publishing/layout.md](../docs/architecture/publishing/layout.md).

**What is still unmeasured is recall** - every number above starts from pairs
found *by* matching headlines, so none of them says anything about same-story
pairs whose headlines differ. Andre named the measurement that would settle it
and it is not code: a blind hand-label of same-day cross-source pairs drawn
without consulting titles.

## 21 - A test walked every published telemetry shard (CLOSED 2026-09-13)

`backend/tests/test_publish_telemetry.py` copied **every** file under
`frontend/public/telemetry/` and ran the migration over all of them, on every
run. Two files and 1,516,467 bytes on 2026-09-13, gaining one file a month.
`CLAUDE.md` section 13 refuses a test that walks a collection the pipeline
appends to.

**It could not simply be bounded, which is why it survived two plans.** The loop
was the only thing in the build that opened every published telemetry file and
checked it still loaded through its contract: `cli._console_payload_faults`
named six producers and `publish_telemetry` was not one of them. Deleting the
loop would have traded a broken rule for a coverage hole.

So the check moved to the producer's own gate, which is where section 13 says
data hygiene belongs, and the test was rebuilt on a projection it writes itself -
carrying an empty month and a one-row month, neither of which the committed
archive has ever produced. The gate's own docstring now names the one directory
whose `keep_months` is declared and not enforced, because a sentence that said
all seven were bounded would have been wrong.

Found by plan 24 row #4 on 2026-09-12 and ruled a row rather than a gap by
Fowler the same day. No row was cut, and
[`20260910-24-day-sharded-ledgers-plan.md`](20260910-24-day-sharded-ledgers-plan.md)
closed with it outstanding.

## 18 - The truncation flag still cannot fire, now for a different reason (OPEN)

Row 16 fed the scorer the real pre-cap body, so `hhem_full` now reads a
different text from `hhem`. The flag built on the gap between them still cannot
fire, and the reason is the aggregation rather than the input.

`score_over_chunks` takes the **maximum** over 900-word windows at a step of
750. The seen text is a prefix of the full text, so the full pass sees the same
first windows, one of them lengthened, plus every window after the cut. A
maximum over a superset cannot be smaller than a maximum over the subset. So
`hhem_full >= hhem` in almost every case, `hhem_delta = hhem - hhem_full` is
zero or negative, and `truncation_flagged = delta > evaluation.truncation_gap_max`
never clears a positive threshold.

Two consequences follow, and only the first is certain:

- The run pays a second cross-encoder pass on every truncated item for a number
  that is negative by construction. At the measured 6.1 percent truncation rate
  that is small, and it is not the argument for changing anything.
- The console's "Article read only in part" counter reads `truncation_flagged`.
  It said **1** when the committed ledger held **157** rows sitting on the cap.
  `Article.truncated` is already persisted and answers that question exactly.

**Why this is not closed by measurement.** No test may fetch the HHEM weights
(Guardrail #7), so the monotonicity claim above is an argument about the aggregation
rather than an observation of the scorer. Confirming it needs a run with the
weights present, and the honest first step is to look at `hhem_delta` on the
rows written since row 16 shipped rather than to reason further.

**The decision, when the evidence exists.** Either the second pass earns its
place under a different comparison, or `truncation_flagged` reads
`Article.truncated`, `evaluation.truncation_gap_max` is deleted as a knob
nothing reads, and the console counter is pointed at the flag that moved. The
second changes what a committed column means and what an operator page reports,
so it is Level 5 and needs an owner ruling before any of it is written.

## 2 - The faithfulness thresholds have no labelled error rate (OPEN)

No current threshold has a measured human error rate. Re-cutting the bands is a
Level-5 reader-facing decision, so no threshold moves until the evidence exists
(Guardrail #10).

### The three queue repairs shipped on 2026-08-27

A person could not use the queue. All three gaps are now closed.

- **The labeller was never shown the article.** `state/scores.csv` carries no
  summary text and no source text, so the CLI printed a fallback string on every
  row. The run now writes the exact premise the scorer read, plus the summary,
  to `backend/var/evidence/<date>/`, and the work job uploads it. The CLI shows
  both, and refuses any row whose text does not match its recorded digest. A row
  scored before that column existed is marked not labellable rather than guessed
  at. PR #178 added the `source_digest` column; PR #182 added the package.
- **The draw leaked the score stratum through its order.** `draw()` returned
  rows decile block by decile block, so a labeller working down the queue was
  handed the confidence gradient in order. It now returns one global `label_id`
  sort. Measured over the 38 rows at `draw_id=d1`: 9 runs of equal decile
  before, 28 after. PR #179.
- **A draw could silently mix pipelines.** `eligible()` filtered on
  `scorer_version` only, and warned about mixed fingerprints instead of refusing
  them. Both halves are now required. An empty pool exits non-zero and prints
  every `(scorer_version, pipeline_fingerprint)` pair in the ledger with its row
  count and date range. PR #179.

Measurement corrected one design note. A global hash shuffle removes the
ordering leak but **does not balance a prefix**. Over the same 38 rows the first
ten deciles run 9, 9, 8, 9, 9, 9, 5, 8, 9, 7. Balance holds in expectation, not
per draw, so stopping early gives a roughly balanced sample rather than a
guaranteed one.

### What is left is not engineering

**0 of 60 labels.** No `state/labels.csv` is committed.

**2 of 10 run-days.** The owner settled the counting rule on 2026-08-27: count
run-days at one `scorer_version`, and carry `pipeline_fingerprint` as a reported
stratum rather than a disqualification. The pair rule it replaced was
unreachable - the stamp digests seventeen inputs, so a reworded prompt or a
sanitizer fix reset the count, and no pair ever held for more than three
consecutive run-days. Measured effect on the same ledger: the drawable sample
went from 32 of 60 with seven deciles short to **60 of 60**, over 450 eligible
rows at `hhem-2.1-open@8e4a2e6e`. What it gives up is stated wherever a result
prints: a rate over a pooled draw is a prior with wide bounds, and a stratum
under `evaluation.label_min_stratum_rows` may not move a threshold. The rule,
the rejected freeze and the measured reset rate are stated once, in
[`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md#design-rationale).

**The evidence packages are not on this machine.** `label_queue.py` reports
`labellable 0 of 60`: 34 rows have no package here, and 26 predate the
`source_digest` column and can never be proved against their article. The run
writes packages to `backend/var/evidence/<date>/` and the `work` job uploads
them, so a labeller downloads that artifact before starting. Nothing is broken;
the evidence simply lives where the run put it.

Remaining steps, in order:

1. Download the evidence artifact for the run-days in the draw.
2. Draw and label 60 rows, six per HHEM decile. Keep the score, band,
   counterweights, model identity, fingerprint and running tally hidden.
3. Collect the remaining run-days at `hhem-2.1-open@8e4a2e6e`.
4. Re-test the cuts by stratum. Move a threshold only when the labels support
   the new cut, and never on a stratum under the floor.

The canonical measurement contract lives in
[`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md).

## What closed, and where it went

| # | Defect | Fix |
| --- | --- | --- |
| 15 | `median()` returned `0` for an empty sample, so all four stage timings lost the difference between "not measured" and "measured as zero" before the chart saw them. `StageTimings.svelte` reconstructed absence from the value, which is a repair on top of a lost fact. | 2026-08-27, PR #180. `median()` returns `null`, `StageTimingDay` carries `number | null`, and the console reads the null directly. Both a missing timing and a real zero are pinned in `frontend/tests/console.spec.ts`. Recorded in [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md). |
| 16 | `dual_score` exists to tell "the model invented something" from "the model faithfully summarized the half we gave it", and its only production caller handed it `article.text` twice. Measured over the whole committed ledger: `hhem_delta` exactly 0.0 on **2,232 of 2,232 rows**. The run also paid for the duplicate pass - about 2 s an item, 21 to 24 minutes of runner wall-clock a day. | 2026-08-27. `extract.to_article_with_source` returns the payload beside the untruncated body; the body stays in the process that extracted it and is never persisted or republished (Guardrail #1). The work stage scores against it, and `dual_score` scores identical texts once. About 97 percent of items are never cut, so most now pay one pass instead of two. Stamped `2026-08-27T20:30` with the read-side rule: a row older than that stamp recorded two scores of one text, so its zero means "never measured". Recorded in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). |
| 17 | `source_word_count` came from `metrics.word_count(full_text)` and `source_seen_word_count` from `article.word_count` - the **same post-cap string** through two different counters. Read as a truncation signal the pair said 87 percent of items were truncated; the real rate is 6.3 percent. The proof is the impossible direction: `source_seen_word_count` was larger on **590 of 2,232 rows**, which cannot happen when one string is a cut of the other. | 2026-08-27. The column is `Article.source_word_count`, the pre-cap count the payload already carried, so one counter produces both numbers and the difference between them is the cut. An article written before that field existed reports its post-cap count rather than inventing a source length. Stamped `2026-08-27T20:00`. Proved by a test that builds its article through the real extractor, so the pair is a genuine cut. Recorded in [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). |
| 19 | `summarize._failed` never received the `Completion`, so a reply the stage refused wrote a `Summary` whose five cost cells were the model's defaults of zero - and `telemetry`'s failed-summarize branch then passed the three stage timings and none of the five model cells, so the census row carried blanks. `reconcile_prefill.pool_ledger` skips a blank rather than pooling it, so the model server counted those requests and the ledger counted none of them. Measured on the committed ledger 2026-09-13: **93 of 93 failed summarize rows carried no cost at all**, and on run `2026-09-12-34717684802` one refused reply is the whole of that run's disagreement with the server - 72,739 tokens over 3,918.41 s against 73,616 over 3,936.07 s, **0.746 percent apart, one article consuming 15 percent of the 5 percent tolerance.** The two neighbouring runs carry no refused reply and match the server to the token, at 0.051 and 0.070 percent. | 2026-09-13. `_failed` takes the `Completion` and records a `CallCost` from it at all six sites in `to_summary` that hold one; the two that do not - the article never extracted, the model never answered - leave the slot empty, because that null is the real zero and is what a pooled read skips rather than averages in. The census row carries the same five cells and call slots a passing row does. No lenient path: the sum rule on `Summary` and on `ItemHealthRow` binds a failed row exactly as it binds an ok one. Both contracts stamped `2026-09-13T14:20` with the read-side rule - on a failed payload written earlier, a zero or an empty cost cell means never recorded, not free. Recorded in [`docs/architecture/summarize/throughput.md`](../docs/architecture/summarize/throughput.md) and [`docs/architecture/sources/item-health.md`](../docs/architecture/sources/item-health.md). The same sweep found the symptom on the flagged two-call path, in a different function; Fowler refused the widening and it is plan 11 row #3h. |
| 20 | Filed as a fingerprint problem: `npm run test:changed -- --group publishing` passed 72 of 72 tests and exited 1 with `The canary build has stale inputs`, because `frontend/tests/malformed-day.spec.ts` ran `idhazh validate-days` with `--digest-root` at a scratch tree and no `--state-root`, so receipts about those scratch trees landed in the tracked `state/day-validations.csv` that `inputFingerprint` hashes. **Both candidate fixes in the original filing were built on a wrong premise.** The message comes from `assertBuild`, which hashes the **build** fingerprint, so excluding `state/` from the **checks** fingerprint would not have changed the failure at all; and `validate-days` already had the flag the second one proposed to add. The exclusion list has no stated rule but is not arbitrary - read against the code it holds exactly two kinds, a tree the tooling itself writes and prose no program reads, and a ledger the console prerenders from is neither. **The real defect was a correctness one and the dirty file was its shadow.** A receipt records a payload's LENGTH and a day is settled on that length, never on a re-read, so the committed receipts settle a same-length day in any other tree without opening it: measured 2026-09-13, a copy of the newest committed day with `"items"` overwritten by `"itemz"`, one byte for one byte, passed against the committed store reporting `0 of them opened`, and was refused against an empty one. The spec's `unbroken` arm - which exists because a guard that only ever refuses proves nothing - had stopped proving anything. | 2026-09-13. Neither candidate: the fingerprint was telling the truth and the producer was fixed (Fowler). `validate-days` refuses a `--digest-root` that is not the committed tree unless `--state-root` is named too, so the pairing is enforced rather than remembered, and the spec names a scratch store beside each scratch tree. `inputFingerprint`'s list is unchanged and now carries the rule it was always following, in writing, including why a `state/` ledger stays in. Caught next time by an argument-level test in `backend/tests/test_contracts.py` - one fabricated day under `tmp_path`, no archive walk, nothing to age out - and by `changedInputNote`, which makes both stale-input failures name the paths that moved instead of saying only that something did. Recorded in [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) and [`docs/reference/agent-notes/gates-and-builds.md`](../docs/reference/agent-notes/gates-and-builds.md). Base-tree re-measurement, 2026-09-13: the reported symptom no longer reproduces - 72 of 72 pass and the launcher exits **0** in 269.3 s - because every committed day now has a current receipt, which makes the dirty file latent and the silent skip live. |

## See also

- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the label and calibration contract.
- [`docs/architecture/publishing/frontend.md`](../docs/architecture/publishing/frontend.md) - the console timing surface defect 15 repaired.
- [`docs/concepts/growing-reads.md`](../docs/concepts/growing-reads.md) - the validation receipt defect 20 pinned to the tree it is about.
- [`docs/reference/agent-notes/gates-and-builds.md`](../docs/reference/agent-notes/gates-and-builds.md) - what a stale-input failure says now that defect 20 is closed.
- [`docs/how-to/distill-a-plan.md`](../docs/how-to/distill-a-plan.md) - how closed rows leave this file.
