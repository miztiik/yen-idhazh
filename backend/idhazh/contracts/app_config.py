"""The tunable knobs (`config/idhazh.json`).

A knob is something a reasonable operator might want set differently without
changing a fact. The runner's own ceilings - 4 vCPU, the 6 h job cap, the 10 GB
cache, the 1 GB published site - are deliberately absent: they are properties of
the platform, and making them editable would invite raising the budget instead
of simplifying the feature (Rule #2).

Every knob ships a sane default, so a fresh clone runs unconfigured.
"""

from __future__ import annotations

from enum import StrEnum
from typing import ClassVar, Literal, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import ChangelogEntry, Contract, Model, Sha256, Slug
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
    file: str = Field(min_length=1)
    quantisation: str = Field(min_length=1)
    sha256: Sha256 | None = Field(
        default=None,
        description="Recorded once measured. A weight that changes silently changes every output.",
    )


class TierWeights(Model):
    """The ranking weight of a source tier. Tier 1 is the institution that IS the fact."""

    institution: float = Field(default=1.0, ge=0.0, le=1.0)
    trade_press: float = Field(default=0.6, ge=0.0, le=1.0)
    community: float = Field(default=0.3, ge=0.0, le=1.0)


class RunConfig(Model):
    safety_ceiling_per_run: int = Field(
        default=200,
        ge=1,
        description=(
            "A crash guard, not an editorial choice. Supply and the ranking decide how "
            "big a day is; this only stops a mis-parsed feed from publishing hundreds "
            "of items in one run. A normal day never reaches it."
        ),
    )
    shard_size: int = Field(
        default=5,
        ge=1,
        description="URLs per worker VM. Set by measured model-load amortization, not by taste.",
    )
    max_parallel: int = Field(default=4, ge=1)
    shard_timeout_minutes: int = Field(
        default=150,
        ge=1,
        description="Derived from the WORST-case article, not the blended figure.",
    )
    success_floor_pct: int = Field(
        default=70, ge=0, le=100, description="Below this, the run additionally opens an issue."
    )


class CollectConfig(Model):
    quarantine_after_failures: int = Field(default=5, ge=1)
    watchlist_max_entities: int = Field(default=30, ge=1)
    max_per_source: int = Field(
        default=2,
        ge=1,
        description=(
            "Most items one feed may contribute to one vertical in a day. Without it, a "
            "quiet news day is whichever blog published most."
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
            "How much freshness may move a score. A bonus, never a filter: a strong "
            "older item still outranks a weak new one, which a hard age cutoff cannot do."
        ),
    )
    recency_half_life_hours: float = Field(
        default=18.0,
        gt=0.0,
        description=("Hours for the recency bonus to halve. At 18 h a day-old item keeps a third."),
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


class ExtractConfig(Model):
    truncation_cap_tokens: int = Field(
        default=2500,
        ge=256,
        description="A performance lever, not only a safety cap: prefill degrades with length.",
    )
    min_source_words: int = Field(
        default=250,
        ge=1,
        description="Below this the item publishes through the brief tier. It is not a drop.",
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
    """Three sizes: the release note, the article, the long read.

    Starting points chosen from the shape of the sources we collect, not
    measurements - nothing here may be quoted as one (Rule #10). The first
    band begins at zero so every article lands in one, and the shortest ask sits
    above `evaluation.summary_words_min` so a summary that misses low by a few
    words is still publishable.
    """
    return [
        SummaryBand(min_source_words=0, target_words_min=50, target_words_max=90),
        SummaryBand(min_source_words=700, target_words_min=70, target_words_max=150),
        SummaryBand(min_source_words=2000, target_words_min=110, target_words_max=200),
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
    truncation_gap_max: float = Field(
        default=0.10,
        ge=0.0,
        le=1.0,
        description="Score gap that flags a truncation artifact rather than a hallucination.",
    )
    summary_words_min: int = Field(
        default=40,
        ge=1,
        description=(
            "Below this it is a headline, not a summary. Set under the lowest band in "
            "`summarize.bands`: the prompt is a request, and dropping an item for missing "
            "it by two words loses a story to a rounding error."
        ),
    )
    summary_words_max: int = Field(
        default=250, ge=1, description="Above this it is a copy. Absolute, not a ratio."
    )
    spot_checks_per_week: int = Field(default=10, ge=0)
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

    @model_validator(mode="after")
    def _bands_and_ranges_are_ordered(self) -> Self:
        if self.band_medium_min >= self.band_high_min:
            raise ValueError("band_medium_min must sit below band_high_min")
        if self.summary_words_min >= self.summary_words_max:
            raise ValueError("summary_words_min must sit below summary_words_max")
        return self


class DriftConfig(Model):
    month_over_month_pct: float = Field(default=10.0, gt=0.0)
    year_over_year_pct: float = Field(default=5.0, gt=0.0)
    quarterly_refresh_fraction: float = Field(default=0.5, gt=0.0, le=1.0)


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
        description="Opens an issue above this. The platform's hard ceiling is 1 GB.",
    )


class LoggingConfig(Model):
    level: LogLevel = LogLevel.INFO


class VisualsConfig(Model):
    """Routing and rendering knobs. "Nothing" is the common answer, by design.

    `enabled_kinds` is the gate that keeps an unbuilt renderer unreachable. The
    four-way enum lives in the contract because a payload must be able to say
    `image`; the router may only choose a kind whose renderer exists, so turning
    one on is a config edit rather than a code change.
    """

    enabled_kinds: list[VisualKind] = Field(
        default_factory=lambda: [VisualKind.CHART, VisualKind.DIAGRAM],
        description="Kinds the router may choose. `none` is always available and never listed.",
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
    SYSTEM = "system"
    LIGHT = "light"
    DARK = "dark"


class VisualSide(StrEnum):
    """Where a visual sits beside its text, at `sm` and above. Below that, always above."""

    ABOVE = "above"
    LEADING = "leading"
    TRAILING = "trailing"


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
    theme_default: ThemeChoice = ThemeChoice.SYSTEM
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


class AppConfig(Contract):
    """`config/idhazh.json` - every tunable, schema-validated."""

    __schema_stem__: ClassVar[str] = "app-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
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
    logging: LoggingConfig = Field(default_factory=LoggingConfig)

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
        return self
