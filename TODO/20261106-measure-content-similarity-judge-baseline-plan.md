# Measure the content-similarity judge baseline

**Last Updated**: 2026-11-06
**Level**: 3 - real measurement under existing private contracts; no model, policy or contract change.

## 0. Operating contract

Table A - Operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Preserve the unfinished independent accuracy measurement separately from the delivered council and evaluator software. |
| A2 | Hard scope - in | One bounded, independently annotated confirmation set; an actual capture of the unchanged production judge; fully offline scoring; the current evidence and its benchmark page. |
| A3 | Chosen strategy | Use the existing freeze, blinded annotation, capture and score procedure. The [operator procedure](../docs/how-to/evaluate-content-similarity-judge.md) owns its steps and evidence requirements. |
| A4 | Contract owner | The [private evaluation compatibility rule](../docs/architecture/contracts/schemas.md#private-judge-evaluation-documents) and `backend/idhazh/contracts/content_similarity_judge_evaluation.py` own the four retained documents and the selection manifest. `config/judges/content-similarity-evaluation.json` owns input and reporting limits. Do not copy or extend these shapes. |
| A5 | Current blocker | Independent annotations are not ready and no human review resource is available. An operator-controlled model process has not been confirmed for this measurement. No real baseline has been captured or scored. |
| A6 | Start condition | Arrange the independent annotation resource and confirm the configured model process before measurement. Then name the source snapshots, freeze the rubric and case selection, and collect the actual model-host evidence. Missing prerequisites leave the row BLOCKED. |
| A7 | ESCALATE triggers | 1. Missing or unqualified independent evidence.<br>2. A required model, prompt, grammar, sampler, confidence, budget or adaptive-policy change.<br>3. A new persisted field, dependency, destination, service or automatic action.<br>4. A required production/recovery dispatch or production-state write.<br>5. A trust-boundary or ownership failure. Keep the current evidence intact and surface the required change rather than substitute another measurement. |
| A8 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer carries the measuring row; parallel N = 1 because capture must not compete with tests or other inference; consult the relevant advisor only for a decision that changes the work; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP. |
| A9 | Delivered prerequisite | The standalone evaluator is delivered in #1936. Its software tests establish the measurement path, not judge accuracy. No engineering row from that delivery needs restarting. |

Table B - Scope boundaries

| Id | What stays out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Changing the judge or activating a fitted threshold | This baseline does not choose a better model or establish a safe publication policy. | A measured error that supports a separately priced instrument or publication change. |
| B2 | Historical recovery, production council dispatch and scheduled evaluation | Missed production dates and continuous qualification remain separate work. | A request naming the dates, writes, consumer, operating budget and retained contracts. |
| B3 | Model marks presented as independent human truth | Accuracy remains unknown while the required annotations are unavailable. | A separately defined model-reference study with its own claims and provenance; it would not complete this human-reference baseline. |
| B4 | Archive discovery, article fetching and new metric frameworks | The study covers only the explicitly named finite inputs and existing report metrics. | A demonstrated need for a named input or metric that the current bounded procedure cannot supply, with its cost and contract declared first. |

## 1. Status Reckoner

Table C - Measurement outcome

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C1 | 1 | Establish the independently labelled current-judge baseline | - | M | BLOCKED | - | - | - |

## 2. Independent quality evidence

### Row #1 - Establish the independently labelled current-judge baseline

- **Scope:** Freeze a real bounded confirmation set, obtain qualified independent annotations, capture the unchanged production judge and preserve its first correctly qualified quality reading.
- **Files touched:**
  - `TODO/20261106-measure-content-similarity-judge-baseline-plan.md`
  - `docs/reference/benchmarks/content-similarity-judge-current-set.json` (new real evidence)
  - `docs/reference/benchmarks/content-similarity-judge-current-labels.json` (new real evidence)
  - `docs/reference/benchmarks/content-similarity-judge-current-run.json` (new real recording)
  - `docs/reference/benchmarks/content-similarity-judge-current-report.json` (new real reading)
  - `docs/reference/benchmarks/how-accurately-the-similarity-judge-decides.md` (new)
- **Acceptance gates:**
  - Preflight: satisfy A6. Do not create empty benchmark files, invent annotations, start inference or mark this outcome delivered while the external inputs are missing.
  - Fix the named native source snapshots, rubric, event groups, development/confirmation split and case list before viewing confirmation predictions. Exclude investigated development examples and prevent article/event groups crossing splits.
  - Include paraphrases, changed actors/numbers/occasions, follow-ups, reactions, genuinely vague summaries and planted-instruction variants from several independent events. Keep representative and challenge streams separate; do not manufacture class labels to meet a quota.
  - Freeze through the existing utility using the native selection manifest. Resolve only its named snapshots. Preserve their exact byte hashes, the frozen sanitized production inputs and the blinded export.
  - Collect primary and independent reviews separately against the fixed rubric. Every confirmation case needs distinct blinded human reviewers in agreement. Use opaque reviewer keys and actual UTC marking instants. Missing, disputed, stale or non-human annotations remain unresolved.
  - Supply a named native host fingerprint for the actual configured model process. Use the existing collection procedure without a production ledger write. Keep unavailable hardware fields null; do not borrow another host's identity.
  - Capture explicitly through the existing utility and production reader. Keep the committed destination, model, prompt, grammar, sampler, reasoning and evidence policy unchanged. Retain both orders, actual request/response spans, costs, UTC instants and instrument/host identities. A transport failure remains incomplete with completed evidence preserved, not a fabricated refusal or automatic retry.
  - Score the saved set, annotations and capture fully offline under the capture's matching committed configuration. Require a measured report with no blockers and complete confirmation coverage. Preserve all outcome classes, including refusals and disagreements in recall denominators, and retain the actual report-settings snapshot.
  - Validate the four real evidence documents with their native models before retaining them at the exact paths above. Reproduce the result using the Oracle, then write the benchmark page with finite case/event support, class/outcome coverage, false-merge and missed-match directions, uncertainty, refusals, order disagreements, method and UTC capture conditions.
  - Keep only the current reading at these paths; version control holds previous readings. Do not rewrite production pairs, aggregates, fitted history or applied lines.
  - Local documentation: run `python backend/utilities/doc_load.py` on this named plan and the new benchmark page; inspect required elements and direct links. Inspect the shared test selector's named input selection. Reuse unchanged software checks rather than repeat an application suite.
  - CI: the required document/format/build checks are authoritative. No inference, annotation collection, real dataset-quality assertions, new bug recordings or benchmark contents become pytest gates.
- **Oracle:** In the same code, metric-library environment and report configuration, fully offline scoring of the frozen set, qualified annotations and complete capture reproduces the canonical report and its exact counts and coverage. This establishes the finite measurement's reproducibility, not population-wide accuracy, a better model or permission to activate a policy.
- **Decisions:**

Table D - Measurement decisions

| Id | Decision | Authority |
| --- | --- | --- |
| D1 | Keep this outcome blocked until the external annotation and model-process prerequisites exist; working evaluator software is not a measured baseline. | [Operator evidence requirements](../docs/how-to/evaluate-content-similarity-judge.md#design-rationale). |
| D2 | Use the existing native document family and private capture path; add no production registration, destination override or alternate parser. | [Contract compatibility](../docs/architecture/contracts/schemas.md#private-judge-evaluation-documents). |
| D3 | Fix splits and rubric before predictions, qualify human annotations against exact input identities, and keep representative/challenge results separate. | [Blinded annotation procedure](../docs/how-to/evaluate-content-similarity-judge.md#collect-labels-without-showing-predictions). |
| D4 | Resample event groups through the existing metric libraries and retain actual report settings. Unsupported intervals remain unknown, not a passing score. | [Saved-evidence scoring](../docs/how-to/evaluate-content-similarity-judge.md#score-saved-evidence). |
| D5 | Report the declared finite population and its uncertainty without inventing a target accuracy, required passing sample count or automatic adoption gate. | [Evaluation limits](../docs/how-to/evaluate-content-similarity-judge.md#design-rationale). |

- **Rejected alternatives:**

Table E - Alternatives that do not complete this measurement

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E1 | Use schema examples or a passing replay as the baseline | Proves software behavior, not correctness of real verdicts. | Real independent annotations and an actual capture would still be needed; substituting examples loses the accuracy claim. | Operator evidence requirements. |
| E2 | Rename model-origin marks as human annotations | Conceals circular evaluation and invalid provenance. | A separately specified model-reference study could measure agreement, but would still leave this baseline unfinished. | Native annotation qualification. |
| E3 | Add votes, retries or confidence cutoffs before measuring | Changes the instrument without evidence that the change addresses its errors. | Additional captured calls, a new decision policy and an independent evaluation of that policy. | Unchanged-instrument scope. |
| E4 | Benchmark in the scheduled production workflow | Couples measurement to publication side effects and recurring runner work. | A consumer, workflow budget, lifecycle, retained contracts and publication design beyond this standalone study. | Offline operation boundary. |

## See also

- [Operator procedure](../docs/how-to/evaluate-content-similarity-judge.md)
- [Similarity rule and instrument identity](../docs/architecture/publishing/autotune-content-similarity.md)
- [Native contract compatibility](../docs/architecture/contracts/schemas.md)
- [Host evidence](../docs/reference/host-metrics.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
