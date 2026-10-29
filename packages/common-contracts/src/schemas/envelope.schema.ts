/** Which writer and recorded format identify one immutable ledger file? */
import { z } from "zod";
import { REJECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS } from "./rejected-article.schema";
import {
  DISCOVERED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS, DISCOVERED_ARTICLE_VERSION,
  LEGACY_PLANNER_ENVELOPE_VERSION, PLANNER_ENVELOPE_ACCEPTED_SCHEMA_VERSIONS,
  PLANNER_LEDGER_VERSION, PLANNER_ENVELOPE_VERSION, PLAN_RUN_VERSION,
  SELECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS, SELECTED_ARTICLE_VERSION, FEED_HEALTH_STATE_VERSION,
} from "../version";
import { RecordedInstantSchema } from "./recorded-instant.schema";
import { CommitShaSchema, CountSchema, DateStampSchema, JobNameSchema, MonthStampSchema, NonEmptySchema, PositiveCountSchema, RunIdSchema, SchemaVersionSchema, ServerJobSchema, Sha256Schema, YearStampSchema, reject } from "./primitives";

export const LedgerNameSchema = z.enum([
  "seen", "feed-health", "item-health", "host-fingerprint", "summary-quality-evals",
  "item-health-summary", "published", "feed-retirements", "visual-prunes",
  "counterfactual-scores", "scored-pairs", "fitted-thresholds", "holdout-pairs", "score-distribution",
  "archive", "metrics", "merge-line-holdout-scores", "traces", "day-metrics", "digest-fragments",
  "gardener", "run-plan", "run-shards", "council-run-records",
  "discovered-articles", "selected-articles", "rejected-articles", "feed-health-state", "plan-runs",
]);
export const TierSchema = z.enum(["raw", "compact"]);
export const PeriodSchema = z.enum(["daily", "monthly", "yearly"]);
export const FormatSchema = z.enum(["parquet", "json"]);
export const CompressionSchema = z.enum(["snappy", "zstd", "none"]);
export const FOOTER_METADATA_KEYS = [
  "envelope_version", "schema_version", "tier", "ledger", "covers", "period",
  "written_at_ms", "run_id", "attempt", "job", "pipeline_name", "task_name",
  "shard", "producer", "unit_id", "file_id", "content_sha256", "git_sha",
  "writer", "writer_version", "compression", "built_from",
] as const;
export const OPTIONAL_FOOTER_METADATA_KEYS = ["job", "period", "built_from", "pipeline_name", "task_name"] as const;
// Stored identity columns begin at these envelope revisions, as in RowIdentity.__column_versions__.
export const ROW_IDENTITY_COLUMN_VERSIONS: Readonly<Record<string, string>> = {
  pipeline_name: "2026-10-12", task_name: "2026-10-12",
};
const JobSchema = z.union([ServerJobSchema, JobNameSchema, z.null()]);
const IdentityFields = {
  run_id: RunIdSchema, attempt: PositiveCountSchema, job: JobSchema,
  pipeline_name: JobNameSchema.nullable().default(null),
  task_name: JobNameSchema.nullable().default(null), shard: CountSchema,
};
function checkWriterIdentity(value: { pipeline_name: string | null; task_name: string | null; job: string | null }, ctx: z.RefinementCtx): void {
  if ((value.pipeline_name === null) !== (value.task_name === null)) reject(ctx, "identity requires both pipeline_name and task_name");
  if (value.task_name === null && value.job === null) reject(ctx, "identity requires a legacy job or pipeline and task");
  if (value.task_name !== null && value.job !== null && value.job !== value.task_name) reject(ctx, "generic job must be absent or match its task");
}
export const WriterIdentitySchema = z.strictObject({
  ...IdentityFields, producer: NonEmptySchema, git_sha: CommitShaSchema,
}).superRefine(checkWriterIdentity);
export const RowIdentitySchema = z.strictObject({
  ledger: LedgerNameSchema, covers: DateStampSchema, ...IdentityFields,
  unit_id: z.string().regex(/^[0-9a-f]{8}-[0-9a-f]{4}-5[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/),
}).superRefine(checkWriterIdentity);
export const FILE_ENVELOPE_VERSION = "2026-10-24" as const;
export const ENVELOPE_VERSIONS = [
  FILE_ENVELOPE_VERSION, "2026-10-20", "2026-10-14", "2026-09-25", "2026-09-27", "2026-09-28", "2026-09-30",
  "2026-10-01", "2026-10-01T16:50", "2026-10-06", "2026-10-10", "2026-10-12",
] as const;
const UuidSchema = z.string().uuid();
export const FileEnvelopeSchema = z.strictObject({
  version: SchemaVersionSchema.default(FILE_ENVELOPE_VERSION),
  row_schema_version: SchemaVersionSchema, tier: TierSchema, ledger: LedgerNameSchema,
  covers: z.union([DateStampSchema, MonthStampSchema, YearStampSchema]),
  period: PeriodSchema.nullable().default(null), written_at_ms: CountSchema,
  identity: WriterIdentitySchema, unit_id: UuidSchema, file_id: UuidSchema,
  content_sha256: Sha256Schema,
  writer: z.enum(["idhazh.ledger.parquet", "idhazh.ledger.json_lines", "idhazh_rust.ledger.parquet", "idhazh_rust.ledger.json_lines", "idhazh_typescript.ledger.parquet"]),
  writer_version: NonEmptySchema, compression: CompressionSchema,
  built_from: CountSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  if (PlannerLedgerNameSchema.safeParse(value.ledger).success) reject(ctx, "planner ledgers require their minimal file envelope");
  if ((value.tier === "compact") !== (value.period !== null)) reject(ctx, "compact files need a period; raw files name no period");
  if (value.tier === "raw" && value.built_from !== null) reject(ctx, "raw files carry no built_from");
  const stamp = value.tier === "raw" || value.period === "daily" ? DateStampSchema : value.period === "monthly" ? MonthStampSchema : YearStampSchema;
  if (!stamp.safeParse(value.covers).success) reject(ctx, "covers must match tier and period");
  if (value.unit_id[14] !== "5" || value.file_id[14] !== "8") reject(ctx, "unit_id must be UUID version 5 and file_id version 8");
  if (!(ENVELOPE_VERSIONS as readonly string[]).includes(value.version)) reject(ctx, "unrecognized file envelope version");
  if (value.writer === "idhazh_typescript.ledger.parquet" && value.version < "2026-10-20") reject(ctx, "TypeScript writer requires envelope version 2026-10-20 or later");
  if (value.writer.startsWith("idhazh_rust.") && (
    value.version !== "2026-10-10" || value.row_schema_version !== "2026-10-10" ||
    value.ledger !== "host-fingerprint" || value.tier !== "raw" ||
    value.identity.producer !== "telemetry.silicon"
  )) reject(ctx, "historical host writer requires its recorded raw host contract");
  if (value.writer.endsWith(".json_lines") && value.compression !== "none") reject(ctx, "JSON lines must record compression none");
});
export function validateEnvelopeContainer(envelope: z.input<typeof FileEnvelopeSchema>, container: z.infer<typeof FormatSchema>): z.infer<typeof FileEnvelopeSchema> {
  const parsed = FileEnvelopeSchema.parse(envelope);
  const expected = FormatSchema.parse(container) === "parquet" ? ".parquet" : ".json_lines";
  if (!parsed.writer.endsWith(expected)) throw new Error("writer does not match the observed container");
  return parsed;
}
export type FileEnvelope = z.infer<typeof FileEnvelopeSchema>;
export type WriterIdentity = z.infer<typeof WriterIdentitySchema>;
export type RowIdentity = z.infer<typeof RowIdentitySchema>;

export const PlannerLedgerNameSchema = z.enum([
  "discovered-articles", "selected-articles", "rejected-articles", "feed-health-state", "plan-runs",
]);
export type PlannerLedgerName = z.infer<typeof PlannerLedgerNameSchema>;
export const PLANNER_FOOTER_METADATA_KEYS = [
  "envelope_version", "schema_version", "tier", "ledger", "covers", "period",
  "file_id", "content_sha256", "writer", "writer_version", "compression", "updated_at",
] as const;
export const PLANNER_OPTIONAL_FOOTER_METADATA_KEYS = ["period", "updated_at"] as const;
export const PlannerFileEnvelopeSchema = z.strictObject({
  version: z.enum(PLANNER_ENVELOPE_ACCEPTED_SCHEMA_VERSIONS).default(PLANNER_ENVELOPE_VERSION),
  row_schema_version: z.enum([
    ...DISCOVERED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS, ...SELECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS,
    PLAN_RUN_VERSION, ...REJECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS, FEED_HEALTH_STATE_VERSION,
  ]),
  tier: TierSchema, ledger: PlannerLedgerNameSchema,
  covers: z.union([DateStampSchema, MonthStampSchema, YearStampSchema]),
  period: PeriodSchema.nullable().default(null), file_id: UuidSchema,
  content_sha256: Sha256Schema,
  writer: z.enum(["idhazh.ledger.parquet", "idhazh_typescript.ledger.parquet"]),
  writer_version: NonEmptySchema, compression: CompressionSchema,
  updated_at: RecordedInstantSchema.nullable().default(null),
}).superRefine((value, ctx) => {
  const rowVersions = {
    "discovered-articles": DISCOVERED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS,
    "selected-articles": SELECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS,
    "rejected-articles": REJECTED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS, "feed-health-state": FEED_HEALTH_STATE_VERSION, "plan-runs": PLAN_RUN_VERSION,
  } as const;
  if ((value.version === PLANNER_LEDGER_VERSION && value.row_schema_version !== PLANNER_LEDGER_VERSION)
    || (value.row_schema_version === LEGACY_PLANNER_ENVELOPE_VERSION
      && value.version !== LEGACY_PLANNER_ENVELOPE_VERSION && value.version !== PLANNER_ENVELOPE_VERSION)
    || (["discovered-articles", "selected-articles"].includes(value.ledger)
      && ([DISCOVERED_ARTICLE_VERSION, SELECTED_ARTICLE_VERSION] as readonly string[]).includes(value.row_schema_version)
      && value.version !== PLANNER_ENVELOPE_VERSION)) {
    reject(ctx, "row schema requires its declared envelope revision");
  }
  const acceptedVersions = typeof rowVersions[value.ledger] === "string"
    ? [rowVersions[value.ledger] as string]
    : rowVersions[value.ledger] as readonly string[];
  if (!acceptedVersions.includes(value.row_schema_version)) reject(ctx, `${value.ledger} requires an accepted row schema`);
  if ((value.tier === "compact") !== (value.period !== null)) reject(ctx, "planner compact files require a period; raw files name none");
  const stamp = value.tier === "raw" || value.period === "daily" ? DateStampSchema
    : value.period === "monthly" ? MonthStampSchema : YearStampSchema;
  if (!stamp.safeParse(value.covers).success) reject(ctx, "planner covers must match its tier and period");
  if (value.file_id[14] !== "8") reject(ctx, "planner file_id must be UUID version 8");
  if ((value.ledger === "feed-health-state") !== (value.updated_at !== null)) reject(ctx, "only feed-health-state files require updated_at");
}).meta({
  version: PLANNER_ENVELOPE_VERSION,
  changelog: [
    { version: PLANNER_ENVELOPE_VERSION, change: "Accept named historical discovery and selected stamps without rewriting article identity." },
    { version: LEGACY_PLANNER_ENVELOPE_VERSION, change: "Register rejected articles and current selection and article-outcome row stamps." },
    { version: "2026-10-26", change: "Require the current row stamp for selected articles and plan runs." },
    { version: PLANNER_LEDGER_VERSION, change: "Declare planner-only file metadata without generic writer identity." },
  ],
});
export type PlannerFileEnvelope = z.infer<typeof PlannerFileEnvelopeSchema>;
