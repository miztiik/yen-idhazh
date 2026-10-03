"""Does `idhazh gardener` route each subcommand to its body and refuse a bad line by name?

The router holds no body of its own, so these drive it the way an operator or
a workflow step does - through `idhazh.cli.main` - against a fixture config, and
read what it printed and the code it exited with. The landing utility takes the
same line, and one test drives it the same way.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from idhazh import cli, config
from idhazh.gardener import cli as gardener_cli
from idhazh.gardener import listing
from idhazh.gardener.outcome import EXIT_INTEGRITY
from utilities import gardener_publish, gardener_shards

from ._garden import GARDENER_FIXTURES, a_config, an_origin, quiet_git

pytestmark = pytest.mark.contract

#: A commit the record's envelope can name. Nothing here reads it back.
SHA = "5c606df91ccfc6071935c77a7dc13d230255b05a"
RUN = ["--run-id", "2026-09-27-1", "--attempt", "1"]


def the_garden(tmp_path: Path) -> Path:
    return a_config(tmp_path, GARDENER_FIXTURES / "garden")


def test_the_gardener_is_a_verb_the_router_lists() -> None:
    assert "gardener" in cli.STAGES


def test_the_retired_cleanup_verb_is_gone_now_the_gardener_workflow_runs_its_tasks(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """`prune-state` only said where its passes went, until a workflow ran them. One does now."""
    assert "prune-state" not in cli.STAGES
    with pytest.raises(SystemExit) as refused:
        cli.main(["prune-state", "--date", "2026-09-27"])
    assert refused.value.code == 2
    assert "invalid choice: 'prune-state'" in capsys.readouterr().err


def test_list_tasks_prints_one_line_a_task(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_dir = the_garden(tmp_path)

    assert cli.main(["gardener", "list-tasks", "--config", str(config_dir)]) == 0

    printed = capsys.readouterr().out.splitlines()
    assert len(printed) == len(list((config_dir / "gardener").glob("*.json")))
    assert (
        "trials: active retention, keeps 90 days, reports only, owns everything else under state"
        in printed
    )


def test_plan_shards_prints_the_payload_the_plan_job_prints(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config_dir = the_garden(tmp_path)

    assert cli.main(["gardener", "plan-shards", "--json", "--config", str(config_dir)]) == 0
    assert capsys.readouterr().out.strip() == gardener_shards.payload(
        gardener_shards.plan(config_dir)
    )

    assert cli.main(["gardener", "plan-shards", "--config", str(config_dir)]) == 0
    printed = capsys.readouterr().out.splitlines()
    assert printed[0] == "5 shards"
    assert printed[-1] == "fullest: shard 0, with 2 tasks"


def test_an_empty_garden_lists_nothing_and_plans_nothing(tmp_path: Path) -> None:
    config_dir = a_config(tmp_path)
    (config_dir / "gardener").rmdir()

    settings = config.load_gardener(config_dir)
    assert listing.tasks(settings) == ["no task is declared: config/gardener/ holds no declaration"]


def test_an_unconfigured_declaration_is_not_read(tmp_path: Path) -> None:
    config_dir = the_garden(tmp_path)
    (config_dir / "gardener" / "Not A Name.json").write_text("{}", encoding="ascii")
    knobs_path = config_dir / "idhazh_gardener.json"
    knobs = json.loads(knobs_path.read_text(encoding="utf-8"))
    knobs["task_names"].append("Not A Name")
    knobs_path.write_text(json.dumps(knobs), encoding="ascii", newline="\n")

    assert cli.main(["gardener", "list-tasks", "--config", str(config_dir)]) == EXIT_INTEGRITY
    assert "config/idhazh_gardener.json is refused" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("line", "refusal"),
    [
        (["seen", "--attempt", "1", "--git-sha", SHA], "--run-id"),
        (["seen", *RUN], "--git-sha"),
        (["seen", *RUN, "--git-sha", "HEAD"], "--git-sha takes the forty hex digits"),
        (["seen", "--run-id", "tuesday", "--attempt", "1", "--git-sha", SHA], "--run-id takes"),
        (["seen", "--run-id", "2026-09-27-1", "--attempt", "0", "--git-sha", SHA], "counts from 1"),
        (["--shard", "7", *RUN, "--git-sha", SHA], "no shard 7"),
        (["day-validations", *RUN, "--git-sha", SHA], "is retired"),
        (["nobody", *RUN, "--git-sha", SHA], "no task is called nobody"),
    ],
)
def test_a_run_task_line_the_router_cannot_run_is_refused(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], line: list[str], refusal: str
) -> None:
    config_dir = the_garden(tmp_path)
    with pytest.raises(SystemExit) as stopped:
        cli.main(["gardener", "run-task", *line, "--config", str(config_dir)])
    assert stopped.value.code == 2
    assert refusal in capsys.readouterr().err


def test_run_task_accepts_an_inclusive_month_range_for_one_task(tmp_path: Path) -> None:
    config_dir = the_garden(tmp_path)
    settings = config.load_gardener(config_dir)
    parser = gardener_cli._parser()
    args = parser.parse_args(
        [
            "run-task",
            "telemetry-aggregate",
            *RUN,
            "--git-sha",
            SHA,
            "--from",
            "2025-01",
            "--to",
            "2025-02",
            "--config",
            str(config_dir),
        ]
    )

    assert gardener_cli.period_range(settings, args, parser) == ("2025-01", "2025-02")


def test_a_task_no_shipped_module_serves_exits_2_before_it_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """No shipped module is named for the task or for its kind, so nothing can run it."""
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {"state/old-days/.keep": ""})
    config_dir = a_config(checkout, GARDENER_FIXTURES / "runner" / "old-days.json")

    code = cli.main(
        [
            "gardener",
            "run-task",
            "old-days",
            *RUN,
            "--git-sha",
            SHA,
            "--repo-root",
            str(checkout),
            "--config",
            str(config_dir),
        ]
    )

    assert code == EXIT_INTEGRITY
    assert "config/gardener/old-days.json is served by no module" in capsys.readouterr().out


def test_the_landing_utility_takes_the_same_line_and_reads_the_commit_itself(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """One parser builds both lines, so a line one accepts the other accepts, less the commit."""
    quiet_git(tmp_path, monkeypatch)
    _, checkout = an_origin(tmp_path, {"state/old-days/.keep": ""})
    config_dir = a_config(checkout, GARDENER_FIXTURES / "runner" / "old-days.json")

    code = gardener_publish.main(
        ["old-days", *RUN, "--repo-root", str(checkout), "--config", str(config_dir)]
    )

    assert code == EXIT_INTEGRITY
    assert "config/gardener/old-days.json is served by no module" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        gardener_publish.main(["old-days", *RUN, "--git-sha", SHA, "--config", str(config_dir)])
