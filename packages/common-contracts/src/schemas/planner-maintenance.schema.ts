/** What the Python scheduler asks TypeScript to compact, and what it may safely replace. */
import { z } from "zod";
import {
  CommitShaSchema, CountSchema, DateStampSchema, MonthStampSchema,
  RelPathSchema, Sha256Schema, YearStampSchema, reject,
} from "./primitives";
import { PlannerLedgerNameSchema } from "./envelope.schema";

export const PLANNER_MAINTENANCE_VERSION = "2026-10-27" as const;
const CompactPeriodSchema = z.enum(["daily", "monthly", "yearly"]);
const PeriodStampSchema = z.union([DateStampSchema, MonthStampSchema, YearStampSchema]);
const RelativeLedgerPathSchema = RelPathSchema.refine(path => /\.(json|parquet)$/.test(path));
const RelativeParquetPathSchema = RelativeLedgerPathSchema.refine(path => path.endsWith(".parquet"));

export const PlannerMaintenanceRequestSchema = z.strictObject({
  version: z.literal(PLANNER_MAINTENANCE_VERSION).default(PLANNER_MAINTENANCE_VERSION),
  revision: CommitShaSchema,
  staging_root: z.string().regex(/^\.planner-maintenance-[0-9a-f]{32}$/),
  ledger: PlannerLedgerNameSchema,
  period: CompactPeriodSchema,
  covers: PeriodStampSchema,
  max_raw_files_per_period: z.int().positive(),
  registry_entry: z.strictObject({
    name: PlannerLedgerNameSchema,
    family: z.string().min(1),
    grain: z.literal("raw-and-compact"),
    lifecycle_status: z.enum(["active", "paused", "retired"]),
    prefix: z.array(z.string().min(1)).min(1),
  }),
  ledger_settings: z.strictObject({
    format: z.literal("parquet"),
    compression_raw: z.enum(["snappy", "zstd", "none"]),
    compression_compact: z.enum(["snappy", "zstd", "none"]),
  }),
}).superRefine((request, ctx) => {
  const stamp = request.period === "yearly" ? YearStampSchema
    : request.period === "monthly" ? MonthStampSchema : DateStampSchema;
  if (!stamp.safeParse(request.covers).success) reject(ctx, "covers must match the requested compact period", ["covers"]);
  if (request.registry_entry.name !== request.ledger
    || request.registry_entry.family !== "feed-ingest-plan"
    || request.registry_entry.lifecycle_status !== "active"
    || request.registry_entry.prefix.join("/") !== `feed-ingest-plan/${request.ledger}`) {
    reject(ctx, "planner maintenance requires its active registered ledger", ["registry_entry"]);
  }
}).meta({
  version: PLANNER_MAINTENANCE_VERSION,
  changelog: [{ version: PLANNER_MAINTENANCE_VERSION, change: "Declare revision-pinned planner compact maintenance." }],
});
export type PlannerMaintenanceRequest = z.infer<typeof PlannerMaintenanceRequestSchema>;

const SourceFileSchema = z.strictObject({
  path: RelativeParquetPathSchema,
  tier: z.enum(["raw", "compact"]),
  period: CompactPeriodSchema.nullable(),
  covers: PeriodStampSchema,
  bytes: CountSchema,
  file_sha256: Sha256Schema,
});
const InputGapSchema = z.enum([
  "missing-local-member", "changed-member", "malformed-member", "unsupported-member", "revision-changed",
]);
export const PlannerMaintenanceResultSchema = z.discriminatedUnion("status", [
  z.strictObject({
    version: z.literal(PLANNER_MAINTENANCE_VERSION),
    status: z.literal("written"),
    revision: CommitShaSchema,
    ledger: PlannerLedgerNameSchema,
    period: CompactPeriodSchema,
    covers: PeriodStampSchema,
    target_path: RelativeParquetPathSchema,
    output_path: RelativeParquetPathSchema,
    expected_target_sha256: Sha256Schema.nullable(),
    target_file_sha256: Sha256Schema,
    content_sha256: Sha256Schema,
    target_bytes: CountSchema,
    row_count: CountSchema,
    carried_over: z.boolean(),
    input_files: z.array(SourceFileSchema),
    delete_paths: z.array(RelativeParquetPathSchema),
  }),
  z.strictObject({
    version: z.literal(PLANNER_MAINTENANCE_VERSION),
    status: z.literal("empty"),
    revision: CommitShaSchema,
    ledger: PlannerLedgerNameSchema,
    period: CompactPeriodSchema,
    covers: PeriodStampSchema,
  }),
  z.strictObject({
    version: z.literal(PLANNER_MAINTENANCE_VERSION),
    status: z.literal("unchanged"),
    revision: CommitShaSchema,
    ledger: PlannerLedgerNameSchema,
    period: CompactPeriodSchema,
    covers: PeriodStampSchema,
    reason: z.enum(["higher-precedence-compact", "already-current"]),
  }),
  z.strictObject({
    version: z.literal(PLANNER_MAINTENANCE_VERSION),
    status: z.literal("refused"),
    revision: CommitShaSchema,
    ledger: PlannerLedgerNameSchema,
    period: CompactPeriodSchema,
    covers: PeriodStampSchema,
    reason: InputGapSchema.or(z.literal("target-conflict")),
    path: RelativeLedgerPathSchema.nullable(),
  }),
]).meta({
  version: PLANNER_MAINTENANCE_VERSION,
  changelog: [{ version: PLANNER_MAINTENANCE_VERSION, change: "Return validated compact receipts or explicit maintenance refusals." }],
});
export type PlannerMaintenanceResult = z.infer<typeof PlannerMaintenanceResultSchema>;
