"""Does the real collecting publisher retain earlier and later completed tenant work?"""

import json
from pathlib import Path

import pytest
from gardener._garden import an_origin, git, on_origin, quiet_git

from idhazh import ledger
from idhazh.contracts.council_run_record import CouncilRunRecord
from idhazh.contracts.ledger_name import LedgerName
from idhazh.council import registry, session
from utilities.council_publish import settle_and_publish

from ._config import copy_config
from ._tenants import TENANT_SOURCE, a_venue, forget

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
    path = target / "idhazh.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["council"]["tenants"] = list(slugs)
    path.write_text(json.dumps(data), encoding="utf-8", newline="\n")
    return target


def test_many_tenants_and_later_dates_survive_a_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    quiet_git(tmp_path, monkeypatch)
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            "config/push-retry.json":             '{"deadline_seconds":{"default":300},"base_step_seconds":0.001,'
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
        assert (
            settle_and_publish(
                repo=repo,
                dates=("2026-10-08", "2026-10-09"),
                run_id="2026-10-09-123",
                commit_sha=git(repo, "rev-parse", "HEAD").strip(),
                config_root=configuration(tmp_path, slugs),
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
        assert len(rows) == 5
        assert sum(row.date == "2026-10-09" for row in rows) == 3
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
