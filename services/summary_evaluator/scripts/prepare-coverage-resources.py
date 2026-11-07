"""Prepare only the named legacy coverage resources, with weights selected explicitly."""

import argparse
from pathlib import Path

from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.source_coverage.load_settings import load_settings
from summary_evaluator.source_coverage.prepare_resources import prepare_resources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--include-weights", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    api = load_scorer_api_settings(root / "config" / "summary-evals" / "api.json", "coverage")
    settings = load_settings(root, api.listener, api.logging)
    prepare_resources(root, settings, include_weights=args.include_weights)
    print("Prepared named source-coverage resources; real inference is a separate capture.")


if __name__ == "__main__":
    main()
