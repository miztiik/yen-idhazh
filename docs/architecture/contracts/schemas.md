# Contracts and Schemas

**Last Updated**: 2026-09-22

The persisted-shape subsystem: where the models live, how the schemas and frontend types are generated from them, and the gate that stops the three from drifting apart. This is the operational home of Guardrail #3 (contracts before logic) and `CLAUDE.md` sections 1a and 11.

Concept-level *why* lives in [../../concepts/principles.md](../../concepts/principles.md) (principle 4). This page is the *shape*.

## One source of truth, two generated outputs

```
backend/idhazh/contracts/*.py <- Pydantic models. HAND-WRITTEN. The source of truth.
 |
 +--> schemas/*.schema.json <- GENERATED. Never hand-edited.
 |
 +--> frontend/src/contracts/*.ts <- GENERATED. Never hand-edited.
```

The direction is one-way and never reversed. To change a persisted shape you edit the Pydantic model and regenerate; editing a generated artifact is an anti-pattern (`CLAUDE.md` section 10) and the drift gate will fail it anyway.

**One command writes both trees.** `python -m idhazh.contracts.export` walks one list of models and emits the schema and the TypeScript from it, so there is no second command a person can forget to run. That matters more than it sounds: the gap a hand-written mirror lives in is exactly the gap between two commands.

## What the TypeScript carries

The emitter reads the generated JSON Schema rather than the model, so the schema and the TypeScript cannot describe two different shapes. One module per contract, named for the schema stem: `schemas/host-fingerprint-row.schema.json` and `frontend/src/contracts/host-fingerprint-row.ts`.

Each module carries the root interface, one declaration per `$defs` entry, and the field descriptions as JSDoc, so a frontend developer reads the contract's own words on hover rather than opening the Python.

**A closed vocabulary ships twice: as a frozen array and as the union that array's members form.**

```ts
export const SERVER_JOB = ['plan', 'work', 'assemble', 'visuals', 'runtime', 'decide'] as const;

export type ServerJob = (typeof SERVER_JOB)[number];
```

The union alone cannot be tested against at run time, and a reader that has to narrow a CSV cell would otherwise retype the members - which is the drift the generator exists to remove. `frontend/src/lib/server/host-fingerprint.ts` narrows the `job` column against that array and `watchedFlags()` hands back `WATCHED_FLAG`, so no list of jobs and no list of instruction-set flags is typed anywhere in the frontend.

**An optional field is emitted optional.** Pydantic marks a field with a default as not required, so `cpu_model?: string | null` is what the contract says: the key may be absent, and present-but-null is the reading nobody took. A reader that fills every key says so by deriving from the generated type - `Required<HostFingerprintRow>` - rather than by declaring a second interface.

**A column added to a model becomes a compile error in the reader that builds the row.** That is the whole point: before this, adding a column moved `schemas/` and moved nothing in `frontend/`.

## What is still hand-written

`frontend/src/lib/payload/types.ts` mirrors `schemas/digest-day.schema.json`, `digest-view`, `search-index` and `visual-data` by hand, and the published reading surface is typed from it. It is not converted yet: several of its types narrow the contract on purpose (`DigestViewItem` is a `Pick`, and `markup` is a build-time field that is deliberately not in the schema), so replacing it is a design change to the reading path rather than a rename. The chart view models under `frontend/src/lib/charts/` that share a name with a `machine-panels` definition are the same kind of case - `console-machine-panels.spec.ts` checks them against the schema at run time instead.

## The model file has no generated schema

`config/models/<name>.json` is validated by `ModelsConfig` and is deliberately absent from `contracts/export.py`, so no `models-config.schema.json` and no `frontend/src/contracts/models-config.ts` exist. **A configuration file this project authors needs no declared shape** (`CLAUDE.md` Guardrail #3, owner ruling 2026-09-21): nothing but this repository writes one and nothing but this repository reads one, so a generated schema restates a model that is already its only reader, and a generated frontend type restates a file the frontend opens by hand.

What the entry still declares is what this project's own code names: the weights, the architecture, the two turn-envelope strings no template can answer, and the digest the settings were derived against. **What it does not declare is the settings themselves.** The `server` block is llama-server's own flags, spelled as the binary spells them and emitted verbatim, and the `request` block is the four values that go in a request body. A typed field for a value this project hands straight to another program is a second spelling somebody has to keep in step - and llama-server refuses a flag it does not accept at every server start, which names it and does not start.

Two keys are required and both are refused by name at configuration load, in `idhazh.config.refuse_a_model_nothing_could_run`: `server["--ctx-size"]`, because this project does real arithmetic on the window and the published site reads it at build time, and `request["request_timeout_minutes"]`, because four call sites multiply it by sixty and llama-server has no default to fall back on. Everything else is optional, and absent means the server's own default.

**The recorded shape keeps the old key.** `ModelRef.inference` is a plain mapping so a `run.json` an earlier run wrote - carrying a weights digest, a decode cap and option names no build declares now - still reads (section 11).

## Why the models, and not the schemas, are the source

A JSON Schema is a good interchange format and a poor authoring format: it cannot express a cross-field invariant readably, it has no place to put a validator, and nobody catches a typo in it at edit time. A Pydantic model is typed at authoring time, carries its invariants as code, and is directly usable by the producer that writes the payload. Generating downward from it means the validation the backend enforces and the types the frontend trusts cannot disagree.

## Layout

| Path | Holds |
| --- | --- |
| `backend/idhazh/contracts/base.py` | The shared string types, the canonical serializer, and the two base models: `Model` for a nested shape and `Contract` for a top-level persisted document. `Contract` owns the `version` date-stamp, the `changelog` tuple, the invariant that `version` equals the newest changelog entry, the `<stem>.schema.json` name, and the JSON Schema emitter. |
| `backend/idhazh/contracts/<name>.py` | One module per persisted shape. |
| `backend/idhazh/contracts/export.py` | Walks the models and writes both generated trees. Also the list of what each of them is allowed to contain. |
| `backend/idhazh/contracts/typescript.py` | Turns one contract's generated JSON Schema into one TypeScript module. |
| `schemas/<name>.schema.json` | Generated. One flat file per model. |
| `frontend/src/contracts/<name>.ts` | Generated. One module per model, named for the same stem. |
| `frontend/src/lib/payload/types.ts` | The published payload's TypeScript shapes, mirroring `schemas/digest-day.schema.json`. Hand-written, and the one mirror left. |

The shapes, and where each one lives once written:

| Model | Schema | Persisted as |
| --- | --- | --- |
| `AppConfig` | `app-config` | `config/idhazh.json` |
| `AppearanceConfig` | `appearance-config` | `config/appearance.json` |
| `Sources` | `sources` | `config/sources.json` |
| `Taxonomy` | `taxonomy` | `config/taxonomy.json` |
| `Watchlist` | `watchlist` | `config/watchlist.json` |
| `RunPlan` | `run-plan` | the day's work list under the run directory |
| `Article` | `article` | one file per item under the run directory |
| `Summary` | `summary` | one file per item under the run directory |
| `VisualDecision` | `visual-decision` | one file per item under the run directory |
| `VisualPlan` | `visual-plan` | not persisted yet - the shape lands ahead of its producers (Guardrail #3), and what a plan may not carry is as much of it as what it holds ([../publishing/visuals.md](../publishing/visuals.md)) |
| `ElementTable` | `element-table` | not persisted yet - the shape lands ahead of its producers (Guardrail #3), and where an article's elements are written is settled by the row that writes them |
| `EvalRow` | `eval-row` | one row of `state/scores/<YYYY>/<MM>/<DD>/`, in the file its writer owns |
| `ObservationIndexRow` | `observation-index-row` | one row of `state/score-index/<YYYY>/<MM>/<DD>/`, the identity of one measurement the day beside it holds |
| `SeenRow` | `seen-row` | one appended row of `state/seen/<YYYY>/<MM>/<DD>.csv` |
| `PublishedRow` | `published-row` | one appended row of `state/published/YYYY/MM/DD.csv` |
| `FeedHealthRow` | `feed-health-row` | one row of `state/feed-health/<YYYY>/<MM>/<DD>/`, in the file its writer owns |
| `FeedRetirementRow` | `feed-retirement-row` | one appended row of `state/feed-retirements.csv` |
| `ItemHealthRow` | `item-health-row` | one row of `state/item-health/<YYYY>/<MM>/<DD>/`, in the file its writer owns |
| `PublicTelemetryRow` | `public-telemetry` | one row of `frontend/public/telemetry/<YYYY-MM>.csv`, the browser-safe projection of the row above |
| `TelemetryAggregateRow` | `telemetry-aggregate-row` | one row of `state/telemetry-aggregate/<YYYY-MM>.csv`, rewritten whole |
| `ScoreArchive` | `score-archive` | `state/score-archive/<YYYY-MM>.json`, one whole document per archived score month |
| `DayMetrics` | `day-metrics` | `state/day-metrics/<YYYY>/<MM>/<DD>.json`, one whole document per published day, rewritten when that day is corrected |
| `StorySimilarityPair` | `story-similarity-pair` | one appended row of `state/content-similarity-judge/scored-pairs/<YYYY>/<MM>/<DD>.csv` - one borderline pair, what it scored, what a judge said in both orders, and the instrument that said it. The same shape holds the day's draw under `backend/var/council/<date>/selection/<judge>/` before a judging unit reads it |
| `StorySimilarityDistribution` | `story-similarity-distribution` | the whole of `state/content-similarity-judge/score-distribution.json`, rewritten - a fixed row of slots and three counts each, so the fit reads one file of a size that never changes (Guardrail #12) |
| `FittedSimilarityThreshold` | `fitted-similarity-threshold` | one appended row of `state/content-similarity-judge/fitted-thresholds/<YYYY>/<MM>/<DD>.csv` - what the merge line was, what the evidence proposed, and what the run applied |
| `SimilarityHoldoutPair` | `similarity-holdout-pair` | one row of `state/content-similarity-judge/holdout-pairs.csv`, typed by a person - two addresses, two headlines, and whether they are one story |
| `CouncilShardOutcome` | `council-shard-outcome` | one appended row of `state/llm-council/shard-outcomes/<YYYY>/<MM>/<DD>.csv` - whether one unit of work finished, stopped on its deadline or had nothing to do, and what the work it hosted cost. It carries no name for the unit, so it reads the same whichever tenant ran |
| `ContentSimilarityJudgeMetrics` | `content-similarity-judge-metrics` | one appended row of `state/content-similarity-judge/metrics/<YYYY>/<MM>/<DD>.csv` - what one shard of that judge's night dealt, read, agreed and lost, plus its two rates and its clocks |
| `MergeLineHoldoutScore` | `content-similarity-judge-merge-line-holdout-score` | one appended row of `state/content-similarity-judge/merge-line-holdout-scores/<YYYY>/<MM>/<DD>.csv` - the line in force, the four cells it scored against the hand-marked holdout, and what the line was made of. No model runs in it, so it carries no call stamp |
| `ValidationRow` | `validation-row` | one row of `state/<run.trial_state_dirname>/validation/<YYYY>/<MM>/<DD>/`, folded in from a segment |
| `RunManifest` | `run-manifest` | `.../<DD>/run.json`, append-only per date |
| `DigestDay` | `digest-day` | `.../<DD>/digest.json` and each `run-<N>.json` |
| `SearchIndex` | `search-index` | `frontend/public/assist/index/<YYYY-MM>.json`, with its vectors in a sibling `.bin` |
| `CorpusRow` | `corpus-row` | one line of `corpus/corpus.jsonl` |
| `CorpusMeta` | `corpus-meta` | `corpus/corpus.meta.json` |

Everything under `state/` is a row contract rather than a file contract, because a file that is only ever appended to has no shape of its own - the row is the unit that has to hold. Which of those ledgers a later run reads back, and what each one answers, is [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md).

`TelemetryAggregateRow` is the one exception and says so in its own line above: its file is derived from the item-health shard it replaces, so every run of the fold writes the same bytes and the file is rewritten rather than appended to. Appending would double a month whenever the fold ran twice over a shard a lost race had restored. What decides when a month is folded is `observability.item_health_full_grain_months`, and what it costs is in [../publishing/retention.md](../publishing/retention.md#what-bounds-the-committed-state-tree).

`ScoreArchive` is the second exception and is a stronger one: it is not a row at all. A month of `state/scores/` past `observability.scores_full_grain_months` becomes one JSON document, and a document is the right shape here because two of the three things it holds are whole-month facts rather than per-row facts - the SHA-256 of that month's day files in day order, and the sorted index of every distinct measurement it held. A CSV would have had to spread both across rows that do not mean anything on their own. It is written temp-then-rename, read back through this contract, and reconciled field by field against a second reading of those day files before any of them is unlinked; `.github/workflows/prune.yml` force-pushes `main` on a schedule (`CLAUDE.md` section 8), so a file deleted on the strength of an unchecked summary does not come back. What it weighs is in [../publishing/retention.md](../publishing/retention.md#what-bounds-the-committed-state-tree).

`DayMetrics` is the third, and a document for the same reason `ScoreArchive` is: it is a whole-day fact, not a per-row one. A run writes one `state/day-metrics/<YYYY>/<MM>/<DD>.json` per published day - the day's counts and sums stored directly, and each median, distinct count or ranked list stored as the day's own value plus whatever lets a reader combine days in a defined way, because a percentile cannot be re-added into a window's percentile. It nests by year and month to mirror the published digest-day layout, and it is never a running total: a correction rewrites the whole record for that day. The console reads it back instead of walking every score, item-health, feed-health and published-day row for a figure that never changes once the day is frozen (Guardrail #12). It was authored as a contract in row 21 of the constant-cost-reads plan (#486), written by the producer in row 22 (#489), and read by the console reducers in rows 23 and 24 (#500, #501).

### A new row ledger ships with its header, not with its first run

`.github/scripts/commit-and-push.sh` runs under `set -euo pipefail` and stages every path a job owns in one `git add "$@"`. A path that is not in the checkout makes that call fail, and `set -e` then abandons the whole commit step - so a ledger that only appears once its producer has succeeded lets a broken producer cost the job the *other* ledgers it was staging beside it. `state/feed-retirements.csv` and `state/content-similarity-judge/holdout-pairs.csv` therefore ship as header-only files, and `backend/utilities/check_seeded_stores.py` asserts each committed header equals its contract's own `csv_columns`.

That is not "pre-creating an empty module for later" (`CLAUDE.md` section 10). The file is the ledger, and its header is the contract's own column list; what is being avoided is a failure mode in the step that commits it.

The training corpus ships the same way and for the same reason: `corpus/corpus.jsonl` is committed empty, `corpus/corpus.meta.json` holds a zero census, and `corpus/holdout.txt` is empty. A test asserts all three are tracked.

`state/feed-retirements.csv` is the third, committed as a header and no rows on 2026-09-02 - one commit before the plan stage started writing it. It is also registered in `ledger.keyed_paths`, keyed on `endpoint_key` alone, so what makes two of its rows one record is declared with the shape rather than with its first writer - which is what makes the rule true from the first row rather than from the second.

`state/content-similarity-judge/holdout-pairs.csv` is the fourth. It was committed as a header on 2026-09-18 and it has held marks since 2026-09-19, so a fresh clone now gets the marks rather than an empty file - which is what lets the console draw the margin on a checkout that has never run the pipeline. It is the one `state/` CSV that names `merge=text` - two edits of it are two people disagreeing about the same rows, and a union merge of a disagreement silently keeps both marks. Only `state/published/**`, `state/visual-prunes/**` and `state/seen/**` carry a union driver at all.

### The one row contract whose CSV omits `version`

Every other row ledger writes `version` as its first cell, because
`csv_columns` is `tuple(cls.model_fields)` and `version` is the first field the
base contract declares. `PublicTelemetryRow` overrides that and writes nineteen
cells, none of them `version`.

The reason was on the far side of the boundary. Until 2026-09-16 `parseTelemetryCsv`
in `frontend/src/lib/charts/series.ts` checked the header **position by position as
a prefix**, so a name at position zero shifted every position the console read and
blanked its charts on every cached bundle. It resolves every cell by its column
name now, so an insert no longer blanks anything
([../publishing/telemetry-series.md](../publishing/telemetry-series.md)). What
keeps `version` off the row is what is left once that hazard is gone: a cell in
every row of a payload the reader downloads, which no panel reads.

The stamp is not lost: it is a field of the shape, and
`schemas/public-telemetry.schema.json` is where a reader of an old shard looks it
up. What the row loses is the ability to say which *row* predates a change, which
is the thing `state/scores/` needs and this file does not - the console reads the
projection for rates and never branches on a row's age.

It is also the only contract here whose forbidden fields are a rule rather than
an omission. `canonical_url`, `url_key` and `detail` are named in
`FORBIDDEN_COLUMNS`, and the module raises at **import** if any of them ever
appears on the model. A trust boundary spelled as a list of strings in the writer
gains a cell by a one-word edit and nothing refuses it; spelled as a model, the
edit does not start (Guardrail #11).

### Two of these are contracts and are deliberately not migration surfaces

`EvidenceItem` and the two corpus shapes carry a `version` like everything else and owe no read-side migration when they change (section 11). Nothing they were written into survives: the oldest `EvidenceItem` that can exist is a 14-day workflow artifact, and the corpus is a rolling window regenerable from the run's own payloads whose history is rewritten every `finetune.prune_every_days`. A shape change there owes a re-run or a re-harvest. They are contracts under Guardrail #3 all the same, because each crosses a process boundary and something on the far side has to be able to refuse a file it cannot trust.

### A shard-grain fact is its own contract, not a field on the run manifest

`HostFingerprintRow` could have been a list on `RunRecord`, and four things say it should not be. **Grain**: a manifest run record is one run and a host record is one job, so the manifest would grow a variable-length list keyed by something it does not otherwise carry. **Producer**: the manifest is written by `assemble`, in another job hours later, so the numbers would have to travel inside the `items-*` artifact - which expires and is never committed, and a cancelled shard's readings are the ones most worth having. **Audience**: `run.json` is a published payload a reader's browser fetches, and this is measurement evidence, which belongs under `state/` where nothing is served. **Timing**: a concurrent branch was also opening `RunManifest`, and two branches stamping one contract's changelog on the same date raise `TypeError` at import.

**The grain argument earned four more cells on 2026-09-19.** `job_seconds`, `model_load_ms` and the two `server_prompt_*` counters are facts about the `work` job rather than about the run, and they landed here rather than on the manifest for the first reason above: one run draws up to eight hosts and takes eight different clocks, so a manifest field would have to become a per-shard list - which is what this ledger already is. `docs/reference/pipeline-cost.md` owns what they measure and how to read them; the rollback rule for the truncation cap is the caller.

**The readings arrive as raw text the job printed** - llama-server's own log, its `GET /metrics` body - and every derivation happens in `telemetry.silicon`, beside the stage that writes the row. A shell that computes a percentage is a second place the arithmetic lives and no place it can be tested; a Python function over text the caller opened is one place, and its oracle is the real captures under `tests/fixtures/runtime/`.

What would overturn it: a published surface that needs the raw readings, which would make them a published payload; or a run that stops being sharded, which would make job grain and run grain the same thing and the manifest the cheaper home.

### A ledger partitions only when its read carries a window

Some `state/` ledgers are one file and some are a directory of shards. The rule
is one question: **does the read that consumes this ledger carry a time
window?** The grain follows what the reader asks for - a month for the ledgers
whose windows are measured in months, a day for `state/published/`, which
mirrors the digest tree its rows are derived from.

| Ledger | Layout | The question it answers | Windowed on read |
| --- | --- | --- | --- |
| `state/seen/` | day files | how old is this address? | yes, `collect.seen_window_days` - and it is the one window here counted in days, so the prune keeps exactly the files the read opens |
| `state/feed-health/` | day files | is this source still working? | yes, `ledger.HEALTH_WINDOW_DAYS` |
| `state/item-health/` | day files | what did every planned item do? | yes - the console pans a window (`default_window_days` 30) and the read opens the days it names |
| `state/telemetry-aggregate/` | monthly shards | what did a month past `item_health_full_grain_months` do, in totals? | it inherits the shard boundary of the file it replaces |
| `state/published/` | day files | have we already published this? | yes, `collect.published_window_days` - committed at `-1`, so the read is whole today |
| `state/scores/` | day files | how did every scored item do? | no - sharded by month from 2026-08-31 and filed by **day** since 2026-09-13, and a month past `scores_full_grain_months` becomes [one `ScoreArchive` document](../publishing/retention.md#what-bounds-the-committed-state-tree) |
| `state/score-index/` | day files | which measurements does the day file beside this one already hold? | no, and deliberately - `OBSERVATION_KEY` carries no date, so the same address, output and scorer is one measurement whenever it is re-taken. It files by the ledger's day rather than a grain of its own, because two grains in one relationship would be a mapping somebody maintains |
| `state/score-archive/` | monthly documents | what did a month past `scores_full_grain_months` do, in totals and distributions - and which measurements did it hold? | it inherits the shard boundary of the file it replaces |
| `state/feed-retirements.csv` | one file | is this address gone for good? | no - a retirement is permanent for one endpoint |
| `state/day-validations.csv` | one file | which frozen days have passed, and against what? | no - a receipt file, read once a run |
| `state/day-metrics/` | day files | what did one published day do, in totals? | it is addressed by day: the site opens the dates a page names and walks nothing |
| `state/visual-prunes/` | day files | is the picture backlog shrinking? | no, and the layout saves this read nothing - see below |
| `state/content-similarity-judge/scored-pairs/` | day files | what did the judge say about this day's borderline pairs? | no - the collecting job reads one named date and never opens that file again |
| `state/content-similarity-judge/fitted-thresholds/` | day files | what was the merge line, and what moved it? | yes - the step-change guard takes a median over the newest `step_change_window_rows` written rows, and `assemble` looks back `applied_lookback_days` for a line |
| `state/content-similarity-judge/holdout-pairs.csv` | one file | which pairs did a person judge, and how? | no - a mark taken in August is still a mark in September, and the file grows with how many pairs somebody has marked rather than with the archive |
| `state/content-similarity-judge/score-distribution.json` | one document | what has the judge said, slot by slot, across the whole band? | no - **it is not a ledger at all.** It is rewritten whole, and its size is the band and the slot width rather than the history. That is the point: the fit reads it instead of sorting every pair ever judged (Guardrail #12) |

A window turns a partition into a skipped file open. `day_partition.days_in_window`
names both ends of a day cover, so a plan run opens the days it names and no
others. It is exact where the month rule it replaced was generous: a 90-day cover
over `state/item-health/` opens 91 day files and reads 90 days of rows, where four
month shards could hold up to 120 days of them.

`ledger.shards_in_window` is that rule one grain up, and **no ledger is read with
it any more** - `drift.read_windows` was the last and moved on 2026-09-13 with
`state/scores/`. What it still answers is how many month-shaped buckets a
day-counted window reaches, which is what sizes the `keep_months` knobs.

**A store and its published mirror may file at different grains, and
`state/item-health/` is the worked example.** The ledger files by day because a
run writes one day; the projection under `frontend/public/telemetry/` stays
monthly because the console prices a window in the files a browser fetches. The
publisher is the bridge: it folds a month from that month's day files, reading at
most 31. Both rules and what the bridge costs are in
[../../concepts/partitions.md](../../concepts/partitions.md#a-store-and-its-mirror-may-file-at-different-grains).

Without a window, sharding is a cost with no matching saving. A question with no
time bound has to read every row, so every shard gets opened anyway - the same
bytes through more file handles, plus a directory listing and a stem loop that a
single `open` does not need. Splitting a file you always read whole makes it
slower, not faster.

Two consequences worth stating so nobody re-derives them:

- **Adding a window to an unsharded ledger buys nothing on its own.** Filtering
 rows after reading them saves no I/O. A window is only a saving once it can
 decide which files to skip, so the window and the shard land together or
 neither does.
- **A monthly shard is not the only shard period available.** A ledger whose
 month file grows past what a reader should download moves to a shorter period
 rather than losing rows - `state/item-health/` did exactly that on 2026-09-13,
 from `<YYYY-MM>.csv` to `<YYYY>/<MM>/<DD>.csv`. The readers walk the tree, so
 the period is a layout change and not a contract change; see
 [../sources/item-health.md](../sources/item-health.md).

**The two single files above are deliberately unsharded, and the burden is on a
change that shards one.** `state/feed-retirements.csv` and
`state/day-validations.csv` are not work left undone. Neither of their reads
carries a window, so by the rule above a partition would open every file anyway
and cost a directory walk a single `open` does not need. One of the two -
`day-validations.csv` - grows for ever with no prune, and **that is a retention
question rather than a grain question**: sharding it would make its read worse
and leave the growth exactly where it is.

There were four until 2026-09-13 and three until 2026-09-19.
`state/fingerprints.csv` was the fourth, and it was deleted rather than sharded:
its read had no window because it had no reader left at all.
`state/runtime-counters.csv` was the third and went the same way - every cell a
reader still wanted moved onto `state/host-fingerprint/`, which is already a day
tree.

**A collection can file by day for a reason that is not the read**, and
`state/visual-prunes/` is the worked case: its question is the whole series, so
the layout buys the read nothing at all. What it buys is a merge surface and a
removal - two runs collide on a file only when they are the same day, and taking
a day back off the record is one `rm` rather than an edit inside a shared file,
which an append-only ledger cannot express.

**What a shard obliges its writer to do is a separate rule, and it is defined
once.** A closed month is rewritten only when a correction targets it; every
other run touches the current partition alone. That rule, the closed rule for
each partitioned collection above, and what the pattern does with a correction, a
deletion, a late arrival and a row whose date changes are in
[../../concepts/partitions.md](../../concepts/partitions.md).

**What a growing collection obliges its reader to declare is a third rule, and it
is also defined once.** A window is one of three shapes a cover can take, and the
column above is only ever true of the reads whose question has a time bound in
it. Which reads carry which shape, why `-1` is a declaration rather than an
omission, and how to decide it for a collection this table does not list are in
[../../concepts/growing-reads.md](../../concepts/growing-reads.md).

Authority: Carmack (cache and shard economics), 2026-08-25.

The eval ledger and source-state CSV ledgers compare the committed header to the row contract before writing. A mismatch stops the append and tells the operator to migrate the ledger. Padding is forbidden: readers map cells by header position, so a stale header would put correct-looking names over the wrong values.

### Narrowing a row ledger is one commit, not three

A reader built on `csv.DictReader` maps cells by name off the file's own header, so dropping a column nothing reads changes no answer the reader gives. What refuses is the append: `require_matching_header` compares the committed header to the contract's columns and raises rather than write. That is called from `extend_ledger_file` and from nothing on the read path, so the model change and the file rewrite have to land together - and once they do there is no read-side transition left to stage, which is what removes the expand-migrate-contract sequence a breaking change usually needs.

The rewrite is a committed one-shot utility rather than an ad-hoc script, so a fork or a stale branch can reproduce the same migration. `backend/utilities/migrate_published_ledger.py` is the worked example: it refuses a ledger that is already narrow, and it refuses to write at all unless the rewritten file carries the same rows, in the same order, with the same values in the cells the read path opens. `PublishedRow` lost `canonical_url` this way on 2026-08-26 ([../sources/freshness.md](../sources/freshness.md)).

A migrated row keeps the `version` cell it was written with. The base contract accepts an older stamp on purpose, so a later read-side migration has something to branch on; restamping every row would erase the only marker of which rows predate the change.

**A narrowing declares the heading it dropped, or the store is unrepairable as well as unappendable.** `ledger.migrate_header` refuses any heading that is neither a current column nor one the reader carries, rather than dropping cells silently - so a column deleted from a contract with nothing declaring it leaves the committed files refusing the append AND refusing the re-file that would fix them. The declaration is a frozen set on the row itself, named `DROPPED_CELLS`, and the ledger hands it to the engine through the store's entry in `ledger.keyed_paths`. `ItemHealthRow` has held one since 2026-09-17; `StorySimilarityPair` gained one on 2026-09-21 when `decode_digest` left. One set serves both sides of the row: the committed day file reaches it through the ledger, and a JSON payload reaches it through a before-validator that drops the same keys, so a removal declared once is honoured wherever the row is read.

**A record whose own name is a stamp over its values lands under a new name when one of those values goes.** `StorySimilarityDistribution.record_stamp` is the archive filename, so removing a stamped value moves it exactly as changing one would: the next record counted archives under the old name and a fresh one starts. Nothing ever re-derives an archive's name, so every file already written stays readable under the name it has, and the reset happens once.

### Widening a row ledger writes an empty cell, never a value invented today

Adding a column is the same commit shape as dropping one, and for the same reason: `require_matching_header` compares the header tuple exactly, so the contract change and the file rewrite land together or the next append stops the run.

What differs is the cell. A column is appended at the end of the row and never filed by meaning, because a cell inserted in the middle shifts every historical value one place right under a reader that maps by position. The new field is nullable, and every row that predates it gets an **empty** cell. Zero, or a value recomputed today, would claim the older run measured something it never looked at - and for a digest that is worse than silence, because the whole point of a digest is that somebody can check it.

**A file the rewrite never reached reads the same way.** The rewrite covers what is committed. It cannot reach a segment an earlier run left in transit, and that file carries its own header - so the reader treats a column the file does not carry as that same empty cell. That is what makes a widening additive for a row nobody migrated, and the `plan` job's catch-up fold depends on it: a run that opened before the column existed leaves rows the next run has to be able to read. The one cell this cannot stand in for is a column where `""` is itself a reading. `HostFingerprintRow.flags` is that column - empty means the host reported none of the watched instruction-set flags - so it has to be present, and every other cell on that row either comes back absent or fails its own field parser by name. A column the contract cannot place is kept rather than projected away, so a file wider than this build is refused instead of quietly losing the cell.

The rewrite is small enough to be reviewed as a diff rather than run as a utility: the header gains one name and each row gains one comma, and nothing else in the file moves. `EvalRow` gained `self_repetition` this way on 2026-08-26 and `source_digest` on 2026-08-27. A committed test appends to a byte copy of the real ledger and asserts every historical cell is where it was, which is the check a fork actually needs.

**Past a few thousand rows it stops being reviewable as a diff, and then it is a utility like any other narrowing.** `FeedHealthRow` gained five columns on 2026-09-02 across 6,433 committed rows, so the rewrite was `backend/utilities/migrate_feed_health.py` and it carried the same two-part oracle the narrowing utility does: every cell the old header named is still under that name and in that order, and every rewritten row loads through the contract with the new cells absent. Its own test was stronger than either half, because the pre-migration file no longer existed to compare against - it derived the narrow shape by dropping the five appended columns off the committed rows, proved `require_matching_header` refuses an append onto that, and then proved the utility turned it back into the committed bytes exactly. That is what said the committed bytes were the migration's output rather than a hand edit. **Both went on 2026-09-13**, when `state/feed-health/` moved to day files: the utility read month shards and no month shard can exist there again, and a test of a deleted function is not a test. `git show` on the 2026-09-02 commit holds them.

**It may derive that shape from the rows stamped below the widening, and only those.** The stamp is the boundary because the utility deliberately left it alone: a migrated row keeps the `version` it was written with, so it stays the one marker of which rows predate the change. Deriving the shape from the whole shard instead held for exactly one day - the five columns are nullable, the next scheduled run filled them, and both halves of the oracle went red at once and took the gate with them. The rule the failure paid for: **a test that reads a growing committed ledger asserts what stays true as it grows, or it is a snapshot with an expiry date nobody wrote down.** The pre-widening rows were a fixed set that only shrank, so the test skipped once retention would have taken the last one rather than reporting a defect that was not there - and `CLAUDE.md` section 13 has since ruled the whole shape out: a walk over committed data carries a fuse, so the check belongs in the producer or in an operator surface and not in the suite.

### Design rationale: one widener for every store, rather than one per widening

`backend/utilities/widen_ledger_header.py` is the operator's door onto `ledger.migrate_header`. Until 2026-09-21 nothing in the repository could widen a header from a command line: `migrate_header` was reached only from the compaction verb, which folds a segment into a head and takes no store argument. So every widening before it shipped its own utility - one for the feed-health header, another for the item-health header - each one a new file doing what the engine already did. Both are deleted; this door is what re-files either store now.

One utility is possible because the two things it needs are already registered elsewhere. The store comes from the prune vocabulary, so a word means the same store in every command an operator types. The contract that reads a row comes from `ledger.keyed_paths`, which already pairs a committed file with its reader for the post-merge settlement. Neither list is restated in the utility, so neither can drift from it, and a store that ships before its writer reports nothing rather than failing.

The dry run is the default, as it is for the prune verb - writing takes a word nobody types by accident. Both modes re-file a copy in a temporary directory and compare bytes, so a dry run's report is the live run's report rather than a second arithmetic that agrees until it does not. Run twice, the second pass reads line one, sees the contract's own header and returns, so the file is byte-identical and reported unchanged.

It checks one thing and leaves the rest to the engine: the row count may not move, because that is the only failure `migrate_header` cannot see from inside a single file. Everything else is already there - it refuses a heading this build cannot place, keeps a row no reader could place and raises, and re-files through the contract's own reader rather than cell by cell.

`StorySimilarityPair` is the first shape it was written for. It gained six columns on 2026-09-21 - `judge_id`, `judge_temperature`, `grammar_applied`, `first_token_probabilities`, `thinking_spans` and `judged_by_run_id` - and the six are declared in the row's own body rather than inherited from `judge_call.JudgeConfigStamp`. Pydantic collects a base class's fields first, so inheriting would have put them at the HEAD of the header and re-read every committed row one cell out of place. A mixin that cannot be inherited by the row it was written for is the price of a store with rows already in it, and it is the reason `JudgeConfigStamp` is a mixin rather than a base class. A seventh column, `decode_digest`, landed and left the same day, and re-filing it away is what made this door narrow as well as widen - the carried set now travels with the reader out of `keyed_paths`, and the reader is looked up for one day rather than for every committed file (Guardrail #12).

`judge_id` is the one appended cell the widening fills rather than leaves empty: its default is not `None`, and the rows it fills were written by the judge that owns the store. That makes it the one column the reader has to name. `StorySimilarityPair.from_csv_row` drops the key when the cell is empty so pydantic supplies the default, and it does that BY NAME - a predicate over "any field whose default is not `None`" would also drop `version`, because a required field has no default at all, and the before-validator would then refill it with this build's own stamp. That is silent coercion on the one cell that says which rows predate the widening.

Authority: Fowler (persisted contracts), 2026-09-21.

`backend/idhazh/contracts/` **must not import any other subpackage** of `backend/idhazh/`. Contracts are the bottom of the dependency graph; everything else depends on them (`CLAUDE.md` section 4). A contract that imports a stage is a contract that cannot be loaded by a test of that stage.

## Every contract carries version and changelog

Inherited from the base model, per `CLAUDE.md` section 11:

- `version` is a **date-stamp** (`YYYY-MM-DD`), never an integer and never an epoch. It says *when* the shape last moved, which is the question anyone reading an old payload actually has. When more than one change lands the same day, extend the stamp to the minute or the second - `YYYY-MM-DDTHH:MM` or `YYYY-MM-DDTHH:MM:SS` - so the value stays ASCII-sortable.
- `changelog` is newest-first, each entry `{ version, change, why }`. `change` says what moved: a field added, removed or retyped, or a meaning shifted. `why` says what the change was for. A `changelog` entry that only restates the field name tells a later reader nothing they could not read off the diff.
- The base model **enforces** that `version` equals `changelog[0].version`, so the two cannot fall out of step.

For the citation sweep approved by miztiik on 2026-09-12, `Field(description=...)`
text could be regenerated without a version bump. `version`, `changelog` and
emitted provenance were explicitly outside that approval. That bounded decision
grants no general exemption for annotation edits. Retained changelog citations
record earlier changes; they are not instructions to an agent.

### One line, five entries, and git holds the rest

`CLAUDE.md` section 11 bounds the changelog, and `backend/tests/contracts/test_changelog_shape.py` is the gate.

**One line per field.** `change` and `why` are each a single sentence on a single source line. A string long enough to wrap is over budget, which is the whole mechanism: the line length is the editor, and it is the same 100 columns ruff already enforces.

**Five entries at most** - the four newest changes, then one pointer entry saying the rest is in git. The pointer carries the oldest stamp the contract still names, so it also marks how far back the retained history reaches. A contract that has never had five changes carries no pointer; there is nothing to point at.

**What may not appear in an entry**: a measurement, a hardware line, a date inside the prose, an incident, a plan row, a persona's name or an owner ruling. A reading belongs in the instrument log (`CLAUDE.md` Guardrail #10) and a rationale belongs in the living doc it impacts (Guardrail #4). The entry names what moved, not the argument that moved it.

**The line is the test.** An entry that will not fit one line is asking a question rather than failing a limit: is the reason worth a `## Design rationale` section on the page that owns the subsystem? If yes, write it there and leave one line here pointing at the page. If no, it was never worth keeping. Those are the only two answers - a wrapped entry is neither.

**Old entries are deleted, not archived.** Every entry is copied verbatim into the generated schema and shipped, so an unbounded changelog is a file that grows forever in two places at once. Git already holds every word, so a fifth entry pointing a reader at the file's history costs one line and loses nothing. A commit hash is not the pointer: hashes do not survive the scheduled history prune (`CLAUDE.md` section 8), and a hash that no longer resolves is worse than no pointer at all.

**Dropping an entry does not stamp a new `version`.** The stamp answers how old the *shape* is, and deleting history moves no field, no type, no default and no validator - a payload that validated before the trim validates after it. The generated bytes do move, so the drift gate has to be re-run, but a version bump here would announce a shape change that did not happen. Trimming is the one edit to a contract module that is exempt, and the rule that made it is dated once in `CLAUDE.md` rather than restamped across every contract.

Additive change: append the entry, stamp today, drop the oldest if that takes the list past five - older payloads still validate. Breaking change: append, stamp today, **and write the read-side migration in the same commit.** A payload written by yesterday's run that today's build cannot read is a release blocker.

A document that arrives without a `version` is stamped with the current one on read, so the generated schema marks the field optional-with-a-default rather than required. Everything this project writes emits it explicitly; the tolerance exists for a hand-edited config file, not as a licence to omit it.

### A published key can be frozen while its Python name moves

A field name in Pydantic is the JSON key by default, so a rename that looks like tidying is a breaking change to a published payload. Where the payload is published and the rename buys only a better word, the honest split is to move the Python name and pin the key with `Field(alias=...)`, plus `serialize_by_alias` and `validate_by_name` on that model. The model then reads and writes the key it always wrote, the generated schema still names the key, and no committed payload is migrated.

`RunRecord` is the one model doing this, since 2026-09-05. `items_decided` writes `items_routed` and `decision_ms` writes `route_ms`, because `run.json` is published and `frontend/src/lib/payload` reads both keys by name at build time. `ModelRole.VISUAL_PLANNER` is the same trade with no alias needed: an enum member is a Python name and its `"route"` value is the wire.

Two conditions, and both have to hold. **The rename must buy a word and nothing else** - an alias that also changes a type or a meaning is a breaking change wearing a rename's clothes. And **the alias must be pinned on the model that owns the key**, not by flipping `by_alias` in the shared serializer: no other contract declares an alias, so a global flag would be a no-op today and a silent key move the first time somebody adds one for an unrelated reason.

What it costs: the Python name and the committed key now disagree, so a grep for the key finds the wire and not the code. That is the price of not migrating 15 published days, and the alias sits on the field where a reader of the model meets it.

## One word per thing, in every identifier - and plain sentences everywhere else

The section above rules on *when* a name may move. This one rules on *which word* it moves to.

**The project's word for a thing is used verbatim in every identifier for that thing.** That binds a module filename, a class, a function, an enum member, a contract field, a schema stem, a telemetry value, a config key, a CLI verb and a prompt filename. Casing follows the language - `VisualPlan` in Python, `visual_state` in a payload key, `visualState` in TypeScript - and the word does not change between them.

**Prose is not bound, and trying to bind it makes the writing worse.** A sentence in a doc, a plan-doc, a commit message or a code comment uses the plain register (`CLAUDE.md` section 0b). "the validator", "the planner", "what the stage spent" are correct English and correct here. A decision record that writes `Visual Plan` in every sentence reads like a specification, and this project does not write specifications.

Two more clauses, and each one has already cost a day:

- **A model's size, vendor or revision never appears in an identifier.** `models.summarize` names the role; which weights fill it is a value in `config/`, and a knob called `models.qwen9b` would have to be renamed the day the weights change. A **filename** under `config/models/` is not an identifier - it names one set of weights and is meant to, which is why `models_file` is the whole swap and no code may compare against what it says (`backend/tests/test_summarize.py::test_no_module_that_opens_a_model_branches_on_which_model_it_is`).
- **A word that is wrong is renamed early, not when it is convenient.** `route` named a dispatch decision and the stage makes a planning decision. It reached a module, a contract, a schema stem, two config keys, a workflow job, an enum member, two TypeScript fields and about two hundred sentences before anybody paid it off. Every plan written against the wrong word writes more of it, so the bill grows with the calendar and never with the difficulty.

Two names in this repository do not take the word a glossary would give them, recorded here so they are not argued twice. **`visual_planner.py`** is the module filename, decided ahead of any glossary because a glossary names steps and not files; the stage it was named for retired on 2026-09-13 and the file kept the name, because what it still holds is the gate and the ladder that decide a picture. **`density_floor`** was chosen over the more formal term outright, by the owner.

**A definition that turns out to be false does not stop the term binding.** `Ledger` is defined as "never edited in place" and the corpus window rewrites at its edge. The word is still the identifier; the narrowed definition on the page that owns it governs what it means. Narrow the definition there rather than minting a second word.

## One serialization, so a round-trip is byte-identical

Every persisted payload is written by one function: **sorted keys, two-space indent, ASCII-escaped, one trailing newline, LF.** Three things fall out of that, and all three are load-bearing:

- A payload that is read and re-written is byte-identical, so a re-run that changed nothing produces an empty diff.
- A diff shows a **changed value** rather than a reshuffled dict, which is what makes reviewing a committed payload possible at all.
- The drift gate can compare bytes rather than parsed structures.

**One payload takes the indent out, and only the indent.** `SearchIndex` serializes through `compact_json`, which is the same function with `separators` closed up: still sorted keys, still ASCII-escaped, still one trailing newline, so all three properties above still hold. It is the one payload a reader downloads whole with entries counted in thousands, and the indent roughly doubles it for whitespace nobody reads. Every other payload keeps the indent, because being able to review a committed diff by eye is worth more than its bytes.

**Three payloads move where the newlines go, and only that.** `Sources`, `Taxonomy` and `Watchlist` serialize through `records_json`: sorted keys, two-space indent, ASCII-escaped, one trailing newline, all as above, with one rule added - **a list of objects is written one object a line.** All three are curated by a person rather than written by a program, and a record's fields mean nothing apart: an id without its vertical, a tier without its title, a word without the sentence the model reads it by. At a field a line, the 215 feeds in `config/sources.json` were 2,391 lines and the 24 words in `config/taxonomy.json` were 359, so comparing two records meant scrolling past everything they agree on and adding one was a twelve-line diff. At a record a line they are 226 and 33, the whole record is in view, and the diff is one line per record changed. A taxonomy record is the widest thing here, because a lens carries its definition sentence and up to nineteen keywords: six lines run past 400 characters and the longest is 535. That is the price of holding a word and the terms it matches on one line, and it is the right trade - the terms are what the word IS. Every payload a program writes keeps the field-a-line layout, which is the right shape for reading down a single record.

**The layout is held still by a test, because nothing else can hold it.** Every layout parses to the same payload, so a hand edit that indents one record across ten lines is invisible to a schema and to every reader. `backend/tests/contracts/test_curated_registries.py` asserts the committed bytes are what the contract's own writer produces, and separately counts the record lines in the file - the first catches a drifting edit, the second catches the day the writer itself changes shape. Both are parametrized over one mapping, so a fourth curated registry is one entry rather than a fourth pair of tests. A field is spelled out even when it holds its default, so what a curator reads is what the model holds.

Timestamps are pinned as text - UTC, second precision, `Z` - rather than as a date type, for the same reason: one spelling, no offset ambiguity, and no serializer whose formatting can drift underneath a committed file.

## A derived value is rebuilt on read, never trusted

Where a field is a function of other fields on the same payload, the model recomputes it during validation and rejects a payload whose stored value disagrees:

- `url_key` is the sha256 of `canonical_url`. It is item identity for dedupe and skip, it is a **field and never a path segment**, and a payload that carries someone else's key does not load.
- `hhem_delta` is `hhem - hhem_full`. The truncation signal cannot be silently wrong.
- `output_digest` is the sha256 of the summary and its key points - the published words only, so a re-run that produced the same text in a different wall-clock does not read as drift.
- `pipeline_fingerprint` was the sha256 of the `PipelineInputs` model's own serialization. Nothing has written it since 2026-09-12, and on 2026-09-13 it was removed from every shape except `EvalRow`, which keeps it because the console still reads that column for days committed before the cutover. The same inputs are recorded by name on the run record. See [determinism.md](determinism.md).

The alternative - trusting the stored value - makes a stale derived field indistinguishable from a correct one, and the mismatch surfaces months later as a dedupe that quietly stopped working.

## Cross-field invariants are why these are models and not schemas

The shapes carry rules a JSON Schema cannot express, and each one is a defect class that would otherwise be found in production:

- An `ok` article carries title and text; a failed one records why. One field cannot mean both.
- `truncated` and `truncated_at_tokens` are set together.
- A visual decided to `none` carries no spec, and only a rendered visual carries an asset path.
- A retired vertical, lens, feed or entity carries its retirement date - the tombstone that keeps old payloads valid.
- The lens and event vocabularies must be labelled exactly once each, so adding an enum member without a display name fails at load.
- A run manifest's two runs never share an ordinal, and its counts reconcile. The numbers may skip: runs land in parallel, so no writer can know what the next one is.
- **In a day payload, `introduced_by_run` may never decrease down the item list.** A later run appends; it never reorders what a reader already read. That is the published-layout rule made mechanical rather than trusted to the assemble stage.
- **A revised item names the run that rewrote it.** `updated_at` and `updated_by_run` are set together, the revising run cannot precede the introducing one, and neither may name a run the day did not record. The manifest names the model per run, so an item's words stay joinable to the model that wrote them after a later run rewrites them.

## Four things that bite when you change a model

- **Adding or removing a field - even an optional one with a default - breaks every fixture of that model.** The serializer emits exactly the model's keys, so the byte-identical round-trip test fails on every committed fixture at once, and a removed field additionally fails validation because the models forbid unknown keys. Update them in the same commit, respecting sorted key order. A run of fixture failures right after a field change is the expected signal, not a regression to hunt.
- **A same-day second revision stamps `version` to the minute**, `YYYY-MM-DDTHH:MM`. That string sorts *after* the bare `YYYY-MM-DD` of the same day, which is exactly what the newest-first `changelog` needs - the revision lands at the top rather than under the entry it supersedes. The base model enforces newest-first **and distinct** at class definition, so two branches that both stamp today's bare date on one contract produce a module that raises `TypeError` on import and takes the whole suite with it. When several branches will touch one contract, stamp to the minute from the first of them.
- **pydantic-core's regex engine has no look-around.** It is the Rust engine, not Python's `re`. A `StringConstraints(pattern=...)` containing `(?!` or `(?<=` raises `SchemaError` when the class is built, so the failure arrives at import time rather than at validation. Spell an explicit segment grammar instead of a negative lookahead.
- **A pattern on a shape the decoder sees must bound its own length.** `llama.cpp`'s schema-to-grammar converter honours a `pattern` **or** a length bound, never both, and the pattern wins. So `maxLength: 22` beside `^[a-z]+-...$` is dropped on the way to the grammar, and the decoder is handed a state with no exit it will ever choose - `[a-z]+` admits no space and no capital, so a model writing an English phrase cannot leave it. One reply on 2026-09-14 wrote 15,472 characters into that 22-character field and burned 15.8 minutes of a 4 vCPU runner, on an item that had already decided it wanted no picture. That makes a loose quantifier an availability surface reachable from any fetched page ([../sources/trust-boundary.md](../sources/trust-boundary.md)), so `backend/tests/contracts/test_decoder_grammar.py` builds every schema the pipeline sends a decoder, walks every string, and fails on any `pattern` holding `+`, `*` or `{n,}`. Write `{1,8}` rather than `+`, and derive the number from whatever really bounds it.
- **Generate the schema in validation mode, not serialization mode.** `model_json_schema(mode="serialization")` marks every field required, which would make "a config file may omit a knob" a lie in the published schema. The exporter uses validation mode and post-processes only `version`.
- **`DateStamp` counts digits and nothing else.** `DATE_PATTERN` in `backend/idhazh/contracts/base.py` is `^\d{4}-\d{2}-\d{2}$`, so `2026-13-45` is a valid `DateStamp` everywhere in this repository, and the caller that reaches for `date.fromisoformat` is where it finally fails - with a bare `ValueError` naming neither the field nor the payload. The pattern cannot bound a month or a day without look-around, which pydantic-core's engine does not have, so the check belongs to whichever function turns the string into a date. **A field typed `DateStamp` is not a field that has been checked**; bound it where you use it, and say so on the line.

## `$id` is relative, on purpose

Each generated schema's `$id` is its own filename, not a URL. An editor's JSON Schema plugin then resolves it offline, with no network call and nothing to 404 - which matters because a schema that only validates when the internet is up is a schema nobody runs.

## The drift gate

CI regenerates both outputs and fails on any diff. This is what makes "never hand-edit a generated artifact" enforceable rather than aspirational.

Two conditions have to hold for the gate to be trustworthy:

- **The generators are deterministic** - stable key ordering, stable formatting. A generator whose output shuffles produces a gate that fails at random and is switched off within a week.
- **The stored bytes match the emitted bytes.** Generated files are pinned to LF in `.gitattributes`, so the gate does not fail purely because a contributor's checkout settings differ.

A clean regeneration proves that schemas match models, not that an edit stayed
in scope. Compare parsed schema trees before and after the change, including
every value nested under `changelog`. Searching diff lines for the `version`
and `changelog` keys misses a changed sentence whose key line did not move.

The backend half is a contract-tier test: it regenerates every schema into a temporary directory and compares bytes against what is committed. It additionally asserts that `schemas/` holds **exactly** the generated set, so retiring a contract cannot leave a stale schema behind for something to keep validating against. `backend/tests/contracts/test_typescript_contracts.py` asks the same two questions of `frontend/src/contracts/`, and adds the one the byte comparison cannot answer: it widens a model in memory and asserts the emitted TypeScript changed, so a generator that stopped reading the model would be caught by a test rather than by a reader.

## The persisted surfaces

The shapes this subsystem owns. `CLAUDE.md` section 11 states the three rules that bind them; this is the list:

| Surface | Written by | Read by |
| --- | --- | --- |
| **Stage payloads** | Each pipeline stage | The next stage, and any re-run |
| **The eval ledger** | The evaluate stage, appended | The dashboard, and any trend query |
| **The fingerprint ledger** | Nothing since 2026-09-12 | Anyone reading the ten rows it already holds |
| **The source ledgers** | Plan and assemble, appended | The next run, deciding an article's age, whether it already ran, and whether a feed should rest |
| **The run manifest** | The assemble stage | A later run, and anyone auditing what produced what |
| **Config** | A human | Both `backend/` and, where a surface needs it, `frontend/` |
| **Published payloads** | The assemble stage | The published site |

## Run manifest count windows

`RunManifest.runs[]` is one record per run. All counts inside that record use
that same window.

- `items_planned`, `items_succeeded`, `items_failed` and `items_skipped` count
 only that run.
- `verticals[].planned` counts the items that run planned for that vertical.
- `verticals[].published` counts the items that run introduced into the day
 payload for that vertical.

The whole-day count lives in `digest.json`: `items.length` and
`verticals[].count`. A later run appends to the day payload, but it must not make
an earlier run's plan look larger than it was.

## Design rationale

Generating the schemas and the frontend types from one hand-written model, and gating on regeneration, exists because the alternative - keeping a Python model, a JSON Schema and a TypeScript interface in step by hand - fails silently and always in the same way: two of the three agree, the third is edited in a hurry, and the mismatch surfaces as a runtime error in the surface furthest from the change. The cost is a generator and a CI step; the benefit is that the mismatch class stops existing. Authority: Fowler ([../../../.github/agents/fowler.agent.md](../../../.github/agents/fowler.agent.md)).

Making `version` a date-stamp rather than an integer is a small choice with a specific payoff: when an old payload turns up, the question is always "how old is this shape?", and an integer cannot answer it without consulting a table. Authority: Fowler.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Hand-write the JSON Schemas | Not authorable at scale, no cross-field invariants, no edit-time checking, and it still has to be kept in step with the producer. | Fowler |
| Generate the Pydantic models from the schemas | Reverses the direction: the readable, invariant-carrying artifact becomes the generated one, and the invariants have nowhere to live. | Fowler |
| Integer schema versions | Not self-documenting. The date-stamp is ASCII-sortable and answers the question a reader of an old payload actually has. | Fowler |
| Absolute URL `$id` | Makes offline validation depend on a network fetch, and on a URL that has to keep resolving forever. | Carmack |
| Skip the drift gate and rely on discipline | Discipline is not a control. The gate is what makes the no-hand-editing rule real. | Fowler |

## See also

- [determinism.md](determinism.md) - what a run records about its own inputs, and the one alarm built on it.
- [../extraction/elements.md](../extraction/elements.md) - the element shape: six kinds, two tiers, and why the verbatim slice is called `span_excerpt`.
- [../sources/freshness.md](../sources/freshness.md) - why the published ledger files by day, and what its cover buys.
- [../sources/item-health.md](../sources/item-health.md) - the fastest-growing shard, and what would move it to a shorter period.
- [../../concepts/partitions.md](../../concepts/partitions.md) - the month partition as a pattern: the freeze rule, and the four cases an append-only writer gets wrong.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - what a read over a growing collection declares, and the three shapes a cover can take.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - the ledger sizes the shard rule is argued from.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the stages whose payloads these are.
- [../../concepts/config.md](../../concepts/config.md) - config as a versioned contract like any other.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - the event envelope, which is deliberately not one of these shapes.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - the eval ledger row.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #3, section 1a, section 4, section 11.
