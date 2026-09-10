# Search Quality

**Last Updated**: 2026-09-10

Whether the archive's on-device search finds the right story: the metric, the
label set, the bar it has to clear, and what it costs to keep that bar honest as
the archive grows.

**This is a different instrument from [evaluation.md](evaluation.md)**, which
asks whether a published summary is faithful to its article. The two share no
data, no metric and no config: this page backs `assist.recall_min` and the
similarity floor, where that one backs the confidence bands. A person arrives
holding one question or the other and never both.

Everything above scores a summary. This section scores a different promise: that
a reader who searches the archive on their own device gets back the items they
were looking for. Until 2026-08-26 nothing measured it at all, and the only
thing that looked like a measurement - five hand-written queries driven through
a browser - is a wiring check. At n=5 the standard error at recall 0.8 is 0.18,
so it cannot see a ten-point regression. It stays exactly what it is and its bar
is never raised.

The instrument is [`backend/idhazh/evals/retrieval.py`](../../backend/idhazh/evals/retrieval.py),
run by the backend test suite. It is not a browser test. The quality question
has nothing to do with a browser, and the browser path pays the whole encoder
download on every run.

## Two tiers, and only one of them exists today

**Tier one is free and needs no labeller.** One query per entity slug carried by
three or more items; the relevant set is exactly the items carrying that slug.
Nobody's judgement is in it, so nothing can bias it, and it fires the moment the
encoder or the committed vectors break.

It produced **zero queries** for its first five days, because no published item
carried an entity slug. `DigestItem.entities` is copied from `Article.entities`
and no stage in the pipeline ever wrote that field - nor `lenses`, nor `events`.
Three declared taxonomy dimensions were empty on every committed item.

**A deterministic tagger now writes all three (2026-08-26).** The rule and its
measured coverage live in
[`../architecture/sources/discovery.md`](../architecture/sources/discovery.md).
What it means for this tier, measured on the committed corpus by running the
real `entity_queries` over items the matcher had tagged: **0 queries becomes
25**, covering **616 of 2,237 items**, from `entity-asml` at 3 items to
`entity-google` at 105.

**That is what the corpus supports, not what the tier reports today.** The
tagger only touches items published from now on; no committed payload was
rewritten, so the tier stays at zero and climbs as new days land. Read the 25 as
the instrument being live rather than as a score.

Two properties of the tier survive the change and are worth restating, because
they are why it was built before it could fire: the relevant set is exactly the
items carrying the slug, so no labeller can bias it, and a slug is assigned by a
whole-word match on a curated alias rather than by a model, so a page cannot
choose which query it answers.

**Tier two is 60 hand-labelled intent queries** in
[`tests/fixtures/search/retrieval-queries.json`](../../tests/fixtures/search/retrieval-queries.json),
carrying 297 relevance judgements. A query is a question in a reader's words; the
relevant set is every published item that answers it, addressed by
`(date, item_id)` because an item id is unique only within a day and is reused
across days. Relevance is binary and a query has many right answers on purpose: a
topic question does, and single-gold labelling makes a working system read as
broken.

No model wrote, ranked or selected those queries. The digest's own summarizer is
the thing being retrieved, so letting it generate the query set would be
LLM-as-judge under another name (`CLAUDE.md` section 0a).

## recall@10 is the gate; reciprocal rank is a diagnostic

The surface is a flat capped list with no rank cue. Rewarding first place would
measure a claim the product does not make, so mean reciprocal rank is computed,
reported, and never gated on.

**The denominator is capped at the ten slots that exist.** A topic query has more
right answers than a ten-item list can hold, so `found / len(gold)` would report
a retriever that filled every slot correctly as a failure, and would move the
score whenever a labeller was generous. `found / min(gold, 10)` asks the question
the surface can answer: of the right answers you could have shown in the slots
you have, how many did you show. The uncapped figure is reported beside it.

**A miss and an absence are different failures, and conflating them makes the
instrument lie.** An item with no vector cannot be retrieved at any threshold.
Every result therefore carries two numbers: the reader-facing one over all
labelled answers, and the ranking one over the answers that carry a vector. Only
the second is gated (`assist.recall_min`), because failing this gate for a gap in
the embedding stage would point at the wrong code.

## The baseline, 2026-08-26

Measured on `onnxruntime` 1.29.0, against the
committed archive after the vector backfill - 2,121 published items of which
2,119 carry a vector (99.9%), 60 queries, floor 0.35, ten slots.

| Number | Value | What it says |
| --- | --- | --- |
| recall@10, all labelled answers | **0.767 +/- 0.036** (n=60) | What a reader gets today. |
| recall@10, answers that carry a vector | **0.767 +/- 0.036** (n=60) | The same number now. |
| Queries with no embedded answer at all | 0 of 60 | Every question is answerable. |
| Coverage of labelled answers | 100% | The coverage failure is closed. |
| Mean reciprocal rank | 0.842 | Diagnostic. A found answer is usually first. |
| Filled slots holding an unjudged item | 65.6% | Why the number above is a lower bound. |

**The coverage failure is fixed and the ranking number fell, and neither of
those is a surprise once you hold one thing constant at a time.** The bar was
0.85, set from 0.931 on an archive where 44.5% of items carried a vector. The
backfill took that to 99.9% and the gate failed at 0.767. Four measurements,
same 47 queries, same labels, same ranking code, separate the causes:

| Arm | recall@10 | Effect |
| --- | --- | --- |
| A - archive before the backfill | 0.902 +/- 0.036 | the old baseline, reproduced |
| A' - same 944 items, today's re-encoded vectors | 0.910 +/- 0.034 | re-encode **+0.007** |
| B - whole archive, old labels, old denominator | 0.761 +/- 0.055 | competition **-0.142** |
| C - whole archive, as gated | 0.743 +/- 0.042 | denominator **-0.018** |

**There is no ranking regression.** Holding the corpus to the same 944 addresses
and swapping in the re-encoded vectors moves the number *up* by 0.007, which is
a fifth of a standard error. The entire drop is 1,175 items that the index could
not see before, now competing for the same ten slots, plus a denominator that
grew with coverage: the summed ceiling over those 47 queries went from 85 slots
to 246.

**The 0.767 is a lower bound on recall, not recall.** The labels were pooled
from an index that could see 44.5% of the corpus, so a right answer with no
vector could not be found by the labeller and could not be labelled. It can be
retrieved now, and the metric counts it as a wrong answer. Measured: of the 382
unlabelled items occupying a slot, 212 - **55.5%** - were unembedded on
labelling day. `crude-oil-price` scores 0.000 and is the clearest case: the five
items above its gold are US commercial crude inventories, record US crude
production, EIA crude stocks, Q2 petroleum market volatility and the Brent
price. Every one of them answers the query's own written intent, "items about
crude output, crude imports or the crude price". None of them is labelled. The
labels are incomplete, not wrong, and no label was changed to raise the score.

**This is pooling bias, and it is the correction the earlier text got wrong.**
The previous version of this page said the number "drifts down as the archive
grows, and that is correct", on the reasoning that a new day can only add
distractors. The measurement says otherwise: most of what takes a slot from a
labelled answer is another right answer nobody judged. So the drift is partly an
artifact, and the bar will keep sliding for a reason that is not a regression.

**The instrument prints its own blindness on every run.** `RetrievalReport`
carries `unlabelled_share` - the share of filled slots holding an item no
labeller judged either way - and a test asserts it is above zero, so the day the
labels catch up somebody is told to delete this caveat.

## Moving search to the month index cost nothing, 2026-08-27

The archive stopped carrying every committed day and started fetching
`index/<YYYY-MM>.json` with its sibling vector file. That is 1.7 MB off
the page, and the question a byte saving can never answer on its own is whether
the index lost information the day payload carried.

Measured on the same checkout, same 60 queries, same labels, same ranking, same
embedded queries - the only difference is which file the vectors came out of:

| Arm | recall@10 | MRR | Corpus |
| --- | ---: | ---: | --- |
| Day payloads, the surface being deleted | 0.756 +/- 0.037 | 0.816 | 2,235 of 2,237 carry a vector |
| Month index, the surface being shipped | 0.756 +/- 0.037 | 0.816 | 2,235 of 2,237 carry a vector |

**Identical to three decimals on every number the report carries.** That is the
expected result rather than a lucky one: the index projects the same int8 bytes
the day payload held, and it decodes them with the `scale` its own header states
rather than a constant, so nothing about the arithmetic changed.

**The reader-facing number moved from 0.767 to 0.756, and the index is not
why.** The baseline above was taken over 2,121 published items; this checkout
holds 2,237. Both arms moved together, which is exactly the pooling drift the
paragraphs above predict - 116 more items competing for the same ten slots
against a frozen label set, and 66.6 percent of filled slots now hold an item no
labeller judged, up from 65.6 percent. 0.756 is 0.3 standard errors under the
baseline and 0.066 above the `assist.recall_min` bar of that day, which was
0.69. The bar has since moved to 0.61 for the reason the next section gives.

`backend/tests/test_retrieval_eval.py` holds the comparison rather than this
page: it fails when the two arms disagree by more than one standard error, so
the day the index starts losing something, a gate says so instead of a byte
count looking like a win.

## The archive grew into the bar, 2026-08-31

The eleventh published day landed and the gate failed at **0.68978 against a bar
of 0.69** - short by 0.00022, which is one percent of one standard error. The
drop is real and it is not the ranking. The same four arms as 2026-08-26, over
the same 60 queries, the same labels and the same ranking code, on,
`onnxruntime` 1.29.0, alone on the machine:

| Arm | recall@10 | Effect |
| --- | --- | --- |
| A - the archive at the last green commit, 3,485 items | 0.69163 +/- 0.04092 | that baseline, reproduced |
| A' - the same 3,485 items, today's vectors | 0.69163 +/- 0.04092 | re-encode **+0.00000** |
| B - the whole 3,596-item archive, old denominator | 0.68978 +/- 0.04124 | competition **-0.00185** |
| C - the whole archive, as gated | 0.68978 +/- 0.04124 | denominator **+0.00000** |

**There is no ranking regression, and A' is the arm that says so.** Reading the
same 3,485 addresses with today's committed vectors gives the identical number
to five decimal places, because **0 of the 10 older day payloads changed a
byte** - published days are immutable and the hashes prove it. The whole
-0.00185 is 111 new items competing for the same ten slots against labels pooled
on 2026-08-26. **70.8 percent of filled slots now hold an item no labeller
judged**, against 65.6 percent then, so most of what takes a slot from a
labelled answer is another right answer nobody judged.

**The denominator cannot move any more, which is the one thing that changed
since 2026-08-26.** Then, coverage went from 44.5 percent to 99.9 percent and
the summed ceiling grew from 85 slots to 246. Now the label set is frozen and
every labelled answer already carries a vector, so the ceiling is 294 slots in
both arms and B equals C exactly. Competition is the only mechanism left.

**The slide has a rate, and the rate is the point.** Measured over all eleven
committed days on one instrument in one run - the eleven points, their corpus
sizes and the fit are in
[../reference/measurements-site.md](../reference/measurements-site.md#how-fast-archive-search-slides-under-a-frozen-label-set) -
recall falls **0.0134 for every published day** and **0.0000479 for every
published item** once the labels close on 2026-08-26. The series reproduces the
record: its 2026-08-26 point is 0.75571 over 2,237 items, against the 0.756 over
2,237 items in the section above.

## The bar, and what it is worth

`assist.recall_min` is **0.68**, two standard errors below the pinned baseline of
0.756 +/- 0.037 (n=60) over the 2,237 items published through 2026-08-26, of
which 2,235 carry a vector: `0.756 - 2 x 0.037 = 0.682`, rounded to two places
the way 0.69 and 0.61 were. It catches what a bar is for: a ranking change that
costs more than about eight points fires it.

**The bar no longer has an expiry date, and that is the whole point.** Three
earlier versions of this number - 0.85, then 0.69, then 0.61 - each expired
within days, and each time the diagnosis was that the bar had been set wrong.
The bar was never the problem. **The gate was scoring the ranking and the
publishing rate at the same time**, and only one of those is something a merge
candidate can change.

The mechanism, stated once so it is not rediscovered a fourth time. The result
list holds ten slots. The gold set is frozen at the labelling date. The
competitor set was the whole live archive, growing about 654 items a day. Every
new item that outranks a gold item **evicts** it, so the numerator erodes while
the denominator, `min(gold_with_vector, slots)`, does not move at all. Measured
at **-0.00004793 recall per published item**, which is 0.031 a day: **one
publishing day moved the instrument 39 percent of the eight-point effect the
gate exists to catch, and three days exceeded it with no code change.** No
constant bar survives that, which is why the gate failed twice in five days -
the second time on a commit that changed one markdown file.

**`assist.eval_corpus_through` is the fix.** The gate scores against the corpus
as it stood on the labelling day, so both inputs are fixed and `recall_min`
measures ranking alone. The live whole-archive number is printed beside the
gated one on every run, because that is what a reader actually gets: 0.602 +/-
0.046 over 6,326 items on 2026-09-04. Completing the labels now *raises* the
gated number instead of chasing an eroding one.

Ruled independently by Fowler and Carmack on 2026-09-04, who reached the same
answer from different altitudes. Both also ruled out the alternatives, and the
reasons are worth keeping: **completing the labels is a larger stopgap wearing a
fix's clothes** - it resets the level and the slide restarts the next morning at
the same rate. **A judged-only metric is fatal** - `LabelledQuery.relevant`
carries no negative judgements, so condensing to judged items makes recall 1.0
whenever any gold appears, and the gate would pass forever. **A trend gate
against the previous run stays confounded**, because last run's corpus differs
from this one's.

`assist.recall_tolerance`, added and removed the same day, is the record of the
wrong shape being tried first: a band around a drifting number is a looser bar,
not a stable one, and the arithmetic priced it at 1.8 days.

**A bar with no expiry date is the same defect as a magnitude with no date.**
The previous version of this page said the bar "has about 0.077 of room before
that matters". That room was spent in five days and nobody was watching the
rate, so the gate failed on `main` and blocked every open pull request. The rate
is now measured, and the pin means it no longer applies to the gated number.

**Archive search does clear a defensible bar, and the bar is lower than it
looked.** 0.767 over 60 questions with a fully embedded corpus is an honest
number for a 384-dimension quantised encoder running in a browser, and it is a
floor rather than a ceiling. What is not defensible is the old 0.85: it was
measured on the 37% of the corpus that happened to have vectors, which is an
easier question than the one a reader asks.

**Completing the labels is the fix, and it belongs in its own commit.** Judging
only the items the ranker put in the ten slots would raise recall by
construction - the metric choosing its own ground truth, which destroys the
alarm. A sound re-label pools deeper than the slot count from two retrievers, a
dense one and a lexical one, judges every candidate against the written intent
by one rule, and lands separately so the bar's movement is attributable to
labels or to the system but never to both at once.

**Re-deriving the bar a third time is not an option that is open twice more.**
Each pass costs a pull request and buys about a week, and each one moves the
alarm further from the level a reader actually gets. The next time this gate
fires, the answer is the labels.

## The similarity floor is a selector, measured

Below the floor a result is not shown at all. It is never reported to a reader as
a quality signal, and no page prints a score.

Re-measured 2026-08-26 against the backfilled archive (2,119 embedded items):
**126,843** same-domain non-answer pairs - a real question against a real item
that does not answer it - score a mean of 0.0761, a p95 of 0.2716 and a p99 of
0.3992. The 297 right answers score a p10 of 0.3753 and a median of 0.5314. The
two distributions overlap, so there is no clean cut, and any floor trades a
right answer against a wrong one.

**The noise did not move when the corpus did.** The earlier reading over 34,715
pairs was mean 0.074, p95 0.269, p99 0.399. At 3.7 times the pairs the numbers
agree to three decimal places. The floor therefore stays at 0.35, which is the
p98.12 of same-domain noise.

| Floor | Non-answers surviving | Right answers kept | recall@10 |
| --- | --- | --- | --- |
| 0.20 (was shipped) | 11.68% | 98.7% | 0.770 |
| 0.30 | 3.55% | 96.0% | 0.770 |
| **0.35 (shipped)** | **1.88%** | **93.6%** | **0.767** |
| 0.40 | 0.99% | 85.2% | 0.747 |
| 0.45 | 0.50% | 76.4% | 0.694 |

0.45 would buy silence on every probe below for 0.073 of recall, which is two
standard errors and so a measurable loss. It is not bought.

**A probe stops being a probe when the archive grows into it.** Four off-domain
questions assert that the empty state can fire. One of them, "restoring a 1960s
mechanical wristwatch movement", stopped being off-domain the moment the
backfill made the archive's smartwatch items reachable: it returned a Pebble
Time 2 review at 0.413 and a Garmin deal at 0.360. Those are wristwatches. The
probe is retired and recorded here rather than deleted quietly, and replaced
with "hand-stitching a leather saddle", which scores 0.194. The four now in the
test score 0.235, 0.295, 0.258 and 0.194, so the tightest has 0.055 of margin
under the floor.

**And a probe set can always be softened, so it is not the only assertion.** A
second test scores every query against every item that does not answer it and
requires the floor to clear the p95 of that distribution. No choice of probe
can dodge it, and it fires if the archive ever grows noisier than the selector.

## Design rationale

**The eval lives in the backend suite (2026-08-26).** The browser test that
existed measured whether search runs, not whether it works, and it paid a 43 MB
encoder download to do it. Retrieval quality is arithmetic over committed vectors
and needs no page. Authority: Andre.

**The gate is on the reachable number, and the reader-facing number is reported
beside it every run (2026-08-26).** A gate that fires on another stage's defect
teaches people to ignore gates. A report that hides the reader's experience is
worse. Both are printed by the same test on every run. Authority: Andre.

**The floor moved on evidence, not on taste (2026-08-26).** The estimate before
measuring was 0.35 to 0.45. The measurement put it at the bottom of that range
and said why: past 0.35 the cost in right answers becomes larger than this
instrument's own spread. Authority: Andre, Rule #10.

**The bar was re-derived rather than lowered, and the difference is the four
arms above (2026-08-26).** A gate that fails after a fix landed can be met two
ways: move the number until it passes, or find out what changed. Holding the
corpus, the labels and the vectors constant one at a time showed the ranking had
not moved at all, so 0.85 was never the system's number - it was the number of
an archive with 44.5% of its vectors. Authority: Andre, Rule #10.

**The floor stayed where it was because the noise did (2026-08-26).** The
corpus grew 3.7x in scored pairs and the same-domain noise distribution did not
shift past the third decimal. Raising a floor the measurement says is correct,
in order to silence one probe, is fitting the knob to the test. The probe was
what broke, and it is recorded rather than removed. Authority: Andre.

**The label set is not repaired in the same commit as the bar (2026-08-26).**
Judging only the items the ranker put in the ten slots can only raise recall -
the metric would be choosing its own ground truth, and the alarm would be gone.
A sound re-label pools deeper than the slot count from a dense and a lexical
retriever and lands on its own, so a reader of the history can tell whether the
number moved because the labels moved or because the system did. Authority:
Andre, Fowler.

**The bar was re-derived a second time, and this time the expiry was measured
(2026-08-31).** The first re-derivation set 0.69 correctly and then said only
that it had "about 0.077 of room". Room with no rate is not a fact anybody can
act on: five published days later the room was gone, the gate failed on `main`,
and every open pull request was blocked by it. So the same four arms ran again,
and a fifth measurement ran beside them - recall at every one of the eleven
committed corpus sizes, which turns the room into a date. The bar is 0.61 and it
lasts about six published days. Two things follow. The number is written with
its expiry, in this page and in the field description, so the next failure is
recognised instead of re-investigated. And the second pass is the last one: it
cost a pull request and bought a week, and a third would move the alarm further
from what a reader gets for the same week. Authority: Andre, Rule #10.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Raise the five-query browser fixture's bar and call it the instrument | At n=5 the standard error at recall 0.8 is 0.18. It cannot see a ten-point regression, so raising its bar would buy noise. | Andre |
| Gate on mean reciprocal rank | The result list is flat and capped and carries no rank cue. Rewarding first place would measure a claim the product does not make. | Andre, Jony |
| One right answer per query | A topic query has many. Single-gold labelling reports a working system as broken and makes the number a function of which answer the labeller happened to pick. | Andre |
| `found / len(gold)` with no cap | Twenty right answers cannot fit in ten slots, so a perfect retriever would score 0.5 and a stingy labeller would score higher than a thorough one. | Andre |
| Substitute the vertical for the missing entity slug in tier one | A vertical holds 72 to 168 items, which caps recall@10 at 0.06 and measures nothing. Substituting a different grouping would also manufacture a green number from a dimension the product does not use. | Andre |
| Use an item's own key points as a free query | The summarizer wrote them. A query generated by the model whose output is being retrieved shares its failure modes, which is the LLM-as-judge ban in `CLAUDE.md` section 0a. | Andre |
| Freeze a corpus snapshot into the fixture so the number never moves | It would duplicate 300 KB of already-committed vectors and would stop the eval from noticing the archive. Published days are immutable, so a labelled answer cannot vanish - and a separate test says so loudly if one does. | Fowler |
| Lower the labels or raise the floor until recall passes 0.5 | The brief for this work said not to, and it was right: an instrument that reports bad news is doing its job. | owner |
| Lower `recall_min` until the failing gate goes green | It is the same move as the row above, with a different knob. The bar has to come from a measurement of what the system does now, and that measurement had to separate a coverage change from a ranking change before any number could be written down. **Still refused, and 2026-09-04 sharpened why**: the bar was never the thing that was wrong. The gate was scoring the ranking and the publishing rate at once, so every re-derivation expired on schedule. Pinning the corpus raised the bar from 0.61 to 0.68 rather than lowering it. | Andre |
| Drop the 13 newly answerable queries, or the queries that score worst | The queries did not change; the corpus did. Removing `crude-oil-price` because it scores 0.000 would delete the single clearest piece of evidence that the labels are incomplete. | Andre |
| Count an unlabelled item in a slot as correct because it looks relevant | That is the metric grading itself. Relevance has to be judged against a written intent by a rule applied to every candidate, in a pool deeper than the slots, or the number means nothing. | Andre |
| Raise the floor to 0.42 so every probe returns nothing | 0.42 silences the smartwatch match and does not silence "competitive bridge bidding" matching an offshore wind auction, which needs 0.44 and 0.073 of recall. The floor would be set by whichever probe happened to be written down rather than by the noise it exists to cut. | Andre |
| Assert "at most one hit" per probe instead of none | It converts a promise the empty state makes into a promise it usually makes. Either the archive has nothing close or it does. | Reader |
| Merge with this gate red, or mark it expected-to-fail | A gate that is allowed to fail is not a gate, and it was blocking every open pull request - so the next person's real regression would have arrived in a suite that was already red. | owner |
| Round the derived 0.60731 down to 0.60 rather than to 0.61 | Both are two decimal places. 0.61 is the nearest, and it is the stronger bar, so it is the one that cannot hide a regression the derivation would have caught. The 0.01 costs less than one published day of room. | Andre |
| Stop the gate reading days published after the labels closed | It would hold the number still, and it would measure a 2,237-item archive nobody has searched since 2026-08-26 - so a ranking change that only hurt recent stories would pass. The gate exists to notice the archive. What has to change is the labels, not the corpus. | Andre |
| Gate on the gap between arm A' and arm A instead of on a level | It is the right instrument for "did the ranking regress" and it needs two committed corpora to compare, which the repository does not keep. Building that is a bigger change than this row, and it does not remove the need for the labels. | Andre, Fowler |

## See also

- [evaluation.md](evaluation.md) - the other instrument: whether a summary is faithful to its article.
- [digest.md](digest.md) - what a reader is searching over.
- [config.md](config.md) - `assist.recall_min` and the similarity floor.
- [../architecture/publishing/frontend.md](../architecture/publishing/frontend.md) - the search control and what it downloads.
- [../reference/measurements-site.md](../reference/measurements-site.md) - the index weight and the recall series.
- [../../CLAUDE.md](../../CLAUDE.md) - Rule #10 (measured, not estimated).
