# Name the judges, and give them an instrument

**Last Updated**: 2026-09-20

**Level**: 5 (a persisted contract with committed rows, and a committed state tree that moves)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 3 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Four CLI verbs name their mechanism rather than their work, a second judge lands soon that shares one of their four steps, and the judging legs record nothing about the machine they ran on while the store that would ship it already exists. |
| Hard scope - in | Rename the four same-story verbs and their modules; fix the verdict upload a cancelled leg skips; replace the derived per-call cost with the measured one; move the leg-timeout knob to the block its validator reads; assert thinking off and stamp the decode; declare the judge-call stamp, the judge-leg row and the holdout-score row; open `ServerJob` and `SegmentLedger` to judges; wire the host fingerprint, the job clock, spans and the segment compaction into the council; group the committed store under the judge slug; score the judge against its holdout; lift the model block into one composite action. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | (1) Row #4 adds four columns to a contract with 82 committed rows - pause for sign-off on the migration before writing it. (2) Row #13 moves a committed state tree - pause for sign-off on the path map before any file moves. (3) Any row that would raise a runner budget figure (Guardrail #2). (4) Row #14: if the holdout still carries 4 labelled two-story pairs, commit the counts and refuse the rate. (5) Row #6 renames a config knob AND the workflow key that reads it - if the two cannot land in one commit, stop. |
| Chosen strategy | Share the model call, not the judge - one constrained-decode layer and a per-reading stamp each judge embeds in its own row, with per-judge packages, contracts and stores above it. Fowler, Carmack and Andre in debate, owner ruling 2026-09-20. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 3.` Three rather than four because the file islands never widen past three: `.github/workflows/llm-council.yml`, `backend/idhazh/ledger.py` and `backend/idhazh/cli.py` are each touched by several rows, and a fourth slot would only produce a held row. |

### How the rows group into pull requests

**A `Parallel-group` letter is one pull request, not one row.** Rows sharing a letter are written together, gated once and merged once. That is what keeps fifteen rows from becoming fifteen review cycles, and it is safe because rows inside a letter share a surface, an owner and a risk profile.

| Group | Pull request | Rows | Why these ship together |
| --- | --- | --- | --- |
| A | The cancelled leg keeps its verdicts | 1 | One line, and it frees the workflow file for every later group. Ships alone and first |
| B | Every persisted shape this plan needs | 2, 3, 4, 5 | All four regenerate `schemas/` and three touch `backend/idhazh/ledger.py`; split, they are four conflicting drift-gate regenerations |
| C | What a call costs, and where its bound lives | 6, 7 | Both touch `backend/idhazh/contracts/knobs/`, `config/idhazh.json` and the generated app-config schema |
| D | The model boundary asserts what it assumed | 8 | `backend/idhazh/llm/` and `backend/idhazh/similarity/`, no persisted shape, no workflow |
| E | The verbs name their work | 9 | Atomic by nature: a verb renamed in `cli.py` and not in the workflow is a run that dies mid-pipeline |
| F | The legs write what they did | 10, 11 | Both are the judging stage filling shapes group B declared |
| G | The council records the machine it ran on | 12, 15 | Both are one pass over `.github/workflows/llm-council.yml` |
| H | The store groups under the judge that fills it | 13 | A tree move, gated on its own |
| I | Where the judge stands against its holdout | 14 | Reads the moved tree, so it follows H |

Nine pull requests for fifteen rows. Groups B, C and D have no predecessor once A lands, which is where the three slots are spent.

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| A `Judge` base class, protocol or registry | The second judge duplicates the stage shape, about 150 lines | A third judge sharing three of the four steps, rather than one |
| A second CLI level (`idhazh <loop> <verb>`) | The flat verb list grows from 25 to about 30 | The first time a flag's help text has to name which judge it belongs to |
| One workflow per judge | Every judge shares one cron, one concurrency group and one runner label; a slow pair day delays the quality fold | A judge needing different weights or a different cadence - which is the independent second-opinion judge |
| The independent second-opinion judge itself | The holdout stays labelled by something the fit consumes, so the floor cannot police the line | The six questions in `20260920-a-second-judge-in-the-council-handover.md` being answered |
| The summary-quality judge's own stages | Plan 36 owns them; this plan only declares the shapes it would reuse | Plan 36 reaching its G-Eval row |
| Promoting fluency to a publish gate | Nothing today - it is a drift monitor and feeds nothing | A measured injection delta on the score, not a shape assertion |
| Console panels for judge health | An operator reads committed rows rather than a page | Plan 36 row #9, which owns `/console/judgement/` |
| Renaming `backend/var/judge/` | The scratch directory keeps a word naming one loop's draw | The parallel work already moving production artefacts out of the code tree |
| A judge role in `ModelRole` | Every judge keeps inheriting the summariser's weights, so no judge can be independent | The second-opinion judge, which is the first that needs different weights |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A cancelled leg keeps the verdicts it paid for | - | A | PENDING | - | - | - |
| 2 | The judge-call stamp, declared once | 1 | B | PENDING | - | - | - |
| 3 | `ServerJob` and `SegmentLedger` admit judges | 1 | B | PENDING | - | - | - |
| 4 | The stamp lands on the pair row | 2 | B | PENDING | - | - | - |
| 5 | The judge-leg row and the holdout-score row | 2, 3 | B | PENDING | - | - | - |
| 6 | The leg timeout moves to the block that validates it | 1 | C | PENDING | - | - | - |
| 7 | The measured judge call replaces the derived one | 1 | C | PENDING | - | - | - |
| 8 | Thinking is asserted off and the decode is stamped | 2 | D | PENDING | - | - | - |
| 9 | The four verbs name their work | 3, 6 | E | PENDING | - | - | - |
| 10 | The leg fills the stamp | 4, 8, 9 | F | PENDING | - | - | - |
| 11 | The leg writes its row and opens its spans | 5, 10 | F | PENDING | - | - | - |
| 12 | The council records the machine it ran on | 11 | G | PENDING | - | - | - |
| 13 | The store groups under the judge that fills it | 5 | H | PENDING | - | - | - |
| 14 | Where the judge stands against its holdout | 13 | I | PENDING | - | - | - |
| 15 | The model block becomes one composite action | 12 | G | PENDING | - | - | - |

## Section 1a - The contracts, settled before any row is written

Guardrail #3: a shape is declared before logic reads or writes it. Everything below is settled, so no worker invents a field. Types are the aliases in `backend/idhazh/contracts/base.py` (`DateStamp`, `RunId`, `Sha256`, `UrlKey`, `Timestamp`).

### New type alias

`JudgeId = Literal["content-similarity-judge", "summary-content-quality-judge"]`, in `backend/idhazh/contracts/judge_call.py`.

A Literal rather than a string for the reason `ScorerModelId` is one: a fold over a store mixing two instruments sums readings that mean different things, and a free-text column splits silently on a typo. It lives in the new module because two contracts import it and neither may import the other. `JudgeModelId` and `ScorerModelId` already exist in `backend/idhazh/contracts/story_similarity_pair.py` and are reused unchanged.

### `JudgeCallStamp` - a mixin, not a standalone payload

`class JudgeCallStamp(Model)` in `backend/idhazh/contracts/judge_call.py`. It declares no `__schema_stem__` and writes no file: each judge's own row inherits it, so the columns are declared once and flattened into that row's CSV. Four of the eight fields already exist on `StorySimilarityPair` and move onto the mixin unchanged.

| Field | Type | Default | State | Description to carry |
| --- | --- | --- | --- | --- |
| `judge_id` | `JudgeId` | - | **new** | Which instrument wrote this reading. Without it a fold over a shared store sums two instruments |
| `judge_model` | `JudgeModelId \| None` | `None` | moves | Which weights judged |
| `decode_digest` | `Sha256 \| None` | `None` | **new** | sha256 of the canonical JSON of temperature, top-p, seed, prediction length and whether thinking was open. The row records the model but not the sampler, so a tuning edit changes what every verdict means with nothing saying so |
| `prompt_digest` | `Sha256 \| None` | `None` | moves | sha256 of the rendered system turn |
| `grammar_digest` | `Sha256 \| None` | `None` | moves | sha256 of the grammar handed to the decoder |
| `grammar_applied` | `bool \| None` | `None` | **new** | Whether the reply opened inside the grammar. Today a failure raises and writes no row, so an operator reading absence cannot tell it from a leg that never started |
| `first_token_probabilities` | `str \| None` | `None` | **new** | Compact JSON, token to probability, at the deciding position. The full vector rather than a derived scalar, so a scoring-formula fix is re-applied from the row instead of by re-spending model time |
| `decode_seconds` | `float \| None` | `None` | moves | Wall clock for this reading |

**`usable`, `verdict`, `verdict_swapped` and `first_token_margin` stay off the mixin.** Agreement between two readings is a position-bias control and has no honest meaning for a judge whose input has no order.

### `StorySimilarityPair` - four columns added

`backend/idhazh/contracts/story_similarity_pair.py`. The declaration becomes `class StorySimilarityPair(JudgeCallStamp, Contract)`. The four stamp fields already in the body are deleted and inherited instead; `judge_id`, `decode_digest`, `grammar_applied` and `first_token_probabilities` are new columns.

Changelog entry to prepend, newest first:

| version | change | why |
| --- | --- | --- |
| `2026-09-20` | Added the judge-call stamp: which judge, its decode digest, whether the grammar applied, and the first-token vector. | A verdict could not be read back to the sampler that produced it. |

**The read-side migration ships in the same commit.** Rows committed before this change lack the four columns. `from_csv_row` fills absent keys from the model defaults, so the three nullable columns read as `None`. `judge_id` is not nullable, so the reader supplies `"content-similarity-judge"` for a row carrying no value - correct because that judge is the only writer this store has ever had. **The migration rests on that property, not on a row count**, which moves every run (Guardrail #10).

### `JudgeLegRow` - new (`backend/idhazh/contracts/judge_leg_row.py`)

`class JudgeLegRow(JudgeCallStamp, CsvContract)`. `__schema_stem__ = "judge-leg-row"`. One row per judge per leg. Key: `("date", "run_id", "job", "shard", "judge_id")`.

**`attempt` is deliberately not a column.** It is in the segment filename and in no column, exactly as `SegmentName` already documents.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | The digest date this leg judged |
| `run_id` | `RunId` | - | The run that dispatched the leg |
| `job` | `ServerJob` | - | Which workflow job produced the row |
| `shard` | `int` | `ge=0` | Which leg |
| `rows_owned` | `int` | `ge=0` | Rows the draw dealt this leg |
| `rows_judged` | `int` | `ge=0` | Rows the leg got a reading for |
| `rows_usable` | `int` | `ge=0` | Rows whose two readings agreed |
| `grammar_failures` | `int` | `ge=0` | Readings that came back outside the grammar |
| `disagreement_rate` | `float \| None` | `ge=0, le=1` | Share of judged rows whose two readings differed. Null when nothing was judged - a rate over zero rows is not zero |
| `unclear_rate` | `float \| None` | `ge=0, le=1` | Share of usable rows answered UNCLEAR. Null on an empty leg, same reason |
| `first_token_margin_median` | `float \| None` | `ge=0, le=1` | Median gap at the deciding position. Collapsing while the verdict mix holds is the instrument failing, not the population moving |
| `server_start_seconds` | `float \| None` | `ge=0` | Weights load to first healthy probe. Separates a slow start from slow decoding |
| `decode_seconds_total` | `float \| None` | `ge=0` | Sum over the leg's readings |
| `reached_bound` | `bool` | default `False` | Whether the leg stopped because it ran out of clock rather than out of rows |

`decode_seconds` is inherited and, on this row, is the leg's longest single reading; `decode_seconds_total` is the sum. Both, because a leg whose total is ordinary and whose worst call is not is the leg that times out next week.

### `HoldoutScoreRow` - new (`backend/idhazh/contracts/holdout_score_row.py`)

`class HoldoutScoreRow(JudgeCallStamp, CsvContract)`. `__schema_stem__ = "holdout-score-row"`. Key: `("date", "run_id", "judge_id")`.

**Counts only. No precision, recall or accuracy column.** A stored rate is a rate somebody reads without its denominator, and this denominator is four.

| Field | Type | Constraint | Description to carry |
| --- | --- | --- | --- |
| `date` | `DateStamp` | - | When the judge was scored |
| `run_id` | `RunId` | - | The run that scored it |
| `applied_line` | `float` | `ge=0, le=1` | The merge line in force when the four cells were counted |
| `merged_and_one_story` | `int` | `ge=0` | The line joined them and the label agrees |
| `merged_and_two_stories` | `int` | `ge=0` | The line joined two stories that are not one. The reader never sees the second - the invisible direction |
| `apart_and_one_story` | `int` | `ge=0` | The line left one story in two pieces. The reader sees it twice and can dismiss it |
| `apart_and_two_stories` | `int` | `ge=0` | The line left them apart and the label agrees |
| `pairs_unresolved` | `int` | `ge=0` | Labelled pairs whose two articles were not both on a day this measurement could read. Reported, never dropped |
| `labelled_two_story_pairs` | `int` | `ge=0` | The negative population the two false-merge cells are drawn from. On the row so no rate is read without it |
| `scorer_model` | `ScorerModelId` | - | Which encoder produced the cosines the line was applied to |
| `cosine_weight` | `float` | `ge=0, le=1` | What the cosine was worth |
| `key_point_weight` | `float` | `ge=0, le=1` | What the key-point term was worth |

### `ServerJob` - three members added (`backend/idhazh/contracts/base.py`)

The enum's contract is that a value is a job's own id in its workflow file, lowercase. So the members and the workflow job ids are renamed in one commit or the contract is broken.

| Member | Value | Workflow job today | Becomes |
| --- | --- | --- | --- |
| `PICK` | `"pick"` | `draw` | `pick` |
| `JUDGE` | `"judge"` | `judge` | `judge` - unchanged; a judge dimension makes the judge a column, not a job |
| `TALLY` | `"tally"` | `fold` | `tally` |

Additive on an enum committed manifests already read, so no manifest migrates. The generated schemas listing the enum regenerate.

### `SegmentLedger` - one member per judge (`backend/idhazh/ledger.py`)

| Member | Value | Transit | Head |
| --- | --- | --- | --- |
| `CONTENT_SIMILARITY_JUDGE` | `"content-similarity-judge"` | `state/segments/content-similarity-judge/` | `state/content-similarity-judge/shards/<YYYY>/<MM>/<DD>.csv` |

**The enum's existing invariant is restated, not broken.** Today a value is the head's own directory name, so transit and head cannot be spelled two ways. A judge head is two levels - the slug, then `shards` - so the value is the slug and the head shape appends the fixed `shards` segment. One judge, one member; adding a judge adds one line.

**Why one member per judge rather than one `"shards"` member shared:** a segment filename is `<run_id>-<attempt>-<job>-<shard>.csv` and carries no judge, so two judges writing the same run, job and shard into one transit directory collide on the filename and one silently overwrites the other.

`_SEGMENT_HEADS` gains an entry: path and relpath helpers keyed on the slug, key `("date", "run_id", "job", "shard", "judge_id")`, model `JudgeLegRow`, no carried columns, `dates_from_run=False` because the row names its own day.

### Store paths (`backend/idhazh/ledger.py`)

| Constant | Value |
| --- | --- |
| `CONTENT_SIMILARITY_JUDGE_DIRNAME` | `"content-similarity-judge"` |
| `JUDGE_SHARDS_DIRNAME` | `"shards"` |
| `HOLDOUT_SCORES_DIRNAME` | `"holdout-scores"` |

Day-sharded, `<slug>/<store>/<YYYY>/<MM>/<DD>.csv`. **Two directory levels and no more:** the day inventory globs `*/<Y>/<M>/<D>` and `*/*/<Y>/<M>/<D>`, so a third level is invisible to `idhazh telemetry show` and the miss is silent.

---

### Row #1 - A cancelled leg keeps the verdicts it paid for

- **Scope:** the judging leg's verdict upload runs on a cancelled job, so a leg stopped by its own timeout no longer discards every verdict it computed.
- **Files touched:**
  - `.github/workflows/llm-council.yml`
- **Acceptance gates:** local - `backend/tests/workflows/test_llm_council_workflow.py`. CI - full suite.
- **Oracle:** the workflow test asserts every `upload-artifact` step whose artifact a later job downloads carries a condition that survives cancellation. It cannot settle whether the artifact is complete - a leg killed mid-write uploads what it had, which is the intended trade.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The step gains `if: always()`. The fold already tolerates a short leg by refusing to fold a partial day, so a truncated verdict file costs that leg's remaining pairs and nothing else. | Carmack |
| 2 | The oracle is written over the file, not over this step. The same omission has cost this repository work twice, and fixing one step is not fixing the file. | Carmack |
| 3 | Ships alone and first, because every later group edits this file. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Raise the leg timeout instead | A bound is a backstop, not a budget; an overrunning leg still loses its work | One knob edit, and the defect survives for the next overrun | Carmack |
| 2 | Upload incrementally | Four legs writing partial artifacts is a new consistency problem for a case already handled | An artifact-per-batch scheme and a fold that reassembles it | Carmack |

---

### Row #2 - The judge-call stamp, declared once

- **Scope:** the eight columns every judge reading carries, declared as a mixin in one module, with `JudgeId` beside them.
- **Files touched:**
  - `backend/idhazh/contracts/judge_call.py` (new)
  - `backend/tests/contracts/test_judge_call.py` (new)
- **Acceptance gates:** local - the new contract test, contract export, drift gate, ruff, mypy. CI - full suite.
- **Oracle:** a model inheriting the mixin round-trips every field through `csv_row` and `from_csv_row` unchanged, and the mixin declares no schema stem so nothing generates a file for it. It cannot settle whether the eight are the right eight - section 1a names why each is there.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A mixin, not a nested model. The rows are flat CSV and a nested payload would need flattening at every write. | Fowler |
| 2 | A mixin, not a separate health table. A table needs a join key and a second write, and a run dying between the two leaves a reading with no stamp. | Andre |
| 3 | The full first-token vector is stored, not only the top-two gap. A scoring-formula fix then costs a re-read of the rows instead of a night of model time. | Andre |
| 4 | `JudgeId` is a Literal of judge slugs, so a second judge is a schema diff and a changelog line rather than a silent change to what a fold sums. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One union verdict row across all judges | Half the columns are null per judge, and `usable` has no honest meaning for a rated scorer | A discriminator column and a contract asserting two instruments are one | Fowler |
| 2 | Put the stamp on a `Judge` base class with behaviour | A shared `usable` would drop every ambivalent fluency reading and bias the fitted floor with nothing red | The cheapest code, and a silently biased sample | Andre |
| 3 | Store only `first_token_margin`, as today | A scoring fix costs a re-run of the model time that produced the rows | Nothing now; a night of model time later | Andre |

---

### Row #3 - `ServerJob` and `SegmentLedger` admit judges

- **Scope:** the closed set of jobs that may appear in a segment filename gains the council's jobs, and the closed set of heads that accept segments gains the content-similarity judge.
- **Files touched:**
  - `backend/idhazh/contracts/base.py`
  - `backend/idhazh/ledger.py`
  - `backend/tests/contracts/`
  - `schemas/` (every generated schema listing `ServerJob`)
- **Acceptance gates:** local - the contract tests, contract export, drift gate. CI - full suite.
- **Oracle:** every `SegmentLedger` member resolves to a `_SEGMENT_HEADS` entry whose model is a `CsvContract`, and every member's transit directory name is derivable from its head path rather than spelled twice. It cannot settle whether a job writes a segment - row #11 does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One `SegmentLedger` member per judge, valued at the judge slug. A shared `"shards"` member would let two judges collide on one segment filename, because the filename carries no judge. | Fowler |
| 2 | The transit-equals-head invariant is restated for a two-level head: the value is the slug, the head appends the fixed `shards` segment. | Fowler |
| 3 | `ServerJob` members and the workflow job ids are renamed in one commit, because the enum's contract is that a value IS a job id in a workflow file. Row #9 carries the workflow half. | Fowler |
| 4 | This row adds the members and leaves every writer alone, so it is reader-before-writer and merges while nothing yet emits a judge segment. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A free-text job column for judges | The closed set exists to stop a typo becoming a job nobody can group by | One less enum member and a column that splits silently | Fowler |
| 2 | One `council` member for all three jobs | Three jobs with different failure modes share a name, and a segment cannot say which wrote it | One member instead of three, and a segment nobody can attribute | Carmack |
| 3 | Add `judge_id` to the segment filename grammar | The grammar is shared by six ledgers with no judge; widening it for one is a cost every ledger pays | A regex change, a rename of every existing segment, and a migration of the compaction | Fowler |

---

### Row #4 - The stamp lands on the pair row

- **Scope:** `StorySimilarityPair` inherits the stamp, gains the four new columns, and reads back the rows written before them.
- **Files touched:**
  - `backend/idhazh/contracts/story_similarity_pair.py`
  - `schemas/story-similarity-pair.schema.json` (generated)
  - `backend/tests/contracts/`
  - `backend/tests/fixtures/`
- **Acceptance gates:** local - the contract tests, contract export, drift gate. CI - full suite.
- **Oracle:** a fixture holding the pre-change column set loads through the migrated reader with the three nullable columns `None` and `judge_id` defaulted, and a row written after the change round-trips unchanged. It cannot settle whether the committed archive loads - the fixture is a copy of its shape, and Guardrail #12 forbids the test walking the store.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The four stamp fields already on the row move to the mixin and are deleted from the body, so there is one declaration rather than two that can drift. | Fowler |
| 2 | `judge_id` defaults to the content-similarity judge on a row carrying no value, because that judge is the only writer this store has ever had. The migration rests on that property, not on a row count. | Guardrail #10 |
| 3 | The changelog gains one line dated `2026-09-20` and the version stamp moves with it. | Section 11 |
| 4 | ESCALATE: committed rows exist. The migration is signed off before it is written. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Make `judge_id` nullable to avoid a migration | A null instrument on a reading is the exact ambiguity the column exists to remove | One less default, and a fold that cannot tell an unstamped row from an unknown judge | Andre |
| 2 | Rewrite the committed rows to carry the new columns | The rows are evidence of what a run did; editing them makes the archive say something the run did not write | A rewrite step and an archive nobody can trust | Fowler |
| 3 | Start a new store at the new shape | Two stores for one question, and every reader joins them for ever | A second path and a permanent fork in the record | Fowler |

---

### Row #5 - The judge-leg row and the holdout-score row

- **Scope:** the two new persisted shapes - one row per judge per leg, and one row per holdout scoring - with their ledger paths and the judge's segment head.
- **Files touched:**
  - `backend/idhazh/contracts/judge_leg_row.py` (new)
  - `backend/idhazh/contracts/holdout_score_row.py` (new)
  - `backend/idhazh/ledger.py`
  - `schemas/judge-leg-row.schema.json` (generated)
  - `schemas/holdout-score-row.schema.json` (generated)
  - `backend/tests/contracts/`
- **Acceptance gates:** local - the contract tests, contract export, drift gate. CI - full suite.
- **Oracle:** both rows round-trip through CSV, and the judge-leg head path a date resolves to is matched by the two-level day glob the telemetry inventory uses - so a store this row creates is visible to `idhazh telemetry show` rather than silently absent. It cannot settle whether the figures a leg puts in them are true; row #11's oracle does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge slug is the group and each judge owns as many day-sharded stores as it has questions - the shape `story-similarity` already uses. | Owner, 2026-09-20 |
| 2 | No `judges/` prefix. The inventory globs two directory levels and reports success while listing nothing deeper. | Fowler |
| 3 | `attempt` is not a column on the leg row. It is in the segment filename and in no column, as `SegmentName` documents. | Fowler |
| 4 | The leg row carries both the leg's total decode seconds and its longest single reading, because a leg with an ordinary total and a bad worst call is the one that times out next. | Carmack |
| 5 | Rates on the leg row are nullable and null on an empty leg. A rate over zero rows is not zero. | Andre |
| 6 | The holdout row stores counts and no rate. The negative population is four, so a stored rate is a number somebody reads without its denominator. | Guardrail #10 |
| 7 | The ledger joins the segment set in this row - the row that moves its writer - never before it. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Put the leg figures on the existing work-shard machine row | That row is one work shard of one digest run, and a judge leg is neither | A discriminator column on a row then describing two unrelated jobs | Carmack |
| 2 | Derive the funnel at read time from the verdict rows | A leg that wrote no verdicts becomes indistinguishable from a leg that never ran | Nothing to store, and the one failure the row exists to show | Andre |
| 3 | Store precision and recall on the holdout row | With four labelled negatives one flip moves the rate 25 points, and a stored rate loses its denominator | Two columns, and a number that reads as a measurement | Guardrail #10 |
| 4 | `state/judges/<slug>/<store>/<date>` | Four levels; the inventory reads two and would report success while listing nothing | A widened glob, and every existing store a level deeper than it needs | Fowler |

---

### Row #6 - The leg timeout moves to the block that validates it

- **Scope:** the judging leg's timeout knob is renamed and moved beside the two numbers its own validator reads.
- **Files touched:**
  - `backend/idhazh/contracts/knobs/run.py`
  - `backend/idhazh/contracts/app_config.py`
  - `config/idhazh.json`
  - `backend/utilities/shard_bound.py`
  - `.github/workflows/llm-council.yml`
  - `backend/tests/contracts/test_app_config.py`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `schemas/app-config.schema.json` (generated)
  - `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - the two named test modules, contract export, drift gate. CI - full suite.
- **Oracle:** the key the workflow passes to `shard_bound.py` and the field the contract declares resolve to the same string, and the utility returns a bare positive integer for it. It cannot settle whether the bound is the right size - row #7's reading does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The knob leaves the generic `run` block for the block holding the pair budget and the shard count its validator already reads. | Fowler |
| 2 | A straight rename in one commit. This is a config knob this repository solely writes, with one config file and one fixture - expand-migrate-contract is for a payload an earlier run wrote. | Fowler |
| 3 | `run.shard_timeout_minutes`, the work job's bound, does not move and does not change meaning. | Fowler |
| 4 | ESCALATE: the knob and the workflow key that reads it land in one commit, or the workflow resolves no bound and the leg runs to the platform ceiling. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave it and let the second judge add a sibling | The first knob stays misnamed and the validator keeps asserting something false about it | Nothing now, and two timeouts neither of which says which judge it bounds | Fowler |
| 2 | One generic leg timeout for every judge | A judge making 30 calls and one making 400 do not share a bound | One field, and a bound sized for the slowest applied to the fastest | Carmack |

---

### Row #7 - The measured judge call replaces the derived one

- **Scope:** every surface quoting a per-call judge cost derived from a tokens-a-second figure carries the measured reading instead, and that reading gets its own benchmark page.
- **Files touched:**
  - `config/idhazh.json`
  - `backend/idhazh/contracts/knobs/run.py`
  - `backend/idhazh/contracts/knobs/placement.py`
  - `.github/workflows/llm-council.yml`
  - `docs/concepts/pipeline-loop.md`
  - `docs/reference/benchmarks/what-a-judge-call-costs.md` (new)
  - `TODO/20260920-a-second-judge-in-the-council-handover.md`
  - `schemas/app-config.schema.json` (generated)
  - `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - contract export, drift gate, `python backend/utilities/doc_load.py --changed` over the touched pages. CI - full suite.
- **Oracle:** the page's figures reproduce by re-running its stated arithmetic over the committed scored-pairs file it names. It cannot settle whether one night's 82 pairs represent a 200-pair cap - the page states the sample size beside every figure and labels the cap figure an extrapolation.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The reading is 94.53 s a pair - min 72.80, max 110.98, n = 82, run `2026-09-18-35339202390`, stock `ubuntu-latest`, `Qwen3.5-9B-Q4_K_M`. Per call that is 47.3 s against 77.6 s derived, so the derived figure was 1.64x conservative. | Carmack |
| 2 | A new reading replaces the old rather than sitting beside it. Git holds what the figure used to say. | Guardrail #10 |
| 3 | `SECONDS_A_CALL` in `placement.py` carries a comment promising a reading would replace it. That promise is now payable and the comment goes with the value. | Carmack |
| 4 | The page is named for what it measured and nothing else; a re-run replaces it rather than adding a second page. | AGENTS.md |
| 5 | The handover's "the council has never run" line is false as of 2026-09-18 and is corrected in the same pass, along with the cost arithmetic that rests on it. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the conservative figure as a safety margin | An unlabelled margin is a wrong number, and it is the number sizing the second judge's budget | Nothing to take, and every later budget decision inherits a 1.64x error | Carmack |
| 2 | Wait for a 200-pair night before writing the page | The cap has never run and nothing schedules it; 82 pairs over four legs is a real sample with a stated size | One scheduled run at the cap | Carmack |

---

### Row #8 - Thinking is asserted off and the decode is stamped

- **Scope:** a judge call refuses to run against a model entry that opens a thinking channel, and the sampler settings that decided a verdict are folded into the decode digest the stamp carries.
- **Files touched:**
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/similarity/prompt.py`
  - `backend/idhazh/similarity/stamps.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/fixtures/`
- **Acceptance gates:** local - the similarity test modules, ruff, mypy. CI - full suite.
- **Oracle:** a canary drives a judge call against a model entry declaring a thinking close and asserts the call is refused rather than silently rendering a reasoning opener; a second asserts the decode digest changes when the judge temperature changes and not otherwise. It cannot settle what a live model does - a recorded completion proves the pipeline's behaviour on that fixture and nothing about the weights.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Three of the five registry entries declare a non-null thinking close; the active entry does not, so the committed rows are clean. The guard is a precondition, not a property of today's config. | Andre |
| 2 | Refuse the call rather than record the flag. The grammar would force a verdict token where the model meant to start reasoning, the reply would still parse, and the margin would describe a reasoning channel with nothing saying so. | Andre |
| 3 | The decode digest covers temperature, top-p, seed, prediction length and whether thinking was open - the settings that change what a verdict means. | Andre |
| 4 | The space-trap guard and the encode-in-position helper move from `similarity/prompt.py` into the model layer, because every judge needs them and only one has them. | Fowler |
| 5 | This row computes the digest; row #10 puts it on the row. Reader before writer. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Record the thinking flag without refusing | A recorded defect is still a defect, and the verdicts are unusable either way | One column, and a night of judging to discard when it fires | Andre |
| 2 | Pin the sampler in the model entry and delete the tuning override | The override exists for a reason and removing it is a separate argument; stamping makes either choice legible | The knob deleted and every judge taking the summariser's temperature | Andre |
| 3 | Assert thinking off in the prompt wording | Prompt wording is not a control (Guardrail #11), and a template cannot close a channel the server opened | Nothing, and a guard that reads as one without being one | Andre |

---

### Row #9 - The four verbs name their work

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
- **Oracle:** the `STAGES` tuple and the verbs the workflow files spell are compared name for name by the workflow harness, and every `ServerJob` value resolves to a job id present in a workflow file. It cannot settle whether the new names are better - decision 1 is the owner ruling.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `judge-draw` -> `pick-item-pairs`, `judge-shard` -> `judge-item-pairs`, `judge-fold` -> `count-verdicts`, `judge-fit` -> `set-merge-line`. | Owner, 2026-09-20 |
| 2 | A verb names its subject, and nothing is named `judge-<step>` again. That is what lets the summary-quality judge take `pick-summaries`, `score-summaries` and `count-scores` without colliding. | Fowler |
| 3 | `set-merge-line` rather than `set-threshold`: a second judge also sets a threshold, and a verb naming no subject cannot say which. | Owner, 2026-09-20 |
| 4 | A judge whose emitted token is the answer takes the stem `judge-`; one whose token is discarded and whose distribution is the answer takes `score-`. Different instruments, different stems. | Andre |
| 5 | The workflow job ids move with the verbs - `draw` becomes `pick`, `fold` becomes `tally` - because `ServerJob` values are job ids and row #3 already added them. | Fowler |
| 6 | The `judge-` grouping in `--help` is given up. The workflow and the owning doc group the four instead. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | `idhazh judge <name> <verb>` | The router would hold a name registry, which section 1a forbids, and only one of four steps is shared | A dispatch table in the router and a judges package with no reason to exist | Fowler |
| 2 | Keep `judge-` as a family prefix | The prefix is what ties the verbs to one loop, which is the defect | Nothing, and the second judge's verbs either lie or break the pattern | Fowler |
| 3 | Rename the verbs but leave the modules | `judge_draw.py` defining `pick-item-pairs` is the drift the router rule exists to stop | A smaller diff, and a file disagreeing with its only export | Fowler |

---

### Row #10 - The leg fills the stamp

- **Scope:** the judging leg records, per reading, which judge read it, under which sampler, whether the grammar applied and what the first-token distribution was.
- **Files touched:**
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/similarity/stamps.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/fixtures/`
- **Acceptance gates:** local - the similarity test modules, ruff, mypy. CI - full suite.
- **Oracle:** a reading driven from a recorded completion produces a row whose `first_token_margin` is recomputable from its own `first_token_probabilities`, so the derived scalar and the stored vector cannot disagree. It cannot settle whether the probabilities the server returned are the model's true distribution.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `grammar_applied` is recorded as a passing value, not only raised as an exception. Today a failure writes no row and an operator reading absence cannot tell it from a leg that never started. | Andre |
| 2 | The stored vector is the authority and the margin is derived from it, so the two can be checked against each other rather than trusted separately. | Andre |
| 3 | The leg is the only writer of the stamp. The draw writes verdict columns empty and must not invent an instrument for a reading nobody took. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Have the draw pre-fill `judge_id` | The draw does not know which judge will read the row, and a guessed instrument is worse than an absent one | One fewer write, and a stamp that can be wrong | Fowler |
| 2 | Keep raising on a grammar failure and record nothing | Absence then means two different things and an operator cannot separate them | Nothing, and a failure mode that reads as a missing leg | Andre |

---

### Row #11 - The leg writes its row and opens its spans

- **Scope:** each judging leg writes one segment row describing what it did and how its instrument behaved, opens a span per model call, and the compaction drains both.
- **Files touched:**
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/telemetry/spans.py`
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/fixtures/`
- **Acceptance gates:** local - the similarity and telemetry test modules, ruff, mypy. CI - full suite.
- **Oracle:** a leg's row reconciles against the verdict rows that leg wrote - owned equals judged plus unjudged, usable is a subset of judged, and the median margin on the row is the median of the margins in those rows. It cannot settle whether the machine readings are accurate; the sampler owns that and plan 37 is changing it.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The leg row is leg-grain because no per-reading row can hold it. Server start time, whether the bound was reached and how many rows were owned are facts about the leg, not about a pair. | Andre |
| 2 | A span is opened per call, not per pair. A pair is two calls in opposite orders and averaging them hides the order that was slow. | Andre |
| 3 | Span names come from the existing closed set, so one rollup groups a judge call and a summarise call by the same vocabulary. | Fowler |
| 4 | The leg writes its segment even when it judged nothing, so a leg that started and did no work is distinguishable from a leg that never started. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Commit a per-call trace file as the digest run does | Per-call JSONL for 400 calls a night, when the per-reading stamp already carries what a trace would | Storage growing every run for a question the stamp answers | Fowler |
| 2 | Skip spans and rely on the leg row's totals | The totals cannot separate a slow server start from slow decoding, which is the question a slow leg raises | One less write on the hot path, and no way to attribute a slow leg | Carmack |
| 3 | Write the leg row from the fold instead | The fold cannot see what the leg's machine did, and a leg that died wrote nothing for the fold to read | One writer instead of four, and nothing recorded for the failure case | Andre |

---

### Row #12 - The council records the machine it ran on

- **Scope:** the judging legs write a host fingerprint and a job clock, and the fold drains every segment the legs left - so a slow leg can be explained rather than guessed at.
- **Files touched:**
  - `.github/workflows/llm-council.yml`
  - `backend/tests/workflows/test_llm_council_workflow.py`
- **Acceptance gates:** local - the workflow harness. CI - full suite.
- **Oracle:** the workflow test asserts every job writing a segment is followed by a job running the compaction that drains it, and that the fingerprint step precedes the first model call. It cannot settle whether the readings are accurate on a runner.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The legs keep the host fingerprint, the job clock, spans and the segment compaction, and take nothing else from the digest workflow. | Owner, 2026-09-20 |
| 2 | Dropped deliberately: the item-health ledger, feed health, the day census, committed per-item traces, day metrics and counterfactual scores. A judge has no items with terminal states, reads no feeds and publishes no day. | Owner, 2026-09-20 |
| 3 | The host fingerprint is reused exactly as it stands - no new schema, no new columns. The leg runs the verb that already exists. | Carmack |
| 4 | This row assumes plan 37's corrected sampler and does not wait for it. The steps are the same either way; what plan 37 changes is what the sampler counts. | Owner, 2026-09-20 |
| 5 | The fingerprint is taken before the first model call, so facts that cannot change inside a job do not differ between two readings of one leg. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Import the digest workflow's observability set wholesale | Half of it answers questions a judge does not have, and every step is time on a leg already holding a server up | A shorter row, and six stores that stay empty or carry meaningless rows | Owner |
| 2 | Wait for plan 37 to land | The steps are identical either way; only the sampler's arithmetic differs | A serialized dependency for no change in what this row writes | Owner |
| 3 | Build a new shipping path for judge telemetry | The segment store and the compaction verb already do this and already drain six ledgers | A second transit mechanism to keep in step with the first | Fowler |

---

### Row #13 - The store groups under the judge that fills it

- **Scope:** the committed same-story tree moves under the judge slug that produced it, so a second judge's stores sit beside it rather than inside a name describing only the first.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `state/story-similarity/` -> `state/content-similarity-judge/`
  - `frontend/` readers of the moved paths
  - `docs/reference/repository-layout.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/architecture/contracts/schemas.md`
  - `backend/tests/`
- **Acceptance gates:** local - the ledger and similarity test modules, the frontend build, `doc_load.py --changed`. CI - full suite, plus the published-site smoke.
- **Oracle:** every file under the old tree has exactly one counterpart under the new one with identical bytes, and no reader in `backend/` or `frontend/` resolves a path under the old name. It cannot settle whether a clone taken before the move still resolves - it does not, and the move is announced rather than migrated.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge slug is the group, so the store a judge produces sits under the judge's name. | Owner, 2026-09-20 |
| 2 | The stores under it keep their names - scored pairs, fitted thresholds, the distribution record, the holdout and the archive all move unchanged. | Fowler |
| 3 | A rename of the tree, not a rewrite of its rows. No row's contents change here. | Fowler |
| 4 | `git mv` per file, so history follows and the move is one reviewable rename rather than a delete and an add. | Fowler |
| 5 | ESCALATE: this moves committed data. The path map is signed off before any file moves. | Section 6 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the tree and put only new judges under slugs | Two organising schemes in one directory, and the oldest judge looks like the exception | Nothing to move, and a layout no reader can infer a rule from | Fowler |
| 2 | Keep `story-similarity` and add the slug as a column | The column already exists on the row; the question is where a second judge's stores go | A flat directory whose growth nobody can predict | Owner |
| 3 | Leave a symlink or a compatibility path | A second name for one store, which is the drift the closed sets exist to stop | One path that works and one that used to | Fowler |

---

### Row #14 - Where the judge stands against its holdout

- **Scope:** the judge is scored against the labelled holdout and the four counts are committed, with the negative population beside them so a thin holdout cannot pass as a measurement.
- **Files touched:**
  - `backend/idhazh/similarity/holdout.py` (new)
  - `backend/idhazh/stages/score_holdout.py` (new)
  - `backend/idhazh/cli.py`
  - `backend/idhazh/ledger.py`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/how-to/label-the-similarity-holdout.md`
  - `backend/tests/`
- **Acceptance gates:** local - the similarity and contract test modules, ruff, mypy, `doc_load.py --changed`. CI - full suite.
- **Oracle:** the four cells plus the unresolved count sum to the number of labelled pairs the holdout carries, so nothing is dropped between the file and the row. It cannot settle whether the judge is good: with four labelled two-story pairs, no rate computed from these cells is a measurement, and decision 4 is what stops one being published.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The row records four plain counts: joined and truly one story, joined and truly two, left apart and truly one, left apart and truly two. | Editor |
| 2 | A false merge shows two stories as one, so the reader never sees the second - the invisible direction, and the one the fit damps. A missed merge shows one story twice, which the reader sees and dismisses. Both are named rather than collapsed into a score. | Editor |
| 3 | No rate is stored. Every rate is derived at read time with the negative population in view. | Guardrail #10 |
| 4 | ESCALATE: if the negative count is still four, commit the counts and refuse the rate. | Owner, 2026-09-20 |
| 5 | The labels interleave - one story at 0.9406, two stories at 0.9407, one story at 0.9409 - so no single threshold separates the populations. This row measures where the line stands; it does not assert a perfect line exists. | Andre |
| 6 | The verb is `score-holdout`, following row #9's rule: a scorer takes the `score-` stem. | Fowler |
| 7 | A person types this verb; nothing in the daily pipeline calls it. The holdout's authority comes from being labelled by something the fit does not consume, and a scheduled self-scoring spends model time nightly for a number that only moves when the instrument does. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Publish one accuracy figure | With 196 of 200 pairs on one side, always answering "one story" scores 98 percent and measures nothing | One column, and a number that looks excellent while the judge is useless | Andre |
| 2 | Have the judge label more holdout pairs to widen the negatives | The holdout's authority comes from being labelled by something the fit does not consume | The floor becomes a copy of the line it polices | Andre |
| 3 | Score against the holdout on every run | It measures the instrument, so it is taken when the instrument or the line moves, not nightly | Model time every night for a number that changes when a fingerprint changes | Carmack |

---

### Row #15 - The model block becomes one composite action

- **Scope:** the weights cache, the fetch, the checksum verify, the server start and the health probe become one composite action, replacing the copies that already exist.
- **Files touched:**
  - `.github/actions/model-server/action.yml` (new)
  - `.github/workflows/llm-council.yml`
  - `.github/workflows/digest.yml`
  - `.github/workflows/measure.yml`
  - `backend/tests/workflows/`
- **Acceptance gates:** local - the workflow harness across every touched file. CI - full suite.
- **Oracle:** the cache key the action emits is character-identical to the key the digest work job writes today, proving the restore still adds no bytes to the allowance. It cannot settle whether a restore succeeds on a runner - a miss costs a re-download and cannot fail a run.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The block is duplicated six to seven times today, before any second judge. The repository already carries a composite action whose own comment records that this class of drift has happened twice. | Carmack |
| 2 | A composite action carries no job-level knob, so the leg bound, the matrix and the runner label stay in the workflow. | Carmack |
| 3 | The cache-hit output is declared explicitly, or the condition on the fetch step silently stops working. | Carmack |
| 4 | The step proving the running server serves the entry the rows will name moves into the action - a judge stamping a model alias the server is not serving is the failure it exists to catch. | Carmack |
| 5 | Ships in the same pull request as row #12, because both are one pass over the council workflow. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A callable workflow instead | Its only unique benefit is a per-caller runner label and permission set, and no judge needs either | A restructure for a differentiation nothing uses | Carmack |
| 2 | Leave the duplication | Six copies that drift the day one is edited, which has happened twice here | Nothing now, and the next judge makes it eight | Carmack |
| 3 | Extract the checkout and install steps too | Three lines behind an indirection costing more to read than the lines it hides | A larger action and no drift it prevents | Carmack |
