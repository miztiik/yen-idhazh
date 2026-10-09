# Encoder comparison 1

**Built**: 2026-10-08

A measurement, not a dataset. It answers one question for plan 63: of the
encoders that could run on this project's hardware, which one best tells two
summaries of the same event from two summaries of different events.

`readings/encoders.md` is the answer. Read "What the numbers mean" before
quoting one.

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
    SEPARATION["separation<br/>Chance a same-event pair<br/>outscores a different one (0 to 1)"]
    LEAN["ambiguous_lean<br/>Share of uncertain pairs<br/>scored above halfway (0 to 1)"]
    SECOND["related_lean<br/>Share of second pieces<br/>scored above halfway (0 to 1)"]
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

**Only the first two buckets make a separation score.** The other two are
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

Counted over the 44 published days: **488 high-overlap pairs come from one
outlet, against 5,517 from two.**

They were dropped at first and are now their own bucket, scored on the same
vectors and reported beside the rest. They are never folded into separation,
because separation answers *"can you tell one event from another"* and this
asks *"can you tell an update from a new story"*. One number answering both
would answer neither clearly.

What the reading means:

- **Near 1.0** - the encoder scores a follow-up as high as a genuine match. In
  production it will fold every update into the story it follows.
- **Lower** - it keeps some signal, and a grouping rule has something to work
  with.

Nobody has said which of those 488 are one event, so this is not an accuracy
either. Plan 63 row R14 builds the set a person validates, and that one can
settle each pair where a word-overlap rule cannot.

## Who wrote the labels

**Nobody. There are none.** This set has no human judgement in it at all, and
that changes what every number on it means.

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
bucket make a separation score; the middle two are scored on the same vectors
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

### What the middle band reports

Nobody knows whether an uncertain pair matches, so it is never counted right or
wrong. What it reports is a **lean**: the share of those pairs an encoder scores
above the halfway mark between its matching and mismatching averages.

- A **high** lean means the encoder pulls doubtful pairs towards "same". In
  production it will join stories that should stay apart.
- A **low** lean means it pushes them towards "different". In production it will
  leave one story in several pieces, which is the failure the current 1.4
  percent already shows.

Two encoders can separate the easy cases equally well and lean very differently.
That difference is invisible to a two-bucket test and it is the one that decides
what the reader sees.

### What this set cannot tell you

Both outer buckets contain mistakes. Two outlets can write near-identical titles
about genuinely different events, and one event can draw two titles with no
words in common. **So no number here is an accuracy.**

What the stand-in can do is rank. Every encoder scores the identical pairs, so
an encoder that handles the hard cases better scores higher, even though none of
them can be scored absolutely. That is the whole claim.

Plan 63 row R14 builds the set that does carry human judgement. When it lands,
this comparison is worth re-running against it.

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

**Separation** is the one to read. Pick one likely-same pair and one
likely-different pair at random: how often does this encoder score the
same-event one higher? 1.0 is perfect, 0.5 is a coin toss.

It is used instead of the gap between two averages, because encoders put their
scores on different scales. An earlier attempt at this comparison, run on a
laptop, reported `all-MiniLM-L6-v2` ahead of `bge-base-en-v1.5` on a gap of
0.720 against 0.431 - but bge places unrelated pairs at 0.456 where MiniLM
places them at 0.105, so the gap was measuring the scale and not the skill. A
rank cannot be fooled that way.

**Spread** is kept beside it because it decides something separate. Two encoders
can separate equally well while one leaves far more room between the two groups
for a decision to sit in. A compressed scale makes any fixed cut-off harder to
place and more fragile when the corpus shifts.

**Articles a second** was taken on the runner. **It is not a selection
criterion.** A batch is about a thousand articles and gets three hours, so the
slowest encoder measured here finishes in a ninth of its session and the
fastest in a hundredth. Nothing in that range changes whether a batch
completes.

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

**Peak memory** is the whole process against the runner's 16 GB. This one does
bite: the batch also runs the summariser, and a large encoder plus a loaded
language model is where the limit is reached.

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
