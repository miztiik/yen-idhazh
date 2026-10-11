# Summary fidelity judge

**Last Updated**: 2026-10-11
**Level**: 5 (CLAUDE.md section 6). Row #3 declares a persisted shape, approved as P1 and amended by P13; every other row states its own level.
**Status**: drafted 2026-10-11 from the drift-review plan of 2026-10-10, whose 16 review changes the owner approved (Table R). The owner then ruled to stop the drift review, to store every check in a ledger under state/raw/ in parquet, and to run the work as a judge in the LLM council. The owner ruled P1 to P19 on 2026-10-11 (P12 deferred to row #8's replay), ruled E1, F1 and G1, ruled that determinism is not an expectation (C10), and dropped rows #10 and #11 (D3). **Hold (owner, 2026-10-11): the owner disapproved judging per site** - the judge must judge summary quality across the digest - and the ledger is drift-evals. The hard look the owner asked for is done: a research survey (TODO/20261011-summary-quality-metrics-research-record.md) and Andre's and Fowler's reviews (TODO/20261011-summary-fidelity-judge-review-record.md). Section 4 proposes the redesign; P20 to P38 await the owner, and rows #2 to #14 are rewritten once they are ruled. Table Q tracks every open request. No row started.

## 0. Operating contract

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The weekly drift review compares per-site medians against fixed percentage thresholds. A median jumps between two kinds of page when their shares cross one half, so a change in a site's mix of story types reads as drift (issue #1270); the thresholds ignore sample size and per-site spread; every result lives only in a GitHub issue that nothing can query; and the review runs in a workflow of its own, outside the council where the project's judges run. |
| A2 | Hard scope - in | - The drift review, its workflow and its settings are deleted (row #1)<br>- The judge's settings in a config file of its own, every number bounded, and site identity: the host, listed multi-tenant hosts, declared page types (row #2)<br>- The judge's ledger under state/raw/ and state/compact/, enrolled for compaction and retention, its tenant module, and its council entry, paused (row #3)<br>- Measures declared in the settings file and tested by kind, with a registry that refuses a bad declaration before any check runs (row #4)<br>- Six measures, each with a p-value: article count (row #5), unusually short articles and page furniture (row #6), article length, copied phrases and faithfulness (row #7)<br>- One false-discovery step per judged date, and a replay that measures false crossings and detection (row #8)<br>- The switch: the judge's council entry turns active (row #9)<br>- The stored checks on a console page (row #12)<br>- An all-sites comparison and a combined-measures check (row #13)<br>- A long-baseline comparison (row #14) |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | The owner-supplied blueprint of 2026-10-10 with the 16 review changes the owner approved on 2026-10-10 (Table R), built from the first row as a tenant of the LLM council (docs/architecture/publishing/llm-council.md), never as a stage of drift.yml that later moves (P8). Reviewed by Fowler (contracts, structure, process safety) and Andre (metric and evaluation design). |
| A6 | Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows #3 to #8 run in order because each edits the judge's settings file, tenant module, tests or doc; rows #5 to #7 each need only row #4, but share the settings file, the declaration contract and the judge's page. Row #3 waits for the council plan's row 'Judges carry a status and a model need'. Rows #12 and #13 can run side by side; row #14 follows row #13, whose files it shares. |

### Hard scope - out

Table B - what is out, and what would bring it in

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Any change to what the pipeline fetches, extracts, summarizes or publishes | A crossed check still needs a person to inspect extraction | A crossing that a person confirms as an extraction defect, handled in its own plan |
| B2 | Acting on a crossed check, or on any score built from checks, by itself: stopping publication, resting a feed, demoting rank, marking items, moving a knob, changing a prompt, rewriting a summary | A real defect publishes until a person acts | An owner ruling that names one action for one check, once a ledger of a person's marks on crossings - filed through the door by a utility, as holdout-pairs is, keyed on H4.5's key and read by newest mark - measures the share of that check's crossings a person confirms. The action then takes a staged path: the judge files the proposed value as a row and never edits config; the stage that acts reads the latest row in its own build, damped, step-capped and clamped to its declared range; it ships behind a default-off flag that only records what it would have done, for a period the ruling names; it lifts itself when the evidence ends. Coverage and ranking stay the Editor's call (CLAUDE.md section 14) and the standing permission the owner's (Level 5); a model entry, temperature, repetition penalty, prompt or grammar never moves this way (P15) |
| B3 | GitHub issues, and any other notification | Nobody is told. A person reads the console panel (row #12), which shows a judged date once the gardener packs it and the site rebuilds, one to two days after the night that judged it | An owner ruling that one check warrants a notification, sent by a separate reader of the judge's ledger |
| B4 | Feed rest and retirement rules | A stopped feed is reported twice: feed-health rests it after five empty reads, and row #5's check crosses | A ruling that row #5 replaces part of feed quarantine |
| B5 | Judged dates before the judge's first night | The stored history starts at the switch. A person can judge a past date by dispatching the council with it, one date per run; the council's concurrency group keeps only one waiting run, so dispatches go one at a time, and each dispatch also runs every other active judge on that date, at its model cost | An owner ruling that history before the switch matters, priced in council runs |
| B6 | Moving the content-similarity judge's settings into a file of their own | The two judges keep their settings in two different places | A plan that moves them; this plan only sets the pattern for a new judge |
| B7 | Any check during the gap between row #1 and row #9 | No drift check runs while the judge is built | The owner rated the old review's output useless; nothing brings the old review back |
| B8 | Repairing a night only this judge missed, until the council plan's row 'Each judge runs over its own outstanding dates' lands: until then its nights_outstanding names no date | That date's rows stay missing; the next night's window shares six of its seven days. A night the whole council missed is still judged when another judge names it, because a council date runs every tenant | That council row, approved as the council plan's P2 on 2026-10-11 and built now; once it lands this judge's nights_outstanding names its own missed dates inside the repair window (Table Q, Q14) |
| B9 | Removing determinism_violation, an eval-row column a production run never sets, kept because committed days carry it and the console reads it (docs/architecture/contracts/determinism.md) | Every eval row keeps a column that is false in production | A plan of its own: drop the console's reader and the training-corpus filter, then the column with its read-side migration (CLAUDE.md section 11); the owner expects it to go |
| B10 | Checks against a fixed article set: a scorer reference set or a golden set (rows #10 and #11, collapsed) | A scorer-library upgrade under one scorer_version reads as faithfulness crossings on many sites in one night, and nothing names the library | An owner ruling that keeps a fixed article set beyond the site's housekeeping, or a scorer_version that also names the installed scorer libraries, so an upgrade opens a new model-and-scorer pair (L1.2) |
| B11 | A stamp on the eval row per scored column, narrower than scorer_version: the faithfulness scorer's revision, weights and window for hhem; METRICS_VERSION for the counterweights | Each scorer_version move restarts the series of copied_phrase_share, faithfulness and page_furniture and keeps them out of the step for up to 14 days per site, even a move of band thresholds alone; page_furniture cannot join the long baseline (row #14) | A plan of its own that changes the eval row (Level 5); the three declarations then retire, and new slugs group on the narrow stamps (G1.4) |

### ESCALATE triggers

Table C - when to stop and ask; C5 and C8 are standing rules and do not stop

| # | Name | Trigger | What happens |
| --- | --- | --- | --- |
| C1 | Stored shape | A row would declare a persisted shape: a contract under backend/idhazh/contracts/ read by a later run, a ledger, or a committed reference file with expected values | Stop. The owner rules on the shape (CLAUDE.md section 0). Row #3's shape was approved as P1 on 2026-10-11 |
| C2 | New dependency | A row needs a new runtime dependency, or a model or extra the council's jobs do not install today | Stop. Name the cost and the beneficiary (Guardrail #8); consult Carmack for runner minutes. scipy was approved as P7 on 2026-10-11 |
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
| 2 | The judge's settings file and site identity | - | A | PENDING | - | - | - |
| 3 | The judge's ledger and its tenant module | 2; council plan: Judges carry a status and a model need | B | PENDING | - | - | - |
| 4 | Metric declarations, the kind registry and the note kind | 3 | C | PENDING | - | - | - |
| 5 | Count kind: article count from the item-health census | 4 | D | PENDING | - | - | - |
| 6 | Share kinds: unusually short and page furniture | 5 | E | PENDING | - | - | - |
| 7 | Distance kind: article length, copied phrases and faithfulness | 6 | F | PENDING | - | - | - |
| 8 | One false-discovery step per judged date, and the replay | 7 | G | PENDING | - | - | - |
| 9 | The switch: the judge joins the council | 1, 8 | H | PENDING | - | - | - |
| 10 | Scorer reference check | 9 | I | COLLAPSED (owner, 2026-10-11, D3, with both reviewers: a fixed article set does not survive the site's housekeeping, and its test expected an exact repeat; B10) | - | - | - |
| 11 | Golden-set check | 9 | I | COLLAPSED (owner, 2026-10-11, D3, with both reviewers; B10) | - | - | - |
| 12 | The stored checks on a console page | 9 | I | PENDING | - | - | - |
| 13 | All-sites comparison and combined-measures check | 9 | I | PENDING | - | - | - |
| 14 | Long-baseline comparison | 13 | J | PENDING | - | - | - |

## 2. Rows

### Row #1 - The drift review is deleted

- **Scope:** .github/workflows/drift.yml, backend/idhazh/drift.py, backend/utilities/drift_report.py, backend/tests/test_drift.py and the drift block of config/idhazh.json are deleted, a config that still spells the block is refused by name, and every doc that describes the review points to this judge instead.
- **Level:** 3 (deletes a workflow and a config block).
- **Files touched:**
  - .github/workflows/drift.yml (deleted)
  - backend/idhazh/drift.py (deleted)
  - backend/utilities/drift_report.py (deleted)
  - backend/tests/test_drift.py (deleted)
  - backend/idhazh/contracts/knobs/evaluation.py (DriftConfig deleted)
  - backend/idhazh/contracts/app_config.py (the drift field deleted; SUPERSEDED_APP_NAMES gains drift with the message that min_articles and min_window_rows moved to config/judges/summary-fidelity-judge.json, that each setting E1.3 moved went to its reader's block, and that every other drift setting is gone; one changelog entry, the oldest entry deleted to keep five as CLAUDE.md section 11 allows; the validator's docstring names drift)
  - config/idhazh.json (the drift block deleted)
  - backend/tests/contracts/test_app_config.py and backend/tests/contracts/test_retired_knobs.py (re-derive at dispatch)
  - backend/tests/workflows/test_triggers.py and backend/tests/workflows/test_workflow_inputs.py (re-derive with git grep -n drift.yml backend/tests at dispatch)
  - docs/concepts/evaluation.md ("Per-item scores cannot see drift": the instrument is this judge's checks over the eval ledger; the fixed set and its refresh move to rejected alternatives with the reason in B10; "A deterministic output can change" becomes "An output can change") and docs/concepts/growing-reads.md
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

### Row #2 - The judge's settings file and site identity

- **Scope:** config/judges/summary-fidelity-judge.json holds every number the judge uses (Table F1), validated by a model that forbids unknown keys and bounds every field and read only by the judge's own package, with each setting landing in the first row that reads it; this row lands the two site settings, and site.py decides a site and a page type: a site stays the host without a leading www., a host listed in multi_tenant_hosts (F1.9) adds its first path segment, and page_types (F1.10) names the path prefixes that mark a page type inside one site.
- **Level:** 3 (decides how every check is grouped).
- **Files touched:**
  - config/judges/summary-fidelity-judge.json (new)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py (new: SummaryFidelityJudgeConfig, imported only by backend/idhazh/summary_fidelity/settings.py, never by backend/idhazh/config.py or a knobs re-export)
  - backend/idhazh/summary_fidelity/__init__.py (new)
  - backend/idhazh/summary_fidelity/settings.py (new: loads and validates the file)
  - backend/idhazh/summary_fidelity/site.py (new)
  - backend/tests/summary_fidelity/test_settings.py (new)
  - backend/tests/summary_fidelity/test_site.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md (new: the judge's own page)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** the committed file loads, and a file with an unknown key or a value outside its declared range is refused naming the key; a fixture of addresses maps to the expected site and page type: a www host to its host; news.mongabay.com and india.mongabay.com to two sites; a host with no public suffix to itself; substack.com/@name to its own site; a /short-article/ address on news.mongabay.com to that site with type short_article. Cannot settle: which live sites change grouping; row #8's replay lists them.

Table F1 - settings this plan declares (named once here; every row points here)

| # | Setting | Default | Allowed range | Meaning | Lands in | Source |
| --- | --- | --- | --- | --- | --- | --- |
| F1.1 | recent_days | 7 | 7 to 28, whole weeks | Days in the recent window, ending on the judged date | 4 | Blueprint; owner, 2026-10-10 (R6) |
| F1.2 | baseline_days | 28 | 7 to 91, whole weeks | Days in the baseline window, ending the day before the recent window starts | 4 | Blueprint |
| F1.3 | min_articles | 20 | 5 to 200 | Articles each side of a check needs before it is tested; was min_domain_rows | 4 | drift.py; owner, 2026-10-10 (R10) |
| F1.4 | min_window_rows | 20 | 1 to 1000 | Rows each whole window needs; below it the judged date stores one window_rows row and no check | 4 | drift.py |
| F1.5 | short_tail_percentile | 0.05 | 0.01 to 0.25 | Baseline percentile whose length defines an unusually short article | 6 | Blueprint section 1 |
| F1.6 | reshuffle_stop_hits | 10 | 1 to 100 | Reshuffling stops once this many reshuffles give a distance at least as large as the observed one (a tie counts) | 7 | Owner, 2026-10-11 (P4) |
| F1.7 | reshuffle_cap_floor | 100000 | 1000 to 10000000 | The smallest cap on reshuffles per check | 7 | Owner, 2026-10-11 (P4) |
| F1.8 | reshuffle_cap_multiple | 10 | 1 to 100 | The cap is the larger of reshuffle_cap_floor and this times the tested checks in the run divided by false_discovery_rate, minus one, counted before any reshuffle | 7 | Owner, 2026-10-11 (P4) |
| F1.9 | multi_tenant_hosts | substack.com, medium.com, github.com | host names | Hosts whose first path segment names its own site | 2 | Blueprint section 3; owner, 2026-10-10 (R7) |
| F1.10 | page_types | news.mongabay.com: short_article = /short-article/, video = /video/ | per host, path prefixes | Path prefixes that name a page type inside one site; any other address is type other | 2 | Owner, 2026-10-10 (R5) |
| F1.11 | false_discovery_rate | 0.05 | 0.001 to 0.2 | Target share of false crossings among the checks that cross, averaged over judged dates | 8 | Blueprint section 5 |
| F1.12 | crossings_budget | 10 | 1 to 100 | The most crossed checks a person reads in one night: the panel lists this many, smallest q_value first, and counts the rest, and row #8's replay is held to it | 8 | Owner, 2026-10-11 (E1) |
| F1.13 | metrics | The declarations H1.1 to H1.7 | Closed words for kind, comparisons, transform, unit and harm direction; combine_weight 0 to 10; the refusals of G1.3 | The named list of what the judge measures: each declaration names its slug, lifecycle_status, kind, source ledger and column, grouping, transform, unit, harm direction, comparisons and combine_weight | 4; each declaration in its kind's row | Owner, 2026-10-11 (separate what from how); owner, 2026-10-11 (P13) |
| F1.14 | long_baseline_weeks | 52 | 12 to 156, whole weeks | Weeks between the long baseline's first day and the recent window's first day; 52 keeps weekday and season | 14 | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P16) |
| F1.15 | long_window_days | 28 | 7 to 91, whole weeks | Days in each window of a long-baseline look, and the days between two looks | 14 | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P16) |

Table F2 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| F2.1 | One settings file per judge under config/judges/, loaded only by that judge, so its numbers never enter the import closure of every module that reads config/idhazh.json | Owner, 2026-10-11 (P6) |
| F2.2 | Every field declares its allowed range. An autotune loop never writes this file: it files its fitted value as a row in a ledger of its own, damped, step-capped and clamped to the field's range, and the reader takes the latest row filed before the night it judges; such a loop is Level 5, and none is built in this plan | Owner, 2026-10-11 (every number in config, ready for autotune); Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P17) |
| F2.3 | A site stays the host without www.; no public suffix lookup, because registered-domain grouping is rejected (F3.3) | Owner, 2026-10-10 (R7) |
| F2.4 | Page types group articles inside one site; they are never separate sites | Owner, 2026-10-10 (R5) |
| F2.5 | A site key is a lower-case host, optionally a slash and one path segment, with no space or backtick, and it is printed inside a code span wherever text reaches a page, so an address such as medium.com/@name never notifies a GitHub user | Owner, 2026-10-10 (R7); Fowler (reviewed 2026-10-11) |
| F2.6 | Combine weights are scored only on the replay's injected slips and reshuffled dates, never on live crossings, and fixed before any night they judge: the replay prints the best weights within 0 to 10, and a person commits them | Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P17) |

Table F3 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F3.1 | A block in config/idhazh.json, as the content-similarity judge's settings are | AppConfig is in the council's import closure, so the block would be a fourth judge contract crossing it, which llm-council.md says cannot grow (C9) | One block in AppConfig and its changelog entry | Owner, 2026-10-11 (P6) |
| F3.2 | Constants in the check modules | Guardrail #6 refuses a hard-coded threshold, and autotune cannot move a constant | One edit per module; every tuning needs a code change and a review | CLAUDE.md Guardrail #6 |
| F3.3 | Group by registered domain from the public suffix list, as the blueprint writes | Merges news.mongabay.com with india.mongabay.com, a second #1270-type mix; the seven author.substack.com feeds merge unless the list carries substack.com | courlan is already installed; the cost is the merged series | Owner, 2026-10-10 (R7) |
| F3.4 | Page types as separate sites | The #1270 week would compare nothing: 10 full and 11 Short recent articles, both under min_articles | Smaller series per site and more untested checks | Owner, 2026-10-10 (R5) |

### Row #3 - The judge's ledger and its tenant module

- **Scope:** the contract DriftEval (Tables H1 to H3) and the ledger drift-evals in the family summary-fidelity-judge are registered and enrolled for compaction and retention as ledger-registry.md requires of a new ledger, and backend/idhazh/summary_fidelity/tenant.py presents the seven members of the council's tenancy protocol and files the rows it is handed through ledger.persist in settle; its council.tenants entry lands paused and model-free (lifecycle_status paused, runs_model false), in the shape the council plan's row 'Judges carry a status and a model need' defines, so no night runs it.
- **Level:** 5 (a persisted contract and a new ledger). ESCALATE C1 fires: the owner rules on P1 before work starts.
- **Files touched:**
  - backend/idhazh/contracts/drift_eval.py (new: DriftEval, CheckOutcome, Direction, TestKind, ValueUnit, Comparison, ChangedPart, and the judge's slug as a closed set beside its column; check_name is a checked name, not a closed set (P13))
  - config/idhazh.json (council.tenants gains {"slug": "summary-fidelity-judge", "lifecycle_status": "paused", "runs_model": false})
  - backend/tests/council/ (re-derive at dispatch: tests that read the committed council.tenants)
  - backend/idhazh/contracts/__init__.py (CONTRACTS, entered the way content_similarity_judge_metrics is; re-derive at dispatch)
  - backend/idhazh/contracts/ledger_name.py (SUMMARY_FIDELITY_JUDGE_DRIFT_EVALS = "drift-evals")
  - config/ledgers.json (family summary-fidelity-judge: status active, one-line description, onboarded day; entry grain raw-and-compact, prefix ["summary-fidelity-judge", "drift-evals"])
  - backend/idhazh/ledger/keys.py (_JUDGE_DOOR_SHAPES: the key in H4.5 and the row contract, imported on first use; no preference)
  - backend/idhazh/ledger/staging.py (REGISTRY: written by the judge's settle in the council's save job, no digest.yml commit label)
  - frontend/src/lib/data/slice-shapes.ts (LEDGER_NAMES gains drift-evals; LEDGER_FOLDERS gains summary-fidelity-judge)
  - config/gardener/compact-summary-fidelity-judge-drift-evals.json (new: kind compaction, owns state/raw/summary-fidelity-judge/drift-evals and state/compact/summary-fidelity-judge/drift-evals, the approved retention chain of H4.4, the other fields copied from compact-council-run-records.json)
  - config/idhazh_gardener.json (task_names gains compact-summary-fidelity-judge-drift-evals)
  - backend/tests/contracts/test_gardener_config.py (RETENTION_LEDGERS gains drift-evals)
  - backend/tests/contracts/_fixtures.py (FIXTURE_FILES) and one drift-eval fixture in the contract fixtures folder it names
  - backend/idhazh/summary_fidelity/tenant.py (new: JUDGE_ID, shard_count 1, committed_paths from staging.staged_path, nights_outstanding naming no date (B8), publication_inputs returning an empty tuple because settle reads nothing committed, prepare, run_shard, settle)
  - backend/idhazh/summary_fidelity/record.py (new: the unit's rows as one JSON-lines file in a slot of its own, never selection, written through session.unit_file with the contract's own model_dump_json and read back with model_validate_json, never registered in backend/idhazh/ledger/csv_file.py, written once after the unit's last check by temp file and rename; and the filing through ledger.persist)
  - pyproject.toml (duckdb joins pyarrow on ruff's banned imports for backend/idhazh/; re-derive existing importers with git grep -n duckdb backend at dispatch)
  - backend/tests/summary_fidelity/test_tenant.py (new)
  - docs/architecture/contracts/state-ledgers.md (one table row)
  - docs/concepts/partitions.md (the count of collections it names; re-derive at dispatch)
  - docs/architecture/publishing/llm-council.md ("What is heard here" gains this judge)
  - docs/architecture/publishing/summary-fidelity-judge.md
  - Every other file that names the newest judge ledger, from git grep -n -e "CONTENT_SIMILARITY_JUDGE_METRICS" -e "content-similarity-judge/metrics" backend frontend config docs at dispatch
- **Acceptance gates:** local - ruff, mypy, the shared test selector over backend/tests/contracts/, backend/tests/council/, backend/tests/workflows/test_ledger_staging.py, backend/tests/workflows/test_ledger_door_jobs.py and backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** a night driven end to end against this tenant in a tmp_path state root, with the council's own session, files rows that read back through ledger.load_days equal to what the unit wrote; two council runs of one judged date both read back; the contract refuses a row whose outcome disagrees with its p_value, q_value and false_discovery_rate; nights_outstanding names no date. Cannot settle: whether the shape answers the questions row #12's panel asks.

Table H1 - check names: the declarations the judge starts with (F1.13) and two reserved names

| # | check_name | Kind | Source: ledger and column | Grouping | Transform | Unit | Harm direction | Comparisons | Combine weight (set in row #13) | Row |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| H1.1 | article_count | count | item-health census: distinct addresses a day (its address column; re-derive at dispatch) | site | none | per_day | fewer | site_window | 0 | 5 |
| H1.2 | unusually_short | tail_share | summary-quality-evals: source_words_before_cap, under the baseline's short_tail_percentile (F1.5) length | site, page_type | none | share | more | site_window | 1 | 6 |
| H1.3 | page_furniture | flag_share | summary-quality-evals: extraction_suspect ("The text looks like page furniture", eval_row.py); was scoring_chrome | site, page_type, scorer_version (G1.7) | none | share | more | site_window | 1 | 6 |
| H1.4 | article_length | distance | summary-quality-evals: source_words_before_cap | site, page_type | log1p | words | shorter | site_window; all_sites (row #13); long_baseline (row #14) | 1 | 7 |
| H1.5 | copied_phrase_share | distance | summary-quality-evals: extractiveness (the share of the summary's 4-word phrases found verbatim in the source) | site, page_type, model_id, scorer_version | none | score | higher | site_window; all_sites (row #13) | 1 | 7 |
| H1.6 | faithfulness | distance | summary-quality-evals: hhem | site, page_type, model_id, scorer_version | none | score | lower | site_window; all_sites (row #13) | 1 | 7 |
| H1.7 | page_mix | note | summary-quality-evals: url_key, typed by site.py (F1.10) | site, page_type | none | share | none | site_window | 0 | 4 |
| H1.8 | window_rows | reserved, never declared: the unit's guard | Rows in each whole window across all sites, one row per judged date | none | none | none | none | site_window | - | 4 |
| H1.9 | combined_measures | reserved, never declared: the combined comparison's row | Every active declaration with combine_weight above 0, each signed in its harm direction | site, model_id, scorer_version | none | none | worse | combined (row #13) | - | 13 |

Table H2 - outcomes (CheckOutcome; declared once here)

| # | Value | Meaning |
| --- | --- | --- |
| H2.1 | threshold_crossed | Tested; q_value at or under false_discovery_rate (row #8). A signal for a person to inspect, not a diagnosis |
| H2.2 | threshold_not_crossed | Tested; q_value above false_discovery_rate. Not evidence that nothing changed |
| H2.3 | too_few_articles | Not tested: under min_articles (F1.3) on a side, or a window_rows row under min_window_rows (F1.4) |
| H2.4 | earlier_model_baseline | A series grouped by model or scorer (G1.6) with fewer than min_articles baseline articles, compared with the earlier series of the same declaration on the site; stored with its p-value and changed_part, never enters the false-discovery step (R4) |
| H2.5 | not_tested | A note row (page_mix), or a window_rows row at or above min_window_rows: a count or share, never tested |
| H2.6 | paused | Tested by a paused declaration (G1.5): stored with its p_value and no q_value, never in the false-discovery step, so it moves no other row's q_value |

Table H3 - DriftEval, one row per check per comparison per judged date per council run (schema stem drift-eval)

| # | Field | Type | Meaning |
| --- | --- | --- | --- |
| H3.1 | run_id | RunId | The council run that judged the date (the judge-ledger rule in ledger-registry.md) |
| H3.2 | judge_id | the judge's slug, a closed set of one | Which judge wrote the row |
| H3.3 | date | DateStamp | The judged date; the recent window ends on it, and it decides the file the row is filed under |
| H3.4 | checked_at | Timestamp | When the unit computed the row |
| H3.5 | rules_version | str | The judge's rules version in force; it rises when a kind's or a comparison's arithmetic changes, never for a declaration, which check_definition spells (H3.22) |
| H3.6 | recent_days, baseline_days, baseline_end | int, int, DateStamp | The window lengths in days and the baseline's last day, so a row names the days it compared, a long baseline's included (row #14) |
| H3.7 | site | a site key (F2.5) or null | Null on window_rows and all_sites rows |
| H3.8 | page_type | str or null | Set on page_mix rows only |
| H3.9 | check_name | a declared name (H1, F1.13): lower-case letters, digits and underscores, starting with a letter, checked against the named list when the row is written; or a reserved name (H1.8, H1.9) | Which measure; not "check", which is a reserved word in the console's query engine |
| H3.10 | model_id, scorer_version | str or null | Set where the declaration's grouping names them (G1.6), and on combined_measures rows |
| H3.11 | baseline_count, recent_count | int | Articles, census addresses or window rows on each side |
| H3.12 | baseline_value, recent_value | float or null | Each side's summary in value_unit (H3.21): median words, median score, share of articles, or addresses a day; null on combined_measures rows |
| H3.13 | effect | float or null | Distance kind: the distance minus the median distance of its reshuffles (log words or score points). Count kind: recent count over its no-change expectation, minus one. Share kinds: recent share minus its no-change share (j / (N_b + 1) for unusually_short), in percentage points. all_sites: the weighted sum of signed mean differences. combined_measures: the weighted sum of its members in standard units |
| H3.14 | direction | Direction: fewer, more, shorter, longer, higher, lower, worse or none | Which way the tested comparison moved, within page type where the test is; worse on a combined_measures row whose sum moved in the harm direction |
| H3.15 | p_value | float or null | Null when not tested; on a reshuffled check, an estimate from H3.18's reshuffles, which a re-run of the date draws again |
| H3.16 | q_value | float or null | The smallest false_discovery_rate at which this check would cross in its family, the (run_id, date) pair: the Benjamini-Hochberg adjusted p-value. It depends on every other check of the same run and date that enters the false-discovery step, so an outcome is not a property of one check alone. Null outside the step, earlier_model_baseline and paused included. Rank or re-threshold only rows of one run_id, the date's latest; two runs of one date can disagree on a check near the cut, because each run draws its own reshuffles, and a re-run dispatched because a check crossed is a second draw, not a correction |
| H3.17 | false_discovery_rate, min_articles, short_tail_percentile | float, int, float | F1.11, F1.3 and F1.5 in force, so a later reader needs no git history |
| H3.18 | reshuffles, reshuffle_hits | int or null | Reshuffles used and the hits among them (a tie counts), on permutation checks; the p-value's relative error from the draw is about 1 / sqrt(reshuffle_hits), 32 percent at 10 |
| H3.19 | outcome | CheckOutcome (H2) | What the check concluded |
| H3.20 | test_kind | TestKind: count, tail_share, flag_share, distance, note, or null on window_rows and combined_measures rows | Which kind of test made the row (G1.2) |
| H3.21 | value_unit | ValueUnit: words, score, share, per_day, or null | What baseline_value and recent_value count |
| H3.22 | check_definition | str | Derived, never hand-typed: the declaration's kind, source ledger and column, grouping, transform, harm direction and comparison, and on a combined_measures row each member and its weight, spelled so a row still explains itself after its declaration retires |
| H3.23 | comparison | Comparison: site_window, all_sites, combined or long_baseline | Which samples were set against each other (G1.2); part of the key (H4.5) |
| H3.24 | changed_part | ChangedPart: model, scorer, both, or null | On an earlier_model_baseline row, which input of the series moved; a scorer move means the comparison measures the scorer as well as the pipeline |

Table H4 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| H4.1 | The ledger is drift-evals in the family summary-fidelity-judge: rows land in state/raw/summary-fidelity-judge/drift-evals/YYYY/MM/DD/ as parquet, and the gardener packs them into state/compact/summary-fidelity-judge/drift-evals/ (daily, monthly and yearly files with their index files); the family leaves room for this judge's later ledgers | Owner, 2026-10-11 (P1) |
| H4.2 | Every file name is minted by the ledger door (a version 8 UUID per writer and attempt); no writer names a file | backend/idhazh/ledger/persist.py |
| H4.3 | Every check of every judged date is stored, untested ones included, so a skipped check is visible; a date whose whole window is under min_window_rows stores its one window_rows row instead | Owner, 2026-10-10 (store every check); blueprint section 2 ("eliminating the silent skip") |
| H4.4 | Retention follows the owner-approved live chain in ledger-registry.md, held by test_every_ledger_uses_the_approved_live_retention_chain | ledger-registry.md |
| H4.5 | Key: run_id, date, site, check_name, comparison, page_type, model_id, scorer_version, with no preference, so packing keeps every council run of a date; a retry of one run settles to its highest attempt through the door; a reader of one judged date takes the run with the latest checked_at | Owner, 2026-10-11 (P1); ledger-registry.md, the rule a judge ledger follows; Fowler (reviewed 2026-10-11); owner, 2026-10-11 (P13) for comparison |
| H4.6 | The row declares none of the door's names (ledger, covers, attempt, job, shard, unit_id) and run_id only as the council run; the writer identity is the council's, job save_council_results | ledger-registry.md, the rule a judge ledger follows |
| H4.7 | One unit a night (shard_count 1): run_shard computes every check's row into a scratch file in the tenant's own slot under backend/var/council/, reports no model calls, writes that file once, after its last check, or leaves none and returns stopped_on_deadline, so settle files a whole date or nothing, and settle applies row #8's step and files the rows, naming its own producer; the tenant declares no refusal of a night, because its work has no cost worth weighing against the council's clock | Owner, 2026-10-11 (P8); backend/idhazh/council/tenancy.py |
| H4.8 | Check names state what is measured and the outcome states whether the threshold was crossed, so a stored row never claims a movement its own outcome denies | Owner, 2026-10-10 (rename request); replaces the alert names of R8; outcome names debated by Fowler and Andre, 2026-10-11 |
| H4.9 | Readers count a stretch, not a night: a stretch is consecutive run days on which one key crosses, and a day with no run does not end one, because one real change stays in the recent window for seven nights | Owner, 2026-10-11 (P11) |

Table H5 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H5.1 | state/raw/summary-quality-evals/drift/ | The registry refuses a door ledger inside another door ledger's folder, because a walk of the outer ledger's raw days would read the inner one's files (backend/idhazh/contracts/ledgers.py); a fixed file name such as ledger.parquet is also refused, because a raw file is immutable once written | A change to the registry rule, or renaming the eval ledger and moving its committed raw and compact files into a nested folder; either is Level 5 | backend/idhazh/contracts/ledgers.py |
| H5.2 | JSON files under state/summary-fidelity-judge/, as two of the content-similarity judge's ledgers still are | The owner wants parquet under state/raw/ with the ledger enrolment; the flat and stamped grains are the ones the registry calls transitional | None | Owner, 2026-10-11 |
| H5.3 | A ledger that is its own family, at state/raw/summary-fidelity-judge/ | No door ledger may sit inside another, so a later ledger of this judge could never sit beside it | A second family later | Owner, 2026-10-11 (P1) |
| H5.4 | Store only crossed checks | A reader cannot tell "checked, threshold not crossed" from "never checked" | Fewer rows a night; row #8's replay measures how many | Owner, 2026-10-10 (store every check) |
| H5.5 | Compute the checks in settle | settle runs inside the collecting job's 30-minute bound for every tenant and date, and a job killed there commits nothing for any tenant | None; the unit pays one runner job either way, with no model server once the council plan's row 'Judges carry a status and a model need' lands | Owner, 2026-10-11 (P8) |
| H5.6 | A preference that keeps one run per date | Packing would delete the earlier run's rows, against "every check stored", and could mix two runs' false-discovery sets in one day | None | Fowler (reviewed 2026-10-11) |

### Row #4 - Metric declarations, the kind registry and the note kind

- **Scope:** the settings file gains metrics (F1.13), the named list of what the judge measures: each declaration names its slug, lifecycle_status, kind, source ledger and column, grouping, transform, unit, harm direction, comparisons and combine_weight (Table H1). registry.py binds each active or paused declaration to the one kind module that serves its kind and each comparison it selects to its comparison module, and refuses what G1.3 lists before any check runs. windows.py reads each declared source through ledger.load_days, one value per distinct article per window. This row lands the note kind, the site_window comparison and the page_mix declaration, and the unit stores one window_rows row per judged date.
- **Level:** 3 (decides how a measure enters the judge; a declaration is config, never a stored row).
- **Files touched:**
  - config/judges/summary-fidelity-judge.json (metrics with the page_mix declaration; recent_days, baseline_days, min_articles, min_window_rows)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py (MetricDeclaration: one model per kind, chosen by kind, unknown keys refused, no field defaulted; MetricLifecycleStatus (active, paused, retired), a set of its own, never shared with a ledger's, a gardener task's or a judge's; Transform (none, log1p); the four window settings; row #3's TestKind, ValueUnit, Comparison and Direction reused)
  - backend/idhazh/summary_fidelity/registry.py (new: binds declarations to kind and comparison modules; the refusals of G1.3)
  - backend/idhazh/summary_fidelity/kinds/__init__.py and backend/idhazh/summary_fidelity/kinds/note.py (new: each kind module exports its word and its run function and nothing else)
  - backend/idhazh/summary_fidelity/comparisons/__init__.py and backend/idhazh/summary_fidelity/comparisons/site_window.py (new: the recent days against the baseline days, per site)
  - backend/idhazh/summary_fidelity/windows.py (new: each declared source read through ledger.load_days; one value per distinct article per window, the newest row by url_key; a row whose column is null is left out and counted)
  - backend/idhazh/summary_fidelity/tenant.py (run_shard runs every active and paused declaration through the registry, and stores the window_rows row)
  - backend/tests/summary_fidelity/test_registry.py (new: each refusal of G1.3, by name)
  - backend/tests/summary_fidelity/test_windows.py (new)
  - backend/tests/summary_fidelity/test_note.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md (the declaration fields, the kinds and comparisons, and how to add a measure)
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** the committed file binds every declaration; each refusal of G1.3 fires by name on a written bad declaration, before any check runs; a two-type fixture stores its page_mix shares; a judged date whose whole window is under min_window_rows stores one window_rows row and no check. Cannot settle: whether five kinds suit a measure nobody has declared yet; a new kind is still a module, its tests and a review.

Table G1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| G1.1 | A declaration says what is measured; a kind module says how it is tested; a comparison module says which samples are set against each other and how the no-change case is re-dealt. A new measure of an existing kind is a config change (Level 3); a new kind or comparison is a module, its tests and a review | Owner, 2026-10-11 (separate what the judge measures from how); CLAUDE.md section 14 (Editor names the content failure, Andre chooses how to measure it); Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P13) |
| G1.2 | Five kinds: count, the negative-binomial lower tail on a daily rate (row #5); tail_share, the exact beta-binomial tail under a cut from the baseline (row #6); flag_share, Fisher's exact test summed over page types (row #6); distance, Wasserstein-1 with reshuffles within page type (row #7); note, stored and never tested (this row). A one-sided kind tests its declaration's harm direction; distance tests both ways. Four comparisons: site_window (this row), all_sites and combined (row #13), long_baseline (row #14) | Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P13, P16) |
| G1.3 | The loader refuses, naming the declaration and the field, before any check runs: a kind or comparison no module serves; a kind or comparison module that no active or paused declaration uses, the combined module counting as used while any declaration carries a combine_weight above 0; a source that is not a door ledger in config/ledgers.json, or a column its row contract lacks or types otherwise than the kind reads; a grouping field the source lacks; a repeated slug, retired declarations included; the reserved names window_rows and combined_measures; a transform its column can fail, so a log reads log(1 + x) of a count that can be 0; a combine_weight above 0 on a count or note declaration, or while no module serves the combined comparison, so each declaration lands at 0 and row #13 sets the weights | Fowler (reviewed 2026-10-11); Andre (the log of a zero count, 2026-10-11); owner, 2026-10-11 (P13) |
| G1.4 | A declaration's meaning - kind, source, grouping, transform, unit and harm direction - is never edited: a change is a new slug, and the old declaration turns retired and stays in the list as the record, so one check_name keeps one meaning across every stored row. A declaration names its kind and comparisons with closed words, never a module or a path | Fowler (reviewed 2026-10-11); knobs_gardener.py (a retired declaration stays as the record); owner, 2026-10-11 (P13) |
| G1.5 | A new declaration lands paused: tested and stored with its p_value and no q_value, outside the false-discovery step (H2.6), and made active by an owner ruling once row #8's replay has run it on reshuffled dates and injected changes. The declarations of H1 land active, because the judge itself stays paused until row #9 and row #8's replay runs them first | Andre (reviewed 2026-10-11); ledger-registry.md (a switch ships safe until a named decision); owner, 2026-10-11 (P13) |
| G1.6 | A measure splits its series only on the fields its grouping names, and names every field whose change changes its column. A change in one starts a new series; until the new series has min_articles baseline articles, its row compares it with the earlier series of the same declaration on the site, stored as earlier_model_baseline with changed_part (H3.24), outside the step. A new scorer, column, scale or transform is a new slug, and no row compares two slugs | Owner, 2026-10-10 (R4); Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P14) |
| G1.7 | Until the eval row carries a stamp per scored column (B11), copied_phrase_share, faithfulness and page_furniture group on scorer_version, the only stamp that names their scorers' inputs: extraction_suspect and extractiveness are counterweights METRICS_VERSION names, and hhem follows the scorer's revision, weights and window. scorer_version also spells inputs a column does not read, such as band thresholds, so a move of those alone still restarts the three series | docs/concepts/evaluation.md (METRICS_VERSION "is folded into scorer_version"); drift.py (the old furniture check split by model and scorer); owner, 2026-10-11 (P14) |
| G1.8 | A judged date whose whole window is thin stores one window_rows row and no check, so a stopped instrument never reads as a quiet week | drift.py (min_window_rows) |
| G1.9 | The judge reads no determinism_violation value: production never sets it, and a reader would hold back its removal (B9) | Owner, 2026-10-11 (determinism is not an expectation) |

Table G2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| G2.1 | check_name as a closed list in the row contract, as H1 first declared it | Every new measure would be a stored-shape change (C1) and a console edit, and a rules_version raised by hand can be forgotten | One list value, one console copy and one changelog line per measure | Fowler (reviewed 2026-10-11); owner, 2026-10-11 (P13) |
| G2.2 | One module per measure, as rows #4 to #7 first wrote | A sixth measure of an existing kind would copy a test module, and what is measured would change together with how it is tested | None | Fowler and Andre (debated 2026-10-11) |
| G2.3 | A declaration that names its module or path | A config value would choose the code that runs (idhazh-gardener.md) | One field per declaration | Fowler (reviewed 2026-10-11) |
| G2.4 | A row comparing a series with a replaced scorer's series inside the step | It measures the scorer as well as the pipeline: "Slicing costs a long article 0.40 of its score" (docs/concepts/evaluation.md) | None | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P14) |
| G2.5 | page_furniture with no scorer split, as this plan first wrote | A METRICS_VERSION move that redefines extraction_suspect would read as furniture crossings on many sites in one night | A series that never restarts on a scorer move | Owner, 2026-10-11 (P14) |

### Row #5 - Count kind: article count from the item-health census

- **Scope:** the count kind tests a declared count of distinct addresses per site in the item-health census (never sampled), the recent window against the baseline's daily rate, by a negative-binomial lower-tail p-value whose spread comes from the baseline's daily counts; article_count (H1.1) is its one declaration; a crossing skips none of the site's other checks, and its row names feed-health first.
- **Level:** 3 (it reverses the old rule that a stopped site is feed quarantine's job).
- **Files touched:**
  - backend/idhazh/summary_fidelity/kinds/count.py (new)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py (the count declaration's model)
  - config/judges/summary-fidelity-judge.json (the article_count declaration)
  - backend/tests/summary_fidelity/test_count.py (new)
  - pyproject.toml (scipy in an optional extra; P7)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** a fixture site whose 28 baseline days alternate 1 and 7 addresses gets a p-value under 0.001 at 5 recent addresses and over 0.3 at 26; the expected values are computed in the test from scipy.stats.nbinom, never copied. Cannot settle: holiday weeks, which whole-week windows do not remove.

Table I1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| I1.1 | The count comes from the item-health census, because the eval ledger counts what the pipeline selected and scored | Owner, 2026-10-10 (R3) |
| I1.2 | Negative-binomial tail with spread from the baseline's daily counts; the rate uses the days the unit actually read, never the settings | Owner, 2026-10-10 (R3) |
| I1.3 | No article floor for this kind: a site with any baseline address is tested | Blueprint section 2 |
| I1.4 | A daily variance under the daily mean is raised to the mean, and the variance also carries the baseline's own noise | Owner, 2026-10-11 (P3) |

Table I2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I2.1 | The Poisson z-score as the blueprint writes it | Fires on 0.04 to 1.49 percent of unchanged sites against 0.135 percent nominal (simulation, 2026-10-10) | One line of arithmetic | Owner, 2026-10-10 (R3) |
| I2.2 | Count scored rows in the eval ledger | Selection limits and run sampling move the count with no change at the source | None | Owner, 2026-10-10 (R3) |

### Row #6 - Share kinds: unusually short and page furniture

- **Scope:** the tail_share kind counts, per site and within each declared page type, recent articles with strictly fewer words than the baseline's short_tail_percentile (F1.5) length and takes the exact beta-binomial tail as its p-value, adding each page type's exact tail; a type with no baseline article has no cut and its recent articles are left out; unusually_short (H1.2) is its declaration. The flag_share kind compares the share of distinct articles carrying a declared flag, within page type, with Fisher's exact test summed over page types; page_furniture (H1.3) is its declaration and reads extraction_suspect.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity/kinds/tail_share.py (new)
  - backend/idhazh/summary_fidelity/kinds/flag_share.py (new)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py (the two share declarations' models; short_tail_percentile)
  - config/judges/summary-fidelity-judge.json (the unusually_short and page_furniture declarations; short_tail_percentile)
  - backend/tests/summary_fidelity/test_tail_share.py (new)
  - backend/tests/summary_fidelity/test_flag_share.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** with no change, the exact probability of a p-value at or under 0.05, computed in the test from scipy.stats.betabinom for baselines of 20 to 102 and recent counts of 21 and 40, is at most 0.05, so the test draws nothing; on a 102-article baseline, 8 of 40 recent articles under the cut gets a p-value under 0.01 and 3 of 40 one over 0.2 (the exact tail gives about 0.004 and 0.31); a page_furniture fixture whose mix moves toward the type with more flagged pages, with the same flagged share within each type, gets a p-value over 0.05, computed in the test from scipy.stats.hypergeom, never copied. Cannot settle: truncation that leaves an article above 60 words but inside the baseline's normal range; whether extraction_suspect still flags what a person calls page furniture.

Table J1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| J1.1 | The p-value is the exact beta-binomial tail, the exact form of the reshuffling R2 approved, because the cut is itself estimated from the baseline; a recent article counts when it has strictly fewer words than the cut | Owner, 2026-10-10 (R2); owner, 2026-10-11 (P2) |
| J1.2 | page_furniture replaces scoring_chrome and reads extraction_suspect, with an exact p-value | Owner, 2026-10-10 (R15; renamed by the rename request) |
| J1.3 | The furniture share is taken within each page type, so a mix that moves toward a type with more flagged pages does not cross, and one distinct article counts once | Owner, 2026-10-11 (P11) |

Table J2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J2.1 | Binomial(N_recent, 0.05) as the blueprint writes it | Treats the estimated cut as known; fires on 0.73 to 4.83 percent of unchanged samples against 0.5 percent nominal at baselines of 20 to 102 (exact, 2026-10-11) | One line of arithmetic | Owner, 2026-10-10 (R2) |
| J2.2 | Fisher's exact test on the pooled furniture share | Fired 9.6 percent at 5 percent nominal when the mix moved with no change (Andre, 2026-10-11) | None | Owner, 2026-10-11 (P11) |

### Row #7 - Distance kind: article length, copied phrases and faithfulness

- **Scope:** the distance kind computes, per site and within each page type, the Wasserstein-1 distance of a declared column between the baseline and recent windows, averaged over page types with weights n_b x n_r / (n_b + n_r), with a permutation p-value whose reshuffles stay within type; article_length (H1.4), copied_phrase_share (H1.5) and faithfulness (H1.6) are its declarations; a series grouped by model or scorer with fewer than min_articles (F1.3) baseline articles is compared with the earlier series of the same declaration on the site and stored as earlier_model_baseline (G1.6).
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity/kinds/distance.py (new)
  - backend/idhazh/summary_fidelity/reshuffle.py (new: the early-stopping reshuffle and its automatic cap; fresh randomness on every run, no seed)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py (the distance declaration's model; reshuffle_stop_hits, reshuffle_cap_floor, reshuffle_cap_multiple)
  - config/judges/summary-fidelity-judge.json (the three distance declarations; the three reshuffle settings)
  - backend/tests/summary_fidelity/test_distance.py (new)
  - backend/tests/summary_fidelity/test_reshuffle.py (new)
  - backend/tests/summary_fidelity/fixtures/issue_1270_window.json (new: news.mongabay.com, 102 baseline and 21 recent lengths with page types, copied from the committed eval ledger)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** the #1270 fixture's article_length row gets a p-value over 0.05 (C6), and the same fixture with half its full articles cut to 300 to 500 words gets one under 0.01; extractiveness moving from 0.15 to 0.55 gets a p-value under 0.001; a new model-and-scorer pair with 25 recent rows and none in the baseline is stored as earlier_model_baseline with a p-value, its changed_part and no q_value. Every assertion on a reshuffled p-value keeps the case's own p-value at least 10 times under an upper bound or 5 times over a lower bound, measured once with at least 1,000 hits and written in the test, so chance fails a run less than once in a million; fixture lengths are committed, never generated, and a failing test prints the entropy its generator drew. Cannot settle: the false-crossing rate on live data, which row #8's replay measures; score movement that a library upgrade causes under one scorer_version (B10).

Table K1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| K1.1 | Wasserstein-1, two-sided: a shorter extraction can be a better one | Owner (blueprint section 1); Andre (reviewed 2026-10-10: keep) |
| K1.2 | article_length reads the log of one plus the word count, so a cut is measured as a share of the text and an empty article stays defined; the row still stores medians in words | Owner, 2026-10-10 (R14); Andre (the log of a zero count, 2026-10-11) |
| K1.3 | Reshuffles stay within page type, so the p-value asks whether one type moved and a change in mix alone does not cross | Owner, 2026-10-10 (R5) |
| K1.4 | The distance is taken within each page type, so a mix that moves toward the shortened type cannot hide a real cut | Owner, 2026-10-11 (P11) |
| K1.5 | No setting seeds the reshuffles: each unit makes one generator from operating-system entropy, never from a constant or the clock, so no loop can choose a draw; a p-value near the cut may differ between two runs of a date, and a reader takes the latest run (H4.5) | Owner, 2026-10-11 (determinism is not an expectation); Fowler and Andre (reviewed 2026-10-11) |

Table K2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K2.1 | The standard-error band W1 > 2.5 x sqrt(var_b / N_b + var_r / N_r) | Wasserstein-1 is never smaller than the difference in means, so the band fires on 1.0 to 3.6 percent of unchanged comparisons and gives no p-value | None | Owner, 2026-10-10 (R2) |
| K2.2 | Kolmogorov-Smirnov or energy distance | The blueprint names Wasserstein-1; the gap table lists the others as equals | A second statistic and its own reshuffling | Owner (blueprint section 1) |

Table L1 - decisions (copied_phrase_share and faithfulness)

| # | Decision | Authority |
| --- | --- | --- |
| L1.1 | Wasserstein-1 with a permutation p-value for hhem and extractiveness | Owner, 2026-10-10 (R2) |
| L1.2 | A deliberate model or scorer change is never a crossing: the comparison with earlier series is stored and stays outside row #8 | Owner, 2026-10-10 (R4) |
| L1.3 | A pair with 1 to 19 baseline articles is compared with earlier pairs too, so no pair falls into the gap L2.2 rejects | Owner, 2026-10-11 (P11) |

Table L2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L2.1 | PSI for bounded scores | Exceeds 0.25 on 92 percent of unchanged samples of 102 against 21 | None | Owner, 2026-10-10 (R2) |
| L2.2 | Skip a new pair until it has its own baseline | Loses the comparison a person wants after a model change | 7 + 20 / (articles a day) days with no score check; at most 14 for any site a 7-day window can test | Owner, 2026-10-10 (R4) |

### Row #8 - One false-discovery step per judged date, and the replay

- **Scope:** settle collects the p-value of every tested row of an active declaration of a judged date, with no earlier cut-off (a paused declaration's rows stay out, H2.6), applies the Benjamini-Hochberg step-up at false_discovery_rate (F1.11), stores each row's q_value and outcome, and a replay utility runs the unit over past dates with its own test.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity/false_discovery.py (new)
  - backend/idhazh/summary_fidelity/tenant.py (settle applies the step before filing)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (false_discovery_rate, crossings_budget)
  - backend/utilities/summary_fidelity_replay.py (new; operator utility)
  - backend/tests/summary_fidelity/test_false_discovery.py (new)
  - backend/tests/summary_fidelity/test_replay.py (new: a tmp_path ledger with two judged dates, read through ledger.load_days)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite. Observation, not a gate: the replay over every judged date of the last 35 days, the same dates with each article's window label reshuffled once per site and shared by all that site's checks, the same dates with whole days reshuffled across sites (P18), and the same dates with half of one site's full articles cut to its short-form length, recorded in the pull request as crossings per date and per check, stretches (H4.9), repeats and injected cuts found, with false crossings counted per stretch and over non-overlapping weeks, and article_count reported on its own.
- **Oracle:** for the textbook input of ten p-values the step keeps exactly the step-up set and stores the matching adjusted values; a date with no tested check still files every row, with no q_value; a paused declaration's row keeps its p_value, gets no q_value and moves no other row's q_value. Cannot settle: crossings that are real but too small to matter; the stored effect lets a reader rank them.

Table M1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| M1.1 | Every check with a p-value hands the step one row; the step is the only threshold, and no check is cut before it by its p-value | Owner, 2026-10-10 (R2) |
| M1.2 | One judged date within one council run, the (run_id, date) pair, is one family for the step; two runs of a date are two families, and a repair date judged on the same night is a family of its own | Owner, 2026-10-11 (P1); Fowler and Andre (reviewed 2026-10-11) |
| M1.3 | The replay reads through ledger.load_days, one judged date at a time (Guardrail #12) | Fowler (reviewed 2026-10-10: keep) |
| M1.4 | Reshuffling stops early and its cap follows the number of checks | Owner, 2026-10-11 (P4) |
| M1.5 | The reading budget (C5) counts new stretches, not crossings: a typical night is the mean number of new stretches (H4.9) per judged date after the first seven; the count is split by check, a check that crosses on the reshuffled dates, where nothing changed, on more than false_discovery_rate of them is fixed first, and false_discovery_rate 0.01 is the second lever | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P18) |

Table M2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M2.1 | Bonferroni | A person reading a short list needs the false share bounded, not the chance of any false crossing | Fewer crossings at the same error target | Andre (reviewed 2026-10-10: keep) |
| M2.2 | DuckDB over state/compact/ as the blueprint writes | Days not yet compacted exist only as raw files, so every site's recent count would read as a collapse; re-runs count twice; Guardrail #12 forbids the glob | None | Owner, 2026-10-10 (R1) |
| M2.3 | The pasted composite: per-measure penalties from raw relative median changes, a weighted sum, bands at 0.2 and 0.4 and a veto at 0.8 | Fixed lines on raw medians ignore sample size and spread: in simulation it went red on 19 percent of unchanged nights at a site with half an article a day, stayed green for a 79 percent length cut and a faithfulness fall from 0.85 to 0.40, and scored 0.18 on the #1270 mix change alone, against the 0.20 line | None: declarations keep the extensibility (row #4) and combined_measures the joint detection (row #13) | Andre and Fowler (debated 2026-10-11); owner, 2026-10-11 (P15) |
| M2.4 | Automatic actions from a score: quarantine a site, demote its rank, raise the repetition penalty, add prompt text, rewrite a low-scoring summary | The judge would steer what it measures: an action's effect reads as a change and then becomes the baseline, and rewriting by the faithfulness score hides a rise in bad summaries (3 to 10 percent logged as 0.09 to 1 percent in simulation); quarantine and demotion are coverage and ranking calls, the Editor's (CLAUDE.md section 14) and feed-health's; a prompt or a penalty is an instrument change made by a reviewed commit | A real defect publishes until a person acts (B2) | Andre and Fowler (debated 2026-10-11); owner, 2026-10-11 (P15) |

### Row #9 - The switch: the judge joins the council

- **Scope:** summary-fidelity-judge's council.tenants entry turns active in config/idhazh.json, and the council's planning, judging and collecting jobs install the extra that carries scipy, so the next nightly run judges yesterday on a cell with no model server and files its rows.
- **Level:** 3 (starts a nightly committed write).
- **Files touched:**
  - config/idhazh.json (the judge's council.tenants entry: lifecycle_status active)
  - .github/workflows/llm-council.yml (the planning, judging and collecting jobs install the extra; P7; the planning job's install can go once the council plan's P8, approved 2026-10-11, lands)
  - The workflow test that reads llm-council.yml's install step (re-derive at dispatch), asserting all three jobs install the extra
  - backend/tests/council/ (re-derive at dispatch: tests that enumerate council.tenants)
  - docs/architecture/publishing/llm-council.md (the tenant list names two active judges)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/council/ and backend/tests/summary_fidelity/; CI - full suite. Observation, not a gate: the first scheduled night, read for rows stored, crossed checks, and the unit's run time and peak memory on a cell with no model server (a unit that does not fit stops the row, C2); when it stores nothing, read the collecting job's log first.
- **Oracle:** a council night driven end to end with both judges active fans out one cell for this judge per date, with runs_model false, and the collecting job commits its raw file under state/raw/summary-fidelity-judge/drift-evals/ beside the other judge's files. Cannot settle: the first live night's run time against the council's clock.

Table N1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| N1.1 | The judge's lifecycle_status on its council.tenants entry is the switch: row #3 registers it paused and model-free, and this row makes it active by the owner's named decision; no separate flag | llm-council.md ("That one line decides whether a night judges anything at all"); council plan E1.5 (approved there as P1, 2026-10-11) |
| N1.2 | The council's nightly schedule replaces the daily schedule the drift plan asked for; this judge names no repair date (B8) | Owner, 2026-10-10 (R6); Fowler (reviewed 2026-10-11) |
| N1.3 | A person judges a past date by dispatching the council workflow with that date | llm-council.md ("A dispatched date replaces the plan outright") |

Table N2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N2.1 | A workflow of the judge's own | The council already provides the schedule, the repair window, one commit path and the writer identity | A second scheduler, commit path and identity to keep correct | Owner, 2026-10-11 (run it as a council judge) |

### Row #12 - The stored checks on a console page

- **Scope:** drift-evals joins ledger.published so the console's Data explorer can query its compact files, and one panel on the console's Model page (P5) lists at most crossings_budget (F1.12) of the newest council run's crossed checks, smallest q_value first, with site, effect and q_value, counts the rest, drawing consecutive nightly crossings of one check as one stretch; a combined_measures row is listed only when none of its site's own rows crossed (T1.3).
- **Level:** 3.
- **Files touched:**
  - config/idhazh.json (ledger.published gains drift-evals)
  - frontend/src/routes/console/model/+page.server.ts and frontend/src/routes/console/model/+page.svelte (the Model route, which the console's settings call the Summaries route)
  - frontend/src/lib/server/ledger-rows.ts (a build-time reader of the drift-evals compact files, beside evalRows and itemHealthRows)
  - frontend/src/lib/server/config.ts (reads crossings_budget from config/judges/summary-fidelity-judge.json)
  - backend/tests/contracts/test_frontend_vocabularies.py and backend/tests/contracts/test_frontend_field_set.py (the hand copy of H2, Direction, TestKind, ValueUnit and the fields the panel reads; check_name prints as stored, so a new declaration needs no console edit)
  - backend/tests/contracts/test_panel_queries.py and backend/tests/contracts/test_frontend_console_lists.py (re-derive at dispatch)
  - config/console/model.json (the panel's own settings, if the page keeps them there; re-derive at dispatch)
  - docs/concepts/growing-reads.md (the reader and its window)
  - docs/architecture/publishing/console.md
- **Acceptance gates:** local - the frontend checks and the contract tests through the shared selector; CI - full suite.
- **Oracle:** a fixture of compact rows with seven consecutive nightly crossings of one check renders one stretch, a fixture where a later council run re-judged a date shows that run's rows only, and a fixture with none renders the empty state. Cannot settle: whether the panel is read.

Table T1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| T1.1 | The Data explorer is the first view; the panel follows | Owner, 2026-10-10 (visualisation is secondary) |
| T1.2 | The Model page carries the panel, and the ledger's compact files are published on the site | Owner, 2026-10-11 (P5) |
| T1.3 | A combined_measures row is listed only when none of its site's own rows crossed, so it adds a line only for what no single measure showed | Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P15) |

Table T2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| T2.1 | A page of its own | The owner ranked the view second to the stored record | A route, its navigation entry and its own tests | Owner, 2026-10-10 |

### Row #13 - All-sites comparison and combined-measures check

- **Scope:** two comparisons join the registry. all_sites, per judged date and per declaration that selects it, sums every site's and page type's signed recent-minus-baseline mean, weighted n_b x n_r / (n_b + n_r), over the sites and types with at least two articles a side, and takes its p-value from reshuffling whole days, so every site's articles of one day move together. combined, per site and current model-and-scorer pair, sums each active declaration with combine_weight above 0, signed in its harm direction and divided by its spread over the same re-deals, and takes its p-value from re-dealing each article's window label once, within page type, for every member together; its row is combined_measures (H1.9). Both rows enter row #8's step, and row #8's replay gains slips injected into several measures at once.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity/comparisons/all_sites.py (new)
  - backend/idhazh/summary_fidelity/comparisons/combined.py (new)
  - config/judges/summary-fidelity-judge.json (article_length, copied_phrase_share and faithfulness select all_sites; the combine weights committed under F2.6)
  - backend/utilities/summary_fidelity_replay.py (slips injected into several measures at once; the best combine weights printed, F2.6)
  - backend/tests/summary_fidelity/test_all_sites.py (new)
  - backend/tests/summary_fidelity/test_combined.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite. Observation, not a gate: row #8's replay over the last 35 judged dates, with whole days reshuffled across sites and with slips injected into several measures, recorded in the pull request as all_sites and combined_measures crossings per date.
- **Oracle:** a committed fixture whose last seven days carry one small step on every site, too small for any site's own check, gets an all_sites p-value under 0.001, and the same fixture with whole days moved together and no step gets one over 0.25; three slips, each too small to cross alone, cross together in combined_measures; the #1270 fixture's combined_measures row does not cross (C6); each assertion keeps row #7's margins. Cannot settle: a change on some sites only; a shared change no larger than the movement between days; a change in spread alone; which measure moved, which the per-measure rows beside it show.

Table U1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| U1.1 | all_sites reshuffles whole days, never single articles: one day's movement is shared by every site, so it belongs in the no-change case | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P16) |
| U1.2 | combined_measures is the only combination that enters the step, filed in drift-evals with its night's family; a weighted score a reader computes later from stored rows has no p-value and enters no step, and one that is ever stored goes to a ledger of its own | Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P15) |
| U1.3 | Each member enters combined as its value against the night's own re-deals of the same articles, never as a raw change or a change scaled by the site's past nights; the weights need not add to one, because scaling them all leaves the p-value unchanged | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P15) |
| U1.4 | Every per-measure row stays in the step beside the combined row, so one severe slip crosses alone and is never averaged away; there is no band and no veto line | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P15) |
| U1.5 | The panel lists a combined_measures row only when none of its site's own rows crossed, and the reading budget counts it by the same rule (T1.3) | Fowler and Andre (debated 2026-10-11); owner, 2026-10-11 (P15) |
| U1.6 | Combine weights follow F2.6: scored on the replay's injected slips and reshuffled dates, never on live crossings, and committed by a person | Owner, 2026-10-11 (P17) |

Table U2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| U2.1 | Reshuffle single articles within site and page type for all_sites | Crossed about 200 times its nominal rate under a shared day movement of 0.01 (simulation, 2026-10-11) | None | Andre (reviewed 2026-10-11) |
| U2.2 | Scale tonight's effect by the site's own night-to-night history | Crossed 25 to 330 times the nominal rate at a cut of 3.89 standard units with no change (simulation, 2026-10-11) | None | Andre (reviewed 2026-10-11) |

### Row #14 - Long-baseline comparison

- **Scope:** the long_baseline comparison compares, per site within page type, the last long_window_days (F1.15) days with the same number of days ending long_baseline_weeks (F1.14) weeks earlier, by the declaration's own kind; it runs only on a judged date whose day count since 1970-01-01 divides by long_window_days, so one site's looks never share a day; its rows enter that night's step; a site without the older window stores too_few_articles. article_length selects it; page_furniture joins once a stamp narrower than scorer_version lets a year-old window share its series (B11).
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity/comparisons/long_baseline.py (new)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py (long_baseline_weeks, long_window_days)
  - config/judges/summary-fidelity-judge.json (long_baseline_weeks, long_window_days; article_length selects long_baseline)
  - backend/tests/summary_fidelity/test_long_baseline.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite. Observation, not a gate: none until the eval ledger holds 52 weeks plus 28 days of scored days, about 2027-09 (estimate from the first scored day, 2026-08-22); until then each look stores too_few_articles.
- **Oracle:** a committed fixture with a steady decline over 52 weeks crosses where the 7-against-28 comparison does not; a judged date whose day count does not divide by long_window_days stores no long_baseline row. Cannot settle: a decline younger than long_baseline_weeks, which it sees only in part; a site younger than 56 weeks; an editorial change against extraction rot.

Table V1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| V1.1 | One look per block of long_window_days: the step bounds the false share within one night, not repeats across nights, and looks that never share a day make a site's yearly false count about 13 times the rate of one look | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P16) |
| V1.2 | 52 weeks keeps weekday and season, and the comparison reuses the declaration's own kind, so a long look tests what a nightly look tests | Andre (reviewed 2026-10-11); owner, 2026-10-11 (P16) |

Table V2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| V2.1 | Nightly long looks, or a 12-week baseline | Nightly looks crossed 4 times as often with no change, and a 35-day replay cannot measure their yearly rate; 12 weeks caught a 40 percent yearly decline 9.7 percent of the time | Faster detection: week 43 rather than 48 at 20 percent a year | Andre (reviewed 2026-10-11) |
| V2.2 | A cumulative sum over the judge's nightly effects | Overlapping windows count one excursion many times (a false alarm by week 6 in simulation); it has no p-value for the step and no history before the switch | Its own false-alarm calibration | Andre (reviewed 2026-10-11) |
| V2.3 | A comparison at every recorded input change | No window may turn on the input record; with weekly changes one change sits inside the previous change's before-window | None; the console already draws the model-change boundary | Andre (reviewed 2026-10-11) |
| V2.4 | Re-score live items with one input swapped (metamorphic checks) | Needs extra scorer passes in the scoring job, a new eval-row field (Level 5) and a cost measurement first | Extra scorer passes per scored run, not measured | Andre (reviewed 2026-10-11) |

## 3. Owner rulings

Table P - owner rulings: P1 to P19 ruled on 2026-10-11; P20 to P38 pending

| # | Question | Ruling | Evidence | Rows |
| --- | --- | --- | --- | --- |
| P1 | Sign off the judge's ledger: family summary-fidelity-judge, ledger drift-evals, its path (H4.1), the row shape (H1 to H3) with the reviewers' changes to it (copied_phrase_share; threshold_crossed and threshold_not_crossed; check_name; baseline_value and recent_value; the effect definition; q_value per (run_id, date); the settings in force on every row), the key with the council run and the reader's rule (H4.5), and one (run_id, date) pair as one false-discovery family (M1.2) | Approved; the ledger name was changed to drift-evals by the owner on 2026-10-11, who disapproved site-drift-evals | ledger-registry.md lists what a new ledger owes and the rule a judge ledger follows; row #3 makes every edit in one change. The changes fix a field name the console's query engine reserves, a medians field that also held shares and rates, an effect that divided by zero and ranked small sites first, and outcome names that read as "nothing moved" (Fowler and Andre, 2026-10-11) | 3 and every later row |
| P2 | Unusually-short check: the exact beta-binomial tail instead of reshuffling, counting recent articles with strictly fewer words than the cut, with page types combined by adding each type's exact tail; a type with no baseline article has no cut and its recent articles are left out | Approved | When the cut is the j-th shortest of N_b baseline articles, the count below it follows BetaBinomial(N_recent, j, N_b - j + 1) with no change; this is the exact form of the reshuffling already approved (checked against every reshuffle of a small case, to 2e-16). With no change it fires on 0.17 to 0.44 percent at 0.5 percent and 2.45 to 4.83 percent at 5 percent (exact, baselines 20 to 102, recent 21 and 40); counting ties as short would fire 0.60 to 2.44 percent at 0.5 percent | 6 |
| P3 | Article-count check: raise a daily variance under the daily mean to the mean, and add the baseline's own noise to the variance (x (1 + recent_days / baseline_days)) | Approved | The negative binomial is undefined when the daily variance is under the mean, which happened in 54 percent of Poisson samples. The baseline rate is itself estimated: with the term, false rates were 0.0055 to 0.21 percent at 0.135 percent nominal (200,000 repeats; 1.5, 4 and 10 a day; Poisson, spread twice the mean, and quiet weekends). Over-dispersed sites still fire up to 3 times nominal at 0.0001, so row #8's replay reports article_count on its own | 5 |
| P4 | Reshuffling: stop once 10 reshuffles give a distance at least as large as the observed one (a tie counts); cap at the larger of 100,000 and 10 x (tested checks in the run) / false_discovery_rate - 1, counted before any reshuffle (its seed clause was withdrawn on 2026-10-11 by the owner's ruling that determinism is not an expectation); every one of these numbers in the settings file | Approved | The smallest p-value 9,999 reshuffles can give is 0.0001, which equals the first threshold at 500 checks (0.05 / 500), so from 500 checks a lone crossing becomes impossible. With early stopping an unchanged check used about 101 reshuffles instead of 9,999, and the p-values stayed valid over 1,000,000 checks. Not counting ties fired 5.8 percent at 5 percent nominal on tie-heavy scores; counting them fired 4.0 percent | 7, 8 |
| P5 | Which console page carries the panel (Model or Judgement), and whether the drift-evals compact files are published on the site | Approved: Model page; publish | The Model page already reads the score and item-health ledgers and lists the sources the checker doubts; the Judgement page reads the similarity judge's merge line, which no check here touches; the Data explorer reads only ledgers in ledger.published | 12 |
| P6 | Where the judge's numbers live: config/judges/summary-fidelity-judge.json, read only by the judge | Approved | Every number bounded in one file an autotune loop can move. A block in config/idhazh.json would put a fourth judge contract in the council's import closure, because the council's registry imports AppConfig, and llm-council.md says that list cannot grow. The house already keeps one file per gardener task (config/gardener/), per console page (config/console/) and per model (config/models/) | 2 and every later row |
| P7 | scipy: an optional extra named for what it carries (statistics), installed by the council's planning, judging and collecting jobs | Approved | The planning job imports every registered tenant module to resolve its slug, and the collecting job runs settle; both install only pip install -e . today, so a scipy import reached from the tenant module would fail every judge's night. CI installs the dev extra, so the tests would stay green. R11 named the drift job, which row #1 deletes | 5, 9 |
| P8 | Build the judge in the council from the first row, with one unit a night computing and settle filing (H4.7), and no stage in drift.yml that later moves | Approved | Nothing is built yet, so there is nothing to migrate; CLAUDE.md section 14 asks for each increment in its intended code path; the council already gives a nightly schedule, one commit path and a writer identity. A shard_count of 0 would break the council's own record, so the judge pays one runner job a night (with the council plan's row 'Judges carry a status and a model need', no model server: runs_model false) | 1, 3 and every later row |
| P9 | Drop urgent and urgent_p_value, which R9 kept | Approved | Their only reader, the issue title, went with the issues; a p-value says how unlikely a drop is by chance, not how much it matters, so "urgent" claims a priority nothing measured (CLAUDE.md section 0b); the stored q_value and effect already rank a crossing | 3, 8 |
| P10 | Repair dates: this judge names none in its first version (B8), and a council plan of its own fans out each tenant's own repair dates before a third judge arrives | Approved; superseded on 2026-10-11 by the council plan's P2, which builds each judge's own repair dates now (B8) | A council date runs every tenant, so a date only this judge named would make the content-similarity judge re-judge a night it already counted, at model cost. The cost of naming none: a night only this judge missed stays missing, and the next window shares six of its seven days (Fowler, 2026-10-11) | 3 |
| P11 | The reviewers' fixes to the checks: distances and the furniture share within page type (J1.3, K1.4); a pair with 1 to 19 baseline articles compared with earlier pairs (L1.3); the scorer reference check outside the false-discovery step (withdrawn with row #10, D3); readers count stretches (H4.9); the replay reshuffles each article's label once per site | Approved | With full articles cut by a quarter and the mix moving toward them, the pooled distance flagged 0 percent and the per-type distance 61 percent; pooled Fisher fired 9.6 percent at 5 percent nominal when the mix moved with no change; a pair with 1 to 19 baseline articles fell into the gap R4 closed; overlapping windows do not raise the false rate per night, they group crossings into stretches (Andre, 2026-10-11) | 6, 7, 8 |
| P12 | Two optional refinements: leave out of the step a check whose smallest reachable p-value is above false_discovery_rate; and count articles item-health rejected as too short as below the cut | Deferred to row #8's replay | Neither was measured here; the second needs item-health to record a too-short rejection per address, which is not checked | 6, 8 |
| P13 | Separate what the judge measures from how it tests: the settings file declares each measure (metrics, F1.13; H1), five kind modules and four comparison modules test them, check_name stores a declared name with test_kind, value_unit, comparison and check_definition beside it, a declaration never changes meaning under one name, and a new one lands paused until row #8's replay has run it (G1.1 to G1.5, H2.6, H3.20 to H3.23); this amends P1's row shape and key | Approved | A sixth measure of an existing kind becomes one config entry (Level 3) instead of a stored-shape change (Level 5) and a console edit; a new kind of test stays a module and a review; the gardener separates declarations from kind modules the same way (knobs_gardener.py); Fowler and Andre debated it to one design (2026-10-11) | 3, 4 and every later row |
| P14 | A replaced model or scorer starts a new series, and no row compares two scorers inside the step (G1.6; changed_part, H3.24); until the eval row carries a narrower stamp (B11), copied_phrase_share, faithfulness and page_furniture group on scorer_version (G1.7), which brings page_furniture back to the old review's split | Approved | "Slicing costs a long article 0.40 of its score" (docs/concepts/evaluation.md), so a scorer move changes the instrument, not the pipeline; extraction_suspect is a counterweight METRICS_VERSION names, and METRICS_VERSION "is folded into scorer_version". Cost: each scorer_version move keeps those three measures out of the step for up to 14 days per site, band-threshold moves included; the alternative is a narrower stamp on the eval row first (Level 5, B11) | 4, 6, 7 |
| P15 | The composite score: adopt the calibrated combined_measures check (row #13) instead of the pasted composite; reject its fixed bands, its veto and its automatic actions (M2.3, M2.4); keep every action out, with a staged way back in that a ledger of a person's marks must earn first (B2) | Approved | Simulated at this pipeline's sizes (Andre, 2026-10-11): the pasted composite went red on 19 percent of unchanged nights at a site with half an article a day, stayed green for a 79 percent length cut (0.25 x 0.79 = 0.198, under the 0.20 line) and for a faithfulness fall from 0.85 to 0.40, and scored 0.18 on the #1270 mix change alone; three slips that each crossed alone 11 to 15 percent of the time crossed together 43 percent of the time in combined_measures; a judge that steers what it measures adopts its own actions as its baseline | 8, 12, 13 |
| P16 | In place of D3's dropped reference rows: an all-sites comparison (row #13) and a long-baseline comparison for article_length (row #14, useful from about 2027-09) | Approved | Neither keeps a fixed article set, so both survive housekeeping: the eval ledger keeps its measurements for 36 months after their articles go. In simulation, the whole-day all-sites check caught a shared step too small for any one site (0.02) 82 to 97 percent of the time, where a single site caught it 6 to 10 percent; the 7-against-28 window has no power against a slow decline, and 52-week blocks caught a 40 percent yearly decline every time | 13, 14 |
| P17 | Combine weights: scored only on the replay's injected slips and reshuffled dates, never on live crossings, and fixed before any night they judge; the replay prints the best weights and a person commits them; an autotune loop never writes the settings file, and an automatic loop would file damped, clamped rows in a ledger of its own, at Level 5, not built here (F2.2, F2.6) | Approved | Weights chosen this way move detection power, never the false-crossing rate, because the p-value comes from the same re-deals whatever the weights; weights fitted on live crossings would let the alarm choose what it alarms on | 8, 13 |
| P18 | The reading budget counts new stretches: a typical night is the mean number of new stretches per judged date after the first seven; the count is split by check, and a check that crosses on reshuffled dates more often than false_discovery_rate is fixed first; false_discovery_rate 0.01 stays the second lever (M1.5). C5 would read: "No stop: the row splits the count by check, fixes a check that crosses too often on reshuffled dates, then sets false_discovery_rate to 0.01 and replays again before the switch; only a typical night still over the budget is reported, as a finding with options, never as a veto" | Approved | One real change stays in the recent window seven nights, so a count of crossings per night counts it seven times; in simulation, lowering the rate first removed 3.4 crossings a night, 2.7 of them real (Andre, 2026-10-11) | 8 |
| P19 | Outside this plan: correct the evaluation persona's file, .github/agents/andre.agent.md, which says this pipeline runs "pinned and deterministic so a re-run is a re-run" | Approved, as one small commit of its own | The owner ruled that determinism is not an expectation, and determinism.md says "Determinism is not a property a summarizer needs"; a persona that expects a repeat would review every later plan against it | none |
| P20 | Unit of judgment: the whole digest, per production model series with per-column instrument keys (P14); a prompt or runtime change labels the crossings inside its window rather than starting a series; sites, article count, unusually short, page furniture and article length are no longer judged, and article length and source become covariates | Pending; recommended: approve | Per-site cells are too small to test, and the one summariser-side change on record moved inside sources: the 99 sources present in both weeks moved -0.101 against -0.103 overall (review record, Andre 1.1); the research treats length, source and page type as covariates (research record 7.3); splitting a series on every input would blind the judge 13 nights after each change, about every 9 days | 3, 4, 7, 15, 8, 13, 12 |
| P21 | The judged set of Table RA: faithfulness (an index and two shares), unsupported numbers and dropped hedges judged; copying and summary length watched as behaviour; coverage, coherence and the input mix as diagnostics; loops and too-short summaries paused until their base rates are known. Amends P13: each declaration gains role, statistic, line, adjust_by and rho, and the kinds become statistics tested by one module | Pending; recommended: approve | LLM-era frameworks judge faithfulness, completeness and conciseness; fluency is near ceiling; adjacent-sentence cosine and top-20-word coverage are unvalidated (research record 1.2 and 2.5); no column measures completeness or conciseness today (P32) | 4, 7, 15 |
| P22 | The test: a recency-weighted 7-day window (recency_lambda 0.15) against the 28 days before it, whole days re-dealt with one deal for every member, widened for each member's day-to-day correlation (rho, proposed by the replay and committed by a person), on values adjusted for length band and source with the raw value stored beside; days under 100 rows left out | Pending; recommended: approve | It held its false rate at every baseline length simulated, and 0 of 8 stable real nights crossed; control limits taken from a reference window alone crossed 4.5 to 53 times their nominal rate in simulation and on 7 of the same 8 real nights; a 56-day reference would span every pipeline regime on record (review record, SP4) | 7, 15, 8 |
| P23 | false_discovery_rate stays 0.05 | Pending; recommended: approve | With no change, 0.10 drift readings a month; 0.01 gives 0.03 but loses about 20 points of power on marginal changes (review record, SP6) | 8 |
| P24 | The composite: every member keeps its own row; two calibrated combined rows enter the same step - quality_worse, the weighted positive parts of the quality members, so an improvement never offsets a harm, and something_changed, a T-squared over the quality and behaviour members; a person reads evaluator check, drift (two consecutive nights), watch or quiet; nothing acts. Amends P15 | Pending; recommended: approve | The 2026-09-07 step was a behaviour change a quality composite must not call worse, yet a person must see it; a signed, correlation-normalised sum lets an improvement cancel a harm; the per-item publish gate stays a veto chain (research record 5 and 7.4; review record, SP5) | 13, 12 |
| P25 | Weights and rho: start from reader harm - faithfulness 3 across its three rows, unsupported numbers 3, dropped hedges 2; the replay scores candidate weights by their worst detection across an injection library (swapped numbers, entities and dates, negated statements, dropped hedges, truncation, a copied lead, repetition) and proposes rho; a person commits both; a new member lands paused with weight 0 and rho 0. Sharpens P17 | Pending; recommended: approve | Calibration does not depend on the weights, because every p comes from the re-deals; weights fitted on live crossings would let the alarm choose what it alarms on | 8, 13 |
| P26 | The rows of Table RB and the settings of Table RC; amends P1: DriftEval loses site and page_type and gains the fields RB2 names, with the key run_id, date, check_name, comparison, model_id, instrument | Pending; recommended: approve | Nothing is written to drift-evals yet, so a shape change costs plan edits only; after row #3 merges, every change is a migration (review record, Fowler 2.5) | all |
| P27 | Withdraw P7 (scipy in an optional extra installed by the council's jobs): the redesigned test needs only numpy | Pending; recommended: approve | The exact tails P7 served left with rows #5 and #6 | 9 |
| P28 | The long-baseline comparison (row #14) moves to Table B with its trigger - 52 weeks plus 28 days of scored history, about 2027-09 - and then covers the quality members | Pending; recommended: approve | A gated row would hold this plan open for about a year (review record, Fowler 7) | 14 |
| P29 | drift-evals names a kind of thing, which the owner's registry rule of 2026-09-27 forbids ("The value says what the ledger holds, never the kind of thing it is"): keep drift-evals and add a dated exception line to ledger-registry.md, or rename it summary-drift-evals | Pending; recommended: keep drift-evals with the exception line | The owner chose drift-evals on 2026-10-11; the cost is that no other judge can use the name (review record, Fowler 2.5) | 3 |
| P30 | Drop row #9's peak-memory observation | Pending; recommended: approve | No machine is recorded per unit, so nothing could read it (review record, Fowler 7) | 9 |
| P31 | A plan of its own, outside this judge: sentence-level faithfulness (each summary sentence against its best article window; the mean, the minimum and the sentences under 0.50 and 0.80), entity and date checks, and per-column instrument stamps, as one eval-row change after a one-day measurement | Pending; recommended: approve, as a separate plan | Scoring the whole summary against each window marks down multi-window articles: a 2-window article scores 0.22 and a 3-window article 0.40 below the same article read whole; about 3 times today's 12.5 scorer-minutes a day (estimate); Level 5; plan 36's 0.50 line must be re-cut on the new score (research record 4; review record, SP3) | - |
| P32 | Completeness and conciseness: pilot a sampled key-fact judge, never the summariser, on injected omissions before building it, its scores in a ledger of its own; a second faithfulness checker only after P31, as a 100-a-day trial | Pending; recommended: approve the pilot only | The only route to completeness and conciseness, unproven at 9B; 20 to 75 runner-minutes a day (estimate); a second checker adds 1 to 3 GB of memory and a dependency (review record, SP3) | - |
| P33 | Plan 36: this judge supplies the drift alarms; plan 36 drops its fit and fold rows (1, 2, 4, 5) and its self-judged fluency (rows 6 and 10), keeps the publish gate on absolute lines, the rejects ledger and rows 3, 8 and 13, re-points its console row to this judge, and fixes three stale premises: a fluency leg in an old workflow, a history rewrite in prune.yml that CLAUDE.md section 8 forbids, and an unregistered state/rejects/ that the gardener's sweep would empty (its retention a 30-day exception) | Pending; recommended: approve, as a revision of plan 36 | Plan 36's own correction E1 made every adaptive floor a watch-only fleet alarm, which is this judge's job, and two alarms per metric would disagree; self-judged fluency carries every documented judge bias on a near-ceiling dimension (research record 2.3; review record, Fowler 3 and Andre 6) | - |
| P34 | Per-source extraction health: a source-health check in feed-health or item-health, in a plan of its own | Pending; recommended: approve | Row #1 deletes the only per-site extraction checks, and no summary metric sees one source's extraction breaking (RD6) | 1 |
| P35 | Accepting a known change: later, a person's mark resets one member's baseline; until then a deliberate change that starts no series reads as drift for up to 35 days | Pending; recommended: later, with B2's ledger of marks | The pipeline changed about every 9 days (RD5) | - |
| P36 | Correct the evaluation persona's line that calls a model judge a project non-goal, which contradicts CLAUDE.md section 1a | Pending; recommended: approve, as one small commit | CLAUDE.md section 1a: "LLM-as-judge is primary evaluation where applicable" | - |
| P37 | Move Table Q to a standing file, TODO/owner-requests.md, read first and updated in every session | Pending; recommended: approve | A plan-doc is deleted when it closes, and Table Q already tracks other plans' items (review record, Fowler 6) | - |
| P38 | P31's eval-row change also makes the faithfulness scorer replaceable: the scorer, its pinned revision and its window size are named in config, the eval column gets a name that does not name HHEM, and RC8's test reads the window size from that declaration | Pending; recommended: approve | The owner gave Q15's reason as "we may change the evaluator or something else". The judge side already copes: a replaced scorer starts a new series (P14), and each member names its instrument (RC11). The scorer side does not: hhem.py pins the HHEM model and revision as code constants, the column is named hhem, and CLAUDE.md section 10 asks for model references in config. P31 already restarts the faithfulness series, so doing it there costs no second restart; the rename reaches every reader of the column (Level 5) | P31's plan |

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
| Q8 | 2026-10-11 | Is the council's model time a concern for this judge? | Done | The council plan's row 'Judges carry a status and a model need': this judge runs no model server | - |
| Q9 | 2026-10-11 | A golden or reference set is impossible here; use trailing windows or a better scientific approach | Done | Rows #10 and #11 collapsed (D3, B10); P16 | Carried into the redesign (Q20) |
| Q10 | 2026-10-11 | Determinism is not an expectation; no back door | Done | C10, K1.5; the persona sentence corrected (P19, commit f1e7738) | - |
| Q11 | 2026-10-11 | determinism_violation should probably go | Out of this plan | B9 | A plan of its own when the owner asks for it |
| Q12 | 2026-10-11 | Judges need a lifecycle status, as ledgers and gardener tasks have | Planned | The council plan's row 'Judges carry a status and a model need', Table E3 | Build |
| Q13 | 2026-10-11 | The council should follow the gardener's strengths: capability, observability, flexibility, commit, sparse | Planned | The council plan, rows #1 to #9 (council P1 to P8 approved) | Q22 maps each strength to its row |
| Q14 | 2026-10-11 | Each judge runs over its own outstanding dates (council P2, approved) | Planned | The council plan's row 'Each judge runs over its own outstanding dates'; B8 | Once it lands, this judge's nights_outstanding names its own missed dates |
| Q15 | 2026-10-11 | The judge must support new metrics: what it measures separate from how it tests, "because we may change the evaluator or something else" | Done in design for the judge; reopened 2026-10-11 for the evaluator | P13 (approved), row #4; P14 (approved): a replaced scorer starts a new series. The scorer itself is still HHEM, fixed in code | Carried into the redesign (Q20); the owner rules P38 |
| Q16 | 2026-10-11 | A composite weighted score, tunable as metrics are added, to decide when something drifted; the pasted penalty, band and veto proposal | Done in design, reopened | P15 and P17 (approved): a calibrated combined check, no automatic actions | Reopened by Q24 |
| Q17 | 2026-10-11 | Approve the recommendations of the last review (judge P13 to P19; council P1 to P8) | Done | Both Table P | - |
| Q18 | 2026-10-11 | The ESCALATE triggers table does not render | Done | Table C's delimiter row had three cells for four columns; F1.5 had an extra cell | - |
| Q19 | 2026-10-11 | Disapprove site-drift-evals; use the generic name drift-evals | Done | H4.1, row #3, P1 | The contract and its stem follow: DriftEval, drift-eval |
| Q20 | 2026-10-11 | Judging per site is wrong: judge summary quality - faithfulness, coherence, conciseness and the other standard metrics - and the variance of the metrics in autotune-summary-quality.md, taking good elements from its loop | Proposed | Section 4; P20 to P30 | The owner rules P20 to P30; then rows #2 to #14 are rewritten |
| Q21 | 2026-10-11 | A hard look at what matters, how we measure it, and what is measured and judged upon | Done | Review record (TODO/20261011-summary-fidelity-judge-review-record.md); Section 4 | Rulings P20 to P37 |
| Q22 | 2026-10-11 | Which council rows bring the gardener's lifecycle, logging, telemetry and other strengths? | Answered | The council plan's Table T maps each gardener strength to its row | The owner rules the council plan's P9 to P11 |
| Q23 | 2026-10-11 | Survey recent research on news and long-form summary metrics; use what is reasonable instead of a small set | Done | Research record (TODO/20261011-summary-quality-metrics-research-record.md); Section 4 | Instrument changes ruled as P31 and P32 |
| Q24 | 2026-10-11 | How to make a composite metric that decides | Proposed | Section 4 (the rule); P24, P25 | The owner rules P24 and P25 |
| Q25 | 2026-10-11 | Keep track of every item so nothing is lost | Done, standing | This table | Update it in every session that touches these plans |
| Q26 | 2026-10-11 | Plan 36 already designs fleet alarms on the same four metrics (raised by the review, not the owner) | Proposed | P33 | The owner rules P33; then plan 36 is revised |
| Q27 | 2026-10-11 | The evaluation persona still calls a model judge a project non-goal, against CLAUDE.md section 1a (raised by the review, not the owner) | Proposed | P36 | The owner rules P36 |
| Q28 | 2026-10-11 | Write the research record's formulas as math that GitHub renders, not invented ASCII such as sqrt | Done for the research record | Research record, commit fce0749 | This plan's section 4 and the review record still write math in ASCII; convert them when the owner asks |
| Q29 | 2026-10-11 | What Display and Display only mean in the research record's table 5.1; what the redesign takes from the research, what it does not, and why | Answered | Research record, under table 5.1 (the terms); review record SP1 row s9 and section 4 of this plan (taken and not taken) | - |
| Q30 | 2026-10-11 | Number the council plan 64 and commit it to main directly | Done | TODO/20261011-64-council-follows-gardener-plan.md, titled Plan 64 | - |
| Q31 | 2026-10-11 | Find the ambiguities in plan 64 and ask about them in the CLAUDE.md options format | Ruled | Plan 64's Table P: P10 to P18 ruled, P9 declined | - |
| Q37 | 2026-10-11 | Deliver plan 64 as merged pull requests, with Fowler resolving any ambiguity | In progress | Plan 64's Status Reckoner | Each row lands as its own pull request, merged on green CI |
| Q32 | 2026-10-11 | A paused or retired judge is not processed by the council, and retirement does not mean deleting code; is that how the gardener works? | Done in design | Plan 64 P15, row #11. The gardener skips paused and retired tasks but refuses a module no active or paused task uses | - |
| Q33 | 2026-10-11 | Pair each exit code with a label that says what it means, per pipeline | Done in design | Plan 64 P16, row #3 | - |
| Q34 | 2026-10-11 | Allow judges to be run by hand | Done in design | Plan 64 P17 and P11, row #7: one date per manual run | - |
| Q35 | 2026-10-11 | The council has its own config, each judge has its own config, and judges register with the council, as the gardener does | Done in design | Plan 64 P18, rows #10, #11 and #1 | This judge's file carries lifecycle_status and runs_model, and its package is summary_fidelity_judge, when this plan's rows are rewritten |
| Q36 | 2026-10-11 | Record a judge's switch to active in the commit message and docs, not in a test; the gardener may be wrong to use one | Done | Plan 64 P9 declined, E1.5; the gardener's test dropped in #1548, merged 2026-10-11 | - |

Table R - the review changes the owner approved on 2026-10-10, and where each lands now

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

## 4. Redesign proposed on 2026-10-11 (pending P20 to P37)

Evidence: TODO/20261011-summary-quality-metrics-research-record.md (76 verified sources) and TODO/20261011-summary-fidelity-judge-review-record.md (Andre's and Fowler's reviews, replayed on the 50 daily records under state/day-metrics/, 2026-08-21 to 2026-10-10).

In one paragraph: the judge judges the quality of the digest's summaries, per production model series, not each site's articles. Each night it compares the last 7 days, recent days weighted more, with the 28 days before, re-dealing whole days to learn what no change looks like, after adjusting each summary for its article's length band and source. Faithfulness, unsupported numbers and dropped hedges are judged; copying and summary length are watched as behaviour; coverage, coherence and the input mix are shown as diagnostics; article length and source are covariates, never judged. Two combined rows sit beside the members, quality_worse and something_changed, and a person reads one of four levels. Nothing acts.

Table RA - what is judged (declared per P13 as amended by P21)

| # | Member | Role | Column and daily statistic | Adjusted for | Worse when | Status at landing | Weight |
| --- | --- | --- | --- | --- | --- | --- | --- |
| RA1 | faith_index | quality | mean of logit(hhem), clipped at logit_clip | length band, source | lower | active | 1 |
| RA2 | faith_below_050 | quality | share of hhem under 0.50 | length band, source | higher | active | 1 |
| RA3 | faith_below_080 | quality | share of hhem under 0.80 | length band, source | higher | active | 1 |
| RA4 | numbers_unsupported | quality | share with at least one unsupported number | source | higher | active | 3 |
| RA5 | hedges_dropped | quality | share with hedge_dropped | source, article hedging present | higher | active | 2 |
| RA6 | repetition_loops | quality | share with self_repetition above 0.05 | none | higher | paused until its base rate is known | 0 |
| RA7 | length_short | quality | share under 25 summary words | none | higher | paused until its base rate is known | 0 |
| RA8 | copy_index | behaviour | mean extractiveness | never | higher | active | in something_changed only |
| RA9 | copy_ceiling | behaviour | share with verbatim_run above 0.50 | never | higher | active | in something_changed only |
| RA10 | length_median | behaviour | median summary words | never | either | active | in something_changed only |
| RA11 | scored_nulls | evaluator | share of rows missing hhem, coherence or semantic_coverage | none | higher | active | - |
| RA12 | coverage, coherence, input mix | diagnostic | semantic_coverage and coherence (median, low tail, spread); length-band shares, source composition, extraction_suspect rate | - | - | stored with p, outside the step | - |

Not judged: compression, hhem_full, hhem_delta, score_ms, band, determinism_violation, and fluency as plan 36 specifies it (P33). Completeness and conciseness wait for an instrument (P32). Rows flagged extraction_suspect leave the quality members.

The rule, as a builder implements it (full form in the review record, section SP5):

- Per summary i and quality member m: y is the member's value; the expected value e is the baseline mean of the summary's length band plus a shrunken source offset (source_shrinkage_rows); the residual is y - e. Behaviour members are never adjusted.
- The daily value x_d is the mean residual of day d (the median of y for length_median), weighted by the day's row count n_d; a day under min_day_rows is left out and stored as thin.
- T_m = h_m x (recency-weighted mean of x over recent_days, weight lambda (1 - lambda)^age, minus the n-weighted mean over baseline_days), where h_m is +1 or -1 by harm direction.
- No-change case: whole days of the two windows re-dealt, the same deal for every member and both combined rows; z_m is T_m standardised against the deals and divided by sqrt((1 + rho_m) / (1 - rho_m)); p_m = (1 + deals at least as large) / (deals + 1).
- quality_worse: S = sum of omega_m x max(z_m, 0) over active quality members, so an improvement never offsets a harm. something_changed: T2 = z' V+ z over active quality and behaviour members, V the covariance of z over the deals. Both take their p from the same deals.
- One false-discovery family per (run_id, date, series): the active members and the two combined rows, Benjamini-Hochberg at false_discovery_rate. Paused members and diagnostics keep a p and get no q.
- Reading levels, derived from stored rows: evaluator check (an evaluator row crossed; read it before calling anything drift); drift (quality_worse, something_changed or a quality member crossed on drift_consecutive_nights consecutive nights); watch (any other crossing); quiet, too few days, or new series. Every crossed row prints its effect raw and adjusted, its q, and the inputs that changed inside its window.
- A new member lands paused with weight 0 and rho 0; the replay runs it on past dates and on injected changes; the owner makes it active; a person commits its weight and rho.

Table RB - the rows after the redesign

| # | Row | Depends-on | Level | Change |
| --- | --- | --- | --- | --- |
| RB1 | #1 The drift review is deleted | - | 3 | Unchanged, except that its removed-setting message no longer names min_articles as moved |
| RB2 | #3 The judge's ledger and its tenant module | council plan: Judges carry a status and a model need | 5 | DriftEval loses site and page_type and gains the member slug, role, statistic, model_id (always set), instrument, recency_lambda, rho, raw and adjusted values, inputs_changed and day counts; key run_id, date, check_name, comparison, model_id, instrument |
| RB3 | #4 Settings file and member declarations per model series | 3 | 3 | Absorbs row #2's settings file; site identity is deleted; declarations gain role, statistic, line, transform, adjust_by, instrument and rho |
| RB4 | #7 Per-summary values, daily values and the mix adjustment | 4 | 3 | Replaces the per-check modules of rows #5 to #7 |
| RB5 | #15 The recency-weighted whole-day test | 7 | 3 | New: one test module for every member |
| RB6 | #8 The false-discovery step per (run, date, series), and the replay with an injection library | 15 | 3 | The replay also proposes weights and rho (P25) |
| RB7 | #9 The switch | 1, 8 | 3 | Its peak-memory observation is dropped (P30) |
| RB8 | #13 The two combined rows and the reading levels | 9 | 3 | Replaces the all-sites and combined-measures row |
| RB9 | #12 The panel on the console Model page | 9 | 3 | Lists crossings by level, smallest q first |
| RB10 | #2, #5, #6 | - | - | COLLAPSED: site identity; article count, which is feed volume; unusually short and page furniture, which are input properties |
| RB11 | #14 | - | - | Moves to Table B with its trigger (P28) |

Table RC - settings that change (config/judges/summary-fidelity-judge.json; the rest of F1 stays)

| # | Field | Default | Range | Note |
| --- | --- | --- | --- | --- |
| RC1 | recent_days | 7 | 7 to 14, whole weeks | F1.1, range narrowed |
| RC2 | baseline_days | 28 | 14 to 56, whole weeks | F1.2, range narrowed |
| RC3 | recency_lambda | 0.15 | 0 to 0.5; 0 is a flat window | New |
| RC4 | min_day_rows | 100 | 20 to 1000 | Replaces min_articles (F1.3) |
| RC5 | min_recent_days, min_baseline_days | 4, 7 | 3 to 7; 7 to 28 | New |
| RC6 | drift_consecutive_nights | 2 | 1 to 7 | New |
| RC7 | logit_clip | 0.001 | 0.000001 to 0.01 | New |
| RC8 | length_band_edges_words | 900, 1650 | ascending, 100 to 10000 | New; a test holds them to HHEM's window geometry |
| RC9 | source_shrinkage_rows | 10 | 0 to 100 | New |
| RC10 | trailing_line_quantile | 0.10 | 0.01 to 0.25 | New; diagnostic tails |
| RC11 | metrics | RA1 to RA12 | role, statistic, line, transform, harm_direction, adjust_by, instrument, combine_weight 0 to 10, rho 0 to 0.8, lifecycle_status | F1.13 as amended by P21 |
| RC12 | short_tail_percentile, multi_tenant_hosts, page_types | - | - | Removed (F1.5, F1.9, F1.10) |

Table RD - what the replay on the real record showed (Andre, 2026-10-11)

| # | Finding |
| --- | --- |
| RD1 | 2026-09-07: watch from 09-09 (copying up), drift from 09-12 (something_changed). Faithfulness rose because the summaries copied more; quality_worse never crossed in the 50 days |
| RD2 | 2026-09-24: drift from 09-26 on shorter summaries and more dropped hedges; part of the hedge rise is an artefact of the band-reason ranking, so the judge reads the eval-row column, never band reasons |
| RD3 | Stable nights: 0 of 8 crossed. With no change, 2.4 percent of nights cross a row, and drift is read 0.10 times a month at q 0.05 (0.03 at q 0.01) |
| RD4 | Detection over a full week: 5 percent of summaries unfaithful 1.00; 2 percent 0.72; one 10-a-day source unfaithful 0.95; unsupported numbers doubled 0.74; dropped hedges up 3 points 0.29, the weakest |
| RD5 | The pipeline changed about every 9 days, and every crossing on record traces to a dated change, so a crossing names the inputs that changed inside its window |
| RD6 | No summary metric sees extraction breaking on one source, and row #1 deletes drift.py's per-site checks; extraction_suspect was 0 on all 50 days (P34) |
