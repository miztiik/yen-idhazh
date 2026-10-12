# Plan 65 - Summary fidelity judge

**Last Updated**: 2026-10-12
**Level**: 5 (CLAUDE.md section 6). Row #3 declares a persisted shape, approved as P1 and amended by P13, and row #23 (the publish gate starting to withhold by itself, signed off by the owner in QQ12) is the first change to a published day; every other row states its own level.
**Status**: plan 65 since 2026-10-11 (it was the summary-fidelity-judge plan). Drafted 2026-10-11 from the drift-review plan of 2026-10-10 (Table R), and it absorbed plan 36, the summary-quality autotune plan, the same day (Section 5). Every decision is ruled: the owner answered Table QQ, QQ1 to QQ32, on 2026-10-11 and 2026-10-12, with A7 - little to no regular human step - as the driving principle. On 2026-10-12 Section 2 was rewritten to the rulings: the judge judges the whole digest per production model series (QQ1); rows #2, #5, #6, #10, #11, #16, #17, #19, #20, #21, #25 and #26 are collapsed; every pending row has its detail section, and Section 2 wins where Section 5's text of a plan 36 row differs. The research record (TODO/20261011-summary-quality-metrics-research-record.md) and the review record (TODO/20261011-summary-fidelity-judge-review-record.md) are the evidence; Section 4 carries the design as ruled. The council work is delivered; [its registration rules](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs) govern this plan's judges. Table Q tracks every request. Writing the rows also named what no ruling had set - setting names and defaults, stored shapes, and a few gaps the rulings left - each marked where it is decided as proposed for the owner's single approval of the plan; Table QA lists them in one place. On 2026-10-12 a lean version, plan 65.1, was written with the reviewers' proposed cuts already in it; the owner withdrew it the same day and it was deleted (Table Q, Q54). Plan 65.2 will be written from this plan, against the owner's intent of 2026-10-12 (Q58), once the owner has ruled on each proposed change or removal (Q57). The hard look is kept as proposals only in TODO/20261012-summary-fidelity-judge-hard-look-record.md. Names (Q72): summary-fidelity-judge now names the one judge of the sampled checks and the test bench, and the drift judge is summary-drift-judge; the rows below keep the old names until 65.2 is written. **This plan stays the record of every ruling; no row has started.**

## North Star

The owner's intent of 2026-10-12 (Table Q, Q58). Every row, research brief and review is checked against these lines; a proposal that breaks one names the line and why.

- **Unsupervised improvement of summary quality.** Measure, test, tune settings and move to newer models with no person in the loop; nothing is trained (Q73, E3); every automatic step is bounded, recorded and has an off switch.
- **Quality over brevity.** A summary is as long as its content needs; length is recorded, never targeted or penalised.
- **Built for tomorrow.** 10,000 summaries a day, longer summaries and new models; nothing is sized on today's numbers.
- **Sample, never check everything.** An approved second model, from a different family than the summarizer, classifies a small sample of summaries against the article text the summarizer was given; sample sizes follow from the precision wanted, and the digest's work step does no extra work.
- **Config-driven and evolvable.** Every number is in config; judges, metrics and ledgers have a lifecycle (active, paused, retired); records are enrolled ledgers in state/raw and state/compact, and kept article text is a small rolling sample deleted on schedule.
- **Metrics, not messages.** Stored metrics and code decide - no GitHub issues and no heuristics on wording; the other autotune judges (feed quality, feed reliability, content similarity) consume this judge's metrics to tune themselves.

## 0. Operating contract

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The weekly drift review compares per-site medians against fixed percentage thresholds. A median jumps between two kinds of page when their shares cross one half, so a change in a site's mix of story types reads as drift (issue #1270); the thresholds ignore sample size and per-site spread; every result lives only in a GitHub issue that nothing can query; and the review runs in a workflow of its own, outside the council where the project's judges run. Plan 36's autotune design for the same summaries (Section 5) planned fitted floors, a fluency judge and a publish gate beside it, so the owner moved it into this plan on 2026-10-11, and one plan now answers each question once. |
| A2 | Hard scope - in | - The drift review, its workflow and its settings are deleted (row #1)<br>- The judge's ledger drift-evals, its tenant module and its registration, paused (row #3)<br>- Its settings and member declarations per production model series (row #4)<br>- Per-summary values, daily values and the length-band and source adjustment (row #7)<br>- The recency-weighted whole-day test (row #15) and the anchor comparison (row #14)<br>- One false-discovery step per (run, date, series), and the replay with a planted-fault library (row #8)<br>- The combined score and the reading levels (row #13)<br>- The switch (row #9) and the panel on the Summaries page (row #12)<br>- Automatic tuning, promotion and drift responses within guards (rows #32 to #34)<br>- Per-source summary failures for the feed-quality plan (row #41) and series boundaries on every recorded change (row #42)<br>- The key-fact check: the sampled article text, summary-completeness-judge and its pilot (rows #29 to #31)<br>- The grounding check: summary-grounding-judge and its pinned model (rows #35 and #40)<br>- The per-sentence faithfulness score (rows #36 to #39)<br>- Plan 36's surviving rows: the eval-row stamp, the publish gate, its panel, withheld summaries and the corpus fence, and the shared judge guards (rows #18, #22 to #24, #27 and #28) |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | The design of Section 4 as the owner ruled it through Table QQ on 2026-10-11 and 2026-10-12, built as tenants of the LLM council and registered under [its current rules](../docs/architecture/publishing/llm-council.md) (P8). Reviewed by Fowler (contracts, structure, process safety) and Andre (metric and evaluation design), with the research record as evidence. |
| A6 | Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md, once the owner approves the whole plan (QQ26). Parallel N = 4. The judge's rows run in dependency order - #1 and #3, then #4, #7, #15, #8 and #9 - and rows #12, #13 and #14 share the judge's page, so they run one after another; the model judges (rows #29 to #31, #35 and #40) and the per-sentence score (rows #36 to #39) run beside them; the gate's rows follow row #18. Table D gives every dependency. |
| A7 | Driving principle | The project assumes little to no human intervention in regular running: aim to automate everything - tuning, promotion, recovery - and keep that as the driving principle, because good design decisions make the outcomes follow (owner, 2026-10-11). Every automatic step is bounded and recorded, so a person can read why it moved. Questions from QQ27 on are asked automation-first, and the earlier rulings that keep a person in a regular step are asked again (QQ27 to QQ29) |

### Hard scope - out

Table B - what is out, and what would bring it in

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Any change to what the pipeline fetches, extracts, summarizes or publishes, except the publish gate the owner approved in QQ12 (rows #22 and #23) | A crossed check still needs a person to inspect extraction | A crossing that a person confirms as an extraction defect, handled in its own plan |
| B2 | Acting on a crossed check, or on any score built from checks, by itself: stopping publication, resting a feed, demoting rank, marking items, moving a knob, changing a prompt, rewriting a summary. The publish gate of QQ12 acts on one summary's own scores against fixed lines, never on a crossed check | A real defect publishes until a person acts | An owner ruling that names one action for one check, once a ledger of a person's marks on crossings - filed through the door by a utility, as holdout-pairs is, keyed on H4.5's key and read by newest mark - measures the share of that check's crossings a person confirms. The action then takes a staged path: the judge files the proposed value as a row and never edits config; the stage that acts reads the latest row in its own build, damped, step-capped and clamped to its declared range; it ships behind a default-off flag that only records what it would have done, for a period the ruling names; it lifts itself when the evidence ends. Coverage and ranking stay the Editor's call (CLAUDE.md section 14) and the standing permission the owner's (Level 5); a model entry, temperature, repetition penalty, prompt or grammar never moves this way (P15) QQ29 (2026-10-11) keeps this: the judge's automatic responses touch nothing published |
| B3 | Any notification other than the one GitHub issue the judge opens, updates and closes itself for a quality alarm (QQ29) | A person hears only of quality alarms; behaviour changes and quiet nights are recorded, not raised | An owner ruling for another channel or for raising more than quality alarms |
| B4 | Feed rest and retirement rules | They stay with feed-health and the feed-quality plan | The feed-quality plan's own rulings (B13) |
| B5 | Judged dates before the judge's first night | The stored history starts at the switch. A person can judge a past date by dispatching the council with it, one date per run; the council's concurrency group keeps only one waiting run, so dispatches go one at a time, and each dispatch also runs every other active judge on that date, at its model cost | An owner ruling that history before the switch matters, priced in council runs |
| B6 | Moving the content-similarity judge's settings into a file of their own | The two judges keep their settings in two different places | A plan that moves them; this plan only sets the pattern for a new judge |
| B7 | Any check during the gap between row #1 and row #9 | No drift check runs while the judge is built | The owner rated the old review's output useless; nothing brings the old review back |
| B8 | Repairing a night only this judge missed, until the council plan's row 'Each judge runs over its own outstanding dates' lands: until then its nights_outstanding names no date | That date's rows stay missing; the next night's window shares six of its seven days. A night the whole council missed is still judged when another judge names it, because a council date runs every tenant | That council row, approved as the council plan's P2 on 2026-10-11 and built now; once it lands this judge's nights_outstanding names its own missed dates inside the repair window (Table Q, Q14) |
| B9 | Removing determinism_violation, an eval-row column a production run never sets, kept because committed days carry it and the console reads it (docs/architecture/contracts/determinism.md) | Every eval row keeps a column that is false in production | A plan of its own: drop the console's reader and the training-corpus filter, then the column with its read-side migration (CLAUDE.md section 11); the owner expects it to go |
| B10 | Checks against a fixed article set: a scorer reference set or a golden set (rows #10 and #11, collapsed) | A scorer-library upgrade under one scorer_version reads as faithfulness crossings on many sites in one night, and nothing names the library | An owner ruling that keeps a fixed article set beyond the site's housekeeping, or a scorer_version that also names the installed scorer libraries, so an upgrade opens a new model-and-scorer pair (L1.2); QQ15's per-column stamp (row #37) names the installed scorer library, so a library upgrade now opens a new series and this cost no longer arises |
| B11 | A stamp on the eval row per scored column, narrower than scorer_version: the faithfulness scorer's revision, weights and window for hhem; METRICS_VERSION for the counterweights | Each scorer_version move restarts the series of copied_phrase_share, faithfulness and page_furniture and keeps them out of the step for up to 14 days per site, even a move of band thresholds alone; page_furniture cannot join the long baseline (row #14) | A plan of its own that changes the eval row (Level 5); the three declarations then retire, and new slugs group on the narrow stamps (G1.4). Brought in by the owner on 2026-10-11 (QQ15): row #37 |
| B12 | Key facts in the digest: the summary prompts and the digest's work shard never ask for, produce or store key facts, today or later; a summary stays a title and a summary (the key points decoded before each summary were removed on 2026-09-24) | Completeness is measured only on the judge's daily sample, never on every summary | An owner ruling (owner, 2026-10-11, Q49). Until then only summary-completeness-judge lists key facts, at night, from the kept article text, as an extra check, and never takes the digest's labelled claims or lede sentences as its key facts; plan 17's keyfacts card, declared in the visual vocabulary but unruled, has nothing to draw while this stands |
| B13 | Per-source extraction health and every action on a source: naming it, its reliability or trust, rest, retirement, rank and the fix to its extraction | A source whose extraction breaks keeps publishing until the feed-quality plan acts; plan 65 only measures | The autotune-feed-quality plan and its judge own it (owner, 2026-10-12, QQ17); plan 65 leaves them alone and records each night's per-source summary failures for them (row #41, QQ32) |
| B14 | A one-year comparison: the recent weeks against the same weeks a year earlier | Seasonal patterns are not compared | An owner ruling once one series has 56 weeks of history; the frozen anchor (row #14) watches slow decline meanwhile (QQ18) |

### ESCALATE triggers

Table C - when to stop and ask; C5 and C8 are standing rules and do not stop

| # | Name | Trigger | What happens |
| --- | --- | --- | --- |
| C1 | Stored shape | A row would declare a persisted shape: a contract under backend/idhazh/contracts/ read by a later run, a ledger, or a committed reference file with expected values | Stop. The owner rules on the shape (CLAUDE.md section 0). Row #3's shape was approved as P1 on 2026-10-11 and amended by P13 and QQ10; the other stored shapes were approved in QQ11 to QQ32 |
| C2 | New dependency | A row needs a new runtime dependency, or a model or extra the council's jobs do not install today | Stop. Name the cost and the beneficiary (Guardrail #8); consult Carmack for runner minutes. scipy was approved as P7 on 2026-10-11 and withdrawn on 2026-10-12 (QQ20) |
| C3 | Unruled item | A row's Decisions table cites a Table P item the owner has not ruled | Stop before implementation of that row |
| C4 | Ledger bypass | A check would read ledger files other than through ledger.load_days or the door's own indexes | Stop. The ledger door is the only reader (docs/concepts/growing-reads.md, Guardrail #12) |
| C5 | Reading budget | Row #8's replay shows a typical night with more crossed checks than crossings_budget (F1.12) | No stop: the row splits the count by check, fixes a check that crosses too often on reshuffled dates, then sets false_discovery_rate (F1.11) to 0.01 and replays again before the switch; only a typical night still over the budget is reported, as a finding with options (CLAUDE.md section 0d), never as a veto (owner, 2026-10-11, E1 and P18) |
| C6 | Mix alarm | A new check crosses on the #1270 fixture (row #7) | Report it with options (CLAUDE.md section 0d) before merge |
| C7 | Untrusted text | Text from an article address would enter a shell argument, a commit message or a file path | Stop (Guardrail #11) |
| C8 | Setting moves | A DriftConfig field has a reader outside the files row #1 deletes | The row continues: the field moves to that reader's config block, and the removed-setting message names where it went (E1.3; owner, 2026-10-11) |
| C9 | Judge import | A judge module or contract would enter the council's import closure | Stop. backend/tests/council/test_council_runs_without_a_judge.py holds the seam, and the list of judge contracts that cross it may not grow (llm-council.md) |
| C10 | Exact repeat | A row of this plan would compare a re-run with a recorded output and expect a match, or fix a seed so a result repeats | Stop. Determinism is not an expectation (owner, 2026-10-11): assert far from the cut, or against a tolerance stated with its noise (Guardrail #10). Reading stored rows back is not a re-run |

## 1. Status Reckoner

Table D - rows

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The drift review is deleted | - | A | PENDING | - | - | - |
| 2 | The judge's settings file and site identity | - | A | COLLAPSED (owner, 2026-10-11, QQ1: site identity is not built; the judge's config file lands with rows #3 and #4) | - | - | - |
| 3 | The judge's ledger and its tenant module | - (council judge registration is delivered) | B | PENDING | - | - | - |
| 4 | The judge's settings and member declarations, per model series | 3 | C | PENDING | - | - | - |
| 5 | Count kind: article count from the item-health census | 4 | D | COLLAPSED (owner, 2026-10-11, QQ1: feed volume is not summary quality; B4, B13) | - | - | - |
| 6 | Share kinds: unusually short and page furniture | 5 | E | COLLAPSED (owner, 2026-10-11, QQ1: article length and page furniture are input properties, shown in RA12) | - | - | - |
| 7 | Per-summary values, daily values and the mix adjustment | 4 | D | PENDING | - | - | - |
| 8 | One false-discovery step per (run, date, series), and the replay with a planted-fault library | 15 | F | PENDING | - | - | - |
| 9 | The switch: the judge joins the council | 1, 8 | G | PENDING | - | - | - |
| 10 | Scorer reference check | 9 | I | COLLAPSED (owner, 2026-10-11, D3, with both reviewers: a fixed article set does not survive the site's housekeeping, and its test expected an exact repeat; B10) | - | - | - |
| 11 | Golden-set check | 9 | I | COLLAPSED (owner, 2026-10-11, D3, with both reviewers; B10) | - | - | - |
| 12 | The stored checks on the Summaries page (/console/model/), beside the publish gate's panel (QQ14) | 9 | H | PENDING | - | - | - |
| 13 | The combined score and the reading levels | 9 | H | PENDING | - | - | - |
| 14 | The anchor comparison: once a week, the recent week against each series' frozen first anchor_days (56) valid days, read from the eval ledger's stored scores; it starts by itself from a series' ninth week and lands paused (QQ18) | 8 | H | PENDING | - | - | - |
| 15 | The recency-weighted whole-day test | 7 | E | PENDING | - | - | - |
| 16 | Plan 36 row #1: extract the fit core, direction-parameterised | plan 34's fit core (on main: backend/idhazh/similarity/fit.py) | K | COLLAPSED (owner, 2026-10-11, QQ3: this judge's nightly test replaces plan 36's fitted floors) | - | - | - |
| 17 | Plan 36 row #2: the two contracts and the per-metric knob block, inert | 16 | L | COLLAPSED (owner, 2026-10-11, QQ3: this judge's nightly test replaces plan 36's fitted floors) | - | - | - |
| 18 | Plan 36 row #3: EvalRow gains publish_decision and withheld_reason, and the stamp tells a record-only would-be withhold from a real one (QQ12; its geval column dropped by QQ4) | plan 35's EvalRow changes (on main since 2026-09-24) | K | PENDING (Level 5: two EvalRow columns, signed off with the owner's single approval of the plan, QQ26; plan 36's approval of 2026-09-19 does not carry) | - | - | - |
| 19 | Plan 36 row #4: the fold | 17, 18 | M | COLLAPSED (owner, 2026-10-11, QQ3: this judge's nightly test replaces plan 36's fitted floors) | - | - | - |
| 20 | Plan 36 row #5: the fit and the faithfulness seed | 16, 17, 19 | N | COLLAPSED (owner, 2026-10-11, QQ3: this judge's nightly test replaces plan 36's fitted floors) | - | - | - |
| 21 | Plan 36 row #6: G-Eval fluency judge in the council | 18 | L | COLLAPSED (owner, 2026-10-11, QQ4: the summarizer grading its own fluency is replaced by the sampled key-fact check, rows #29 to #31) | - | - | - |
| 22 | Plan 36 row #7: the publish gate stamps every summary, record-only: an unsupported number, and faithfulness on the sentence-level score once row #37 lands (row #39 switches it on); today's whole-summary score only stamps (QQ12 B2) | 18 | O | PENDING (Level 5: the run record gains the counts of stories that would be lost entirely, named for the owner's single approval, QQ26) | - | - | - |
| 23 | Plan 36 row #8: the gate withholds by itself while its guards hold and returns to record-only when one fails; a withheld summary is absent from the day and the story's next-best duplicate takes its place; no stub pre-filter; withhold_failing_summaries stops it (QQ12 A1, C1, D1) | 22, 27, 35 | P | PENDING (Level 5: the first change to a published day, signed off by the owner in QQ12; the switch record on the run plan, named for the owner's single approval, QQ26) | - | - | - |
| 24 | Plan 36 row #9, as QQ14 ruled: the publish gate's panel on the Summaries page beside the drift judge's crossings - the gate's state, its two guards against their lines, the daily withheld share by reason and the stories lost entirely; no alarm of its own; plan 36's band charts are not drawn | 22 | P | PENDING (it reads rows #23 and #35 as they land) | - | - | - |
| 25 | Plan 36 row #10: measure a real G-Eval call | 21 | M | COLLAPSED (owner, 2026-10-11, QQ4, with row #21) | - | - | - |
| 26 | Plan 36 row #11: confirm coherence runs in assemble | plan 35's coherence scorer (scoring since 2026-09-24) | K | COLLAPSED (owner, 2026-10-12, QQ24: coherence is scored every day since 2026-09-24 in the daily work step that composes the eval row, not in assemble as plan 36 assumed; the console's Hardware page shows memory; nothing judges coherence, QQ2) | - | - | - |
| 27 | Plan 36 row #12, as QQ13 ruled: every withheld summary kept in key-fact-articles beside the sampled articles (no rejects ledger), and the corpus harvest skipping the summaries the gate marks on a line that may withhold | 18, 22, 29 | P | PENDING (Level 5: the withheld entries in key-fact-articles, and what the training corpus takes) | - | - | - |
| 28 | Plan 36 row #13, as QQ25 ruled: one shared set of guards for every model judge - no trailing space where a judge reads a one-token answer (the grounding judge's yes or no, the content-similarity judge's verdict), answer tokens built in position and first-token probabilities logged; thinking off for every judge call, pinned by a canary that rejects a recorded thinking-on completion; the planted-instruction canary on recorded completions for the two judges that read article text; a live red-team stays out of scope (Guardrail #7) | plan 34, 30, 35 | Q | PENDING | - | - | - |
| 29 | The digest run samples 30 scored summaries a day across its runs and keeps their article text in key-fact-articles for a rolling window set in config (31 days, QQ30), and the article text of the would-be withheld summaries the faithfulness check reads (faithfulness_checks_per_night, 8; QQ12, QQ16) | - | R | PENDING (Level 5: committed article text, a CLAUDE.md section 0a exception the owner approved in QQ4; key-fact-articles is a ledger the door does not file, one folder a day, in the family summary-completeness-judge, QQ11) | - | - | - |
| 30 | summary-completeness-judge: completeness and conciseness of the sampled summaries from their key facts, with the summarizer's own model, as its own council judge that runs the model (config/judges/summary-completeness-judge.json; its numbers in key-fact-scores); it lists key facts itself from the kept article text, never from the digest (B12) | 29 | S | PENDING (Level 5: a new ledger, key-fact-scores, numbers only, QQ30 and QQ11) | - | - | - |
| 31 | The pilot: summaries with facts removed on purpose; the key-fact metrics join the alarm through automatic promotion (QQ28) once they catch them; if they do not, moving the check to Gemma 4 E4B is an owner decision (a model change) | 4, 8, 30 | T | PENDING | - | - | - |
| 32 | The scheduled replay tunes weights and rho within guards, records every proposal, and stops at once when auto_apply_tuning is false | 8, 13 | U | PENDING (Level 5: a new ledger, drift-evals-tuning, one row per tuning run, QQ30 and QQ11) | - | - | - |
| 33 | Automatic promotion and pausing of metrics at each scheduled replay, every move recorded; auto_promote_metrics stops it | 8, 32 | U | PENDING (each move a row in drift-evals-tuning, QQ30 and QQ11) | - | - | - |
| 34 | Automatic responses to a drift reading: the stored diagnosis, the larger key-fact sample while a quality alarm lasts, and one GitHub issue the judge opens, updates and closes; auto_respond_to_drift stops them | 13, 29, 30 | V | PENDING (Level 5: keyfact_sample_multiplier on DriftEval, named for the owner's single approval, QQ26; needs issues: write on the council job that settles this judge, under [per-job permissions](../docs/reference/github-actions.md#llm-council-permissions); C7 untrusted text) | - | - | - |
| 35 | summary-grounding-judge at night (QQ16): IBM Granite Guardian 3.3 8B, the official GGUF build, through the pinned llama.cpp runtime, classifies each sentence of up to faithfulness_checks_per_night (8) summaries against the kept article text with its groundedness criterion - yes or no, never a new summary - planted unfaithful variants first (planted_checks_per_night, 2), then the gate's would-be withholds, then sampled ones, within faithfulness_check_budget_minutes (40); its verdicts go to grounding-verdicts; once it catches planted unfaithful summaries, the share it confirms feeds the gate's guard (QQ12) and its disagreement with the main scorer is charted; the model and its prompt template are named in config, so a later model is a config change plus the same planted-fault test | 22, 29, 40 | W | PENDING (Level 5: a new ledger, grounding-verdicts, and a new judge, config/judges/summary-grounding-judge.json with runs_model true) | - | - | - |
| 36 | The cost of per-sentence faithfulness, measured on one day's worth of committed summaries and their article text before the eval-row change (QQ15) | - | X | PENDING | - | - | - |
| 37 | One eval-row change (QQ15): per-sentence faithfulness - each sentence against its best window; the mean, the lowest sentence, sentences under 0.50 and 0.80 and the winning window - name and date checks, a version stamp per scored column (for faithfulness the scorer, its revision, weights, window geometry and installed library; METRICS_VERSION for the counterweights; coherence's encoder), and a replaceable scorer named in config with a column that does not name HHEM | 36 | Y | PENDING (Level 5: the owner's sign-off in QQ15) | - | - | - |
| 38 | The switchover: the new score runs beside the old one, the drift judge declares the per-sentence members paused, and the old faithfulness members retire by themselves the night their replacements turn active under QQ28 (at least 28 usable days and the planted-fault test: 4 to 8 weeks); each replacement takes over its predecessor's starting weight (QQ31); two more paused members read the name and date checks | 8, 33, 37 | Z | PENDING | - | - | - |
| 39 | The gate and the corpus fence read the per-sentence line: the gate's faithfulness line starts at 0.50 on the lowest-scoring sentence and its own guards decide whether it acts (QQ12); the corpus harvest skips summaries under it (QQ13) | 22, 27, 37 | Z | PENDING | - | - | - |
| 40 | Pin the checker model: Granite Guardian 3.3 8B, the Q4_K_M GGUF build (4.94 GB, Apache 2.0), in the model config with its file's hash, fetched each night for the judge whose declaration names it (served_model) and never saved to the shared cache (QQ16) | - | X | PENDING (a new model, approved in QQ16; ModelsConfig gains a checker slot and the judge declaration gains served_model, named for the owner's single approval, QQ26; Carmack confirms the runner's memory, minutes and fetch time) | - | - | - |
| 41 | summary-failures-by-source, for the feed-quality plan: each night the drift judge files one row per source and model series - the summaries scored, the failures by reason (under the faithfulness line, an unsupported number, an extraction flag, withheld by the gate) and the points docked, one per summary with at least one failure, with no weights by reason; it changes no source's reliability, trust, rank, rest or config (QQ17, QQ32) | 9 | AA | PENDING (Level 5: a new ledger in the family summary-fidelity-judge, approved in QQ32) | - | - | - |
| 42 | Series boundaries on every recorded change (QQ19): model and scorer changes restart as before (P14); a prompt, quantization or runtime change restarts the metrics its expected_shifts entry lists, or every metric when it has none, each with a new anchor (row #14); the judge reads the prompt version, quantization and runtime build each scored row was made with, from the run's recorded inputs, joined to each eval row by run_id (row #37 adds no column for them) | 8, 37 | AB | PENDING | - | - | - |

## 2. Rows

Rewritten on 2026-10-12 to the rulings of Table QQ (QQ26). Each pending row has its section here, in row order; a collapsed row keeps a short note. Settings are named once, in row #4's Table F1 or in Table RC; the members are Table RA; the arithmetic is the rule in Section 4.

### Row #1 - The drift review is deleted

- **Scope:** .github/workflows/drift.yml, backend/idhazh/drift.py, backend/utilities/drift_report.py, backend/tests/test_drift.py and the drift block of config/idhazh.json are deleted, a config that still spells the block is refused by name, and every doc that describes the review points to this judge instead.
- **Level:** 3 (deletes a workflow and a config block).
- **Files touched:**
  - .github/workflows/drift.yml (deleted)
  - backend/idhazh/drift.py (deleted)
  - backend/utilities/drift_report.py (deleted)
  - backend/tests/test_drift.py (deleted)
  - backend/idhazh/contracts/knobs/evaluation.py (DriftConfig deleted)
  - backend/idhazh/contracts/app_config.py (the drift field deleted; SUPERSEDED_APP_NAMES gains drift with the message that summary-fidelity-judge replaces the review, with its own settings in config/judges/summary-fidelity-judge.json, that each setting E1.3 moved went to its reader's block, and that every other drift setting is gone; one changelog entry, the oldest entry deleted to keep five as CLAUDE.md section 11 allows; the validator's docstring names drift)
  - config/idhazh.json (the drift block deleted)
  - backend/tests/contracts/test_app_config.py and backend/tests/contracts/test_retired_knobs.py (re-derive at dispatch)
  - backend/tests/workflows/test_triggers.py and backend/tests/workflows/test_workflow_inputs.py (re-derive with git grep -n drift.yml backend/tests at dispatch)
  - docs/concepts/evaluation.md ("Per-item scores cannot see drift": the instrument is this judge's nightly test over the eval ledger, per production model series; the fixed set and its refresh move to rejected alternatives with the reason in B10; "A deterministic output can change" becomes "An output can change") and docs/concepts/growing-reads.md
  - Every other reader of the deleted names, from git grep -n -i -e "drift.yml" -e "drift_report" -e "idhazh.drift" -e "DriftConfig" -e "Drift review" -e "app.drift" -e "test_drift" -e "min_domain_rows" -e "source_word_count_drop" -e "extractiveness_rise" -e "month_over_month_pct" -e "year_over_year_pct" -e "quarterly_refresh_fraction" -- . at dispatch
- **Acceptance gates:** local - ruff, mypy and the shared test selector over the contract and workflow tests per docs/how-to/run-the-gates.md; CI - full suite.
- **Oracle:** the search above finds history and nothing else, and a config that still carries a drift block is refused with a message naming where each moved setting went. Cannot settle: who read the old issues; a person closes the four open drift issues.

Table E1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| E1.1 | The drift review is deleted before the judge is built, so nothing is migrated and no second implementation runs beside the first | Owner, 2026-10-11 (stop the drift review); P8 |
| E1.2 | No new code lives under a drift name; the judge's code lives in a package of its own, so later judges and later drift work each have a home | Owner, 2026-10-11 |
| E1.3 | month_over_month_pct, year_over_year_pct and quarterly_refresh_fraction go with the block when the search finds no reader; a setting that something still reads moves to that reader's config block, the removed-setting message names where it went, and the row continues (C8) | Owner, 2026-10-10 (B6 of the drift plan); owner, 2026-10-11 (C8 a standing rule) |

Table E2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E2.1 | Keep the drift review until the judge runs | The owner rated its output useless | Weekly issues from the old rules until row #9 merges | Owner, 2026-10-11 |
| E2.2 | Split drift.py into a package first, as the drift plan's row #1 did | Nothing will be added to it; the checks start in the judge's own package | A structural pull request whose result is deleted | Owner, 2026-10-11 |

### Row #2 - The judge's settings file and site identity (collapsed)

Collapsed on 2026-10-11 by QQ1 (A1): the judge compares the whole digest per production model series, so site identity, multi_tenant_hosts and page_types are not built (RB10). The judge's config file is created by row #3, which registers the judge, and its settings land with row #4, whose Table F1 lists them. The decisions this row made are kept in row #4's Tables F2 and F3 for the rulings that cite them.

### Row #3 - The judge's ledger and its tenant module

- **Scope:** the contract DriftEval (Table H3, the row the owner ruled in QQ10) and the ledger drift-evals in the family summary-fidelity-judge are registered and enrolled for compaction and retention as ledger-registry.md requires of a new ledger, and backend/idhazh/summary_fidelity_judge/tenant.py presents the members of the council's tenancy protocol and files the rows it is handed through ledger.persist in settle. The judge follows the [registration rules](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs): config/llm_council.json gains summary-fidelity-judge in judge_names, and the new config/judges/summary-fidelity-judge.json carries lifecycle_status paused and runs_model false, so no night runs it until row #9. This row also writes the dated naming exception for drift-evals (QQ11) and lists numpy directly in the base dependencies (QQ20).
- **Level:** 5 (a persisted contract and a new ledger). ESCALATE C1 is settled: the owner approved the shape as P1, amended by P13 and by QQ10 (P26).
- **Files touched:**
  - backend/idhazh/contracts/drift_eval.py (new: DriftEval, CheckOutcome, Role, Statistic, Comparison, Direction and ValueUnit, and the judge's slug as a closed set beside its column; check_name is a checked name, not a closed set (P13))
  - config/llm_council.json (judge_names gains summary-fidelity-judge)
  - config/judges/summary-fidelity-judge.json (new: lifecycle_status paused, runs_model false; row #4 adds the settings)
  - backend/tests/council/ (re-derive at dispatch: tests that enumerate judge_names or load each judge's config file; no test enforces an activation decision, per the [activation rule](../docs/architecture/publishing/llm-council.md#design-rationale-a-new-judge-starts-paused))
  - backend/idhazh/contracts/__init__.py (CONTRACTS, entered the way content_similarity_judge_metrics is; re-derive at dispatch)
  - backend/idhazh/contracts/ledger_name.py (SUMMARY_FIDELITY_JUDGE_DRIFT_EVALS = "drift-evals")
  - config/ledgers.json (family summary-fidelity-judge: status active, one-line description, onboarded day; entry grain raw-and-compact, prefix ["summary-fidelity-judge", "drift-evals"])
  - backend/idhazh/ledger/keys.py (_JUDGE_DOOR_SHAPES: the key of H4.5 and the row contract, imported on first use; no preference)
  - backend/idhazh/ledger/staging.py (REGISTRY: written by the judge's settle in the council's save job, no digest.yml commit label)
  - frontend/src/lib/data/slice-shapes.ts (LEDGER_NAMES gains drift-evals; LEDGER_FOLDERS gains summary-fidelity-judge)
  - config/gardener/compact-summary-fidelity-judge-drift-evals.json (new: kind compaction, owns state/raw/summary-fidelity-judge/drift-evals and state/compact/summary-fidelity-judge/drift-evals, the approved retention chain of H4.4, the other fields copied from compact-council-run-records.json) and config/idhazh_gardener.json (task_names gains it)
  - backend/tests/contracts/test_gardener_config.py (RETENTION_LEDGERS gains drift-evals), backend/tests/contracts/_fixtures.py (FIXTURE_FILES) and one drift-eval fixture in the contract fixtures folder it names
  - backend/idhazh/summary_fidelity_judge/__init__.py and backend/idhazh/summary_fidelity_judge/tenant.py (new: JUDGE_ID, shard_count 1, committed_paths from staging.staged_path, nights_outstanding naming no date (B8), publication_inputs returning an empty tuple because settle reads nothing committed, prepare, run_shard, settle)
  - backend/idhazh/summary_fidelity_judge/record.py (new: the unit's rows as one JSON-lines file in a slot of its own, written once after the unit's last row by temp file and rename through session.unit_file with the contract's own model_dump_json and read back with model_validate_json, never registered in backend/idhazh/ledger/csv_file.py; and the filing through ledger.persist)
  - pyproject.toml (numpy listed directly in the base dependencies rather than arriving through onnxruntime, QQ20; duckdb joins pyarrow on ruff's banned imports for backend/idhazh/, re-derive existing importers with git grep -n duckdb backend at dispatch)
  - backend/tests/summary_fidelity_judge/test_tenant.py (new)
  - docs/architecture/contracts/state-ledgers.md (one table row); docs/architecture/contracts/ledger-registry.md (a dated line under the naming rule: drift-evals keeps its general name by the owner's ruling of 2026-10-11 (QQ11), and a later drift ledger takes a name that says what it holds); docs/concepts/partitions.md (the count of collections it names; re-derive at dispatch)
  - docs/architecture/publishing/llm-council.md ("What is heard here" gains this judge, paused) and docs/architecture/publishing/summary-fidelity-judge.md (new: the judge's own page)
  - Every other file that names the newest judge ledger, from git grep -n -e "CONTENT_SIMILARITY_JUDGE_METRICS" -e "content-similarity-judge/metrics" backend frontend config docs at dispatch
- **Acceptance gates:** local - ruff, mypy, the shared test selector over backend/tests/contracts/, backend/tests/council/, backend/tests/workflows/test_ledger_staging.py, backend/tests/workflows/test_ledger_door_jobs.py and backend/tests/summary_fidelity_judge/; CI - full suite.
- **Oracle:** a night driven end to end against this tenant in a tmp_path state root, with the council's own session, files rows that read back through ledger.load_days equal to what the unit wrote; two council runs of one judged date both read back; the contract refuses a row whose outcome disagrees with its p_value, q_value and false_discovery_rate, and a row whose role and outcome cannot go together (a shown or paused row with a q_value); nights_outstanding names no date; the committed judge_names and the new config file load, and the paused judge is never planned. Cannot settle: whether the shape answers the questions row #12's panel asks.

Table H1 - the 2026-10-11 draft's declarations, and what replaced each (the members as ruled are Table RA, declared in row #4)

| # | Draft declaration | In the ruled design |
| --- | --- | --- |
| H1.1 | article_count, a count of the item-health census per site | Collapsed with row #5: feed volume, not summary quality (QQ1); feed counts belong to feed-health and the feed-quality plan (B4, B13) |
| H1.2 | unusually_short, a tail share of article length per site | Collapsed with row #6: an input property; article length only adjusts (QQ1) |
| H1.3 | page_furniture, the extraction_suspect share per site | Collapsed with row #6: rows flagged extraction_suspect leave the judged members, and their rate is shown in the input-mix diagnostic (RA12) |
| H1.4 | article_length, a distance per site | Not judged: article length is a covariate that only adjusts (QQ1) and is shown in the input mix (RA12) |
| H1.5 | copied_phrase_share, a distance per site | copy_index and copy_ceiling, watched as behaviour, never in the combined score (RA8, RA9; QQ2) |
| H1.6 | faithfulness, a distance per site | faith_index, faith_below_050 and faith_below_080, judged (RA1 to RA3); replaced by per-sentence members once row #37 lands (row #38) |
| H1.7 | page_mix, a note of page-type shares | Shown in the input-mix diagnostic (RA12), outside the step |
| H1.8 | window_rows, the reserved guard row | Replaced by the valid-day minimums: a night with too few valid days stores too_few_days on every member (H2.3; QQ6) |
| H1.9 | combined_measures, the reserved combined row | Replaced by combined_score, the reserved name of the one signed, correlation-adjusted score (row #13; QQ8) |

Table H2 - outcomes (CheckOutcome; declared once here, QQ10)

| # | Value | Meaning |
| --- | --- | --- |
| H2.1 | threshold_crossed | Tested in the step; q_value at or under false_discovery_rate (row #8). A signal for a person or the automatic diagnosis to inspect, not a diagnosis |
| H2.2 | threshold_not_crossed | Tested in the step; q_value above false_discovery_rate. Not evidence that nothing changed |
| H2.3 | too_few_days | Not tested: the recent window holds fewer than min_recent_days valid days or the baseline fewer than min_baseline_days, because days are missing, failed or thin (QQ6) |
| H2.4 | earlier_model_baseline | Retired with the 2026-10-11 draft: nothing is compared across a recorded change (QQ19), and a young series reads new_series (H2.7) |
| H2.5 | not_tested | Retired with the note kind and window_rows; a shown row is stored as paused (H2.6) |
| H2.6 | paused | Tested and stored with its p_value and no q_value, outside the step, so it moves no other row's q_value: a paused member (G1.5) or a shown member (role shown), which is never promoted |
| H2.7 | new_series | Not tested: the series started inside the windows (QQ19), so it lacks the valid days a test needs; series_started_by (H3.24) names the change |

Table H3 - DriftEval, one row per member and comparison per judged night per council run, plus one combined_score row (schema stem drift-eval; QQ10)

| # | Field | Type | Meaning |
| --- | --- | --- | --- |
| H3.1 | run_id | RunId | The council run that judged the night (the judge-ledger rule in ledger-registry.md) |
| H3.2 | judge_id | the judge's slug, a closed set of one | Which judge wrote the row |
| H3.3 | date | DateStamp | The judged night; the recent window ends on it, and it decides the file the row is filed under |
| H3.4 | checked_at | Timestamp | When the unit computed the row |
| H3.5 | rules_version | str | The rule's version in force; it rises when the arithmetic of Section 4 changes, never for a declaration, which check_definition spells (H3.22) |
| H3.6 | recent_days, baseline_days, baseline_lag_days, recency_lambda | int, int, int, float | The window settings in force for this row's comparison (QQ5, QQ6) |
| H3.7 | recent_valid_days, baseline_valid_days | int, int | The valid days each window used; a skipped day is never filled in (QQ6) |
| H3.8 | model_id | str | The production model series the row judges |
| H3.9 | check_name | a declared member name (Table RA, F1.13): lower-case letters, digits and underscores, starting with a letter, checked against the named list when the row is written; or the reserved name combined_score | Which member; not "check", which is a reserved word in the console's query engine |
| H3.10 | instrument | str | The stamp of the scorer behind the member's column: scorer_version until row #37 stamps each scored column (G1.7, P14) |
| H3.11 | role | Role: judged, watched, evaluator or shown | Judged members and combined_score enter the step and the combined score; watched and evaluator members enter the step alone; shown members never enter it (QQ2, QQ8, QQ10) |
| H3.12 | recent_value, baseline_value | float or null | Each window's raw daily statistic in value_unit; null on the combined_score row |
| H3.13 | recent_adjusted, baseline_adjusted | float or null | The same after the length-band and source adjustment (row #7); equal to the raw values for watched members |
| H3.14 | direction | Direction: higher, lower, either or worse | The member's harm direction; worse on the combined_score row |
| H3.15 | p_value | float or null | Null when not tested; from the shared whole-day deals (row #15), so a re-run of the night draws again |
| H3.16 | q_value | float or null | The Benjamini-Hochberg adjusted p-value within the row's family, the (run_id, date, model_id) triple (M1.2); null outside the step. Rank or re-threshold only rows of one run_id, the night's latest; two runs of one night can disagree near the cut, because each draws its own deals |
| H3.17 | false_discovery_rate, min_day_rows, min_recent_days, min_baseline_days | float, int, int, int | The settings in force, so a later reader needs no git history |
| H3.18 | reshuffles, reshuffle_hits | int or null | Deals used and the hits among them (a tie counts); the p-value's relative error from the draw is about 1 / sqrt(reshuffle_hits) |
| H3.19 | outcome | CheckOutcome (H2) | What the row concluded |
| H3.20 | statistic | Statistic: logit_mean, share_past_line, mean or median, or combined on the combined_score row | Which daily statistic made the row (replaces the draft's test_kind; one test serves every statistic, row #15) |
| H3.21 | value_unit | ValueUnit: score, share, words or z | What the values count |
| H3.22 | check_definition | str | Derived, never hand-typed: the member's column, statistic, line, transform, adjustment and harm direction, and on the combined_score row each member and its weight, spelled so a row still explains itself after its declaration retires |
| H3.23 | comparison | Comparison: trailing or anchor | Which windows were set against each other: the recent week against the lagged baseline (row #15) or against the series' frozen anchor (row #14); part of the key (H4.5) |
| H3.24 | series_started_by | str or null | The recorded change that started the series the row reads - a model, prompt, quantization, runtime or scorer change, or a declared expected shift (QQ19, row #42); replaces the draft's changed_part |
| H3.25 | effect | float or null | The adjusted recent value minus the adjusted baseline value, in value_unit; on the combined_score row, the combined score C in standard units |
| H3.26 | z_value, rho | float or null, float | The member's standardised score against the deals, widened by its day-to-day correlation rho, and the rho applied (Section 4; QQ9) |
| H3.27 | tuning_version | str or null | On the combined_score row, the tuning_version of the applied tuning row in force in drift-evals-tuning, which carries the weights and rho; null before the first applied tuning (QQ27, QQ30; row #32) |
| H3.28 | settings_digest | str | The sha256 of the settings file in force, so the full settings of a row can be read back from git without guessing (QQ10) |
| H3.29 | inputs_changed | list of str | The recorded inputs that changed inside the row's windows, which a crossing names (QQ29; RD5) |
| H3.30 | keyfact_sample_multiplier | int or null | On the combined_score row, the multiplier of the key-fact sample the night orders: drift_sample_multiplier during a quality alarm with auto_respond_to_drift true, otherwise 1; null on rows of other kinds (QQ29; row #34, X6.3) |

Table H4 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| H4.1 | The ledger is drift-evals in the family summary-fidelity-judge: rows land in state/raw/summary-fidelity-judge/drift-evals/YYYY/MM/DD/ as parquet, and the gardener packs them into state/compact/summary-fidelity-judge/drift-evals/ (daily, monthly and yearly files with their index files); the family also holds drift-evals-tuning (row #32) and summary-failures-by-source (row #41) | Owner, 2026-10-11 (P1); owner, 2026-10-11 (QQ11); owner, 2026-10-12 (QQ32) |
| H4.2 | Every file name is minted by the ledger door (a version 8 UUID per writer and attempt); no writer names a file | backend/idhazh/ledger/persist.py |
| H4.3 | Every member of every judged night is stored, untested ones included (too_few_days, new_series, paused), so a skipped member is visible | Owner, 2026-10-10 (store every check); owner, 2026-10-11 (QQ10) |
| H4.4 | Retention follows the owner-approved live chain in ledger-registry.md, held by test_every_ledger_uses_the_approved_live_retention_chain | ledger-registry.md |
| H4.5 | Key: run_id, date, check_name, comparison, model_id, instrument, with no preference, so packing keeps every council run of a night; a retry of one run settles to its highest attempt through the door; a reader of one judged night takes the run with the latest checked_at | Owner, 2026-10-11 (P1, QQ10); ledger-registry.md, the rule a judge ledger follows; Fowler (reviewed 2026-10-11) |
| H4.6 | The row declares none of the door's names (ledger, covers, attempt, job, shard, unit_id) and run_id only as the council run; the writer identity is the council's, job save_council_results | ledger-registry.md, the rule a judge ledger follows |
| H4.7 | One unit a night (shard_count 1): run_shard computes every row into a scratch file in the tenant's own slot under backend/var/council/, reports no model calls, writes that file once, after its last row, or leaves none and returns stopped_on_deadline, so settle files a whole night or nothing; settle applies row #8's step and files the rows, naming its own producer; the tenant declares no refusal of a night, because its work takes seconds and runs no model | Owner, 2026-10-11 (P8, Q44); backend/idhazh/council/tenancy.py |
| H4.8 | Member names state what is measured and the outcome states whether the threshold was crossed, so a stored row never claims a movement its own outcome denies | Owner, 2026-10-10 (rename request); outcome names debated by Fowler and Andre, 2026-10-11 |
| H4.9 | Readers count a stretch, not a night: a stretch is consecutive run days on which one key crosses, and a day with no run does not end one, because one real change stays in the recent window for seven nights | Owner, 2026-10-11 (P11) |
| H4.10 | The judge registers through the council: judge_names in config/llm_council.json and its own config/judges/summary-fidelity-judge.json with lifecycle_status and runs_model; the owner's decision to activate it is recorded in the commit message and the judge's page, never in a test | [Judge registration](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs); owner, 2026-10-11 (Q35, Q36) |
| H4.11 | drift-evals keeps its general name with a dated exception under the naming rule in ledger-registry.md; a later drift ledger takes a name that says what it holds | Owner, 2026-10-11 (QQ11, P29) |

Table H5 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H5.1 | state/raw/summary-quality-evals/drift/ | The registry refuses a door ledger inside another door ledger's folder, because a walk of the outer ledger's raw days would read the inner one's files (backend/idhazh/contracts/ledgers.py); a fixed file name such as ledger.parquet is also refused, because a raw file is immutable once written | A change to the registry rule, or renaming the eval ledger and moving its committed raw and compact files into a nested folder; either is Level 5 | backend/idhazh/contracts/ledgers.py |
| H5.2 | JSON files under state/summary-fidelity-judge/, as two of the content-similarity judge's ledgers still are | The owner wants parquet under state/raw/ with the ledger enrolment; the flat and stamped grains are the ones the registry calls transitional | None | Owner, 2026-10-11 |
| H5.3 | A ledger that is its own family, at state/raw/summary-fidelity-judge/ | No door ledger may sit inside another, so a later ledger of this judge could never sit beside it | A second family later | Owner, 2026-10-11 (P1) |
| H5.4 | Store only crossed rows | A reader cannot tell "checked, threshold not crossed" from "never checked" | Fewer rows a night | Owner, 2026-10-10 (store every check) |
| H5.5 | Compute the rows in settle | settle runs inside the collecting job's 30-minute bound for every tenant and date, and a job killed there commits nothing for any tenant | None; the unit pays one runner job either way, with no model server | Owner, 2026-10-11 (P8) |
| H5.6 | A preference that keeps one run per night | Packing would delete the earlier run's rows, against "every check stored", and could mix two runs' families in one day | None | Fowler (reviewed 2026-10-11) |

### Row #4 - The judge's settings and member declarations, per model series

- **Scope:** config/judges/summary-fidelity-judge.json gains every setting the judge reads (Table F1 and the rows of Table RC that name this file), validated by a model that forbids unknown keys, bounds every field and is imported only by the judge's own package. metrics (F1.13) declares the members of Table RA: each names its slug, lifecycle_status, role (judged, watched, evaluator or shown), eval-ledger column, statistic, line, transform, adjust_by (length band, source or none), harm direction, instrument key, combine_weight and rho, and the comparisons it takes (trailing, and anchor once row #14 lands). registry.py refuses a bad declaration before any night (G1.3), and windows.py reads the eval ledger through ledger.load_days for the days the windows span, one row per distinct summary.
- **Level:** 3 (decides how a member enters the judge; a declaration is config, never a stored row).
- **Files touched:**
  - config/judges/summary-fidelity-judge.json (the settings of F1 and of the RC rows that name this file; metrics with the members of Table RA at their landing status, weights and rho)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py (new: SummaryFidelityJudgeConfig and MemberDeclaration, unknown keys refused, no field defaulted; MetricLifecycleStatus (active, paused, retired), a set of its own; Role, Statistic, Transform and AdjustBy; imported only by backend/idhazh/summary_fidelity_judge/settings.py, never by backend/idhazh/config.py or a knobs re-export)
  - backend/idhazh/summary_fidelity_judge/settings.py (new: loads and validates the file)
  - backend/idhazh/summary_fidelity_judge/registry.py (new: binds each active or paused member to its statistic and comparisons; the refusals of G1.3)
  - backend/idhazh/summary_fidelity_judge/windows.py (new: the eval ledger read through ledger.load_days for the recent window, the lag and the baseline; one row per distinct summary, the newest by url_key; a row whose column is null is left out and counted for scored_nulls (RA11))
  - backend/idhazh/summary_fidelity_judge/tenant.py (run_shard reads the settings and the windows)
  - backend/tests/summary_fidelity_judge/test_settings.py, test_registry.py and test_windows.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md (the settings, the member fields, the roles, and how to add a member)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/; CI - full suite.
- **Oracle:** the committed file loads and binds every member of Table RA; a file with an unknown key or a value outside its declared range is refused naming the key; each refusal of G1.3 fires by name on a written bad declaration, before any night runs; a windows fixture with a duplicated summary, a null column and a day with no run reads one row per summary, counts the null and skips the missing day. Cannot settle: whether the members of Table RA suit a reader failure nobody has declared yet; a new statistic is still a module, its tests and a review.

Table F1 - the settings this plan declares in config/judges/summary-fidelity-judge.json (named once here or in Table RC; every row points to one of the two)

| # | Setting | Default | Allowed range | Meaning | Lands in | Source |
| --- | --- | --- | --- | --- | --- | --- |
| F1.1 | recent_days | 7 | 7 to 14, whole weeks | Days in the recent window, ending on the judged night | 15 | Owner, 2026-10-11 (QQ5); RC1 |
| F1.2 | baseline_days | 56 | 14 to 91, whole weeks | Days in the baseline window, ending baseline_lag_days (RC13) before the judged night | 15 | Owner, 2026-10-11 (QQ6); RC2 |
| F1.3 | min_articles | removed | - | Replaced by min_day_rows (RC4) and the valid-day minimums (RC5) | - | Owner, 2026-10-11 (QQ6) |
| F1.4 | min_window_rows | removed | - | Replaced by min_recent_days and min_baseline_days (RC5) | - | Owner, 2026-10-11 (QQ6) |
| F1.5 | short_tail_percentile | removed | - | Removed with unusually short articles (RC12) | - | Owner, 2026-10-11 (QQ1) |
| F1.6 | reshuffle_stop_hits | 10 | 1 to 100 | The shared whole-day deals stop once every tested row of the family, the combined score included, has this many deals at least as extreme as its own (a tie counts) | 15 | Owner, 2026-10-11 (P4) |
| F1.7 | reshuffle_cap_floor | 100000 | 1000 to 10000000 | The smallest cap on deals per family | 15 | Owner, 2026-10-11 (P4) |
| F1.8 | reshuffle_cap_multiple | 10 | 1 to 100 | The cap is the larger of reshuffle_cap_floor and this times the family's tested rows divided by false_discovery_rate, minus one | 15 | Owner, 2026-10-11 (P4) |
| F1.9 | multi_tenant_hosts | removed | - | Removed with site identity (RC12) | - | Owner, 2026-10-11 (QQ1) |
| F1.10 | page_types | removed | - | Removed with site identity (RC12) | - | Owner, 2026-10-11 (QQ1) |
| F1.11 | false_discovery_rate | 0.05 | 0.001 to 0.2 | Target share of false crossings among the rows that cross, per family; 0.01 is the approved fallback when the replay's typical night exceeds crossings_budget (C5) | 8 | Owner, 2026-10-11 (QQ7, P23) |
| F1.12 | crossings_budget | 10 | 1 to 100 | The most crossed rows a person reads in one night: the panel lists this many, smallest q_value first, and counts the rest, and row #8's replay is held to it | 8 | Owner, 2026-10-11 (E1) |
| F1.13 | metrics | The members of Table RA | Closed words for role, statistic, transform, adjust_by and harm direction; combine_weight 0 to 10; rho 0 to 0.8; optional on a member: replaces (the member it takes over, QQ31; Y3.8), min_day_rows (10 to 1000, in place of RC4; X3.6) and tuning_pinned (true or false; X4.7); the refusals of G1.3 | The named list of members (RC11) | 4 | Owner, 2026-10-11 (separate what from how; P13, P21, QQ2, QQ9) |
| F1.14 | long_baseline_weeks | removed | - | Replaced by anchor_days (RC31) | - | Owner, 2026-10-12 (QQ18) |
| F1.15 | long_window_days | removed | - | Replaced by anchor_look_every_days (RC32) | - | Owner, 2026-10-12 (QQ18) |

Every other setting of this file is named once in Table RC (Section 4): RC3 to RC10, RC13 to RC21 and RC31 to RC33. RC22 to RC30 and RC34 to RC38 belong to the files their notes name.

Table F2 - decisions (made for the settings file in the collapsed row #2)

| # | Decision | Authority |
| --- | --- | --- |
| F2.1 | One settings file per judge under config/judges/, loaded only by that judge, so its numbers never enter the import closure of every module that reads config/idhazh.json | Owner, 2026-10-11 (P6) |
| F2.2 | Every field declares its allowed range. No loop ever writes this file: the scheduled replay files the weights and rho it tunes as rows in drift-evals-tuning, each change step-capped and inside the field's range, and the judge reads the latest applied row filed before the night it judges; a value pinned in this file is left alone | Owner, 2026-10-11 (every number in config, ready for autotune; P17; QQ27) |
| F2.3 | A site stays the host without www. | Retired with site identity (QQ1) |
| F2.4 | Page types group articles inside one site | Retired with site identity (QQ1) |
| F2.5 | A site key is printed inside a code span wherever text reaches a page | Retired with site identity (QQ1); the rule of Guardrail #11 for any address text still holds |
| F2.6 | Combine weights start from reader harm and are tuned only on the replay's injected faults and reshuffled dates, never on live crossings; the scheduled replay applies them within guards (QQ27), and the starting weights stay in this file | Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P17, QQ9, QQ27) |

Table F3 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F3.1 | A block in config/idhazh.json, as the content-similarity judge's settings once were | AppConfig is in the council's import closure, so the block would be a judge contract crossing it, which llm-council.md says cannot grow (C9) | One block in AppConfig and its changelog entry | Owner, 2026-10-11 (P6) |
| F3.2 | Constants in the judge's modules | Guardrail #6 refuses a hard-coded threshold, and tuning cannot move a constant | One edit per module; every tuning needs a code change and a review | CLAUDE.md Guardrail #6 |
| F3.3 | Group by registered domain | Retired with site identity (QQ1) | None | Owner, 2026-10-11 (QQ1) |
| F3.4 | Page types as separate sites | Retired with site identity (QQ1) | None | Owner, 2026-10-11 (QQ1) |

Table G1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| G1.1 | A member declaration says what is measured; the statistic and the one test (row #15) say how it is tested; a comparison says which windows are set against each other. A new member of an existing statistic is a config change (Level 3); a new statistic or comparison is a module, its tests and a review | Owner, 2026-10-11 (separate what the judge measures from how; P13); CLAUDE.md section 14; Fowler and Andre (debated 2026-10-11) |
| G1.2 | One test for every member: the recency-weighted whole-day test (row #15). Statistics: logit_mean (faith_index), share_past_line, mean and median. Comparisons: trailing (row #15) and anchor (row #14). The combined score is its own row (row #13) | Owner, 2026-10-11 (QQ5, QQ8); owner, 2026-10-12 (QQ18) |
| G1.3 | The loader refuses, naming the member and the field, before any night runs: a statistic or comparison no module serves; a column the eval row lacks or types otherwise than the statistic reads; an adjust_by the rule does not know; a line outside the column's range; a transform its column can fail; a repeated slug, retired members included; the reserved name combined_score; a combine_weight above 0 on a watched, evaluator or shown member; a rho outside 0 to 0.8 | Fowler (reviewed 2026-10-11); owner, 2026-10-11 (P13, QQ8, QQ9) |
| G1.4 | A member's meaning - column, statistic, line, transform, adjustment and harm direction - is never edited: a change is a new slug, and the old member turns retired and stays in the list as the record, so one check_name keeps one meaning across every stored row. A member names its statistic and comparisons with closed words, never a module or a path | Fowler (reviewed 2026-10-11); owner, 2026-10-11 (P13) |
| G1.5 | A new member lands paused with weight 0 and rho 0: tested and stored with its p_value and no q_value (H2.6). The scheduled replay promotes it automatically when it passes QQ28's guards (row #33), and a member that replaces another for the same reader harm takes over its predecessor's starting weight (QQ31). The members of Table RA land at the status RA gives them | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P13, QQ28); owner, 2026-10-11 (QQ31) |
| G1.6 | A series is one production model with one instrument per column. Every recorded change - model, prompt, quantization, runtime build, scorer - is a series boundary; a declared expected shift restarts only the members it lists (row #42); nothing is compared across a boundary, and a young series reads new_series (H2.7) | Owner, 2026-10-10 (R4); owner, 2026-10-11 (P14); owner, 2026-10-12 (QQ19) |
| G1.7 | Until row #37 stamps each scored column, a member whose column follows the faithfulness scorer or METRICS_VERSION takes scorer_version as its instrument, so a move of either starts a new series (P14) | docs/concepts/evaluation.md (METRICS_VERSION "is folded into scorer_version"); owner, 2026-10-11 (P14); owner, 2026-10-11 (QQ15) |
| G1.8 | A day with fewer than min_day_rows scored rows is thin and left out, never filled in; a night whose windows hold too few valid days stores too_few_days, so a stopped instrument never reads as a quiet week | Owner, 2026-10-11 (QQ6) |
| G1.9 | The judge reads no determinism_violation value: production never sets it, and a reader would hold back its removal (B9) | Owner, 2026-10-11 (determinism is not an expectation) |
| G1.10 | Rows flagged extraction_suspect leave the judged members and count in the input-mix diagnostic; a source the feed-quality plan flags will leave them too once that plan's record exists | Owner, 2026-10-11 (QQ2); owner, 2026-10-12 (QQ17) |

Table G2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G2.1 | check_name as a closed list in the row contract | Every new member would be a stored-shape change (C1) and a console edit, and a rules_version raised by hand can be forgotten | One list value, one console copy and one changelog line per member | Fowler (reviewed 2026-10-11); owner, 2026-10-11 (P13) |
| G2.2 | One module per member | A new member of an existing statistic would copy a test module, and what is measured would change together with how it is tested | None | Fowler and Andre (debated 2026-10-11) |
| G2.3 | A declaration that names its module or path | A config value would choose the code that runs (idhazh-gardener.md) | One field per declaration | Fowler (reviewed 2026-10-11) |
| G2.4 | A row comparing a series with a replaced scorer's series inside the step | It measures the scorer as well as the pipeline: "Slicing costs a long article 0.40 of its score" (docs/concepts/evaluation.md) | None | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P14) |
| G2.5 | page_furniture with no scorer split | Retired with page_furniture (QQ1); the rule that a METRICS_VERSION move starts a new series stays in G1.7 | None | Owner, 2026-10-11 (P14) |

### Row #5 - Count kind: article count from the item-health census (collapsed)

Collapsed on 2026-10-11 by QQ1 (A1, RB10): the number of articles a day is feed volume, not summary quality. Feed counts stay with feed-health and the autotune-feed-quality plan (B4, B13).

### Row #6 - Share kinds: unusually short and page furniture (collapsed)

Collapsed on 2026-10-11 by QQ1 (A1, RB10): article length and page furniture are input properties. Article length only adjusts, and the extraction_suspect rate is shown in the input-mix diagnostic (RA12; G1.10). The decision below is kept for the ruling that cites it.

Table J1 - decisions kept for citation

| # | Decision | Authority |
| --- | --- | --- |
| J1.3 | A share is taken so that a mix moving toward a different kind of article does not cross; in the ruled design the length-band and source adjustment does this (row #7, K1.4) | Owner, 2026-10-11 (P11); owner, 2026-10-11 (QQ1) |

### Row #7 - Per-summary values, daily values and the mix adjustment

- **Scope:** for every scored summary in the windows, member_values.py computes each member's value from the eval row: the logit of hhem clipped at logit_clip (RC7) for faith_index, an indicator past the member's line for a share, extractiveness, summary words and the evaluator's null count. For judged members, expected_values.py takes the expected value as the baseline mean of the summary's length band (length_band_edges_words, RC8) plus its source's offset shrunk toward zero by source_shrinkage_rows (RC9), and the residual is what is left; hedges_dropped also adjusts for whether the article hedges (RA5); watched members are never adjusted. daily_values.py turns residuals into one value per member per day (the median for length_median) with the day's row count, leaves out a day under min_day_rows as thin, and computes the shown diagnostics of RA12 (coverage, coherence, the input mix).
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity_judge/member_values.py (new)
  - backend/idhazh/summary_fidelity_judge/expected_values.py (new: the length band and the shrunk source offset, fitted on the baseline days only)
  - backend/idhazh/summary_fidelity_judge/daily_values.py (new: daily values, row counts, thin days, the shown diagnostics)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (min_day_rows, logit_clip, length_band_edges_words, source_shrinkage_rows, trailing_line_quantile; RC4, RC7 to RC10)
  - backend/tests/summary_fidelity_judge/test_member_values.py, test_expected_values.py and test_daily_values.py (new)
  - backend/tests/summary_fidelity_judge/fixtures/issue_1270_window.json (new: the #1270 mix change, copied from the committed eval ledger, with each summary's article length, source and scores)
  - docs/architecture/publishing/summary-fidelity-judge.md (the adjustment, with the formula of Section 4)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/; CI - full suite.
- **Oracle:** on the #1270 fixture, where the mix moved toward one kind of article and nothing moved inside a length band or a source, the raw daily faithfulness moves and the adjusted daily value does not move beyond its stated noise (C6); a fixture where every band loses the same planted amount shows that amount in the adjusted values; a source with 3 baseline rows gets exactly 3 / (3 + 10) of its raw offset; a test holds length_band_edges_words to the scorer's window geometry (chunk_words, and chunk_words plus chunk_words minus chunk_overlap_words); a thin day is left out and counted; extraction_suspect rows leave the judged members and count in the input-mix diagnostic. Cannot settle: a covariate the adjustment does not know, such as topic; the shown input mix lets a person see one.

Table K1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| K1.1 | The unit is the whole digest per production model series; article length and source only adjust a value and are never judged | Owner, 2026-10-11 (QQ1, P20); research record section 6.3 |
| K1.2 | The expected value is the baseline mean of the summary's length band plus its source's offset, shrunk toward zero by source_shrinkage_rows, fitted on the baseline days only so the recent week cannot explain itself away; watched members are never adjusted, because adjusting output behaviour would hide real change | Andre (reviewed 2026-10-11); owner, 2026-10-11 (QQ2, QQ5); research record section 6.3 |
| K1.3 | A day is the unit a value is computed for: per-summary residuals become one daily value per member, weighted later by the day's row count, and a day under min_day_rows is thin and left out | Owner, 2026-10-11 (QQ6); review record, finding C |
| K1.4 | A mix that moves toward a different kind of article cannot read as drift: each summary is compared with its own length band and source. This replaces the per-type distance of the 2026-10-11 draft (P11) | Owner, 2026-10-11 (P11, QQ1, QQ5) |
| K1.5 | No setting seeds the deals: each unit makes one generator from operating-system entropy, never from a constant or the clock, so no loop can choose a draw; a p-value near the cut may differ between two runs of a night, and a reader takes the latest run (H4.5) | Owner, 2026-10-11 (determinism is not an expectation); Fowler and Andre (reviewed 2026-10-11) |
| K1.6 | The judge reads committed eval rows only, through ledger.load_days, bounded to the days its windows span | CLAUDE.md Guardrail #12; owner, 2026-10-10 (R1) |

Table K2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K2.1 | Judge each site's articles | Per-site cells are too small to test, and the one summarizer-side change on record moved inside sources (99 sources in both weeks moved -0.101 against -0.103 overall) | Per-site series and their false alarms | Owner, 2026-10-11 (QQ1); review record, Andre 1.1 |
| K2.2 | Compare raw daily medians with no adjustment | A change in the mix of article lengths reads as drift, the #1270 failure | None | Owner, 2026-10-11 (QQ5); issue #1270 |
| K2.3 | Adjust watched members too | Copying and summary length are the summarizer's behaviour; adjusting them would hide the change they exist to show | None | Owner, 2026-10-11 (QQ2); research record section 6.3 |

Table L1 - decisions of the 2026-10-11 draft kept for citation

| # | Decision | Authority |
| --- | --- | --- |
| L1.1 | Wasserstein-1 with a permutation p-value for hhem and extractiveness | Retired: one recency-weighted whole-day test serves every member (row #15; QQ5) |
| L1.2 | A deliberate change is never a crossing: every recorded change starts a new series, and nothing is compared across it (row #42) | Owner, 2026-10-10 (R4); owner, 2026-10-12 (QQ19) |
| L1.3 | A pair with 1 to 19 baseline articles is compared with earlier pairs | Retired: a young series reads new_series until its windows hold enough valid days (H2.7; QQ6, QQ19) |

### Row #8 - One false-discovery step per (run, date, series), and the replay with a planted-fault library

- **Scope:** settle builds one family per (run_id, date, model series): every tested row of an active judged, watched or evaluator member and, once row #13 lands, the combined_score row; paused and shown rows stay out. It applies the Benjamini-Hochberg step-up at false_discovery_rate (F1.11) and stores each row's q_value and outcome. A replay utility runs the unit over stored nights: on the quiet record, to count false crossings and stretches against crossings_budget (C5); and with the planted-fault library, to measure detection within a week. The same engine serves the scheduled tuning and promotion (rows #32 and #33), the key-fact pilot (row #31) and the grounding judge's planted-fault test (row #35).
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity_judge/false_discovery.py (new)
  - backend/idhazh/summary_fidelity_judge/tenant.py (settle applies the step before filing)
  - backend/idhazh/summary_fidelity_judge/planted_faults.py (new: each fault rewrites stored rows - a share of summaries made unfaithful, one source's summaries made unfaithful, unsupported numbers doubled, hedges dropped, and one declared fault per member - and never calls a model)
  - backend/utilities/summary_fidelity_replay.py (new: the operator utility and the engine rows #31 to #35 call)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (false_discovery_rate, crossings_budget)
  - backend/tests/summary_fidelity_judge/test_false_discovery.py, test_planted_faults.py and test_replay.py (new: a tmp_path ledger with two judged nights, read through ledger.load_days)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/; CI - full suite. Observation, not a gate: the replay over every stored night since the first scored day (2026-08-22), on the quiet record and with each planted fault, recorded in the pull request as crossings and stretches per night, false crossings per month at false_discovery_rate 0.05 and 0.01, and detection within a week per fault; it re-measures RD3 and RD4, which were measured on a 28-day baseline.
- **Oracle:** for the textbook input of ten p-values the step keeps exactly the step-up set and stores the matching adjusted values; a night with no tested row still files every row, with no q_value; a paused or shown row keeps its p_value, gets no q_value and moves no other row's q_value; two runs or two model series never share a family; each planted fault changes exactly the rows and the amount it declares. Cannot settle: crossings that are real but too small to matter; the stored effect lets a reader rank them.

Table M1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| M1.1 | Every tested row hands the step its p-value; the step is the only threshold, and no row is cut before it | Owner, 2026-10-10 (R2) |
| M1.2 | One family per judged night within one council run and one model series, the (run_id, date, model series) triple; two runs of a night are two families, and a repair night judged on the same run is a family of its own | Owner, 2026-10-11 (P1, QQ8); Fowler and Andre (reviewed 2026-10-11) |
| M1.3 | The replay reads through ledger.load_days, one judged night at a time (Guardrail #12) | Fowler (reviewed 2026-10-10: keep) |
| M1.4 | The deals stop early and their cap follows the family size (F1.6 to F1.8; row #15) | Owner, 2026-10-11 (P4) |
| M1.5 | The reading budget (C5) counts new stretches, not crossings: a typical night is the mean number of new stretches (H4.9) per judged night after the first seven; the count is split by member, a member that crosses on reshuffled nights, where nothing changed, more often than false_discovery_rate is fixed first, and false_discovery_rate 0.01 is the second lever | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P18, QQ7) |
| M1.6 | One replay engine serves every automatic step that needs evidence from history - tuning, promotion, the key-fact pilot and the grounding judge's planted-fault test - so each is measured the same way | Owner, 2026-10-11 (A7, QQ27, QQ28); owner, 2026-10-11 (QQ16) |
| M1.7 | Planted faults are built from stored rows and never by calling a model, so the replay needs no server and no test expects a model to repeat itself | CLAUDE.md Guardrails #7 and #10; owner, 2026-10-11 (determinism is not an expectation) |

Table M2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M2.1 | Bonferroni | A person reading a short list needs the false share bounded, not the chance of any false crossing | Fewer crossings at the same error target | Andre (reviewed 2026-10-10: keep) |
| M2.2 | DuckDB over state/compact/ as the blueprint writes | Days not yet compacted exist only as raw files; re-runs count twice; Guardrail #12 forbids the glob | None | Owner, 2026-10-10 (R1) |
| M2.3 | The pasted composite: per-measure penalties from raw relative median changes, a weighted sum, bands at 0.2 and 0.4 and a veto at 0.8 | Fixed lines on raw medians ignore sample size and spread: in simulation it went red on 19 percent of unchanged nights at a small site, stayed green for a 79 percent length cut and a faithfulness fall from 0.85 to 0.40, and scored 0.18 on the #1270 mix change alone | None: declarations keep the extensibility (row #4) and combined_score the joint detection (row #13) | Andre and Fowler (debated 2026-10-11); owner, 2026-10-11 (P15, QQ8) |
| M2.4 | Automatic actions from a score on what is published or fetched: quarantine a source, demote its rank, raise the repetition penalty, add prompt text, rewrite a low-scoring summary | The judge would steer what it measures, and quarantine and demotion are coverage calls; the automatic responses the owner approved later touch nothing published (QQ29), and the publish gate acts per summary on fixed lines, never on a crossing (B1, B2) | A real defect publishes until a person or the gate acts | Andre and Fowler (debated 2026-10-11); owner, 2026-10-11 (P15, QQ29) |

### Row #9 - The switch: the judge joins the council

- **Scope:** lifecycle_status turns active in config/judges/summary-fidelity-judge.json by the owner's named decision, recorded in the commit message and on the judge's page, never in a test ([activation rule](../docs/architecture/publishing/llm-council.md#design-rationale-a-new-judge-starts-paused)), so the next nightly run judges yesterday on a cell with no model server (runs_model false) and files its rows. No statistics extra is installed (QQ20). The switch waits for rows #1 and #8: the old review is gone, and the replay's typical night is within crossings_budget (C5).
- **Level:** 3 (starts a nightly committed write).
- **Files touched:**
  - config/judges/summary-fidelity-judge.json (lifecycle_status active)
  - docs/architecture/publishing/llm-council.md (the judge list names two active judges)
  - docs/architecture/publishing/summary-fidelity-judge.md (the activation, dated, with the replay's numbers)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/council/ and backend/tests/summary_fidelity_judge/; CI - full suite. Observation, not a gate: the first scheduled night, read for rows stored, crossings and the unit's run time on a cell with no model server; peak memory is not read (QQ21); when it stores nothing, read the collecting job's log first.
- **Oracle:** a council night driven end to end with both judges active fans out one cell for this judge per date, with runs_model false, and the collecting job commits its raw file under state/raw/summary-fidelity-judge/drift-evals/ beside the other judge's files. Cannot settle: the first live night's run time against the council's clock.

Table N1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| N1.1 | The judge's lifecycle_status in its own config file is the switch: row #3 registers it paused and model-free, and this row makes it active by the owner's named decision; no separate flag and no test enforces the activation decision | [Activation rule](../docs/architecture/publishing/llm-council.md#design-rationale-a-new-judge-starts-paused); Q35, Q36 |
| N1.2 | The council's nightly schedule replaces the daily schedule the drift plan asked for; this judge names no repair date until the council plan's row 'Each judge runs over its own outstanding dates' lands (B8) | Owner, 2026-10-10 (R6); Fowler (reviewed 2026-10-11) |
| N1.3 | A person judges a past date by dispatching the council workflow with that date | llm-council.md ("A dispatched date replaces the plan outright") |

Table N2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N2.1 | A workflow of the judge's own | The council already provides the schedule, the repair window, one commit path and the writer identity | A second scheduler, commit path and identity to keep correct | Owner, 2026-10-11 (run it as a council judge) |

### Row #12 - The stored checks on the Summaries page

- **Scope:** drift-evals joins ledger.published so the console's Data explorer can query its compact files, and one panel on the Summaries page (/console/model/) lists the newest council run's crossed rows by reading level - evaluator check, then drift, then watch (row #13) - smallest q_value first within a level, at most crossings_budget (F1.12) rows, counting the rest, and draws consecutive nightly crossings of one key as one stretch (H4.9). Each crossed row prints its effect raw and adjusted, its q_value and the inputs that changed inside its window (QQ29). The publish gate's panel (row #24) sits beside it (QQ14).
- **Level:** 3.
- **Files touched:**
  - config/idhazh.json (ledger.published gains drift-evals)
  - frontend/src/routes/console/model/+page.server.ts and frontend/src/routes/console/model/+page.svelte (the Summaries route)
  - frontend/src/lib/server/ledger-rows.ts (a build-time reader of the drift-evals compact files, beside evalRows and itemHealthRows)
  - frontend/src/lib/server/config.ts (reads crossings_budget from config/judges/summary-fidelity-judge.json)
  - backend/tests/contracts/test_frontend_vocabularies.py and backend/tests/contracts/test_frontend_field_set.py (the hand copy of H2, Role, Statistic, Comparison, Direction, ValueUnit and the fields the panel reads; check_name prints as stored, so a new member needs no console edit)
  - backend/tests/contracts/test_panel_queries.py and backend/tests/contracts/test_frontend_console_lists.py (re-derive at dispatch)
  - config/console/model.json (the panel's own settings, if the page keeps them there; re-derive at dispatch)
  - docs/concepts/growing-reads.md (the reader and its window) and docs/architecture/publishing/console.md
- **Acceptance gates:** local - the frontend checks and the contract tests through the shared selector; CI - full suite.
- **Oracle:** a fixture of compact rows with seven consecutive nightly crossings of one key renders one stretch; a fixture where a later council run re-judged a night shows that run's rows only; rows render grouped by level and ordered by q_value; a fixture with none renders the empty state. Cannot settle: whether the panel is read.

Table T1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| T1.1 | The Data explorer is the first view; the panel follows | Owner, 2026-10-10 (visualisation is secondary) |
| T1.2 | The Summaries page carries this panel and the publish gate's panel beside it, and the ledger's compact files are published on the site | Owner, 2026-10-11 (P5); owner, 2026-10-11 (QQ14) |
| T1.3 | Rows are grouped by reading level, evaluator check first, because an instrument fault must be read before anything is called drift; the combined_score row is listed in its level with the members that moved beside it | Owner, 2026-10-11 (QQ8, P15) |
| T1.4 | The panel prints numbers, member names and recorded input names only, never article or summary text | Owner, 2026-10-11 (QQ14); CLAUDE.md Guardrail #11 |

Table T2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| T2.1 | A page of its own | The owner ranked the view second to the stored record, and the Summaries page already reads the score and item-health ledgers | A route, its navigation entry and its own tests | Owner, 2026-10-10; owner, 2026-10-11 (QQ14) |

### Row #13 - The combined score and the reading levels

- **Scope:** settle adds the combined_score row to each family: over the active judged members $Q$, each standardised score $z_m$ oriented so that positive means worse, with weights $w_m$ and $R$ the correlation of the members' standardised daily values over the baseline days, $C = \sum_{m \in Q} w_m z_m / \sqrt{w^{\top} R w}$, tested one-sided for worse with its p-value from the same deals as the members (row #15). Weights start from reader harm - faithfulness 3 split over its three members, unsupported numbers 3, dropped hedges 2 - and are never negative; each member's rho starts where the replay puts it; both are tuned later within guards (row #32). reading_levels.py derives each night's level from stored rows: evaluator check, drift (the combined score or a judged member crossed on drift_consecutive_nights consecutive nights), watch, or quiet, too few days or new series. The replay gains faults planted in several members at once.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity_judge/combined_score.py (new)
  - backend/idhazh/summary_fidelity_judge/reading_levels.py (new: the level of a night from stored rows; the panel (row #12) and the automatic responses (row #34) read it)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (combine_weight and rho per member; drift_consecutive_nights, RC6)
  - backend/idhazh/summary_fidelity_judge/planted_faults.py and backend/utilities/summary_fidelity_replay.py (faults planted in several members at once)
  - backend/tests/summary_fidelity_judge/test_combined_score.py and test_reading_levels.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md (the combined score with its formula, and the reading levels)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/; CI - full suite. Observation, not a gate: row #8's replay over the stored nights with faults planted in several members, recorded in the pull request as combined_score crossings and levels per night.
- **Oracle:** three planted faults, each too small to cross alone, cross together in combined_score; an improvement in one judged member offsets a harm of the same weighted size in another (the owner's choice); scaling every weight by one factor leaves the p-value unchanged; a judged member crossing on two consecutive nights reads drift and on one night watch; an evaluator crossing reads evaluator check whatever else crossed; the #1270 fixture's combined row does not cross (C6). Cannot settle: which member moved, which the member rows beside it show; a change no larger than the movement between days.

Table U1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| U1.1 | The all-sites comparison of the 2026-10-11 draft | Retired: the whole digest is the only unit (QQ1) |
| U1.2 | combined_score is the only combination that enters the step, filed in drift-evals with its night's family; a weighted score a reader computes later from stored rows has no p-value and enters no step | Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P15, QQ8) |
| U1.3 | Each member enters as its standardised score against the night's own deals; the correlation matrix keeps correlated members from counting twice, and the weights need not add to one, because scaling them all leaves the p-value unchanged | Owner, 2026-10-11 (QQ8); research record section 6.2 |
| U1.4 | Every member row stays in the step beside the combined row, so one severe slip crosses alone and is never averaged away; there is no band and no veto line | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P15) |
| U1.5 | The panel and the reading budget count the combined row by the same levels (T1.3) | Owner, 2026-10-11 (QQ8, P18) |
| U1.6 | Weights start from reader harm and are tuned only on planted faults and reshuffled nights, never on live crossings; the scheduled replay applies them within guards and records every proposal (row #32) | Owner, 2026-10-11 (P17, QQ9, QQ27) |
| U1.7 | Inside the combined score an improvement in one judged member offsets a harm in another; each member keeps its own verdict beside it | Owner, 2026-10-11 (QQ8) |
| U1.8 | Drift is the combined score or a judged member crossing on drift_consecutive_nights consecutive nights; any other crossing is watch; an evaluator crossing is read first, before anything is called drift | Owner, 2026-10-11 (QQ8); Section 4 |

Table U2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| U2.1 | Reshuffle single summaries rather than whole days | Crossed about 200 times its nominal rate under a shared day movement of 0.01 (simulation, 2026-10-11); days are overdispersed (review record, finding C) | None | Andre (reviewed 2026-10-11) |
| U2.2 | Scale tonight's effect by the series' own night-to-night history | Crossed 25 to 330 times the nominal rate at a cut of 3.89 standard units with no change (simulation, 2026-10-11) | None | Andre (reviewed 2026-10-11) |
| U2.3 | Two combined rows, quality_worse and something_changed | The owner chose one signed score; changes in copying and length reach a person as watch-level crossings of their own members | One more row and one more test per family | Owner, 2026-10-11 (QQ8; P24 declined) |

### Row #14 - The anchor comparison

- **Scope:** every anchor_look_every_days (RC32, 7) nights, each member that takes the anchor comparison sets the recent week against its series' frozen anchor - the series' first anchor_days (RC31, 56) valid days - by row #15's test, so a slow decline that drags the moving baseline along still crosses. The anchor's daily values are read back from the eval ledger, which keeps scored rows for 36 months, so nothing new is stored. A series' anchor looks start by themselves once it has anchor_days plus recent_days valid days, from about its ninth week; their rows land paused and join the step through QQ28's promotion (row #33), about weeks 13 to 17; a new series (row #42) starts a new anchor.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity_judge/comparisons/anchor.py (new)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (anchor_days, anchor_look_every_days; the members that take the anchor comparison)
  - backend/tests/summary_fidelity_judge/test_anchor.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/; CI - full suite.
- **Oracle:** a committed fixture with a steady decline over 20 weeks crosses on the anchor where the trailing comparison does not, with row #15's margins; a series with fewer than 63 valid days stores too_few_days on its anchor rows; a night off the look cadence stores no anchor row; a new series reads a new anchor. Cannot settle: a decline that began inside the anchor's own days; a change in the mix of articles the adjustment does not know.

Table V1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| V1.1 | One look per anchor_look_every_days, so looks never share recent days and the step's bound per night holds for anchor rows too | Andre (reviewed 2026-10-11); owner, 2026-10-12 (QQ18) |
| V1.2 | The anchor is the series' own first anchor_days valid days of stored scores, tested by the same test as the nightly comparison, so a look tests what a nightly look tests; QQ18's stored scores are the eval ledger's, which keeps scored rows for 36 months, so no new record is stored | Owner, 2026-10-12 (QQ18); research record section 6.3 (a long-baseline anchor made of stored scores) |
| V1.3 | Anchor rows land paused and join the step only through QQ28's promotion; a series restarted by a recorded change gets a new anchor | Owner, 2026-10-11 (QQ28); owner, 2026-10-12 (QQ18, QQ19) |

Table V2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| V2.1 | Nightly long looks, or a 12-week baseline | Nightly looks crossed 4 times as often with no change; 12 weeks caught a 40 percent yearly decline 9.7 percent of the time | Faster detection | Andre (reviewed 2026-10-11) |
| V2.2 | A cumulative sum over the judge's nightly effects | Overlapping windows count one excursion many times (a false alarm by week 6 in simulation), and it has no p-value for the step | Its own false-alarm calibration | Andre (reviewed 2026-10-11) |
| V2.3 | A before-and-after comparison at every recorded input change | No window may turn on the input record; QQ19 restarts the series at a recorded change instead of comparing across it | None | Andre (reviewed 2026-10-11); owner, 2026-10-12 (QQ19) |
| V2.4 | Re-score live items with one input swapped (metamorphic checks) | Needs extra scorer passes in the scoring job, a new eval-row field (Level 5) and a cost measurement first | Extra scorer passes per scored run, not measured | Andre (reviewed 2026-10-11) |
| V2.5 | The one-year comparison of the 2026-10-11 draft | It needs one series 56 weeks old, and every recorded change restarts a series | Out of scope until one series has 56 weeks of history (B14) | Owner, 2026-10-12 (QQ18) |

### Row #15 - The recency-weighted whole-day test

- **Scope:** for each member and comparison, comparisons/trailing.py sets the recent window $R$ (recent_days ending on the judged night $t$) against the baseline $B$ (baseline_days ending baseline_lag_days before $t$), each holding only its valid days; a member is tested only when $R$ holds min_recent_days and $B$ min_baseline_days valid days, and otherwise stores too_few_days, or new_series when its series started inside the windows. whole_day_test.py computes the statistic of Section 4 - recent days weighted by $a_d = \lambda (1 - \lambda)^{t - d}$ and row count, baseline days by row count, signed by harm direction - and standardises it against whole-day deals, widened by the member's rho. day_deals.py deals the whole days of $R \cup B$ into the two windows, the same deal for every member and the combined score, stopping early under F1.6 to F1.8.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity_judge/comparisons/__init__.py and backend/idhazh/summary_fidelity_judge/comparisons/trailing.py (new)
  - backend/idhazh/summary_fidelity_judge/whole_day_test.py (new: the statistic, its standardisation and the p-value)
  - backend/idhazh/summary_fidelity_judge/day_deals.py (new: the shared deals, the early stop and the cap; one generator from operating-system entropy per unit, K1.5)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (recent_days, baseline_days, baseline_lag_days, recency_lambda, min_recent_days, min_baseline_days and the reshuffle settings; F1.1, F1.2, F1.6 to F1.8, RC3, RC5, RC13)
  - backend/tests/summary_fidelity_judge/test_trailing.py, test_whole_day_test.py and test_day_deals.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md (the windows and the test, with the formulas of Section 4)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/; CI - full suite.
- **Oracle:** with recency_lambda 0 the statistic equals the row-weighted flat difference exactly; a recent week with 3 valid days stores too_few_days, and a series that started 10 days before the night stores new_series naming its change; every member's p-value in one night comes from the same deal indices; a planted step of 3 standard units in the recent week gets a p-value under 0.01, and nights drawn from a quiet stretch of the committed record get p-values under 0.05 no more often than their binomial noise allows, each assertion kept at least 10 times inside its bound and measured once with at least 1,000 hits (Guardrail #10). Cannot settle: the false-crossing rate on live nights, which row #8's replay measures.

Table W1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| W1.1 | The recency-weighted last week against the 56 days that end 8 days before the judged night, so one day separates the two windows and a slow drift does not become its own baseline; recency_lambda 0 makes the week flat | Owner, 2026-10-11 (QQ5, QQ6); research record section 6.3 |
| W1.2 | Whole days are dealt, never single summaries: days are the exchangeable unit, and the deals keep every day-level dependence between members | Owner, 2026-10-11 (QQ5); review record, finding C; research record section 6.3 |
| W1.3 | A window holds only valid days: a day with no run, a failed run or a thin day is skipped, never filled and never replaced by an older day, and the row records the valid days used | Owner, 2026-10-11 (QQ6) |
| W1.4 | One deal set per night serves every member and the combined score, so their p-values are comparable and the combined score's calibration does not depend on its weights | Owner, 2026-10-11 (QQ8); Section 4 |
| W1.5 | Each member's score is widened by its own day-to-day correlation rho, proposed by the replay from quiet stretches and tuned within guards; a new member starts at rho 0 | Owner, 2026-10-11 (QQ9, QQ27) |
| W1.6 | Every number of the test is a setting with a declared range, so another test type can join later as a module a declaration selects | Owner, 2026-10-11 (QQ5, P13) |

Table W2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| W2.1 | A flat week against the 28 days before it, as the 2026-10-11 draft set | The research's lagged 56-day window keeps a slow drift out of the baseline; the record changed regime about every 9 days, which the windows' valid-day rule absorbs | None | Owner, 2026-10-11 (QQ6) |
| W2.2 | Fitted floors per metric, as plan 36 designed | A fitted floor says where the low tail sits, not whether a night moved beyond chance; limits from a reference window alone crossed 4.5 to 53 times their nominal rate in simulation | None | Owner, 2026-10-11 (QQ3); RE7 |
| W2.3 | A self-starting or cumulative chart in place of the windowed test | Slow drifts can be absorbed into its running baseline, and it gives no p-value for one false-discovery step; it may join later as a test module (W1.6) | Its own calibration | Research record section 6.1; owner, 2026-10-11 (QQ5) |

### Row #18 - Plan 36 row #3: EvalRow gains publish_decision and withheld_reason, and the stamp tells a record-only would-be withhold from a real one

- **Scope:** The eval row (contract eval-row, ledger summary-quality-evals) gains two columns, appended after the last one as the file's layout rule asks, each with a default, so every file and sealed payload written before them reads back as published with no reason. publish_decision is published, would_be_withheld (the summary failed a line that may withhold while that line was record-only, so it published) or withheld (it failed a live line and is absent from the day). withheld_reason is null or the line that decided: unsupported_number, or lowest_sentence_faithfulness (reserved for row #39; nothing stamps it before). The whole-summary faithfulness score is not a gate line: its only stamp is the display band the eval row already carries (band low under evaluation.band_medium_min). No geval column. Expand only: nothing writes a non-default value until row #22.
- **Level:** 5 (two persisted columns that later runs and every reader of the eval ledger read; the owner's one approval of plan 65 (QQ26) signs the shape off, and plan 36's approval of 2026-09-19 does not carry).
- **Files touched:**
  - backend/idhazh/contracts/eval_row.py (PublishDecision and WithheldReason, two closed sets; publish_decision, default published, and withheld_reason, default null, appended after semantic_coverage; a validator that refuses a stamp that contradicts itself; one changelog entry and the version, keeping five entries as CLAUDE.md section 11 allows)
  - backend/tests/contracts/_fixtures.py (FIXTURE_FILES) and the eval-row fixtures in the folder it names: one stamped row, one row written before the change (re-derive at dispatch)
  - The contract and eval tests (re-derive at dispatch: git grep -l -e EvalRow -e eval-row backend/tests)
  - Every file that lists the eval row's columns by hand (re-derive at dispatch: git grep -n -e semantic_coverage -e self_repetition backend frontend docs)
  - docs/concepts/evaluation.md (the two columns, what each value means, and that a whole-summary mark never withholds and never fences)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/contracts/ and the eval tests named above; CI - full suite.
- **Oracle:** a raw eval file written before the change, and a sealed .eval.json payload from a run that spans the merge, read back through the ledger door and EvalRow.read as published with no reason; a stamped row round-trips through the door unchanged; the contract refuses would_be_withheld or withheld with no reason, and a published row with any reason. Cannot settle: whether anything ever stamps a summary (rows #22 and #23).

Table O1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| O1.1 | The stamp lives on the eval row, not on the published item: a withheld summary is absent from the day, and the eval row records every scored summary, the withheld included | Owner, 2026-10-11 (QQ12 C1); Fowler (plan 36 row #3 decision 1); owner, 2026-09-19 (plan 36 section 0e H1); plan 36 G12 |
| O1.2 | publish_decision has three values, so the stamp alone tells a record-only would-be withhold (would_be_withheld: it published) from a real one (withheld: absent from the day), with no join to the run's gate state | Owner, 2026-10-11 (QQ12 A1); Table D, row #18 |
| O1.3 | withheld_reason names the one line that decided. unsupported_number may withhold from the start; lowest_sentence_faithfulness is reserved now, so row #39 needs no second change to this shape. The whole-summary faithfulness score is not a gate line: its only stamp is the display band the eval row already carries, so it never makes a would-be withhold and never fences | Owner, 2026-10-11 (QQ12 B2, QQ13 B1, QQ15) |
| O1.4 | No geval column: plan 36's self-graded fluency is dropped | Owner, 2026-10-11 (QQ4 A1) |
| O1.5 | Both columns are appended after the last one with defaults, so a file or a sealed payload written before them reads as published with no reason, never refused | backend/idhazh/contracts/eval_row.py (the layout comment on the appended columns); CLAUDE.md section 11 |
| O1.6 | The contract checks the stamp against itself only: a would-be or real withhold needs a reason, and a published row carries none | Owner, 2026-10-11 (QQ12 A1, B2) |

Table O9 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O9.1 | A geval column for the summariser's own fluency grade | A model grading its own text favours it, on a dimension near its ceiling; rows #21 and #25 collapsed | A nullable column nothing writes | Owner, 2026-10-11 (QQ4 A1); research record section 2.3 |
| O9.2 | publish_decision as published or withheld, with downgraded reserved (plan 36 row #3) | A record-only would-be withhold and a real one would read alike without the run's gate state beside them, and the per-item downgrade band is empty by construction | Every reader joins the run's gate state to read one row | Owner, 2026-10-11 (QQ12 A1); Andre, 2026-09-18 (plan 36 E1) |
| O9.3 | The stamp on the published item | A withheld item is absent from the day, so nothing there can carry its stamp | A published contract field (Level 5) that could only ever read published | Fowler (plan 36 row #3 decision 1); owner, 2026-09-19 (plan 36 section 0e H1) |
| O9.4 | Refuse a stamp that disagrees with the row's own scores | corpus.rescored re-measures unsupported_numbers against a re-fetched body and carries the recorded stamp across, so the refusal would drop a rebuilt row the run stamped correctly | None | backend/idhazh/corpus.py (rescored) |

### Row #22 - Plan 36 row #7: the publish gate stamps every summary, record-only

- **Scope:** A veto chain over fixed lines stamps every scored summary in the work step, where score.to_eval_row composes its eval row. The lines, in order: an unsupported number (a figure the summary asserts that the article never gave), which may withhold from the start, and the lowest-sentence faithfulness line, off until row #39 switches it on. The whole-summary faithfulness score under the band's own 0.50 cut (evaluation.band_medium_min) only stamps, through the display band the eval row already carries; it is not a gate line. Every line is record-only here, so a summary that fails a line that may withhold is stamped would_be_withheld and publishes, and no published day changes. With each run, assemble counts the day's stories whose every summary the gate marked on a line that may withhold.
- **Level:** 5 (the run record in run.json gains the counts of stories that would be lost entirely, beside same_story_floor_applied - a persisted shape named here for the owner's single approval of the plan (QQ26); the stamp is row #18's shape, and nothing published changes).
- **Files touched:**
  - backend/idhazh/evals/publish_gate.py (new: the lines in order, each line's state, every one record-only in this row, and the stamp)
  - backend/idhazh/evals/score.py (to_eval_row takes the lines' states and stamps publish_decision and withheld_reason; verdict and the band are unchanged)
  - backend/idhazh/stages/work.py (hands to_eval_row every line as record-only)
  - backend/idhazh/stages/assemble.py (after the day is assembled, counts its stories whose every summary is marked, from this run's stamps and the date's earlier stamps read through the ledger door, one date)
  - backend/idhazh/assemble.py (the day's same-story groups the count reads; re-derive at dispatch: git grep -n "def collapse_same_story" backend)
  - backend/idhazh/contracts/run_manifest.py (RunRecord: the day's stories whose every summary the gate marked, and of those the ones whose every summary was withheld, zero until row #23; one changelog entry)
  - The score, work-stage and assemble tests (re-derive at dispatch: git grep -l -e to_eval_row -e stage_assemble backend/tests)
  - docs/architecture/publishing/autotune-summary-quality.md (the publish gate section to the rulings: fixed lines, a record-only stamp on every scored summary, no adaptive floor, no downgrade, no person's corpus turn)
  - docs/concepts/evaluation.md (what the gate stamps, and that a summary with no eval row carries no stamp)
  - config/judges/summary-fidelity-judge.json (the withheld_share member, RA13: the daily share stamped would_be_withheld or withheld, watched, landing paused and promoted like any member, Q39)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over the tests named above; CI - full suite.
- **Oracle:** built items stamp as the chain says: one unsupported number gives would_be_withheld with unsupported_number; a faithfulness score of 0.45 and no unsupported number gives published with no reason, and its low display band; both together give unsupported_number; a clean summary gives published with no reason; nothing stamps lowest_sentence_faithfulness; the record step and assemble read one stamp for one summary; the built day keeps every item; a day whose two duplicates of one story are both marked counts one story, and a marked summary with an unmarked duplicate counts none. Cannot settle: whether a line marks real failures, which row #23's guard and row #35's checker measure.

Table O2 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| O2.1 | A veto chain over fixed lines, never a composite: each line reads one summary's own score, and the stamp names the line that decided | Owner, 2026-10-11 (QQ3 A1, P39); Andre and Fowler, 2026-09-18 (plan 36 D4); research record section 7.4 (gates per summary, non-compensatory) |
| O2.2 | Unsupported number may withhold from the start; faithfulness may withhold only on the lowest-sentence line, which waits for row #37's score and row #39's switch and starts at 0.50; the whole-summary score only stamps, through the display band it already has, because scoring the whole summary against each window puts a 2-window article 0.22 and a 3-window article 0.40 below the same article read whole | Owner, 2026-10-11 (QQ12 B2, QQ15, P43); P31 evidence; research record section 4.2 |
| O2.3 | The whole-summary stamp is the display band itself (evaluation.band_medium_min), so no second stamp can disagree with it about one score | Owner, 2026-10-11 (QQ3 A1: fixed lines only); Andre and Editor, 2026-09-18 (plan 36 D3) |
| O2.4 | The band and its reason stay what score.verdict decides; the stamp is a second answer and changes no published field | Andre, 2026-09-18 (plan 36 E1) |
| O2.5 | The stamp is decided in the work step, never later: the work job's record step files the eval row before assemble files it again, and the eval ledger keeps the first row per key (url_key, output_digest, scorer_version) with no preference, so a stamp decided in assemble would leave two disagreeing rows for one summary | backend/idhazh/stages/record.py; backend/idhazh/ledger/keys.py (OBSERVATION_KEY); backend/idhazh/ledger/ledger_files.py (load_ledger_rows) |
| O2.6 | Record-only from the day this row lands; whether a line may act is decided by row #23's guards | Owner, 2026-10-11 (QQ12 A1) |
| O2.7 | One count, in assemble, from the day's own same-story groups, serves the record-only phase and the live one, so the panel never shows two rules for one number | Owner, 2026-10-11 (QQ12 C1, QQ14 B1); review record section 3, Table H (one answer per question) |
| O2.8 | No displayed overall is built: the drift judge's combined score is the one combination, and it feeds no action | Owner, 2026-10-11 (QQ8 A3); RE11; review record section 3, Table I, I7 |
| O2.9 | A summary with no eval row - a run not drawn at observability.sample_rate, or one whose scorer did not load - carries no stamp, so the gate never acts on it | backend/idhazh/stages/assemble.py (the branch for an unscored item); Q44 (sampling takes whole runs) |

### Row #23 - Plan 36 row #8: the gate withholds by itself while its guards hold and returns to record-only when one fails

- **Scope:** Each run's plan stage reads the gate's two guards for every line that may withhold, over the gate_trial_days (28) completed dates before the run: the share of that line's marked summaries that summary-grounding-judge checked and confirmed (row #35, counted only once it has caught planted unfaithful summaries, and only once at least gate_min_checks (30) of them were checked in the window) against gate_min_agreement (0.7), and every night's would-be withheld share against withhold_share_ceiling (0.25). A line is live while both hold and withhold_failing_summaries is true; the plan carries each line's state to the work shards, which stamp withheld and record the item failed under a new FailureCode. Assemble leaves a withheld summary out before collapse_same_story runs, so the story's next-best duplicate takes its place. Every switch is recorded with its reason.
- **Level:** 5 (the first change to a published day, signed off by the owner in QQ12; the switch record - each line's state, since when, why and the guard readings - is a persisted shape on the run plan, named here for the owner's single approval of the plan (QQ26)).
- **Files touched:**
  - backend/idhazh/evals/publish_gate.py (each line's state from withhold_failing_summaries and the two guards, and the reason for it)
  - backend/idhazh/stages/plan.py (reads through the ledger door the gate_trial_days completed dates before the run - grounding-verdicts (row #35) and the eval stamps - and decides each line's state once a run)
  - backend/idhazh/contracts/run_plan.py (the switch record, carried to the work shards and filed with the plan; one changelog entry)
  - backend/idhazh/contracts/knobs/evaluation.py and backend/idhazh/contracts/app_config.py (PublishGateConfig: gate_trial_days 7 to 91, gate_min_agreement 0.5 to 0.95, gate_min_checks 10 to 200, withhold_share_ceiling 0.05 to 0.5, withhold_failing_summaries with no default; one AppConfig changelog entry; re-derive at dispatch)
  - config/idhazh.json (evaluation.publish_gate: 28, 0.7, 30, 0.25 and true)
  - backend/idhazh/stages/work.py (stamps withheld under a live line, and seals the item-health row as failed under the new code, its detail naming the line and its score)
  - backend/idhazh/contracts/item_health.py (the new FailureCode member, withheld_by_publish_gate; version and changelog)
  - backend/idhazh/contracts/knobs/collect.py and config/idhazh.json (collect.settled_failure_codes gains withheld_by_publish_gate, O3.12)
  - backend/idhazh/telemetry/census.py (the rebuild for an item no shard sealed reads the stamp, so it never files a withheld item as ok; re-derive at dispatch)
  - backend/idhazh/stages/assemble.py (a withheld summary never enters the run's items, so collapse_same_story never sees it; the stories whose every summary was withheld are counted by grouping those summaries with the day's items at the same merge line)
  - The plan, work-stage, assemble, census and contract tests and the canary day (re-derive at dispatch: git grep -l -e stage_plan -e census_row -e canary backend/tests)
  - docs/architecture/publishing/autotune-summary-quality.md (the guards, the switch and the withhold; its "target design (in flight)" framing removed, plan 36 section 3)
  - docs/architecture/sources/item-health.md (the new code)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over the tests named above; CI - full suite. The canary day is built once with every line record-only and once with unsupported_number live, and a browser smoke shows the day rendering with an item withheld (CLAUDE.md section 12).
- **Oracle:** over built records, agreement 0.75 with every night under 0.25 for gate_trial_days makes a line live; agreement 0.65, agreement 1.0 on fewer than gate_min_checks checks, a checker that has not passed its planted-fault test, fewer stamped dates than gate_trial_days, one night at 0.26, or withhold_failing_summaries false each keep it record-only, and the switch record names which; on the canary day with the line live, the withheld summary is absent, its duplicate is the story's kept item, its item-health row is failed under the new code with the line and score in its detail, published plus failed stays at most planned, and the record step's and assemble's rows carry the same stamp. Cannot settle: the editorial cost of a thinner day; a blind spot the line and the checker share; a broken scorer on the day it breaks, because the guards read completed nights.

Table O3 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| O3.1 | The gate goes live by itself, line by line, while both guards hold, and returns to record-only when one fails; no person flips it and no corpus turn is read | Owner, 2026-10-11 (QQ12 A1); Table A, A7 |
| O3.2 | Each line earns its own trial: the agreement guard reads only that line's marked summaries, so the lowest-sentence line that row #39 switches on starts record-only and never withholds on the unsupported-number line's record | Owner, 2026-10-11 (QQ15: its own guards decide whether it acts; QQ12 A1) |
| O3.3 | The independent check is summary-grounding-judge, which supersedes gate_checks_per_day; a verdict counts only from a checker that has caught planted unfaithful summaries, and only from the checker series that passed that test | Owner, 2026-10-11 (QQ12 A1, QQ16 A1 and C1, P47); RC26; RC30 |
| O3.4 | A night whose would-be withheld share is over withhold_share_ceiling returns every line to record-only from the next run, because a broken scorer is the likelier cause; the switch record names the night and its share for the quality-alarm issue | Owner, 2026-10-11 (QQ12 A1) |
| O3.5 | withhold_failing_summaries has no default and lands true: the owner's sign-off in QQ12 is the permission and the guards decide when a line acts; false stops withholding from the next run while the stamps continue | Owner, 2026-10-11 (QQ12 A1); RC28 |
| O3.6 | The plan stage decides each line's state once a run, over completed dates, and the run plan carries it, so every shard of a run stamps under one state | backend/idhazh/stages/record.py and backend/idhazh/ledger/keys.py (the stamp is fixed where the eval row is composed, O2.5) |
| O3.7 | A withheld summary is absent from the day, dropped before collapse_same_story so the story's next-best duplicate takes its place; no link-only card, no reader-facing surface, and digest_day.py untouched because a withheld item counts in failed | Owner, 2026-10-11 (QQ12 C1); owner, 2026-09-19 (plan 36 section 0e H1, H3); Fowler, 2026-09-18 (plan 36 E7) |
| O3.8 | Item-health records the withhold as failed under one new FailureCode, its detail naming the line and its score and never fetched text; the work step seals the row, so the record step's and assemble's rows agree and the item-health preference has nothing to decide | Owner, 2026-09-19 (plan 36 section 0e H2); backend/idhazh/ledger/keys.py (ITEM_HEALTH_RULE); CLAUDE.md Guardrail #11 |
| O3.9 | No stub pre-filter: the 60-word extraction floor (extract.min_source_words) stays | Owner, 2026-10-11 (QQ12 D1) |
| O3.10 | The gate's settings live in config/idhazh.json under evaluation.publish_gate, read by the digest: the off switch must act at the next run, and a judge's file is read only by that judge | RC24, RC25, RC27, RC28 (home: rows #22 and #23); owner, 2026-10-11 (P6) |
| O3.11 | The gate acts on one summary's own scores and its own two guards, never on a drift-evals crossing or the combined score | Table B, B2; RE11 |
| O3.12 | The new code joins collect.settled_failure_codes, so a later run of the day does not plan the address again: a same-day retry would be the re-summarize option the owner declined, and keeping whichever retry passes favours copied text | Owner, 2026-10-11 (QQ12 C1 over C2); research record section 4 (faithfulness scores reward copying, Ladhak 2022); backend/idhazh/contracts/knobs/collect.py (settled_failure_codes) |
| O3.13 | The agreement guard counts only once at least gate_min_checks of the line's marked summaries were checked in the window, so a handful of checks cannot switch a line on; at 8 checks a night, 2 of them planted and the would-be withholds next, the unsupported-number line's would-be withholds - 1.7% of about 327 scored summaries, about 5.6 a day - reach it in about 5 to 6 days, well inside two weeks | Proposed 2026-10-12 for the owner's single approval (QQ26), completing QQ12 A1's guard; RC34 |

Table O7 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O7.1 | A person flips the flag after reading one corpus turn of would-be withholds (plan 36 row #8) | A regular human step, and a flag nothing re-checks once it is flipped | A person's review before every switch, and no automatic return to record-only | Owner, 2026-10-11 (QQ12 A1); Table A, A7 |
| O7.2 | A link-only card saying the summary could not be verified (plan 36 E4) | The owner ruled the item absent; the signal lives on the operator surface | A published contract field and a card component (Level 5) | Owner, 2026-09-19 (plan 36 section 0e H1) |
| O7.3 | Drop the withheld item after collapse_same_story | It deletes every duplicate folded behind the withheld representative and breaks the day's count invariants | None | Fowler, 2026-09-18 (plan 36 E7) |
| O7.4 | A stub pre-filter that never summarises an article under 200 words (plan 36 E5) | The owner kept the 60-word extraction floor | Fewer short articles summarised, and a second length floor to keep in step | Owner, 2026-10-11 (QQ12 D1) |
| O7.5 | Withhold on the whole-summary 0.50 line (plan 36 D3) | The whole-summary score marks long, multi-window articles down, so it would withhold faithful summaries of them | About 5.6 percent of scored summaries withheld (2026-09-24 to 2026-10-10) on a score with a known length confound | Owner, 2026-10-11 (QQ12 B2); P31 and P43 evidence |
| O7.6 | One state for the whole gate | A line switched on later (row #39) would withhold from its first day on another line's record | A line with no record of its own acting at once | Owner, 2026-10-11 (QQ15) |
| O7.7 | A same-run ceiling check in assemble that overrides the stamp | The work job files the eval and item-health rows before assemble runs, so an override leaves two disagreeing rows for one summary | A preference rule on two ledgers' keys, and a stamp that changes after it is filed | backend/idhazh/stages/record.py; backend/idhazh/ledger/keys.py |

### Row #24 - Plan 36 row #9, as QQ14 ruled: the publish gate's panel on the Summaries page beside the drift judge's crossings

- **Scope:** One panel on the Summaries page (/console/model/), beside the drift judge's crossings once row #12 lands, shows the publish gate's state per line - record-only or live, since when and why - its two guards against their lines (the independent check's agreement against gate_min_agreement, each night's would-be withheld share against withhold_share_ceiling), the daily share withheld or that would have been, by reason, and the stories lost entirely or that would be. It has no alarm of its own and never shows a withheld summary's text, headline or address. It lands after row #22 and draws what exists: a part whose record has not landed (row #23's switch record, row #35's verdicts) prints an unavailable sentence, never zeros.
- **Level:** 3 (an operator panel; no persisted shape).
- **Files touched:**
  - frontend/src/routes/console/model/+page.server.ts and frontend/src/routes/console/model/+page.svelte (the panel, beside the drift judge's crossings)
  - The panel's component under frontend/src/lib/console/ (re-derive at dispatch)
  - frontend/src/lib/server/ledger-rows.ts (evalRows reads publish_decision and withheld_reason; build-time readers of the switch record and of the run record's story counts, bounded by the console window)
  - config/console/model.json (the panel's group and its judged id)
  - frontend/tests/console-model.spec.ts and frontend/tests/support/panel-drivers/model.ts (populated, record-only with no switch record yet, and empty)
  - The route's expectations under frontend/tests/support/console-expect/ (re-derive at dispatch)
  - backend/tests/contracts/test_frontend_vocabularies.py and backend/tests/contracts/test_frontend_field_set.py (the hand copies of PublishDecision, WithheldReason, the new FailureCode member and the fields the panel reads)
  - docs/architecture/publishing/console.md (the Summaries route's panel)
  - docs/concepts/console-design/what-the-quality-and-source-panels-draw.md (re-derive at dispatch)
- **Acceptance gates:** local - the frontend checks and the contract tests through the shared selector; CI - full suite. Browser smoke per CLAUDE.md section 12, including the data-absent states.
- **Oracle:** a fixture of stamped eval rows over two dates draws each day's withheld and would-be withheld shares by reason, re-derived from the rows; a fixture with no switch record draws the shares and prints the state and guards as unavailable; a fixture with a live line draws its since-date and reason from the record; a night above withhold_share_ceiling is drawn above the line; the panel's readers select no title, summary or address column. Cannot settle: whether the panel is read.

Table O4 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| O4.1 | The panel sits on the Summaries page beside the drift judge's crossings; the Judgement page stays the same-story judge's | Owner, 2026-10-11 (QQ14 A1, P45, P5) |
| O4.2 | It shows each line's state, since when and why; the two guards against their lines; the daily share withheld or that would have been, by reason; and the stories lost entirely | Owner, 2026-10-11 (QQ14 B1); research record section 7.4 (chart each daily gate rate) and section 7.5 (chart the disagreement between independent instruments) |
| O4.3 | No alarm of its own: the drift judge's withheld-share member and the quality-alarm issue carry alarms | Owner, 2026-10-11 (QQ14 B1) |
| O4.4 | Never a withheld summary's text, headline or address: counts and shares only | Owner, 2026-10-11 (QQ14 B1); owner, 2026-09-19 (plan 36 section 0e J5) |
| O4.5 | Plan 36's band charts and fitted floors are not drawn, and neither is its 11 percent baseline: each night's share is drawn against withhold_share_ceiling | Owner, 2026-10-11 (QQ3 A1, QQ14 A1, P39); P43 evidence (5.6 percent under 0.50 and 1.7 percent with an unsupported number, re-measured) |
| O4.6 | It depends on row #22 alone and draws each part once its record exists; a missing record prints an unavailable sentence, never a measured zero | Table D (row #24 reads rows #23 and #35 as they land); docs/architecture/publishing/console.md (a missing record is not a zero) |

### Row #27 - Plan 36 row #12, as QQ13 ruled: every withheld summary kept in key-fact-articles beside the sampled articles, and the corpus harvest skipping the summaries the gate marks on a line that may withhold

- **Scope:** Every summary the gate withholds is kept in key-fact-articles beside the sampled articles (row #29), under the same sampled_article_keep_days window (31) and the same history purge by the gardener's history job, in an entry that says it was kept because it was withheld and carries the summary, the article text the model read, the failed line and its scores, the model and prompt identity and the item's identity, never the rendered prompt. The training-corpus harvest (corpus.harvest_rows) skips every summary the gate marks on a line that may withhold - publish_decision would_be_withheld or withheld - whether or not the gate is live, before keeps_its_counterweights, which stays faithfulness-free; a whole-summary mark never fences.
- **Level:** 5 (committed article text of withheld summaries, held under the key-fact-articles exception of CLAUDE.md section 0a, and a change to what the training corpus takes; QQ13, signed off with the owner's one approval of plan 65, QQ26).
- **Files touched:**
  - The key-fact-articles writer row #29 adds (re-derive at dispatch: the module row #29 names), which writes the withheld entry where it writes the sampled ones
  - The entry contract row #29 declares (re-derive at dispatch): the reason withheld beside sampled and checked for the gate, and the failed line and its scores where the shape lacks them; one entry per summary, naming every reason it was kept
  - backend/idhazh/corpus.py (harvest_rows skips a summary marked on a line that may withhold, before keeps_its_counterweights, which is unchanged)
  - The corpus and writer tests (re-derive at dispatch: git grep -l -e harvest_rows -e keeps_its_counterweights backend/tests)
  - CLAUDE.md section 0a (the key-fact-articles exception also holds withheld summaries, under the same window and purge)
  - docs/how-to/fine-tune-a-model.md (What never selects a row: the fence reads the gate's stamp, never a score; from row #39 the stamp selects on faithfulness, which the drift judge's copying members watch)
  - docs/architecture/publishing/autotune-summary-quality.md (where withheld evidence lives; plan 36's note on an offline reader of the withheld tail points to key-fact-articles)
  - The key-fact-articles page row #29 writes (re-derive at dispatch)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over the tests named above; CI - full suite. No test walks committed article text or the corpus (CLAUDE.md section 13, Guardrail #12).
- **Oracle:** for a built withheld summary one key-fact-articles entry lands, naming withheld as its reason, with the summary, the text the model read, the failed line and its scores, the model and prompt identity and the item's identity, and no rendered prompt; a summary both sampled and withheld lands once, naming both reasons; harvest_rows skips a built row stamped would_be_withheld on lowest_sentence_faithfulness whose counterweights all pass, keeps a row whose only mark is its low display band, and keeps_its_counterweights still reads no faithfulness column. Cannot settle: whether the lines withhold real failures rather than good summaries, which row #23's guard measures; what training on the fenced corpus teaches, which the drift judge's copying members watch.

Table O5 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| O5.1 | Withheld summaries are kept in key-fact-articles beside the sampled articles, under its window and purge: no rejects ledger, no prune verb, no history rewrite outside the gardener's history job, and plan 36's state/rejects/ exception is not used | Owner, 2026-10-11 (QQ13 A1, P44); CLAUDE.md section 8 |
| O5.2 | Kept: every summary the gate withholds; a would-be withhold is kept only when it is checked for the gate (row #29) | Owner, 2026-10-11 (QQ13 A1, QQ16 A1) |
| O5.3 | An entry carries the summary, the article text the model read, the failed line and its scores, the model and prompt identity and the item's identity; no rendered prompt, which the harvest's reconstruction rebuilds from the article text and that day's prompt code | Owner, 2026-10-11 (QQ13 C1) |
| O5.4 | Never served: no payload, projection, index or panel reads an entry; the panel shows counts only | Owner, 2026-10-11 (QQ30 A1, QQ14 B1); owner, 2026-09-19 (plan 36 section 0e J5) |
| O5.5 | The fence skips every summary marked on a line that may withhold, live or not, reading the stamp and never a raw score; it sits before keeps_its_counterweights, which stays faithfulness-free, and the whole-summary mark never fences | Owner, 2026-10-11 (QQ13 B1); owner, 2026-09-19 (plan 36 section 0e J6) |
| O5.6 | The fence holds on the re-fetch path too: corpus.rescored rebuilds a row from the recorded one and carries its stamp across | backend/idhazh/corpus.py (rescored) |
| O5.7 | Until row #39 the fence drops nothing the counterweights do not already drop, because unsupported_numbers is one of them; from row #39 it selects the corpus on faithfulness through the stamp, and since faithfulness scores reward copying, the drift judge's copying members show the effect | Owner, 2026-10-11 (P44); research record section 7.6 (Goodhart effects move copying and length first) |
| O5.8 | The corpus stays fenced whichever of rows #23 and #27 merges first: before row #39 only unsupported_number can withhold, which the counterweights already drop, and row #39 depends on this row | Table D (rows #23, #27 and #39); backend/idhazh/corpus.py (keeps_its_counterweights) |

Table O8 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O8.1 | A rejects ledger of its own: state/rejects/ with a RejectRow per withheld item, a 30-day prune verb and prune.yml's force-push (plan 36 row #12) | A folder the gardener's sweep would empty unless registered, a history rewrite outside the gardener's history job, and a third article-text exception | A ledger, a contract, a retention verb and a third exception in CLAUDE.md section 0a | Owner, 2026-10-11 (QQ13 A1, P44); review record section 3, Table I, I12 |
| O8.2 | The rendered prompt in each entry (plan 36 J2) | The harvest's reconstruction rebuilds it from the article text and that day's prompt code | The system and user turns committed beside the article text | Owner, 2026-10-11 (QQ13 C1) |
| O8.3 | Fence on the faithfulness score itself | A corpus filtered on its monitor trains a model against that monitor, and the whole-summary score marks long articles down | A model taught to score well on the instrument that judges it | Owner, 2026-10-11 (QQ13 B1); Andre and the owner, 2026-09-19 (plan 36 section 0e J6); docs/how-to/fine-tune-a-model.md |
| O8.4 | Fence real withholds only | Record-only would-be withholds would train the model while the gate is off | None | Owner, 2026-10-11 (QQ13 B1) |

### Row #28 - Plan 36 row #13, as QQ25 ruled: one shared set of guards for every model judge

- **Scope:** One shared set of guards, in one module, for the content-similarity judge, summary-completeness-judge and summary-grounding-judge. Where a judge reads a one-token answer - the grounding judge's yes or no and the content-similarity judge's verdict - a rendered prompt that ends in a space is refused before the call, the answer's token ids are built by encoding each legal answer in position after the prompt, and every first-token alternative is recorded with its log probability. Every judge call goes out with thinking off, and a canary rejects a recorded thinking-on completion rather than scoring it. For the two judges that read article text, a planted-instruction canary runs on recorded completions. A live red-team stays out of scope.
- **Level:** 3 (guards and canaries over recorded completions; no persisted shape: row #35's verdict rows already carry the answer's first-token probability, X9.27).
- **Files touched:**
  - backend/idhazh/llm/judge_guards.py (new: the prompt-end check, the in-position answer tokens and the thinking-on refusal every model judge calls)
  - backend/idhazh/llm/server.py (every judge request body carries the entry's thinking keyword off; re-derive at dispatch: git grep -n "def grammar_completion_payload" backend)
  - backend/idhazh/similarity/judge.py (read_once calls the guards; its two-span reasoning path is closed to judge calls)
  - backend/idhazh/similarity/prompt.py (first_token_openings asks the vocabulary for each legal reply in position after the rendered prompt)
  - summary-grounding-judge's package (row #35; re-derive at dispatch): the guards on its yes-or-no call, its first-token alternatives recorded where its verdict rows hold them
  - summary-completeness-judge's package (row #30; re-derive at dispatch): thinking off and the planted-instruction canary
  - The three judges' tests, with recorded fixtures: one thinking-on completion per judge, and a kept article carrying a planted instruction for the two article readers (re-derive at dispatch)
  - docs/architecture/publishing/llm-council.md (the guards every model judge passes)
  - docs/architecture/summarize/model-boundary.md (a judge call never opens a reasoning span)
  - docs/architecture/sources/trust-boundary.md (the planted-instruction canary holds on recorded completions only; a live red-team is out of scope)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over the three judges' tests and the llm tests; CI - full suite. No network and no live server (Guardrail #7).
- **Oracle:** for each judge that reads a one-token answer, a rendered prompt ending in a space is refused before any call; the answer token ids built in position from a recorded tokenizer reply equal the first tokens of each legal answer after the prompt; every alternative of a recorded first-token window is recorded; every judge's request body carries thinking off, and a recorded completion carrying a reasoning span is rejected and recorded as not a verdict; for the two article readers, an article with a planted instruction renders it only inside the article's block, with the judge's own ask after it, and a recorded completion that obeys it outside the answer's grammar is refused while a legal one reads as it does on the clean article. Cannot settle: a live model's resistance to a planted instruction, accepted by contract (Guardrail #7); a tokenizer or template the fixtures do not hold.

Table O6 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| O6.1 | One shared set of guards for the three model judges, not folded into each judge's row and not dropped with the fluency judge it was written for | Owner, 2026-10-12 (QQ25 A1) |
| O6.2 | The space guard and the in-position answer tokens apply where a judge reads a one-token answer: the grounding judge's yes or no and the content-similarity judge's verdict; summary-completeness-judge writes lists, not a first-token answer | Owner, 2026-10-12 (QQ25 A1); Table D, row #28 |
| O6.3 | The content-similarity judge keeps its optional leading space, its prefix bucketing and its recorded first-token window; what changes is that its openings are asked of the vocabulary in position after the rendered prompt, where today they are asked one legal reply at a time | backend/idhazh/similarity/prompt.py (first_token_openings, verdicts_opened_by); owner, 2026-10-12 (QQ25 A1) |
| O6.4 | Thinking is off for every judge call, whatever the model entry declares: the content-similarity judge's two-span reasoning path is closed to judge calls, and a later judge model that declares thinking_close (Gemma 4 E4B among RC30's choices) is decoded with its template keyword off | Owner, 2026-10-12 (QQ25 A1); owner, 2026-10-11 (QQ16 B1: no-think mode); backend/idhazh/similarity/judge.py (read_once) |
| O6.5 | A recorded thinking-on completion is rejected and recorded as not a verdict, never scored, so the canary fails loudly if a template or a server turns reasoning back on | Owner, 2026-10-12 (QQ25 A1); Andre, 2026-09-18 (plan 36 E10) |
| O6.6 | The planted-instruction canary runs on recorded completions for summary-completeness-judge and summary-grounding-judge, the two judges that read article text; it proves the prompt keeps the article as data and the reader refuses a reply outside its answers, not that a live model resists | Owner, 2026-10-12 (QQ25 A1); CLAUDE.md Guardrails #7 and #11; Andre (plan 36 row #13 decision 2) |
| O6.7 | A live red-team stays out of scope | Owner, 2026-10-12 (QQ25 A1); CLAUDE.md Guardrail #7 |

### Row #29 - The digest run samples 30 scored summaries a day across its runs and keeps their article text in key-fact-articles

- **Scope:** The digest run keeps, in key-fact-articles, the article text of keyfact_sample_per_day (30) scored summaries a date, drawn across the date's runs blind to every score, and of up to faithfulness_checks_per_night (8) of the gate's would-be withholds: one JSON file per kept summary, one folder a date, outside the ledger door's packing, in the family summary-completeness-judge. An entry holds the summary, the article text the model read, the model and prompt identity, the item's identity and every reason it was kept (Table X9). A gardener retention task removes a file after sampled_article_keep_days (31), and the history job carries its bytes out of git history. CLAUDE.md section 0a lists the record as the second article-text exception; it is never published.
- **Level:** 5 (committed article text, the CLAUDE.md section 0a exception the owner approved in QQ4, and a persisted record later runs read; its shape, Table X9, is named here for the owner's single approval of the plan, QQ26).
- **Files touched:**
  - CLAUDE.md (section 0a: key-fact-articles is the second committed article-text exception after corpus/, with its window, its removal and its history purge)
  - backend/idhazh/contracts/key_fact_article.py (new: KeyFactArticle, Table X9, with version and changelog), backend/idhazh/contracts/__init__.py (CONTRACTS) and one fixture through backend/tests/contracts/_fixtures.py
  - backend/idhazh/contracts/ledger_name.py (SUMMARY_COMPLETENESS_JUDGE_KEY_FACT_ARTICLES = "key-fact-articles"), config/ledgers.json (new family summary-completeness-judge: status active, a one-line description, its onboarded day; the entry at grain tree, prefix ["summary-completeness-judge", "key-fact-articles"]) and frontend/src/lib/data/slice-shapes.ts (LEDGER_NAMES; LEDGER_FOLDERS only if a nested tree ledger needs it - re-derive at dispatch)
  - backend/idhazh/ledger/staging.py (REGISTRY: the keep stage in the assemble job, label assemble) and backend/idhazh/ledger/filenames.py (an entry's file name built from its url_key; re-derive at dispatch: git grep -n segment_name backend/idhazh/ledger)
  - backend/idhazh/key_fact_articles.py (new: writes and reads one entry through the ledger package's path builders, asking ledger.accepts_new_rows before a write)
  - backend/idhazh/stages/keep_sampled_articles.py (new stage: the date's two draws from the run's items directory and eval rows), backend/utilities/digest_publish.py (its verb) and .github/workflows/digest.yml (a step in the assemble job after the corpus harvest that blocks no publication; the day's commit stages the record - re-derive at dispatch: git grep -n COMMIT_STAGED_PATHS)
  - backend/idhazh/contracts/knobs/evaluation.py, backend/idhazh/contracts/app_config.py (one changelog entry) and config/idhazh.json (keyfact_sample_per_day 30, 2 to 100, and faithfulness_checks_per_night 8, 1 to 50: RC23 and RC26)
  - config/gardener/key-fact-articles.json (new: kind retention, window 31 days - sampled_article_keep_days, RC22 - live, owning state/summary-completeness-judge/key-fact-articles; re-derive the declaration's name rule at dispatch), backend/idhazh/gardener/tasks/key_fact_articles.py (new, on the traces task's pattern) and config/idhazh_gardener.json (task_names)
  - backend/tests/contracts/test_gardener_config.py (the declaration's window held to 7 to 60 days), backend/tests/contracts/test_no_csv_ledger_is_left.py (a fourth JSON ledger outside the door) and backend/tests/workflows/test_ledger_staging.py
  - New tests for the stage, the writer and the gardener task (re-derive their folders at dispatch: git grep -n -l stage_harvest backend/tests)
  - docs/architecture/contracts/ledger-registry.md (a dated line: key-fact-articles files outside the door by the owner's ruling QQ30), docs/architecture/contracts/state-ledgers.md (one row), docs/concepts/config/retention-ages.md and docs/architecture/publishing/retention.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/contracts/, backend/tests/workflows/ and the new stage, writer and gardener-task tests; CI - full suite. Observation, not a gate: the first live date's folder, read for the entries each run kept and the bytes committed.
- **Oracle:** a fixture of five runs' items directories keeps at most keyfact_sample_per_day sampled entries for the date, spread over the runs, and keeps the same entries when every score in the fixture is reversed; an entry round-trips through its contract with the article text, the summary and its reasons, in the date's folder under a name built from its url_key; a summary whose eval row carries the gate's would-be withhold stamp is kept as checked_for_gate, at most faithfulness_checks_per_night a date; a paused family writes nothing and logs one warning; the gardener task takes a fixture file older than its window and keeps the newest. Cannot settle: whether 30 a day gives the key-fact members any power, which rows #31 and #33 measure; a removed file's bytes stay in git history until the history job's next squash past them.

Table X1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| X1.1 | key-fact-articles is a record of its own outside the ledger door's packing: one JSON file per kept summary, one folder a digest date, in the family summary-completeness-judge, at the registry's tree grain; ledger-registry.md records it as kept outside the door on purpose, because the door's packing would keep article text for up to 36 months | Owner, 2026-10-11 (QQ30 A1, QQ11 B1 and C1; P41, P42) |
| X1.2 | CLAUDE.md section 0a lists key-fact-articles as the second committed article-text exception, after corpus/, with its window and its history purge; plan 36's state/rejects/ carve-out is not used | Owner, 2026-10-11 (QQ4, QQ13 A1, QQ30 A1; P32, P44) |
| X1.3 | The sample is keyfact_sample_per_day (RC23) scored summaries a digest date, drawn in each run's assemble job from that run's scored summaries by a digest of the date and the url_key - the blind selector backend/idhazh/evals/sampling.py uses for runs - in proportion to the run's share of the date's scored summaries; the date stops at its quota, counted from what earlier runs kept, and no kept entry is deleted, so no article text is committed that no judge reads | Owner, 2026-10-11 (QQ4: 30 a day, a config number); Table D (across its runs); backend/idhazh/evals/sampling.py (a selector that could see an outcome would bias what it thins) |
| X1.4 | Up to faithfulness_checks_per_night (RC26) of the date's would-be withholds are kept the same way, read from the gate's stamp on the eval row (publish_decision would_be_withheld, row #18) and never re-derived from scores; if this row merges before rows #18 and #22, that selection lands with row #35, which comes after both | Owner, 2026-10-11 (QQ12, QQ16); Table D |
| X1.5 | An entry names every reason it was kept - sampled, checked_for_gate, withheld (row #27 writes the third) - so a summary is kept once and neither draw thins the other | Owner, 2026-10-11 (QQ13 A1) |
| X1.6 | An entry carries what QQ13 names and nothing more (Table X9): no rendered prompt, and no element labels from the work shard's first call, so no judge can take the digest's claims or lede sentences as key facts | Owner, 2026-10-11 (QQ13 C1; B12, Q49) |
| X1.7 | keyfact_sample_per_day and faithfulness_checks_per_night live in the evaluation block of config/idhazh.json, because the digest run draws both samples and a judge's settings file is read only by that judge; the two judges read the same fields from the app config, as the content-similarity judge reads its block there | Table RC (RC23 and RC26: homes decided with rows #29, #30 and #35); owner, 2026-10-11 (P6) |
| X1.8 | sampled_article_keep_days (RC22) is the window of a gardener retention task that owns the record's folder, on the traces task's pattern: retention stays with the pass that deletes, so a paused or retired judge cannot keep article text past its window; the task lands live, its commit naming QQ30 as the owner's decision, and a test holds its window to RC22's 7 to 60 days | Owner, 2026-10-11 (QQ30 A1); Table RC (RC22: home decided here); ledger-registry.md (retention stays with the pass that deletes) |
| X1.9 | A removed file's bytes leave git history through the gardener's existing history job, which squashes all of main older than its window, so this row adds no history code; they are gone within about 60 to 90 days of removal | Owner, 2026-10-11 (QQ30 A1); .github/workflows/idhazh-gardener.yml (the history job collapses what is older than its window into one root) |
| X1.10 | Never published: the record has no compact files and stays out of ledger.published and every payload, projection and index | Owner, 2026-10-11 (QQ30 A1); plan 36 J5 |
| X1.11 | Article text is untrusted data: an entry's name is built by the ledger package from the item's url_key, a sha256, and the commit message stays fixed, so no article text reaches a path, a commit message or a shell argument | CLAUDE.md Guardrail #11; Table C, C7 |
| X1.12 | The writer asks whether the family takes new rows before it writes, as the trace sink does; a failed keep step leaves the date short and blocks no publication, as the corpus harvest does | ledger-registry.md (the write path reads the status on every write); .github/workflows/digest.yml (the harvest step) |

Table X9 - the fields of the records rows #29, #30, #32 and #35 declare (named once here; rows #30 to #35 point here)

| # | Record | Fields | Meaning | Authority |
| --- | --- | --- | --- | --- |
| X9.1 | key-fact-articles (KeyFactArticle, JSON, row #29) | version | The schema stamp a later reader reads the entry by | CLAUDE.md section 11 |
| X9.2 | key-fact-articles | kept_because: one or more of sampled, checked_for_gate, withheld | Why the entry was kept | Owner, 2026-10-11 (QQ13 A1) |
| X9.3 | key-fact-articles | date, run_id, item_id, url_key, source_id, vertical | The item's identity: the digest date and run, the address key and the feed that carried it | Owner, 2026-10-11 (QQ13 C1) |
| X9.4 | key-fact-articles | model_id, prompt_digest | The summarizer and its prompt identity, the digest the corpus harvest records | Owner, 2026-10-11 (QQ13 C1) |
| X9.5 | key-fact-articles | title, summary | The summary as written, published or withheld | Owner, 2026-10-11 (QQ13 C1) |
| X9.6 | key-fact-articles | article_text | The sanitised text the model read, held as untrusted data | Owner, 2026-10-11 (QQ4, QQ13 C1); CLAUDE.md Guardrail #11 |
| X9.7 | key-fact-articles | failed_line and the scores it read, or null | Set on checked_for_gate and withheld entries from the gate's stamp | Owner, 2026-10-11 (QQ13 C1) |
| X9.8 | key-fact-articles | key_facts, key_fact_model_id, key_fact_prompt_version, key_facts_parsed, or null | Written at night by summary-completeness-judge (row #30); null until judged; removed with the entry | Owner, 2026-10-11 (QQ11 B1, QQ30 B1) |
| X9.9 | key-fact-scores (KeyFactScore, parquet through the door, row #30) | run_id, date, judge_id, url_key | The council run, the judged digest date, the judge and the entry scored | ledger-registry.md (the rule a judge ledger follows) |
| X9.10 | key-fact-scores | model_id | The production model series of the judged summary | Owner, 2026-10-11 (QQ1; P14) |
| X9.11 | key-fact-scores | judge_model_id, judge_prompt_version | The instrument: the model that judged and its prompt version | Owner, 2026-10-11 (QQ30 B1); owner, 2026-10-12 (QQ22) |
| X9.12 | key-fact-scores | completeness, conciseness, key_fact_count | The share of listed key facts the summary holds, the share of its sentences that carry one, and how many facts were listed; the two shares null when an answer did not parse | Owner, 2026-10-11 (QQ4, QQ30 B1) |
| X9.13 | key-fact-scores | parsed | Whether both answers came out of the grammar | Owner, 2026-10-11 (QQ30 B1) |
| X9.14 | key-fact-scores | sample_group: sampled or planted | The date's uniform sample, the alarm's larger sample included, or row #31's planted variant; the drift judge reads sampled rows only | Owner, 2026-10-11 (QQ30 B1) |
| X9.15 | key-fact-scores | key: run_id, date, url_key, sample_group; no preference | Two council runs of one date never settle into one record | ledger-registry.md (the rule a judge ledger follows) |
| X9.16 | drift-evals-tuning (DriftEvalsTuning, parquet through the door, rows #32 and #33) | run_id, date, row_kind: tuning_run or metric_move | One ledger, a row per tuning run and a row per metric move | Owner, 2026-10-11 (QQ30 C1) |
| X9.17 | drift-evals-tuning, tuning_run | tuning_version | The id the night's combined-score rows reference | Owner, 2026-10-11 (QQ10, QQ30 C1) |
| X9.18 | drift-evals-tuning, tuning_run | members, a list of structs: each member's slug and status, its weight and rho in force, proposed and applied, and for a paused member its promotion test values | What the replay proposed, what was applied, and why a paused member stayed | Owner, 2026-10-11 (QQ27, QQ28, QQ30 C1) |
| X9.19 | drift-evals-tuning, tuning_run | each guard's result (in range, within step, false-alarm rate against its target, worst-case detection in force and proposed), applied, held_reason | Why the values moved or were held | Owner, 2026-10-11 (QQ27, QQ30 C1) |
| X9.20 | drift-evals-tuning, tuning_run | auto_apply_tuning, tuning_every_days, max_weight_step, max_rho_step in force | The settings in force, so a reader needs no git history | Owner, 2026-10-11 (QQ10, QQ27) |
| X9.21 | drift-evals-tuning, metric_move | check_name, from and to status, the check_name it replaced and the starting weight taken over, or null | Which member moved, and the predecessor a replacement retired | Owner, 2026-10-11 (QQ28, QQ31) |
| X9.22 | drift-evals-tuning, metric_move | usable days, false-alarm rate, detection share within a week, typical night's new stretches, reason | The test values and the reason for the move | Owner, 2026-10-11 (QQ28, QQ30 C1) |
| X9.23 | drift-evals-tuning, metric_move | auto_promote_metrics, promotion_min_days, promotion_min_detection in force | The settings in force | Owner, 2026-10-11 (QQ10, QQ28) |
| X9.24 | drift-evals-tuning | key: run_id, date, row_kind, check_name (none on a tuning_run row); no preference | Every council run's tuning night kept | ledger-registry.md (the rule a judge ledger follows) |
| X9.25 | grounding-verdicts (GroundingVerdict, parquet through the door, row #35) | run_id, date, judge_id, url_key, source_id, model_id | The council run, the judged digest date, the summary checked, its source and its production series | Owner, 2026-10-11 (QQ16 C1); owner, 2026-10-12 (QQ32: it names the source) |
| X9.26 | grounding-verdicts | checked_because: gate, sampled or planted | The order the night took it in - the gate's would-be withholds and withheld summaries, then sampled ones - and planted variants for its own test | Owner, 2026-10-11 (QQ12, QQ16 A1) |
| X9.27 | grounding-verdicts | sentence_index; verdict: supported, unsupported or null; parsed; answer_probability | One summary sentence's answer, read as the criterion defines it, with its first-token probability | Owner, 2026-10-11 (QQ16 A1); owner, 2026-10-12 (QQ25) |
| X9.28 | grounding-verdicts | checker_model, checker_sha256, prompt_template_version | The instrument | Owner, 2026-10-11 (QQ16 B1); owner, 2026-10-12 (QQ22) |
| X9.29 | grounding-verdicts | main_score, main_line | The main scorer's score and line for the summary, so disagreement is read from this ledger alone | Owner, 2026-10-11 (QQ16 A1) |
| X9.30 | grounding-verdicts | skipped: one row, with no sentence, for a summary the budget did not reach | What the night skipped | Owner, 2026-10-11 (QQ16 A1; Table RC, RC29) |
| X9.31 | grounding-verdicts | key: run_id, date, url_key, checked_because, sentence_index; no preference | One answer per sentence per council run | ledger-registry.md (the rule a judge ledger follows) |

### Row #30 - summary-completeness-judge: completeness and conciseness from key facts, with the summarizer's own model

- **Scope:** summary-completeness-judge joins the council as a judge of its own that runs the summarizer's own model (Qwen 3.5 9B): its settings file, its slug in judge_names, its package and its family. Each night it reads the judged date's entries kept as sampled and, by FineSurE's method, lists each article's key facts from the kept article text before it sees the summary, then aligns the summary's sentences to those facts. Completeness, conciseness and the instrument's identity go to key-fact-scores, numbers only, through the door (Table X9); the key-fact list is written into the article's own entry and leaves with it. It never reads the digest's labelled claims or lede sentences (B12).
- **Level:** 5 (a new ledger, key-fact-scores, and a new judge that runs a model; its shape, Table X9, is named here for the owner's single approval of the plan, QQ26).
- **Files touched:**
  - config/judges/summary-completeness-judge.json (new: lifecycle_status, runs_model true, its decode temperature and the most key facts one list may hold, each bounded) and backend/idhazh/contracts/knobs/summary_completeness_judge.py (new: imported only by the judge's settings module)
  - config/llm_council.json (judge_names gains summary-completeness-judge)
  - backend/idhazh/summary_completeness_judge/__init__.py, settings.py and tenant.py (new: JUDGE_ID; shard_count the council's width; committed_paths the two ledgers; nights_outstanding the dates in the window whose sampled entries carry no list; prepare deals the date's sampled entries; run_shard makes the two calls an entry; settle files the scores and writes each list into its entry; the judged date's folder named as a publication input under the [collection rules](../docs/architecture/publishing/llm-council.md#units-judge-and-only-the-collecting-job-writes) - re-derive at dispatch)
  - backend/idhazh/summary_completeness_judge/key_facts.py (new: the two calls through backend/idhazh/llm/server.py's grammar payload, and the two shares)
  - backend/idhazh/prompts/list_key_facts.txt and backend/idhazh/prompts/align_summary_to_key_facts.txt (new)
  - backend/idhazh/contracts/key_fact_score.py (new: KeyFactScore, Table X9), backend/idhazh/contracts/__init__.py (CONTRACTS) and one fixture through backend/tests/contracts/_fixtures.py
  - The ledger's registration as ledger-registry.md requires: backend/idhazh/contracts/ledger_name.py (SUMMARY_COMPLETENESS_JUDGE_KEY_FACT_SCORES = "key-fact-scores"), config/ledgers.json (raw-and-compact in the family summary-completeness-judge), backend/idhazh/ledger/keys.py (_JUDGE_DOOR_SHAPES), backend/idhazh/ledger/staging.py (REGISTRY, no digest.yml label) and frontend/src/lib/data/slice-shapes.ts (LEDGER_NAMES, LEDGER_FOLDERS)
  - config/gardener/compact-summary-completeness-judge-key-fact-scores.json (new), config/idhazh_gardener.json (task_names) and backend/tests/contracts/test_gardener_config.py (RETENTION_LEDGERS)
  - backend/tests/summary_completeness_judge/ (new: recorded completions) and backend/tests/council/ (re-derive at dispatch: tests that enumerate judge_names)
  - docs/architecture/publishing/summary-completeness-judge.md (new: the judge's own page), docs/architecture/publishing/llm-council.md ("What is heard here"), docs/architecture/contracts/state-ledgers.md and docs/architecture/publishing/autotune-summary-quality.md (the key-fact check in place of the self-graded fluency)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_completeness_judge/, backend/tests/council/, backend/tests/contracts/ and backend/tests/workflows/; CI - full suite. Observation, not a gate: the first live night's minutes a summary and the share of answers that parsed, read against the council's window.
- **Oracle:** recorded completions of the two calls (Guardrail #7) give a completeness and a conciseness the test computes from the recorded alignment, never copies; the first call's rendered prompt holds the article text and no summary text, and neither prompt holds an element label; an answer outside the grammar files a row with parsed false and no shares; the list lands in its entry and no text lands in key-fact-scores; a council night driven end to end in a tmp_path state root files rows that read back through ledger.load_days. Cannot settle: whether a 9B model lists the facts a person would - FineSurE's completeness tracked people at 0.571 Pearson even when GPT-4 listed the facts (research record); the bias of a model judging its own summaries, which every row names.

Table X2 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| X2.1 | summary-completeness-judge is a council judge of its own that runs a model: config/judges/summary-completeness-judge.json with lifecycle_status and runs_model true, its slug in judge_names, its package summary_completeness_judge, and its family folder holding key-fact-articles and key-fact-scores | Owner, 2026-10-11 (QQ4 C3, QQ11 C1; P42); [Judge registration](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs) |
| X2.2 | FineSurE's method, two calls a summary: the first lists the article's key facts from the kept article text alone, before the model sees the summary; the second aligns the summary's sentences to those facts; completeness is the share of facts the summary holds, conciseness the share of its sentences that carry one | Owner, 2026-10-11 (QQ4); research record section 7.2 (J1) |
| X2.3 | Key facts are listed only here, at night, from the kept article text, never from the digest's labelled claims or lede sentences; the summary prompts and the work shard stay free of them | Owner, 2026-10-11 (B12, Q49) |
| X2.4 | The key-fact list is model output drawn from untrusted article text, so it is written into the article's entry as data and leaves with it; key-fact-scores holds numbers only | Owner, 2026-10-11 (QQ30 B1); CLAUDE.md Guardrail #11 |
| X2.5 | key-fact-scores files through the door, raw-and-compact, in the family summary-completeness-judge, under the rule a judge ledger follows | Owner, 2026-10-11 (QQ11 B1 and C1, QQ30 B1; P41, P42); ledger-registry.md |
| X2.6 | The judging model is the one the council serves as the summarizer, so a summarizer swap is also a judge-model change: each row names the judging model and prompt version, the drift judge starts a new series on either, and the judge's page names it as the writer's own model | Owner, 2026-10-11 (QQ4 C3); P14; owner, 2026-10-12 (QQ22) |
| X2.7 | Answers come out of a grammar, as the content-similarity judge's do: a reply the grammar cannot have written is a row with parsed false and no shares, never read back as prose; thinking is off; row #28 then holds this judge to the shared guards | backend/idhazh/similarity/judge.py; owner, 2026-10-12 (QQ25) |
| X2.8 | The night's work is the judged date's entries kept as sampled; entries kept for the gate or withheld are the grounding judge's, so this judge keeps key facts only | Owner, 2026-10-11 (QQ16 A1) |
| X2.9 | A unit stops at its deadline, and an entry it did not reach keeps no list; nights_outstanding names a date in the council's window whose sampled entries carry none, so a missed night is repaired while its article text is kept | backend/idhazh/council/tenancy.py; [Per-judge dates](../docs/architecture/publishing/llm-council-dates.md#scheduled-dates-belong-to-each-judge); owner, 2026-10-11 (QQ30 A1) |
| X2.10 | The judge lands paused and turns active in the row's last commit, the message and the judge's page naming QQ4 as the owner's decision; its numbers reach no alarm until row #31's members are promoted | [Activation rule](../docs/architecture/publishing/llm-council.md#design-rationale-a-new-judge-starts-paused); owner, 2026-10-11 (QQ4, QQ28) |
| X2.11 | Its settings model and row contract stay out of the council's import closure: the settings imported only by the judge's settings module, the row contract in _JUDGE_DOOR_SHAPES | Table C, C9; ledger-registry.md |

### Row #31 - The pilot: summaries with facts removed on purpose

- **Scope:** Each night summary-completeness-judge also aligns a planted variant of some sampled summaries - whole sentences removed on purpose, chosen without reading its own alignment - against the key-fact list it already made for the article, and files it in key-fact-scores as sample_group planted. Completeness and conciseness are declared in the drift judge's settings as two paused quality members reading the sampled rows; a week's planted rows are their planted fault in the replay. They join the alarm only through row #33's automatic promotion once they catch it (QQ28); if they never do, moving the check to Gemma 4 E4B is the owner's decision, because it changes the model the council serves.
- **Level:** 3 (declarations are config and the planted value of sample_group is row #30's shape; the day minimum and the pilot's settings, X3.6 and X3.7, are named here for the owner's single approval of the plan, QQ26).
- **Files touched:**
  - backend/idhazh/summary_completeness_judge/planted.py (new: a planted variant drops whole summary sentences chosen at random, never by the alignment)
  - backend/idhazh/summary_completeness_judge/tenant.py (run_shard aligns each planted variant against its article's list; settle files it with sample_group planted)
  - backend/idhazh/contracts/knobs/summary_completeness_judge.py and config/judges/summary-completeness-judge.json (planted_omissions_per_night and sentences_removed_per_omission, RC35 and RC36, X3.7)
  - config/judges/summary-fidelity-judge.json (two paused quality declarations on key-fact-scores, sample_group sampled: completeness and conciseness at weight 0 and rho 0, each declaring min_day_rows 20, X3.6)
  - The drift judge's planted_faults.py and backend/utilities/summary_fidelity_replay.py (row #8): the key-fact members' planted fault is a week's planted rows in place of their originals
  - backend/tests/summary_completeness_judge/test_planted.py (new) and backend/tests/summary_fidelity_judge/ (the two declarations bind paused; the planted fault - re-derive at dispatch)
  - docs/architecture/publishing/summary-completeness-judge.md (the pilot, what caught means, and the owner's model decision) and docs/architecture/publishing/summary-fidelity-judge.md (the two members)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_completeness_judge/ and backend/tests/summary_fidelity_judge/; CI - full suite. Observation, not a gate: the first four weeks of planted rows, read for the share caught, which the scheduled replay then reads.
- **Oracle:** a recorded alignment of a planted variant that lost the sentence carrying two of five listed facts gives a completeness the test computes as two fifths under its original's; the variant's sentences are its original's less the removed ones, chosen with no input from the alignment; the two declarations bind paused, read only sampled rows and carry weight 0 and rho 0; the replay's planted fault for them puts a week's planted rows in place of their originals. Cannot settle: whether the live model notices removed facts, which the first weeks of planted rows measure; whether a removed sentence stands for the omissions a summarizer makes.

Table X3 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| X3.1 | A planted variant drops whole summary sentences, never the title, chosen at random with no input from the judge's alignment, so the judge cannot choose what it is tested on; it reuses the article's key-fact list, so it costs one alignment call | Owner, 2026-10-11 (QQ4: injected omissions; P32); review record, I4 |
| X3.2 | A planted variant is caught when its completeness is under its original's; the share caught each week is the pilot's evidence, and a week's planted rows in place of their originals are the key-fact members' own planted fault in the replay | Owner, 2026-10-11 (QQ28) |
| X3.3 | Completeness and conciseness are declared as two quality members reading key-fact-scores, sample_group sampled only, grouped by production series and judging instrument, adjusted as Table RA's quality members are through the eval row of the same url_key, harm direction lower, landing paused at weight 0 and rho 0 | Owner, 2026-10-11 (QQ2, QQ9, QQ28; Table RA's note); P14 |
| X3.4 | They join the alarm only through row #33's automatic promotion, at weight 0 until a tuning gives them one; nothing in this row makes them active | Owner, 2026-10-11 (QQ28) |
| X3.5 | A member that is never promoted leaves its test values on every tuning-run row (row #33); moving the check to Gemma 4 E4B, whose model file config/models/gemma-4-e4b-qat.json already holds, is the owner's decision, because it changes the model the council serves; nothing notifies (B3) | Owner, 2026-10-11 (QQ4, QQ28) |
| X3.6 | A member may declare a day minimum of its own, which replaces min_day_rows (RC4, 100) for that member alone; completeness and conciseness declare 20, under keyfact_sample_per_day (RC23, 30), so a night with a few unparsed answers still counts as a usable day; every other member keeps RC4 | Proposed for the owner's single approval of the plan (QQ26); Table RC (RC4, RC23) |
| X3.7 | The pilot's two settings live in the judge's own file: planted_omissions_per_night (RC35, 5), the planted variants aligned each night on top of the sampled summaries, and sentences_removed_per_omission (RC36, 1), the whole sentences each variant drops | Proposed for the owner's single approval of the plan (QQ26); owner, 2026-10-11 (P6); CLAUDE.md Guardrail #6 |

### Row #32 - The scheduled replay tunes weights and rho within guards, records every proposal, and stops at once when auto_apply_tuning is false

- **Scope:** On a judged night when tuning is due - every tuning_every_days (28) - the drift judge's unit runs the replay: it proposes each judged member's weight from the best worst-case detection on the injected faults and its rho from quiet stretches, within one step of the values in force, and applies the proposal only when every guard passes - each value inside its range, each change within max_weight_step (1) or max_rho_step (0.1), false alarms on reshuffled history on target, worst-case detection no worse - and otherwise holds the values in force. Every proposal, applied or held, is one row in drift-evals-tuning, a new door ledger beside drift-evals; the settings file is never written; auto_apply_tuning false stops application at once.
- **Level:** 5 (a new ledger, drift-evals-tuning, declaring both its row kinds; its shape, Table X9, is named here for the owner's single approval of the plan, QQ26).
- **Files touched:**
  - backend/idhazh/contracts/drift_evals_tuning.py (new: DriftEvalsTuning with both row kinds of Table X9, the held reasons and move reasons as closed sets), backend/idhazh/contracts/__init__.py (CONTRACTS) and one fixture through backend/tests/contracts/_fixtures.py
  - The ledger's registration as ledger-registry.md requires: backend/idhazh/contracts/ledger_name.py (SUMMARY_FIDELITY_JUDGE_DRIFT_EVALS_TUNING = "drift-evals-tuning"), config/ledgers.json (raw-and-compact, prefix ["summary-fidelity-judge", "drift-evals-tuning"]), backend/idhazh/ledger/keys.py (_JUDGE_DOOR_SHAPES), backend/idhazh/ledger/staging.py (REGISTRY, no digest.yml label) and frontend/src/lib/data/slice-shapes.ts (LEDGER_NAMES)
  - config/gardener/compact-summary-fidelity-judge-drift-evals-tuning.json (new), config/idhazh_gardener.json (task_names) and backend/tests/contracts/test_gardener_config.py (RETENTION_LEDGERS)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (auto_apply_tuning with no default, tuning_every_days, max_weight_step, max_rho_step: RC14 to RC16)
  - backend/idhazh/summary_fidelity_judge/tuning.py (new: when tuning is due, the proposal inside the step box, the four guards, apply or hold)
  - backend/utilities/summary_fidelity_replay.py (row #8): its core moves into the judge's package so the unit can call it, and the utility stays the operator's front, so the scheduled replay and the operator's replay are one code path
  - backend/idhazh/summary_fidelity_judge/tenant.py (committed_paths gains the ledger; run_shard tunes on a due night; settle files the rows; the combined score reads the latest applied row filed before the date it judges and stamps its tuning_version)
  - backend/tests/summary_fidelity_judge/test_tuning.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md (the loop, its guards and its off switch) and docs/architecture/contracts/state-ledgers.md (one row)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/, backend/tests/contracts/ and backend/tests/workflows/; CI - full suite. Observation, not a gate: the first tuning night's run time inside the unit, and its row.
- **Oracle:** over fixture histories, a proposal outside its range, over its step, raising false alarms on reshuffled history or lowering worst-case detection is held with that reason, and one that passes every guard is applied under a new tuning_version that the next night's combined row names (H3.27); a night inside tuning_every_days of the newest tuning-run row runs no tuning; auto_apply_tuning false files the same proposal as held and the next night keeps the last applied values; a member declared tuning_pinned never moves; config/judges/summary-fidelity-judge.json reads back unchanged after a tuning night; assertions on reshuffled rates sit far from their lines, never on an exact repeat (C10). Cannot settle: whether the injected faults resemble the faults the pipeline will make.

Table X4 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| X4.1 | The replay runs inside the judge's own unit on a judged night when the newest tuning-run row is tuning_every_days (RC15) or more days old, or none is filed; it reads through ledger.load_days one judged date at a time, and settle files its rows | Owner, 2026-10-11 (QQ27; P8); CLAUDE.md Guardrail #12 |
| X4.2 | It proposes weights by the best worst-case detection on the injection library and rho from quiet stretches; weights are never negative | Owner, 2026-10-11 (QQ9; P25) |
| X4.3 | It searches only values one step can reach from those in force, inside each declared range, so the loop moves toward the best set in capped steps rather than proposing a set the step guard always holds | Owner, 2026-10-11 (QQ27: a capped step; P46: a weight reaches 3 from 0 in three tunings) |
| X4.4 | A proposal is applied only when every guard passes: each value inside its declared range; each change within max_weight_step or max_rho_step (RC16); the share of reshuffled dates on which a member or the combined score crosses at or under false_discovery_rate; worst-case detection on the injected faults no worse than with the values in force. Otherwise every value is held and the values in force stay | Owner, 2026-10-11 (QQ27); P18 |
| X4.5 | A replay with no reshuffled history to measure holds every value, so the first tunings wait for history rather than guess | Owner, 2026-10-11 (QQ27: otherwise keeps the current values) |
| X4.6 | Every proposal, applied or held, is one tuning-run row with each guard's result and why a value was held (Table X9); the night's combined row names the tuning_version in force | Owner, 2026-10-11 (QQ10, QQ27, QQ30 C1) |
| X4.7 | The loop never writes the settings file, which keeps the starting values and bounds; each night reads the latest applied tuning row filed before the date it judges, and a member the settings file declares tuning_pinned true keeps its declared weight and rho, for which tuning proposes nothing | Owner, 2026-10-11 (QQ27; P17); the field's name: proposed for the owner's single approval of the plan (QQ26) |
| X4.8 | auto_apply_tuning (RC14) has no default; false stops application at once: the replay still runs and files its proposals as held, and the last applied values stay | Owner, 2026-10-11 (QQ27) |
| X4.9 | drift-evals-tuning sits beside drift-evals in the family summary-fidelity-judge and declares both row kinds now, the tuning run and row #33's metric move, so its shape is approved once, with the plan (QQ26) | Owner, 2026-10-11 (QQ11 C1, QQ30 C1; P41, P42) |
| X4.10 | Key run_id, date, row_kind and check_name, with no preference: every council run's tuning night is kept, and a reader takes the latest run of a date | ledger-registry.md (the rule a judge ledger follows); owner, 2026-10-11 (P1) |

### Row #33 - Automatic promotion and pausing of metrics at each scheduled replay, every move recorded; auto_promote_metrics stops it

- **Scope:** In the same scheduled replay, after tuning, every paused member is tested for promotion - at least promotion_min_days (28) usable days, false alarms on reshuffled history on target, its own planted fault caught in at least promotion_min_detection (0.8) of the replayed weeks, and a typical night within crossings_budget - and turns active at weight 0 until the next tuning, or at its predecessor's starting weight when it replaces a member for the same reader harm, which retires that night. An active member that alarms too often on unchanged history goes back to paused. Every move is a metric-move row in drift-evals-tuning; auto_promote_metrics false stops both moves at once.
- **Level:** 3 (a move is a row of row #32's shape; the row decides how a member's status changes without a person).
- **Files touched:**
  - backend/idhazh/summary_fidelity_judge/promotion.py (new: the four tests, pausing, the replacement rule, and each member's status for a night)
  - backend/idhazh/summary_fidelity_judge/tenant.py (run_shard runs promotion after tuning on a due night; settle files the move rows; every night binds each declaration at its status for that night)
  - The module row #4 binds declarations in (re-derive at dispatch): a declaration's status is its declared one, moved by the latest move row filed before the night
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (auto_promote_metrics with no default, promotion_min_days, promotion_min_detection: RC17 to RC19; the declaration field naming the member a replacement replaces, X5.3)
  - backend/tests/summary_fidelity_judge/test_promotion.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md (how a member moves and how to read a move; the owner step of P13 replaced)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/; CI - full suite.
- **Oracle:** over fixture histories, a paused member one usable day short of promotion_min_days stays paused and its test values land on the tuning-run row; with enough days, its planted fault caught in 0.9 of the weeks, false alarms on target and a typical night within budget, it turns active at weight 0; a declared replacement turns active at its predecessor's starting weight and the predecessor reads retired from that night; an active member over the false-alarm target reads paused the next night; auto_promote_metrics false moves nothing while the test values still land; the settings file reads back unchanged. Cannot settle: whether a member's planted fault is the fault that matters to a reader.

Table X5 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| X5.1 | At each scheduled replay a paused member turns active only when all four hold: at least promotion_min_days (RC18) usable days in its series; its false-alarm rate on reshuffled history at or under false_discovery_rate; its own planted fault from row #8's injection library - row #31's planted rows for the key-fact members - caught in at least promotion_min_detection (RC19) of the replayed weeks; a typical night, with it active, within crossings_budget | Owner, 2026-10-11 (QQ28; P18) |
| X5.2 | A promoted member joins the combined score at weight 0 until the next tuning gives it one; a member declared as replacing another for the same reader harm takes its predecessor's starting weight instead, and the predecessor retires that night | Owner, 2026-10-11 (QQ28, QQ31; P46) |
| X5.3 | A replacement names the member it replaces in its own declaration, so the link is config read when the declaration binds, never inferred from names | Owner, 2026-10-11 (QQ31; P13: a declaration is config) |
| X5.4 | An active member whose false-alarm rate on reshuffled history is over target goes back to paused | Owner, 2026-10-11 (QQ28) |
| X5.5 | The tuning-run row lists every paused member's four test values, so a member that never qualifies leaves its evidence; a move files a metric-move row of its own with from, to, the test values and the reason (Table X9) | Owner, 2026-10-11 (QQ28, QQ30 C1); Table A, A7 |
| X5.6 | A member's status on a night is its declared status moved by the latest move row filed before that night; the loop never writes the settings file, and a member the file declares retired never moves | Owner, 2026-10-11 (QQ27, QQ28; P13, P17) |
| X5.7 | auto_promote_metrics (RC17) has no default; false stops both moves at once, while the test values still land on the tuning-run row | Owner, 2026-10-11 (QQ28) |
| X5.8 | Promotion runs after tuning in the same replay, so a member promoted tonight gets a weight at the next tuning, never tonight's | Owner, 2026-10-11 (QQ28: weight 0 until the next tuning) |
| X5.9 | This replaces P13's owner ruling that made a paused declaration active; switching the key-fact check's model stays the owner's (row #31) | Owner, 2026-10-11 (P13's note, QQ28) |

### Row #34 - Automatic responses to a drift reading: the stored diagnosis, the larger key-fact sample and one self-closing GitHub issue; auto_respond_to_drift stops them

- **Scope:** When the drift judge's night reads a quality alarm - the combined score or a judged quality member crossed on drift_consecutive_nights nights - its diagnosis is always stored - the night's rows: which members moved, raw and adjusted, which recorded inputs changed inside the window - and two responses follow, both stopped at once by auto_respond_to_drift false: the digest run keeps keyfact_sample_per_day times drift_sample_multiplier (2) sampled summaries a date until the alarm clears; and the judge opens one GitHub issue, found by a fixed label, updates it each night the alarm lasts and closes it when it clears, holding only metric names, numbers and recorded input names. Behaviour-only changes are recorded, never raised.
- **Level:** 5 (one new field on DriftEval, keyfact_sample_multiplier, the key-fact sample multiplier each night orders (X6.3, H3.30), named here for the owner's single approval of the plan, QQ26; and one outbound effect, the issue B3 now allows).
- **Files touched:**
  - backend/idhazh/summary_fidelity_judge/quality_alarm.py (new: whether a night is a quality alarm, from stored rows by row #13's reading-level rule, and its diagnosis)
  - backend/idhazh/summary_fidelity_judge/alarm_issue.py (new: the issue's title and body from a fixed template; find by label, open, update, close; standard-library HTTP over an injected transport)
  - backend/idhazh/summary_fidelity_judge/tenant.py (settle responds after filing, when auto_respond_to_drift is true)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (auto_respond_to_drift with no default, drift_sample_multiplier: RC20 and RC21)
  - backend/idhazh/contracts/drift_eval.py (keyfact_sample_multiplier, the multiplier the night orders on its combined_score rows, with version and changelog, X6.3) and its contract fixture
  - backend/idhazh/stages/keep_sampled_articles.py (row #29's stage: the date's quota times the multiplier the newest judged date's rows order)
  - .github/workflows/llm-council.yml (save_council_results gains issues: write; the settle step's environment carries the token) and the [per-job permission test](../backend/tests/workflows/test_llm_council_workflow.py) (re-derive at dispatch: git grep -n "permissions" backend/tests/workflows)
  - backend/tests/summary_fidelity_judge/test_quality_alarm.py and test_alarm_issue.py (new: recorded GitHub responses), and the keep stage's test (the larger sample)
  - docs/architecture/publishing/summary-fidelity-judge.md (what raises the issue, what it holds, how to stop it) and docs/architecture/publishing/llm-council.md (why the save job may write issues)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/, backend/tests/workflows/ and the keep stage's tests; CI - full suite.
- **Oracle:** over fixtures of stored rows and recorded GitHub responses, two consecutive nights with the combined row crossed open one labelled issue whose body holds only declared metric names, numbers and input names; a third night updates the same issue and a quiet night closes it; a crossing of a copying member alone calls nothing; the night's combined_score rows carry drift_sample_multiplier during the alarm and 1 once it clears, and the keep stage keeps the base times the newest judged date's stamp; auto_respond_to_drift false calls nothing and stamps 1 while the rows still file. Cannot settle: whether a person reads the issue; a live GitHub call (Guardrail #7).

Table X6 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| X6.1 | A quality alarm is the drift reading on the combined score or a judged quality member, crossed on drift_consecutive_nights nights, derived from stored rows by row #13's rule; watch and evaluator readings, and changes only in copying or length, are recorded and never raised | Owner, 2026-10-11 (QQ8, QQ29); B3 |
| X6.2 | Every alarm's diagnosis is its night's stored rows: which members crossed, each one's raw and adjusted values and effect, and the recorded inputs that changed inside its window; this row stores nothing new for it | Owner, 2026-10-11 (QQ10, QQ29, QQ30 C1) |
| X6.3 | While a quality alarm lasts the digest run keeps keyfact_sample_per_day times drift_sample_multiplier (RC21) sampled summaries a date, and the base once it clears. The judge decides: each night's combined_score rows carry the multiplier that night orders - drift_sample_multiplier during a quality alarm with auto_respond_to_drift true, otherwise 1 - and the digest run reads the newest judged date's stamp inside the council's repair window through ledger.load_days, so the rule lives in the judge and the digest never reads the judge's settings file. Row #3's settings in force carry neither setting, so the field is new on DriftEval as keyfact_sample_multiplier (H3.30), named here for the owner's single approval of the plan, QQ26 | Owner, 2026-10-11 (QQ29, QQ30 C1: drift records stay in the drift-evals rows; P6) |
| X6.4 | One open GitHub issue per quality alarm, found by one fixed label declared in the judge's package: opened the first night, updated each night the alarm lasts, closed the night it clears, written from settle in the save job | Owner, 2026-10-11 (QQ29, QQ30 C1); B3 |
| X6.5 | The issue holds metric names, numbers and the names of recorded inputs, the series named by its model id, from a fixed template: never article text, a title, a source name or a summary | Owner, 2026-10-11 (QQ29); CLAUDE.md Guardrail #11; Table C, C7 |
| X6.6 | The call uses the standard library over an injected transport, with the token from the environment and never in a log, as the gardener's GitHub adapter does; tests read recorded responses | backend/idhazh/gardener/github_collections.py; CLAUDE.md Guardrails #7 and #8 |
| X6.7 | save_council_results gains issues: write and nothing else; the judging cells keep their read-only token, so no unit that reads article text holds a write token | Owner, 2026-10-11 (QQ29); [Per-job permissions](../docs/reference/github-actions.md#llm-council-permissions) |
| X6.8 | auto_respond_to_drift (RC20) has no default; false stops the larger sample and every GitHub call at once, while the rows and their diagnosis still file; an issue already open stays as last written | Owner, 2026-10-11 (QQ29; Table RC, RC20) |
| X6.9 | Nothing published is touched: no rank, source, prompt, setting or summary moves | Owner, 2026-10-11 (QQ29; P40); B2 |
| X6.10 | A night the gate publishes record-only because the would-be withheld share passed withhold_share_ceiling is named in the open quality-alarm issue; whichever of this row and row #23 lands second adds that line | Owner, 2026-10-11 (QQ12 A1) |

### Row #35 - summary-grounding-judge at night: IBM Granite Guardian 3.3 8B classifies each summary sentence against the kept article text

- **Scope:** summary-grounding-judge joins the council as a judge of its own that runs IBM Granite Guardian 3.3 8B (row #40) through the pinned llama.cpp runtime. Each night it takes up to faithfulness_checks_per_night (8) summaries of the judged date - planted_checks_per_night (2) planted unfaithful variants first, then the gate's would-be withholds and withheld summaries, then sampled ones - and classifies each summary sentence against the kept article text with the groundedness criterion in no-think mode, yes or no, never writing a summary, stopping inside faithfulness_check_budget_minutes (40) and filing what it skipped. Verdicts go to grounding-verdicts (Table X9); once it catches at least min_planted_caught (0.8) of a week's planted variants, the share it confirms feeds the gate's guard and its disagreement with the main scorer is charted.
- **Level:** 5 (a new ledger, grounding-verdicts, and a new judge with runs_model true; its shape, Table X9, is named here for the owner's single approval of the plan, QQ26).
- **Files touched:**
  - config/judges/summary-grounding-judge.json (new: lifecycle_status, runs_model true, served_model and grounding_prompt (RC30), faithfulness_check_budget_minutes (RC29), planted_checks_per_night and min_planted_caught (RC37, RC38), its decode temperature) and backend/idhazh/contracts/knobs/summary_grounding_judge.py (new)
  - config/llm_council.json (judge_names gains summary-grounding-judge)
  - backend/idhazh/summary_grounding_judge/__init__.py, settings.py and tenant.py (new: one unit; prepare orders the date's entries; run_shard checks inside the budget; settle files; nights_outstanding the dates in the window with kept entries and no verdict)
  - backend/idhazh/summary_grounding_judge/check.py (new: one sentence against the kept article through the grammar; yes stored as unsupported) and the prompt template the config names, under backend/idhazh/prompts/ (new)
  - backend/idhazh/contracts/grounding_verdict.py (new: GroundingVerdict, Table X9), backend/idhazh/contracts/__init__.py (CONTRACTS) and one fixture through backend/tests/contracts/_fixtures.py
  - The ledger's registration as ledger-registry.md requires: backend/idhazh/contracts/ledger_name.py (SUMMARY_GROUNDING_JUDGE_GROUNDING_VERDICTS = "grounding-verdicts"), config/ledgers.json (a new family summary-grounding-judge holding it, raw-and-compact), backend/idhazh/ledger/keys.py (_JUDGE_DOOR_SHAPES), backend/idhazh/ledger/staging.py (REGISTRY) and frontend/src/lib/data/slice-shapes.ts (LEDGER_NAMES, LEDGER_FOLDERS)
  - config/gardener/compact-summary-grounding-judge-grounding-verdicts.json (new), config/idhazh_gardener.json (task_names) and backend/tests/contracts/test_gardener_config.py (RETENTION_LEDGERS)
  - config/idhazh.json (ledger.published gains grounding-verdicts), frontend/src/lib/server/ledger-rows.ts (its build-time reader) and frontend/src/routes/console/model/+page.server.ts and +page.svelte (the daily disagreement share)
  - backend/tests/summary_grounding_judge/ (new: recorded completions) and backend/tests/council/ (re-derive at dispatch: tests that enumerate judge_names)
  - docs/architecture/publishing/summary-grounding-judge.md (new: the judge's own page), docs/architecture/publishing/llm-council.md, docs/architecture/contracts/state-ledgers.md and docs/architecture/publishing/console.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_grounding_judge/, backend/tests/council/, backend/tests/contracts/ and backend/tests/workflows/, and the frontend checks; CI - full suite. Observation, not a gate: the first live night's summaries checked and skipped and the minutes used, against faithfulness_check_budget_minutes.
- **Oracle:** recorded completions (Guardrail #7): a sentence the article supports reads supported, a planted sentence with a swapped number reads unsupported, and a reply outside the grammar is unparsed; with a fixture clock the unit stops before a summary that would pass the budget and files it as skipped; the gate's summaries are taken before sampled ones; the rendered prompt carries the criterion's no-think form with the article before the sentence; a gate summary with one unsupported sentence counts as confirmed. Cannot settle: accuracy on this digest's news - the model's card reports 0.669 balanced accuracy on AggreFact-CNN in no-think mode against 0.761 on average - which the planted test bounds only for faults like the planted ones.

Table X7 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| X7.1 | summary-grounding-judge is a council judge of its own that runs a model: config/judges/summary-grounding-judge.json with runs_model true, its slug in judge_names, its package summary_grounding_judge, and grounding-verdicts in its own family | Owner, 2026-10-11 (QQ16 C1; P47) |
| X7.2 | It classifies each summary sentence against the kept article text with Granite Guardian 3.3 8B's groundedness criterion in no-think mode and never writes a summary; the criterion's yes names the risk, a claim the context does not support, so yes is stored as unsupported and no as supported | Owner, 2026-10-11 (QQ16 A1 and B1); the model's card, ibm-granite/granite-guardian-3.3-8b (yes is the risky answer) |
| X7.3 | Up to faithfulness_checks_per_night (RC26) summaries a night: its planted variants first (X7.7), then the gate's would-be withholds and withheld summaries, then sampled ones; inside faithfulness_check_budget_minutes (RC29) it stops when the next summary would not fit and files what it skipped | Owner, 2026-10-11 (QQ16 A1); Q51 |
| X7.4 | One unit a night, so the budget is one clock and the weights are restored once; the article is the shared prefix of every sentence's call, so the server's prompt cache pays its prefill once a summary | Owner, 2026-10-11 (QQ16: one budget a night); backend/idhazh/council/tenancy.py (shard_count) |
| X7.5 | The model and its prompt template are named in config (served_model and grounding_prompt, RC30), so a later model is a config change plus the same planted-fault test; a change of either starts a new series of its verdicts | Owner, 2026-10-11 (QQ16 B1); P14; owner, 2026-10-12 (QQ19) |
| X7.6 | Each night it also classifies planted unfaithful variants of kept summaries - one sentence with a number, a name or a date swapped, or negated, from row #8's injection library - filed as checked_because planted; its other checks feed the gate's guard and the chart only while it calls at least min_planted_caught (RC38) of a week's planted variants unsupported | Owner, 2026-10-11 (QQ12: QQ28's test, row #35; QQ16) |
| X7.7 | Of the faithfulness_checks_per_night (RC26) summaries, planted_checks_per_night (RC37, 2) are planted variants, checked first so the catch test never runs out of budget; its verdicts count only while it calls at least min_planted_caught (RC38, 0.8) of a week's planted variants unsupported. Both live in the judge's own file, because a judge's file is read only by that judge and promotion_min_detection is the drift judge's | Proposed for the owner's single approval of the plan (QQ26); owner, 2026-10-11 (P6; QQ16 A1: 8 a night); RC19 (the drift judge's line, 0.8) |
| X7.8 | A gate summary is confirmed when at least one of its sentences is unsupported; the confirmed share over gate_trial_days is what the gate's guard reads in rows #22 and #23 | Owner, 2026-10-11 (QQ12 A1, QQ16 A1) |
| X7.9 | Each row stores the main scorer's score and line for its summary, so the disagreement is read from grounding-verdicts alone; the Summaries page charts the daily disagreement share | Owner, 2026-10-11 (QQ14 A1, QQ16 A1; P45); research record section 7.4 |
| X7.10 | grounding-verdicts holds verdicts, numbers, identities and the source, never article or summary text, so it can join ledger.published for the chart | Owner, 2026-10-11 (QQ14 B1); owner, 2026-10-12 (QQ32) |
| X7.11 | Answers come out of a grammar; a reply outside it is unparsed and never a verdict; thinking is off; row #28 holds this judge to the shared guards | backend/idhazh/similarity/judge.py; owner, 2026-10-12 (QQ25) |
| X7.12 | The judge lands paused and turns active in the row's last commit naming QQ16, after Carmack has read row #40's measurement | [Activation rule](../docs/architecture/publishing/llm-council.md#design-rationale-a-new-judge-starts-paused); owner, 2026-10-11 (QQ16) |

### Row #36 - The cost of per-sentence faithfulness, measured before the eval-row change

- **Scope:** before row #37 changes the eval row, one dispatch measures what per-sentence faithfulness costs on a day's worth of committed summaries and their article text: the newest rows of corpus/corpus.jsonl, CLAUDE.md section 0a's committed exception, as many as the eval ledger scored that day. On one stock ubuntu-latest runner the pinned scorer scores each summary both ways - the whole summary over windows, and each sentence against each window through score_by_sentence, landed here and unused until row #37 - and the record gives pairs, seconds per pair and per summary, and the day's scorer-minutes each way against the estimate: 12.5 today, 35 to 40 per sentence, about 48 to 53 while both run. Only numbers leave the job.
- **Level:** 3 (a measurement utility, a dispatch option and a function nothing calls yet; nothing a later run reads is persisted, and nothing a reader sees changes).
- **Files touched:**
  - backend/idhazh/evals/hhem.py (score_by_sentence: each sentence of the summary, cut by one sentence rule, against every window of the premise; each sentence's best window; the mean, the lowest, the counts under 0.50 and 0.80, the winning windows and the pairs scored)
  - backend/utilities/measure_sentence_faithfulness.py (new: reads the newest corpus rows, and that day's scored count and per-shard item counts through ledger.load_days; scores each summary both ways in one process; writes a report of numbers only)
  - .github/workflows/measure.yml (measure.target gains the option that runs it with the faithfulness extra and the pinned scorer weights; re-derive at dispatch: git grep -n "target" .github/workflows/measure.yml)
  - backend/tests/test_evals.py (score_by_sentence against a stub scorer; re-derive at dispatch: git grep -l score_over_chunks backend/tests)
  - The utility's test (new: the report's arithmetic on built rows; re-derive the folder at dispatch: git grep -l "backend/utilities" backend/tests)
  - backend/tests/workflows/ (the new measure.target option; re-derive at dispatch: git grep -n measure.yml backend/tests/workflows)
  - docs/reference/benchmarks/what-per-sentence-faithfulness-costs.md (new: the reading with its runner, processor, date and run, the sample's article lengths beside the day's, and the estimate it tested) and docs/reference/github-actions.md (measure.yml's line)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/test_evals.py, the utility's test and the measure.yml workflow tests; CI - full suite. Observation, not a gate: one dispatch of the new option on the branch, its figures written into the benchmark page and the pull request; row #37 starts from this reading.
- **Oracle:** with a stub scorer whose score for each pair is written down, a two-sentence summary over a 1,000-word premise (two 900-word windows at overlap 150) scores four pairs and returns each sentence's best window, the mean and the lowest; a one-window premise scores one pair per sentence; the report's minutes recompute from its own per-summary numbers; neither the report nor the job's log carries article or summary text. Cannot settle: another runner's figures (the processor drawn is named, not removed); how far the corpus's counterweight filter moves the sample's article lengths from the day's scored set, which the record prints side by side.

Table Y1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| Y1.1 | The cost is measured once, on committed data, before the eval-row change, and row #37 starts from the reading | Owner, 2026-10-11 (QQ15 C1); review record SP3 (I1: approve after a one-day measurement, which Carmack runs) |
| Y1.2 | The sample is the newest corpus rows - the only committed summaries that keep the article text the model saw - as many as the eval ledger scored that day, and the per-summary cost is scaled to that count | Owner, 2026-10-11 (QQ15 C1); CLAUDE.md section 0a (corpus/ is a committed exception) |
| Y1.3 | Both ways are scored in one process on one runner, so their ratio does not depend on the processor drawn; the record names the runner, the processor, the date and the run | CLAUDE.md Guardrail #10; docs/reference/benchmarks/the-processor-lottery.md |
| Y1.4 | What is timed is what ships: score_by_sentence lands here, and row #37 wires it in unchanged | Owner, 2026-10-11 (QQ15 C1); plan 36 E9 (measure the real call before trusting a budget) |
| Y1.5 | The estimate under test: 12.5 scorer-minutes a day today (r4 median; 1.1 s median and 2.0 s mean a summary); the per-sentence minutes are measured on the summaries' own sentence counts, never on an assumed summary length (owner, 2026-10-12, Q60), and they run beside the old score while the old score runs beside the new (row #38) | Owner, 2026-10-11 (QQ15, as corrected; P31); review record SP3 (I1) |
| Y1.6 | The record also sizes the work shard: the minutes the day's busiest shard would add, against run.shard_timeout_minutes | docs/reference/pipeline-cost.md ("Size against the slowest credible shard") |
| Y1.7 | Article text is data and never leaves the job: no article or summary text in the record, a log, a commit message or a path | CLAUDE.md section 0a; CLAUDE.md Guardrail #11 |

### Row #37 - One eval-row change: per-sentence faithfulness, name and date checks, a stamp per scored column and a replaceable scorer

- **Scope:** one change to EvalRow and its writers (Table Y7). Each summary sentence is scored against every window of the text the model saw through row #36's score_by_sentence, and the row keeps the mean, the lowest sentence, the sentences under 0.50 and 0.80 and each sentence's winning window. unsupported_names and unsupported_dates count the names and dates the summary states that the full article does not. Three stamps name the instrument behind each scored column: the faithfulness scorer with its revision, weights, window geometry and installed libraries (closing B10), METRICS_VERSION for the counterweights, and coherence's encoder. The scorer is named in config, and the three hhem columns take names that do not name it. The whole-summary score keeps being written.
- **Level:** 5 (a persisted shape: new and renamed eval-row columns with their read-side migration; the per-sentence series starts here; the owner's sign-off in QQ15).
- **Files touched:**
  - backend/idhazh/contracts/eval_row.py (the columns of Table Y7, appended and null on older rows; RENAMED_CELLS gains hhem, hhem_full and hhem_delta; metrics_version read from scorer_version on an older row; the delta validator on the new names; one changelog entry, keeping five as CLAUDE.md section 11 allows)
  - backend/idhazh/contracts/knobs/evaluation.py and config/idhazh.json (faithfulness_scorer in the evaluation block: id, repository and a 40-character revision, refused otherwise, beside chunk_words and chunk_overlap_words; one AppConfig changelog entry)
  - backend/idhazh/evals/hhem.py (HHEM_MODEL, HHEM_REVISION and HHEM_SCORER_ID leave the code for that declaration; the loader and is_pinned read it; the installed scorer libraries are read when it loads)
  - backend/idhazh/evals/metrics.py (unsupported_names and unsupported_dates; the faithfulness stamp derived beside scorer_version; METRICS_VERSION stays 4) and backend/idhazh/evals/score.py (to_eval_row fills the sentence columns, the two checks and the three stamps)
  - backend/idhazh/stages/work.py and backend/idhazh/cli.py (the scorer built from its declaration, the stamps built once a shard, the sentence pass inside the score span), and every other builder of the scorer (re-derive at dispatch: git grep -n -e HHEM_MODEL -e HHEM_REVISION -e HHEM_SCORER_ID -e "HhemScorer(" backend)
  - backend/idhazh/stages/assemble.py (score.verdict reads summary_faithfulness, so the published band is unchanged)
  - backend/idhazh/contracts/day_metrics.py (INSTRUMENT_COLUMNS follow the rename, and a committed day record that names hhem reads under the new name; re-derive the producer at dispatch)
  - config/judges/summary-fidelity-judge.json (if rows #4 to #7 have landed: every member that names hhem - the three faithfulness members and scored_nulls - spells the renamed column and keeps scorer_version as its instrument, so no series restarts here (Y2.10); the per-sentence members of row #38 take faithfulness_instrument, G1.7; re-derive at dispatch)
  - Every other reader of the renamed columns, from git grep -n -w -e hhem -e hhem_full -e hhem_delta -- backend frontend config docs at dispatch (corpus.py, evals/labels.py, evals/evidence.py, the gate if row #22 has landed, the console's ledger-rows.ts and Summaries page, the published columns, the frontend vocabulary tests); the console's queries read compact files packed under either name
  - backend/tests/test_evals.py, backend/tests/test_corpus_harvest.py, backend/tests/contracts/ and backend/tests/pipeline/ (re-derive at dispatch: an older row read under the new names, the two checks, the stamps, an unchanged published band)
  - docs/concepts/evaluation.md (faithfulness scored per sentence, the stamps, the scorer named in config), docs/concepts/summary-metrics.md (unsupported_names and unsupported_dates), docs/architecture/publishing/autotune-summary-quality.md and docs/how-to/label-the-faithfulness-queue.md (the column names)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/test_evals.py, backend/tests/test_corpus_harvest.py, backend/tests/contracts/, backend/tests/pipeline/ and backend/tests/summary_fidelity_judge/ where it exists, and the frontend checks for the console's readers; CI - full suite. Observation, not a gate: the first digest run after the merge, read for scored rows whose new columns are null and for its work shards' scorer minutes against row #36's reading.
- **Oracle:** an eval row written before the change reads back with its hhem cells under the new names, null in every new column and metrics_version 4 from its scorer_version; for a built item and a stub scorer, a two-sentence summary over a two-window article stores the mean, the lowest, both counts and the winning windows the stub implies; a summary naming a person and a date the full article never states counts one of each, and a summary naming only what the article states counts none; the faithfulness stamp moves when the configured revision, the weights digest, the window or an installed scorer library moves, and not when a band line moves; a scorer revision that is not a 40-character commit is refused by name; a built day publishes the same bands as before. Cannot settle: whether a lexical check finds the names and dates a reader would call errors (FRANK's categories are not tested here); whether the sentence score removes the long-article mark-down on live rows, which row #38's replay and the length-band adjustment show.

Table Y2 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| Y2.1 | One eval-row change carries every part QQ15 names, so the new faithfulness series starts once, here, while the members already declared keep theirs (Y2.10) | Owner, 2026-10-11 (QQ15 B1; P31; P38); review record SP3 (I1, I2 and I6 as one change) |
| Y2.2 | Each sentence is scored against every window of the text the model saw and keeps its best window; the row stores the mean as an index, the lowest sentence as a gate, the counts under 0.50 and 0.80, and the winning windows as a position profile | Owner, 2026-10-11 (QQ15 B1); research record sections 4.2 (steps 1 to 4) and 7.1 (rank 1) |
| Y2.3 | The whole-summary score, its full-article twin and their difference keep being written under their new names: the old faithfulness members judge the first until they retire (row #38), and the published band reads it, which this row does not move | Owner, 2026-10-11 (QQ15 C1); research record section 4.2 (step 5: keep the whole-article score and the delta as diagnostics) |
| Y2.4 | The three hhem columns take names that do not name the scorer, and older rows read under them through RENAMED_CELLS, the read-side migration eval_row.py already runs; every reader moves in this change | Owner, 2026-10-11 (P38); CLAUDE.md sections 0b and 11 |
| Y2.5 | The scorer is named in config - id, repository and pinned revision in the evaluation block, beside the window size already there - and hhem.py keeps the loader and no model constant; a revision that is not a 40-character commit is refused, as is_pinned asks today | Owner, 2026-10-11 (P38; QQ15 B1); CLAUDE.md section 10 |
| Y2.6 | unsupported_names and unsupported_dates are lexical, read the full article as unsupported_numbers does, add no dependency, and band, stamp and withhold nothing in this plan | Owner, 2026-10-11 (QQ15 B1; QQ12 B2); review record SP3 (I2); research record section 7.1 (rank 2) |
| Y2.7 | Every stamp is derived from what loaded, never hand-typed: faithfulness_instrument spells the scorer, its revision, the weights digest, the window geometry and the installed scorer libraries; metrics_version carries METRICS_VERSION; coherence_instrument carries the encoder reference embed.py defines | Owner, 2026-10-11 (QQ15 B1, which closes B10 and brings in B11); research record section 7.4 (item 1); review record SP3 (I6) |
| Y2.8 | The window geometry in the faithfulness stamp includes the sentence rule, because a new rule changes every sentence column | Owner, 2026-10-11 (P14: a series names every field whose change changes its column, G1.6) |
| Y2.9 | METRICS_VERSION stays 4: the two checks are columns nothing bands, which metrics.py's own rule says never moves it, so scorer_version does not move | backend/idhazh/evals/metrics.py (METRICS_VERSION's comment); review record SP3 (I2 priced a move to 5) |
| Y2.10 | On an older row, metrics_version is read from the metrics- part of scorer_version, so the counterweight members keep their series; the faithfulness and coherence stamps stay null there, because no older row recorded the installed library or the encoder. The members already declared keep scorer_version as their instrument, which this change does not move (Y2.9), so none of them restarts and the members about to retire keep judging without a 14-night gap; the per-sentence members start their own series on faithfulness_instrument (row #38) | Owner, 2026-10-11 (P14; QQ15 B1); Table B, B10; the instrument the retiring members keep: proposed for the owner's single approval of the plan (QQ26) |
| Y2.11 | No column for the prompt version, quantization or runtime build: the run's recorded inputs already carry prompt_sha256, quantisation and runtime_build (RunRecord.inputs), joined by run_id, and a test holds the three present for row #42 | Owner, 2026-10-12 (QQ19); Table D (row #42); backend/idhazh/contracts/fingerprint.py |
| Y2.12 | New columns are appended at the end of the row and are null, never zero, on a row written before the change | backend/idhazh/contracts/eval_row.py (appended columns; null where nothing was measured); CLAUDE.md section 11 |

Table Y7 - the eval-row fields row #37 adds or renames (names proposed here; what each holds is QQ15 B1's; null on a row written before the change unless the entry says otherwise)

| # | Field | Type | Meaning |
| --- | --- | --- | --- |
| Y7.1 | summary_faithfulness (was hhem) | float, 0 to 1 | The whole summary against its best window of the text the model saw; the published band reads it (score.verdict), and the old faithfulness members judge it until they retire (row #38); stored cells read under the new name through RENAMED_CELLS |
| Y7.2 | summary_faithfulness_full (was hhem_full) | float, 0 to 1 | The same against the article before the truncation cap; a diagnostic |
| Y7.3 | summary_faithfulness_delta (was hhem_delta) | float | summary_faithfulness minus summary_faithfulness_full, rebuilt on every read as today |
| Y7.4 | sentence_faithfulness_mean | float, 0 to 1, or null | The mean over the summary's sentences of each sentence's best-window score against the text the model saw: the index |
| Y7.5 | sentence_faithfulness_min | float, 0 to 1, or null | The lowest sentence's best-window score; the gate's faithfulness line reads it from row #39 |
| Y7.6 | sentences_under_050, sentences_under_080 | int or null | Sentences whose best-window score is under 0.50, and under 0.80; each line is part of its column's definition, spelled in its name |
| Y7.7 | sentence_winning_windows | str or null | The index of each sentence's best window, in sentence order, space-separated, because every eval-row field is a scalar: the position profile |
| Y7.8 | unsupported_names | int or null | Names, runs of capitalised words, that the summary states and the full article does not |
| Y7.9 | unsupported_dates | int or null | Dates the summary states that the full article does not state in any spelling the check normalises |
| Y7.10 | faithfulness_instrument | str or null | Derived, never hand-typed: the scorer's id, repository and revision, its weights digest, the window geometry (size, overlap, anchoring and the sentence rule) and the installed versions of the libraries it runs on; it stamps Y7.1 to Y7.7 |
| Y7.11 | metrics_version | str | METRICS_VERSION, the stamp of the counterweights: compression, extractiveness, verbatim_run, unsupported_numbers, unsupported_names, unsupported_dates, hedge_dropped, self_repetition, the two densities, semantic_coverage and extraction_suspect; on an older row, the metrics- part of its scorer_version |
| Y7.12 | coherence_instrument | str or null | The encoder that scored coherence, as embed.ENCODER_REF spells it; null whenever coherence is null |

### Row #38 - The switchover: per-sentence members land paused, and the old faithfulness members retire by themselves

- **Scope:** the new score runs beside the old (row #37 writes both). The drift judge declares three per-sentence members, paused, each naming the member it replaces: faith_sentence_index for faith_index, faith_sentence_below_050 for faith_below_050 and faith_sentence_below_080 for faith_below_080 (Table RA), each on row #37's faithfulness stamp and with a planted fault of its own. At each scheduled replay QQ28's promotion (row #33) turns a replacement active once it has promotion_min_days (28) usable days and catches its fault, about 4 to 8 weeks in; that night it takes over its predecessor's starting weight (QQ31) and the predecessor retires, both moves recorded. Two more paused members read row #37's name and date checks (Y3.9). Meanwhile the scorer spends about 48 to 53 minutes a day (estimate; row #36 measures it).
- **Level:** 3 (member declarations are config, never a stored row; the moves it files have the shape row #33 records).
- **Files touched:**
  - config/judges/summary-fidelity-judge.json (metrics gains the three replacements, paused, each naming the member it replaces and declaring its predecessor's starting weight, rho 0; and two paused members on row #37's checks, names_unsupported and dates_unsupported, at weight 0 and rho 0, Y3.9)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py (MemberDeclaration gains replaces; the refusals of Y3.8)
  - backend/idhazh/summary_fidelity_judge/registry.py (the refusals, before any night)
  - backend/idhazh/summary_fidelity_judge/member_values.py (the per-sentence columns the three members read; re-derive at dispatch)
  - backend/idhazh/summary_fidelity_judge/planted_faults.py (one declared fault per replacement and per name or date member, written into the cells it reads in stored rows)
  - The promotion step of row #33 (re-derive at dispatch: git grep -n auto_promote_metrics backend/idhazh): a promoted replacement keeps its declared weight, and its predecessor's retirement is filed in drift-evals-tuning beside the promotion, with its reason
  - backend/tests/summary_fidelity_judge/test_registry.py, test_planted_faults.py and the promotion tests (re-derive at dispatch)
  - docs/architecture/publishing/summary-fidelity-judge.md (the switchover and the replaces field) and docs/concepts/evaluation.md (which faithfulness members judge, and from when)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/; CI - full suite. Observation, not a gate: each scheduled replay's promotion record for the three replacements, until all three are active.
- **Oracle:** the committed settings bind the three replacements paused, each naming its predecessor, and the loader refuses a replacement that names no member, a retired member or a member another replacement already names; driven through promotion on a tmp_path ledger, a replacement that passes turns active with its predecessor's starting weight (1), its predecessor's rows leave the step and the combined score that night, and both moves are filed with their reasons; a replacement that misses its planted fault stays paused while its predecessor keeps judging; each planted fault changes exactly the per-sentence cells and amount it declares. Cannot settle: whether 28 usable days hold a regime the replay never saw; whether the sentence-level members read the same harm as the old ones, which the overlap's two series show side by side.

Table Y3 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| Y3.1 | The new score runs beside the old one, and the old faithfulness members keep judging until each replacement turns active | Owner, 2026-10-11 (QQ15 C1) |
| Y3.2 | Three replacements for the same reader harm, one per predecessor: faith_sentence_index (the mean of logit(sentence_faithfulness_mean), clipped at logit_clip) for faith_index; faith_sentence_below_050 (the share of summaries whose lowest sentence is under 0.50) for faith_below_050; faith_sentence_below_080 (the same under 0.80) for faith_below_080 | Owner, 2026-10-11 (QQ2; QQ15 B1); review record SP2 (each member's later instrument) |
| Y3.3 | Each keeps its predecessor's role (judged), adjustment (length band and source) and harm direction, reads faithfulness_instrument as its instrument, and uses row #7's statistics, so no statistic module is added | Owner, 2026-10-11 (QQ2; P13); Table RA (RA1 to RA3) |
| Y3.4 | Each lands paused with rho 0 and a planted fault of its own in the replay's library | Owner, 2026-10-11 (QQ28; P13); row #8 (one declared fault per member) |
| Y3.5 | A replacement turns active only through QQ28's promotion at a scheduled replay: at least promotion_min_days (28) usable days, the false-alarm rate on target, its own fault caught at least promotion_min_detection (0.8) of the time within a week, and a typical night within crossings_budget; about 4 to 8 weeks | Owner, 2026-10-11 (QQ28; QQ15, as corrected) |
| Y3.6 | Each declares its predecessor's starting weight (1, Table RA) as its combine_weight, which counts from the night it turns active; QQ28's weight 0 does not apply to it, and tuning moves it afterwards within its guards | Owner, 2026-10-11 (QQ31 F1; P46; QQ27) |
| Y3.7 | The predecessor retires the night its replacement turns active, filed as a move with its reason beside the promotion, so no night counts both in the combined score; auto_promote_metrics false stops both moves | Owner, 2026-10-11 (QQ28; QQ31 F1) |
| Y3.8 | A declaration names the member it replaces; the loader refuses a name no member has, a retired member, and two replacements of one member | Owner, 2026-10-11 (QQ31; P13); G1.3 (refusals by name before any night) |
| Y3.9 | The name and date checks are declared as two paused judged members, names_unsupported and dates_unsupported - each the share of summaries with at least one, adjusted by source, worse when higher, at weight 0 and rho 0, each with a planted fault of its own - so QQ28's promotion can bring either in once it proves itself; until then they only store | Proposed for the owner's single approval of the plan (QQ26); owner, 2026-10-11 (QQ15 B1, QQ28); research record section 7.1 (rank 2) |

### Row #39 - The gate and the corpus fence read the per-sentence line

- **Scope:** row #22's lowest-sentence faithfulness line is switched on: it reads sentence_faithfulness_min (row #37) against its own line, starting at 0.50 in evaluation.publish_gate; the whole-summary score keeps only its display band. It acts only through its own guards (row #23): record-only, stamping would_be_withheld, until summary-grounding-judge confirms at least gate_min_agreement of its marked summaries over gate_trial_days and each night's share stays under withhold_share_ceiling; then it withholds, and it returns to record-only when either fails or withhold_failing_summaries is false. A withheld summary follows row #23's path. Row #27's corpus fence skips every summary this line marks, live or not, by the stamp, never the score.
- **Level:** 5 (a summary may now be withheld for faithfulness, a change to a published day, and the training corpus takes less; signed off by the owner in QQ12 B2, QQ13 B1 and QQ15).
- **Files touched:**
  - backend/idhazh/evals/publish_gate.py (the lowest-sentence line switched on: sentence_faithfulness_min against its line)
  - backend/idhazh/contracts/knobs/evaluation.py and config/idhazh.json (evaluation.publish_gate gains lowest_sentence_faithfulness_line, 0.50, bounded to the score's range; one AppConfig changelog entry; re-derive at dispatch)
  - backend/idhazh/evals/score.py (to_eval_row hands the gate the row's sentence_faithfulness_min; re-derive at dispatch: git grep -n publish_gate backend/idhazh)
  - The gate's tests (re-derive at dispatch: git grep -l publish_gate backend/tests)
  - backend/tests/test_corpus_harvest.py and backend/tests/pipeline/ (a built day with the line record-only, and the canary day with it live)
  - docs/architecture/publishing/autotune-summary-quality.md (the publish gate's faithfulness line on the lowest sentence at 0.50) and docs/concepts/evaluation.md (which faithfulness line may withhold)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over the gate's tests, backend/tests/test_corpus_harvest.py and backend/tests/pipeline/; CI - full suite.
- **Oracle:** on built items, a summary whose lowest sentence scores 0.45 while its whole-summary score is 0.70 is stamped would_be_withheld with lowest_sentence_faithfulness and left out of the corpus harvest; one whose whole-summary score is 0.45 with every sentence at 0.60 or more is stamped published, keeps its low display band and stays in the corpus; with the line's guards met, the first summary is absent from the canary day and its next-best duplicate is the story's kept item; with them unmet, or with withhold_failing_summaries false, the day is unchanged and the stamps continue; keeps_its_counterweights reads no faithfulness column. Cannot settle: whether 0.50 on the lowest sentence is the right line (P31 asks for it to be re-cut on the new score), which the stamps and the grounding judge's agreement show over time; how many summaries a live day loses, which withhold_share_ceiling bounds.

Table Y4 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| Y4.1 | The faithfulness line that may withhold reads the lowest-scoring sentence and starts at 0.50, a setting of its own with a declared range, apart from the band's cut, so it can be re-cut on the new score without moving the display band | Owner, 2026-10-11 (QQ12 B2; QQ15); P31 (the line must be re-cut on the new score); CLAUDE.md Guardrail #6 |
| Y4.2 | It is the gate's only faithfulness line; the whole-summary score keeps only its display band, so it never withholds and never fences | Owner, 2026-10-11 (QQ12 B2; QQ13 B1); row #22 (O2.2) |
| Y4.3 | It acts only through its own guards, read over its own marked summaries (row #23): record-only until they hold, live while they do, record-only again when either fails, every switch recorded | Owner, 2026-10-11 (QQ15: its own guards decide whether it acts; QQ12 A1); row #23 (O3.2) |
| Y4.4 | The independent check is summary-grounding-judge, and a verdict counts only once that judge has caught planted unfaithful summaries, so the line cannot go live before row #35 has passed its test | Owner, 2026-10-11 (QQ12 A1; QQ16 A1 and C1); row #23 (O3.3) |
| Y4.5 | withhold_failing_summaries false stops this line's withholding from the next run, and its stamps continue | Owner, 2026-10-11 (QQ12 A1); RC28 |
| Y4.6 | A withheld summary is absent from the day, dropped before collapse_same_story so the story's next-best duplicate takes its place, and item-health records it failed with the line and its score | Owner, 2026-10-11 (QQ12 C1); owner, 2026-09-19 (plan 36 section 0e, H1 to H3) |
| Y4.7 | Row #27's corpus fence skips every summary this line marks, record-only or live, by the stamp and never the score, with no change of its own; keeps_its_counterweights stays faithfulness-free | Owner, 2026-10-11 (QQ13 B1); row #27 |
| Y4.8 | key-fact-articles keeps this line's would-be withholds and summary-grounding-judge reads them first, both from the stamp, so rows #27, #29 and #35 do not change | Owner, 2026-10-11 (QQ13 A1; QQ16 A1) |
| Y4.9 | The stamp names this line lowest_sentence_faithfulness, the value row #18 reserved, so the panel's withheld share by reason (row #24) keeps it apart from the unsupported-number line | Row #18 (O1.3); owner, 2026-10-11 (QQ14 B1); CLAUDE.md section 0b |
| Y4.10 | Nothing in this plan moves the line; a re-cut is a reviewed config change | Table B, B2 (no knob moves by itself); owner, 2026-10-11 (QQ15: the line starts at 0.50) |

### Row #40 - Pin the checker model: Granite Guardian 3.3 8B, the Q4_K_M GGUF build

- **Scope:** config/models/ gains Granite Guardian 3.3 8B, the official Q4_K_M GGUF build (4.94 GB, Apache 2.0), pinned by repository, revision, file, sha256 and byte count, with its server settings; the model-server action fetches and serves it, through the pinned llama.cpp runtime, for the cells of the judge whose declaration names it in served_model, and never saves it to the shared cache (X8.6); and a dispatched measurement on a stock runner records its fetch time, peak memory and seconds per sentence on committed corpus/ pairs, which Carmack reads against the runner's 16 GB and the council's clock before row #35's judge turns active.
- **Level:** 5 (a new model the council serves, approved under C2 in QQ16; and two persisted config shapes - ModelsConfig gains a checker slot, and the judge declaration gains served_model - named here for the owner's single approval of the plan, QQ26, X8.4).
- **Files touched:**
  - config/models/granite-guardian-3.3-8b-q4km.json (new: repository ibm-granite/granite-guardian-3.3-8b-GGUF; its revision, file, sha256 and byte_count read from the repository at dispatch; quantisation Q4_K_M; arch granite; server settings with the prompt cache on; no thinking kwarg)
  - backend/idhazh/contracts/knobs/models.py (ModelsConfig gains an optional checker slot; a file declares exactly one served role, and the digest refuses a models_file with no summarizer, X8.4) and backend/idhazh/contracts/knobs/council.py (JudgeDeclaration gains served_model, a config/models file stem, absent meaning the digest's own models_file)
  - backend/utilities/model_refs.py and .github/actions/model-server/action.yml (describe, fetch and serve the model file a cell names; the checker's entry is restored from no cache and saved to none, X8.6)
  - backend/utilities/council_matrix.py and .github/workflows/llm-council.yml (a cell carries its judge's served_model, X8.4)
  - backend/utilities/measure_grounding_check.py (new) and .github/workflows/measure.yml (a dispatched job: fetch, serve, and measure the fetch time, peak memory and seconds per sentence on corpus/ pairs)
  - docs/reference/models.md, docs/reference/models/granite-guardian-3.3-8b-q4km.md (new), docs/reference/ci-model-runtime.md (why the checker is fetched each night and never cached) and docs/reference/benchmarks/what-a-grounding-check-costs.md (new)
  - Tests over the model file and its cache key (re-derive at dispatch: git grep -n describe-pinned-model backend/tests)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over the model-config and workflow tests (re-derive at dispatch); CI - full suite. Observation, not a gate: the dispatched measurement - the server's and the process's peak memory, seconds per sentence with the article cached and not, and the processor drawn - read by Carmack against the 16 GB runner and faithfulness_check_budget_minutes.
- **Oracle:** the committed file validates and names the official repository, Q4_K_M and a 64-character sha256; a cell whose judge declares this served_model fetches it and saves nothing to the cache; a cell whose judge declares none restores the summarizer exactly as before; a models file declaring both slots, or neither, is refused, and so is a models_file with no summarizer. Cannot settle: the fetch time on a later night, which each council run's record shows; a later runner's speed, because the processor drawn varies.

Table X8 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| X8.1 | Granite Guardian 3.3 8B, the official GGUF build from ibm-granite/granite-guardian-3.3-8b-GGUF, Q4_K_M (4.94 GB), Apache 2.0, pinned by revision, file and sha256 in a file of its own under config/models/ | Owner, 2026-10-11 (QQ16 B1; P47: the owner's approval of the new model under C2) |
| X8.2 | Served by the pinned llama.cpp runtime with config/llama-cpp-pin.json unchanged; if the pinned build cannot serve the granite architecture the row stops, because a build change is a runtime change for every model and a series boundary for every metric | Owner, 2026-10-11 (QQ16 B1); owner, 2026-10-12 (QQ19) |
| X8.3 | Its entry has a key of its own, built from its declared files and the runtime build, so it never shares the summarizer's; a cell that serves the summarizer restores exactly as before, and a cell that serves the checker fetches it (X8.6) | Owner, 2026-10-11 (QQ16); .github/actions/model-server/action.yml |
| X8.4 | The checker is declared under a slot named for what it does: ModelsConfig gains checker, a file declares exactly one served role, and the digest refuses a models_file with no summarizer. A council cell learns its model from the judge declaration, which gains served_model - a config/models file stem, absent meaning the digest's own models_file - because the council reads declarations and never a judge's own settings | Proposed for the owner's single approval of the plan (QQ26); CLAUDE.md section 0b; [Judge declarations](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs); Table C, C9 |
| X8.5 | Its memory and minutes are measured on a stock runner from committed corpus/ pairs, because row #29's record may not exist yet; Carmack reads the reading before row #35's judge turns active | Owner, 2026-10-12 (QQ21); Table D (Carmack confirms) |
| X8.6 | The checker's weights are fetched each night and never saved to the shared cache: its 4.94 GB beside the summarizer's 5.68 GB passes the 10 GB allowance, and an evicted summarizer would be fetched again by the next digest run. Row #40's measurement records the fetch time, which Carmack reads against the council's clock; a larger, paid cache stays the owner's decision | Proposed for the owner's single approval of the plan (QQ26); .github/workflows/llm-council.yml (the 10 GB allowance); config/models/qwen3.5-9b-q4km.json (byte_count) |
| X8.7 | Used only in its prescribed scoring mode, a yes or no inside score tags, as its model card requires | The model's card, ibm-granite/granite-guardian-3.3-8b (Scope of Use) |

### Row #41 - summary-failures-by-source, for the feed-quality plan

- **Scope:** each night the drift judge counts, from the judged date's eval rows joined to item-health for each summary's source, one row per source and model series: the summaries scored, the summaries failing each reason - under the gate's faithfulness line, an unsupported number, an extraction flag, withheld by the gate - and the points docked, one per summary with at least one failure, with no weight by reason (Table Y8). settle files the rows through ledger.persist into summary-failures-by-source, a new ledger in the family summary-fidelity-judge, enrolled as ledger-registry.md requires. The judge changes no source's reliability, trust, rank, rest or config; the autotune-feed-quality plan reads the record and decides. The grounding judge's verdicts stay in grounding-verdicts.
- **Level:** 5 (a new ledger in the family summary-fidelity-judge, approved in QQ32).
- **Files touched:**
  - backend/idhazh/contracts/source_summary_failures.py (new: SourceSummaryFailures, Table Y8; schema stem source-summary-failures; version and one changelog entry)
  - backend/idhazh/contracts/__init__.py (CONTRACTS, entered the way row #3 enters DriftEval; re-derive at dispatch)
  - backend/idhazh/contracts/ledger_name.py (SUMMARY_FIDELITY_JUDGE_SUMMARY_FAILURES_BY_SOURCE = "summary-failures-by-source")
  - config/ledgers.json (the family summary-fidelity-judge gains the entry: grain raw-and-compact, prefix ["summary-fidelity-judge", "summary-failures-by-source"])
  - backend/idhazh/ledger/keys.py (_JUDGE_DOOR_SHAPES: the key of Y5.8 and the row contract, imported on first use; no preference) and backend/idhazh/ledger/staging.py (REGISTRY: written by the judge's settle in the council's save job)
  - frontend/src/lib/data/slice-shapes.ts (LEDGER_NAMES gains summary-failures-by-source)
  - config/gardener/compact-summary-fidelity-judge-summary-failures-by-source.json (new: the approved live retention chain, the other fields copied from row #3's declaration) and config/idhazh_gardener.json (task_names gains it)
  - backend/tests/contracts/test_gardener_config.py (RETENTION_LEDGERS), backend/tests/contracts/_fixtures.py (FIXTURE_FILES) and one fixture in the folder it names
  - backend/idhazh/summary_fidelity_judge/failures_by_source.py (new: the night's counts per source and model series, the item-health join included)
  - backend/idhazh/summary_fidelity_judge/tenant.py and backend/idhazh/summary_fidelity_judge/record.py (run_shard writes the rows into the unit's scratch file; settle files them through ledger.persist; committed_paths gains the ledger)
  - backend/tests/summary_fidelity_judge/test_failures_by_source.py (new) and backend/tests/summary_fidelity_judge/test_tenant.py
  - docs/architecture/contracts/state-ledgers.md (one table row) and docs/architecture/publishing/summary-fidelity-judge.md (what the record holds, who reads it, and that the judge acts on no source)
  - Every other file that names the family's ledgers, from git grep -n -e SUMMARY_FIDELITY_JUDGE_DRIFT_EVALS -e "summary-fidelity-judge/drift-evals" backend frontend config docs at dispatch
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/contracts/, backend/tests/council/, backend/tests/workflows/test_ledger_staging.py, backend/tests/workflows/test_ledger_door_jobs.py and backend/tests/summary_fidelity_judge/; CI - full suite.
- **Oracle:** a fixture night of eight summaries from three sources and two model series - one with an unsupported number and an extraction flag, one under the faithfulness line, one stamped withheld - files one row per source and series whose reasons count each summary once per reason, whose points docked count it once, and whose summaries_scored add up to the night's scored summaries; a night whose rows carry no gate stamp files null in withheld_by_gate; a summary with no item-health row counts under no source; the rows read back through ledger.load_days equal what the unit wrote; the tenant's committed_paths name only the family's own ledgers. Cannot settle: what a docked point is worth to a source, which the feed-quality plan decides (B13); whether a source's failures come from its extraction or from the summarizer.

Table Y5 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| Y5.1 | A ledger of its own, summary-failures-by-source, in the family summary-fidelity-judge, never extra rows in drift-evals | Owner, 2026-10-12 (QQ32 R1; P48) |
| Y5.2 | One row per night, source and model series; the night is the judged date, whose eval rows alone are counted, one per distinct summary | Owner, 2026-10-12 (QQ32) |
| Y5.3 | Each reason is counted on its own, so one summary may count under several reasons and docks one point; no weight by reason, because the feed-quality plan sets them | Owner, 2026-10-12 (QQ32) |
| Y5.4 | The reasons, each from the eval row's own cells: under the gate's faithfulness line (the lowest sentence under its line once row #39 switches that line on, the whole-summary score under evaluation.band_medium_min before), at least one unsupported number, extraction_suspect, and a stamp that reads withheld (row #18), never would_be_withheld; the gate's lines are read from config, never copied | Owner, 2026-10-11 (QQ12 B2; QQ15); owner, 2026-10-12 (QQ32); row #22 (O2.3) |
| Y5.5 | withheld_by_gate is null, never 0, on a night whose eval rows carry no stamp, because 0 would claim a count nothing took | backend/idhazh/contracts/eval_row.py (null where nothing was measured); CLAUDE.md section 11 |
| Y5.6 | Plan 65 measures and records: nothing in the judge changes a source's reliability, trust, rank, rest or config, and its only writes are its own ledgers; the autotune-feed-quality plan reads the record and decides | Owner, 2026-10-12 (QQ17 B1; B13; Q52, separation of duties) |
| Y5.7 | The grounding judge's verdicts stay in grounding-verdicts, which names the source too; nothing here copies them | Owner, 2026-10-12 (QQ32) |
| Y5.8 | The row follows the rule a judge ledger follows: run_id is the council run, settle files the rows through ledger.persist under the council's writer identity, and the judged date decides the file; key run_id, date, source_id, model_id, faithfulness_instrument, metrics_version, with no preference | ledger-registry.md (the rule a judge ledger follows); owner, 2026-10-12 (QQ32) |
| Y5.9 | A summary counts under the source item-health records for it, joined on url_key as the judge's source adjustment joins it (row #7); one with no item-health row counts under no source, so a night's rows add up to its scored summaries | Owner, 2026-10-12 (QQ32); review record SP2 (source joins item-health on url_key) |
| Y5.10 | Retention follows the owner-approved live chain | ledger-registry.md (what a new ledger owes); test_every_ledger_uses_the_approved_live_retention_chain |

Table Y8 - SourceSummaryFailures, one row per judged night, source and model series per council run (schema stem source-summary-failures; QQ32)

| # | Field | Type | Meaning |
| --- | --- | --- | --- |
| Y8.1 | run_id | RunId | The council run that counted the night (the rule a judge ledger follows) |
| Y8.2 | judge_id | the judge's slug, a closed set of one | Which judge wrote the row |
| Y8.3 | date | DateStamp | The judged night whose eval rows are counted; it decides the file the row is filed under |
| Y8.4 | checked_at | Timestamp | When the unit computed the row |
| Y8.5 | source_id | str or null | The summary's source as item-health records it; null when no item-health row names one |
| Y8.6 | model_id | str | The production model series (QQ1) |
| Y8.7 | faithfulness_instrument | str | The stamp of the faithfulness score the line read (row #37), or scorer_version on a row that carries none (G1.7) |
| Y8.8 | metrics_version | str | The counterweights' stamp behind the number and extraction reasons (row #37), or the metrics- part of scorer_version on an older row |
| Y8.9 | summaries_scored | int | Summaries of this source and series scored that night, one per distinct summary as the judge's windows read them (row #4) |
| Y8.10 | under_faithfulness_line | int | Summaries whose faithfulness score is under the gate's faithfulness line (Y5.4) |
| Y8.11 | faithfulness_column, faithfulness_line | str, float | The score the line read - the whole-summary score until row #39, the lowest sentence after - and the line in force |
| Y8.12 | with_unsupported_number | int | Summaries with at least one unsupported number, the gate's other line |
| Y8.13 | extraction_flagged | int | Summaries flagged extraction_suspect |
| Y8.14 | withheld_by_gate | int or null | Summaries whose stamp reads withheld, a real withhold and never a record-only stamp; null on a night whose rows carry no stamp (rows #18 and #23) |
| Y8.15 | points_docked | int | Summaries with at least one failure among the reasons counted that night, one point each, with no weight by reason |

### Row #42 - Series boundaries on every recorded change

- **Scope:** every recorded change becomes a series boundary. A new model (model_id or model_sha256) restarts every member and a move in a member's own instrument stamp restarts that member, as before (P14). A prompt, quantization or runtime-build change, read for each eval row from its run's recorded inputs (RunRecord.inputs, joined by run_id; row #37 adds no column for them), restarts only the members its expected_shifts entry lists (RC33), or every member when it has none; each restarted member reads new_series until its windows refill and takes a new anchor (row #14), while every other member keeps comparing. The same reader names the changes behind every row (series_started_by) and inside its windows (inputs_changed).
- **Level:** 3 (decides how stored rows group into series; series_started_by and inputs_changed are row #3's fields, and expected_shifts is config, never a stored row).
- **Files touched:**
  - backend/idhazh/summary_fidelity_judge/recorded_changes.py (new: reads RunRecord.inputs from the run.json of each day the windows span, frontend/public/digest/<YYYY>/<MM>/<DD>/run.json, joins each eval row to its run by run_id, and lists every recorded change with its run, date and kind; re-derive the manifest reader at dispatch: git grep -n RunManifest backend/idhazh)
  - backend/idhazh/summary_fidelity_judge/series.py (new: each member's series start from the model, its own instrument stamp, the recorded changes and expected_shifts, and the change that started it)
  - backend/idhazh/summary_fidelity_judge/windows.py and backend/idhazh/summary_fidelity_judge/comparisons/trailing.py (a member's windows hold only days of its current series; a day that straddles a change splits by run; new_series while too young)
  - backend/idhazh/summary_fidelity_judge/comparisons/anchor.py (if row #14 has landed: the anchor starts at the member's series start, so a restart takes a new anchor)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (expected_shifts, RC33, empty; the refusals of Y6.7)
  - backend/idhazh/summary_fidelity_judge/tenant.py (series_started_by and inputs_changed filled from the same recorded changes)
  - backend/tests/summary_fidelity_judge/test_recorded_changes.py and backend/tests/summary_fidelity_judge/test_series.py (new)
  - backend/idhazh/contracts/fingerprint.py and backend/idhazh/contracts/run_manifest.py (docstrings only: the drift judge restarts its series on the record, and still no run, pool or published number turns on it)
  - docs/architecture/contracts/determinism.md ("It records and it gates nothing" gains the drift judge's series boundaries)
  - docs/architecture/publishing/summary-fidelity-judge.md (the boundaries, how a change declares its expected shifts, and the 14-night cost of a change that declares nothing)
  - docs/architecture/summarize/prompt.md, docs/reference/ci-model-runtime.md and docs/concepts/config/model-file.md (a change to the prompt, the runtime pin or a model file's quantisation writes its expected_shifts entry in the same commit)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity_judge/ and backend/tests/contracts/; CI - full suite. Observation, not a gate: row #8's replay over the stored record with the recorded changes since 2026-09-12 as boundaries, recorded in the pull request as the nights each member went without a judgement.
- **Oracle:** on a tmp_path eval ledger with two runs a day and their manifests, a prompt change whose entry lists faith_index restarts faith_index alone, which reads new_series naming the change, while numbers_unsupported keeps comparing and still crosses on a fault planted after the change; the same change with no entry restarts every member; a quantisation or runtime-build change follows its entry the same way; a model change restarts every member whatever the entries say; a day that straddles a change splits by run; a run whose manifest holds no inputs starts a series for every member; the loader refuses an entry for a model or scorer change and one that names an unknown member. Cannot settle: an entry written after its change was judged, which RC33 forbids and the rows of the nights before it keep visible; a change the record does not enumerate.

Table Y6 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| Y6.1 | Every recorded change - model, prompt, quantization, runtime build, scorer - is a series boundary, and nothing is compared across one | Owner, 2026-10-12 (QQ19 A1 B1; P20, its last clause reversed); research record section 7.4 (item 1) |
| Y6.2 | Model and scorer changes restart as before: a new model_id or model_sha256 restarts every member, and a move in a member's own instrument stamp restarts that member | Owner, 2026-10-11 (P14); owner, 2026-10-12 (QQ19) |
| Y6.3 | A prompt, quantization or runtime-build change restarts only the members its expected_shifts entry lists, each with a new anchor (row #14); every other member keeps comparing, so a side effect still alerts | Owner, 2026-10-12 (QQ19 B1; QQ18); RC33 |
| Y6.4 | A recorded change with no entry restarts every member; the cost the owner accepted is no judgement for 14 nights, the first night whose baseline, ending baseline_lag_days (8) before it, holds min_baseline_days (7) valid days of the new series | Owner, 2026-10-12 (QQ19); RC5; RC13; RD5 (a change about every 9 days) |
| Y6.5 | Prompt, quantization and runtime build are read from the run's recorded inputs - RunRecord.inputs on each day's run.json, bounded to the days the windows span - joined to each eval row by run_id; a prompt change is a move in any of the prose inputs, prompt_sha256, chat_template_sha256 and output_schema_sha256 | Owner, 2026-10-12 (QQ19); Table D (row #42); backend/idhazh/fingerprint.py (PROSE_INPUTS, the words handed to the model); CLAUDE.md Guardrail #12 |
| Y6.6 | A run with no recorded inputs, a manifest written before 2026-09-12, is never read as unchanged: the first recorded run after it starts a series for every member | Owner, 2026-10-12 (QQ19: nothing is compared across an unannounced change); backend/idhazh/contracts/fingerprint.py (an absent value is never a substituted one) |
| Y6.7 | An entry names a date, one change - prompt (any prose input), quantisation or runtime_build, the last two spelled as the record spells them - and the members it expects to move, and is written in the commit that makes the change, never afterwards; the loader refuses a model or scorer change, an unknown member and two entries for one date and change | RC33; owner, 2026-10-12 (QQ19); G1.3 (refusals by name) |
| Y6.8 | Each eval row belongs to the series of the run that made it, so a day that straddles a change splits by run, and each part is a day of its own series, kept only when it holds min_day_rows | Owner, 2026-10-11 (QQ6); owner, 2026-10-12 (QQ19) |
| Y6.9 | One reader serves the boundaries and the record: series_started_by names the change that started a row's series, and inputs_changed names every recorded input that moved inside its windows, those that start no series included (sampling, context and batch sizes, the truncation cap, the extractor and sanitizer versions) | Owner, 2026-10-11 (QQ10; QQ29); owner, 2026-10-12 (QQ19) |
| Y6.10 | The pages that say no window turns on the recorded inputs change with this row: the drift judge's series now do, and still no run, pool or published number turns on them | CLAUDE.md Guardrail #4; owner, 2026-10-12 (QQ19) |

Table Y9 - rejected alternatives (rows #36 to #39, #41 and #42)

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Y9.1 | Row #36: build the eval-row change on the estimate alone | The estimate rests on an assumed summary length and the r4 median, not a measurement, and the overlap adds its minutes to every work shard | None in code; a shard that may outrun its own clock unseen | Owner, 2026-10-11 (QQ15 C1); review record SP3 (I1) |
| Y9.2 | Row #37: a plan of its own for the faithfulness instrument, as P31 first proposed | The owner put it inside plan 65 as rows #36 to #39, ordered before the gate's faithfulness line | A second approval round, and the gate's faithfulness line waiting on another plan | Owner, 2026-10-11 (QQ15 A2; P31) |
| Y9.3 | Row #37: the sentence score, the name and date checks, the stamps and the scorer's rename as separate eval-row changes | Each change of instrument restarts the faithfulness series; one change restarts it once | Up to three restarts of about 14 nights each, and three read-side migrations | Owner, 2026-10-11 (QQ15 B1; P38); review record SP3 (one series restart, not three) |
| Y9.4 | Row #38: the old score retires on the new series' 15th day, as QQ15 was first asked | The per-sentence members are new declarations, which turn active only through QQ28's promotion, so the old members would retire before their replacements could judge | None | Owner, 2026-10-11 (QQ15, as corrected) |
| Y9.5 | Row #38: a replacement starts at weight 0 until tuning raises it, QQ28's rule for a new member | Tuning moves a weight by at most max_weight_step (1), so faithfulness would weigh less in the combined score for 16 to 20 weeks after its series starts | None | Owner, 2026-10-11 (QQ31 F1; P46) |
| Y9.6 | Row #39: withhold on today's whole-summary score at 0.50 | Scoring the whole summary against each window marks multi-window articles down - a 2-window article 0.22 and a 3-window article 0.40 below the same article read whole - so the line would withhold faithful summaries of long articles | None | Owner, 2026-10-11 (QQ12 B2; P31) |
| Y9.7 | Row #41: per-source failures as extra rows in drift-evals | drift-evals holds the judge's tests, keyed by member and comparison; a per-source count is another record for another reader | Rows keyed by source inside a ledger keyed by member, which every reader of drift-evals would have to tell apart | Owner, 2026-10-12 (QQ32 R1) |
| Y9.8 | Row #41: weights by reason, or a source score computed here | The feed-quality plan sets weights and decides; plan 65 measures and records | A second owner of a source's standing | Owner, 2026-10-12 (QQ32; QQ17 B1; Q52) |
| Y9.9 | Row #41: plan 65 acts on a failing source - rests it, lowers its trust or flags its extraction | Every action on a source belongs to the autotune-feed-quality plan and its judge | A broken source publishes until that plan acts | Owner, 2026-10-12 (QQ17; B13) |
| Y9.10 | Row #42: a prompt or runtime change only labels the crossings inside its window, P20's last clause | It compares across a change, where every recorded change is now a series boundary | Crossings that trace to a deliberate change, about every 9 days | Owner, 2026-10-12 (QQ19; P20, that clause reversed) |
| Y9.11 | Row #42: a person's mark resets one member's baseline later, as P35 proposed | A regular human step, against A7; a declared expected shift does the same with no person | A deliberate change reads as drift for up to 35 days until someone marks it | Owner, 2026-10-12 (QQ19 B1; P35); Table A, A7 |

## 3. Owner rulings

Table QQ - the open decisions, asked one at a time in this order (each with its trade-offs and what the research says, in the CLAUDE.md section 0c format; automation-first from QQ27 on, A7; a ruling is written into Table P and here before the next question is asked)

| # | Question | Decides | Depends on | Status | Ruling |
| --- | --- | --- | --- | --- | --- |
| QQ1 | Unit of judgment: what the judge compares night to night - each site, the whole digest per production model, or the digest plus a per-source pointer | P20; rows #2 and #4 to #14 | - | Ruled 2026-10-11 | A1: the whole digest, per production model series; article length and source only adjust the comparison and are never judged. The judge reads every scored summary and samples nothing itself (Q44) |
| QQ2 | What is judged: which metrics decide drift, which are only watched as behaviour, and which are only shown | P21; Table RA | QQ1 | Ruled 2026-10-11 | A1: faithfulness (the average and the shares under 0.50 and 0.80), unsupported numbers and dropped hedges are judged; loops and too-short summaries wait paused until their base rates are known; copying and summary length are watched as behaviour; coverage, coherence and the input mix are shown only; article length and source only adjust (Table RA) |
| QQ3 | Plan 36's fitted floors (a 5th-percentile floor per metric, refitted daily): replace them with this judge's nightly test, keep both, or keep the floors as the alarm | Rows #16, #17, #19 and #20; part of row #24 | QQ2 | Ruled 2026-10-11 | A1: this judge's nightly test replaces plan 36's fitted floors; rows #16, #17, #19 and #20 collapse, the floor lines leave row #24, and the gate (row #22) reads fixed lines only |
| QQ4 | Fluency as plan 36 designs it (the summariser grades its own fluency) against a sampled key-fact judge for completeness and conciseness, or both | Rows #21 and #25, the geval column of row #18; P32 (first part) | QQ2 | Ruled 2026-10-11 | A1 B1 C3. The digest run keeps the article text of the day's sampled summaries in a small ledger, deleted after a rolling window (31 days by QQ30), and the judge reads it the next night (a CLAUDE.md section 0a exception, approved). The summarizer's own model lists each article's key facts before it sees the summary, then marks which facts the summary holds (completeness) and which summary sentences carry one (conciseness); if the pilot shows it overlooking removed facts, the check moves to Gemma 4 E4B. 30 summaries a day, a config number. Plan 36's self-graded fluency is dropped (rows #21 and #25 collapse; row #18 loses geval). Rows #29 to #31 |
| QQ5 | The nightly test: the recency-weighted last 7 days against the days before, whole days re-dealt, values adjusted for article length and source | P22 | QQ1, QQ2 | Ruled 2026-10-11 | A1, on the owner's condition that it stays configurable: the recency-weighted last week against the baseline, whole days reshuffled, one test for every member. Every number is a setting in config/judges/summary-fidelity-judge.json (RC): recent_days, baseline_days, recency_lambda 0.15 (0 makes a flat week), min_day_rows 100, the reshuffle settings. Another test type, such as a chart that adds up small daily slips, can join later as a module a declaration selects (P13) |
| QQ6 | Baseline length: 28 days, 56 days with a gap, or 14 days | P22 (RC2) | QQ5 | Ruled 2026-10-11 | A2, the research's window, with the owner's rule that the code adapts to the days it has. The baseline is the 56 days that end 8 days before the judged night (days 63 to 8 back, research record section 6.3), so one day separates it from the 7-day recent window. Days with no run, a failed run or fewer than min_day_rows scored summaries are skipped, never filled in and never replaced by older days. The judge judges once the recent window holds at least min_recent_days valid days and the baseline at least min_baseline_days; before that, as in a short history or the first weeks after a model change, it stores too few days. Every row records how many valid days each window used. Settings: baseline_days 56 (14 to 91), baseline_lag_days 8 (at least recent_days), min_recent_days 4, min_baseline_days 7 |
| QQ7 | False-discovery rate: 0.05, 0.01 or 0.10 | P23 | QQ5 | Ruled 2026-10-11 | A1: false_discovery_rate 0.05 (F1.11, a setting from 0.001 to 0.2), with the approved fallback of C5 and P18: if the replay shows a typical night over the reading budget, a metric that crosses too often on reshuffled dates is fixed first, then the rate drops to 0.01 |
| QQ8 | The composite: two combined rows (quality worse; something changed) beside every metric's own row, one signed score, or no composite | P24 | QQ2, QQ5 | Ruled 2026-10-11 | A3: each metric keeps its own verdict (QQ2, QQ5), and the one combined score is the research's signed, correlation-adjusted score over the judged quality members, each oriented so that positive means worse; it is tested one-sided for worse and takes its p-value from the same reshuffled days, so an improvement in one judged metric offsets a harm in another inside it (the owner's choice). quality_worse and something_changed are not built; changes in copying and length reach a person as watch-level crossings of their own members. Reading levels: evaluator check; drift (the combined score or a judged member crossed on drift_consecutive_nights nights in a row); watch (any other crossing); quiet. Nothing acts |
| QQ9 | Weights and day-to-day correlation settings: start from reader harm, tune on injected faults, a person commits them | P25 | QQ8 | Ruled 2026-10-11 | A1 B1: weights start from reader harm (faithfulness 3, one per measure; unsupported numbers 3; dropped hedges 2), are tried on injected faults by the replay, which proposes the set with the best worst-case detection; weights are never negative and a new metric starts at 0. One rho per metric, proposed by the replay from quiet stretches; a new metric starts at 0. The owner then set the principle A7, so the step where a person commits both is asked again as QQ27 |
| QQ10 | The stored row: fields and key of the drift-evals ledger, a persisted shape (the judge's nightly rows; the other stored records are QQ30) | P26 | QQ1 to QQ9 | Ruled 2026-10-11 | A1: one row per metric, plus one for the combined score, per judged night and council run. Who: run_id, date, model_id and the metric's instrument (scorer) stamp. What: check_name, role (judged, watched, evaluator, shown), statistic and comparison. Windows: valid days used in each window, baseline_lag_days and recency_lambda. Values: recent and baseline values, raw and adjusted, and the effect. Test: p_value, q_value, reshuffles used, the rho applied, and on the combined row the version of the tuned weights in force. Outcome: crossed, not crossed, too few days, paused or new series. Context: the settings in force and the recorded inputs that changed inside the window. Key: run_id, date, check_name, comparison, model_id, instrument |
| QQ11 | Names: drift-evals against the owner's 2026-09-27 naming rule, the names of the records QQ30 adds, and the key-fact check's judge | P29 | QQ10, QQ30 | Ruled 2026-10-11 | A1 B1 C1. A1: drift-evals keeps its name, and row #3 adds a dated line under the owner's naming rule in docs/architecture/contracts/ledger-registry.md, so a later drift ledger takes a name that says what it holds. B1: key-fact-articles holds the sampled article text and the key-fact lists (row #29); key-fact-scores holds the key-fact check's numbers (row #30); drift-evals-tuning holds the tuning runs and metric moves (rows #32 and #33). C1: the key-fact check is the council judge summary-completeness-judge - config/judges/summary-completeness-judge.json, its entry in config/llm_council.json and its family folder, which holds key-fact-scores and key-fact-articles; drift-evals-tuning sits beside drift-evals in the family summary-fidelity-judge |
| QQ12 | Plan 36's publish gate: whether one summary is withheld from the day and on which lines, what happens to a withheld summary, the stub pre-filter, and how the gate goes live (record-only first, then switched on automatically or by the owner) | Rows #18, #22 and #23; B1 | QQ3 | Ruled 2026-10-11 | A1 B2 C1 D1. A1: the gate stamps every summary from the day it lands, record-only. It starts withholding by itself once, over the last gate_trial_days (28) days, an independent check agrees with at least gate_min_agreement (0.7) of its would-be withholds - the second checker if QQ16 adds one, otherwise summary-completeness-judge's model checking up to gate_checks_per_day (10) of them a day once it catches planted unfaithful summaries (QQ28's test, row #35) - and the would-be withheld share stayed under withhold_share_ceiling (0.25) every night. It re-checks both guards nightly and returns to record-only when one fails; a night over the ceiling publishes record-only, because a broken scorer is the likelier cause, and the quality-alarm issue says so. withhold_failing_summaries (true or false, no default) stops withholding at once while the stamps continue; every switch is recorded. B2: an unsupported number can withhold from the start; faithfulness withholds only on the sentence-level score once QQ15's instrument exists and until then only stamps. C1: a withheld summary is absent from the day, the story's next-best duplicate takes its place and item-health records why (the owner's ruling of 2026-09-19); the stamps also count the stories that would be lost entirely. D1: no stub pre-filter; the 60-word extraction floor stays. The answer is the owner's Level 5 sign-off for the first change to a published day |
| QQ13 | Plan 36's rejects ledger and corpus fence: keep the text of withheld summaries in key-fact-articles or in a ledger of its own, what an entry carries, and whether the training corpus skips the summaries the gate fails | Row #27 | QQ12 | Ruled 2026-10-11 | A1 B1 C1. A1: every summary the gate withholds is kept in key-fact-articles beside the sampled articles, under the same window (sampled_article_keep_days, 31) and the same history purge by the gardener's history job, and each entry says why it was kept (sampled, checked for the gate, withheld); there is no separate rejects ledger, so CLAUDE.md section 0a lists two article-text exceptions (corpus/ and key-fact-articles) and plan 36's state/rejects/ carve-out of 2026-09-19 is not used. B1: the training-corpus harvest skips any summary the gate marks on a line that may withhold - an unsupported number now, the sentence-level faithfulness once it exists - whether or not the gate is live; it reads the stamp, never a raw score, so keeps_its_counterweights stays faithfulness-free and the whole-summary score never fences. C1: an entry carries the summary, the article text the model read, the failed line and its scores, the model and prompt identity and the item's identity; no rendered prompt, which the corpus harvest's reconstruction rebuilds from the article text and that day's prompt code |
| QQ14 | Where the console shows this plan's results: the drift judge's crossings and the publish gate's panel on the Summaries page (/console/model/), the gate's panel on the Judgement page, or no new panel; and what the gate's panel shows | Rows #12 and #24; P5 | QQ3, QQ12 | Ruled 2026-10-11 | A1 B1. A1: both on the Summaries page (/console/model/): the drift judge's crossings (P5) and the publish gate's panel beside them; the Judgement page stays the same-story judge's page, and plan 36's per-metric band charts are not drawn, because their fitted floors are gone (QQ3). B1: the gate's panel shows its state (record-only or live, since when and why), its two guards against their lines (the independent check's agreement against gate_min_agreement, the night's share against withhold_share_ceiling), the daily share withheld or that would have been, by reason, and the stories lost entirely; it has no alarm of its own, because the drift judge's withheld-share member and the quality-alarm issue carry alarms; it never shows the text of a withheld summary |
| QQ15 | The faithfulness instrument: sentence-level scoring, name and date checks, per-column stamps and a replaceable scorer - inside plan 65 or a plan of its own, what the one change includes, and how it switches over; QQ12 (B2) lets faithfulness withhold only on its sentence-level score | P31, P38; row #18; the gate's faithfulness line | QQ2 | Ruled 2026-10-11 | A2 B1 C1. A2: inside plan 65, as rows #36 to #39, ordered before the gate's faithfulness line. B1: one eval-row change carries per-sentence faithfulness (each sentence against its best window: the mean, the lowest sentence, sentences under 0.50 and 0.80 and the winning window), name and date checks, a version stamp per scored column (for faithfulness the scorer, its revision, weights, window geometry and installed library, which also closes B10's gap; METRICS_VERSION for the counterweights; coherence's encoder) and a replaceable scorer named in config with a column that does not name HHEM, so the faithfulness series restarts once. C1: after a one-day cost measurement, the new score runs beside the old one, and the old faithfulness members retire by themselves once their per-sentence replacements turn active. Corrected on 2026-10-11: the question said the old score retires on the new series' 15th day, but the per-sentence members are new declarations, and under QQ28 a new member turns active only after promotion_min_days (28) usable days and its planted-fault test, checked at each scheduled replay, so the overlap lasts 4 to 8 weeks (about 48 to 53 scorer-minutes a day meanwhile); the replacements' starting weight is QQ31. The gate's faithfulness line starts at 0.50 on the lowest-scoring sentence, and its own guards decide whether it acts. The answer is the owner's Level 5 sign-off for the eval-row change |
| QQ16 | A second faithfulness checker: at night on the kept articles, in the daily run on every summary, or not now; and which checker. QQ12 (A1) makes it the gate's independent check when it exists | P32 (second part) | QQ15 | Ruled 2026-10-11 | A1 B1 C1, with the owner's limits. A1: the check runs at night on the kept articles, on faithfulness_checks_per_night (8, the most a run's shards take; the gate's would-be withholds first, then sampled ones) within faithfulness_check_budget_minutes (40), both raised once everything works; it supersedes gate_checks_per_day (QQ12), and summary-completeness-judge keeps key facts only. It classifies each summary sentence as supported by the article or not and never writes a summary. B1: IBM Granite Guardian 3.3 8B, the official GGUF build (Q4_K_M, 4.94 GB, Apache 2.0), served by the pinned llama.cpp runtime with its groundedness criterion in no-think mode; the model and its prompt template are named in config, so a later model (Granite Guardian 4.1, Gemma 4 E4B or another GGUF model) is a config change plus the planted-fault test. C1: the judge is summary-grounding-judge (config/judges/summary-grounding-judge.json, runs_model true, an entry in config/llm_council.json), and its ledger is grounding-verdicts in its own family |
| QQ17 | Per-source extraction health: who notices when one source's extraction breaks - a plan of its own in the source-health system, a row in plan 65, or nothing new - and what happens automatically while it is broken | P34; the gap row #1 leaves | QQ1 | Ruled 2026-10-12 | The owner, 2026-10-12: per-source extraction health belongs to the autotune-feed-quality plan and its judge, which plan 65 leaves alone (B13), so neither A1 nor A2 is built here. B1, with separation of duties: plan 65 measures and records - each night, per source and model series, the summary failures it already sees and the points docked (row #41, named in QQ32) - and never changes a source's reliability, trust, rank, rest or config; the feed-quality plan reads the record and decides. Rows the extractor flags leave the quality members, and a source the feed-quality plan flags will leave them too once that plan's record exists. The existing reliability factor (collect.reliability_floor and reliability_window_days) measures only whether a feed's reads return entries, and the source-health module refuses one combined credibility score, so combining it with this record is the feed-quality plan's decision |
| QQ18 | The long-baseline comparison: a frozen anchor per series (each series' first weeks) compared with the recent week, the one-year comparison deferred to Table B until a year of one series exists, or the one-year comparison built now to start by itself | P28 | QQ5 | Ruled 2026-10-12 | A1: a frozen anchor per series replaces the one-year comparison. Each production series' first anchor_days (56) valid days, stored as score quantiles, become its anchor; every anchor_look_every_days (7) the judge compares the recent week with the anchor, so a slow decline that drags the moving baseline along still crosses. Built now, it starts by itself from a series' ninth week, lands paused and joins the alarm through QQ28's promotion (about weeks 13 to 17). The one-year comparison moves to Table B (B14) |
| QQ19 | Accepting a known change: whether a prompt or runtime change starts a new series or only labels the crossings inside its window (P20's last clause), and how an intended shift stops reading as drift without a person (P35) | P35; P20 (last clause) | QQ5 | Ruled 2026-10-12 | A1 B1, combined: every recorded change - model, prompt, quantization, runtime build, scorer - is a series boundary, as the research advises (research record 7.4). Model and scorer changes restart as before (P14). A prompt, quantization or runtime change that declares in the judge's config (expected_shifts: the date, the change, the metrics it expects to move) restarts only those metrics, each with a new anchor (row #14), and every other metric keeps comparing, so a side effect still alerts; a recorded change that declares nothing restarts every metric, so nothing is ever compared across an unannounced change. The cost the owner accepted: an undeclared change leaves the judge without a judgement for 14 nights, and the pipeline changed about every 9 days, so declaring a change matters. P20's labelling clause is not taken; every crossing still names the recorded changes inside its window (QQ29) |
| QQ20 | Drop the statistics library extra (scipy) that the redesign no longer needs | P27 | QQ5 | Ruled 2026-10-12 | A1: P7 is withdrawn. The council's nightly jobs install no statistics extra; the judge's reshuffles, false-discovery step and combined score use numpy only, which row #3 lists directly in the base dependencies instead of relying on onnxruntime to bring it. scipy stays in the dev extra for tests; a later check that needs an exact distribution brings its own extra with it |
| QQ21 | Drop the switch row's peak-memory observation for the drift judge, which runs no model; the model judges keep their own memory check (row #40) | P30 | - | Ruled 2026-10-12 | A1: row #9 drops the drift judge's peak-memory reading and keeps the first-night run-time reading; the model judges keep their own memory check when their models are pinned (row #40) |
| QQ22 | Correct the evaluation persona's line that calls a model judge a project non-goal (.github/agents/andre.agent.md, item 10), which contradicts CLAUDE.md section 1a: replace it with the checks a model judge must pass, delete it, or leave it | P36 | - | Ruled 2026-10-12 | A1, done in its own commit (87929458, 2026-10-12): item 10 of .github/agents/andre.agent.md now reads that a model judge is a measurement only once it has been checked - it catches planted faults before its verdicts count, its model and prompt versions are recorded with every verdict, its agreement with an independent checker is charted, and a judge from the writer's model family is named as such - and asks the reviewer to say so when a judge lacks those checks |
| QQ23 | Where the owner's requests are tracked once plan 65 closes: Table Q moved to a standing file read first in every session, kept in the plan and carried to the next plan, or one GitHub issue per request | P37 | - | Ruled 2026-10-12 | The owner: the docs distillation is the memory. Neither a standing request file nor GitHub issues: Table Q stays plan 65's work ledger; each request's durable outcome lands on the page that owns it in the same commit (Guardrail #4), anything left is distilled per docs/how-to/distill-a-plan.md before the plan is deleted, open items go where that guide routes them, and git history keeps the record of what was asked |
| QQ24 | Plan 36's coherence-placement row: collapse it, because coherence is scored every day in the daily work step that composes the eval row (not in assemble, as plan 36 assumed) and the console's Hardware page already shows memory, or keep it as a memory check of the work step | Row #26 | QQ2 | Ruled 2026-10-12 | A1: row #26 collapses. The code scores coherence in the daily work step, because that step composes the eval row and scoring it elsewhere would leave the column empty; it has scored every day since 2026-09-24, nothing judges it (QQ2), and the console's Hardware page already shows how close the work step runs to its memory limits. Plan 36's H5 and H6 (coherence in assemble) no longer describe the code |
| QQ25 | Plan 36's retro row of guards (a prompt ending in a space shifts a one-token verdict; thinking left on; instructions planted in article text): keep it for the judges that exist now - the content-similarity judge, summary-completeness-judge and summary-grounding-judge - fold the guards into each judge's own row, or drop it with the fluency judge it was written for | Row #28 | QQ4 (ruled) | Ruled 2026-10-12 | A1: row #28 stays as one shared set of guards for the content-similarity judge, summary-completeness-judge and summary-grounding-judge: no trailing space where a judge reads a one-token answer, with answer tokens built in position and first-token probabilities logged; thinking off for every judge call, pinned by a canary that rejects a recorded thinking-on completion; and the planted-instruction canary on recorded completions for the two judges that read article text, which the project treats as untrusted (Guardrail #11) |
| QQ26 | Execution approval: carry plan 36's approval of 2026-09-19 to its surviving rows, hold every row for one approval of plan 65 once its rows are rewritten to the rulings, or approve plan 65 now on the strength of the rulings | Every row; Section 0 (AUTHOR-AND-STOP) | QQ1 to QQ25 | Ruled 2026-10-12 | A1: one approval for the whole plan. Rows #2 to #14 are rewritten to the rulings, and every pending row gets its detail section written to the rulings; the owner then approves plan 65 once, and it runs by itself per Section 0 (four rows at a time, merging on green gates). Plan 36's execution approval of 2026-09-19 does not carry to its rows |
| QQ27 | Automate the tuning commit: the replay's weights and rho applied automatically within guards (inside their ranges, a capped step, the false-alarm rate kept, every proposal recorded), instead of a person committing them | QQ9; P17, P25 | QQ9 | Ruled 2026-10-11 | A1, with an off switch, the owner's 'andon cord': the replay runs every tuning_every_days days and applies new weights and rho only when every guard passes - each value inside its declared range, each change within max_weight_step or max_rho_step, the false-alarm rate on reshuffled history on target, worst-case detection on the injected faults no worse than now - and otherwise keeps the current values. Every proposal, applied or held, is stored with its reason; the loop never writes the settings file, which keeps the starting values and bounds, and a value pinned in config is left alone. auto_apply_tuning (true or false, no default; named for what it does, CLAUDE.md section 0b) stops automatic application at once: the replay still runs and records its proposals as held, and the last applied values stay. Row #32 |
| QQ28 | Promote a paused metric to active automatically when its replay passes (it catches its injected fault and keeps the false-alarm rate), instead of an owner ruling | P13 (G1.5); row #31 | QQ27 | Ruled 2026-10-11 | A1: automatic in both directions, with guards and an off switch. At each scheduled replay a paused metric turns active only when it has at least promotion_min_days (28) usable days, keeps the false-alarm rate on reshuffled history on target, catches its own planted fault at least promotion_min_detection (0.8) of the time within a week, and keeps a typical night within crossings_budget; it joins the combined score at weight 0 until the next tuning gives it one (QQ27). An active metric that alarms too often on unchanged history goes back to paused automatically. Every move is stored with its reason. auto_promote_metrics (true or false, no default) stops both moves at once. Switching the key-fact check's model to Gemma 4 E4B stays an owner decision, because it changes the model the council serves. Row #33 |
| QQ29 | What follows a drift reading when no person reads it regularly: which automatic responses, if any, follow a crossing (reopens B2 and the no-automatic-actions part of P15) | B2, P15; rows #12 and #13 | QQ27 | Ruled 2026-10-11 | A1: investigate automatically and notify only when quality gets worse; nothing published is touched. Every alarm stores its diagnosis: which metrics moved and by how much, raw and adjusted, and which recorded inputs changed inside its window. While a quality alarm lasts (the combined score or a judged metric crossing on drift_consecutive_nights nights), the key-fact check multiplies its daily sample by drift_sample_multiplier (2: 30 to 60) and returns when the alarm clears. A quality alarm opens one GitHub issue the judge writes, updates nightly and closes when the alarm clears; it holds only metric names, numbers and recorded input names, never article text (Guardrail #11). Changes only in copying or length are recorded, never raised. auto_respond_to_drift (true or false, no default) stops all of it. B3 is narrowed to allow this one issue; B2 stands. Row #34 |
| QQ30 | The other stored records plan 65 adds: the sampled article text (row #29), the key-fact scores (row #30), the record of tuning and promotion moves (rows #32 and #33) and the drift diagnoses and issue state (row #34) - each a persisted shape | Rows #29, #30, #32 to #34 | QQ10 | Ruled 2026-10-11 | A1 B1 C1, with the article window a rolling window in config, default 31 days. A1: the sampled article text is a record of its own outside the ledger door's packing, one file per sampled summary per day; files older than sampled_article_keep_days (31) are removed; old bytes leave git history through the gardener's existing history job, beside the training corpus (within about 60 to 90 days); never published; CLAUDE.md section 0a lists it as the second article-text exception. B1: the key-fact scores are numbers only - completeness, conciseness, the number of key facts, model and prompt version, whether the answer parsed and the sample group; the key-fact lists live in the article record and leave with it. C1: one ledger through the door holds a row per tuning run (proposed and applied values, each guard's result, why a value was held, a version id the combined-score rows reference) and a row per metric move (from, to, the test values, the reason). Drift diagnoses stay in the drift-evals rows, and the judge finds its GitHub issue by a fixed label |
| QQ31 | Follow-up to QQ15: the starting weight of a per-sentence member that replaces a faithfulness member - its predecessor's starting weight, or QQ28's weight 0 until tuning raises it | QQ28 (as it applies to a replacement); row #38 | QQ9, QQ15, QQ28 | Ruled 2026-10-11 | F1: a measure that replaces another for the same reader harm takes over its predecessor's starting weight when it turns active, and the predecessor retires that night; tuning adjusts the weight afterwards within its guards (QQ27) |
| QQ32 | Follow-up to QQ17: the per-source record for the feed-quality plan - a ledger of its own (its name and fields) or extra rows in drift-evals | B13; row #41 | QQ11, QQ17 | Ruled 2026-10-12 | R1: a ledger of its own, summary-failures-by-source, in the family summary-fidelity-judge: one row per night, source and model series - the summaries scored, the failures by reason (under the faithfulness line, an unsupported number, an extraction flag, withheld by the gate) and the points docked, one per summary with at least one failure. No weights by reason: the feed-quality plan sets them. The grounding judge's verdicts stay in grounding-verdicts, which also names the source |

Table QA - what the 2026-10-12 rewrite names that no ruling had set, covered by the single approval (QQ26)

| # | What the rewrite names | Where it is decided | Why it was needed |
| --- | --- | --- | --- |
| QA1 | The stored shapes the rulings asked for, spelled out: the gate stamp's values (published, would_be_withheld, withheld; unsupported_number, lowest_sentence_faithfulness), the run record's count of stories lost entirely, the gate's switch record on the run plan, the fields of key-fact-articles, key-fact-scores, drift-evals-tuning and grounding-verdicts, the eval-row fields, summary-failures-by-source, and DriftEval's tuning_version and keyfact_sample_multiplier | Rows #18, #22 and #23 (O1, O2, O3); Tables X9, Y7 and Y8; H3.27 and H3.30 | A persisted shape is Level 5 and needs the owner's approval of its exact fields |
| QA2 | A withheld summary is a settled failure of the day, so a later run of the same day does not summarize it again | Row #23 (O3.12) | A same-day retry would be the re-summarize option the owner declined (QQ12, C1 over C2) |
| QA3 | The gate's agreement guard needs at least gate_min_checks (30) independent checks in its window | Row #23 (O3.13); RC34 | Without a floor, a handful of checks could switch a line on |
| QA4 | The whole-summary faithfulness score keeps running, because the published display band reads it; the scorer's extra minutes stay while it does. Moving the band to the per-sentence score is a reader-facing change no ruling makes | Row #37 (Y2.3, Y7.1) | QQ15 retires the old score as a judged metric, not as the band's input |
| QA5 | What starts a series: the model, the prompt (the prompt text, chat template and output schema), the quantization, the runtime build and the scorer. Sampling, context size, the truncation cap and the extractor versions are recorded and named on each row, but start no series | Row #42 (Y6.5, Y6.9) | QQ19 named the kinds of change, not the recorded fields behind each |
| QA6 | How QQ19's A1 and B1 combine: every recorded change is a series boundary; a change that declares its expected shifts restarts only those members; an undeclared change restarts every member, with the 14-night blind spot the owner accepted | Row #42 (Y6.1 to Y6.4) | The two answers were given together |
| QA7 | The council serves a judge's own model: ModelsConfig gains a checker slot, the judge declaration gains served_model, and the checker's weights are fetched each night and never saved to the shared cache | Row #40 (X8.4, X8.6); RC30 | The council serves one model today, and both models together pass the 10 GB cache |
| QA8 | The anchor's daily values are read back from the eval ledger, which keeps scored rows for 36 months, instead of being stored as score quantiles | Row #14 (V1.2) | Nothing new needs storing, and the anchor is computed exactly as the nightly comparison is |
| QA9 | A member may declare its own day minimum (the key-fact members 20, under the 30 sampled a day), a member may be pinned against tuning (tuning_pinned), and a replacement names the member it replaces (replaces) | X3.6, X4.7, Y3.8; F1.13 | The 100-row day minimum would keep the key-fact members from ever being tested; QQ27 allowed pinned values without naming how |
| QA10 | The pilot's and the checker's planted tests: 5 planted omissions a night removing 1 sentence each; 2 of the checker's 8 nightly checks are planted unfaithful variants, and its verdicts count only while it catches at least 0.8 of a week's | X3.7, X7.7; RC35 to RC38 | The rulings asked for planted tests without setting their sizes |
| QA11 | The faithfulness members already declared keep scorer_version as their instrument through row #37, so they keep judging until they retire, with no 14-night gap | Row #37 (Y2.10) | Moving them to the new stamp would restart members that are about to retire |
| QA12 | The name and date checks are declared as two paused members, which QQ28's promotion can bring in once they prove themselves | Row #38 (Y3.9); RA19, RA20 | QQ15 stores the checks; without members they could never join the alarm |
| QA13 | Granite Guardian is weaker on news than on average (0.669 balanced accuracy on AggreFact-CNN against 0.761), and the planted test bounds it only for faults like the planted ones | Row #35 (Cannot settle) | Named so the approval is made knowing it |

Table P - owner rulings: P1 to P19 ruled on 2026-10-11; P20 to P38 asked one at a time through Table QQ, each marked when ruled; P39 to P48 on 2026-10-11 and 2026-10-12

| # | Question | Ruling | Evidence | Rows |
| --- | --- | --- | --- | --- |
| P1 | Sign off the judge's ledger: family summary-fidelity-judge, ledger drift-evals, its path (H4.1), the row shape (H1 to H3) with the reviewers' changes to it (copied_phrase_share; threshold_crossed and threshold_not_crossed; check_name; baseline_value and recent_value; the effect definition; q_value per (run_id, date); the settings in force on every row), the key with the council run and the reader's rule (H4.5), and one (run_id, date) pair as one false-discovery family (M1.2) | Approved; the ledger name was changed to drift-evals by the owner on 2026-10-11, who disapproved site-drift-evals | ledger-registry.md lists what a new ledger owes and the rule a judge ledger follows; row #3 makes every edit in one change. The changes fix a field name the console's query engine reserves, a medians field that also held shares and rates, an effect that divided by zero and ranked small sites first, and outcome names that read as "nothing moved" (Fowler and Andre, 2026-10-11) | 3 and every later row |
| P2 | Unusually-short check: the exact beta-binomial tail instead of reshuffling, counting recent articles with strictly fewer words than the cut, with page types combined by adding each type's exact tail; a type with no baseline article has no cut and its recent articles are left out | Approved | When the cut is the j-th shortest of N_b baseline articles, the count below it follows BetaBinomial(N_recent, j, N_b - j + 1) with no change; this is the exact form of the reshuffling already approved (checked against every reshuffle of a small case, to 2e-16). With no change it fires on 0.17 to 0.44 percent at 0.5 percent and 2.45 to 4.83 percent at 5 percent (exact, baselines 20 to 102, recent 21 and 40); counting ties as short would fire 0.60 to 2.44 percent at 0.5 percent | 6 |
| P3 | Article-count check: raise a daily variance under the daily mean to the mean, and add the baseline's own noise to the variance (x (1 + recent_days / baseline_days)) | Approved | The negative binomial is undefined when the daily variance is under the mean, which happened in 54 percent of Poisson samples. The baseline rate is itself estimated: with the term, false rates were 0.0055 to 0.21 percent at 0.135 percent nominal (200,000 repeats; 1.5, 4 and 10 a day; Poisson, spread twice the mean, and quiet weekends). Over-dispersed sites still fire up to 3 times nominal at 0.0001, so row #8's replay reports article_count on its own | 5 |
| P4 | Reshuffling: stop once 10 reshuffles give a distance at least as large as the observed one (a tie counts); cap at the larger of 100,000 and 10 x (tested checks in the run) / false_discovery_rate - 1, counted before any reshuffle (its seed clause was withdrawn on 2026-10-11 by the owner's ruling that determinism is not an expectation); every one of these numbers in the settings file | Approved | The smallest p-value 9,999 reshuffles can give is 0.0001, which equals the first threshold at 500 checks (0.05 / 500), so from 500 checks a lone crossing becomes impossible. With early stopping an unchanged check used about 101 reshuffles instead of 9,999, and the p-values stayed valid over 1,000,000 checks. Not counting ties fired 5.8 percent at 5 percent nominal on tie-heavy scores; counting them fired 4.0 percent | 7, 8 |
| P5 | Which console page carries the panel (Model or Judgement), and whether the drift-evals compact files are published on the site | Approved: Model page; publish; QQ14 (2026-10-11) puts the publish gate's panel beside it | The Model page already reads the score and item-health ledgers and lists the sources the checker doubts; the Judgement page reads the similarity judge's merge line, which no check here touches; the Data explorer reads only ledgers in ledger.published | 12 |
| P6 | Where the judge's numbers live: config/judges/summary-fidelity-judge.json, read only by the judge | Approved | Every number bounded in one file an autotune loop can move. A block in config/idhazh.json would put a fourth judge contract in the council's import closure, because the council's registry imports AppConfig, and llm-council.md says that list cannot grow. The house already keeps one file per gardener task (config/gardener/), per console page (config/console/) and per model (config/models/) | 2 and every later row |
| P7 | scipy: an optional extra named for what it carries (statistics), installed by the council's planning, judging and collecting jobs | Approved 2026-10-11; withdrawn 2026-10-12 through QQ20 (P27) | The planning job imports every registered tenant module to resolve its slug, and the collecting job runs settle; both install only pip install -e . today, so a scipy import reached from the tenant module would fail every judge's night. CI installs the dev extra, so the tests would stay green. R11 named the drift job, which row #1 deletes | 5, 9 |
| P8 | Build the judge in the council from the first row, with one unit a night computing and settle filing (H4.7), and no stage in drift.yml that later moves | Approved | Nothing is built yet, so there is nothing to migrate; CLAUDE.md section 14 asks for each increment in its intended code path; the council already gives a nightly schedule, one commit path and a writer identity. A shard_count of 0 would break the council's own record, so the judge pays one runner job a night (with the council plan's row 'Judges carry a status and a model need', no model server: runs_model false) | 1, 3 and every later row |
| P9 | Drop urgent and urgent_p_value, which R9 kept | Approved | Their only reader, the issue title, went with the issues; a p-value says how unlikely a drop is by chance, not how much it matters, so "urgent" claims a priority nothing measured (CLAUDE.md section 0b); the stored q_value and effect already rank a crossing | 3, 8 |
| P10 | Repair dates: this judge names none in its first version (B8), and a council plan of its own fans out each tenant's own repair dates before a third judge arrives | Approved; superseded on 2026-10-11 by the council plan's P2, which builds each judge's own repair dates now (B8) | A council date runs every tenant, so a date only this judge named would make the content-similarity judge re-judge a night it already counted, at model cost. The cost of naming none: a night only this judge missed stays missing, and the next window shares six of its seven days (Fowler, 2026-10-11) | 3 |
| P11 | The reviewers' fixes to the checks: distances and the furniture share within page type (J1.3, K1.4); a pair with 1 to 19 baseline articles compared with earlier pairs (L1.3); the scorer reference check outside the false-discovery step (withdrawn with row #10, D3); readers count stretches (H4.9); the replay reshuffles each article's label once per site | Approved | With full articles cut by a quarter and the mix moving toward them, the pooled distance flagged 0 percent and the per-type distance 61 percent; pooled Fisher fired 9.6 percent at 5 percent nominal when the mix moved with no change; a pair with 1 to 19 baseline articles fell into the gap R4 closed; overlapping windows do not raise the false rate per night, they group crossings into stretches (Andre, 2026-10-11) | 6, 7, 8 |
| P12 | Two optional refinements: leave out of the step a check whose smallest reachable p-value is above false_discovery_rate; and count articles item-health rejected as too short as below the cut | Deferred to row #8's replay | Neither was measured here; the second needs item-health to record a too-short rejection per address, which is not checked | 6, 8 |
| P13 | Separate what the judge measures from how it tests: the settings file declares each measure (metrics, F1.13; H1), five kind modules and four comparison modules test them, check_name stores a declared name with test_kind, value_unit, comparison and check_definition beside it, a declaration never changes meaning under one name, and a new one lands paused until row #8's replay has run it (G1.1 to G1.5, H2.6, H3.20 to H3.23); this amends P1's row shape and key | Approved; its step where an owner ruling makes a paused declaration active was replaced on 2026-10-11 by QQ28's automatic promotion (auto_promote_metrics) | A sixth measure of an existing kind becomes one config entry (Level 3) instead of a stored-shape change (Level 5) and a console edit; a new kind of test stays a module and a review; the gardener separates declarations from kind modules the same way (knobs_gardener.py); Fowler and Andre debated it to one design (2026-10-11) | 3, 4 and every later row |
| P14 | A replaced model or scorer starts a new series, and no row compares two scorers inside the step (G1.6; changed_part, H3.24); until the eval row carries a narrower stamp (B11), copied_phrase_share, faithfulness and page_furniture group on scorer_version (G1.7), which brings page_furniture back to the old review's split | Approved | "Slicing costs a long article 0.40 of its score" (docs/concepts/evaluation.md), so a scorer move changes the instrument, not the pipeline; extraction_suspect is a counterweight METRICS_VERSION names, and METRICS_VERSION "is folded into scorer_version". Cost: each scorer_version move keeps those three measures out of the step for up to 14 days per site, band-threshold moves included; the alternative is a narrower stamp on the eval row first (Level 5, B11) | 4, 6, 7 |
| P15 | The composite score: adopt the calibrated combined_measures check (row #13) instead of the pasted composite; reject its fixed bands, its veto and its automatic actions (M2.3, M2.4); keep every action out, with a staged way back in that a ledger of a person's marks must earn first (B2) | Approved; confirmed 2026-10-11 by QQ8 (A3) in the research's correlation-adjusted form, with each metric keeping its own verdict | Simulated at this pipeline's sizes (Andre, 2026-10-11): the pasted composite went red on 19 percent of unchanged nights at a site with half an article a day, stayed green for a 79 percent length cut (0.25 x 0.79 = 0.198, under the 0.20 line) and for a faithfulness fall from 0.85 to 0.40, and scored 0.18 on the #1270 mix change alone; three slips that each crossed alone 11 to 15 percent of the time crossed together 43 percent of the time in combined_measures; a judge that steers what it measures adopts its own actions as its baseline | 8, 12, 13 |
| P16 | In place of D3's dropped reference rows: an all-sites comparison (row #13) and a long-baseline comparison for article_length (row #14, useful from about 2027-09) | Approved | Neither keeps a fixed article set, so both survive housekeeping: the eval ledger keeps its measurements for 36 months after their articles go. In simulation, the whole-day all-sites check caught a shared step too small for any one site (0.02) 82 to 97 percent of the time, where a single site caught it 6 to 10 percent; the 7-against-28 window has no power against a slow decline, and 52-week blocks caught a 40 percent yearly decline every time | 13, 14 |
| P17 | Combine weights: scored only on the replay's injected slips and reshuffled dates, never on live crossings, and fixed before any night they judge; the replay prints the best weights and a person commits them; an autotune loop never writes the settings file, and an automatic loop would file damped, clamped rows in a ledger of its own, at Level 5, not built here (F2.2, F2.6) | Approved; its person-commits step was replaced on 2026-10-11 by QQ27's guarded automatic application, with the auto_apply_tuning off switch | Weights chosen this way move detection power, never the false-crossing rate, because the p-value comes from the same re-deals whatever the weights; weights fitted on live crossings would let the alarm choose what it alarms on | 8, 13 |
| P18 | The reading budget counts new stretches: a typical night is the mean number of new stretches per judged date after the first seven; the count is split by check, and a check that crosses on reshuffled dates more often than false_discovery_rate is fixed first; false_discovery_rate 0.01 stays the second lever (M1.5). C5 would read: "No stop: the row splits the count by check, fixes a check that crosses too often on reshuffled dates, then sets false_discovery_rate to 0.01 and replays again before the switch; only a typical night still over the budget is reported, as a finding with options, never as a veto" | Approved | One real change stays in the recent window seven nights, so a count of crossings per night counts it seven times; in simulation, lowering the rate first removed 3.4 crossings a night, 2.7 of them real (Andre, 2026-10-11) | 8 |
| P19 | Outside this plan: correct the evaluation persona's file, .github/agents/andre.agent.md, which says this pipeline runs "pinned and deterministic so a re-run is a re-run" | Approved, as one small commit of its own | The owner ruled that determinism is not an expectation, and determinism.md says "Determinism is not a property a summarizer needs"; a persona that expects a repeat would review every later plan against it | none |
| P20 | Unit of judgment: the whole digest, per production model series with per-column instrument keys (P14); a prompt or runtime change labels the crossings inside its window rather than starting a series; sites, article count, unusually short, page furniture and article length are no longer judged, and article length and source become covariates | Approved 2026-10-11 through QQ1 (A1), except its clause on prompt and runtime changes, which QQ19 asks; its clause on prompt and runtime changes was reversed on 2026-10-12 (QQ19): such a change starts a fresh history for the metrics it declares, or for every metric when it declares none | Per-site cells are too small to test, and the one summariser-side change on record moved inside sources: the 99 sources present in both weeks moved -0.101 against -0.103 overall (review record, Andre 1.1); the research treats length, source and page type as covariates (research record 7.3); splitting a series on every input would blind the judge 13 nights after each change, about every 9 days | 3, 4, 7, 15, 8, 13, 12 |
| P21 | The judged set of Table RA: faithfulness (an index and two shares), unsupported numbers and dropped hedges judged; copying and summary length watched as behaviour; coverage, coherence and the input mix as diagnostics; loops and too-short summaries paused until their base rates are known. Amends P13: each declaration gains role, statistic, line, adjust_by and rho, and the kinds become statistics tested by one module | Approved 2026-10-11 through QQ2 (A1) for the judged set and the four roles; the declaration fields it adds for the test (rho, one test module) are decided with QQ5 and QQ9 | LLM-era frameworks judge faithfulness, completeness and conciseness; fluency is near ceiling; adjacent-sentence cosine and top-20-word coverage are unvalidated (research record 1.2 and 2.5); no column measures completeness or conciseness today (P32) | 4, 7, 15 |
| P22 | The test: a recency-weighted 7-day window (recency_lambda 0.15) against the 28 days before it, whole days re-dealt with one deal for every member, widened for each member's day-to-day correlation (rho, proposed by the replay and committed by a person), on values adjusted for length band and source with the raw value stored beside; days under 100 rows left out | Approved 2026-10-11 through QQ5 (A1) for the test, with every number in config as the owner required; the baseline length is QQ6 and rho is QQ9; the baseline is the research's window, 56 days ending 8 days before the judged night, using the valid days it has (QQ6) | It held its false rate at every baseline length simulated, and 0 of 8 stable real nights crossed; control limits taken from a reference window alone crossed 4.5 to 53 times their nominal rate in simulation and on 7 of the same 8 real nights; a 56-day reference would span every pipeline regime on record (review record, SP4) | 7, 15, 8 |
| P23 | false_discovery_rate stays 0.05 | Approved 2026-10-11 through QQ7 (A1) | With no change, 0.10 drift readings a month; 0.01 gives 0.03 but loses about 20 points of power on marginal changes (review record, SP6) | 8 |
| P24 | The composite: every member keeps its own row; two calibrated combined rows enter the same step - quality_worse, the weighted positive parts of the quality members, so an improvement never offsets a harm, and something_changed, a T-squared over the quality and behaviour members; a person reads evaluator check, drift (two consecutive nights), watch or quiet; nothing acts. Amends P15 | Declined 2026-10-11 through QQ8: the owner chose A3, one signed, correlation-adjusted combined score, the form P15 first approved, over P24's two rows | The 2026-09-07 step was a behaviour change a quality composite must not call worse, yet a person must see it; a signed, correlation-normalised sum lets an improvement cancel a harm; the per-item publish gate stays a veto chain (research record 5 and 7.4; review record, SP5) | 13, 12 |
| P25 | Weights and rho: start from reader harm - faithfulness 3 across its three rows, unsupported numbers 3, dropped hedges 2; the replay scores candidate weights by their worst detection across an injection library (swapped numbers, entities and dates, negated statements, dropped hedges, truncation, a copied lead, repetition) and proposes rho; a person commits both; a new member lands paused with weight 0 and rho 0. Sharpens P17 | Approved 2026-10-11 through QQ9 (A1 B1); its step where a person commits was replaced on 2026-10-11 by QQ27's guarded automatic application, with the auto_apply_tuning off switch | Calibration does not depend on the weights, because every p comes from the re-deals; weights fitted on live crossings would let the alarm choose what it alarms on | 8, 13 |
| P26 | The rows of Table RB and the settings of Table RC; amends P1: DriftEval loses site and page_type and gains the fields RB2 names, with the key run_id, date, check_name, comparison, model_id, instrument | Approved 2026-10-11 through QQ10 (A1) for the stored drift-evals row; the row list (Table RB) and the settings (Table RC) follow the rulings and are rewritten with the rows | Nothing is written to drift-evals yet, so a shape change costs plan edits only; after row #3 merges, every change is a migration (review record, Fowler 2.5) | all |
| P27 | Withdraw P7 (scipy in an optional extra installed by the council's jobs): the redesigned test needs only numpy | Approved 2026-10-12 through QQ20 (A1); numpy is listed directly in the base dependencies (row #3) | The exact tails P7 served left with rows #5 and #6 | 9 |
| P28 | The long-baseline comparison (row #14) moves to Table B with its trigger - 52 weeks plus 28 days of scored history, about 2027-09 - and then covers the quality members | Superseded 2026-10-12 by QQ18 (A1): row #14 becomes the frozen-anchor comparison, and the one-year comparison moves to Table B (B14) | A gated row would hold this plan open for about a year (review record, Fowler 7) | 14 |
| P29 | drift-evals names a kind of thing, which the owner's registry rule of 2026-09-27 forbids ("The value says what the ledger holds, never the kind of thing it is"): keep drift-evals and add a dated exception line to ledger-registry.md, or rename it summary-drift-evals | Approved 2026-10-11 through QQ11 (A1): drift-evals stays, and row #3 adds the dated line to docs/architecture/contracts/ledger-registry.md | The owner chose drift-evals on 2026-10-11; the cost is that no other judge can use the name (review record, Fowler 2.5) | 3 |
| P30 | Drop row #9's peak-memory observation | Approved 2026-10-12 through QQ21 (A1) | No machine is recorded per unit, so nothing could read it (review record, Fowler 7) | 9 |
| P31 | A plan of its own, outside this judge: sentence-level faithfulness (each summary sentence against its best article window; the mean, the minimum and the sentences under 0.50 and 0.80), entity and date checks, and per-column instrument stamps, as one eval-row change after a one-day measurement | Approved 2026-10-11 through QQ15 (A2 B1 C1): inside plan 65 as rows #36 to #39, not a plan of its own; one eval-row change after a one-day measurement; the new score runs beside the old until its replacements turn active (QQ28), then the old retires by itself | Scoring the whole summary against each window marks down multi-window articles: a 2-window article scores 0.22 and a 3-window article 0.40 below the same article read whole; about 3 times today's 12.5 scorer-minutes a day (estimate); Level 5; plan 36's 0.50 line must be re-cut on the new score (research record 4; review record, SP3) | 36 to 39 |
| P32 | Completeness and conciseness: pilot a sampled key-fact judge, never the summariser, on injected omissions before building it, its scores in a ledger of its own; a second faithfulness checker only after P31, as a 100-a-day trial | Approved 2026-10-11 through QQ4 (A1 B1 C3) for the key-fact check, including the owner's approval to commit the sampled article text for a rolling window (31 days by QQ30), which row #29 writes into CLAUDE.md section 0a as the second exception after corpus/ (QQ13 keeps withheld summaries there too, so plan 36's rejects exception is not used); the judge model is the summarizer's own for the pilot, not another model as first proposed here. The second faithfulness checker is asked as QQ16 | The only route to completeness and conciseness, unproven at 9B; it needs the article, which is gone the day after it is summarised (autotune-summary-quality.md, Where each metric runs), so it runs in the digest job or keeps a sample of articles, a carve-out like plan 36's J3 (Section 5; CLAUDE.md section 0a); 20 to 75 runner-minutes a day (estimate); a second checker adds 1 to 3 GB of memory and a dependency (review record, SP3) | - |
| P33 | Plan 36: this judge supplies the drift alarms; plan 36 drops its fit and fold rows (1, 2, 4, 5) and its self-judged fluency (rows 6 and 10), keeps the publish gate on absolute lines, the rejects ledger and rows 3, 8 and 13, re-points its console row to this judge, and fixes three stale premises: a fluency leg in an old workflow, a history rewrite in prune.yml that CLAUDE.md section 8 forbids, and an unregistered state/rejects/ that the gardener's sweep would empty (its retention a 30-day exception) | Withdrawn 2026-10-11: the owner moved plan 36 into this plan (Q41), so its parts are asked as QQ3, QQ4 and QQ12 to QQ14 | Plan 36's own correction E1 made every adaptive floor a watch-only fleet alarm, which is this judge's job, and two alarms per metric would disagree; self-judged fluency carries every documented judge bias on a near-ceiling dimension (research record 2.3; review record, Fowler 3 and Andre 6) | - |
| P34 | Per-source extraction health: a source-health check in feed-health or item-health, in a plan of its own | Settled 2026-10-12 through QQ17: not in plan 65 - the autotune-feed-quality plan and its judge own per-source extraction health and every action on a source; plan 65 records per-source summary failures for them | Row #1 deletes the only per-site extraction checks, and no summary metric sees one source's extraction breaking (RD6) | 1, 41; B13 |
| P35 | Accepting a known change: later, a person's mark resets one member's baseline; until then a deliberate change that starts no series reads as drift for up to 35 days | Settled 2026-10-12 through QQ19 (B1): a change declares the metrics it expects to move and those restart, with no person's mark; an undeclared change restarts every metric (A1) | The pipeline changed about every 9 days (RD5) | 42 |
| P36 | Correct the evaluation persona's line that calls a model judge a project non-goal, which contradicts CLAUDE.md section 1a | Approved 2026-10-12 through QQ22 (A1) and done in its own commit, 87929458 | CLAUDE.md section 1a: "LLM-as-judge is primary evaluation where applicable" | none (.github/agents/andre.agent.md) |
| P37 | Move Table Q to a standing file, TODO/owner-requests.md, read first and updated in every session | Declined 2026-10-12 through QQ23: the docs distillation is the memory (docs/how-to/distill-a-plan.md); Table Q stays the plan's work ledger until the plan is deleted | A plan-doc is deleted when it closes, and Table Q already tracks other plans' items (review record, Fowler 6) | - |
| P38 | P31's eval-row change also makes the faithfulness scorer replaceable: the scorer, its pinned revision and its window size are named in config, the eval column gets a name that does not name HHEM, and RC8's test reads the window size from that declaration | Approved 2026-10-11 through QQ15 (B1), inside row #37's change | The owner gave Q15's reason as "we may change the evaluator or something else". The judge side already copes: a replaced scorer starts a new series (P14), and each member names its instrument (RC11). The scorer side does not: hhem.py pins the HHEM model and revision as code constants, the column is named hhem, and CLAUDE.md section 10 asks for model references in config. P31 already restarts the faithfulness series, so doing it there costs no second restart; the rename reaches every reader of the column (Level 5) | 37 |
| P39 | Plan 36's fitted floors (rows #16, #17, #19 and #20, and the floor lines of row #24) are replaced by this judge's nightly test | Approved 2026-10-11 through QQ3 (A1) | Plan 36's own correction E1 left the floors no per-item action: faithfulness's 5th percentile (0.14) sits below the fixed 0.50 line, so each floor became a watch-only alarm on the whole digest, which this judge provides with a known false-alarm rate; the judge already watches the low end through the shares under 0.50 and 0.80 (QQ2) | 16, 17, 19, 20, 22, 24 |
| P40 | What follows a drift reading when no person reads it regularly | Approved 2026-10-11 through QQ29 (A1): automatic diagnosis, a larger key-fact sample while a quality alarm lasts, and one self-closing GitHub issue for a quality alarm; nothing published is touched | Every crossing on record traced to a dated deliberate change, and faithfulness never declined in 50 days, so a quality alarm is rare; under A7 a reading nobody sees has no value; acting on the pipeline was rejected before (P15, M2.4) | 12, 13, 34 |
| P41 | The other stored records: the sampled article text, the key-fact scores and the tuning-and-promotion log | Approved 2026-10-11 through QQ30 (A1 with a 31-day rolling window in config, B1, C1) | The normal ledger packing would keep article text for up to 36 months; deleting a file leaves it in git history, which only the gardener's history job may rewrite; every automatic move must stay explainable (QQ27, QQ28) | 29, 30, 32, 33 |
| P42 | The names of the records QQ30 adds and of the key-fact check's judge | Approved 2026-10-11 through QQ11 (B1, C1): key-fact-articles, key-fact-scores and drift-evals-tuning; the judge is summary-completeness-judge | The registry rule of 2026-09-27 (a name says what the ledger holds) and one unique set of ledger names (LedgerName); a judge named for what it measures keeps its name if its method changes | 29, 30, 32, 33 |
| P43 | Plan 36's publish gate | Approved 2026-10-11 through QQ12 (A1 B2 C1 D1): record-only first, then it withholds by itself while an independent check agrees with it and the withheld share stays under a ceiling, and returns to record-only when either fails; an unsupported number from the start, faithfulness only on the sentence-level score; a withheld summary is absent and the next-best duplicate takes its place; no stub pre-filter. The answer is the owner's Level 5 sign-off for the first change to a published day | Research record sections 4.2, 7.1, 7.2 and 7.4 (non-compensatory vetoes per summary, sentence-level scoring, oversampling summaries that hit a gate, agreement between independent instruments); the review record's sizes for 2026-09-24 to 2026-10-10 (5.6 percent under 0.50, 1.7 percent with an unsupported number); the owner's ruling of 2026-09-19 (plan 36 section 0e, H1) | 18, 22, 23, 29, 35 |
| P44 | Plan 36's rejects ledger and corpus fence | Approved 2026-10-11 through QQ13 (A1 B1 C1): withheld summaries are kept in key-fact-articles under its window and purge, with no separate rejects ledger; the corpus harvest skips the summaries the gate marks on a line that may withhold, live or not; an entry carries the summary, the article text, the failed line and its scores, the model and prompt identity and the item's identity, without the rendered prompt | CLAUDE.md section 0a keeps two article-text exceptions; plan 36's stale premises (an unregistered folder and a history rewrite outside the gardener's job) no longer arise; faithfulness scores reward copying (research record, Ladhak 2022), so the drift judge's copying watch shows the fence's effect | 27, 29 |
| P45 | One console home and the publish gate's panel | Approved 2026-10-11 through QQ14 (A1 B1): the drift judge's crossings and the gate's panel both on the Summaries page; the panel shows the gate's state, its two guards, the daily withheld share by reason and the stories lost, with no alarm of its own and never a withheld summary's text | The Summaries page already reads the score and item-health ledgers; the Judgement page's six panels are the same-story judge's; research record 7.4 (chart each daily gate rate, and the disagreement rate between independent instruments) | 12, 24 |
| P46 | The starting weight of a member that replaces another of the same reader harm | Approved 2026-10-11 through QQ31 (F1): the replacement takes over its predecessor's starting weight, and the predecessor retires the same night | QQ9 starts weights from reader harm (faithfulness 3); QQ28 starts a promoted metric at 0, and a tuning moves a weight by at most max_weight_step (1), so a replacement starting at 0 reaches 3 after three tunings, 16 to 20 weeks after its series starts | 38 |
| P47 | The second faithfulness checker | Approved 2026-10-11 through QQ16 (A1 with the owner's limits, B1, C1): at night on the kept articles, faithfulness_checks_per_night (8) within faithfulness_check_budget_minutes (40), classifying each sentence as supported or not; IBM Granite Guardian 3.3 8B (official GGUF) named in config, which is the owner's approval of the new model under ESCALATE C2; the judge summary-grounding-judge and its ledger grounding-verdicts | Research record 7.1 rank 3 (a second checker, all items if affordable, otherwise a sample) and 7.4 (chart the disagreement rate); the owner's limits of 2026-10-11 | 29, 35, 40 |
| P48 | The per-source record for the feed-quality plan | Approved 2026-10-12 through QQ32 (R1): summary-failures-by-source, one row per night, source and model series, with failures by reason and the points docked, unweighted | Separation of duties (the owner, 2026-10-12, Q52): plan 65 measures, the feed-quality plan decides; the registry rule of 2026-09-27 for the name | 41 |

Table Q - every owner request on these plans since 2026-10-10, and where it landed (kept current; an open item is closed only by a ruling, a row or a commit)

| # | Date | Request, in the owner's words where short | Status | Where it landed | Next step |
| --- | --- | --- | --- | --- | --- |
| Q1 | 2026-10-10 | Turn the drift improvement suggestion into a TODO plan; have Fowler and Andre review it; change nothing without approval | Done | The drift-review plan; 16 review changes approved (Table R) | - |
| Q2 | 2026-10-10 | Persist every check under state/raw/ as parquet with ledger enrolment; abandon GitHub issues | Done | Row #3, H4.1, B3 | - |
| Q3 | 2026-10-10 | Replace "alerts" with threshold wording | Done | H2 (threshold_crossed, threshold_not_crossed), H4.8 | - |
| Q4 | 2026-10-10 | Check the blueprint's formulas | Done | Table R; P2 to P4 | Re-checked by the redesign (Q20) |
| Q5 | 2026-10-11 | Name the plan summary-fidelity-judge; run it as an LLM-council judge in its own package; every number in a config JSON; its own ledger in parquet | Done | Rows #2 and #3; P6, P8 | - |
| Q6 | 2026-10-11 | Commit partial work to main, following CLAUDE.md | Done, standing | Every plan change is committed to main | Continue each session |
| Q7 | 2026-10-11 | Ask the escalation questions in the CLAUDE.md options format | Done, standing | Tables C and P | - |
| Q8 | 2026-10-11 | Is the council's model time a concern for this judge? | Done | [Judge declarations](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs): this judge runs no model server | - |
| Q9 | 2026-10-11 | A golden or reference set is impossible here; use trailing windows or a better scientific approach | Done | Rows #10 and #11 collapsed (D3, B10); P16 | Carried into the redesign (Q20) |
| Q10 | 2026-10-11 | Determinism is not an expectation; no back door | Done | C10, K1.5; the persona sentence corrected (P19, commit f1e7738) | - |
| Q11 | 2026-10-11 | determinism_violation should probably go | Out of this plan | B9 | A plan of its own when the owner asks for it |
| Q12 | 2026-10-11 | Judges need a lifecycle status, as ledgers and gardener tasks have | Delivered | [Judge declarations](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs) | - |
| Q13 | 2026-10-11 | The council should follow the gardener's strengths: capability, observability, flexibility, commit, sparse | Delivered | [Council rules](../docs/architecture/publishing/llm-council.md) | - |
| Q14 | 2026-10-11 | Each judge runs over its own outstanding dates (council P2, approved) | Delivered | [Per-judge dates](../docs/architecture/publishing/llm-council-dates.md#scheduled-dates-belong-to-each-judge); B8 here | This judge's nights_outstanding names its own missed dates |
| Q15 | 2026-10-11 | The judge must support new metrics: what it measures separate from how it tests, "because we may change the evaluator or something else" | Done in design for the judge; reopened 2026-10-11 for the evaluator | P13 (approved), row #4; P14 (approved): a replaced scorer starts a new series. The scorer itself is still HHEM, fixed in code | Carried into the redesign (Q20); the owner rules P38 |
| Q16 | 2026-10-11 | A composite weighted score, tunable as metrics are added, to decide when something drifted; the pasted penalty, band and veto proposal | Done in design, reopened | P15 and P17 (approved): a calibrated combined check, no automatic actions | Reopened by Q24 |
| Q17 | 2026-10-11 | Approve the recommendations of the last review (judge P13 to P19; council P1 to P8) | Done | This plan's Table P; [council rules](../docs/architecture/publishing/llm-council.md) | - |
| Q18 | 2026-10-11 | The ESCALATE triggers table does not render | Done | Table C's delimiter row had three cells for four columns; F1.5 had an extra cell | - |
| Q19 | 2026-10-11 | Disapprove site-drift-evals; use the generic name drift-evals | Done | H4.1, row #3, P1 | The contract and its stem follow: DriftEval, drift-eval; QQ11 kept the name with a dated exception to the naming rule |
| Q20 | 2026-10-11 | Judging per site is wrong: judge summary quality - faithfulness, coherence, conciseness and the other standard metrics - and the variance of the metrics in autotune-summary-quality.md, taking good elements from its loop | Proposed | Section 4; P20 to P30 | Asked through Table QQ (QQ1 to QQ11) |
| Q21 | 2026-10-11 | A hard look at what matters, how we measure it, and what is measured and judged upon | Done | Review record (TODO/20261011-summary-fidelity-judge-review-record.md); Section 4 | Rulings P20 to P37 |
| Q22 | 2026-10-11 | Which council rows bring the gardener's lifecycle, logging, telemetry and other strengths? | Delivered | [Council rules](../docs/architecture/publishing/llm-council.md) | - |
| Q23 | 2026-10-11 | Survey recent research on news and long-form summary metrics; use what is reasonable instead of a small set | Done | Research record (TODO/20261011-summary-quality-metrics-research-record.md); Section 4 | Instrument changes ruled as P31 and P32 |
| Q24 | 2026-10-11 | How to make a composite metric that decides | Proposed | Section 4 (the rule); P24, P25 | Asked through Table QQ (QQ8, QQ9) |
| Q25 | 2026-10-11 | Keep track of every item so nothing is lost | Done, standing | This table | Update it in every session that touches these plans |
| Q26 | 2026-10-11 | Plan 36 already designs fleet alarms on the same four metrics (raised by the review, not the owner) | Superseded by Q41 | Plan 36 is Section 5 of this plan; its parts are QQ3, QQ4 and QQ12 to QQ14 | - |
| Q27 | 2026-10-11 | The evaluation persona still calls a model judge a project non-goal, against CLAUDE.md section 1a (raised by the review, not the owner) | Proposed | P36 | The owner rules P36 |
| Q28 | 2026-10-11 | Write the research record's formulas as math that GitHub renders, not invented ASCII such as sqrt | Done | Research record (commit fce0749); this plan's Section 4 (2026-10-11) | The review record is an archive and keeps its ASCII formulas |
| Q29 | 2026-10-11 | What Display and Display only mean in the research record's table 5.1; what the redesign takes from the research, what it does not, and why | Answered | Research record, under table 5.1 (the terms); review record SP1 row s9 and section 4 of this plan (taken and not taken) | - |
| Q30 | 2026-10-11 | Number the council plan 64 and commit it to main directly | Done | Completed council plan retained in git history | - |
| Q31 | 2026-10-11 | Find the ambiguities in plan 64 and ask about them in the CLAUDE.md options format | Ruled | Council rulings retained in git history; [current rules](../docs/architecture/publishing/llm-council.md) | - |
| Q32 | 2026-10-11 | A paused or retired judge is not processed by the council, and retirement does not mean deleting code; is that how the gardener works? | Delivered | [Judge status](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs). The gardener skips paused and retired tasks but refuses a module no active or paused task uses | - |
| Q33 | 2026-10-11 | Pair each exit code with a label that says what it means, per pipeline | Delivered | [Events and exit codes](../docs/architecture/publishing/llm-council.md#events-and-exit-codes) | - |
| Q34 | 2026-10-11 | Allow judges to be run by hand | Delivered | [Manual runs](../docs/architecture/publishing/llm-council-dates.md#manual-runs-select-judges-and-one-date): one date per run | - |
| Q35 | 2026-10-11 | The council has its own config, each judge has its own config, and judges register with the council, as the gardener does | Done (2026-10-12, the rewrite) | [Judge registration](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs) | This judge's file carries lifecycle_status and runs_model, and its package is summary_fidelity_judge, when this plan's rows are rewritten |
| Q36 | 2026-10-11 | Record a judge's switch to active in the commit message and docs, not in a test; the gardener may be wrong to use one | Done | [Activation rule](../docs/architecture/publishing/llm-council.md#design-rationale-a-new-judge-starts-paused); the gardener's test dropped in #1548, merged 2026-10-11 | - |
| Q37 | 2026-10-11 | Deliver plan 64 as merged pull requests, with Fowler resolving any ambiguity | Delivered | Final council change merged in #1568; [current council rules](../docs/architecture/publishing/llm-council.md) | - |
| Q38 | 2026-10-11 | Plan 64 is delivered by another agent, so focus on this judge only: which documents count, which one to read, and are the inputs of autotune-summary-quality.md already in it? | Answered | Status (what to read); Section 4, Table RE (every element of the design of record and where it landed); P32 gained the article constraint the design of record states | Asked through Table QQ |
| Q39 | 2026-10-11 | The design of record watches the withhold rate; the redesign covers it only through its two causes (found while answering Q38, not raised by the owner) | Done (2026-10-12, the rewrite): RA13 withheld_share, declared paused by row #22 | Section 4, RE12 | - |
| Q40 | 2026-10-11 | Rename the plan to include 65: plan 65 | Done | TODO/20261011-65-summary-fidelity-judge-plan.md, titled Plan 65; links updated in plan 64, the research and review records and autotune-summary-quality.md | - |
| Q41 | 2026-10-11 | Plan 36 targets the same topic: bring its full scope into plan 65 and remove plan 36 | Done | Section 5 holds plan 36's full text; its rows are #16 to #28, each held until its question is ruled; TODO/20260918-36-summary-quality-autotune-plan.md deleted | QQ3, QQ4, QQ12 to QQ14 and QQ24 to QQ26 decide what of it is built |
| Q42 | 2026-10-11 | Ask every open decision of plan 65 as a question, one at a time, with its trade-offs in the CLAUDE.md section 0c format; P20 to P38 cannot be decided without them | In progress | Table QQ | After each ruling, record it and ask the next open question |
| Q43 | 2026-10-11 | Does plan 65 include the research data? | Answered | It cites the research record and carries its conclusions in Section 4 and in each decision's evidence; the record stays a file of its own, as the house keeps research records beside their plans | - |
| Q44 | 2026-10-11 | With A1: "I am assuming we are sampling - if a day ingested 10k items, we are not judging all of them, just a sample size that is config driven" | Answered | About 10,000 addresses are considered a day, but only 148 to 400 summaries a day (327 on average since 2026-09-24) were written and scored. The judge reads every scored summary, because it reads stored scores, runs no model and takes seconds. Sampling stays config-driven where it costs: observability.sample_rate decides which runs the faithfulness scorer scores (1.0 today, whole runs only), and QQ4's LLM judge would take a configured number of summaries a day. Section 4 says so The owner then said the intuition came from the completeness gap: research makes completeness essential, no score measures it, and an LLM judge that could measure it can only see a sample. That sampling belongs to QQ4, with its daily sample size in config | - |
| Q45 | 2026-10-11 | With A1 for QQ2: "is this what the research papers also suggest?" | Answered | Yes for what today's scores can measure: the research makes faithfulness essential, finds fluency near its ceiling and coherence secondary for short summaries, finds no validation for word-recall coverage or neighbouring-sentence coherence, treats copying and length as properties to watch rather than quality, and treats wrong numbers and dropped hedges as named error types (research record, sections 1.2, 2.1 and 2.6). It also makes completeness essential and conciseness third, which no score measures yet (QQ4), and asks for faithfulness per sentence with entity and date checks (QQ15) | - |
| Q46 | 2026-10-11 | For future questions, add hints on what comes from the research papers | Done, standing | Every question from QQ3 on carries what the research says, beside each option | - |
| Q47 | 2026-10-11 | "We can do that even today with the same model or we can ask another model to do it, say 2 random articles to be summarized and checked, in the judge pipeline" | Ruled as QQ4 (A1 B1 C3) | Rows #29 to #31; Table QQ, QQ4 | - |
| Q48 | 2026-10-11 | "The project assume little to no human intervention regularly, we should aim for auto everything, keep that as the driving principle. We make good design decisions and outcomes follow." | Done, standing | Section 0, A7; QQ27 to QQ29 ask again the steps that need a person; later questions are asked automation-first | Apply A7 in every later question |
| Q49 | 2026-10-11 | Confirm that key facts are not a usual pipeline thing in the prompt, and that only the judge checks and collects them as an extra validation: the digest.yml work shard does not produce key facts from source articles today and will not in the future | Done | Table B, B12; row #30. Checked on main on 2026-10-11: the summary prompts ask for none; a summary holds a title and a summary since the key points were removed on 2026-09-24; the work shard's first call labels the article's elements (quantities, dates, quotes, claims, key phrases, lede sentences) for the summary and its visual, which the judge does not use as key facts | - |
| Q50 | 2026-10-11 | How many more questions are there? | Answered | 13 open after QQ13: QQ14 to QQ26 | Continue one at a time |
| Q51 | 2026-10-11 | For the second checker: a configurable number of summaries, 8 not 40 (the most a run's shards take), finishing within 40 minutes, raised later once everything works; does it re-summarize from the source article or classify the summary; can it be any model, for example Gemma 4 instruct, or any model with GGUF support, so a future model change needs little work | Answered | QQ16, row #35, RC26 and RC29: it classifies each summary sentence as supported by the article or not and writes nothing; any GGUF model the pinned llama.cpp runtime serves can do it, named in config with its prompt template, once it catches planted unfaithful summaries | QQ16 asked again with GGUF options |
| Q52 | 2026-10-12 | "There will be another plan judge for autotune-feed-quality - you leave that alone. B1 - there is already a config value somewhere for feed source quality reliability or trust; you measure and dock points, some metric you keep track of, and the other autotune plan will use it and fix - separation of duties" | Done | QQ17; Table B, B13; row #41; QQ32 asks the record's name and fields | - |
| Q53 | 2026-10-12 | "/doc distill is memory" (answering QQ23) | Done | QQ23; P37 declined: durable outcomes live in docs/, distilled per docs/how-to/distill-a-plan.md, and git history keeps what was asked | - |
| Q54 | 2026-10-12 | Write a lean delivery version of this plan, and have Fowler and Andre take a hard look at what stays and what is ceremony | Withdrawn by the owner the same day | Plan 65.1 wrote the reviewers' cuts in before the owner ruled on them, so it was deleted from main; the reviews are kept as proposals in TODO/20261012-summary-fidelity-judge-hard-look-record.md | Q57 |
| Q55 | 2026-10-12 | No GitHub issues: stored metrics and code make the decisions; strip every issue, its code, tests and logic | Ruled | Row #34's issue, its job, its permission and its tests leave plan 65.2; Table B, B3 is superseded; the larger sample of row #34 is not part of this ruling | Applied when 65.2 is written |
| Q56 | 2026-10-12 | Row #28's guards for the content-similarity judge are that judge's domain: record the findings on its own page | Done | docs/architecture/publishing/autotune-content-similarity.md (commit 27f310c): a prompt ending in a space is open; token ids built from a string and thinking left on are closed | Row #28 keeps only this plan's own judges |
| Q57 | 2026-10-12 | Plan 65.2, with this plan as its source: group the rows logically, and discuss each proposed removal of over-engineering or ceremony with the owner before anything is deleted | Open | This plan stays the source; nothing leaves 65.2 that the owner has not ruled | The owner's rulings on each group |
| Q58 | 2026-10-12 | The intent for 65.2: unsupervised improvement of summary quality; built for 10,000 summaries a day; sampling, not full O(N) testing; config-driven, flexible and evolvable; lifecycle management; the approved second model samples summaries and a small sample of full articles, and classifies summaries; ledgers in state/raw and state/compact with ledger enrolment; the digest's work model does no more work; the other autotune judges (feed quality, feed reliability, content similarity) consume this judge's metrics to tune themselves; built for tomorrow, since summaries will grow and today's numbers will change | Done | The North Star above Section 0 (2026-10-12), carried into 65.2 | Every group is checked against it |
| Q59 | 2026-10-12 | Is there any gain in automatic tuning that is tuned and scored on faults the plan plants itself; how can tuning work outside the noise without people; was the research meant to cover this | Answered | Row #32 tunes the drift alarm's weights and rho, never a summary; the combined score it tunes added at most 0.055 detection (review record 5.7); the research covered measuring and detecting drift, not improving summaries, and leaves every action to a person (research record 7.4, 7.6) | A loop that improves summaries, discussed under Q57 |
| Q60 | 2026-10-12 | The owner never agreed to a three-sentence summary; that assumption is wrong and stays out of the plan | Ruled | Struck from row #36 (Y1.5, Y9.1); nothing in the plan assumes a summary length | - |
| Q61 | 2026-10-12 | Rulings for 65.2 from the grouped discussion | Ruled | Approved: per-sentence faithfulness only on the sample, in the council, by the second model, with the work step unchanged (reverses QQ15 B1 in part); every recorded change is named on the rows, and only a change to a metric's own scorer restarts it (reverses QQ19); sample sizes come from a precision target and length limits are relative to recent days, all in config. Deleted: tuning of the alarm's weights and rho - weights stay at QQ9's values and rho is measured once by row #8's replay (reverses QQ27); settings copied onto every result row, the stored rule description and the reshuffle counts (reverses QQ10 in part); adaptive reshuffle stopping (reverses P4); crossings_budget and its stop (reverses P18); the hhem column renames, while the scorer is still named in config (reverses P38 in part); the name and date checks, and unsupported numbers as a reason to withhold (reverse QQ15 B1 and QQ12 B2 in part); display-only metrics and scored_nulls stored nightly (reverses QQ2 in part); row #28 as a shared module. Added: a research pass on unsupervised improvement and fine-tuning, then its rows; a metrics contract the other autotune judges read, per source and per feed, extending row #41 | Applied when 65.2 is written |
| Q62 | 2026-10-12 | Article-length bands go entirely: they only guess, and quality comes before brevity - the content finds its own length | Ruled | RC8 and every length-band adjustment leave 65.2; the drift judge adjusts for source only, and its faithfulness metrics move to the sample's sentence checks (Q61) | Applied when 65.2 is written |
| Q63 | 2026-10-12 | Show what the second model labels (source, prompt, output), recommend a GGUF model and a sample size, and say whether source text is needed; keep only the sample, corpus-style, rolling; propose a new model for completeness; explain how the publish gate works without length bands | Answered; ruled in Q73 | Labels: each summary sentence against the source text the summarizer was given, which is needed; Granite Guardian 3.3 8B; 100 a night at random. Open: corpus-style storage of the sample, Gemma 4 E4B for completeness, and the gate's line without length bands | The owner's rulings |
| Q64 | 2026-10-12 | Keep the owner's intent as a North Star at the beginning of the plan, to ground every agent and research pass; it includes unsupervised fine-tuning for quality | Done | The North Star above Section 0, carried into 65.2 | - |
| Q65 | 2026-10-12 | Run the research pass on unsupervised improvement and fine-tuning approved in Q61 | Done | TODO/20261012-unsupervised-summary-improvement-research-record.md: build a paired champion/challenger harness in the council first; the judge's accuracy on news limits what can be learned; fine-tune with DPO on judged pairs on a rented 24 GB GPU started from CI; completeness from small-model key facts is unproven | The owner rules on a second, small checker and on the rented GPU; then the improvement-loop rows |
| Q66 | 2026-10-12 | Add a second, small checker beside Granite Guardian (Table D, D1) | Ruled: approved | One MIT-licensed checker, FactCG-DeBERTa-L or MiniCheck-Flan-T5-L, measured beside Granite on the same sample; the one better on this digest's news runs the tests and the other is the held-out judge the tuning never sees; it is a second model approved under the North Star | Its contracts follow Q68 |
| Q67 | 2026-10-12 | Table E is partly flawed: what would be fine-tuned, the summarizer or the scorer? A scorer would need retraining now and then; instead, architect the plan to move to newer classes of model as capabilities grow. Leaning towards E3 | Answered; E3 ruled in Q73 | Table E was about fine-tuning the summarizer; no scorer is trained in this plan. Under E3 nothing is trained: quality improves through tested setting changes and through newer models that enter as candidates and are promoted only when they beat the incumbent on the same sample; the North Star's first line then reads 'tune settings and move to newer models' instead of 'fine-tune' | Confirmation of E3 |
| Q68 | 2026-10-12 | Design the plan so the scorer models can be swapped: the judge as a pipeline, where a scorer - Granite and MiniCheck today, another model tomorrow - is a replaceable stage; create the contracts; Fowler's job, intent first, contract follows | Ruled | TODO/20261012-summary-quality-scorer-contracts-design.md: one scorer interface for every model; a config file per scorer; candidates promoted automatically past guards on planted faults and controls, with an off switch; the same pattern for summarizer candidates; three decisions for the owner (T, U, V) | Q69 to Q71 |
| Q69 | 2026-10-12 | May code switch the summarizer? (design, Table T) | Ruled: T1 | Code may promote a committed, pinned candidate summarizer that passes the test bench's guards (held-out judge, a self-comparison test, fresh articles, no other metric worse); off switch auto_promote_summarizer, with no default; reverses plan 65 B2's clause that a model entry never moves by itself (P15), for this path only | Applied when 65.2 is written |
| Q70 | 2026-10-12 | Which small checker? (design, Table U) | Ruled: U1 | FactCG-DeBERTa-L and MiniCheck-Flan-T5-L both run as candidates for the first window; the one that takes a job stays | Applied when 65.2 is written |
| Q71 | 2026-10-12 | One judge for every sampled check and the test bench (design, Table V); a better name than summary-source-judge, because in this project 'source' means a feed or publisher, the feed-quality judge's domain | Ruled: V1; name N1 (Q72) | One judge hosts the sentence checks, the completeness checks, scorer candidates and summarizer candidates (reverses the two-judge split of QQ11 C1 and QQ16 C1). 'Source' now means a feed or publisher only: the design's task names read sentence_against_article and summary_against_article, and the North Star says article text | Applied when 65.2 is written |
| Q72 | 2026-10-12 | The unified judge's name | Ruled: N1 | summary-fidelity-judge names the one judge of the sampled checks and the test bench (package summary_fidelity_judge); the drift judge becomes summary-drift-judge (package summary_drift_judge, config/judges/summary-drift-judge.json, family summary-drift-judge; drift-evals keeps its name). Both names now say what each judge does; reverses the drift judge's name of Q5; nothing is built, so it costs plan text only | Applied when 65.2 is written |
| Q73 | 2026-10-12 | Rulings E3, A1, B1 and C1 | Ruled | E3: nothing is trained; quality improves through tested setting changes and newer models that enter as candidates (the North Star's first line now says so). A1: the evaluation sample is a file beside the training corpus, holding only the sample, rolled after 31 days and cleaned from git history by the existing corpus squash; it is never trained on, and its verdicts are enrolled ledgers. B1: Gemma 4 E4B lists each sampled article's key facts, counted only once it passes planted omissions. C1: the publish gate has one line per number of article windows the scorer read, fitted from the sample's verdicts; it withholds only while the sample shows the line precise enough and returns to marking when it is not (replaces QQ12's agreement guard; completes Q63's B4) | Applied in plan 65.2 |

Table R - the review changes the owner approved on 2026-10-10, and where each landed in the 2026-10-11 draft (rows #2, #5 and #6 later collapsed with QQ1)

| # | Change | Lands in rows | Note |
| --- | --- | --- | --- |
| R1 | Read through ledger.load_days, never DuckDB over state/compact/; duckdb banned outside tests | 3, 4, 8 | Applied |
| R2 | Every check returns a p-value; the false-discovery step is the only threshold | 6, 7, 8 | Applied; P2 and P4 refine it |
| R3 | Article count from the item-health census, negative-binomial tail, no skip of other checks, feed-health named first | 5 | Applied; P3 refines it |
| R4 | A new model pair's comparison with earlier pairs is stored, never a crossing | 7 | Applied as the earlier_model_baseline outcome (H2.4) |
| R5 | Page types per host; reshuffles within type; the mix stored as a note; the #1270 fixture a gate (C6) | 2, 4, 6, 7 | Applied; the note is the page_mix row (H1.7) |
| R6 | Daily runs that never repeat one notice; fixed text; trigger C7 | 9 | Superseded: no issues exist, the council runs nightly, and its fixed commit message keeps C7 satisfied |
| R7 | A site stays the host; multi_tenant_hosts applies to listed hosts only; site keys in code spans | 2 | Applied |
| R8 | Alert names that state a measurement | 3 | Replaced by the rename request: check names (H1) plus outcomes (H2) |
| R9 | Urgent marking for a count crossing with p under 0.001; no label | 8 | Withdrawn by P9 on 2026-10-11: its only reader, the issue title, went with the issues |
| R10 | A flag for the new path; the old rules and settings leave together | 1, 9 | Superseded: row #1 deletes the old review outright, and registration in council.tenants is the switch |
| R11 | scipy in an optional extra installed only by the job that runs the checks | 5, 9 | Adapted to the council's judging job (P7) |
| R12 | Scorer reference and golden set in the jobs that already load their models; one benchmark-row contract | 10, 11 | Withdrawn 2026-10-11 with rows #10 and #11 (D3; B10) |
| R13 | The replay covers past dates, reshuffled labels and injected cuts, with its own test | 8 | Applied |
| R14 | Log word counts for the length check | 7 | Applied |
| R15 | The furniture check reads extraction_suspect with an exact p-value | 6 | Applied; named page_furniture by the rename request |
| R16 | Plan text: complete Files touched lists, the measured #1270 cause in A1, a Status line | all | Applied; its schemas/app-config.schema.json item was dropped, because the generated schema folder was deleted on 2026-09-23 (backend/tests/contracts/test_no_generated_layer.py) and a new contract now owes a fixture instead |

Table S - checked and kept as written

| # | Item | Why it stays | Raised by |
| --- | --- | --- | --- |
| S1 | ESCALATE triggers C1, C2 and C4; Level 5 on row #3; the execution stamp | The ledger door is the documented bounded read; Level 5 pauses for the owner; the stamp is execute-a-plan's own line | Fowler |
| S2 | The ledger's place and name: drift-evals inside the family summary-fidelity-judge, file names minted by the door, enrolment for packing; the registry refuses the nested path when it loads | backend/idhazh/contracts/ledgers.py; ledger-registry.md | Fowler |
| S3 | Two-sided Wasserstein-1 | A shorter extraction can be a better one; the distance reads in words or score points and needs no bins | Andre |
| S4 | The 20-article floor | Below 20 a real shift is rarely caught | Andre |
| S5 | Benjamini-Hochberg over Bonferroni | Valid once every check has a p-value (R2) | Andre |
| S6 | Stage 1 checks ignore the model | Already true for the length rule today | Andre |

## 4. The design, as ruled on 2026-10-11 and 2026-10-12

Evidence: TODO/20261011-summary-quality-metrics-research-record.md (76 verified sources) and TODO/20261011-summary-fidelity-judge-review-record.md (Andre's and Fowler's reviews, replayed on the 50 daily records under state/day-metrics/, 2026-08-21 to 2026-10-10).

In one paragraph: the judge judges the quality of the digest's summaries, per production model series, not each site's articles. Each night it compares the last 7 days, recent days weighted more, with the 56 days that end 8 days before the judged night (QQ6), skipping days that are missing, failed or thin, dealing whole days to learn what no change looks like, after adjusting each summary for its article's length band and source. Faithfulness, unsupported numbers and dropped hedges are judged; copying and summary length are watched as behaviour; coverage, coherence and the input mix are shown as diagnostics; article length and source are covariates, never judged. One combined score sits beside the members: the research's signed, correlation-adjusted score over the judged metrics (QQ8), and a person reads one of four levels. Once a week each member is also compared with its series' frozen first 56 valid days (QQ18), and every recorded change starts a new series unless the change declares the metrics it moves (QQ19). The judge tunes its weights and rho and promotes or pauses metrics by itself within guards (QQ27, QQ28), diagnoses every alarm and opens one GitHub issue per quality alarm (QQ29); nothing it reads changes what is published. Two model judges join it - summary-completeness-judge for key facts on a sample (QQ4) and summary-grounding-judge with Granite Guardian on 8 summaries a night (QQ16) - and the publish gate (rows #22 and #23) is the one part of the plan that changes what readers see (QQ12).

What the judge reads: every scored summary in its windows; it samples nothing itself. About 10,000 addresses are considered a day, but only about 150 to 400 summaries a day are written and scored, so the 63 days its windows span hold about 9,500 to 25,000 stored rows, and the judge's work takes seconds with no model (owner, 2026-10-11, Q44). Sampling stays config-driven where it costs: observability.sample_rate decides which runs the faithfulness scorer scores (1.0 today; whole runs only, never part of a run, docs/concepts/evaluation.md), and any LLM judge takes a configured number of summaries a day (QQ4). A day with fewer than min_day_rows scored rows is left out and stored as thin (RC4).

Table RE - what the redesign takes from the design of record, docs/architecture/publishing/autotune-summary-quality.md (unchanged since 2026-09-29; the owner asked to take its good elements without following it fully, Q20)

| # | The design of record | In this redesign | Where |
| --- | --- | --- | --- |
| RE1 | Four metrics, named with SummEval's axes: Faithfulness, Coverage, Coherence, Fluency | Faithfulness is judged; Coverage and Coherence are shown as diagnostics; Fluency is not built as specified | RA, P21 |
| RE2 | Faithfulness (HHEM) is the one metric reliable enough to withhold a story, at the absolute 0.50 line | Judged three ways: an index, the share under 0.50 (the block line) and the share under 0.80 (the display band) | RA1 to RA3 |
| RE3 | Coverage, the recall of the article's 20 most-used content words, only watches: low recall can be a faithful abstraction | A diagnostic, never judged: the research found no validation for this kind of recall. Completeness waits for an instrument that measures it | RA12, P32 |
| RE4 | Coherence, the cosine of neighbouring sentences, is a monitor and never a gate: a repeated sentence reads as coherent | A diagnostic; repetition is judged on its own by repetition_loops, paused until its base rate is known | RA6, RA12 |
| RE5 | Fluency by G-Eval: the summariser judges its own output, next day, on about 30 summaries | Not built: a model judging its own text favours it, on a dimension already near its ceiling. The sampled key-fact check measures completeness and conciseness instead; for its pilot it uses the summarizer's own model, listing the article's key facts before it sees the summary | QQ4, rows #29 to #31 |
| RE6 | No human labels: each metric is judged against its own rolling distribution | Taken: each member is compared with its own earlier 56 days, which end 8 days before the judged night (QQ6); no golden or reference set | P22 |
| RE7 | An adaptive floor per metric, the 5th percentile of a fixed-size rolling histogram, fitted daily, damped, gated and clamped | Not taken: a fitted floor says where the low tail sits, not whether a day moved beyond chance, and limits estimated from a reference window alone crossed 4.5 to 53 times their nominal rate in simulation. The whole-day re-deal test replaces the fit, and plan 36's fitted floors (rows #16, #17, #19 and #20) are dropped (QQ3) | P22, QQ3 |
| RE8 | The adaptive floors only downgrade or watch; plan 36's correction E1 later made every one a watch-only fleet alarm | Taken: this judge is that alarm. Nothing it reads downgrades or withholds a summary; on an alarm it stores a diagnosis, enlarges the key-fact sample and opens one issue per quality alarm (QQ29), and a person or an agent reads one of four levels | P24, B2, QQ29 |
| RE9 | Faithfulness seeds from the committed HHEM history, so its first day has a baseline | Taken in effect: the judge reads the committed eval ledger, which held 50 scored days when the redesign was reviewed | P22 |
| RE10 | When the fit stops moving, the council's cadence drops to weekly | Not taken: the judge runs no model and costs one runner job a night | RB7 |
| RE11 | The publish gate is "a veto chain, never a composite", on absolute lines, behind a flag that first only stamps; an overall number "feeds no action" | Taken (QQ12): rows #22 and #23 stamp every summary record-only, then withhold by themselves while an independent check agrees with them, and only on an unsupported number or the sentence-level faithfulness score. This judge's combined score only reports and feeds no action, which the page allows | P24, QQ12 |
| RE12 | The withhold rate is itself watched | Covered through its two causes, faith_below_050 and numbers_unsupported. Once the gate (row #22) stamps its decision, a member reading that stamp lands paused, so a cause the owner later promotes to block is counted too | RA2, RA4, Q39 |
| RE13 | Anything that needs the article runs the same day, because article bodies are gone the next day; the council reads committed rows only | Taken: the judge reads committed eval rows only. The key-fact check needs the article, so the digest run keeps the article text of the day's 30 sampled summaries for a rolling window (31 days, QQ30), and the check reads it the next night (QQ4) | QQ4, rows #29 to #31 |
| RE14 | A change to what a column means goes through METRICS_VERSION, never a config knob | Taken: an instrument change starts a new series, and each member names its instrument key | P14, RC11 |
| RE15 | UniEval was rejected: llama.cpp cannot serve it, and it was never measured | Kept rejected: the research found that such evaluators transfer poorly to LLM summaries | Research record, section 2.1 |

Table RA - what is judged (declared per P13 as amended by P21)

| # | Member | Role (QQ10's words) | Column and daily statistic | Adjusted for | Worse when | Status at landing | Weight |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RA1 | faith_index | judged | mean of logit(hhem), clipped at logit_clip | length band, source | lower | active | 1 |
| RA2 | faith_below_050 | judged | share of hhem under 0.50 | length band, source | higher | active | 1 |
| RA3 | faith_below_080 | judged | share of hhem under 0.80 | length band, source | higher | active | 1 |
| RA4 | numbers_unsupported | judged | share with at least one unsupported number | source | higher | active | 3 |
| RA5 | hedges_dropped | judged | share with hedge_dropped | source, article hedging present | higher | active | 2 |
| RA6 | repetition_loops | judged | share with self_repetition above 0.05 | none | higher | paused until its base rate is known | 0 |
| RA7 | length_short | judged | share under 25 summary words | none | higher | paused until its base rate is known | 0 |
| RA8 | copy_index | watched | mean extractiveness | never | higher | active | watched only; never in the combined score |
| RA9 | copy_ceiling | watched | share with verbatim_run above 0.50 | never | higher | active | watched only; never in the combined score |
| RA10 | length_median | watched | median summary words | never | either | active | watched only; never in the combined score |
| RA11 | scored_nulls | evaluator | share of rows missing hhem, coherence or semantic_coverage | none | higher | active | - |
| RA12 | coverage, coherence, input mix | shown | semantic_coverage and coherence (median, low tail, spread); length-band shares, source composition, extraction_suspect rate | - | - | stored with p, outside the step | - |
| RA13 | withheld_share | watched | share of summaries stamped would_be_withheld or withheld (row #18) | never | higher | paused (row #22) | watched only; never in the combined score |
| RA14 | completeness | judged | mean completeness of the sampled key-fact rows (key-fact-scores, row #30) | length band, source, through the eval row of the same url_key | lower | paused (row #31); its own day minimum, 20 | 0 |
| RA15 | conciseness | judged | mean conciseness of the sampled key-fact rows | length band, source, through the eval row of the same url_key | lower | paused (row #31); its own day minimum, 20 | 0 |
| RA16 | faith_sentence_index | judged | mean of logit(sentence_faithfulness_mean), clipped at logit_clip (row #37) | length band, source | lower | paused; replaces faith_index (row #38) | 1, from the night it turns active (QQ31) |
| RA17 | faith_sentence_below_050 | judged | share whose lowest sentence scores under 0.50 | length band, source | higher | paused; replaces faith_below_050 (row #38) | 1, from the night it turns active (QQ31) |
| RA18 | faith_sentence_below_080 | judged | share whose lowest sentence scores under 0.80 | length band, source | higher | paused; replaces faith_below_080 (row #38) | 1, from the night it turns active (QQ31) |
| RA19 | names_unsupported | judged | share with at least one unsupported name (row #37) | source | higher | paused (row #38) | 0 |
| RA20 | dates_unsupported | judged | share with at least one unsupported date (row #37) | source | higher | paused (row #38) | 0 |

RA13 to RA20 are declared by the rows their status names, land paused and join only through row #33's automatic promotion (QQ28); RA16 to RA18 each name the member they replace and take its starting weight (QQ31), and RA19, RA20 and the declaration fields they use are proposed for the owner's single approval of the plan (QQ26). From row #37, hhem, hhem_full and hhem_delta read as summary_faithfulness, summary_faithfulness_full and summary_faithfulness_delta (Y7.1 to Y7.3), and RA1 to RA3 and RA11 read the renamed column.

Not judged: compression, hhem_full, hhem_delta, score_ms, band, determinism_violation, and fluency as plan 36 specifies it (row #21; QQ4). Completeness and conciseness come from the sampled key-fact check (QQ4; rows #29 to #31): its scores land paused and join the alarm once its pilot passes. Rows flagged extraction_suspect leave the quality members, and a source the feed-quality plan flags will leave them too once that plan's record exists (QQ17).

The rule, as a builder implements it (full form in the review record, section SP5):

- **Expected value.** For summary $i$ and quality member $m$, $y_{mi}$ is the member's value. The expected value is the baseline mean of the summary's length band $b_i$ plus a source offset shrunk toward zero by $k$ = source_shrinkage_rows, and the residual is what is left:
    $$e_{mi} = \mu_m(b_i) + u_m(s_i), \qquad u_m(s) = \frac{\sum_{i \in B,\ s_i = s} \left( y_{mi} - \mu_m(b_i) \right)}{n_B(s) + k}, \qquad r_{mi} = y_{mi} - e_{mi}$$
    Behaviour members are never adjusted: $r_{mi} = y_{mi}$.
- **Daily value.** $x_{md}$ is the mean residual of day $d$ (the median of $y$ for length_median), and $n_d$ is the day's row count; a day with fewer than min_day_rows rows is left out and stored as thin.
- **Windows.** The recent window $R$ is the recent_days days ending on the judged night $t$; the baseline $B$ is the baseline_days days ending baseline_lag_days days before $t$. Each holds only its valid days: a day with no run, a failed run or a thin day is skipped, never filled in. The member is tested only when $R$ holds at least min_recent_days valid days and $B$ at least min_baseline_days; otherwise its row is stored as too few days. The row records how many valid days each window used.
- **Test statistic.** The recent days $R$ (recent_days) carry recency weights $a_d = \lambda (1 - \lambda)^{t - d}$, with $\lambda$ = recency_lambda and $t$ the judged date; the baseline days $B$ (baseline_days) are weighted by row count alone; $h_m$ is $+1$ or $-1$ by harm direction:
    $$T_m = h_m \left( \frac{\sum_{d \in R} a_d n_d x_{md}}{\sum_{d \in R} a_d n_d} - \frac{\sum_{d \in B} n_d x_{md}}{\sum_{d \in B} n_d} \right)$$
- **No-change case.** $N$ deals $\pi$ of the whole days of $R \cup B$ into the two windows, the same deal for every member and the combined score, give $T^{\ast}_{m,\pi}$. The member's score is standardised against the deals and widened for its day-to-day correlation $\rho_m$ (rho); $z^{\ast}_{m,\pi}$ is each deal standardised the same way, unwidened:
    $$z_m = \frac{T_m - \operatorname{mean}_{\pi} T^{\ast}_{m,\pi}}{\operatorname{sd}_{\pi} T^{\ast}_{m,\pi}} \bigg/ \sqrt{\frac{1 + \rho_m}{1 - \rho_m}}, \qquad p_m = \frac{1 + \operatorname{count} \lbrace \pi : z^{\ast}_{m,\pi} \ge z_m \rbrace}{N + 1}$$
- **Combined score.** Over the active judged quality members $Q$, each $z_m$ oriented so that a positive value means worse, with weights $w_m$ (combine_weight) and $R$ the correlation matrix of the members' standardised daily values over the baseline days. It is tested one-sided for worse, and its p-value comes from the same deals, so its calibration does not depend on the weights; an improvement in one member offsets a harm in another inside it (owner, QQ8):
    $$C = \frac{\sum_{m \in Q} w_m z_m}{\sqrt{w^{\top} R w}}$$
- **Decision.** One false-discovery family $F$ per (run_id, date, series): the active members and the combined score. Benjamini-Hochberg at $q$ = false_discovery_rate sorts the p-values and crosses the $k$ smallest, where $k = \max \lbrace i : p_{(i)} \le i q / |F| \rbrace$. Paused members and diagnostics keep a p-value and get no q-value.
- Reading levels, derived from stored rows: evaluator check (an evaluator row crossed; read it before calling anything drift); drift (the combined score or a judged quality member crossed on drift_consecutive_nights consecutive nights); watch (any other crossing); quiet, too few days, or new series. Every crossed row prints its effect raw and adjusted, its q, and the inputs that changed inside its window.
- A new member lands paused with weight 0 and rho 0; the scheduled replay runs it on past nights and planted faults, promotes it when it passes QQ28's guards, and tunes weights and rho within QQ27's guards; a member that replaces another for the same reader harm takes over its predecessor's starting weight (QQ31). auto_promote_metrics and auto_apply_tuning stop either at once.
- Comparisons: trailing (the recent week against the lagged baseline) every night, and anchor (the recent week against the series' frozen first anchor_days valid days) every anchor_look_every_days nights (QQ18). A series is one production model with one instrument per column; every recorded change is a boundary, and a change that declares its expected shifts restarts only the members it lists (QQ19).

Table RB - the rows after the redesign (written into Section 2 on 2026-10-12)

| # | Row | Depends-on | Level | Change |
| --- | --- | --- | --- | --- |
| RB1 | #1 The drift review is deleted | - | 3 | Unchanged, except that its removed-setting message no longer names min_articles as moved |
| RB2 | #3 The judge's ledger and its tenant module | [Council judge registration](../docs/architecture/publishing/llm-council.md#each-registered-judge-declares-whether-it-runs), delivered | 5 | DriftEval loses site and page_type and holds the fields QQ10 ruled: run_id, date, model_id, instrument, check_name, role, statistic, comparison, valid days used in each window, baseline_lag_days, recency_lambda, raw and adjusted recent and baseline values, effect, p_value, q_value, reshuffles, rho, the tuned-weights version on the combined row, outcome, the settings in force and inputs_changed; key run_id, date, check_name, comparison, model_id, instrument; the judge registers in config/llm_council.json (judge_names), and config/judges/summary-fidelity-judge.json carries lifecycle_status paused and runs_model false beside the judge's settings (Q35) |
| RB3 | #4 Settings file and member declarations per model series | 3 | 3 | Absorbs row #2's settings file; site identity is deleted; declarations gain role, statistic, line, transform, adjust_by, instrument and rho |
| RB4 | #7 Per-summary values, daily values and the mix adjustment | 4 | 3 | Replaces the per-check modules of rows #5 to #7 |
| RB5 | #15 The recency-weighted whole-day test | 7 | 3 | New: one test module for every member |
| RB6 | #8 The false-discovery step per (run, date, series), and the replay with an injection library | 15 | 3 | The replay also proposes weights and rho (P25) |
| RB7 | #9 The switch | 1, 8 | 3 | lifecycle_status turns active in config/judges/summary-fidelity-judge.json, the owner's decision named in the commit message and the judge's doc ([activation rule](../docs/architecture/publishing/llm-council.md#design-rationale-a-new-judge-starts-paused), Q36); its peak-memory observation is dropped (P30) |
| RB8 | #13 The combined score and the reading levels | 9 | 3 | Replaces the all-sites and combined-measures row |
| RB9 | #12 The panel on the console Model page | 9 | 3 | Lists crossings by level, smallest q first; the publish gate's panel sits beside it (QQ14) |
| RB10 | #2, #5, #6 | - | - | COLLAPSED: site identity; article count, which is feed volume; unusually short and page furniture, which are input properties |
| RB11 | #14 The anchor comparison | 8 | 3 | Rewritten (QQ18): the recent week against each series' frozen first 56 valid days, once a week; it replaces the one-year comparison, lands paused and joins through QQ28 |

Table RC - settings that change (config/judges/summary-fidelity-judge.json unless the note names another home; the rest of F1 stays)

| # | Field | Default | Range | Note |
| --- | --- | --- | --- | --- |
| RC1 | recent_days | 7 | 7 to 14, whole weeks | F1.1, range narrowed |
| RC2 | baseline_days | 56 | 14 to 91, whole weeks | F1.2; the research's window (QQ6) |
| RC3 | recency_lambda | 0.15 | 0 to 0.5; 0 is a flat window | New |
| RC4 | min_day_rows | 100 | 20 to 1000 | Replaces min_articles (F1.3); a member may declare its own, 10 to 1000 (X3.6; the key-fact members 20) |
| RC5 | min_recent_days, min_baseline_days | 4, 7 | 3 to 7; 7 to 28 | New; the windows use the valid days they have and judge once these minimums are met (QQ6) |
| RC6 | drift_consecutive_nights | 2 | 1 to 7 | New |
| RC7 | logit_clip | 0.001 | 0.000001 to 0.01 | New |
| RC8 | length_band_edges_words | 900, 1650 | ascending, 100 to 10000 | New; a test holds them to HHEM's window geometry |
| RC9 | source_shrinkage_rows | 10 | 0 to 100 | New |
| RC10 | trailing_line_quantile | 0.10 | 0.01 to 0.25 | New; diagnostic tails |
| RC11 | metrics | RA1 to RA12 | role, statistic, line, transform, harm_direction, adjust_by, instrument, combine_weight 0 to 10, rho 0 to 0.8, lifecycle_status | F1.13 as amended by P21 |
| RC12 | short_tail_percentile, multi_tenant_hosts, page_types | - | - | Removed (F1.5, F1.9, F1.10) |
| RC13 | baseline_lag_days | 8 | from recent_days to 28 | New (QQ6): the baseline ends this many days before the judged night, so it never overlaps the recent window |
| RC14 | auto_apply_tuning | none: set it on purpose | true or false | New (QQ27): false stops automatic application of tuned weights and rho at once; the replay still runs and records its proposals as held |
| RC15 | tuning_every_days | 28 | 7 to 91 | New (QQ27): how often the replay tunes |
| RC16 | max_weight_step, max_rho_step | 1, 0.1 | 0.1 to 5; 0.01 to 0.3 | New (QQ27): the largest change one tuning may make |
| RC17 | auto_promote_metrics | none: set it on purpose | true or false | New (QQ28): false stops automatic promotion and pausing of metrics at once |
| RC18 | promotion_min_days | 28 | 7 to 91 | New (QQ28): usable days a paused metric needs before it can turn active |
| RC19 | promotion_min_detection | 0.8 | 0.5 to 0.99 | New (QQ28): the share of weeks in which a metric must catch its own planted fault |
| RC20 | auto_respond_to_drift | none: set it on purpose | true or false | New (QQ29): false stops the larger sample and the issue at once; the diagnosis is still stored |
| RC21 | drift_sample_multiplier | 2 | 1 to 4 | New (QQ29): how much the key-fact sample grows while a quality alarm lasts |
| RC22 | sampled_article_keep_days | 31 | 7 to 60 | New (QQ30): the rolling window for sampled article text; home: the window of the gardener retention task that owns key-fact-articles (row #29, X1.8) |
| RC23 | keyfact_sample_per_day | 30 | 2 to 100 | New (QQ4): summaries the key-fact check samples a day; home: config/idhazh.json evaluation, read by the digest run and the judges (row #29, X1.7) |
| RC24 | gate_trial_days | 28 | 7 to 91 | New (QQ12): the days the publish gate's guards are read over, before it may withhold and every night after; home: config/idhazh.json evaluation.publish_gate (rows #22 and #23) |
| RC25 | gate_min_agreement | 0.7 | 0.5 to 0.95 | New (QQ12): the share of would-be withholds an independent check must confirm; home: config/idhazh.json evaluation.publish_gate (rows #22 and #23) |
| RC26 | faithfulness_checks_per_night | 8 | 1 to 50 | QQ16 (the owner, 2026-10-11): summaries the second checker reads a night: its planted variants (RC37) first, then the gate's would-be withholds, then sampled ones; the most a run's shards take; raised once everything works; supersedes gate_checks_per_day (10) of QQ12; home: config/idhazh.json evaluation, read by the digest run and the judge (row #29, X1.7) |
| RC27 | withhold_share_ceiling | 0.25 | 0.05 to 0.5 | New (QQ12): about twice the highest share seen (0.117 under 0.50 in late August); a night above it publishes record-only; home: config/idhazh.json evaluation.publish_gate (rows #22 and #23) |
| RC28 | withhold_failing_summaries | none: set it on purpose | true or false | New (QQ12): false stops withholding at once and the stamps continue; replaces plan 36's publish_gate.enabled; home: config/idhazh.json evaluation.publish_gate (rows #22 and #23) |
| RC29 | faithfulness_check_budget_minutes | 40 | 10 to 120 | New (QQ16, the owner): the check stops when its next summary would not fit, and records what it skipped; home: config/judges/summary-grounding-judge.json (row #35) |
| RC30 | served_model, grounding_prompt | granite-guardian-3.3-8b-q4km, with its groundedness prompt template | any config/models file the pinned llama.cpp runtime serves, with its prompt template | New (QQ16): the checker's model and prompt, named grounding_model when QQ16 was ruled; served_model is a field any judge declaration may carry (absent: the digest's own model), so the council serves a judge's model without reading its settings (X8.4); a change starts a new series and needs the planted-fault test again; home: config/judges/summary-grounding-judge.json |
| RC31 | anchor_days | 56 | 28 to 91 | New (QQ18): the first valid days of a series whose stored scores, read from the eval ledger, form its frozen anchor; replaces long_baseline_weeks (F1.14) |
| RC32 | anchor_look_every_days | 7 | 7 to 28 | New (QQ18): how often the recent week is compared with the anchor; replaces long_window_days (F1.15) |
| RC33 | expected_shifts | empty | entries of a date, the recorded change and the metrics it is expected to move | New (QQ19): only the listed metrics start a fresh history on that date; a recorded change with no entry restarts every metric; written with the change itself, never by a person afterwards |
| RC34 | gate_min_checks | 30 | 10 to 200 | New (the rewrite, 2026-10-12): the fewest independent checks of a line's marked summaries over gate_trial_days before its agreement guard may pass (O3.13); home: config/idhazh.json evaluation.publish_gate (row #23) |
| RC35 | planted_omissions_per_night | 5 | 0 to 15 | New (the rewrite): planted variants the completeness judge aligns a night, on top of the sampled summaries (X3.7); home: config/judges/summary-completeness-judge.json (row #31) |
| RC36 | sentences_removed_per_omission | 1 | 1 to 2 | New (the rewrite): whole sentences each planted variant drops, never the title (X3.1, X3.7); home: config/judges/summary-completeness-judge.json (row #31) |
| RC37 | planted_checks_per_night | 2 | 0 to 4 | New (the rewrite): planted unfaithful variants among the grounding judge's faithfulness_checks_per_night, checked first (X7.7); home: config/judges/summary-grounding-judge.json (row #35) |
| RC38 | min_planted_caught | 0.8 | 0.5 to 0.99 | New (the rewrite): the share of a week's planted variants the grounding judge must call unsupported before its verdicts count, as promotion_min_detection is for the drift judge (X7.7); home: config/judges/summary-grounding-judge.json (row #35) |

Table RD - what the replay on the real record showed (Andre, 2026-10-11)

| # | Finding |
| --- | --- |
| RD1 | 2026-09-07: watch from 09-09 (copying up), drift from 09-12 (something_changed). Faithfulness rose because the summaries copied more; quality_worse never crossed in the 50 days (measured under the two-row design QQ8 replaced; the replay re-measures it under the signed score) |
| RD2 | 2026-09-24: drift from 09-26 on shorter summaries and more dropped hedges; part of the hedge rise is an artefact of the band-reason ranking, so the judge reads the eval-row column, never band reasons |
| RD3 | Stable nights: 0 of 8 crossed. With no change, 2.4 percent of nights cross a row, and drift is read 0.10 times a month at q 0.05 (0.03 at q 0.01) |
| RD4 | Detection over a full week: 5 percent of summaries unfaithful 1.00; 2 percent 0.72; one 10-a-day source unfaithful 0.95; unsupported numbers doubled 0.74; dropped hedges up 3 points 0.29, the weakest |
| RD5 | The pipeline changed about every 9 days, and every crossing on record traces to a dated change, so a crossing names the inputs that changed inside its window |
| RD6 | No summary metric sees extraction breaking on one source, and row #1 deletes drift.py's per-site checks; extraction_suspect was 0 on all 50 days (P34) |

## 5. Plan 36's scope, moved here on 2026-10-11

The owner moved plan 36 into this plan on 2026-10-11, because both target the quality of the digest's summaries, and deleted its file, TODO/20260918-36-summary-quality-autotune-plan.md; git history keeps it. This section is plan 36's full text, so none of its scope, rulings or rejected alternatives is lost. Read it with three rules:

- **Rows.** Plan 36's row N is this plan's row #(N + 15): plan 36 row #1 is row #16, and plan 36 row #13 is row #28 (Table D). Inside this section, "Row N" means plan 36's row N; "Row 17" in plan 36's Section 0a means plan 34's row 17.
- **Ids.** The ids in this section - D1 to D8, E1 to E10, G1 to G14, H1 to H8, J1 to J8 and plan 36's numbered decisions - are plan 36's own. Outside this section they are written as plan 36 D1, plan 36 E1 and so on.
- **Authority.** Plan 36's rulings stand as the owner and its reviewers made them, until a question in Table QQ changes one. Each of rows #16 to #28 is held until the question named beside it in Table D is ruled. Plan 36's execution stamp (execution AUTHORIZED by the owner on 2026-09-19, to begin once plan 34's fit core and plan 35's EvalRow changes were on main) and its zero-context handover are superseded by this plan's Section 0; whether that approval carries to rows #16 to #28 is QQ26, which ruled that it does not. Section 2 now holds rows #18, #22, #23, #24, #27 and #28 as the rulings rewrote them; where this section's text of those rows differs, Section 2 wins. QQ24 (2026-10-12) found that H5 and H6 no longer describe the code: coherence is scored in the daily work step that composes the eval row.

### Plan 36 - the summariser grades itself, and content decides its future

**Created**: 2026-09-18
**Depends on**: plan 34's fit core (rows 5-8) merged; plan 35's `EvalRow` churn (rows 6, 7, 8) merged
**Correction level**: 5 - a model verdict decides what a reader is shown

### Plan 36: start here - the handoff

Every summary already gets a faithfulness score (HHEM) the day it is written. That number sets a
display badge and nothing else: the item publishes whatever the badge says. This plan closes the loop
plan 34 opened for the merge line, for summary quality: measure every summary on four axes, fit a band
to each axis from its own rolling distribution with no human in the loop, and let the band decide
whether a summary publishes or is withheld - and a withheld summary is absent from the reader's day,
tracked in item-health telemetry and surfaced in the console, never a reader-facing card (section 0e).

**The one sentence that orders every decision here, taken from plan 34 and still true: withholding a
story the reader never sees is an invisible loss; publishing a weak summary is a visible, recoverable
one. Only one of those is invisible.** So the default is to publish, the only failure that withholds is
a false claim, and the floor that withholds is an absolute line that does not drift.

### Plan 36 section 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The autotune is half-built: plan 35 measures four quality axes but nothing acts on them. This fits an adaptive band to each axis and gates publication on it, mirroring plan 34's proven loop. |
| Hard scope - in | Two new contracts (`MetricScoreDistribution`, `FittedMetricBand`); three `EvalRow` columns; the fold and fit stages; the G-Eval fluency judge in the `LLM-JUDGES` council; the veto-chain publish gate (record-only, then flagged on); the console panels; a G-Eval cost measurement. |
| Hard scope - out | see table below |
| ESCALATE triggers | (1) Row 8 flips the flag and withholds items - the first change to a published day, lands alone, owner sign-off. (2) promoting any metric's action from `watch`/`downgrade` to `block` - owner, on a track record. |
| Chosen strategy | Reuse plan 34 wholesale: extract its fit core direction-parameterised, mint data-parameterised per-metric contracts, host G-Eval on the existing `LLM-JUDGES` workflow, ship the gate record-only behind a flag. Owner + convergence debate, 2026-09-18. |
| Execution | AUTHORIZED (owner, 2026-09-19); begins once plan 34's fit core and plan 35's EvalRow churn are on main. Parallel N = 4; the running-pool orchestration + 9-PR wave grouping is section 0d Table B. |
| Intent | Every summary is measured on four axes; an adaptive band is fit to each from its own rolling distribution with no human in the loop; and the band decides whether a summary publishes or is withheld - a withheld item is absent from the reader's day and recorded as an item-health metric surfaced in the console (section 0e). The contracts each row names FOLLOW this intent; when a contract and the intent disagree, the contract changes, not the intent (CLAUDE.md 0d). |

#### Plan 36: Onboarding (cold start - read these first, zero context assumed)

A worker picks up any row with no prior context by reading, in order: [`CLAUDE.md`](../CLAUDE.md) (the
engineering contract), [`docs/how-to/execute-a-plan.md`](../docs/how-to/execute-a-plan.md) (how this plan
runs), [`docs/agents/bootstrap.md`](../docs/agents/bootstrap.md) (which page owns the surface a row
touches), and [`docs/how-to/run-the-gates.md`](../docs/how-to/run-the-gates.md) (the gate commands). The
design of record is [`docs/architecture/publishing/autotune-summary-quality.md`](../docs/architecture/publishing/autotune-summary-quality.md)
(the four metrics, the fold-fit loop, the publish gate). The loop this plan mirrors is the adaptive
merge line in [`docs/architecture/publishing/autotune-content-similarity.md`](../docs/architecture/publishing/autotune-content-similarity.md)
- Row 1 extracts its fit core from `backend/idhazh/similarity/fit.py`. Owning pages per surface:
contracts + schema versioning ->
[`docs/architecture/contracts/schemas.md`](../docs/architecture/contracts/schemas.md); evaluation + the
console -> [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md). Every row's `Files touched`
is the exact surface; every persisted change stamps its schema `version` + `changelog` (CLAUDE.md 11).

#### Plan 36: Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| A composite/normalised single score as the gate | No one "quality number" to gate on | Never for the gate - it dilutes the one reliable signal and erases which axis fired (veto chain instead). A displayed "overall" is Row 7's optional console convenience |
| Blocking on coverage, coherence or fluency | Only faithfulness can withhold | A calibration showing that metric's low tail means "bad" and the owner promoting its action to `block` |
| An adaptive percentile as the BLOCK floor | The block binds to the absolute HHEM 0.50 that already ships | Never - a percentile floor drifts up as the summariser improves and silently deletes fine stories |
| A human holdout set (plan 34 has one) | No hand-marked drift alarm | Nothing - plan 34's holdout was its only floor; plan 36's absolute floors replace it, and the record-only corpus turn is the go/no-go |
| Human quality labels for calibration | Bands are set from each metric's own distribution | The owner's standing "no human labour" rule forbids it; distributional bands self-correct |

#### Plan 36 section 0a - what plan 34 taught, and what transfers

Plan 34 built the same loop for the merge line. Every load-bearing piece transfers; the table is the map.

| Plan 34 pattern | Transfers to plan 36 as | Change |
| --- | --- | --- |
| `StorySimilarityDistribution` - fixed-size 120-slot record, folded daily, never grows (Guardrail #12) | `MetricScoreDistribution` - one per metric | Add a `metric` enum; data-parameterised |
| `FittedSimilarityThreshold` - per-day row, proposed/damped/applied, gates, clamp, `held_reason` | `FittedMetricBand` - one per metric per day | Add a `metric` enum; two floors (block, watch) not one line |
| The fit: walk slots from the TOP (NO verdicts), `discard_share`, the `+ bin_width` boundary | The fit: walk from the BOTTOM (low scores) | One direction parameter; the boundary rule is identical and load-bearing |
| One-directional damping: the risky move is damped, the safe move lands at once | Same invariant | The risky move is RAISING the floor (withhold more = invisible deletion), so the raise is damped |
| `enabled` flag ships off; the "Apply" row is the first that changes a published day; everything before writes numbers nobody reads | Same | Row 8 is the Apply row; it lands alone |
| Record-only first: stamp what WOULD happen for a corpus turn before acting | Same | Row 7 stamps `publish_decision` counterfactually; a person reads it once as go/no-go |
| The `LLM-JUDGES` daily workflow hosts the judge; reads committed data, never article bodies | Hosts G-Eval fluency as another leg | Fluency is summary-only, so committed `digest.json` is enough |
| Held reasons, min-days/min-samples gates, settle test, step-change guard | Same, per metric | Faithfulness seeds from committed history, so its gates clear on day one |
| Row 17 measures a real judge call before trusting the leg budget | Row 10 measures a real G-Eval call | Same discipline |
| The console draws the loop on `/console/judgement/` | Adds the quality panels beside the merge panels | Same route |

#### Plan 36 section 0b - the converged design (owner + debate, 2026-09-18)

| # | Decision | Ruling | Authority |
| --- | --- | --- | --- |
| D1 | Instrument all four, or just gate faithfulness? | All four get the full fold/fit/band. The ACTION on crossing is a per-metric config knob: `block` / `downgrade` / `watch`. Fully instrumented; the default action is conservative and promotable. | owner, Andre |
| D2 | Which metric may withhold? | Faithfulness only. A false claim is the one failure where no story beats the story. Coverage and coherence are confounded (reward extractive / reward repetition), so their low tail can be a GOOD summary - default `watch`. Fluency is next-day, so it structurally cannot gate - `watch`. | Andre, Editor |
| D3 | Block floor: absolute or adaptive? | BLOCK on the absolute reader-safety lines that already ship and do not drift: HHEM 0.50 and unsupported-number. The adaptive p01/p05 bands DOWNGRADE (faithfulness) or WATCH (others), never block, until the owner promotes one. | Andre, Editor |
| D4 | A composite score for the gate? | No. Veto chain, like `verdict()`. Averaging dilutes HHEM with confounded signals and erases which axis fired (`doubt-reasons.ts`). A displayed "overall" is console convenience that feeds no action. | Andre, Fowler |
| D5 | Sane defaults with no human labels? | Faithfulness seeds its band from p01/p05 of the ~6,966 committed HHEM readings, filtered to the current `scorer_version`. Coverage/coherence/fluency are record-only until their distribution fills (~5-10 days), then `downgrade`/`watch`. | Andre |
| D6 | Damping direction | Damp the RAISE, drop at once: raising a floor withholds/marks more, which is the invisible-deletion direction. Same invariant as plan 34. For a `downgrade` band the asymmetry is weaker (a marker is visible), so the first fortnight measures whether the direction should differ per action. | Andre |
| D7 | Human holdout? | Killed. Plan 34's holdout was its only floor; the absolute block floors replace it. The safety net is the record-only corpus turn a person reads once before the flag flips - reviewing output, not producing labels. | Fowler |
| D8 | Withhold rate | WATCHed. A thin-but-true digest beats a full-but-false one, but a rising withhold rate is a bad-summariser day an operator must see, not a digest silently going hollow. | Editor |

#### Plan 36 section 0c - critical-review corrections (2026-09-18)

The 2026-09-18 critical review (Andre, Carmack, Fowler, Editor, each verified against the committed
code and the 11,140-row ledger) reshaped the gate. These supersede the 0b rows they cite. Two are owner
decisions (E4, E6) and gate their rows.

| # | Correction | Supersedes | Authority |
| --- | --- | --- | --- |
| E1 | **All adaptive floors are WATCH-only (fleet-rate alarms), none downgrades per item.** Measured: faithfulness p05 = 0.14, but the absolute block 0.50 sits at the ~11th percentile, so the adaptive faithfulness floor is BELOW the block and the "downgrade" band is empty by construction - it can never fire. The only per-item faithfulness reader action is the absolute 0.50 block plus the EXISTING 0.80/0.50 display bands. | D1, D3 | Andre (A2) |
| E2 | **The seed keys on the HHEM instrument sub-identity** (`hhem_rev@rev + weights_digest + window=900/150/anchored`), NOT the whole `scorer_version`. Plan 35 changes `scorer_version` (drops `;lead=`, bumps `metrics-3`->`4`), so a whole-version filter matches 0 of 11,140 rows and day one is empty. Keying on HHEM identity keeps ~8,461 current-geometry rows. | D5 | Andre (A1) |
| E3 | **Symmetric damping for every watch floor.** "Damp the raise" belonged to plan 34's INVISIBLE-deletion trigger; here the withhold is absolute and undamped, and a watch/downgrade floor is a visible/operator signal, so asymmetric damping only ratchets the alarm down under noise and silences it. Resolve now, not after a fortnight. | D6 | Andre (B1) |
| E4 | **SUPERSEDED by 0e H1 (2026-09-19): the reader sees nothing; the withhold is an item-health metric, not a card.** Historical rationale (no longer in force): the Editor proposed degrading a below-0.50 item to a link-only card so the loss stayed visible; the owner instead ruled the item ABSENT from the day and the signal an operator-only item-health metric surfaced in the console. | D2, D8 | Editor proposed; superseded by owner (0e H1) |
| E5 | **State the ~11% steady-state withhold rate; add a length pre-filter.** The 0.50 line is the ~11th percentile, so Row 8 withholds (does not publish) ~11% of items every day, and 24% of that tail is sub-200-word stubs. A length pre-filter (never summarise a stub) and the stated baseline keep D8's alarm from reading 11% as an anomaly. | D8, Row 8 | Andre (B2), Editor |
| E6 | **SUPERSEDED by 0e H5 (2026-09-19): no 3-model peak - coherence runs in `assemble`, not the `work` shard.** Verified: MiniLM is already loaded in the `plan`/`assemble` jobs (it builds the search index) and the summariser is NOT resident there, so coherence scores in `assemble` reusing the loaded MiniLM - summariser + HHEM + MiniLM never coexist in one process. Historical concern (no longer in force): that coherence would be a third resident model on the busy `work` shard. | Row 8 (35), Row 11 (36) | Carmack; corrected by owner (0e H5) |
| E7 | **Where the block lands: BEFORE `collapse_same_story`.** Withdrawing a same-story group's representative after the fold silently deletes every duplicate folded into it and trips `DigestDay`/placement count invariants. Drop/relegate before the fold so the next-best duplicate is promoted, and recompute run/vertical/desk counts. `DigestDay`'s `planned = published + failed` gains a `link_only` term (`planned = published + failed + link_only`), counted on `RunManifest`, with a test that the arithmetic closes. **(The `link_only` DigestDay term is SUPERSEDED by 0e H3: it is dropped - a withheld item counts in `failed`, so `published + failed <= planned` already holds and `digest_day.py` is untouched. The `collapse_same_story` placement above still applies.)** | Row 8 | Fowler (A1, B5) |
| E8 | **The daily judge workflow may be renamed `LLM-JUDGES` -> `LLM-COUNCIL`.** The plan declares ONE dependency line and uses name-agnostic prose ("the daily judge council workflow") everywhere; the runtime (cache key, server start, matrix) is name-independent, so a rename touches only `name:`, `concurrency.group`, and the `_harness.py` expectation in one commit. | 0a, Row 6 | Fowler (B2), Carmack (A6) |
| E9 | **Row 6 (G-Eval leg) depends on Row 10 (measure the call)**, or the leg timeout is a labelled estimate x generous margin - do not repeat plan 34 row 17's sequencing gap. G-Eval is a STEP inside the existing judge legs (reuse the hot server), not a new job. It is monitor-only and feeds no gate (delete-first justification: an operator drift alarm). | Row 6, Row 10 | Carmack (A3, A5), Fowler (C1) |
| E10 | **Two guards to add.** (a) REVISED by 0e J6/J7 (2026-09-19): the corpus is NO LONGER byte-identical gate-off vs gate-on - Row 12 fences withheld items out of the corpus on purpose. The anti-Goodhart guard is instead that the fence reads the stamped `publish_decision` (not `hhem`) and `keeps_its_counterweights` stays faithfulness-free; the rejects ledger makes the fence auditable. (b) The G-Eval canary asserts CONTAINMENT (`geval` never reaches `publish_decision`) and that thinking is off, not just that the grammar parsed. | Row 8, Row 12, Row 6/10 | Andre (B3, B4); owner (J6/J7) |

Also corrected: the committed HHEM count is 11,140 (8,461 at the current instrument identity), not ~6,966
(E2); the design-of-record doc's remaining "block p01" phrasing is reconciled to the absolute-0.50 block
in the same commit as Row 5.

#### Plan 36 section 0d - round-2 restructure (Fowler + Carmack, 2026-09-18)

The rows were written against 0b (D1-D8) and never reshaped to absorb the 0c corrections (E1-E10). Two
custom agents verified against the tree: most E-items float in 0c with no row owning them, and the
single biggest hole is that **E4 turned "withhold" into a link-only CARD but no row builds it** - Row 8
still says a withheld item "is absent". These corrections bind the rows and add **Row 11**. (Section 0e,
2026-09-19, later REVERSED the E4 link-only card that G1/G2/G3 describe and repurposed Row 11 - read 0e
first; the link-only references in this section are historical.)

**Table A - corrections-to-rows (each floating E-item and gap now has an owner)**

| id | Correction | Owner row | What the row must now do |
| --- | --- | --- | --- |
| G1 | **E4 link-only card has no builder (the critical hole).** | NEW Row 11 | Build the reader-facing card: add published `DigestViewItem.link_only` (bool, default false) + `withheld_reason` (nullable); the `ITEM_FIELDS` allow-list in `frontend/src/lib/payload/project.ts`; a card component (headline + source + "we could not verify our summary" marker, NO summary); a browser smoke. Ships INERT (field false until Row 8). Level-5 additive published contract. |
| G2 | E7 placement (the DigestDay `link_only` term is SUPERSEDED by 0e H3). | Row 8 | Drop/relegate a withheld item BEFORE `collapse_same_story` ([assemble.py:2038](../backend/idhazh/assemble.py)) so the next-best duplicate promotes; recompute run/vertical/desk counts. The `DigestDay` `link_only` term + validator rewrite are DROPPED by 0e H3 - a withheld item counts in `failed`, so `published + failed <= planned` holds and `digest_day.py` is untouched. |
| G3 | E4 makes Row 8's gate self-contradict ("a withheld item is absent"). | Row 8 | The integration gate asserts the withheld item is PRESENT as a link-only card WITHOUT a summary, not absent; Row 8 writes `link_only=true` + `withheld_reason` using Row 11's field. |
| G4 | E5 length pre-filter + the ~11% baseline float. | Row 8 | Add a length pre-filter (never summarise a sub-200-word stub); state the ~11% steady-state link-only baseline so D8's alarm does not read 11% as an anomaly. |
| G5 | E10(a) corpus-harvest test. **REVISED by 0e J6/J7:** the fence (Row 12) excludes withheld items from the corpus, so byte-identity gate-off-vs-on no longer holds. | Row 12 | Integration test: an item stamped `publish_decision == withheld` is excluded by `harvest_rows`, and `keeps_its_counterweights` is unchanged (still reads no `hhem`) - the fence reads the decision, not the score. |
| G6 | E1 all floors WATCH-only; the per-item downgrade band is empty by construction. | Rows 2, 5, 7 | Drop the per-item `downgrade` action; faithfulness's only per-item reader action is the absolute 0.50 block + the existing 0.80/0.50 display bands. Keep the `downgraded` enum value ONLY as a reserved future-promotion member said so on the field, or drop it (G12). |
| G7 | E2 seed keys on the HHEM instrument sub-identity, not `scorer_version`. | Rows 4, 5 | Row 4 folds faithfulness by the HHEM sub-identity (`hhem_rev@rev + weights_digest + window=900/150/anchored`), not the whole `scorer_version` (plan 35 changes it -> 0 of 11,140 match). Row 5 seeds from that key. |
| G8 | E3 symmetric damping floats. | Row 5 | Row 5 dec 2 + oracle: symmetric damping for every watch floor (the withhold is absolute+undamped; a watch floor is an operator signal, so asymmetric damping only ratchets the alarm down under noise). |
| G9 | Row 5 seed is a growing read + a test that walks committed data. | Row 5 | The production seed declares Guardrail #12's escape-hatch (what it reads, why a bounded input cannot answer); the seed TEST uses a bounded fixture, never the committed archive (section 13); cite the PROPERTY ("rows at the current HHEM identity"), never the rotting cardinal 8,461. |
| G10 | E6 coherence 3-model RAM. **SUPERSEDED by 0e H5 (2026-09-19): no peak - coherence runs in `assemble` where MiniLM is already loaded.** | Rows 4, 5, 11 | Row 11 confirms coherence is wired into `assemble` (not the `work` shard) and takes one cheap RSS reading; no eviction, no timeout bump. Coherence is same-day (in `assemble`, after `work`); its action stays `watch` (never gates). |
| G11 | E8 rename touch-points; E9 Row 6/10 sequencing. | Rows 6, 10 | If the `LLM-COUNCIL` rename lands, Row 6 edits only `name:`, `concurrency.group`, `_harness.py`. Row 6's leg timeout is a LABELLED estimate x generous margin and does NOT hard-block on Row 10 (E9); Row 10 measures the merged call after. E10(b): Row 6 canary asserts containment (`geval` never reaches `publish_decision`) + thinking off. |
| G12 | Row 3 dec 1 stale premise; the `downgraded` dead value. | Row 3 | Fix dec 1: a withheld item is ABSENT from the day but recorded in item-health telemetry (0e H1/H2); the `EvalRow` stamp still records every scored item including the withheld. Resolve `publish_decision`: values are `published` \| `withheld`; keep `downgraded` only if reserved for a named future promotion, else drop. |
| G13 | Row 2 omits the contract fixtures + `export.py` tuple. | Row 2 | Name `tests/fixtures/contracts/<stem>/` fixtures for both new contracts and the `CONTRACTS` tuple + import in `export.py`. |
| G14 | The design-of-record doc lags the corrections. | Row 5 + Row 8 commits | Widen the reconciliation: `docs/architecture/publishing/autotune-summary-quality.md` drops the faithfulness-downgrades-below-adaptive-floor language (E1), the `block p01` phrasing, and the asymmetric "damp the raise" (E3); the publish-gate section says withhold = absent + item-health telemetry, surfaced in the console (0e H1/H2/H4), NOT a link-only card. |

**Table B - PR-wave grouping (11 PRs across 4 waves; each PR independently green)**

| PR | Wave | Rows | Ships as / why grouped | Depends on |
| --- | --- | --- | --- | --- |
| fit-core | 1 | 1 | pure refactor; plan-34 tests are the oracle | 34 fit on main |
| eval-columns | 1 | 3 | expand-only EvalRow width; `merge=union` carve-out (lands on main before any writer, never branch-stacked) | 35 EvalRow on main |
| metric-fold-fit | 2 | 2, 4, 5 | all edit `ledger/__init__.py` + share the two new contracts; fold-before-fit; inert until Row 8 | fit-core, eval-columns |
| geval-leg | 2 | 6 | disjoint island (`quality/geval.py` + the council workflow) | eval-columns |
| publish-gate | 3 | 7 | backend veto chain, record-only, stamps `EvalRow` | metric-fold-fit |
| geval-measure | 3 | 10 | MEASURES -> runs alone (`measure.yml` on a clean runner) | geval-leg |
| coherence-place | 1 | 11 | confirm coherence runs in `assemble` (MiniLM already loaded there); one cheap RSS reading; no peak, no eviction, no timeout bump (0e H5-H7) | 35 coherence scorer |
| console-panels | 3 | 9 | frontend island on `/console/judgement/`; + the not-published/withhold panel from item-health (0e H4) | metric-fold-fit, publish-gate |
| apply-gate | 4 | 8 | ESCALATE, owner sign-off, first published-day change; withhold = absent + item-health (0e H1-H3, E7 placement) | publish-gate |
| rejects-ledger | 3 | 12 | the `state/rejects/` ledger + its prune verb + the corpus fence; reads the stamped `publish_decision` (0e Table C) | publish-gate |
| plan34-gaps | 4 | 13 | retro plan-34 latent gaps (space-trap re-set, thinking-variant, injection live-test note); the space-trap guard is shared with Row 6's G-Eval | 34 landed, geval-leg |

**Peak pool width 2** (Carmack): Rows 1 and 3 are TWO co-roots from t0, not one width-1 head. The serial
spine is `1 -> 2 -> 4 -> 5 -> 7 -> 8` (6 deep); the width-1 point is the TAIL (Row 8), by owner mandate.
Provision 2 workers; `Parallel N = 4` never binds.

**Table C - optimistic-dispatch rule (the CI-idle fix)**

| Edge class | Dispatch base | Why |
| --- | --- | --- |
| Disjoint (1 vs 3; 4 vs 6; 5 vs 10; 11 vs 8) | `origin/main`, at once | no shared file (Row 11 is a backend measure utility, Row 8 is `assemble.py`) |
| Shared-file, shape settled + mechanical (1->2 once `ClampOutcome`/`FitEnd` settle; 4->5 once the `ledger/__init__.py` helper settles) | predecessor's BRANCH tip, pre-merge | shape cannot move; pool never idles on CI |
| New persisted contract (2->4/5/7) | wait on `main` | the contract shape is exactly what review moves; fold/fit WRITE it |
| Measuring (6->10) | wait on `main` | Row 10 must call the merged `geval.py`; runs alone anyway |
| ESCALATE / Level-5 (7->8) | wait on `main` + owner sign-off | first change to a published day; lands alone |
| EvalRow width vs the external plan-35 widening | HARD wait on `main` (never optimistic) | `state/scores` is `merge=union`; two open widenings stack silently. After any EvalRow merge, census committed shards for a stacked header. |

#### Plan 36 section 0e - owner rulings, 2026-09-19 (supersede 0d G1/G2/G3, refine E6/G10)

The owner reversed the E4 link-only card and set the coherence-RAM approach. User approval supersedes
the Editor's link-only recommendation and every advisor (CLAUDE.md section 0).

**Table A - the withhold surface (supersedes E4, G1, G2, G3)**

| id | Ruling |
| --- | --- |
| H1 | **A withheld item is NOT published - it is ABSENT from the reader's day.** No link-only card, no reader-facing surface. Row 11's link-only card is RETIRED. Rationale: a below-0.50 faithfulness says our prose is untrustworthy; the reader sees nothing rather than a card, and the signal lives on the operator surface. |
| H2 | **The withhold is a METRIC in item-health telemetry.** A withheld item is `ItemOutcome.failed` with a NEW `FailureCode` member (the summary was written but failed the faithfulness floor) + the `detail`. "Expand columns are necessary" - the enum member is that expansion. The item-health census already feeds the console, so the metric ships with no new persisted reader surface. |
| H3 | **Row 8 simplifies.** The `DigestDay` `link_only` arithmetic term (old G2) is DROPPED - a withheld item counts in `failed`, so `published + failed <= planned` already holds and `digest_day.py` is not touched. The E7 "drop BEFORE `collapse_same_story`" placement STILL applies (promote the next-best duplicate). |
| H4 | **The console surfaces the signal (Row 9).** A not-published/withhold panel on `/console/judgement/` reads item-health: the withhold count, the ~11% baseline (E5), and the reason breakdown by `FailureCode` - the operator's view of what the gate withheld and why. |

**Table B - coherence placement: no 3-model peak (owner + verified, 2026-09-19; supersedes the earlier eviction design)**

| id | Ruling |
| --- | --- |
| H5 | **No 3-model peak: coherence runs in `assemble`.** MiniLM is already loaded in the `plan`/`assemble` jobs to build the search index, and the summariser is NOT resident there (it lives only in the `work` shard, with HHEM). So coherence scores in `assemble`, reusing the loaded MiniLM - summariser + HHEM + MiniLM never coexist in one process. The sequential-eviction machinery the earlier design feared is unnecessary. |
| H6 | **Row 11 collapses to a confirmation.** It confirms coherence is wired into `assemble` (not the `work` shard, plan 35 Row 8) and takes one cheap RSS reading in `assemble` (MiniLM + the ROUGE work) to show it fits with headroom. No server-stop step, no two-phase `work` shard, no eviction. |
| H7 | **The 200 -> 220 shard-timeout bump is RETIRED** - it existed only for the two-pass `work` shard, which is gone. `assemble` absorbs coherence's ~0.16 s/item (a few tens of seconds over a day). Keep a timeout bump only if a separate measurement asks for it; it is not part of this plan. |

**Table C - the rejects ledger (owner, 2026-09-19; adds Row 12)**

| id | Ruling |
| --- | --- |
| J1 | **Persist every withheld summary for troubleshooting.** Today a withheld summary's TEXT survives nowhere committed (only the discarded run intermediate); the `EvalRow` keeps the scores + a one-way hash, not the prose - so the gate deletes ~11% of items daily and erases its own evidence. Row 12 adds a committed, fully-sharded ledger: `state/rejects/<YYYY>/<MM>/<DD>/<item_id>.json`, one `RejectRow` per withheld item. |
| J2 | **What the `RejectRow` carries** (for a person or a bigger model to judge later, never a reader): `title`, `summary` (the failing prose), `source_text` (the sanitised extract the model read), `prompt` (the rendered system + user turns), the failure (`hhem`, `withheld_reason`, `band`, `scorer_version`), the summariser fingerprint (model + decode), identity (`item_id`, `url_key`, `canonical_url`, `source_id`), provenance (`version`, `generated_at`, `run_id`). |
| J3 | **Source text is committed here - a second carve-out beyond `corpus/` (CLAUDE.md 0a).** The owner authorised it (2026-09-19); the executing PR amends 0a to write BOTH carve-outs - the `corpus/` one (today only cross-referenced from section 8) and `state/rejects/` - so 0a becomes the canonical list (S5 A1). It is sanitised extract (crossed the trust boundary once at extraction, Guardrail #11), stored as data a person or an offline judge reads - never re-fed to a model as instruction. Bounded by J4. |
| J4 | **Prune prose and source together, tightly: 30 days, config-driven.** A new knob (`finetune.reject_window_days`, default 30 - tighter than the corpus's 60) + its own verb (`retention.prune_rejects`) wired into the retention prune, deleting whole day directories past the window; the history bytes ride `prune.yml`'s force-push on the same schedule. |
| J5 | **Never served.** `state/rejects/` stays unwired from `payload.ts`, the telemetry projection, the embed/index input, and the `DigestViewItem`/`ITEM_FIELDS` allow-list. The console (Row 9) plots only the aggregate - the rate, the reasons, the withheld-tail score distribution - never the prose or the source. |
| J6 | **Fence the corpus: never train on a withheld summary.** The harvest reads `items/` directly ([corpus.py:217](../backend/idhazh/corpus.py)), so a withheld summary IS harvested today. Row 12 skips any `Scored` whose `EvalRow.publish_decision == withheld`, placed BEFORE `keeps_its_counterweights` - reading the stamped DECISION, not the raw `hhem`, so `keeps_its_counterweights` stays faithfulness-free (Andre's anti-monitor-selector rule holds). |
| J7 | **This inverts E10(a) on purpose, and the ledger is the safety net.** E10(a) pinned "corpus byte-identical gate-off vs gate-on"; the fence deliberately breaks that (do not train on what we blocked). The Goodhart risk - training only on high-HHEM prose teaches the model to game HHEM - is mitigated because the ledger makes the fence AUDITABLE: a bigger model or a human reads the withheld tail offline and confirms the floor catches real failures rather than deleting good summaries. E10(a) + G5 + Row 8's gate are revised to match. |
| J8 | **Replaces the "extend the human label draw" idea.** That would feed withheld items back into the live label queue and muddy the distribution-based autotune (owner). Instead the ledger is the substrate for offline judging (bigger model or human), never reader-facing; the label queue is untouched. |

Note: `state/rejects/` is committed, so the withheld prose lives in the repository (not the digest, not
the Pages site). If the repository is public it is browsable there for the 30-day window; the prune +
`prune.yml` force-push bound it. The owner accepts this to have a committed, queryable ledger rather than
an expiring CI artifact - revisit if the repository's visibility changes.

TODO (a note, not a plan row; distils to `docs/` per distill-a-plan.md): the OFFLINE JUDGE that reads
the rejects ledger - a bigger model or a person auditing the withheld tail (J7/J8) - is a deferred
follow-up with no row in this plan. When this plan distils it moves to
`docs/architecture/publishing/autotune-summary-quality.md` as the named future consumer that makes the corpus-fence
auditable.

### Plan 36 section 1 - Status Reckoner

Every plan 36 row was PENDING on 2026-10-11, and none had started. The rows now sit in this plan's Table D as rows #16 to #28, with plan 36's dependencies renumbered and the question that holds each.

### Plan 36 section 2 - Row detail

#### Plan 36 row #1 - extract the fit core, direction-parameterised (plan 65 row #16)

- **Scope:** move plan 34's fit arithmetic into a neutral, contract-free logic package both plans call,
  parameterised on which tail it walks. Behaviour-preserving for plan 34.
- **Files touched:** new `backend/idhazh/fitting/edge.py` (imports stdlib only; takes a `Sequence[int]`
  of cost-counts, the band edges, `bin_width`, `previous`, the knobs; returns plain values and a frozen
  `ClampOutcome`); `backend/idhazh/similarity/fit.py` becomes a thin adapter (Distribution -> primitives
  -> core).
- **Acceptance gates:** plan 34's `backend/tests/test_similarity_fit.py` stays byte-for-byte green;
  new unit tests drive `edge.py` with both `FitEnd.TOP` and `FitEnd.BOTTOM` primitives.
- **Oracle:** for a built count array, `FitEnd.TOP` returns the upper edge plan 34 returns and
  `FitEnd.BOTTOM` returns the lower edge; it cannot settle whether the quality direction is
  semantically right (that is Row 5 against real scores).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Extract at the second user; the `+ bin_width` boundary is a reader-facing correctness invariant, so rule-of-three yields | Fowler |
  | 2 | Direction is one parameter (`FitEnd`), so a caller cannot mismatch walk and returned edge | Fowler |
  | 3 | `ClampKind` stays a per-Band wire enum; the core returns a neutral `ClampOutcome.kind` each adapter maps | Fowler |

#### Plan 36 row #2 - the two contracts + the per-metric knob block (plan 65 row #17)

- **Scope:** `MetricScoreDistribution` (fixed-size, one file per metric) and `FittedMetricBand` (one
  row per metric per day), both carrying a `metric: MetricId` enum, plus a per-metric `MetricBandConfig`
  knob block, `enabled` off. Nothing reads or writes them yet.
- **Files touched:** `backend/idhazh/contracts/metric_score_distribution.py`,
  `backend/idhazh/contracts/fitted_metric_band.py` (declares `MetricId`, `ClampKind`, `HeldReason`,
  `MetricAction`), `backend/idhazh/contracts/knobs/evaluation.py` (the `MetricBandConfig` block),
  `backend/idhazh/contracts/export.py` + regenerated schemas, `backend/idhazh/ledger/__init__.py` (paths),
  committed seed distributions, `config/idhazh.json`, `config/appearance.json` if a console knob lands.
- **Acceptance gates:** contract drift gate; contract tests over the validators (band divides into
  slots, slot count matches, a date folds once - the plan 34 shapes); a fresh clone runs on the
  defaults with `enabled` off.
- **Oracle:** a fitted band without its two floors, or a distribution whose slots miss the grid, is
  refused; it cannot settle whether the seeded faithfulness floor is a good number (Row 5).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | One Distribution + one Band contract, data-parameterised by `metric`; adding a metric is an enum member + a config block, not a new contract | Fowler |
  | 2 | One file per metric under `state/summary-quality/<metric>/`, so the fold-once guard and the input-change archive fire per metric | Fowler |
  | 3 | `MetricAction` is `block`, `downgrade`, or `watch`; the knob's default is `block` for faithfulness, `watch` for the rest (D2) | Andre, Editor |
  | 4 | The band carries two floors - a block floor and a watch floor - not one line (D3) | Andre |

- **Rejected alternatives:**

  | # | Option | Why rejected | What it would cost to take | Authority |
  | --- | --- | --- | --- | --- |
  | 1 | One shared distribution file for all four metrics | Couples their cadence; a single archive-on-input-change would reset all four when one scorer moves | - | Fowler |
  | 2 | A `scored-pairs`-style per-item tree | Per-item scores already persist in `EvalRow`; a second copy is a second answer | - | Fowler |

#### Plan 36 row #3 - `EvalRow`: the three new columns (plan 65 row #18)

- **Scope:** add `geval` (fluency 0-1, nullable), `publish_decision` (`published`|`withheld`, default
  `published`; `downgraded` is a RESERVED future-promotion value that nothing stamps today - E1 makes the
  per-item downgrade band empty, G6/G12), `withheld_reason` (a `MetricId`-or-`unsupported_number` enum,
  nullable) to the committed eval ledger. Expand only; nothing writes the decision yet.
- **Files touched:** `backend/idhazh/contracts/eval_row.py` (+ schema + changelog + version), the
  read-side tolerance for old shards, the affected tests.
- **Acceptance gates:** contract drift gate; a fixture read of an old shard that omits all three columns
  (defaults on read); no positional CSV reader exists (header-keyed).
- **Oracle:** an old `state/scores` row without the columns validates and reads back `published`; it
  cannot settle whether the gate ever writes `withheld` (Row 7).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The stamp lives on `EvalRow`, not the published item: a withheld item is ABSENT from the day, so it cannot be stamped there, and `EvalRow` records every scored item including the withheld | Fowler |
  | 2 | `hhem` exists; `coherence`/`semantic_coverage` were added by plan 35 row 8; plan 36 only adds `geval` + the two decision columns | Fowler |
  | 3 | There is no `coverage` column to fold. Plan 35 row 7 retired it into `DROPPED_CELLS` (it measured the survival of the article's opening, on a different scale), so row 8 named the new one `semantic_coverage` rather than reuse a name committed shards already carry meaning something else | plan 35 row 8, Fowler |

#### Plan 36 row #4 - the fold (plan 65 row #19)

- **Scope:** read one committed day's `EvalRow`s and fold each metric's scores into that metric's
  fixed-size distribution, one slot each, dropping nothing. Archive and restart a distribution when its
  scorer version, band edges or slot width moved (plan 34's `inputs_changed`).
- **Files touched:** new `backend/idhazh/quality/fold.py`, `backend/idhazh/stages/quality_fold.py`,
  `backend/idhazh/ledger/__init__.py` (append/load for the distribution).
- **Acceptance gates:** unit tests over a built day of `EvalRow`s and a built distribution; a fold of a
  date already folded raises; a moved `scorer_version` archives and restarts.
- **Oracle:** a score lands in the slot whose edge it clears, and a re-fold of one date is refused; it
  reads one named day file, never the ledger tree (Guardrail #12).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The fold reads `EvalRow` one day at a time by date, never the whole ledger | Fowler, Carmack |
  | 2 | Faithfulness folds only rows under the current `scorer_version` (D5), so p01 is not a mixture artefact | Andre |

#### Plan 36 row #5 - the fit (plan 65 row #20)

- **Scope:** for each metric, walk its distribution from the low tail and write a `FittedMetricBand`
  row: the block floor (absolute, from config), the watch floor (adaptive p05, damped/clamped/gated),
  and the held reason on a day nothing moved. Seed faithfulness from committed HHEM history so its
  gates clear on day one.
- **Files touched:** new `backend/idhazh/quality/fit.py` (the second `edge.py` adapter),
  `backend/idhazh/stages/quality_fit.py`, `backend/idhazh/ledger/__init__.py`, a seeding step that reads the
  committed HHEM readings once, and **`docs/architecture/publishing/autotune-summary-quality.md`** (G14) - strike the
  four stale phrases: faithfulness-downgrades-below-an-adaptive-floor (E1), `block p01` (E1), the
  asymmetric "damp the raise" (E3), and any "coherence runs same-day in the work shard" wording
  (coherence runs in `assemble`, 0e H5).
- **Acceptance gates:** unit tests over built distributions per metric; the seed test builds the
  faithfulness distribution from committed readings and asserts its floors are non-null on day one;
  each gate writes its own `held_reason` and moves nothing.
- **Oracle:** the watch floor is the lower edge of the slot the low-tail walk stopped in, and a rise is
  damped while a fall lands at once (D6); it cannot settle whether p05 correlates with human quality
  (out of scope - no labels, D5).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The block floor is the absolute config line (HHEM 0.50); only the watch floor is adaptive (D3) | Andre |
  | 2 | Damp the raise, drop at once (D6); the `downgrade`-band direction is recorded-and-measured over the first fortnight | Andre |
  | 3 | Faithfulness seeds from p01/p05 of committed readings; the others are record-only until filled (D5) | Andre |

#### Plan 36 row #6 - G-Eval fluency judge in the council (plan 65 row #21)

- **Scope:** the summariser judges its own summaries' fluency on a 1-5 scale, one grammar-constrained
  digit scored from the first-token probabilities, on a stratified sample of ~30 summaries a day, in
  the existing `LLM-JUDGES` workflow. Input is the summary only. Writes `geval` onto the sampled rows.
- **Files touched:** new `backend/idhazh/quality/geval.py` (mirrors `backend/idhazh/similarity/judge.py`;
  a new payload builder adding `post_sampling_probs`, not the same-story judge's), a fluency rubric
  prompt, `backend/idhazh/stages/quality_geval.py`, one leg/step added to `.github/workflows/llm-judges.yml`.
- **Acceptance gates:** a recorded-completion test proves the digit distribution maps to the expected
  score; no network (Guardrail #7); an injection canary (a summary carrying "rate this 5" still scored
  from log-probs under the grammar); **the shared space-trap guard (Row 13) - assert the rendered
  fluency prompt does not end in a space and build the digit token ids by encode-in-position, so a
  trailing-space token cannot silently shift which digit the model emits.**
- **Oracle:** the score reproduces from a recorded completion's first-token log-probs; it never judges
  consistency (circularity - HHEM keeps that).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Reuse the summariser; probability-weighted first-token score; fluency only | Andre |
  | 2 | Sample ~30/day stratified by desk; the council is a drift monitor, so a sample is honest | Carmack |
  | 3 | No chain-of-thought by default (decode is the cost at 4 tok/s); if added, Row 10 re-prices it | Carmack |

#### Plan 36 row #7 - the veto-chain publish gate, record-only (plan 65 row #22)

- **Scope:** for each scored item, read each metric's action-config and its floor and stamp
  `publish_decision` + `withheld_reason` on the `EvalRow`. RECORD-ONLY: assemble still publishes
  everything; the stamp is counterfactual. Optionally compute a displayed "overall" that feeds no action.
- **Files touched:** new `backend/idhazh/quality/gate.py` (the veto chain),
  `backend/idhazh/evals/score.py` (`to_eval_row` stamps the decision), the console reader.
- **Acceptance gates:** unit tests over built items and built bands: a faithfulness reading below the
  absolute block floor stamps `withheld`; a reading in the watch band stamps nothing per item (watch is
  a fleet-rate alarm, not a per-item action - E1); a low coverage stamps nothing under the default
  `watch`; the bite - flip coverage's action to `block` and the same item stamps `withheld`.
- **Oracle:** the veto chain stamps the most severe action any metric earned and names the metric that
  earned it; it changes no published day (record-only).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Veto chain, not a composite; the reason names the metric (D4) | Andre, Fowler |
  | 2 | Record-only first; a person reads the counterfactual withheld list once as go/no-go before Row 8 (D7) | Fowler, Editor |
  | 3 | A displayed "overall", if built, is labelled a display aggregate that feeds no action | Andre |

#### Plan 36 row #8 - flip the flag - ESCALATE (plan 65 row #23)

- **Scope:** assemble reads the `EvalRow` stamp and acts. A `withheld` (below-absolute-floor)
  faithfulness item does NOT publish - it is ABSENT from the reader's day, no card, no reader-facing
  surface (0e H1). The withhold is recorded in item-health telemetry as `ItemOutcome.failed` with a new
  `FailureCode` (the summary was written but failed the faithfulness floor) + the `detail`, so the
  operator has the metric and the reason (0e H2). The drop/relegate happens BEFORE `collapse_same_story`
  ([assemble.py:2038](../backend/idhazh/assemble.py)) so the next-best duplicate promotes (E7). A length
  pre-filter never summarises a sub-200-word stub (E5). Behind `publish_gate.enabled`, ships off; the
  first row that changes a published day.
- **Files touched:** `backend/idhazh/stages/assemble.py` (drop a withheld item before the fold, record
  the item-health row, recompute run/vertical/desk counts), `backend/idhazh/contracts/item_health.py`
  (the new `FailureCode` member + schema/version/changelog, 0e H2), `config/idhazh.json`
  (`publish_gate.enabled` + the stub-length floor, removal condition on the declaring line).
  `digest_day.py` is NOT touched - a withheld item counts in `failed`, so `published + failed <= planned`
  already holds (0e H3).
- **Acceptance gates:** integration over the canary day, built once gate-off and once gate-on, asserting
  a withheld item is ABSENT from the day and PRESENT in item-health with the new `FailureCode` + detail
  (0e H2), and the `published + failed <= planned` invariant still closes; browser smoke that the day
  renders with an item withheld and when the band tree is absent. (The corpus fence + its test move to
  Row 12; the old byte-identity assertion is retired, 0e J6/J7.)
- **Oracle:** with the flag off, every published day is byte-identical to today; with it on, a
  below-absolute-floor item is absent from the day and carries an item-health row naming why, and the
  story's next-best duplicate is promoted; it cannot settle the editorial cost of a thin day (D8 - the
  not-published rate is watched on the console at the stated ~11% baseline, E5).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Lands alone, after a corpus turn of record-only review; owner sign-off (Level 5) | owner, Fowler |
  | 2 | Only faithfulness withholds; coverage/coherence are watch-only (E1) and never withhold; the owner sets the absolute floor and permits withholding (reader-safety boundary) | Editor, owner |

#### Plan 36 row #9 - console: the quality bands (plan 65 row #24)

- **Scope:** add panels to `/console/judgement/` drawing each metric's distribution, its fitted floors
  over time, and the record-only counterfactual list a person reviews before Row 8. Add a not-published
  / withhold panel that reads item-health: the withhold count, the ~11% baseline (E5), and the reason
  breakdown by `FailureCode` - the operator's view of what the gate withheld and why (0e H4).
- **Files touched:** `frontend/src/routes/console/judgement/*.svelte`, a console reader under
  `frontend/src/lib/console/`, the affected browser specs.
- **Acceptance gates:** frontend `test:changed`; browser smoke per section 12, including the data-absent
  check (rebuild with an empty band tree, confirm the panel draws its axis and its empty-state copy).
- **Oracle:** the browser oracle re-derives each drawn floor from the committed band shard; it cannot
  settle whether the panel reads well (Susan's sufficiency check).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | The not-published/withhold rate is a first-class panel with its own alarm, read from item-health (D8, 0e H4) | Editor |
  | 2 | A tiny glyph links each metric to `docs/architecture/publishing/autotune-summary-quality.md` | Susan |

#### Plan 36 row #10 - measure a real G-Eval call (plan 65 row #25)

- **Scope:** measure a real fluency G-Eval call on a stock `ubuntu-latest`, prefill and decode
  separately, over at least 20 calls, and replace the ~28 s estimate that sizes the council leg.
- **Files touched:** new `backend/utilities/measure_geval_call.py`, a `workflow_dispatch` job in
  `.github/workflows/measure.yml`, `docs/reference/benchmarks/what-a-geval-call-costs.md`,
  `docs/reference/measurements.md`.
- **Acceptance gates:** unit tests over built readings (the cold call is reported not averaged, a run
  stopped on the clock reports what it got); the record names the weights and the processor it drew.
- **Oracle:** the record reproduces its statistics from the committed `calls.jsonl`; it cannot settle a
  different runner's number (the processor lottery is named).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Measure prefill (summary + rubric) and decode (confirm it is one digit, not generated CoT) separately; worst x 30 sizes the leg, never the mean | Carmack |

#### Plan 36 row #11 - confirm coherence runs in `assemble` (no 3-model peak) (plan 65 row #26)

- **Scope:** confirm coherence (plan 35's MiniLM scorer) is wired into the `assemble` job, where MiniLM
  is ALREADY loaded to build the search index and the summariser is NOT resident - so the feared
  3-model peak (summariser + HHEM + MiniLM) never occurs (0e H5). Take one cheap RSS reading in
  `assemble` to show MiniLM + the coherence/ROUGE work fits with headroom.
- **Files touched:** confirm plan 35 Row 8 wired coherence into `assemble` (not `work`); a one-off RSS
  reading recorded in `docs/reference/measurements.md`. NO server-stop step, NO two-phase `work` shard,
  NO `shard_timeout_minutes` change - all retired with the eviction (0e H7).
- **Acceptance gates:** the reading shows the `assemble` peak RSS (MiniLM + ROUGE, no summariser) fits
  16 GB with headroom, hardware + date named (Guardrail #10); coherence scores land on the same day's
  eval rows.
- **Oracle:** coherence is computed in `assemble` and the `work` shard's peak is unchanged (summariser
  + HHEM only). It cannot settle a future model swap's footprint (re-measure then).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Coherence runs in `assemble`, reusing the MiniLM already loaded for the search index; no 3-model peak (0e H5, corrected 2026-09-19) | owner, Carmack |
  | 2 | The sequential server-eviction + two-phase `work` shard + the 200->220 timeout are RETIRED - they solved a peak that does not occur | owner |

#### Plan 36 row #12 - the rejects ledger + the corpus fence (`state/rejects/`, 30-day prune) (plan 65 row #27)

- **Intent:** capture every withheld summary with enough context to investigate WHY it failed - offline,
  by a person or a bigger model, NEVER shown to a reader - and stop training the model on summaries we
  blocked. Row 8 removes the item; Row 12 keeps the evidence and fences the corpus (owner, 2026-09-19;
  section 0e Table C).
- **Scope + files touched:**
  - **The contract:** new `RejectRow` in `backend/idhazh/contracts/reject_row.py` + generated
    `schemas/reject-row.schema.json` + the `CONTRACTS` tuple/import in `contracts/export.py` + a
    `tests/fixtures/contracts/reject-row/` round-trip fixture. Fields per 0e J2; `version` + one
    `changelog`.
  - **The write:** at the record-only gate (`backend/idhazh/quality/gate.py`, Row 7), when an item is
    stamped `withheld`, write `state/rejects/<YYYY>/<MM>/<DD>/<item_id>.json` (temp-file-plus-rename,
    one item one file - no `merge=union`). The summary, article extract and scores are already in hand;
    render the prompt with `summarize.system_prompt(...)` + `summarize.user_turn(...)` (the same
    reconstruction the corpus harvest uses at [corpus.py:400](../backend/idhazh/corpus.py)) so the
    stored prompt is the exact one the model saw. Reuse the `ledger` / day-partition helpers.
  - **The prune:** a `finetune.reject_window_days` knob (default 30) + `retention.prune_rejects` wired
    into `backend/idhazh/stages/prune_state.py` beside `prune_traces`, deleting whole day directories
    past the window (the `keep-future-dated` guard applies unchanged).
  - **The corpus fence:** in `backend/idhazh/corpus.py` `harvest_rows`, skip any `Scored` whose
    `row.publish_decision == withheld` BEFORE `keeps_its_counterweights` (which stays `hhem`-free). Do
    NOT add `hhem` to `keeps_its_counterweights` (0e J6).
  - **The 0a amendment + docs:** amend `CLAUDE.md` section 0a to write BOTH committed-article-text
    carve-outs (S5 A1, owner 2026-09-19): the `corpus/` one FIRST (today it is only cross-referenced
    from section 8, never stated in 0a) and `state/rejects/` SECOND, bounded by the 30-day prune (0e J3),
    so section 0a becomes the canonical list. Document the ledger + the fence in
    `docs/how-to/fine-tune-a-model.md` and the design-of-record.
- **Acceptance gates:** contract drift gate (the new schema regenerates byte-identical); a unit test
  that a withheld item writes exactly one `RejectRow` carrying the prose + source + rendered prompt
  (driven from a bounded fixture, never the archive); a `harvest_rows` test that an item stamped
  `withheld` is excluded from the corpus while a published sibling stays, and `keeps_its_counterweights`
  still reads no `hhem`; a prune test on a bounded fixture that a day past the window is deleted. No
  test walks the committed ledger (section 13, Guardrail #12).
- **Oracle:** for a built withheld item, a `RejectRow` round-trips with the failing prose, the source
  extract and the exact rendered prompt, and the corpus harvest drops it. It cannot settle whether the
  0.50 floor is well-calibrated - that is the offline judge the ledger exists to feed (J8), out of scope.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A committed ledger of JSON payloads rather than CSV rows - prose has newlines - one file per item, day-sharded, on the `state/traces/` pattern | Fowler |
  | 2 | Source text committed here, a second 0a carve-out, bounded by a 30-day config-driven prune | owner (J3/J4) |
  | 3 | The corpus fence reads the stamped `publish_decision`, never `hhem`; `keeps_its_counterweights` stays faithfulness-free | Andre, owner (J6) |
  | 4 | The ledger is the auditable safety net that makes fencing the corpus sound despite the Goodhart risk; offline judging (bigger model or human) reads it, never a reader (J7/J8) | Andre, owner |

#### Plan 36 row #13 - retro: plan-34 latent gaps + the shared space-trap guard (plan 65 row #28)

- **Intent:** three defects flagged during the plan-34 review were never given a home (out of scope for
  plan 34's merge). They land here as the last row because one - the first-token-probability space trap -
  is re-introduced by Row 6's G-Eval fluency judge, so the guard is shared (owner, 2026-09-19).
- **Scope + files touched:**
  - **Space-trap re-set:** a trailing-space token in a rendered prompt silently shifts which
    digit/verdict the model emits from its first-token probabilities, and the output still parses.
    Assert the rendered prompt does not end in a space; build the digit/verdict token ids by
    encode-in-position (not by string); log all first-token probabilities. Covers
    `backend/idhazh/similarity/judge.py` (plan 34) and `backend/idhazh/quality/geval.py` (Row 6).
  - **Thinking-variant:** confirm `thinking` is OFF for every judge/council call and pin it with a canary
    that a thinking-on recorded completion is REJECTED, not silently scored (plan 34 + Row 6).
  - **Injection live-test note:** the injection canary runs against a RECORDED completion only (Guardrail
    #7 forbids a live server in tests), so it proves the grammar + log-prob read resists a side-loaded
    instruction in the fixture, not a live model. State this as accepted-by-contract in one line; a live
    red-team is a separate, out-of-scope follow-up.
- **Acceptance gates:** the space-trap + thinking-off canaries pass against recorded fixtures for BOTH
  the plan-34 judge and Row 6's G-Eval; no network (Guardrail #7).
- **Oracle:** a rendered prompt ending in a space fails the guard, and a thinking-on recorded completion
  is rejected. It cannot settle live-model injection resistance (accepted-by-contract, Guardrail #7).
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Retro plan-34 gaps re-homed here as the last row (owner, 2026-09-19); the space-trap guard is shared with Row 6 because both read first-token probabilities | owner, Andre |
  | 2 | The injection test stays recorded-fixture only (Guardrail #7); a live red-team is a separate, out-of-scope follow-up | Andre |

### Plan 36 section 3 - the loop, and where it is documented

The design of record, with the mermaid and the formulas, is
[`docs/architecture/publishing/autotune-summary-quality.md`](../docs/architecture/publishing/autotune-summary-quality.md). That page
carries the four metrics, how each is measured, the fold-fit loop, and the publish gate; this plan
sizes the rows that build it. When Row 8 lands, the page's "target design (in flight)" framing is
removed in the same commit.

### Plan 36: See also

- [`docs/architecture/publishing/autotune-content-similarity.md`](../docs/architecture/publishing/autotune-content-similarity.md) - the
  merge line that fits itself: the loop this plan mirrors, and the fit core Row 1 extracts.
- [`docs/concepts/evaluation.md`](../docs/concepts/evaluation.md) - the two measures that left the
  eval row and the two that arrived, and what the departure did to `scorer_version`.
- [`docs/architecture/publishing/autotune-summary-quality.md`](../docs/architecture/publishing/autotune-summary-quality.md) - the
  metrics, the formulas, and the loop diagram.
