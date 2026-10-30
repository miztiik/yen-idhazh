/** Which authored settings bound the operator listener and its named input files? */
import { z } from "zod";
import { DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema } from "@idhazh/common-contracts";
import { ArtifactRootSchema } from "../selected-artifact-path";

export const RelativePathSchema = NonEmptySchema.refine(
  value => !value.includes("\\") && !value.includes(":") && !value.startsWith("/")
    && value.split("/").every(part => part !== "" && part !== "." && part !== ".."),
  "must be a relative POSIX path without parent traversal",
);
export const LedgerDayInputSchema = z.strictObject({
  day: DateStampSchema,
  indexes: z.strictObject({
    yearly: RelativePathSchema.optional(), monthly: RelativePathSchema.optional(),
    daily: RelativePathSchema.optional(),
  }).optional(),
  raw_files: z.array(RelativePathSchema).optional(),
  raw_index: RelativePathSchema.optional(),
  raw_revision: z.string().regex(/^[0-9a-f]{40}$/).optional(),
}).refine(value => value.raw_files === undefined || value.raw_index === undefined, {
  message: "name raw_files or raw_index, not both",
});
export const PlannerDayInputSchema = LedgerDayInputSchema.refine(value => value.raw_index === undefined, {
  message: "Planner raw days use Parquet members, not raw_index",
}).refine(value => value.indexes === undefined, {
  message: "Planner compact membership uses exact files, not indexes",
}).refine(value => value.raw_files === undefined || value.raw_revision !== undefined, {
  message: "Configured planner raw_files require their complete raw_revision",
});
export type LedgerDayInput = z.infer<typeof LedgerDayInputSchema>;
export const ServiceSettingsSchema = z.strictObject({
  enabled: z.boolean().default(false).describe(
    "Remove when the planner is approved for production use.",
  ),
  removal_condition: NonEmptySchema,
  listener: z.strictObject({
    hostname: NonEmptySchema, port: PositiveCountSchema.max(65535),
    idle_timeout_seconds: PositiveCountSchema.max(255),
    max_body_bytes: PositiveCountSchema,
    max_stage_batches: PositiveCountSchema.default(128),
    parser_concurrency: PositiveCountSchema.default(4),
  }),
  supervision: z.strictObject({
    readiness_timeout_ms: PositiveCountSchema,
    shutdown_timeout_ms: PositiveCountSchema,
    forced_exit_timeout_ms: PositiveCountSchema,
  }),
  inputs: z.strictObject({
    planning: RelativePathSchema, taxonomy: RelativePathSchema, sources: RelativePathSchema,
    extraction: RelativePathSchema, registrations: RelativePathSchema,
    output_root: RelativePathSchema, discovered_files: z.array(RelativePathSchema).default([]),
    digest_root: RelativePathSchema.default("frontend/public/digest"),
    published_url_lookback_days: NonNegativeSchema.optional(),
    artifact_root: ArtifactRootSchema.default("backend/var/feed-ingest-plan"),
    health_period_limit: PositiveCountSchema.default(32),
    feed_health_input_gap: z.boolean().default(false),
    discovered_days: z.array(PlannerDayInputSchema).default([]),
    published_days: z.array(LedgerDayInputSchema).default([]),
    settled_failure_days: z.array(LedgerDayInputSchema).default([]),
    feed_health_days: z.array(PlannerDayInputSchema).default([]),
  }),
});
export type ServiceSettings = z.infer<typeof ServiceSettingsSchema>;
