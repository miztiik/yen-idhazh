"""Import bounded named data inputs, preserving the code HEAD, index and foreign work."""

from __future__ import annotations

import argparse
import shutil
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from utilities.publication_git import Repository

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def take_inputs(
    repo: Path,
    inputs: tuple[str, ...],
    resolve: Callable[[Repository, str], tuple[str, ...]] | None = None,
) -> str:
    """Validate and download the complete named import before changing local inputs."""
    from utilities.publication_git import Repository
    from utilities.publication_inputs import materialize, named_entries
    from utilities.publication_request import PLAIN_MODE, IntegrityError, safe_file

    git = Repository(repo)
    source = git.git("rev-parse", "HEAD").strip()
    previous = git.run("rev-parse", "--verify", "--quiet", "refs/worktree/publication-input-state")
    if previous.returncode == 0:
        source = previous.stdout.decode().strip()
    tip = git.fetch()
    if resolve is not None:
        inputs = tuple(set(inputs) | set(resolve(git, tip)))
    before = named_entries(git, source, inputs)
    after = named_entries(git, tip, inputs)
    # Validate the complete import before replacing or removing any named file.
    staged = set(git.git("diff", "--cached", "--name-only", "-z").split("\0")) - {""}
    for path in before.keys() | after.keys():
        if path in before and before[path][:2] != (PLAIN_MODE, "blob"):
            raise IntegrityError("source input is not a plain data file", (path,))
        git.parents_safe(source, path)
        target = safe_file(repo, path, exists=False)
        if path in staged:
            raise IntegrityError("named input has foreign pre-staged changes", (path,))
        if target.exists():
            if path not in before or target.read_bytes() != git.blob(before[path][2], fetches=True):
                raise IntegrityError("named input has foreign local changes", (path,))
    scratch = repo / "backend" / "var" / "publication" / f"inputs-{uuid4().hex}"
    scratch.mkdir(parents=True)
    try:
        materialize(git, tip, inputs, scratch)
        for path in after:
            target = safe_file(repo, path, exists=False)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((scratch / path).read_bytes())
        for path in before.keys() - after.keys():
            safe_file(repo, path, exists=False).unlink(missing_ok=True)
        git.git("update-ref", "refs/worktree/publication-input-state", tip)
    finally:
        shutil.rmtree(scratch)
    return tip


def main(argv: list[str] | None = None) -> int:
    from idhazh import config
    from utilities.digest_assemble import input_paths, resolved_inputs

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", choices=("state",))
    parser.add_argument("--date", default=datetime.now(UTC).date().isoformat())
    args = parser.parse_args(argv)
    settings = config.load()
    inputs = tuple(
        path for path in input_paths(date=args.date, settings=settings) if path.startswith("state/")
    )

    def state_inputs(git: Repository, tree: str) -> tuple[str, ...]:
        return tuple(
            path
            for path in resolved_inputs(git, tree, date=args.date, settings=settings)
            if path.startswith("state/")
        )

    tip = take_inputs(Path.cwd(), inputs, state_inputs)
    print(f"named state inputs taken from {tip}; code HEAD and index unchanged")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
