"""Do selected dates run end to end while paused bytes stay out of the real Git publisher?"""

from __future__ import annotations

import json
import shutil
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from gardener._garden import an_origin, git, on_origin, quiet_git
from support.paths import FIXTURES_DIR

from idhazh import config, ledger
from idhazh.contracts.council_events import CouncilProgram
from idhazh.contracts.council_invocation import Cell
from idhazh.contracts.council_run_record import CouncilRunRecord
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import night_plan, outcome, registry, session, trial_paths, work_files
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
    assert (
        night_plan.main(
            [
                "--config-root",
                str(target),
                "--tonight",
                DAY,
                "--run-id",
                RUN,
                "--commit",
                "a" * 40,
                *args,
            ]
        )
        == 0
    )
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
    selected = selected.model_copy(update={"git_sha": git(repo, "rev-parse", "HEAD").strip()})
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    monkeypatch.setenv("COUNCIL_SELECTION", selected.model_dump_json())
    monkeypatch.setenv("COUNCIL_EVENT_FILE", str(session.COUNCIL_ROOT / "events" / "planner.jsonl"))
    assert (
        outcome.run(
            CouncilProgram.PREPARE,
            lambda: outcome.of_results(session.prepare(council, run_id=RUN, selection=selected)),
        )
        == 0
    )
    capsys.readouterr()
    assert council_matrix.main(["--config-root", str(target)]) == 0
    output = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
    cells = json.loads(output["matrix"])
    assert set(output["committed_paths"].split()) == set(
        session.publication_paths(council, selection=selected)
    )
    for cell in cells:
        monkeypatch.setenv(
            "COUNCIL_EVENT_FILE",
            str(
                session.COUNCIL_ROOT
                / "events"
                / cell["tenant"]
                / cell["date"]
                / f"{cell['shard']}.jsonl",
            ),
        )
        authorized_cell = Cell.model_validate(cell)

        def run_cell(cell: Cell = authorized_cell) -> int:
            return outcome.of_results(
                (
                    session.run_shard(
                        council,
                        slug=cell.tenant,
                        date=cell.date,
                        run_id=RUN,
                        shard=cell.shard,
                        shards=cell.shards,
                        started=time.monotonic(),
                        selection=selected,
                    ),
                )
            )

        assert outcome.run(CouncilProgram.SHARD, run_cell) == 0
    monkeypatch.delenv("COUNCIL_EVENT_FILE")
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
                "--matrix",
                output["matrix"],
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
    receipts = [PublicationReceipt.read(receipts_root / "0000.json")] if active else []
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
    venue: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    paused_family: bool,
    failed_step: str,
) -> None:
    origin, repo = repository(venue, monkeypatch)
    before = git(origin, "rev-parse", "main")
    target = room(venue, {"paused-judge": ("paused", False)})
    method = "run_shard" if failed_step == "shard" else failed_step
    source = INDEPENDENT_SOURCE.format(slug="paused-judge")
    signature = next(line for line in source.splitlines() if line.startswith(f"    def {method}("))
    source = source.replace(signature, signature + '\n        raise RuntimeError("unit failed")')
    (venue / PACKAGE / "paused_judge" / "tenant.py").write_text(source, encoding="ascii")
    forget(PACKAGE)
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
        target,
        capsys,
        "--mode",
        "manual",
        "--dispatched",
        OLD,
        "--judges",
        '["paused-judge"]',
    )
    selected = selected.model_copy(update={"git_sha": git(repo, "rev-parse", "HEAD").strip()})
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    monkeypatch.setenv("COUNCIL_SELECTION", selected.model_dump_json())
    council = config.load_council(target)
    trial = trial_paths.root(session.COUNCIL_ROOT, run_id=RUN, judge_id="paused-judge")
    results = session.prepare(council, date=OLD, run_id=RUN, selection=selected)
    if failed_step == "prepare":
        assert outcome.of_results(results) == 1
    elif failed_step == "shard":
        with pytest.raises(RuntimeError):
            session.run_shard(
                council,
                slug="paused-judge",
                date=OLD,
                run_id=RUN,
                shard=0,
                shards=1,
                started=time.monotonic(),
                selection=selected,
            )
    else:
        session.run_shard(
            council,
            slug="paused-judge",
            date=OLD,
            run_id=RUN,
            shard=0,
            shards=1,
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
                "--units-result",
                "failure",
            ]
        )
        == 1
    )
    recorded = ledger.load_days(
        trial / "state",
        LedgerName.COUNCIL_RUN_RECORDS,
        [OLD],
        model=CouncilRunRecord,
    )
    expected_count = 1 if failed_step == "prepare" else 3
    assert len(recorded) == expected_count
    failed_count = {"prepare": 1, "shard": 2, "settle": 1}[failed_step]
    assert (
        sum(row.outcome == "failed" and row.fault == "raised" for row in recorded) == failed_count
    )
    assert (
        sum(row.outcome == "completed" and row.fault is None for row in recorded)
        == expected_count - failed_count
    )
    assert not (session.COUNCIL_ROOT / "publication").exists()
    assert not ledger.load_days(
        repo / "state",
        LedgerName.COUNCIL_RUN_RECORDS,
        [OLD],
        model=CouncilRunRecord,
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
                "--run-id",
                RUN,
                "--commit",
                "a" * 40,
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
                "--run-id",
                RUN,
                "--commit",
                "a" * 40,
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


INDEPENDENT_SOURCE = '''
"""Process only the opaque JSON task this plugin prepared."""
import json
from pathlib import Path
from idhazh import atomic_write
from idhazh.contracts.council_invocation import JudgeSchedule
from idhazh.contracts.council_run_record import ShardOutcome
from idhazh.council import session
from idhazh.council.tenancy import ShardResult

class FilePlugin:
    judge_id = "{slug}"
    shard_count = 1
    committed_paths = ("state/experiments/{slug}",)

    def schedule(self, *, request):
        if self.judge_id == "declining-judge":
            return JudgeSchedule(dates=())
        dates = (request.anchor_date,)
        if self.judge_id == "failing-judge":
            dates += ("2026-10-09",)
        return JudgeSchedule(dates=dates)

    def publication_inputs(self, *, date):
        return ()

    def prepare(self, *, date, run_id, shards):
        if self.judge_id == "failing-judge" and date == "2026-10-10":
            raise RuntimeError("private source text must not escape")
        task = session.unit_file(date, slot="work-items", judge_id=self.judge_id, suffix=".json")
        empty = self.judge_id == "empty-judge"
        atomic_write.write_atomic(task, json.dumps([] if empty else [date]))
        return ShardResult(
            outcome=ShardOutcome.NOTHING_TO_DO if empty else ShardOutcome.COMPLETED,
            files=(session.artifact_path(task),),
        )

    def run_shard(self, *, date, run_id, shard, shards, deadline, prepared):
        task = session.unit_file(date, slot="work-items", judge_id=self.judge_id, suffix=".json")
        values = json.loads(task.read_text(encoding="utf-8"))
        output = session.unit_file(
            date, slot="processed", judge_id=self.judge_id, shard=shard, suffix=".json",
        )
        atomic_write.write_atomic(output, json.dumps([value.upper() for value in values]))
        return ShardResult(outcome=ShardOutcome.COMPLETED, files=(session.artifact_path(output),))

    def settle(self, *, date, run_id, state_dir, identity, prepared, reports):
        if prepared.state == "no_work":
            if reports:
                raise ValueError("empty work cannot have shard reports")
            value = []
        else:
            if len(reports) != prepared.shards or any(
                report.report_state != "reported" or report.outcome != ShardOutcome.COMPLETED
                or report.code != 0 for report in reports
            ):
                raise ValueError("not all parts completed")
            output = session.unit_file(
                date, slot="processed", judge_id=self.judge_id, shard=0, suffix=".json",
            )
            value = json.loads(output.read_text(encoding="utf-8"))
        atomic_write.write_atomic(
            state_dir / "experiments" / self.judge_id / (date + ".json"), json.dumps(value),
        )
        return ShardResult(outcome=ShardOutcome.COMPLETED)

TENANT = FilePlugin()
'''


def _deliver_document(
    source: Path,
    target: Path,
    selected: Selection,
    document: object,
    *,
    event: str,
) -> None:
    from idhazh.contracts.council_invocation import PreparationReceipt, ShardFiles

    assert isinstance(document, (PreparationReceipt, ShardFiles))
    base = work_files.invocation_root(source, selected, document.judge_id)
    shard = document.shard if isinstance(document, ShardFiles) else None
    manifest = (
        work_files.preparation_path(source, selected, document.judge_id, document.date)
        if shard is None
        else work_files.shard_path(
            source,
            selected,
            document.judge_id,
            document.date,
            shard,
        )
    )
    named = [
        manifest,
        *(base / file.path for file in document.files),
        work_files.record_path(source, selected, document.judge_id, document.date, shard),
    ]
    for path in named:
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    event_source = source / "events" / event
    destination = target / "events" / event
    destination.parent.mkdir(parents=True, exist_ok=True)
    if not destination.exists():
        shutil.copyfile(event_source, destination)


@pytest.mark.parametrize(
    ("raised", "kind"),
    [
        ("raise KeyboardInterrupt()", KeyboardInterrupt),
        ("raise TimeoutError()", TimeoutError),
        (
            'raise ExceptionGroup("failed recording", [ValueError(), FileIntegrityError()])',
            ExceptionGroup,
        ),
    ],
)
def test_fatal_preparation_does_not_finish_or_admit_a_failed_receipt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    raised: str,
    kind: type[BaseException],
) -> None:
    from ._tenants import a_venue

    package = "fatal_file_plugins"
    source = INDEPENDENT_SOURCE.replace(
        "    def prepare(self, *, date, run_id, shards):",
        "    def prepare(self, *, date, run_id, shards):\n        " + raised,
    ).replace(
        "from idhazh.council import session",
        "from idhazh.council import session\nfrom idhazh.council.work_files import FileIntegrityError",
    )
    a_venue(tmp_path, package=package, slugs={"one-judge": (1, ())}, source=source)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "council")
    target = room(tmp_path, {"one-judge": ("active", False)})
    council = config.load_council(target)
    selected = Selection.model_validate(
        {
            "run_id": RUN,
            "attempt": 1,
            "git_sha": "a" * 40,
            "mode": "manual",
            "anchor_date": DAY,
            "window": (DAY,),
            "judges": ({"tenant": "one-judge", "status": "active", "dates": (DAY,), "shards": 1},),
        }
    )
    forget(package)
    try:
        with pytest.raises(kind):
            session.prepare(council, run_id=RUN, selection=selected)
        assert "preparation_finished=true" not in capsys.readouterr().out
        assert work_files.read_preparation(session.COUNCIL_ROOT, selected, "one-judge", DAY) is None
        assert work_files.record_path(
            session.COUNCIL_ROOT, selected, "one-judge", DAY, None
        ).is_file()
    finally:
        forget(package)


def test_matrix_date_arguments_cannot_override_the_selection(tmp_path: Path) -> None:
    target = room(tmp_path, {"one-judge": ("active", False)})
    selected = Selection.model_validate(
        {
            "run_id": RUN,
            "attempt": 1,
            "git_sha": "a" * 40,
            "mode": "manual",
            "anchor_date": DAY,
            "window": (DAY,),
            "judges": ({"tenant": "one-judge", "status": "active", "dates": (DAY,), "shards": 1},),
        }
    )
    with pytest.raises(ValueError, match="matrix dates"):
        council_matrix.cells(target, dates=(OLD,), selection=selected)


def test_preparation_isolated_by_judge_and_date_and_only_ready_work_runs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reverting per-cell preparation isolation loses the independently completed remote writes."""
    from idhazh.contracts.council_invocation import ShardFiles

    from ._tenants import a_venue

    names = ("declining-judge", "failing-judge", "empty-judge", "unrelated-judge")
    package = "independent_file_plugins"
    a_venue(
        tmp_path,
        package=package,
        slugs={name: (1, (f"state/experiments/{name}",)) for name in names},
        source=INDEPENDENT_SOURCE,
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    forget(package)
    origin, repo = repository(tmp_path, monkeypatch)
    sha = git(repo, "rev-parse", "HEAD").strip()
    target = room(tmp_path, dict.fromkeys(names, ("active", False)))
    council = config.load_council(target)
    selected = night_plan.plan_the_night(
        council,
        tonight=DAY,
        hosted=registry.tenants(names, council=council),
        run_id=RUN,
        attempt=1,
        git_sha=sha,
    )
    assert selected.judges[0].dates == ()
    planner = tmp_path / "planner"
    monkeypatch.setattr(session, "COUNCIL_ROOT", planner)
    monkeypatch.setenv(
        "COUNCIL_EVENT_FILE", str(planner / "outgoing" / "planner" / "events" / "planner.jsonl")
    )
    assert (
        outcome.run(
            CouncilProgram.PREPARE,
            lambda: outcome.of_results(session.prepare(council, run_id=RUN, selection=selected)),
        )
        == 1
    )
    assert "preparation_finished=true" in capsys.readouterr().out
    receipts = {
        (judge.tenant, day): work_files.read_preparation(planner, selected, judge.tenant, day)
        for judge in selected.judges
        for day in judge.dates
    }
    assert {key: receipt.state for key, receipt in receipts.items() if receipt is not None} == {
        ("failing-judge", DAY): "failed",
        ("failing-judge", OLD): "ready",
        ("empty-judge", DAY): "no_work",
        ("unrelated-judge", DAY): "ready",
    }
    empty = receipts[("empty-judge", DAY)]
    assert empty is not None and empty.shards == 0 and len(empty.files) == 1
    matrix = council_matrix.cells(target, selection=selected)
    assert {(cell["tenant"], cell["date"], cell["shard"]) for cell in matrix} == {
        ("failing-judge", OLD, 0),
        ("unrelated-judge", DAY, 0),
    }
    planner_bundle = planner / "outgoing" / "planner"
    collector = repo / "backend" / "var" / "council"
    incoming_plan = collector / "incoming" / f"council-selection-{DAY}"
    for receipt in receipts.values():
        assert receipt is not None
        _deliver_document(planner_bundle, incoming_plan, selected, receipt, event="planner.jsonl")
    for cell in matrix:
        name, day = str(cell["tenant"]), str(cell["date"])
        worker = tmp_path / f"worker-{name}-{day}"
        monkeypatch.setattr(session, "COUNCIL_ROOT", worker)
        work_files.import_preparation(worker, planner_bundle, selected, name, day)
        event = f"{name}/{day}/0.jsonl"
        bundle = worker / "outgoing" / f"shard-{name}-{day}-0"
        monkeypatch.setenv("COUNCIL_EVENT_FILE", str(bundle / "events" / event))

        def run_worker(name: str = name, day: str = day) -> int:
            return outcome.of_results(
                (
                    session.run_shard(
                        council,
                        slug=name,
                        date=day,
                        run_id=RUN,
                        shard=0,
                        shards=1,
                        started=time.monotonic(),
                        selection=selected,
                    ),
                )
            )

        assert outcome.run(CouncilProgram.SHARD, run_worker) == 0
        document = ShardFiles.read(work_files.shard_path(worker, selected, name, day, 0))
        _deliver_document(
            bundle,
            collector / "incoming" / f"council-metrics-{name}-{day}-0",
            selected,
            document,
            event=event,
        )
    monkeypatch.setattr(session, "COUNCIL_ROOT", collector)
    monkeypatch.setenv("COUNCIL_SELECTION", selected.to_json())
    monkeypatch.delenv("COUNCIL_EVENT_FILE")
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
                sha,
                "--planning-result",
                "failure",
                "--matrix",
                json.dumps(matrix),
            ]
        )
        == 1
    )
    assert json.loads(
        on_origin(origin, f"state/experiments/failing-judge/{OLD}.json") or "null"
    ) == [OLD]
    assert json.loads(
        on_origin(origin, f"state/experiments/unrelated-judge/{DAY}.json") or "null"
    ) == [DAY]
    assert (
        json.loads(on_origin(origin, f"state/experiments/empty-judge/{DAY}.json") or "null") == []
    )
    assert on_origin(origin, f"state/experiments/failing-judge/{DAY}.json") is None
    assert not work_files.shard_path(collector, selected, "empty-judge", DAY, 0).exists()
    rows = ledger.load_days(
        repo / "state",
        LedgerName.COUNCIL_RUN_RECORDS,
        (DAY, OLD),
        model=CouncilRunRecord,
    )
    assert not any(
        row.judge_id == "empty-judge" and row.evaluation_step == "evaluate_work_part"
        for row in rows
    )
    assert any(
        row.judge_id == "failing-judge"
        and row.date == DAY
        and row.work_part_count == 0
        and row.outcome == "failed"
        for row in rows
    )
    forget(package)
