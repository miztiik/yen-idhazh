"""Stop generation or score existing workflow summaries through native APIs."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))

if __name__ == "__main__":
    from summary_eval_pipeline.failures import WorkflowError
    from summary_eval_pipeline.saved_workflow import main

    try:
        main()
    except WorkflowError as error:
        print(error.error.model_dump_json(), file=sys.stderr)
        raise SystemExit(1) from None
    except OSError:
        print(WorkflowError("REPORT_FAILED", "report").error.model_dump_json(), file=sys.stderr)
        raise SystemExit(1) from None
