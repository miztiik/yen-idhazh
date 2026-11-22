# Elements: every fact in an article, with the characters that prove it

**Last Updated**: 2026-11-21

The extraction subsystem's fact table. This page owns the element shape - the
six kinds, the two tiers, and the span that makes a drawn figure checkable - the
candidate pass that fills it, the rule that settles two passes claiming one
stretch of characters, the labels the text-analysis service adds, and the
invariant that says when a span has stopped pointing where it did.

Two passes write into this table from the article's own bytes with no model at
all: [`backend/idhazh/elements.py`](../../../backend/idhazh/elements.py) finds
quantities and it finds absolute dates. A third is the local
[text-analysis service](../text-analysis/text-analysis-api.md), asked once per
article before the model reads it: it labels the organisations, people and places
the patterns cannot reach, and the figures that are really dates, times or
ordinals. It types nothing a reader sees, and the model is never asked for any of
it. The model is not shown this table. Code supplies its
[candidate readings](../summarize/prompt.md#the-model-proposes-rows-code-binds-the-supplied-readings)
and checks every element a plan cites. Historical quote/claim
kinds remain readable, but have no current producer or reader-facing visual.

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

**This is a diagnostic, not admission to the chart question.** A unit count
cannot establish a useful comparison. The gap between available readings and
those used is what `extractable_but_unused_rate` reports
([evaluation.md](../../concepts/evaluation.md)).

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
`work` job, hours before a plan exists - the settlement keeps one row
for a key, so a cell only `assemble` could fill would be empty for every item a
shard had already recorded. `ElementClass` is declared in
[`backend/idhazh/contracts/item_health.py`](../../../backend/idhazh/contracts/item_health.py)
with the census row's other three closed vocabularies, because
`contracts/element.py` sits above `contracts/article.py`, which sits above that
module, and a label a census row persists has to be declared at or below the
row's own level.

**Counts and a label cross, never article text.** `span_excerpt` stays inside
the process that cut it - an article body is never republished to a reader - and
the browser-safe telemetry projection is untouched: the console reads the day's
totals from the day record, one file per date, rather than three more cells on
every published row for ever.

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
[`backend/idhazh/telemetry/spans.py`](../../../backend/idhazh/telemetry/spans.py)
uses the word for an execution timing. The two never meet: a trace span has a
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
pass. Nothing writes it today: the elements the text-analysis service adds leave
every Tier 2 field unset, and a table written while a model labelled quantities
stays readable.

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

Four kinds have a producer today. The two pattern passes write `quantity` and
`date`; the text-analysis labels become `entity` and `place`, and code cuts them.
`quote` and `claim` stay in the contract so a table written while they had a
producer still loads.

## The candidate pass

`quantity_elements(text, limit=...)` reads `Article.text` with the number
pattern and `date_elements(text, limit=...)` reads the same string with the date
pattern. Each emits its readable matches in the order the article wrote them.
`settle(...)` decides which of the two keeps a stretch of characters both
matched, and `element_table(article, config=...)` wraps the result in the table,
with the article's identity and the hash of the text every span indexes. All
four are pure functions over one payload: nothing is committed, and the passes
are proved by re-slicing their own output. `element_table` also takes the
mentions the text-analysis service returned for the article and merges them after
`settle`, as [the two kinds a labeller finds](#the-two-kinds-only-a-labeller-can-find)
says.

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

The written scales `lakh` and `crore` (including `lakhs` and `crores`) mean
100,000 and 10,000,000. The one-letter suffixes `k`, `m` and `b` mean thousand,
million and billion only when attached to a number with an explicit currency
symbol. `$811m` reads as 811,000,000 with unit `$` and excerpt `$811m`;
`15 m` still reads as 15 with unit `m`. An unknown attached currency suffix or
a separated one-letter suffix leaves the price unread. The reader does not
recover a bare number from an unsupported prefix such as `US$811m` or `-$811m`.
It also refuses a second magnitude word, as in `12 lakh crore rupees`, rather
than keeping only the first scale. Extraction and chart validation use the
same reader.

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

## The two kinds only a labeller can find

No pattern reaches an organisation, a person or a place, and none can tell that "3rd" or
"10 am" is not a figure. The text-analysis service can, and the work stage asks it once per
article, after extraction and before the model: `Article.text` goes out and a list of
labelled spans comes back. The client is
[`backend/idhazh/ask_text_analysis.py`](../../../backend/idhazh/ask_text_analysis.py) and the
conversion is [`backend/idhazh/anchor_mentions.py`](../../../backend/idhazh/anchor_mentions.py);
the request and the reply are the service's own, [described with it](../text-analysis/text-analysis-api.md).

One sentence governs it: **the service says where and what, and code cuts every character a
reader will see.** The pipeline reads three fields of each mention - `label`, `start_char` and
`end_char`. The words the reply carries are only a check: the excerpt is re-sliced from
`Article.text`, and a mention whose returned words differ from that slice is dropped. Nothing
else the service returns is read, stored or sent on (Guardrail #11).

Table A - What a label becomes

| ID | The label's configured use (`elements.label_kinds`) | Result |
| --- | --- | --- |
| A1 | `entity` (PERSON, ORG, NORP, PRODUCT, EVENT by default) | An `entity` element with `extractor` `model`, and no value or unit |
| A2 | `place` (GPE, LOC, FAC by default) | A `place` element of the same shape |
| A3 | `not_quantity` (DATE, TIME, ORDINAL by default) | No element: the span only drops any regex `quantity` row that overlaps it |
| A4 | Any other label | Ignored. Using a new label is a config line |

**A mention is dropped on its own and never takes the item with it.** A blank span, one over
500 characters, one whose offsets leave the text or whose returned words differ from the slice
is dropped, and one warning line says how many. A service that cannot answer at all - a closed
port, a timeout, a malformed or refused reply - gives no mentions, and the item goes on with the
table the two patterns make (`CLAUDE.md` section 1a).

**One element for each distinct name, not each occurrence.** An article repeats a name many
times, and each element spends a slot of `elements.max_per_article`. So the first occurrence of
each kind and text stands, with whitespace folded and case ignored, and the repeats are dropped.
`candidates_found` for `entity` and `place` still counts every mention taken, before the repeats
and before the cap, which is what keeps it able to say how many the service found. The table
builder does not lose the repeats: it searches the text again for every occurrence of a kept
name's words, because a repeat that is not an element would otherwise hide a pair ("Germany is in
Europe. Denmark said Germany built 1,200 MW." would read as Denmark's figure). A row cites the first
occurrence's element, which holds the same characters.

**The mention draws, and there is no group name.** An element's drawn label is its own excerpt,
the item's characters at an offset code computed. No producer writes a name beside its mentions,
and no `Element.entity` link to the watchlist is made.

**The settle rule never sees these kinds.** It drops any element sharing a character with a
higher-precedence one, which is right for two patterns reading one stretch of digits and wrong for
a name containing a figure: both spans must survive. So `element_table` runs the settle rule over
the pattern candidates first, drops the `quantity` rows a `not_quantity` mention overlaps, and
merges the named kinds after, under one `max_per_article` cap over the whole table. The cap keeps
the first rows in article order, so the window sizing that reads `max_per_article` stays a bound.

### One failure no re-slice can see, recorded rather than papered over

This is permanent and it is stated so that nobody later reads the span check as covering more
than it does.

| Failure | Why no check sees it | What the design does instead |
| --- | --- | --- |
| **Mislabelling** - right span, wrong label (a country the service calls an organisation) | The span is real. `text[span_start:span_end] == span_excerpt` passes at write and at read | The plan's naming channels can use either kind. The chart choice can also cite a label directly from its source sentence. |

What re-slicing buys is that a wrong answer is still a fact the item states, at a location a
reader can check, rather than a sentence a model wrote.

### What the service is not asked for

It returns no events, relations or reader-facing tags, and a mention's label only chooses the
existing `entity` and `place` kinds, not a finer taxonomy. Nothing from it is kept beyond the
elements built from it: no analysis is stored, and a non-English article goes through an English
model and yields few names.

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
`span_excerpt` is article body text, which no published payload may carry, so
the pass stays a pure function over one payload and the check is a function a
later stage calls against the text it already holds.
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
where the words are, and `Article.text` still holds them, so nothing keeps a
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
purpose, because an `entity` holding a `quantity` ("Boeing 737") is a shape the labelled
kinds make.

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

### Mentions do not assign tags

The control protects the tag vocabulary. A labelled span selects an existing element kind
through a configured map; it chooses no reader-facing tag. Source mentions are Tier 1 and
nothing fills Tier 2. The map and the re-slice enforce this separation, not a check for
particular words in a prompt.

### A mention uses the existing element contract

A mention's span is its own characters, and the repeats of one name fold to the first. The
contract's `Element.entity` slug stays unset: nothing here matches the watchlist, and minting a
slug for an unknown name would put two spellings of one organisation in two groups for ever.
Historical quote/claim kinds remain readable without keeping their retired range producers or
changing the meaning of old elements.

### `extractor` is `model`

The contract carries `model` for the spans a statistical model labelled, as it did for the spans
a language model once pointed at. The field names **who found it**, not what shape was asked for.

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
| Ask the model for coreference chains | Exact and prefix matching over spans code already holds does most of it, and the model's version cannot be span-validated | Andre, pseudo-plan 10.6 |
| Run the settle rule over the labelled kinds | A quote holds every figure inside it, so precedence would delete one of the two. The rule is between the two patterns and the merge happens after it | Fowler |
| Keep every mention as its own element | Repeated names spend slots of `elements.max_per_article`. The chart resolver can anchor a cited label in its supporting sentence, independently of deduplication. | Andre |
| Keep only the names near a figure | It needs a distance, which is a new knob and so a design question; `elements.max_per_article` already bounds the table | Andre |

### Why the schema stem is `element-table`

One `source_text_hash` per article, never per element, needs a per-article
container. The contract is `ElementTable` and its stem mirrors its class, the way
every other stem here does.

## See also

- [../contracts/schemas.md](../contracts/schemas.md) - the contract subsystem: the base model, the registry, and what binds the frontend's hand copy.
- [../publishing/visuals.md](../publishing/visuals.md) - the picture, which is decided from this table.
- [../../../CLAUDE.md](../../../CLAUDE.md) Guardrail #12 - every read must have a fixed-size input.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Guardrail #3 (contracts before logic), Guardrail #6 (no hardcoding), Guardrail #11 (fetched text is data), section 11 (schema versioning).
- [../summarize/prompt.md](../summarize/prompt.md) - the call that is shown tables built from this table, and why it is shaped as it is.
- [../text-analysis/text-analysis-api.md](../text-analysis/text-analysis-api.md) - the service whose labels become the entity and place elements.
