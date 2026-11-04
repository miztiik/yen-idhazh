"""Start the selected shared API component as an owned workflow child."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "backend"))

if __name__ == "__main__":
    from summary_eval_pipeline.serve_api import main

    main()
