"""Do actual local publications report closed events without losing completed work?"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest
from gardener._garden import a_hook, an_origin, git, on_origin, quiet_git

from idhazh import config, ledger
from idhazh.contracts.base import Model
from idhazh.contracts.council_events import (
    CouncilProgram,
    NightPublished,
    ProgramFinished,
    UnitFinished,
)
from idhazh.contracts.council_run_record import CouncilRunRecord
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.publication_receipt import PublicationReceipt
from idhazh.council import event_log, outcome, registry, session
from utilities.council_publish import settle_and_publish
from utilities.publication_git import Repository

from ._tenants import a_venue, forget
from .test_publication import SOURCE, configuration

HOSTILE = "HOSTILE_PUBLICATION_TEXT ::error:: $(touch should-not-exist)"
HOSTILE_SOURCE = SOURCE.replace(
    'raise RuntimeError("later tenant failed after completing its write")',
    f"raise RuntimeError({HOSTILE!r})  # {HOSTILE}",
)
SUCCESS_SOURCE = SOURCE.replace('self.judge_id.endswith("failed")', "False")
RUN_ID = "2026-10-09-123"
DATES = ("2026-10-08", "2026-10-09")


@contextmanager
def venue(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    *,
    slugs: tuple[str, ...] = ("first",),
    source: str = SUCCESS_SOURCE,
) -> Iterator[tuple[Path, Path, Path]]:
    quiet_git(tmp_path, monkeypatch)
    # Explicitly generated bare repositories only; never change machine config.
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "safe.bareRepository")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "all")
    origin, repo = an_origin(
        tmp_path,
        {
            "seed": "seed\n",
            "config/push-retry.json": json.dumps(
                {
                    "deadline_seconds": {"default": 1},
                    "base_step_seconds": 0.001,
                    "ceiling_seconds": 0.001,
                    "ceiling_after": 1,
                }
            )
            + "\n",
        },
    )
    package = "event_publication_tenants"
    a_venue(
        tmp_path,
        package=package,
        slugs={slug: (1, (f"state/experiments/{slug}",)) for slug in slugs},
        source=source,
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    monkeypatch.setattr(session, "COUNCIL_ROOT", repo / "backend" / "var" / "council")
    # outcome.run installs the crash printer; restore it when this test ends.
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(caplog.handler, "formatter", event_log.OneJsonLine())
    forget(package)
    try:
        with caplog.at_level(logging.INFO):
            target = configuration(tmp_path, slugs)
            app_config = target / "idhazh.json"
            settings = json.loads(app_config.read_text(encoding="utf-8"))
            settings["observability"]["host_telemetry_enabled"] = False
            settings["observability"]["host_fingerprint"] = False
            settings["observability"]["memory_profiling_enabled"] = False
            app_config.write_text(json.dumps(settings), encoding="utf-8", newline="\n")
            yield origin, repo, target
    finally:
        forget(package)


def events(caplog: pytest.LogCaptureFixture) -> list[dict[str, Any]]:
    formatter = event_log.OneJsonLine()
    records = [record for record in caplog.records if record.name == event_log.logger.name]
    lines = [formatter.format(record) for record in records]
    assert all("\n" not in line and "\r" not in line for line in lines)
    assert "HOSTILE_PUBLICATION_TEXT" not in "\n".join(lines)
    assert "should-not-exist" not in "\n".join(lines)
    assert "::error::" not in "\n".join(lines)
    parsed = [json.loads(line) for line in lines]
    models: dict[str, type[Model]] = {
        "night-published": NightPublished,
        "unit-finished": UnitFinished,
        "program-finished": ProgramFinished,
    }
    for event in parsed:
        assert event["at"].endswith("Z")
        if event["event"] in models:
            fields = {
                key: value for key, value in event.items() if key not in ("event", "at", "level")
            }
            # ProgramFinished's computed fields are output, not model inputs.
            fields.pop("label", None)
            fields.pop("sentence", None)
            models[event["event"]].model_validate(fields)
    return parsed


def run(
    repo: Path,
    target: Path,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
    *,
    code: int,
    landing: str,
    units: int,
    dates: tuple[str, ...] = DATES,
    units_failed: bool = False,
) -> dict[str, Any]:
    actual = outcome.run(
        CouncilProgram.PUBLISH,
        lambda: settle_and_publish(
            repo=repo,
            dates=dates,
            run_id=RUN_ID,
            commit_sha=git(repo, "rev-parse", "HEAD").strip(),
            config_root=target,
            units_failed=units_failed,
        ),
    )
    assert actual == code
    captured = capsys.readouterr()
    assert captured.out == "", "publisher details must not be printed"
    assert captured.err == "", "events belong on the logging handler"
    parsed = events(caplog)
    assert "HOSTILE_PUBLICATION_TEXT" not in caplog.text
    finished = [event for event in parsed if event["event"] == "program-finished"]
    assert len(finished) == 1
    assert finished[0]["program"] == "publish"
    assert finished[0]["code"] == code
    assert finished[0]["label"] == outcome.CouncilExit(code).label
    assert finished[0]["sentence"] == outcome.CouncilExit(code).sentence
    published = [event for event in parsed if event["event"] == "night-published"]
    assert len(published) == 1
    assert published[0]["dates"] == list(dates)
    assert published[0]["run_id"] == RUN_ID
    assert published[0]["code"] == code
    assert published[0]["landing"] == landing
    unit_events = [event for event in parsed if event["event"] == "unit-finished"]
    assert len(unit_events) == units
    assert all(event["evaluation_step"] == "combine_judge_results" for event in unit_events)
    return published[0]


def evidence(repo: Path, *, origin: Path | None = None) -> dict[str, str]:
    receipts = [
        PublicationReceipt.read(path)
        for path in sorted((repo / "backend/var/council/publication").glob("*.json"))
    ]
    assert receipts
    writes = {path: digest for receipt in receipts for path, digest in receipt.writes.items()}
    assert writes
    remote = Repository(origin) if origin is not None else None
    for path, digest in writes.items():
        completed = (repo / path).read_bytes()
        assert hashlib.sha256(completed).hexdigest() == digest
        if remote is not None:
            entry = remote.entry("main", path)
            assert entry is not None, f"completed write never landed: {path}"
            assert remote.blob(entry.oid) == completed
    return writes


def rows(repo: Path) -> list[CouncilRunRecord]:
    loaded = ledger.load_days(
        repo / "state", LedgerName.COUNCIL_RUN_RECORDS, DATES, model=CouncilRunRecord
    )
    return loaded


def test_raising_judge_keeps_later_judges_dates_and_completed_bytes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    slugs = ("first", "second-failed", "third")
    with venue(tmp_path, monkeypatch, caplog, slugs=slugs, source=HOSTILE_SOURCE) as (
        _origin,
        repo,
        target,
    ):
        council = config.load_council(target)
        with pytest.raises(RuntimeError, match="HOSTILE_PUBLICATION_TEXT"):
            session.settle(
                council,
                date=DATES[0],
                run_id=RUN_ID,
                state_dir=repo / "state",
                commit_sha=git(repo, "rev-parse", "HEAD").strip(),
            )
        session.settle(
            council,
            date=DATES[1],
            run_id=RUN_ID,
            state_dir=repo / "state",
            commit_sha=git(repo, "rev-parse", "HEAD").strip(),
        )
        for slug in slugs:
            for date in DATES:
                assert (repo / f"state/experiments/{slug}/{date}.json").read_text() == "completed\n"
        failed = [event for event in events(caplog) if event.get("outcome") == "failed"]
        assert len(failed) == 1
        assert failed[0]["judge_id"] == "second-failed"
        assert failed[0]["date"] == DATES[0]
        assert failed[0]["error"] == "RuntimeError"
        assert failed[0]["where"].startswith("idhazh.council.")
        recorded = rows(repo)
        assert len(recorded) == 6
        assert [(row.judge_id, row.date, row.fault) for row in recorded if row.outcome == "failed"] == [
            ("second-failed", DATES[0], "raised")
        ]
        assert sum(row.date == DATES[1] for row in recorded) == 3


def test_a_push_deadline_can_expire_before_the_rejection_hook_runs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture,
) -> None:
    with venue(tmp_path, monkeypatch, caplog) as (origin, repo, _):
        before = git(origin, "rev-parse", "main").strip()
        a_hook(origin, 'printf "rejected\\n" >> "$GIT_DIR/rejected-pushes"\nexit 1')
        repository = Repository(repo)
        repository.deadline = time.monotonic()
        with pytest.raises(RuntimeError, match="deadline expired before Git operation"):
            repository.push(before)
        assert not (origin / "rejected-pushes").exists()
        assert git(origin, "rev-parse", "main").strip() == before


def test_post_work_integrity_refusal_does_not_push_or_claim_prework_stop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    source = SUCCESS_SOURCE.replace(
        "        if False",
        """        if self.judge_id == "second":
            atomic_write.write_atomic(state_dir / "undeclared/output.json", "unowned\\n")
        if False""",
    )
    with venue(tmp_path, monkeypatch, caplog, slugs=("first", "second"), source=source) as (
        origin,
        repo,
        target,
    ):
        before = git(origin, "rev-parse", "main")
        published = run(
            repo,
            target,
            caplog,
            capsys,
            code=1,
            landing="integrity-refused",
            units=2,
            dates=(DATES[0],),
        )
        assert published["pushes"] == 0
        assert git(origin, "rev-parse", "main") == before
        preserved = evidence(repo)
        assert f"state/experiments/first/{DATES[0]}.json" in preserved
        # The second tenant's declared write is known, but its unauthorized
        # write prevents a receipt for that tenant and prevents all publication.
        assert published["writes"] == len(preserved) + 1
        assert (repo / f"state/experiments/second/{DATES[0]}.json").read_bytes() == b"completed\n"
        assert (repo / "state/undeclared/output.json").read_bytes() == b"unowned\n"
        assert on_origin(origin, f"state/experiments/first/{DATES[0]}.json") is None
        assert len(rows(repo)) == 2
