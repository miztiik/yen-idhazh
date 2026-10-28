/** Which completed in-memory work fact contributes to this run's health counters? */
import { z } from "zod";
import { CountSchema, PositiveCountSchema, RunIdSchema, SlugSchema, TimestampSchema } from "./primitives";
import { ExtractionFailureSchema, FetchFailureSchema } from "./harvest-diagnostics.schema";

export const DocumentWorkFactSchema = z.strictObject({
  run_id: RunIdSchema, attempt: PositiveCountSchema, feed_id: SlugSchema,
  document_kind: z.enum(["feed", "article"]), operation: z.enum(["fetch", "parse", "attempt"]),
  outcome: z.enum(["success", "empty", "failed", "not_attempted", "unavailable"]),
  occurred_at: TimestampSchema, duration_ms: CountSchema,
  http_status: z.int().min(100).max(599).nullable(),
  attribution: z.enum(["source", "pipeline", "unresolved"]).nullable(),
  failure_code: z.union([FetchFailureSchema, ExtractionFailureSchema, z.literal("malformed-feed"), z.null()]),
  request_phase: z.enum(["validation", "robots", "target"]).nullable(),
  dispatched_request_count: CountSchema.nullable(), request_coverage: z.enum(["complete", "partial", "unknown"]).nullable(),
});
export type DocumentWorkFact = z.infer<typeof DocumentWorkFactSchema>;
