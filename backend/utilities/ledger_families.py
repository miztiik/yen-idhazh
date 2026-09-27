"""Which families does the ledger registry hold, and how many files does each ledger hold?

An operator listing, run by hand from the repository root:

    python backend/utilities/ledger_families.py

For every family in `config/ledgers.json` it prints the family's name, its
lifecycle status, the UTC day it was onboarded and the one line saying what it
holds, then each ledger in it with the number of files that ledger holds under
the state tree. In a clean checkout those are the committed files.

**This is a growing read, and it is the one this file owns.** Counting a
ledger's files means listing its folder, so what this costs rises with every
file a run commits (CLAUDE.md Guardrail #12). Nothing bounded can answer "how
many files does this ledger hold". A person types it; nothing in the pipeline
calls it, and its test drives it from a registry and a state tree the test
writes, never from the committed ones.

The registry is read through its own contract, so a registry the build would
refuse is refused here too, with the same message. A ledger's folder comes from
its prefix, the same field every path builder reads; a ledger that is one file is
counted as that file or nothing. A name that opens on a dot, such as a
`.gitkeep` placeholder, holds no rows and is not counted.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from idhazh.contracts.ledgers import Grain, LedgerEntry, LedgersConfig
from idhazh.ledger import paths


def files_held(state_dir: Path, held: LedgerEntry) -> int:
    """How many files this ledger holds under the state tree. Zero for one never written."""
    if held.grain is Grain.FLAT:
        return int(state_dir.joinpath(*held.prefix, f"{held.stem}{held.suffix}").is_file())
    root = state_dir.joinpath(*held.prefix)
    if not root.is_dir():
        return 0
    return sum(1 for found in root.rglob("*") if found.is_file() and not found.name.startswith("."))


def listing(config_dir: Path, state_dir: Path) -> list[str]:
    """One block of lines per family, in the order the registry lists them."""
    registry = LedgersConfig.from_json(
        (config_dir / paths.REGISTRY_FILENAME).read_text(encoding="utf-8")
    )
    lines: list[str] = []
    for family in registry.families:
        lines.append(
            f"{family.name}: {family.lifecycle_status.value}, "
            f"onboarded {family.onboarded.isoformat()} UTC"
        )
        lines.append(f"  {family.description}")
        for held in family.ledgers:
            count = files_held(state_dir, held)
            lines.append(f"  - {held.name.value}: {count} file{'' if count == 1 else 's'}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=Path("config"))
    parser.add_argument("--state", type=Path, default=Path(paths.STATE_DIRNAME))
    args = parser.parse_args(argv)
    print("\n".join(listing(args.config, args.state)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
