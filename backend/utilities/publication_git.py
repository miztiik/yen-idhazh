"""Which literal Git operations build a candidate without changing the user's index?"""

from __future__ import annotations

import hashlib
import os
import subprocess
import time
from contextvars import ContextVar
from pathlib import Path, PurePosixPath
from uuid import uuid4

from utilities.publication_request import PLAIN_MODE, Entry, IntegrityError, PublicationRequest

COMMITTER_NAME = "miztiik"
COMMITTER_EMAIL = "miztiik@users.noreply.github.com"
TRAILER = "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
INVOCATION_DEADLINE: ContextVar[float | None] = ContextVar("publication-deadline", default=None)


class Repository:
    """All Git calls are literal and lazy fetching is opt-in."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self._entries: dict[tuple[str, str], Entry | None] = {}
        self.deadline: float | None = None

    def prime(self, tree: str, paths: set[str]) -> None:
        """Read only named entries and their parents, in bounded argv batches."""
        names = sorted(
            paths
            | {
                parent.as_posix()
                for path in paths
                for parent in PurePosixPath(path).parents
                if parent.parts
            }
        )
        batch: list[str] = []
        size = 0
        for path in names:
            if size + len(path) > 16000 and batch:
                self._prime_batch(tree, batch)
                batch, size = [], 0
            batch.append(path)
            size += len(path) + 1
        if batch:
            self._prime_batch(tree, batch)

    def _prime_batch(self, tree: str, paths: list[str]) -> None:
        for path in paths:
            self._entries[tree, path] = None
        for line in self.git("ls-tree", "-z", tree, "--", *paths).split("\0"):
            if line:
                metadata, name = line.split("\t", 1)
                mode, _, oid = metadata.split()
                self._entries[tree, name] = Entry(mode, oid)

    def run(
        self,
        *args: str,
        data: bytes | None = None,
        index: Path | None = None,
        fetches: bool = False,
    ) -> subprocess.CompletedProcess[bytes]:
        env = dict(os.environ)
        env.pop("GIT_INDEX_FILE", None)
        if not fetches:
            env["GIT_NO_LAZY_FETCH"] = "1"
        else:
            env.pop("GIT_NO_LAZY_FETCH", None)
        if index is not None:
            env["GIT_INDEX_FILE"] = str(index)
            args = ("-c", "core.sparseCheckout=false", "-c", "index.sparse=false", *args)
        deadline = self.deadline if self.deadline is not None else INVOCATION_DEADLINE.get()
        remaining = deadline - time.monotonic() if deadline is not None else None
        if remaining is not None and remaining <= 0:
            raise RuntimeError("publication deadline expired before Git operation")
        return subprocess.run(
            ["git", *(("--literal-pathspecs",) if "check-ignore" not in args else ()), *args],
            input=data,
            cwd=self.repo,
            capture_output=True,
            env=env,
            check=False,
            timeout=remaining,
        )

    def git(
        self,
        *args: str,
        data: bytes | None = None,
        index: Path | None = None,
        fetches: bool = False,
    ) -> str:
        done = self.run(*args, data=data, index=index, fetches=fetches)
        if done.returncode:
            raise RuntimeError(f"git {args[0]}: {done.stderr.decode('utf-8', errors='replace')}")
        return done.stdout.decode("utf-8")

    def fetch(self) -> str:
        depth = (
            ("--depth=1",)
            if self.git("rev-parse", "--is-shallow-repository").strip() == "true"
            else ()
        )
        self.git(
            "fetch",
            "--quiet",
            "--no-tags",
            *depth,
            "origin",
            "+refs/heads/main:refs/remotes/origin/main",
        )
        return self.git("rev-parse", "--verify", "origin/main").strip()

    def entry(self, tree: str, path: str) -> Entry | None:
        if (tree, path) in self._entries:
            return self._entries[tree, path]
        listed = self.git("ls-tree", "-z", tree, "--", path).split("\0")
        for line in listed:
            if line:
                metadata, name = line.split("\t", 1)
                if name == path:
                    mode, _, oid = metadata.split()
                    entry = Entry(mode, oid)
                    self._entries[tree, path] = entry
                    return entry
        self._entries[tree, path] = None
        return None

    def parents_safe(self, tree: str, path: str) -> None:
        for parent in PurePosixPath(path).parents:
            if not parent.parts:
                break
            entry = self.entry(tree, parent.as_posix())
            if entry is not None and entry.mode != "040000":
                raise IntegrityError("source parent is not a directory", (path,))

    def index_entry(self, path: str) -> Entry | None:
        listed = self.git("ls-files", "--stage", "-z", "--", path)
        for line in listed.split("\0"):
            if not line:
                continue
            metadata, name = line.split("\t", 1)
            if name == path:
                mode, oid, stage = metadata.split()
                if stage != "0":
                    raise IntegrityError("named output has an unresolved index entry", (path,))
                return Entry(mode, oid)
        return None

    def blob(self, oid: str, *, fetches: bool = False) -> bytes:
        done = self.run("cat-file", "blob", oid, fetches=fetches)
        if done.returncode:
            raise RuntimeError(f"required blob {oid} is not materialized")
        return done.stdout

    def objects(self, request: PublicationRequest) -> dict[str, Entry]:
        """Check the filtered bytes Git will actually put in the candidate."""
        entries: dict[str, Entry] = {}
        checked = self.run(
            "check-ignore",
            "--no-index",
            "-z",
            "--stdin",
            data="".join(path + "\0" for path in request.writes).encode(),
        )
        if checked.returncode not in (0, 1):
            raise RuntimeError(
                "Git could not check named ignored outputs: "
                + checked.stderr.decode(errors="replace")
            )
        ignored = set(checked.stdout.decode().split("\0")) - {""}
        for path, write in request.writes.items():
            if path in ignored and write.baseline is None:
                raise IntegrityError("ignored write was written and did not stage", (path,))
            oid = self.git("hash-object", "-w", f"--path={path}", "--", path).strip()
            if hashlib.sha256(self.blob(oid)).hexdigest() != write.sha256:
                raise IntegrityError("Git filter changed confirmed bytes", (path,))
            entries[path] = Entry(PLAIN_MODE, oid)
        return entries

    def candidate(self, base: str, request: PublicationRequest, entries: dict[str, Entry]) -> str:
        named = self.git("rev-parse", "--git-path", f"publish-{uuid4().hex}.index").strip()
        index = Path(named)
        if not index.is_absolute():
            index = self.repo / index
        try:
            self.git("read-tree", base, index=index)
            lines = [f"{entry.mode} {entry.oid}\t{path}\0" for path, entry in entries.items()]
            lines += [f"0 {'0' * 40}\t{path}\0" for path in request.deletions]
            if lines:
                self.git(
                    "update-index",
                    "-z",
                    "--index-info",
                    data="".join(lines).encode("utf-8"),
                    index=index,
                )
            tree = self.git("write-tree", "--missing-ok", index=index).strip()
            self.prime(tree, set(entries) | set(request.deletions))
            for path, expected in entries.items():
                if self.entry(tree, path) != expected:
                    raise IntegrityError("candidate does not contain confirmed write", (path,))
            for path in request.deletions:
                if self.entry(tree, path) is not None:
                    raise IntegrityError("candidate does not contain deletion", (path,))
            changed = set(
                self.git(
                    "diff-tree",
                    "-r",
                    "--no-renames",
                    "--name-only",
                    "-z",
                    base,
                    tree,
                ).split("\0")
            ) - {""}
            if changed - request.writes.keys() - request.deletions.keys():
                raise IntegrityError("candidate contains foreign changes", tuple(sorted(changed)))
            message = request.message
            if TRAILER not in message:
                message += "\n\n" + TRAILER
            return self.git(
                "-c",
                f"user.name={COMMITTER_NAME}",
                "-c",
                f"user.email={COMMITTER_EMAIL}",
                "commit-tree",
                tree,
                "-p",
                base,
                "-m",
                message,
            ).strip()
        finally:
            index.unlink(missing_ok=True)
            Path(str(index) + ".lock").unlink(missing_ok=True)

    def push(self, candidate: str) -> bool:
        return (
            self.run(
                "push", "--quiet", "--no-thin", "origin", f"{candidate}:refs/heads/main"
            ).returncode
            == 0
        )
