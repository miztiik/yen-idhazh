"""Run one visible preparation, generation or evaluation task."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

if __name__ == "__main__":
    from summary_eval_pipeline.run import main

    main()
