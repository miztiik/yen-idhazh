"""What does each mode of the command parse, print and exit with?"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from conftest import REPO_ROOT, SEED_COMMIT

from idhazh import config, ledger
from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import Period
from idhazh.contracts.ledger_name import LedgerName
from utilities import migrate_to_parquet as command
from utilities.ledger_migration import (
    csv_files,
    path_labels,
    phases,
)
from utilities.ledger_migration.packing import packs_here

from ._fixtures import (
    EVALS,
    HOST,
    ITEM,
    MONTH_ARGS,
    MONTHS,
    NEW,
    OLD,
    ON_CSV,
    RUN,
    ByKey,
    clock_row,
    config_beside,
    feed_row,
    file_hashes,
    item_row,
    plan_named_roots,
    probe_row,
    read_back,
    registry_back_on_csv,
    run_migration,
    todays_reader,
    write_csv,
    writer_file_name,
)

pytestmark = pytest.mark.contract


def test_check_says_whether_a_csv_is_left_and_writes_nothing(tmp_path: Path) -> None:
    state = tmp_path / "state"
    write_csv(
        state,
        ITEM,
        NEW,
        writer_file_name(NEW, 1, ServerJob.ASSEMBLE),
        [item_row(NEW, "ai-03", machine=False).csv_row()],
    )
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT, "--check"]
    before = file_hashes(tmp_path)

    assert command.main([*MONTH_ARGS, *argv]) == command.EXIT_NOT_PROVEN
    assert command.main([*MONTH_ARGS, *[*argv, "--ledger", EVALS.value]]) == command.EXIT_MIGRATED
    assert file_hashes(tmp_path) == before, "a check writes nothing"
    run_migration(state, ITEM)
    assert command.main([*MONTH_ARGS, *argv]) == command.EXIT_MIGRATED


def test_check_reads_moved_ledgers_unless_named(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """With no `--ledger`, a check reads the table ledgers the registry files through the door.

    A ledger still on CSV writes a CSV file on every run, so a check that read
    it unasked could never pass: handed a registry entry that files one ledger
    the way it was filed before it moved, the check leaves that ledger's file
    alone. Named, it is read, and `--ledger` repeats.
    """
    state = tmp_path / "state"
    feed = write_csv(state, ON_CSV, OLD, writer_file_name(OLD, 1, ServerJob.PLAN), [feed_row(OLD).csv_row()])
    argv = ["--state-dir", str(state), "--run-id", RUN, "--git-sha", SEED_COMMIT, "--check"]

    assert command.main([*MONTH_ARGS, *argv]) == command.EXIT_NOT_PROVEN
    assert capsys.readouterr().out.splitlines() == [
        f"{path_labels.label_path(feed)} is still a CSV",
        "1 CSV file(s) left",
    ]

    with monkeypatch.context() as patched:
        held_back = registry_back_on_csv(config_beside(state), ON_CSV)
        patched.setattr(config, "DEFAULT_CONFIG_DIR", held_back)
        assert command.main([*MONTH_ARGS, *argv]) == command.EXIT_MIGRATED
    assert capsys.readouterr().out.splitlines() == ["0 CSV file(s) left"]

    item = write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [item_row(OLD, "ai-01", machine=True).csv_row()],
    )
    named = [*argv, "--ledger", ITEM.value, "--ledger", ON_CSV.value]

    assert command.main([*MONTH_ARGS, *named]) == command.EXIT_NOT_PROVEN
    assert capsys.readouterr().out.splitlines() == [
        f"{path_labels.label_path(item)} is still a CSV",
        f"{path_labels.label_path(feed)} is still a CSV",
        "2 CSV file(s) left",
    ]


def test_cli_migrates_each_repeated_trial_root_raw_only(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state = tmp_path / "state"
    trials = [
        state / "pipeline-tests",
        state / "pipeline-tests-no-visual-plan",
        state / "pipeline-tests-production-settings",
    ]
    source_files: dict[Path, tuple[Path, LedgerName, str]] = {}
    wanted: dict[tuple[Path, LedgerName], dict[str, ByKey]] = {}
    for number, trial in enumerate(trials):
        day = OLD if number < 2 else NEW
        item = item_row(day, f"ai-{number + 1:02d}", machine=True)
        host = [probe_row(day).csv_row(), clock_row(day).csv_row()]
        for which, rows in ((ITEM, [item.csv_row()]), (HOST, host)):
            path = write_csv(trial, which, day, writer_file_name(day, 1, ServerJob.WORK), rows)
            source_files[path] = (trial, which, day)
            wanted[trial, which] = todays_reader(trial, which)
    args = [part for trial in trials for part in ("--state-dir", str(trial))]
    args.extend(
        [
            *MONTH_ARGS,
            "--run-id",
            RUN,
            "--git-sha",
            SEED_COMMIT,
            "--ledger",
            ITEM.value,
            "--ledger",
            HOST.value,
        ]
    )

    assert command.main([*MONTH_ARGS, *args]) == command.EXIT_MIGRATED
    output = capsys.readouterr().out
    assert output.count(": raw only") == len(trials)
    for path, (trial, which, day) in source_files.items():
        assert not path.exists()
        assert read_back(trial, which, day) == wanted[trial, which][day]
        assert not ledger.compact_index_path(trial, which, Period.DAILY).exists()
    check = [*args, "--check"]
    assert command.main([*MONTH_ARGS, *check]) == command.EXIT_MIGRATED


@pytest.mark.parametrize(
    "phase",
    [[], ["--plan"], ["--check"], ["--verify"], ["--retire"]],
    ids=["no-write", "plan", "check", "verify", "retire"],
)
def test_raw_only_requires_explicit_write_before_any_file_changes(
    tmp_path: Path, phase: list[str]
) -> None:
    args = [
        *MONTH_ARGS,
        "--state-dir",
        str(tmp_path),
        "--ledger",
        ITEM.value,
        "--run-id",
        RUN,
        "--git-sha",
        SEED_COMMIT,
        *phase,
        "--raw-only",
    ]
    before = file_hashes(tmp_path)
    with pytest.raises(SystemExit) as refused:
        command.main(args)
    assert refused.value.code == 2
    assert file_hashes(tmp_path) == before


def test_production_raw_only_write_leaves_csv_and_compact_bytes_unchanged(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    state = tmp_path / "state"
    config_dir = config_beside(state)
    monkeypatch.setattr(config, "DEFAULT_CONFIG_DIR", config_dir)
    assert packs_here(state, config_dir)
    args = [
        *MONTH_ARGS,
        "--state-dir",
        str(state),
        "--ledger",
        ITEM.value,
        "--run-id",
        RUN,
        "--git-sha",
        SEED_COMMIT,
    ]
    first = item_row(OLD, "ai-01", machine=True)
    write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 1, ServerJob.WORK),
        [first.csv_row()],
    )
    assert command.main(args) == command.EXIT_MIGRATED
    capsys.readouterr()

    late = item_row(OLD, "ai-02", machine=True)
    source = write_csv(
        state,
        ITEM,
        OLD,
        writer_file_name(OLD, 2, ServerJob.WORK),
        [late.csv_row()],
    )
    csv_before = {path: path.read_bytes() for path in csv_files.left(state, [ITEM], months=MONTHS)}
    compact_before = file_hashes(state / "compact")
    assert compact_before, "the production-root setup must have compact output to protect"

    assert command.main([*args, "--write", "--raw-only"]) == command.EXIT_MIGRATED
    output = capsys.readouterr().out

    assert "raw-only write complete" in output
    assert "packing and parity proof outstanding" in output
    assert source.exists()
    assert {path: path.read_bytes() for path in csv_files.left(state, [ITEM], months=MONTHS)} == csv_before
    assert file_hashes(state / "compact") == compact_before


@pytest.mark.parametrize("mode", ["--check", "--plan", "--write", "--verify", "--retire", None])
def test_every_mode_refuses_a_missing_root(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], mode: str | None
) -> None:
    root = tmp_path / "mistyped-root"
    args = [
        *MONTH_ARGS, "--state-dir", str(root), "--ledger", HOST.value,
        "--run-id", RUN, "--git-sha", SEED_COMMIT,
    ]
    assert command.main(args + ([mode] if mode else [])) == 1
    message = capsys.readouterr().err
    assert f"{path_labels.label_path(root)}: not an existing directory" in message
    assert not root.exists()


def test_script_execution_catches_the_same_phase_refusal_class(tmp_path: Path) -> None:
    root = tmp_path / "trial"
    row = item_row(OLD, "ai-01", machine=True)
    write_csv(root, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [row.csv_row()])
    result = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "backend" / "utilities" / "migrate_to_parquet.py"),
            *MONTH_ARGS,
            "--state-dir",
            str(root),
            "--ledger",
            ITEM.value,
            "--run-id",
            RUN,
            "--git-sha",
            SEED_COMMIT,
            "--verify",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == command.EXIT_NOT_PROVEN
    assert "not proven, nothing deleted" in result.stderr
    assert "Traceback" not in result.stderr


def test_a_two_root_verify_refusal_names_the_bad_root_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    roots = [tmp_path / "good", tmp_path / "bad"]
    row = item_row(OLD, "ai-01", machine=True)
    for root in roots:
        write_csv(root, ITEM, OLD, writer_file_name(OLD, 1, ServerJob.WORK), [row.csv_row()])
    phases.write_roots(plan_named_roots(roots, ITEM))
    (file,) = ledger.read_day_files(roots[-1], ITEM, OLD)
    file.path.unlink()
    args = [
        *MONTH_ARGS,
        "--ledger",
        ITEM.value,
        "--run-id",
        RUN,
        "--git-sha",
        SEED_COMMIT,
        "--verify",
    ]
    for root in roots:
        args.extend(["--state-dir", str(root)])
    assert command.main(args) == command.EXIT_NOT_PROVEN
    output = capsys.readouterr()
    label = path_labels.label_path(roots[-1])
    assert f"{label}: {ITEM.value} {OLD}: migrated output is missing" in output.err
    assert output.err.count(f"{ITEM.value} {OLD}") == 1
    for root in roots:
        assert output.out.count(f"{path_labels.label_path(root)}: raw only") == 1
    assert "\\" not in output.out + output.err


@pytest.mark.parametrize("mode", ["--plan", "--write", "--verify", "--retire"])
def test_phase_modes_are_mutually_exclusive_with_each_other_and_check(
    tmp_path: Path, mode: str
) -> None:
    args = [
        *MONTH_ARGS,
        "--state-dir",
        str(tmp_path),
        "--ledger",
        ITEM.value,
        "--run-id",
        RUN,
        "--git-sha",
        SEED_COMMIT,
    ]
    for other in ("--plan", "--write", "--verify", "--retire", "--check"):
        if other == mode:
            continue
        with pytest.raises(SystemExit) as refusal:
            command.main([*args, mode, other])
        assert refusal.value.code == 2


def test_cli_phases_preview_write_verify_and_retire(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    root = tmp_path / "trial"
    row = item_row(NEW, "ai-01", machine=True)
    source = write_csv(root, ITEM, NEW, writer_file_name(NEW, 1, ServerJob.WORK), [row.csv_row()])
    args = [
        *MONTH_ARGS,
        "--state-dir",
        str(root),
        "--ledger",
        ITEM.value,
        "--run-id",
        RUN,
        "--git-sha",
        SEED_COMMIT,
    ]
    before = file_hashes(tmp_path)
    assert command.main([*args, "--plan", "--ledger", HOST.value]) == 0
    preview = capsys.readouterr().out
    assert "write needed" in preview
    assert f"{HOST.value}: no CSV inputs" in preview
    assert file_hashes(tmp_path) == before
    assert command.main([*args, "--verify"]) == 1
    assert "not proven" in capsys.readouterr().err
    assert command.main([*args, "--write"]) == 0
    assert "CSV kept" in capsys.readouterr().out
    assert source.exists()
    written = file_hashes(tmp_path)
    assert command.main([*args, "--verify"]) == 0
    assert file_hashes(tmp_path) == written
    assert command.main([*args, "--retire"]) == 0
    assert not source.exists()


@pytest.mark.parametrize("month", ["202609", "2026-13", "0000-01", "../2026-09"])
def test_migration_cli_refuses_invalid_months(tmp_path: Path, month: str) -> None:
    with pytest.raises(SystemExit) as refused:
        command.main(
            [
                "--state-dir",
                str(tmp_path),
                "--run-id",
                RUN,
                "--git-sha",
                SEED_COMMIT,
                "--month",
                month,
            ]
        )
    assert refused.value.code == 2


def test_migration_cli_requires_a_month(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as refused:
        command.main(["--state-dir", str(tmp_path), "--run-id", RUN, "--git-sha", SEED_COMMIT])
    assert refused.value.code == 2
