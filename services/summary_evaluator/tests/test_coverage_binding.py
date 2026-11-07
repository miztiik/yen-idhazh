"""Do genuine coverage results and native safe policies cross the real TypeScript reader?"""

import json
import subprocess

import pytest
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.coverage_recordings import read_coverage_recordings

from summary_evaluator.serve_http.refuse_request import refuse_request
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode
from summary_evaluator.shared.contracts.service_settings import ListenerSettings
from summary_evaluator.source_coverage.contracts.evaluation_result import (
    CoverageMetrics,
    CoverageResult,
    SentenceEvidence,
    UncoveredSection,
)

BIND_READER = """
import { readEvaluationResponse, CoverageApiFailure, COVERAGE_FAILURE_STATUS }
  from './.github/scripts/prepare-evaluation-request.ts';
import { CoverageListenerSchema } from './.github/scripts/read-coverage-settings.ts';
import ts from './packages/common-contracts/node_modules/typescript/lib/typescript.js';
import { readFileSync } from 'node:fs';
const input = await Bun.stdin.json();
const file = ts.createSourceFile('ai-pipeline.ts',
  readFileSync('.github/scripts/ai-pipeline.ts', 'utf8'), ts.ScriptTarget.Latest, true);
const fields = {};
for (const statement of file.statements) {
  if (ts.isInterfaceDeclaration(statement)) {
    fields[statement.name.text] = statement.members.filter(ts.isPropertySignature)
      .map(member => ({ name: member.name.getText(file), optional: !!member.questionToken }));
  }
}
let result;
try { result = { metrics: readEvaluationResponse(input.body, input.status).metrics }; }
catch (error) {
  if (!(error instanceof CoverageApiFailure)) throw error;
  result = { error: { code: error.code, status: error.httpStatus } };
}
console.log(JSON.stringify({ result, fields, statuses: COVERAGE_FAILURE_STATUS,
  listener: Object.keys(CoverageListenerSchema.shape),
  hosts: CoverageListenerSchema.shape.host.options }));
"""


def read_with_native_typescript(body: object, status: int = 200) -> dict[str, object]:
    result = subprocess.run(
        ["bun", "--eval", BIND_READER],
        input=json.dumps({"body": body, "status": status}),
        cwd=REPOSITORY,
        capture_output=True,
        text=True,
        timeout=30,
        check=True,
    )
    value: dict[str, object] = json.loads(result.stdout)
    return value


def test_genuine_metrics_cross_the_actual_reader_with_bound_fields_and_vocabularies() -> None:
    _, recording = read_coverage_recordings()
    response = CoverageResult.model_validate_json(
        json.dumps({"status": "success", "metrics": recording.cases[1].expected_metrics})
    ).model_dump(mode="json")
    bound = read_with_native_typescript(response)
    assert bound["result"] == {"metrics": response["metrics"]}
    fields = bound["fields"]
    assert isinstance(fields, dict)
    for model, name in (
        (CoverageMetrics, "QualityEvaluationMetrics"),
        (SentenceEvidence, "SentenceGroundingDetail"),
        (UncoveredSection, "UncoveredSectionDetail"),
    ):
        copied = fields[name]
        assert {field["name"] for field in copied} == set(model.model_fields)
        assert {field["name"] for field in copied if not field["optional"]} == set(
            model.model_json_schema().get("required", [])
        )
    listener = bound["listener"]
    assert isinstance(listener, list)
    assert set(listener) == set(ListenerSettings.model_fields)
    assert bound["hosts"] == ListenerSettings.model_json_schema()["properties"]["host"]["enum"]
    assert bound["statuses"] == {
        code: policy.http_status
        for code, policy in ERROR_POLICIES.items()
        if policy.http_status is not None
    }


@pytest.mark.parametrize(
    "code",
    [
        "QUEUE_FULL", "QUEUE_TIMEOUT", "WORKER_NOT_READY", "EVALUATION_TIMEOUT",
        "INVALID_MODEL_OUTPUT", "WORKER_EXITED",
    ],
)
def test_actual_safe_renderer_is_a_failure_in_the_real_caller(code: ErrorCode) -> None:
    policy = ERROR_POLICIES[code]
    assert policy.http_status is not None
    response = refuse_request(code, policy.message, policy.http_status)
    received = read_with_native_typescript(json.loads(bytes(response.body)), response.status_code)
    assert received["result"] == {"error": {"code": code, "status": policy.http_status}}
