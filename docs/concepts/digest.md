# Digest

**Last Updated**: 2026-08-29

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
| **A source-limit sentence** | Shown only when the reader would otherwise be surprised. An abstract says: "This is a summary of the paper's abstract. The full paper is a PDF." A cut read says: "We could only read the first N percent of this page." An item carries **every** limit that applies to it, so a cut abstract says both. It is a sentence in the summary voice, never a badge or coloured pill. |
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
- **The mark names what is missing, not how good the item is.** "Our summary leaves out names or figures from the opening" is something a reader can check when they click through. "Mostly matches the source" is a grade, and a reader can do nothing with it. The published item carries a `band_reason` identifier and the site owns the sentence ([evaluation.md](evaluation.md)).
- A top-band item says nothing at all. Copy about the absence of a problem is ink a reader cannot act on.
- **Confidence is stated per item and never as a day-level chart.** A three-segment bar of the day's bands was deleted on 2026-08-24: its proportions were the same every day (57.7 / 24.2 / 18.1 re-banded at n=447), it shared its tokens with the item mark so it trained a reader to ignore the mark that does vary, and it spread a number over hundreds of items a reader could neither locate nor act on. Colour is spent where it changes between two items on one screen.
- A partial run **publishes, and says it was partial.** The failure count is a tracked number with a date on it, not something noticed when a human complains.
- **The day is stated in one line, once.** Every run used to print its own near-identical paragraph saying one fact. The line is the count, the failures, and how many arrived after the first run.
- The footer says: "We skipped N stories today because we could not read enough of the page to summarize them fairly."
- A run with zero successes still publishes. A day whose failures are invisible is a day nobody fixes.

Surfacing this without turning every item into a disclaimer is a typography and hierarchy problem, and it is a real one.

## The reader's budget

About two minutes. Ten items a reader can skim beats forty they cannot.

That is a design target for the page, not a cap on the pipeline. Nothing limits how many items a day may carry - supply and the ranking decide ([../architecture/sources/freshness.md](../architecture/sources/freshness.md)). The reader's budget is protected by ordering and by hierarchy: the best items are first, and a day that runs long is a scroll rather than a truncation.

**A long day gets its hierarchy from its topics.** 586 items in one queue had no usable first screen - its opening items were whichever vertical id sorted first, which is an accident rather than an edit. The all-topics page now shows each topic's first few and links to the rest ([../architecture/publishing/frontend.md](../architecture/publishing/frontend.md)). Nothing is removed, hidden or re-ranked; the published order survives inside every section. That is hierarchy doing the work the reader's budget always asked of it, and it is why truncating a long day was refused.

The page must also render when its data file is absent or empty. That is a normal state, designed on purpose, not an error discovered as a white screen ([../../CLAUDE.md](../../CLAUDE.md) section 12).

## Design rationale

### The cut sentence carries the scale

**The sentence is "We could only read the first N percent of this page.", where N is a whole number.**

Until 2026-08-29 every cut item printed one sentence with no number in it: "We could only read the first part of this page." Measured over the 22 genuinely cut items in `state/scores.csv` on 2026-08-29, that one sentence covered a page we read 99 percent of (1,923 words of 1,948) and a page we read 23 percent of (1,923 of 8,442). Those are different situations and the reader could not tell them apart. Deciding whether to click through is the only thing the note is for, so a word that means both means nothing.

Raising the cap does not remove the problem, it narrows it. At a 5,000-token cap only four of those 22 items are still cut, and they still lose between 9 and 54 percent.

A percentage of what we read, rather than a count of words, because the reader cannot see the page's true length. "We read 1,923 words" tells them nothing on its own; "23 percent" ranks instantly against every other item on the page, with no arithmetic inside a two-minute budget.

**Rejected wordings:**

| Wording | Why not |
| --- | --- |
| "We could only read the first 1,923 words of this 8,442-word page." | Two four-digit numbers and a division. The reader has to do arithmetic to get the one fact they came for. |
| "We could only read about half of this page." | A bucket is the same failure at a coarser grain: one phrase would still have to cover 9 percent lost and 30 percent lost. The boundaries would also be an invisible tunable. |
| "The other 77 percent is at the link." | Leads with the article rather than with our own limit, and spends a second sentence pointing at a link that is already on the item. |
| Rounding N to the nearest 5 or 10 to avoid false precision | A grain constant that buys nothing. A whole percent is already coarser than the word count it is derived from. |
| Keeping the old sentence and letting the reader judge from the link | The reader cannot tell whether "the first part" is 91 percent or 46 percent, so they cannot decide whether the link is worth opening. |

The noun stays "page", not "article", because the same sentence has to be true of a paper's landing page as of a news story, and because "the page" is what the reader is deciding whether to open.

**Where the note states no scale.** The length before the cut is `Article.source_word_count`, and it is absent on any payload written before that field existed - 142 of the 2,683 rows in `state/scores.csv` on 2026-08-29. There the note falls back to the sentence it already shipped: "We could only read the first part of this page." The same fallback runs when the share rounds to all of it or none of it, because a cut page that claims "the first 100 percent" says the opposite of what happened. Degrade, do not fail ([../../CLAUDE.md](../../CLAUDE.md) section 1a): the note drops the number it cannot support, never the fact.

### An item carries every limit, not the first one

The note used to return on the first limit it found, so an item that was both an abstract and cut published only the abstract sentence and dropped the cut in silence. That is the failure this page polices hardest: a reader who is not told what is missing has been misled, however accurate the words are.

It has never fired. Nothing in extract exempts an abstract from the cap - the cut runs on every body - but the one feed that declares the abstract form produced 28 items across `state/item-health/2026-08.csv` on 2026-08-29 and the longest body among them was 330 words, against a cut point of 1,923. Being unreachable today is not a reason to keep a shape that drops a fact.

## See also

- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - where these items are written, the dated routes a reader walks, and retention.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - what the summarizer is asked for, and why the title is ours.
- [ui-shell.md](ui-shell.md) - the layout and chrome around these items.
- [design-system.md](design-system.md) - the visual language.
- [evaluation.md](evaluation.md) - where the confidence signal comes from.
- [pipeline-loop.md](pipeline-loop.md) - the Route, Render and Assemble stages that produce this.
- [../../.github/agents/reader.agent.md](../../.github/agents/reader.agent.md) - the person this page is written for.
- [../../.github/agents/jony.agent.md](../../.github/agents/jony.agent.md) - the persona who owns the surface.
