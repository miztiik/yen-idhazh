"""Read named host plans and completions and report verification without writes."""

from __future__ import annotations

import argparse
import json
from dataclasses import fields
from pathlib import Path

from idhazh.contracts.host_output import HostWriteCompletion, HostWritePlan, HostWriterIdentity
from idhazh.telemetry.host_output_verify import (
    VerificationLimits,
    load_verification_document,
    verify_host_output,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog=(
            "Raw host files contain exactly one row. Parquet admits only flat "
            "int64/float64/string PLAIN or one-entry dictionary pages before row decoding. "
            "The decode budget includes actual pages and Arrow flat-cell buffers; "
            "max-json-depth also bounds compact Thrift nesting."
        ),
    )
    parser.add_argument("--workspace-root", required=True, type=Path)
    parser.add_argument("--target-root", required=True)
    parser.add_argument("--plan", required=True, type=Path)
    parser.add_argument("--completion", required=True, type=Path)
    parser.add_argument("--previous-plan", type=Path)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt", required=True, type=int)
    parser.add_argument("--job", required=True)
    parser.add_argument("--shard", required=True, type=int)
    parser.add_argument("--git-sha", required=True)
    parser.add_argument("--publication-producer", required=True)
    parser.add_argument("--allow-partial", action="store_true")
    for field in fields(VerificationLimits):
        parser.add_argument("--" + field.name.replace("_", "-"), required=True, type=int)
    args = parser.parse_args(argv)
    try:
        limits = VerificationLimits(
            **{field.name: getattr(args, field.name) for field in fields(VerificationLimits)}
        )
        root = args.workspace_root.absolute()

        def load(path: Path) -> dict[str, object]:
            return load_verification_document(
                path if path.is_absolute() else root / path, root=root, limits=limits
            )

        identity = HostWriterIdentity.model_validate(
            {
                "run_id": args.run_id,
                "attempt": args.attempt,
                "job": args.job,
                "shard": args.shard,
                "git_sha": args.git_sha,
                "producer": args.publication_producer,
            }
        )
        result = verify_host_output(
            HostWritePlan.model_validate(load(args.plan)),
            HostWriteCompletion.model_validate(load(args.completion)),
            workspace_root=root,
            target_root=args.target_root,
            publication_identity=identity,
            limits=limits,
            require_all=not args.allow_partial,
            previous_plan=(
                HostWritePlan.model_validate(load(args.previous_plan))
                if args.previous_plan
                else None
            ),
        )
        print(
            json.dumps(
                {
                    "verified_files": len(result.files),
                    "planned_files": result.planned_files,
                    "complete": result.complete,
                    "physical_sha256": {
                        file.relative_path: file.physical_sha256 for file in result.files
                    },
                },
                sort_keys=True,
            )
        )
        return 0
    except (ValueError, OSError, TypeError) as exc:
        print(
            json.dumps(
                {
                    "verified": False,
                    "error": type(exc).__name__,
                    "reason": str(exc).splitlines()[0],
                },
                sort_keys=True,
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
