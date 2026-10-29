/** Which independent uses can read the verified health facts for one UTC day? */
import { isDeepStrictEqual } from "node:util";
import { z } from "zod";
import {
  FeedHealthAdmissionFieldsSchema, FeedHealthIdentitySchema, FeedHealthReliabilityFieldsSchema,
  FeedHealthRequestFieldsSchema, FeedHealthRestFieldsSchema,
} from "@idhazh/common-contracts";
import type { FeedHealthFieldUse, FeedHealthIdentity } from "@idhazh/common-contracts";
import type { LedgerRegistration } from "@idhazh/ledger-file-writer";
import type { LedgerDayInput } from "../config/service-settings";
import { LedgerHistoryReadError } from "./ledger-history-error";
import { createPlannerHistoryCache, readStoredPlannerDay } from "./read-planner-history";
import type { PlannerHistoryCache } from "./read-planner-history";

export type FeedHealthFieldGap = {
  use: FeedHealthFieldUse; field: string; day: string;
  code: "missing" | "invalid"; identity: FeedHealthIdentity | null;
};

function projectFields<S extends z.ZodRawShape>(
  day: string, records: readonly Record<string, unknown>[], schema: z.ZodObject<S>, use: FeedHealthFieldUse,
) {
  const rows: z.infer<typeof schema>[] = [];
  const partialSchema = z.object(schema.shape).partial();
  const partial_rows: z.infer<typeof partialSchema>[] = [];
  const gaps: FeedHealthFieldGap[] = [];
  for (const record of records) {
    const identity = FeedHealthIdentitySchema.safeParse(record);
    const parsed = schema.safeParse(record);
    const wrongDay = record.date !== day;
    if (parsed.success && !wrongDay) { rows.push(parsed.data); continue; }
    const valid: Record<string, unknown> = {};
    for (const [field, validator] of Object.entries(schema.shape)) {
      const cell = z.safeParse(validator, record[field]);
      if (cell.success) valid[field] = cell.data;
    }
    const paths = new Map<string, PropertyKey[]>((parsed.success ? [] : parsed.error.issues)
      .map(issue => [issue.path.map(String).join(".") || "$row", issue.path]));
    if (wrongDay) paths.set("date", ["date"]);
    for (const [field, path] of paths) {
      delete valid[String(path[0])];
      let value: unknown = record;
      for (const part of path) {
        value = typeof value === "object" && value !== null ? Reflect.get(value, part) : undefined;
      }
      gaps.push({ use, field, day, code: value === undefined ? "missing" : "invalid",
        identity: identity.success && !wrongDay ? identity.data : null });
    }
    if (identity.success && !wrongDay) partial_rows.push(partialSchema.parse(valid));
  }
  return { rows, partial_rows, gaps };
}

export function projectFeedHealthFields(day: string, records: readonly Record<string, unknown>[]) {
  const distinct = new Map<string, Record<string, unknown>>();
  const invalidIdentity: Record<string, unknown>[] = [];
  for (const record of records) {
    const identity = FeedHealthIdentitySchema.safeParse(record);
    if (!identity.success) { invalidIdentity.push(record); continue; }
    const key = JSON.stringify(identity.data);
    const previous = distinct.get(key);
    if (previous !== undefined && !isDeepStrictEqual(previous, record)) {
      throw new LedgerHistoryReadError("Conflicting copies of one finalized planner health fact");
    }
    distinct.set(key, record);
  }
  const settled = [...distinct.values(), ...invalidIdentity];
  return {
    request_totals: projectFields(day, settled, FeedHealthRequestFieldsSchema, "request_totals"),
    feed_rest: projectFields(day, settled, FeedHealthRestFieldsSchema, "feed_rest"),
    feed_reliability: projectFields(day, settled, FeedHealthReliabilityFieldsSchema, "feed_reliability"),
    article_admission: projectFields(day, settled, FeedHealthAdmissionFieldsSchema, "article_admission"),
  };
}

export async function readFeedHealthFieldsDay(
  root: string, registration: LedgerRegistration, day: LedgerDayInput,
  cache: PlannerHistoryCache<Record<string, unknown>> = createPlannerHistoryCache(),
) {
  if (registration.name !== "feed-health-state") {
    throw new LedgerHistoryReadError("Health field reads require the feed-health-state ledger");
  }
  const { rows, ...stored } = await readStoredPlannerDay(root, registration, day, cache);
  const uses = projectFeedHealthFields(day.day, rows);
  for (const view of Object.values(uses)) for (const gap of view.gaps) {
    console.error(JSON.stringify({ event: "planner_health_field_gap", ...gap }));
  }
  return { ...stored, uses };
}
