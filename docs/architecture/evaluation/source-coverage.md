# How source coverage uses retrieved evidence

**Last Updated**: 2026-11-07

How the legacy method preserves its source-section coverage and sentence
explanations without becoming native UniEval's independent-reference method.

## Calculation

The caller supplies prepared source and summary text. The method trims the
same outer whitespace as the legacy calculation, prepares its macro view,
and evaluates fluency, coherence and retrieved sentence/source consistency
in that order through the real upstream summarization evaluator.

Fluency uses the complete cleaned summary. Coherence uses the retained macro
view: eligible paragraphs, the configured character limits for short views,
or the leading paragraphs and final paragraph separated by the omission
marker. The long view keeps the existing word limit.

Source chunks retain overlapping word boundaries. The default target remains
380 words with the legacy `stride_words` setting retaining 80 overlapping
words, so adjacent default chunks advance by 300 words. The configured limits
change behavior without editing source; extraction introduces no new truncation.

For each summary sentence, BM25 selects the existing ordered source candidates.
The default remains two candidates. Identical source/sentence pairs are
deduplicated in first-use order before the genuine batched consistency call.
Each sentence keeps its highest score and first winning chunk on ties.

Scores retain three-decimal rounding. Sentence support uses the rounded score
against the existing 0.50 grounding threshold. Coverage counts distinct winning
chunks for supported sentences, not every retrieved chunk with a high score,
and retains one-decimal percentage rounding. Overall consistency averages the
already-rounded sentence scores and rounds that average again.

Supported sentences retain their selected source sentence and explanation.
Uncovered sections retain their excerpt, maximum compared score and explanation.
Optional historical evidence fields remain readable; absent fields are not
filled with invented evidence.

## Independent method and resources

Native UniEval also requires an independent reference summary and calculates
relevance. Source coverage does not receive, generate or substitute that
reference and does not relabel its coverage or sentence scores as native
relevance. Its upstream model-call boundary remains distinct even when the
selected model repository is the same.

`config/summary-evals/unieval-evaluator/coverage.json` owns the exact preparation
defaults and named code, tokenizer and sentence resources. The loader verifies
the immutable local code and model identities. The public NLTK sentence API
uses the prepared `tokenizers/punkt_tab` layout. Retained tokenizer/retrieval
fallbacks carry fixed safe warnings rather than exception or article text.

The [capture procedure](../../how-to/capture-source-coverage-calls.md) retains
genuine ordered dimension-call inputs/results and final metrics. Replay uses
the actual upstream converter, tokenizer, retrieval and reduction; a saved final
HTTP response is not that calculation oracle.

## Complete native result boundary

Each returned batch must match its requested comparison count and contain
every requested dimension as a finite probability. Validation runs before
rounding or reduction. Missing batches, keys or nonfinite values fail with
`INVALID_MODEL_OUTPUT` instead of becoming successful zero scores. A genuine
numeric zero remains valid. No completed dimension becomes partial coverage
success when another required call fails.

## Design rationale

Preparation, retrieval and reduction answer separate questions, so they live
in separate modules. The model boundary contains the real upstream call and
converter rather than a renamed native scorer or a plausible-value replacement.
Keeping the recorded before-calculation evidence makes structural extraction
checkable without claiming model quality or fresh-run numerical reproducibility.

## See also

- [unieval-api.md](unieval-api.md) - the independent-reference native calculation.
- [summary-evaluator.md](summary-evaluator.md) - shared HTTP composition and process ownership.
- [../../reference/unieval-api.md](../../reference/unieval-api.md) - native request and result fields.
- [../../how-to/capture-source-coverage-calls.md](../../how-to/capture-source-coverage-calls.md) - actual recording provenance and commands.
