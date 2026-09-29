"""What did each enabled test case do with the drawn articles, and did one come back summarized?"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from idhazh.contracts.pipeline_tests import PipelineTestsConfig
from utilities.pipeline_test_case import TEST_CASES_ROOT


def _item_id(path: Path) -> str:
    return path.name.split(".")[0]


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
    print("| test case | articles | summarized | slowest article (s) | failed |")
    print("| --- | --- | --- | --- | --- |")

    silent: list[str] = []
    missing: list[str] = []
    strays: list[str] = []
    unsummarized: list[str] = []
    for test_case in settings.test_cases:
        if not test_case.enabled:
            continue
        # Every runner's articles, put back together: each runner uploads the
        # items it worked, and the download merges them under one test case.
        items = args.test_cases_root / test_case.id / "run" / "items"
        landed = sorted(_item_id(path) for path in items.glob("*.article.json"))
        summarized = sum(
            json.loads(path.read_text(encoding="utf-8")).get("status") == "ok"
            for path in items.glob("*.summary.json")
        )
        slowest_ms = 0
        failed = []
        for path in sorted(items.glob("*.health.json")):
            row = json.loads(path.read_text(encoding="utf-8"))
            slowest_ms = max(slowest_ms, row.get("item_total_ms") or 0)
            if row.get("outcome") != "ok":
                failed.append(f"{_item_id(path)}:{row.get('code')}")
        note = ", ".join(failed) or "-"
        absent = sorted(set(expected) - set(landed))
        extra = sorted(set(landed) - set(expected))
        if not landed:
            silent.append(test_case.id)
            note = "nothing recorded"
        elif not summarized:
            unsummarized.append(test_case.id)
        if landed and absent:
            missing.append(f"{test_case.id} is missing {' '.join(absent)}")
        if extra:
            strays.append(f"{test_case.id} recorded {' '.join(extra)}")
        print(f"| {test_case.id} | {len(landed)} | {summarized} | {slowest_ms // 1000} | {note} |")

    print("")
    print(f"the draw asked every test case for {' and '.join(expected)}")
    off = [test_case.id for test_case in settings.test_cases if not test_case.enabled]
    if off:
        print(f"switched off in config/pipeline-tests.json: {', '.join(off)}")
    # A runner that failed filed no run, so its articles are missing here and
    # its own job is already red. Named, so a reader need not count rows.
    if silent:
        print(f"these test cases produced nothing: {', '.join(silent)}")
    if missing:
        print(f"a runner of these test cases filed nothing: {'; '.join(missing)}")
    # An article the draw did not choose means a runner read another plan, so
    # nothing it reports belongs to this dispatch.
    if strays:
        raise SystemExit(
            "these test cases recorded articles the draw did not choose: " + "; ".join(strays)
        )
    # A test case whose articles all stopped before the model answered - a
    # refused download, a failed extraction, a call that never came back - has
    # said nothing about the model, so it fails the job rather than reading as a
    # pass. A silent test case is not counted here: its own job is already red.
    if unsummarized:
        raise SystemExit(
            "no article came back summarized, so these test cases said nothing about "
            "the model: " + ", ".join(unsummarized)
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())