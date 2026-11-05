"""Which quality measurements does the complete, identity-bound offline evidence support?"""

from __future__ import annotations

import json
import logging
import math
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Final

import numpy as np
from numpy.typing import NDArray
from scipy.stats import bootstrap
from sklearn.metrics import precision_recall_fscore_support

from idhazh import config, event_lines
from idhazh.atomic_write import write_atomic
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.content_similarity_judge.evaluation_events import EvaluationEvidenceRefused
from idhazh.content_similarity_judge.freeze_evaluation import private_output, validate_inputs
from idhazh.content_similarity_judge.run_evaluation import config_sha256
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.content_similarity_judge_evaluation import (
    EvaluationAnnotation,
    EvaluationBlocker,
    EvaluationCase,
    EvaluationClassMetrics,
    EvaluationLabels,
    EvaluationPrediction,
    EvaluationReading,
    EvaluationReport,
    EvaluationRun,
    EvaluationSet,
    EvaluationStream,
    EvaluationStreamReport,
    document_sha256,
)
from idhazh.contracts.knobs.content_similarity_judge import ContentSimilarityEvaluationConfig
from idhazh.contracts.knobs.models import ModelRef
from idhazh.contracts.story_similarity_pair import JUDGE_POLICY_VERSION, SameStoryVerdict
from idhazh.llm.server import one_reply, parse_completion
from idhazh.similarity import judge, prompt

LOG: Final = logging.getLogger("idhazh")
VERDICTS: Final = tuple(SameStoryVerdict)
PREDICTIONS: Final[tuple[EvaluationPrediction, ...]] = (
    "YES", "NO", "UNCLEAR", "DISAGREE", "REFUSED",
)
RATE_COUNT: Final = 2 * len(VERDICTS)
STREAMS: Final[tuple[EvaluationStream, ...]] = ("representative", "challenge")


def _qualified_labels(
    evaluation: EvaluationSet, labels: EvaluationLabels | None,
) -> tuple[dict[str, SameStoryVerdict], set[EvaluationBlocker]]:
    if labels is None:
        return {}, {"missing_labels"}
    blockers: set[EvaluationBlocker] = set()
    if (
        labels.set_sha256 != document_sha256(evaluation)
        or labels.rubric_sha256 != derive_text_digest(labels.rubric)
    ):
        return {}, {"provenance_mismatch"}
    cases = {case.case_id: case for case in evaluation.cases}
    annotations: dict[str, list[EvaluationAnnotation]] = {
        case.case_id: [] for case in evaluation.cases
    }
    for row in labels.annotations:
        case = cases.get(row.case_id)
        if case is None or row.input_sha256 != case.input_sha256:
            blockers.add("provenance_mismatch")
        else:
            annotations[row.case_id].append(row)
    qualified: dict[str, SameStoryVerdict] = {}
    for case in evaluation.cases:
        rows = annotations[case.case_id]
        if not rows:
            continue
        if len({row.verdict for row in rows}) != 1:
            continue
        roles = {row.role for row in rows}
        required = {"primary", "independent"} if case.split == "confirmation" else {"primary"}
        if required <= roles and all(row.origin == "human" for row in rows):
            qualified[case.case_id] = rows[0].verdict
    return qualified, blockers


def _label_blockers(
    cases: Sequence[EvaluationCase], labels: EvaluationLabels | None,
) -> set[EvaluationBlocker]:
    blockers: set[EvaluationBlocker] = set()
    for case in cases:
        rows = [] if labels is None else [
            row for row in labels.annotations
            if row.case_id == case.case_id and row.input_sha256 == case.input_sha256
        ]
        roles = {row.role for row in rows}
        required = {"primary", "independent"} if case.split == "confirmation" else {"primary"}
        if not required <= roles:
            blockers.add("missing_labels")
        if any(row.origin != "human" for row in rows):
            blockers.add("unqualified_labels")
        if len({row.verdict for row in rows}) > 1:
            blockers.add("conflicting_labels")
    return blockers


def _reading_matches(
    reading: EvaluationReading, case: EvaluationCase, *, reverse: bool,
    settings: config.Settings,
) -> bool:
    """Recheck saved raw evidence through the production parser and closed policy."""
    entry = judge.entry_of(settings)
    left, right = (case.right, case.left) if reverse else (case.left, case.right)
    expected_user = prompt.user_turn(left, right)
    requests = [json.loads(body) for body in reading.request_json]
    if any(
        not isinstance(body.get("prompt"), str)
        or body["prompt"].count(expected_user) != 1
        or prompt.system_turn() not in body["prompt"]
        for body in requests
    ):
        return False
    answer = requests[-1]
    if (
        answer.get("grammar") != prompt.grammar()
        or any(answer.get(key) != value for key, value in judge.decode_settings(settings).items())
        or reading.thinking_spans != int(entry.thinks)
    ):
        return False
    replies = [
        parse_completion(raw, reasoning_delimiters=entry.reasoning_delimiters)
        for raw in reading.raw_response
    ]
    reply = replies[-1]
    if entry.thinks:
        reply = one_reply(thought=replies[0], answer=reply)
        if (
            entry.thinking_close is None
            or answer["prompt"] != requests[0]["prompt"] + replies[0].content + entry.thinking_close
        ):
            return False
    verdict = None
    reason = None
    try:
        verdict = judge.verdict_of(reply.content)
        judge._the_emission_opened_the_word_that_came_back(reply, verdict)
    except judge.GrammarNotAppliedError as refused:
        reason = refused.reason
        verdict = None
    return (
        reading.verdict == verdict
        and reading.refusal_reason == reason
        and reading.grammar_applied == (verdict is not None)
        and reading.prompt_tokens == reply.prompt_tokens
        and reading.completion_tokens == reply.completion_tokens
        and reading.first_token_margin == judge.margin_of(reply.first_token_choices)
        and reading.first_token_window == (
            judge.first_token_window(reply.first_token_choices) or None
        )
    )


def _predictions(
    evaluation: EvaluationSet, run: EvaluationRun, *, settings: config.Settings,
) -> tuple[dict[str, EvaluationPrediction], dict[str, list[float]], set[EvaluationBlocker]]:
    predictions: dict[str, EvaluationPrediction] = {}
    margins: dict[str, list[float]] = {}
    blockers: set[EvaluationBlocker] = set()
    selected = {case.case_id: case for case in evaluation.cases if case.split == run.split}
    model = ModelRef.model_validate(
        judge.entry_of(settings).model_dump(include=set(ModelRef.model_fields))
    )
    if (
        run.set_sha256 != document_sha256(evaluation)
        or run.config_sha256 != config_sha256(settings)
        or run.model != model
        or run.prompt_digest != prompt.prompt_digest()
        or run.grammar_digest != prompt.grammar_digest()
        or run.judge_policy_version != JUDGE_POLICY_VERSION
    ):
        return {}, {}, {"provenance_mismatch"}
    if set(selected) != {case.case_id for case in run.cases}:
        blockers.add("incomplete_capture")
        if any(case.case_id not in selected for case in run.cases):
            blockers.add("provenance_mismatch")
    if run.state != "captured":
        blockers.add("incomplete_capture")
    for row in run.cases:
        case = selected.get(row.case_id)
        if case is None or row.input_sha256 != case.input_sha256:
            blockers.add("provenance_mismatch")
            continue
        if row.forward is None or row.reverse is None:
            blockers.add("incomplete_capture")
            continue
        try:
            matches = (
                _reading_matches(row.forward, case, reverse=False, settings=settings)
                and _reading_matches(row.reverse, case, reverse=True, settings=settings)
            )
        except (ValueError, KeyError, TypeError):
            matches = False
        if not matches:
            event_lines.emit(
                EvaluationEvidenceRefused(scope="capture", case_id=case.case_id),
                logger=LOG, level=logging.WARNING,
            )
            blockers.add("provenance_mismatch")
            continue
        if row.forward.verdict is None or row.reverse.verdict is None:
            prediction: EvaluationPrediction = "REFUSED"
        elif row.forward.verdict != row.reverse.verdict:
            prediction = "DISAGREE"
        else:
            prediction = row.forward.verdict.value
        predictions[case.case_id] = prediction
        margins[case.case_id] = [
            reading.first_token_margin for reading in (row.forward, row.reverse)
            if reading.first_token_margin is not None
        ]
    return predictions, margins, blockers


def _metrics(gold: Sequence[str], predicted: Sequence[str]) -> NDArray[np.float64]:
    precision, recall, _, _ = precision_recall_fscore_support(
        gold, predicted, labels=[verdict.value for verdict in VERDICTS], zero_division=np.nan,
    )
    return np.asarray([*precision, *recall], dtype=np.float64)


def _class_metrics(
    cases: Sequence[EvaluationCase], labels: dict[str, SameStoryVerdict],
    predictions: dict[str, EvaluationPrediction], *, tuning: ContentSimilarityEvaluationConfig,
    blocked: bool,
) -> dict[SameStoryVerdict, EvaluationClassMetrics]:
    groups = sorted({case.group_id for case in cases})
    gold = [labels[case.case_id].value for case in cases] if not blocked else []
    predicted = [predictions[case.case_id] for case in cases] if not blocked else []
    values = (
        _metrics(gold, predicted) if cases and not blocked else np.full(RATE_COUNT, np.nan)
    )
    intervals: NDArray[np.float64] | None = None
    defined: NDArray[np.bool_] | None = None
    if not blocked and len(groups) >= 2 and tuning.resamples >= 2:
        members = [[index for index, case in enumerate(cases) if case.group_id == group]
                   for group in groups]

        def statistic(sample: NDArray[np.int64]) -> NDArray[np.float64]:
            indexes = [index for group in sample for index in members[int(group)]]
            measured = _metrics([gold[index] for index in indexes],
                                [predicted[index] for index in indexes])
            # Keep undefined resamples explicit without feeding NaNs to SciPy's quantiles.
            return np.concatenate((
                np.nan_to_num(measured, nan=0.0), np.isfinite(measured).astype(np.float64),
            ))

        seed = tuning.resample_seed
        if seed < 0:
            seed = int(derive_text_digest(str(seed)), 16)
        result = bootstrap(
            (np.arange(len(groups)),), statistic, vectorized=False, method="percentile",
            confidence_level=tuning.confidence_level, n_resamples=tuning.resamples,
            rng=np.random.default_rng(seed),
        )
        intervals = np.asarray([
            result.confidence_interval.low[:RATE_COUNT],
            result.confidence_interval.high[:RATE_COUNT],
        ], dtype=np.float64)
        defined = np.asarray(
            np.all(result.bootstrap_distribution[RATE_COUNT:] == 1, axis=1), dtype=np.bool_,
        )
    metrics: dict[SameStoryVerdict, EvaluationClassMetrics] = {}
    for index, verdict in enumerate(VERDICTS):
        fields: dict[str, object] = {}
        for name, position in (("precision", index), ("recall", index + len(VERDICTS))):
            value = float(values[position])
            fields[name] = value if math.isfinite(value) else None
            fields[name + "_lower"] = None
            fields[name + "_upper"] = None
            reason = None
            denominator_groups = {
                case.group_id for case in cases
                if (
                    predictions.get(case.case_id) == verdict.value
                    if name == "precision" else labels.get(case.case_id) == verdict
                )
            }
            if blocked:
                reason = "blocked"
            elif not math.isfinite(value):
                reason = "zero_denominator"
            elif len(denominator_groups) < 2:
                reason = "insufficient_groups"
            elif intervals is None or defined is None or not defined[position]:
                reason = "undefined_resamples"
            else:
                fields[name + "_lower"] = float(intervals[0, position])
                fields[name + "_upper"] = float(intervals[1, position])
            fields[name + "_interval_reason"] = reason
        metrics[verdict] = EvaluationClassMetrics.model_validate(fields)
    return metrics


def _stream_report(
    cases: Sequence[EvaluationCase], *, stream: EvaluationStream,
    labels: dict[str, SameStoryVerdict], predictions: dict[str, EvaluationPrediction],
    margins: dict[str, list[float]], tuning: ContentSimilarityEvaluationConfig, blocked: bool,
) -> EvaluationStreamReport:
    gold_counts = Counter(labels[case.case_id] for case in cases if case.case_id in labels)
    prediction_counts = Counter(
        predictions[case.case_id] for case in cases if case.case_id in predictions
    )
    confusion = {gold: dict.fromkeys(PREDICTIONS, 0) for gold in VERDICTS}
    for case in cases:
        if case.case_id in labels and case.case_id in predictions:
            confusion[labels[case.case_id]][predictions[case.case_id]] += 1
    diagnostics = None
    if not blocked:
        diagnostics = {}
        for outcome in PREDICTIONS:
            values = [value for case in cases if predictions[case.case_id] == outcome
                      for value in margins[case.case_id]]
            diagnostics[outcome] = sum(values) / len(values) if values else None
    return EvaluationStreamReport(
        stream=stream, case_count=len(cases), group_count=len({case.group_id for case in cases}),
        qualified_label_count=sum(gold_counts.values()),
        gold_counts={gold: gold_counts[gold] for gold in VERDICTS},
        prediction_counts={outcome: prediction_counts[outcome] for outcome in PREDICTIONS},
        confusion=confusion,
        valid_agreement_count=sum(prediction_counts[word.value] for word in VERDICTS),
        unclear_count=prediction_counts["UNCLEAR"],
        refusal_count=prediction_counts["REFUSED"],
        disagreement_count=prediction_counts["DISAGREE"],
        class_metrics=_class_metrics(cases, labels, predictions, tuning=tuning, blocked=blocked),
        margin_diagnostics=diagnostics,
    )


def score(
    evaluation: EvaluationSet, labels: EvaluationLabels | None, run: EvaluationRun, *,
    settings: config.Settings, tuning: ContentSimilarityEvaluationConfig,
) -> EvaluationReport:
    """Account for every selected case without opening a socket or inferring absent labels."""
    report_settings = ContentSimilarityEvaluationConfig.model_validate(tuning.model_dump())
    blockers: set[EvaluationBlocker] = set()
    try:
        validate_inputs(evaluation, max_cases=report_settings.max_cases)
    except ValueError:
        event_lines.emit(
            EvaluationEvidenceRefused(scope="set"), logger=LOG, level=logging.WARNING,
        )
        blockers.add("provenance_mismatch")
    qualified, label_errors = _qualified_labels(evaluation, labels)
    predictions, margins, capture_errors = _predictions(evaluation, run, settings=settings)
    selected = tuple(case for case in evaluation.cases if case.split == run.split)
    blockers |= label_errors | capture_errors | _label_blockers(selected, labels)
    if not selected:
        blockers.add("incomplete_capture")
    return EvaluationReport(
        version=EvaluationReport.schema_version(),
        set_sha256=document_sha256(evaluation),
        labels_sha256=(
            document_sha256(labels) if labels is not None
            else derive_text_digest(canonical_json(None))
        ),
        run_sha256=document_sha256(run),
        report_settings=report_settings,
        state="blocked" if blockers else "measured",
        blockers=tuple(sorted(blockers)),
        streams=tuple(
            _stream_report(
                tuple(case for case in selected if case.stream == stream), stream=stream,
                labels=qualified, predictions=predictions, margins=margins,
                tuning=report_settings, blocked=bool(blockers),
            )
            for stream in STREAMS
        ),
    )


def score_files(
    *, set_path: Path, labels_path: Path | None, run_path: Path,
    output_root: Path, config_dir: Path,
) -> tuple[EvaluationReport, Path]:
    """Score only the named saved documents, with no model initialization or network."""
    settings = config.load(config_dir)
    report = score(
        EvaluationSet.read(set_path),
        None if labels_path is None else EvaluationLabels.read(labels_path),
        EvaluationRun.read(run_path),
        settings=settings, tuning=judge_settings.load_evaluation(config_dir),
    )
    path = private_output(output_root, f"report-{document_sha256(report)}.json")
    write_atomic(path, report.to_json())
    return report, path
