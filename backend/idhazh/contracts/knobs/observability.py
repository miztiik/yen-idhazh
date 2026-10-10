"""What the pipeline records about itself, and what an operator may switch off."""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Any, Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, ServerJob
from idhazh.contracts.knobs.removed import refuse_a_removed_knob


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


#: The `observability` names this block used to carry, and where the same number
#: lives now. An empty value means the ledger itself is gone. A cleanup age moved
#: into the declaration of the gardener task that spends it.
SUPERSEDED_RETENTION_NAMES: Final[Mapping[str, str]] = MappingProxyType(
    {
        "keep_months": "series.full-grain.value in config/gardener/telemetry-aggregate.json",
        "hard_delete_after_months": "series.aggregate in config/gardener/telemetry-aggregate.json",
        "public_scores_keep_months": "",
        "public_feed_health_keep_months": "",
        "runtime_counters_scrape": "",
        "trace_window_days": "window.value in config/gardener/traces.json",
        "item_health_full_grain_months": (
            "series.full-grain.value in config/gardener/telemetry-aggregate.json"
        ),
        "item_health_aggregate_keep_months": (
            "series.aggregate in config/gardener/telemetry-aggregate.json"
        ),
        "public_telemetry_keep_months": (
            "series.public-copy.value in config/gardener/telemetry-aggregate.json"
        ),
        "feed_health_keep_months": (
            "monthly_window.value in config/gardener/compact-feed-health.json"
        ),
        "host_fingerprint_keep_months": (
            "monthly_window.value in config/gardener/compact-host-fingerprint.json"
        ),
        "scores_full_grain_months": (
            "monthly_window in config/gardener/compact-summary-quality-evals.json, which "
            "keeps every eval row for ever and summarises no month"
        ),
        "score_archive_keep_months": (
            "monthly_window in config/gardener/compact-summary-quality-evals.json, which "
            "keeps every eval row for ever and summarises no month"
        ),
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

    **A ledger's cleanup age lives with the task that spends it.** Each retention
    pass is a gardener task, and how long it keeps what it owns is its own
    declaration under `config/gardener/`. What is left here is the windows the
    publishers read for the copies they trim, and the visual-attempt windows,
    whose pass lands with the ledger's writer. The published windows are checked
    against the shards a console read can still select, and a summary that
    replaces a full-grain window must outlive it.
    """

    evaluation_enabled: bool = Field(
        default=True,
        description=(
            "Whether the faithfulness scorer runs. False writes no row to "
            "the summary-quality-evals ledger, so for those days the eval dashboard and the "
            "console's score panels list nothing and each item bands from the model-free "
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
            "the item-health ledger still holds every row, so switching it back on "
            "republishes the gap."
        ),
    )
    host_fingerprint: bool = Field(
        default=True,
        description=(
            "Whether a job records what silicon it drew - processor family, model, "
            "stepping, instruction-set flags, cache, and the platform's own name for "
            "the machine size - into the host-fingerprint ledger "
            "(state/raw/host-fingerprint/). "
            "False writes no row, and every throughput number that run takes becomes "
            "uncomparable with any other run's, because nothing says which machine "
            "produced it. Retire it when the platform stops mixing processor "
            "generations in one runner pool: a quarter of runs in which every job "
            "reports the same family, model and flags, which would make the row a "
            "constant and a constant is not a reading."
        ),
    )
    host_fingerprint_bandwidth_jobs: tuple[ServerJob, ...] = Field(
        default=(ServerJob.RUNTIME,),
        description=(
            "Which workflow jobs take the memory-bandwidth reading. A job outside "
            "this list records every other cell of the fingerprint and leaves "
            "memcpy_gib_s empty, with memcpy_probe_mib at zero beside it so the row "
            "says the reading was not taken rather than implying a machine that "
            "could not copy. "
            "The bench alone by default, because the reading wants a gigabyte and an "
            "idle machine: measure.yml takes it between its corpus step and its "
            "sweep, where nothing else is running, and that is the job whose whole "
            "purpose is to tell one machine from another. A production job that took "
            "it would allocate twice the cache it drew and time a copy against "
            "whatever else it had already started, which measures the run rather "
            "than the host. Add a job here to read its bandwidth; the cell is "
            "nullable and nothing refuses a row without it."
        ),
    )
    host_fingerprint_bandwidth_floor_mib: int = Field(
        default=512,
        ge=0,
        description=(
            "The smallest buffer each side of the memory-bandwidth probe may "
            "allocate, so the probe holds twice this. Zero switches the probe off "
            "and leaves the bandwidth cell empty; every other cell of the "
            "fingerprint still gets written. It is a floor and not the answer: a "
            "buffer that does not clear the cache measures cache and reads as a "
            "memory figure several times too high, and the reported L3 across the "
            "machines this project draws spans 32 MiB to 480 MiB. So the probe "
            "raises the buffer to host_fingerprint_bandwidth_cache_multiple times "
            "whatever cache the machine it drew reports, and this value is what a "
            "machine reporting no cache at all gets. memcpy_probe_mib on the row "
            "records the size that was used."
        ),
    )
    host_fingerprint_bandwidth_cache_multiple: int = Field(
        default=2,
        ge=1,
        description=(
            "How many times the reported cache each side of the memory-bandwidth "
            "probe has to be. The probe holds two buffers, so at 2 the working set "
            "is four times the cache and no part of the copy can be served from it; "
            "below that the reading stops being a memory reading, and above it the "
            "runner pays memory it does not get back before the model server starts. "
            "It is one value because two readers need the same one: the probe sizes "
            "its buffer by it, and the console grades a committed row by it and "
            "withholds the copy speed of a row whose buffer did not clear the cache "
            "by this much. Two numbers in two languages would let a row the probe "
            "wrote correctly be refused by the page that draws it."
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
            "a short rolling window the gardener's traces task bounds, and folds "
            "the shard's spans into the committed span rollup. That file is the only "
            "destination a span has, so no run reaches a third party whatever this says."
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
    public_run_days_keep_months: int = Field(
        default=14,
        ge=1,
        description=(
            "How long frontend/public/run-days/ keeps a month of day rows. Fourteen "
            "because the console reaches 367 inclusive days and those days can fall in "
            "fourteen month shards, which is the same reason the gardener's feed-health "
            "task keeps fourteen months. It has no state ledger to be paired with: the "
            "source is the committed day payloads themselves, whose retention is the "
            "archive's, and this row is a reduction of two of them to counts."
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
            "How long frontend/public/machine/ keeps a month of machine rows. "
            "Fourteen on the same argument. The shard is folded from the "
            "item-health and host-fingerprint ledgers, so it may not outlive "
            "either source: a published month whose source months are gone cannot be "
            "rebuilt. config.load_gardener refuses a declaration governing the "
            "host-fingerprint ledger - its compaction - that keeps less than this, on "
            "the argument the telemetry copy makes for its own pair."
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
        """Fail a config that still names a retired knob, and say where its number went.

        `keep_months` and `hard_delete_after_months` governed `state/item-health/`
        and nothing else, while three other ledgers had no age at all. Their
        successors have since moved again, with every other cleanup age: each is
        the window of the gardener task that deletes by it, in that task's own
        declaration, because the task is the only thing that reads it.

        `public_scores_keep_months` and `public_feed_health_keep_months` have no
        successor because the trees they bounded are gone. They pruned published
        copies of the eval and feed-health ledgers that nothing ever fetched; the
        ledgers stay and keep their own ages.

        `runtime_counters_scrape` has no successor either. It switched off a row
        in `state/runtime-counters.csv`, and that ledger is gone: the four cells a
        reader still wants are on the host row, which `job-clock` writes from the
        same scrape. Honouring the flag would now switch off nothing at all.

        Refused rather than ignored, and refused rather than carried forward: a
        number left here would be read by nothing, and an operator who changed it
        would believe they had moved a window that did not move.
        """
        return refuse_a_removed_knob("observability", data, SUPERSEDED_RETENTION_NAMES)

    def full_grain_months(self) -> Mapping[str, int]:
        """Every published window here that has to outlive what a console read can select.

        The console fetches these copies: a published shard deleted while a
        window preset still reaches it blanks the panel that draws it, and it
        does so silently, because a month with no file is indistinguishable from
        a month with no runs. The windows of the ledgers behind them are the
        gardener's, and `config.load_gardener` holds those to the same read.
        """
        return MappingProxyType(
            {
                "public_run_days_keep_months": self.public_run_days_keep_months,
                "public_day_metrics_keep_months": self.public_day_metrics_keep_months,
                "public_machine_keep_months": self.public_machine_keep_months,
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
        months = self.visual_aggregate_keep_months
        if months is not None and months <= self.visuals_full_grain_months:
            raise ValueError(
                "observability.visual_aggregate_keep_months must sit above "
                "visuals_full_grain_months, or a month is deleted before it is ever summarised"
            )
        return self
