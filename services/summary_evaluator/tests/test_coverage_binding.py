"""Do genuine coverage results and native safe policies cross the real TypeScript reader?"""

import json
import subprocess
from typing import get_args

import pytest
from summary_evaluator_cases.contract_examples import REPOSITORY
from summary_evaluator_cases.coverage_recordings import read_coverage_recordings

from summary_evaluator.serve_http.api_settings import (
    load_api_configuration,
    resolve_scorer_api_settings,
)
from summary_evaluator.serve_http.contracts.api_deployment_settings import ApiDeploymentSettings
from summary_evaluator.serve_http.contracts.api_settings import ApiComponent, ApiSettings
from summary_evaluator.serve_http.refuse_request import refuse_request
from summary_evaluator.shared.contracts.error_policy import ERROR_POLICIES, ErrorCode
from summary_evaluator.shared.contracts.service_settings import ListenerSettings, LoggingSettings
from summary_evaluator.source_coverage.contracts.evaluation_result import (
    CoverageMetrics,
    CoverageResult,
    SentenceEvidence,
    UncoveredSection,
)

BIND_READER = """
import { readEvaluationResponse, CoverageApiFailure, COVERAGE_FAILURE_STATUS }
  from './tools/ai-pipeline-experiment/prepare-evaluation-request.ts';
import { CoverageListenerSchema, CoverageApiSettingsSchema, CoverageDeploymentSettingsSchema,
  CoverageApiComponentSchema, CoverageLoggingSchema, resolveCoverageApiSettings }
  from './tools/ai-pipeline-experiment/read-coverage-settings.ts';
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
  hosts: CoverageListenerSchema.shape.host.options,
  api: Object.keys(CoverageApiSettingsSchema.shape),
  deployment: Object.keys(CoverageDeploymentSettingsSchema.shape),
  listeners: Object.keys(CoverageDeploymentSettingsSchema.shape.listeners.shape),
  logging: Object.keys(CoverageLoggingSchema.shape),
  levels: CoverageLoggingSchema.shape.level.options,
  components: CoverageApiComponentSchema.options,
  version: CoverageApiSettingsSchema.shape.version.parse('2026-11-07'),
  apiRequired: Object.entries(CoverageApiSettingsSchema.shape)
    .filter(([, schema]) => !schema.isOptional()).map(([key]) => key),
  deploymentRequired: Object.entries(CoverageDeploymentSettingsSchema.shape)
    .filter(([, schema]) => !schema.isOptional()).map(([key]) => key),
  selected: input.api ? resolveCoverageApiSettings(input.api) : null }));
"""


def read_with_native_typescript(
    body: object, status: int = 200, *, api: object = None
) -> dict[str, object]:
    result = subprocess.run(
        ["bun", "--eval", BIND_READER],
        input=json.dumps({"body": body, "status": status, "api": api}),
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
    for api_model, key in ((ApiSettings, "api"), (ApiDeploymentSettings, "deployment")):
        fields_bound, required_bound = bound[key], bound[f"{key}Required"]
        assert isinstance(fields_bound, list) and isinstance(required_bound, list)
        assert set(fields_bound) == set(api_model.model_fields)
        assert set(required_bound) == set(api_model.model_json_schema()["required"])
    listeners, components, logging = bound["listeners"], bound["components"], bound["logging"]
    assert (
        isinstance(listeners, list) and isinstance(components, list) and isinstance(logging, list)
    )
    assert set(listeners) == set(components) == set(get_args(ApiComponent))
    assert set(logging) == set(LoggingSettings.model_fields)
    assert bound["levels"] == LoggingSettings.model_json_schema()["properties"]["level"]["enum"]
    assert bound["version"] == ApiSettings.model_json_schema()["properties"]["version"]["const"]
    assert bound["statuses"] == {
        code: policy.http_status
        for code, policy in ERROR_POLICIES.items()
        if policy.http_status is not None
    }


@pytest.mark.parametrize("legacy", [False, True])
def test_coverage_settings_resolve_identically_in_both_native_readers(legacy: bool) -> None:
    configuration = load_api_configuration(REPOSITORY / "config" / "summary-evals" / "api.json")
    if legacy:
        configuration = resolve_scorer_api_settings(configuration, "hhem")
    expected = resolve_scorer_api_settings(configuration, "coverage")
    _, recording = read_coverage_recordings()
    response = {"status": "success", "metrics": recording.cases[0].expected_metrics}
    bound = read_with_native_typescript(response, api=configuration.model_dump(mode="json"))
    assert bound["selected"] == expected.model_dump(mode="json")


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
