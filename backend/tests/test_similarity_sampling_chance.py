"""What chance had a pair of being taken and usable, and does the night file it with that chance?

The arithmetic over a slice's counts, and the collecting job that applies it: what it files
through the ledger door is what every later reader of the night works from.

Every row and every file here is built in the test that uses it. Nothing walks the committed
ledger (CLAUDE.md section 13).
"""

from __future__ import annotations

import logging
from hashlib import sha256
from pathlib import Path
from typing import Final

import pytest
from support.judged_pairs import a_night_of_pairs, a_reading, a_saver, a_verdict_file
from support.ledger import SEED_COMMIT

from idhazh import atomic_write, ledger
from idhazh.content_similarity_judge import tenant
from idhazh.content_similarity_judge.ledger_reads import load_pair_verdicts, load_threshold_history
from idhazh.content_similarity_judge.tenant import JUDGE_ID
from idhazh.contracts.base import derive_text_digest, derive_url_key
from idhazh.contracts.council_invocation import (
    ArtifactFile,
    PreparationReceipt,
    SelectedJudge,
    Selection,
)
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.knobs.council import JudgeLifecycleStatus
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import LedgersConfig
from idhazh.contracts.story_similarity_diagnostics import (
    SampleStatus,
    SliceOutcomes,
    read_diagnostic_text,
)
from idhazh.contracts.story_similarity_pair_verdict import (
    JUDGE_POLICY_VERSION,
    PairBucket,
    StorySimilarityPairVerdict,
)
from idhazh.contracts.story_similarity_threshold_history_row import (
    StorySimilarityThresholdHistoryRow,
)
from idhazh.council import metrics_sink, session
from idhazh.similarity.sample_diagnostics import sample_columns
from idhazh.similarity.sampling_chance import with_sampling_chance
from idhazh.stages import file_pair_verdicts

DATE: Final = "2026-09-18"

#: The name the council night these tests settle files its rows under.
RUN: Final = f"{DATE}-9"

#: Where each slice below sits, the way the draw cut them at the committed thresholds.
UPPER_THIN: Final = (PairBucket.UPPER_THIN, 0.90, 0.91)
SIMILAR: Final = (PairBucket.FULLY_SIMILAR, 0.93, 1.0)
LOWER_THIN: Final = (PairBucket.LOWER_THIN, 0.70, 0.71)


def a_row(
    index: int,
    *,
    cut: tuple[PairBucket, float, float] = UPPER_THIN,
    available: int = 10,
    judged: int = 4,
    agree: bool | None = True,
    shard: int = 0,
    date: str = DATE,
    run_id: str = RUN,
    pair: int | None = None,
) -> StorySimilarityPairVerdict:
    """One pair of a slice, judged to agree or disagree with itself, or not judged at all.

    `agree` of `None` is a pair a shard has not read. The score sits in the middle of the
    slice, and the thresholds are the committed starts, so the contract's own checks on
    the bucket and the score are the ones that run.
    """
    bucket, low, high = cut
    left, right = sorted(
        (
            derive_url_key(f"https://left.example/{index if pair is None else pair}"),
            derive_url_key(f"https://right.example/{index if pair is None else pair}"),
        )
    )
    score = round((low + high) / 2, 4) if bucket is not PairBucket.FULLY_SIMILAR else 0.95
    raw: dict[str, object] = {
        "date": date,
        "run_id": run_id,
        "work_part_index": shard,
        "pair_key": derive_text_digest(left + right),
        "left_url_key": left,
        "right_url_key": right,
        "similarity_score": score,
        "cosine": score,
        "headline": False,
        "scorer_model": "all-minilm-l6-v2-quantized",
        "cosine_weight": 1.0,
        "bucket": bucket,
        "slice_low": low,
        "slice_high": high,
        "slice_pairs_available": available,
        "slice_pairs_judged": judged,
        "lower_threshold_in_force": 0.7,
        "upper_threshold_in_force": 0.93,
        "config_versions": '{"judges/content-similarity-judge.json":"2026-11-19"}',
    }
    if agree is not None:
        raw |= {
            "verdict": "YES",
            "verdict_swapped": "YES" if agree else "NO",
            "readings_agree": agree,
            "judge_model": "qwen3-5-9b-q4-k-m",
            "prompt_digest": "a" * 64,
            "grammar_digest": "b" * 64,
            "judge_temperature": 0.0,
            "thinking_spans": 0,
            "grammar_applied": True,
            "judge_policy_version": JUDGE_POLICY_VERSION,
        }
    return StorySimilarityPairVerdict.model_validate(raw)


def test_a_slices_chance_is_its_usable_pairs_over_the_pairs_it_held() -> None:
    """A hand-worked night over three slices, and every row of a slice carries its slice's number.

    The thin slice held 10 pairs, the draw took 4, and 3 of those agree with themselves:
    a chance of 0.3 on all four rows, including the row that disagreed. The similar end
    held 7, took 2 and both agree: 2/7. The lower slice took one pair that disagreed, so
    nothing in it is usable and its chance is zero - a fact about the night, and not a
    missing value.
    """
    rows = [
        *(a_row(index, agree=index != 3) for index in range(4)),
        *(a_row(10 + index, cut=SIMILAR, available=7, judged=2) for index in range(2)),
        a_row(20, cut=LOWER_THIN, available=3, judged=1, agree=False),
    ]

    filled = with_sampling_chance(rows)

    assert [(row.slice_pairs_usable, row.sampling_chance) for row in filled] == [
        (3, 0.3), (3, 0.3), (3, 0.3), (3, 0.3), (2, 2 / 7), (2, 2 / 7), (0, 0.0),
    ]
    assert [row.verdict for row in filled] == [row.verdict for row in rows], "nothing else moves"


def test_a_pair_that_left_no_row_lowers_the_chance_of_its_slice() -> None:
    """The draw took 4 pairs and one runner was lost, so 3 rows came back and 3 agree.

    The chance is 3 usable over 10 held, the same 0.3 as when all four are read and one
    disagrees: a pair that was never read is a pair that was not usable.
    """
    rows = [a_row(index) for index in range(3)]

    assert {row.sampling_chance for row in with_sampling_chance(rows)} == {0.3}


def test_rows_of_one_slice_that_disagree_about_what_it_held_are_refused() -> None:
    """Only rows of one draw agree on a slice's size, so a stray row is not weighed."""
    rows = [a_row(0), a_row(1, available=11)]

    with pytest.raises(ValueError, match="not from one draw"):
        with_sampling_chance(rows)


def a_night(
    root: Path, per_unit: list[list[StorySimilarityPairVerdict]]
) -> tuple[Path, Path]:
    """A night's units as they leave a runner: a verdict file and a shipped reading each."""
    shipped, verdicts = root / "shipped", root / "verdicts"
    for unit, rows in enumerate(per_unit):
        metrics_sink.ship_judge_metrics(
            a_reading(shard=unit, dealt=len(rows), date=DATE, run_id=RUN),
            judge_id=JUDGE_ID,
            name=str(unit),
            out_dir=shipped,
        )
        atomic_write.write_atomic(verdicts / f"{DATE}-{JUDGE_ID}-{unit:02d}.csv", a_verdict_file(rows))
    return shipped, verdicts


def a_hand_worked_night() -> list[list[StorySimilarityPairVerdict]]:
    """Two units of three slices, the thin slice split across both: 3 of its 4 agree."""
    return [
        [a_row(0, shard=0), a_row(1, shard=0, agree=False), a_row(10, cut=SIMILAR, available=7, judged=2, shard=0)],
        [a_row(2, shard=1), a_row(3, shard=1), a_row(10 + 1, cut=SIMILAR, available=7, judged=2, shard=1)],
    ]


def file_the_night(
    root: Path, state: Path, per_unit: list[list[StorySimilarityPairVerdict]], *, expected: int = 2
) -> file_pair_verdicts.FileReport:
    shipped, verdicts = a_night(root, per_unit)
    return file_pair_verdicts.stage_file_pair_verdicts(
        DATE,
        run_id=RUN,
        judge_id=JUDGE_ID,
        shipped_root=shipped,
        verdicts_dir=verdicts,
        identity=a_saver(RUN),
        expected_shards=expected,
        state_dir=state,
    )


def test_every_row_the_night_files_carries_the_chance_of_its_slice(tmp_path: Path) -> None:
    """Read back through the door: 6 rows, the thin slice at 3/10 and the similar end at 2/7."""
    state = tmp_path / "state"

    report = file_the_night(tmp_path, state, a_hand_worked_night())

    filed = load_pair_verdicts(state, [DATE])
    (raw_file,) = ledger.list_raw_files(
        state, LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS, days=[DATE]
    )
    assert (report.rows_filed, report.shards_present, report.runners_reported) == (6, 2, 2)
    assert isinstance(report.filed_rows, tuple)
    assert {row.pair_key: row for row in report.filed_rows} == {row.pair_key: row for row in filed}
    assert sorted((row.work_part_index, row.pair_key) for row in filed) == sorted(
        (row.work_part_index, row.pair_key) for unit in a_hand_worked_night() for row in unit
    )
    assert {row.sampling_chance for row in filed if row.bucket is PairBucket.UPPER_THIN} == {0.3}
    assert {
        (row.slice_pairs_usable, row.sampling_chance)
        for row in filed
        if row.bucket is PairBucket.FULLY_SIMILAR
    } == {(2, 2 / 7)}
    assert raw_file.envelope.identity.producer == file_pair_verdicts.PRODUCER
    assert raw_file.envelope.identity.run_id == RUN


def test_a_night_that_lost_a_runner_files_the_rows_the_others_returned(tmp_path: Path) -> None:
    """One unit never shipped anything, so its pairs are gone and every other pair is kept.

    The slice chances fall, because a pair that left no row was not usable, and the night
    is not held back: the scheduler reads a night as done once it has any row.
    """
    state = tmp_path / "state"
    survivors = a_hand_worked_night()[:1]

    report = file_the_night(tmp_path, state, survivors, expected=2)

    filed = load_pair_verdicts(state, [DATE])
    assert (report.rows_filed, report.shards_present, report.shards_expected) == (3, 1, 2)
    assert len(filed) == 3
    assert {row.sampling_chance for row in filed if row.bucket is PairBucket.UPPER_THIN} == {0.1}
    assert {row.sampling_chance for row in filed if row.bucket is PairBucket.FULLY_SIMILAR} == {
        1 / 7
    }


@pytest.mark.parametrize(
    ("stray", "refused"),
    [
        (a_row(0, date="2026-09-17", run_id="2026-09-17-9"), "another night's artifact"),
        (a_row(0, run_id="2026-09-18-8"), "another night's artifact"),
    ],
    ids=["another date", "another run"],
)
def test_a_row_from_another_nights_artifact_stops_the_night_before_anything_is_filed(
    tmp_path: Path, stray: StorySimilarityPairVerdict, refused: str
) -> None:
    """The door would file it under its own date and let its own run stand, unseen.

    A foreign row would skew its slice's chance, and dropping it would read as a lost
    runner, so the whole night is refused and nothing is written.
    """
    state = tmp_path / "state"
    night = a_hand_worked_night()
    night[0].append(stray)

    with pytest.raises(ValueError, match=refused):
        file_the_night(tmp_path, state, night)

    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS).exists()


def test_a_pair_that_comes_back_twice_stops_the_night_before_anything_is_filed(
    tmp_path: Path,
) -> None:
    state = tmp_path / "state"
    night = a_hand_worked_night()
    night[1].append(a_row(0, shard=1))

    with pytest.raises(ValueError, match="came back twice"):
        file_the_night(tmp_path, state, night)

    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS).exists()


def test_a_night_whose_units_shipped_nothing_files_nothing(tmp_path: Path) -> None:
    """An empty upload is a night with no tenant, never a run to fail."""
    state = tmp_path / "state"

    report = file_pair_verdicts.stage_file_pair_verdicts(
        DATE,
        run_id=RUN,
        judge_id=JUDGE_ID,
        shipped_root=tmp_path / "nothing-was-uploaded",
        verdicts_dir=tmp_path / "nothing-was-judged",
        identity=a_saver(RUN),
        expected_shards=0,
        state_dir=state,
    )

    assert (report.rows_filed, report.shards_present, report.runners_reported) == (0, 0, 0)
    assert report.filed_rows == ()
    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS).exists()


def test_a_nonempty_batch_declined_by_the_ledger_is_not_an_empty_attempt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS
    registry = ledger.paths._CONFIG.model_dump(mode="json")
    family = next(
        family
        for family in registry["families"]
        if any(held["name"] == which for held in family["ledgers"])
    )
    family["lifecycle_status"] = "paused"
    monkeypatch.setattr(ledger.paths, "_CONFIG", LedgersConfig.model_validate(registry))
    state = tmp_path / "state"

    report = file_the_night(tmp_path, state, a_hand_worked_night())

    assert report.rows_filed == 0 and report.filed_rows is None
    assert not ledger.raw_root(state, which).exists()
    draw = a_night_of_pairs([(0.95, "YES")], date=DATE, answered=False)
    columns = sample_columns(
        draw, report.filed_rows, date=DATE, run_id=RUN, cutoff=0.87, upper_cutoff=0.93
    )
    assert columns == {"sample_status": SampleStatus.NOT_FILED, "pairs_drawn": 1}


def test_the_log_line_counts_the_units_that_reported_and_files_no_totals_of_its_own(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The readings the units shipped are counted, not summed: the totals ride the night's row."""
    with caplog.at_level(logging.INFO, logger="idhazh"):
        file_the_night(tmp_path, tmp_path / "state", a_hand_worked_night())

    said = next(
        record.getMessage() for record in caplog.records if "file-pair-verdicts" in record.getMessage()
    )
    assert "shards=2/2 filed=6 runners_reported=2" in said
    assert "dealt=" not in said


def test_sample_ranking_admits_the_whole_tie_that_reaches_90_percent_recall() -> None:
    pairs = [(0.96, "YES")] * 8 + [(0.87, "YES"), (0.87, "NO"), (0.40, "YES")]
    draw = a_night_of_pairs(pairs, date=DATE, answered=False)
    filed = a_night_of_pairs(pairs, date=DATE)

    def measurements(rows: list[StorySimilarityPairVerdict]) -> dict[str, str | int | float | None]:
        return sample_columns(draw, rows, date=DATE, run_id=RUN, cutoff=0.87, upper_cutoff=0.93)

    columns = measurements(filed)
    assert columns == measurements(list(reversed(filed)))
    assert columns["sample_average_precision"] == pytest.approx(4 / 5 + 9 / 100 + 1 / 11)
    assert columns["sample_precision_at_recall_90"] == 0.9
    assert columns["sample_recall_90_cutoff"] == 0.87
    assert columns["sample_recall_at_recall_90_cutoff"] == 0.9


def test_a_binary_sample_without_yes_has_no_ranking_but_can_have_zero_error() -> None:
    pairs = [(0.40, "NO")]
    columns = sample_columns(
        a_night_of_pairs(pairs, date=DATE, answered=False),
        a_night_of_pairs(pairs, date=DATE),
        date=DATE,
        run_id=RUN,
        cutoff=0.87,
        upper_cutoff=0.93,
    )
    assert columns["sample_tn"] == 1
    assert columns["cutoff_brier_score"] == columns["upper_cutoff_brier_score"] == 0.0
    assert columns["sample_precision"] is columns["sample_recall"] is None
    assert columns["sample_f0_5"] is columns["upper_cutoff_false_match_share"] is None
    assert columns.get("sample_average_precision") is None
    assert columns.get("sample_precision_at_recall_90") is None


def test_settlement_files_only_this_attempts_exact_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Read the real history partition after a full, shorter and empty attempt of one run."""
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "var" / "council")
    state = tmp_path / "state"
    sample: list[tuple[float, str | tuple[str, str]]] = [
        (0.96, "NO"),
        (0.93, "YES"),
        (0.87, "YES"),
        (0.86, "NO"),
        (0.40, "YES"),
        (0.50, "NO"),
        (0.89, "UNCLEAR"),
        (0.89, ("YES", "NO")),
        (0.89, "NO"),
        (0.78, "YES"),
        (0.89, "YES"),
    ]
    draw_rows = [
        row.model_copy(update={"work_part_index": i % 2})
        for i, row in enumerate(a_night_of_pairs(sample, answered=False, date=DATE))
    ]
    returned = [
        row.model_copy(
            update={
                "work_part_index": i % 2,
                "sampling_chance": None,
                "slice_pairs_usable": None,
            }
        )
        for i, row in enumerate(a_night_of_pairs(sample, date=DATE)[:9])
    ]
    returned[8] = returned[8].model_copy(
        update={
            "verdict": None,
            "verdict_swapped": None,
            "readings_agree": False,
            "grammar_applied": False,
        }
    )

    def settle(attempt: int, count: int) -> StorySimilarityThresholdHistoryRow:
        monkeypatch.setenv("GITHUB_RUN_ATTEMPT", str(attempt))
        selection = Selection(
            version=Selection.schema_version(),
            run_id=RUN,
            attempt=attempt,
            git_sha=SEED_COMMIT,
            mode="scheduled",
            anchor_date=DATE,
            window=(DATE,),
            judges=(
                SelectedJudge(
                    tenant=JUDGE_ID, status=JudgeLifecycleStatus.ACTIVE, dates=(DATE,), shards=2
                ),
            ),
        )
        with session._route(selection, JUDGE_ID):
            draw = tenant._draw_path(DATE)
            document = a_verdict_file(draw_rows).encode("utf-8")
            atomic_write.write_atomic_bytes(draw, document)
            prepared = PreparationReceipt(
                version=PreparationReceipt.schema_version(),
                run_id=RUN,
                attempt=attempt,
                git_sha=SEED_COMMIT,
                judge_id=JUDGE_ID,
                date=DATE,
                state="ready",
                shards=2,
                files=(
                    ArtifactFile(
                        path=session.artifact_path(draw),
                        size_bytes=len(document),
                        sha256=sha256(document).hexdigest(),
                    ),
                ),
            )
            for shard in range(2):
                atomic_write.write_atomic(
                    tenant._verdict_path(DATE, shard=shard),
                    a_verdict_file(returned[:count][shard::2]),
                )
            if attempt == 1:
                # Runner 1 left rows despite not shipping a reading. Runner 0 says one
                # pair was unreadable; that pair is already unreturned in the draw.
                report = a_reading(shard=0, dealt=6, date=DATE, run_id=RUN).model_copy(
                    update={
                        "pairs_valid": 4,
                        "pairs_agreed": 4,
                        "pairs_refused": 1,
                        "pairs_unreadable": 1,
                        "unclear_rate": 0.25,
                    }
                )
                metrics_sink.ship_judge_metrics(
                    report, judge_id=JUDGE_ID, name="0", out_dir=tenant._shipping_dir(DATE)
                )
            settled = tenant.TENANT.settle(
                date=DATE,
                run_id=RUN,
                state_dir=state,
                identity=a_saver(RUN).model_copy(update={"attempt": attempt}),
                prepared=prepared,
                reports=(),
            )
        assert settled.outcome is ShardOutcome.COMPLETED
        (filed_row,) = load_threshold_history(state, [DATE])
        assert (filed_row.date, filed_row.run_id) == (DATE, RUN)
        return filed_row

    first = settle(1, count=9)
    assert first.sample_status is SampleStatus.MEASURED
    assert (first.runners_expected, first.runners_reported, first.pairs_dealt) == (2, 1, 6)
    assert (first.pairs_unreadable, first.pairs_refused, first.unclear_rate) == (1, 1, 0.25)
    assert (first.pairs_drawn, first.pairs_returned) == (11, 9)
    assert first.slice_outcomes is not None
    slices = read_diagnostic_text(first.slice_outcomes, column="slice_outcomes", model=SliceOutcomes)
    assert {
        (one.low, one.high): (
            one.available,
            one.drawn,
            one.yes,
            one.no,
            one.unclear,
            one.split,
            one.refused,
            one.drawn - one.returned,
        )
        for one in slices.slices
    } == {
        (-1.0, 0.70): (6, 2, 1, 1, 0, 0, 0, 0),
        (0.76, 0.80): (3, 1, 0, 0, 0, 0, 0, 1),
        (0.84, 0.87): (3, 1, 0, 1, 0, 0, 0, 0),
        (0.87, 0.88): (3, 1, 1, 0, 0, 0, 0, 0),
        (0.89, 0.90): (12, 4, 0, 0, 1, 1, 1, 1),
        (0.93, 1.0): (6, 2, 1, 1, 0, 0, 0, 0),
    }
    assert first.evaluated_cutoff == 0.87
    assert (first.sample_tp, first.sample_fp, first.sample_fn, first.sample_tn) == (2, 1, 1, 2)
    assert (first.sample_precision, first.sample_recall, first.sample_f0_5) == pytest.approx(
        (2 / 3, 2 / 3, 2 / 3)
    )
    assert first.cutoff_brier_score == pytest.approx(2 / 6)
    assert first.upper_cutoff_sample_size == 2
    assert first.upper_cutoff_false_match_share == 0.5
    assert first.upper_cutoff_brier_score == 0.5
    assert first.sample_average_precision == pytest.approx(5 / 9)
    assert (
        first.sample_precision_at_recall_90,
        first.sample_recall_90_cutoff,
        first.sample_recall_at_recall_90_cutoff,
    ) == (0.5, 0.40, 1.0)

    short = settle(2, count=2)
    assert short.sample_status is SampleStatus.MEASURED
    assert (short.pairs_drawn, short.pairs_returned, short.runners_reported) == (11, 2, 0)
    assert (short.sample_tp, short.sample_fp, short.sample_fn, short.sample_tn) == (1, 1, 0, 0)
    assert short.cutoff_brier_score == 0.5

    empty = settle(3, count=0)
    assert empty.sample_status is SampleStatus.MEASURED
    assert (empty.pairs_drawn, empty.pairs_returned, empty.runners_reported) == (11, 0, 0)
    assert (empty.sample_tp, empty.sample_fp, empty.sample_fn, empty.sample_tn) == (0, 0, 0, 0)
    assert empty.sample_precision is empty.sample_recall is empty.cutoff_brier_score is None
    assert empty.upper_cutoff_sample_size == 0
    assert empty.upper_cutoff_false_match_share is empty.upper_cutoff_brier_score is None
    assert empty.slice_outcomes is not None
    empty_slices = read_diagnostic_text(
        empty.slice_outcomes, column="slice_outcomes", model=SliceOutcomes
    )
    assert [(one.low, one.drawn, one.returned) for one in empty_slices.slices] == [
        (one.low, one.drawn, 0) for one in slices.slices
    ]
    # An empty attempt did not write pair rows: the fit still reads the existing ledger window.
    assert len(load_pair_verdicts(state, [DATE])) == 2
    assert empty.upper_usable_pairs_used == short.upper_usable_pairs_used == 2
