# Elements: every fact in an article, with the characters that prove it

**Last Updated**: 2026-09-18

The extraction subsystem's fact table. This page owns the element shape - the
six kinds, the two tiers, and the span that makes a drawn figure checkable - the
candidate pass that fills it, the rule that settles two passes claiming one
stretch of characters, the call that labels what the pass found, and the
invariant that says when a span has stopped pointing where it did.

Two passes write into this table from the article's own bytes with no model at
all: [`backend/idhazh/elements.py`](../../../backend/idhazh/elements.py) finds
quantities and it finds absolute dates. A third asks a model, and it is two
sections below: it labels what the two patterns found, points at a figure they
missed, and points at the four kinds no pattern can reach - an organisation, a
place, a quote and a claim. It types nothing a reader sees. All six kinds have a
producer now, and every one of them carries a span code cut.

## What an element is

One fact, plus the range of characters it was cut from:

| Field | Holds |
| --- | --- |
| `element_id` | `<kind>-<span_start>-<span_end>`, the address inside its article |
| `kind` | one of `quantity`, `date`, `entity`, `place`, `quote`, `claim` |
| `span_start`, `span_end` | half-open character indices into `Article.text` |
| `span_excerpt` | the verbatim slice those indices name |
| `value` | what the span reads as - a decimal, a date, or null |
| `unit` | a quantity's normalised unit, and null on every other kind |
| `sentence_index` | which sentence of `Article.text` the span starts in |
| `extractor` | `regex` or `model` - which path found it |

`ElementTable` holds one article's elements, the article's identity, the sha256
of the exact string the spans index, and one count per kind of what the pass
matched before the cap.

## What the numbers say the article could carry

`elements.classify(table, min_chart_points=...)` reads the settled table and
answers with one of three classes. It rests on Tier 1 fields alone - `kind`,
`value` and `unit` - so it is byte-exact and carries no model judgement.

| Class | The article states |
| --- | --- |
| `chartable` | at least `visuals.min_chart_points` distinct quantities sharing a unit |
| `narrative` | no quantity at all |
| `unclassified` | quantities, but no unit shared widely enough |

**Distinct quantities per unit, because a bar chart cannot draw the same figure
twice.** A chart's bars must share one unit and are distinct by construction, so
counting a repeated figure here would call an article chartable that nothing
could ever draw - and the rate built on it would carry that gap for ever while
claiming to measure the picture. The empty unit is a group like any other.

**This is not `chart_is_reachable` and is not meant to be.** That function asks
whether a chart could survive the planner's own drops - the sixteen-fact cap and
the floor under a magnitude of two. This asks what the article states. The gap
between the two answers is what `extractable_but_unused_rate` reports
([evaluation.md](../../concepts/evaluation.md)), so closing it here would delete
the measurement.

**Three classes, and it will say three until the diagram plan lands.**
`comparative` and `processual` are claims about how an article is written rather
than about its numbers, so no query here can reach them. Anything reporting per
class names three and says so.

**The threshold is `visuals.min_chart_points` and not a second knob** (Guardrail #6).
Mint one and the console can call an article chartable while the planner refuses
to draw it, and the rate then measures two knobs drifting apart rather than
measuring the planner.

**Where the three cells go.** `elements.extraction_health(article,...)` is the
one caller in the run: it is called from `telemetry.classify_item`, which builds
the item-health census row, and it writes `span_integrity`, `elements_found` and
`element_class` on that row. It lands there rather than beside the visual
decision because two writers append that ledger and the earlier one runs in the
`work` job, hours before a plan exists - `stage_compact` settles the row
for a key, so a cell only `assemble` could fill would be empty for every item a
shard had already recorded. `ElementClass` is declared in
[`backend/idhazh/contracts/item_health.py`](../../../backend/idhazh/contracts/item_health.py)
with the census row's other three closed vocabularies, because
`contracts/element.py` sits above `contracts/article.py`, which sits above that
module, and a label a census row persists has to be declared at or below the
row's own level.

**Counts and a label cross, never article text.** `span_excerpt` stays inside
the process that cut it (`CLAUDE.md` section 0a), and the browser-safe telemetry
projection is untouched: the console reads the day's totals from the day record,
one file per date, rather than three more cells on every published row for ever.

**`elements` is capped and `candidates_found` is not.** How many candidates a
producer keeps is a tunable (`elements.max_per_article`, 256), so the length of
`elements` saturates. Read a density signal off it and a 600-word note carrying
16 figures looks the same as a 3,000-word data story carrying 60 - and the
second is the chartable one. It fails silently, because a capped counter still
returns a plausible integer. The count is taken before any dedupe, before the
overlap rule and before the cap, and the shape refuses a table that kept more of
a kind than it says it found.

**`candidates_found` is one count per pass and never a total.** Two passes may
both count one stretch of characters, because both matched it and only one kept
it. So `candidates_found[quantity]` is what the number pattern matched and
`candidates_found[date]` is what the date pattern matched, and summing them
double-counts every span they competed for. Measured 2026-09-08 on the nine
bounded fixtures: 17 quantities and 8 dates matched, 9 quantities and 8 dates
kept.

**The knob bounds each pass and then the settled table.** Each pass stops at
`elements.max_per_article`, and the merged, settled list is cut to the same
number, so neither a runaway pattern nor two passes together can put more
elements in an article than the knob names.

**A span here is a character range, not a trace span.**
[`backend/idhazh/contracts/span_rollup.py`](../../../backend/idhazh/contracts/span_rollup.py)
uses the word for an execution timing. The two never meet: a rollup span has a
name and a duration, an element span has two integers and a string.

**The string the offsets index is `Article.text`** - post-sanitize and
post-truncation, as `backend/idhazh/extract.py` leaves it. It is neither the
fetched page nor the pre-cap body. An offset taken against either of those
points somewhere else in the article, which is the failure the article hash
exists to catch.

**One hash per article, not per element.** The table carries
`source_text_hash`, the sha256 of that string, computed by the same
`derive_text_digest` the rest of the pipeline uses. A hash on every element
would be redundant against this one plus a re-slice, and it would be a hash per
element on every article for ever. The re-slice itself is
[the span-drift invariant](#the-span-drift-invariant) below.

## The two tiers

**Tier 1 is what code found**: `element_id`, `kind`, `span_start`, `span_end`,
`span_excerpt`, `value`, `unit`, `sentence_index`, `extractor`. Each comes from
a pattern over the bytes or from arithmetic on offsets. Nothing model-authored
reaches them, on any kind.

**Tier 2 is what a labeller said about it**: `entity`, `time`, `measure`,
`measure_canonical`, `dimension`, `salience`, `attribution`, `hedge`, plus
`label_source` and `ledger_version`, which record who said it and under which
pass.

The split is enforced three ways, not described:

- Every Tier 1 field is **required** and every Tier 2 field is **optional**, so
 the generated schema's `required` list is exactly the nine Tier 1 names. An
 element carrying a judgement and no anchor does not load.
- `TIER_ONE_FIELDS` and `TIER_TWO_FIELDS` are declared in the module, and it
 raises at **import** if a field belongs to neither. A field added without a
 tier is a field with no trust story, and the failure arrives when the module
 is first read rather than when a payload is first written.
- A judged field carries `label_source` and `ledger_version`; the pair with
 nothing judged is refused too. A claim with no author cannot be measured
 later, and an author with no claim is a record of nothing.

`extractor` is the field that lets the two paths be measured apart. Without it,
a fall in the quantity count reads the same whether a pattern stopped matching
or a model stopped pointing, and those have different fixes.

**`extractor` is not `Article.extractor_version`.** That names the HTML-to-text
extractor that produced the article body - the stage that made the string. This
names the pass that found a fact inside it. Two words would have been better and
the second one is spoken for; the field carries the note instead.

## What a kind may say

| Kind | `value` | `unit` |
| --- | --- | --- |
| `quantity` | a decimal, written as text | the normalised unit, or null |
| `date` | `YYYY` or `YYYY-MM-DD` | null |
| `entity`, `place`, `quote`, `claim` | null | null |

Absolute dates and years only. "Three years ago" resolves against a publication
date the article never wrote, so the grammar refuses it at the shape and no
producer can write one by accident.

The value is pinned as **text** for the reason a timestamp is: one spelling, and
no float formatting that can drift underneath a committed file.

Six kinds shipped in one changelog entry and all six have a producer. The two
pattern passes write `quantity` and `date`; the label call points at the other four and
code cuts them.

## The candidate pass

`quantity_elements(text, limit=...)` reads `Article.text` with the number
pattern and `date_elements(text, limit=...)` reads the same string with the date
pattern. Each emits one element per match, in the order the article wrote them.
`settle(...)` decides which of the two keeps a stretch of characters both
matched, and `element_table(article, config=...)` wraps the result in the table,
with the article's identity and the hash of the text every span indexes. All
four are pure functions over one payload: nothing is committed, and the passes
are proved by re-slicing their own output.

**The offsets are not new work.** The retired planner's `numeric_facts`
computed `match.start` and `match.end`, and threw them away.
This pass keeps them and cuts `span_excerpt` at them.

**What the pass keeps that the fact reader dropped.** `numeric_facts` picked a few bars
for one chart, so it collapsed a figure repeated across two periods into one
fact, dropped a magnitude at or below two, dropped a bare year, and stopped at 16.
Every one of those is correct for choosing bars and wrong for a candidate set -
the collapsed repeat is exactly the series a trend chart exists to show. Nothing
in the candidate pass dedupes and nothing drops on size. Measured 2026-09-08 on
the nine bounded fixtures (`tests/fixtures/canaries` and
`tests/fixtures/pages`), the two passes keep 17 elements - 9 quantities and 8
dates - where `numeric_facts` keeps 11 facts; on
`tests/fixtures/pages/article.html` alone it is 3 quantities and 4 dates
against 3 facts.

`numeric_facts` is untouched and still behaves that way for the planner that
calls it. Row 2 added a producer beside it rather than repairing it in place.

**The span ends where the reading ends.** A trailing word is inside a quantity's
span only when it was read as the unit, so `1,200 MW` and `$4.5 billion` are
excerpts and `40 percent of` never is. A date's span is the whole match with
nothing trimmed off either end, so `15 March 2026` keeps the month word that
makes it readable on the page. Either way the excerpt is something a reader can
find, rather than a phrase the pattern happened to touch.

### What the date pass will read, and what it refuses

Four shapes, tried longest-first so a full date is never read as the bare year
inside it:

| Written | `value` |
| --- | --- |
| `2026-03-15` | `2026-03-15` |
| `15 March 2026`, `15th Jan. 2026` | `2026-03-15`, `2026-01-15` |
| `March 15, 2026` | `2026-03-15` |
| `2026`, alone and inside 1900-2100 | `2026` |

Everything else is refused, and each refusal is the same rule: a date the
article did not write is not a date it stated.

- **A relative date.** "Three years ago" resolves against a publication date the
 article never wrote (decision 4). The contract's value grammar refuses it too,
 so no producer can write one by accident.
- **A slash date.** `03/04/2026` is 3 April in one country and 4 March in
 another. Neither reading is stated, so neither is taken - the year is
 unambiguous and it is still claimed.
- **A day the calendar does not have.** `February 31, 2026` is refused outright
 rather than rounded to a day that exists, and the digits stay available to the
 number pattern.
- **A four-digit run that is not a year.** A price (`$2026`), a decimal
 (`2026.5`), a thousands separator (`1,200`) and a year either side of
 1900-2100 are all numbers.

`YEAR_MIN` and `YEAR_MAX` are the bounds, and they are one definition rather
than two: they moved off `visual_planner` in this row so the pass that claims a
bare year and the pass that refused to plot one read the same pair. The second
of those retired on 2026-09-13 and the constants stayed here, where the pass
that still needs them lives.

### Two passes, one stretch of characters

Both patterns match `2026`. `settle` is the rule that decides which keeps it,
and `KIND_PRECEDENCE` is the order: **the date wins on any shared character**,
whether the two spans are equal, nested either way round, or merely crossing.
The quantity is dropped whole. The ruling and what it costs are in the design
rationale below.

The check is every pair of candidates against every other, which is quadratic in
one article and bounded by `elements.max_per_article` - it cannot grow with the
archive (Guardrail #12). Measured 2026-09-08 on a a developer machine with
Python 3.14.2: on the densest bounded fixture, 11 candidates settle to 7 in a
median 0.0116 ms, spread 0.0111-0.0167 ms over 9 runs of 200. At the ceiling -
256 from each pass - 512 candidates settle to 384 in a median 12.37 ms, spread
11.92-13.13 ms over 9 runs of 20. The whole table for that fixture, both passes
and the rule together, is a median 0.384 ms, spread 0.366-0.401 ms.

**The rule is between the two regex passes and is not a property of the table.**
The contract does not refuse an element whose span sits inside another's,
because a `quote` carrying a `quantity` inside it is the shape the
model-anchored kinds need and a blanket validator would refuse that too.

### What a pattern over fetched bytes can hand you

Fetched text is data (`CLAUDE.md` Guardrail #11), and a hostile or broken page can
follow a number with a 600-character hyphenated word, or state a 200-digit
serial number. Two bounds keep that from raising in the middle of an article:

- A value too wide to write is not a quantity. It is not emitted and it is not
 counted, because it never was one.
- A word too wide to be a unit is read as no unit. The element still lands with
 its span; only the unit reading is refused.

The bounds are the contract's own, exported as `VALUE_MAX_LENGTH` and
`UNIT_MAX_LENGTH`, so the producer refuses what the shape would refuse rather
than carrying a second copy of the numbers.

### The value is text, and it has one spelling

`4.2 billion` and `4,200,000,000` are one quantity, so they have to compare
equal as strings or pinning the value as text buys nothing. The pass writes the
plain decimal form with no exponent and no trailing zeros: `4200000000` for
both. `span_excerpt` still holds whichever of the two the article wrote.

## The label call: what the model may say about a candidate

The candidate pass says where every figure is. It cannot say what any of them
means, because meaning is not in the bytes. The label call is the pass that asks, and it
lives in
[`backend/idhazh/classify/calls.py`](../../../backend/idhazh/classify/calls.py).

One sentence governs it: **code finds and cuts every character a reader will
see, and the model points at where to cut and says what the cut means.**

The model is given the item's title, the whole article one addressed sentence
per line, and the candidate table addressed by `element_id` - the article rather
than a summary of it, because a compression cannot carry a series it dropped and
judging what an item is about against text that lost the figures is judging the
wrong document. Both blocks are fenced as untrusted data (Guardrail #11). The
addresses are ours; the sentences are a stranger's web page.

**No field of the reply accepts a number.** Not a value, not a unit, not a
count, not a span and not a character offset. Every position the model may name
is a string address code printed for it - `s7` for a sentence, `quantity-19-33`
for a candidate - so a figure the article does not carry is unreachable by
grammar rather than caught by a check downstream. That is the row's oracle and
it is asserted against the generated schema, beside a shape that fails the same
assertion so the check is known to be able to go red.

Every field the reply may carry, what it is for, and who reads it. Counts are
from run 34943695821 shard 3, 20 articles, 2026-09-15.

| Field | What we ask for | Why | Who reads it | Found |
| --- | --- | --- | --- | --- |
| `labels[].element_id` | the address of a figure the candidate pass found | points rather than types, so a number cannot be invented | element table, then the chart | 60 |
| `labels[].measure` | what the figure measures, in the article's words | `4,200` is not an axis label; `exports` is | the chart's axis | - |
| `labels[].dimension` | what it varies over - year, region | what makes a series a series | the chart | - |
| `labels[].entity` | whose figure it is | two numbers share a chart only if they measure comparable things | the chart's grouping | - |
| `labels[].time_element_id` | the address of the date this figure belongs to | the whole of a time series | the chart's time axis | - |
| `labels[].attribution` | named / self_reported / anonymous / unattributed | a figure a company said about itself is not one a regulator published | element table | - |
| `labels[].hedge` | did the article say "about", "expects", "may" | a hedged figure must not be drawn as a fact | element table | - |
| `labels[].salience` | primary / supporting / background | which figure the story is about. A word, never a score | the chart's ranking | - |
| `proposed[]` | a figure in digits the candidate pass missed | the pattern misses figures inside odd punctuation. Model proposes, code re-reads the characters | the chart | **0 of 20** |
| `entity_mentions[]` | organisations and people, and where each is named | groups "OpenAI", "ChatGPT", "the company" into one thing | **the chart's category axis** - `mention_elements` is the only producer of `ENTITY` | 87 |
| `place_mentions[]` | the same, for locations | same | **the chart's category axis** - the only producer of `PLACE` | 15 |
| `quotes[]` | two sentence addresses, no text | indices only: an exact search rejects a real quote over one changed word, silently | **nobody** - no renderer compiles a quote | 24 |
| `claims[]` | the same, for the article's own assertions | same | **nobody** | 73 |
| `keyphrases[]` | up to 8 phrases copied from the article | "the only search surface that needs no embedding model" | **nobody** - search uses the embedding vector | 138 |
| `lede_sentence_ids[]` | the 1-2 sentences carrying the main point | carried for `lead_coverage` | **nobody** - `lead_coverage` is a deterministic function | 20 |

`labels` was empty on 8 of 20 articles and `proposed` on all 20.

**The prompt names these eight fields and no others, and a test holds it
there.** `LabelReply` forbids an unknown key, so a prompt asking for a field the
reply has no room for does not fail a run: the decoder moves the probability
behind that key onto the keys the grammar does allow. A field the prompt stops
describing is still required, and is still emitted with nothing said about it.
Both are silent, and both cost quality on every item.
`test_the_label_prompt_names_every_field_of_the_reply_and_no_other` reads the
names the prompt introduces at the left margin and compares them against
`LabelReply.model_fields`. The three recorded-byte fixtures beside it say the
prompt moved; this one says the move is wrong, which is the difference that
matters the moment somebody re-records.

**The two mention lists reach a reader, and that was measured rather than
assumed.** `elements.py` mints only `QUANTITY` and `DATE`; `ENTITY` and `PLACE`
exist only because these two lists produce them. Over the published archive on
2026-09-15, 495 bar charts have shipped and 404 of them - 82 percent - open on a
category a `DATE` cannot supply, so a model-found mention filled it. Deleting
the two lists takes the picture off four charts in five.

**`quotes` and `claims` are unbuilt, not barred.** Section 0a bars republishing
article bodies **to a reader**; a `SentenceRange` carries two addresses, a
speaker, an enum and a boolean, and no text. What is true of them is narrower
and still fatal: nothing renders a quote or a claim, and `timeline` sits in
`TYPE_RULES` rather than `UNRULED_TYPES`, so an item with a date and a claim can
be judged reachable, decode a plan, and be refused at render.

**The two mention lists are named for what code takes from them, and that was a
ruling rather than a preference.** A prompt in this repository may not ask a
model to pick a reader-facing tag - a page choosing its own steers a control -
and [`backend/tests/test_tag.py`](../../../backend/tests/test_tag.py) holds every
prompt to it. Asking where an item names an organisation is not that: the model
returns an address and some of the item's own words, code cuts the characters,
and the group key is matched against slugs code already holds. The control is
untouched, the lists carry the Tier 1 word, and the reasoning is in the design
rationale below.

**A band is a word, and the score is code's arithmetic.** `salience` is
`primary`, `supporting` or `background`, and `Element.salience` gets the
midpoint of that band over 0 to 1. The model may not type `0.83`, so it does not
get to; and three words are a judgement a person can check, where a decimal to
two places is a precision nobody has.

**`attribution` is a type, not a sentence**: `named`, `self_reported`,
`anonymous` or `unattributed`. A closed list is what makes the attribution rule
mechanical instead of aspirational, and `unattributed` writes nothing - the item
stated it in its own voice, so there is no attribution to record.

**`time` cites a date element and is never typed.** The date pass exists, so a
label that wants to say when a figure applies names a `date` row of the same
table and code copies the value that row already holds. An address that names no
date drops the time and keeps the measure: a label is several judgements, and
one of them being unusable says nothing about the others.

**`entity` groups under a slug the watchlist holds, and this pass mints none.**
The model names the organisation in the item's words; code matches that name
against the entities we already track. An unknown name is one we do not track
yet, and inventing a slug for it would put two spellings of one company in two
groups for ever. The alias ledger is separate work.

### What `proposed` is for, now that the candidate pass exists

It is the escape hatch for a figure the pattern missed, and after the candidate
pass landed there are two ways left to miss one.

**The bound on work.** `elements.max_per_article` keeps the first 256 figures in
article order, and a dense long article states more than that. The figures after
the cap are exactly the ones nobody can label. So the merged table is bounded by
`max_per_article` **plus** the proposal cap rather than by `max_per_article`
alone: spending the recovery out of the pattern's budget would make the escape
hatch unreachable on the articles that need it. There are at most four
proposals, so the total is still a stated bound, and the merge only ever adds -
nothing the pattern found is evicted.

**A character the pattern cannot start on.** The number pattern refuses a run of
digits glued to a word or a hyphen, which is what keeps `COVID-19` from reading
as a quantity. A proposal is re-read in the article's own context, with that
refusal still in force, so a figure the pattern structurally cannot reach stays
unreachable. That is the conservative half of the trade and it is deliberate.

Four refusals, and each is ambiguity rather than a near miss:

- **A sentence address that names no sentence.** Nothing to search.
- **A surface that occurs twice in its sentence, or not at all.** This is the
 mis-pointing failure no span check can see - the span would be real, just the
 wrong one - so ambiguity is refused rather than guessed.
- **A surface holding two figures, or none.** Same rule, one level down.
- **A number spelled out in words, and a relative change.** "About a third" and
 "doubled" have nothing for the pattern to parse, and a figure worked out from
 them is a derived value rather than a found one.

**A proposal over characters the pass already read is dropped before anything is
settled.** A second reading of a stretch of characters code already read is not
a recovery, and leaving it to `settle` would let the later pass take a span off
the earlier one on nothing better than which offset came first.

`candidates_found` counts every proposal that read as a figure, including the
ones dropped next. It is one count per pass taken before the rules that remove,
which is what keeps it able to say the cap bit and by how much.

## The four kinds only a model can find

No pattern reaches an organisation, a place, a quotation or an assertion. The label call
points at all four, and code cuts every character. The producers are in
[`backend/idhazh/classify/calls.py`](../../../backend/idhazh/classify/calls.py)
beside `proposed`, because they read the same reply.

**The anchoring rule is different for each pair, and that is the point.**

| Kind | What the reply carries | How code anchors it |
| --- | --- | --- |
| `entity`, `place` | a group key, and up to four `(sentence address, the words)` mentions of it | Each mention is searched inside **its own named sentence** and must occur there exactly once. Every hit is one element |
| `quote`, `claim` | the address of the first and last sentence | The run between them is sliced whole, trimmed of surrounding whitespace by moving the offsets |

**A name is never searched for.** An item writes "Vestas Wind Systems A/S" once
and "Vestas" four times, and the fullest form may appear nowhere verbatim - so
searching for it would reject the thing it was meant to find. Resolving a name to
its mentions is what a semantic model is good at and string matching is bad at,
which is why the model does that half and code does the cutting.

**The mention draws; the name never does.** `drawn_label(group)` answers with the
longest mention that anchored, and a page has nothing else to show: the name is
model-authored words with no span, and a mention is the item's own characters at
an offset code computed. That is the invariant an implementer is most likely to
lose, because drawing the name is easier and looks tidier, so it is the second
half of this row's oracle and it is asserted with a counter-implementation beside
it.

**The name lands only as a slug this project already tracks.** An unknown name is
one we do not track yet, and minting a slug for it would put two spellings of one
organisation in two groups for ever. Grouping the rest is the alias ledger's job
and it is separate work.

**A quote is addresses, never text.** An exact search for a long quotation
rejects a real one over a single changed word, and it does so silently, which is
worse than no check at all. A run wider than the 500 characters the shape holds
is **dropped rather than cut down** - a truncated excerpt stops being the
characters its span names, and that is the one property every one of these kinds
exists to keep.

**A rejection is per element, never per article.** A mention that will not anchor
drops itself; a group that anchored none of its mentions drops itself; a range
whose address names no sentence drops itself. Every sibling stands and the item
still publishes (`CLAUDE.md` section 1a).

**The settle rule never sees these kinds.** It drops any element sharing a
character with a higher-precedence one, which is right for two patterns reading
one stretch of digits and exactly wrong here: a quote holds every figure inside
it, and both have to survive. So `anchored` runs the settle rule over the pattern
candidates first and merges the model-pointed kinds after it, and two of them
claiming one address is settled by keeping the first.

### A quote's excerpt is article text, and it stops at the element table

`CLAUDE.md` section 0a says article bodies are never republished to a reader. A
`quote` or a `claim` element carries a run of the item's own sentences, so it is
the one element kind whose excerpt is a paragraph of somebody's page rather than
a figure or a name.

It may go where the table goes: into the labelled table the summarize-and-plan call reads, into an
eval row, into a log line, into a fixture. **It may not reach a reader-facing
page**, and neither may a fragment of it. What publishes is the link and our own
summary. A later row that wants to show a quotation is proposing a change to
section 0a and has to take it there, not to this page.

### Two failures no anchoring check can see, recorded rather than papered over

This is permanent and it is stated so that nobody later reads the span check as
covering more than it does.

| Failure | Why no check sees it | What the design does instead |
| --- | --- | --- |
| **Mis-pointing** - the model means one `"5"` and the anchor lands on another | The span is real. `text[span_start:span_end] == span_excerpt` passes, the write-time re-slice passes and the read-time one passes | The per-sentence rule. A surface is searched inside one named sentence and must hit exactly once, so ambiguity is a rejection rather than a coin toss |
| **Mis-labelling** - right span, wrong `measure`, `entity` or `salience` | Tier 2 is a judgement and no string search reaches it | A judgement is only ever attached to an address, so it is checkable against that element's own kind, unit and magnitude. A judgement attached to a free string is checkable against nothing |

Neither is closed and neither is closable by anchoring. What anchoring buys is
that a wrong answer is still *a fact the item states*, at a location a reader can
check, rather than a sentence the model wrote.

### What the label call is not asked for

An **event** and a **relation** are the next thing this table wants and neither is
in it. When they arrive, every actor and object in one has to resolve to a
surviving `entity` element or the row is dropped, because an unanchored arrow is
a causal claim the article did not make.

A **type for a named thing** and a **geographical hint** are sketched in the plan
and are not asked for. `Element` has nowhere to put either, `ElementKind` already
separates an organisation from a location, and a decoded field with no consumer
costs output tokens on every item for ever. Adding one is cheap the day something
reads it.

## The span-drift invariant

A span is two integers, and integers do not know when the string underneath them
has changed. `Article.text` is derived from a page we fetched, through a
sanitizer and a truncation cap, so it moves when any of those three move - and a
table built against yesterday's string, read against today's, cuts characters
nobody wrote.

`ElementTable.span_drift(text)` is the whole check. It cuts `text` at every span
and compares the result to `span_excerpt`. `None` means every span still holds,
so the table is usable against that text. A string means one did not, and it is
a reason the caller can log and record. Nothing is raised there, because the two
callers want opposite dispositions out of one answer.

| Part | Where | What it does |
| --- | --- | --- |
| Write time | `element_table` | Raises `SpanDriftError`. The pass cut every excerpt out of the string it hashed moments earlier, so a mismatch is its own arithmetic being wrong and every article in the run has it |
| Read time | a consumer holding a table it did not build | Records the reason against that item and moves to the next. No sibling changes |
| Census | `elements.extraction_health`, through `telemetry.classify_item` | Catches `SpanDriftError` and writes `span_integrity=false` on that item's row. The item degrades, the run continues, and `span_integrity_rate` is what makes the refusal visible |
| CI | `backend/tests/test_elements.py`, `backend/tests/contracts/` | The nine bounded fixtures re-slice against their own text; a built run of five items with one text moved by a character degrades exactly one |

The write-time half is what makes the one-hash-per-article decision mechanical:
the hash, the length and every excerpt come out of one call against one string,
and the re-slice proves it rather than the call site promising it. Neither
pattern pass can fail it, because each cuts its excerpt at its own offsets. The
failure it exists for is a caller that builds elements from one string and a
table over another - `quantity_elements` and `date_elements` are public and take
any text, so the pre-cap body is one wrong argument away - and plan 11's
producers risk it on every article, because there a model proposes the location
and code cuts at it.

**"Read time" is the moment a consumer reads a table it did not build, and
there is still no such consumer.** Nothing writes an element table to disk:
`span_excerpt` is article body text, which no published payload may carry
(`CLAUDE.md` section 0a), so the pass stays a pure function over one payload and
the check is a function a later stage calls against the text it already holds.
It is correct for that and for a payload from an earlier run if one ever lands,
because it takes the text as an argument and reads nothing else.

**What the run does call is `extraction_health`, and it is a third disposition
rather than a fourth invariant.** It builds the table for one article, catches
`SpanDriftError`, and turns the answer into three cells on that article's
item-health row. A shape refusal is deliberately not caught: a payload the
contract will not hold is failing for every article that took the same path, and
a rate that swallowed it would report the run as healthy.

**It re-slices every span rather than comparing `source_text_hash` first, and
the measurement is the reason.** The hash covers the whole article and the
excerpts cover a few dozen characters of it, so the cheap-looking short-circuit
is the more expensive half. Measured 2026-09-08 on a 12th Gen Intel Core
a developer machine with Python 3.14.2: on the densest captured page - 7 elements over
1,337 characters - the re-slice takes a median 1.15 us against 1.78 us to hash
the text, spread 1.12-1.33 and 1.77-1.87 over 9 runs of 2,000. At the ceiling of
256 spans over 60,000 characters it is 41.30 us against 44.35 us, spread
38.28-53.99 and 41.27-47.17 over 9 runs of 500. So a hash short-circuit would be
a second code path that costs more than the work it skips, on every article for
ever. `source_text_hash` keeps its own job: it says which string this table is
about, which is what `span_integrity_rate` reports against.

**What it answers, and the two things it does not.** It answers whether every
span still cuts its own characters. It does not answer whether the table is
still *complete* for that text - text that grew may hold facts the pass never
saw, and the remedy is to run the pass again rather than to degrade an item. And
it cannot see a span that moved onto identical characters elsewhere in the text:
the excerpt, the value and the unit are all unchanged there, and only
`sentence_index` could be stale. Both are stated rather than implied, because a
check whose limits are folklore gets trusted for things it never did.

**Nothing about the persisted shape moved.** The text a span indexes is not in
the payload and is not going into it, so the invariant cannot be a model
validator and there was no field to add. `element-table.schema.json` is
unchanged and the `version` stamp stays where row 3 left it.

## `context` is gone, and this is the sentence saying so

The retired planner's `NumericFact` carried `context`: a whitespace-cleaned
window of the words around a number, about 50 characters back and 30 forward,
snapped to word boundaries. This shape does not have it.

A derived string is replaced by a pointer. `sentence_index` plus the span says
where the words are, and `Article.text` still holds them, so nothing stores a
second copy of the reader's sentence. That derived string retired with its
producer on 2026-09-13, and this contract never carried it.

## Design rationale

### Break the build on what our own code gets wrong; degrade the item on what one article's data can

`derived_provenance_complete` breaks the build. A displayed value tracing to
neither a Tier 1 element nor a complete provenance chain is a number our own code
could not follow, so it is already wrong everywhere that path runs.

`span_integrity_pass` degrades the item. Span drift is a source text moving -
true of one article, and saying nothing about a sibling. A day of 500 stories
must not fall to one drifted span.

That asymmetry is the whole rule, and it is why the span invariant is the only
exception: every other integrity claim here is a claim about arithmetic we
control.

### A date takes the characters from any quantity it touches

Two patterns read one string and both match `2026`. The pass with the **closed
vocabulary wins**: dates accept a fixed list of calendar shapes and a four-digit
run inside 1900-2100, numbers accept any run of digits. Specificity is the only
property of two patterns that compares mechanically - pass order, span length and
write order are accidents of how code is arranged. A third pass declares its
place in `KIND_PRECEDENCE` or it does not ship.

It covers all four ways two spans can meet, not just the exact tie, or `15 March`
and `2026 hit` would both stand beside the date they sit in.

Measured 2026-09-08 over the nine bounded fixtures: the rule dropped eight
quantities and every one was a year. Two were worse than a plain year - `2027
after` and `2027 only`, where the next word had been read as a unit.

**Why not keep a quantity that carries a unit?** Those same two carry one, because
`after` and `only` are not in the 61-word stop list. The unit reading is itself a
guess; conditioning precedence on it stacks two guesses.

**What it costs, stated:** a real four-digit count written without a separator
loses - "the survey drew 1994 responses" yields a date and no quantity. Write
`1,994` and it survives. A missing candidate degrades one chart; a wrong bar
publishes a figure the article never stated. A test carries the case.

The rule lives in the producer, not the shape: `ElementTable` allows overlap on
purpose, because a `quote` holding a `quantity` is the shape the model-pointed
kinds need.

### The verbatim slice is `span_excerpt`

`raw` is whitespace-cleaned and drops the magnitude word and the unit -
`"$4.5 billion"` becomes `"$4.5"` - so it is not a slice of anything.

`surface` already means "a place something is shown" in 458 sentences across this
repository, `CLAUDE.md` section 11 included. A second meaning inside one contract
is how a word stops carrying information.

`span_excerpt` binds to `span_start` and `span_end` by name, and the invariant is
checked rather than promised: `len(span_excerpt)` equals `span_end - span_start`.
A cleaned string shortens without moving the offsets, so the shape refuses it.

**Why not a slice plus a normalised reading form?** Normalising is a judgement, so
a normalised string in Tier 1 would be the first Tier 1 field a model could
plausibly write, and the tier would stop meaning anything. In Tier 2 it already
exists twice, as `entity` and `measure_canonical`. For a quantity, `value` and
`unit` are the reading and a display form is derivable.

### `candidates_found` is uncapped, keyed by kind, and required

`elements.max_per_article` bounds what a pass keeps, so `len(elements)` saturates
and stops measuring the article. `candidates_found` is what the pass matched
before the bound applied.

**Required, not defaulted**, because a default of zero cannot be told apart from a
pass that found nothing. **Keyed by kind**, because a total that mixes dates into
quantities stops answering the density question the moment the date pass writes
into the same table, and a total cannot be split back apart. **Checked**: a cap
only removes, so a table keeping more of a kind than it counted does not load.

### Shared vocabulary lives in the lower pass

`NUMBER`, the magnitude table, the percent set, the unit stop list,
`normalise_unit`, `YEAR_MIN` and `YEAR_MAX` moved from `visual_planner` to
`backend/idhazh/elements.py`. Two passes read the same vocabulary about the same
bytes, and a duplicated regex is a second definition that drifts the first time
either is fixed.

`_TRIVIAL_MAX` and the context window stayed with the planner. They are its
judgements about what makes a bar, and the candidate pass does not share them.

### The mention lists were named, and the tag control was not narrowed

`test_no_prompt_asks_a_model_for_a_tag` refuses any prompt carrying `lens`,
`event type` or the plural of `entity`, because a page choosing its own
reader-facing tags steers a control. The obvious field name trips it.

The field was renamed rather than the control narrowed. The control protects the
tag vocabulary and a mention list does not touch that vocabulary, so nothing here
needs it changed - and the name is better, not merely permitted: the mention is
Tier 1 and is what draws, while the group key is Tier 2. `entity_mentions` says
the mentions are the payload.

**What it costs:** the control now passes on a prompt that does ask about an
organisation, so silence could later read as approval. This section is the
record, and `test_the_mention_lists_do_not_reach_the_tag_control` holds the same
three words out of the reply schema as well - the schema is handed to the decoder,
so a class docstring is prompt text too.

### A mention is an element, so the four model-pointed kinds needed no contract change

A mention's span is its own characters, and several mentions of one organisation
are several elements. The grouping key is `Element.entity`, which already exists,
is already a slug, and is filled by matching the watchlist rather than by minting.
No schema moved and no fixture gained a key.

### `extractor` is `model`

The plan spells it `model_proposed`. The contract already carried `model`, and
`entity`, `place`, `quote` and `claim` are model-pointed the same way without
being proposals - so `model_proposed` would be wrong on four of the five paths
that write it. The field names **who found it**, not what shape was asked for.

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Name the slice `surface` | The word already means "a place something is shown" in 458 sentences here, `data-surface` included. A second meaning inside one contract makes the word stop carrying information | Fowler |
| Name the slice `raw`, or reuse `NumericFact.raw` | It is whitespace-cleaned and drops the magnitude word and the unit, so it is not a slice and cannot prove provenance | Fowler, row 4 decision 2 |
| Two fields: the slice plus a normalised reading form | Normalising is a judgement, so it cannot be Tier 1 without breaking the tier; in Tier 2 it duplicates `entity` and `measure_canonical`; for a quantity it is derivable from `value` and `unit` | Andre |
| A per-element text hash | Redundant against the per-article hash plus the re-slice, and it is a hash per element on every article for ever | Fowler |
| One flat tier | Then nothing distinguishes a character range code cut from a word a model chose, which is the entire trust argument | Andre |
| Ship only the two kinds that have producers | Six kinds in one contract with one changelog entry is cheaper than four later widenings of a persisted shape | Fowler |
| Carry the element cap in the contract | A cap is a tunable and lives in `config/` (Guardrail #6). The shape says what an element is, never how many a producer keeps | Fowler |
| Reuse `numeric_facts` as the candidate source | It collapses a figure repeated across two periods, drops a magnitude at or below two, drops a bare year, nulls a stop-listed unit and stops at 16. Every one of those is right for picking bars and wrong for a candidate set | Row 2 decision 2 |
| Repair `numeric_facts` in place instead of adding a pass | Its caller wants the drops. Two callers want opposite things, so they are two functions | Fowler |
| Count the candidates after the cap | A capped counter returns a plausible integer, so the failure is silent. The count is taken before the cap or it is not a count | Andre |
| One total instead of a count per kind | It stops answering the density question as soon as the date extractor writes into the same table, and a total cannot be split back apart | Fowler |
| The quantity wins an overlap, or the longer span wins, or the first pass wins | Length and pass order are accidents of how the code is arranged. On the captured pages the quantity reading was the wrong one every time: eight dropped quantities, eight of them years, two of them years with the next word read as a unit | Andre |
| Keep the quantity when it carries a unit | `2027 after` and `2027 only` both carry one, because `after` and `only` are not in the 61-word stop list. The unit reading is a guess, so conditioning precedence on it stacks two guesses | Andre |
| Refuse every overlapping span in `ElementTable` | A `quote` carrying a `quantity` inside it is the shape plan 11 needs, so a blanket validator would have to be reversed. The rule is between the two regex passes and lives with them | Fowler |
| Count `candidates_found` after the overlap rule | A date pattern that swallowed every figure would then report an article with no figures in it - the same silent failure the counter exists to prevent, one level along | Andre |
| Read `Month YYYY` as a date | The value grammar holds `YYYY` or `YYYY-MM-DD`, so it would need a day nobody wrote. The bare-year branch claims the year anyway, and dropping the branch also stops `may` and `march` being read as month names when no digits are near | Andre |
| Read a slash date | `03/04/2026` is two different days depending on the country. Choosing one states a date the article did not | Andre, decision 4 |
| Resolve a relative date | "Three years ago" resolves against a publication date the article never wrote, on the very plan that establishes the trust boundary | Andre, O45 |
| Duplicate the number pattern in the new pass | Two definitions of one concept, and the first fix to either would land in one of them | Fowler |
| Raise on a 200-digit run or a 600-character unit word | Degrade, do not fail (`CLAUDE.md` section 1a). A pattern over fetched bytes will meet both, and one hostile page must not take an article's whole table down | Andre |
| Exact-search a name to find its mentions | It confuses a location with a label. The fullest form may appear nowhere verbatim, so the search rejects the very thing it was written to find | Andre, row 2 decision 1 |
| Ask the model for coreference chains | Exact and prefix matching over spans code already holds does most of it, and the model's version cannot be span-validated | Andre, pseudo-plan 10.6 |
| Exact-search a quotation to anchor it | One changed word rejects a real quote, silently. Two sentence addresses cannot fail that way | Andre, row 2 decision 3 |
| Draw the group name instead of a mention | The name has no span, so a page would show a string the item may not contain. The mention is the item's own characters at an offset code computed | Andre, invariant 2 |
| Truncate a quotation too wide for the shape | A cut-down excerpt stops being the characters its span names, which is the one property these kinds exist to keep. The range is dropped instead | Fowler |
| Run the settle rule over the model-pointed kinds | A quote holds every figure inside it, so precedence would delete one of the two. The rule is between the two patterns and the merge happens after it | Fowler |
| One flat mention list carrying the name on every entry | The name and the band are then repeated per mention, and output tokens are the expensive direction on this runner | Andre, pseudo-plan 10.6 |

### Why the schema stem is `element-table`

One `source_text_hash` per article, never per element, needs a per-article
container. The contract is `ElementTable` and its stem mirrors its class, the way
every other stem here does.

### The label call is built and nothing dispatches it

The request, the reply shape, the parser and every anchoring path ship; no stage
calls them. The label call alone produces a labelled table and no page - the call
that turns it into a summary and a visual appends to this call's message array,
so the article prefills once. Wiring it in alone would spend a model call per item
for an answer nothing reads. There is no flag and no dead knob: production
behaviour is byte-identical until the second call lands.

## See also

- [../contracts/schemas.md](../contracts/schemas.md) - the contract subsystem: the base model, the generated schemas, and the drift gate over both.
- [../publishing/visuals.md](../publishing/visuals.md) - the picture, which is decided from this table.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - what a read over a growing collection has to declare.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #3 (contracts before logic), Guardrail #6 (no hardcoding), Guardrail #11 (fetched text is data), section 11 (schema versioning).
- [../../../TODO/20260905-08-element-table-plan.md](../../../TODO/20260905-08-element-table-plan.md) - the plan this shape was written for, and the producers that follow it.
- [../../../TODO/20260905-11-two-call-planner-plan.md](../../../TODO/20260905-11-two-call-planner-plan.md) - the plan the label call belongs to, and the call that reads its table next.
