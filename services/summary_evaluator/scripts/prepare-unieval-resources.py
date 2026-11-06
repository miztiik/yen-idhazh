"""Prepare named tokenizer/sentence assets, and optionally weights, before scoring."""

import argparse
from pathlib import Path

from summary_evaluator.serve_http.api_settings import load_api_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.unieval.prepare_unieval_resources import prepare_unieval_resources


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--include-weights", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    settings = load_unieval_settings(
        root, load_api_settings(root / "config" / "summary-evals" / "api.json")
    )
    prepare_unieval_resources(root, settings, include_weights=args.include_weights)
    print("Declared UniEval resources prepared; no model execution was claimed.")


if __name__ == "__main__":
    main()
