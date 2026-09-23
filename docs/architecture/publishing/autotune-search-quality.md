# Autotuning search quality

**Last Updated**: 2026-09-23

**This page is research, not a description of what runs.** Nothing here is built.
It records what search does today, what was measured about it, what was found
wrong, and the shape a person-free quality loop would take. It exists so the
plan that implements it starts from measurements rather than from a fresh
investigation. **It needs a plan-doc, and the design below needs further
refinement before any of it ships.** The open questions are listed at the end
and none of them is settled.

The same ranker serves the front page search box and the archive search, so
this page owns both. It does not own the grouping line that decides two items
are one story - that is
[autotune-content-similarity.md](autotune-content-similarity.md), and it is the
closest working precedent for everything proposed here.

## What search actually does

There is no term matching anywhere in it. Every published story carries a
384-number vector produced by the sentence encoder committed under
`frontend/static/assist/models/all-minilm-l6-v2-quantized/2026-08-22/`. That
path holds the model weights and nothing else - the stories themselves are under
`frontend/public/digest/<YYYY>/<MM>/<DD>/digest.json` and the searchable copy is
`frontend/public/assist/index/<YYYY>-<MM>.json` beside its `.bin` of vectors.

A reader's typed question goes through the same weights. The score is the dot
product of two unit-length vectors, which is cosine similarity: a number from -1
to 1. Anything below `assist.similarity_floor` is dropped, what survives sorts by
score then by most recent then by item id, and the top `assist.result_limit`
show. That is the whole ranker.

It exists twice, and the two copies must move together:
`frontend/src/lib/assist/search.ts` is what a reader runs, and
`backend/idhazh/evals/retrieval.py` is the Python twin that measures it.

## Search is windowed, and the window is a config value

A reader does not search the whole archive. `assist.search_months` is how many
month files a tab reads, newest first. `assist.search_min_days` is a floor: if
the newest month holds fewer days than that, the tab reads one more month file,
and one more only, so a search on the first of a month does not collapse to a
single day. The rule is `readScope` in `search.ts`; `load_index_corpus` in
`retrieval.py` is the copy that measures it.

Measured 2026-09-22 with `search_months` 1 and `search_min_days` 7: the
September file held 21 days, so a reader searched September and nothing else -
7,044 stories.

## What an answer key is, and the two this repository has

An answer key is a list of questions, each paired with the stories that are
correct answers to it. You measure search by asking the questions and counting
how many correct answers came back in the slots the surface has.

There are two, and they are not substitutes.

### The hand-written key: 60 questions, one sitting, frozen

`tests/fixtures/search/retrieval-queries.json` holds 60 questions written in a
reader's words and 297 relevance judgements. One person wrote every one of them
in one sitting. No model wrote, ranked or selected any of it, because the
digest's own summarizer is part of what is being measured.

Keeping it current means a person re-reading every new day and adding
judgements. Nobody has. Measured 2026-09-22: every one of the 297 judged stories
falls between 2026-08-21 and 2026-08-26, and the archive had reached 2026-09-22.
Zero judged stories fall in September, so scoring these 60 questions over the
window a reader actually gets returns 0.000 with all 60 unanswerable.

**That is a fact about the window, not about search.** It is also the reason this
key cannot be the live instrument: it measures one fixed week, forever.

### The self-hydrating key: entity tags, no person

`entity_queries` in `retrieval.py` builds a second key with nobody in the loop.
The question is an entity name; the correct answers are exactly the stories
carrying that tag. A tag is assigned by whole-word match against a curated alias
list, so a fetched page cannot choose which question it answers - which is the
property that lets this run on untrusted input at all (Guardrail #11).

It hydrates itself. A new day adds stories to the questions that already exist.
A new alias adds a question.

Measured 2026-09-23 over the 21 September days a reader searches: **2,874 of
7,044 stories carry at least one tag, across 30 distinct names, and every one of
the 30 reaches three or more stories** - smallest 14, largest `openai` at 680.
Archive-wide it is 3,584 of 11,130.

**Two traps in it, both measured.**

The published month file carries no tags at all. Its entries are `date`,
`item_id`, `title`, `vector` and `vertical`, so `load_index_corpus` hard-codes
the tag set empty. Scored through the reader's own loader this key yields zero
questions today and will tomorrow. **It has to read the day payloads.**

And [search-quality.md](../../concepts/search-quality.md) still says this tier
"stays at zero and climbs as new days land". That was true before the
deterministic tagger landed on 2026-08-26. It is stale, and the measurement
above is what replaces it.

## What each key can see

| id | | Self-hydrating (tags) | Hand-written (60) |
| --- | --- | --- | --- |
| A1 | Needs a person | No | Yes, every day, forever |
| A2 | Catches a broken, swapped or re-quantised encoder | Yes, on live data | Only on the frozen week |
| A3 | Catches missing vectors or a foreign shard | Yes | Yes |
| A4 | Catches a floor set too high to return anything | Yes | Yes |
| A5 | Says whether a reader's own phrasing finds the story | **No** - the question is the tag | **Yes, and only it does** |
| A6 | Covers untagged stories | No - 59 percent of the window | Yes, within its week |
| A7 | Gives a level a bar can be set on | No - a question with 680 right answers cannot be lost | Yes |

Keep both. A6 and A7 are why the hand-written key is not deleted, and A1 is why
it cannot be the daily instrument.

## What was wrong, and what is being removed now

The backend suite carried a second reading beside its gated one. `live_corpus`
in `backend/tests/test_retrieval_eval.py` called `load_corpus` with no bound, so
it opened every published day - 32 on 2026-09-22, one more every day the
pipeline runs. It fed `live_report`, which was printed and never asserted.

Three things were wrong with it.

It scored the day payloads, but a reader searches the month file, so it
measured a collection nobody queries. Nothing asserted its result, so it was not
a test. And it was a parameter of the gate, so a malformed day payload would
turn `test_the_ranking_clears_its_bar` red for something no merge candidate
caused - exactly the failure `CLAUDE.md` section 13 describes.

It was also an expensive proxy. Its stated question was how far the frozen key
had drifted from the archive. That is answerable from the month file names plus
the key's own dates, at fixed cost, without running the ranker over the whole
archive.

**It is deleted, along with the declared growing read that covered it in
[growing-reads.md](../../concepts/growing-reads.md).** What the project gives up
is the whole-archive number as a watchable level - 0.602 on 2026-09-04, falling
at 0.0000479 per story published, which is about 0.031 a day. Nobody acted on
it, because the gate is pinned and the decline is a fitted line rather than a
regression. What genuinely goes is noticing a change in that rate if the
publishing mix shifts, and re-fitting recovers it.

That deletion is the only part of this page that ships today. Everything below
it is design.

## The constraint: no results is fine, bad results are not

This is the ruling that shapes the whole loop, and it inverts what is gated
today.

A search that returns nothing says "nothing in the archive is close to that",
and a reader can act on that. A search that returns four plausible-looking
stories that do not answer the question costs the reader the time to read them
and costs the digest its credibility. The two failures are not symmetric.

So **precision at the filled slots becomes the gated number, and recall becomes
reported-only.** Today it is the reverse: `assist.recall_min` is 0.68 and
nothing gates precision. Precision here means: of the slots the search filled,
how many held a story that actually answers.

The floor is the right knob for an autotuner to move, for one structural reason.
Raising it *removes* a result rather than reordering it, so precision moves
monotonically with it and an empty list stays a valid output. A knob that
reorders can trade one query's win for another's loss with no net direction.

**The floor needs one wall it may never cross downward: the measured noise
level.** Measured 2026-08-26 over 126,843 same-domain pairs - a real question
against a real story from the same corpus that does not answer it - the 95th
percentile is **0.2716**. Four off-domain probes scored 0.235, 0.295, 0.258 and
0.194 against the same corpus, so the tightest has 0.055 of margin under the
current 0.35. At the floor this replaced, 0.20, every one of the four returned a
full list. A floor under the noise makes the empty state a promise the selector
cannot keep.

## The vocabulary moves, and the metric has to survive that

An earlier version of this design carried a hash of the alias list, on the
assumption that the vocabulary is stable and a change to it is an event. **That
assumption is wrong.** Desks, lenses and entities grow and evolve continuously.
Most are derived from articles, but a person may add one with no article in the
corpus yet - so a new name can appear with zero correct answers behind it, and
that is not a defect.

A growing vocabulary breaks a naive comparison: the question set changes between
two runs, so the two numbers are not measuring the same thing. A version stamp
says the vocabulary moved; it does not say the number moved *because* it moved.

| id | Field | What it answers |
| --- | --- | --- |
| B1 | `taxonomy_version`, `watchlist_version` | Did the vocabulary move at all |
| B2 | `query_set_digest` | A hash of the question **ids** scored, not of the alias list |
| B3 | `queries_added`, `queries_dropped` | How the set moved between runs |
| B4 | `score_on_common` | **The answer.** The metric over the questions present in both runs, which holds the denominator still while the vocabulary grows |

B4 is the same move `assist.eval_corpus_through` already makes for the stories:
pin the comparison, report the live figure beside it.

## The persisted metric

Nothing records a reading today. Two things break because of that. Retention
deletes expired published days, so a reading not taken on the day can never be
recomputed. And the console cannot draw a trend without re-running the encoder.

**Where.** `state/search-quality/<YYYY>/<MM>/<DD>/`, named for the ranker rather
than for one of its two surfaces. It serves the front page box and the archive
alike, so `archive-search-quality` would have claimed half of what it measures.

**The filename follows the one-writer-per-path rule**, not a bare `<DD>.json`.
That mechanism is `SEGMENT_NAME` in `backend/idhazh/ledger.py`:
`<run_id>-<attempt>-<job>-<shard>`, where the run id matches the contract's own
pattern, the attempt is what keeps a GitHub re-run from writing the path its
first try took, and the shard is two digits. `idhazh.paths` is what checks that
a committed path has exactly one writer. The mechanism may itself change later;
whatever it becomes, this store follows it rather than inventing a second
scheme.

**Who writes it.** The daily pipeline, after the index is built. Not a person's
verb under `backend/utilities/`, because the window is gone after the prune and
a reading not taken that day is lost. Not a new workflow, because the pipeline
already loads this encoder.

**Candidate fields, recorded and deliberately not frozen.** Freezing a shape
that nothing writes and nothing reads would make every later correction a
breaking change with a migration to write (`CLAUDE.md` section 11). These are
recorded so the plan starts from them, not so it inherits them.

| id | Field | What it lets somebody decide |
| --- | --- | --- |
| C1 | `date`, `run_id` | Which day's archive was measured, and by which run |
| C2 | `window_months`, `window_days`, `window_items` | What was searched, so two readings compare |
| C3 | `items_tagged` | Separates "search got worse" from "fewer stories carried a name" |
| C4 | `queries`, `answers` | Whether a low reading is weak or merely thin |
| C5 | `precision_at_filled`, `weakest_query` | The gated number, and the part that is not ceiling-bound |
| C6 | `recall_capped` | Reported, never gated - see the constraint above |
| C7 | `encoder_ref` | The ruler. Two values inside one window is a change in the instrument, not in search |
| C8 | `similarity_floor`, `result_limit`, `min_items` | The three knobs that move the number while search stands still |
| C9 | B1 to B4 above | Whether a moving vocabulary explains a moving number |

**Do not gate on it at first.** It is ceiling-bound - a question with 680
correct answers cannot be lost - and it has no baseline. Let it write rows for
two weeks, then argue a bar from what it measured. The same discipline the
grouping line went through.

**`min_items` is hard-coded 3 in two tests.** It becomes a config knob before it
is production behaviour (Guardrail #6).

## The judge, and why it belongs in the council

The self-hydrating key answers "did search return the stories carrying this
name". It cannot answer "were these ten results *good*", because the question
text is the tag and the correct answers are defined by the same tagger.

A model verdict can answer it, and `CLAUDE.md` section 1a permits one to run in
a production workflow, score live content and determine publication. The venue
already exists: [llm-council.md](llm-council.md) owns the workflow, the three
verbs, the tenancy protocol and the 6 h arithmetic. The closest working tenant
is the merge-line judge in
[autotune-content-similarity.md](autotune-content-similarity.md).

**The shape, sketched and not designed.** A judging night samples questions from
the self-hydrating key plus a sample of real result lists, asks a model whether
each returned story answers its question, and turns the verdicts into a
precision reading. That reading proposes a floor. The proposal is damped,
step-capped and clamped exactly as
`backend/idhazh/contracts/fitted_similarity_threshold.py` already does for the
grouping line: `previous`, `proposed`, `after_damping`, `applied`, `clamp_kind`,
`clamp_movement`, `held_reason`, `settled`, plus the asymmetric `max_down_step`
and `max_up_step`. That contract is the template; do not invent a second one.

**The wall stays.** A judge may not move the floor below the measured noise
level, whatever it scores. That is a floor on the floor, and it is not the
judge's to move.

**This is not in the current work.** It is written here so the plan that builds
it does not start by rediscovering that the venue, the damping and the clamp
shapes already exist.

## Already true - do not research this again

| id | Path | What it already gives |
| --- | --- | --- |
| D1 | `backend/idhazh/contracts/fitted_similarity_threshold.py` | A working autotuned-threshold row: proposed, damped, applied, clamp kind, held reason, asymmetric step caps |
| D2 | [autotune-content-similarity.md](autotune-content-similarity.md) | Damping, dead zone, step cap, band walls, and a judge that is already a council tenant |
| D3 | [llm-council.md](llm-council.md) | The venue, three verbs, tenancy protocol, the 6 h arithmetic |
| D4 | `backend/idhazh/ledger.py` | `SEGMENT_NAME`, the one-writer-per-path filename; `idhazh.paths` checks it |
| D5 | `backend/tests/test_retrieval_eval.py` | Noise 95th percentile **0.2716** over **126,843** pairs, 2026-08-26; off-domain probes at 0.235, 0.295, 0.258, 0.194 |
| D6 | `backend/idhazh/contracts/knobs/assist.py` | Floor 0.35, `recall_min` 0.68, limit 10, months 1, min days 7, and the pin `eval_corpus_through` |
| D7 | `tests/fixtures/search/retrieval-queries.json` | The 60 questions and 297 judgements, and their six-day span |
| D8 | `backend/utilities/measure_retrieval.py` | The index-coverage read: does the index name every published story |
| D9 | `frontend/src/lib/assist/search.ts` | `readScope` and `searchable`, the two rules the Python twin must match |
| D10 | [search-quality.md](../../concepts/search-quality.md) | The baseline, the bar, the pooling bias, and why recall@10 is a lower bound |

Measured figures worth not re-taking: the one-month window holds **7,044
stories and zero judged answers**; the self-hydrating key covers **2,874 of
those 7,044, across 30 names**; archive-wide **3,584 of 11,130**; the live
whole-archive reading was **0.602 on 2026-09-04** falling at **0.0000479 per
story published**.

## Open questions, none of them settled

1. **How is precision measured without a person?** The self-hydrating key gives
   correct answers but not incorrect ones - a story with no tag is unjudged,
   not wrong. Counting unjudged as wrong makes precision a lower bound, which is
   the same bias the recall figure already carries. Whether that bound is tight
   enough to gate on is unmeasured.
2. **How many questions, and sampled how?** 30 names today, growing. Scoring all
   of them every day may or may not fit the pipeline's budget; nobody has timed
   the encoder over that set.
3. **What does the judge see?** The question, the ten results, and what else? A
   title alone may be too little to judge relevance and a full body is too much
   to fit a night.
4. **What is the bar, and on what evidence?** Deliberately unanswered. Two weeks
   of rows first.
5. **Does the month file need to carry tags?** Reading day payloads works and is
   bounded by the window, but it is a second read of data the index already
   summarises.
6. **What happens to a name with no stories behind it?** A person may add one
   before any article mentions it. It must not read as a search failure.

## See also

- [llm-council.md](llm-council.md) - the venue a judge for this would be a tenant of.
- [autotune-content-similarity.md](autotune-content-similarity.md) - the working precedent: a judged line that fits itself nightly.
- [../../concepts/search-quality.md](../../concepts/search-quality.md) - the measured baseline, the bar, and why the number is a lower bound.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - what a read over a growing collection has to declare.
- [retention.md](retention.md) - why a reading not taken on the day cannot be recomputed.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #10 (measure to decide), #12 (growth is not recurring work), section 1a (what a model verdict may decide).
