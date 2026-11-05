/** Which safe native event identifies a failed request at the hosting boundary? */
import { z } from "zod";
import { CloudEventSchema, createCloudEvent, readCloudEvent } from "@idhazh/common-contracts";
import type { OperationMetadata } from "@idhazh/common-contracts";
import { PIPELINE_API_EVENT_SOURCE } from "./declare-event-source";

export const REQUEST_FAILURE_EVENT_VERSION = "2026-11-05";
const diagnosticContract = {
  version: REQUEST_FAILURE_EVENT_VERSION,
  readCompatibility: "current_only; diagnostic readers and writers change together",
  changelog: [
    { version: REQUEST_FAILURE_EVENT_VERSION, change: "Declare safe native API request failures." },
  ],
};
const RequestFailureDataSchema = z.strictObject({
  code: z.literal("API_OPERATION_FAILED"),
}).meta(diagnosticContract);
export const RequestFailureDiagnosticSchema = RequestFailureDataSchema.extend({
  event: z.literal("typescript_api_request_failed"),
}).meta(diagnosticContract);
export const RequestFailureEventSchema = CloudEventSchema.safeExtend({
  source: z.literal(PIPELINE_API_EVENT_SOURCE),
  type: z.literal("typescript_api_request_failed"), data: RequestFailureDataSchema,
}).meta(diagnosticContract);
export type RequestFailureEvent = z.infer<typeof RequestFailureEventSchema>;

export function createRequestFailureEvent(input: { context: OperationMetadata }): RequestFailureEvent {
  return RequestFailureEventSchema.parse(createCloudEvent({
    source: PIPELINE_API_EVENT_SOURCE, type: "typescript_api_request_failed", context: input.context,
    data: { code: "API_OPERATION_FAILED" }, parseData: value => RequestFailureDataSchema.parse(value),
  }));
}

export function readRequestFailureEvent(raw: unknown): RequestFailureEvent {
  return RequestFailureEventSchema.parse(readCloudEvent(raw, value => value));
}
