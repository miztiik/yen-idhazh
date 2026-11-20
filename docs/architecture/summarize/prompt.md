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

The request restricts the answer about a chart to what the request offered: `type`
is `none` or a form on the request's forms line, and `focus` is a row code the
tables show, or null. The model names a row and writes no element id and no
position: code finds the elements the row stands for, from offsets it computed.
With no tables the grammar is the summary alone, so the decoder cannot write an
answer about a chart, rather than being asked not to.

## One call writes the summary and plans the visual, and the article is read once

[classify/calls.py](../../../backend/idhazh/classify/calls.py) builds the one request
each item makes, and [stages/summarize_one_item.py](../../../backend/idhazh/stages/summarize_one_item.py)
sends it:

- **The system turn** is `write-digest-summary.txt` and `plan-visual.txt`, joined:
  the summary rules, then one short block of chart rules. It is the same bytes on
  every item.
- **The user turn** is the fenced headline, the fenced article as the page wrote it,
  the tables of figures when code built any, and the closing question from
  `continue-summary.txt`.

The prompt is rendered explicitly rather than by the model's chat template. The shared
system turn is a prefix the server's cache answers for on every item after the first,
so only the headline, the article and the tables are read again.

**The names and places are not asked of the model.** The
[text-analysis service](../text-analysis/text-analysis-api.md) labels them in
`Article.text` before the model runs, and the work stage turns each labelled span into an
entity or place element with code-computed ids. A service that cannot answer leaves the
element table with the figures and dates the patterns found; with no names there is no
table of figures, so the call asks no question about a chart, and the item publishes. The
[element contract](../extraction/elements.md) owns how a label becomes an element.

### The model is shown tables of figures, never the element table

[`pair_names_with_figures.py`](../../../backend/idhazh/classify/pair_names_with_figures.py)
reads the element table and the article text with no model, and builds rows of
`code | name | figure`, such as `r1 | Denmark | 1200 MW`. A blank line separates one
table from the next, and the codes run r1, r2, ... across all of them. A table is a run of
consecutive sentences that each pair names with exactly one figure of one unit, with
between `visuals.min_chart_points` and `visuals.max_chart_points` rows; a list over the
ceiling is refused whole, never trimmed. **A wrong pairing is worse than a missed one**: a
chart of true numbers beside the wrong name passes every check that follows, so a sentence
code cannot pair for sure pairs nothing. The module's docstring owns the rules and the
cases each one refuses.

The tables follow the article inside the same untrusted fence
([trust boundary](../sources/trust-boundary.md#the-tables-of-figures-are-article-words-inside-the-fence)),
and one line written by code, outside the fence, names the chart forms on offer. Only
`bar` and `dot` are offered: a name and a figure a mark, with no separately stated whole,
is all a table holds. The validator, the replacement ladder and the compiler still support
the other numeric forms; no model answer reaches them, so the ladder has nothing to step
down from today and stays off by default.
No table built means the question about a chart is left off the request
([what that records](../publishing/visuals.md#every-none-says-which-gate-refused-it)).

**The reply is `summary`, then `visual`.** `summary` is decoded first, so a cut reply
keeps it. `visual` is `{why, type, focus, title, caption}`, every key present and null when
unused: `why` is one sentence in words with no digits, `type` is `none` or an offered
form, `focus` is the row the item turns on, and `title` and `caption` are short prose that
keep the plan contract's length bounds. `why` comes first because with thinking off it is
the model's only room to reason; that order is a design choice, and whether it improves
answers is read off published runs. `none` is final: no plan is built, nothing else in the
answer is read, and `why` becomes the recorded rationale.

The chart rules in the system turn are the same for every article, so the cached start of
the prompt never moves. They say when a chart is worth drawing - the item is about how the
figures in one table compare across names - and when it is not, with one worked chart
answer and one worked `none` answer;
[`plan-visual.txt`](../../../config/prompts/plan-visual.txt) owns the wording. The
[visual rule](../../concepts/digest.md#the-visual-rule) does not
depend on unfinished article classification or require a fact absent from the
summary. Numeric density alone does not establish a useful comparison.

**Code builds the plan, and the model never writes one.** A chart answer becomes a complete
`VisualPlan` from the table of the row it names, and it is refused by a named rule when it
has no `focus`, no title, or a digit in `why`, `title` or `caption`
([the plan page](../publishing/what-a-visual-plan-may-say-and-what-happens-to-one-that-is-refused.md#a-chart-answer-becomes-a-plan-in-code)).
The validator, the replacement ladder and the compiler run unchanged.

An input oracle proves that the request shows the rows code built and binds the answer to
their codes. Replaying a recorded valid answer proves parsing, plan building and
compilation, not that a real model will choose a useful visual.

### Every instruction sits in front of the article

Put shared instructions in one stable system turn: summary rules and chart rules. Keep only item-dependent requests, such as the tables and the reply fields, behind the article. Derive requested field names from the reply shape.

Fenced headline and article text remain untrusted data. Do not let either become a system instruction, shell argument, filename or fetch destination. Scope an instruction to the job it governs: a plan rule against inventing numbers must not forbid the summary from reporting a source figure.

### The model is shown no sentence address

The article is printed once, whole and unchanged, because the call is asked for no
location. No `[sN]` address, element id, character offset or position appears in any
model-facing text, and the grammar has no field that could carry one. Every row is cut
by offsets into `Article.text`, so the table builder refuses an element table built over
a different string than the text it reads (`SpanDriftError`): rows that point into a
document the model is not reading are the failure it prevents.

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

Never recover a partially written summary. A chart is built only from rows of tables code cut from the article, never from a figure invented by the summary it follows.

### The output budget

The call has nothing to derive a budget from. Its two prose fields carry no length
bound, so it runs under the model file's `sampling.max_tokens`, or
`DEFAULT_MAX_TOKENS` where the file names none, with tables or without; see
[model-file.md](../../concepts/config/model-file.md#design-rationale). Do not silently clamp a reply
budget to available context. Report a window failure at the call site.

For capacity diagnostics, tokenize the complete rendered request with the
configured model's vocabulary, then add the effective response limit from that
request body. The complete input already contains the system turn, the article and
the tables of figures. Cached tokens still occupy context; do not omit them.

The pre-call gate remains an estimate, not a certificate for every request: a measured
scaffold and word rate that bound the prompt from above, the UTF-8 bytes of the tables
shown, and the call's response limit. It sizes the article alone first and reads an item
without its tables when they would not fit; [throughput.md](throughput.md#the-window-is-checked-before-the-call-is-sent)
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

`RunRecord.inputs.prompt_sha256` covers templates, substituted policy, turn markers and turn order. It must not change merely because the article changes. `classify.calls.prompt_inputs` supplies the digest call's inputs to the recorded run manifest: the system and user turns rendered with the headline and article empty, one fixed example table framed exactly as a real one is, the summarize block, `visuals.enabled_kinds` and the selected chart types. The example table is there because no real table is in a rendering with no article, so without it a change to the table wording, the row layout, the fence or the forms line would leave the stamp unmoved. The kinds are digested beside the bytes because the rendering is always the call without tables, so a run that asks about no chart would otherwise read as unchanged.

Changing prompt wording or policy changes this identity. The digest makes the change observable; it is not permission to skip work or a quality verdict.

## The changes are not retroactive

Prompt changes affect new work, not frozen published days. Do not rebuild the archive as an incidental part of a prompt edit. An evaluation harness must exercise the same request construction and transport as the production path it claims to assess.

## Design rationale

Read the article once. The first of the two calls the pipeline used to make only labelled what
code could already find: on 66 captured articles it took 3.67 of 7.04 hours of model time
(52 percent) and fed a chart planner that published no chart, while the local text-analysis
service returns the same names and places with exact offsets in seconds. Dropping the call
saves its decode, because the remaining call reads the article either way. What the model no
longer writes - what a figure measures and whom it describes - is not replaced by a model:
code pairs a name with the figure written beside it, the model reads the pair against the
article, and the validator still checks every element the plan cites.
Scatter and bubble charts needed the subject link only that call wrote, so they cannot validate
until a code rule links a figure to its subject.

**Why the model is shown rows and not elements.** Code makes the pairing of a name with a figure,
under rules that refuse any sentence they cannot pair for sure, and the model keeps the judgement
only it can make: whether a table is worth a chart, in which form, which row the item turns on, and
the title. It writes no figure and no id, so its answer is a few short fields and the worst a
hostile page can do is steer the choice of table, form or row. What this gives up: a story whose
figures sit in prose the rules refuse draws nothing, and so does a form that needs more than a name
and a figure for each mark. Those forms stay supported downstream and are offered only when the
builder can make a table shape that holds them.

The service is a new recipient of article text, so it is a loopback process the run starts
and its reply is data ([trust boundary](../sources/trust-boundary.md)). What reaches the model
from it is an excerpt re-sliced from `Article.text` and shown only as a cell of a fenced row,
like any other word of the article; no word the service returns is ever a prompt, path, URL or
shell argument.

The model sees a row code, a name and a figure's words. Element ids, kinds, parsed values and
units, character offsets, extractor bookkeeping and sentence addresses stay out of this
projection. Persisted spans, source hashes and re-slicing checks remain intact: they validate
the evidence rather than merely help debugging.

A stable prefix reduces repeated reading without treating prompt wording as a control. Summary-first decoding protects the reader's primary content when visual planning cannot finish. Model-specific transport declarations keep shared editorial instructions testable across models.

Task paths belong to the selected configuration so a candidate never reads
instructions from the original checkout. One directory holds distinct products
and call flows, not one shared summary instruction or a scanned prompt registry.

The article is printed unchanged and unaddressed, so the bytes the model reads are the bytes
`Article.text` holds and every row it is shown is cut from them. These invariants prove transport, not
improved model coverage or useful generated visuals; those require a fresh production call.

## See also

- [model-boundary.md](model-boundary.md) - model and runtime compatibility.
- [throughput.md](throughput.md) - request scheduling and rates.
- [../sources/trust-boundary.md](../sources/trust-boundary.md) - untrusted input controls.
- [../../concepts/config/summary-length.md](../../concepts/config/summary-length.md) - what gets summarized, and why no length is asked.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - budget measurements.
