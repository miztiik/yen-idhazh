"""What chance had a pair of being taken and usable, and does the night file it with that chance?

The arithmetic over a slice's counts, and the collecting job that applies it: what it files
through the ledger door is what every later reader of the night works from.

Every row and every file here is built in the test that uses it. Nothing walks the committed
ledger (CLAUDE.md section 13).
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path
from typing import Final

import pytest
from support.judged_pairs import a_reading, a_saver, a_verdict_file
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
from idhazh.contracts.story_similarity_pair_verdict import (
    JUDGE_POLICY_VERSION,
    PairBucket,
    StorySimilarityPairVerdict,
)
from idhazh.council import metrics_sink, session
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
    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_PAIR_VERDICTS).exists()


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
    assert not ledger.raw_root(tmp_path / "state", LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS).exists()


@pytest.fixture
def admitted_invocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "var" / "council")
    selection = Selection(
        version=Selection.schema_version(),
        run_id=RUN,
        attempt=1,
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
        yield


@pytest.mark.usefixtures("admitted_invocation")
def test_the_tenant_files_a_night_that_lost_a_runner_whatever_the_reports_say(
    tmp_path: Path,
) -> None:
    """The venue's reports say nothing the files do not: the rows that exist are filed.

    One of the two units left a file and a shipped reading and the other left nothing, and
    no report arrived for either. The surviving unit's pairs are filed and the night
    reports itself settled.
    """
    state = tmp_path / "state"
    draw = tenant._draw_path(DATE)
    document = a_verdict_file([]).encode("utf-8")
    atomic_write.write_atomic(draw, document.decode("utf-8"))
    prepared = PreparationReceipt(
        version=PreparationReceipt.schema_version(),
        run_id=RUN,
        attempt=1,
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
    atomic_write.write_atomic(
        tenant._verdict_path(DATE, shard=0), a_verdict_file(a_hand_worked_night()[0])
    )
    metrics_sink.ship_judge_metrics(
        a_reading(shard=0, dealt=2, date=DATE, run_id=RUN),
        judge_id=JUDGE_ID,
        name="0",
        out_dir=tenant._shipping_dir(DATE),
    )

    settled = tenant.TENANT.settle(
        date=DATE,
        run_id=RUN,
        state_dir=state,
        identity=a_saver(RUN),
        prepared=prepared,
        reports=(),
    )

    assert settled.outcome is ShardOutcome.COMPLETED
    assert len(load_pair_verdicts(state, [DATE])) == 3
    (filed_row,) = load_threshold_history(state, [DATE])
    assert (filed_row.date, filed_row.run_id, filed_row.runners_reported) == (DATE, RUN, 1)
