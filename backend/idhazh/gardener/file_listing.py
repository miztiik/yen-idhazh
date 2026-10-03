"""Which files does the commit hold under a task's folders, and what does each weigh?

A gardener task decides from names: the day a file records, the month it falls
in, whether a picture is past its window. Those names come from one listing a
shard builds once, and each task is handed the part of it that covers the
folders its declaration owns or reads. A task never walks the disk to learn
what is there.

**Three builders make the same listing.** `from_paths` weighs only supplied
files and never discovers siblings. The migration uses it for named months.
`from_commit` takes what
`git ls-tree -r -l` printed for the commit the shard checked out. A file's size
is git's own where the clone holds the file, and GitHub's trees API's where the
clone never downloaded it: a blob id is a hash of the blob's size and bytes, so
one id has one size wherever it is read. `backend/utilities/gardener_publish.py`
runs git and calls it, because nothing under `backend/idhazh/` starts a process.
`from_disk` walks the folders as the checkout holds them, for
`idhazh gardener run-task`, which reads no commit, and for tests that build
plain fixture files.

**A folder outside the listing is refused, never read as empty.** A task that
asks for the names under a folder its declaration neither owns nor reads has a
declaration that forgot the folder, and an empty answer would be the silent
zero that lets a task report success over rows it could not see. A declared
folder the commit does not hold answers empty: nothing has written one yet.

**Content arrives before it is read, a folder at a time.** `fetch` widens the
checkout in one call, by whole folders or by the files directly inside a
file's own folder, and then checks that every listed file it brought is on
disk. A file the commit holds and the checkout lacks is fetched or the task
fails; it is never taken for a member that is not there. What the widening
added is what the shard downloaded for its tasks, and the record says so.

**A task sees what the shard's earlier tasks changed.** One task may read a
folder another task of its shard owns, so after each task the listing drops
what it deleted and adds what it wrote. A later task then decides from the
tree the shard will commit, and never fetches a file an earlier task deleted.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final, Protocol

#: A git object id as `git ls-tree` prints it: forty lowercase hex digits. A tree
#: id is put into an API address, so it is checked as an identity first.
_OBJECT_ID: Final = re.compile(r"^[0-9a-f]{40}$")


class FileNotFetchedError(Exception):
    """A file the commit holds is still not on disk after the checkout was widened for it."""


class TreeReader(Protocol):
    """The one call the size reader makes of GitHub: a GET, decoded."""

    def read(self, path: str) -> dict[str, Any]:
        """One GET under the repository, such as `git/trees/<id>?recursive=1`."""


@dataclass(frozen=True, slots=True)
class TreeEntry:
    """One file `git ls-tree -r -l` named: its path, its blob id, and its size when git knew it."""

    path: str
    blob: str
    #: None when the clone never downloaded the file, which git prints as `BAD`.
    size: int | None


def parse_tree(printed: str) -> list[TreeEntry]:
    """Every file in what `git ls-tree -r -l -z` printed. A submodule is not a file."""
    entries: list[TreeEntry] = []
    for record in printed.split("\0"):
        if not record:
            continue
        described, path = record.split("\t", 1)
        _, kind, blob, size = described.split()
        if kind == "blob":
            known = int(size) if size.isdigit() else None
            entries.append(TreeEntry(path=path, blob=blob, size=known))
    return entries


def sizes_from_github(api: TreeReader, trees: Iterable[str]) -> dict[str, int]:
    """Every file's size under these trees, by blob id, as GitHub's trees API reports it.

    One request a tree, each listing everything under it. A reply GitHub marks
    `truncated` left files out, so it is refused rather than read as complete.
    """
    sizes: dict[str, int] = {}
    for tree in trees:
        if not _OBJECT_ID.fullmatch(tree):
            raise ValueError(f"{tree!r} is not a git tree id, and it would go into an API address")
        reply = api.read(f"git/trees/{tree}?recursive=1")
        if reply.get("truncated"):
            raise ValueError(
                f"GitHub truncated its listing of tree {tree}, so some files have no size. "
                "A shard lists fewer folders, or the sizes are read another way"
            )
        for item in reply.get("tree", []):
            if item.get("type") == "blob":
                sizes[str(item["sha"])] = int(item["size"])
    return sizes


def _folder(name: str) -> str:
    """A repository folder as the listing spells it: POSIX, no trailing slash."""
    return name.strip().rstrip("/")


def _inside(path: str, folder: str) -> bool:
    """Whether a repository path is this folder or sits inside it."""
    return path == folder or path.startswith(f"{folder}/")


def _parent(path: str) -> str:
    return path.rpartition("/")[0]


@dataclass(slots=True)
class _Checkout:
    """What every task of one shard shares: the checkout, how to widen it, and what that added."""

    repo_root: Path
    #: Widens a sparse checkout by these entries in one call. None for a listing
    #: read off the disk, which has nothing to widen.
    widen: Callable[[Sequence[str]], None] | None
    #: Every folder the shard listed, which is what a download is counted under.
    folders: tuple[str, ...]
    #: Every file a widening put on disk, with its size.
    added: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FileListing:
    """The files under some folders, by repository path, and what each weighs."""

    #: The folders this listing answers for, sorted. Asking about anything else
    #: is refused.
    folders: tuple[str, ...]
    #: Every file the shard listed, by repository path, in path order. A task's
    #: view shares it and answers only for its own folders.
    sizes: Mapping[str, int]
    checkout: _Checkout

    @classmethod
    def from_paths(
        cls, repo_root: Path, paths: Iterable[Path], *, folders: Iterable[str]
    ) -> FileListing:
        """Weigh only supplied files under the declared folders, without discovering siblings."""
        chosen = tuple(sorted({_folder(folder) for folder in folders}))
        sizes: dict[str, int] = {}
        for path in sorted(set(paths)):
            name = path.relative_to(repo_root).as_posix()
            if not any(_inside(name, folder) for folder in chosen):
                raise ValueError(f"{name} is outside the listing's declared folders")
            sizes[name] = path.stat().st_size
        return cls(
            folders=chosen,
            sizes=sizes,
            checkout=_Checkout(repo_root=repo_root, widen=None, folders=chosen),
        )

    @classmethod
    def from_disk(cls, repo_root: Path, folders: Iterable[str]) -> FileListing:
        """Every file under these folders as the checkout holds them, weighed on disk."""
        chosen = tuple(sorted({_folder(folder) for folder in folders}))
        sizes: dict[str, int] = {}
        for folder in chosen:
            root = repo_root / folder
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if path.is_file():
                    sizes[path.relative_to(repo_root).as_posix()] = path.stat().st_size
        return cls(
            folders=chosen,
            sizes=dict(sorted(sizes.items())),
            checkout=_Checkout(repo_root=repo_root, widen=None, folders=chosen),
        )

    @classmethod
    def from_commit(
        cls,
        repo_root: Path,
        folders: Iterable[str],
        entries: Iterable[TreeEntry],
        github_sizes: Mapping[str, int],
        *,
        widen: Callable[[Sequence[str]], None],
    ) -> FileListing:
        """The files the commit holds under these folders, each with a size or a refusal.

        `github_sizes` answers, by blob id, for every file git printed no size
        for. A file neither can size is refused by name: a weight that skipped it
        would read low and say nothing.
        """
        chosen = tuple(sorted({_folder(folder) for folder in folders}))
        sizes: dict[str, int] = {}
        for entry in entries:
            if not any(_inside(entry.path, folder) for folder in chosen):
                continue
            size = entry.size if entry.size is not None else github_sizes.get(entry.blob)
            if size is None:
                raise ValueError(
                    f"{entry.path} has no size: this clone never downloaded blob {entry.blob}, "
                    "and GitHub's trees API did not report it"
                )
            sizes[entry.path] = size
        return cls(
            folders=chosen,
            sizes=dict(sorted(sizes.items())),
            checkout=_Checkout(repo_root=repo_root, widen=widen, folders=chosen),
        )

    @property
    def repo_root(self) -> Path:
        return self.checkout.repo_root

    def within(self, folders: Iterable[str]) -> FileListing:
        """The part of this listing that covers these folders, sharing its checkout."""
        chosen = tuple(sorted({_folder(folder) for folder in folders}))
        for folder in chosen:
            self._refuse_outside(folder)
        return FileListing(folders=chosen, sizes=self.sizes, checkout=self.checkout)

    def _relative(self, path: str | Path) -> str:
        """A repository path as the listing spells it; a `Path` sits under the checkout."""
        if isinstance(path, Path):
            return path.relative_to(self.repo_root).as_posix()
        return _folder(path)

    def _refuse_outside(self, path: str) -> None:
        if not any(_inside(path, folder) for folder in self.folders):
            raise ValueError(
                f"{path} is not under a folder this task owns or reads "
                f"({', '.join(self.folders) or 'it names none'}), so none of its names are "
                "listed. Declare the folder under owns or reads"
            )

    def files_under(self, folder: str | Path) -> list[str]:
        """Every listed file under this folder, as repository paths, in path order."""
        relative = self._relative(folder)
        self._refuse_outside(relative)
        return [path for path in self.sizes if path.startswith(f"{relative}/")]

    def paths_under(self, folder: str | Path) -> list[Path]:
        """Every listed file under this folder, as paths in the checkout, in path order."""
        return [self.repo_root / path for path in self.files_under(folder)]

    def holds(self, path: str | Path) -> bool:
        """Whether the commit holds this file."""
        relative = self._relative(path)
        self._refuse_outside(relative)
        return relative in self.sizes

    def size_of(self, path: str | Path) -> int:
        """What one listed file weighs, in bytes."""
        relative = self._relative(path)
        self._refuse_outside(relative)
        size = self.sizes.get(relative)
        if size is None:
            raise ValueError(f"{relative} is not a file the listing holds, so it has no size")
        return size

    def _brought(self, entry: str) -> list[str]:
        """What one widening entry puts on disk of what is listed.

        A sparse checkout takes a folder whole, and it always takes the files
        directly inside every folder above one it takes. An entry that names a
        file takes no folder, so it brings only the files beside it.
        """
        above: set[str] = set()
        parent = _parent(entry)
        while parent:
            above.add(parent)
            parent = _parent(parent)
        return [
            path for path in self.sizes if path.startswith(f"{entry}/") or _parent(path) in above
        ]

    def fetch(
        self, folders: Iterable[str | Path] = (), *, beside: Iterable[str | Path] = ()
    ) -> None:
        """Put these folders' files, and the files directly beside these files, on disk.

        One widening of the checkout for the whole call, which a partial clone
        serves with one download, by exactly the entries that bring a file the
        checkout lacks: a folder whose files an earlier task of this shard wrote
        is on disk already. A folder the commit does not hold is passed over,
        because there is nothing in it to read. Every listed file brought is on
        disk afterwards, or this raises naming the first one missing.
        """
        entries: list[str] = []
        for folder in folders:
            relative = self._relative(folder)
            self._refuse_outside(relative)
            if self.files_under(relative):
                entries.append(relative)
        for file in beside:
            relative = self._relative(file)
            self._refuse_outside(relative)
            if relative not in self.sizes:
                raise ValueError(f"{relative} is not a file the listing holds")
            entries.append(relative)
        wanted = {entry: self._brought(entry) for entry in entries}
        brought = sorted({path for paths in wanted.values() for path in paths})
        absent = [path for path in brought if not (self.repo_root / path).is_file()]
        if absent and self.checkout.widen is not None:
            lacking = set(absent)
            self.checkout.widen(
                [entry for entry, paths in wanted.items() if lacking.intersection(paths)]
            )
        missing = [path for path in absent if not (self.repo_root / path).is_file()]
        if missing:
            raise FileNotFetchedError(
                f"{missing[0]} is in the commit and still not on disk after the checkout was "
                f"widened for it ({len(missing)} such files). A task does not read an absent "
                "file as a missing member"
            )
        for path in absent:
            self.checkout.added[path] = self.sizes[path]

    def settled(self, *, written: Iterable[str], deleted: Iterable[str]) -> FileListing:
        """This listing after one task's changes, for the tasks of the shard that run later.

        A deleted file is no longer listed. A written file is listed with what it
        weighs on disk, where the task left it, when it sits under a listed folder.
        """
        sizes = dict(self.sizes)
        for path in deleted:
            sizes.pop(path, None)
        for path in written:
            on_disk = self.repo_root / path
            if on_disk.is_file() and any(_inside(path, folder) for folder in self.folders):
                sizes[path] = on_disk.stat().st_size
        return FileListing(
            folders=self.folders, sizes=dict(sorted(sizes.items())), checkout=self.checkout
        )

    def downloaded(self) -> dict[str, int] | None:
        """What the shard's widenings added, in bytes, under each folder it listed.

        None for a listing read off the disk, where nothing was downloaded.
        """
        if self.checkout.widen is None:
            return None
        weights = dict.fromkeys(self.checkout.folders, 0)
        for path, size in self.checkout.added.items():
            held = next(folder for folder in self.checkout.folders if _inside(path, folder))
            weights[held] += size
        return weights
