/** Write only the declared sparse progress payload, never a work batch or article body. */
import { FeedIngestEventSchema } from "@idhazh/common-contracts";
import type { FeedIngestEvent } from "@idhazh/common-contracts";
import type { RunContext } from "../resolve-run-context";
// RFC 4122 DNS namespace identifies deterministic local work events.
export const EVENT_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";

export function writeJsonLine(record: unknown): void { console.error(JSON.stringify(record)); }
export function writeAuditEvent(event: FeedIngestEvent): void {
  writeJsonLine(FeedIngestEventSchema.parse(event));
}
export function createStageLogger(context: RunContext, write = writeAuditEvent) {
  return (operation: FeedIngestEvent["operation"], phase: FeedIngestEvent["phase"],
    details: Partial<Pick<FeedIngestEvent, "source_id" | "input_count" | "output_count" | "duration_ms" | "failure_code">> = {}) => {
    write(FeedIngestEventSchema.parse({
      run_id: context.run_id, correlation_id: context.correlation_id, occurred_at: new Date().toISOString(),
      operation, phase, source_id: null, input_count: null, output_count: null, duration_ms: null,
      failure_code: null, ...details,
    }));
  };
}
