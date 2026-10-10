# Summary fidelity judge

**Last Updated**: 2026-10-11
**Level**: 5 (CLAUDE.md section 6). Rows #3, #10 and #11 declare persisted shapes and pause for the owner; every other row states its own level.
**Status**: drafted 2026-10-11 from the drift-review plan of 2026-10-10, whose 16 review changes the owner approved (Table R). The owner then ruled to stop the drift review, to store every check in a ledger under state/raw/ in parquet, and to run the work as a judge in the LLM council. Fowler and Andre reviewed it on 2026-10-11 and settled two contested items in debate. The owner ruled P1 to P12 on 2026-10-11 (P12 deferred to row #8's replay). No row started.

## 0. Operating contract

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 4 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. AUTHOR-AND-STOP until the user authorizes.

Table A - operating contract

| # | Field | Value |
| --- | --- | --- |
| A1 | Why this plan exists | The weekly drift review compares per-site medians against fixed percentage thresholds. A median jumps between two kinds of page when their shares cross one half, so a change in a site's mix of story types reads as drift (issue #1270); the thresholds ignore sample size and per-site spread; every result lives only in a GitHub issue that nothing can query; and the review runs in a workflow of its own, outside the council where the project's judges run. |
| A2 | Hard scope - in | - The drift review, its workflow and its settings are deleted (row #1)<br>- The judge's settings in a config file of its own, every number bounded, and site identity: the host, listed multi-tenant hosts, declared page types (row #2)<br>- The judge's ledger under state/raw/ and state/compact/, enrolled for compaction and retention, and its tenant module (row #3)<br>- Six checks, each with a p-value: article count (row #4), unusually short articles (row #5), article length and page furniture (row #6), copied phrases and faithfulness per model (row #7)<br>- One false-discovery step per judged date, and a replay that measures false crossings and detection (row #8)<br>- The switch: the judge joins council.tenants (row #9)<br>- Scorer reference and golden-set checks (rows #10, #11)<br>- The stored checks on a console page (row #12) |
| A3 | Hard scope - out | Table B |
| A4 | ESCALATE triggers | Table C |
| A5 | Chosen strategy | The owner-supplied blueprint of 2026-10-10 with the 16 review changes the owner approved on 2026-10-10 (Table R), built from the first row as a tenant of the LLM council (docs/architecture/publishing/llm-council.md), never as a stage of drift.yml that later moves (P8). Reviewed by Fowler (contracts, structure, process safety) and Andre (metric and evaluation design). |
| A6 | Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 4. Rows #3 to #8 run in order because each edits the judge's tenant module, its tests and its doc. |

### Hard scope - out

Table B - what is out, and what would bring it in

| # | What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- | --- |
| B1 | Any change to what the pipeline fetches, extracts, summarizes or publishes | A crossed check still needs a person to inspect extraction | A crossing that a person confirms as an extraction defect, handled in its own plan |
| B2 | Acting on a crossed check by itself: stopping publication, resting a feed, marking items, moving a knob | A real defect publishes until a person acts | An owner ruling that names the action for one check, once row #8's replay measures the share of that check's crossings a person confirms; a knob it moves follows the fitted-line pattern of autotune-content-similarity.md |
| B3 | GitHub issues, and any other notification | Nobody is told. A person reads the console panel (row #12), which shows a judged date once the gardener packs it and the site rebuilds, one to two days after the night that judged it | An owner ruling that one check warrants a notification, sent by a separate reader of the judge's ledger |
| B4 | Feed rest and retirement rules | A stopped feed is reported twice: feed-health rests it after five empty reads, and row #4's check crosses | A ruling that row #4 replaces part of feed quarantine |
| B5 | Judged dates before the judge's first night | The stored history starts at the switch. A person can judge a past date by dispatching the council with it, one date per run; the council's concurrency group keeps only one waiting run, so dispatches go one at a time | An owner ruling that history before the switch matters, priced in council runs |
| B6 | Moving the content-similarity judge's settings into a file of their own | The two judges keep their settings in two different places | A plan that moves them; this plan only sets the pattern for a new judge |
| B7 | Any check during the gap between row #1 and row #9 | No drift check runs while the judge is built | The owner rated the old review's output useless; nothing brings the old review back |
| B8 | Repairing a night only this judge missed: its nights_outstanding names no date | That date's rows stay missing; the next night's window shares six of its seven days. A night the whole council missed is still judged when another judge names it, because a council date runs every tenant | A council plan that fans out each tenant's own repair dates (night_plan.py, council_matrix.py, council_publish.py, llm-council.yml), due before a third judge arrives |

### ESCALATE triggers

Table C - when to stop and ask

| # | Trigger | What happens |
| --- | --- | --- |
| C1 | A row would declare a persisted shape: a contract under backend/idhazh/contracts/ read by a later run, a ledger, or a committed reference file with expected values | Stop. The owner rules on the shape (CLAUDE.md section 0). Row #3's shape was approved as P1 on 2026-10-11; rows #10 and #11 still stop here |
| C2 | A row needs a new runtime dependency, or a model or extra the council's jobs do not install today | Stop. Name the cost and the beneficiary (Guardrail #8); consult Carmack for runner minutes. scipy was approved as P7 on 2026-10-11 |
| C3 | A row's Decisions table cites a Table P item the owner has not ruled | Stop before implementation of that row |
| C4 | A check would read ledger files other than through ledger.load_days or the door's own indexes | Stop. The ledger door is the only reader (docs/concepts/growing-reads.md, Guardrail #12) |
| C5 | Row #8's replay shows more crossed checks per judged date than a person can inspect | Report it as a finding with options (CLAUDE.md section 0d), never as a veto |
| C6 | A new check crosses on the #1270 fixture (row #6) | Report it with options (CLAUDE.md section 0d) before merge |
| C7 | Text from an article address would enter a shell argument, a commit message or a file path | Stop (Guardrail #11) |
| C8 | A DriftConfig field has a reader outside the files row #1 deletes | Stop. The owner rules where that field moves before row #1 deletes the block |
| C9 | A judge module or contract would enter the council's import closure | Stop. backend/tests/council/test_council_runs_without_a_judge.py holds the seam, and the list of judge contracts that cross it may not grow (llm-council.md) |

## 1. Status Reckoner

Table D - rows

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | The drift review is deleted | - | A | PENDING | - | - | - |
| 2 | The judge's settings file and site identity | - | A | PENDING | - | - | - |
| 3 | The judge's ledger and its tenant module | 2 | B | PENDING | - | - | - |
| 4 | Article-count check from the item-health census | 3 | C | PENDING | - | - | - |
| 5 | Unusually-short check | 4 | D | PENDING | - | - | - |
| 6 | Article-length and page-furniture checks | 5 | E | PENDING | - | - | - |
| 7 | Copied-phrase and faithfulness checks per model | 6 | F | PENDING | - | - | - |
| 8 | One false-discovery step per judged date, and the replay | 7 | G | PENDING | - | - | - |
| 9 | The switch: the judge joins the council | 1, 8 | H | PENDING | - | - | - |
| 10 | Scorer reference check | 9 | I | PENDING | - | - | - |
| 11 | Golden-set check | 9 | I | PENDING | - | - | - |
| 12 | The stored checks on a console page | 9 | I | PENDING | - | - | - |

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
  - backend/idhazh/contracts/app_config.py (the drift field deleted; SUPERSEDED_APP_NAMES gains drift with the message that min_articles and min_window_rows moved to config/judges/summary-fidelity-judge.json and every other drift setting is gone; one changelog entry, the oldest entry deleted to keep five as CLAUDE.md section 11 allows; the validator's docstring names drift)
  - config/idhazh.json (the drift block deleted)
  - backend/tests/contracts/test_app_config.py and backend/tests/contracts/test_retired_knobs.py (re-derive at dispatch)
  - backend/tests/workflows/test_triggers.py and backend/tests/workflows/test_workflow_inputs.py (re-derive with git grep -n drift.yml backend/tests at dispatch)
  - docs/concepts/evaluation.md and docs/concepts/growing-reads.md
  - Every other reader of the deleted names, from git grep -n -i -e "drift.yml" -e "drift_report" -e "idhazh.drift" -e "DriftConfig" -e "Drift review" -e "app.drift" -e "test_drift" -e "min_domain_rows" -e "source_word_count_drop" -e "extractiveness_rise" -e "month_over_month_pct" -e "year_over_year_pct" -e "quarterly_refresh_fraction" -- . at dispatch
- **Acceptance gates:** local - ruff, mypy and the shared test selector over the contract and workflow tests per docs/how-to/run-the-gates.md; CI - full suite.
- **Oracle:** the search above finds history and nothing else, and a config that still carries a drift block is refused with a message saying which two settings moved to config/judges/summary-fidelity-judge.json. Cannot settle: who read the old issues; a person closes the four open drift issues.

Table E1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| E1.1 | The drift review is deleted before the judge is built, so nothing is migrated and no second implementation runs beside the first | Owner, 2026-10-11 (stop the drift review); P8 |
| E1.2 | No new code lives under a drift name; the judge's code lives in a package of its own, so later judges and later drift work each have a home | Owner, 2026-10-11 |
| E1.3 | month_over_month_pct, year_over_year_pct and quarterly_refresh_fraction go with the block when the search finds no reader; a reader stops the row (C8) | Owner, 2026-10-10 (B6 of the drift plan) |

Table E2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| E2.1 | Keep the drift review until the judge runs | The owner rated its output useless | Weekly issues from the old rules until row #9 merges | Owner, 2026-10-11 |
| E2.2 | Split drift.py into a package first, as the drift plan's row #1 did | Nothing will be added to it; the checks start in the judge's own package | A structural pull request whose result is deleted | Owner, 2026-10-11 |

### Row #2 - The judge's settings file and site identity

- **Scope:** config/judges/summary-fidelity-judge.json holds every number the judge uses (Table F1), validated by a model that forbids unknown keys and bounds every field and read only by the judge's own package, with each setting landing in the first row that reads it; this row lands the two site settings, and site.py decides a site and a page type: a site stays the host without a leading www., a host listed in multi_tenant_hosts (F1.10) adds its first path segment, and page_types (F1.11) names the path prefixes that mark a page type inside one site.
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
| F1.5 | short_tail_percentile | 0.05 | 0.01 to 0.25 | Baseline percentile whose length defines an unusually short article | 5 | Blueprint section 1 |
| F1.6 | reshuffle_stop_hits | 10 | 1 to 100 | Reshuffling stops once this many reshuffles give a distance at least as large as the observed one (a tie counts) | 6 | Owner, 2026-10-11 (P4) |
| F1.7 | reshuffle_cap_floor | 100000 | 1000 to 10000000 | The smallest cap on reshuffles per check | 6 | Owner, 2026-10-11 (P4) |
| F1.8 | reshuffle_cap_multiple | 10 | 1 to 100 | The cap is the larger of reshuffle_cap_floor and this times the tested checks in the run divided by false_discovery_rate, minus one, counted before any reshuffle | 6 | Owner, 2026-10-11 (P4) |
| F1.9 | reshuffle_seed | a fixed integer | any integer | Base seed; each row's reshuffles are seeded from it and the row's key, so a judged date gives the same p-values on every run and a p-value never depends on the order checks run in | 6 | Owner, 2026-10-11 (every number in config; P4) |
| F1.10 | multi_tenant_hosts | substack.com, medium.com, github.com | host names | Hosts whose first path segment names its own site | 2 | Blueprint section 3; owner, 2026-10-10 (R7) |
| F1.11 | page_types | news.mongabay.com: short_article = /short-article/, video = /video/ | per host, path prefixes | Path prefixes that name a page type inside one site; any other address is type other | 2 | Owner, 2026-10-10 (R5) |
| F1.12 | false_discovery_rate | 0.05 | 0.001 to 0.2 | Target share of false crossings among the checks that cross, averaged over judged dates | 8 | Blueprint section 5 |

Table F2 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| F2.1 | One settings file per judge under config/judges/, loaded only by that judge, so its numbers never enter the import closure of every module that reads config/idhazh.json | Owner, 2026-10-11 (P6) |
| F2.2 | Every field declares its allowed range, and an autotune loop may move a field only within it; reshuffle_seed is a fact, and no loop moves it, because a loop would keep the seed with the fewest crossings | Owner, 2026-10-11 (every number in config, ready for autotune); Fowler (reviewed 2026-10-11) |
| F2.3 | A site stays the host without www.; no public suffix lookup, because registered-domain grouping is rejected (F3.3) | Owner, 2026-10-10 (R7) |
| F2.4 | Page types group articles inside one site; they are never separate sites | Owner, 2026-10-10 (R5) |
| F2.5 | A site key is a lower-case host, optionally a slash and one path segment, with no space or backtick, and it is printed inside a code span wherever text reaches a page, so an address such as medium.com/@name never notifies a GitHub user | Owner, 2026-10-10 (R7); Fowler (reviewed 2026-10-11) |

Table F3 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| F3.1 | A block in config/idhazh.json, as the content-similarity judge's settings are | AppConfig is in the council's import closure, so the block would be a fourth judge contract crossing it, which llm-council.md says cannot grow (C9) | One block in AppConfig and its changelog entry | Owner, 2026-10-11 (P6) |
| F3.2 | Constants in the check modules | Guardrail #6 refuses a hard-coded threshold, and autotune cannot move a constant | One edit per module; every tuning needs a code change and a review | CLAUDE.md Guardrail #6 |
| F3.3 | Group by registered domain from the public suffix list, as the blueprint writes | Merges news.mongabay.com with india.mongabay.com, a second #1270-type mix; the seven author.substack.com feeds merge unless the list carries substack.com | courlan is already installed; the cost is the merged series | Owner, 2026-10-10 (R7) |
| F3.4 | Page types as separate sites | The #1270 week would compare nothing: 10 full and 11 Short recent articles, both under min_articles | Smaller series per site and more untested checks | Owner, 2026-10-10 (R5) |

### Row #3 - The judge's ledger and its tenant module

- **Scope:** the contract SummaryFidelityWindowCheck (Tables H1 to H3) and the ledger window-checks in the family summary-fidelity-judge are registered and enrolled for compaction and retention as ledger-registry.md requires of a new ledger, and backend/idhazh/summary_fidelity/tenant.py presents the seven members of the council's tenancy protocol and files the rows it is handed through ledger.persist in settle; the slug is not yet in council.tenants, so no night runs it.
- **Level:** 5 (a persisted contract and a new ledger). ESCALATE C1 fires: the owner rules on P1 before work starts.
- **Files touched:**
  - backend/idhazh/contracts/summary_fidelity_window_check.py (new: SummaryFidelityWindowCheck, WindowCheck, CheckOutcome, Direction, and the judge's slug as a closed set beside its column)
  - backend/idhazh/contracts/__init__.py (CONTRACTS, entered the way content_similarity_judge_metrics is; re-derive at dispatch)
  - backend/idhazh/contracts/ledger_name.py (SUMMARY_FIDELITY_JUDGE_WINDOW_CHECKS = "window-checks")
  - config/ledgers.json (family summary-fidelity-judge: status active, one-line description, onboarded day; entry grain raw-and-compact, prefix ["summary-fidelity-judge", "window-checks"])
  - backend/idhazh/ledger/keys.py (_JUDGE_DOOR_SHAPES: the key in H4.5 and the row contract, imported on first use; no preference)
  - backend/idhazh/ledger/staging.py (REGISTRY: written by the judge's settle in the council's save job, no digest.yml commit label)
  - frontend/src/lib/data/slice-shapes.ts (LEDGER_NAMES gains window-checks; LEDGER_FOLDERS gains summary-fidelity-judge)
  - config/gardener/compact-summary-fidelity-judge-window-checks.json (new: kind compaction, owns state/raw/summary-fidelity-judge/window-checks and state/compact/summary-fidelity-judge/window-checks, the approved retention chain of H4.4, the other fields copied from compact-council-run-records.json)
  - config/idhazh_gardener.json (task_names gains compact-summary-fidelity-judge-window-checks)
  - backend/tests/contracts/test_gardener_config.py (RETENTION_LEDGERS gains window-checks)
  - backend/tests/contracts/_fixtures.py (FIXTURE_FILES) and one summary-fidelity-window-check fixture in the contract fixtures folder it names
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

Table H1 - check names (WindowCheck; declared once here)

| # | Value | What it compares | Direction tested | Row |
| --- | --- | --- | --- | --- |
| H1.1 | article_count | Distinct addresses per site in the item-health census, recent window against the baseline's daily rate | fewer | 4 |
| H1.2 | window_rows | Rows in each whole window across all sites; one row per judged date | none | 4 |
| H1.3 | unusually_short | Share of a site's recent articles shorter than the baseline's short_tail_percentile (F1.5) length, within page type | more | 5 |
| H1.4 | article_length | Wasserstein-1 distance between baseline and recent log word counts within each page type, averaged with weights n_b x n_r / (n_b + n_r), reshuffled within type | either | 6 |
| H1.5 | page_furniture | Share of distinct articles flagged extraction_suspect ("The text looks like page furniture", eval_row.py), within page type; was scoring_chrome | more | 6 |
| H1.6 | page_mix | Share of each declared page type (F1.11); stored, never tested | none | 6 |
| H1.7 | copied_phrase_share | Wasserstein-1 distance of extractiveness (the share of the summary's 4-word phrases found verbatim in the source), per model-and-scorer pair, within page type as H1.4 | either | 7 |
| H1.8 | faithfulness | Wasserstein-1 distance of hhem, per model-and-scorer pair, within page type as H1.4 | either | 7 |

Table H2 - outcomes (CheckOutcome; declared once here)

| # | Value | Meaning |
| --- | --- | --- |
| H2.1 | threshold_crossed | Tested; q_value at or under false_discovery_rate (row #8). A signal for a person to inspect, not a diagnosis |
| H2.2 | threshold_not_crossed | Tested; q_value above false_discovery_rate. Not evidence that nothing changed |
| H2.3 | too_few_articles | Not tested: under min_articles (F1.3) on a side, or a window_rows row under min_window_rows (F1.4) |
| H2.4 | earlier_model_baseline | A model-and-scorer pair with fewer than min_articles baseline articles, compared with earlier pairs on the site; stored with its p-value, never enters the false-discovery step (R4) |
| H2.5 | not_tested | A page_mix row, or a window_rows row at or above min_window_rows: a count or share, never tested |

Table H3 - SummaryFidelityWindowCheck, one row per check per judged date per council run (schema stem summary-fidelity-window-check)

| # | Field | Type | Meaning |
| --- | --- | --- | --- |
| H3.1 | run_id | RunId | The council run that judged the date (the judge-ledger rule in ledger-registry.md) |
| H3.2 | judge_id | the judge's slug, a closed set of one | Which judge wrote the row |
| H3.3 | date | DateStamp | The judged date; the recent window ends on it, and it decides the file the row is filed under |
| H3.4 | checked_at | Timestamp | When the unit computed the row |
| H3.5 | rules_version | str | The judge's rules version in force |
| H3.6 | recent_days, baseline_days | int | The window lengths in days the unit used |
| H3.7 | site | a site key (F2.5) or null | Null on window_rows rows |
| H3.8 | page_type | str or null | Set on page_mix rows only |
| H3.9 | check_name | WindowCheck (H1) | Which comparison; not "check", which is a reserved word in the console's query engine |
| H3.10 | model_id, scorer_version | str or null | Set on copied_phrase_share and faithfulness rows only |
| H3.11 | baseline_count, recent_count | int | Articles, census addresses or window rows on each side |
| H3.12 | baseline_value, recent_value | float or null | Each side's summary: median words (article_length), median score (copied_phrase_share, faithfulness), share of articles (unusually_short, page_furniture, page_mix), addresses a day (article_count) |
| H3.13 | effect | float or null | Distance checks: the distance minus the median distance of its reshuffles (log words or score points). article_count: recent count over its no-change expectation, minus one. Share checks: recent share minus its no-change share (j / (N_b + 1) for unusually_short), in percentage points |
| H3.14 | direction | Direction: fewer, more, shorter, longer, higher, lower or none | Which way the tested comparison moved, within page type where the test is |
| H3.15 | p_value | float or null | Null when not tested |
| H3.16 | q_value | float or null | The smallest false_discovery_rate at which this check would cross in its family, the (run_id, date) pair: the Benjamini-Hochberg adjusted p-value. It depends on every other check of the same run and date that enters the false-discovery step, so an outcome is not a property of one check alone. Null outside the step, earlier_model_baseline included. Rank or re-threshold only rows of one run_id, the date's latest |
| H3.17 | false_discovery_rate, min_articles, short_tail_percentile | float, int, float | F1.12, F1.3 and F1.5 in force, so a later reader needs no git history |
| H3.18 | reshuffles | int or null | Reshuffles used, on permutation checks |
| H3.19 | outcome | CheckOutcome (H2) | What the check concluded |

Table H4 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| H4.1 | The ledger is window-checks in the family summary-fidelity-judge: rows land in state/raw/summary-fidelity-judge/window-checks/YYYY/MM/DD/ as parquet, and the gardener packs them into state/compact/summary-fidelity-judge/window-checks/ (daily, monthly and yearly files with their index files); the family leaves room for the judge's later ledgers (rows #10, #11) | Owner, 2026-10-11 (P1) |
| H4.2 | Every file name is minted by the ledger door (a version 8 UUID per writer and attempt); no writer names a file | backend/idhazh/ledger/persist.py |
| H4.3 | Every check of every judged date is stored, untested ones included, so a skipped check is visible; a date whose whole window is under min_window_rows stores its one window_rows row instead | Owner, 2026-10-10 (store every check); blueprint section 2 ("eliminating the silent skip") |
| H4.4 | Retention follows the owner-approved live chain in ledger-registry.md, held by test_every_ledger_uses_the_approved_live_retention_chain | ledger-registry.md |
| H4.5 | Key: run_id, date, site, check_name, page_type, model_id, scorer_version, with no preference, so packing keeps every council run of a date; a retry of one run settles to its highest attempt through the door; a reader of one judged date takes the run with the latest checked_at | Owner, 2026-10-11 (P1); ledger-registry.md, the rule a judge ledger follows; Fowler (reviewed 2026-10-11) |
| H4.6 | The row declares none of the door's names (ledger, covers, attempt, job, shard, unit_id) and run_id only as the council run; the writer identity is the council's, job save_council_results | ledger-registry.md, the rule a judge ledger follows |
| H4.7 | One unit a night (shard_count 1): run_shard computes every check's row into a scratch file in the tenant's own slot under backend/var/council/, reports no model calls, writes that file once, after its last check, or leaves none and returns stopped_on_deadline, so settle files a whole date or nothing, and settle applies row #8's step and files the rows, naming its own producer; the tenant declares no refusal of a night, because its work has no cost worth weighing against the council's clock | Owner, 2026-10-11 (P8); backend/idhazh/council/tenancy.py |
| H4.8 | Check names state what is measured and the outcome states whether the threshold was crossed, so a stored row never claims a movement its own outcome denies | Owner, 2026-10-10 (rename request); replaces the alert names of R8; outcome names debated by Fowler and Andre, 2026-10-11 |
| H4.9 | Readers count a stretch, not a night: a stretch is consecutive run days on which one key crosses, and a day with no run does not end one, because one real change stays in the recent window for seven nights | Owner, 2026-10-11 (P11) |

Table H5 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| H5.1 | state/raw/summary-quality-evals/drift/ | The registry refuses a door ledger inside another door ledger's folder, because a walk of the outer ledger's raw days would read the inner one's files (backend/idhazh/contracts/ledgers.py); a fixed file name such as ledger.parquet is also refused, because a raw file is immutable once written | A change to the registry rule, or renaming the eval ledger and moving its committed raw and compact files into a nested folder; either is Level 5 | backend/idhazh/contracts/ledgers.py |
| H5.2 | JSON files under state/summary-fidelity-judge/, as two of the content-similarity judge's ledgers still are | The owner wants parquet under state/raw/ with the ledger enrolment; the flat and stamped grains are the ones the registry calls transitional | None | Owner, 2026-10-11 |
| H5.3 | A ledger that is its own family, at state/raw/summary-fidelity-judge/ | No door ledger may sit inside another, so rows #10 and #11 could never add a ledger beside it | A second family later | Owner, 2026-10-11 (P1) |
| H5.4 | Store only crossed checks | A reader cannot tell "checked, threshold not crossed" from "never checked" | Fewer rows a night; row #8's replay measures how many | Owner, 2026-10-10 (store every check) |
| H5.5 | Compute the checks in settle | settle runs inside the collecting job's 30-minute bound for every tenant and date, and a job killed there commits nothing for any tenant | None; the unit's model-server start is spent either way | Owner, 2026-10-11 (P8) |
| H5.6 | A preference that keeps one run per date | Packing would delete the earlier run's rows, against "every check stored", and could mix two runs' false-discovery sets in one day | None | Fowler (reviewed 2026-10-11) |

### Row #4 - Article-count check from the item-health census

- **Scope:** per site, the check counts distinct addresses in the item-health census (never sampled) over the recent window, compares them with the baseline's daily rate through a negative-binomial lower-tail p-value whose spread comes from the baseline's daily counts, and returns one article_count row; a crossing skips none of the site's other checks and its row text names feed-health first; the unit also stores one window_rows row per judged date.
- **Level:** 3 (it reverses the old rule that a stopped site is feed quarantine's job).
- **Files touched:**
  - backend/idhazh/summary_fidelity/windows.py (new: the eval ledger and the item-health census read through ledger.load_days)
  - backend/idhazh/summary_fidelity/article_count.py (new)
  - backend/idhazh/summary_fidelity/tenant.py (run_shard calls the check)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (recent_days, baseline_days, min_articles, min_window_rows)
  - backend/tests/summary_fidelity/test_article_count.py (new)
  - pyproject.toml (scipy in an optional extra; P7)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** a fixture site whose 28 baseline days alternate 1 and 7 addresses gets a p-value under 0.001 at 5 recent addresses and over 0.3 at 26; the expected values are computed in the test from scipy.stats.nbinom, never copied. Cannot settle: holiday weeks, which whole-week windows do not remove.

Table I1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| I1.1 | The count comes from the item-health census, because the eval ledger counts what the pipeline selected and scored | Owner, 2026-10-10 (R3) |
| I1.2 | Negative-binomial tail with spread from the baseline's daily counts; the rate uses the days the unit actually read, never the settings | Owner, 2026-10-10 (R3) |
| I1.3 | No article floor for this check: a site with any baseline address is tested | Blueprint section 2 |
| I1.4 | A daily variance under the daily mean is raised to the mean, and the variance also carries the baseline's own noise | Owner, 2026-10-11 (P3) |
| I1.5 | A judged date whose whole window is thin stores one window_rows row and no check, so a stopped instrument never reads as a quiet week | drift.py (min_window_rows) |

Table I2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| I2.1 | The Poisson z-score as the blueprint writes it | Fires on 0.04 to 1.49 percent of unchanged sites against 0.135 percent nominal (simulation, 2026-10-10) | One line of arithmetic | Owner, 2026-10-10 (R3) |
| I2.2 | Count scored rows in the eval ledger | Selection limits and run sampling move the count with no change at the source | None | Owner, 2026-10-10 (R3) |

### Row #5 - Unusually-short check

- **Scope:** per site and within each declared page type, the check counts recent articles with strictly fewer words than the baseline's short_tail_percentile (F1.5) length, takes the exact beta-binomial tail as its p-value, adding each page type's exact tail, and returns one unusually_short row; a type with no baseline article has no cut and its recent articles are left out.
- **Level:** 2.
- **Files touched:**
  - backend/idhazh/summary_fidelity/unusually_short.py (new)
  - backend/idhazh/summary_fidelity/tenant.py
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (short_tail_percentile)
  - backend/tests/summary_fidelity/test_unusually_short.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** on a seeded sweep with no change, the share of p-values at or under 0.05 stays at or under 0.05 within the sweep's sampling error; on a 102-article baseline, 8 of 40 recent articles under the cut gets a p-value under 0.01 and 3 of 40 one over 0.2 (the exact tail gives about 0.004 and 0.31). Cannot settle: truncation that leaves an article above 60 words but inside the baseline's normal range.

Table J1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| J1.1 | The p-value is the exact beta-binomial tail, the exact form of the reshuffling R2 approved, because the cut is itself estimated from the baseline; a recent article counts when it has strictly fewer words than the cut | Owner, 2026-10-10 (R2); owner, 2026-10-11 (P2) |

Table J2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| J2.1 | Binomial(N_recent, 0.05) as the blueprint writes it | Treats the estimated cut as known; fires on 0.73 to 4.83 percent of unchanged samples against 0.5 percent nominal at baselines of 20 to 102 (exact, 2026-10-11) | One line of arithmetic | Owner, 2026-10-10 (R2) |

### Row #6 - Article-length and page-furniture checks

- **Scope:** per site, the article_length check computes the Wasserstein-1 distance of log word counts within each page type, weighted as H1.4, with a permutation p-value whose reshuffles stay within page type; the page_furniture check compares the share of distinct articles flagged extraction_suspect with Fisher's exact test summed over page types; each declared page type's share is stored as a page_mix row.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity/article_length.py (new)
  - backend/idhazh/summary_fidelity/page_furniture.py (new)
  - backend/idhazh/summary_fidelity/reshuffle.py (new: the early-stopping reshuffle and its automatic cap, seeded per row key)
  - backend/idhazh/summary_fidelity/tenant.py
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (reshuffle_stop_hits, reshuffle_cap_floor, reshuffle_cap_multiple, reshuffle_seed)
  - backend/tests/summary_fidelity/test_article_length.py (new)
  - backend/tests/summary_fidelity/test_page_furniture.py (new)
  - backend/tests/summary_fidelity/fixtures/issue_1270_window.json (new: news.mongabay.com, 102 baseline and 21 recent lengths with page types, copied from the committed eval ledger)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** the #1270 fixture's article_length check gets a p-value over 0.05 (C6), and the same fixture with half its full articles cut to 300 to 500 words gets one under 0.01. Cannot settle: the false-crossing rate on live data; row #8's replay measures it.

Table K1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| K1.1 | Wasserstein-1, two-sided: a shorter extraction can be a better one | Owner (blueprint section 1); Andre (reviewed 2026-10-10: keep) |
| K1.2 | Log word counts, so a cut is measured as a share of the text; the row still stores medians in words | Owner, 2026-10-10 (R14) |
| K1.3 | Reshuffles stay within page type, so the p-value asks whether one type got shorter and a change in mix alone does not cross | Owner, 2026-10-10 (R5) |
| K1.4 | page_furniture replaces scoring_chrome and reads extraction_suspect, with an exact p-value | Owner, 2026-10-10 (R15; renamed by the rename request) |
| K1.5 | The distance and the furniture share are taken within each page type, so a mix that moves toward the shortened type cannot hide a real cut, and one distinct article counts once | Owner, 2026-10-11 (P11) |

Table K2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| K2.1 | The standard-error band W1 > 2.5 x sqrt(var_b / N_b + var_r / N_r) | Wasserstein-1 is never smaller than the difference in means, so the band fires on 1.0 to 3.6 percent of unchanged comparisons and gives no p-value | None | Owner, 2026-10-10 (R2) |
| K2.2 | Kolmogorov-Smirnov or energy distance | The blueprint names Wasserstein-1; the gap table lists the others as equals | A second statistic and its own reshuffling | Owner (blueprint section 1) |

### Row #7 - Copied-phrase and faithfulness checks per model

- **Scope:** per site and model-and-scorer pair with min_articles (F1.3) on each side, the copied_phrase_share and faithfulness checks compute the Wasserstein-1 distance of extractiveness and hhem within page type as H1.4, with a permutation p-value; a pair with fewer than min_articles baseline articles is compared with all earlier pairs on that site and stored as earlier_model_baseline.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity/scores.py (new)
  - backend/idhazh/summary_fidelity/tenant.py
  - backend/tests/summary_fidelity/test_scores.py (new)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite.
- **Oracle:** extractiveness moving from 0.15 to 0.55 gets a p-value under 0.001; a new pair with 25 recent rows and none in the baseline is stored as earlier_model_baseline with a p-value and no q_value. Cannot settle: score movement that a library upgrade causes under one scorer_version (row #10).

Table L1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| L1.1 | Wasserstein-1 with a permutation p-value for hhem and extractiveness | Owner, 2026-10-10 (R2) |
| L1.2 | A deliberate model or scorer change is never a crossing: the comparison with earlier pairs is stored and stays outside row #8 | Owner, 2026-10-10 (R4) |
| L1.3 | A pair with 1 to 19 baseline articles is compared with earlier pairs too, so no pair falls into the gap L2.2 rejects | Owner, 2026-10-11 (P11) |

Table L2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| L2.1 | PSI for bounded scores | Exceeds 0.25 on 92 percent of unchanged samples of 102 against 21 | None | Owner, 2026-10-10 (R2) |
| L2.2 | Skip a new pair until it has its own baseline | Loses the comparison a person wants after a model change | 7 + 20 / (articles a day) days with no score check; at most 14 for any site a 7-day window can test | Owner, 2026-10-10 (R4) |

### Row #8 - One false-discovery step per judged date, and the replay

- **Scope:** settle collects the p-value of every tested check of a judged date, with no earlier cut-off, applies the Benjamini-Hochberg step-up at false_discovery_rate (F1.12), stores each row's q_value and outcome, and a replay utility runs the unit over past dates with its own test.
- **Level:** 3.
- **Files touched:**
  - backend/idhazh/summary_fidelity/false_discovery.py (new)
  - backend/idhazh/summary_fidelity/tenant.py (settle applies the step before filing)
  - backend/idhazh/contracts/knobs/summary_fidelity_judge.py and config/judges/summary-fidelity-judge.json (false_discovery_rate)
  - backend/utilities/summary_fidelity_replay.py (new; operator utility)
  - backend/tests/summary_fidelity/test_false_discovery.py (new)
  - backend/tests/summary_fidelity/test_replay.py (new: a tmp_path ledger with two judged dates, read through ledger.load_days)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/summary_fidelity/; CI - full suite. Observation, not a gate: the replay over every judged date of the last 35 days, the same dates with each article's window label reshuffled once per site and shared by all that site's checks, and the same dates with half of one site's full articles cut to its short-form length, recorded in the pull request as crossings per date, stretches (H4.9), repeats and injected cuts found, with false crossings counted per stretch and over non-overlapping weeks, and article_count reported on its own.
- **Oracle:** for the textbook input of ten p-values the step keeps exactly the step-up set and stores the matching adjusted values; a date with no tested check still files every row, with no q_value. Cannot settle: crossings that are real but too small to matter; the stored effect lets a reader rank them.

Table M1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| M1.1 | Every check with a p-value hands the step one row; the step is the only threshold, and no check is cut before it by its p-value | Owner, 2026-10-10 (R2) |
| M1.2 | One judged date within one council run, the (run_id, date) pair, is one family for the step; two runs of a date are two families, and a repair date judged on the same night is a family of its own | Owner, 2026-10-11 (P1); Fowler and Andre (reviewed 2026-10-11) |
| M1.3 | The replay reads through ledger.load_days, one judged date at a time (Guardrail #12) | Fowler (reviewed 2026-10-10: keep) |
| M1.4 | Reshuffling stops early and its cap follows the number of checks | Owner, 2026-10-11 (P4) |

Table M2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| M2.1 | Bonferroni | A person reading a short list needs the false share bounded, not the chance of any false crossing | Fewer crossings at the same error target | Andre (reviewed 2026-10-10: keep) |
| M2.2 | DuckDB over state/compact/ as the blueprint writes | Days not yet compacted exist only as raw files, so every site's recent count would read as a collapse; re-runs count twice; Guardrail #12 forbids the glob | None | Owner, 2026-10-10 (R1) |

### Row #9 - The switch: the judge joins the council

- **Scope:** summary-fidelity-judge joins council.tenants in config/idhazh.json, and the council's planning, judging and collecting jobs install the extra that carries scipy, so the next nightly run judges yesterday and files its rows.
- **Level:** 3 (starts a nightly committed write).
- **Files touched:**
  - config/idhazh.json (council.tenants gains summary-fidelity-judge)
  - .github/workflows/llm-council.yml (the planning, judging and collecting jobs install the extra; P7)
  - The workflow test that reads llm-council.yml's install step (re-derive at dispatch), asserting all three jobs install the extra
  - backend/tests/council/ (re-derive at dispatch: tests that enumerate council.tenants)
  - docs/architecture/publishing/llm-council.md (the tenant list names two judges)
  - docs/architecture/publishing/summary-fidelity-judge.md
- **Acceptance gates:** local - ruff, mypy and the shared test selector over backend/tests/council/ and backend/tests/summary_fidelity/; CI - full suite. Observation, not a gate: the first scheduled night, read for rows stored, crossed checks, and the unit's run time and peak memory beside the model server (a unit that does not fit stops the row, C2); when it stores nothing, read the collecting job's log first.
- **Oracle:** a council night driven end to end with both tenants registered fans out one cell for this judge per date, and the collecting job commits its raw file under state/raw/summary-fidelity-judge/window-checks/ beside the other judge's files. Cannot settle: the first live night's run time against the council's clock.

Table N1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| N1.1 | Registration in council.tenants is the switch; no separate flag | llm-council.md ("That one line decides whether a night judges anything at all") |
| N1.2 | The council's nightly schedule replaces the daily schedule the drift plan asked for; this judge names no repair date (B8) | Owner, 2026-10-10 (R6); Fowler (reviewed 2026-10-11) |
| N1.3 | A person judges a past date by dispatching the council workflow with that date | llm-council.md ("A dispatched date replaces the plan outright") |

Table N2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| N2.1 | A workflow of the judge's own | The council already provides the schedule, the repair window, one commit path and the writer identity | A second scheduler, commit path and identity to keep correct | Owner, 2026-10-11 (run it as a council judge) |

### Row #10 - Scorer reference check

- **Scope:** a fixed set of real committed article-summary pairs with recorded faithfulness scores is re-scored on every scored run by the job that already loads the scorer, and the judge stores a crossing when any score differs from its record beyond floating-point noise, naming the installed transformers and torch versions.
- **Level:** 5 (a committed reference file and dated benchmark rows). ESCALATE C1 fires before work starts.
- **Files touched:** set by the owner's ruling on the shape (C1); at least the reference set file, the job that loads the scorer, a ledger in the summary-fidelity-judge family, a WindowCheck value added with that ruling, backend/tests/summary_fidelity/test_reference_scores.py (new) and docs/architecture/publishing/summary-fidelity-judge.md.
- **Acceptance gates:** set with the shape.
- **Oracle:** re-scoring the set on an unchanged scorer reproduces every recorded score, and a deliberately changed score file crosses. Cannot settle: scorer change on content the set does not cover.

Table O1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| O1.1 | The scorer job re-scores; the judge reads the dated rows through ledger.load_days | Owner, 2026-10-10 (R12) |
| O1.3 | Any difference from the record is a library change, so this check has no p-value and stays outside row #8's step | Owner, 2026-10-11 (P11) |
| O1.2 | One dated benchmark-row contract serves rows #10 and #11; its shape and the set's location | Owner ruling pending (C1) |

Table O2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| O2.1 | Re-score in the judge's unit | The unit would load HHEM every night for a set that changes only when a library changes | The faithfulness extra and the scorer's load every night; Carmack prices it | Owner, 2026-10-10 (R12) |
| O2.2 | A tolerance band | HHEM is pinned and deterministic, so any difference is a library change, which a band would hide | None | Owner, 2026-10-10 (R12) |

### Row #11 - Golden-set check

- **Scope:** the current summarizer runs on the qualification golden set inside the qualification job whenever the model file hash, runtime build, prompt or scorer version changes, and weekly otherwise, scored by HHEM and the deterministic counterweights; the judge stores a crossing on a shift against the earlier dated rows.
- **Level:** 5 (dated benchmark rows and model inference on the runner). ESCALATE C1 and C2 fire before work starts.
- **Files touched:** set by the owner's ruling on the shape (C1), including a WindowCheck value added with that ruling.
- **Acceptance gates:** set with the shape.
- **Oracle:** a replay of the golden set against a deliberately degraded model output crosses (docs/concepts/evaluation.md, "a drift detector that has never fired has not been shown to work"). Cannot settle: drift on content the golden set does not hold.

Table Q1 - decisions

| # | Decision | Authority |
| --- | --- | --- |
| Q1.1 | The qualification job runs the set; the judge reads its dated rows | Owner, 2026-10-10 (R12) |
| Q1.2 | The golden set, its refresh schedule and the benchmark-row contract | Owner ruling pending (C1) |

Table Q2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| Q2.1 | A nightly re-run of an unchanged set | A pinned, deterministic pipeline on unchanged inputs reproduces itself | Runner minutes every night; Carmack prices them | Owner, 2026-10-10 (R12) |
| Q2.2 | A model judge | A judge that shares the summarizer's failure modes measures nothing | A judge model, its prompt and its own calibration | Andre (reviewed 2026-10-10) |

### Row #12 - The stored checks on a console page

- **Scope:** window-checks joins ledger.published so the console's Data explorer can query its compact files, and one panel on the console's Model page (P5) lists the newest council run's crossed checks by site with effect and q_value, drawing consecutive nightly crossings of one check as one stretch.
- **Level:** 3.
- **Files touched:**
  - config/idhazh.json (ledger.published gains window-checks)
  - frontend/src/routes/console/model/+page.server.ts and frontend/src/routes/console/model/+page.svelte (the Model route, which the console's settings call the Summaries route)
  - frontend/src/lib/server/ledger-rows.ts (a build-time reader of the window-checks compact files, beside evalRows and itemHealthRows)
  - backend/tests/contracts/test_frontend_vocabularies.py and backend/tests/contracts/test_frontend_field_set.py (the hand copy of H1, H2 and the fields the panel reads)
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

Table T2 - rejected alternatives

| # | Option | Why rejected | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| T2.1 | A page of its own | The owner ranked the view second to the stored record | A route, its navigation entry and its own tests | Owner, 2026-10-10 |

## 3. Owner rulings

Table P - rulings the owner made on 2026-10-11

| # | Question | Ruling | Evidence | Rows |
| --- | --- | --- | --- | --- |
| P1 | Sign off the judge's ledger: family summary-fidelity-judge, ledger window-checks, its path (H4.1), the row shape (H1 to H3) with the reviewers' changes to it (copied_phrase_share; threshold_crossed and threshold_not_crossed; check_name; baseline_value and recent_value; the effect definition; q_value per (run_id, date); the settings in force on every row), the key with the council run and the reader's rule (H4.5), and one (run_id, date) pair as one false-discovery family (M1.2) | Approved | ledger-registry.md lists what a new ledger owes and the rule a judge ledger follows; row #3 makes every edit in one change. The changes fix a field name the console's query engine reserves, a medians field that also held shares and rates, an effect that divided by zero and ranked small sites first, and outcome names that read as "nothing moved" (Fowler and Andre, 2026-10-11) | 3 and every later row |
| P2 | Unusually-short check: the exact beta-binomial tail instead of reshuffling, counting recent articles with strictly fewer words than the cut, with page types combined by adding each type's exact tail; a type with no baseline article has no cut and its recent articles are left out | Approved | When the cut is the j-th shortest of N_b baseline articles, the count below it follows BetaBinomial(N_recent, j, N_b - j + 1) with no change; this is the exact form of the reshuffling already approved (checked against every reshuffle of a small case, to 2e-16). With no change it fires on 0.17 to 0.44 percent at 0.5 percent and 2.45 to 4.83 percent at 5 percent (exact, baselines 20 to 102, recent 21 and 40); counting ties as short would fire 0.60 to 2.44 percent at 0.5 percent | 5 |
| P3 | Article-count check: raise a daily variance under the daily mean to the mean, and add the baseline's own noise to the variance (x (1 + recent_days / baseline_days)) | Approved | The negative binomial is undefined when the daily variance is under the mean, which happened in 54 percent of Poisson samples. The baseline rate is itself estimated: with the term, false rates were 0.0055 to 0.21 percent at 0.135 percent nominal (200,000 repeats; 1.5, 4 and 10 a day; Poisson, spread twice the mean, and quiet weekends). Over-dispersed sites still fire up to 3 times nominal at 0.0001, so row #8's replay reports article_count on its own | 4 |
| P4 | Reshuffling: stop once 10 reshuffles give a distance at least as large as the observed one (a tie counts); cap at the larger of 100,000 and 10 x (tested checks in the run) / false_discovery_rate - 1, counted before any reshuffle; seed each row's reshuffles from reshuffle_seed and its key; every one of these numbers in the settings file | Approved | The smallest p-value 9,999 reshuffles can give is 0.0001, which equals the first threshold at 500 checks (0.05 / 500), so from 500 checks a lone crossing becomes impossible. With early stopping an unchanged check used about 101 reshuffles instead of 9,999, and the p-values stayed valid over 1,000,000 checks. Not counting ties fired 5.8 percent at 5 percent nominal on tie-heavy scores; counting them fired 4.0 percent | 5, 6, 7, 8 |
| P5 | Which console page carries the panel (Model or Judgement), and whether the window-checks compact files are published on the site | Approved: Model page; publish | The Model page already reads the score and item-health ledgers and lists the sources the checker doubts; the Judgement page reads the similarity judge's merge line, which no check here touches; the Data explorer reads only ledgers in ledger.published | 12 |
| P6 | Where the judge's numbers live: config/judges/summary-fidelity-judge.json, read only by the judge | Approved | Every number bounded in one file an autotune loop can move. A block in config/idhazh.json would put a fourth judge contract in the council's import closure, because the council's registry imports AppConfig, and llm-council.md says that list cannot grow. The house already keeps one file per gardener task (config/gardener/), per console page (config/console/) and per model (config/models/) | 2 and every later row |
| P7 | scipy: an optional extra named for what it carries (statistics), installed by the council's planning, judging and collecting jobs | Approved | The planning job imports every registered tenant module to resolve its slug, and the collecting job runs settle; both install only pip install -e . today, so a scipy import reached from the tenant module would fail every judge's night. CI installs the dev extra, so the tests would stay green. R11 named the drift job, which row #1 deletes | 4, 9 |
| P8 | Build the judge in the council from the first row, with one unit a night computing and settle filing (H4.7), and no stage in drift.yml that later moves | Approved | Nothing is built yet, so there is nothing to migrate; CLAUDE.md section 14 asks for each increment in its intended code path; the council already gives a nightly schedule, one commit path and a writer identity. A shard_count of 0 would break the council's own record, so the judge pays one model-server start a night | 1, 3 and every later row |
| P9 | Drop urgent and urgent_p_value, which R9 kept | Approved | Their only reader, the issue title, went with the issues; a p-value says how unlikely a drop is by chance, not how much it matters, so "urgent" claims a priority nothing measured (CLAUDE.md section 0b); the stored q_value and effect already rank a crossing | 3, 8 |
| P10 | Repair dates: this judge names none in its first version (B8), and a council plan of its own fans out each tenant's own repair dates before a third judge arrives | Approved | A council date runs every tenant, so a date only this judge named would make the content-similarity judge re-judge a night it already counted, at model cost. The cost of naming none: a night only this judge missed stays missing, and the next window shares six of its seven days (Fowler, 2026-10-11) | 3 |
| P11 | The reviewers' fixes to the checks: distances and the furniture share within page type (K1.5); a pair with 1 to 19 baseline articles compared with earlier pairs (L1.3); the scorer reference check outside the false-discovery step (O1.3); readers count stretches (H4.9); the replay reshuffles each article's label once per site | Approved | With full articles cut by a quarter and the mix moving toward them, the pooled distance flagged 0 percent and the per-type distance 61 percent; pooled Fisher fired 9.6 percent at 5 percent nominal when the mix moved with no change; a pair with 1 to 19 baseline articles fell into the gap R4 closed; overlapping windows do not raise the false rate per night, they group crossings into stretches (Andre, 2026-10-11) | 6, 7, 8, 10 |
| P12 | Two optional refinements: leave out of the step a check whose smallest reachable p-value is above false_discovery_rate; and count articles item-health rejected as too short as below the cut | Deferred to row #8's replay | Neither was measured here; the second needs item-health to record a too-short rejection per address, which is not checked | 5, 8 |

Table R - the review changes the owner approved on 2026-10-10, and where each lands now

| # | Change | Lands in rows | Note |
| --- | --- | --- | --- |
| R1 | Read through ledger.load_days, never DuckDB over state/compact/; duckdb banned outside tests | 3, 8 | Applied |
| R2 | Every check returns a p-value; the false-discovery step is the only threshold | 5, 6, 7, 8 | Applied; P2 and P4 refine it |
| R3 | Article count from the item-health census, negative-binomial tail, no skip of other checks, feed-health named first | 4 | Applied; P3 refines it |
| R4 | A new model pair's comparison with earlier pairs is stored, never a crossing | 7 | Applied as the earlier_model_baseline outcome (H2.4) |
| R5 | Page types per host; reshuffles within type; the mix stored as a note; the #1270 fixture a gate (C6) | 2, 5, 6 | Applied; the note is the page_mix row (H1.6) |
| R6 | Daily runs that never repeat one notice; fixed text; trigger C7 | 9 | Superseded: no issues exist, the council runs nightly, and its fixed commit message keeps C7 satisfied |
| R7 | A site stays the host; multi_tenant_hosts applies to listed hosts only; site keys in code spans | 2 | Applied |
| R8 | Alert names that state a measurement | 3 | Replaced by the rename request: check names (H1) plus outcomes (H2) |
| R9 | Urgent marking for a count crossing with p under 0.001; no label | 8 | Withdrawn by P9 on 2026-10-11: its only reader, the issue title, went with the issues |
| R10 | A flag for the new path; the old rules and settings leave together | 1, 9 | Superseded: row #1 deletes the old review outright, and registration in council.tenants is the switch |
| R11 | scipy in an optional extra installed only by the job that runs the checks | 4, 9 | Adapted to the council's judging job (P7) |
| R12 | Scorer reference and golden set in the jobs that already load their models; one benchmark-row contract | 10, 11 | Applied; their ledgers join the summary-fidelity-judge family |
| R13 | The replay covers past dates, reshuffled labels and injected cuts, with its own test | 8 | Applied |
| R14 | Log word counts for the length check | 6 | Applied |
| R15 | The furniture check reads extraction_suspect with an exact p-value | 6 | Applied; named page_furniture by the rename request |
| R16 | Plan text: complete Files touched lists, the measured #1270 cause in A1, a Status line | all | Applied; its schemas/app-config.schema.json item was dropped, because the generated schema folder was deleted on 2026-09-23 (backend/tests/contracts/test_no_generated_layer.py) and a new contract now owes a fixture instead |

Table S - checked and kept as written

| # | Item | Why it stays | Raised by |
| --- | --- | --- | --- |
| S1 | ESCALATE triggers C1, C2 and C4; Level 5 on rows #3, #10 and #11; the execution stamp | The ledger door is the documented bounded read; Level 5 pauses for the owner; the stamp is execute-a-plan's own line | Fowler |
| S2 | The ledger's place and name: window-checks inside the family summary-fidelity-judge, file names minted by the door, enrolment for packing; the registry refuses the nested path when it loads | backend/idhazh/contracts/ledgers.py; ledger-registry.md | Fowler |
| S3 | Two-sided Wasserstein-1 | A shorter extraction can be a better one; the distance reads in words or score points and needs no bins | Andre |
| S4 | The 20-article floor | Below 20 a real shift is rarely caught | Andre |
| S5 | Benjamini-Hochberg over Bonferroni | Valid once every check has a p-value (R2) | Andre |
| S6 | Stage 1 checks ignore the model | Already true for the length rule today | Andre |
