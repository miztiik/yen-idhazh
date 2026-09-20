# Name the judges, and give them an instrument

**Last Updated**: 2026-09-20

**Level**: 5 (a persisted contract with committed rows, and a committed state tree that moves)

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

## Section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Four CLI verbs name their mechanism instead of their work, a second judge lands soon that shares one of their four steps, and the judge legs record nothing about the machine they ran on. |
| Hard scope - in | Rename the four same-story verbs and their modules; fix the verdict upload that a cancelled leg skips; replace the derived per-call cost with the measured one; move the leg-timeout knob to the block its validator reads; assert thinking off and stamp the decode; embed the per-reading judge stamp; open `ServerJob` and `SegmentLedger` to judges; mint the judge-leg row; wire host fingerprint, job clock, spans and compaction into the council; group the committed store under the judge slug; record the judge against its holdout; lift the model block into one composite action. |
| Hard scope - out | See the table below. |
| ESCALATE triggers | (1) Row #6 adds fields to a contract that already has 82 committed rows - pause for sign-off on the read-side migration before writing it. (2) Row #11 moves a committed state tree - pause for sign-off on the path map before any file moves. (3) Any row that would raise a runner budget figure (Guardrail #2). (4) Row #12: if the holdout still carries 4 labelled two-story pairs, publish the counts and refuse the rate - surface rather than print a percentage that one flip moves 25 points. |
| Chosen strategy | Share the model call, not the judge - one constrained-decode layer and a per-reading stamp each judge embeds in its own row, with per-judge packages, contracts and stores above it. Fowler, Carmack and Andre in debate, owner ruling 2026-09-20. |
| Execution | `autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4.` Rows #1 through #4 and #7, #9, #10, #13 all touch `.github/workflows/llm-council.yml`, so the real fan-out is narrower than the group letters suggest; the dispatcher computes readiness from `Files touched`, not from the letter. |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| A `Judge` base class, protocol or registry | Judge three duplicates judge one's stage shape, about 150 lines | A third judge that shares three of the four steps, rather than one |
| A second CLI level (`idhazh <loop> <verb>`) | The flat verb list grows from 25 to about 30 | The first time a flag's help text has to name which judge it belongs to |
| One workflow per judge | Every judge shares one cron, one concurrency group and one `runs-on`; a slow pair day delays the quality fold | A judge that needs different weights or a different cadence - which is the independent second-opinion judge |
| The independent second-opinion judge itself | The holdout stays labelled by something the fit consumes, so the floor cannot police the line | The six questions in `20260920-a-second-judge-in-the-council-handover.md` being answered |
| Promoting fluency to a publish gate | Nothing today - it is a drift monitor and feeds nothing | A measured injection delta on the score, not a shape assertion |
| Console panels for judge health | An operator reads the committed rows rather than a page | Plan 36 row #9, which owns `/console/judgement/` |
| Renaming `backend/var/judge/` | The scratch directory keeps a word that names one loop's draw | The parallel work already moving production artefacts out of the code tree |

## Section 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | A cancelled leg keeps the verdicts it paid for | - | A | PENDING | - | - | - |
| 2 | The measured judge call replaces the derived one | 1 | A | PENDING | - | - | - |
| 3 | The four verbs name their work | 2 | B | PENDING | - | - | - |
| 4 | The leg timeout moves to the block that validates it | 3 | B | PENDING | - | - | - |
| 5 | Thinking is asserted off and the decode is stamped | 3 | C | PENDING | - | - | - |
| 6 | The per-reading stamp is embedded in the pair row | 5 | C | PENDING | - | - | - |
| 7 | `ServerJob` admits the council's jobs | 4 | D | PENDING | - | - | - |
| 8 | The judge-leg row and its segment ledger | 7 | D | PENDING | - | - | - |
| 9 | The council records the machine it ran on | 8 | E | PENDING | - | - | - |
| 10 | The judge leg opens spans | 9 | E | PENDING | - | - | - |
| 11 | The committed store groups under the judge slug | 8 | F | PENDING | - | - | - |
| 12 | Where the judge stands against its holdout | 11 | F | PENDING | - | - | - |
| 13 | The model block becomes one composite action | 9 | G | PENDING | - | - | - |

---

### Row #1 - A cancelled leg keeps the verdicts it paid for

- **Scope:** the judging leg's verdict upload runs on a cancelled job, so a leg stopped by its own timeout no longer discards every verdict it already computed.
- **Files touched:**
  - `.github/workflows/llm-council.yml`
- **Acceptance gates:** local - the workflow harness test for this file. CI - full suite.
- **Oracle:** the workflow test asserts every `upload-artifact` step whose artifact a later job consumes carries a condition that survives cancellation. It cannot settle whether the artifact is complete: a leg killed mid-write uploads what it had, which is the intended trade.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The step gains a condition that runs on cancellation; the fold already tolerates a short leg by refusing to fold a partial day. | Carmack |
| 2 | The oracle is written over the file rather than over this one step, because the same omission has cost this repository work twice and fixing one step is not fixing the file. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Raise the leg timeout instead | A bound is a backstop, not a budget; a leg that overruns still loses its work | One knob edit, and the defect stays for the next overrun | Carmack |
| 2 | Have the leg upload incrementally | Four legs writing partial artifacts is a second consistency problem for a case that is already handled | An artifact-per-batch scheme and a fold that reassembles it | Carmack |

---

### Row #2 - The measured judge call replaces the derived one

- **Scope:** every surface quoting a per-call judge cost derived from a tokens-a-second figure carries the reading taken from the 82 committed pairs instead, and that reading gets its own benchmark page.
- **Files touched:**
  - `config/idhazh.json`
  - `backend/idhazh/contracts/knobs/run.py`
  - `backend/idhazh/contracts/knobs/placement.py`
  - `.github/workflows/llm-council.yml`
  - `docs/concepts/pipeline-loop.md`
  - `docs/reference/benchmarks/what-a-judge-call-costs.md` (new)
  - `schemas/app-config.schema.json` (generated)
  - `frontend/src/contracts/app-config.ts` (generated)
- **Acceptance gates:** local - the contract export, then the drift gate. CI - full suite.
- **Oracle:** the benchmark page's figures reproduce from `state/story-similarity/scored-pairs/2026/09/18.csv` by re-running the arithmetic in the page. It cannot settle whether one night's 82 pairs represent the 200-pair cap: the page states the sample size beside every figure and the cap is an extrapolation, labelled as one.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The reading is 94.53 s a pair - min 72.80, max 110.98, n = 82, run `2026-09-18-35339202390`, stock `ubuntu-latest`, `Qwen3.5-9B-Q4_K_M`. Per call that is 47.3 s against the 77.6 s derived, so the derived figure was 1.64x conservative. | Carmack |
| 2 | A new reading replaces the old one rather than sitting beside it; git holds what the figure used to say. | Guardrail #10 |
| 3 | `SECONDS_A_CALL` in `placement.py` carries a comment promising a reading would replace it. That promise is now payable and the comment goes with the value. | Carmack |
| 4 | The page is named for what it measured and nothing else, and a re-run replaces it rather than adding a second page. | AGENTS.md |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep the conservative figure as a safety margin | A margin nobody labelled is a wrong number, and it is the number sizing the second judge's budget | Nothing to take, and every later budget decision inherits a 1.64x error | Carmack |
| 2 | Wait for a full 200-pair night before writing the page | The cap has never run and may not for weeks; 82 pairs across four legs is a real sample with a stated size | One scheduled run at the cap, which nothing currently schedules | Carmack |

---

### Row #3 - The four verbs name their work

- **Scope:** the same-story verbs, their stage modules and their stage functions are renamed to say what they do rather than which mechanism they use, and the rule that produced the names is written where the next verb author reads it.
- **Files touched:**
  - `backend/idhazh/cli.py`
  - `backend/idhazh/stages/judge_draw.py` -> `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/stages/judge_shard.py` -> `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/stages/judge_fold.py` -> `backend/idhazh/stages/count_verdicts.py`
  - `backend/idhazh/stages/judge_fit.py` -> `backend/idhazh/stages/set_merge_line.py`
  - `backend/idhazh/similarity/fit.py`, `backend/idhazh/similarity/fold.py` (docstring references)
  - `backend/tests/test_similarity_draw.py`, `backend/tests/test_similarity_fit.py`, `backend/tests/test_similarity_judge.py`
  - `.github/workflows/llm-council.yml`
  - `docs/how-to/label-the-similarity-holdout.md`
  - `docs/reference/repository-layout.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
- **Acceptance gates:** local - the changed-test selector over the similarity modules, plus ruff and mypy. CI - full suite.
- **Oracle:** the `STAGES` tuple and the verbs the workflow files spell are compared name for name by the existing workflow harness, so a verb renamed on one side and not the other fails before a run does. It cannot settle whether the new names are better - that is the owner ruling in decision 1.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | `judge-draw` -> `pick-item-pairs`, `judge-shard` -> `judge-item-pairs`, `judge-fold` -> `count-verdicts`, `judge-fit` -> `set-merge-line`. | Owner, 2026-09-20 |
| 2 | The rule is that a verb names its subject, and nothing is named `judge-<step>` again. Three of the four names carry their subject, which is what lets a second judge take `pick-summaries`, `score-summaries` and `count-scores` without colliding. | Fowler |
| 3 | `set-merge-line` rather than `set-threshold`, because a second judge also sets a threshold and a verb naming no subject cannot say which. | Owner, 2026-09-20 |
| 4 | A judge whose emitted token is the answer takes the stem `judge-`; one whose token is discarded and whose distribution is the answer takes `score-`. They are different instruments and a shared stem would say they are not. | Andre |
| 5 | The `judge-` prefix as a grouping device is dropped. The four no longer sort together under `--help`; the workflow and the owning doc group them instead. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | `idhazh judge <name> <verb>`, a two-level namespace | The router would hold a name registry, which section 1a forbids; and only one of the four steps is shared with the second judge | A dispatch table in the router and a judges package that has no reason to exist | Fowler |
| 2 | Keep `judge-` as a family prefix on all four | It is the prefix that ties the verbs to one loop, which is the defect being fixed | Nothing to take, and the second judge's verbs then either lie or break the pattern | Fowler |
| 3 | Rename the CLI verbs but leave the modules | `judge_draw.py` would define `pick-item-pairs`, which is the drift the router rule exists to stop | A smaller diff now, and a file whose name disagrees with its only export | Fowler |

---

### Row #4 - The leg timeout moves to the block that validates it

- **Scope:** the judging leg's timeout knob is renamed and moved beside the two numbers its own validator reads, so a generic name is no longer bound by pair-specific arithmetic.
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
- **Acceptance gates:** local - contract export then the drift gate, plus the two named test modules. CI - full suite.
- **Oracle:** the workflow test's timeout key and the contract field resolve to the same string, and `shard_bound.py` returns an integer for it. It cannot settle whether the bound is the right size - row #2's reading does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The knob moves out of the generic `run` block into the block holding the pair budget and the shard count that its validator already reads. | Fowler |
| 2 | This is a config knob this repository is the sole writer of, with one config file and one fixture, so it is a straight rename in one commit. Expand-migrate-contract is for a payload an earlier run wrote, not for a knob. | Fowler |
| 3 | `run.shard_timeout_minutes` - the work job's own bound - does not move and does not change meaning. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave it and let the second judge add a sibling | The first knob stays misnamed for ever and the validator keeps asserting something false about it | Nothing now, and two timeouts neither of which says which judge it bounds | Fowler |
| 2 | One generic leg timeout for every judge | A judge making 30 calls and a judge making 400 do not share a bound | One field, and a bound sized for the slowest judge applied to the fastest | Carmack |

---

### Row #5 - Thinking is asserted off and the decode is stamped

- **Scope:** a judge call asserts the thinking channel is closed rather than inheriting whatever the active model entry declares, and the sampler settings that decided a verdict are recorded as a digest.
- **Files touched:**
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/similarity/prompt.py`
  - `backend/idhazh/similarity/stamps.py`
  - `backend/idhazh/contracts/` (the decode digest shape)
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/fixtures/` (a recorded completion for the canary)
- **Acceptance gates:** local - the similarity test modules plus ruff and mypy. CI - full suite.
- **Oracle:** a canary drives a judge call against a model entry that declares a thinking channel and asserts the call is refused rather than silently rendering a reasoning opener. It cannot settle what a live model does - a recorded completion proves the pipeline's behaviour on that fixture and nothing about the weights.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Three of the five registry entries declare a non-null thinking close. The active entry does not, so the 82 committed rows are clean - but the guard is a precondition, not a property of today's config. | Andre |
| 2 | The grammar forces a verdict token at the position a thinking model meant to start reasoning. The reply still parses and the first-token margin then describes a reasoning channel with nothing on the row saying so. | Andre |
| 3 | The judge temperature is read from a tuning knob that overrides the model entry, and the row records the model but not the decode. The digest covers temperature, top-p, seed, prediction length and the thinking flag. | Andre |
| 4 | The space-trap guard and the encode-in-position helper move out of the similarity package into the model layer, because every judge needs them and only one has them. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Record the thinking flag without refusing the call | A recorded defect is still a defect, and the verdicts it produced are unusable either way | One column, and a night of judging to discard when it fires | Andre |
| 2 | Pin the sampler in the model entry instead of stamping it | The override exists for a reason and removing it is a separate argument; stamping is what makes either choice legible | The tuning knob deleted and every judge taking the summariser's temperature | Andre |

---

### Row #6 - The per-reading stamp is embedded in the pair row

- **Scope:** every judged reading carries the instrument that produced it, embedded in the judge's own row rather than joined from a second table.
- **Files touched:**
  - `backend/idhazh/contracts/story_similarity_pair.py`
  - `backend/idhazh/contracts/` (the shared stamp model)
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/stages/count_verdicts.py`
  - `backend/idhazh/ledger.py` (the read-side migration)
  - `schemas/story-similarity-pair.schema.json` (generated)
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/fixtures/`
- **Acceptance gates:** local - the similarity and contract test modules, contract export, drift gate. CI - full suite.
- **Oracle:** the 82 committed rows written before this change still load through the migrated reader, and a row written after it round-trips through the contract unchanged. It cannot settle whether the new fields are the right ones - decision 2 names why each is on the row.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The stamp is embedded, not tabled. A separate health table needs a join key and a second write, and a run that dies between the two leaves a row with no stamp. | Andre |
| 2 | The stamp carries: which instrument wrote the row, the weights, the decode digest from row #5, the prompt and grammar digests, whether the grammar applied, the full first-token distribution, and the decode seconds. The full distribution rather than a derived scalar is what lets a scoring fix be re-applied without re-spending model time. | Andre |
| 3 | The verdict-shaped fields stay off any shared shape. Agreement between two readings is a position-bias control and means nothing for a judge whose input has no order. | Andre |
| 4 | Whether the grammar applied is recorded as a passing value, not only as an exception. Today a failed leg writes no row, and an operator reading absence cannot tell it from a leg that never started. | Andre |
| 5 | ESCALATE: 82 committed rows exist, so the read-side migration ships in the same commit and pauses for sign-off first. | Section 11 |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One union verdict row across all judges | Half the columns would be null per judge, and the agreement field has no honest meaning for a rated scorer | A discriminator column and a contract that says two instruments are one | Fowler |
| 2 | A separate judge-health table joined on the pair key | Two writes, a join key, and a row with no stamp when a run dies between them | A second store and a join every reader pays | Andre |
| 3 | Store only the top-two token gap, as today | A scoring-formula fix then costs a re-run of the model time that produced the rows | Nothing now; a night of model time later | Andre |

---

### Row #7 - `ServerJob` admits the council's jobs

- **Scope:** the closed set of jobs that may appear in a segment filename gains the council's jobs, and the workflow's job ids are renamed to match the verbs they now run.
- **Files touched:**
  - `backend/idhazh/contracts/base.py`
  - `.github/workflows/llm-council.yml`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `schemas/` (every generated schema listing the enum)
- **Acceptance gates:** local - the workflow harness plus contract export and drift gate. CI - full suite.
- **Oracle:** every job id in the council workflow resolves to a member of the enum, and every member names a job id that exists in some workflow file. It cannot settle whether a job writes a segment - row #8 does that.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The enum's contract is that a value is a job's own id in its workflow file, lowercase, so a reader goes from a row to the steps that wrote it with no lookup table. The job ids and the enum are renamed together or the contract is broken. | Fowler |
| 2 | The job ids follow the verbs: the draw job becomes the pick job, the fold job becomes the tally job. The judging job keeps its id, because a judge dimension on the matrix makes the judge a column rather than a job. | Carmack |
| 3 | Adding a member is additive on an enum that committed manifests already read, so no manifest needs migrating. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A free-text job column for judges | The closed set exists to stop a typo becoming a job nobody can group by | One less enum member and a column that silently splits on a typo | Fowler |
| 2 | One `council` member covering all three jobs | Three jobs with different failure modes would share one name, and a segment filename could not say which wrote it | One member instead of three, and a segment nobody can attribute | Carmack |

---

### Row #8 - The judge-leg row and its segment ledger

- **Scope:** one row per judge per leg, shipped through the existing segment store, recording the funnel through the judge and the health of the instrument that walked it.
- **Files touched:**
  - `backend/idhazh/contracts/judge_leg_row.py` (new)
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `schemas/judge-leg-row.schema.json` (generated)
  - `backend/tests/contracts/`
  - `backend/tests/fixtures/`
- **Acceptance gates:** local - the contract test modules, contract export, drift gate. CI - full suite.
- **Oracle:** a leg's row totals reconcile against the verdict rows that leg wrote - owned equals judged plus unjudged, usable is a subset of judged. It cannot settle whether the leg's readings are true, only that the two writes agree.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The store is `state/<judge-slug>/shards/<YYYY>/<MM>/<DD>.csv`. The judge slug is the group and each judge owns as many day-sharded stores as it has questions, which is the shape `story-similarity` already uses. | Owner, 2026-09-20 |
| 2 | No `judges/` prefix. The day inventory globs two directory levels and reports success while seeing nothing deeper, so a prefix would make the store silently invisible to `idhazh telemetry show`. | Fowler |
| 3 | The judge slugs are `content-similarity-judge` and `summary-content-quality-judge`. | Owner, 2026-09-20 |
| 4 | The row is leg-grain because no per-reading row can hold it. How long the server took to start, whether the leg neared its bound and how many rows it owned are facts about the leg, not about a pair. | Andre |
| 5 | The row carries the funnel (owned, judged, usable), the instrument's health (grammar failures, disagreement rate, unclear share, median first-token margin), the model and decode fingerprint, and the cost (decode seconds, server start seconds, whether the bound was reached). | Andre |
| 6 | The ledger joins the segment set in this row, which is the row that moves its writer - never before it. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | `state/judges/<slug>/<store>/<date>` | Four levels; the inventory reads two and would report success while listing nothing | A widened glob, and every existing store one level deeper than it needs | Fowler |
| 2 | Put the leg figures on the existing work-shard machine row | That row is one work shard of one digest run, and a judge leg is neither | A discriminator column on a row that would then describe two unrelated jobs | Carmack |
| 3 | Derive the funnel at read time from the verdict rows | A leg that wrote no verdicts is then indistinguishable from a leg that never ran | Nothing to store, and the one failure mode the row exists to show | Andre |

---

### Row #9 - The council records the machine it ran on

- **Scope:** the judging legs write a host fingerprint, a job clock and their leg rows, and the fold drains the segments - so a slow leg can be explained rather than guessed at.
- **Files touched:**
  - `.github/workflows/llm-council.yml`
  - `backend/tests/workflows/test_llm_council_workflow.py`
- **Acceptance gates:** local - the workflow harness. CI - full suite.
- **Oracle:** the workflow test asserts that every job writing a segment also runs the compaction that drains it, and that the fingerprint step precedes the first model call. It cannot settle whether the readings are accurate on a runner - the sampler owns that, and plan 37 is changing it.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge legs keep the host fingerprint, the job clock, spans and the segment compaction, and take nothing else from the digest workflow. | Owner, 2026-09-20 |
| 2 | Dropped deliberately: the item-health ledger, feed health, the day census, committed per-item traces, day metrics and counterfactual scores. A judge has no items with terminal states, reads no feeds and publishes no day, so each of those answers nothing here. | Owner, 2026-09-20 |
| 3 | The host fingerprint is reused exactly as it stands - no new schema, no new columns. The leg runs the verb that already exists. | Carmack |
| 4 | This row assumes plan 37's corrected sampler and does not wait for it. The steps this row adds are the same steps either way; what plan 37 changes is what the sampler counts. | Owner, 2026-09-20 |
| 5 | The fingerprint is taken before the first model call, because the facts that cannot change inside a job must not differ between two readings of one leg. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Import the digest workflow's observability set wholesale | Half of it answers questions a judge does not have, and every step is time on a leg that already holds a server up | A shorter row now, and six stores that stay empty or carry meaningless rows | Owner |
| 2 | Wait for plan 37 to land first | The steps are identical either way; only the sampler's arithmetic differs | A serialized dependency for no change in what this row writes | Owner |
| 3 | Build a new shipping path for judge telemetry | The segment store and the compaction verb already do exactly this, and are already draining six ledgers | A second transit mechanism to keep in step with the first | Fowler |

---

### Row #10 - The judge leg opens spans

- **Scope:** the judging leg opens spans around the server start and each model call, so decode timing and startup cost reach the rollup the pipeline already keeps.
- **Files touched:**
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/telemetry/spans.py`
  - `.github/workflows/llm-council.yml`
  - `backend/tests/`
- **Acceptance gates:** local - the similarity test modules and the telemetry test modules. CI - full suite.
- **Oracle:** the span tree for one leg totals to that leg's recorded decode seconds within the sampler's own resolution. It cannot settle wall-clock attribution below that resolution, and the tolerance is stated rather than inferred.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Spans and the rollup are in scope. | Owner, 2026-09-20 |
| 2 | The span names come from the existing closed set rather than new strings, so one rollup groups a judge call and a summarise call by the same vocabulary. | Fowler |
| 3 | A span is opened per call, not per pair. A pair is two calls in opposite orders and averaging them hides the order that was slow. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Skip spans and rely on the leg row's total | The total cannot separate a slow server start from slow decoding, which is the question a slow leg raises | One less write on the hot path, and no way to attribute a slow leg | Carmack |
| 2 | Commit a per-call trace file as the digest run does | Per-call JSONL for 400 calls a night, when the per-reading stamp already carries what a trace would | Storage that grows with every run for a question the stamp answers | Fowler |

---

### Row #11 - The committed store groups under the judge slug

- **Scope:** the committed same-story tree moves under the judge slug that produced it, so a second judge's stores sit beside it rather than inside a name that describes only the first.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `state/story-similarity/` -> `state/content-similarity-judge/`
  - `frontend/` readers of the moved paths
  - `docs/reference/repository-layout.md`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `backend/tests/`
- **Acceptance gates:** local - the ledger and similarity test modules, plus the frontend build. CI - full suite, plus the published-site smoke.
- **Oracle:** every file under the old tree has exactly one counterpart under the new one with identical bytes, and no reader resolves a path under the old name. It cannot settle whether an external clone taken before the move still resolves - it does not, and the move is announced rather than migrated.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The judge slug is the group, so the store that a judge produces sits under the judge's name. | Owner, 2026-09-20 |
| 2 | The stores under it keep their names - the scored pairs, the fitted thresholds, the distribution record, the holdout and the archive all move unchanged. | Fowler |
| 3 | ESCALATE: this moves committed data. The path map is signed off before any file moves. | Section 6 |
| 4 | The move is a rename of the tree, not a rewrite of its rows. No row's contents change in this row. | Fowler |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave the tree and put only new judges under slugs | Two organising schemes in one directory, and the oldest judge is the one that looks like an exception | Nothing to move, and a layout no reader can infer a rule from | Fowler |
| 2 | Keep `story-similarity` as the name and add the slug as a column | The column already exists on the row; the question here is where a second judge's stores go | A flat directory whose growth nobody can predict | Owner |

---

### Row #12 - Where the judge stands against its holdout

- **Scope:** the judge is scored against the labelled holdout and the result is committed, with the counts beside every rate so a thin negative population cannot pass as a measurement.
- **Files touched:**
  - `backend/idhazh/contracts/holdout_score_row.py` (new)
  - `backend/idhazh/similarity/` (the scoring arithmetic)
  - `backend/idhazh/ledger.py`
  - `schemas/holdout-score-row.schema.json` (generated)
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `backend/tests/`
- **Acceptance gates:** local - the similarity and contract test modules, contract export, drift gate. CI - full suite.
- **Oracle:** the four cells of the matrix sum to the number of holdout pairs the judge could resolve, and the unresolvable pairs are reported rather than dropped. It cannot settle whether the judge is good: with four labelled two-story pairs, the false-merge rate is not a measurement, and decision 3 is what stops it being printed as one.
- **Decisions:**

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The row records, in plain words: how many pairs the line joined that are truly one story, how many it joined that are not, how many it left apart that are one story, and how many it correctly left apart. | Editor |
| 2 | A false merge shows two stories as one, so the reader never sees the second - that is the invisible direction and it is the one the fit damps. A missed merge shows one story twice, which the reader sees and can dismiss. The row names both rather than collapsing them into one score. | Editor |
| 3 | Every rate carries its denominator on the same row. The holdout holds 196 one-story and 4 two-story pairs, so one flip moves the false-merge rate by 25 points. A rate over four negatives is reported with the four beside it or not at all. | Guardrail #10 |
| 4 | ESCALATE: if the negative count is still four when this row runs, publish the counts and refuse the rate. | Owner, 2026-09-20 |
| 5 | The labels interleave - a one-story pair at 0.9406, a two-story pair at 0.9407, a one-story pair at 0.9409 - so no single threshold separates the populations. The row measures where the line stands; it does not assert a line exists that would score perfectly. | Andre |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Publish one accuracy figure | With 196 of 200 pairs on one side, always answering "one story" scores 98 percent and measures nothing | One column, and a number that looks excellent while the judge is useless | Andre |
| 2 | Have the judge label more holdout pairs to widen the negatives | The holdout's authority comes from being labelled by something the fit does not consume | The floor becomes a copy of the line it polices | Andre |
| 3 | Score against the holdout on every run | It is a measurement of the instrument, taken when the instrument or the line moves, not a daily reading | Model time every night for a number that changes when a fingerprint changes | Carmack |

---

### Row #13 - The model block becomes one composite action

- **Scope:** the weights cache, the fetch, the checksum verify, the server start and the health probe become one composite action, replacing the copies that already exist across the workflows.
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
| 4 | The step that proves the running server is serving the entry the rows will name moves into the action, because a judge stamping a model alias the server is not serving is the failure the step exists to catch. | Carmack |

- **Rejected alternatives:**

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A callable workflow instead | Its only unique benefit is a per-caller runner label and permission set, and no judge needs either | A restructure now for a differentiation nothing uses | Carmack |
| 2 | Leave the duplication | Six copies that drift the day one is edited, which has already happened twice here | Nothing now, and the next second judge makes it eight | Carmack |
| 3 | Extract the checkout and install steps too | Three lines behind an indirection that costs more to read than the lines it hides | A larger action and no drift it prevents | Carmack |

