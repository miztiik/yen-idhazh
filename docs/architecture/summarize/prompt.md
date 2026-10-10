# The Summarizer Prompt

**Last Updated**: 2026-10-10

What the model is asked to produce, how the two calls share context, and what the pipeline validates. Prompt wording is not a security control: sanitization and validated output shapes enforce the boundary.

## The prompt is a template, not a text

Templates under `backend/idhazh/prompts/` take their word ranges, title limits and quotation limits from configuration. Use strict substitution so a missing or renamed value fails rather than reaching the model as an unresolved placeholder.

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

## A long summary may be two paragraphs

`summarize.paragraphs_max` limits paragraphs; `second_paragraph_from_words` decides when the prompt asks for a break. One blank line separates paragraphs. Prose normalization rejoins a lone newline, collapses repeated blank lines and replaces other control characters with spaces.

Fold surplus paragraphs into the last permitted paragraph rather than dropping their text. Sentence trimming must preserve retained paragraph breaks. Keep the paragraph instruction independent of an item's band when it appears in the shared system prefix.

Keep decoder character limits loose enough for replies the length policy would publish. A parse failure happens before trimming, so a tight rail can bypass the intended tolerance.

If extraction read only part of the article, state that limitation on the item. Asking for fewer summary words does not tell the reader that part of the source was missing.

## The decoder holds the shape, the prompt does not

Use grammar-constrained decoding derived from the declared reply model. Refuse unknown keys and validate the result after decoding. A well-shaped object still needs content checks.

## The second call writes this summary, and the article is read once

[classify/calls.py](../../../backend/idhazh/classify/calls.py) makes adjacent calls for each item:

1. Label the extracted article elements with `label_article_elements.txt`.
2. Continue that conversation to write the summary and plan a visual.

The completion prompts are rendered explicitly. The second extends the first prompt and its validated reply instead of reconstructing a chat-message array. Keep the calls adjacent on the same slot so another item cannot evict the shared prefix.

### Every instruction sits in front of the article

Put shared instructions in one stable system turn: element labels, summary rules and visual-plan rules. Keep only item-dependent requests, such as the chosen word range, in the continuation. Derive requested field names from the reply shape.

Fenced headline and article text remain untrusted data. Do not let either become a system instruction, shell argument, filename or fetch destination. Scope an instruction to the job it governs: a labeling rule against inventing numbers must not forbid the summary from reporting a source figure.

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

Derive reply budgets from the schema's bounded arrays and strings. Both calls use the shared JSON-width calculation, but their character-to-token conversions differ because their outputs differ.

The summarize-and-plan reply contains prose and bounded structure. The label reply uses a measured output-density estimate. Name the tokenizer and evidence behind that estimate; it is not a mathematical guarantee for every possible string.

The label reply also becomes part of the second prompt. Count it in both positions when checking the context window. Do not silently clamp a reply budget to available context. Report a window failure at the call site.

A cut label reply fails as `labels_truncated`. Do not repair missing arrays as empty: that would make incomplete output indistinguishable from an article with no elements. A retry needs a deliberate input change and a configured attempt policy; repeating an identical deterministic request is not recovery.

## The shape is not the whole check

After parsing, `to_summary` enforces publishability.

- Reject excessive contiguous copying from the source with `copied_source`, using the configured verbatim ceiling.
- Reject a summary containing an address or the sanitizer's link marker with `leaked_address`. Reuse the sanitizer's definition instead of adding another URL pattern.
- If the generated title is invalid or leaks an address, discard that title and use the established fallback; do not discard a valid summary for a title failure.
- Record a typed failure and its observed values in item health. Do not infer outcomes later by scraping logs.

## Two spans on one call

Reasoning is declared by the model's closing marker. On the explicit-completion path, a reasoning span runs without the output grammar until that marker, the context limit or timeout. The answer span continues the same prompt with the grammar restored and its own reply budget.

Discard reasoning before the reply reaches a persisted payload, reader surface or later article-level continuation. With no declared marker, reject unexpected reasoning. Check both inline thinking blocks and a separate reasoning channel, and inspect every inline block rather than only the first.

The chat-template path lets the runtime manage its reasoning split. It must still satisfy the same no-leakage check. Use current [qualification rules](../../concepts/qualification.md) and [evaluation policy](../../concepts/evaluation.md) to assess quality; a protocol change does not establish a quality gain.

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

A stable prefix reduces repeated reading without treating prompt wording as a control. Per-band requests fit different source lengths while a separate acceptance policy preserves useful replies. Summary-first decoding protects the reader's primary content when visual planning cannot finish. Model-specific transport declarations keep shared editorial instructions testable across models.

## See also

- [model-boundary.md](model-boundary.md) - model and runtime compatibility.
- [throughput.md](throughput.md) - request scheduling and rates.
- [../sources/trust-boundary.md](../sources/trust-boundary.md) - untrusted input controls.
- [../../concepts/config/summary-length.md](../../concepts/config/summary-length.md) - length configuration.
- [../../concepts/qualification.md](../../concepts/qualification.md) - candidate verification.
- [../../reference/pipeline-cost.md](../../reference/pipeline-cost.md) - budget measurements.
