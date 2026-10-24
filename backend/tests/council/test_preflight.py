"""Does a written bad judge set stop planning before any judge receives work?"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from support.paths import REPO_ROOT

from idhazh import config
from idhazh.contracts.council_events import CouncilProgram, Diagnostic
from idhazh.council import event_log, night_plan, outcome, registry, session
from utilities import council_matrix

from ._config import copy_config, write_declarations
from ._tenants import a_venue, forget, written

PACKAGE = "preflight_tenants"
FIRST = "first-judge"
BAD = "bad-judge"
DATE = "2026-10-10"
HOSTILE = "SOURCE-TEXT https://example.invalid/secret\n::error::untrusted"


@pytest.fixture
def venue(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", PACKAGE)
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "scratch")
    forget(PACKAGE)
    yield tmp_path
    forget(PACKAGE)


def configuration(root: Path, slugs: tuple[str, ...]) -> Path:
    target = copy_config(root)
    write_declarations(target, slugs)
    raw = json.loads((target / "llm_council.json").read_text(encoding="utf-8"))
    raw["judge_names"] = slugs
    (target / "llm_council.json").write_text(json.dumps(raw), encoding="utf-8", newline="\n")
    return target


def invoke(command: str, target: Path) -> int:
    if command == "night":
        return night_plan.main(["--config-root", str(target), "--tonight", DATE])
    if command == "matrix":
        return council_matrix.main(["--config-root", str(target), "--date", DATE])

    def prepare() -> int:
        session.prepare(config.load_council(target), date=DATE, run_id="2026-10-11-123")
        return 0

    return outcome.run(CouncilProgram.PREPARE, prepare)


@pytest.mark.parametrize("command", ["night", "matrix", "prepare"])
@pytest.mark.parametrize(
    "defect",
    ["missing-file", "duplicate", "missing-package", "raising-import", "missing-dependency"],
)
def test_bad_sets_refuse_by_safe_name_before_any_work(
    venue: Path,
    defect: str,
    command: str,
    caplog: pytest.LogCaptureFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    a_venue(venue, package=PACKAGE, slugs={FIRST: (1, ()), BAD: (1, ())})
    target = configuration(venue, (FIRST, BAD, BAD) if defect == "duplicate" else (FIRST, BAD))
    if defect == "missing-file":
        (target / "judges" / f"{BAD}.json").unlink()
    elif defect == "missing-package":
        (venue / PACKAGE / "bad_judge").rename(venue / PACKAGE / "not_registered")
    elif defect in ("raising-import", "missing-dependency"):
        source = (
            f"raise RuntimeError({HOSTILE!r})\n"
            if defect == "raising-import"
            else "import missing_preflight_dependency\n"
        )
        (venue / PACKAGE / "bad_judge" / "tenant.py").write_text(
            source, encoding="utf-8", newline="\n"
        )

    with caplog.at_level(logging.INFO):
        assert invoke(command, target) == 2
    output = capsys.readouterr()
    assert output.out == ""
    formatter = event_log.OneJsonLine()
    events = [json.loads(formatter.format(record)) for record in caplog.records]
    assert any(
        event.get("kind") == "refusal" and event.get("judge_id") == BAD for event in events
    )
    assert events[-1]["code"] == 2 and events[-1]["label"] == "refused"
    assert "SOURCE-TEXT" not in json.dumps(events) + output.out + output.err
    assert "::error::untrusted" not in json.dumps(events) + output.err
    assert not any(event["event"] == "unit-finished" for event in events)
    earlier = written(PACKAGE, FIRST).TENANT
    assert earlier.asked == [] and earlier.prepared == []
    assert earlier.ran == [] and earlier.settled == []
    assert not (venue / "scratch").exists()


@pytest.mark.parametrize("status", ["paused", "retired"])
@pytest.mark.parametrize("defect", ["raising-import", "missing-package"])
@pytest.mark.parametrize("command", ["night", "matrix"])
def test_inactive_packages_are_neither_imported_nor_checked(
    venue: Path, status: str, defect: str, command: str, capsys: pytest.CaptureFixture[str]
) -> None:
    a_venue(venue, package=PACKAGE, slugs={FIRST: (1, ())}, poisoned_neighbour=BAD)
    target = configuration(venue, (FIRST, BAD))
    (target / "judges" / f"{BAD}.json").write_text(
        json.dumps({"lifecycle_status": status, "runs_model": False}),
        encoding="utf-8",
        newline="\n",
    )
    if defect == "missing-package":
        (venue / PACKAGE / "bad_judge").rename(venue / PACKAGE / "not_registered")

    assert invoke(command, target) == 0
    output = dict(line.split("=", 1) for line in capsys.readouterr().out.splitlines())
    if command == "night":
        assert json.loads(output["dates"])[0] == DATE
    else:
        assert {cell["tenant"] for cell in json.loads(output["matrix"])} == {FIRST}
    assert f"{PACKAGE}.bad_judge" not in sys.modules
    assert f"{PACKAGE}.bad_judge.tenant" not in sys.modules


def test_dependency_cause_survives_the_named_set_refusal(venue: Path) -> None:
    a_venue(venue, package=PACKAGE, slugs={BAD: (1, ())})
    (venue / PACKAGE / "bad_judge" / "tenant.py").write_text(
        "import missing_preflight_dependency\n", encoding="utf-8", newline="\n"
    )
    with pytest.raises(ValueError) as caught:
        registry.tenants((BAD,))
    assert isinstance(caught.value.__cause__, ModuleNotFoundError)
    assert caught.value.__cause__.name == "missing_preflight_dependency"


def test_diagnostic_rejects_a_judge_name_containing_source_text() -> None:
    with pytest.raises(ValueError):
        Diagnostic(kind="refusal", judge_id=HOSTILE)


def test_binding_the_live_tenant_defers_its_execution_imports() -> None:
    """A fresh process binds the active fixture without importing its stage closure."""
    code = """
import sys
from idhazh import config
from idhazh.council import registry
council = config.load_council()
registry.tenants(council.running(), council=council)
assert not any(name.startswith(("scipy", "numpy", "httpx")) for name in sys.modules)
assert not any(name.startswith("idhazh.stages.") for name in sys.modules)
"""
    env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "backend")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
