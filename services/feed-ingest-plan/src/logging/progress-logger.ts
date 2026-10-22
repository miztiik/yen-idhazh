/** Report live work without replacing the persisted audit event identity. */
import { createUuidV5 } from "@idhazh/ledger-file-writer";
import { EVENT_NAMESPACE, writeJsonLine } from "./structured-logger";

export type ProgressEventType =
  | "PIPELINE_STARTED" | "HISTORY_READ_STARTED" | "HISTORY_READ_COMPLETED"
  | "FEED_DISCOVERY_STARTED" | "FEED_FETCH_STARTED" | "FEED_FETCH_COMPLETED"
  | "ARTICLE_EXTRACTION_STARTED" | "ARTICLE_EXTRACTION_COMPLETED"
  | "FEED_REJECTED" | "ARTICLE_REJECTED"
  | "STAGE_COMPLETED" | "PLANNING_STAGES_COMPLETED"
  | "AUDIT_RECORDING_STARTED" | "AUDIT_RECORDING_COMPLETED"
  | "PUBLICATION_OBSERVATION_STARTED" | "PUBLICATION_OBSERVATION_COMPLETED";
export type ProgressDetails = {
  source_id?: string; candidate_id?: string; stage?: string;
  input_count?: number; output_count?: number; rejection_count?: number;
  fetch_status?: string; parse_status?: string; drop_reason?: string | null;
};
export type ProgressRecord = ProgressDetails & {
  timestamp: string; level: "INFO"; message: string; eventId: string;
  eventType: ProgressEventType; correlationId: string; durationMs: number; elapsedMs: number;
};

export function createProgressLogger(
  correlationId: string, write: (record: ProgressRecord) => void = writeJsonLine,
) {
  const started = performance.now();
  let previous = started;
  let sequence = 0;
  return (eventType: ProgressEventType, details: ProgressDetails = {}) => {
    const measured = performance.now();
    const record: ProgressRecord = {
      timestamp: new Date().toISOString(), level: "INFO", message: `Pipeline Event: ${eventType}`,
      eventId: `evt_${createUuidV5(EVENT_NAMESPACE, `progress\n${correlationId}\n${eventType}\n${sequence++}`)}`, eventType, correlationId,
      durationMs: Math.round(measured - previous), elapsedMs: Math.round(measured - started), ...details,
    };
    previous = measured;
    write(record);
  };
}
