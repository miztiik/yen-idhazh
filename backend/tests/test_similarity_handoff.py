"""Does what one job of a judging night wrote reach the job that has to read it?

The council carries one directory between its jobs and carries nothing else. A
path outside that directory is not slow and not wasteful - it is gone, thrown
away with the runner that wrote it, and every later job fails on a file nobody
uploaded.

Driven against isolated directories standing in for runners. Day payloads and
ledger files that a test needs are written to those directories.
"""

from __future__ import annotations

import shutil
from collections import Counter
from collections.abc import Sequence
from math import comb
from pathlib import Path
from typing import Final

import pytest
from test_content_similarity_judge_ledger_reads import (
    THRESHOLD_HISTORY,
    a_night,
    a_night_with_pool,
    file_through_the_door,
)
from test_same_story import block, item, unit

from idhazh import assemble, atomic_write, config
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge import tenant
from idhazh.content_similarity_judge.ledger_reads import load_threshold_history
from idhazh.contracts.council_invocation import (
    PreparationReceipt,
    SelectedJudge,
    Selection,
)
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.contracts.digest_day import DigestDay, DigestItem, DigestRunRef, DigestVerticalRef
from idhazh.contracts.knobs.council import JudgeLifecycleStatus
from idhazh.contracts.story_similarity_diagnostics import (
    ScoreDriftStatus,
    ScorePoolHistogram,
    diagnostic_text,
)
from idhazh.contracts.story_similarity_score_pool import ContentSimilarityScorePool
from idhazh.council import session, work_files
from idhazh.council.model_selection import bind_model
from idhazh.similarity.thresholds_in_force import lookback_days
from idhazh.stages import common, judge_item_pairs, pick_item_pairs

#: A night these tests ask the tenant about. Any date would do - none of them
#: reads a published day.
A_NIGHT: Final = "2026-09-20"

A_RUN: Final = "2026-09-21-35534060762"


def a_published_day(
    root: Path, *, date: str, stories: Sequence[tuple[DigestItem, float]] | None = None
) -> None:
    """One day on disk, with real quantized vectors at the specified angles."""
    if stories is None:
        stories = [
            (item("world-01", source="wire", outlet="The Wire"), 0.0),
            (item("world-02", source="paper", outlet="The Paper"), 12.0),
            (item("world-03", source="herald", outlet="The Herald"), 24.0),
        ]
    items = [story for story, _ in stories]
    day = DigestDay(
        version=DigestDay.schema_version(),
        date=date,
        generated_at=f"{date}T06:00:00Z",
        partial=False,
        items_planned=len(items),
        items_failed=0,
        runs=[DigestRunRef(n=1, at=f"{date}T06:00:00Z", items_added=len(items))],
        verticals=[
            DigestVerticalRef(id=name, display_name=name.title(), count=count)
            for name, count in sorted(Counter(one.vertical for one in items).items())
        ],
        items=items,
        embeddings=block({story.item_id: unit(angle) for story, angle in stories}),
    )
    atomic_write.write_atomic(assemble.day_dir(root, date) / "digest.json", day.to_json())


def _selection(*, shards: int | None = None, attempt: int = 1) -> Selection:
    council = config.load_council()
    return Selection(
        version=Selection.schema_version(),
        run_id=A_RUN,
        attempt=attempt,
        git_sha="a" * 40,
        mode="manual",
        anchor_date=A_NIGHT,
        window=(A_NIGHT,),
        judges=(
            SelectedJudge(
                tenant=tenant.JUDGE_ID,
                status=JudgeLifecycleStatus.ACTIVE,
                dates=(A_NIGHT,),
                shards=council.shards if shards is None else shards,
                model=bind_model(council, tenant.JUDGE_ID),
            ),
        ),
    )


def _one_runner(tmp_path: Path, name: str, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A bare checkout with the council's root inside it and an empty state root.

    Returned as the checkout rather than the root, so a path written anywhere
    else in the tree is visible to the caller instead of invisible above it. The
    state root is empty because the picking stage reads this judge's threshold
    history from it, and a test must not read the committed one.
    """
    checkout = tmp_path / name
    monkeypatch.setattr(session, "COUNCIL_ROOT", checkout / session.COUNCIL_ROOT_RELPATH)
    monkeypatch.setattr(common, "STATE_ROOT", checkout / "state")
    return checkout


def _prepared_bundle(selected: Selection) -> tuple[Path, PreparationReceipt]:
    session.prepare(config.load_council(), run_id=A_RUN, selection=selected)
    bundle = session.COUNCIL_ROOT / "outgoing" / "planner"
    receipt = work_files.read_preparation(bundle, selected, tenant.JUDGE_ID, A_NIGHT)
    assert receipt is not None and receipt.state == "ready"
    return bundle, receipt


def _settle(selected: Selection) -> None:
    session.settle(
        config.load_council(),
        date=A_NIGHT,
        run_id=A_RUN,
        state_dir=common.STATE_ROOT,
        commit_sha=selected.git_sha,
        selection=selected,
    )


def test_every_path_this_tenant_writes_for_a_later_job_is_inside_the_carried_root(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rule the whole night rests on, asked of the disk and not of the source.

    The declared task file must exist inside the carried invocation, including
    on an empty day that leaves only its CSV header as bookkeeping.
    """
    runner = _one_runner(tmp_path, "picked-the-work", monkeypatch)
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "no-day-was-published")

    with session._route(_selection(shards=2), tenant.JUDGE_ID):
        result = tenant.TENANT.prepare(date=A_NIGHT, run_id=A_RUN, shards=2)
        carried = runner / session.COUNCIL_ROOT_RELPATH
        drawn = tenant._draw_path(A_NIGHT)
        assert drawn.is_file()
        assert drawn.is_relative_to(carried)
        assert result.files == (session.artifact_path(drawn),)
        assert result.outcome is ShardOutcome.NOTHING_TO_DO


def test_preparation_deals_real_pairs_at_the_admitted_width(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The selected width, not the configured maximum, decides pair ownership."""
    _one_runner(tmp_path, "picked-real-work", monkeypatch)
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "digest")
    a_published_day(common.PUBLIC_ROOT, date=A_NIGHT)
    with session._route(_selection(shards=2), tenant.JUDGE_ID):
        result = tenant.TENANT.prepare(date=A_NIGHT, run_id=A_RUN, shards=2)
        draw = tenant._draw_path(A_NIGHT)
        rows = [
            row
            for shard in range(2)
            for row in judge_item_pairs._rows_this_shard_owns(draw, shard=shard, shards=2)
        ]

        assert result.outcome is ShardOutcome.COMPLETED
        assert rows
        assert {row.work_part_index for row in rows} <= {0, 1}
        assert result.files == (
            session.artifact_path(draw),
            session.artifact_path(tenant._score_pool_path(A_NIGHT)),
        )


def test_a_unit_on_a_second_runner_finds_the_work_the_first_one_picked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The trip a night really makes, with only the artifact in between.

    One runner picks the work. What crosses is the directory the workflow
    uploads, copied whole and by itself. A second runner then reads the draw the
    way a judging unit reads it.

    **The day has nothing published, and that is the case worth driving.** The
    selection writes a header either way, so an absent draw never means "nothing
    to judge" - which is what lets the shard refuse rather than return empty.
    """
    _one_runner(tmp_path, "picked-the-work", monkeypatch)
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "no-day-was-published")
    with session._route(_selection(), tenant.JUDGE_ID):
        result = tenant.TENANT.prepare(date=A_NIGHT, run_id=A_RUN, shards=8)
        drawn = tenant._draw_path(A_NIGHT)

    judged = tmp_path / "judged-a-shard"
    monkeypatch.setattr(session, "COUNCIL_ROOT", judged / session.COUNCIL_ROOT_RELPATH)
    destination = session.invocation_root(_selection(), tenant.JUDGE_ID) / result.files[0]
    destination.parent.mkdir(parents=True)
    shutil.copyfile(drawn, destination)
    with session._route(_selection(), tenant.JUDGE_ID):
        on_the_second_runner = tenant._draw_path(A_NIGHT)

    assert drawn.is_file(), "the unit that picks the work left no draw"
    assert on_the_second_runner.is_file(), (
        "the draw did not travel, so all eight units would die on a missing file"
    )
    assert judge_item_pairs._rows_this_shard_owns(on_the_second_runner, shard=0, shards=8) == []


def test_a_draw_that_did_not_travel_is_refused_and_says_why(tmp_path: Path) -> None:
    """A missing draw is an error, never an empty day, and the message has to say so.

    The selection writes a header on a day it drew nothing from, so the only
    thing an absent file can mean is that it never reached this runner. Two
    people read the old message and went looking at the ordering of the jobs.
    """
    with pytest.raises(FileNotFoundError, match="carries between jobs"):
        judge_item_pairs._rows_this_shard_owns(
            tmp_path / "nothing-was-downloaded.csv", shard=0, shards=8
        )


def test_the_place_a_unit_writes_its_verdicts_is_the_place_the_settle_reads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Writer and reader, asked of the two functions the night really calls.

    These two ran on different runners and against different roots until
    2026-09-23: the units wrote where nothing was uploaded from and the settle
    listed an empty directory, so a night came back having counted nothing and
    reported success.
    """
    runner = _one_runner(tmp_path, "judged-a-shard", monkeypatch)

    written = [tenant._verdict_path(A_NIGHT, shard=unit) for unit in range(8)]
    read = tenant._verdicts_dir(A_NIGHT)

    assert {path.parent for path in written} == {read}
    assert len({path.name for path in written}) == 8, "eight units, eight names"
    assert read.is_relative_to(runner / session.COUNCIL_ROOT_RELPATH)


def test_the_real_distinct_pool_leaves_the_draw_alone_and_files_its_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Count unused pairs too, then import the real receipt and read the settled Parquet row."""
    _one_runner(tmp_path, "planner", monkeypatch)
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "digest")
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "2")
    yesterday, = lookback_days(A_NIGHT, within_days=1)
    today = [
        item(f"world-0{index}", source=f"source-{index}", when=f"{A_NIGHT}T06:00:00Z")
        for index in range(1, 6)
    ]
    repeated = item("world-00", source="source-1", when=f"{yesterday}T18:00:00Z").model_copy(
        update={"source_url": today[0].source_url}
    )
    older = item("world-09", source="source-9", when=f"{yesterday}T18:00:00Z")
    a_published_day(common.PUBLIC_ROOT, date=A_NIGHT, stories=[(story, 0.0) for story in today])
    a_published_day(common.PUBLIC_ROOT, date=yesterday, stories=[(repeated, 180.0), (older, 180.0)])

    selected = _selection(attempt=2)
    bundle, receipt = _prepared_bundle(selected)
    with session._route(selected, tenant.JUDGE_ID):
        draw_path = tenant._draw_path(A_NIGHT)
        pool_path = tenant._score_pool_path(A_NIGHT)
        assert tuple(file.path for file in receipt.files) == (
            session.artifact_path(draw_path),
            session.artifact_path(pool_path),
        )
    payload = ContentSimilarityScorePool.read(pool_path)
    assert (payload.date, payload.run_id, payload.attempt) == (A_NIGHT, A_RUN, 2)
    before = tmp_path / "unobserved.csv"
    unobserved = pick_item_pairs.stage_pick_item_pairs(
        A_NIGHT,
        run_id=A_RUN,
        settings=config.load(),
        draw_path=before,
        digest_root=common.PUBLIC_ROOT,
        state_dir=common.STATE_ROOT,
    )
    assert draw_path.read_bytes() == before.read_bytes()
    pool = payload.histogram
    # The ten same-day pairs score 1. The five against the unique earlier story score -1.
    # The republished URL contributes no new key even though its earlier scores differ.
    assert (pool.counts[0], pool.counts[-1]) == (len(today), comb(len(today), 2))
    assert len(unobserved.draw.taken) < sum(pool.counts) == unobserved.draw.pairs_available

    _one_runner(tmp_path, "collector", monkeypatch)
    assert work_files.import_preparation(
        session.COUNCIL_ROOT, bundle, selected, tenant.JUDGE_ID, A_NIGHT
    ) == receipt
    rules = judge_settings.load().diagnostics
    earlier_pool = ScorePoolHistogram(
        stamp=pool.stamp, edges=pool.edges, counts=(2, *((0,) * (len(pool.counts) - 2)), 1),
    )
    earlier_run = f"{A_NIGHT}-9"
    days = lookback_days(A_NIGHT, within_days=rules.score_baseline_days)
    for day in days:
        prior = a_night_with_pool(a_night(day, earlier_run), earlier_pool)
        file_through_the_door(common.STATE_ROOT, THRESHOLD_HISTORY, prior)

    _settle(selected)

    row, = load_threshold_history(common.STATE_ROOT, [A_NIGHT])
    assert row.score_pool_histogram == diagnostic_text(pool)
    assert row.score_drift_status is ScoreDriftStatus.MEASURED
    assert row.score_drift_baseline is not None


def test_a_score_pool_not_in_the_receipt_cannot_supply_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _one_runner(tmp_path, "planner", monkeypatch)
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "digest")
    a_published_day(common.PUBLIC_ROOT, date=A_NIGHT)
    selected = _selection()
    bundle, receipt = _prepared_bundle(selected)
    draw_file, pool_file = receipt.files
    bundle_root = work_files.invocation_root(bundle, selected, tenant.JUDGE_ID)
    bundled_pool = bundle_root / pool_file.path
    atomic_write.write_atomic(
        work_files.preparation_path(bundle, selected, tenant.JUDGE_ID, A_NIGHT),
        receipt.model_copy(update={"files": (draw_file,)}).to_json(),
    )

    _one_runner(tmp_path, "collector", monkeypatch)
    work_files.import_preparation(session.COUNCIL_ROOT, bundle, selected, tenant.JUDGE_ID, A_NIGHT)
    # Even a valid same-attempt file at the expected address is not receipt evidence.
    with session._route(selected, tenant.JUDGE_ID):
        shutil.copyfile(bundled_pool, tenant._score_pool_path(A_NIGHT))
    _settle(selected)

    row, = load_threshold_history(common.STATE_ROOT, [A_NIGHT])
    assert row.score_drift_status is ScoreDriftStatus.NO_HISTOGRAM
    assert row.score_pool_histogram is None
    assert row.score_drift_baseline is None
    assert row.score_psi is row.score_ks_distance is row.score_wasserstein_distance is None


@pytest.mark.parametrize("remove", [False, True], ids=["changed", "missing"])
def test_a_declared_score_pool_must_survive_transfer_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, remove: bool
) -> None:
    _one_runner(tmp_path, "planner", monkeypatch)
    monkeypatch.setattr(common, "PUBLIC_ROOT", tmp_path / "digest")
    a_published_day(common.PUBLIC_ROOT, date=A_NIGHT)
    selected = _selection()
    bundle, receipt = _prepared_bundle(selected)

    _one_runner(tmp_path, "collector", monkeypatch)
    work_files.import_preparation(session.COUNCIL_ROOT, bundle, selected, tenant.JUDGE_ID, A_NIGHT)
    pool_file = session.invocation_root(selected, tenant.JUDGE_ID) / receipt.files[1].path
    if remove:
        pool_file.unlink()
    else:
        # The payload still parses and names the right attempt, but the bytes are not the receipt's.
        atomic_write.write_atomic(pool_file, pool_file.read_text(encoding="utf-8") + "\n")
    with pytest.raises(work_files.FileIntegrityError):
        _settle(selected)
    assert load_threshold_history(common.STATE_ROOT, [A_NIGHT]) == []
