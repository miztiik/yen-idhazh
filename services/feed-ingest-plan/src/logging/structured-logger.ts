/** Which typed event records the stage observation made at this point in a run? */
import { createUuidV5 } from "@idhazh/ledger-file-writer";
import {
  FeedCurationPolicySchema, FeedIngestEventSchema, FeedScreeningPolicySchema, PolicyIdentitySchema,
} from "@idhazh/common-contracts";
import type { EventPayload, FeedIngestEvent, PolicyIdentity } from "@idhazh/common-contracts";
import type { RunContext } from "../resolve-run-context";
import type { HarvestInputs } from "../harvest-feeds/load-harvest-inputs";

// RFC 4122 DNS namespace, also used by the existing pipeline event logger.
export const EVENT_NAMESPACE = "6ba7b810-9dad-11d1-80b4-00c04fd430c8";

export function writeAuditEvent(event: FeedIngestEvent): void {
  const eventType = `${event.stage}_${event.audit_event_type}`.replaceAll("-", "_").toUpperCase();
  writeJsonLine({
    timestamp: new Date().toISOString(), level: "INFO", message: `Pipeline Event: ${eventType}`,
    eventId: `evt_${event.event_id}`, eventType, correlationId: event.correlation_id,
    durationMs: event.step_elapsed_ms, audit: event,
  });
}

export function resolveRunPolicy(inputs: HarvestInputs, freshnessHours?: number): PolicyIdentity {
  const triage = FeedScreeningPolicySchema.strip().parse(inputs.config.triage);
  const { mmr_weights, ...curate } = FeedCurationPolicySchema.strip().parse(inputs.config.curate);
  return PolicyIdentitySchema.parse({
    policy_version: inputs.config.version, config_sha256: inputs.config_sha256,
    ...triage, ...curate, ...mmr_weights,
    ...(freshnessHours === undefined ? {} : { max_age_hours: freshnessHours }),
  });
}

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
        event_id: createUuidV5(EVENT_NAMESPACE, `audit\n${context.correlation_id}\n${sequence}`),
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
