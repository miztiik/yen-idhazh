/** Admit only body-free current metadata at the public document API boundary. */
import { z } from "zod";
import {
  CountSchema, NonEmptySchema, OperationMetadataSchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema, FetchFailureSchema,
  HarvestDiagnosticsSchema,
} from "@idhazh/common-contracts";

export const FetchResponseSchema = OperationMetadataSchema.safeExtend({
  run_id: RunIdSchema,
  fetch_item_type: z.enum(["feed", "article"]), feed_id: SlugSchema, article_id: Sha256Schema, canonical_url: UrlSchema,
  http_status: z.int().min(100).max(599).nullable(), failure: FetchFailureSchema.nullable(), body_sha256: Sha256Schema.nullable(),
});
const parsedIdentity = {
  run_id: RunIdSchema,
  parsed_count: CountSchema, failure: NonEmptySchema.nullable(),
};
export const ParseResponseSchema = z.discriminatedUnion("fetch_item_type", [
  OperationMetadataSchema.safeExtend({
    ...parsedIdentity, fetch_item_type: z.literal("feed"), offers: z.array(z.strictObject({
      offer_id: Sha256Schema, feed_id: SlugSchema, canonical_url: UrlSchema, title: z.string().nullable(),
      categories: z.array(z.string()), published_at: TimestampSchema.nullable(),
    })),
  }),
  OperationMetadataSchema.safeExtend({
    ...parsedIdentity, fetch_item_type: z.literal("article"), pending_offers: CountSchema,
    warnings: HarvestDiagnosticsSchema.shape.warnings,
  }),
]);
