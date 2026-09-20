# The council ships, the judges measure

**Last Updated**: 2026-09-20

**Level**: 5 (a persisted contract with committed rows, a committed state tree that moves, and a new meaning for a `run_id` cell)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 3 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The council had no separation between its own pipeline observability and the metrics a judge produces, so a shared row was about to force judge two to file columns it cannot have. Four verbs name their mechanism rather than their work. And five defects the work uncovered would lose data on a live run. |
| Hard scope - in | The three-layer separation, written into the page that owns the council; the shipping capability a judge calls; the council's own shard-outcome record; the content-similarity judge's own metrics; the four verb renames and the deletion of `leg` and `fold` from the vocabulary; the five defects (a shard losing its verdicts on its own clock, the council having no run identity, the reader that cannot fill a default, the header that makes the store unappendable, and the verdict artifact a cancelled shard never writes); the measured call cost; the knob move; the thinking refusal and decode stamp; the store grouping under the judge slug; the line-against-holdout record; one composite action for the model block. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | (1) Row #2 changes what a committed `run_id` cell means - pause for sign-off. (2) **Row #8** widens a header on a store with committed rows, rewrites them, and extends a persisted key - pause for sign-off before the rewrite runs. (3) **Row #9** renames a config knob AND the workflow key that reads it - if the two cannot land in one commit, stop. (4) **Row #11** widens the record's stamp, which resets the distribution once by construction - pause for sign-off on that reset. (5) **Row #18** moves a committed state tree - pause for sign-off on the path map before any file moves. (6) **Row #19**: if the holdout resolves fewer pairs than its floor, write the cells null and refuse the reading. (7) **Row #21** mints three config knobs, changes the matrix width, widens the workflow permissions block and raises artifact retention - pause for sign-off on the permissions change. (8) Any row that would raise a runner budget figure (Guardrail #2). |
| Chosen strategy | The council owns the pipe and its own execution record; each judge owns what it measures and its own store. Share the call and the shipping capability, never the metric set. Owner ruling 2026-09-20, after four adversarial rounds (section 1b). |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2.` Two, and live in two windows only: the dependency chain leaves at most two groups ready at once. |

### The separation this plan exists to hold

| Layer | Owns | Stored | Lifetime |
| --- | --- | --- | --- |
| **Council pipeline observability** | Did the pipeline work - which shards started, which finished, which stopped on their own clock, what each cost | `state/llm-council/shard-outcomes/` | Discardable. One run a night |
| **The shipping capability** | The plumbing only. Takes a validated payload a judge hands it and gets it committed. **Declares nothing about what is in it** | code, not data | n/a |
| **Judge metrics** | Entirely the judge's. Its units, its funnel, its instrument readings, its own contract | `state/<judge-id>/metrics/<YYYY>/<MM>/<DD>.csv` | The judge's to prune |

**Which readings sit where.** The council records the shard's identity, its clock, its outcome, and the aggregate cost of the work it hosted - and nothing that needs a name for the unit. The judge records units dealt, read, unusable and abandoned; whether the grammar applied; the first-token margin; and any agreement or uncertainty reading its own design produces. A judge that runs no model at all files a metrics row with no model columns, and the council's record is unchanged.

**A judge owns more than one store, and running under the council does not make any of them the council's.** The content-similarity judge owns two: `metrics/`, which is how its instrument behaved, and `merge-line-holdout-scores/`, which is how the line it produced stands against a benchmark labelled outside the loop. **The second is the one most likely to be mis-filed**, because the council is what runs it - but it measures a judge's output, so it is the judge's. The test is what the reading is ABOUT, never what executed it. A reading about the pipeline goes under `state/llm-council/`; a reading about a judge's instrument or a judge's output goes under that judge's slug, however many stores that takes.

**Why the split is not a matter of taste.** A first draft put the funnel and the margin on one shared row. The margin means "the grammar chose and the model did not" for a judge whose emitted token is the answer, and "a legitimate middle score" for a judge whose distribution is the answer. A shared column would have made one fold sum two instruments, which is the defect the judge identity exists to prevent.

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| A host fingerprint on each judging shard | The council cannot say which processor ran a shard | A council reading that depends on the machine. The digest pipeline already characterises the same runner pool, and the bandwidth probe wants 1.9 GiB on the widest part in the fleet against a server that peaks at 96 percent of the runner || Per-call spans folded into the shared span rollup | Per-call attribution. The judge's own row carries the call count, the total and the worst instead | A question the three aggregate numbers cannot answer |
| Each judging shard committing its own rows instead of uploading them | **Segments would break the job that counts the shards, not protect it.** Every checkout in the council names no ref, so each job is pinned to the commit the run was triggered at - rows a shard commits at 22:40 are invisible to a collecting job checked out at 22:00. Segments remove a conflict between many committing writers on one file; the council has one committing writer, and its day file is already settled on every write by a key carrying the run id | A judging shard whose output is too large for an artifact, or which must survive the artifact's 24-hour retention. Neither is true today |
| The council running the compaction verb | It takes no ledger filter and no date filter: it folds every waiting segment and then deletes the files it read. `origin/main` carries 21 waiting files across five ledgers right now. A council run would fold and delete all 21 while committing only its own folders. **And it raises rather than skips on a directory naming an unregistered ledger** - it is the first step of the digest run's planning job, so one unregistered directory stops publishing five times a day | **Nothing. This is refused for as long as the verb has no filter**, and it is a separate refusal from the one above |
| A shared judge metric schema | Nothing. Each judge declares its own | Never. This is the defect the plan exists to remove |
| A `Judge` base class, protocol or registry | The second judge duplicates the stage shape, about 150 lines | A third judge sharing three of the four steps |
| One workflow per judge | Every judge shares one schedule and one runner label | A judge needing different weights or a different cadence |
| The independent second-opinion judge | The holdout stays labelled outside the loop, which is correct but unmaintained | The six questions in the second-judge handover being answered |
| A real judge-against-holdout measurement | Nothing measures whether the JUDGE agrees with the labels, only whether the LINE does | A budget: 200 pairs at 94.53 s a pair is 5.25 h on one job |
| The summary-quality judge's own stages | Plan 36 owns them | Plan 36 reaching its scoring row |
| New console panels | The judgement console already renders the holdout against the applied line | An operator asking for something the committed rows cannot answer |
| Renaming `backend/var/judge/` | The scratch directory keeps a word naming one loop's selection | The parallel work already moving production artefacts out of the code tree |

## Section 1 - Status Reckoner

**A `Parallel-group` letter is one pull request, not one row.** Rows sharing a letter are written together, gated once and merged once, and are chained in `Depends-on` where they write the same files.

| Group | Pull request | Rows |
| --- | --- | --- |
| A | A shard survives its own clock, and the council knows which run it is | 1, 2 |
| B | The separation, written where the next agent reads it | 3 |
| C | Every persisted shape this plan needs | 4, 5, 6, 7, 8 |
| D | What a call costs, and where its bound lives | 9, 10 |
| E | The model boundary asserts what it assumed | 11 |
| F | The verbs name their work, and two borrowed words leave | 12, 13 |
| G | The judge fills its stamp and ships its metrics | 14, 15 |
| H | The council records the machine and the model block folds into one action | 16, 17 |
| I | The store groups under the judge that fills it | 18 |
| J | Where the judge's merge line stands against its holdout | 19 |
| K | The plan pointer, and the guard is renamed | 20, 22 |
| L | The council repairs its own missing nights | 21 |

**L lands last, and that is a correction.** It was in the first pull request until round four caught it: the repair re-judges a date, and re-judging without the extended pair key from C and the widened record stamp from E discards the very work it re-does.

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A shard keeps the verdicts it paid for | - | A | PENDING | - | - | - |
| 2 | The council knows which run it is | 1 | A | PENDING | - | - | - |
| 3 | The separation, written where the next agent reads it | - | B | PENDING | - | - | - |
| 4 | The judge-call stamp, declared once | 2 | C | PENDING | - | - | - |
| 5 | The council's own shard-outcome record | 4 | C | PENDING | - | - | - |
| 6 | The content-similarity judge's own metrics | 5 | C | PENDING | - | - | - |
| 7 | The judge's merge-line benchmark record | 5 | C | PENDING | - | - | - |
| 8 | The pair row gains the stamp, and the store is rewritten | 5 | C | PENDING | - | - | - |
| 9 | The shard timeout moves to the block that validates it | 2 | D | PENDING | - | - | - |
| 10 | The measured judge pair replaces the derived call | 9 | D | PENDING | - | - | - |
| 11 | Thinking is refused and the decode is stamped | 4 | E | PENDING | - | - | - |
| 12 | The four verbs name their work | 9 | F | PENDING | - | - | - |
| 13 | `leg` and `fold` leave the vocabulary | 12 | F | PENDING | - | - | - |
| 14 | The judge fills the stamp | 8, 11, 13 | G | PENDING | - | - | - |
| 15 | The judge writes its metrics, and the council ships them | 6, 14 | G | PENDING | - | - | - |
| 16 | The model block becomes one composite action | 15 | H | PENDING | - | - | - |
| 17 | The council records its own shard outcomes | 16 | H | PENDING | - | - | - |
| 18 | The store groups under the judge that fills it | 17 | I | PENDING | - | - | - |
| 19 | Where the judge's merge line stands against its holdout | 7, 18 | J | PENDING | - | - | - |
| 20 | The plan pointer | 19 | K | PENDING | - | - | - |
| 21 | The council repairs its own missing nights | 8, 11, 12 | L | PENDING | - | - | - |
| 22 | The guard that stops a shard committing is renamed and re-reasoned | 13, 21 | F | PENDING | - | - | - |

**A `Parallel-group` letter is one pull request.** Rows sharing a letter are written together, gated once and merged once, and are chained in `Depends-on` where they write the same files - which is why every row inside C and F carries a predecessor.

## Section 1a - The words this plan deletes

**The plain-meaning test.** A word earns a name only when its ordinary English meaning is what the thing does. Where you have to know which field it was borrowed from, it is a second name for something that already has one, and it is deleted rather than replaced.

| Word | Borrowed from | What it actually meant | Becomes |
| --- | --- | --- | --- |
| `leg` | relay racing | one shard of the judging work | **deleted.** `shard` is already the column, the knob and the count. **Test names included** - a scrub that leaves the word in a test's own name has not been done |
| `fold` | functional programming | collect the shards' output, commit it, count it into the record | the job is `collect`; the verb is `count-verdicts`; prose names the action |
| `draw` | a lottery | the pairs selected for judging | the verb is `pick-item-pairs`; the file is `picked-pairs.csv` |
| `arm` | clinical trials | one configuration of a comparison run | already deleted on 2026-09-15, in favour of `cases` - one test case a pass, the first being the baseline the rest are read against |

**Prose names the action, not the job.** "A day with a missing shard is not counted into the record" replaces "the fold refuses a partial day". This is the half that keeps coming back after the identifiers are fixed.

## Section 1b - What four adversarial rounds changed

Each line is a claim a worker would otherwise re-derive. Four rounds ran against earlier drafts, 2026-09-20 and 2026-09-21. Round three split a stamp that had started meaning three things again, added a sixth pair column and extended a persisted key; round four found the catch-up scheduled before the key it depends on, four sign-off triggers naming the wrong rows, and a three-decision chain that latched the council into judging nothing for ever.

| The draft said | The code says | What changed |
| --- | --- | --- |
| `if: always()` on the verdict upload fixes the cancelled shard | The shard builds a list and writes once after the loop, so a cancelled shard has written nothing and the upload takes an absent path | Row #1 is a stage change - a deadline, a flush and a header-first write |
| A row may inherit `CsvContract` | It is a `typing.Protocol` in the ledger; mixing it with a pydantic model is a metaclass conflict, and the import is circular | Every new row subclasses `Contract` |
| The pair row inherits the stamp mixin | Base fields are collected first, so the header reorders and the append check raises - the store becomes unappendable | The pair row declares the columns in its own body, at the tail |
| `from_csv_row` fills absent keys from defaults | It maps an absent cell to empty string, converting only when the default is `None`; a Literal refuses it and the loader stops the read | Named as new code, added to the existing by-name branch - not a general predicate, which would also pop `version` |
| The council reuses a run id | It has none, and the pair rows carry the digest run's | Row #2 mints one, from the day the council **runs** - the compaction reads a run id's first ten characters as the day the run opened and publishes it as a lag figure |
| Spans come from the existing closed set | The rollup has five members and silently skips anything else | Spans dropped entirely (scope-out), and the judge's row carries three aggregate numbers |
| The fingerprint goes before the first model call | The probe wants 1.9 GiB and the server peaks at 14.31 GiB of 16 GB | The fingerprint is dropped entirely (scope-out), which removes the risk rather than ordering around it |
| The fold stages what the shards wrote | A shard's files are on its own runner, and the collecting job downloads only verdicts | Row #15 gives the council its own artifact path, which is what it already runs for verdicts |
| The council runs the compaction verb | It takes no filter: it files away every ledger waiting in transit and deletes the transit copies. The digest run's are often still waiting at 22:00 | The council does not run it. Its own artifact path has no shared transit to collide on, and the segment design it declines solves a conflict the council does not have - it has one committing writer, not eight |
| The plan updates the plan-queue page | A gate fails any pull request that edits it, and it already names this plan | The page is left alone |
| Widening the probability window fixes the margin | The margin is the top two of whatever came back, and the top two do not move | The margin is taken over the three verdict-opening ids, renormalised |
| A grammar failure writes `usable` false | A nullable verdict makes two failures compare equal, so `usable` goes true with no verdict and the row's validator refuses that shape | The agreement test gains a null check in the same change |

## Section 1c - The contracts, settled before any row is written

Guardrail #3. Types are the aliases in `backend/idhazh/contracts/base.py`. **Every new contract is registered in the `CONTRACTS` tuple in `backend/idhazh/contracts/export.py`** - that tuple writes `schemas/` and the frontend types, and the drift gate derives both sides from it, so an unregistered contract fails with a message about an orphan file rather than a missing registration.

### New type alias

`JudgeId = Literal["content-similarity-judge", "summary-content-quality-judge"]`, in `backend/idhazh/contracts/judge_call.py`.

A Literal for the reason the scorer id is one: a fold over a store mixing two instruments sums readings that mean different things. **A judge's identity is a property of its stage, not a tunable** - the stage names its own `JudgeId` as a module constant and it never reaches `config/`.

### `CouncilShardOutcome` - the council's own record (`backend/idhazh/contracts/council_shard_outcome.py`)

`class CouncilShardOutcome(Contract)`. `__schema_stem__ = "council-shard-outcome"`. One row per shard per run. Key: `("date", "run_id", "shard")`. Store: `state/llm-council/shard-outcomes/<YYYY>/<MM>/<DD>.csv`.

**It carries nothing that needs a name for the unit of work.** That is the whole of the separation: this row is about the pipeline, and it reads the same whether the judge it hosted made four hundred model calls or none.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | The digest date this run judged |
| `run_id` | `RunId` | - | The council run, minted from the day the council ran |
| `judge_id` | `JudgeId` | - | Which judge this shard hosted. Without it a night running two judges files rows nobody can attribute |
| `shard` | `int` | `ge=0` | Which shard |
| `shards` | `int` | `ge=1` | How many the work was split across. A run judged by fewer shards than it was split for leaves work unread, and the pair alone says so |
| `outcome` | `ShardOutcome` | - | `completed`, `stopped_on_deadline`, or `nothing_to_do`. A shard killed by the platform writes no row at all, and absence against a known shard count is what says so |
| `started_at` | `Timestamp` | - | When the judging stage began |
| `seconds_spent` | `float` | `ge=0` | Wall clock for the stage. Not the job - the job's own clock includes a checkout and a weights restore this row is not about |
| `model_calls` | `int \| None` | `ge=0` | How many calls the hosted work made. **Null, not zero, for a judge that runs no model**; zero for a model judge whose shard had nothing to judge. The judge's stage decides which, because only it knows whether it has a model. Counted per call rather than derived as twice the pairs - a pair refused on its first call made one call, not two |
| `tokens_in` | `int \| None` | `ge=0` | Prompt tokens the server reported across the shard. **Requires the reading type to stop dropping the count it already receives** |
| `tokens_out` | `int \| None` | `ge=0` | Generated tokens. **Requires the reading type to carry a completion count it does not carry today** - row #17 adds it or this column is dropped rather than shipped null for ever |
| `model_seconds` | `float \| None` | `ge=0` | Wall clock inside model calls, summed from each reading's own clock. Read against `seconds_spent`, the two say how much of a shard was the model and how much was everything else |
| `host_model` | `str \| None` | `PRINTABLE_LINE_PATTERN`, `max_length=96` | The processor name, one line read from the kernel's own file. **This is not the host fingerprint** - the 1.9 GiB bandwidth probe stays refused. Without it a slow night and a slower processor read identically, and the scope-out's "the digest pipeline already characterises the pool" has no join key a council row could use |

`ShardOutcome` is a `StrEnum` in the same module, three members, because a free-text outcome is a column that splits silently on a typo.

### One stamp, and why there is not a second (`backend/idhazh/contracts/judge_call.py`)

**`JudgeConfigStamp(Model)` - what the instrument was SET TO.** Grain-free, so any row may carry it whatever its unit.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `judge_id` | `JudgeId` | default `"content-similarity-judge"` | Which instrument wrote this |
| `judge_model` | `JudgeModelId \| None` | default `None` | Which weights judged |
| `judge_temperature` | `float \| None` | `ge=0`, default `None` | The sampler temperature, as a number. An operator reading a row needs the value, not a hash of it |
| `decode_digest` | `Sha256 \| None` | default `None` | sha256 of the canonical JSON of six sampler keys **of the body actually posted**: temperature, top-p, seed, prediction length, the alternatives count and the probability mode. Not the prompt, which differs every row; not the grammar or the model, which have their own columns. Taken from the payload rather than from config, because a digest built off config cannot see a payload-builder bug |
| `prompt_digest` | `Sha256 \| None` | default `None` | sha256 of the rendered system turn |
| `grammar_digest` | `Sha256 \| None` | default `None` | sha256 of the grammar handed to the decoder |

**There is no per-call mixin, and that is a deliberate deletion.** An earlier draft split this in two and gave the per-call half three fields - whether the grammar applied, the first-token window and one call's clock. **Nothing inherited it.** The pair row declares its own columns at the tail because inheriting reorders a header with committed rows behind it, the shard metrics row has no single call, and neither the council's record nor the holdout row involves a model. Three fields declared for a row that does not exist is speculative generality; the second judge extracts a per-call mixin when it is the second real caller.

**The per-call fields therefore live where they are used**, and each names its own grain: the pair row's `grammar_applied` means both calls of that pair opened inside the grammar, and its `first_token_probabilities` is the file-order call's window, named so because a pair makes two calls and a singular column must say which.

**A key added to the payload builder and not to the digest is a digest gone silently narrower.** The builder and the digest are held together by a test that enumerates the payload's keys and fails on one the digest neither covers nor names as excluded.

**`first_token_probabilities` is the first model-written value this loop commits.** It is safe where it lands - a quoted CSV value, never a key, never a name - and it stays there (Guardrail #11).

### `ContentSimilarityJudgeMetrics` - the judge's own (`backend/idhazh/contracts/content_similarity_judge_metrics.py`)

`class ContentSimilarityJudgeMetrics(JudgeConfigStamp, Contract)`. `__schema_stem__ = "content-similarity-judge-metrics"`. Key: `("date", "run_id", "shard")`. Store: `state/content-similarity-judge/metrics/<YYYY>/<MM>/<DD>.csv`.

**It inherits the config stamp and not the call stamp.** A shard has no single call, so a per-call grammar flag, a per-call probability window and a per-call clock have no referent here. The three shard-level equivalents are `pairs_refused`, `first_token_margin_median` and the two decode totals below.

**Every column here is this judge's own.** A second judge declares its own contract with its own columns and shares none of them.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | The digest date judged |
| `run_id` | `RunId` | - | The council run |
| `shard` | `int` | `ge=0` | Which shard |
| `pairs_dealt` | `int` | `ge=0` | Pairs the selection gave this shard |
| `pairs_read` | `int` | `ge=0` | Pairs that got a reading inside the grammar |
| `pairs_agreed` | `int` | `ge=0` | Pairs whose two order-swapped readings matched |
| `pairs_unreadable` | `int` | `ge=0` | Pairs whose items the window no longer reaches. The stage counts this today and throws it into a log line |
| `pairs_refused` | `int` | `ge=0` | Pairs where a reading came back outside the grammar. **Pairs, not calls** - a pair is two calls, so counting calls would over-count a pair that failed twice and make the identity below go red on a real event |
| `pairs_abandoned` | `int` | `ge=0` | Pairs owned and never reached, because the shard stopped on its own deadline |
| `disagreement_rate` | `float \| None` | `ge=0, le=1` | Share of read pairs whose two readings differed. Null when nothing was read - a rate over zero rows is not zero. **Per shard over read pairs**, where the line-setting gate is per day over agreed pairs; two different quantities, and the description says so |
| `unclear_rate` | `float \| None` | `ge=0, le=1` | Share of agreed pairs answered UNCLEAR. Null on an empty shard, same reason, same caveat |
| `first_token_margin_median` | `float \| None` | `ge=0, le=1` | Median gap at the deciding position, over the three verdict openings. **Not comparable to another judge's**: a flat distribution means the grammar chose here, and a legitimate middle score for a judge whose distribution is the answer |
| `decode_seconds_total` | `float \| None` | `ge=0` | Sum over the shard's calls |
| `decode_seconds_max` | `float \| None` | `ge=0` | The longest single call. A shard with an ordinary total and a bad worst call is the one that runs out of clock next |

**The identity that closes:** `pairs_dealt = pairs_read + pairs_refused + pairs_unreadable + pairs_abandoned`, enforced by a model validator. Every term is a column, including the abandoned one - without it the identity fails on exactly the shard row #1 exists to let write a row at all.

**No bare `decode_seconds` on this row.** The two totals are named for what they are, so no reader mistakes a per-call column for the typical call.

### `MergeLineHoldoutScore` - new (`backend/idhazh/contracts/merge_line_holdout_score.py`)

`class MergeLineHoldoutScore(Contract)`. `__schema_stem__ = "content-similarity-judge-merge-line-holdout-score"`. Key: `("date", "run_id")`. Store: `state/content-similarity-judge/line-holdout-scores/<YYYY>/<MM>/<DD>.csv`.

**It does not inherit the call stamp.** No judge reads anything here: the holdout rows carry no verdict, the scoring applies a threshold to a recomputed similarity, and the labels were written by a model outside the pipeline. Eight call columns would be five nulls and one asserting an instrument that never ran.

**Counts only. No precision, recall or accuracy column** - a stored rate is a rate somebody reads without its denominator, and this denominator is four.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | When the line was scored |
| `run_id` | `RunId` | - | The run that scored it |
| `applied_line` | `float` | `ge=0, le=1` | The merge line in force when the cells were counted |
| `labeller` | `str` | `PRINTABLE_LINE_PATTERN`, `max_length=64` | Who marked the holdout. Not a `JudgeModelId`: the committed labels name a model outside the registry, and a column that could only hold pipeline models would refuse the truth |
| `merged_and_one_story` | `int` | `ge=0` | The line joined them and the label agrees |
| `merged_and_two_stories` | `int` | `ge=0` | The line joined two stories that are not one. The reader never sees the second - the invisible direction |
| `apart_and_one_story` | `int` | `ge=0` | The line left one story in two pieces. The reader sees it twice and can dismiss it |
| `apart_and_two_stories` | `int` | `ge=0` | The line left them apart and the label agrees |
| `pairs_unresolved` | `int` | `ge=0` | Labelled pairs whose two days retention has deleted. Reported, never dropped |
| `labelled_two_story_pairs` | `int` | `ge=0` | The negative population the false-merge cell is drawn from. On the row so no rate is read without it |
| `scorer_model` | `ScorerModelId` | - | Which encoder produced the cosines |
| `cosine_weight` | `float` | `ge=0, le=1` | What the cosine was worth |
| `key_point_weight` | `float` | `ge=0, le=1` | What the key-point term was worth |

**The read is bounded by the holdout, not by the archive** (Guardrail #12). Each holdout row names its own two days, so the file's length is the bound. The unbounded walk in the sheet tool exists only because that tool resolves against a different date, and this must not copy it.

### `StorySimilarityPair` - six columns appended at the tail

The declaration is unchanged - it does **not** inherit either stamp. **Six** fields are appended after `decode_seconds`, so the header widens and does not reorder: `judge_id` (default `"content-similarity-judge"`), `judge_temperature`, `decode_digest`, `grammar_applied`, `first_token_probabilities`, and `judged_by_run_id`.

**`judged_by_run_id: RunId | None`, and the key extends to `("date", "run_id", "pair_key", "judged_by_run_id")`.** This is what makes a re-judge possible at all. `run_id` on this row is the DIGEST run that published the day - a property of the date, so two council runs judging one date write the identical string. Under today's three-part key the append path's de-duplication keeps the first row it sees, which is the one already in the checked-out file, so **every re-judged pair would be silently discarded while the record counted the fresh verdicts** - the committed store and the fitted record would then describe two different sets with nothing able to tell.

**The ordering rule, because the column is nullable and every committed row will carry it empty.** The de-duplication compares raw cells, so an empty cell and a run id are two distinct keys and both rows survive - which is exactly what a re-judge needs. The defect is downstream: the one-row-a-pair tie-break in the counting module orders on a bare `>`, and comparing two empty values or an empty against a string raises. **The ordering is `(row.judged_by_run_id or "")`, null lowest**, so a stamped re-judge beats an unstamped original and two unstamped rows keep file order - which is today's behaviour exactly. A unit test drives two rows, one null, and asserts the newest wins.

**`grammar_applied` on this row means both calls of the pair opened inside the grammar**, because this row's grain is a pair. `first_token_probabilities` on this row is the **file-order** call's window, named so, because a pair makes two calls and a singular column must say which.

`decode_seconds` keeps its existing meaning on this row - both calls on the pair - and its description says so.

Changelog entry to prepend: version `2026-09-20`, change "Added the judge-call stamp columns: which judge, its temperature and decode digest, whether the grammar applied, and the first-token vector.", why "A verdict could not be read back to the sampler that produced it."

**Two migrations, both in the same commit.**

1. **Read side.** `from_csv_row` adds `judge_id` to the existing by-name branch that already special-cases the other non-null default on this row. **Not a general predicate over "any field whose default is not `None`"** - a required field's default is undefined, not `None`, so a general branch would also pop `version`, which a before-validator then refills with this build's own stamp. That is silent coercion on the one column the header migration uses as its sentinel.
2. **Write side.** The committed day files are widened in place by `migrate_header(path, StorySimilarityPair.csv_columns(), refiler(StorySimilarityPair))`. **`refiler` alone touches no file** - it returns a row-to-row function, and `migrate_header` is what writes. Nothing runs either from a command line today, so row #8 adds the operator entry point. Widening adds empty cells and changes no value any run wrote. Verified read-only on 2026-09-20: all 82 committed rows re-validate through all three model validators and re-render.

### The shipping capability (`backend/idhazh/council/metrics_sink.py`)

The council's own path, end to end, and **not** the digest pipeline's segment-and-compaction machinery.

| Step | Who | What |
| --- | --- | --- |
| 1 | the judge's stage | builds its own metrics row and calls `ship_judge_metrics(row, out_dir=...)` |
| 2 | the capability | validates through the judge's own contract, writes one file per shard under the run directory, temp-file-then-rename |
| 3 | the workflow | uploads that directory as an artifact, with an always condition |
| 4 | the collecting job | downloads every shard's artifact merged, and appends each row to the store its contract names |

**The capability declares nothing about the payload.** It takes a `Contract` instance, a judge id and an output directory. A judge that measures nothing calls it with a row carrying only its identity and its counts.

**Why not the segment store and the compaction verb.** That verb takes no filter: it files away every ledger waiting in transit and then deletes the transit copies. The digest run's own segments are often still waiting at 22:00 when the council starts - measured 2026-09-20, 21 files across five ledgers - so a council run that compacted and then committed only its own folders would delete the digest pipeline's transit copies while leaving the files they were filed into uncommitted. The council's own path has no such collision, and it is the path the council already runs for verdict files.

### Store paths and prune targets (`backend/idhazh/ledger.py`)

| Constant | Value | Store |
| --- | --- | --- |
| `COUNCIL_DIRNAME` | `"llm-council"` | `state/llm-council/shard-outcomes/` |
| `SHARD_OUTCOMES_DIRNAME` | `"shard-outcomes"` | |
| `CONTENT_SIMILARITY_JUDGE_DIRNAME` | `"content-similarity-judge"` | `state/content-similarity-judge/metrics/` |
| `JUDGE_METRICS_DIRNAME` | `"metrics"` | |
| `MERGE_LINE_HOLDOUT_SCORES_DIRNAME` | `"merge-line-holdout-scores"` | |

Day-sharded, `<group>/<store>/<YYYY>/<MM>/<DD>.csv`. **Two directory levels and no more:** the day inventory globs one and two levels, so a third is invisible to the telemetry reader and the miss is silent.

All three stores join the prune targets (CLAUDE.md 1b: a prune verb per store) and the filled-by-nothing list until their writers land.

**`STORY_SIMILARITY_DIRNAME` is deleted in row #18**, not left holding the same string as the judge constant. Two constants carrying one value re-opens the drift the closed sets exist to close, and the prune vocabulary is built by joining those constants.

### Config knobs

| Today | Becomes |
| --- | --- |
| `run.judge_shard_timeout_minutes` | `assemble.same_story.adaptive_dedup_threshold.shard_timeout_minutes` |
| (new) | `...adaptive_dedup_threshold.shard_wrap_up_minutes`, default `12`, `ge=0` |
| (new) | `...adaptive_dedup_threshold.flush_every_pairs`, default `1`, `ge=1` |
| (new, row #21) | `...adaptive_dedup_threshold.repair_window_days`, default `14`, `ge=1`, `le=60` - how far back the night plan looks |
| (new, row #21) | `...adaptive_dedup_threshold.repair_floor_date`, a date stamp, no default - **the council's own first night.** Without it the plan names every published day the council predates, which is 29 dates on its first run |
| (new, row #21) | `...adaptive_dedup_threshold.repair_dates_a_night`, default `1`, `ge=0`, `le=4` - how many missing dates one run may add beside tonight's. Zero switches the repair off |
| (new, row #19) | `HOLDOUT_RESOLVED_FLOOR` in `knobs/placement.py`, a source constant at half the labelled population - a property of what makes the reading meaningful, not something an operator tunes down to turn a red row green |

Committed value `200`, bounds unchanged. It moves beside the pair budget and the shard count its validator already reads, and its two siblings move with it so one stage's clocks are not in two blocks. The bound reader gains a dotted-path key and keeps one reader and one refusal message. `run.shard_timeout_minutes`, the work job's own bound, does not move.

**The deadline is a backstop with room to spare.** At the committed budget a shard draws 50 pairs; at the measured 94.53 s a pair that is 78.8 minutes and at the worst measured pair 92.5 minutes, against a 200-minute bound. `stopped_on_deadline` is reachable in the type system and will not fire on the runner until the shard count drops or the budget rises, which is why row #1's oracle drives it directly. **The flush default is 1**: a rewrite of a file of at most 50 rows is not measurable beside a pair that costs 94.53 s.

---

### Row #1 - A shard keeps the verdicts it paid for

- **Scope:** the judging stage takes its own deadline, writes its verdict file from the first pair onward, and the workflow uploads whatever exists.
- **Files touched:** `backend/idhazh/stages/judge_shard.py`, `backend/idhazh/contracts/knobs/run.py`, `config/idhazh.json`, `.github/workflows/llm-council.yml`, `backend/tests/test_similarity_judge.py`, `backend/tests/workflows/test_llm_council_workflow.py`, `schemas/app-config.schema.json` (generated)
- **Acceptance gates:** local - the similarity test module, the workflow harness, contract export, drift gate. CI - full suite.
- **Oracle:** the stage driven against a fixture selection with a client that raises after k pairs leaves a file holding exactly k rows. It cannot settle what the platform does on a real cancellation - the stage's own deadline is what makes that case unreachable.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | An always condition alone does not fix this. The stage builds a list and writes once after the loop, so a cancelled shard has written nothing and the upload takes an absent path. | Andre |
| 2 | The stage takes a deadline from the shard bound minus a wrap-up margin, stops on it, writes what it has and exits clean. The work shard already does exactly this, computing from its own start with no job timestamp passed in. | Carmack |
| 3 | A header-only file is written before the first pair, so the artifact always exists and a no-files-found error becomes meaningful rather than permanent. | Andre |
| 4 | The file is rewritten whole every flush, not appended. A temp-file-then-rename has no partial state, which is what makes an interrupted shard's file readable. | Fowler |
| 5 | The flush interval and the wrap-up margin are **new knobs in the same block the shard bound moves to in row #9**, not reuses of the work shard's. `run.shard_wrap_up_minutes` exists at 12 and belongs to a different stage with a different preamble. **The default flush is 1**: a rewrite of a file of at most 50 rows is not measurable beside a pair that costs 94.53 s. | Carmack |
| 6 | The deadline's zero is the stage's own start, as the work shard already does - it passes no job timestamp in. **The margin must cover what the stage cannot see**: a checkout, an install, a weights restore and a health loop of up to ten minutes. That is why the margin is its own knob rather than a copy of 12. | Carmack |
| 7 | **The deadline is checked before a pair, never between its two calls.** A pair stopped between its calls has one reading and no agreement, so it is neither read nor abandoned, and the funnel identity in row #6 stops closing. | Andre |
| 8 | This makes `stopped_on_deadline` reachable, and `pairs_abandoned` is what keeps the judge's funnel identity closing when it fires. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | An always condition on the upload and nothing else | The oracle goes green while a cancelled shard still loses every verdict | One line, and the next overrun costs the same hours | Andre |
| 2 | Raise the bound | A bound is a backstop, not a budget | The defect survives for the next overrun | Carmack |
| 3 | Append to an open handle | An interrupted append leaves a half-written row the reader stops on | An unreadable tail | Fowler |

---

### Row #2 - The council knows which run it is

- **Scope:** the council mints a run identity of its own and hands it to every verb that writes a row.
- **Files touched:** `backend/idhazh/cli.py`, `backend/idhazh/stages/common.py`, `.github/workflows/llm-council.yml`, `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/`
- **Acceptance gates:** local - the workflow test module, ruff, mypy. CI - full suite.
- **Oracle:** a row is produced from a date and a run id passed on the command line, with no plan file on disk. It cannot settle whether the id is unique across re-runs - the platform's run id is stable across attempts, which the artifact naming handles separately.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The council has no run id today - the string does not appear in its workflow file, and the verbs that record one read it from a plan file only the digest pipeline produces. | Carmack |
| 2 | The affected verbs take **a date and a run id**, not a plan object. Those are the only two attributes either reads off it, and a stub plan is not free - the plan contract requires a generated-at stamp beside them. | Carmack |
| 3 | The run id is minted from **the day the council runs**, not the day it judges. The compaction reads a run id's first ten characters as the day the run opened and feeds it to the console's lag figure, so a yesterday prefix would publish a standing two-day lag that is not real. The judged date is already the `date` column, which is what routes a row to its store. | Carmack |
| 4 | The run identity is minted from the platform's **run id**, which is unique per repository across every workflow - **not the run number, which is unique only within one workflow** and would let a council id equal a digest run id in a column that already carries both meanings. | Carmack |
| 5 | A reader separates the 82 pair rows carrying a digest run id from the council ids that follow by the `version` stamp the row already carries. One column, one store, two meanings across time - the stamp is the discriminator, and it is free. | Carmack |
| 5 | ESCALATE: `run_id` on a pair row means the run that published the day; on a council row it means the run that judged it. Two columns, two meanings, both written down. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Reuse the digest run's id | It claims a machine and a clock for a run that never drew them, and its date prefix is a day stale | A corrupted lag figure nobody would see | Carmack |
| 2 | Give the council a planning job so the existing verb works | A job that plans nothing, to produce one string | One job, one artifact, a stage satisfying a signature | Fowler |

---

### Row #3 - The separation, written where the next agent reads it

- **Scope:** the page that owns the council states the three layers, which readings sit in which, and why - so the next agent does not put a judge's metrics on the council's row.
- **Files touched:** `docs/architecture/publishing/llm-council.md`, `docs/concepts/telemetry.md`
- **Acceptance gates:** local - `doc_load.py --changed`. CI - full suite. No application suite: documentation-only.
- **Oracle:** the page names all three layers, their stores and the rule that decides which layer a reading belongs to. It cannot settle whether a future reading is classified correctly - that is what the rule is for.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The council owns the pipe and its own execution record. Each judge owns what it measures and its own store. The capability declares nothing about a payload. | Owner, 2026-09-20 |
| 2 | The page carries the worked example that makes the rule stick: a shared margin column would mean "the grammar chose" for one judge and "a legitimate middle score" for another, and one fold would sum two instruments. | Andre |
| 3 | A judge that runs no model is a judge. The council's record has no column that assumes one, and the judge's own contract carries model columns only if it has a model. | Owner, 2026-09-20 |
| 4 | The page also carries the plain-meaning test from section 1a, because the terms it deletes were invented on this page's own subject. | Owner, 2026-09-20 |
| 5 | **No new judge-telemetry page.** The council page answers the venue question and the telemetry concept page owns the stores; a third would be the split the documentation standard forbids. | Guardrail #4 |
| 6 | Docs-only, no predecessor, so it can land first and guide every row after it. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Record the separation only in this plan | A plan is a cache of the docs, and it is deleted when it closes | The next agent re-derives it, or does not | Guardrail #4 |
| 2 | A new page for judge telemetry | Two pages answering one question, and neither authoritative | A split with no question behind it | Fowler |

---

### Row #4 - The judge-call stamp, declared once

- **Scope:** the nine columns a model-using judge's reading carries, declared as a mixin in one module, with the judge identity beside them.
- **Files touched:** `backend/idhazh/contracts/judge_call.py` (new), `backend/idhazh/contracts/export.py`, `backend/tests/contracts/test_judge_call.py` (new)
- **Acceptance gates:** local - the new contract test, contract export, drift gate, ruff, mypy. CI - full suite.
- **Oracle:** a `Contract` subclass inheriting the mixin round-trips every field through the CSV writer and reader, and the mixin declares no schema stem so nothing generates a file for it. It cannot settle whether the nine are the right nine.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A mixin over the plain model base, inherited alongside `Contract`. Never alongside the CSV protocol, which is a `typing.Protocol` in the ledger - the combination is a metaclass conflict and the import is circular. | Fowler |
| 2 | The pair row does not inherit it. Inheriting reorders the committed header and makes the store unappendable. | Fowler |
| 3 | `decode_seconds` on the mixin is one call and nothing else. The pair row's column of the same name is both calls, and its description says so. | Andre |
| 4 | The probability vector is a list of id and logprob pairs. A rendered token is right for one set of weights, two ids can collide as one string, and exponentiating a logprob throws away the precision the margin is computed at. | Andre |
| 5 | A judge with no model does not inherit this at all. It is the stamp for a model call, not for a judge. | Owner, 2026-09-20 |
| 6 | Every new contract is registered in the export tuple, or no schema is generated and the drift gate reports an orphan file instead of a missing registration. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One union row across all judges | Half the columns null per judge, and the agreement field has no meaning for a judge whose input has no order | A contract asserting two instruments are one | Fowler |
| 2 | A base class with behaviour | A shared usable field would drop every ambivalent reading and bias a fitted floor with nothing red | The cheapest code, and a silently biased sample | Andre |
| 3 | A separate health table | A join key and a second write; a run dying between the two leaves a reading with no stamp | A second store and a join every reader pays | Andre |

---

### Row #5 - The council's own shard-outcome record

- **Scope:** one row per shard per council run, saying whether the pipeline worked and what the work it hosted cost.
- **Files touched:** `backend/idhazh/contracts/council_shard_outcome.py` (new), `backend/idhazh/contracts/export.py`, `backend/idhazh/ledger.py`, `backend/idhazh/telemetry/prune.py`, `schemas/council-shard-outcome.schema.json` (generated), `frontend/src/contracts/` (generated), `docs/concepts/partitions.md`, `docs/architecture/publishing/retention.md`, `backend/tests/contracts/`, `backend/tests/retention/test_prune_range.py`, `backend/tests/workflows/test_ledger_staging.py`
- **Acceptance gates:** local - the contract, retention and staging test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the row round-trips through CSV, and the store path a date resolves to is matched by the two-level day glob the telemetry reader uses - so a store this row creates is visible rather than silently absent. It cannot settle whether the figures are true; row #17 does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The row carries no name for the unit of work. That is the separation: it reads the same whether the judge it hosted made four hundred model calls or none. | Owner, 2026-09-20 |
| 2 | `model_calls`, `tokens_in`, `tokens_out` and `model_seconds` are nullable and **null, not zero**, for a judge that runs no model. Zero would read as a broken model judge. | Owner, 2026-09-20 |
| 3 | `judge_id` is on the row so a night running two judges files rows an operator can attribute. | Owner, 2026-09-20 |
| 4 | The outcome is a three-member enum. A shard killed by the platform writes no row at all, and absence against the recorded shard count is what says so - which is why `shards` is a column. | Carmack |
| 5 | `seconds_spent` is the stage's clock, not the job's. The job includes a checkout and a weights restore this row is not about, and the digest pipeline already records job clocks. | Carmack |
| 6 | The store joins the prune targets and the day-partition page, with no writer named yet - the wording two existing stores already use for a shape that lands ahead of its producer. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Put the council's outcome on the existing work-shard machine row | That row is one work shard of one digest run and carries 113 columns this pipeline does not fill | A discriminator column on a row describing two unrelated jobs | Carmack |
| 2 | A host fingerprint per judging shard | The probe wants 1.9 GiB against a server at 96 percent of the runner, and the digest pipeline already characterises the same runner pool | An OOM risk for a reading nobody asked for | Carmack |
| 3 | Units dealt and completed on the council row | The council has no name for the unit, and the judge already counts it - two counts of one thing that can disagree | A duplicate that drifts | Owner |

---

### Row #6 - The content-similarity judge's own metrics

- **Scope:** the contract for what this judge measures, owned by this judge, in this judge's own store.
- **Files touched:** `backend/idhazh/contracts/content_similarity_judge_metrics.py` (new), `backend/idhazh/contracts/export.py`, `backend/idhazh/ledger.py`, `backend/idhazh/telemetry/prune.py`, `schemas/content-similarity-judge-metrics.schema.json` (generated), `frontend/src/contracts/` (generated), `docs/architecture/contracts/schemas.md`, `docs/concepts/partitions.md`, `backend/tests/contracts/`
- **Acceptance gates:** local - the contract test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** `pairs_dealt = pairs_read + pairs_refused + pairs_unreadable + pairs_abandoned` is enforced by a model validator, so a shard cannot file a funnel that does not close. It cannot settle whether the figures are true; row #15 does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Every column is this judge's own. A second judge declares its own contract and shares none of them. | Owner, 2026-09-20 |
| 2 | `pairs_refused` counts **pairs, not calls**. A pair is two calls, so counting calls would over-count a pair that failed twice and make the identity go red on a real event rather than on a defect. | Andre |
| 3 | `pairs_abandoned` is a column because the deadline row #1 adds makes it reachable, and without it the identity fails on exactly the shard the deadline exists to let report. | Andre |
| 4 | Rates are nullable and null on an empty shard. A rate over zero rows is not zero. | Andre |
| 5 | The margin median carries a warning in its own description: it is not comparable to another judge's, because a flat distribution means opposite things for a verdict judge and a rated scorer. **A column may be compared across judges only when it is a count or a clock.** | Andre |
| 6 | This row is a record, not an alarm. The line-setting gates already fire on the day-grain rates, and a second threshold here would be an answer nobody could reconcile with the first. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A shared vitals mixin every judge inherits | It is the council dictating a judge's metric set, which is the coupling this plan exists to remove | Three columns judge two cannot have and one that inverts | Owner |
| 2 | A free-text metrics blob on one shared row | Nothing validates it, nothing generates a type, no schema diff fires when a judge changes what it records | Guardrail #3 broken | Fowler |
| 3 | Derive the funnel at read time from the verdict rows | A shard that wrote no verdicts becomes indistinguishable from one that never ran | The one failure the row exists to show | Andre |

---

### Row #7 - The content-similarity judge's merge-line benchmark record

- **Scope:** the persisted shape for scoring the merge line against the labelled holdout, with its store and prune target.
- **Files touched:** `backend/idhazh/contracts/merge_line_holdout_score.py` (new), `backend/idhazh/contracts/export.py`, `backend/idhazh/ledger.py`, `backend/idhazh/telemetry/prune.py`, `schemas/content-similarity-judge-merge-line-holdout-score.schema.json` (generated), `frontend/src/contracts/` (generated), `docs/architecture/contracts/schemas.md`, `docs/concepts/partitions.md`, `backend/tests/contracts/`
- **Acceptance gates:** local - the contract test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the row refuses a set of cells whose sum exceeds the labelled population. It cannot settle whether the cells were counted correctly; row #19 does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | It scores the LINE, not the judge. The holdout rows carry no verdict, the shipped implementation calls no model, and the labels were written outside the pipeline. | Andre |
| 2 | It does not inherit the call stamp. Eight call columns here would be five nulls and one asserting an instrument that never ran. | Andre |
| 3 | A labeller column, free text rather than a model id, because the committed labels name a model outside the registry. | Andre |
| 4 | Counts only, no stored rate. Every rate is derived at read time with the negative population in view. | Guardrail #10 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Store precision and recall | With four labelled negatives one flip moves the rate 25 points, and a stored rate loses its denominator | A number that reads as a measurement | Guardrail #10 |
| 2 | Put the call stamp on it for symmetry | Symmetry that asserts a model ran when none did | Five null columns and one false one | Andre |

---

### Row #8 - The pair row gains the stamp, and the store is rewritten

- **Scope:** the pair row gains five columns at the tail, the reader learns to fill a non-null default, and the committed file is widened so the store stays appendable.
- **Files touched:** `backend/idhazh/contracts/story_similarity_pair.py`, `backend/utilities/widen_ledger_header.py` (new), `schemas/story-similarity-pair.schema.json` (generated), `frontend/src/contracts/` (generated), `state/story-similarity/scored-pairs/2026/09/18.csv`, `docs/architecture/contracts/schemas.md`, `backend/tests/contracts/`, `backend/tests/fixtures/`
- **Acceptance gates:** local - the contract tests, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** a fixture carrying the pre-change header is widened, then a fresh row is appended to it through the ledger's own append path without raising. **The append is the load-bearing half** - a read-only oracle cannot see the header equality check that makes the store unappendable.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The columns are appended in the row's own body, not inherited, so the header widens rather than reorders. | Fowler |
| 2 | The reader adds one field to its existing by-name branch. A general predicate over non-`None` defaults would also pop `version`, which a before-validator refills with this build's stamp - silent coercion on the header sentinel. | Fowler |
| 3 | **Nothing in the repository can widen a header from a command line today.** The row adds an operator utility under `backend/utilities/`, which pytest does not collect, taking a store from the prune vocabulary and dry-running by default as the prune verb does. | Fowler |
| 4 | The committed file is widened in the same commit, or the append check refuses it and the next re-dispatch of that date kills the commit step and every ledger staged beside it. | Andre |
| 5 | `judge_id` carries a default rather than being required, so the widening can fill it and the selection stage - which writes these rows with verdict columns empty - does not invent an instrument. | Fowler |
| 6 | ESCALATE: committed rows are rewritten. Sign-off before the utility runs. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Inherit the mixin here too | The header reorders and the append raises; the store dies | One declaration instead of two, and a dead store | Fowler |
| 2 | Leave the committed file alone | The check refuses it on the next append and takes the commit step down | A failed run later | Andre |
| 3 | Start a new store at the new shape | Two stores for one question, joined by every reader for ever | A permanent fork | Fowler |

---

### Row #9 - The shard timeout moves to the block that validates it

- **Scope:** the judging shard's timeout knob is renamed and moved beside the two numbers its validator reads, with its two clock siblings, and the reader learns a dotted path.
- **Files touched:** `backend/idhazh/contracts/knobs/run.py`, `backend/idhazh/contracts/knobs/` (the receiving block), `backend/idhazh/contracts/app_config.py`, `config/idhazh.json`, `backend/utilities/shard_bound.py`, `.github/workflows/llm-council.yml`, `frontend/src/lib/server/config.ts`, `docs/concepts/config.md`, `backend/tests/contracts/test_app_config.py`, `backend/tests/workflows/test_llm_council_workflow.py`, `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`, `schemas/app-config.schema.json` (generated), `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - the two named test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the dotted key the workflow passes and the field the contract declares resolve to the same value, and the reader returns a bare positive integer. It cannot settle whether the bound is the right size.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The knob leaves the generic run block for the block holding the pair budget and the shard count its validator already reads, and the wrap-up and flush knobs land beside it. | Fowler |
| 2 | The bound reader resolves a dotted path rather than a leaf under a fixed block. One reader, one refusal message. | Carmack |
| 3 | A straight rename in one commit. One config file, one fixture, no payload an earlier run wrote. | Fowler |
| 4 | The hand-written frontend config mirror moves with it, or the two disagree silently. | Fowler |
| 5 | ESCALATE: the knob and the workflow key land in one commit, or the workflow resolves no bound and the shard runs to the platform ceiling. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave it in the run block | The validator keeps asserting something pair-specific about a generic knob | Two timeouts neither of which says what it bounds | Fowler |
| 2 | A block flag beside the key flag | Two ways to spell one address | A second grammar | Carmack |

---

### Row #10 - The judge's own bound reads a measured number

- **Scope:** the judge's shard bound is sized from a measured per-pair reading instead of a derived per-call one, and the reading is written up. **Nothing outside the judge's own arithmetic moves.**
- **Files touched:** `backend/idhazh/contracts/knobs/placement.py` (a new judge-specific constant beside the existing one, which does not change), `backend/idhazh/contracts/app_config.py` (the judge's validator arm only), `.github/workflows/llm-council.yml` (the header comment), `docs/reference/benchmarks/what-a-judge-pair-costs.md` (new), `backend/tests/contracts/test_app_config.py`
- **Acceptance gates:** local - the named test module, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the page's figures reproduce by re-running its stated arithmetic over the committed file it names, **and the validator arm that bounds the work shard returns the same value before and after this row**. The second half is the load-bearing one: it proves the judge's number did not move anybody else's.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The reading is **94.53 s a pair** - min 72.80, max 110.98, population sd 7.84, n = 82, judged 2026-09-18 on four stock runners, `Qwen3.5-9B-Q4_K_M`. The four shards' means spread 88.24 to 99.89 s, a 13.2 percent lottery. | Carmack |
| 2 | **`SECONDS_A_CALL` does not change.** It sizes the work shard's budget as well as the judge's, so one judge's measurement moving it drags every other budget with it - and the other consumers have no measurement behind the move. The judge gets its own constant, measured, beside the shared one. | Owner, 2026-09-21 |
| 3 | **A per-pair figure, not a per-call one.** The committed column is the sum of both calls and the second reuses the system-turn prefix, so any halving is an inference with the direction known and the magnitude unknown. Sizing a pair budget in pairs removes the need to split it at all. | Andre |
| 4 | The bound is sized against the worst measured pair, not the mean. A max 17 percent above the mean is what a bad night looks like, and the page says which statistic sizes the bound. | Carmack |
| 5 | **The council page and the handover are left alone.** Their stale figures are corrected by the rows that already touch them - row #3 rewrites the council page and row #19 the handover - rather than dragging two more files into a budget row. | Owner, 2026-09-21 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Replace the shared constant everywhere it is quoted | One judge's measurement then re-sizes the work shard's budget, the placement arithmetic and two doc pages, none of which was measured | A twelve-file row that fails on a surface nobody was changing | Owner |
| 2 | Keep the derived figure | An unlabelled 1.64x margin sizes the judge's bound | A budget built on a number nobody took | Carmack |
| 3 | Wait for a night at the cap | The cap has never run and nothing schedules it | One dispatched run | Carmack |

---

### Row #11 - The judge can think, and the decode says whether it did

- **Scope:** the judge call adopts the two-span shape the summariser already uses, so a model with a thinking channel reasons first and answers inside the grammar second; the stamp records which shape ran; and the margin is taken over the verdict openings under a pinned probability mode.
- **Files touched:** `backend/idhazh/llm/server.py`, `backend/idhazh/similarity/judge.py`, `backend/idhazh/similarity/prompt.py`, `backend/idhazh/similarity/stamps.py`, `backend/idhazh/similarity/fold.py` (the change detector), `backend/tests/test_similarity_judge.py`, `backend/tests/fixtures/`, `docs/reference/benchmarks/which-probabilities-the-server-returns.md` (new)
- **Acceptance gates:** local - the similarity test modules, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** a canary drives a recorded reply from a model entry declaring a thinking close and asserts the verdict is read from the **answer** span with the thinking span recorded and not parsed as a verdict; a second drives a reply whose returned window omits a verdict opening and asserts a null margin rather than a gap between two prefixes. It cannot settle what a live model returns.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **Thinking is supported, not refused.** An earlier draft refused a call whose model entry opened a thinking channel. That was wrong: the temperature is already above zero for writing that reads like a person wrote it, and thinking mode is coming. A guard that breaks the judge the day the feature lands is not a guard. | Owner, 2026-09-21 |
| 2 | **The machinery already exists and the judge is the only caller not using it.** The model layer carries a thinking span and an answer span, and the summariser's payload builder sends the template flag that turns the channel on. The judge's builder is single-span and sends no flag. It adopts the two-span shape. | Owner, 2026-09-21 |
| 3 | **The grammar constrains the answer span, never position zero.** That is the whole defect the refusal was reaching for: constraining the first token forces a verdict where the model meant to start reasoning, the reply still parses, and the margin then describes a reasoning channel with nothing saying so. Constraining the answer span makes the margin a reading about the verdict again, whether or not the model thought first. | Andre |
| 4 | **The stamp records which shape ran**, so a margin taken after a thinking span and one taken without are distinguishable. The change detector sees it, because a verdict produced after reasoning is not the same measurement as one produced cold. | Andre |
| 5 | The window is sized to the grammar's legal first-token set at the answer position - the 25 non-empty prefixes of its six legal strings - not to the count of verdict words. | Andre |
| 6 | **Widening the window alone changes the margin by nothing**, because the margin is the top two of whatever came back. So it is taken over the three verdict-opening ids, renormalised, and is null when fewer than two are present. The stage already computes those ids and discards them. | Andre |
| 7 | The probability mode is sent explicitly rather than inherited from a build default, and which mode the server returns is measured and written up. | Andre |
| 8 | The digest covers exactly six posted keys and is held to the payload by a test that enumerates the builder's keys and fails on one the digest neither covers nor excludes by name. | Andre |
| 9 | The change detector gains the temperature, the decode digest and the thinking shape in this commit. A stamp column the detector cannot see is a stamp that lies. | Andre |
| 10 | ESCALATE: widening the detector resets the distribution once, by construction. Row #21 decision 5 says why that is correct and how it is recorded. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Refuse a call whose model entry opens a thinking channel | It breaks the judge on the day thinking mode ships, and thinking mode is a stated direction. A guard against a feature you intend to use is a bug with a schedule | A judge that stops working when the writing improves | Owner |
| 2 | Constrain the first token and let the model think inside the grammar | The grammar admits three verdict words; a model that meant to reason emits one of them at position zero and the reasoning never happens. The reply parses and the reading is wrong | A silent measurement failure | Andre |
| 3 | Keep the three-wide window | It is sized to the answer set rather than to what the grammar admits | A margin over the wrong tokens | Andre |
| 4 | Assert thinking off in the prompt wording | Prompt wording is not a control, and a template cannot close a channel the server opened | A guard that reads as one without being one | Andre |

---

### Row #12 - The four verbs name their work

- **Scope:** the same-story verbs, their stage modules, their stage functions and the workflow job ids are renamed to say what they do.
- **Files touched:** `backend/idhazh/cli.py`; `backend/idhazh/stages/judge_draw.py` -> `pick_item_pairs.py`; `judge_shard.py` -> `judge_item_pairs.py`; `judge_fold.py` -> `count_verdicts.py`; `judge_fit.py` -> `set_merge_line.py`; `backend/idhazh/similarity/fit.py`, `fold.py`; the three similarity test modules; `.github/workflows/llm-council.yml`; `docs/how-to/label-the-similarity-holdout.md`; `docs/reference/repository-layout.md`; `docs/architecture/publishing/autotune-content-similarity.md`; `docs/architecture/publishing/llm-council.md`
- **Acceptance gates:** local - the changed-test selector over the similarity modules, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the stage tuple and the verbs the workflow spells are compared name for name by the workflow harness. It cannot settle whether the new names are better - decision 1 is the owner ruling.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `judge-draw` -> `pick-item-pairs`, `judge-shard` -> `judge-item-pairs`, `judge-fold` -> `count-verdicts`, `judge-fit` -> `set-merge-line`. | Owner, 2026-09-20 |
| 2 | A verb names its subject, and nothing is named `judge-<step>` again. That is what lets the summary-quality judge take `pick-summaries`, `score-summaries` and `count-scores` without colliding. | Fowler |
| 3 | A judge whose emitted token is the answer takes the `judge-` stem; one whose token is discarded and whose distribution is the answer takes `score-`. | Andre |
| 4 | The workflow job ids move with the verbs: `draw` becomes `pick`, `fold` becomes `collect`. | Owner, 2026-09-20 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A two-level judge namespace | The router would hold a name registry, and only one of four steps is shared with judge two | A dispatch table and a package with no reason to exist | Fowler |
| 2 | Keep the family prefix | The prefix is what ties the verbs to one loop, which is the defect | The second judge's verbs lie or break the pattern | Fowler |

---

### Row #13 - `leg` and `fold` leave the vocabulary

- **Scope:** the two borrowed words are deleted from identifiers, field descriptions, docstrings and prose, and the plain-meaning test that caught them is written down.
- **Files touched:** the eighteen files carrying `leg`; `backend/idhazh/similarity/fold.py` -> `counting.py`; `backend/idhazh/similarity/draw.py` -> `selection.py`; `backend/idhazh/contracts/fitted_similarity_threshold.py`, `story_similarity_pair.py`, `knobs/placement.py`, `knobs/run.py` (field descriptions); `schemas/` (generated); `CLAUDE.md` section 0b; `docs/architecture/publishing/llm-council.md`
- **Acceptance gates:** local - the similarity and contract test modules, contract export, drift gate, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** a grep over tracked text finds no `leg`, `legs`, `arm` or `fold` used as a name for a shard or for the collecting job. It cannot settle whether a future borrowed word is caught - that is what the test in section 0b is for.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `leg` is a pure synonym for `shard` - 75 occurrences across 18 files, every one meaning the thing the `shard` column already names. It is deleted, not replaced. | Owner, 2026-09-20 |
| 2 | `fold` is functional-programming vocabulary for the job that collects the shards' output, commits it and counts it. The job becomes `collect`, and **prose names the action, never the job**: "a day with a missing shard is not counted into the record". | Owner, 2026-09-20 |
| 3 | The repository has done this scrub before - `arm` became `cases` on 2026-09-15 with a read-side migration - so the pattern and its changelog wording already exist. | Fowler |
| 4 | Two occurrences of `leg` mean a clause of a two-part rule rather than a shard. Those become "the first of two checks". | Fowler |
| 5 | Four contract files carry the word in **field descriptions**, so the scrub regenerates schemas and takes a changelog line. No field name or value moves, so no payload migrates. | Section 11 |
| 6 | The plain-meaning test goes into section 0b, where the voice rules live, because this is the fourth borrowed word this repository has had to remove. | Owner, 2026-09-20 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Invent a new word for a shard | There is nothing to name - the concept already has a name used everywhere else | A third synonym | Fowler |
| 2 | Leave the field descriptions and fix only identifiers | The descriptions are the generated schema, so the word survives in the published contract | A word deleted from code and kept in the artifact | Section 11 |
| 3 | Scrub `fit` as well | "Fit a line to evidence" is ordinary English, and the verb rename already fixed the surface a person types | Churn with no reader gain | Fowler |

---

### Row #14 - The judge fills the stamp

- **Scope:** the judging stage records, per reading, which judge read it, at what temperature, under which posted sampler, whether both calls opened inside the grammar, and what the returned window held.
- **Files touched:** `backend/idhazh/stages/judge_item_pairs.py`, `backend/idhazh/similarity/judge.py`, `backend/idhazh/similarity/counting.py`, `backend/idhazh/similarity/stamps.py`, `backend/tests/test_similarity_judge.py`, `backend/tests/fixtures/`
- **Acceptance gates:** local - the similarity test modules, ruff, mypy. CI - full suite.
- **Oracle:** a recorded reply whose window omits a verdict opening produces a row with the grammar flag recorded, `usable` false, `verdict` null, and the counting step skips it - and the stage exits 0. **The margin is not asserted against the vector**, because both derive from one tuple and that assertion is a tautology that cannot go red.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A grammar failure is recorded rather than raised. Today it raises and the stage dies, so absence means two things an operator cannot separate. | Andre |
| 2 | **The agreement test gains a null check in the same change.** It compares the two verdicts today, and a nullable verdict makes two failures compare equal - so `usable` would go true with no verdict, and the pair row's own validator refuses exactly that shape. The writer that reaches for the verdict's value maps null to empty rather than raising on it. | Andre |
| 3 | The grammar flag means **both calls** opened inside the grammar, and the judge's `pairs_refused` counts rows where it is false. | Andre |
| 4 | **Both calls always run.** A first-call failure does not skip the second, or the pair row's decode seconds - documented as both calls - silently becomes one. | Andre |
| 5 | The judging stage is the only writer of the stamp's model-side columns. The selection stage writes the row with verdict columns empty and carries only the defaulted judge identity. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep raising on a grammar failure | Absence means two different things and an operator cannot separate them | A failure that reads as a missing shard | Andre |
| 2 | Assert the margin against the stored vector | Both derive from one tuple, so the oracle passes in every failure world | A green test that proves nothing | Andre |

---

### Row #15 - The judge writes its metrics, and the council ships them

- **Scope:** the shipping capability, and the content-similarity judge as its first caller.
- **Files touched:** `backend/idhazh/council/__init__.py` (new), `backend/idhazh/council/metrics_sink.py` (new), `backend/idhazh/stages/judge_item_pairs.py`, `backend/idhazh/stages/count_verdicts.py`, `backend/idhazh/ledger.py`, `.github/workflows/llm-council.yml`, `backend/tests/`, `backend/tests/workflows/test_ledger_staging.py`, `docs/architecture/publishing/llm-council.md`
- **Acceptance gates:** local - the similarity, council and staging test modules, the workflow harness, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** every metrics file a shard writes is uploaded under a name the collecting job's download pattern matches, and the appended store holds one row per shard the run recorded. **Not "the staged path list mentions the store"** - staging a path on a machine where the file was never written stages nothing and exits 0, so that assertion goes green over an instrument that records nothing.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The capability declares nothing about the payload.** It takes a contract instance, a judge identity and an output directory, validates, and writes one file a shard with a temp-file-then-rename. | Owner, 2026-09-20 |
| 2 | **The council's own artifact path, and the reason is that a commit would not reach the reader.** Every checkout in the council names no ref, so each job is pinned to the commit the run started at. A shard that commits its rows at 22:40 puts them where the collecting job - checked out at 22:00 - cannot see them, and the counting step decides whether every shard reported by counting the files it downloaded. Moving the rows into the tree does not make them safer; it makes them unreachable. | Fowler |
| 3 | **Segments solve a conflict this workflow does not have.** The compaction's own docstring says they are where a writer puts its rows when more than one job writes one ledger. The digest pipeline has four to eight committing shards on one day file; the council has one committing writer, and its day file is already settled on every write by a key carrying the run id - which is the property segments exist to provide. | Fowler |
| 4 | This is the path the council already runs for its primary data: the collecting stage appends every judged pair to the day file and pushes, tonight and every night. The metrics take the path the verdicts already take. | Carmack |
| 5 | **The trigger that adopts segments, stated so it is a condition rather than a preference:** a judging shard whose output is too large for an artifact, or which must survive the artifact's 24-hour retention. Adopting them then also requires giving the collecting job a way to see commits made during its own run, which it does not have today. | Owner, 2026-09-20 |
| 6 | **A judge that needs no model needs no shards.** Sharding exists because the model is slow. A pure-Python judge gets one job, so it has one writer and none of this applies to it. | Carmack |
| 7 | The upload carries an always condition, and the shard uploads as it goes rather than once at the end. **The real exposure was never the collecting job dying - it is a shard dying**, which today ships nothing at all after up to 79 minutes of judging. | Carmack |
| 8 | The collecting job appends each row to the store its own contract names, so a second judge needs no change here. | Fowler |
| 9 | The staging drift guard is widened in this row to every workflow reaching a store writer, not only the daily one. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Shards commit segments; the digest pipeline's compaction files them later | The collecting job cannot see commits made during its own run, so a re-run finds an empty directory. It also makes the council able to stop publishing: the compaction parses every waiting row through its contract and runs before the digest run plans a day, so one malformed judge row ends that run | Rows the counting step cannot reach, a cross-pipeline outage path, and three closed sets widened per judge | Fowler |
| 2 | The collecting job writes segments instead of appending | One writer cannot conflict with itself, and the rows then wait for another pipeline's schedule - up to 4.8 hours - to become readable | A dependency on someone else's cron for no gain | Fowler |
| 3 | Segments plus the council running the compaction verb | The verb has no filter and the transit directory is shared | Twenty-one waiting files deleted, their heads uncommitted | Carmack |
| 4 | A capability that defines the metric columns | That is the council dictating a judge's metrics - the coupling this plan removes | Judge two files columns it cannot have | Owner |

---

### Row #16 - The model block becomes one composite action

- **Scope:** the weights cache, the fetch, the checksum verify, the server start and the health probe become one composite action, used by the two workflows that run all five steps.
- **Files touched:** `.github/actions/model-server/action.yml` (new), `.github/workflows/llm-council.yml`, `.github/workflows/digest.yml`, `backend/tests/workflows/_harness.py`, `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/workflows/test_model_server_jobs.py`, `backend/tests/workflows/test_weights_and_model_refs.py`
- **Acceptance gates:** local - the workflow harness across both files. CI - full suite.
- **Oracle:** the cache key literal inside the action matches a committed fixture character for character. **Not a comparison against the daily workflow** - once the key moves into the action there is nothing left there to compare against.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Measured across all eleven workflow files - one ends `.yaml`, which is how an earlier count missed it: four call the shared fetch script, three spell the server-start step verbatim, and one runs all five under its own names. This row converts the two that run the five identically. | Carmack |
| 2 | **This row lands before row #17**, because row #17's oracle asks where a step sits relative to the server start and this row moves that step into the action. | Carmack |
| 3 | Every test that looks a weights step up by name moves with it. Four modules do, including two tables in the shared harness pinning three step names for three jobs. | Carmack |
| 4 | A composite action carries no job-level knob, so the bound, the matrix and the runner label stay in the workflow. The cache-hit output is declared explicitly or the fetch condition silently stops working. | Carmack |
| 5 | The one-server-per-shard guard survives by reading the action's step list rather than the job's. It is what stops a second server landing on a 16 GB runner. | Carmack |
| 6 | Whether a composite step sees the caller's workflow-level environment is verified on a branch first; if it does not, the port becomes an action input. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A callable workflow | Its only unique benefit is a per-caller runner label and permission set, and nothing needs either | A restructure for a differentiation nothing uses | Carmack |
| 2 | Convert all six cache blocks | Four share one of the five steps; folding them in makes the action a parameter soup | Four callers using a tenth of it | Carmack |

---

### Row #17 - The council records its own shard outcomes

- **Scope:** each judging shard writes the council's own outcome row, the workflow ships it, and the collecting job commits it.
- **Files touched:** `backend/idhazh/council/metrics_sink.py`, `backend/idhazh/stages/judge_item_pairs.py`, `backend/idhazh/stages/count_verdicts.py`, `.github/workflows/llm-council.yml`, `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/workflows/test_staged_paths.py`, `backend/tests/workflows/test_ledger_staging.py`, `state/llm-council/.gitkeep`
- **Acceptance gates:** local - the three workflow test modules and the council test module. CI - full suite.
- **Oracle:** a run that records three of four shards leaves a store an operator can read as "one shard is missing", because the recorded shard count and the row count disagree. It cannot settle why the shard is missing.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The council records the shard's identity, its clock, its outcome and the aggregate cost of the work it hosted - and nothing that needs a name for the unit. | Owner, 2026-09-20 |
| 2 | **No host fingerprint.** The probe wants 1.9 GiB against a server at 96 percent of the runner, the council's data is discardable, and the digest pipeline already characterises the same runner pool. Dropping it removes the only memory risk in this plan rather than ordering around it. | Carmack |
| 3 | **No per-call spans and no span rollup.** The judge's own row carries the call count, the total and the worst, which is what the three questions actually need. | Owner, 2026-09-20 |
| 4 | The outcome row is written by the same capability the judge metrics use, so there is one shipping path and not two. | Fowler |
| 5 | The store is seeded with a `.gitkeep`, **not a header-only day file**. A header-only file at a day path is a real day file to the partition walker - a permanent phantom day in the prune target and the day inventory. The three seeded directories in this repository are all `.gitkeep`. | Fowler |
| 6 | This row assumes plan 37's corrected sampler and does not wait for it. Nothing here reads the sampler. | Owner, 2026-09-20 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Import the digest workflow's observability set | Half of it answers questions a judge does not have, and its item-health row carries 113 columns this pipeline does not fill | Stores that stay empty or carry meaningless rows | Owner |
| 2 | Record the machine per shard | The runner pool is already characterised, and the probe is the only OOM risk in the plan | A reading nobody asked for | Carmack |

---

### Row #18 - The store groups under the judge that fills it

- **Scope:** the committed same-story tree moves under the judge slug that produced it, and every reader, workflow path and document naming the old tree moves with it.
- **Files touched:** `backend/idhazh/ledger.py`, `backend/utilities/sample_sheet.py`, `state/story-similarity/` -> `state/content-similarity-judge/`, `.github/workflows/llm-council.yml`, `.gitattributes`, `frontend/src/lib/server/similarity-holdout.ts`, `frontend/src/routes/console/judgement/+page.server.ts`, `docs/reference/repository-layout.md`, `docs/architecture/publishing/autotune-content-similarity.md`, `docs/architecture/contracts/schemas.md`, `docs/concepts/partitions.md`, `docs/concepts/growing-reads.md`, `docs/architecture/publishing/retention.md`, `docs/how-to/label-the-similarity-holdout.md`, `TODO/20260920-a-second-judge-in-the-council-handover.md`, `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/retention/test_prune_range.py`, `backend/tests/`
- **Acceptance gates:** local - the ledger and similarity test modules, the workflow harness, the frontend build, `doc_load.py --changed`. CI - full suite, plus the published-site smoke.
- **Oracle:** no reader in backend, frontend, workflows or docs resolves a path under the old name - a grep over tracked files, asserted once. **The file-by-file byte comparison is an operator check run during the move**, not a committed test: walking the tree every run is a growing read.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge slug is the group, so the store a judge produces sits under the judge's name, beside its metrics store. | Owner, 2026-09-20 |
| 2 | The stores under it keep their names - scored pairs, fitted thresholds, the distribution record, the holdout and the archive all move unchanged. | Fowler |
| 3 | The council workflow names the old paths in its commit step. It moves here, or the next run's staging aborts under a failing shell and costs the ledgers beside it. | Carmack |
| 4 | **`STORY_SIMILARITY_DIRNAME` is deleted**, not left holding the new string. Two constants carrying one value re-opens the drift the closed sets exist to close, and the prune vocabulary is built by joining those constants - so the prune words move with them. | Fowler |
| 5 | `git mv` per file, so history follows and the move reviews as a rename. A rename of the tree, not a rewrite of its rows. | Fowler |
| 6 | ESCALATE: this moves committed data. The path map is signed off before any file moves. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the tree and put only new judges under slugs | Two organising schemes, and the oldest judge looks like the exception | A layout no reader can infer a rule from | Fowler |
| 2 | Leave a compatibility path | A second name for one store | One path that works and one that used to | Fowler |

---

### Row #19 - Where the content-similarity judge's merge line stands against its holdout

- **Scope:** the merge line is scored against the labelled holdout and the four counts are committed, with the negative population beside them and a floor below which the reading is refused.
- **Files touched:** `backend/idhazh/similarity/holdout.py` (new), `backend/idhazh/stages/score_merge_line_holdout.py` (new), `backend/idhazh/cli.py`, `backend/idhazh/ledger.py`, `backend/idhazh/contracts/knobs/placement.py`, `frontend/src/lib/server/similarity-holdout.ts`, `frontend/src/routes/console/judgement/+page.server.ts`, `docs/architecture/publishing/autotune-content-similarity.md`, `docs/how-to/label-the-similarity-holdout.md`, `docs/concepts/growing-reads.md`, `backend/tests/workflows/test_ledger_staging.py`, `backend/tests/`
- **Acceptance gates:** local - the similarity and contract test modules, ruff, mypy, `doc_load.py --changed`, the frontend build. CI - full suite, plus the published-site smoke.
- **Oracle:** the four cells plus the unresolved count sum to the labelled population, **and** the resolved count clears the floor - without the floor, a run that resolved nothing satisfies the sum with four zeros and a full unresolved count, and the row reads as a measurement.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | It scores the line, not the judge. A judge-against-holdout measurement is a different row and a different budget, named in the scope-out table. | Andre |
| 2 | A shipped implementation already does this in the console's server layer. This row commits the counts so the reading survives the page, and the console then reads the committed row instead of recomputing beside it - two answers to one question is what the commit exists to stop. On a date with no row the console says the line has not been scored, never an error. | Andre |
| 3 | The read is bounded by the holdout file, whose rows name their own two days. | Guardrail #12 |
| 4 | ESCALATE: the floor is **half the labelled population**, a constant beside the frozen two-story maximum rather than a config knob, because it is a property of what makes the reading meaningful and not something to tune down to make a red row green. Retention deletes days the holdout still names, so this floor is reached by the calendar rather than by a bug. | Owner, 2026-09-20 |
| 5 | The frozen two-story maximum in the knobs module is reconciled with this row or retired, so one number does not have two sources. | Andre |
| 6 | The verb is `score-merge-line-holdout`. A person types it; nothing in the daily pipeline calls it. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Publish one accuracy figure | With 196 of 200 pairs on one side, always answering "one story" scores 98 percent and measures nothing | A number that looks excellent while the line is useless | Andre |
| 2 | Have the judge label more holdout pairs | The holdout's authority comes from being labelled outside the loop | The floor becomes a copy of the line it polices | Andre |
| 3 | Keep only the console panel | A reading that exists only while a page renders cannot be compared across weeks | No history | Andre |

---

### Row #20 - The plan pointer

- **Scope:** the index that lists live plans learns this one exists, and the findings that outlive the plan reach the pages that own them.
- **Files touched:** `AGENTS.md`, `docs/reference/agent-notes/`, `docs/architecture/publishing/autotune-content-similarity.md`
- **Acceptance gates:** local - `doc_load.py --changed`. CI - full suite. No application suite: documentation-only closure.
- **Oracle:** every live plan file is named by the agent index, and every entry names a file that exists.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A plan absent from the index is invisible to the next agent. | Fowler |
| 2 | **The plan-queue page is not touched.** A gate refuses any pull request that edits it and tells the author to restore it from the trunk; one job writes it after merge, and it discovers plans structurally - it already names this plan. | Fowler |
| 3 | The findings that outlive the plan go to the living doc that owns them. The separation itself went to the council page in row #3, which is why it is not repeated here. | Guardrail #4 |

---

### Row #21 - The council repairs its own missing nights

- **Scope:** the council judges every date its record has not counted, within a window floored at the council's own first night, recovering a dead run's uploads where they still exist and re-judging where they do not. **No operator action repairs a dead night.**
- **Files touched:** `backend/idhazh/council/night_plan.py` (new), `backend/idhazh/cli.py`, `backend/idhazh/contracts/app_config.py`, `backend/idhazh/contracts/knobs/` (the window, the floor and the per-night cap), `config/idhazh.json`, `.github/workflows/llm-council.yml`, `backend/tests/`, `backend/tests/workflows/test_llm_council_workflow.py`, `backend/tests/contracts/test_app_config.py`, `docs/architecture/publishing/llm-council.md`, `schemas/app-config.schema.json` (generated), `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - the council, workflow and app-config test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** driven against a fixture record and store, the night plan names a date whose day file holds **three of four shards' rows** - the shape the dominant failure actually produces - and does not name a date the record has counted. **The read is bounded by the window it is asked about** (Guardrail #12). It cannot settle whether the recovery succeeds on a runner.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The gap predicate is "the record has not counted this date", never "no committed evidence".** A run that lost one shard still commits the other three shards' rows, so a date with 75 percent of its pairs on disk is the common failure and reads as evidence. The one value meaning "this date is not in the fit" is the record's own counted-dates list. | Andre |
| 2 | **The record keeps a second date list that survives a reset.** Resetting the counts is correct when the instrument moves - the old counts were taken under a different instrument. Resetting the memory of WHICH dates were read is not: the stamp governs the counts and has nothing to say about which nights the council saw. So `judged_dates` persists across the archive-and-empty, and the gap predicate reads it. **Without this the design latches**: widening the stamp empties the record, every date becomes a gap, decision 3 refuses all of them, no judging job runs, so nothing ever empties the record again and nothing on the schedule can clear it. | Andre |
| 3 | **A date is refused only when the record previously counted it under an instrument that has since moved.** A date the council has never seen is judged normally whatever the stamps say, which is what keeps tonight working through an instrument change. | Andre |
| 4 | **The counting step admits only rows the record's own stamp matches**, and that filter runs BEFORE the one-row-a-pair de-duplication - otherwise a discarded row from the old instrument can still win a tie-break against a fresh one. Every value the filter needs is already a column on the pair row. | Andre |
| 5 | **Widening the stamp resets the record exactly once, and that is correct rather than a defect.** Nobody recorded the temperature or the posted body behind today's counts, and row #8 fills those cells empty rather than inventing them. Measured 2026-09-21: the record holds one date and eight agreed NO readings against gates of ten days and 200 negatives, so the reset costs four percent of the evidence the line needs before it can move at all. It lands in row #11's commit beside the record widening, so the council judges that night as on any other night. Three existing surfaces record it - the archived file in the run's commit, the run log's report, and that date's fitted row carrying its held reason beside the new stamp. No new state, no new alarm. | Andre |
| 6 | **The window has a floor: the council's first night.** The store holds one day file against 30 published days, so an unfloored predicate names 29 dates on its first run and cannot tell "this night died" from "the council did not exist yet". | Carmack |
| 7 | **A per-night cap with a committed value of 1**, plus the floor. A cap without a floor only slows a 29-date backfill to 29 nights. | Carmack |
| 8 | **The judging job's timeout is per job, so a catch-up date costs wall clock, not headroom.** At the committed budget a shard judges 50 pairs at the measured 94.53 s a pair - 78.8 minutes against a 200-minute bound, per job, per date. | Carmack |
| 9 | **The matrix's parallel width becomes shards times dates**, capped at the platform's 20-job ceiling. It is the shard count today, so two dates would otherwise run as two waves and finish near 01:30 rather than 23:30. The timeout clock starts when a job begins executing, not when it is queued, so a queued job still gets its full bound. | Carmack |
| 10 | **The config validator that guarantees a shard fits gains the date cap as a multiplier**, and its refusal message names the cap as a fourth knob to lower. Without it the validator passes at 50 pairs while the run costs two dates. | Carmack |
| 11 | **Every artifact name carries the date.** Two dates in one run would either fail the job on an immutable name or silently overwrite the first date's verdicts. The collecting job's download pattern moves with them. | Carmack |
| 12 | **Recovery needs two things the workflow does not have, and neither is a stored secret.** The permissions block declares one scope and a declared block sets every unlisted scope to none, so cross-run download needs `actions: read` and the default credential passed explicitly. And **the uploads expire after one day**, before the next night's collecting job reaches them - so verdict retention rises to the cap plus two. A shard file is about 27 KB, so a week of four shards is under a megabyte. | Carmack |
| 13 | **The collecting job is per date.** Its two verbs, both commit messages and - the dangerous one - the command that rebuilds the derived record after a lost push all name a single date today. Left alone on a two-date night the rebuild would regenerate one date and drop the other's count. | Carmack |
| 14 | **An explicit dispatched date replaces the night plan entirely** and judges exactly that date. An operator naming a date is asserting something the plan cannot know. | Carmack |
| 15 | **No operator action repairs a dead night. An instrument change is a person's decision, and it is already one** - the model entry, the temperature, the prompt and the grammar all reach a runner through a reviewed commit, and rows #8 and #11 both carry a sign-off trigger. The person approves the instrument at the commit, not at 22:00 on a runner. | Andre |
| 16 | The plan is computed per judge against that judge's own record, so a judge added later inherits the repair with no change here. | Fowler |
| 17 | **This does not depend on anything noticing.** There is no alarm to read: the next run finds the gap because finding the gap is how it chooses its work. | Owner, 2026-09-20 |
| 18 | The house pattern is "the next run finishes the dead run's work". **The mechanism is new** - the digest run's catch-up drains whatever is waiting and takes no date at all, so there is no code to copy, only the principle. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | An alarm reporting a night with no evidence, and a person re-dispatches | Manual effort with a notification in front of it, and it fails exactly when it is needed - a run that dies quietly is one nobody is watching for | A repair that happens only when somebody is looking | Owner |
| 2 | Accept the loss because the first fitted line is far away | **Builds for today's data rather than for the pipeline being built.** More judges are coming and the line will be wired to a published day | A record with gaps nobody can account for later | Owner |
| 3 | Re-judge without extending the pair key | The re-judged rows collide with the partial run's on a key that cannot tell two council runs apart, and the de-duplication keeps the row already on disk - so the fresh verdicts are discarded while the record counts them | Four shards of model time discarded on write, and a record that cannot be re-derived from the tree it summarises | Andre |
| 4 | Record both readings and let the counting step split the window at a fingerprint change | Splitting needs a per-date stamp the record does not have and a fit that can weight two populations | Two features to build before the first repair works | Andre |
| 5 | Have the council re-trigger itself through the platform API | The default credential cannot start a new run, so it needs a stored personal token | A credential to manage, for a repair the next scheduled run already does | Carmack |

---

### Row #22 - The guard that stops a shard committing is renamed and re-reasoned

- **Scope:** the guard keeps its assertion, loses a name carrying a deleted word, loses a dead reason, and learns to see a commit issued from a composite action.
- **Files touched:** `backend/tests/workflows/test_llm_council_workflow.py`, `.github/workflows/llm-council.yml`, `docs/architecture/publishing/llm-council.md`
- **Acceptance gates:** local - the workflow harness, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the guard still refuses a judging job that commits, **and it detects one issued from a composite action** rather than only from an inline script. It cannot settle whether the new reason is the best one.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | **The test's own name carries the word this plan deletes**, so it is renamed here with every other occurrence. A vocabulary scrub that leaves the word in a test name has not been done. | Owner, 2026-09-20 |
| 2 | The assertion stays. The reason goes: it says four shards would push into one union-merged file, and union merging left the judged-pairs store on 2026-09-19. Quoting it today quotes a dead fact and invites a reader to retire the guard with it. | Fowler |
| 3 | The reason that replaces it cannot be retired by a config edit: **the job that counts the shards is pinned to the commit the run started at, so rows a shard commits during the run are invisible to it.** | Fowler |
| 4 | The same dead premise is repeated in the workflow's own comment and is corrected in the same pass. | Carmack |
| 5 | **The guard is a substring search over the job's inline scripts, so it sees nothing issued from a composite action** - and the composite-action row moves the model block into exactly such an action. It is widened here rather than discovered later. | Carmack |
| 6 | The council page asserts the upload choice and has never priced it. It gains a `## Design rationale` naming the pinned checkout, the conflict segments solve, and the trigger that would change the answer. | Guardrail #4 |
