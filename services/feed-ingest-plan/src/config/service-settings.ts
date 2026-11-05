/** Which authored settings bound the operator listener and its named input files? */
import { z } from "zod";
import {
  ArticleEntityLimitsSchema, DateStampSchema, MAX_PLANNER_FAILURE_CAUSES,
  NonEmptySchema, NonNegativeSchema, PositiveCountSchema,
} from "@idhazh/common-contracts";
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
}).refine(value => value.raw_files === undefined || value.raw_index === undefined, {
  message: "name raw_files or raw_index, not both",
});
export const PlannerDayInputSchema = LedgerDayInputSchema.refine(value => value.raw_index === undefined, {
  message: "Planner raw days use Parquet members, not raw_index",
}).refine(value => value.indexes === undefined, {
  message: "Planner compact membership uses exact files, not indexes",
});
export type LedgerDayInput = z.infer<typeof LedgerDayInputSchema>;
export const FailureCaptureLimitsSchema = z.strictObject({
  max_stack_chars: PositiveCountSchema.max(65536).default(16384),
  max_causes: z.int().min(0).max(MAX_PLANNER_FAILURE_CAUSES).default(MAX_PLANNER_FAILURE_CAUSES),
});
export type FailureCaptureLimits = z.infer<typeof FailureCaptureLimitsSchema>;
export const ServiceSettingsSchema = z.strictObject({
  enabled: z.boolean().default(false).describe(
    "Remove when the planner is approved for production use.",
  ),
  removal_condition: NonEmptySchema,
  dump_raw_document_contents: z.boolean().default(false).describe(
    "Append body-free failed-document metadata only to the optional private diagnostic artifact.",
  ),
  diagnostics: z.strictObject({
    failure: FailureCaptureLimitsSchema.prefault({}),
    named_entities: ArticleEntityLimitsSchema.default({ max_entities: 256, max_entity_chars: 160 }),
  }).prefault({}).describe("Per-run diagnostics run only inside the existing development service gate."),
  listener: z.strictObject({
    hostname: NonEmptySchema.describe("Standalone planner address; composed tasks use config/hono-server.json."),
    port: PositiveCountSchema.max(65535).describe("Standalone planner port; composed tasks use config/hono-server.json."),
    idle_timeout_seconds: PositiveCountSchema.max(255).describe("Standalone idle timer; composed tasks use config/hono-server.json."),
    max_body_bytes: PositiveCountSchema,
    max_stage_batches: PositiveCountSchema.default(128),
    parser_concurrency: PositiveCountSchema.default(4),
  }),
  inputs: z.strictObject({
    planning: RelativePathSchema, sources: RelativePathSchema,
    extraction: RelativePathSchema, registrations: RelativePathSchema,
    output_root: RelativePathSchema, discovered_files: z.array(RelativePathSchema).default([]),
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

export function parseRawDocumentDumpControl(value: string): boolean {
  return z.enum(["false", "true"]).parse(value) === "true";
}
