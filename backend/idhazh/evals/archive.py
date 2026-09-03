"""Summarise a month of the eval ledger, and prove the summary before the rows go.

`state/scores/<YYYY-MM>.csv` is the committed record of how every summary scored.
Past `observability.scores_full_grain_months` it is turned into
`state/score-archive/<YYYY-MM>.json` and unlinked - and the whole safety
argument of this module is the order those two things happen in.

The summary is computed, written temp-then-rename, read back through its
contract, and reconciled field by field against a second reading of the shard.
Only then is the shard unlinked. Nothing is deleted on the strength of a write
nobody checked, and `.github/workflows/prune.yml` force-pushes `main` on a
schedule (`CLAUDE.md` section 8), so a shard this removes stops being
recoverable once the prune passes over it.

**The observation index is the half that is easy to forget.**
`evals.writer.recorded_observations` is what stops a run scoring an old
measurement again as if it were new, and it works by reading the rows. Delete a
shard with no index and every measurement in it becomes fresh again, which turns
a count over the ledger from a count of items into a count of times the pipeline
looked. So the archive stores one digest per distinct observation, sorted, and
the writer unions them with the live rows.

**The measurements are named here rather than discovered.** A column added to
`EvalRow` has to be filed as a signal or as a measurement in the same commit,
and `backend/tests/test_evals.py` refuses a column that is in neither - because
a column that quietly fell out of the archive is a column that stops existing
fourteen months later, silently.
"""

from __future__ import annotations

import csv
import hashlib
import tempfile
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Final

from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.eval_row import ConfidenceBand
from idhazh.contracts.score_archive import (
    DECILES,
    Moment,
    ScoreArchive,
    ScoreCohort,
    decile_of,
)
from idhazh.ledger import STATE_DIRNAME

ARCHIVE_DIRNAME: Final = "score-archive"
ARCHIVE_RELDIR: Final = f"{STATE_DIRNAME}/{ARCHIVE_DIRNAME}"

#: What a cohort is one of. Every field changes what a number over the group
#: means, which is the test for belonging here.
COHORT_KEY: Final = (
    "date",
    "run_id",
    "version",
    "model_id",
    "pipeline_fingerprint",
    "scorer_version",
)

#: Boolean columns of the eval row. Counted, never averaged: a count over
#: several cohorts is a sum, where a rate over several cohorts is an average of
#: averages and is wrong whenever the cohorts differ in size.
SIGNAL_COLUMNS: Final = (
    "truncation_flagged",
    "hedge_dropped",
    "extraction_suspect",
    "determinism_violation",
)

#: Numeric columns of the eval row, each stored as a moment. `attempt` is here
#: with the scores because it is a number a later reader asks about - how often
#: the summarizer had to try twice - and dropping it would make that
#: unanswerable for the month rather than merely coarse.
MEASUREMENT_COLUMNS: Final = (
    "attempt",
    "hhem",
    "hhem_full",
    "hhem_delta",
    "coverage",
    "compression",
    "extractiveness",
    "verbatim_run",
    "unsupported_numbers",
    "source_word_count",
    "source_seen_word_count",
    "summary_word_count",
    "score_ms",
    "evidential_density",
    "speculative_density",
    "self_repetition",
)

#: What a person reading a utility's refusal needs to know in one line.
RAW_WINDOW_NOTE: Final = (
    "state/scores/ keeps observability.scores_full_grain_months months of item-level "
    "rows. An older month exists only as state/score-archive/<YYYY-MM>.json, which "
    "carries totals, distributions, ranges, spread and the dedupe index, and no item."
)


def archive_relpath(month: str) -> str:
    """`state/score-archive/<YYYY-MM>.json` - the POSIX form, for a log line."""
    return f"{ARCHIVE_RELDIR}/{month}.json"


def archive_path(state_dir: Path, month: str) -> Path:
    """Where one month's summary lives, given a state tree.

    A caller passes the directory and the month and never the file name, so a
    second writer cannot spell the layout differently from the prune and have
    both be right.
    """
    return state_dir / ARCHIVE_DIRNAME / f"{month}.json"


def archive_files(state_dir: Path) -> list[Path]:
    """Every `<YYYY-MM>.json` in the archive directory, oldest first.

    Anything else in there is left alone. A directory a prune deletes from names
    what it recognises rather than acting on what it does not.
    """
    directory = state_dir / ARCHIVE_DIRNAME
    if not directory.is_dir():
        return []
    found = [path for path in directory.glob("*.json") if _is_month_stem(path.stem)]
    return sorted(found, key=lambda path: path.stem)


def archived_months(state_dir: Path) -> list[str]:
    """The months that exist only as a summary, oldest first."""
    return [path.stem for path in archive_files(state_dir)]


def _is_month_stem(stem: str) -> bool:
    return len(stem) == 7 and stem[4] == "-" and stem.replace("-", "").isdigit()


def digest_of(values: Iterable[str]) -> str:
    """The one digest an observation key is reduced to.

    Digested through the project's own canonical serialization rather than
    joined with a separator, so no value can contain the thing that separates
    two values - `scorer_version` carries semicolons, slashes and an at-sign,
    and a join is one grammar change away from two different keys digesting the
    same.
    """
    return derive_text_digest(canonical_json(list(values)))


def read_rows(shard: Path) -> list[dict[str, str]]:
    """One month of the ledger, as the CSV spells it."""
    with shard.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _number(cell: str | None) -> float | None:
    """A numeric cell, or nothing. An empty cell is absent, never zero."""
    text = (cell or "").strip()
    return float(text) if text else None


def _flag(cell: str | None) -> bool:
    return (cell or "").strip().lower() == "true"


def _moment(values: Sequence[float]) -> Moment:
    if not values:
        return Moment(n=0, sum=0.0, sum_squares=0.0)
    return Moment(
        n=len(values),
        sum=sum(values),
        sum_squares=sum(value * value for value in values),
        min=min(values),
        max=max(values),
    )


def _cohort(rows: Sequence[Mapping[str, str]]) -> ScoreCohort:
    """One group's numbers, computed from the rows the shard held for it."""
    first = rows[0]
    deciles = [0] * DECILES
    bands = dict.fromkeys(ConfidenceBand, 0)
    signals = dict.fromkeys(SIGNAL_COLUMNS, 0)
    columns: dict[str, list[float]] = {name: [] for name in MEASUREMENT_COLUMNS}
    cut_known = 0
    cut = 0
    premises: list[str] = []

    for row in rows:
        faithfulness = _number(row.get("hhem"))
        if faithfulness is not None:
            deciles[decile_of(faithfulness)] += 1
        bands[ConfidenceBand(row["band"])] += 1
        for name in SIGNAL_COLUMNS:
            if _flag(row.get(name)):
                signals[name] += 1
        for name in MEASUREMENT_COLUMNS:
            value = _number(row.get(name))
            if value is not None:
                columns[name].append(value)
        full = _number(row.get("source_word_count"))
        if full is not None:
            cut_known += 1
            if full > (_number(row.get("source_seen_word_count")) or 0.0):
                cut += 1
        premise = (row.get("source_digest") or "").strip()
        if premise:
            premises.append(premise)

    return ScoreCohort(
        date=first["date"],
        run_id=first["run_id"],
        row_version=first["version"],
        model_id=first["model_id"],
        pipeline_fingerprint=first["pipeline_fingerprint"],
        scorer_version=first["scorer_version"],
        rows=len(rows),
        hhem_deciles=deciles,
        bands=bands,
        signals=signals,
        cut_known=cut_known,
        cut=cut,
        premise_recorded=len(premises),
        premise_distinct=len(set(premises)),
        measurements={name: _moment(values) for name, values in columns.items()},
    )


def summarise(shard: Path, *, observation_key: Sequence[str]) -> ScoreArchive:
    """One month of the ledger as the shape that outlives it.

    `observation_key` is `evals.writer.OBSERVATION_KEY`, passed in rather than
    imported so this module stays below the writer that unions its digests back
    in. A wrong key would build a wrong index, which is why the caller that
    passes it is the same module that owns the dedupe.

    The source hash is over the shard's bytes, not over its parsed rows: what a
    reconcile has to prove is that this summary describes the file about to be
    unlinked, and two different files can parse to the same rows.
    """
    rows = read_rows(shard)
    grouped: dict[tuple[str, ...], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(tuple(row[name] for name in COHORT_KEY), []).append(row)

    digests = sorted({digest_of(row[name] for name in observation_key) for row in rows})
    return ScoreArchive(
        version=ScoreArchive.schema_version(),
        month=shard.stem,
        source_rows=len(rows),
        source_sha256=hashlib.sha256(shard.read_bytes()).hexdigest(),
        observation_digests=digests,
        cohorts=[_cohort(grouped[key]) for key in sorted(grouped)],
    )


def write(path: Path, archive: ScoreArchive) -> None:
    """Temp-then-rename, so the file either exists complete or does not exist.

    Spelled here rather than taken from `assemble.write_atomic`, which is four
    identical lines: `assemble` imports the embedder, so borrowing it would load
    onnxruntime into every prune and every archive read.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="\n", dir=path.parent, delete=False
    )
    try:
        with handle:
            handle.write(archive.to_json())
        Path(handle.name).replace(path)
    except BaseException:
        Path(handle.name).unlink(missing_ok=True)
        raise


def read(path: Path) -> ScoreArchive:
    """One archived month, through its contract. A malformed file raises here."""
    return ScoreArchive.from_json(path.read_text(encoding="utf-8"))


def reconcile(stored: ScoreArchive, shard: Path, *, observation_key: Sequence[str]) -> None:
    """Prove the file that was read back describes the shard, or raise saying which part does not.

    Compared field by field rather than with one equality test. A bare `!=` says
    the archive is wrong and nothing about how, and the person reading that
    message is deciding whether a committed file may be deleted.
    """
    fresh = summarise(shard, observation_key=observation_key)
    for name in ("month", "source_rows", "source_sha256"):
        _same(getattr(stored, name), getattr(fresh, name), shard, f"the shard's {name}")
    _same(
        stored.observation_digests,
        fresh.observation_digests,
        shard,
        f"the {len(fresh.observation_digests)} observation digests",
    )
    _same(
        [cohort.key for cohort in stored.cohorts],
        [cohort.key for cohort in fresh.cohorts],
        shard,
        f"the {len(fresh.cohorts)} cohort keys",
    )
    for mine, theirs in zip(stored.cohorts, fresh.cohorts, strict=True):
        where = f"cohort {'/'.join(theirs.key)}"
        _same(mine.rows, theirs.rows, shard, f"{where}: the row count")
        _same(mine.hhem_deciles, theirs.hhem_deciles, shard, f"{where}: the deciles")
        _same(mine.bands, theirs.bands, shard, f"{where}: the bands")
        _same(mine.signals, theirs.signals, shard, f"{where}: the signal counts")
        _same(
            (mine.cut_known, mine.cut),
            (theirs.cut_known, theirs.cut),
            shard,
            f"{where}: the cut",
        )
        _same(
            (mine.premise_recorded, mine.premise_distinct),
            (theirs.premise_recorded, theirs.premise_distinct),
            shard,
            f"{where}: the premise digests",
        )
        _same(mine.measurements, theirs.measurements, shard, f"{where}: the moments")


def _same(stored: object, fresh: object, shard: Path, what: str) -> None:
    if stored != fresh:
        raise ValueError(
            f"{archive_relpath(shard.stem)} does not reconcile with {shard.name}: "
            f"{what} reads back as {stored!r} and recomputes as {fresh!r}, so the shard stays"
        )


def archived_observations(state_dir: Path) -> set[str]:
    """Every measurement the archived months hold, as digests.

    The half of the dedupe that survives a deletion. A missing directory is a
    tree nothing has been archived out of, which is what a fresh clone has.
    """
    found: set[str] = set()
    for path in archive_files(state_dir):
        found.update(read(path).observation_digests)
    return found
