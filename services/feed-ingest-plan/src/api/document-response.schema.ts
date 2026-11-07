/** Admit only body-free current metadata at the public document API boundary. */
import { z } from "zod";
import {
  BodyLimitEvidenceSchema, CandidateIdSchema, CountSchema, NonEmptySchema, OperationMetadataSchema, PLANNER_PROTOCOL_VERSION, PositiveCountSchema, RunIdSchema, Sha256Schema, SlugSchema, TimestampSchema, UrlSchema, FetchFailureSchema,
  HarvestDiagnosticsSchema, deriveUrlKey,
} from "@idhazh/common-contracts";

export const DOCUMENT_RESPONSE_VERSION = PLANNER_PROTOCOL_VERSION;
export const DOCUMENT_RESPONSE_CHANGELOG = [
  { version: DOCUMENT_RESPONSE_VERSION, change: "Expose fetch byte-cutoff evidence and prepared article word-limit evidence." },
] as const;

const fetchedIdentity = {
  run_id: RunIdSchema,
  feed_id: SlugSchema, canonical_url: UrlSchema,
  http_status: z.int().min(100).max(599).nullable(), failure: FetchFailureSchema.nullable(), body_sha256: Sha256Schema.nullable(),
  body_limit: BodyLimitEvidenceSchema.nullable(),
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
  if (value.body_limit !== null && value.failure !== "body-too-large") {
    ctx.addIssue({ code: "custom", path: ["body_limit"], message: "Byte-cutoff evidence requires a body-too-large failure" });
  }
}).meta({ version: DOCUMENT_RESPONSE_VERSION, changelog: DOCUMENT_RESPONSE_CHANGELOG });
export const ArticleWordLimitEvidenceSchema = z.strictObject({
  max_input_words: PositiveCountSchema,
  original_word_count: CountSchema,
  returned_word_count: CountSchema,
  truncated: z.boolean(),
}).superRefine((value, ctx) => {
  if (value.returned_word_count !== Math.min(value.original_word_count, value.max_input_words)) {
    ctx.addIssue({ code: "custom", path: ["returned_word_count"], message: "Prepared words must obey the configured ceiling" });
  }
  if (value.truncated !== (value.original_word_count > value.max_input_words)) {
    ctx.addIssue({ code: "custom", path: ["truncated"], message: "Word truncation must describe an applied cut" });
  }
});
export type ArticleWordLimitEvidence = z.infer<typeof ArticleWordLimitEvidenceSchema>;
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
    word_limit: ArticleWordLimitEvidenceSchema.nullable(),
  }),
]).meta({ version: DOCUMENT_RESPONSE_VERSION, changelog: DOCUMENT_RESPONSE_CHANGELOG });
