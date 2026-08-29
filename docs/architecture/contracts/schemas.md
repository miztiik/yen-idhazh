# Contracts and Schemas

**Last Updated**: 2026-08-29

The persisted-shape subsystem: where the models live, how the schemas and frontend types are generated from them, and the gate that stops the three from drifting apart. This is the operational home of Rule #3 (contracts before logic) and `CLAUDE.md` sections 1a and 11.

Concept-level *why* lives in [../../concepts/principles.md](../../concepts/principles.md) (principle 4). This page is the *shape*.

## One source of truth, two generated outputs

```
backend/idhazh/contracts/*.py        <- Pydantic models. HAND-WRITTEN. The source of truth.
        |
        +--> schemas/*.schema.json           <- GENERATED. Never hand-edited.
                  |
                  +--> frontend/src/lib/payload/types.ts   <- mirrors the schema. HAND-WRITTEN, for now.
```

The direction is one-way and never reversed. To change a persisted shape you edit the Pydantic model and regenerate; editing a generated artifact is an anti-pattern (`CLAUDE.md` section 10) and the drift gate will fail it anyway.

**The third arrow is not automated yet, and that is a known gap.** `frontend/src/lib/payload/types.ts` is written by hand against `schemas/digest-day.schema.json`, so nothing stops the two drifting apart except a person noticing. The generator and the gate over it land with the rest of the frontend contract work. Until then the mirror is narrow on purpose - the published payload only, not all seventeen shapes - because a hand-kept mirror is only safe while it is small enough to read in one sitting.

## Why the models, and not the schemas, are the source

A JSON Schema is a good interchange format and a poor authoring format: it cannot express a cross-field invariant readably, it has no place to put a validator, and nobody catches a typo in it at edit time. A Pydantic model is typed at authoring time, carries its invariants as code, and is directly usable by the producer that writes the payload. Generating downward from it means the validation the backend enforces and the types the frontend trusts cannot disagree.

## Layout

| Path | Holds |
| --- | --- |
| `backend/idhazh/contracts/base.py` | The shared string types, the canonical serializer, and the two base models: `Model` for a nested shape and `Contract` for a top-level persisted document. `Contract` owns the `version` date-stamp, the `changelog` tuple, the invariant that `version` equals the newest changelog entry, the `<stem>.schema.json` name, and the JSON Schema emitter. |
| `backend/idhazh/contracts/<name>.py` | One module per persisted shape. |
| `backend/idhazh/contracts/export.py` | Walks the models and writes `schemas/`. Also the list of what a schema directory is allowed to contain. |
| `schemas/<name>.schema.json` | Generated. One flat file per model. |
| `frontend/src/lib/payload/types.ts` | The published payload's TypeScript shapes, mirroring `schemas/digest-day.schema.json`. Hand-written today, generated later. |

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
| `Route` | `route` | one file per item under the run directory |
| `EvalRow` | `eval-row` | one appended row of `state/scores.csv` |
| `FingerprintRow` | `fingerprint-row` | one appended row of `state/fingerprints.csv` |
| `SeenRow` | `seen-row` | one appended row of `state/seen/<YYYY-MM>.csv` |
| `PublishedRow` | `published-row` | one appended row of `state/published.csv` |
| `FeedHealthRow` | `feed-health-row` | one appended row of `state/feed-health/<YYYY-MM>.csv` |
| `ItemHealthRow` | `item-health-row` | one appended row of `state/item-health/<YYYY-MM>.csv` |
| `RuntimeCountersRow` | `runtime-counters-row` | one appended row of `state/runtime-counters.csv` |
| `ValidationRow` | `validation-row` | one appended row of `state/validation-<date>.csv` |
| `RunManifest` | `run-manifest` | `.../<DD>/run.json`, append-only per date |
| `DigestDay` | `digest-day` | `.../<DD>/digest.json` and each `run-<N>.json` |
| `SearchIndex` | `search-index` | `frontend/public/assist/index/<YYYY-MM>.json`, with its vectors in a sibling `.bin` |
| `CorpusRow` | `corpus-row` | one line of `corpus/corpus.jsonl` |
| `CorpusMeta` | `corpus-meta` | `corpus/corpus.meta.json` |

Everything under `state/` is a row contract rather than a file contract, because a file that is only ever appended to has no shape of its own - the row is the unit that has to hold. Which of those ledgers a later run reads back, and what each one answers, is [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md).

### A new row ledger ships with its header, not with its first run

`.github/scripts/commit-and-push.sh` runs under `set -euo pipefail` and stages every path a job owns in one `git add "$@"`. A path that is not in the checkout makes that call fail, and `set -e` then abandons the whole commit step - so a ledger that only appears once its producer has succeeded lets a broken producer cost the job the *other* ledgers it was staging beside it. `state/runtime-counters.csv` therefore ships as a header-only file, and a test asserts the committed header equals `RuntimeCountersRow.csv_columns()`.

That is not "pre-creating an empty module for later" (`CLAUDE.md` section 10). The file is the ledger, and its header is the contract's own column list; what is being avoided is a failure mode in the step that commits it.

The training corpus ships the same way and for the same reason: `corpus/corpus.jsonl` is committed empty, `corpus/corpus.meta.json` holds a zero census, and `corpus/holdout.txt` is empty. A test asserts all three are tracked.

### Two of these are contracts and are deliberately not migration surfaces

`EvidenceItem` and the two corpus shapes carry a `version` like everything else and owe no read-side migration when they change (section 11). Nothing they were written into survives: the oldest `EvidenceItem` that can exist is a 14-day workflow artifact, and the corpus is a rolling window regenerable from the run's own payloads whose history is rewritten every `finetune.prune_every_days`. A shape change there owes a re-run or a re-harvest. They are contracts under Rule #3 all the same, because each crosses a process boundary and something on the far side has to be able to refuse a file it cannot trust.

### A shard-grain fact is its own contract, not a field on the run manifest

`RuntimeCountersRow` could have been a list on `RunRecord`, and four things say it should not be. **Grain**: a manifest run record is one run and a counter snapshot is one shard, so the manifest would grow a variable-length list keyed by something it does not otherwise carry. **Producer**: the manifest is written by `assemble`, in another job hours later, so the numbers would have to travel inside the `items-*` artifact - which expires in a day and is not uploaded at all when a job is cancelled, and a cancelled shard's counters are the ones most worth having. **Audience**: `run.json` is a published payload a reader's browser fetches, and this is measurement evidence, which belongs under `state/` where nothing is served. **Timing**: a concurrent branch was also opening `RunManifest`, and two branches stamping one contract's changelog on the same date raise `TypeError` at import.

**The grain argument earned two more cells on 2026-08-29.** `job_seconds` and `cpu_model` are facts about the `work` job rather than about its model server, and they landed here rather than on the manifest for the first reason above: one run draws up to eight hosts and takes eight different clocks, so a manifest field would have to become a per-shard list - which is what this ledger already is. `docs/reference/measurements.md` owns what they measure and how to read them; the rollback rule for the truncation cap is the caller.

What would overturn it: a published surface that needs the counters, which would make them a published payload; or a run that stops being sharded, which would make shard grain and run grain the same thing and the manifest the cheaper home.

### A ledger shards by month only when its read carries a window

Some `state/` ledgers are one file and some are a directory of `<YYYY-MM>.csv`
shards. The rule is one question: **does the read that consumes this ledger
carry a time window?**

| Ledger | Layout | The question it answers | Windowed on read |
| --- | --- | --- | --- |
| `state/seen/` | monthly shards | how old is this address? | yes, `collect.seen_window_days` |
| `state/feed-health/` | monthly shards | is this source still working? | yes, `ledger.HEALTH_WINDOW_DAYS` |
| `state/item-health/` | monthly shards | what did every planned item do? | yes - the console pans a window (`default_window_days` 30) and fetches month shards |
| `state/published.csv` | one file | have we already published this? | no - published is forever |
| `state/fingerprints.csv` | one file | has this exact input run before? | no |
| `state/scores.csv` | one file | how did every scored item do? | no |
| `state/runtime-counters.csv` | one file | what did the model server itself count? | no - the audit reads one run |

A window turns a shard into a skipped file open. `ledger._shards_in_window`
walks the days the window can touch and opens only those stems, so a plan run
reads one or two files instead of every month the project has ever written. The
item-health shard boundary survives all the way to the browser: the projection
under `frontend/public/telemetry/` is written one file per month, so the console
fetches the months its window covers and no more.

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
  (`YYYY-Www.csv`) rather than losing rows - see
  [../sources/item-health.md](../sources/item-health.md). The readers glob the
  directory, so the period is a layout change and not a contract change.

Authority: Carmack (cache and shard economics), 2026-08-25.

The eval ledger and source-state CSV ledgers compare the committed header to the row contract before writing. A mismatch stops the append and tells the operator to migrate the ledger. Padding is forbidden: readers map cells by header position, so a stale header would put correct-looking names over the wrong values.

### Narrowing a row ledger is one commit, not three

A reader built on `csv.DictReader` maps cells by name off the file's own header, so dropping a column nothing reads changes no answer the reader gives. What refuses is the append: `require_matching_header` compares the committed header to the contract's columns and raises rather than write. That is called from `_append` and from nothing on the read path, so the model change and the file rewrite have to land together - and once they do there is no read-side transition left to stage, which is what removes the expand-migrate-contract sequence a breaking change usually needs.

The rewrite is a committed one-shot utility rather than an ad-hoc script, so a fork or a stale branch can reproduce the same migration. `backend/utilities/migrate_published_ledger.py` is the worked example: it refuses a ledger that is already narrow, and it refuses to write at all unless the rewritten file carries the same rows, in the same order, with the same values in the cells the read path opens. `PublishedRow` lost `canonical_url` this way on 2026-08-26 ([../sources/freshness.md](../sources/freshness.md)).

A migrated row keeps the `version` cell it was written with. The base contract accepts an older stamp on purpose, so a later read-side migration has something to branch on; restamping every row would erase the only marker of which rows predate the change.

### Widening a row ledger writes an empty cell, never a value invented today

Adding a column is the same commit shape as dropping one, and for the same reason: `require_matching_header` compares the header tuple exactly, so the contract change and the file rewrite land together or the next append stops the run.

What differs is the cell. A column is appended at the end of the row and never filed by meaning, because a cell inserted in the middle shifts every historical value one place right under a reader that maps by position. The new field is nullable, and every row that predates it gets an **empty** cell. Zero, or a value recomputed today, would claim the older run measured something it never looked at - and for a digest that is worse than silence, because the whole point of a digest is that somebody can check it.

The rewrite is small enough to be reviewed as a diff rather than run as a utility: the header gains one name and each row gains one comma, and nothing else in the file moves. `EvalRow` gained `self_repetition` this way on 2026-08-26 and `source_digest` on 2026-08-27. A committed test appends to a byte copy of the real ledger and asserts every historical cell is where it was, which is the check a fork actually needs.

`backend/idhazh/contracts/` **must not import any other subpackage** of `backend/idhazh/`. Contracts are the bottom of the dependency graph; everything else depends on them (`CLAUDE.md` section 4). A contract that imports a stage is a contract that cannot be loaded by a test of that stage.

## Every contract carries version and changelog

Inherited from the base model, per `CLAUDE.md` section 11:

- `version` is a **date-stamp** (`YYYY-MM-DD`, extended to the minute for same-day revisions), never an integer and never an epoch. It says *when* the shape last moved, which is the question anyone reading an old payload actually has.
- `changelog` is newest-first, each entry `{ version, change, why }`.
- The base model **enforces** that `version` equals `changelog[0].version`, so the two cannot fall out of step.

Additive change: append the entry, stamp today, done - older payloads still validate. Breaking change: append, stamp today, **and write the read-side migration in the same commit.** A payload written by yesterday's run that today's build cannot read is a release blocker.

A document that arrives without a `version` is stamped with the current one on read, so the generated schema marks the field optional-with-a-default rather than required. Everything this project writes emits it explicitly; the tolerance exists for a hand-edited config file, not as a licence to omit it.

## One serialization, so a round-trip is byte-identical

Every persisted payload is written by one function: **sorted keys, two-space indent, ASCII-escaped, one trailing newline, LF.** Three things fall out of that, and all three are load-bearing:

- A payload that is read and re-written is byte-identical, so a re-run that changed nothing produces an empty diff.
- A diff shows a **changed value** rather than a reshuffled dict, which is what makes reviewing a committed payload possible at all.
- The drift gate can compare bytes rather than parsed structures.

**One payload takes the indent out, and only the indent.** `SearchIndex` serializes through `compact_json`, which is the same function with `separators` closed up: still sorted keys, still ASCII-escaped, still one trailing newline, so all three properties above still hold. It is the one payload a reader downloads whole with entries counted in thousands, and the indent roughly doubles it for whitespace nobody reads. Every other payload keeps the indent, because being able to review a committed diff by eye is worth more than its bytes.

Timestamps are pinned as text - UTC, second precision, `Z` - rather than as a date type, for the same reason: one spelling, no offset ambiguity, and no serializer whose formatting can drift underneath a committed file.

## A derived value is rebuilt on read, never trusted

Where a field is a function of other fields on the same payload, the model recomputes it during validation and rejects a payload whose stored value disagrees:

- `url_key` is the sha256 of `canonical_url`. It is item identity for dedupe and skip, it is a **field and never a path segment**, and a payload that carries someone else's key does not load.
- `hhem_delta` is `hhem - hhem_full`. The truncation signal cannot be silently wrong.
- `output_digest` is the sha256 of the summary and its key points - the published words only, so a re-run that produced the same text in a different wall-clock does not read as drift.
- `pipeline_fingerprint` is the sha256 of the `PipelineInputs` model's own serialization, so a ledger row cannot claim a stamp its components do not produce. See [determinism.md](determinism.md).

The alternative - trusting the stored value - makes a stale derived field indistinguishable from a correct one, and the mismatch surfaces months later as a dedupe that quietly stopped working.

## Cross-field invariants are why these are models and not schemas

The shapes carry rules a JSON Schema cannot express, and each one is a defect class that would otherwise be found in production:

- An `ok` article carries title and text; a failed one records why. One field cannot mean both.
- `truncated` and `truncated_at_tokens` are set together.
- A visual routed to `none` carries no spec, and only a rendered visual carries an asset path.
- A retired vertical, lens, feed or entity carries its retirement date - the tombstone that keeps old payloads valid.
- The lens and event vocabularies must be labelled exactly once each, so adding an enum member without a display name fails at load.
- A run manifest's runs are numbered from one without gaps, and its counts reconcile.
- **In a day payload, `introduced_by_run` may never decrease down the item list.** A later run appends; it never reorders what a reader already read. That is the published-layout rule made mechanical rather than trusted to the assemble stage.
- **A revised item names the run that rewrote it.** `updated_at` and `updated_by_run` are set together, the revising run cannot precede the introducing one, and neither may name a run the day did not record. The manifest names the model per run, so an item's words stay joinable to the model that wrote them after a later run rewrites them.

## Four things that bite when you change a model

- **Adding or removing a field - even an optional one with a default - breaks every fixture of that model.** The serializer emits exactly the model's keys, so the byte-identical round-trip test fails on every committed fixture at once, and a removed field additionally fails validation because the models forbid unknown keys. Update them in the same commit, respecting sorted key order. A run of fixture failures right after a field change is the expected signal, not a regression to hunt.
- **A same-day second revision stamps `version` to the minute**, `YYYY-MM-DDTHH:MM`. That string sorts *after* the bare `YYYY-MM-DD` of the same day, which is exactly what the newest-first `changelog` needs - the revision lands at the top rather than under the entry it supersedes. The base model enforces newest-first **and distinct** at class definition, so two branches that both stamp today's bare date on one contract produce a module that raises `TypeError` on import and takes the whole suite with it. When several branches will touch one contract, stamp to the minute from the first of them.
- **pydantic-core's regex engine has no look-around.** It is the Rust engine, not Python's `re`. A `StringConstraints(pattern=...)` containing `(?!` or `(?<=` raises `SchemaError` when the class is built, so the failure arrives at import time rather than at validation. Spell an explicit segment grammar instead of a negative lookahead.
- **Generate the schema in validation mode, not serialization mode.** `model_json_schema(mode="serialization")` marks every field required, which would make "a config file may omit a knob" a lie in the published schema. The exporter uses validation mode and post-processes only `version`.

## `$id` is relative, on purpose

Each generated schema's `$id` is its own filename, not a URL. An editor's JSON Schema plugin then resolves it offline, with no network call and nothing to 404 - which matters because a schema that only validates when the internet is up is a schema nobody runs.

## The drift gate

CI regenerates both outputs and fails on any diff. This is what makes "never hand-edit a generated artifact" enforceable rather than aspirational.

Two conditions have to hold for the gate to be trustworthy:

- **The generators are deterministic** - stable key ordering, stable formatting. A generator whose output shuffles produces a gate that fails at random and is switched off within a week.
- **The stored bytes match the emitted bytes.** Generated files are pinned to LF in `.gitattributes`, so the gate does not fail purely because a contributor's checkout settings differ.

The backend half is a contract-tier test: it regenerates every schema into a temporary directory and compares bytes against what is committed. It additionally asserts that `schemas/` holds **exactly** the generated set, so retiring a contract cannot leave a stale schema behind for something to keep validating against. The frontend half lands with the frontend.

## The persisted surfaces

The shapes this subsystem owns, from `CLAUDE.md` section 11:

| Surface | Written by | Read by |
| --- | --- | --- |
| **Stage payloads** | Each pipeline stage | The next stage, and any re-run |
| **The eval ledger** | The evaluate stage, appended | The dashboard, and any trend query |
| **The fingerprint ledger** | Any stage writing under a new stamp, appended | A later run deciding whether to skip, and anyone auditing drift |
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

- [determinism.md](determinism.md) - the pipeline fingerprint, its ledger, and the skip rule built on it.
- [../sources/freshness.md](../sources/freshness.md) - why the published ledger is one file and its dedupe read has no window.
- [../sources/item-health.md](../sources/item-health.md) - the fastest-growing shard, and what would move it to a shorter period.
- [../../reference/measurements.md](../../reference/measurements.md) - the ledger sizes the shard rule is argued from.
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the stages whose payloads these are.
- [../../concepts/config.md](../../concepts/config.md) - config as a versioned contract like any other.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - the event envelope, one of these shapes.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - the eval ledger row.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #3, section 1a, section 4, section 11.
