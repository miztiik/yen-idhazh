"""Compose one item's measurements and faithfulness-only confidence into one ledger row."""

from __future__ import annotations

from typing import Final, NamedTuple

from idhazh.contracts.article import Article
from idhazh.contracts.base import fit_field
from idhazh.contracts.eval_row import BandReason, ConfidenceBand, EvalRow
from idhazh.contracts.knobs.evaluation import EvaluationConfig
from idhazh.contracts.run_plan import PlannedItem
from idhazh.contracts.summary import Summary
from idhazh.evals import embedding_metrics, metrics
from idhazh.evals.embedding_metrics import Encoder
from idhazh.fingerprint import text_digest

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
    config: EvaluationConfig,
) -> Verdict:
    """Grade faithfulness, or explicitly leave an unevaluated item unscored."""
    if faithfulness is None:
        return Verdict(ConfidenceBand.MEDIUM, BandReason.NOT_SCORED)
    if faithfulness >= config.band_high_min:
        return Verdict(ConfidenceBand.HIGH, None)
    if faithfulness >= config.band_medium_min:
        return Verdict(ConfidenceBand.MEDIUM, BandReason.FAITHFULNESS)
    return Verdict(ConfidenceBand.LOW, BandReason.FAITHFULNESS)


def band(
    faithfulness: float | None,
    *,
    config: EvaluationConfig,
) -> ConfidenceBand:
    """The band alone, for a caller that has no reader to explain it to."""
    return verdict(faithfulness, config=config).band


def to_eval_row(
    *,
    item: PlannedItem,
    article: Article,
    summary: Summary,
    full_text: str,
    premise: str,
    hhem: float,
    hhem_full: float,
    config: EvaluationConfig,
    date: str,
    run_id: str,
    scorer_version: str,
    scored_at: str,
    extraction_suspect: bool = False,
    determinism_violation: bool = False,
    encoder: Encoder | None = None,
) -> EvalRow:
    """Everything measured about one item, in the shape the ledger keeps forever.

    `full_text` is the whole article, not the truncated text the model saw. The
    gap between the two faithfulness scores is the cost of truncation, and it is
    invisible unless both are measured.

    `truncation_flagged` is `article.truncated` and nothing else. Extract is the
    only stage that cuts a body, so it is the only stage that knows, and the flag
    now carries that fact rather than inferring it from the gap. The gap stays,
    under its own two columns: it answers what the cut cost, which is a different
    question and needs a threshold nothing has measured yet.

    `premise` is the text the faithfulness scorer was handed as `seen_text` - the
    article after sanitizing and truncation - and it is digested, never stored.
    It is a parameter rather than something read back off `article` on purpose:
    the caller passes the one variable it also passed the scorer, so a later
    change that scores something else cannot leave the digest quietly naming the
    text the scorer used to read.

    The two densities take `full_text` alone. They are the only columns that
    score the article rather than the summary, and they are recorded and not
    banded: nothing here knows yet what a normal value looks like.

    `self_repetition` takes the summary alone. It is the only column that reads
    neither the article nor the pair, and it is recorded and not banded for the
    same reason.

    `encoder` is the one model this function touches, and it is optional: a
    caller with no encoder in hand records a null `coherence` and every other
    column exactly as before. The work shard is the only production caller and
    it is where the row is composed, so that is where the encoder is loaded -
    the jobs that hold it already only ever read this row back
    (`docs/concepts/evaluation.md`).

    `source_words_before_cap` and `source_words` both come off `article`,
    never off a text this function counts for itself. They are a before-the-cap
    and after-the-cap pair, and a pair is only readable when one counter
    produced both numbers. The full count is None when it is not knowable, and
    `EvalRow` refuses a row where the seen count is the larger of the two.
    """
    text = summary.summary or ""
    unsupported = metrics.unsupported_numbers(text, full_text)
    hedge = metrics.hedge_dropped(text, full_text)
    verbatim = metrics.verbatim_run(text, full_text)
    # An article payload written before extract recorded the pre-cap length knows
    # its own full length only when nothing was cut. Otherwise it stays None: the
    # post-cap count would say the article was exactly as long as the part we read.
    source_words = article.source_word_count
    if source_words is None and not article.truncated:
        source_words = article.word_count
    delta = round(hhem - hhem_full, _DELTA_PLACES)

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
        # Fitted, because a headline is a stranger's text: it arrives with the
        # length, the punctuation and the script the page chose, and this column
        # has its own opinion about all three.
        title=fit_field(
            item.title or article.title or _UNTITLED,
            model=EvalRow,
            field="title",
            absent=_UNTITLED,
        ),
        vertical=item.vertical,
        model_id=summary.model_id,
        summary_attempt=summary.attempt,
        hhem=hhem,
        hhem_full=hhem_full,
        hhem_delta=delta,
        truncation_flagged=article.truncated,
        compression=metrics.compression(text, full_text),
        extractiveness=metrics.extractiveness(text, full_text),
        verbatim_run=verbatim,
        unsupported_numbers=unsupported,
        hedge_dropped=hedge,
        evidential_density=metrics.evidential_density(full_text),
        speculative_density=metrics.speculative_density(full_text),
        self_repetition=metrics.self_repetition(text),
        coherence=(
            embedding_metrics.coherence(text, encoder=encoder) if encoder is not None else None
        ),
        semantic_coverage=metrics.semantic_coverage(text, full_text),
        extraction_suspect=extraction_suspect,
        band=band(hhem, config=config),
        source_words_before_cap=source_words,
        source_words=article.word_count,
        summary_words=metrics.word_count(text),
        output_digest=summary.output_digest,
        source_digest=text_digest(premise),
        determinism_violation=determinism_violation,
        scorer_version=scorer_version,
        scored_at=scored_at,
    )
