# Config

**Last Updated**: 2026-08-21

Where tunable behaviour lives, and the rule that separates a knob from an identifier. Config-driven with sane defaults is a project principle ([principles.md](principles.md), Holy Law #6): a fresh clone runs on the defaults, and no threshold, cap or source list is hardcoded in code.

## What `config/` is

`config/` holds **human-edited, schema-validated tunable knobs**. Both sides read it: `backend/` at build time, and `frontend/` wherever a published surface needs one. Every config file conforms to a typed model in `backend/idhazh/contracts/` before the logic that reads it exists, and to the schema generated from it ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)). A config file that fails its schema fails the build (`CLAUDE.md` section 1a).

Config is a **persisted contract like any other**: it is version-stamped and changelogged, and a breaking change ships with its read-side migration in the same commit (`CLAUDE.md` section 11). A knob is not exempt from the contract discipline just because a human types it.

## What belongs in a knob

The test is simple: **would a reasonable operator ever want a different value without changing behaviour that is a fact rather than a preference?**

Knobs, by the surface they tune:

- **Sources** - which feeds or listings are consulted, and the filters a candidate link must survive.
- **Extraction** - the truncation cap, the retry budget, backoff, and what counts as an oversized body.
- **Model** - which model reference and quantisation, the context size, thread count, and the sampling parameters that pin determinism.
- **Evaluation** - the confidence band thresholds, the truncation-gap threshold, the expected compression range, and the spot-check sample size ([evaluation.md](evaluation.md)).
- **Run shape** - the daily item cap, the batch size, per-job timeouts, and concurrency ([pipeline-loop.md](pipeline-loop.md)).
- **Drift** - the alert thresholds and the schedule ([evaluation.md](evaluation.md)).
- **Logging** - the level, and which events emit ([telemetry.md](telemetry.md)).

These are the *surfaces*, not a field list. The field-level truth is `schemas/app-config.schema.json`, generated from the model - read it there rather than restating it here, because a list copied into prose is a list that goes stale.

The knobs are spread across four files rather than one, along the line of who edits them and how often: `config/idhazh.json` for behaviour, and `config/taxonomy.json`, `config/sources.json` and `config/watchlist.json` for the source model ([../architecture/sources/discovery.md](../architecture/sources/discovery.md)). Curating a feed list and tuning a threshold are different activities with different review cadences, and putting them in one file means every feed addition touches the file that also holds the decoding parameters.

Every knob ships a sane default. The only values with no default are the model references, because there is no honest default for "which weights" - a wrong guess would silently run the wrong model rather than failing.

## What is NOT a knob

Not everything variable is tunable. Two categories stay out of `config/`:

- **Facts, not preferences.** The runner's core count, the 6 h job cap and the 10 GB cache ceiling are properties of the platform (Holy Law #2). Making them configurable would imply they can be chosen.
- **Identifiers.** Stage names, event names, route kinds and score-band names are schema-validated enums defined in the contracts. Code references them; they never change to match a label.

The distinction matters because a value in `config/` reads as an invitation to change it.

## Build-time config versus shipped config

Most knobs are read only by the producer and never reach a reader: source lists, model references, batch sizes, timeouts, retry budgets. Shipping those into the published bundle would be dead bytes and a muddled surface.

A knob is shipped **only** when a published surface genuinely needs it - for example, how the dashboard buckets the ledger it renders. When that happens the value is *imported into the bundle at build time*, never fetched at read time: it is tiny, it is needed before the first paint, and fetching it would put a round trip on the critical path for something that cannot change between builds.

## Design rationale

Keeping tunables in schema-validated files rather than in code exists so that tuning the system never requires reading it, and so that a change of threshold is a reviewable one-line diff with a date on it rather than an archaeological dig. Treating config as a versioned contract - rather than as "just a JSON file" - is what stops a silently-renamed key from failing a run at 6 a.m. on a Sunday. Authority: Fowler ([../../.github/agents/fowler.agent.md](../../.github/agents/fowler.agent.md)).

Excluding the runner's ceilings is the less obvious half. They look exactly like knobs and are not: a configurable job timeout invites someone to raise it rather than fix the batch size, which is precisely the reasoning Holy Law #2 exists to prevent. Authority: Carmack.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Fetch `config/*.json` from the published site at read time | A round trip on the critical path for about a kilobyte, plus a request that can fail, to load something that never changes between builds. | Carmack |
| Copy config into the published directory at build time | Two copies of one file, free to drift, with nothing gating them. | Fowler |
| Environment variables for pipeline tunables | Invisible in review, unversioned, and undiffable. A knob nobody can see the history of is a knob nobody can trust. | Fowler |
| Put the runner's ceilings in config | They are platform facts, not preferences, and making them editable invites raising the budget instead of simplifying the feature. | Carmack |

## See also

- [principles.md](principles.md) - config-driven with sane defaults.
- [pipeline-loop.md](pipeline-loop.md) - the stages these knobs tune.
- [evaluation.md](evaluation.md) - the bands and thresholds.
- [telemetry.md](telemetry.md) - the logging knobs.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the schema every config file conforms to.
- [../agents/guardrails.md](../agents/guardrails.md) - the identifier-and-config discipline.
