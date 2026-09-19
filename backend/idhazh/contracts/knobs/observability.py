"""What the pipeline records about itself, and what an operator may switch off."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model
from idhazh.contracts.knobs.removed import refuse_a_removed_knob


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


#: The `observability` names this block used to carry, and the knob that governs
#: the same store now. An empty value means the store itself is gone.
SUPERSEDED_RETENTION_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "keep_months": "item_health_full_grain_months",
        "hard_delete_after_months": "item_health_aggregate_keep_months",
        "public_scores_keep_months": "",
        "public_feed_health_keep_months": "",
        "runtime_counters_scrape": "",
    }
)


class LoggingConfig(Model):
    """Which records the pipeline builds, and how loud the logger that prints them is.

    Those are two different questions and this block holds both. **The flags
    choose which records EXIST; `level` chooses how loud the logger is.** Turning
    the level down to WARNING does not stop a per-item record being built, and
    turning it up to DEBUG does not create one.

    One switch would not have done. Per-item lines cost a few hundred bytes a
    run and prompt capture costs a run artifact, so an operator has to be able to
    keep the cheap instrument and drop the expensive one. That is why there are
    five flags here rather than a verbosity dial (Fowler, 2026-09-14).

    Every flag defaults ON, because the reason they exist is a 5x model-time
    regression that ran for six days with nothing printing during a 200-minute
    shard. They are defaulted on to be switched off once that is closed, so
    **every one of them except `item_lines` carries its removal condition on the
    line that declares it** (Guardrail #6), and each condition names the reading
    that retires it rather than a piece of work that lands.
    """

    level: LogLevel = Field(
        default=LogLevel.INFO,
        description=(
            "How loud the logger is, and nothing else. Unrelated to the flags beside "
            "it: they decide which records are built, this decides which of the built "
            "records are printed. It predates them and no removal condition applies."
        ),
    )
    item_lines: bool = Field(
        default=True,
        description=(
            "Whether an item logs a record when it starts and another when it "
            "finishes, success or failure. NO REMOVAL CONDITION, on purpose: this is "
            "the permanent instrument and not a debugging aid. A run that cannot say "
            "which item it is on, and which ones it got through, is the blind window "
            "the rest of this block exists to end. It is a knob at all only so an "
            "operator re-running one shard by hand can quieten it for that "
            "invocation."
        ),
    )
    stage_lines: bool = Field(
        default=True,
        description=(
            "Whether fetch, extract, label, summarize and faithfulness each log a "
            "record when they end. Retire it when the per-stage split has stopped "
            "saying anything the completion record does not: a week of runs in which "
            "no stage's share of item time moves by more than the run-to-run spread, "
            "and no item time is left unattributed. Until then a shard that dies on a "
            "timeout names no stage at all, and the completion record arrives only "
            "for an item that finished."
        ),
    )
    waiting_heartbeat_seconds: int = Field(
        default=30,
        ge=0,
        description=(
            "How often, in seconds, to log elapsed time while a model call is in "
            "flight. 0 turns the heartbeat off and IS the retirement, so this knob "
            "retires itself rather than being deleted. A NEGATIVE VALUE IS REFUSED: a "
            "number that quietly means never when the operator meant often is the "
            "worst shape a misconfiguration of this knob can take. Set it to 0 once "
            "the slowest single model call in a full run has stayed under a minute "
            "for a week, because then a stuck call is visible from its own completion "
            "record and elapsed time adds nothing. Today the slowest call returns "
            "after 22 minutes having printed nothing at all."
        ),
    )
    capture_prompts: bool = Field(
        default=True,
        description=(
            "Whether the rendered prompts are written to a run artifact. Retire it "
            "when the prompt is no longer in question - a week of runs in which every "
            "item's recorded prompt token count matches what the budget predicts, "
            "with nothing truncated. At that point the SHA-256 and the token count "
            "each row already carries say what the text said, for a fraction of the "
            "bytes."
        ),
    )
    capture_replies: bool = Field(
        default=True,
        description=(
            "Whether the raw model replies are written to a run artifact. The most "
            "expensive thing this block can switch on, because a reply is the longest "
            "text in the run. Retire it when no item has been cut short for a week "
            "and the decoded token counts agree with what each row records, because "
            "the reply text is then answering a question nobody is asking."
        ),
    )


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
    host_fingerprint: bool = Field(
        default=True,
        description=(
            "Whether a job records what silicon it drew - processor family, model, "
            "stepping, instruction-set flags, cache, and the platform's own name for "
            "the machine size - into state/host-fingerprint/<YYYY>/<MM>/<DD>.csv. "
            "False writes no row, and every throughput number that run takes becomes "
            "uncomparable with any other run's, because nothing says which machine "
            "produced it. Retire it when the platform stops mixing processor "
            "generations in one runner pool: a quarter of runs in which every job "
            "reports the same family, model and flags, which would make the row a "
            "constant and a constant is not a reading."
        ),
    )
    host_fingerprint_bandwidth_mib: int = Field(
        default=512,
        ge=0,
        description=(
            "The buffer each side of the memory-bandwidth probe allocates, so the "
            "probe holds twice this. Zero switches the probe off and leaves the "
            "bandwidth cell empty; every other cell of the fingerprint still gets "
            "written. The default beats the largest L3 this project has drawn, 480 "
            "MiB, because a buffer that fits in cache measures cache and reads as a "
            "memory figure four times too high. Raise it when a drawn machine "
            "reports an L3 at or above this."
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
            "Whether a work shard builds a span tree. On by default: a "
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
            "invent a total nobody reads. Seven days covers a week of runs, and the "
            "window is what keeps state/traces/ a constant size whatever the project's "
            "age rather than one that grows with it (Guardrail #12). It does "
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
            "means never, and never is the default: the fold is a small fraction of the "
            "shard it summarises, and deleting it would make a year-over-year comparison "
            "unanswerable, which Guardrail #10 then forbids citing at all. Set, it must sit "
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
            "and those days can fall in fourteen calendar months. The ledger files by "
            "day and this age is still a month, so the prune takes a month's day files "
            "whole."
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
    visuals_full_grain_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long state/visuals/ stays readable attempt by attempt. Past it a month "
            "is folded to the eight-term group VisualAggregateRow declares and the "
            "full-grain shard goes, so a reader keeps every cause breakdown and every "
            "stratum and loses the per-attempt row and its join key. Fourteen matches "
            "the two ledgers it is read beside; a shorter one would leave a day whose "
            "failures are still readable and whose refused pictures are not. It is NOT "
            "in full_grain_months() yet, and the reason is that no console read opens "
            "one of these shards today - the panels that will are their own plan, and "
            "the window joins that check in the same commit as the first of them."
        ),
    )
    visual_aggregate_keep_months: int | None = Field(
        default=None,
        ge=1,
        description=(
            "Months after which a folded visual month is removed outright. Null means "
            "never, on the same argument as the other two aggregates: the fold is the "
            "only record that a gate ever refused anything, and it is kilobytes. Set, "
            "it must sit ABOVE visuals_full_grain_months."
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
    public_run_days_keep_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long frontend/public/run-days/ keeps a month of day rows. Fourteen "
            "because the console reaches 367 inclusive days and those days can fall in "
            "fourteen month shards, which is the same reason feed_health_keep_months "
            "is fourteen. It has no state ledger to be paired with: the source is the "
            "committed day payloads themselves, whose retention is the archive's, and "
            "this row is a reduction of two of them to counts."
        ),
    )
    public_day_metrics_keep_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long frontend/public/day-metrics/ keeps a month of day records. "
            "Fourteen on the same argument as public_run_days_keep_months. The source "
            "under state/day-metrics/ has no age of its own - a day record is a few "
            "kilobytes and it is the only place a band count or an extraction census "
            "survives once the day's items are folded - so this bounds the published "
            "copy without claiming to bound the ledger."
        ),
    )
    public_machine_keep_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long frontend/public/machine/ keeps a month of shard rows. "
            "Fourteen on the same argument. Both sources file by day, so the month "
            "boundary is inherited from them and this bounds the published copy "
            "without claiming to bound either ledger."
        ),
    )
    public_span_rollup_keep_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long frontend/public/span-rollup/ keeps a published shard. Fourteen "
            "on the same argument as the item-health copy above."
        ),
    )
    public_run_timeline_keep_months: int = Field(
        default=2,
        ge=1,
        description=(
            "How long frontend/public/run-timeline/ keeps a published shard. Two, not "
            "fourteen, and it is the one published series no window preset can reach: "
            "the panel draws ONE run and names it, so a month older than the newest "
            "buys nothing a reader can select. The second month is there so a run on "
            "the first of a month still has the day before it. At roughly a kilobyte "
            "per item this is the widest published row we write, so keeping it at the "
            "console's window would publish megabytes nothing fetches."
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
            "(CLAUDE.md Guardrail #10's one carve-out). The console prints the rate it "
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
        """Fail a config that still names one of the five retired knobs.

        `keep_months` and `hard_delete_after_months` governed `state/item-health/`
        and nothing else, while three other stores had no age at all. They were
        read and dropped for a day so the rows that spend the new ages could land
        one at a time; now that every reader has moved, a file still spelling one
        is refused by name.

        `public_scores_keep_months` and `public_feed_health_keep_months` are next,
        and they have no successor because the trees they bounded are gone. They
        pruned published copies of `state/scores/` and `state/feed-health/` that
        nothing ever fetched; the ledgers stay and keep their own ages.

        `runtime_counters_scrape` is the fifth and has no successor either. It
        switched off a row in `state/runtime-counters.csv`, and that store is
        gone: the four cells a reader still wants are on the host row, which
        `job-clock` writes from the same scrape. Honouring the flag would now
        switch off nothing at all.

        Refused rather than ignored, and refused rather than carried forward. The
        old age values were set against a check that could not answer the question
        - it compared `months * 30` against the console window instead of the
        shards that window selects - so honouring them would honour the defect,
        and dropping any of the five silently would leave an operator believing a
        number nothing reads.
        """
        return refuse_a_removed_knob("observability", data, SUPERSEDED_RETENTION_NAMES)

    def full_grain_months(self) -> Mapping[str, int]:
        """Every window that has to outlive what a console read can still select.

        The published windows are in here beside the state ones because the
        console fetches them now: a published shard deleted while a window
        preset still reaches it blanks the panel that draws it, and it does so
        silently, because a month with no file is indistinguishable from a month
        with no runs.
        """
        return MappingProxyType(
            {
                "item_health_full_grain_months": self.item_health_full_grain_months,
                "feed_health_keep_months": self.feed_health_keep_months,
                "scores_full_grain_months": self.scores_full_grain_months,
                "public_telemetry_keep_months": self.public_telemetry_keep_months,
                "public_run_days_keep_months": self.public_run_days_keep_months,
                "public_day_metrics_keep_months": self.public_day_metrics_keep_months,
                "public_machine_keep_months": self.public_machine_keep_months,
                "public_span_rollup_keep_months": self.public_span_rollup_keep_months,
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
            ("visual_aggregate_keep_months", "visuals_full_grain_months"),
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
        """A projection and the ledger it projects age together.

        `public_telemetry` is the only pair left. The other four published
        payloads have no state ledger of their own and so appear in no pair here -
        `public_run_days`, `public_day_metrics`, `public_machine` and
        `public_span_rollup` are bounded by their own knob and by
        `refuse_windows_shorter_than`.
        """
        for published, source in (
            ("public_telemetry_keep_months", "item_health_full_grain_months"),
        ):
            if getattr(self, published) != getattr(self, source):
                raise ValueError(
                    f"observability.{published} must equal {source}. The projection is "
                    "the browser's copy of that ledger, so any other pair leaves either "
                    "a published month nothing can check or a window the console cannot "
                    "draw"
                )
        return self
