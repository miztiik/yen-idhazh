"""Does the real collecting publisher retain earlier and later completed tenant work?"""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from _host_placement import refuse_external_placement
from gardener._garden import an_origin, git, on_origin, quiet_git

from idhazh import ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.council_run_record import CouncilRunRecord
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import registry, session
from utilities.council_publish import settle_and_publish
from utilities.publication_git import Repository

from ._config import copy_config, set_host_fingerprint_placement, write_declarations
from ._tenants import TENANT_SOURCE, a_venue, forget
from .test_lifecycle import room

SOURCE = TENANT_SOURCE.replace(
    "from pathlib import Path", "from pathlib import Path\nfrom idhazh import atomic_write"
).replace(
    "        self.settled.append(date)",
    """        self.settled.append(date)
        atomic_write.write_atomic(
            state_dir.parent / self.committed_paths[0] / (date + ".json"), "completed\\n"
        )
        if self.judge_id.endswith("failed") and date == "2026-10-08":
            raise RuntimeError("later tenant failed after completing its write")""",
)


def configuration(root: Path, slugs: tuple[str, ...]) -> Path:
    target = copy_config(root)
    write_declarations(target, slugs)
    path = target / "llm_council.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["judge_names"] = list(slugs)
    path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    return target


def test_publication_resolves_only_the_active_judge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            "config/push-retry.json": '{"deadline_seconds":{"default":300},"base_step_seconds":0.001,'
            '"ceiling_seconds":0.001,"ceiling_after":1}\n',
        },
    )
    package = "publication_lifecycle"
    a_venue(
        tmp_path,
        package=package,
        slugs={"active-judge": (1, ("state/paper",))},
        poisoned_neighbour="paused-judge",
        source=SOURCE,
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    forget(package)
    try:
        target = room(
            tmp_path,
            {
                "paused-judge": ("paused", True),
                "active-judge": ("active", False),
                "retired-judge": ("retired", False),
            },
        )
        assert (
            settle_and_publish(
                repo=repo,
                dates=("2026-10-10",),
                run_id="2026-10-11-123",
                commit_sha=git(repo, "rev-parse", "HEAD").strip(),
                config_root=target,
            )
            == 0
        )
        assert on_origin(origin, "state/paper/2026-10-10.json") == "completed\n"
        rows = ledger.load_days(
            repo / "state",
            LedgerName.COUNCIL_RUN_RECORDS,
            ["2026-10-10"],
            model=CouncilRunRecord,
        )
        assert len(rows) == 1 and rows[0].judge_id == "active-judge"
    finally:
        forget(package)


def test_many_tenants_and_later_dates_survive_a_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            "config/push-retry.json": '{"deadline_seconds":{"default":300},"base_step_seconds":0.001,'
            '"ceiling_seconds":0.001,"ceiling_after":1}\n',
        },
    )
    package = "publisher_tenants"
    slugs = ("first", "second-failed", "third")
    a_venue(
        tmp_path,
        package=package,
        slugs={slug: (1, (f"state/experiments/{slug}",)) for slug in slugs},
        source=SOURCE,
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    forget(package)
    try:
        config_root = configuration(tmp_path, slugs)
        set_host_fingerprint_placement(config_root, False)
        with refuse_external_placement():
            assert (
                settle_and_publish(
                    repo=repo,
                    dates=("2026-10-08", "2026-10-09"),
                    run_id="2026-10-09-123",
                    commit_sha=git(repo, "rev-parse", "HEAD").strip(),
                    config_root=config_root,
                    started_at=datetime(2026, 10, 9, 23, 59, tzinfo=UTC),
                    clock=lambda: datetime(2026, 10, 10, 0, 2, tzinfo=UTC),
                )
                == 1
            )
        for slug in slugs:
            for date in ("2026-10-08", "2026-10-09"):
                assert on_origin(origin, f"state/experiments/{slug}/{date}.json") == "completed\n"
        rows = ledger.load_days(
            repo / "state",
            LedgerName.COUNCIL_RUN_RECORDS,
            ["2026-10-08", "2026-10-09"],
            model=CouncilRunRecord,
        )
        assert len(rows) == 6
        assert sum(row.outcome == "failed" and row.fault == "raised" for row in rows) == 1
        assert sum(row.date == "2026-10-09" for row in rows) == 3
        receipts = [
            PublicationReceipt.read(path)
            for path in (repo / "backend" / "var" / "council" / "publication").iterdir()
        ]
        evidence = {path: digest for receipt in receipts for path, digest in receipt.writes.items()}
        machine = {
            path: digest
            for path, digest in evidence.items()
            if path.startswith("state/raw/host-fingerprint/")
        }
        assert len(machine) == 2, "both probe and closing clock must have receipts"
        remote = Repository(origin, git_dir=origin)
        for path in machine:
            entry = remote.entry("main", path)
            assert entry is not None, "a receipted machine write was never pushed"
            assert remote.blob(entry.oid) == (repo / path).read_bytes()
            assert "/2026/10/09/" in path, "machine belongs to opened night, not settled date"
        host_rows = ledger.load_days(
            repo / "state",
            LedgerName.HOST_FINGERPRINT,
            ["2026-10-08", "2026-10-09", "2026-10-10"],
            model=HostFingerprintRow,
        )
        assert len(host_rows) == 1, "many dates and tenants still draw one collecting machine"
        assert host_rows[0].job_seconds == 180
        assert host_rows[0].memcpy_probe_mib == 0
        assert host_rows[0].memcpy_gib_s is None
        assert host_rows[0].job == ServerJob.SAVE_COUNCIL_RESULTS.value
        assert host_rows[0].run_id == "2026-10-09-123"
        assert host_rows[0].measured_at is not None
    finally:
        forget(package)


def test_empty_venue_writes_no_row_or_commit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(tmp_path, {"seed": "seed\n"})
    before = git(origin, "rev-parse", "main")
    assert (
        settle_and_publish(
            repo=repo,
            dates=("2026-10-09",),
            run_id="2026-10-09-123",
            commit_sha=git(repo, "rev-parse", "HEAD").strip(),
            config_root=configuration(tmp_path, ()),
        )
        == 0
    )
    assert git(origin, "rev-parse", "main") == before
    assert not (repo / "state").exists()
