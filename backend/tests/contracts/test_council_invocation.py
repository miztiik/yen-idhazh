"""Do invocation documents refuse unauthorized work while permitting explicit no work?"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from idhazh.contracts.council_invocation import (
    ArtifactFile,
    JudgeSchedule,
    PreparationReceipt,
    ScheduleRequest,
    Selection,
    ShardFiles,
)

pytestmark = pytest.mark.contract
IDENTITY = {"run_id": "2026-11-05-1", "attempt": 1, "git_sha": "a" * 40}
FILE = {"path": "2026-11-04/tasks/paper-judge/task.json", "size_bytes": 2, "sha256": "b" * 64}


def test_scheduled_selection_retains_an_explicitly_declining_plugin() -> None:
    selected = Selection.model_validate(
        IDENTITY
        | {
            "mode": "scheduled",
            "anchor_date": "2026-11-04",
            "window": ("2026-11-04",),
            "judges": ({"tenant": "paper-judge", "status": "active", "dates": (), "shards": 1},),
        }
    )
    assert selected.names() == ("paper-judge",)
    assert selected.dates == ()
    assert Selection.from_json(selected.to_json()) == selected


@pytest.mark.parametrize(
    "dates",
    [
        ("2026-11-04", "2026-11-04"),
        ("2026-02-30",),
        ("2026-11-02",),
        ("2026-11-03", "2026-11-01"),
    ],
)
def test_schedule_is_refused_not_repaired(dates: tuple[str, ...]) -> None:
    request = ScheduleRequest(
        anchor_date="2026-11-04",
        window=("2026-11-04", "2026-11-03", "2026-11-01"),
        max_dates=2,
        max_older_dates=1,
        shards=1,
        shard_seconds=10,
    )
    with pytest.raises(ValueError):
        JudgeSchedule(dates=dates).check(request)


@pytest.mark.parametrize(
    ("state", "shards", "files", "error"),
    [
        ("ready", 0, (FILE,), None),
        ("ready", 1, (), None),
        ("no_work", 1, (), None),
        ("failed", 0, (FILE,), "ValueError"),
        ("failed", 0, (), None),
        ("ready", 1, (FILE, FILE), None),
    ],
)
def test_preparation_state_cannot_invent_work(
    state: str,
    shards: int,
    files: tuple[dict[str, object], ...],
    error: str | None,
) -> None:
    with pytest.raises(ValidationError):
        PreparationReceipt.model_validate(
            IDENTITY
            | {
                "judge_id": "paper-judge",
                "date": "2026-11-04",
                "state": state,
                "shards": shards,
                "files": files,
                "error": error,
            }
        )


def test_no_work_can_carry_bookkeeping_without_a_model_job() -> None:
    receipt = PreparationReceipt.model_validate(
        IDENTITY
        | {
            "judge_id": "paper-judge",
            "date": "2026-11-04",
            "state": "no_work",
            "shards": 0,
            "files": (FILE,),
        }
    )
    assert PreparationReceipt.from_json(receipt.to_json()) == receipt


@pytest.mark.parametrize(
    "path",
    [
        "/absolute",
        "C:/file",
        "../file",
        "date/../file",
        "date\\file",
        "date/*.json",
    ],
)
def test_file_addresses_are_relative_and_literal(path: str) -> None:
    with pytest.raises(ValidationError):
        ArtifactFile.model_validate(FILE | {"path": path})


def test_shard_width_and_index_are_strict() -> None:
    for update in ({"shard": 1}, {"shards": 0}, {"shard": True}, {"shards": 1.0}):
        with pytest.raises(ValidationError):
            ShardFiles.model_validate(
                IDENTITY
                | {
                    "judge_id": "paper-judge",
                    "date": "2026-11-04",
                    "shard": 0,
                    "shards": 1,
                    "files": (),
                }
                | update,
            )
