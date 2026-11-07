/** How does one saved summary cross the prepared-text-only coverage boundary? */
import {
  createChildContext,
  readTraceContext,
  type OperationMetadata,
} from "../../packages/common-contracts/src/index.ts";
import type { SummaryStructuredOutput } from "../../.github/scripts/ai-pipeline.ts";
import {
  readEvaluationServerTelemetry,
  readQualityMetrics,
  type PipelineEvent,
} from "./read-pipeline-events.ts";

export type EvaluationRequest = {
  source_text: string;
  summary_text: string;
};

export function prepareEvaluationRequest(
  input: PipelineEvent<SummaryStructuredOutput>,
  phase: OperationMetadata,
): { context: OperationMetadata; request: EvaluationRequest } {
  const producer = readTraceContext({ traceparent: input.traceparent, tracestate: input.tracestate });
  if (!producer) throw new Error("INVALID_SAVED_PRODUCER_CONTEXT");
  const result = input.data.result;
  return {
    context: createChildContext(phase, {
      links: [{ traceId: producer.traceId, spanId: producer.spanId }],
    }),
    request: {
      source_text: result.source_audit.extractedText,
      summary_text: result.analytic_synthesis,
    },
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

// This hand copy is held against the native shared status policy by the coverage binding test.
export const COVERAGE_FAILURE_STATUS = {
  INVALID_JSON: 400,
  INVALID_REQUEST: 400,
  INPUT_TIMEOUT: 408,
  BODY_TOO_LARGE: 413,
  UNSUPPORTED_MEDIA: 415,
  ORIGIN_FORBIDDEN: 403,
  HOST_FORBIDDEN: 403,
  WINDOW_LIMIT_EXCEEDED: 400,
  QUEUE_FULL: 429,
  QUEUE_TIMEOUT: 503,
  SERVICE_DISABLED: 503,
  SERVICE_STOPPED: 503,
  WORKER_NOT_READY: 503,
  MODEL_LOAD_FAILED: 500,
  MODEL_IDENTITY_CHANGED: 500,
  MODEL_SCORING_FAILED: 500,
  INVALID_MODEL_OUTPUT: 500,
  WORKER_EXITED: 500,
  WORKER_PROTOCOL_FAILED: 500,
  WORKER_STOP_FAILED: 500,
  EVALUATION_TIMEOUT: 504,
  LOGGING_FAILED: 500,
  INTERNAL_ERROR: 500,
} as const;

export class CoverageApiFailure extends Error {
  constructor(
    public readonly code: keyof typeof COVERAGE_FAILURE_STATUS,
    public readonly httpStatus: number,
  ) {
    super("SOURCE_COVERAGE_FAILED");
    this.name = "CoverageApiFailure";
  }
}

export function readEvaluationResponse(value: unknown, httpStatus = 200) {
  if (isRecord(value) && value.error !== undefined) {
    const error = value.error;
    if (!isRecord(error) || Object.keys(error).length !== 3 || error.type !== "api_error"
      || typeof error.code !== "string" || typeof error.message !== "string"
      || !Object.hasOwn(COVERAGE_FAILURE_STATUS, error.code)) {
      throw new Error("INVALID_EVALUATION_RESPONSE");
    }
    const code = error.code as keyof typeof COVERAGE_FAILURE_STATUS;
    if (COVERAGE_FAILURE_STATUS[code] !== httpStatus) throw new Error("INVALID_EVALUATION_RESPONSE");
    throw new CoverageApiFailure(code, httpStatus);
  }
  if (httpStatus !== 200) throw new Error("INVALID_EVALUATION_RESPONSE");
  if (!isRecord(value) || value.status !== "success") throw new Error("INVALID_EVALUATION_RESPONSE");
  const metrics = readQualityMetrics(value.metrics);
  if (value.event === undefined) return { metrics };
  if (!isRecord(value.event) || !isRecord(value.event.payload)) throw new Error("INVALID_EVALUATION_EVENT");
  const serverTelemetry = value.event.payload.serverTelemetry;
  if (serverTelemetry === undefined) return { metrics };
  return { metrics, serverTelemetry: readEvaluationServerTelemetry(serverTelemetry) };
}
