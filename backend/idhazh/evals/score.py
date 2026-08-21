"""Compose one item's scores into one ledger row.

The faithfulness score is one input here, not the verdict. It is paired with
metrics that see what it cannot, and one of them can override it outright: a
summary asserting a figure the article never gave is low-confidence whatever
the faithfulness model thinks, because that model marks a wrong number
generously - the entity and the relation both survive, and only the fact is
false.
"""

from __future__ import annotations

from typing import Final

from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.article import Article
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary
from idhazh.evals import metrics

_DELTA_PLACES: Final = 6
_UNTITLED: Final = "Untitled item"


def band(
    faithfulness: float, *, unsupported_numbers: int, config: EvaluationConfig
) -> ConfidenceBand:
    """The band, not the number, is what drives behaviour and what a reader sees.

    An unsupported figure forces the bottom band. Nothing else in the row can
    see that defect, so nothing else may outvote it.
    """
    if unsupported_numbers:
        return ConfidenceBand.LOW
    if faithfulness >= config.band_high_min:
        return ConfidenceBand.HIGH
    if faithfulness >= config.band_medium_min:
        return ConfidenceBand.MEDIUM
    return ConfidenceBand.LOW


def to_eval_row(
    *,
    item: PlannedItem,
    article: Article,
    summary: Summary,
    full_text: str,
    hhem: float,
    hhem_full: float,
    config: EvaluationConfig,
    date: str,
    run_id: str,
    scorer_version: str,
    scored_at: str,
    extraction_suspect: bool = False,
    determinism_violation: bool = False,
) -> EvalRow:
    """Everything measured about one item, in the shape the ledger keeps forever.

    `full_text` is the whole article, not the truncated text the model saw. The
    gap between the two faithfulness scores is the cost of truncation, and it is
    invisible unless both are measured.
    """
    text = summary.summary or ""
    unsupported = metrics.unsupported_numbers(text, full_text)
    delta = round(hhem - hhem_full, _DELTA_PLACES)

    return EvalRow(
        version=EvalRow.schema_version(),
        date=date,
        run_id=run_id,
        item_id=item.item_id,
        url_key=item.url_key,
        source_url=item.canonical_url,
        title=(item.title or article.title or _UNTITLED),
        vertical=item.vertical,
        model_id=summary.model_id,
        attempt=summary.attempt,
        hhem=hhem,
        hhem_full=hhem_full,
        hhem_delta=delta,
        truncation_flagged=delta > config.truncation_gap_max,
        coverage=metrics.lead_coverage(text, full_text),
        compression=metrics.compression(text, full_text),
        extractiveness=metrics.extractiveness(text, full_text),
        verbatim_run=metrics.verbatim_run(text, full_text),
        unsupported_numbers=unsupported,
        hedge_dropped=metrics.hedge_dropped(text, full_text),
        extraction_suspect=extraction_suspect,
        band=band(hhem, unsupported_numbers=unsupported, config=config),
        source_word_count=metrics.word_count(full_text),
        source_seen_word_count=article.word_count,
        summary_word_count=metrics.word_count(text),
        pipeline_fingerprint=summary.pipeline_fingerprint,
        output_digest=summary.output_digest,
        determinism_violation=determinism_violation,
        scorer_version=scorer_version,
        scored_at=scored_at,
    )
