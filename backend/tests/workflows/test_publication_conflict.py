"""Does the real commit loop keep both writers' named publication entries?"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest
from conftest import FIXTURES_DIR, REPO_ROOT, read_text

from idhazh import assemble
from idhazh.contracts.digest_day import DigestDay
from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.publication import (
    initialize_inventory,
    read_inventory,
    record_day,
    record_files,
    record_month,
    record_state_files,
)
from utilities.publication_conflict import capture_publication_delta, replay_publication_delta

from ._harness import _run_commit_script, _write

pytestmark = pytest.mark.workflow


def _git(repo: Path, environment: dict[str, str], *args: str) -> str:
    result = subprocess.run(
        [
            "git",
            "-c",
            "user.name=miztiik",
            "-c",
            "user.email=miztiik@users.noreply.github.com",
            *args,
        ],
        cwd=repo,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _git_environment(tmp_path: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir()
    return {
        **{
            name: value
            for name, value in os.environ.items()
            if not name.startswith("GIT_CONFIG_")
            and name not in {"GITHUB_OUTPUT", "GITHUB_STEP_SUMMARY"}
        },
        "HOME": str(home),
        "USERPROFILE": str(home),
        "GIT_TERMINAL_PROMPT": "0",
    }


def _register_day(checkout: Path, day: DigestDay, *, index: bool = False) -> list[str]:
    public_root = checkout / "frontend" / "public"
    relative_dir = f"digest/{day.date.replace('-', '/')}"
    digest = public_root / relative_dir / "digest.json"
    _write(digest, day.to_json())
    _write(digest.with_name("run.json"), "{}\n")
    for item in day.items:
        if item.visual is not None:
            _write(digest.with_name(f"{item.item_id}.json"), "{}\n")
    inventory = record_day(public_root, day)
    if index:
        assemble.rebuild_search_index(
            digest_root=public_root / "digest",
            index_root=public_root / "assist" / "index",
            month=day.date[:7],
        )
        inventory = record_month(public_root, day.date[:7])
    return [
        "frontend/public/publication.json",
        *(f"frontend/public/{entry.path}" for entry in inventory.entries),
    ]


def test_replay_updates_and_removes_only_this_runs_named_entries(tmp_path: Path) -> None:
    local_public = tmp_path / "local" / "public"
    local_state = tmp_path / "local" / "state"
    initialize_inventory(
        local_public,
        seed=PublicationInventory(version=PublicationInventory.schema_version(), dates=[]),
    )
    changed = "series/changed.csv"
    removed = "series/removed.csv"
    untouched = "series/untouched.csv"
    state_name = "feed-health/ours.csv"
    remote_state_name = "feed-health/remote.csv"
    _write(local_public / changed, "old\n")
    _write(local_public / removed, "old\n")
    _write(local_public / untouched, "keep\n")
    _write(local_state / state_name, "old\n")
    record_files(local_public, paths=[changed, removed, untouched])
    record_state_files(local_public, local_state, paths=[state_name])
    before = read_inventory(local_public).to_json()

    _write(local_public / changed, "updated bytes\n")
    (local_public / removed).unlink()
    record_files(local_public, paths=[changed, removed])
    _write(local_state / state_name, "updated state\n")
    record_state_files(local_public, local_state, paths=[state_name])
    delta = capture_publication_delta(before, read_inventory(local_public).to_json())

    origin_public = tmp_path / "origin" / "public"
    origin_state = tmp_path / "origin" / "state"
    initialize_inventory(
        origin_public,
        seed=PublicationInventory(version=PublicationInventory.schema_version(), dates=[]),
    )
    _write(origin_public / changed, "old\n")
    _write(origin_public / removed, "old\n")
    _write(origin_public / untouched, "keep\n")
    _write(origin_public / "series/remote.csv", "remote\n")
    _write(origin_state / state_name, "old\n")
    _write(origin_state / remote_state_name, "other writer\n")
    record_files(origin_public, paths=[changed, removed, untouched, "series/remote.csv"])
    record_state_files(origin_public, origin_state, paths=[state_name, remote_state_name])

    _write(origin_public / changed, "updated bytes\n")
    (origin_public / removed).unlink()
    _write(origin_state / state_name, "updated state\n")
    replay_publication_delta(origin_public, origin_state, delta)

    inventory = read_inventory(origin_public)
    public_entries = {entry.path: entry for entry in inventory.entries if entry.root == "public"}
    state_entries = {entry.path: entry for entry in inventory.entries if entry.root == "state"}
    assert set(public_entries) == {changed, untouched, "series/remote.csv"}
    assert set(state_entries) == {state_name, remote_state_name}
    assert public_entries[changed].bytes == len("updated bytes\n")
    assert state_entries[state_name].bytes == len("updated state\n")
    assert inventory.total_bytes == sum(entry.bytes for entry in public_entries.values())
    assert inventory.total_items == 0


def test_two_checkouts_keep_both_real_publication_updates(
    tmp_path: Path,
) -> None:
    environment = _git_environment(tmp_path)
    origin = tmp_path / "origin.git"
    seed = tmp_path / "seed"
    _git(tmp_path, environment, "init", "--bare", "--initial-branch=main", str(origin))
    _git(tmp_path, environment, "clone", str(origin), str(seed))
    _write(seed / ".gitattributes", read_text(REPO_ROOT / ".gitattributes"))
    public_root = seed / "frontend" / "public"
    initialize_inventory(
        public_root,
        seed=PublicationInventory(version=PublicationInventory.schema_version(), dates=[]),
    )
    _git(seed, environment, "add", ".gitattributes", "frontend/public/publication.json")
    _git(seed, environment, "commit", "-m", "seed publication inventory")
    _git(seed, environment, "push", "-u", "origin", "main")

    first = tmp_path / "first"
    second = tmp_path / "second"
    _git(tmp_path, environment, "clone", str(origin), str(first))
    _git(tmp_path, environment, "clone", str(origin), str(second))

    fixture = DigestDay.read(FIXTURES_DIR / "contracts" / "digest-day" / "two-runs.json")
    first_paths = _register_day(first, fixture)
    second_day = fixture.model_copy(
        update={"date": "2026-08-22", "generated_at": "2026-08-22T18:22:05Z"}
    )
    second_paths = _register_day(second, second_day)
    settings = {
        "COMMIT_MESSAGE": "register publication files",
        "NOTHING_STAGED_MESSAGE": "nothing staged",
        "PUSH_FAILED_MESSAGE": "push failed",
        "GITHUB_JOB": "assemble",
    }
    first_result = _run_commit_script(first, environment, first_paths, settings)
    second_result = _run_commit_script(second, environment, second_paths, settings)

    assert first_result.returncode == 0, first_result.stderr
    assert second_result.returncode == 0, second_result.stderr
    assert '"prepared": true' in second_result.stdout
    assert _git(origin, environment, "log", "--format=%an <%ae>", "main", "-2").splitlines() == [
        "miztiik <miztiik@users.noreply.github.com>",
        "miztiik <miztiik@users.noreply.github.com>",
    ]

    payload = _git(origin, environment, "show", "main:frontend/public/publication.json")
    inventory = PublicationInventory.model_validate_json(payload)
    expected_paths = {
        entry.path
        for root in (first / "frontend" / "public", second / "frontend" / "public")
        for entry in read_inventory(root).entries
    }
    public_entries = [entry for entry in inventory.entries if entry.root == "public"]
    assert {entry.path for entry in public_entries} == expected_paths
    assert inventory.dates == ["2026-08-22", "2026-08-21"]
    assert inventory.total_items == len(fixture.items) + len(second_day.items)
    assert inventory.total_items > 0
    assert inventory.total_bytes == sum(entry.bytes for entry in public_entries)
    assert inventory.total_bytes > 0
    expected_items = {
        f"digest/{day.date.replace('-', '/')}/digest.json": len(day.items)
        for day in (fixture, second_day)
    }
    assert {entry.path: entry.items for entry in public_entries if entry.items} == expected_items
    assert inventory.total_bytes == sum(
        int(_git(origin, environment, "cat-file", "-s", f"main:frontend/public/{entry.path}"))
        for entry in public_entries
    )
