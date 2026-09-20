# Name the judges, and give them an instrument

**Last Updated**: 2026-09-20

**Level**: 5 (two persisted contracts with committed rows, a committed state tree that moves, and a new meaning for a `run_id` cell)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 3 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Four CLI verbs name their mechanism rather than their work, a second judge lands soon that shares one of their four steps, and the judging legs record nothing about the machine they ran on while the store that would ship it already exists. |
| Hard scope - in | Make a leg survive its own clock; give the council a run identity of its own; rename the four same-story verbs and their modules; replace the derived per-call cost with the measured one; move and rename the leg-timeout knob; assert thinking off and stamp the decode off the posted body; declare the judge-call stamp, the judge-leg row and the line-against-holdout row; open `ServerJob`, `SegmentLedger`, `RollupSpan` and `AttrKey` to judges; wire the host fingerprint, the job clock, spans and the segment compaction into the council and stage what they write; group the committed store under the judge slug; lift the model block into one composite action; update the plan pointers. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | (1) Row #2 changes what a committed `run_id` cell means across four contracts - pause for sign-off. (2) Row #7 widens a header on a store with committed rows and refiles them - pause for sign-off on the refile before it runs. (3) Row #17 moves a committed state tree - pause for sign-off on the path map before any file moves. (4) Any row that would raise a runner budget figure (Guardrail #2). (5) Row #18: if the holdout resolves fewer pairs than its stated floor, write the cells null and refuse the reading. (6) Row #9 renames a config knob AND the workflow key that reads it - if the two cannot land in one commit, stop. |
| Chosen strategy | Share the model call, not the judge - one constrained-decode layer and a per-reading stamp each judge embeds in its own row, with per-judge packages, contracts and stores above it. Fowler, Carmack and Andre in debate, owner ruling 2026-09-20; corrected by adversarial review 2026-09-20 (see section 1b). |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3.` Three because the file islands never widen past three once groups C, E and G are sequenced (section 0, grouping note). |

### How the rows group into pull requests

**A `Parallel-group` letter is one pull request, not one row.** Rows sharing a letter are written together, gated once and merged once.

| Group | Pull request | Rows | Why these ship together |
| --- | --- | --- | --- |
| A | A leg survives its own clock, and the council knows which run it is | 1, 2 | Both are prerequisites nothing else can be written without, and both touch the council workflow |
| B | Every persisted shape this plan needs | 3, 4, 5, 6, 7, 8 | All six regenerate `schemas/`, four touch `backend/idhazh/ledger.py`, and all six register through one `CONTRACTS` tuple; split, they are six conflicting drift-gate regenerations |
| C | What a call costs, and where its bound lives | 9, 10 | Both touch `backend/idhazh/contracts/knobs/`, `config/idhazh.json` and the generated app-config schema |
| D | The model boundary asserts what it assumed | 11 | `backend/idhazh/llm/` and `backend/idhazh/similarity/`, no persisted shape |
| E | The verbs name their work | 12 | Atomic by nature: a verb renamed in `cli.py` and not in the workflow is a run that dies mid-pipeline |
| F | The legs write what they did | 13, 14 | Both are the judging stage filling shapes group B declared |
| G | The council records the machine it ran on | 15, 16 | Both are one pass over `.github/workflows/llm-council.yml` |
| H | The store groups under the judge that fills it | 17 | A tree move, gated on its own |
| I | Where the line stands against its holdout | 18 | Reads the moved tree, so it follows H |
| J | The plan pointers | 19 | Docs only |

**`.github/workflows/llm-council.yml` is the chokepoint and is sequenced rather than hoped about.** It is touched by groups A, C, E, G and H. The Reckoner's `Depends-on` column chains them: C after A, E after C, G after E, H after G. Under N = 3 the three live slots are spent on B, D and whichever of the workflow chain is current.

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| A `Judge` base class, protocol or registry | The second judge duplicates the stage shape, about 150 lines | A third judge sharing three of the four steps, rather than one |
| A second CLI level (`idhazh <loop> <verb>`) | The flat verb list grows from 25 to about 31 | The first time a flag's help text has to name which judge it belongs to |
| One workflow per judge | Every judge shares one cron, one concurrency group and one runner label | A judge needing different weights or a different cadence |
| The independent second-opinion judge itself | The holdout stays labelled by something outside the loop, which is correct today but unmaintained | The six questions in `20260920-a-second-judge-in-the-council-handover.md` being answered |
| A real judge-against-holdout measurement | Nothing measures whether the JUDGE agrees with the labels - only whether the LINE does (row #18) | A budget: 200 pairs at the measured 94.53 s a pair is 5.25 h on one job, so it shards or it does not ship |
| The summary-quality judge's own stages | Plan 36 owns them; this plan only declares the shapes it would reuse | Plan 36 reaching its G-Eval row |
| Promoting fluency to a publish gate | Nothing today - it is a drift monitor and feeds nothing | A measured injection delta on the score |
| New console panels | `/console/judgement/` already renders the holdout against the applied line | An operator asking for a panel the committed rows cannot answer |
| Renaming `backend/var/judge/` | The scratch directory keeps a word naming one loop's draw | The parallel work already moving production artefacts out of the code tree |
| A judge role in `ModelRole` | Every judge keeps inheriting the summariser's weights, so no judge can be independent | The second-opinion judge, the first that needs different weights |
| Converting `measure.yml` and `validate.yml` to the composite action | Four cache blocks stay hand-written; they share one of the action's five steps, so the drift risk is small | A second judge in either file |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A leg survives its own clock | - | A | PENDING | - | - | - |
| 2 | The council knows which run it is | - | A | PENDING | - | - | - |
| 3 | The judge-call stamp, declared once | 2 | B | PENDING | - | - | - |
| 4 | `ServerJob` and `SegmentLedger` admit judges | 2 | B | PENDING | - | - | - |
| 5 | A judge call is a committed span | 4 | B | PENDING | - | - | - |
| 6 | The judge-leg row, and what prunes it | 3, 4 | B | PENDING | - | - | - |
| 7 | The pair row gains the stamp, and the store is refiled | 3 | B | PENDING | - | - | - |
| 8 | The line-against-holdout row | 4 | B | PENDING | - | - | - |
| 9 | The leg timeout moves to the block that validates it | 1 | C | PENDING | - | - | - |
| 10 | The measured judge pair replaces the derived call | 1 | C | PENDING | - | - | - |
| 11 | Thinking is refused and the decode is stamped | 3 | D | PENDING | - | - | - |
| 12 | The four verbs name their work | 4, 9 | E | PENDING | - | - | - |
| 13 | The leg fills the stamp | 7, 11, 12 | F | PENDING | - | - | - |
| 14 | The leg writes its row and opens its spans | 5, 6, 13 | F | PENDING | - | - | - |
| 15 | The council records the machine it ran on | 14 | G | PENDING | - | - | - |
| 16 | The model block becomes one composite action | 15 | G | PENDING | - | - | - |
| 17 | The store groups under the judge that fills it | 15 | H | PENDING | - | - | - |
| 18 | Where the line stands against its holdout | 8, 17 | I | PENDING | - | - | - |
| 19 | The plan pointers | 18 | J | PENDING | - | - | - |

## Section 1b - What the adversarial review changed

Recorded because each correction is a claim an executing worker would otherwise re-derive, and four of them were wrong in the first draft in ways that would have destroyed committed data or shipped a green test over a live defect.

| # | The first draft said | The code says | What changed |
| --- | --- | --- | --- |
| 1 | `if: always()` on the verdict upload fixes the cancelled leg | The leg builds a list and calls `write_atomic` once after the loop, so a cancelled leg has written **nothing** and the upload has no file to take | Row #1 is now a stage change - a deadline, an incremental flush and a header-first write - and the workflow condition is the last line of it, not the whole of it |
| 2 | `class JudgeLegRow(JudgeCallStamp, CsvContract)` | `CsvContract` is a `typing.Protocol` in `ledger.py`, not a base class. Mixing it with a pydantic model is a metaclass conflict, and importing `ledger` into `contracts/` is a circular import that breaks section 4 | Every new row subclasses `Contract` and satisfies the protocol structurally, as all fifteen existing CSV contracts do |
| 3 | The pair row inherits the stamp mixin | Pydantic collects base fields first, so the header **reorders**; `_append` compares headers for equality and raises. The store becomes unappendable and a re-dispatch of that date dies | The pair row declares the new columns in its own body, at the tail, and the one committed file is refiled in the same commit |
| 4 | `from_csv_row` fills absent keys from model defaults | It maps an absent cell to `""`, and converts to `None` only when `field.default is None`. A Literal refuses `""`, and the loader stops the read rather than skipping | The migration is named as new code with its own oracle |
| 5 | The council reuses a run id | The council has **no run id at all**; the pair rows carry the *digest* run's id, and `SPAN_ROLLUP_KEY` has no `job` column - so a judge leg writing spans under that id would overwrite the digest run's committed rows | Row #2 mints a council run id before anything writes a row |
| 6 | Spans come from the existing closed set | `RollupSpan` has five members and no `model_call`; the rollup silently skips anything else, so the spans would commit nothing | Row #5 adds the member as a stamped contract change, in group B |
| 7 | The fingerprint is taken before the first model call | The bandwidth probe wants two buffers of at least 512 MiB and the server peaks at 14.31 GiB of a 16 GB runner. A step after `Start the model` satisfies that wording and OOMs the leg | The order is asserted against `Start the model` by name |
| 8 | `reached_bound` records a leg that ran out of clock | The stage reads no clock; the only bound is the platform's, which kills the process before it can write | Row #1 gives the stage its own deadline, so the column is reachable |
| 9 | Row #14 scores the judge against the holdout | The holdout rows carry no verdict, the shipped implementation takes weights and a line and calls no model, and the labels were written by an outside model | Row #18 scores the **line**, carries no judge stamp, and names its labeller |
| 10 | `first_token_probabilities` lets a scoring fix be re-applied from the row | `n_probs` is 3, and the grammar admits prefix tokens, so the window can hold `{" ", "YES", "Y"}` with two verdicts outside it | Row #11 sizes the window to the legal first-token set and sends `post_sampling_probs` explicitly; the claim is narrowed to what the window holds |
| 11 | `decode_digest` records the sampler | Temperature, top-p, seed and the thinking flag are all constants on every row that can exist, and deriving it from `settings` cannot see a payload-builder bug | The digest is taken from the body actually posted, and `judge_temperature` is carried as a plain number beside it |

## Section 1c - The contracts, settled before any row is written

Guardrail #3. Types are the aliases in `backend/idhazh/contracts/base.py`. **Every new contract is registered in the `CONTRACTS` tuple in `backend/idhazh/contracts/export.py`** - that tuple is what writes `schemas/` and `frontend/src/contracts/`, and the drift gate derives both sides from it, so an unregistered contract fails with a message about an orphan file rather than about a missing registration.

### New type aliases (`backend/idhazh/contracts/judge_call.py`)

| Name | Definition |
| --- | --- |
| `JudgeId` | `Literal["content-similarity-judge", "summary-content-quality-judge"]` |

A Literal for the reason `ScorerModelId` is one: a fold over a store mixing two instruments sums readings that mean different things. **A judge's identity is a property of its stage, not a tunable** - the stage names its own `JudgeId` as a module constant and it never reaches `config/` (Guardrail #6 does not bind: there is nothing here an operator should change).

### `JudgeCallStamp` - a mixin for NEW rows only

`class JudgeCallStamp(Model)` in `backend/idhazh/contracts/judge_call.py`. No `__schema_stem__`, writes no file. **`StorySimilarityPair` does not inherit it** (section 1b row 3).

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `judge_id` | `JudgeId` | default `"content-similarity-judge"` | Which instrument wrote this reading |
| `judge_model` | `JudgeModelId \| None` | default `None` | Which weights judged |
| `judge_temperature` | `float \| None` | `ge=0`, default `None` | The sampler temperature, as a number. An operator reading a row needs the value, not a hash of it |
| `decode_digest` | `Sha256 \| None` | default `None` | sha256 of the canonical JSON of the sampler keys **of the body actually posted**. Taken from the payload rather than from config, because a digest built off config cannot see a bug in the payload builder - which is the one failure a digest exists to catch |
| `prompt_digest` | `Sha256 \| None` | default `None` | sha256 of the rendered system turn |
| `grammar_digest` | `Sha256 \| None` | default `None` | sha256 of the grammar handed to the decoder |
| `grammar_applied` | `bool \| None` | default `None` | Whether the reply opened inside the grammar |
| `first_token_probabilities` | `str \| None` | `PRINTABLE_LINE_PATTERN`, `max_length=512`, default `None` | Compact JSON, a list of `[token_id, token, logprob]` in the server's own order. Ids because a token string is right for one set of weights and says nothing when the weights move; logprobs because exponentiating loses the precision the margin is computed at |
| `decode_seconds` | `float \| None` | `ge=0`, default `None` | Wall clock for **one call**. Exactly one call, on every row that inherits this |

**`usable`, `verdict`, `verdict_swapped` and `first_token_margin` stay off the mixin.** Agreement between two readings is a position-bias control with no honest meaning for a judge whose input has no order.

**`first_token_probabilities` is the first model-written free text this loop commits.** It is safe where it lands - a quoted CSV value, never a key, never a name - and it stays there. No path, filename or URL is ever keyed on a token (Guardrail #11).

### `StorySimilarityPair` - four columns appended at the tail

`backend/idhazh/contracts/story_similarity_pair.py`. Declaration is unchanged - it does **not** inherit the mixin. Four fields are appended after `decode_seconds`, so the header widens and does not reorder.

| Field | Type | Constraint |
| --- | --- | --- |
| `judge_id` | `JudgeId` | default `"content-similarity-judge"` |
| `judge_temperature` | `float \| None` | `ge=0`, default `None` |
| `decode_digest` | `Sha256 \| None` | default `None` |
| `grammar_applied` | `bool \| None` | default `None` |
| `first_token_probabilities` | `str \| None` | `PRINTABLE_LINE_PATTERN`, `max_length=512`, default `None` |

`decode_seconds` keeps its existing meaning on this row - **both calls on the pair** - and its description says so, because the mixin's field of the same name means one call and the two must not be confused.

Changelog entry to prepend:

| version | change | why |
| --- | --- | --- |
| `2026-09-20` | Added the judge-call stamp columns: which judge, its temperature and decode digest, whether the grammar applied, and the first-token vector. | A verdict could not be read back to the sampler that produced it. |

**Two migrations, both in the same commit.**

1. **Read side.** `from_csv_row` gains a branch that drops an empty cell for any field whose default is not `None`, so the field default applies instead of `""` reaching a Literal.
2. **Write side.** `refiler(StorySimilarityPair)` is run over `state/story-similarity/scored-pairs/**/*.csv`, widening the header in place. This adds empty cells and changes no value any run wrote, so the "do not edit the archive" objection does not apply. Without it `_append` refuses the file and a re-dispatch of that date kills the commit step and every ledger staged beside it.

### `JudgeLegRow` - new (`backend/idhazh/contracts/judge_leg_row.py`)

`class JudgeLegRow(JudgeCallStamp, Contract)`. `__schema_stem__ = "judge-leg-row"`. Supplies its own `csv_columns` / `csv_row` / `from_csv_row`, copied from `StorySimilarityPair`. Key: `("date", "run_id", "job", "shard")` - identical to `HOST_FINGERPRINT_KEY`, and **without `judge_id`**, because one `SegmentLedger` member per judge means every row in this head carries the same value and a constant cell settles nothing.

**`attempt` is deliberately not a column.** It is in the segment filename and in no column, as `SegmentName` documents.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | The digest date this leg judged |
| `run_id` | `RunId` | - | **The council run that dispatched this leg** - not the digest run that published the day |
| `job` | `ServerJob` | - | Which workflow job produced the row |
| `shard` | `int` | `ge=0` | Which leg |
| `rows_owned` | `int` | `ge=0` | Rows the draw dealt this leg |
| `rows_judged` | `int` | `ge=0` | Rows that got a reading inside the grammar |
| `rows_usable` | `int` | `ge=0` | Rows whose two readings agreed |
| `rows_unreadable` | `int` | `ge=0` | Drawn rows whose items the window no longer reaches. The stage already counts this and throws it into a log line |
| `grammar_failures` | `int` | `ge=0` | Readings that came back outside the grammar. Disjoint from `rows_judged` |
| `disagreement_rate` | `float \| None` | `ge=0, le=1` | Share of judged rows whose two readings differed. Null on an empty leg - a rate over zero rows is not zero. **Per leg over judged rows**, where the fit's gate is per day over usable rows; the two are different quantities and the description says so |
| `unclear_rate` | `float \| None` | `ge=0, le=1` | Share of usable rows answered UNCLEAR. Null on an empty leg, same reason, same per-leg caveat |
| `first_token_margin_median` | `float \| None` | `ge=0, le=1` | Median gap at the deciding position |
| `server_start_seconds` | `float \| None` | `ge=0` | Weights load to first healthy probe |
| `decode_seconds_total` | `float \| None` | `ge=0` | Sum over the leg's calls |
| `decode_seconds_max` | `float \| None` | `ge=0` | The leg's longest single call. A leg with an ordinary total and a bad worst call is the one that times out next week |
| `reached_bound` | `bool` | default `False` | Whether the leg stopped on its own deadline rather than on running out of rows. Reachable only because row #1 gives the stage a deadline |

**The identity that closes:** `rows_owned = rows_judged + grammar_failures + rows_unreadable`. This is row #14's oracle, and every term is a column.

The inherited `decode_seconds` is this leg's **first** call, kept so the mixin's meaning is honoured on every row that carries it.

### `LineHoldoutScoreRow` - new (`backend/idhazh/contracts/line_holdout_score_row.py`)

`class LineHoldoutScoreRow(Contract)`. `__schema_stem__ = "line-holdout-score-row"`. Key: `("date", "run_id")`.

**It does not inherit `JudgeCallStamp`.** No judge reads anything here: the holdout rows carry no verdict column, the scoring applies a threshold to a recomputed similarity, and the labels were written by an outside model. Eight judge-call columns on this row would be five nulls and a `judge_id` asserting an instrument that never ran.

**Counts only. No precision, recall or accuracy column.** A stored rate is a rate somebody reads without its denominator, and this denominator is four.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | When the line was scored |
| `run_id` | `RunId` | - | The run that scored it |
| `applied_line` | `float` | `ge=0, le=1` | The merge line in force when the four cells were counted |
| `labeller` | `str` | `PRINTABLE_LINE_PATTERN`, `max_length=64` | Who marked the holdout. Not a `JudgeModelId`: the committed labels name an outside model, and a column that could only hold pipeline models would refuse the truth |
| `merged_and_one_story` | `int` | `ge=0` | The line joined them and the label agrees |
| `merged_and_two_stories` | `int` | `ge=0` | The line joined two stories that are not one. The reader never sees the second - the invisible direction |
| `apart_and_one_story` | `int` | `ge=0` | The line left one story in two pieces. The reader sees it twice and can dismiss it |
| `apart_and_two_stories` | `int` | `ge=0` | The line left them apart and the label agrees |
| `pairs_unresolved` | `int` | `ge=0` | Labelled pairs whose two days retention has deleted. Reported, never dropped |
| `labelled_two_story_pairs` | `int` | `ge=0` | The negative population the false-merge cell is drawn from. On the row so no rate is read without it |
| `scorer_model` | `ScorerModelId` | - | Which encoder produced the cosines |
| `cosine_weight` | `float` | `ge=0, le=1` | What the cosine was worth |
| `key_point_weight` | `float` | `ge=0, le=1` | What the key-point term was worth |

**The read is bounded by the holdout, not by the archive** (Guardrail #12). Each holdout row carries `left_date` and `right_date`, so the days opened are named by the file and its length is the bound. The unbounded walk in `sample_sheet.index` exists only because that tool resolves against the draw's date instead; this row must not copy it.

### `ServerJob` - three members added (`backend/idhazh/contracts/base.py`)

| Member | Value | Workflow job today | Becomes |
| --- | --- | --- | --- |
| `PICK` | `"pick"` | `draw` | `pick` |
| `JUDGE` | `"judge"` | `judge` | `judge`, unchanged |
| `TALLY` | `"tally"` | `fold` | `tally` |

Additive; no manifest migrates. **Between group B and group E merging, `PICK` and `TALLY` name jobs that do not exist yet.** That is stated rather than hidden, and no test asserts the correspondence in that window.

### `SegmentLedger` - one member per judge (`backend/idhazh/ledger.py`)

| Member | Value | Transit | Head |
| --- | --- | --- | --- |
| `CONTENT_SIMILARITY_JUDGE` | `"content-similarity-judge"` | `state/segments/content-similarity-judge/` | `state/content-similarity-judge/shards/<YYYY>/<MM>/<DD>.csv` |

The value is the judge slug and the head shape appends the fixed `shards` segment, which restates the transit-equals-head invariant for a two-level head rather than breaking it. **One member per judge, not one shared `"shards"` member:** a segment filename carries the run, the attempt, the job and the shard and no judge, so two judges would collide and one would silently overwrite the other.

`_SEGMENT_HEADS` gains the entry; `keyed_paths` gains the head so it is registered for settlement, which is the half the span-rollup defect was missed on.

### `RollupSpan` - one member added (`backend/idhazh/contracts/span_rollup.py`)

| Member | Value |
| --- | --- |
| `JUDGE_CALL` | `"judge_call"` |

`RollupSpan` has five members and the rollup silently skips any span not in it, so without this row #14's spans commit nothing. This is a persisted contract: the schema is stamped and a changelog line appended. `ITEM` is not reused - the fold raises on overlapping item spans and a judge call would be indistinguishable from an article in the record.

### `AttrKey` - the members a judge span carries (`backend/idhazh/telemetry/spans.py`)

| Member | Value | Why it is safe |
| --- | --- | --- |
| `JUDGE_ID` | `"judge.id"` | A Literal this repository writes |
| `PAIR_KEY` | `"judge.pair_key"` | sha256 |
| `SHARD` | `"judge.shard"` | An integer |

Ids and digests only. A title or a URL never becomes a span attribute.

### Config knob - moved and renamed

| Today | Becomes |
| --- | --- |
| `run.judge_shard_timeout_minutes` | `assemble.same_story.adaptive_dedup_threshold.leg_timeout_minutes` |

Committed value `200`, `ge=1`, `le=350`, unchanged. It moves beside `pair_budget` and `shards`, the two numbers its validator already reads. `backend/utilities/shard_bound.py` resolves `run["<key>"]` only, so it gains a dotted-path `--key` and keeps one reader and one refusal message. `run.shard_timeout_minutes` does not move.

### Store paths (`backend/idhazh/ledger.py`)

| Constant | Value |
| --- | --- |
| `CONTENT_SIMILARITY_JUDGE_DIRNAME` | `"content-similarity-judge"` |
| `JUDGE_SHARDS_DIRNAME` | `"shards"` |
| `LINE_HOLDOUT_SCORES_DIRNAME` | `"line-holdout-scores"` |

Day-sharded, `<slug>/<store>/<YYYY>/<MM>/<DD>.csv`. **Two directory levels and no more:** the day inventory globs `*/<Y>/<M>/<D>` and `*/*/<Y>/<M>/<D>`, so a third level is invisible to `idhazh telemetry show` and the miss is silent.

Both stores join `TARGETS` in `backend/idhazh/telemetry/prune.py` (CLAUDE.md 1b: a prune verb per store) and `STORES_NOTHING_FILLS_YET` in `backend/tests/workflows/test_ledger_staging.py` until their writers land in rows #14 and #18.

---

### Row #1 - A leg survives its own clock

- **Scope:** the judging leg takes its own deadline, writes its verdict file from the first pair onward, and the workflow uploads whatever exists - so a leg that runs out of clock keeps the verdicts it paid for.
- **Files touched:**
  - `backend/idhazh/stages/judge_shard.py`
  - `backend/idhazh/contracts/knobs/run.py`
  - `config/idhazh.json`
  - `.github/workflows/llm-council.yml`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `schemas/app-config.schema.json` (generated)
- **Acceptance gates:** local - the similarity test module, the workflow harness, contract export, drift gate. CI - full suite.
- **Oracle:** `stage_judge_shard` driven against a fixture draw with a client that raises after k pairs leaves a file on disk holding exactly k rows. It cannot settle what GitHub does on a real cancellation - the stage's own deadline is what makes that case unreachable, and the workflow condition is the backstop.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `if: always()` alone does not fix this. The leg builds a list and calls `write_atomic` once after the loop, so a cancelled leg has written nothing and the upload takes an absent path. | Andre |
| 2 | The stage takes a deadline derived from the leg bound minus a wrap-up margin, stops on it, writes what it has and exits clean. The pattern is `run.shard_wrap_up_minutes`, which already exists for the work shard. | Andre |
| 3 | A header-only file is written before the first pair, so the artifact always exists and `if-no-files-found: error` becomes a meaningful assertion rather than a permanent failure. | Andre |
| 4 | The file is rewritten whole through `write_atomic` every flush, not appended. A temp-file-plus-rename has no partial state, which is the property that makes an interrupted leg's file readable. | Fowler |
| 5 | The flush interval is a knob with a sane default, because a flush per pair costs a rewrite per pair and a flush per leg is what this row is fixing. | Guardrail #6 |
| 6 | This makes `JudgeLegRow.reached_bound` reachable. Without a deadline in the stage, the leg that hit the bound is exactly the leg that cannot write a row saying so. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | `if: always()` on the upload and nothing else | The oracle goes green while a cancelled leg still loses every verdict, and the row closes over a live defect | One line, and the next overrun costs the same hours it costs today | Andre |
| 2 | Raise the leg timeout | A bound is a backstop, not a budget; an overrunning leg still loses its work | One knob edit, and the defect survives | Carmack |
| 3 | Append to an open file handle | An interrupted append leaves a half-written row that the contract reader stops on | A faster flush and an unreadable tail | Fowler |

---

### Row #2 - The council knows which run it is

- **Scope:** the council mints a run identity of its own and hands it to every verb that writes a row, so a judge leg's rows are filed under the run that judged rather than the run that published.
- **Files touched:**
  - `backend/idhazh/cli.py`
  - `backend/idhazh/telemetry/silicon.py`
  - `backend/idhazh/stages/common.py`
  - `.github/workflows/llm-council.yml`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `backend/tests/`
- **Acceptance gates:** local - the telemetry and workflow test modules, ruff, mypy. CI - full suite.
- **Oracle:** the fingerprint and job-clock verbs produce a row from a run id passed on the command line, with no plan file on disk. It cannot settle whether the id the council passes is unique across re-runs - GitHub's run id is stable across attempts, which is why the segment filename carries the attempt separately.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The council has no run id today - the string does not appear in its workflow file. The fingerprint and job-clock verbs read one from `backend/var/run/<date>/plan.json`, which only exists because the digest work job downloads a plan artifact. The council has no plan job. | Carmack |
| 2 | The two verbs take a run id directly rather than a plan object, so a workflow with no planning stage can still record a machine. | Carmack |
| 3 | The council's run id is the judged date joined to the platform run number, which satisfies the `RunId` pattern. | Carmack |
| 4 | ESCALATE: `run_id` on a pair row means the run that published the day; on a leg row it means the council run that judged it. Two columns, two meanings, both written down. Sign-off before the code. | Section 6 |
| 5 | Without this row, reusing the digest run's id would collide on `SPAN_ROLLUP_KEY`, which carries no `job` column - and the compaction settles by attempt, so the council's segment would delete the digest run's committed span rows for that date. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Reuse the digest run's id | Silently deletes committed span-rollup rows for that date, and claims a machine for a run that never drew it | Nothing to write, and a corrupted instrument nobody would see | Carmack |
| 2 | Give the council a plan job so the existing verb works | A plan job that plans nothing, to produce one string | One job, one artifact, and a stage that exists to satisfy a signature | Fowler |
| 3 | Add `job` to `SPAN_ROLLUP_KEY` instead | Changes a persisted key on a store with committed rows, to avoid minting a string | A key migration and a re-settlement of every committed month | Fowler |

---

### Row #3 - The judge-call stamp, declared once

- **Scope:** the nine columns every judge reading carries, declared as a mixin for the new rows, with `JudgeId` beside them.
- **Files touched:**
  - `backend/idhazh/contracts/judge_call.py` (new)
  - `backend/idhazh/contracts/export.py`
  - `backend/tests/contracts/test_judge_call.py` (new)
- **Acceptance gates:** local - the new contract test, contract export, drift gate, ruff, mypy. CI - full suite.
- **Oracle:** a `Contract` subclass inheriting the mixin round-trips every field through `csv_row` and `from_csv_row`, and the mixin declares no schema stem so nothing generates a file for it. It cannot settle whether the nine are the right nine - section 1c names why each is there.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A mixin over `Model`, inherited alongside `Contract`. Never alongside `CsvContract`, which is a Protocol in `ledger.py` - the combination is a metaclass conflict and the import is circular. | Fowler |
| 2 | `StorySimilarityPair` does not inherit it. Pydantic collects base fields first, so inheriting would reorder the committed header and make the store unappendable. | Fowler |
| 3 | `decode_seconds` on the mixin is one call and nothing else. The pair row's column of the same name is both calls, and its description says so. | Andre |
| 4 | The probability vector is a list of id, token and logprob triples, not a token-keyed map. Two ids rendering to one string would collide as duplicate keys, and exponentiating a logprob throws away the precision the margin is computed at. | Andre |
| 5 | `judge_temperature` is carried as a number beside the digest, because an operator reading a row needs the value. | Andre |
| 6 | Every new contract is registered in the `CONTRACTS` tuple, or no schema is generated and the drift gate reports an orphan file instead of a missing registration. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One union verdict row across all judges | Half the columns null per judge, and `usable` has no honest meaning for a rated scorer | A discriminator column and a contract asserting two instruments are one | Fowler |
| 2 | A `Judge` base class with behaviour | A shared `usable` would drop every ambivalent fluency reading and bias the fitted floor with nothing red | The cheapest code, and a silently biased sample | Andre |
| 3 | A separate judge-health table | A join key and a second write; a run dying between the two leaves a reading with no stamp | A second store and a join every reader pays | Andre |

---

### Row #4 - `ServerJob` and `SegmentLedger` admit judges

- **Scope:** the closed set of jobs that may appear in a segment filename gains the council's jobs, and the closed set of heads that accept segments gains the content-similarity judge, registered for settlement.
- **Files touched:**
  - `backend/idhazh/contracts/base.py`
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/telemetry/prune.py`
  - `backend/tests/contracts/`
  - `backend/tests/workflows/test_ledger_staging.py`
  - `backend/tests/retention/test_prune_range.py`
  - `docs/architecture/publishing/retention.md`
  - `schemas/` (every generated schema listing `ServerJob`)
- **Acceptance gates:** local - the contract, staging and retention test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** every `SegmentLedger` member resolves to a `_SEGMENT_HEADS` entry and to a `keyed_paths` entry, so a ledger cannot be staged without being registered for settlement. It cannot settle whether a job writes a segment - row #14 does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One `SegmentLedger` member per judge, valued at the judge slug. A shared member would let two judges collide on one segment filename. | Fowler |
| 2 | The head key is `("date", "run_id", "job", "shard")` and carries no `judge_id`. One head per judge means the column is constant, and a constant cell settles nothing - worse, it would claim two judges could share this head. | Fowler |
| 3 | The head joins `keyed_paths` in the same row as `_SEGMENT_HEADS`. Registering one without the other is the exact defect the settlement test's docstring records. | Fowler |
| 4 | Both new stores join the prune targets in this row. A day-sharded store with no prune verb is a store that grows for ever (CLAUDE.md 1b). | Fowler |
| 5 | The two stores are listed as filled-by-nothing until rows #14 and #18 land, so the staging test is green between group B and group F. | Fowler |
| 6 | Reader before writer: this row adds the members and leaves every writer alone. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A free-text job column | The closed set exists to stop a typo becoming a job nobody can group by | A column that splits silently | Fowler |
| 2 | Add `judge_id` to the segment filename grammar | The grammar is shared by six ledgers with no judge; widening it for one is a cost every ledger pays | A regex change, a rename of every existing segment, a compaction migration | Fowler |
| 3 | Skip the prune targets and add them later | A store that ships without a prune verb is one nobody remembers to bound | Two lines now, unbounded growth otherwise | Fowler |

---

### Row #5 - A judge call is a committed span

- **Scope:** the rollup's closed set of committed spans gains a judge call, so a leg's per-call timing survives the fold instead of being silently dropped.
- **Files touched:**
  - `backend/idhazh/contracts/span_rollup.py`
  - `backend/idhazh/telemetry/spans.py`
  - `backend/idhazh/telemetry/rollup.py`
  - `schemas/span-rollup-row.schema.json` (generated)
  - `backend/tests/`
- **Acceptance gates:** local - the telemetry and contract test modules, contract export, drift gate. CI - full suite.
- **Oracle:** a span tree carrying the new member folds to a committed row, and the import-time assertion that every rollup member maps into the tracer's own name set still holds. It cannot settle whether the timing is accurate.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `RollupSpan` has five members and no model call; the rollup skips anything outside the set, so a leg opening judge spans today commits zero rows. | Carmack |
| 2 | A new member, not a reuse of the item span. The fold raises on overlapping item spans, and a judge call would be indistinguishable from an article in the committed record. | Carmack |
| 3 | This is a persisted contract: the schema is stamped and a changelog line appended in this row, which is why it sits in group B and not with the writer in group F. | Section 11 |
| 4 | The span attribute keys are declared here too, and carry ids and digests only. A span attribute reaches a committed store, so Guardrail #3 binds and Guardrail #11 binds. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Reuse the item span | The fold raises on overlap, and the record could not tell a judge call from an article | Nothing to declare, and a corrupted rollup | Carmack |
| 2 | Drop spans and put per-call timing on the leg row only | The leg row's totals cannot separate a slow server start from slow decoding | One less contract change, and the question a slow leg raises stays unanswerable | Carmack |
| 3 | Keep the span uncommitted, as the existing model-call span is | A span nobody commits answers nothing after the runner is gone | Nothing, and no record at all | Carmack |

---

### Row #6 - The judge-leg row, and what prunes it

- **Scope:** one row per judge per leg, its ledger path, its segment head and its prune target.
- **Files touched:**
  - `backend/idhazh/contracts/judge_leg_row.py` (new)
  - `backend/idhazh/contracts/export.py`
  - `backend/idhazh/ledger.py`
  - `schemas/judge-leg-row.schema.json` (generated)
  - `frontend/src/contracts/` (generated)
  - `docs/architecture/contracts/schemas.md`
  - `backend/tests/contracts/`
- **Acceptance gates:** local - the contract tests, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the row round-trips through CSV, and `rows_owned = rows_judged + grammar_failures + rows_unreadable` is enforced by a model validator, so a leg cannot file a funnel that does not close. It cannot settle whether the figures are true; row #14's oracle does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge slug is the group and each judge owns as many day-sharded stores as it has questions - the shape `story-similarity` already uses. | Owner, 2026-09-20 |
| 2 | No `judges/` prefix. The inventory globs two directory levels and reports success while listing nothing deeper. | Fowler |
| 3 | `rows_unreadable` is a column because the stage already counts it and throws it into a log line, and without it the funnel identity does not close. | Andre |
| 4 | `grammar_failures` is disjoint from `rows_judged`. A reading outside the grammar has no verdict, so counting it as judged would make the disagreement rate a share of a population it is not drawn from. | Andre |
| 5 | The leg row carries both the leg's total and its worst single call, because a leg with an ordinary total and a bad worst call is the one that times out next. | Carmack |
| 6 | The leg row is a record and the fit's held reason is the alarm. The two rates on this row are per-leg over judged rows; the fit's gates are per-day over usable rows. The descriptions say so, so a reader comparing them does not see a contradiction that is not one. | Andre |
| 7 | The schema register gains a row for this shape. | Section 11 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Put the leg figures on the existing work-shard machine row | That row is one work shard of one digest run, and a judge leg is neither | A discriminator column on a row describing two unrelated jobs | Carmack |
| 2 | Derive the funnel at read time from the verdict rows | A leg that wrote no verdicts becomes indistinguishable from a leg that never ran | Nothing to store, and the one failure the row exists to show | Andre |
| 3 | Give the leg row its own alarm thresholds | Two alarms on one question, and the fit's held reason already fires on the day-grain rates | Two knobs, and a second answer nobody can reconcile with the first | Andre |

---

### Row #7 - The pair row gains the stamp, and the store is refiled

- **Scope:** `StorySimilarityPair` gains five columns at the tail, the reader learns to fill a non-null default, and the one committed file is refiled so the store stays appendable.
- **Files touched:**
  - `backend/idhazh/contracts/story_similarity_pair.py`
  - `schemas/story-similarity-pair.schema.json` (generated)
  - `frontend/src/contracts/` (generated)
  - `state/story-similarity/scored-pairs/2026/09/18.csv`
  - `docs/architecture/contracts/schemas.md`
  - `backend/tests/contracts/`
  - `backend/tests/fixtures/`
- **Acceptance gates:** local - the contract tests, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** a fixture carrying the pre-change header is refiled, then a fresh row is appended to it through the ledger's own append path without raising. **The append is the load-bearing half** - a read-only oracle cannot see the header equality check that makes the store unappendable. It cannot settle whether the committed archive refiles cleanly; the refile is run once, under sign-off, and its output is reviewed as a diff.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The columns are appended in the row's own body, not inherited, so the header widens rather than reorders. | Fowler |
| 2 | The reader gains a branch dropping an empty cell for any field whose default is not `None`. The existing reader converts to `None` only when the default is `None`, so a Literal would receive `""` and the loader stops the read rather than skipping the row. | Fowler |
| 3 | The committed file is refiled in the same commit. Without it `_append` refuses the file and a re-dispatch of that date kills the commit step and every ledger staged beside it. | Andre |
| 4 | A refile adds empty cells and changes no value any run wrote, so it is not an edit to the archive's evidence. The repository already ships the helper for exactly this. | Andre |
| 5 | `judge_id` carries a default rather than being required, so the refile can fill it and the draw - which writes these rows with verdict columns empty - does not have to invent an instrument. | Fowler |
| 6 | `decode_seconds` keeps its existing meaning on this row: both calls on the pair. The description says so, because the mixin's field of the same name is one call. | Andre |
| 7 | ESCALATE: committed rows are rewritten. Sign-off on the refile before it runs. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Inherit the mixin on this row too | The header reorders and `_append` raises; the store becomes unappendable | One declaration instead of two, and a dead store | Fowler |
| 2 | Leave the committed file alone | The header check refuses it on the next append, and a re-dispatch of that date takes the whole commit step down | Nothing now, and a failed run later | Andre |
| 3 | Start a new store at the new shape | Two stores for one question, joined by every reader for ever | A second path and a permanent fork | Fowler |
| 4 | Make `judge_id` required | The draw writes these rows before any judge reads them, so it would have to assert an instrument that has not run | One less default, and a stamp that can be wrong | Fowler |

---

### Row #8 - The line-against-holdout row

- **Scope:** the persisted shape for scoring the merge line against the labelled holdout, with its ledger path and prune target.
- **Files touched:**
  - `backend/idhazh/contracts/line_holdout_score_row.py` (new)
  - `backend/idhazh/contracts/export.py`
  - `backend/idhazh/ledger.py`
  - `schemas/line-holdout-score-row.schema.json` (generated)
  - `frontend/src/contracts/` (generated)
  - `docs/architecture/contracts/schemas.md`
  - `backend/tests/contracts/`
- **Acceptance gates:** local - the contract tests, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the row round-trips through CSV and refuses a set of cells whose sum exceeds the labelled population. It cannot settle whether the cells were counted correctly; row #18's oracle does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | It scores the LINE, not the judge. The holdout rows carry no verdict column, the shipped implementation takes weights and a line and calls no model, and the labels were written by an outside model. | Andre |
| 2 | It does not inherit `JudgeCallStamp`. Eight judge-call columns here would be five nulls and a `judge_id` asserting an instrument that never ran. | Andre |
| 3 | A `labeller` column, free text rather than a `JudgeModelId`, because the committed labels name a model that is not in the pipeline's registry and a column that could only hold pipeline models would refuse the truth. | Andre |
| 4 | Counts only, no stored rate. Every rate is derived at read time with the negative population in view. | Guardrail #10 |
| 5 | The schema register gains a row, and the store joins the prune targets. | Section 11 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Store precision and recall | With four labelled negatives one flip moves the rate 25 points, and a stored rate loses its denominator | Two columns, and a number that reads as a measurement | Guardrail #10 |
| 2 | Put the judge stamp on it anyway, for symmetry | Symmetry that asserts a model ran when none did | Five null columns and one false one | Andre |
| 3 | Reuse the existing frozen two-story maximum constant as the answer | A constant in a knobs module and a counted row would be two sources of truth for one number | Nothing, and a contradiction the next reader finds | Andre |

---

### Row #9 - The leg timeout moves to the block that validates it

- **Scope:** the judging leg's timeout knob is renamed and moved beside the two numbers its own validator reads, and the utility that reads it learns to address a nested block.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/run.py`
  - `backend/idhazh/contracts/knobs/` (the block that receives it)
  - `backend/idhazh/contracts/app_config.py`
  - `config/idhazh.json`
  - `backend/utilities/shard_bound.py`
  - `.github/workflows/llm-council.yml`
  - `frontend/src/lib/server/config.ts`
  - `docs/concepts/config.md`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`
  - `schemas/app-config.schema.json` (generated)
  - `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - the two named test modules, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the dotted key the workflow passes and the field the contract declares resolve to the same value, and the utility returns a bare positive integer. It cannot settle whether the bound is the right size - row #10's reading does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The new name is `assemble.same_story.adaptive_dedup_threshold.leg_timeout_minutes`, committed value 200, bounds unchanged. | Fowler |
| 2 | `shard_bound.py` resolves a dotted path rather than a leaf under a fixed block. One reader, one refusal message - the utility's own docstring requires it. | Carmack |
| 3 | A straight rename in one commit. One config file, one fixture, no payload an earlier run wrote. | Fowler |
| 4 | `run.shard_timeout_minutes` does not move and does not change meaning; the utility keeps resolving it. | Fowler |
| 5 | The hand-written frontend config mirror moves with it, or the two disagree silently. | Fowler |
| 6 | ESCALATE: the knob and the workflow key land in one commit, or the workflow resolves no bound and the leg runs to the platform ceiling. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave it in the run block | The validator keeps asserting something pair-specific about a generic knob | Nothing, and two timeouts neither of which says which judge it bounds | Fowler |
| 2 | Give the utility a `--block` flag beside `--key` | Two ways to spell one address, which is the drift a single reader exists to stop | One flag, and a second grammar | Carmack |

---

### Row #10 - The measured judge pair replaces the derived call

- **Scope:** every surface quoting a per-call judge cost derived from a tokens-a-second figure carries the measured per-pair reading instead, and that reading gets its own benchmark page.
- **Files touched:**
  - `config/idhazh.json`
  - `backend/idhazh/contracts/knobs/run.py`
  - `backend/idhazh/contracts/knobs/placement.py`
  - `backend/idhazh/contracts/app_config.py`
  - `backend/utilities/measure_judge_call.py`
  - `.github/workflows/llm-council.yml`
  - `docs/concepts/pipeline-loop.md`
  - `docs/reference/benchmarks/what-a-judge-pair-costs.md` (new)
  - `TODO/20260920-a-second-judge-in-the-council-handover.md`
  - `backend/tests/test_measure_judge_call.py`
  - `schemas/app-config.schema.json` (generated)
  - `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - the named test module, contract export, drift gate, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the page's figures reproduce by re-running its stated arithmetic over the committed scored-pairs file it names. It cannot settle the per-call split - the committed column is the sum of both calls, and the prefix is shared, so a per-call figure is an inference until row #14's spans measure it.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The published reading is **94.53 s a pair** - min 72.80, max 110.98, population sd 7.84, n = 82, judged 2026-09-18 on four stock `ubuntu-latest` legs, `Qwen3.5-9B-Q4_K_M`. The four legs' means spread 88.24 to 99.89 s, a 13.2 percent lottery. | Carmack |
| 2 | **47.3 s a call is not published as a measurement.** The committed column is the sum of both calls, the second call reuses the system-turn prefix, so the split is knowably uneven with the direction known and the magnitude unknown. The page labels it an inference and names row #14's spans as what settles it. | Andre |
| 3 | The leg bound is sized against the worst measured pair, not the mean. A max 17 percent above the mean is what a bad night looks like, and the page says which statistic sizes the bound. | Carmack |
| 4 | The provenance cites the council's own Actions run for the judging, and notes that the `run_id` column on those rows addresses the day's publish instead. | Carmack |
| 5 | The workflow header's justification for the council being a separate workflow becomes false at the measured figure - 200 pairs is 5.25 h, under the ceiling. The header is rewritten to state the real reason: the work job already occupies the day. | Carmack |
| 6 | The handover's "the council has never run" line is false as of 2026-09-18 and is corrected in the same pass. | Carmack |
| 7 | The page is named for what it measured; a re-run replaces it rather than adding a second page. | AGENTS.md |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Publish 47.3 s a call as measured | It is a halved sum of two unequal calls, and it is the number that sizes a budget | Nothing, and a budget built on an inference nobody labelled | Andre |
| 2 | Keep the conservative derived figure | An unlabelled margin is a wrong number, and it sizes the second judge's budget | A 1.64x error inherited by every later decision | Carmack |
| 3 | Wait for a 200-pair night | The cap has never run and nothing schedules it | One scheduled run at the cap | Carmack |
| 4 | Take the per-call reading now with the existing measurement tool | It needs a live server and a runner; row #14's spans get it from the production path for free | A dispatch, a runner and a benchmark job | Carmack |

---

### Row #11 - Thinking is refused and the decode is stamped

- **Scope:** a judge call refuses to run against a model entry that opens a thinking channel, asks the server for the whole grammar-legal first-token set under a pinned probability mode, and digests the sampler keys of the body it actually posted.
- **Files touched:**
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/similarity/prompt.py`
  - `backend/idhazh/similarity/stamps.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/fixtures/`
  - `docs/reference/benchmarks/which-probabilities-the-server-returns.md` (new)
- **Acceptance gates:** local - the similarity test modules, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** a canary drives a judge call against a model entry declaring a thinking close and asserts the call is refused; a second drives a recorded reply whose returned window does **not** contain all three verdict openings and asserts the row records that rather than reporting a margin over an incomplete set. It cannot settle what a live model returns - a recorded completion proves the pipeline's behaviour on that fixture.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Three of five registry entries declare a non-null thinking close; the active entry does not, so the committed rows are clean. The guard is a precondition, not a property of today's config. | Andre |
| 2 | Refuse the call rather than record the flag. The grammar would force a verdict token where the model meant to start reasoning, the reply would still parse, and the margin would describe a reasoning channel. | Andre |
| 3 | The refusal is scoped to the judge call. The summariser legitimately uses a thinking channel and must not be affected. | Andre |
| 4 | The alternatives window is sized to the grammar's legal first-token set, not to the count of verdict words. A grammar admits any token whose bytes are a legal prefix, so a three-wide window can hold a leading space and a one-letter prefix while two verdicts sit outside it. | Andre |
| 5 | `post_sampling_probs` is sent explicitly rather than inherited from a build default, and which mode the server returns is measured and written up. A margin over an unpinned mode is a reading about the grammar or about arbitrary vocabulary tokens, and nobody can tell which. | Andre |
| 6 | The decode digest is taken from the sampler keys of the posted body, never from config. A digest built off config cannot see a payload-builder bug, which is the one failure it exists to catch. | Andre |
| 7 | The space-trap guard and the encode-in-position helper move into the model layer, because every judge needs them and only one has them. | Fowler |
| 8 | This row computes; row #13 writes. Reader before writer. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Record the thinking flag without refusing | A recorded defect is still a defect, and the verdicts are unusable either way | One column, and a night of judging to discard | Andre |
| 2 | Keep the three-wide window | It is sized to the answer set rather than to what the grammar admits, so it can exclude the answers | Nothing, and a margin computed over the wrong tokens | Andre |
| 3 | Assert thinking off in the prompt wording | Prompt wording is not a control, and a template cannot close a channel the server opened | A guard that reads as one without being one | Andre |
| 4 | Leave the probability mode unpinned | It is a property of an unpinned build, and it silently changes what every margin means | Nothing, and a reading nobody can interpret | Andre |

---

### Row #12 - The four verbs name their work

- **Scope:** the same-story verbs, their stage modules, their stage functions and the workflow job ids are renamed to say what they do rather than which mechanism they use.
- **Files touched:**
  - `backend/idhazh/cli.py`
  - `backend/idhazh/stages/judge_draw.py` -> `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/stages/judge_shard.py` -> `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/stages/judge_fold.py` -> `backend/idhazh/stages/count_verdicts.py`
  - `backend/idhazh/stages/judge_fit.py` -> `backend/idhazh/stages/set_merge_line.py`
  - `backend/idhazh/similarity/fit.py`, `backend/idhazh/similarity/fold.py`
  - `backend/tests/test_similarity_draw.py`, `backend/tests/test_similarity_fit.py`, `backend/tests/test_similarity_judge.py`
  - `.github/workflows/llm-council.yml`
  - `docs/how-to/label-the-similarity-holdout.md`
  - `docs/reference/repository-layout.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
- **Acceptance gates:** local - the changed-test selector over the similarity modules, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the `STAGES` tuple and the verbs the workflow files spell are compared name for name by the workflow harness, and the three council members of `ServerJob` each resolve to a job id present in a workflow file. It cannot settle whether the new names are better - decision 1 is the owner ruling.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `judge-draw` -> `pick-item-pairs`, `judge-shard` -> `judge-item-pairs`, `judge-fold` -> `count-verdicts`, `judge-fit` -> `set-merge-line`. | Owner, 2026-09-20 |
| 2 | A verb names its subject, and nothing is named `judge-<step>` again. That is what lets the summary-quality judge take `pick-summaries`, `score-summaries` and `count-scores` without colliding. | Fowler |
| 3 | A judge whose emitted token is the answer takes the stem `judge-`; one whose token is discarded and whose distribution is the answer takes `score-`. | Andre |
| 4 | The workflow job ids move with the verbs, because `ServerJob` values are job ids. | Fowler |
| 5 | The oracle asserts over the three council members only. Two existing members name no job in any workflow - one retired with its job and is kept for committed rows, one names a filename writer and not a column - and asserting over all of them would go red on members that must stay. | Fowler |
| 6 | The `judge-` grouping in `--help` is given up. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | `idhazh judge <name> <verb>` | The router would hold a name registry, which section 1a forbids, and only one of four steps is shared | A dispatch table and a package with no reason to exist | Fowler |
| 2 | Keep `judge-` as a family prefix | The prefix is what ties the verbs to one loop, which is the defect | The second judge's verbs either lie or break the pattern | Fowler |
| 3 | Rename the verbs but leave the modules | A module defining a verb it is not named for is the drift the router rule exists to stop | A file disagreeing with its only export | Fowler |

---

### Row #13 - The leg fills the stamp

- **Scope:** the judging leg records, per reading, which judge read it, at what temperature, under which posted sampler, whether the grammar applied, and what the returned first-token window held.
- **Files touched:**
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/similarity/fold.py`
  - `backend/idhazh/similarity/stamps.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/fixtures/`
- **Acceptance gates:** local - the similarity test modules, ruff, mypy. CI - full suite.
- **Oracle:** a recorded reply whose returned window omits a verdict opening produces a row with `grammar_applied` recorded, `usable` false, and `verdict` null - and the fold skips it. **The margin is not asserted against the vector**, because both derive from one tuple and that assertion is a tautology that cannot go red.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A grammar failure is recorded rather than raised: `grammar_applied` false, `usable` false, `verdict` null where there was none. Today it raises and the leg dies, so absence means two things an operator cannot separate. | Andre |
| 2 | A recorded failure is counted in `grammar_failures` and not in `rows_judged`, so the disagreement rate stays a share of the population it is drawn from. | Andre |
| 3 | The fold's docstring already claims `usable` is false when the grammar could not be shown to have held. That is false today because the path raises; this row makes it true and the docstring stops lying. | Andre |
| 4 | The leg is the only writer of the stamp's model-side columns. The draw writes the row with its verdict columns empty and carries only the defaulted `judge_id`. | Fowler |
| 5 | The judge's identity is a module constant in the stage, not a config knob. | Guardrail #6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep raising on a grammar failure | Absence means two different things and an operator cannot separate them | A failure mode that reads as a missing leg | Andre |
| 2 | Assert the margin against the stored vector | Both derive from one tuple, so the oracle is a tautology that passes in every failure world | A green test that proves nothing | Andre |

---

### Row #14 - The leg writes its row and opens its spans

- **Scope:** each judging leg writes one segment row describing what it did and how its instrument behaved, opens a span per model call, and the compaction drains both.
- **Files touched:**
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/telemetry/spans.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/workflows/test_ledger_staging.py`
  - `backend/tests/fixtures/`
- **Acceptance gates:** local - the similarity, telemetry and staging test modules, ruff, mypy. CI - full suite.
- **Oracle:** a leg's row satisfies `rows_owned = rows_judged + grammar_failures + rows_unreadable` against the verdict rows that leg wrote, and its median margin is the median of the margins in those rows. It cannot settle whether the machine readings are accurate; the sampler owns that and plan 37 is changing it.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The leg row is leg-grain because no per-reading row can hold it. | Andre |
| 2 | A span is opened per call, not per pair. A pair is two calls in opposite orders and averaging them hides the order that was slow - and it is what settles row #10's inferred per-call split. | Andre |
| 3 | The leg writes its segment even when it judged nothing. | Andre |
| 4 | The staging drift guard is widened in this row to every workflow reaching a store writer, not only the daily one. Scoping a drift guard to a file rather than to a question is what let a second writer through before. | Carmack |
| 5 | The two filled-by-nothing entries added in row #4 are deleted here for the leg store. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Commit a per-call trace file | Per-call JSONL for 400 calls a night, when the stamp already carries what a trace would | Storage growing every run | Fowler |
| 2 | Write the leg row from the fold | The fold cannot see the leg's machine, and a leg that died wrote nothing for the fold to read | Nothing recorded for the failure case | Andre |
| 3 | Leave the staging guard scoped to the daily workflow | Three new state writers land in a workflow the guard does not read - the same defect, again | Nothing, and an unstaged store that goes with the runner | Carmack |

---

### Row #15 - The council records the machine it ran on

- **Scope:** the judging legs write a host fingerprint and a job clock before the server starts, and the fold stages and commits everything the legs left behind.
- **Files touched:**
  - `.github/workflows/llm-council.yml`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `backend/tests/workflows/test_staged_paths.py`
  - `backend/tests/workflows/test_ledger_staging.py`
  - `state/content-similarity-judge/shards/.gitkeep`
- **Acceptance gates:** local - the three workflow test modules. CI - full suite.
- **Oracle:** the fingerprint step appears **before the step named `Start the model`**, and every state prefix a leg writes appears in the fold's staged path set. It cannot settle whether the readings are accurate on a runner.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The legs keep the host fingerprint, the job clock, spans and the segment compaction, and take nothing else from the digest workflow. | Owner, 2026-09-20 |
| 2 | Dropped deliberately: the item-health ledger, feed health, the day census, committed per-item traces, day metrics and counterfactual scores. A judge has no items with terminal states, reads no feeds and publishes no day. | Owner, 2026-09-20 |
| 3 | The fingerprint runs **before the model server starts**, not merely before the first model call. The bandwidth probe wants two buffers of at least 512 MiB and the server peaks at 14.31 GiB of a 16 GB runner, so a step placed after the server OOMs the leg. The oracle asserts the order against the server step by name. | Carmack |
| 4 | The probe carries `continue-on-error`, and the job clock carries both `if: always()` and `continue-on-error`. A leg at the cap holds hours of decode; a failed instrument must not throw it away. | Carmack |
| 5 | The fold stages four new prefixes: the segment transit, the host fingerprint, the span rollup and the judge head. Nothing commits any of them today, and `git add` under a failing shell aborts the whole step and costs the ledgers staged beside it. | Carmack |
| 6 | A header-only day file is committed for the judge head, so a fresh clone has a path for `git add` to find. This is the three-part fix the same defect needed before. | Carmack |
| 7 | This row assumes plan 37's corrected sampler and does not wait for it. The steps are the same either way. | Owner, 2026-09-20 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Import the digest workflow's observability set wholesale | Half of it answers questions a judge does not have | Six stores that stay empty or carry meaningless rows | Owner |
| 2 | Wait for plan 37 | The steps are identical; only the sampler's arithmetic differs | A serialized dependency for no change | Owner |
| 3 | Build a new shipping path | The segment store and the compaction verb already drain six ledgers | A second transit mechanism to keep in step | Fowler |

---

### Row #16 - The model block becomes one composite action

- **Scope:** the weights cache, the fetch, the checksum verify, the server start and the health probe become one composite action, used by the two workflows that run all five steps.
- **Files touched:**
  - `.github/actions/model-server/action.yml` (new)
  - `.github/workflows/llm-council.yml`
  - `.github/workflows/digest.yml`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `backend/tests/workflows/`
- **Acceptance gates:** local - the workflow harness across both files. CI - full suite.
- **Oracle:** the cache key literal inside the action matches a committed fixture, character for character. **Not a comparison against the daily workflow** - once the key moves into the action there is nothing left in that workflow to compare against, so the old oracle cancels itself.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The full five-step block exists **twice**, in the daily workflow and the council. Six cache blocks exist overall, but the other four share at most one of the five steps. The row is scoped to the two. | Carmack |
| 2 | Converting the measurement and validation workflows is out of scope and priced in the scope-out table. | Carmack |
| 3 | A composite action carries no job-level knob, so the leg bound, the matrix and the runner label stay in the workflow. | Carmack |
| 4 | The cache-hit output is declared explicitly, or the condition on the fetch step silently stops working. | Carmack |
| 5 | The one-server-per-leg guard must survive by reading the action's step list rather than the job's. It is what stops a second server landing on a 16 GB runner. | Carmack |
| 6 | Whether a composite step sees the caller's workflow-level environment is verified on a branch before the row is written; if it does not, the port becomes an action input and the single-port test is told where to look. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A callable workflow | Its only unique benefit is a per-caller runner label and permission set, and no judge needs either | A restructure for a differentiation nothing uses | Carmack |
| 2 | Leave the duplication | Two copies that drift the day one is edited, which has happened twice here | The next judge makes it three | Carmack |
| 3 | Convert all six cache blocks | Four of them share one of the five steps; folding them in would make the action a parameter soup | A larger action and four callers that use a tenth of it | Carmack |

---

### Row #17 - The store groups under the judge that fills it

- **Scope:** the committed same-story tree moves under the judge slug that produced it, and every reader, workflow path and document naming the old tree moves with it.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/utilities/sample_sheet.py`
  - `state/story-similarity/` -> `state/content-similarity-judge/`
  - `.github/workflows/llm-council.yml`
  - `.gitattributes`
  - `frontend/src/lib/server/similarity-holdout.ts`
  - `frontend/src/routes/console/judgement/+page.server.ts`
  - `docs/reference/repository-layout.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/concepts/partitions.md`
  - `docs/concepts/growing-reads.md`
  - `docs/architecture/publishing/retention.md`
  - `docs/how-to/label-the-similarity-holdout.md`
  - `TODO/20260920-a-second-judge-in-the-council-handover.md`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `backend/tests/`
- **Acceptance gates:** local - the ledger and similarity test modules, the workflow harness, the frontend build, `doc_load.py --changed`. CI - full suite, plus the published-site smoke.
- **Oracle:** no reader in `backend/`, `frontend/`, `.github/` or `docs/` resolves a path under the old name - a grep over tracked files, asserted once. **The file-by-file byte comparison is an operator check run during the move**, not a committed test: walking the tree on every run is a growing read (Guardrail #12).
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge slug is the group, so the store a judge produces sits under the judge's name. | Owner, 2026-09-20 |
| 2 | The stores under it keep their names - scored pairs, fitted thresholds, the distribution record, the holdout and the archive all move unchanged. | Fowler |
| 3 | The council workflow names the old paths in its commit step. It moves in this row, or the next run's `git add` aborts under a failing shell and costs the ledgers staged beside it. | Carmack |
| 4 | Two utilities build their paths from the directory constants and follow the rename for free; the ones that spell the path move by hand. The attribute file pins the holdout by exact path and its rule goes dead unless it moves. | Fowler |
| 5 | `git mv` per file, so history follows and the move reviews as a rename. | Fowler |
| 6 | A rename of the tree, not a rewrite of its rows. | Fowler |
| 7 | ESCALATE: this moves committed data. The path map is signed off before any file moves. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the tree and put only new judges under slugs | Two organising schemes, and the oldest judge looks like the exception | A layout no reader can infer a rule from | Fowler |
| 2 | Leave a compatibility path | A second name for one store, which is the drift the closed sets exist to stop | One path that works and one that used to | Fowler |

---

### Row #18 - Where the line stands against its holdout

- **Scope:** the merge line is scored against the labelled holdout and the four counts are committed, with the negative population beside them and a floor below which the reading is refused.
- **Files touched:**
  - `backend/idhazh/similarity/holdout.py` (new)
  - `backend/idhazh/stages/score_line_holdout.py` (new)
  - `backend/idhazh/cli.py`
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/contracts/knobs/placement.py`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/how-to/label-the-similarity-holdout.md`
  - `docs/concepts/growing-reads.md`
  - `backend/tests/workflows/test_ledger_staging.py`
  - `backend/tests/`
- **Acceptance gates:** local - the similarity and contract test modules, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the four cells plus the unresolved count sum to the labelled population, **and** the resolved count clears a stated floor - without the floor, a run that resolved nothing satisfies the sum with four zeros and a full unresolved count, and the row reads as a measurement. It cannot settle whether the line is good: with four labelled two-story pairs, no rate from these cells is a measurement.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | It scores the line, not the judge. A judge-against-holdout measurement is a different row and a different budget, and it is named in the scope-out table. | Andre |
| 2 | A shipped implementation already does this in the console's server layer. This row commits the counts so the reading survives the page, and the two must agree; the console reads the committed row rather than recomputing beside it. | Andre |
| 3 | The read is bounded by the holdout file, whose rows name their own two days. The existing sheet tool walks the archive only because it resolves against a different date, and this row must not copy it. | Guardrail #12 |
| 4 | ESCALATE: below the resolved-pairs floor the four cells are written null rather than zero, and the row says why. That is the same rule the leg row applies to its rates. | Owner, 2026-09-20 |
| 5 | The frozen two-story maximum constant in the knobs module is reconciled with this row or retired, so one number does not have two sources. | Andre |
| 6 | The labels interleave - one story at 0.9406, two stories at 0.9407, one story at 0.9409 - so no single threshold separates the populations. This row measures where the line stands; it does not assert a perfect line exists. | Andre |
| 7 | The verb is `score-line-holdout`. A person types it; nothing in the daily pipeline calls it. | Carmack |
| 8 | The growing-reads inventory gains a row naming what this reads and why a fixture cannot answer it. | Guardrail #12 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Publish one accuracy figure | With 196 of 200 pairs on one side, always answering "one story" scores 98 percent and measures nothing | A number that looks excellent while the line is useless | Andre |
| 2 | Have the judge label more holdout pairs | The holdout's authority comes from being labelled outside the loop | The floor becomes a copy of the line it polices | Andre |
| 3 | Delete the row and keep only the console panel | A reading that exists only while a page renders cannot be compared across weeks | Nothing to store, and no history | Andre |
| 4 | Score on every run | It measures the instrument, so it is taken when the instrument or the line moves | Model time for a number that only moves when a fingerprint does | Carmack |

---

### Row #19 - The plan pointers

- **Scope:** the two indexes that list live plans learn this one exists, and the closed rows' findings reach the pages that own them.
- **Files touched:**
  - `AGENTS.md`
  - `TODO/STATUS.md`
  - `docs/reference/agent-notes/`
  - `docs/architecture/publishing/autotune-content-similarity.md`
- **Acceptance gates:** local - `doc_load.py --changed`. CI - full suite. No application suite: documentation-only closure.
- **Oracle:** every live plan file under `TODO/` is named by both indexes, and every index entry names a file that exists. It cannot settle whether the descriptions are accurate.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A plan absent from the indexes is invisible to the next agent, and every landed plan in this repository has carried its pointer. | Fowler |
| 2 | The findings that outlive the plan go to the living doc that owns them, not into the plan-doc's own history. | Guardrail #4 |
