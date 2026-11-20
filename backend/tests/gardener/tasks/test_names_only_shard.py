"""Can the standalone census summary find its input in a sparse checkout?"""

from __future__ import annotations

import json
import re
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any, Final

import pytest
from support.paths import CONFIG_DIR

from idhazh import config, ledger
from idhazh.config import GardenerSettings
from idhazh.contracts.collection_prune import CollectionPruneRow, StopReason
from idhazh.contracts.ledger_name import LedgerName
from idhazh.gardener.outcome import EXIT_TASK_FAILED, Outcome
from utilities import gardener_publish

from .._garden import (
    OriginBlobs,
    a_config,
    a_partial_clone,
    git,
    named_task_package,
    quiet_git,
)
from ._oracle_tree import RUN_ID, build

pytestmark = pytest.mark.slow

#: The wake both shards run at: 00:40 UTC on the day every window was drawn from.
WAKE: Final = datetime(2027, 11, 15, 0, 40, tzinfo=UTC)

#: The one task the census summary is, and the folder its summaries land in.
SUMMARY: Final = "telemetry-aggregate"
SUMMARIES: Final = "state/raw/item-health-summary/"

#: A name the ledger door mints fresh for every file it writes.
_FILE_ID: Final = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")

#: What two runs of one shard cannot agree on: the clock, and what each downloaded.
_OWN_TO_THE_RUN: Final = {"downloaded_bytes", "duration_ms"}


def a_live_garden(root: Path, **changed: dict[str, Any]) -> GardenerSettings:
    """The named committed declarations with their deletions turned on.

    `changed` replaces fields of one declaration, by its name.
    """
    config_dir = a_config(root, CONFIG_DIR / "gardener")
    names = json.loads((config_dir / "gardener/config/idhazh_gardener.json").read_text(encoding="utf-8"))[
        "task_names"
    ]
    for name in names:
        source = config_dir / "gardener" / f"{name}.json"
        declared = json.loads(source.read_text(encoding="utf-8"))
        declared["dry_run"] = False
        declared |= changed.get(source.stem.replace("-", "_"), {})
        (config_dir / "gardener" / source.name).write_text(json.dumps(declared), encoding="utf-8")
    return config.load_gardener(config_dir)


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
    names: tuple[str, ...],
    settings: GardenerSettings,
    checkout: Path,
    origin: Path,
    package: ModuleType,
) -> tuple[Outcome, dict[str, CollectionPruneRow], list[str]]:
    said: list[str] = []
    outcome = gardener_publish.run_and_land(
        names,
        settings=settings,
        repo_root=checkout,
        run_id=RUN_ID,
        attempt=1,
        shard=0,
        git_sha=git(checkout, "rev-parse", "HEAD").strip(),
        trees=OriginBlobs(origin),
        package=package,
        clock=lambda: WAKE,
        say=said.append,
    )
    assert outcome.record is not None, said
    rows = {row.task: row for row in ledger.load([outcome.record], model=CollectionPruneRow)}
    return outcome, rows, said


def changed_paths(origin: Path, seed: Path) -> list[str]:
    """What the shard's commit changed on the origin, a freshly named file under its pattern."""
    return sorted(_FILE_ID.sub("<file_id>", line) for line in raw_changed_paths(origin, seed))


def raw_changed_paths(origin: Path, seed: Path) -> list[str]:
    """What the shard's commit changed on the origin, with the file id intact."""
    before = git(seed, "rev-parse", "HEAD").strip()
    listed = git(origin, "diff", "--name-status", "--no-renames", before, "main")
    return sorted(listed.splitlines())


def _by_pattern(origin: Path, seed: Path) -> dict[str, str]:
    return {_FILE_ID.sub("<file_id>", line): line for line in raw_changed_paths(origin, seed)}


def blob(origin: Path, path: str) -> bytes:
    """One file from origin main, as bytes."""
    done = subprocess.run(
        ["git", "--git-dir", str(origin), "show", f"main:{path}"],
        cwd=origin,
        capture_output=True,
        check=True,
    )
    return done.stdout


def comparable(rows: dict[str, CollectionPruneRow]) -> dict[str, dict[str, Any]]:
    return {task: row.model_dump(exclude=_OWN_TO_THE_RUN) for task, row in rows.items()}


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
    full = a_full_clone(tmp_path, full_origin)
    only_code = a_partial_clone(tmp_path, names_origin, "config", name="only-code")
    package = named_task_package(tmp_path, monkeypatch)

    _, whole_rows, _ = landed((SUMMARY,), settings, full, full_origin, package)
    _, lean_rows, said = landed((SUMMARY,), settings, only_code, names_origin, package)

    assert lean_rows[SUMMARY].stopped_because is not StopReason.FAILED, said
    assert comparable(lean_rows) == comparable(whole_rows)
    names_changes = _by_pattern(names_origin, seed)
    full_changes = _by_pattern(full_origin, seed)
    written = [line for line in names_changes if SUMMARIES in line]
    assert written, "no month was due, so this shows nothing"
    assert written == [line for line in full_changes if SUMMARIES in line]
    for line in written:
        names_path = names_changes[line].split("\t", 1)[1]
        full_path = full_changes[line].split("\t", 1)[1]
        names_file = tmp_path / "names" / names_path
        full_file = tmp_path / "full" / full_path
        names_file.parent.mkdir(parents=True, exist_ok=True)
        full_file.parent.mkdir(parents=True, exist_ok=True)
        names_file.write_bytes(blob(names_origin, names_path))
        full_file.write_bytes(blob(full_origin, full_path))
        model = ledger.door_contract(LedgerName.ITEM_HEALTH_SUMMARY)
        assert ledger.load([names_file], model=model) == ledger.load([full_file], model=model)

    blind = a_live_garden(tmp_path / "blind-garden", telemetry_aggregate={"reads": []})
    shard = a_partial_clone(tmp_path, blind_origin, "config", name="blind")
    outcome, blind_rows, _ = landed((SUMMARY,), blind, shard, blind_origin, package)

    assert outcome.exit_code == EXIT_TASK_FAILED
    assert blind_rows[SUMMARY].stopped_because is StopReason.FAILED
    assert not [line for line in changed_paths(blind_origin, seed) if SUMMARIES in line]
