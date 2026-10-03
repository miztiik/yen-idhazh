"""Initialize publication.json from an explicitly named inventory, never from an archive walk."""

from __future__ import annotations

import argparse
from pathlib import Path

from idhazh.contracts.publication_inventory import PublicationInventory
from idhazh.publication import initialize_from_paths, initialize_inventory, upgrade_inventory


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-root", required=True, type=Path)
    parser.add_argument("--state-root", type=Path)
    parser.add_argument("--state-paths", type=Path, help="Named list of state-root-relative paths.")
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument(
        "--seed", type=Path, help="Named PublicationInventory JSON migration input."
    )
    inputs.add_argument(
        "--empty", action="store_true", help="Explicitly initialize a new empty tree."
    )
    inputs.add_argument(
        "--upgrade", action="store_true", help="Measure only files named by a legacy inventory."
    )
    inputs.add_argument(
        "--paths", type=Path, help="Named UTF-8 list, one public-root-relative file path per line."
    )
    args = parser.parse_args()
    if args.upgrade:
        upgrade_inventory(args.public_root, state_root=args.state_root)
        return 0
    if args.paths is not None:
        initialize_from_paths(
            args.public_root,
            paths=args.paths.read_text(encoding="utf-8-sig").splitlines(),
            state_root=args.state_root,
            state_paths=(
                args.state_paths.read_text(encoding="utf-8-sig").splitlines()
                if args.state_paths is not None
                else []
            ),
        )
        return 0
    seed = (
        PublicationInventory.read(args.seed)
        if args.seed is not None
        else PublicationInventory(version=PublicationInventory.schema_version(), dates=[])
    )
    initialize_inventory(args.public_root, seed=seed, state_root=args.state_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
