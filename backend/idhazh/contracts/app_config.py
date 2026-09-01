"""The tunable knobs (`config/idhazh.json`).

A knob is something a reasonable operator might want set differently without
changing a fact. The runner's own ceilings - 4 vCPU, the 6 h job cap, the 10 GB
cache, the 1 GB published site - are deliberately absent: they are properties of
the platform, and making them editable would invite raising the budget instead
of simplifying the feature (Rule #2).

Every knob ships a sane default, so a fresh clone runs unconfigured.
"""

from __future__ import annotations

import math
from enum import StrEnum
from typing import ClassVar, Literal, Self

from pydantic import Field, field_validator, model_validator

from idhazh.contracts.base import ChangelogEntry, CommitSha, Contract, Model, Sha256, Slug
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.route import VisualKind


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ModelRef(Model):
    """Which weights, from where. Per-item payloads carry only the `id`."""

    id: Slug
    repo: str = Field(min_length=1, description="Hugging Face repository the GGUF is pulled from.")
    revision: CommitSha | None = Field(
        default=None,
        description=(
            "The hub commit the weights are fetched at. A download that names a branch "
            "gets whatever was uploaded last, so the bytes can change under a config "
            "that still records the old sha256."
        ),
    )
    file: str = Field(min_length=1)
    quantisation: str = Field(min_length=1)
    sha256: Sha256 | None = Field(
        default=None,
        description="Recorded once measured. A weight that changes silently changes every output.",
    )
    hf_base_repo: str | None = Field(
        default=None,
        min_length=1,
        description=(
            "The safetensors repository a fine-tune trains against, when this entry "
            "names a GGUF conversion of somebody else's weights. It sits here rather "
            "than in `finetune` because the two strings describe the same model: held "
            "apart, a model swap moves one and leaves the other, and a LoRA adapter "
            "loads onto a mismatched base without raising. Optional - only an entry we "
            "intend to fine-tune needs it."
        ),
    )


class TierWeights(Model):
    """The ranking weight of a source tier. Tier 1 is the institution that IS the fact."""

    institution: float = Field(default=1.0, ge=0.0, le=1.0)
    trade_press: float = Field(default=0.6, ge=0.0, le=1.0)
    community: float = Field(default=0.3, ge=0.0, le=1.0)


class RunConfig(Model):
    safety_ceiling_per_run: int = Field(
        default=160,
        ge=1,
        description=(
            "What sizes a run. It began as a crash guard against a mis-parsed feed and "
            "supply overtook it: items_planned has been exactly this number on every run "
            "since 2026-08-25, so it is the cap whatever it is called. Owner decision, "
            "2026-08-29: it stays at 160, and a run gets better by spending those slots "
            "on articles that can be read rather than by raising this. It is also what "
            "sizes the worst case a work shard and the route stage have to finish, so "
            "any new number is bounded by the slower of those two - and a worker killed "
            "at run.shard_timeout_minutes uploads nothing."
        ),
    )
    shard_size: int = Field(
        default=5,
        ge=1,
        description="URLs per worker VM. Set by measured model-load amortization, not by taste.",
    )
    max_parallel: int = Field(
        default=4,
        ge=1,
        description=(
            "The most workers a run may derive for itself. It is four rather than the "
            "eight digest.yml lets an operator dispatch, because eight has never "
            "published a day; the three conditions that would move it are in "
            "docs/reference/measurements.md."
        ),
    )
    shard_timeout_minutes: int = Field(
        default=150,
        ge=1,
        description=(
            "The work job's own timeout, which digest.yml reads from here. A backstop, "
            "never a budget: a worker has no clock of its own, and one killed at this "
            "bound uploads nothing, so the run loses every item that worker held. Sized "
            "at half again the slowest worker measured at run.safety_ceiling_per_run - "
            "94.5 minutes on 2026-08-26 - and it still clears the 117.5-minute worst of "
            "2026-08-24, when a day handed a worker 50 items instead of 40. A slow "
            "worker is answered by lowering the ceiling, never by raising this "
            "(Rule #2)."
        ),
    )
    route_budget_minutes: int = Field(
        default=40,
        ge=1,
        description=(
            "What the route stage may spend before it stops asking the model and leaves "
            "the rest of the day unrouted. Sized below the job's own timeout, not equal "
            "to it: a job killed at its bound uploads no artifact, so the whole hour's "
            "decisions are lost rather than the tail it could not reach."
        ),
    )
    success_floor_pct: int = Field(
        default=70, ge=0, le=100, description="Below this, the run additionally opens an issue."
    )


class CollectConfig(Model):
    quarantine_after_failures: int = Field(default=5, ge=1)
    watchlist_max_entities: int = Field(default=30, ge=1)
    settled_failure_codes: tuple[FailureCode, ...] = Field(
        default=(
            FailureCode.ROBOTS_DENIED,
            FailureCode.ROBOTS_UNREACHABLE,
            FailureCode.BLOCKED_ADDRESS,
            FailureCode.HTTP_CLIENT_ERROR,
            FailureCode.PAYWALLED,
            FailureCode.NO_TEXT,
            FailureCode.NOT_PROSE,
            FailureCode.BOILERPLATE,
            FailureCode.TOO_SHORT,
            FailureCode.UNSUPPORTED_FORM,
        ),
        description=(
            "Failure codes that will not change before tomorrow. An address that failed "
            "today with one of these is not planned again today. A paywall, a robots "
            "rule and a 404 are the same answer at 02:20 and at 18:20; a rate limit, a "
            "reset connection and an unreachable model are not, so they are absent and "
            "a later run retries them. Empty means retry everything, which is what the "
            "pipeline did before 2026-08-29."
        ),
    )
    max_per_source: int = Field(
        default=2,
        ge=1,
        description=(
            "Most items one feed may contribute to one vertical in a day. Without it, a "
            "quiet news day is whichever blog published most."
        ),
    )
    max_source_share_per_day: float = Field(
        default=0.05,
        gt=0.0,
        le=1.0,
        description=(
            "Most of one day one feed may hold, counting every desk and every run. "
            "max_per_source bounds a count inside one desk in one run, and a feed sits "
            "on one desk, so what a feed can hold of a whole day is that count times "
            "the runs the day had - a fixed number whose share moves with the day's "
            "size. Measured 2026-08-31 over the eleven committed days, the most one "
            "feed ever held was 10 items, which is 2.32 percent of the 431-item day of "
            "2026-08-30 and 25 percent of the four-item day of 2026-08-21. The default "
            "is above the largest full-day share by a factor of two, so it displaces "
            "nothing that has ever been published; it bounds the thin day, where a "
            "fixed count of ten is a quarter of the page. It is never tighter than "
            "max_per_source for one desk in one run - a day ceiling below that would "
            "tighten the per-desk rule, which is a different decision and was refused."
        ),
    )
    tier_weights: TierWeights = Field(default_factory=TierWeights)
    repetition_weight: float = Field(default=1.0, ge=0.0)
    watchlist_bonus: float = Field(default=0.5, ge=0.0)
    front_page_bonus: float = Field(default=0.4, ge=0.0)
    recency_weight: float = Field(
        default=0.6,
        ge=0.0,
        description=(
            "How much freshness may move a score, inside the window max_age_hours "
            "allows. It orders what is already fresh enough to publish; it is "
            "max_age_hours, not this, that decides what is too old to add at all."
        ),
    )
    recency_half_life_hours: float = Field(
        default=18.0,
        gt=0.0,
        description=("Hours for the recency bonus to halve. At 18 h a day-old item keeps a third."),
    )
    max_age_hours: float = Field(
        default=24.0,
        gt=0.0,
        description=(
            "How old a story may be and still be added. A hard gate, applied to the "
            "date we believe rather than the date the feed claimed. An article we "
            "could not date at all is not too old - first sight is its age, so it "
            "gets the day we found it and no more."
        ),
    )
    max_future_hours: float = Field(
        default=6.0,
        ge=0.0,
        description=(
            "A publish date further ahead than this is not believed and the item falls "
            "back to first sight. Feeds that stamp tomorrow would otherwise take the "
            "top slot every single day."
        ),
    )
    seen_window_days: int = Field(
        default=90,
        ge=1,
        description=(
            "How far back the first-sight store is consulted. Older shards stay "
            "committed and readable; they are just not evidence about today."
        ),
    )
    blocked_url_markers: list[str] = Field(
        default_factory=list,
        description=(
            "Case-insensitive substrings of a canonical address that never enter the "
            "pool. For the promotional page a working news feed syndicates: an affiliate "
            "product review is short declarative prose, so it is trivially entailed and "
            "no faithfulness threshold detects it at any cut. Empty by default - the "
            "entries are a source list and live in config/ (Rule #6)."
        ),
    )


class ExtractConfig(Model):
    truncation_cap_tokens: int = Field(
        default=2500,
        ge=256,
        description="A performance lever, not only a safety cap: prefill degrades with length.",
    )
    min_source_words: int = Field(
        default=60,
        ge=1,
        description=(
            "Below this the item publishes through the brief tier. It is derived in "
            "AppConfig from summarize.bands[0].target_words_min divided by "
            "evaluation.brief_compression_ceiling."
        ),
    )
    prose_sentence_min: int = Field(
        default=3,
        ge=1,
        description="Sentences of prose needed before a page stops carrying the not_prose signal.",
    )
    prose_sentence_words_min: int = Field(
        default=8,
        ge=1,
        description="Words a sentence needs before it counts as prose for the shape signal.",
    )
    prose_line_count_min: int = Field(
        default=12,
        ge=1,
        description="Lines needed before the line-shape guard runs.",
    )
    prose_line_ratio_min: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Minimum share of lines that must look like prose on a line-heavy page.",
    )
    reject_not_prose: bool = Field(
        default=False,
        description="If true, a not_prose signal rejects the item. Default records and publishes.",
    )
    reject_boilerplate: bool = Field(
        default=False,
        description=(
            "If true, a boilerplate signal rejects the item. Default records and publishes."
        ),
    )
    boilerplate_ratio_max: float = Field(
        default=0.4,
        gt=0.0,
        le=1.0,
        description="Share of an item's lines also seen on sibling items from the same host.",
    )
    paywall_markers: list[str] = Field(
        default_factory=lambda: [
            "isaccessibleforfree\":false",
            "isaccessibleforfree\": false",
            "subscribe to continue reading",
            "register or subscribe to continue",
        ],
        min_length=1,
        description=(
            "Fallback markers used only when publisher JSON-LD does not declare the paywall."
        ),
    )
    max_body_bytes: int = Field(default=2_000_000, ge=1024)
    max_retries: int = Field(default=3, ge=0)
    backoff_initial_seconds: float = Field(default=1.0, ge=0.0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    request_timeout_seconds: float = Field(default=20.0, gt=0.0)
    user_agent: str = Field(default="yen-idhazh/1.0 (+https://github.com/miztiik/yen-idhazh)")


class InferenceConfig(Model):
    """Decoding is pinned here so a change of output is a reviewable diff."""

    n_ctx: int = Field(default=8192, ge=512)
    n_threads: int = Field(default=4, ge=1)
    n_batch: int = Field(default=512, ge=1)
    n_ubatch: int = Field(default=512, ge=1)
    n_parallel: int | None = Field(
        default=None,
        ge=1,
        description="llama-server -np. None omits the flag and keeps the runtime default.",
    )
    n_threads_batch: int | None = Field(
        default=None,
        ge=1,
        description="llama-server -tb. None omits the flag and lets it follow n_threads.",
    )
    startup_warmup: bool = Field(
        default=True,
        description="If false, emit --no-warmup. True lets llama-server warm at startup.",
    )
    metrics: bool = Field(
        default=True,
        description=(
            "If true, emit --metrics and llama-server serves its counters on "
            "/metrics. On by default: without them a run cannot say how close it came "
            "to n_ctx, and a concurrency result has no busy-slot number to read it by."
        ),
    )
    flash_attention: Literal["on", "off"] | None = Field(
        default=None,
        description="llama-server -fa. None omits the flag and leaves the runtime on auto.",
    )
    load_mode: Literal["mmap+mlock"] | None = Field(
        default=None,
        description="llama-server -lm. None omits the flag and keeps the runtime default.",
    )
    cache_type_k: Literal["q8_0"] | None = Field(
        default=None,
        description="llama-server -ctk. None omits the flag and keeps full-precision KV.",
    )
    cache_type_v: Literal["q8_0"] | None = Field(
        default=None,
        description="llama-server -ctv. None omits the flag and keeps full-precision KV.",
    )
    priority: int | None = Field(
        default=None,
        ge=-1,
        le=3,
        description="llama-server --prio. None omits the flag and keeps normal priority.",
    )
    poll: int | None = Field(
        default=None,
        ge=0,
        description="llama-server --poll. None omits the flag and keeps the runtime default.",
    )
    temperature: float = Field(default=0.0, ge=0.0)
    top_p: float = Field(default=1.0, gt=0.0, le=1.0)
    seed: int = Field(
        default=0,
        description="Dead code under greedy decoding. Never cited as the determinism control.",
    )
    thinking: bool = Field(
        default=False,
        description="Off. Reasoning measurably increases hallucination when summarizing.",
    )
    max_output_tokens: int = Field(
        default=900,
        ge=1,
        description=(
            "A crash guard, not a length target. The prompt sets the length; this only "
            "stops a runaway decode from burning a shard's whole timeout. Sized at 250 "
            "the reply ran out of budget mid-object and failed as a shape error, which "
            "named the wrong cause - so it is set well above any summary we want."
        ),
    )
    request_timeout_minutes: float = Field(
        default=22.1,
        gt=0.0,
        description=(
            "One summarizer POST may wait this long. Sized from the measured worst "
            "8B long article plus one cold prompt prefix, doubled; the shard timeout "
            "remains the outer bound."
        ),
    )


class ModelsConfig(Model):
    summarize: ModelRef
    route: ModelRef
    inference: InferenceConfig = Field(default_factory=InferenceConfig)


class SummaryBand(Model):
    """How long a summary to ask for, once the article is at least this long."""

    min_source_words: int = Field(
        ge=0, description="The band applies to articles this long and longer."
    )
    target_words_min: int = Field(ge=1, description="The shortest summary the prompt asks for.")
    target_words_max: int = Field(ge=1, description="The longest summary the prompt asks for.")

    @model_validator(mode="after")
    def _the_range_is_ordered(self) -> Self:
        if self.target_words_min >= self.target_words_max:
            raise ValueError("target_words_min must sit below target_words_max")
        return self


def _default_bands() -> list[SummaryBand]:
    """Five sizes: the note, the report, the feature, the long feature, the investigation.

    Starting points chosen from the shape of the sources we collect, not
    measurements - nothing here may be quoted as one (Rule #10). The first
    band begins at zero so every article lands in one, and the shortest ask sits
    above `evaluation.summary_words_min` so a summary that misses low by a few
    words is still publishable.

    The last floor is the last one there may ever be. It stays below
    `int(extract.truncation_cap_tokens / extract.TOKENS_PER_WORD)`, so no rung
    asks for a summary of words the model was never handed
    (`docs/architecture/summarize/prompt.md`).
    """
    return [
        SummaryBand(min_source_words=0, target_words_min=30, target_words_max=45),
        SummaryBand(min_source_words=60, target_words_min=50, target_words_max=90),
        SummaryBand(min_source_words=700, target_words_min=70, target_words_max=150),
        SummaryBand(min_source_words=2000, target_words_min=110, target_words_max=200),
        SummaryBand(min_source_words=3000, target_words_min=150, target_words_max=230),
    ]


class SummarizeConfig(Model):
    """What the prompt asks the model for.

    Separate from `evaluation`, which is what the pipeline agrees to accept. The
    two ranges are deliberately different: a prompt is a request and a gate is a
    rule, and asking for a tighter range than we enforce is what stops a
    two-word miss from losing a story. `AppConfig` checks the invariant that
    actually matters - every ask sits inside the gate - because only there are
    both blocks visible.

    Every value here is substituted into the prompt text at render time, so the
    prompt cannot drift from the bounds the pipeline enforces (Rule #6).
    """

    bands: list[SummaryBand] = Field(
        default_factory=_default_bands,
        min_length=1,
        description=(
            "One length ask per article size, ordered by min_source_words. A release "
            "note and a long read asked for the same range gives a padded summary of "
            "the first and a thin one of the second."
        ),
    )
    key_points_min: int = Field(
        default=2,
        ge=1,
        description=(
            "Also the decoder's floor. The prompt and the response schema read this same "
            "number, or the decoder rejects a reply that did exactly what was asked."
        ),
    )
    key_points_max: int = Field(default=5, ge=1, description="Also the decoder's ceiling.")
    title_words_min: int = Field(
        default=6,
        ge=1,
        description=(
            "Shortest title the prompt asks for. Below this a headline stops naming "
            "who did what, and the reader is back to guessing from the source's own "
            "framing."
        ),
    )
    title_words_max: int = Field(
        default=14,
        ge=1,
        le=40,
        description=(
            "Longest title the prompt asks for, and the decoder's ceiling. Unlike the "
            "summary there is no floor on the decoder: a headline does not stop early, "
            "and a floor would only pad a good short one. Capped at 40 so the widest "
            "decoder ceiling this can produce still fits an UntrustedLine, which is "
            "what the payload field is."
        ),
    )
    max_verbatim_words: int = Field(
        default=20,
        ge=1,
        description=(
            "Longest quotation the prompt allows, and it must be attributed. Long "
            "enough to carry a real sentence somebody said, short enough that a summary "
            "cannot become the article. The ledger measures the run that actually came "
            "back (`verbatim_run`), so this number is the ask and that column is the "
            "answer."
        ),
    )

    @model_validator(mode="after")
    def _the_bands_cover_every_article(self) -> Self:
        if self.bands[0].min_source_words != 0:
            raise ValueError("the first band must start at zero, or a short article has no band")
        starts = [band.min_source_words for band in self.bands]
        if starts != sorted(set(starts)):
            raise ValueError("bands must climb, and no two may start at the same length")
        if self.key_points_min > self.key_points_max:
            raise ValueError("key_points_min must not exceed key_points_max")
        if self.title_words_min > self.title_words_max:
            raise ValueError("title_words_min must not exceed title_words_max")
        return self

    def band_for(self, source_words: int) -> SummaryBand:
        """The longest band the article reaches. Total, because band one starts at zero."""
        chosen = self.bands[0]
        for band in self.bands:
            if source_words >= band.min_source_words:
                chosen = band
        return chosen


class EvaluationConfig(Model):
    chunk_words: int = Field(
        default=900,
        ge=1,
        description=(
            "Words of article the faithfulness scorer reads in one window. Attention is "
            "quadratic in the premise, so a whole long article in one pass is the "
            "expensive shape. The default has never been calibrated (Rule #10): with no "
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
    summary_words_min: int = Field(
        default=25,
        ge=1,
        description=(
            "Below this it is a headline, not a summary. Set under the lowest band in "
            "`summarize.bands`: the prompt is a request, and dropping an item for missing "
            "it by two words loses a story to a rounding error."
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
    summary_words_max: int = Field(
        default=250, ge=1, description="Above this it is a copy. Absolute, not a ratio."
    )
    verbatim_reject_ceiling: float = Field(
        default=0.75,
        gt=0.0,
        le=1.0,
        description=(
            "Above this share of the summary copied from the source in one unbroken "
            "run, the item is refused rather than published. A starting point and not a "
            "calibrated threshold (Rule #10): it is the midpoint of the band left open "
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
            "A draw over one day is a draw over one day's sources. The pipeline "
            "fingerprint is reported per stratum rather than required to hold still: "
            "requiring both made the gate unreachable, and no pair has ever held for "
            "more than three consecutive run-days."
        ),
    )
    label_min_stratum_rows: int = Field(
        default=20,
        ge=1,
        description=(
            "Rows one pipeline must contribute to a draw before a result read off that "
            "stratum may move a threshold. Below it the stratum is printed and marked "
            "too thin to cut on, because a rate over a handful of rows from one producer "
            "is noise wearing a decimal point (Rule #10)."
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

    @model_validator(mode="after")
    def _bands_and_ranges_are_ordered(self) -> Self:
        if self.band_medium_min >= self.band_high_min:
            raise ValueError("band_medium_min must sit below band_high_min")
        if self.summary_words_min >= self.summary_words_max:
            raise ValueError("summary_words_min must sit below summary_words_max")
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


class RetentionConfig(Model):
    """Ships disabled. A default is a promise, not a placeholder."""

    image_months: int = Field(
        default=-1, ge=-1, description="-1 disables pruning entirely. Age-based only, never size."
    )
    dry_run: bool = True
    max_deletes_per_run: int = Field(
        default=200,
        ge=0,
        description="The fuse. An off-by-one in a date parse must not eat the archive.",
    )
    site_budget_mb: int = Field(
        default=800,
        ge=1,
        description=(
            "Logs a warning above this, and does nothing else: it never fails a build "
            "and never deletes. Sized in days of warning, not in round numbers. It sits "
            "224 MB below the platform's 1 GB ceiling, which is 26 days of warning at "
            "the fastest growth this project has measured (a PNG on every item, "
            "8,537 KB/day, 2026-08-23), against a 14-day target. The target is a "
            "judgement about one maintainer acting on one warning, not a measurement "
            "(Rule #10). The arithmetic and its inputs are in "
            "docs/reference/measurements.md, 'Where the alarm fires, and what it buys'."
        ),
    )


class LoggingConfig(Model):
    level: LogLevel = LogLevel.INFO


class ObservabilityConfig(Model):
    """What the pipeline records about itself, and what an operator may switch off.

    Four switches rather than one master switch. Collection, scoring, publishing
    and tracing fail in different ways and a reader has to behave differently
    for each of them, so one switch would leave nobody able to say which
    instrument went dark.

    **The item-health census is not on this list and must never be added to it.**
    Every rate this project publishes divides by that census, so switching it off
    would not thin a measurement - it would make every other measurement
    unreadable. A rate printed without its denominator beside it is the exact
    defect the census exists to prevent.

    An instrument that did not run writes an EMPTY cell, never a zero. A switch
    here decides whether a row is written at all; it never changes the shape of a
    row, so a month file stays readable across a day somebody turned something
    off.
    """

    evaluation_enabled: bool = Field(
        default=True,
        description=(
            "Whether the faithfulness scorer runs. False writes no row to "
            "state/scores.csv, so for those days the eval dashboard and the console's "
            "score panels list nothing and each item bands from the model-free "
            "counterweights instead. The digest still publishes. `--no-faithfulness` "
            "is the same switch for one invocation and overrides this; no flag turns "
            "it back on. It governs the daily pipeline's work stage only: `validate` "
            "and `qualify` are asked for by hand and each refuses outright without a "
            "scorer, so a standing switch cannot silence them into measuring nothing. "
            "Every run records the state of this switch on its run manifest."
        ),
    )
    telemetry_publish: bool = Field(
        default=True,
        description=(
            "Whether a run copies its item-health rows into "
            "frontend/public/telemetry/<YYYY-MM>.csv. False leaves that month file at "
            "whatever the last publishing run wrote, so every console chart ends on "
            "that date and the page says which day it read to. Nothing is lost: "
            "state/item-health/ still holds every row, so switching it back on "
            "republishes the gap."
        ),
    )
    runtime_counters_scrape: bool = Field(
        default=True,
        description=(
            "Whether a work shard reads llama-server's GET /metrics before it stops "
            "the server. False writes no row to state/runtime-counters.csv for that "
            "shard, so context headroom, reading against writing, cache hits and the "
            "shard clock all read as ABSENT for the run rather than as zero. Nothing "
            "else about the run changes - the counters are read after the last item "
            "is summarized."
        ),
    )
    sample_rate: float = Field(
        default=1.0,
        gt=0.0,
        le=1.0,
        description=(
            "The fraction of RUNS whose scorer runs - never the fraction of items. A "
            "run scores every item or none, so a day's rows are never a partial "
            "sample of that day and a per-day rate stays honest. Below 1.0 most days "
            "write no eval row and the console's score panels thin to the sampled "
            "days. Not a switch: `evaluation_enabled` is the way to say off, and a "
            "rate of zero is refused so the two can never disagree about it. The draw "
            "is a digest of the run id, so it is reproducible from the committed "
            "manifest and blind to the run's content, and both the rate and the draw "
            "land on the run manifest whether or not the run was taken. A published "
            "rate is still computed from the item-health census, which is never "
            "sampled; the thinned ledger publishes distributions only."
        ),
    )
    tracing_enabled: bool = Field(
        default=False,
        description=(
            "Whether a work shard builds a span tree. The only switch here that is "
            "OFF unconfigured, because it is the only instrument nothing reads: no "
            "page renders a span, no gate consults one, and the ledgers stay the "
            "record. It buys a developer the nesting a flat row cannot carry - the "
            "robots read inside the fetch, the prompt render and the reply parse "
            "either side of the model call. True writes one JSON line per span under "
            "backend/var/traces/, which is gitignored and published nowhere. A host "
            "is opt-in on top of that, through LANGFUSE_HOST with its key pair, and "
            "CI names none - so an ordinary run reaches no third party whatever this "
            "says."
        ),
    )
    keep_months: int = Field(
        default=13,
        ge=1,
        description=(
            "How many months of ledger stay at full grain before a month is "
            "downsampled to one row per (date, stage). Past this point a reader loses "
            "the per-item detail - the console's failure list offers no rows for those "
            "months - and keeps every daily total, so a year-over-year comparison "
            "still works. Thirteen, so a whole year plus the month being written is "
            "always readable in full."
        ),
    )
    hard_delete_after_months: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Months after which a downsampled month file is removed outright. Null "
            "means never, and never is the default: console.max_window_days is 366, so "
            "a shard has to stay readable for a year, and an aggregate costs about "
            "219 KB a year. Set it and a window reaching past it shows nothing for "
            "those days rather than a thinner series. It must sit above keep_months, "
            "or a month would be deleted before it was ever downsampled."
        ),
    )
    cost_currency: str = Field(
        default="USD",
        pattern=r"^[A-Z]{3}$",
        description=(
            "The currency the console prints the counterfactual cost in, as an ISO "
            "4217 code. Named rather than assumed: a bare number with a symbol in "
            "front of it is the shape a bill takes, and this figure is not a bill."
        ),
    )
    cost_input_per_million: float = Field(
        default=0.20,
        ge=0.0,
        description=(
            "What a hosted provider would charge for a million PROMPT tokens, in "
            "cost_currency. Priced apart from output because a provider prices them "
            "apart - output usually runs three to five times input - and one blended "
            "rate would understate a run that wrote a lot and overstate one that read "
            "a lot. This is the operator's number to set: nothing bills us, so the "
            "committed value is a documented starting point rather than a measurement "
            "(CLAUDE.md Rule #10's one carve-out). The console prints the rate it "
            "used and says whether it came from here or from the operator, and it "
            "labels the result a counterfactual - what the run would have cost "
            "elsewhere - never an amount owed."
        ),
    )
    cost_output_per_million: float = Field(
        default=0.60,
        ge=0.0,
        description=(
            "What a hosted provider would charge for a million GENERATED tokens, in "
            "cost_currency. Same standing as cost_input_per_million: a documented "
            "starting point the operator sets, never a bill. Zero is allowed and "
            "means free rather than unknown, so a rate nobody has chosen is the "
            "committed default and not an empty cell."
        ),
    )

    @model_validator(mode="after")
    def _the_two_thresholds_are_ordered(self) -> Self:
        if (
            self.hard_delete_after_months is not None
            and self.hard_delete_after_months <= self.keep_months
        ):
            raise ValueError(
                "observability.hard_delete_after_months must sit above keep_months, "
                "or a month is deleted before it is ever downsampled"
            )
        return self


class FinetuneConfig(Model):
    """The training corpus and the schedules that maintain it.

    Nothing here runs on the runner. Training needs a GPU and the runner has
    none (section 0a), so these knobs size a file CI commits and a notebook
    somewhere else reads. The two model fields name a KEY in `models` rather
    than a model, because `models.summarize` has already moved once and a knob
    that spells a model name is stale the day the config moves.

    The prune knobs live here and not in `retention`. That block is about
    published-site images and its own `site_budget_mb`; putting corpus history
    under the same name would file two unrelated retention policies together.
    """

    teacher: Slug = Field(
        default="summarize",
        description="A key in `models`. The model whose outputs a session fine-tunes.",
    )
    student: Slug = Field(
        default="route",
        description="A key in `models`. The smaller model a distillation session trains.",
    )
    corpus_rows: int = Field(
        default=2000,
        ge=1,
        description=(
            "The window: how many rows `corpus/corpus.jsonl` holds. It costs storage and "
            "git history only - 2.9 KB compressed per row, measured 2026-08-27 over 2,459 "
            "scored rows and the 114 published items of that day - and it buys a bigger "
            "pool to sample a diverse session from."
        ),
    )
    train_rows: int = Field(
        default=1000,
        ge=1,
        description=(
            "The sample: how many rows one session draws from the window. A CEILING, not "
            "a demand - a session takes the lesser of this and what is left once the "
            "holdout is removed, and prints both numbers. It costs GPU hours rather than "
            "storage: estimated 1.8 h for 1000 rows over 2 epochs on a free T4, and no "
            "training job has run here yet, so that is an estimate (Rule #10)."
        ),
    )
    min_rows: int = Field(
        default=500,
        ge=1,
        description="Below this the corpus trains nothing, and a repair refuses to cut further.",
    )
    harvest_every_days: int = Field(
        default=7,
        ge=1,
        description=(
            "How often the digest run harvests. A number and not a cron line: standard "
            "5-field cron has no every-N-days field, and `on.schedule` is parsed before "
            "any step runs, so no value in config can ever reach it. The step wakes with "
            "the daily run, reads `harvested_at` from the committed meta file and decides "
            "for itself, which also means a missed day self-corrects on the next wake."
        ),
    )
    prune_every_days: int = Field(
        default=30,
        ge=1,
        description=(
            "How often `prune.yml` fires. Each firing costs one force-push of `main` - "
            "the single exception CLAUDE.md section 8 carries, and the reason it carries "
            "one is that git history is append-only, so deleting a corpus row does not "
            "delete its bytes."
        ),
    )
    prune_keep_days: int = Field(
        default=60,
        ge=1,
        description=(
            "Where the squash boundary sits. Retention is this number, full stop, and it "
            "is not a multiple of anything. At 30 and 60 the history holds 60 to 90 days "
            "of commits - 9 to 13 weekly harvests, 25 MB to 38 MB, flat forever. Two whole "
            "datasets survive any squash for free, because the boundary commit holds a "
            "complete copy of the corpus and so does the tip."
        ),
    )
    holdout_days: int = Field(
        default=14,
        ge=1,
        description=(
            "The trailing days held out of training, by date and never at random. "
            "Production always runs on tomorrow's news; a random split puts the same "
            "story from three feeds on both sides and reports memorisation as success. "
            "It has to be shorter than the window has existed, or the split holds out "
            "every row and leaves nothing to train on."
        ),
    )
    reference_rows: int = Field(
        default=500,
        ge=1,
        description=(
            "How many ideal summaries the hand-authored reference set aims to hold. "
            "The set is authored in slices and is usable before it is full, so this is "
            "a target rather than a floor - nothing refuses to run below it."
        ),
    )
    reference_test_rows: int = Field(
        default=100,
        ge=1,
        description=(
            "How many of `reference_rows` are held back as test references and read "
            "line by line by a person. The rest are drafted with an expert model in an "
            "editor. Two numbers because they carry two standards and two costs: a "
            "drafted row is about two minutes, a read row about five, so this knob is "
            "the one that decides how many hours the set takes."
        ),
    )
    epochs: int = Field(default=2, ge=1)
    sequence_length: int = Field(
        default=8192,
        ge=1,
        description=(
            "Measured worst case, rounded up to a power of two: the system prompt is 920 "
            "tokens, a user turn carrying an article at extract.truncation_cap_tokens "
            "(5,000) measures 5,335 with its fence and instructions, and the output "
            "budget is 900 - so 7,155. 7168 clears that by 13 tokens, which is not a "
            "margin. A row longer than this is truncated in training with no error, "
            "which teaches the model to stop mid-summary."
        ),
    )

    @model_validator(mode="after")
    def _a_session_cannot_draw_more_than_the_window_holds(self) -> Self:
        if self.train_rows > self.corpus_rows:
            raise ValueError("finetune.train_rows cannot exceed finetune.corpus_rows")
        if self.min_rows > self.corpus_rows:
            raise ValueError("finetune.min_rows cannot exceed finetune.corpus_rows")
        if self.reference_test_rows >= self.reference_rows:
            raise ValueError(
                "finetune.reference_test_rows must leave rows to train on, "
                "so it is less than finetune.reference_rows"
            )
        return self


class VisualsConfig(Model):
    """Routing and rendering knobs. "Nothing" is the common answer, by design.

    `enabled_kinds` is the gate that keeps an unbuilt renderer unreachable. The
    four-way enum lives in the contract because a payload must be able to say
    `image`; the router may only choose a kind whose renderer exists, so turning
    one on is a config edit rather than a code change.
    """

    enabled_kinds: list[VisualKind] = Field(
        default_factory=lambda: [VisualKind.CHART],
        description=(
            "Kinds the router may choose. `none` is always available and never listed. "
            "Diagram ships off: the model drafted it zero times in 88 items and rendered "
            "it zero times in 703 (ubuntu-latest, 2026-08-24/25), while its presence made "
            "the router's own pre-filter unfireable, because a diagram's steps come from "
            "prose and nothing about it is decidable in advance. The renderer is built and "
            "tested; turning the arm back on is this one word."
        ),
    )
    min_chart_points: int = Field(
        default=3,
        ge=2,
        description="Below this a chart says less than the sentence it sits under.",
    )
    max_chart_points: int = Field(default=8, ge=2)
    min_diagram_steps: int = Field(default=3, ge=2)
    max_diagram_steps: int = Field(default=6, ge=2)
    canvas_width: int = Field(
        default=800,
        ge=200,
        description="One fixed canvas for every visual. Height follows the 16:10 ratio.",
    )
    max_output_tokens: int = Field(
        default=400,
        ge=1,
        description="Routing emits a small object. It does not need the summarizer's budget.",
    )
    max_facts: int = Field(
        default=16,
        ge=2,
        description=(
            "How many quantities the router may choose between. A long indexed menu is "
            "lost-in-the-middle for a small model picking an integer index."
        ),
    )
    lead_words: int = Field(
        default=150,
        ge=1,
        description=(
            "How much of the article's own opening the router reads beside the summary. "
            "This is most of each request's prefill, and prefill is most of the stage's "
            "wall-clock, so it is a measured lever rather than a literal (Rule #6)."
        ),
    )
    request_timeout_minutes: float = Field(
        default=2.0,
        gt=0.0,
        description=(
            "One routing POST may wait this long. Sized from the measured worst routed "
            "item - 56.0 s on ubuntu-latest, 2026-08-24 - doubled. The stage used the "
            "summarizer's 150-minute shard bound before this existed, which is longer "
            "than the job it runs in, so it could never fire."
        ),
    )

    @property
    def canvas_height(self) -> int:
        """16:10, matching the frontend's fixed figure box exactly."""
        return round(self.canvas_width * 10 / 16)

    @model_validator(mode="after")
    def _bounds_are_orderable(self) -> Self:
        if self.max_chart_points < self.min_chart_points:
            raise ValueError("max_chart_points is below min_chart_points")
        if self.max_diagram_steps < self.min_diagram_steps:
            raise ValueError("max_diagram_steps is below min_diagram_steps")
        if VisualKind.NONE in self.enabled_kinds:
            raise ValueError("`none` is always reachable and is never listed as enabled")
        return self


class ThemeChoice(StrEnum):
    """The two themes. There is no third member for "follow the device".

    `system` was removed on 2026-08-31 with the control that offered it. It was
    not a theme - it was the absence of a choice - and keeping it here would let
    an operator set a value no surface can honour. `UiConfig` migrates an older
    file that names it (section 11).
    """

    LIGHT = "light"
    DARK = "dark"


class VisualSide(StrEnum):
    """Where a visual sits beside its text, at `sm` and above. Below that, always above."""

    ABOVE = "above"
    LEADING = "leading"
    TRAILING = "trailing"


class TodayAnchor(StrEnum):
    RIGHT = "right"
    CENTRE = "centre"


class ConsoleConfig(Model):
    """Knobs for the operator console's time viewport."""

    default_window_days: int = Field(
        default=30,
        ge=1,
        description=(
            "Initial time span for the console charts. A viewport, not a deletion. "
            "Thirty rather than fourteen because the page states its own retirement "
            "rules over fourteen days, so a window equal to the rule shows the rule "
            "with no margin either side of it."
        ),
    )
    window_presets: list[int] = Field(
        default_factory=lambda: [7, 14, 30, 90],
        min_length=2,
        description=(
            "The day counts the console's window control offers, ascending and "
            "distinct. A short list rather than a slider: every value is a distinct "
            "fetch cost, because a wider window pulls more month files, and most "
            "values in between are indistinguishable on the page. "
            "`default_window_days` must be one of them, or the console would open on "
            "a window its own control cannot name."
        ),
    )
    today_anchor: TodayAnchor = Field(
        default=TodayAnchor.RIGHT,
        description="Where today sits in the initial viewport when enough history exists.",
    )
    pan_days: int = Field(default=7, ge=1, description="Days moved by one arrow-key pan.")
    zoom_factor: float = Field(default=1.5, gt=1.0)
    min_window_days: int = Field(default=7, ge=1)
    max_window_days: int = Field(default=366, ge=1)
    min_attempts_for_rate: int = Field(
        default=5,
        ge=1,
        description="Below this count a rate is outlined because the denominator is thin.",
    )
    chart_height: int = Field(default=180, ge=120)
    chart_width: int = Field(
        default=600,
        ge=240,
        description=(
            "The width a console chart is drawn at on the server, in CSS pixels. A "
            "prerendered chart has no element to measure, and a chart drawn in "
            "arbitrary units and then stretched by its viewBox renders its labels at "
            "whatever the stretch factor happens to be - measured 2026-08-25, one page "
            "put the same font-size at 4.5px and at 16.6px. 600 is what the reading "
            "column leaves a full-width chart on any window wide enough to reach it; "
            "a narrower one redraws at its measured width once a script runs."
        ),
    )
    failure_list_max: int = Field(
        default=25,
        ge=1,
        description=(
            "How many failed items the console lists before it offers more. The shape "
            "comes first and the rows come on demand: an uncapped list put the "
            "compression chart 9000 pixels down the page."
        ),
    )
    band_outlier_rows: int = Field(
        default=10,
        ge=1,
        description=(
            "How many summaries the console names as furthest from the length the "
            "prompt asked for. Capped, with the tail stated in a sentence, because the "
            "list exists to be acted on and the far tail is a one-word miss nobody "
            "chases. Ten, matching the source-cut table beside it."
        ),
    )
    chart_arm_rule_days: int = Field(
        default=14,
        ge=1,
        description=(
            "The span the chart arm's retirement rule is stated over. A median taken "
            "over any other span is the same figure with a different meaning and "
            "nothing on the page to say which one is being read, so under this many "
            "days the section prints the rule's own span and no number at all."
        ),
    )
    chart_arm_minutes_target: float = Field(
        default=6.0,
        gt=0.0,
        description=(
            "Router minutes per published chart above which the median day retires "
            "the chart arm. Drawn as a marker on the bar, never as a subtraction the "
            "reader performs."
        ),
    )
    chart_arm_coverage_pct: float = Field(
        default=5.0,
        gt=0.0,
        le=100.0,
        description=(
            "The share of a day's published items that must carry a chart, in whole "
            "percent. Below this on the median day the arm is retired: an arm that "
            "reaches almost nothing is paying for a capability the digest does not "
            "use."
        ),
    )

    @model_validator(mode="after")
    def _window_bounds_are_ordered(self) -> Self:
        if self.min_window_days > self.default_window_days:
            raise ValueError("console.min_window_days must not exceed default_window_days")
        if self.default_window_days > self.max_window_days:
            raise ValueError("console.default_window_days must not exceed max_window_days")
        if self.window_presets != sorted(set(self.window_presets)):
            raise ValueError("console.window_presets must be ascending and distinct")
        if self.default_window_days not in self.window_presets:
            raise ValueError("console.default_window_days must be one of console.window_presets")
        # The presets are the only way the page sets its span, so these two bounds
        # would have no reader at all if a preset could sit outside them.
        outside = [
            days
            for days in self.window_presets
            if days < self.min_window_days or days > self.max_window_days
        ]
        if outside:
            raise ValueError(
                "console.window_presets must lie between min_window_days and max_window_days"
            )
        # A rule no preset can reach is a rule the page can never print. The
        # section would show the widen-the-window notice at every setting of the
        # control, which reads as a broken surface rather than as a narrow one.
        if max(self.window_presets) < self.chart_arm_rule_days:
            raise ValueError(
                "console.window_presets must offer a span of at least chart_arm_rule_days"
            )
        return self


class UiConfig(Model):
    """The published surface's knobs.

    `sections` is the modularity story: reordering the page is a config edit,
    not a code change. What is deliberately absent is a per-element layout
    engine - on the surface that matters, a phone, there is no left and no
    right, and a per-reader layout would break the promise that a shared link
    shows the recipient what the sender saw.
    """

    sections: list[str] = Field(
        default_factory=lambda: ["notice", "topics", "items"],
        min_length=1,
        description="Render order of the day page's sections, by registry id.",
    )
    theme_default: ThemeChoice = Field(
        default=ThemeChoice.DARK,
        description=(
            "The theme a reader who has never touched the control is served. It is the "
            "theme `:root` carries in tokens.css, so it is also what a page paints "
            "before any script runs and what a page with no script keeps."
        ),
    )
    visual_side: VisualSide = VisualSide.ABOVE
    source_mark: bool = Field(
        default=True, description="The monogram beside a source name. A scanning aid, not the id."
    )
    show_filter: bool = Field(
        default=True,
        description=(
            "An in-place filter inside the topic row. Never a top-level search bar: on a "
            "page this short it would promise an archive it cannot reach."
        ),
    )
    items_per_topic: int = Field(
        default=3,
        ge=1,
        description=(
            "How many of a topic's stories the all-topics page shows before it links to "
            "the rest. One long queue has no usable first screen: its opening items are "
            "whichever topic sorts first. Nothing is removed or re-ranked - every item "
            "stays one click away on its own topic page."
        ),
    )
    topic_pills_max: int = Field(
        default=8,
        ge=1,
        description=(
            "How many topic pills stay on the row before the rest go inside a "
            "disclosure. The cut is decided by each topic's story count at build "
            "time, never by measuring the row in pixels: every page here is "
            "prerendered, so a pixel-measured row is wrong until a script runs. "
            "Eight is what a 360px screen holds in three wrapped lines without the "
            "row becoming the page."
        ),
    )
    shell_seed_items: int = Field(
        default=15,
        ge=1,
        description=(
            "How many of a day's stories a prerendered document carries. It is the "
            "one knob in this block a browser is never told, because the root "
            "layout inlines the rest of them into every document and a number no "
            "page reads would ride to every reader for ever. Fifteen is the most "
            "items any reading surface draws before the reader acts: the five "
            "desks config/taxonomy.json declares times items_per_topic, which is "
            "above the twelve a flat list pages at. Re-derive it from those two "
            "when either moves - do not raise it to cover a busy day, because the "
            "stories past the seed arrive by fetch. Measured 2026-09-01 on the "
            "431-story day of 2026-08-30, gzip -9, Intel Core i7-1265U / Windows "
            "11 / node 24.12.0: the first fifteen stories cost a dated route "
            "20,302 bytes across the two documents it emits, against 420,074 for "
            "all 431."
        ),
    )
    repo_url: str = Field(default="https://github.com/miztiik/yen-idhazh", min_length=1)
    site_title: str = Field(default="yen-idhazh", min_length=1)
    tagline: str = Field(
        default="A daily digest that checks its own work.",
        min_length=1,
    )
    read_mark_days: int = Field(
        default=7,
        ge=1,
        description=(
            "How many digest days of read marks the browser keeps. Marks are held per "
            "digest date, so a mark made on one day can never grey out a different "
            "day's article. Every page load keeps the newest days up to this number "
            "and drops the rest, which bounds the store without trusting the device "
            "clock. One week covers a reader who comes back after a break."
        ),
    )
    archive_page_size: int = Field(
        default=25,
        ge=1,
        description=(
            "How many stories the archive's list adds each time a reader asks for more. "
            "The day page pages at twelve because a day is short and the reader came to "
            "read it; the archive holds thousands and the reader came to find one, so "
            "it opens on the same twenty-five the console's failure list does."
        ),
    )

    @field_validator("theme_default", mode="before")
    @classmethod
    def _system_reads_as_the_base_theme(cls, value: object) -> object:
        """Read-side migration for a config written before 2026-08-31 (section 11).

        `system` meant "follow the device". Nothing asks the device any more, so
        the only honest reading of an older file is the base theme.
        """
        return ThemeChoice.DARK if value == "system" else value


class PageWeightConfig(Model):
    """A gzip-size ceiling per prerendered route, enforced by
    `frontend/scripts/bundle-gate.mjs`.

    The gate reads `config/idhazh.json`, never this model, so a number here
    would be a second copy of what the file already holds, free to drift from
    the one the gate enforces. The default is empty for that reason: the
    committed config is the single source, and this model owns only the shape
    and the validation (Rule #6).

    A route is worth a fixed ceiling when somebody has priced its growth in
    published days. `/404` and `/evals/` render no day and no ledger, so their
    weight is a function of source alone and their ceiling is the heaviest build
    plus the 64-byte noise floor. `/archive/` grows, but only by one day link a
    day since it stopped inlining the day payloads, so its ceiling carries a year
    of that growth as measured headroom. The three `/console/` routes grow with
    the ledger their panels read, so each ceiling carries a measured few days and
    expires by design. What a page that renders a day cannot have is a fixed
    ceiling at all: the only way under one is to publish fewer items, which is
    capping the news rather than catching a regression, so `/` and `/<date>/` are
    counted and reported and never failed.

    **A surface that splits into routes takes a ceiling per route.** One number
    covering three surfaces still fails when any of them grows, and then cannot
    say which one did - so the operator raises the shared number and the
    regression lands under it. Sizing them separately is what makes the split
    worth having.
    """

    ceilings_bytes: dict[str, int] = Field(
        default_factory=dict,
        description=(
            "Route class -> the largest gzip -9 size that route's prerendered HTML may "
            "reach. The committed values live in config/idhazh.json, which the gate "
            "reads; this default is empty so the numbers are not duplicated here where "
            "they could drift from the file the gate enforces (Rule #6). A route the "
            "object does not name is measured and reported by the gate but not failed. "
            "A route earns a ceiling when its growth is priced: /404 and /evals/ grow "
            "only when the source does, /archive/ grows by one day link a day so its "
            "ceiling carries a measured year of that, and each of the three /console/ "
            "routes grows with the ledger its own panels read so each carries a "
            "measured few days and is meant to expire. One surface split across "
            "several routes takes one key per route, or a blown budget cannot name "
            "which route blew it. A page that renders a day is never capped, because "
            "the only way under such a ceiling is to publish less."
        ),
    )

    @model_validator(mode="after")
    def _a_ceiling_bounds_a_route(self) -> Self:
        for route, ceiling in self.ceilings_bytes.items():
            if not route.startswith("/"):
                raise ValueError(f"page_weight ceiling {route!r} is not a route")
            if ceiling <= 0:
                raise ValueError(f"page_weight ceiling for {route} must be above zero")
        return self


class AssistConfig(Model):
    """On-device archive search: what the encoder reads, and what the list shows.

    Every value here was a literal with no override path (Rule #6). The first two
    describe how much of an item the encoder is allowed to read; the rest describe
    what the reader's list keeps. All five are set from measurement rather than
    from taste.
    """

    max_tokens: int = Field(
        default=256,
        ge=16,
        le=512,
        description=(
            "How far into an item's text the encoder reads before it truncates. 512 "
            "is the hard ceiling because that is the encoder's position table; the "
            "default is 256 because that is what the model was trained at, and the "
            "measurement says nothing is waiting above it. Measured 2026-08-26 over "
            "the 1886 embedded items of the six committed days: p95 217 tokens, p99 "
            "243, max 280, and 0.58 percent of items run past 256 by a mean of 13 "
            "tokens. Raising it would read 0.05 percent more text and re-date every "
            "committed vector."
        ),
    )
    min_readable_letter_share: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "How much of an item's alphabet the encoder has to know before the item "
            "gets a vector at all. The committed weights carry an English uncased "
            "vocabulary, so an item written in another script still produces a "
            "confident unit vector that no query can retrieve. Below this share the "
            "item gets no vector and the run records why. Half is a plain reading of "
            "'mostly not in our alphabet', and it sits in the middle of an empty "
            "band: measured 2026-08-26 over the six committed days, 3 of 1889 items "
            "score 0.0 and the next lowest scores 0.9975, so every threshold between "
            "0.01 and 0.99 selects the same three items."
        ),
    )
    similarity_floor: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        description=(
            "Cosine similarity a result must reach to be shown at all. A SELECTOR, "
            "never reported to a reader as a quality signal. Re-measured 2026-08-26 on "
            "the backfilled archive (Windows 11, 12 logical CPUs, onnxruntime 1.29.0; "
            "2,119 embedded items, 60 labelled queries, 126,843 same-domain non-answer "
            "pairs): non-answers score a mean of 0.0761, a p95 of 0.2716 and a p99 of "
            "0.3992; the 297 right answers score a p10 of 0.3753 and a median of 0.5314. "
            "The noise distribution did not move when the corpus grew 3.7x - the earlier "
            "reading over 34,715 pairs was mean 0.074, p95 0.269, p99 0.399 - so the "
            "floor does not move either. 0.35 sits at the p98.12 of same-domain noise, "
            "keeps 93.6% of right answers, and lets 1.88% of non-answers survive. 0.45 "
            "would cut noise to 0.50% and cost 0.073 of recall@10, which is two standard "
            "errors and so a measurable loss."
        ),
    )
    result_limit: int = Field(
        default=10,
        ge=1,
        description=(
            "How many results the flat list shows. The list carries no rank cue, so "
            "this is also the denominator the recall bar is measured against - the "
            "denominator is min(right answers, this), because more right answers than "
            "slots cannot all be shown."
        ),
    )
    search_months: int = Field(
        default=1,
        ge=1,
        le=12,
        description=(
            "How many month shards a search always reads, newest first. The reader "
            "waits on the download, not on the arithmetic: measured 2026-08-26, one "
            "month is a 2.53 MB vector file beside a 518 KB browse index, about 2.1 "
            "seconds on a 10 Mbit line at the rate the committed days ran, or 4.8 "
            "seconds at the structural ceiling, against 74 to 159 milliseconds of "
            "ranking. The fetch is 9 to 30 times the ranking at every scope, so this "
            "knob buys download seconds and never compute seconds. Three months is a "
            "14.4 second download, so one month is the only scope whose first search "
            "starts inside about five seconds. This is a floor rather than a ceiling: "
            "assist.search_min_days can add one more shard when the newest one is "
            "thin. The page names the days it read, so a wider scope is a sentence a "
            "reader can see."
        ),
    )
    search_min_days: int = Field(
        default=7,
        ge=1,
        le=366,
        description=(
            "The fewest days of published stories a search tries to reach. The scope "
            "is month shards, and a calendar month is not a window: on the last day "
            "of a month the newest shard holds 31 days, and on the next morning it "
            "holds one. That is 31 times less reach for a reason no reader can see, "
            "and a search that finds nothing then looks exactly like a story that was "
            "never published. When the shards search_months names cover fewer days "
            "than this, a search reads ONE more shard - one more and no more, so the "
            "cost is bounded at a single extra fetch. Seven, because a week is already "
            "this site's unit for what a reader still has in mind: ui.read_mark_days "
            "keeps a read mark for seven days and console.min_window_days will not "
            "draw a narrower window. At the observed rate of 353.5 items a day the "
            "extra fetch fires on the first 6 days of a month, 20 percent of them, "
            "and it fires only when the shard a search already reads is small: "
            "measured 2026-08-26, an entry costs 50.03 gzipped bytes of browse index "
            "and 249.79 of vector, so the two shards together on 1 September move "
            "about what the one shard on 30 September already moves. The bytes are "
            "levelled across the month rather than doubled."
        ),
    )
    recall_min: float = Field(
        default=0.61,
        ge=0.0,
        le=1.0,
        description=(
            "The regression bar for recall@result_limit over the committed query set, "
            "counted over right answers that carry a vector. Coverage is excluded on "
            "purpose: an item the pipeline never embedded cannot be retrieved at any "
            "threshold, so counting it here would fail this gate for a defect in "
            "another stage. Set two standard errors below the 2026-08-31 baseline of "
            "0.690 +/- 0.041 (n=60), measured on Windows 11, 12 logical CPUs, "
            "onnxruntime 1.29.0, over 3,596 published items of which 3,594 carry a "
            "vector: 0.690 - 2 x 0.041 = 0.607, rounded to two places as 0.61. That "
            "baseline is a LOWER BOUND: 70.8% of filled slots hold an item no labeller "
            "judged either way, and every one of them is counted as a wrong answer. "
            "THIS BAR HAS AN EXPIRY DATE. Measured over eleven published days, recall "
            "slides 0.0134 a day against the frozen label set for a reason that is not "
            "a regression, so 0.61 has 0.080 of room and about six published days of "
            "it. Re-deriving the number a third time is not the fix; completing the "
            "labels is, and it lands on its own - see docs/concepts/evaluation.md."
        ),
    )


class AppConfig(Contract):
    """`config/idhazh.json` - every tunable, schema-validated."""

    __schema_stem__: ClassVar[str] = "app-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-01",
            change=(
                "ui.shell_seed_items added, defaulting to 15. The shape is "
                "`UiConfig`, which this document and `AppearanceConfig` share, so "
                "both schemas moved together. Additive with a default, so a config "
                "written before today still validates."
            ),
            why=(
                "A reading route's build-time load now splits a day into the facts "
                "that do not grow with the story count, the head of the published "
                "order, and the remainder. This number is where the head ends. "
                "Nothing fetches yet - the two halves are put straight back "
                "together, and the prerendered output is byte-identical - so the "
                "knob decides nothing today and everything once the item list "
                "moves to a browser fetch. Fifteen is the most items any reading "
                "surface draws before the reader acts, measured against the five "
                "desks `config/taxonomy.json` declares and `ui.items_per_topic`."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:59",
            change=(
                "ui.topic_pills_max added, defaulting to 8. The shape is `UiConfig`, "
                "which this document and `AppearanceConfig` share, so both schemas "
                "moved together. Additive with a default, so a config written before "
                "today still validates."
            ),
            why=(
                "The topic row was a horizontal scroll container, which is a control "
                "that hides its own contents; the owner ruled on 2026-08-31 that no "
                "reader-facing surface carries one. The row wraps now, and the topics "
                "past this number sit inside a `+N more` disclosure so a day with "
                "many topics does not turn the row into the page. A cap a component "
                "spells is a cap an operator cannot move (Rule #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:58",
            change="Added collect.max_source_share_per_day, and the committed config sets it.",
            why=(
                "Nothing counted one feed's contribution across a day. "
                "collect.max_per_source bounds a count inside one desk in one run, and "
                "a feed sits on exactly one desk, so a feed's ceiling for a whole day "
                "is that count times the runs the day had - 10 on a five-run day. A "
                "fixed count is a moving share: measured 2026-08-31 over the eleven "
                "committed days, 21 feeds held exactly 10 items of the 431-item day of "
                "2026-08-30, which is 2.32 percent each, while one feed held 1 of the "
                "four-item day of 2026-08-21, which is 25 percent. The share is what a "
                "reader sees and nothing bounded it. Additive with a default, so a "
                "config written before today still loads (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:55",
            change=(
                "ThemeChoice lost its `system` member and ui.theme_default now defaults "
                "to `dark`; the committed config repeats it. The shape is `UiConfig`, "
                "which this document and `AppearanceConfig` share, so both schemas "
                "moved together. Breaking: the enum is narrower. The read-side "
                "migration is a before-validator on `UiConfig.theme_default` that reads "
                "`system` as `dark`, so a config written before today still loads."
            ),
            why=(
                "The site now starts dark and light is an opt-in stored choice, so the "
                "three-state theme control became one button with two states (owner "
                "decision, 2026-08-31). `system` was never a theme - it was the absence "
                "of a choice - and nothing asks the device any more. Leaving the member "
                "in would let an operator set a value no surface can honour, which is a "
                "knob that silently does nothing. `dark` is the value `:root` carries "
                "in tokens.css, so the config and the first painted frame now agree "
                "instead of disagreeing."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:45",
            change=(
                "assist.recall_min default moved from 0.69 to 0.61, and the committed "
                "config repeats it. The shape is `AssistConfig`, which this document "
                "and `AppearanceConfig` share, so both schemas moved together."
            ),
            why=(
                "0.69 was two standard errors below a 2026-08-26 baseline of 0.767, "
                "and the baseline has slid to 0.690 since. The gate failed on main by "
                "0.00022, which is one percent of one standard error. It is not a "
                "ranking regression, and four arms over the same 60 queries, the same "
                "labels and the same ranking code say so. The archive at the last "
                "green commit scores 0.69163 +/- 0.04092. The same 3,485 items read "
                "with today's vectors score 0.69163 again, so the re-encode is "
                "+0.00000 and 0 of 10 committed day payloads changed a byte. The whole "
                "3,596-item archive held to that same denominator scores 0.68978, so "
                "competition is -0.00185. The whole archive as gated scores 0.68978 "
                "too, so the denominator is +0.00000 - unlike 2026-08-26 it cannot "
                "move, because the label set is frozen and already fully embedded. The "
                "entire drop is 111 new items competing for the same ten slots against "
                "labels pooled on 2026-08-26, which is the pooling bias "
                "docs/concepts/evaluation.md describes: 70.8 percent of filled slots "
                "now hold an item no labeller judged, against 65.6 percent then. The "
                "new bar comes off the same rule as the old one, 0.690 - 2 x 0.041 = "
                "0.607, rounded to two places as 0.61. The same rule applied at the "
                "last green commit also gives 0.61, so the number does not depend on "
                "which day it was taken. It buys about six published days at the "
                "measured slide of 0.0134 a day, and that expiry is written into the "
                "field description rather than left to be discovered by the next "
                "failing gate. Same field, same type: a config that names 0.69 still "
                "validates, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31T23:00",
            change=(
                "observability gained cost_currency, cost_input_per_million and "
                "cost_output_per_million, all with defaults the committed config "
                "repeats. page_weight.ceilings_bytes moved /console/machine/ from "
                "6,899 to 30,391."
            ),
            why=(
                "The Machine route now draws the six panels rows 13 to 16 of the "
                "observability plan describe, one of which prices a run's tokens at a "
                "hosted provider's rate. That figure is a counterfactual and never a "
                "bill - nothing bills us, because Actions minutes are free on a public "
                "repository - and CLAUDE.md Rule #10 carries the owner's carve-out for "
                "it on the condition that the rate and its source are printed beside "
                "it. So the rate is a config knob and not a literal in a component "
                "(Rule #6), input and output are priced apart because a provider "
                "prices them apart, and the currency is named rather than assumed. "
                "The committed values are a documented starting point the owner has "
                "not yet set; docs/concepts/config.md says so. The ceiling moved "
                "because the route went from rendering no ledger to rendering nine "
                "panels: it is a ratchet and not a budget, re-derived from five builds "
                "with the heaviest per route, and no panel was cut to stay under the "
                "old number (owner ruling, 2026-08-31). Additive only - the model "
                "defaults and the committed file agree, and a config written before "
                "today still validates, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-31",
            change=(
                "page_weight.ceilings_bytes gained /console/model/ at 18,682 and "
                "/console/machine/ at 6,899 in config/idhazh.json, and /console/ moved "
                "from 259,908 to 250,643. PageWeightConfig now says a surface that "
                "splits into routes takes a ceiling per route. No field moved."
            ),
            why=(
                "The console became three prerendered routes, and one ceiling covering "
                "three surfaces cannot say which of them blew a budget - which is the "
                "decisive argument for routes over tabs, so the split is not finished "
                "until the ceilings follow it. The gate already fails a ceiling that "
                "names no route in the build; a route that names no ceiling is only "
                "reported, so two new surfaces would have grown unwatched. All three "
                "numbers are re-derived rather than carried over: heaviest of five "
                "builds, plus seven published days priced by removing a real one, plus "
                "the 64-byte noise floor, measured 2026-08-31 (measurements.md). "
                "/console/ came down because its model panels moved to a route of their "
                "own. Committed values only - the model default stays empty, the shape "
                "and the validation are unchanged, and every older config still "
                "validates, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T21:15",
            change=(
                "console.chart_arm_rule_days, console.chart_arm_minutes_target and "
                "console.chart_arm_coverage_pct added, defaulting to 14 days, 6.0 "
                "minutes and 5 percent. The shape is `ConsoleConfig`, which this "
                "document and `AppearanceConfig` share, so both schemas moved together."
            ),
            why=(
                "The chart arm is the only console section with a written decision rule "
                "in its own prose, and all three numbers in that rule were constants in "
                "a TypeScript module - so the one section that states a threshold was "
                "the one section an operator could not move a threshold on (Rule #6). "
                "The two limits are now markers on bars and the span is what decides "
                "whether a median is printed at all. Additive with defaults, so a "
                "config written before today still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T20:00",
            change=(
                "console.band_outlier_rows added, defaulting to 10. The shape is "
                "`ConsoleConfig`, which this document and `AppearanceConfig` share, so "
                "both schemas moved together."
            ),
            why=(
                "The console's compression scatter became a per-day split plus a list "
                "of the summaries furthest from the length the prompt asked for, and a "
                "list that is capped needs the cap where an operator can move it. The "
                "scatter drew 2,740 marks in one colour, measured 2026-08-30, which "
                "rendered the dense middle as a block and hid the outliers - the only "
                "marks on it anybody could act on. Additive with a default, so a config "
                "written before today still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T18:00",
            change="observability.tracing_enabled added, defaulting to false.",
            why=(
                "A work shard can now build a span tree, which is the one thing the "
                "three ledgers cannot hold: a start instant, a parent, and a step too "
                "small to earn a column. The robots read nests inside the fetch, and "
                "the prompt render and the reply parse sit either side of the model "
                "call, so a slow item finally says which of the five it was slow in. "
                "It is the only switch in this block that is off unconfigured, because "
                "it is the only instrument nothing reads: no page renders a span, no "
                "gate consults one, and a trace is evidence where a ledger row is the "
                "record (CLAUDE.md section 1b). Off is also what keeps CI clean - a "
                "publish job that could fail on a third party's availability is a "
                "worse job."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T16:00",
            change=(
                "observability.evaluation_enabled and observability.sample_rate now say "
                "which stage reads them and where the draw is recorded."
            ),
            why=(
                "Both fields described a behaviour that nothing performed: the block "
                "landed as config with no reader, so the scorer still took its decision "
                "from the command-line flag alone. Wiring them raised two questions the "
                "descriptions did not answer. A standing switch must not reach `validate` "
                "or `qualify`, because each refuses to run without a scorer and a "
                "config file would turn a deliberate measurement into an exit code. And "
                "a rate is unreadable a year later unless the run says which rate it ran "
                "under and whether it was drawn, so both now travel on the run manifest. "
                "No field was added, removed or retyped; only two descriptions changed, "
                "and every committed config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T14:00",
            change=(
                "The observability block added: evaluation_enabled, telemetry_publish, "
                "runtime_counters_scrape, sample_rate, keep_months and "
                "hard_delete_after_months."
            ),
            why=(
                "The pipeline had no way to turn a measurement off or to thin one, so "
                "every instrument was all-or-nothing at the command line and nothing at "
                "all in config (Rule #6). Three switches rather than one, because "
                "collection, scoring and publishing fail differently: state/scores.csv "
                "empties when the scorer will not load, the published telemetry file "
                "stops when a run does not publish, and state/runtime-counters.csv is "
                "silent when llama-server was gone before it was read. One master switch "
                "would leave a reader unable to say which of the three went dark. "
                "sample_rate is a rate over RUNS and is refused at zero, because a "
                "second way to say off is how two ways of saying it end up disagreeing. "
                "The item-health census is deliberately absent and the model says so: it "
                "is the denominator under every rate, so switching it off would make "
                "every other measurement unreadable rather than cheaper. Additive with "
                "defaults that reproduce today's behaviour exactly, so an older config "
                "still validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30T12:00",
            change="Added drift.min_window_rows.",
            why=(
                "The drift review printed 'no drift across 0 recent and 0 baseline "
                "rows' and exited 0, because compare() walks the domains a window "
                "holds and an empty window holds none. Turn the scorer off for a "
                "week and the only automated watchman for slow extraction failure "
                "reports all clear every day, under a green check. The floor that "
                "separates 'nothing to compare' from 'no drift' is a tunable, not a "
                "literal (Rule #6). Additive with a default, so an older config "
                "still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-30",
            change=(
                "Added collect.max_age_hours. collect.recency_weight's description now "
                "says it orders inside that window rather than deciding admission."
            ),
            why=(
                "Age was a bonus and never a gate, so nothing had a lower bound. "
                "Measured 2026-08-30 over the 2,900 items published between 2026-08-22 "
                "and 2026-08-29, aged at the moment their own run planned them: the "
                "median is 5.5 hours and the 90th percentile is 35.7 days. The oldest "
                "story the digest has published was 6,474 days old - a stock note from "
                "December 2008 - and 826 items (28.5 percent) were over a day old when "
                "they were added. They came from research-lab and institution feeds "
                "that serve a whole back catalogue, and the tier weighting scores an "
                "undated institution post at 1.0 against 0.64 for a three-day-old "
                "trade-press story, so the archive won. The argument for keeping age "
                "soft was that a cutoff wastes a slot on a quiet day. There are no "
                "quiet days: every run since 2026-08-25 has hit its ceiling, so each "
                "old item displaced a fresher one. Additive with a default, so an "
                "older config still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T23:30",
            change=(
                "finetune.sequence_length default raised from 4096 to 8192, and "
                "finetune.holdout_days now states it must be shorter than the window "
                "has existed."
            ),
            why=(
                "Both were sized before the truncation cap moved, and running the "
                "pre-flight gates on 2026-08-29 showed both were wrong. 4096 was "
                "derived from a 1,923-word article; extract.truncation_cap_tokens is "
                "now 5,000 tokens, so the worst case is 920 + 5,335 + 900 = 7,155 and "
                "15 of 1,308 corpus rows already exceed 4096. Those rows would be "
                "truncated in training with no error, which teaches the model to stop "
                "mid-summary. The old text argued 8192 was headroom nothing uses; the "
                "measurement says it is the first power of two with a real margin, "
                "because 7168 clears the worst case by 13 tokens. Separately, "
                "holdout_days 14 over a window that had existed 7 days held out all "
                "1,308 rows and left nothing to train on, and split said so and exited "
                "0 anyway."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T23:00",
            change=(
                "console.window_presets added, and console.default_window_days must "
                "now be one of its members."
            ),
            why=(
                "The console had no way to say how many days it was showing, so every "
                "section picked its own span and one of them hard-coded seven days in "
                "the frontend. One control now sets one window for the whole page, and "
                "a control needs a list of the spans it offers. Four presets rather "
                "than a free number: a wider window fetches more month files, so every "
                "value is a distinct transfer cost and most of the values between "
                "these four cannot be told apart on the page. Additive with a default, "
                "so an older config still validates - the committed 30 is a member of "
                "the default list (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T22:00",
            change="Added collect.settled_failure_codes.",
            why=(
                "An address that failed was never recorded as published, so every later "
                "run of the same day planned it again. Measured over 2026-08-24 to "
                "2026-08-29: 403 repeat attempts inside a day produced 2 items, and 231 "
                "of the 233 repeated addresses never succeeded on any attempt. The codes "
                "listed cannot change before tomorrow; the ones left out - a rate limit, "
                "a reset connection, an unreachable model - can, so they still retry. "
                "Additive with a default, so an older config still validates "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T20:00",
            change=(
                "finetune.reference_rows raised from 300 to 500, and "
                "finetune.reference_test_rows added."
            ),
            why=(
                "Owner decision, 2026-08-29. The size of the set and the size of its "
                "read-by-a-person slice were one number, which hid the only cost that "
                "matters: a row drafted with an expert model is about two minutes and a "
                "row read line by line is about five, so the split is what decides the "
                "hours. At 500 and 100 that is roughly 13 hours of drafting and 8 of "
                "reading, against the 12 the plan estimated for 300. Additive with a "
                "default, so an older config still validates (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T18:00",
            change=(
                "The finetune block added, and models.<role>.hf_base_repo added as an "
                "optional field."
            ),
            why=(
                "The training corpus needs its sizes and its two schedules in config "
                "before anything writes a row (Rule #6), and the window and the sample "
                "are two knobs rather than one because they price differently: the "
                "window costs 2.9 KB of compressed history per row and the sample costs "
                "GPU hours. The prune is two knobs for the same reason - how often it "
                "fires and how far back it keeps are independent, and 'prune quarterly' "
                "means neither one on its own. hf_base_repo sits on the model entry and "
                "not here because training reads the safetensors repository while the "
                "pipeline reads the GGUF one: held in two blocks, a model swap moves one "
                "string and leaves the other, and a LoRA adapter loads onto a mismatched "
                "base without raising, so the damage arrives as a quality drop nobody can "
                "attribute. Both additive with defaults, so an older config still "
                "validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T16:00",
            change=(
                "summarize.bands gained a fifth rung at min_source_words 3000, asking "
                "150 to 230 words. No existing rung moved."
            ),
            why=(
                "A 2,000-word article and a 3,846-word article were handed the identical "
                "ask, so one was compressed 10 to 1 and the other 19 to 1 for the same "
                "150-word midpoint. 3,846 words is what extract.truncation_cap_tokens of "
                "5000 lets through, so both are read whole and the difference is real "
                "text and not a guess about text. The floor is 3000 because that is the "
                "midpoint of the whole-read range, 2,923, rounded to a seam the ledger "
                "reports. Measured 2026-08-29 over the 445 rows of state/scores.csv that "
                "carry a trustworthy pre-cap length: 9 of them reach 3,000 words, which "
                "is 2.02 percent of items and 1 to 4 items a run over four runs of 107 "
                "to 117 items. This is the last rung there may be - a floor above the "
                "cut point would ask for words the model was never handed, and the "
                "model would fill the gap by elaborating the opening. 230 sits inside "
                "evaluation.summary_words_max of 250, so the gate did not move. "
                "Additive with a default, so an older config still validates and no "
                "read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T14:00",
            change=(
                "page_weight.ceilings_bytes gained /console/ in config/idhazh.json, and "
                "the description here stopped saying that route is unpriced. No field "
                "moved."
            ),
            why=(
                "The description said /console/ 'stays uncapped until somebody measures "
                "it', and this is that measurement. The page costs about 60 gzipped "
                "bytes a published item: removing one real mature day from every ledger "
                "the console reads and rebuilding cost 43,745, 43,704 and 36,504 bytes "
                "over 731, 724 and 621 scored items, measured 2026-08-29 on an Intel "
                "Core i7-1265U, Windows, node 24.12.0. So the headroom is three days of "
                "the heaviest of those, not the year /archive/ carries, and the number "
                "is meant to expire (Rule #10)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-29T09:00",
            change="evaluation.truncation_gap_max removed.",
            why=(
                "Its one caller stopped reading it in this commit, so the knob and its "
                "last reader go together and there is never a state where the number "
                "exists and nothing consults it. It set truncation_flagged from the gap "
                "between the two faithfulness scores, and that flag now carries "
                "Article.truncated - whether extract cut the body - because that is what "
                "its name says and what its one consumer prints. Retuning it was the "
                "alternative and it is not available: score_over_chunks takes the best "
                "of overlapping windows, a cut article's last window is not a window of "
                "the whole article, and the two window sets are not nested, so the gap "
                "can come out positive on an article that was never cut. Measured "
                "2026-08-28 over all 2,683 committed rows of state/scores.csv, the gap "
                "on the 22 genuinely cut rows runs -0.1235 to +0.0381 against this "
                "knob's 0.100 default - no value in that range separates a cut from "
                "chunk-boundary noise (Rule #10). "
                "BREAKING: EvaluationConfig forbids unknown keys, so a config file that "
                "still names this key fails to load with a message naming it. The "
                "read-side migration is the deletion of the key from config/idhazh.json "
                "in this same commit (section 11); a fork carrying its own config "
                "deletes one line. hhem, hhem_full and hhem_delta all stay - they answer "
                "what the cut cost, which is a different question."
            ),
        ),
        ChangelogEntry(
            version="2026-08-28",
            change=(
                "evaluation.chunk_words added, defaulting to 900, and "
                "evaluation.chunk_overlap_words added, defaulting to 150. Both were "
                "constants in backend/idhazh/evals/hhem.py. EvaluationConfig now refuses "
                "an overlap at or above the window."
            ),
            why=(
                "The faithfulness scorer's window size decides what premise every score "
                "was measured over, so it is a tunable and belongs in config (Rule #6), "
                "and scorer_version now spells it as window=900/150/anchored so a ledger "
                "row records the geometry that produced it. Neither default moves today: "
                "with 0 of 60 human labels drawn there is no ground truth to tune "
                "against, and a sweep would show only that the number moves, not which "
                "value is right (Rule #10). The guard exists because the chunker steps "
                "chunk_words - chunk_overlap_words and clamps that step to one word, so "
                "an overlap at or above the window walks a long article one word at a "
                "time - a job that never finishes rather than one that fails. Additive; "
                "an older config still validates and gets both defaults."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T21:00",
            change=(
                "evaluation.label_min_stratum_rows added, defaulting to 20, and "
                "evaluation.label_min_run_days now counts run-days at one scorer version "
                "rather than at one (scorer_version, pipeline_fingerprint) pair."
            ),
            why=(
                "The old rule was unreachable, not strict. The pipeline stamp digests "
                "seventeen inputs - a reworded prompt, a llama.cpp rebuild, a sanitizer "
                "fix - so shipping any summarize-side improvement reset the count to "
                "zero. Measured over the whole committed ledger on 2026-08-27: six "
                "distinct stamps across six scored run-days, and the longest unbroken "
                "run at one pair is three. Ten was never once reached. What is being "
                "calibrated is the scorer's cut, which lives inside scorer_version, so "
                "the pipeline is a covariate: it is reported per stratum and a stratum "
                "under label_min_stratum_rows is marked too thin to cut on. The trade is "
                "named rather than hidden - a pooled rate over several producers is a "
                "prior with wide bounds, never a calibration. Owner decision, 2026-08-27. "
                "Additive plus a widened meaning; an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T12:00",
            change=(
                "evaluation.verbatim_reject_ceiling added, defaulting to 0.75, and "
                "EvaluationConfig now refuses a value at or below "
                "evaluation.brief_compression_ceiling."
            ),
            why=(
                "Summarize had no rule that refused a summary which merely copies the "
                "source, so a brief published on 2026-08-26 was 44 words of which every "
                "word was one unbroken copy of its 53-word source - republishing an "
                "article body, which CLAUDE.md section 0a forbids outright. The number "
                "is a second knob rather than a reuse of brief_compression_ceiling: a "
                "refused item writes no score, so it leaves the corpus the brief-copying "
                "gate reads, and one shared number would have made that gate unable to "
                "fail. It sits in evaluation and not summarize because summarize is "
                "hashed whole into the pipeline fingerprint, and a rule that refuses a "
                "reply moves not one word the model writes. 0.75 is the midpoint of the "
                "empty band those eight brief items left - seven at or below 0.241, one "
                "at 1.000 - and it is a starting point, not a calibration (Rule #10). "
                "The invariant is the control: without it an operator editing one line "
                "silences the gate instead of tightening it. Additive with a default, so "
                "an older config still validates and no read-side migration is needed "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T09:00",
            change=(
                "assist.search_min_days added, defaulting to 7, and "
                "assist.search_months restated as a floor rather than the whole scope."
            ),
            why=(
                "assist.search_months named a count of calendar shards, so the reach a "
                "search had was whatever the current month happened to hold - 31 days "
                "on 31 August and one day on 1 September. A reader who searched that "
                "morning got nothing back and could not tell it from a story we never "
                "published. A day floor makes the reach a promise instead of an "
                "accident, and capping the extra read at one shard keeps the cost "
                "bounded: measured 2026-08-26 the extra shard fires on 6 days of a "
                "30-day month and only when the shard already being read is small, so "
                "the bytes a search moves are levelled across the month rather than "
                "doubled. Additive with a default, so an older config still validates "
                "and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T05:00",
            change=(
                "page_weight.ceilings_bytes gained /archive/ again, at 7,553, and "
                "PageWeightConfig now says a route earns a ceiling when its growth is "
                "priced rather than when it does not grow."
            ),
            why=(
                "/archive/ was dropped on 2026-08-26 because it inlined every committed "
                "day, grew about 170 KB a publish, and was raised twice in one day to "
                "silence it - a countdown, not a bound. Search reads the month index "
                "now, so the page grows by one day link instead of by every story: "
                "measured 2026-08-27 at 2,906 bytes gzipped against 1,766,585 on main, "
                "and a year of publishing adds 4,476 more. With no ceiling the 99.8 "
                "percent saving had nothing holding it, and restoring the eager load "
                "would have passed every gate. Committed value only - the model default "
                "stays empty, the shape and the validation are unchanged, and every "
                "older config still validates, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T02:30",
            change="assist.search_months added, defaulting to 1.",
            why=(
                "Archive search used to rank over every committed day, because the page "
                "carried every committed day. It now reads month shards, so how many "
                "months it reads is a real choice and it was about to become a literal "
                "in the ranking module (Rule #6). One month, because the reader waits on "
                "the download and not on the arithmetic: measured 2026-08-26, a month of "
                "vectors is 518 KB and about 2.1 seconds on a 10 Mbit line at the rate "
                "the committed days ran, against 74 to 159 milliseconds of ranking, and "
                "three months is a 14.4 second download. Additive with a default, so an "
                "older config still validates and no read-side migration is needed "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27T02:00",
            change="ui.archive_page_size added, defaulting to 25.",
            why=(
                "The archive now lists every published story instead of a row per day, "
                "and a list of thousands needs a first screen. The number belongs in "
                "config rather than in the page (Rule #6). Additive with a default, so "
                "an older config still validates and no read-side migration is needed "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-27",
            change=(
                "run.shard_timeout_minutes gained the derivation behind its 150, and "
                "digest.yml now reads the work job's timeout from it. Same field, same "
                "type, same value."
            ),
            why=(
                "The knob had no reader anywhere and said only 'derived from the "
                "WORST-case article'. digest.yml set the work job to 330 minutes, so "
                "config declared 150 while production ran 330 - a wrong answer with a "
                "schema behind it, and the number a model adoption sizes against. "
                "Reading the wall-clock of 106 work jobs over 27 runs settled which one "
                "was wrong: across 16 full days at four workers the slowest worker of a "
                "run took 83.5 to 117.5 minutes, and at today's item ceiling the worst "
                "was 94.5. 150 is half again that and 330 was 3.5x it, so the workflow's "
                "number moved and the config number did not. Description only, so every "
                "committed config still validates and no read-side migration is needed "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T21:45",
            change=(
                "page_weight.ceilings_bytes default is now empty, and /archive/ and "
                "/console/ are dropped from the committed config."
            ),
            why=(
                "The default duplicated the four numbers the gate reads from "
                "config/idhazh.json, so raising a ceiling meant editing two files a test "
                "then forced to agree - config is the single source now (Rule #6). "
                "/archive/ grows with every committed day and /console/ with the ledger "
                "its charts read, so their fixed ceilings failed on ordinary publishes "
                "rather than catching regressions; the gate now reports an unnamed route "
                "without failing it. Older config still validates and the empty default "
                "changes no committed value, so no read-side migration (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T20:00",
            change="ModelRef gained an optional revision: the hub commit the weights are at.",
            why=(
                "Every weights download in the pipeline and the measurement harness read "
                "`resolve/main`, which is a branch. Upstream re-uploads a GGUF and the "
                "bytes change under a config that still records the old sha256, so a run "
                "either dies at the checksum or - where no checksum runs - measures a "
                "model nobody named (Rule #10). This field was rejected once as "
                "speculative because nothing read it; validate.yml now pins a revision "
                "and the adoption target names one, so it has readers. Optional with a "
                "null default, so the published run manifests that carry no revision "
                "still validate and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T11:45",
            change="page_weight.ceilings_bytes['/archive/'] moved from 1,676,048 to 1,676,110.",
            why=(
                "The archive page now carries the search box, and a box costs bytes. "
                "Measured by building one tree twice on the same machine, same day "
                "payloads: with main's frontend /archive/ gzips to 1,675,988 and with "
                "the search box to 1,676,050, so the box costs 62 bytes against 60 of "
                "headroom. The new ceiling keeps the same 60-byte allowance the other "
                "three routes carry rather than rounding up to a number that would stop "
                "the gate firing. What the bytes buy is the input, its label and its "
                "empty state on the one page that can search the whole archive. Same "
                "field, same type: an older config still validates. A changed default, "
                "so it is stamped here (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T11:20",
            change=(
                "assist.recall_min default moved from 0.85 to 0.69. "
                "assist.similarity_floor keeps 0.35 and carries a re-measured description."
            ),
            why=(
                "0.85 was calibrated against an archive where only 44.5% of items carried "
                "a vector, and the backfill took that to 99.9%. On the same 47 queries, "
                "the same labels and the same ranker, the number went 0.902 +/- 0.036 to "
                "0.743 +/- 0.042. That is not a ranking regression: holding the corpus to "
                "the same 944 items and swapping in the re-encoded vectors gives 0.910 "
                "+/- 0.034, so the vectors improved by 0.007. The whole effect is 1,175 "
                "items that the index could not see competing for the same ten slots "
                "(-0.142) plus a denominator that grew with coverage (-0.018). The new "
                "baseline over all 60 queries is 0.767 +/- 0.036 and the bar is two "
                "standard errors below it. It is a lower bound: 55.5% of the unlabelled "
                "items now holding a slot were unembedded when the labels were pooled, so "
                "nobody could have judged them, and they are counted as wrong answers. "
                "The floor does not move because the measurement says not to - the "
                "same-domain noise distribution is unchanged at 3.7x the pair count "
                "(p95 0.269 -> 0.2716, p99 0.399 -> 0.3992). Same fields, same types: an "
                "older config still validates and a committed config that names 0.85 "
                "still loads. A changed default, so it is stamped here (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T10:10",
            change="Added the assist search knobs: similarity_floor, result_limit and recall_min.",
            why=(
                "Archive search had no measurement at all, and its two behavioural "
                "constants were literals in the ranking module with no override path "
                "(Rule #6). The floor was 0.20 and is now 0.35, which is a measured "
                "change rather than a preference: at 0.20 every one of eight off-domain "
                "probe queries returned results - one of them eighteen - so 'Nothing in "
                "the archive is close to that' was a promise the selector could not keep. "
                "Measured 2026-08-26 on the committed archive over 60 hand-labelled "
                "queries: the floor cuts surviving non-answers from 11.4% to 1.9% and "
                "costs 0.035 of reachable recall@10, which is inside one standard error. "
                "recall_min is the regression bar the new backend eval enforces. All "
                "three are additive with defaults, so an older config still validates and "
                "no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T10:05",
            change="Added the assist block: max_tokens and min_readable_letter_share.",
            why=(
                "The encoder's token cap was a literal in embed.py, which is exactly the "
                "kind of tunable Rule #6 puts in config. The second knob is new "
                "behaviour: an item the encoder cannot read used to get a confident "
                "vector no query could retrieve, and now gets no vector and a logged "
                "reason. Both defaults are measured, not chosen - see the field "
                "descriptions. Additive with defaults, so an older config still "
                "validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26T10:00",
            change="Added the page_weight block.",
            why=(
                "A prerendered page could grow without limit and nothing said so. The "
                "marker count in payload-weight.spec.ts catches a day payload inlined "
                "where no day is rendered; it cannot see /archive/, which inlines every "
                "day on purpose, and it cannot see growth that carries no marker. A "
                "ceiling per route catches both. It is a knob rather than a literal in "
                "the gate script (Rule #6). Additive with a default, so an older config "
                "still validates and no read-side migration is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-26",
            change=(
                "run.safety_ceiling_per_run default moved from 200 to 160. "
                "run.max_parallel gained a description."
            ),
            why=(
                "The ceiling is the worst case every downstream bound has to clear, and "
                "200 cleared neither of them. digest.yml now derives the automatic work "
                "fan-out as min(ceil(items / run.shard_size), run.max_parallel), so at "
                "the ceiling a worker draws 50 items across the four workers a scheduled "
                "run gets. Against the Qwen3.5-9B candidate that is 318 derived minutes "
                "by length interpolation and 345 by decode ratio, over a 330-minute work "
                "timeout that nobody may raise (Rule #2); at 160 the same arithmetic "
                "gives 40 items, 254 and 276 minutes. The route stage says the same "
                "thing from the other side: its measured slow-host ceiling is 166 items "
                "at a 50-minute budget (2026-08-25, six runs, 703 items), so 200 and the "
                "router never agreed and 160 does. The largest day ever planned is 149 "
                "items (run 32742672105, 2026-08-24), so 160 removes nothing that has "
                "ever been read. run.max_parallel had no description at all while being "
                "the bound the derivation clamps by, and it is deliberately four while "
                "digest.yml lets an operator dispatch eight. Same fields, same types, "
                "same units: an older config still validates, and a committed config "
                "that names 200 still loads. A changed default, so it is stamped here "
                "(section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25T19:30",
            change="Added models.inference.metrics, on by default.",
            why=(
                "A run could not say how close it came to the context wall, and no "
                "number said whether more than one slot was ever busy. llama-server "
                "counts both already and only publishes them under --metrics. The flag "
                "is a knob rather than a workflow literal (Rule #6), and the endpoint "
                "it opens is llama-server's own loopback surface inside a CI job, so no "
                "reader is served by it and Rule #1 is untouched. Additive with a "
                "default, so an older config still validates and no read-side migration "
                "is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25T18:00",
            change="Added console.chart_width.",
            why=(
                "Every console chart is prerendered, so on the server there is no element "
                "to measure and the chart needs a width given to it. Without one each "
                "chart drew into an arbitrary viewBox and let the browser stretch it: "
                "measured 2026-08-25 at a 1057px window, one page scaled the same "
                "font-size to 4.5px in one panel and 16.6px in the next. Additive with a "
                "default, so an older config still validates and no read-side migration "
                "is needed (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-25",
            change=(
                "run.route_budget_minutes now stops the route stage instead of warning it, "
                "and visuals.enabled_kinds defaults to chart alone."
            ),
            why=(
                "Warning after the fact never saved a day. Measured on ubuntu-latest over "
                "six runs on 2026-08-24/25 (703 routed items): the mean per-item cost is "
                "20.7 s on a fast host and 40.3 s on a slow one, so a 145-item day needs "
                "50 to 97 minutes against a 60-minute job. Four of the six runs were "
                "cancelled at the bound, and a cancelled job skips its upload step - so "
                "every decision the hour bought was discarded and the day published with "
                "zero visuals. The diagram arm is what made the existing pre-filter "
                "unfireable: it is reachable for every item by construction, so the model "
                "was asked about 145 of 145 items on 2026-08-25 while it drafted zero "
                "diagrams in 88 and rendered zero in 703. With the arm off, 68 of those "
                "145 items (46.9%) never reach the model at all. Same fields, same types, "
                "same units; an older config still validates. Semantic shift on one and a "
                "changed default on the other, so both are stamped here (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T23:40",
            change=(
                "Added evaluation.labellers, evaluation.label_draw_per_decile and "
                "evaluation.label_min_run_days."
            ),
            why=(
                "The faithfulness cuts are a reader-facing promise with no measured error "
                "rate behind them, and the missing instrument was labels rather than more "
                "rows. The draw size and the collection floor are tuning decisions, not "
                "literals (Rule #6). `labellers` is empty by default, so a fresh clone can "
                "draw the queue and read it but cannot record a verdict - and because the "
                "row has no author field a model could fill, that list is a structural "
                "control rather than a discouragement. Additive with defaults."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T23:10",
            change=(
                "Added visuals.request_timeout_minutes, visuals.lead_words and "
                "run.route_budget_minutes."
            ),
            why=(
                "The route stage crossed its 60-minute job bound on five of the last "
                "eight runs. Measured on ubuntu-latest 2026-08-24 (run 32742672105): "
                "fixed cost 47 s, stage 3155 s, 149 items at a mean of 21.0 s. So "
                "per-item inference owns the time, not model load. The router had no "
                "request budget of its own and borrowed run.shard_timeout_minutes - "
                "150 minutes against a 60-minute job, which can never fire. lead_words "
                "was a literal on the hot path and is most of each request's prefill. "
                "The route budget warns before the bound instead of after it. All three "
                "are additive with defaults, so an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T21:40",
            change="Added ui.items_per_topic and console.failure_list_max.",
            why=(
                "Both are the same defect at two altitudes: a page that renders every "
                "row it holds. 586 items in one queue gave the day page a first screen "
                "chosen by whichever topic id sorts first, and 800 failed rows measured "
                "7824 pixels and pushed the compression chart off the operator's reach. "
                "How many to show first is a tuning decision, not a literal (Rule #6). "
                "Both are additive with defaults, so an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-24T11:15",
            change="Added collect.blocked_url_markers, empty by default.",
            why=(
                "A working news feed syndicated affiliate credit-card pages, which "
                "published at 0.92 to 0.95 faithfulness and banded high. The summaries "
                "were faithful - that is the point. Short declarative marketing prose is "
                "trivially entailed, so no faithfulness threshold detects it at any cut "
                "and raising the bar rewards it. The control has to sit where the item is "
                "collected, before anything is spent on it (Rule #2)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T19:50",
            change=(
                "Added the brief summary band, lowered evaluation.summary_words_min to 25, "
                "lowered extract.min_source_words to its derived value, added "
                "evaluation.brief_compression_ceiling, and added line-shape prose knobs."
            ),
            why=(
                "Short sources should publish with an honest brief instead of being padded "
                "or dropped. The old word gate forced the decoder to keep writing on a "
                "small source, which made invention more likely."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T19:40",
            change="Added the console block for the interactive telemetry viewport.",
            why=(
                "The console now lets the operator pan and zoom over the published "
                "item-health projection, so the default window, pan step, zoom factor, "
                "minimum denominator and chart size are tunable config values (Rule #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T19:35",
            change="Added llama-server runtime-sweep knobs to models.inference.",
            why=(
                "The runtime sweep must change one measured flag at a time through config, "
                "not through workflow literals. The startup_warmup default matches the "
                "current digest workflow, so the fingerprint input describes the server "
                "that actually runs."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T18:15",
            change=(
                "Added extract prose-shape, enforcement and paywall-marker knobs; changed "
                "extract.min_source_words to a brief-tier threshold."
            ),
            why=(
                "Extraction now records short or list-shaped pages instead of dropping "
                "them by length, while publisher-declared paywalls still stop publication. "
                "The new thresholds and switches are tunable config values (Rule #6)."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T17:52",
            change="Added models.inference.request_timeout_minutes.",
            why=(
                "One hung summarizer request was using the whole shard timeout, so a "
                "single bad item could burn 150 minutes and hide the cause. The new "
                "per-request budget is sized from the measured worst 8B long article "
                "plus a cold prompt prefix, doubled, while run.shard_timeout_minutes "
                "stays the outer bound. Additive - an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T17:41",
            change="Added evaluation.lead_coverage_min.",
            why=(
                "Lead coverage now caps a high confidence band at medium. The threshold "
                "is a tunable band input, so it belongs in config rather than in score.py "
                "(Rule #6). Additive - an older config still validates through the "
                "schema default."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T16:00",
            change="Added ui.read_mark_days.",
            why=(
                "Read marks were one flat list of item ids that never expired, so an id "
                "reused on a later day greyed out an article the reader had never "
                "opened, and the store grew for ever. Marks are now held per digest "
                "date and pruned to the newest days this number allows. Additive - an "
                "older config still validates, and the browser drops the old flat list "
                "on sight because there is no honest way to tell which day those ids "
                "belonged to."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23T15:00",
            change="Added summarize.title_words_min and summarize.title_words_max.",
            why=(
                "The digest published the source's own headline, which is written to "
                "win a click rather than to say what happened. The summarizer now "
                "writes the title too, and the range it is asked for is a knob like "
                "every other length in this block (Rule #6). Additive - an older "
                "config still validates, and an item whose title misses the range "
                "falls back to the source's."
            ),
        ),
        ChangelogEntry(
            version="2026-08-23",
            change="Added the summarize block: length bands, key-point range and quote cap.",
            why=(
                "The lengths the prompt asks for were literals inside the prompt text, "
                "where no schema could see them and nothing checked them against the "
                "range the pipeline accepts (Rule #6). They are bands rather than "
                "one range because a release note and a long read asked for the same "
                "number of words gives a padded summary of the first and a thin one of "
                "the second. Moving them here also puts them inside the prompt string "
                "the fingerprint hashes, so changing what we ask for now re-summarizes "
                "rather than reusing a cached reply written under the old ask. "
                "Additive - an older config still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22T11:00",
            change=(
                "Replaced run.item_cap_per_day with run.safety_ceiling_per_run. Added "
                "collect.recency_weight, collect.recency_half_life_hours, "
                "collect.max_future_hours and collect.seen_window_days. Raised "
                "inference.max_output_tokens to 900."
            ),
            why=(
                "A daily cap decided the size of the day; supply and the ranking should. "
                "The ceiling that remains is a crash guard against a mis-parsed feed. "
                "Recency is a bonus rather than a cutoff so a strong older item is never "
                "dropped for a weak new one. The token stop is labelled as the crash "
                "guard it always was, and sized so the prompt sets the length."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22T09:00",
            change="Removed collect.min_feeds_floor.",
            why=(
                "Nothing read it. The floor a vertical is actually held to is its own "
                "min_feeds in taxonomy.json, so a second number calling itself the "
                "default described a mechanism that does not exist."
            ),
        ),
        ChangelogEntry(
            version="2026-08-22",
            change="Added the visuals block.",
            why=(
                "Routing needs its bounds and its enabled-kinds gate in config before the "
                "router may choose a kind. Additive - an older payload still validates."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T06:00",
            change="Added the ui block.",
            why="The published surface's knobs need a home before a component reads one.",
        ),
        ChangelogEntry(
            version="2026-08-21T05:00",
            change="Added collect.max_per_source.",
            why=(
                "The first live run planned a whole vertical from one blog: with no story "
                "carried twice, the tie-break decided the day and one source won it."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21T03:00",
            change=(
                "Replaced evaluation.compression_min/max with summary_words_min/max; added "
                "extract.min_source_words and extract.boilerplate_ratio_max."
            ),
            why=(
                "At a fixed output budget a compression ratio measures the article's length, "
                "not the summary's quality - it would have flagged every short article "
                "forever. Absolute word bounds detect the two real failures directly."
            ),
        ),
        ChangelogEntry(
            version="2026-08-21",
            change="Initial shape: run, collect, extract, models, evaluation, drift, retention.",
            why="Contracts before logic - no stage may reach for a tunable that has no home.",
        ),
    )

    run: RunConfig = Field(default_factory=RunConfig)
    collect: CollectConfig = Field(default_factory=CollectConfig)
    extract: ExtractConfig = Field(default_factory=ExtractConfig)
    models: ModelsConfig
    summarize: SummarizeConfig = Field(default_factory=SummarizeConfig)
    evaluation: EvaluationConfig = Field(default_factory=EvaluationConfig)
    drift: DriftConfig = Field(default_factory=DriftConfig)
    retention: RetentionConfig = Field(default_factory=RetentionConfig)
    visuals: VisualsConfig = Field(default_factory=VisualsConfig)
    ui: UiConfig = Field(default_factory=UiConfig)
    assist: AssistConfig = Field(default_factory=AssistConfig)
    console: ConsoleConfig = Field(default_factory=ConsoleConfig)
    page_weight: PageWeightConfig = Field(default_factory=PageWeightConfig)
    finetune: FinetuneConfig = Field(default_factory=FinetuneConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    observability: ObservabilityConfig = Field(default_factory=ObservabilityConfig)

    @model_validator(mode="after")
    def _the_ask_sits_inside_the_gate(self) -> Self:
        """The prompt may ask for less than we accept. It may never ask for more.

        An operator editing one block cannot see the other, and the failure is
        silent in the worst way: the prompt asks for 300 words, the model
        complies, and the gate drops a correct summary every single run. So the
        two blocks are checked together here, where both are in scope.
        """
        for band in self.summarize.bands:
            if band.target_words_min < self.evaluation.summary_words_min:
                raise ValueError(
                    f"summarize band at {band.min_source_words} words asks for a summary "
                    "shorter than evaluation.summary_words_min accepts"
                )
            if band.target_words_max > self.evaluation.summary_words_max:
                raise ValueError(
                    f"summarize band at {band.min_source_words} words asks for a summary "
                    "longer than evaluation.summary_words_max accepts"
                )
        brief_target = self.summarize.bands[0].target_words_min
        derived_floor = math.ceil(brief_target / self.evaluation.brief_compression_ceiling)
        if self.extract.min_source_words != derived_floor:
            raise ValueError(
                "extract.min_source_words must equal summarize.bands[0].target_words_min "
                "divided by evaluation.brief_compression_ceiling"
            )
        return self

    @model_validator(mode="after")
    def _finetune_names_models_that_exist(self) -> Self:
        """A role that names no model is a training session that downloads nothing.

        Checked here because `FinetuneConfig` cannot see `models` and a typo
        would otherwise surface on a GPU somebody is paying for, hours later.
        """
        roles = set(ModelsConfig.model_fields) - {"inference"}
        for field in ("teacher", "student"):
            named = getattr(self.finetune, field)
            if named not in roles:
                spelled = ", ".join(sorted(roles))
                raise ValueError(f"finetune.{field} must name one of models: {spelled}")
        return self
