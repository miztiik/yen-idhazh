# Plan 63 - Topics, events and stories the pipeline finds for itself

**Last Updated**: 2026-10-08

**Level**: 5 (CLAUDE.md section 6). The work adds persisted shapes - an event
group, a topic, a story edge - and changes what the reader sees. No row of this
plan writes one yet: rows R1 to R8 measure, and the owner rules on the shapes
before any row declares one.

**Status**: written 2026-10-08 from a research session that read eight papers
and the current corpus. It supersedes nothing: `TODO/unsupervised-topic-
detection-event-clustering.md` stays where it is and this plan sits beside it,
per the owner's ruling of 2026-10-07. Checked against `origin/main` at
0c6b69015.

**Why this plan exists.** The pipeline groups two articles as one story when
their summaries sit at cosine 0.94 or above inside 36 hours. On the 45 published
days that rule grouped 212 articles out of 15,122 - **1.4 percent**. The other
98.6 percent each stand alone. A rule that strict finds near-identical reposts
and nothing else, which is why the same wire story from five Indian outlets
still reads as five stories. The feed's whole promise is that a reader sees each
story once.

## 0. Operating contract

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | 1.4 percent of published articles are grouped. The rest stand alone, including wire copy republished by five outlets on the same day |
| A2 | Hard scope - in | Measure what the corpus can support (R1-R8). Build a human-validated set of event groups (R14). Replace the single cosine rule with several kinds of evidence combined so that any weak one vetoes the group (R4, R5). Find topics from the data instead of from a hand-written list (R8). Carry a group's identity from one run to the next so the reader's view does not reshuffle (R9-R15) |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | Measure first, on the runner, with no labels. Then build the validated group set, because every later number needs it. Then one small learned model, not fifteen hand-set numbers |
| A6 | Execution | Owner carries the plan. Rows R1-R8 need no labels and no owner decision, so they run first and in parallel where they touch different files |

### Hard scope - out

Table B - what is out, and what would bring it in

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Fine-tuning a sentence encoder on this corpus | The encoder keeps whatever separation it was trained with. Two papers that tried it had 12,233 labelled articles across 593 events and still watched one fine-tuning objective score **worse** than no fine-tuning at all | Three things together: the validated group set (R14), three months of corpus, and a measured baseline showing headroom. The corpus grows daily, so this is a date and not a refusal |
| B2 | Predicate frames - a record binding an actor to an action and a target | Two reports that reverse the roles - "X sues Y" and "Y sues X" - look alike to every other channel | A relation extractor measured on these summaries. The zero-shot entity models name spans, not roles; the earlier design document admits this itself |
| B3 | Resistance to a coordinated attempt to move a group's meaning | Nothing defends against an attacker who feeds the pipeline shaped stories over weeks | The source list stops being a curated set of 136 domains. Until then the threat is accidental, not deliberate, and R4 covers the accidental form |
| B4 | A story that spans months - its shape, its main route, its branches | The reader sees grouped events and no thread between them | Six months of published days. At 45 days a story that long cannot be seen, so it cannot be checked. R19 records the evidence now so the thread can be drawn later without re-reading the archive |
| B5 | Cross-table integrity manifests, replica validation, partial-coverage publication | A run that half-finishes leaves state nobody validated | More than one machine writing state. One runner writes one run |

### ESCALATE triggers

Table C - when to stop and ask

| # | Trigger | What happens |
| --- | --- | --- |
| C1 | A row would declare a persisted shape - a model under `backend/idhazh/contracts/` | Stop. The owner rules on a persisted shape (CLAUDE.md section 0) |
| C2 | A measurement refuses the intent, for example no encoder separates these summaries | Report it as a finding with options, never as a veto (CLAUDE.md section 0d) |
| C3 | A row would publish a reader-facing grouping before R14 validates it | Stop. An unvalidated group shown to a reader is a claim nobody checked |
| C4 | A measurement is taken on hardware that is not the runner and then quoted as a runner number | Stop and re-run on the runner (Guardrail #2) |

## 1. What the corpus holds

Measured 2026-10-08 from the committed digest archive at
`frontend/public/digest/`, read by `scratch_extract_items.py`.
**Taken on a laptop, not the runner** - these are counts, so the hardware does
not change them. Timings are not in this table for that reason.

Table D - the corpus as committed

| # | Measure | Value | What it means |
| --- | --- | --- | --- |
| D1 | Published days | 45 | 2026-08-23 to 2026-10-05 |
| D2 | Item rows across days | 15,150 | What the archive holds |
| D3 | Distinct articles | **15,122** | Only 28 articles appear on more than one day. The archive is one row an article |
| D4 | Articles a day | 337 average | A 7-day window holds about 2,360 articles |
| D5 | Registrable domains | 136 | The five heaviest are Indian outlets that republish the same wire copy |
| D6 | Summary length | median 78 words, p10 55, p90 124 | Long enough to embed. Short enough that one missing fact matters |
| D7 | Blank summaries | 0 | Every article has one |
| D8 | Blank titles | 0 | Every article has one |
| D9 | Publication time from the feed | 11,352 of 15,122, **75.1 percent** | Trustworthy |
| D10 | No publication time at all | 3,721, **24.6 percent** | A quarter of articles cannot answer when they were published |
| D11 | Publication time from first sight | 49, 0.3 percent | Ingest time wearing a publication label |
| D12 | Articles grouped as one story today | **212, which is 1.4 percent** | The reason this plan exists |
| D13 | Published vectors | 384 numbers an article, stored as whole bytes | A compressed form. Guardrail #2 caps the site at 1 GB and this is how the vectors fit |

**What D10 decides.** A quarter of articles cannot say when they were
published. So time cannot be a requirement for grouping, and a 36-hour window
silently mistreats them. Time earns one job in this design and no other:
**it breaks a match that meaning alone would make, and only when both articles
have a resolved occurrence time that disagrees.** A funding round six months ago
and a share sale today read alike; only a real date separates them. Unknown time
is neither agreement nor conflict, and the channel is skipped rather than
guessed.

## 2. What the papers settled

Eight papers, read 2026-10-07. Short names are this plan's, for citation.

Table E - the papers and what each one decides here

| # | Short name | Paper | What it settles |
| --- | --- | --- | --- |
| E1 | NewsLens | Laban, P. and Hearst, M. "newsLens: building and visualizing long-ranging news stories." Events and Stories in the News Workshop, ACL 2017. <https://aclanthology.org/W17-2701.pdf> | Overlapping windows give link, split and merge for free. A keyword graph plus community detection separates two crowds that share one accidental link. Honest about coverage: their strict setting grouped **10 percent** of articles |
| E2 | EntityBERT | Saravanakumar, K.K., Ballesteros, M., Chandrasekaran, M.K. and McKeown, K. "Event-Driven News Stream Clustering using Entity-Aware Contextual Embeddings." EACL 2021. <https://aclanthology.org/2021.eacl-main.198.pdf> | Word counts plus a timestamp score **91.7** out of 100 on a standard set, against **94.8** for the full neural stack - so the expensive part buys 3 points. Entity awareness as a yes-or-no flag beats one flag a type by more than 2 points. Fine-tuning on the wrong objective scores **worse than no fine-tuning** |
| E3 | TimeBERT | Jiang, H., Beeferman, D., Mao, W. and Roy, D. "Topic Detection and Tracking with Time-Aware Document Embeddings." arXiv:2112.06166v2, March 2024. <https://arxiv.org/html/2112.06166v2> | Folding the timestamp into the vector beats keeping it apart, **+14 points** on one set. Their gain comes from recurring events - two daily stock reports months apart. Needs months of corpus to learn that, which is B1's reason |
| E4 | StoryForest | Liu, B., Niu, D., Lai, K., Kong, L. and Xu, Y. "Growing Story Forest Online from Massive Breaking News." CIKM 2017. arXiv:1803.00189v1. <https://arxiv.org/html/1803.00189v1> | Two layers of grouping - keywords first, then documents - lift purity from **0.55 to 0.96**. Their reviewers rated a tree **82.8 percent** correct edges against **32.9 percent** for a free-form graph |
| E5 | NarrativeMaps | Keith Norambuena, B.F. and Mitra, T. "Narrative Maps: An Algorithmic Approach to Represent and Extract Information Narratives." arXiv:2009.04508v2, 2020. <https://arxiv.org/html/2009.04508v2> | Combine parts with a geometric mean, not an average, so any weak part drags the whole to zero. Pick the main route as the highest-scoring path. Pick one representative a storyline using a standard graph result, with no cutoff to argue about |
| E6 | ContrastTL | Duan, Y., Jatowt, A. and Yoshikawa, M. "Comparative Timeline Summarization via Dynamic Affinity-Preserving Random Walk." ECAI 2020. <https://adammo12.github.io/adamjatowt/ecai20.pdf> | Importance has two scales: important inside one time window, and important across many |
| E7 | TLS-Bench | Gholipour Ghalandari, D. and Ifrim, G. "Examining the State-of-the-Art in News Timeline Summarization." ACL 2020. arXiv:2005.10107v1. <https://arxiv.org/html/2005.10107v1> | Automatic scores **reward repetition**. Forcing their timelines to repeat less made every score worse. A warning for any self-tuning loop |
| E8 | Survey54 | Keith Norambuena, B.F., Mitra, T. and North, C. "A Survey on Event-based News Narrative Extraction." ACM Computing Surveys, 2023. arXiv:2302.08351. <https://arxiv.org/pdf/2302.08351> | Screened 900 papers, kept 54. Entity use across the field "remains limited in scope". **No benchmark exists** for grouping at the article-set level - a gap this project could fill |

All eight were read in full on 2026-10-07, not read about. E1 and E2 came from
the owner first, E3 and E4 second, E5 to E8 third. The ninth input is this
repository's own `TODO/unsupervised-topic-detection-event-clustering.md`, which
is the design these papers were read against.

**No paper here chooses an encoder.** E2 and E3 use BERT-family models from 2019
to 2021 because that is what they had; their finding is about *what to do with*
an encoder - add entity awareness, add time - not about which to buy today. The
encoder choice is row R2's to measure (Table G, G3), and nothing in this table
settles it.

**What they agree on, which is the part worth trusting.** Seven of the eight use
the headline or the opening lines as the unit of meaning. Four replace a
hand-set threshold with one small learned combination. Four put entities in the
representation instead of scoring them on the side. Two warn that a time penalty
wrongly kills a story that goes quiet and comes back. Three say: store a
flexible shape, show a simple one.

## 3. The design

```
LLM, slow, kept for this and nothing else
  article  ->  summary, and which kind of picture suits it

fast, repeatable, same answer every run
  summary  ->  entities, typed
           ->  sentences, word stems, and who-did-what
           ->  one vector of meaning
           ->  word counts

six kinds of evidence for a pair of articles
  meaning . word overlap . entities . places . action . time
                    |
          geometric mean - any weak one vetoes
                    |
  pairs -> graph -> communities  ->  EVENTS     7-day window, every run
                    |
  entity and word co-occurrence ->  TOPICS      whole corpus, weekly
                    |
         FEED, one card an event      GRAPH, topics and their links
```

Table F - why each channel is there

| # | Channel | Where it comes from | What it catches that the others miss |
| --- | --- | --- | --- |
| F1 | Meaning | One vector a summary | Two reports of one event written in different words |
| F2 | Word overlap | Word counts over the summary | An exact figure or an unusual name the vector smoothed away |
| F3 | Entities | A typed entity model | Who and what. Weighted so a rare name counts more than a common one |
| F4 | Places | The same model, place types only | Where. Two strikes, Paris and London, read alike without it |
| F5 | Action | Sentence structure of the first sentence | What happened. "Police arrested a suspect" against "police attended a protest" share every entity and every place |
| F6 | Time | A resolved date, when there is one | Separates a recurrence from its earlier twin. Skipped when either side is unknown (D10) |

**Why a geometric mean and not a weighted sum.** A weighted sum lets a strong
meaning score hide a zero somewhere else - which is how "X sues Y" and "Y sues X"
end up in one group. A geometric mean is zero whenever any part is zero, so a
single piece of contrary evidence stops the group on its own. That replaces
three mechanisms in the earlier design - a score, a verification step and a veto
list - with one number (E5).

## 4. Status reckoner

Rows R1 to R8 need no labels, no owner decision and no new dependency. They run
first.

| # | Row title | Depends-on | Status | Note |
| --- | --- | --- | --- | --- |
| R1 | How many articles are grouped today | - | **DONE** | 1.4 percent (D12) |
| R2 | Which encoder separates these summaries best, measured on the runner | - | IN PROGRESS | First attempt scored encoders on different scales and was wrong; second attempt uses a rank score. Must run on the runner (C4) |
| R3 | Typed entities and sentence structure over all summaries | - | TODO | Two layers: an entity model for who and where, sentence structure for what happened |
| R4 | Tell a republished story from an independently reported one | - | TODO | Domain, near-identical meaning, near-identical title. A copy adds reach, not weight, and does not restart the clock |
| R5 | Six channels, combined by geometric mean | R2, R3 | TODO | Hand-set weights until R18 |
| R6 | Compare every pair inside the window | R5 | TODO | A 7-day window holds about 2,360 articles. The smallest score inside a group has to clear the bar, so one weak pair blocks it |
| R7 | Does the grouping agree with itself | R6 | TODO | Windows overlap by half, so half the articles are grouped twice. They should land the same way both times. **Needs no labels**, scores any change, and the disagreements are the pairs worth asking about |
| R8 | Find topics in the whole corpus | R3 | TODO | Entity and word co-occurrence, communities that may overlap. A keyword can belong to more than one topic, which a partition cannot express |
| R9 | Carry a group's identity across runs | R6 | TODO | Majority of members came from group T, so it is T. Larger side keeps the name on a split; both names survive a merge (E1) |
| R10 | Two clocks, one for events and one for topics | R9 | TODO | Events move daily, topics over months |
| R11 | A topic's life: starting, busy, fading, quiet | R10 | TODO | Counted on events arriving, not articles, so republished copy cannot fake vitality |
| R12 | A topic becomes visible only after it holds still | R11 | TODO | Enough events, enough days, enough runs. Otherwise every outlier is a node in the reader's graph |
| R13 | A quiet topic can come back | R11 | TODO | Similar meaning, far apart in time. The air-crash case: new evidence years later |
| R14 | **Event groups, validated by a person** | R6 | **TODO - blocks everything measured** | I group, the owner marks each group keep, split or join. About 2,000 groups covering about 12,000 articles, worth 5,000 to 6,000 confirmed same-event pairs |
| R15 | Identity that survives a re-run | R9 | TODO | The repository already derives an article's identity from its address. Groups need the same |
| R16 | Set aside the judge's existing answers | - | TODO | They were only ever asked about pairs that already looked alike, so they cannot show the error that matters: two reports of one event written differently |
| R17 | Ask the judge where the grouping is unsure | R7, R14 | TODO | Replaces the fixed band. The disagreements from R7 are the questions worth paying for |
| R18 | One small learned combination, six numbers | R14, R17 | TODO | Replaces about fifteen hand-set numbers |
| R19 | Record what a story thread would need | R6 | TODO | Later sentences of one summary echoing another's first sentence; action changes; time gaps. Recorded now, read in six months (B4) |
| R20 | Scores that need the validated set | R14 | TODO | Includes one that weights every group equally, because the common one is dominated by large groups and hides a split small one |
| R21 | A repetition score | R6 | TODO | Guards R18 from tuning itself toward repetition (E7) |

## 5. Open questions

Table G - what the owner still decides

| # | Question | Why it matters | Recommendation |
| --- | --- | --- | --- |
| G1 | Does sentence structure come from the parser that was tested as noisy, or another? | Without it, reversed roles and denials have no cheap detector (B2). The noisy test may have been the small model; the large one is a different thing | Measure the large one on 200 summaries and show the owner the rate before deciding |
| G2 | How many groups can the owner validate in a week | R14 blocks every measured number | About 2,000 groups, over-grouped on purpose so the work is mostly splitting, which is quicker than hunting for a missed merge |
| G3 | Which encoders go in the runner comparison | R2 | Table H. No paper read here settles it, and the one trial so far was run on a laptop and scored wrongly (C4) |
| G4 | May the plan commit work that rebuilds vectors for every published day | A better encoder means re-reading 45 days | Yes, once. The published form stays compressed for the site; the grouping reads the full-precision form inside the run |

### The encoder shortlist

Table H - what R2 measures on the runner, and why each is in it

An encoder turns a summary into a list of numbers so two summaries can be
compared. The current one dates from 2021 and is the smallest in common use.
**No paper in Table E chooses one**, so this list is argued from the shape of
this job, not borrowed: English only, short text of about 110 word-pieces,
4 shared processor threads, no graphics card, and a six-hour job that also has
to summarize the day.

| # | Encoder | Numbers an article | Size | Why it is in the list |
| --- | --- | --- | --- | --- |
| H1 | `sentence-transformers/all-MiniLM-L6-v2` | 384 | 22M | What runs today. Every other row is read as a gain or a loss against it |
| H2 | `BAAI/bge-base-en-v1.5` | 768 | 110M | A widely used mid-sized English model. Known to pack unrelated pairs close together, which is a problem for a fixed cut-off and not for a rank score |
| H3 | `thenlper/gte-base` | 768 | 110M | Same size as H2, trained differently. Two models of one size tell us whether size or training is doing the work |
| H4 | `intfloat/e5-base-v2` | 768 | 110M | Same size again. Needs a short prefix on its input; getting that wrong silently costs quality, which is itself worth proving on our own data |
| H5 | `BAAI/bge-large-en-v1.5` | 1024 | 335M | Three times H2. The owner has approved the larger published size, so the question is whether the extra time fits the job |
| H6 | `BAAI/bge-m3` | 1024 | 568M | The one with a different shape: it returns a meaning vector **and** word weights from a single pass, which is channels F1 and F2 from one model instead of two. Five times H2 in size, and multilingual weight we do not need |

**On H6.** It is the model most often named when people ask for "the best", and
it may well not win here. It carries languages this corpus never uses, and its
long-text ability is wasted on a 78-word summary. Its one real attraction is
that it could collapse two channels into one pass. That is worth a measurement
and not an assumption.

**What R2 reports for each row.** How well it separates - the chance that it
scores a same-event pair above a different-event pair, which no difference in
scale can distort. How wide its spread is, because an encoder that puts every
unrelated pair at 0.46 leaves less room for a decision than one that puts them
at 0.11. How many seconds for 15,122 summaries on four threads. And peak memory,
against the 16 GB the runner has.

## 6. Design rationale

**Measure before building.** The 1.4 percent figure was available in the
committed archive the whole time and settles more than any paper does: this is
not a tuning problem.

**The summary is the only text, and that is a choice.** The source body is not
kept; only the address is. So the pipeline's own de-hyped summary is the unit of
meaning. Seven of eight papers use a headline or opening lines instead, but they
had no such summary available - a neutral restatement that keeps names and
figures and drops the adjectives is what those papers were approximating. The
risk runs the other way: one model writing in one voice may make two different
events read alike. R2's rank score is what would show it.

**Unknown is not a value.** A quarter of articles have no publication time
(D10). The earlier design says unknown time is neither a match nor a
contradiction, and the data makes that a requirement rather than a nicety.

**One number with a veto beats three mechanisms.** A score, a verification step
and a veto list all answer the same question. A geometric mean answers it once
(E5).

**Consistency can be measured without truth.** Half of each window's articles
appear in the next window. They should be grouped the same way both times. That
is not proof of correctness - grouping everything together is perfectly
consistent - so it is read beside coverage and group-size spread, and the three
together are hard to fake (R7).
