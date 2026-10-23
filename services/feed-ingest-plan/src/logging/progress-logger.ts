/** Report live work without replacing the persisted audit event identity. */
import { createUuidV5 } from "@idhazh/ledger-file-writer";
import { EVENT_NAMESPACE, writeJsonLine } from "./structured-logger";
import type { HarvestDiagnostics } from "@idhazh/common-contracts";
import type { FetchAttempt } from "../api/operation-contracts";
import type { z } from "zod";
import type { PlannerObservationSchema } from "../api/operation-contracts";

export type ProgressEventType =
  | "PIPELINE_STARTED" | "HISTORY_READ_STARTED" | "HISTORY_READ_COMPLETED"
  | "FEED_DISCOVERY_STARTED" | "FEED_FETCH_STARTED" | "FEED_FETCH_COMPLETED"
  | "ARTICLE_HARVEST_STARTED" | "ARTICLE_HARVEST_COMPLETED"
  | "ARTICLE_EXTRACTION_WARNING"
  | "DOCUMENT_FETCHED" | "DOCUMENT_PARSED" | "FETCH_ATTEMPT_COMPLETED"
  | "FEED_REJECTED" | "ARTICLE_REJECTED"
  | "STAGE_COMPLETED" | "PLANNING_STAGES_COMPLETED"
  | "AUDIT_RECORDING_STARTED" | "AUDIT_RECORDING_COMPLETED"
  | "PUBLICATION_OBSERVATION_STARTED" | "PUBLICATION_OBSERVATION_COMPLETED"
  | "HTTP_LISTENER_STARTED" | "HTTP_RESPONSE_RECEIVED" | "HTTP_LISTENER_STOPPED";
export type ProgressDetails = {
  source_id?: string; candidate_id?: string; stage?: string;
  input_count?: number; output_count?: number; rejection_count?: number;
  fetch_status?: string; parse_status?: string; drop_reason?: string | null;
  http_status?: number;
  diagnostics?: HarvestDiagnostics | null;
  duration_ms?: number;
  extraction_outcome?: "success" | "empty" | "failed" | "not-attempted";
  document_observation?: z.infer<typeof PlannerObservationSchema>;
  fetch_attempt?: FetchAttempt;
};
export type ProgressRecord = ProgressDetails & {
  timestamp: string; level: "INFO" | "WARN"; message: string; eventId: string;
  eventType: ProgressEventType; correlationId: string; durationMs: number | null; elapsedMs: number;
};

export function createProgressLogger(
  correlationId: string, write: (record: ProgressRecord) => void = writeJsonLine,
) {
  const started = performance.now();
  let sequence = 0;
  return (eventType: ProgressEventType, details: ProgressDetails = {}) => {
    const measured = performance.now();
    const { duration_ms, ...evidence } = details;
    const record: ProgressRecord = {
      timestamp: new Date().toISOString(), level: eventType === "ARTICLE_EXTRACTION_WARNING" ? "WARN" : "INFO",
      message: `Pipeline Event: ${eventType}`,
      eventId: `evt_${createUuidV5(EVENT_NAMESPACE, `progress\n${correlationId}\n${eventType}\n${sequence++}`)}`, eventType, correlationId,
      durationMs: duration_ms ?? null, elapsedMs: Math.round(measured - started), ...evidence,
    };
    write(record);
  };
}
