"""Which files does the commit hold under a task's folders, and what does each weigh?

A gardener task decides from names: the day a file records, the month it falls
in, whether a picture is past its window. Those names come from one listing a
shard builds once, and each task is handed the part of it that covers the
folders its declaration owns or reads. A task never walks the disk to learn
what is there.

**Three builders make the same listing, and each records the paths it was
given.** `from_paths` weighs only supplied files and never discovers siblings.
`from_commit` takes what `git ls-tree -r -l` printed for named period paths in
the commit the shard checked out. A file's size is git's own where the clone
holds the file, and GitHub's blob API's where the clone never downloaded it.
`backend/utilities/gardener_publish.py` runs git and calls it, because nothing
under `backend/idhazh/` starts a process. `from_disk` walks only the named day,
month, or run-directory paths passed to it, for `idhazh gardener run-task` and
tests that build fixtures.

**A step that chooses its periods as it runs names them then.** `name` hands
back a listing that also answers for the paths it was given, listed by the
builder's own lister in one call: `git ls-tree` over the same commit for a
shard, the same disk walk for `from_disk`. A path the listing already answers
for is not listed again, so a naming never brings back a file an earlier task
of the shard deleted. `from_paths` has no lister, and refuses to name more.
Every file a later naming listed is recorded for the shard, so `listed` can
hold a shard's deletions to what it listed, and the next `settled` listing
answers for those paths too.

**A folder outside the listing is refused, never read as empty.** A task that
asks for the names under a folder its declaration neither owns nor reads has a
declaration that forgot the folder, and an empty answer would be the silent
zero that lets a task report success over rows it could not see. A declared
folder the commit does not hold answers empty: nothing has written one yet.

**A path no step named is refused, never answered "not held".** The listing
looked only at the paths it was given. A file at or below one of them is
answered for, and one the commit lacks is not held: a step named its period,
and nothing is there. Anywhere else under a listed folder, `holds`, `size_of`
and `fetch` raise `PathNotNamedError`, naming the path and the nearest paths a
step did name. "Not held" there would be a guess, and a step that looked in the
wrong months would act on it as if those months were empty. A folder that holds
a named path passes too, because fetching it brings what was named inside it.
`saw_any_of` says beforehand whether a path would pass, for a caller that may
find nothing named there.

**`files_under` answers for all of a folder or for none of it.** It answers
only for a path a step named, or one inside such a path, because only there has
the listing seen every file. A folder that merely holds named periods, or sits
beside them, is refused: its answer would be the named part of it read as the
whole. `named_files` is the walk over the named periods inside a folder, and a
caller asks for that partial walk by name.

**Content arrives before it is read, a folder at a time.** `fetch` widens the
checkout in one call, by whole folders or by the files directly inside a
file's own folder, and then checks that every listed file it brought is on
disk. A file the commit holds and the checkout lacks is fetched or the task
fails; it is never taken for a member that is not there. What the widening
added is what the shard downloaded for its tasks, and the record says so.

**A task sees what the shard's earlier tasks changed.** One task may read a
folder another task of its shard owns, so after each task the listing drops
what it deleted and adds what it wrote, and a file it adds counts as named. A
later task then decides from the tree the shard will commit, and never fetches
a file an earlier task deleted.
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

#: Lists every file the commit holds at or under these repository paths, with its
#: size in bytes. Each builder brings its own: `git ls-tree` for a shard, the disk
#: walk for `from_disk`.
type Lister = Callable[[Sequence[str]], Mapping[str, int]]


class FileNotFetchedError(Exception):
    """A file the commit holds is still not on disk after the checkout was widened for it."""


class PathNotNamedError(Exception):
    """A path under a listed folder that no step named, so the listing cannot answer for it.

    Not a `ValueError`, so a handler that skips bad data cannot skip this defect too.
    """


class TreeReader(Protocol):
    """The one call the size reader makes of GitHub: a GET for one blob."""

    def read(self, path: str) -> dict[str, Any]:
        """One GET under the repository, such as `git/blobs/<id>`."""


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


def sizes_from_github(api: TreeReader, blobs: Iterable[str]) -> dict[str, int]:
    """The size of each named blob, without reading any sibling paths."""
    sizes: dict[str, int] = {}
    for blob in sorted(set(blobs)):
        if not _OBJECT_ID.fullmatch(blob):
            raise ValueError(f"{blob!r} is not a git blob id, and it would go into an API address")
        reply = api.read(f"git/blobs/{blob}")
        try:
            size = int(reply["size"])
        except (KeyError, TypeError, ValueError) as refusal:
            raise ValueError(f"GitHub did not report a size for blob {blob}") from refusal
        if size < 0:
            raise ValueError(f"GitHub reported a negative size for blob {blob}")
        sizes[blob] = size
    return sizes


def sizes_of(entries: Iterable[TreeEntry], github_sizes: Mapping[str, int]) -> dict[str, int]:
    """Each file's size: git's where it printed one, else GitHub's for the file's blob.

    A file neither can size is refused by name: a weight that skipped it would
    read low and say nothing.
    """
    sizes: dict[str, int] = {}
    for entry in entries:
        size = entry.size if entry.size is not None else github_sizes.get(entry.blob)
        if size is None:
            raise ValueError(
                f"{entry.path} has no size: this clone never downloaded blob {entry.blob}, "
                "and GitHub's blob API did not report it"
            )
        sizes[entry.path] = size
    return sizes


def _on_disk(repo_root: Path, names: Iterable[str]) -> dict[str, int]:
    """Every file at or under these repository paths, weighed on disk. A symlink is refused."""
    sizes: dict[str, int] = {}
    for name in sorted(set(names)):
        root = repo_root / name
        if root.is_symlink():
            raise ValueError(f"{root} is a symlink inside a named period path")
        if root.is_file():
            candidates: Iterable[Path] = (root,)
        elif root.is_dir():
            candidates = root.rglob("*")
        else:
            continue
        for path in candidates:
            if path.is_symlink():
                raise ValueError(f"{path} is a symlink inside a named period path")
            if path.is_file():
                sizes[path.relative_to(repo_root).as_posix()] = path.stat().st_size
    return dict(sorted(sizes.items()))


def _folder(name: str) -> str:
    """A repository folder as the listing spells it: POSIX, no trailing slash."""
    return name.strip().rstrip("/")


def _inside(path: str, folder: str) -> bool:
    """Whether a repository path is this folder or sits inside it."""
    return path == folder or path.startswith(f"{folder}/")


def _parent(path: str) -> str:
    return path.rpartition("/")[0]


def _shared(left: str, right: str) -> int:
    """How many leading segments two repository paths have in common."""
    count = 0
    for mine, theirs in zip(left.split("/"), right.split("/"), strict=False):
        if mine != theirs:
            break
        count += 1
    return count


def _nearest(path: str, named: Sequence[str]) -> str:
    """The named paths sharing the most leading segments with `path`, as a refusal says them."""
    if not named:
        return "No step named any path under it"
    closest = max(_shared(path, other) for other in named)
    nearest = [other for other in named if _shared(path, other) == closest]
    if len(nearest) == 1:
        return f"The nearest path a step named is {nearest[0]}"
    return (
        f"The nearest paths a step named run from {nearest[0]} to {nearest[-1]} "
        f"({len(nearest)} paths)"
    )


@dataclass(slots=True)
class _Checkout:
    """What every task of one shard shares: the checkout, how to widen and list it, what it got."""

    repo_root: Path
    #: Widens a sparse checkout by these entries in one call. None for a listing
    #: read off the disk, which has nothing to widen.
    widen: Callable[[Sequence[str]], None] | None
    #: Every folder the shard listed, which is what a download is counted under.
    folders: tuple[str, ...]
    #: Lists what the commit holds under a path a step names as it runs. None for
    #: a listing built from named files alone, which can name nothing more.
    lister: Lister | None = None
    #: Every file a widening put on disk, with its size.
    added: dict[str, int] = field(default_factory=dict)
    #: Every path a step named after the listing was built.
    named_later: set[str] = field(default_factory=set)
    #: Every file listed under those paths, with its size.
    listed_later: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class FileListing:
    """The files under some folders, by repository path, and what each weighs."""

    #: The folders this listing answers for, sorted. Asking about anything else
    #: is refused.
    folders: tuple[str, ...]
    #: Every path a step named for this listing - a file or a period folder - by
    #: repository path, sorted. A path under a listed folder that is not one of
    #: these, under one, or above one is refused.
    named: tuple[str, ...]
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
            named=tuple(sorted(sizes)),
            sizes=sizes,
            checkout=_Checkout(repo_root=repo_root, widen=None, folders=chosen),
        )

    @classmethod
    def from_disk(
        cls, repo_root: Path, folders: Iterable[str], *, paths: Iterable[Path]
    ) -> FileListing:
        """Every file under these named period paths, weighed on disk.

        A path named later is walked the same way, so a step that names its
        periods as it runs reads the disk exactly as this listing did.
        """
        chosen = tuple(sorted({_folder(folder) for folder in folders}))
        named: set[str] = set()
        for root in sorted(set(paths)):
            try:
                name = root.relative_to(repo_root).as_posix()
            except ValueError as refusal:
                raise ValueError(f"{root} is outside the checkout") from refusal
            if not any(_inside(name, folder) for folder in chosen):
                raise ValueError(f"{name} is outside the listing's declared folders")
            named.add(name)

        def walked(names: Sequence[str]) -> Mapping[str, int]:
            return _on_disk(repo_root, names)

        return cls(
            folders=chosen,
            named=tuple(sorted(named)),
            sizes=_on_disk(repo_root, named),
            checkout=_Checkout(repo_root=repo_root, widen=None, folders=chosen, lister=walked),
        )

    @classmethod
    def from_commit(
        cls,
        repo_root: Path,
        folders: Iterable[str],
        entries: Iterable[TreeEntry],
        github_sizes: Mapping[str, int],
        *,
        paths: Iterable[str],
        widen: Callable[[Sequence[str]], None],
        lister: Lister | None = None,
    ) -> FileListing:
        """The files the commit holds under these folders, each with a size or a refusal.

        `paths` are the period paths `git ls-tree` was asked about, so they are
        what the listing answers for. `github_sizes` answers, by blob id, for
        every file git printed no size for. A file neither can size is refused
        by name: a weight that skipped it would read low and say nothing.
        `lister` lists the same commit for a path a step names later; without
        one, `name` refuses.
        """
        chosen = tuple(sorted({_folder(folder) for folder in folders}))
        sizes = sizes_of(
            (entry for entry in entries if any(_inside(entry.path, folder) for folder in chosen)),
            github_sizes,
        )
        return cls(
            folders=chosen,
            named=tuple(sorted({_folder(path) for path in paths})),
            sizes=dict(sorted(sizes.items())),
            checkout=_Checkout(repo_root=repo_root, widen=widen, folders=chosen, lister=lister),
        )

    @property
    def repo_root(self) -> Path:
        return self.checkout.repo_root

    def within(self, folders: Iterable[str]) -> FileListing:
        """The part of this listing that covers these folders, sharing its checkout."""
        chosen = tuple(sorted({_folder(folder) for folder in folders}))
        for folder in chosen:
            self._refuse_outside(folder)
        return FileListing(
            folders=chosen, named=self.named, sizes=self.sizes, checkout=self.checkout
        )

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

    def _refuse_unnamed(self, path: str) -> None:
        """Refuse a path no step named, because the listing never looked there.

        A path passes when a step named it, a folder above it, or a path inside
        it: a file can hold no path, and fetching a folder brings what was named
        inside it.
        """
        if self.saw_any_of(path):
            return
        folder = next(folder for folder in self.folders if _inside(path, folder))
        nearest = _nearest(path, [named for named in self.named if _inside(named, folder)])
        raise PathNotNamedError(
            f"{path} is under {folder}, which this task owns or reads, but no step named it: "
            "the listing never looked there, so it cannot say whether the commit holds it. "
            f"{nearest}. A step reads only inside the periods its task named"
        )

    def saw_any_of(self, path: str | Path) -> bool:
        """Whether the listing saw any of a path.

        A step named it, a folder above it, or a path inside it. `answers_for`
        says whether it saw all of the path.
        """
        relative = self._relative(path)
        self._refuse_outside(relative)
        return any(_inside(relative, named) or _inside(named, relative) for named in self.named)

    def answers_for(self, path: str | Path) -> bool:
        """Whether the listing saw all at or under a path: a step named it, or a folder above it."""
        relative = self._relative(path)
        return any(_inside(relative, named) for named in self.named)

    def _listed_under(self, relative: str) -> list[str]:
        """Every listed file under a folder, in path order, asked of nothing but the listing."""
        return [path for path in self.sizes if path.startswith(f"{relative}/")]

    def files_under(self, folder: str | Path) -> list[str]:
        """Every file the commit holds under this folder, as repository paths, in path order.

        Only a folder a step named, or one inside such a folder, is answered:
        anywhere else the listing has seen part of the folder at most. A folder
        that holds named periods without being one is refused as well as one
        beside them, because its answer would be the named part read as all of
        it. `named_files` walks the named periods instead, by name.
        """
        relative = self._relative(folder)
        self._refuse_outside(relative)
        if not self.answers_for(relative):
            area = next(held for held in self.folders if _inside(relative, held))
            nearest = _nearest(relative, [named for named in self.named if _inside(named, area)])
            raise PathNotNamedError(
                f"{relative} is not a path a step named, nor inside one, so the listing holds "
                f"only the periods named inside {area} and cannot say what all of {relative} "
                f"holds. {nearest}. Walk the named periods with named_files"
            )
        return self._listed_under(relative)

    def named_files(self, folder: str | Path) -> list[str]:
        """Every listed file inside the periods a step named at, above or under this folder.

        The walk for a tree whose periods a task named one by one: it answers
        for those periods, in path order, and says nothing of the rest of the
        folder. A folder with no named period at, above or under it is refused,
        as `holds` refuses a path there.
        """
        relative = self._relative(folder)
        self._refuse_unnamed(relative)
        return self._listed_under(relative)

    def name(self, paths: Iterable[str | Path]) -> FileListing:
        """This listing, answering also for these paths: what the commit holds at or under each.

        For a step that chooses its periods as it runs, after the listing was
        built. The builder's lister lists every path this listing does not
        answer for yet, in one call. A path at or inside a named one is not
        listed again, and a file listed inside one is passed over, so a naming
        never brings back a file an earlier task of the shard deleted. What the
        lister found is recorded for the shard, for `listed` and `settled`.
        """
        wanted = sorted({self._relative(path) for path in paths})
        for path in wanted:
            self._refuse_outside(path)
        fresh = [path for path in wanted if not self.answers_for(path)]
        fresh = [
            path
            for path in fresh
            if not any(path != other and _inside(path, other) for other in fresh)
        ]
        if not fresh:
            return self
        lister = self.checkout.lister
        if lister is None:
            raise ValueError(
                f"{fresh[0]} cannot be named now: this listing was built from named files "
                "and has no lister to list more"
            )
        found = {
            path: size
            for path, size in lister(fresh).items()
            if any(_inside(path, named) for named in fresh) and not self.answers_for(path)
        }
        self.checkout.named_later.update(fresh)
        self.checkout.listed_later.update(found)
        return FileListing(
            folders=self.folders,
            named=tuple(sorted({*self.named, *fresh})),
            sizes=dict(sorted({**self.sizes, **found}.items())),
            checkout=self.checkout,
        )

    def listed(self) -> frozenset[str]:
        """Every file this listing was built with, and every file a later naming listed.

        What a shard's deletions are held to: a file a task deleted is one the
        shard listed from the commit, when the listing was built or when a step
        named its period later.
        """
        return frozenset(self.sizes) | frozenset(self.checkout.listed_later)

    def holds(self, path: str | Path) -> bool:
        """Whether the commit holds this file. A path no step named is refused."""
        relative = self._relative(path)
        self._refuse_unnamed(relative)
        return relative in self.sizes

    def size_of(self, path: str | Path) -> int:
        """What one listed file weighs, in bytes."""
        relative = self._relative(path)
        self._refuse_unnamed(relative)
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
        because there is nothing in it to read; a folder or file no step named
        is refused, as `holds` refuses it. Every listed file brought is on disk
        afterwards, or this raises naming the first one missing.
        """
        entries: list[str] = []
        for folder in folders:
            relative = self._relative(folder)
            self._refuse_unnamed(relative)
            if self._listed_under(relative):
                entries.append(relative)
        for file in beside:
            relative = self._relative(file)
            self._refuse_unnamed(relative)
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

        It first takes in every path a step named as it ran and the files listed
        under each, so a later task that names the same path is not handed the
        commit's files again. Then a deleted file is no longer listed, and a
        written file is listed with what it weighs on disk, where the task left
        it, when it sits under a listed folder, and it counts as named: the
        listing knows exactly what that path holds.
        """
        later = [path for path in self.checkout.named_later if not self.answers_for(path)]
        named = {*self.named, *later}
        sizes = dict(self.sizes)
        sizes.update(
            (path, size)
            for path, size in self.checkout.listed_later.items()
            if any(_inside(path, folder) for folder in later)
        )
        for path in deleted:
            sizes.pop(path, None)
        for path in written:
            on_disk = self.repo_root / path
            if on_disk.is_file() and any(_inside(path, folder) for folder in self.folders):
                sizes[path] = on_disk.stat().st_size
                named.add(path)
        return FileListing(
            folders=self.folders,
            named=tuple(sorted(named)),
            sizes=dict(sorted(sizes.items())),
            checkout=self.checkout,
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
