# Elements: every fact in an article, with the characters that prove it

**Last Updated**: 2026-09-08

The extraction subsystem's fact table. This page owns the element shape - the
six kinds, the two tiers, and the span that makes a drawn figure checkable.

Nothing writes this table yet. The contract lands ahead of its producers because
a persisted shape is a Pydantic model before any logic reads or writes it
(`CLAUDE.md` Rule #3), and because two producers, an invariant and a metric are
all written against it in the rows that follow.

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

`ElementTable` holds one article's elements, the article's identity, and the
sha256 of the exact string the spans index.

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

Six kinds ship in one changelog entry and two of them have producers. A kind
with no producer is legal and simply never appears, which is cheaper than
widening a persisted shape four more times.

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

### Why the schema stem is `element-table`

The plan-doc's file list named `schemas/element.schema.json`. The shape it also
asked for - one `source_text_hash` per article, never per element - needs a
per-article container, so the contract is `ElementTable` and its stem mirrors
its class the way every other stem in this repository does. The plan's own prose
calls the thing "the element table" throughout, so the word was already chosen;
only the file list predates the shape.

## See also

- [../contracts/schemas.md](../contracts/schemas.md) - the contract subsystem: the base model, the generated schemas, and the drift gate over both.
- [../../concepts/growing-reads.md](../../concepts/growing-reads.md) - what a read over a growing collection has to declare.
- [../../../CLAUDE.md](../../../CLAUDE.md) - Rule #3 (contracts before logic), Rule #6 (no hardcoding), Rule #11 (fetched text is data), section 11 (schema versioning).
- [../../../TODO/20260905-08-element-table-plan.md](../../../TODO/20260905-08-element-table-plan.md) - the plan this shape was written for, and the producers that follow it.
