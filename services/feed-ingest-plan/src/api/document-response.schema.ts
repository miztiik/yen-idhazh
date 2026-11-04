/** Admit only body-free current metadata at the public document API boundary. */
import { z } from "zod";
import {
  CandidateIdSchema, CountSchema, NonEmptySchema, OperationMetadataSchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema, FetchFailureSchema,
  HarvestDiagnosticsSchema, deriveUrlKey,
} from "@idhazh/common-contracts";

const fetchedIdentity = {
  run_id: RunIdSchema,
  feed_id: SlugSchema, canonical_url: UrlSchema,
  http_status: z.int().min(100).max(599).nullable(), failure: FetchFailureSchema.nullable(), body_sha256: Sha256Schema.nullable(),
};
export const FetchResponseSchema = z.discriminatedUnion("fetch_item_type", [
  OperationMetadataSchema.safeExtend({ ...fetchedIdentity, fetch_item_type: z.literal("feed"), document_id: Sha256Schema }),
  OperationMetadataSchema.safeExtend({
    ...fetchedIdentity, fetch_item_type: z.literal("article"), article_id: Sha256Schema, candidate_id: CandidateIdSchema,
  }),
]).superRefine((value, ctx) => {
  const field = value.fetch_item_type === "feed" ? "document_id" : "article_id";
  const identity = value.fetch_item_type === "feed" ? value.document_id : value.article_id;
  if (value.canonical_url.includes("#") || deriveUrlKey(value.canonical_url) !== identity) {
    ctx.addIssue({ code: "custom", path: [field], message: "Resource identity must match its canonical URL" });
  }
});
const parsedIdentity = {
  run_id: RunIdSchema,
  parsed_count: CountSchema, failure: NonEmptySchema.nullable(),
};
export const ParseResponseSchema = z.discriminatedUnion("fetch_item_type", [
  OperationMetadataSchema.safeExtend({
    ...parsedIdentity, fetch_item_type: z.literal("feed"), feed_id: SlugSchema, document_id: Sha256Schema,
    offers: z.array(z.strictObject({
      article_id: Sha256Schema, candidate_id: CandidateIdSchema, feed_id: SlugSchema, canonical_url: UrlSchema, title: z.string().nullable(),
      categories: z.array(z.string()), published_at: TimestampSchema.nullable(),
    }).refine(offer => !offer.canonical_url.includes("#") && deriveUrlKey(offer.canonical_url) === offer.article_id,
      { path: ["article_id"], message: "Offered article identity must match its canonical URL" })),
  }),
  OperationMetadataSchema.safeExtend({
    ...parsedIdentity, fetch_item_type: z.literal("article"), article_id: Sha256Schema, candidate_id: CandidateIdSchema, pending_offers: CountSchema,
    warnings: HarvestDiagnosticsSchema.shape.warnings,
  }),
]);
