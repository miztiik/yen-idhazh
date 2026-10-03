"""Does a shard that checks out only its code land what a shard that checks out every folder lands?

Over one fixture tree - the tree the retention tasks' record was taken over -
every shipped task a wake runs on this repository's files runs twice: once in
a full clone, where every file is on disk, and once in a partial clone whose
checkout holds only config, where a task learns its members from the commit's
names and fetches the folders it reads. Each lands on an origin of its own, and
the two must write the same record rows, apart from what each downloaded and
how long each took, and change the same paths.

The census summary is also run in a shard of its own, the way a wake can plan
it apart from the census compaction. It must still find its due months from
the census's names and read their rows, and with `reads` gone from its
declaration it must fail rather than report a census it never saw.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import pytest
from conftest import CONFIG_DIR

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.knobs.gardener import TaskKind
from idhazh.gardener import shards
from idhazh.gardener.outcome import EXIT_TASK_FAILED, Outcome
from utilities import gardener_publish

from .._garden import COMMITTED_DECLARATIONS, OriginTrees, a_config, a_partial_clone, git, quiet_git
from ._oracle_tree import RUN_ID, build

pytestmark = pytest.mark.slow

#: The wake both shards run at: 00:40 UTC on the day every window was drawn from.
WAKE: Final = datetime(2027, 11, 15, 0, 40, tzinfo=UTC)

#: The one task the census summary is, and the folder its summaries land in.
SUMMARY: Final = "telemetry-aggregate"
SUMMARIES: Final = "state/item-health-summary/"

#: A name the ledger door mints fresh for every file it writes.
_FILE_ID: Final = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

#: What two runs of one shard cannot agree on: the clock, and what each downloaded.
_OWN_TO_THE_RUN: Final = {"downloaded_bytes", "duration_ms"}


def a_live_garden(root: Path, **changed: dict[str, Any]) -> GardenerSettings:
    """The named committed declarations with their deletions and fold turned on.

    `changed` replaces fields of one declaration, by its name.
    """
    config_dir = a_config(root)
    for source in (CONFIG_DIR / "gardener" / name for name in COMMITTED_DECLARATIONS):
        declared = json.loads(source.read_text(encoding="utf-8"))
        declared["dry_run"] = False
        if isinstance(declared.get("fold"), dict):
            declared["fold"]["dry_run"] = False
        declared |= changed.get(source.stem.replace("-", "_"), {})
        (config_dir / "gardener" / source.name).write_text(json.dumps(declared), encoding="utf-8")
    return config.load_gardener(config_dir)


def in_the_repository(settings: GardenerSettings) -> tuple[str, ...]:
    """Every task a wake's shards run whose members are files in this repository."""
    planned = shards.plan(settings)
    elsewhere = (TaskKind.COLLECTION, TaskKind.HISTORY)
    return tuple(
        sorted(
            name
            for shard in planned.shards
            for name in shard.task_names
            if settings.tasks[name].kind not in elsewhere
        )
    )


def origins(root: Path, count: int) -> tuple[Path, list[Path]]:
    """The fixture tree committed once, and `count` bare origins that each hold that commit.

    The attributes are the repository's own, so each write is hashed the way a
    wake hashes it.
    """
    seed = build(root / "seed")
    (seed / ".gitattributes").write_text("* text=auto eol=lf\n", encoding="ascii")
    git(seed, "init", "--quiet", "-b", "main")
    git(seed, "add", "--all")
    git(seed, "commit", "--quiet", "-m", "seed")
    made: list[Path] = []
    for index in range(count):
        origin = root / f"origin-{index}.git"
        git(root, "init", "--quiet", "--bare", "-b", "main", str(origin))
        git(seed, "push", "--quiet", str(origin), "HEAD:refs/heads/main")
        made.append(origin)
    return seed, made


def a_full_clone(root: Path, origin: Path) -> Path:
    checkout = root / "full"
    git(root, "clone", "--quiet", str(origin), str(checkout))
    return checkout


def landed(
    names: tuple[str, ...], settings: GardenerSettings, checkout: Path, origin: Path
) -> tuple[Outcome, dict[str, CollectionPruneRow], list[str]]:
    said: list[str] = []
    outcome = gardener_publish.run_and_land(
        names,
        settings=settings,
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        trees=OriginTrees(origin),
        clock=lambda: WAKE,
        say=said.append,
    )
    assert outcome.record is not None, said
    rows = {row.task: row for row in ledger.load([outcome.record], model=CollectionPruneRow)}
    return outcome, rows, said


def changed_paths(origin: Path, seed: Path) -> list[str]:
    """What the shard's commit changed on the origin, a freshly named file under its pattern."""
    before = git(seed, "rev-parse", "HEAD").strip()
    listed = git(origin, "diff", "--name-status", "--no-renames", before, "main")
    return sorted(_FILE_ID.sub("<file_id>", line) for line in listed.splitlines())


def comparable(rows: dict[str, CollectionPruneRow]) -> dict[str, dict[str, Any]]:
    return {task: row.model_dump(exclude=_OWN_TO_THE_RUN) for task, row in rows.items()}


def test_a_shard_that_checks_out_only_code_lands_what_a_full_checkout_lands(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    quiet_git(tmp_path, monkeypatch)
    seed, (full_origin, names_origin) = origins(tmp_path, 2)
    settings = a_live_garden(tmp_path / "garden")
    names = in_the_repository(settings)
    full = a_full_clone(tmp_path, full_origin)
    only_code = a_partial_clone(tmp_path, names_origin, "config", name="only-code")

    whole, whole_rows, whole_said = landed(names, settings, full, full_origin)
    lean, lean_rows, lean_said = landed(names, settings, only_code, names_origin)

    assert lean.exit_code == whole.exit_code, (whole_said, lean_said)
    assert comparable(lean_rows) == comparable(whole_rows)
    changes = changed_paths(names_origin, seed)
    assert changes == changed_paths(full_origin, seed)
    assert any(line.startswith("D\t") for line in changes), "nothing was deleted"
    assert any(line.startswith("A\tstate/compact/") for line in changes), "no compaction wrote"
    row = next(iter(lean_rows.values()))
    assert row.cone_bytes is not None and row.downloaded_bytes is not None
    assert 0 < row.downloaded_bytes < row.cone_bytes, "the lean shard downloaded every folder"
    assert {each.downloaded_bytes for each in whole_rows.values()} == {0}


def test_the_census_summary_in_a_shard_of_its_own_reads_the_census_or_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Planned apart from the census compaction, it lists the census from the commit.

    It finds a month due from the census's file names, fetches that month and
    writes the summary a full checkout writes. Without `reads` its listing does
    not cover the census, so the task fails rather than find no month due.
    """
    quiet_git(tmp_path, monkeypatch)
    seed, (full_origin, names_origin, blind_origin) = origins(tmp_path, 3)
    settings = a_live_garden(tmp_path / "garden")
    assert SUMMARY in in_the_repository(settings)
    full = a_full_clone(tmp_path, full_origin)
    only_code = a_partial_clone(tmp_path, names_origin, "config", name="only-code")

    _, whole_rows, _ = landed((SUMMARY,), settings, full, full_origin)
    _, lean_rows, said = landed((SUMMARY,), settings, only_code, names_origin)

    assert lean_rows[SUMMARY].stopped_because is not StopReason.FAILED, said
    assert comparable(lean_rows) == comparable(whole_rows)
    written = [line for line in changed_paths(names_origin, seed) if SUMMARIES in line]
    assert written, "no month was due, so this shows nothing"
    assert written == [line for line in changed_paths(full_origin, seed) if SUMMARIES in line]
    for line in written:
        path = line.split("\t", 1)[1]
        assert git(names_origin, "show", f"main:{path}") == git(full_origin, "show", f"main:{path}")

    blind = a_live_garden(tmp_path / "blind-garden", telemetry_aggregate={"reads": []})
    shard = a_partial_clone(tmp_path, blind_origin, "config", name="blind")
    outcome, blind_rows, _ = landed((SUMMARY,), blind, shard, blind_origin)

    assert outcome.exit_code == EXIT_TASK_FAILED
    assert blind_rows[SUMMARY].stopped_because is StopReason.FAILED
    assert not [line for line in changed_paths(blind_origin, seed) if SUMMARIES in line]
