"""Commit named evaluation inputs without touching the producing job's checkout."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from tempfile import TemporaryDirectory

from idhazh.atomic_write import write_atomic, write_atomic_bytes
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.observation_lookup import (
    ObservationBatch,
    ObservationLookupNode,
    ObservationLookupReceipt,
    ObservationLookupRoot,
    ObservationPreparation,
)
from idhazh.evals.lookup_nodes import node_path, read_page
from idhazh.evals.observation_batches import incoming_path, input_root, lookup_root, save_batch
from idhazh.evals.observation_lookup import ROOT_NAME, ObservationLookup
from utilities.push_retry import DEFAULT_CONFIG

COMMIT_PROGRAM = Path(__file__).with_name("commit_and_push.py").resolve()
_JOB_COMMANDS = frozenset(
    {
        "REGENERATE_COMMAND",
        "DROP_RACED_ASSETS_COMMAND",
        "GITHUB_OUTPUT",
        "GIT_DIR",
        "GIT_COMMON_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_QUARANTINE_PATH",
        "GIT_PREFIX",
    }
)


def _git(
    root: Path, environment: Mapping[str, str], *arguments: str, input_text: str | None = None
) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        env=dict(environment),
        input=input_text,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _copy_git_file(
    checkout: Path,
    environment: Mapping[str, str],
    relative: str,
    destination: Path,
    reference: str,
) -> None:
    content = subprocess.run(
        ["git", "show", f"{reference}:{relative}"],
        cwd=checkout,
        env=dict(environment),
        capture_output=True,
        check=True,
    ).stdout
    write_atomic_bytes(destination, content)


def _receipts(
    checkout: Path,
    environment: Mapping[str, str],
    relative: Path,
    batch_ids: Sequence[str],
    destination: Path,
    reference: str,
) -> dict[str, ObservationLookupReceipt]:
    """Materialize only named receipt routes, never the archive or the whole index."""
    root_path = (relative / ROOT_NAME).as_posix()
    if not _git(checkout, environment, "ls-tree", reference, "--", root_path):
        return {}
    _copy_git_file(checkout, environment, root_path, destination / ROOT_NAME, reference)
    root = ObservationLookupRoot.read(destination / ROOT_NAME)
    keys = {derive_text_digest(canonical_json(["batch", batch_id])) for batch_id in batch_ids}

    def hydrate(node: ObservationLookupNode, prefix: str, wanted: set[str]) -> None:
        path = node_path(destination, node)
        _copy_git_file(
            checkout,
            environment,
            (relative / path.relative_to(destination)).as_posix(),
            path,
            reference,
        )
        if node.kind == "page":
            page = read_page(destination, node, prefix, root.settings.max_leaf_bytes)
            for digit, child in page.children.items():
                matching = {key for key in wanted if key[len(prefix)] == digit}
                if matching:
                    hydrate(child, prefix + digit, matching)

    hydrate(root.node, "", keys)
    with ObservationLookup(destination) as lookup:
        entries = lookup.find("batch", batch_ids)
        return {
            identity: entry.receipt
            for identity, entry in entries.items()
            if entry.receipt is not None
        }


def committed_receipts(
    state_dir: Path, batch_ids: Sequence[str]
) -> dict[str, ObservationLookupReceipt]:
    """An uncommitted local receipt must never stand in for a completed publication."""
    if not batch_ids:
        return {}
    for batch_id in batch_ids:
        incoming_path(state_dir, batch_id)
    repository = Path(_git(state_dir.parent, os.environ, "rev-parse", "--show-toplevel"))
    with TemporaryDirectory(prefix="evaluation-receipts-") as directory:
        return _receipts(
            repository,
            os.environ,
            lookup_root(state_dir).relative_to(repository),
            batch_ids,
            Path(directory),
            "HEAD",
        )


def _forward_checkout_credentials(repository: Path, environment: dict[str, str]) -> None:
    credentials = subprocess.run(
        ["git", "config", "--null", "--get-regexp", r"^http\..*\.extraheader$"],
        cwd=repository,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    if credentials.returncode not in {0, 1}:
        raise RuntimeError("could not read the checkout's Git authentication configuration")
    count = int(environment.get("GIT_CONFIG_COUNT", "0"))
    for record in filter(None, credentials.stdout.split("\0")):
        key, value = record.split("\n", 1)
        environment[f"GIT_CONFIG_KEY_{count}"] = key
        environment[f"GIT_CONFIG_VALUE_{count}"] = value
        count += 1
    environment["GIT_CONFIG_COUNT"] = str(count)


def prepare_inputs(
    state_dir: Path,
    batches: Sequence[ObservationBatch],
    *,
    environment: Mapping[str, str] | None = None,
) -> list[str]:
    """Prepare only named inbox files against HEAD, without fetching or publishing."""
    if not batches:
        return []
    state_dir = state_dir.resolve()
    inherited = os.environ if environment is None else environment
    repository = Path(_git(state_dir.parent, inherited, "rev-parse", "--show-toplevel"))
    named = {
        incoming_path(state_dir, batch.batch_id).relative_to(repository).as_posix(): batch
        for batch in batches
    }
    with TemporaryDirectory(prefix="evaluation-inbox-receipts-") as directory:
        receipts = _receipts(
            repository,
            inherited,
            lookup_root(state_dir).relative_to(repository),
            [batch.batch_id for batch in batches],
            Path(directory),
            "HEAD",
        )
    for path, batch in named.items():
        receipt = receipts.get(batch.batch_id)
        destination = repository / path
        if receipt is not None:
            if receipt.payload_sha256 != batch.payload_sha256:
                raise ValueError("a committed evaluation receipt differs from its sealed batch")
            destination.unlink(missing_ok=True)
        elif destination.exists():
            if ObservationBatch.read(destination) != batch:
                raise ValueError("a committed evaluation input differs from its sealed batch")
        else:
            write_atomic(destination, batch.to_json())
    return list(named)


def publish_inputs(
    state_dir: Path,
    batches: Sequence[ObservationBatch],
    *,
    environment: Mapping[str, str] | None = None,
) -> None:
    """Git serializes the inbox commit; only the named inputs enter its sparse clone."""
    if not batches:
        return
    inherited = os.environ if environment is None else environment
    isolated = {
        name: value
        for name, value in inherited.items()
        if name not in _JOB_COMMANDS and not name.startswith(("REFRESH", "PREPARE"))
    }
    repository = Path(_git(state_dir.parent, isolated, "rev-parse", "--show-toplevel"))
    retry_config = (repository / isolated.get("PUSH_RETRY_CONFIG", str(DEFAULT_CONFIG))).resolve()
    origin = _git(repository, isolated, "remote", "get-url", "origin")
    push_origin = _git(repository, isolated, "remote", "get-url", "--push", "origin")
    _forward_checkout_credentials(repository, isolated)
    named = {
        incoming_path(state_dir, batch.batch_id).relative_to(repository).as_posix(): batch
        for batch in batches
    }
    with TemporaryDirectory(prefix="evaluation-inbox-") as directory:
        checkout = Path(directory).resolve() / "checkout"
        _git(
            repository,
            isolated,
            "clone",
            "--shared",
            "--no-checkout",
            str(repository),
            str(checkout),
        )
        _git(checkout, isolated, "remote", "set-url", "origin", origin)
        _git(checkout, isolated, "remote", "set-url", "--push", "origin", push_origin)
        _git(checkout, isolated, "fetch", "origin", "refs/heads/main:refs/remotes/origin/main")
        _git(
            checkout,
            isolated,
            "sparse-checkout",
            "set",
            "--no-cone",
            "--stdin",
            input_text="".join(f"/{path}\n" for path in named),
        )
        _git(checkout, isolated, "checkout", "-B", "main", "origin/main")
        _git(checkout, isolated, "branch", "--set-upstream-to=origin/main", "main")
        state = checkout / state_dir.relative_to(repository)
        local_inputs = input_root(state)
        excluded = checkout / _git(checkout, isolated, "rev-parse", "--git-path", "info/exclude")
        write_atomic(
            excluded,
            excluded.read_text(encoding="utf-8")
            + f"\n/{local_inputs.relative_to(checkout).as_posix()}/\n",
        )
        for batch in batches:
            save_batch(state, batch)
        manifest = local_inputs / "inbox.json"
        write_atomic(
            manifest,
            ObservationPreparation.model_validate(
                {"batches": [batch.batch_id for batch in batches], "paths": []}
            ).to_json(),
        )
        paths = prepare_inputs(state, batches, environment=isolated)
        if not _git(
            checkout, isolated, "status", "--porcelain", "--untracked-files=all", "--", *paths
        ):
            return
        prepared = (local_inputs / "inbox-paths.json").relative_to(checkout).as_posix()
        subprocess.run(
            [sys.executable, str(COMMIT_PROGRAM), "--update"],
            cwd=checkout,
            env={
                **isolated,
                "PYTHONPATH": os.pathsep.join(
                    filter(None, [str(COMMIT_PROGRAM.parent.parent), isolated.get("PYTHONPATH")])
                ),
                "COMMIT_MESSAGE": "Record pending evaluation inputs",
                "NOTHING_STAGED_MESSAGE": "Evaluation inputs are already durable",
                "PUSH_FAILED_MESSAGE": "Could not publish pending evaluation inputs",
                "PUSH_RETRY_CONFIG": str(retry_config),
                "PREPARE_COMMAND": " ".join(
                    [
                        sys.executable,
                        str(COMMIT_PROGRAM.with_name("prepare_evaluation_publication.py")),
                        "--inbox-only",
                        "--state-dir", state.relative_to(checkout).as_posix(),
                        "--inputs", manifest.relative_to(checkout).as_posix(),
                        "--paths-file", prepared,
                    ]
                ),
                "PREPARED_PATHS_FILE": prepared,
            },
            check=True,
        )