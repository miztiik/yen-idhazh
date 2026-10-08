"""What does each pipeline test case change about the config it runs under?"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from idhazh.contracts.pipeline_tests import TRIAL_STATE_PREFIX, PipelineTestsConfig
from idhazh.llm.server import SETTING_KEYS
from utilities.pipeline_test_case import TEST_CASES_ROOT


def write_test_case(test_case: object, *, source: Path, root: Path) -> Path:
    """Two files move, and one intention moves both.

    `visuals.enabled_kinds` empty is what makes no picture reachable;
    `summarize.asks_for_a_visual_plan` false is what sizes the window for the
    call really sent. Apart they disagree, and the disagreement refuses articles
    that fit.

    The test case also names its own child under the shared trial root, so three
    test cases write separate trees without changing their writer identities.
    """
    if root.exists():
        shutil.rmtree(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, root)

    app_path = root / "idhazh.json"
    app = json.loads(app_path.read_text(encoding="utf-8"))
    # Through `.get`, because the committed config carries only what differs from
    # a default - so a block this test case moves may not be in the file at all.
    summarize = dict(app.get("summarize") or {})
    summarize["asks_for_a_visual_plan"] = test_case.asks_for_a_visual_plan  # type: ignore[attr-defined]
    app["summarize"] = summarize
    if not test_case.asks_for_a_visual_plan:  # type: ignore[attr-defined]
        visuals = dict(app.get("visuals") or {})
        visuals["enabled_kinds"] = []
        app["visuals"] = visuals
    run = dict(app.get("run") or {})
    run["trial_state_dirname"] = TRIAL_STATE_PREFIX
    run["trial_case_dirname"] = test_case.id  # type: ignore[attr-defined]
    app["run"] = run
    app_path.write_text(json.dumps(app, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    models_path = root / app["models_file"]
    models = json.loads(models_path.read_text(encoding="utf-8"))
    entry = dict(models["summarizer"])
    server = dict(entry["server"])
    if test_case.n_parallel is not None:  # type: ignore[attr-defined]
        server[SETTING_KEYS["n_parallel"]] = test_case.n_parallel  # type: ignore[attr-defined]
    if test_case.n_ctx is not None:  # type: ignore[attr-defined]
        server[SETTING_KEYS["n_ctx"]] = test_case.n_ctx  # type: ignore[attr-defined]
    entry["server"] = server
    models["summarizer"] = entry
    models_path.write_text(json.dumps(models, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--test-cases-root", type=Path, default=TEST_CASES_ROOT)
    args = parser.parse_args(argv)

    settings = PipelineTestsConfig.from_json(
        (args.config_root / "pipeline-tests.json").read_text(encoding="utf-8")
    )
    for test_case in settings.test_cases:
        root = write_test_case(
            test_case, source=args.config_root, root=args.test_cases_root / test_case.id / "config"
        )
        print(f"{test_case.id}={root.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
