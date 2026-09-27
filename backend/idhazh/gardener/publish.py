"""How does a gardener shard land its one commit on main, however many shards race it?

The work happens once, before this is called. What is left is to stage exactly
what the shard wrote and deleted, commit it, and push - and to do that again
against a newer tip when another shard pushed first. Each try starts from
`origin/main` as it is now, so a lost race costs one fetch and one commit
rather than a merge.

**The record decides whether the shard has already landed.** Every shard writes
one record under the gardener's own ledger, and its bytes are unique to the
shard. If `origin/main` already holds that path with those bytes, an earlier try
landed and this one stops with success; the same path with other bytes is two
runs claiming one identity, and that is exit 2.

**Three checks run over what was staged, before every commit.** Every write is
staged, unless its bytes already equal `origin/main`'s, which is a write that
already landed. Nothing outside the shard's writes and deletions is staged. And
a deletion that staged nothing is an error only while the path still exists on
`origin/main`, because a path already gone is a deletion somebody finished.

**Exit codes, worst first:** 2 is ownership or integrity and is never retried;
3 is a push that kept losing and is retried at the next wake; 1 is a task that
failed and is retried at the next wake; 0 is everything landed. A shard reports
the worst code any part of it earned.
"""

from __future__ import annotations

import random
import subprocess
import time
from collections.abc import Callable
from pathlib import Path
from typing import Final, Self

from pydantic import Field, model_validator

from idhazh.contracts.base import Model, RelPath

EXIT_OK: Final = 0
EXIT_TASK_FAILED: Final = 1
EXIT_INTEGRITY: Final = 2
EXIT_PUSH_KEPT_LOSING: Final = 3

#: The four codes in the order a shard reports them: the worst one it earned.
_WORST_FIRST: Final = (EXIT_INTEGRITY, EXIT_PUSH_KEPT_LOSING, EXIT_TASK_FAILED, EXIT_OK)

#: The one identity every commit in this repository carries. The same two values
#: `backend/utilities/commit_and_push.py` sets, which a test holds in step: this
#: package cannot import a utility, so the value is written in both.
COMMITTER_NAME: Final = "miztiik"
COMMITTER_EMAIL: Final = "miztiik@users.noreply.github.com"

#: The branch every shard lands on, and the remote it is fetched from.
REMOTE: Final = "origin"
BRANCH: Final = "main"

#: The longest one wait between two tries, in seconds.
MAX_BACKOFF_SECONDS: Final = 8


def worst(*codes: int) -> int:
    """The worst of these exit codes, by the order above. No code at all is success."""
    return next((code for code in _WORST_FIRST if code in codes), EXIT_OK)


class Shard(Model):
    """What one shard hands the commit loop: its record, and every path it changed."""

    index: int = Field(ge=0, description="Which shard of the wake this is.")
    task_names: tuple[str, ...] = Field(description="The tasks it ran, in the order they ran.")
    record_path: RelPath = Field(description="The one record the shard wrote.")
    written_paths: frozenset[RelPath] = Field(
        description="Every file the shard wrote, the record among them."
    )
    deleted_paths: frozenset[RelPath] = Field(description="Every file the shard deleted.")

    @model_validator(mode="after")
    def _the_record_is_one_of_the_writes(self) -> Self:
        if self.record_path not in self.written_paths:
            raise ValueError("the shard's record is one of the files it writes")
        both = sorted(self.written_paths & self.deleted_paths)
        if both:
            raise ValueError(f"{', '.join(both)} is both written and deleted by one shard")
        return self


class Checkout:
    """The git commands the loop runs, all of them in one checkout."""

    def __init__(self, repo: Path) -> None:
        self._repo = repo

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args], cwd=self._repo, capture_output=True, text=True, check=False
        )

    def git(self, *args: str) -> str:
        """Run one command and hand back what it printed, or raise with what it said."""
        done = self._run(*args)
        if done.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {done.stderr.strip()}")
        return done.stdout

    def git_ok(self, *args: str) -> bool:
        """Run one command and say whether it worked, for the ones that may fail."""
        return self._run(*args).returncode == 0

    def remote_blob(self, path: str) -> str | None:
        """The object `origin/main` holds at this path, or None when it holds nothing there."""
        done = self._run("rev-parse", "--verify", "--quiet", f"{REMOTE}/{BRANCH}:{path}")
        return done.stdout.strip() if done.returncode == 0 else None

    def local_blob(self, path: str) -> str | None:
        """The object this checkout's file at this path would be, or None when there is none."""
        if not (self._repo / path).is_file():
            return None
        return self.git("hash-object", "--", path).strip()

    def staged_names(self) -> set[str]:
        """Every path the next commit would change."""
        return set(self.git("diff", "--cached", "--name-only", "-z").split("\0")) - {""}


def sleep_with_jitter(attempt: int, *, sleep: Callable[[float], None] = time.sleep) -> None:
    """Wait a random time before try `attempt + 1`, longer after each loss, never past the cap."""
    sleep(random.uniform(0, min(2 ** (attempt - 1), MAX_BACKOFF_SECONDS)))


def _refuse_a_directory(shard: Shard, repo: Path) -> str | None:
    """A deletion names one file. A folder here would stage everything under it."""
    for path in sorted(shard.deleted_paths):
        if (repo / path).is_dir():
            return f"{path} is a folder, and a shard deletes files one at a time"
    return None


def _what_staging_missed(shard: Shard, checkout: Checkout) -> str | None:
    """The three checks over what was staged, or None when the index is exactly the shard."""
    staged = checkout.staged_names()
    stray = sorted(staged - shard.written_paths - shard.deleted_paths)
    if stray:
        return f"{', '.join(stray)} staged, and this shard neither wrote nor deleted it"
    for path in sorted(shard.written_paths - staged):
        mine = checkout.local_blob(path)
        if mine is None or mine != checkout.remote_blob(path):
            return f"{path} was written and did not stage"
    for path in sorted(shard.deleted_paths - staged):
        if checkout.remote_blob(path) is not None:
            return f"{path} was deleted, did not stage, and {REMOTE}/{BRANCH} still holds it"
    return None


def publish(
    shard: Shard,
    message: str,
    *,
    attempts: int,
    repo: Path,
    say: Callable[[str], None] = print,
) -> int:
    """Stage, commit and push this shard, trying again on a newer tip, `attempts` times at most."""
    refused = _refuse_a_directory(shard, repo)
    if refused is not None:
        say(f"shard {shard.index}: {refused}")
        return EXIT_INTEGRITY
    checkout = Checkout(repo)
    for attempt in range(1, attempts + 1):
        checkout.git("fetch", "--quiet", REMOTE, BRANCH, "--depth=1")
        landed = checkout.remote_blob(shard.record_path)
        if landed is not None:
            if landed == checkout.local_blob(shard.record_path):
                say(f"shard {shard.index}: already on {BRANCH}, try {attempt}")
                return EXIT_OK
            say(
                f"shard {shard.index}: {shard.record_path} is on {BRANCH} with other bytes, "
                "so two runs claimed one record"
            )
            return EXIT_INTEGRITY
        checkout.git("reset", "--quiet", "--mixed", f"{REMOTE}/{BRANCH}")
        for path in sorted(shard.written_paths):
            checkout.git_ok("add", "--sparse", "--", path)
        for path in sorted(shard.deleted_paths):
            checkout.git_ok("rm", "--quiet", "--cached", "--sparse", "--ignore-unmatch", "--", path)
        missed = _what_staging_missed(shard, checkout)
        if missed is not None:
            say(f"shard {shard.index}: {missed}")
            return EXIT_INTEGRITY
        checkout.git(
            "-c",
            f"user.name={COMMITTER_NAME}",
            "-c",
            f"user.email={COMMITTER_EMAIL}",
            "commit",
            "--quiet",
            "-m",
            message,
        )
        if checkout.git_ok("push", "--quiet", REMOTE, f"HEAD:refs/heads/{BRANCH}"):
            say(f"shard {shard.index}: landed on {BRANCH}, try {attempt} of {attempts}")
            return EXIT_OK
        say(f"shard {shard.index}: try {attempt} of {attempts} lost the push")
        if attempt < attempts:
            sleep_with_jitter(attempt)
    return EXIT_PUSH_KEPT_LOSING
