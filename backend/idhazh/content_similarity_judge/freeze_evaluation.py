"""How are explicitly selected published comparisons frozen without fetching or discovering data?"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path

from idhazh import config, sanitize
from idhazh.atomic_write import write_atomic
from idhazh.content_similarity_judge import settings as judge_settings
from idhazh.contracts.base import canonical_json, derive_text_digest
from idhazh.contracts.content_similarity_judge_evaluation import (
    EvaluationCase,
    EvaluationSelection,
    EvaluationSelectionPair,
    EvaluationSet,
    EvaluationSource,
    EvaluationSplit,
    case_sha256,
    corpus_sha256,
    document_sha256,
)
from idhazh.contracts.digest_day import DigestDay, DigestItem
from idhazh.contracts.knobs.content_similarity_judge import ContentSimilarityEvaluationConfig
from idhazh.similarity import prompt


def input_sha256(left: DigestItem, right: DigestItem) -> str:
    """Hash both ordered sanitized user turns, exactly as the production judge renders them."""
    return derive_text_digest(canonical_json([
        prompt.user_turn(left, right), prompt.user_turn(right, left),
    ]))


def sanitizer_sha256() -> str:
    """The named sanitizer implementation, not a claim about a library version."""
    return hashlib.sha256(Path(sanitize.__file__).read_bytes()).hexdigest()


def named_source(root: Path, relative: str) -> Path:
    """Resolve a validated operator-named source without following an escaping symlink."""
    base = root.resolve()
    path = (base / relative).resolve()
    if not path.is_relative_to(base):
        raise ValueError("evaluation source escapes its explicit root")
    return path


def private_output(root: Path, filename: str) -> Path:
    """Evaluation output is private scratch, never config, production state or published data."""
    base = root.resolve()
    repo = config.REPO_ROOT.resolve()
    if base.is_relative_to(repo) and not base.is_relative_to(repo / "backend" / "var"):
        raise ValueError("evaluation output inside the repository requires backend/var")
    path = (base / filename).resolve()
    if not path.is_relative_to(base):
        raise ValueError("evaluation output escapes its explicit root")
    return path


def selected_case_count(selection: EvaluationSelection) -> int:
    """Count each explicit parent once and each requested variant once."""
    parents = {
        (pair.left_source, pair.left_item_id, pair.right_source, pair.right_item_id)
        for pair in selection.pairs
    }
    return len(parents) + sum(pair.mutation is not None for pair in selection.pairs)


def freeze(
    selection: EvaluationSelection,
    snapshots: Mapping[str, bytes],
    *,
    tuning: ContentSimilarityEvaluationConfig,
) -> EvaluationSet:
    """Freeze named native days; variants add a challenge case without replacing the original."""
    requested = selected_case_count(selection)
    if requested > tuning.max_cases:
        raise ValueError("evaluation selection exceeds max_cases, including variants")
    if set(snapshots) != set(selection.sources):
        raise ValueError("snapshots must match exactly the named sources")
    sources: list[EvaluationSource] = []
    items: dict[str, dict[str, DigestItem]] = {}
    for path in selection.sources:
        raw = snapshots[path]
        day = DigestDay.model_validate_json(raw)
        sources.append(EvaluationSource(
            path=path, date=day.date, sha256=hashlib.sha256(raw).hexdigest(),
        ))
        items[path] = {item.item_id: item for item in day.items}
        if len(items[path]) != len(day.items):
            raise ValueError("a source day contains duplicate item identities")
    cases: dict[str, EvaluationCase] = {}
    original_selections: set[str] = set()
    for pair in selection.pairs:
        try:
            left = items[pair.left_source][pair.left_item_id]
            right = items[pair.right_source][pair.right_item_id]
        except KeyError:
            raise ValueError("a selected item is absent from its named source") from None
        original = _case(pair, left, right)
        # A manifest may name the parent again to declare another mutation, not duplicate it.
        pair_key = canonical_json(pair.model_dump(mode="json"))
        if pair_key in original_selections:
            raise ValueError("duplicate selected pair or variant")
        original_selections.add(pair_key)
        prior = cases.setdefault(original.case_id, original)
        if prior != original:
            raise ValueError("a selected case has conflicting group/split/stream declarations")
        if pair.mutation is not None:
            changed = left if pair.mutation.side == "left" else right
            mutated = DigestItem.model_validate(changed.model_dump() | {
                "summary": changed.summary + " " + pair.mutation.append_summary,
            })
            variant = _case(
                pair,
                mutated if pair.mutation.side == "left" else left,
                mutated if pair.mutation.side == "right" else right,
                parent=original.case_id,
            )
            if variant.input_sha256 == original.input_sha256:
                raise ValueError("a planted instruction must change the sanitized model input")
            if variant.case_id in cases:
                raise ValueError("duplicate planted-instruction case")
            cases[variant.case_id] = variant
    frozen_sources = tuple(sources)
    frozen_cases = tuple(sorted(cases.values(), key=lambda case: case.case_id))
    return EvaluationSet(
        version=EvaluationSet.schema_version(),
        sources=frozen_sources, cases=frozen_cases,
        corpus_sha256=corpus_sha256(frozen_sources, frozen_cases),
        sanitizer_sha256=sanitizer_sha256(),
    )


def _case(
    pair: EvaluationSelectionPair,
    left: DigestItem,
    right: DigestItem,
    *,
    parent: str | None = None,
) -> EvaluationCase:
    digest = input_sha256(left, right)
    kind = "none" if parent is None else "planted_instruction"
    return EvaluationCase.model_validate({
        "case_id": case_sha256(left, right, digest, kind, parent),
        "group_id": pair.group_id,
        "split": pair.split,
        "stream": pair.stream if parent is None else "challenge",
        "left": left,
        "right": right,
        "left_source": pair.left_source,
        "right_source": pair.right_source,
        "input_sha256": digest,
        "parent_case_id": parent,
        "mutation_kind": kind,
    })


def validate_inputs(evaluation: EvaluationSet, *, max_cases: int) -> None:
    """Recompute all identities at a consuming boundary, before any model call."""
    EvaluationSet.model_validate(evaluation.model_dump())
    if not evaluation.cases or len(evaluation.cases) > max_cases:
        raise ValueError("evaluation set must contain one through max_cases cases")
    if evaluation.sanitizer_sha256 != sanitizer_sha256():
        raise ValueError("evaluation sanitizer provenance differs from this implementation")
    for case in evaluation.cases:
        if input_sha256(case.left, case.right) != case.input_sha256:
            raise ValueError("evaluation input_sha256 differs from the sanitized summaries")


def blinded_view(evaluation: EvaluationSet, *, split: EvaluationSplit) -> str:
    """Opaque identities and exact model-visible turns, with no case-selection metadata."""
    return "\n\n".join(
        f"Case: {case.case_id}\nInput: {case.input_sha256}\n\n"
        + prompt.user_turn(case.left, case.right)
        for case in evaluation.cases if case.split == split
    ) + "\n"


def freeze_files(
    *, selection_path: Path, source_root: Path, output_root: Path,
    split: EvaluationSplit, config_dir: Path,
) -> tuple[Path, Path]:
    """Read exactly the declared native snapshots and write private content-addressed output."""
    selection = EvaluationSelection.model_validate_json(selection_path.read_bytes())
    tuning = judge_settings.load_evaluation(config_dir)
    if selected_case_count(selection) > tuning.max_cases:
        raise ValueError("evaluation selection exceeds max_cases, including variants")
    evaluation = freeze(
        selection,
        {name: named_source(source_root, name).read_bytes() for name in selection.sources},
        tuning=tuning,
    )
    if not any(case.split == split for case in evaluation.cases):
        raise ValueError("the blinded export split has no cases")
    identity = document_sha256(evaluation)
    output = private_output(output_root, f"set-{identity}.json")
    blind = private_output(output_root, f"annotation-{identity}-{split}.txt")
    write_atomic(output, evaluation.to_json())
    write_atomic(blind, blinded_view(evaluation, split=split))
    return output, blind
