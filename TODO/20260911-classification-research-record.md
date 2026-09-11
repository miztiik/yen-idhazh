# Classification research record - the design conversation of 2026-09-10 and 2026-09-11

**Last Updated**: 2026-09-11

Working material under `TODO/`. Not a `docs/` page, not a plan, and nothing here
is a row anybody is executing.

---

## 1. What this records

This is the decision and research record for the design conversation of
2026-09-10 and 2026-09-11, the conversation that produced
[`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md),
[`20260910-24-day-sharded-ledgers-plan.md`](20260910-24-day-sharded-ledgers-plan.md)
and
[`20260910-25-placement-plan.md`](20260910-25-placement-plan.md).
Its job is to let a future agent reconstruct **why** those three plans say what
they say, without the conversation: every decision, who took it and on what day,
the measurement behind it, and the alternatives that were rejected and the
reason each one was rejected. Owner decisions recorded here are authoritative
under [`../CLAUDE.md`](../CLAUDE.md) section 0, which puts user approval above
every rule and every agent.

---

## 2. Owner decisions

Every row is an owner decision taken on 2026-09-10 or 2026-09-11. The date
column says which.

| Decision | Date | Why |
| --- | --- | --- |
| **The `pipeline_fingerprint` is deleted**, as an evaluation gate and as the key of the eval window. A recorded input manifest replaces it and gates nothing | 2026-09-10 | The eval window needs N consecutive run-days at one stamp. In a system where prompts, lenses and verticals change weekly that window never closes, so the gate turns ordinary evolution into a fault |
| **The determinism contract is broken deliberately.** Determinism with a model summary is not a requirement. [`../docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md) is rewritten as a run-inputs page | 2026-09-10 | The page already opens by refusing the claim its title makes - its first section heading reads "`temperature=0` is not determinism" - so the rewrite finishes an argument the page had already started |
| **Two model calls per item, not three.** The element table and every label go in call 1; the summary and the visual plan go in call 2. This amends pseudo-plan decision O43, which fixed the count at two and put the labels in call 1 and the summary in call 2 | 2026-09-10 | A third call does not fit the context window (section 7, Carmack). Two calls was already the ruling; what moved is that the element table joins the labels in call 1 |
| **Budgets are guardrails, not rules.** A band is widened when it binds, never pre-emptively | 2026-09-10 | A pre-emptively widened band measures nothing, and a band nobody may widen turns a measurement into a veto |
| **Every label vocabulary is config, not code.** Change the definition text and the model scores against the new text on the next run | 2026-09-10 | A vocabulary that needs a deploy to change is a vocabulary nobody tunes |
| **Score adjustment is automatic, every run, with no human in the loop** | 2026-09-10 | A person in a per-run loop is a person who stops answering, and the loop then stops |
| **Verticals are in scope for model classification.** The desk the model reads is a new field beside `Article.vertical`, and `Article.vertical` itself cannot move | 2026-09-10 | `Article` validates that `item_id` starts with the vertical (`backend/idhazh/contracts/article.py`, verified 2026-09-11), so the vertical is the published address. A read desk has to sit beside it, not replace it |
| **Auto-promotion of a new vertical or a new lens is BUILT and switched OFF**, behind flags that default false | 2026-09-10 | Building it late is more expensive than building it now and leaving it off; switching it on is one config edit and a person's name against it |
| **Self-consistency is BUILT and switched OFF.** `classification.self_consistency_n` defaults to 1 | 2026-09-10 | Same reason as auto-promotion. At 1 it costs one call, which is what the budget already pays |
| **Non-zero temperature on retry only**, and on best-of-N when best-of-N exists | 2026-09-10 | A retry that perturbs nothing repeats the same failure. The first attempt stays at temperature 0 so the ordinary path does not move |
| **Links may break.** The real world is messy and a dead link is not a defect worth a migration; semantic search is the fallback | 2026-09-11 | A forward-only id change is cheap only if old addresses are allowed to rot |
| **The item id becomes 16 Crockford base32 characters** over `url_key`, forward-only | 2026-09-11 | Deterministic by construction (a slice of a digest the payload already carries), 80 bits, and Crockford excludes `i`, `l`, `o` and `u` so the existing slug grammar survives untouched |
| **Political viewpoint becomes FIVE independent fields**, each with its own `not_applicable` | 2026-09-11 | One axis forces unrelated arguments onto one line. Five independent fields let a piece be loud on one axis and silent on four, which is what most pieces are |
| **The console gains two tabs: `Judgement` and `Voices`** | 2026-09-11 | `Voices` is the owner's name, chosen over Susan's `Sources`: the tab is about who is speaking in the corpus, and `Sources` already means a feed everywhere else in this repository |
| **The confidence panel must be drawn, not refused** | 2026-09-11 | The owner ruled that refusing to draw a distribution is a charting failure rather than a reading problem - the answer to a panel nobody can read is a better panel |

---

## 3. Measurements

Every row was re-measured on **2026-09-11** in a worktree cut from `origin/main`
at `70e87bd6`, unless the source column says otherwise. Where the figure the
conversation carried disagrees with the tree, the tree wins and the old figure
is named so the disagreement is visible rather than silently overwritten.

| Figure | Value | How and when measured | Measurement or estimate |
| --- | --- | --- | --- |
| Worst shard, trailing days | **72.93 min** over 108 rows stamped 2026-09-06 or later | `job_seconds` in [`../state/runtime-counters.csv`](../state/runtime-counters.csv), read 2026-09-11. **The conversation carried 66.87 min over 96 rows; both moved** | Measurement |
| Escalate trigger and job timeout | **180 min** trigger, **200 min** timeout | The trigger is plan 11 section 0, restated in plan 23 section 0.3. The timeout is `run.shard_timeout_minutes` in [`../config/idhazh.json`](../config/idhazh.json) | Measurement, both read from the tree |
| The safety ceiling halving | 160 to **80**, on **2026-09-07** | `git log -S` over `config/idhazh.json`: commit `22a8cca9`, "Halve the day to 80 and raise the shard timeout to 200" (#469). **The conversation said "around 2026-09-06"** - it is the seventh, and the same commit raised the timeout to 200, so the two are one decision | Measurement |
| Worst shard before the halving | **135.40 min** | Same column over all 253 rows that carry it. This is the figure older notes quote; it is a pre-halving reading and does not describe today | Measurement |
| Decode rate | median **5.45 tok/s**, min 3.27, max 7.53, over **277 rows** | `tokens_predicted_total / tokens_predicted_seconds_total` per row of the counters ledger. **The conversation said 265 rows; the three rates are exact** | Measurement |
| Prefill rate | median **9.84 tok/s** over 277 rows | `prompt_tokens_total / prompt_seconds_total` per row. Corroborates the 9.85 median over 4,117 timed items already on [`../docs/reference/measurements.md`](../docs/reference/measurements.md) | Measurement |
| A summarize call | median **114.6 s**, p95 **312.7 s**, longest **800.9 s**, over 4,117 rows | The figure [`../docs/reference/measurements.md`](../docs/reference/measurements.md) carries today, cited rather than restated. A whole-ledger recount over all 8,975 timed item-health rows gives a median of 117.7 s, which is a different denominator and not a correction | Measurement |
| Output tokens an item | median **249**, p95 **355**, max 760, over 8,156 rows | `output_tokens` across `state/item-health/`, nearest-rank percentile. **The conversation said p95 356**; a different percentile convention reaches it, the median is exact | Measurement |
| Published items a day | mean **347**, median 358, range **282 to 387** | The four committed days 2026-09-06 to 2026-09-09: 387, 357, 282, 360. **The 347 the conversation carried is the mean, not the median** | Measurement |
| The committed archive | **8,697 items over 22 day files** | Every `frontend/public/digest/**/digest.json`, 2026-09-11. **The conversation said 8,550 over 21**; 2026-09-11 landed with 147 items and is still publishing | Measurement |
| `source_kind` is `reporting` | **84.68 percent**, 7,365 of 8,697 | Same read. The rest: analysis 4.85, announcement 4.39, research 3.29, community 1.60, government 1.18. **The conversation said 84.5 percent** | Measurement |
| Lenses that carry no weight | **4 of the 6 live lenses** sit at weight 0.0, and fired **2,418** times against **670** for the two that carry weight - **3.61x** | Weights from [`../config/taxonomy.json`](../config/taxonomy.json) (`chips` and `trade` at 0.3; `china`, `cyber`, `markets`, `war` at 0.0; `ai-roi` retired 2026-08-30). Firings counted over the committed archive. **The conversation said 2,343 against 650; the ratio held** | Measurement |
| A story more than one feed carried | `carried_by` above 1 on **285 of the 5,101 items that record it, 5.59 percent**; three or more on **21** | Committed archive, 2026-09-11. **The conversation said 246 of 4,464, 5.51 percent, and 17.** The field is null on every item published before it landed, so the denominator is the 5,101 that carry it and never the 8,697 | Measurement |
| The retry column | **every one of 8,931 rows is attempt 1** | `attempt` across `state/scores/`. **The conversation said 6,966 rows.** The column has never held a second value | Measurement |
| Determinism violations | **0 on all 22 committed day-metrics files** | `state/day-metrics/**/*.json`. **The field is `determinism_violations`, plural**, and the conversation said 21 files | Measurement |
| Peak memory against the runner's 16 GB | at `n_ctx` **8,192**: 12 rows, median **12.78 GB**, max 14.10. At **16,384**: 40 rows, median **12.58 GB**, max 14.00 | `peak_rss_bytes` grouped by `n_ctx_configured`. **The conversation said 12.94 GB at 8,192 and about 12.5 at 16,384 over 28 rows.** 193 further rows predate the column and carry no window at all | Measurement |
| The worst article, two calls | **15,889 tokens against a 16,384 window - 97 percent, a margin of 1.03x** | On record in [`../docs/reference/measurements.md`](../docs/reference/measurements.md), from plan 11 row 5. Re-read 2026-09-11 and unchanged | Measurement |
| A third call on the same article | 16,374 tokens with the instruction at its floor (a margin of 1.0006x, ten tokens), **16,674 and an overflow of 290** at a realistic instruction length | Plan 23 section 0.3, derived from the 15,889 above | **Estimate**, and labelled one: the instruction length is assumed, not measured |
| MiniLM-L6 cannot read a whole article | **512-position table**; a p50 article of about 1,277 tokens needs **five chunked passes**, fifteen at p90 | `max_position_embeddings` in the committed `frontend/static/assist/models/all-minilm-l6-v2-quantized/2026-08-22/config.json`, verified 2026-09-11. The pass counts are plan 23's arithmetic over that limit | Measurement for the limit, arithmetic for the pass count |
| Qwen3-4B decode on the runner | **13.00 +/- 0.03 tok/s** | `llama-bench`, `ubuntu-latest`, 2026-08-22, on record in [`../docs/reference/measurements.md`](../docs/reference/measurements.md). It is a bench figure and not the prompt-cache cost in the live digest path, which that page says of itself | Measurement, with its own stated limit |
| `watchlist_bonus` fires | `watchlist_hit` is **true on 1,118 of the 5,101 committed items that record it, 21.92 percent** | Committed archive, 2026-09-11. It was dead arithmetic until 2026-08-26 and it is not dead now | Measurement |
| A story on a front page | `on_front_page` is true on **7 of 5,101** | Same read. The vote almost never lands, which agrees with the host-overlap finding already recorded for that signal | Measurement |
| `events` fire | `release` on **1,602** items, `regulation` on **1,055** | Committed archive, 2026-09-11. **Plan 23 section 26 says 1,546 and 1,016**; both grew | Measurement |

---

## 4. The research

From an arXiv search run on 2026-09-11. Each entry says what the paper is in
one sentence, what it buys this project, and whether we took it.

- **RADio** (arXiv 2209.13520, RecSys 2022). A set of normative diversity
  measures for a news recommender, built as a rank-aware divergence between the
  list a reader is shown and a target distribution over normative concepts.
  **What it buys us:** a way to grade a published day that needs **no
  behavioural feedback at all** - no clicks, no dwell, no accounts. **Taken**,
  as the shape the day-quality measure should have.
- **Vrijenhoek and colleagues** (arXiv 2012.10185). The paper under RADio: it
  takes concepts out of democratic theory and turns them into quantities a
  recommender can be scored on. **What it buys us:** the argument that
  "editorial values" can be written down as a distribution rather than left as
  taste. **Taken**, as the reasoning behind the target distribution.
- **D-RDW** (arXiv 2508.13035, RecSys 2025). Diversity-driven random walks: a
  lightweight re-ranker that takes a customisable target distribution over
  article properties and is cheaper than the neural re-rankers it is compared
  against. **What it buys us:** the re-ranker is arithmetic over properties we
  already hold, so it fits the runner. **Taken**, as the re-ranking shape plan
  25 should reach for.
- **Frames for diversity** (arXiv 2509.02266, 2025). Uses the media frame of a
  story as the thing being diversified, and reports exposure to frames a reader
  had not seen rising by up to 50 percent. **What it buys us:** evidence that
  the axis you diversify on matters more than the algorithm. **Taken as
  direction**, not as a vocabulary - see the Media Frames Corpus row in section
  6.
- **arXiv 2510.05952** (2025). Argues that the public datasets a
  diversity-aware recommender would need do not carry the labels it needs.
  **What it buys us:** the most useful negative result here - **nobody else has
  the labels either**, so labelling our own corpus is not a detour around a
  shortcut, it is the only road. **Taken**, as the justification for the
  reference dataset.
- **"The Format Tax"** (arXiv 2604.03616, 2026). Asking a model for structured
  output degrades its reasoning and its writing, and **most of the loss enters
  at the prompt - the format instruction itself - before any decoder constraint
  applies**. **What it buys us:** it moves the blame. Loosening the decoder does
  not recover what the instruction already cost. **Taken**, and it is why the
  labels ride in a call whose instruction is already paid for.
- **Grammar-Aligned Decoding** (arXiv 2405.21047, NeurIPS 2024). Constraining a
  decoder to a grammar **distorts the model's own distribution**: the output is
  grammatical, and its likelihood is no longer proportional to what the model
  believed. **What it buys us:** the warning that a confidence number read off a
  constrained decode is not the model's confidence. **Taken**, and it is half
  the reason the `logprob_mode` question is a blocking prerequisite.
- **Structured output collapses answer diversity** (arXiv 2607.18476, 2026).
  Across 44 models, asking for JSON collapses answers toward the mode, and
  enforcing the format at the decoder compresses no further than merely asking
  for it. **What it buys us:** the two halves of the cost are not additive, so
  the honest comparison is "structured or not", never "asked or enforced".
  **Taken**, as the reason not to spend design effort choosing between asking
  and enforcing.
- **arXiv 2608.28382** (EMNLP 2026). What a model says about its confidence and
  what its logits say diverge, and instruction-tuned models report higher
  confidence and calibrate worse. **What it buys us:** it kills the cheapest
  design - asking the model how sure it is. **Taken**, and it is why a
  self-reported confidence field is rejected in section 6.
- **arXiv 2608.03854** (2026). On quantized models, **switching from summed to
  mean-token log-likelihood reverses which model appears better calibrated**,
  while accuracy moves at most 1.4 points. **What it buys us:** the scoring
  convention is not a detail; it can invert the finding. **Taken**, and it is
  the other half of why `logprob_mode` has to be established before any
  confidence number is believed.
- **arXiv 2307.06713**. Unsupervised calibration by adapting the assumed prior
  class distribution - no labels needed. **What it buys us:** a calibration path
  that does not wait on a human-labelled set. **Taken as a fallback**, behind
  the labelled reference dataset.

### The synthesis, which is the most valuable finding here

**The field working under this project's exact constraint - no clicks, editorial
values to honour, and a list to publish every day - does not build a learned
importance score. It builds a target distribution and measures the divergence
from it.**

That is the whole finding, and it changes what plan 25 is. You do not need a
learned score, a training signal or a feedback loop. You need to say what a good
day looks like as a distribution over desks, kinds, lenses and viewpoints, and
then measure how far today's page is from that. It is deterministic, it is
cheap, it needs no labels to run, and every input it takes is a field the
payload already carries.

---

## 5. The vocabularies as settled

### Article kind: five values, and what each one renders

`kind` has exactly five values. **There is no `other`, the field is never
absent, and the fallback when the model declines is the feed's declared kind.**

| Value | What it means | What the reader sees |
| --- | --- | --- |
| `report` | A journalist described what happened and attributed the contested parts to named people | **Nothing.** It is 84.68 percent of the corpus, so a chip would be wallpaper |
| `analysis` | Explains why something happened, on a subject the publisher does not gain from | **Nothing** |
| `research` | A study, a paper or a benchmark that states a method a reader could go and check | A chip |
| `announcement` | The organisation the story is about publishing its own news, with nobody independent checking it | `company's own account` or `government's own account` |
| `opinion` | A named author arguing a position | A chip |

The display rule is Reader's, and it has two halves: **label the exceptions,
never the rule**, and **describe who is talking, never what is missing**.
`announcement` renders a presence ("the company's own account") rather than an
absence ("unverified"), because an absence is somebody's fault and the reader
decides whose.

### Political viewpoint: five independent fields

Each field is independent of the other four and each carries its own
`not_applicable`.

| Field | Values |
| --- | --- |
| `stance_on_change` | `conservatism` / `progressivism` |
| `stance_on_economic_power` | `socialism` / `libertarianism` |
| `stance_on_state_power` | `statism` / `constitutionalism` |
| `stance_on_borders` | `nationalism` / `internationalism` |
| `stance_on_personal_sphere` | `civil_libertarianism` / `communitarianism` |

Every definition begins "This piece argues that...", so the model is scoring an
argument the text makes rather than a label somebody would apply to the author.
The fifth axis, verbatim, because it is the newest and the least obvious:

> `civil_libertarianism` - *"This piece argues that a person keeps a sphere -
> their data, body, movement, belief or speech - that no state and no company
> may enter, record or restrict without a specific and limited reason."*

> `communitarianism` - *"This piece argues that the community's safety, order or
> shared standards justify seeing, recording or restricting what an individual
> does."*

### The codable tie-break between the third axis and the fifth

The third axis and the fifth both fire on stories about state power, so the
split has to be mechanical:

**`constitutionalism` asks whether a power was CHECKED. The personal-sphere axis
asks whether the power should EXIST.**

- "The state may build this database, with judicial oversight" is
  `constitutionalism`. The power is accepted and the check is the argument.
- "This database should not exist" is `civil_libertarianism`. The check is not
  the argument; the existence is.
- **A piece with no state actor in it at all can only be the fifth axis**, which
  is the cheapest half of the rule to apply.

### A definition-text fix to record

`conservatism` must cover *"restores or preserves a prior arrangement of who
gets what"*. Without that clause, an argument to remove an existing protection
has no home at all: it is a change, so it is not conservatism as first written,
and it neither widens rights nor reduces disadvantage, so it is not
progressivism either.

### The measurement unit, and it is the thing most likely to be got wrong

**An item is silent only when EVERY one of the five fields is
`not_applicable`.**

Counting `not_applicable` per field will show roughly 80 percent and mean
nothing. A wealth-tax argument has nothing to say about borders, so
`not_applicable` on `stance_on_borders` is a **correct and complete label**, not
a miss. Per-field silence is a property of the vocabulary working; item-level
silence is the only number that says anything about coverage.

### The diagnostic

One person, 100 gate-opened items, hand-labelled first and blind.

**The vocabulary is broken if either of these holds:**

1. the human labels cleanly and the model returns all-`not_applicable` on more
   than **25 percent** of those items; or
2. **the human** writes "no value fits" on more than **10 percent** of the items
   they judged political.

**The second one is the real instrument.** A model's silence cannot tell you a
word is missing - silence is what a model does when the vocabulary is wrong and
also what it does when the vocabulary is right and the piece is apolitical. Only
a person reaching for a word that is not there can distinguish them.

**The model is over-labelling if** item-level silence falls below **15 percent**,
or the mean number of live fields per labelled item rises above **2.0**.

---

## 6. Rejected alternatives

| Rejected | Why |
| --- | --- |
| A third model call | It does not fit the context window. On the worst article the ledger holds, two calls reach 15,889 tokens of 16,384; a third call with its instruction at a realistic length reaches 16,674 and **overflows by 290 tokens** |
| Fingerprinting the taxonomy | It rebuilds the thing being deleted. A taxonomy stamp is a `pipeline_fingerprint` by another name, and it closes the eval window for exactly the same reason: a vocabulary that is config is a vocabulary that changes weekly |
| A two-digest scheme in the schema | Two digests need a rule for which one governs, and every reader has to carry that rule. One recorded input manifest that gates nothing carries the same information and needs no rule |
| `uuid4` for the item id | Not deterministic. The same article re-processed gets a different address, so nothing can be compared across runs and a replay invents a new story |
| `uuid5` or `uuid8` | Deterministic, and they carry a namespace and version grammar nobody here needs, in a character set the existing slug pattern does not accept. Crockford base32 over a digest the payload already holds is the same guarantee inside the grammar already in force |
| A semantic evidence check | It is a model grading a model on the failure mode they share. `CLAUDE.md` section 0a bans a judge that selects what publishes, and this would be one |
| A string evidence check | Cheap and wrong in a way that looks right: it passes a summary that copies the article and fails a correct paraphrase. The element table already re-slices the source text, which is a stronger check and costs microseconds |
| A self-reported confidence field | arXiv 2608.28382 measures exactly this: linguistic and logit confidence diverge, and instruction-tuned models report higher confidence while calibrating worse. Asking the model how sure it is buys a number that is confidently wrong |
| Best-of-N now | It multiplies the per-item cost against a shard budget with 33 minutes of headroom at the slow tail. It is built behind a flag and stays off until the budget says otherwise |
| Self-consistency voting as the default | Same budget, and the same answer: `classification.self_consistency_n` defaults to 1, so the default path pays for one call |
| A `train/` split in the reference dataset | Nothing here trains on it. A split named `train/` invites somebody to, and the set is small enough that spending half of it on a phase we do not run is the whole cost |
| Equal-width ECE bins | On a distribution piled at the top, equal-width bins put nearly every item in one bin and report a calibration error about a bin nobody is in. Equal-mass bins ask the question that was meant |
| A run writing `config/taxonomy.json` directly | A pipeline run editing its own committed config is a change with no review and no author. The loop proposes; a person disposes |
| A weekly loop rather than per-run | Weekly makes the feedback interval a week, so a vocabulary change takes a week to show. Per-run is the same arithmetic on a fresher input |
| A standing pull request the workflow keeps updating | It reads as reviewed because it is open, and its diff changes under the reviewer. A fresh proposal per run is honest about what is being agreed to |
| Graph models, or outlet-level bias models | Both label the outlet rather than the piece, which is the thing we refuse to publish: a verdict on a newsroom instead of a description of one article |
| The Media Frames Corpus as a second vocabulary now | Two vocabularies to maintain, two to label against and two to explain, before the first one has a diagnostic run against it. The frames finding (arXiv 2509.02266) is taken as direction; the corpus is not taken as a vocabulary |
| `populism` as a viewpoint value | It is a style of argument, not a position on any of the five axes, so it is orthogonal to all of them and would fire alongside every one. A label that never discriminates is wallpaper |
| Open-versus-managed-society as the fifth axis | It restates the third axis in different words: a managed society is one whose powers are unchecked, which `constitutionalism` already asks |
| Transparency-versus-secrecy as the fifth axis | It is about the state's own visibility, not the person's. Most pieces that fire on it also fire on `stance_on_state_power`, so it buys a second reading of one fact |
| Individual-autonomy-versus-collective-security as the fifth axis | Closest of the three, and refused on the tie-break: "security" narrows it to safety, where the sphere being argued over is data, body, movement, belief and speech. The personal-sphere wording covers a privacy story with no threat in it, which this wording does not |
| A single combined quality score on the console | It hides which of the things it combines moved, so the one number an operator watches is the one number that cannot be acted on |
| `Sources` as the fifth tab name | `Sources` already means a feed everywhere else in this repository, and the tab is about who is speaking in the corpus. Susan proposed it; the owner chose `Voices` |

---

## 7. Persona rulings

**Reader.** Ruled on what a label does to a page. The load-bearing pair, quoted
in plan 23 section 0.1: **"label the exceptions, never the rule"** - a chip on
nearly every item is wallpaper by item four, so `report` at 84.68 percent
renders nothing - and **"describe who is talking, never what is missing"** -
"unverified" describes an absence, an absence is somebody's fault, and the chip
becomes a verdict on a newsroom, where "the company's own account" gives the
same warning with no blame.

**Editor.** Ruled on which vocabularies earn their place. The load-bearing
finding: **a US left-right axis is refused because it would be empty on most of
this corpus.** The digest is five desks of world, business, energy, AI and
security news; an axis whose values only apply to United States domestic
politics labels a small slice and returns `not_applicable` on everything else,
which is a vocabulary that costs a call and answers nothing.

**Andre.** Ruled on what the model can be asked and what its answers are worth.
Two findings, and both are blocking. **llama.cpp silently drops JSON-Schema
conditionals** - `if`/`then`/`else` is accepted and not enforced, so a schema
conditional is not a control and any design that leans on one is unguarded.
And **temperature 0 can collapse post-sampling probabilities to a constant
1.000**, which means a confidence figure taken from the wrong distribution is
not a weak measurement, it is the number 1 with a decimal point. Which
distribution the runtime reports (`logprob_mode`) has to be established before
any confidence number is believed, which is why it is an ESCALATE trigger rather
than a row.

**Fowler.** Ruled on what a field deletion costs. The load-bearing finding:
`backend/idhazh/contracts/base.py` sets `model_config = ConfigDict(extra="forbid",
...)`, so **removing a field makes every older payload fail at read time** -
which turns a one-commit deletion into a read-side migration kept for as long as
the oldest committed payload lives. The split that follows: stop the reading
now, argue the shape later.

**Carmack.** Ruled on what fits the runner. The load-bearing finding: **the
third call did not fit the context window.** Two calls on the worst article the
ledger holds are 15,889 tokens of 16,384; a third with a realistic instruction
is 16,674 and overflows by 290. That single arithmetic is what fixed the design
at two calls.

**Susan.** Ruled on whether the reader-facing surface is good enough to ship.
The load-bearing finding: **two of the three proposed chips already exist** in
`frontend/src/lib/bands.ts`, which exports `SOURCE_KINDS` and
`KIND_WORTH_SAYING` (verified 2026-09-11). The new work is smaller than it
looked, and a plan that proposed building all three would have shipped a second
copy of a vocabulary already in the bundle.

---

## 8. Open gaps nobody owns

Named here so they are not lost. None of them is a row of plan 23, 24 or 25.

- **`backend/utilities/prompt_loop.py` still targets the single-call summariser
  prompt** and must retarget. Once the call structure is a directed graph, it is
  tuning a prompt that no longer exists in that shape. It is owned by no row of
  any plan.
- **`events` and `entities` are matched, stored, versioned and schema-gated, and
  rendered nowhere.** `release` fires on 1,602 committed items and `regulation`
  on 1,055 (2026-09-11), and both names sit in `FORBIDDEN_FIELDS` in
  `frontend/src/lib/payload/project.ts`, so the projection refuses to serve
  them. **The `Judgement` tab is their proposed home.** Until somebody takes
  that row, they are rent nobody is paying for on purpose.
- **Prerender is legacy, and its removal belongs to the UI shell plan - not to
  plan 23, 24 or 25.** Recorded here so it is not lost. What is true on
  2026-09-11: `frontend/prerender-guard.js` exists and
  `frontend/svelte.config.js` imports its `handleUnseenRoutes`, so prerendering
  is wired into the build; **23 pages under `docs/` name it**, not the eleven
  the conversation carried; and `.github/workflows/ci.yml`'s only mention is a
  comment explaining what prerendering used to give for free before the reading
  routes were split on 2026-09-01. **The app UI should not use it.**
  **Superseded the same day.** No UI shell plan-doc exists or is planned, and
  [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md)
  took the gap. Reading the tree changed the answer: the dated reading routes
  stopped prerendering on 2026-09-09 and six routes deliberately did not, with
  the reasons written beside the code, so the guard is legacy and the routes are
  a live decision. That plan rules the six stay, deletes the guard, and prices
  the reversal for the day the owner wants it.
- **`watchlist_bonus` was documented as dead arithmetic**, fixed on 2026-08-26,
  and it now fires: `watchlist_hit` is true on **1,118 of the 5,101 committed
  items that record it, 21.92 percent** (measured 2026-09-11). The gap is that
  nothing was watching, so anything that comes to rely on it should re-run that
  count rather than trust this line.
- **`retention.dry_run` is `true`** (`config/idhazh.json`, verified 2026-09-11),
  so **every prune in this repository is a no-op today**. Flipping it is a
  decision about the whole repository and is nobody's row.

---

## 9. Honest limits

**This record was reconstructed from a design conversation. The raw reasoning
traces and the subagent transcripts were not retrievable.** What is here is the
decisions, the measurements and the citations - it is not a transcript, and it
does not claim to be one.

Three consequences, stated plainly:

1. **Anything a future agent cannot verify from the tree should be treated as
   provenance, not as fact.** The owner decisions in section 2, the persona
   rulings in section 7 and the rejected alternatives in section 6 are records
   of what was decided and why it was said to have been decided. They are not
   independently checkable, and several of them - the Editor's refusal of a
   left-right axis, the `Voices` naming, the five stance axes - appear in no
   other file in this repository.
2. **The arXiv entries in section 4 are the search's own output on
   2026-09-11**, recorded as they were returned. Their identifiers, venues and
   claims have not been verified against the papers, and no reader of this file
   should cite them onward without doing that.
3. **Every measurement in section 3 carries its date and its source, and several
   were already wrong when this file was written** - the archive gained a day
   and 147 items between the conversation and the re-measurement. Re-run the
   read before quoting any of them; a count over a collection this pipeline
   appends to is stale within hours.

---

## See also

- [`20260910-23-article-classification-plan.md`](20260910-23-article-classification-plan.md) - the plan this conversation produced; its section 0.3 carries the budget arithmetic and its section 26 the open gaps section 8 extends.
- [`20260910-24-day-sharded-ledgers-plan.md`](20260910-24-day-sharded-ledgers-plan.md) - the ledger work the same conversation split out.
- [`20260910-25-placement-plan.md`](20260910-25-placement-plan.md) - the placement work the same conversation split out; section 4's synthesis is the finding it should be read against.
- [`20260911-26-retire-prerender-plan.md`](20260911-26-retire-prerender-plan.md) - the plan that took the prerender finding in section 8 and, having read the tree, ruled the opposite way on half of it.
- [`20260902-visual-planner-pseudo-plan.md`](20260902-visual-planner-pseudo-plan.md) - decision O43, which section 2 amends.
- [`../docs/reference/measurements.md`](../docs/reference/measurements.md) - the instrument log section 3 cites rather than restates.
- [`../docs/architecture/contracts/determinism.md`](../docs/architecture/contracts/determinism.md) - the page the determinism decision rewrites.
- [`../CLAUDE.md`](../CLAUDE.md) - section 0 (owner approval), section 0a (the judge ban), Rule #10 (a number carries its hardware, date and spread).
