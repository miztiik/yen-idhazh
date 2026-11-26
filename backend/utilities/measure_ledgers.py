"""Report the per-item timing residual and how article words turn into prompt tokens.

Read-only, offline, and not a stage. It runs when somebody wants these figures,
never on the daily pipeline's critical path. It is committed
rather than kept as a private script so anyone can re-derive the figures in
`docs/reference/pipeline-cost.md` from a fork or a stale branch, which is the
same reason `reconcile_prefill.py` lives beside it.

**1. The clock residual.** `summarize_ms` is our stopwatch around the HTTP call.
`prefill_ms + decode_ms` is what the model server said the same call cost. The
difference is transport, JSON and validation - plus, if it is large, time the
server spent that its own timings block does not name. It decides whether a slow
day is the model's fault or ours, and today the model is blamed by default
because it is the only thing measured.

It is reported here and deliberately not published. It is a difference of two
clocks, so it can print negative, and a negative "overhead" one line away from a
model-time figure invites a reader to add the two and get a wrong number.

**2. Words to tokens, at the configured cap.** `input_tokens` regressed on
`source_words` - **regressed, never divided**. A ratio blends the fixed prompt
into the per-word rate and reads high on short articles: over the widest item
of one run the ratio says 1.695 tokens a word where the regression says 1.387
and a 951-token fixed prompt. Dividing is how a cap gets called safe or unsafe
against the wrong number.

**Which rows count as "at the configured cap", and why one instrument.** A run
qualifies on one proof, and it is committed data:

- **The item ledger itself.** A row carries `truncation_cap_tokens`, the cap that
  cut it, written at the moment of the cut. A run with a row naming the
  configured cap ran at that cap, and nothing else has to be inferred.

  **The ceiling is not re-derived to check this, and that is deliberate.** The
  proof used to be `source_words` equal to
  `int(truncation_cap_tokens / extract.TOKENS_PER_WORD)`, which asks about this
  morning's config rather than about the run: the ratio is a reading, and when it
  was retaken on 2026-09-14 the implied ceiling moved from 1,000 words to 953 and
  every historical row stopped matching at once. What happened to a row is
  recorded on the row.

  **A run before 2026-09-14 recorded no cap and cannot be admitted.** That is the
  honest answer rather than a loss: backfilling today's cap onto a run that never
  used it is how rows of an unknown cap get into one regression.

  There were two until 2026-09-12. The second read `pipeline_fingerprint` off
  `state/scores/`, because the cap was one of the inputs that stamp was taken
  over - so the stamp moved when the cap moved. The stamp stopped being written,
  so a run after that date can only be admitted on the physical proof. What that
  costs: a run whose articles were all shorter than the ceiling now has no proof
  at all and is excluded, where the stamp used to admit it.

There is no second proof to agree with, and that is the whole of the change. The
report still says which proof admitted each run - there is one value it can
print - so a reader can check the population rather than trust it.

Usage, from the root of a checkout:

    python backend/utilities/measure_ledgers.py

Exit code 1 when a ledger it needs is absent, so a shell can tell "nothing to
read" from "read it, here are the numbers".
"""

from __future__ import annotations

import argparse
import math
import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from idhazh import config, ledger
from idhazh.contracts.item_health import ItemHealthRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.extract import TOKENS_PER_WORD
from idhazh.llm.server import response_limit, window

#: The percentile the residual is reported at, beside the median and the two
#: extremes. High enough to show the tail an average hides, low enough that a
#: few hundred rows can carry it.
UPPER_PERCENTILE: Final = 0.95


@dataclass(frozen=True, slots=True)
class Item:
    """The cells of one item-health row these two reports read.

    Every cell is optional because the ledger predates most of them, and a null
    is not a zero: a row written before token capture is not evidence that zero
    tokens were read.
    """

    run_id: str
    summarize_ms: int | None
    prefill_ms: int | None
    decode_ms: int | None
    input_tokens: int | None
    source_words: int | None
    source_words_before_cap: int | None
    truncation_cap_tokens: int | None

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
    """Every committed item-health row, read through the ledger door."""
    items: list[Item] = []
    for held in ledger.load_ledger_rows(state_dir, LedgerName.ITEM_HEALTH, model=ItemHealthRow):
        row = held.csv_row()
        items.append(
            Item(
                run_id=row["run_id"],
                summarize_ms=_cell(row, "summarize_ms"),
                prefill_ms=_cell(row, "prefill_ms"),
                decode_ms=_cell(row, "decode_ms"),
                input_tokens=_cell(row, "input_tokens"),
                source_words=_cell(row, "source_words"),
                source_words_before_cap=_cell(row, "source_words_before_cap"),
                truncation_cap_tokens=_cell(row, "truncation_cap_tokens"),
            )
        )
    return items


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
    """One run, and whether the cap proof lets it into the regression."""

    run_id: str
    rows: int
    widest_words: int
    cut_by_the_cap: bool

    @property
    def admitted(self) -> bool:
        return self.cut_by_the_cap

    @property
    def proof(self) -> str:
        if self.cut_by_the_cap:
            return "a row naming the configured cap as the one that cut it"
        return (
            "none - no row of this run names the configured cap. A run before "
            "2026-09-14 recorded no cap at all and cannot be admitted"
        )


def ceiling_words(cap_tokens: int) -> int:
    """The widest article the configured cap can pass, in words, as `extract` cuts it."""
    return int(cap_tokens / TOKENS_PER_WORD)


def admissions(state_dir: Path, items: Sequence[Item], *, cap_tokens: int) -> list[Admission]:
    """Every run in the item ledger, with the proof it ran at the configured cap."""
    out: list[Admission] = []
    for run_id in sorted({item.run_id for item in items}):
        sized = [
            i
            for i in items
            if i.run_id == run_id and i.source_words is not None and i.input_tokens is not None
        ]
        if not sized:
            continue
        cut_by_the_cap = any(
            i.truncation_cap_tokens == cap_tokens
            for i in items
            if i.run_id == run_id
        )
        out.append(
            Admission(
                run_id=run_id,
                rows=len(sized),
                widest_words=max(i.source_words or 0 for i in sized),
                cut_by_the_cap=cut_by_the_cap,
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
    """The two reports, each with its denominator and what it could not answer."""
    items = read_items(state_dir)
    lines = [f"{len(items)} committed item-health rows, from {state_dir.as_posix()}", ""]

    lines.append("1. The clock residual, summarize_ms - (prefill_ms + decode_ms), per item")
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
        f"2. Words to tokens at truncation_cap_tokens={cap_tokens} "
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
    parser = argparse.ArgumentParser(description="Item timing and token counts from the ledger.")
    parser.add_argument("--state", type=Path, default=Path("state"))
    args = parser.parse_args()
    if not ledger.held_days(args.state, LedgerName.ITEM_HEALTH):
        print(f"no item-health ledger under {args.state.as_posix()} - nothing to read")
        return 1
    settings = config.load()
    print(
        report(
            args.state,
            cap_tokens=settings.app.extract.truncation_cap_tokens,
            context_tokens=window(settings.models.summarizer.server),
            output_tokens=response_limit(settings.models.summarizer.sampling),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
