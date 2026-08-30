# Vision

**Last Updated**: 2026-08-30

What yen-idhazh is, what it is not, and the one-sentence product idea every other concept doc serves. This is the top of the concept tier; if a later doc contradicts this page, this page is wrong and gets fixed.

## The idea in one sentence

yen-idhazh is a daily **article digest that scores its own work**: a build-time pipeline reads public web articles, summarizes each one with a small open-weights model, measures how faithful the summary is to the source, and publishes both the digest and the scores as static pages.

*idhazh* is Tamil for a journal or magazine. The name is "my journal".

## Who it is for

The digest is for **a general reader**, in the sense a newspaper is: no assumed background, no account, no reason to explain who it is for. The Reader persona is the median non-technical person, not an ML researcher and not the person who built the pipeline.

The eval dashboard is for **the operator**. It is instrumentation rather than a reading surface: it takes no ornament and spends no reader attention, but it owes the operator the same legibility the digest owes a reader. Being correct is where it starts.

The two audiences are why the two surfaces are held to different standards, and it is worth being explicit about what does *not* follow from it. The evaluation is still the product in the sense of [principles.md](principles.md) principle 6 - it is what makes the digest worth a stranger's two minutes. What the split settles is who each surface is written for, not which one matters.

## The shape

A run starts at 02:20, 06:20, 10:20, 14:20, and 18:20 UTC inside GitHub Actions,
and commits what it produced. All five runs of a day append to the same dated
digest, so the day grows through the day. A reader later opens a static page.
Nothing computes at read time, so there is no server to run, nothing to scale,
and nothing that can be down. See
[../reference/github-actions.md](../reference/github-actions.md) for the exact
trigger contract.

Two artifacts come out of a run, and they are equally the product:

- **The digest** - the day's items, each a link, a summary, and a visual only where a visual earns its place.
- **The eval ledger** - one row per item recording how the summary scored, appended forever, rendered as a dashboard.

## What makes it interesting

Anyone can wire an article to a summarizer in an afternoon. The hard part, and the reason the second artifact exists, is that **a summarizer nobody measures is a machine for producing confident, plausible, wrong text.** Every summary reads equally authoritative. A reader cannot tell the accurate ones from the invented ones by looking, so the system has to know, and has to say.

That is why the intended evaluation loop is not reporting. It is the feature:

- Every summary is scored for faithfulness twice - against the text the model actually saw, and against the full article. The gap between those two numbers is what truncation cost us, and it is invisible to a single score.
- Faithfulness is paired with deterministic counterweights, because faithfulness alone rewards copying: a summary that quotes the source verbatim scores nearly perfectly and has summarized nothing.
- The scores are committed, not computed on demand, so the trend across months is a fact rather than a re-derivation.
- A separate benchmark re-runs a fixed set on a schedule, because per-item scores measure variance within a day and drift is a movement across months.

Two parts are not implemented as described yet. Production passes truncated
text as both faithfulness inputs, so its truncation gap is zero by construction.
The drift workflow compares live ledger windows rather than replaying and
persisting a fixed-set benchmark. These are active implementation gaps, not
reasons to weaken the product contract
([evaluation.md](evaluation.md),
[../architecture/contracts/determinism.md](../architecture/contracts/determinism.md)).

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
3. **Measured, not estimated.** Throughput, cost and quality claims carry the hardware, the date and the spread. This has already changed the architecture once - measured per-job overhead against measured per-item work is what turned one-job-per-item into batching. One figure is exempt and says so on the page: the operator console prices a run at a rate the operator sets, as a counterfactual and never as a bill ([`CLAUDE.md`](../../CLAUDE.md) Rule #10).

## What the ceiling actually is

Not compute. The order in which limits bite is: how many good articles a day the sources actually supply, then how many summaries a person will read, then artifact storage, then repository growth, and only far behind all of those, concurrency.

Note what is *not* on that list: an editorial number. There is no daily item cap chosen for how long a day should be. Supply, the score and `max_per_source` decide the shape of a day, and `run.safety_ceiling_per_run` bounds its size - a number that began as a crash guard, was overtaken by supply, and is now knowingly the cap ([../architecture/sources/freshness.md](../architecture/sources/freshness.md)). Making the day bigger is still a source-diversity question first: the ceiling only binds because 27 percent of every run was being spent on sources that could not be read.

## Design rationale

**"It earns no design budget" was struck from the operator paragraph on 2026-08-29.** The split between the two audiences is real and stays; what was wrong was turning a priority order into a permanent licence to under-build. The reader coming first does not make the operator's instrument exempt from being readable, and the sentence was doing that work: measured 2026-08-28, the console rendered a 10-column table at 627px, drew three charts at 164px each, carried seven horizontal scrollbars and ran to 6562px of page height, all inside a 672px column on a 1209px screen. Each of those passed review because the doctrine said the surface did not have to be good. The rejected alternative was leaving it and fixing the console anyway; the sentence would have been cited against the next such fix, exactly as it had been cited against this one. Authority: owner, 2026-08-29. The replacement wording, and the sufficiency checks that now bind every surface, are in [design-system.md](design-system.md).

## See also

- [principles.md](principles.md) - the beliefs these constraints turn into daily practice.
- [design-system.md](design-system.md) - the visual language, and the sufficiency checks every surface passes.
- [pipeline-loop.md](pipeline-loop.md) - the stages a single article passes through.
- [evaluation.md](evaluation.md) - how a summary is scored, and what each metric cannot see.
- [digest.md](digest.md) - what a reader actually gets.
- [config.md](config.md) - the tunable surface.
- [../reference/github-actions.md](../reference/github-actions.md) - workflow names and exact triggers.
- [../../CLAUDE.md](../../CLAUDE.md) - the engineering contract, including the full non-goals.
- [../../README.md](../../README.md) - the short entry point.
