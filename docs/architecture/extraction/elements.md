# Elements: every fact in an article, with the characters that prove it

**Last Updated**: 2026-09-08

The extraction subsystem's fact table. This page owns the element shape - the
six kinds, the two tiers, and the span that makes a drawn figure checkable - and
the candidate pass that fills it with quantities.

One pass writes into this table today. It finds quantities, and it is pure code
over the article's own bytes: `backend/idhazh/elements.py`. The four kinds a
model has to point at have no producer, and a kind with no producer is legal and
simply never appears.

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
returns a plausible integer. The count is taken before any dedupe and before the
cap, and the shape refuses a table that kept more of a kind than it says it
found.

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

Six kinds ship in one changelog entry and one of them has a producer today. A
kind with no producer is legal and simply never appears, which is cheaper than
widening a persisted shape four more times.

## The candidate pass

`quantity_elements(text, limit=...)` reads `Article.text` with the number
pattern and emits one element per quantity, in the order the article wrote them.
`element_table(article, config=...)` wraps that in the table, with the article's
identity and the hash of the text every span indexes. Both are pure functions
over one payload: nothing is committed, and the pass is proved by re-slicing its
own output.

**The offsets are not new work.** `visual_planner.numeric_facts` has always
computed `match.start()` and `match.end()`, and has always thrown them away.
This pass keeps them and cuts `span_excerpt` at them.

**What the pass keeps that the planner drops.** `numeric_facts` picks a few bars
for one chart, so it collapses a figure repeated across two periods into one
fact, drops a magnitude at or below two, drops a bare year, and stops at 16.
Every one of those is correct for choosing bars and wrong for a candidate set -
the collapsed repeat is exactly the series a trend chart exists to show. Nothing
in the candidate pass dedupes and nothing drops on size. Measured 2026-09-08 on
the eight bounded fixtures (`tests/fixtures/canaries` and
`tests/fixtures/pages`), the pass emits 17 quantities where `numeric_facts`
keeps 11; on `tests/fixtures/pages/article.html` alone it is 7 against 3.

`numeric_facts` is untouched and still behaves that way for the planner that
calls it. This row added a producer beside it rather than repairing it in place.

**The span ends where the reading ends.** A trailing word is inside the span
only when it was read as the unit, so `1,200 MW` and `$4.5 billion` are
excerpts and `40 percent of` never is. That is what keeps the excerpt something
a reader can find on the page rather than a phrase the pattern happened to
touch.

**A bare year is a quantity here, for now.** The date extractor and the rule
that settles two extractors competing for one span land in the next row, which
is where the overlap rule has a home. Until then the pass emits every quantity
the number pattern matched, which is what "candidate" means.

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

`_TRIVIAL_MAX`, the year range and the context window stayed with the planner.
They are its judgements about what makes a bar, and the candidate pass does not
share them.

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
| Duplicate the number pattern in the new pass | Two definitions of one concept, and the first fix to either would land in one of them | Fowler |
| Raise on a 200-digit run or a 600-character unit word | Degrade, do not fail (`CLAUDE.md` section 1a). A pattern over fetched bytes will meet both, and one hostile page must not take an article's whole table down | Andre |

### Why the schema stem is `element-table`

The plan-doc's file list named `schemas/element.schema.json`. The shape it also
asked for - one `source_text_hash` per article, never per element - needs a
per-article container, so the contract is `ElementTable` and its stem mirrors
its class the way every other stem in this repository does. The plan's own prose
calls the thing "the element table" throughout, so the word was already chosen;
only the file list predates the shape.

## See also

- [../contracts/schemas.md](../contracts/schemas.md) - the contract subsystem: the base model, the generated schemas, and the drift gate over both.
- [../publishing/visuals.md](../publishing/visuals.md) - the visual planner, which reads the same number pattern and keeps its own drops.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - what a read over a growing collection has to declare.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #3 (contracts before logic), Rule #6 (no hardcoding), Rule #11 (fetched text is data), section 11 (schema versioning).
- [../../../TODO/20260905-08-element-table-plan.md](../../../TODO/20260905-08-element-table-plan.md) - the plan this shape was written for, and the producers that follow it.
