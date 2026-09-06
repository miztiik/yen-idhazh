"""The tunable knobs (`config/idhazh.json`).

A knob is something a reasonable operator might want set differently without
changing a fact. The runner's own ceilings - 4 vCPU, the 6 h job cap, the 10 GB
cache - are deliberately absent: they are properties of the platform, and making
them editable would invite raising the budget instead of simplifying the feature
(Rule #2).

The 1 GB published site is the one that is here, and it is here bounded rather
than trusted. `retention.pages_hard_cap_mb` may name a smaller cap and is
refused above `PAGES_HARD_CAP_MB`, so a config edit can only ever make the site
gate stricter. That is the same rule the absent ceilings obey, held by the schema
instead of by nobody editing a constant.

Every knob ships a sane default, so a fresh clone runs unconfigured.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date as date_type
from datetime import timedelta
from enum import StrEnum
from functools import lru_cache
from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Final, Literal, Self

from pydantic import Field, StringConstraints, field_validator, model_validator

from idhazh.contracts.base import ChangelogEntry, CommitSha, Contract, Model, Sha256, Slug
from idhazh.contracts.item_health import FailureCode
from idhazh.contracts.visual_decision import VisualKind


@lru_cache(maxsize=16)
def months_a_window_can_touch(within_days: int) -> int:
    """The most `<YYYY-MM>` shards one read of that window can open.

    A window of N days reads N+1 inclusive days - the way
    `ledger.shards_in_window` walks them - and the answer is how many calendar
    months those days fall in. It is not `N / 30`. The extreme is a window that
    ends on the first of a month and starts on the last day of another, which is
    why the committed 366-day console window reaches **14** shards and a
    thirteen-month retention is one shard short of what a reader can still ask
    for.

    Sweeping the month-firsts of one 400-year Gregorian cycle is exact rather
    than a sample. Moving the end date later inside its month spends days that
    would otherwise reach back, so the widest span always ends on a first, and
    the calendar repeats every 400 years.
    """
    if within_days < 0:
        raise ValueError("a window cannot be negative")
    span = timedelta(days=within_days)
    widest = 1
    for year in range(2000, 2400):
        for month in range(1, 13):
            end = date_type(year, month, 1)
            start = end - span
            reach = (end.year * 12 + end.month) - (start.year * 12 + start.month) + 1
            widest = max(widest, reach)
    return widest


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
        default=80,
        ge=1,
        description=(
            "What sizes a run. It began as a crash guard against a mis-parsed feed and "
            "supply overtook it: items_planned has been exactly this number on every run "
            "since 2026-08-25, so it is the cap whatever it is called. Owner decision, "
            "2026-09-05: it comes down to 80 from 160 - the day publishes half as many "
            "stories, and the gain is that those 80 slots go to articles worth reading "
            "rather than to a second copy of one already chosen or to a feed that has "
            "been publishing badly. It is an editorial choice about the day now, not a "
            "crash guard. It is also what sizes the worst case a work shard and the "
            "route stage have to finish - a smaller run makes a smaller worst case - and "
            "a worker killed at run.shard_timeout_minutes uploads nothing."
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
        default=200,
        ge=1,
        description=(
            "The work job's own timeout, which digest.yml reads from here. A backstop, "
            "never a budget: a worker has no clock of its own, and one killed at this "
            "bound uploads nothing, so the run loses every item that worker held. It "
            "rose to 200 from 150 as headroom for the coming two-call summariser "
            "change, not because any worker got slower - at run.safety_ceiling_per_run "
            "of 80 a worker draws 20 items, half of the 40 it drew before, so the base "
            "work roughly halves. Sized from the worst measured shard, not the median: "
            "over 80 shard rows on 2026-09-02 the worst used 135.4 minutes of the old "
            "150-minute bound and the median used 78.5, and the second model call an "
            "item spends exactly that margin. 200 is 56 percent of the six-hour platform "
            "ceiling, well inside Rule #2. A slow worker is still answered by lowering "
            "the ceiling, never by raising this."
        ),
    )
    visual_planner_budget_minutes: int = Field(
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

    @model_validator(mode="before")
    @classmethod
    def _a_renamed_knob_still_opens(cls, data: Any) -> Any:
        return read_a_renamed_key("run", data, RENAMED_RUN_KEYS)


#: The `collect` names this block used to carry, and the knob that answers the
#: same question now. A config still spelling one is refused by name.
SUPERSEDED_COLLECT_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {"quarantine_after_failures": "availability_strikes_before_rest"}
)

#: The `observability` names this block used to carry, and the knob that governs
#: the same store now.
SUPERSEDED_RETENTION_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "keep_months": "item_health_full_grain_months",
        "hard_delete_after_months": "item_health_aggregate_keep_months",
    }
)


def refuse_a_removed_knob(block: str, data: Any, names: Mapping[str, str]) -> Any:
    """Fail a config that still spells a removed knob, and name its replacement.

    Every model here forbids unknown keys, so a removed name already fails - with
    "extra inputs are not permitted", which does not tell an operator where their
    number went. Ignoring it silently would be worse: that is how somebody comes
    to believe a value nothing reads.
    """
    if not isinstance(data, dict):
        return data
    carried = sorted(name for name in names if name in data)
    if carried:
        spelled = "; ".join(f"{block}.{name} is now {block}.{names[name]}" for name in carried)
        raise ValueError(
            f"{block} carries a knob that was removed ({spelled}). Rename it - a knob "
            "nothing reads is a number somebody believes"
        )
    return data


#: The `run` knobs this block used to carry, and the knob holding the same
#: number now. A config still spelling one is read as the new name.
RENAMED_RUN_KEYS: Final[Mapping[str, str]] = MappingProxyType(
    {"route_budget_minutes": "visual_planner_budget_minutes"}
)

#: The `models` keys this block used to carry, and the key holding the same
#: model now. It is also the map `finetune` roles are read through, because a
#: role names one of these keys as a value.
RENAMED_MODELS_KEYS: Final[Mapping[str, str]] = MappingProxyType({"route": "visual_planner"})


def read_a_renamed_key(block: str, data: Any, names: Mapping[str, str]) -> Any:
    """Read a config still spelling a renamed key as though it spelled the new one.

    `config/` is a persisted surface, so a key rename is breaking: every model
    here forbids unknown keys, and a file written before the rename would be
    refused outright (section 11). The migration sits on the model that owns the
    key, so one place knows both spellings and there is no second config reader.

    A file carrying both spellings with different values is refused. Taking one
    silently is how somebody comes to believe a number nothing reads.
    """
    if not isinstance(data, dict):
        return data
    migrated = dict(data)
    for old, new in names.items():
        if old not in migrated:
            continue
        carried = migrated.pop(old)
        if new in migrated and migrated[new] != carried:
            raise ValueError(
                f"{block} spells both {old} and {new}, with different values. "
                f"{block}.{old} is now {block}.{new} - keep one"
            )
        migrated.setdefault(new, carried)
    return migrated


class CollectConfig(Model):
    availability_strikes_before_rest: int = Field(
        default=5,
        ge=1,
        description=(
            "Consecutive results that count against a feed before a run stops asking "
            "it, and how many runs that rest then lasts. One number for both counters "
            "because there is one question here - how much evidence is enough - and "
            "discover.resting takes it once. It replaced quarantine_after_failures on "
            "2026-09-03, carrying the same 5: the old name read as a policy about "
            "quarantine and this one is named for what it counts."
        ),
    )
    availability_rest_runs: int = Field(
        default=5,
        ge=1,
        description=(
            "How many runs a rested feed is skipped before it is asked again. The rest "
            "ends on its own, so a source that came back is live on that very run and a "
            "source that is still dead costs one request per cycle rather than one per "
            "run. Still unread: the rest lasts availability_strikes_before_rest runs, "
            "because splitting one number into two is a change to the rest rule rather "
            "than a rename, and the rename is what landed."
        ),
    )
    feed_http_410_runs_before_retirement: int = Field(
        default=5,
        ge=1,
        description=(
            "Distinct runs that must each read HTTP 410 from one address before that "
            "address is retired. Distinct runs and not attempts: one bad afternoon "
            "retrying itself is one run's evidence."
        ),
    )
    robots_denied_recheck_runs: int = Field(
        default=1,
        ge=1,
        description=(
            "Runs to wait before asking robots.txt again after a refusal. One, because "
            "permission can be granted back at any moment and a refusal costs one small "
            "request to re-establish - a longer wait buys nothing measurable and delays "
            "a source's return."
        ),
    )
    robots_unreachable_recheck_runs: int = Field(
        default=1,
        ge=1,
        description=(
            "The same, for permission we could not establish at all. Separate from the "
            "denial cadence because the two are different facts: one is a publisher's "
            "stated policy and the other is our own failed read."
        ),
    )
    source_yield_min_complete_days: int = Field(
        default=30,
        ge=1,
        description=(
            "Complete days of item-health evidence a per-source yield judgement needs "
            "before it may be made at all. Below it any yield threshold is an estimate "
            "rather than a measurement (Rule #10), and no source may be demoted on one."
        ),
    )
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
    reliability_window_days: int = Field(
        default=30,
        ge=30,
        description=(
            "Trailing days of committed feed-health read to score a feed's "
            "reliability - how often its reads carried entries rather than failing or "
            "parsing to nothing. At least 30, because a feed publishes a few times a "
            "day at most and a shorter window would let one bad afternoon set the "
            "factor. The read is bounded by this window and never the whole ledger "
            "(Rule #12)."
        ),
    )
    reliability_floor: float = Field(
        default=0.5,
        gt=0.0,
        le=1.0,
        description=(
            "The lowest a reliability factor may reach. The factor scales a feed's "
            "authority and is clamped to the range [floor, 1.0], so it only ever "
            "reduces a score and never removes a feed. At 0.5 the worst a feed's "
            "record can do is halve its authority - a two-to-one cut, never more - so "
            "a reliable feed of a lower tier can still be caught but a single desk is "
            "never emptied by this alone."
        ),
    )
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
    dedup_similarity_min: float = Field(
        default=0.94,
        ge=0.0,
        le=1.0,
        description=(
            "How alike two of a day's planned stories have to be, by cosine over the "
            "headline-and-lead vectors the plan builds, before they are recorded as one "
            "story carried at two addresses. The same number and the same reason as "
            "assemble.duplicate_similarity_min: set by hand labels at 0.94, the first "
            "round hundredth above the highest-scoring pair a person marked as two "
            "stories (measured 2026-09-01, i7-1265U, 3,978 items). The plan pass reuses "
            "it rather than minting a second threshold for the same question one stage "
            "earlier. Raising it misses duplicates; lowering it risks folding two "
            "stories into one, so it leans high."
        ),
    )
    dedup_enforce: bool = Field(
        default=False,
        description=(
            "Whether the plan-stage duplicate pass CUTS the weaker telling of a "
            "repeated story, or only records what it would cut. False is record-only: "
            "the pass logs each would-collapse pair against what it matched and removes "
            "nothing, so a day is measured before it is trimmed. Turning it on cuts the "
            "lower-ranked of each pair before the safety ceiling and changes nothing "
            "else. It ships false, because a cut nobody has read the record of is a cut "
            "nobody can defend."
        ),
    )

    @model_validator(mode="before")
    @classmethod
    def _refuse_a_removed_knob(cls, data: Any) -> Any:
        return refuse_a_removed_knob("collect", data, SUPERSEDED_COLLECT_NAMES)


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
    visual_planner: ModelRef
    inference: InferenceConfig = Field(default_factory=InferenceConfig)

    @model_validator(mode="before")
    @classmethod
    def _a_renamed_key_still_opens(cls, data: Any) -> Any:
        return read_a_renamed_key("models", data, RENAMED_MODELS_KEYS)


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


#: The platform's own ceiling on a published Pages site, in MB. A property of the
#: host rather than a preference, so it is the bound `retention.pages_hard_cap_mb`
#: is validated against and never a value config can reach past: an operator may
#: make the site gate stricter and may not make it looser (Rule #2).
PAGES_HARD_CAP_MB: Final = 1024


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
    pages_hard_cap_mb: int = Field(
        default=PAGES_HARD_CAP_MB,
        ge=1,
        le=PAGES_HARD_CAP_MB,
        description=(
            "The size at which the built site can no longer be published, in MB. "
            "`idhazh site-weight` fails the job above it, and that failure is the "
            "whole difference between this knob and site_budget_mb: the other one "
            "warns and this one stops. Bounded on purpose - the 1 GB belongs to "
            "GitHub Pages, so config can lower the cap a run enforces and can never "
            "raise it (Rule #2). Lowering it buys an earlier and louder failure while "
            "there is still headroom to act in; no value buys more room. The console's "
            "site band is drawn against the platform's own 1 GB rather than this, "
            "because it reports the ceiling that exists and not the one this run "
            "chose to stop at."
        ),
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

    **Every store names its own cleanup age.** One age covered
    `state/item-health/` while `state/feed-health/`, `state/scores/` and
    `frontend/public/telemetry/` had none, so three of the four grew with nothing
    to stop them and the fourth was tuned by a number that said nothing about
    them. The four full-grain windows are checked against the shards a console
    read can still select, and a summary that replaces a full-grain window must
    outlive it.
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
        default=True,
        description=(
            "Whether a work shard builds a span tree. On by default (2026-09-06): a "
            "span tree is the one thing the three ledgers cannot hold - a start "
            "instant, a parent, and a step too small to earn a column, the robots "
            "read inside the fetch and the prompt render and reply parse either side "
            "of the model call. It stays an instrument nothing reads: no page renders "
            "a span, no gate consults one, and the ledgers stay the record. True "
            "writes one JSON line per span to the committed trace under state/traces/, "
            "a short rolling window observability.trace_window_days bounds, and folds "
            "the shard's spans into the committed span rollup. A host is opt-in on top "
            "of that, through LANGFUSE_HOST with its key pair, and CI names none - so "
            "an ordinary run reaches no third party whatever this says."
        ),
    )
    trace_window_days: int = Field(
        default=7,
        ge=1,
        description=(
            "How many days of raw span traces state/traces/ keeps. A trace is the "
            "evidence an operator opens to see one recent run step by step; the "
            "committed record is the span rollup, so a trace has a short life and a "
            "file past this window is deleted whole rather than folded - a fold would "
            "invent a total nobody reads. Seven days covers a week of runs. Measured at "
            "about 0.6 MB a run at the run.safety_ceiling_per_run item ceiling over the "
            "five scheduled runs a day (2026-09-06), so the window bounds state/traces/ "
            "at about 21 MB whatever the project's age - constant (Rule #12), and a "
            "fraction of the 1 GB Pages reference it is not even part of. It does "
            "nothing until observability.tracing_enabled is true: before that no trace "
            "is written and the prune walks an empty tree."
        ),
    )
    item_health_full_grain_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long state/item-health/ stays readable item by item. Past it a month "
            "is folded to one row per (date, stage) and the full-grain shard goes, so "
            "a reader keeps every daily total and loses the per-item detail the "
            "console's failure list offers. Fourteen because console.max_window_days "
            "is 366, and a 366-day window reads 367 inclusive days, which can fall in "
            "fourteen calendar months - a window ending on the first of a month starts "
            "on the last day of another. Thirteen looks like a year plus the month "
            "being written and is one shard short of what the console can still ask "
            "for."
        ),
    )
    item_health_aggregate_keep_months: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Months after which the folded item-health month is removed outright. Null "
            "means never, and never is the default: the aggregate costs a measured "
            "63.8 bytes a row over four stages - about 93 KB a year against the "
            "shard's 77 MB - and deleting it would make a year-over-year comparison "
            "unanswerable, which Rule #10 then forbids citing at all. Set, it must sit "
            "ABOVE item_health_full_grain_months, or a month would be deleted before "
            "it was ever folded."
        ),
    )
    feed_health_keep_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long state/feed-health/ keeps a month. It is a per-feed-per-run "
            "record rather than a measurement worth summarising, so its retention is "
            "one number and there is no aggregate under it. Fourteen for the same "
            "reason the item-health window is: the console reaches 367 inclusive days "
            "and those days can fall in fourteen month shards."
        ),
    )
    scores_full_grain_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long state/scores/ stays readable item by item. The eval ledger is "
            "the only record of how a summary scored, and the console's model panels "
            "take medians and percentiles over the rows themselves - so this is the "
            "window inside which a quality question can still be asked of the items "
            "rather than of a total. Fourteen matches the census it is read beside; a "
            "shorter one would leave a day whose failures are still readable and whose "
            "quality is not."
        ),
    )
    score_archive_keep_months: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Months after which a summarised score month is removed outright. Null "
            "means never, on the same argument as item_health_aggregate_keep_months: a "
            "summary is kilobytes and it is the only thing that makes a year-over-year "
            "quality claim citable. Set, it must sit ABOVE "
            "scores_full_grain_months."
        ),
    )
    public_telemetry_keep_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long frontend/public/telemetry/ keeps a published shard. It must "
            "EQUAL item_health_full_grain_months and the contract refuses any other "
            "pair: the projection is the browser's copy of that ledger, so a published "
            "month whose source has been folded away is a rate nobody can check, and a "
            "source month with no published copy is a window the console cannot draw."
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

    @model_validator(mode="before")
    @classmethod
    def _refuse_a_removed_knob(cls, data: Any) -> Any:
        """Fail a config that still names `keep_months` or `hard_delete_after_months`.

        Those two governed `state/item-health/` and nothing else, while three
        other stores had no age at all. They were read and dropped for a day so
        the rows that spend the new ages could land one at a time; now that every
        reader has moved, a file still spelling one is refused by name.

        Refused rather than ignored, and refused rather than carried forward. The
        old value was set against a check that could not answer the question - it
        compared `months * 30` against the console window instead of the shards
        that window selects - so honouring it would honour the defect, and
        dropping it silently would leave an operator believing a number nothing
        reads.
        """
        return refuse_a_removed_knob("observability", data, SUPERSEDED_RETENTION_NAMES)

    def full_grain_months(self) -> Mapping[str, int]:
        """Every window that has to outlive what a console read can still select."""
        return MappingProxyType(
            {
                "item_health_full_grain_months": self.item_health_full_grain_months,
                "feed_health_keep_months": self.feed_health_keep_months,
                "scores_full_grain_months": self.scores_full_grain_months,
                "public_telemetry_keep_months": self.public_telemetry_keep_months,
            }
        )

    def refuse_windows_shorter_than(self, shards: int, *, window_days: int) -> None:
        """Refuse a config that would delete a shard a console read still opens.

        Checked against the shards the window selects rather than against the
        window's own length, because a month is not thirty days and the old
        `months * 30` comparison passed a value that is one shard short.
        """
        short = {
            name: months for name, months in self.full_grain_months().items() if months < shards
        }
        if short:
            spelled = ", ".join(f"observability.{name} is {value}" for name, value in short.items())
            raise ValueError(
                f"a {window_days}-day read can select {shards} month shards, so every "
                f"full-grain window must keep at least {shards}: {spelled}"
            )

    @model_validator(mode="after")
    def _a_summary_outlives_the_rows_it_replaces(self) -> Self:
        for kept, full_grain in (
            ("item_health_aggregate_keep_months", "item_health_full_grain_months"),
            ("score_archive_keep_months", "scores_full_grain_months"),
        ):
            months: int | None = getattr(self, kept)
            if months is not None and months <= getattr(self, full_grain):
                raise ValueError(
                    f"observability.{kept} must sit above {full_grain}, or a month is "
                    "deleted before it is ever summarised"
                )
        return self

    @model_validator(mode="after")
    def _the_published_copy_lasts_as_long_as_its_source(self) -> Self:
        if self.public_telemetry_keep_months != self.item_health_full_grain_months:
            raise ValueError(
                "observability.public_telemetry_keep_months must equal "
                "item_health_full_grain_months. The projection is the browser's copy "
                "of that ledger, so any other pair leaves either a published month "
                "nothing can check or a window the console cannot draw"
            )
        return self


#: What a `finetune` role may spell. A key in `models` is a Python attribute
#: name, so it is snake_case - not the kebab-case a `Slug` allows, which no key
#: could ever be. `AppConfig` checks the name against the real block; this only
#: bounds the shape, so an editor reading `schemas/` refuses a typo offline.
ModelRole = Annotated[str, StringConstraints(pattern=r"^[a-z0-9]+(?:_[a-z0-9]+)*$")]


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

    teacher: ModelRole = Field(
        default="summarize",
        description="A key in `models`. The model whose outputs a session fine-tunes.",
    )
    student: ModelRole = Field(
        default="visual_planner",
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

    @model_validator(mode="before")
    @classmethod
    def _a_role_naming_a_renamed_key_still_opens(cls, data: Any) -> Any:
        """A role naming a renamed `models` key reads as the new name.

        `ModelsConfig` carries the same rename where it is spelled as a key.
        This carries it where it is spelled as a value, and without it a file
        written before the rename loads its `models` block and then fails the
        `AppConfig` check that a role names a real one.
        """
        if not isinstance(data, dict):
            return data
        migrated = dict(data)
        for field in ("teacher", "student"):
            named = migrated.get(field)
            if isinstance(named, str) and named in RENAMED_MODELS_KEYS:
                migrated[field] = RENAMED_MODELS_KEYS[named]
        return migrated

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
    """Planning, rendering and serving knobs. "Nothing" is the common answer, by design.

    `enabled_kinds` is the gate that keeps an unbuilt renderer unreachable. It
    is a list rather than a flag so that a kind added later is switched on by a
    config edit rather than by a code change.

    `asset_base_url` is the same shape at the other end of the pipeline: where a
    browser asks for a drawing the pipeline already published. It ships empty,
    which means this site, and the whole point of it existing empty is that
    moving the bytes off the 1 GB Pages cap is then a config edit rather than a
    project.
    """

    enabled_kinds: list[VisualKind] = Field(
        default_factory=lambda: [VisualKind.CHART],
        description=(
            "Kinds the planner may choose. `none` is always available and never listed. "
            "Chart is the only one left: the diagram arm shipped off - the model drafted "
            "it zero times in 88 items and rendered it zero times in 703 (ubuntu-latest, "
            "2026-08-24/25), while its presence made the planner's own pre-filter "
            "unfireable, because a diagram's steps come from prose and nothing about it "
            "is decidable in advance - and its renderer was deleted with the Mermaid "
            "round trip on 2026-09-05."
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
        description="The planner emits a small object. It does not need the summarizer's budget.",
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
    asset_base_url: str = Field(
        default="",
        description=(
            "Where a browser asks for a published drawing. Empty means this site, and "
            "empty is what ships: the drawings sit in the bundle, and the bundle is what "
            "the 1 GB Pages ceiling counts. An absolute `https://` prefix moves the "
            "drawings a reader scrolls to off that ceiling, and the committed path is "
            "joined onto it unchanged - so which file is asked for never moves, only "
            "where it is asked for. Two costs, both measured 2026-09-02 against the "
            "candidate host: it caches for five minutes, so a repeat reader refetches, "
            "which is real on a slow connection; and the page's own `connect-src` gains "
            "that one origin, so the browser stops being the thing that makes reaching "
            "anywhere else impossible. Kept shut until the site's measured growth says "
            "otherwise."
        ),
    )

    @field_validator("asset_base_url")
    @classmethod
    def _the_valve_names_a_prefix_a_path_can_be_joined_onto(cls, value: str) -> str:
        """Empty, or an absolute `https://` prefix carrying no trailing slash.

        The value comes off our own config and never off the web (Rule #11), and
        it is checked all the same, because it is about to become the front half
        of every drawing address and the one origin the page's `connect-src`
        admits. A trailing slash is refused rather than trimmed: the join writes
        one, and trimming it silently is how an operator learns about the rule
        from a broken page instead of from a failed build.
        """
        if not value:
            return value
        if not value.startswith("https://"):
            raise ValueError("visuals.asset_base_url is empty or begins with https://")
        if value.endswith("/"):
            raise ValueError("visuals.asset_base_url carries no trailing slash")
        if any(character in value for character in " \t?#"):
            raise ValueError(
                "visuals.asset_base_url carries no whitespace, query or fragment"
            )
        return value

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


class AssembleConfig(Model):
    """What the published day does with the items a run finished.

    Its own group rather than a knob under `assist`, because `AppearanceConfig`
    imports `AssistConfig` whole: a threshold the pipeline applies once at build
    time would then also land in `config/appearance.json`, where it has no
    reader and no meaning.
    """

    duplicate_similarity_min: float = Field(
        default=0.94,
        ge=0.0,
        le=1.0,
        description=(
            "How alike two of a day's items have to be before they are one story. "
            "Cosine over the vectors the day already carries, and EVERY pair inside a "
            "group has to clear it - not only each item against the one it joined. "
            "NOT comparable to assist.similarity_floor: that one scores a reader's "
            "query against an item and this one scores two items against each other, "
            "so the two distributions are different shapes. Set by hand labels rather "
            "than by taste. Every group the pass forms over the eleven committed days "
            "was read and marked same-story or not, measured 2026-09-01 on Intel Core "
            "i7-1265U / Windows 11 / Python 3.14.2 over 3,978 items: at 0.93 one group "
            "of thirty is two different stories - Ontario's pushback against the lake "
            "renaming, merged into Google doing the renaming, at 0.9317 - and at 0.94 "
            "all twenty-two groups are one story each. The rule is the first round "
            "hundredth above the highest-scoring pair a person marked as two stories, "
            "which leaves a margin of 0.0083. That margin is thin, and the way to widen "
            "it is more labels rather than a higher number. Raising this costs missed "
            "duplicates, which a reader sees as the same story twice; lowering it costs "
            "a false merge, which is a story that never ran, so the two errors are not "
            "equal and this number leans high."
        ),
    )


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
    """Where a figure sits relative to the text it belongs to.

    `above` puts it before the text, `leading` beside the text on the side
    reading starts from, `trailing` after the text. A card is one column at
    every width the site ships, so `leading` cannot yet differ from `trailing`
    - a figure has no column of its own until the render spec is handed the
    width it will occupy (docs/concepts/design-system.md).
    """

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
        default_factory=lambda: [1, 7, 14, 30, 90],
        min_length=2,
        description=(
            "The day counts the console's window control offers, ascending and "
            "distinct. A short list rather than a slider: every value is a distinct "
            "fetch cost, because a wider window pulls more month files, and most "
            "values in between are indistinguishable on the page. "
            "`default_window_days` must be one of them, or the console would open on "
            "a window its own control cannot name. One day is the narrowest read the "
            "console can offer - one month file, and the run that has just finished - "
            "and it is the setting an operator wants when a run has gone wrong and "
            "the surrounding month is noise around it. It is also the only preset a "
            "reader can pick that reads no history at all."
        ),
    )
    today_anchor: TodayAnchor = Field(
        default=TodayAnchor.RIGHT,
        description="Where today sits in the initial viewport when enough history exists.",
    )
    pan_days: int = Field(default=7, ge=1, description="Days moved by one arrow-key pan.")
    zoom_factor: float = Field(default=1.5, gt=1.0)
    min_window_days: int = Field(
        default=1,
        ge=1,
        description=(
            "The narrowest span a preset may name. One, because the preset list "
            "offers a single day and a floor above it would refuse the list. It "
            "bounds the presets and nothing else - a reader sets the span through "
            "them and through no other control."
        ),
    )
    max_window_days: int = Field(
        default=366,
        ge=1,
        description=(
            "The widest span a preset may name, and through that the oldest month "
            "shard the pipeline may delete. It is a retention floor rather than a "
            "viewport clamp: the preset radio buttons are the only span control a "
            "reader can reach, so no page is held to this number and "
            "`observability` is - `AppConfig` refuses a cleanup age shorter than the "
            "months a window this wide can touch. Lowering it therefore does not "
            "make any page cheaper; it authorises deleting shards the console can "
            "still ask for, and a deleted shard draws as a gap that reads like a day "
            "the pipeline did nothing. Three hundred and sixty-six is a leap year, "
            "so a full year of history stays readable on every date."
        ),
    )
    min_attempts_for_rate: int = Field(
        default=5,
        ge=1,
        description="Below this count a rate is outlined because the denominator is thin.",
    )
    chart_height: int = Field(
        default=220,
        ge=120,
        description=(
            "The drawn height of a console chart, in CSS pixels. The same number "
            "`chart.height_px` carries: both were raised from 180 when the frame "
            "widened, because a chart that grows in one dimension only flattens its "
            "own signal. `config/appearance.json` owns the value, as "
            "`console.chart_height`."
        ),
    )
    chart_width: int = Field(
        default=760,
        ge=240,
        description=(
            "The width a console chart is drawn at on the server, in CSS pixels. A "
            "prerendered chart has no element to measure, and a chart drawn in "
            "arbitrary units and then stretched by its viewBox renders its labels at "
            "whatever the stretch factor happens to be - measured 2026-08-25, one page "
            "put the same font-size at 4.5px and at 16.6px. It is a seed rather than "
            "the final width: the client re-measures its container once a script runs, "
            "and the drawn SVG was its host's width to within a pixel at 1440, 768 and "
            "390 (measured 2026-09-01). 760 is the same number `chart.width_px` "
            "carries, so a console page has one answer to how wide a chart starts. "
            "`config/appearance.json` owns the value, as `console.chart_width`."
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
    source_rows: int = Field(
        default=10,
        ge=1,
        description=(
            "How many sources the console ranks by the articles their failures cost, "
            "before it states the tail in one sentence. Measured 2026-09-01 over the "
            "committed projection, a thirty-day window holds 60 sources with a loss, "
            "which is a list nobody reads to the end. Ten, matching the source-cut "
            "list above it."
        ),
    )
    feed_rows: int = Field(
        default=10,
        ge=1,
        description=(
            "How many failing feeds the console lists before it states the tail in one "
            "sentence. Measured 2026-09-01 over the committed ledger, 26 of 182 "
            "checked feeds have failed at least once. Ten, matching "
            "`console.source_rows`."
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
    doubt_rows: int = Field(
        default=10,
        ge=1,
        description=(
            "How many sources the Summaries route ranks by the summaries its "
            "faithfulness checker doubted, before it states the tail in one sentence. "
            "Measured 2026-09-01 over the committed score ledger, a thirty-day window "
            "holds 112 sources carrying at least one doubted summary and the worst ten "
            "hold 266 of the 1,047 doubts - so the tail is sources with a single doubt "
            "in a month, which nobody acts on. Ten, matching `console.source_rows` and "
            "`console.feed_rows`."
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
        default_factory=lambda: ["notice", "leads", "topics", "items"],
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
    visual_side: VisualSide = Field(
        default=VisualSide.TRAILING,
        description=(
            "Where a story's figure sits relative to its text. Nothing reads it yet, and "
            "the default is what `DigestItem.svelte` renders: the figure comes after the "
            "summary at every width. It stays reserved until the render spec is handed "
            "the width the figure will occupy, because a chart drawn at 825 x 437 is "
            "illegible in a 20rem column (docs/concepts/design-system.md). "
            "`config/appearance.json` owns the value, as `digest.visual_side`."
        ),
    )
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
    filter_min_chars: int = Field(
        default=2,
        ge=1,
        le=8,
        description=(
            "How many characters a reader types before an in-place filter narrows a "
            "list. It binds the day page and the archive, which share one panel since "
            "2026-09-01. Two rather than one because one letter narrows nothing: "
            "measured 2026-09-01 over the 12 committed days and 4,203 story titles - "
            "arithmetic over committed text, so the spread is zero by construction - "
            "the median single letter matches 80.2 percent of them and `e` matches 99.8 "
            "percent, against a median 0.8 percent for a two-letter pair. A first "
            "keystroke that redraws the page and removes almost nothing is work the "
            "reader watches for no answer. Over 8 the field stops narrowing anything a "
            "reader would think to type."
        ),
    )
    items_per_topic: int = Field(
        default=3,
        ge=1,
        deprecated=True,
        description=(
            "Retired 2026-09-01 and read by nothing. The all-topics page drew this many "
            "of each topic under a heading and put the rest behind a link, which on the "
            "431-story day of 2026-08-30 published 15 stories and hid 416. The leading "
            "block replaced the headings and the flat stream carries the whole day. "
            "Kept as a field, and dropped from the committed config, so a file written "
            "before today still validates - an unknown key is refused (section 11)."
        ),
    )
    leading_stories: int = Field(
        default=5,
        ge=1,
        description=(
            "The most stories the leading block may hold. They are chosen across the "
            "whole day, so the block is the page's first screen and the stream below it "
            "still carries every story in the published order."
        ),
    )
    leading_per_desk: int = Field(
        default=2,
        ge=1,
        description=(
            "The most leads one desk may hold. It matters more than it looks: 25 of the "
            "30 committed watchlist entries are technology companies, so the "
            "shared-subject term is structurally biased toward the AI and business "
            "desks, and this is the only thing holding it."
        ),
    )
    leading_min: int = Field(
        default=3,
        ge=1,
        description=(
            "The fewest leads worth drawing a block for. Under it nothing renders and "
            "the day goes straight to the stream, because four real leads beat five "
            "with one filler."
        ),
    )
    lead_cluster_floor: int = Field(
        default=3,
        ge=2,
        description=(
            "How many distinct sources must name one entity in their published titles "
            "before that shared subject counts for anything. Under it the term is zero. "
            "Measured 2026-09-01 over the 11 committed days and 4,086 items: at two "
            "sources 14.64 percent of stories sit in a cluster and at three it is 12.85 "
            "percent, so the stronger claim costs 73 stories in 11 days."
        ),
    )
    lead_shared_subject_weight: float = Field(
        default=0.2,
        ge=0.0,
        description=(
            "What a qualifying shared subject adds to a story's rank inside the leading "
            "block. It is a step and not a ramp: no measurement supports a shape, and a "
            "shape nobody measured may not justify a design (Rule #10). It must stay "
            "below what one more trade-press carrier is worth, which is "
            "collect.tier_weights.trade_press times collect.repetition_weight - 0.6 on "
            "the committed config - so a recurring subject cannot outrank a story two "
            "independent feeds carried today. Measured 2026-09-01: a second carrier "
            "fires on 4.49 percent of the stories that record it and a shared subject "
            "on 12.85 percent, 2.9 times as often, and 0.6 divided by 2.9 is 0.21."
        ),
    )
    lead_max_yesterday: int = Field(
        default=1,
        ge=0,
        description=(
            "The most leads the block may give to stories the feed dated to the "
            "previous calendar day. A day's leading stories are today's; one late "
            "arrival is a catch-up and three are yesterday's page."
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
    desk_thin_max: int = Field(
        default=12,
        ge=1,
        description=(
            "The most stories a desk may publish and still be called thin. A thin "
            "desk prints one sentence saying how many stories its sources offered "
            "and how many were too old to run; every other desk prints nothing, "
            "because a shortfall sentence under all five is a column of absences "
            "pretending to be information. Twelve is one page of the stream - what "
            "a reader sees before the first `Show more` - so a desk under it is a "
            "desk they see the whole of at once, which is where 'is this broken?' "
            "starts. Measured 2026-09-02 over the 12 committed days and 56 "
            "desk-days: 7 sit at or below it, 12.5 percent, and the record has a "
            "gap with nothing between 4 and 12 - so any value from 5 to 12 selects "
            "the same six startup desk-days and 12 adds the seventh. Arithmetic "
            "over committed payloads, so the spread is zero by construction."
        ),
    )
    shell_seed_items: int = Field(
        default=15,
        ge=1,
        description=(
            "How many of a day's stories a prerendered document carries. It is the "
            "one knob in this block a browser is never told, because the root "
            "layout inlines the rest of them into every document and a number no "
            "page reads would ride to every reader for ever. Fifteen covers the "
            "twelve a flat list pages at and the five the leading block draws. It "
            "is a floor rather than the whole answer: a lead is chosen across the "
            "whole day and is not inside any prefix, so the document has to carry "
            "those as well - measured 2026-09-01 on the 601-story day of "
            "2026-08-31, the five sat at positions 249, 285, 337, 344 and 493. "
            "Re-derive it when the block or the page size moves; do not raise it "
            "to cover a busy day, because the stories past the seed arrive by "
            "fetch. Measured 2026-09-01 on the 431-story day of 2026-08-30, gzip "
            "-9, Intel Core i7-1265U / Windows 11 / node 24.12.0: the first "
            "fifteen stories cost a dated route 20,302 bytes across the two "
            "documents it emits, against 420,074 for all 431."
        ),
    )
    payload_slow_ms: int = Field(
        default=1200,
        ge=250,
        le=30_000,
        description=(
            "How long a reader may wait for the rest of a day before the page says "
            "one sentence about it. The opposite of `shell_seed_items`: this is the "
            "one knob in this block only a browser reads, because the wait happens "
            "in the browser and a prerendered document is the only way to tell it "
            "anything. No spinner and no bar - a sentence, which is what a state a "
            "reader has to act on gets (docs/concepts/design-system.md). Under 250 "
            "ms the sentence fires on a fetch that was never slow, which teaches a "
            "reader to ignore it; over 30 s they have already decided the page is "
            "broken. Measured 2026-09-01 on Intel Core i7-1265U / Windows 11 / node "
            "24.12.0, Chromium against a local preview server: a 9,731-byte served "
            "day answered in 10.2 to 22.3 ms over 12 probes, median 13, so the "
            "default is about 90 times that median and cannot fire on a healthy "
            "fetch here. That is a server on the same machine and not a reader's "
            "connection, which is exactly why this is a knob and not a constant."
        ),
    )
    repo_url: str = Field(default="https://github.com/miztiik/yen-idhazh", min_length=1)
    site_title: str = Field(default="yen-idhazh", min_length=1)
    tagline: str = Field(
        default="A daily digest that checks its own work.",
        min_length=1,
    )
    read_mark_days: int = Field(
        default=14,
        ge=1,
        description=(
            "How far back a read mark is kept, counted in calendar days from today. "
            "Marks are held per digest date, so a mark made on one day can never "
            "grey out a different day's article, and every page load drops the dates "
            "that now sit outside this window. Fourteen days, the same span "
            "`archive_recent_days` lists, so the days the archive offers as rows of "
            "their own are exactly the days a reader can still see their own marks "
            "on. THIS RULE TRUSTS THE DEVICE CLOCK AND THE RULE IT REPLACED "
            "DELIBERATELY DID NOT: keeping the newest N dates present in the store "
            "needed no clock at all, and expiry by calendar cannot work without one, "
            "so a clock set wrong now keeps marks too long or drops them early. That "
            "is the price. It is worth paying because the old rule bounded the store "
            "by how often a reader came back rather than by time: a reader who opened "
            "one day a month kept marks from seven different months, and every one "
            "of them greyed out an article last seen most of a year ago. A wrong "
            "mark is the thing this store exists to avoid."
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
    archive_recent_days: int = Field(
        default=14,
        ge=1,
        le=31,
        description=(
            "How many of the newest published days the archive lists as rows of their "
            "own, each carrying the long date, the story count and whether every story "
            "finished. Every other day sits inside a disclosure for its month, so this "
            "block is the shortcut and never the only way in. Fourteen, and it matches "
            "`read_mark_days` for the same reason it matched it at seven: a row here is "
            "an invitation back to a day, and a day whose marks have already been "
            "dropped comes back looking unread. The two numbers move together or the "
            "block starts offering days it misrepresents. The ceiling is a month: "
            "above that the block is the wall of dates it replaced, and a month row "
            "already reaches any date in two clicks. Read by the build alone, like "
            "`shell_seed_items`, so it never rides to a reader."
        ),
    )
    archive_window_days: int = Field(
        default=30,
        ge=1,
        description=(
            "The span the archive's window control opens on, in days. IT MUST BE ONE "
            "OF `console.window_presets`, and `AppConfig` and `AppearanceConfig` both "
            "refuse a file where it is not - that is how the archive reuses the "
            "console's list of spans instead of declaring a second one, so the two "
            "surfaces cannot offer different day counts for the same idea. It names a "
            "span rather than a list for the reason `console.default_window_days` "
            "does: the list is the presets, and a second list is one more thing to "
            "keep in step. Thirty, because that is the span the console opens on and "
            "about the reach `assist.search_months` gives a search today, so the "
            "control ships opening on what the archive already costs. NOTHING READS "
            "IT YET - the control that will is row 25 of "
            "TODO/20260906-constant-cost-reads-plan.md. Read by the build alone, like "
            "`archive_recent_days`, so it never rides to a reader."
        ),
    )
    rail_group_minutes: int = Field(
        default=60,
        ge=1,
        le=1440,
        description=(
            "How coarse the day's time rail groups its stories. The rail draws one "
            "marker per group and none on the stories under it, so this is what "
            "decides how many times a reader is told the time. Measured 2026-09-02 "
            "over the 12 committed days and 4,713 stories, at 60 minutes: 907 markers "
            "instead of 4,713, so 80.8 percent of the labels are duplicates the rail "
            "does not draw. Sixty is the hour, which is the unit a reader already "
            "reads a clock in; 1440 is a whole day and 1 is a marker on almost every "
            "story, which is the state this knob exists to avoid."
        ),
    )
    offline_version: int = Field(
        default=1,
        ge=1,
        description=(
            "The version the offline reader carries. The site ships a service worker so "
            "a day already opened can be read again with no network, and this number is "
            "how a build says which worker it is. It is compared against "
            "`offline_retired_through`, and nothing else reads it. Raise it by one to "
            "bring the worker back after a retirement; leave it alone otherwise. Read "
            "by the build alone, like `shell_seed_items`, so it never rides to a reader."
        ),
    )
    offline_retired_through: int = Field(
        default=0,
        ge=0,
        description=(
            "The switch that turns the offline reader off and cleans up after it. Every "
            "worker whose `offline_version` is at or below this number unregisters "
            "itself and deletes every cache it owns, the first time it activates. Zero "
            "retires none, because the lowest version a worker can carry is one. This "
            "is the one thing a worker outliving the tab needs and an ordinary page "
            "does not: a way out that does not depend on the worker being well "
            "(docs/concepts/ui-shell.md). It is published as `service-worker-kill.json` "
            "at the site root, so a retirement can be pushed as one file. Read by the "
            "build alone, so it never rides to a reader."
        ),
    )
    offline_days_kept: int = Field(
        default=14,
        ge=1,
        le=366,
        description=(
            "How many opened days the offline reader keeps on the reader's device. The "
            "worker caches a day only after that day has been fetched once - it never "
            "prefetches a day nobody asked for - and this is what stops the kept set "
            "growing with the archive. Fourteen is two weeks, the same span "
            "`read_mark_days` keeps a read mark for, so a day a reader can still see "
            "their marks on is a day they can still open with no network. Measured "
            "2026-09-02 on Intel Core i7-1265U / Windows 11 / node 24.12.0 over the 12 "
            "served days: a day payload is 8,231 to 1,373,593 bytes uncompressed, "
            "median 727,622, so the full fourteen is about 10 MB at the median and "
            "about 19 MB at the largest. Arithmetic over committed payloads, so the "
            "spread is zero by construction. That 167-fold spread is why a day count "
            "cannot be the only bound - `offline_bytes_kept` is the other one. Read by "
            "the build alone, so it never rides to a reader."
        ),
    )
    offline_bytes_kept: int = Field(
        default=20_000_000,
        ge=2_000_000,
        le=100_000_000,
        description=(
            "The most bytes of cached day payloads the offline reader keeps on the "
            "reader's device. A SECOND BOUND BESIDE `offline_days_kept`, NOT A "
            "REPLACEMENT FOR IT, because a day count cannot bound bytes: measured "
            "2026-09-02 on Intel Core i7-1265U / Windows 11 / node 24.12.0 over the 12 "
            "served days, one day payload runs 8,231 to 1,373,593 bytes uncompressed, "
            "median 727,622 - a factor of 167 between the smallest day and the largest, "
            "so fourteen days is anything from 115 KB to 19 MB and the count alone "
            "promises the reader nothing. Twenty million bytes is 20 MB, just over the "
            "19,230,302 the day count already permits at the largest day measured, so "
            "on today's payloads the day count still binds first and this is the "
            "backstop for the day payloads grow. The floor is 2 MB, above the largest "
            "single day measured, so no reachable value can leave the cache unable to "
            "hold one day - a ceiling that evicts a day as fast as it arrives is worse "
            "than no cache, because the reader pays the download and keeps nothing. "
            "The ceiling is 100 MB, a little over twice the 43.2 MB the on-device "
            "search model and its runtime already take, because taking a tenth of a "
            "gigabyte of somebody's phone for a news digest is not a thing a config "
            "edit should be able to do quietly. NOTHING READS IT YET - the eviction "
            "rule that will is row 8 of TODO/20260906-constant-cost-reads-plan.md. "
            "Read by the build alone, so it never rides to a reader."
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

    @model_validator(mode="after")
    def _the_leading_block_can_reach_its_own_floor(self) -> Self:
        """A floor above the ceiling is a block that can never draw.

        Both numbers read as reasonable on their own, and the failure is silent:
        the block simply never appears and nothing says why.
        """
        if self.leading_min > self.leading_stories:
            raise ValueError("leading_min cannot exceed leading_stories")
        if self.leading_per_desk > self.leading_stories:
            raise ValueError("leading_per_desk cannot exceed leading_stories")
        return self


def refuse_an_archive_window_no_preset_offers(ui: UiConfig, console: ConsoleConfig) -> None:
    """The archive's opening span has to be one the shared preset list names.

    Checked here rather than on `UiConfig`, because the presets are
    `ConsoleConfig`'s and the two blocks cannot see each other. Both config
    documents call it, because both carry both blocks.

    This IS the reuse: the archive declares one span and no list of its own, so
    the only list of day counts in the contract is the console's. Let the two
    drift and the archive opens on a window neither control can name, which is
    the failure `console.default_window_days` is already checked against.
    """
    if ui.archive_window_days not in console.window_presets:
        raise ValueError("ui.archive_window_days must be one of console.window_presets")


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
            "cost is bounded at a single extra fetch. Seven, and it is this knob's own "
            "number rather than a borrowed one: it used to be justified as the week "
            "`ui.read_mark_days` and `console.min_window_days` also kept, and on "
            "2026-09-06 those moved to fourteen calendar days and to one day. What "
            "still holds is the measurement. At the observed rate of 353.5 items a day the "
            "extra fetch fires on the first 6 days of a month, 20 percent of them, "
            "and it fires only when the shard a search already reads is small: "
            "measured 2026-08-26, an entry costs 50.03 gzipped bytes of browse index "
            "and 249.79 of vector, so the two shards together on 1 September move "
            "about what the one shard on 30 September already moves. The bytes are "
            "levelled across the month rather than doubled."
        ),
    )
    recall_min: float = Field(
        default=0.68,
        ge=0.0,
        le=1.0,
        description=(
            "The regression bar for recall@result_limit over the committed query set, "
            "counted over right answers that carry a vector, scored against the corpus "
            "pinned by eval_corpus_through. Coverage is excluded on purpose: an item "
            "the pipeline never embedded cannot be retrieved at any threshold, so "
            "counting it here would fail this gate for a defect in another stage. Set "
            "two standard errors below the pinned baseline of 0.756 +/- 0.037 (n=60) "
            "over the 2,237 items published through 2026-08-26, of which 2,235 carry a "
            "vector: 0.756 - 2 x 0.037 = 0.682, rounded to two places as 0.68. "
            "Measured 2026-09-04 on Windows 11, 12 logical CPUs, onnxruntime 1.29.0. "
            "THIS BAR NO LONGER HAS AN EXPIRY DATE, and that is the whole point of the "
            "pin. The two earlier versions of this number, 0.85 and 0.69 and then 0.61, "
            "each expired within days because they were measured against a corpus that "
            "kept growing under them. Both inputs are now fixed, so the number moves "
            "only when the ranking moves or the labels are completed - and completing "
            "the labels raises it rather than eroding it. It is still a LOWER BOUND: "
            "66.6 percent of filled slots hold an item no labeller judged either way, "
            "and every one of them is counted as a wrong answer. `config/idhazh.json` "
            "owns the value. This is a pipeline gate rather than a drawn surface: the "
            "one reader is `backend/tests/test_retrieval_eval.py`, and the frontend's "
            "own `AssistConfig` does not declare the field at all. See "
            "docs/concepts/evaluation.md."
        ),
    )
    eval_corpus_through: str | None = Field(
        default="2026-08-26",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description=(
            "The last published day the retrieval gate scores against, as YYYY-MM-DD. "
            "Set to the day the label set was pooled, so the gate's competitor set is "
            "the one the labellers saw. THIS IS THE FIX FOR A GATE THAT USED TO EXPIRE. "
            "Scored against the live archive, recall@10 measures two things at once: "
            "the ranking, and how many stories were published since the labels were "
            "written. Only the first is something a merge candidate can change. The "
            "second is unbounded and monotone - the result list holds ten slots, the "
            "archive grew about 654 items a day through 2026-09, and every new item "
            "that outranks a gold item evicts it - so the numerator erodes while the "
            "denominator, min(gold_with_vector, slots), does not move at all. Measured "
            "at -0.00004793 recall per published item, which is 0.031 a day: one "
            "publishing day moved the instrument 39 percent of the eight-point effect "
            "the gate exists to catch, and three days exceeded it with no code change. "
            "The gate failed twice in five days for that reason alone, the second time "
            "on a commit that changed one markdown file. Pinned, the drift term is zero "
            "and recall_min measures ranking. Null reads the whole archive, which is "
            "what the printed diagnostic beside the gate reports, because that number "
            "is what a reader actually gets. Ruled by Fowler and Carmack independently, "
            "2026-09-04; the reasoning is in docs/concepts/evaluation.md."
        ),
    )


class AppConfig(Contract):
    """`config/idhazh.json` - every tunable, schema-validated."""

    __schema_stem__: ClassVar[str] = "app-config"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-09-06T22:30",
            change=(
                "run.safety_ceiling_per_run default lowered from 160 to 80, and "
                "run.shard_timeout_minutes default raised from 150 to 200. Both are "
                "defaults on RunConfig; an older config that names either value keeps "
                "it."
            ),
            why=(
                "The ceiling is now an editorial cap: a day publishes half as many "
                "stories, and the 80 slots go to articles worth reading rather than to "
                "a duplicate or a badly-publishing feed (owner, 2026-09-05). The "
                "timeout rise is headroom for the coming two-call summariser change, "
                "not a response to a slower worker - at 80 items a worker draws 20 and "
                "the base work roughly halves; the bound is sized from the worst "
                "measured shard, 135.4 of the old 150 minutes over 80 rows on "
                "2026-09-02, not the median 78.5."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T21:40",
            change=(
                "collect.dedup_similarity_min added, defaulting to 0.94 and bounded to "
                "[0.0, 1.0], and collect.dedup_enforce added, defaulting to false. "
                "Together they drive a plan-stage pass that finds a day's same-story "
                "repeats across sources by cosine over headline-and-lead vectors. "
                "Additive: an older config validates and takes the defaults."
            ),
            why=(
                "The same story at two addresses was planned twice: the exact-url "
                "collapse only joins identical addresses, and two outlets carrying one "
                "story carry two addresses. The pass ships record-only (dedup_enforce "
                "false), so a day's duplicate rate is written to the run log and read "
                "before any cut is turned on. The threshold reuses "
                "assemble.duplicate_similarity_min rather than minting a second number "
                "for the same question one stage earlier."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T17:00",
            change=(
                "collect.reliability_window_days added, defaulting to 30 and refused "
                "below 30, and collect.reliability_floor added, defaulting to 0.5 and "
                "bounded above 0.0 and at most 1.0. Together they drive a per-feed "
                "reliability factor - productive reads over evidence-bearing reads in "
                "the trailing window - that scales a feed's authority inside "
                "rank.authority, clamped to [floor, 1.0]. Additive: an older config "
                "validates and takes the defaults."
            ),
            why=(
                "A feed that fails or parses to nothing kept scoring as though it had "
                "published, because authority read only its tier and its hand-set "
                "weight. The factor is derived from the committed feed-health record "
                "rather than hand-tuned, it only ever reduces (the clamp caps it at "
                "1.0), and a feed with no evidence in the window scores 1.0 so an "
                "untested or politely-refused feed is never punished. The window bounds "
                "the read (Rule #12) and the floor bounds the cut at two-to-one."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T16:00",
            change=(
                "observability.tracing_enabled default moves from false to true. A "
                "work shard now builds a span tree unconfigured, writes it to the "
                "committed trace under state/traces/, and folds it into the span "
                "rollup. The committed config sets the same value, so a fresh clone "
                "and the shipped file still agree."
            ),
            why=(
                "The owner turned tracing on by default (2026-09-06): the span tree "
                "and the committed rollup are worth their runner cost, which Carmack "
                "measured negligible. It is safe to run in CI because the sink is the "
                "committed file and nothing else - no host, no key - and the closed "
                "attribute vocabulary keeps article text out of every span (Rule #11). "
                "The move is additive: the committed config sets the value explicitly, "
                "so no persisted config changes meaning and no read-side migration is "
                "needed."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T15:00",
            change=(
                "observability.trace_window_days added, defaulting to 7. It bounds "
                "state/traces/, the raw span traces kept so an operator can open a "
                "recent run; a trace whose published day is more than that many days "
                "behind today is deleted whole. Additive - an older config validates "
                "and takes the default."
            ),
            why=(
                "Raw traces are evidence with a short life while the span rollup is the "
                "record, so the traces need a rolling window of their own. A trace is a "
                "lookup an operator opens, so it is deleted rather than folded - a fold "
                "would invent a total nobody reads. Seven days is measured at about "
                "0.6 MB a run over five runs a day, which bounds the tree at about "
                "21 MB whatever the project's age (Rule #12)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T14:00",
            change=(
                "ui.read_mark_days moves from 7 to 14, and its meaning moves from 'the "
                "newest 7 dates the store holds' to '14 calendar days back from today'. "
                "ui.archive_recent_days moves from 7 to 14. console.window_presets "
                "gains a 1-day span and is now [1, 7, 14, 30, 90]; console.min_window_days "
                "moves from 7 to 1 so the new preset satisfies the existing range check. "
                "console.max_window_days keeps 366 and gains a description. Two fields "
                "are added: ui.offline_bytes_kept, defaulting to 20,000,000 and bounded "
                "at 2,000,000 and 100,000,000, and ui.archive_window_days, defaulting to "
                "30 and refused unless it names one of console.window_presets. The "
                "shapes are `UiConfig` and `ConsoleConfig`, which this document and "
                "`AppearanceConfig` share, so both schemas moved together. Every value "
                "legal before today is legal now and both new fields carry defaults, so "
                "a config written before today still validates and no read-side "
                "migration is owed."
            ),
            why=(
                "Read marks expired by position rather than by time. Keeping the newest "
                "7 dates the store happens to hold needs no clock, which was the point, "
                "but it bounds the store by how often a reader comes back instead of by "
                "how long ago they read: a reader who opens one day a month kept marks "
                "from seven different months, and each of them greyed out an article "
                "last seen most of a year ago. Fourteen calendar days trusts the device "
                "clock, which the old rule deliberately did not, and that cost is "
                "stated in the field itself rather than hidden - a clock set wrong now "
                "keeps marks too long or drops them early. A wrong mark is what the "
                "store exists to avoid, so the trade is taken (owner decision, "
                "2026-09-06). THE STATED RULE AND THE SHIPPED PRUNING ARE ONE COMMIT "
                "APART ON PURPOSE: this document is the contract for every row of "
                "TODO/20260906-constant-cost-reads-plan.md, so the knobs land once and "
                "no later row edits the config file. Row 4 of that plan changes "
                "frontend/src/lib/readstate.ts to prune by calendar. Until it merges "
                "the browser still keeps the newest 14 dates, which is a superset of "
                "the 14-day window and therefore never hides a mark a reader should "
                "still see. ui.archive_recent_days follows to 14 for the reason it "
                "matched read_mark_days at 7: a row in that block invites a reader back "
                "to a day, and a day whose marks were already dropped comes back "
                "looking unread. The presets gain one day because every span is a "
                "distinct fetch cost - a window pulls a month file per month it reaches "
                "- and there was no way to ask for the cheapest read of all, the run "
                "that has just finished. min_window_days drops to 1 to admit it. "
                "max_window_days does not move, and the description now says why: it is "
                "a retention floor rather than a viewport clamp, the only span control "
                "a reader can reach is the preset list, and lowering it would authorise "
                "deleting month shards the console can still ask for. "
                "ui.offline_bytes_kept exists because offline_days_kept cannot bound "
                "bytes: measured 2026-09-02 over the 12 served days, one day payload "
                "runs 8,231 to 1,373,593 bytes, a factor of 167, so fourteen days is "
                "anything from 115 KB to 19 MB. ui.archive_window_days names a span out "
                "of console.window_presets rather than declaring a second list of day "
                "counts, so the contract holds exactly one list of spans and the two "
                "surfaces cannot drift. Neither new knob has a reader yet; rows 8 and "
                "25 of the same plan are the readers."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06T12:00",
            change=(
                "visuals.asset_base_url is added. It defaults to the empty string, which "
                "means this site, and is otherwise an absolute https prefix carrying no "
                "trailing slash, no query and no fragment."
            ),
            why=(
                "The published site has a 1 GB ceiling and the drawings are the part of it "
                "that grows with every day. This is the release valve for that: an "
                "operator names a host, the drawings a reader scrolls to are asked for "
                "there instead, and the bytes stop counting against the ceiling - one "
                "config edit rather than a project. It ships shut because nothing yet says "
                "the bytes must move, and opening it costs something measured: the "
                "candidate host caches for five minutes, so a repeat reader refetches, and "
                "the page's connect-src has to admit that one origin. Additive and "
                "backwards-compatible, so no read-side migration is owed - a config "
                "written before this loads on the default and every drawing is asked for "
                "at exactly the address it was asked for before."
            ),
        ),
        ChangelogEntry(
            version="2026-09-06",
            change=(
                "retention.pages_hard_cap_mb is added. It defaults to the 1024 MB the "
                "published-site gate already failed at, and is bounded ge=1, le=1024."
            ),
            why=(
                "The cap was a module constant in backend/idhazh/retention.py, so the one "
                "number that stops a deploy could not be read out of config or tightened "
                "without a source edit. The bound is what makes exposing it safe: config "
                "can only ever lower the cap, which is Rule #2's 'the budget is the "
                "platform, not a preference' held by the schema rather than by trusting "
                "nobody to edit a constant. Additive and backwards-compatible, so no "
                "read-side migration is owed - a config written before this loads on the "
                "default and the gate fires at exactly the size it fired at before."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T18:00",
            change=(
                "VisualKind, which types visuals.enabled_kinds, lost diagram and image. A "
                "config naming either value no longer loads."
            ),
            why=(
                "The diagram renderer went with the Mermaid round trip it read, and image "
                "never had a renderer at all (pseudo-plan row 63), so a config could ask "
                "for a kind nothing could draw. No read-side migration is owed: the "
                "committed config/idhazh.json names chart alone, which is the only value "
                "left, so the shipped file loads unchanged."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T14:00",
            change=(
                "models.route is renamed models.visual_planner, run.route_budget_minutes "
                "is renamed run.visual_planner_budget_minutes, and finetune.student now "
                "names visual_planner. finetune.teacher and finetune.student are typed "
                "ModelRole rather than Slug. Breaking: three key spellings changed. The "
                "read-side migration is a before-validator on ModelsConfig, RunConfig and "
                "FinetuneConfig that reads the old spelling as the new one and refuses a "
                "file carrying both with different values, so a config written before "
                "today still loads. No value moved: the weights, the revision, the sha256 "
                "and the 40 minutes are the numbers they were yesterday."
            ),
            why=(
                "Route names a dispatch decision and the stage names a planning "
                "decision, so every knob spelling it teaches the wrong word. It is paid "
                "now rather than later because twenty more plans are about to mint names "
                "against these keys, and each one would write the wrong name and then pay "
                "to change it (owner decision 2026-09-05). ModelRole replaces Slug "
                "because these two fields spell a key in models, a key in models is a "
                "Python attribute name, and an attribute name is snake_case - so Slug's "
                "kebab-case was a shape no key could ever have, and visual_planner would "
                "have been refused by the pattern before the check that matters ran. "
                "AppConfig already checks the name against the real block, so the pattern "
                "only has to bound the shape for an editor reading schemas/ offline."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T13:00",
            change=(
                "console.chart_height now defaults to 220 rather than 180 and "
                "console.chart_width to 760 rather than 600, and both carry a "
                "description naming their owner. The committed config/idhazh.json "
                "drops both keys; config/appearance.json keeps them. "
                "config/appearance.json drops assist.recall_min, which this document "
                "keeps at 0.68. The shapes are `ConsoleConfig` and `AssistConfig`, "
                "which this document and `AppearanceConfig` share, so both schemas "
                "moved together. A semantic shift on two defaults and nothing else - "
                "every value legal yesterday is legal today, and a config/idhazh.json "
                "written before today still declares the two console sizes and still "
                "wins over the new defaults through the frontend's middle merge "
                "layer, so no read-side migration is owed."
            ),
            why=(
                "Three keys were declared in both config files with two different "
                "values. The frontend merges the appearance block last, so the "
                "appearance file wins and the loser is silent. The two console sizes "
                "are drawn by the console pages and by nothing in backend/, so "
                "config/appearance.json owns them - the same rule that settled "
                "visual_side on 2026-09-05, and the rule backend/idhazh/config.py "
                "already follows when it reads console.max_window_days out of the "
                "appearance file. The defaults follow what ships: 220 and 760 are the "
                "numbers chart.height_px and chart.width_px already carry, raised from "
                "180 and 600 when the frame widened, so a fresh clone with no config "
                "would have drawn a console chart at a size no console page uses. "
                "assist.recall_min runs the other way. It is a gate on the ranking "
                "that only backend/tests/test_retrieval_eval.py reads, off this "
                "document, at 0.68; the frontend's AssistConfig does not declare the "
                "field, so the 0.61 in config/appearance.json had no reader at all. It "
                "was the value the bar held before it was re-derived against the "
                "pinned corpus on 2026-09-04, and 0.07 of drift is 10.3 percent of the "
                "live bar - worth nothing today and a wrong gate the day anything "
                "reads the appearance copy."
            ),
        ),
        ChangelogEntry(
            version="2026-09-05T12:00",
            change=(
                "ui.visual_side now defaults to trailing rather than above, and carries a "
                "description. The shape is `UiConfig`, which this document and "
                "`AppearanceConfig` share, so both schemas moved together. The value is "
                "dropped from the committed config/idhazh.json; config/appearance.json "
                "keeps it as digest.visual_side. A semantic shift on the default and "
                "nothing else - every value that was legal yesterday is legal today, so a "
                "file written before today still validates and owes no read-side "
                "migration."
            ),
            why=(
                "Two files declared one knob with two values: config/idhazh.json said "
                "above and config/appearance.json said trailing. That is the whole "
                "divergence between the two - the legacy ui block is a 16-key subset of "
                "the appearance digest block's 26, and visual_side was the only one of "
                "the 16 whose value disagreed. The published surface is drawn from "
                "config/appearance.json (docs/concepts/config.md), so the appearance file "
                "wins and the pipeline file drops its copy. The default follows the "
                "committed value because above is the one thing the page does not do: "
                "`DigestItem.svelte` renders the figure after the summary, so a fresh "
                "clone with no config would have resolved to a position no page renders."
            ),
        ),
        ChangelogEntry(
            version="2026-09-04T20:00",
            change=(
                "Added assist.eval_corpus_through, default 2026-08-26. Removed "
                "assist.recall_tolerance, added the same day and never released. "
                "assist.recall_min re-derived against the pinned corpus, 0.61 to 0.68."
            ),
            why=(
                "The retrieval gate scored against the live archive, so it measured the "
                "ranking and the publishing rate at once. The result list holds ten "
                "slots and the archive grew about 654 items a day, so every new item "
                "that outranked a gold item evicted it: the numerator eroded at "
                "-0.00004793 recall per published item while the denominator did not "
                "move. One publishing day shifted the instrument 39 percent of the "
                "eight-point effect the gate exists to catch, so no constant bar could "
                "survive - it failed twice in five days, the second time on a commit "
                "that changed one markdown file. The tolerance band bought 1.8 days and "
                "was the wrong shape; a band around a drifting number is a looser bar, "
                "not a stable one. Pinned, the drift term is zero, the bar rises from "
                "0.61 to 0.68, and it stops expiring. Ruled by Fowler and Carmack "
                "independently, 2026-09-04."
            ),
        ),
        ChangelogEntry(
            version="2026-09-04T18:00",
            change=(
                "Added assist.recall_tolerance, default 0.10. The retrieval gate now "
                "compares recall against recall_min x (1 - recall_tolerance) rather "
                "than against recall_min itself."
            ),
            why=(
                "recall@10 is measured over 60 queries with a standard error near "
                "0.046, so a bar at the measurement's own edge decides on noise. It "
                "failed on 2026-09-04 at 0.604 against 0.610 - inside the error bar - "
                "on a commit that changed one markdown file. The drift underneath is "
                "not a search regression: the gold set is frozen while the competitor "
                "set grows about 654 items a day, so a new item outscoring a gold item "
                "evicts it from the ten slots. At -0.00004793 recall per published "
                "item this band is worth 1,148 items, or 1.8 days - it buys time to "
                "pin the eval corpus, which is the fix, and it is deleted when that "
                "lands. Owner decision, 2026-09-04."
            ),
        ),
        ChangelogEntry(
            version="2026-09-03T18:00",
            change=(
                "collect.quarantine_after_failures removed, and the two "
                "observability names that were still readable in code - keep_months "
                "and hard_delete_after_months - removed with it. The rest rule now "
                "reads collect.availability_strikes_before_rest, and the telemetry "
                "fold reads observability.item_health_full_grain_months and "
                "observability.item_health_aggregate_keep_months. A config still "
                "spelling any of the three is refused, and the message names the knob "
                "to use instead."
            ),
            why=(
                "The three names were compatibility shims, kept readable only until "
                "every reader had moved. They have all moved, so keeping the shims "
                "means the emitted config says the same thing twice and an operator "
                "cannot tell which copy decides. No behaviour changes here and none "
                "could: the committed config carries 5 under both collect names and "
                "the tuned fixture carries 3 under both, so every reader reads the "
                "number it read yesterday. Refusing beats ignoring, because a knob an "
                "operator edits and nothing reads is a value they believe (Rule #6). "
                "The payload read migration for VerticalPlan.live_feeds stays, because "
                "a committed payload cannot be rewritten (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T22:00",
            change=(
                "observability.keep_months and observability.hard_delete_after_months "
                "removed, and six named ages added: item_health_full_grain_months 14, "
                "item_health_aggregate_keep_months null, feed_health_keep_months 14, "
                "scores_full_grain_months 14, score_archive_keep_months null and "
                "public_telemetry_keep_months 14. A config still carrying either old "
                "name loads and resolves to those defaults; carrying an old name "
                "beside its successor is refused. Every full-grain window is checked "
                "against the month shards console.max_window_days can select."
            ),
            why=(
                "One name covered state/item-health/ while state/feed-health/, "
                "state/scores/ and frontend/public/telemetry/ had no cleanup age at "
                "all, so three stores grew with nothing to stop them. Its value was "
                "also one shard short: the old check compared months * 30 against the "
                "console window instead of the shards that window selects, and a "
                "366-day read walks 367 inclusive days, which can fall in fourteen "
                "calendar months. The old value is read and dropped rather than "
                "carried forward, because it was chosen against a check that could not "
                "answer the question."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T20:00",
            change=(
                "collect.availability_strikes_before_rest, collect.availability_rest_runs, "
                "collect.feed_http_410_runs_before_retirement, "
                "collect.robots_denied_recheck_runs, "
                "collect.robots_unreachable_recheck_runs and "
                "collect.source_yield_min_complete_days added, defaulting to 5, 5, 5, 1, 1 "
                "and 30. Additive with defaults, so a config written before today still "
                "validates. Nothing reads them yet, and collect.quarantine_after_failures "
                "still decides every rest."
            ),
            why=(
                "The source lifecycle is four different questions - may we ask, does the "
                "address work today, is the address gone for good, and does the source "
                "publish anything worth reading - and one knob answered all of them. "
                "Naming each one first means the changes that read them are reviewable "
                "as behaviour rather than as a knob and a behaviour at once "
                "(docs/architecture/sources/health.md)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T18:00",
            change=(
                "ui.offline_version, ui.offline_retired_through and ui.offline_days_kept "
                "added, defaulting to 1, 0 and 14. The shape is `UiConfig`, which this "
                "document and `AppearanceConfig` share, so both schemas moved together. "
                "Additive with defaults, so a config written before today still "
                "validates."
            ),
            why=(
                "The site ships a service worker, so a day a reader has already opened "
                "can be read again with no network. A worker is the only code this "
                "project ships that outlives the tab, so the switch that turns it off "
                "is a contract rather than a code edit: `offline_retired_through` "
                "retires every worker at or below the version it names, and a retired "
                "worker unregisters itself and deletes every cache it owns. "
                "`offline_days_kept` bounds what the worker keeps, because a cache that "
                "grows with the archive is the failure that argued against caching days "
                "at all (Rule #6, docs/concepts/ui-shell.md)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T16:00",
            change=(
                "ui.desk_thin_max added, defaulting to 12, floored at 1. The shape is "
                "`UiConfig`, which this document and `AppearanceConfig` share, so both "
                "schemas moved together. Additive with a default, so a config written "
                "before today still validates."
            ),
            why=(
                "A desk now publishes why it ran what it ran, and one sentence under "
                "every desk would be a column of absences rather than information. This "
                "is the line between a desk that explains itself and a desk that says "
                "nothing, and a component may not spell it (Rule #6). Twelve is one "
                "page of the stream, so a desk under it is one a reader sees the whole "
                "of at once. Measured 2026-09-02 over the 12 committed days and 56 "
                "desk-days: 7 sit at or below it, 12.5 percent, and nothing in the "
                "record sits between 4 and 12."
            ),
        ),
        ChangelogEntry(
            version="2026-09-02T14:00",
            change=(
                "ui.rail_group_minutes added, defaulting to 60, bounded at 1 and 1440. "
                "The shape is `UiConfig`, which this document and `AppearanceConfig` "
                "share, so both schemas moved together. Additive with a default, so a "
                "config written before today still validates."
            ),
            why=(
                "The day's stories now run newest first down a time rail, and the rail "
                "draws one marker per group of stories rather than one per story. How "
                "coarse a group is decides how many times a reader is told the time, "
                "and a page may not spell that (Rule #6). Measured 2026-09-02 on Intel "
                "Core i7-1265U / Windows 11 / Python 3.14.2 over the 12 committed days "
                "and 4,713 stories, at the 60-minute default: 907 markers rather than "
                "4,713, so the rail leaves out 80.8 percent of the labels a "
                "marker-per-story rail would print. The busiest day, 2026-09-01, draws "
                "33 markers over 627 stories."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T20:00",
            change=(
                "ui.archive_recent_days added, defaulting to 7, bounded at 1 and 31. "
                "The shape is `UiConfig`, which this document and `AppearanceConfig` "
                "share, so both schemas moved together. Additive with a default, so a "
                "config written before today still validates."
            ),
            why=(
                "The archive listed every published day as a link and had nothing "
                "bounding it. At the 700 days this archive reaches in two years that "
                "is a wall of dates a reader has to scan past to get to the stories. "
                "It is now the newest few days as rows over one disclosure a month "
                "and one a year before this one, so the list a reader SEES grows "
                "twelve rows a year instead of 365. How many days stay out is a "
                "choice a page may not spell (Rule #6), and the ceiling is what makes "
                "the knob safe: set to 400 it is the wall again. Read by the build "
                "alone, so it never rides to a reader. What the DOCUMENT costs did not "
                "fall to nothing and is not claimed to: measured 2026-09-01 on Intel "
                "Core i7-1265U / Windows 11 / node 24.12.0, over two fixture archives "
                "of the same 24 months at 700 and 182 published days, gzip -9 of the "
                "prerendered /archive/ document, the page grew 11.05 bytes a day "
                "before and 8.0 after - 27.7 percent slower, not flat, because a link "
                "for every day is what a reader with no script uses to reach one "
                "(docs/reference/measurements.md)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T18:00",
            change=(
                "page_weight.ceilings_bytes moved /console/ from 251,324 to 276,828, "
                "/console/model/ from 29,273 to 37,979 and /console/machine/ from "
                "31,714 to 39,743, in config/idhazh.json. No field moved and no "
                "default changed, so a config written before today still validates."
            ),
            why=(
                "The console chart-craft plan closed and all three numbers were "
                "derived on a tree twenty-six rows older. Nothing had crossed: the "
                "pages measured 142,623, 27,744 and 29,599 against ceilings of "
                "251,324, 29,273 and 31,714. What expired is the runway. A ceiling "
                "here is the heaviest of five builds plus seven published days at the "
                "measured per-day rate plus the 64-byte build noise floor, and "
                "/console/model/ had 1,529 bytes of slack left - 1.05 publishes - "
                "with /console/machine/ at 1.47. The raise decomposes into a page "
                "term and a rate term that sum to it exactly: +26,470 and -966 for "
                "/console/, +6,788 and +1,918 for /console/model/, +6,489 and +1,540 "
                "for /console/machine/. Measured 2026-09-01 on i7-1265U, Windows 11, "
                "node v24.12.0, twelve published days; see "
                "docs/reference/measurements.md."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T14:00",
            change=(
                "ui.filter_min_chars added, defaulting to 2. The shape is `UiConfig`, "
                "which this document and `AppearanceConfig` share, so both schemas "
                "moved together. Additive with a default, so a config written before "
                "today still validates."
            ),
            why=(
                "The day page's filter and the archive's topic pills became one panel, "
                "and the archive's field now narrows the loaded list as a reader types "
                "- so the same rule governs two surfaces and may not be spelled in "
                "either of them (Rule #6). Two rather than one because one letter "
                "narrows nothing: measured 2026-09-01 over the 12 committed days and "
                "4,203 story titles, the median single letter matches 80.2 percent of "
                "them and `e` matches 99.8 percent, against a median 0.8 percent for a "
                "two-letter pair."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T13:00",
            change=(
                "console.doubt_rows added, defaulting to 10. The shape is "
                "`ConsoleConfig`, which this document and `AppearanceConfig` share, "
                "so both schemas moved together. Additive with a default, so a "
                "config written before today still validates."
            ),
            why=(
                "The Summaries route now ranks sources by how often the faithfulness "
                "checker doubted their summaries, and an uncapped ranking is a page "
                "nobody reads to the end: measured 2026-09-01 over the committed "
                "score ledger, a thirty-day window holds 112 sources with a doubted "
                "summary. The cap is a knob rather than a literal for the same reason "
                "`source_rows` and `feed_rows` are (Rule #6), and it takes their "
                "default so three ranked lists on one console do not each end at a "
                "different depth."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T12:30",
            change=(
                "ui.leading_stories, ui.leading_per_desk, ui.leading_min, "
                "ui.lead_cluster_floor, ui.lead_shared_subject_weight and "
                "ui.lead_max_yesterday added, defaulting to 5, 2, 3, 3, 0.2 and 1. "
                "ui.items_per_topic is deprecated, read by nothing, and dropped "
                "from the committed file. The shape is `UiConfig`, which this "
                "document and `AppearanceConfig` share, so both schemas moved "
                "together."
            ),
            why=(
                "The day gets a leading block, and every number that decides it is "
                "a knob rather than a literal in a stage (Rule #6). The block "
                "replaces the three-per-topic headings, which on the 431-story day "
                "of 2026-08-30 drew 15 stories and put 416 behind five links - so "
                "items_per_topic lost its only reader. The field stays so a config "
                "written before today still validates, because an unknown key is "
                "refused; nothing reads it and the committed file no longer sets it "
                "(section 11). Every addition carries a default, so a file written "
                "before today still validates either way."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T10:00",
            change=(
                "ui.payload_slow_ms added, defaulting to 1200. The shape is "
                "`UiConfig`, which this document and `AppearanceConfig` share, so "
                "both schemas moved together. Additive with a default, so a config "
                "written before today still validates."
            ),
            why=(
                "The rest of a day is about to arrive by fetch, so for the first "
                "time a reading page can be waiting on something. What it shows "
                "meanwhile is one sentence past this number - never a spinner and "
                "never a bar, because the first frame is already readable and a "
                "compressed response cannot report a byte count worth printing. "
                "This is the one knob in the block only a browser reads: "
                "`shell_seed_items` is decided at build time and never told to a "
                "reader, and this one is the exact opposite, because the wait it "
                "bounds happens in the reader's browser."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T09:00",
            change="Added the assemble group and its duplicate_similarity_min knob.",
            why=(
                "The published day now groups its own items on the vectors it already "
                "carries, so a reader is not shown the same story eight times, and the "
                "cosine that decides it is a tuning knob rather than a literal (Rule "
                "#6). Its own group because `AppearanceConfig` imports `AssistConfig` "
                "whole: filing a build-time threshold there would publish it to a "
                "config the browser reads, where nothing can act on it. Additive with "
                "a default, so a config written before today still loads (section 11)."
            ),
        ),
        ChangelogEntry(
            version="2026-09-01T02:00",
            change=(
                "console.source_rows and console.feed_rows added, both defaulting to "
                "10. The shape is `ConsoleConfig`, which this document and "
                "`AppearanceConfig` share, so both schemas moved together."
            ),
            why=(
                "Two console lists gained a cap on the same day, and a cap a "
                "component hardcodes is one an operator cannot move (Rule #6). The "
                "failure section now ranks sources by the articles their failures "
                "cost the digest; measured 2026-09-01 over the committed "
                "projection, a thirty-day window holds 60 sources with a loss, so "
                "an uncapped ranking is a list nobody reads to the end. The feed "
                "list had no cap at all and draws 26 of 182 checked feeds. "
                "Additive with defaults, so a config written before today still "
                "validates (section 11)."
            ),
        ),
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
    assemble: AssembleConfig = Field(default_factory=AssembleConfig)
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

    @model_validator(mode="after")
    def _the_archive_opens_on_a_span_the_presets_name(self) -> Self:
        refuse_an_archive_window_no_preset_offers(self.ui, self.console)
        return self

    @model_validator(mode="after")
    def _no_cleanup_age_is_shorter_than_the_console_can_ask_for(self) -> Self:
        """Every full-grain window outlives the widest read the console offers.

        Checked here because `ObservabilityConfig` cannot see `console`, and the
        failure is the worst kind: a shard is deleted, a reader pans back to it
        months later, and the page draws a gap that reads as a day the pipeline
        did nothing. `config.load` runs the same check again against
        `config/appearance.json`, which is the file the published console
        actually reads its window from.
        """
        self.observability.refuse_windows_shorter_than(
            months_a_window_can_touch(self.console.max_window_days),
            window_days=self.console.max_window_days,
        )
        return self
