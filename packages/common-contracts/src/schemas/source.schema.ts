/** Which configured feed facts govern access and numeric authority without article classifications? */
import { z } from "zod";
import { FiniteSchema, NonEmptySchema, PositiveCountSchema, SlugSchema, UrlSchema } from "./primitives";

export const SourceTierSchema = PositiveCountSchema;
export const PublisherIdSchema = SlugSchema;
export const LifecycleStatusSchema = z.enum(["draft", "active", "retired"]);
export const SourceSnapshotSchema = z.strictObject({
  source_id: SlugSchema, publisher_id: PublisherIdSchema.nullable().default(null),
  feed_url: UrlSchema, title: NonEmptySchema, tier: SourceTierSchema, status: LifecycleStatusSchema,
  weight: FiniteSchema.min(0).max(1), applied_tier_weight: FiniteSchema.min(0).max(1),
});
export type SourceSnapshot = z.infer<typeof SourceSnapshotSchema>;
