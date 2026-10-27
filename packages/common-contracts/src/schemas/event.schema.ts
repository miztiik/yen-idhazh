/** Which sparse body-free progress event may leave the planner runtime? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, RunIdSchema, SlugSchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { SourceSnapshotSchema } from "./source.schema";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema } from "./planner-stage.schema";
import { PlanApiTimingSchema } from "./plan-run.schema";
import { FEED_OUTCOME_PAYLOAD_VERSION } from "../version";

export const FeedIngestEventSchema = z.strictObject({
  version: z.literal("2026-10-26").default("2026-10-26"),
  run_id: RunIdSchema, correlation_id: z.uuid({ version: "v4" }),
  occurred_at: RecordedInstantSchema,
  operation: z.enum(["history", ...PlanApiTimingSchema.shape.operation.options, "plan"]),
  phase: z.enum(["started", "completed", "failed"]),
  feed_id: SlugSchema.nullable(), input_count: CountSchema.nullable(), output_count: CountSchema.nullable(),
  duration_ms: CountSchema.nullable(), failure_code: NonEmptySchema.nullable(),
}).meta({
  version: "2026-10-26",
  changelog: [
    { version: "2026-10-26", change: "Name pre-fetch and selection health captures separately." },
  ],
});
export type FeedIngestEvent = z.infer<typeof FeedIngestEventSchema>;
export function readFeedIngestEvent(raw: unknown): FeedIngestEvent {
  return FeedIngestEventSchema.parse(raw);
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
