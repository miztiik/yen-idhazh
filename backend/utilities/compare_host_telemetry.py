"""Which isolated host-evidence operation did the operator request?"""

from __future__ import annotations

import argparse
from pathlib import Path

from idhazh.telemetry.host_evidence_comparison import compare
from idhazh.telemetry.host_evidence_inputs import isolated_workspace
from utilities.host_telemetry_session import cleanup, drain, prepare, start, workload


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "verb", choices=("prepare", "start", "workload", "drain", "compare", "cleanup")
    )
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--git-sha")
    parser.add_argument("--run-number")
    parser.add_argument("--attempt", type=int)
    parser.add_argument("--compile", type=Path)
    parser.add_argument("--gates", type=Path)
    parser.add_argument("--probe")
    parser.add_argument("--clock")
    args = parser.parse_args()
    if args.verb == "prepare":
        if not all((args.git_sha, args.run_number, args.attempt, args.compile, args.gates)):
            parser.error("prepare requires git-sha, run-number, attempt, compile and gates")
        prepare(
            args.workspace,
            git_sha=args.git_sha,
            run_number=args.run_number,
            attempt=args.attempt,
            compile_file=args.compile,
            gates=args.gates,
        )
    elif args.verb == "compare":
        if not args.probe or not args.clock:
            parser.error("compare requires the exact native probe and clock result paths")
        report = compare(isolated_workspace(args.workspace), probe=args.probe, clock=args.clock)
        if report.correctness != "passed":
            raise SystemExit(
                "isolated comparison failed; retain the report without widening bounds"
            )
    else:
        {"start": start, "workload": workload, "drain": drain, "cleanup": cleanup}[args.verb](
            isolated_workspace(args.workspace)
        )


if __name__ == "__main__":
    main()
