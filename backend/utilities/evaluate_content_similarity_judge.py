"""Which explicit offline evaluation operation did the operator request?"""

from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path

from idhazh import config, crash_trace
from idhazh.content_similarity_judge.freeze_evaluation import freeze_files
from idhazh.content_similarity_judge.run_evaluation import capture_file
from idhazh.content_similarity_judge.score_evaluation import score_files


def main(argv: list[str] | None = None) -> int:
    """Route named files to freeze, capture or score; no council or publishing action exists."""
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config-dir", type=Path, default=config.DEFAULT_CONFIG_DIR)
    common.add_argument("--output-root", type=Path, required=True)
    parser = argparse.ArgumentParser(description=__doc__)
    operations = parser.add_subparsers(dest="operation", required=True)
    freezing = operations.add_parser("freeze", parents=[common])
    freezing.add_argument("--selection", type=Path, required=True)
    freezing.add_argument("--source-root", type=Path, required=True)
    freezing.add_argument("--split", choices=("development", "confirmation"), required=True)
    capturing = operations.add_parser("capture", parents=[common])
    capturing.add_argument("--set", dest="set_path", type=Path, required=True)
    capturing.add_argument("--split", choices=("development", "confirmation"), required=True)
    capturing.add_argument("--host", type=Path, required=True)
    scoring = operations.add_parser("score", parents=[common])
    scoring.add_argument("--set", dest="set_path", type=Path, required=True)
    scoring.add_argument("--labels", type=Path)
    scoring.add_argument("--run", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.operation == "freeze":
        frozen, blind = freeze_files(
            selection_path=args.selection, source_root=args.source_root,
            output_root=args.output_root, split=args.split, config_dir=args.config_dir,
        )
        print(f"set={frozen.name}\nannotation={blind.name}")
        return 0
    if args.operation == "capture":
        revision = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=config.REPO_ROOT,
            check=True, capture_output=True, text=True,
        ).stdout.strip()
        run, path = capture_file(
            set_path=args.set_path, split=args.split, config_dir=args.config_dir,
            host_path=args.host, git_sha=revision, output_root=args.output_root,
        )
        print(f"state={run.state}\nrun={path.name}")
        return 0
    report, path = score_files(
        set_path=args.set_path, labels_path=args.labels, run_path=args.run,
        output_root=args.output_root, config_dir=args.config_dir,
    )
    print(f"state={report.state}\nreport={path.name}")
    if report.blockers:
        print("blockers=" + ",".join(report.blockers))
    return 2 if report.state == "blocked" else 0


if __name__ == "__main__":
    crash_trace.install()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
