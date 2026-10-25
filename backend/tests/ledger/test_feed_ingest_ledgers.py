"""Are all planning ledgers registered before any planner writes rows?"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import replace
from datetime import date
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5

import pytest
from gardener.tasks._task import run_declared
from support.paths import CONFIG_DIR, CONTRACT_FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import config, ledger
from idhazh.contracts.base import Contract, ServerJob
from idhazh.contracts.collection_prune import StopReason
from idhazh.contracts.feed_ingest_article_assessment import ArticleAssessmentRecord
from idhazh.contracts.feed_ingest_candidate import derive_candidate_id
from idhazh.contracts.feed_ingest_dispatch import FeedIngestDispatch
from idhazh.contracts.feed_ingest_diversity import DiversityMetricRow
from idhazh.contracts.feed_ingest_editorial_selection import EditorialSelectionRow
from idhazh.contracts.feed_ingest_feedback import FeedIngestOperationalStateRow
from idhazh.contracts.feed_ingest_observations import DocumentObservationRecord
from idhazh.contracts.feed_ingest_rejection import CandidateRejectionRecord
from idhazh.contracts.feed_ingest_source_run import SourceRunRecord
from idhazh.contracts.file_envelope import Format, Period, WriterIdentity
from idhazh.contracts.knobs.gardener import CompactionPolicy
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgersConfig
from idhazh.ledger import paths
from idhazh.ledger.persist import StoredRow

pytestmark = pytest.mark.contract

PRODUCED_PLANNING_LEDGERS = (
    ("article-dispatches", FeedIngestDispatch, "feed-ingest-dispatch/one-article.json"),
    ("editorial-selections", EditorialSelectionRow, "feed-ingest-editorial-selection/one-article.json"),
    ("ingest-rejections", CandidateRejectionRecord, "feed-ingest-rejection/empty-feed.json"),
    ("feed-runs", SourceRunRecord, "feed-ingest-source-run/one-observation.json"),
    ("article-assessments", ArticleAssessmentRecord, "feed-ingest-article-assessment/one-observation.json"),
    ("article-selection-diversity", DiversityMetricRow, "feed-ingest-diversity/one-observation.json"),
)
LEGACY_PLANNING_LEDGERS = (
    ("dispatches", FeedIngestDispatch, "feed-ingest-dispatch/one-article.json"),
    ("rejections", CandidateRejectionRecord, "feed-ingest-rejection/empty-feed.json"),
    ("source-runs", SourceRunRecord, "feed-ingest-source-run/one-observation.json"),
    ("diversity", DiversityMetricRow, "feed-ingest-diversity/one-observation.json"),
)
DOCUMENT_OBSERVATION_LEDGER = (
    "document-observations",
    DocumentObservationRecord,
    "feed-ingest-document-observation/refused-fetch.json",
)
OPERATIONAL_STATE_LEDGER = (
    "operational-state",
    FeedIngestOperationalStateRow,
    "feed-ingest-operational-state/qualified.json",
)
RENAMED_DOCUMENT_OBSERVATION_LEDGER = (
    "ingest-observations",
    DocumentObservationRecord,
    "feed-ingest-document-observation/refused-fetch.json",
)
REGISTERED_PLANNING_LEDGERS = (
    *PRODUCED_PLANNING_LEDGERS,
    *LEGACY_PLANNING_LEDGERS,
    DOCUMENT_OBSERVATION_LEDGER,
    OPERATIONAL_STATE_LEDGER,
    RENAMED_DOCUMENT_OBSERVATION_LEDGER,
)


@pytest.mark.parametrize(("name", "model", "fixture"), REGISTERED_PLANNING_LEDGERS)
def test_planning_ledger_registration(name: str, model: type[Contract], fixture: str) -> None:
    """Missing registration, a wrong row binding or an unscheduled task fails here."""
    assert name in LedgerName, f"Planning ledger {name} is not registered"
    which = LedgerName(name)
    entry = paths.entry(which)
    assert entry.grain is Grain.RAW_AND_COMPACT
    assert entry.prefix == ("feed-ingest-plan", name)
    assert ledger.door_contract(which) is model
    key = ledger.door_key(which)
    assert key
    assert isinstance(model.from_json(read_text(CONTRACT_FIXTURES_DIR / fixture)), model)
    policy = config.load_gardener().tasks[f"compact-feed-ingest-plan-{name}"]
    assert isinstance(policy, CompactionPolicy)
    assert policy.ledger is which
    assert list(policy.owns) == [
        f"state/raw/feed-ingest-plan/{name}", f"state/compact/feed-ingest-plan/{name}"
    ]
    assert (policy.dry_run, policy.compact_after_days, policy.daily_keep_days) == (False, 1, 45)
    assert (policy.monthly_keep_days, policy.monthly_window.unit) == (93, "forever")
    assert (policy.yearly_keep_months, policy.yearly_prune_enable) == (36, True)


def test_planning_family_has_exactly_the_declared_ledgers() -> None:
    families = LedgersConfig.from_json(read_text(CONFIG_DIR / "ledgers.json")).families
    family = next((held for held in families if held.name == "feed-ingest-plan"), None)
    assert family is not None, "The feed-ingest-plan family is not registered"
    assert {held.name.value for held in family.ledgers} == {
        name for name, _, _ in REGISTERED_PLANNING_LEDGERS
    }


def _identity(attempt: int, run: int = 1, shard: int = 0) -> WriterIdentity:
    return WriterIdentity(
        run_id=f"2026-10-20-{run}", attempt=attempt, job=ServerJob.PLAN,
        shard=shard, producer="tests.feed_ingest_ledgers", git_sha="a" * 40,
    )


def _row(
    model: type[Contract], fixture: str, *, attempt: int, run: int = 1, second: bool = False
) -> Contract:
    payload: dict[str, Any] = model.from_json(
        read_text(CONTRACT_FIXTURES_DIR / fixture)
    ).model_dump(mode="json")
    if model is FeedIngestDispatch:
        content = payload["content"]
        content["run_id"] = f"2026-10-20-{run}"
        content["entry_ordinal"] = int(second)
        content["candidate_id"] = derive_candidate_id(
            content["run_id"], content["source_id"], content["entry_ordinal"]
        )
        payload["selection"]["candidate_id"] = content["candidate_id"]
    else:
        if model is FeedIngestOperationalStateRow:
            payload["state_revision"] = run * 10 + attempt
            payload["date"] = "2026-10-20"
            if second:
                payload["source_id"] = "second-feed"
        if model is DocumentObservationRecord:
            payload["event_id"] = str(
                uuid5(UUID(payload["event_id"]), f"{run}\n{attempt}\n{int(second)}")
            )
        if "run_id" in payload:
            payload["run_id"] = f"2026-10-20-{run}"
        if "attempt" in payload:
            payload["attempt"] = attempt
        if second:
            if "candidate_id" in payload and payload["candidate_id"] is not None:
                payload["candidate_id"] = "c" * 64
            elif model is DiversityMetricRow:
                payload["basis"] = "eligible"
            else:
                payload["source_id"] = "second-feed"
                if "source" in payload:
                    payload["source"]["source_id"] = "second-feed"
    return model.model_validate(payload)


def _raw(state: Path, which: LedgerName, model: type[Contract]) -> list[list[StoredRow[Contract]]]:
    return [
        ledger.load_stored([held.path], model=model)
        for held in ledger.read_day_files(state, which, "2026-10-20")
    ]


def _snapshot(rows: list[StoredRow[Contract]]) -> list[tuple[str, int, str, str]]:
    return sorted(
        (held.identity.run_id, held.identity.attempt, held.identity.unit_id, held.row.to_json())
        for held in rows
    )


@pytest.mark.parametrize(("name", "model", "fixture"), REGISTERED_PLANNING_LEDGERS)
def test_attempts_survive_real_compaction_and_late_repacking(
    tmp_path: Path, name: str, model: type[Contract], fixture: str
) -> None:
    """A fewer-item retry and a separate run stay distinct, even across multiple raw files."""
    which = LedgerName(name)
    state = tmp_path / "state"
    first = _row(model, fixture, attempt=1)
    second = _row(model, fixture, attempt=1, second=True)
    replay_identity = (
        _identity(1, shard=1) if model is DocumentObservationRecord else _identity(1)
    )
    for rows, identity in (
        ([first, second], _identity(1)),
        ([first], replay_identity),
        ([_row(model, fixture, attempt=2)], _identity(2)),
        ([_row(model, fixture, attempt=1, run=2)], _identity(1, run=2)),
    ):
        ledger.persist(
            state, rows, ledger=which, covers="2026-10-20", identity=identity, fmt=Format.PARQUET
        )
    key = ledger.door_key(which)
    raw = ledger.settle_rows(_raw(state, which, model), key)
    assert len(raw) == 4
    assert sorted(held.identity.attempt for held in raw) == [1, 1, 1, 2]
    assert len({held.identity.run_id for held in raw}) == 2
    task = f"compact-feed-ingest-plan-{name}"
    policy = config.load_gardener().tasks[task]
    assert isinstance(policy, CompactionPolicy)
    raw_bytes = {held.path: held.path.read_bytes() for held in ledger.read_day_files(
        state, which, "2026-10-20"
    )}
    dry = run_declared(
        task, policy.model_copy(update={"dry_run": True}), tmp_path,
        today=date(2026, 10, 22), first_year="2026",
    )
    assert dry.dry_run and dry.written and dry.taken
    assert all(path.read_bytes() == data for path, data in raw_bytes.items())
    assert not ledger.compact_index_path(state, which, Period.DAILY).exists()
    live = run_declared(task, policy, tmp_path, today=date(2026, 10, 22), first_year="2026")
    assert set(live.taken) == set(dry.taken)
    assert set(live.written) == set(dry.written)
    packed = ledger.compact_path(state, which, Period.DAILY, "2026-10-20")
    stored = ledger.load_stored([packed], model=model)
    assert _snapshot(stored) == _snapshot(raw)
    assert not ledger.read_day_files(state, which, "2026-10-20")
    assert len(ledger.load_days(state, which, {"2026-10-20"}, model=model, key=key)) == 4

    late = _row(model, fixture, attempt=3)
    ledger.persist(
        state, [late], ledger=which, covers="2026-10-20", identity=_identity(3),
        fmt=Format.PARQUET,
    )
    expected = ledger.settle_rows([stored, *_raw(state, which, model)], key)
    assert len(expected) == 5
    run_declared(task, policy, tmp_path, today=date(2026, 10, 23), first_year="2026")
    assert _snapshot(ledger.load_stored([packed], model=model)) == _snapshot(expected)
    assert len(ledger.load_days(state, which, {"2026-10-20"}, model=model, key=key)) == 5
    for period, covers in ((Period.MONTHLY, "2026-10"), (Period.YEARLY, "2026")):
        repacked = ledger.persist_period(
            state, expected, model=model, ledger=which, period=period, covers=covers,
            identity=_identity(1, run=9), built_from=1, fmt=Format.PARQUET,
        )
        reread = ledger.load_stored([repacked], model=model)
        assert _snapshot(reread) == _snapshot(expected)
        assert _snapshot(ledger.settle_rows([reread, reread], key)) == _snapshot(expected)


def test_zero_completion_evidence_survives_without_erasing_an_earlier_complete_attempt(
    tmp_path: Path,
) -> None:
    """No output file represents zero; a later complete source record does."""
    which = LedgerName.FEED_INGEST_PLAN_SOURCE_RUNS
    fixture = "feed-ingest-source-run/one-observation.json"
    state = tmp_path / "state"
    dispatches = LedgerName.FEED_INGEST_PLAN_DISPATCHES
    dispatch_fixture = "feed-ingest-dispatch/one-article.json"
    (output,) = ledger.persist(
        state, [
            _row(FeedIngestDispatch, dispatch_fixture, attempt=1),
            _row(FeedIngestDispatch, dispatch_fixture, attempt=1, second=True),
        ],
        ledger=dispatches, covers="2026-10-20", identity=_identity(1), fmt=Format.PARQUET,
    )
    envelope = ledger.read_envelope(output)
    payload = _row(SourceRunRecord, fixture, attempt=1).model_dump(mode="json")
    for entry in payload["completion_evidence"]:
        if entry["ledger"] == "dispatches":
            entry["row_count"] = 2
            entry["files"] = [{
                "file_id": str(envelope.file_id),
                "content_sha256": envelope.content_sha256,
                "row_count": 2,
            }]
    source = SourceRunRecord.model_validate(payload)
    zero = _row(SourceRunRecord, fixture, attempt=3)
    for row, attempt in ((source, 1), (zero, 3)):
        ledger.persist(
            state, [row], ledger=which, covers="2026-10-20",
            identity=_identity(attempt), fmt=Format.PARQUET,
        )
    # A partial retry has output but no completion record.
    ledger.persist(
        state, [_row(FeedIngestDispatch, dispatch_fixture, attempt=2)],
        ledger=dispatches, covers="2026-10-20", identity=_identity(2), fmt=Format.PARQUET,
    )
    task = "compact-feed-ingest-plan-source-runs"
    policy = config.load_gardener().tasks[task]
    run_declared(task, policy, tmp_path, today=date(2026, 10, 22), first_year="2026")
    dispatch_task = "compact-feed-ingest-plan-dispatches"
    run_declared(
        dispatch_task, config.load_gardener().tasks[dispatch_task], tmp_path,
        today=date(2026, 10, 22), first_year="2026",
    )
    rows = ledger.load_days(
        state, which, {"2026-10-20"}, model=SourceRunRecord, key=ledger.door_key(which)
    )
    assert [row.attempt for row in rows] == [1, 3]
    assert rows[0] == source
    assert rows[0].completion_evidence is not None
    dispatch_evidence = next(
        entry for entry in rows[0].completion_evidence if entry.ledger == "dispatches"
    )
    assert dispatch_evidence.files[0].file_id == envelope.file_id
    assert dispatch_evidence.files[0].content_sha256 == envelope.content_sha256
    assert rows[1].completion_evidence is not None
    assert all(
        entry.row_count == 0 and not entry.files for entry in rows[1].completion_evidence
    )
    stored = ledger.load_stored(
        [ledger.compact_path(state, dispatches, Period.DAILY, "2026-10-20")],
        model=FeedIngestDispatch,
    )
    assert sorted(held.identity.attempt for held in stored) == [1, 1, 2]
    # The native producer and reader bracket the actual production compactor.
    bun = shutil.which("bun")
    assert bun, "Install the declared TypeScript planner dependencies before this CI case"
    generated = tmp_path / "native-attempts"
    driver = REPO_ROOT / "services" / "feed-ingest-plan" / "test" / "compaction-recording.ts"
    subprocess.run(
        [bun, str(driver), "produce", str(generated)], check=True, cwd=REPO_ROOT, timeout=120
    )
    native = json.loads((generated / "attempts.json").read_text(encoding="utf-8"))
    assert native["keys"] == {
        name: list(ledger.door_key(LedgerName(name)))
        for name, _, _ in (*PRODUCED_PLANNING_LEDGERS, *LEGACY_PLANNING_LEDGERS)
    }
    for tier, today in (
        ("daily", date(2026, 10, 23)),
        ("monthly", date(2026, 11, 3)),
        ("yearly", date(2027, 3, 15)),
    ):
        for name, _, _ in PRODUCED_PLANNING_LEDGERS:
            task = f"compact-feed-ingest-plan-{name}"
            declaration = config.load_gardener().tasks[task]
            tuned = declaration.model_copy(update={
                "max_periods_per_run": 400, "daily_keep_days": 1, "monthly_keep_days": 33,
            })
            # A wake closes years before months before days; later wakes consume their indexes.
            for _wake in range(3):
                run_declared(task, tuned, generated, today=today, first_year="2026")
        subprocess.run(
            [bun, str(driver), "verify", str(generated), tier],
            check=True, cwd=REPO_ROOT, timeout=120,
        )


def test_planning_keys_are_trusted_and_never_applied_to_another_ledger(tmp_path: Path) -> None:
    which = LedgerName.FEED_INGEST_PLAN_DISPATCHES
    state = tmp_path / "state"
    row = _row(FeedIngestDispatch, "feed-ingest-dispatch/one-article.json", attempt=1)
    ledger.persist(
        state, [row], ledger=which, covers="2026-10-20", identity=_identity(1),
        fmt=Format.PARQUET,
    )
    files = _raw(state, which, FeedIngestDispatch)
    with pytest.raises(ValueError, match="declared key"):
        ledger.settle_rows(files, ("content.__class__",))
    original = files[0][0]
    assert isinstance(original.row, FeedIngestDispatch)
    changed = original.row.model_copy(update={
        "content": original.row.content.model_copy(update={"title": "Different title"}),
    })
    conflict = replace(original, row=changed)
    with pytest.raises(ValueError, match="conflicting duplicate"):
        ledger.settle_rows([*files, [conflict]], ledger.door_key(which))
    ledger.persist(
        state, [changed], ledger=which, covers="2026-10-20", identity=_identity(1),
        fmt=Format.PARQUET,
    )
    before = {held.path: held.path.read_bytes() for held in ledger.read_day_files(
        state, which, "2026-10-20"
    )}
    task = "compact-feed-ingest-plan-dispatches"
    refused = run_declared(
        task, config.load_gardener().tasks[task], tmp_path,
        today=date(2026, 10, 22), first_year="2026",
    )
    assert refused.stopped_because is StopReason.FAILED
    assert all(path.read_bytes() == data for path, data in before.items())
    assert not ledger.compact_path(state, which, Period.DAILY, "2026-10-20").exists()
