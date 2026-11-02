/** Which configured feed facts govern access and numeric authority without article classifications? */
import { z } from "zod";
import { FiniteSchema, NonEmptySchema, SlugSchema, UrlSchema } from "./primitives";
import { FEED_INGEST_CANDIDATE_VERSION } from "../version";

export const PublisherIdSchema = SlugSchema;
export const LifecycleStatusSchema = z.enum(["draft", "active", "retired"]);
export const SourceSnapshotSchema = z.strictObject({
  feed_id: SlugSchema, publisher_id: PublisherIdSchema.nullable().default(null),
  feed_url: UrlSchema, title: NonEmptySchema, status: LifecycleStatusSchema,
  weight: FiniteSchema.min(0).max(1),
}).meta({
  version: FEED_INGEST_CANDIDATE_VERSION,
  changelog: [
    { version: FEED_INGEST_CANDIDATE_VERSION, change: "Use configured feed weight without planner tier classifications or multipliers." },
  ],
});
export type SourceSnapshot = z.infer<typeof SourceSnapshotSchema>;
