# Vision

**Last Updated**: 2026-08-20

What yen-idhazh is, what it is not, and the one-sentence product idea every other concept doc serves. This is the top of the concept tier; if a later doc contradicts this page, this page is wrong and gets fixed.

## The idea in one sentence

yen-idhazh is a daily **article digest that scores its own work**: a build-time pipeline reads public web articles, summarizes each one with a small open-weights model, measures how faithful the summary is to the source, and publishes both the digest and the scores as static pages.

*idhazh* (இதழ்) is Tamil for a journal or magazine. The name is "my journal".

## The shape

A run happens once a day, entirely inside GitHub Actions, and commits what it produced. A reader later opens a static page. Nothing computes at read time, so there is no server to run, nothing to scale, and nothing that can be down.

Two artifacts come out of a run, and they are equally the product:

- **The digest** - the day's items, each a link, a summary, and a visual only where a visual earns its place.
- **The eval ledger** - one row per item recording how the summary scored, appended forever, rendered as a dashboard.

## What makes it interesting

Anyone can wire an article to a summarizer in an afternoon. The hard part, and the reason the second artifact exists, is that **a summarizer nobody measures is a machine for producing confident, plausible, wrong text.** Every summary reads equally authoritative. A reader cannot tell the accurate ones from the invented ones by looking, so the system has to know, and has to say.

That is why the evaluation loop is not reporting. It is the feature:

- Every summary is scored for faithfulness twice - against the text the model actually saw, and against the full article. The gap between those two numbers is what truncation cost us, and it is invisible to a single score.
- Faithfulness is paired with deterministic counterweights, because faithfulness alone rewards copying: a summary that quotes the source verbatim scores nearly perfectly and has summarized nothing.
- The scores are committed, not computed on demand, so the trend across months is a fact rather than a re-derivation.
- A separate benchmark re-runs a fixed set on a schedule, because per-item scores measure variance within a day and drift is a movement across months.

## What it is not

- **Not a news reader or a feed.** No accounts, no personalisation, no notifications, no infinite scroll.
- **Not a republisher.** The pipeline publishes a link and our own summary. The article body is never committed and never served.
- **Not a service.** There is no backend in production. `backend/` is a producer that runs in CI and on a developer machine.
- **Not model-agnostic by accident.** The model is chosen against a measured budget and a measured quality bar, and swapping it is a contract-level decision.
- **Not a place where the model grades itself.** A judge that shares the failure modes of the thing judged is not a measurement.

The full non-goal list is [`CLAUDE.md`](../../CLAUDE.md) section 0a.

## The constraints that shape everything

Three, in the order they bite:

1. **Static-first publication.** What reaches a reader is a committed file. This removes an entire category of design (runtime inference, personalisation, telemetry, accounts) and is why the project can run for years at no cost.
2. **The runner is the architecture.** 4 vCPU, no GPU, a 6 h job cap and a 10 GB cache decide which model can be used and how work is divided. The budget is the platform, not a preference: a feature that does not fit gets simplified, never a bigger machine.
3. **Measured, not estimated.** Throughput, cost and quality claims carry the hardware, the date and the spread. This has already changed the architecture once - measured per-job overhead against measured per-item work is what turned one-job-per-item into batching.

## What the ceiling actually is

Not compute. The order in which limits bite is: how many good articles a day the sources actually supply, then how many summaries a person will read, then artifact storage, then repository growth, and only far behind all of those, concurrency. Raising the daily item count is a source-diversity and readership decision, not a capacity one.

## See also

- [principles.md](principles.md) - the beliefs these constraints turn into daily practice.
- [pipeline-loop.md](pipeline-loop.md) - the stages a single article passes through.
- [evaluation.md](evaluation.md) - how a summary is scored, and what each metric cannot see.
- [digest.md](digest.md) - what a reader actually gets.
- [config.md](config.md) - the tunable surface.
- [../../CLAUDE.md](../../CLAUDE.md) - the engineering contract, including the full non-goals.
- [../../README.md](../../README.md) - the short entry point.
