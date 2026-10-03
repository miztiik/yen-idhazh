"""What does every gardener test build before it asks its question?

Three things, each real. A config folder: the committed `config/idhazh.json`,
`config/appearance.json` and `config/idhazh_gardener.json`, with declarations
copied in from a fixture tree under `tests/fixtures/gardener/`. A package of
task modules, imported from `tests/fixtures/gardener/task_packages/` - real
modules that do real work through the real core. And a checkout with a bare
repository standing in for origin, so the commit loop pushes to something that
answers the way GitHub does, with no network (CLAUDE.md section 13).

Git runs with no machine configuration to fall back on, so a developer's own
settings - a signing key, a hook, an identity - cannot make a test pass or fail.
"""

from __future__ import annotations

import hashlib
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path
from types import ModuleType
from typing import Any, Final
from uuid import uuid4

import pytest
from conftest import CONFIG_DIR, FIXTURES_DIR, REPO_ROOT
from origin_template import copy_origin, template

from idhazh.gardener.registry import TaskModule

GARDENER_FIXTURES: Final = FIXTURES_DIR / "gardener"
TASK_PACKAGES: Final = GARDENER_FIXTURES / "task_packages"

#: The committed files a gardener config folder needs beside its declarations.
COMMITTED_FILES: Final = ("idhazh.json", "appearance.json", "idhazh_gardener.json")

#: The task declarations these integration fixtures exercise, not a directory census.
COMMITTED_DECLARATIONS: Final = (
    "compact-candidate-models.json",
    "compact-counterfactual-scores.json",
    "compact-feed-retirements.json",
    "compact-gardener.json",
    "compact-host-fingerprint.json",
    "compact-item-health.json",
    "compact-published.json",
    "compact-seen.json",
    "compact-summary-quality-evals.json",
    "compact-visual-prunes.json",
    "corpus-squash.json",
    "digest-fragments.json",
    "feed-health.json",
    "telemetry-aggregate.json",
    "traces.json",
    "trials.json",
    "visual-prune.json",
    "workflow-artifacts.json",
    "workflow-runs.json",
)

TASK_MODULES: Final = (
    "collection",
    "compaction",
    "corpus_squash",
    "digest_fragments",
    "feed_health",
    "telemetry_aggregate",
    "traces",
    "trials",
    "visual_prune",
)

FIXTURE_DECLARATIONS: Final = {
    "garden": (
        "compact-gardener.json",
        "day-validations.json",
        "feed-health.json",
        "history.json",
        "host-fingerprint.json",
        "seen.json",
        "telemetry-aggregate.json",
        "traces.json",
        "trials.json",
        "workflow-artifacts.json",
    ),
    "runner": ("compact-gardener.json", "old-days.json", "rehearsal.json"),
    "breaks": ("broken.json", "old-days.json"),
}

#: Who the seed commits are by. Not the repository's identity, on purpose: a
#: commit the gardener made is told from the seed by its author.
SEED_IDENTITY: Final = (
    "-c",
    "user.name=Scripted Origin",
    "-c",
    "user.email=origin@example.invalid",
)

#: One download a partial clone starts for itself, as a `GIT_TRACE` log records
#: it: a fetch handed the ids of the files it lacks on its input.
LAZY_FETCH: Final = re.compile(r"run_command: .*fetch.*--filter=blob:none --stdin")

#: How GitHub's blob API is asked for the size of one named file.
_BLOB_ROUTE: Final = re.compile(r"git/blobs/([0-9a-f]{40})")


def a_config(root: Path, *declarations: Path) -> Path:
    """A config folder under `root`: the committed files, plus these declarations.

    Each argument is a declaration file, a fixture folder, or the committed
    task folder, whose named integration inputs are copied.
    """
    config_dir = root / "config"
    (config_dir / "gardener").mkdir(parents=True, exist_ok=True)
    for name in COMMITTED_FILES:
        shutil.copyfile(CONFIG_DIR / name, config_dir / name)
    task_names: set[str] = set()
    for given in declarations:
        if given == CONFIG_DIR / "gardener":
            configured = json.loads(
                (config_dir / "idhazh_gardener.json").read_text(encoding="utf-8")
            )["task_names"]
            sources = [given / f"{name}.json" for name in configured]
        elif given.parent == GARDENER_FIXTURES:
            sources = [given / name for name in FIXTURE_DECLARATIONS[given.name]]
        elif given.is_dir():
            raise ValueError(f"test declarations must be named, not listed: {given}")
        else:
            sources = [given]
        for source in sources:
            shutil.copyfile(source, config_dir / "gardener" / source.name)
            task_names.add(source.stem)
    gardener_config = config_dir / "idhazh_gardener.json"
    gardener_settings = json.loads(gardener_config.read_text(encoding="utf-8"))
    gardener_settings["task_names"] = sorted(task_names)
    gardener_config.write_text(
        json.dumps(gardener_settings, indent=2) + "\n", encoding="utf-8"
    )
    return config_dir


def task_package(name: str, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """One fixture package, imported by its name from the fixture folder, for one test."""
    monkeypatch.syspath_prepend(str(TASK_PACKAGES))
    return importlib.import_module(name)


def named_task_modules() -> dict[str, TaskModule]:
    """Import the named task implementations without discovering the source tree."""
    modules: dict[str, TaskModule] = {}
    for stem in TASK_MODULES:
        module = importlib.import_module(f"idhazh.gardener.tasks.{stem}")
        modules[stem] = TaskModule(stem=stem, kind=module.KIND, run=module.run)
    return modules


def named_task_package(root: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Build a discoverable package from named real sources, never a source-tree walk."""
    name = f"garden_tasks_{uuid4().hex}"
    folder = root / name
    folder.mkdir()
    source = REPO_ROOT / "backend" / "idhazh" / "gardener" / "tasks"
    for stem in (
        "__init__",
        "_compact_tree",
        "_daily_period",
        "_index_day",
        "_monthly_period",
        "_yearly_period",
        *TASK_MODULES,
    ):
        shutil.copyfile(source / f"{stem}.py", folder / f"{stem}.py")
    monkeypatch.syspath_prepend(str(root))
    return importlib.import_module(name)


def quiet_git(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Git in this process and its children, with no machine configuration at all."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(home / "gitconfig"))
    monkeypatch.setenv("GIT_CONFIG_NOSYSTEM", "1")
    monkeypatch.setenv("GIT_TERMINAL_PROMPT", "0")
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)


def git(repo: Path, *args: str) -> str:
    """One git command in `repo`, as the seed's author, raising on failure."""
    done = subprocess.run(
        ["git", *SEED_IDENTITY, *args],
        cwd=repo,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0, f"git {' '.join(args)} failed: {done.stderr}"
    return done.stdout


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii", newline="\n")
    return path


def _build_origin(root: Path, files: dict[str, str]) -> None:
    """The bare origin holding these files in one commit, built in a template folder."""
    origin = root / "origin.git"
    git(root, "init", "--quiet", "--bare", "-b", "main", str(origin))
    seed = root / "seed"
    git(root, "clone", "--quiet", str(origin), str(seed))
    for relative, text in {"README.md": "seed\n", **files}.items():
        write(seed / relative, text)
    git(seed, "add", "--all")
    git(seed, "commit", "--quiet", "-m", "seed")
    git(seed, "push", "--quiet", "origin", "HEAD:refs/heads/main")


def an_origin(root: Path, files: dict[str, str]) -> tuple[Path, Path]:
    """A bare origin holding these files in one commit, and a clone of it to work in.

    The origin is built once per session for each distinct set of files and
    copied here, so the commit and push behind it are paid once. The copy is
    the test's own: it pushes to it, and nothing writes to what was copied.
    """
    held = hashlib.sha256(json.dumps(files, sort_keys=True).encode("utf-8")).hexdigest()
    built, unbuilt = template(("garden", held))
    if unbuilt:
        _build_origin(built, files)
    origin = root / "origin.git"
    copy_origin(built, origin)
    checkout = root / "checkout"
    git(root, "clone", "--quiet", str(origin), str(checkout))
    return origin, checkout


def read_origin(origin: Path, destination: Path, *paths: str) -> Path:
    """These paths of the origin's `main`, written under `destination` without a clone."""
    packed = subprocess.run(
        ["git", "archive", "--format=tar", "main", *paths],
        cwd=origin,
        env=os.environ.copy(),
        capture_output=True,
        check=True,
    ).stdout
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(packed)) as archive:
        archive.extractall(destination, filter="data")
    return destination


def on_origin(origin: Path, relative: str) -> str | None:
    """What `main` on the origin holds at this path, or None when it holds nothing.

    Read as bytes, because a record is parquet: text decoding would fail on it
    in the reader thread and look like a file that never landed.
    """
    done = subprocess.run(
        ["git", "show", f"main:{relative}"],
        cwd=origin,
        env=os.environ.copy(),
        capture_output=True,
        check=False,
    )
    return done.stdout.decode("utf-8", errors="replace") if done.returncode == 0 else None


def commits_on(origin: Path) -> list[str]:
    """Every commit on the origin's `main`, newest first, as `author: subject`."""
    return git(origin, "log", "--format=%an <%ae>: %s", "main").splitlines()


def a_hook(origin: Path, body: str) -> None:
    """A pre-receive hook on the origin, the way a racing push or a refusal is staged."""
    hook = origin / "hooks" / "pre-receive"
    hook.write_text(f"#!/bin/sh\n{body}\n", encoding="ascii", newline="\n")
    hook.chmod(0o755)


def a_partial_clone(root: Path, origin: Path, *cone: str, name: str = "shard") -> Path:
    """A wake's shard: a depth-1 partial clone of `origin` whose checkout holds only `cone`.

    A `file://` address, because a plain local clone copies every file and would
    hide a file the shard never downloaded; the origin serves the filter a
    partial clone asks for, and the objects it asks for later.
    """
    git(origin, "config", "uploadpack.allowFilter", "true")
    git(origin, "config", "uploadpack.allowAnySHA1InWant", "true")
    shard = root / name
    git(
        root,
        "clone",
        "--quiet",
        "--filter=blob:none",
        "--depth=1",
        "--sparse",
        origin.as_uri(),
        str(shard),
    )
    git(shard, "sparse-checkout", "set", "--cone", *cone)
    git(shard, "config", "index.sparse", "true")
    return shard


def lazy_fetches(trace: Path) -> int:
    """How many downloads a partial clone started for itself, in a `GIT_TRACE` log."""
    if not trace.is_file():
        return 0
    logged = trace.read_text(encoding="utf-8", errors="replace").splitlines()
    return sum(1 for line in logged if LAZY_FETCH.search(line))


class OriginBlobs:
    """GitHub's blob size endpoint, answered by the origin's own git.

    The origin holds the same blob objects GitHub holds, so git's byte count is
    the size endpoint's answer without returning any sibling names.
    """

    def __init__(self, origin: Path) -> None:
        self._origin = origin
        #: Every blob asked about, in order.
        self.asked: list[str] = []

    def read(self, path: str) -> dict[str, Any]:
        found = _BLOB_ROUTE.fullmatch(path)
        assert found is not None, f"only a named blob is asked for, not {path}"
        self.asked.append(found[1])
        return {"size": int(git(self._origin, "cat-file", "-s", found[1]))}
