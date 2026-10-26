/** Which UTC instant first established an article's global URL identity? */
import { z } from "zod";
import { PLANNER_LEDGER_VERSION } from "../version";
import { DateStampSchema, Sha256Schema, reject } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const DiscoveredArticleRowSchema = z.strictObject({
  url_key: Sha256Schema, first_seen_at: RecordedInstantSchema, date: DateStampSchema,
}).superRefine((value, ctx) => {
  if (value.date !== value.first_seen_at.slice(0, 10)) reject(ctx, "discovery date must be the UTC day of first_seen_at");
});
export type DiscoveredArticleRow = z.infer<typeof DiscoveredArticleRowSchema>;
export const DiscoveredArticleRowContract = {
  schema: DiscoveredArticleRowSchema, schemaVersion: PLANNER_LEDGER_VERSION,
} as const;
