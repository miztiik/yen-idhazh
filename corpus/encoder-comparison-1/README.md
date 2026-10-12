# Encoder comparison 1

**Built**: 2026-10-08. **Judged comparison updated**: 2026-10-09 UTC.

A measurement, not a dataset. It answers one question for plan 63: of the
encoders that could run on this project's hardware, which one best tells two
summaries of the same event from two summaries of different events.

The current model-judged answer is
[`judgments/evaluation.json`](judgments/evaluation.json), summarized below.
`readings/encoders.md` retains the title-derived proxy and the encoding costs.
The proxy is a screen, not selection proof.

## Plain-English summary

Both Jina and EmbeddingGemma-2 finished encoding the same 10,675 summaries.
MiniLM and GTE-small reused their saved vectors. Each article was encoded once,
not once for every pair in which it appears.

All 935 pair rows are labeled: 365 same event, 547 different events and 23
uncertain. These are model-written decisions, not human-reviewed article labels.
The 935 rows involve 1,386 distinct articles; we did not label all 15,122 articles.

After removing repeated copies, conflicting decisions, uncertain pairs and
unavailable inputs, 723 distinct pairs remain. We used 178 to choose each
encoder's cutoff and kept 545 separate to measure the result. No article appears
in both sets.

GTE-small has the highest observed ranking score and the shortest recorded
encoding time. Gemma is close on ranking, but this test does not establish a
GTE/Gemma quality winner. Jina and Gemma have not shown a clear practical gain
over the owner's existing GTE-small and MiniLM candidates.

### What the numbers mean

- **Precision:** Of the pairs called "same event", how many really have that
  label? GTE-small found 86 matches; 81 were labeled same and five different:
  precision is 81 / 86 = 94.19%.
- **Recall:** Of all pairs labeled same, how many were found? GTE-small found
  81 of the 261 same-event pairs in the separate test set: recall is 31.03%.
- **Average precision (AP):** A summary of how clean the predicted matches stay
  as the cutoff is loosened to find more of them. Higher means a better ordering
  of same-event versus different-event pairs. AP 0.8954 is not 89.54% accuracy.
- **ROC AUC:** The chance a randomly chosen same-event pair gets a higher score
  than a randomly chosen different-event pair. 0.5 is chance-level; 1 is perfect
  ordering. It is not the fraction of correct decisions at one cutoff.

The precision and recall table uses a different cutoff for each encoder, chosen
only on the cutoff-setting set. The target was 95% precision there, not a promise
of 95% on the separate test or in production. Gemma's observed 100% precision
means zero wrong matches among just 23 predicted matches; it still missed 238
same-event pairs. Recorded times came from separate runner hosts.

## Why this exists

The pipeline decides two articles report one story when their summaries sit at
cosine 0.94 or above inside 36 hours. Over the 45 published days that grouped
212 articles out of 15,122, which is **1.4 percent**. Everything downstream of
that decision depends on the numbers an encoder produces, and nobody had
measured which encoder produces the best ones for this job.

**This is not the search encoder.** `backend/idhazh/embed.py` runs a quantized
`all-MiniLM-L6-v2` whose vectors a reader's browser compares against a query it
embeds in the tab. That encoder is sized by what a visitor downloads - 23 MB -
and the runner and the browser deliberately load the same file so the two
agree. The grouping encoder never reaches a browser, so its size is free and
its choice is open. Changing one does not change the other.

## What it is

| | |
| --- | --- |
| Measured by | `backend/utilities/compare_summary_encoders.py`, run by `.github/workflows/encoder-comparison.yml` |
| Hardware | A GitHub `ubuntu-latest` runner: 4 processor threads, 16 GB, no graphics card |
| Read from | the committed digest archive, `frontend/public/digest/` |
| Encoders asked | `config/encoder-comparison.json` |
| The answer | `readings/encoders.md` for a person, `readings/encoders.json` for a program |
| What ran | `manifest.json` - commit, run, runner, input counts, which encoders reported |
| The input | `pairs.json` - the pair set every encoder scored |
| What each shard printed | `logs/` |

## How the comparison runs

A selected run passes `selected_encoders` as comma-separated config slugs and
sets `reuse_pairs` to true. It reads the committed `pairs.json` without rebuilding
it. Only the selected encoders run; the collector retains the other saved rows.
Thus a new candidate does not spend runner time re-encoding the controls.

The October 2026 candidates are text-only `google/embeddinggemma-2` with the
sentence-similarity instruction, and the official merged text-matching weights
for Jina v5 nano. Both inputs to a pair have the same role. Revisions, constructor
options, prompts and the input hash are saved with each new reading. The runtime
package versions are uploaded with the shard log. Vectors are retained for 90
days, not three. The Jina weights are CC-BY-NC-4.0; this comparison is not approval
for commercial deployment.

The text-only load still constructs a vision-aware processor. The comparison
runtime therefore installs the supported image extra, including Pillow. Torch
and Torchvision come from the same CPU wheel index; mixing a CPU tensor runtime
with a CUDA vision wheel would fail before any summaries are encoded. Processor
imports are checked before the shard downloads model weights.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontFamily": "sans-serif", "primaryColor": "#f8fafc", "primaryTextColor": "#1f2937", "primaryBorderColor": "#64748b", "lineColor": "#64748b", "textColor": "#1f2937", "clusterBkg": "#f8fafc", "clusterBorder": "#94a3b8", "edgeLabelBackground": "#ffffff"}}}%%
flowchart TD
  ARCHIVE[("Published days<br/>Title, summary, outlet, day")] --> NEIGHBOUR{"Two articles near<br/>each other in time?"}
  NEIGHBOUR -->|"No"| SKIP["Not compared<br/>Too far apart to be one event"]
  NEIGHBOUR -->|"Yes"| OVERLAP{"How much of the subject<br/>do the two TITLES share?"}

  OVERLAP -->|"Below 0.10"| DIFFBUCKET["Different events<br/>Should score low"]
  OVERLAP -->|"0.10 to 0.30"| MIDBUCKET["Uncertain<br/>Never scored right or wrong"]
  OVERLAP -->|"0.30 and above"| OUTLET{"Same outlet?"}

  OUTLET -->|"No"| SAMEBUCKET["Same event<br/>Should score high"]
  OUTLET -->|"Yes"| RELBUCKET["Second piece<br/>A correction or a follow-up<br/>Never scored right or wrong"]

  SAMEBUCKET --> PAIRSET[("Pair set<br/>SUMMARIES and pair numbers<br/>The titles stop here")]
  DIFFBUCKET --> PAIRSET
  MIDBUCKET --> PAIRSET
  RELBUCKET --> PAIRSET

  PAIRSET --> ENCODE["One encoder a shard<br/>Encode every summary"]
  ENCODE --> PROGRESS[("Reading saved<br/>Every 512 articles")]
  ENCODE --> SCORE["Score every pair<br/>Closeness of two vectors"]
  SCORE --> TABLE[("Readings<br/>One row an encoder")]

  subgraph OBSERVED["Metrics"]
    SEPARATION["Proxy ROC AUC<br/>Positive pair ranks above<br/>negative pair (0 to 1)"]
    LEAN["Middle-overlap exceedance fraction<br/>Unlabeled scores above the<br/>class-mean midpoint (0 to 1)"]
    SECOND["Same-outlet exceedance fraction<br/>Unlabeled scores above the<br/>class-mean midpoint (0 to 1)"]
    RATE["articles_a_second<br/>Encoding rate on the runner (count/s)"]
  end

  SCORE --- OBSERVED

  classDef stage fill:#f8fafc,stroke:#64748b,stroke-width:1.5px,color:#1f2937;
  classDef decision fill:#ecfeff,stroke:#0e7490,stroke-width:1.5px,color:#164e63;
  classDef yes fill:#f0fdf4,stroke:#166534,stroke-width:1.5px,color:#14532d;
  classDef no fill:#fef2f2,stroke:#991b1b,stroke-width:1.5px,color:#7f1d1d;
  classDef warn fill:#fffbeb,stroke:#92400e,stroke-width:1.5px,color:#78350f;
  classDef data fill:#eff6ff,stroke:#1d4ed8,stroke-width:1.5px,color:#1e3a8a;
  classDef metric fill:#ffffff,stroke:#475569,stroke-width:1.5px,color:#1f2937;

  class ENCODE,SCORE stage;
  class NEIGHBOUR,OUTLET,OVERLAP decision;
  class SAMEBUCKET yes;
  class DIFFBUCKET no;
  class MIDBUCKET,RELBUCKET,SKIP warn;
  class ARCHIVE,PAIRSET,PROGRESS,TABLE data;
  class SEPARATION,LEAN,SECOND,RATE metric;
```

**The encoders read summaries. They never read a title.** A title decides which
bucket a pair goes in and is then set aside. Letting an encoder see the same
signal that built the answer key would flatter every one of them equally.

**Only the first two buckets make a proxy ROC AUC.** The other two are
scored on the same vectors and reported on their own, because neither has an
answer anybody knows. Folding them in would leave one number answering three
questions and none of them clearly.

An article is encoded once however many pairs it appears in: 10,675 articles
carry 15,522 pair comparisons, and comparing two vectors is nearly free next to
producing one.

### The same-outlet bucket

One outlet publishing twice about one subject on one day is usually a
correction, an update, or a follow-up - *"Tencent leases 100,000 chips"*
followed by *"What the Tencent chip lease means for Oracle"*. Whether those are
one event or two is a real question with a real answer, and a title-overlap
rule cannot give it: the two titles share their subject words either way.

Counted over the 44 named UTC days: **488 high-overlap pairs come from one
outlet, against 5,517 from two.**

They are their own unlabeled group, scored on the same vectors and reported
beside the rest. They are not folded into proxy ROC AUC because their event
identity has not been judged in this proxy.

The mean cosine and fraction above the class-mean midpoint describe this
group's scores. A fraction near one does not prove an error: some of these
pairs may really report one event. No precision, recall or over-merging claim
can be made without labels. The separate model-judged set answers event
identity for its selected pairs; it does not label all 488 proxy candidates.

## Who wrote the labels

The original comparison buckets below remain title-derived. The separate
`judgments/pairs.json` contains the recovered 935-pair reading sheet, and
`judgments/verdicts.jsonl` contains append-only decisions. These are model-written
labels, not human ground truth. No original author model was recorded for the
first 54 recovered verdicts; their notes are preserved without inventing that
provenance. New decisions name their model, confidence and reason. A person's
review has a separate `human_verdict` field.

Each judgment carries hashes of both the sheet and the article content. A
changed sheet cannot silently reuse an old answer. Corrections append a new
history row; they do not overwrite the prior decision. Every finished batch is
committed as a delta. Conversation memory is not the label store.

### Which articles and pairs were selected

There are two inputs, not one. The original sampling export contains **15,122
distinct articles**, from 45 published UTC days between 2026-08-21 and
2026-10-05. Its SHA-256 is
`726ef4918640c9c8e18e633e1bc04aaf0fbece7b27ee29957a124f9eb96fa48d`.
The selected sheet uses **1,386 distinct articles** from that export.

The encoder comparison reads the narrower 2026-08-23 to 2026-10-05 window:
44 named days, one without a digest, and **15,115 valid distinct article URLs**.
Seven sampling-export URLs are absent from this window. Five articles first
published before it reappear inside it, so filtering only `first_day` would not
reproduce the encoder pool.

The proxy pair builder requires a URL, title and summary, keeps the first
appearance of each URL in the named window, and compares nearby days. It keeps
5,517 likely matches, 5,517 likely mismatches, 4,000 middle-overlap pairs and
488 same-outlet follow-ups. Only the **10,675 distinct summaries touched by those
15,522 comparisons** are encoded. That is why not every judged article has a
cached vector.

The separate judging sampler is `backend/utilities/choose_pairs_to_judge.py`.
It considers same-day or next-day pairs whose titles each have at least three
content words. Title overlap is shared content words divided by all content
words in the two titles; common English filler words are removed.

No encoder vectors were supplied to that sampler. Its rules, in priority order,
are: missing usable timestamps with overlap at least 0.15; same-outlet pairs
with overlap at least 0.30; same-day, different-outlet pairs with overlap at
least 0.55; unrelated titles with overlap below 0.05; and middle overlap from
0.15 up to 0.45. In this recovered frame, the legacy name `encoders_differ`
means that last title-overlap group, **not measured disagreement between models**.

Sampling targeted 1,000 unique pairs with quotas of 100 obvious matches,
100 obvious mismatches, 350 middle cases, 200 same-outlet follow-ups, 150
low-overlap/high-vector-similarity matches and 100 missing-time cases. The
vector-dependent quota was empty, leaving **850 unique pairs**. The sampler
shuffled within each group with seed `20261008`, added 85 blind repeat copies
and shuffled the sheet again: **935 rows**. The missing quota was not filled
with easier pairs.

The corpus did **not** form only 935 pairs. The sampler considered **9,101,758
same-day or next-day candidate pairs** before choosing 850 identities. The
1,000 target was a bounded judgment budget, not a count of all events or a
statistical power calculation. Reusing articles and inserting blind copies
means 935 rows touch 1,386 articles, not 1,870. The current uncertainty ranges
describe this enriched sample; they do not establish archive-wide accuracy.

Expanding the sample should add the missing low-word-overlap same-event cases,
hard different-event neighbors, and representative randomly selected candidate
pairs, rather than merely more easy mismatches. More article-independent,
reviewed examples would improve coverage and the label evidence.

The original export and these arguments reproduced every row and selection
field of the committed sheet exactly:

```powershell
python backend\utilities\choose_pairs_to_judge.py `
  --items $ItemsExport --out $RebuiltSheet `
  --total 1000 --duplicate-share 0.10 --seed 20261008 --reach-days 1
```

The original export was retained locally. The new, local-only archive contract
freezes its exact bytes in [`../story-dataset-1/articles.jsonl`](../story-dataset-1/articles.jsonl).
This is not publication approval. The committed 935-row sheet contains
the complete article text needed to judge it; the cached encoder input and
report preserve the scoring inputs and their hashes.

### How the model judgments were made

The judging view shows both complete summaries, titles, outlets and published
days, but hides the sampling group and encoder scores. Each decision compares
the specific actors, action and occasion, not merely shared subject words.

Two descriptions of one occurrence are `same`. A separate announcement,
decision, competition stage or independently newsworthy follow-up is
`different`, even if its actors match. A corrected number or currency unit alone
does not create another event. If the summaries do not settle identity, the
verdict is `cannot_tell`; a first-published day is not proof of occurrence time.

Every finished batch records reasons, available confidence, author-model
provenance and input hashes in append-only JSONL, then gets its own Git commit.
The recovered first 54 decisions have no recorded author model or confidence;
that information is not invented. The other 881 name `gpt-6.1-sol`.

### Judging, audit and fixed-split flow

The earlier diagram describes the title-derived proxy. This one describes the
completed model-judged evaluation.

```mermaid
%%{init: {"theme": "base", "themeVariables": {"fontFamily": "sans-serif", "primaryColor": "#f8fafc", "primaryTextColor": "#1f2937", "primaryBorderColor": "#64748b", "lineColor": "#64748b", "textColor": "#1f2937"}}}%%
flowchart TD
  SOURCE[("15,122 source articles")] --> SAMPLE["Title and metadata sampling<br/>850 unique pairs from 1,386 articles<br/>85 blind copies added"]
  SOURCE --> WINDOW["Named encoder window<br/>15,115 valid article URLs"]
  WINDOW --> INPUT[("10,675 summaries touched by proxy pairs")]
  INPUT --> VECTORS["Saved vectors<br/>Reuse MiniLM and GTE-small<br/>Encode Jina and Gemma once"]
  SAMPLE --> FRAME[("935 fixed pair rows")]
  FRAME --> JUDGE["Model reads full descriptions<br/>Same, different or uncertain<br/>No scores or sampling groups shown"]
  JUDGE --> STORE[("Append-only verdicts and delta commits<br/>935 decisions; zero human review")]
  STORE --> AUDIT["Collapse repeats and audit agreement<br/>Exclude conflicts and uncertain identities"]
  VECTORS --> COVERAGE["Require both vectors<br/>Require unchanged summary text"]
  AUDIT --> COVERAGE
  COVERAGE --> ELIGIBLE[("723 eligible unique pairs")]
  FRAME --> GRAPH["Connect articles using every frame link<br/>Including excluded pairs"]
  GRAPH --> SPLIT["One fixed article-disjoint split<br/>Seed 20261009; no retries"]
  ELIGIBLE --> SPLIT
  SPLIT --> CAL["178 calibration pairs<br/>Choose one cutoff per model<br/>Target 95% sample precision"]
  SPLIT --> HELD["545 held-out pairs<br/>Do not tune on these"]
  CAL --> HELD
  HELD --> RESULT["AP, AUC, precision and recall<br/>1,000 paired component resamples<br/>Same draws for all four encoders"]
  RESULT --> REPORT[("Versioned evaluation.json<br/>Limits and exclusions remain explicit")]
```

## Complete model-judged comparison

This reading replaces the partial 140-row result. It uses all **935 initial
model judgments**, committed at `1cd139a51ca5528184e6db156e0ee5dc28ad2a84`.
There are 365 `same`, 547 `different` and 23 `cannot_tell` decisions, with
**zero human review**. The first 54 have an unrecorded author model; the other
881 name `gpt-6.1-sol`. No verdict was changed or decided by a majority vote.
All four encoders score exactly the same eligible unique pairs.

An unordered pair of article URLs is one identity. The 935 rows contain **850
unique identities and 85 repeat groups**, each seen twice. Of the repeat groups,
83 agree and two disagree: `p0158` says `different` while `p0467` says `same`;
`p0402` says `same` while `p0540` says `different`. Both conflicting identities
are excluded in full. There are no reversed repeats in this frame; the utility
handles them. The report lists every repeat's IDs and verdicts, not just these
two disagreements.

Saved inputs cover 817 rows by URL and by exact summary text. **118 rows lack
vectors; zero rows have changed summaries.** These are overlapping row-level
audits, not unique-pair exclusion counts. At unique-pair level the exclusions,
in order, are two conflicts, 23 uncertain decisions and 102 missing-vector
identities. This leaves **723 eligible unique pairs: 325 same and 398 different**
(44.95 percent same). Another 71 agreeing copies of eligible pairs are removed.
All excluded IDs remain in the report. Missing inputs are not re-encoded.

**118 rows versus 102 pairs:** A row is one appearance on the judging sheet,
including blind copies. The 118 appearances without both vectors represent
106 distinct identities: 12 appearances are repeats. Four of those identities
are already excluded as uncertain (`p0453`, `p0568`, `p0693`, `p0717`).
That leaves 102 otherwise eligible distinct pairs excluded for missing vectors:
**118 - 12 - 4 = 102**. These are missing encoded inputs, not missing judgments,
and they are never treated as zero similarity or a wrong model answer.

Table A. Selection strata, before exclusions and after unique-pair audit.

| ID | Selection group | Available metadata pairs | Unique pairs chosen | Judged rows including repeats | Eligible unique pairs |
| --- | --- | ---: | ---: | ---: | ---: |
| A1 | Middle title overlap (`encoders_differ`) | 14,649 | 350 | 384 | 301 |
| A2 | Same-outlet follow-ups (`hard_mismatch`) | 361 | 200 | 220 | 196 |
| A3 | Missing usable time (`no_publication_time`) | 4,857 | 100 | 109 | 86 |
| A4 | Obvious title match (`settled_match`) | 646 | 100 | 107 | 98 |
| A5 | Obvious title mismatch (`settled_mismatch`) | 8,743,516 | 100 | 115 | 42 |
| A6 | Low title overlap, high vector similarity (`hard_match`) | 0 | 0 | 0 | 0 |

There is **no `hard_match` group**. Titles and metadata enriched this frame.
Its event prevalence is not the production prevalence, and its precision is
not an estimate of deployed precision.

### Calibration and held-out results

The split is fixed before vectors are opened. A connected component is a set
of articles joined by any pair in the full reading sheet. This includes
uncertain, conflicting and uncovered pairs, so known event links are not lost
when metrics exclude a row. SciPy finds 558 components across 1,386 articles;
456 components have eligible pairs, and 102 are excluded-only.

Seed `20261009` assigns 137 of the 456 active components to calibration
(30.04 percent) and 319 to evaluation. Components have different sizes:
calibration therefore receives 24.62 percent of eligible pairs, not 30 percent.
There are **zero shared articles** between the two partitions. No split or seed
was retried. Events without a shared article or known link can still cross it.

Table B. The fixed article-disjoint partitions. Component article counts include
articles used only by excluded links.

| ID | Partition | Components | Articles (eligible articles) | Pairs | Same | Different | Same prevalence |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| B1 | Calibration | 137 | 318 (314) | 178 | 64 | 114 | 35.96% |
| B2 | Held-out | 319 | 862 (849) | 545 | 261 | 284 | 47.89% |

Each encoder gets its own threshold from **calibration only**, at the configured
95 percent precision target. Scikit-learn's precision-recall curve keeps tied
scores in complete blocks. The utility chooses the greatest recall meeting the
target, and then the lowest qualifying threshold. It never adjusts a threshold
on held-out results. An unattainable target produces null operating metrics with
a reason; no predicted positives produces null precision, not a success claim.

Average precision (AP) is the primary ranking measure; ROC AUC measures how
often a same-event pair outscores a different-event pair. Cosines are computed
in float64 from the cached float32 vectors, without loading an encoder.
The 95 percent AP intervals below resample whole held-out components 1,000
times with seed `20261010`. Every encoder and the GTE-small reference use the
**same draws**. All 1,000 draws contain both classes; none are discarded.

Table C. Held-out ranking and paired differences from GTE-small.

| ID | Encoder | AP (95% component interval) | ROC AUC | AP minus GTE (95% paired interval) |
| --- | --- | --- | ---: | --- |
| C1 | MiniLM-L6 | 0.8453 (0.7887 to 0.9046) | 0.8639 | -0.0500 (-0.0722 to -0.0275) |
| C2 | GTE-small | 0.8954 (0.8519 to 0.9396) | 0.9053 | 0.0000 (reference) |
| C3 | Jina v5 nano text-matching | 0.8639 (0.8106 to 0.9123) | 0.8752 | -0.0315 (-0.0598 to -0.0015) |
| C4 | EmbeddingGemma-2 text-only | 0.8911 (0.8435 to 0.9357) | 0.8979 | -0.0043 (-0.0249 to 0.0170) |

Table D. The frozen calibrated operating points. Precision is the share of
predicted matches that are model-labeled same; recall is the share of
model-labeled same pairs found.

| ID | Encoder | Threshold | Calibration precision / recall | Held-out precision / recall | Held-out TP / FP / FN / TN |
| --- | --- | ---: | --- | --- | --- |
| D1 | MiniLM-L6 | 0.910011 | 100.00% / 18.75% | 97.44% / 14.56% | 38 / 1 / 223 / 283 |
| D2 | GTE-small | 0.965687 | 96.30% / 40.63% | 94.19% / 31.03% | 81 / 5 / 180 / 279 |
| D3 | Jina v5 nano text-matching | 0.946977 | 95.45% / 32.81% | 98.28% / 21.84% | 57 / 1 / 204 / 283 |
| D4 | EmbeddingGemma-2 text-only | 0.971336 | 100.00% / 7.81% | 100.00% / 8.81% | 23 / 0 / 238 / 284 |

The report retains full-precision thresholds; the table rounds them for reading.
GTE-small's held-out precision is **below 95 percent**, despite reaching the
calibration target. Gemma's perfect observed precision comes with only 23
predicted matches and low recall, not a guarantee.

Whole-data AP on all 723 eligible unique pairs is **descriptive only**:
MiniLM 0.8423, GTE-small 0.8840, Jina 0.8516, Gemma 0.8772. It is not held-out
evidence and was not used to pick a split or threshold.

### Cost and conclusion

Table E. Saved encoding costs for 1,000 articles on separate GitHub
4-vCPU, 16-GB, no-GPU runs, with whole-process peak memory.

| ID | Encoder | Minutes / 1,000 | Peak GiB | Vector run |
| --- | --- | ---: | ---: | --- |
| E1 | MiniLM-L6 | 0.58 | 0.87 | `37850950040` |
| E2 | GTE-small | 0.18 | 1.14 | `37850950040` |
| E3 | Jina v5 nano text-matching | 4.80 | 1.91 | `37895396586` |
| E4 | EmbeddingGemma-2 text-only | 5.64 | 3.30 | `37909985697` |

These are not controlled same-silicon trials. One timing per encoder gives no
confidence estimate, and parameter count alone does not explain speed.
Jina's merged weights contain about 212M parameters; the advertised 239M is the
multi-adapter family. Its CC-BY-NC-4.0 license is not commercial-adoption
approval. Gemma is text-only 270M with vision/audio disabled and Apache-2.0.
Model IDs, prefixes, recorded revisions, options, vector hashes, run/artifact
names and saved cost readings are in the report. Baseline revisions were not
recorded; none are invented.

GTE-small has the highest held-out AP and greatest recall at its frozen cut.
Its paired AP differences from MiniLM and Jina exclude zero in this conditional,
unadjusted comparison. **GTE-small and Gemma are not separated by this test**:
their difference interval includes zero. The intervals measure sampling of
held-out components, not model-label errors, threshold-estimation error or
multiple-comparison-adjusted significance.

This frame can compare the four candidates against these model-written event
decisions. It cannot establish human-validated quality, production precision,
coverage of missing inputs, or a statistically demonstrated GTE/Gemma winner.
GTE-small and MiniLM remain the owner's candidates. No production configuration
changes. A representative sample and human review of label disagreements would
test the remaining deployment assumptions; neither is claimed here.

### Settings and fine-tuning worth investigating

The official [EmbeddingGemma-2 model card](https://huggingface.co/google/embeddinggemma-2)
documents symmetric task prefixes, mean pooling, 768-dimensional output and
float32 or bfloat16 inference. The measured run already used mean pooling,
full 768 dimensions, float32 and
`task: sentence similarity | query: ` on both inputs. There was no missing
similarity instruction to repair. Vision and audio were disabled for memory
and CPU cost; enabling them does not enrich text-only inputs.

**A lower cosine cutoff increases recall but can lower precision.** On the
178 calibration pairs only, Gemma's 95% precision constraint selected a
0.971336 cutoff, finding five of 64 same-event pairs (7.81% recall, 100%
observed precision). Relaxing the constraint to 90% selected 0.951614 and found
18 of 64 (28.13% recall, 18 correct / 20 predicted matches). This is
calibration-only exploration, not a new held-out result or a proposed
production setting. Changing the cutoff does not improve AP, which measures
the whole ranking.

The comparison caps every input at **256 tokens**; Gemma supports 8,192.
A tokenizer-only audit at the recorded model revision, including the same
prefix and special tokens, found 25 of 10,675 encoded inputs above the cap
(maximum 332 tokens). Four of 1,163 distinct eligible articles exceed it,
affecting four of the 545 held-out pairs: `p0132`, `p0317`, `p0577`, `p0592`.
The tokenizer JSON hash is
`4d777ef5bdc1aa36227abdfb77c3e49e7b9c892d16e1b6bda41c393504828be4`.
Testing 512 tokens would cover all recorded inputs for this tokenizer. The
audit does not establish that missing text changed those four labels or scores,
or that a larger context would solve the recall problem.

A `Clustering` prefix is another documented Gemma task setting to test on
development data, not a demonstrated improvement. Broad topical clustering
may be less suitable than similarity for distinguishing separate events about
the same company. Matryoshka truncation to 512 or 256 dimensions can be
evaluated from saved full vectors after re-normalization: it saves vector
storage and scoring cost, not the main encoder forward pass, and is not a
promised recall boost. Batch size, thread count and supported numerical
precision primarily affect runtime and memory.

GTE-small's [official card](https://huggingface.co/thenlper/gte-small) identifies
**Alibaba DAMO Academy** as its training group. Its uploader name is not its
research pedigree. Google's resources, a model's age and published general
benchmarks do not establish superiority on this particular event-identity
task. GTE-small remains the provisional quality/cost choice, with MiniLM as
the retained control, not a deployment decision.

**GTE-small can be fine-tuned** with Sentence Transformers. Binary
same/different pairs fit a supervised contrastive objective; difficult
different-event examples teach the model not to join separate occurrences.
The [training guide](https://sbert.net/docs/sentence_transformer/training_overview.html)
and [loss guide](https://sbert.net/docs/sentence_transformer/loss_overview.html)
describe domain adaptation and matching a loss to label format. Same-event
positive pairs can also support ranking losses, but indiscriminate in-batch
negatives may incorrectly separate different articles about one real event.

Fine-tuning is a hypothesis, not a free upgrade. There are only 723 unique
covered binary pairs, and the existing non-held-out partition has just 178
pairs (64 same, 114 different). Review inconsistent or ambiguous labels and
collect additional train/development data. Keep connected articles together,
keep the 545 held-out pairs out of training and hyperparameter selection, and
reserve a fresh confirmation set after repeated model comparisons. Training
on all 935 and measuring on those same pairs would be memorization, not
evidence of improvement. No fine-tuning or additional encoding has run here.

### Faster evaluation of additional encoders

A new encoder need not encode the archive. The **entire fixed judging sheet**
needs at most **1,386 unique summaries encoded once**, not 935 times two and
not 15,000 articles. That is about one eighth of the earlier 10,675-summary
encoding work, assuming similar lengths and batch efficiency; actual wall
time still needs measurement.

All four current encoders already cover 1,269 of those articles; 117 distinct
article inputs are absent from their caches. The earlier 118 missing rows and
102 excluded identities count pair appearances and pair identities, not
articles. Filling those missing inputs would require additional encoding and
versioned provenance for every baseline included in a larger comparison.

For an exact like-for-like comparison on the **existing 723-pair evaluation**,
a new encoder needs only its **1,163 distinct eligible summaries**. It can
reuse the fixed pair IDs, article partitions and model judgments; encode
those texts once, then calculate cosine scores. Saved models require no
encoding to test other cutoffs or compute additional metrics.

The current `encoder-comparison.yml` still reads the 10,675-summary proxy input,
and the evaluator refuses vectors in a different article order. A compact
selected-input encoder and order/hash validation now exist in the local
full-archive pipeline below. They do not replace the old evaluator or change its
completed run. A prompt/context or
weight change needs new vectors for that changed variant, but only for its
selected inputs. A learned cutoff or representation must be chosen without
tuning on the final held-out sample.

### Reproduce without encoding

The instrument is `backend/utilities/evaluate_encoder_judgments.py`, with report
shape `backend/idhazh/contracts/encoder_evaluation.py`. Its code/config commit is
`f1ace961b2b8ef57e2bca3b60b5f7d7756aae180`. Config holds the seeds, split fraction,
precision target, bootstrap rounds and reference. `judgment_vectors` names four
relative files beneath a local saved-vector root; set `$VectorRoot` to that root
before running this PowerShell command from the checkout:

```powershell
$env:PYTHONPATH = "$PWD\backend"
python backend\utilities\evaluate_encoder_judgments.py `
  --config config\encoder-comparison.json `
  --corpus corpus\encoder-comparison-1 `
  --vector-root $VectorRoot `
  --out corpus\encoder-comparison-1\judgments\evaluation.json
```

Use an interpreter with the project's development dependencies (scikit-learn,
SciPy, NumPy and Pydantic). The recorded run used Python 3.14.2, NumPy 2.4.1,
SciPy 1.17.0 and scikit-learn 1.8.0; the report records all runtime versions.
The input frame hash is
`7f0d931c697217431fed88ea84c96cd4fee05b6602e617718661b13fe2066feb`.
The utility refuses incomplete judgments, changed label provenance, invalid
vectors, mismatched input hashes and a split without both classes. It requires
committed, unchanged instrument sources and config. The report is one current
file; Git retains its history. The saved vectors are local artifacts, not
committed weights. The model judgments, report and instrument are Git-versioned
artifacts. Publishing them does not convert model-written labels into human
validation or adopt an encoder in production.

If this branch is squash-merged into `main`, retain the source branch
`feat/encoder-selected-checkpoints`. It keeps the individual label delta commits
and the report's original code and label commit references reachable. The merged
snapshot contains the full labels, report, instrument and documentation.

## How title-derived proxy labels work

**No human wrote or reviewed these labels.** The original proxy buckets below
are also not human ground truth.

The run needs to know which pairs of articles report one event. It has no such
list, so it builds a stand-in from a signal the encoders never see - the
generated title. A title in this pipeline is actor plus action with the hype
removed, so the words two titles share carry a real signal about whether they
cover one story.

### Four buckets, not two

A comparison that asks only "can you tell an obvious match from an obvious
mismatch" is one every encoder passes. It would also repeat a fault this project
has already found in its own duplicate judge: that judge is only ever shown
pairs scoring 0.88 or above, so it never sees the error that matters - two
reports of one event written so differently that nothing flags them.

So every pair is sorted by how much of their subject two titles share, and the
middle band is kept.

| Bucket | Rule | Treated as |
| --- | --- | --- |
| Same event | Two outlets, titles share **0.30 or more** of their subject words | A match the encoder should score high |
| Second piece | **One outlet**, titles share 0.30 or more | Neither. A correction or a follow-up |
| Uncertain | Two outlets, titles share **0.10 up to 0.30** | Neither |
| Different events | Two outlets, titles share **less than 0.10** | A mismatch the encoder should score low |

Every pair is published the same day or a day apart. Only the first and last
bucket make a proxy ROC AUC; the middle two are scored on the same vectors
and reported on their own.

### Where the thresholds came from

The lower bound is the one that matters, and it was chosen by counting. Over the
44 published days, at a floor of 0.34 the archive yields 3,762 matching pairs;
at 0.30 it yields more than 8,000. The project asked for at least 5,000, so the
floor sits at **0.30** and the caps in `config/encoder-comparison.json` decide
how many of them are used - not the floor, which would otherwise quietly set the
count.

The 0.10 line is where a shared word stops meaning anything: below it, two
titles usually share only a country or a company name that half the corpus
mentions.

### What the unlabeled score distributions report

The middle-overlap and same-outlet groups have no event labels in this proxy.
Each group has a mean cosine and a descriptive exceedance fraction: the share
of scores strictly above `(positive mean + negative mean) / 2`. The midpoint is
encoder-specific and is not a calibrated or production threshold.

Higher or lower fractions describe scores, not correct or incorrect decisions.
Neither an over-merging rate nor recall can be inferred from them. The generated
[`readings/encoders.md`](readings/encoders.md) spells out the formulas and maps
the historical JSON names to these descriptions.

### What the title-derived proxy cannot tell you

Both outer buckets contain mistakes. Two outlets can write near-identical titles
about genuinely different events, and one event can draw two titles with no
words in common. **So no number here is an accuracy.**

Every encoder scores identical proxy pairs, but scores near one on easy,
title-derived cases cannot establish a ranking on actual event identity. The
completed model-judged evaluation is the harder selector. It is explicitly
model-written, not the future human-reviewed evidence this project still lacks.

## If a shard runs out of time

The reading is written before the first article is encoded and rewritten every
512 articles, each time to a temporary file that is then renamed - so a reader
only ever sees a whole file, and a shard killed at the six-hour limit leaves
behind how far it got and how fast it was going.

`state` says which happened:

| State | What it means |
| --- | --- |
| `loading` | Weights were still downloading. Nothing encoded |
| `encoding` | Stopped partway. `articles_done` and `articles_a_second` are real |
| `measured` | Finished. Every number is there |
| `unavailable` | The model would not load. `reason` carries what the runtime said |
| `stopped` | The encode raised. `reason` carries it |

An encoder that cannot finish inside six hours has answered the cost question
even though it never answered the quality one, and the table says so rather than
leaving the row blank.

## What the numbers mean

**ROC AUC** is the standard name of the statistic historically stored as
`separation`. On the proxy, it compares likely-positive with likely-negative
pairs, not verified event labels. One is perfect ordering, 0.5 is chance-level,
and ties receive half credit.

It is used instead of the gap between two averages, because encoders put their
scores on different scales. An earlier attempt at this comparison, run on a
laptop, reported `all-MiniLM-L6-v2` ahead of `bge-base-en-v1.5` on a gap of
0.720 against 0.431 - but bge places unrelated pairs at 0.456 where MiniLM
places them at 0.105, so the gap was measuring the scale and not the skill. A
rank cannot be fooled that way.

**Mean cosine difference** is the standard descriptive quantity stored as
`spread`: positive mean minus negative mean. It is not variance, standard
deviation, Cohen's d or a scale-free quality measure. A larger gap does not
establish easier calibration or more stable production behavior; separate
encoders have different similarity distributions.

**Throughput** is encoded summaries divided by encoding seconds, on the
recorded host. It informs runtime cost, not embedding quality or the chance
of meeting every future job deadline. The time projections assume that rate
continues for the configured number of articles.

The figure is kept for two narrower purposes: deciding how long a comparison
like this one takes to run, and pricing the one-time cost of re-encoding the
whole archive if the encoder ever changes.

**Treat the figure as the machine's, not the model's.** Two runs of
`gte-base` - same code, same pairs, same kind of runner - returned 8.4 articles
a second and then 0.8, while three other encoders repeated to within one
percent. In the same run a 335-million parameter model finished in 2h 13m and a
109-million one took 3h 34m. A hosted runner is whatever silicon it drew, and
cache size and memory bandwidth differ between them. Each shard now records the
processor it ran on, so a figure can be read against its machine instead of
being read as the model's.

**Peak resident memory** is the whole process, reported in GiB, against the
runner's advertised 16 GB. This one does
bite: the batch also runs the summariser, and a large encoder plus a loaded
language model is where the limit is reached.

The [generated metric glossary](readings/encoders.md#metric-glossary) defines
cosine, ROC AUC, AP, precision, recall, confusion counts, diagnostic midpoint
fractions, throughput, memory and confidence intervals. The historical JSON
keys are retained so the original numeric measurements and report provenance
remain intact. Refresh the readable table without encoding or changing a
manifest:

```powershell
python backend\utilities\compare_summary_encoders.py render `
  --readings corpus\encoder-comparison-1\readings\encoders.json `
  --out corpus\encoder-comparison-1\readings\encoders.md
```

## What was removed

Nothing. Every article in the named range that has a title, a summary and an
address is eligible. An article the pair builder never paired is simply not
encoded, because encoding an article no pair touches would cost time and answer
nothing.

## How to read a shard that did not report

A model that will not load is recorded as `unavailable` with its reason, and the
run continues. A gated model, a renamed one, or one needing a library version
the runner does not have all land there. That is a finding about the model's
availability, not about its quality, and the row says so rather than going
missing.

## Local full-archive dataset contract and run plan

The new [`../story-dataset-1/manifest.json`](../story-dataset-1/manifest.json)
freezes all 15,122 URL-unique rows, 14,371,193 bytes, without rewriting the
source. It also pins the old 935-row frame, verdicts and encoder input hashes.
The original regression labels retain their old binary meaning. They are not
new hierarchy labels. No old artifact, production encoder or workflow changes.

[`../../config/story-dataset.json`](../../config/story-dataset.json) is the
machine-readable run plan. Its stages and approved meanings are durable.
Batch size 20, topK 10, block size 32, random audit fraction 0.01, Bernoulli pair
probability 0.00001, split seed and development fraction are **provisional
engineering parameters**, not quality guarantees, labeling budgets, pair quotas
or owner-approved acceptance targets. Acceptance remains `unapproved`.

### Identity and label meaning

Topic > Event > Story is the hierarchy. Event is the broader parent: presidential
election > 2024 presidential election > TV debate 1. Each article can have
several supported paths, all equal. A specific occurrence is recorded below a
Story but is not the definition of an Event. Whole-article duplicate coverage
is a separate pair judgment. Shared-only-some coverage is partial overlap.

The [approved B1-B10 source artifact](../story-dataset-1/approved-examples.json)
is preserved byte-for-byte, including its earlier discussion status. The
owner's later approval is recorded in
[seed-catalog-review.json](../story-dataset-1/seed-catalog-review.json). A1-A5
were not used. B10's explanatory sibling-Story boundary remains unresolved;
its earlier recorded source findings do not become a fabricated adjudication
or a fabricated check timestamp. Fifty-three explicit seed identities are
examples, not a closed ontology and not twenty completed article annotations.

An article ID is `a-` plus SHA-256 of its exact validated URL. Its input hash
is SHA-256 of canonical JSON for the complete validated source row, with LF.
Source bytes themselves are never normalized. Catalog IDs hash an explicitly
reviewed global identity key and kind, not an article title or batch filename.
Worker-local `proposal:<slug>` references are scoped by the batch hash.
Identical display names are never automatically merged.

### Worker request and answer

From the preserved `archive-story-dataset` worktree root, use the existing Python
with the project's development dependencies: Pydantic, NumPy, SciPy and
scikit-learn. On this machine `C:\Python314\python.exe` has them; the main
checkout's `.venv` lacks scikit-learn. Installing only NumPy and Pydantic is not
enough because the CLI also imports the offline evaluation modules. A fresh
environment needs the project's existing `.[dev]` extra, not new tools.

```powershell
Set-Location 'C:\Users\kumarsnaveen\Downloads\NawiN\personal\gitrepos\yen-idhazh.worktrees\archive-story-dataset'
$Python = 'C:\Python314\python.exe'
$env:PYTHONPATH = "$PWD\backend"
$D = 'corpus\story-dataset-1'
& $Python -m idhazh.story_dataset.cli status
& $Python -m idhazh.story_dataset.cli schema --output "$D\schemas"
& $Python -m idhazh.story_dataset.cli export --output "$D\workers\primary-0002.json"
```

The first unanswered request is already
[`workers/primary-0001.json`](../story-dataset-1/workers/primary-0001.json).
Its `.catalog.json` sidecar contains shared definitions. The evidence view
contains the exact full summary, title, URL, domain, item ID, first day,
published instant, nullable original time-source value and input hash.
It contains no candidate group or encoder score. Source text is untrusted data.
All instants newly written by the pipeline use UTC.

Give a fresh `gpt-6.1-sol` worker that request, sidecar and
[`schemas/WorkerSubmission.json`](../story-dataset-1/schemas/WorkerSubmission.json).
Ask it to return one local JSON artifact, not to write the catalog or repository.
It must answer **every** requested article ID. This is the answer shape; the
angle-bracket fields below must be copied from the request, not invented:

```json
{
  "batch_id": "<request batch_id>",
  "source_sha256": "<request source_sha256>",
  "catalog_revision": "<request catalog_revision>",
  "label_source": "model",
  "labeler": "gpt-6.1-sol",
  "worker_id": "primary-0001-sol",
  "operation": "primary",
  "independent_of": [],
  "proposals": [],
  "decisions": {
    "<article_id>": {
      "input_sha256": "<that article input_sha256>",
      "state": "annotated",
      "memberships": [{
        "topic": "<canonical topic ID or proposal ref>",
        "event": "<linked event ID or proposal ref>",
        "story": "<linked story ID or proposal ref>",
        "occurrence_refs": [],
        "evidence": "<reasoned support from this article>"
      }],
      "reason": "<reasoned full-article decision>",
      "unresolved_reasons": [],
      "review_flags": [],
      "source_checks": [],
      "summary_evidence": "full-stored-summary"
    }
  },
  "supersedes": {}
}
```

Repeat each map entry for the complete request. For ambiguity, use
`state: "unresolved"` and nonempty `unresolved_reasons`; supported paths can
remain alongside uncertainty. Read the full summary first. Consult original
sources when ambiguous or conflicting. Record real source findings and check
instants; necessary inaccessible evidence remains unresolved. Never claim
blank source checks prove the evidence is complete or that a model is human.

Unseen identity proposals have exactly `ref`, `kind`, `name`, `parent_refs`,
`definition`, and `evidence_article_ids`. Kinds are `topic`, `event`, `story`,
`occurrence`. Topic parents are empty; Event parents are Topics; Story parents
are Events; occurrence parents are Stories. A proposed membership is imported
as **catalog pending**, not as a qualified global label.

```powershell
& $Python -m idhazh.story_dataset.cli import --input '.\worker-answer.json'
& $Python -m idhazh.story_dataset.cli catalog --output "$D\catalog-current.json"
& $Python -m idhazh.story_dataset.cli catalog-review --input '.\catalog-review.json'
& $Python -m idhazh.story_dataset.cli status
```

A `CatalogReview` must name the exact `expected_revision`, model reviewer and
reason. New entities carry a reviewed `identity_key`, definition, typed parent
IDs and supporting article IDs. Use `identity_id(kind, identity_key)` from
`idhazh.story_dataset.catalog` to compute IDs. `proposal_resolutions` maps
`<batch_id>:proposal:<slug>` to those IDs. Explicit aliases preserve old entities
and reviewed history. Unknown parents, cycles, broken paths and stale revisions
are refused. No string-name equality or majority vote reconciles identities.
Catalog changes must preserve both primary and independent-review membership
paths; a proposal cannot resolve to a Story under an unrelated Event.

Each import is one SQLite transaction in the **local ignored**
`state.sqlite3`; previous record payloads are immutable. An identical submission
resumes with zero added rows. Missing/foreign IDs, input-hash changes, fake human
provenance and unsupported parent links fail the whole batch. A correction needs
a fresh explicit-ID export and exact `correction_targets` copied to
`supersedes`. It appends a record, never edits an earlier answer. Keep the SQLite
file out of Git. Commit immutable typed checkpoints instead; `history --output <dir>`
also exports typed JSONL history, but does not by itself freeze a coherent multi-file
epoch. Do not push these commits.

`checkpoint --output <new-directory>` reads the named database in one consistent
read transaction. With active writers and a rollback journal, first use SQLite's
online backup API through a read-only source connection into an integration-owned
ignored index. Copy bounded page batches without a long live read transaction.
Run the checkpoint exporter against that completed, private snapshot, not a
file copy of the changing SQLite file or its worker logs.
It exports exact typed history rows in sequence order, worker
batches, submission metadata and proposals, current catalogue, active partition
with its exposure lineage, and portable vector manifest. Submission decisions
are reconstructed from the history and checked
against their original hashes on restore. Catalogue revisions are rebuilt from
review records and checked against the stored snapshots before export. The
hash-and-size manifest is written last; a directory without it is not complete.

`restore-checkpoint --input <directory>` requires an empty local index and the
same frozen source and policy. It restores records and worker state atomically.
The approved archive and example captures have exact-byte Git attributes:
their original CRLF bytes are evidence, not authored text to normalize.
It does not copy raw source HTML, model binaries, vector arrays or the large
pair frame. Those omissions remain named by their immutable revisions in the
checkpoint; missing frame settings are not activated. Supply the exact portable
vector evidence at the dataset-relative manifest paths before vector scoring,
and regenerate or explicitly recover the exact pair frame before pair-frame
dependent work. Status and annotation resume do not require those large files.
Confirmation exposure stays locked after restore even when its development
configuration is an omitted artifact. Both prediction and evaluation of an
external confirmation run record exposure before returning label-based metrics.
Partition revisions keep each article's original development or confirmation
exposure through temporary uncertainty, so later corrections cannot redraw it.
Neighbor evidence with selected vector extensions records both endpoint file
hashes; a mixed-file comparison has their canonical combined digest.

Automatic exports reserve disjoint pending article batches. An interrupted
worker resumes the **same** input:

```powershell
& $Python -m idhazh.story_dataset.cli resume `
  --batch-id '<original batch_id>' --output "$D\workers\resumed.json"
& $Python -m idhazh.story_dataset.cli export --operation review `
  --output "$D\workers\review-0001.json"
```

Reviews select flagged, unresolved or catalog-pending rows plus a reproducible
hash-based random audit of the rest. They hide the first answer and include
opaque record hashes and primary worker IDs only. A different worker must copy
`independent_of_workers` to its answer's `independent_of`. Review imports do not
overwrite primary labels. Status reports disagreements and pending resolutions;
agreement is not accuracy. No mandatory second pass or invented acceptance
bound is imposed.

### Candidates, coverage and fresh partitions

The probability stream independently samples the declared population of
**114,329,881 unordered distinct archive pairs**. Geometric skips give each pair
the configured Bernoulli inclusion probability without building an all-pairs
list. The challenge stream separately records metadata proposals and the union
of ranked neighbors from all four models. Each model retains its own cosine,
rank, query and vector hash. Cosines are never averaged. Rank disagreement
means actual model-rank disagreement, not the old lexical sampling-group name.

Metadata discovery considers uncached articles too. `pair-add` accepts typed
source-backed extended-time, paraphrase or follow-up proposals without making
labels. Source-backed tags require source-check evidence. A pair can be in both
streams; its identity is one pair but its acquisitions remain separately
reported. Do not concatenate them into a production-frequency estimator.

```powershell
& $Python -m idhazh.story_dataset.cli pairs `
  --queries "$D\approved-example-ids.json" --output "$D\pairs-example-neighbors.json"
& $Python -m idhazh.story_dataset.cli pair-export `
  --frame "$D\pairs-example-neighbors.json" --output "$D\workers\pairs-0001.json"
& $Python -m idhazh.story_dataset.cli pair-import --input '.\pair-worker-answer.json'
& $Python -m idhazh.story_dataset.cli pair-export --operation review `
  --frame "$D\pairs-example-neighbors.json" --output "$D\workers\pair-review-0001.json"
```

Omit `--queries` for full cached-query discovery, or use `--metadata-only` to
avoid vectors. Query IDs are a cost/discovery choice, not a labeling budget.
Pair workers see both full evidence rows and independently label Topic, Event,
Story, occurrence and coverage. Canonical article memberships do not supply
automatic pair answers. Pair review views are independent and blind too.
Pair export serializes, validates and hashes one canonical frame snapshot before
taking SQLite's write lock. A registered frame must match those exact bytes; it
is not serialized or inserted again. Frame and batch IDs keep their original
meaning. Selection and reservations still share one transaction, and corrupt or
conflicting stored bytes fail closed.

The four saved caches contain 10,675 URLs. **Three summaries differ from the
full archive source**, so only 10,672 rows are currently text-valid. The 4,447
uncached rows and three conflicts remain missing inputs, never zero-score
negatives. This does not establish full semantic retrieval coverage.
[`vectors.json`](../story-dataset-1/vectors.json) pins order, text, numeric shape,
nonzero finite rows, each file hash, reading hash and encoding settings.

### Repair the saved registration after a worktree move

The original `vectors.json` and SQLite registration used absolute paths. Three
paths still name the old worktree. Do not edit that JSON or a historical SQLite
payload. `relocate-vectors` creates a new typed `VectorSnapshot`, with the prior
registration hash in `previous_revision`. It checks every supplied location
against the exact old file hash before copying anything. It copies input,
readings, config, vectors and any extensions once into immutable, hash-named
`vector-evidence/` files beneath the dataset root. Persisted paths are relative
POSIX paths. Later reads resolve them against `--root`, not the working directory.
Move that whole dataset root together; the old session cache is no longer needed
by the new snapshot. No model runs and no settings, row order, text hashes or
source identities change. Copying cached bytes costs disk space, not encoding.

For the current saved registration, run this once after the active dataset
worker has finished its write. Use the `$Python`, `$D` and worktree above:

```powershell
$Legacy = Get-Content "$D\vectors.json" -Raw | ConvertFrom-Json
& $Python -m idhazh.story_dataset.cli relocate-vectors `
  --expected-revision '3ddd0f15e7d1f49af9bdb0691b5009b35c4157096e08daca186fc70ee4bd93d9' `
  --file "$($Legacy.input_sha256)=$PWD\corpus\encoder-comparison-1\pairs.json" `
  --file "$($Legacy.readings_sha256)=$PWD\corpus\encoder-comparison-1\readings\encoders.json" `
  --file "$($Legacy.encoder_config_sha256)=$PWD\config\encoder-comparison.json" `
  --output "$D\vectors-relocated-0001.json"
& $Python -m idhazh.story_dataset.cli pairs `
  --queries "$D\approved-example-ids.json" --output "$D\pairs-relocated-0001.json"
```

The existing external vector files are still at their saved locations, so this
repair needs only the three checkout mappings. If an external cache also moves,
add `--file "<its file_sha256>=<its new path>"` for each affected cache or
extension. Unknown hashes, changed bytes, a stale expected revision or an
existing output with different bytes are refused. There is no basename search
or automatic path substitution. The old JSON and registration remain intact.
`status` reports coverage from registered identities; `pairs` checks all evidence
hashes before using the vectors. A different active revision needs that revision's
evidence and expected hash, not the historical hash above.

New `vectors --vector-root <cache-root> --output <new-file.json>` registrations
produce portable snapshots immediately. They refuse to replace an existing
registration; use the explicit relocation command instead. Extension imports
also require a portable base and retain their input and model checks.

The owner's 2026-10-11 ruling forbids local encoding or inference. The old
`encode` entry points remain available for other operators, but must not be
run for this delivery. Use the manual runner path below for unfinished rows.
`vector-import` validates a typed downloaded extension before adding coverage.
Unknown historical control revisions remain unknown. A current pin cannot
repair their provenance.

When the historical MiniLM or GTE revision is unknown, a current official pin
is **not** proof of the historical weights. The separate
`idhazh.story_dataset.candidate_cli` path registers a **new** immutable
`PinnedEncoderCandidate` from the exact saved reading and a dated, hash-checked
official model metadata capture. Its distinct slug preserves the unknown old
revision; it never changes the old reading or activates an old vector manifest.
Its `CandidateVectorUnit` and `CandidateVectorState` contain only independently
encoded new rows. Old control arrays cannot supply their coverage.

```powershell
& $Python -m idhazh.story_dataset.candidate_cli `
  --source-root "$D" --root '<new candidate evidence root>' register `
  --vectors '<exact portable snapshot.json>' --legacy-root "$D" `
  --slug '<old control slug>' --pin '<official immutable revision>' `
  --metadata '<captured official API response.json>' --check '<SourceCheck.json>'
& $Python -m idhazh.story_dataset.candidate_cli `
  --source-root "$D" --root '<new candidate evidence root>' import `
  --candidate '<hash-named candidate.json>' --unit '<unit.json>' `
  --previous '<previous immutable candidate state.json>'
```

Omit `--previous` for the first unit only. Registration retains original options,
prefix, dimensions, symmetric query/candidate roles, 256-token truncation and
float32 arrays. Encoding requires a checked isolated ST >= 6.1,
Transformers >= 5.19, Pillow and matching CPU torch/torchvision environment;
it remains offline-only after exact official model acquisition. Candidate state
imports copy vectors into hash-named evidence and recheck retained unit bytes.
The new control must encode every article of the eventual common evaluation
universe itself; combining it with unknown historical rows is prohibited.

### Exact missing-only runner inputs

`.github/workflows/story-archive-encoding.yml` is manual only. It does not
commit, push, dispatch another workflow, publish metrics or select a winner.
The older `encoder-comparison.yml` still answers its original proxy question;
it is not the full-archive encoder.

`RunnerShard` carries the frozen source manifest, resolved policy, parent
registration, pinned reading or candidate, exact ordered full article evidence,
summary-input hashes and expected model file hashes. `RunnerPackage` hashes
the actual input and code files. Preparing that package grants no consent.
Upload or push requires a separate approval naming the exact package,
recipient repository and visibility. The owner's 2026-10-11 ruling selects
a public workflow in the public repository, not a private repository or runner.
It uses the standard `ubuntu-latest` runner with four CPUs and 16 GB.
Encoding checks actual CPU and memory before loading weights.
Workflow code, input artifacts, logs and result artifacts can be publicly
accessible. Omitting a link does not make them private. The exact outbound
preview must disclose this before separate upload, push or dispatch approval.

The preserved input has 15,122 rows. MiniLM's distinct pinned candidate is
complete and is never selected for re-encoding. The prepared continuation
has GTE 2,922, Jina 4,430 and Gemma 4,430 missing inputs. It uses 32 shards
of at most 400 rows, each split into immutable units of at most 20 rows.
These are encoding gaps, not missing labels or a quality finding.
Each job loads one model once. It uses the saved symmetric prefixes, 256-token
input cap, CPU float32 output, two threads and batches of 16. Native Gemma
output stays 768 wide. Two shards can run concurrently. The five-hour soft
stop leaves time before GitHub's six-hour kill; shard completion is not
guaranteed before an actual runner measurement.

`config/story-runner-requirements.txt` pins the complete Linux CPython 3.14
dependency closure to official wheel hashes. Its adjacent JSON records the
versions and official metadata hashes. It reuses the declared comparison
runtime: ST 6.1, Transformers 5.19, Pillow 12.3 and matching CPU
Torch 2.14.1 / Torchvision 0.29.1. Windows wheel hashes are not reused.
Preparation checked official metadata and Linux dependency markers, not a
Linux execution. Runner preflight checks installed versions, CPU vision
operators, the Gemma processor and every selected model, tokenizer and
custom-code file before offline inference. No model substitution, TLS bypass
or unbounded dependency upgrade is allowed.

Prepare locally with the exact current heads, never a mutable source-folder
commit:

```powershell
& $Python -m idhazh.story_dataset.runner_cli prepare `
  --source-root "$D" --vectors '<current portable vector snapshot.json>' `
  --vector-root '<native evidence root>' `
  --candidate '<pinned GTE candidate.json>' --state '<current GTE state.json>' `
  --candidate-root '<current candidate evidence root>' `
  --requirements 'config\story-runner-requirements.txt' `
  --output 'backend\var\runner-input'
& $Python -m idhazh.story_dataset.runner_cli validate `
  --package-root 'backend\var\runner-input'
```

Only after exact outbound approval, upload the prepared ZIP as a release asset
in `miztiik/yen-idhazh`. This route does not require a pre-existing Actions
artifact. Use `gh release upload <approved-release-tag> <exact-ZIP-path>`
without `--clobber`, then obtain the numeric asset ID from
`gh api repos/miztiik/yen-idhazh/releases/tags/<approved-release-tag>`.
Preview the tag, exact ZIP path/hash, recipient and public exposure before
approval; release assets, article summaries, logs and vectors are public data.
Dispatch the workflow at its exact code commit with `input_asset_id`,
`archive_sha256` and the approved `package.json` hash. Alternatively, an
already-approved `archive-input` Actions artifact can use `input_artifact_id`.
The workflow refuses both routes together. An exact shard runs only that shard.
Preparation checks each code file against its committed LF Git blob; dirty
or CRLF code cannot produce a runner-approved preview.
The standard-library bootstrap checks installer bytes before pip runs.
The workflow downloads no source from a changing digest window.

Every complete unit gets a native `.npy`, typed descriptor, file checksum,
input order and immutable candidate or extension lineage. `RunnerResult`
records runtime, model files, host, UTC times, run/attempt, complete units and
the exact pending IDs. Results remain GitHub artifacts for 90 days, not
committed raw vectors. A hard-killed unit is not registered from an orphan
array or a progress counter. A durable initial result records runtime and model
provenance before encoding. `runner_cli recover --package-root ... --shard ...
--result ...` validates complete descriptor/array pairs that survived a manifest
interruption, reconstructs their exact manifest and keeps incomplete files in a
sibling ignored directory. It does not infer, encode or register incomplete
units. The workflow excludes `.part` files from result artifacts.

After approval and execution, use `runner_cli download --recipient <owner/repo>
--artifact-id <id> --name <archive-result-shard> --output <ignored-directory>`.
It checks the exact recipient, artifact name, GitHub's archive digest,
size and safe paths before extraction. Then use `runner_cli validate` with
`--package-root`, `--shard` and `--result`. Import with the same arguments plus
`--source-root`, `--root` and, for GTE, `--state-pointer` naming the current
integration-owned state. Import uses the existing typed candidate/extension
APIs. It rejects changed inputs, wrong pins, different prefixes, shape/dtype
errors, nonfinite or zero rows, unexpected files and conflicting coverage.
It never writes the annotation workers' index.

A partial result can resume through the same package and one exact shard,
with `resume_artifact_id` naming its retained result artifact. Validation
skips only complete twenty-row units. Alternatively, import complete units
first and prepare a new missing-only package from the advanced registration.
Neither route borrows unknown legacy vectors. No workflow has run merely
because these files exist.

### Derived Gemma dimensions without inference

`runner_cli derive --vectors <native snapshot.json> --root <native root>
--output-root <derived root> --dimensions 128` also supports 256 and 512.
It reads the native 768 rows, takes the first requested components and
L2-normalizes each prefix. L2 normalization divides by the prefix's length.
It makes no model call and leaves all native registrations and arrays intact.
Finite, nonzero prefixes are required.

Each `GemmaDimensionCandidate` has a distinct slug, native registration and
file hashes, source/settings hashes, ordered IDs and actual output hash.
Its `DerivedVectorSnapshot` has only that candidate's vectors. Query and
candidate scoring therefore use the identical width and transform.
Keep arrays and full derived snapshots in the ignored cache; compact lineage
descriptors can be committed.

Choose dimensions on development data. Put
`"vector_candidates": {"<derived slug>": "<derived snapshot hash>"}`
in the existing `DevelopmentConfig.parameters`, then freeze it before opening
confirmation. `predict` and `evaluate` accept `--vectors <derived snapshot>`
without changing the saved native registration. Both refuse an unselected
derived candidate. Existing complete-qrels, source/catalogue partition and
confirmation-exposure checks still apply. Arithmetic fixtures or smaller
files are not evidence of improved quality. Full fresh comparison remains
blocked until the required labels, reviews and independent qrels are ready.

Fix the split before tuning:

```powershell
& $Python -m idhazh.story_dataset.cli split --output "$D\partition-0001.json"
& $Python -m idhazh.story_dataset.cli evaluate --output "$D\evaluation-blocked.json"
```

Every supported Event membership joins its article component; multi-Event
articles connect all their Events. A known Event still connects its article
when another membership, parent support or occurrence is unresolved. The whole
connected component remains unknown-membership quarantined. Regression exposure
also persists on exposed peers after a later correction removes the original
link, and survives checkpoint replay. `split --frame <named-link-frame.json>` also
joins every supplied link, including uncertain ones. Supply deliberate identity
links, never the broad discovery frame: discovery is not identity evidence.
Articles exposed in the old 935 frame, and their new linked components,
are quarantined from fresh confirmation. Unqualified rows are not silently
excluded. A later edge crossing development and confirmation quarantines the
whole component, never redraws a favorable split. Provisional unknown-membership
quarantine can clear after evidence is completed; exposure/crossing quarantine
cannot. A changed annotation/catalog snapshot blocks old evaluations.

`freeze-development` registers a typed `DevelopmentConfig` against the fixed
partition before confirmation is opened. `predict --config ... --ids ...
--model ... --partition ... --relation ...` produces actual saved-vector
article-neighbor rankings. With `--cluster`, it produces a development-frozen
cosine connected-component baseline, never chooses a cluster count from test
labels. These predictions are not automatic quality claims.

Retrieval evaluation requires independently judged relations for **every**
query/candidate pair in the declared candidate universe, plus positives and
negatives. Unjudged/unresolved pairs are not negatives. Precision@k, recall@k
and binary NDCG@k are reported only on that completely judged universe.
Topic/Event/Story cluster evaluation uses overlapping pairwise co-membership
precision/recall/F1, not ordinary ARI. Pairwise comparison supports equal
multiple memberships; it is not a chance-adjusted Omega score. Reference:
Collins and Dent, 1988, *Omega: a general formulation of the Rand Index of
cluster recovery suitable for non-disjoint solutions*. No all-positive toy
universe can return a falsely perfect accepted evaluation.

### Validation and current scope

The current immutable local epoch is
`corpus/story-dataset-1/checkpoints/main-20261012-1635`.
It is **partial model annotation, not full gold or accepted quality**.
SQLite's consistent read-only backup captured sequence 17,296 and catalogue
revision `5f5b56b4ea0a5adf47847b22476b648ee0c5c971115cf3f2ebcece76641bfa13`.
It contains 14,140 visited articles: 3,976 have resolved catalogue memberships,
9,465 are catalogue-pending and 699 are unresolved. The raw primary decisions
call 13,441 articles annotated; that is not the qualified count.
Another 982 of the frozen 15,122 articles were unvisited.
This adds 3,040 visited articles over the retained `main-20261011-1930` epoch.
The frozen history contains 1,225 article reviews, of which 1,211 still target
the current primary record, and 1,608 distinct judged pairs. Of 214 pair-review
records, 212 pairs have a current independent review.
The 1,026 current article-review conflicts and 96 pair-review conflicts include
unresolved catalogue comparisons. They are not error-rate measurements.

Quality acceptance is held. A 36-item nonblind diagnostic found one concrete
main-body/source-scope failure, S09, and two uncertain parent identities.
That mixed targeted sample is not an archive-wide error-rate estimate. Fresh
blind targeted review and evidence-backed reconciliation remain annotation
coordinator work. Later review receipts cannot retroactively qualify this
frozen epoch. Required unavailable sources and transcripts stay uncertain.
The protected twenty-source review still needs its owning coordinator's
completed reader and import; this checkpoint does not assert that it passed.

The epoch keeps full history, canonical catalogue, submission bindings,
vector metadata and exposure settings. An empty ignored index replays its
exact file hashes and bindings. Omitted discovery frames and their active
settings remain explicit rather than being silently restored. It contains
no live SQLite index, worker directory, models, raw arrays or captures.
`replay-receipt.json` records exact typed file, submission binding, record
payload and sequence equality after replay into an empty ignored index.
The checkpoint hash is
`54f925c0f5236ca79fc3dbfa97b4770fbeb4209b72d3ba7c098d5f5f18790745`.
The original frozen source and 935 judgments remain byte-identical; those
935 historical judgments are regression evidence, not fresh archive gold.

The annotation index's historical four-control vector registration covers
10,672 common articles. It is separate from the completed pinned MiniLM,
pinned GTE and native Gemma evidence, each covering 15,122 articles.
The already-approved Linux run `38174944453` succeeded; its twenty retained
artifacts supplied 7,352 missing vectors. No new upload or dispatch occurred.
`vector-preparation-receipt.json` ties their rechecked byte hashes and Gemma
128/256/512-dimensional prefix-and-normalization replay to this annotation epoch.
Arrays and weights remain in ignored local evidence, not in this commit.
Jina still lacks 4,430 vectors; its prepared preview grants no outbound approval.

`evaluation-preparation.json` is a typed blocked report with no measured scores.
Catalogue identities are still changing, complete query relevance judgments
are missing, and neither a stable outcome-blind partition nor development
settings are frozen. No partition or relevance judgments were materialized from
this unstable catalogue. Discovery candidates do not establish identity links.
Fresh four-model comparison and any final model/dimension choice remain blocked.
No confirmation results were inspected, settings tuned or production code changed.
These archive checkpoints remain local Git data, not a public archive delivery.

The named real fixture is
`backend/tests/fixtures/story-dataset/approved.json`, with twenty actual approved
source rows and four byte-checked slices of the real saved vectors. Tests
exercise freeze changes, foreign IDs, all-or-nothing import, pending proposals,
catalog review, equal memberships, partial coverage, B10 uncertainty, unchanged
old record bytes, resume, disjoint requests, independent blind reviews, known
probability, rank union, vector conflicts, split crossings, unjudged qrels and
overlapping metrics. Relocation tests preserve old payload bytes, vector bytes,
settings, text/order identities, labels and ranks. They move a generated dataset,
remove its old cache, then reopen and use its saved vectors. Hash changes,
nonportable paths, stale registrations and immutable-output changes fail closed.
No test downloads a model or calls a label service.

Run `status` for current annotation counts; primary workers may be active.
Seed definitions and passing fixture tests are not full-archive annotation or
evaluation. Status distinguishes
visited, annotated, unresolved, catalog-pending, reviewed and unvisited rows.
All 15,122 rows must eventually have a qualified annotation or a reasoned
unresolved state. Quality acceptance, audit sufficiency and a meaningful minimum
encoder difference are not yet owner-approved.

```mermaid
flowchart TD
  F[Exact local source freeze] --> W[Blind resumable primary batches]
  W --> P[Unresolved or proposed identities]
  P --> C[Explicit catalog review and aliases]
  C --> R[Independent targeted and random review]
  F --> A[Probability stream plus separate challenge acquisitions]
  A --> J[Independent pair evidence judgments]
  C --> S[Fresh Event and article components]
  J --> S
  S --> D[Freeze development settings]
  D --> E[Complete qrels and overlapping-membership pilot evaluation]
  E --> B[Report blockers and unapproved acceptance]
```
