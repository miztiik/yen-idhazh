# The Summarizer Prompt

**Last Updated**: 2026-11-26

What the model reads and writes, and what the pipeline validates. Prompt
wording is not a security control: sanitization and validated output shapes
enforce the boundary.

## The prompt is a template, not a text

Templates under `config/prompts/` may take their quotation limit from
configuration. Use strict substitution so a missing or renamed value fails
rather than reaching the model as an unresolved placeholder.

`config/idhazh.json.prompt_files` selects each production task's file, relative
to the selected config root (`CONFIG_ROOT` in a candidate action). Validate the
relative POSIX path when config loads: it must name a `.txt` file under
`prompts/`, without an absolute path, URL, backslash or parent traversal.
Read only the task being rendered. Missing, blank or invalid UTF-8 text fails
by its configured name; templates are not globally cached across roots.
Config/model description validates paths without requiring unrelated text files.

Table A - Production instruction files

| Id | `prompt_files` key | Path relative to the selected config root |
| --- | --- | --- |
| A1 | `write_digest_summary` | `prompts/write-digest-summary.txt` |
| A2 | `plan_visual` | `prompts/plan-visual.txt` |
| A3 | `summarize_article` | `prompts/generate-summary.txt` |
| A4 | `compare_articles` | `prompts/compare-articles.txt` |

Production rendering retains universal-newline reading and performs no
whitespace trimming. The app config's additive reader uses the declared task paths if an older
authored input omits `prompt_files`; new authored configuration names them all. A config that
still names `generate_labels`, the retired first call's file, is refused by name: no task reads
such a file, so a path left in `prompt_files` would be one somebody believes.
The standalone summary, corpus and reference-set readers use A3, shared with the
[summary generator's default](../../reference/summary-generator-api.md).
It emits `title` and `summary`, and its instructions are identical for every
article. Configured templates may still use the validated substitution values.
Reference sampling spreads articles by source length, as the
[reference-set procedure](../../how-to/fine-tune-a-model.md#the-reference-set)
describes.
The digest reads A1 and adds A2 only when asking for a chart.
The comparison judge and its stamp use A4's full rendered instructions.
Offline judge capture and saved-evidence validation use that same selected file,
so their recorded identity cannot describe instructions from another root.

The [summary generator](../../reference/summary-generator-api.md) and
[comparison workflow](../../reference/summary-evaluation-workflow.md) select
different tasks in the same directory. Neither replaces the digest's call
with fresh independent calls. [Native UniEval](../../reference/unieval-api.md)
resolves its own question files before scoring; source coverage keeps its pinned
upstream question construction.

Keep editorial wording shared across models. Model-specific turn markers and template behavior belong with the model entry, not in a second instruction set. [Model boundary](model-boundary.md) owns compatibility checks.

## A reply is published as the model wrote it

No length decides whether a reply publishes, and nothing shortens one. The prompt asks for no fixed word or sentence limits either; instead it asks for length proportional to the article's information density (one short paragraph for a brief update, multiple short paragraphs for a dense or multi-part report, with no padding). A reply that holds its shape - a non-empty `title` and a non-empty `paragraphs` array of non-empty strings - is joined on blank lines and published word for word, however long or short. Its words meet one check, the [address rule](#the-shape-is-not-the-whole-check); its whitespace is tidied as [the next section](#paragraphs-follow-the-models-prose) says. A summary that is empty once that tidying is done fails the item as `bad_shape`.

The decoder's grammar bounds neither field above, so a long reply is neither cut off mid-field nor refused. Only the call's response limit ([below](#the-output-budget)) ends one early. There is no automatic retry.

Do not add a cut, a floor or a character limit to a reply. A sentence splitter cannot find a safe cut, because abbreviations, decimals and percentages contain periods, and a reader can see that a summary is long or short but cannot see that part of it was deleted.

## Paragraphs follow the model's prose

There is no paragraph-count cap or word threshold for a paragraph break.
The transient draft model (`SummaryDraft`) decodes `paragraphs: list[str]`
(at least one non-empty item, `extra="forbid"`), and `parse_draft` joins those
entries with one blank line (`\n\n`) and runs `normalize_prose()` so the
persisted `Summary.summary` contract and the frontend remain unchanged.
Prose normalization rejoins a lone newline inside an element, collapses
repeated blank lines, drops whitespace-only entries, and replaces other
control characters with spaces. Recorded drafts written under the earlier
single-string `summary` key remain readable on the read side when `paragraphs`
is absent.

Preserve every nonempty paragraph.

The digest prompt (`config/prompts/write-digest-summary.txt`) asks for a
one-sentence lead stating the central finding followed by tight paragraphs of
evidence, caveats, and substantive responses in plain, direct sentences,
dropping chronological play-by-play. It forbids straight double quotes (`"`)
inside `title` and `paragraphs` (paraphrase speech; use single quotes `'...'`
when a short term must be quoted) so constrained JSON decoding does not close
a string mid-sentence.

If extraction read only part of the article, state that limitation on the item. Asking for fewer summary words does not tell the reader that part of the source was missing.

## The decoder holds the shape, the prompt does not

Use grammar-constrained decoding derived from the declared reply model. Refuse unknown keys and validate the result after decoding. A well-shaped object still needs content checks.

The chart grammar allows `visual: null` or a proposal for an enabled form
the compiler supports. Each type has its own row shape. Every label-bearing
row shape decodes its reading ID field(s) (`reading`, `start`/`end`, or
`x`/`y`/`size`) before `label` (and optional `series`) so the decoder locks
onto the selected evidence line before writing the model label. A reading
references one finite quantity occurrence ID (`ev<n>`) and chooses `as_stated`
or `negative_magnitude`. Time roles reference a separate finite set of date
IDs (`dt<n>`). No source strings enter schema literals. A summary-only request
has neither chart instructions nor `visual` or `model_reason` fields in its
grammar.

## One call writes the summary and plans the visual

[classify/calls.py](../../../backend/idhazh/classify/calls.py) builds the one request
each item makes, and [stages/summarize_one_item.py](../../../backend/idhazh/stages/summarize_one_item.py)
sends it:

- **The system turn** is `write-digest-summary.txt`, unchanged, with a short
  `plan-visual.txt` addendum for a chart-capable request. The addendum forbids
  evidence IDs or parenthetical citations inside `title` and `paragraphs`, and
  names the exact same forms as the reply schema.
- **The user turn** is one sanitized, fenced block containing the headline and
  article body, unchanged and without markers. A chart-capable request adds
  separate fenced one-line local snippets with non-prose `ev` quantity IDs and
  `dt` date IDs, bracketing each reading inside its local context. Only those
  bounded snippets repeat source words; no instruction follows them.

The prompt is rendered explicitly rather than by the model's chat template. The shared
system text is a reusable prefix for items with the same request shape.

The [text-analysis service](../text-analysis/text-analysis-api.md) still finds
mentions and sentence offsets in that same analysis request, and can rule out a
matched number that is not a measurement. Each span is checked independently
against the sanitized article. Valid mentions survive unusable sentences. It does
not have to find category names for a chart to be considered.

### The model proposes rows; code binds the supplied readings

The reply is `summary`, then `visual`, then optional `model_reason`. The model chooses the chart type
and the title, axis titles, category labels and series names. The native
schema describes the rows, decodes reading IDs before `label`, and offers
disjoint finite `ev` quantity IDs and `dt` date IDs.
The source carries units. Bar, dot and slope proposals also name the shared
comparison basis in a short phrase (3-8 words so it stays well within the
80-character field ceiling). Single-series charts set `series: null`; `series`
is reserved for distinguishing two or more series. Each row's `label` matches
the words beside its chosen ID, and listed breakdowns include every item or
return `visual: null`. The model decides relevance, direction,
scope and suitability; code does not infer those from the article or summary.

[Chart preparation](../publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md#a-chart-answer-becomes-a-plan-in-code)
binds an ID to the exact source occurrence and keeps display wording separate. It
does not decide what a sentence means. A null proposal records a decline.
The addendum asks for a reason for either choice: one plain-text line, at
most 20 whitespace-separated words and within the untrusted-line character
limit. Code drops a missing, invalid or unsafe reason independently of the
summary and visual. The reason is untrusted text, not evidence or a validator
verdict; only the visual decision handoff and
[attempt ledger](../contracts/ledger-registry.md#visual-design-attempts) carry it.
Replaying a known reply checks parsing and compilation; the
[retained workflow](../../reference/retained-article-verification.md) shows
what a live model selected.

### Every instruction sits in front of the article

Put shared instructions in the system turn. The user turn is source data,
not a second instruction or a copy of the reply schema.

Fenced headline and article text remain untrusted data. Do not let either become a system instruction, shell argument, filename or fetch destination. Scope an instruction to the job it governs: a plan rule against inventing numbers must not forbid the summary from reporting a source figure.

### Evidence stays separate from the article

The prompt contains the sanitized article and, where applicable, the
evidence block. It does not change stored `Article.text`. Request-only `ev`
and `dt` IDs locate quantity and date occurrences as one-line local snippets
inside complete verified sentences (up to five surrounding words on each side,
trimmed with `...` inside the sentence and isolated to the reading's line when
a sentence spans bullet lines, with the reading itself bracketed and no
character offsets). Published output retains original canonical element
references (`quantity-start-end`, `date-start-end`), never these transient IDs
or snippets. The [evidence bounds](../../concepts/config/run-limits.md) limit
the entire rendered block. Sentences are deduplicated and selected in source
order; a sentence whose readings cannot fit is omitted whole, never partially
dropped. Surrounding separator whitespace on each verified sentence is trimmed
before slicing so snippets never bleed across sentence boundaries.
Fewer than two offered quantities, unusable sentence spans or a combined
request that cannot fit select the existing plain summary path. Line and
slope are omitted from both instructions and grammar unless the offered
dates include two distinct canonical values at a common precision. Only
date IDs in such a precision group enter time roles. Slope also requires
four offered quantities for its two paired rows. These checks establish
reachable roles, not whether the story deserves that chart.

Preparation re-slices the selected readings from the original element
table over `Article.text`.
A mention whose offsets do not cut those words is dropped. The
[element contract](../extraction/elements.md#the-two-kinds-only-a-labeller-can-find)
owns those meanings and the anchoring rules.

### What is in the prompt bytes, and who wrote each part

The active model entry declares its turn opening, closing, reply openings, system-turn placement and any thinking marker. Preserve required whitespace. Validate the declaration against the model identity and the runtime's own template before processing items.

- Require the role placeholder where a marker opens a role-bearing turn.
- Reject empty structural markers and incompatible system-role/joiner declarations.
- Confirm the sanitizer strips every declared marker an article could forge.
- Prove both byte-prefix and token-prefix continuity with the configured tokenizer.

The native completion request carries `json_schema` explicitly and declares
`cache_prompt`. Do not assume a compatibility route honors a field merely
because it accepts the request. Tests cover request contracts, source isolation,
template substitution and reusable-prefix continuity, not production instruction
wording or full-prompt snapshots. Live startup checks prove compatibility with
the current server and model; neither establishes semantic extraction quality.

### Summary before visual

Decode the summary before the answer about a chart. If output ends during the answer, `recovered_completion` may recover a complete summary with the JSON decoder, normalize the repaired completion status, and pass it through the same content checks as a normal reply. If the budget runs out after the top-level visual proposal or decline closes, keep it only if it passes the normal checks. A cut reason is null; a complete valid reply keeps its reason even if its last token used the budget. Publish no picture when its answer is incomplete.

Never recover a partially written summary. A chart is built only from readings and
labels code resolves against the article, never from a figure in the summary.

### The output budget

The call has nothing to derive a budget from. Its two prose fields carry no length
bound, so it runs under the model file's `sampling.max_tokens`, or
`DEFAULT_MAX_TOKENS` where the file names none, with chart data or without; see
[model-file.md](../../concepts/config/model-file.md#design-rationale). Do not silently clamp a reply
budget to available context. Report a window failure at the call site.

For capacity diagnostics, tokenize the complete rendered request with the
configured model's vocabulary, then add the effective response limit from that
request body. The complete input already contains the system turn and the
source block. Cached tokens still occupy context; do not omit them.

The pre-call gate remains an estimate, not a certificate for every request: a measured
scaffold and word rate, the UTF-8 bytes of the chart addendum, and the call's
response limit. It sizes the summary-only call first; when only that shape
fits, it leaves the chart question off. [Throughput](throughput.md#the-window-is-checked-before-the-call-is-sent)
owns the arithmetic and its figures.
Conservative byte ceilings are not observed token counts. A bounded check with
retained production replies and a constructed source-cap input measures those
requests only; a repeated long source and its historical reply do not establish
universal fit or present-day planning quality. Capacity diagnostics do not
change admission, suppress a visual, reduce a response cap or replace existing
summary-first recovery.

A reply the output budget cuts inside the summary fails as `output_truncated`; one cut
inside the answer about a chart keeps its summary, as [above](#summary-before-visual). A retry needs a deliberate input change and a configured attempt policy; repeating an identical deterministic request is not recovery.

## The shape is not the whole check

After parsing, `to_summary` enforces publishability.

- Reject a summary containing an address or the sanitizer's link marker with `leaked_address`. Reuse the sanitizer's definition instead of adding another URL pattern.
- If the generated title is blank, leaks an address or is longer than the payload's title field holds, discard that title and use the established fallback; do not discard a valid summary for a title failure. Publish any other title as written, whatever its length.
- Record a typed failure and its observed values in item health. Do not infer outcomes later by scraping logs.

## Two spans on one call

Reasoning is declared by the model's closing marker. On the explicit-completion
path, a reasoning span runs without the output grammar until that marker, the
context limit or timeout, or the configured `max_tokens` limit when present.
The answer span continues the same prompt with the grammar restored and its own
reply budget, also replaced by an explicit `max_tokens` when present.

Discard reasoning before the reply reaches a persisted payload, reader surface or later article-level continuation. With no declared marker, reject unexpected reasoning. Check both inline thinking blocks and a separate reasoning channel, and inspect every inline block rather than only the first.

The chat-template path lets the runtime manage its reasoning split. It must still satisfy the same no-leakage check. Assess published summaries with the [evaluation policy](../../concepts/evaluation.md); a protocol change does not establish a quality gain.

## Model compatibility is mechanical

Derive template keyword names and turn structure from the model declaration. Do not rely on an instruction inserted into article text to change reasoning mode.

Re-tokenize the complete rendered requests for a candidate model. Recorded incumbent fixtures prove parser behavior, not another model's template, context fit or live responses.

## What the prompt asks for, section by section

| Section | Required content |
| --- | --- |
| Framing | Make clear how the article knows what it reports |
| Title | A new factual title drawn from the body, with a source headline when available |
| Source form | Attribute an abstract's claims to its authors |
| Attribution | Name who made a claim; distinguish self-reported figures |
| Certainty | Preserve the difference between proposal, forecast, claim and result |
| Faithfulness | Preserve source facts, names and figures without invention |
| Quoting | Paraphrase speech; forbid straight double quotes inside JSON fields and use single quotes for short quoted terms |
| Voice | Plain, neutral third-person reporting in direct, one-idea sentences |

## The title is ours, and the source's is only a fallback

Ask for actor and action without hype, withheld facts or a question addressed to the reader. Fence the source headline like the body. Require a title in the decoded draft so the model attempts it. Publish the model's headline as it wrote it, with extra spaces collapsed; no word range applies to it. Fall back to the source headline, and then `Untitled item`, only when the model's is blank, carries an address or is longer than the payload's title field holds (500 characters).

An absent source headline does not block summarization. The article keeps that
absence; the generated title belongs to the summary, not to the source.

The evaluation record identifies the article with its source headline, not a generated title that can change between runs.

## The record covers the ask

`RunRecord.inputs.prompt_sha256` covers both variants of the rendered digest
call with fixed inputs: templates, substituted policy, turn markers and order,
and the data framing and capabilities. `output_schema_sha256` fingerprints the
reply shapes, which are independent of any article. The exact
article-specific request and reply remain in the native capture.

Changing prompt wording or policy changes this identity. The digest makes the change observable; it is not permission to skip work or a quality verdict.

## The changes are not retroactive

Prompt changes affect new work, not frozen published days. Do not rebuild the archive as an incidental part of a prompt edit. An evaluation harness must exercise the same request construction and transport as the production path it claims to assess.

## Design rationale

Read the article once. The first of the two calls the pipeline used to make only labelled what
code could already find: on 66 captured articles it took 3.67 of 7.04 hours of model time
(52 percent) and fed a chart planner that published no chart, while the local text-analysis
service returns the same names and places with exact offsets in seconds. Dropping the call
saves its decode because the remaining call reads the article either way.

**Why give readings without annotating the article.** Chart-specific marks
can leak into the summary. The separate list restricts which readings can
be drawn without inserting marks into the article. Matching a source amount
does not prove it belongs to the model's label or comparison. The model
chooses the meaning; code checks the readings and the drawing rules.

The service is a new recipient of article text, so it is a loopback process the run starts
and its reply is data ([trust boundary](../sources/trust-boundary.md)).
No word the service returns becomes a prompt, path, URL or shell argument.

Element ids, parsed values, character offsets and extractor bookkeeping
stay out of the evidence projection. Source hashes and re-slicing checks
keep each reading tied to the article.

A stable prefix reduces repeated reading without treating prompt wording as a control. Summary-first decoding protects the reader's primary content when visual planning cannot finish. Model-specific transport declarations keep shared editorial instructions testable across models.

Task paths belong to the selected configuration so a candidate never reads
instructions from the original checkout. One directory holds distinct products
and call flows, not one shared summary instruction or a scanned prompt registry.

The exact evidence spans stay in the backend. These invariants prove the
transport and refusal rules, not the model's live chart selection rate.

**Why decode `paragraphs: list[str]` and forbid straight double quotes in the digest prompt.**
Under constrained JSON decoding, an unescaped straight double quote inside a
single `summary` string closes the JSON string early and truncates the item
mid-sentence (measured 42 of 400 items on 2026-11-26), while single-string
decoding also encourages walls of text. Moving paragraph breaks into the
transient `SummaryDraft.paragraphs` array and instructing the model to
paraphrase or use single quotes fixes both failure modes at the decode boundary
while keeping `Summary.summary`, persisted digests, and the frontend unchanged.

**Why non-prose `ev`/`dt` IDs, one-line local snippets, and `reading`-before-`label` decode order.**
Prose-like `q`/`d` IDs combined with the verb "Cite" caused models to leak
markers such as `(q1)` into published summaries. Full repeated `Passage:`
blocks with `[start:end]` character offsets forced the model to cross-index
dense lists across separate paragraphs, causing row/label slips when a chart
label decoded before its reading ID. Replacing passages and offsets with
one-line local snippets (`ev5: - Firebaugh, CA: +[10 stalls]`), renaming
transient IDs to `ev`/`dt`, forbidding evidence IDs in summary prose, and
decoding reading IDs before `label` keeps transient planning aligned with the
chosen occurrence while leaving persisted `VisualPlan` and `VisualData`
contracts unchanged.

## See also

- [model-boundary.md](model-boundary.md) - model and runtime compatibility.
- [throughput.md](throughput.md) - request scheduling and rates.
- [../sources/trust-boundary.md](../sources/trust-boundary.md) - untrusted input controls.
- [../../concepts/config/summary-length.md](../../concepts/config/summary-length.md) - what gets summarized, and why no length is asked.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - budget measurements.
