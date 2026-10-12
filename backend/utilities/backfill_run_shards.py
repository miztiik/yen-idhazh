"""Backfill only manifest shard counts over an explicit inclusive UTC interval."""

import argparse
from pathlib import Path

from idhazh.contracts.base import ServerJob
from idhazh.contracts.file_envelope import WriterIdentity
from idhazh.telemetry.run_shards import backfill


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--digest", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--first", required=True)
    parser.add_argument("--through", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    count = backfill(
        args.digest,
        args.state,
        first=args.first,
        through=args.through,
        identity=WriterIdentity(
            run_id=args.run_id,
            attempt=1,
            job=ServerJob.OPERATOR,
            shard=0,
            producer="utilities.backfill_run_shards",
            git_sha=args.commit,
        ),
    )
    print(f"Filed {count} manifest count records in [{args.first}, {args.through}].")


if __name__ == "__main__":
    main()
