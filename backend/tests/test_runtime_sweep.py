"""Does a runtime repeat run Python with its exact plan and shard identity?"""

from pathlib import Path

from utilities.runtime_sweep import work_command


def test_work_command_keeps_the_exact_plan_and_shard(tmp_path: Path) -> None:
    command = work_command(
        config_root=tmp_path,
        date="2026-09-27",
        execution=123,
        shard=1,
        shards=2,
        commit_sha="a" * 40,
    )
    assert command[1:4] == ["-m", "idhazh", "work"]
    for flag, value in (
        ("--config", str(tmp_path)),
        ("--date", "2026-09-27"),
        ("--execution", "123"),
        ("--commit", "a" * 40),
        ("--shard", "1"),
        ("--shards", "2"),
    ):
        assert command[command.index(flag) + 1] == value
