"""Which task stops generation or evaluates an existing saved handoff?"""

import argparse
import asyncio
import os
import sys
from pathlib import Path

from .contracts import PipelineError
from .failures import WorkflowError
from .report_saved_scores import render_saved_scores
from .run_task import run_task
from .saved_requests import SavedSummary, read_saved_requests
from .score_saved_summaries import score_saved_summaries
from .settings import load_pipeline_settings
from .stop_generation import stop_generation


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    stop = commands.add_parser("stop-generation")
    stop.add_argument("--pid-file", action="append", required=True, type=Path)
    evaluate = commands.add_parser("evaluate")
    evaluate.add_argument("--requests", required=True, type=Path)
    args = parser.parse_args()
    try:
        root = args.root.resolve()
        os.chdir(root)
        pipeline = load_pipeline_settings(root)
    except (OSError, ValueError):
        raise WorkflowError("INPUT_INVALID", "input") from None
    if args.command == "stop-generation":
        errors = stop_generation(root, args.pid_file, pipeline)
    else:
        directory = root / pipeline.output_directory / "saved-summaries"
        directory.mkdir(parents=True, exist_ok=True)
        if os.environ.get("GITHUB_OUTPUT"):
            with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
                output.write(f"output_directory={directory.relative_to(root).as_posix()}\n")
        summaries: tuple[SavedSummary, ...] = ()
        collected: list[PipelineError] = []
        try:
            summaries = read_saved_requests(args.requests, pipeline.max_input_bytes)
            run_task(
                lambda: score_saved_summaries(root, summaries, directory, pipeline, collected)
            )
        except WorkflowError as failure:
            collected.append(failure.error)
        except asyncio.CancelledError:
            collected.append(WorkflowError("TASK_CANCELLED", "evaluation").error)
        except (OSError, ValueError, KeyError, TypeError):
            collected.append(WorkflowError("EVALUATION_FAILED", "evaluation").error)
        report = render_saved_scores(summaries, collected)
        temporary = directory / "report.md.tmp"
        temporary.write_text(report, encoding="utf-8")
        temporary.replace(directory / "report.md")
        if os.environ.get("GITHUB_STEP_SUMMARY"):
            with Path(os.environ["GITHUB_STEP_SUMMARY"]).open("a", encoding="utf-8") as summary:
                summary.write(report)
        errors = tuple(collected) + tuple(detail for saved in summaries for detail in saved.errors)
        if not summaries or any(
            saved.outcomes.hhem is None or saved.outcomes.hhem.status != "complete"
            or saved.outcomes.unieval is None or saved.outcomes.unieval.status != "complete"
            for saved in summaries
        ):
            for detail in errors:
                print(detail.model_dump_json(), file=sys.stderr)
            raise SystemExit(1)
    for detail in errors:
        print(detail.model_dump_json(), file=sys.stderr)
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
