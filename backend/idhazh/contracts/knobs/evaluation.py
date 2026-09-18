"""What a summary is scored against, and when a score has drifted far enough to say so."""

from __future__ import annotations

from typing import Any, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, Slug


class EvaluationConfig(Model):
    chunk_words: int = Field(
        default=900,
        ge=1,
        description=(
            "Words of article the faithfulness scorer reads in one window. Attention is "
            "quadratic in the premise, so a whole long article in one pass is the "
            "expensive shape. The default has never been calibrated (Guardrail #10): with no "
            "human labels there is nothing to tune it against, and a sweep would show "
            "only that the number moves. Moving it moves `scorer_version`, which restarts "
            "the run-day count in `evaluation.label_min_run_days`."
        ),
    )
    chunk_overlap_words: int = Field(
        default=150,
        ge=0,
        description=(
            "Words shared between one window and the next, so a claim that straddles a "
            "boundary is still whole somewhere. Must sit below `chunk_words`."
        ),
    )
    band_high_min: float = Field(default=0.80, ge=0.0, le=1.0)
    band_medium_min: float = Field(default=0.50, ge=0.0, le=1.0)
    lead_coverage_min: float = Field(
        default=0.30,
        ge=0.0,
        le=1.0,
        description=(
            "Below this the summary missed the source lead. It caps a high band at "
            "medium rather than forcing low."
        ),
    )
    brief_compression_ceiling: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        description=(
            "Maximum summary/source ratio for a brief item. Also caps verbatim_run on "
            "briefs and derives extract.min_source_words from the first brief ask."
        ),
    )
    verbatim_reject_ceiling: float = Field(
        default=0.75,
        gt=0.0,
        le=1.0,
        description=(
            "Above this share of the summary copied from the source in one unbroken "
            "run, the item is refused rather than published. A starting point and not a "
            "calibrated threshold (Guardrail #10): it is the midpoint of the band left open "
            "by one run-day of eight brief items on 2026-08-26, where seven scored at "
            "or below 0.241 and the eighth scored 1.000, and eight items is not a "
            "distribution. It must sit above brief_compression_ceiling, or the brief "
            "copying gate loses the band it can still fail in."
        ),
    )
    spot_checks_per_week: int = Field(default=10, ge=0)
    labellers: list[Slug] = Field(
        default_factory=list,
        description=(
            "Who may write a faithfulness label. Empty by default, so a fresh clone can "
            "draw the queue and read it but cannot record a verdict. The list is what "
            "keeps a machine out of the label ledger: there is no author field a model "
            "could fill, and adding one would be a schema change with a written reason "
            "(CLAUDE.md section 0a)."
        ),
    )
    label_draw_per_decile: int = Field(
        default=6,
        ge=1,
        description=(
            "Labels drawn from each hhem decile. Uniform, not weighted to the cuts: the "
            "first question is what `high` means at all, and a boundary-weighted draw "
            "cannot answer that."
        ),
    )
    label_min_run_days: int = Field(
        default=10,
        ge=1,
        description=(
            "Distinct run-days at one scorer version before a draw is worth finalising. "
            "A draw over one day is a draw over one day's sources. It is the only "
            "collection requirement: a draw is one pool at one scorer, and the figure "
            "read off it is reported rather than withheld."
        ),
    )
    golden_set_size: int = Field(default=20, ge=1)
    validation_articles: int = Field(
        default=20,
        ge=1,
        description="Golden articles a candidate must be scored on before its mean counts.",
    )
    validation_drop_max: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description=(
            "How far below its leaderboard number the incumbent may land before the "
            "ranking stops being a usable prior and the challengers get scored too."
        ),
    )
    validation_switch_margin: float = Field(
        default=0.05,
        ge=0.0,
        le=1.0,
        description=(
            "How much better a challenger must be on our own corpus to change the pick. "
            "A number, because 'materially diverges' is an argument waiting to happen."
        ),
    )
    qualification_pool_multiple: int = Field(
        default=6,
        ge=1,
        description=(
            "Articles a qualification shard extracts for every one it replays. A floor "
            "on the choice the stratified selection gets, never a cap on the walk: a "
            "shard that has not yet been offered every length tier keeps going through "
            "its slice. Raising it buys fetch seconds, never model minutes, because the "
            "model still sees corpus_per_shard articles - one address measured 2.1 s on "
            "2026-08-26 over 150 of them, against 330 minutes for the job."
        ),
    )
    qualification_min_per_band: int = Field(
        default=3,
        ge=0,
        description=(
            "Articles a qualification corpus aims at in each summarize band. It "
            "describes the measuring stick rather than the candidate, so a corpus "
            "short of it is reported on the verdict and blocks nothing - the gate "
            "that refuses a thin run is scored_denominator, which counts what was "
            "actually scored."
        ),
    )
    qualification_min_over_cap: int = Field(
        default=2,
        ge=0,
        description=(
            "Articles the corpus aims at that are long enough to be truncated. They "
            "are the only ones that exercise the cap at all."
        ),
    )
    qualification_min_brief: int = Field(
        default=2,
        ge=0,
        description=(
            "Articles the corpus aims at that take the brief prompt, which is a "
            "different prompt - a corpus without one says nothing about that path."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _summary_word_bounds_moved_to_the_ladder(cls, data: Any) -> Any:
        """Read a config that still names the old global summary word bounds.

        `summary_words_min` and `summary_words_max` were one pair of integers
        applied to every rung of the ladder, and a reply outside them deleted the
        item. They are gone: the floor is `summarize.length_policy` and the
        ceiling is derived per band. `config/` is a persisted surface and every
        model here forbids unknown keys, so a file written before the move would be
        refused outright (section 11). The old values are dropped rather than
        mapped - neither has a counterpart, and carrying 250 forward as a ceiling
        would reinstate the cap the ladder now sets for itself.
        """
        if not isinstance(data, dict):
            return data
        if not any(name in data for name in ("summary_words_min", "summary_words_max")):
            return data
        migrated = dict(data)
        migrated.pop("summary_words_min", None)
        migrated.pop("summary_words_max", None)
        return migrated

    @model_validator(mode="after")
    def _bands_and_ranges_are_ordered(self) -> Self:
        if self.band_medium_min >= self.band_high_min:
            raise ValueError("band_medium_min must sit below band_high_min")
        # The chunker steps `chunk_words - chunk_overlap_words`. An overlap at or
        # above the window makes that step zero or negative, and the clamp that
        # stops it looping walks a long article one word at a time - a job that
        # never finishes rather than a job that fails.
        if self.chunk_overlap_words >= self.chunk_words:
            raise ValueError("chunk_overlap_words must sit below chunk_words")
        # The reject drops the item before it can be scored, so anything it catches
        # leaves the corpus the brief-copying gate reads. Set the two equal and the
        # gate has no band left to fail in - and it stops failing silently, which
        # reads exactly like a fixed pipeline.
        if self.verbatim_reject_ceiling <= self.brief_compression_ceiling:
            raise ValueError(
                "verbatim_reject_ceiling must sit above brief_compression_ceiling"
            )
        return self


class DriftConfig(Model):
    month_over_month_pct: float = Field(default=10.0, gt=0.0)
    year_over_year_pct: float = Field(default=5.0, gt=0.0)
    quarterly_refresh_fraction: float = Field(default=0.5, gt=0.0, le=1.0)
    min_domain_rows: int = Field(
        default=20,
        ge=2,
        description=(
            "Distinct articles with the required metric on each side of a domain "
            "comparison. A smaller sample is reported as insufficient evidence, "
            "not as drift or as healthy. This is a safety floor, not a confidence level."
        ),
    )
    source_word_count_drop: float = Field(
        default=0.40,
        gt=0.0,
        lt=1.0,
        description="Fractional fall in median extracted article length that raises an alert.",
    )
    extractiveness_rise: float = Field(
        default=0.15,
        gt=0.0,
        le=1.0,
        description="Absolute rise in median copied four-word-phrase share that raises an alert.",
    )
    min_window_rows: int = Field(
        default=20,
        ge=1,
        description=(
            "Rows a window must hold on each side before a comparison of the two "
            "means anything. Below it the review fails instead of reporting no "
            "drift, because an empty window and a healthy one produce the same "
            "empty finding list. Sized against the ledger rather than picked "
            "round: measured 2026-08-30 over the 3,113 rows committed to "
            "state/scores.csv, the lightest full day holds 117 and the heaviest "
            "731, so a seven-day recent window holding under 20 is a stopped "
            "instrument and not a quiet week - 20 is a sixth of one of those days."
        ),
    )
