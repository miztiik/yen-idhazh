"""Point a scratch config at the candidate, by moving one line and nothing else.

Nothing is transplanted onto the entry: the candidate's own file carries its
own blocks.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

POINTER_KEY = "models_file"
SCRATCH = Path("backend/var/candidate-config")


def point_at(models_file: str, *, scratch: Path = SCRATCH) -> Path:
    path = scratch / "idhazh.json"
    settings = json.loads(path.read_text(encoding="utf-8"))
    settings[POINTER_KEY] = models_file
    path.write_text(json.dumps(settings, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-file", required=True)
    parser.add_argument("--scratch", type=Path, default=SCRATCH)
    args = parser.parse_args(argv)
    point_at(args.models_file, scratch=args.scratch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
