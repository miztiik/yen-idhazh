/** Which sparse body-free progress event may leave the planner runtime? */
import { z } from "zod";
import { CountSchema, NonEmptySchema, RunIdSchema, SlugSchema } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { SourceSnapshotSchema } from "./source.schema";
import { HarvestDiagnosticsSchema } from "./harvest-diagnostics.schema";
import { ParsedFeedBatchSchema, SelectedFeedBatchSchema, PartitionedFeedBatchSchema } from "./planner-stage.schema";

export const FeedIngestEventSchema = z.strictObject({
  version: z.literal("2026-10-25").default("2026-10-25"),
  run_id: RunIdSchema, correlation_id: z.uuid({ version: "v4" }),
  occurred_at: RecordedInstantSchema,
  operation: z.enum(["history", "fetch", "parse", "select", "partition", "persist", "feed-health-summary", "plan"]),
  phase: z.enum(["started", "completed", "failed"]),
  source_id: SlugSchema.nullable(), input_count: CountSchema.nullable(), output_count: CountSchema.nullable(),
  duration_ms: CountSchema.nullable(), failure_code: NonEmptySchema.nullable(),
}).meta({
  version: "2026-10-25",
  changelog: [{ version: "2026-10-25", change: "Emit sparse body-free progress instead of article audit histories." }],
});
export type FeedIngestEvent = z.infer<typeof FeedIngestEventSchema>;
export const readFeedIngestEvent = (raw: unknown) => FeedIngestEventSchema.parse(raw);
export const PlannerWorkEventSchema = z.discriminatedUnion("stage", [
  z.strictObject({ stage: z.literal("parsed"), payload: ParsedFeedBatchSchema }),
  z.strictObject({ stage: z.literal("selected"), payload: SelectedFeedBatchSchema }),
  z.strictObject({ stage: z.literal("partitioned"), payload: PartitionedFeedBatchSchema }),
]);
export type PlannerWorkEvent = z.infer<typeof PlannerWorkEventSchema>;
export const FeedOutcomePayloadSchema = z.strictObject({
  kind: z.literal("feed_outcome"), source: SourceSnapshotSchema,
  fetch_status: z.enum(["success", "timeout", "http_failure", "network_failure", "not_requested"]),
  parse_status: z.enum(["success", "empty", "failure", "not_attempted"]),
  parsed_count: CountSchema.nullable(), harvested_count: CountSchema.nullable(),
  fetch_duration_ms: CountSchema.nullable(), parse_duration_ms: CountSchema.nullable(),
  rejection_reason: NonEmptySchema.nullable(), diagnostics: HarvestDiagnosticsSchema.nullable().default(null),
  history: z.null().default(null),
});
export type FeedOutcomePayload = z.infer<typeof FeedOutcomePayloadSchema>;
