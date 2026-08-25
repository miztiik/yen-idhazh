"""Move this run's rendered assets off any path origin already published.

`.github/scripts/commit-and-push.sh` pipes `git ls-tree` over the tip the push
wants into this, once per attempt, before it rebases. Everything it decides is
in `idhazh.render.renumber_racing_assets`; this file only turns a tree listing
into that call, so the naming contract stays in the module that owns it.

Usage: `git ls-tree -r --name-only <ref> -- <paths> | renumber_racing_assets.py
--date YYYY-MM-DD`, from the root of a checkout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from idhazh.render import renumber_racing_assets

# What a published asset path is relative to. `asset_relpath` writes the rest of
# it, and a day payload carries the rest of it, so this prefix is the only part
# a tree listing adds.
PUBLIC_PREFIX: Final = "frontend/public/"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", required=True)
    args = parser.parse_args()

    root = Path.cwd()
    published = [
        line.removeprefix(PUBLIC_PREFIX)
        for line in (raw.strip() for raw in sys.stdin)
        if line.startswith(PUBLIC_PREFIX)
    ]
    moves = renumber_racing_assets(
        public_root=root / "frontend" / "public",
        items_dir=root / "backend" / "var" / "run" / args.date / "items",
        date=args.date,
        published=published,
    )
    for was, now in moves:
        print(f"{was} is already published, so this run's copy moved to {now}")


if __name__ == "__main__":
    main()
