/** Which bounded native inputs support one saved feed-health state revision? */
import { createHash } from "node:crypto";
import { z } from "zod";
import { FEED_HEALTH_STATE_VERSION } from "../version";
import { DocumentObservationRecordSchema } from "./ingest-observations.schema";
import { FeedHealthRowSchema } from "./feed-health.schema";
import {
  CountSchema, DateStampSchema, NonEmptySchema, NonNegativeSchema, PositiveCountSchema,
  Sha256Schema, SlugSchema, TimestampSchema, reject,
} from "./primitives";

const RelativePosixPathSchema = NonEmptySchema.refine(value =>
  !value.startsWith("/") && !value.includes("\\") && !value.includes(":")
    && value.split("/").every(part => part !== "" && part !== "." && part !== ".."),
  "state evidence paths must be relative POSIX paths",
);
function isCanonicalUtcDay(day: string): boolean {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(day) || day.startsWith("0000-")) return false;
  const parsed = new Date(`${day}T00:00:00Z`);
  return Number.isFinite(parsed.valueOf()) && parsed.toISOString().slice(0, 10) === day;
}
function matchesNativeFilePath(
  path: string,
  prefix: string,
  tier: "raw" | "compact",
  period: "daily" | "monthly" | "yearly" | null,
  fileId: string,
): boolean {
  const parts = path.slice(prefix.length).split("/");
  if (tier === "raw") {
    return period === null && parts.length === 4
      && parts[3] === `${fileId}.parquet`
      && isCanonicalUtcDay(parts.slice(0, 3).join("-"));
  }
  if (period === null || !parts.at(-1)?.endsWith(".parquet")) return false;
  const cover = parts.at(-1)!.slice(0, -".parquet".length);
  if (period === "yearly") {
    return parts.length === 3 && parts[0] === "yearly" && parts[1] === cover
      && /^\d{4}$/.test(cover) && isCanonicalUtcDay(`${cover}-01-01`);
  }
  if (period === "monthly") {
    return parts.length === 3 && parts[0] === "monthly" && /^\d{4}$/.test(parts[1]!)
      && /^\d{2}$/.test(cover) && isCanonicalUtcDay(`${parts[1]}-${cover}-01`);
  }
  return parts.length === 4 && parts[0] === "daily" && /^\d{4}$/.test(parts[1]!)
    && /^\d{2}$/.test(parts[2]!) && isCanonicalUtcDay(`${parts[1]}-${parts[2]}-${cover}`);
}
const FeedHealthLedgerSchema = z.enum([
  "feed-health", "document-observations", "ingest-observations",
]);
export const FeedHealthStateIndexIdentitySchema = z.strictObject({
  ledger: FeedHealthLedgerSchema,
  kind: z.enum(["raw", "daily", "monthly", "yearly"]),
  path: RelativePosixPathSchema,
  content_sha256: Sha256Schema,
  day_membership_sha256: Sha256Schema,
}).superRefine((value, ctx) => {
  const tier = value.kind === "raw" ? "raw" : "compact";
  const prefix = value.ledger === "feed-health"
    ? `state/${tier}/feed-health/`
    : `state/${tier}/feed-ingest-plan/${value.ledger}/`;
  if (!value.path.startsWith(prefix)) reject(ctx, "index path matches its native ledger and tier");
});
export const FeedHealthStateFileIdentitySchema = z.strictObject({
  ledger: FeedHealthLedgerSchema,
  tier: z.enum(["raw", "compact"]),
  period: z.enum(["daily", "monthly", "yearly"]).nullable(),
  path: RelativePosixPathSchema,
  file_id: z.uuid({ version: "v8" }),
  content_sha256: Sha256Schema,
  file_sha256: Sha256Schema.nullable(),
  bytes: CountSchema,
  row_count: CountSchema,
}).superRefine((value, ctx) => {
  if ((value.tier === "raw") !== (value.period === null)) {
    reject(ctx, "raw files have no compact period and compact files name one");
  }
  if ((value.tier === "compact") !== (value.file_sha256 !== null)) {
    reject(ctx, "compact file identities retain their indexed byte digest");
  }
  const prefix = value.ledger === "feed-health"
    ? `state/${value.tier}/feed-health/`
    : `state/${value.tier}/feed-ingest-plan/${value.ledger}/`;
  if (!value.path.startsWith(prefix)
    || !matchesNativeFilePath(value.path, prefix, value.tier, value.period, value.file_id)) {
    reject(ctx, "Parquet path matches its native ledger, tier, period and file identity");
  }
});
export const FeedHealthStateInputIdentitySchema = z.strictObject({
  input_day: DateStampSchema,
  fingerprint: Sha256Schema,
  indexes: z.array(FeedHealthStateIndexIdentitySchema).min(1),
  files: z.array(FeedHealthStateFileIdentitySchema),
}).superRefine((value, ctx) => {
  const indexPaths = value.indexes.map(item => item.path);
  const filePaths = value.files.map(item => item.path);
  const fileIds = value.files.map(item => item.file_id);
  const indexedLedgers = new Set(value.indexes.map(item => item.ledger));
  if (value.files.some(item => !indexedLedgers.has(item.ledger))) {
    reject(ctx, "each named Parquet file belongs to an identified native ledger");
  }
  if (new Set(indexPaths).size !== indexPaths.length) reject(ctx, "day identity names each native index once");
  if (new Set(filePaths).size !== filePaths.length || new Set(fileIds).size !== fileIds.length) {
    reject(ctx, "day identity names each native file once");
  }
});

const GapReasonSchema = z.enum([
  "missing", "lost", "unreadable", "set-aside", "index-identity-unavailable",
]);
export const FeedHealthStateLifecycleDaySchema = z.strictObject({
  input_day: DateStampSchema,
  read_status: z.enum(["available", "gap"]),
  gap_reason: GapReasonSchema.nullable(),
  input_identity: FeedHealthStateInputIdentitySchema.nullable(),
  observed_fingerprint: Sha256Schema.nullable(),
  rows: z.array(FeedHealthRowSchema),
}).superRefine((value, ctx) => {
  if (value.read_status === "available") {
    if (value.input_identity === null || value.gap_reason !== null
      || value.observed_fingerprint !== value.input_identity.fingerprint) {
      reject(ctx, "an available lifecycle day has a verified current contribution");
    }
  } else if (value.gap_reason === null) {
    reject(ctx, "an unreadable lifecycle day records its gap reason");
  }
  if (value.input_identity === null && value.rows.length > 0) {
    reject(ctx, "retained lifecycle rows name their verified contribution");
  }
  if (value.rows.some(row => row.date !== value.input_day)) {
    reject(ctx, "feed-health rows retain their native represented day");
  }
  if (value.input_identity !== null && value.input_identity.input_day !== value.input_day) {
    reject(ctx, "lifecycle identity names its represented input day");
  }
  if (value.input_identity !== null
    && [...value.input_identity.indexes, ...value.input_identity.files].some(item => item.ledger !== "feed-health")) {
    reject(ctx, "lifecycle evidence names only the feed-health ledger");
  }
});
export const FeedHealthStateRequestDaySchema = z.strictObject({
  input_day: DateStampSchema,
  read_status: z.enum(["available", "gap"]),
  gap_reason: GapReasonSchema.nullable(),
  input_identity: FeedHealthStateInputIdentitySchema.nullable(),
  observed_fingerprint: Sha256Schema.nullable(),
  rows: z.array(DocumentObservationRecordSchema),
}).superRefine((value, ctx) => {
  if (value.read_status === "available") {
    if (value.input_identity === null || value.gap_reason !== null
      || value.observed_fingerprint !== value.input_identity.fingerprint) {
      reject(ctx, "an available request day has a verified current contribution");
    }
  } else if (value.gap_reason === null) {
    reject(ctx, "an unreadable request day records its gap reason");
  }
  if (value.input_identity === null && value.rows.length > 0) {
    reject(ctx, "retained request rows name their verified contribution");
  }
  if (value.input_identity !== null && value.input_identity.input_day !== value.input_day) {
    reject(ctx, "request identity names its closed input day");
  }
  if (value.input_identity !== null
    && [...value.input_identity.indexes, ...value.input_identity.files].some(item =>
      item.ledger !== "document-observations" && item.ledger !== "ingest-observations")) {
    reject(ctx, "request evidence names only current or migrated observation ledgers");
  }
  if (value.rows.some(row => row.occurred_at.slice(0, 10) !== value.input_day)) {
    reject(ctx, "document observations retain their native occurrence day");
  }
});
export const FeedHealthStateSnapshotReferenceSchema = z.strictObject({
  snapshot_role: z.enum(["latest", "previous"]),
  path: RelativePosixPathSchema,
  file_id: z.uuid({ version: "v8" }),
  content_sha256: Sha256Schema,
  bytes: CountSchema,
  row_count: CountSchema,
  state_revision: PositiveCountSchema,
  parent_revision: PositiveCountSchema.nullable(),
}).superRefine((value, ctx) => {
  const root = "state/raw/feed-ingest-plan/feed-health-state/";
  if (!value.path.startsWith(root)) {
    reject(ctx, "snapshot path belongs to the feed-health-state raw ledger");
  }
  const parts = value.path.slice(root.length).split("/");
  const day = parts.slice(0, 3).join("-");
  const clock = new Date(`${day}T00:00:00Z`);
  if (parts.length !== 4 || parts.slice(0, 3).some(part => !/^\d{4}$|^\d{2}$/.test(part))
    || !Number.isFinite(clock.valueOf()) || clock.toISOString().slice(0, 10) !== day) {
    reject(ctx, "snapshot path follows the native raw UTC day layout");
  }
  if (parts[3] !== `${value.file_id}.parquet`) {
    reject(ctx, "snapshot path must end with its native file identifier");
  }
  if ((value.state_revision === 1) !== (value.parent_revision === null)) {
    reject(ctx, "the first snapshot has no parent and later revisions name one");
  }
  if (value.parent_revision !== null && value.parent_revision + 1 !== value.state_revision) {
    reject(ctx, "snapshot revision follows its actual parent");
  }
  if (value.row_count !== 1) reject(ctx, "each snapshot file contains exactly one complete state row");
});
export const FeedHealthStateHeadIndexSchema = z.strictObject({
  version: z.literal(FEED_HEALTH_STATE_VERSION).default(FEED_HEALTH_STATE_VERSION),
  ledger: z.literal("feed-health-state").default("feed-health-state"),
  latest: FeedHealthStateSnapshotReferenceSchema,
  previous: FeedHealthStateSnapshotReferenceSchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.latest.snapshot_role !== "latest") reject(ctx, "head index latest reference names the latest slot");
  if (value.previous !== null) {
    if (value.previous.snapshot_role !== "previous") reject(ctx, "head index previous reference names the previous slot");
    if (value.previous.state_revision >= value.latest.state_revision) {
      reject(ctx, "previous snapshot revision is older than latest");
    }
    if (value.latest.parent_revision !== value.previous.state_revision) {
      reject(ctx, "latest snapshot parent is the previous saved revision");
    }
    if (value.previous.path === value.latest.path || value.previous.file_id === value.latest.file_id) {
      reject(ctx, "latest and previous snapshots are independent files");
    }
  } else if (value.latest.parent_revision !== null) {
    reject(ctx, "a noninitial latest snapshot retains its previous revision");
  }
});
export const FeedHealthStateInventorySourceSchema = z.strictObject({
  source_id: SlugSchema,
  endpoint_key: Sha256Schema,
  publisher_id: SlugSchema.nullable(),
  registry_status: z.enum(["draft", "active", "retired"]),
});
export const FeedHealthStateReliabilitySchema = z.strictObject({
  success_fraction: NonNegativeSchema.max(1),
  productive: CountSchema,
  attempted: PositiveCountSchema,
  window_days: PositiveCountSchema,
  from_day: DateStampSchema.nullable(),
  through_day: DateStampSchema.nullable(),
  production_factor: NonNegativeSchema.max(1),
}).superRefine((value, ctx) => {
  if (value.productive > value.attempted
    || value.success_fraction !== value.productive / value.attempted) {
    reject(ctx, "success fraction matches the settled feed rows");
  }
  if (value.production_factor < value.success_fraction) {
    reject(ctx, "production factor does not fall below measured success");
  }
  if ((value.from_day === null) !== (value.through_day === null)
    || (value.from_day !== null && value.through_day !== null && value.from_day > value.through_day)) {
    reject(ctx, "reliability evidence bounds are available and ordered");
  }
});
export const FeedHealthStateLifecycleResultSchema = z.strictObject({
  input_status: z.enum(["complete", "partial", "unavailable"]),
  lifecycle: z.enum(["eligible", "resting", "retired", "unknown"]),
  strikes: CountSchema.nullable(),
  rested_runs: CountSchema.nullable(),
  robots_permission: z.enum(["allowed", "denied", "unverified"]),
  reliability: FeedHealthStateReliabilitySchema.nullable(),
}).superRefine((value, ctx) => {
  if (value.lifecycle === "unknown" && (value.strikes !== null || value.rested_runs !== null)) {
    reject(ctx, "unknown lifecycle does not claim strike or rest counts");
  }
});
export const FeedHealthStateRequestResultSchema = z.strictObject({
  input_status: z.enum(["complete", "partial", "unavailable"]),
  qualification_status: z.enum(["qualified", "insufficient_support", "unavailable"]),
  measured_target_requests: CountSchema.nullable(),
  measured_source_wasted_requests: CountSchema.nullable(),
  observed_attempted_opportunities: CountSchema.nullable(),
  observed_measured_opportunities: CountSchema.nullable(),
  measured_coverage: NonNegativeSchema.max(1).nullable(),
  request_waste_ratio: NonNegativeSchema.max(1).nullable(),
  request_component_weight: NonNegativeSchema.max(1),
  request_component_penalty: NonNegativeSchema.max(1).nullable(),
}).superRefine((value, ctx) => {
  if ((value.measured_target_requests === null)
    !== (value.measured_source_wasted_requests === null)) {
    reject(ctx, "measured request totals and waste are available together");
  }
  if (value.measured_target_requests !== null
    && value.measured_source_wasted_requests! > value.measured_target_requests) {
    reject(ctx, "wasted requests cannot exceed measured requests");
  }
  if (value.observed_attempted_opportunities !== null
    && value.observed_measured_opportunities !== null
    && value.observed_measured_opportunities > value.observed_attempted_opportunities) {
    reject(ctx, "measured opportunities cannot exceed attempted opportunities");
  }
  if (value.input_status !== "complete") {
    if (value.qualification_status === "qualified") {
      reject(ctx, "incomplete request inputs cannot qualify a source");
    }
    if (value.request_waste_ratio !== null || value.request_component_penalty !== null) {
      reject(ctx, "incomplete request inputs carry no score");
    }
  }
  if (value.qualification_status === "qualified") {
    if (value.measured_target_requests === null || value.measured_target_requests === 0
      || value.measured_coverage === null || value.request_waste_ratio === null
      || value.request_component_penalty === null) {
      reject(ctx, "qualified request evidence has complete positive support");
    }
    if (value.request_component_penalty
      !== value.request_waste_ratio! * value.request_component_weight) {
      reject(ctx, "request penalty matches the normalized configured weight");
    }
  } else if (value.request_waste_ratio !== null || value.request_component_penalty !== null) {
    reject(ctx, "unqualified request evidence has no estimate or score");
  }
});
export const FeedHealthStateSourceResultSchema = z.strictObject({
  source_id: SlugSchema,
  endpoint_key: Sha256Schema,
  lifecycle: FeedHealthStateLifecycleResultSchema,
  requests: FeedHealthStateRequestResultSchema,
});
function sourceInventoryDigest(sources: z.infer<typeof FeedHealthStateInventorySourceSchema>[]): string {
  return createHash("sha256").update(JSON.stringify(sources), "utf8").digest("hex");
}
function offsetUtcDay(day: string, offset: number): string {
  const instant = new Date(`${day}T00:00:00Z`);
  instant.setUTCDate(instant.getUTCDate() + offset);
  return instant.toISOString().slice(0, 10);
}

export const FeedHealthStateSnapshotSchema = z.strictObject({
  version: z.literal(FEED_HEALTH_STATE_VERSION).default(FEED_HEALTH_STATE_VERSION),
  state_revision: PositiveCountSchema,
  parent_revision: PositiveCountSchema.nullable(),
  written_at_utc: TimestampSchema,
  selection_batch_id: z.uuid({ version: "v4" }),
  selection_started_at_utc: TimestampSchema,
  code_revision: z.string().regex(/^[0-9a-f]{40}$/),
  policy_version: DateStampSchema,
  policy_sha256: Sha256Schema,
  lifecycle_window_days: PositiveCountSchema,
  lifecycle_availability: z.enum(["complete", "partial", "unavailable"]),
  lifecycle_window_start: DateStampSchema.nullable(),
  lifecycle_window_end: DateStampSchema.nullable(),
  lifecycle_days: z.array(FeedHealthStateLifecycleDaySchema),
  request_window_days: PositiveCountSchema,
  request_availability: z.enum(["complete", "partial", "unavailable"]),
  request_window_start: DateStampSchema,
  request_window_end: DateStampSchema,
  request_days: z.array(FeedHealthStateRequestDaySchema),
  source_inventory_complete: z.boolean(),
  source_inventory_sha256: Sha256Schema.nullable(),
  source_inventory: z.array(FeedHealthStateInventorySourceSchema),
  source_results: z.array(FeedHealthStateSourceResultSchema),
}).superRefine((value, ctx) => {
  if ((value.state_revision === 1) !== (value.parent_revision === null)) {
    reject(ctx, "the first snapshot has no parent and later revisions name one");
  }
  if (value.parent_revision !== null && value.parent_revision >= value.state_revision) {
    reject(ctx, "parent revision must be older than the snapshot");
  }
  if (value.parent_revision !== null && value.parent_revision + 1 !== value.state_revision) {
    reject(ctx, "snapshot revision follows its actual parent");
  }
  const lifecycleDates = value.lifecycle_days.map(day => day.input_day);
  if (lifecycleDates.length > value.lifecycle_window_days
    || lifecycleDates.some((day, index) => index > 0 && lifecycleDates[index - 1]! >= day)) {
    reject(ctx, "lifecycle days are distinct, ascending and within the configured window");
  }
  if (lifecycleDates.some(day => day > value.selection_started_at_utc.slice(0, 10))) {
    reject(ctx, "lifecycle inputs do not follow the selection start clock");
  }
  if ((lifecycleDates[0] ?? null) !== value.lifecycle_window_start
    || (lifecycleDates.at(-1) ?? null) !== value.lifecycle_window_end) {
    reject(ctx, "lifecycle bounds match the retained represented-day inputs");
  }
  const lifecycleAvailable = value.lifecycle_days.filter(day => day.read_status === "available").length;
  const lifecycleAvailability = value.lifecycle_days.length === value.lifecycle_window_days
    && lifecycleAvailable === value.lifecycle_days.length ? "complete"
    : lifecycleAvailable > 0 ? "partial" : "unavailable";
  if (value.lifecycle_availability !== lifecycleAvailability) {
    reject(ctx, "lifecycle availability matches represented-day evidence");
  }
  if (value.request_window_end !== offsetUtcDay(value.selection_started_at_utc.slice(0, 10), -1)) {
    reject(ctx, "request evidence ends on the last closed UTC day before selection");
  }
  if (offsetUtcDay(value.request_window_start, value.request_window_days - 1) !== value.request_window_end) {
    reject(ctx, "request window bounds match its configured closed-day count");
  }
  const requestDates = value.request_days.map(day => day.input_day);
  const expectedDates = Array.from(
    { length: value.request_window_days },
    (_, index) => offsetUtcDay(value.request_window_start, index),
  );
  if (requestDates.length !== expectedDates.length
    || requestDates.some((day, index) => day !== expectedDates[index])) {
    reject(ctx, "request days name every closed UTC day exactly once");
  }
  const requestAvailable = value.request_days.filter(day => day.read_status === "available").length;
  const requestAvailability = requestAvailable === value.request_window_days ? "complete"
    : requestAvailable > 0 ? "partial" : "unavailable";
  if (value.request_availability !== requestAvailability) {
    reject(ctx, "request availability matches closed-day evidence");
  }
  if (!value.source_inventory_complete) {
    if (value.source_inventory_sha256 !== null || value.source_inventory.length !== 0
      || value.source_results.length !== 0) {
      reject(ctx, "an unavailable source roster has no invented members or results");
    }
  } else {
    if (value.source_inventory_sha256 === null) {
      reject(ctx, "a complete source roster has an explicit digest, including when empty");
    }
    if (value.source_inventory_sha256 !== sourceInventoryDigest(value.source_inventory)) {
      reject(ctx, "source roster digest matches its canonical inventory");
    }
    const inventoryIds = value.source_inventory.map(item => item.source_id);
    const resultIds = value.source_results.map(item => item.source_id);
    if (inventoryIds.some((id, index) => index > 0 && inventoryIds[index - 1]! >= id)) {
      reject(ctx, "source roster is sorted and contains each source once");
    }
    if (resultIds.length !== inventoryIds.length
      || resultIds.some((id, index) => id !== inventoryIds[index])) {
      reject(ctx, "source results match the complete source roster");
    }
    const endpoints = new Map(value.source_inventory.map(item => [item.source_id, item.endpoint_key]));
    if (value.source_results.some(item => endpoints.get(item.source_id) !== item.endpoint_key)) {
      reject(ctx, "source results retain the configured endpoint identity");
    }
  }
  if (value.request_availability !== "complete"
    && value.source_results.some(item => item.requests.qualification_status === "qualified")) {
    reject(ctx, "request gaps cannot qualify retained source results");
  }
  if (value.source_results.some(item => item.lifecycle.input_status !== value.lifecycle_availability
    || item.requests.input_status !== value.request_availability)) {
    reject(ctx, "source results retain each component's input availability");
  }
});
export type FeedHealthStateSnapshot = z.infer<typeof FeedHealthStateSnapshotSchema>;
