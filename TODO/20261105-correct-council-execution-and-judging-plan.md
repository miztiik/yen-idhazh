# Correct council execution and judging

**Last Updated**: 2026-11-05
**Level**: 5 - plugin communication, retained measurement contracts and independent evaluation; each delivery row states its own level.

## 0. Operating contract

Table A - Operating contract

| Id | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | Keep the council independent of its judges, prevent one failed preparation from blocking independent work, and correct and measure the content-similarity judge without concealing failures. |
| A2 | Hard scope - in | - Distinct-article eligibility in shared article scoring.<br>- Judge-owned scheduling and task files, with generic council transport and failure handling.<br>- Correct emitted-token evidence and order-independent statistics.<br>- Correct calibration population and published-threshold selection.<br>- A real offline evaluator and a separately tracked, independently labelled baseline.<br>- Related contracts, compatibility, fixtures, tests and living documentation. |
| A3 | Hard scope - out | Table B prices the exclusions. No recovery dispatch is part of any row. |
| A4 | Chosen strategy | Extend the existing plugin interface, not a new task framework; retain strict article-pair validation and correct the judge's evidence path. Architecture: Fowler. Judge interpretation and evaluation: Andre. |
| A5 | Baseline | Investigated commit `40411f60cd777d47e07fda59d6fcd1d140db4c76`. Reconcile every inventory and existing concurrent change against the row's actual base before dispatch. Current enforcement predicates are recorded in the per-row Decisions tables. |
| A6 | PR shape | Each Status Reckoner row is one PR-sized outcome. The evaluator and its real baseline are separate rows because working evaluation code cannot substitute for independent labels or a measured result. No production recovery run is added by that split. |
| A7 | ESCALATE triggers | 1. Pause before an unlisted Level-5 design change.<br>2. Surface any persisted field, policy, dependency or automatic action not declared below.<br>3. Stop on a required change to model choice, prompts, grammar, sampling, destination, adaptive activation, platform limits, or the trust boundary.<br>4. Surface another active change that moves a named interface or retained reader; update this plan rather than silently substitute its contract.<br>5. Pause row 6 when independent labels or an operator-controlled model process are unavailable; do not replace them with model-generated truth or mark the baseline complete.<br>6. Surface ownership/integrity failures, unresolved advisor disagreement, or the cost-overrun trigger in the execution contract.<br>7. Do not edit `CLAUDE.md` or `AGENTS.md`. |
| A8 | Execution | Execute per docs/how-to/execute-a-plan.md: one maintainer coordinates the plan; one nested app session owns each row and its PR; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. |
| A9 | Parallelism | Rows 1 and 2 have independent implementation files. Later dependencies include real shared-file constraints, identified in Table I. The shared Reckoner is coordinated as prescribed by the execution contract, not treated as an independent implementation file. Row 6 measures alone. |
| A10 | Contract order | Expand readers and validators before changing writers within each affected PR. Same-invocation transport is revision/run/attempt-bound; retained ledgers and private evaluation documents retain their declared read-side compatibility. |

### Scope boundaries

Table B - What stays outside these PRs

| Id | What is out | Cost of leaving it out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Rejudging historical dates, recovery dispatches and automatic cross-run artifact recovery | Previously missed results remain missed unless ordinary existing scheduling selects them. | A separate recovery request naming the dates and publication effects. |
| B2 | Removing duplicate published placements, URL alias discovery, source-name changes and ingestion redesign | Duplicate placements can remain visible; this plan prevents self-comparisons and false independent coverage, not every form of repeated work. | A bounded example proving a separate ingestion, representative-selection or identity defect and a priced producer/reader change. |
| B3 | New judges, model-role/resource architecture, model switches, extra votes, tie-breaking retries and reasoning changes | Existing model capacity and correlated-error limits remain. | A distinct judge requirement or row 6 evidence that identifies a change worth its quality and execution cost. |
| B4 | Enabling adaptive thresholds, changing their limits, or using confidence margins as a publication gate | Corrected evidence does not itself activate a new grouping policy or establish calibrated confidence. | A separate decision supported by independent quality evidence and the affected reader trade-off. |
| B5 | New services, brokers, plugin frameworks, scheduled evaluators or production evaluation ledgers | Offline evaluation is explicit operator work; it does not continuously qualify the model. | A requirement with a named consumer, operating budget, ownership and retained contract. |
| B6 | Rewriting old pair rows, fitted rows, aggregate archives or historical versions | Old readings retain their original method; corrected populations start separately. | A separately specified migration that can reconstruct the missing original evidence without guessing. |
| B7 | Editing the contract files named in A7 or recording approval narratives and personal/company attribution | No project-wide policy amendment is included. | A separate explicit instruction for the affected file; no row here depends on one. |

### Responsibility boundary

Table C - What belongs to which side

| Id | Surface | Judge responsibility | Council responsibility |
| --- | --- | --- | --- |
| C1 | Participation | A plugin declares its identity and whether it needs a model; its scheduling method can return no dates. | Read the configured registration and active/paused/retired status. Import only authorized plugins. Keep an empty active set legal. |
| C2 | Dates | Choose actual scheduled work dates inside the supplied window and date budgets. Decide which earlier dates its own evidence has not completed. | Supply UTC bounds and resource limits; validate the answer without inserting dates, truncating it or reading judge ledgers. Manual selection remains one explicit date. |
| C3 | Work | Select articles or other domain inputs, create task files, and decide whether preparation found work. | Record preparation, validate identity and file ownership, transport opaque files, and dispatch only ready work. |
| C4 | Execution | Implement the unit, stop safely at the supplied deadline, and return declared output files and costs. | Supply deadlines and identities, isolate ordinary unit failures, collect reports and retain unsuccessful overall status. |
| C5 | Results | Interpret verdicts, maintain its own counts and produce its own permitted state writes. | Check write ownership and completed-byte evidence, collect generic records and publish only permitted completed output. |
| C6 | Interface | Translate between the generic invocation contract and existing judge stages in the plugin adapter. | Own the generic communication types. Never add article fields, verdict rules or a judge-name switch to orchestration. |

### Platform communication contract

Table D - Types declared by row 2

| Id | Type and location | Fields and required meaning |
| --- | --- | --- |
| D1 | `ScheduleRequest`, in-process model in `backend/idhazh/contracts/council_invocation.py` | `anchor_date: DateStamp`, `window: tuple[DateStamp, ...]`, `max_dates: int`, `max_older_dates: int`, `shards: int`, `shard_seconds: float`. Calendar dates are valid and unique. The window includes the anchor and the configured older window, clipped at `first_night`. Budgets are derived from existing council config: maximum dates is one plus the older-date cap; effective width is the smaller of plugin and council widths; seconds use the existing deadline calculation. No new resource values are introduced. |
| D2 | `JudgeSchedule`, in-process model beside D1 | `dates: tuple[DateStamp, ...]`. Empty explicitly declines scheduled work. Nonempty answers must be unique, inside the supplied window, and satisfy both total and older-date budgets. Invalid answers are refused, not repaired by the platform. |
| D3 | `Selection` and `SelectedJudge`, native models beside D1 | Move their declarations out of `council/selection.py`. `Selection` is a versioned document with `run_id: RunId`, positive strict `attempt: int`, `git_sha: CommitSha`, `mode: Literal["scheduled", "manual"]`, `anchor_date: DateStamp`, `window: tuple[DateStamp, ...]` and `judges: tuple[SelectedJudge, ...]`. Each `SelectedJudge` carries `tenant: Slug`, `status: JudgeLifecycleStatus`, `dates: tuple[DateStamp, ...]` and positive strict `shards: int`. Scheduled selections retain every active plugin in registration order, including plugins with no dates. Manual selections retain the existing nonempty judge set and one shared date. |
| D4 | `ArtifactFile`, native model beside D1 | `path: RelPath`, nonnegative strict `size_bytes`, and `sha256: Sha256`. The platform calculates size and digest from the declared file. Paths are relative to the selected active/trial invocation root and must address the expected date/slot/judge namespace. They are never supplied by article or model text. |
| D5 | `PreparationReceipt`, versioned document beside D1 | Invocation identity from D3, `judge_id`, `date`, `state` (`ready`, `no_work`, `failed`), nonnegative strict `shards`, `files: tuple[ArtifactFile, ...]`, and optional sanitized `error`/`where` using the existing event types. Table E defines the state constraints. |
| D6 | `ShardFiles`, versioned document beside D1 | Invocation identity from D3, `judge_id`, `date`, nonnegative strict `shard`, positive strict `shards`, and declared `files`. Its part index must be below its width and agree with the selected cell. It carries file evidence, not the unit outcome. |
| D7 | `Cell`, native model beside D1 | Move the declaration from `council/run_summary.py`; retain `tenant`, `date`, `shard`, `shards`, `runs_model`. A cell is authorized only by a matching ready receipt. |
| D8 | `ShardReport`, in-process normalized model beside D1 | `shard`, `shards`, `report_state` (`reported`, `refused`, `missing`, `invalid`, `not_dispatched`), optional `outcome`, and optional `code`. A reported unit has complete validated unit/program events, not necessarily a successful outcome. |
| D9 | Existing `Tenant` protocol | Keep identity, width and committed-path properties. Replace `nights_outstanding` with `schedule(*, request: ScheduleRequest) -> JudgeSchedule`. Preparation receives `date`, `run_id`, `shards`. Shard execution additionally receives `prepared: PreparationReceipt`. Settlement additionally receives `prepared` and `reports: tuple[ShardReport, ...]`. Make existing `publication_inputs(*, date) -> tuple[RelPath, ...]` mandatory; an empty tuple is valid. |
| D10 | Existing `ShardResult` dataclass | Keep the outcome, costs and opaque plugin CSV row. Add `files: tuple[RelPath, ...] = ()` for scratch output names. Do not serialize plugin metrics through a base-typed model or use scratch-file declarations as permission to publish state. |
| D11 | Versioning and artifact addresses | D3, D5 and D6 inherit the native version/changelog rules, each with one minimal schema-verification fixture. Test state variations in memory, not additional edge-case files. Match revision, run and attempt exactly; old invocation artifacts are not resumed or migrated. Active scratch is under `backend/var/council/runs/<run-id>/<attempt>/`; trial roots keep their current invocation/judge isolation. Preserve the date/slot/judge helper layout inside each root. Receipt, selection and file-bundle addresses are computed from validated invocation identities, never discovered by scanning prior runs. |

Table E - Platform state transitions

| Id | Observation | Dispatch and collection rule |
| --- | --- | --- |
| E1 | Preparation returns `COMPLETED`; recording and file checks succeed | Write `ready`, with the selected positive width and at least one valid task file. Only this state produces judging cells. |
| E2 | Preparation returns `NOTHING_TO_DO`; recording and file checks succeed | Write `no_work`, width zero, with optional bookkeeping files. Run settlement with no shard reports. Do not create model jobs, empty shard files or synthetic shard records. |
| E3 | Ordinary preparation exception | The platform writes `failed`, width zero, no admitted task files, and sanitized fault metadata after recording the actual failed step. Continue independent judge/date preparations. No judge may fabricate a failed return value. |
| E4 | Expected preparation receipt is absent | Report unknown preparation/no report, not no work. Skip that judge's settlement, retain valid platform records, and keep the aggregate unsuccessful. |
| E5 | Ready/no-work preparation reaches collection | Call the plugin's settlement with its own preparation and normalized reports. Failed or unknown preparation does not call domain settlement. Valid independent work remains eligible for publication. |
| E6 | Dispatched shard has missing, malformed, refused, failed or deadline-stopped evidence | Preserve the distinct report state; do not certify its date complete. File valid arrived evidence where permitted and keep the invocation unsuccessful. |
| E7 | Phase abort after ready preparation but before dispatch | Report not dispatched. Do not turn the absence into successful no work or invent a cause for an individual missing report. |
| E8 | Cancellation, phase timeout, ownership/integrity failure, including a fatal member of an exception group | Do not contain it as an ordinary plugin failure. Preserve cancellation/failure; keep the existing whole-publication integrity refusal. Post-work integrity failure is unsuccessful, not a claim that no work ran. |
| E9 | Invalid config, import, required member, identity, width, declaration or schedule before preparation | Refuse the invocation before work. Do not silently drop the plugin or grant partial authorization from an invalid plan. |
| E10 | Complete preparation batch includes ordinary unit failures | Print `preparation_finished=true` only after all its units have been visited. Fanout can run after that failed preparation step. Dispatch must explicitly override dependency success, require that marker and a present nonempty matrix, and refuse cancellation. Collection receives both planning and judging job results. |
| E11 | Zero-part non-shard record | Expand `CouncilRunRecord` and `UnitFinished` to permit zero parts for prepare/settle, while shard rows still require a positive count and valid index. Ready records use the prepared width; no-work/failed preparation uses zero. Historical positive-count no-work rows and rows without `fault` remain readable. |

### Judge evidence and calibration contract

Table F - Types and meanings changed by rows 3 and 4

| Id | Surface | Required contract |
| --- | --- | --- |
| F1 | Decoder evidence, in memory | Add frozen `EmittedToken(token_id: int, text: str, bytes: tuple[int, ...])`, with nonnegative token ID and byte values in the byte range, plus `Completion.emitted_tokens: tuple[EmittedToken, ...] or None` and `Completion.raw_response: str or None`, both defaulting to None. Parse emitted positions in order from their own `id`, `token`, `bytes`; retain `top_logprobs` only as alternatives. Missing/invalid emission evidence stays absent for the judge's explicit refusal rather than failing unrelated response consumers. Existing non-judge completion consumers retain compatible defaults. |
| F2 | Valid judge reading | Keep the literal YES/NO/UNCLEAR parser and optional single leading space. Consume actual emitted prefixes until they identify the literal verdict. Define `ReadingRefusalReason` once beside the pair contract: invalid_literal, missing_emission, invalid_emission, ambiguous_emission, mismatched_emission. Missing, malformed, empty, ambiguous or contradictory evidence produces the corresponding reason, null verdict and `grammar_applied=false`, with retained costs. Carry the reason in the in-memory reading for logs/evaluation, not a new pair-ledger column. No alternative-ranking fallback, retokenized substitute, retry or skipped reverse reading. |
| F3 | Shared statistics | For completed, matching-instrument pairs, let Q be attempted pairs; V be pairs with two valid readings; A be valid agreeing pairs, including UNCLEAR; R = Q - V; D = V - A; U be agreed UNCLEAR pairs. Disagreement is D/V or null when V is zero. Unclear share is U/A or null when A is zero. Derive rates from combined counts, never average shard rates. |
| F4 | Statistics writers/readers | Shard fields retain `pairs_read=V`, `pairs_agreed=A`, `pairs_refused=R`. Fit fields become `pairs_judged=V`, `pairs_usable=A`, plus nullable `pairs_refused`; fitted disagreement/unclear rates become nullable. Old rows keep their stored readings and unknown new fields. Null rates skip the existing rate comparisons, without adding a health gate or claiming a zero measurement. Preserve valid fitted lines when rates are unavailable; display unavailable rates as gaps. |
| F5 | Judge interpretation identity | Declare one date-valued `JUDGE_POLICY_VERSION` beside the pair contract. Append `judge_policy_version: DateStamp or None`, default None, to pair, distribution, metrics and fitted contracts. Old rows and unjudged draw rows read/retain null; new judged pairs, aggregates, metrics and fits supply the current value. This protocol date identifies code semantics and cannot be an operator tuning value. Carry it through `JudgeStamp`, instrument filtering, input-change detection and record identity. Do not alter the prompt to manufacture an identity change or extend generic model config stamps. |
| F6 | Calibration population | For cumulative counts and today's subtractable contribution, apply matching instrument -> newest row per pair -> usable -> `headline is False` -> score slot. Continue judging and retaining headline overrides as audit evidence; daily judge-health statistics still describe all audit pairs. |
| F7 | Calibration identity | Declare one date-valued `CALIBRATION_POLICY_VERSION` beside the distribution contract. Append `calibration_policy_version: DateStamp or None`, default None, to distribution and fitted contracts; include it in new record construction, input-change detection and record identity. Old values read null. As in F5, the value identifies implemented semantics, not an operator choice. |
| F8 | Aggregate reset and historical fit evidence | Archive the previous aggregate successfully before replacing it. Carry `judged_dates` unchanged into empty current-policy counts. If archiving cannot occur, keep the old aggregate and the existing input-change hold. A transition resets once; policy changes deployed together produce one reset. Do not rebuild old slot totals or rejudge remembered dates. Preserve the previous applied line, but restrict shift/settled history to the current record identity. |
| F9 | Published threshold | Read the selected day's named `run.json` through the existing manifest validation. Select greatest `completed_at`, missing time oldest, later list entry winning ties; read that record's `same_story_floor_applied`. Missing manifest or null legacy value uses configured `floor_min` with an explicit legacy-fallback log. Malformed present input fails validation. Do not search older records for a value or reconstruct history from today's fitted ledger. |
| F10 | Selection band | Use F9 only to protect mandatory pairs at/above the published threshold. Keep the configured band fixed. No change to pair budget, band limits, decoder settings or adaptive activation. |
| F11 | Retained compatibility | Advance affected schema dates/changelogs, expand native and frontend readers before new writers, and retain named historical JSON/CSV/Parquet fixtures. A historical policy is not relabelled as current and old rates are not connected across a policy boundary. New-policy records enforce the new count/rate/usability invariants. |

### Offline evaluation contract

Table G - Documents declared by row 5 and populated by row 6

| Id | Document or operation | Required content and validation |
| --- | --- | --- |
| G1 | `EvaluationSet` | Versioned fields: `sources: tuple[EvaluationSource, ...]`, `cases: tuple[EvaluationCase, ...]`, `corpus_sha256: Sha256`, `sanitizer_sha256: Sha256`. A source has `path: RelPath`, `date: DateStamp`, `sha256: Sha256`. A case has `case_id: Sha256`, event `group_id: Slug`, `split` (development/confirmation), `stream` (representative/challenge), frozen `left`/`right: DigestItem`, `left_source`/`right_source: RelPath`, `input_sha256: Sha256`, optional `parent_case_id: Sha256`, and `mutation_kind` (none/planted_instruction). Source references must resolve inside `sources`. Input identity hashes the actual sanitized summary-pair input; case identity additionally includes canonical article identities and the declared variant. Reject self-pairs, duplicate cases, inconsistent copies and any article/event group crossing splits. |
| G2 | `EvaluationLabels` | Versioned fields: `set_sha256: Sha256`, `rubric: str`, `rubric_sha256: Sha256`, `annotations: tuple[EvaluationAnnotation, ...]`. Each annotation has `case_id`, `input_sha256`, opaque `reviewer_key: Slug`, `role` (primary/independent), `origin` (human/model/unverified), `verdict: SameStoryVerdict`, and `marked_at: Timestamp` in UTC. The rubric hash must match its text. Qualified confirmation labels require two distinct blinded human annotations in agreement; missing or disputed labels remain unresolved, never NO. Software checks provenance declarations; actual independent label collection is external work, not a flag the worker fabricates. |
| G3 | `EvaluationRun` | Versioned fields: `set_sha256`, selected `split`, `model: ModelRef`, `config_sha256`, `prompt_digest`, `grammar_digest`, `judge_policy_version`, `envelope_sha256`, `git_sha`, UTC `started_at`/nullable `finished_at`, private `host: HostFingerprintRow`, `state` (not_run/incomplete/captured), and `cases: tuple[EvaluationCaseRun, ...]`. A case run carries `case_id`, `input_sha256`, and nullable `forward`/`reverse: EvaluationReading`. A reading carries nullable `verdict`, `grammar_applied`, nullable `refusal_reason`, token counts, elapsed seconds, nullable first-token margin/window, thinking-span count, exact request JSON and raw response text. Use F2's closed evidence reasons; never parse model text into identities or paths. Save atomically as cases complete. Captured requires both readings of every selected case; transport failure leaves incomplete, not an invented refusal response. |
| G4 | `EvaluationReport` | Versioned fields: `set_sha256`, `labels_sha256`, `run_sha256`, `state` (blocked/measured), `blockers`, and `streams: tuple[EvaluationStreamReport, ...]`. Blockers are closed words: missing_labels, conflicting_labels, unqualified_labels, incomplete_capture, provenance_mismatch. A stream report identifies its stream and carries case/group/qualified-label counts; per-class gold/prediction counts; a dense confusion table with gold SameStoryVerdict against predicted YES/NO/UNCLEAR/DISAGREE/REFUSED; valid-agreement, unclear, refusal and disagreement counts; per-class precision/recall and nullable interval bounds; nullable margin diagnostics. Counts are strict nonnegative integers; rates/bounds are null or within the unit interval; validators enforce complete category keys and reconciled totals. Recall includes all gold cases, including refusals/disagreements. Incomplete required labels or capture blocks quality metrics rather than manufacturing a score. |
| G5 | Freeze, capture, score operations | The project-authored pair manifest is validated as `EvaluationSelection(Model)`: `sources: tuple[RelPath, ...]`, `pairs: tuple[EvaluationSelectionPair, ...]`. Each pair supplies `left_source`, `right_source`, `left_item_id`, `right_item_id`, `group_id`, `split`, `stream`, and optional `mutation`. A mutation supplies `side` (left/right) and nonempty `append_summary`; the resulting item must pass the existing `DigestItem` validation. Preserve a parent case and mark the variant as planted_instruction. Resolve only the named `DigestDay` files and enforce case limits, including variants; this manifest is configuration, not another retained contract family. Freeze embeds the original summaries and creates a blinded export with exactly the sanitized text the production judge sees. Capture alone may contact the configured operator-controlled model process through the production reader. Score is fully offline. No operation fetches articles, discovers archive days, writes production ledgers or dispatches the council. |
| G6 | Evidence separation | Existing model-labelled marks are development references only. Fix case groups, split and rubric before reading confirmation results. Representative and challenge cases are reported separately. A measured baseline describes this finite case set; no acceptance threshold, automatic promotion or population-wide accuracy claim is introduced. |
| G7 | Completion boundary | Row 5 delivers the working evaluator, including honest blocked outcomes on incomplete input. Row 6 delivers real independent labels and the current baseline. A green harness cannot mark row 6 done. Record only the current baseline in its living benchmark page and named evidence files; let version control hold earlier readings. |

### Configuration and common gates

Table H - Shared implementation instructions

| Id | Surface | Required action |
| --- | --- | --- |
| H1 | Existing settings | Keep council registration, lifecycle values, timeouts, widths, current model, prompt, grammar, sampling, confidence use and adaptive flags unchanged. These are completed corrections, not a second default-off implementation. |
| H2 | New offline settings | Row 5 adds `config/judges/content-similarity-evaluation.json`, read only through a new `load_evaluation(config_dir)` settings helper and `ContentSimilarityEvaluationConfig` in the existing judge knobs module. Declare fields actually computed on: positive strict `max_cases=200` as a per-set input ceiling, `confidence_level=0.95` strictly between zero and one as report interval coverage, positive strict `resamples=2000` as interval resampling count, and strict `resample_seed=0` for repeatable report arithmetic. These are engineering/reporting defaults, not accuracy acceptance criteria or model-determinism promises. Derive source reads from the named set; do not add another archive window or duplicate model settings. |
| H3 | Local selection | Inspect `npm --prefix frontend run test:changed -- --list`; record its source inputs and reasons. Use the existing environment and focused Python/logic selections below for the inner loop, with the shared launcher/lock per `docs/how-to/run-the-gates.md`. New regressions use minimal in-memory inputs and permitted boundary fakes, not mocked business logic or recorded payload files. Generate named temporary files only when file I/O is the boundary under test; never walk or glob test directories, including temporary ones. Do not repeat an unchanged worker check or install dependencies without a manifest change or missing-dependency failure. |
| H4 | Local static checks | Run the existing ruff and mypy gates for changed Python, and the existing frontend check for changed TypeScript/Svelte. Run the row's named oracle and relevant dependent tests. Demonstrate a new behaviour regression on an isolated base copy per the gate guide, not by changing this checkout's state. |
| H5 | CI | The merge candidate's full required suite is authoritative. Contract and unknown shared paths may broaden selection. Tests cover software logic, boundaries and build integrity, not real dataset contents or quality. Existing disk fixtures are used only for schema/contract verification. No live model call, workflow dispatch, external fetch, real baseline score assertion or production-data mutation is a CI gate. |
| H6 | Published/operator surfaces | Row 3 changes displayed rate availability and history. Use the single existing canonical browser journey and the mandated integrated smoke; no additional browser cases across themes, widths or data states. Empty/missing measurement assertions belong in unit/contract tests. Confirm the mandated missing-data rendering during the same manual smoke, with no new unrelated console errors/404s. Susan reviews the changed operator surface before merge. |
| H7 | Measurement | Use the existing installed metric libraries: scikit-learn for class metrics and SciPy for event-group resampling. Resample independent groups, not individual correlated pairs. Record group support and null intervals with a fixed reason when support or a denominator is insufficient. Report width is evidence, not a merge gate. No new dependency or custom statistics framework is required. |

## 1. Status Reckoner

Table I - Delivery rows

| Id | # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| I1 | 1 | Reject same-article comparisons in shared scoring | - | A | DONE | sturdy-sniffle | #1925 | Article identity fix |
| I2 | 2 | Run independent prepared plugin work through the council | - | A | DONE | symmetrical-potato | #1927 | Council plugin execution |
| I3 | 3 | Correct emitted evidence and judge statistics | 1, 2 | B | IN-FLIGHT | - | - | Judge evidence correction |
| I4 | 4 | Fit only adjustable comparisons and protect published decisions | 3 | C | PENDING | - | - | - |
| I5 | 5 | Deliver a frozen offline judge evaluator | 4 | D | PENDING | - | - | - |
| I6 | 6 | Establish the independently labelled current-judge baseline | 5 | M | PENDING | - | - | - |

## 2. Article identity

### Row #1 - Reject same-article comparisons in shared scoring

- **Scope:** Refuse a comparison between identical canonical article URLs in the shared eligibility predicate without deleting either published placement or weakening the pair contract.
- **Level:** 3 - shared article behaviour used by publication and judge selection.
- **Files touched:**
  - `backend/idhazh/assemble.py`
  - `backend/tests/test_same_story.py`
  - `backend/tests/test_similarity_selection.py`
  - `backend/tests/contracts/test_story_similarity.py`
  - `docs/architecture/publishing/autotune-content-similarity.md`
- **Acceptance gates:**
  - Local: H3-H4; one focused run of `backend/tests/test_same_story.py`, `backend/tests/test_similarity_selection.py`, `backend/tests/pipeline/test_same_story_window.py`, and `backend/tests/contracts/test_story_similarity.py`.
  - Add bounded same-day, current/earlier-day and earlier/earlier-day cases with different item IDs, desks and source labels but one canonical URL.
  - Include a third, genuinely distinct article; preserve valid coverage without letting duplicate placements enter one all-pairs group or inflate independent-source counts.
  - Exercise picker file I/O with minimal generated inputs at explicit temporary paths; verify contract-readable output, accurate population/budget/shard accounting and valid alternatives surviving. Do not add a recorded bug fixture.
  - Retain rejection of equal pair address keys, distinct-URL scoring, published IDs/order and missing-vector behaviour.
  - CI: H5; no live council dispatch.
- **Oracle:** The same-URL fixture produces no self-pair and no independent-coverage link between its placements, while distinct-URL comparisons still produce contract-valid selected rows; this cannot establish that two different URLs report the same event.
- **Decisions:**

Table J - Row 1 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| J1 | Add an early canonical-URL equality guard in `assemble._pair_terms`, shared by `cross_source_pairs`, `_group_fit` and group reporting; keep article logic out of council code. The current predicate has only window/number/headline/score gates. | Fowler; direct predicates in `backend/idhazh/assemble.py`. |
| J2 | The defect occurs because `_drawn_row` converts placement IDs into equal URL identities only after selection; its retained contract correctly requires strictly ordered, distinct address keys. Do not catch and skip that validation error. | `backend/idhazh/stages/pick_item_pairs.py`; `backend/idhazh/contracts/story_similarity_pair.py`; Fowler. |
| J3 | Preserve appearances and the all-pairs grouping rule. A duplicate placement may remain separately visible rather than claim independent corroboration. Update the existing eligibility explanation in place; no additional concept is introduced. | Fowler; `docs/architecture/publishing/autotune-content-similarity.md`. |

- **Rejected alternatives:**

Table K - Row 1 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K1 | Relax strict pair ordering or catch invalid rows after selection | Admits a self-pair or spends budget on work later discarded; it leaves shared grouping wrong. | Lost validation and inconsistent population/budget accounting, with no removal of the cause. | Fowler. |
| K2 | Rename a source or remove a duplicate placement upstream | Fixes one input representation without making retained days safe and changes unrelated source/placement behaviour. | A separate producer/identity/reader design and representative-selection rules; requires the bounded defect described in B2. | Fowler. |

## 3. Generic council execution

### Row #2 - Run independent prepared plugin work through the council

- **Scope:** Implement Tables C-E as one complete generic scheduling, preparation, transport and collection path, with only the existing judge's adapter changed to translate that interface.
- **Level:** 5 - plugin interface and retained zero-part records.
- **Files touched:**
  - `backend/idhazh/contracts/council_invocation.py` (new)
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/contracts/council_events.py`
  - `backend/idhazh/contracts/council_run_record.py`
  - `backend/idhazh/contracts/knobs/council.py`
  - `backend/idhazh/council/work_files.py` (new)
  - `backend/idhazh/council/tenancy.py`
  - `backend/idhazh/council/selection.py`
  - `backend/idhazh/council/night_plan.py`
  - `backend/idhazh/council/registry.py`
  - `backend/idhazh/council/session.py`
  - `backend/idhazh/council/deadline.py`
  - `backend/idhazh/council/outcome.py`
  - `backend/idhazh/council/run_summary.py`
  - `backend/idhazh/cli.py`
  - `backend/utilities/council_matrix.py`
  - `backend/utilities/council_publish.py`
  - `backend/idhazh/content_similarity_judge/tenant.py`
  - `backend/idhazh/stages/count_verdicts.py`
  - `.github/workflows/llm-council.yml`
  - `backend/tests/contracts/test_council_invocation.py` (new)
  - `backend/tests/contracts/test_council_run_record.py`
  - `backend/tests/contracts/_fixtures.py`
  - `backend/tests/council/test_work_files.py` (new)
  - `backend/tests/council/_config.py`
  - `backend/tests/council/_imports.py`
  - `backend/tests/council/_tenants.py`
  - `backend/tests/council/test_council_matrix.py`
  - `backend/tests/council/test_council_runs_without_a_judge.py`
  - `backend/tests/council/test_deadline.py`
  - `backend/tests/council/test_event_publication.py`
  - `backend/tests/council/test_events.py`
  - `backend/tests/council/test_failed_records.py`
  - `backend/tests/council/test_lifecycle.py`
  - `backend/tests/council/test_metrics_sink.py`
  - `backend/tests/council/test_night_plan.py`
  - `backend/tests/council/test_preflight.py`
  - `backend/tests/council/test_registry.py`
  - `backend/tests/council/test_publication.py`
  - `backend/tests/council/test_run_summary.py`
  - `backend/tests/council/test_selected_runs.py`
  - `backend/tests/council/test_selection.py`
  - `backend/tests/council/test_session.py`
  - `backend/tests/council/test_sparse_publication.py`
  - `backend/tests/council/test_trial_paths.py`
  - `backend/tests/workflows/test_llm_council_workflow.py`
  - `backend/tests/test_similarity_tenant.py`
  - `backend/tests/test_similarity_handoff.py`
  - `backend/tests/test_similarity_counting.py`
  - `tests/fixtures/council/selection_tenant.py`
  - `tests/fixtures/council/named_input_tenant.py`
  - `tests/fixtures/contracts/council-selection/scheduled.json` (new)
  - `tests/fixtures/contracts/council-preparation/ready.json` (new)
  - `tests/fixtures/contracts/council-shard-files/completed.json` (new)
  - `docs/architecture/publishing/llm-council.md`
  - `docs/architecture/publishing/llm-council-dates.md`
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:**
  - Local: H3-H4; run the oracle first, then the named council package, new invocation contracts, council-record contracts, workflow tests, and existing adapter/handoff/counting tests.
  - Add `backend/tests/council/test_selected_runs.py::test_preparation_isolated_by_judge_and_date_and_only_ready_work_runs` using minimal file-processing boundary plugins materialized from in-memory definitions in the existing test helpers, separate generated planner/worker/collector roots, and the local Git publisher. Assert only the explicitly named files and remote writes.
  - Cover a plugin declining every date, a plugin failing one date and preparing another, an empty draw requiring bookkeeping, and a ready unrelated plugin whose payload uses a non-selection slot and non-CSV format.
  - Verify unsafe paths, symlinks, duplicate destinations, identity/attempt/revision mismatches, missing files and changed bytes are refused before model startup; verify the collector's integrity gate still blocks unsafe publication.
  - Verify fatal exception-group members and cancellation propagate, while ordinary preparation/settlement failures retain valid siblings and unsuccessful aggregate status.
  - Keep paused-only/mixed trial isolation and named sparse inputs; round-trip historical and zero-part council rows through native and compact readers.
  - CI: H5. Observe the next ordinary scheduled run for ready-only dispatch and honest summary; observation does not add a recovery dispatch or replace fixture gates.
- **Oracle:** Exact dispatched cells equal valid ready receipts, valid empty work settles without shards, and independent permitted writes reach the fixture remote despite another preparation failure while the run stays unsuccessful; this cannot establish model quality or production runtime cost.
- **Decisions:**

Table L - Row 2 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| L1 | First move the existing selection/cell models without behaviour change; then land the entire new execution path in one behavioural commit in the same PR. Do not ship an interface whose production adapter arrives later. | Fowler. |
| L2 | The gardener validates before work, contains ordinary task errors, checks ownership and aggregates results. Reuse those semantics, not its deletion-task framework or fault vocabulary. Existing council settlement already continues siblings; preparation does not. | Fowler; `backend/idhazh/gardener/runner.py`; direct `council/session.py` preparation and settlement loops. |
| L3 | Mint invocation identity before the identity-bound selection. Add explicit run/attempt/commit inputs to planning and consumers as needed. Require validated selection for execution; remove `for_dates` authorization fallbacks in both utilities. Local callers generate an explicit manual selection instead of receiving implicit authorization from a date. | Fowler; direct `council/selection.py`, `council/night_plan.py`, and utility consumers. |
| L4 | Prepare the whole selection in Python when `council-prepare` has no explicit date; retain explicit date narrowing only inside the authorized selection. Replace the shell date loop. Fanout follows preparation and uses E10, not the original unconditional selected-date matrix. | Fowler; direct `.github/workflows/llm-council.yml` ordering and `council_matrix.cells`. |
| L5 | Add `council-shard --verify-only` before model setup and reuse its admission checks in actual execution. Its new closed `verify-work` event is not a shard exit report. Give collection `--planning-result` as well as `--units-result`; derive preparation expectations from D3 and shard expectations from the emitted matrix. | Fowler. |
| L6 | `work_files.py` validates only declared invocation files. Reject absolute paths, traversal, backslashes, globs, symlinks, non-regular files, duplicate destinations and ownership escapes. Separate incoming artifacts from canonical scratch and outgoing bundles; validate all identities/hashes before installation. Download bundles separately rather than merge unvalidated paths. Workers upload only their own outgoing bundle; remove slot-based upload exclusions. | Fowler; existing always-uploaded artifacts and whole-publication integrity predicate. |
| L7 | A dedicated native file-integrity exception is fatal to the phase and is translated into the existing publisher integrity refusal at the utility boundary. Keep cancellation, timeout and fatal exception-group members out of ordinary per-plugin catches. Do not print untrusted exception messages. | Fowler; Tables E and existing event/crash-printer contract. |
| L8 | The adapter implements its own scheduling using current date memory, declares actual task/verdict/metric files, and consumes receipts/reports. Make `expected_shards` and `reports_complete` required at `stage_count_verdicts`. Zero-work settlement supplies zero expected shards and no synthetic output; ready work uses its admitted width. Existing count/fit mathematics stay unchanged. | Fowler; direct `stage_count_verdicts` shard-count predicate and existing adapter no-work result. |
| L9 | Update all actual callers found by exact searches for `nights_outstanding`, `for_dates`, the moved model imports and `stage_count_verdicts`. Historical mentions in older plans remain historical, not runtime compatibility shims. Extend the named import inventory; do not weaken the no-judge import tests. | Fowler; discovered caller inventory reflected in Files touched. |
| L10 | Keep the two council architecture pages for their existing separate questions: execution/transport and judge/date selection. Put the invocation/retained compatibility distinction on the schema page. No new model resources, registry statuses or config values are needed. | Fowler. |

- **Rejected alternatives:**

Table M - Row 2 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M1 | Continue the shell loop or add `continue-on-error` | Does not establish which plugin/date prepared valid work and can launch jobs without admitted inputs. | Ambiguous completion and duplicated shell/application policy; still needs an evidence contract. | Fowler. |
| M2 | Create a preparation job per date or a new message broker | Independent jobs do not by themselves define readiness, no-work bookkeeping or safe transport. | Extra runner starts/installations, artifacts and coordination; a broker adds a new service without a consumer that requires it. | Fowler. |
| M3 | Keep forced default dates and launch empty model jobs | Prevents a plugin declining work and spends startup cost before it can say no work. | Repeated unnecessary runner/model setup; conflicts with the chosen plugin boundary. | Fowler. |
| M4 | Treat missing output as no work or fabricate empty shard records | Erases failed/cancelled work or records steps that never ran. | Unrepairable date memory and false success; no valid compatibility benefit. | Fowler. |

## 4. Correct interpretation of judge evidence

### Row #3 - Correct emitted evidence and judge statistics

- **Scope:** Implement F1-F5 and F11, one production model-reader seam, and corresponding native/frontend readers without changing the model or question asked.
- **Level:** 5 - changed evidence validity, retained measurement identity and nullable rates.
- **Files touched:**
  - `backend/idhazh/llm/server.py`
  - `backend/idhazh/content_similarity_judge/model_reader.py` (new)
  - `backend/idhazh/similarity/statistics.py` (new)
  - `backend/idhazh/similarity/judge.py`
  - `backend/idhazh/similarity/stamps.py`
  - `backend/idhazh/similarity/counting.py`
  - `backend/idhazh/similarity/fit.py`
  - `backend/idhazh/stages/judge_item_pairs.py`
  - `backend/idhazh/stages/count_verdicts.py`
  - `backend/idhazh/stages/set_merge_line.py`
  - `backend/idhazh/contracts/story_similarity_pair.py`
  - `backend/idhazh/contracts/story_similarity_distribution.py`
  - `backend/idhazh/contracts/content_similarity_judge_metrics.py`
  - `backend/idhazh/contracts/fitted_similarity_threshold.py`
  - `backend/tests/support/judge_reader.py` (new)
  - `backend/tests/test_completion_evidence.py` (new)
  - `backend/tests/test_similarity_statistics.py` (new)
  - `backend/tests/test_similarity_judge.py`
  - `backend/tests/test_similarity_counting.py`
  - `backend/tests/test_similarity_fit.py`
  - `backend/tests/contracts/test_story_similarity.py`
  - `backend/tests/contracts/test_content_similarity_judge_metrics.py`
  - `backend/tests/contracts/test_frontend_console_lists.py`
  - `backend/tests/contracts/test_schema_drift.py`
  - `backend/tests/contracts/_fixtures.py`
  - `frontend/src/lib/server/content-similarity-judge.ts`
  - `frontend/src/lib/console/merge-line.ts`
  - `frontend/src/routes/console/judgement/+page.server.ts`
  - `frontend/src/routes/console/judgement/JudgeAgreement.svelte`
  - `frontend/tests/merge-line.spec.ts`
  - `frontend/tests/similarity-ledgers.spec.ts`
  - `frontend/tests/judgement-evidence.spec.ts`
  - `frontend/tests/console-judgement-nothings.spec.ts`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/summarize/model-boundary.md`
- **Acceptance gates:**
  - Local: H3-H4; focused new emission/statistics tests, judge/count/fit tests and affected native contracts. Include dependent completion consumers: `backend/tests/test_summarize.py`, `backend/tests/test_classify.py`, `backend/tests/test_item_records.py`, `backend/tests/test_telemetry.py`, and `backend/tests/test_measure_judge_call.py`.
  - Use minimal in-memory native-format inputs for YES, NO, split UNCLEAR, leading space, absent/malformed evidence and the thinking answer span. Selected `Sure` with returned YES must still be refused, without loading a recorded bug payload.
  - A minimal in-memory protocol input puts an illegal alternative above a legal emitted token; the answer must remain accepted. These inputs prove parser logic, not a model's actual answers.
  - Verify emitted evidence survives `one_reply` from the answer, not the thinking span; retain optional defaults for unrelated callers.
  - Compare forward-refused/reverse-valid and forward-valid/reverse-refused cases, valid YES/NO disagreement, agreed UNCLEAR and two refusals. Verify zero denominators, stamp-before-recency filtering, archive-before-reset and no repeat reset.
  - Run frontend field/vocabulary bindings and selected merge-line/ledger logic checks; perform H6 on the existing operator surface with mixed historical/current policies and unavailable rates.
  - CI: H5, including retained contract fixtures and the existing representative console coverage.
- **Oracle:** Swapping which order failed and splitting/recombining completed pairs leave refusal counts and derived valid-reading rates unchanged, while actual emitted evidence rather than alternative rank determines acceptance; this cannot establish verdict accuracy.
- **Decisions:**

Table N - Row 3 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| N1 | The parser sorts `top_logprobs`, and the judge currently treats its first element as the emitted answer. Native fixtures already hold selected-token fields separately. Use F1-F2; keep alternative windows diagnostic. The recorded probability benchmark describes an older runtime and is not a current-model frequency measurement. | Andre; direct `llm/server.py` probability parser and `similarity/judge.py` answer check; existing native response fixtures. |
| N2 | Missing emitted evidence is now explicitly refused for this judge, not silently accepted as a literal-only proof. This stricter behaviour needs its own policy stamp, compatible readers and tests; other completion consumers do not inherit judge-only refusal policy. | Andre; F2 and F5. |
| N3 | Extract existing reader construction into `ModelReader(client, markers)` in the judge package. Allow the stage to receive an in-memory boundary reader; default production construction retains endpoint resolution, template/tokenizer checks and the existing post function. Convert the judge tests away from their listener and recorded business-logic payloads rather than introduce new network tests or mock internal judge logic. | Existing stage reader-construction call site; current test policy. |
| N4 | One `similarity/statistics.py` calculation serves shard and fit writers. The current fit selects on the first verdict alone while shard metrics use both valid readings; F3 fixes that order asymmetry. Filter current instrument before pair recency. | Andre; direct `judge_item_pairs._instrument_reading`, `stage_set_merge_line` and `counting.rows_the_record_admits`. |
| N5 | Introduce the judge policy before its new writers. Reuse the aggregate archive/reset mechanism, with the archive-success requirement in F8 from its first use here. Carry date memory and preserve historical readings; do not pretend old refusal denominators are reconstructable. | Andre; direct aggregate loader/reset and `record_stamp`. |
| N6 | Update the frontend reader before nullable rates are written. It currently rejects a valid line when either rate is absent. Retain the line, show gaps for absent rates, retain historical method identity and do not join series across method changes. This is data correctness, not a visual redesign. | Andre; direct `frontend/src/lib/server/content-similarity-judge.ts` required-measurement predicate. |
| N7 | Row 3 waits for row 1's shared judge document/contract tests and row 2's count-stage, fixture-registry and schema-page edits. Neither algorithm becomes platform-owned because of this integration order. | Exact Files touched intersections. |

- **Rejected alternatives:**

Table O - Row 3 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O1 | Trust the highest alternative or accept missing evidence | Confuses candidate probability with emitted output or loses patched-answer detection. | Selective refusal of valid outputs, or acceptance without the required evidence; a new runtime capture would not fix the predicate. | Andre. |
| O2 | Reword the prompt or add retries to improve these rates | Does not repair evidence interpretation or asymmetric denominators. | More model calls, correlated selection bias and a new instrument without an accuracy finding. | Andre. |
| O3 | Fill missing rates with zero or rewrite historical values | Presents absence as perfect agreement and invents old denominators. | Misleading console history and silent contract reinterpretation. | Andre. |

## 5. Correct threshold calibration

### Row #4 - Fit only adjustable comparisons and protect published decisions

- **Scope:** Implement F6-F10 so the fitted threshold uses only comparisons it can change and sampling protects the decisions the published build actually used.
- **Level:** 5 - retained calibration identity and aggregate reset.
- **Files touched:**
  - `backend/idhazh/similarity/counting.py`
  - `backend/idhazh/similarity/published_line.py` (new)
  - `backend/idhazh/stages/count_verdicts.py`
  - `backend/idhazh/stages/set_merge_line.py`
  - `backend/idhazh/stages/pick_item_pairs.py`
  - `backend/idhazh/contracts/story_similarity_distribution.py`
  - `backend/idhazh/contracts/fitted_similarity_threshold.py`
  - `backend/tests/test_similarity_counting.py`
  - `backend/tests/test_similarity_fit.py`
  - `backend/tests/test_similarity_selection.py`
  - `backend/tests/test_similarity_published_line.py` (new)
  - `backend/tests/contracts/test_story_similarity.py`
  - `backend/tests/contracts/test_schema_drift.py`
  - `backend/tests/contracts/_fixtures.py`
  - `docs/architecture/publishing/autotune-content-similarity.md`
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:**
  - Local: H3-H4; focused counting, fit, selection and new published-line tests plus affected historical contract fixtures and `backend/tests/test_similarity_applied.py`.
  - Add arbitrary usable headline YES/NO audit rows and verify identical calibration slots, proposal, subtractable daily counts and current-policy shift history.
  - Verify old aggregate bytes are archived before replacement, all date memory survives, an unavailable archive prevents reset, and unchanged subsequent input does not reset again.
  - Exercise manifest ordering, equal completion instants, missing timestamps, absent manifest, legacy null and malformed-present data.
  - With a published threshold below the configured floor and a tight budget, retain every in-band pair above that published threshold; keep the band's population unchanged.
  - CI: H5; adaptive activation and its existing flag/default remain unchanged.
- **Oracle:** Headline-only audit additions leave calibration counts/proposals unchanged and mandatory selection follows the last published build's recorded line without moving the band; this cannot establish that any fitted value is safe to activate.
- **Decisions:**

Table P - Row 4 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| P1 | The shared scorer forces matching-headline scores to one regardless of cosine, but current `day_counts` admits them. Raising the adjustable threshold cannot correct such a match. Keep the audit and separate the calibration population, as the existing threshold holdout already does. | Andre; direct `assemble._pair_terms`, `similarity/counting.py`, and `similarity/holdout.py`. |
| P2 | Slot totals no longer retain per-pair headline identity, so old totals cannot be repaired by subtraction. Use the additional calibration policy and F8 rather than reinterpretation or a backfill. | Andre; retained distribution fields and existing reset path. |
| P3 | The picker currently passes configured `floor_min` even though `RunRecord.same_story_floor_applied` exists. F9 follows the latest-completed-build rule already used by the frontend, but fails malformed present input rather than hiding it. No manifest schema change is needed. | Andre; direct picker call, manifest field and `frontend/src/lib/server/recorded-line.ts`. |
| P4 | The band remains config-owned. Only the mandatory/budget split follows the recorded published threshold; do not feed a fitted line into band edges or prompt inputs. The defect is latent while adaptation remains disabled, not evidence to enable it. | Andre; current selection-band test and adaptive reader. |
| P5 | Row 4 follows row 3 because it shares counting, fit, retained contracts, fixture registration and canonical docs, and must preserve row 3's new interpretation identity. Keep both policy fields explicit rather than one flag with two meanings. | Exact Files touched intersections; Andre. |

- **Rejected alternatives:**

Table Q - Row 4 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Q1 | Drop headline overrides from persistence or stop judging them | Removes the audit of a rule that can still make wrong merges. | Loss of evidence for the non-adjustable branch; any removal needs its own reader trade-off. | Andre. |
| Q2 | Move the sampling band with the applied line | Lets the fit choose its next evidence population. | A feedback loop and a new sampling/calibration design that needs independent evaluation. | Andre. |
| Q3 | Reconstruct the old population from retained aggregate slots or today's fitted history | Neither supplies the original per-pair population and applied build decision. | A bounded full-evidence reconstruction study; until available it would be guessing. | Andre. |

## 6. Offline evaluation capability

### Row #5 - Deliver a frozen offline judge evaluator

- **Scope:** Implement Table G's real freeze/capture/score path with the production judge reader and honest incomplete-evidence reporting, without adding any production action.
- **Level:** 5 - new persisted private evaluation documents.
- **Files touched:**
  - `backend/idhazh/contracts/content_similarity_judge_evaluation.py` (new)
  - `backend/idhazh/contracts/__init__.py`
  - `backend/idhazh/content_similarity_judge/freeze_evaluation.py` (new)
  - `backend/idhazh/content_similarity_judge/run_evaluation.py` (new)
  - `backend/idhazh/content_similarity_judge/score_evaluation.py` (new)
  - `backend/idhazh/content_similarity_judge/settings.py`
  - `backend/idhazh/contracts/knobs/content_similarity_judge.py`
  - `backend/utilities/evaluate_content_similarity_judge.py` (new)
  - `config/judges/content-similarity-evaluation.json` (new)
  - `backend/tests/test_content_similarity_judge_evaluation.py` (new)
  - `backend/tests/contracts/test_content_similarity_judge_evaluation.py` (new)
  - `backend/tests/contracts/test_content_similarity_judge_config.py`
  - `backend/tests/contracts/_fixtures.py`
  - `tests/fixtures/contracts/content-similarity-judge-evaluation-set/example.json` (new)
  - `tests/fixtures/contracts/content-similarity-judge-evaluation-labels/example.json` (new)
  - `tests/fixtures/contracts/content-similarity-judge-evaluation-run/example.json` (new)
  - `tests/fixtures/contracts/content-similarity-judge-evaluation-report/example.json` (new)
  - `docs/how-to/evaluate-content-similarity-judge.md` (new)
  - `docs/architecture/contracts/schemas.md`
- **Acceptance gates:**
  - Local: H3-H4; new evaluator unit/integration/contract tests, native schema round-trips and the existing no-judge-import checks.
  - Drive the production request builder and evaluator through the in-memory boundary reader using minimal inputs. Assert identical request bytes for the same frozen inputs and identity-bound response capture, without asserting a real model's quality.
  - Validate set/case/input hashes, event/article split disjointness, unknown/duplicate cases, rubric mismatch, stale labels, conflicting or missing independent annotations, refusal/disagreement denominators and incomplete captures.
  - Verify blind export excludes source-label metadata, model output and similarity scores, yet includes the exact sanitized summaries sent to the model; do not strip factual names from summary text.
  - Verify attempted external fetch, production-state output and destination override cannot be introduced through set/model text. Output paths derive from explicit operator roots and recomputed identities.
  - Test count/precision/recall/coverage arithmetic against the existing metric libraries, including absent classes and clustered interval support. Changing H2 must change the relevant limits/report arithmetic without source edits.
  - CI: H5. Tests use minimal in-memory boundary inputs, not recorded business-logic responses, a listener, weights download or live model process.
- **Oracle:** The evaluator sends the production judge's exact request bytes and accounts for every declared case without converting unavailable labels or failed readings into negatives; this proves the measurement path, not model accuracy.
- **Decisions:**

Table R - Row 5 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| R1 | Do not reuse the existing retrieval/cluster report as a judge-accuracy report: its evaluator requires vectors and rankings/memberships, and its contract declares that separate scope. Reuse metric libraries and native article/verdict/identity types, not an incompatible result shape. | Andre; direct `story_dataset/evaluation.py` prerequisites and `contracts/story_evaluation.py` report scope. |
| R2 | Add only the four versioned documents in G1-G4. Their schema stems match the named fixture directories in Files touched. Register named inputs, never discover fixtures or source days through a walk. Transcripts stay private evidence and never become trusted instructions or paths. | Andre; native contracts and trust boundary. |
| R3 | The utility exposes explicit `freeze`, `capture`, `score` operations, with named input/output paths and the shared config root. Capture uses the selected committed model and production reader; score consumes captured data with no model call. No council enrollment, workflow, ledger or activation flag is added. | Andre. |
| R4 | Build-independent tests use minimal in-memory protocol inputs and prove software rules, not model quality. The new documents each receive one minimal schema example; edge cases remain in memory. Those examples are not human gold or model recordings. The evaluator can truthfully report blocked while its code is fully usable; G7 keeps the missing baseline as separate work. | Current test policy; row sizing by separately verifiable outcome. |
| R5 | Keep article/event splits and representative/challenge results separate. Label and capture coverage remain visible even when quality metrics are blocked. Existing model-labelled marks cannot become independent confirmation labels by renaming their origin. | Andre. |
| R6 | The new how-to owns operator freeze/capture/score and labelling steps. The schema page owns compatibility. No broad rewrite of the long similarity architecture page is needed for an independently usable offline procedure. | Documentation split test; Andre. |
| R7 | Row 5 integrates after row 4 because native contract registration, fixture inputs and schema documentation overlap, and captures must carry the corrected policy identities. No new live measurement blocks rows 1-4. | Exact Files touched and input dependencies. |

- **Rejected alternatives:**

Table S - Row 5 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| S1 | Call two-order agreement or the threshold holdout judge accuracy | Measures consistency or threshold decisions, not correctness of model verdicts. | False confidence without independently checked truth. | Andre. |
| S2 | Add a second model, confidence cutoff or automatic promotion | No scoped evidence establishes a gain or calibrated confidence. | Extra calls, model/resource decisions and a separate acceptance policy; row 6 must first identify the relevant error. | Andre. |
| S3 | Adapt the retrieval/cluster evaluator wholesale | Its vector/universe prerequisites and metrics answer another question. | Unnecessary source/catalog/vector coupling and misleading report scope; a small native judge report is less code to maintain. | Andre; direct prior-art check. |

## 7. Independent quality evidence

### Row #6 - Establish the independently labelled current-judge baseline

- **Scope:** Freeze a real bounded confirmation set, obtain G2's independent annotations, capture the unchanged current judge and preserve its first correctly qualified quality reading.
- **Level:** 3 - measured evidence under row 5's declared private contracts; any model/prompt/adoption change escalates under A7.
- **Files touched:**
  - `docs/reference/benchmarks/content-similarity-judge-current-set.json` (new real evidence)
  - `docs/reference/benchmarks/content-similarity-judge-current-labels.json` (new real evidence)
  - `docs/reference/benchmarks/content-similarity-judge-current-run.json` (new real recording)
  - `docs/reference/benchmarks/content-similarity-judge-current-report.json` (new real reading)
  - `docs/reference/benchmarks/how-accurately-the-similarity-judge-decides.md` (new)
- **Acceptance gates:**
  - Before work: obtain the independent annotation resource and the explicitly controlled model process. If either is absent, mark this row blocked with the exact missing input; do not block completed code rows or invent substitutes.
  - Fix the named source snapshots, rubric, event groups, split and case list before viewing confirmation predictions. Keep investigated/development examples out of confirmation groups.
  - Include independently labelled paraphrases, changed actors/numbers/occasions, follow-ups, reactions, genuinely vague summaries and planted-instruction variants from several independent events; tag challenge cases and keep their results separate.
  - Run capture explicitly through row 5's tool, then score the frozen capture offline. No production council command, state write or historical recovery run is permitted.
  - Preserve the actual finite sample counts, full outcome/class coverage, false-merge and missed-match directions, uncertainty/support, refusals and order disagreements; retain current model/config/policy and host identities with UTC conditions.
  - Operator validation: validate the real evidence against G1-G4 and score it offline through the utility. Preserve the exact result beside its benchmark page; do not turn real sample contents or scores into pytest assertions.
  - CI: document/format/build checks under H5 only, never inference, human labelling or a real dataset-quality gate. The actual capture and offline scoring are measurements, not repeatable merge gates.
- **Oracle:** Offline scoring of the frozen, independently labelled real capture reproduces its exact counts and coverage, with qualified labels for every confirmation case; this cannot establish population-wide accuracy, choose a better model or justify activation without another decision.
- **Decisions:**

Table T - Row 6 decisions

| Id | Decision | Authority |
| --- | --- | --- |
| T1 | Separate this row from the evaluator PR. Independent annotation is external work and actual inference is measurement; a tested harness does not supply either. Keep this row pending/blocked until the real outcome exists. | Andre; execution row-sizing rule. |
| T2 | Do not invent a target accuracy, minimum useful model difference or required passing sample count. Name the selected finite case population and report uncertainty; inadequate support is a finding about the measurement, not permission to claim success or change the model. | Andre; current evidence limitations. |
| T3 | Use H2 for report settings and H7 for uncertainty. Record hardware for the actual capture; developer-host elapsed time does not establish runner throughput. Run the measuring row without competing tests or inference. | Measurement convention and execution contract. |
| T4 | The benchmark page records the current result, method, provenance, scope and limits. It does not record approval history or make an activation ruling. Real captured replies are recorded evidence, not fabricated fixtures or reproducible build intermediates. | Andre; documentation ownership and G7. |

- **Rejected alternatives:**

Table U - Row 6 rejected alternatives

| Id | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| U1 | Relabel existing model marks as independent truth | Conceals circular evaluation and the narrow event coverage. | A human review of the actual frozen inputs is still required; skipping it removes the meaning of the result. | Andre. |
| U2 | Mark the baseline done with a blocked report or a passing replay test | Confuses working software with measured quality. | Lost visibility of unfinished external inputs and no answer about actual verdict correctness. | Andre. |
| U3 | Benchmark inside the scheduled production workflow | Adds committed side effects and couples judge measurement to platform execution. | Runner/model budget, lifecycle, retention and publication design beyond this offline baseline; B5 names the entry condition. | Fowler; Andre. |

## See also

- [Plan authoring](../docs/how-to/author-a-plan.md)
- [Plan execution](../docs/how-to/execute-a-plan.md)
- [Gate commands](../docs/how-to/run-the-gates.md)
- [Council execution](../docs/architecture/publishing/llm-council.md)
- [Judge/date selection](../docs/architecture/publishing/llm-council-dates.md)
- [Content-similarity rules](../docs/architecture/publishing/autotune-content-similarity.md)
- [Model boundary](../docs/architecture/summarize/model-boundary.md)
- [Documentation structure](../docs/reference/documentation-structure.md)
