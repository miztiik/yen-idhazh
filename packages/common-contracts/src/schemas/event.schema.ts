/** Which sparse body-free progress event may leave the planner runtime? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, RunIdSchema } from "./primitives";
import { SourceSnapshotSchema } from "./source.schema";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema } from "./planner-stage.schema";
import { PlanApiTimingSchema } from "./plan-run.schema";
import { FEED_INGEST_EVENT_VERSION, FEED_OUTCOME_PAYLOAD_VERSION } from "../version";
import { CloudEventSchema } from "./cloud-event.schema";
import { readCloudEvent } from "../read-cloud-event";

const FEED_INGEST_OPERATIONS = ["history", ...PlanApiTimingSchema.shape.operation.options, "plan", "artifact-upload", "quality", "request-attempt"] as const;
export const FeedIngestEventDataSchema = z.strictObject({
  version: z.literal(FEED_INGEST_EVENT_VERSION),
  run_id: RunIdSchema,
  operation: z.enum(FEED_INGEST_OPERATIONS),
  phase: z.enum(["started", "completed", "failed"]),
  details: z.record(z.string(), z.json()),
});
export const FeedIngestEventSchema = CloudEventSchema.safeExtend({
  type: z.literal("planner.progress"), data: FeedIngestEventDataSchema,
}).meta({
  version: FEED_INGEST_EVENT_VERSION,
  changelog: [
    { version: FEED_INGEST_EVENT_VERSION, change: "Wrap sparse planner progress in a current CloudEvents envelope." },
    { version: "2026-11-02", change: "Remove robots fields and request categories from progress evidence." },
    { version: "2026-11-01", change: "Add independently validated native request-failure evidence." },
    { version: "2026-11-01", change: "Require current progress events without earlier-version conversion." },
    { version: "2026-10-29T08:00", change: "Earlier changes are in this file's Git history." },
  ],
});
export type FeedIngestEvent = z.infer<typeof FeedIngestEventSchema>;
export type FeedIngestEventData = z.infer<typeof FeedIngestEventDataSchema>;
export function readFeedIngestEvent(raw: unknown): FeedIngestEvent {
  return FeedIngestEventSchema.parse(readCloudEvent(raw, value => FeedIngestEventDataSchema.parse(value)));
}
export const PlannerWorkEventSchema = z.discriminatedUnion("stage", [
  z.strictObject({ stage: z.literal("parsed"), payload: ParsedFeedBatchSchema }),
  z.strictObject({ stage: z.literal("selected"), payload: SelectedFeedBatchSchema }),
  z.strictObject({ stage: z.literal("partitioned"), payload: PartitionedFeedBatchSchema }),
]);
export type PlannerWorkEvent = z.infer<typeof PlannerWorkEventSchema>;
export const FeedOutcomePayloadSchema = z.strictObject({
  version: z.literal(FEED_OUTCOME_PAYLOAD_VERSION).default(FEED_OUTCOME_PAYLOAD_VERSION),
  kind: z.literal("feed_outcome"), source: SourceSnapshotSchema,
  fetch_status: z.enum(["success", "timeout", "http_failure", "network_failure", "not_requested"]),
  parse_status: z.enum(["success", "empty", "failure", "not_attempted"]),
  parsed_count: CountSchema.nullable(), harvested_count: CountSchema.nullable(),
  fetch_duration_ms: CountSchema.nullable(), parse_duration_ms: CountSchema.nullable(),
  rejection_reason: NonEmptySchema.nullable(), diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  history: z.null().default(null),
}).meta({
  version: FEED_OUTCOME_PAYLOAD_VERSION,
  changelog: [
    { version: FEED_OUTCOME_PAYLOAD_VERSION, change: "Carry target-only fetch diagnostics in feed outcomes." },
    { version: FEED_OUTCOME_PAYLOAD_VERSION, change: "Retain source weights without planner tier fields." },
    { version: "2026-10-31", change: "Retain decoded response byte-limit evidence." },
    { version: "2026-10-27", change: "Remove source classification fields from planner feed outcomes." },
  ],
});
export type FeedOutcomePayload = z.infer<typeof FeedOutcomePayloadSchema>;
