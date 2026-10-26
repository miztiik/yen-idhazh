/** Admit only body-free current metadata at the public document API boundary. */
import { z } from "zod";
import {
  CountSchema, NonEmptySchema, RequestIdSchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema, FetchFailureSchema,
} from "@idhazh/common-contracts";

export const FetchResponseSchema = z.strictObject({
  fetch_request_id: RequestIdSchema, batch_id: RequestIdSchema, run_id: RunIdSchema, correlation_id: RequestIdSchema,
  kind: z.enum(["feed", "article"]), feed_id: SlugSchema, article_id: Sha256Schema, canonical_url: UrlSchema,
  http_status: z.int().min(100).max(599).nullable(), failure: FetchFailureSchema.nullable(), body_sha256: Sha256Schema.nullable(),
});
const parsedIdentity = {
  batch_id: RequestIdSchema, fetch_request_id: RequestIdSchema, run_id: RunIdSchema,
  parsed_count: CountSchema, failure: NonEmptySchema.nullable(),
};
export const ParseResponseSchema = z.discriminatedUnion("kind", [
  z.strictObject({
    ...parsedIdentity, kind: z.literal("feed"), offers: z.array(z.strictObject({
      offer_id: Sha256Schema, feed_id: SlugSchema, canonical_url: UrlSchema, title: z.string().nullable(),
      categories: z.array(z.string()), published_at: TimestampSchema.nullable(),
    })),
  }),
  z.strictObject({ ...parsedIdentity, kind: z.literal("article"), pending_offers: CountSchema }),
]);
