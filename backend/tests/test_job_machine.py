"""Does job instrumentation preserve identity, elapsed time and work failures?"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from conftest import SEED_COMMIT
from test_host_event_client import SessionPeer, _manifest

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry import job_machine, silicon
from idhazh.telemetry.host_event_client import HostEventClient

DAY = "2026-09-27"
RUN = f"{DAY}-18012345678"
START = datetime(2026, 9, 27, 0, 40, tzinfo=UTC)


class _NativeEvents:
    native = True

    def __init__(self, *, started: bool, active: bool = True) -> None:
        self.native_started = started
        self._active = active

    def begin_job(self) -> bool:
        if self.native_started:
            raise OSError("native command already published")
        return self._active

    def end_job(self) -> bool:
        return True


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


def test_native_boundary_is_the_sole_raw_host_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = config.load()
    events = _NativeEvents(started=False)
    monkeypatch.setattr(
        silicon,
        "file_machine_row",
        lambda **_: pytest.fail("Python machine writer competed with native output"),
    )
    monkeypatch.setattr(
        silicon,
        "file_job_clock",
        lambda **_: pytest.fail("Python clock writer competed with native output"),
    )

    with job_machine.record(
        date=DAY,
        run_id=RUN,
        settings=settings,
        state_root=tmp_path,
        commit_sha=SEED_COMMIT,
        job=ServerJob.RUN_TASKS,
        host_events=events,  # type: ignore[arg-type]
    ) as written:
        assert written == []


def test_shadow_boundary_keeps_both_authoritative_python_writes(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    peer = SessionPeer(tmp_path, manifest)
    settings = config.load()
    settings.app.observability.host_fingerprint_bandwidth_floor_mib = 0
    try:
        events = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"))
        assert events.register_worker(server_pid=None)
        with job_machine.record(
            date=manifest.date,
            run_id=manifest.run_id,
            settings=settings,
            state_root=tmp_path / "state",
            commit_sha=manifest.git_sha,
            job=manifest.job,
            shard=manifest.shard,
            attempt=manifest.attempt,
            started_at=START,
            clock=lambda: START + timedelta(seconds=60),
            host_events=events,
        ) as written:
            pass
        files = ledger.list_raw_files(
            tmp_path / "state", LedgerName.HOST_FINGERPRINT, days={manifest.date}
        )
        assert len(files) == 2
        assert set(written) == {file.path for file in files}
        (row,) = ledger.load_days(
            tmp_path / "state",
            LedgerName.HOST_FINGERPRINT,
            [manifest.date],
            model=HostFingerprintRow,
        )
        assert row.job_seconds == 60
    finally:
        peer.close()


def test_native_failure_after_publication_does_not_fall_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = config.load()
    events = _NativeEvents(started=True)
    monkeypatch.setattr(
        silicon,
        "file_machine_row",
        lambda **_: pytest.fail("partial native session must not write a Python row"),
    )
    with pytest.raises(OSError, match="native command already published"):
        with job_machine.record(
            date=DAY,
            run_id=RUN,
            settings=settings,
            state_root=tmp_path,
            commit_sha=SEED_COMMIT,
            job=ServerJob.RUN_TASKS,
            host_events=events,  # type: ignore[arg-type]
        ):
            raise AssertionError("native setup should fail before work starts")


def test_native_unavailable_before_publication_never_uses_legacy_writer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = config.load()
    events = _NativeEvents(started=False, active=False)
    with pytest.raises(RuntimeError, match="Python collection is disabled"):
        with job_machine.record(
            date=DAY,
            run_id=RUN,
            settings=settings,
            state_root=tmp_path,
            commit_sha=SEED_COMMIT,
            job=ServerJob.RUN_TASKS,
            host_events=events,  # type: ignore[arg-type]
        ):
            pytest.fail("work started without its selected native instrument")
    assert not ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT).exists()


def test_native_environment_requires_the_prepared_session_before_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "rust")
    for name in ("WORKSPACE", "MANIFEST", "CONFIG"):
        monkeypatch.delenv(f"IDHAZH_HOST_TELEMETRY_{name}", raising=False)
    with pytest.raises(ValueError, match="host event session needs"):
        with job_machine.record(
            date=DAY,
            run_id=RUN,
            settings=config.load(),
            state_root=tmp_path,
            commit_sha=SEED_COMMIT,
            job=ServerJob.RUN_TASKS,
        ):
            pytest.fail("an unprepared native producer started its work")
    assert not ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT).exists()


def test_native_environment_io_failure_does_not_fall_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "rust")
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MANIFEST", "absent-manifest.json")
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_CONFIG", "absent-config.json")
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_INVOCATION", "absent-invocation.json")
    with pytest.raises(OSError):
        with job_machine.record(
            date=DAY, run_id=RUN, settings=config.load(), state_root=tmp_path,
            commit_sha=SEED_COMMIT, job=ServerJob.RUN_TASKS,
        ):
            pytest.fail("native input I/O failure started work with legacy collection")
    assert not ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT).exists()


def test_native_config_cannot_select_a_python_fallback_without_a_launcher(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("IDHAZH_HOST_TELEMETRY_MODE", raising=False)
    settings = config.load()
    settings.app.observability.host_event_mode = "native"
    with pytest.raises(ValueError, match="host event session needs"):
        with job_machine.record(
            date=DAY, run_id=RUN, settings=settings, state_root=tmp_path,
            commit_sha=SEED_COMMIT, job=ServerJob.RUNTIME,
        ):
            pytest.fail("configured native mode fell back to Python")
    assert not ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT).exists()


def test_rust_selection_cannot_accept_a_supplied_shadow_collector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "rust")
    events = _NativeEvents(started=False)
    monkeypatch.setattr(events, "native", False)
    with pytest.raises(ValueError, match="cannot use a Python or shadow"):
        with job_machine.record(
            date=DAY, run_id=RUN, settings=config.load(), state_root=tmp_path,
            commit_sha=SEED_COMMIT, job=ServerJob.RUNTIME,
            host_events=events,  # type: ignore[arg-type]
        ):
            pytest.fail("Rust selection accepted a legacy collector")
    assert not ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT).exists()
