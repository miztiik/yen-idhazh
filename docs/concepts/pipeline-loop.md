# Pipeline Loop

**Last Updated**: 2026-08-20

The stages one article passes through, what each stage owns, and the rule that they talk in payloads rather than calls. This is the build-time equivalent of a product's core loop: it is the thing that happens over and over, and every other concept doc hangs off it.

The concrete stage list, the module names and the field-level payload shapes are owned by the plan-doc and by the subsystem docs under `docs/architecture/`; this page fixes the *vocabulary* and the invariants that hold whatever the stage list becomes.

## The unit of work is one item

An **item** is one source URL and everything derived from it. It is the atom of the whole system:

- It is fetched, extracted, summarized, scored and routed independently of every other item.
- It lands as one **content-addressed file** - the name is derived from the URL, so the same URL always writes the same path and a re-run can skip what already exists.
- It is written **temp-then-rename**, so a file either exists complete or does not exist. There is no half-written item.
- Its failure is its own. A dead link, a paywall, a failed extraction, a visual that would not render - each degrades that item and records why, and the run continues.

This is what makes the pipeline resumable: re-running costs only the items that did not finish.

## Stages talk in payloads, not calls

Each stage consumes one validated payload and emits another. It never reaches into another stage's internals. Two consequences follow, and they are the reason for the rule:

- **Every stage is invocable alone**, with a file in and a file out. A stage that can only run as part of the whole pipeline cannot be tested, and is a design error.
- **Every boundary is a fixture.** Because a payload is plain serializable data, a real captured payload can be replayed in a test with no mocks and no network (Holy Law #7).

The payload shapes are Pydantic models under `backend/idhazh/contracts/`, written before the logic that reads them (Holy Law #3). See [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md).

## The stages

In order, with what each one owns:

| Stage | Owns | Emits |
| --- | --- | --- |
| **Collect** | Which sources are consulted and which candidate links survive the filters. Honours `robots.txt`; never touches a paywalled or login-walled source. See [../architecture/sources/discovery.md](../architecture/sources/discovery.md). | The day's candidate list. |
| **Extract** | Turning a page into readable text, and **the trust boundary**. This is where a stranger's bytes are sanitized, exactly once. Also where an over-long body is truncated and *flagged* as truncated - never silently dropped. | One article payload per item, including the failure cases. |
| **Summarize** | Turning article text into a summary of a pinned shape, deterministically. The output shape is enforced by the decoder, not requested in the prompt. | One summary payload per item. |
| **Evaluate** | Scoring the summary, and knowing what each score cannot see. See [evaluation.md](evaluation.md). | One eval row per item, appended to the committed ledger. |
| **Route** | Deciding whether an item gets a chart, a diagram, an illustration, or nothing - where "nothing" is a frequent and correct answer. | A route decision per item. |
| **Render** | Producing the visual the route asked for. A render failure degrades the item to no visual; it never fails the item. | The visual asset, or nothing. |
| **Assemble** | Collecting whatever finished into the published digest, including when some items did not finish. See [../architecture/publishing/layout.md](../architecture/publishing/layout.md). | One dated day payload plus its run manifest under `frontend/public/digest/`. |

**Collect and Assemble are the only stages that see the whole day.** Everything between them sees exactly one item, which is what allows the middle of the pipeline to run as many independent workers.

## The run shape

The orchestration mirrors the same rule one level up: a planning step decides the work and divides it, a set of independent workers each does a batch on its own machine, and an assembling step collects whatever finished.

Three invariants hold regardless of how the batches are sized:

- **A worker failure is contained to its batch**, and does not cancel its siblings.
- **The batch size is a measured decision, not a preference.** It is set by how long loading the model takes relative to how long an item takes - if loading dominates, the batch is too small. Per-item atomicity survives inside a batch through the content-addressed write plus skip-if-exists.
- **The assemble step always runs, and always publishes.** A run with failures publishes a digest that says so, and the failure count lands in the ledger as a fact with a date on it. A run that publishes nothing on a bad day is a run whose bad days are invisible.

## What never happens in the loop

- No stage fetches at read time. Everything here is build time (Holy Law #1).
- No article body is committed or served. The link and our summary are the output (see [../../CLAUDE.md](../../CLAUDE.md) section 0a).
- No fetched text becomes an instruction, a shell argument, a file path, or a URL to fetch (Holy Law #11).
- No stage silently drops data. Truncation, degradation and failure are all recorded on the item.

## See also

- [../architecture/sources/discovery.md](../architecture/sources/discovery.md) - what Collect consults, and how the source set changes over time.
- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - what Assemble writes, the reader's routes, and retention.
- [evaluation.md](evaluation.md) - what the Evaluate stage measures and what it cannot see.
- [digest.md](digest.md) - what Assemble publishes and what a reader gets.
- [config.md](config.md) - the knobs that tune the stages.
- [telemetry.md](telemetry.md) - the event envelope each stage emits and logs.
- [principles.md](principles.md) - the beliefs behind the invariants on this page.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - the payload contracts.
- [../../CLAUDE.md](../../CLAUDE.md) - the contract, including the layer rules for stages.
