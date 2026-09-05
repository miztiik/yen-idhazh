# Digest

**Last Updated**: 2026-09-05

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

**The item's key points are not on it, and that is now measured rather than asserted.** The summarizer writes two to five key points per item and the published payload carries them, but no reading surface draws them. The reason used to be a judgement about screen space. Since 2026-09-02 it is a count: over twenty items drawn from the two longest summary bands, 78 of 89 key points restate a claim the summary already makes - seven in eight ([Design rationale](#the-key-points-stay-off-the-item-and-the-count-is-why) below).

## The visual rule

There are exactly three answers, and the third is the common one:

- **Numbers in the article -> a chart**, built from a specification whose data values are drawn from the article. The constraint that makes this safe: a number in the chart that is not in the article is a defect, not a rounding difference.
- **A process in the article -> a diagram**, rendered deterministically from a text description.
- **Anything else -> nothing.**

"Nothing" is a real, frequent, correct answer. The failure mode being designed against is decoration: a generated picture of a chart with invented axis labels is worse than no picture, because it looks like evidence. A reader who once notices invented numbers stops trusting every summary on the page - the same contagion that makes an unmeasured summarizer dangerous.

A render failure degrades the item to no visual. It never fails the item, and it never fails the run.

### A number can be right and still be mislabelled

The invented-number failure is closed by construction. Every value drawn comes from the article's own bytes, so a chart cannot carry a figure the article does not.

**What a number means is a different question, and it is not closed.** A pattern can find `4,200 tonnes`. It cannot know whether that is exports or production. Only the model can say, so the model does - and that judgement is the one part of a visual nothing verifies. Two failures follow, and neither raises an error:

- **Mis-pointing.** The model means one figure and the anchor lands on another. The span is real, so every span check passes.
- **Mis-labelling.** The right figure, the wrong measure, unit or entity. No string search reaches a judgement.

Three controls narrow it, and none of them closes it:

- A surface is searched inside **one named sentence** and must match there exactly once, so an ambiguous anchor is a rejection rather than a coin toss.
- A label is attached to an **element identifier**, never to a free string, so it can at least be checked against that element's own unit and magnitude.
- The model never types a value. No field of the reply schema accepts a number, so authorship is refused by the grammar rather than caught by a check.

**This is a permanent property of the design, not a defect waiting for a fix.** The alternative is to draw only what a pattern can name, which produces charts whose axis reads "number" - correct, verifiable, and worth nobody's attention. A digest that will not say what a figure means is not publishing a fact, it is publishing a decoration with better provenance. Owner decision, 2026-09-04.

Note the split this implies, because it is easy to lose: **code finds and cuts every character a reader sees; the model points at where to cut and says what the cut means.** A value is never model-authored. A meaning always is.

## Honesty is a design requirement

The system knows things about its own output that a reader cannot see: that a source was an abstract, that a source was truncated, that a summary scored badly, that some of today's items did not finish. These are surfaced:

- A short or abstract source can publish as a brief item. Brevity is not a confidence band; a 100-word post can be summarized faithfully.
- A source-limit sentence appears only where the missing context would surprise the reader. A normal short post does not get a label.
- A low-confidence item **publishes, marked.** Suppressing it would make the digest look better than it is.
- **The mark names what is missing, not how good the item is.** "Our summary leaves out names or figures from the opening" is something a reader can check when they click through. "Mostly matches the source" is a grade, and a reader can do nothing with it. The published item carries a `band_reason` identifier and the site owns the sentence ([evaluation.md](evaluation.md)).
- A top-band item says nothing at all. Copy about the absence of a problem is ink a reader cannot act on.
- **Confidence is stated per item and never as a day-level chart.** A three-segment bar of the day's bands was deleted on 2026-08-24: its proportions were the same every day (57.7 / 24.2 / 18.1 re-banded at n=447), it shared its tokens with the item mark so it trained a reader to ignore the mark that does vary, and it spread a number over hundreds of items a reader could neither locate nor act on. Colour is spent where it changes between two items on one screen.
- A partial run **publishes, and says it was partial.** The failure count is a tracked number with a date on it, not something noticed when a human complains.
- **The day is stated in one line, once.** Every run used to print its own near-identical paragraph saying one fact. The line is the count, the failures, how many arrived after the first run, and which run made the page.
- The line says: "N did not finish, because we could not read enough of the page to summarize them fairly." It sat in the footer until 2026-08-31, which printed it on every route including the ones that render no day, and printed it a second time under a page whose day notice was already saying it.
- A run with zero successes still publishes. A day whose failures are invisible is a day nobody fixes.

Surfacing this without turning every item into a disclaimer is a typography and hierarchy problem, and it is a real one.

## The day's leading stories

The day opens on at most five stories, chosen across the whole day, each
carrying **one sentence saying why it is there**. Below three it does not
render at all and the day goes straight to the stream: four real leads beat
five with one filler.

The block is a **way into the day and never a version of it**. Every lead is
still in the stream below, in the published order, and every story a rule kept
out still publishes there too, marked exactly as it was. The block holds ids and
sentences; the day holds the stories.

It replaced the topic sections on 2026-09-01. Those drew three stories under
each desk heading and put the rest behind five links, which on the 431-story day
of 2026-08-30 meant 15 stories shown and 416 one click away. The stream now
carries the whole day and the topic pill row is the way to a desk, where every
topic is already its own route.

**Why-lines are true or they are absent.** There are four, and a lead carries
the strongest one that is true of it:

| Sentence | When it is true |
| --- | --- |
| `Four of today's stories are about Nvidia.` | Enough of our sources named that subject in their own headlines today. |
| `Nvidia is on our watchlist.` | The story's title names an entry in our registry. |
| `The same report reached us through three of our feeds.` | Several feeds carried the same address. Never "three sources covered this": that is a different claim and the number does not support it. |
| `The lead story on our Energy desk.` | It is the strongest story on that desk today. |

A story with nothing true to say does not lead. That is the whole of the rule
and it is why there is no fifth, vaguer sentence: a block that invents its
reasons is worse than no block, and it would spend the same trust the summary
marks are protecting.

**No numerals.** A number beside a story implies a score we would then owe the
reader an explanation for, and the sentence already gives the reason in words.

Two sentences are deliberately missing. **Recency gets none** - the item's own
line already prints the time. **A weighted theme gets none** - a weight on a
lens is an editorial subsidy for a theme we think is under-carried, and "this is
here because it mentions tariffs" tells the reader about our config rather than
about the news.

How a lead is chosen, what a cap costs and where the weight came from is
[../architecture/sources/discovery.md](../architecture/sources/discovery.md#a-second-order-over-the-same-day-the-leading-stories).

## A thin desk says what did not run

A desk that published three stories and a desk whose sources broke looked
identical, and the reader had no way to tell them apart. A topic page whose desk
is thin now carries one sentence under the topic panel:

> Today our sources offered 40 stories on this topic. 31 were too old for
> today's page.

Both numbers are the day's own. The first is the distinct stories our sources
offered that desk; the second is how many of them were older than the age gate
and so could not run. Neither is a claim about the world - we know what we read,
not what was published.

**It fires on one desk, not on all of them.** Only the desk the reader has
opened, and only on a topic page. There is no desk being read on the all-topics
view, and a sentence under every pill would be a column of absences pretending
to be information.

**Three things all have to be true**, and the rule is arithmetic rather than a
feeling:

| Clause | Why it is there |
| --- | --- |
| The desk published at most `digest.desk_thin_max` stories. | Above one page of the stream the reader is scrolling, not wondering. |
| At least one story was dropped for age. | With nothing dropped there is no reason to name, and a count with no explanation is worse than silence. |
| Our sources offered more than the desk ran. | The offered count is taken per run and the day's stories accumulate across runs, so it is not an upper bound on the desk's count. Without this clause a page showing eight stories could say the sources offered five. |

A day published before 2026-09-02 carries none of these counts, and absent reads
as unknown rather than zero - so those days print nothing at all.

**How many feeds answered is not on this page.** That is a fact about our
pipeline rather than about a story, and the operator console answers it for the
one person who asks. The day records it beside the two counts and no reading
surface draws it.

## The reader's budget

About two minutes. Ten items a reader can skim beats forty they cannot.

That is a design target for the page, not a cap on the pipeline. What a day carries is decided by supply, the score and `run.safety_ceiling_per_run` ([../architecture/sources/freshness.md](../architecture/sources/freshness.md)). The reader's budget is protected by ordering and by hierarchy: the best items are first, and a day that runs long is a scroll rather than a truncation.

**A long day gets its hierarchy from its leading stories.** 586 items in one queue had no usable first screen - its opening items were whichever vertical id sorted first, which is an accident rather than an edit. The day now opens on at most five stories chosen across the whole day, and the stream below them carries every story in the published order. Nothing is removed, hidden or re-ranked. Until 2026-09-01 that hierarchy came from topic sections instead, and they bought it by hiding: three stories a desk on the page and 416 of 431 behind five links.

The page must also render when its data file is absent or empty. That is a normal state, designed on purpose, not an error discovered as a white screen ([../../CLAUDE.md](../../CLAUDE.md) section 12).

## Design rationale

### The key points stay off the item, and the count is why

**Measured 2026-09-02: 78 of 89 key points restate a claim the item's own summary already makes.** Twenty items drawn from the two longest summary bands, ninety points read one at a time against a rule written before the sample was drawn. Thirteen of the twenty add nothing whatever, and on all thirteen the points are a strict subset - the summary carries facts the points drop, never the reverse. Six points in ninety, on four items of twenty, carry a claim a summary-only reader would not have. Hardware, method, the rule and the per-item table are in [../reference/measurements.md](../reference/measurements.md#whether-an-items-key-points-repeat-its-own-summary-2026-09-02).

The idea the measurement was taken against was that length is the discriminator: a 30-to-45-word brief has no room for its points to differ, but a 3,000-word article compressed to 200 words leaves things only the points can carry. **The count says length does not discriminate.** Items with an addition have a median summary of 154 words and items with none 146 - eight words apart on a sample of twenty - and the longest summary drawn, at 210 words, produced one addition.

**The one item where the points did real work is the shortest summary in the sample, not the longest.** A 3,195-word source in a band that asks for 150 to 230 words came back with a 49-word summary, and three of its four points carry claims the summary never made. The points were doing the summary's job because the summary did not. That is a defect in the summary and it is not rare: 20 of the 110 eligible items, 18.2 percent, are shorter than their own band's floor, 13 of them in the longest band. Adding a second list under every item would hide that failure behind a feature instead of fixing it, and it would cost the other 87 percent of items the same words twice.

So the refusal holds at every length, and the fix the count actually points at is the length floor on a long article's summary, not a new element on the page ([../architecture/summarize/prompt.md](../architecture/summarize/prompt.md)).

**What a reader loses** (guardrails: a veto names the loss). On four items in twenty they lose one fact each, and on one item in twenty they lose three. What they keep is an item they can skim in one pass instead of two, and a summary that is still the only thing on the item claiming to be complete.

The field stays in the published payload. It is nine tenths of the twenty-three-field projection's added weight and the in-page filter reads it, so removing it is a contract change rather than a rendering one ([../architecture/publishing/layout.md](../architecture/publishing/layout.md#two-projections-and-what-one-day-costs)).

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

So the fixture reaches it instead. The canary day the browser suite runs against publishes one item that is both an abstract and cut, and the suite reads the joined sentence back off the page as a single paragraph. Before that the pair had a unit test and nothing that rendered it: measured 2026-08-29 over every committed `frontend/public/digest/**/digest.json`, no published item carries an abstract note at all, so the two sentences a reader would meet were two sentences no browser had ever drawn. The share the fixture prints is 75 percent, which is 2,100 words read of 2,800 - a number, because a note that says "the first 100 percent" is worse than one that states no scale.

## See also

- [../architecture/publishing/layout.md](../architecture/publishing/layout.md) - where these items are written, the dated routes a reader walks, and retention.
- [../architecture/summarize/prompt.md](../architecture/summarize/prompt.md) - what the summarizer is asked for, and why the title is ours.
- [ui-shell.md](ui-shell.md) - the layout and chrome around these items.
- [design-system.md](design-system.md) - the visual language.
- [evaluation.md](evaluation.md) - where the confidence signal comes from.
- [pipeline-loop.md](pipeline-loop.md) - the visual planning, Render and Assemble stages that produce this.
- [../../.github/agents/reader.agent.md](../../.github/agents/reader.agent.md) - the person this page is written for.
- [../../.github/agents/jony.agent.md](../../.github/agents/jony.agent.md) - the persona who owns the surface.
