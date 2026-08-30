"""Score one (premise, summary) pair twice and read what the window geometry did to it.

The faithfulness scorer reads a long article in overlapping windows and keeps
the best window (`idhazh.evals.hhem.score_over_chunks`). Two known biases ride
on the number of windows, and they pull in opposite directions:

- **More windows is more draws.** The aggregation is a max, so an article at
  three windows gets three chances at a high number where an article at one
  window gets one. That inflates the score, and it inflates it more the longer
  the article is.
- **No window holds the whole summary's evidence.** A summary drawing on an
  article's opening and its closing has no single window supporting all of it,
  so every window is marked down for the half it cannot see. That deflates the
  score, and it deflates it more the longer the article is.

Which one wins is an empirical question and this reads the answer off real
pairs. **Each item is its own control.** The same premise and the same summary
are scored at today's geometry and again at a window wide enough to hold the
whole premise, and nothing else varies - so a difference cannot be explained by
long articles simply being more summarizable. Comparing the mean score of long
articles against short ones is the confounded query this exists to replace.

**The one-slice items are the control.** An item that is a single window under
both geometries is scored over the identical text twice, and the scorer is
deterministic, so its difference must be exactly zero. A non-zero reading there
means the harness is wrong and no other row of the table may be read.

Read-only. It never writes into a published tree, never appends to a ledger,
and changes no default: `evaluation.chunk_words` is what it measures, not what
it moves.

The pairs are the ones the run actually scored, from
`backend/idhazh/evals/evidence.py`. They are gitignored (`CLAUDE.md`
section 0a - an article body is not ours to republish) and reach this tool as a
workflow artifact:

    gh run download <run-id> --pattern 'evidence-*' --dir <dir>
    python backend/utilities/grader_length_bias.py --evidence <dir>

Absent that input the tool fails and says so. It never reports a zero it did
not measure.
"""

from __future__ import annotations

import argparse
import csv
import statistics
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from idhazh.config import load
from idhazh.contracts.app_config import EvaluationConfig
from idhazh.contracts.evidence import EvidenceItem
from idhazh.evals.evidence import EVIDENCE_ROOT_RELPATH, index, key_of
from idhazh.evals.hhem import Scorer, chunks, score_over_chunks
from idhazh.evals.writer import LEDGER_RELPATH

HOW_TO_GET_PAIRS = (
    "The pairs are gitignored and travel as a workflow artifact with a 14-day life. "
    "Take them from a digest run with: "
    "gh run download <run-id> --pattern 'evidence-*' --dir <dir>"
)


class NoEvidenceError(RuntimeError):
    """Raised instead of reporting a number over no pairs.

    A harness that prints 0.0 on an empty directory is indistinguishable from
    one that measured a real zero, and this project has already published a
    figure that way once (`docs/concepts/evaluation.md`, the 2,232 rows that
    never measured the gap).
    """


@dataclass(frozen=True, slots=True)
class Pair:
    """One measurement's two texts, and whether extract cut the article behind it."""

    key: str
    premise: str
    summary: str
    cut: bool | None

    @property
    def premise_words(self) -> int:
        return len(self.premise.split())


@dataclass(frozen=True, slots=True)
class Reading:
    """What one pair scored under each geometry, and what each pass cost."""

    key: str
    slices: int
    premise_words: int
    cut: bool | None
    narrow: float
    wide: float
    narrow_seconds: float
    wide_seconds: float

    @property
    def delta(self) -> float:
        """Today's score minus the single-slice score. Positive means today scores higher."""
        return self.narrow - self.wide


@dataclass(frozen=True, slots=True)
class Group:
    """A row of the report: n, the mean difference, and its spread."""

    label: str
    n: int
    mean: float
    lowest: float
    highest: float
    stdev: float


@dataclass(frozen=True, slots=True)
class Report:
    narrow: EvaluationConfig
    wide_words: int
    by_slices: tuple[Group, ...]
    by_cut: tuple[Group, ...]
    narrow_seconds_per_pass: Group
    wide_seconds_per_pass: Group


def slices_under(text: str, config: EvaluationConfig) -> int:
    return len(chunks(text, config.chunk_words, config.chunk_overlap_words))


def _cut_by_row(path: Path) -> dict[str, bool | None]:
    """Whether extract cut each measurement's article, keyed the way evidence is named.

    Read as the arithmetic rather than as the flag. `source_word_count` counts
    the body before `extract.truncation_cap_tokens` and `source_seen_word_count`
    counts what survived it, and the difference between them is the cut and
    nothing else (`docs/concepts/evaluation.md`). `truncation_flagged` changed
    meaning on 2026-08-28 and is true on one row in the whole ledger, so reading
    it here would split the table on a column that measures something else.

    An empty `source_word_count` is a row that does not know its own pre-cap
    length, and that is `None` rather than `False`.
    """
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        return {key_of(record): _cut_of(record) for record in csv.DictReader(handle)}


def _cut_of(record: Mapping[str, str]) -> bool | None:
    full = str(record.get("source_word_count") or "").strip()
    if not full:
        return None
    return int(full) > int(record["source_seen_word_count"])


def load_pairs(evidence_dir: Path, ledger: Path) -> list[Pair]:
    """Every pair in a downloaded evidence package, joined to the ledger for the cut.

    Refuses an empty package rather than returning an empty list. Every caller
    of this function goes on to divide by the count.
    """
    files = index(evidence_dir)
    if not files:
        raise NoEvidenceError(
            f"no evidence pairs under {evidence_dir.as_posix()} "
            f"(the pipeline writes them to {EVIDENCE_ROOT_RELPATH}/<date>/). {HOW_TO_GET_PAIRS}"
        )
    cut = _cut_by_row(ledger)
    pairs = []
    for key, path in sorted(files.items()):
        item = EvidenceItem.from_json(path.read_text(encoding="utf-8"))
        pairs.append(Pair(key=key, premise=item.premise, summary=item.summary, cut=cut.get(key)))
    return pairs


def single_slice_geometry(pairs: Sequence[Pair], narrow: EvaluationConfig) -> EvaluationConfig:
    """A window that holds the longest premise whole, so every item is one slice.

    Derived from the corpus rather than configured. The comparison needs one
    geometry under which no item is ever aggregated, and the smallest such
    window is the longest premise present - picking a round number larger than
    that would only make the wide pass slower for nothing.

    The overlap is zero because there is nothing to overlap with, and because
    `EvaluationConfig` refuses an overlap at or above the window.
    """
    widest = max(pair.premise_words for pair in pairs)
    return narrow.model_copy(update={"chunk_words": max(widest, 1), "chunk_overlap_words": 0})


def _timed(
    scorer: Scorer, premise: str, summary: str, config: EvaluationConfig
) -> tuple[float, float]:
    started = time.perf_counter()
    value = score_over_chunks(scorer, premise, summary, evaluation=config)
    return value, time.perf_counter() - started


def read(
    scorer: Scorer, pairs: Iterable[Pair], *, narrow: EvaluationConfig, wide: EvaluationConfig
) -> list[Reading]:
    """Score every pair twice. The narrow pass first, so a warm cache favours neither."""
    readings = []
    for pair in pairs:
        narrow_value, narrow_seconds = _timed(scorer, pair.premise, pair.summary, narrow)
        wide_value, wide_seconds = _timed(scorer, pair.premise, pair.summary, wide)
        readings.append(
            Reading(
                key=pair.key,
                slices=slices_under(pair.premise, narrow),
                premise_words=pair.premise_words,
                cut=pair.cut,
                narrow=narrow_value,
                wide=wide_value,
                narrow_seconds=narrow_seconds,
                wide_seconds=wide_seconds,
            )
        )
    return readings


def _group(label: str, values: Sequence[float]) -> Group:
    if not values:
        return Group(label=label, n=0, mean=0.0, lowest=0.0, highest=0.0, stdev=0.0)
    return Group(
        label=label,
        n=len(values),
        mean=statistics.fmean(values),
        lowest=min(values),
        highest=max(values),
        stdev=statistics.stdev(values) if len(values) > 1 else 0.0,
    )


def _slice_label(count: int) -> str:
    return "4+ slices" if count >= 4 else f"{count} slice" + ("" if count == 1 else "s")


def summarise(readings: Sequence[Reading], *, narrow: EvaluationConfig, wide_words: int) -> Report:
    """The table the row asks for: the difference by slice count, and by whether it was cut."""
    buckets: dict[str, list[float]] = {}
    for reading in readings:
        buckets.setdefault(_slice_label(reading.slices), []).append(reading.delta)
    by_slices = tuple(
        _group(label, buckets[label])
        for label in sorted(buckets, key=lambda name: (name == "4+ slices", name))
    )

    cut_labels = {True: "article was cut", False: "article was not cut", None: "cut unknown"}
    cuts: dict[str, list[float]] = {}
    for reading in readings:
        cuts.setdefault(cut_labels[reading.cut], []).append(reading.delta)
    by_cut = tuple(_group(label, cuts[label]) for label in sorted(cuts))

    return Report(
        narrow=narrow,
        wide_words=wide_words,
        by_slices=by_slices,
        by_cut=by_cut,
        narrow_seconds_per_pass=_group(
            f"{narrow.chunk_words}-word windows", [r.narrow_seconds for r in readings]
        ),
        wide_seconds_per_pass=_group(
            f"{wide_words}-word window", [r.wide_seconds for r in readings]
        ),
    )


def _row(group: Group, digits: int) -> str:
    return (
        f"  {group.label}: n={group.n} mean={group.mean:+.{digits}f} "
        f"spread={group.lowest:+.{digits}f} to {group.highest:+.{digits}f} "
        f"stdev={group.stdev:.{digits}f}"
    )


def lines_for(report: Report) -> list[str]:
    lines = [
        f"geometry now: {report.narrow.chunk_words}/{report.narrow.chunk_overlap_words} anchored",
        f"geometry wide: {report.wide_words} words, every item one slice",
        "today's score minus the single-slice score, by slice count:",
    ]
    lines.extend(_row(group, 4) for group in report.by_slices)
    lines.append("the same, by whether extract cut the article:")
    lines.extend(_row(group, 4) for group in report.by_cut)
    lines.append("seconds per pass:")
    lines.append(_row(report.narrow_seconds_per_pass, 3))
    lines.append(_row(report.wide_seconds_per_pass, 3))
    return lines


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--evidence",
        type=Path,
        default=Path(EVIDENCE_ROOT_RELPATH),
        help="a downloaded evidence package, in whatever shape the workflow uploaded it",
    )
    parser.add_argument("--scores", type=Path, default=Path(LEDGER_RELPATH))
    parser.add_argument("--config", type=Path, default=Path("config"))
    args = parser.parse_args(argv)

    narrow = load(args.config).app.evaluation
    pairs = load_pairs(args.evidence, args.scores)
    wide = single_slice_geometry(pairs, narrow)

    from idhazh.evals.hhem import HhemScorer

    scorer = HhemScorer()
    scorer.load()

    readings = read(scorer, pairs, narrow=narrow, wide=wide)
    print("\n".join(lines_for(summarise(readings, narrow=narrow, wide_words=wide.chunk_words))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
