# Source health, automatic endpoint lifecycle, and bounded ledgers

**Last Updated**: 2026-09-02
**Level**: 5 (persisted health contracts, automatic endpoint retirement, robots trust policy, and deletion of committed evidence). Owner authorization is required before row 1 starts; no further pause is required inside the plan once given.

## 0 - Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | The quarantine counts repeated rows instead of attempts, a polite refusal wipes a real failure record, two supported Python versions read one `robots.txt` differently, a dead address can only be dropped by a person, and three committed stores have no cleanup at all. |
| Hard scope - in | One effective feed result per feed per run; strike rules that add, preserve and reset for different evidence; typed robots permission and one parser that behaves identically on Python 3.12-3.14; automatic retirement of a feed endpoint that reports itself permanently gone; feed floors that count only endpoints we may ask; one named cleanup age per store; deletion of a browser copy alongside its private source; a bounded score ledger with a permanent summary and exact dedupe index; permission, availability, retirement and yield shown separately on the operator console; removal of the superseded names. |
| Hard scope - out | A single credibility score; reliability or yield changing `FeedDef.weight`, tier weight or item rank; retirement from zero yield, robots denial, 403, 404, a paywall, a transient error or an empty feed; automatic source discovery or replacement; serving raw `state/` rows to a browser; any change to digest-day, visual, corpus or published-article retention; a runtime service, an account, or third-party telemetry. |
| ESCALATE triggers | (1) Execution begins without explicit owner authorization for this Level-5 plan. (2) Any retirement cause other than five distinct HTTP 410 results is proposed. (3) A reliability or yield number is proposed as a rank input or as an irreversible lifecycle input. (4) A legacy row would need an invented endpoint identity or an invented measurement. (5) A cleanup would delete a shard a 366-day read still selects, or unlink anything before its summary is written and read back. (6) Raw item-health rows, source URLs, digests, free text or a robots body would enter the published tree. (7) The parser dependency measures more than three times its recorded install-time or installed-byte figure. Those figures are now measured rather than guessed: **53,292 installed bytes over 17 files, and 0.52 s to install** (row 2, measured on a GitHub-hosted runner on 2026-09-02). Compare against those, never against the 10,296-byte wheel - a wheel is a zip, and the unpacked source, its bytecode and its metadata are three different things. Owner ruling, 2026-09-02. |
| Chosen strategy | Expand, migrate, then contract. Keep permission, current availability, publication yield and editorial value as four separate facts; derive every reversible state from immutable events; persist only HTTP-410 endpoint retirement; summarise before deleting. Ruled by Fowler with Editor on source policy, Carmack on runtime and robots, and Andre on score evidence, 2026-09-02. |
| Execution | autonomous orchestrator per `docs/how-to/execute-a-plan.md`. Parallel N = 2. Each row is its own worktree off `origin/main` and its own PR. |

Execute per docs/how-to/execute-a-plan.md: orchestrator dispatches one worktree-isolated worker subagent per row; workers consult personas on ambiguity; AUTO-merge on green gates; parallel N = 2; honor the ESCALATE triggers in section 0.

**Deletion is the one irreversible act in this plan.** `.github/workflows/prune.yml` squashes and force-pushes `main` on a schedule (`CLAUDE.md` section 8), so a state file deleted by rows 6 and 7 stops being recoverable from history once the prune passes over it. Both rows therefore ship with the existing `prune-state --dry-run` flag set in the workflow, log exactly what they would remove, and a separate one-line commit turns live deletion on after one scheduled run has printed that list.

**Widening a committed CSV header is forward-only.** `ledger.require_matching_header` refuses a header that is not the contract's column list exactly, so row 1 carries both the contract change and the shard migration in one commit, and reverting that commit alone would leave migrated shards no reader can open. A revert of row 1 must revert its shard migration in the same action.

## 0a - What this plan does, in plain English

| # | Row | What changes | The problem it fixes |
| --- | --- | --- | --- |
| 1 | 1 | Add the new columns and settings, move the saved files onto them, and change no decision yet. | The record cannot yet say which address it asked, whether a site allowed it, or why an address was dropped. |
| 2 | 2 | Read each site's "please do not crawl this" file the same way on every Python version we support. | The same rules can be read as allowed on one machine and refused on another, so the pipeline's own behaviour is not reproducible. |
| 3 | 3 | Count one result per source per run, and stop a polite refusal from erasing a source's failure record. | The saved record holds 555 repeated rows, and a site saying "do not crawl" currently wipes five real failures. |
| 4 | 4 | Stop asking an address that reports itself permanently gone, and count only sources we are allowed to ask when checking a topic has enough of them. | Only a person can drop a dead address today, and paused or refused sources pad the count that is meant to stop a thin topic reaching a reader. |
| 5 | 5 | Give every saved record its own named age limit. | One shared setting controls unrelated records, and two of the four are never cleaned at all. |
| 6 | 6 | Delete the browser copy of a record in the same step as the private one. | The public copy outlives the data it was made from, so the page keeps offering detail that no longer exists. |
| 7 | 7 | Summarise old quality scores, prove the summary matches, then delete only the detail. | Nothing bounds that store, and deleting it outright would erase the evidence behind every past quality claim. |
| 8 | 8 | Show each source's permission, working state, retirement and publishing record as four separate facts. | The operator page counts a source that refused us as a reliable one. |
| 9 | 9 | Remove the old setting and field names once every saved file has moved. | Two names for one setting is how somebody edits the one nothing reads. |

## 1 - Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Widen the health record and name the knobs | - | A | DONE #373 | `yi-s01` | 373 | worker |
| 2 | Read robots rules identically on every supported Python | 1 | B | DONE #374 | `yi-s02` | 374 | worker |
| 3 | One result per feed per run, and an honest strike rule | 2 | C | DONE #376 | `yi-s03` | 376 | worker |
| 4 | Retire gone endpoints and count only askable feeds | 3 | D | DONE #377 | `yi-s04` | 377 | worker |
| 5 | Name a cleanup age for every record | 1 | B | DONE #375 | `yi-s05` | 375 | worker |
| 6 | Delete the private record and its browser copy together | 4, 5 | E | DONE #381 | `yi-s06` | 381 | worker |
| 7 | Summarise old scores, then delete only what was summarised | 6 | F | DONE #382 | `yi-s07` | 382 | worker |
| 8 | Publish the source-health scorecard | 4, 7 | G | DONE #383 | `yi-s08` | 383 | worker |
| 9 | Remove the legacy names | 8 | H | PENDING | - | - | - |

**Wave composition, checked by diffing the file lists rather than asserted.** Rows 2 and 5 are the only pair that ever runs concurrently, and their `Files touched` lists are disjoint: row 1 owns every `config/idhazh.json` and `docs/concepts/config.md` edit for the collect knobs, so row 2 needs neither. Every other row shares at least `backend/idhazh/cli.py`, `backend/idhazh/ledger.py` or `backend/idhazh/retention.py` with its predecessor and is serialised for that reason. Row 8 depends on row 4 semantically and on row 7 only because both write `backend/idhazh/cli.py`.

---

### Row #1 - Widen the health record and name the knobs

- **Scope:** Add the columns, the retirement ledger, and the config knobs the later rows read; migrate the committed feed-health shards onto the wider header; change no decision.
- **Files touched:**
  - `backend/idhazh/contracts/feed_health.py`
  - `backend/idhazh/contracts/feed_retirement.py` (new)
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/contracts/export.py`
  - `backend/idhazh/ledger.py`
  - `backend/utilities/migrate_feed_health.py` (new)
  - `backend/utilities/build_canary_day.py`
  - `config/idhazh.json`
  - `schemas/feed-health-row.schema.json`
  - `schemas/feed-retirement-row.schema.json` (generated)
  - `schemas/app-config.schema.json`
  - `state/feed-health/2026-08.csv`
  - `state/feed-health/2026-09.csv`
  - `backend/tests/test_contracts.py`
  - `backend/tests/test_ledger.py`
  - `backend/tests/test_workflows.py`
  - `docs/architecture/sources/health.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/concepts/config.md`
- **Acceptance gates:**
  - Stamp `version` and append a `changelog` entry on every changed contract; `python -m idhazh.contracts.export` then `git diff --exit-code -- schemas/` is clean.
  - Append new columns at the end of the model, never in the middle.
  - Migrate both committed shards in this commit, preserve LF, and read every migrated row back through `FeedHealthRow.from_csv_row()`.
  - Resolve the inevitable append conflict on `state/feed-health/2026-09.csv` by taking the upstream file whole and re-running the migration on it.
  - Register `state/feed-retirements.csv` in `ledger.keyed_paths` so the post-merge settlement already covers it; confirm `.gitattributes` needs no edit because `state/**/*.csv` is already `merge=union`.
  - The canary builder writes every column the contract defines.
  - Run `ruff`, `mypy`, `backend/tests/test_contracts.py`, `test_ledger.py`, and `test_workflows.py`.
- **Oracle:** Every committed feed-health row still validates after the migration and the new cells read back as absent rather than as a value; a fixture built from the pre-migration header fails the header guard, proving the guard is what forced the migration into this commit.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Expand before behaviour. This row adds shape and knobs and changes no decision, so the behavioural rows that follow are reviewable as behaviour alone. | Fowler |
  | 2 | Add nullable `endpoint_key`, typed `robots_outcome`, nullable `robots_checked_at`, nullable `robots_status` and nullable `target_attempted` to `FeedHealthRow`. New rows fill them; every existing row reads as unknown. | Fowler, Carmack |
  | 3 | `endpoint_key` is the SHA-256 of the validated configured feed URL. It identifies what was asked; it never makes two rows for one feed and run legitimate. | Fowler |
  | 4 | Add `FeedRetirementRow` for `state/feed-retirements.csv`: `feed_id`, `endpoint_key`, `retired_on`, `decided_by_run`, `cause`, `evidence_run_ids`. `http_410` is the only cause the enum admits. | Fowler |
  | 5 | Add `collect.availability_strikes_before_rest = 5`, `availability_rest_runs = 5`, `feed_http_410_runs_before_retirement = 5`, `robots_denied_recheck_runs = 1`, `robots_unreachable_recheck_runs = 1` and `source_yield_min_complete_days = 30`. `quarantine_after_failures` keeps working through a read migration until row 9. | Fowler, Carmack |
  | 6 | Do not derive a legacy `endpoint_key` from today's `config/sources.json`. The configured URL may have changed since the row was written, and a guessed identity would retire the wrong address later. | Fowler |
  | 7 | Measured on this Windows developer checkout, 2026-09-02: `state/feed-health/` holds 6,289 rows in 571,426 bytes, and 555 of its `(run_id, feed_id)` keys repeat, 37 of them with differing outcomes or item counts. Reading a committed file is deterministic, so the spread is zero. | Rule #10 measurement |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Ship the shape and the new strike rule in one PR | It mixes a structural change with a behavioural one, so a reviewer cannot tell which of the two moved a quarantine. | Fowler, Kent Beck's Tidy First |
  | 2 | Widen the header without migrating the shards | `require_matching_header` raises on the first scheduled append, so the next digest run fails rather than the branch. | Fowler |
  | 3 | Insert the new columns beside the ones they relate to | The guard compares the whole list, and an appended column is what keeps the old header a readable prefix of the new one. | Fowler |
  | 4 | Keep the retirement record inside `config/sources.json` | A generated commit would rewrite a file a person curates. | Fowler |

---

### Row #2 - Read robots rules identically on every supported Python

- **Scope:** Replace the version-dependent standard-library robots parser, evaluate this crawler against each target path, and record permission as typed evidence.
- **Files touched:**
  - `pyproject.toml`
  - `backend/idhazh/fetch.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/telemetry.py`
  - `.github/workflows/ci.yml`
  - `tests/fixtures/robots/` (new captured text fixtures)
  - `backend/tests/test_extract.py`
  - `backend/tests/test_spans.py`
  - `backend/tests/test_telemetry.py`
  - `docs/architecture/sources/trust-boundary.md`
  - `docs/reference/measurements.md`
- **Acceptance gates:**
  - Record the dependency's measured install seconds and installed bytes with hardware, date, sample count and spread before merge (Rule #8, Rule #10).
  - Run the robots fixture matrix on Python 3.12 and 3.14 in CI.
  - Assert an allowed path and a denied path in the same test, so a swapped-argument call cannot pass by returning one constant answer.
  - Cover crawler-specific groups, wildcard fallback, repeated group merging, longest-match precedence, allow-on-tie, `*`, terminal `$`, percent encoding and malformed lines.
  - Cover robots 2xx, 4xx other than 429, 429, 5xx, timeout, reset and blocked address, with no test touching the network (Rule #7).
  - Prove a denied or unknown target is never requested, and that recovery requests `/robots.txt` first and the target second.
  - Run `ruff`, `mypy`, and the focused fetch, span and telemetry tests.
- **Oracle:** The same committed fixture corpus yields byte-identical permission decisions on Python 3.12 and 3.14, and a recording fetch boundary shows only `/robots.txt` while permission is denied or unknown, then `/robots.txt` followed by the target on the run permission returns.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Use `protego==0.6.2`, the Scrapy organisation's pure-Python parser. Read from PyPI metadata on 2026-09-02: a 10,296-byte pure-Python wheel, BSD-3-Clause, no declared dependencies, `requires_python >= 3.10`, with wildcard support and length-based precedence - which is the behaviour the standard library disagrees with itself about. **Measured on a GitHub-hosted runner (4 vCPU, 16 GB, CPython 3.12.14) on 2026-09-02: 53,292 installed bytes over 17 files, and 0.661 / 0.449 / 0.454 s to install - mean 0.52 s, spread 0.21 s over three samples.** Nothing else in the manifest moved version. The installed footprint is 5.18 times the wheel because a wheel is a zip: 19,709 bytes of source, 30,496 of bytecode pip compiles, 9,142 of metadata. That is 7.3 percent of PyYAML's 728,341 installed bytes, which this project already carries. Owner ruled it inside the budget, 2026-09-02, and set the installed figure as the baseline trigger 7 compares against. | Carmack, Rule #8, owner |
  | 2 | Keep `yen-idhazh/1.0 (+https://github.com/miztiik/yen-idhazh)` as the crawler identity. A group naming another crawler does not bind us; an exact or wildcard group does. | Carmack |
  | 3 | Cache one parsed robots document per normalised `(scheme, host, port)` for the life of one process, and evaluate every target path against it separately. Persist no robots body. | Carmack, Rule #11 |
  | 4 | A robots 4xx other than 429 means the host publishes no rules and the target is permitted. A 429, a 5xx or a transport failure leaves permission unknown and fails closed. | RFC 9309 section 2.3.1; Carmack |
  | 5 | Explicit denial and unreachable rules become different typed outcomes. Neither adds nor clears an availability strike, because neither attempted the target. | Fowler, Carmack |
  | 6 | Recheck denied and unknown permission on the next distinct run. A retry carrying the same `run_id` does not advance the cadence. | Carmack |
  | 7 | Bump `FETCHER_VERSION`. A parser policy change is a different input, and the fingerprint has to be able to say so. | Fowler |
  | 8 | `Protego.can_fetch(url, user_agent)` takes its two arguments in the opposite order to `RobotFileParser.can_fetch(useragent, url)`. A swap is silent and answers every question the same way, so the fixtures assert an allowance and a denial rather than only exercising the call. | Carmack |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep `urllib.robotparser` | Python 3.12 uses the first matching group and the first matching rule; Python 3.14 merges groups and applies longest-match with `*` and `$`. Two supported runtimes can reach opposite decisions on one file. | Carmack |
  | 2 | Pin the whole project to Python 3.14 | A 10,296-byte parser isolates the inconsistent primitive without narrowing the supported range or disturbing the compiled dependency matrix. | Carmack |
  | 3 | Recheck permission on a 24-hour timer | Scheduled runs are irregular, a timer delays same-day recovery, and no measurement justifies the delay it buys. | Carmack |
  | 4 | Send a user agent a site allows | It defeats the publisher's stated policy and discards the contact URL the identity exists to carry. | Rule #11 |
  | 5 | Persist the robots body as evidence | The lifecycle needs a typed decision, not a publisher-controlled document inside `state/`. | Fowler, Rule #11 |

---

### Row #3 - One result per feed per run, and an honest strike rule

- **Scope:** Reduce repeated feed-health rows to one effective event, give add, preserve and reset behaviour to the evidence that deserves each, and make the console read the identical rule.
- **Files touched:**
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/discover.py`
  - `backend/idhazh/cli.py`
  - `frontend/src/lib/feed-health.ts`
  - `frontend/src/lib/server/payload.ts`
  - `frontend/src/lib/server/console-shell.ts`
  - `frontend/src/routes/console/+page.server.ts`
  - `backend/tests/test_discover.py`
  - `backend/tests/test_ledger.py`
  - `backend/tests/test_plan.py`
  - `frontend/tests/console-feeds.spec.ts`
  - `frontend/tests/console-sources.spec.ts`
  - `docs/architecture/sources/health.md`
- **Acceptance gates:**
  - Settle repeated keys both before the write and after the merge, because a job checked out at its trigger commit cannot see rows a sibling attempt pushed afterwards.
  - Prove no committed `(run_id, feed_id)` key repeats after the settlement runs.
  - Cover the full evidence table: non-empty success, empty success, blocked, permanent, transient, robots denied, robots unknown, and skipped.
  - Run `npm run build:canary` before any console spec, so the specs read the canary and not the real digest.
  - Run `ruff`, `mypy`, `test_discover.py`, `test_ledger.py`, `test_plan.py`, then the two focused console specs.
- **Oracle:** One fixture holding duplicate failures, a duplicated non-empty success, a robots denial, a skipped run and a later real success reduces to the same effective events and the same strike count in Python and in TypeScript, with each distinct run counted exactly once.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | A feed-health event is unique by `(run_id, feed_id)`. Where repeats conflict, a non-empty target success wins; otherwise the latest `checked_at` wins. | Fowler |
  | 2 | Blocked, permanent, transient and a success carrying zero items each add one strike. A robots result and a skipped run preserve the streak. A non-empty success resets it. | Editor |
  | 3 | Keep the immediate reset. The streak answers whether the endpoint is broken now; the ledger keeps every old failure for the reliability record, so nothing is forgotten by resetting it. | Editor, Fowler |
  | 4 | The console reducer and the pipeline reducer read the same rule over the same evidence. Two implementations that disagree are how a page contradicts the run that produced it. | Fowler |
  | 5 | Today's resting set is identical with and without deduplication, measured on this checkout on 2026-09-02 over the 31-day read: 15 feeds either way. The defect is therefore latent rather than active, and the fix is correctness rather than a repair of a live outage. | Rule #10 measurement |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Decrement the streak one success at a time | It mixes a historical reliability judgement into a circuit breaker, and holds a recovered endpoint down for failures that are no longer true. | Editor |
  | 2 | One credibility score across permission, availability, yield and editorial value | The four have different units and different actions, and one number cannot say which of them fired. | Editor, Fowler |
  | 3 | Deduplicate only in Collect and leave the shards as they are | Every other reader, the console included, would keep counting a different record. | Fowler |
  | 4 | Settle repeats only before the write | The writer reads a frozen checkout, so a sibling attempt's rows arrive afterwards through the union merge. Both moments are needed. | Fowler |

---

### Row #4 - Retire gone endpoints and count only askable feeds

- **Scope:** Derive permission, rest, probe and HTTP-410 retirement from committed events in one pure reducer, exclude retired endpoints without touching curated config, and make the feed floor describe endpoints we may legally ask.
- **Files touched:**
  - `backend/idhazh/source_health.py` (new)
  - `backend/idhazh/ledger.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/rank.py`
  - `backend/idhazh/assemble.py`
  - `backend/idhazh/contracts/run_plan.py`
  - `backend/idhazh/contracts/run_manifest.py`
  - `schemas/run-plan.schema.json`
  - `schemas/run-manifest.schema.json`
  - `.github/workflows/digest.yml`
  - `backend/tests/test_source_health.py` (new)
  - `backend/tests/test_plan.py`
  - `backend/tests/test_pipeline.py`
  - `backend/tests/test_contracts.py`
  - `backend/tests/test_workflows.py`
  - `docs/architecture/sources/health.md`
  - `docs/architecture/sources/discovery.md`
  - `docs/concepts/pipeline-loop.md`
- **Acceptance gates:**
  - Stamp and migrate `RunPlan` and `RunManifest`; a payload an earlier run wrote still validates.
  - Stage `state/feed-retirements.csv` in the plan job's commit step.
  - Cover every cell of the decision table with pure reducer tests that need no I/O.
  - Cover two stale checkouts appending the same retirement; the merged file settles to one row.
  - Run `ruff`, `mypy`, source-health, plan, pipeline, contract and workflow tests.
- **Oracle:** Five distinct HTTP 410 events against one configured feed endpoint make the next Collect run append exactly one retirement row and issue zero requests to that address; `config/sources.json` is byte-identical afterwards, every historical `source_id` still resolves to a title, and changing that feed's configured URL produces a new endpoint key that is eligible again.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `config/sources.json` stays the curated registry. The automated lifecycle writes `state/feed-retirements.csv` and never rewrites a source definition. | Fowler |
  | 2 | Five HTTP 410 results across five distinct runs retire that endpoint and nothing else. An article-level 410 affects only that item. Retirement outranks rest. | Editor, Fowler |
  | 3 | A non-empty success clears the availability streak and the pending 410 streak. An empty success adds an availability strike and does not clear the 410 streak. | Editor |
  | 4 | Other 4xx, blocks, empty feeds and transient failures may rest an endpoint and may never retire it. Robots denial and unknown permission make it ineligible and stay reversible. | Editor, Carmack |
  | 5 | Runtime retirement is permanent for one endpoint key. A changed configured URL is a new endpoint, with no inherited strikes and no inherited retirement. | Fowler |
  | 6 | Rename `VerticalPlan.live_feeds` to `eligible_feeds`, add `feed_floor` beside it, and carry both onto `VerticalCount`. The read migration maps the old field and invents no floor for a payload that never carried one. | Fowler |
  | 7 | `eligible_feeds` excludes curated tombstones, retired endpoints, robots denials and unknown permission. It includes permitted endpoints that are resting or failing, because the floor measures lawful source diversity rather than today's socket result. | Editor, Fowler |
  | 8 | Availability and yield never change `FeedDef.weight`, source tier, source kind or item rank. | Editor |
  | 9 | Measured on this checkout on 2026-09-02: two live feeds are resting and every desk clears its floor, so this row changes no desk's publishing state on the day it lands. It exists for the outage where that is no longer true. | Rule #10 measurement |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Let the pipeline edit `config/sources.json` | A robot would rewrite curation in a commit nobody reviewed, and two queued runs could reverse each other. | Fowler |
  | 2 | Retire on robots denial | Permission can change, and the recheck must be able to recover it without a config edit. | Carmack |
  | 3 | Retire on 403, 404, a paywall, an empty feed or zero yield | None of them says the address is permanently gone, and each would eventually remove unique primary or regional reporting. | Editor |
  | 4 | Drop every resting endpoint from the feed floor | A bad afternoon would take a well-sourced desk dark. | Editor |
  | 5 | Persist a mutable status snapshot as the control state | A stale writer can overwrite a newer state; immutable events plus a pure reducer replay safely. | Fowler |

---

### Row #5 - Name a cleanup age for every record

- **Scope:** Replace the one generic retention name with a validated value per store, type the browser-safe projection, and keep the old names readable.
- **Files touched:**
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/contracts/public_telemetry.py` (new)
  - `backend/idhazh/contracts/export.py`
  - `backend/idhazh/config.py`
  - `backend/idhazh/publish_telemetry.py`
  - `config/idhazh.json`
  - `schemas/app-config.schema.json`
  - `schemas/public-telemetry.schema.json` (generated)
  - `frontend/public/telemetry/2026-08.csv`
  - `frontend/public/telemetry/2026-09.csv`
  - `backend/tests/test_contracts.py`
  - `backend/tests/test_publish_telemetry.py`
  - `docs/concepts/config.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/publishing/layout.md`
  - `docs/architecture/publishing/telemetry-series.md`
- **Acceptance gates:**
  - Stamp `AppConfig`; both schemas regenerate byte-identically.
  - Read `observability.keep_months` and `hard_delete_after_months` through a migration and stop emitting them in committed config.
  - Validate every full-grain window against `console.max_window_days` at config load, and require the public projection window to equal the item-health window.
  - Migrate the committed public telemetry shards through `PublicTelemetryRow`, preserve LF, and read every row back.
  - Run `ruff`, `mypy`, contract and telemetry-publication tests.
- **Oracle:** Over every end date in a 400-year Gregorian cycle a 366-day read selects only months the configured values retain; lowering any required value by one fails validation, and a config still carrying the old names resolves to the documented migrated values.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `observability.item_health_full_grain_months = 14`. | Fowler |
  | 2 | `observability.feed_health_keep_months = 14`. | Fowler |
  | 3 | `observability.scores_full_grain_months = 14`. | Fowler, Andre |
  | 4 | `observability.public_telemetry_keep_months = 14`, and the contract requires it to equal `item_health_full_grain_months`. | Fowler |
  | 5 | `observability.item_health_aggregate_keep_months = null` and `observability.score_archive_keep_months = null`. Null keeps a summary indefinitely; a finite value must sit above its full-grain window. | Fowler, Andre |
  | 6 | The existing `keep_months = 13` is a config value, not a constant, and 13 is too few: an inclusive 366-day window can touch 14 calendar shards, and the old check compared `months * 30` against the window instead of the shards it selects. | Fowler |
  | 7 | `PublicTelemetryRow` is the browser-safe projection as a contract. It carries its schema version and the existing public columns and cannot carry `canonical_url`, `url_key` or `detail`. | Fowler, Rule #3 |
  | 8 | Config validation reads `config/appearance.json` because that file owns the console window. The digest of that file is already recorded on the run manifest, and no model input fingerprint changes. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Keep one `keep_months` across unrelated stores | An edit meant for item timings would silently delete feed evidence or score history. | Fowler |
  | 2 | Keep 13 because `13 * 30` exceeds 366 | Retention deletes calendar shards, not 30-day blocks, and that arithmetic misses both the inclusive window and short months. | Fowler |
  | 3 | Keep the browser-safe copy only under `state/` | Pages deploys the frontend build; a browser cannot read a file that never leaves `state/`. | Fowler, Rule #1 |
  | 4 | Serve the raw item-health rows | They carry addresses, keys and free text a reader never needs. | Rule #11 |

---

### Row #6 - Delete the private record and its browser copy together

- **Scope:** Fold expired item health, delete expired feed health, remove the browser copy in the same step, and put every deletion behind a summary that was written and read back first.
- **Files touched:**
  - `backend/idhazh/retention.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/publish_telemetry.py`
  - `.github/workflows/digest.yml`
  - `backend/tests/test_retention.py`
  - `backend/tests/test_publish_telemetry.py`
  - `backend/tests/test_workflows.py`
  - `frontend/tests/console-window.spec.ts`
  - `docs/architecture/publishing/layout.md`
  - `docs/architecture/publishing/telemetry-series.md`
  - `docs/architecture/sources/health.md`
  - `docs/architecture/sources/item-health.md`
  - `docs/concepts/config.md`
- **Acceptance gates:**
  - Extend the existing post-publish `prune-state` stage; add no second scheduler.
  - Set `--dry-run` in the workflow for this row, and log the exact list of files a live run would remove.
  - Write and read back the aggregate before unlinking a raw shard or its public copy.
  - Delete only recognised `<YYYY-MM>.csv` shards below their own configured boundary; leave `state/feed-retirements.csv` alone, because it carries no time window.
  - Correct `docs/architecture/sources/item-health.md`, which still says the ledger is never pruned.
  - Cover dry run, empty tree, unrecognised filenames, rerun idempotence, a failed aggregate write, and a stale public copy whose source is already gone.
  - Run `ruff`, `mypy`, retention, telemetry-publication, workflow and the focused console-window spec.
- **Oracle:** A 15-month fixture leaves 14 full-grain item-health shards, 14 matching public copies and 14 feed-health shards; the expired item month exists only as one verified aggregate, the expired feed month is gone, a second run changes no byte, and no 366-day read names a deleted file.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | `state/item-health/` is the private authoritative record and `frontend/public/telemetry/` is its derived browser-safe copy. Both already sit in the right tree; only their lifetimes were disconnected. | Fowler |
  | 2 | Order per expired month: compute the aggregate, write it atomically, read it back and reconcile it, unlink the raw shard, then unlink the public copy. Nothing is deleted on the strength of a write nobody checked. | Fowler |
  | 3 | Feed health older than its window is deleted rather than folded. The quarantine reads 31 days and the console reads at most 366, so no older summary has a reader, and inventing one would persist a shape nothing consumes. | Fowler, Carmack |
  | 4 | This row ships in dry run. Turning live deletion on is a separate one-line config commit taken after a scheduled run has printed what it would delete. | Fowler, owner-facing safety |
  | 5 | Cleanup stays `continue-on-error` after the publish commit. Thirteen-month-old diagnostics must never be the reason a reader loses today's digest. | Fowler |
  | 6 | Measured on this checkout on 2026-09-02: item health holds 6,186 rows in 1,944,795 bytes and feed health 6,289 rows in 571,426 bytes, both across two monthly shards. Reading committed files is deterministic, so the spread is zero. | Rule #10 measurement |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Let the public copy outlive its private source | The page would keep offering per-item detail whose authoritative rows are gone. | Fowler |
  | 2 | Move the raw record into `frontend/public/` | It publishes operator-only fields and charges the deploy budget for private evidence. | Rule #1, Rule #11 |
  | 3 | Delete on total size rather than age | The deletion date would then depend on unrelated files, and the worst days are the first a size rule takes. | Fowler |
  | 4 | Turn live deletion on in the same commit | The prune squashes history, so a wrong boundary would be unrecoverable before anyone read the log. | Fowler |

---

### Row #7 - Summarise old scores, then delete only what was summarised

- **Scope:** Keep 14 months of full score rows, archive older months into a permanent typed summary with an exact observation index, and delete only a shard whose archive reconciles.
- **Files touched:**
  - `backend/idhazh/contracts/score_archive.py` (new)
  - `backend/idhazh/contracts/label_row.py`
  - `backend/idhazh/contracts/export.py`
  - `schemas/score-archive.schema.json` (generated)
  - `schemas/label-row.schema.json`
  - `backend/idhazh/evals/archive.py` (new)
  - `backend/idhazh/evals/writer.py`
  - `backend/idhazh/evals/labels.py`
  - `backend/idhazh/retention.py`
  - `backend/idhazh/cli.py`
  - `backend/utilities/data_wrangler.py`
  - `backend/utilities/label_queue.py`
  - `backend/utilities/reband_scores.py`
  - `backend/utilities/grader_length_bias.py`
  - `.github/workflows/digest.yml`
  - `backend/tests/test_evals.py`
  - `backend/tests/test_labels.py`
  - `backend/tests/test_retention.py`
  - `backend/tests/test_pipeline.py`
  - `backend/tests/test_workflows.py`
  - `docs/concepts/evaluation.md`
  - `docs/architecture/contracts/schemas.md`
  - `docs/architecture/publishing/layout.md`
  - `docs/concepts/config.md`
  - `docs/reference/measurements.md`
- **Acceptance gates:**
  - Stamp `LabelRow`, add its read migration, regenerate both schemas.
  - Write `state/score-archive/<YYYY-MM>.json` atomically and read it back through its contract before unlinking `state/scores/<YYYY-MM>.csv`.
  - Reconcile source hash, row count, observation digests, cohort counts, every stored moment, bands, deciles, signal counts and cut counts before deletion.
  - Union live observation keys with archived digests in `recorded_observations()`.
  - Make a human label self-contained before its source score row can expire.
  - Name the 14-month raw limit in every utility that needs item-level rows, and fail clearly when a requested row has aged out.
  - Ship in dry run, as row 6 does, and measure archive bytes against source bytes with hardware, date, sample count and spread.
  - Run `ruff`, `mypy`, eval, label, retention, pipeline and workflow tests.
- **Oracle:** Archiving one real-shaped month yields a file whose source hash and row count match the shard, whose observation digests are bijective with the shard's `OBSERVATION_KEY` set, and whose moments recompute exactly; after the shard is removed, every archived observation is still refused as a repeat.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Keep the current month plus the previous 13 at full grain, archive older months, and keep archives indefinitely by default. | Andre |
  | 2 | The archive carries its version, the month, the source row count and hash, the sorted observation digests, and cohorts keyed by date, run, row version, model, pipeline fingerprint and scorer version. | Andre |
  | 3 | Each cohort carries its count, ten score deciles, three bands, boolean signal counts, known and actual cut counts, premise-digest counts, and `{n, sum, sum_squares, min, max}` per numeric measurement, so means, ranges and spread survive the deletion. | Andre |
  | 4 | Extend `LabelRow` with the counterweights it currently rejoins from the score row, so a label stays interpretable after its source row expires. | Andre |
  | 5 | What is deliberately lost after 14 months: item-level lookup, a late draw, arbitrary rebanding, percentile recovery, correlation work and any slice the cohorts do not carry. What survives: totals, rates, distributions, ranges, spread, signals, cuts and exact dedupe. | Andre, Rule #10 |
  | 6 | Measured on this checkout on 2026-09-02: `state/scores/` holds 5,001 rows in 3,982,563 bytes across two shards, the largest of the three ledgers this plan bounds. Reading committed files is deterministic, so the spread is zero. | Rule #10 measurement |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Delete old score shards with no archive | It erases the evidence behind published quality claims and lets an old observation be scored again as if it were new. | Andre, Rule #10 |
  | 2 | Keep every raw score row forever | Monthly sharding bounds one file, not the tree, and the dedupe read grows with every month. | Carmack |
  | 3 | Reuse the item-health aggregate shape | Stage timings and model-quality cohorts answer different questions at different grains. | Andre, Fowler |
  | 4 | Compress the old shard and keep scanning it | Fewer bytes, the same unbounded read, and no contract a reader can rely on. | Carmack |
  | 5 | Fold qualification reports here too | It is a separate contract and is not needed to reconcile or deduplicate this one. | Fowler |

---

### Row #8 - Publish the source-health scorecard

- **Scope:** Publish one browser-safe source-health view and show permission, availability, retirement and publishing record as four separate facts on the operator console.
- **Files touched:**
  - `backend/idhazh/contracts/source_health_view.py` (new)
  - `backend/idhazh/contracts/export.py`
  - `schemas/source-health-view.schema.json` (generated)
  - `backend/idhazh/publish_source_health.py` (new)
  - `backend/idhazh/cli.py`
  - `backend/utilities/build_canary_day.py`
  - `.github/workflows/digest.yml`
  - `config/idhazh.json`
  - `frontend/public/source-health.json` (generated)
  - `frontend/src/lib/feed-health.ts`
  - `frontend/src/lib/server/payload.ts`
  - `frontend/src/lib/server/console-shell.ts`
  - `frontend/src/routes/console/+page.server.ts`
  - `frontend/src/routes/console/+page.svelte`
  - `backend/tests/test_publish_source_health.py` (new)
  - `backend/tests/test_contracts.py`
  - `backend/tests/test_pipeline.py`
  - `backend/tests/test_workflows.py`
  - `frontend/tests/console-feeds.spec.ts`
  - `frontend/tests/console-sources.spec.ts`
  - `frontend/tests/console-flow.spec.ts`
  - `docs/architecture/sources/health.md`
  - `docs/architecture/publishing/frontend.md`
  - `docs/concepts/ui-shell.md`
  - `docs/reference/measurements.md`
- **Acceptance gates:**
  - Generate and drift-check the view; it carries no source URL, item URL, digest, free text or robots body.
  - Build the view in Assemble, once the run's health and item rows exist, and commit it on the existing frontend publication path.
  - Count publication yield over distinct `(source_id, url_key)` pairs across complete UTC dates, so five runs of one day cannot inflate either side of the ratio.
  - Print counts and an explicit insufficient-history state until 30 complete dates exist.
  - Render a missing or malformed view as a degraded panel, never a blank page.
  - Finalise every user-facing string before measuring, then re-record `page_weight.ceilings_bytes["/console/"]`, currently 276,828, and pass `npm run bundle-gate`.
  - Run `ruff`, `mypy`, the backend tests above, then `npm run check`, `npm run build:canary`, the focused console specs, and a browser smoke over `/console/` and one digest route with zero new errors and zero new 404s.
- **Oracle:** Every row of the published view reconciles against the backend reducer and the deduplicated item census: permission states sum to the known endpoint count, each retired row resolves to a title, no yield numerator exceeds its opportunity count, and the forbidden raw fields are absent by construction rather than by filtering.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Four columns of fact: permission, availability, retirement, and 30-day publishing record. No column combines two of them. | Editor, Fowler |
  | 2 | An opportunity is one distinct planned address on a complete date; a publication is that address reaching publish on any attempt of that date. Source-owned failures are reported beside the ratio and never subtracted twice. | Editor |
  | 3 | Below the configured minimum history the page prints counts and says the record is too short to read as a rate. | Rule #10 |
  | 4 | A source that refused us is ineligible, not clean and not failed; unknown permission is neither. The reliability sentence stops counting both as reliable delivery. | Editor, Carmack |
  | 5 | The published file is a replaceable projection, never control state. Collect keeps deriving every decision from the private ledgers. | Fowler |
  | 6 | Each automatic state names what the reader loses while it holds: denied or unknown permission withholds that source until the next recheck, a rest withholds it until the probe, and retirement withholds that address until its configured URL changes. | Editor, guardrails veto rule |
  | 7 | The console does not re-derive retirement in TypeScript. It renders the backend's decision, because two reducers are two answers. | Fowler |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | One credibility percentage per source | It cannot distinguish disallowed from unreachable from empty from low-yield, which are four different actions. | Editor |
  | 2 | Ship the raw ledgers to the browser | The page needs derived states and counts, not private addresses, keys and diagnostics. | Rule #11 |
  | 3 | Hide the short-history case | A rate over fewer than 30 complete dates would present an estimate as a measurement. | Rule #10, Andre |
  | 4 | Fetch the view at read time on every load | It is small, it is needed on first paint, and the console already prerenders what it knows at build time. | Jony, Carmack |

---

### Row #9 - Remove the legacy names

- **Scope:** Stop emitting and reading the superseded config and payload field names now that every writer and every committed file has moved.
- **Files touched:**
  - `backend/idhazh/contracts/app_config.py`
  - `backend/idhazh/contracts/run_plan.py`
  - `backend/idhazh/contracts/run_manifest.py`
  - `backend/idhazh/cli.py`
  - `backend/idhazh/rank.py`
  - `config/idhazh.json`
  - `schemas/app-config.schema.json`
  - `schemas/run-plan.schema.json`
  - `schemas/run-manifest.schema.json`
  - `backend/tests/test_contracts.py`
  - `backend/tests/test_plan.py`
  - `backend/tests/test_discover.py`
  - `docs/concepts/config.md`
  - `docs/architecture/sources/health.md`
- **Acceptance gates:**
  - Remove `collect.quarantine_after_failures`, `observability.keep_months` and `observability.hard_delete_after_months` from the emitted config and from every reader.
  - Keep the read-side migration for any committed payload that still carries `live_feeds`, and prove it against the oldest committed run payload.
  - Stamp every changed contract and regenerate the schemas byte-identically.
  - Grep the repository for each removed name and show zero hits outside a changelog entry or a design-rationale line.
  - Run `ruff`, `mypy`, and the full backend suite.
- **Oracle:** A config file carrying only the new names loads with no defaulted lifecycle value, a config carrying a removed name fails validation with a message naming its replacement, and every committed run payload still validates.
- **Decisions:**

  | # | Decision | Authority |
  | --- | --- | --- |
  | 1 | Contract last. The old names stay readable until every row that depends on them has merged, then leave in one commit. | Fowler |
  | 2 | A removed config name fails loudly and names its replacement. Silently ignoring an edited knob is how an operator believes a value that nothing reads. | Fowler |
  | 3 | Payload read migrations for `live_feeds` remain, because a committed payload cannot be rewritten and a reader must still open it. | Fowler, section 11 |

- **Rejected alternatives:**

  | # | Option | Why rejected | Authority |
  | --- | --- | --- | --- |
  | 1 | Delete the old names in row 1 | Every later row would have landed against a config nobody could roll back to. | Fowler |
  | 2 | Keep both names indefinitely | Two names for one knob is how the wrong one gets edited, and the dual read never gets deleted. | Fowler |
  | 3 | Drop the payload read migration too | An older committed run payload would stop validating, which is a release blocker under section 11. | Fowler |
