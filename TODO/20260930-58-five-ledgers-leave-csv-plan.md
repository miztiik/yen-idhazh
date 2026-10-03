# Plan 58 - Five more ledgers leave CSV, and one kit moves the rest

**Last Updated**: 2026-10-02

**Level**: 4 (CLAUDE.md section 6). Each ledger row deletes committed CSV once its rows are proven in parquet, and a deletion the history squash has passed cannot be undone (CLAUDE.md section 8). So reverting a row costs more than writing it. No row changes a persisted contract; a row that needs to stops at ESCALATE trigger 4.

**Status**: written 2026-09-30, refined 2026-10-01 after Fowler's review, and corrected the same day after a second review. Later on 2026-10-01 the person asked for packing by month and by year on every door ledger, the three moved before this plan included, with every packing, prune and retention setting in JSON: row 8 is new, rows 2 to 6 pack live with their windows reporting, and section 4's decisions 2 and 3 are answered. Rows 1, 2, 3, 4 and 8 are done (#1184, #1190, #1181, #1186, #1185). The first upkeep wake after plan 51's packing row completed on 2026-10-02 and packed item-health and host-fingerprint live without failure. The person answered section 4 decisions 1 and 4 on 2026-10-02: a re-run replaces its first try's `seen` rows, and `digest.yml` keeps running through row 5's merge. Row 5 is ready.

Execute per docs/how-to/execute-a-plan.md: one owner carries the plan and delegates a row where delegation pays; keep parallel N = 2 rows in flight, refilling a slot as soon as a worker returns and never waiting on a merge; consult a persona only where two answers would lead to different code; AUTO-merge on green gates; honor the ESCALATE triggers in section 0. The person authorized execution on 2026-10-01.

## 0. Operating contract

| Field | Value |
| --- | --- |
| Why this plan exists | Most ledgers under `state/` still write CSV and no plan owns moving them, so the person asked for the next ones to move writer and readers to the parquet door with their CSV code, tests and docs deleted, every shape declared before any code, and the tools built once so that every later batch repeats the same steps. On 2026-10-01 the person added that packing by month and by year works on every door ledger, the ones moved before this plan included, with every packing, prune and retention setting in JSON |
| Hard scope - in | - Section 2 declares every shape the moves need, and row 1 lands the shared ones before any ledger moves.<br>- `counterfactual-scores`, `candidate-models`, `seen`, `published` and `feed-health` meet every part of section 2.10 (rows 4 to 6).<br>- One migrator for any ledger's CSV, in `state/` and in every trial root, and the recipe on one page (rows 1 and 2).<br>- A guard that holds every moved ledger to no CSV path, and a loader that reads each kept window from the one declaration that governs the ledger (row 1).<br>- The prune verb reaches every ledger on the door, and each compaction declaration says whether the verb may take its days (row 3).<br>- Every compaction declaration names every setting it runs with, and a window can report while packing runs live (row 8).<br>- Packing by day, by month and, for a ledger kept for ever, by year runs live for the five ledgers. The migrator packs every period, and packs the three ledgers moved before this plan too (rows 2 and 4 to 6, section 2.11).<br>- The CSV that `item-health` and `host-fingerprint` left in the trial roots (row 2).<br>- The map of every ledger still on CSV, with what blocks each one (row 7) |
| Hard scope - out | the table below |
| ESCALATE triggers | 1. A window that deletes rows going live before the person approves it: a `monthly_window_dry_run` moving from `true` to `false`, or a retention declaration's `dry_run` doing so. Also a `dry_run` moving from `true` to `false` on a declaration section 2.3 does not write, or a `monthly_window` or `monthly_keep_days` other than the one section 2.3 derives.<br>2. The migrator refuses a ledger, or a read-back differs from the CSV by one cell. The row deletes nothing and reports the day and the file.<br>3. A change that could drop or shorten a row of `seen` or `published`, other than a CSV row the migrator has proven in parquet and the re-run rule the person settles in section 4: a reach under a reader's window, or a prune path.<br>4. A move needs a contract field renamed, retyped or removed, a contract `version` moved, or a new `ServerJob` or `LedgerName` member. That changes a persisted contract (CLAUDE.md section 6, Level 5).<br>5. A row's precondition is false at dispatch, or main no longer matches a shape section 2 quotes.<br>6. A change would pack a trial root |
| Chosen strategy | One pull request lands every shared shape first, beside the prune. Then every compaction setting is written out, after the completed packing change #1177. Then the migrator's second layout and its packing run beside the two ledgers no reader depends on, then the two union ledgers move, then the one a page reads. Rows that run together share no file and no touching Reckoner line. Fowler, 2026-09-30 and 2026-10-01; packing and settings added at the person's request, 2026-10-01 |
| Execution | autonomous orchestrator per docs/how-to/execute-a-plan.md. Parallel N = 2: a running pool (execute-a-plan, "Parallel fan-out") over a graph that never has more than two rows ready at once - rows 1 and 3, then row 8, then rows 2 and 4, then rows 5, 6 and 7 one at a time. Eight pull requests, one a row. The owner merges each one on green gates with `gh pr merge --squash --delete-branch`, as execute-a-plan says, and never with `--auto`, which GitHub refuses on this repository; a ledger row merges only inside section 3 step 3's window |

### Hard scope - out

| What is out | What it costs to leave out | What would bring it in |
| --- | --- | --- |
| The four `content-similarity-judge` ledgers and `llm-council/shard-outcomes` | They keep writing CSV, with the union driver and the closed-day fold | A second batch. It needs a registry rule for a nested folder name, `Literal` fields in the arrow mapper, and a person's ruling on each field that carries a name the file envelope reserves (`shard`, `run_id`) but means something else. Row 7 writes the map |
| `item-health-summary` | It stays a CSV month file | A ruling in the second batch: each run rewrites its month file, which neither layout in section 2.6 reads |
| `summary-quality-evals-index`, the eval ledger's ID files | None here | Plan 56's row "The eval ledger's ID files are packed a month at a time", done (#1180) |
| `span-rollup`, and its CSV in the trial roots | None here | Retirement and the item command are complete in merged PR #1189 |
| `state/content-similarity-judge/holdout-pairs.csv` | None: a person edits it by hand. It is also the guard's example of a ledger the door refuses | A person's decision that a program writes it |
| Publishing a moved ledger to the site | The site cannot query the five ledgers until then | Plan 55's row "Every declared ledger reaches the site, capped at the widest span" |
| A window that deletes rows going live on `counterfactual-scores`, `seen` or `feed-health` | Their month files stay past the window, as today's report-only retention keeps their CSV, and each pass records what the window would take | The person's approval, one ledger at a time, through plan 57's row "The retention windows the person approves go live, one task a pull request": that compaction's `monthly_window_dry_run` set to `false` |
| Year files for `item-health`, `host-fingerprint`, `counterfactual-scores`, `seen` and `feed-health` | Each keeps up to 12 month files a year where one year file would do | A window of forever on that ledger, which keeps every row for ever. A year file cannot give back one month when a window reaches it, so the loader refuses `monthly_keep_days` beside any other window |
| The prune verb's lists left in code: `_TARGET_LEDGERS`, and the line of `REFUSED` for `summary-quality-evals-index` | Those settings stay in `backend/idhazh/telemetry/prune.py`. The five CSV ledgers left have no declaration to hold one, and the ID files' declaration is a retention one | The second batch moves the five ledgers, which empties `_TARGET_LEDGERS`; a `prune_refusal` key on retention declarations would take the last line of `REFUSED` |
| The shared CSV machinery: `backend/idhazh/day_shards.py`, `write_segment` and `extend_segment`, `backend/idhazh/gardener/closed_day_fold.py`, `extend_ledger_file`, and the frontend's `readDayShards` | None: each still has a user | Each goes with its last user. Row 7 writes each one's removal condition |

## 1. Status Reckoner

| # | Row title | Depends-on | Parallel-group | Status | Worktree | PR | Subagent |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | Every shape the moves need is declared, and a guard holds each moved ledger to it | - | A | DONE | p58r1 | #1184 | p58-r1-worker |
| 2 | The migrator reads both CSV layouts in every root, packs every period, and the recipe is written down | 1, 3, 8 | C | DONE | p58r2 | #1190 | p58-r2-worker |
| 3 | The prune verb reaches every ledger on the door | - | A | DONE | p58r3 | #1181 | p58-r3-worker |
| 4 | The counterfactual scores and the candidate verdicts move to the door | 1, 3, 8 | C | DONE | p58r4 | #1186 | p58-r4-worker |
| 5 | The seen and published ledgers move to the door, and their union drivers retire | 2, 4 | D | DONE | p58r5 | #1194 | p58-r5-worker |
| 6 | Feed health moves to the door, and the Voices page reads it packed | 5 | E | PENDING | - | - | - |
| 7 | The map of the ledgers left on CSV is written, and the plan closes | 6 | F | PENDING | - | - | - |
| 8 | Every compaction declaration names every setting it runs with, and a window can report while packing runs live | 1, 3 | B | DONE | p58r8 | #1185 | p58-r8-worker |

Row 8's external packing prerequisite is complete (#1177), and its first live upkeep wake was verified on 2026-10-02. Row 5's decisions 1 and 4 were answered that day. The plan-queue reader, `backend/utilities/plan_status.py`, cannot follow a pointer by title, so the owner checks those at dispatch.

Rows that can be in flight together sit on lines that do not touch - 1 with 3, then 2 with 4 - because each row's pull request edits its own line and git refuses two edits to touching lines. Row 8 shares files with rows 1 and 3, so it runs alone. The owner marks both rows of a pair `IN-FLIGHT` on main in one commit before cutting either branch.

## 2. Contracts

Every shape a worker needs is declared here. A row builds the parts its own section names and invents none; a shape main no longer matches is ESCALATE trigger 5. No persisted contract changes: no field, no `version` stamp, no `ServerJob` member and no `LedgerName` member. `config/ledgers.json` and `config/gardener/*.json` are configuration this project authors, loaded by the models that load them today; rows 3 and 8 add two keys to `CompactionPolicy`, which loads the second (section 2.11).

### 2.1 The five door declarations

Row 1 adds the five entries to `_DOOR_SHAPES` in `backend/idhazh/ledger/keys.py`, and declares `SEEN_KEY` and `PUBLISHED_KEY` beside the other keys. `_DoorShape` keeps its two fields, `key` and `model`. Nothing asks the door about a ledger before its registry grain switches (section 2.2), so the entries change nothing until then.

| Ledger | Row contract | Door key | How repeats settle | A row with no `date` field | Fields with an envelope name |
| --- | --- | --- | --- | --- | --- |
| `counterfactual-scores` | `CounterfactualScoreRow`, `backend/idhazh/contracts/counterfactual_score.py` | `COUNTERFACTUAL_SCORE_KEY`: `date`, `run_id`, `vertical`, `url_key` | the first row filed wins | none: every row has `date` | `run_id`, the run that wrote the row |
| `candidate-models` | `ValidationRow`, `backend/idhazh/contracts/validation_row.py` | `VALIDATION_KEY`: `date`, `run_id`, `model_id` | the first row filed wins | none | `run_id`, the same |
| `feed-health` | `FeedHealthRow`, `backend/idhazh/contracts/feed_health.py` | `FEED_HEALTH_KEY`: `run_id`, `feed_id` | `FEED_HEALTH_RULE`, which `preference_for(FEED_HEALTH_KEY)` already returns | none | `run_id`, the same |
| `seen` | `SeenRow`, `backend/idhazh/contracts/seen.py` | `SEEN_KEY`, new: `url_key`, `first_seen_run` | the first row filed wins; only exact copies share a key | filed under the day the plan stage ran for | none |
| `published` | `PublishedRow`, `backend/idhazh/contracts/seen.py` | `PUBLISHED_KEY`, new: `url_key`, `published_on`, `item_id` | the first row filed wins; only exact copies share a key | filed under the digest day `append_published` is given | none |

- Before any key, the door's own rule holds for every ledger: for each work unit it keeps the file of the highest attempt (`settle_rows` in `backend/idhazh/ledger/raw_files.py`). Section 4 decision 1 is what that means for `seen`.
- An envelope name is one of the keys in `_KEYS` in `backend/idhazh/contracts/file_envelope.py`, which every door file carries beside its rows. In all three ledgers above `run_id` means the run id, so no field is renamed.
- `ValidationRow.commit_sha` is declared `Sha256 | str`. Row 1 teaches `columns_of` in `backend/idhazh/ledger/arrow_schema.py` to map a union whose members are all strings to the string column type. `Literal` fields and every other union stay refused.

### 2.2 Registry entries

Each ledger's entry in `config/ledgers.json` becomes this, in the commit that moves it:

```json
{
  "name": "<ledger>",
  "grain": "raw-and-compact",
  "prefix": ["<ledger>"],
  "stem": null,
  "suffix": null
}
```

The family block around the entry is unchanged; `seen` and `published` lose `"suffix": ".csv"`. The grain is the only switch. The guard (2.9), the prune's door targets (2.8) and the migrator's refusals and `--check` (2.6) read it, the loader (2.7) follows the declarations the same commit writes, and no second flag says the same thing.

### 2.3 Compaction declarations

`config/gardener/compact-<ledger>.json`, written in the ledger's own row:

```json
{
  "compact_after_days": 1,
  "daily_keep_days": 45,
  "dry_run": false,
  "kind": "compaction",
  "ledger": "<ledger>",
  "lifecycle_status": "active",
  "max_deletes_per_run": null,
  "max_periods_per_run": 8,
  "max_raw_files_per_period": 2000,
  "monthly_keep_days": "<Y>",
  "monthly_window": "<W>",
  "monthly_window_dry_run": true,
  "owns": [
    "state/raw/<ledger>",
    "state/compact/<ledger>"
  ],
  "prune_refusal": "<P>",
  "raw_index_keep_days": 90,
  "window": {
    "unit": "forever"
  }
}
```

Every key is written: from row 8 the loader refuses a compaction declaration that omits one (section 2.11). `dry_run` is `false` and `monthly_window_dry_run` is `true` in all five, so packing runs live and no window deletes a row until the person turns it live (section 4, decisions 2 and 3). The four other numbers are main's defaults of 2026-10-01, written out. `<W>` is a window object, not a string. It carries an old retention window counted in months over unchanged; otherwise it is the smallest whole number of months that `compaction_reaches` (2.7) accepts against every floor in 2.7 and the old window in 2.6; and it is `{"unit": "forever"}` where nothing deletes the ledger today. It is re-derived at dispatch, and a different answer is ESCALATE trigger 1. `<Y>` is 93 where `<W>` is forever - the wait the person set for the eval ledger (plan 56, ruling R6) - and `null` elsewhere, because the loader refuses a year beside any other window. `<P>` is `null`, or the sentence `REFUSED` in `backend/idhazh/telemetry/prune.py` gives the ledger on main. At the settings of 2026-10-01:

| Ledger | Old window (2.6) | Floor (2.7) | `<W>` | `<Y>` | `<P>` | Row |
| --- | --- | --- | --- | --- | --- | --- |
| `counterfactual-scores` | 30 days | `lens_weights.window_days`, 30 | 1 month | `null` | `null` | 4 |
| `candidate-models` | forever | none | forever | 93 | `null` | 4 |
| `seen` | 90 days | `collect.seen_window_days`, 90 | 2 months | `null` | the sentence `REFUSED` gives `seen` | 5 |
| `published` | forever | `collect.published_window_days`, -1, which means forever | forever | 93 | the sentence `REFUSED` gives `published` | 5 |
| `feed-health` | 14 months | the console's widest read | 14 months | `null` | `null` | 6 |

Each row adds its compactions' `dry_run` to `LIVE_BY_DECISION` in `backend/tests/contracts/test_gardener_config.py`, with the reason in plain words and no plan number: packing writes every row into a coarser file before it deletes one, and the window only reports. A window the person turns live later adds its own entry the same way.

### 2.4 Writers

| Ledger | Writer today | Becomes | Identity |
| --- | --- | --- | --- |
| `counterfactual-scores` | `ledger.write_segment` in `backend/idhazh/stages/plan.py` | `ledger.persist(state, rows, ledger=LedgerName.COUNTERFACTUAL_SCORES, covers=date, identity=identity)` | the `WriterIdentity` plan.py already builds for feed retirements: `job=ServerJob.PLAN`, `shard=PLAN_SHARD`, `producer=PRODUCER`, `git_sha=commit_sha`, built once and passed to all three plan writers |
| `feed-health` | `ledger.write_segment` in plan.py | `ledger.persist(state, rows, ledger=LedgerName.FEED_HEALTH, covers=date, identity=identity)` | the same |
| `seen` | `ledger.append_seen`, called from plan.py | `append_seen(state_dir, date, rows, *, identity) -> int`, filing through `ledger.persist(..., covers=date)` and returning the rows it filed | the same |
| `published` | `ledger.append_published`, called from `backend/idhazh/stages/assemble.py` | `append_published(state_dir, date, rows, *, identity) -> int`, the same way | the identity assemble.py already builds for item-health: `job=ServerJob.ASSEMBLE`, `shard=ASSEMBLE_SHARD` |
| `candidate-models` | `ledger.write_segment` in `backend/idhazh/stages/qualify_decide.py` and `stages/decide.py` | `ledger.persist(state, rows, ledger=LedgerName.CANDIDATE_MODELS, covers=date, identity=identity)` | `WriterIdentity(run_id=run_id, attempt=run_context.run_attempt(), job=ServerJob.DECIDE, shard=DECIDE_SHARD, producer=PRODUCER, git_sha=commit_sha)`; each module gains `PRODUCER: Final = __name__.partition(".")[2]`, as plan.py has |
| `feed-health`, canary | `ledger.write_segment` in `health()`, `backend/utilities/build_canary_day.py` | `ledger.persist(state, rows, ledger=LedgerName.FEED_HEALTH, covers=date, identity=identity)`, and `PACKED_LEDGERS` gains `LedgerName.FEED_HEALTH` | `WriterIdentity(run_id=f"{date}-1", attempt=1, job=ServerJob.PLAN, shard=0, producer=PRODUCER, git_sha=FIXTURE_SHA)`, with the module's own `PRODUCER` and `FIXTURE_SHA`, as `_fixture_writer` uses them |

- `stage_qualify_decide` gains `commit_sha: str`, and `backend/idhazh/cli.py` passes `args.commit`, as it already does for `decide`.
- `.github/workflows/validate.yml`: the step "Run the gates" of the `decide` job gains `--commit "${{ github.sha }}"`. Its commit step already stages the whole trial root and is unchanged.
- `.github/workflows/digest.yml` already passes `--commit` to `plan` and `assemble`. `backend/tests/workflows/test_ledger_door_jobs.py` names any other step that runs a writing verb without it.

### 2.5 Readers

The backend readers keep their signatures and their answers:

```python
def load_seen(state_dir: Path, *, today: str, within_days: int) -> dict[str, str]: ...
def load_published(state_dir: Path, *, today: str | None, within_days: int) -> dict[str, str]: ...
def load_health(state_dir: Path, *, today: str, within_days: int) -> list[FeedHealthRow]: ...
```

| Reader | Reads after the move | Answer |
| --- | --- | --- |
| `ledger.load_seen` | `ledger.load_days(state_dir, LedgerName.SEEN, days_in_window(today, within_days), model=SeenRow)` | each address to its earliest `first_seen_at`, as today |
| `ledger.load_published`, with a window | `load_days` over `days_in_window(today, within_days)` | each address to its earliest `published_on`, as today |
| `ledger.load_published`, with `within_days` -1 or `today` None | one month at a time: `load_days(state_dir, LedgerName.PUBLISHED, month_days(m), model=PublishedRow)` for each `m` in `held_months(state_dir, LedgerName.PUBLISHED)`, folded into the answer before the next month is read | the same; the most it holds is one month's rows and the answer |
| `ledger.load_health` | the newest `within_days` days that `held_days(state_dir, LedgerName.FEED_HEALTH)` returns, through `load_days`; `today` stays unread, as it is today | the same rows, sorted by `date` and then by the run number in `run_id`, as today |

`days_in_window` is in `backend/idhazh/day_partition.py`; `held_days`, `held_months` and `month_days` are in `backend/idhazh/ledger/ledger_files.py`. Reading every published day stays the growing read it is today (Guardrail #12), and `docs/concepts/growing-reads.md` names its new files.

The console's build-time read of feed health:

```ts
// frontend/src/lib/server/ledger-rows.ts - new, written the way itemHealthRows is
export const FEED_HEALTH_COLUMNS = ['run_id', 'date', 'feed_id', 'checked_at', 'outcome', 'status', 'items', 'detail'] as const;
export async function feedHealthRows(days: number = LEDGER_WINDOW_DAYS, root: string = STATE_ROOT): Promise<LedgerTable>;

// frontend/src/lib/server/payload.ts - was synchronous
export async function feedResults(days: number = LEDGER_WINDOW_DAYS, root: string = STATE_ROOT): Promise<FeedResult[]>;
```

- `feedHealthRows` returns `newestRows(root, 'feed-health', days, FEED_HEALTH_COLUMNS, (start, end) => sliceFromDisk(root, 'feed-health', { columns: [...datedFirst(FEED_HEALTH_COLUMNS)], from: start, to: end }))`.
- `feedResults` maps those rows to `FeedResult` exactly as it maps CSV rows today and returns them through `settled()`. A ledger not yet packed gives an empty list. `frontend/src/routes/console/voices/+page.server.ts` awaits it.
- `LEDGER_NAMES` in `frontend/src/lib/data/slice-shapes.ts` gains `'feed-health'`, unless plan 55 has already widened it to every ledger.
- `frontend/tests/console-voices-feeds.spec.ts` reads the canary's feed rows through `feedHealthRows(days, join(CANARY, 'state'))` instead of `readDayShards`.

### 2.6 The migrator's table and command line

Row 1 declares the table and the refusals in `backend/utilities/migrate_to_parquet.py`; row 2 adds the `day` layout and repeated roots.

```python
class CsvLedger(NamedTuple):
    """How one ledger was filed before it moved to the door, and how long it was kept."""

    old_entry: LedgerEntry
    old_window: Window


CSV_LEDGERS: Final[Mapping[LedgerName, CsvLedger]] = MappingProxyType({...})


def csv_root(state_dir: Path, ledger: LedgerName) -> Path: ...
```

`CSV_LEDGERS` replaces `LEDGERS`. A ledger's contract and key come from `door_contract` and `door_key`, so the table holds neither. `csv_root` is `state_dir` joined with `old_entry.prefix`. The docstring of `CSV_LEDGERS` carries its removal condition: the table, the module and its tests are deleted when no ledger is left on CSV.

| Ledger | `old_entry.grain` | `old_entry.prefix` | `old_entry.suffix` | `old_window` | Where `old_window` comes from |
| --- | --- | --- | --- | --- | --- |
| `item-health` | `tree` | `item-health` | null | 14 months | the `full-grain` series of `config/gardener/telemetry-aggregate.json` |
| `summary-quality-evals` | `tree` | `scores` | null | forever | nothing deletes an eval row |
| `host-fingerprint` | `tree` | `host-fingerprint` | null | 14 months | `config/gardener/host-fingerprint.json`, which row 1 deletes |
| `counterfactual-scores` | `tree` | `counterfactual-scores` | null | 30 days | `config/gardener/counterfactual-scores.json` |
| `candidate-models` | `tree` | `candidate-models` | null | forever | nothing deletes it |
| `feed-health` | `tree` | `feed-health` | null | 14 months | `config/gardener/feed-health.json` |
| `seen` | `day` | `seen` | `.csv` | 90 days | `config/gardener/seen.json` |
| `published` | `day` | `published` | `.csv` | forever | nothing deletes it |

The three moved entries are read from `config/ledgers.json` as it stood before plan 50 moved them, and a value that differs from this table is ESCALATE trigger 5. The eval ledger's CSV sat at `scores/`, its folder before plan 56 renamed it, so its `old_entry` has the prefix `scores` under the name `summary-quality-evals`: a `scores` name would need a `LedgerName` member, which is ESCALATE trigger 4. `CSV_LEDGERS` replaces main's `_CSV_FOLDERS` pin as well as `LEDGERS`.

Layouts, under `csv_root(root, ledger)`:

- `tree`: `YYYY/MM/DD/*.csv`, one file a writer a day, with `before-partition.csv` and the closed-day fold's `settled.csv` included. Row 1 keeps it as it is.
- `day`: `YYYY/MM/DD.csv`, one shared file a day. Row 2.
- Any other grain is refused by name.

```
python backend/utilities/migrate_to_parquet.py --state-dir DIR [--state-dir DIR ...] --run-id RUN_ID --git-sha SHA [--ledger NAME ...] [--check]
```

- `--state-dir` repeats from row 2; row 1 keeps one, and from row 1 a root other than `<repo>/state` is filed raw and never packed. `--ledger` repeats from row 1; its choices are the keys of `CSV_LEDGERS`, and with none named it means every table ledger the registry files as `raw-and-compact`.
- Refused before any file is written, with exit 1 and the reason: a named ledger the registry does not file as `raw-and-compact`; a ledger with no `compact-<ledger>` declaration; a declaration that fails `compaction_reaches(policy, old_window)`.
- A run, root by root: read the old layout; file each day through `ledger.persist` with `WriterIdentity(run_id=RUN_ID, attempt=1, job=ServerJob.MIGRATE, shard=0, producer="utilities.migrate_to_parquet", git_sha=SHA)`, a row with no `date` field under its CSV file's day; pack, only when the root is `<repo>/state`, as the next point says; read every day back through `load_days` and compare cell for cell; then delete that root's CSV of the ledger.
- To pack, the migrator runs the compaction's own pass, `run` in `backend/idhazh/gardener/tasks/compaction.py`, on the ledger's declaration with `dry_run` false, `monthly_window_dry_run` true and no period ceiling, and runs it again until a pass writes and deletes nothing. So it packs every day, month and year the declaration admits, into the files the upkeep would write, and drops no month. Main's `_pack` runs the daily step alone.
- A ledger the run covers that has no CSV left under `<repo>/state` is packed and nothing else, so `--ledger item-health` packs a ledger moved before this plan.
- `--check` writes nothing and exits 1 when a CSV file of the named ledgers remains under any root.
- Exit 0 means migrated, or nothing left to migrate.
- `RUN_ID` matches `RUN_ID_PATTERN` in `backend/idhazh/contracts/base.py`: the UTC day of the migration commit, then `-1`. A later run for the same row, under section 3 step 3 or step 4, passes the same `RUN_ID`. A day it files again is then the same work unit, and its new file - the rows the door held, with the late CSV folded on - replaces the first. `SHA` is the full sha of the commit the migrator runs at.

### 2.7 The loader's floors

Row 1, `backend/idhazh/config.py`. Floors are keyed by ledger and read from whichever declaration governs the ledger now, so no ledger row edits this file.

```python
_WINDOW_FLOORS: Final[Mapping[LedgerName, str]] = MappingProxyType(
    {
        LedgerName.SEEN: "collect.seen_window_days",
        LedgerName.COUNTERFACTUAL_SCORES: "lens_weights.window_days",
        LedgerName.PUBLISHED: "collect.published_window_days",
    }
)
_CONSOLE_READ_LEDGERS: Final[tuple[LedgerName, ...]] = (
    LedgerName.FEED_HEALTH,
    LedgerName.SUMMARY_QUALITY_EVALS_INDEX,
)
_CONSOLE_READ_SERIES: Final[tuple[tuple[str, str], ...]] = (
    ("telemetry-aggregate", FULL_GRAIN),
    ("telemetry-aggregate", PUBLIC_COPY),
)
_MACHINE_SOURCE: Final = LedgerName.HOST_FINGERPRINT


def _governing(
    ledger: LedgerName, tasks: Mapping[str, TaskPolicy]
) -> RetentionPolicy | CompactionPolicy | None:
    """The one declaration that says how long this ledger is kept now."""


def compaction_reaches(policy: CompactionPolicy, needed: Window) -> bool:
    """Whether this compaction keeps every day `needed` asks for."""
```

- `_governing` returns `compact-<ledger>` when it is a `CompactionPolicy`; else the `RetentionPolicy` whose `owns` holds `state/` joined with the ledger's registry prefix; else `None`.
- A floor of N days is `DaysWindow(N)`, and a negative knob is `ForeverWindow`. `None` meets every floor, because nothing deletes the ledger. A `RetentionPolicy` meets a floor when `_reaches(policy.window, floor)`; a `CompactionPolicy` when `compaction_reaches(policy, floor)`.
- `compaction_reaches`: a `monthly_window` of forever reaches anything; otherwise a forever floor is never reached; otherwise `daily_keep_days` plus the fewest days `monthly_window` can hold must be at least the most days `needed` can hold. That is the arithmetic `_refuse_a_compaction_that_cuts_its_ledger` uses today, and that function calls this one.
- Each ledger in `_CONSOLE_READ_LEDGERS` keeps `MonthsWindow(months_a_window_can_touch(console.max_window_days))` by the same two rules. `_CONSOLE_READ_SERIES` keep today's rule.
- The declaration that governs `_MACHINE_SOURCE` keeps `MonthsWindow(observability.public_machine_keep_months)`.
- `_old_tree_floor` keeps its series branch. Its owns branch goes, together with `config/gardener/host-fingerprint.json`. `host_fingerprint_keep_months` in `backend/idhazh/contracts/knobs/observability.py` points at `monthly_window.value in config/gardener/compact-host-fingerprint.json`.
- Every refusal names the declaration file, the knob and both values, as today's do.

### 2.8 The prune verb on the door

Row 3.

```
idhazh telemetry prune --target WORD --since YYYY-MM-DD --until YYYY-MM-DD [--max-deletes N] [--dry-run | --no-dry-run] [--run-id RUN_ID --commit SHA]
```

- Targets: `_TARGET_LEDGERS`, unchanged in name and meaning (the CSV ledgers), plus every ledger the registry files as `raw-and-compact` whose compaction declaration's `prune_refusal` is `null`. A door ledger whose declaration gives a sentence is refused with that sentence, as `REFUSED` refuses a ledger today, and `REFUSED` keeps the ledgers no compaction declares. A target word is the ledger's prefix joined by `-`, as today.
- `prune_refusal: str | None` is a new key of `CompactionPolicy`, with no default. Row 3 writes it into every compaction declaration on main and the two under `tests/fixtures/gardener/`: for `summary-quality-evals`, a sentence that every eval row is kept for ever and why (plan 56, ruling R1); `null` for the rest. Without that sentence the verb would take days from the eval ledger.
- `--run-id` and `--commit` are required when `--no-dry-run` names a door target; without them the verb refuses before reading a file. A dry run needs neither.
- A rebuilt file is written as `WriterIdentity(run_id=RUN_ID, attempt=1, job=ServerJob.MIGRATE, shard=0, producer="telemetry.prune", git_sha=SHA)`.
- New module `backend/idhazh/ledger/day_removal.py`. Its first sentence: "Which door files hold a range of days, and each one rebuilt without them."

```python
class HeldFile(NamedTuple):
    path: Path
    tier: Tier
    period: Period | None
    covers: str
    days: tuple[str, ...]


def find_holding_files(state_dir: Path, ledger: LedgerName, days: Collection[str]) -> list[HeldFile]: ...


def rebuild_without(
    state_dir: Path, held: HeldFile, days: Collection[str], *, identity: WriterIdentity
) -> PeriodFile: ...
```

- `Tier` and `Period` are the enums in `backend/idhazh/contracts/file_envelope.py`, and `PeriodFile` is the class in `backend/idhazh/ledger/persist.py`. `rebuild_without` builds the replacement and writes nothing; the verb writes it, only on a live pass, with the atomic write the compaction uses. Both functions are exported from `backend/idhazh/ledger/__init__.py`.
- A member is a day. `--max-deletes` caps the days a pass takes, oldest first, and defaults to every day the range names, as it does for a CSV target. `resume_from` is the first day in the range the pass did not take, and `kept` is the days it saw that the range did not hold.
- For the days it takes, a live pass first deletes their raw day folders and their listings under `state/raw/<prefix>/index/`; then rebuilds each daily, monthly and yearly file that holds one of them, once, without their rows, writing an empty file when no row is left so that no index or watermark has a hole; and last rewrites each index it touched through the writer the compaction uses. Deletes go first because a rebuilt file no longer holds the day, so a listing left behind by a pass cut short after its rebuilds would never be selected again. A dry run lists the same paths and writes nothing.
- A pass cut short by its ceiling or by a failure is finished by running the same command again: a rebuilt file no longer holds the day, and a deleted folder is not listed.
- `Outcome` gains `rewritten: tuple[str, ...]`, the POSIX paths of rebuilt files. `removed` still means deleted files, and `bytes_freed` is the bytes of the deleted files plus what each rebuilt file shrank by.

### 2.9 The guard and the table tests

Row 1. New file `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`. "A door ledger" below means a ledger the registry files as `raw-and-compact`. Every test reads the committed `config/ledgers.json` and `config/gardener/`, never a fixture garden, which holds declarations the committed config does not.

| Test | Holds |
| --- | --- |
| `test_a_door_ledger_has_no_csv_shape` | no door ledger is in `_TREE_SHAPES` or `DAY_TREES` |
| `test_a_door_ledger_takes_no_union_driver` | no door ledger's `state/<prefix>` is in `path_classes.UNION_SAFE` |
| `test_a_door_ledger_is_not_a_csv_prune_target` | no door ledger is in `_TARGET_LEDGERS` of `backend/idhazh/telemetry/prune.py` |
| `test_a_compaction_and_a_door_ledger_come_together` | every door ledger has `config/gardener/compact-<ledger>.json`, and every compaction names a door ledger |
| `test_every_folder_a_declaration_owns_is_one_the_registry_builds` | every `owns` path under `state/` of every declaration is `state/<prefix>` of a CSV ledger, or `state/raw/<prefix>` or `state/compact/<prefix>` of a door ledger |
| `test_every_door_key_names_fields_its_contract_declares` | for every `_DOOR_SHAPES` entry, the key is a subset of the model's fields, and `arrow_schema.columns_of(model)` maps every field |
| `test_every_door_field_with_an_envelope_name_is_listed` | `ENVELOPE_NAMED_FIELDS: Final[Mapping[LedgerName, frozenset[str]]]`, a table written in the test file, equals for every `_DOOR_SHAPES` model its fields whose names are in `_KEYS`, so a door ledger whose field reuses an envelope name is a line somebody writes on purpose |

In `backend/tests/ledger/test_migrate_to_parquet.py`, which builds every CSV tree it reads under `tmp_path` and names its own fixture ledgers rather than looping over the whole table:

| Test | Holds |
| --- | --- |
| `test_every_unmoved_table_entry_is_the_registry_entry` | for each `CSV_LEDGERS` ledger that is not a door ledger, `old_entry` equals its registry entry |
| `test_every_moved_ledger_keeps_its_old_window` | for each that is, the committed `compact-<ledger>` passes `compaction_reaches(policy, old_window)` |
| `test_a_ledger_still_on_csv_is_refused` | a run naming a ledger that is not a door ledger exits 1 and writes nothing |
| `test_check_reads_moved_ledgers_unless_named` | `--check` with no `--ledger` reads door ledgers only |
| `test_a_shared_day_file_moves_cell_for_cell` | row 2: a `day` layout under two roots moves cell for cell, and the second root is filed raw only |

`backend/tests/ledger/test_ledger_files.py` takes `LedgerName.CONTENT_SIMILARITY_JUDGE_HOLDOUT_PAIRS` as its example of a ledger the door refuses, because `seen` gains a door entry in row 1; that ledger stays CSV by decision.

### 2.10 A ledger is moved when every part holds

Row 2 copies this table into `docs/how-to/move-a-ledger-to-parquet.md`, and from then on that page owns it.

| # | Part | Moved when | Held by |
| --- | --- | --- | --- |
| 1 | Registry | its entry is the one in section 2.2 | `backend/tests/contracts/test_ledger_registry.py` |
| 2 | Door table | `_DOOR_SHAPES` holds its entry from section 2.1, and neither `_TREE_SHAPES` nor `DAY_TREES` names it | section 2.9 |
| 3 | Writers | every writer files through `ledger.persist` with its identity from section 2.4, and every workflow step that runs a writing verb passes `--commit` | `backend/tests/workflows/test_ledger_door_jobs.py` |
| 4 | Backend readers | each reads as section 2.5 says, with the same signature and answer | the row's oracle |
| 5 | Console readers | where a console page reads it, it reads as section 2.5 says, and the ledger is in `LEDGER_NAMES` | `backend/tests/contracts/test_frontend_index_shapes.py` |
| 6 | Compaction | its declaration is the one in section 2.3 | `config.load_gardener()`, and section 2.9 |
| 7 | Migration | every committed CSV day, in `state/` and every trial root, reads back cell for cell before any CSV file is deleted, and `--check` exits 0 | section 2.6 |
| 8 | Retention | its retention declaration, its task module and their tests are deleted | section 2.9 |
| 9 | Union | a union ledger's `.gitattributes` line and its `UNION_SAFE` entry are deleted | section 2.9, and `backend/tests/workflows/test_daily_commit_steps.py` |
| 10 | Prune | the prune verb reaches it as section 2.8 says, and the declarations' `prune_refusal` keeps `seen` and `published` refused | section 2.8's tests |
| 11 | CSV code, tests and docs | section 3 step 1's search finds no line that still describes the ledger's CSV | the row's owner, before the pull request |
| 12 | Packing | its compaction packs live with its window reporting, the migration commit packs every period its declaration admits, and the first upkeep wake after the merge packs without a failure | section 2.11, and the owner's reading of that wake as plan 57 section 2 reads a switch |

### 2.11 Packing, and every setting in the declaration

Packing is the compaction pass in `backend/idhazh/gardener/tasks/compaction.py`. It takes each finished raw day into a daily file (`_daily_period.py`). Once `daily_keep_days` have passed since a month ended, it absorbs that month's daily files into one month file (`_monthly_period.py`). Where `monthly_keep_days` is set, it packs each finished year's month files into one year file that many days after the year ends (`_yearly_period.py`). Each step deletes only files whose rows it has already written into the coarser file. A `monthly_window` is different: it drops month files, and raw days, older than it keeps, and that deletes rows.

**Two switches.** Row 8 adds `monthly_window_dry_run: bool` to `CompactionPolicy` in `backend/idhazh/contracts/knobs/gardener.py`. With `dry_run` false and `monthly_window_dry_run` true, a pass packs live and only reports the drops its `monthly_window` would make: it keeps those month files and raw days, and packs them like any other. With both false, a pass does what a live pass does today. With `dry_run` true, it changes nothing, as today. Raw listings past `raw_index_keep_days` stay with `dry_run`, because their rows are already in daily files.

**The record keeps its fields.** A pass with its window reporting records `dry_run` false. `selected` counts every file it would delete with its window live, and `deleted` the files it deleted, so `selected` minus `deleted` is what the window would take. `CollectionPruneRow` gains no field and no meaning.

**Every setting is in the declaration.** Row 8 removes every default from `CompactionPolicy`, and the `DEFAULT_` constants that only those defaults read, so the loader refuses a compaction declaration that omits a key and names the key (CLAUDE.md Guardrail #3, owner ruling 2026-09-21). Every committed compaction declaration, and the two under `tests/fixtures/gardener/`, then writes each key with the value it runs with today:

| # | Key | What it sets | Value row 8 writes into each declaration on main |
| --- | --- | --- | --- |
| 1 | `dry_run` | whether a pass changes files | as declared |
| 2 | `monthly_window_dry_run` | new: whether a live pass only reports its window's drops | `false`, so a `dry_run` turned `false` later means what it means today |
| 3 | `raw_index_keep_days` | how long a raw day's listing outlives the day | 90 |
| 4 | `daily_keep_days` | how long after a month ends it waits in daily files | 45; 31 for `item-health` and `host-fingerprint`, by #1177 |
| 5 | `monthly_window` | how long a month file is kept once its month is absorbed | as declared; 13 months in `compact-gardener` and `compact-visual-prunes`, which omit it today |
| 6 | `monthly_keep_days` | how long after a year ends its month files wait before one year file takes them; `null` packs no year | `null`; 93 for `summary-quality-evals` |
| 7 | `max_periods_per_run` | the most days, and separately months and years, one pass packs | 8 |
| 8 | `max_raw_files_per_period` | the most raw files one period is built from in one pass | 2000 |
| 9 | `compact_after_days` | how many whole days after a day ends it may be packed | 1 |
| 10 | `prune_refusal` | new in row 3: `null` lets `idhazh telemetry prune` take days; a sentence refuses the ledger with it | `null`; a sentence for `summary-quality-evals` (2.8) |
| 11 | `window` and `max_deletes_per_run` | fixed by the model: `forever` and `null` | unchanged |

**A year file only for a ledger kept for ever.** The loader refuses `monthly_keep_days` beside a `monthly_window` that is not forever (`_a_year_packs_every_month_it_holds`), because a year file cannot give back one month when the window reaches it. So `summary-quality-evals`, `candidate-models` and `published` pack years, and every other door ledger packs days and months. Every ledger's rows are from 2026, so the first year file can be written on 2027-04-04, 93 days after 2026 ends. Until then year packing is proven on fixtures, in `backend/tests/gardener/tasks/test_compaction_years.py` and the migrator's tests.

**Who turns each door ledger's packing live:**

| # | Ledger | Packs | Packing live by | Its window |
| --- | --- | --- | --- | --- |
| 1 | `item-health` | days, months | completed packing change #1177 | 15 months, live by that change |
| 2 | `host-fingerprint` | days, months | completed packing change #1177 | 14 months, live by that change |
| 3 | `summary-quality-evals` | days, months, years | plan 57's row "The eval ledger is packed live, and every scores window stays forever"; row 2 packs what is due before then | forever: drops nothing |
| 4 | `gardener`, `visual-prunes` and `feed-retirements` | days, months | plan 57's row "The upkeep record, the picture cleanup's record and the feed retirements are packed live" | 13, 13 and 60 months, as that row turns them |
| 5 | `counterfactual-scores` | days, months | row 4 | 1 month, reporting |
| 6 | `candidate-models` | days, months, years | row 4 | forever |
| 7 | `seen` | days, months | row 5 | 2 months, reporting |
| 8 | `published` | days, months, years | row 5 | forever |
| 9 | `feed-health` | days, months | row 6 | 14 months, reporting |

Row 2 packs `item-health`, `host-fingerprint` and `summary-quality-evals` once, through the migrator (2.6), so the months the three moved before this plan hold are packed whichever switch lands first.

## 3. How a move lands, and the rows

1. **The search.** At dispatch and again before the pull request, the row's owner runs `git grep -l -E "<pattern>" -- . ":!state" ":!corpus" ":!TODO" ":!docs/archive"` with the row's search pattern and reads every file it finds. A line that still describes the ledger's CSV - its path, layout, union driver, retention task, fold or CSV reader - is changed or deleted. A line that only names the ledger - its `LedgerName` member, its row contract, its key, its knobs - stays. Each row's `Files touched` is what that search on main, as of 2026-10-01, showed the row must edit, with the files its scope names, creates or deletes; the owner adds what main has added since.
2. **Two commits.** A ledger row's pull request carries its code commit, then a migration commit made by section 2.6's command for the row's ledgers over `state` and every trial root that holds them. The owner makes the migration commit last: in the quiet window of step 3, after the final merge from main. CI runs on that commit. Reverting a row reverts both.
3. **Merge window.** The owner reads the run list (`gh run list --repo miztiik/yen-idhazh --status queued`, then `--status in_progress`) before the migration commit and again just before the merge, and merges only when both reads show no run of `digest.yml`, `idhazh-gardener.yml`, `idhazh-pipeline-tests.yaml`, `validate.yml` or `measure.yml`. A run checks out the commit it was created at, so one that runs across the merge writes CSV the migration did not see. A run seen at the second read is waited out; the owner then merges main into the branch, runs the migrator again with the row's `RUN_ID` (section 2.6), commits what it moved, pushes, and reads the list again once CI is green.
4. **After the merge.** At the next quiet window the owner runs `--check` over `state` and every trial root on main. A row is `DONE` at its merge; a CSV file `--check` names afterwards reopens it, and a follow-up pull request under the same row migrates that file with the row's `RUN_ID`.
5. **The pool.** Two slots, refilled as soon as a worker returns. A ready row is held while a row in flight lists one of its files, and the owner diffs the two `Files touched` lists at dispatch rather than trusting the pairing in section 1.

### Row #1 - Every shape the moves need is declared, and a guard holds each moved ledger to it

- **Scope:** lands sections 2.1, 2.6 (the table, the refusals, the raw-only rule for a root other than `<repo>/state`, a repeating `--ledger` and the default of `--check`), 2.7 and 2.9, and deletes `config/gardener/host-fingerprint.json`. The migrator's paragraph in `docs/architecture/contracts/persistence.md` and its line in `docs/concepts/growing-reads.md` then name the table, every root it is given and its removal condition from section 2.6, so row 2 does not edit the second page. No ledger moves and no committed data changes.
- **Precondition:** plan 56's row "The eval ledger becomes `summary-quality-evals`" is DONE (#1179, 2026-10-01). It rewrote the keys, the loader, the migrator, the prune verb and the tests this row edits. The completed packing change #1177 and this row share two tests and two docs - `backend/tests/contracts/test_gardener_config.py`, `backend/tests/ledger/test_ledger_files.py`, `docs/concepts/config/idhazh-gardener.md` and `docs/concepts/config/retention-ages.md` - and this row takes the merged change first.
- **Search pattern:** `_WINDOW_FLOORS|_CONSOLE_READS|_MACHINE_SOURCE_TASK|_old_tree_floor|gardener/host-fingerprint|host-fingerprint\.json|host_fingerprint_keep_months|_DOOR_SHAPES|_DoorShape|migrate_to_parquet|door_key\(LedgerName\.SEEN`.
- **Files touched:** `backend/idhazh/ledger/keys.py`; `backend/idhazh/ledger/arrow_schema.py`; `backend/idhazh/config.py`; `backend/idhazh/contracts/knobs/observability.py`; `backend/utilities/migrate_to_parquet.py`; `config/gardener/host-fingerprint.json` (deleted); `backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py` (new); `backend/tests/contracts/test_gardener_config.py`; `backend/tests/contracts/test_retention_knobs.py`; `backend/tests/gardener/tasks/test_every_window_moved_unchanged.py`; `backend/tests/ledger/test_arrow_schema.py`; `backend/tests/ledger/test_ledger_files.py`; `backend/tests/ledger/test_migrate_to_parquet.py`; `backend/tests/test_ledger.py`; `tests/fixtures/gardener/prune-oracle/removals.json`; `docs/architecture/contracts/ledger-registry.md`; `docs/architecture/contracts/persistence.md`; `docs/concepts/adaptive-pruning.md`; `docs/concepts/config/retention-ages.md`; `docs/concepts/config/idhazh-gardener.md`; `docs/concepts/growing-reads.md`; this plan's Reckoner line.
- **Acceptance gates:** local: the checks `npm --prefix frontend run test:changed -- --list` selects, which include `pytest backend/tests/contracts/ backend/tests/ledger/ backend/tests/test_ledger.py backend/tests/gardener/tasks/test_every_window_moved_unchanged.py`, with ruff and mypy as `docs/how-to/run-the-gates.md` names them, and `python backend/utilities/doc_load.py` with all touched Markdown paths passed as arguments, before and after. The worker records the selector's list and each result. CI: the full suite.
- **Oracle:** every test in section 2.9 passes; `config.load_gardener()` loads the committed declarations and the fixture garden under `tests/fixtures/gardener/garden/`; and the ownership test fails at the parent commit on `config/gardener/host-fingerprint.json`, which owns `state/host-fingerprint`, a folder the registry no longer builds. It cannot settle a ledger's own readers and writers; each ledger row's oracle does.
- **Merge window:** none; the row changes no committed data.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One pull request lands every shared shape before any ledger moves, so a ledger row edits only the lines that must change with its grain | Fowler, 2026-10-01 |
| 2 | The registry grain is the only switch, and every rule that depends on a move reads it | Fowler, 2026-10-01 |
| 3 | `seen` and `published` take keys that only exact copies share, and no preference. In the committed CSV no `seen` address repeats within a day, and every one of the 3,143 `published` rows that repeat a whole key within a day is an exact copy | Fowler, 2026-10-01, counted over the committed CSV; it withdraws the per-ledger preference ruled on 2026-09-30. Recounted by the owner at dispatch, 2026-10-01, by the whole key; the figure first written was 3,050 exact copies of 3,052 repeats |
| 4 | The old-window table lives in the migrator, and its test reads the committed declarations on every pull request | Fowler, 2026-10-01 |
| 5 | Floors are keyed by ledger and read from the governing declaration, and a ledger that none governs meets every floor | Fowler, 2026-10-01 |
| 6 | The guard is a pytest test built from the registry; the check that no CSV file is left stays in `--check` | Fowler, 2026-09-30 |
| 7 | Row 1 no longer waits for packing change #1177. With the rename merged they share two tests and two docs, and the lines both would write - the compaction settings - are row 8's | Plan owner, 2026-10-01 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | A preference on each door ledger | The keys in section 2.1 settle both union ledgers with the door's own rule | A `_DoorShape` field, a branch in `settle_rows` and in the daily packing step, and their tests, with no reader that needs them | Fowler, 2026-10-01 |
| 2 | The old-window table in `backend/idhazh/ledger/`, read by the loader too | The move is its only consumer, and its test already gates every pull request | A module in the ledger package and a loader rule, both deleted again when the last ledger moves | Fowler, 2026-10-01 |
| 3 | Refuse a floor whose declaration is missing | The fixture gardens hold fewer declarations than `config/gardener/` | Declarations added to every fixture garden that do not test anything | Fowler, 2026-10-01 |
| 4 | A `csv_source` block on each registry entry | It writes a fact about the past into the file that says what a ledger is now | A registry field and its contract test, kept until the last ledger moves | Fowler, 2026-09-30 |
| 5 | A test that scans the frontend for CSV paths | Section 3 step 1 searches the frontend in every ledger row | A second test over Svelte and TypeScript source, and its upkeep | Fowler, 2026-09-30 |
| 6 | One declarations pull request for each ledger | Each would edit the same key, loader and test lines, one after another | Four more rebases over the same lines, and four more CI runs | Fowler, 2026-10-01 |

### Row #2 - The migrator reads both CSV layouts in every root, packs every period, and the recipe is written down

- **Scope:** adds section 2.6's `day` layout, repeated `--state-dir`, and packing of every period with the compaction's own pass; files the CSV that `item-health` and `host-fingerprint` left in the trial roots, raw only, and deletes it; packs `item-health`, `host-fingerprint` and `summary-quality-evals` in `state/` through the migrator, in its migration commit; writes `docs/how-to/move-a-ledger-to-parquet.md`, which carries section 2.10 and section 3 for every later ledger, and links it from `docs/architecture/contracts/persistence.md`.
- **Precondition:** rows 1, 3 and 8 are DONE. Packing change #1177 has merged, and its first upkeep wake must have packed `item-health` and `host-fingerprint` live with no failure, read as plan 57 section 2 reads a switch: the person ruled that the first live packing is read on those two ledgers before more follow.
- **Search pattern:** `migrate_to_parquet|move-a-ledger-to-parquet|_pack\(|PACK_EVERY_DAY`.
- **Files touched:** `backend/utilities/migrate_to_parquet.py`; `backend/tests/ledger/test_migrate_to_parquet.py`; `docs/how-to/move-a-ledger-to-parquet.md` (new); `docs/architecture/contracts/persistence.md`; `state/raw/item-health/`, `state/compact/item-health/`, `state/raw/host-fingerprint/`, `state/compact/host-fingerprint/`, `state/raw/summary-quality-evals/` and `state/compact/summary-quality-evals/` (packed); `state/pipeline-tests/host-fingerprint/` (deleted); `state/pipeline-tests/raw/host-fingerprint/` (new); `state/pipeline-tests-no-visual-plan/item-health/` (deleted); `state/pipeline-tests-no-visual-plan/raw/item-health/` (new); `state/pipeline-tests-production-settings/item-health/` (deleted); `state/pipeline-tests-production-settings/raw/item-health/` (new); this plan's Reckoner line.
- **Acceptance gates:** local: the selected checks, which include `pytest backend/tests/ledger/test_migrate_to_parquet.py`; after the migration commit, `--check --ledger item-health --ledger host-fingerprint` over `state`, `state/pipeline-tests`, `state/pipeline-tests-no-visual-plan` and `state/pipeline-tests-production-settings` exits 0; a dry pass of each compaction of the three ledgers row 2 packs has nothing left to pack at that commit; `doc_load.py` with all touched Markdown paths passed as arguments, as in row 1. CI: the full suite.
- **Oracle:** for every leftover day, `load_days` over the new raw files returns the rows the CSV reader returned at the parent commit, cell for cell after settling, and `test_a_shared_day_file_moves_cell_for_cell` proves the `day` layout. For each of the three ledgers it packs, `load_days` over every day it holds returns the same rows at the migration commit as at its parent. A fixture test packs a finished year of a ledger kept for ever into one year file, through the migrator. It cannot settle a month, flat or stamp layout; the batch that needs one adds it. It cannot settle a real year file before 2027-04-04 (section 2.11).
- **Merge window:** section 3 step 3. Nothing writes the two ledgers' CSV any more, but the packing writes files that the upkeep's live compactions of `item-health` and `host-fingerprint` write too.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A trial root is filed raw and never packed: nothing reads a packed trial root, and the trials task empties the root | Fowler, 2026-09-30 |
| 2 | Two layouts only; every other grain is refused by name until a ledger needs it | Fowler, 2026-09-30 |
| 3 | Row 2 waits for row 3 although it reads nothing row 3 writes, so the two are never in flight on touching Reckoner lines | Plan author, 2026-10-01 |
| 4 | The migrator packs with the compaction's own pass rather than a copy of its steps, so a file the migrator packs is the file the upkeep would write | The person, 2026-10-01: packing by month and by year in the migrator |
| 5 | Row 2 packs the three ledgers moved before this plan, after the first live wake of #1177 is read | The person, 2026-10-01; the order is the person's ruling of 2026-09-30 in plan 57 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | One migrator for each ledger | Each copy repeats reading, proving and deleting | One copy of the prove-then-delete path, and its tests, for each ledger | Fowler, 2026-09-30 |
| 2 | Pack the trial roots too | Decision 1 | Packed files and indexes in folders nothing reads, and a rule in the trials task for them | Fowler, 2026-09-30 |
| 3 | Pack only days, as main's migrator does | The person asked for months and years | Month files only from each compaction's own switch, and none for a ledger whose packing stays report-only | The person, 2026-10-01 |

### Row #3 - The prune verb reaches every ledger on the door

- **Scope:** section 2.8, with the `prune_refusal` key in `CompactionPolicy` and in every compaction declaration.
- **Precondition:** plan 56's row "The eval ledger becomes `summary-quality-evals`" is DONE (#1179, 2026-10-01).
- **Search pattern:** `_TARGET_LEDGERS|prune\.REFUSED|WRITER_OWNED_LEDGERS|prune_range|telemetry prune|prune_refusal`.
- **Files touched:** `backend/idhazh/telemetry/prune.py`; `backend/idhazh/telemetry/cli.py`, which hands `--run-id` and `--commit` to `prune_range`; `backend/idhazh/contracts/knobs/gardener.py`; the six `config/gardener/compact-*.json` on main and the two under `tests/fixtures/gardener/`; `backend/idhazh/ledger/day_removal.py` (new); `backend/idhazh/ledger/__init__.py`; `backend/tests/retention/test_prune_range.py`; `backend/tests/ledger/test_day_removal.py` (new); `backend/tests/workflows/test_telemetry_cli.py`; `docs/how-to/prune-a-collection.md`; `docs/architecture/publishing/retention.md`; this plan's Reckoner line.
- **Acceptance gates:** local: the selected checks, which include `pytest backend/tests/retention/test_prune_range.py backend/tests/ledger/test_day_removal.py backend/tests/workflows/test_telemetry_cli.py`; `doc_load.py` with all touched Markdown paths passed as arguments, as in row 1. CI: the full suite.
- **Oracle:** on a ledger built under `tmp_path` through the door, with raw, daily and monthly files, pruning a range leaves `load_days` returning no row for the pruned days and the same rows for every other day, and every index and watermark loads. Today the verb refuses `item-health` as a target it does not know. After the row it takes days from `item-health`, and refuses `summary-quality-evals` with its declaration's sentence. It cannot settle a live prune of committed rows, which stays a person's `--no-dry-run`.
- **Merge window:** none; the row changes no committed data.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | One verb prunes both kinds of ledger (CLAUDE.md section 1b) | Fowler, 2026-09-30 |
| 2 | A period whose rows all go stays as an empty file | Fowler, 2026-09-30 |
| 3 | A rebuilt file is written as job `migrate` with producer `telemetry.prune`, and a live pass needs `--run-id` and `--commit` | Fowler, 2026-10-01 |
| 4 | A door ledger's refusal is its declaration's `prune_refusal`, beside its windows, and `REFUSED` keeps only the ledgers no compaction declares | The person, 2026-10-01: prune settings in JSON |
| 5 | `summary-quality-evals` is refused: every eval row is kept for ever | Plan 56, ruling R1 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Leave door ledgers out of the verb | Every moved ledger leaves it, and CLAUDE.md section 1b asks for one prune verb | A bad day in a moved ledger can go only by a hand-written rewrite of its parquet files | Fowler, 2026-09-30 |
| 2 | Delete a whole packed file that holds a pruned day | It deletes every other day in that file | Every row of the month around a pruned day | Fowler, 2026-09-30 |
| 3 | A new `ServerJob` member for the prune | It changes a persisted vocabulary (ESCALATE trigger 4) | A Level 5 change for a label nothing groups by | Fowler, 2026-10-01 |

### Row #4 - The counterfactual scores and the candidate verdicts move to the door

- **Scope:** `counterfactual-scores` and `candidate-models` meet every part of section 2.10: their registry entries (2.2), compactions (2.3: packing live, each `dry_run` with its `LIVE_BY_DECISION` line, the window reporting), writers and the `--commit` on "Run the gates" (2.4). Their `_TREE_SHAPES` and `DAY_TREES` lines go; `counterfactual-scores` leaves `_TARGET_LEDGERS`; its `fold.dry_run` line in `LIVE_BY_DECISION` and the `candidate-models` line in `UNFOLDED_BY_DECISION` go; `config/gardener/counterfactual-scores.json`, `backend/idhazh/gardener/tasks/counterfactual_scores.py` and `backend/tests/gardener/tasks/test_counterfactual_scores_task.py` are deleted. The migration commit moves `state/counterfactual-scores/`; `candidate-models` has no committed CSV, and `--check` confirms it.
- **Precondition:** rows 1, 3 and 8 are DONE.
- **Search pattern:** `counterfactual-scores|COUNTERFACTUAL_SCORES|CounterfactualScoreRow|counterfactual_scores|candidate-models|LedgerName\.CANDIDATE_MODELS|ValidationRow|stage_qualify_decide`.
- **Files touched:** `.github/workflows/validate.yml`; `backend/idhazh/cli.py`; `backend/idhazh/contracts/__init__.py`; `backend/idhazh/contracts/base.py`; `backend/idhazh/contracts/counterfactual_score.py`; `backend/idhazh/contracts/knobs/placement.py`; `backend/idhazh/contracts/ledger_name.py`; `backend/idhazh/contracts/validation_row.py`; `backend/idhazh/evals/validation.py`; `backend/idhazh/gardener/tasks/counterfactual_scores.py` (deleted); `backend/idhazh/ledger/keys.py`; `backend/idhazh/ledger/settle.py`; `backend/idhazh/stages/decide.py`; `backend/idhazh/stages/plan.py`; `backend/idhazh/stages/qualify_decide.py`; `backend/idhazh/telemetry/prune.py`; `config/ledgers.json`; `config/gardener/counterfactual-scores.json` (deleted); `config/gardener/compact-counterfactual-scores.json` (new); `config/gardener/compact-candidate-models.json` (new); `backend/tests/contracts/test_cell_shapes.py`; `backend/tests/contracts/test_gardener_config.py`; `backend/tests/contracts/test_ledger_registry.py`; `backend/tests/gardener/tasks/_oracle_tree.py`; `backend/tests/gardener/tasks/test_counterfactual_scores_task.py` (deleted); `backend/tests/gardener/tasks/test_every_window_moved_unchanged.py`; `backend/tests/ledger/test_lifecycle.py`; `backend/tests/pipeline/test_day_shards.py`; `backend/tests/retention/test_prune_range.py`; `backend/tests/test_ledger.py`; `backend/tests/test_rank.py`; `backend/tests/test_validation.py`; `backend/tests/workflows/test_validation_state_root.py`; `backend/tests/workflows/test_worker_ledgers.py`; `tests/fixtures/gardener/prune-oracle/removals.json`; `docs/architecture/contracts/ledger-registry.md`; `docs/architecture/contracts/schemas.md`; `docs/architecture/publishing/idhazh-gardener.md`; `docs/concepts/adaptive-pruning.md`; `docs/concepts/config/idhazh-gardener.md`; `docs/concepts/config/retention-ages.md`; `docs/concepts/growing-reads.md`; `docs/concepts/partitions.md`; `docs/how-to/test-models-locally.md`; `docs/reference/repository-layout.md`; `state/counterfactual-scores/` (deleted); `state/raw/counterfactual-scores/` (new); this plan's Reckoner line.
- **Acceptance gates:** local: the selected checks, which include `pytest backend/tests/test_rank.py backend/tests/test_validation.py backend/tests/workflows/test_validation_state_root.py backend/tests/workflows/test_ledger_door_jobs.py backend/tests/contracts/test_gardener_config.py backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py backend/tests/ledger/test_migrate_to_parquet.py`; `--check --ledger counterfactual-scores --ledger candidate-models` over every root; `doc_load.py` with all touched Markdown paths passed as arguments, as in row 1. CI: the full suite.
- **Oracle:** for every committed day, `load_days` of `counterfactual-scores` at the migration commit returns the rows the CSV reader returned at its parent, cell for cell, and `--check` exits 0 for both ledgers over every root. It cannot settle the lens tuning that will read these scores, which does not exist yet; the `lens_weights.window_days` floor keeps the window that tuning will need.
- **Merge window:** section 3 step 3. The first scheduled upkeep wake after the merge is read as plan 57 section 2 reads a switch.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | These two move first: no reader depends on either, so a fault shows in the migration's read-back, not on a page or in a digest | Fowler, 2026-09-30 |
| 2 | The arrow mapper grows only by what these ledgers need; `Literal` fields stay refused until a ledger in the second batch needs them | Plan author, 2026-09-30 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Map `Literal` fields in the arrow mapper now | No ledger in this plan has one | A mapping and its tests with no user until the second batch | Plan author, 2026-09-30 |

### Row #5 - The seen and published ledgers move to the door, and their union drivers retire

- **Scope:** `seen` and `published` meet every part of section 2.10: their registry entries (2.2), compactions (2.3: packing live, the windows reporting, `compact-published` packing years), writers (2.4) and readers (2.5). `.gitattributes` loses `state/published/**/*.csv text eol=lf merge=union` and `state/seen/**/*.csv text eol=lf merge=union` with their comments, and `UNION_SAFE` loses `state/published` and `state/seen`. These are deleted: `config/gardener/seen.json`, `backend/idhazh/gardener/tasks/seen.py` and `backend/tests/gardener/tasks/test_seen_task.py`; `backend/utilities/split_published_ledger.py` and `backend/utilities/migrate_published_ledger.py`, one-shot rewrites of files that no longer exist; and `backend/utilities/measure_day_window.py`, the benchmark of the move from month files to day files, whose record stays in `docs/reference/benchmarks/day-window-read.md`. `backend/utilities/migrate_to_day_shards.py` and its test lose their `seen` case, or go whole if `seen` was its last ledger. The two refusal sentences move from `REFUSED` into the two declarations' `prune_refusal`, so the prune verb still refuses both.
- **Precondition:** rows 2 and 4 are DONE, and the person has answered section 4 decisions 1 and 4.
- **Search pattern:** `LedgerName\.SEEN|append_seen|load_seen|state/seen|SeenRow|seen_window_days|tasks\.seen|tasks/seen|seen\.json|test_seen|LedgerName\.PUBLISHED|append_published|load_published|state/published|PublishedRow|published_window_days|split_published_ledger|migrate_published_ledger|measure_day_window`.
- **Files touched:** `.gitattributes`; `.github/workflows/digest.yml`; `backend/idhazh/contracts/__init__.py`; `backend/idhazh/contracts/base.py`; `backend/idhazh/contracts/digest_day.py`; `backend/idhazh/contracts/knobs/collect.py`; `backend/idhazh/contracts/run_plan.py`; `backend/idhazh/contracts/seen.py`; `backend/idhazh/day_partition.py`; `backend/idhazh/day_shards.py`; `backend/idhazh/gardener/tasks/seen.py` (deleted); `backend/idhazh/ledger/__init__.py`; `backend/idhazh/ledger/csv_file.py`; `backend/idhazh/ledger/rows.py`; `backend/idhazh/ledger/settle.py`; `backend/idhazh/month_partition.py`; `backend/idhazh/path_classes.py`; `backend/idhazh/stages/assemble.py`; `backend/idhazh/stages/plan.py`; `backend/idhazh/telemetry/prune.py`; `backend/utilities/measure_day_window.py` (deleted); `backend/utilities/migrate_published_ledger.py` (deleted); `backend/utilities/split_published_ledger.py` (deleted); `backend/utilities/migrate_to_day_shards.py`; `backend/utilities/reconcile_prefill.py`; `config/idhazh.json`; `config/ledgers.json`; `config/gardener/seen.json` (deleted); `config/gardener/compact-seen.json` (new); `config/gardener/compact-published.json` (new); `backend/tests/contracts/test_gardener_config.py`; `backend/tests/contracts/test_ledger_package.py`; `backend/tests/contracts/test_ledger_registry.py`; `backend/tests/contracts/test_retention_knobs.py`; `backend/tests/gardener/tasks/_oracle_tree.py`; `backend/tests/gardener/tasks/test_every_window_moved_unchanged.py`; `backend/tests/gardener/tasks/test_seen_task.py` (deleted); `backend/tests/gardener/test_file_listing.py`; `backend/tests/gardener/test_named_trees.py`; `backend/tests/gardener/test_publish.py`; `backend/tests/ledger/test_ledger_files.py`; `backend/tests/ledger/test_lifecycle.py`; `backend/tests/pipeline/test_day_shards.py`; `backend/tests/pipeline/test_publication_registry.py`; `backend/tests/pipeline/test_publish_window.py`; `backend/tests/retention/test_seen_days.py`; `backend/tests/retention/test_union_safe_repeats.py`; `backend/tests/test_day_partition.py`; `backend/tests/test_ledger.py`; `backend/tests/test_ledger_families.py`; `backend/tests/test_marks.py`; `backend/tests/test_migrate_to_day_shards.py`; `backend/tests/test_plan.py`; `backend/tests/test_widen_ledger_header.py`; `backend/tests/workflows/rebuild_day.py`; `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`; `backend/tests/workflows/test_commit_script.py`; `backend/tests/workflows/test_daily_commit_steps.py`; `backend/tests/workflows/test_telemetry_cli.py`; `backend/tests/workflows/test_worker_ledgers.py`; `tests/fixtures/contracts/app-config/every-knob-differs-from-the-committed-config.json`; `tests/fixtures/gardener/garden/seen.json`; `tests/fixtures/gardener/prune-oracle/removals.json`; `tests/fixtures/gardener/prune-oracle/windows.json`; `docs/architecture/contracts/ledger-registry.md`; `docs/architecture/contracts/schemas.md`; `docs/architecture/contracts/state-ledgers.md`; `docs/architecture/publishing/committing.md`; `docs/architecture/publishing/layout.md`; `docs/architecture/sources/discovery.md`; `docs/architecture/sources/freshness.md`; `docs/architecture/sources/item-health.md`; `docs/concepts/adaptive-pruning.md`; `docs/concepts/config/idhazh-gardener.md`; `docs/concepts/config/retention-ages.md`; `docs/concepts/evaluation.md`; `docs/concepts/glossary.md`; `docs/concepts/growing-reads.md`; `docs/concepts/partitions.md`; `docs/concepts/pipeline-loop.md`; `docs/how-to/run-the-pipeline.md`; `docs/reference/benchmarks/day-window-read.md`; `docs/reference/benchmarks/what-the-suite-costs.md`; `docs/reference/repository-layout.md`; `state/seen/` and `state/published/` (deleted); `state/raw/seen/` and `state/raw/published/` (new); this plan's Reckoner line.
- **Acceptance gates:** local: the selected checks, which include `pytest backend/tests/test_plan.py backend/tests/test_ledger.py backend/tests/ledger/ backend/tests/retention/ backend/tests/workflows/test_daily_commit_steps.py backend/tests/contracts/test_door_ledgers_keep_no_csv_path.py`, with `test_load_published_costs_the_answer_and_not_the_file` restated as "double the months held, and the peak stays flat"; `--check --ledger seen --ledger published` over every root; `doc_load.py` with all touched Markdown paths passed as arguments, as in row 1. CI: the full suite.
- **Oracle:** over the committed tree at the migration commit's parent, `load_seen` with the plan stage's window and `load_published` with `within_days` -1 give the same answer before and after the move: the same addresses, and for each the same earliest instant or day. It cannot settle a digest run that writes CSV inside the merge window; section 3 step 4 catches that.
- **Merge window:** section 3 step 3, and ESCALATE trigger 3. A run created before the merge that pushes after it cannot push at all: it appends to a day file of `seen` or `published` that main has deleted, `backend/utilities/commit_and_push.py` stops the push on that conflict, and the run's whole day goes uncommitted. The person ruled on 2026-10-02 that `digest.yml` keeps running (section 4 decision 4), so the owner keeps that gap to seconds: the second read of step 3 runs straight before `gh pr merge`, and a run it shows is waited out as step 3 says. A run created inside those seconds cannot push; nothing it wrote reaches main, and the articles it found stay unseen for the next run. The first scheduled upkeep wake after the merge is read as plan 57 section 2 reads a switch.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | A row with no `date` field is filed under its CSV file's day, so no row changes day | Fowler, 2026-09-30 |
| 2 | `load_published` reads a month at a time, so its peak memory is one month's rows whatever the history holds | Fowler, 2026-10-01 |
| 3 | `compact-published` keeps every month while the digest reads every published day | Fowler, 2026-09-30 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep `seen` and `published` on CSV, because every digest run reads them | Their risk is the read-back this row's oracle checks, and they are why the union driver exists | Two more CSV ledgers, with the union driver, its settle rules and their tests kept for them | Fowler, 2026-09-30 |
| 2 | File each `seen` row under the UTC day of its `first_seen_at` | It moves rows between days and changes what a window of named days reads | A second oracle over the moved rows, and a window read that differs from today's | Fowler, 2026-09-30 |
| 3 | Read every published day with `load_ledger_rows` | It holds every row at once, and `test_load_published_costs_the_answer_and_not_the_file` refuses that | A peak memory that grows with the history | Fowler, 2026-10-01 |

### Row #6 - Feed health moves to the door, and the Voices page reads it packed

- **Scope:** `feed-health` meets every part of section 2.10: its registry entry (2.2), its compaction (2.3: packing live with its `LIVE_BY_DECISION` entry, the 14-month window reporting), its writer and the canary's (2.4), and `load_health` and the console read (2.5). Its `_TREE_SHAPES` and `DAY_TREES` lines go; it leaves `_TARGET_LEDGERS`; its `fold.dry_run` line in `LIVE_BY_DECISION` goes; `config/gardener/feed-health.json`, `backend/idhazh/gardener/tasks/feed_health.py` and `backend/tests/gardener/tasks/test_feed_health_task.py` are deleted. `.gitignore` loses `frontend/static/feed-health/` if nothing writes that folder.
- **Precondition:** row 5 is DONE, and with it row 8 and the completed packing change #1177, whose indexes and daily packing the Voices page reads.
- **Search pattern:** `state/feed-health|LedgerName\.FEED_HEALTH|load_health|feedResults|FEED_HEALTH_RULE|gardener/feed-health|tasks/feed_health|tasks\.feed_health|test_feed_health_task|frontend/static/feed-health`, and the name `feed-health` in quotes or before a `/`.
- **Files touched:** `.gitattributes`; `.gitignore`; `backend/idhazh/contracts/feed_health.py`; `backend/idhazh/contracts/knobs/observability.py`; `backend/idhazh/contracts/ledger_name.py`; `backend/idhazh/contracts/source_health_view.py`; `backend/idhazh/discover.py`; `backend/idhazh/gardener/tasks/feed_health.py` (deleted); `backend/idhazh/ledger/__init__.py`; `backend/idhazh/ledger/keys.py`; `backend/idhazh/ledger/rows.py`; `backend/idhazh/ledger/settle.py`; `backend/idhazh/month_partition.py`; `backend/idhazh/path_classes.py`; `backend/idhazh/stages/plan.py`; `backend/idhazh/telemetry/prune.py`; `backend/idhazh/telemetry/publish/console_band.py`; `backend/idhazh/telemetry/publish/source_health.py`; `backend/idhazh/telemetry/source_health.py`; `backend/utilities/build_canary_day.py`; `config/ledgers.json`; `config/gardener/feed-health.json` (deleted); `config/gardener/compact-feed-health.json` (new); `frontend/src/lib/data/slice-shapes.ts`; `frontend/src/lib/feed-health.ts`; `frontend/src/lib/server/ledger-rows.ts`; `frontend/src/lib/server/payload.ts`; `frontend/src/routes/console/voices/+page.server.ts`; `backend/tests/conftest.py`; `backend/tests/contracts/test_frontend_index_shapes.py`; `backend/tests/contracts/test_gardener_config.py`; `backend/tests/contracts/test_ledger_registry.py`; `backend/tests/contracts/test_retention_knobs.py`; `backend/tests/contracts/test_two_call_ledgers.py`; `backend/tests/gardener/tasks/_oracle_tree.py`; `backend/tests/gardener/tasks/test_every_window_moved_unchanged.py`; `backend/tests/gardener/tasks/test_feed_health_task.py` (deleted); `backend/tests/gardener/test_closed_day_fold.py`; `backend/tests/gardener/test_fold_lands.py`; `backend/tests/gardener/test_named_trees.py`; `backend/tests/gardener/test_shards.py`; `backend/tests/ledger/test_lifecycle.py`; `backend/tests/pipeline/test_day_shards.py`; `backend/tests/retention/_trees.py`; `backend/tests/retention/test_prune_range.py`; `backend/tests/test_canary_packing.py`; `backend/tests/test_console_payloads_producer.py`; `backend/tests/test_discover.py`; `backend/tests/test_ledger.py`; `backend/tests/test_plan.py`; `backend/tests/test_publish_source_health.py`; `backend/tests/test_source_health.py`; `backend/tests/test_widen_ledger_header.py`; `backend/tests/workflows/test_a_trial_tree_may_hold_door_files.py`; `backend/tests/workflows/test_commit_script.py`; `backend/tests/workflows/test_daily_commit_steps.py`; `backend/tests/workflows/test_telemetry_cli.py`; `backend/tests/workflows/test_worker_ledgers.py`; `frontend/tests/console-voices-feeds.spec.ts`; `frontend/tests/console-window-claims.spec.ts`; `frontend/tests/console.spec.ts`; `tests/fixtures/contracts/collection-prune-row/a-live-fold-beside-a-dry-window.json`; `tests/fixtures/gardener/garden/feed-health.json`; `tests/fixtures/gardener/prune-oracle/removals.json`; `docs/architecture/contracts/ledger-registry.md`; `docs/architecture/contracts/schemas.md`; `docs/architecture/contracts/state-ledgers.md`; `docs/architecture/publishing/console-machine.md`; `docs/architecture/publishing/console-payloads.md`; `docs/architecture/publishing/who-supplied-the-day-and-which-feeds-failed.md`; `docs/architecture/sources/freshness.md`; `docs/architecture/sources/health.md`; `docs/architecture/sources/item-health.md`; `docs/concepts/adaptive-pruning.md`; `docs/concepts/config/idhazh-gardener.md`; `docs/concepts/config/retention-ages.md`; `docs/concepts/evaluation.md`; `docs/concepts/growing-reads.md`; `docs/concepts/partitions.md`; `docs/concepts/pipeline-loop.md`; `docs/how-to/run-the-pipeline.md`; `docs/reference/repository-layout.md`; `state/feed-health/` (deleted); `state/raw/feed-health/` (new); this plan's Reckoner line.
- **Acceptance gates:** local: the selected checks, which include `pytest backend/tests/test_source_health.py backend/tests/test_publish_source_health.py backend/tests/test_console_payloads_producer.py backend/tests/test_canary_packing.py backend/tests/test_plan.py`, the specs `frontend/tests/console-voices-feeds.spec.ts`, `frontend/tests/console-window-claims.spec.ts` and `frontend/tests/console.spec.ts`, and the browser smoke of `/console/voices` (CLAUDE.md section 12), with and without a packed feed file; `--check --ledger feed-health` over every root; `doc_load.py` with all touched Markdown paths passed as arguments, as in row 1. CI: the full suite.
- **Oracle:** for every committed day, `load_health` at the migration commit returns the rows it returned at the parent, and the Voices page draws the same feed rows for every day the packed files hold. It cannot settle the days after the newest packed day, which the page shows only after the next packing wake.
- **Merge window:** section 3 step 3. The first scheduled upkeep wake after the merge is read as plan 57 section 2 reads a switch.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The page shows days through the newest packed day, at most one upkeep wake behind the newest raw day, as the console's other packed ledgers do | Fowler, 2026-09-30 |
| 2 | Feed health moves last: it is the only one of the five a page reads | Fowler, 2026-09-30 |
| 3 | `monthly_window` keeps the window the retention declaration had; forever would be the person's call | Fowler, 2026-09-30 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Keep `feedResults` on CSV while the backend moves | The page would read files no writer writes | A Voices page frozen at the merge | Fowler, 2026-09-30 |
| 2 | Teach `sliceFromDisk` to read raw files in this row | The door's read tiers belong to plan 55's row "The door answers a written question, on the engine plan 51 shipped", which adds a tier for the writers' files | A second read path in the door, built twice | Fowler, 2026-09-30 |

### Row #7 - The map of the ledgers left on CSV is written, and the plan closes

- **Scope:** `--check` exits 0 over `state` and every trial root for every ledger in `CSV_LEDGERS`. Every door ledger's newest compaction record on main shows the packing section 2.11 says it runs, or names the plan row that turns it on. `docs/architecture/contracts/ledger-registry.md` carries the map of every ledger still on CSV with what blocks it, and each piece of shared CSV machinery with its removal condition, which is its last user leaving. The plan closes per `docs/how-to/execute-a-plan.md`.
- **Precondition:** row 6 is DONE.
- **Search pattern:** the search patterns of rows 4 to 6.
- **Files touched:** `docs/architecture/contracts/ledger-registry.md`; `docs/how-to/move-a-ledger-to-parquet.md`; `docs/architecture/contracts/persistence.md`; this plan-doc, closed per `docs/how-to/execute-a-plan.md`.
- **Acceptance gates:** local: `--check` over every root; `doc_load.py` with all touched Markdown paths passed as arguments. No application suite: the row changes documentation only.
- **Oracle:** the search for each of the five ledgers finds no line that still describes its CSV, and `--check` exits 0 for every ledger in the table. It cannot settle the ledgers left, which the map hands to the next batch.
- **Merge window:** none.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | The migrator stays until no ledger is left on CSV | Fowler, 2026-09-30 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Delete the migrator when this plan closes | Ledgers are still on CSV, and the next batch would write it again | The migrator, its table and its tests, written a second time | Fowler, 2026-09-30 |

### Row #8 - Every compaction declaration names every setting it runs with, and a window can report while packing runs live

- **Scope:** section 2.11's two switches, and every setting in the declaration. `CompactionPolicy` in `backend/idhazh/contracts/knobs/gardener.py` loses every default, the `DEFAULT_` constants that only those defaults read go, and it gains `monthly_window_dry_run`. `backend/idhazh/gardener/tasks/compaction.py` keeps and reports the drops its `monthly_window` would make while that key is `true`, and packs the periods they hold. Every compaction declaration on main, and both under `tests/fixtures/gardener/`, writes every key with the value it runs with today, and `monthly_window_dry_run` as `false`, so no pass changes. `LIVE_BY_DECISION` lists each live window - a compaction whose `dry_run` and `monthly_window_dry_run` are both `false` - with its reason; on main those are `compact-item-health` and `compact-host-fingerprint`, live by #1177. `docs/concepts/config/idhazh-gardener.md` then describes every key, `prune_refusal` included, which row 3 left to this row because rows 1 and 8 edit that page.
- **Precondition:** rows 1 and 3 are DONE, and packing change #1177 is complete. It wrote the `daily_keep_days` and `dry_run` lines of two of these declarations, and edited the packing steps the switch reads. Row 1 shares `backend/tests/contracts/test_gardener_config.py`, `docs/concepts/config/idhazh-gardener.md` and `docs/concepts/config/retention-ages.md` with this row, so the two run one after the other.
- **Search pattern:** `DEFAULT_RAW_INDEX_KEEP_DAYS|DEFAULT_DAILY_KEEP_DAYS|DEFAULT_MONTHLY_WINDOW_MONTHS|DEFAULT_MAX_PERIODS_PER_RUN|DEFAULT_MAX_RAW_FILES_PER_PERIOD|DEFAULT_COMPACT_AFTER_DAYS|_default_monthly_window|monthly_window_dry_run|"kind": "compaction"`.
- **Files touched:** `backend/idhazh/contracts/knobs/gardener.py`; `backend/idhazh/gardener/tasks/compaction.py`; `backend/idhazh/gardener/tasks/_daily_period.py` and `_monthly_period.py`, where a list of drops must be read without dropping; `config/gardener/compact-feed-retirements.json`; `config/gardener/compact-gardener.json`; `config/gardener/compact-host-fingerprint.json`; `config/gardener/compact-item-health.json`; `config/gardener/compact-summary-quality-evals.json`; `config/gardener/compact-visual-prunes.json`; `tests/fixtures/gardener/garden/compact-gardener.json`; `tests/fixtures/gardener/runner/compact-gardener.json`; `backend/tests/contracts/test_gardener_config.py`; `backend/tests/gardener/tasks/test_compaction.py`; `docs/concepts/config/idhazh-gardener.md`; `docs/architecture/publishing/idhazh-gardener.md`; `docs/concepts/config/retention-ages.md`; this plan's Reckoner line.
- **Acceptance gates:** local: the selected checks, which include `pytest backend/tests/contracts/test_gardener_config.py backend/tests/gardener/`, with ruff and mypy as `docs/how-to/run-the-gates.md` names them; `doc_load.py` with all touched Markdown paths passed as arguments, as in row 1. CI: the full suite.
- **Oracle:** every committed compaction declaration loads to the same values at the row's commit as at its parent, key for key, apart from `monthly_window_dry_run`, which is `false` and so changes no pass. On a fixture ledger that holds month files older than its window, a live pass with `monthly_window_dry_run` `true` packs every due day, month and year, deletes only files whose rows it copied, keeps every month file, and records `selected` above `deleted` by exactly the files a pass with its window live also deletes. A declaration that omits any one key is refused, with the key's name. It cannot settle a window going live on the runner, which stays the person's approval.
- **Merge window:** none; the row changes no committed data.

| # | Decision | Authority |
| --- | --- | --- |
| 1 | Every setting a compaction runs with is written in its declaration, and the loader refuses a missing one by name | The person, 2026-10-01: every packing, prune and retention setting in JSON; CLAUDE.md Guardrail #3, owner ruling 2026-09-21 |
| 2 | Packing and the window's drops have separate switches, so packing runs live while a window that deletes rows only reports | The person, 2026-10-01: packing working on every door ledger. Plan owner, on plan 57's rule that a deleting window goes live by the person's approval |
| 3 | The record keeps its fields: `selected` counts what a pass would delete with its window live, and `deleted` what it deleted | Plan owner, 2026-10-01: no persisted contract changes (ESCALATE trigger 4) |
| 4 | `monthly_window_dry_run` is `false` in every declaration main holds, so a `dry_run` turned `false` later does what it does today | Plan owner, 2026-10-01 |

| # | Rejected | Why | What it would cost to take | Authority |
| --- | --- | --- | --- | --- |
| 1 | Pack live by setting a window of forever where today's window only reports | It removes the retention setting from the file a person reads | The 30-day, 90-day and 14-month windows, written nowhere | Plan owner, 2026-10-01 |
| 2 | A separate task for the window's drops | Two tasks writing one ledger's periods in one wake can write a path the other deletes, and the shard refuses that | A second task kind, an order between the two, and their tests | Plan owner, 2026-10-01 |
| 3 | Fill the record's `fold_dry_run` and `folded_` fields for a compaction | It changes what `dry_run` and `deleted` mean on a compaction's rows, a shifted meaning in a persisted payload | A record migration, and a change in every reader of the upkeep record | Plan owner, 2026-10-01 |
| 4 | Keep the defaults, and write only the keys that differ | A person reading a declaration cannot see the numbers it runs with | Nothing to build; the request is not met | The person, 2026-10-01 |

## 4. Decisions the person makes before a row starts

The owner asks these in one message, in the shape of CLAUDE.md section 0c, before the row that needs them is dispatched. The person answered decisions 2 and 3 on 2026-10-01, by asking for packing by month and by year on every door ledger, and decisions 1 and 4 on 2026-10-02.

| # | Decision | Needed by | What each answer does | Recommended |
| --- | --- | --- | --- | --- |
| 1 | A re-run of the plan job replaces its first try's `seen` rows | row 5 | Yes: the door's rule for every ledger stands. A re-run checks out the commit its run started at, so it does not see its first try's rows, and the door then reads only the re-run's file for that unit: an address both tries filed takes the re-run's later `first_seen_at`, and an address only the first try filed is filed again by the next run that sees it. No: a door rule keeps every attempt of `seen`, at the cost of a `_DoorShape` field, a branch in `settle_rows` and their tests | Answered: yes. The person, 2026-10-02. An undated article's age moves later by the time between the two tries, and only for addresses the first try filed (Fowler, 2026-10-01) |
| 2 | `compact-published` packs live | row 5 | Live: packing deletes only raw and daily files whose rows it has already written into a month file, and a `monthly_window` of forever drops no month. Report-only: each assemble run adds a raw file that the digest's read of every published day opens, about 1,800 a year at five runs a day (an estimate) | Answered: live. The person, 2026-10-01 |
| 3 | `compact-feed-health` packs live, with its 14-month window | row 6 | Live: the Voices page reads packed days, at most one upkeep wake behind. Report-only: the page shows no day after the move | Answered: packing live. The person, 2026-10-01. The window reports until the person turns it live (section 0, Hard scope - out) |
| 4 | Row 5 disables `digest.yml` for its merge window | row 5 | Yes: no digest run can start on the old commit between the last read and the merge. A scheduled run that falls inside the pause is not made up later, so that day has one digest run fewer. No: the two reads of section 3 step 3 leave a gap of seconds in which a run can start on the old commit, and that run cannot push its day | Answered: no. The person, 2026-10-02: `digest.yml` keeps running, and row 5's merge relies on the two reads of section 3 step 3 (row 5, Merge window) |

## 5. Dependencies on other plans

A pointer names the other plan's row by its title. Where a row here and a row there edit one file, whichever merges second takes main in first.

| Plan | Row | What it means here |
| --- | --- | --- |
| [56](20260930-56-summary-quality-evals-plan.md) | "The eval ledger becomes `summary-quality-evals`" | Done (#1179, 2026-10-01), and rows 1 and 3 no longer wait. Sections 2.6 and 2.7 use its names: `summary-quality-evals`, and `summary-quality-evals-index` for the ID files |
| [56](20260930-56-summary-quality-evals-plan.md) | "The eval ledger's ID files are packed a month at a time" | Done (#1180). It owns `summary-quality-evals-index`, which `REFUSED` keeps refusing (section 2.8) |
| [56](20260930-56-summary-quality-evals-plan.md) | "A year file is read under an address no earlier read used, and a published ledger's declaration sets its own wait" | Complete (#1182): fresh year-file addresses removed the publication-specific minimum wait, without loosening a retention setting; rows 1 and 8 use the committed declarations |
| Completed #1177 | Packed-ledger indexes and daily packing for `item-health` and `host-fingerprint` | The code prerequisite is complete and its first live wake was verified on 2026-10-02. Row 6 reads its indexes and daily packing through row 5. [The query reader](../docs/architecture/publishing/how-the-query-door-answers-a-panel.md) owns the published index and missing-file behavior |
| Completed #1189 | The span-rollup family is retired and one item's trace is a command | Retirement is merged; row 2 leaves that family and its trial-root CSV alone. [Telemetry](../docs/concepts/telemetry.md#the-committed-traces-briefly) owns the bounded item command |
| [52](20260926-52-fifty-panels-move-and-six-projections-go-plan.md) | "Voices asks the ledger, and the ranking panels join it" | It moves the Voices panels to the query door and keeps the feed row on `feedResults`. If it lands first, row 6 edits the reader it leaves |
| [55](20260928-55-one-page-queries-every-ledger-plan.md) | "The door answers a written question, on the engine plan 51 shipped" | It widens `LEDGER_NAMES` to every registry ledger, and gives the door a tier for the writers' files, which would end the lag in row 6's decision 1 |
| [55](20260928-55-one-page-queries-every-ledger-plan.md) | "Every declared ledger reaches the site, capped at the widest span" | It publishes the moved ledgers, and its question over `feed-health` needs row 6. A ledger it adds to `ledger.published` with `monthly_window` forever must pack years, by the loader's rule, which touches `compact-published` |
| [57](20260930-57-upkeep-tasks-switch-on-plan.md) | "The eval ledger is packed live, and every scores window stays forever" and "The upkeep record, the picture cleanup's record and the feed retirements are packed live" | They turn `dry_run` to `false` on compactions that row 8 rewrites with every key. Row 8 writes `monthly_window_dry_run` as `false`, so their switch means what it means today. Row 2 packs the eval ledger's due months once, or finds them packed |
| [57](20260930-57-upkeep-tasks-switch-on-plan.md) | "The retention windows the person approves go live, one task a pull request" | Its table lists `seen`, `feed-health` and `counterfactual-scores`, whose retention declarations rows 4 to 6 delete. Their compactions keep the window reporting, so turning one live there becomes that compaction's `monthly_window_dry_run` set to `false`. If one went live there first, the row writes that compaction's window live, as the person approved (ESCALATE trigger 1) |
| [57](20260930-57-upkeep-tasks-switch-on-plan.md) | Section 2, how a switch is approved, landed and read | Section 4's live switches use its approval message and its reading of the first wake. Its rows also edit `backend/tests/contracts/test_gardener_config.py` and `docs/concepts/config/idhazh-gardener.md` |
