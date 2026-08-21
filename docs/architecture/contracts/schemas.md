# Contracts and Schemas

**Last Updated**: 2026-08-21

The persisted-shape subsystem: where the models live, how the schemas and frontend types are generated from them, and the gate that stops the three from drifting apart. This is the operational home of Holy Law #3 (contracts before logic) and `CLAUDE.md` sections 1a and 11.

Concept-level *why* lives in [../../concepts/principles.md](../../concepts/principles.md) (principle 4). This page is the *shape*.

## One source of truth, two generated outputs

```
backend/idhazh/contracts/*.py        <- Pydantic models. HAND-WRITTEN. The source of truth.
        |
        +--> schemas/*.schema.json           <- GENERATED. Never hand-edited.
                  |
                  +--> frontend/src/contracts/*.d.ts + validators   <- GENERATED. Never hand-edited.
```

The direction is one-way and never reversed. To change a persisted shape you edit the Pydantic model and regenerate; editing a generated artifact is an anti-pattern (`CLAUDE.md` section 10) and the drift gate will fail it anyway.

## Why the models, and not the schemas, are the source

A JSON Schema is a good interchange format and a poor authoring format: it cannot express a cross-field invariant readably, it has no place to put a validator, and nobody catches a typo in it at edit time. A Pydantic model is typed at authoring time, carries its invariants as code, and is directly usable by the producer that writes the payload. Generating downward from it means the validation the backend enforces and the types the frontend trusts cannot disagree.

## Layout

| Path | Holds |
| --- | --- |
| `backend/idhazh/contracts/base.py` | The shared string types, the canonical serializer, and the two base models: `Model` for a nested shape and `Contract` for a top-level persisted document. `Contract` owns the `version` date-stamp, the `changelog` tuple, the invariant that `version` equals the newest changelog entry, the `<stem>.schema.json` name, and the JSON Schema emitter. |
| `backend/idhazh/contracts/<name>.py` | One module per persisted shape. |
| `backend/idhazh/contracts/export.py` | Walks the models and writes `schemas/`. Also the list of what a schema directory is allowed to contain. |
| `schemas/<name>.schema.json` | Generated. One flat file per model. |
| `frontend/src/contracts/` | Generated TypeScript types and runtime validators. |

The eleven shapes, and where each one lives once written:

| Model | Schema | Persisted as |
| --- | --- | --- |
| `AppConfig` | `app-config` | `config/idhazh.json` |
| `Sources` | `sources` | `config/sources.json` |
| `Taxonomy` | `taxonomy` | `config/taxonomy.json` |
| `Watchlist` | `watchlist` | `config/watchlist.json` |
| `Article` | `article` | one file per item under the run directory |
| `Summary` | `summary` | one file per item under the run directory |
| `Route` | `route` | one file per item under the run directory |
| `EvalRow` | `eval-row` | one appended row of `evals/scores.csv` |
| `FingerprintRow` | `fingerprint-row` | one appended row of `evals/fingerprints.csv` |
| `RunManifest` | `run-manifest` | `.../<DD>/run.json`, append-only per date |
| `DigestDay` | `digest-day` | `.../<DD>/digest.json` and each `run-<N>.json` |

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
| **The run manifest** | The assemble stage | A later run, and anyone auditing what produced what |
| **Config** | A human | Both `backend/` and, where a surface needs it, `frontend/` |
| **Published payloads** | The assemble stage | The published site |

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
- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the stages whose payloads these are.
- [../../concepts/config.md](../../concepts/config.md) - config as a versioned contract like any other.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - the event envelope, one of these shapes.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - the eval ledger row.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Holy Law #3, section 1a, section 4, section 11.
