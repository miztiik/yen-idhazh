"""Where each ledger's file lives under `state/`, and never guessed.

Two kinds of address, and nine builders in all. A ledger that files the way the
CSV trees do is read from `config/ledgers.json`, which is loaded and validated
once, when this module loads, so a config that does not describe every ledger
stops the build rather than a run four hundred seconds in. A ledger that goes
through the door in `ledger/persist.py` files under `state/raw/` or
`state/compact/`, and those two roots have one fixed grammar, so their five
builders need no registry entry to answer.

The registry's four builders come in two pairs. `path` and `relpath` are the
same address in the two forms this project uses - a `Path` for local I/O, a
POSIX string for anything leaving the process (CLAUDE.md section 2) - and they
are built from one segment list so they cannot disagree. `tree_root` and
`tree_relpath` are the same pair for the folder a reader walks: the one that
holds every file of a ledger and nothing else.

**Nothing the door writes is born outside the two roots.** Each of the five
root builders refuses, by name, a path whose first folder under `state/` is
neither `raw` nor `compact`, so a third root is a `ValueError` rather than a
convention somebody forgot.

**A ledger the registry lists as `raw-and-compact` has no registry address.**
Its files sit under the two roots and are named by their grammar, so the four
registry builders refuse it by name and point at the four that can build it,
rather than hand back a CSV address nothing writes.

Nothing here globs `state/`. A walk would cost more every day, and it cannot tell
a retired ledger from one that has never run (Guardrail #12).

What makes two rows one record is a separate question with a separate home, which
is why this module imports nothing that answers it.
"""

from __future__ import annotations

import os
import uuid
from functools import cache
from pathlib import Path, PurePath
from typing import Final

from pydantic import ValidationError

from idhazh import config
from idhazh.contracts.file_envelope import Format, Period, Tier, covers_fits
from idhazh.contracts.ledger_name import LedgerName
from idhazh.contracts.ledgers import Grain, LedgerEntry, LedgersConfig

STATE_DIRNAME: Final = "state"

REGISTRY_FILENAME: Final = "ledgers.json"

#: The folder each root takes under `state/`. The builders spell a root from
#: these and the refusal checks against `Tier` itself, so a root renamed here
#: without the enum moving is caught rather than written.
RAW_DIRNAME: Final = Tier.RAW.value
COMPACT_DIRNAME: Final = Tier.COMPACT.value

#: The two roots, and the whole of them. A third is refused, never created.
_THE_TWO_ROOTS: Final = frozenset(tier.value for tier in Tier)

#: Where a compact period's listing sits inside a ledger.
INDEX_DIRNAME: Final = "index"

#: What each compact period's resume mark is called, inside that period's folder.
WATERMARK_FILENAME: Final = "watermark.json"

#: The suffix of the small JSON files the gardener rewrites whole.
_JSON_SUFFIX: Final = ".json"

#: What `covers` means for each dated grain, quoted back to a caller that omitted
#: it. A grain names its period; a period is never the day a job woke.
_PERIOD: Final[dict[Grain, str]] = {
    Grain.DAY_FILE: "the YYYY-MM-DD day its rows describe",
    Grain.DAY_TREE: "the YYYY-MM-DD day its rows describe",
    Grain.MONTH_FILE: "the YYYY-MM month its rows describe",
    Grain.STAMPED: "the stamp its rows were taken under",
}


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
    """Every child of `state/` a writer owns, whatever its lifecycle status.

    What the gardener's complement subtracts from the children of `state/`
    before the `trials` task treats what is left as a trial run's tree. An
    active family, a paused one and a retired one are all claimed: the status
    says what a writer may do, never whether the rows survive.

    A family is named for its top-level folder, so each name here is a child of
    `state/`.

    `raw` and `compact` are claimed too, and they are not families: they are the
    two roots the ledger door files under. Unclaimed, the sweep would read them
    as a trial run's trees and delete what the door wrote. Claimed means "not a
    stray", never "not pruned" - a compaction bounds what sits in them.
    """
    return frozenset(family.name for family in _CONFIG.families) | _THE_TWO_ROOTS


def _no_registry_address(held: LedgerEntry) -> ValueError:
    """The refusal a ledger that files under the two roots gets from a registry builder."""
    return ValueError(
        f"{held.name} files by {held.grain.value}: its files sit under "
        f"{STATE_DIRNAME}/{RAW_DIRNAME}/ and {STATE_DIRNAME}/{COMPACT_DIRNAME}/ and are "
        "named by their own grammar, so the registry holds no single address for it. "
        "Ask raw_path, compact_path, compact_index_path or watermark_path"
    )


def _segments(held: LedgerEntry, covers: str | None) -> tuple[str, ...]:
    """The address under `state/`, one segment at a time, for the grain it carries."""
    if held.grain is Grain.RAW_AND_COMPACT:
        raise _no_registry_address(held)
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


def _folder(held: LedgerEntry) -> tuple[str, ...]:
    """The folder a ledger has to itself under `state/`, one segment at a time.

    A flat file has none. It shares its folder with other files -
    `holdout-pairs.csv` sits beside the similarity judge's other ledgers - so a
    walk handed that folder would read files that are not this ledger's. A
    ledger under the two roots has two folders rather than one, so it is refused
    too.
    """
    if held.grain is Grain.RAW_AND_COMPACT:
        raise _no_registry_address(held)
    if held.grain is Grain.FLAT:
        raise ValueError(
            f"{held.name} is one file in a folder it shares with other files, so it has "
            "no day tree to walk and no folder of its own. Ask `path` for the file"
        )
    return held.prefix


def tree_root(state_dir: Path, ledger: LedgerName) -> Path:
    """The folder that holds every file of this ledger and nothing else, under this state root.

    What the `day_shards`, `day_partition` and `month_partition` readers are
    handed: a walk that starts here meets every day, month or stamp the ledger
    has filed. It is a builder of its own rather than `path` with no period, so
    `path` keeps refusing a missing one.
    """
    return state_dir.joinpath(*_folder(_REGISTRY[ledger]))


def tree_relpath(ledger: LedgerName) -> str:
    """The same folder as `tree_root`, POSIX and relative, for a log line or a manifest."""
    return "/".join((STATE_DIRNAME, *_folder(_REGISTRY[ledger])))


# --- the two roots the ledger door files under --------------------------------


@cache
def _resolved_root(absolute: Path) -> Path:
    """Resolve one absolute state root for this process; candidate paths remain checked fresh."""
    return absolute.resolve()


def _shown(state_dir: Path, built: Path) -> str:
    """A path as it may leave the process: relative to the state root, POSIX (section 2)."""
    try:
        below = os.path.relpath(built.resolve(), _resolved_root(state_dir.absolute()))
    except ValueError:
        return built.name
    return PurePath(STATE_DIRNAME, below).as_posix()


def _under_the_two_roots(state_dir: Path, built: Path) -> Path:
    """The path back, or a refusal naming it and the rule.

    Checked on the resolved path, so a segment that walks back out of a root -
    `raw/../scores` - is refused however its folders are spelled. The state root
    is the one the caller handed in, so a trial run's tree is held to the same
    rule as the production one.
    """
    try:
        first = built.resolve().relative_to(_resolved_root(state_dir.absolute())).parts[:1]
    except ValueError:
        first = ()
    if not first or first[0] not in _THE_TWO_ROOTS:
        raise ValueError(
            f"{_shown(state_dir, built)} is outside the two roots. Everything the ledger "
            f"door writes sits under {STATE_DIRNAME}/{Tier.RAW.value}/ or "
            f"{STATE_DIRNAME}/{Tier.COMPACT.value}/, so a third root is refused rather "
            "than created"
        )
    return built


def _day_segments(date: str) -> tuple[str, str, str]:
    """`YYYY`, `MM` and `DD`, or a refusal: a stamp that is not a day addresses nothing."""
    if not covers_fits(date, tier=Tier.RAW, period=None):
        raise ValueError(f"{date!r} is not a YYYY-MM-DD UTC day, so it names no raw day folder")
    return date[:4], date[5:7], date[8:10]


def raw_root(state_dir: Path, ledger: LedgerName) -> Path:
    """The folder that holds every raw file of one ledger: `raw/<ledger>/`.

    What a reader walks to find the days a ledger has files for. `raw_path` is
    built from it, so the folder a reader walks and the files a writer puts in
    it cannot disagree about where the ledger sits.
    """
    return _under_the_two_roots(state_dir, state_dir.joinpath(RAW_DIRNAME, ledger.value))


def raw_path(
    state_dir: Path,
    ledger: LedgerName,
    date: str,
    file_id: uuid.UUID,
    *,
    fmt: Format = Format.PARQUET,
) -> Path:
    """Where one writer's file for one day sits: `raw/<ledger>/<YYYY>/<MM>/<DD>/<file_id>`.

    Many writers file into one day, and the minted `file_id` is what keeps two of
    them off one path. The suffix is the format's own, so a JSON-lines file is
    `<file_id>.json`.
    """
    year, month, day = _day_segments(date)
    built = raw_root(state_dir, ledger).joinpath(year, month, day, f"{file_id}.{fmt.value}")
    return _under_the_two_roots(state_dir, built)


def compact_path(
    state_dir: Path,
    ledger: LedgerName,
    period: Period,
    covers: str,
    *,
    fmt: Format = Format.PARQUET,
) -> Path:
    """Where one compact period's file sits, named for what it covers.

    `compact/<ledger>/daily/<YYYY>/<MM>/<DD>`, `compact/<ledger>/monthly/<YYYY>/<MM>`
    or `compact/<ledger>/yearly/<YYYY>/<YYYY>`. A compact period has one writer, so its
    name is the period rather than a minted id, and a reader can compute the
    address. `covers` has to be the shape `period` covers, or this refuses rather
    than file a month under a day. No file sits directly beside its period's
    watermark, a year file included, because fetching a watermark into a checkout
    that holds only names brings every file beside it.
    """
    if not covers_fits(covers, tier=Tier.COMPACT, period=period):
        raise ValueError(
            f"{covers!r} is not a {period.value} period: a daily file covers YYYY-MM-DD, "
            "a monthly file covers YYYY-MM and a yearly file covers YYYY"
        )
    *folders, leaf = covers.split("-")
    built = state_dir.joinpath(
        COMPACT_DIRNAME, ledger.value, period.value, *(folders or [leaf]), f"{leaf}.{fmt.value}"
    )
    return _under_the_two_roots(state_dir, built)


def compact_index_path(state_dir: Path, ledger: LedgerName, period: Period) -> Path:
    """Where the listing of one compact period sits: `compact/<ledger>/index/<period>.json`."""
    built = state_dir.joinpath(
        COMPACT_DIRNAME, ledger.value, INDEX_DIRNAME, f"{period.value}{_JSON_SUFFIX}"
    )
    return _under_the_two_roots(state_dir, built)


def watermark_path(state_dir: Path, ledger: LedgerName, period: Period) -> Path:
    """Where one compact period's resume mark sits: `compact/<ledger>/<period>/watermark.json`.

    It records the newest period this roll-up has looked at, including one that
    held nothing, which is the one fact no listing of the tree can recover.
    """
    built = state_dir.joinpath(COMPACT_DIRNAME, ledger.value, period.value, WATERMARK_FILENAME)
    return _under_the_two_roots(state_dir, built)
