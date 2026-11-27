"""Does transient selection refuse altered or malformed requests before work?"""

import json
import sys
from pathlib import Path

import pytest

from idhazh import cli, config
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.knobs.council import JudgeRefusalError
from idhazh.council import night_plan, registry, session
from idhazh.council.model_selection import bind_model, verify_model
from idhazh.council.selection import SelectedJudge, Selection
from utilities import council_matrix, council_publish

from ._config import copy_config
from ._tenants import a_belated_venue, forget
from .test_lifecycle import room


def test_judge_preset_is_independent_and_admission_binds_its_bytes(tmp_path: Path) -> None:
    root = copy_config(tmp_path)
    council = config.load_council(root)
    (name,) = council.running()
    judge_file = root / "judges" / f"{name}.json"
    declaration = json.loads(judge_file.read_text(encoding="utf-8"))
    digest_preset = config.load_app(root).models_file
    alternate = "models/alternate-judge.json"
    other = json.loads((root / digest_preset).read_text(encoding="utf-8"))
    other["summarizer"].update(id="alternate-judge", sha256="0" * 64, declared_for="0" * 64)
    (root / alternate).write_text(json.dumps(other), encoding="utf-8")

    declaration["models_file"] = digest_preset
    judge_file.write_text(json.dumps(declaration), encoding="utf-8")
    same_model = bind_model(council, name)
    assert same_model is not None and same_model.model_id == config.load(root).models.summarizer.id

    declaration["models_file"] = alternate
    judge_file.write_text(json.dumps(declaration), encoding="utf-8")
    binding = bind_model(council, name)
    assert binding is not None and binding.weights_sha256 != same_model.weights_sha256
    settings = judge_settings.load_runtime(root)
    assert settings.explicit_models_file == binding.models_file
    assert settings.models.summarizer.id == binding.model_id
    assert config.load(root).models.summarizer.id == same_model.model_id

    selected = SelectedJudge(
        tenant=name, status=council.declaration(name).lifecycle_status,
        dates=("2026-11-26",), shards=1, model=binding,
    )
    assert verify_model(council, selected) == binding
    preset = root / binding.models_file
    preset.write_bytes(preset.read_bytes() + b"\n")
    with pytest.raises(JudgeRefusalError, match="selected model differs"):
        verify_model(council, selected)

    declaration.pop("models_file")
    judge_file.write_text(json.dumps(declaration), encoding="utf-8")
    with pytest.raises(JudgeRefusalError, match="models_file"):
        bind_model(council, name)
    assert config.load(root).models.summarizer.id == same_model.model_id


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
            run_id="2026-10-11-123",
            attempt=1,
            git_sha="a" * 40,
        )
        assert {judge.tenant: judge.dates for judge in selected.judges} == {
            "first": ("2026-10-10", "2026-10-09"),
            "second": ("2026-10-10", "2026-10-07"),
        }
        monkeypatch.setattr(session, "COUNCIL_ROOT", tmp_path / "scratch")
        session.prepare(council, date=None, run_id=selected.run_id, selection=selected)
        cells = council_matrix.cells(target, selection=selected)
        assert cells == [], "each plugin explicitly reports no work during preparation"
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
    if payload:
        raw = json.loads(payload)
        raw.update(
            run_id="2026-10-11-123",
            attempt=1,
            git_sha="a" * 40,
            anchor_date="2026-10-10",
            window=["2026-10-10", "2026-10-09"],
        )
        for judge in raw.get("judges", []):
            judge["shards"] = 1
        payload = json.dumps(raw)
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
                "--commit",
                "a" * 40,
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
                "run_id": "2026-10-11-123",
                "attempt": 1,
                "git_sha": "a" * 40,
                "anchor_date": "2026-10-10",
                "window": ["2026-10-10", "2026-10-09"],
                "judges": [
                    {"tenant": "first", "status": "active", "dates": ["2026-10-10"], "shards": 1},
                    {"tenant": "second", "status": "paused", "dates": ["2026-10-09"], "shards": 1},
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
                "run_id": "2026-10-11-123",
                "attempt": 1,
                "git_sha": "a" * 40,
                "anchor_date": "2026-10-10",
                "window": ["2026-10-10"],
                "judges": [
                    {
                        "tenant": "named-judge",
                        "status": "active",
                        "dates": ["2026-10-10"],
                        "shards": 1,
                    }
                ],
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
