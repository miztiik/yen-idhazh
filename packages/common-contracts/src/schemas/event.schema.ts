/** Which sparse body-free progress event may leave the planner runtime? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, RunIdSchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { SourceSnapshotSchema } from "./source.schema";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema } from "./planner-stage.schema";
import { PlanApiTimingSchema } from "./plan-run.schema";
import {
  FEED_INGEST_EVENT_VERSION, FEED_OUTCOME_PAYLOAD_VERSION, LEGACY_FEED_INGEST_EVENT_VERSION,
} from "../version";

const LEGACY_FEED_INGEST_EVENT_OPERATIONS = ["history", ...PlanApiTimingSchema.shape.operation.options, "plan", "artifact-upload"] as const;
export const FeedIngestEventSchema = z.strictObject({
  version: z.literal(FEED_INGEST_EVENT_VERSION).default(FEED_INGEST_EVENT_VERSION),
  run_id: RunIdSchema, correlation_id: z.uuid({ version: "v4" }),
  occurred_at: RecordedInstantSchema,
  operation: z.enum([...LEGACY_FEED_INGEST_EVENT_OPERATIONS, "quality"]),
  phase: z.enum(["started", "completed", "failed"]),
  details: z.record(z.string(), z.json()),
}).meta({
  version: FEED_INGEST_EVENT_VERSION,
  changelog: [
    { version: FEED_INGEST_EVENT_VERSION, change: "Add separate quality-rejection events beside artifact inventory and safe article addresses." },
    { version: "2026-10-29", change: "Move operation-specific fields into flexible details." },
    { version: "2026-10-28", change: "Name the publisher on sparse article progress events." },
    { version: "2026-10-26", change: "Name pre-fetch and selection health captures separately." },
  ],
});
export type FeedIngestEvent = z.infer<typeof FeedIngestEventSchema>;
const LegacyFeedIngestEventSchema = FeedIngestEventSchema.extend({
  version: z.literal(LEGACY_FEED_INGEST_EVENT_VERSION),
  operation: z.enum(LEGACY_FEED_INGEST_EVENT_OPERATIONS),
});
export function readFeedIngestEvent(raw: unknown): FeedIngestEvent {
  const current = FeedIngestEventSchema.safeParse(raw);
  if (current.success) return current.data;
  const legacy = LegacyFeedIngestEventSchema.safeParse(raw);
  if (!legacy.success) return FeedIngestEventSchema.parse(raw);
  return FeedIngestEventSchema.parse({ ...legacy.data, version: FEED_INGEST_EVENT_VERSION });
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
    { version: FEED_OUTCOME_PAYLOAD_VERSION, change: "Remove source classification fields from planner feed outcomes." },
  ],
});
export type FeedOutcomePayload = z.infer<typeof FeedOutcomePayloadSchema>;
