"""Which small task implements the requested visible workflow phase?"""

import argparse
import json
import os
from pathlib import Path

from .contracts import PhaseName
from .failures import WorkflowError
from .phases import run_phase
from .preparation import prepare_assets


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("phase", choices=("prepare", "generate", "evaluate"))
    args = parser.parse_args()
    root = args.root.resolve()
    os.chdir(root)
    try:
        if args.phase == "prepare":
            prepare_assets(root)
        else:
            phase: PhaseName = "generation" if args.phase == "generate" else "evaluation"
            evidence = run_phase(root, phase)
            print(
                json.dumps(
                    {"event": "summary_phase_finished", "phase": phase, "status": evidence.status}
                )
            )
            if evidence.status != "complete":
                raise SystemExit(1)
    except WorkflowError as failure:
        print(failure.error.model_dump_json())
        raise SystemExit(1) from None
    except (OSError, ValueError, KeyError):
        print(json.dumps({"event": "summary_phase_failed", "reason": "invalid_run_setup"}))
        raise SystemExit(1) from None
