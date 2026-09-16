"""What did the three cases measure, and did they all read the same two articles?"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from idhazh.contracts.pipeline_tests import PipelineTestsConfig

CASES_ROOT = Path("backend/var/cases")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", required=True, help="Item ids the draw chose.")
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--cases-root", type=Path, default=CASES_ROOT)
    args = parser.parse_args(argv)

    settings = PipelineTestsConfig.from_json(
        (args.config_root / "pipeline-tests.json").read_text(encoding="utf-8")
    )
    expected = sorted(args.expected.split())
    print("| case | items | summaries | model ms | failed |")
    print("| --- | --- | --- | --- | --- |")

    silent: list[str] = []
    disagreed: list[str] = []
    for case in settings.cases:
        items = args.cases_root / case.id / "run" / "items"
        landed = sorted(path.name.split(".")[0] for path in items.glob("*.article.json"))
        summaries = sorted(items.glob("*.summary.json"))
        spent = 0
        failed = []
        for path in summaries:
            summary = json.loads(path.read_text(encoding="utf-8"))
            spent += summary.get("summarize_ms") or 0
            if summary.get("status") != "ok":
                failed.append(f"{path.name.split('.')[0]}:{summary.get('failure_code')}")
        note = ", ".join(failed) or "-"
        if not landed:
            silent.append(case.id)
            note = "nothing recorded"
        elif landed != expected:
            disagreed.append(f"{case.id} recorded {landed}")
        print(f"| {case.id} | {len(landed)} | {len(summaries)} | {spent} | {note} |")

    print("")
    print(f"the draw asked every case for {' and '.join(expected)}")
    if silent:
        print(f"these cases produced nothing: {', '.join(silent)}")
    # A case that recorded other articles has produced numbers nobody may
    # subtract, so this raises where a silent case only reports.
    if disagreed:
        raise SystemExit(
            "the cases did not all read the same two articles, so nothing here compares: "
            + "; ".join(disagreed)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
