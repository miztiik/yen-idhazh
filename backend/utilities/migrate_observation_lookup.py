"""Explicitly migrate legacy evaluation IDs without rewriting evaluation row files."""

from __future__ import annotations

import argparse
import csv
import json
from collections.abc import Sequence
from dataclasses import asdict
from pathlib import Path

from idhazh.config import load_observation_lookup
from idhazh.contracts.base import StalePayloadError
from idhazh.evals.observation_migration import migrate


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--state-dir",
        type=Path,
        required=True,
        help="Explicit state directory; the lookup destination is derived inside it.",
    )
    parser.add_argument(
        "--existing",
        choices=("refuse", "verify"),
        default="refuse",
        help="Verify remaining source IDs against the existing lookup and finish CSV cleanup.",
    )
    args = parser.parse_args(argv)
    try:
        result = migrate(args.state_dir, load_observation_lookup(), existing=args.existing)
    except OSError as refusal:
        parser.exit(2, f"migration refused: {refusal.strerror or str(refusal)}\n")
    except (ValueError, csv.Error, StalePayloadError) as refusal:
        parser.exit(2, f"migration refused: {refusal}\n")
    print(json.dumps(asdict(result), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())