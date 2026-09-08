# Elements: every fact in an article, with the characters that prove it

**Last Updated**: 2026-09-08

The extraction subsystem's fact table. This page owns the element shape - the
six kinds, the two tiers, and the span that makes a drawn figure checkable - the
candidate pass that fills it, and the rule that settles two passes claiming one
stretch of characters.

Two passes write into this table today, both pure code over the article's own
bytes: [`backend/idhazh/elements.py`](../../../backend/idhazh/elements.py) finds
quantities and it finds absolute dates. The four kinds a model has to point at
have no producer, and a kind with no producer is legal and simply never appears.

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
element on every article for ever.

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

Six kinds ship in one changelog entry and two of them have a producer today. A
kind with no producer is legal and simply never appears, which is cheaper than
widening a persisted shape four more times.

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
computed `match.start()` and `match.end()`, and has always thrown them away.
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
archive (Rule #12). Measured 2026-09-08 on a 12th Gen Intel Core i7-1265U with
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

## `context` is gone, and this is the sentence saying so

`visual_planner.NumericFact` carries `context`: a whitespace-cleaned window of
the words around a number, about 50 characters back and 30 forward, snapped to
word boundaries. This shape does not have it.

A derived string is replaced by a pointer. `sentence_index` plus the span says
where the words are, and `Article.text` still holds them, so nothing stores a
second copy of the reader's sentence. `NumericFact.context` is untouched by this
contract and retires when its own producer does.

## Design rationale

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

## See also

- [../contracts/schemas.md](../contracts/schemas.md) - the contract subsystem: the base model, the generated schemas, and the drift gate over both.
- [../publishing/visuals.md](../publishing/visuals.md) - the visual planner, which reads the same number pattern and keeps its own drops.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - what a read over a growing collection has to declare.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #3 (contracts before logic), Rule #6 (no hardcoding), Rule #11 (fetched text is data), section 11 (schema versioning).
- [../../../TODO/20260905-08-element-table-plan.md](../../../TODO/20260905-08-element-table-plan.md) - the plan this shape was written for, and the producers that follow it.
