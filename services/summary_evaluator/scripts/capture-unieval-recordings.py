"""Capture actual UniEval comparisons for the named project-authored fixture inputs."""

import argparse
import hashlib
from datetime import UTC, datetime
from pathlib import Path

from recording_json import canonical_bytes

from summary_evaluator.serve_http.api_settings import load_scorer_api_settings
from summary_evaluator.serve_http.load_scorer_settings import load_unieval_settings
from summary_evaluator.unieval.contracts.previous_unieval_result import (
    PreviousEffectiveUnievalControls,
    PreviousUnievalError,
)
from summary_evaluator.unieval.contracts.unieval_contract import UNIEVAL_VERSION
from summary_evaluator.unieval.contracts.unieval_recording import (
    RecordedUnievalCase,
    RecordedUnievalComparison,
    UnievalRecordingInputs,
    UnievalRecordingPredictions,
)
from summary_evaluator.unieval.contracts.unieval_request import UnievalControls, UnievalRequest
from summary_evaluator.unieval.load_unieval import load_unieval
from summary_evaluator.unieval.prepare_unieval_resources import (
    atomic_write,
    prepare_unieval_resources,
)
from summary_evaluator.unieval.score_unieval import prepare_unieval


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    directory = root / "tests" / "fixtures" / "unieval-evaluator"
    inputs = UnievalRecordingInputs.model_validate_json(
        (directory / "model-inputs.json").read_bytes()
    )
    settings = load_unieval_settings(
        root, load_scorer_api_settings(root / "config" / "summary-evals" / "api.json", "unieval")
    )
    prepare_unieval_resources(root, settings, include_weights=True)
    predictor = load_unieval(settings, root)
    identity = canonical_bytes(predictor.identity.model_dump(mode="json"))
    cases: list[RecordedUnievalCase] = []
    for case in inputs.cases:
        controls = UnievalControls.model_validate({
            **case.controls.model_dump(), "evaluate_relevance": True,
        })
        request = UnievalRequest.model_validate({
            **case.request.model_dump(), "evaluate_relevance": True,
        })
        selected = settings.model_copy(update={"scoring": controls})
        plan = prepare_unieval(request, selected, predictor.resources)
        predictions = tuple(
            RecordedUnievalComparison(
                dimension=comparison.dimension,
                index=comparison.index,
                sentence_index=comparison.sentence_index,
                source_index=comparison.source_index,
                prompt_sha256=hashlib.sha256(comparison.prompt.encode("utf-8")).hexdigest(),
                score=predictor.score(comparison.prompt),
            )
            for comparison in plan.comparisons
        )
        cases.append(
            RecordedUnievalCase(
                id=case.id,
                input_sha256=hashlib.sha256(
                    canonical_bytes(case.model_dump(mode="json"))
                ).hexdigest(),
                effective_settings=PreviousEffectiveUnievalControls.model_validate(
                    plan.controls.model_dump(exclude={"evaluate_relevance"})
                ),
                work=plan.work,
                errors=tuple(
                    PreviousUnievalError.model_validate_json(error.model_dump_json())
                    for error in plan.errors
                ),
                comparisons=predictions,
            )
        )
    result = UnievalRecordingPredictions(
        version=UNIEVAL_VERSION,
        recorded_at=datetime.now(UTC),
        model_identity_sha256=hashlib.sha256(identity).hexdigest(),
        cases=tuple(cases),
    )
    atomic_write(directory / "model-identity.json", identity + b"\n")
    atomic_write(
        directory / "model-predictions.json",
        result.model_dump_json(indent=2).encode("utf-8") + b"\n",
    )
    print("Actual UniEval predictions captured for the named inputs; no workflow proof claimed.")


if __name__ == "__main__":
    main()
