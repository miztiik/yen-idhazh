"""Delete this run's copy of any rendered asset origin already published.

`.github/scripts/commit-and-push.sh` pipes `git ls-tree` over the tip the push
wants into this, once per attempt, before it rebases. Everything it decides is
in `idhazh.render.drop_raced_assets`; this file only turns a tree listing into
that call, so the naming contract stays in the module that owns it.

Usage: `git ls-tree -r --name-only <ref> -- <paths> | drop_raced_assets.py
--date YYYY-MM-DD`, from the root of a checkout.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Final

from idhazh.render import drop_raced_assets

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
    dropped = drop_raced_assets(
        public_root=root / "frontend" / "public",
        items_dir=root / "backend" / "var" / "run" / args.date / "items",
        published=published,
    )
    for relpath in dropped:
        print(f"{relpath} is already published, so this run's copy of it was dropped")


if __name__ == "__main__":
    main()
