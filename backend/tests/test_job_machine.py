"""Does job instrumentation preserve identity, elapsed time and work failures?"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import SEED_COMMIT

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry import job_machine

DAY = "2026-09-27"
RUN = f"{DAY}-18012345678"
START = datetime(2026, 9, 27, 0, 40, tzinfo=UTC)


@pytest.mark.parametrize("fails", [False, True], ids=["success", "failed-work"])
def test_both_halves_name_one_attempt_and_clock_the_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fails: bool
) -> None:
    monkeypatch.setenv("GITHUB_RUN_ATTEMPT", "9")
    settings = config.load()
    settings.app.observability.host_fingerprint_bandwidth_floor_mib = 0
    written: list[Path] = []

    def work() -> None:
        with job_machine.record(
            date=DAY,
            run_id=RUN,
            settings=settings,
            state_root=tmp_path,
            commit_sha=SEED_COMMIT,
            job=ServerJob.RUN_TASKS,
            shard=3,
            attempt=2,
            started_at=START,
            clock=lambda: START + timedelta(seconds=60),
        ) as paths:
            written.extend(paths)
            if fails:
                raise RuntimeError("the work failed")
        written[:] = paths

    if fails:
        with pytest.raises(RuntimeError, match="the work failed"):
            work()
    else:
        work()

    (row,) = ledger.load_days(
        tmp_path, LedgerName.HOST_FINGERPRINT, [DAY], model=HostFingerprintRow
    )
    assert row.job_seconds == 60
    assert row.fingerprint is not None
    assert (row.job, row.shard, row.run_id) == (ServerJob.RUN_TASKS, 3, RUN)
    files = ledger.list_raw_files(tmp_path, LedgerName.HOST_FINGERPRINT, days={DAY})
    assert len(files) == 2 and {f.envelope.identity.attempt for f in files} == {2}
    assert len({f.envelope.unit_id for f in files}) == 1
    if not fails:
        assert set(written) == {f.path for f in files}


def test_disabled_recording_writes_neither_half(tmp_path: Path) -> None:
    settings = config.load()
    settings.app.observability.host_fingerprint = False
    with job_machine.record(
        date=DAY,
        run_id=RUN,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        job=ServerJob.RUN_TASKS,
    ) as written:
        assert written == []
    assert written == [] and not ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT).exists()


def test_instrument_io_failure_is_reported_without_losing_the_work(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    settings = config.load()
    settings.app.observability.host_fingerprint_bandwidth_floor_mib = 0
    blocked = tmp_path / "not-a-directory"
    blocked.write_text("blocked", encoding="ascii")
    with job_machine.record(
        date=DAY,
        run_id=RUN,
        settings=settings,
        state_root=blocked,
        commit_sha=SEED_COMMIT,
        job=ServerJob.RUN_TASKS,
    ) as written:
        assert written == []
    assert written == []
    assert "machine probe not written" in caplog.text
    assert "machine clock not written" in caplog.text
