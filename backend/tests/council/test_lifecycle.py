"""Does every scheduled council step reach only active judges from written declarations?"""

import json
import shutil
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import CONFIG_DIR

from idhazh import config, ledger
from idhazh.contracts.council_run_record import CouncilRunRecord
from idhazh.contracts.ledger_name import LedgerName
from idhazh.council import night_plan, registry, session
from idhazh.ledger import paths, staging
from utilities import council_matrix
from utilities.council_publish import settle_and_publish

from ._config import copy_config
from ._tenants import a_venue, forget, written

PACKAGE = "lifecycle_tenants"
DATE = "2026-10-10"
RUN = "2026-10-11-123"
SHA = "a" * 40


def room(root: Path, declarations: dict[str, tuple[str, bool]]) -> Path:
    """Write a registered room, including unavailable judges' declarations."""
    target = copy_config(root)
    shutil.copyfile(CONFIG_DIR / "ledgers.json", target / "ledgers.json")
    path = target / "llm_council.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["judge_names"] = list(declarations)
    path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    (target / "judges").mkdir(exist_ok=True)
    for name, (status, model) in declarations.items():
        (target / "judges" / f"{name}.json").write_text(
            json.dumps({"lifecycle_status": status, "runs_model": model, "private": "unvalidated"}),
            encoding="utf-8",
            newline="\n",
        )
    return target


@pytest.fixture
def venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", PACKAGE)
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "scratch")
    forget(PACKAGE)
    yield tmp_path
    forget(PACKAGE)


@pytest.mark.parametrize("runs_model", [True, False])
def test_only_active_judges_get_cells_work_and_publication_paths(
    venue: Path, capsys: pytest.CaptureFixture[str], runs_model: bool
) -> None:
    a_venue(
        venue,
        package=PACKAGE,
        slugs={"active-judge": (2, ("state/paper",))},
        poisoned_neighbour="paused-judge",
    )
    target = room(
        venue,
        {
            "paused-judge": ("paused", True),
            "active-judge": ("active", runs_model),
            "retired-judge": ("retired", False),
        },
    )
    council = config.load_council(target)
    assert night_plan.main(["--config-root", str(target), "--tonight", DATE]) == 0
    assert json.loads(capsys.readouterr().out.split("=", 1)[1])[0] == DATE
    cells = council_matrix.cells(target, dates=(DATE,))
    assert cells == [
        {
            "tenant": "active-judge",
            "date": DATE,
            "shard": shard,
            "shards": 2,
            "runs_model": runs_model,
        }
        for shard in range(2)
    ]
    assert council_matrix.committed_paths(target) == (
        *(staging.staged_path(which) for which in session.VENUE_LEDGERS),
        "state/paper",
    )
    assert len(session.prepare(council, date=DATE, run_id=RUN)) == 1
    for cell in cells:
        session.run_shard(
            council,
            slug=str(cell["tenant"]),
            date=DATE,
            run_id=RUN,
            shard=int(str(cell["shard"])),
            shards=2,
            started=time.monotonic(),
        )
    assert (
        len(
            session.settle(
                council, date=DATE, run_id=RUN, state_dir=venue / "state", commit_sha=SHA
            )
        )
        == 1
    )
    host = written(PACKAGE, "active-judge").TENANT
    assert host.prepared == [DATE] and host.settled == [DATE]
    assert len(host.ran) == 2
    rows = ledger.load_days(
        venue / "state", LedgerName.COUNCIL_RUN_RECORDS, [DATE], model=CouncilRunRecord
    )
    assert len(rows) == 4 and {row.judge_id for row in rows} == {"active-judge"}
    assert f"{PACKAGE}.paused_judge.tenant" not in sys.modules
    assert f"{PACKAGE}.retired_judge.tenant" not in sys.modules
    for inactive in ("paused-judge", "retired-judge", "unregistered-judge"):
        with pytest.raises(ValueError, match=inactive):
            session.run_shard(
                council,
                slug=inactive,
                date=DATE,
                run_id=RUN,
                shard=0,
                shards=1,
                started=time.monotonic(),
            )


@pytest.mark.parametrize("status", ["paused", "retired"])
def test_an_inactive_only_room_runs_every_step_without_import_or_output(
    venue: Path, capsys: pytest.CaptureFixture[str], status: str
) -> None:
    a_venue(venue, package=PACKAGE, slugs={}, poisoned_neighbour="unavailable-judge")
    target = room(venue, {"unavailable-judge": (status, True)})
    council = config.load_council(target)
    assert night_plan.main(["--config-root", str(target), "--tonight", DATE]) == 0
    assert json.loads(capsys.readouterr().out.split("=", 1)[1]) == [DATE]
    assert council_matrix.cells(target, dates=(DATE,)) == []
    assert council_matrix.committed_paths(target) == ()
    assert session.prepare(council, date=DATE, run_id=RUN) == ()
    assert (
        session.settle(council, date=DATE, run_id=RUN, state_dir=venue / "state", commit_sha=SHA)
        == ()
    )
    assert (
        settle_and_publish(
            repo=venue / "not-a-git-repository",
            dates=(DATE,),
            run_id=RUN,
            commit_sha=SHA,
            config_root=target,
        )
        == 0
    )
    assert not (venue / "state").exists()
    assert not (venue / "scratch").exists()
    assert f"{PACKAGE}.unavailable_judge.tenant" not in sys.modules


@pytest.mark.parametrize("status", ["paused", "retired"])
@pytest.mark.parametrize("tier", ["raw", "compact"])
@pytest.mark.parametrize(
    "which", [LedgerName.CONTENT_SIMILARITY_JUDGE_SCORED_PAIRS, LedgerName.COUNCIL_RUN_RECORDS]
)
def test_any_inactive_committed_family_refuses_the_active_judge_by_name(
    venue: Path, monkeypatch: pytest.MonkeyPatch, status: str, tier: str, which: LedgerName
) -> None:
    scope = (
        staging.staged_path(which)
        if tier == "raw"
        else paths.compact_folder(Path("state"), which).as_posix()
    )
    a_venue(venue, package=PACKAGE, slugs={"active-judge": (1, (scope,))})
    target = room(venue, {"active-judge": ("active", False)})
    registry_file = target / "ledgers.json"
    raw = json.loads(registry_file.read_text(encoding="utf-8"))
    family_name = ""
    for family in raw["families"]:
        if any(entry["name"] == which.value for entry in family["ledgers"]):
            family["lifecycle_status"] = status
            family_name = family["name"]
    registry_file.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    monkeypatch.setattr(paths, "_CONFIG", paths._load(target))
    with pytest.raises(ValueError) as refused:
        council_matrix.cells(target, dates=(DATE,))
    assert all(
        word in str(refused.value) for word in ("active-judge", which.value, family_name, status)
    )


@pytest.mark.parametrize(
    "raw",
    [
        {"runs_model": True},
        {"lifecycle_status": "active"},
        {"lifecycle_status": "unknown", "runs_model": False},
        {"lifecycle_status": "paused", "runs_model": "false"},
    ],
)
def test_a_bad_declaration_is_refused_by_name(tmp_path: Path, raw: dict[str, object]) -> None:
    target = room(tmp_path, {"declared-judge": ("paused", False)})
    (target / "judges" / "declared-judge.json").write_text(
        json.dumps(raw), encoding="utf-8", newline="\n"
    )
    with pytest.raises(ValueError, match="declared-judge"):
        config.load_council(target)


def test_registration_order_is_preserved_and_a_duplicate_is_refused(tmp_path: Path) -> None:
    target = room(
        tmp_path,
        {
            "second-judge": ("active", False),
            "paused-judge": ("paused", True),
            "first-judge": ("active", True),
        },
    )
    council = config.load_council(target)
    assert council.running() == ("second-judge", "first-judge")
    path = target / "llm_council.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["judge_names"].append("second-judge")
    path.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    with pytest.raises(ValueError, match="second-judge"):
        config.load_council(target)
