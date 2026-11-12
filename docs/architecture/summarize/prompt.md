# The Summarizer Prompt

**Last Updated**: 2026-11-12

What the model is asked to produce, how the two calls share context, and what the pipeline validates. Prompt wording is not a security control: sanitization and validated output shapes enforce the boundary.

## The prompt is a template, not a text

Templates under `config/prompts/` take their word ranges, title limits and
quotation limits from configuration. Use strict substitution so a missing or
renamed value fails rather than reaching the model as an unresolved placeholder.

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
| A1 | `generate_labels` | `prompts/generate-labels.txt` |
| A2 | `write_digest_summary` | `prompts/write-digest-summary.txt` |
| A3 | `plan_visual` | `prompts/plan-visual.txt` |
| A4 | `continue_summary` | `prompts/continue-summary.txt` |
| A5 | `summarize_article` | `prompts/summarize-article.txt` |
| A6 | `compare_articles` | `prompts/compare-articles.txt` |

Production rendering retains universal-newline reading and performs no
whitespace trimming. The prompt-loop utility retains its raw-newline incumbent
read. The app config's additive reader uses the declared task paths if an older
authored input omits `prompt_files`; new authored configuration names them all.
The standalone summary, corpus, reference-set and prompt-loop readers use A5;
the comparison judge and its stamp use A6's full rendered instructions.
Offline judge capture and saved-evidence validation use that same selected file,
so their recorded identity cannot describe instructions from another root.

The [summary generator](../../reference/summary-generator-api.md) and
[comparison workflow](../../reference/summary-evaluation-workflow.md) select
different tasks in the same directory. Neither replaces the digest's continuation
with fresh independent calls. [Native UniEval](../../reference/unieval-api.md)
resolves its own question files before scoring; source coverage keeps its pinned
upstream question construction.

Keep editorial wording shared across models. Model-specific turn markers and template behavior belong with the model entry, not in a second instruction set. [Model boundary](model-boundary.md) owns compatibility checks.

## One ask per article length

`summarize.bands` is an increasing ladder of source-length thresholds and requested summary lengths. Choose the highest band the source reaches; a brief item uses the first band.

- Start the first band at zero and reject duplicate or descending thresholds.
- Choose using source-body length before truncation. `Article.band_source_words` falls back to the available text length for an older payload without that count.
- Keep the extraction floor, brief compression rule and first band's request consistent.
- Keep the absolute rejection floor below every requested band minimum.
- Check that configured thresholds remain reachable under the extraction and context rules.

The active values live in `config/idhazh.json`; [summary length](../../concepts/config/summary-length.md) owns their configuration. Do not copy model-specific tuning values into generic tests.

## What happens when a reply misses the ask

The requested range and the acceptance policy serve different purposes. `summarize.length_policy` tolerates reasonable misses without losing the story.

| Reply | Action |
| --- | --- |
| Within the maximum plus allowance | Publish unchanged |
| Above it on a band whose action is `trim` | Keep the last complete sentence that fits |
| Above it on a band whose action is `publish` | Publish over-length |
| Below the requested minimum | Publish unless the absolute floor applies |
| Below the absolute floor, from a sufficiently long source | Fail the item with its typed length cause |

Use the larger of the proportional and fixed-word overshoot allowances. Apply the absolute floor only above its configured source-length threshold. If no sentence boundary fits a trim, keep the whole reply rather than publish a broken clause.

Long-form bands may retain an over-length ending because it can carry a qualification or response. Length alone must not silently delete a story for exceeding the requested maximum. There is no automatic retry for these misses.

## Paragraphs follow the model's prose

There is no paragraph-count cap or word threshold for a paragraph break.
One blank line separates paragraphs. Prose normalization rejoins a lone
newline, collapses repeated blank lines and replaces other control characters
with spaces.

Preserve every nonempty paragraph. Sentence trimming must preserve retained
paragraph breaks.

Keep decoder character limits loose enough for replies the length policy would publish. A parse failure happens before trimming, so a tight rail can bypass the intended tolerance.

If extraction read only part of the article, state that limitation on the item. Asking for fewer summary words does not tell the reader that part of the source was missing.

## The decoder holds the shape, the prompt does not

Use grammar-constrained decoding derived from the declared reply model. Refuse unknown keys and validate the result after decoding. A well-shaped object still needs content checks.

The label request narrows its reply schema to printed quantity and sentence
addresses. Date rows remain source evidence, but receive no first-pass quantity
judgments. Empty quantity pools permit only an empty label list; no selection
is mandatory. Output budgets use the widest current reply shape rather than
the narrower request.

## The second call writes this summary, and the article is read once

[classify/calls.py](../../../backend/idhazh/classify/calls.py) makes adjacent calls for each item:

1. Label the extracted article elements with `generate-labels.txt`, sharing the
   system turn with `write-digest-summary.txt` and `plan-visual.txt`.
2. Continue that conversation with `continue-summary.txt` to write the summary
   and plan a visual.

The completion prompts are rendered explicitly. The second extends the first prompt and its validated reply instead of reconstructing a chat-message array. Keep the calls adjacent on the same slot so another item cannot evict the shared prefix.

**The continuation receives the same finalized table as reachability and
validation.** After the first reply, `anchored()` adds source-backed entities,
places and recovered quantities with code-computed element ids.
The request builder requires that table rather than reconstructing ids from
the raw label reply. Its compact, fenced data preserves the source cells and
existing label judgements after the reusable prefix. Attaching the data does
not depend on a placeholder in the selected continuation template.

Every reference field in the derived request grammar chooses from exactly
those visible ids. With no ids, reference lists can only be empty and the
optional declared whole can only be null. The native persisted plan remains
unchanged. The active configuration enables type selection and offers only
implemented numeric chart forms. The same restriction applies when type
selection is off. Historical names remain in the
native vocabulary for compatibility, not as new production requests or future
delivery promises.

The shared system turn appends a compact guide derived from the native role
vocabulary and configured evidence floors, without repeating the prompt's
chart and decline instructions or offering retired forms. The
[visual rule](../../concepts/digest.md#the-visual-rule) does not
depend on unfinished article classification or require a fact absent from the
summary. Numeric density alone does not establish a useful comparison.

An input oracle proves that finalized ids are visible and constrain references.
Replaying an authored valid plan proves parsing and compilation, not that a
real model will choose a useful visual.

The current label reply contains `labels`, `proposed` and `named_mentions`.
Quantity labels contain only `element_id`, `measure` and `entity`. A named group
contains exact mention citations, its `entity` or `place` kind and a source-given
name. The single collection preserves the former collections' combined capacity.
Claims, quotes, keyphrases and lede addresses have no current producer.

Historical replies must pass their original closed shape and bounds before
adaptation. The older observation fields are validated together before being
discarded; removed quantity/group judgments are validated too. The continuation
replays the original raw reply only after validation. Unknown keys and malformed
old evidence still fail. Capture envelopes and historical raw bytes are unchanged.

The planner no longer repeats `element_ids`. Code collects the references in
encodings, labels, annotations and the declared whole into the native saved
plan's existing bounded field. Title, caption and diagnostic numbers must be
supported by that selected evidence, not an additional unplotted fact.
Planner confidence remains model-authored and unchanged. Historical raw plans
validate their original reference list; the persisted plan shape is unchanged.

### Every instruction sits in front of the article

Put shared instructions in one stable system turn: element labels, summary rules and visual-plan rules. Keep only item-dependent requests, such as the chosen word range, in the continuation. Derive requested field names from the reply shape.

Fenced headline and article text remain untrusted data. Do not let either become a system instruction, shell argument, filename or fetch destination. Scope an instruction to the job it governs: a labeling rule against inventing numbers must not forbid the summary from reporting a source figure.

### Sentence addresses identify source sentences, not physical line counts

The label turn prints each original sentence slice as `[sN]` followed by one
JSON string on one physical line. JSON escapes internal line controls,
backslashes and quotation marks; decoding and concatenating those strings
recovers the original source, including sentence-boundary whitespace. The
presentation does not change `Article.text`, segmentation, offsets or hashes.
Non-ASCII text stays literal so the existing sanitizer still recognizes forged
turn markers. The escaped strings remain fenced user data, never instructions.

Copy the printed address literally. Mention surfaces must occur exactly once
inside that original named sentence. A repeated bare name needs another exact
unique occurrence or a minimal exact qualifying noun phrase within the existing
bound; it does not permit neighbouring-sentence, global or fuzzy rescue.
Distinct people remain distinct and geographic markets belong in place mentions. The
[element contract](../extraction/elements.md#the-two-kinds-only-a-model-can-find)
owns those meanings and anchoring rules.

The current grammar binds quantity labels to printed quantity ids and citations
to printed sentences. Only code-minted addresses enter the grammar, never source
words. Empty pools keep empty selections. Legal references do not establish
useful numeric generation.

`measure_two_calls.article_from_user_turn` recognizes the explicit current
JSON-string heading and the historical raw-line heading separately. It decodes
only the former and refuses malformed current strings or addresses, without
retrying them as historical text. Historical displays keep literal escapes and
continuation newlines; their stripped sentence separators cannot recover the
original offsets. Use the retained native Article for that provenance.
Historical raw label replies and capture fields stay unchanged; their
compatibility validation does not widen the current three-field decoder.

### What is in the prompt bytes, and who wrote each part

The active model entry declares its turn opening, closing, reply openings, system-turn placement and any thinking marker. Preserve required whitespace. Validate the declaration against the model identity and the runtime's own template before processing items.

- Require the role placeholder where a marker opens a role-bearing turn.
- Reject empty structural markers and incompatible system-role/joiner declarations.
- Match nested reply openings longest-first.
- Read a continuation's opening from the prompt being extended, not an independent flag.
- Confirm the sanitizer strips every declared marker an article could forge.
- Prove both byte-prefix and token-prefix continuity with the configured tokenizer.

The native completion request carries `json_schema` explicitly and declares `cache_prompt`. Do not assume a compatibility route honors a field merely because it accepts the request. Recorded prompt fixtures prove rendering; live startup checks prove compatibility with the current server and model.

### Summary before visual

Decode the summary before the visual plan. If output ends during the plan, `recovered_completion` may recover a complete summary with the JSON decoder, normalize the repaired completion status, and pass it through the same content checks as a normal reply. Publish no picture when its plan is incomplete.

Never recover a partially written summary. A visual plan may cite only validated source elements, not a figure invented by the summary it follows.

### The output budget is derived, not picked

When the model file does not declare `sampling.max_tokens`, derive reply budgets
from the schema's bounded arrays and strings. An explicit limit replaces those
budgets on each request, including continuations; see
[model-file.md](../../concepts/config/model-file.md#design-rationale).
Both calls use the shared JSON-width calculation, but their character-to-token
conversions differ because their outputs differ.

The summarize-and-plan reply contains prose and bounded structure. The label reply uses a measured output-density estimate. Name the tokenizer and evidence behind that estimate; it is not a mathematical guarantee for every possible string.

The label reply also becomes part of the second prompt. Count it in both positions when checking the context window. Do not silently clamp a reply budget to available context. Report a window failure at the call site.

The label and context allowances derive from the current native shape, not
retired observations or the narrower per-article reference menu. Effective
configured response caps, context and timeout settings do not change with this
retirement.

For capacity diagnostics, tokenize the complete rendered continuation with the
configured model's vocabulary, then add the effective response limit from that
request body. The complete input already contains the first prompt, the actual
label reply, the shared guide and the finalized evidence menu. Cached tokens
still occupy context; do not omit them or add the first reply's maximum budget
again. Check the first call's own prompt and response allowance separately.

An explicit `max_tokens` replaces the shape-derived budget. Summary word ranges
are editorial requests, not those runtime token limits. The measurement utility
reports complete-request capacity using the effective cap before applying its
optional diagnostic decode cap, so a short timing run cannot claim more
production space than the configured request has.

The existing pre-label gate remains an estimate over measured word/menu rates
and derived reply budgets, not a certificate for every finalized request.
Conservative byte ceilings are not observed token counts. A bounded check with
retained production replies and a constructed source-cap input measures those
requests only; a repeated long source and its historical reply do not establish
universal fit or present-day planning quality. Capacity diagnostics do not
change admission, suppress a visual, reduce a response cap or replace existing
summary-first recovery.

A cut label reply fails as `labels_truncated`. Do not repair missing arrays as empty: that would make incomplete output indistinguishable from an article with no elements. A retry needs a deliberate input change and a configured attempt policy; repeating an identical deterministic request is not recovery.

## The shape is not the whole check

After parsing, `to_summary` enforces publishability.

- Reject excessive contiguous copying from the source with `copied_source`, using the configured verbatim ceiling.
- Reject a summary containing an address or the sanitizer's link marker with `leaked_address`. Reuse the sanitizer's definition instead of adding another URL pattern.
- If the generated title is invalid or leaks an address, discard that title and use the established fallback; do not discard a valid summary for a title failure.
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

Re-tokenize the complete rendered requests for a candidate model. Recorded incumbent fixtures prove parser behavior, not another model's template, context fit or live responses. Keep decoder character rails derived from the current acceptance policy, while retaining word-based content checks after parsing.

## What the prompt asks for, section by section

| Section | Required content |
| --- | --- |
| Framing | Make clear how the article knows what it reports |
| Title | A new factual title drawn from the body, with a source headline when available |
| Length | The selected band's request |
| Source form | Attribute an abstract's claims to its authors |
| Attribution | Name who made a claim; distinguish self-reported figures |
| Certainty | Preserve the difference between proposal, forecast, claim and result |
| Faithfulness | Preserve source facts, names and figures without invention |
| Quoting | Attribute quotations and apply the configured limit |
| Voice | Plain, neutral third-person reporting |

## The title is ours, and the source's is only a fallback

Ask for actor and action without hype, withheld facts or a question addressed to the reader. Fence the source headline like the body. Require a title in the decoded draft so the model attempts it, but permit the published title to fall back to the source headline and then `Untitled item`.

An absent source headline does not block summarization. The article keeps that
absence; the generated title belongs to the summary, not to the source.

The evaluation record identifies the article with its source headline, not a generated title that can change between runs.

## The record covers the ask

`RunRecord.inputs.prompt_sha256` covers templates, substituted policy, turn markers and turn order. It must not change merely because the article or label reply changes. The two-call path supplies its own prompt inputs to the recorded run manifest.

Changing prompt wording or policy changes this identity. The digest makes the change observable; it is not permission to skip work or a quality verdict.

## The changes are not retroactive

Prompt changes affect new work, not frozen published days. Do not rebuild the archive as an incidental part of a prompt edit. An evaluation harness must exercise the same request construction and transport as the production path it claims to assess.

## Design rationale

Reduce labeling to chart evidence, not a general article inventory. Quantity
meaning and known-subject links support chart planning and relationship checks.
Repeated salience, attribution, hedge, dimension and time judgments have no
independent downstream check; chart framing must still preserve material
qualifications, and temporal charts still cite source DATE elements.

The model sees source ids, kinds, excerpts, parsed values, units and sentence
addresses, plus retained measure/subject judgments. Character offsets, extractor
bookkeeping and unused historical judgments stay out of this projection.
Persisted spans, source hashes and re-slicing checks remain intact: they validate
the evidence rather than merely help debugging. Summary instructions and the
shared-prefix continuation are unchanged.

A stable prefix reduces repeated reading without treating prompt wording as a control. Per-band requests fit different source lengths while a separate acceptance policy preserves useful replies. Summary-first decoding protects the reader's primary content when visual planning cannot finish. Model-specific transport declarations keep shared editorial instructions testable across models.

Task paths belong to the selected configuration so a candidate never reads
instructions from the original checkout. One directory holds distinct products
and call flows, not one shared summary instruction or a scanned prompt registry.

Escaping sentence presentation removes unaddressed continuation lines without
normalizing the source that evidence indexes. An explicit heading distinguishes
that presentation from historical raw text without changing the saved reply or
capture format. These invariants prove transport, not improved model coverage
or useful generated visuals; those require both fresh production calls.

## See also

- [model-boundary.md](model-boundary.md) - model and runtime compatibility.
- [throughput.md](throughput.md) - request scheduling and rates.
- [../sources/trust-boundary.md](../sources/trust-boundary.md) - untrusted input controls.
- [../../concepts/config/summary-length.md](../../concepts/config/summary-length.md) - length configuration.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - budget measurements.
