"""Test helpers for isolated repositories and named standalone programs."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from fixture_git import command as fixture_git_command
from origin_template import copy_origin, template
from support.paths import CONFIG_DIR, REPO_ROOT, read_text

ACTIONS_DIR = REPO_ROOT / ".github" / "actions"

PROBE_URL_VALUE = "http://127.0.0.1:8080"
START_SERVER_MODULE = REPO_ROOT / "backend" / "utilities" / "model_runtime.py"

TAKE_STATE_MODULE = REPO_ROOT / "backend" / "utilities" / "take_state_from_the_tip.py"
PRUNE_PUSH_MODULE = REPO_ROOT / "backend" / "utilities" / "corpus_history.py"
SQUASH_DUE_MODULE = REPO_ROOT / "backend" / "utilities" / "corpus_squash_due.py"
GARDENER_PLAN_MODULE = REPO_ROOT / "backend" / "utilities" / "gardener_shards.py"
CRASH_TRACE_MODULE = REPO_ROOT / "backend" / "idhazh" / "crash_trace.py"
PACKAGE_INIT_MODULE = REPO_ROOT / "backend" / "idhazh" / "__init__.py"
PUBLISH_DECISION_MODULE = REPO_ROOT / "backend" / "utilities" / "publish_decision.py"

SUBSTITUTED_DATE = "2026-08-25"
SUBSTITUTED_EXECUTION = "40000000001"


def _copy_config(target: Path, *, models_file: str | None = None) -> None:
    """Copy only the named configs used by these tests."""
    pointer = json.loads(read_text(CONFIG_DIR / "idhazh.json"))["models_file"]
    names = (
        "idhazh.json",
        "llm_council.json",
        "judges/content-similarity-judge.json",
        "sources.json",
        "taxonomy.json",
        "watchlist.json",
        "appearance.json",
        "pipeline-tests.json",
        "push-retry.json",
        "llama-cpp-pin.json",
        "ledgers.json",
        pointer,
    )
    for name in names:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CONFIG_DIR / name, destination)
    if models_file is not None and models_file != pointer:
        destination = target / models_file
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(CONFIG_DIR / pointer, destination)


def _isolated_env(tmp_path: Path) -> dict[str, str]:
    """Run Git without machine identity, global config, or inherited step outputs."""
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    if sys.platform == "win32":
        (home / "gitconfig").write_text("[core]\n\tlongpaths = true\n", encoding="ascii")
    return {
        **{
            name: value
            for name, value in os.environ.items()
            if name not in {"GITHUB_OUTPUT", "PUSH_RETRY_CONFIG"}
        },
        "HOME": str(home),
        "USERPROFILE": str(home),
        "GIT_CONFIG_GLOBAL": str(home / "gitconfig"),
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
    }


def _git(repo: Path, env: dict[str, str], *args: str) -> str:
    completed = subprocess.run(
        fixture_git_command(
            repo,
            "-c",
            "user.name=Scripted Origin",
            "-c",
            "user.email=origin@example.invalid",
            *args,
        ),
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return completed.stdout


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="ascii", newline="\n")


def _seed_ledger(staged: str) -> str:
    return staged if staged.endswith((".csv", ".json")) else f"{staged}/ledger.csv"


def _fast_push_retry() -> dict[str, Any]:
    config: dict[str, Any] = json.loads(read_text(CONFIG_DIR / "push-retry.json"))
    config.update(base_step_seconds=0.003, ceiling_seconds=0.024)
    return config


def _seed_scripted_origin(root: Path, staged_paths: Sequence[str]) -> None:
    env = _isolated_env(root)
    origin = root / "origin.git"
    _git(root, env, "init", "--bare", "-b", "main", str(origin))
    seed = root / "seed"
    _git(root, env, "clone", str(origin), str(seed))
    for index, staged in enumerate(staged_paths):
        _write(seed / _seed_ledger(staged), f"header\nrow-{index}\n")
    _write(seed / "docs" / "unrelated.md", "seed\n")
    _write(seed / "runner-noise.txt", "clean\n")
    _write(seed / ".gitattributes", read_text(REPO_ROOT / ".gitattributes"))
    _write(seed / ".gitignore", read_text(REPO_ROOT / ".gitignore"))
    _write(seed / "config/push-retry.json", json.dumps(_fast_push_retry()) + "\n")
    _git(
        seed,
        env,
        "add",
        ".gitattributes",
        ".gitignore",
        "config/push-retry.json",
        "docs",
        "runner-noise.txt",
        *staged_paths,
    )
    _git(seed, env, "commit", "-m", "seed")
    _git(seed, env, "push", "-u", "origin", "main")


def _scripted_origin(
    tmp_path: Path, env: dict[str, str], staged_paths: Sequence[str]
) -> tuple[Path, Path]:
    """Create a private bare origin and the clone a job would check out."""
    root, unbuilt = template(("scripted", *staged_paths))
    if unbuilt:
        _seed_scripted_origin(root, staged_paths)
    origin = tmp_path / "origin.git"
    copy_origin(root, origin)
    runner = tmp_path / "runner"
    _git(tmp_path, env, "clone", str(origin), str(runner))
    return origin, runner


def _race(tmp_path: Path, env: dict[str, str], relative: str, text: str) -> None:
    """Push a competing change to the scripted origin."""
    other = tmp_path / "other"
    if not other.exists():
        _git(tmp_path, env, "clone", str(tmp_path / "origin.git"), str(other))
    _write(other / relative, text)
    _git(other, env, "add", relative)
    _git(other, env, "commit", "-m", "racing change")
    _git(other, env, "push", "origin", "main")


def _run_commit_script(
    runner: Path,
    env: dict[str, str],
    staged_paths: Sequence[str],
    settings: dict[str, str],
    *,
    authority: Sequence[str] = ("frontend/public",),
) -> subprocess.CompletedProcess[str]:
    """Drive the shared publisher with explicit fixture evidence."""
    import dataclasses

    from idhazh.contracts.base import ServerJob
    from idhazh.contracts.file_envelope import WriterIdentity
    from utilities.digest_publish import INVENTORY, inventory_preparation
    from utilities.publication_evidence import confirmed
    from utilities.publication_git import Repository
    from utilities.publication_request import PublicationRequest
    from utilities.publish_to_repo import publish
    from utilities.push_retry import PushRetry

    git = Repository(runner)
    source = _git(runner, env, "rev-parse", "HEAD").strip()
    hashes = {
        path: hashlib.sha256((runner / path).read_bytes()).hexdigest() for path in staged_paths
    }
    request = PublicationRequest(
        WriterIdentity(
            run_id=f"{SUBSTITUTED_DATE}-{SUBSTITUTED_EXECUTION}",
            attempt=1,
            job=ServerJob(settings.get("GITHUB_JOB", "work")),
            shard=0,
            producer="tests.completed-publication",
            git_sha=source,
        ),
        settings["COMMIT_MESSAGE"],
        source,
        tuple(authority),
        (),
        confirmed(git, hashes, source=source, permissions=tuple(authority), mutable=(INVENTORY,)),
        preparation_scopes=(INVENTORY,) if INVENTORY in hashes else (),
    )
    if INVENTORY in hashes:
        request = dataclasses.replace(request, prepare=inventory_preparation(runner, request))
    result = publish(
        request,
        repo=runner,
        retry=PushRetry({"default": 120}, 0.001, 0.001, 1),
    )
    return subprocess.CompletedProcess(
        ["shared-publisher"],
        result.exit_code,
        json.dumps(dataclasses.asdict(result), default=str),
        result.detail,
    )


def _reject_the_first_pushes(origin: Path, count: int) -> None:
    """Make the origin reject the next pushes before accepting later ones."""
    budget = origin / "reject-this-many-pushes"
    budget.write_text(f"{count}\n", encoding="utf-8", newline="\n")
    hook = origin / "hooks" / "pre-receive"
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        "#!/bin/sh\n"
        'budget="$(dirname "$0")/../reject-this-many-pushes"\n'
        'left=$(cat "$budget" 2>/dev/null || echo 0)\n'
        'if [ "$left" -gt 0 ]; then\n'
        '  echo $((left - 1)) > "$budget"\n'
        '  echo "rejecting this push on purpose, $left left" >&2\n'
        "  exit 1\n"
        "fi\n"
        "exit 0\n",
        encoding="utf-8",
        newline="\n",
    )
    hook.chmod(0o755)


def _mapping(value: object, description: str) -> dict[str, object]:
    assert isinstance(value, dict), f"{description} must be a mapping"
    return value
