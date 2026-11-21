# The Summarizer Prompt

**Last Updated**: 2026-11-18

What the model is asked to produce, what it reads beside the article, and what the pipeline validates. Prompt wording is not a security control: sanitization and validated output shapes enforce the boundary.

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
| A3 | `continue_summary` | `prompts/continue-summary.txt` |
| A4 | `summarize_article` | `prompts/generate-summary.txt` |
| A5 | `compare_articles` | `prompts/compare-articles.txt` |

Production rendering retains universal-newline reading and performs no
whitespace trimming. The app config's additive reader uses the declared task paths if an older
authored input omits `prompt_files`; new authored configuration names them all. A config that
still names `generate_labels`, the retired first call's file, is refused by name: no task reads
such a file, so a path left in `prompt_files` would be one somebody believes.
The standalone summary, corpus and reference-set readers use A4, shared with the
[summary generator's default](../../reference/summary-generator-api.md).
It emits `title` and `summary`, and its instructions are identical for every
article. Configured templates may still use the validated substitution values.
Reference sampling spreads articles by source length, as the
[reference-set procedure](../../how-to/fine-tune-a-model.md#the-reference-set)
describes.
The digest retains its separate A1, A2 and A3 instructions, and its one call reads
those three.
The comparison judge and its stamp use A5's full rendered instructions.
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

No length decides whether a reply publishes, and nothing shortens one. The prompt asks for no length either. A reply that holds its shape - a `title` and a `summary`, neither empty - is published word for word, however long or short. Its words meet one check, the [address rule](#the-shape-is-not-the-whole-check); its whitespace is tidied as [the next section](#paragraphs-follow-the-models-prose) says. A summary that is empty once that tidying is done fails the item as `bad_shape`.

The decoder's grammar bounds neither field above, so a long reply is neither cut off mid-field nor refused. Only the call's response limit ([below](#the-output-budget)) ends one early. There is no automatic retry.

Do not add a cut, a floor or a character limit to a reply. A sentence splitter cannot find a safe cut, because abbreviations, decimals and percentages contain periods, and a reader can see that a summary is long or short but cannot see that part of it was deleted.

## Paragraphs follow the model's prose

There is no paragraph-count cap or word threshold for a paragraph break.
One blank line separates paragraphs. Prose normalization rejoins a lone
newline, collapses repeated blank lines and replaces other control characters
with spaces.

Preserve every nonempty paragraph.

If extraction read only part of the article, state that limitation on the item. Asking for fewer summary words does not tell the reader that part of the source was missing.

## The decoder holds the shape, the prompt does not

Use grammar-constrained decoding derived from the declared reply model. Refuse unknown keys and validate the result after decoding. A well-shaped object still needs content checks.

The request restricts `type` to `none` or an enabled renderer capability. Measured
channels and the optional whole and highlight use references shown in the request,
not literal data, element ids or offsets. A summary-only request has no chart
field in its grammar.

The chart grammar branches on the type the model writes, using the same role
rules as the validator. A line cannot assign its values to a scatter axis,
and a categorical comparison cites a short label span next to each reading.
Label choices are code-supplied references to literal phrases in the fenced
data, not assigned names or a pre-paired data set. The model picks labels and
readings; code checks each reference and cuts the label from source.
An optional date reference can ground a date mentioned in the title or
caption without putting it on the chart's axis.

## One call writes the summary and plans the visual, and the article is read once

[classify/calls.py](../../../backend/idhazh/classify/calls.py) builds the one request
each item makes, and [stages/summarize_one_item.py](../../../backend/idhazh/stages/summarize_one_item.py)
sends it:

- **The system turn** is `write-digest-summary.txt` and `plan-visual.txt`, joined:
  the summary rules, then one short block of chart rules. It is the same bytes on
  every item.
- **The user turn** is the fenced headline, the fenced article as the page wrote it,
  the data references when available, and the closing question from
  `continue-summary.txt`.

The prompt is rendered explicitly rather than by the model's chat template. The shared
system turn is a prefix the server's cache answers for on every item after the first,
so only the headline, the article and the data references are read again.

The [text-analysis service](../text-analysis/text-analysis-api.md) still finds
mentions and can rule out a matched number that is not a measurement. It does
not have to find category names for a chart to be considered.

### The model is shown independent source readings

[`plan_visual_request.py`](../../../backend/idhazh/classify/plan_visual_request.py)
assigns a `q` code to each quantity and a `d` code to each date in the bounded
element table. In short excerpts, the code sits on the reading itself so a
price cannot be mistaken for a nearby percent change. Overlapping excerpts
are joined rather than repeating the numbers beside each other. The excerpts
stay [inside their own untrusted fence](../sources/trust-boundary.md#data-references-are-article-words-inside-the-fence).
The capabilities line outside it is the same for every article under one
configuration; Python does not rank or shortlist forms based on the article.

**The reply is `summary`, then `visual`.** The chart's `why` comes before
`type` so the model names the comparison and takeaway, or a specific mismatch,
before committing to a form. Matching examples in
[`plan-visual.txt`](../../../config/prompts/plan-visual.txt) distinguish two
share prices from a share price and an amount raised. Separately stated
figures can be comparable, and two readings can be enough. The model
looks for the strongest comparable subset before considering a decline;
unrelated figures do not disqualify that subset.

The model chooses which readings and roles to use and cites label phrases
in the article's own words. Code turns those citations into the
[existing visual plan](../publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md#a-chart-answer-becomes-a-plan-in-code).
`none` builds no plan and its `why` is recorded. Replaying a known reply
checks parsing and compilation; the [retained workflow](../../reference/retained-article-verification.md)
shows what the real model chose.

### Every instruction sits in front of the article

Put shared instructions in one stable system turn: summary rules and chart rules. Keep only item-dependent material, such as the data references and the reply fields, behind the article. Derive requested field names from the reply shape.

Fenced headline and article text remain untrusted data. Do not let either become a system instruction, shell argument, filename or fetch destination. Scope an instruction to the job it governs: a plan rule against inventing numbers must not forbid the summary from reporting a source figure.

### The model is shown no sentence address

The article is printed once, whole and unchanged, because the call is asked for no
location. No `[sN]` address, element id, character offset or position appears in any
model-facing text. The evidence index refuses a table built over a different string
from the one the model reads (`SpanDriftError`).

Code derives every location from the labelled spans the service returned, and re-slices
each excerpt from `Article.text` rather than trusting the words the service sent back.
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

Decode the summary before the answer about a chart. If output ends during the answer, `recovered_completion` may recover a complete summary with the JSON decoder, normalize the repaired completion status, and pass it through the same content checks as a normal reply. Publish no picture when its answer is incomplete.

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
request body. The complete input already contains the system turn, the article and
the data references. Cached tokens still occupy context; do not omit them.

The pre-call gate remains an estimate, not a certificate for every request: a measured
scaffold and word rate that bound the prompt from above, the UTF-8 bytes of the references
shown, and the call's response limit. It sizes the article alone first and reads an item
without its references when they would not fit; [throughput.md](throughput.md#the-window-is-checked-before-the-call-is-sent)
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
| Quoting | Attribute quotations and apply the configured limit |
| Voice | Plain, neutral third-person reporting |

## The title is ours, and the source's is only a fallback

Ask for actor and action without hype, withheld facts or a question addressed to the reader. Fence the source headline like the body. Require a title in the decoded draft so the model attempts it. Publish the model's headline as it wrote it, with extra spaces collapsed; no word range applies to it. Fall back to the source headline, and then `Untitled item`, only when the model's is blank, carries an address or is longer than the payload's title field holds (500 characters).

An absent source headline does not block summarization. The article keeps that
absence; the generated title belongs to the summary, not to the source.

The evaluation record identifies the article with its source headline, not a generated title that can change between runs.

## The record covers the ask

`RunRecord.inputs.prompt_sha256` covers both variants of the rendered digest
call with fixed inputs: templates, substituted policy, turn markers and order,
and the data framing and capabilities. `output_schema_sha256` fingerprints the
reply shapes before their references are bound to an article. The exact
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

**Why the model cites readings instead of writing values.** Code reads the
numbers. The model decides what is comparable and useful, and it can do so
without a list of name-and-figure pairs already arranged by Python. The model
can select the wrong source readings; it cannot author a new chart value.

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

The article is printed unchanged and unaddressed, so the bytes the model reads are the bytes
`Article.text` holds and every evidence excerpt comes from them. These invariants prove transport, not
improved model coverage or useful generated visuals; those require a fresh production call.

## See also

- [model-boundary.md](model-boundary.md) - model and runtime compatibility.
- [throughput.md](throughput.md) - request scheduling and rates.
- [../sources/trust-boundary.md](../sources/trust-boundary.md) - untrusted input controls.
- [../../concepts/config/summary-length.md](../../concepts/config/summary-length.md) - what gets summarized, and why no length is asked.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - budget measurements.
