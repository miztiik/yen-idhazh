"""Does the collector report real transported events without inventing a job's result?"""

from __future__ import annotations

import json
import logging
import os
import shutil
from pathlib import Path

import pytest

from idhazh import cli, config, event_lines
from idhazh.contracts.base import Model
from idhazh.contracts.council_events import (
    CouncilExit,
    CouncilProgram,
    Diagnostic,
    NightPublished,
    ProgramFinished,
    UnitFinished,
)
from idhazh.contracts.council_invocation import Selection
from idhazh.contracts.council_run_record import EvaluationStep, ShardOutcome
from idhazh.council import event_log, outcome, registry, run_summary, session, work_files
from utilities import council_publish

from ._tenants import a_venue, forget
from .test_events import HOSTILE
from .test_publication import configuration
from .test_selected_runs import INDEPENDENT_SOURCE, _deliver_document

DATE = "2026-10-10"
RUN = "2026-10-11-123"


def authorize(
    tmp_path: Path,
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    source: str = INDEPENDENT_SOURCE,
) -> Path:
    package = "report_file_plugins"
    a_venue(tmp_path, package=package, slugs={"one-judge": (1, ())}, source=source)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    forget(package)
    root = configuration(repo, ("one-judge",))
    selected = Selection.model_validate(
        {
            "run_id": RUN,
            "attempt": 1,
            "git_sha": "a" * 40,
            "mode": "manual",
            "anchor_date": DATE,
            "window": (DATE,),
            "judges": ({"tenant": "one-judge", "status": "active", "dates": (DATE,), "shards": 1},),
        }
    )
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    monkeypatch.setenv("COUNCIL_SELECTION", selected.to_json())
    session.prepare(config.load_council(root), run_id=RUN, selection=selected)
    return root


def unit(
    judge: str = "one-judge",
    *,
    date: str = DATE,
    shard: int = 0,
    shards: int = 1,
    outcome: ShardOutcome | str = ShardOutcome.COMPLETED,
    step: EvaluationStep = EvaluationStep.EVALUATE_WORK_PART,
) -> UnitFinished:
    return UnitFinished.model_validate(
        {
            "date": date,
            "run_id": RUN,
            "judge_id": judge,
            "evaluation_step": step,
            "work_part_index": shard if step is EvaluationStep.EVALUATE_WORK_PART else None,
            "work_part_count": shards,
            "outcome": outcome,
        }
    )


def matrix(*judges: str, dates: tuple[str, ...] = (DATE,), shards: int = 1) -> str:
    return json.dumps(
        [
            {
                "tenant": judge,
                "date": date,
                "shard": shard,
                "shards": shards,
                "runs_model": False,
            }
            for judge in judges
            for date in dates
            for shard in range(shards)
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


def test_publication_words_match_their_counts() -> None:
    report = run_summary.Report(
        events=[
            NightPublished(
                dates=(DATE,),
                run_id=RUN,
                landing="landed",
                pushes=1,
                writes=1,
                code=CouncilExit.OK,
            )
        ]
    )
    assert "Publication: `landed`; 1 write; 1 push." in report.markdown()


def test_each_judge_date_and_stage_is_reported_and_grouped_once(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    dates = (DATE, "2026-10-09")
    judges = ("first-judge", "second-judge")
    shards = 4
    root = tmp_path / "events"
    for cell in run_summary.cells(matrix(*judges, dates=dates, shards=shards)):
        write_events(
            cell.event_path(root),
            unit(
                cell.tenant,
                date=cell.date,
                shard=cell.shard,
                shards=cell.shards,
            ),
            ProgramFinished(program=CouncilProgram.SHARD, code=CouncilExit.OK),
        )
    write_events(
        root / "planner.jsonl",
        *(
            unit(
                judge,
                date=date,
                shards=shards,
                step=EvaluationStep.SELECT_JUDGE_WORK,
            )
            for judge in judges
            for date in dates
        ),
    )
    report = run_summary.Report(
        events=[
            *(
                unit(
                    judge,
                    date=date,
                    shards=shards,
                    step=EvaluationStep.COMBINE_JUDGE_RESULTS,
                )
                for judge in judges
                for date in dates
            ),
            *collector(),
        ]
    )
    report.load(matrix(*judges, dates=dates, shards=shards), root, RUN)
    assert not report.failed
    path = tmp_path / "summary.md"
    path.write_text("Earlier step.\n", encoding="utf-8", newline="\n")
    report.write(path)
    text = path.read_text("utf-8")
    assert text.startswith("Earlier step.\n") and text.count("### Council night") == 1
    assert text.count("#### Judge `") == 2
    assert text.count("2 of 2 dates completed; 8 of 8 judging jobs completed.") == 2
    assert text.count("<details>") == 2 and text.count("</details>") == 2
    first = text.split("#### Judge `first-judge`", 1)[1].split("#### Judge `second-judge`", 1)[0]
    second = text.split("#### Judge `second-judge`", 1)[1]
    for letter, judge, section in zip(("A", "B"), judges, (first, second), strict=True):
        assert f"Table {letter} - `{judge}` by date (UTC)" in section
        assert f"| {letter}1 | {dates[0]}" in section
        assert f"| {letter}2 | {dates[1]}" in section
        for date in dates:
            assert f"- {date} prepare: completed" in section
            for shard in range(shards):
                assert (
                    f"- {date} shard {shard} of {shards} (starts at 0): completed; exit 0 `ok`"
                ) in section
            assert f"- {date} settle: completed" in section
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
    assert text.count("0/1 completed; **1 failed or incomplete**") == 3
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
    text = report.markdown()
    assert " | not run | " in text
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
    caplog: pytest.LogCaptureFixture,
) -> None:
    root = tmp_path / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    path = cell.event_path(root)
    monkeypatch.setenv("COUNCIL_EVENT_FILE", str(path))
    event_log.install("ERROR")
    try:
        with caplog.at_level(logging.ERROR, logger=event_log.logger.name):
            event_log.emit(unit())
            assert outcome.finish(CouncilProgram.SHARD, 0) == 0
    finally:
        monkeypatch.delenv("COUNCIL_EVENT_FILE")
        event_log.install()
    assert "unit-finished" not in caplog.text
    assert [type(event) for event in run_summary.read_events(path)] == [
        UnitFinished,
        ProgramFinished,
    ]
    report = run_summary.Report()
    report.load(matrix("one-judge"), root, RUN)
    assert not report.failed
    assert report.units[0].ended() == "completed; exit 0 `ok`"


def test_bundle_writer_is_isolated_from_registered_logger_handlers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    path = tmp_path / "events.jsonl"
    monkeypatch.setenv("COUNCIL_EVENT_FILE", str(path))
    registered = logging.getLogger("idhazh.council.event_log.transport")
    previous = registered.propagate
    registered.propagate = True
    registered.addHandler(caplog.handler)
    try:
        event_log.install()
        with caplog.at_level(logging.INFO), event_log.capture() as captured:
            event_log.emit(unit(outcome="failed"), level=logging.ERROR)
        assert len(caplog.records) == 1
        assert len(captured) == 1
        assert len(run_summary.read_events(path)) == 1
    finally:
        registered.removeHandler(caplog.handler)
        registered.propagate = previous
        monkeypatch.delenv("COUNCIL_EVENT_FILE")
        event_log.install()


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
        with pytest.raises(ValueError):
            handler.close()


def test_ready_work_without_a_matrix_cell_is_not_dispatched(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repo = tmp_path / "repo"
    target = authorize(tmp_path, repo, monkeypatch)
    selected = Selection.model_validate_json(
        os.environ["COUNCIL_SELECTION"],
    ).check(config.load_council(target))
    report = run_summary.Report()
    report.load("[]", session.COUNCIL_ROOT / "events", RUN, selection=selected)
    assert len(report.units) == 1
    assert report.units[0].normalized().report_state == "not_dispatched"
    assert report.failed
    assert "not dispatched" in report.markdown()


def test_missing_preparation_is_unknown_not_no_work(
    tmp_path: Path,
) -> None:
    selected = Selection.model_validate(
        {
            "run_id": RUN,
            "attempt": 1,
            "git_sha": "a" * 40,
            "mode": "manual",
            "anchor_date": DATE,
            "window": (DATE,),
            "judges": ({"tenant": "one-judge", "status": "active", "dates": (DATE,), "shards": 1},),
        }
    )
    report = run_summary.Report()
    write_events(
        tmp_path / "events" / "planner.jsonl",
        unit(step=EvaluationStep.SELECT_JUDGE_WORK),
    )
    report.load("[]", tmp_path / "events", RUN, selection=selected)
    assert report.missing_preparations == (("one-judge", DATE),)
    assert report.failed and report.units == ()
    text = report.markdown()
    assert "0 of 1 date completed" in text
    assert "unknown; no report" in text
    assert "judging job count unknown for 1 of 1 date" in text
    assert "no judging jobs" not in text


def test_no_work_date_is_complete_without_judging_jobs() -> None:
    report = run_summary.Report(
        planning=(
            unit(
                outcome=ShardOutcome.NOTHING_TO_DO,
                step=EvaluationStep.SELECT_JUDGE_WORK,
            ),
        ),
        events=[
            unit(
                outcome=ShardOutcome.NOTHING_TO_DO,
                step=EvaluationStep.COMBINE_JUDGE_RESULTS,
            ),
            *collector(),
        ],
    )
    assert "1 of 1 date completed; no judging jobs." in report.markdown()


@pytest.mark.parametrize("layout", ["flat", "named"])
def test_actual_verification_and_execution_share_one_report(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    layout: str,
) -> None:
    repo = tmp_path / "repo"
    planner = repo / "backend" / "var" / "council"
    monkeypatch.setenv(
        "COUNCIL_EVENT_FILE",
        str(planner / "outgoing" / "planner" / "events" / "planner.jsonl"),
    )
    event_log.install()
    target = authorize(tmp_path, repo, monkeypatch)
    selected = Selection.model_validate_json(os.environ["COUNCIL_SELECTION"])
    receipt = work_files.read_preparation(planner, selected, "one-judge", DATE)
    assert receipt is not None
    worker = tmp_path / "worker"
    download = worker / "incoming"
    if layout == "named":
        download /= f"council-selection-{DATE}"
    _deliver_document(
        planner / "outgoing" / "planner",
        download,
        selected,
        receipt,
        event="planner.jsonl",
    )
    monkeypatch.setattr(session, "COUNCIL_ROOT", worker)
    root = worker / "outgoing" / f"shard-one-judge-{DATE}-0" / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    monkeypatch.setenv("COUNCIL_EVENT_FILE", str(cell.event_path(root)))
    args = [
        "council-shard",
        "--config",
        str(target),
        "--tenant",
        cell.tenant,
        "--date",
        DATE,
        "--run-id",
        RUN,
        "--commit",
        selected.git_sha,
        "--shard",
        "0",
        "--shards",
        "1",
    ]
    assert cli.main([*args, "--verify-only"]) == 0
    assert cli.main(args) == 0
    exits = [
        event.program
        for event in run_summary.read_events(cell.event_path(root))
        if isinstance(event, ProgramFinished)
    ]
    assert exits == [CouncilProgram.VERIFY_WORK, CouncilProgram.SHARD]
    result = run_summary.reported(cell, root, RUN)
    assert not result.failed and not result.invalid
    assert result.normalized().report_state == "reported"
    assert result.program is not None and result.program.program is CouncilProgram.SHARD


@pytest.mark.parametrize("code", list(CouncilExit))
def test_verification_never_substitutes_for_the_actual_shard_exit(
    tmp_path: Path,
    code: CouncilExit,
) -> None:
    root = tmp_path / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    write_events(
        cell.event_path(root),
        ProgramFinished(program=CouncilProgram.VERIFY_WORK, code=code),
    )
    result = run_summary.reported(cell, root, RUN)
    assert not result.invalid and result.failed
    assert result.unit is None and result.program is None
    normalized = result.normalized()
    assert normalized.report_state == ("refused" if code is CouncilExit.REFUSED else "missing")
    assert normalized.code is code


@pytest.mark.parametrize(
    "programs",
    [
        (CouncilProgram.VERIFY_WORK, CouncilProgram.VERIFY_WORK),
        (CouncilProgram.SHARD, CouncilProgram.SHARD),
        (CouncilProgram.PREPARE,),
    ],
)
def test_duplicate_or_unrelated_program_exits_are_invalid(
    tmp_path: Path,
    programs: tuple[CouncilProgram, ...],
) -> None:
    root = tmp_path / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    write_events(
        cell.event_path(root),
        *(ProgramFinished(program=program, code=CouncilExit.OK) for program in programs),
    )
    result = run_summary.reported(cell, root, RUN)
    assert result.invalid and result.failed


@pytest.mark.parametrize("code", [CouncilExit.FAILED, CouncilExit.REFUSED])
def test_work_after_rejected_verification_cannot_report_success(
    tmp_path: Path,
    code: CouncilExit,
) -> None:
    root = tmp_path / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    write_events(
        cell.event_path(root),
        ProgramFinished(program=CouncilProgram.VERIFY_WORK, code=code),
        unit(),
        ProgramFinished(program=CouncilProgram.SHARD, code=CouncilExit.OK),
    )
    result = run_summary.reported(cell, root, RUN)
    assert result.invalid and result.failed


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
    config_root = authorize(tmp_path, repo, monkeypatch)
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
        str(config_root),
        "--matrix",
        matrix("one-judge"),
        "--units-result",
        upstream,
    ]
    code = council_publish.main(args)
    assert code == 1
    text = summary.read_text("utf-8")
    assert "Council night: exit 1 `failed`" in text
    if upstream != "cancelled":
        assert "completed; exit 0 `ok`" in text


def test_collector_failure_still_appends_one_safe_summary(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = tmp_path / "repo"
    config_root = authorize(tmp_path, repo, monkeypatch)
    root = repo / "backend" / "var" / "council" / "events"
    (cell,) = run_summary.cells(matrix("one-judge"))
    write_events(
        cell.event_path(root),
        unit(),
        ProgramFinished(program=CouncilProgram.SHARD, code=CouncilExit.OK),
    )
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    package = "report_file_plugins"
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
        str(config_root),
        "--matrix",
        matrix("one-judge"),
    ]
    try:
        code = council_publish.main(args)
        captured = capsys.readouterr()
    finally:
        forget(package)
    assert code != 0
    text = summary.read_text("utf-8")
    assert text.count("### Council night") == 1
    assert "exit 1 `failed`" in text and "completed; exit 0 `ok`" in text
    assert "SOURCE-TEXT" not in text + captured.out + captured.err


def test_real_shard_bundle_is_read_by_the_real_collector_when_a_shard_raises(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    package = "summary_tenants"
    source = INDEPENDENT_SOURCE.replace(
        '        values = json.loads(task.read_text(encoding="utf-8"))',
        f"        raise RuntimeError({HOSTILE!r})",
    )
    repo = tmp_path / "collector"
    config_root = authorize(tmp_path, repo, monkeypatch, source=source)
    package = "report_file_plugins"
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
        "--commit",
        "a" * 40,
        "--config",
        str(config_root),
    ]
    try:
        shard_code = cli.main(argv)
        shard_output = capsys.readouterr()
    finally:
        forget(package)
    assert shard_code == 1
    assert b"\r" not in uploaded.read_bytes() and "SOURCE-TEXT" not in uploaded.read_text("utf-8")
    received = repo / "backend" / "var" / "council" / "events" / "one-judge" / DATE / "0.jsonl"
    received.parent.mkdir(parents=True)
    shutil.copy2(uploaded, received)
    monkeypatch.delenv("COUNCIL_EVENT_FILE")
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
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
        str(config_root),
        "--matrix",
        matrix("one-judge"),
        "--units-result",
        "failure",
    ]
    publish_code = council_publish.main(args)
    publish_output = capsys.readouterr()
    assert publish_code == shard_code
    text = summary.read_text("utf-8")
    assert text.count("### Council night") == 1
    assert "failed" in text
    assert "SOURCE-TEXT" not in text
    assert "SOURCE-TEXT" not in shard_output.err + publish_output.out + publish_output.err
    assert publish_output.out.count("::group::one-judge") == 1
    assert "::error title=one-judge::" in publish_output.out
