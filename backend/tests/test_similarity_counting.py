"""What does the record hold after a day is counted into it, and what is refused?

The arithmetic, and the collecting job that applies it: what it files beside
the record through the ledger door is part of what a counted day leaves behind.

Every record and every row here is built in the test that uses it. Nothing walks
the committed day tree: the arithmetic is about one record and a handful of rows,
and a fixture that grows with the archive would make these slower every week
(CLAUDE.md section 13).
"""

from __future__ import annotations

import csv
import dataclasses
import io
import json
import logging
from collections.abc import Iterator
from hashlib import sha256
from pathlib import Path
from typing import Final

import pytest
from support.ledger import SEED_COMMIT
from support.paths import CONFIG_DIR, read_text

from idhazh import atomic_write, config, ledger
from idhazh.content_similarity_judge import tenant
from idhazh.content_similarity_judge.tenant import JUDGE_ID, VERDICTS_DIRNAME
from idhazh.contracts.base import ServerJob, derive_text_digest, derive_url_key
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.council_events import CouncilExit
from idhazh.contracts.council_invocation import (
    ArtifactFile,
    PreparationReceipt,
    ScheduleRequest,
    SelectedJudge,
    Selection,
    ShardReport,
)
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.contracts.knobs.council import JudgeLifecycleStatus
from idhazh.contracts.knobs.placement import SimilarityThresholdConfig
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import LedgersConfig
from idhazh.contracts.story_similarity_distribution import (
    CALIBRATION_POLICY_VERSION,
    StorySimilarityDistribution,
)
from idhazh.contracts.story_similarity_pair import (
    JUDGE_POLICY_VERSION,
    SameStoryVerdict,
    StorySimilarityPair,
)
from idhazh.council import metrics_sink, session
from idhazh.similarity import counting, fit
from idhazh.similarity.stamps import JudgeStamp, ScorerStamp, judge_inputs, scorer_inputs
from idhazh.stages import count_verdicts

DATE: Final = "2026-09-18"

#: The night before the one these tests count, used where a test needs two nights
#: it can tell apart by name.
AN_EARLIER_DATE: Final = "2026-09-17"

#: The name the council night these tests settle files its rows under.
A_COUNCIL_RUN: Final = f"{DATE}-9"

#: A twelve-slot band, wide enough to tell an edge from a middle and small enough
#: that a failing assertion names a slot a reader can count to.
KNOBS: Final = SimilarityThresholdConfig(band_low=0.50, band_high=0.62, bin_width=0.01)


def a_scorer() -> ScorerStamp:
    return ScorerStamp(scorer_model="all-minilm-l6-v2-quantized", cosine_weight=1.0)


def a_judge() -> JudgeStamp:
    return JudgeStamp(
        judge_model="qwen3-5-9b-q4-k-m",
        prompt_digest="a" * 64,
        grammar_digest="b" * 64,
        judge_temperature=0.0,
        thinks=False,
    )


def a_record() -> StorySimilarityDistribution:
    return counting.empty_record(KNOBS, scorer=a_scorer(), judge=a_judge())


def a_pair(index: int) -> tuple[str, str, str]:
    """Two addresses in stored order and the identity they digest to.

    A row names its pair by a digest of its own two address keys and the contract
    recomputes it, so a test that needs two pairs it can tell apart moves the
    addresses rather than the digest.
    """
    low, high = sorted(
        (
            derive_url_key(f"https://left.example/{index}"),
            derive_url_key(f"https://right.example/{index}"),
        )
    )
    return low, high, derive_text_digest(low + high)


def a_row(
    *,
    score: float,
    headline: bool = False,
    verdict: SameStoryVerdict = SameStoryVerdict.NO,
    usable: bool = True,
    pair: int | None = None,
    run_id: str | None = None,
    judged_by_run_id: str | None = None,
    judge: JudgeStamp | None = None,
    date: str = DATE,
) -> StorySimilarityPair:
    """One concrete pair under the named instrument, without a recorded payload."""
    scorer, stamped = a_scorer(), judge if judge is not None else a_judge()
    left, right, key = a_pair(0 if pair is None else pair)
    return StorySimilarityPair.model_validate(
        {
            "version": StorySimilarityPair.schema_version(),
            "date": date,
            "run_id": run_id if run_id is not None else f"{date}-1",
            "judged_by_run_id": judged_by_run_id,
            "composite_score": score,
            "cosine": score,
            "headline": headline,
            "work_part_index": 0,
            "verdict": verdict.value,
            "verdict_swapped": verdict.value if usable else (
                "YES" if verdict is not SameStoryVerdict.YES else "NO"
            ),
            "usable": usable,
            "left_url_key": left,
            "right_url_key": right,
            "pair_key": key,
            "scorer_model": scorer.scorer_model,
            "cosine_weight": scorer.cosine_weight,
            "judge_model": stamped.judge_model,
            "prompt_digest": stamped.prompt_digest,
            "grammar_digest": stamped.grammar_digest,
            "judge_temperature": stamped.judge_temperature,
            "thinking_spans": int(stamped.thinks),
            "grammar_applied": True,
            "judge_policy_version": stamped.judge_policy_version,
        }
    )


def test_a_score_lands_in_the_slot_whose_lower_edge_it_clears() -> None:
    """A pair scoring a slot's lower edge is in that slot, not the one below."""
    record = a_record()

    assert counting.slot_index(0.50, record=record) == 0
    assert counting.slot_index(0.5099, record=record) == 0
    assert counting.slot_index(0.51, record=record) == 1


def test_a_score_at_the_top_of_the_band_lands_in_the_last_slot() -> None:
    """`band_high` has no next slot to fall into, so it closes the last one."""
    record = a_record()

    assert counting.slot_index(0.62, record=record) == len(record.slots) - 1


def test_a_score_outside_the_band_lands_nowhere() -> None:
    """Below the band nothing was ever judged, so the record can say nothing."""
    record = a_record()

    assert counting.slot_index(0.499, record=record) is None
    assert counting.slot_index(0.621, record=record) is None


def test_an_exact_slot_edge_on_the_shipped_band_is_that_slot() -> None:
    """`(0.950 - 0.88) / 0.001` is 69.99999999999995, and an untoleranced walk files 69.

    Driven on the band the pipeline actually ships rather than this module's
    twelve-slot one, because the defect only appears at edges where the division
    lands a hair short - and the shipped band has 120 of them. The fit reads the
    merge line off a slot edge, so filing one slot low is a whole bin of error on
    the one number this feature exists to set.
    """
    record = counting.empty_record(SimilarityThresholdConfig(), scorer=a_scorer(), judge=a_judge())

    for score in (0.900, 0.930, 0.950, 0.970, 0.990):
        index = counting.slot_index(score, record=record)
        assert index is not None
        assert record.slots[index].bin_low == pytest.approx(score), (
            f"{score} is a slot's own lower edge and belongs in that slot"
        )


def test_an_unusable_row_is_counted_nowhere() -> None:
    """A verdict nobody can vouch for still moves the line if it is counted."""
    record = a_record()

    counted = counting.count_day(record, [a_row(score=0.55, usable=False)], date=DATE)

    assert sum(slot.different_count for slot in counted.slots) == 0
    assert counted.counted_dates == (DATE,), "the day is still counted as read"


def test_an_unclear_verdict_is_counted_only_as_unclear() -> None:
    """Counted and never fitted on, so a rising share of them is visible."""
    record = a_record()

    counted = counting.count_day(
        record, [a_row(score=0.55, verdict=SameStoryVerdict.UNCLEAR)], date=DATE
    )

    slot = counted.slots[counting.slot_index(0.55, record=record) or 0]
    assert (slot.same_count, slot.different_count, slot.unclear_count) == (0, 0, 1)


@pytest.mark.parametrize("verdict", list(SameStoryVerdict))
@pytest.mark.parametrize("audit_pairs", [1, 4])
def test_headline_audits_do_not_change_calibration_or_daily_contributions(
    verdict: SameStoryVerdict, audit_pairs: int
) -> None:
    """Counting headline overrides would change a line that cannot affect them."""
    knobs = SimilarityThresholdConfig()
    previous = counting.count_day(
        counting.empty_record(knobs, scorer=a_scorer(), judge=a_judge()),
        [a_row(score=0.93, pair=1, date=AN_EARLIER_DATE)],
        date=AN_EARLIER_DATE,
    )
    today = [a_row(score=0.96, pair=2)]
    audits = [
        a_row(score=1.0, headline=True, verdict=verdict, pair=10 + index)
        for index in range(audit_pairs)
    ]

    plain = counting.count_day(previous, today, date=DATE)
    audited = counting.count_day(previous, [*today, *audits], date=DATE)
    contribution = counting.day_counts(today, record=plain)

    assert audited == plain
    assert counting.day_counts([*today, *audits], record=audited) == contribution
    assert fit.fit_line(audited, discard_share=knobs.discard_share) == pytest.approx(0.961)
    assert fit.daily_shift(
        audited, contribution, discard_share=knobs.discard_share
    ) == pytest.approx(0.03)


def test_a_newest_headline_audit_does_not_restore_an_older_adjustable_reading() -> None:
    """Pair recency must be settled before the headline branch is excluded."""
    record = counting.empty_record(
        SimilarityThresholdConfig(), scorer=a_scorer(), judge=a_judge()
    )
    rows = [
        a_row(score=0.95, judged_by_run_id=f"{DATE}-1"),
        a_row(score=1.0, headline=True, judged_by_run_id=f"{DATE}-2"),
    ]

    assert counting.day_counts(rows, record=record) == {}


def test_counting_a_date_the_record_already_holds_raises() -> None:
    """A re-run of the count is free rather than a day counted twice."""
    record = counting.count_day(a_record(), [a_row(score=0.55)], date=DATE)

    with pytest.raises(ValueError, match=DATE):
        counting.count_day(record, [a_row(score=0.55)], date=DATE)


def test_a_changed_scorer_stamp_archives_and_starts_empty() -> None:
    """A different weight puts the same pair in a different slot."""
    record = a_record()
    moved = ScorerStamp(scorer_model="all-minilm-l6-v2-quantized", cosine_weight=0.8)

    assert counting.inputs_changed(record, knobs=KNOBS, scorer=a_scorer(), judge=a_judge()) is None
    assert counting.inputs_changed(record, knobs=KNOBS, scorer=moved, judge=a_judge()) == (
        "1.0",
        "0.8",
    )
    assert counting.archive_stem(record) != counting.archive_stem(
        counting.empty_record(KNOBS, scorer=moved, judge=a_judge())
    )


@pytest.mark.parametrize("field", ["judge_temperature", "thinks"])
def test_every_value_the_record_stamps_is_a_value_the_detector_sees(field: str) -> None:
    """A stamp column the detector cannot see is a stamp that lies.

    The record would archive under a name nobody can explain: the counts move to
    a new file and the operator reading the held line is told nothing moved.
    """
    record = a_record()
    after = {
        "judge_temperature": dataclasses.replace(a_judge(), judge_temperature=0.2),
        "thinks": dataclasses.replace(a_judge(), thinks=True),
    }[field]

    assert counting.inputs_changed(record, knobs=KNOBS, scorer=a_scorer(), judge=after) is not None
    assert counting.archive_stem(record) != counting.archive_stem(
        counting.empty_record(KNOBS, scorer=a_scorer(), judge=after)
    )


def test_a_record_written_before_the_decode_columns_resets_once() -> None:
    """The read-side migration, and what it costs.

    A record written under the older shape carries the two decode values null,
    loads here, and stamps to a value it never stamped to - so the first day
    after the widening archives it and counts on from zero. That is the reset,
    it is by construction rather than by an input moving, and it happens once.
    """
    record = a_record()
    older = record.model_copy(update={"judge_temperature": None, "judge_thinks": None})

    assert older.record_stamp() != record.record_stamp()
    assert counting.inputs_changed(older, knobs=KNOBS, scorer=a_scorer(), judge=a_judge()) == (
        "None",
        "0.0",
    )
    assert counting.inputs_changed(record, knobs=KNOBS, scorer=a_scorer(), judge=a_judge()) is None


def test_one_pair_judged_twice_is_counted_once_at_the_newer_run() -> None:
    """The newer run read the day as it stands; counting both doubles one pair."""
    record = a_record()
    rows = [
        a_row(score=0.55, verdict=SameStoryVerdict.YES, run_id=f"{DATE}-1"),
        a_row(score=0.55, verdict=SameStoryVerdict.NO, run_id=f"{DATE}-2"),
    ]

    kept = counting.one_row_a_pair(rows)

    assert [row.run_id for row in kept] == [f"{DATE}-2"]
    counted = counting.count_day(record, rows, date=DATE)
    slot = counted.slots[counting.slot_index(0.55, record=record) or 0]
    assert (slot.same_count, slot.different_count) == (0, 1)


def test_a_stamped_re_judge_beats_the_unstamped_rows_it_replaces() -> None:
    """Three rows, because two of them are what the old ordering decided between.

    `judged_by_run_id` is empty on every row written before the column existed,
    and an empty stamp sorts lowest - so a re-judge wins whichever digest run it
    is filed under. The two unstamped rows are still ordered by `run_id`, which
    is what this did before the column existed: drop that half of the pair and
    they would compare equal and the first one seen would win.
    """
    rows = [
        a_row(score=0.55, verdict=SameStoryVerdict.YES, run_id=f"{DATE}-2"),
        a_row(
            score=0.55,
            verdict=SameStoryVerdict.NO,
            run_id=f"{DATE}-1",
            judged_by_run_id=f"{DATE}-7",
        ),
        a_row(score=0.55, verdict=SameStoryVerdict.UNCLEAR, run_id=f"{DATE}-1"),
    ]

    kept = counting.one_row_a_pair(rows)

    assert [row.verdict for row in kept] == [SameStoryVerdict.NO]
    assert [row.run_id for row in counting.one_row_a_pair(rows[::2])] == [f"{DATE}-2"]


def a_metrics_row(*, shard: int, dealt: int = 2, date: str = DATE) -> ContentSimilarityJudgeMetrics:
    """One unit's instrument reading, with a funnel that closes."""
    return ContentSimilarityJudgeMetrics.model_validate(
        {
            "date": date,
            "run_id": f"{date}-9",
            "work_part_index": shard,
            "pairs_dealt": dealt,
            "pairs_read": dealt,
            "pairs_agreed": dealt,
            "pairs_unreadable": 0,
            "pairs_refused": 0,
            "pairs_abandoned": 0,
            "disagreement_rate": 0.0,
            "unclear_rate": 0.0,
            "first_token_margin_median": 0.5,
            "decode_seconds_total": 3.5 + shard,
            "decode_seconds_max": 2.0,
        }
    )


def a_verdict_file(rows: list[StorySimilarityPair]) -> str:
    """What a unit leaves behind, written through the contract's own columns."""
    out = io.StringIO()
    writer = csv.DictWriter(out, fieldnames=StorySimilarityPair.csv_columns(), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row.csv_row())
    return out.getvalue()


def a_night(
    root: Path, *, units: int, date: str = DATE, verdicts_a_unit: int = 0
) -> tuple[Path, Path, list[ContentSimilarityJudgeMetrics]]:
    """A night's units as they leave a runner: a verdict file and a shipped row each.

    The verdict files carry a header and `verdicts_a_unit` rows under it. Zero is
    the default because most of what these ask is what the collecting job does
    with what the units shipped rather than how a verdict is counted; a test that
    needs a day file with something in it says how much.
    """
    shipped = root / "shipped"
    verdicts = root / VERDICTS_DIRNAME
    written = [a_metrics_row(shard=unit, date=date) for unit in range(units)]
    for unit, row in enumerate(written):
        metrics_sink.ship_judge_metrics(row, judge_id=JUDGE_ID, name=str(unit), out_dir=shipped)
        atomic_write.write_atomic(
            verdicts
            / session.unit_file(date, slot=VERDICTS_DIRNAME, judge_id=JUDGE_ID, shard=unit).name,
            a_verdict_file(
                [
                    a_row(
                        score=0.55, pair=unit * 16 + index, date=date,
                        judge=judge_inputs(config.load(CONFIG_DIR)),
                    )
                    for index in range(verdicts_a_unit)
                ]
            ),
        )
    return shipped, verdicts, written


def a_saver(run_id: str = A_COUNCIL_RUN) -> WriterIdentity:
    """The writer the council hands a tenant: the job that saves the night's results."""
    return WriterIdentity(
        run_id=run_id,
        attempt=1,
        job=ServerJob.SAVE_COUNCIL_RESULTS,
        shard=0,
        producer="council.session",
        git_sha=SEED_COMMIT,
    )


def test_the_row_the_collecting_job_lands_is_the_row_the_unit_shipped(tmp_path: Path) -> None:
    """Cell for cell, and the whole row is compared rather than a column of it.

    The units ship through the contract's own columns and the door files through
    the contract's own fields, so a cell one side knows about and the other does
    not shows up here as a row that is no longer the row the unit wrote - which
    is the one failure a spot check of two cells would walk straight past.
    """
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"
    shipped, verdicts, written = a_night(tmp_path, units=settings.council.shards)

    report = count_verdicts.stage_count_verdicts(
        DATE,
        run_id=A_COUNCIL_RUN,
        judge_id=JUDGE_ID,
        shipped_root=shipped,
        verdicts_dir=verdicts,
        settings=settings,
        identity=a_saver(),
        expected_shards=settings.council.shards,
        reports_complete=True,
        state_dir=state,
    )

    which = LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS
    landed = ledger.load_days(state, which, [DATE], model=ContentSimilarityJudgeMetrics)
    (filed,) = ledger.list_raw_files(state, which, days=[DATE])

    assert report.metrics_appended == len(written)
    assert report.counted is True, "every unit reported, so the day is counted"
    assert sorted(landed, key=lambda row: row.work_part_index) == written
    assert filed.envelope.identity.producer == count_verdicts.PRODUCER


def test_the_readings_land_on_a_night_the_record_refused_to_count(tmp_path: Path) -> None:
    """A unit that ran and a day that cannot be counted are two different facts.

    Holding the readings back until the record accepts the day would delete the
    evidence of the first to record the second - and the night a unit dies is
    exactly the night an operator opens this ledger to find out why.
    """
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"
    shipped, verdicts, written = a_night(tmp_path, units=1)

    report = count_verdicts.stage_count_verdicts(
        DATE,
        run_id=A_COUNCIL_RUN,
        judge_id=JUDGE_ID,
        shipped_root=shipped,
        verdicts_dir=verdicts,
        settings=settings,
        identity=a_saver(),
        expected_shards=settings.council.shards,
        reports_complete=True,
        state_dir=state,
    )

    assert settings.council.shards > len(written), "a night short of a unit"
    assert (report.counted, report.held_reason) == (False, "shards_missing")
    assert report.metrics_appended == 1
    assert ledger.list_raw_files(state, LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS, days=[DATE])


def test_a_night_whose_units_shipped_nothing_appends_nothing(tmp_path: Path) -> None:
    """An empty upload is a night with no tenant, never a run to fail."""
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"

    report = count_verdicts.stage_count_verdicts(
        DATE,
        run_id=A_COUNCIL_RUN,
        judge_id=JUDGE_ID,
        shipped_root=tmp_path / "nothing-was-uploaded",
        verdicts_dir=tmp_path / "nothing-was-judged",
        settings=settings,
        identity=a_saver(),
        expected_shards=settings.council.shards,
        reports_complete=False,
        state_dir=state,
    )

    assert report.metrics_appended == 0
    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS).exists()
    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS).exists()


@pytest.mark.parametrize("reports_complete", [False, True])
def test_counting_uses_admitted_width_and_requires_complete_reports(
    tmp_path: Path, reports_complete: bool
) -> None:
    """Files alone cannot turn failed or refused units into a completed date."""
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"
    shipped, verdicts, _ = a_night(tmp_path, units=1, verdicts_a_unit=1)
    report = count_verdicts.stage_count_verdicts(
        DATE,
        run_id=A_COUNCIL_RUN,
        judge_id=JUDGE_ID,
        shipped_root=shipped,
        verdicts_dir=verdicts,
        settings=settings,
        identity=a_saver(),
        expected_shards=1,
        reports_complete=reports_complete,
        state_dir=state,
    )

    assert report.shards_expected == report.shards_present == 1
    assert report.counted is reports_complete
    assert report.held_reason == (None if reports_complete else "reports_incomplete")
    assert report.rows_appended == report.metrics_appended == 1
    assert len(ledger.load_story_similarity_pairs(state, DATE)) == 1
    if not reports_complete:
        assert not ledger.path(
            state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION
        ).exists()


def test_zero_work_counts_without_creating_shard_evidence(tmp_path: Path) -> None:
    """A no-work receipt completes its date without fabricated verdicts or readings."""
    state = tmp_path / "state"
    shipped, verdicts = tmp_path / "shipped", tmp_path / "verdicts"
    report = count_verdicts.stage_count_verdicts(
        DATE,
        run_id=A_COUNCIL_RUN,
        judge_id=JUDGE_ID,
        shipped_root=shipped,
        verdicts_dir=verdicts,
        settings=config.load(CONFIG_DIR),
        identity=a_saver(),
        expected_shards=0,
        reports_complete=True,
        state_dir=state,
    )

    assert report.counted
    assert report.shards_expected == report.shards_present == 0
    assert report.rows_appended == report.metrics_appended == 0
    assert not shipped.exists()
    assert not verdicts.exists()
    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS).exists()
    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS).exists()
    record = StorySimilarityDistribution.from_json(
        ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION).read_text(
            encoding="utf-8"
        )
    )
    assert record.judged_dates == (DATE,)


@pytest.mark.parametrize(
    ("max_dates", "max_older_dates", "expected"),
    [
        (1, 1, (DATE,)),
        (3, 0, (DATE,)),
        (2, 1, (DATE, "2026-09-16")),
        (3, 2, (DATE, "2026-09-16", "2026-09-15")),
    ],
)
def test_schedule_chooses_anchor_then_newest_outstanding_within_budgets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    max_dates: int,
    max_older_dates: int,
    expected: tuple[str, ...],
) -> None:
    """The judge, not its host, selects actual dates from its own date memory."""
    settings = config.load(CONFIG_DIR)
    counted_by(
        AN_EARLIER_DATE,
        root=tmp_path / "finished",
        state=tmp_path / "state",
        settings=settings,
        units=settings.council.shards,
    )
    monkeypatch.setattr(config, "REPO_ROOT", tmp_path)
    request = ScheduleRequest(
        anchor_date=DATE,
        window=("2026-09-15", AN_EARLIER_DATE, DATE, "2026-09-16"),
        max_dates=max_dates,
        max_older_dates=max_older_dates,
        shards=1,
        shard_seconds=1.0,
    )

    assert tenant.TENANT.schedule(request=request).dates == expected


#: The commit the save job's command line names, and the attempt the platform
#: says it is on. Both have to reach every file the night files.
A_COMMIT: Final = "0735031c2a9e4b8f1d6c3a5e7b9d0f2a4c6e8b1d"
AN_ATTEMPT: Final = 2


@pytest.fixture
def admitted_invocation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "var" / "council")
    selection = Selection(
        version=Selection.schema_version(),
        run_id=A_COUNCIL_RUN,
        attempt=AN_ATTEMPT,
        git_sha=A_COMMIT,
        mode="scheduled",
        anchor_date=DATE,
        window=(DATE, AN_EARLIER_DATE),
        judges=(
            SelectedJudge(
                tenant=JUDGE_ID,
                status=JudgeLifecycleStatus.ACTIVE,
                dates=(DATE, AN_EARLIER_DATE),
                shards=config.load_council(CONFIG_DIR).shards,
            ),
        ),
    )
    with session._route(selection, JUDGE_ID):
        yield


@pytest.mark.usefixtures("admitted_invocation")
@pytest.mark.parametrize(
    ("report_state", "outcome", "code", "counted"),
    [
        ("reported", ShardOutcome.COMPLETED, CouncilExit.OK, True),
        ("reported", ShardOutcome.FAILED, CouncilExit.FAILED, False),
        ("reported", ShardOutcome.STOPPED_ON_DEADLINE, CouncilExit.FAILED, False),
        ("reported", ShardOutcome.COMPLETED, CouncilExit.REFUSED, False),
        ("missing", None, None, False),
        ("refused", None, CouncilExit.REFUSED, False),
        ("invalid", None, None, False),
        ("not_dispatched", None, None, False),
        (None, None, None, False),
    ],
)
def test_adapter_preserves_arrived_evidence_but_holds_unsuccessful_reports(
    tmp_path: Path,
    report_state: str | None,
    outcome: ShardOutcome | None,
    code: CouncilExit | None,
    counted: bool,
) -> None:
    """Only complete successful reports may add a date to count memory."""
    state = tmp_path / "state"
    draw = tenant._draw_path(DATE)
    document = a_verdict_file([]).encode("utf-8")
    atomic_write.write_atomic(draw, document.decode("utf-8"))
    prepared = PreparationReceipt(
        version=PreparationReceipt.schema_version(),
        run_id=A_COUNCIL_RUN,
        attempt=AN_ATTEMPT,
        git_sha=A_COMMIT,
        judge_id=JUDGE_ID,
        date=DATE,
        state="ready",
        shards=1,
        files=(
            ArtifactFile(
                path=session.artifact_path(draw),
                size_bytes=len(document),
                sha256=sha256(document).hexdigest(),
            ),
        ),
    )
    atomic_write.write_atomic(
        tenant._verdict_path(DATE, shard=0), a_verdict_file([a_row(score=0.55)])
    )
    metrics_sink.ship_judge_metrics(
        a_metrics_row(shard=0),
        judge_id=JUDGE_ID,
        name="0",
        out_dir=tenant._shipping_dir(DATE),
    )
    reports = (
        ()
        if report_state is None
        else (
            ShardReport.model_validate(
                {
                    "shard": 0,
                    "shards": 1,
                    "report_state": report_state,
                    "outcome": outcome,
                    "code": code,
                }
            ),
        )
    )

    tenant.TENANT.settle(
        date=DATE,
        run_id=A_COUNCIL_RUN,
        state_dir=state,
        identity=a_saver(),
        prepared=prepared,
        reports=reports,
    )

    assert len(ledger.load_story_similarity_pairs(state, DATE)) == 1
    assert (
        len(
            ledger.load_days(
                state,
                LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS,
                [DATE],
                model=ContentSimilarityJudgeMetrics,
            )
        )
        == 1
    )
    record_path = ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION)
    if counted:
        assert StorySimilarityDistribution.from_json(
            record_path.read_text(encoding="utf-8")
        ).judged_dates == (DATE,)
    else:
        assert not record_path.exists()


@pytest.mark.usefixtures("admitted_invocation")
def test_adapter_settles_no_work_without_synthetic_shard_outputs(tmp_path: Path) -> None:
    prepared = PreparationReceipt(
        version=PreparationReceipt.schema_version(),
        run_id=A_COUNCIL_RUN,
        attempt=AN_ATTEMPT,
        git_sha=A_COMMIT,
        judge_id=JUDGE_ID,
        date=DATE,
        state="no_work",
        shards=0,
        files=(),
    )
    state = tmp_path / "state"

    tenant.TENANT.settle(
        date=DATE,
        run_id=A_COUNCIL_RUN,
        state_dir=state,
        identity=a_saver(),
        prepared=prepared,
        reports=(),
    )

    assert not tenant._verdicts_dir(DATE).exists()
    assert not tenant._shipping_dir(DATE).exists()
    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS).exists()
    assert not ledger.raw_root(state, LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS).exists()
    record = StorySimilarityDistribution.from_json(
        ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION).read_text(
            encoding="utf-8"
        )
    )
    assert record.judged_dates == (DATE,)


@pytest.mark.usefixtures("admitted_invocation")
def test_a_settled_night_files_each_judged_date_through_the_door_and_the_fit_reads_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The adapter files each admitted date under the supplied writer identity.

    Two judged dates, each settled through the adapter over every unit's
    verdicts and readings. Each date leaves one
    raw file of judged pairs and one of readings under the judge's own folder of
    the door's raw root, each filed under the council's writer identity with the
    counting stage as its producer, and nothing under the folders the two
    ledgers used to fill as CSV. Each pair and each reading keeps the part that
    judged it. The fit then reads the day's pairs back through the door: its
    row counts every pair the night filed for that day.
    """
    from test_similarity_fit import a_published_day

    from idhazh.stages import common

    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "var" / "council")
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "digest")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", str(AN_ATTEMPT))
    a_published_day(common.PUBLIC_ROOT, date=DATE)
    state = tmp_path / "state"
    units = config.load_council(CONFIG_DIR).shards
    nights = (AN_EARLIER_DATE, DATE)
    for date in nights:
        for unit in range(units):
            reading = ContentSimilarityJudgeMetrics.model_validate(
                a_metrics_row(shard=unit, date=date).model_dump() | {"run_id": A_COUNCIL_RUN}
            )
            metrics_sink.ship_judge_metrics(
                reading,
                judge_id=JUDGE_ID,
                name=str(unit),
                out_dir=session.scratch_root(date) / session.METRICS_DIRNAME,
            )
            judged = StorySimilarityPair.model_validate(
                a_row(
                    score=0.55, pair=unit, date=date, run_id=A_COUNCIL_RUN,
                    judge=judge_inputs(config.load(CONFIG_DIR)),
                ).model_dump()
                | {"work_part_index": unit}
            )
            atomic_write.write_atomic(
                session.unit_file(date, slot=VERDICTS_DIRNAME, judge_id=JUDGE_ID, shard=unit),
                a_verdict_file([judged]),
            )
        draw_path = tenant._draw_path(date)
        document = a_verdict_file([]).encode("utf-8")
        atomic_write.write_atomic(draw_path, document.decode("utf-8"))
        prepared = PreparationReceipt(
            version=PreparationReceipt.schema_version(),
            run_id=A_COUNCIL_RUN,
            attempt=AN_ATTEMPT,
            git_sha=A_COMMIT,
            judge_id=JUDGE_ID,
            date=date,
            state="ready",
            shards=units,
            files=(
                ArtifactFile(
                    path=session.artifact_path(draw_path),
                    size_bytes=len(document),
                    sha256=sha256(document).hexdigest(),
                ),
            ),
        )
        reports = tuple(
            ShardReport(
                shard=unit,
                shards=units,
                report_state="reported",
                outcome=ShardOutcome.COMPLETED,
                code=CouncilExit.OK,
            )
            for unit in range(units)
        )
        identity = a_saver().model_copy(
            update={
                "attempt": AN_ATTEMPT,
                "git_sha": A_COMMIT,
            }
        )
        assert (
            tenant.TENANT.settle(
                date=date,
                run_id=A_COUNCIL_RUN,
                state_dir=state,
                identity=identity,
                prepared=prepared,
                reports=reports,
            ).outcome
            is ShardOutcome.COMPLETED
        )

    writer = WriterIdentity(
        run_id=A_COUNCIL_RUN,
        attempt=AN_ATTEMPT,
        job=ServerJob.SAVE_COUNCIL_RESULTS,
        shard=0,
        producer="stages.count_verdicts",
        git_sha=A_COMMIT,
    )
    scored = LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS
    metrics = LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS
    for date in nights:
        for which in (scored, metrics):
            (filed,) = ledger.list_raw_files(state, which, days=[date])
            assert filed.envelope.identity == writer, which
            assert filed.path.parent == ledger.raw_root(state, which).joinpath(*date.split("-"))
        pairs = ledger.load_days(state, scored, [date], model=StorySimilarityPair)
        readings = ledger.load_days(state, metrics, [date], model=ContentSimilarityJudgeMetrics)
        assert sorted((row.work_part_index, row.pair_key) for row in pairs) == [
            (unit, a_pair(unit)[2]) for unit in range(units)
        ]
        assert sorted(row.work_part_index for row in readings) == list(range(units))
    assert not (state / JUDGE_ID / "scored-pairs").exists()
    assert not (state / JUDGE_ID / "metrics").exists()

    (fitted,) = ledger.load_fitted_thresholds(state, today=DATE, within_days=0)
    assert (fitted.date, fitted.pairs_in_band) == (DATE, units), (
        "the fit read the day's pairs back through the door"
    )


def a_ruler_moved(settings: config.Settings) -> config.Settings:
    """The committed settings with the scorer's two weights swapped over.

    A real instrument move: the same pair scores differently, so the counts taken
    under the old weights answer a different question and the record is archived.
    """
    app = settings.app.model_copy(deep=True)
    app.assemble.same_story.cosine_weight = 0.8
    return dataclasses.replace(settings, app=app)


def counted_by(
    date: str, *, root: Path, state: Path, settings: config.Settings, units: int
) -> count_verdicts.CountReport:
    """Run one night of `units` units through the collecting job.

    Every unit ships a reading and leaves one verdict behind, so a night short of
    a unit still puts rows in the day file - which is the shape the dominant
    failure produces and the one an outstanding-night answer has to see through.
    """
    shipped, verdicts, _ = a_night(root, units=units, date=date, verdicts_a_unit=1)
    return count_verdicts.stage_count_verdicts(
        date,
        run_id=f"{date}-9",
        judge_id=JUDGE_ID,
        shipped_root=shipped,
        verdicts_dir=verdicts,
        settings=settings,
        identity=a_saver(f"{date}-9"),
        expected_shards=settings.council.shards,
        reports_complete=units == settings.council.shards,
        state_dir=state,
    )


def test_the_night_that_lost_a_unit_is_the_night_this_judge_asks_for_again(
    tmp_path: Path,
) -> None:
    """The council asks what this judge is behind on, and this is the answer.

    Two nights, and the difference between them is the one the answer turns on.
    One had every unit report and was counted. The other lost a unit, so its
    rows landed and the date did not: counting three units of four cannot be
    repaired later, because the record counts a date once. That date is what a
    repair job is for, and the counted one is not - naming it would spend a
    runner on a night that can never be counted twice.

    Driven against a ledger this test built, never the committed one, so it costs
    the same when the archive is a year deep (CLAUDE.md section 13).
    """
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"
    shards = settings.council.shards

    whole = counted_by(DATE, root=tmp_path / "whole", state=state, settings=settings, units=shards)
    short = counted_by(
        AN_EARLIER_DATE,
        root=tmp_path / "short",
        state=state,
        settings=settings,
        units=shards - 1,
    )

    answered = tenant.TENANT.nights_outstanding(window=(AN_EARLIER_DATE, DATE), state_dir=state)

    assert (whole.counted, short.counted) == (True, False)
    assert len(ledger.load_story_similarity_pairs(state, AN_EARLIER_DATE)) == shards - 1, (
        "the units that did report still wrote their verdicts to the day file"
    )
    assert answered == (AN_EARLIER_DATE,)


def test_the_date_memory_survives_the_reset_that_empties_the_counts(tmp_path: Path) -> None:
    """A night already read is never asked for again, whatever happened to its counts.

    Moving a weight archives the record and starts the counts from zero, because
    they answer a different question under the new ruler. The nights already read
    come across, so the council is not handed a week of repair jobs the day
    somebody retunes the scorer - and every one of those jobs would be wasted,
    because the record still refuses to count a date twice.
    """
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"
    shards = settings.council.shards
    counted_by(DATE, root=tmp_path / "first", state=state, settings=settings, units=shards)

    after = counted_by(
        AN_EARLIER_DATE,
        root=tmp_path / "second",
        state=state,
        settings=a_ruler_moved(settings),
        units=shards,
    )
    record = StorySimilarityDistribution.from_json(
        read_text(ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION))
    )

    assert after.archived is not None, "the weights moved, so the counts were archived"
    assert record.counted_dates == (AN_EARLIER_DATE,), "the counts start again from this night"
    assert record.judged_dates == (AN_EARLIER_DATE, DATE), "and both nights are remembered"
    assert tenant.TENANT.nights_outstanding(window=(AN_EARLIER_DATE, DATE), state_dir=state) == ()


def test_a_paused_judge_family_takes_no_verdict_reading_archive_or_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Each write the collecting job makes into this judge's family asks first.

    One active night leaves a record under the old ruler. With the family paused,
    a night under a moved ruler would append verdicts and readings, archive the
    record and count the day - and each of the four is skipped with one warning
    naming its own ledger, while the job reports the day as not counted rather
    than failing.
    """
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"
    shards = settings.council.shards
    counted_by(DATE, root=tmp_path / "first", state=state, settings=settings, units=shards)
    record_path = ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION)
    before = record_path.read_bytes()
    registry = json.loads(read_text(CONFIG_DIR / ledger.paths.REGISTRY_FILENAME))
    for family in registry["families"]:
        if family["name"] == "content-similarity-judge":
            family["lifecycle_status"] = "paused"
    monkeypatch.setattr(ledger.paths, "_CONFIG", LedgersConfig.model_validate(registry))

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        after = counted_by(
            AN_EARLIER_DATE,
            root=tmp_path / "second",
            state=state,
            settings=a_ruler_moved(settings),
            units=shards,
        )
    skipped = sorted(
        record.getMessage().split(" ")[3]
        for record in caplog.records
        if "ledger write skipped" in record.getMessage()
    )

    assert (after.counted, after.held_reason, after.archived) == (
        False,
        "family_not_active",
        None,
    )
    assert record_path.read_bytes() == before
    assert not ledger.path(
        state, LedgerName.CONTENT_SIMILARITY_JUDGE_ARCHIVE,
        StorySimilarityDistribution.from_json(before.decode()).record_stamp(),
    ).exists()
    assert not ledger.raw_root(
        state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS
    ).joinpath(*AN_EARLIER_DATE.split("-")).exists()
    assert skipped == [
        "ledger=archive",
        "ledger=metrics",
        "ledger=score-distribution",
        "ledger=scored-pairs",
    ]


def test_a_judge_with_no_record_yet_names_no_night(tmp_path: Path) -> None:
    """Before the first day is counted there is no record, so there is nothing to be behind on.

    A tenant raises the council's floor for itself by naming no night from before
    it arrived, and a judge with no record has not arrived on any of them. The
    other answer - every night in the window - would have a judge that moved in
    today dispatch a week of repair jobs for nights it was never asked to read.
    An operator who wants one of them judged names the date, which replaces the
    plan outright.
    """
    answered = tenant.TENANT.nights_outstanding(
        window=(AN_EARLIER_DATE, DATE), state_dir=tmp_path / "nothing-was-counted-yet"
    )

    assert answered == ()


def test_policy_filtering_precedes_pair_recency() -> None:
    record = a_record()
    current = a_row(score=0.55, judged_by_run_id=f"{DATE}-1")
    historical = a_row(
        score=0.55, judged_by_run_id=f"{DATE}-9",
        judge=dataclasses.replace(a_judge(), judge_policy_version=None),
        verdict=SameStoryVerdict.YES,
    )

    counts = counting.day_counts([current, historical], record=record)

    assert sum(slot.different for slot in counts.values()) == 1
    assert sum(slot.same for slot in counts.values()) == 0
    assert record.record_stamp() != record.model_copy(
        update={"judge_policy_version": None}
    ).record_stamp()
    assert counting.inputs_changed(
        record.model_copy(update={"judge_policy_version": None}),
        knobs=KNOBS, scorer=a_scorer(), judge=a_judge(),
    ) == ("None", JUDGE_POLICY_VERSION)


def test_calibration_policy_changes_the_record_identity_without_moving_the_instrument() -> None:
    record = a_record()
    historical = record.model_copy(update={"calibration_policy_version": None})

    assert historical.record_stamp() != record.record_stamp()
    assert counting.inputs_changed(
        historical, knobs=KNOBS, scorer=a_scorer(), judge=a_judge()
    ) == ("None", CALIBRATION_POLICY_VERSION)
    assert counting.inputs_changed(
        record, knobs=KNOBS, scorer=a_scorer(), judge=a_judge()
    ) is None


@pytest.mark.parametrize("archive_available", [True, False])
@pytest.mark.parametrize(
    "changed_policies",
    [
        ("judge_policy_version",),
        ("calibration_policy_version",),
        ("judge_policy_version", "calibration_policy_version"),
    ],
)
def test_policy_reset_requires_an_archive_preserves_memory_and_happens_once(
    tmp_path: Path, archive_available: bool, changed_policies: tuple[str, ...]
) -> None:
    settings = config.load(CONFIG_DIR)
    state = tmp_path / "state"
    old = counting.empty_record(
        settings.app.assemble.same_story.judging_knobs(),
        scorer=scorer_inputs(settings),
        judge=judge_inputs(settings),
        judged_dates=("2026-09-15", DATE),
    ).model_copy(update={
        "counted_dates": (DATE,),
        **dict.fromkeys(changed_policies),
    })
    old = old.model_copy(update={"slots": (
        old.slots[0].model_copy(update={"different_count": 3}), *old.slots[1:],
    )})
    payload = old.model_dump(mode="json") | {"version": "2026-10-24"}
    for policy in changed_policies:
        del payload[policy]
    old_bytes = json.dumps(payload, indent=2).encode()
    record_path = ledger.path(state, LedgerName.CONTENT_SIMILARITY_JUDGE_SCORE_DISTRIBUTION)
    archive_path = ledger.path(
        state, LedgerName.CONTENT_SIMILARITY_JUDGE_ARCHIVE, old.record_stamp()
    )
    atomic_write.write_atomic_bytes(record_path, old_bytes)
    if not archive_available:
        archive_path.mkdir(parents=True)

    def count(date: str) -> count_verdicts.CountReport:
        return count_verdicts.stage_count_verdicts(
            date, run_id=f"{date}-9", judge_id=JUDGE_ID,
            shipped_root=tmp_path / "no-shipped-work", verdicts_dir=tmp_path / "no-verdicts",
            settings=settings, identity=a_saver(f"{date}-9"),
            expected_shards=0, reports_complete=True, state_dir=state,
        )

    report = count(AN_EARLIER_DATE)
    if not archive_available:
        assert not report.counted and report.archived is None
        assert report.held_reason == "inputs_changed"
        assert record_path.read_bytes() == old_bytes
        assert archive_path.is_dir()
        return

    assert report.counted and report.archived == old.record_stamp()
    assert archive_path.read_bytes() == old_bytes
    current = StorySimilarityDistribution.from_json(record_path.read_text(encoding="utf-8"))
    assert current.judge_policy_version == JUDGE_POLICY_VERSION
    assert current.calibration_policy_version == CALIBRATION_POLICY_VERSION
    assert current.counted_dates == (AN_EARLIER_DATE,)
    assert current.judged_dates == ("2026-09-15", AN_EARLIER_DATE, DATE)
    assert all(
        (slot.same_count, slot.different_count, slot.unclear_count) == (0, 0, 0)
        for slot in current.slots
    )
    again = count("2026-09-16")
    assert again.counted and again.archived is None and again.held_reason is None
    assert archive_path.read_bytes() == old_bytes
    assert not ledger.path(
        state, LedgerName.CONTENT_SIMILARITY_JUDGE_ARCHIVE, current.record_stamp()
    ).exists()
    assert StorySimilarityDistribution.from_json(
        record_path.read_text(encoding="utf-8")
    ).judged_dates == ("2026-09-15", "2026-09-16", AN_EARLIER_DATE, DATE)


def test_a_row_from_another_instrument_is_counted_nowhere() -> None:
    """The record says one model, one prompt and one sampler produced every count.

    A re-judge leaves the older row in the append-only day file, so a day read
    twice under two instruments holds both readings. Adding them together makes
    the record's own stamp a lie, and no later read can pull them apart again.
    """
    record = a_record()
    elsewhere = dataclasses.replace(a_judge(), judge_temperature=0.7)

    counted = counting.count_day(
        record,
        [
            a_row(score=0.55, pair=1),
            a_row(score=0.55, pair=2, judge=elsewhere),
        ],
        date=DATE,
    )

    slot = counted.slots[counting.slot_index(0.55, record=record) or 0]
    assert slot.different_count == 1, "one row was judged under the record's own instrument"


def test_a_stale_row_does_not_take_the_pair_from_the_fresh_one() -> None:
    """Why the stamp filter runs before the de-duplication rather than after it.

    Both rows are the same pair. The one from the old instrument was judged by
    the later run, so on recency it wins the pair - and filtering afterwards
    would then throw it away and count nothing, losing the reading that was
    standing behind it. Filtering first leaves the fresh row to win uncontested.
    """
    record = a_record()
    rows = [
        a_row(score=0.55, run_id=f"{DATE}-1", judged_by_run_id=f"{DATE}-1"),
        a_row(
            score=0.55,
            run_id=f"{DATE}-2",
            judged_by_run_id=f"{DATE}-9",
            judge=dataclasses.replace(a_judge(), judge_temperature=0.7),
        ),
    ]

    counted = counting.count_day(record, rows, date=DATE)

    slot = counted.slots[counting.slot_index(0.55, record=record) or 0]
    assert slot.different_count == 1, "the fresh row was counted, not discarded with the stale one"


def test_counting_a_day_writes_it_to_both_date_lists() -> None:
    """The two lists are kept in step here, because this is the verb that reads a night."""
    counted = counting.count_day(a_record(), [a_row(score=0.55)], date=DATE)

    assert (counted.counted_dates, counted.judged_dates) == ((DATE,), (DATE,))
