"""Which explicit local dataset stage did the operator request?"""

from __future__ import annotations

import argparse
from pathlib import Path

from idhazh.story_dataset.commands import execute


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--root", type=Path, default=Path("corpus") / "story-dataset-1")
    parser.add_argument("--policy", type=Path, default=Path("config") / "story-dataset.json")
    commands = parser.add_subparsers(dest="command", required=True)
    freeze = commands.add_parser("freeze")
    freeze.add_argument("--examples", type=Path, required=True)
    commands.add_parser("status")
    commands.add_parser("schema").add_argument("--output", type=Path, required=True)
    export = commands.add_parser("export")
    export.add_argument("--operation", choices=("primary", "review"), default="primary")
    export.add_argument("--ids", type=Path)
    export.add_argument("--output", type=Path, required=True)
    commands.add_parser("import").add_argument("--input", type=Path, required=True)
    catalog = commands.add_parser("catalog")
    catalog.add_argument("--output", type=Path, required=True)
    commands.add_parser("catalog-review").add_argument("--input", type=Path, required=True)
    vectors = commands.add_parser("vectors")
    vectors.add_argument("--vector-root", type=Path, required=True)
    vectors.add_argument("--output", type=Path, required=True)
    relocation = commands.add_parser("relocate-vectors")
    relocation.add_argument("--expected-revision", required=True)
    relocation.add_argument(
        "--file",
        action="append",
        default=[],
        metavar="SHA256=PATH",
        help="Explicit replacement location with the exact historical file hash; repeat as needed.",
    )
    relocation.add_argument("--output", type=Path, required=True)
    pairs = commands.add_parser("pairs")
    pairs.add_argument("--queries", type=Path)
    pairs.add_argument("--output", type=Path, required=True)
    pairs.add_argument("--metadata-only", action="store_true")
    addition = commands.add_parser("pair-add")
    addition.add_argument("--frame", type=Path, required=True)
    addition.add_argument("--input", type=Path, required=True)
    addition.add_argument("--output", type=Path, required=True)
    export_pairs = commands.add_parser("pair-export")
    export_pairs.add_argument("--frame", type=Path, required=True)
    export_pairs.add_argument("--ids", type=Path)
    export_pairs.add_argument("--output", type=Path, required=True)
    export_pairs.add_argument("--operation", choices=("primary", "review"), default="primary")
    commands.add_parser("pair-import").add_argument("--input", type=Path, required=True)
    split = commands.add_parser("split")
    split.add_argument("--frame", type=Path)
    split.add_argument("--previous", type=Path)
    split.add_argument("--output", type=Path, required=True)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--frame", type=Path)
    evaluate.add_argument("--retrieval", type=Path)
    evaluate.add_argument("--clusters", type=Path)
    evaluate.add_argument("--vectors", type=Path)
    evaluate.add_argument("--output", type=Path, required=True)
    commands.add_parser("history").add_argument("--output", type=Path, required=True)
    commands.add_parser("checkpoint").add_argument("--output", type=Path, required=True)
    commands.add_parser("restore-checkpoint").add_argument("--input", type=Path, required=True)
    commands.add_parser("freeze-development").add_argument("--input", type=Path, required=True)
    prediction = commands.add_parser("predict")
    prediction.add_argument("--config", type=Path, required=True)
    prediction.add_argument("--vectors", type=Path)
    prediction.add_argument("--ids", type=Path, required=True)
    prediction.add_argument("--model", required=True)
    prediction.add_argument("--partition", choices=("development", "confirmation"), required=True)
    prediction.add_argument(
        "--relation", choices=("topic", "event", "story", "occurrence", "duplicate"), required=True
    )
    prediction.add_argument("--cluster", action="store_true")
    prediction.add_argument("--output", type=Path, required=True)
    encoding = commands.add_parser("encode")
    encoding.add_argument("--ids", type=Path, required=True)
    encoding.add_argument("--model", required=True)
    encoding.add_argument("--output", type=Path, required=True)
    extension = commands.add_parser("vector-import")
    extension.add_argument("--input", type=Path, required=True)
    extension.add_argument("--output", type=Path, required=True)
    resume = commands.add_parser("resume")
    resume.add_argument("--batch-id", required=True)
    resume.add_argument("--output", type=Path, required=True)
    try:
        execute(parser.parse_args())
    except (ValueError, OSError) as error:
        parser.exit(2, f"refused: {error}\n")


if __name__ == "__main__":
    main()
