# Config

**Last Updated**: 2026-09-23

Where tunable behaviour lives, and the rule that separates a knob from an identifier. Config-driven with sane defaults is a project principle ([principles.md](principles.md), Guardrail #6): a fresh clone runs on the defaults, and no threshold, cap or source list is hardcoded in code.

This page holds the rules every config file obeys. What one individual knob does is on the page that owns that surface, and the table under [Where a knob is written up](#where-a-knob-is-written-up) routes.

## What `config/` is

`config/` holds **human-edited, schema-validated tunable knobs**. Both sides read it: `backend/` at build time, and `frontend/` wherever a published surface needs one. Every config file conforms to a typed model in `backend/idhazh/contracts/` before the logic that reads it exists, and to the schema generated from it ([../architecture/contracts/schemas.md](../architecture/contracts/schemas.md)). A config file that fails its schema fails the build (`CLAUDE.md` section 1a).

Config is a **persisted contract like any other**: it is version-stamped and changelogged, and a breaking change ships with its read-side migration in the same commit (`CLAUDE.md` section 11). A knob is not exempt from the contract discipline just because a human types it.

### The file names every knob it owns, and a default is a floor rather than a hiding place

**`config/` is the one source: the committed file names every knob it owns, at the value in force.** A default in the model keeps a fresh clone running and nothing more. It does not tell the person reading `config/` that the knob exists, and a knob nobody can see is a knob nobody tunes - which is the same failure as [a knob nothing reads](#a-knob-nothing-reads-is-deleted), arriving from the other direction.

Measured 2026-09-17, before the rule was enforced: `idhazh.json` did not name **18** of the leaves it owns and `appearance.json` **2**, while the other four config files named all of theirs. Among the missing were `summarize.key_point_words_max` and `summarize.asks_for_a_visual_plan`, both load-bearing, and three `summarize.bands` entries that omitted `over_length_action` - a default nested inside a list entry, which is the shape that hides best and the reason the check reads leaf paths rather than top-level keys.

**Owns, not declares, and the difference is load-bearing.** Three blocks sit on two models, and only one file is their source: `appearance.json` owns everything the published surface draws, while `idhazh.json` keeps `ui`, `console` and `assist` as the read-side migration's middle layer. Filling those legacy blocks out to their model would give one knob two answers in two files - the frontend merges the appearance block over the legacy one, so the loser is edited and nothing happens. `CONFIG_NOT_OWNED` names each side's exclusions, derived from the `MOVED_BLOCKS` and `PIPELINE_OWNED` facts that already governed it.

`test_the_config_file_names_every_knob_it_owns` holds every file in `CONFIG_FILES` to this. The fix when it fails is never a hand edit: regenerate through the model, then put back what another file owns.

**What this costs, stated rather than implied.** `idhazh.json` grew from 9,499 to 10,133 bytes and `appearance.json` from 2,856 to 2,911. A reader now scrolls past knobs nobody has moved off their default. That is the price of the alternative being a control surface you can only discover by reading Python.

## Where a knob is written up

Seven pages, one question each. Arrive at the one holding your question and stop.

| Page | The question it answers |
| --- | --- |
| this one | What is a knob, what is not one, and what happens to one nothing reads |
| [config/model-file.md](config/model-file.md) | Which model runs, and what runtime settings and turn markers are declared for those exact bytes |
| [config/appearance.md](config/appearance.md) | What a reader's page and an operator's console are drawn from, and which file owns a key two files name |
| [config/summary-length.md](config/summary-length.md) | How much of an article is read, how many words the summary is asked for, and what refuses one |
| [config/source-lifecycle.md](config/source-lifecycle.md) | When a run stops asking a feed, when an address is retired, and what keeps a link out |
| [config/run-limits.md](config/run-limits.md) | Whether a number is a guard, an alarm or a limit - the run shape, the job bounds and the page ceilings |
| [config/retention-ages.md](config/retention-ages.md) | Which instruments run, and how long what they write is kept |

**No individual knob is described on this page.** A knob written up here is the first line of the page this split removed.

## What belongs in a knob

The test is simple: **would a reasonable operator ever want a different value without changing behaviour that is a fact rather than a preference?**

Knobs, by the surface they tune:

- **Sources** - which feeds or listings are consulted, and the filters a candidate link must survive ([config/source-lifecycle.md](config/source-lifecycle.md)).
- **Extraction** - the truncation cap, the retry budget, backoff, what counts as an oversized body, shape-signal thresholds, shape enforcement switches, and paywall fallback markers ([config/summary-length.md](config/summary-length.md)).
- **Model** - which model reference and quantisation, the context size, thread count, and the sampling parameters that pin determinism ([config/model-file.md](config/model-file.md)).
- **Summarize** - the length bands, each carrying its own key-point range, plus the title range and quote cap ([config/summary-length.md](config/summary-length.md)).
- **Evaluation** - the confidence band thresholds, the brief compression ceiling, the copy reject ceiling, the word gate, the faithfulness window and its overlap, and the spot-check sample size ([evaluation.md](evaluation.md)).
- **Run shape** - the safety ceiling, the batch size, per-job timeouts, and concurrency ([pipeline-loop.md](pipeline-loop.md)). Every knob here is the digest pipeline's; the judging night's own clock is in `council` ([config/run-limits.md](config/run-limits.md)).
- **Council** - what one judging night costs a runner, whatever judges it hosts, and who it hosts. `council.shard_timeout_minutes` is how long one judging shard may run, `council.shard_preamble_minutes` is how much of that is already gone before the judging process starts, `council.shard_wrap_up_minutes` is how much the shard keeps back so it stops on its own clock rather than being killed on the platform's, and `council.shards` is how many ways a night's work may split. `council.tenants` is an ordered list of slugs and **it may be empty**: it is the one place a judge is registered, it names the content-similarity judge today, and an empty list is a night the venue runs end to end and judges nothing. The workflow reads the bound to set `timeout-minutes`; the width and the tenants size its matrix. [Why these are the venue's and not a judge's](config/run-limits.md#why-the-councils-runner-numbers-are-a-block-of-their-own).
- **Same-story line** - `assemble.same_story.adaptive_dedup_threshold` holds how the merge line fits itself: the band worth judging, how the record slices it, the five steps that move the line, and the three gates it has to clear first. The line falls fast and rises slow, and both daily caps are counted in slots of `bin_width` rather than written as decimals. `enabled` is the switch and it ships **off**, so a fresh clone publishes exactly the groups `assemble.same_story.floor_min` produced before the block existed. With it on, `assemble` reads the newest fitted line inside `applied_lookback_days` and groups the day at that number instead; the run records which number it used, so a committed `run.json` says what shaped its groups ([../architecture/publishing/autotune-content-similarity.md](../architecture/publishing/autotune-content-similarity.md)). **The whole block is optional**, and an absent block is what a repository with no content-similarity judge in it looks like: the pass then groups at `floor_min`, which is the same day the switch being off produces.
- **Bench** - how many articles one runtime-sweep repeat reads, how many times each case repeats, and whether a bench dispatch measures the model's raw speed first. `bench.corpus_items` is a fit against the job timeout rather than a taste ([../how-to/evaluate-new-summarizer-model.md](../how-to/evaluate-new-summarizer-model.md#why-the-bench-corpus-is-three-articles)), and `bench.repeats` is the other multiplier in that same fit - the two are here together so that raising one shows the other rather than leaving it to be found at 330 minutes. `bench.run_model_speed_case` is true by default; false skips the `llama-bench` job and leaves the rest of the dispatch running, which is what to set when the flow is being exercised rather than a model measured ([../reference/github-actions.md](../reference/github-actions.md#design-rationale)).
- **Retention** - the image age window, the dry-run switch, the deletion fuse, the published-site alarm point and the published-site cap ([../architecture/publishing/layout.md](../architecture/publishing/layout.md)). `retention.site_budget_mb` and `retention.pages_hard_cap_mb` are read by `idhazh site-weight`, which runs after the site is built and measures the built bundle - never the committed payload tree, which is a different tree eighteen times smaller. The alarm point warns; the cap fails the job ([config/run-limits.md](config/run-limits.md)).
- **Drift** - the window and per-domain sample floors and the length/copying
 alert thresholds. The workflow owns the schedule and its date-window inputs
 ([evaluation.md](evaluation.md#comparable-domain-samples)).
- **Logging** - the level, plus one flag per kind of record the pipeline builds about itself ([telemetry.md](telemetry.md)). The two are unrelated: the flags decide which records exist, the level decides how loud the logger that prints them is.
- **Observability** - which instruments run, how often the scorer runs, and how long a ledger stays at full grain ([config/retention-ages.md](config/retention-ages.md)).
- **Console** - the telemetry viewport's default window, today anchor, pan step,
 zoom factor, minimum denominator for rate bars, and chart height ([config/appearance.md](config/appearance.md)).

These are the *surfaces*, not a field list. The field-level truth is `schemas/app-config.schema.json`, generated from the model - read it there rather than restating it here, because a list copied into prose is a list that goes stale.

The knobs are spread across six files rather than one, along the line of who edits them and how often: `config/idhazh.json` for pipeline behaviour, `config/models/<name>.json` for everything that is a fact about one set of weights, `config/appearance.json` for everything the published surface is drawn from, and `config/taxonomy.json`, `config/sources.json` and `config/watchlist.json` for the source model ([../architecture/sources/discovery.md](../architecture/sources/discovery.md)). Curating a feed list and tuning a threshold are different activities with different review cadences, and putting them in one file means every feed addition touches the file that also holds the decoding parameters.

**Three of those files are lists rather than settings, and they are written one record a line.** `config/sources.json` holds a feed per line, `config/taxonomy.json` a word per line and `config/watchlist.json` an entity per line, keys sorted, every field spelled out even at its default. Adding a feed is one line; changing a tier is a one-line diff; adding a keyword to a lens moves that lens and nothing else. A test holds the layout still, because nothing else can - every layout parses to the same payload, so a record hand-indented across ten lines is invisible to the schema and to every reader. See [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md).

Every knob ships a sane default. The one exception is the model references, and why they have none is [config/model-file.md](config/model-file.md#the-model-references-are-the-only-values-in-config-with-no-default).

## What is NOT a knob

Not everything variable is tunable. Two categories stay out of `config/`:

- **Facts, not preferences.** The runner's core count, the 6 h job cap and the 10 GB cache allowance are properties of the platform (Guardrail #2). Making them configurable would imply they can be chosen.
- **Identifiers.** Stage names, event names, visual kinds and score-band names are schema-validated enums defined in the contracts. Code references them; they never change to match a label. Which word a new key takes is [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md).

The distinction matters because a value in `config/` reads as an invitation to change it.

A third category is in `config/`, is a knob, and is still not there to be tuned: a guard, an alarm or a limit. What separates those three, and why the name has to say which it is, is [config/run-limits.md](config/run-limits.md).

## A knob nothing reads is deleted

A knob that no code path reads is worse than clutter. It reads as a control, so the next person to open the file sizes the system by what the knobs claim - and eventually somebody changes one and waits for an effect that never arrives.

Three were removed this way, each describing a mechanism that does not exist:

- `collect.min_feeds_floor` claimed to be the default feed floor. The floor a vertical is actually held to is its own `min_feeds` in `taxonomy.json`. Nothing read the default.
- A per-feed `weight` on a salience feed. An aggregator has no subject taxonomy to be graded on, so there was nothing for a per-feed weight to express, and what a vote was worth was one number for every aggregator rather than one per feed. That number, `collect.front_page_bonus`, was itself removed on 2026-09-13 under the retirement condition it shipped with ([../architecture/sources/discovery.md](../architecture/sources/discovery.md#a-speculative-term-ships-with-the-condition-that-retires-it)) - so a vote is now a published fact about a story and moves no score at all. **The feed weight on ordinary sources is untouched and load-bearing** - it multiplies the tier score ([../architecture/sources/discovery.md](../architecture/sources/discovery.md)).
- `Sources.live_feeds_for`, a method with no caller that also disagreed with the code doing the job: it honoured `retired_on` and ignored `status`, so it would have read a draft feed. One concept, one home.

### The other failure: a vocabulary with no way to be applied

A knob nothing reads has a mirror image, and it is harder to see. `taxonomy.json` declared four lenses and nine event types from the first commit, and every one of them carried an `id`, a `display_name` and **no way to say what assigns it**. So nothing ever did: measured 2026-08-26, 0 of 2,121 committed items carried a lens or an event. The file read as a working vocabulary and was a list of labels.

The fix, on 2026-08-26, was a `keywords` list on each lens and each event, holding the curated terms that assign it ([../architecture/sources/discovery.md](../architecture/sources/discovery.md) owns the rule and its measured coverage). Two things about that field are deliberate:

- **It is a config field and not a code constant** (Guardrail #6), because it is a curated artifact that gets tuned. The first draft over-tagged: bare `research` and `study` put the `research` event on 34.7 percent of real articles, which is not a filter. Tuning it must not be a code change.
- **An empty list is legal and assigns nothing.** That is what makes the field additive - a taxonomy written before it still validates - and it is also exactly the silence that let the vocabulary ship unwired for five days. A test now asserts every committed lens and event carries terms, so the empty state cannot come back unnoticed.

The lesson generalises past this file: **a config entry that declares a thing must also declare how the thing is decided, or it is decoration.** An id and a display name describe a label. They never describe a rule.

The same day found the third shape of the same failure, and it is the worst of them: **a knob that is read, but always against an empty input.** `collect.watchlist_bonus` was read on every planned item and added to the score under `if watchlist_hit`, and it could never fire, because `watchlist_hit` was tested against a `watchlist_keys` the caller hardcoded to the empty set. Nothing here was dead code and nothing was unread config, and the term still never moved a number. A test asserting "the bonus lifts the score" passed the whole time, because the test supplied the flag itself. Fixed 2026-08-26: `config/watchlist.json` carries 30 entities and the flag comes from their aliases. The test now pins each term's **size** against its knob rather than only its direction, which is the check that would have caught it.

### Removing a config field is breaking, and its migration is the file

Deleting a key is a breaking schema change like any other, so it ships a changelog entry and a version stamp (`CLAUDE.md` section 11).

The read-side migration is unusual and worth stating once: **for a config contract, the migration is the config edit in the same commit.** No run writes these files - a person does - so there is no back catalogue of old payloads to upgrade. There is one file per contract, and `extra="forbid"` fails loudly and by name if a stale key survives. A migration function would have nothing to migrate.

## Build-time config versus shipped config

Most knobs are read only by the producer and never reach a reader: source lists, model references, batch sizes, timeouts, retry budgets. Shipping those into the published bundle would be dead bytes and a muddled surface.

A knob is shipped **only** when a published surface genuinely needs it - for example, how the dashboard buckets the ledger it renders. When that happens the value is *imported into the bundle at build time*, never fetched at read time: it is tiny, it is needed before the first paint, and fetching it would put a round trip on the critical path for something that cannot change between builds.

## Design rationale

Keeping tunables in schema-validated files rather than in code exists so that tuning the system never requires reading it, and so that a change of threshold is a reviewable one-line diff with a date on it rather than an archaeological dig. Treating config as a versioned contract - rather than as "just a JSON file" - is what stops a silently-renamed key from failing a run at 6 a.m. on a Sunday. Authority: Fowler ([../../.github/agents/fowler.agent.md](../../.github/agents/fowler.agent.md)).

Excluding the runner's ceilings is the less obvious half. They look exactly like knobs and are not: a configurable job timeout invites someone to raise it rather than fix the batch size, which is precisely the reasoning Guardrail #2 exists to prevent. Authority: Carmack.

**This page became an index on 2026-09-23, and six pages came off it.** It answered at least six questions at about 33,300 tokens, which made it the heaviest page the routing table could send an agent to. One section titled for a frame width had grown to hold the model references, the extraction signals, the summary ladder and the source filters, so a reader could not act on the frame width without reading past four unrelated answers - the split test failing in the open ([../reference/documentation-structure.md](../reference/documentation-structure.md)). The stem keeps the rules every config file obeys and the routing table; each child keeps one question. The cost is real and is the usual one: a knob whose page nobody can guess now costs a table lookup, where before it cost a long scroll. Authority: Fowler.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Fetch `config/*.json` from the published site at read time | A round trip on the critical path for about a kilobyte, plus a request that can fail, to load something that never changes between builds. | Carmack |
| Copy config into the published directory at build time | Two copies of one file, free to drift, with nothing gating them. | Fowler |
| Environment variables for pipeline tunables | Invisible in review, unversioned, and undiffable. A knob nobody can see the history of is a knob nobody can trust. | Fowler |
| Put the runner's ceilings in config | They are platform facts, not preferences, and making them editable invites raising the budget instead of simplifying the feature. | Carmack |
| Keeping a dead knob "in case it is wanted later" | It reads as a control. The next person sizes the system by what the knobs claim, and one of them is a lie. | Fowler |
| One page per config file, rather than per question | `config/idhazh.json` holds the run shape, the extraction signals, the summary ladder, the source filters and the ledger ages. A reader arrives holding one of those and never holding a filename. | Fowler |
| Leaving the page whole and cutting only its longest section | The length was the symptom. Six questions on one page means only the section order says which statement governs, and a reader arriving by search never sees the order. | Fowler |

## See also

- [config/model-file.md](config/model-file.md) - which model runs, and what is declared for those weights.
- [config/appearance.md](config/appearance.md) - what the reader's page and the operator's console are drawn from.
- [config/summary-length.md](config/summary-length.md) - what gets summarized, and at what length.
- [config/source-lifecycle.md](config/source-lifecycle.md) - when a feed is rested, retired, or kept out.
- [config/run-limits.md](config/run-limits.md) - guards, alarms and limits, and the run shape.
- [config/retention-ages.md](config/retention-ages.md) - which instruments run, and how long a record is kept.
- [principles.md](principles.md) - config-driven with sane defaults.
- [pipeline-loop.md](pipeline-loop.md) - the stages these knobs tune.
- [telemetry.md](telemetry.md) - the logging knobs, which are the one surface still written up here.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the schema every config file conforms to, and which word a new key takes.
- [../reference/documentation-structure.md](../reference/documentation-structure.md) - the split test this page was cut by.
