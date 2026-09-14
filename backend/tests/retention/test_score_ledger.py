"""When is a score month summarised, and what must reconcile before its days are deleted?"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import re
from pathlib import Path

import pytest
from conftest import CONTRACT_FIXTURES_DIR, read_text

from idhazh import day_partition
from idhazh.contracts.app_config import CollectConfig, ObservabilityConfig, RetentionConfig
from idhazh.contracts.eval_row import ConfidenceBand, EvalRow
from idhazh.evals import archive as score_archive
from idhazh.evals import writer as score_writer
from idhazh.retention import oldest_month_kept, prune_scores
from idhazh.stages.prune_state import stage_prune_state

from ._trees import (
    HISTORY_MONTHS,
    NOT_MONTHS,
    RUN_ID,
    TODAY,
    months_back,
)

pytestmark = pytest.mark.slow


def score_row(*, day: str, run: int, number: int) -> EvalRow:
    """One eval row, built off the committed fixture so every column is real-shaped.

    `hhem` walks the deciles and `band` follows it, so a fixture month exercises
    more than one bucket and more than one band - a summary that collapsed
    either would still pass a single-value fixture.
    """
    base = json.loads(read_text(CONTRACT_FIXTURES_DIR / "eval-row" / "high.json"))
    faithfulness = round(0.05 + (number % 10) / 10, 4)
    seed = f"{day}-{run}-{number}"
    band = (
        ConfidenceBand.HIGH
        if faithfulness >= 0.80
        else ConfidenceBand.MEDIUM
        if faithfulness >= 0.50
        else ConfidenceBand.LOW
    )
    return EvalRow.model_validate(
        {
            **base,
            "date": day,
            "run_id": f"{day}-{run}",
            "item_id": f"ai-{number:04d}",
            "url_key": hashlib.sha256(seed.encode("ascii")).hexdigest(),
            "output_digest": hashlib.sha256(f"out-{seed}".encode("ascii")).hexdigest(),
            "hhem": faithfulness,
            "hhem_full": faithfulness,
            "hhem_delta": 0.0,
            "band": band.value,
            "unsupported_numbers": number % 3,
            "hedge_dropped": number % 4 == 0,
            "extraction_suspect": number % 5 == 0,
            "source_word_count": 1320,
            "source_seen_word_count": 1320 - (number % 2) * 40,
            "score_ms": 1000 + number,
            "scored_at": f"{day}T06:18:02Z",
        }
    )

def score_history(state_dir: Path, months: list[str]) -> None:
    """Two real score days a month, written through the real appender."""
    for index, month in enumerate(months):
        for day_of_month in (4, 17):
            day = f"{month}-{day_of_month:02d}"
            score_writer.append(
                state_dir,
                [score_row(day=day, run=1, number=index * 100 + offset) for offset in range(6)],
            )

def a_score_tree(tmp_path: Path) -> Path:
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, HISTORY_MONTHS))
    return state

def score_months(state: Path) -> list[str]:
    """The months the score ledger's day files fall in, oldest first."""
    return sorted(day_partition.days_by_month(state / score_writer.LEDGER_DIRNAME))

def score_bytes(state: Path) -> dict[str, bytes]:
    """Every score day file's bytes, keyed by its `<YYYY>/<MM>/<DD>.csv` path."""
    return {
        day.relative_to(state).as_posix(): day.read_bytes()
        for day in score_writer.ledger_days(state)
    }

def test_a_score_month_past_the_window_is_summarised_and_then_deleted(tmp_path: Path) -> None:
    """The whole point: the day files go, and everything they could still answer stays."""
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    boundary = oldest_month_kept(TODAY, config.scores_full_grain_months)
    doomed = [month for month in score_months(state) if month < boundary]
    assert doomed, "the fixture has to reach past the window or this proves nothing"
    taken = [
        score_writer.ledger_relpath(f"{month}-{day.stem}")
        for month in doomed
        for day in day_partition.days_by_month(state / score_writer.LEDGER_DIRNAME)[month]
    ]

    result = prune_scores(state, config, TODAY)

    assert result.archived == tuple(doomed)
    assert result.dry_run is False
    assert list(result.days_removed) == taken, (
        "the day files a live run removed are not the ones a dry run would name"
    )
    assert score_months(state) == [
        month for month in months_back(TODAY, HISTORY_MONTHS) if month >= boundary
    ]
    for month in doomed:
        emptied = state / score_writer.LEDGER_DIRNAME / month[:4] / month[5:7]
        assert not emptied.exists(), f"{month} left an empty month directory behind"
    assert score_archive.archived_months(state) == doomed
    # Every archived month reads back through its contract and still adds up.
    for month in doomed:
        stored = score_archive.read(score_archive.archive_path(state, month))
        assert stored.month == month
        assert sum(cohort.rows for cohort in stored.cohorts) == stored.source_rows
        assert len(stored.observation_digests) == stored.source_rows
    assert result.rows_archived == sum(
        score_archive.read(score_archive.archive_path(state, month)).source_rows for month in doomed
    )

def test_a_score_month_inside_the_window_is_untouched(tmp_path: Path) -> None:
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, 3))
    held = score_bytes(state)

    result = prune_scores(state, ObservabilityConfig(), TODAY)

    assert result.changed is False
    assert result.archived == ()
    assert result.days_removed == ()
    assert score_bytes(state) == held
    assert score_archive.archived_months(state) == []

def test_a_score_dry_run_writes_nothing_and_still_counts_both_sides(tmp_path: Path) -> None:
    """The dry run's own deliverable is the byte ratio, so it has to compute it.

    A dry run that reported only a file list would leave the person deciding
    whether to switch the deletion on with no idea what the archive costs
    (Guardrail #10). It summarises, measures both sides, and writes nothing.
    """
    state = a_score_tree(tmp_path)
    held = score_bytes(state)

    result = prune_scores(state, ObservabilityConfig(), TODAY, dry_run=True)

    assert result.dry_run is True
    assert result.archived
    assert result.days_removed, "a dry run that names no file is not a deliverable"
    assert result.source_bytes > 0
    assert result.archive_bytes > 0
    assert score_bytes(state) == held
    assert score_archive.archived_months(state) == []
    assert not (state / score_archive.ARCHIVE_DIRNAME).exists()

def test_a_month_with_real_volume_summarises_to_a_fraction_of_its_shard(tmp_path: Path) -> None:
    """The measurement the policy rests on, pinned as a direction rather than a figure.

    Two costs make up an archive: one digest per distinct measurement, which is
    64 hex characters against a whole CSV row of thirty-odd columns, and a fixed
    block of moments per cohort. The first is what saves the bytes and the
    second is what a thin month pays anyway - so a twelve-row month really does
    summarise LARGER than it held, and a month with a run's worth of rows in it
    does not. Fourteen-month-old months are the full ones, which is why this
    direction is the one that matters. The measured figure and its date are in
    `docs/reference/measurements.md`.
    """
    state = tmp_path / "state"
    day = "2025-01-09"
    score_writer.append(state, [score_row(day=day, run=1, number=n) for n in range(200)])
    days = score_writer.ledger_days(state)
    source_bytes = sum(path.stat().st_size for path in days)

    built = score_archive.summarise(
        days, month=day[:7], observation_key=score_writer.OBSERVATION_KEY
    )
    archive_bytes = len(built.to_json().encode("utf-8"))

    assert built.source_rows == 200
    assert len(built.cohorts) == 1
    assert archive_bytes * 2 < source_bytes, (
        f"{archive_bytes} bytes of archive against {source_bytes} of rows is not a saving"
    )

def test_a_second_score_run_over_a_settled_tree_moves_no_byte(tmp_path: Path) -> None:
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    prune_scores(state, config, TODAY)
    settled = {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*"))
        if path.is_file()
    }

    again = prune_scores(state, config, TODAY)

    assert again.changed is False
    assert {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*"))
        if path.is_file()
    } == settled

def test_a_score_file_the_reader_cannot_place_stops_the_prune(tmp_path: Path) -> None:
    """A stray is refused now, where the month reader used to walk past it.

    `day_partition.day_files` refuses a name it cannot place, so a store holding
    one is unreadable rather than partly readable - and the prune it stops is the
    one that deletes. It is the stronger of the two behaviours and it is why this
    store went to the day tree's rule rather than keeping its own: a file the
    reader skips is a month it might summarise without.
    """
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, HISTORY_MONTHS))
    stray = state / score_writer.LEDGER_DIRNAME / "notes.csv"
    stray.write_text("nothing the contract knows\n", encoding="utf-8")
    before = {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*"))
        if path.is_file()
    }

    with pytest.raises(ValueError, match=re.escape("notes.csv")):
        prune_scores(state, ObservabilityConfig(), TODAY)

    assert {
        path.relative_to(state).as_posix(): path.read_bytes()
        for path in sorted(state.rglob("*"))
        if path.is_file()
    } == before, "the refused pass deleted something anyway"

def test_a_month_shaped_name_beside_the_day_tree_is_refused_rather_than_archived(
    tmp_path: Path,
) -> None:
    """The defect this row exists for, on the one store where it deleted a file.

    `prune_scores` summarises a month past the window and then unlinks its day
    files. Its reader used to accept any seven characters of the right shape, so
    `2025-13.csv` was archived into `state/score-archive/` and then deleted here,
    while `prune_feed_health` - reading the strict rule - left the same name
    alone. Nothing in this repository writes `2025-13.csv`, so nothing could have
    said afterwards what was in it, and `prune.yml` force-pushes `main`.

    **The day tree closes it harder than the strict month rule did.** A
    month-shaped name at the root of a day tree is a name
    `day_partition.day_files` cannot place, so the whole read is refused and this
    prune archives nothing at all - where the strict rule merely walked past the
    file. The name survives either way; what is stronger here is that a half-read
    store can no longer produce a summary.
    """
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, HISTORY_MONTHS))
    strays = {
        state / score_writer.LEDGER_DIRNAME / f"{stem}.csv": f"{stem} was never written\n"
        for stem in NOT_MONTHS
    }
    for path, text in strays.items():
        path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="day file"):
        prune_scores(state, ObservabilityConfig(), TODAY)

    assert {path: path.read_text(encoding="utf-8") for path in strays} == strays
    assert not (state / score_archive.ARCHIVE_DIRNAME).exists(), (
        "a store the reader cannot walk produced a summary anyway"
    )

def test_an_archive_that_does_not_reconcile_leaves_its_days(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nothing is deleted on the strength of a summary nobody checked.

    The read-back is not enough on its own: a file that parses can still
    describe a different month. So the reconcile recomputes from the day files
    and compares, and a disagreement raises with every one of them still on disk.
    """
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    boundary = oldest_month_kept(TODAY, config.scores_full_grain_months)
    by_month = day_partition.days_by_month(state / score_writer.LEDGER_DIRNAME)
    doomed = [day for month, days in by_month.items() if month < boundary for day in days]
    assert doomed
    honest = score_archive.read

    def one_row_short(path: Path) -> object:
        stored = honest(path)
        return stored.model_copy(update={"source_rows": stored.source_rows + 1})

    monkeypatch.setattr(score_archive, "read", one_row_short)

    with pytest.raises(ValueError, match="does not reconcile"):
        prune_scores(state, config, TODAY)

    assert all(day.exists() for day in doomed), (
        "a day file was unlinked against a summary that disagreed"
    )

def test_the_archive_is_kept_forever_unless_somebody_asks_for_the_bytes_back(
    tmp_path: Path,
) -> None:
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    assert config.score_archive_keep_months is None

    result = prune_scores(state, config, TODAY)

    assert result.hard_deleted == ()
    assert score_archive.archived_months(state)

def test_a_hard_delete_takes_the_archive_only_after_the_month_has_been_archived(
    tmp_path: Path,
) -> None:
    """A finite archive age must sit above the full-grain window, and does.

    Fifteen against fourteen, so the month that is deleted outright is one that
    was summarised on an earlier pass rather than one that never was.
    """
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig(scores_full_grain_months=14, score_archive_keep_months=15)
    prune_scores(state, ObservabilityConfig(), TODAY)
    before = score_archive.archived_months(state)
    assert len(before) > 1

    result = prune_scores(state, config, TODAY)

    assert result.hard_deleted == tuple(
        month for month in before if month < oldest_month_kept(TODAY, 15)
    )
    assert result.hard_deleted, "the fixture has to reach past both ages"
    assert score_archive.archived_months(state) == [
        month for month in before if month not in result.hard_deleted
    ]

def test_the_oracle_an_archived_month_reconciles_and_is_still_refused_as_a_repeat(
    tmp_path: Path,
) -> None:
    """The row's Oracle, both halves.

    First: the archive's source hash and row count match the day files, its
    observation digests are one-for-one with their own observation keys,
    and its moments recompute exactly - checked against the raw CSV rather than
    by calling the summariser again, so the oracle cannot pass by agreeing with
    the code it is checking.

    Second, and the one that matters most: after the rows are gone, every
    measurement they held is still refused as a repeat. Without that, the day a
    month is deleted every row in it becomes scoreable again as if it were new.
    """
    state = a_score_tree(tmp_path)
    config = ObservabilityConfig()
    boundary = oldest_month_kept(TODAY, config.scores_full_grain_months)
    by_month = day_partition.days_by_month(state / score_writer.LEDGER_DIRNAME)
    month = next(name for name in sorted(by_month) if name < boundary)
    days = sorted(by_month[month])
    raw = [
        record
        for day in days
        for record in csv.DictReader(io.StringIO(day.read_text(encoding="utf-8")))
    ]
    rolling = hashlib.sha256()
    for day in days:
        rolling.update(day.read_bytes())
    fingerprint = rolling.hexdigest()
    keys = {tuple(row[name] for name in score_writer.OBSERVATION_KEY) for row in raw}
    hhem_by_cohort: dict[tuple[str, ...], list[float]] = {}
    for row in raw:
        cohort = tuple(row[name] for name in score_archive.COHORT_KEY)
        hhem_by_cohort.setdefault(cohort, []).append(float(row["hhem"]))
    doomed = list(raw)

    prune_scores(state, config, TODAY)

    stored = score_archive.read(score_archive.archive_path(state, month))
    assert stored.source_sha256 == fingerprint
    assert stored.source_rows == len(raw)
    assert set(stored.observation_digests) == {score_archive.digest_of(key) for key in keys}
    assert len(stored.observation_digests) == len(keys)
    for group in stored.cohorts:
        values = hhem_by_cohort[group.key]
        moment = group.measurements["hhem"]
        assert moment.n == len(values)
        assert moment.sum == pytest.approx(sum(values))
        assert moment.sum_squares == pytest.approx(sum(value * value for value in values))
        assert moment.min == pytest.approx(min(values))
        assert moment.max == pytest.approx(max(values))

    # The second half. Every row of the deleted month, offered again.
    assert not any(day.exists() for day in days)
    replayed = [
        EvalRow.model_validate({key: value for key, value in row.items() if value != ""})
        for row in doomed
    ]
    assert score_writer.append(state, replayed) == 0, (
        "a deleted month made its measurements new again"
    )
    assert not any(day.exists() for day in days), (
        "the replay recreated a day file the archive replaced"
    )

def test_the_stage_names_the_score_day_files_a_live_run_would_remove(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The dry run names every score day file too, in the POSIX form section 2 asks for.

    Each one by name, not a synthesised `<month>-01`: a month is a directory now,
    so a caller that spelled one would name a file the ledger may never have held.
    """
    state = tmp_path / "state"
    config = ObservabilityConfig()
    months = months_back(TODAY, config.scores_full_grain_months + 1)
    score_history(state, months)
    expired = months[0]
    doomed = sorted(
        score_writer.ledger_relpath(f"{expired}-{day.stem}")
        for day in day_partition.days_by_month(state / score_writer.LEDGER_DIRNAME)[expired]
    )
    assert len(doomed) > 1, "one day a month would not separate a path from a synthesis"

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=config,
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
                dry_run=True,
            )
            == 0
        )

    named = sorted(
        line.split("would remove ", 1)[1]
        for line in caplog.text.splitlines()
        if "prune-state would remove " in line and not line.endswith("files:")
    )
    assert named == doomed
    assert "\\" not in caplog.text, "a path leaving the process is POSIX (section 2)"
    assert score_writer.ledger_days(state), "a dry run deleted the ledger"

def test_the_stage_says_so_when_every_score_month_is_at_full_grain(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Silence and "nothing aged out" read the same, and only one of them is true."""
    state = tmp_path / "state"
    score_history(state, months_back(TODAY, 2))

    with caplog.at_level(logging.INFO):
        assert (
            stage_prune_state(
                observability=ObservabilityConfig(),
                collect=CollectConfig(),
                retention_config=RetentionConfig(),
                run_id=RUN_ID,
                today=TODAY,
                state_dir=state,
            )
            == 0
        )

    assert "score archive: every month is inside the 14-month window" in caplog.text
