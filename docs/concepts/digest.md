# Digest

**Last Updated**: 2026-08-23

What a reader actually gets: the published surface, the item, and the rule that decides whether an item gets a picture. This page fixes the vocabulary and the invariants; the concrete layout and typography are Jony's territory and live in [ui-shell.md](ui-shell.md) and [design-system.md](design-system.md).

## The published surface

Two pages, both static files with nothing computed at read time:

- **The digest** - the day's items. This is what the project is for.
- **The eval dashboard** - the committed ledger, rendered. It reads the CSV and never recomputes a score ([evaluation.md](evaluation.md)).

The digest is a **rendering, never a source of truth.** The truth is the per-item payloads and the ledger; the page is one view over them and can be regenerated at any time. This is why an item carries its own identity as a field and the digest does not.

## The item

An item is the unit a reader consumes. It carries, at minimum:

| Element | Why it is there |
| --- | --- |
| **The title** | Ours, not the source's. A headline is written to win a click; a digest line has to say what happened. The summarizer writes it from the article body rather than from the headline, under the same attribution and certainty rules as the summary, because it is the one line every reader sees. Where the rewrite misses, the item falls back to the source's headline rather than failing ([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)). |
| **The source link** | The reader's means of verification and their exit. It is a first-class element, not a footnote. Burying it is a dark pattern. |
| **The summary** | Our own text, of a pinned shape. Never the article body - that is never committed and never served. |
| **A source-limit sentence** | Shown only when the reader would otherwise be surprised. An abstract says: "This is a summary of the paper's abstract. The full paper is a PDF." A truncated read says: "We could only read the first part of this page." It is a sentence in the summary voice, never a badge or coloured pill. |
| **A confidence signal** | Where the item scored low, or where the source was truncated, the reader is told, in their words, before they find out by clicking through. |
| **A visual, or deliberately none** | See below. |

Everything else earns its place by surviving a deletion attempt.

## The visual rule

There are exactly three answers, and the third is the common one:

- **Numbers in the article -> a chart**, built from a specification whose data values are drawn from the article. The constraint that makes this safe: a number in the chart that is not in the article is a defect, not a rounding difference.
- **A process in the article -> a diagram**, rendered deterministically from a text description.
- **Anything else -> nothing.**

"Nothing" is a real, frequent, correct answer. The failure mode being designed against is decoration: a generated picture of a chart with invented axis labels is worse than no picture, because it looks like evidence. A reader who once notices invented numbers stops trusting every summary on the page - the same contagion that makes an unmeasured summarizer dangerous.

A render failure degrades the item to no visual. It never fails the item, and it never fails the run.

## Honesty is a design requirement

The system knows things about its own output that a reader cannot see: that a source was an abstract, that a source was truncated, that a summary scored badly, that some of today's items did not finish. These are surfaced:

- A short or abstract source can publish as a brief item. Brevity is not a confidence band; a 100-word post can be summarized faithfully.
- A source-limit sentence appears only where the missing context would surprise the reader. A normal short post does not get a label.
- A low-confidence item **publishes, marked.** Suppressing it would make the digest look better than it is.
- A partial run **publishes, and says it was partial.** The failure count is a tracked number with a date on it, not something noticed when a human complains.
- The footer says: "We skipped N stories today because we could not read enough of the page to summarize them fairly."
- A run with zero successes still publishes. A day whose failures are invisible is a day nobody fixes.

Surfacing this without turning every item into a disclaimer is a typography and hierarchy problem, and it is a real one.

## The reader's budget

About two minutes. Ten items a reader can skim beats forty they cannot.

That is a design target for the page, not a cap on the pipeline. Nothing limits how many items a day may carry - supply and the ranking decide ([../architecture/sources/freshness.md](../architecture/sources/freshness.md)). The reader's budget is protected by ordering and by hierarchy: the best items are first, and a day that runs long is a scroll rather than a truncation. Whether a long day needs more than ordering is a typography question, and it is open.

The page must also render when its data file is absent or empty. That is a normal state, designed on purpose, not an error discovered as a white screen ([../../CLAUDE.md](../../CLAUDE.md) section 12).

## See also

- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - where these items are written, the dated routes a reader walks, and retention.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - what the summarizer is asked for, and why the title is ours.
- [ui-shell.md](ui-shell.md) - the layout and chrome around these items.
- [design-system.md](design-system.md) - the visual language.
- [evaluation.md](evaluation.md) - where the confidence signal comes from.
- [pipeline-loop.md](pipeline-loop.md) - the Route, Render and Assemble stages that produce this.
- [../../.github/agents/reader.agent.md](../../.github/agents/reader.agent.md) - the person this page is written for.
- [../../.github/agents/jony.agent.md](../../.github/agents/jony.agent.md) - the persona who owns the surface.
