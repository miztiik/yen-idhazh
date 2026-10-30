/** Which UTC instant first established an article's global URL identity? */
import { z } from "zod";
import {
  DISCOVERED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS, DISCOVERED_ARTICLE_VERSION,
  LEGACY_DISCOVERED_ARTICLE_VERSION,
} from "../version";
import { DateStampSchema, Sha256Schema, reject } from "./primitives";
import { RecordedInstantSchema } from "./recorded-instant.schema";

export const DiscoveredArticleRowSchema = z.strictObject({
  url_key: Sha256Schema, first_seen_at: RecordedInstantSchema, date: DateStampSchema,
}).superRefine((value, ctx) => {
  if (value.date !== value.first_seen_at.slice(0, 10)) reject(ctx, "discovery date must be the UTC day of first_seen_at");
}).meta({
  version: DISCOVERED_ARTICLE_VERSION,
  changelog: [
    { version: DISCOVERED_ARTICLE_VERSION, change: "Identify query-free article discovery while retaining historical keys unchanged." },
    { version: LEGACY_DISCOVERED_ARTICLE_VERSION, change: "Record the first global discovery instant and its UTC day." },
  ],
});
export type DiscoveredArticleRow = z.infer<typeof DiscoveredArticleRowSchema>;
export const DiscoveredArticleRowContract = {
  schema: DiscoveredArticleRowSchema, schemaVersion: DISCOVERED_ARTICLE_VERSION,
  acceptedSchemaVersions: DISCOVERED_ARTICLE_ACCEPTED_SCHEMA_VERSIONS,
} as const;
