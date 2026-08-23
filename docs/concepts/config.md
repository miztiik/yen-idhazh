# Config

**Last Updated**: 2026-08-23

Where tunable behaviour lives, and the rule that separates a knob from an identifier. Config-driven with sane defaults is a project principle ([principles.md](principles.md), Rule #6): a fresh clone runs on the defaults, and no threshold, cap or source list is hardcoded in code.

## What `config/` is

`config/` holds **human-edited, schema-validated tunable knobs**. Both sides read it: `backend/` at build time, and `frontend/` wherever a published surface needs one. Every config file conforms to a typed model in `backend/idhazh/contracts/` before the logic that reads it exists, and to the schema generated from it ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)). A config file that fails its schema fails the build (`CLAUDE.md` section 1a).

Config is a **persisted contract like any other**: it is version-stamped and changelogged, and a breaking change ships with its read-side migration in the same commit (`CLAUDE.md` section 11). A knob is not exempt from the contract discipline just because a human types it.

## What belongs in a knob

The test is simple: **would a reasonable operator ever want a different value without changing behaviour that is a fact rather than a preference?**

Knobs, by the surface they tune:

- **Sources** - which feeds or listings are consulted, and the filters a candidate link must survive.
- **Extraction** - the truncation cap, the retry budget, backoff, what counts as an oversized body, shape-signal thresholds, shape enforcement switches, and paywall fallback markers.
- **Model** - which model reference and quantisation, the context size, thread count, and the sampling parameters that pin determinism.
- **Evaluation** - the confidence band thresholds, the truncation-gap threshold, the expected compression range, and the spot-check sample size ([evaluation.md](evaluation.md)).
- **Run shape** - the safety ceiling, the batch size, per-job timeouts, and concurrency ([pipeline-loop.md](pipeline-loop.md)).
- **Drift** - the alert thresholds and the schedule ([evaluation.md](evaluation.md)).
- **Logging** - the level, and which events emit ([telemetry.md](telemetry.md)).

These are the *surfaces*, not a field list. The field-level truth is `schemas/app-config.schema.json`, generated from the model - read it there rather than restating it here, because a list copied into prose is a list that goes stale.

The knobs are spread across four files rather than one, along the line of who edits them and how often: `config/idhazh.json` for behaviour, and `config/taxonomy.json`, `config/sources.json` and `config/watchlist.json` for the source model ([../architecture/sources/discovery.md](../architecture/sources/discovery.md)). Curating a feed list and tuning a threshold are different activities with different review cadences, and putting them in one file means every feed addition touches the file that also holds the decoding parameters.

Every knob ships a sane default. The only values with no default are the model references, because there is no honest default for "which weights" - a wrong guess would silently run the wrong model rather than failing.

Extraction has three shape and access controls:

- `extract.prose_sentence_min` and `extract.prose_sentence_words_min` decide when text carries `not_prose`.
- `extract.boilerplate_ratio_max` decides when sibling-shared lines carry `boilerplate`.
- `extract.paywall_markers` is the fallback when JSON-LD does not declare a paywall.

Two enforcement switches default to false: `extract.reject_not_prose` and
`extract.reject_boilerplate`. False means record the signal and publish. True
means reject the item as a listing. `extract.min_source_words` now marks the
brief tier. It does not reject the item.

## What is NOT a knob

Not everything variable is tunable. Two categories stay out of `config/`:

- **Facts, not preferences.** The runner's core count, the 6 h job cap and the 10 GB cache ceiling are properties of the platform (Rule #2). Making them configurable would imply they can be chosen.
- **Identifiers.** Stage names, event names, route kinds and score-band names are schema-validated enums defined in the contracts. Code references them; they never change to match a label.

The distinction matters because a value in `config/` reads as an invitation to change it.

## A guard is not a limit, and its name has to say so

Some numbers in `config/` are not there to be tuned. They are there to stop a bug running for six hours. A guard and a limit look identical in JSON, so the name and the comment carry the whole difference:

- `run.safety_ceiling_per_run` (200) is a **crash guard**. A normal run is nowhere near it. If a canonicalisation bug ever produces thousands of candidates, the run stops instead of discovering that slowly. Hitting it means find the bug, not raise the number. It replaced a daily item cap, which was a limit pretending to be a guard - see [../architecture/sources/freshness.md](../architecture/sources/freshness.md).
- `models.inference.max_output_tokens` (900) is a **crash guard**. It stops a runaway decode from burning a shard's whole timeout. It is not a length target: the length a summary should be is set by the word bands in `summarize.bands`, which is the knob a person actually wants ([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)). It was 250, and at 250 the reply ran out of budget mid-object and failed as a *shape* error - which named the wrong cause and sent the reader of that failure looking at the decoder. It now sits well above any summary we would want.
- `models.inference.request_timeout_minutes` (22.1) is a **per-request guard**. It limits one summarizer POST, not the shard. It protects the day from one local model request that accepts a connection and never replies: that item records `model_unreachable`, and the worker continues. The default is sized from the authoritative runner measurements in [../reference/measurements.md](../reference/measurements.md): the worst 8B long article plus one cold prompt prefix, doubled. `run.shard_timeout_minutes` stays the outer bound for the whole shard.

A guard set near the working range is the worst of both. It fires on good runs, gets raised to stop the noise, and stops guarding anything. That is the failure the token cap actually had.

## A knob nothing reads is deleted

A knob that no code path reads is worse than clutter. It reads as a control, so the next person to open the file sizes the system by what the knobs claim - and eventually somebody changes one and waits for an effect that never arrives.

Three were removed this way, each describing a mechanism that does not exist:

- `collect.min_feeds_floor` claimed to be the default feed floor. The floor a vertical is actually held to is its own `min_feeds` in `taxonomy.json`. Nothing read the default.
- A per-feed `weight` on a salience feed. What an aggregator vote is worth is `collect.front_page_bonus`, one number for every aggregator. An aggregator has no subject taxonomy to be graded on, so there was nothing for a per-feed weight to express. **The feed weight on ordinary sources is untouched and load-bearing** - it multiplies the tier score ([../architecture/sources/discovery.md](../architecture/sources/discovery.md)).
- `Sources.live_feeds_for`, a method with no caller that also disagreed with the code doing the job: it honoured `retired_on` and ignored `status`, so it would have read a draft feed. One concept, one home.

### Removing a config field is breaking, and its migration is the file

Deleting a key is a breaking schema change like any other, so it ships a changelog entry and a version stamp (section 11).

The read-side migration is unusual and worth stating once: **for a config contract, the migration is the config edit in the same commit.** No run writes these files - a person does - so there is no back catalogue of old payloads to upgrade. There is one file per contract, and `extra="forbid"` fails loudly and by name if a stale key survives. A migration function would have nothing to migrate.

## Build-time config versus shipped config

Most knobs are read only by the producer and never reach a reader: source lists, model references, batch sizes, timeouts, retry budgets. Shipping those into the published bundle would be dead bytes and a muddled surface.

A knob is shipped **only** when a published surface genuinely needs it - for example, how the dashboard buckets the ledger it renders. When that happens the value is *imported into the bundle at build time*, never fetched at read time: it is tiny, it is needed before the first paint, and fetching it would put a round trip on the critical path for something that cannot change between builds.

## Design rationale

Keeping tunables in schema-validated files rather than in code exists so that tuning the system never requires reading it, and so that a change of threshold is a reviewable one-line diff with a date on it rather than an archaeological dig. Treating config as a versioned contract - rather than as "just a JSON file" - is what stops a silently-renamed key from failing a run at 6 a.m. on a Sunday. Authority: Fowler ([../../.github/agents/fowler.agent.md](../../.github/agents/fowler.agent.md)).

Excluding the runner's ceilings is the less obvious half. They look exactly like knobs and are not: a configurable job timeout invites someone to raise it rather than fix the batch size, which is precisely the reasoning Rule #2 exists to prevent. Authority: Carmack.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Fetch `config/*.json` from the published site at read time | A round trip on the critical path for about a kilobyte, plus a request that can fail, to load something that never changes between builds. | Carmack |
| Copy config into the published directory at build time | Two copies of one file, free to drift, with nothing gating them. | Fowler |
| Environment variables for pipeline tunables | Invisible in review, unversioned, and undiffable. A knob nobody can see the history of is a knob nobody can trust. | Fowler |
| Put the runner's ceilings in config | They are platform facts, not preferences, and making them editable invites raising the budget instead of simplifying the feature. | Carmack |
| Keeping a dead knob "in case it is wanted later" | It reads as a control. The next person sizes the system by what the knobs claim, and one of them is a lie. | Fowler |
| A daily item cap as the run-shape knob | It decides how many good articles a day may have before knowing what the day contains. The safety ceiling catches the failure a cap was accidentally also catching. | Reader |
| Using `max_output_tokens` as the summary length control | A length set by a token budget fails as a malformed object rather than as a long summary, so the error names the decoder instead of the prompt. | Andre |

## See also

- [principles.md](principles.md) - config-driven with sane defaults.
- [pipeline-loop.md](pipeline-loop.md) - the stages these knobs tune.
- [../architecture/sources/freshness.md](../architecture/sources/freshness.md) - the run cadence and the scoring knobs under `collect`.
- [../architecture/sources/health.md](../architecture/sources/health.md) - what `quarantine_after_failures` decides.
- [evaluation.md](evaluation.md) - the bands and thresholds.
- [telemetry.md](telemetry.md) - the logging knobs.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the schema every config file conforms to.
- [../agents/guardrails.md](../agents/guardrails.md) - the identifier-and-config discipline.
