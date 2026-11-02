# Measuring article substance

**Last Updated**: 2026-11-02

How does screening measure article shape without changing the source text?
It measures retained paragraphs once and caches `substance_word_count` and
the signed `substance_score` for each admitted article. The selector adds this
cached score to authority, recency and the technical pass adjustment once in
the [base calculation](feed-curation.md#fixed-score-preparation). Selection
does not analyze article text.

## Paragraph evidence and separate counts

The parser writes `word_count` for the complete sanitized article body.
Screening leaves that count, the body, extraction evidence and worker work
estimate unchanged. The raw technical word minimum still decides admission;
there is no retained-word minimum.

After the existing cheap gates, split sanitized `article_text` on one or more
newlines, trim each block and ignore empty blocks. For each nonempty block,
use the shared Unicode-whitespace word counter once and compromise once.
Retain the block when it has at least 25 words OR at least two library
sentences. Both thresholds are configurable and inclusive.

Sum cached word and sentence counts only for retained blocks. On their local
library documents, count non-overlapping `match('#ProperNoun+')` name spans
and `numbers().not('#ProperNoun')` quantity spans. One-word names count;
multiword spans count once. The string exclusion prevents proper-noun terms
from earning numerical credit too. No separate name or sentence parser is used.
Every block is analyzed, including blocks after full length credit is reached.

Build the opening from retained blocks in source order, separated by two
newlines. Stop copying at the configured Unicode-character limit, 2,000 by
default; do not stop the remaining measurement. Only the measured retained
count, sentence/name/number counts and bounded opening leave the helper.
Library documents never cross that boundary. There is no joined full-body
analysis, raw-text fallback or downstream recount.

A newline block is not a semantic paragraph guarantee. Long disclaimers and
short two-sentence footers can survive. Short one-sentence prose and
soft-wrapped lines can be discarded. Abbreviations, names and quantities
follow the pinned library's English heuristics; removal rates are unmeasured.

## Soft length and density points

All settings below come from `curate_articles.substance` in
`config/feed-ingest-plan.json`. Length uses only the measured retained count.

Table A

| Id | Retained words | Default length points |
| --- | --- | --- |
| A1 | Zero through 749 | Linear from zero at zero words toward 1.0 at 750 words |
| A2 | 750 through 3,500, inclusive | 1.0 |
| A3 | Above 3,500 through 6,000 | Continuous linear taper from 1.0 to 0.80 |
| A4 | Above 6,000 | Constant 0.80 |

The configured ramp end, full-credit end, taper end, full score and floor
control the same continuous curve. There is no short-article refusal or
lower-word offset. For example, 150 retained words earn 0.20 length points;
4,750 earn 0.90. Discarded padding cannot move either value.

Density is retained name spans plus retained quantity spans divided by
retained sentence units; zero units gives zero density. Divide that density
by the configured full-credit density, clamp to zero through one, and multiply
by the density weight. Defaults give at most 0.30 points, reaching full credit
at one signal per sentence. Two signals across four sentences earn 0.15 points.
This is lexical evidence, not factual verification.

## Headline deductions

Preserve original headline case for shouting. Read public `doc.json()` as
unknown and validate each consumed term's text, normal form, tags and optional
root with local Zod. A root can be a string, null or absent, as returned by the
public library output. Ignore unused metadata; do not inspect library internals.

Shouting counts headline terms with at least two Unicode letters by default.
An uppercase term must equal its uppercase form and differ from its lowercase
form. Only library-recognized `acronyms()` terms, identified by the public
`Acronym` tag, leave the uppercase numerator. Acronyms and grammar words stay
in the denominator. The flag requires at least two unexempt uppercase terms
and an inclusive half-headline ratio. `BIG NEWS calm words` flags;
`BIG NEWS calm words today` does not. No short-word exemption or acronym
allowlist is used.

Punctuation flags once if any configured Unicode pattern matches. Defaults
match repeated exclamation marks and mixed question/exclamation marks.
Patterns are prepared once per screening invocation, not per article.

For opening overlap, lowercase separate headline and bounded-opening documents,
then run public `compute('root')` without rewriting sentences. Use a validated
word root only for terms tagged `Verb` or both `Noun` and `Plural`. Otherwise,
or when the root is null or absent, keep the term's normal form. Adjectives,
adverbs and singular nouns keep their normal forms. Compare whole words, not
display text. Keep distinct headline keywords with at least four Unicode
letters after configured grammar-word exclusions. A mismatch needs nonempty
keyword and opening sets with no whole-term intersection. Missing opening
evidence cannot prove mismatch. Ordinary inflections can match; substrings,
synonyms and arbitrary derivational pairs are not treated as equivalent.

Default deductions are 0.10 points for shouting, 0.10 for punctuation and
0.05 for opening mismatch. Clamp their sum to the configured 0.25-point
maximum. Substance equals length plus density minus that nonnegative
deduction. It is signed, not a probability: full length and density with all
three flags gives 1.05 points. Parsing and configuration failures are explicit,
not zero-score fallbacks.

## Empty and unknown evidence

A technically admitted article can retain zero words. It stays admitted with
measured zero count, zero length/density and no opening mismatch. Observed
shouting and punctuation still deduct points. Missing or null required cache
fields fail native validation; they are never filled with zero. The native
screened-candidate schema also enforces retained count <= raw count.

Unknown age remains null, with timing source unknown and zero recency. It does
not prevent substance measurement or add a technical refusal. Only known
age is checked against the effective global ceiling; technical pass/refusal
denominators are independent of age and selection.

## Design rationale

Substance is measured during screening and reused as a fixed ranking input.
Admission and shape scoring remain separate. Separate counts prevent
navigation padding from buying length or
density credit while preserving the original body for later processing.
The scorer's preferences do not establish factual quality or complete
boilerplate removal.

compromise 14.19.0 supplies sentence, proper-name, quantity and inflection
analysis. It adds service-side JavaScript and two direct dependencies, efrt
and suffix-thumb. It adds no native build, model download or browser payload.
No timing or installed-byte guarantee is claimed.

Opening overlap needs word base forms, not rewritten sentences. Whole-sentence
verb conversion can fail on ordinary questions in headlines or retained prose.
Public word roots avoid that conversion. The noun and verb tag checks prevent
adjective and adverb roots from widening the comparison.

## See also

- [Screening](feed-screening.md)
- [Extraction measurement](extraction-quality.md)
- [Policy settings](feed-ingest-policies.md)
- [Native checks](../../how-to/run-the-gates.md#independent-typescript-packages-and-services)
