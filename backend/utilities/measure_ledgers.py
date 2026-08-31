"""Three figures the committed ledgers already hold, and that nobody had taken.

Read-only, offline, and not a stage. It runs when somebody wants one of these
three numbers, never on the daily pipeline's critical path. It is committed
rather than kept as a private script so anyone can re-derive the figures in
`docs/reference/measurements.md` from a fork or a stale branch, which is the
same reason `reconcile_prefill.py` lives beside it.

**1. Unaccounted shard wall-clock.** A `work` shard's own clock, minus the
milliseconds its items claim for fetching, extracting and summarizing. It
answers one question: is the model busy for most of a shard? If it is, more
shards buys throughput. If it is not, more shards buys more fixed cost, and
nobody could see that before, because the two clocks sat in two files nothing
joined.

**This is per shard where the rows allow it and per run where they do not.**
`shard` landed on `ItemHealthRow` on 2026-08-30 and is empty on every row written
before it, so both grains are live at once and the report says which one each
line is. Per run is the coarser answer because it averages the shards together,
and the read rate spreads 2.30x between shards inside one run - which is exactly
the variance the per-shard split exists to show.

**2. The clock residual.** `summarize_ms` is our stopwatch around the HTTP call.
`prefill_ms + decode_ms` is what the model server said the same call cost. The
difference is transport, JSON and validation - plus, if it is large, time the
server spent that its own timings block does not name. It decides whether a slow
day is the model's fault or ours, and today the model is blamed by default
because it is the only thing measured.

It is reported here and deliberately not published. It is a difference of two
clocks, so it can print negative, and a negative "overhead" one line away from a
model-time figure invites a reader to add the two and get a wrong number.

**3. Words to tokens, at the configured cap.** `input_tokens` regressed on
`source_words` - **regressed, never divided**. A ratio blends the fixed prompt
into the per-word rate and reads high on short articles: over the widest item
of one run the ratio says 1.695 tokens a word where the regression says 1.387
and a 951-token fixed prompt. Dividing is how a cap gets called safe or unsafe
against the wrong number.

**Which rows count as "at the configured cap", and why two instruments.** A run
qualifies on either proof, and both are committed data:

- **The eval ledger.** `state/scores/<YYYY-MM>.csv` carries `pipeline_fingerprint`, and
  `extract.truncation_cap_tokens` is a field of the payload that stamp is taken
  over - so the stamp moved when the cap moved. The live stamp is the one on the
  newest committed row, the same "the live instrument is the last row" rule
  `label_queue.py` uses for `scorer_version`.
- **The item ledger itself.** `source_words` is post-cap and cannot exceed
  `int(truncation_cap_tokens / extract.TOKENS_PER_WORD)`, so a row sitting
  exactly on that ceiling with a larger `source_words_before_cap` is physical
  proof the configured cap did the cutting.

Neither alone is enough. A run whose eval rows have not been committed yet has
no stamp; a run whose longest article never reached the ceiling cut nothing.
Where both apply they must agree, and the report says which proof admitted each
run so a reader can check the population rather than trust it.

Usage, from the root of a checkout:

    python backend/utilities/measure_ledgers.py

Exit code 1 when a ledger it needs is absent, so a shell can tell "nothing to
read" from "read it, here are the numbers".
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh import config, ledger
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.evals.writer import records as score_records
from idhazh.extract import TOKENS_PER_WORD

#: The percentile the residual is reported at, beside the median and the two
#: extremes. High enough to show the tail an average hides, low enough that a
#: few hundred rows can carry it.
UPPER_PERCENTILE: Final = 0.95


@dataclass(frozen=True, slots=True)
class Item:
    """The cells of one item-health row these three figures read.

    Every cell is optional because the ledger predates most of them, and a null
    is not a zero: a row written before token capture is not evidence that zero
    tokens were read.
    """

    run_id: str
    shard: str | None
    fetch_ms: int | None
    extract_ms: int | None
    summarize_ms: int | None
    prefill_ms: int | None
    decode_ms: int | None
    input_tokens: int | None
    source_words: int | None
    source_words_before_cap: int | None

    @property
    def residual_ms(self) -> int | None:
        """Our stopwatch minus the server's own two clocks, or None if either is absent."""
        if self.summarize_ms is None or self.prefill_ms is None or self.decode_ms is None:
            return None
        return self.summarize_ms - self.prefill_ms - self.decode_ms


def _cell(row: dict[str, str], name: str) -> int | None:
    value = row.get(name, "")
    return int(value) if value else None


def read_items(state_dir: Path) -> list[Item]:
    """Every committed item-health row, from every month shard."""
    directory = state_dir / ledger.ITEM_HEALTH_DIRNAME
    items: list[Item] = []
    for path in sorted(directory.glob("*.csv")):
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                items.append(
                    Item(
                        run_id=row["run_id"],
                        shard=row.get("shard") or None,
                        fetch_ms=_cell(row, "fetch_ms"),
                        extract_ms=_cell(row, "extract_ms"),
                        summarize_ms=_cell(row, "summarize_ms"),
                        prefill_ms=_cell(row, "prefill_ms"),
                        decode_ms=_cell(row, "decode_ms"),
                        input_tokens=_cell(row, "input_tokens"),
                        source_words=_cell(row, "source_words"),
                        source_words_before_cap=_cell(row, "source_words_before_cap"),
                    )
                )
    return items


@dataclass(frozen=True, slots=True)
class ShardClock:
    """A committed job clock against the item milliseconds charged under it.

    The scope is one shard where the item rows name their shard, and one whole
    run where they do not.
    """

    run_id: str
    shard: str | None
    counter_rows: int
    distinct_shards: int
    job_seconds: int
    fetch_ms: int
    extract_ms: int
    summarize_ms: int

    @property
    def scope(self) -> str:
        return self.run_id if self.shard is None else f"{self.run_id} shard {self.shard}"

    @property
    def accounted_seconds(self) -> float:
        return (self.fetch_ms + self.extract_ms + self.summarize_ms) / 1000.0

    @property
    def unaccounted_seconds(self) -> float:
        return self.job_seconds - self.accounted_seconds

    @property
    def unaccounted_share(self) -> float:
        return self.unaccounted_seconds / self.job_seconds if self.job_seconds else 0.0

    @property
    def model_share(self) -> float:
        """Summarizing, as a share of the job clocks. The lever question."""
        return self.summarize_ms / 1000.0 / self.job_seconds if self.job_seconds else 0.0

    @property
    def joinable(self) -> bool:
        """Whether the two ledgers cover the same work in this scope.

        A scope holding more counter rows than shards had a shard re-run. Both
        ledgers are appended by the shard itself and merged line by line, so
        neither execution can see the other's rows and each files its own. The
        two then cover different sets of executions, and their difference is not
        a measurement of anything.
        """
        return self.counter_rows == self.distinct_shards and self.unaccounted_seconds >= 0

    @property
    def verdict(self) -> str:
        if self.counter_rows != self.distinct_shards:
            return (
                f"NOT JOINABLE: {self.counter_rows} counter rows for "
                f"{self.distinct_shards} shards, so a shard was re-run and the two ledgers "
                "cover different sets of executions"
            )
        if self.unaccounted_seconds < 0:
            return (
                "NOT JOINABLE: the items claim more time than the job clocks hold, "
                "so a shard that produced rows filed no clock"
            )
        return (
            f"{self.unaccounted_seconds:.1f} s outside fetch, extract and summarize "
            f"({self.unaccounted_share * 100:.1f} percent of the job clocks); "
            f"summarizing is {self.model_share * 100:.1f} percent of them"
        )


def shard_clocks(state_dir: Path, items: Sequence[Item]) -> list[ShardClock]:
    """The finest grain the two ledgers support, for every run that filed a clock.

    One entry per shard where that run's item rows name their shard, and one for
    the whole run where they do not. `shard` landed on `ItemHealthRow` on
    2026-08-30 and is empty on every row written before it, so a ledger can hold
    both kinds of run at once.
    """
    counters = _counter_rows(state_dir)
    clocks: list[ShardClock] = []
    for run_id in sorted({row["run_id"] for row in counters if row["job_seconds"]}):
        rows = [r for r in counters if r["run_id"] == run_id and r["job_seconds"]]
        mine = [item for item in items if item.run_id == run_id]
        if mine and all(item.shard is not None for item in mine):
            for shard in sorted({item.shard for item in mine if item.shard is not None}):
                clocks.append(
                    _clock(run_id, shard, [r for r in rows if r["shard"] == shard], mine)
                )
        else:
            clocks.append(_clock(run_id, None, rows, mine))
    return clocks


def _clock(
    run_id: str, shard: str | None, rows: list[dict[str, str]], items: Sequence[Item]
) -> ShardClock:
    mine = items if shard is None else [item for item in items if item.shard == shard]
    return ShardClock(
        run_id=run_id,
        shard=shard,
        counter_rows=len(rows),
        distinct_shards=len({r["shard"] for r in rows}),
        job_seconds=sum(int(r["job_seconds"]) for r in rows),
        fetch_ms=sum(i.fetch_ms or 0 for i in mine),
        extract_ms=sum(i.extract_ms or 0 for i in mine),
        summarize_ms=sum(i.summarize_ms or 0 for i in mine),
    )


def _counter_rows(state_dir: Path) -> list[dict[str, str]]:
    """`state/runtime-counters.csv` as raw cells.

    Read as text rather than through `load_runtime_counters`, which filters to
    one run and so cannot say which runs exist.
    """
    path = ledger.runtime_counters_path(state_dir)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def percentile(values: Sequence[int], share: float) -> int:
    """Nearest-rank: the smallest value at least `share` of the sample is at or under."""
    ordered = sorted(values)
    rank = max(1, math.ceil(share * len(ordered)))
    return ordered[rank - 1]


@dataclass(frozen=True, slots=True)
class Residual:
    """`summarize_ms - (prefill_ms + decode_ms)`, over every row that carries all three."""

    values: tuple[int, ...]

    @classmethod
    def over(cls, items: Iterable[Item]) -> Residual:
        return cls(values=tuple(sorted(v for v in (i.residual_ms for i in items) if v is not None)))

    @property
    def count(self) -> int:
        return len(self.values)

    @property
    def minimum(self) -> int:
        return self.values[0]

    @property
    def maximum(self) -> int:
        return self.values[-1]

    @property
    def median(self) -> float:
        return statistics.median(self.values)

    @property
    def upper(self) -> int:
        return percentile(self.values, UPPER_PERCENTILE)

    @property
    def negatives(self) -> int:
        """Rows where the two clocks disagree in the impossible direction."""
        return sum(1 for value in self.values if value < 0)


@dataclass(frozen=True, slots=True)
class WordsToTokens:
    """`input_tokens` regressed on `source_words`. Never a ratio - see the module docstring."""

    count: int
    slope: float
    intercept: float
    residual_sd: float
    widest_words: int
    widest_tokens: int

    @classmethod
    def over(cls, pairs: Sequence[tuple[int, int]]) -> WordsToTokens:
        mean_words = statistics.fmean(w for w, _ in pairs)
        mean_tokens = statistics.fmean(t for _, t in pairs)
        variance = sum((w - mean_words) ** 2 for w, _ in pairs)
        covariance = sum((w - mean_words) * (t - mean_tokens) for w, t in pairs)
        slope = covariance / variance
        intercept = mean_tokens - slope * mean_words
        residuals = [t - (intercept + slope * w) for w, t in pairs]
        widest = max(pairs)
        return cls(
            count=len(pairs),
            slope=slope,
            intercept=intercept,
            residual_sd=statistics.stdev(residuals),
            widest_words=widest[0],
            widest_tokens=widest[1],
        )

    def prompt_at(self, words: int) -> float:
        """The whole prompt an article of `words` words is predicted to cost, in tokens."""
        return self.intercept + self.slope * words

    @property
    def ratio_on_widest(self) -> float:
        """What dividing would have said. Kept only to show how far it is out."""
        return self.widest_tokens / self.widest_words


@dataclass(frozen=True, slots=True)
class Admission:
    """One run, and whether the two cap proofs let it into the regression."""

    run_id: str
    rows: int
    widest_words: int
    cut_at_ceiling: bool
    carries_live_stamp: bool

    @property
    def admitted(self) -> bool:
        return self.cut_at_ceiling or self.carries_live_stamp

    @property
    def proof(self) -> str:
        if self.cut_at_ceiling and self.carries_live_stamp:
            return "both: a row cut on the ceiling, and the live pipeline stamp"
        if self.cut_at_ceiling:
            return "a row cut exactly on the ceiling the configured cap implies"
        if self.carries_live_stamp:
            return "the live pipeline stamp on its eval rows"
        return "none - no row reached the ceiling and no eval row carries the live stamp"


def ceiling_words(cap_tokens: int) -> int:
    """The widest article the configured cap can pass, in words, as `extract` cuts it."""
    return int(cap_tokens / TOKENS_PER_WORD)


def stamps_by_run(state_dir: Path) -> tuple[str, dict[str, set[str]]]:
    """The live pipeline fingerprint, and every stamp each run's eval rows carry.

    Live means the newest committed row's stamp, not the most common one: a
    ledger holds every pipeline this project has ever run, and only the last one
    is the pipeline in force.
    """
    per_run: dict[str, set[str]] = {}
    live = ""
    for row in score_records(state_dir):
        live = row["pipeline_fingerprint"]
        per_run.setdefault(row["run_id"], set()).add(live)
    return live, per_run


def admissions(state_dir: Path, items: Sequence[Item], *, cap_tokens: int) -> list[Admission]:
    """Every run in the item ledger, with the proof it ran at the configured cap."""
    ceiling = ceiling_words(cap_tokens)
    live, per_run = stamps_by_run(state_dir)
    out: list[Admission] = []
    for run_id in sorted({item.run_id for item in items}):
        sized = [
            i
            for i in items
            if i.run_id == run_id and i.source_words is not None and i.input_tokens is not None
        ]
        if not sized:
            continue
        cut_on_ceiling = any(
            i.source_words == ceiling
            and i.source_words_before_cap is not None
            and i.source_words_before_cap > i.source_words
            for i in items
            if i.run_id == run_id
        )
        out.append(
            Admission(
                run_id=run_id,
                rows=len(sized),
                widest_words=max(i.source_words or 0 for i in sized),
                cut_at_ceiling=cut_on_ceiling,
                carries_live_stamp=bool(live) and live in per_run.get(run_id, set()),
            )
        )
    return out


def sized_pairs(items: Iterable[Item], runs: Iterable[str]) -> list[tuple[int, int]]:
    """`(source_words, input_tokens)` for every row of the named runs that carries both."""
    wanted = set(runs)
    return [
        (i.source_words, i.input_tokens)
        for i in items
        if i.run_id in wanted and i.source_words is not None and i.input_tokens is not None
    ]


def report(state_dir: Path, *, cap_tokens: int, context_tokens: int, output_tokens: int) -> str:
    """The three figures, each with its denominator and what it could not answer."""
    items = read_items(state_dir)
    lines = [f"{len(items)} committed item-health rows, from {state_dir.as_posix()}", ""]

    lines.append("1. Unaccounted job wall-clock")
    attributed = sum(1 for item in items if item.shard is not None)
    if "shard" not in ItemHealthRow.csv_columns():
        lines.append(
            "   per SHARD is unavailable: item-health has no `shard` column, so an item "
            "row cannot be attributed to the machine that produced it"
        )
    elif attributed == 0:
        lines.append(
            f"   per SHARD has no population yet: `shard` is a column but 0 of {len(items)} "
            "committed rows carry one, so every line below is a whole run"
        )
    else:
        lines.append(
            f"   {attributed} of {len(items)} committed rows name their shard; "
            "a run splits per shard once all of its rows do"
        )
    clocks = shard_clocks(state_dir, items)
    if not clocks:
        lines.append("   no run has committed a job clock yet")
    for clock in clocks:
        lines.append(
            f"   {clock.scope}: {clock.job_seconds} s over {clock.counter_rows} counter rows; "
            f"fetch {clock.fetch_ms / 1000:.1f} s, extract {clock.extract_ms / 1000:.1f} s, "
            f"summarize {clock.summarize_ms / 1000:.1f} s"
        )
        lines.append(f"     {clock.verdict}")
    lines.append("")

    lines.append("2. The clock residual, summarize_ms - (prefill_ms + decode_ms), per item")
    residual = Residual.over(items)
    if residual.count == 0:
        lines.append("   no row carries all three clocks")
    else:
        lines.append(
            f"   n={residual.count}  min {residual.minimum} ms  median {residual.median:.1f} ms  "
            f"p{int(UPPER_PERCENTILE * 100)} {residual.upper} ms  max {residual.maximum} ms"
        )
        lines.append(
            f"   {residual.negatives} rows negative "
            "(a negative is the two clocks rounding past each other, never an overhead)"
        )
    lines.append("")

    ceiling = ceiling_words(cap_tokens)
    lines.append(
        f"3. Words to tokens at truncation_cap_tokens={cap_tokens} "
        f"({ceiling} words at {TOKENS_PER_WORD} tokens a word)"
    )
    admitted = [a for a in admissions(state_dir, items, cap_tokens=cap_tokens) if a.admitted]
    for entry in admitted:
        lines.append(
            f"   {entry.run_id}: {entry.rows} sized rows, widest {entry.widest_words} words "
            f"- {entry.proof}"
        )
    pairs = sized_pairs(items, (a.run_id for a in admitted))
    if len(pairs) < 2:
        lines.append("   fewer than two rows at the configured cap - nothing to regress")
    else:
        fit = WordsToTokens.over(pairs)
        lines.append(
            f"   n={fit.count}  slope {fit.slope:.4f} tokens an article word  "
            f"fixed prompt {fit.intercept:.0f} tokens  residual sd {fit.residual_sd:.0f} tokens"
        )
        lines.append(
            f"   widest item {fit.widest_words} words / {fit.widest_tokens} prompt tokens; "
            f"dividing would read {fit.ratio_on_widest:.3f} tokens a word"
        )
        lines.append(
            f"   an article on the {ceiling}-word ceiling is predicted at "
            f"{fit.prompt_at(ceiling):.0f} prompt tokens; with {output_tokens} output tokens "
            f"that is {fit.prompt_at(ceiling) + output_tokens:.0f} of {context_tokens}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Three figures the committed ledgers hold.")
    parser.add_argument("--state", type=Path, default=Path("state"))
    args = parser.parse_args()
    if not (args.state / ledger.ITEM_HEALTH_DIRNAME).is_dir():
        print(f"no item-health ledger under {args.state.as_posix()} - nothing to read")
        return 1
    settings = config.load()
    print(
        report(
            args.state,
            cap_tokens=settings.app.extract.truncation_cap_tokens,
            context_tokens=settings.app.models.inference.n_ctx,
            output_tokens=settings.app.models.inference.max_output_tokens,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
