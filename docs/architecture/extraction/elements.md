# Elements: every fact in an article, with the characters that prove it

**Last Updated**: 2026-09-10

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
twice.** `visual_planner.same_unit_bars` groups the chosen bars by unit and the
bars are distinct by construction, so counting a repeated figure here would call
an article chartable that no planner could ever draw - and the rate built on it
would carry that gap for ever while claiming to measure the planner. The empty
unit is a group like any other, which is the reading `chart_is_reachable`
already takes.

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

**The threshold is `visuals.min_chart_points` and not a second knob** (Rule #6).
Mint one and the console can call an article chartable while the planner refuses
to draw it, and the rate then measures two knobs drifting apart rather than
measuring the planner.

**Where the three cells go.** `elements.extraction_health(article,...)` is the
one caller in the run: it is called from `telemetry.classify_item`, which builds
the item-health census row, and it writes `span_integrity`, `elements_found` and
`element_class` on that row. It lands there rather than beside the visual
decision because two writers append that ledger and the earlier one runs in the
`work` job, hours before a plan exists - `append_item_health` keeps the first row
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
pattern passes write `quantity` and `date`; call 1 points at the other four and
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

**The offsets are not new work.** `visual_planner.numeric_facts` has always
computed `match.start` and `match.end`, and has always thrown them away.
This pass keeps them and cuts `span_excerpt` at them.

**What the pass keeps that the planner drops.** `numeric_facts` picks a few bars
for one chart, so it collapses a figure repeated across two periods into one
fact, drops a magnitude at or below two, drops a bare year, and stops at 16.
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
bare year and the pass that refuses to plot one read the same pair.

### Two passes, one stretch of characters

Both patterns match `2026`. `settle` is the rule that decides which keeps it,
and `KIND_PRECEDENCE` is the order: **the date wins on any shared character**,
whether the two spans are equal, nested either way round, or merely crossing.
The quantity is dropped whole. The ruling and what it costs are in the design
rationale below.

The check is every pair of candidates against every other, which is quadratic in
one article and bounded by `elements.max_per_article` - it cannot grow with the
archive (Rule #12). Measured 2026-09-08 on a a developer machine with
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

Fetched text is data (`CLAUDE.md` Rule #11), and a hostile or broken page can
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

## Call 1: what the model may say about a candidate

The candidate pass says where every figure is. It cannot say what any of them
means, because meaning is not in the bytes. Call 1 is the pass that asks, and it
lives in
[`backend/idhazh/classify/calls.py`](../../../backend/idhazh/classify/calls.py).

One sentence governs it: **code finds and cuts every character a reader will
see, and the model points at where to cut and says what the cut means.**

The model is given the item's title, the whole article one addressed sentence
per line, and the candidate table addressed by `element_id` - the article rather
than a summary of it, because a compression cannot carry a series it dropped and
judging what an item is about against text that lost the figures is judging the
wrong document. Both blocks are fenced as untrusted data (Rule #11). The
addresses are ours; the sentences are a stranger's web page.

**No field of the reply accepts a number.** Not a value, not a unit, not a
count, not a span and not a character offset. Every position the model may name
is a string address code printed for it - `s7` for a sentence, `quantity-19-33`
for a candidate - so a figure the article does not carry is unreachable by
grammar rather than caught by a check downstream. That is the row's oracle and
it is asserted against the generated schema, beside a shape that fails the same
assertion so the check is known to be able to go red.

| The reply says | What code does with it |
| --- | --- |
| `labels[]` - a candidate's `element_id`, and what it means | Writes the Tier 2 cells onto that element. An address the pass never minted drops **that label**; its siblings stand |
| `proposed[]` - a sentence address and the words a figure was written in | Searches only the named sentence, demands exactly one hit, and re-reads the value and the unit from the article's own bytes. Stamped `extractor: model` |
| `entity_mentions[]`, `place_mentions[]` - a group key, and the sentences the item names that thing in | Searches each mention inside its own named sentence. Every hit is one `entity` or `place` element carrying the item's characters |
| `quotes[]`, `claims[]` - two sentence addresses, no text | Slices the run of sentences between them into one `quote` or `claim` element. Indices only: an exact search over a long quotation rejects a real one over a single changed word, silently |
| `keyphrases[]`, `lede_sentence_ids[]` | Carried for search and for `lead_coverage`. Nothing draws them |

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

No pattern reaches an organisation, a place, a quotation or an assertion. Call 1
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

It may go where the table goes: into the labelled table call 2 reads, into an
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

### What call 1 is not asked for

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
| CI | `backend/tests/test_elements.py`, `backend/tests/test_contracts.py` | The nine bounded fixtures re-slice against their own text; a built run of five items with one text moved by a character degrades exactly one |

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

`visual_planner.NumericFact` carries `context`: a whitespace-cleaned window of
the words around a number, about 50 characters back and 30 forward, snapped to
word boundaries. This shape does not have it.

A derived string is replaced by a pointer. `sentence_index` plus the span says
where the words are, and `Article.text` still holds them, so nothing stores a
second copy of the reader's sentence. `NumericFact.context` is untouched by this
contract and retires when its own producer does.

## Design rationale

### Which invariants break the build, and which degrade the item

Two invariants were declared build-failing while this subsystem was being
planned and never ruled on, and a coverage row cited the span invariant's
softening as though it had settled all three
([`TODO/20260902-visual-planner-pseudo-plan.md`](../../../TODO/20260902-visual-planner-pseudo-plan.md),
12.9 G13). It had not. Here is the ruling, one sentence each.

**`derived_provenance_complete` breaks the build.** A displayed value that
resolves to neither a Tier 1 element nor a complete provenance chain is a number
whose origin our own code could not trace, so it is already failing for every
value that took the same path, and degrading the one item that happened to
surface it hides the rest.

**`span_integrity_pass` degrades the item.** It is the reporting face of the
invariant on this page rather than a second rule, so it inherits this page's
disposition: one article's text moving is one article's problem, and a day of
500 stories taken down by one drifted span is exactly the corpus-wide refusal
this row was told not to build.

**The span invariant is the exception because its cause sits outside our code.**
Every other integrity claim in that document is a claim about arithmetic we
control, and a claim about our own arithmetic that fails once is failing
everywhere it runs; span drift is a source text moving, which is true of one
article and says nothing about a sibling.

That is the whole rule, and it is the same one the write-time and read-time
halves above already follow: **break the build on what our own code can get
wrong, degrade the item on what one article's data can.**

`derived_value_rate` is the metric the pseudo-plan puts beneath
`derived_provenance_complete` (12.11 G21), so this ruling names what it would
report on; it is not built here and belongs to the plan that ships the derived
values it counts.

Authority: **Andre** (the trust boundary between what code found and what a
model said) on `derived_provenance_complete`; **Fowler** (persisted contracts,
and where an invariant is enforced) on `span_integrity_pass` and on the
exception rule.

### A date takes the characters from any quantity it touches

Two patterns read one string and both match `2026`. One of them has to lose, and
the rule has no other home than the row that put the second pass in the table.

**The ruling: on any shared character the date element survives and the quantity
element is dropped whole.** It covers all four ways two spans can meet - equal,
the date containing the quantity, the quantity containing the date, and the two
merely crossing - because a rule that only settled the exact tie would leave
`15 March` and `2026 hit` both standing beside the date they sit in.

The principle behind it is **the pass with the closed vocabulary wins**. The date
pattern accepts a fixed list of calendar shapes and a four-digit run inside
1900-2100; the number pattern accepts any run of digits. Specificity is the one
property of two patterns that can be compared mechanically - which pass ran
first, which span is longer and which was written first are all accidents of how
the code is arranged. A third pass has to say where it sits in `KIND_PRECEDENCE`
or it does not ship.

**What the wrong answer costs, measured on the captured pages.** A year
kept as a quantity is a bar 2,027 units high standing next to a bar 12 units
high, and a reader cannot see that it is wrong - which is exactly why
`numeric_facts` drops a bare year before picking bars. On 2026-09-08 the rule
dropped eight quantities across the nine bounded fixtures and every one of them
was a year: `2029`, `2031`, `1994` and `2035` in `article.html`, `2027` three
times in `hostile.html` and the canaries. Two of the eight were worse than a
plain year - `2027 after` and `2027 only`, where the word following the year had
been read as its unit.

**The exception that was considered and refused: keep the quantity when it
carries a unit.** It is the obvious narrowing, and those same two elements are
why it fails. `after` and `only` are not in the 61-word stop list, so the
quantity pass gave them a unit and a unit-conditioned rule would have kept both
as measurements of 2,027. The unit reading is itself a guess; conditioning the
precedence rule on it stacks two guesses.

**What the rule costs, stated rather than implied.** A real four-digit count
written without a thousands separator loses to the year reading: "the survey
drew 1994 responses" yields a date and no quantity. Write it `1,994` and the
quantity survives, because the thousands separator takes it out of the
bare-year shape. The trade is deliberate and it is the same one `CLAUDE.md`
section 1a asks for everywhere else - a missing candidate degrades one chart,
and a wrong bar publishes a figure the article never stated. None of the nine
bounded fixtures hits this case; a test carries it so the cost is visible rather
than folklore.

**The rule lives in the producer, not in the shape.** `ElementTable` does not
refuse overlapping spans, and that is deliberate: a `quote` element carrying a
`quantity` inside it is the shape plan 11's model-anchored kinds need, and a
blanket no-overlap validator would refuse it and have to be reversed. What is
settled here is the narrower thing - two patterns over the same bytes never both
keep one span.

Authority: **Andre** (the trust boundary, and which reading of untrusted bytes
is the defensible one) on the precedence and on refusing the unit exception;
**Fowler** (persisted contracts) on keeping the rule out of the shape.

### One name for the verbatim slice, and it is `span_excerpt`

Three names were in play for one concept - `raw`, `surface` and `span_excerpt` -
and a later metric is defined on whichever one wins. One field survives.

`raw` was never a candidate once it was read. On `NumericFact` it is
`currency + sign + digits`, whitespace-cleaned: `"$4.5 billion"` in the article
becomes `"$4.5"` in the field. It drops the magnitude word and the unit, so it
is not a slice of anything and cannot prove where a figure came from.

`surface` is refused because this project already owns the word. Measured
2026-09-08 by `git grep`: 458 occurrences across 104 files in `docs/`,
`CLAUDE.md`, `backend/` and `frontend/src/`, every one of them meaning a place
something is shown or persisted - "the published surface", "a persisted
surface", `data-surface="operator"` on three console routes. `CLAUDE.md` section
11 names its subject "the persisted surfaces". Giving the most-used noun in the
repository a second meaning inside one contract is how a term stops carrying
information. One word per thing
([../contracts/schemas.md](../contracts/schemas.md)) rules the other way.

`span_excerpt` says what it is and binds to the two fields beside it by name. A
reader meeting `span_start`, `span_end` and `span_excerpt` can state the
invariant without being told it.

**The invariant is checked, not promised.** `len(span_excerpt)` must equal
`span_end - span_start`. That single comparison refuses a cleaned string
outright, which is what makes the ruling mechanical: substituting a `raw`-shaped
value shortens the string without moving the offsets, and the shape says no. A
contract test asserts it on `"$4.5 billion"`.

Authority: **Fowler** (persisted contracts, identifier discipline) on the name.

### Two fields with two jobs, rejected

The other coherent answer was a verbatim slice plus a normalised reading form.
It is refused on the trust argument rather than on bytes.

Tier 1 is defined as what code cut out of the bytes. Normalising is a judgement
- which words to fold, which magnitude to absorb, which article of speech to
drop - so a normalised string in Tier 1 would be the first Tier 1 field a model
could plausibly write, and the tier would stop meaning anything. Put it in
Tier 2 instead and it already exists there twice: `entity` is the canonical name
of a named thing, and `measure_canonical` is the canonical name of a measured
one. A third field would be a second wording of both.

For a quantity there is nothing left to hold either. `value` and `unit` are the
machine-readable reading, and a reading form assembled from them is derivable,
not stored.

What the second field would have cost, stated plainly: a metric five plans out
would be defined on one string and computed on the other by whoever wrote the
query, and nothing in the shape would catch it. That is the confusion the
naming decision exists to stop.

Authority: **Andre** (the trust boundary) on why the second field cannot be
Tier 1.

### The uncapped count is keyed by kind, and it is required

`elements.max_per_article` bounds what a pass keeps, so `len(elements)`
saturates and stops being a measure of the article. `candidates_found` is what
the pass matched before that bound applied, and the two together say whether the
cap bit and by how much.

**Required rather than defaulted.** A default of zero is indistinguishable from
a pass that genuinely found nothing, which is the same silent failure one level
down. Nothing had been persisted under the previous shape - row 1 shipped the
contract with no writer - so the only payloads that had to move were the two
committed fixtures, and they moved in the same commit.

**Keyed by kind rather than a single total.** The date extractor writes into
this same table next, and a total that mixes dates into quantities stops
answering the density question the moment it does. Summing a mapping is free;
splitting a total is not.

**Checked, not promised.** A cap only ever removes, so a table that kept more of
a kind than it says it found does not load, and neither does one that kept a
kind it counted nothing for. Without that, `candidates_found` would be a second
number nobody reads against anything.

Authority: **Andre** (2026-09-05) on the counter; **Fowler** (persisted
contracts) on required and on the key.

### The number pattern moved to the pass that is lower

`NUMBER`, the magnitude table, the percent set, the unit stop list and
`normalise_unit` were `visual_planner` privates. Two passes now read the same
vocabulary, and the fact pass is the lower of the two, so the definitions live
in `backend/idhazh/elements.py` and the planner imports them back. Nothing about
its behaviour changed: a duplicated regex would have been a second definition of
one concept, guaranteed to drift the first time the pattern is fixed.

`_TRIVIAL_MAX` and the context window stayed with the planner. They are its
judgements about what makes a bar, and the candidate pass does not share them.
The year range followed the pattern down in row 3, when a second pass needed the
same fact.

Authority: **Fowler** (module structure).

### The mention lists were named, and the tag control was not narrowed

Call 1 could not ask for a named thing until this was settled.
`test_no_prompt_asks_a_model_for_a_tag` refuses any prompt carrying the literal
words `lens`, `event type` or the plural of `entity`, and its stated reason is
that a page choosing its own reader-facing tags steers a control. The obvious
field name for a list of organisations trips that check on the third word.

Two honest routes existed. **Narrow the control** to the tag vocabulary it names,
so an extraction field is not caught by a bare word. **Or name the field for what
code takes from it**, if a name exists that a reader of the prompt would not
misread. The second was taken, for three reasons and one of them decided it.

The control is not ours to weaken. It is Andre's ruling and it protects the tag
vocabulary; a mention list does not touch that vocabulary at all, so nothing in
this row needs the ruling changed. **And the name is better, not merely
permitted.** Decision 1 of this row says the mention is Tier 1 and is what draws,
while the name is Tier 2 and a grouping key. A field called after the plural of
`entity` invites the reader to think the named thing is the payload;
`entity_mentions` says the mentions are. The third reason is that the check is a
substring match, so a chosen name is a stable answer and a narrowed control is a
new judgement call on every future prompt.

What that costs, stated rather than hidden: the control now passes on a prompt
that does ask about an organisation, so a later reader could take the silence as
approval it never gave. Two things answer that. This section is the record. And
`test_the_mention_lists_do_not_reach_the_tag_control` holds the same three words
out of the reply **schema** as well as the prompt, which is one surface more than
the original control reads - the schema is handed to the decoder in
`response_format`, so a class docstring is prompt text too.

Authority: **Andre** (the prompt and the schema at the injection boundary),
consulted by reading [`.github/agents/andre.agent.md`](../../../.github/agents/andre.agent.md).

### The four kinds needed no contract change

The row's own file list did not name `backend/idhazh/contracts/element.py`, and
after checking it did not need to. A **mention is an element**: its span is the
mention's own characters, and several mentions of one organisation are several
elements. The grouping key decision 1 calls the `name` is `Element.entity`, which
already exists, is already a slug, and is already filled by matching against the
watchlist rather than by minting. So `schemas/` did not move, no changelog entry
was owed, and no committed fixture had to gain a key in sorted order.

The one contract file that did move gained no field: `UNTRUSTED_LINE_MAX` is now
a named number beside the annotation that used it. A producer slicing a run of
sentences has to refuse a slice the shape will not hold, and the only other way
to find that out is to let the shape raise part-way through an article. It is the
same move `VALUE_MAX_LENGTH` and `UNIT_MAX_LENGTH` made one row earlier, and the
generated schema is byte-identical either way.

Authority: **Fowler** (persisted contracts), consulted by reading
[`.github/agents/fowler.agent.md`](../../../.github/agents/fowler.agent.md).

## Rejected alternatives

| Option | Why rejected | Authority |
| --- | --- | --- |
| Name the slice `surface` | The word already means "a place something is shown" in 458 sentences here, `data-surface` included. A second meaning inside one contract makes the word stop carrying information | Fowler |
| Name the slice `raw`, or reuse `NumericFact.raw` | It is whitespace-cleaned and drops the magnitude word and the unit, so it is not a slice and cannot prove provenance | Fowler, row 4 decision 2 |
| Two fields: the slice plus a normalised reading form | Normalising is a judgement, so it cannot be Tier 1 without breaking the tier; in Tier 2 it duplicates `entity` and `measure_canonical`; for a quantity it is derivable from `value` and `unit` | Andre |
| A per-element text hash | Redundant against the per-article hash plus the re-slice, and it is a hash per element on every article for ever | Fowler |
| One flat tier | Then nothing distinguishes a character range code cut from a word a model chose, which is the entire trust argument | Andre |
| Ship only the two kinds that have producers | Six kinds in one contract with one changelog entry is cheaper than four later widenings of a persisted shape | Fowler |
| Carry the element cap in the contract | A cap is a tunable and lives in `config/` (Rule #6). The shape says what an element is, never how many a producer keeps | Fowler |
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

The plan-doc's file list named `schemas/element.schema.json`. The shape it also
asked for - one `source_text_hash` per article, never per element - needs a
per-article container, so the contract is `ElementTable` and its stem mirrors
its class the way every other stem in this repository does. The plan's own prose
calls the thing "the element table" throughout, so the word was already chosen;
only the file list predates the shape.

### The year range moved to the pass that is lower

`YEAR_MIN` and `YEAR_MAX` were `visual_planner` privates. Two passes now need
the same fact about the same bytes - one to claim a bare four-digit run as a
year, the other to refuse it as a bar height - so the constants live in
`backend/idhazh/elements.py` and the planner imports them back. It is the same
move row 2 made for the number pattern, and for the same reason: two definitions
of one concept drift the first time either is fixed.

The planner keeps the judgement it makes with them, which is the half that is
not shared - a year is a label rather than a bar height, so it drops one. That
sentence moved from the constant to the line that acts on it. `_TRIVIAL_MAX` and
the context window stayed where they were; the candidate pass does not share
them.

Authority: **Fowler** (module structure).

### `extractor` is `model`, and the plan spells it `model_proposed`

The plan that specified call 1 asks for a proposed figure to be stamped
`extractor="model_proposed"`. The contract already carried the member and calls
it `model`, with the docstring "a model proposed the location and code cut the
characters at it" - the same property under a shorter word. It stayed as it is,
and the reason is the rows still to come: `entity`, `place`, `quote` and `claim`
are model-pointed the same way and none of them is a proposal, so a field spelled
`model_proposed` would be wrong on four of the five paths that will write it. The
field names **who found it**, not what shape was asked for.

Cost, stated rather than implied: a reader holding the plan-doc and the payload
side by side sees two words for one thing until they reach this paragraph. The
alternative cost was a persisted enum value that four later producers would have
to contradict.

### Call 1 is built and nothing dispatches it

The request, the reply shape, the parser and every anchoring path ship here; no
stage calls them. That is deliberate rather than unfinished. Call 1 alone
produces a labelled table and no page: the call that turns it into a summary and
a visual is the next row, and it appends to **this** call's message array, so the
article prefills once. Wiring call 1 in on its own would spend a model call per
item for an answer nothing reads yet, and it would do it inside a job with a
50-minute bound.

So there is no flag to flip and no dead config knob: production behaviour is
byte-identical, and the row that adds the second call is the row that turns both
on together.

## See also

- [../contracts/schemas.md](../contracts/schemas.md) - the contract subsystem: the base model, the generated schemas, and the drift gate over both.
- [../publishing/visuals.md](../publishing/visuals.md) - the visual planner, which reads the same number pattern and keeps its own drops.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - what a read over a growing collection has to declare.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #3 (contracts before logic), Rule #6 (no hardcoding), Rule #11 (fetched text is data), section 11 (schema versioning).
- [../../../TODO/20260905-08-element-table-plan.md](../../../TODO/20260905-08-element-table-plan.md) - the plan this shape was written for, and the producers that follow it.
- [../../../TODO/20260905-11-two-call-planner-plan.md](../../../TODO/20260905-11-two-call-planner-plan.md) - the plan call 1 belongs to, and the call that reads its table next.
