"""Does transient selection refuse altered or malformed requests before work?"""

import json
import sys
from pathlib import Path

import pytest

from idhazh import cli, config
from idhazh.council import night_plan, registry, session
from idhazh.council.selection import SelectedJudge, Selection
from utilities import council_matrix, council_publish

from ._tenants import a_belated_venue, forget
from .test_lifecycle import room


def test_each_judge_has_its_own_repair_cap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    package = "independent_repair_caps"
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    a_belated_venue(tmp_path, package=package, slug="first", behind_on=("2026-10-09", "2026-10-08"))
    a_belated_venue(
        tmp_path, package=package, slug="second", behind_on=("2026-10-07", "2026-10-06")
    )
    try:
        target = room(
            tmp_path,
            {"first": ("active", False), "second": ("active", True)},
            first_night="2026-10-01",
            repair_window_nights=6,
            repair_dates_a_night=1,
        )
        council = config.load_council(target)
        assert (
            council.first_night,
            council.repair_window_nights,
            council.repair_dates_a_night,
        ) == ("2026-10-01", 6, 1)
        selected = night_plan.plan_the_night(
            council,
            tonight="2026-10-10",
            hosted=registry.tenants(council.running(), council=council),
        )
        assert {judge.tenant: judge.dates for judge in selected.judges} == {
            "first": ("2026-10-10", "2026-10-09"),
            "second": ("2026-10-10", "2026-10-07"),
        }
        cells = council_matrix.cells(target, selection=selected)
        assert [cell["runs_model"] for cell in cells] == [False, False, True, True]
    finally:
        forget(package)


@pytest.mark.parametrize("command", ["matrix", "prepare", "shard", "settle", "publish"])
@pytest.mark.parametrize(
    "payload",
    [
        "",
        "{}",
        '{"mode":"manual","judges":[]}',
        '{"mode":"manual","judges":[{"tenant":"named-judge","status":"retired","dates":["2026-10-10"]}]}',
        '{"mode":"manual","judges":[{"tenant":"named-judge","status":"paused","dates":["2026-10-10"]}]}',
        '{"mode":"manual","judges":[{"tenant":"named-judge","status":"active","dates":["2026-02-30"]}]}',
        '{"mode":"manual","judges":[{"tenant":"named-judge","status":"active","dates":["2026-10-10","2026-10-09"]}]}',
        '{"mode":"manual","judges":[{"tenant":"source-text/../name","status":"active","dates":["2026-10-10"]}]}',
    ],
)
def test_every_consumer_refuses_invalid_selection_before_any_import_or_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    command: str,
    payload: str,
) -> None:
    package = "invalid_selection_judges"
    monkeypatch.setattr(registry, "TENANT_PACKAGE", package)
    monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "scratch")
    target = room(tmp_path, {"named-judge": ("active", False)})
    monkeypatch.setenv("COUNCIL_SELECTION", payload)
    if command == "matrix":
        code = council_matrix.main(["--config-root", str(target)])
    elif command == "publish":
        code = council_publish.main(
            [
                "--config-root",
                str(target),
                "--repo-root",
                str(tmp_path),
                "--run-id",
                "2026-10-11-123",
                "--commit",
                "a" * 40,
            ]
        )
    else:
        code = cli.main(
            [
                f"council-{command}",
                "--config",
                str(target),
                "--date",
                "2026-10-10",
                "--run-id",
                "2026-10-11-123",
                "--tenant",
                "named-judge",
            ]
        )
    assert code == 2
    assert f"{package}.named_judge.tenant" not in sys.modules
    assert not (tmp_path / "scratch").exists()
    assert not (tmp_path / "state").exists()
    assert "source-text" not in capsys.readouterr().err


def test_manual_selection_refuses_multiple_judges_with_different_dates() -> None:
    with pytest.raises(ValueError):
        Selection.model_validate(
            {
                "mode": "manual",
                "judges": [
                    {"tenant": "first", "status": "active", "dates": ["2026-10-10"]},
                    {"tenant": "second", "status": "paused", "dates": ["2026-10-09"]},
                ],
            }
        )


def test_a_selected_shard_cannot_run_another_date(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = room(tmp_path, {"named-judge": ("active", False)})
    council = config.load_council(target)
    selected = Selection.model_validate_json(
        json.dumps(
            {
                "mode": "manual",
                "judges": [{"tenant": "named-judge", "status": "active", "dates": ["2026-10-10"]}],
            }
        )
    )
    with pytest.raises(ValueError):
        session.run_shard(
            council,
            slug="named-judge",
            date="2026-10-09",
            run_id="2026-10-11-123",
            shard=0,
            shards=1,
            started=0,
            selection=selected,
        )
    assert isinstance(selected.judges[0], SelectedJudge)
