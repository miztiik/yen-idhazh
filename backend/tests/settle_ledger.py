"""Settle a ledger the way the shipped stage does, against the runner's own tree.

`python -m idhazh dedupe-ledgers` resolves `state/` off the installed package,
which under a test is the developer's own repository rather than the temporary
one the harness built - the same reason `rebuild_day.py` exists beside it. So
the harness substitutes the root and nothing else: this calls the shipped
`ledger.drop_repeated_rows`, with the key it is given, on a path relative to the
working directory the commit script runs in.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from idhazh import ledger


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, required=True)
    parser.add_argument("--key", required=True, help="Comma-separated column names.")
    args = parser.parse_args()
    dropped = ledger.drop_repeated_rows(args.path, tuple(args.key.split(",")))
    print(f"dropped {dropped} repeated rows from {args.path.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
