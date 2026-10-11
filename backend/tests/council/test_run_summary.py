"""Does the collector report real transported events without inventing a job's result?"""

from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path

import pytest

from idhazh import event_lines
from idhazh.contracts.base import Model
from idhazh.contracts.council_events import (
    CouncilExit,
    CouncilProgram,
    Diagnostic,
    NightPublished,
    ProgramFinished,
    UnitFinished,
)
from idhazh.contracts.council_run_record import EvaluationStep, ShardOutcome
from idhazh.council import event_log, run_summary

from ._tenants import TENANT_SOURCE, a_scripted_venue, a_venue
from .test_events import HOSTILE, completed_process
from .test_publication import configuration

DATE = "2026-10-10"
RUN = "2026-10-11-123"


def unit(
    judge: str = "one-judge",
    *,
    date: str = DATE,
    outcome: ShardOutcome | str = ShardOutcome.COMPLETED,
    step: EvaluationStep = EvaluationStep.EVALUATE_WORK_PART,
) -> UnitFinished:
    return UnitFinished.model_validate(
        {
            "date": date,
            "run_id": RUN,
            "judge_id": judge,
            "evaluation_step": step,
            "work_part_index": 0 if step is EvaluationStep.EVALUATE_WORK_PART else None,
            "work_part_count": 1,
            "outcome": outcome,
        }
    )


def matrix(*judges: str, dates: tuple[str, ...] = (DATE,)) -> str:
    return json.dumps(
        [
            {"tenant": judge, "date": date, "shard": 0, "shards": 1, "runs_model": False}
            for judge in judges
            for date in dates
        ]
    )


def write_events(path: Path, *events: Model) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.Logger("summary-fixture")
    handler = event_log.EventFile(path, encoding="utf-8")
    handler.setFormatter(event_log.OneJsonLine())
    logger.addHandler(handler)
    try:
        for event in events:
            event_lines.emit(event, logger=logger, force=True)
    finally:
        logger.removeHandler(handler)
        handler.close()


def collector(code: CouncilExit = CouncilExit.OK) -> list[Model]:
    return [
        NightPublished(
            dates=(DATE,), run_id=RUN, landing="no-changes", pushes=0, writes=0, code=code
        ),
        ProgramFinished(program=CouncilProgram.PUBLISH, code=code),
    ]


def test_fixed_base_oracle_requires_real_event_transport_and_collector_report() -> None:
    from conftest import REPO_ROOT

    workflow = (REPO_ROOT / ".github" / "workflows" / "llm-council.yml").read_text("utf-8")
    publisher = (REPO_ROOT / "backend" / "utilities" / "council_publish.py").read_text("utf-8")
    assert "COUNCIL_EVENT_FILE:" in workflow
    assert '--matrix "$COUNCIL_MATRIX"' in workflow
    assert "report.write(" in publisher
    assert "GITHUB_STEP_SUMMARY" in publisher


@pytest.mark.parametrize("code", list(CouncilExit))
def test_each_exit_has_its_label_and_fixed_sentence(code: CouncilExit, tmp_path: Path) -> None:
    report = run_summary.Report(events=collector(code))
    text = report.markdown()
    assert f"exit {code.value} `{code.label}`" in text
    assert code.sentence[:1].upper() + code.sentence[1:] in text
    path = tmp_path / "exit.jsonl"
    write_events(path, ProgramFinished(program=CouncilProgram.SHARD, code=code))
    (event,) = run_summary.read_events(path)
    assert isinstance(event, ProgramFinished) and event.sentence == code.sentence


def test_each_judge_date_and_stage_is_reported_and_grouped_once(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dates = (DATE, "2026-10-09")
    root = tmp_path / "events"
    for cell in run_summary.cells(matrix("first-judge", "second-judge", dates=dates)):
        write_events(
            cell.event_path(root),
            unit(cell.tenant, date=cell.date),
            ProgramFinished(program=CouncilProgram.SHARD, code=CouncilExit.OK),
        )
    write_events(
        root / "planner.jsonl",
        unit("first-judge", step=EvaluationStep.SELECT_JUDGE_WORK),
    )
    report = run_summary.Report(
        events=[
            unit("second-judge", step=EvaluationStep.COMBINE_JUDGE_RESULTS),
            *collector(),
        ]
    )
    report.load(matrix("first-judge", "second-judge", dates=dates), root, RUN)
    assert not report.failed
    path = tmp_path / "summary.md"
    path.write_text("Earlier step.\n", encoding="utf-8", newline="\n")
    report.write(path)
    text = path.read_text("utf-8")
    assert text.startswith("Earlier step.\n") and text.count("### Council night") == 1
    assert "prepare | completed" in text and "settle | completed" in text
    for judge in ("first-judge", "second-judge"):
        for date in dates:
            assert f"`{judge}` | {date} | shard 0 of 1" in text
    commands = capsys.readouterr().out
    assert commands.count("::group::") == 2 and commands.count("::endgroup::") == 2
    assert "::error" not in commands
    assert b"\r" not in path.read_bytes()


def test_missing_failed_and_invalid_reports_are_not_success(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "events"
    selected = run_summary.cells(matrix("failed-judge", "killed-judge", "invalid-judge"))
    write_events(
        selected[0].event_path(root),
        unit("failed-judge", outcome="failed"),
        ProgramFinished(program=CouncilProgram.SHARD, code=CouncilExit.FAILED),
    )
    write_events(selected[2].event_path(root), unit("other-judge"))
    report = run_summary.Report(events=collector(CouncilExit.FAILED))
    report.load(matrix("failed-judge", "killed-judge", "invalid-judge"), root, RUN)
    assert report.failed
    text = report.markdown()
    assert "**failed**; exit 1 `failed`" in text
    assert "**no report**" in text and "**invalid report**" in text
    report.write(tmp_path / "summary.md")
    commands = capsys.readouterr().out
    assert commands.count("::error title=") == 3
    assert commands.index("::endgroup::") < commands.index("::error title=")
    assert "other-judge" not in commands


@pytest.mark.parametrize("outcome", ["failed", "stopped_on_deadline"])
def test_prepare_and_settle_failures_get_annotations(
    outcome: str,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    report = run_summary.Report(
        planning=(unit(step=EvaluationStep.SELECT_JUDGE_WORK, outcome=outcome),),
        events=[unit(step=EvaluationStep.COMBINE_JUDGE_RESULTS, outcome=outcome), *collector()],
    )
    report.write(tmp_path / "summary.md")
    output = capsys.readouterr().out
    assert output.count("::group::one-judge") == 1
    assert f"::error title=one-judge::{DATE} prepare:" in output
    assert f"::error title=one-judge::{DATE} settle:" in output


@pytest.mark.parametrize(
    "change",
    [
        {"event": "unknown"},
        {"event": {"text": HOSTILE}},
        {"message": HOSTILE},
        {"error": HOSTILE},
        {"where": HOSTILE},
        {"at": HOSTILE},
        {"level": HOSTILE},
        {"label": HOSTILE},
        {"sentence": HOSTILE},
    ],
)
def test_unknown_and_hostile_event_data_is_rejected(
    change: dict[str, object],
    tmp_path: Path,
) -> None:
    path = tmp_path / "hostile.jsonl"
    write_events(path, Diagnostic(kind="exception"))
    line = json.loads(path.read_text("utf-8"))
    line.update(change)
    path.write_text(json.dumps(line) + "\n", encoding="utf-8", newline="\n")
    with pytest.raises(ValueError):
        run_summary.read_events(path)


@pytest.mark.parametrize("change", [{"tenant": HOSTILE}, {"date": "2026-13-45"}, {"shard": -1}])
def test_hostile_or_invalid_planned_cells_are_rejected(change: dict[str, object]) -> None:
    data = json.loads(matrix("one-judge"))
    data[0].update(change)
    with pytest.raises(ValueError):
        run_summary.cells(json.dumps(data))


@pytest.mark.parametrize("code", list(CouncilExit))
def test_partial_reports_keep_the_explicit_exit_without_claiming_success(
    code: CouncilExit,
    tmp_path: Path,
) -> None:
    root = tmp_path / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    write_events(cell.event_path(root), ProgramFinished(program=CouncilProgram.SHARD, code=code))
    result = run_summary.reported(cell, root, RUN)
    assert result.failed
    assert f"exit {code.value} `{code.label}`" in result.ended()
    assert ("not attempted" in result.ended()) == (code is CouncilExit.REFUSED)
    assert "completed" not in result.ended()


def test_hidden_progress_still_rides_the_bundle(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("COUNCIL_EVENT_FILE", str(path))
    process = completed_process(
        "from idhazh.council import event_log, outcome; "
        "from idhazh.contracts.council_events import CouncilProgram, UnitFinished; "
        "event_log.install('ERROR'); "
        f"event_log.emit(UnitFinished.model_validate({unit().model_dump(mode='json')!r})); "
        "raise SystemExit(outcome.finish(CouncilProgram.SHARD, 0))"
    )
    assert process.returncode == 0, process.stderr
    assert [type(event) for event in run_summary.read_events(path)] == [
        UnitFinished,
        ProgramFinished,
    ]
    assert "unit-finished" not in process.stderr
    assert json.loads(process.stderr)["label"] == "ok"


def test_event_transport_write_failure_is_not_silently_ignored(tmp_path: Path) -> None:
    logger = logging.Logger("closed-transport")
    handler = event_log.EventFile(tmp_path / "closed.jsonl", encoding="utf-8")
    handler.setFormatter(event_log.OneJsonLine())
    logger.addHandler(handler)
    assert handler.stream is not None
    handler.stream.close()
    try:
        with pytest.raises(ValueError):
            event_lines.emit(unit(), logger=logger, force=True)
    finally:
        logger.removeHandler(handler)
        handler.stream = None
        handler.close()


@pytest.mark.parametrize("defect", ["wrong-run", "duplicate", "contradictory", "truncated"])
def test_corrupt_or_mismatched_reports_are_rejected(defect: str, tmp_path: Path) -> None:
    root = tmp_path / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    reported = unit(outcome="failed" if defect == "contradictory" else "completed")
    if defect == "wrong-run":
        reported = reported.model_copy(update={"run_id": "2026-10-11-999"})
    events: list[Model] = [reported]
    if defect == "duplicate":
        events.append(reported)
    events.append(ProgramFinished(program=CouncilProgram.SHARD, code=CouncilExit.OK))
    path = cell.event_path(root)
    write_events(path, *events)
    if defect == "truncated":
        with path.open("a", encoding="utf-8", newline="\n") as output:
            output.write('{"event":')
    result = run_summary.reported(cell, root, RUN)
    assert result.invalid and result.unit is None and result.program is None


@pytest.mark.parametrize("upstream", ["failure", "cancelled"])
def test_upstream_failure_is_preserved_even_with_a_complete_success_report(
    upstream: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    root = repo / "backend" / "var" / "council" / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    write_events(
        cell.event_path(root),
        unit(),
        ProgramFinished(program=CouncilProgram.SHARD, code=CouncilExit.OK),
    )
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    args = [
        "--date",
        DATE,
        "--run-id",
        RUN,
        "--commit",
        "a" * 40,
        "--repo-root",
        str(repo),
        "--config-root",
        str(configuration(repo, ())),
        "--matrix",
        matrix("one-judge"),
        "--units-result",
        upstream,
    ]
    saved = completed_process(
        f"from utilities.council_publish import main; raise SystemExit(main({args!r}))"
    )
    assert saved.returncode == 1, saved.stderr
    text = summary.read_text("utf-8")
    assert "Council night: exit 1 `failed`" in text
    assert "completed; exit 0 `ok`" in text


def test_collector_failure_still_appends_one_safe_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    root = repo / "backend" / "var" / "council" / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    write_events(
        cell.event_path(root),
        unit(),
        ProgramFinished(program=CouncilProgram.SHARD, code=CouncilExit.OK),
    )
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    package = "collector_failure_tenants"
    a_venue(tmp_path, package=package, slugs={"one-judge": (1, ())})
    args = [
        "--date",
        DATE,
        "--run-id",
        RUN,
        "--commit",
        "a" * 40,
        "--repo-root",
        str(repo),
        "--config-root",
        str(configuration(repo, ("one-judge",))),
        "--matrix",
        matrix("one-judge"),
    ]
    saved = completed_process(
        "from utilities.council_publish import main; from idhazh.council import registry; "
        f"registry.TENANT_PACKAGE={package!r}; raise SystemExit(main({args!r}))",
        root=tmp_path,
    )
    assert saved.returncode != 0
    text = summary.read_text("utf-8")
    assert text.count("### Council night") == 1
    assert "exit 1 `failed`" in text and "completed; exit 0 `ok`" in text
    assert "SOURCE-TEXT" not in text + saved.stdout + saved.stderr


@pytest.mark.parametrize("result", ["completed", "stopped_on_deadline", "raised"])
def test_real_shard_bundle_is_read_by_the_real_collector_on_success_and_failure(
    result: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = "summary_tenants"
    if result == "raised":
        source = TENANT_SOURCE.replace(
            "        self.ran.append((date, run_id, shard, shards))",
            f"        raise RuntimeError({HOSTILE!r})",
        )
        a_venue(tmp_path, package=package, slugs={"one-judge": (1, ())}, source=source)
    else:
        a_scripted_venue(tmp_path, package=package, slug="one-judge", shard_count=1, outcome=result)
    config_root = configuration(tmp_path, ("one-judge",))
    uploaded = tmp_path / "uploaded" / "events" / "one-judge" / DATE / "0.jsonl"
    monkeypatch.setenv("COUNCIL_EVENT_FILE", str(uploaded))
    argv = [
        "council-shard",
        "--tenant",
        "one-judge",
        "--date",
        DATE,
        "--run-id",
        RUN,
        "--config",
        str(config_root),
    ]
    process = completed_process(
        "from pathlib import Path; from idhazh import cli; "
        "from idhazh.council import registry, session; "
        f"registry.TENANT_PACKAGE={package!r};"
        f"session.COUNCIL_ROOT=Path({str(tmp_path / 'scratch')!r});"
        f"raise SystemExit(cli.main({argv!r}))",
        root=tmp_path,
    )
    assert process.returncode == (0 if result == "completed" else 1)
    assert b"\r" not in uploaded.read_bytes() and "SOURCE-TEXT" not in uploaded.read_text("utf-8")
    repo = tmp_path / "collector"
    received = repo / "backend" / "var" / "council" / "events" / "one-judge" / DATE / "0.jsonl"
    received.parent.mkdir(parents=True)
    shutil.copy2(uploaded, received)
    monkeypatch.delenv("COUNCIL_EVENT_FILE")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    args = [
        "--date",
        DATE,
        "--run-id",
        RUN,
        "--commit",
        "a" * 40,
        "--repo-root",
        str(repo),
        "--config-root",
        str(configuration(repo, ())),
        "--matrix",
        matrix("one-judge"),
        "--units-result",
        "success" if result == "completed" else "failure",
    ]
    saved = completed_process(
        f"from utilities.council_publish import main; raise SystemExit(main({args!r}))"
    )
    assert saved.returncode == process.returncode, saved.stderr
    text = summary.read_text("utf-8")
    assert text.count("### Council night") == 1
    assert (result.replace("_", " ") if result != "raised" else "failed") in text
    assert "SOURCE-TEXT" not in text and "SOURCE-TEXT" not in saved.stdout
    assert saved.stdout.count("::group::one-judge") == 1
    assert ("::error title=one-judge::" in saved.stdout) == (process.returncode != 0)
