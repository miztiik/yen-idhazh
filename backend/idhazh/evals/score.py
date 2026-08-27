"""Compose one item's scores into one ledger row.

The faithfulness score is one input here, not the verdict. It is paired with
metrics that see what it cannot, and one of them can override it outright: a
summary asserting a figure the article never gave is low-confidence whatever
the faithfulness model thinks, because that model marks a wrong number
generously - the entity and the relation both survive, and only the fact is
false.
"""

from __future__ import annotations

from typing import Final, NamedTuple

from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.article import Article
from idhazh.contracts.eval_row import BandReason, ConfidenceBand, EvalRow
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary
from idhazh.evals import metrics

_DELTA_PLACES: Final = 6
_UNTITLED: Final = "Untitled item"


class Verdict(NamedTuple):
    """The band and the one thing that explains it.

    Returned together because a page that showed a band from one code path and a
    reason from another would eventually show a reason that is not why.
    """

    band: ConfidenceBand
    reason: BandReason | None


def verdict(
    faithfulness: float | None,
    *,
    unsupported_numbers: int,
    lead_coverage: float,
    hedge_dropped: bool,
    config: EvaluationConfig,
) -> Verdict:
    """The band, and why it is not the top one.

    An unsupported figure forces the bottom band. Nothing else in the row can
    see that defect, so nothing else may outvote it. Missing lead facts and
    dropped hedges cap confidence at medium rather than forcing low.

    A `high` item carries no reason. It has nothing to explain, and copy about
    the absence of a problem is ink a reader cannot act on.

    When both counterweights fail, the missing lead is named. Dropped facts are
    the larger loss: a flattened hedge changes how a sentence reads, and a
    missing lead means the story's who, what and how-much never arrived.
    """
    if unsupported_numbers:
        return Verdict(ConfidenceBand.LOW, BandReason.UNSUPPORTED_NUMBER)
    if faithfulness is None:
        scored, reason = ConfidenceBand.MEDIUM, BandReason.NOT_SCORED
    elif faithfulness >= config.band_high_min:
        scored, reason = ConfidenceBand.HIGH, None
    elif faithfulness >= config.band_medium_min:
        scored, reason = ConfidenceBand.MEDIUM, BandReason.FAITHFULNESS
    else:
        scored, reason = ConfidenceBand.LOW, BandReason.FAITHFULNESS

    if scored is ConfidenceBand.HIGH:
        if lead_coverage < config.lead_coverage_min:
            return Verdict(ConfidenceBand.MEDIUM, BandReason.LEAD_MISSING)
        if hedge_dropped:
            return Verdict(ConfidenceBand.MEDIUM, BandReason.HEDGE_DROPPED)
    return Verdict(scored, reason)


def band(
    faithfulness: float | None,
    *,
    unsupported_numbers: int,
    lead_coverage: float,
    hedge_dropped: bool,
    config: EvaluationConfig,
) -> ConfidenceBand:
    """The band alone, for a caller that has no reader to explain it to."""
    return verdict(
        faithfulness,
        unsupported_numbers=unsupported_numbers,
        lead_coverage=lead_coverage,
        hedge_dropped=hedge_dropped,
        config=config,
    ).band


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

    The two densities take `full_text` alone. They are the only columns that
    score the article rather than the summary, and they are recorded and not
    banded: nothing here knows yet what a normal value looks like.

    `self_repetition` takes the summary alone. It is the only column that reads
    neither the article nor the pair, and it is recorded and not banded for the
    same reason.
    """
    text = summary.summary or ""
    unsupported = metrics.unsupported_numbers(text, full_text)
    coverage = metrics.lead_coverage(text, full_text)
    hedge = metrics.hedge_dropped(text, full_text)
    verbatim = metrics.verbatim_run(text, full_text)
    delta = round(hhem - hhem_full, _DELTA_PLACES)
    truncation_flagged = delta > config.truncation_gap_max or (
        article.brief and verbatim > config.brief_compression_ceiling
    )

    return EvalRow(
        version=EvalRow.schema_version(),
        date=date,
        run_id=run_id,
        item_id=item.item_id,
        url_key=item.url_key,
        source_url=item.canonical_url,
        # The source's headline, not ours. This column exists so a row still
        # identifies its article after the day is pruned from the site, and
        # identity has to be the thing that does not vary: our title is
        # rewritten per run and is absent whenever the rewrite missed its range.
        title=(item.title or article.title or _UNTITLED),
        vertical=item.vertical,
        model_id=summary.model_id,
        attempt=summary.attempt,
        hhem=hhem,
        hhem_full=hhem_full,
        hhem_delta=delta,
        truncation_flagged=truncation_flagged,
        coverage=coverage,
        compression=metrics.compression(text, full_text),
        extractiveness=metrics.extractiveness(text, full_text),
        verbatim_run=verbatim,
        unsupported_numbers=unsupported,
        hedge_dropped=hedge,
        evidential_density=metrics.evidential_density(full_text),
        speculative_density=metrics.speculative_density(full_text),
        self_repetition=metrics.self_repetition(text),
        extraction_suspect=extraction_suspect,
        band=band(
            hhem,
            unsupported_numbers=unsupported,
            lead_coverage=coverage,
            hedge_dropped=hedge,
            config=config,
        ),
        source_word_count=metrics.word_count(full_text),
        source_seen_word_count=article.word_count,
        summary_word_count=metrics.word_count(text),
        pipeline_fingerprint=summary.pipeline_fingerprint,
        output_digest=summary.output_digest,
        determinism_violation=determinism_violation,
        scorer_version=scorer_version,
        scored_at=scored_at,
    )
