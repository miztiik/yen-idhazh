/** Which validated API response and preparation evidence may a private summary caller save? */
import { z } from "zod";
import { createHash } from "node:crypto";
import { readCloudEvent } from "@idhazh/common-contracts/read-cloud-event";
import { readTraceContext } from "@idhazh/common-contracts/propagate-trace-context";
import type { CloudEvent } from "@idhazh/common-contracts/schemas/cloud-event";
import { SummarizeRequestSchema } from "../../../services/summary-generator/src/schemas/request-payload.schema.js";
import {
  SUMMARY_API_VERSION, SummaryResultSchema,
} from "../../../services/summary-generator/src/schemas/summary-result.schema.js";
import { SourceAuditSchema } from "./system-telemetry.schema.js";
import { SUMMARY_GENERATOR_TESTS_EVENT_SOURCE } from "../declare-event-source.js";

export const SUMMARY_WORKFLOW_VERSION = SUMMARY_API_VERSION;
export const SUMMARY_WORKFLOW_EVENT_TYPE = "SUMMARY_API_COMPLETED";
export const SUMMARY_WORKFLOW_CHANGELOG = [
  { version: SUMMARY_WORKFLOW_VERSION, change: "Capture the server-reported model and retain earlier summary captures." },
  { version: "2026-11-06", change: "Capture the pure summary response and caller-owned preparation evidence." },
] as const;
export const SummaryWorkflowDataSchema = z.object({
  version: z.enum([SUMMARY_WORKFLOW_VERSION, "2026-11-06"]),
  model_name: z.string().min(1),
  request: SummarizeRequestSchema,
  result: SummaryResultSchema,
  source_audit: SourceAuditSchema,
  input_sha256: z.string().regex(/^[a-f0-9]{64}$/),
  api_traceparent: z.string(),
  api_tracestate: z.string().optional(),
  duration_ms: z.number().finite().nonnegative(),
  classifications: z.literal("not_collected"),
  machine_readings: z.literal("not_collected"),
}).strict().superRefine((data, context) => {
  if (!readTraceContext({ traceparent: data.api_traceparent, tracestate: data.api_tracestate })) {
    context.addIssue({ code: "custom", message: "The API response carrier is invalid." });
  }
  const digest = (text: string) => createHash("sha256").update(text, "utf8").digest("hex");
  if (data.input_sha256 !== digest(data.request.input_text)) {
    context.addIssue({ code: "custom", message: "The captured input digest is unrelated to the request." });
  }
  const prompt = data.request.system_prompt;
  if (data.result.prompt_source !== (prompt === undefined ? "default" : "override")
    || (prompt !== undefined && data.result.prompt_sha256 !== digest(prompt))) {
    context.addIssue({ code: "custom", message: "The captured prompt identity is unrelated to the request." });
  }
});
export type SummaryWorkflowData = z.infer<typeof SummaryWorkflowDataSchema>;
export type SummaryWorkflowEvent = CloudEvent<SummaryWorkflowData>;

export function readSummaryWorkflowEvent(value: unknown): SummaryWorkflowEvent {
  const event = readCloudEvent(value, data => SummaryWorkflowDataSchema.parse(data));
  const caller = readTraceContext({ traceparent: event.traceparent, tracestate: event.tracestate });
  const api = readTraceContext({
    traceparent: event.data.api_traceparent, tracestate: event.data.api_tracestate,
  });
  if (event.type !== SUMMARY_WORKFLOW_EVENT_TYPE || event.source !== SUMMARY_GENERATOR_TESTS_EVENT_SOURCE
    || caller?.traceId !== api?.traceId || caller?.spanId === api?.spanId) {
    throw new Error("The summary workflow occurrence is unrelated to its API request.");
  }
  return event;
}
