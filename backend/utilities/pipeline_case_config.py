"""What does each pipeline-test case change about the config it runs under?"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from idhazh.contracts.pipeline_tests import PipelineTestsConfig
from idhazh.llm.server import SETTING_KEYS

CASES_ROOT = Path("backend/var/cases")


def write_case(case: object, *, source: Path, root: Path) -> Path:
    """Two files move, and one intention moves both.

    `visuals.enabled_kinds` empty is what makes no picture reachable;
    `summarize.asks_for_a_visual_plan` false is what sizes the window for the
    call really sent. Apart they disagree, and the disagreement refuses articles
    that fit.

    The case also names its own trial root, so three cases write three trees and
    none of them shares a path with another.
    """
    if root.exists():
        shutil.rmtree(root)
    root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, root)

    app_path = root / "idhazh.json"
    app = json.loads(app_path.read_text(encoding="utf-8"))
    # Through `.get`, because the committed config carries only what differs from
    # a default - so a block this case moves may not be in the file at all.
    summarize = dict(app.get("summarize") or {})
    summarize["asks_for_a_visual_plan"] = case.asks_for_a_visual_plan  # type: ignore[attr-defined]
    app["summarize"] = summarize
    if not case.asks_for_a_visual_plan:  # type: ignore[attr-defined]
        visuals = dict(app.get("visuals") or {})
        visuals["enabled_kinds"] = []
        app["visuals"] = visuals
    run = dict(app.get("run") or {})
    run["trial_state_dirname"] = case.trial_state_dirname  # type: ignore[attr-defined]
    app["run"] = run
    app_path.write_text(json.dumps(app, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    models_path = root / app["models_file"]
    models = json.loads(models_path.read_text(encoding="utf-8"))
    entry = dict(models["summarizer"])
    server = dict(entry["server"])
    if case.n_parallel is not None:  # type: ignore[attr-defined]
        server[SETTING_KEYS["n_parallel"]] = case.n_parallel  # type: ignore[attr-defined]
    if case.n_ctx is not None:  # type: ignore[attr-defined]
        server[SETTING_KEYS["n_ctx"]] = case.n_ctx  # type: ignore[attr-defined]
    entry["server"] = server
    models["summarizer"] = entry
    models_path.write_text(json.dumps(models, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return root


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config-root", type=Path, default=Path("config"))
    parser.add_argument("--cases-root", type=Path, default=CASES_ROOT)
    args = parser.parse_args(argv)

    settings = PipelineTestsConfig.from_json(
        (args.config_root / "pipeline-tests.json").read_text(encoding="utf-8")
    )
    for case in settings.cases:
        root = write_case(case, source=args.config_root, root=args.cases_root / case.id / "config")
        print(f"{case.id}={root.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
