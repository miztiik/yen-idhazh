"""Do selected dates run end to end while paused bytes stay out of the real Git publisher?"""

from __future__ import annotations

import json
import shutil
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR
from gardener._garden import an_origin, git, on_origin, quiet_git

from idhazh import config, ledger
from idhazh.contracts.council_run_record import CouncilRunRecord
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import night_plan, registry, session, trial_paths
from idhazh.council.selection import Selection
from idhazh.ledger import paths
from utilities import council_matrix, council_publish

from ._tenants import forget
from .test_lifecycle import room

PACKAGE = "selected_fixture_judges"
DAY = "2026-10-10"
OLD = "2026-10-09"
RUN = "2026-10-11-123"
JUDGES = ("older-judge", "current-judge", "paused-judge")


@pytest.fixture
def venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", PACKAGE)
    root = tmp_path / PACKAGE
    root.mkdir()
    (root / "__init__.py").write_text("", encoding="ascii", newline="\n")
    for slug in JUDGES:
        package = root / slug.replace("-", "_")
        package.mkdir()
        (package / "__init__.py").write_text("", encoding="ascii", newline="\n")
        shutil.copyfile(FIXTURES_DIR / "council" / "selection_tenant.py", package / "tenant.py")
    forget(PACKAGE)
    yield tmp_path
    forget(PACKAGE)


def planned(target: Path, capsys: pytest.CaptureFixture[str], *args: str) -> Selection:
    assert night_plan.main(["--config-root", str(target), "--tonight", DAY, *args]) == 0
    output = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
    return Selection.model_validate_json(output["selection"])


def execute(
    target: Path,
    repo: Path,
    selected: Selection,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    expected_code: int = 0,
) -> None:
    council = config.load_council(target)
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    monkeypatch.setenv("COUNCIL_SELECTION", selected.model_dump_json())
    assert council_matrix.main(["--config-root", str(target)]) == 0
    output = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
    cells = json.loads(output["matrix"])
    assert set(output["committed_paths"].split()) == set(
        session.publication_paths(council, selection=selected)
    )
    for day in selected.dates:
        session.prepare(council, date=day, run_id=RUN, selection=selected)
    for cell in cells:
        session.run_shard(
            council,
            slug=cell["tenant"],
            date=cell["date"],
            run_id=RUN,
            shard=cell["shard"],
            shards=cell["shards"],
            started=time.monotonic(),
            selection=selected,
        )
    assert (
        council_publish.main(
            [
                "--config-root",
                str(target),
                "--repo-root",
                str(repo),
                "--run-id",
                RUN,
                "--commit",
                git(repo, "rev-parse", "HEAD").strip(),
            ]
        )
        == expected_code
    )


def repository(root: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    quiet_git(root, monkeypatch)
    # A generated bare repository needs an explicit process-only Git permission.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "safe.bareRepository")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "all")
    return an_origin(
        root,
        {
            "seed": "seed\n",
            "config/push-retry.json": '{"deadline_seconds":{"default":300},'
            '"base_step_seconds":0.001,"ceiling_seconds":0.001,"ceiling_after":1}\n',
            **{f"state/experiments/{slug}/seed.json": '{"count":7}\n' for slug in JUDGES},
        },
    )


def test_each_scheduled_judge_prepares_runs_and_settles_only_its_own_dates(
    venue: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    origin, repo = repository(venue, monkeypatch)
    target = room(venue, {"older-judge": ("active", False), "current-judge": ("active", False)})
    selected = planned(target, capsys)
    assert {judge.tenant: judge.dates for judge in selected.judges} == {
        "older-judge": (DAY, OLD),
        "current-judge": (DAY,),
    }
    execute(target, repo, selected, monkeypatch, capsys)
    for slug, days in (("older-judge", (DAY, OLD)), ("current-judge", (DAY,))):
        for day in days:
            content = on_origin(origin, f"state/experiments/{slug}/{day}.json")
            assert content is not None
            assert json.loads(content)["seed"] == {"count": 7}
    assert (
        git(origin, "ls-tree", "-r", "main", "--", f"state/experiments/current-judge/{OLD}.json")
        == ""
    )
    rows = ledger.load_days(
        repo / "state", LedgerName.COUNCIL_RUN_RECORDS, [DAY, OLD], model=CouncilRunRecord
    )
    assert len(rows) == 9
    assert {(row.judge_id, row.date) for row in rows} == {
        ("older-judge", DAY),
        ("older-judge", OLD),
        ("current-judge", DAY),
    }
    assert f"{PACKAGE}.paused_judge.tenant" not in sys.modules


@pytest.mark.parametrize(
    ("active", "paused_family"), [(True, False), (False, False), (False, True)]
)
def test_manual_paused_outputs_and_records_are_downloadable_but_never_published(
    venue: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    active: bool,
    paused_family: bool,
) -> None:
    origin, repo = repository(venue, monkeypatch)
    before = git(origin, "rev-parse", "main")
    target = room(
        venue,
        {
            "older-judge": ("active", False),
            "current-judge": ("active", False),
            "paused-judge": ("paused", False),
        },
    )
    if paused_family:
        registry_file = target / "ledgers.json"
        raw = json.loads(registry_file.read_text(encoding="utf-8"))
        for family in raw["families"]:
            if any(
                entry["name"] == LedgerName.COUNCIL_RUN_RECORDS.value for entry in family["ledgers"]
            ):
                family["lifecycle_status"] = "paused"
        registry_file.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
        monkeypatch.setattr(paths, "_CONFIG", paths._load(target))
    requested = ["older-judge", "paused-judge"] if active else ["paused-judge"]
    selected = planned(
        target, capsys, "--mode", "manual", "--dispatched", OLD, "--judges", json.dumps(requested)
    )
    assert selected.dates == (OLD,)
    execute(target, repo, selected, monkeypatch, capsys)
    trial = trial_paths.root(session.COUNCIL_ROOT, run_id=RUN, judge_id="paused-judge")
    trial_result = trial / "state" / "experiments" / "paused-judge" / f"{OLD}.json"
    assert json.loads(trial_result.read_text(encoding="utf-8"))["seed"] == {"count": 7}
    trial_rows = ledger.load_days(
        trial / "state", LedgerName.COUNCIL_RUN_RECORDS, [OLD], model=CouncilRunRecord
    )
    assert len(trial_rows) == 3 and {row.judge_id for row in trial_rows} == {"paused-judge"}
    assert not (repo / "state" / "experiments" / "paused-judge" / f"{OLD}.json").exists()
    assert (
        git(origin, "ls-tree", "-r", "main", "--", f"state/experiments/paused-judge/{OLD}.json")
        == ""
    )
    assert on_origin(origin, "state/experiments/paused-judge/seed.json") == '{"count":7}\n'
    # The downloaded run root is bounded. No committed archive is enumerated.
    receipts_root = session.COUNCIL_ROOT / "publication"
    receipts = (
        [PublicationReceipt.read(path) for path in receipts_root.iterdir()]
        if receipts_root.exists()
        else []
    )
    assert all("paused-judge" not in path for receipt in receipts for path in receipt.writes)
    remote_records = git(
        origin, "ls-tree", "-r", "--name-only", "main", "--", "state/raw/council-run-records"
    )
    for relative in remote_records.splitlines():
        content = on_origin(origin, relative)
        assert content is not None
        assert "paused-judge" not in content
    if active:
        content = on_origin(origin, f"state/experiments/older-judge/{OLD}.json")
        assert content is not None
        assert json.loads(content)["seed"] == {"count": 7}
        assert receipts
        assert git(origin, "rev-parse", "main") != before
    else:
        assert receipts == []
        assert git(origin, "rev-parse", "main") == before
    assert f"{PACKAGE}.current_judge.tenant" not in sys.modules


def test_failed_paused_input_stays_red_but_later_active_output_lands(
    venue: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    origin, repo = repository(venue, monkeypatch)
    target = room(venue, {"paused-judge": ("paused", False), "older-judge": ("active", False)})
    selected = planned(
        target,
        capsys,
        "--mode",
        "manual",
        "--dispatched",
        OLD,
        "--judges",
        '["paused-judge","older-judge"]',
    )
    root = trial_paths.root(
        repo / "backend" / "var" / "council", run_id=RUN, judge_id="paused-judge"
    )
    foreign = root / "state" / "experiments" / "paused-judge" / "seed.json"
    foreign.parent.mkdir(parents=True)
    foreign.write_text('{"count":99}\n', encoding="ascii", newline="\n")
    execute(target, repo, selected, monkeypatch, capsys, expected_code=1)
    content = on_origin(origin, f"state/experiments/older-judge/{OLD}.json")
    assert content is not None
    assert json.loads(content)["seed"] == {"count": 7}
    assert (
        git(origin, "ls-tree", "-r", "main", "--", f"state/experiments/paused-judge/{OLD}.json")
        == ""
    )
    assert foreign.read_text(encoding="utf-8") == '{"count":99}\n'


@pytest.mark.parametrize("paused_family", [False, True])
@pytest.mark.parametrize("failed_step", ["prepare", "shard", "settle"])
def test_raised_paused_trial_files_failed_rows_without_publication(
    venue: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
    paused_family: bool, failed_step: str,
) -> None:
    origin, repo = repository(venue, monkeypatch)
    before = git(origin, "rev-parse", "main")
    target = room(venue, {"paused-judge": ("paused", False)})
    if paused_family:
        registry_file = target / "ledgers.json"
        raw = json.loads(registry_file.read_text(encoding="utf-8"))
        for family in raw["families"]:
            if any(
                entry["name"] == LedgerName.COUNCIL_RUN_RECORDS.value for entry in family["ledgers"]
            ):
                family["lifecycle_status"] = "paused"
        registry_file.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
        monkeypatch.setattr(paths, "_CONFIG", paths._load(target))
    selected = planned(
        target, capsys, "--mode", "manual", "--dispatched", OLD,
        "--judges", '["paused-judge"]',
    )
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    monkeypatch.setenv("COUNCIL_SELECTION", selected.model_dump_json())
    council = config.load_council(target)
    trial = trial_paths.root(session.COUNCIL_ROOT, run_id=RUN, judge_id="paused-judge")
    with trial_paths.route(trial):
        drawn = session.unit_file(OLD, slot="selection", judge_id="paused-judge", suffix=".json")
        verdict = session.unit_file(OLD, slot="verdicts", judge_id="paused-judge", suffix=".json")
    if failed_step == "prepare":
        drawn.parent.parent.parent.mkdir(parents=True)
        drawn.parent.parent.write_text("blocked selection\n", encoding="ascii", newline="\n")
        with pytest.raises(OSError):
            session.prepare(council, date=OLD, run_id=RUN, selection=selected)
    else:
        session.prepare(council, date=OLD, run_id=RUN, selection=selected)
    if failed_step == "shard":
        drawn.unlink()
    if failed_step in ("prepare", "shard"):
        with pytest.raises(OSError):
            session.run_shard(
                council, slug="paused-judge", date=OLD, run_id=RUN, shard=0, shards=1,
                started=time.monotonic(), selection=selected,
            )
    else:
        session.run_shard(
            council, slug="paused-judge", date=OLD, run_id=RUN, shard=0, shards=1,
            started=time.monotonic(), selection=selected,
        )
        verdict.unlink()
    assert council_publish.main(
        [
            "--config-root", str(target), "--repo-root", str(repo), "--run-id", RUN,
            "--commit", git(repo, "rev-parse", "HEAD").strip(), "--units-result", "failure",
        ]
    ) == 1
    recorded = ledger.load_days(
        trial / "state", LedgerName.COUNCIL_RUN_RECORDS, [OLD], model=CouncilRunRecord,
    )
    assert len(recorded) == 3
    failed_count = {"prepare": 3, "shard": 2, "settle": 1}[failed_step]
    assert sum(row.outcome == "failed" and row.fault == "raised" for row in recorded) == failed_count
    assert sum(row.outcome == "completed" and row.fault is None for row in recorded) == 3 - failed_count
    assert not (session.COUNCIL_ROOT / "publication").exists()
    assert not ledger.load_days(
        repo / "state", LedgerName.COUNCIL_RUN_RECORDS, [OLD], model=CouncilRunRecord,
    )
    assert git(origin, "rev-parse", "main") == before


def test_paused_manual_judge_cannot_reopen_a_retired_family(
    venue: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = room(venue, {"paused-judge": ("paused", False)})
    registry_file = target / "ledgers.json"
    raw = json.loads(registry_file.read_text(encoding="utf-8"))
    for family in raw["families"]:
        if any(
            entry["name"] == LedgerName.COUNCIL_RUN_RECORDS.value for entry in family["ledgers"]
        ):
            family["lifecycle_status"] = "retired"
    registry_file.write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    monkeypatch.setattr(paths, "_CONFIG", paths._load(target))
    assert (
        night_plan.main(
            [
                "--config-root",
                str(target),
                "--mode",
                "manual",
                "--dispatched",
                OLD,
                "--judges",
                '["paused-judge"]',
            ]
        )
        == 2
    )
    assert not (venue / "state").exists()


@pytest.mark.parametrize(
    ("names", "day"),
    [
        ("", OLD),
        ("[]", OLD),
        ('["unknown-judge"]', OLD),
        ('["older-judge","older-judge"]', OLD),
        ('["retired-judge"]', OLD),
        ('["../source-text"]', OLD),
        ("[1]", OLD),
        ('"older-judge"', OLD),
        ('["older-judge"]', ""),
        ('["older-judge"]', "2026-02-30"),
        ('["older-judge"]', f"{OLD},{DAY}"),
    ],
)
def test_invalid_manual_request_refuses_before_import_or_work(
    venue: Path, capsys: pytest.CaptureFixture[str], names: str, day: str
) -> None:
    target = room(venue, {"older-judge": ("active", False), "retired-judge": ("retired", False)})
    assert (
        night_plan.main(
            [
                "--config-root",
                str(target),
                "--mode",
                "manual",
                "--dispatched",
                day,
                "--judges",
                names,
            ]
        )
        == 2
    )
    output = capsys.readouterr()
    assert output.out == ""
    assert "source-text" not in output.err
    assert f"{PACKAGE}.older_judge.tenant" not in sys.modules
    assert f"{PACKAGE}.retired_judge.tenant" not in sys.modules
