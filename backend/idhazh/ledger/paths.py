"""Where each ledger's file lives, read from `config/ledgers.json` and never guessed.

The registry is loaded and validated once, when this module loads, so a config
that does not describe every ledger stops the build rather than a run four
hundred seconds in.

Three builders and no fourth. `path` and `relpath` are the same address in the
two forms this project uses - a `Path` for local I/O, a POSIX string for anything
leaving the process (CLAUDE.md section 2) - and they are built from one segment
list so they cannot disagree. `tree_root` is the whole-tree directory a reader
walks.

Nothing here globs `state/`. A walk would cost more every day, and it cannot tell
a retired ledger from one that has never run (Guardrail #12).

What makes two rows one record is a separate question with a separate home, which
is why this module imports nothing that answers it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgerEntry, LedgersConfig

STATE_DIRNAME: Final = "state"

REGISTRY_FILENAME: Final = "ledgers.json"

#: What `covers` means for each dated grain, quoted back to a caller that omitted
#: it. A grain names its period; a period is never the day a job woke.
_PERIOD: Final[dict[Grain, str]] = {
    Grain.DAY_FILE: "the YYYY-MM-DD day its rows describe",
    Grain.DAY_TREE: "the YYYY-MM-DD day its rows describe",
    Grain.MONTH_FILE: "the YYYY-MM month its rows describe",
    Grain.STAMPED: "the stamp its rows were taken under",
}

#: The grains that put their files in a `<YYYY>/<MM>/` tree, so a reader can walk
#: one root and meet every day.
_DAY_GRAINS: Final[frozenset[Grain]] = frozenset({Grain.DAY_FILE, Grain.DAY_TREE})


def _load(config_dir: Path) -> LedgersConfig:
    """Read the registry, or refuse naming the file an operator has to edit."""
    text = (config_dir / REGISTRY_FILENAME).read_text(encoding="utf-8")
    try:
        return LedgersConfig.from_json(text)
    except ValidationError as error:
        raise ValueError(f"config/{REGISTRY_FILENAME} is refused: {error}") from error


_CONFIG: Final[LedgersConfig] = _load(config.DEFAULT_CONFIG_DIR)

#: Every ledger in one table, whichever family lists it. An address is a fact
#: about one ledger, so no builder here needs to know the family.
_REGISTRY: Final[dict[LedgerName, LedgerEntry]] = {
    held.name: held for family in _CONFIG.families for held in family.ledgers
}


def entry(ledger: LedgerName) -> LedgerEntry:
    """One ledger's registry row: its grain and where it sits."""
    return _REGISTRY[ledger]


def claimed_roots() -> frozenset[str]:
    """Every family the registry names, whatever its lifecycle status.

    What `prune-state` subtracts from the children of `state/` before treating
    what is left as a trial run's tree. An active family, a paused one and a
    retired one are all claimed: the status says what a writer may do, never
    whether the rows survive.

    A family is named for its top-level folder, so each name here is a child of
    `state/`. `feed-retirements` is the one name that is a file's stem rather
    than a folder - its only ledger is `state/feed-retirements.csv` - and
    carrying it is harmless, because the sweep only ever looks at directories.
    """
    return frozenset(family.name for family in _CONFIG.families)


def _segments(held: LedgerEntry, covers: str | None) -> tuple[str, ...]:
    """The address under `state/`, one segment at a time, for the grain it carries."""
    if held.grain is Grain.FLAT:
        if covers is not None:
            raise ValueError(
                f"{held.name} is one flat file and names no period, so {covers!r} "
                "addresses nothing. Drop the argument"
            )
        return (*held.prefix, f"{held.stem}{held.suffix}")
    if covers is None:
        raise ValueError(
            f"{held.name} files by {held.grain.value} and needs {_PERIOD[held.grain]}. "
            "Pass it - this builder does not guess a period, and a period is never "
            "the day a job woke"
        )
    if held.grain is Grain.DAY_TREE:
        return (*held.prefix, covers[:4], covers[5:7], covers[8:10])
    if held.grain is Grain.DAY_FILE:
        return (*held.prefix, covers[:4], covers[5:7], f"{covers[8:10]}{held.suffix}")
    # A month file and a stamped file both name themselves after the whole period.
    return (*held.prefix, f"{covers}{held.suffix}")


def path(state_dir: Path, ledger: LedgerName, covers: str | None = None) -> Path:
    """Where this ledger puts the rows covering this period, under this state root.

    `covers` is the period the rows describe and never the day the job woke
    (CLAUDE.md section 2). A dated ledger handed nothing raises, and a flat one
    handed a period raises: an address this cannot build is a row filed where
    nobody will look for it.
    """
    return state_dir.joinpath(*_segments(_REGISTRY[ledger], covers))


def relpath(ledger: LedgerName, covers: str | None = None) -> str:
    """The same address as `path`, POSIX and relative, for a log line or a manifest."""
    return "/".join((STATE_DIRNAME, *_segments(_REGISTRY[ledger], covers)))


def tree_root(state_dir: Path, ledger: LedgerName) -> Path:
    """The whole-tree directory a reader walks, for a ledger that files by day.

    What `day_shards.settled_rows` and `day_partition.day_files` are handed. It
    is a builder of its own rather than `path` with no period, so `path` keeps
    refusing a missing one.
    """
    held = _REGISTRY[ledger]
    if held.grain not in _DAY_GRAINS:
        raise ValueError(
            f"{held.name} files by {held.grain.value}, so it has no day tree to walk. "
            "Only a ledger filing by day has one"
        )
    return state_dir.joinpath(*held.prefix)
