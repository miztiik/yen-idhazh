"""Which frozen inputs, independent labels and captured readings support a judge report?"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, ClassVar, Literal, Self

from pydantic import Field, JsonValue, TypeAdapter, model_validator

from idhazh.contracts.base import (
    ChangelogEntry,
    CommitSha,
    Contract,
    DateStamp,
    ItemId,
    Model,
    RelPath,
    Sha256,
    Slug,
    Timestamp,
    canonical_json,
    derive_text_digest,
    derive_url_key,
)
from idhazh.contracts.digest_day import DigestItem
from idhazh.contracts.host_fingerprint import HostFingerprintRow
from idhazh.contracts.knobs.models import ModelRef
from idhazh.contracts.story_similarity_pair import ReadingRefusalReason, SameStoryVerdict

EvaluationSplit = Literal["development", "confirmation"]
EvaluationStream = Literal["representative", "challenge"]
EvaluationPrediction = Literal["YES", "NO", "UNCLEAR", "DISAGREE", "REFUSED"]
EvaluationBlocker = Literal[
    "missing_labels", "conflicting_labels", "unqualified_labels",
    "incomplete_capture", "provenance_mismatch",
]
IntervalReason = Literal[
    "blocked", "insufficient_groups", "zero_denominator", "undefined_resamples",
]
Count = Annotated[int, Field(strict=True, ge=0)]
Rate = Annotated[float, Field(strict=True, ge=0, le=1, allow_inf_nan=False)]
Seconds = Annotated[float, Field(strict=True, ge=0, allow_inf_nan=False)]


def document_sha256(document: Contract) -> str:
    """Bind the complete canonical document, including its recorded version."""
    return derive_text_digest(document.to_json())


def case_sha256(
    left: DigestItem, right: DigestItem, input_sha256: str,
    mutation_kind: str = "none", parent_case_id: str | None = None,
) -> str:
    """Bind the ordered articles, model-visible input and explicit variant."""
    return derive_text_digest(canonical_json({
        "articles": [derive_url_key(left.source_url), derive_url_key(right.source_url)],
        "input_sha256": input_sha256,
        "mutation_kind": mutation_kind,
        "parent_case_id": parent_case_id,
    }))


class EvaluationSource(Model):
    path: RelPath
    date: DateStamp
    sha256: Sha256

    @model_validator(mode="after")
    def _calendar_date(self) -> Self:
        datetime.strptime(self.date, "%Y-%m-%d")
        return self


class EvaluationMutation(Model):
    side: Literal["left", "right"]
    append_summary: str = Field(min_length=1)

    @model_validator(mode="after")
    def _nonempty_instruction(self) -> Self:
        if not self.append_summary.strip():
            raise ValueError("append_summary must contain text")
        return self


class EvaluationSelectionPair(Model):
    left_source: RelPath
    right_source: RelPath
    left_item_id: ItemId
    right_item_id: ItemId
    group_id: Slug
    split: EvaluationSplit
    stream: EvaluationStream
    mutation: EvaluationMutation | None = None


class EvaluationSelection(Model):
    sources: tuple[RelPath, ...] = Field(min_length=1)
    pairs: tuple[EvaluationSelectionPair, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _named_sources(self) -> Self:
        if len(set(self.sources)) != len(self.sources):
            raise ValueError("duplicate source paths")
        used = {path for pair in self.pairs for path in (pair.left_source, pair.right_source)}
        if used != set(self.sources):
            raise ValueError("sources must be exactly the paths named by pairs")
        return self


class EvaluationCase(Model):
    case_id: Sha256
    group_id: Slug
    split: EvaluationSplit
    stream: EvaluationStream
    left: DigestItem
    right: DigestItem
    left_source: RelPath
    right_source: RelPath
    input_sha256: Sha256
    parent_case_id: Sha256 | None = None
    mutation_kind: Literal["none", "planted_instruction"] = "none"

    def identity_sha256(self) -> str:
        """One ordered input and variant of two canonical articles."""
        return case_sha256(
            self.left, self.right, self.input_sha256, self.mutation_kind, self.parent_case_id
        )

    @model_validator(mode="after")
    def _identity_and_variant(self) -> Self:
        if self.left.source_url == self.right.source_url:
            raise ValueError("an article cannot be paired with itself")
        if (self.parent_case_id is None) != (self.mutation_kind == "none"):
            raise ValueError("planted instructions require a parent case")
        if self.case_id != self.identity_sha256():
            raise ValueError("case_id does not match article/input/variant identity")
        return self


def corpus_sha256(
    sources: tuple[EvaluationSource, ...], cases: tuple[EvaluationCase, ...],
) -> str:
    return derive_text_digest(canonical_json({
        "sources": [source.model_dump(mode="json") for source in sources],
        "cases": [case.model_dump(mode="json") for case in cases],
    }))


class EvaluationSet(Contract):
    """The named snapshots and exact frozen comparisons, with disjoint splits."""

    __schema_stem__: ClassVar[str] = "content-similarity-judge-evaluation-set"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-05", change="Declare frozen judge cases and source identities.",
            why="Saved comparisons must retain their exact inputs and split boundaries.",
        ),
    )

    sources: tuple[EvaluationSource, ...]
    cases: tuple[EvaluationCase, ...]
    corpus_sha256: Sha256
    sanitizer_sha256: Sha256

    def corpus_digest(self) -> str:
        return corpus_sha256(self.sources, self.cases)

    @model_validator(mode="after")
    def _consistent_population(self) -> Self:
        sources = {source.path: source for source in self.sources}
        cases = {case.case_id: case for case in self.cases}
        if len(sources) != len(self.sources) or len(cases) != len(self.cases):
            raise ValueError("duplicate sources or cases")
        articles: dict[str, EvaluationSplit] = {}
        groups: dict[str, EvaluationSplit] = {}
        copies: dict[tuple[str, str], DigestItem] = {}
        comparisons: set[tuple[tuple[tuple[str, str], ...], str]] = set()
        for case in self.cases:
            comparison = (
                tuple(sorted((item.source_url, item.summary) for item in (case.left, case.right))),
                case.mutation_kind,
            )
            if comparison in comparisons:
                raise ValueError("duplicate comparison, including reversed article order")
            comparisons.add(comparison)
            if groups.setdefault(case.group_id, case.split) != case.split:
                raise ValueError("an event group crosses splits")
            for path, item in ((case.left_source, case.left), (case.right_source, case.right)):
                if path not in sources:
                    raise ValueError("a case references an unknown source")
                article = derive_url_key(item.source_url)
                if articles.setdefault(article, case.split) != case.split:
                    raise ValueError("an article crosses splits")
                if case.mutation_kind == "none":
                    key = (path, item.item_id)
                    if copies.setdefault(key, item) != item:
                        raise ValueError("inconsistent frozen item copies")
            if case.parent_case_id is not None:
                parent = cases.get(case.parent_case_id)
                if parent is None or parent.mutation_kind != "none":
                    raise ValueError("a variant must reference an original case")
                if (
                    (case.group_id, case.split, case.left_source, case.right_source)
                    != (parent.group_id, parent.split, parent.left_source, parent.right_source)
                    or case.stream != "challenge"
                ):
                    raise ValueError(
                        "a variant must retain its parent group/split and be challenge"
                    )
                changed = 0
                for item, original in ((case.left, parent.left), (case.right, parent.right)):
                    if item != original:
                        changed += 1
                        if (
                            item.model_dump(exclude={"summary"})
                            != original.model_dump(exclude={"summary"})
                            or not item.summary.startswith(
                                (original.summary + " ", original.summary + "\n\n")
                            )
                            or not item.summary[len(original.summary):].strip()
                        ):
                            raise ValueError("a variant may only append to one summary")
                if changed != 1:
                    raise ValueError("a variant must change exactly one summary")
        if self.corpus_sha256 != self.corpus_digest():
            raise ValueError("corpus_sha256 does not match frozen sources and cases")
        return self


class EvaluationAnnotation(Model):
    case_id: Sha256
    input_sha256: Sha256
    reviewer_key: Slug
    role: Literal["primary", "independent"]
    origin: Literal["human", "model", "unverified"]
    verdict: SameStoryVerdict
    marked_at: Timestamp = Field(description="When this annotation was recorded, in UTC.")

    @model_validator(mode="after")
    def _utc_instant(self) -> Self:
        datetime.strptime(self.marked_at, "%Y-%m-%dT%H:%M:%SZ")
        return self


class EvaluationLabels(Contract):
    """Declared annotations, not proof that a reviewer is actually independent."""

    __schema_stem__: ClassVar[str] = "content-similarity-judge-evaluation-labels"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-05", change="Declare input-bound reviewer annotations and rubric.",
            why="Unresolved and model-origin marks must not become independent human truth.",
        ),
    )

    set_sha256: Sha256
    rubric: str = Field(min_length=1)
    rubric_sha256: Sha256
    annotations: tuple[EvaluationAnnotation, ...]

    @model_validator(mode="after")
    def _rubric_and_reviewer_identity(self) -> Self:
        if self.rubric_sha256 != derive_text_digest(self.rubric):
            raise ValueError("rubric_sha256 does not match rubric")
        keys = [(row.case_id, row.reviewer_key) for row in self.annotations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate reviewer annotations for a case")
        return self


class EvaluationReading(Model):
    verdict: SameStoryVerdict | None
    grammar_applied: bool = Field(strict=True)
    refusal_reason: ReadingRefusalReason | None
    prompt_tokens: Count
    completion_tokens: Count
    elapsed_seconds: Seconds
    first_token_margin: Rate | None
    first_token_window: str | None
    thinking_spans: Count
    request_json: tuple[str, ...] = Field(min_length=1)
    raw_response: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _completed_reading(self) -> Self:
        if self.grammar_applied != (self.verdict is not None):
            raise ValueError("only a grammar-valid reading carries a verdict")
        if (self.refusal_reason is None) != self.grammar_applied:
            raise ValueError("a refused reading must carry its closed reason")
        if self.thinking_spans not in (0, 1):
            raise ValueError("a production reading has zero or one thinking span")
        if len(self.request_json) != len(self.raw_response):
            raise ValueError("each request must retain its actual raw response")
        if len(self.request_json) != self.thinking_spans + 1:
            raise ValueError("retain each production span in request order")
        for request in self.request_json:
            TypeAdapter(dict[str, JsonValue]).validate_json(request)
        return self


class EvaluationCaseRun(Model):
    case_id: Sha256
    input_sha256: Sha256
    forward: EvaluationReading | None = None
    reverse: EvaluationReading | None = None


class EvaluationRun(Contract):
    """The real two-order transcript, including an honest unfinished capture."""

    __schema_stem__: ClassVar[str] = "content-similarity-judge-evaluation-run"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-05", change="Declare private two-order judge capture and provenance.",
            why="A transport failure is incomplete evidence, not a fabricated model refusal.",
        ),
    )

    set_sha256: Sha256
    split: EvaluationSplit
    model: ModelRef
    config_sha256: Sha256
    prompt_digest: Sha256
    grammar_digest: Sha256
    judge_policy_version: DateStamp
    envelope_sha256: Sha256
    git_sha: CommitSha
    started_at: Timestamp = Field(description="Capture start instant in UTC.")
    finished_at: Timestamp | None = Field(description="Capture end instant in UTC, if finished.")
    host: HostFingerprintRow
    state: Literal["not_run", "incomplete", "captured"]
    cases: tuple[EvaluationCaseRun, ...]

    @model_validator(mode="after")
    def _capture_state(self) -> Self:
        start = datetime.strptime(self.started_at, "%Y-%m-%dT%H:%M:%SZ")
        if self.finished_at is not None:
            finish = datetime.strptime(self.finished_at, "%Y-%m-%dT%H:%M:%SZ")
            if finish < start:
                raise ValueError("capture cannot finish before it starts")
        if len({case.case_id for case in self.cases}) != len(self.cases):
            raise ValueError("duplicate captured cases")
        complete = all(case.forward is not None and case.reverse is not None for case in self.cases)
        if self.state == "captured" and (not self.cases or not complete):
            raise ValueError("captured requires both readings of every selected case")
        if self.state == "captured" and self.finished_at is None:
            raise ValueError("captured requires its UTC finish instant")
        if self.state == "not_run" and any(
            case.forward is not None or case.reverse is not None for case in self.cases
        ):
            raise ValueError("not_run cannot contain model readings")
        return self


class EvaluationClassMetrics(Model):
    precision: Rate | None
    recall: Rate | None
    precision_lower: Rate | None
    precision_upper: Rate | None
    recall_lower: Rate | None
    recall_upper: Rate | None
    precision_interval_reason: IntervalReason | None
    recall_interval_reason: IntervalReason | None

    @model_validator(mode="after")
    def _intervals(self) -> Self:
        for metric in ("precision", "recall"):
            value = getattr(self, metric)
            lower, upper = getattr(self, metric + "_lower"), getattr(self, metric + "_upper")
            reason = getattr(self, metric + "_interval_reason")
            if (lower is None) != (upper is None):
                raise ValueError("interval bounds must be present together")
            if lower is not None and (lower > upper or value is None or reason is not None):
                raise ValueError("a measured interval needs an ordered pair and a metric")
            if lower is None and reason is None:
                raise ValueError("unavailable intervals require a fixed reason")
        return self


class EvaluationStreamReport(Model):
    stream: EvaluationStream
    case_count: Count
    group_count: Count
    qualified_label_count: Count
    gold_counts: dict[SameStoryVerdict, Count]
    prediction_counts: dict[EvaluationPrediction, Count]
    confusion: dict[SameStoryVerdict, dict[EvaluationPrediction, Count]]
    valid_agreement_count: Count
    unclear_count: Count
    refusal_count: Count
    disagreement_count: Count
    class_metrics: dict[SameStoryVerdict, EvaluationClassMetrics]
    margin_diagnostics: dict[EvaluationPrediction, Rate | None] | None

    @model_validator(mode="after")
    def _complete_reconciled_categories(self) -> Self:
        verdicts = set(SameStoryVerdict)
        predictions = verdicts | {"DISAGREE", "REFUSED"}
        if (
            set(self.gold_counts) != verdicts
            or set(self.class_metrics) != verdicts
            or set(self.confusion) != verdicts
            or set(self.prediction_counts) != predictions
            or any(set(row) != predictions for row in self.confusion.values())
            or (
                self.margin_diagnostics is not None
                and set(self.margin_diagnostics) != predictions
            )
        ):
            raise ValueError("reports require every gold and prediction category")
        if not (
            self.group_count <= self.case_count and self.qualified_label_count <= self.case_count
        ) or (self.group_count == 0) != (self.case_count == 0):
            raise ValueError("support cannot exceed the declared case population")
        if sum(self.gold_counts.values()) != self.qualified_label_count:
            raise ValueError("gold counts must account for qualified labels")
        if sum(self.prediction_counts.values()) > self.case_count:
            raise ValueError("predictions cannot exceed declared cases")
        known = sum(sum(row.values()) for row in self.confusion.values())
        if known < (
            self.qualified_label_count + sum(self.prediction_counts.values()) - self.case_count
        ):
            raise ValueError("confusion omits known label/prediction overlap")
        for gold, row in self.confusion.items():
            if sum(row.values()) > self.gold_counts[gold]:
                raise ValueError("confusion exceeds qualified gold support")
        for prediction, count in self.prediction_counts.items():
            if sum(row[prediction] for row in self.confusion.values()) > count:
                raise ValueError("confusion exceeds captured prediction support")
        if (
            self.valid_agreement_count
            != sum(self.prediction_counts[word.value] for word in SameStoryVerdict)
            or self.unclear_count != self.prediction_counts["UNCLEAR"]
            or self.refusal_count != self.prediction_counts["REFUSED"]
            or self.disagreement_count != self.prediction_counts["DISAGREE"]
        ):
            raise ValueError("outcome counts disagree with prediction categories")
        return self


class EvaluationReport(Contract):
    """Separate finite-set streams; blocked evidence never receives quality scores."""

    __schema_stem__: ClassVar[str] = "content-similarity-judge-evaluation-report"
    __changelog__: ClassVar[tuple[ChangelogEntry, ...]] = (
        ChangelogEntry(
            version="2026-11-05", change="Declare coverage-aware offline judge reports.",
            why="Missing labels and failed captures must remain visible as unknown metrics.",
        ),
    )

    set_sha256: Sha256
    labels_sha256: Sha256
    run_sha256: Sha256
    state: Literal["blocked", "measured"]
    blockers: tuple[EvaluationBlocker, ...]
    streams: tuple[EvaluationStreamReport, ...]

    @model_validator(mode="after")
    def _honest_measurement(self) -> Self:
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("duplicate report blockers")
        if (self.state == "blocked") != bool(self.blockers):
            raise ValueError("blocked requires blockers; measured forbids them")
        if {row.stream for row in self.streams} != {"representative", "challenge"}:
            raise ValueError("report both streams separately")
        if len(self.streams) != 2:
            raise ValueError("duplicate stream reports")
        if self.state == "measured" and not any(stream.case_count for stream in self.streams):
            raise ValueError("measured requires at least one selected case")
        for stream in self.streams:
            if self.state == "blocked":
                if any(
                    metric.precision is not None or metric.recall is not None
                    or metric.precision_lower is not None or metric.recall_lower is not None
                    for metric in stream.class_metrics.values()
                ) or stream.margin_diagnostics is not None:
                    raise ValueError("blocked reports cannot carry quality metrics")
            elif (
                stream.qualified_label_count != stream.case_count
                or sum(stream.prediction_counts.values()) != stream.case_count
                or any(
                    sum(stream.confusion[gold].values()) != count
                    for gold, count in stream.gold_counts.items()
                )
            ):
                raise ValueError("measured requires complete labels, captures and confusion")
            else:
                for verdict, metric in stream.class_metrics.items():
                    if "blocked" in (
                        metric.precision_interval_reason, metric.recall_interval_reason
                    ):
                        raise ValueError("measured metrics cannot carry blocked interval reasons")
                    correct = stream.confusion[verdict][verdict.value]
                    predicted = stream.prediction_counts[verdict.value]
                    gold = stream.gold_counts[verdict]
                    if (
                        metric.precision != (correct / predicted if predicted else None)
                        or metric.recall != (correct / gold if gold else None)
                    ):
                        raise ValueError("class metrics disagree with the complete confusion table")
        return self
