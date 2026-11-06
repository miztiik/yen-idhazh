"""Prove UUID compatibility and independence using named native vectors."""

import shutil
import subprocess
from typing import TypedDict
from uuid import NAMESPACE_DNS, UUID, uuid5

import pytest
from pydantic import TypeAdapter, ValidationError
from summary_evaluator_cases.contract_examples import (
    CORRELATION_ID,
    EXECUTION_ID,
    REPOSITORY,
    REQUEST_ID,
)

from summary_evaluator.hhem.contracts.evaluate_request import EvaluateRequest
from summary_evaluator.hhem.resolve_ids import (
    EVENT_NAMESPACE,
    create_event_id,
    create_event_seed,
    resolve_ids,
)
from summary_evaluator.shared.create_execution_id import create_execution_id


class UuidVector(TypedDict):
    name: str
    namespace: str
    execution_id: str
    sequence: int
    request_id: str
    correlation_id: str
    seed: str
    expected_uuid: str


class BunUuidResult(TypedDict):
    name: str
    actual_uuid: str


def read_vectors() -> list[UuidVector]:
    path = REPOSITORY / "tests" / "fixtures" / "hhem-evaluator" / "event-id-vectors.json"
    return TypeAdapter(list[UuidVector]).validate_json(path.read_bytes(), strict=True)


def test_python_uuid5_matches_named_vectors_and_exact_seeds() -> None:
    vectors = read_vectors()
    assert EVENT_NAMESPACE == NAMESPACE_DNS
    assert len({vector["name"] for vector in vectors}) == len(vectors)
    for vector in vectors:
        assert vector["namespace"] == str(EVENT_NAMESPACE)
        assert create_event_seed(vector["execution_id"], vector["sequence"]) == vector["seed"]
        assert not vector["seed"].endswith("\n")
        expected = vector["expected_uuid"]
        assert str(uuid5(UUID(vector["namespace"]), vector["seed"])) == expected
        assert create_event_id(vector["execution_id"], vector["sequence"]) == expected
    first, _, repeated, *_ = vectors
    assert first["request_id"] == repeated["request_id"]
    assert first["correlation_id"] == repeated["correlation_id"]
    assert first["execution_id"] != repeated["execution_id"]
    assert first["expected_uuid"] != repeated["expected_uuid"]


def test_existing_typescript_uuid5_matches_the_same_vectors() -> None:
    bun = shutil.which("bun")
    if bun is None:
        pytest.fail(
            "Bun is required for UUID compatibility. Install the repository's Bun runtime, "
            "then run bun install --frozen-lockfile --cwd packages/ledger-file-writer."
        )
    writer_dependency = (
        REPOSITORY / "packages" / "ledger-file-writer" / "node_modules" / "zod" / "package.json"
    )
    if not writer_dependency.is_file():
        pytest.fail(
            "The writer's locked dependencies are required. Run "
            "bun install --frozen-lockfile --cwd packages/common-contracts and "
            "bun install --frozen-lockfile --cwd packages/ledger-file-writer."
        )
    fixture = REPOSITORY / "tests" / "fixtures" / "hhem-evaluator" / "event-id-vectors.json"
    bridge = REPOSITORY / "services" / "summary_evaluator" / "tests" / "check_uuid_vectors.ts"
    completed = subprocess.run(
        [bun, "run", "--no-install", str(bridge), str(fixture)],
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert completed.returncode == 0, (
        "The actual TypeScript UUID reader failed. Prepare its locked Bun dependencies. "
        + completed.stderr
    )
    actual = TypeAdapter(list[BunUuidResult]).validate_json(completed.stdout, strict=True)
    assert actual == [
        {"name": vector["name"], "actual_uuid": vector["expected_uuid"]}
        for vector in read_vectors()
    ]


def test_caller_spelling_survives_without_determining_execution_identity() -> None:
    request = EvaluateRequest(
        source_text="Source.",
        summary_text="Summary.",
        request_id=REQUEST_ID.upper(),
        correlation_id=CORRELATION_ID.upper(),
    )
    first_execution = create_execution_id()
    second_execution = create_execution_id()
    assert first_execution != second_execution
    for execution in (first_execution, second_execution):
        assert UUID(execution).version == 4
        assert execution == execution.lower()
        identity = resolve_ids(request, execution)
        assert identity.execution_id == execution
        assert identity.request_id == REQUEST_ID.upper()
        assert identity.correlation_id == CORRELATION_ID.upper()
    assert create_event_id(first_execution, 1) != create_event_id(second_execution, 1)


def test_only_omitted_caller_ids_are_generated() -> None:
    request = EvaluateRequest(source_text="Source.", summary_text="Summary.")
    identity = resolve_ids(request, EXECUTION_ID)
    ids = (identity.execution_id, identity.request_id, identity.correlation_id)
    assert len(set(ids)) == 3
    assert all(UUID(value).version == 4 and value == value.lower() for value in ids)


@pytest.mark.parametrize(
    "value",
    ["", "not-a-uuid", REQUEST_ID.replace("-", ""), REQUEST_ID.replace("-4", "-5", 1), None],
)
def test_invalid_supplied_ids_fail_without_replacement(value: object) -> None:
    with pytest.raises(ValidationError):
        EvaluateRequest.model_validate(
            {"source_text": "Source.", "summary_text": "Summary.", "request_id": value}
        )


@pytest.mark.parametrize("sequence", [0, -1, True])
def test_invalid_event_sequence_fails(sequence: int) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        create_event_id(EXECUTION_ID, sequence)
