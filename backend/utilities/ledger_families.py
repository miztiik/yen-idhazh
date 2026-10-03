"""Which ledger families own the files an operator named?

An operator listing, run by hand from the repository root:

    python backend/utilities/ledger_families.py

For every family in `config/ledgers.json` it prints the family's name, its
lifecycle status, the UTC day it was onboarded and the one line saying what it
holds, then each ledger in it with the number of files that ledger holds under
the state tree. In a clean checkout those are the committed files.

Counts cover only the named input files, never every file a ledger holds.

The registry is read through its own contract, so a registry the build would
refuse is refused here too, with the same message. A ledger's folder comes from
its prefix, the same field every path builder reads; a ledger that is one file is
counted as that file or nothing. A ledger that goes through the door has two
folders, one under each of `state/raw/` and `state/compact/`, and each is counted
on its own line, because they answer different questions: what runs wrote, and
what compaction has kept of it. A name that opens on a dot, such as a
`.gitkeep` placeholder, holds no rows and is not counted.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

from idhazh.contracts.ledgers import Grain, LedgerEntry, LedgersConfig
from idhazh.ledger import paths

#: The two roots a ledger that goes through the door files under, in order.
THE_TWO_ROOTS = (paths.RAW_DIRNAME, paths.COMPACT_DIRNAME)


def _files_in(root: Path, files: Sequence[Path]) -> int:
    return sum(
        1
        for found in files
        if found.is_relative_to(root) and found.is_file() and not found.name.startswith(".")
    )


def files_held(state_dir: Path, held: LedgerEntry, files: Sequence[Path]) -> int:
    """Count only the named files that belong to this ledger."""
    if held.grain is Grain.FLAT:
        path = state_dir.joinpath(*held.prefix, f"{held.stem}{held.suffix}")
        return int(path in files and path.is_file())
    if held.grain is Grain.RAW_AND_COMPACT:
        return sum(
            _files_in(state_dir.joinpath(root, *held.prefix), files) for root in THE_TWO_ROOTS
        )
    return _files_in(state_dir.joinpath(*held.prefix), files)


def _counted(count: int) -> str:
    return f"{count} file{'' if count == 1 else 's'}"


def listing(config_dir: Path, state_dir: Path, names: Sequence[str]) -> list[str]:
    """One block of lines per family, in the order the registry lists them."""
    registry = LedgersConfig.from_json(
        (config_dir / paths.REGISTRY_FILENAME).read_text(encoding="utf-8")
    )
    from utilities.named_inputs import named_files

    state_dir = state_dir.resolve()
    files = named_files(state_dir, names)
    lines: list[str] = []
    for family in registry.families:
        lines.append(
            f"{family.name}: {family.lifecycle_status.value}, "
            f"onboarded {family.onboarded.isoformat()} UTC"
        )
        lines.append(f"  {family.description}")
        for held in family.ledgers:
            if held.grain is Grain.RAW_AND_COMPACT:
                for root in THE_TWO_ROOTS:
                    count = _files_in(state_dir.joinpath(root, *held.prefix), files)
                    lines.append(f"  - {held.name.value} under {root}/: {_counted(count)}")
                continue
            lines.append(f"  - {held.name.value}: {_counted(files_held(state_dir, held, files))}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--state", type=Path, default=Path(paths.STATE_DIRNAME))
    parser.add_argument(
        "--file", action="append", required=True, help="Named path relative to state/."
    )
    args = parser.parse_args(argv)
    print("Counts cover named files only.")
    print("\n".join(listing(args.config, args.state, args.file)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
