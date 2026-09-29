"""What did each test case measure, and did it read the drawn pair and get one summarized?"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from idhazh.contracts.pipeline_tests import PipelineTestsConfig
from utilities.pipeline_test_case import TEST_CASES_ROOT


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", required=True, help="Item ids the draw chose.")
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--test-cases-root", type=Path, default=TEST_CASES_ROOT)
    args = parser.parse_args(argv)

    settings = PipelineTestsConfig.from_json(
        (args.config_root / "pipeline-tests.json").read_text(encoding="utf-8")
    )
    expected = sorted(args.expected.split())
    print("| test case | items | summaries | model ms | failed |")
    print("| --- | --- | --- | --- | --- |")

    silent: list[str] = []
    disagreed: list[str] = []
    unsummarized: list[str] = []
    for test_case in settings.test_cases:
        items = args.test_cases_root / test_case.id / "run" / "items"
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
            silent.append(test_case.id)
            note = "nothing recorded"
        elif landed != expected:
            disagreed.append(f"{test_case.id} recorded {landed}")
        if landed and len(failed) == len(summaries):
            unsummarized.append(test_case.id)
        print(f"| {test_case.id} | {len(landed)} | {len(summaries)} | {spent} | {note} |")

    print("")
    print(f"the draw asked every test case for {' and '.join(expected)}")
    if silent:
        print(f"these test cases produced nothing: {', '.join(silent)}")
    # A test case that recorded other articles has produced numbers nobody may
    # subtract, so this raises where a silent test case only reports.
    if disagreed:
        raise SystemExit(
            "the test cases did not all read the same two articles, so nothing here compares: "
            + "; ".join(disagreed)
        )
    # A test case whose articles all stopped before the model answered - a
    # refused download, a failed extraction, a call that never came back - has
    # said nothing about the model, so it fails the job rather than reading as a
    # pass. A silent test case is not counted here: its own step is already red.
    if unsummarized:
        raise SystemExit(
            "no article came back summarized, so these test cases said nothing about "
            "the model: " + ", ".join(unsummarized)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
