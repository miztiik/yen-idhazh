/** Which typed event records the stage observation made at this point in a run? */
import { createHash } from "node:crypto";
import { FeedIngestEventSchema } from "@idhazh/common-contracts";
import type { EventPayload, FeedIngestEvent, PolicyIdentity } from "@idhazh/common-contracts";
import type { RunContext } from "../resolve-run-context";

export function createStageLogger(context: RunContext, write: (event: FeedIngestEvent) => void) {
  const events: FeedIngestEvent[] = [];
  const started = performance.now();
  let stepStarted = started;
  return {
    events,
    startStep() { stepStarted = performance.now(); },
    emit(
      stage: FeedIngestEvent["stage"], payload: EventPayload, policy: PolicyIdentity,
      source_id: string | null = null, candidate_id: string | null = null,
    ) {
      const measured = performance.now();
      const sequence = events.length;
      const event = FeedIngestEventSchema.parse({
        event_id: createHash("sha256").update(`${context.run_id}\n${context.writer.attempt}\n${sequence}`).digest("hex"),
        correlation_id: context.correlation_id, run_id: context.run_id,
        attempt: context.writer.attempt, sequence, occurred_at: context.now,
        stage, audit_event_type: payload.kind, source_id, candidate_id,
        elapsed_ms: Math.round(measured - started), step_elapsed_ms: Math.round(measured - stepStarted),
        policy, payload,
      });
      events.push(event);
      write(event);
      return event;
    },
  };
}

export function writeJsonLine(record: unknown): void {
  console.error(JSON.stringify(record));
}
