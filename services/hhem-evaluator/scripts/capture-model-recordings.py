"""Record actual official CPU predictions for the named project-authored fixture."""

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from hhem_evaluator.fail_evaluation import EvaluationFailure
from hhem_evaluator.fingerprint_model import canonical_bytes
from hhem_evaluator.load_model import load_model, quiet_model_output
from hhem_evaluator.load_settings import load_settings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    root: Path = args.root
    fixture = root / "tests" / "fixtures" / "hhem-evaluator"
    settings = load_settings(root / "config" / "hhem-evaluator" / "settings.json")
    inputs = json.loads((fixture / "model-inputs.json").read_bytes())
    try:
        predictor = load_model(settings, root, local_only=False)
        predictions = []
        for case in inputs["cases"]:
            with quiet_model_output():
                score = predictor.score(case["source_text"], case["summary_text"])
            predictions.append(
                {
                    "id": case["id"],
                    "input_sha256": hashlib.sha256(
                        canonical_bytes([case["source_text"], case["summary_text"]])
                    ).hexdigest(),
                    "score": score,
                }
            )
    except EvaluationFailure as failure:
        print(failure.error.model_dump_json(), file=sys.stderr)
        return 1
    except Exception:
        print('{"code":"MODEL_SCORING_FAILED"}', file=sys.stderr)
        return 1
    recorded_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    (fixture / "model-predictions.json").write_text(
        json.dumps(
            {
                "version": settings.version,
                "recorded_at": recorded_at,
                "model_identity_sha256": hashlib.sha256(
                    canonical_bytes(predictor.identity.model_dump(mode="json"))
                ).hexdigest(),
                "cases": predictions,
            },
            indent=2,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )
    (fixture / "model-identity.json").write_text(
        json.dumps(predictor.identity.model_dump(mode="json"), indent=2) + "\n",
        encoding="utf-8",
    )
    print('{"status":"captured","case_count":' + str(len(predictions)) + "}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
