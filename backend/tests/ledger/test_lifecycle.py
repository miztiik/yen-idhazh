"""Does a paused family take no new rows, while maintenance and the compact tier still write?

A family's `lifecycle_status` says whether new rows are written into its
ledgers. Every route that writes new rows asks `ledger.accepts_new_rows` first,
and into a paused family it writes nothing, logs one warning naming the ledger,
the family, the status and the rows, and carries on - a run that stopped on a
status would cost every other family its rows.

A family is paused the way the suite redirects its roots: a real registry, read
from the committed `config/ledgers.json` with that one family's status changed,
handed to the ledger through `monkeypatch.setattr`. Nothing is mocked.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Final

import pytest
from conftest import CONFIG_DIR, read_text

from idhazh import config, ledger
from idhazh.contracts.base import Contract, ServerJob
from idhazh.contracts.content_similarity_judge_metrics import ContentSimilarityJudgeMetrics
from idhazh.contracts.council_shard_outcome import CouncilShardOutcome
from idhazh.contracts.day_metrics import DayMetrics
from idhazh.contracts.feed_health import FeedHealthRow
from idhazh.contracts.feed_retirement import FeedRetirementRow
from idhazh.contracts.file_envelope import Period, RowIdentity, Tier, WriterIdentity
from idhazh.contracts.fitted_similarity_threshold import FittedSimilarityThreshold
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import LedgerLifecycleStatus, LedgersConfig
from idhazh.contracts.merge_line_holdout_score import MergeLineHoldoutScore
from idhazh.contracts.seen import PublishedRow, SeenRow
from idhazh.contracts.story_similarity_pair import StorySimilarityPair
from idhazh.contracts.visual_prune import VisualPruneRow
from idhazh.council import metrics_sink
from idhazh.ledger import paths
from idhazh.stages import score_merge_line_holdout, work
from idhazh.telemetry import FileSink, source_health
from idhazh.telemetry.publish import day_metrics

from ._fixtures import fixture_rows

pytestmark = pytest.mark.contract

A_DAY: Final = "2026-09-24"
A_RUN: Final = "2026-09-24-17482910337"
SKIPPED: Final = "ledger write skipped"


def _first[M: Contract](model: type[M]) -> M:
    """The first named contract fixture of this model."""
    return fixture_rows(model)[0]


def _identity(job: ServerJob) -> WriterIdentity:
    return WriterIdentity(
        run_id=A_RUN, attempt=1, job=job, shard=0, producer="tests.ledger", git_sha="a" * 40
    )


def _family_of(which: LedgerName) -> str:
    """The family the committed registry files this ledger under."""
    registry = LedgersConfig.from_json(read_text(CONFIG_DIR / paths.REGISTRY_FILENAME))
    return next(
        family.name
        for family in registry.families
        if any(held.name is which for held in family.ledgers)
    )


def _pause(
    monkeypatch: pytest.MonkeyPatch,
    family: str,
    status: LedgerLifecycleStatus = LedgerLifecycleStatus.PAUSED,
) -> None:
    """Hand the ledger a real registry with this one family's status changed."""
    raw = json.loads(read_text(CONFIG_DIR / paths.REGISTRY_FILENAME))
    for held in raw["families"]:
        if held["name"] == family:
            held["lifecycle_status"] = status.value
    monkeypatch.setattr(paths, "_CONFIG", LedgersConfig.model_validate(raw))


def _files(state: Path) -> int:
    return sum(1 for path in state.rglob("*") if path.is_file()) if state.exists() else 0


def _wrote(state: Path, write: Callable[[], object]) -> bool:
    """Whether this write left a file under the state root that was not there before."""
    before = _files(state)
    write()
    return _files(state) > before


# --- every checked route ---------------------------------------------------------


def _persist(state: Path) -> bool:
    row = _first(VisualPruneRow)
    return bool(
        ledger.persist(
            state,
            [row],
            ledger=LedgerName.VISUAL_PRUNES,
            covers=A_DAY,
            identity=_identity(ServerJob.ASSEMBLE),
        )
    )


def _segment(state: Path, *, extend: bool) -> bool:
    writer = ledger.extend_segment if extend else ledger.write_segment
    row = _first(FeedHealthRow)
    return _wrote(
        state,
        lambda: writer(
            state,
            LedgerName.FEED_HEALTH,
            [row],
            run_id=A_RUN,
            attempt=1,
            job=ServerJob.WORK,
            shard=0,
        ),
    )


def _collect_metrics(state: Path) -> bool:
    shipped = state.parent / "shipped"
    metrics_sink.ship_judge_metrics(
        _first(ContentSimilarityJudgeMetrics),
        judge_id="content-similarity-judge",
        shard=0,
        out_dir=shipped,
    )
    which = LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS
    return _wrote(
        state,
        lambda: metrics_sink.collect_judge_metrics(
            shipped,
            judge_id="content-similarity-judge",
            contract=ContentSimilarityJudgeMetrics,
            which=which,
            into=ledger.path(state, which, A_DAY),
        ),
    )


def _trace(state: Path) -> bool:
    return isinstance(work.trace_sink(config.load(CONFIG_DIR), run_id=A_RUN, shard=0), FileSink)


#: Every route that records new rows and asks the check, with the ledger it
#: writes and how many rows it tries. The judge's record and archive and the
#: digest fragment are driven through their stages in their own modules' tests.
ROUTES: Final[dict[str, tuple[LedgerName, int, Callable[[Path], bool]]]] = {
    "persist": (LedgerName.VISUAL_PRUNES, 1, _persist),
    "write_segment": (LedgerName.FEED_HEALTH, 1, lambda s: _segment(s, extend=False)),
    "extend_segment": (LedgerName.FEED_HEALTH, 1, lambda s: _segment(s, extend=True)),
    "append_seen": (
        LedgerName.SEEN,
        1,
        lambda s: _wrote(
            s,
            lambda: ledger.append_seen(
                s, A_DAY, [_first(SeenRow)], identity=_identity(ServerJob.PLAN)
            ),
        ),
    ),
    "append_published": (
        LedgerName.PUBLISHED,
        1,
        lambda s: _wrote(
            s,
            lambda: ledger.append_published(
                s, A_DAY, [_first(PublishedRow)], identity=_identity(ServerJob.ASSEMBLE)
            ),
        ),
    ),
    "file_retirements": (
        LedgerName.FEED_RETIREMENTS,
        1,
        lambda s: _wrote(
            s,
            lambda: source_health.file_retirements(
                s, [_first(FeedRetirementRow)], _identity(ServerJob.PLAN)
            ),
        ),
    ),
    "append_story_similarity_pairs": (
        LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS,
        1,
        lambda s: _wrote(
            s,
            lambda: ledger.append_story_similarity_pairs(s, A_DAY, [_first(StorySimilarityPair)]),
        ),
    ),
    "append_fitted_thresholds": (
        LedgerName.CONTENT_SIMILARITY_JUDGE_FITTED_THRESHOLDS,
        1,
        lambda s: _wrote(
            s,
            lambda: ledger.append_fitted_thresholds(s, A_DAY, [_first(FittedSimilarityThreshold)]),
        ),
    ),
    "append_council_shard_outcomes": (
        LedgerName.LLM_COUNCIL_SHARD_OUTCOMES,
        1,
        lambda s: _wrote(
            s,
            lambda: ledger.append_council_shard_outcomes(s, A_DAY, [_first(CouncilShardOutcome)]),
        ),
    ),
    "score_merge_line_holdout": (
        LedgerName.CONTENT_SIMILARITY_JUDGE_MERGE_LINE_HOLDOUT_SCORES,
        1,
        lambda s: _wrote(
            s, lambda: score_merge_line_holdout._append(s, A_DAY, _first(MergeLineHoldoutScore))
        ),
    ),
    "collect_judge_metrics": (LedgerName.CONTENT_SIMILARITY_JUDGE_METRICS, 1, _collect_metrics),
    "day_metrics": (
        LedgerName.DAY_METRICS,
        1,
        lambda s: _wrote(s, lambda: day_metrics.write(s, _first(DayMetrics))),
    ),
    "trace_sink": (LedgerName.TRACES, 0, _trace),
}


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_every_checked_route_writes_into_an_active_family(route: str, tmp_path: Path) -> None:
    _, _, write = ROUTES[route]

    assert write(tmp_path / "state"), f"{route} wrote nothing into an active family"


@pytest.mark.parametrize("route", sorted(ROUTES))
def test_every_checked_route_writes_nothing_into_a_paused_family_and_says_so_once(
    route: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The oracle's first case: nothing written, one warning, and the run carries on."""
    which, rows, write = ROUTES[route]
    family = _family_of(which)
    _pause(monkeypatch, family)

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        wrote = write(tmp_path / "state")

    skipped = [record.getMessage() for record in caplog.records if SKIPPED in record.getMessage()]
    assert not wrote, f"{route} wrote into the paused family {family}"
    assert skipped == [
        f"{SKIPPED} ledger={which.value} family={family} status=paused rows={rows}"
    ]


def test_a_retired_family_is_skipped_exactly_like_a_paused_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _pause(monkeypatch, _family_of(LedgerName.VISUAL_PRUNES), LedgerLifecycleStatus.RETIRED)

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        wrote = _persist(tmp_path / "state")

    assert not wrote
    assert [r.getMessage() for r in caplog.records if SKIPPED in r.getMessage()] == [
        f"{SKIPPED} ledger=visual-prunes family=visual-prunes status=retired rows=1"
    ]


# --- a paused family costs only its own rows -----------------------------------------


def test_the_plan_stage_with_seen_paused_still_lands_feed_health_and_counterfactual_scores(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The oracle's second case: one paused family does not stop the stage's other writes."""
    from test_plan import COMMUNITY, LAB, TRADE, plan

    state = tmp_path / "state"
    _pause(monkeypatch, _family_of(LedgerName.SEEN))

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        built = plan([LAB, TRADE, COMMUNITY], state=state)

    assert built.items, "the stage planned nothing, so this proves nothing"
    assert not ledger.raw_root(state, LedgerName.SEEN).exists()
    assert list(ledger.tree_root(state, LedgerName.FEED_HEALTH).rglob("*.csv"))
    assert ledger.list_raw_files(state, LedgerName.COUNTERFACTUAL_SCORES)
    skipped = [r.getMessage() for r in caplog.records if SKIPPED in r.getMessage()]
    assert len(skipped) == 1
    assert skipped[0].startswith(f"{SKIPPED} ledger=seen family=seen status=paused rows=")


# --- maintenance and the compact tier are never skipped ------------------------------


@pytest.mark.parametrize(
    ("job", "tier"),
    [
        (ServerJob.RUN_TASKS, Tier.RAW),
        (ServerJob.MIGRATE, Tier.RAW),
        (ServerJob.ASSEMBLE, Tier.COMPACT),
    ],
    ids=["run-tasks-raw", "migrate-raw", "assemble-compact"],
)
def test_the_door_writes_into_a_paused_family_for_maintenance_and_the_compact_tier(
    job: ServerJob,
    tier: Tier,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The oracle's third case: each of these files rows again that were already recorded.

    Skipping one after its source was deleted would lose rows while the run
    reported success, so a status never stops them.
    """
    row = _first(VisualPruneRow)
    _pause(monkeypatch, _family_of(LedgerName.VISUAL_PRUNES))
    unit = ledger.unit_id(
        ledger=LedgerName.VISUAL_PRUNES,
        covers=row.date,
        run_id=A_RUN,
        job=ServerJob.ASSEMBLE,
        shard=0,
        producer="tests.ledger",
    )
    filed = ledger.StoredRow(
        identity=RowIdentity(
            ledger=LedgerName.VISUAL_PRUNES,
            covers=row.date,
            run_id=A_RUN,
            attempt=1,
            job=ServerJob.ASSEMBLE,
            shard=0,
            unit_id=str(unit),
        ),
        row=row,
    )

    with caplog.at_level(logging.WARNING, logger="idhazh"):
        if tier is Tier.RAW:
            written = ledger.persist(
                tmp_path / "state",
                [row],
                ledger=LedgerName.VISUAL_PRUNES,
                covers=row.date,
                identity=_identity(job),
            )
        else:
            written = [
                ledger.persist_period(
                    tmp_path / "state",
                    [filed],
                    model=VisualPruneRow,
                    ledger=LedgerName.VISUAL_PRUNES,
                    period=Period.DAILY,
                    covers=row.date,
                    identity=_identity(job),
                    built_from=1,
                )
            ]

    assert [path.is_file() for path in written] == [True]
    assert not [r for r in caplog.records if SKIPPED in r.getMessage()]
