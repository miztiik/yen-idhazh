/** Which bounded native inputs support one saved feed-health state revision? */
import { z } from "zod";
import { FEED_HEALTH_STATE_VERSION } from "../version";
import { DocumentObservationRecordSchema } from "./ingest-observations.schema";
import { FeedHealthRowSchema } from "./feed-health.schema";
import {
  CountSchema, DateStampSchema, NonEmptySchema, PositiveCountSchema, Sha256Schema,
  TimestampSchema, reject,
} from "./primitives";

const RelativePosixPathSchema = NonEmptySchema.refine(value =>
  !value.startsWith("/") && !value.includes("\\") && !value.includes(":")
    && value.split("/").every(part => part !== "" && part !== "." && part !== ".."),
  "state evidence paths must be relative POSIX paths",
);
const FeedHealthLedgerSchema = z.enum([
  "feed-health", "document-observations", "ingest-observations",
]);
export const FeedHealthStateIndexIdentitySchema = z.strictObject({
  ledger: FeedHealthLedgerSchema,
  kind: z.enum(["raw", "daily", "monthly", "yearly"]),
  path: RelativePosixPathSchema,
  content_sha256: Sha256Schema,
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
  bytes: CountSchema,
  row_count: CountSchema,
}).superRefine((value, ctx) => {
  if ((value.tier === "raw") !== (value.period === null)) {
    reject(ctx, "raw files have no compact period and compact files name one");
  }
  const prefix = value.ledger === "feed-health"
    ? `state/${value.tier}/feed-health/`
    : `state/${value.tier}/feed-ingest-plan/${value.ledger}/`;
  if (!value.path.startsWith(prefix) || !value.path.endsWith(`/${value.file_id}.parquet`)) {
    reject(ctx, "Parquet path matches its native ledger, tier and file identifier");
  }
});
export const FeedHealthStateInputIdentitySchema = z.strictObject({
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

export const FeedHealthStateLifecycleDaySchema = z.strictObject({
  input_day: DateStampSchema,
  read_status: z.enum(["available", "gap"]),
  gap_reason: z.enum(["missing", "lost", "unreadable", "set-aside"]).nullable(),
  input_identity: FeedHealthStateInputIdentitySchema.nullable(),
  rows: z.array(FeedHealthRowSchema),
}).superRefine((value, ctx) => {
  if (value.read_status === "available") {
    if (value.input_identity === null || value.gap_reason !== null) {
      reject(ctx, "an available lifecycle day has a verified identity and no gap");
    }
  } else if (value.gap_reason === null) {
    reject(ctx, "an unreadable lifecycle day records its gap reason");
  }
  if (value.rows.some(row => row.date !== value.input_day)) {
    reject(ctx, "feed-health rows retain their native represented day");
  }
  if (value.input_identity !== null
    && [...value.input_identity.indexes, ...value.input_identity.files].some(item => item.ledger !== "feed-health")) {
    reject(ctx, "lifecycle evidence names only the feed-health ledger");
  }
});
export const FeedHealthStateRequestDaySchema = z.strictObject({
  input_day: DateStampSchema,
  read_status: z.enum(["available", "gap"]),
  gap_reason: z.enum(["missing", "lost", "unreadable", "set-aside"]).nullable(),
  input_identity: FeedHealthStateInputIdentitySchema.nullable(),
  rows: z.array(DocumentObservationRecordSchema),
}).superRefine((value, ctx) => {
  if (value.read_status === "available") {
    if (value.input_identity === null || value.gap_reason !== null) {
      reject(ctx, "an available request day has a verified identity and no gap");
    }
  } else if (value.gap_reason === null) {
    reject(ctx, "an unreadable request day records its gap reason");
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
  if (!value.path.startsWith("state/raw/feed-ingest-plan/feed-health-state/")) {
    reject(ctx, "snapshot path belongs to the feed-health-state raw ledger");
  }
  if (!value.path.endsWith(`/${value.file_id}.parquet`)) {
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
function offsetUtcDay(day: string, offset: number): string {
  const instant = new Date(`${day}T00:00:00Z`);
  instant.setUTCDate(instant.getUTCDate() + offset);
  return instant.toISOString().slice(0, 10);
}

export const FeedHealthStateSnapshotSchema = z.strictObject({
  version: z.literal(FEED_HEALTH_STATE_VERSION).default(FEED_HEALTH_STATE_VERSION),
  snapshot_role: z.enum(["latest", "previous"]),
  state_revision: PositiveCountSchema,
  parent_revision: PositiveCountSchema.nullable(),
  written_at_utc: TimestampSchema,
  selection_batch_id: z.uuid({ version: "v4" }),
  selection_started_at_utc: TimestampSchema,
  code_revision: z.string().regex(/^[0-9a-f]{40}$/),
  policy_version: DateStampSchema,
  policy_sha256: Sha256Schema,
  lifecycle_window_days: PositiveCountSchema,
  lifecycle_window_start: DateStampSchema.nullable(),
  lifecycle_window_end: DateStampSchema.nullable(),
  lifecycle_days: z.array(FeedHealthStateLifecycleDaySchema),
  request_window_days: PositiveCountSchema,
  request_window_start: DateStampSchema,
  request_window_end: DateStampSchema,
  request_days: z.array(FeedHealthStateRequestDaySchema),
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
});
export type FeedHealthStateSnapshot = z.infer<typeof FeedHealthStateSnapshotSchema>;
