"""Does a job without a bound Rust session stay uninstrumented without losing its work?"""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import SEED_COMMIT
from test_host_event_client import _manifest

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.ledger_name import LedgerName
from idhazh.telemetry import job_machine
from idhazh.telemetry.host_event_client import HostEventClient

DAY = "2026-09-27"
RUN = f"{DAY}-18012345678"


@pytest.mark.parametrize("fails", [False, True], ids=["success", "failed-work"])
def test_uninstrumented_job_never_writes_a_python_host_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, fails: bool
) -> None:
    monkeypatch.delenv("IDHAZH_HOST_TELEMETRY_MODE", raising=False)
    with caplog.at_level("INFO"):
        try:
            with job_machine.record(
                date=DAY, run_id=RUN, settings=config.load(), state_root=tmp_path,
                commit_sha=SEED_COMMIT, job=ServerJob.RUN_TASKS,
            ) as written:
                assert written == []
                if fails:
                    raise RuntimeError("the work failed")
        except RuntimeError as error:
            assert fails and str(error) == "the work failed"
        else:
            assert not fails
    assert written == []
    assert not ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT).exists()
    assert "no bound Rust session" in caplog.text


def test_resource_only_client_cannot_become_a_host_writer(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)
    events = HostEventClient(tmp_path, Path("manifest.json"), Path("config.json"), native=False)
    with pytest.raises(ValueError, match="require a native session"):
        with job_machine.record(
            date=manifest.date, run_id=manifest.run_id, settings=config.load(),
            state_root=tmp_path / "state", commit_sha=manifest.git_sha,
            job=manifest.job, shard=manifest.shard, attempt=manifest.attempt,
            host_events=events,
        ):
            pytest.fail("a resource-only client was accepted as a host writer")
    assert not ledger.raw_root(tmp_path / "state", LedgerName.HOST_FINGERPRINT).exists()


def test_native_environment_requires_independent_bound_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "rust")
    for name in ("WORKSPACE", "MANIFEST", "CONFIG", "INVOCATION"):
        monkeypatch.delenv(f"IDHAZH_HOST_TELEMETRY_{name}", raising=False)
    with pytest.raises(ValueError, match="native host session needs"):
        with job_machine.record(
            date=DAY, run_id=RUN, settings=config.load(), state_root=tmp_path,
            commit_sha=SEED_COMMIT, job=ServerJob.RUN_TASKS,
        ):
            pytest.fail("an unprepared native producer started work")
    assert not ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT).exists()


def test_native_environment_io_failure_cannot_start_work_with_a_python_fallback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_MODE", "rust")
    monkeypatch.setenv("IDHAZH_HOST_TELEMETRY_WORKSPACE", str(tmp_path))
    for name in ("MANIFEST", "CONFIG", "INVOCATION"):
        monkeypatch.setenv(f"IDHAZH_HOST_TELEMETRY_{name}", f"absent-{name.lower()}.json")
    with pytest.raises(OSError):
        with job_machine.record(
            date=DAY, run_id=RUN, settings=config.load(), state_root=tmp_path,
            commit_sha=SEED_COMMIT, job=ServerJob.RUN_TASKS,
        ):
            pytest.fail("native input failure started uninstrumented work")
    assert not ledger.raw_root(tmp_path, LedgerName.HOST_FINGERPRINT).exists()
