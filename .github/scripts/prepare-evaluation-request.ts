/** How does one saved summary cross the unchanged foreign evaluator boundary? */
import { randomUUID } from "node:crypto";
import {
  createChildContext,
  readTraceContext,
  type OperationMetadata,
} from "../../packages/common-contracts/src/index.ts";
import type { RunnerMetadata, SummaryStructuredOutput } from "./ai-pipeline.ts";
import { readQualityMetrics, type PipelineEvent } from "./read-pipeline-events.ts";

type EvaluationRequest = {
  correlationId: string;
  runnerName: string;
  shardId: string;
  sourceIdentifier: string;
  sourceTitle: string;
  sourceText: string;
  summaryText: string;
};

export function prepareEvaluationRequest(
  input: PipelineEvent<SummaryStructuredOutput>,
  phase: OperationMetadata,
  runner: Pick<RunnerMetadata, "runnerName" | "shardId">,
): { context: OperationMetadata; request: EvaluationRequest } {
  const producer = readTraceContext({ traceparent: input.traceparent, tracestate: input.tracestate });
  if (!producer) throw new Error("INVALID_SAVED_PRODUCER_CONTEXT");
  const result = input.data.result;
  return {
    context: createChildContext(phase, {
      links: [{ traceId: producer.traceId, spanId: producer.spanId }],
    }),
    request: {
      // The Python request retains its separate UUID, not a native trace identifier.
      correlationId: randomUUID(),
      runnerName: runner.runnerName,
      shardId: runner.shardId,
      sourceIdentifier: result.source_audit.sourceIdentifier,
      sourceTitle: result.headline,
      sourceText: result.source_audit.extractedText,
      summaryText: result.analytic_synthesis,
    },
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

export function readEvaluationResponse(value: unknown) {
  if (!isRecord(value) || value.status !== "success") throw new Error("INVALID_EVALUATION_RESPONSE");
  const metrics = readQualityMetrics(value.metrics);
  if (value.event === undefined) return { metrics };
  if (!isRecord(value.event) || !isRecord(value.event.payload)) throw new Error("INVALID_EVALUATION_EVENT");
  const serverTelemetry = value.event.payload.serverTelemetry;
  if (serverTelemetry === undefined) return { metrics };
  if (!isRecord(serverTelemetry) || ![
    "duration_ms", "cpu_percent", "server_vm_rss_mb", "server_vm_swap_mb",
  ].every(field => typeof serverTelemetry[field] === "number" && Number.isFinite(serverTelemetry[field]))) {
    throw new Error("INVALID_EVALUATION_SERVER_TELEMETRY");
  }
  return { metrics, serverTelemetry };
}
