"""What did the re-encode change, day by day?"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digest-root", type=Path, default=Path("frontend/public/digest"))
    args = parser.parse_args(argv)

    items = vectors = 0
    for path in sorted(args.digest_root.glob("*/*/*/digest.json")):
        day = json.loads(path.read_text(encoding="utf-8"))
        drawn = len((day.get("embeddings") or {}).get("vectors", {}))
        held = len(day["items"])
        items += held
        vectors += drawn
        print(f"{day['date']}  items={held:>5}  vectors={drawn:>5}")
    print(f"corpus: {vectors} vectors over {items} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
