# Pipeline Loop

**Last Updated**: 2026-08-23

The stages one article passes through, what each stage owns, and the rule that they talk in payloads rather than calls. This is the build-time equivalent of a product's core loop: it is the thing that happens over and over, and every other concept doc hangs off it.

The concrete stage list, the module names and the field-level payload shapes are owned by the plan-doc and by the subsystem docs under `docs/architecture/`; this page fixes the *vocabulary* and the invariants that hold whatever the stage list becomes.

## The unit of work is one item

An **item** is one source URL and everything derived from it. It is the atom of the whole system:

- It is fetched, extracted, summarized, scored and routed independently of every other item.
- It lands as one file per item under a predictable path - the day, the vertical, and the item's ordinal within that vertical. Identity for dedupe is a field on the payload, never a path segment, so a re-run skips work by comparing the payload's fingerprint rather than by probing the filesystem.
- It is written **temp-then-rename**, so a file either exists complete or does not exist. There is no half-written item.
- Its failure is its own. A dead link, a paywall, a failed extraction, a dead model server, or a visual that would not render - each degrades that item and records why, and the run continues.

This is what makes the pipeline resumable: re-running costs only the items that did not finish.

## Stages talk in payloads, not calls

Each stage consumes one validated payload and emits another. It never reaches into another stage's internals. Two consequences follow, and they are the reason for the rule:

- **Every stage is invocable alone**, with a file in and a file out. A stage that can only run as part of the whole pipeline cannot be tested, and is a design error.
- **Every boundary is a fixture.** Because a payload is plain serializable data, a real captured payload can be replayed in a test with no mocks and no network (Rule #7).

The payload shapes are Pydantic models under `backend/idhazh/contracts/`, written before the logic that reads them (Rule #3). See [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md).

## The stages

In order, with what each one owns:

| Stage | Owns | Emits |
| --- | --- | --- |
| **Collect** | Which sources are consulted and which candidate links survive the filters. Honours `robots.txt`; never touches a paywalled or login-walled source. See [../architecture/sources/discovery.md](../architecture/sources/discovery.md). | The day's candidate list. |
| **Extract** | Turning a page into readable text, and **the trust boundary**. This is where a stranger's bytes are sanitized, exactly once. See [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md). Also where an over-long body is truncated and *flagged* as truncated - never silently dropped. Short or list-shaped text is recorded as a signal and still publishes by default. Publisher-declared paywalls and unsupported forms do not publish. | One article payload per item, including the failure cases and recorded shape signals. |
| **Summarize** | Turning article text into a summary of a pinned shape, deterministically. The output shape is enforced by the decoder, not requested in the prompt. Also writes the item's title: a headline is written to win a click, so the digest publishes its own. If the local model server is down, Summarize records `model_unreachable` on the item rather than blaming the source or the model reply. See [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md). | One summary payload per item. |
| **Evaluate** | Scoring the summary, and knowing what each score cannot see. See [evaluation.md](evaluation.md). | One eval row per item, appended to the committed ledger. |
| **Route** | Deciding whether an item gets a chart, a diagram, an illustration, or nothing - where "nothing" is a frequent and correct answer. | A route decision per item. |
| **Render** | Producing the visual the route asked for. A render failure degrades the item to no visual; it never fails the item. | The visual asset, or nothing. |
| **Assemble** | Collecting whatever finished into the published digest, including when some items did not finish. It also writes the item-health census once per run, because it is the only stage that sees every planned item and every finished payload. See [../architecture/publishing/layout.md](../architecture/publishing/layout.md). | One dated day payload plus its run manifest under `frontend/public/digest/`, and one item-health row per planned item under `state/item-health/`. |

**Collect and Assemble are the only stages that see the whole day.** Everything between them sees exactly one item, which is what allows the middle of the pipeline to run as many independent workers.

## The run shape

The orchestration mirrors the same rule one level up: a planning step decides the work and divides it, a set of independent workers each does a batch on its own machine, and an assembling step collects whatever finished.

**The loop turns four times a day, every six hours.** All four runs append to the same dated digest rather than replacing it, so a day grows through the day. That is only safe because an item's identity comes from its address rather than its rank - see [../architecture/sources/freshness.md](../architecture/sources/freshness.md).

Four invariants hold regardless of how the batches are sized:

- **A worker failure is contained to its batch**, and does not cancel its siblings.
- **The batch size is a measured decision, not a preference.** It is set by how long loading the model takes relative to how long an item takes - if loading dominates, the batch is too small. Per-item atomicity survives inside a batch through the temp-then-rename write plus a fingerprint comparison against the run index.
- **A worker may change the processing order inside its shard.** It currently
  fetches and extracts its assigned items, then sorts the items that can be
  summarized by prompt band before the model loop. The files are addressed by
  item id, not by processing order, so grouping same-band prompts changes cache
  locality and not correctness.
- **An item whose fingerprint already matches does no work and writes no eval row.** A re-run that changed nothing measured nothing. What the fingerprint covers, and what happens when it matches but the words differ, is [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md).
- **The assemble step always runs, and always publishes.** A run with failures publishes a digest that says so, and the failure count lands in the ledger as a fact with a date on it. A run that publishes nothing on a bad day is a run whose bad days are invisible.

## What one run leaves for the next

There is no database (Rule #1), so anything a later run must read has to survive as a committed file. Five append-only ledgers under `state/` are the whole of the pipeline's memory:

| File | Written by | Answers |
| --- | --- | --- |
| `state/seen/<YYYY-MM>.csv` | Collect | How old is this article, when its feed gave no date? |
| `state/published.csv` | Assemble | Have we already published this address? |
| `state/feed-health/<YYYY-MM>.csv` | Collect | What did every feed do, on every run? |
| `state/fingerprints.csv` | the workers | Did anything about this item actually change? |
| `state/item-health/<YYYY-MM>.csv` | Assemble | What did every planned item do in this run? |

Three rules hold for all of them:

- **Append, never rewrite.** A mutable flag would turn an append into a read-modify-write over the whole history, and two runs racing on that lose rows.
- **The stage that can honestly answer is the stage that writes.** Assemble writes the published ledger, not Collect - until a digest is committed, nothing was published, and a run that dies mid-way must not leave a claim that it finished.
- **Nothing under `state/` is ever served.** The console reads it at build time and bakes the numbers into the page. A reader gets the figures, never the file.

See [../architecture/sources/freshness.md](../architecture/sources/freshness.md) for the first two and [../architecture/sources/health.md](../architecture/sources/health.md) for the third.

## What never happens in the loop

- No stage fetches at read time. Everything here is build time (Rule #1).
- No article body is committed or served. The link and our summary are the output (see [../../CLAUDE.md](../../CLAUDE.md) section 0a).
- No fetched text becomes an instruction, a shell argument, a file path, or a URL to fetch (Rule #11).
- No stage silently drops data. Truncation, degradation and failure are all recorded on the item.

## Design rationale

The plan step guarantees one `url_key` across the whole run before it applies
the safety ceiling. Discovery deduplicates repeated entries inside one feed, and
ranking deduplicates repeated entries inside one vertical. The plan step is the
first place that can see a story carried by two verticals. It keeps the
highest-ranked occurrence, with stable tie-breaks, then records the dropped
duplicates in the log. A duplicate is not a bad source and not a failed item. It
is one address seen twice, so it degrades to one planned item instead of failing
the run or consuming a ceiling slot.

The pipeline records shape. It does not judge newsworthiness. A one-line item can
be news, and a long article can be empty. Extract therefore records `too_short`,
`not_prose` and `boilerplate` by default, then lets the item continue. Only a
paywall, an unsupported form, or genuine missing text stops the item. Authority:
Owner override O3.

## See also

- [../architecture/sources/discovery.md](../architecture/sources/discovery.md) - what Collect consults, and how the source set changes over time.
- [../architecture/sources/freshness.md](../architecture/sources/freshness.md) - the six-hour cadence, how age is scored, and what stops an article publishing twice.
- [../architecture/sources/health.md](../architecture/sources/health.md) - what every feed did on every run, and the quarantine that reads it.
- [../architecture/sources/trust-boundary.md](../architecture/sources/trust-boundary.md) - what Extract does to a stranger's bytes, and the canaries that assert it.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - what Summarize asks a model for, and where every number in that ask comes from.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - what Assemble writes, the reader's routes, and retention.
- [evaluation.md](evaluation.md) - what the Evaluate stage measures and what it cannot see.
- [digest.md](digest.md) - what Assemble publishes and what a reader gets.
- [config.md](config.md) - the knobs that tune the stages.
- [telemetry.md](telemetry.md) - the event envelope each stage emits and logs.
- [principles.md](principles.md) - the beliefs behind the invariants on this page.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the payload contracts.
- [../architecture/contracts/determinism.md](../architecture/contracts/determinism.md) - what makes "this re-run changed nothing" checkable.
- [../../CLAUDE.md](../../CLAUDE.md) - the contract, including the layer rules for stages.
