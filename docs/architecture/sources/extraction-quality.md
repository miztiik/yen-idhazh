# Measured extraction quality

**Last Updated**: 2026-10-30

Which article-shape signals did the TypeScript parser measure, and what do
they change? The shared `parseDocument` stage serves both `/parse` and `/plan`.
It uses the meanings in `backend/idhazh/extract.py` and
`backend/idhazh/contracts/article.py`, not an additional article contract.

## Measurements and consequences

The existing diagnostic object carries optional `quality`, declared in
`backend/idhazh/contracts/feed_ingest_diagnostics.py` and bound to its small
TypeScript copy by `test_typescript_field_types_defaults_and_vocabularies`.
No quality verdict is inferred from an author, a title, or source authority.
Publisher access refusal precedes quality, as in Python: paywalled pages carry
no quality verdict and retain the existing later paywall rejection.

`source_word_count` counts the complete sanitized extracted body before any
worker cap. `word_count` counts the returned body. They agree here because
harvesting retains full text for dispatch. `token_count`, `truncated` and
`truncated_at_tokens` are null: this stage neither runs a tokenizer nor cuts
the worker's model input. `truncation_cap_tokens` records the configured
downstream cap, not a claim that it ran. Worker extraction retains ownership
of that cut and its token estimate. Stored article input is not shortened to
simulate it.

`corroborated_word_count` is the largest qualifying independent statement of
article length: a news-article JSON-LD `articleBody`, microdata `articleBody`,
or the first article container whose first heading matches `og:title`.
The container is wrapped as an inert page and extracted on its own. Its raw
body words are counted before sanitizer transformations, as in Python.
Script, style and noscript text do not enter the tree witnesses. Malformed
JSON-LD records the existing warning and does not erase other witnesses.
A witness below `corroboration_min_words` does not qualify.

`contaminated` is true when full extracted words divided by corroborated
words strictly exceeds `corroboration_ratio_max`. It is null without a
qualifying witness, not a false claim of a clean page.
`not_prose` uses the existing minimum sentence count, sentence word count,
line-count floor and proportion of prose lines. `too_short` compares full
source words with `min_source_words`.

`boilerplate` is null. Python receives no sibling-host lines and therefore
cannot provide a meaningful positive reading either. Enabling
`reject_boilerplate` cannot supply that missing measurement. There is no host
history or additional state file.

All measured booleans remain visible. `failure_code` selects the native
precedence: contamination, boilerplate if measured, non-prose, then short
text. Only that selected signal's rejection flag applies. This preserves the
native case where short non-prose text remains admitted when
`reject_not_prose` is false, even if `reject_too_short` is true.
An `abstract` is exempt only from the short-text rejection; its short-text
measurement remains recorded.

The loader requires the existing extraction controls from `config/idhazh.json`.
It checks that `min_source_words` equals the rounded-up quotient of
`summarize.bands[0].target_words_min` and
`evaluation.brief_compression_ceiling`, exactly as `AppConfig` does.
The committed values are unchanged: `reject_too_short` is true and the other
three rejection flags are false. Model-default false values are not a reason
to override authored configuration.

A configured rejection uses existing `EXTRACT_FAILED` with the selected typed
signal and full measurements in diagnostics. Parsing remains successful. Its
completion event carries a separate `quality_rejection` reason and measured
source/body word counts, plus the safe article address when available.
Attribution reads that typed reason as a quality decision, not a source failure.
The capture is not counted as admitted or source-refused, so its admission total
and source pass rate remain unavailable rather than assigning source blame.
Other refusals, rankings, source quotas and screening thresholds are unchanged.
An acceptable body with no source title is measured, but the planner's existing
required-title rejection remains; this increment does not change that contract.

## Provenance and historical reads

`extractor_version` names the installed Defuddle and Linkedom versions and a
SHA-256 fingerprint of the fixed named extraction source files.
`sanitizer_version` identifies the TypeScript sanitizer implementation and its
source fingerprint, not a claim that Python executed.
Source line endings are normalized before hashing so identical behavior has
the same identity on Windows and Ubuntu. Provenance participates in the
harvest configuration fingerprint and durable operation configuration check.
A changed implementation cannot replay an old operation as new extraction.

Rejections, article assessments and planner events advance to `2026-10-23`.
Earlier diagnostic schemas remain exact for physical and logical digest
verification. Their readers add null quality only after validating the
historical record. No word count, quality verdict or implementation version
is reconstructed for historical rows. Files on disk are not restamped.
Candidate, dispatch and source-run shapes do not change.
Logical completion proofs also use their exact original schema: diagnostic-era
proofs retain every measured diagnostic cell, and exclusion-era proofs retain
their exclusion details. Only absent, null quality is removed for those stamps.
A non-null newer measurement cannot be encoded as an older proof.

## Design rationale

Defuddle and Trafilatura are different extractors, not interchangeable version
labels. The recorded contaminated-front-page fixture returns 1,378 full words
and a 1,017-word container witness in TypeScript: about 1.36 times the witness,
below the configured contamination ceiling of 2 times. The committed Python
expectations are 3,818 words and a 1,034-word witness: about 3.69 times, above
that ceiling. The native rule is the same; what the libraries extract differs.
The TypeScript fixture records the actual reading rather than manufacturing a
positive signal or moving the threshold. Controlled markup variations on the
recorded article prove both sides of the ratio and the configured consequence.
This is signal-rule parity, not byte-identical extracted content.

The existing Defuddle, Linkedom and sanitizer are reused. No dependency,
network authority, publication switch or external state is added. Consent and
blocked-player interface containers are removed by their exact class tokens
before main-body extraction, as in the native extractor. Resources remain
disabled and publisher metadata never supplies a fetch target.

## See also

- [Harvesting](feed-harvesting.md)
- [Failure diagnostics](feed-failure-diagnostics.md)
- [Trust boundary](trust-boundary.md)
- [Run the gates](../../how-to/run-the-gates.md)
