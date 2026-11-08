"""Create the shared Markdown report after all evaluator and host work is finished."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

if __name__ == "__main__":
    from summary_eval_pipeline.report_task import main

    main()
