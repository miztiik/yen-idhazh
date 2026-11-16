# Summary Metrics

**Last Updated**: 2026-11-15

What a retained measurement says about a summary, an extraction or a run.

The work stage writes summary measurements through `to_eval_row` in
`backend/idhazh/evals/score.py`. `EvalRow` owns their persisted fields.
[Evaluation](evaluation.md#faithfulness-scored-twice) defines the HHEM
faithfulness scores, their window geometry and the confidence thresholds.

## Summary measurements

Table A

| ID | Column | Meaning and limit |
| --- | --- | --- |
| A1 | `coherence` | Mean cosine between adjacent summary sentences, using the sentence encoder. Its scale is -1 to 1; fewer than two sentences or unavailable weights produce null. Repeated sentences can score highly, so it is recorded, never a gate. |
| A2 | `compression` | Summary word count divided by full-source word count. This is a length ratio, not a confidence grade. The corpus alone retains its existing ratio cutoff, defined in [summary length](config/summary-length.md#the-brief-floor-is-derived-not-chosen). |
| A3 | `source_words_before_cap` | The extractor's full body count, or null when an old cut article's original length is unknowable. |
| A4 | `source_words` | The same extractor counter after the cap. It cannot exceed a known pre-cap count. |
| A5 | `summary_words` | The summary word count, using the retained word tokenizer. Length asks and tolerance remain the summarizer's own policy. |
| A6 | `score_ms` | The faithfulness scorer's elapsed milliseconds for this item, not the model's writing clock. Historical zeroes can mean unmeasured, not instant. |

Coherence runs where the work stage composes the eval row. Assembly reads that
row back rather than recomputing it with another encoder. Compression and word
helpers remain model-free and are also used by extraction and length handling.

## The cut flag says the article was cut

`truncation_flagged` is `Article.truncated`: extraction cut the body at
`extract.truncation_cap_tokens`. It is not inferred from a score gap.
Extraction remains the only stage that cuts article input.

The most direct cut reading is
`source_words_before_cap > source_words`. Both counts come from the extractor,
so their difference measures the cut rather than two tokenizers disagreeing.
Null pre-cap length stays unknown; it is never filled with zero or the cut
length.

Historical flags predate this meaning. The console keeps its existing
`CUT_FLAG_MEANS_A_CUT_FROM` boundary; an earlier flag cannot establish that an
article was cut. The HHEM pair and its validated delta remain independent
measurements, with the windowing limits described in [evaluation](evaluation.md).

## Two rates that score the run, not a summary

The day-metrics producer, `backend/idhazh/telemetry/publish/day_metrics.py`,
joins the day's item-health extraction records to its published items.
`DayExtraction` stores counts, not precomputed rates, so a window can sum the
counts and divide once.

Table B

| ID | Rate | Numerator and denominator |
| --- | --- | --- |
| B1 | `extractable_but_unused_rate` | Published chartable articles without a chart, divided by published chartable articles. Unpublished candidates cannot inflate it. |
| B2 | `span_integrity_rate` | Articles whose element spans still slice their own characters, divided by articles the extraction pass measured. |

An empty denominator produces null, not zero. Neither rate gates publication.
Span integrity remains an item-level trust control; a damaged span degrades its
own item and records why.

Chartability uses `visuals.min_chart_points`, the planner's existing threshold,
not an independent reporting knob. The extraction classes and their limits
remain defined by the [element contract](../architecture/extraction/elements.md).

## Design rationale

The checker bundle is `metrics-6`. Removing heuristic measurements changes
which cells a row carries, not the HHEM model, weights, window or confidence
cuts. Old rows keep their recorded versions, bands and scorer identities.
A run that evaluated nothing still records no scorer identity.

Native readers discard retired cells by name. Current eval rows and day, run
and human-label records omit their retired measurements and aggregates.
Historical confidence reasons and copied-source failure tokens remain decodable
only where an old payload needs them. No archived payload is rewritten, and an
unknown key or invalid retained value still fails validation.

The summarizer no longer measures or rejects copied text. The corpus retains
its extraction-suspect and compression checks without a replacement model-score
gate. The offline prompt loop is removed because all of its promotion targets
were retired; it has no replacement promotion rule.

## See also

- [evaluation.md](evaluation.md) - faithfulness, confidence and human labels.
- [config/summary-length.md](config/summary-length.md) - extraction and summary length policy.
- [../architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md](../architecture/publishing/why-a-summary-was-doubted-and-what-the-checker-measures.md) - retained console consumers.
- [../architecture/contracts/schemas.md](../architecture/contracts/schemas.md) - native contract and compatibility rules.
