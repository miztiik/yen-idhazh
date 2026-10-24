"""Do actual council entrypoints emit safe JSON events and the approved exit vocabulary?"""

from __future__ import annotations

import itertools
import json
import logging
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest
from support.paths import REPO_ROOT

from idhazh import config
from idhazh.contracts.council_events import (
    CouncilExit,
    CouncilProgram,
    Diagnostic,
    ProgramFinished,
    UnitFinished,
)
from idhazh.contracts.council_run_record import CouncilRunRecord, ShardOutcome
from idhazh.council import event_log, metrics_sink, outcome, registry, session

from ._tenants import TENANT_SOURCE, a_scripted_venue, a_venue, forget
from .test_publication import configuration

DATE = "2026-10-10"
RUN = "2026-10-11-123"
HOSTILE = "SOURCE-TEXT https://example.invalid/secret\n::error::untrusted"
PACKAGE = "event_tenants"


def lines(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    formatter = event_log.OneJsonLine()
    return [json.loads(formatter.format(record)) for record in caplog.records]


def test_every_combination_uses_the_approved_precedence() -> None:
    ranks = {0: 0, 1: 1, 3: 2, 2: 3}
    for codes in itertools.product(range(4), repeat=3):
        assert outcome.worst(codes) == max(codes, key=ranks.__getitem__)
    assert outcome.worst(()) is CouncilExit.OK
    with pytest.raises(ValueError):
        outcome.worst((4,))


@pytest.mark.parametrize(
    "code,label,sentence",
    [
        (0, "ok", "every unit finished and the rows landed"),
        (1, "failed", "a unit failed, or the rows did not land (stale or lost)"),
        (2, "refused", "stopped before any unit ran"),
        (3, "push_refused", "main refused every push, so nothing landed"),
    ],
)
def test_code_label_and_sentence_are_declared_and_printed_together(
    code: int, label: str, sentence: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO):
        assert outcome.finish(CouncilProgram.PREPARE, code) == code
    (said,) = lines(caplog)
    assert (said["code"], said["label"], said["sentence"]) == (code, label, sentence)
    assert ProgramFinished(program=CouncilProgram.PREPARE, code=CouncilExit(code)).label == label


@pytest.mark.parametrize("logger_name", ["idhazh.library", HOSTILE])
def test_unstructured_library_logs_cannot_carry_source_or_exception_text(
    caplog: pytest.LogCaptureFixture, logger_name: str,
) -> None:
    with caplog.at_level(logging.INFO):
        try:
            raise RuntimeError(HOSTILE)
        except RuntimeError:
            logging.getLogger(logger_name).exception(HOSTILE)
    (said,) = lines(caplog)
    assert said["event"] == "diagnostic" and said["error"] == "RuntimeError"
    assert "SOURCE-TEXT" not in json.dumps(said) and "example.invalid" not in json.dumps(said)
    with pytest.raises(ValueError):
        Diagnostic(kind="exception", error=HOSTILE)
    with pytest.raises(ValueError):
        Diagnostic(kind="exception", where=HOSTILE)


def test_a_raised_unit_has_one_failure_event_and_one_failed_record(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    source = TENANT_SOURCE.replace(
        "        self.ran.append((date, run_id, shard, shards))",
        f"        raise RuntimeError({HOSTILE!r})",
    )
    a_venue(tmp_path, package=PACKAGE, slugs={"one-judge": (1, ())}, source=source)
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", PACKAGE)
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "scratch")
    council = config.load_council(configuration(tmp_path, ("one-judge",)))
    forget(PACKAGE)
    try:
        with caplog.at_level(logging.INFO), pytest.raises(RuntimeError):
            session.run_shard(
                council,
                slug="one-judge",
                date=DATE,
                run_id=RUN,
                shard=0,
                shards=1,
                started=time.monotonic(),
            )
        (said,) = lines(caplog)
        assert (said["event"], said["outcome"], said["error"]) == (
            "unit-finished",
            "failed",
            "RuntimeError",
        )
        assert str(said["where"]).startswith("idhazh.council.deadline:")
        assert "SOURCE-TEXT" not in json.dumps(said)
        (row,) = metrics_sink.shipped_rows(
            session.outcomes_dir(DATE), judge_id="one-judge", contract=CouncilRunRecord
        )
        assert (row.outcome, row.fault) == (ShardOutcome.FAILED, "raised")
        assert row.seconds_spent >= 0
        assert row.model_calls is None and row.model_seconds is None
        assert row.tokens_in is None and row.tokens_out is None
        assert HOSTILE not in row.to_json()
    finally:
        forget(PACKAGE)


def test_row_filing_failure_does_not_emit_a_successful_unit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    a_venue(tmp_path, package=PACKAGE, slugs={"one-judge": (1, ())})
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", PACKAGE)
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "scratch")
    council = config.load_council(configuration(tmp_path, ("one-judge",)))
    blocked = session.outcomes_dir(DATE)
    blocked.parent.mkdir(parents=True)
    blocked.write_text("not a directory\n", encoding="utf-8", newline="\n")
    forget(PACKAGE)
    try:
        with caplog.at_level(logging.INFO), pytest.raises(OSError):
            session.run_shard(
                council,
                slug="one-judge",
                date=DATE,
                run_id=RUN,
                shard=0,
                shards=1,
                started=time.monotonic(),
            )
        events = [said for said in lines(caplog) if said["event"] == "unit-finished"]
        assert len(events) == 1 and events[0]["outcome"] == "failed"
        assert events[0]["error"] in ("FileExistsError", "NotADirectoryError")
    finally:
        forget(PACKAGE)


def completed_process(
    script: str, *, root: Path | None = None, bare: bool = False
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *(["-S"] if bare else []), "-c", script],
        capture_output=True,
        text=True,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                [str(REPO_ROOT / "backend"), *([str(root)] if root is not None else [])]
            ),
        },
        check=False,
    )


def test_crash_printer_still_runs_before_application_dependencies_are_installed() -> None:
    process = completed_process(
        "from idhazh import event_lines; event_lines.install_crash_printer(); "
        f"raise RuntimeError({HOSTILE!r})",
        bare=True,
    )
    assert process.returncode == 1
    assert "RuntimeError" in process.stderr and "__main__:" in process.stderr
    assert "SOURCE-TEXT" not in process.stderr and "example.invalid" not in process.stderr
    assert "::error" not in process.stderr


def test_success_exit_is_printed_even_when_configured_logging_level_is_error() -> None:
    process = completed_process(
        "from idhazh.council import event_log, outcome; "
        "from idhazh.contracts.council_events import CouncilProgram; "
        "event_log.install('ERROR'); outcome.finish(CouncilProgram.PREPARE, 0)"
    )
    assert process.returncode == 0 and process.stdout == ""
    (said,) = [json.loads(line) for line in process.stderr.splitlines()]
    assert (said["code"], said["label"]) == (0, "ok")


@pytest.mark.parametrize("result", ["completed", "stopped_on_deadline", "raised", "exit-zero"])
def test_actual_shard_entrypoint_prints_only_json_and_earns_its_real_code(
    result: str, tmp_path: Path
) -> None:
    if result in ("raised", "exit-zero"):
        raised = f"RuntimeError({HOSTILE!r})" if result == "raised" else "SystemExit(0)"
        source = TENANT_SOURCE.replace(
            "        self.ran.append((date, run_id, shard, shards))",
            f"        raise {raised}",
        )
        a_venue(tmp_path, package=PACKAGE, slugs={"one-judge": (1, ())}, source=source)
    else:
        a_scripted_venue(tmp_path, package=PACKAGE, slug="one-judge", shard_count=1, outcome=result)
    target = configuration(tmp_path, ("one-judge",))
    argv = [
        "council-shard",
        "--tenant",
        "one-judge",
        "--date",
        DATE,
        "--run-id",
        RUN,
        "--config",
        str(target),
    ]
    process = completed_process(
        "from pathlib import Path; from idhazh import cli; "
        "from idhazh.council import registry, session; "
        f"registry.TENANT_PACKAGE={PACKAGE!r}; session.COUNCIL_ROOT=Path({str(tmp_path / 'scratch')!r});"
        f"raise SystemExit(cli.main({argv!r}))",
        root=tmp_path,
    )
    expected = 0 if result == "completed" else 1
    assert process.returncode == expected
    assert process.stdout == ""
    said = [json.loads(line) for line in process.stderr.splitlines()]
    assert all(str(event["at"]).endswith("Z") for event in said)
    assert [event["event"] for event in said].count("unit-finished") == 1
    assert (said[-1]["event"], said[-1]["code"]) == ("program-finished", expected)
    assert "SOURCE-TEXT" not in process.stderr and "example.invalid" not in process.stderr


@pytest.mark.parametrize(
    "module,args",
    [
        ("idhazh.council.run_identity", ["--platform-run-id", HOSTILE]),
        ("idhazh.council.night_plan", ["--tonight", HOSTILE]),
        ("utilities.council_matrix", ["--date", HOSTILE]),
        ("utilities.council_publish", ["--date", HOSTILE, "--run-id", RUN, "--commit", "a" * 40]),
        ("utilities.council_publish", ["--date", DATE, "--run-id", HOSTILE, "--commit", "a" * 40]),
    ],
)
def test_entrypoint_refusals_are_json_with_no_argument_or_exception_text(
    module: str,
    args: list[str],
) -> None:
    process = completed_process(f"from {module} import main; raise SystemExit(main({args!r}))")
    assert process.returncode == 2 and process.stdout == ""
    said = [json.loads(line) for line in process.stderr.splitlines()]
    assert said[-1]["code"] == 2 and said[-1]["label"] == "refused"
    assert "SOURCE-TEXT" not in process.stderr and "example.invalid" not in process.stderr


def test_unit_event_refuses_an_untrusted_payload_field() -> None:
    with pytest.raises(ValueError):
        UnitFinished.model_validate(
            {
                "date": DATE,
                "run_id": RUN,
                "judge_id": "one-judge",
                "evaluation_step": "evaluate_work_part",
                "work_part_count": 1,
                "outcome": "failed",
                "message": HOSTILE,
            }
        )
