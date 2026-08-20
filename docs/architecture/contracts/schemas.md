# Contracts and Schemas

**Last Updated**: 2026-08-20

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
| `backend/idhazh/contracts/base.py` | The base model every persisted shape inherits: the `version` date-stamp, the `changelog` array, the invariant that `version` equals the newest changelog entry, the name-to-schema-stem mapping, and the JSON Schema emitter. |
| `backend/idhazh/contracts/<name>.py` | One module per persisted shape. |
| `backend/idhazh/contracts/export.py` | Walks the models and writes `schemas/`. |
| `schemas/<name>.schema.json` | Generated. One flat file per model. |
| `frontend/src/contracts/` | Generated TypeScript types and runtime validators. |

`backend/idhazh/contracts/` **must not import any other subpackage** of `backend/idhazh/`. Contracts are the bottom of the dependency graph; everything else depends on them (`CLAUDE.md` section 4). A contract that imports a stage is a contract that cannot be loaded by a test of that stage.

## Every contract carries version and changelog

Inherited from the base model, per `CLAUDE.md` section 11:

- `version` is a **date-stamp** (`YYYY-MM-DD`, extended to the minute for same-day revisions), never an integer and never an epoch. It says *when* the shape last moved, which is the question anyone reading an old payload actually has.
- `changelog` is newest-first, each entry `{ version, change, why }`.
- The base model **enforces** that `version` equals `changelog[0].version`, so the two cannot fall out of step.

Additive change: append the entry, stamp today, done - older payloads still validate. Breaking change: append, stamp today, **and write the read-side migration in the same commit.** A payload written by yesterday's run that today's build cannot read is a release blocker.

## `$id` is relative, on purpose

Each generated schema's `$id` is its own filename, not a URL. An editor's JSON Schema plugin then resolves it offline, with no network call and nothing to 404 - which matters because a schema that only validates when the internet is up is a schema nobody runs.

## The drift gate

CI regenerates both outputs and fails on any diff. This is what makes "never hand-edit a generated artifact" enforceable rather than aspirational.

Two conditions have to hold for the gate to be trustworthy:

- **The generators are deterministic** - stable key ordering, stable formatting. A generator whose output shuffles produces a gate that fails at random and is switched off within a week.
- **The stored bytes match the emitted bytes.** Generated files are pinned to LF in `.gitattributes`, so the gate does not fail purely because a contributor's checkout settings differ.

## The persisted surfaces

The shapes this subsystem owns, from `CLAUDE.md` section 11:

| Surface | Written by | Read by |
| --- | --- | --- |
| **Stage payloads** | Each pipeline stage | The next stage, and any re-run |
| **The eval ledger** | The evaluate stage, appended | The dashboard, and any trend query |
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

- [../../concepts/pipeline-loop.md](../../concepts/pipeline-loop.md) - the stages whose payloads these are.
- [../../concepts/config.md](../../concepts/config.md) - config as a versioned contract like any other.
- [../../concepts/telemetry.md](../../concepts/telemetry.md) - the event envelope, one of these shapes.
- [../../concepts/evaluation.md](../../concepts/evaluation.md) - the eval ledger row.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Holy Law #3, section 1a, section 4, section 11.
